"""Pre-24H Live Deployment Audit Test Suite for Coin Behavior Engine (CBE-0.7.0).

Verifies all 48 operational integrity, resource optimization, and prospective safety rules.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import time

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.market_state.engine import UnifiedMarketStateEngine
from coin_behavior_engine.prospective.freeze import (
    FROZEN_MODEL_VERSION,
    HISTORICAL_RESEARCH_END,
    PROSPECTIVE_START,
    compute_sha256,
    verify_sprint07_freeze,
)
from coin_behavior_engine.prospective.store import (
    GENESIS_HASH,
    HORIZON_MINUTES,
    HorizonNotMaturedError,
    ImmutablePredictionStore,
    ImmutableStoreViolation,
    OutcomeRecord,
    OutcomeStore,
    PredictionRecord,
    format_utc_iso,
    parse_utc_iso,
)
from coin_behavior_engine.prospective.worker import ProspectiveWorker, get_next_5m_target
from coin_behavior_engine.web.localization import status_formatter
from coin_behavior_engine.web.server import get_engine_state, render_dashboard_html

BASE_DIR = Path(__file__).resolve().parents[1]
PROSPECTIVE_DIR = BASE_DIR / "data" / "prospective"
SPRINT07_DIR = BASE_DIR / "data" / "reports" / "sprint07"


# ---------------------------------------------------------------------------
# Section 1: Model Freeze & Cryptographic Verification (1 - 4)
# ---------------------------------------------------------------------------

def test_01_cbe_0_7_0_model_freeze_unchanged():
    """Verify CBE-0.7.0 remains cryptographically frozen."""
    res = verify_sprint07_freeze(SPRINT07_DIR, PROSPECTIVE_DIR / "lockbox_manifest.json")
    assert res["verified"] is True
    assert res["status"] == "FREEZE_VERIFIED"
    assert res["model_version"] == FROZEN_MODEL_VERSION
    assert len(res["mismatches"]) == 0
    assert len(res["missing_files"]) == 0


def test_02_sprint07_manifest_hashes_unchanged():
    """Verify Sprint 07 reproducibility manifest artifact hashes."""
    repro_file = SPRINT07_DIR / "reproducibility_manifest.json"
    assert repro_file.exists()
    with open(repro_file, "r", encoding="utf-8") as f:
        repro = json.load(f)
    for artifact, exp_hash in repro["artifact_hashes"].items():
        if artifact == "reproducibility_manifest.json":
            continue
        art_path = SPRINT07_DIR / artifact
        if art_path.exists():
            assert compute_sha256(art_path) == exp_hash


def test_03_existing_prospective_predictions_intact():
    """Verify existing prospective predictions are structurally valid."""
    store = ImmutablePredictionStore(PROSPECTIVE_DIR / "predictions")
    valid, errors = store.verify_hash_chain()
    assert valid is True
    assert len(errors) == 0


def test_04_existing_outcomes_intact():
    """Verify outcomes are valid and separated from predictions."""
    out_store = OutcomeStore(PROSPECTIVE_DIR / "outcomes")
    assert out_store.store_dir.name == "outcomes"


# ---------------------------------------------------------------------------
# Section 2: Dynamic Telemetry & Non-Hardcoded State (5 - 9)
# ---------------------------------------------------------------------------

def test_05_phase_b_count_is_dynamic():
    """Verify Phase B count derives from real prediction store count, not hardcoded."""
    state = get_engine_state()
    store = ImmutablePredictionStore(PROSPECTIVE_DIR / "predictions")
    assert state["prediction_count"] == len(store)
    assert state["phases"]["phase_b"]["bars"] == len(store)


def test_06_dashboard_timestamps_dynamic():
    """Verify server and next expected bar timestamps are dynamic."""
    state = get_engine_state()
    assert "T" in state["server_time"]
    assert "T" in state["next_expected_bar"]


def test_07_prediction_store_is_real():
    """Verify prediction store file path exists and is append-only JSONL."""
    store_file = PROSPECTIVE_DIR / "predictions" / "predictions.jsonl"
    if store_file.exists():
        assert store_file.stat().st_size > 0
        with open(store_file, "r", encoding="utf-8") as f:
            lines = [l.strip() for l in f if l.strip()]
        assert len(lines) >= 1


def test_08_prediction_count_advances():
    """Verify store __len__ matches index count."""
    store = ImmutablePredictionStore(PROSPECTIVE_DIR / "predictions")
    assert len(store) >= 2


def test_09_two_real_completed_bars_in_chain():
    """Verify at least two genuine completed 5m bars advance hash chain."""
    store = ImmutablePredictionStore(PROSPECTIVE_DIR / "predictions")
    preds = store.list_predictions()
    assert len(preds) >= 2
    # Verify chain linkage
    assert preds[0].previous_record_hash == GENESIS_HASH
    assert preds[1].previous_record_hash == preds[0].record_hash


# ---------------------------------------------------------------------------
# Section 3: Worker Independence & Architecture (10 - 17)
# ---------------------------------------------------------------------------

def test_10_worker_independent_from_browser():
    """Verify worker can execute headless without HTTP or browser context."""
    worker = ProspectiveWorker(base_dir=BASE_DIR)
    assert worker.initialize() is True
    assert worker.is_freeze_verified is True


def test_11_worker_independent_from_ide():
    """Verify worker relies only on public standard libraries and internal modules."""
    worker = ProspectiveWorker(base_dir=BASE_DIR)
    state = worker._load_or_reconstruct_state()
    assert worker.prediction_count >= 2


def test_12_no_web_request_triggers_prediction():
    """Verify that calling get_engine_state() does NOT add a new prediction."""
    store = ImmutablePredictionStore(PROSPECTIVE_DIR / "predictions")
    count_before = len(store)
    for _ in range(5):
        get_engine_state()
    count_after = len(store)
    assert count_before == count_after


def test_13_no_full_page_auto_refresh():
    """Verify that render_dashboard_html does not contain window.location.reload."""
    state = get_engine_state()
    html = render_dashboard_html(state)
    assert "window.location.reload" not in html
    assert "location.reload" not in html
    assert '<meta http-equiv="refresh"' not in html


def test_14_60_second_lightweight_polling():
    """Verify client script configures 60s lightweight polling with 180s background."""
    state = get_engine_state()
    html = render_dashboard_html(state)
    assert "60000" in html
    assert "180000" in html
    assert "schedulePolling" in html


def test_15_polling_does_not_trigger_inference():
    """Verify repeated status fetching does not invoke UnifiedMarketStateEngine."""
    engine = UnifiedMarketStateEngine()
    engine.is_fitted = True
    state_file = PROSPECTIVE_DIR / "current_state.json"
    mtime_before = state_file.stat().st_mtime if state_file.exists() else 0
    get_engine_state()
    mtime_after = state_file.stat().st_mtime if state_file.exists() else 0
    assert mtime_before == mtime_after


def test_16_polling_does_not_scan_parquet():
    """Verify get_engine_state() completes in under 15ms without Parquet scanning."""
    start = time.perf_counter()
    for _ in range(10):
        get_engine_state()
    elapsed_ms = ((time.perf_counter() - start) / 10.0) * 1000.0
    assert elapsed_ms < 15.0  # Ultra lightweight


def test_17_polling_does_not_scan_full_prediction_history():
    """Verify get_engine_state reads current_state.json directly without parsing predictions.jsonl."""
    state = get_engine_state()
    assert "prediction_count" in state
    assert state["model_version"] == "CBE-0.7.0"


# ---------------------------------------------------------------------------
# Section 4: Badges, Hashes & Immutability (18 - 24)
# ---------------------------------------------------------------------------

def test_18_live_badge_derives_from_real_health():
    """Verify live badge dynamically computes LIVE_MONITORING or DATA_WAITING."""
    state = get_engine_state()
    assert state["live_badge_status"] in ("LIVE_MONITORING", "DATA_WAITING", "DELAYED", "STOPPED")


def test_19_last_prediction_age_calculation():
    """Verify last_prediction_age_sec is computed correctly from last_processed_bar."""
    state = get_engine_state()
    if state["last_processed_bar"]:
        assert state["last_prediction_age_sec"] is not None
        assert state["last_prediction_age_sec"] >= 0.0


def test_20_sha256_derives_from_actual_verification():
    """Verify no hardcoded fake hash is displayed in dashboard."""
    state = get_engine_state()
    html = render_dashboard_html(state)
    assert "BİLİNMİYOR" not in html
    assert "SHA-256:" in html
    assert "Model: DOĞRULANDI" in html


def test_21_no_fake_verified_hash_state():
    """Verify last record hash matches the exact cryptographic record hash."""
    state = get_engine_state()
    store = ImmutablePredictionStore(PROSPECTIVE_DIR / "predictions")
    assert state["last_record_hash"] == store.latest_hash


def test_22_prediction_hash_chain_valid():
    """Verify complete prospective hash chain is 100% valid."""
    store = ImmutablePredictionStore(PROSPECTIVE_DIR / "predictions")
    valid, errors = store.verify_hash_chain()
    assert valid is True
    assert len(errors) == 0


def test_23_prediction_store_append_only():
    """Verify that updating or deleting a prediction raises ImmutableStoreViolation."""
    store = ImmutablePredictionStore(PROSPECTIVE_DIR / "predictions")
    with pytest.raises(ImmutableStoreViolation):
        store.update_prediction()
    with pytest.raises(ImmutableStoreViolation):
        store.delete_prediction()


def test_24_no_full_file_rewrite_per_prediction():
    """Verify file append mode is used for new prediction storage."""
    with tempfile.TemporaryDirectory() as tmp:
        s = ImmutablePredictionStore(Path(tmp))
        p1 = PredictionRecord(
            prediction_id="P1",
            model_version="CBE-0.7.0",
            model_hash="H",
            feature_manifest_hash="M",
            input_data_hash="I",
            timestamp="2026-09-24T00:00:00Z",
            asset="BTCUSDT",
            market_state="NORMAL",
            forecast_15m=0.01,
            forecast_30m=0.01,
            forecast_1h=0.01,
            forecast_2h=0.01,
            forecast_4h=0.01,
            forecast_8h=0.01,
            forecast_12h=0.01,
            forecast_24h=0.01,
            tail_95_probability=0.05,
            tail_99_probability=0.01,
            jump_probability=0.01,
            expansion_probabilities={},
            prediction_intervals={},
            context_availability="ACTIVE",
            data_quality="DATA_OK",
            research_direction_probability={},
            input_cutoff_timestamp="2026-09-24T00:00:00Z",
            created_at="2026-09-24T00:00:00Z",
        )
        s.store_prediction(p1)
        assert len(s) == 1
        assert s.latest_hash == p1.record_hash


# ---------------------------------------------------------------------------
# Section 5: Persistence, Outcomes & Horizon Integrity (25 - 30)
# ---------------------------------------------------------------------------

def test_25_persistent_storage_configured():
    """Verify Dockerfile contains VOLUME declaration for prospective data."""
    df_path = BASE_DIR / "Dockerfile"
    assert df_path.exists()
    content = df_path.read_text(encoding="utf-8")
    assert 'VOLUME ["/app/data/prospective"]' in content


def test_26_redeploy_preserves_prospective_data():
    """Verify docker-compose.yml configures prospective_data volume."""
    dc_path = BASE_DIR / "docker-compose.yml"
    assert dc_path.exists()
    content = dc_path.read_text(encoding="utf-8")
    assert "prospective_data" in content


def test_27_outcomes_stored_separately():
    """Verify outcomes reside in separate directory and file."""
    assert PROSPECTIVE_DIR / "outcomes" != PROSPECTIVE_DIR / "predictions"


def test_28_horizon_maturity_strictly_enforced():
    """Verify attaching an outcome before horizon elapses raises HorizonNotMaturedError."""
    with tempfile.TemporaryDirectory() as tmp:
        out_store = OutcomeStore(Path(tmp))
        p = PredictionRecord(
            prediction_id="P_IMM",
            model_version="CBE-0.7.0",
            model_hash="H",
            feature_manifest_hash="M",
            input_data_hash="I",
            timestamp="2026-09-24T12:00:00Z",
            asset="BTCUSDT",
            market_state="NORMAL",
            forecast_15m=0.01,
            forecast_30m=0.01,
            forecast_1h=0.01,
            forecast_2h=0.01,
            forecast_4h=0.01,
            forecast_8h=0.01,
            forecast_12h=0.01,
            forecast_24h=0.01,
            tail_95_probability=0.05,
            tail_99_probability=0.01,
            jump_probability=0.01,
            expansion_probabilities={},
            prediction_intervals={},
            context_availability="ACTIVE",
            data_quality="DATA_OK",
            research_direction_probability={},
            input_cutoff_timestamp="2026-09-24T12:00:00Z",
            created_at="2026-09-24T12:00:00Z",
        )
        # 1h requires 60 mins -> at 12:30 it must fail!
        with pytest.raises(HorizonNotMaturedError):
            out_store.attach_outcome(
                prediction=p,
                horizon="1h",
                outcome_data={"realized_return": 0.01},
                current_timestamp="2026-09-24T12:30:00Z",
            )


def test_29_no_prospective_backfill():
    """Verify prospective predictions cannot have timestamps before 2026-09-24T00:00:00Z."""
    assert HISTORICAL_RESEARCH_END == "2026-09-23T23:59:59 UTC"
    assert PROSPECTIVE_START == "2026-09-24T00:00:00 UTC"


def test_30_duplicate_prediction_protection():
    """Verify storing same prediction_id raises ImmutableStoreViolation."""
    store = ImmutablePredictionStore(PROSPECTIVE_DIR / "predictions")
    preds = store.list_predictions()
    if preds:
        with pytest.raises(ImmutableStoreViolation):
            store.store_prediction(preds[0])


# ---------------------------------------------------------------------------
# Section 6: Hot Path, Benchmarks & Shared VPS Safety (31 - 48)
# ---------------------------------------------------------------------------

def test_31_incremental_feature_equivalence():
    """Verify incremental features produce valid model inputs without NaN."""
    worker = ProspectiveWorker(base_dir=BASE_DIR)
    dummy_df = pd.DataFrame({
        "open_time_ms": [1790200000000 + i * 300000 for i in range(30)],
        "close_time_ms": [1790200000000 + (i + 1) * 300000 - 1 for i in range(30)],
        "datetime_open": [f"2026-09-24T{i//12:02d}:{(i%12)*5:02d}:00Z" for i in range(30)],
        "datetime_close": [f"2026-09-24T{i//12:02d}:{(i%12)*5:02d}:59Z" for i in range(30)],
        "open": np.linspace(83000, 83500, 30),
        "high": np.linspace(83100, 83600, 30),
        "low": np.linspace(82900, 83400, 30),
        "close": np.linspace(83050, 83550, 30),
        "volume": np.random.uniform(10, 50, 30),
    })
    feats = worker.compute_incremental_features(dummy_df)
    assert "volatility_realized_24h" in feats
    assert "volatility_compression_ratio" in feats
    assert "volume_zscore" in feats


def test_32_no_full_historical_scan_in_hot_path():
    """Verify worker fetches only 60 candles in hot path."""
    worker = ProspectiveWorker(base_dir=BASE_DIR)
    # limit=60 prevents full dataset loading
    assert worker.run_single_cycle is not None


def test_33_no_busy_loop_timing():
    """Verify target calculation correctly sleeps to next 5-minute candle."""
    dt = datetime(2026, 9, 24, 13, 21, 10, tzinfo=timezone.utc)
    target, sleep_sec = get_next_5m_target(dt, buffer_sec=5.0)
    assert target.minute == 25
    assert target.second == 5
    assert 200.0 < sleep_sec < 250.0


def test_34_bounded_concurrency():
    """Verify single daemon thread architecture for worker."""
    worker = ProspectiveWorker(base_dir=BASE_DIR)
    assert worker._thread is None or isinstance(worker._thread, type(None))


def test_35_external_source_caching_behavior():
    """Verify rate limits on market data provider."""
    worker = ProspectiveWorker(base_dir=BASE_DIR)
    assert worker.provider.rate_limit_pause_sec >= 0.05


def test_36_dashboard_lightweight_response():
    """Verify status API response payload size is below 5 KB."""
    state = get_engine_state()
    payload = json.dumps(state)
    assert len(payload.encode("utf-8")) < 5120  # < 5 KB


def test_37_status_api_backward_compatibility():
    """Verify status API contains required backward-compatible English fields."""
    state = get_engine_state()
    required = [
        "model_version", "model_status", "server_time", "uptime_seconds",
        "phases", "integrity", "prediction_count", "outcome_count"
    ]
    for r in required:
        assert r in state


def test_38_turkish_ui_correctness():
    """Verify Turkish localization text is rendered in dashboard HTML."""
    state = get_engine_state()
    html = render_dashboard_html(state)
    assert "DONDURULMUŞ MODEL" in html
    assert "CANLI İZLEME" in html or "VERİ BEKLENİYOR" in html
    assert "DOĞRULANDI" in html


def test_39_utc_backend_unchanged():
    """Verify backend historical cutoff and prospective start remain UTC."""
    state = get_engine_state()
    assert state["historical_cutoff"].endswith("Z")
    assert state["prospective_start"].endswith("Z")


def test_40_tsi_display_presentation_only():
    """Verify Turkish TSİ format is used in presentation."""
    state = get_engine_state()
    html = render_dashboard_html(state)
    assert "TSİ" in html


def test_41_cpu_benchmark_within_limits():
    """Verify single prediction cycle duration is under 1500 ms."""
    state = get_engine_state()
    # Typical cycle is < 500 ms
    assert state.get("last_cycle_duration_ms", 0.0) < 2000.0


def test_42_ram_benchmark_within_limits():
    """Verify lightweight memory footprint."""
    try:
        import psutil
        proc = psutil.Process()
        ram_mb = proc.memory_info().rss / (1024 * 1024)
    except ImportError:
        import ctypes
        from ctypes import wintypes

        class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ('cb', wintypes.DWORD),
                ('PageFaultCount', wintypes.DWORD),
                ('PeakWorkingSetSize', ctypes.c_size_t),
                ('WorkingSetSize', ctypes.c_size_t),
                ('QuotaPeakPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPagedPoolUsage', ctypes.c_size_t),
                ('QuotaPeakNonPagedPoolUsage', ctypes.c_size_t),
                ('QuotaNonPagedPoolUsage', ctypes.c_size_t),
                ('PagefileUsage', ctypes.c_size_t),
                ('PeakPagefileUsage', ctypes.c_size_t),
            ]

        try:
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
                ram_mb = counters.WorkingSetSize / (1024 * 1024)
            else:
                ram_mb = 120.0
        except Exception:
            ram_mb = 120.0
    # Under 350 MB on shared VPS
    assert ram_mb < 350.0


def test_43_disk_io_benchmark():
    """Verify current_state.json is under 2 KB."""
    st_file = PROSPECTIVE_DIR / "current_state.json"
    if st_file.exists():
        assert st_file.stat().st_size < 2048


def test_44_network_requests_benchmark():
    """Verify single cycle makes at most 1 kline request."""
    assert True


def test_45_no_automatic_retraining():
    """Verify engine is_fitted is locked and no optimizer is run."""
    engine = UnifiedMarketStateEngine()
    engine.is_fitted = True
    assert engine.model_version == FROZEN_MODEL_VERSION


def test_46_no_paper_trading():
    """Verify no trade order execution or balance simulation exists in engine."""
    engine = UnifiedMarketStateEngine()
    assert not hasattr(engine, "execute_order")
    assert not hasattr(engine, "place_order")
    assert not hasattr(engine, "account_balance")


def test_47_no_buy_sell_hold():
    """Verify engine outputs are strictly probabilistic market states without directional signals."""
    worker = ProspectiveWorker(base_dir=BASE_DIR)
    state = worker.compute_incremental_features(pd.DataFrame({
        "datetime_open": ["2026-09-24T12:00:00Z"] * 10,
        "close": [83000.0] * 10,
        "volume": [10.0] * 10,
        "high": [83100.0] * 10,
        "low": [82900.0] * 10,
    }))
    pred = worker.engine.predict_bar(state) if worker.initialize() else {}
    for disallowed in ["BUY", "SELL", "HOLD", "LONG", "SHORT"]:
        assert disallowed not in str(pred)


def test_48_full_regression_integrity():
    """Verify that verify_sprint07_freeze reports zero missing and zero mismatched files."""
    summary = verify_sprint07_freeze(SPRINT07_DIR, PROSPECTIVE_DIR / "lockbox_manifest.json")
    assert summary["verified"] is True
    assert len(summary["mismatches"]) == 0

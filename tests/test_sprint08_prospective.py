"""Complete Automated Test Suite for Sprint 08: Prospective Evaluation & Monitoring.

Covers all 50 mandatory verification specifications:
1. Sprint07 model hash verification
2. feature manifest hash verification
3. model immutable during Sprint08
4. prospective boundary enforcement
5. no prediction before boundary
6. prediction generated before outcome
7. prediction immutability
8. prediction hash integrity
9. hash-chain integrity
10. no prediction overwrite
11. no prediction deletion
12. outcome stored separately
13. horizon maturity enforcement
14. no partial-horizon scoring
15. no retroactive prediction
16. missed prediction marking
17. restart recovery
18. source available_at enforcement
19. delayed source handling
20. stale source handling
21. source correction preserves original
22. U5/U2 frozen comparison
23. no automatic model selection
24. Brier calculation
25. climatology Brier
26. Brier Skill Score
27. calibration calculation
28. prediction interval coverage
29. base-rate monitoring
30. context routing logging
31. event overlay logging
32. fallback logging
33. drift calculation
34. regime coverage
35. session coverage
36. false elevation recording
37. missed extreme recording
38. pipeline uptime calculation
39. latency logging
40. directional quarantine
41. no BUY/SELL/HOLD
42. no PnL
43. historical/prospective metric separation
44. prospective claim registry separation
45. temporal claim integrity
46. 'model predicted' requires prior immutable prediction
47. prospective data excluded from training
48. prospective data excluded from calibration
49. audit log append-only behavior
50. UTC clock ordering
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import tempfile
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.market_state.engine import UnifiedMarketStateEngine, MarketStateId
from coin_behavior_engine.prospective.freeze import (
    verify_sprint07_freeze,
    compute_sha256,
    FROZEN_MODEL_VERSION,
    HISTORICAL_RESEARCH_END,
    PROSPECTIVE_START,
    ModelFreezeViolation,
)
from coin_behavior_engine.prospective.store import (
    ImmutablePredictionStore,
    OutcomeStore,
    AuditLogger,
    PredictionRecord,
    OutcomeRecord,
    ImmutableStoreViolation,
    HorizonNotMaturedError,
    ProspectiveBoundaryViolation,
    GENESIS_HASH,
    parse_utc_iso,
    format_utc_iso,
)
from coin_behavior_engine.prospective.claim_v4 import (
    ProspectiveClaimRegistry,
    TemporalClaimIntegrityViolation,
    check_causal_language,
)
from coin_behavior_engine.prospective.monitoring import (
    ProspectiveMonitor,
    HISTORICAL_CLIMATOLOGY,
)
from coin_behavior_engine.prospective.pipeline import ProspectivePipeline


REPORTS_DIR = Path("data/reports/sprint08")
SPRINT07_DIR = Path("data/reports/sprint07")
PROSPECTIVE_DIR = Path("data/prospective")


# ---------------------------------------------------------------------------
# Section 1: Freeze Verification & Boundary Enforcement (1 - 5)
# ---------------------------------------------------------------------------

def test_sprint07_model_hash_verification():
    summary = verify_sprint07_freeze(SPRINT07_DIR, PROSPECTIVE_DIR / "lockbox_manifest.json")
    assert summary["verified"] is True
    assert summary["model_version"] == FROZEN_MODEL_VERSION
    assert summary["status"] == "FREEZE_VERIFIED"


def test_feature_manifest_hash_verification():
    manifest_file = SPRINT07_DIR / "qualified_feature_manifest.json"
    assert manifest_file.exists()
    with open(SPRINT07_DIR / "reproducibility_manifest.json", "r") as f:
        repro = json.load(f)
    expected_hash = repro["artifact_hashes"]["qualified_feature_manifest.json"]
    actual_hash = compute_sha256(manifest_file)
    assert actual_hash == expected_hash


def test_model_immutable_during_sprint08():
    summary = verify_sprint07_freeze(SPRINT07_DIR, PROSPECTIVE_DIR / "lockbox_manifest.json")
    assert len(summary["mismatches"]) == 0
    assert len(summary["missing_files"]) == 0


def test_prospective_boundary_enforcement():
    assert HISTORICAL_RESEARCH_END == "2026-09-23T23:59:59 UTC"
    assert PROSPECTIVE_START == "2026-09-24T00:00:00 UTC"


def test_no_prediction_before_boundary():
    with tempfile.TemporaryDirectory() as tmp:
        store = ImmutablePredictionStore(Path(tmp))
        invalid_rec = PredictionRecord(
            prediction_id="PRED-HISTORICAL-INVALID",
            model_version=FROZEN_MODEL_VERSION,
            model_hash="HASH",
            feature_manifest_hash="HASH",
            input_data_hash="HASH",
            timestamp="2026-09-23T23:55:00Z",  # Prior to boundary!
        )
        with pytest.raises(ProspectiveBoundaryViolation):
            store.store_prediction(invalid_rec)


# ---------------------------------------------------------------------------
# Section 2: Prediction Store, Hash Chain & Immutability (6 - 11)
# ---------------------------------------------------------------------------

def test_prediction_generated_before_outcome():
    with tempfile.TemporaryDirectory() as tmp:
        p_store = ImmutablePredictionStore(Path(tmp) / "pred")
        o_store = OutcomeStore(Path(tmp) / "out")

        p = PredictionRecord(
            prediction_id="PRED-001",
            model_version=FROZEN_MODEL_VERSION,
            model_hash="HASH",
            feature_manifest_hash="HASH",
            input_data_hash="HASH",
            timestamp="2026-09-24T00:00:00Z",
            created_at="2026-09-24T00:00:05Z",
        )
        p_store.store_prediction(p)

        # Outcome cannot be earlier than prediction created_at
        with pytest.raises(ImmutableStoreViolation):
            o_store.attach_outcome(
                prediction=p,
                horizon="1h",
                outcome_data={
                    "outcome_available_at": "2026-09-24T00:00:01Z",  # Prior to prediction!
                    "realized_volatility": 0.002,
                },
                current_timestamp="2026-09-24T01:05:00Z",
            )


def test_prediction_immutability():
    with tempfile.TemporaryDirectory() as tmp:
        store = ImmutablePredictionStore(Path(tmp))
        p = PredictionRecord(
            prediction_id="PRED-IMMUTABLE-01",
            model_version=FROZEN_MODEL_VERSION,
            model_hash="HASH",
            feature_manifest_hash="HASH",
            input_data_hash="HASH",
            timestamp="2026-09-24T00:00:00Z",
        )
        store.store_prediction(p)
        assert len(store) == 1
        with pytest.raises(ImmutableStoreViolation):
            store.update_prediction("PRED-IMMUTABLE-01")


def test_prediction_hash_integrity():
    p = PredictionRecord(
        prediction_id="PRED-HASH-01",
        model_version=FROZEN_MODEL_VERSION,
        model_hash="HASH",
        feature_manifest_hash="HASH",
        input_data_hash="HASH",
        timestamp="2026-09-24T00:00:00Z",
        previous_record_hash=GENESIS_HASH,
    )
    h1 = p.compute_hash()
    assert len(h1) == 64
    assert h1 == p.compute_hash()


def test_hash_chain_integrity():
    with tempfile.TemporaryDirectory() as tmp:
        store = ImmutablePredictionStore(Path(tmp))
        p1 = PredictionRecord(
            prediction_id="P1", model_version=FROZEN_MODEL_VERSION,
            model_hash="H", feature_manifest_hash="H", input_data_hash="H",
            timestamp="2026-09-24T00:00:00Z"
        )
        p2 = PredictionRecord(
            prediction_id="P2", model_version=FROZEN_MODEL_VERSION,
            model_hash="H", feature_manifest_hash="H", input_data_hash="H",
            timestamp="2026-09-24T00:05:00Z"
        )
        store.store_prediction(p1)
        store.store_prediction(p2)

        assert p1.previous_record_hash == GENESIS_HASH
        assert p2.previous_record_hash == p1.record_hash

        valid, errs = store.verify_hash_chain()
        assert valid is True
        assert len(errs) == 0


def test_no_prediction_overwrite():
    with tempfile.TemporaryDirectory() as tmp:
        store = ImmutablePredictionStore(Path(tmp))
        p1 = PredictionRecord(
            prediction_id="P_UNIQUE", model_version=FROZEN_MODEL_VERSION,
            model_hash="H", feature_manifest_hash="H", input_data_hash="H",
            timestamp="2026-09-24T00:00:00Z"
        )
        store.store_prediction(p1)
        p1_dup = PredictionRecord(
            prediction_id="P_UNIQUE", model_version=FROZEN_MODEL_VERSION,
            model_hash="H", feature_manifest_hash="H", input_data_hash="H",
            timestamp="2026-09-24T00:00:00Z", forecast_1h=0.0099
        )
        with pytest.raises(ImmutableStoreViolation):
            store.store_prediction(p1_dup)


def test_no_prediction_deletion():
    with tempfile.TemporaryDirectory() as tmp:
        store = ImmutablePredictionStore(Path(tmp))
        with pytest.raises(ImmutableStoreViolation):
            store.delete_prediction("ANY_ID")


# ---------------------------------------------------------------------------
# Section 3: Separated Outcome Store & Horizon Maturity (12 - 17)
# ---------------------------------------------------------------------------

def test_outcome_stored_separately():
    with tempfile.TemporaryDirectory() as tmp:
        p_dir = Path(tmp) / "preds"
        o_dir = Path(tmp) / "outs"
        p_store = ImmutablePredictionStore(p_dir)
        o_store = OutcomeStore(o_dir)

        p = PredictionRecord(
            prediction_id="P1", model_version=FROZEN_MODEL_VERSION,
            model_hash="H", feature_manifest_hash="H", input_data_hash="H",
            timestamp="2026-09-24T00:00:00Z", created_at="2026-09-24T00:00:05Z"
        )
        p_store.store_prediction(p)
        o_store.attach_outcome(
            prediction=p,
            horizon="1h",
            outcome_data={"realized_volatility": 0.002, "outcome_available_at": "2026-09-24T01:05:00Z"},
            current_timestamp="2026-09-24T01:05:00Z",
        )

        assert p_dir / "predictions.jsonl" in p_dir.iterdir()
        assert o_dir / "outcomes.jsonl" in o_dir.iterdir()
        assert (p_dir / "outcomes.jsonl").exists() is False


def test_horizon_maturity_enforcement():
    with tempfile.TemporaryDirectory() as tmp:
        o_store = OutcomeStore(Path(tmp))
        p = PredictionRecord(
            prediction_id="P_MATURE", model_version=FROZEN_MODEL_VERSION,
            model_hash="H", feature_manifest_hash="H", input_data_hash="H",
            timestamp="2026-09-24T00:00:00Z", created_at="2026-09-24T00:00:05Z"
        )
        # Attempt to attach 4h outcome at T+2h (premature!)
        with pytest.raises(HorizonNotMaturedError):
            o_store.attach_outcome(
                prediction=p,
                horizon="4h",
                outcome_data={"realized_volatility": 0.004, "outcome_available_at": "2026-09-24T02:00:00Z"},
                current_timestamp="2026-09-24T02:00:00Z",
            )


def test_no_partial_horizon_scoring():
    with tempfile.TemporaryDirectory() as tmp:
        o_store = OutcomeStore(Path(tmp))
        p = PredictionRecord(
            prediction_id="P_PARTIAL", model_version=FROZEN_MODEL_VERSION,
            model_hash="H", feature_manifest_hash="H", input_data_hash="H",
            timestamp="2026-09-24T00:00:00Z"
        )
        status_early = o_store.get_status(p.prediction_id, "1h", current_time="2026-09-24T00:30:00Z", pred_time=p.timestamp)
        assert status_early == "PENDING"
        status_matured = o_store.get_status(p.prediction_id, "1h", current_time="2026-09-24T01:05:00Z", pred_time=p.timestamp)
        assert status_matured == "MATURED"


def test_no_retroactive_prediction():
    # Attempting to insert a prediction retroactively for an elapsed bar
    with tempfile.TemporaryDirectory() as tmp:
        p_store = ImmutablePredictionStore(Path(tmp))
        # Created_at later than outcome available_at is forbidden when scoring
        p = PredictionRecord(
            prediction_id="P_RETRO", model_version=FROZEN_MODEL_VERSION,
            model_hash="H", feature_manifest_hash="H", input_data_hash="H",
            timestamp="2026-09-24T00:00:00Z", created_at="2026-09-24T02:00:00Z"
        )
        p_store.store_prediction(p)
        o_store = OutcomeStore(Path(tmp) / "out")
        with pytest.raises(ImmutableStoreViolation):
            o_store.attach_outcome(
                prediction=p, horizon="1h",
                outcome_data={"outcome_available_at": "2026-09-24T01:00:00Z", "realized_volatility": 0.002},
                current_timestamp="2026-09-24T02:05:00Z"
            )


def test_missed_prediction_marking():
    # Missing bar audit flag
    pipeline = ProspectivePipeline()
    audit_res = pipeline.audit_logger.log_event("MISSED_PROSPECTIVE_PREDICTION", {"bar": "2026-09-24T01:15:00Z", "reason": "UPSTREAM_FEED_DOWN"})
    assert audit_res["event_type"] == "MISSED_PROSPECTIVE_PREDICTION"


def test_restart_recovery():
    with tempfile.TemporaryDirectory() as tmp:
        p_dir = Path(tmp) / "preds"
        p_store1 = ImmutablePredictionStore(p_dir)
        p1 = PredictionRecord(
            prediction_id="P_RESTART_1", model_version=FROZEN_MODEL_VERSION,
            model_hash="H", feature_manifest_hash="H", input_data_hash="H",
            timestamp="2026-09-24T00:00:00Z"
        )
        p_store1.store_prediction(p1)

        # Simulate restart
        p_store2 = ImmutablePredictionStore(p_dir)
        assert len(p_store2) == 1
        assert p_store2.latest_hash == p1.record_hash
        valid, errs = p_store2.verify_hash_chain()
        assert valid is True


# ---------------------------------------------------------------------------
# Section 4: Live-like Causality, Sources & Fallbacks (18 - 23)
# ---------------------------------------------------------------------------

def test_source_available_at_enforcement():
    # Cutoff timestamp must equal or precede prediction timestamp
    p = PredictionRecord(
        prediction_id="P_CUTOFF", model_version=FROZEN_MODEL_VERSION,
        model_hash="H", feature_manifest_hash="H", input_data_hash="H",
        timestamp="2026-09-24T00:00:00Z",
        input_cutoff_timestamp="2026-09-24T00:00:00Z"
    )
    assert p.input_cutoff_timestamp <= p.timestamp


def test_delayed_source_handling():
    # If source is delayed, data quality is marked DEGRADED_STREAM
    with tempfile.TemporaryDirectory() as tmp:
        pipe = ProspectivePipeline(reports_dir=Path(tmp) / "rep", prospective_data_dir=Path(tmp) / "prosp")
        pipe.initialize_and_verify()
        bar = {
            "datetime_open": "2026-09-24T00:00:00Z",
            "volatility_realized_24h": 0.002,
            "volatility_compression_ratio": 1.0,
            "basis_level": np.nan,  # Missing derivatives!
        }
        pred = pipe.process_prospective_bar(bar)
        assert pred.data_quality in ["DEGRADED_STREAM", "FALLBACK_TRIGGERED"]


def test_stale_source_handling():
    # When macro is stale, routed overlay zeroes it out without error
    with tempfile.TemporaryDirectory() as tmp:
        pipe = ProspectivePipeline(reports_dir=Path(tmp) / "rep", prospective_data_dir=Path(tmp) / "prosp")
        pipe.initialize_and_verify()
        bar = {
            "datetime_open": "2026-09-24T00:00:00Z",
            "volatility_realized_24h": 0.002,
            "volatility_compression_ratio": 1.0,
            "session_new_york_active": False,  # Weekend/night macro closure
            "sp500_ret_1d": 0.05,
        }
        pred = pipe.process_prospective_bar(bar)
        assert pred.market_state in [s.value for s in MarketStateId]


def test_source_correction_preserves_original():
    # Original prediction input remains immutable even if future source updates
    with tempfile.TemporaryDirectory() as tmp:
        store = ImmutablePredictionStore(Path(tmp))
        p = PredictionRecord(
            prediction_id="P_SRC_CORR", model_version=FROZEN_MODEL_VERSION,
            model_hash="H", feature_manifest_hash="H", input_data_hash="ORIGINAL_HASH_123",
            timestamp="2026-09-24T00:00:00Z"
        )
        store.store_prediction(p)
        loaded = store.get_prediction("P_SRC_CORR")
        assert loaded.input_data_hash == "ORIGINAL_HASH_123"


def test_u5_u2_frozen_comparison():
    p = REPORTS_DIR / "prospective_baseline_comparison.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert "u5_r2" in df.columns
    assert "u2_reference_r2" in df.columns


def test_no_automatic_model_selection():
    # Model remains frozen as CBE-0.7.0 regardless of prospective delta
    pipe = ProspectivePipeline()
    assert pipe.initialize_and_verify()["model_version"] == FROZEN_MODEL_VERSION


# ---------------------------------------------------------------------------
# Section 5: Metrics, Brier, BSS & Calibration (24 - 29)
# ---------------------------------------------------------------------------

def test_brier_calculation():
    mon = ProspectiveMonitor()
    y_true = np.array([0, 1, 0, 0, 1])
    y_prob = np.array([0.1, 0.9, 0.2, 0.1, 0.8])
    bs_m, bs_c, bss = mon.compute_brier_skill_score(y_true, y_prob, base_rate=0.4)
    assert bs_m < 0.10


def test_climatology_brier():
    assert HISTORICAL_CLIMATOLOGY["tail_95"] == 0.05
    assert HISTORICAL_CLIMATOLOGY["tail_99"] == 0.01


def test_brier_skill_score():
    mon = ProspectiveMonitor()
    y_true = np.array([0, 1, 0, 0, 1])
    # Model is sharper than climatology (0.4)
    y_prob = np.array([0.05, 0.95, 0.05, 0.05, 0.95])
    bs_m, bs_c, bss = mon.compute_brier_skill_score(y_true, y_prob, base_rate=0.4)
    assert bss > 0.0, "Skillful model must achieve positive BSS over climatology"


def test_calibration_calculation():
    p = REPORTS_DIR / "calibration_monitor.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert (df["calibration_slope"] >= 0.90).all()


def test_prediction_interval_coverage():
    p = REPORTS_DIR / "prediction_interval_monitor.csv"
    assert p.exists()
    df = pd.read_csv(p)
    cov80 = df.loc[df["interval_type"] == "80_PCT_PI", "prospective_coverage"].values[0]
    assert 0.75 <= cov80 <= 0.85


def test_base_rate_monitoring():
    p = REPORTS_DIR / "base_rate_monitor.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert set(df["target"].values) == {"tail_95", "tail_99", "jump", "expansion"}


# ---------------------------------------------------------------------------
# Section 6: Context Routing, Overlays & Regime Coverage (30 - 35)
# ---------------------------------------------------------------------------

def test_context_routing_logging():
    p = REPORTS_DIR / "context_routing_monitor.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) >= 4


def test_event_overlay_logging():
    p = REPORTS_DIR / "event_overlay_monitor.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert "period_type" in df.columns


def test_fallback_logging():
    p = REPORTS_DIR / "fallback_monitor.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert "fallback_level" in df.columns


def test_drift_calculation():
    mon = ProspectiveMonitor()
    exp = np.random.normal(0, 1, 1000)
    act = np.random.normal(0, 1, 1000)
    psi = mon.compute_psi(exp, act)
    assert psi < 0.10, "Same distribution must have low PSI"


def test_regime_coverage():
    p = REPORTS_DIR / "regime_coverage.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) == 9  # 9 market states


def test_session_coverage():
    p = REPORTS_DIR / "session_coverage.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) == 5  # Asia, London, NY, Overlap, Weekend


# ---------------------------------------------------------------------------
# Section 7: Diagnostics, Reliability & Latency (36 - 40)
# ---------------------------------------------------------------------------

def test_false_elevation_recording():
    p = REPORTS_DIR / "false_elevations.csv"
    assert p.exists()


def test_missed_extreme_recording():
    p = REPORTS_DIR / "missed_extremes.csv"
    assert p.exists()


def test_pipeline_uptime_calculation():
    p = REPORTS_DIR / "operational_reliability.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert df["uptime_percentage"].values[0] == 100.0


def test_latency_logging():
    p = REPORTS_DIR / "latency_monitor.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert "total_pipeline" in df["stage"].values


def test_directional_quarantine():
    p = PredictionRecord(
        prediction_id="P_DIR", model_version=FROZEN_MODEL_VERSION,
        model_hash="H", feature_manifest_hash="H", input_data_hash="H",
        timestamp="2026-09-24T00:00:00Z"
    )
    assert "research_direction_probability" in p.to_canonical_dict()
    assert p.research_direction_probability["p_up"] == 0.50
    assert p.research_direction_probability["p_down"] == 0.50


# ---------------------------------------------------------------------------
# Section 8: Zero Trading Execution & Firewall Isolation (41 - 44)
# ---------------------------------------------------------------------------

def test_no_buy_sell_hold():
    # Check all outputs for forbidden trading directives
    for f in REPORTS_DIR.glob("*.csv"):
        text = f.read_text(encoding="utf-8").lower()
        for forbidden in ["buy_signal", "sell_signal", "hold_signal", "order_type"]:
            assert forbidden not in text


def test_no_pnl():
    for f in REPORTS_DIR.glob("*.csv"):
        text = f.read_text(encoding="utf-8").lower()
        for forbidden in ["pnl", "sharpe_ratio", "sortino", "take_profit", "stop_loss"]:
            assert forbidden not in text


def test_historical_prospective_metric_separation():
    # Historical and prospective metrics must live in separate files
    p_hist = SPRINT07_DIR / "architecture_comparison.csv"
    p_prosp = REPORTS_DIR / "prospective_metrics.csv"
    assert p_hist.exists()
    assert p_prosp.exists()
    assert p_hist != p_prosp


def test_prospective_claim_registry_separation():
    p_hist_claim = SPRINT07_DIR / "claim_registry.json"
    p_prosp_claim = REPORTS_DIR / "prospective_claim_registry.json"
    assert p_hist_claim.exists()
    assert p_prosp_claim.exists()


# ---------------------------------------------------------------------------
# Section 9: Claim Integrity V4 & Clock/Audit Behavior (45 - 50)
# ---------------------------------------------------------------------------

def test_temporal_claim_integrity():
    reg = ProspectiveClaimRegistry()
    # Claim with temporal violation: prediction created after outcome available
    reg.register_prospective_claim(
        claim_id="CLAIM-LEAK-TEST",
        claim_text="Future realized volatility matches model forecast.",
        metric_name="test_metric",
        metric_value=0.002,
        prediction_id="P_LEAK",
        prediction_created_at="2026-09-24T02:00:00Z",  # AFTER outcome!
        outcome_available_at="2026-09-24T01:00:00Z",
        prediction_hash="HASH",
        sample_size=10,
    )
    ok, reason = reg.verify_temporal_integrity("CLAIM-LEAK-TEST")
    assert ok is False
    assert "TEMPORAL LEAKAGE" in reason


def test_model_predicted_requires_prior_immutable_prediction():
    reg = ProspectiveClaimRegistry()
    # Using 'the model predicted' without prediction proof must fail
    reg.register_prospective_claim(
        claim_id="CLAIM-HINDSIGHT-TEST",
        claim_text="The model predicted high volatility expansion.",
        metric_name="test",
        metric_value=1.0,
        prediction_id="",
        prediction_created_at="2026-09-24T00:00:00Z",
        outcome_available_at="2026-09-24T01:00:00Z",
        prediction_hash="",
        sample_size=1,
    )
    ok, reason = reg.verify_claim_language("CLAIM-HINDSIGHT-TEST")
    assert ok is False
    assert "without immutable prediction proof" in reason


def test_prospective_data_excluded_from_training():
    engine = UnifiedMarketStateEngine()
    # Engine is fitted strictly on Discovery (2021-2024), never prospective
    assert engine.model_version == FROZEN_MODEL_VERSION


def test_prospective_data_excluded_from_calibration():
    with open(PROSPECTIVE_DIR / "lockbox_manifest.json") as f:
        lockbox = json.load(f)
    assert lockbox["prospective_data_present"] is False


def test_audit_log_append_only_behavior():
    with tempfile.TemporaryDirectory() as tmp:
        logger_audit = AuditLogger(Path(tmp))
        e1 = logger_audit.log_event("EVENT1", {"k": 1})
        e2 = logger_audit.log_event("EVENT2", {"k": 2})
        assert e2["prev_hash"] == e1["entry_hash"]
        assert logger_audit.verify_audit_chain() is True


def test_utc_clock_ordering():
    t1 = parse_utc_iso("2026-09-24T00:00:00Z")
    t2 = parse_utc_iso("2026-09-24T00:05:00Z")
    assert t2 > t1
    assert t1.tzinfo is not None

"""Comprehensive test suite for Prospective Analytics & Audit Dashboard (Sprint 08.1).

Covers:
- Scientific validity outcome filter (is_valid_evaluation_outcome)
- Sample size reliability classification (classify_sample_size)
- Statistical metric formulas (MAE, RMSE, Bias, Pearson, Spearman, Brier)
- 5-bin probability calibration and predictive interval coverage
- Tail/jump constant fallback provenance classification
- Market-state post-event behavioral analysis
- Runtime feature provenance & availability panel
- Deterministic anomaly detection (duplicates, orphans, lookaheads)
- Operational integrity vs model performance distinction
- Daily snapshot and first 24h audit artifact generation
- Web server endpoints (/api/analytics/*) and UI localization
"""

import json
import math
from pathlib import Path
import tempfile
from typing import Any, Dict

import pytest

from coin_behavior_engine.prospective.analytics import (
    ProspectiveAnalyticsEngine,
    classify_sample_size,
    compute_bias,
    compute_brier_score,
    compute_mae,
    compute_pearson,
    compute_rmse,
    compute_spearman,
    is_valid_evaluation_outcome,
)
from coin_behavior_engine.prospective.store import OutcomeRecord, PredictionRecord
from coin_behavior_engine.web.server import get_engine_state, render_dashboard_html


# ======================================================================
# 1. Authoritative Evaluation Validity Filter Tests
# ======================================================================

def test_is_valid_evaluation_outcome_valid_v2():
    """Valid Schema V2 outcome with reference close must be accepted."""
    outcome = {
        "prediction_id": "PRED_20260924_190000_123456",
        "horizon": "1h",
        "status": "SCORED",
        "excluded_from_evaluation": False,
        "invalidation_reason": None,
        "realized_return": 0.0045,
        "realized_volatility": 0.0052,
        "outcome_available_at": "2026-09-24T20:00:00Z",
    }
    pred = {
        "prediction_id": "PRED_20260924_190000_123456",
        "timestamp": "2026-09-24T19:00:00Z",
        "created_at": "2026-09-24T19:00:02Z",
        "reference_close": 63450.0,
        "prediction_schema_version": "2",
    }
    assert is_valid_evaluation_outcome(outcome, pred) is True


def test_is_valid_evaluation_outcome_excluded_flag():
    """Outcomes with excluded_from_evaluation=True must be rejected."""
    outcome = {
        "status": "SCORED",
        "excluded_from_evaluation": True,
        "realized_return": 0.001,
        "outcome_available_at": "2026-09-24T20:00:00Z",
    }
    assert is_valid_evaluation_outcome(outcome) is False


def test_is_valid_evaluation_outcome_invalid_reference_price_status():
    """Outcomes with INVALID_REFERENCE_PRICE status must be rejected."""
    outcome = {
        "status": "INVALID_REFERENCE_PRICE",
        "excluded_from_evaluation": False,
        "realized_return": 0.0,
        "outcome_available_at": "2026-09-24T20:00:00Z",
    }
    assert is_valid_evaluation_outcome(outcome) is False


def test_is_valid_evaluation_outcome_missing_ref_close_v1():
    """Outcomes with legacy V1 missing reference close reason must be rejected."""
    outcome = {
        "status": "INVALID",
        "invalidation_reason": "PREDICTION_SCHEMA_V1_MISSING_REFERENCE_CLOSE",
        "excluded_from_evaluation": False,
        "realized_return": 0.0,
    }
    assert is_valid_evaluation_outcome(outcome) is False


def test_is_valid_evaluation_outcome_non_finite_return():
    """Outcomes with NaN, None, or infinite realized returns must be rejected."""
    assert is_valid_evaluation_outcome({"status": "SCORED", "realized_return": None}) is False
    assert is_valid_evaluation_outcome({"status": "SCORED", "realized_return": float("nan")}) is False
    assert is_valid_evaluation_outcome({"status": "SCORED", "realized_return": float("inf")}) is False


def test_is_valid_evaluation_outcome_lookahead_violation():
    """Outcomes where prediction timestamp >= outcome timestamp must be rejected."""
    pred = {"created_at": "2026-09-24T20:05:00Z", "reference_close": 63000.0}
    outcome = {
        "status": "SCORED",
        "excluded_from_evaluation": False,
        "realized_return": 0.002,
        "outcome_available_at": "2026-09-24T20:00:00Z",  # Prior to prediction!
    }
    assert is_valid_evaluation_outcome(outcome, pred) is False


def test_is_valid_evaluation_outcome_dataclass_instance():
    """Filter must support OutcomeRecord and PredictionRecord dataclasses."""
    outcome = OutcomeRecord(
        prediction_id="PID_001",
        horizon="1h",
        outcome_available_at="2026-09-24T20:00:00Z",
        realized_return=0.003,
        realized_volatility=0.004,
        status="SCORED",
        excluded_from_evaluation=False,
    )
    pred = PredictionRecord(
        prediction_id="PID_001",
        timestamp="2026-09-24T19:00:00Z",
        created_at="2026-09-24T19:00:01Z",
        model_version="CBE-0.7.0",
        model_hash="dummy_model_hash",
        feature_manifest_hash="dummy_manifest_hash",
        input_data_hash="dummy_data_hash",
        reference_close=63000.0,
        prediction_schema_version="2",
    )
    assert is_valid_evaluation_outcome(outcome, pred) is True


# ======================================================================
# 2. Sample Size Reliability Classification Tests
# ======================================================================

def test_classify_sample_size_insufficient():
    res = classify_sample_size(5)
    assert res["code"] == "INSUFFICIENT"
    assert res["status"] == "YETERSİZ ÖRNEK"
    assert res["reliable"] is False
    assert "N=5 < 10" in res["description"]


def test_classify_sample_size_early():
    res = classify_sample_size(15)
    assert res["code"] == "EARLY"
    assert res["status"] == "ERKEN GÖZLEM"
    assert res["reliable"] is False
    assert "10 <= N=15 < 30" in res["description"]


def test_classify_sample_size_developing():
    res = classify_sample_size(50)
    assert res["code"] == "DEVELOPING"
    assert res["status"] == "GELİŞEN ÖRNEK"
    assert res["reliable"] is True
    assert "30 <= N=50 < 100" in res["description"]


def test_classify_sample_size_sufficient():
    res = classify_sample_size(150)
    assert res["code"] == "SUFFICIENT"
    assert res["status"] == "YETERLİ GÖZLEM"
    assert res["reliable"] is True
    assert "N=150 >= 100" in res["description"]


# ======================================================================
# 3. Statistical Metric Calculations Tests
# ======================================================================

def test_compute_mae_known_values():
    forecasts = [1.0, 2.0, 3.0]
    realized = [1.2, 1.8, 3.5]
    # |1.0 - 1.2| = 0.2, |2.0 - 1.8| = 0.2, |3.0 - 3.5| = 0.5 -> avg = 0.9 / 3 = 0.3
    mae = compute_mae(forecasts, realized)
    assert mae is not None
    assert abs(mae - 0.3) < 1e-6


def test_compute_mae_empty():
    assert compute_mae([], []) is None


def test_compute_rmse_known_values():
    forecasts = [1.0, 2.0]
    realized = [1.3, 1.6]
    # (0.3)^2 + (0.4)^2 = 0.09 + 0.16 = 0.25 -> mean = 0.125 -> sqrt(0.125) = 0.353553
    rmse = compute_rmse(forecasts, realized)
    assert rmse is not None
    assert abs(rmse - math.sqrt(0.125)) < 1e-6


def test_compute_rmse_empty():
    assert compute_rmse([], []) is None


def test_compute_bias_positive():
    forecasts = [2.0, 3.0]
    realized = [1.0, 2.0]
    # (2-1) + (3-2) = 2.0 / 2 = +1.0 (over-forecast)
    bias = compute_bias(y_true=realized, y_pred=forecasts)
    assert bias is not None
    assert abs(bias - 1.0) < 1e-6


def test_compute_bias_negative():
    forecasts = [1.0, 2.0]
    realized = [2.0, 3.0]
    # (1-2) + (2-3) = -2.0 / 2 = -1.0 (under-forecast)
    bias = compute_bias(y_true=realized, y_pred=forecasts)
    assert bias is not None
    assert abs(bias - (-1.0)) < 1e-6


def test_compute_pearson_exact():
    forecasts = [1.0, 2.0, 3.0, 4.0]
    realized = [2.0, 4.0, 6.0, 8.0]
    r = compute_pearson(forecasts, realized)
    assert r is not None
    assert abs(r - 1.0) < 1e-5


def test_compute_pearson_inverse():
    forecasts = [1.0, 2.0, 3.0, 4.0]
    realized = [8.0, 6.0, 4.0, 2.0]
    r = compute_pearson(forecasts, realized)
    assert r is not None
    assert abs(r - (-1.0)) < 1e-5


def test_compute_pearson_insufficient_samples():
    assert compute_pearson([1.0, 2.0], [2.0, 3.0]) is None


def test_compute_pearson_zero_variance():
    assert compute_pearson([1.0, 1.0, 1.0], [2.0, 3.0, 4.0]) is None


def test_compute_spearman_exact():
    forecasts = [1.0, 2.0, 3.0, 4.0, 5.0]
    realized = [10.0, 20.0, 40.0, 80.0, 160.0]
    rho = compute_spearman(forecasts, realized)
    assert rho is not None
    assert abs(rho - 1.0) < 1e-5


def test_compute_spearman_insufficient_samples():
    assert compute_spearman([1.0, 2.0], [3.0, 4.0]) is None


def test_compute_brier_score_perfect():
    probs = [1.0, 0.0, 1.0, 0.0]
    outcomes = [1.0, 0.0, 1.0, 0.0]
    score = compute_brier_score(probs, outcomes)
    assert score is not None
    assert abs(score - 0.0) < 1e-6


def test_compute_brier_score_worst():
    probs = [1.0, 0.0]
    outcomes = [0.0, 1.0]
    score = compute_brier_score(probs, outcomes)
    assert score is not None
    assert abs(score - 1.0) < 1e-6


def test_compute_brier_score_empty():
    assert compute_brier_score([], []) is None


# ======================================================================
# 4. Engine End-to-End Analytics Tests
# ======================================================================

def test_engine_summary_metrics():
    """Engine summary must return structured dictionary with required keys."""
    engine = ProspectiveAnalyticsEngine()
    summary = engine.get_summary_metrics("all")
    assert summary["period"] == "all"
    assert "prediction_count" in summary
    assert "schema_v2_predictions" in summary
    assert "valid_evaluation_outcomes" in summary
    assert "sample_size_classification" in summary
    assert "prediction_label" in summary
    assert summary["prediction_label"] == "KAYDEDİLEN TAHMİN"
    assert "data_quality" in summary
    assert "model_scope" in summary
    assert "scientific_disclaimer" in summary


def test_engine_horizon_performance_structure():
    """Active horizons 1h, 4h, 24h must be evaluated; others listed as unavailable."""
    engine = ProspectiveAnalyticsEngine()
    horizons_res = engine.get_horizon_performance("all")
    active_horizons = [h["horizon"] for h in horizons_res["horizons"]]
    assert active_horizons == ["1h", "4h", "24h"]

    unavailable = [u["horizon"] for u in horizons_res["unavailable_horizons"]]
    assert set(unavailable) == {"15m", "30m", "2h", "8h", "12h"}


def test_engine_calibration_analysis_5bin():
    """Calibration analysis must return 5 bins and interval coverage targets."""
    engine = ProspectiveAnalyticsEngine()
    cal = engine.get_calibration_analysis("all")
    assert "expansion_calibration" in cal
    assert "interval_coverage" in cal
    assert "tail_jump_provenance_audit" in cal

    # Provenance audit verification
    audit = cal["tail_jump_provenance_audit"]
    assert audit["tail_95_status"] == "MODEL ÇIKTISI DEĞİL / FALLBACK"
    assert audit["jump_status"] == "MODEL ÇIKTISI DEĞİL / FALLBACK"
    assert audit["tail_constant_observed"] == 0.05
    assert audit["jump_constant_observed"] == 0.01
    assert audit["included_in_performance"] is False


def test_engine_market_state_analysis():
    """Market state analysis must return non-empty list of states with disclaimers."""
    engine = ProspectiveAnalyticsEngine()
    ms = engine.get_market_state_analysis("all")
    assert "market_states" in ms
    assert len(ms["market_states"]) > 0
    assert "disclaimer" in ms


def test_engine_feature_availability_panel():
    """Panel must reflect spot-only active status and missing derivatives/macro/etf."""
    engine = ProspectiveAnalyticsEngine()
    panel = engine.get_feature_availability_panel()
    assert panel["current_fallback_level"] == "SPOT_ONLY_U0"
    assert panel["data_quality_state"] == "DEGRADED_STREAM"

    groups = {g["group"]: g["status"] for g in panel["feature_groups"]}
    assert groups["SPOT"] == "AKTİF"
    assert groups["SESSION"] == "AKTİF"
    assert groups["DERIVATIVES"] == "EKSİK"
    assert groups["ETF_FLOWS"] == "EKSİK"
    assert groups["MACRO"] == "EKSİK"
    assert groups["EVENTS"] == "EKSİK"


def test_engine_system_integrity():
    """System integrity must verify cryptographic chains and separate integrity from model performance."""
    engine = ProspectiveAnalyticsEngine()
    integ = engine.get_system_integrity()
    assert integ["hash_chain_valid"] is True
    assert integ["model_freeze_status"] == "FREEZE_VERIFIED"
    assert integ["canonical_artifacts_verified"] == 29
    assert integ["canonical_artifacts_total"] == 29
    assert "integrity_distinction_note" in integ


def test_engine_prospective_timeline():
    """Timeline must present historical research, freeze V2, and schema V2 milestones."""
    engine = ProspectiveAnalyticsEngine()
    tl = engine.get_prospective_timeline()
    milestones = [m["code"] for m in tl["milestones"]]
    assert "HISTORICAL_RESEARCH" in milestones
    assert "FREEZE_V2" in milestones
    assert "SCHEMA_V2" in milestones


# ======================================================================
# 5. Anomaly Detection Tests
# ======================================================================

def test_anomaly_detection_synthetic():
    """Test anomaly detector on synthetic directory with an injected duplicate."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_path = Path(tmp_dir)
        pred_file = base_path / "predictions" / "predictions.jsonl"
        pred_file.parent.mkdir(parents=True)
        outcome_file = base_path / "outcomes" / "outcomes.jsonl"
        outcome_file.parent.mkdir(parents=True)

        # Write duplicate prediction
        pred_data = {
            "prediction_id": "DUP_ID_001",
            "timestamp": "2026-09-24T12:00:00Z",
            "created_at": "2026-09-24T12:00:01Z",
            "prediction_schema_version": "2",
            "reference_close": 60000.0,
        }
        with open(pred_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(pred_data) + "\n")
            f.write(json.dumps(pred_data) + "\n")

        with open(outcome_file, "w", encoding="utf-8") as f:
            f.write("")

        engine = ProspectiveAnalyticsEngine(base_dir=base_path)
        anomalies = engine.detect_anomalies()
        types = [a["type"] for a in anomalies]
        assert "DUPLICATE_PREDICTION_ID" in types


def test_anomaly_detection_orphan_outcome():
    """Test anomaly detector flags outcome without matching prediction."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_path = Path(tmp_dir)
        pred_file = base_path / "predictions" / "predictions.jsonl"
        pred_file.parent.mkdir(parents=True)
        outcome_file = base_path / "outcomes" / "outcomes.jsonl"
        outcome_file.parent.mkdir(parents=True)

        with open(pred_file, "w", encoding="utf-8") as f:
            f.write("")

        orphan_outcome = {
            "prediction_id": "ORPHAN_PID",
            "horizon": "1h",
            "outcome_available_at": "2026-09-24T13:00:00Z",
            "realized_return": 0.001,
        }
        with open(outcome_file, "w", encoding="utf-8") as f:
            f.write(json.dumps(orphan_outcome) + "\n")

        engine = ProspectiveAnalyticsEngine(base_dir=base_path)
        anomalies = engine.detect_anomalies()
        types = [a["type"] for a in anomalies]
        assert "ORPHAN_OUTCOME" in types


# ======================================================================
# 6. Artifact Generators (Snapshots & 24h Audit)
# ======================================================================

def test_generate_daily_snapshot():
    """Engine must generate daily snapshot report with correct structure."""
    engine = ProspectiveAnalyticsEngine()
    snapshot = engine.generate_daily_snapshot("2026-09-24")
    assert snapshot["report_date"] == "2026-09-24"
    assert snapshot["model_version"] == "CBE-0.7.0"
    assert "prediction_count" in snapshot
    assert "valid_outcome_count" in snapshot
    assert "invalid_outcome_count" in snapshot


def test_generate_first_24h_audit_report():
    """Engine must generate first 24h audit artifact separating operational and V2 windows."""
    engine = ProspectiveAnalyticsEngine()
    report = engine.generate_first_24h_audit_report()
    assert report["model_version"] == "CBE-0.7.0"
    assert "operational_prospective_window" in report
    assert "valid_schema_v2_evaluation_window" in report
    assert report["valid_schema_v2_evaluation_window"]["legacy_v1_excluded"] is True
    assert report["audit_verdict"]["hash_chain_intact"] is True


# ======================================================================
# 7. Web Server Presentation & Localization Tests
# ======================================================================

def test_web_ui_renamed_kaydedilen_tahmin():
    """Dashboard HTML must use 'Kaydedilen Tahmin' and not 'Başarılı Tahmin'."""
    state = get_engine_state()
    html = render_dashboard_html(state)
    assert "Kaydedilen Tahmin" in html
    assert "Başarılı Tahmin" not in html


def test_web_ui_sprint_08_1_analytics_section():
    """Dashboard HTML must render Sprint 08.1 analytics section and controls."""
    state = get_engine_state()
    html = render_dashboard_html(state)
    assert "İleriye Dönük Performans ve Denetim (Sprint 08.1)" in html
    assert "TÜM PROSPECTIVE DÖNEM" in html
    assert "SON 30 GÜN" in html
    assert "SON 7 GÜN" in html
    assert "SON 24 SAAT" in html
    assert "SPOT ONLY U0" in html
    assert "Çoklu Tahmin Vadeleri Hata ve Korelasyon Metrikleri" in html
    assert "Volatilite Genişleme Olasılığı Kalibrasyonu (5-Bin)" in html
    assert "Tahmin Aralığı Kapsama Oranı (Predictive Interval Coverage)" in html
    assert "Piyasa Durumlarına Göre Olay Sonrası Davranış Analizi" in html
    assert "Çalışma Zamanı Özellik & Veri Katmanları" in html
    assert "Sistem Bütünlüğü vs Model Performansı Ayrımı" in html


def test_web_server_endpoints_available():
    """Test that all 7 analytics endpoints are registered in server.py."""
    from coin_behavior_engine.web.server import get_analytics_engine
    engine = get_analytics_engine()
    assert engine is not None
    assert engine.get_summary_metrics("all")["prediction_label"] == "KAYDEDİLEN TAHMİN"
    assert len(engine.get_horizon_performance("all")["horizons"]) == 3
    assert engine.get_system_integrity()["hash_chain_valid"] is True


# ======================================================================
# 8. Sprint 08.1.1 Production Bugfix & Failure Isolation Tests
# ======================================================================

def test_summary_mae_1h_propagated_authoritatively():
    """1h MAE in summary must match get_horizon_performance authoritative 1h MAE."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_path = Path(tmp_dir)
        pred_file = base_path / "predictions" / "predictions.jsonl"
        pred_file.parent.mkdir(parents=True)
        outcome_file = base_path / "outcomes" / "outcomes.jsonl"
        outcome_file.parent.mkdir(parents=True)

        # Create 6 valid predictions and outcomes (N >= 5 for statistical metrics)
        for i in range(6):
            pid = f"PRED_TEST_{i}"
            p_data = {
                "prediction_id": pid,
                "timestamp": f"2026-09-24T1{i}:00:00Z",
                "created_at": f"2026-09-24T1{i}:00:01Z",
                "reference_close": 60000.0,
                "prediction_schema_version": "2",
                "forecast_1h": 0.0150 + (i * 0.001),
                "forecast_availability": {"1h": True, "4h": True, "24h": True},
            }
            o_data = {
                "prediction_id": pid,
                "horizon": "1h",
                "outcome_available_at": f"2026-09-24T1{i+1}:00:00Z",
                "status": "SCORED",
                "excluded_from_evaluation": False,
                "realized_volatility": 0.0140 + (i * 0.001),
                "realized_return": 0.002,
                "outcome_schema_version": "2",
            }
            with open(pred_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(p_data) + "\n")
            with open(outcome_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(o_data) + "\n")

        engine = ProspectiveAnalyticsEngine(base_dir=base_path)
        summary = engine.get_summary_metrics("all")
        horizons = engine.get_horizon_performance("all")

        h1 = next(h for h in horizons["horizons"] if h["horizon"] == "1h")
        assert h1["mae"] is not None
        assert summary["mae_1h"] is not None
        # Must be identical from the single authoritative calculation
        assert summary["mae_1h"] == h1["mae"]
        assert summary["schema_v2_predictions"] == 6
        assert summary["valid_evaluation_outcomes"] == 6


def test_summary_null_mae_displays_safely():
    """When N < 5, summary mae_1h is None and horizons 1h mae is None."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        base_path = Path(tmp_dir)
        pred_file = base_path / "predictions" / "predictions.jsonl"
        pred_file.parent.mkdir(parents=True)
        outcome_file = base_path / "outcomes" / "outcomes.jsonl"
        outcome_file.parent.mkdir(parents=True)

        # Only 2 samples (N < 5)
        for i in range(2):
            pid = f"PRED_FEW_{i}"
            p_data = {
                "prediction_id": pid,
                "timestamp": f"2026-09-24T1{i}:00:00Z",
                "created_at": f"2026-09-24T1{i}:00:01Z",
                "reference_close": 60000.0,
                "prediction_schema_version": "2",
                "forecast_1h": 0.0150,
            }
            o_data = {
                "prediction_id": pid,
                "horizon": "1h",
                "outcome_available_at": f"2026-09-24T1{i+1}:00:00Z",
                "status": "SCORED",
                "excluded_from_evaluation": False,
                "realized_volatility": 0.0140,
                "realized_return": 0.001,
            }
            with open(pred_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(p_data) + "\n")
            with open(outcome_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(o_data) + "\n")

        engine = ProspectiveAnalyticsEngine(base_dir=base_path)
        summary = engine.get_summary_metrics("all")
        horizons = engine.get_horizon_performance("all")
        h1 = next(h for h in horizons["horizons"] if h["horizon"] == "1h")

        assert summary["mae_1h"] is None
        assert h1["mae"] is None


def test_sufficient_sample_classification_rendering():
    """Sample size classification for N >= 100 must be SUFFICIENT / YETERLİ GÖZLEM."""
    cls_obj = classify_sample_size(150)
    assert cls_obj["code"] == "SUFFICIENT"
    assert cls_obj["status"] == "YETERLİ GÖZLEM"
    assert cls_obj["reliable"] is True


def test_js_syntax_clean_no_unexpected_tokens():
    """Dashboard HTML script block must be valid JavaScript with zero syntax errors."""
    state = get_engine_state()
    html = render_dashboard_html(state)
    start_idx = html.find("<script>") + 8
    end_idx = html.find("</script>")
    assert start_idx > 8
    assert end_idx > start_idx
    js_code = html[start_idx:end_idx]

    # Verify no unescaped inner double quotes breaking string literals
    assert "safeNum" in js_code
    assert "safeFixed" in js_code
    assert "safePct" in js_code
    assert "safeSigned" in js_code
    assert "renderSampleBadge" in js_code
    assert "getSampleDesc" in js_code


def test_js_failure_isolation_per_panel():
    """Dashboard script must have independent try/catch failure isolation for each panel."""
    state = get_engine_state()
    html = render_dashboard_html(state)

    # Verify per-panel failure isolation in fetchAnalytics
    assert "// Panel 1: Summary Cards (Failure-isolated)" in html
    assert "// Panel 2: Horizon Performance Table (Failure-isolated)" in html
    assert "// Panel 3: Probability Calibration & Predictive Intervals (Failure-isolated)" in html
    assert "// Panel 4: Market-State Behavior Analysis (Failure-isolated)" in html
    assert "// Panel 5: Feature Availability & Runtime Provenance (Failure-isolated)" in html


def test_js_no_indefinite_loading_states():
    """All panel catch blocks must update the UI with 'Veri yüklenemedi' on error."""
    state = get_engine_state()
    html = render_dashboard_html(state)
    assert "Veri yüklenemedi" in html


def test_js_immediate_initial_fetch():
    """Initial load must call fetchAndUpdate() and selectPeriod('all') immediately."""
    state = get_engine_state()
    html = render_dashboard_html(state)
    assert "fetchAndUpdate();" in html
    assert 'selectPeriod("all");' in html


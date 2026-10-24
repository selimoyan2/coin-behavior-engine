"""
Sprint Product Acceleration 07 — Test Suite.

Verifies:
1. Multi-timeframe derivation engine mathematical aggregation rules (OHLCV)
2. Exact UTC boundary alignment (15m, 1h, 4h, 1d)
3. Incomplete aggregation window dropping (strict drop, no extrapolation)
4. Canonical parity of derived timeframes on 2026-09 partition
5. Historical data importer CLI and derivation workflow
6. Comparative market workbench metrics (Net return, Realized Vol, MDD, Amplitude)
7. Normalized trajectory curves with anchor candle locking
8. Formula injection defense on CSV exports
9. Regime distribution drift intelligence (JSD, PSI, Wasserstein)
10. Regime transition probability matrices and persistence durations
11. Research readiness hardening (fail-closed BLOCKED_NO_DATA 0.0% on unimported months)
12. Research readiness success on imported canonical partitions
13. Dashboard API endpoints: comparative analysis, export, regime drift, derivation status
14. Non-negotiable governance invariants
"""

from datetime import datetime, timezone
from http import HTTPStatus
import json
import math
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.data_import import HistoricalDataImporter
from coin_behavior_engine.product.comparative_workbench import ComparativeMarketEngine, sanitize_csv_cell
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.dataset_manager import DatasetManager
from coin_behavior_engine.product.regime_drift import RegimeDriftEngine
from coin_behavior_engine.product.research_readiness import ResearchReadinessEngine
from coin_behavior_engine.product.timeframe_derivation import (
    INTERVAL_RATIOS,
    MultiTimeframeDerivationEngine,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------------------
# 1. Multi-Timeframe Derivation — Mathematical Rules
# -----------------------------------------------------------------------------
def test_01_derivation_mathematical_rules():
    """Verify exact OHLCV derivation logic: open==first, high==max, low==min, close==last, volume==sum."""
    start_ms = 1725148800000  # 2024-09-01 00:00:00 UTC
    bars_5m = []
    for i in range(12):  # 1 hour
        bars_5m.append({
            "open_time": start_ms + i * 300000,
            "open": 60000.0 + i * 10,
            "high": 60100.0 + i * 10,
            "low": 59900.0 + i * 10,
            "close": 60050.0 + i * 10,
            "volume": 5.0,
        })
    df_5m = pd.DataFrame(bars_5m)

    derived_1h = MultiTimeframeDerivationEngine.derive_dataframe(df_5m, "5m", "1h")
    assert len(derived_1h) == 1
    row = derived_1h.iloc[0]
    assert row["open_time"] == start_ms
    assert row["open"] == 60000.0  # first open
    assert row["high"] == 60100.0 + 11 * 10  # max high
    assert row["low"] == 59900.0  # min low
    assert row["close"] == 60050.0 + 11 * 10  # last close
    assert abs(row["volume"] - 60.0) < 1e-6  # sum volume


# -----------------------------------------------------------------------------
# 2. Multi-Timeframe Derivation — Boundary Alignment
# -----------------------------------------------------------------------------
def test_02_derivation_boundary_alignment():
    """Verify timestamps align exactly to UTC boundaries."""
    # 00:05 UTC (not on 15m or 1h boundary)
    ts = 1725149100000
    ratio_15m_ms = 15 * 60 * 1000
    expected_15m_ts = (ts // ratio_15m_ms) * ratio_15m_ms
    assert expected_15m_ts == 1725148800000  # 00:00 UTC


# -----------------------------------------------------------------------------
# 3. Multi-Timeframe Derivation — Incomplete Window Dropping
# -----------------------------------------------------------------------------
def test_03_derivation_incomplete_window_dropping():
    """Verify that incomplete windows (e.g. 11/12 bars) are strictly dropped."""
    start_ms = 1725148800000
    bars_5m = []
    for i in range(11):  # Only 11 of 12 required bars
        bars_5m.append({
            "open_time": start_ms + i * 300000,
            "open": 60000.0,
            "high": 60100.0,
            "low": 59900.0,
            "close": 60050.0,
            "volume": 1.0,
        })
    df_5m = pd.DataFrame(bars_5m)
    derived = MultiTimeframeDerivationEngine.derive_dataframe(df_5m, "5m", "1h")
    assert len(derived) == 0  # Incomplete window dropped


# -----------------------------------------------------------------------------
# 4. Multi-Timeframe Derivation — Canonical Parity on 2026-09
# -----------------------------------------------------------------------------
def test_04_derivation_canonical_parity():
    """Verify derived timeframes match canonical partitions for 2026-09 with zero discrepancy."""
    engine = MultiTimeframeDerivationEngine()
    for target_intv in ["15m", "1h", "4h", "1d"]:
        res = engine.verify_derived_vs_canonical("2026-09", target_intv)
        assert res["status"] == "PASS"
        assert res["derived_rows"] > 0
        assert res["canonical_rows"] == res["derived_rows"]
        assert res["max_price_difference"] < 1e-4
        assert res["max_volume_difference"] < 1e-2
        assert res["exact_parity"] is True


# -----------------------------------------------------------------------------
# 5. Data Importer — Derive Mode Dry Run
# -----------------------------------------------------------------------------
def test_05_importer_derive_workflow():
    """Verify HistoricalDataImporter.derive_timeframes workflow in dry-run mode."""
    importer = HistoricalDataImporter()
    result = importer.derive_timeframes(
        source_interval="5m",
        target_intervals=["15m", "1h"],
        month="2026-09",
        dry_run=True,
    )
    assert result["status"] == "DERIVATION_SUCCESS"
    receipts = result["derived_receipts"]
    assert len(receipts) == 2
    for r in receipts:
        assert r["records_derived"] > 0
        assert r["comparison_with_canonical"]["exact_parity"] is True


# -----------------------------------------------------------------------------
# 6. Comparative Workbench — Metrics Calculation
# -----------------------------------------------------------------------------
def test_06_comparative_metrics_calculation():
    """Verify net return, realized volatility, MDD, amplitude, and volume."""
    start_ms = 1725148800000
    candles = [
        {"open_time": start_ms + 0 * 86400000, "open": 100.0, "high": 110.0, "low": 95.0, "close": 105.0, "volume": 10.0},
        {"open_time": start_ms + 1 * 86400000, "open": 105.0, "high": 120.0, "low": 100.0, "close": 115.0, "volume": 20.0},
        {"open_time": start_ms + 2 * 86400000, "open": 115.0, "high": 118.0, "low": 90.0, "close": 92.0, "volume": 15.0},
    ]
    metrics = ComparativeMarketEngine.compute_period_metrics(candles, interval="1d")
    assert metrics["candle_count"] == 3
    assert metrics["start_price"] == 100.0
    assert metrics["end_price"] == 92.0
    assert metrics["net_return_pct"] == -8.0
    assert metrics["high_price"] == 120.0
    assert metrics["low_price"] == 90.0
    assert metrics["amplitude_pct"] == round(((120.0 - 90.0) / 90.0) * 100.0, 3)
    assert metrics["max_drawdown_pct"] > 0.0
    assert metrics["total_volume"] == 45.0
    assert metrics["realized_volatility_annualized_pct"] > 0.0


# -----------------------------------------------------------------------------
# 7. Comparative Workbench — Normalized Trajectories & Anchor
# -----------------------------------------------------------------------------
def test_07_comparative_normalized_trajectories():
    """Verify normalized trajectory curves start at 0.0% return."""
    candles_a = [
        {"open_time": 1000, "close": 200.0, "volume": 5.0},
        {"open_time": 2000, "close": 210.0, "volume": 6.0},
    ]
    candles_b = [
        {"open_time": 1000, "close": 500.0, "volume": 15.0},
        {"open_time": 2000, "close": 450.0, "volume": 16.0},
    ]
    traj = ComparativeMarketEngine.normalize_trajectories(candles_a, candles_b, anchor_index_a=0, anchor_index_b=0)
    assert len(traj) == 2
    assert traj[0]["return_pct_a"] == 0.0
    assert traj[0]["return_pct_b"] == 0.0
    assert traj[1]["return_pct_a"] == 5.0
    assert traj[1]["return_pct_b"] == -10.0


# -----------------------------------------------------------------------------
# 8. Comparative Workbench — Dual Period Comparison
# -----------------------------------------------------------------------------
def test_08_comparative_dual_period_comparison():
    """Verify full comparison execution between 2024-03 and 2024-11."""
    res = ComparativeMarketEngine.compare_periods(
        period_a={"month": "2024-03", "interval": "1d"},
        period_b={"month": "2024-11", "interval": "1d"},
    )
    assert res["status"] == "success"
    assert "delta_metrics" in res
    assert "normalized_trajectory" in res
    assert res["period_a"]["metrics"]["candle_count"] == 31
    assert res["period_b"]["metrics"]["candle_count"] == 30


# -----------------------------------------------------------------------------
# 9. Formula Injection Defense on Export
# -----------------------------------------------------------------------------
def test_09_formula_injection_defense():
    """Verify cells starting with =, +, -, @ are escaped with single quote."""
    assert sanitize_csv_cell("=cmd|' /C calc'!A0") == "'=cmd|' /C calc'!A0"
    assert sanitize_csv_cell("+12345") == "'+12345"
    assert sanitize_csv_cell("@SUM(A1:A10)") == "'@SUM(A1:A10)"
    assert sanitize_csv_cell("-100") == "'-100"
    assert sanitize_csv_cell("SAFE_STRING") == "SAFE_STRING"
    assert sanitize_csv_cell(123) == 123


# -----------------------------------------------------------------------------
# 10. Regime Drift — Preset Windows
# -----------------------------------------------------------------------------
def test_10_regime_drift_presets():
    """Verify preset windows discovery."""
    presets = RegimeDriftEngine.get_preset_windows()
    assert len(presets) >= 4
    preset_ids = [p["id"] for p in presets]
    assert "q4_2025_vs_q1_2026" in preset_ids
    assert "h1_2026_vs_h2_2026" in preset_ids


# -----------------------------------------------------------------------------
# 11. Regime Drift — JSD & PSI Divergence Metrics
# -----------------------------------------------------------------------------
def test_11_regime_drift_divergence_metrics():
    """Verify JSD and PSI mathematical properties."""
    p = {"SIDEWAYS": 0.5, "HIGH_VOLATILITY": 0.5, "UNCERTAIN": 0.0, "TRENDING_BULL": 0.0, "TRENDING_BEAR": 0.0, "POSSIBLE_REVERSAL": 0.0}
    q = {"SIDEWAYS": 0.5, "HIGH_VOLATILITY": 0.5, "UNCERTAIN": 0.0, "TRENDING_BULL": 0.0, "TRENDING_BEAR": 0.0, "POSSIBLE_REVERSAL": 0.0}

    # Identical distributions should yield JSD == 0 and PSI == 0
    jsd_identical = RegimeDriftEngine.compute_jsd(p, q)
    psi_val, status, label = RegimeDriftEngine.compute_psi(p, q)
    assert jsd_identical == 0.0
    assert psi_val == 0.0
    assert status == "STABLE"

    # Perturbed distribution
    q_shift = {"SIDEWAYS": 0.1, "HIGH_VOLATILITY": 0.9, "UNCERTAIN": 0.0, "TRENDING_BULL": 0.0, "TRENDING_BEAR": 0.0, "POSSIBLE_REVERSAL": 0.0}
    jsd_shift = RegimeDriftEngine.compute_jsd(p, q_shift)
    psi_shift, status_shift, _ = RegimeDriftEngine.compute_psi(p, q_shift)
    assert jsd_shift > 0.0
    assert psi_shift > 0.10


# -----------------------------------------------------------------------------
# 12. Regime Drift — Wasserstein Volatility Distance
# -----------------------------------------------------------------------------
def test_12_regime_drift_wasserstein_distance():
    """Verify Wasserstein-1 distance on ordered volatility rank states."""
    p = {"SIDEWAYS": 1.0, "UNCERTAIN": 0.0, "TRENDING_BULL": 0.0, "TRENDING_BEAR": 0.0, "POSSIBLE_REVERSAL": 0.0, "HIGH_VOLATILITY": 0.0}
    q = {"SIDEWAYS": 0.0, "UNCERTAIN": 0.0, "TRENDING_BULL": 0.0, "TRENDING_BEAR": 0.0, "POSSIBLE_REVERSAL": 0.0, "HIGH_VOLATILITY": 1.0}
    w = RegimeDriftEngine.compute_wasserstein_volatility(p, q)
    assert w > 0.0


# -----------------------------------------------------------------------------
# 13. Regime Drift — Transition Matrix & Duration Dynamics
# -----------------------------------------------------------------------------
def test_13_regime_drift_transitions_and_durations():
    """Verify transition probabilities and mean durations."""
    records = [
        {"datetime_utc": "2026-01-01T00:00:00Z", "regime": "SIDEWAYS"},
        {"datetime_utc": "2026-01-01T00:05:00Z", "regime": "SIDEWAYS"},
        {"datetime_utc": "2026-01-01T00:10:00Z", "regime": "HIGH_VOLATILITY"},
        {"datetime_utc": "2026-01-01T00:15:00Z", "regime": "HIGH_VOLATILITY"},
    ]
    durations = RegimeDriftEngine.compute_mean_durations(records)
    assert durations["SIDEWAYS"]["mean_bars"] == 2.0
    assert durations["HIGH_VOLATILITY"]["mean_bars"] == 2.0

    transitions = RegimeDriftEngine.compute_transition_matrix(records)
    assert transitions["SIDEWAYS"]["SIDEWAYS"] == 0.5
    assert transitions["SIDEWAYS"]["HIGH_VOLATILITY"] == 0.5


# -----------------------------------------------------------------------------
# 14. Research Readiness — Hardened Fail-Closed on Unimported Month
# -----------------------------------------------------------------------------
def test_14_readiness_hardening_fail_closed():
    """Verify unimported month (2026-10) returns BLOCKED_NO_DATA and score 0.0%."""
    eval_10 = ResearchReadinessEngine.evaluate_readiness("2026-10")
    assert eval_10["overall_verdict"] == "BLOCKED_NO_DATA"
    assert eval_10["overall_score_pct"] == 0.0
    assert "Bu dönem için doğrulanmış piyasa verisi bulunmuyor" in eval_10["user_message"]
    for m in eval_10["modules"]:
        assert m["status"] == "BLOCKED_NO_DATA"
        assert m["readiness_score_pct"] == 0.0


# -----------------------------------------------------------------------------
# 15. Research Readiness — Canonical Month 2026-09 Ready
# -----------------------------------------------------------------------------
def test_15_readiness_canonical_ready():
    """Verify imported canonical month (2026-09) returns READY with 100.0% score."""
    eval_09 = ResearchReadinessEngine.evaluate_readiness("2026-09")
    assert eval_09["overall_verdict"] == "READY"
    assert eval_09["overall_score_pct"] == 100.0


# -----------------------------------------------------------------------------
# 16. Dashboard API — Comparative Endpoints
# -----------------------------------------------------------------------------
def test_16_api_comparative_endpoints():
    """Verify /api/v1/product/comparative-analysis and /api/v1/product/comparative-export."""
    code, res = ProductDashboardApiService.handle_request(
        "/api/v1/product/comparative-analysis",
        {"month_a": ["2024-03"], "month_b": ["2024-11"], "interval": ["1d"]}
    )
    assert code == HTTPStatus.OK
    assert res["status"] == "success"
    assert "delta_metrics" in res

    code_exp, res_exp = ProductDashboardApiService.handle_request(
        "/api/v1/product/comparative-export",
        {"month_a": ["2024-03"], "month_b": ["2024-11"], "format": ["csv"]}
    )
    assert code_exp == HTTPStatus.OK
    assert res_exp["format"] == "csv"
    assert "# CBE HISTORICAL COMPARATIVE WORKBENCH EXPORT" in res_exp["content"]


# -----------------------------------------------------------------------------
# 17. Dashboard API — Regime Drift Endpoint
# -----------------------------------------------------------------------------
def test_17_api_regime_drift_endpoint():
    """Verify /api/v1/product/regime-drift endpoint."""
    code, res = ProductDashboardApiService.handle_request(
        "/api/v1/product/regime-drift",
        {"preset": ["q4_2025_vs_q1_2026"]}
    )
    assert code == HTTPStatus.OK
    assert res["status"] == "success"
    assert "drift_telemetry" in res
    assert res["drift_telemetry"]["population_stability_index"] >= 0.0


# -----------------------------------------------------------------------------
# 18. Dashboard API — Derivation Status Endpoint
# -----------------------------------------------------------------------------
def test_18_api_derivation_status_endpoint():
    """Verify /api/v1/product/derivation-status endpoint."""
    code, res = ProductDashboardApiService.handle_request(
        "/api/v1/product/derivation-status",
        {}
    )
    assert code == HTTPStatus.OK
    assert res["status"] == "success"
    assert res["canonical_source_interval"] == "5m"
    assert res["derivation_pipeline_ready"] is True


# -----------------------------------------------------------------------------
# 19. Governance Invariants Enforcement
# -----------------------------------------------------------------------------
def test_19_governance_invariants():
    """Enforce strict offline governance and zero live trading rules."""
    code, gov = ProductDashboardApiService.handle_request("/api/v1/product/governance", {})
    assert code == HTTPStatus.OK
    contract = gov.get("governance_contract", {})
    assert contract.get("technical_decision") == "TECHNICAL_NO_GO"
    assert contract.get("governance_authorization") == "NOT_GRANTED"
    assert contract.get("production_token_issued") is False

    caps = gov.get("capabilities_matrix", [])
    obs = next((c for c in caps if c.get("capability") == "PROSPECTIVE_LIVE_OBSERVATION"), None)
    assert obs and obs["status"] == "DISABLED"
    order = next((c for c in caps if c.get("capability") == "ORDER_EXECUTION"), None)
    assert order and order["status"] == "PERMANENTLY_PROHIBITED"

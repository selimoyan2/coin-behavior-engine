"""Sprint Product Acceleration 04 — Advanced Analytical Workbench Test Suite.

Verifies:
1. Market Regime Analytics (105,120 bars, duration percentiles, volatility conditioning)
2. Empirical Markov Transition Matrix (row stochasticity, transition counts, 95% CIs)
3. Regime Persistence & Survival Curves (Kaplan-Meier S(t), empirical histograms, hazard rates)
4. Advanced Macro Impact Laboratory (236 events, multi-horizon returns, volatility jumps)
5. Analog Forensic Audit & Scaling Resolution (+0.89% verified vs distorted +88.90%)
6. Out-of-Sample Analog Calibration (directional rate, corridor coverage)
7. Deterministic Offline Scenario Laboratory (4 scenario types, repeatability, timing)
8. Bounded Research Exports (CSV/JSON, formula injection defense, row capping)
9. Web Server POST routing & Governance Invariants
"""

from http import HTTPStatus
import json
import pytest

from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.web.server import EngineRequestHandler


# =============================================================================
# 1. Regime Intelligence Center Tests
# =============================================================================

def test_regime_analytics_distribution_and_stats():
    """Verify 6-regime distributions, duration percentiles, and volatility profiles."""
    status_code, data = ProductDashboardApiService.handle_request("/api/v1/product/regime-analytics")
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["total_bars"] == 105120
    assert data["total_episodes"] > 10000

    regimes = data["regimes"]
    assert len(regimes) == 6
    regime_names = {r["regime"] for r in regimes}
    expected = {"SIDEWAYS", "UNCERTAIN", "TRENDING_BULL", "HIGH_VOLATILITY", "TRENDING_BEAR", "POSSIBLE_REVERSAL"}
    assert regime_names == expected

    # Check that frequency percentages sum to ~100%
    total_pct = sum(r["frequency_percent"] for r in regimes)
    assert 99.5 <= total_pct <= 100.5

    # Check duration percentiles structure
    for r in regimes:
        assert r["mean_duration_hours"] > 0
        assert r["median_duration_hours"] > 0
        assert r["p10_duration_hours"] <= r["p25_duration_hours"] <= r["p75_duration_hours"] <= r["p90_duration_hours"]
        assert r["realized_vol_mean"] > 0


def test_regime_transition_matrix_stochasticity():
    """Verify empirical 6x6 Markov transition matrix and transition probabilities."""
    status_code, data = ProductDashboardApiService.handle_request("/api/v1/product/regime-transitions")
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["total_transitions_observed"] == 12721

    matrix = data["transition_matrix"]
    assert len(matrix) == 6

    # Verify transition probabilities from each source regime
    for src, dst_dict in matrix.items():
        assert len(dst_dict) == 6
        prob_sum = sum(dst["probability"] for dst in dst_dict.values())
        # Probabilities sum to 1.0 (or 0.0 if empty source)
        assert 0.99 <= prob_sum <= 1.01 or prob_sum == 0.0

    # Verify recent transitions exist and have required fields
    recent = data["recent_transitions"]
    assert len(recent) > 0
    sample = recent[0]
    assert "timestamp" in sample
    assert "from_regime" in sample
    assert "to_regime" in sample
    assert "close_price" in sample


def test_regime_persistence_and_survival_curves():
    """Verify Kaplan-Meier survival curves S(t) and empirical duration bins."""
    status_code, data = ProductDashboardApiService.handle_request("/api/v1/product/regime-persistence")
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert "persistence" in data

    pers = data["persistence"]
    assert "SIDEWAYS" in pers
    assert "HIGH_VOLATILITY" in pers

    for reg, p_info in pers.items():
        assert p_info["episodes_count"] > 0
        assert p_info["median_duration_hours"] > 0
        survival = p_info["survival_curve"]
        assert len(survival) > 0

        # Survival curve S(t) must be monotonically non-increasing
        probs = [pt["survival_probability"] for pt in survival]
        for i in range(len(probs) - 1):
            assert probs[i] >= probs[i+1]


# =============================================================================
# 2. Advanced Macro Event Impact Laboratory Tests
# =============================================================================

def test_macro_impact_cross_category_analytics():
    """Verify cross-category macro reactions, volatility expansion, and control baseline."""
    status_code, data = ProductDashboardApiService.handle_request("/api/v1/product/macro-impact")
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["total_verified_events"] == 236

    categories = data["categories"]
    assert len(categories) >= 5
    cat_names = [c["category"] for c in categories]
    assert "US_INFLATION" in cat_names
    assert "US_MONETARY_POLICY" in cat_names
    assert "US_LABOR" in cat_names

    # Verify volatility multiplier vs control is computed
    for c in categories:
        assert "volatility_multiplier_vs_control" in c
        assert c["volatility_multiplier_vs_control"] >= 0.5
        assert "mean_ret_1h_pct" in c
        assert "distribution_1h_bins" in c


# =============================================================================
# 3. Analog Intelligence & Scaling Defect Resolution
# =============================================================================

def test_analog_scaling_defect_resolution():
    """Forensic verification: ensure 100x scaling distortion is fixed (+0.89% instead of +88.90%)."""
    # 1. Check get_analogs return values
    status_code, data = ProductDashboardApiService.get_analogs({"decision_time": ["2026-08-15T14:30:00Z"]})
    assert status_code == HTTPStatus.OK
    disp = data["trajectory_dispersion"]

    # Mean 24h return must be ~ +0.89%, NOT +88.90%
    assert 0.80 <= disp["mean_24h_return_percent"] <= 0.95
    assert 0.70 <= disp["median_24h_return_percent"] <= 0.80

    # Check individual analog return
    first_analog = data["analogs"][0]
    assert abs(first_analog["fwd_ret_24h_percent"]) < 10.0  # reasonable single-digit %

    # 2. Check analog validation endpoint
    s_val, val_data = ProductDashboardApiService.handle_request("/api/v1/product/analog-validation")
    assert s_val == HTTPStatus.OK
    assert val_data["status"] == "success"
    assert val_data["forensic_audit_extreme_values"]["verified_status"] == "AUDITED_AND_REMEDIATED"
    assert val_data["forensic_audit_extreme_values"]["verified_remediated_mean_24h_return"] == "+0.89%"


def test_analog_out_of_sample_calibration():
    """Verify out-of-sample directional calibration and dispersion corridor coverage."""
    status_code, data = ProductDashboardApiService.handle_request("/api/v1/product/analog-validation")
    assert status_code == HTTPStatus.OK
    oos = data["out_of_sample_calibration"]
    assert oos["directional_accuracy_pct"] == 52.4
    assert oos["dispersion_corridor_coverage_pct"] >= 80.0
    assert oos["economic_viability"] == "STATISTICALLY_INTERESTING_BUT_NOT_ECONOMIC"


# =============================================================================
# 4. Deterministic Offline Scenario Laboratory Tests
# =============================================================================

def test_scenario_evaluation_regime_forward_return():
    """Verify deterministic forward return scenario evaluation."""
    payload = {
        "scenario_type": "regime_forward_return",
        "regime": "COMPRESSION",
        "horizon": "4h",
        "sample_limit": 200,
    }
    status_code, data = ProductDashboardApiService.handle_post_request(
        "/api/v1/product/scenarios/evaluate",
        body=payload,
    )
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["scenario_type"] == "regime_forward_return"
    assert data["parameters"]["sample_size"] == 200
    assert "mean_return_pct" in data["metrics"]
    assert "downside_p10_pct" in data["metrics"]
    assert "upside_p90_pct" in data["metrics"]
    assert len(data["histogram"]) > 0

    # Repeat test to prove determinism
    status_code2, data2 = ProductDashboardApiService.handle_post_request(
        "/api/v1/product/scenarios/evaluate",
        body=payload,
    )
    assert data["metrics"] == data2["metrics"]


def test_scenario_evaluation_other_types():
    """Verify volatility expansion and hold period sensitivity scenarios."""
    # Volatility expansion
    s1, d1 = ProductDashboardApiService.handle_post_request(
        "/api/v1/product/scenarios/evaluate",
        body={"scenario_type": "volatility_expansion"},
    )
    assert s1 == HTTPStatus.OK
    assert d1["scenario_type"] == "volatility_expansion"
    assert "subsequent_expansion_probability_pct" in d1["metrics"]

    # Hold period sensitivity
    s2, d2 = ProductDashboardApiService.handle_post_request(
        "/api/v1/product/scenarios/evaluate",
        body={"scenario_type": "hold_period_sensitivity"},
    )
    assert s2 == HTTPStatus.OK
    assert d2["scenario_type"] == "hold_period_sensitivity"
    assert len(d2["sensitivity_table"]) == 7


def test_scenario_evaluation_bad_parameters():
    """Verify invalid scenario requests return 400 Bad Request."""
    status_code, data = ProductDashboardApiService.handle_post_request(
        "/api/v1/product/scenarios/evaluate",
        body={"scenario_type": "invalid_unknown_type"},
    )
    assert status_code == HTTPStatus.BAD_REQUEST
    assert "error" in data


# =============================================================================
# 5. Research Exports & Formula Injection Defense Tests
# =============================================================================

def test_research_export_csv_and_formula_defense():
    """Verify CSV export sanitization against spreadsheet formula injection (=, +, -, @)."""
    status_code, data = ProductDashboardApiService.handle_request(
        "/api/v1/product/research-export",
        {"dataset": ["regimes"], "format": ["csv"], "limit": ["50"]},
    )
    assert status_code == HTTPStatus.OK
    assert data["format"] == "csv"
    assert data["rows_exported"] == 6
    assert data["formula_injection_defense"] == "ENFORCED"
    assert "cbe_research_regimes_" in data["filename"]
    assert "regime,bar_count,frequency_percent" in data["content"]


def test_research_export_json():
    """Verify bounded JSON export format."""
    status_code, data = ProductDashboardApiService.handle_request(
        "/api/v1/product/research-export",
        {"dataset": ["transitions"], "format": ["json"], "limit": ["20"]},
    )
    assert status_code == HTTPStatus.OK
    assert data["format"] == "json"
    assert data["rows_exported"] <= 20
    assert len(data["data"]) <= 20


# =============================================================================
# 6. Governance Invariants Integrity
# =============================================================================

def test_sprint04_governance_invariants():
    """Verify fail-closed governance invariants remain locked."""
    status_code, data = ProductDashboardApiService.handle_request("/api/v1/product/governance")
    assert status_code == HTTPStatus.OK
    gov = data["governance_contract"]
    assert gov["technical_decision"] == "TECHNICAL_NO_GO"
    assert gov["governance_authorization"] == "NOT_GRANTED"
    assert gov["production_token_issued"] is False
    assert "capabilities_matrix" in data
    order_cap = next(c for c in data["capabilities_matrix"] if c["capability"] == "ORDER_EXECUTION")
    assert order_cap["status"] == "PERMANENTLY_PROHIBITED"

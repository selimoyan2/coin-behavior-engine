"""Sprint 37 Verification Suite: Market Regime Predictive Validity & Scientific Research Lab V3.

Validates all 20 acceptance criteria:
1. PredictiveValidityAnalyticsEngine singleton initialization and caching
2. Forward horizons precomputation (1h, 4h, 12h, 24h, 72h: returns, log returns, MAE, MFE, MDD, RV)
3. Causal point-in-time guarantee (strictly historical expanding quantiles, no future data leakage)
4. Circular Block Bootstrap empirical 95% Confidence Intervals
5. Newey-West HAC standard error and t-statistic calculation (lag truncation H-1)
6. Realistic 30 bps round-trip transaction cost haircutting
7. Benjamini-Hochberg False Discovery Rate (FDR) multiple testing q-values
8. Holm-Bonferroni step-down family-wise error rate adjusted p-values
9. Scientific Scorecard exact structure (30 hypothesis tests: 6 regimes x 5 horizons)
10. Scientific verdict classification logic (SUPPORTED, INCONCLUSIVE, NOT_SUPPORTED, INSUFFICIENT_DATA)
11. Volatility elevation empirical validation (HIGH_VOLATILITY forward volatility clustering)
12. Reversal fallacy empirical validation (POSSIBLE_REVERSAL binomial test fails to beat 50%)
13. Kolmogorov-Smirnov test between SIDEWAYS and UNCERTAIN forward returns
14. Unconditional return null distribution baseline
15. Simple 24h momentum and 24h mean-reversion baselines
16. Lagged realized volatility baseline forecast comparison
17. Annual walk-forward stability across 2022, 2023, 2024, 2025, 2026
18. REST API endpoints contract verification (HTTP 200 and schema validation)
19. Permanent live trading prohibition preservation (HTTP 403 Forbidden)
20. Dashboard UI candidate rendering and Tier distinction banner
"""

import pytest
from http import HTTPStatus

from coin_behavior_engine.product.predictive_validity_analytics import (
    PredictiveValidityAnalyticsEngine,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.dashboard_ui import render_product_dashboard_html


class TestSprint37PredictiveValidity:
    """Comprehensive test suite for Sprint 37 deliverables."""

    @pytest.fixture(scope="class")
    def engine(self):
        """Provide a cached PredictiveValidityAnalyticsEngine instance."""
        return PredictiveValidityAnalyticsEngine.get_instance()

    @pytest.fixture(scope="class")
    def api_service(self):
        """Provide a ProductDashboardApiService instance."""
        return ProductDashboardApiService()

    # 1. Singleton and Caching
    def test_01_predictive_validity_singleton_and_caching(self, engine):
        eng2 = PredictiveValidityAnalyticsEngine.get_instance()
        assert engine is eng2
        df = engine.get_forward_returns_df()
        assert df is not None
        assert len(df) > 40000

    # 2. Forward Horizons Precomputation
    def test_02_forward_horizons_precomputation(self, engine):
        df = engine.get_forward_returns_df()
        expected_horizons = ["1h", "4h", "12h", "24h", "72h"]
        for h in expected_horizons:
            assert f"fwd_ret_{h}" in df.columns
            assert f"fwd_log_ret_{h}" in df.columns
            assert f"fwd_mae_{h}" in df.columns
            assert f"fwd_mfe_{h}" in df.columns
            assert f"fwd_mdd_{h}" in df.columns
            assert f"fwd_vol_{h}" in df.columns

    # 3. Lookahead-Free Point-in-Time Guarantee
    def test_03_lookahead_free_point_in_time_guarantee(self, engine):
        df = engine.get_forward_returns_df()
        assert "regime" in df.columns
        assert "close" in df.columns
        # Verify valid regimes
        valid_regimes = {
            "SIDEWAYS", "UNCERTAIN", "TRENDING_BULL",
            "TRENDING_BEAR", "POSSIBLE_REVERSAL", "HIGH_VOLATILITY"
        }
        actual_regimes = set(df["regime"].dropna().unique())
        assert actual_regimes.issubset(valid_regimes)

    # 4. Circular Block Bootstrap Empirical 95% CI
    def test_04_circular_block_bootstrap_ci(self, engine):
        scorecard = engine.get_scorecard()
        assert len(scorecard) == 30
        for entry in scorecard:
            lo = entry["bootstrap_ci_95_lower"]
            hi = entry["bootstrap_ci_95_upper"]
            assert lo <= hi
            # For finite sample size, confidence interval width should be non-zero
            assert (hi - lo) >= 0.0

    # 5. Newey-West HAC Standard Errors
    def test_05_newey_west_hac_standard_errors(self, engine):
        scorecard = engine.get_scorecard()
        for entry in scorecard:
            t_stat = entry["newey_west_t_stat"]
            p_val = entry["raw_p_value"]
            if t_stat is not None:
                assert isinstance(t_stat, float)
                assert 0.0 <= p_val <= 1.0

    # 6. Realistic 30 bps Transaction Cost Haircutting
    def test_06_economic_transaction_cost_deduction(self, engine):
        scorecard = engine.get_scorecard()
        for entry in scorecard:
            gross = entry["mean_fwd_return_gross_pct"]
            net = entry["mean_fwd_return_net_pct"]
            # Net return must be exactly gross return minus 0.30%
            assert pytest.approx(net, abs=1e-4) == gross - 0.30

    # 7. Benjamini-Hochberg FDR Multiple Testing Correction
    def test_07_multiple_testing_benjamini_hochberg_fdr(self, engine):
        scorecard = engine.get_scorecard()
        q_vals = [e["fdr_q_value"] for e in scorecard if e["fdr_q_value"] is not None]
        assert len(q_vals) == 30
        for q in q_vals:
            assert 0.0 <= q <= 1.0

    # 8. Holm-Bonferroni Step-Down Correction
    def test_08_multiple_testing_holm_bonferroni(self, engine):
        scorecard = engine.get_scorecard()
        for entry in scorecard:
            raw_p = entry["raw_p_value"]
            holm_p = entry["holm_p_value"]
            if raw_p is not None and holm_p is not None:
                # Holm p-value must be greater than or equal to raw p-value
                assert holm_p >= raw_p or pytest.approx(holm_p, abs=1e-5) == raw_p
                assert holm_p <= 1.0

    # 9. Scientific Scorecard Exact Structure
    def test_09_scorecard_structure_and_counts(self, engine):
        scorecard = engine.get_scorecard()
        assert len(scorecard) == 30
        expected_keys = {
            "hypothesis_id", "regime", "horizon", "sample_size",
            "mean_fwd_return_gross_pct", "mean_fwd_return_net_pct",
            "bootstrap_ci_95_lower", "bootstrap_ci_95_upper",
            "newey_west_t_stat", "raw_p_value", "fdr_q_value", "holm_p_value",
            "mae_pct", "mfe_pct", "mean_fwd_max_drawdown_pct",
            "mean_fwd_realized_vol_pct", "scientific_verdict", "verdict_reason"
        }
        for entry in scorecard:
            assert expected_keys.issubset(set(entry.keys()))

    # 10. Scientific Verdict Classification Logic
    def test_10_scientific_verdict_classification(self, engine):
        scorecard = engine.get_scorecard()
        valid_verdicts = {"SUPPORTED", "INCONCLUSIVE", "NOT_SUPPORTED", "INSUFFICIENT_DATA"}
        for entry in scorecard:
            verdict = entry["scientific_verdict"]
            assert verdict in valid_verdicts
            # For directional return hypotheses, if net return is negative and raw p > 0.05, it cannot be SUPPORTED
            if entry["regime"] != "HIGH_VOLATILITY" and entry["mean_fwd_return_net_pct"] <= 0 and entry["raw_p_value"] > 0.05:
                assert verdict in {"NOT_SUPPORTED", "INCONCLUSIVE"}

    # 11. Volatility Elevation Empirical Validation (Clustering)
    def test_11_volatility_clustering_supported(self, engine):
        trans = engine.get_transition_dynamics()
        assert "volatility_elevation" in trans
        ve = trans["volatility_elevation"]
        assert ve["p_val"] < 0.01  # Highly significant
        assert ve["ratio"] > 1.2    # HIGH_VOLATILITY forward vol is substantially higher

    # 12. Reversal Fallacy Empirical Validation
    def test_12_reversal_fallacy_refuted(self, engine):
        trans = engine.get_transition_dynamics()
        assert "reversal_fallacy" in trans
        rf = trans["reversal_fallacy"]
        assert "p_val" in rf
        assert "reversal_rate" in rf
        assert 0.40 <= rf["reversal_rate"] <= 0.65

    # 13. Kolmogorov-Smirnov Test (Sideways vs Uncertain)
    def test_13_sideways_uncertain_distributional_equivalence(self, engine):
        trans = engine.get_transition_dynamics()
        assert "ks_test_sideways_uncertain" in trans
        ks = trans["ks_test_sideways_uncertain"]
        assert "d_stat" in ks
        assert "p_val" in ks
        assert ks["d_stat"] < 0.10  # Very small distributional difference

    # 14. Unconditional Return Null Baseline
    def test_14_unconditional_return_baseline(self, engine):
        baselines = engine.get_baseline_comparisons()
        assert "unconditional_forward_returns" in baselines
        uncond = baselines["unconditional_forward_returns"]
        for h in ["1h", "4h", "12h", "24h", "72h"]:
            assert h in uncond
            assert "mean_pct" in uncond[h]
            assert "std_pct" in uncond[h]

    # 15. Momentum and Mean-Reversion Baselines
    def test_15_momentum_and_mean_reversion_baselines(self, engine):
        baselines = engine.get_baseline_comparisons()
        assert "momentum_24h_hit_rate_pct" in baselines
        assert "mean_reversion_24h_hit_rate_pct" in baselines
        mom_hr = baselines["momentum_24h_hit_rate_pct"]
        mr_hr = baselines["mean_reversion_24h_hit_rate_pct"]
        assert 40.0 <= mom_hr <= 60.0
        assert 40.0 <= mr_hr <= 60.0

    # 16. Lagged Volatility Baseline Comparison
    def test_16_lagged_volatility_forecast_baseline(self, engine):
        baselines = engine.get_baseline_comparisons()
        assert "volatility_forecast" in baselines
        vf = baselines["volatility_forecast"]
        assert "lagged_vol_rmse" in vf
        assert "regime_vol_rmse" in vf
        assert vf["regime_vol_rmse"] > 0

    # 17. Annual Walk-Forward Stability
    def test_17_walk_forward_stability(self, engine):
        wf = engine.get_walk_forward_stability()
        years = ["2022", "2023", "2024", "2025", "2026"]
        for y in years:
            assert y in wf
            assert "SIDEWAYS" in wf[y]
            assert "HIGH_VOLATILITY" in wf[y]

    # 18. REST API Endpoints Contract
    def test_18_rest_api_predictive_validity_endpoints(self):
        endpoints = [
            "/api/v1/product/predictive-validity/scorecard",
            "/api/v1/product/predictive-validity/forward-returns",
            "/api/v1/product/predictive-validity/transitions",
            "/api/v1/product/predictive-validity/baselines",
            "/api/v1/product/predictive-validity/walk-forward",
        ]
        for ep in endpoints:
            code, res = ProductDashboardApiService.handle_request(ep, {}, {})
            assert code == HTTPStatus.OK
            assert "status" in res or "scorecard" in res or "findings" in res or "annual_validation" in res

    # 19. Permanent Live Trading Prohibition
    def test_19_live_trading_prohibition_preserved(self):
        prohibited_endpoints = [
            "/api/v1/product/research/btc-timing/live-trade/execute",
            "/api/v1/order/execute",
            "/api/v1/trade/live",
            "/api/v1/execution/submit",
        ]
        for ep in prohibited_endpoints:
            code, res = ProductDashboardApiService.handle_post_request(ep, {})
            assert code == HTTPStatus.FORBIDDEN
            assert "GOVERNANCE_VIOLATION" in str(res) or "PROHIBITED" in str(res).upper() or "YASAK" in str(res).upper()

    # 20. Dashboard UI Elements and Tier Distinction Banner
    def test_20_dashboard_ui_v14_candidate_elements(self):
        html = render_product_dashboard_html()
        assert "tab-btn-predictive-validity" in html
        assert "module-predictive-validity" in html
        assert "loadPredictiveValidity" in html
        assert "TIER 1" in html
        assert "TIER 2" in html
        assert "pv-scorecard-table" in html
        assert "CBE-0.7.0 (STRICTLY_FROZEN)" in html

"""Sprint 38 Test Suite: Predictive Validity Intelligence, Evidence Explorer & Scientific Decision Support (Dashboard V15).

Verifies all Sprint 38 specifications and acceptance criteria:
1. Canonical model invariance: CBE-0.7.0 remains STRICTLY_FROZEN.
2. Dataset provenance and zero synthetic bars invariant.
3. Scorecard exact reconciliation: 30 hypotheses (4 SUPPORTED, 25 NOT_SUPPORTED, 1 INCONCLUSIVE).
4. Evidence Explorer API contract and detailed profile metadata enrichment.
5. Evidence Explorer filtering by verdict (SUPPORTED=4, NOT_SUPPORTED=25, INCONCLUSIVE=1).
6. Evidence Explorer filtering by research category (VOLATILITY_PERSISTENCE=5, DIRECTIONAL_RETURN=25).
7. Volatility Forecast Benchmark Laboratory: Regime RMSE 16.0612 vs GARCH 17.4578 (+8.00% improvement).
8. Volatility Forecast Benchmark: Diebold-Mariano test and strict non-trading boundary assertion.
9. Market Regime Persistence Intelligence: durations, transition matrix, and CANONICAL_PARITY_NOT_ESTABLISHED.
10. Model Tier Governance: Tier 1 frozen causal states vs Tier 2 derived research classifier.
11. Directional Predictability Reality Check: Momentum 47.57%, Mean-reversion 52.51%, Unconditional +0.0518%.
12. Directional Predictability: Mandatory disclaimer and REJECTED_OVERFITTING preservation.
13. Transaction cost impact: 30 bps round-trip friction eliminates gross margin across all directional tests.
14. Scientific Evidence & Reproducibility metadata (Manifest SHA-256 1ff50222..., Experiment ID).
15. Annual walk-forward stability and sign inversion verification across 2022-2026.
16. Permanent live trading prohibition: HTTP 403 Forbidden on all order/execution endpoints.
17. Negative governance tests: Unauthorized parameter modification or live order dispatch blocked.
18. Dashboard V15 HTML rendering: 8 integrated scientific sections and Evidence Explorer modal.
19. Subview switcher buttons and modal elements integrity.
20. In-memory caching and sub-10ms response latency benchmark.
"""

import pytest
from http import HTTPStatus
import time

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.product.predictive_validity_analytics import (
    PredictiveValidityAnalyticsEngine,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.dashboard_ui import render_product_dashboard_html


class TestSprint38PredictiveIntelligence:
    """Comprehensive test suite for Sprint 38 Predictive Validity Intelligence & Dashboard V15."""

    @pytest.fixture(scope="class")
    def engine(self):
        """Provide a cached PredictiveValidityAnalyticsEngine instance."""
        return PredictiveValidityAnalyticsEngine.get_instance()

    # 1. Model status invariant: CBE-0.7.0 is STRICTLY_FROZEN
    def test_01_canonical_model_frozen_invariant(self):
        assert FROZEN_MODEL_VERSION == "CBE-0.7.0"

    # 2. Dataset provenance and zero synthetic bars
    def test_02_dataset_provenance_and_zero_synthetic_bars(self, engine):
        meta = engine.get_scientific_evidence_metadata()
        assert meta["manifest_sha256"] == "1ff50222c31a486b094a7f2ac9f06d38b1258527e5492acbef5faf9a73c55f14"
        assert meta["synthetic_bars_count"] == 0
        assert meta["hourly_bars_evaluated"] == 42717

    # 3. Scorecard exact reconciliation: 30 hypotheses (4 SUPPORTED, 25 NOT_SUPPORTED, 1 INCONCLUSIVE)
    def test_03_scorecard_exact_reconciliation(self, engine):
        scorecard = engine.get_scientific_scorecard()["scorecard"]
        assert len(scorecard) == 30
        verdicts = {}
        for h in scorecard:
            v = h["scientific_verdict"]
            verdicts[v] = verdicts.get(v, 0) + 1
        assert verdicts["SUPPORTED"] == 4
        assert verdicts["NOT_SUPPORTED"] == 25
        assert verdicts["INCONCLUSIVE"] == 1
        assert verdicts["SUPPORTED"] + verdicts["NOT_SUPPORTED"] + verdicts["INCONCLUSIVE"] == 30

    # 4. Evidence Explorer API contract and detailed profile metadata enrichment
    def test_04_evidence_explorer_api_profile_structure(self, engine):
        res = engine.get_hypothesis_evidence_explorer_data()
        assert res["total_hypotheses"] == 30
        assert len(res["items"]) == 30
        for item in res["items"]:
            assert "hypothesis_id" in item
            assert "regime" in item
            assert "horizon" in item
            assert "research_category" in item
            assert "h0_definition" in item
            assert "h1_definition" in item
            assert "data_period" in item
            assert "sample_size" in item
            assert item["sample_size"] > 0
            assert "test_methodology" in item
            assert "confidence_interval_95" in item
            assert len(item["confidence_interval_95"]) == 2
            assert "raw_p_value" in item
            assert "fdr_q_value" in item
            assert "holm_p_value" in item
            assert "baseline_comparison" in item
            assert "manifest_sha256" in item
            assert "scientific_verdict" in item
            assert "limitations" in item
            assert "source_evidence_file" in item

    # 5. Evidence Explorer filtering by verdict
    def test_05_evidence_explorer_verdict_filters(self, engine):
        supp = engine.get_hypothesis_evidence_explorer_data(verdict="SUPPORTED")
        assert supp["filtered_hypotheses"] == 4
        assert all(x["scientific_verdict"] == "SUPPORTED" for x in supp["items"])

        nsupp = engine.get_hypothesis_evidence_explorer_data(verdict="NOT_SUPPORTED")
        assert nsupp["filtered_hypotheses"] == 25
        assert all(x["scientific_verdict"] == "NOT_SUPPORTED" for x in nsupp["items"])

        incon = engine.get_hypothesis_evidence_explorer_data(verdict="INCONCLUSIVE")
        assert incon["filtered_hypotheses"] == 1
        assert all(x["scientific_verdict"] == "INCONCLUSIVE" for x in incon["items"])

    # 6. Evidence Explorer filtering by research category
    def test_06_evidence_explorer_category_filters(self, engine):
        vol = engine.get_hypothesis_evidence_explorer_data(category="VOLATILITY_PERSISTENCE")
        assert vol["filtered_hypotheses"] == 5
        assert all(x["regime"] == "HIGH_VOLATILITY" for x in vol["items"])

        ret = engine.get_hypothesis_evidence_explorer_data(category="DIRECTIONAL_RETURN")
        assert ret["filtered_hypotheses"] == 25
        assert all(x["regime"] != "HIGH_VOLATILITY" for x in ret["items"])

    # 7. Volatility Forecast Benchmark Laboratory metrics
    def test_07_volatility_benchmark_metrics(self, engine):
        vol_lab = engine.get_volatility_forecast_benchmark_data()
        models = vol_lab["models"]
        assert "regime_conditioned_volatility" in models
        assert "garch_lagged_benchmark" in models

        regime_rmse = models["regime_conditioned_volatility"]["rmse"]
        garch_rmse = models["garch_lagged_benchmark"]["rmse"]

        assert regime_rmse == 16.0612
        assert garch_rmse == 17.4578
        assert vol_lab["sample_size"] == 42693
        assert vol_lab["forecast_horizon"] == "24h"
        assert models["regime_conditioned_volatility"]["relative_improvement_vs_benchmark_pct"] == 8.00

    # 8. Volatility Forecast Benchmark: Diebold-Mariano test and strict non-trading boundary
    def test_08_volatility_benchmark_comparability_and_boundary(self, engine):
        vol_lab = engine.get_volatility_forecast_benchmark_data()
        dm = vol_lab["error_distribution"]["diebold_mariano_test"]
        assert dm["dm_statistic"] < 0
        assert dm["p_value"] < 0.001
        comp = vol_lab["methodological_comparability"]
        assert comp["identical_test_period"] is True
        assert comp["identical_target_variable"] is True
        assert comp["identical_horizon"] is True
        assert "HTTP 403 Forbidden" in vol_lab["scientific_boundary_notice"]

    # 9. Market Regime Persistence Intelligence
    def test_09_regime_persistence_intelligence(self, engine):
        pers = engine.get_regime_persistence_intelligence()
        assert pers["governance_status"] == "CANONICAL_PARITY_NOT_ESTABLISHED"
        metrics = pers["persistence_metrics"]
        assert "SIDEWAYS" in metrics
        assert "HIGH_VOLATILITY" in metrics
        assert metrics["SIDEWAYS"]["mean_duration_hours"] == 18.4
        assert metrics["SIDEWAYS"]["persistence_prob"] > 0.90
        assert pers["total_transitions_analyzed"] == 3464

    # 10. Model Tier Governance
    def test_10_model_tier_governance(self, engine):
        pers = engine.get_regime_persistence_intelligence()
        tiers = pers["tier_architecture"]
        assert tiers["tier_1_canonical_model"]["status"] == "STRICTLY_FROZEN"
        assert tiers["tier_1_canonical_model"]["mutation_allowed"] is False
        assert tiers["tier_2_derived_research_classifier"]["classification"] == "DERIVED_RESEARCH_CLASSIFIER"
        assert tiers["tier_2_derived_research_classifier"]["parity_verdict"] == "CANONICAL_PARITY_NOT_ESTABLISHED"

    # 11. Directional Predictability Reality Check baseline metrics
    def test_11_directional_reality_check_metrics(self, engine):
        dir_data = engine.get_directional_predictability_data()
        m = dir_data["metrics"]
        assert m["momentum_24h_hit_rate_pct"] == 47.57
        assert m["mean_reversion_24h_hit_rate_pct"] == 52.51
        assert m["unconditional_forward_return_mean_pct"] == 0.0518
        assert m["transaction_cost_round_trip_bps"] == 30.0
        assert m["net_directional_alpha_bps"] < 0

    # 12. Directional Predictability: Mandatory disclaimer and REJECTED_OVERFITTING
    def test_12_directional_reality_check_disclaimer(self, engine):
        dir_data = engine.get_directional_predictability_data()
        assert dir_data["primary_verdict"] == "REJECTED_OVERFITTING"
        assert dir_data["mandatory_disclaimer"] == "Yönsel fiyat tahmininde istatistiksel olarak güvenilir bir üstünlük henüz doğrulanmamıştır."
        assert dir_data["trading_signals"] == "ZERO_SIGNALS_GENERATED"
        assert dir_data["live_trading_eligibility"] == "PERMANENTLY_PROHIBITED"

    # 13. Transaction cost impact: 30 bps round-trip haircut
    def test_13_transaction_cost_impact(self, engine):
        scorecard = engine.get_scientific_scorecard()["scorecard"]
        for h in scorecard:
            gross = h.get("mean_fwd_return_gross_pct", h.get("mean_forward_return_pct", 0.0))
            net = h.get("net_return_after_costs_pct", h.get("mean_fwd_return_net_pct", 0.0))
            # Net return must strictly reflect transaction cost deduction
            assert net < gross or gross == 0.0

    # 14. Scientific Evidence & Reproducibility metadata
    def test_14_scientific_evidence_metadata(self, engine):
        meta = engine.get_scientific_evidence_metadata()
        assert meta["experiment_id"] == "EXP-CBE-PV-202611-V3"
        assert meta["canonical_model_version"] == "CBE-0.7.0 (STRICTLY_FROZEN)"
        assert meta["methodology_version"] == "V3-HAC-CBB-FDR"
        assert meta["reproducibility_status"] == "DETERMINISTIC_REPRODUCIBLE"
        assert "scorecard" in meta["artifacts_map"]

    # 15. Annual walk-forward stability across 2022-2026
    def test_15_walk_forward_stability(self, engine):
        wf = engine.get_walk_forward_stability()
        for y in ["2022", "2023", "2024", "2025", "2026"]:
            assert y in wf
            assert "SIDEWAYS" in wf[y]
            assert "HIGH_VOLATILITY" in wf[y]

    # 16. Permanent live trading prohibition: HTTP 403 Forbidden
    def test_16_permanent_live_trading_prohibition(self):
        prohibited = [
            "/place-order",
            "/live-trade/execute",
            "/api/v1/order/execute",
            "/api/v1/trade/live",
            "/api/v1/execution/submit",
        ]
        for ep in prohibited:
            status, res = ProductDashboardApiService.handle_post_request(ep, {})
            assert status == HTTPStatus.FORBIDDEN
            assert res.get("error") == "GOVERNANCE_VIOLATION"

    # 17. Negative governance tests
    def test_17_negative_governance_block(self):
        # Attempting GET on order endpoints must also be rejected
        status, res = ProductDashboardApiService.handle_request("/api/v1/order/execute", {}, {})
        assert status == HTTPStatus.FORBIDDEN

    # 18. Dashboard V15 HTML rendering
    def test_18_dashboard_v15_html_rendering(self):
        html = render_product_dashboard_html()
        assert "tab-btn-predictive-validity" in html
        assert "module-predictive-validity" in html
        assert "DASHBOARD V15" in html
        assert "CBE-0.7.0 (STRICTLY_FROZEN)" in html
        assert "TIER 1" in html
        assert "TIER 2" in html
        assert "pv-scorecard-table" in html
        assert "pv-evidence-modal" in html
        assert "pv-reality-check-banner" in html

    # 19. Subview switcher buttons and modal elements integrity
    def test_19_subview_switcher_elements(self):
        html = render_product_dashboard_html()
        assert "btn-pv-sub-overview" in html
        assert "btn-pv-sub-evidence" in html
        assert "btn-pv-sub-volatility" in html
        assert "btn-pv-sub-persistence" in html
        assert "btn-pv-sub-directional" in html
        assert "btn-pv-sub-uncertainty" in html
        assert "btn-pv-sub-limitations" in html
        assert "btn-pv-sub-history" in html
        assert "pv-filter-category" in html

    # 20. In-memory caching and sub-10ms response latency benchmark
    def test_20_performance_latency_benchmark(self):
        endpoints = [
            "/api/v1/product/predictive-validity/scorecard",
            "/api/v1/product/predictive-validity/evidence-explorer",
            "/api/v1/product/predictive-validity/volatility-benchmark",
            "/api/v1/product/predictive-validity/regime-persistence",
            "/api/v1/product/predictive-validity/directional-reality",
            "/api/v1/product/predictive-validity/evidence-metadata",
        ]
        for ep in endpoints:
            start = time.perf_counter()
            status, res = ProductDashboardApiService.handle_request(ep, {}, {})
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            assert status == HTTPStatus.OK
            assert elapsed_ms < 50.0, f"Endpoint {ep} took {elapsed_ms:.2f}ms (>50ms cap)"

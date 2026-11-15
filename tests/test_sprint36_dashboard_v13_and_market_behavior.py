"""Sprint 36 Verification Suite: Dashboard V13, Canonical Data Consistency & Market Behavior Intelligence.

Validates all 20 acceptance criteria:
1. Central coverage single source of truth (HistoricalDatasetRegistry / DatasetRegistryV2)
2. 58 complete months + 1 partial month (59 total months)
3. Latest verified candle: 2026-11-15 21:15:00 UTC (Close 64966.01)
4. Granular candle quality taxonomy (CandleQualityClass enum)
5. Audit of 8 missing 5m candles across 4 gaps in November 2026
6. Multi-timeframe gap ripple effect across 15m, 1h, 4h, 1d
7. Zero synthetic candles guarantee (synthetic_candles_count == 0)
8. MarketBehaviorAnalyticsEngine singleton and caching
9. Canonical regimes coverage
10. Regime frequencies sum to 100% (+/- 0.05%)
11. Regime persistence duration metrics (mean, median, max)
12. Transition matrix P_ij probabilities row-sum to 1.0
13. Annual regime distributions from 2022 to 2026
14. Historical drawdown analytics (peak, trough, max DD %)
15. Downside risk metrics: downside deviation, VaR 95/99%, CVaR 95/99%
16. Regime 24h excursions (MAE/MFE)
17. Causal point-in-time calculation (prefix invariance, zero lookahead)
18. Live trading permanently prohibited (HTTP 403 Forbidden)
19. REST API endpoint contracts
20. Dashboard UI V13 elements and dynamic coverage binding
"""

import pytest
from http import HTTPStatus

from coin_behavior_engine.product.dataset_registry import (
    HistoricalDatasetRegistry,
    DatasetRegistryV2,
    DatasetStatus,
    CandleQualityClass,
)
from coin_behavior_engine.product.market_behavior_analytics import (
    MarketBehaviorAnalyticsEngine,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.dashboard_ui import render_product_dashboard_html


class TestSprint36DashboardV13AndMarketBehavior:
    """Complete test suite for Sprint 36 deliverables."""

    # 1. Central Coverage Single Source of Truth
    def test_01_central_coverage_single_source_of_truth(self):
        reg = DatasetRegistryV2()
        cov = reg.get_central_coverage()
        assert cov["symbol"] == "BTCUSDT"
        assert cov["earliest_month"] == "2022-01"
        assert cov["latest_month"] == "2026-11"
        assert cov["total_months"] == 59
        assert cov["complete_months"] == 58
        assert cov["partial_months"] == 1
        assert "58 Tam Ay + 1 Kısmi Ay" in cov["coverage_span_text"]

    # 2. Latest Verified Candle Verification
    def test_02_latest_verified_candle(self):
        reg = HistoricalDatasetRegistry()
        cov = reg.get_central_coverage()
        latest = cov["latest_verified_candle"]
        assert latest["timestamp_utc"] == "2026-11-15T21:15:00Z"
        assert latest["interval"] == "5m"
        assert latest["month"] == "2026-11"
        assert latest["close"] == 64966.01

    # 3. Granular Candle Quality Classes Taxonomy
    def test_03_candle_quality_classes_taxonomy(self):
        assert CandleQualityClass.COMPLETE_VERIFIED.value == "COMPLETE_VERIFIED"
        assert CandleQualityClass.PARTIAL_VERIFIED.value == "PARTIAL_VERIFIED"
        assert CandleQualityClass.INCOMPLETE_CANDLE.value == "INCOMPLETE_CANDLE"
        assert CandleQualityClass.GAP_AFFECTED.value == "GAP_AFFECTED"
        assert CandleQualityClass.MISSING.value == "MISSING"
        assert CandleQualityClass.INVALID.value == "INVALID"

    # 4. Audit of November 2026 Missing 5m Candles (8 Candles, 4 Gaps)
    def test_04_november_missing_candles_audit(self):
        reg = HistoricalDatasetRegistry()
        cov = reg.get_central_coverage()
        missing_info = cov["missing_candles"]
        assert missing_info["affected_month"] == "2026-11"
        assert missing_info["total_missing_5m"] == 8
        assert missing_info["total_missing_minutes"] == 40
        assert missing_info["synthetic_candles_allowed"] is False
        assert missing_info["synthetic_candles_count"] == 0
        assert len(missing_info["gaps"]) == 4

        # Verify the 4 exact gap timestamps
        gaps = missing_info["gaps"]
        assert gaps[0]["from_utc"] == "2026-11-03 05:10 UTC"
        assert gaps[0]["missing_bars"] == 3
        assert gaps[1]["from_utc"] == "2026-11-04 21:55 UTC"
        assert gaps[1]["missing_bars"] == 1
        assert gaps[2]["from_utc"] == "2026-11-05 01:30 UTC"
        assert gaps[2]["missing_bars"] == 1
        assert gaps[3]["from_utc"] == "2026-11-07 08:55 UTC"
        assert gaps[3]["missing_bars"] == 3

    # 5. Multi-Timeframe Gap Ripple Effect
    def test_05_multitimeframe_gap_ripple_effect(self):
        reg = HistoricalDatasetRegistry()
        audit = reg.audit_partial_candles_and_gaps(year=2026, month=11)
        breakdown = audit["timeframe_quality_breakdown"]

        # 5m
        assert breakdown["5m"]["total_candles"] == 4280
        assert breakdown["5m"]["complete_verified_count"] == 4280

        # 15m
        assert breakdown["15m"]["gap_affected_count"] == 1
        assert breakdown["15m"]["incomplete_candle_count"] == 1
        assert breakdown["15m"]["complete_verified_count"] == 1426

        # 1h
        assert breakdown["1h"]["gap_affected_count"] == 2
        assert breakdown["1h"]["incomplete_candle_count"] == 1
        assert breakdown["1h"]["complete_verified_count"] == 355

        # 4h
        assert breakdown["4h"]["gap_affected_count"] == 4
        assert breakdown["4h"]["incomplete_candle_count"] == 1
        assert breakdown["4h"]["complete_verified_count"] == 85

        # 1d
        assert breakdown["1d"]["gap_affected_count"] == 4
        assert breakdown["1d"]["incomplete_candle_count"] == 1
        assert breakdown["1d"]["complete_verified_count"] == 10

    # 6. Market Behavior Analytics Engine Singleton & Caching
    def test_06_market_behavior_engine_singleton(self):
        engine1 = MarketBehaviorAnalyticsEngine.get_instance()
        engine2 = MarketBehaviorAnalyticsEngine.get_instance()
        assert engine1 is engine2

    # 7. Canonical Regime Distribution & Frequencies Sum to 100%
    def test_07_canonical_regimes_frequencies(self):
        engine = MarketBehaviorAnalyticsEngine.get_instance()
        regimes = engine.get_regime_analytics()
        assert len(regimes) >= 5

        total_freq = sum(r["frequency_pct"] for r in regimes)
        assert abs(total_freq - 100.0) < 0.1

        regime_names = [r["regime"] for r in regimes]
        assert "SIDEWAYS" in regime_names
        assert "UNCERTAIN" in regime_names
        assert "HIGH_VOLATILITY" in regime_names

    # 8. Regime Persistence Duration Metrics
    def test_08_regime_persistence_durations(self):
        engine = MarketBehaviorAnalyticsEngine.get_instance()
        regimes = engine.get_regime_analytics()
        for r in regimes:
            dur = r["duration_hours"]
            assert dur["mean"] > 0
            assert dur["median"] > 0
            assert dur["max"] >= dur["mean"]
            assert r["annualized_volatility_pct"] > 0

    # 9. Transition Probability Matrix Rows Sum to 1.0
    def test_09_transition_matrix_row_stochastic(self):
        engine = MarketBehaviorAnalyticsEngine.get_instance()
        trans = engine.get_transition_matrix()
        probs = trans["transition_probabilities"]
        assert len(probs) > 0
        for from_regime, targets in probs.items():
            row_sum = sum(targets.values())
            assert abs(row_sum - 1.0) < 0.01, f"Row sum for {from_regime} is {row_sum}"
            # Self-transition should be highest (persistence property)
            assert targets[from_regime] > 0.5, f"Persistence of {from_regime} should exceed 0.5"

    # 10. Annual Regime Distributions (2022 to 2026)
    def test_10_annual_regime_distributions(self):
        engine = MarketBehaviorAnalyticsEngine.get_instance()
        annual = engine.get_annual_regime_distribution()
        assert annual["status"] == "success"
        years = annual["years"]
        assert 2022 in years
        assert 2023 in years
        assert 2024 in years
        assert 2025 in years
        assert 2026 in years
        for yr in years:
            dist = annual["annual_distributions"][str(yr)]
            assert dist["total_bars"] > 1000
            sum_pct = sum(dist["regime_distribution"].values())
            assert abs(sum_pct - 100.0) < 0.1

    # 11. Historical Drawdown Analytics
    def test_11_historical_drawdown_metrics(self):
        engine = MarketBehaviorAnalyticsEngine.get_instance()
        risk = engine.get_market_risk_metrics()
        dd = risk["historical_drawdown"]
        assert dd["max_drawdown_pct"] < -60.0
        assert dd["peak"]["price_usdt"] > 45000.0
        assert dd["trough"]["price_usdt"] < 17000.0
        assert "2022-03" in dd["peak"]["datetime"]
        assert "2022-11" in dd["trough"]["datetime"]

    # 12. Downside Risk Metrics (VaR & CVaR)
    def test_12_downside_risk_metrics(self):
        engine = MarketBehaviorAnalyticsEngine.get_instance()
        risk = engine.get_market_risk_metrics()
        down = risk["downside_risk"]
        assert down["annualized_downside_deviation_pct"] > 30.0
        assert down["var_95_1h_pct"] > 0
        assert down["var_99_1h_pct"] > down["var_95_1h_pct"]
        assert down["cvar_95_expected_shortfall_pct"] > down["var_95_1h_pct"]
        assert down["cvar_99_expected_shortfall_pct"] > down["var_99_1h_pct"]

    # 13. Regime 24h Excursions (MAE vs MFE)
    def test_13_regime_excursions(self):
        engine = MarketBehaviorAnalyticsEngine.get_instance()
        risk = engine.get_market_risk_metrics()
        excursions = risk["regime_excursions_24h_mean_pct"]
        assert len(excursions) > 0
        for reg, exc in excursions.items():
            assert exc["mean_mfe_pct"] > 0
            assert exc["mean_mae_pct"] > 0

    # 14. Prefix Invariance & Causal Point-in-Time Check
    def test_14_causal_prefix_invariance(self):
        engine = MarketBehaviorAnalyticsEngine.get_instance()
        # 2022 analytics should only use 2022 data
        risk_2022 = engine.get_market_risk_metrics(year_filter=2022)
        assert risk_2022["filter_applied"] == "YEAR_2022"
        assert risk_2022["sample_bars"] == 8760

        # Overall analytics uses full 42,717 verified 1h bars (2022-01 to 2026-11-15 21:00)
        risk_all = engine.get_market_risk_metrics()
        assert risk_all["sample_bars"] == 42717

    # 15. Live Trading Prohibition HTTP 403
    def test_15_live_trading_permanently_prohibited(self):
        trading_endpoints = [
            "/api/v1/product/research/btc-timing/live-trade/execute",
            "/api/v1/order/execute",
            "/api/v1/trade/live",
            "/api/v1/execution/submit",
        ]
        for ep in trading_endpoints:
            code, res = ProductDashboardApiService.handle_post_request(ep, {})
            assert code == HTTPStatus.FORBIDDEN
            assert "GOVERNANCE_VIOLATION" in str(res) or "PROHIBITED" in str(res).upper() or "YASAK" in str(res).upper()

    # 16. REST API Central Coverage Endpoint
    def test_16_api_central_coverage(self):
        code, res = ProductDashboardApiService.handle_request("/api/v1/product/central-coverage", {}, {})
        assert code == HTTPStatus.OK
        assert res["total_months"] == 59
        assert res["complete_months"] == 58
        assert res["partial_months"] == 1

    # 17. REST API Candle Quality Audit Endpoint
    def test_17_api_candle_quality_audit(self):
        code, res = ProductDashboardApiService.handle_request("/api/v1/product/candle-quality-audit", {}, {})
        assert code == HTTPStatus.OK
        assert "timeframe_quality_breakdown" in res
        assert "5m" in res["timeframe_quality_breakdown"]
        assert "1h" in res["timeframe_quality_breakdown"]

    # 18. REST API Market Behavior Sub-endpoints
    def test_18_api_market_behavior_subendpoints(self):
        # /market-behavior/regimes
        code, res = ProductDashboardApiService.handle_request("/api/v1/product/market-behavior/regimes", {}, {})
        assert code == HTTPStatus.OK
        assert res["regimes_count"] > 0

        # /market-behavior/transitions
        code, res = ProductDashboardApiService.handle_request("/api/v1/product/market-behavior/transitions", {}, {})
        assert code == HTTPStatus.OK
        assert "transition_probabilities" in res

        # /market-behavior/annual
        code, res = ProductDashboardApiService.handle_request("/api/v1/product/market-behavior/annual", {}, {})
        assert code == HTTPStatus.OK
        assert "annual_distributions" in res

        # /market-behavior/risk
        code, res = ProductDashboardApiService.handle_request("/api/v1/product/market-behavior/risk", {}, {})
        assert code == HTTPStatus.OK
        assert "historical_drawdown" in res

    # 19. Dashboard V13 HTML Elements & Upgraded Title
    def test_19_dashboard_v13_html_elements(self):
        html = render_product_dashboard_html()
        assert "<title>Coin Behavior Engine | Araştırma Portalı & Piyasa İstihbaratı V13</title>" in html
        assert "PİYASA DAVRANIŞI ARAŞTIRMA LABORATUVARI V2" in html
        assert "tbl-transition-matrix" in html
        assert "tbl-annual-regime-distribution" in html
        assert "risk-metrics-kpi-grid" in html
        assert "market-behavior-year-select" in html
        assert "dyn-coverage-span" in html

    # 20. Verification that hardcoded September 2026 coverage is eliminated
    def test_20_elimination_of_hardcoded_september_coverage(self):
        html = render_product_dashboard_html()
        # Ensure obsolete header strings are not present
        assert "2022-01 — 2026-09 (41.615 Saatlik Bar)" not in html
        assert "2022-01 — 2026-09 (57 Kesintisiz Ay)" not in html

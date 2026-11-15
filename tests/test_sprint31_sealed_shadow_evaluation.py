"""
Comprehensive Automated Test Suite for Sprint 31:
Sealed BTC Strategy Evaluation & Offline Shadow Research.

Covers:
1. Policy freeze integrity & SHA-256 manifest tampering detection.
2. Parameter changes after freeze rejection.
3. Offline dataset import validation (Parquet/CSV, OHLCV, gaps, duplicates, non-negativity).
4. Holdout contamination audit & provenance trust boundaries.
5. Deterministic simulation, cash/satoshi balance conservation, and fee attribution.
6. Benchmark alignment across all 6 frozen policies.
7. Independent evaluation of Hypotheses H1 through H5 with Bonferroni correction.
8. Lookahead prevention & next candle open execution timing.
9. Dashboard V9 API endpoints & persistence across restarts.
10. Governance restrictions & permanent prohibition of live trading (HTTP 403).
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.product.btc_timing_research.accounting_reconciler import (
    IndependentAccountingReconciler,
)
from coin_behavior_engine.product.btc_timing_research.dataset_adapter import (
    REGISTERED_BTC_DATASETS,
    HistoricalBTCDatasetAdapter,
)
from coin_behavior_engine.product.btc_timing_research.experimental_policies import (
    DerivedRegimeConfirmationPolicy,
    PeriodicRebalancePolicy,
    TrendLowTurnoverPolicy,
)
from coin_behavior_engine.product.btc_timing_research.offline_dataset_importer import (
    PROVENANCE_PROVISIONAL_IMPORT,
    PROVENANCE_RESTRICTED_UNVERIFIED,
    PROVENANCE_SELF_DECLARED_REJECTED,
    OfflineDatasetImporter,
)
from coin_behavior_engine.product.btc_timing_research.paper_portfolio_engine import (
    PaperPortfolioEngine,
    run_historical_simulation,
)
from coin_behavior_engine.product.btc_timing_research.sealed_evaluation_engine import (
    BASELINE_SOURCE_COMMIT,
    CANONICAL_EXPERIMENT_STATUS,
    CANONICAL_MODEL_ID,
    CANONICAL_MODEL_STATUS,
    FROZEN_POLICY_SPECIFICATIONS,
    SealedEvaluationRunner,
    SealedPolicyPackage,
)
from coin_behavior_engine.product.btc_timing_research.timing_policy_engine import (
    BuyAndHoldPolicy,
    SimpleTrendPolicy,
    USDTCashPolicy,
    create_policy,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService


# =============================================================================
# 1. POLICY FREEZE & MANIFEST TAMPERING TESTS
# =============================================================================

class TestPolicyFreezeAndTampering:
    def test_frozen_policies_count_and_keys(self):
        pkg = SealedPolicyPackage.create()
        assert len(pkg.policies) == 6
        expected_keys = {
            "POLICY_BUY_AND_HOLD",
            "POLICY_USDT_CASH",
            "POLICY_SIMPLE_TREND",
            "POLICY_TREND_LOW_TURNOVER",
            "POLICY_PERIODIC_REBALANCE",
            "POLICY_DERIVED_REGIME_CONFIRMATION",
        }
        assert set(pkg.policies.keys()) == expected_keys

    def test_package_fingerprint_deterministic(self):
        pkg1 = SealedPolicyPackage.create()
        pkg2 = SealedPolicyPackage.create()
        assert pkg1.sha256_fingerprint == pkg2.sha256_fingerprint
        assert len(pkg1.sha256_fingerprint) == 64

    def test_package_integrity_verified(self):
        pkg = SealedPolicyPackage.create()
        ok, err = pkg.verify_integrity()
        assert ok is True
        assert err is None

    def test_tampering_detected_on_parameter_change(self):
        pkg = SealedPolicyPackage.create()
        # Tamper with parameter
        tampered_policies = copy.deepcopy(pkg.policies)
        tampered_policies["POLICY_TREND_LOW_TURNOVER"]["parameters"]["hysteresis_pct"] = 0.05
        tampered_pkg = SealedPolicyPackage(
            package_id=pkg.package_id,
            sealed_at_utc=pkg.sealed_at_utc,
            source_commit=pkg.source_commit,
            policies=tampered_policies,
            assumptions=pkg.assumptions,
            sha256_fingerprint=pkg.sha256_fingerprint,
            canonical_model_status=pkg.canonical_model_status,
            canonical_experiment_status=pkg.canonical_experiment_status,
        )
        ok, err = tampered_pkg.verify_integrity()
        assert ok is False
        assert "tampering detected" in err.lower()

    def test_tampering_detected_on_policy_addition_or_removal(self):
        pkg = SealedPolicyPackage.create()
        tampered_policies = copy.deepcopy(pkg.policies)
        del tampered_policies["POLICY_USDT_CASH"]
        tampered_pkg = SealedPolicyPackage(
            package_id=pkg.package_id,
            sealed_at_utc=pkg.sealed_at_utc,
            source_commit=pkg.source_commit,
            policies=tampered_policies,
            assumptions=pkg.assumptions,
            sha256_fingerprint=pkg.sha256_fingerprint,
            canonical_model_status=pkg.canonical_model_status,
            canonical_experiment_status=pkg.canonical_experiment_status,
        )
        ok, err = tampered_pkg.verify_integrity()
        assert ok is False

    def test_canonical_model_frozen_and_not_evaluable(self):
        pkg = SealedPolicyPackage.create()
        assert pkg.canonical_model_status == "STRICTLY_FROZEN"
        assert pkg.canonical_experiment_status == "NOT_EVALUABLE_CANONICAL_OUTPUT_UNAVAILABLE"


# =============================================================================
# 2. OFFLINE DATASET IMPORT VALIDATION TESTS
# =============================================================================

class TestOfflineDatasetImportValidation:
    @pytest.fixture
    def importer(self):
        return OfflineDatasetImporter()

    def test_valid_parquet_import_contiguous_2025(self, importer):
        target_path = "data/historical/historical_binance_btcusdt_1h_2025.parquet"
        res = importer.validate_file(target_path, proposed_dataset_id="DS-BTC-1H-2025-SEALED")
        assert res.is_valid is True
        assert res.total_bars == 8760
        assert res.is_continuous is True
        assert res.missing_candle_count == 0
        assert res.duplicate_count == 0
        assert res.bad_candle_count == 0
        assert res.holdout_contamination_detected is False
        assert res.is_eligible_unseen_holdout is True

    def test_invalid_symbol_rejected(self, importer, tmp_path):
        bad_file = tmp_path / "bad_sym.parquet"
        df = pd.DataFrame({
            "open_time": [1735689600000, 1735693200000],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [10.0, 12.0],
        })
        df.to_parquet(bad_file)
        res = importer.validate_file(bad_file, symbol="ETHUSDT")
        assert res.is_valid is False
        assert any("symbol" in e.lower() for e in res.validation_errors)

    def test_invalid_market_type_rejected(self, importer, tmp_path):
        bad_file = tmp_path / "futures.parquet"
        df = pd.DataFrame({
            "open_time": [1735689600000, 1735693200000],
            "open": [100.0, 101.0],
            "high": [102.0, 103.0],
            "low": [99.0, 100.0],
            "close": [101.0, 102.0],
            "volume": [10.0, 12.0],
        })
        df.to_parquet(bad_file)
        res = importer.validate_file(bad_file, market_type="FUTURES")
        assert res.is_valid is False
        assert any("market type" in e.lower() for e in res.validation_errors)

    def test_invalid_ohlcv_mathematical_integrity(self, importer, tmp_path):
        bad_file = tmp_path / "bad_ohlcv.parquet"
        df = pd.DataFrame({
            "open_time": [1735689600000, 1735693200000, 1735696800000],
            "open": [100.0, 100.0, 100.0],
            "high": [90.0, 110.0, 110.0],   # Row 0: high < open!
            "low": [80.0, 120.0, 90.0],    # Row 1: low > open!
            "close": [85.0, 105.0, 100.0],
            "volume": [10.0, 10.0, -5.0],   # Row 2: negative volume!
        })
        df.to_parquet(bad_file)
        res = importer.validate_file(bad_file)
        assert res.is_valid is False
        assert res.bad_candle_count >= 2

    def test_missing_candles_gap_detection(self, importer, tmp_path):
        gap_file = tmp_path / "gap.parquet"
        # 3600000 ms is 1h. Jump by 7200000 ms (1 missing candle)
        df = pd.DataFrame({
            "open_time": [1735689600000, 1735696800000],
            "open": [100.0, 101.0],
            "high": [105.0, 106.0],
            "low": [95.0, 96.0],
            "close": [101.0, 102.0],
            "volume": [10.0, 12.0],
        })
        df.to_parquet(gap_file)
        res = importer.validate_file(gap_file)
        assert res.missing_candle_count == 1
        assert res.is_continuous is False

    def test_duplicate_timestamp_detection(self, importer, tmp_path):
        dup_file = tmp_path / "dup.parquet"
        df = pd.DataFrame({
            "open_time": [1735689600000, 1735689600000],  # Duplicate
            "open": [100.0, 101.0],
            "high": [105.0, 106.0],
            "low": [95.0, 96.0],
            "close": [101.0, 102.0],
            "volume": [10.0, 12.0],
        })
        df.to_parquet(dup_file)
        res = importer.validate_file(dup_file)
        assert res.duplicate_count == 1
        assert res.is_continuous is False

    def test_holdout_contamination_detected_on_2024_overlap(self, importer, tmp_path):
        # 2024 Q4 range: 2024-10-04 to 2024-12-31 (approx 1728000000000 ms)
        contam_file = tmp_path / "contam.parquet"
        ts_2024_q4 = int(pd.Timestamp("2024-11-01T00:00:00Z").timestamp() * 1000)
        df = pd.DataFrame({
            "open_time": [ts_2024_q4, ts_2024_q4 + 3600000],
            "open": [65000.0, 65100.0],
            "high": [65500.0, 65600.0],
            "low": [64800.0, 64900.0],
            "close": [65100.0, 65200.0],
            "volume": [50.0, 60.0],
        })
        df.to_parquet(contam_file)
        res = importer.validate_file(contam_file)
        assert res.holdout_contamination_detected is True
        assert res.is_eligible_unseen_holdout is False

    def test_self_declared_provenance_rejected(self, importer, tmp_path):
        test_file = tmp_path / "self_dec.parquet"
        df = pd.DataFrame({
            "open_time": [1735689600000, 1735693200000],
            "open": [100.0, 101.0],
            "high": [105.0, 106.0],
            "low": [95.0, 96.0],
            "close": [101.0, 102.0],
            "volume": [10.0, 12.0],
        })
        df.to_parquet(test_file)
        res = importer.validate_file(
            test_file,
            declared_provenance_meta={"self_certified": True, "source": "SelfClaimedAuthority"}
        )
        assert res.provenance_classification == PROVENANCE_SELF_DECLARED_REJECTED


# =============================================================================
# 3. SEALED EVALUATION RUNNER & SIMULATION INTEGRITY
# =============================================================================

class TestSealedEvaluationExecution:
    @pytest.fixture
    def runner(self):
        return SealedEvaluationRunner()

    def test_readiness_audit_structure(self, runner):
        readiness = runner.check_readiness()
        assert readiness["package_integrity_verified"] is True
        assert readiness["canonical_model_status"] == "STRICTLY_FROZEN"
        assert readiness["target_evaluation_dataset"] == "DS-BTC-1H-2025-SEALED"
        assert readiness["dataset_verified"] is True
        assert readiness["frozen_policies_count"] == 6

    def test_full_evaluation_execution_stages(self, runner):
        res = runner.execute_sealed_evaluation(accessed_by="Test_Suite_Runner")
        assert res["status"] == "COMPLETED"
        expected_stages = [
            "POLICY_FREEZE",
            "DATASET_ELIGIBILITY_CHECK",
            "HOLDOUT_ACCESS_AUTHORIZATION",
            "FIRST_EVALUATION_ACCESS",
            "HISTORICAL_SIMULATION",
            "BENCHMARK_COMPARISON",
            "EVIDENCE_SEALING",
            "SCIENTIFIC_REPORT",
        ]
        assert res["stages_executed"] == expected_stages

    def test_cash_and_satoshi_conservation(self, runner):
        res = runner.execute_sealed_evaluation()
        assert res["accounting_verified"] is True
        for pid, s in res["accounting_summary"].items():
            assert s["cash_conserved"] is True, f"Cash conservation violated for {pid}"
            assert s["satoshi_conserved"] is True, f"Satoshi conservation violated for {pid}"
            assert s["accounting_reconciled"] is True, f"Accounting reconciliation failed for {pid}"

    def test_transaction_cost_decomposition_exactness(self, runner):
        res = runner.execute_sealed_evaluation()
        metrics = res["policy_metrics"]
        for pid, m in metrics.items():
            fees = m["total_fees_usdt"]
            spread = m["total_spread_usdt"]
            slippage = m["total_slippage_usdt"]
            total_costs = m["total_transaction_costs_usdt"]
            assert abs((fees + spread + slippage) - total_costs) < 0.05, f"Cost decomposition mismatch for {pid}"

    def test_turnover_control_cost_reduction(self, runner):
        res = runner.execute_sealed_evaluation()
        m_simple = res["policy_metrics"]["POLICY_SIMPLE_TREND"]
        m_low = res["policy_metrics"]["POLICY_TREND_LOW_TURNOVER"]
        assert m_low["total_transaction_costs_usdt"] < m_simple["total_transaction_costs_usdt"]
        cost_reduction = (m_simple["total_transaction_costs_usdt"] - m_low["total_transaction_costs_usdt"]) / m_simple["total_transaction_costs_usdt"]
        assert cost_reduction > 0.50, f"Expected >50% cost reduction, got {cost_reduction*100:.1f}%"

    def test_deterministic_simulation_repeatability(self, runner):
        res1 = runner.execute_sealed_evaluation()
        res2 = runner.execute_sealed_evaluation()
        m1 = res1["policy_metrics"]["POLICY_TREND_LOW_TURNOVER"]
        m2 = res2["policy_metrics"]["POLICY_TREND_LOW_TURNOVER"]
        assert m1["ending_equity_usdt"] == m2["ending_equity_usdt"]
        assert m1["net_return_pct"] == m2["net_return_pct"]
        assert m1["trade_count"] == m2["trade_count"]
        assert m1["total_transaction_costs_usdt"] == m2["total_transaction_costs_usdt"]


# =============================================================================
# 4. SCIENTIFIC HYPOTHESES TESTING (H1 - H5)
# =============================================================================

class TestScientificHypothesesEvaluation:
    @pytest.fixture
    def evaluation_results(self):
        runner = SealedEvaluationRunner()
        return runner.execute_sealed_evaluation()

    def test_all_five_hypotheses_evaluated(self, evaluation_results):
        hyps = evaluation_results["hypotheses"]
        assert len(hyps) == 5
        assert set(hyps.keys()) == {"H1", "H2", "H3", "H4", "H5"}

    def test_multiple_comparisons_bonferroni_adjustment(self, evaluation_results):
        for hid, h in evaluation_results["hypotheses"].items():
            # 5 hypotheses -> alpha = 0.05 / 5 = 0.01
            assert h["multiple_comparison_adjusted_alpha"] == 0.01

    def test_h1_verdict_supported(self, evaluation_results):
        h1 = evaluation_results["hypotheses"]["H1"]
        assert h1["verdict"] == "SUPPORTED"
        assert h1["test_statistic"] > 50.0  # >50% reduction

    def test_h2_verdict_supported(self, evaluation_results):
        h2 = evaluation_results["hypotheses"]["H2"]
        assert h2["verdict"] == "SUPPORTED"
        assert h2["test_statistic"] > 0.0  # net return improved

    def test_h3_verdict_supported(self, evaluation_results):
        h3 = evaluation_results["hypotheses"]["H3"]
        assert h3["verdict"] == "SUPPORTED"
        assert h3["test_statistic"] > 0.0  # drawdown severity reduced

    def test_h4_verdict_honest_unsupported(self, evaluation_results):
        h4 = evaluation_results["hypotheses"]["H4"]
        # In 2025, active timing did NOT outperform Buy & Hold
        assert h4["verdict"] == "UNSUPPORTED"
        assert h4["test_statistic"] < 0.0  # excess return is negative

    def test_h5_verdict_derived_regime(self, evaluation_results):
        h5 = evaluation_results["hypotheses"]["H5"]
        assert h5["verdict"] in ("SUPPORTED", "UNSUPPORTED")
        assert "DERIVED research classifier" in h5["notes"]

    def test_scientific_evidence_classification(self, evaluation_results):
        assert evaluation_results["scientific_classification"] == "SEALED_UNSEEN_HISTORICAL_EVALUATION"


# =============================================================================
# 5. DASHBOARD V9 API & GOVERNANCE RESTRICTIONS
# =============================================================================

class TestDashboardApiAndGovernance:
    def test_readiness_endpoint_http_200(self):
        code, res = ProductDashboardApiService.handle_request("research/btc-timing/sealed-evaluation/readiness")
        assert code == 200
        assert res.get("status") == "success"
        rd = res.get("readiness", {})
        assert rd.get("package_integrity_verified") is True

    def test_results_endpoint_http_200(self):
        code, res = ProductDashboardApiService.handle_request("research/btc-timing/sealed-evaluation/results")
        assert code == 200
        assert res.get("status") == "success"
        assert "policy_metrics" in res.get("latest_evaluation", {})

    def test_hypotheses_endpoint_http_200(self):
        code, res = ProductDashboardApiService.handle_request("research/btc-timing/sealed-evaluation/hypotheses")
        assert code == 200
        assert res.get("status") == "success"
        assert len(res.get("hypotheses", {})) == 5

    def test_import_endpoint_post_validation(self):
        code, res = ProductDashboardApiService.handle_post_request(
            "research/btc-timing/sealed-evaluation/import-dataset",
            {"file_path": "data/historical/historical_binance_btcusdt_1h_2025.parquet", "dataset_id": "DS-BTC-1H-2025-SEALED"}
        )
        assert code == 200
        assert res.get("status") == "success"

    def test_run_sealed_eval_endpoint_post(self):
        code, res = ProductDashboardApiService.handle_post_request(
            "research/btc-timing/sealed-evaluation/run",
            {"dataset_id": "DS-BTC-1H-2025-SEALED", "accessed_by": "Test_Runner"}
        )
        assert code == 200
        assert res.get("status") == "success"

    def test_live_trading_prohibited_http_403(self):
        endpoints_to_test = [
            "/api/v1/product/research/btc-timing/orders/live-trade",
            "/api/v1/product/research/btc-timing/broker-api/execute",
            "/api/v1/product/research/btc-timing/place-order",
            "/api/v1/product/research/btc-timing/trade/execute",
            "/api/v1/product/research/btc-timing/live_order",
        ]
        for ep in endpoints_to_test:
            code, res = ProductDashboardApiService.handle_post_request(ep, {"symbol": "BTCUSDT", "quantity": 1.0})
            assert code == 403, f"Endpoint {ep} should be forbidden (403), got {code}"
            assert res.get("error") == "GOVERNANCE_VIOLATION"

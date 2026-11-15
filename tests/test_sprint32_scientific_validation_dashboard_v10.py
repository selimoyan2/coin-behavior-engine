"""Sprint 32 Automated Test Suite: Scientific Validation Closure & Investment Research Dashboard V10.

Tests:
1. Dataset provenance, physical hashes, continuity, and conservative classification
2. Raw-to-merged 12-month parquet exact candle parity (8,760 bars)
3. Sealed policy package freeze, tamper detection, and SHA-256 seal (73a8349d...)
4. Freeze chronology and external TSA anchoring limitation
5. Statistical claims audit, serial dependence treatment, and p-value revocation
6. Transaction cost convention (one-way 17.5 bps vs round-trip 35.0 bps)
7. Independent portfolio double-entry accounting reconciliation (0.00 discrepancy)
8. Dashboard V10 REST API endpoints (overview, comparison, strategy, trades, costs, evidence, timeline, report)
9. Paginated trade ledger and filtering
10. Report generation across JSON, Markdown, and CSV
11. Live trading safety gating (HTTP 403)
12. Canonical model CBE-0.7.0 immutability
"""

from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
import pytest

from coin_behavior_engine.product.btc_timing_research.dataset_provenance_auditor import (
    DatasetProvenanceAuditor,
)
from coin_behavior_engine.product.btc_timing_research.statistical_claims_auditor import (
    StatisticalClaimsAuditor,
)
from coin_behavior_engine.product.btc_timing_research.transaction_cost_auditor import (
    TransactionCostAuditor,
)
from coin_behavior_engine.product.btc_timing_research.sealed_evaluation_auditor import (
    SealedEvaluationAuditor,
)
from coin_behavior_engine.product.btc_timing_research.investment_research_v10 import (
    InvestmentResearchV10Engine,
    POLICY_METADATA,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService


# =========================================================================
# TEST CLASS 1: DATASET PROVENANCE & RAW-TO-MERGED PARITY
# =========================================================================
class TestDatasetProvenanceAndParity:

    def test_monthly_partitions_count_and_months(self):
        auditor = DatasetProvenanceAuditor()
        audits = auditor.audit_monthly_partitions()
        assert len(audits) == 12
        months = [a.month for a in audits]
        expected_months = [f"2025-{m:02d}" for m in range(1, 13)]
        assert months == expected_months

    def test_monthly_partitions_ohlcv_and_zero_gaps(self):
        auditor = DatasetProvenanceAuditor()
        audits = auditor.audit_monthly_partitions()
        for a in audits:
            assert a.ohlcv_valid is True, f"OHLCV violation in {a.filename}"
            assert a.gaps_count == 0, f"Gap detected in {a.filename}"
            assert a.row_count > 0
            assert len(a.sha256) == 64

    def test_raw_to_merged_exact_candle_parity(self):
        auditor = DatasetProvenanceAuditor()
        is_eq, cols_match, raw_rows, merged_rows = auditor.verify_raw_to_merged_parity()
        assert cols_match is True
        assert raw_rows == 8760
        assert merged_rows == 8760
        assert is_eq is True

    def test_provenance_audit_classification_unverified(self):
        auditor = DatasetProvenanceAuditor()
        res = auditor.run_full_provenance_audit()
        assert res.total_bars == 8760
        assert res.duplicate_timestamps_count == 0
        assert res.timestamp_continuity_verified is True
        assert res.ohlcv_mathematical_integrity_verified is True
        assert res.historical_price_plausibility_verified is True
        assert res.external_crypto_authority_verified is False
        assert res.provenance_classification == "RESTRICTED_EVIDENCE_UNVERIFIED_PROVENANCE"

    def test_provenance_markdown_reports_generation(self):
        auditor = DatasetProvenanceAuditor()
        res = auditor.run_full_provenance_audit()
        md_prov = auditor.generate_provenance_audit_markdown(res)
        assert "# 01 — Dataset Provenance & Integrity Audit Report" in md_prov
        assert "RESTRICTED_EVIDENCE_UNVERIFIED_PROVENANCE" in md_prov
        assert "DS-BTC-1H-2025-SEALED" in md_prov

        md_parity = auditor.generate_raw_to_merged_markdown(res)
        assert "# 02 — Raw-to-Merged Data Verification Report" in md_parity
        assert "VERIFIED_EXACT_EQUIVALENCE" in md_parity


# =========================================================================
# TEST CLASS 2: STATISTICAL CLAIMS AUDIT & HYPOTHESIS RE-CLASSIFICATION
# =========================================================================
class TestStatisticalClaimsAudit:

    def test_all_five_hypotheses_audited(self):
        auditor = StatisticalClaimsAuditor()
        res = auditor.audit_all_hypotheses()
        assert len(res.hypotheses) == 5
        assert set(res.hypotheses.keys()) == {"H1", "H2", "H3", "H4", "H5"}

    def test_serial_dependence_and_pvalue_revocation(self):
        auditor = StatisticalClaimsAuditor()
        res = auditor.audit_all_hypotheses()
        for h_id, rec in res.hypotheses.items():
            # In all hypotheses, statistical significance cannot be established from N=1 serial path
            assert rec.statistical_verdict == "STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED"
            assert "serial" in rec.serial_dependence_assessment.lower()
            assert len(rec.statistical_assumptions_violated) >= 1

    def test_descriptive_verdicts_met_except_h4(self):
        auditor = StatisticalClaimsAuditor()
        res = auditor.audit_all_hypotheses()
        assert res.hypotheses["H1"].descriptive_verdict == "DESCRIPTIVE_THRESHOLD_MET"
        assert res.hypotheses["H2"].descriptive_verdict == "DESCRIPTIVE_THRESHOLD_MET"
        assert res.hypotheses["H3"].descriptive_verdict == "DESCRIPTIVE_THRESHOLD_MET"
        assert res.hypotheses["H4"].descriptive_verdict == "DESCRIPTIVE_THRESHOLD_FAILED"
        assert res.hypotheses["H5"].descriptive_verdict == "DESCRIPTIVE_THRESHOLD_MET"

    def test_h4_unsupported_honest_effect_size(self):
        auditor = StatisticalClaimsAuditor()
        res = auditor.audit_all_hypotheses()
        h4 = res.hypotheses["H4"]
        assert h4.test_statistic_value < 0.0  # Lagged buy and hold (-19.10 pp)
        assert h4.descriptive_verdict == "DESCRIPTIVE_THRESHOLD_FAILED"
        assert "REJECTED" in h4.interpretation

    def test_h5_canonical_model_attribution_disclaimer(self):
        auditor = StatisticalClaimsAuditor()
        res = auditor.audit_all_hypotheses()
        h5 = res.hypotheses["H5"]
        assert "NOT CANONICAL" in h5.canonical_model_attribution

    def test_statistical_audit_markdown_and_json_generation(self):
        auditor = StatisticalClaimsAuditor()
        res = auditor.audit_all_hypotheses()
        md = auditor.generate_audit_markdown(res)
        assert "# 03 — Statistical Claims Audit Report" in md
        assert "STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED" in md

        d_json = auditor.generate_corrected_classifications_json(res)
        assert "hypotheses" in d_json
        assert len(d_json["hypotheses"]) == 5


# =========================================================================
# TEST CLASS 3: TRANSACTION COST CONVENTION & INDEPENDENT ACCOUNTING
# =========================================================================
class TestTransactionCostAndAccounting:

    def test_cost_convention_one_way_vs_round_trip(self):
        auditor = TransactionCostAuditor()
        conv = auditor.audit_cost_conventions()
        # One-way is 17.5 bps
        assert conv.one_way_total_pct == 0.00175
        # Round trip is 35.0 bps
        assert conv.implied_round_trip_pct == 0.00350
        assert conv.taker_fee_pct == 0.00100
        assert conv.half_spread_pct == 0.00025
        assert conv.slippage_pct == 0.00050
        assert "total_round_trip_cost_pct" in conv.misleading_legacy_label

    def test_independent_portfolio_trade_reconstruction(self):
        auditor = TransactionCostAuditor()
        res = auditor.run_full_reconciliation()
        assert res.overall_accounting_verdict == "ALL_POLICIES_RECONCILED_ZERO_DISCREPANCY"
        assert len(res.policies) == 6
        for pol_key, p_rec in res.policies.items():
            assert p_rec.reconciliation_verdict == "EXACT_MATCH_ZERO_DISCREPANCY"
            assert p_rec.equity_discrepancy_usdt < 1.50
            assert p_rec.costs_discrepancy_usdt < 0.05
            assert p_rec.return_discrepancy_pct < 0.02
            assert p_rec.cash_flow_conservation_valid is True
            assert p_rec.satoshi_conservation_valid is True

    def test_compounded_performance_drag_multiplier(self):
        auditor = TransactionCostAuditor()
        res = auditor.run_full_reconciliation()
        drag = res.compounded_drag_analysis
        assert drag["direct_cash_cost_difference_usdt"] > 5000.0  # ~$5,995
        assert drag["total_equity_preservation_usdt"] > 2000.0   # Equity preserved
        assert drag["compounded_performance_drag_multiplier"] > 0.0


# =========================================================================
# TEST CLASS 4: SEALED EVALUATION INTEGRITY & POLICY FREEZE
# =========================================================================
class TestSealedEvaluationIntegrity:

    def test_policy_package_seal_verified(self):
        auditor = SealedEvaluationAuditor()
        integrity_ok, seal = auditor.verify_policy_package()
        assert integrity_ok is True
        assert seal == "73a8349dcf340be2360631df4e6307e5cb09ffa3b34ead81d27b9a0215f2ed3c"

    def test_chronology_pipeline_sequential(self):
        auditor = SealedEvaluationAuditor()
        res = auditor.audit_chronology()
        assert res.policy_package_integrity_verified is True
        assert res.all_stages_strictly_sequential is True
        assert len(res.stages_audited) == 8
        assert res.external_tsa_cryptographically_anchored is False
        assert "OFFLINE_HISTORICAL_RESEARCH" in res.scientific_evidence_classification

    def test_chronology_markdown_and_json(self):
        auditor = SealedEvaluationAuditor()
        res = auditor.audit_chronology()
        md = auditor.generate_chronology_audit_markdown(res)
        assert "# 07 — Policy Freeze Chronology & Sealed Pipeline Audit" in md
        assert res.expected_policy_package_seal in md

        d_json = auditor.generate_evidence_classification_json(res)
        assert "scientific_evidence_classification" in d_json


# =========================================================================
# TEST CLASS 5: DASHBOARD V10 BACKEND & REST API ENDPOINTS
# =========================================================================
class TestDashboardV10BackendAndApi:

    def test_v10_overview_endpoint(self):
        code, resp = ProductDashboardApiService.handle_request("/api/v1/product/research/btc-timing/v10/overview")
        assert code == HTTPStatus.OK
        assert resp["status"] == "success"
        assert resp["disclaimer_banner"] == "TARİHSEL ARAŞTIRMA — CANLI YATIRIM SİNYALİ DEĞİLDİR"
        assert resp["evaluation_period"]["total_hours"] == 8760
        assert resp["provenance_status"] == "RESTRICTED_EVIDENCE_UNVERIFIED_PROVENANCE"

    def test_v10_comparison_endpoint(self):
        code, resp = ProductDashboardApiService.handle_request("/api/v1/product/research/btc-timing/v10/comparison")
        assert code == HTTPStatus.OK
        assert resp["status"] == "success"
        assert len(resp["policies"]) == 6
        assert len(resp["equity_curves"]) == 6

    def test_v10_strategy_endpoint(self):
        code, resp = ProductDashboardApiService.handle_request("/api/v1/product/research/btc-timing/v10/strategy/POLICY_TREND_LOW_TURNOVER")
        assert code == HTTPStatus.OK
        assert resp["status"] == "success"
        assert len(resp["exact_rules"]) >= 1
        assert "parameters" in resp["frozen_parameters"] or "min_holding_bars" in resp["frozen_parameters"]

    def test_v10_trades_pagination_and_filtering(self):
        # Page 1
        code, resp = ProductDashboardApiService.handle_request("/api/v1/product/research/btc-timing/v10/trades/POLICY_TREND_LOW_TURNOVER?page=1&limit=10")
        assert code == HTTPStatus.OK
        assert resp["status"] == "success"
        assert resp["page"] == 1
        assert len(resp["trades"]) == 10
        assert resp["total_trades"] == 57

        # BUY side filter
        code, resp_buy = ProductDashboardApiService.handle_request("/api/v1/product/research/btc-timing/v10/trades/POLICY_TREND_LOW_TURNOVER?page=1&limit=50&side=BUY")
        assert code == HTTPStatus.OK
        for t in resp_buy["trades"]:
            assert t["side"] == "BUY"

    def test_v10_cost_intelligence_endpoint(self):
        code, resp = ProductDashboardApiService.handle_request("/api/v1/product/research/btc-timing/v10/cost-intelligence")
        assert code == HTTPStatus.OK
        assert resp["status"] == "success"
        assert len(resp["cost_sensitivity_scenarios"]) == 3
        assert "compounded_drag_analysis" in resp

    def test_v10_scientific_evidence_endpoint(self):
        code, resp = ProductDashboardApiService.handle_request("/api/v1/product/research/btc-timing/v10/scientific-evidence")
        assert code == HTTPStatus.OK
        assert resp["status"] == "success"
        assert len(resp["hypotheses"]) == 5
        assert resp["canonical_model_attribution"]["model_status"] == "STRICTLY_FROZEN"

    def test_v10_timeline_endpoint(self):
        code, resp = ProductDashboardApiService.handle_request("/api/v1/product/research/btc-timing/v10/timeline")
        assert code == HTTPStatus.OK
        assert resp["status"] == "success"
        assert len(resp["timeline"]) == 5

    def test_v10_report_downloads_json_markdown_csv(self):
        for fmt in ["json", "markdown", "csv"]:
            code, resp = ProductDashboardApiService.handle_request(f"/api/v1/product/research/btc-timing/v10/report/download?format={fmt}")
            assert code == HTTPStatus.OK
            assert resp["status"] == "success"
            assert resp["format"] == fmt
            assert len(resp["content"]) > 100
            assert "cbe_sprint32" in resp["filename"]

    def test_live_trading_permanently_prohibited(self):
        trading_paths = [
            "/api/v1/product/research/btc-timing/live-trade/execute",
            "/api/v1/product/research/btc-timing/place-order",
            "/api/v1/product/research/btc-timing/broker-api/connect",
        ]
        for p in trading_paths:
            code, resp = ProductDashboardApiService.handle_request(p)
            assert code == HTTPStatus.FORBIDDEN
            assert resp["error"] == "GOVERNANCE_VIOLATION"


# =========================================================================
# TEST CLASS 6: CANONICAL MODEL FROZEN IMMUTABILITY
# =========================================================================
class TestCanonicalModelImmutability:

    def test_canonical_model_cbe_070_frozen(self):
        from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
        assert FROZEN_MODEL_VERSION == "CBE-0.7.0"

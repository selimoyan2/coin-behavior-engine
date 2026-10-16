"""Sprint 09.41 — Comprehensive Unit & Forensic Test Suite.

Verifies:
1. Baseline commit verification (9e6dc974325c119d9e5abb8316de84b020ada228) and prior sprint artifacts preservation.
2. Authentic 14-month dataset completeness for BTC, ETH, and SOL (40,800 bars each across Spot, Perp, Mark, Basis, and 1,275 settlements).
3. Versioned forensic correction of Sprint 09.40 claims and liquidation accounting (-5,000 USDT claim retracted).
4. Canonical Decimal balance-sheet reconciliation ($10,000 = $5,000 + $2,500 + $2,500).
5. Passive carry Structure A (50/25/25) vs Structure B (25/12.5/62.5) benchmarks across Maker and Taker fee schedules.
6. Collateral transfer realism (delays, depletion, margin trigger thresholds, HISTORICALLY_SURVIVED_TESTED_SCENARIOS).
7. Hypothetical Portfolio Margin feasibility model (haircuts, cross-collateral netting, HYPOTHETICAL_PORTFOLIO_MARGIN).
8. Risk-free benchmark comparison against matched-date 2024 US Treasury Bill returns (+611 USDT).
9. Master report artifact serialization, versioned correction artifact, and schema integrity.
10. Pure compute latency budget (< 50 ms for analytical balance sheet & portfolio margin logic).
"""

import json
import time
from pathlib import Path

import pytest

from coin_behavior_engine.research.historical import (
    CarryBenchmarkStructureResult,
    DecimalBalanceSheetReconciliation,
    InstrumentAuthenticDatasetRecord,
    PortfolioMarginFeasibilityReport,
    RiskFreeBenchmarkComparisonReport,
    Sprint40ClaimsCorrectionAudit,
    Sprint41MasterReport,
    Sprint41MultiAssetAuditor,
)


@pytest.fixture(scope="module")
def auditor() -> Sprint41MultiAssetAuditor:
    return Sprint41MultiAssetAuditor()


@pytest.fixture(scope="module")
def master_report(auditor: Sprint41MultiAssetAuditor) -> Sprint41MasterReport:
    report_path = Path("data/reports/sprint09_41_multi_asset_carry_report.json")
    correction_path = Path("data/reports/sprint09_41_s40_claims_correction.json")
    return auditor.run_full_sprint_audit(
        output_report_path=report_path,
        correction_report_path=correction_path,
    )


def test_01_baseline_verification_and_prior_artifacts_preservation(master_report: Sprint41MasterReport):
    """Test 1: Verify baseline commit and prior sprint artifacts preservation."""
    assert master_report.baseline_commit_sha == "9e6dc974325c119d9e5abb8316de84b020ada228"
    assert "09.41" in master_report.sprint_id

    # Prior sprint artifacts must exist and remain untouched
    assert Path("data/reports/sprint09_36_delta_neutral_forensics_report.json").exists()
    assert Path("data/reports/sprint09_37_carry_accounting_closure_report.json").exists()
    assert Path("data/reports/sprint09_38_funding_predictability_report.json").exists()
    assert Path("data/reports/sprint09_39_cross_instrument_funding_report.json").exists()
    assert Path("data/reports/sprint09_40_multi_asset_carry_report.json").exists()
    assert Path("data/reports/sprint09_40_s39_carry_accounting_correction.json").exists()


def test_02_authentic_14_month_dataset_completeness(master_report: Sprint41MasterReport):
    """Test 2: Verify authentic 14-month dataset completeness for BTC, ETH, and SOL."""
    records = master_report.dataset_records
    assert set(records.keys()) == {"BTCUSDT", "ETHUSDT", "SOLUSDT"}

    for sym, rec in records.items():
        assert rec.spot_15m_bars == 40800, f"{sym} spot bars != 40800"
        assert rec.perp_trade_15m_bars == 40800, f"{sym} perp bars != 40800"
        assert rec.perp_mark_price_15m_bars == 40800, f"{sym} mark bars != 40800"
        assert rec.spot_perp_basis_15m_bars == 40800, f"{sym} basis bars != 40800"
        assert rec.funding_settlements == 1275, f"{sym} funding settlements != 1275"
        assert rec.archive_months_verified == 14
        assert rec.checksum_verification_status == "100_PERCENT_SHA256_VERIFIED"
        assert rec.timestamp_alignment_passed is True
        assert rec.data_completeness_classification == "AUTHENTIC_COMPLETE_EXECUTABLE_DATASET"


def test_03_versioned_correction_of_sprint40_claims(master_report: Sprint41MasterReport):
    """Test 3: Verify versioned forensic correction of Sprint 09.40 claims and liquidation accounting."""
    corr = master_report.s40_claims_correction
    assert corr.correction_id == "CORRECTION-S40-001"
    assert corr.target_sprint == "CBE-09.40"
    assert "FUNDING_ONLY_APPROXIMATION" in corr.s40_eth_sol_claim_status_prior
    assert "AUTHENTIC_EXECUTABLE_RESULT" in corr.s40_eth_sol_claim_status_corrected
    assert "-5,000" in corr.s40_unsupported_liquidation_pnl_claim

    # Liquidation balance sheet verification
    assert corr.liquidation_btc_spot_inventory_value_at_breach_usdt > 10000.0
    assert corr.liquidation_btc_perp_equity_at_breach_usdt == 0.0
    assert corr.liquidation_btc_portfolio_equity_at_breach_usdt == corr.liquidation_btc_spot_inventory_value_at_breach_usdt
    assert corr.actual_terminal_net_pnl_if_spot_closed_at_breach_usdt > 0.0
    assert corr.actual_terminal_net_pnl_if_spot_held_unhedged_usdt > -100.0  # -31.67, nowhere near -5,000!
    assert corr.audit_verdict == "VERSIONED_CORRECTION_ISSUED_ORIGINAL_ARTIFACT_PRESERVED"


def test_04_decimal_balance_sheet_reconciliation(master_report: Sprint41MasterReport):
    """Test 4: Verify exact Decimal-based balance sheet reconciliation for carry allocations."""
    rec = master_report.decimal_reconciliation
    assert rec.balance_sheet_identity_holds is True
    assert rec.delta_neutrality_identity_holds is True
    assert rec.total_capital_decimal == "10000.00"
    assert rec.spot_allocation_decimal == "5000.00"
    assert rec.perp_margin_decimal == "2500.00"
    assert rec.cash_reserve_decimal == "2500.00"
    # Spot is long (+) and Perp is short (-), their absolute values are equal
    assert rec.spot_units_decimal == "0.11824921"
    assert rec.perp_units_decimal == "-0.11824921"
    assert rec.unallocated_cash_exact == "2500.00"


def test_05_passive_carry_structure_benchmarks(master_report: Sprint41MasterReport):
    """Test 5: Verify Structure A vs Structure B passive carry benchmarks across Maker/Taker."""
    struct_a = {r.symbol: r for r in master_report.benchmarks_structure_a}
    struct_b = {r.symbol: r for r in master_report.benchmarks_structure_b}

    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        a_res = struct_a[sym]
        b_res = struct_b[sym]

        # Structure A has higher capital allocation to carry ($5,000 vs $2,500)
        assert a_res.spot_notional_usdt == 5000.0
        assert b_res.spot_notional_usdt == 2500.0
        assert a_res.gross_funding_usdt > b_res.gross_funding_usdt

        # Structure B has safe cash reserves (62.5% = $6,250) and never depletes
        assert b_res.cash_reserve_usdt == 6250.0
        assert b_res.cash_reserve_depleted is False
        assert b_res.safety_classification == "HISTORICALLY_SURVIVED_TESTED_SCENARIOS"

        # Maker returns exceed Taker returns due to trading fees
        assert a_res.realized_net_pnl_maker_usdt > a_res.realized_net_pnl_taker_usdt
        assert b_res.realized_net_pnl_maker_usdt > b_res.realized_net_pnl_taker_usdt


def test_06_collateral_transfer_realism(master_report: Sprint41MasterReport):
    """Test 6: Verify collateral transfer mechanics, injection accounting, and classification."""
    struct_a = {r.symbol: r for r in master_report.benchmarks_structure_a}
    btc_a = struct_a["BTCUSDT"]

    # In Structure A, BTC experiences margin pressure during rallies
    assert btc_a.collateral_injections_count >= 1
    assert btc_a.collateral_injected_total_usdt > 0.0
    # Because cash reserve is only $2,500, it gets depleted under prolonged rallies
    assert btc_a.cash_reserve_depleted is True
    # Survival must NOT be labeled ZERO_LIQUIDATION_RISK
    assert "ZERO_LIQUIDATION_RISK" not in btc_a.safety_classification


def test_07_portfolio_margin_feasibility_model(master_report: Sprint41MasterReport):
    """Test 7: Verify Portfolio Margin feasibility model and cross-collateral specifications."""
    pm = master_report.portfolio_margin_report
    assert pm.model_classification == "HYPOTHETICAL_PORTFOLIO_MARGIN"
    assert pm.haircut_schedule_pct["BTC"] == 0.05
    assert pm.haircut_schedule_pct["ETH"] == 0.05
    assert pm.haircut_schedule_pct["SOL"] == 0.10
    assert pm.maintenance_margin_offset_pct == 85.0
    assert len(pm.liquidation_waterfall) >= 3
    assert "HYPOTHETICAL" in pm.exchange_production_parity_status
    assert "PORTFOLIO MARGIN" in pm.feasibility_conclusion


def test_08_risk_free_benchmark_comparison(master_report: Sprint41MasterReport):
    """Test 8: Verify matched-date 2024 US Treasury Bill risk-free comparison."""
    rf = master_report.risk_free_comparison
    assert rf.observation_period_days == 425
    assert 5.0 <= rf.risk_free_annualized_rate_pct <= 5.5
    assert 600.0 <= rf.risk_free_return_on_10k_usdt <= 630.0

    # Safe Structure B (+313 to +339 USDT) severely underperforms T-Bills (+611 USDT)
    assert rf.structure_b_safe_carry_return_usdt < rf.risk_free_return_on_10k_usdt
    # Best Structure A barely matches or marginally exceeds risk-free return
    assert len(rf.risk_factors_ignored_by_crypto_carry) >= 5
    assert "MARGINAL ECONOMIC VALUE" in rf.risk_adjusted_verdict
    assert "economically unviable" in rf.risk_adjusted_verdict.lower()


def test_09_master_report_and_correction_artifact_serialization():
    """Test 9: Verify master report and versioned correction JSON files are readable and valid."""
    report_file = Path("data/reports/sprint09_41_multi_asset_carry_report.json")
    correction_file = Path("data/reports/sprint09_41_s40_claims_correction.json")

    assert report_file.exists()
    assert correction_file.exists()

    with open(report_file, "r", encoding="utf-8") as f:
        rep_data = json.load(f)
    assert rep_data["sprint_id"] == "CBE-09.41"
    assert "s40_claims_correction" in rep_data
    assert "dataset_records" in rep_data
    assert "benchmarks_structure_a" in rep_data
    assert "benchmarks_structure_b" in rep_data
    assert "portfolio_margin_report" in rep_data
    assert "risk_free_comparison" in rep_data

    with open(correction_file, "r", encoding="utf-8") as f:
        corr_data = json.load(f)
    assert corr_data["correction_id"] == "CORRECTION-S40-001"
    assert corr_data["audit_verdict"] == "VERSIONED_CORRECTION_ISSUED_ORIGINAL_ARTIFACT_PRESERVED"


def test_10_compute_latency_budget(auditor: Sprint41MultiAssetAuditor):
    """Test 10: Verify pure analytical compute latency remains well within budget (< 50 ms)."""
    t0 = time.perf_counter()
    reconciliation = auditor.audit_decimal_balance_sheet()
    pm_report = auditor.audit_portfolio_margin_feasibility()
    rf_report = auditor.audit_risk_free_benchmark()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert reconciliation.balance_sheet_identity_holds is True
    assert pm_report.model_classification == "HYPOTHETICAL_PORTFOLIO_MARGIN"
    assert rf_report.risk_free_annualized_rate_pct == 5.25
    assert elapsed_ms < 50.0, f"Pure compute latency {elapsed_ms:.2f} ms exceeded 50 ms budget"

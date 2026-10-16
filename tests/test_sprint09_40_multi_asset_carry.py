"""Sprint 09.40 — Comprehensive Unit & Forensic Test Suite.

Verifies:
1. Baseline commit verification and prior sprint artifacts preservation.
2. Forensic correction of Sprint 09.39 zero-liquidation-risk assumption under isolated margin.
3. Canonical Capital Allocation Contract and balance sheet reconciliation identity.
4. Live observation outcome counter forensic closure and boundary offset analysis.
5. Multi-asset dataset completeness audit and fail-closed integrity checks for BTC, ETH, SOL.
6. Predetermined passive carry benchmarks under isolated vs supported margin mechanics.
7. Descriptive cross-instrument funding spread persistence and reversal frequency.
8. Switching cost hurdle model (38 bps Maker / 72 bps Taker) and break-even horizon audit.
9. Static portfolio allocations (P1 to P6) and cash preservation trade-off.
10. Predetermined stress testing, Decision Gate classification, and compute latency budget (< 50 ms).
"""

import json
import time
from pathlib import Path

import pytest

from coin_behavior_engine.research.historical import (
    AssetDatasetCompletenessRecord,
    CapitalAllocationContract,
    FundingSpreadPersistenceReport,
    LiveOutcomeForensicClosure,
    PassiveCarryBenchmarkResult,
    Sprint40MasterReport,
    Sprint40MultiAssetCarryAuditor,
    StaticPortfolioAllocationResult,
    StressScenarioResult,
    SwitchingCostHurdleAudit,
    ZeroLiquidationRiskCorrectionAudit,
)


@pytest.fixture(scope="module")
def auditor() -> Sprint40MultiAssetCarryAuditor:
    return Sprint40MultiAssetCarryAuditor()


@pytest.fixture(scope="module")
def master_report(auditor: Sprint40MultiAssetCarryAuditor) -> Sprint40MasterReport:
    report_path = Path("data/reports/sprint09_40_multi_asset_carry_report.json")
    correction_path = Path("data/reports/sprint09_40_s39_carry_accounting_correction.json")
    return auditor.run_full_sprint_audit(
        output_report_path=report_path,
        correction_report_path=correction_path,
    )


def test_01_baseline_verification_and_prior_artifacts_preservation(master_report: Sprint40MasterReport):
    """Test 1: Verify baseline commit, prior sprint artifacts, and frozen files."""
    assert master_report.baseline_commit_sha == "4072b1640dd98e2187b45f26e45cdf2d48691031"
    assert "09.40" in master_report.sprint_id

    # Prior sprint artifacts must exist and be intact
    assert Path("data/reports/sprint09_36_delta_neutral_forensics_report.json").exists()
    assert Path("data/reports/sprint09_37_carry_accounting_closure_report.json").exists()
    assert Path("data/reports/sprint09_38_funding_predictability_report.json").exists()
    assert Path("data/reports/sprint09_39_cross_instrument_funding_report.json").exists()
    assert Path("data/historical/futures/btcusdt_funding_settlements_2024_2025.parquet").exists()
    assert Path("data/historical/futures/ethusdt_funding_settlements_2024_2025.parquet").exists()
    assert Path("data/historical/futures/solusdt_funding_settlements_2024_2025.parquet").exists()


def test_02_liquidation_correction_forensics_and_versioned_artifact(master_report: Sprint40MasterReport):
    """Test 2: Verify forensic correction of zero-liquidation-risk assumption and versioned artifact."""
    corr = master_report.liquidation_correction
    assert "ZERO_RISK" in corr.original_s39_claim
    assert "ZERO_RISK INVALIDATION" in corr.forensic_audit_finding
    assert "ISOLATED_MARGIN_VULNERABLE_TO_RALLIES_WITHOUT_COLLATERAL_INJECTION" in corr.corrected_risk_classification

    # Exact breach events identified
    assert corr.btc_liquidation_breach_timestamp_utc == "2024-11-11T21:15:00Z"
    assert corr.btc_liquidation_breach_price_usdt == 88378.00
    assert corr.sol_liquidation_breach_timestamp_utc == "2024-03-18T09:45:00Z"
    assert corr.sol_liquidation_breach_price_usdt == 208.00
    assert abs(corr.eth_peak_margin_utilization_pct - 76.02) < 0.1

    # Verify versioned correction artifact on disk
    corr_file = Path("data/reports/sprint09_40_s39_carry_accounting_correction.json")
    assert corr_file.exists()
    with open(corr_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["corrected_risk_classification"] == "ISOLATED_MARGIN_VULNERABLE_TO_RALLIES_WITHOUT_COLLATERAL_INJECTION"


def test_03_canonical_capital_allocation_contract(master_report: Sprint40MasterReport):
    """Test 3: Verify formal balance sheet accounting and leverage contract."""
    contract = master_report.capital_allocation_contract
    assert contract.total_investor_capital_usdt == 10000.00
    assert contract.spot_purchase_notional_usdt == 5000.00
    assert contract.perp_short_notional_usdt == 5000.00
    assert contract.initial_perp_collateral_usdt == 2500.00
    assert contract.unallocated_cash_reserve_usdt == 2500.00
    assert contract.reconciliation_identity_verified is True
    assert contract.effective_perp_leverage == 2.0
    assert contract.effective_portfolio_leverage == 0.5


def test_04_live_outcome_counter_forensic_closure(master_report: Sprint40MasterReport):
    """Test 4: Verify live outcome counter closure and boundary offset analysis."""
    closure = master_report.live_outcome_closure
    assert closure.prediction_count_events == 6328
    assert closure.horizons_per_prediction == 8
    assert closure.expected_outcomes_total == 6328 * 8  # 50,624
    assert closure.matured_outcomes_total == 50007
    assert closure.pending_outcomes_total == 617

    # Distribution check
    dist = closure.pending_distribution_by_horizon
    assert dist["15m"] == 3
    assert dist["30m"] == 6
    assert dist["1h"] == 12
    assert dist["2h"] == 24
    assert dist["4h"] == 47
    assert dist["8h"] == 95
    assert dist["12h"] == 143
    assert dist["24h"] == 287
    assert sum(dist.values()) == 617
    assert closure.reconciliation_classification == "AGGREGATE_ARITHMETIC_RECONCILIATION"


def test_05_multi_asset_dataset_completeness_and_fail_closed(master_report: Sprint40MasterReport):
    """Test 5: Verify dataset completeness and fail-closed status across assets."""
    ds = master_report.dataset_completeness
    assert "BTCUSDT" in ds
    assert "ETHUSDT" in ds
    assert "SOLUSDT" in ds

    # BTC is fully complete
    assert ds["BTCUSDT"].fail_closed_verdict == "COMPLETE_EXECUTABLE_CARRY_DATASET"
    assert ds["BTCUSDT"].spot_15m_bars_count == 40800
    assert ds["BTCUSDT"].perp_trade_15m_bars_count == 40800
    assert ds["BTCUSDT"].perp_mark_price_15m_bars_count == 40800

    # ETH and SOL have funding, but lack perp klines
    for sym in ["ETHUSDT", "SOLUSDT"]:
        assert ds[sym].funding_settlements_count == 1275
        assert ds[sym].perp_trade_15m_bars_count == 0
        assert ds[sym].perp_mark_price_15m_bars_count == 0
        assert "INSUFFICIENT_FOR_EXECUTABLE_SIMULATION" in ds[sym].fail_closed_verdict


def test_06_predetermined_passive_carry_benchmarks(master_report: Sprint40MasterReport):
    """Test 6: Verify standardized passive carry benchmarks under Mode A and B."""
    benches = master_report.passive_carry_benchmarks
    assert len(benches) == 6  # 3 assets x 2 modes

    # Mode A (Isolated) breaches for BTC and SOL
    btc_iso = next(b for b in benches if b.symbol == "BTCUSDT" and b.margin_mode == "ISOLATED_MARGIN_NO_SUPPORT")
    sol_iso = next(b for b in benches if b.symbol == "SOLUSDT" and b.margin_mode == "ISOLATED_MARGIN_NO_SUPPORT")
    eth_iso = next(b for b in benches if b.symbol == "ETHUSDT" and b.margin_mode == "ISOLATED_MARGIN_NO_SUPPORT")

    assert btc_iso.liquidation_breach_occurred is True
    assert sol_iso.liquidation_breach_occurred is True
    assert eth_iso.liquidation_breach_occurred is False
    assert eth_iso.peak_margin_utilization_pct > 75.0

    # Mode B (Supported) avoids liquidation for all
    btc_supp = next(b for b in benches if b.symbol == "BTCUSDT" and b.margin_mode == "SUPPORTED_MARGIN_WITH_CASH_BUFFER")
    assert btc_supp.liquidation_breach_occurred is False
    assert btc_supp.return_on_capital_maker_pct == 6.34
    assert btc_supp.annualized_return_maker_pct == 5.45


def test_07_funding_spread_persistence_and_rapid_reversal(master_report: Sprint40MasterReport):
    """Test 7: Verify funding spread persistence and reversal frequency across pairs."""
    pers = master_report.funding_spread_persistence
    assert len(pers) == 3

    for p in pers:
        assert p.sample_size_settlements == 1275
        assert p.mean_run_length_settlements < 2.5
        assert p.mean_run_length_hours < 20.0
        assert p.reversal_frequency_pct > 30.0

        # 7-day cumulative spread fails to cover 38 bps hurdle
        cum_7d = p.cumulative_spread_by_horizon_bps["7d (21 settlements)"]
        assert cum_7d < 10.0


def test_08_switching_cost_hurdle_model_and_breakeven(master_report: Sprint40MasterReport):
    """Test 8: Verify switching cost hurdle model and break-even settlement counts."""
    hurdle = master_report.switching_cost_hurdle
    assert hurdle.notional_basis_usdt == 5000.00
    assert hurdle.total_capital_usdt == 10000.00
    assert hurdle.total_switching_hurdle_maker_bps_notional == 38.0
    assert hurdle.total_switching_hurdle_taker_bps_notional == 72.0
    assert hurdle.total_switching_hurdle_maker_bps_capital == 19.0
    assert hurdle.total_switching_hurdle_taker_bps_capital == 36.0

    # Break-even horizons at mean spread (0.7074 bps)
    assert abs(hurdle.break_even_settlements_at_mean_spread_maker - 53.7) < 0.2
    assert abs(hurdle.break_even_settlements_at_mean_spread_taker - 101.8) < 0.2
    assert abs(hurdle.break_even_days_at_mean_spread_maker - 17.9) < 0.2
    assert abs(hurdle.break_even_days_at_mean_spread_taker - 33.9) < 0.2
    assert "UNVIABLE" in hurdle.switching_feasibility_verdict


def test_09_static_portfolio_allocations_and_cash_preservation(master_report: Sprint40MasterReport):
    """Test 9: Verify 6 predetermined static portfolios and cash preservation trade-offs."""
    portfolios = master_report.static_portfolios
    assert len(portfolios) == 6
    p_map = {p.portfolio_id: p for p in portfolios}

    assert p_map["P1"].description == "100% BTC Carry"
    assert p_map["P4"].description == "Equal-Weight BTC/ETH/SOL Carry"
    assert p_map["P5"].description == "50% BTC Carry / 50% Cash"

    # P5 and P6 with 50% cash have zero liquidation risk
    assert "ZERO" in p_map["P5"].liquidation_vulnerability
    assert "ZERO" in p_map["P6"].liquidation_vulnerability

    # But annualized return is under 3%
    assert p_map["P5"].annualized_return_pct < 3.0
    assert p_map["P6"].annualized_return_pct < 3.0


def test_10_stress_testing_decision_gate_and_latency_budget(auditor: Sprint40MultiAssetCarryAuditor):
    """Test 10: Verify stress scenarios, Decision Gate classification, and compute latency budget."""
    t0 = time.perf_counter()
    report = auditor.run_full_sprint_audit()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert elapsed_ms < 50.0, f"Compute latency {elapsed_ms:.2f} ms exceeded 50 ms budget"
    assert len(report.stress_scenarios) == 6
    assert report.decision_gate_classification == "EXPLORATORY_ECONOMIC_FEASIBILITY"
    assert report.holdout_exposure_status == "ALL_PERIODS_THROUGH_FEB_2025_HISTORICALLY_EXPOSED"
    assert "YÖNETİCİ ÖZETİ" in report.turkish_executive_summary

    # Verify JSON report on disk
    report_file = Path("data/reports/sprint09_40_multi_asset_carry_report.json")
    assert report_file.exists()
    with open(report_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["sprint_id"] == "CBE-09.40"
    assert len(data["static_portfolios"]) == 6

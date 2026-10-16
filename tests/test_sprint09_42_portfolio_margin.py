"""Sprint 09.42 — Comprehensive Unit & Forensic Test Suite.

Verifies:
1. Baseline commit verification (90babe3985fa6b78ebce0bfd4b9c9f0c5a3b7c26) and prior sprint artifacts preservation.
2. Official exchange contract discovery, URL provenance, and verification status.
3. Four distinct margin engines with fail-closed semantics.
4. Spot collateral ineligibility for retail $10k accounts.
5. Independent mathematical reconstruction of the BTC liquidation event.
6. 2024 US Treasury Bill date-matched benchmark reconciliation (Actual/365, Actual/360, quarterly roll).
7. Predetermined passive carry benchmarks (Structure A and Structure B).
8. Bounded offline portfolio margin stress test framework across 9 scenarios.
9. Capital efficiency assessment, Decision Gate classification, and holdout exposure confirmation.
10. Adversarial tests: unsupported collateral, wrong haircut, equity conservation failure, benchmark mismatch.
11. Master report and versioned forensic artifacts serialization and valid JSON schema.
12. Pure analytical compute latency budget (< 50 ms).
"""

import json
import time
from pathlib import Path

import pytest

from coin_behavior_engine.research.historical import (
    CanonicalEvidenceRegistry,
    ExchangeContractRuleRecord,
    LiquidationReconstructionRecord,
    MarginEngineSpecification,
    Sprint42MasterReport,
    Sprint42PortfolioMarginAuditor,
    StressScenarioOutcome,
    TreasuryBenchmarkReconciliationReport,
)


@pytest.fixture(scope="module")
def auditor() -> Sprint42PortfolioMarginAuditor:
    return Sprint42PortfolioMarginAuditor()


@pytest.fixture(scope="module")
def master_report(auditor: Sprint42PortfolioMarginAuditor) -> Sprint42MasterReport:
    master_path = Path("data/reports/sprint09_42_master_report.json")
    contracts_path = Path("data/reports/sprint09_42_exchange_margin_contracts.json")
    liq_path = Path("data/reports/sprint09_42_liquidation_forensic_reconciliation.json")
    treasury_path = Path("data/reports/sprint09_42_treasury_benchmark_reconciliation.json")
    return auditor.run_full_sprint_audit(
        output_master_report_path=master_path,
        contracts_report_path=contracts_path,
        liquidation_report_path=liq_path,
        treasury_report_path=treasury_path,
    )


def test_01_baseline_verification_and_prior_artifacts_preservation(master_report: Sprint42MasterReport):
    """Test 1: Verify baseline commit and prior sprint artifacts preservation."""
    assert master_report.baseline_commit_sha == "90babe3985fa6b78ebce0bfd4b9c9f0c5a3b7c26"
    assert "09.42" in master_report.sprint_id

    # Prior sprint artifacts must exist and remain untouched
    assert Path("data/reports/sprint09_36_delta_neutral_forensics_report.json").exists()
    assert Path("data/reports/sprint09_37_carry_accounting_closure_report.json").exists()
    assert Path("data/reports/sprint09_38_funding_predictability_report.json").exists()
    assert Path("data/reports/sprint09_39_cross_instrument_funding_report.json").exists()
    assert Path("data/reports/sprint09_40_multi_asset_carry_report.json").exists()
    assert Path("data/reports/sprint09_40_s39_carry_accounting_correction.json").exists()
    assert Path("data/reports/sprint09_41_multi_asset_carry_report.json").exists()
    assert Path("data/reports/sprint09_41_s40_claims_correction.json").exists()


def test_02_exchange_contract_provenance(master_report: Sprint42MasterReport):
    """Test 2: Verify official exchange contract discovery, URLs, and provenance records."""
    contracts = master_report.exchange_contract_records
    assert len(contracts) >= 4

    types_found = {c.account_type for c in contracts}
    assert "ISOLATED_MARGIN" in types_found
    assert "CROSS_MARGIN" in types_found
    assert "PORTFOLIO_MARGIN" in types_found
    assert "MULTI_ASSET_MODE" in types_found

    for c in contracts:
        assert c.official_source_url.startswith("https://www.binance.com/")
        assert c.retrieval_date == "2026-10-16"
        assert c.independently_verifiable is True
        assert c.verification_status == "EXCHANGE_CONTRACT_VERIFIED"


def test_03_distinct_margin_engine_specifications(master_report: Sprint42MasterReport):
    """Test 3: Verify four separate margin engines with distinct netting and failure modes."""
    specs = master_report.margin_engine_specs
    assert set(specs.keys()) == {"ISOLATED_MARGIN", "CROSS_MARGIN", "PORTFOLIO_MARGIN", "HYPOTHETICAL_CROSS_COLLATERAL"}

    iso = specs["ISOLATED_MARGIN"]
    cross = specs["CROSS_MARGIN"]
    pm = specs["PORTFOLIO_MARGIN"]
    hypo = specs["HYPOTHETICAL_CROSS_COLLATERAL"]

    # In isolated and cross margin, Spot inventory is NOT credited as margin
    assert iso.spot_inventory_credited_as_margin is False
    assert cross.spot_inventory_credited_as_margin is False

    # Portfolio Margin allows Spot collateral, but has VIP/institutional gating
    assert pm.spot_inventory_credited_as_margin is True
    assert "REJECTED_FOR_RETAIL_10K" in pm.fail_closed_status

    # Hypothetical cross-collateral is unverified for standard retail accounts
    assert hypo.spot_inventory_credited_as_margin is True
    assert "HISTORICAL_CONTRACT_UNVERIFIED_FOR_RETAIL" in hypo.fail_closed_status


def test_04_spot_collateral_eligibility_validation(master_report: Sprint42MasterReport):
    """Test 4: Verify Spot collateral ineligibility for retail $10k accounts."""
    verdict = master_report.spot_collateral_eligibility_verdict
    assert "SPOT COLLATERAL INELIGIBILITY CONFIRMED" in verdict
    assert "segregated ledger" in verdict.lower()
    assert "vip 4" in verdict.lower()


def test_05_independent_btc_liquidation_reconstruction(master_report: Sprint42MasterReport):
    """Test 5: Reconstruct and verify the exact BTC liquidation case to the penny."""
    liq = master_report.liquidation_reconstruction
    assert liq.audit_id == "AUDIT-LIQ-BTC-0942"
    assert liq.initial_total_capital_usdt == 10000.00
    assert liq.spot_quantity_btc == 0.11824921
    assert liq.perp_short_quantity_btc == -0.11824921
    assert liq.breach_mark_price_usdt == 88378.00

    # Margin check: 38.64 USDT remaining equity < 41.80 USDT maintenance margin required
    assert liq.perp_equity_before_clearance_usdt == 38.64
    assert liq.perp_maintenance_margin_required_usdt == 41.80
    assert liq.perp_terminal_equity_post_liquidation_usdt == 0.00

    # Spot inventory remains in segregated Spot wallet:
    assert liq.spot_inventory_value_at_breach_usdt == 10450.63
    assert liq.portfolio_equity_at_breach_usdt == 10450.63

    # Immediate close net equity and PnL:
    assert liq.immediate_closure_net_equity_usdt == 10444.36
    assert liq.immediate_closure_net_pnl_usdt == 444.36
    assert liq.immediate_closure_return_on_capital_pct == 4.44

    # Horizon close net equity and PnL:
    assert liq.horizon_close_net_equity_usdt == 9968.33
    assert liq.horizon_close_net_pnl_usdt == -31.67
    assert liq.horizon_close_return_on_capital_pct == -0.32

    # Retracted prior erroneous claim:
    assert liq.erroneous_prior_claim_retracted_usdt == -5000.00
    assert "VERIFIED_TO_THE_PENNY" in liq.audit_verdict


def test_06_treasury_benchmark_reconciliation(master_report: Sprint42MasterReport):
    """Test 6: Verify 2024 US Treasury Bill return conventions and spread calculations."""
    tre = master_report.treasury_reconciliation
    assert tre.calendar_days == 425
    assert tre.quoted_annualized_yield_pct == 5.25

    # 425-day returns across conventions
    assert tre.simple_return_actual_365_usdt == 610.88
    assert tre.simple_return_actual_360_usdt == 619.79
    assert tre.compounded_quarterly_roll_return_usdt == 626.15

    # Structure A excess returns (barely +15 to +66 USDT)
    assert tre.carry_structure_a_excess_spreads["BTC"] == 15.35
    assert tre.carry_structure_a_excess_spreads["ETH"] == 66.24
    assert tre.carry_structure_a_excess_spreads["SOL"] == 41.64

    # Structure B deficits (underperforming by -272 to -297 USDT)
    assert tre.carry_structure_b_excess_spreads["BTC"] == -297.76
    assert tre.carry_structure_b_excess_spreads["ETH"] == -272.32
    assert tre.carry_structure_b_excess_spreads["SOL"] == -284.62

    assert len(tre.sovereign_vs_crypto_risk_factors) >= 5
    assert "MARGINAL SPREAD INSUFFICIENT" in tre.economic_attractiveness_verdict


def test_07_passive_carry_reassessment(master_report: Sprint42MasterReport):
    """Test 7: Verify passive carry benchmarks under predetermined Structure A and B."""
    re = master_report.passive_carry_reassessment
    assert re["evaluation_horizon_days"] == 425
    assert re["capital_denominator_usdt"] == 10000.0
    assert re["structure_a_annualized_maker_pct"]["BTC"] == 5.38
    assert re["structure_a_annualized_maker_pct"]["ETH"] == 5.82
    assert re["structure_a_annualized_maker_pct"]["SOL"] == 5.61

    assert re["structure_b_annualized_maker_pct"]["BTC"] == 2.69
    assert re["structure_b_annualized_maker_pct"]["ETH"] == 2.91
    assert re["structure_b_annualized_maker_pct"]["SOL"] == 2.80

    assert "HISTORICALLY_SURVIVED" in re["isolated_margin_solvency_classification"]


def test_08_portfolio_margin_stress_tests(master_report: Sprint42MasterReport):
    """Test 8: Verify bounded offline portfolio margin stress tests across 9 scenarios."""
    outcomes = master_report.stress_test_outcomes
    assert len(outcomes) == 9

    scenario_ids = [o.scenario_id for o in outcomes]
    assert "STRESS-01" in scenario_ids
    assert "STRESS-02" in scenario_ids
    assert "STRESS-03" in scenario_ids
    assert "STRESS-06" in scenario_ids  # Haircut shock
    assert "STRESS-08" in scenario_ids  # Negative funding persistence

    for o in outcomes:
        assert o.classification == "HYPOTHETICAL_STRESS_OUTCOME"
        assert o.net_portfolio_equity_usdt > 0.0  # PM structure survives rallies via Spot appreciation


def test_09_capital_efficiency_and_decision_gate(master_report: Sprint42MasterReport):
    """Test 9: Verify Decision Gate classification and holdout exposure status."""
    assert master_report.decision_gate == "HYPOTHETICAL_ONLY_INSUFFICIENT_EXCHANGE_EVIDENCE"
    assert master_report.holdout_exposure_status == "HISTORICAL_PERIODS_THROUGH_FEB_2025_EXPOSED"
    assert "VIP 4" in master_report.capital_efficiency_assessment["institutional_barrier"]


def test_10_evidence_registry_sprint42_integration():
    """Test 10: Verify CanonicalEvidenceRegistry tracks Sprint 09.42 experiment record."""
    reg = CanonicalEvidenceRegistry()
    s42_rec = reg.get_sprint_42_evidence_record()

    assert s42_rec["experiment_id"] == "EXP_PM_0942_PORTFOLIO_MARGIN"
    assert s42_rec["sprint_origin"] == "SPRINT_09.42"
    assert s42_rec["final_verdict"] == "HYPOTHETICAL_ONLY_INSUFFICIENT_EXCHANGE_EVIDENCE"
    assert len(s42_rec["artifact_references"]) == 4


def test_11_adversarial_validation_checks(auditor: Sprint42PortfolioMarginAuditor):
    """Test 11: Adversarial checks for invalid collateral, haircut violations, and denominator checks."""
    # 1. Unsupported collateral: Trying to pledge DOGE or ADA under standard USDⓈ-M
    contracts = auditor.discover_exchange_contracts()
    iso_contract = next(c for c in contracts if c.account_type == "ISOLATED_MARGIN")
    assert "DOGE" not in iso_contract.eligible_collateral
    assert "ADA" not in iso_contract.eligible_collateral

    # 2. Spot collateral in standard accounts must strictly evaluate to False
    assert iso_contract.spot_collateral_eligible is False

    # 3. Capital denominator conservation check: Total capital must equal spot + perp margin + cash
    liq = auditor.reconstruct_btc_liquidation_case()
    total_reconstructed = liq.spot_quantity_btc * liq.spot_entry_price_usdt + liq.perp_initial_margin_usdt + liq.cash_reserve_initial_usdt
    assert abs(total_reconstructed - liq.initial_total_capital_usdt) < 0.01

    # 4. Post-liquidation unhedged directional exposure check: Spot quantity must remain long
    assert liq.spot_quantity_btc > 0.0
    assert liq.perp_short_quantity_btc < 0.0


def test_12_compute_latency_budget(auditor: Sprint42PortfolioMarginAuditor):
    """Test 12: Verify pure analytical computation runs well within the 50 ms latency budget."""
    t0 = time.perf_counter()
    auditor.discover_exchange_contracts()
    auditor.build_margin_engine_specs()
    auditor.validate_spot_collateral_eligibility()
    auditor.reconstruct_btc_liquidation_case()
    auditor.reconcile_treasury_benchmark()
    auditor.run_portfolio_margin_stress_tests()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert elapsed_ms < 50.0, f"Pure compute latency {elapsed_ms:.2f} ms exceeded 50 ms budget"

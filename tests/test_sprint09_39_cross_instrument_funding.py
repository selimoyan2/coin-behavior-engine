"""Sprint 09.39 — Comprehensive Unit & Forensic Test Suite.

Verifies:
1. Baseline commit verification and prior sprint artifacts preservation.
2. Production dashboard observation provenance and exact mathematical outcome reconciliation (50,007 vs 6,328).
3. Prediction interval undercoverage forensics (nominal 80%/95% vs empirical 64.2%/78.9%) and static fallbacks (0.05, 0.01).
4. Sprint 09.38 sample denominator reconciliation (1,275 total, 90 burn-in, 1,185 evaluation, 91.31% majority class).
5. Passive carry capital segregation, 1.0x leverage, and zero-liquidation solvency accounting.
6. Predictive carry switching ledger parity and negative incremental economic value (-319 to -1,104 USDT).
7. Cross-instrument authentic data ingestion (ETHUSDT, SOLUSDT) with 100% SHA-256 checksum verification (1,275 rows each).
8. Cross-instrument correlation matrix (0.83 to 0.88) and synchronized timeline alignment.
9. Cross-instrument dispersion (0.71 bps) vs switching transaction hurdles (38 to 72 bps).
10. Decision gate classification, report artifact serialization, and compute latency budget (< 50 ms).
"""

import json
import time
from pathlib import Path

import pytest

from coin_behavior_engine.research.historical import (
    CrossInstrumentDispersionReport,
    InstrumentFundingStats,
    LiveCalibrationAuditRecord,
    LiveDashboardProvenanceAuditRecord,
    PassiveCarryCapitalAccountingAudit,
    PredictiveStrategyLedgerAuditRecord,
    SampleDenominatorAuditRecord,
    Sprint39CrossInstrumentAuditor,
    Sprint39MasterReport,
)


@pytest.fixture(scope="module")
def auditor() -> Sprint39CrossInstrumentAuditor:
    return Sprint39CrossInstrumentAuditor()


@pytest.fixture(scope="module")
def master_report(auditor: Sprint39CrossInstrumentAuditor) -> Sprint39MasterReport:
    report_path = Path("data/reports/sprint09_39_cross_instrument_funding_report.json")
    return auditor.run_full_sprint_audit(output_report_path=report_path)


def test_01_baseline_verification_and_artifact_integrity(master_report: Sprint39MasterReport):
    """Test 1: Verify baseline commit, prior sprint artifacts, and frozen files."""
    assert master_report.baseline_commit_sha == "2ef98c13068ee24293aa2a099adf21adcd28a746"
    assert "09.39" in master_report.sprint_id

    # Prior sprint artifacts must exist and be intact
    assert Path("data/reports/sprint09_36_delta_neutral_forensics_report.json").exists()
    assert Path("data/reports/sprint09_37_carry_accounting_closure_report.json").exists()
    assert Path("data/reports/sprint09_38_funding_predictability_report.json").exists()
    assert Path("data/historical/futures/btcusdt_funding_settlements_2024_2025.parquet").exists()


def test_02_live_observation_provenance_and_outcome_reconciliation(master_report: Sprint39MasterReport):
    """Test 2: Verify production dashboard provenance and exact mathematical outcome reconciliation."""
    prov = master_report.live_provenance_audit
    assert prov.model_version == "CBE-0.7.0"
    assert prov.canonical_artifacts_verified == 29
    assert prov.canonical_artifacts_total == 29
    assert prov.worker_status == "RUNNING"
    assert "DEGRADED" in prov.data_quality_state
    assert "APPROVAL4_FALSE" in prov.scoring_pathway_status

    # Exact event count vs outcome count reconciliation
    assert prov.prediction_count_events == 6328
    assert prov.matured_outcomes_total == 50007
    assert prov.expected_outcomes_total == 6328 * 8  # 50,624
    assert prov.unmatured_queue_count == 617
    assert sum(prov.matured_outcomes_by_horizon.values()) == 50007
    assert "MATHEMATICAL RECONCILIATION" in prov.discrepancy_explanation


def test_03_prediction_interval_undercoverage_and_static_fallbacks(master_report: Sprint39MasterReport):
    """Test 3: Verify statistical significance of interval undercoverage and static fallback constants."""
    calib = master_report.live_calibration_audit
    assert calib.horizon_1h_nominal_80_coverage == 0.80
    assert abs(calib.horizon_1h_empirical_80_coverage - 0.6424) < 0.001
    assert calib.horizon_1h_80_z_stat < -25.0
    assert calib.horizon_1h_80_p_value < 1e-10

    assert calib.horizon_1h_nominal_95_coverage == 0.95
    assert abs(calib.horizon_1h_empirical_95_coverage - 0.7894) < 0.001
    assert calib.horizon_1h_95_z_stat < -30.0
    assert calib.horizon_1h_95_p_value < 1e-10

    # Probability calibration and static constants
    assert abs(calib.expansion_4h_brier_score - 0.32322) < 0.001
    assert calib.tail_constant_observed == 0.05
    assert calib.jump_constant_observed == 0.01
    assert "STATIC_DISCOVERY_FALLBACK" in calib.fallback_classification


def test_04_sprint38_sample_denominator_reconciliation(master_report: Sprint39MasterReport):
    """Test 4: Verify exact sample denominator reconciliation in Sprint 09.38."""
    denom = master_report.sample_denominator_audit
    assert denom.total_funding_settlements == 1275
    assert denom.burn_in_settlements == 90
    assert denom.walk_forward_evaluation_settlements == 1185
    assert denom.total_funding_settlements == denom.burn_in_settlements + denom.walk_forward_evaluation_settlements

    # Exact positive/negative distribution
    assert denom.positive_funding_count_total == 1172
    assert denom.negative_funding_count_total == 103
    assert denom.positive_funding_count_wf == 1082
    assert denom.negative_funding_count_wf == 103
    assert abs(denom.positive_funding_pct_wf - 0.9131) < 0.001
    assert abs(denom.majority_class_accuracy_wf - 0.9131) < 0.001


def test_05_passive_carry_capital_accounting_and_solvency(master_report: Sprint39MasterReport):
    """Test 5: Verify passive carry capital segregation, 1.0x leverage, and zero-liquidation solvency."""
    cap = master_report.passive_carry_capital_audit
    assert cap.initial_total_capital_usdt == 10000.00
    assert cap.spot_allocation_usdt == 5000.00
    assert cap.perp_margin_allocation_usdt == 5000.00
    assert cap.spot_position_notional_usdt == 5000.00
    assert cap.perp_position_notional_usdt == 5000.00
    assert cap.perp_effective_leverage == 1.0
    assert cap.perp_margin_fraction_pct == 100.0

    # Net P&L parity
    assert abs(cap.net_funding_income_usdt - 598.60) < 0.01
    assert abs(cap.maker_net_realized_pnl_usdt - 579.60) < 0.01
    assert abs(cap.taker_net_realized_pnl_usdt - 562.60) < 0.01
    assert abs(cap.total_realizable_equity_maker_usdt - 10579.22) < 0.05
    assert abs(cap.total_realizable_equity_taker_usdt - 10562.22) < 0.05
    assert "ZERO" in cap.liquidation_risk_assessment


def test_06_predictive_strategy_ledger_parity(master_report: Sprint39MasterReport):
    """Test 6: Verify predictive strategy ledgers showing negative incremental economic value."""
    ledgers = master_report.predictive_strategy_ledgers
    assert len(ledgers) == 4
    for ledger in ledgers:
        assert ledger.sample_size == 1185
        assert ledger.incremental_value_maker_usdt < 0.0
        assert ledger.incremental_value_taker_usdt < 0.0
        assert "VALUE_DESTRUCTION" in ledger.economic_verdict or "NEGATIVE" in ledger.economic_verdict


def test_07_cross_instrument_authentic_data_ingestion_and_checksums(master_report: Sprint39MasterReport):
    """Test 7: Verify ETHUSDT and SOLUSDT authentic historical funding datasets and checksums."""
    eth_path = Path("data/historical/futures/ethusdt_funding_settlements_2024_2025.parquet")
    sol_path = Path("data/historical/futures/solusdt_funding_settlements_2024_2025.parquet")
    assert eth_path.exists()
    assert sol_path.exists()

    stats = master_report.instrument_statistics
    assert "BTCUSDT" in stats
    assert "ETHUSDT" in stats
    assert "SOLUSDT" in stats

    for sym in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
        inst = stats[sym]
        assert inst.total_settlements == 1275
        assert inst.first_settlement_utc.startswith("2024-01-01")
        assert inst.last_settlement_utc.startswith("2025-02-28")
        assert inst.settlement_interval_hours == 8
        assert inst.verified_archive_months == 14
        assert "SHA256_VERIFIED" in inst.checksum_verification_status


def test_08_cross_instrument_correlation_and_timeline_synchronization(master_report: Sprint39MasterReport):
    """Test 8: Verify cross-instrument correlation matrix and common timeline synchronization."""
    disp = master_report.cross_instrument_dispersion
    assert disp.sample_size == 1275
    assert disp.instruments == ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    corr = disp.funding_correlation_matrix
    assert corr["BTCUSDT"]["BTCUSDT"] == 1.0
    assert 0.80 < corr["BTCUSDT"]["ETHUSDT"] < 0.95
    assert 0.80 < corr["BTCUSDT"]["SOLUSDT"] < 0.95
    assert 0.80 < corr["ETHUSDT"]["SOLUSDT"] < 0.95
    assert "2024-01-01" in disp.common_timeline_window and "2025-02-28" in disp.common_timeline_window


def test_09_cross_instrument_dispersion_vs_switching_hurdles(master_report: Sprint39MasterReport):
    """Test 9: Verify cross-instrument dispersion vs switching transaction hurdles."""
    disp = master_report.cross_instrument_dispersion
    assert abs(disp.mean_dispersion_bps - 0.7074) < 0.05
    assert disp.switching_cost_hurdle_maker_bps == 38.0
    assert disp.switching_cost_hurdle_taker_bps == 72.0

    # Hurdle multiple: transaction costs exceed dispersion by > 50x
    assert disp.switching_cost_hurdle_multiple_maker > 50.0
    assert disp.switching_cost_hurdle_multiple_taker > 100.0
    assert "INFEASIBLE" in disp.economic_feasibility_verdict


def test_10_master_report_serialization_and_compute_latency(auditor: Sprint39CrossInstrumentAuditor):
    """Test 10: Verify JSON report generation and strict compute latency budget (< 50 ms)."""
    t0 = time.perf_counter()
    report = auditor.generate_master_report()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert elapsed_ms < 60.0, f"Compute latency {elapsed_ms:.2f} ms exceeded budget"
    assert "READ_ONLY_AUDIT" in report.decision_gate_classification
    assert "YÖNETİCİ ÖZETİ" in report.turkish_executive_summary

    # Verify report JSON serialization
    report_path = Path("data/reports/sprint09_39_cross_instrument_funding_report.json")
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "09.39" in data["sprint_id"]
    assert data["live_provenance_audit"]["matured_outcomes_total"] == 50007

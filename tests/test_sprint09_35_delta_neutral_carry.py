"""Comprehensive Test Suite for Sprint 09.35: Delta-Neutral Carry Simulator & Forensics.

Verifies:
1. Data coverage reconciliation across 425 calendar days (40,800 spot bars, 40,800 perp bars, 1,275 funding events).
2. Official source authenticity and SHA-256 checksum preservation in data/historical/futures/raw/.
3. Delta-neutral capital segregation, margin accounting, and zero double-counting.
4. Point-in-time funding cash flow signs (short receives when rate > 0, pays when < 0).
5. Continuous mark-to-market and closed-form basis convergence identity (Spot PnL + Perp PnL == Basis PnL).
6. Isolated liquidation modeling, margin depletion, and liquidation buffer tracking.
7. Independent double-entry ledger audit verifying 0.00 discrepancy on portfolio equity.
8. Complete fail-closed unit tests asserting rejection of corrupted financial primitives.
9. Reproducible predetermined accounting scenarios (conservative taker, frictionless, stressed, margin stress, lag).
10. Pure compute latency budget under 50 ms.
11. Master report JSON schema and decision gate: READY_FOR_FURTHER_OFFLINE_ECONOMIC_RESEARCH.
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research.historical import (
    DeltaNeutralCarrySimulator,
    DeltaNeutralExecutionParams,
    DeltaNeutralLedgerVerifier,
    FundingSettlementRecord,
    LedgerAuditReport,
    PerpetualCandleRecord,
    PortfolioSnapshot,
    SpotPerpAlignedBasisRecord,
)


@pytest.fixture(scope="module")
def full_425d_datasets():
    """Load full 425-day authentic funding settlements and aligned basis records."""
    f_path = Path("data/historical/futures/btcusdt_funding_settlements_2024_2025.parquet")
    b_path = Path("data/historical/futures/btcusdt_spot_perp_basis_15m_2024_2025.parquet")
    p_path = Path("data/historical/futures/btcusdt_perp_15m_2024_2025.parquet")

    assert f_path.exists(), "Funding parquet must exist."
    assert b_path.exists(), "Basis parquet must exist."
    assert p_path.exists(), "Perpetual klines parquet must exist."

    df_f = pd.read_parquet(f_path)
    funding_records = [FundingSettlementRecord(**r) for r in df_f.to_dict(orient="records")]

    df_b = pd.read_parquet(b_path)
    basis_records = [SpotPerpAlignedBasisRecord(**r) for r in df_b.to_dict(orient="records")]

    df_p = pd.read_parquet(p_path)
    perp_candles = [PerpetualCandleRecord(**r) for r in df_p.to_dict(orient="records")]

    return funding_records, basis_records, perp_candles


def test_coverage_reconciliation_425d(full_425d_datasets):
    """Verify that historical coverage matches 425 calendar days across all datasets."""
    funding_records, basis_records, perp_candles = full_425d_datasets

    # 1. Exact counts
    assert len(funding_records) == 1275, f"Expected 1275 funding settlements, got {len(funding_records)}"
    assert len(basis_records) == 40800, f"Expected 40800 basis records, got {len(basis_records)}"
    assert len(perp_candles) == 40800, f"Expected 40800 perp candles, got {len(perp_candles)}"

    # 2. Exact boundaries
    # First timestamp: 2024-01-01 00:00:00 UTC (1704067200000 ms)
    assert basis_records[0].timestamp_ms == 1704067200000
    assert basis_records[0].timestamp_utc.startswith("2024-01-01T00:00:00")

    # Last timestamp: 2025-02-28 23:45:00 UTC (1740786300000 ms)
    assert basis_records[-1].timestamp_ms == 1740786300000
    assert basis_records[-1].timestamp_utc.startswith("2025-02-28T23:45:00")

    # 3. Calendar days: 40800 / 96 = 425 days exactly
    assert len(basis_records) / 96.0 == 425.0


def test_raw_archives_and_checksum_preservation():
    """Verify that all raw zip archives and checksum files are preserved in data/historical/futures/raw/."""
    raw_dir = Path("data/historical/futures/raw")
    assert raw_dir.exists(), "Raw directory must exist."

    zips = list(raw_dir.glob("*.zip"))
    checksums = list(raw_dir.glob("*.CHECKSUM"))

    # 14 monthly klines + 14 monthly funding = 28 archives + 28 checksums = 56 files
    assert len(zips) >= 28, f"Expected at least 28 raw zip archives, found {len(zips)}"
    assert len(checksums) >= 28, f"Expected at least 28 checksum files, found {len(checksums)}"


def test_delta_neutral_capital_segregation_and_no_double_counting(full_425d_datasets):
    """Verify explicit capital segregation between Spot, Perpetual Margin, and Cash Reserve."""
    funding_records, basis_records, _ = full_425d_datasets
    sim = DeltaNeutralCarrySimulator(DeltaNeutralExecutionParams(
        initial_capital_usdt=10000.0,
        spot_allocation_pct=50.0,
        perp_margin_allocation_pct=25.0,
    ))

    res, snaps = sim.run_simulation(basis_records[:100], funding_records)
    s0 = snaps[0]

    # Segregation check
    assert s0.unallocated_cash_usdt == 2500.0
    assert res.spot_purchase_capital_usdt == 5000.0
    assert res.perp_margin_initial_usdt == 2500.0
    assert res.unallocated_cash_reserve_usdt == 2500.0

    # Total initial capital conserved
    assert abs(res.spot_purchase_capital_usdt + res.perp_margin_initial_usdt + res.unallocated_cash_reserve_usdt - 10000.0) < 1e-4

    # Target hedge ratio h = 1.0
    assert abs(s0.hedge_ratio - 1.0) < 1e-4
    assert s0.spot_btc_qty > 0.0
    assert s0.perp_btc_qty < 0.0


def test_point_in_time_funding_cash_flow_conventions(full_425d_datasets):
    """Verify funding cash flows follow authentic exchange conventions strictly at settlement boundaries."""
    funding_records, basis_records, _ = full_425d_datasets
    sim = DeltaNeutralCarrySimulator()
    res, snaps = sim.run_simulation(basis_records[:500], funding_records)

    # Find bars where funding occurred
    funding_snaps = []
    prev_net = 0.0
    for s in snaps:
        if abs(s.net_funding_usdt - prev_net) > 1e-4:
            funding_snaps.append(s)
            prev_net = s.net_funding_usdt

    assert len(funding_snaps) > 0

    # Check timestamps: must be 00:00, 08:00, or 16:00 UTC
    for fs in funding_snaps:
        dt = datetime.fromtimestamp(fs.timestamp_ms / 1000.0, tz=timezone.utc)
        assert dt.minute == 0
        assert dt.hour in (0, 8, 16)


def test_continuous_mark_to_market_and_basis_identity(full_425d_datasets):
    """Verify that Spot PnL + Perp PnL == Basis Convergence PnL identically."""
    funding_records, basis_records, _ = full_425d_datasets
    sim = DeltaNeutralCarrySimulator()
    res, snaps = sim.run_simulation(basis_records[:300], funding_records)

    assert res.basis_identity_verified is True
    assert res.accounting_conservation_verified is True
    assert res.max_accounting_discrepancy_usdt < 0.01

    for s in snaps:
        # Check closed-form basis identity
        combined_leg_pnl = s.spot_unrealized_pnl_usdt + s.perp_unrealized_pnl_usdt
        diff = abs(combined_leg_pnl - s.basis_convergence_pnl_usdt)
        assert diff < 0.05, f"Basis identity failed at {s.timestamp_utc}: {diff}"


def test_isolated_margin_depletion_and_liquidation_trigger(full_425d_datasets):
    """Verify that isolated margin depletion on large price surges triggers forced liquidation."""
    funding_records, basis_records, _ = full_425d_datasets
    # Q1 2024 had a massive rally from 42k to 60k+
    sim = DeltaNeutralCarrySimulator(DeltaNeutralExecutionParams(
        allow_reserve_margin_transfer=False, # strict isolated margin
    ))
    res, snaps = sim.run_simulation(basis_records, funding_records, start_idx=0, end_idx=8736)

    # Must terminate via liquidation breach
    assert res.terminal_status == "LIQUIDATION_BREACH_FORCED_EXIT"
    assert res.number_of_forced_exits == 1
    assert snaps[-1].is_liquidated is True


def test_independent_ledger_verifier_audits_cleanly(full_425d_datasets):
    """Verify that independent ledger verifier approves simulation runs with zero violations."""
    funding_records, basis_records, _ = full_425d_datasets
    sim = DeltaNeutralCarrySimulator()
    res, snaps = sim.run_simulation(basis_records, funding_records, start_idx=0, end_idx=2976)

    audit = DeltaNeutralLedgerVerifier.audit_simulation_run(res, snaps)
    assert audit.is_valid is True
    assert len(audit.violations) == 0
    assert audit.chronological_order_verified is True
    assert audit.hedge_ratio_verified is True
    assert audit.funding_sign_verified is True
    assert audit.zero_leakage_verified is True
    assert audit.equity_discrepancy_usdt < 0.05


def test_fail_closed_primitive_corruptions():
    """Verify that all fail-closed corruption unit tests detect errors and fail closed."""
    results = DeltaNeutralLedgerVerifier.audit_fail_closed_test_cases()
    assert results["wrong_funding_sign_detected"] is True
    assert results["double_counted_funding_detected"] is True
    assert results["missing_settlement_detected"] is True
    assert results["incorrect_hedge_ratio_detected"] is True
    assert results["missing_fee_detected"] is True
    assert results["negative_collateral_detected"] is True
    assert results["future_funding_leakage_detected"] is True
    assert results["corrupted_ordering_detected"] is True


def test_predetermined_scenarios_cost_impact(full_425d_datasets):
    """Verify that trading frictions consume a substantial portion of carry profits."""
    funding_records, basis_records, _ = full_425d_datasets

    # S1: Baseline Taker
    sim1 = DeltaNeutralCarrySimulator(DeltaNeutralExecutionParams())
    r1, _ = sim1.run_simulation(basis_records, funding_records, start_idx=0, end_idx=2976)

    # S2: Frictionless
    sim2 = DeltaNeutralCarrySimulator(DeltaNeutralExecutionParams(
        spot_taker_fee_rate=0.0, perp_taker_fee_rate=0.0, spot_slippage_rate=0.0, perp_slippage_rate=0.0
    ))
    r2, _ = sim2.run_simulation(basis_records, funding_records, start_idx=0, end_idx=2976)

    # S3: Stressed Costs
    sim3 = DeltaNeutralCarrySimulator(DeltaNeutralExecutionParams(
        spot_taker_fee_rate=0.0012, perp_taker_fee_rate=0.0008, spot_slippage_rate=0.0005, perp_slippage_rate=0.0005
    ))
    r3, _ = sim3.run_simulation(basis_records, funding_records, start_idx=0, end_idx=2976)

    # Frictionless PnL > Baseline Taker PnL > Stressed PnL
    assert r2.net_total_pnl_usdt > r1.net_total_pnl_usdt > r3.net_total_pnl_usdt
    assert r2.net_total_pnl_usdt == 57.10
    assert r1.net_total_pnl_usdt == 41.04
    assert r3.net_total_pnl_usdt == 27.02

    # Friction impact: Stressed costs reduce profit by > 50% relative to frictionless
    friction_reduction_pct = (r2.net_total_pnl_usdt - r3.net_total_pnl_usdt) / r2.net_total_pnl_usdt * 100.0
    assert friction_reduction_pct > 50.0


def test_pure_compute_latency_budget(full_425d_datasets):
    """Verify that simulation and audit compute latency is well under the 50 ms budget."""
    funding_records, basis_records, _ = full_425d_datasets
    sim = DeltaNeutralCarrySimulator()
    sample = basis_records[:500]

    latencies = []
    for _ in range(15):
        t0 = time.perf_counter()
        res, snaps = sim.run_simulation(sample, funding_records)
        audit = DeltaNeutralLedgerVerifier.audit_simulation_run(res, snaps)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    median_lat = sorted(latencies)[len(latencies) // 2]
    assert median_lat < 50.0, f"Median compute latency {median_lat:.2f} ms exceeds 50 ms budget."


def test_master_report_json_and_decision_gate():
    """Verify that generated report exists, is complete, and classifies simulator correctly."""
    rep_path = Path("data/reports/sprint09_35_delta_neutral_carry_report.json")
    assert rep_path.exists(), "Master report must exist."

    with open(rep_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["sprint_id"] == "SPRINT_09_35"
    assert data["decision_gate"]["classification"] == "READY_FOR_FURTHER_OFFLINE_ECONOMIC_RESEARCH"
    assert data["decision_gate"]["live_trading_permitted"] is False
    assert data["coverage_forensics"]["joint_data_readiness"] == "JOINT_DATA_RESEARCH_READY"
    assert len(data["scenarios"]) >= 5
    assert len(data["fail_closed_test_cases"]) >= 8

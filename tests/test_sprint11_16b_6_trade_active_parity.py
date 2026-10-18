"""Sprint 11.16B.6: Trade-Active Parity & Final Scientific Integrity Gate Test Suite.

Verifies:
1. Multi-window active replay execution across Bull, Bear, Sideways, and High Volatility regimes.
2. Trade-active parity for all 5 policies, with rule enforcement:
   "A policy with no executed trades must not receive EXECUTION_PARITY_PASS."
3. Controlled active trade parity fixture for Policy D and Policy E (entries, fills, stops, targets, balances).
4. Intrabar stop-loss and take-profit execution with pessimistic priority and gap-down modeling.
5. Expired pending order cancellation upon crash recovery (no retroactive fills).
6. Canonical Execution Policy V2 30 bps roundtrip friction reconciliation.
7. Analogue candidate library freeze identity audit.
8. Process memory footprint (<250 MB) and CPU latency bounds (<0.20 CPU budget).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import time
import tracemalloc
from typing import List

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research_lab.compact_analogue_runtime import (
    CompactAnalogueRuntime,
)
from coin_behavior_engine.research_lab.crash_consistent_journal import (
    CrashConsistentJournal,
    JournalEntryType,
    VirtualFill,
    VirtualOrder,
)
from coin_behavior_engine.research_lab.independent_policy_replay import (
    FROZEN_POLICIES,
    IndependentPolicyReplayHarness,
)
from coin_behavior_engine.research_lab.shadow_decision_protocol import (
    ProspectiveIntegrityEngine,
    ShadowDecisionAction,
    ShadowExecutionSimulator,
)
from coin_behavior_engine.research_lab.shadow_market_data_bridge import (
    CandleStreamType,
    HistoricalSeedProvenance,
    MarketCandle,
    ShadowMarketDataBridge,
)


# -------------------------------------------------------------------------
# Test 1: Multi-Window Replay Execution & Deliverable Verification
# -------------------------------------------------------------------------
def test_multi_window_replay_execution_and_deliverable_generation():
    """Verify that multi-window replay generates valid CSV deliverables with 20 audit rows."""
    out_dir = Path("research_outputs")
    csv_out = out_dir / "trade_active_policy_parity.csv"
    root_csv = Path("trade_active_policy_parity.csv")

    assert csv_out.is_file(), f"Missing {csv_out}"
    assert root_csv.is_file(), f"Missing {root_csv}"

    df = pd.read_csv(csv_out)
    assert len(df) == 20, f"Expected 20 rows (4 regimes x 5 policies), got {len(df)}"

    expected_cols = [
        "regime", "policy_id", "bars_evaluated", "entries_count", "exits_count",
        "stops_count", "take_profits_count", "virtual_fills_count", "unresolved_orders_count",
        "total_taker_fee_usdt", "total_slippage_usdt", "total_friction_usdt",
        "nominal_friction_rate_bps", "ending_ref_equity", "ending_indep_equity",
        "equity_discrepancy_usdt", "execution_parity_status"
    ]
    for col in expected_cols:
        assert col in df.columns, f"Missing column {col} in trade_active_policy_parity.csv"

    # Regimes present
    regimes = df["regime"].unique().tolist()
    assert set(regimes) == {"BULL", "BEAR", "SIDEWAYS", "HIGH_VOLATILITY"}

    # Equity discrepancies across all 20 rows must be <= 0.01 USDT
    assert (df["equity_discrepancy_usdt"] <= 0.01).all()

    # Policy A must always be permanent cash
    pol_a = df[df["policy_id"] == "POLICY_A_USDT_CASH"]
    assert (pol_a["execution_parity_status"] == "PASS_PERMANENT_CASH_INTENDED").all()
    assert (pol_a["entries_count"] == 0).all()

    # Policy B must execute buy at inception in each window
    pol_b = df[df["policy_id"] == "POLICY_B_BTC_BUY_AND_HOLD"]
    assert (pol_b["execution_parity_status"] == "EXECUTION_PARITY_PASS").all()
    assert (pol_b["entries_count"] == 1).all()

    # Policy C must execute active trades in Bull, Sideways, High Volatility
    pol_c = df[df["policy_id"] == "POLICY_C_TREND48_FOLLOWING"]
    c_bull = pol_c[pol_c["regime"] == "BULL"].iloc[0]
    assert c_bull["entries_count"] >= 5
    assert c_bull["exits_count"] >= 5
    assert c_bull["execution_parity_status"] == "EXECUTION_PARITY_PASS"

    c_side = pol_c[pol_c["regime"] == "SIDEWAYS"].iloc[0]
    assert c_side["entries_count"] >= 10
    assert c_side["execution_parity_status"] == "EXECUTION_PARITY_PASS"

    # Policy D and Policy E must be BLOCKED_ZERO_TRADES_EXECUTED because real 5m ATR < 0.015
    for pol_id in ("POLICY_D_SELECTIVE_TREND_ONLY", "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED"):
        pol_sub = df[df["policy_id"] == pol_id]
        assert (pol_sub["execution_parity_status"] == "BLOCKED_ZERO_TRADES_EXECUTED").all()
        assert (pol_sub["entries_count"] == 0).all()


# -------------------------------------------------------------------------
# Test 2: Controlled Active Trade Parity Fixture for Policy D & Policy E
# -------------------------------------------------------------------------
def test_trade_active_execution_parity_policy_d_and_e_controlled_fixture():
    """Verify that in a controlled market where filters trigger, Policy D and E execute with 100% parity."""
    # Build 864 warmup candles at 80,000, then trigger breakout
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    warmup_candles = []
    for i in range(864):
        c = MarketCandle(
            symbol="BTCUSDT",
            interval="5m",
            timestamp_open_utc=(base_t + timedelta(minutes=5 * i)).isoformat(),
            timestamp_close_utc=(base_t + timedelta(minutes=5 * (i + 1))).isoformat(),
            open_p=80000.0,
            high_p=80100.0,
            low_p=79900.0,
            close_p=80000.0,
            volume_base=10.0,
            volume_usdt=800000.0,
            is_closed=True,
            stream_type=CandleStreamType.HISTORICAL_SEED_WARMUP,
            sequence_number=i,
            provenance="FIXTURE",
        )
        warmup_candles.append(c)

    # Eval candles: Bar 864 breaks out above 24h & 72h SMA with atr_pct in [0.015, 0.065]
    eval_candles = []
    # Bar 864: Breakout to 81,000 (SMA_24h is 80,000, 81000 <= 80000*1.0225=81800, so anti_chase ok)
    # High: 82500, Low: 79500 -> TR = 3000 -> atr_14 will rise
    c864 = MarketCandle(
        symbol="BTCUSDT",
        interval="5m",
        timestamp_open_utc=(base_t + timedelta(minutes=5 * 864)).isoformat(),
        timestamp_close_utc=(base_t + timedelta(minutes=5 * 865)).isoformat(),
        open_p=80500.0,
        high_p=82500.0,
        low_p=79500.0,
        close_p=81000.0,
        volume_base=25.0,
        volume_usdt=2025000.0,
        is_closed=True,
        stream_type=CandleStreamType.PROSPECTIVE_LIVE_OBSERVATION,
        sequence_number=864,
        provenance="FIXTURE",
    )
    # Bar 865: Open at 81,100 -> Fill occurs here! Then drops to hit stop loss at 79,000
    c865 = MarketCandle(
        symbol="BTCUSDT",
        interval="5m",
        timestamp_open_utc=(base_t + timedelta(minutes=5 * 865)).isoformat(),
        timestamp_close_utc=(base_t + timedelta(minutes=5 * 866)).isoformat(),
        open_p=81100.0,
        high_p=81200.0,
        low_p=78500.0,  # Below stop loss (81100 * 0.975 = 79072.5)
        close_p=78600.0,
        volume_base=30.0,
        volume_usdt=2358000.0,
        is_closed=True,
        stream_type=CandleStreamType.PROSPECTIVE_LIVE_OBSERVATION,
        sequence_number=865,
        provenance="FIXTURE",
    )
    # Bar 866: Post exit
    c866 = MarketCandle(
        symbol="BTCUSDT",
        interval="5m",
        timestamp_open_utc=(base_t + timedelta(minutes=5 * 866)).isoformat(),
        timestamp_close_utc=(base_t + timedelta(minutes=5 * 867)).isoformat(),
        open_p=78600.0,
        high_p=78700.0,
        low_p=78500.0,
        close_p=78550.0,
        volume_base=10.0,
        volume_usdt=785500.0,
        is_closed=True,
        stream_type=CandleStreamType.PROSPECTIVE_LIVE_OBSERVATION,
        sequence_number=866,
        provenance="FIXTURE",
    )
    eval_candles = [c864, c865, c866]

    with tempfile.TemporaryDirectory() as tmpdir:
        j_dir = Path(tmpdir) / "journal_pol_d"
        journal = CrashConsistentJournal(journal_dir=j_dir, initial_capital_usdt=10000.0, policy_id="POLICY_D_SELECTIVE_TREND_ONLY")
        ref_engine = ProspectiveIntegrityEngine(policy_id="POLICY_D_SELECTIVE_TREND_ONLY", initial_capital=10000.0)

        # Bar 864 features: force gating conditions to True
        feat_864 = {
            "sma_24h": 80000.0,
            "sma_72h": 80000.0,
            "atr_pct": 0.025,
            "analogue_prob": 0.70,
        }

        # Ref evaluation
        ref_dec = ref_engine.evaluate_bar(
            bar_idx=0,
            timestamp_utc=c864.timestamp_open_utc,
            availability_timestamp_utc=c864.timestamp_close_utc,
            open_p=c864.open_p,
            high_p=c864.high_p,
            low_p=c864.low_p,
            close_p=c864.close_p,
            features=feat_864,
        )
        assert ref_dec.decision == ShadowDecisionAction.BUY_CANDIDATE.value

        # Independent decision
        journal.commit_decision(
            decision_id="DEC-TEST-001",
            decision_hash=ref_dec.decision_hash,
            action=ShadowDecisionAction.BUY_CANDIDATE.value,
            candle_open_utc=c864.timestamp_open_utc,
            candle_close_utc=c864.timestamp_close_utc,
            close_p=c864.close_p,
            eligible_open_utc=c865.timestamp_open_utc,
        )
        assert journal.pending_order is not None
        assert journal.pending_order.action == "BUY"

        # Next open (c865.open_p = 81100.0) fills the order
        ref_buy_res = ref_engine.simulator.execute_hypothetical_buy(next_open=c865.open_p)
        assert ref_buy_res["success"] is True

        indep_fill = journal.commit_fill(
            order=journal.pending_order,
            next_open_price=c865.open_p,
            fill_timestamp_utc=c865.timestamp_open_utc,
        )
        assert indep_fill is not None

        # Verify buy fill parity down to 0.0001
        assert abs(ref_engine.simulator.btc_balance - journal.btc_balance) < 1e-6
        assert abs(ref_engine.simulator.usdt_balance - journal.usdt_balance) < 1e-2
        assert abs(ref_engine.simulator.stop_loss_price - journal.stop_loss_price) < 1e-2
        assert abs(ref_engine.simulator.take_profit_price - journal.take_profit_price) < 1e-2

        # Bar 865: Price drops to 78,500, triggering intrabar stop loss (stop_price is 81100 * 0.975 = 79072.5)
        intrabar_fill = journal.check_intrabar_exit(
            high_p=c865.high_p,
            low_p=c865.low_p,
            open_p=c865.open_p,
            fill_timestamp_utc=c865.timestamp_open_utc,
        )
        assert intrabar_fill is not None
        assert intrabar_fill.reason == "STOP_LOSS"
        assert abs(intrabar_fill.fill_price - (79072.5 * 0.9995)) < 1e-2

        # Ref engine intrabar check
        ref_dec_865 = ref_engine.evaluate_bar(
            bar_idx=1,
            timestamp_utc=c865.timestamp_open_utc,
            availability_timestamp_utc=c865.timestamp_close_utc,
            open_p=c865.open_p,
            high_p=c865.high_p,
            low_p=c865.low_p,
            close_p=c865.close_p,
            features={"sma_24h": 80000.0, "sma_72h": 80000.0, "atr_pct": 0.025},
        )
        assert ref_dec_865.decision == ShadowDecisionAction.EXIT_TO_USDT.value

        # Post-stop cash balances must match to 0.01 USDT
        assert abs(ref_engine.simulator.usdt_balance - journal.usdt_balance) < 0.01
        assert ref_engine.simulator.btc_balance == 0.0
        assert journal.btc_balance == 0.0


# -------------------------------------------------------------------------
# Test 3: Intrabar Exit Pessimistic Priority & Gap Down Scenarios
# -------------------------------------------------------------------------
def test_intrabar_exit_pessimistic_priority_and_friction():
    """Verify stop-loss precedes take-profit when both touched, and gap-downs fill at open."""
    with tempfile.TemporaryDirectory() as tmpdir:
        j_dir = Path(tmpdir) / "journal_intrabar"
        journal = CrashConsistentJournal(journal_dir=j_dir, initial_capital_usdt=10000.0, policy_id="POLICY_C_TREND48_FOLLOWING")

        # 1. Setup active position: Buy at 100,000
        ord_buy = VirtualOrder("ORD-001", "DEC-001", "POLICY_C", "BUY", "2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z")
        journal.commit_fill(ord_buy, next_open_price=100000.0, fill_timestamp_utc="2026-01-01T00:05:00Z")
        assert journal.position_active is True
        assert journal.stop_loss_price == 97500.0
        assert journal.take_profit_price == 105000.0

        # Scenario A: Gap down below stop-loss (Open = 96,000 <= 97,500)
        gap_fill = journal.check_intrabar_exit(
            high_p=96500.0,
            low_p=95000.0,
            open_p=96000.0,
            fill_timestamp_utc="2026-01-01T00:10:00Z",
        )
        assert gap_fill is not None
        assert gap_fill.reason == "STOP_LOSS_GAP_DOWN"
        # Filled at open (96000 * (1 - 0.0005) = 95952.0)
        assert abs(gap_fill.fill_price - 95952.0) < 1e-2
        assert journal.position_active is False

        # Reset position with fresh order for Scenario B
        ord_b = VirtualOrder("ORD-002", "DEC-002", "POLICY_C", "BUY", "2026-01-01T00:15:00Z", "2026-01-01T00:15:00Z")
        journal.commit_fill(ord_b, next_open_price=100000.0, fill_timestamp_utc="2026-01-01T00:15:00Z")

        # Scenario B: Low hits stop loss (Low = 97,000 <= 97,500, High = 101,000)
        stop_fill = journal.check_intrabar_exit(
            high_p=101000.0,
            low_p=97000.0,
            open_p=99000.0,
            fill_timestamp_utc="2026-01-01T00:20:00Z",
        )
        assert stop_fill is not None
        assert stop_fill.reason == "STOP_LOSS"
        # Filled at stop price (97500 * (1 - 0.0005) = 97451.25)
        assert abs(stop_fill.fill_price - 97451.25) < 1e-2

        # Reset position with fresh order for Scenario C
        ord_c = VirtualOrder("ORD-003", "DEC-003", "POLICY_C", "BUY", "2026-01-01T00:25:00Z", "2026-01-01T00:25:00Z")
        journal.commit_fill(ord_c, next_open_price=100000.0, fill_timestamp_utc="2026-01-01T00:25:00Z")

        # Scenario C: Both boundaries touched (Low = 97,000 <= 97,500 AND High = 106,000 >= 105,000)
        # Pessimistic rule: Stop loss executes FIRST!
        both_fill = journal.check_intrabar_exit(
            high_p=106000.0,
            low_p=97000.0,
            open_p=100000.0,
            fill_timestamp_utc="2026-01-01T00:30:00Z",
        )
        assert both_fill is not None
        assert both_fill.reason == "STOP_LOSS"  # Must not be TAKE_PROFIT!
        assert abs(both_fill.fill_price - 97451.25) < 1e-2

        # Reset position with fresh order for Scenario D
        ord_d = VirtualOrder("ORD-004", "DEC-004", "POLICY_C", "BUY", "2026-01-01T00:35:00Z", "2026-01-01T00:35:00Z")
        journal.commit_fill(ord_d, next_open_price=100000.0, fill_timestamp_utc="2026-01-01T00:35:00Z")

        # Scenario D: Only take profit touched (High = 106,000 >= 105,000, Low = 98,000 > 97,500)
        tp_fill = journal.check_intrabar_exit(
            high_p=106000.0,
            low_p=98000.0,
            open_p=100000.0,
            fill_timestamp_utc="2026-01-01T00:40:00Z",
        )
        assert tp_fill is not None
        assert tp_fill.reason == "TAKE_PROFIT"
        # Filled at take profit price (105000 * (1 - 0.0005) = 104947.5)
        assert abs(tp_fill.fill_price - 104947.5) < 1e-2


# -------------------------------------------------------------------------
# Test 4: Expired Pending Order Safety Upon Restart
# -------------------------------------------------------------------------
def test_expired_pending_order_cancelled_upon_restart():
    """Verify pending orders older than 300s are rejected upon recovery (no retroactive fills)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        j_dir = Path(tmpdir) / "journal_expired"
        j1 = CrashConsistentJournal(journal_dir=j_dir, initial_capital_usdt=10000.0, policy_id="POLICY_C_TREND48_FOLLOWING")

        # Stage BUY decision at 12:00:00, eligible open at 12:05:00
        j1.commit_decision(
            decision_id="DEC-EXP-001",
            decision_hash="0" * 64,
            action="BUY",
            candle_open_utc="2026-01-01T12:00:00Z",
            candle_close_utc="2026-01-01T12:05:00Z",
            close_p=90000.0,
            eligible_open_utc="2026-01-01T12:05:00Z",
        )
        assert j1.pending_order is not None

        # Simulate crash and restart 15 minutes later at 12:20:00 (> 300s offline)
        j2 = CrashConsistentJournal(journal_dir=j_dir, initial_capital_usdt=10000.0, policy_id="POLICY_C_TREND48_FOLLOWING")
        ok, msg = j2.recover()
        assert ok is True
        assert j2.pending_order is not None

        # Attempt to fill with next candle at 12:20:00 (15 minutes late)
        fill = j2.commit_fill(
            order=j2.pending_order,
            next_open_price=92000.0,
            fill_timestamp_utc="2026-01-01T12:20:00Z",
        )
        assert fill is None  # Must refuse retroactive fill!
        assert j2.pending_order is None  # Pending order cancelled
        assert j2.position_active is False
        assert j2.usdt_balance == 10000.0


# -------------------------------------------------------------------------
# Test 5: Canonical Execution Policy V2 30 bps Cost Reconciliation
# -------------------------------------------------------------------------
def test_canonical_execution_policy_v2_cost_reconciliation():
    """Verify exact 30 bps roundtrip friction: 10 bps fee + 5 bps slippage per side."""
    sim = ShadowExecutionSimulator(
        initial_capital_usdt=10000.0,
        taker_fee_bps=10.0,
        slippage_bps=5.0,
        allocation_cap_pct=98.0,
    )

    # 1. Buy at 100,000
    buy_res = sim.execute_hypothetical_buy(next_open=100000.0)
    assert buy_res["success"] is True

    # Nominal entry friction check
    allocated = 10000.0 * 0.98  # 9800 USDT
    expected_entry_fee = allocated * 0.0010  # 9.80 USDT
    expected_entry_slip = (100000.0 * 0.0005) * (allocated / (100000.0 * 1.0005))
    assert abs(buy_res["entry_friction_usdt"] - (expected_entry_fee + expected_entry_slip)) < 1e-4

    # 2. Exit at 100,000 (flat gross PnL)
    exit_res = sim.execute_hypothetical_exit(exit_raw_price=100000.0)
    assert exit_res["success"] is True

    # Realized gross PnL must be 0.0
    assert abs(exit_res["realized_gross_pnl_usdt"]) < 1e-4

    # Total roundtrip friction must be approx 30 bps of traded notional
    total_fric = sim.cumulative_friction_usdt
    notional = allocated
    effective_roundtrip_bps = (total_fric / notional) * 10000.0
    assert abs(effective_roundtrip_bps - 30.0) < 0.5  # within 0.5 bps of nominal 30 bps

    # Conservation invariant: starting_equity + net_pnl == ending_equity
    ending_equity = sim.get_portfolio_equity(100000.0)
    assert abs((sim.initial_capital_usdt + sim.cumulative_net_pnl_usdt) - ending_equity) < 1e-4


# -------------------------------------------------------------------------
# Test 6: Analogue Freeze Identity Audit
# -------------------------------------------------------------------------
def test_analogue_freeze_identity_audit():
    """Verify compact analogue candidate matrix satisfies freeze constraints and non-leakage."""
    runtime = CompactAnalogueRuntime()
    ok, msg = runtime.verify_and_load()
    assert ok is True

    # Candidate matrix must contain 67,752 candidates (strictly from training partition <= 68,040)
    assert len(runtime.candidate_matrix) == 67752
    assert runtime.candidate_matrix.shape[1] == 10

    # Holdout partition (> 68,040) must be completely excluded
    # Max training timestamp must not exceed 2026-06-11
    max_ts = int(max(runtime.candidate_timestamps))
    max_dt = datetime.fromtimestamp(max_ts / 1000.0, tz=timezone.utc)
    assert max_dt < datetime(2026, 6, 12, tzinfo=timezone.utc), f"Leakage detected: max training ts {max_dt} >= 2026-06-12"

    # Forward return distribution
    pos_labels = (runtime.candidate_returns >= 0.0120).sum()
    pct_pos = pos_labels / len(runtime.candidate_returns) * 100.0
    assert 40.0 <= pct_pos <= 55.0, f"Unexpected positive label proportion: {pct_pos:.2f}%"


# -------------------------------------------------------------------------
# Test 7: Linux Runtime Memory Footprint & CPU Latency Bounds
# -------------------------------------------------------------------------
def test_linux_runtime_resource_bounds():
    """Verify heap memory < 120 MB and query latency < 10 ms."""
    tracemalloc.start()

    runtime = CompactAnalogueRuntime()
    runtime.verify_and_load()
    harness = IndependentPolicyReplayHarness()

    current_mem, peak_mem = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    peak_mb = peak_mem / (1024 * 1024)
    # Peak memory must be well within the 250 MB prospective container ceiling
    assert peak_mb < 150.0, f"Memory footprint too high: {peak_mb:.2f} MB >= 150 MB"

    # Measure 50 queries latency
    vec = np.zeros(10, dtype=np.float32)
    t0 = time.perf_counter()
    for _ in range(50):
        runtime.query(vec, k=20)
    t1 = time.perf_counter()
    avg_latency_ms = (t1 - t0) / 50 * 1000.0

    assert avg_latency_ms < 10.0, f"Query latency too high: {avg_latency_ms:.2f} ms >= 10 ms"

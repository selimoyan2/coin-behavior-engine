"""Comprehensive test suite for Sprint 09.27: Behavioral Signal Validation, Regime Causality Audit & Strict Holdout Evaluation.

Covers:
1. Research Integrity Gate Verification:
   - Reproduction of Sprint 09.25/09.26 trade ledger reconciliation (190 filled, 47 unfilled, -0.27% net return).
2. Market Regime Classification Causality Audit:
   - Mathematical proof and empirical verification of why BULLISH <-> BEARISH transitions pass through SIDEWAYS_RANGE.
   - Attribution to COMBINED_EFFECT_PREDOMINANTLY_ARTIFACT (classifier hysteresis geometry).
   - Null model comparisons: Single EMA50 (>700 direct transitions) vs Dual EMA crossover (73 direct transitions).
   - Sensitivity across EMA span pairs (20/100, 50/200, 100/300).
3. B3 Executable Hypothesis Simulation:
   - Point-in-time entry at next bar open (zero lookahead).
   - Independent non-overlapping trade clustering.
   - Directional asymmetry audit (Continuation vs Reversion, Long vs Short).
   - Cost accounting (Maker 6 bps, Taker 16 bps).
4. B5 Executable Hypothesis Simulation:
   - Failed continuation rebound entry logic with ATR stop-loss and take-profit barriers.
   - Rebound bullish vs symmetric execution.
5. Pre-Registration Gate & Hash Integrity:
   - Immutable SHA-256 parameter hash verification.
   - Tamper-proofing: mutating parameters raises gate violation.
6. Chronological Walk-Forward Development (Q1-Q3):
   - Out-of-sample evaluation on developmental quarters.
7. Multiple-Testing Statistical Control:
   - Bonferroni adjustment (nominal alpha / 4 = 0.0125).
   - Benjamini-Hochberg False Discovery Rate control.
8. Single-Pass Q4 2024 Virgin Holdout Confirmatory Evaluation:
   - Strict confirmatory test against untouched Q4 holdout.
   - Objective validation verdict (REJECTED due to negative net returns after transaction costs).
9. Performance Regression Forensics:
   - Separate verification of isolated in-memory compute (< 50 ms) and disk WAL I/O documentation.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
import time
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research.historical import (
    AuditableTradeRecord,
    B3StrategyConfig,
    B5StrategyConfig,
    BehavioralDecisionVerdict,
    BehavioralValidationOrchestrator,
    CausalityAttribution,
    ConfirmatoryHoldoutResult,
    ExecutableBehaviorSimulator,
    ExecutableStrategyMetrics,
    HistoricalDatasetStore,
    HistoricalMarketSpec,
    MultipleTestingCorrectionReport,
    PreRegistrationGate,
    RegimeClassificationAuditor,
    RegimeCausalityAuditReport,
)


# =========================================================================
# 1. Research Integrity Gate Verification
# =========================================================================

def test_research_integrity_reproduction_sprint09_26():
    """Verify exact reproduction of Sprint 09.25/09.26 trade ledger reconciliation."""
    ledger_path = Path("data/reports/sprint09_25_trade_ledger.jsonl")
    assert ledger_path.exists(), "Sprint 09.25 trade ledger file missing"

    records = []
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(AuditableTradeRecord(**json.loads(line)))

    assert len(records) == 237
    filled = [r for r in records if r.is_filled]
    unfilled = [r for r in records if not r.is_filled]
    assert len(filled) == 190
    assert len(unfilled) == 47

    ledger_sum_pct = sum(r.net_return_pct for r in filled)
    assert math.isclose(ledger_sum_pct * 100.0, -0.27, abs_tol=0.02)


# =========================================================================
# 2. Market Regime Classification Causality Audit Tests
# =========================================================================

def test_regime_classification_causality_audit_and_null_models():
    """Verify that near-zero transitions are proven to be an algorithmic artifact."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_q1 = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec_q1, ext="parquet")).to_dict(orient="records")

    auditor = RegimeClassificationAuditor(candles)
    report = auditor.audit_trend_transitions()

    assert isinstance(report, RegimeCausalityAuditReport)
    assert report.attribution == CausalityAttribution.COMBINED_EFFECT_PREDOMINANTLY_ARTIFACT

    # Dual-condition engine has near-zero direct flips
    assert report.direct_transition_rate_pct < 1.0  # < 1% of state transitions
    assert report.direct_transitions_observed_count <= 10

    # Single EMA null model has hundreds of flips
    null1 = report.null_model_single_ema
    assert null1.direct_bull_to_bear + null1.direct_bear_to_bull > 500

    # Dual EMA crossover null model
    null2 = report.null_model_dual_ema_crossover
    assert null2.direct_bull_to_bear + null2.direct_bear_to_bull > 50

    # Sensitivity variations all maintain low flip rates due to dual-condition topology
    for var in report.sensitivity_variations:
        assert var.direct_flip_rate_pct < 10.0
        assert var.sideways_frequency > 0.15  # Buffer zone is always populated

    assert "MATHEMATICAL PROOF" in report.mathematical_proof
    assert "AUDIT VERDICT" in report.auditor_conclusion


# =========================================================================
# 3. B3 Executable Strategy Tests
# =========================================================================

def test_b3_executable_strategy_simulation_and_cost_accounting():
    """Verify B3 execution rules, zero-lookahead, and cost accounting."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_q1 = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec_q1, ext="parquet")).to_dict(orient="records")

    sim = ExecutableBehaviorSimulator(candles)
    cfg_cont = B3StrategyConfig(direction_mode="CONTINUATION")
    metrics_cont, records_cont = sim.simulate_b3(cfg_cont, dataset_tag="q1_2024")

    # Invariants
    assert metrics_cont.independent_trades > 50
    assert metrics_cont.independent_trades <= metrics_cont.total_signals_detected
    assert len(records_cont) == metrics_cont.independent_trades

    # Verify zero-lookahead entry at next bar open
    for r in records_cont[:5]:
        assert r.intended_entry_price == float(candles[r.entry_bar_index]["open"])
        assert r.effective_entry_price == float(candles[r.entry_bar_index]["open"])
        assert r.is_independent is True
        assert r.holding_bars <= cfg_cont.max_holding_bars

    # Cost accounting: Net Maker must equal Gross minus 6 bps
    expected_net = round(metrics_cont.gross_expectancy_bps - 6.0, 2)
    assert math.isclose(metrics_cont.net_maker_expectancy_bps, expected_net, abs_tol=0.05)

    # Taker net must equal Gross minus 16 bps
    expected_taker = round(metrics_cont.gross_expectancy_bps - 16.0, 2)
    assert math.isclose(metrics_cont.net_taker_expectancy_bps, expected_taker, abs_tol=0.05)


# =========================================================================
# 4. B5 Executable Strategy Tests
# =========================================================================

def test_b5_executable_strategy_simulation_and_cost_accounting():
    """Verify B5 failed continuation rebound execution and barrier exits."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_q1 = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec_q1, ext="parquet")).to_dict(orient="records")

    sim = ExecutableBehaviorSimulator(candles)
    cfg_bull = B5StrategyConfig(direction_mode="REBOUND_BULLISH")
    metrics_bull, records_bull = sim.simulate_b5(cfg_bull, dataset_tag="q1_2024")

    assert metrics_bull.independent_trades >= 30
    assert len(records_bull) == metrics_bull.independent_trades

    # All trades in REBOUND_BULLISH must be LONG
    for r in records_bull:
        assert r.direction == "LONG"
        assert r.exit_reason in ["STOP_LOSS", "TAKE_PROFIT", "HORIZON_EXPIRED"]

    # Symmetric mode includes both LONG and SHORT
    cfg_symm = B5StrategyConfig(direction_mode="REBOUND_SYMMETRIC")
    metrics_symm, records_symm = sim.simulate_b5(cfg_symm, dataset_tag="q1_2024")
    assert metrics_symm.long_trades_count > 0
    assert metrics_symm.short_trades_count > 0


# =========================================================================
# 5. Pre-Registration Gate & Hash Integrity Tests
# =========================================================================

def test_preregistration_gate_freeze_and_hash_integrity():
    """Verify immutable pre-registration gate and tamper prevention."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    orchestrator = BehavioralValidationOrchestrator(store)
    gate = orchestrator.create_pre_registration_gate()

    assert gate.is_frozen is True
    assert len(gate.frozen_strategy_hashes) == 4
    for key, h in gate.frozen_strategy_hashes.items():
        assert len(h) == 64  # SHA-256 hex length

    # Modifying a parameter hash must fail integrity check
    tampered_hashes = dict(gate.frozen_strategy_hashes)
    tampered_hashes["B3_CONTINUATION"] = "0" * 64
    assert gate.verify_integrity(tampered_hashes) is False


# =========================================================================
# 6. Chronological Walk-Forward Development Tests
# =========================================================================

def test_chronological_walk_forward_development():
    """Verify chronological walk-forward folds across development data (Q1-Q3)."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    orchestrator = BehavioralValidationOrchestrator(store)

    folds_b3 = orchestrator.evaluate_walk_forward_development("B3_CONTINUATION")
    assert len(folds_b3) == 2
    assert folds_b3[0].val_quarter == "q2_2024"
    assert folds_b3[1].val_quarter == "q3_2024"

    # Both folds must have independent trades evaluated
    assert folds_b3[0].metrics.independent_trades >= 30
    assert folds_b3[1].metrics.independent_trades >= 30

    # Net maker expectancy in both development test folds is negative
    assert folds_b3[0].metrics.net_maker_expectancy_bps < 0.0
    assert folds_b3[1].metrics.net_maker_expectancy_bps < 0.0


# =========================================================================
# 7. Multiple-Testing Statistical Control Tests
# =========================================================================

def test_multiple_testing_correction_control():
    """Verify Bonferroni and Benjamini-Hochberg multiple-testing corrections."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    orchestrator = BehavioralValidationOrchestrator(store)

    mock_p_values = {
        "B3_CONTINUATION": 0.32,
        "B3_REVERSION": 0.17,
        "B5_REBOUND_BULLISH": 0.41,
        "B5_REBOUND_SYMMETRIC": 0.38,
    }

    report = orchestrator.apply_multiple_testing_control(mock_p_values, nominal_alpha=0.05)
    assert report.family_size == 4
    assert report.bonferroni_alpha == 0.0125

    # None should survive with these high p-values
    for k in mock_p_values:
        assert report.bonferroni_survived[k] is False
        assert report.benjamini_hochberg_survived[k] is False


# =========================================================================
# 8. Single-Pass Q4 2024 Virgin Holdout Confirmatory Tests
# =========================================================================

def test_q4_confirmatory_holdout_single_pass_verdict():
    """Verify single-pass confirmatory test on Q4 2024 holdout dataset."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    orchestrator = BehavioralValidationOrchestrator(store)
    gate = orchestrator.create_pre_registration_gate()

    # Confirmatory evaluation for B3
    h_b3 = orchestrator.evaluate_confirmatory_q4_holdout("B3_CONTINUATION", gate)
    assert isinstance(h_b3, ConfirmatoryHoldoutResult)
    assert h_b3.holdout_dataset == "historical_binance_btcusdt_15m_q4_2024.parquet"
    assert h_b3.passed_confirmatory_gate is False
    assert h_b3.verdict == BehavioralDecisionVerdict.REJECTED
    assert h_b3.metrics.net_maker_expectancy_bps < 0.0

    # Confirmatory evaluation for B5
    h_b5 = orchestrator.evaluate_confirmatory_q4_holdout("B5_REBOUND_BULLISH", gate)
    assert isinstance(h_b5, ConfirmatoryHoldoutResult)
    assert h_b5.passed_confirmatory_gate is False
    assert h_b5.verdict == BehavioralDecisionVerdict.REJECTED
    assert h_b5.metrics.net_maker_expectancy_bps < 0.0


# =========================================================================
# 9. Performance Latency Budget Forensics
# =========================================================================

def test_performance_latency_budget_pure_compute():
    """Verify pure in-memory compute latency is strictly within the 50 ms budget."""
    store = HistoricalDatasetStore(base_dir=Path("data/historical"))
    spec_q1 = HistoricalMarketSpec(symbol="BTCUSDT", interval="15m", dataset_tag="q1_2024")
    candles = pd.read_parquet(store.get_dataset_filepath(spec_q1, ext="parquet")).to_dict(orient="records")

    sim = ExecutableBehaviorSimulator(candles[:500])

    times = []
    for _ in range(100):
        t0 = time.perf_counter()
        sim.engine.classify_bar(250)
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000.0)

    mean_compute_ms = float(np.mean(times))
    assert mean_compute_ms < 50.0, f"Pure compute latency {mean_compute_ms:.2f} ms exceeded 50 ms budget"

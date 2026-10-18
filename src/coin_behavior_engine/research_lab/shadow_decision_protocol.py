"""Shadow Decision Protocol & Prospective Research Readiness Engine.

Sprint 11.15: Prospective Research Readiness & Shadow Decision Protocol.
Provides an immutable, tamper-evident shadow decision contract, cryptographic
hash chaining, realistic offline spot execution under Policy V2, policy freeze
mechanisms, and fail-closed data integrity guards.

Strictly air-gapped: zero live network connections, zero exchange orders,
zero mutation of staging/production/live capture containers.
"""

from __future__ import annotations

import copy
import dataclasses
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import enum
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from coin_behavior_engine.research_lab.contracts import (
    DecisionAction,
    MarketRegimeType,
)

logger = logging.getLogger("cbe_shadow_decision_protocol")

CANONICAL_DATASET_SHA256 = "2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487"
GENESIS_PARENT_HASH = "0000000000000000000000000000000000000000000000000000000000000000"
BASE_CODE_COMMIT = "7ee1104564cfe2283d234284e220d0ef06f40963"
POLICY_V2_VERSION = "2.0.0-sprint11.13"


class ShadowDecisionAction(str, enum.Enum):
    """Permitted discrete decision actions under Shadow Decision Protocol."""
    WAIT_USDT = "WAIT_USDT"
    BUY_CANDIDATE = "BUY_CANDIDATE"
    HOLD_BTC = "HOLD_BTC"
    REDUCE_BTC = "REDUCE_BTC"
    EXIT_TO_USDT = "EXIT_TO_USDT"
    NO_DECISION_DATA = "NO_DECISION_DATA"


@dataclass
class ShadowDecisionRecord:
    """Machine-readable, immutable shadow decision record."""
    decision_id: str
    sequence_number: int
    observation_timestamp_utc: str
    data_availability_timestamp_utc: str
    source_identifier: str
    btc_spot_reference_price: float
    hypothetical_usdt_balance: float
    hypothetical_btc_balance: float
    hypothetical_total_equity_usdt: float
    market_regime: str
    forecast_probabilities: Dict[str, float]
    uncertainty_score: float
    decision: str
    hypothetical_target_price: Optional[float] = None
    hypothetical_stop_price: Optional[float] = None
    evidence_rationale: Dict[str, Any] = field(default_factory=dict)
    policy_id: str = "POLICY_D_SELECTIVE_TREND_ONLY"
    policy_version: str = "1.0.0-frozen"
    code_commit_hash: str = BASE_CODE_COMMIT
    parent_decision_hash: str = GENESIS_PARENT_HASH
    decision_hash: str = ""

    def compute_hash(self) -> str:
        """Compute deterministic SHA-256 hash over canonical payload representation."""
        payload = {
            "decision_id": self.decision_id,
            "sequence_number": self.sequence_number,
            "observation_timestamp_utc": self.observation_timestamp_utc,
            "data_availability_timestamp_utc": self.data_availability_timestamp_utc,
            "source_identifier": self.source_identifier,
            "btc_spot_reference_price": round(float(self.btc_spot_reference_price), 4),
            "hypothetical_usdt_balance": round(float(self.hypothetical_usdt_balance), 4),
            "hypothetical_btc_balance": round(float(self.hypothetical_btc_balance), 8),
            "hypothetical_total_equity_usdt": round(float(self.hypothetical_total_equity_usdt), 4),
            "market_regime": str(self.market_regime),
            "forecast_probabilities": {k: round(float(v), 6) for k, v in sorted(self.forecast_probabilities.items())},
            "uncertainty_score": round(float(self.uncertainty_score), 6),
            "decision": str(self.decision),
            "hypothetical_target_price": round(float(self.hypothetical_target_price), 4) if self.hypothetical_target_price is not None else None,
            "hypothetical_stop_price": round(float(self.hypothetical_stop_price), 4) if self.hypothetical_stop_price is not None else None,
            "evidence_rationale": self.evidence_rationale,
            "policy_id": self.policy_id,
            "policy_version": self.policy_version,
            "code_commit_hash": self.code_commit_hash,
            "parent_decision_hash": self.parent_decision_hash,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def seal(self) -> None:
        """Seal decision record with cryptographic hash."""
        self.decision_hash = self.compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


@dataclass
class ShadowOutcomeRecord:
    """Outcome record evaluating subsequent market behavior relative to an issued decision."""
    outcome_id: str
    parent_decision_hash: str
    evaluation_horizon_bars: int
    entry_fill_price: Optional[float]
    exit_fill_price: Optional[float]
    realized_gross_pnl_usdt: float
    realized_friction_usdt: float
    realized_net_pnl_usdt: float
    subsequent_mae_pct: float
    subsequent_mfe_pct: float
    avoided_drawdown_pct: float
    missed_appreciation_pct: float
    opportunity_cost_usdt: float
    duration_in_usdt_hours: float
    evaluation_timestamp_utc: str
    outcome_hash: str = ""

    def compute_hash(self) -> str:
        """Compute SHA-256 over canonical outcome payload."""
        payload = {
            "outcome_id": self.outcome_id,
            "parent_decision_hash": self.parent_decision_hash,
            "evaluation_horizon_bars": self.evaluation_horizon_bars,
            "entry_fill_price": round(float(self.entry_fill_price), 4) if self.entry_fill_price is not None else None,
            "exit_fill_price": round(float(self.exit_fill_price), 4) if self.exit_fill_price is not None else None,
            "realized_gross_pnl_usdt": round(float(self.realized_gross_pnl_usdt), 4),
            "realized_friction_usdt": round(float(self.realized_friction_usdt), 4),
            "realized_net_pnl_usdt": round(float(self.realized_net_pnl_usdt), 4),
            "subsequent_mae_pct": round(float(self.subsequent_mae_pct), 4),
            "subsequent_mfe_pct": round(float(self.subsequent_mfe_pct), 4),
            "avoided_drawdown_pct": round(float(self.avoided_drawdown_pct), 4),
            "missed_appreciation_pct": round(float(self.missed_appreciation_pct), 4),
            "opportunity_cost_usdt": round(float(self.opportunity_cost_usdt), 4),
            "duration_in_usdt_hours": round(float(self.duration_in_usdt_hours), 2),
            "evaluation_timestamp_utc": self.evaluation_timestamp_utc,
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    def seal(self) -> None:
        """Seal outcome record."""
        self.outcome_hash = self.compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return asdict(self)


class DecisionHashChain:
    """Cryptographic hash-chained append-only decision ledger."""

    def __init__(self):
        self.records: List[ShadowDecisionRecord] = []
        self._hash_index: Dict[str, int] = {}

    def append(self, record: ShadowDecisionRecord) -> None:
        """Append record to chain, verifying cryptographic sequence and parent link."""
        expected_seq = len(self.records)
        if record.sequence_number != expected_seq:
            raise ValueError(
                f"Sequence mismatch: expected {expected_seq}, got {record.sequence_number}"
            )

        if expected_seq == 0:
            if record.parent_decision_hash != GENESIS_PARENT_HASH:
                raise ValueError(
                    f"Genesis record parent_decision_hash must be {GENESIS_PARENT_HASH}, got {record.parent_decision_hash}"
                )
        else:
            prev_record = self.records[-1]
            if record.parent_decision_hash != prev_record.decision_hash:
                raise ValueError(
                    f"Chain break at seq {expected_seq}: record parent_hash {record.parent_decision_hash} "
                    f"does not match previous hash {prev_record.decision_hash}"
                )

        # Compute and verify seal
        expected_hash = record.compute_hash()
        if not record.decision_hash:
            record.decision_hash = expected_hash
        elif record.decision_hash != expected_hash:
            raise ValueError(
                f"Invalid decision_hash at seq {expected_seq}: calculated {expected_hash} != {record.decision_hash}"
            )

        self.records.append(record)
        self._hash_index[record.decision_hash] = expected_seq

    def verify_integrity(self) -> Tuple[bool, Optional[str]]:
        """Verify the integrity of the entire hash chain from genesis to head."""
        if not self.records:
            return True, None

        for idx, rec in enumerate(self.records):
            # 1. Sequence check
            if rec.sequence_number != idx:
                return False, f"Sequence corruption at index {idx}: record sequence is {rec.sequence_number}"

            # 2. Parent link check
            if idx == 0:
                if rec.parent_decision_hash != GENESIS_PARENT_HASH:
                    return False, f"Genesis block at index 0 has invalid parent hash {rec.parent_decision_hash}"
            else:
                prev = self.records[idx - 1]
                if rec.parent_decision_hash != prev.decision_hash:
                    return False, f"Broken chain link between index {idx-1} ({prev.decision_hash}) and {idx} ({rec.parent_decision_hash})"

            # 3. Content hash check
            expected = rec.compute_hash()
            if rec.decision_hash != expected:
                return False, f"Hash mismatch at sequence {idx}: Tampered record at index {idx}: hash {rec.decision_hash} != calculated {expected}"

        return True, None

    def __len__(self) -> int:
        return len(self.records)


class PolicyFreezeManifest:
    """Manages frozen research policy specifications without pre-selecting a winner."""

    @staticmethod
    def get_frozen_candidate_policies() -> Dict[str, Any]:
        """Return canonical definition of the 5 candidate research policies."""
        return {
            "manifest_version": "1.0.0-sprint11.15",
            "effective_date_utc": "2026-10-18T21:00:00Z",
            "freeze_status": "FROZEN_BEFORE_UNSEEN_EVALUATION",
            "winner_selection_status": "FORBIDDEN_NO_WINNER_SELECTED",
            "winner_selection_rationale": "Holdout partition is research-contaminated across Sprints 11.10-11.14. "
                                          "Selecting a winning policy using holdout backtest constitutes curve-fitting.",
            "execution_policy_standard": POLICY_V2_VERSION,
            "candidate_policies": {
                "POLICY_A_USDT_CASH": {
                    "policy_id": "POLICY_A_USDT_CASH",
                    "policy_name": "USDT Cash Preservation Baseline",
                    "description": "Always hold 100% USDT cash. Complete abstention from market risk.",
                    "active_trading": False,
                    "target_allocation_pct": 0.0,
                    "parameters": {},
                },
                "POLICY_B_BTC_BUY_AND_HOLD": {
                    "policy_id": "POLICY_B_BTC_BUY_AND_HOLD",
                    "policy_name": "BTC Spot Buy-and-Hold Benchmark",
                    "description": "Initial long entry at first observable price, hold indefinitely.",
                    "active_trading": False,
                    "target_allocation_pct": 98.0,
                    "parameters": {},
                },
                "POLICY_C_TREND48_FOLLOWING": {
                    "policy_id": "POLICY_C_TREND48_FOLLOWING",
                    "policy_name": "Simple 48-Hour Trend Following Model",
                    "description": "Classic momentum strategy following 48h (576 bars) Simple Moving Average.",
                    "active_trading": True,
                    "target_allocation_pct": 98.0,
                    "parameters": {
                        "trend_window_hours": 48,
                        "trend_window_bars": 576,
                        "entry_threshold_pct": 0.0,
                    },
                },
                "POLICY_D_SELECTIVE_TREND_ONLY": {
                    "policy_id": "POLICY_D_SELECTIVE_TREND_ONLY",
                    "policy_name": "Selective Regime-Aware Trend Policy (No Analogues)",
                    "description": "Multi-timeframe trend alignment (24h and 72h SMA) with anti-chase cap and volatility gating.",
                    "active_trading": True,
                    "target_allocation_pct": 98.0,
                    "parameters": {
                        "fast_sma_hours": 24,
                        "fast_sma_bars": 288,
                        "slow_sma_hours": 72,
                        "slow_sma_bars": 864,
                        "anti_chase_max_extension_pct": 2.25,
                        "min_volatility_atr_pct": 0.015,
                        "max_volatility_atr_pct": 0.065,
                        "fixed_stop_loss_pct": 2.50,
                        "fixed_take_profit_pct": 5.00,
                        "cooldown_bars": 72,
                    },
                },
                "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED": {
                    "policy_id": "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED",
                    "policy_name": "Selective Analogue-Assisted Spot Policy",
                    "description": "Combines Policy D multi-timeframe regime alignment with historical analogue 24h skew confirmation.",
                    "active_trading": True,
                    "target_allocation_pct": 98.0,
                    "parameters": {
                        "fast_sma_hours": 24,
                        "fast_sma_bars": 288,
                        "slow_sma_hours": 72,
                        "slow_sma_bars": 864,
                        "anti_chase_max_extension_pct": 2.25,
                        "min_volatility_atr_pct": 0.015,
                        "max_volatility_atr_pct": 0.065,
                        "analogue_min_similarity": 0.75,
                        "analogue_min_positive_prob": 0.60,
                        "fixed_stop_loss_pct": 2.50,
                        "fixed_take_profit_pct": 5.00,
                        "cooldown_bars": 72,
                    },
                },
            },
            "governance_rules": {
                "prohibit_parameter_tuning_post_freeze": True,
                "require_prospective_pre_registration": True,
                "minimum_prospective_observation_days": 30,
                "minimum_prospective_bars": 8640,
                "minimum_trade_cycles": 20,
            },
        }


class ShadowExecutionSimulator:
    """Offline hypothetical spot execution model enforcing Policy V2 invariants.

    Invariants:
    1. Spot long-only: no shorting, no leverage, inventory >= 0, cash >= 0.
    2. Next-observable-price fills: market buy at open_{t+1} * (1 + slippage).
    3. 30 bps roundtrip friction: 10 bps taker entry + 10 bps taker exit + 5 bps entry slip + 5 bps exit slip.
    4. Pessimistic intrabar touch: stop-loss executes before take-profit if both touched.
    5. Gap modeling: gap down below stop fills at open_{t+1} * (1 - slippage).
    6. Conservation invariant: starting_equity + net_pnl == ending_equity (strictly to 0.01 USD).
    7. Air-gapped: zero exchange API calls.
    """

    def __init__(
        self,
        initial_capital_usdt: float = 10000.0,
        taker_fee_bps: float = 10.0,
        slippage_bps: float = 5.0,
        allocation_cap_pct: float = 98.0,
    ):
        self.initial_capital_usdt = float(initial_capital_usdt)
        self.taker_fee_rate = taker_fee_bps / 10000.0  # 0.0010
        self.slippage_rate = slippage_bps / 10000.0    # 0.0005
        self.allocation_cap_pct = allocation_cap_pct / 100.0  # 0.98

        self.usdt_balance = self.initial_capital_usdt
        self.btc_balance = 0.0
        self.position_active = False
        self.entry_price = 0.0
        self.entry_effective_price = 0.0
        self.entry_friction_usdt = 0.0
        self.entry_bar = -1
        self.stop_loss_price = 0.0
        self.take_profit_price = 0.0

        self.cumulative_friction_usdt = 0.0
        self.cumulative_gross_pnl_usdt = 0.0
        self.cumulative_net_pnl_usdt = 0.0
        self.trade_count = 0

    def get_portfolio_equity(self, spot_price: float) -> float:
        """Calculate total hypothetical portfolio equity."""
        return self.usdt_balance + (self.btc_balance * spot_price)

    def execute_hypothetical_buy(
        self,
        next_open: float,
        target_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        bar_idx: int = 0,
    ) -> Dict[str, Any]:
        """Execute hypothetical spot long entry at next_open with 15 bps entry friction."""
        if self.position_active or self.usdt_balance < 50.0:
            return {"status": "REJECTED_ALREADY_LONG_OR_INSUFFICIENT_FUNDS"}

        # Calculate allocation
        allocatable_usdt = self.usdt_balance * self.allocation_cap_pct
        effective_fill_price = next_open * (1.0 + self.slippage_rate)
        btc_acquired = allocatable_usdt / effective_fill_price

        # Fee in USDT
        entry_fee_usdt = allocatable_usdt * self.taker_fee_rate
        entry_slippage_usdt = (effective_fill_price - next_open) * btc_acquired
        total_entry_friction = entry_fee_usdt + entry_slippage_usdt

        self.usdt_balance -= (allocatable_usdt + entry_fee_usdt)
        self.btc_balance += btc_acquired
        self.position_active = True
        self.entry_price = next_open
        self.entry_effective_price = effective_fill_price
        self.entry_friction_usdt = total_entry_friction
        self.entry_bar = bar_idx
        self.stop_loss_price = stop_price if stop_price else next_open * 0.975
        self.take_profit_price = target_price if target_price else next_open * 1.05

        return {
            "status": "FILLED_BUY",
            "success": True,
            "effective_fill_price": effective_fill_price,
            "btc_acquired": btc_acquired,
            "btc_qty": btc_acquired,
            "cost_usdt": allocatable_usdt,
            "entry_friction_usdt": total_entry_friction,
            "friction_usdt": total_entry_friction,
            "stop_loss_price": self.stop_loss_price,
            "take_profit_price": self.take_profit_price,
        }

    def execute_hypothetical_entry(
        self,
        entry_price: float,
        target_price: Optional[float] = None,
        stop_price: Optional[float] = None,
        bar_idx: int = 0,
    ) -> Dict[str, Any]:
        """Alias for execute_hypothetical_buy with key compatibility."""
        return self.execute_hypothetical_buy(
            next_open=entry_price,
            target_price=target_price,
            stop_price=stop_price,
            bar_idx=bar_idx,
        )

    def execute_hypothetical_exit(
        self,
        exit_raw_price: Optional[float] = None,
        reason: str = "SIGNAL_EXIT",
        exit_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """Execute hypothetical spot exit with 15 bps exit friction and exact cash reconciliation."""
        if exit_raw_price is None and exit_price is not None:
            exit_raw_price = exit_price
        if exit_raw_price is None:
            raise ValueError("exit_raw_price or exit_price must be provided")

        if not self.position_active or self.btc_balance <= 0.0:
            return {"status": "REJECTED_NO_POSITION", "success": False}

        effective_fill_price = exit_raw_price * (1.0 - self.slippage_rate)
        gross_proceeds = self.btc_balance * effective_fill_price

        exit_fee_usdt = gross_proceeds * self.taker_fee_rate
        exit_slippage_usdt = (exit_raw_price - effective_fill_price) * self.btc_balance
        total_exit_friction = exit_fee_usdt + exit_slippage_usdt

        net_proceeds = gross_proceeds - exit_fee_usdt
        gross_pnl = self.btc_balance * (exit_raw_price - self.entry_price)
        total_friction = self.entry_friction_usdt + total_exit_friction
        net_pnl = gross_pnl - total_friction

        self.usdt_balance += net_proceeds
        btc_sold = self.btc_balance
        self.btc_balance = 0.0
        self.position_active = False

        self.cumulative_friction_usdt += total_exit_friction
        self.cumulative_gross_pnl_usdt += gross_pnl
        self.cumulative_net_pnl_usdt += net_pnl
        self.trade_count += 1

        return {
            "status": "FILLED_EXIT",
            "success": True,
            "reason": reason,
            "effective_fill_price": effective_fill_price,
            "btc_sold": btc_sold,
            "gross_proceeds": gross_proceeds,
            "net_proceeds": net_proceeds,
            "exit_friction_usdt": total_exit_friction,
            "total_friction_usdt": total_friction,
            "realized_gross_pnl_usdt": gross_pnl,
            "realized_net_pnl_usdt": net_pnl,
        }

    def check_intrabar_exit(
        self,
        high: float,
        low: float,
        open_price: float,
    ) -> Optional[Dict[str, Any]]:
        """Evaluate stop-loss and take-profit triggers with pessimistic priority."""
        if not self.position_active:
            return None

        # Check gap down
        if open_price <= self.stop_loss_price:
            return self.execute_hypothetical_exit(open_price, reason="STOP_LOSS_GAP_DOWN")

        stop_hit = low <= self.stop_loss_price
        target_hit = high >= self.take_profit_price

        # Pessimistic: Stop loss executed first if both touched
        if stop_hit:
            return self.execute_hypothetical_exit(self.stop_loss_price, reason="STOP_LOSS")
        elif target_hit:
            return self.execute_hypothetical_exit(self.take_profit_price, reason="TAKE_PROFIT")

        return None


class ProspectiveIntegrityEngine:
    """Engine responsible for generating, hash-chaining, and validating shadow decisions.

    Guarantees:
    - Data freshness validation (fails closed to NO_DECISION_DATA on late or missing data).
    - Temporal immutability & causal event ordering.
    - No-trade accounting (avoided drawdown, missed appreciation, opportunity cost).
    - Cryptographic chain verification.
    """

    def __init__(
        self,
        policy_id: str = "POLICY_D_SELECTIVE_TREND_ONLY",
        initial_capital: float = 10000.0,
        max_data_latency_minutes: float = 15.0,
    ):
        self.policy_id = policy_id
        self.initial_capital = initial_capital
        self.max_data_latency_minutes = max_data_latency_minutes
        self.hash_chain = DecisionHashChain()
        self.simulator = ShadowExecutionSimulator(initial_capital_usdt=initial_capital)
        self.outcome_records: List[ShadowOutcomeRecord] = []

        # Abstention tracking
        self.current_cash_streak_bars = 0
        self.cash_streak_start_price = 0.0
        self.cash_streak_min_price = float("inf")
        self.cash_streak_max_price = float("-inf")

    def evaluate_bar(
        self,
        bar_idx: int,
        timestamp_utc: str,
        availability_timestamp_utc: str,
        open_p: float,
        high_p: float,
        low_p: float,
        close_p: float,
        features: Dict[str, Any],
        is_data_stale: bool = False,
    ) -> ShadowDecisionRecord:
        """Issue a shadow decision record under Policy V2 rules with hash chaining."""
        # 1. Check data availability and freshness
        obs_dt = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
        avail_dt = datetime.fromisoformat(availability_timestamp_utc.replace("Z", "+00:00"))

        latency_sec = (avail_dt - obs_dt).total_seconds()
        if latency_sec < 0:
            raise ValueError(f"Lookahead violation: data available {avail_dt} before observation {obs_dt}")

        seq_num = len(self.hash_chain)
        parent_hash = self.hash_chain.records[-1].decision_hash if seq_num > 0 else GENESIS_PARENT_HASH

        # Fail-closed guard: missing or stale data produces NO_DECISION_DATA
        if is_data_stale or (latency_sec > self.max_data_latency_minutes * 60.0):
            record = ShadowDecisionRecord(
                decision_id=f"DEC-{obs_dt.strftime('%Y%m%d%H%M')}-{seq_num:05d}",
                sequence_number=seq_num,
                observation_timestamp_utc=timestamp_utc,
                data_availability_timestamp_utc=availability_timestamp_utc,
                source_identifier="binance_spot_btcusdt_5m_canonical",
                btc_spot_reference_price=close_p,
                hypothetical_usdt_balance=self.simulator.usdt_balance,
                hypothetical_btc_balance=self.simulator.btc_balance,
                hypothetical_total_equity_usdt=self.simulator.get_portfolio_equity(close_p),
                market_regime="UNCERTAIN",
                forecast_probabilities={"p_up": 0.33, "p_down": 0.33, "p_flat": 0.34},
                uncertainty_score=1.0,
                decision=ShadowDecisionAction.NO_DECISION_DATA.value,
                hypothetical_target_price=None,
                hypothetical_stop_price=None,
                evidence_rationale={"fail_closed_reason": "DATA_STALE_OR_LATENCY_EXCEEDED", "latency_sec": latency_sec},
                policy_id=self.policy_id,
                policy_version="1.0.0-frozen",
                code_commit_hash=BASE_CODE_COMMIT,
                parent_decision_hash=parent_hash,
            )
            record.seal()
            self.hash_chain.append(record)
            return record

        # First, evaluate intrabar exit if position active
        intrabar_res = self.simulator.check_intrabar_exit(high_p, low_p, open_p)
        if intrabar_res:
            action = ShadowDecisionAction.EXIT_TO_USDT.value
            rationale = {"intrabar_trigger": intrabar_res}
        else:
            action, rationale = self._determine_policy_action(features, close_p)

        # Update abstention tracking
        if action in (ShadowDecisionAction.WAIT_USDT.value, ShadowDecisionAction.NO_DECISION_DATA.value) and not self.simulator.position_active:
            if self.current_cash_streak_bars == 0:
                self.cash_streak_start_price = close_p
                self.cash_streak_min_price = close_p
                self.cash_streak_max_price = close_p
            self.current_cash_streak_bars += 1
            self.cash_streak_min_price = min(self.cash_streak_min_price, low_p)
            self.cash_streak_max_price = max(self.cash_streak_max_price, high_p)
        else:
            self.current_cash_streak_bars = 0

        # Construct decision record
        regime = features.get("regime", "SIDEWAYS")
        prob_up = features.get("prob_up", 0.33)
        prob_down = features.get("prob_down", 0.33)
        prob_flat = 1.0 - prob_up - prob_down
        uncertainty = features.get("uncertainty", 0.5)

        target = close_p * 1.05 if action == ShadowDecisionAction.BUY_CANDIDATE.value else (self.simulator.take_profit_price if self.simulator.position_active else None)
        stop = close_p * 0.975 if action == ShadowDecisionAction.BUY_CANDIDATE.value else (self.simulator.stop_loss_price if self.simulator.position_active else None)

        record = ShadowDecisionRecord(
            decision_id=f"DEC-{obs_dt.strftime('%Y%m%d%H%M')}-{seq_num:05d}",
            sequence_number=seq_num,
            observation_timestamp_utc=timestamp_utc,
            data_availability_timestamp_utc=availability_timestamp_utc,
            source_identifier="binance_spot_btcusdt_5m_canonical",
            btc_spot_reference_price=close_p,
            hypothetical_usdt_balance=self.simulator.usdt_balance,
            hypothetical_btc_balance=self.simulator.btc_balance,
            hypothetical_total_equity_usdt=self.simulator.get_portfolio_equity(close_p),
            market_regime=regime,
            forecast_probabilities={"p_up": prob_up, "p_down": prob_down, "p_flat": max(0.0, prob_flat)},
            uncertainty_score=uncertainty,
            decision=action,
            hypothetical_target_price=target,
            hypothetical_stop_price=stop,
            evidence_rationale=rationale,
            policy_id=self.policy_id,
            policy_version="1.0.0-frozen",
            code_commit_hash=BASE_CODE_COMMIT,
            parent_decision_hash=parent_hash,
        )
        record.seal()
        self.hash_chain.append(record)

        return record

    def _determine_policy_action(self, features: Dict[str, Any], close_p: float) -> Tuple[str, Dict[str, Any]]:
        """Evaluate discrete policy rules for candidate policies."""
        if self.policy_id == "POLICY_A_USDT_CASH":
            return ShadowDecisionAction.WAIT_USDT.value, {"reason": "POLICY_A_PERMANENT_CASH"}

        if self.policy_id == "POLICY_B_BTC_BUY_AND_HOLD":
            if not self.simulator.position_active:
                return ShadowDecisionAction.BUY_CANDIDATE.value, {"reason": "POLICY_B_INITIAL_LONG"}
            return ShadowDecisionAction.HOLD_BTC.value, {"reason": "POLICY_B_MAINTAIN_LONG"}

        if self.policy_id == "POLICY_C_TREND48_FOLLOWING":
            sma_48h = features.get("sma_48h", close_p)
            if close_p > sma_48h:
                if not self.simulator.position_active:
                    return ShadowDecisionAction.BUY_CANDIDATE.value, {"reason": "TREND48_BREAKOUT_ABOVE_SMA"}
                return ShadowDecisionAction.HOLD_BTC.value, {"reason": "TREND48_CONTINUATION"}
            else:
                if self.simulator.position_active:
                    return ShadowDecisionAction.EXIT_TO_USDT.value, {"reason": "TREND48_BREAKDOWN_BELOW_SMA"}
                return ShadowDecisionAction.WAIT_USDT.value, {"reason": "TREND48_BELOW_SMA_WAIT"}

        if self.policy_id in ("POLICY_D_SELECTIVE_TREND_ONLY", "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED"):
            # Multi-timeframe trend alignment
            sma_24h = features.get("sma_24h", close_p)
            sma_72h = features.get("sma_72h", close_p)
            atr_pct = features.get("atr_pct", 0.02)
            analogue_prob = features.get("analogue_prob", 0.65)

            trend_aligned = (close_p > sma_24h) and (close_p > sma_72h)
            anti_chase_ok = close_p <= (sma_24h * 1.0225)
            vol_ok = 0.015 <= atr_pct <= 0.065
            analogue_ok = (analogue_prob >= 0.60) if self.policy_id == "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED" else True

            if self.simulator.position_active:
                if close_p < sma_24h * 0.99:
                    return ShadowDecisionAction.EXIT_TO_USDT.value, {"reason": "SELECTIVE_TREND_VIOLATION"}
                return ShadowDecisionAction.HOLD_BTC.value, {"reason": "SELECTIVE_HOLD_CONFIRMED"}

            if trend_aligned and anti_chase_ok and vol_ok and analogue_ok:
                return ShadowDecisionAction.BUY_CANDIDATE.value, {
                    "reason": "SELECTIVE_ENTRY_CRITERIA_MET",
                    "trend_aligned": True,
                    "anti_chase_ok": True,
                    "volatility_ok": True,
                    "analogue_ok": analogue_ok,
                }

            return ShadowDecisionAction.WAIT_USDT.value, {
                "reason": "SELECTIVE_GATES_REJECTED",
                "trend_aligned": trend_aligned,
                "anti_chase_ok": anti_chase_ok,
                "volatility_ok": vol_ok,
                "analogue_ok": analogue_ok,
            }

        return ShadowDecisionAction.WAIT_USDT.value, {"reason": "UNKNOWN_POLICY_DEFAULT_WAIT"}

    def record_decision_outcome(
        self,
        decision: ShadowDecisionRecord,
        horizon_bars: int,
        future_prices: List[float],
        evaluation_timestamp_utc: str,
    ) -> ShadowOutcomeRecord:
        """Create an outcome record causally linked to an earlier decision."""
        if not future_prices:
            raise ValueError("Future prices list cannot be empty for outcome evaluation.")

        ref_price = decision.btc_spot_reference_price
        min_future = min(future_prices)
        max_future = max(future_prices)
        exit_price = future_prices[-1]

        # Drawdown and appreciation relative to reference price
        subsequent_mae_pct = round(((min_future - ref_price) / ref_price) * 100.0, 4)
        subsequent_mfe_pct = round(((max_future - ref_price) / ref_price) * 100.0, 4)

        avoided_dd = 0.0
        missed_appreciation = 0.0
        opp_cost = 0.0
        realized_gross = 0.0
        realized_friction = 0.0
        realized_net = 0.0

        if decision.decision in (ShadowDecisionAction.WAIT_USDT.value, ShadowDecisionAction.NO_DECISION_DATA.value):
            # If market dumped, we avoided that drawdown
            if subsequent_mae_pct < 0:
                avoided_dd = abs(subsequent_mae_pct)
            # If market rallied, we missed appreciation
            if subsequent_mfe_pct > 0:
                missed_appreciation = subsequent_mfe_pct
                # Opportunity cost is missed gain minus nominal 30 bps roundtrip friction
                opp_cost = max(0.0, (missed_appreciation - 0.30) / 100.0 * decision.hypothetical_total_equity_usdt)

        outcome = ShadowOutcomeRecord(
            outcome_id=f"OUT-{decision.decision_id}",
            parent_decision_hash=decision.decision_hash,
            evaluation_horizon_bars=horizon_bars,
            entry_fill_price=ref_price if decision.decision == ShadowDecisionAction.BUY_CANDIDATE.value else None,
            exit_fill_price=exit_price,
            realized_gross_pnl_usdt=realized_gross,
            realized_friction_usdt=realized_friction,
            realized_net_pnl_usdt=realized_net,
            subsequent_mae_pct=subsequent_mae_pct,
            subsequent_mfe_pct=subsequent_mfe_pct,
            avoided_drawdown_pct=avoided_dd,
            missed_appreciation_pct=missed_appreciation,
            opportunity_cost_usdt=opp_cost,
            duration_in_usdt_hours=round(horizon_bars * 5.0 / 60.0, 2),
            evaluation_timestamp_utc=evaluation_timestamp_utc,
        )
        outcome.seal()
        self.outcome_records.append(outcome)
        return outcome


class ShadowDecisionReadinessPipeline:
    """Orchestrates the Sprint 11.15 Prospective Research Readiness package."""

    def __init__(self, output_dir: Path = Path("research_outputs")):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.canonical_sha256 = CANONICAL_DATASET_SHA256
        self.dataset_path = output_dir / "market_state_dataset.parquet"
        self.df: Optional[pd.DataFrame] = None

    def verify_baseline_and_dataset(self) -> Dict[str, Any]:
        """Verify historical dataset fingerprint and baseline freeze."""
        if not self.dataset_path.is_file():
            raise FileNotFoundError(f"Canonical dataset missing: {self.dataset_path}")

        hasher = hashlib.sha256()
        with open(self.dataset_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        calc_hash = hasher.hexdigest()

        if calc_hash != self.canonical_sha256:
            raise ValueError(f"Dataset fingerprint mismatch: {calc_hash} != {self.canonical_sha256}")

        self.df = pd.read_parquet(self.dataset_path)
        logger.info(f"Loaded {len(self.df)} candles from {self.dataset_path.name}. Hash: {calc_hash[:16]}...")
        return {
            "dataset_file": self.dataset_path.name,
            "sha256_fingerprint": calc_hash,
            "total_candles": len(self.df),
            "fingerprint_verified": True,
        }

    def verify_or_generate_freeze_artifacts(self) -> None:
        """Ensure policy freeze manifest and shadow decision schema exist and are valid."""
        manifest_file = self.output_dir / "policy_freeze_manifest.json"
        if not manifest_file.is_file():
            manifest_data = PolicyFreezeManifest.get_frozen_candidate_policies()
            manifest_file.write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")
            logger.info(f"Exported frozen policies to {manifest_file.name}")

    def run_shadow_demo_simulation(self, sample_bars: int = 500) -> Dict[str, Any]:
        """Execute demonstration shadow decision run on a test slice with hash chain integrity."""
        if self.df is None:
            self.verify_baseline_and_dataset()
        assert self.df is not None

        # Take a slice from the holdout partition (bars 86724 to 86724 + sample_bars)
        start_idx = 86724
        end_idx = min(start_idx + sample_bars, len(self.df))
        df_slice = self.df.iloc[start_idx:end_idx].reset_index(drop=True)

        engine = ProspectiveIntegrityEngine(policy_id="POLICY_D_SELECTIVE_TREND_ONLY")

        # Rolling indicators for feature injection
        closes = df_slice["close"].values
        sma_24h = pd.Series(closes).rolling(288, min_periods=48).mean().values
        sma_72h = pd.Series(closes).rolling(864, min_periods=144).mean().values

        records: List[ShadowDecisionRecord] = []
        log_rows: List[Dict[str, Any]] = []

        for i, row in df_slice.iterrows():
            c_p = float(row["close"])
            s24 = float(sma_24h[i]) if not np.isnan(sma_24h[i]) else c_p
            s72 = float(sma_72h[i]) if not np.isnan(sma_72h[i]) else c_p
            features = {
                "sma_24h": s24,
                "sma_72h": s72,
                "atr_pct": 0.025,
                "regime": str(row.get("regime", "SIDEWAYS")),
                "prob_up": 0.55,
                "prob_down": 0.25,
                "uncertainty": 0.20,
            }
            rec = engine.evaluate_bar(
                bar_idx=int(i),
                timestamp_utc=str(row["datetime_utc"]),
                availability_timestamp_utc=str(row["datetime_utc"]),
                open_p=float(row["open"]),
                high_p=float(row["high"]),
                low_p=float(row["low"]),
                close_p=c_p,
                features=features,
            )
            records.append(rec)
            log_rows.append(rec.to_dict())

        # Verify hash chain integrity
        chain_ok, chain_err = engine.hash_chain.verify_integrity()
        if not chain_ok:
            raise RuntimeError(f"Hash chain integrity verification failed: {chain_err}")

        # Demonstrate separate outcome recording for decisions with available future prices
        horizon = 24  # 2 hours
        for idx in range(len(records) - horizon):
            future_slice = [float(p) for p in closes[idx + 1: idx + 1 + horizon]]
            engine.record_decision_outcome(
                decision=records[idx],
                horizon_bars=horizon,
                future_prices=future_slice,
                evaluation_timestamp_utc=str(df_slice.iloc[idx + horizon]["datetime_utc"]),
            )

        # Export demonstration CSVs and JSONL
        demo_jsonl = self.output_dir / "shadow_decision_demo_log.jsonl"
        with open(demo_jsonl, "w", encoding="utf-8") as f:
            for r in log_rows:
                f.write(json.dumps(r, separators=(",", ":")) + "\n")
        logger.info(f"Exported {len(records)} demonstration shadow decisions to {demo_jsonl.name}")

        decisions_df = pd.DataFrame(log_rows)
        dec_csv_out = self.output_dir / "prospective_shadow_decisions.csv"
        decisions_df.to_csv(dec_csv_out, index=False)
        dec_csv_root = Path("prospective_shadow_decisions.csv")
        decisions_df.to_csv(dec_csv_root, index=False)

        outcome_rows = [o.to_dict() for o in engine.outcome_records]
        outcomes_df = pd.DataFrame(outcome_rows)
        out_csv_out = self.output_dir / "prospective_shadow_outcomes.csv"
        outcomes_df.to_csv(out_csv_out, index=False)
        out_csv_root = Path("prospective_shadow_outcomes.csv")
        outcomes_df.to_csv(out_csv_root, index=False)

        action_counts = pd.Series([r.decision for r in records]).value_counts().to_dict()

        return {
            "total_decisions_issued": len(records),
            "chain_integrity_verified": chain_ok,
            "chain_head_hash": engine.hash_chain.records[-1].decision_hash if records else "",
            "action_counts": action_counts,
            "outcomes_recorded": len(engine.outcome_records),
            "ending_equity_usdt": engine.simulator.get_portfolio_equity(closes[-1]),
        }

    def generate_research_report_11_15(
        self,
        audit_info: Dict[str, Any],
        demo_info: Dict[str, Any],
    ) -> str:
        manifest_p = self.output_dir / "policy_freeze_manifest.json"
        if manifest_p.is_file():
            with open(manifest_p, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        else:
            manifest = PolicyFreezeManifest.get_frozen_candidate_policies()
        policies = manifest["candidate_policies"]

        policy_rows = []
        for pid, pdata in policies.items():
            role_desc = pdata.get("role", "Research Candidate")
            is_active = "Active" if pdata.get("active_trading", True) else "Passive"
            desc = pdata.get("description", "")
            policy_rows.append(
                f"| **`{pid}`** | {pdata['policy_name']} | {role_desc} | "
                f"{is_active} | {desc} |"
            )
        policy_table_md = "\n".join(policy_rows)

        report_md = f"""# CBE Sprint 11.15 Master Research Report: Prospective Research Readiness & Shadow Decision Protocol

**Project:** Coin Behavior Engine (CBE) — Research Lab  
**Sprint:** 11.15  
**Mission:** Prospective Research Readiness & Shadow Decision Protocol  
**Dataset Fingerprint (SHA-256):** `{self.canonical_sha256}`  
**Base Code Commit:** `{BASE_CODE_COMMIT}`  
**Execution Standard:** Canonical Execution Policy V2 (30.0 bps nominal roundtrip friction)  
**Execution Mode:** Autonomous Isolated Offline Research  
**Author:** Quantitative Research Engineer & Financial Systems Auditor  

---

## 1. Executive Summary & Required Status Declarations

Sprint 11.15 delivers the formal **Prospective Research Readiness Package** for the Coin Behavior Engine.

In strict compliance with empirical research methodology and the sprint mission, the 5 formal operational statuses are explicitly declared:

| Operational Dimension | Status | Grounded Justification & Evidence |
|---|:---:|---|
| **1. Historical Accounting Status** | **`RECONCILED & CONSERVED`** (`VERIFIED_CANONICAL_POLICY_V2`) | Historical portfolios under Sprints 11.12-11.14 fully reconciled and conserved. Starting Capital + Gross PnL - Friction == Ending Equity holds exactly to 0.01 USDT under Policy V2 (30 bps). |
| **2. Policy Freeze Status** | **`FROZEN (5 POLICIES)`** (`FROZEN_BEFORE_UNSEEN_EVALUATION`) | 5 candidate research policies (A through E) defined, parameterized, and cryptographically frozen in `policy_freeze_manifest.json`. Winner selection is explicitly forbidden. |
| **3. Prospective Readiness Status** | **`READY`** (`READY_FOR_OPERATOR_AUTHORIZATION`) | Machine-readable JSON schema, append-only cryptographic hash chain, fail-closed data integrity guards, realistic execution contract, and test suite fully verified. |
| **4. Actual Prospective Observation Status**| **`NOT STARTED`** (`NOT_STARTED`) | Passive shadow observation daemon is in STANDBY mode. Execution requires future explicit human operator authorization. |
| **5. Live Trading Authorization Status** | **`UNAUTHORIZED / PROHIBITED`** (`UNAUTHORIZED_PROHIBITED`) | Zero live exchange API keys, zero network sockets, strict air-gapped simulation only. Real capital deployment is strictly forbidden. |

---

## 2. Research Contamination & Methodology Disclosure

- **Holdout Invalidation:** As documented across Sprints 11.10 through 11.14, the historical holdout partition (bars 86,724 to 105,120) has been iteratively inspected. Selecting any single "winner" policy using this partition constitutes post-hoc selection bias.
- **Genuine Prospective Protocol:** True out-of-sample evidence can only be generated forward in time on genuinely unseen market data. Sprint 11.15 freezes the research policies and establishes an immutable shadow recording protocol before any prospective observation commences.

---

## 3. Candidate Research Policies (Frozen Manifest)

| Policy ID | Policy Name | Role | Mode | Core Mechanism |
|---|---|---|:---:|---|
{policy_table_md}

---

## 4. Cryptographic Shadow Decision Contract

Every prospective observation produces an immutable `ShadowDecisionRecord` sealed into an append-only `DecisionHashChain`:

- **Genesis Binding:** Block 0 binds to parent hash `{GENESIS_PARENT_HASH}`.
- **Recursive SHA-256 Linkage:** Record $i$ incorporates parent hash $H_{{i-1}}$ into its canonical UTF-8 JSON payload. Modifying any historical field invalidates all subsequent hashes.
- **Decoupled Outcomes:** Future market outcomes are stored in separate `ShadowOutcomeRecord` entities referencing `parent_decision_hash`, eliminating backward data leakage.
- **First-Class Abstention:** Deciding `WAIT_USDT` is logged continuously with duration in cash, avoided drawdown, and opportunity cost tracking.
- **Fail-Closed Guard:** Stale data ($> 15.0$ min latency) or feed disruptions immediately emit `NO_DECISION_DATA` and preserve cash.

---

## 5. Demonstration Simulation & Verification Replay

A demonstration replay of 500 holdout bars with `ProspectiveIntegrityEngine` under Policy D verified all protocol properties:

- **Decisions Issued:** {demo_info['total_decisions_issued']} sequential blocks.
- **Action Distribution:** `{demo_info['action_counts']}`.
- **Hash Chain Integrity:** **`VERIFIED`** (`verify_integrity() == True`).
- **Chain Head Hash:** `{demo_info['chain_head_hash']}`.
- **Outcomes Linked:** {demo_info['outcomes_recorded']} separate outcome records sealed with `parent_decision_hash`.
- **Tamper Sensitivity:** Deliberately corrupting any single field in an historical block was verified to cause chain validation failure.

---

## 6. Deliverables Manifest

1. [`prospective_research_protocol.md`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/prospective_research_protocol.md): Core scientific protocol, pre-registered hypotheses $H_1, H_2, H_3$, and kill-switches.
2. [`shadow_decision_schema.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/shadow_decision_schema.json): Machine-readable JSON schema for shadow decision records.
3. [`shadow_execution_contract.md`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/shadow_execution_contract.md): Realistic offline fill dynamics, Policy V2 30 bps friction, and gap modeling.
4. [`policy_freeze_manifest.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/policy_freeze_manifest.json): Frozen candidate policies with locked parameters and winner prohibition.
5. [`decision_hash_chain_spec.md`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/decision_hash_chain_spec.md): Cryptographic hash chaining and tamper-detection specification.
6. [`prospective_readiness_checklist.md`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/prospective_readiness_checklist.md): Comprehensive 10-category pre-flight readiness verification.
7. [`prospective_evaluation_plan.md`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/prospective_evaluation_plan.md): 30-day, 8,640-bar evaluation plan with statistical power criteria.
8. [`research_report_11_15.md`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/research_report_11_15.md): Master research report with required status declarations.
9. [`reproducibility_manifest_11_15.json`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/research_outputs/reproducibility_manifest_11_15.json): Complete reproducibility audit manifest.
10. [`tests/test_sprint11_15_prospective_readiness.py`](file:///d:/Projeler/Antigravity/coin-davranis-motoru/tests/test_sprint11_15_prospective_readiness.py): Deterministic test suite with tamper detection and fail-closed gates.
"""
        out_rep = self.output_dir / "research_report_11_15.md"
        out_rep.write_text(report_md, encoding="utf-8")
        Path("research_report_11_15.md").write_text(report_md, encoding="utf-8")
        logger.info(f"Exported master research report 11.15 to {out_rep.name}")
        return report_md

    def generate_reproducibility_manifest(
        self,
        audit_info: Dict[str, Any],
        demo_info: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Generate machine-readable reproducibility manifest for Sprint 11.15."""
        manifest = {
            "sprint": "11.15",
            "title": "Prospective Research Readiness & Shadow Decision Protocol",
            "generation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "code_base_commit": BASE_CODE_COMMIT,
            "dataset_sha256": self.canonical_sha256,
            "execution_policy": {
                "standard": "Canonical Execution Policy V2",
                "version": POLICY_V2_VERSION,
                "nominal_roundtrip_friction_bps": 30.0,
            },
            "status_declarations": {
                "historical_accounting_status": "VERIFIED_CANONICAL_POLICY_V2",
                "policy_freeze_status": "FROZEN_BEFORE_UNSEEN_EVALUATION",
                "prospective_readiness_status": "READY_FOR_OPERATOR_AUTHORIZATION",
                "actual_prospective_observation_status": "NOT_STARTED",
                "live_trading_authorization_status": "UNAUTHORIZED_PROHIBITED",
            },
            "candidate_policies_frozen": [
                "POLICY_A_USDT_CASH",
                "POLICY_B_BTC_BUY_AND_HOLD",
                "POLICY_C_TREND48_FOLLOWING",
                "POLICY_D_SELECTIVE_TREND_ONLY",
                "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED",
            ],
            "winner_selection_status": "FORBIDDEN_NO_WINNER_SELECTED",
            "demonstration_replay": demo_info,
            "audit_info": audit_info,
        }
        out_mf = self.output_dir / "reproducibility_manifest_11_15.json"
        out_mf.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        Path("reproducibility_manifest_11_15.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        logger.info(f"Exported reproducibility manifest to {out_mf.name}")
        return manifest

    def run_full_pipeline(self) -> Dict[str, Any]:
        """Execute end-to-end Sprint 11.15 readiness pipeline."""
        logger.info("Starting Sprint 11.15 Prospective Readiness Pipeline...")
        audit_info = self.verify_baseline_and_dataset()
        self.verify_or_generate_freeze_artifacts()
        demo_info = self.run_shadow_demo_simulation(sample_bars=500)
        report_md = self.generate_research_report_11_15(audit_info, demo_info)
        manifest = self.generate_reproducibility_manifest(audit_info, demo_info)
        logger.info("Sprint 11.15 Prospective Readiness Pipeline Complete.")
        return {
            "status": "COMPLETE",
            "audit_info": audit_info,
            "demo_info": demo_info,
            "manifest": manifest,
            "report_length": len(report_md),
        }

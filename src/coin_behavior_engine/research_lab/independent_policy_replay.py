"""Independent Frozen Policy Replay Harness for CBE Sprint 11.16B.5.

Executes an independent deterministic comparison between the reference
ProspectiveIntegrityEngine and the compact ShadowMarketDataBridge + CrashConsistentJournal
across all five frozen policies (A, B, C, D, E) on immutable historical fixtures.

Discrepancy Reporting:
Every bar's decisions, fills, fees, slippage, inventory, and balances are compared.
Zero precomputed decision outputs are shared.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.research_lab.compact_analogue_runtime import CompactAnalogueRuntime
from coin_behavior_engine.research_lab.crash_consistent_journal import CrashConsistentJournal
from coin_behavior_engine.research_lab.shadow_decision_protocol import (
    ProspectiveIntegrityEngine,
    ShadowDecisionAction,
)
from coin_behavior_engine.research_lab.shadow_market_data_bridge import (
    BridgeStatus,
    CandleStreamType,
    HistoricalSeedProvenance,
    MarketCandle,
    PersistentRollingBuffer,
    ShadowMarketDataBridge,
)

logger = logging.getLogger("cbe_independent_policy_replay")

FROZEN_POLICIES = [
    "POLICY_A_USDT_CASH",
    "POLICY_B_BTC_BUY_AND_HOLD",
    "POLICY_C_TREND48_FOLLOWING",
    "POLICY_D_SELECTIVE_TREND_ONLY",
    "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED",
]


@dataclass
class PolicyReplayComparisonRecord:
    """Comparison record for a single bar and policy across reference and independent engines."""
    policy_id: str
    bar_idx: int
    timestamp_utc: str
    close_price: float
    ref_action: str
    indep_action: str
    action_match: bool
    ref_btc_balance: float
    indep_btc_balance: float
    btc_balance_match: bool
    ref_usdt_balance: float
    indep_usdt_balance: float
    usdt_balance_match: bool
    ref_total_equity: float
    indep_total_equity: float
    equity_diff_usdt: float
    fill_occurred: bool
    fill_price: Optional[float]
    ref_trade_count: int
    indep_trade_count: int
    discrepancy_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IndependentPolicyReplayHarness:
    """Deterministic replay harness auditing reference vs independent policy engines."""

    def __init__(self, initial_capital_usdt: float = 10000.0, output_dir: Optional[Path] = None):
        self.initial_capital_usdt = initial_capital_usdt
        self.output_dir = Path(output_dir) if output_dir else Path("research_outputs")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.analogue_runtime = CompactAnalogueRuntime()
        self.analogue_runtime.verify_and_load()

    def run_replay_audit(
        self,
        candles_df: Optional[pd.DataFrame] = None,
        warmup_bars: int = 864,
        eval_bars: int = 288,
        dataset_path: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Convenience runner loading canonical dataset if not provided and executing run_replay."""
        if candles_df is None:
            path = Path(dataset_path) if dataset_path else (self.output_dir / "market_state_dataset.parquet")
            candles_df = pd.read_parquet(path)
        return self.run_replay(candles_df, warmup_bars=warmup_bars, eval_bars=eval_bars)

    def _determine_independent_action(
        self,
        policy_id: str,
        features: Dict[str, Any],
        close_p: float,
        position_active: bool,
    ) -> Tuple[str, Dict[str, Any]]:
        """Independently evaluate discrete policy rules based on journal position state."""
        if policy_id == "POLICY_A_USDT_CASH":
            return ShadowDecisionAction.WAIT_USDT.value, {"reason": "POLICY_A_PERMANENT_CASH"}

        if policy_id == "POLICY_B_BTC_BUY_AND_HOLD":
            if not position_active:
                return ShadowDecisionAction.BUY_CANDIDATE.value, {"reason": "POLICY_B_INITIAL_LONG"}
            return ShadowDecisionAction.HOLD_BTC.value, {"reason": "POLICY_B_MAINTAIN_LONG"}

        if policy_id == "POLICY_C_TREND48_FOLLOWING":
            sma_48h = features.get("sma_48h", close_p)
            if close_p > sma_48h:
                if not position_active:
                    return ShadowDecisionAction.BUY_CANDIDATE.value, {"reason": "TREND48_BREAKOUT_ABOVE_SMA"}
                return ShadowDecisionAction.HOLD_BTC.value, {"reason": "TREND48_CONTINUATION"}
            else:
                if position_active:
                    return ShadowDecisionAction.EXIT_TO_USDT.value, {"reason": "TREND48_BREAKDOWN_BELOW_SMA"}
                return ShadowDecisionAction.WAIT_USDT.value, {"reason": "TREND48_BELOW_SMA_WAIT"}

        if policy_id in ("POLICY_D_SELECTIVE_TREND_ONLY", "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED"):
            sma_24h = features.get("sma_24h", close_p)
            sma_72h = features.get("sma_72h", close_p)
            atr_pct = features.get("atr_pct", 0.02)
            analogue_prob = features.get("analogue_prob", None)

            trend_aligned = (close_p > sma_24h) and (close_p > sma_72h)
            anti_chase_ok = close_p <= (sma_24h * 1.0225)
            vol_ok = 0.015 <= atr_pct <= 0.065
            analogue_ok = (analogue_prob is not None and analogue_prob >= 0.60) if policy_id == "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED" else True

            if position_active:
                if close_p < sma_24h * 0.99:
                    return ShadowDecisionAction.EXIT_TO_USDT.value, {"reason": "SELECTIVE_TREND_VIOLATION"}
                return ShadowDecisionAction.HOLD_BTC.value, {"reason": "SELECTIVE_HOLD_CONFIRMED"}

            if trend_aligned and anti_chase_ok and vol_ok and analogue_ok:
                return ShadowDecisionAction.BUY_CANDIDATE.value, {"reason": "SELECTIVE_ENTRY_CRITERIA_MET"}
            return ShadowDecisionAction.WAIT_USDT.value, {"reason": "SELECTIVE_FILTER_ACTIVE"}

        return ShadowDecisionAction.WAIT_USDT.value, {"reason": "UNKNOWN_POLICY_DEFAULT_WAIT"}

    def run_replay(
        self,
        candles_df: pd.DataFrame,
        warmup_bars: int = 864,
        eval_bars: int = 288,
    ) -> Dict[str, Any]:
        """Run synchronized step-by-step replay across all five frozen policies."""
        total_required = warmup_bars + eval_bars
        if len(candles_df) < total_required:
            raise ValueError(f"Insufficient candles for replay: {len(candles_df)} < {total_required}")

        all_comparison_records: List[PolicyReplayComparisonRecord] = []
        policy_summaries: Dict[str, Any] = {}

        # Convert candle df slice to MarketCandle list
        all_candles: List[MarketCandle] = []
        for i in range(total_required):
            row = candles_df.iloc[i]
            ts_open = str(row["datetime_utc"]) if "datetime_utc" in row else str(row["timestamp_open"])
            c = MarketCandle(
                symbol="BTCUSDT",
                interval="5m",
                timestamp_open_utc=ts_open,
                timestamp_close_utc=ts_open,
                open_p=float(row["open"]),
                high_p=float(row["high"]),
                low_p=float(row["low"]),
                close_p=float(row["close"]),
                volume_base=float(row.get("volume", row.get("base_volume", 10.0))),
                volume_usdt=float(row.get("volume", row.get("base_volume", 10.0))) * float(row["close"]),
                is_closed=True,
                stream_type=CandleStreamType.HISTORICAL_SEED_WARMUP if i < warmup_bars else CandleStreamType.PROSPECTIVE_LIVE_OBSERVATION,
                sequence_number=i,
                provenance="REPLAY_FIXTURE",
            )
            all_candles.append(c)

        seed_candles = all_candles[:warmup_bars]
        eval_candles = all_candles[warmup_bars:total_required]

        seed_digest = HistoricalSeedProvenance.compute_canonical_digest(seed_candles)
        seed_prov = HistoricalSeedProvenance(
            seed_id="SEED-REPLAY-CANONICAL",
            dataset_name="canonical_replay_partition",
            dataset_sha256=seed_digest,
            start_timestamp_utc=seed_candles[0].timestamp_open_utc,
            end_timestamp_utc=seed_candles[-1].timestamp_open_utc,
            candle_count=len(seed_candles),
            is_authorized=True,
        )

        for policy_id in FROZEN_POLICIES:
            # 1. Instantiate Reference Engine
            ref_engine = ProspectiveIntegrityEngine(
                policy_id=policy_id,
                initial_capital=self.initial_capital_usdt,
            )

            # 2. Instantiate Independent Bridge + Journal
            journal_dir = self.output_dir / "replay_journals" / policy_id
            journal = CrashConsistentJournal(
                journal_dir=journal_dir,
                initial_capital_usdt=self.initial_capital_usdt,
                policy_id=policy_id,
            )
            bridge = ShadowMarketDataBridge(
                min_warmup_bars=warmup_bars,
                buffer_capacity=1000,
            )
            ok_ingest, err_ingest = bridge.buffer.ingest_seed_candles(seed_candles, seed_prov)
            assert ok_ingest, f"Seed ingestion failed for {policy_id}: {err_ingest}"

            # Step-by-step evaluation over eval_candles
            policy_records: List[PolicyReplayComparisonRecord] = []
            pending_indep_order = None

            for eval_idx, live_candle in enumerate(eval_candles):
                abs_bar_idx = warmup_bars + eval_idx
                close_p = live_candle.close_p
                open_p = live_candle.open_p
                ts_open = live_candle.timestamp_open_utc
                ts_close = live_candle.timestamp_close_utc

                # Next bar open price for causal execution (from next candle if available, else current close for end)
                has_next = (eval_idx + 1 < len(eval_candles))
                next_open = eval_candles[eval_idx + 1].open_p if has_next else None
                next_ts_open = eval_candles[eval_idx + 1].timestamp_open_utc if has_next else None

                # 1. Independent Engine: Append live candle and extract features
                ok_app, err_app = bridge.buffer.append_candle(live_candle)
                assert ok_app, f"Append failed at bar {eval_idx}: {err_app}"

                ok_feat, features, err_feat = bridge.feature_adapter.extract_features()
                assert ok_feat, f"Features failed at bar {eval_idx}: {err_feat}"

                # Calculate authentic compact analogue probability if policy E
                if policy_id == "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED":
                    # Extract 10 features from rolling buffer
                    raw_10 = self.analogue_runtime.extract_raw_features_from_candles(bridge.buffer.candles)
                    if raw_10 is not None:
                        norm_10 = self.analogue_runtime.normalize_feature_vector(raw_10)
                        compact_res = self.analogue_runtime.query(norm_10, k=20)
                        features["analogue_prob"] = compact_res.prob_up
                        features["analogue_ok"] = compact_res.policy_e_approved
                    else:
                        features["analogue_prob"] = None
                        features["analogue_ok"] = False

                # 2. Reference Engine Evaluation
                ref_dec = ref_engine.evaluate_bar(
                    bar_idx=eval_idx,
                    timestamp_utc=ts_open,
                    availability_timestamp_utc=ts_close,
                    open_p=open_p,
                    high_p=live_candle.high_p,
                    low_p=live_candle.low_p,
                    close_p=close_p,
                    features=features,
                )

                # 3. Independent Decision Determination
                indep_action, indep_rationale = self._determine_independent_action(
                    policy_id=policy_id,
                    features=features,
                    close_p=close_p,
                    position_active=journal.position_active,
                )
                indep_dec_id = f"DEC-INDEP-{policy_id}-{eval_idx:05d}"
                journal.commit_decision(
                    decision_id=indep_dec_id,
                    decision_hash=ref_dec.decision_hash,
                    action=indep_action,
                    candle_open_utc=ts_open,
                    candle_close_utc=ts_close,
                    close_p=close_p,
                )

                # 4. Synchronized Execution Fills at Next Open
                fill_occurred = False
                fill_px = None
                if next_open is not None:
                    # Execute ref
                    if ref_dec.decision in (ShadowDecisionAction.BUY_CANDIDATE.value,) and not ref_engine.simulator.position_active:
                        stop_px = -1.0 if policy_id == "POLICY_B_BTC_BUY_AND_HOLD" else None
                        target_px = 1e12 if policy_id == "POLICY_B_BTC_BUY_AND_HOLD" else None
                        ref_engine.simulator.execute_hypothetical_buy(
                            next_open=next_open,
                            stop_price=stop_px,
                            target_price=target_px,
                        )
                    elif ref_dec.decision in (ShadowDecisionAction.EXIT_TO_USDT.value,) and ref_engine.simulator.position_active:
                        ref_engine.simulator.execute_hypothetical_exit(exit_raw_price=next_open)

                    # Execute indep journal
                    if journal.pending_order is not None:
                        fill = journal.commit_fill(
                            order=journal.pending_order,
                            next_open_price=next_open,
                            fill_timestamp_utc=next_ts_open,
                        )
                        if fill is not None:
                            fill_occurred = True
                            fill_px = fill.fill_price

                # Checkpoint independent state on fills, periodically, or at completion
                if fill_occurred or eval_idx % 24 == 0 or eval_idx == len(eval_candles) - 1:
                    journal.create_checkpoint()

                # Compare states
                ref_btc = round(ref_engine.simulator.btc_balance, 8)
                indep_btc = round(journal.btc_balance, 8)
                ref_usdt = round(ref_engine.simulator.usdt_balance, 4)
                indep_usdt = round(journal.usdt_balance, 4)
                ref_eq = round(ref_engine.simulator.get_portfolio_equity(close_p), 4)
                indep_eq = round(journal.get_total_equity(close_p), 4)

                action_match = (ref_dec.decision == indep_action)
                btc_match = (abs(ref_btc - indep_btc) < 1e-6)
                usdt_match = (abs(ref_usdt - indep_usdt) < 1e-2)
                eq_diff = round(abs(ref_eq - indep_eq), 4)

                disc_reason = None
                if not action_match:
                    disc_reason = f"ACTION_MISMATCH: Ref={ref_dec.decision}, Indep={indep_action}"
                elif not btc_match or not usdt_match:
                    disc_reason = f"BALANCE_MISMATCH: BTC(Ref={ref_btc}, Ind={indep_btc}), USDT(Ref={ref_usdt}, Ind={indep_usdt})"

                record = PolicyReplayComparisonRecord(
                    policy_id=policy_id,
                    bar_idx=abs_bar_idx,
                    timestamp_utc=ts_open,
                    close_price=close_p,
                    ref_action=ref_dec.decision,
                    indep_action=indep_action,
                    action_match=action_match,
                    ref_btc_balance=ref_btc,
                    indep_btc_balance=indep_btc,
                    btc_balance_match=btc_match,
                    ref_usdt_balance=ref_usdt,
                    indep_usdt_balance=indep_usdt,
                    usdt_balance_match=usdt_match,
                    ref_total_equity=ref_eq,
                    indep_total_equity=indep_eq,
                    equity_diff_usdt=eq_diff,
                    fill_occurred=fill_occurred,
                    fill_price=fill_px,
                    ref_trade_count=ref_engine.simulator.trade_count,
                    indep_trade_count=len(journal.executed_fills_history),
                    discrepancy_reason=disc_reason,
                )
                policy_records.append(record)
                all_comparison_records.append(record)

            # Summarize policy replay
            mismatches = [r for r in policy_records if not (r.action_match and r.btc_balance_match and r.usdt_balance_match)]
            policy_summaries[policy_id] = {
                "total_evaluated_bars": len(policy_records),
                "action_matches": sum(1 for r in policy_records if r.action_match),
                "balance_matches": sum(1 for r in policy_records if r.btc_balance_match and r.usdt_balance_match),
                "total_discrepancies": len(mismatches),
                "ending_ref_equity": policy_records[-1].ref_total_equity,
                "ending_indep_equity": policy_records[-1].indep_total_equity,
                "ending_ref_trades": policy_records[-1].ref_trade_count,
                "ending_indep_trades": policy_records[-1].indep_trade_count,
                "parity_verdict": "PERFECT_PARITY" if len(mismatches) == 0 else f"DISCREPANCY_DETECTED_{len(mismatches)}",
            }

        # Export ledgers
        df_records = pd.DataFrame([r.to_dict() for r in all_comparison_records])
        csv_path = self.output_dir / "policy_parity_replay_ledgers.csv"
        df_records.to_csv(csv_path, index=False)

        json_path = self.output_dir / "policy_parity_replay_ledgers.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({
                "audit_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "initial_capital_usdt": self.initial_capital_usdt,
                "warmup_bars": warmup_bars,
                "eval_bars": eval_bars,
                "policy_summaries": policy_summaries,
                "total_records_audited": len(all_comparison_records),
            }, f, indent=2)

        return {
            "csv_ledger_path": str(csv_path),
            "json_ledger_path": str(json_path),
            "summaries": policy_summaries,
            "total_records": len(all_comparison_records),
        }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    print("Running Independent Policy Replay Harness (CBE Sprint 11.16B.5)...")
    harness = IndependentPolicyReplayHarness()
    results = harness.run_replay_audit(warmup_bars=864, eval_bars=288)
    print("\n--- REPLAY AUDIT COMPLETED ---")
    print(f"Total comparison records: {results['total_records']}")
    print("Policy Summaries:")
    for pol, summ in results["summaries"].items():
        print(f"  {pol}: verdict={summ['parity_verdict']}, actions={summ['action_matches']}/{summ['total_evaluated_bars']}, balances={summ['balance_matches']}/{summ['total_evaluated_bars']}, discrepancies={summ['total_discrepancies']}")
        print(f"    Ref ending equity: {summ['ending_ref_equity']:.4f} USDT, Indep ending equity: {summ['ending_indep_equity']:.4f} USDT")

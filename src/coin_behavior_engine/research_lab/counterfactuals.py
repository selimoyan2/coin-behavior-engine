"""Retrospective counterfactual trade analysis engine.

Sprint 11.04: Research Integrity, Verified Market Context & First Reliable Strategy Benchmark.
Evaluates alternative scenarios for significant executed trades:
- Skipped trade
- Reduced size (50%)
- Higher-timeframe confirmation requirement
- Adverse event block
- Delayed exit (+1 hour / +12 bars)

MANDATORY INTEGRITY REQUIREMENT:
All counterfactuals are explicitly marked RETROSPECTIVE_COUNTERFACTUAL.
Never present hindsight-optimized results as achievable real-time decisions.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd

from coin_behavior_engine.research_lab.contracts import (
    CandleData,
    MarketBehaviorFeatures,
    PaperTrade,
)


@dataclass
class CounterfactualTradeRecord:
    """Formal audit record of an actual trade and its retrospective counterfactual variants."""
    trade_id: str
    strategy_name: str
    symbol: str
    entry_time_utc: str
    exit_time_utc: str
    actual_entry_price: float
    actual_exit_price: float
    actual_quantity: float
    actual_net_pnl: float
    actual_return_pct: float
    actual_exit_reason: str
    actual_fees_paid: float
    methodology: str = "RETROSPECTIVE_COUNTERFACTUAL"
    
    # Counterfactual 1: Skipped Trade
    pnl_if_skipped: float = 0.0
    
    # Counterfactual 2: Reduced Position Sizing (50%)
    pnl_if_size_halved: float = 0.0
    fees_if_size_halved: float = 0.0
    
    # Counterfactual 3: Waited for Higher-Timeframe (1h) Confirmation
    htf_1h_aligned_at_entry: bool = False
    action_if_htf_required: str = "EXECUTE"  # "EXECUTE" or "BLOCK_TRADE"
    pnl_if_htf_required: float = 0.0
    
    # Counterfactual 4: Blocked by Adverse Event
    had_active_macro_event: bool = False
    action_if_event_blocked: str = "EXECUTE"  # "EXECUTE" or "BLOCK_TRADE"
    pnl_if_event_blocked: float = 0.0
    
    # Counterfactual 5: Delayed Exit (+12 bars / +1 hour)
    delayed_exit_price: Optional[float] = None
    delayed_exit_pnl: Optional[float] = None
    delayed_exit_delta_pnl: Optional[float] = None
    
    retrospective_finding: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CounterfactualAnalyzer:
    """Computes retrospective alternative execution paths for significant trades."""

    @classmethod
    def analyze_significant_trades(
        cls,
        trades: List[PaperTrade],
        candles: List[CandleData],
        features: List[MarketBehaviorFeatures],
        top_n: int = 10,
    ) -> List[CounterfactualTradeRecord]:
        """Select top winners and top losers and compute counterfactual paths."""
        if not trades or not candles:
            return []

        # Build fast timestamp to candle/feature index map
        ts_to_idx = {c.timestamp_open: i for i, c in enumerate(candles)}
        utc_to_idx = {c.datetime_open_utc: i for i, c in enumerate(candles)}

        # Sort trades by net PnL
        sorted_trades = sorted(trades, key=lambda t: t.net_pnl)
        significant_trades: List[PaperTrade] = []
        
        # Take top losers and top winners without duplicates
        half = max(1, top_n // 2)
        losers = sorted_trades[:half]
        winners = sorted_trades[-half:]
        unique_trades_dict = {t.trade_id: t for t in (losers + winners)}
        significant_trades = list(unique_trades_dict.values())

        records: List[CounterfactualTradeRecord] = []

        for t in significant_trades:
            entry_idx = utc_to_idx.get(t.entry_time_utc)
            if entry_idx is None:
                # Fallback: search nearest
                for i, c in enumerate(candles):
                    if c.datetime_open_utc >= t.entry_time_utc:
                        entry_idx = i
                        break

            entry_idx = entry_idx if entry_idx is not None else 0
            feat_at_entry = features[entry_idx] if entry_idx < len(features) else None

            # Counterfactual 2: Halved size
            half_pnl = round(t.net_pnl * 0.5, 2)
            half_fees = round(t.fees_paid * 0.5, 2)

            # Counterfactual 3: HTF confirmation
            htf_aligned = feat_at_entry.is_htf_trend_aligned if feat_at_entry else False
            if not htf_aligned:
                action_htf = "BLOCK_TRADE"
                pnl_htf = 0.0
            else:
                action_htf = "EXECUTE"
                pnl_htf = t.net_pnl

            # Counterfactual 4: Event block (check if regime is high vol or liquidation)
            is_high_risk = feat_at_entry.regime.value in ("CASCADE_LIQUIDATION", "HIGH_VOLATILITY_EXPANSION") if feat_at_entry else False
            if is_high_risk:
                action_evt = "BLOCK_TRADE"
                pnl_evt = 0.0
            else:
                action_evt = "EXECUTE"
                pnl_evt = t.net_pnl

            # Counterfactual 5: Delayed exit (+12 bars = 1 hour)
            exit_idx = utc_to_idx.get(t.exit_time_utc)
            if exit_idx is None:
                exit_idx = min(len(candles) - 1, entry_idx + (t.holding_period_minutes // 5))

            delayed_idx = min(len(candles) - 1, exit_idx + 12)
            delayed_price = candles[delayed_idx].close
            # Slippage on exit: 0.05%
            delayed_eff_exit = delayed_price * 0.9995
            delayed_gross = t.quantity * delayed_eff_exit
            delayed_fee = delayed_gross * 0.0010
            delayed_pnl = round(delayed_gross - delayed_fee - (t.quantity * t.entry_price), 2)
            delta_pnl = round(delayed_pnl - t.net_pnl, 2)

            # Retrospective finding summary
            if t.net_pnl < 0:
                if not htf_aligned:
                    finding = "Counter-trend entry: requiring HTF confirmation would have completely avoided this loss."
                elif is_high_risk:
                    finding = "High-volatility entry: adverse regime filter would have protected capital."
                elif delta_pnl > abs(t.net_pnl) * 0.5:
                    finding = "Premature stop-out: price subsequently recovered after shakeout."
                else:
                    finding = "Structural breakdown: strict stop prevented further catastrophic downside."
            else:
                if delta_pnl > 0:
                    finding = "Trend continuation: delaying exit allowed capturing extended runner move."
                else:
                    finding = "Optimal exit: disciplined take-profit captured peak before subsequent mean-reversion."

            rec = CounterfactualTradeRecord(
                trade_id=t.trade_id,
                strategy_name=t.strategy_name,
                symbol=t.symbol,
                entry_time_utc=t.entry_time_utc,
                exit_time_utc=t.exit_time_utc,
                actual_entry_price=t.entry_price,
                actual_exit_price=t.exit_price,
                actual_quantity=t.quantity,
                actual_net_pnl=t.net_pnl,
                actual_return_pct=t.return_pct,
                actual_exit_reason=t.exit_reason.value if hasattr(t.exit_reason, "value") else str(t.exit_reason),
                actual_fees_paid=t.fees_paid,
                methodology="RETROSPECTIVE_COUNTERFACTUAL",
                pnl_if_skipped=0.0,
                pnl_if_size_halved=half_pnl,
                fees_if_size_halved=half_fees,
                htf_1h_aligned_at_entry=htf_aligned,
                action_if_htf_required=action_htf,
                pnl_if_htf_required=pnl_htf,
                had_active_macro_event=is_high_risk,
                action_if_event_blocked=action_evt,
                pnl_if_event_blocked=pnl_evt,
                delayed_exit_price=round(delayed_price, 2),
                delayed_exit_pnl=delayed_pnl,
                delayed_exit_delta_pnl=delta_pnl,
                retrospective_finding=finding,
            )
            records.append(rec)

        return records

    @classmethod
    def export_counterfactuals_csv(
        cls,
        records: List[CounterfactualTradeRecord],
        output_csv: Path,
    ) -> None:
        """Export counterfactual table to CSV."""
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        rows = [r.to_dict() for r in records]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

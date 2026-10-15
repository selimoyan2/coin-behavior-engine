"""Executable strategy specifications and realistic trade simulators for B3 and B5 behaviors.

Transforms observational patterns B3 (Extended Deviation from Mean) and B5 (Failed Trend
Continuation / Rebound) into strictly point-in-time executable trading rules with:
- Next-bar open entry (zero lookahead).
- Point-in-time ATR-based stop-loss and take-profit barriers.
- Max holding horizon (12 bars).
- Non-overlapping independent trade clustering.
- Directional asymmetry auditing (Long vs Short).
- Maker vs Taker execution cost accounting.
- Auditable trade record ledger generation.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
import math
from typing import Any, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from coin_behavior_engine.research.historical.market_regime_intelligence import (
    MarketRegimeEngine,
    MarketRegimeState,
    TrendRegime,
    VolumeRegime,
)
from coin_behavior_engine.research.historical.provenance import (
    AuditableTradeLedger,
    AuditableTradeRecord,
)


@dataclass(frozen=True)
class B3StrategyConfig:
    """Pre-registered configuration for B3 Extended Deviation Strategy."""

    strategy_id: str = "B3_RANGE_EXPANSION"
    direction_mode: str = "CONTINUATION"  # "CONTINUATION" or "REVERSION"
    stretch_atr_multiple: float = 2.50
    ema_span: int = 50
    entry_timing: str = "NEXT_BAR_OPEN"
    stop_loss_atr_multiple: float = 1.50
    take_profit_atr_multiple: float = 2.25
    max_holding_bars: int = 12
    cost_maker_bps: float = 6.0  # 3 bps per side
    cost_taker_bps: float = 16.0  # 8 bps per side

    @property
    def config_hash(self) -> str:
        d = asdict(self)
        raw = json.dumps(d, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class B5StrategyConfig:
    """Pre-registered configuration for B5 Failed Continuation Strategy."""

    strategy_id: str = "B5_FAILED_CONTINUATION"
    direction_mode: str = "REBOUND_BULLISH"  # "REBOUND_BULLISH" or "REBOUND_SYMMETRIC"
    trend_filter: str = "BULLISH_TREND"
    volume_filter: str = "HIGH_VOLUME"
    entry_timing: str = "NEXT_BAR_OPEN"
    stop_loss_atr_multiple: float = 1.50
    take_profit_atr_multiple: float = 2.25
    max_holding_bars: int = 12
    cost_maker_bps: float = 6.0
    cost_taker_bps: float = 16.0

    @property
    def config_hash(self) -> str:
        d = asdict(self)
        raw = json.dumps(d, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class ExecutableStrategyMetrics:
    """Rigorous performance metrics for an executable historical strategy."""

    strategy_id: str
    direction_mode: str
    dataset_tag: str
    total_signals_detected: int
    independent_trades: int
    gross_expectancy_bps: float
    net_maker_expectancy_bps: float
    net_taker_expectancy_bps: float
    win_rate_gross: float
    win_rate_maker: float
    win_rate_taker: float
    profit_factor_maker: float
    profit_factor_taker: float
    max_drawdown_bps: float
    t_statistic_maker: float
    t_statistic_taker: float
    bootstrap_ci_95_maker_bps: tuple[float, float]
    long_trades_count: int
    long_net_maker_bps: float
    short_trades_count: int
    short_net_maker_bps: float
    asymmetry_notes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExecutableBehaviorSimulator:
    """Simulates realistic execution of pre-registered behavioral strategies."""

    def __init__(self, candles: Sequence[Mapping[str, Any]], symbol: str = "BTCUSDT") -> None:
        self.candles = candles
        self.symbol = symbol
        self.n_bars = len(candles)
        self.engine = MarketRegimeEngine(candles)
        self._closes = np.array([float(c["close"]) for c in candles])
        self._highs = np.array([float(c["high"]) for c in candles])
        self._lows = np.array([float(c["low"]) for c in candles])
        self._opens = np.array([float(c["open"]) for c in candles])
        self._timestamps = [int(c.get("open_time", c.get("timestamp_open", c.get("timestamp_ms", 0)))) for c in candles]

    def simulate_b3(
        self,
        config: B3StrategyConfig,
        dataset_tag: str = "q1_2024",
    ) -> tuple[ExecutableStrategyMetrics, list[AuditableTradeRecord]]:
        """Simulate B3 Extended Deviation from Mean Strategy."""
        states = [self.engine.classify_bar(i) for i in range(self.n_bars)]
        signals: list[int] = []
        in_stretch = False

        for i in range(self.n_bars):
            if states[i].adx_proxy >= config.stretch_atr_multiple:
                if not in_stretch:
                    signals.append(i)
                    in_stretch = True
            else:
                in_stretch = False

        # Run trade execution
        records = self._execute_signals(
            signals=signals,
            get_direction_fn=lambda idx: (
                ("LONG" if self._closes[idx] > self.engine._ema50[idx] else "SHORT")
                if config.direction_mode == "CONTINUATION"
                else ("SHORT" if self._closes[idx] > self.engine._ema50[idx] else "LONG")
            ),
            sl_atr_mult=config.stop_loss_atr_multiple,
            tp_atr_mult=config.take_profit_atr_multiple,
            max_bars=config.max_holding_bars,
            maker_cost_bps=config.cost_maker_bps,
            taker_cost_bps=config.cost_taker_bps,
            opportunity_prefix=f"B3_{config.direction_mode}_{dataset_tag}",
        )

        metrics = self._calculate_metrics(
            strategy_id=config.strategy_id,
            direction_mode=config.direction_mode,
            dataset_tag=dataset_tag,
            total_signals=len(signals),
            records=records,
            maker_cost_bps=config.cost_maker_bps,
            taker_cost_bps=config.cost_taker_bps,
        )

        return metrics, records

    def simulate_b5(
        self,
        config: B5StrategyConfig,
        dataset_tag: str = "q1_2024",
    ) -> tuple[ExecutableStrategyMetrics, list[AuditableTradeRecord]]:
        """Simulate B5 Failed Trend Continuation / Rebound Strategy."""
        states = [self.engine.classify_bar(i) for i in range(self.n_bars)]
        signals: list[int] = []

        for i in range(self.n_bars):
            s = states[i]
            c_close = self._closes[i]
            c_open = self._opens[i]

            if config.direction_mode == "REBOUND_BULLISH":
                if s.trend == TrendRegime.BULLISH_TREND and s.volume == VolumeRegime.HIGH_VOLUME and c_close < c_open:
                    signals.append(i)
            elif config.direction_mode == "REBOUND_SYMMETRIC":
                if s.volume == VolumeRegime.HIGH_VOLUME:
                    if s.trend == TrendRegime.BULLISH_TREND and c_close < c_open:
                        signals.append(i)
                    elif s.trend == TrendRegime.BEARISH_TREND and c_close > c_open:
                        signals.append(i)

        # Run trade execution
        def get_b5_direction(idx: int) -> str:
            if states[idx].trend == TrendRegime.BULLISH_TREND:
                return "LONG"
            return "SHORT"

        records = self._execute_signals(
            signals=signals,
            get_direction_fn=get_b5_direction,
            sl_atr_mult=config.stop_loss_atr_multiple,
            tp_atr_mult=config.take_profit_atr_multiple,
            max_bars=config.max_holding_bars,
            maker_cost_bps=config.cost_maker_bps,
            taker_cost_bps=config.cost_taker_bps,
            opportunity_prefix=f"B5_{config.direction_mode}_{dataset_tag}",
        )

        metrics = self._calculate_metrics(
            strategy_id=config.strategy_id,
            direction_mode=config.direction_mode,
            dataset_tag=dataset_tag,
            total_signals=len(signals),
            records=records,
            maker_cost_bps=config.cost_maker_bps,
            taker_cost_bps=config.cost_taker_bps,
        )

        return metrics, records

    def _execute_signals(
        self,
        signals: list[int],
        get_direction_fn: Any,
        sl_atr_mult: float,
        tp_atr_mult: float,
        max_bars: int,
        maker_cost_bps: float,
        taker_cost_bps: float,
        opportunity_prefix: str,
    ) -> list[AuditableTradeRecord]:
        """Execute signals with strict non-overlapping independent trade clustering."""
        records: list[AuditableTradeRecord] = []
        last_exit_idx = -1

        for sig_idx in signals:
            if sig_idx + max_bars + 1 >= self.n_bars:
                continue

            # Independent trade condition: cannot enter while previous trade is open
            if sig_idx <= last_exit_idx:
                continue

            entry_bar_idx = sig_idx + 1
            direction_str = get_direction_fn(sig_idx)
            direction_val = 1.0 if direction_str == "LONG" else -1.0

            entry_price = self._opens[entry_bar_idx]
            entry_ts = self._timestamps[entry_bar_idx]
            atr = self.engine._atr14[sig_idx]
            if atr <= 0:
                atr = entry_price * 0.005

            sl_dist = sl_atr_mult * atr
            tp_dist = tp_atr_mult * atr

            exit_bar_idx = entry_bar_idx + max_bars
            exit_price = self._closes[exit_bar_idx]
            exit_reason = "HORIZON_EXPIRED"

            # Check intrabar barriers
            for bar_k in range(entry_bar_idx, entry_bar_idx + max_bars + 1):
                hi_k = self._highs[bar_k]
                lo_k = self._lows[bar_k]

                if direction_str == "LONG":
                    if lo_k <= entry_price - sl_dist:
                        exit_bar_idx = bar_k
                        exit_price = entry_price - sl_dist
                        exit_reason = "STOP_LOSS"
                        break
                    elif hi_k >= entry_price + tp_dist:
                        exit_bar_idx = bar_k
                        exit_price = entry_price + tp_dist
                        exit_reason = "TAKE_PROFIT"
                        break
                else:
                    if hi_k >= entry_price + sl_dist:
                        exit_bar_idx = bar_k
                        exit_price = entry_price + sl_dist
                        exit_reason = "STOP_LOSS"
                        break
                    elif lo_k <= entry_price - tp_dist:
                        exit_bar_idx = bar_k
                        exit_price = entry_price - tp_dist
                        exit_reason = "TAKE_PROFIT"
                        break

            last_exit_idx = exit_bar_idx
            exit_ts = self._timestamps[exit_bar_idx]
            holding_bars = exit_bar_idx - entry_bar_idx

            gross_return_pct = ((exit_price - entry_price) / entry_price) * direction_val
            net_maker_pct = gross_return_pct - (maker_cost_bps / 10000.0)

            rec = AuditableTradeRecord(
                opportunity_id=f"{opportunity_prefix}_{len(records) + 1:04d}",
                symbol=self.symbol,
                direction=direction_str,
                entry_bar_index=int(entry_bar_idx),
                entry_timestamp_ms=int(entry_ts),
                exit_bar_index=int(exit_bar_idx),
                exit_timestamp_ms=int(exit_ts),
                intended_entry_price=float(round(entry_price, 2)),
                effective_entry_price=float(round(entry_price, 2)),
                exit_price=float(round(exit_price, 2)),
                exit_reason=str(exit_reason),
                holding_bars=int(holding_bars),
                is_filled=True,
                fill_ratio=1.0,
                adverse_selection_bps=2.0,
                cost_bps=float(maker_cost_bps),
                gross_return_pct=float(round(gross_return_pct, 6)),
                net_return_pct=float(round(net_maker_pct, 6)),
                net_return_bps=float(round(net_maker_pct * 10000.0, 2)),
                is_win=bool(net_maker_pct > 0.0),
                is_independent=True,
            )
            records.append(rec)

        return records

    def _calculate_metrics(
        self,
        strategy_id: str,
        direction_mode: str,
        dataset_tag: str,
        total_signals: int,
        records: list[AuditableTradeRecord],
        maker_cost_bps: float,
        taker_cost_bps: float,
    ) -> ExecutableStrategyMetrics:
        """Calculate statistical and financial metrics from simulated records."""
        n_trades = len(records)
        if n_trades == 0:
            return ExecutableStrategyMetrics(
                strategy_id=strategy_id,
                direction_mode=direction_mode,
                dataset_tag=dataset_tag,
                total_signals_detected=total_signals,
                independent_trades=0,
                gross_expectancy_bps=0.0,
                net_maker_expectancy_bps=0.0,
                net_taker_expectancy_bps=0.0,
                win_rate_gross=0.0,
                win_rate_maker=0.0,
                win_rate_taker=0.0,
                profit_factor_maker=0.0,
                profit_factor_taker=0.0,
                max_drawdown_bps=0.0,
                t_statistic_maker=0.0,
                t_statistic_taker=0.0,
                bootstrap_ci_95_maker_bps=(0.0, 0.0),
                long_trades_count=0,
                long_net_maker_bps=0.0,
                short_trades_count=0,
                short_net_maker_bps=0.0,
                asymmetry_notes="Zero trades executed.",
            )

        gross_bps_arr = np.array([r.gross_return_pct * 10000.0 for r in records])
        net_maker_arr = np.array([r.net_return_bps for r in records])
        net_taker_arr = np.array([r.gross_return_pct * 10000.0 - taker_cost_bps for r in records])

        gross_mean = float(np.mean(gross_bps_arr))
        net_maker_mean = float(np.mean(net_maker_arr))
        net_taker_mean = float(np.mean(net_taker_arr))

        wr_gross = float(np.mean(gross_bps_arr > 0.0))
        wr_maker = float(np.mean(net_maker_arr > 0.0))
        wr_taker = float(np.mean(net_taker_arr > 0.0))

        # Profit factor
        maker_wins = net_maker_arr[net_maker_arr > 0.0]
        maker_losses = -net_maker_arr[net_maker_arr < 0.0]
        pf_maker = (float(np.sum(maker_wins)) / float(np.sum(maker_losses))) if np.sum(maker_losses) > 0 else 1.0

        taker_wins = net_taker_arr[net_taker_arr > 0.0]
        taker_losses = -net_taker_arr[net_taker_arr < 0.0]
        pf_taker = (float(np.sum(taker_wins)) / float(np.sum(taker_losses))) if np.sum(taker_losses) > 0 else 1.0

        # Max drawdown
        cum_ret = np.cumsum(net_maker_arr)
        peak = np.maximum.accumulate(cum_ret)
        dd = peak - cum_ret
        max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0

        # t-statistic
        se_maker = float(np.std(net_maker_arr, ddof=1) / math.sqrt(n_trades)) if n_trades > 1 else 1.0
        t_maker = net_maker_mean / se_maker if se_maker > 1e-9 else 0.0

        se_taker = float(np.std(net_taker_arr, ddof=1) / math.sqrt(n_trades)) if n_trades > 1 else 1.0
        t_taker = net_taker_mean / se_taker if se_taker > 1e-9 else 0.0

        # Bootstrap 95% CI on net maker expectancy
        rng = np.random.default_rng(seed=42)
        boot_means = [np.mean(rng.choice(net_maker_arr, size=n_trades, replace=True)) for _ in range(1000)]
        ci_low = float(np.percentile(boot_means, 2.5))
        ci_high = float(np.percentile(boot_means, 97.5))

        # Long vs Short asymmetry
        long_recs = [r for r in records if r.direction == "LONG"]
        short_recs = [r for r in records if r.direction == "SHORT"]

        long_cnt = len(long_recs)
        short_cnt = len(short_recs)
        long_mean = float(np.mean([r.net_return_bps for r in long_recs])) if long_cnt > 0 else 0.0
        short_mean = float(np.mean([r.net_return_bps for r in short_recs])) if short_cnt > 0 else 0.0

        asym_notes = (
            f"Long: {long_cnt} trades, mean {long_mean:.2f} bps; "
            f"Short: {short_cnt} trades, mean {short_mean:.2f} bps. "
            f"Asymmetry delta: {long_mean - short_mean:.2f} bps."
        )

        return ExecutableStrategyMetrics(
            strategy_id=strategy_id,
            direction_mode=direction_mode,
            dataset_tag=dataset_tag,
            total_signals_detected=total_signals,
            independent_trades=n_trades,
            gross_expectancy_bps=round(gross_mean, 2),
            net_maker_expectancy_bps=round(net_maker_mean, 2),
            net_taker_expectancy_bps=round(net_taker_mean, 2),
            win_rate_gross=round(wr_gross, 4),
            win_rate_maker=round(wr_maker, 4),
            win_rate_taker=round(wr_taker, 4),
            profit_factor_maker=round(pf_maker, 2),
            profit_factor_taker=round(pf_taker, 2),
            max_drawdown_bps=round(max_dd, 2),
            t_statistic_maker=round(t_maker, 2),
            t_statistic_taker=round(t_taker, 2),
            bootstrap_ci_95_maker_bps=(round(ci_low, 2), round(ci_high, 2)),
            long_trades_count=long_cnt,
            long_net_maker_bps=round(long_mean, 2),
            short_trades_count=short_cnt,
            short_net_maker_bps=round(short_mean, 2),
            asymmetry_notes=asym_notes,
        )

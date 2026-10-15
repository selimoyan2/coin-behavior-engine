"""Pre-registered Cross-Sectional Hypotheses (CS1 to CS4) and Spot-Only Execution Simulator.

Implements and evaluates:
- CS1: Relative Momentum Persistence (Does top risk-adjusted asset outperform benchmark/cash?)
- CS2: Leadership Rotation (Does high leadership concentration predict rotation to laggards?)
- CS3: Market Breadth Confirmation (Does breadth > 66% confirm BTC trend breakouts?)
- CS4: BTC Regime Dependency (Does cross-sectional momentum alpha depend on BTC trend regime?)

Strict Spot-only execution rules:
- No naked shorting.
- No leverage.
- No borrowed assets.
- No perpetual funding in Spot P&L.
- Cash versus asset allocation only.
- Realistic rebalancing turnover and transaction costs (Maker 6 bps, Taker 16 bps).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import math
from typing import Any, Mapping, Optional, Sequence

import numpy as np
import pandas as pd

from coin_behavior_engine.research.historical.cross_sectional_relative_strength import (
    CrossSectionalFeatureSnapshot,
    CrossSectionalRelativeStrengthEngine,
)
from coin_behavior_engine.research.historical.market_breadth import (
    MarketBreadthEngine,
    MarketBreadthSnapshot,
)
from coin_behavior_engine.research.historical.market_regime_intelligence import (
    MarketRegimeEngine,
    TrendRegime,
)
from coin_behavior_engine.research.historical.provenance import (
    AuditableTradeRecord,
)


class CrossSectionalDecisionVerdict(str, Enum):
    REJECTED = "REJECTED"
    OBSERVATIONAL_ONLY = "OBSERVATIONAL_ONLY"
    EXPLORATORY = "EXPLORATORY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    INDEPENDENT_VALIDATION_CANDIDATE = "INDEPENDENT_VALIDATION_CANDIDATE"


@dataclass(frozen=True)
class CS1Config:
    """CS1: Relative Momentum Persistence configuration."""

    hypothesis_id: str = "CS1_RELATIVE_MOMENTUM_PERSISTENCE"
    lookback_bars: int = 96  # 24h
    rebalance_horizon_bars: int = 16  # 4h
    rebalance_cost_maker_bps: float = 6.0
    rebalance_cost_taker_bps: float = 16.0

    @property
    def config_hash(self) -> str:
        d = asdict(self)
        raw = json.dumps(d, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class CS2Config:
    """CS2: Leadership Rotation configuration."""

    hypothesis_id: str = "CS2_LEADERSHIP_ROTATION"
    lookback_bars: int = 96
    concentration_hhi_threshold: float = 0.60
    rebalance_horizon_bars: int = 16
    cost_maker_bps: float = 6.0
    cost_taker_bps: float = 16.0

    @property
    def config_hash(self) -> str:
        d = asdict(self)
        raw = json.dumps(d, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class CS3Config:
    """CS3: Market Breadth Confirmation configuration."""

    hypothesis_id: str = "CS3_MARKET_BREADTH_CONFIRMATION"
    lookback_bars: int = 96
    holding_bars: int = 16
    breadth_threshold_broad: float = 0.66
    breadth_threshold_narrow: float = 0.34
    cost_maker_bps: float = 6.0
    cost_taker_bps: float = 16.0

    @property
    def config_hash(self) -> str:
        d = asdict(self)
        raw = json.dumps(d, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class CS4Config:
    """CS4: BTC Regime Dependency configuration."""

    hypothesis_id: str = "CS4_BTC_REGIME_DEPENDENCY"
    lookback_bars: int = 96
    holding_bars: int = 16
    cost_maker_bps: float = 6.0
    cost_taker_bps: float = 16.0

    @property
    def config_hash(self) -> str:
        d = asdict(self)
        raw = json.dumps(d, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class CrossSectionalPreRegistrationGate:
    """Pre-registration contract for cross-sectional market research."""

    registration_id: str
    timestamp_utc: str
    baseline_commit: str
    strategy_hashes: dict[str, str]
    spot_execution_invariants: dict[str, Any]
    acceptance_criteria: dict[str, Any]
    is_frozen: bool = True

    def verify_integrity(self, active_hashes: dict[str, str]) -> bool:
        for name, expected in self.strategy_hashes.items():
            if active_hashes.get(name) != expected:
                return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CrossSectionalHypothesisResult:
    """Complete empirical result record for a cross-sectional hypothesis."""

    hypothesis_id: str
    description: str
    total_events_evaluated: int
    independent_decision_events: int
    gross_expectancy_bps: float
    net_maker_expectancy_bps: float
    net_taker_expectancy_bps: float
    win_rate_maker: float
    win_rate_taker: float
    profit_factor_maker: float
    max_drawdown_bps: float
    t_statistic_maker: float
    bootstrap_ci_95_maker_bps: tuple[float, float]
    verdict: CrossSectionalDecisionVerdict
    scientific_notes: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["verdict"] = self.verdict.value
        return d


class CrossSectionalResearchRunner:
    """Executes pre-registered cross-sectional hypotheses under Spot constraints."""

    def __init__(
        self,
        asset_candles: Mapping[str, Sequence[Mapping[str, Any]]],
        benchmark_symbol: str = "BTCUSDT",
    ) -> None:
        self.benchmark_symbol = benchmark_symbol
        self.rs_engine = CrossSectionalRelativeStrengthEngine(asset_candles, benchmark_symbol)
        self.breadth_engine = MarketBreadthEngine(asset_candles, benchmark_symbol)
        self.btc_regime_engine = MarketRegimeEngine(asset_candles[benchmark_symbol])

        self.snaps = self.rs_engine.compute_snapshots(lookback_bars=96)
        self.breadth_snaps = self.breadth_engine.compute_breadth_snapshots(lookback_bars=96)
        self.n_bars = len(self.snaps)

    def create_preregistration_gate(self) -> CrossSectionalPreRegistrationGate:
        """Create and freeze pre-registration gate hashes."""
        hashes = {
            "CS1": CS1Config().config_hash,
            "CS2": CS2Config().config_hash,
            "CS3": CS3Config().config_hash,
            "CS4": CS4Config().config_hash,
        }
        invariants = {
            "spot_only": True,
            "no_naked_shorting": True,
            "no_leverage": True,
            "no_borrowed_assets": True,
            "no_perpetual_funding_in_spot": True,
            "cash_drag_modeled": True,
            "maker_cost_roundtrip_bps": 6.0,
            "taker_cost_roundtrip_bps": 16.0,
        }
        criteria = {
            "family_alpha_bonferroni": 0.0125,
            "min_independent_events": 30,
            "bootstrap_ci_lower_gt_zero": True,
            "holdout_positive_net": True,
        }
        return CrossSectionalPreRegistrationGate(
            registration_id="PREREG-SPRINT09.28-CROSS-SECTIONAL",
            timestamp_utc="2026-10-15T09:00:00Z",
            baseline_commit="95fb3016162706b372768b718611972cc63393bf",
            strategy_hashes=hashes,
            spot_execution_invariants=invariants,
            acceptance_criteria=criteria,
            is_frozen=True,
        )

    def evaluate_cs1_momentum_persistence(
        self,
        config: CS1Config,
    ) -> tuple[CrossSectionalHypothesisResult, list[AuditableTradeRecord]]:
        """Evaluate CS1: Relative Momentum Persistence (Top Asset vs Benchmark & Cash)."""
        h = config.rebalance_horizon_bars
        records: list[AuditableTradeRecord] = []
        net_maker_returns = []
        gross_returns = []

        last_sym = None
        for i in range(0, self.n_bars - h, h):
            s = self.snaps[i]
            top_sym = s.top_asset
            p0 = s.prices[top_sym]
            p1 = self.snaps[i + h].prices[top_sym]
            gross_pct = (p1 - p0) / p0

            # Cost applies on entry and symbol switch
            is_rebalanced = (top_sym != last_sym)
            cost_bps = config.rebalance_cost_maker_bps if is_rebalanced else 0.0
            last_sym = top_sym

            net_pct = gross_pct - (cost_bps / 10000.0)
            net_bps = net_pct * 10000.0

            gross_returns.append(gross_pct * 10000.0)
            net_maker_returns.append(net_bps)

            rec = AuditableTradeRecord(
                opportunity_id=f"CS1_REBALANCE_{len(records) + 1:04d}",
                symbol=top_sym,
                direction="LONG",
                entry_bar_index=s.bar_index,
                entry_timestamp_ms=s.timestamp_ms,
                exit_bar_index=self.snaps[i + h].bar_index,
                exit_timestamp_ms=self.snaps[i + h].timestamp_ms,
                intended_entry_price=round(p0, 2),
                effective_entry_price=round(p0, 2),
                exit_price=round(p1, 2),
                exit_reason="REBALANCE_HORIZON",
                holding_bars=h,
                is_filled=True,
                fill_ratio=1.0,
                adverse_selection_bps=2.0,
                cost_bps=cost_bps,
                gross_return_pct=round(gross_pct, 6),
                net_return_pct=round(net_pct, 6),
                net_return_bps=round(net_bps, 2),
                is_win=net_bps > 0.0,
                is_independent=True,
            )
            records.append(rec)

        res = self._compute_hypothesis_result(
            hyp_id=config.hypothesis_id,
            description="Cross-sectional risk-adjusted momentum top asset Spot allocation",
            gross_returns=gross_returns,
            net_maker_returns=net_maker_returns,
            records=records,
            taker_cost_bps=config.rebalance_cost_taker_bps,
        )
        return res, records

    def evaluate_cs2_leadership_rotation(
        self,
        config: CS2Config,
    ) -> tuple[CrossSectionalHypothesisResult, list[AuditableTradeRecord]]:
        """Evaluate CS2: Leadership Rotation (Concentration Mean Reversion)."""
        h = config.rebalance_horizon_bars
        records: list[AuditableTradeRecord] = []
        gross_returns = []
        net_maker_returns = []

        for i in range(0, self.n_bars - h, h):
            s = self.snaps[i]
            # Trigger: Leadership concentration HHI >= threshold
            if s.leadership_concentration_hhi >= config.concentration_hhi_threshold:
                target_sym = s.bottom_asset
                p0 = s.prices[target_sym]
                p1 = self.snaps[i + h].prices[target_sym]
                gross_pct = (p1 - p0) / p0
                net_pct = gross_pct - (config.cost_maker_bps / 10000.0)
                net_bps = net_pct * 10000.0

                gross_returns.append(gross_pct * 10000.0)
                net_maker_returns.append(net_bps)

                rec = AuditableTradeRecord(
                    opportunity_id=f"CS2_ROTATION_{len(records) + 1:04d}",
                    symbol=target_sym,
                    direction="LONG",
                    entry_bar_index=s.bar_index,
                    entry_timestamp_ms=s.timestamp_ms,
                    exit_bar_index=self.snaps[i + h].bar_index,
                    exit_timestamp_ms=self.snaps[i + h].timestamp_ms,
                    intended_entry_price=round(p0, 2),
                    effective_entry_price=round(p0, 2),
                    exit_price=round(p1, 2),
                    exit_reason="REBALANCE_HORIZON",
                    holding_bars=h,
                    is_filled=True,
                    fill_ratio=1.0,
                    adverse_selection_bps=2.0,
                    cost_bps=config.cost_maker_bps,
                    gross_return_pct=round(gross_pct, 6),
                    net_return_pct=round(net_pct, 6),
                    net_return_bps=round(net_bps, 2),
                    is_win=net_bps > 0.0,
                    is_independent=True,
                )
                records.append(rec)

        res = self._compute_hypothesis_result(
            hyp_id=config.hypothesis_id,
            description="Mean reversion rotation into lagging assets upon concentrated leadership",
            gross_returns=gross_returns,
            net_maker_returns=net_maker_returns,
            records=records,
            taker_cost_bps=config.cost_taker_bps,
        )
        return res, records

    def evaluate_cs3_breadth_confirmation(
        self,
        config: CS3Config,
    ) -> tuple[CrossSectionalHypothesisResult, list[AuditableTradeRecord]]:
        """Evaluate CS3: Market Breadth Confirmation for BTC Trend Advances."""
        h = config.holding_bars
        records: list[AuditableTradeRecord] = []
        gross_returns = []
        net_maker_returns = []

        for i in range(0, self.n_bars - h, h):
            s = self.snaps[i]
            bs = self.breadth_snaps[i]
            btc_trend = self.btc_regime_engine.classify_bar(s.bar_index).trend

            # Trigger: BTC in BULLISH_TREND AND Broad Advance (breadth >= 66%)
            if btc_trend == TrendRegime.BULLISH_TREND and bs.is_broad_advance:
                p0 = s.prices[self.benchmark_symbol]
                p1 = self.snaps[i + h].prices[self.benchmark_symbol]
                gross_pct = (p1 - p0) / p0
                net_pct = gross_pct - (config.cost_maker_bps / 10000.0)
                net_bps = net_pct * 10000.0

                gross_returns.append(gross_pct * 10000.0)
                net_maker_returns.append(net_bps)

                rec = AuditableTradeRecord(
                    opportunity_id=f"CS3_BREADTH_{len(records) + 1:04d}",
                    symbol=self.benchmark_symbol,
                    direction="LONG",
                    entry_bar_index=s.bar_index,
                    entry_timestamp_ms=s.timestamp_ms,
                    exit_bar_index=self.snaps[i + h].bar_index,
                    exit_timestamp_ms=self.snaps[i + h].timestamp_ms,
                    intended_entry_price=round(p0, 2),
                    effective_entry_price=round(p0, 2),
                    exit_price=round(p1, 2),
                    exit_reason="TIME_HORIZON",
                    holding_bars=h,
                    is_filled=True,
                    fill_ratio=1.0,
                    adverse_selection_bps=2.0,
                    cost_bps=config.cost_maker_bps,
                    gross_return_pct=round(gross_pct, 6),
                    net_return_pct=round(net_pct, 6),
                    net_return_bps=round(net_bps, 2),
                    is_win=net_bps > 0.0,
                    is_independent=True,
                )
                records.append(rec)

        res = self._compute_hypothesis_result(
            hyp_id=config.hypothesis_id,
            description="BTC trend continuation filtered by broad multi-asset participation",
            gross_returns=gross_returns,
            net_maker_returns=net_maker_returns,
            records=records,
            taker_cost_bps=config.cost_taker_bps,
        )
        return res, records

    def evaluate_cs4_btc_regime_dependency(
        self,
        config: CS4Config,
    ) -> tuple[CrossSectionalHypothesisResult, list[AuditableTradeRecord]]:
        """Evaluate CS4: Cross-Sectional Alpha Dependency on BTC Regime."""
        h = config.holding_bars
        records: list[AuditableTradeRecord] = []
        gross_returns = []
        net_maker_returns = []

        for i in range(0, self.n_bars - h, h):
            s = self.snaps[i]
            btc_trend = self.btc_regime_engine.classify_bar(s.bar_index).trend

            # Strategy: Only hold top altcoin when BTC is in BULLISH_TREND; hold Cash otherwise
            if btc_trend == TrendRegime.BULLISH_TREND:
                top_sym = s.top_asset
                p0 = s.prices[top_sym]
                p1 = self.snaps[i + h].prices[top_sym]
                gross_pct = (p1 - p0) / p0
                net_pct = gross_pct - (config.cost_maker_bps / 10000.0)
            else:
                # Cash allocation: 0 return, 0 cost
                top_sym = "CASH"
                p0 = 1.0
                p1 = 1.0
                gross_pct = 0.0
                net_pct = 0.0

            net_bps = net_pct * 10000.0
            gross_returns.append(gross_pct * 10000.0)
            net_maker_returns.append(net_bps)

            rec = AuditableTradeRecord(
                opportunity_id=f"CS4_REGIME_{len(records) + 1:04d}",
                symbol=top_sym,
                direction="LONG" if top_sym != "CASH" else "CASH",
                entry_bar_index=s.bar_index,
                entry_timestamp_ms=s.timestamp_ms,
                exit_bar_index=self.snaps[i + h].bar_index,
                exit_timestamp_ms=self.snaps[i + h].timestamp_ms,
                intended_entry_price=round(p0, 2),
                effective_entry_price=round(p0, 2),
                exit_price=round(p1, 2),
                exit_reason="REGIME_REBALANCE",
                holding_bars=h,
                is_filled=True,
                fill_ratio=1.0,
                adverse_selection_bps=0.0 if top_sym == "CASH" else 2.0,
                cost_bps=0.0 if top_sym == "CASH" else config.cost_maker_bps,
                gross_return_pct=round(gross_pct, 6),
                net_return_pct=round(net_pct, 6),
                net_return_bps=round(net_bps, 2),
                is_win=net_bps > 0.0,
                is_independent=True,
            )
            records.append(rec)

        res = self._compute_hypothesis_result(
            hyp_id=config.hypothesis_id,
            description="Top momentum Spot allocation gated by BTC Bullish trend regime",
            gross_returns=gross_returns,
            net_maker_returns=net_maker_returns,
            records=records,
            taker_cost_bps=config.cost_taker_bps,
        )
        return res, records

    def _compute_hypothesis_result(
        self,
        hyp_id: str,
        description: str,
        gross_returns: list[float],
        net_maker_returns: list[float],
        records: list[AuditableTradeRecord],
        taker_cost_bps: float,
    ) -> CrossSectionalHypothesisResult:
        n = len(net_maker_returns)
        if n == 0:
            return CrossSectionalHypothesisResult(
                hypothesis_id=hyp_id,
                description=description,
                total_events_evaluated=0,
                independent_decision_events=0,
                gross_expectancy_bps=0.0,
                net_maker_expectancy_bps=0.0,
                net_taker_expectancy_bps=0.0,
                win_rate_maker=0.0,
                win_rate_taker=0.0,
                profit_factor_maker=0.0,
                max_drawdown_bps=0.0,
                t_statistic_maker=0.0,
                bootstrap_ci_95_maker_bps=(0.0, 0.0),
                verdict=CrossSectionalDecisionVerdict.INSUFFICIENT_EVIDENCE,
                scientific_notes="Zero decision events generated.",
            )

        g_arr = np.array(gross_returns)
        m_arr = np.array(net_maker_returns)
        t_arr = np.array([r - (taker_cost_bps - 6.0) for r in net_maker_returns])

        g_mean = float(np.mean(g_arr))
        m_mean = float(np.mean(m_arr))
        t_mean = float(np.mean(t_arr))

        wr_maker = float(np.mean(m_arr > 0.0))
        wr_taker = float(np.mean(t_arr > 0.0))

        wins = m_arr[m_arr > 0.0]
        losses = -m_arr[m_arr < 0.0]
        pf = (float(np.sum(wins)) / float(np.sum(losses))) if np.sum(losses) > 0 else 1.0

        cum = np.cumsum(m_arr)
        peak = np.maximum.accumulate(cum)
        dd = peak - cum
        max_dd = float(np.max(dd)) if len(dd) > 0 else 0.0

        se = float(np.std(m_arr, ddof=1) / math.sqrt(n)) if n > 1 else 1.0
        t_stat = (m_mean / se) if se > 1e-9 else 0.0

        rng = np.random.default_rng(seed=42)
        boots = [np.mean(rng.choice(m_arr, size=n, replace=True)) for _ in range(1000)]
        ci_low = float(np.percentile(boots, 2.5))
        ci_high = float(np.percentile(boots, 97.5))

        # Scientific verdict determination
        if n < 30:
            verdict = CrossSectionalDecisionVerdict.INSUFFICIENT_EVIDENCE
            notes = f"Insufficient sample size (N={n} < 30)."
        elif m_mean <= 0.0:
            verdict = CrossSectionalDecisionVerdict.REJECTED
            notes = f"Negative net maker expectancy ({m_mean:.2f} bps). Rejected after execution costs."
        elif ci_low <= 0.0:
            verdict = CrossSectionalDecisionVerdict.EXPLORATORY
            notes = (
                f"Modest positive expectancy ({m_mean:.2f} bps), but 95% bootstrap CI includes zero "
                f"[{ci_low:.2f}, {ci_high:.2f}] bps. Cannot confirm statistical advantage."
            )
        else:
            verdict = CrossSectionalDecisionVerdict.INDEPENDENT_VALIDATION_CANDIDATE
            notes = f"Statistically distinguishable net-positive expectancy ({m_mean:.2f} bps, CI_low > 0)."

        return CrossSectionalHypothesisResult(
            hypothesis_id=hyp_id,
            description=description,
            total_events_evaluated=n,
            independent_decision_events=n,
            gross_expectancy_bps=round(g_mean, 2),
            net_maker_expectancy_bps=round(m_mean, 2),
            net_taker_expectancy_bps=round(t_mean, 2),
            win_rate_maker=round(wr_maker, 4),
            win_rate_taker=round(wr_taker, 4),
            profit_factor_maker=round(pf, 2),
            max_drawdown_bps=round(max_dd, 2),
            t_statistic_maker=round(t_stat, 2),
            bootstrap_ci_95_maker_bps=(round(ci_low, 2), round(ci_high, 2)),
            verdict=verdict,
            scientific_notes=notes,
        )

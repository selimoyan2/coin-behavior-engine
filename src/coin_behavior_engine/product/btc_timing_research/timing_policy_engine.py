"""Historical BTC Timing Policy Engine (Module 29.5).

Implements transparent, deterministic historical timing policies for research evaluation:
- Policy A: Buy and Hold (Mandatory passive benchmark)
- Policy B: USDT Cash (Capital preservation benchmark)
- Policy C: Simple Trend Filter (Dual moving average / price vs SMA)
- Policy D: Volatility-Aware Allocation (Parkinson volatility scaling)
- Policy E: CBE Regime-Based Allocation (CBE-0.7.0 canonical market regimes)
- Policy F: Combined Trend and CBE Regime Filter (Experimental hybrid)

Enforces spot-only discrete allocation targets: 0%, 25%, 50%, 75%, 100%.
No short selling, no leverage, no borrowed funds.
"""

from __future__ import annotations

import abc
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

ALLOWED_ALLOCATION_TIERS: Tuple[float, ...] = (0.0, 0.25, 0.50, 0.75, 1.0)


def snap_to_tier(raw_allocation: float) -> float:
    """Clamp and snap an allocation fraction to the nearest allowed tier."""
    clamped = max(0.0, min(1.0, float(raw_allocation)))
    best_tier = min(ALLOWED_ALLOCATION_TIERS, key=lambda t: abs(t - clamped))
    return best_tier


@dataclass(frozen=True)
class PolicyDecision:
    """Historical decision outcome for a single point in time."""
    target_btc_allocation: float
    decision_reason: str
    indicators_used: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BaseTimingPolicy(abc.ABC):
    """Abstract base class for historical timing research policies."""

    policy_id: str
    name: str
    description: str

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        self.parameters = parameters or {}

    @abc.abstractmethod
    def evaluate(self, current_candle: Dict[str, Any], historical_context: Optional[Any] = None) -> PolicyDecision:
        """Evaluate decision strictly at candle close T using past information only."""
        pass

    def to_dict(self) -> Dict[str, Any]:
        return {
            "policy_id": self.policy_id,
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class BuyAndHoldPolicy(BaseTimingPolicy):
    """Policy A: Passive Buy and Hold benchmark. Holds 100% BTC throughout."""

    policy_id = "POLICY_BUY_AND_HOLD"
    name = "Buy and Hold (Passive Benchmark)"
    description = "Allocates 100% to BTC at start and holds passively throughout the evaluation period."

    def evaluate(self, current_candle: Dict[str, Any], historical_context: Optional[Any] = None) -> PolicyDecision:
        return PolicyDecision(
            target_btc_allocation=1.0,
            decision_reason="PASSIVE_HOLD: 100% allocation maintained by policy definition.",
            indicators_used={"close": current_candle.get("close")},
        )


class USDTCashPolicy(BaseTimingPolicy):
    """Policy B: USDT Cash Capital Preservation benchmark. Holds 0% BTC throughout."""

    policy_id = "POLICY_USDT_CASH"
    name = "USDT Cash (Capital Preservation Benchmark)"
    description = "Maintains 100% USDT cash (0% BTC) throughout the evaluation period with no yield."

    def evaluate(self, current_candle: Dict[str, Any], historical_context: Optional[Any] = None) -> PolicyDecision:
        return PolicyDecision(
            target_btc_allocation=0.0,
            decision_reason="CAPITAL_PRESERVATION: 100% USDT maintained with no BTC exposure.",
            indicators_used={},
        )


class SimpleTrendPolicy(BaseTimingPolicy):
    """Policy C: Moving Average Trend Filter.

    Allocates 100% to BTC when close > slow_sma, else 0% (USDT cash).
    """

    policy_id = "POLICY_SIMPLE_TREND"
    name = "Simple Moving Average Trend Filter"
    description = "Allocates 100% BTC when close is above moving average, otherwise 0% BTC."

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        super().__init__(parameters)
        self.fast_window = int(self.parameters.get("fast_window", 20))
        self.slow_window = int(self.parameters.get("slow_window", 50))
        self.rule = str(self.parameters.get("rule", "PRICE_ABOVE_SLOW"))

    def evaluate(self, current_candle: Dict[str, Any], historical_context: Optional[Any] = None) -> PolicyDecision:
        close = float(current_candle.get("close", 0.0))
        slow_sma = current_candle.get(f"sma_{self.slow_window}")
        fast_sma = current_candle.get(f"sma_{self.fast_window}")

        if slow_sma is None or (isinstance(slow_sma, float) and (slow_sma == 0.0 or str(slow_sma) == "nan")):
            # Warming up
            return PolicyDecision(
                target_btc_allocation=0.0,
                decision_reason=f"WARMING_UP: Waiting for {self.slow_window} historical candles.",
                indicators_used={"close": close, "slow_sma": None},
            )

        slow_val = float(slow_sma)
        if self.rule == "MA_CROSS" and fast_sma is not None and str(fast_sma) != "nan":
            fast_val = float(fast_sma)
            bullish = fast_val > slow_val
            rule_str = f"fast_sma({fast_val:.2f}) > slow_sma({slow_val:.2f})"
        else:
            bullish = close > slow_val
            rule_str = f"close({close:.2f}) > slow_sma({slow_val:.2f})"

        target = 1.0 if bullish else 0.0
        reason = f"BULLISH_TREND: {rule_str}" if bullish else f"BEARISH_TREND: not {rule_str}"

        return PolicyDecision(
            target_btc_allocation=target,
            decision_reason=reason,
            indicators_used={
                "close": close,
                f"sma_{self.slow_window}": slow_val,
                f"sma_{self.fast_window}": float(fast_sma) if fast_sma is not None and str(fast_sma) != "nan" else None,
            },
        )


class VolatilityAwarePolicy(BaseTimingPolicy):
    """Policy D: Volatility-Aware Allocation.

    Reduces BTC exposure as historical volatility increases:
    - COMPRESSED_VOLATILITY: 100% BTC
    - NORMAL_VOLATILITY: 75% BTC
    - ELEVATED_VOLATILITY: 25% BTC
    - EXTREME_VOLATILITY: 0% BTC
    """

    policy_id = "POLICY_VOLATILITY_AWARE"
    name = "Parkinson Volatility-Scaled Allocation"
    description = "Scales BTC allocation inversely with rolling Parkinson volatility tiers."

    def evaluate(self, current_candle: Dict[str, Any], historical_context: Optional[Any] = None) -> PolicyDecision:
        vol_regime = current_candle.get("volatility_regime", "NORMAL_VOLATILITY")
        p_vol = float(current_candle.get("parkinson_vol_24", 0.0))

        tier_map = {
            "COMPRESSED_VOLATILITY": 1.0,
            "NORMAL_VOLATILITY": 0.75,
            "ELEVATED_VOLATILITY": 0.25,
            "EXTREME_VOLATILITY": 0.0,
        }
        target = snap_to_tier(tier_map.get(vol_regime, 0.50))
        reason = f"VOLATILITY_REGIME_{vol_regime}: Target {target * 100:.0f}% based on Parkinson vol {p_vol:.4f}."

        return PolicyDecision(
            target_btc_allocation=target,
            decision_reason=reason,
            indicators_used={"volatility_regime": vol_regime, "parkinson_vol_24": p_vol},
        )


class CBERegimePolicy(BaseTimingPolicy):
    """Policy E: CBE-0.7.0 Regime-Based Allocation.

    Maps canonical CBE-0.7.0 scientific market regimes to discrete allocations:
    - MOMENTUM_EXPANSION: 100% BTC
    - RECOVERY_ACCUMULATION: 75% BTC
    - CONSOLIDATION_RANGING: 50% BTC
    - DISTRIBUTION: 25% BTC
    - CAPITULATION: 0% BTC
    - HIGH_VOLATILITY_EXPANSION: 0% BTC
    """

    policy_id = "POLICY_CBE_REGIME"
    name = "CBE-0.7.0 Frozen Regime Allocation"
    description = "Allocates exposure using verified canonical market regimes from frozen CBE-0.7.0 model."

    def evaluate(self, current_candle: Dict[str, Any], historical_context: Optional[Any] = None) -> PolicyDecision:
        m_regime = current_candle.get("market_regime", "CONSOLIDATION_RANGING")

        regime_map = {
            "MOMENTUM_EXPANSION": 1.0,
            "RECOVERY_ACCUMULATION": 0.75,
            "CONSOLIDATION_RANGING": 0.50,
            "DISTRIBUTION": 0.25,
            "HIGH_VOLATILITY_EXPANSION": 0.0,
            "CAPITULATION": 0.0,
        }
        target = snap_to_tier(regime_map.get(m_regime, 0.50))
        reason = f"CBE_REGIME_{m_regime}: Target {target * 100:.0f}% mapped from canonical CBE-0.7.0 classification."

        return PolicyDecision(
            target_btc_allocation=target,
            decision_reason=reason,
            indicators_used={"market_regime": m_regime},
        )


class CombinedTrendRegimePolicy(BaseTimingPolicy):
    """Policy F: Combined Trend and CBE Regime Filter.

    Requires trend confirmation (close > sma_slow) AND healthy market regime
    to take exposure. Fails to cash in capitulation or downtrends.
    """

    policy_id = "POLICY_COMBINED_TREND_REGIME"
    name = "Combined Trend & CBE Regime Filter (Experimental)"
    description = "Experimental hybrid requiring moving average trend filter and CBE regime confirmation."

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        super().__init__(parameters)
        self.slow_window = int(self.parameters.get("slow_window", 50))

    def evaluate(self, current_candle: Dict[str, Any], historical_context: Optional[Any] = None) -> PolicyDecision:
        close = float(current_candle.get("close", 0.0))
        slow_sma = current_candle.get(f"sma_{self.slow_window}")
        m_regime = current_candle.get("market_regime", "CONSOLIDATION_RANGING")

        if slow_sma is None or (isinstance(slow_sma, float) and (slow_sma == 0.0 or str(slow_sma) == "nan")):
            return PolicyDecision(
                target_btc_allocation=0.0,
                decision_reason=f"WARMING_UP: Waiting for {self.slow_window} candles.",
                indicators_used={"close": close, "slow_sma": None, "market_regime": m_regime},
            )

        slow_val = float(slow_sma)
        trend_bullish = close > slow_val

        # Adverse regimes force immediate defensive positioning
        if m_regime in ("CAPITULATION", "HIGH_VOLATILITY_EXPANSION"):
            target = 0.0
            reason = f"DEFENSIVE_OVERRIDE: Adverse regime {m_regime} forces 0% BTC."
        elif not trend_bullish:
            target = 0.0
            reason = f"BEARISH_TREND: close({close:.2f}) <= sma_{self.slow_window}({slow_val:.2f}) forces 0% BTC."
        else:
            # Bullish trend and favorable/neutral regime
            if m_regime == "MOMENTUM_EXPANSION":
                target = 1.0
            elif m_regime == "RECOVERY_ACCUMULATION":
                target = 0.75
            elif m_regime == "CONSOLIDATION_RANGING":
                target = 0.50
            else:
                target = 0.25
            reason = f"CONFIRMED_EXPOSURE: Bullish trend and {m_regime} regime yield {target*100:.0f}% BTC."

        return PolicyDecision(
            target_btc_allocation=snap_to_tier(target),
            decision_reason=reason,
            indicators_used={
                "close": close,
                f"sma_{self.slow_window}": slow_val,
                "market_regime": m_regime,
            },
        )


POLICY_REGISTRY: Dict[str, type] = {
    "POLICY_BUY_AND_HOLD": BuyAndHoldPolicy,
    "POLICY_USDT_CASH": USDTCashPolicy,
    "POLICY_SIMPLE_TREND": SimpleTrendPolicy,
    "POLICY_VOLATILITY_AWARE": VolatilityAwarePolicy,
    "POLICY_CBE_REGIME": CBERegimePolicy,
    "POLICY_COMBINED_TREND_REGIME": CombinedTrendRegimePolicy,
    "POLICY_DERIVED_RESEARCH_REGIME": CBERegimePolicy,  # Accurate alias grounded in parity audit
}


def _ensure_experimental_policies_registered() -> None:
    """Lazily registers experimental low-turnover policies to avoid circular import."""
    if "POLICY_TREND_LOW_TURNOVER" in POLICY_REGISTRY:
        return
    try:
        from coin_behavior_engine.product.btc_timing_research.experimental_policies import (
            TrendLowTurnoverPolicy,
            VolatilityHysteresisPolicy,
            DerivedRegimeConfirmationPolicy,
            RiskControlTrendPolicy,
            PeriodicRebalancePolicy,
        )
        POLICY_REGISTRY.update({
            "POLICY_TREND_LOW_TURNOVER": TrendLowTurnoverPolicy,
            "POLICY_VOLATILITY_HYSTERESIS": VolatilityHysteresisPolicy,
            "POLICY_DERIVED_REGIME_CONFIRMATION": DerivedRegimeConfirmationPolicy,
            "POLICY_RISK_CONTROL_TREND": RiskControlTrendPolicy,
            "POLICY_PERIODIC_REBALANCE": PeriodicRebalancePolicy,
        })
    except ImportError:
        pass


# Populate registry at module import time so dictionary does not mutate during iteration
_ensure_experimental_policies_registered()


def create_policy(policy_id: str, parameters: Optional[Dict[str, Any]] = None) -> BaseTimingPolicy:
    """Factory to instantiate any timing policy."""
    _ensure_experimental_policies_registered()
    if policy_id not in POLICY_REGISTRY:
        raise ValueError(f"Unknown policy_id '{policy_id}'. Allowed: {list(POLICY_REGISTRY.keys())}")
    cls = POLICY_REGISTRY[policy_id]
    return cls(parameters)

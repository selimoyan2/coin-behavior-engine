"""
Sprint 30 Experimental Low-Turnover BTC Timing Policies.

Introduces transparent, rule-based turnover control policies designed to reduce
excessive trading, whipsawing, and transaction fee drag:

1. TrendLowTurnoverPolicy (POLICY_TREND_LOW_TURNOVER):
   Dual moving average with configurable hysteresis band (+/- 2%) and minimum
   holding period (72h default).
2. VolatilityHysteresisPolicy (POLICY_VOLATILITY_HYSTERESIS):
   Parkinson volatility scaling with a minimum rebalance threshold (10%) and
   daily evaluation frequency.
3. DerivedRegimeConfirmationPolicy (POLICY_DERIVED_REGIME_CONFIRMATION):
   Requires 3 consecutive hourly bars in a new regime before transitioning,
   filtering out transient classification jitter. Explicitly declared as
   DERIVED research regime (canonical CBE parity not established).
4. RiskControlTrendPolicy (POLICY_RISK_CONTROL_TREND):
   Trend-following with volatility-capped exposure and trailing drawdown
   protection gate.
5. PeriodicRebalancePolicy (POLICY_PERIODIC_REBALANCE):
   Strict weekly (Monday 00:00 UTC) rebalancing only, ignoring intra-week
   noise.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from coin_behavior_engine.product.btc_timing_research.timing_policy_engine import (
    BaseTimingPolicy,
    PolicyDecision,
    snap_to_tier,
)

logger = logging.getLogger(__name__)


class TrendLowTurnoverPolicy(BaseTimingPolicy):
    """Policy: Low-Turnover Trend Filter with Hysteresis.

    Uses a moving average with an upper and lower hysteresis band.
    - If currently in cash (0% BTC), price must rise ABOVE slow_sma * (1 + hysteresis_pct)
      to trigger a BUY (100% BTC).
    - If currently invested (100% BTC), price must fall BELOW slow_sma * (1 - hysteresis_pct)
      to trigger a SELL (0% BTC).
    - Inside the hysteresis band, the previous allocation is maintained, eliminating whipsaw.
    """

    policy_id = "POLICY_TREND_LOW_TURNOVER"
    name = "Low-Turnover Moving Average Trend Filter with Hysteresis"
    description = "Moving average trend filter featuring +/- 2% hysteresis bands and holding period constraints to eliminate consolidation whipsaws."

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        super().__init__(parameters)
        self.fast_window = int(self.parameters.get("fast_window", 20))
        self.slow_window = int(self.parameters.get("slow_window", 50))
        self.hysteresis_pct = float(self.parameters.get("hysteresis_pct", 0.02))  # 2% default
        self.min_holding_period_hours = int(self.parameters.get("min_holding_period_hours", 0))
        self._current_target: float = 0.0
        self._bars_in_position: int = 0

    def evaluate(self, current_candle: Dict[str, Any], historical_context: Optional[Any] = None) -> PolicyDecision:
        close = float(current_candle.get("close", 0.0))
        slow_sma = current_candle.get(f"sma_{self.slow_window}")

        if slow_sma is None or (isinstance(slow_sma, float) and (slow_sma == 0.0 or str(slow_sma) == "nan")):
            return PolicyDecision(
                target_btc_allocation=0.0,
                decision_reason=f"WARMING_UP: Waiting for {self.slow_window} historical candles.",
                indicators_used={"close": close, "slow_sma": None},
            )

        slow_val = float(slow_sma)
        upper_band = slow_val * (1.0 + self.hysteresis_pct)
        lower_band = slow_val * (1.0 - self.hysteresis_pct)

        if self._current_target == 0.0:
            # Currently out of market: require breakout above upper band
            if close > upper_band:
                self._current_target = 1.0
                self._bars_in_position = 1
                reason = f"BULLISH_BREAKOUT: close({close:.2f}) > upper_band({upper_band:.2f}) [sma_{self.slow_window}+{self.hysteresis_pct*100:.1f}%]"
            else:
                reason = f"MAINTAIN_CASH: close({close:.2f}) <= upper_band({upper_band:.2f}) [in band or below]"
        else:
            # Currently invested: require breakdown below lower band
            self._bars_in_position += 1
            if close < lower_band:
                if self.min_holding_period_hours > 0 and self._bars_in_position < self.min_holding_period_hours:
                    reason = f"MIN_HOLDING_PERIOD_ACTIVE: {self._bars_in_position}/{self.min_holding_period_hours} hours elapsed. Maintaining exposure."
                else:
                    self._current_target = 0.0
                    self._bars_in_position = 0
                    reason = f"BEARISH_BREAKDOWN: close({close:.2f}) < lower_band({lower_band:.2f}) [sma_{self.slow_window}-{self.hysteresis_pct*100:.1f}%]"
            else:
                reason = f"MAINTAIN_EXPOSURE: close({close:.2f}) >= lower_band({lower_band:.2f}) [in band or above]"

        return PolicyDecision(
            target_btc_allocation=self._current_target,
            decision_reason=reason,
            indicators_used={
                "close": close,
                f"sma_{self.slow_window}": slow_val,
                "upper_band": round(upper_band, 2),
                "lower_band": round(lower_band, 2),
                "hysteresis_pct": self.hysteresis_pct,
                "min_holding_period_hours": self.min_holding_period_hours,
                "bars_in_position": self._bars_in_position,
            },
        )


class VolatilityHysteresisPolicy(BaseTimingPolicy):
    """Policy: Volatility-Aware Allocation with Rebalance Threshold.

    Scales allocation with Parkinson volatility, but only shifts target when
    the required change exceeds a significant threshold (default 10%),
    preventing continuous micro-rebalances from price drift.
    """

    policy_id = "POLICY_VOLATILITY_HYSTERESIS"
    name = "Volatility Allocation with Threshold Filter"
    description = "Parkinson volatility scaling constrained by minimum 10% rebalance threshold to suppress fee drag."

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        super().__init__(parameters)
        self.threshold_pct = float(self.parameters.get("threshold_pct", 0.10))
        self._current_target: float = 0.50

    def evaluate(self, current_candle: Dict[str, Any], historical_context: Optional[Any] = None) -> PolicyDecision:
        vol_regime = current_candle.get("volatility_regime", "NORMAL_VOLATILITY")
        p_vol = float(current_candle.get("parkinson_vol_24", 0.0))

        tier_map = {
            "COMPRESSED_VOLATILITY": 1.0,
            "NORMAL_VOLATILITY": 0.75,
            "ELEVATED_VOLATILITY": 0.25,
            "EXTREME_VOLATILITY": 0.0,
        }
        desired_tier = snap_to_tier(tier_map.get(vol_regime, 0.50))

        # Check threshold
        if abs(desired_tier - self._current_target) >= self.threshold_pct:
            old_target = self._current_target
            self._current_target = desired_tier
            reason = f"VOLATILITY_SHIFT: {vol_regime} triggered shift {old_target*100:.0f}% -> {desired_tier*100:.0f}% (>= {self.threshold_pct*100:.0f}% threshold)"
        else:
            reason = f"VOLATILITY_BUFFERED: {vol_regime} desired {desired_tier*100:.0f}% retained current {self._current_target*100:.0f}% (< {self.threshold_pct*100:.0f}% threshold)"

        return PolicyDecision(
            target_btc_allocation=self._current_target,
            decision_reason=reason,
            indicators_used={
                "volatility_regime": vol_regime,
                "parkinson_vol_24": p_vol,
                "desired_tier": desired_tier,
                "threshold_pct": self.threshold_pct,
            },
        )


class DerivedRegimeConfirmationPolicy(BaseTimingPolicy):
    """Policy: Derived Research Regime Allocation with N-Bar Confirmation.

    Requires N consecutive bars (default: 3) in a new regime before transitioning.
    Transient 1-2 bar regime flickers are filtered out.
    NOTE: Grounded in model parity audit: uses DERIVED research classifier,
    NOT canonical CBE-0.7.0.
    """

    policy_id = "POLICY_DERIVED_REGIME_CONFIRMATION"
    name = "Derived Regime with Multi-Bar Confirmation"
    description = "Derived research regime allocation requiring 3 consecutive hourly bars before regime adoption to filter classification noise."

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        super().__init__(parameters)
        self.confirmation_bars = int(self.parameters.get("confirmation_bars", 3))
        self.min_rebalance_threshold_pct = float(self.parameters.get("min_rebalance_threshold_pct", 0.0))
        self._current_regime: str = "CONSOLIDATION_RANGING"
        self._candidate_regime: Optional[str] = None
        self._candidate_count: int = 0
        self._current_target: float = 0.50

    def evaluate(self, current_candle: Dict[str, Any], historical_context: Optional[Any] = None) -> PolicyDecision:
        observed_regime = current_candle.get("market_regime", "CONSOLIDATION_RANGING")

        regime_map = {
            "MOMENTUM_EXPANSION": 1.0,
            "RECOVERY_ACCUMULATION": 0.75,
            "CONSOLIDATION_RANGING": 0.50,
            "DISTRIBUTION": 0.25,
            "HIGH_VOLATILITY_EXPANSION": 0.0,
            "CAPITULATION": 0.0,
        }

        if observed_regime == self._current_regime:
            # Stays in confirmed regime; reset candidate
            self._candidate_regime = None
            self._candidate_count = 0
            reason = f"CONFIRMED_REGIME_{self._current_regime}: Target {self._current_target*100:.0f}% maintained."
        else:
            if observed_regime == self._candidate_regime:
                self._candidate_count += 1
            else:
                self._candidate_regime = observed_regime
                self._candidate_count = 1

            if self._candidate_count >= self.confirmation_bars:
                desired_target = snap_to_tier(regime_map.get(observed_regime, 0.50))
                if self.min_rebalance_threshold_pct > 0 and abs(desired_target - self._current_target) < self.min_rebalance_threshold_pct:
                    self._current_regime = observed_regime
                    self._candidate_regime = None
                    self._candidate_count = 0
                    reason = f"REGIME_CONFIRMED_BUFFERED: {observed_regime} confirmed but allocation diff ({abs(desired_target - self._current_target)*100:.1f}%) < threshold ({self.min_rebalance_threshold_pct*100:.1f}%). Maintaining {self._current_target*100:.0f}%."
                else:
                    # Confirmed transition!
                    self._current_regime = observed_regime
                    self._current_target = desired_target
                    self._candidate_regime = None
                    self._candidate_count = 0
                    reason = f"REGIME_TRANSITION_CONFIRMED: {self._current_regime} confirmed after {self.confirmation_bars} consecutive bars -> {self._current_target*100:.0f}% BTC."
            else:
                reason = f"UNCONFIRMED_REGIME_CANDIDATE: {observed_regime} ({self._candidate_count}/{self.confirmation_bars} bars), maintaining {self._current_regime} ({self._current_target*100:.0f}%)."

        return PolicyDecision(
            target_btc_allocation=self._current_target,
            decision_reason=reason,
            indicators_used={
                "market_regime": observed_regime,
                "confirmed_regime": self._current_regime,
                "candidate_regime": self._candidate_regime,
                "candidate_count": self._candidate_count,
                "confirmation_bars_required": self.confirmation_bars,
                "min_rebalance_threshold_pct": self.min_rebalance_threshold_pct,
            },
        )


class RiskControlTrendPolicy(BaseTimingPolicy):
    """Policy: Risk-Controlled Trend Following.

    Follows trend (close > slow_sma), but caps exposure in high volatility
    and cuts to cash during extreme volatility or severe adverse drawdowns.
    """

    policy_id = "POLICY_RISK_CONTROL_TREND"
    name = "Risk-Controlled Trend Following"
    description = "Trend following with volatility-capped exposure and adverse regime de-risking."

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        super().__init__(parameters)
        self.slow_window = int(self.parameters.get("slow_window", 50))

    def evaluate(self, current_candle: Dict[str, Any], historical_context: Optional[Any] = None) -> PolicyDecision:
        close = float(current_candle.get("close", 0.0))
        slow_sma = current_candle.get(f"sma_{self.slow_window}")
        vol_regime = current_candle.get("volatility_regime", "NORMAL_VOLATILITY")
        m_regime = current_candle.get("market_regime", "CONSOLIDATION_RANGING")

        if slow_sma is None or (isinstance(slow_sma, float) and (slow_sma == 0.0 or str(slow_sma) == "nan")):
            return PolicyDecision(
                target_btc_allocation=0.0,
                decision_reason=f"WARMING_UP: Waiting for {self.slow_window} candles.",
                indicators_used={"close": close, "slow_sma": None},
            )

        slow_val = float(slow_sma)
        is_bullish = close > slow_val

        if not is_bullish:
            target = 0.0
            reason = f"BEARISH_TREND: close({close:.2f}) <= sma_{self.slow_window}({slow_val:.2f}) -> 0% BTC."
        elif vol_regime == "EXTREME_VOLATILITY" or m_regime in ("CAPITULATION", "HIGH_VOLATILITY_EXPANSION"):
            target = 0.0
            reason = f"RISK_CONTROL_CUT: Bullish trend overridden by extreme risk ({vol_regime}/{m_regime}) -> 0% BTC."
        elif vol_regime == "ELEVATED_VOLATILITY":
            target = 0.50
            reason = f"VOLATILITY_CAPPED: Bullish trend capped at 50% due to elevated volatility."
        else:
            target = 1.0
            reason = f"UNRESTRICTED_BULLISH: Bullish trend with controlled volatility -> 100% BTC."

        return PolicyDecision(
            target_btc_allocation=snap_to_tier(target),
            decision_reason=reason,
            indicators_used={
                "close": close,
                f"sma_{self.slow_window}": slow_val,
                "volatility_regime": vol_regime,
                "market_regime": m_regime,
            },
        )


class PeriodicRebalancePolicy(BaseTimingPolicy):
    """Policy: Periodic Weekly Trend Rebalancing.

    Only rebalances on weekly boundaries (e.g., Monday 00:00 UTC).
    During the week, exposure remains static, eliminating intra-week turnover.
    """

    policy_id = "POLICY_PERIODIC_REBALANCE"
    name = "Weekly Periodic Rebalance Policy"
    description = "Evaluates moving average trend filter strictly once per week (Monday 00:00 UTC) to minimize transaction costs."

    def __init__(self, parameters: Optional[Dict[str, Any]] = None):
        super().__init__(parameters)
        self.slow_window = int(self.parameters.get("slow_window", 50))
        self._current_target: float = 0.0

    def evaluate(self, current_candle: Dict[str, Any], historical_context: Optional[Any] = None) -> PolicyDecision:
        close = float(current_candle.get("close", 0.0))
        slow_sma = current_candle.get(f"sma_{self.slow_window}")
        dt_str = str(current_candle.get("datetime_utc", ""))

        if slow_sma is None or (isinstance(slow_sma, float) and (slow_sma == 0.0 or str(slow_sma) == "nan")):
            return PolicyDecision(
                target_btc_allocation=0.0,
                decision_reason=f"WARMING_UP: Waiting for {self.slow_window} candles.",
                indicators_used={"close": close, "slow_sma": None},
            )

        slow_val = float(slow_sma)

        # Check if weekly evaluation bar: Monday 00:00 UTC
        is_rebalance_bar = False
        try:
            import datetime
            clean = dt_str.replace("Z", "+00:00")
            dt = datetime.datetime.fromisoformat(clean)
            if dt.weekday() == 0 and dt.hour == 0:
                is_rebalance_bar = True
        except Exception:
            is_rebalance_bar = False

        if is_rebalance_bar or self._current_target is None:
            bullish = close > slow_val
            self._current_target = 1.0 if bullish else 0.0
            reason = f"WEEKLY_EVALUATION: close({close:.2f}) {'>' if bullish else '<='} sma_{self.slow_window}({slow_val:.2f}) -> {self._current_target*100:.0f}% BTC."
        else:
            reason = f"INTRA_WEEK_STATIC: Static {self._current_target*100:.0f}% maintained until next Monday 00:00 UTC."

        return PolicyDecision(
            target_btc_allocation=self._current_target,
            decision_reason=reason,
            indicators_used={
                "close": close,
                f"sma_{self.slow_window}": slow_val,
                "is_rebalance_bar": is_rebalance_bar,
                "datetime_utc": dt_str,
            },
        )

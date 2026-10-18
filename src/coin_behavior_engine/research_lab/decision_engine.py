"""Research decision engine for generating hypothetical paper trading candidates.

Sprint 11.03: Market Behavior Research Lab.
Evaluates opportunity, downside risk, pattern evidence, and event context
to emit BUY_CANDIDATE, SELL_CANDIDATE, HOLD, and NO_TRADE with explainable rejection reasons.
"""

from __future__ import annotations

import uuid
from typing import List, Optional

from coin_behavior_engine.research_lab.contracts import (
    DecisionAction,
    DecisionMode,
    EventIntelligenceRecord,
    MarketBehaviorFeatures,
    MarketRegimeType,
    ProbabilisticPrediction,
    ResearchDecision,
)
from coin_behavior_engine.research_lab.risk_engine import RiskEngine


class ResearchDecisionEngine:
    """Generates research-only hypothetical trading decisions across multiple strategies."""

    def __init__(self, risk_engine: Optional[RiskEngine] = None):
        self.risk_engine = risk_engine or RiskEngine()

    def evaluate_decision(
        self,
        features: MarketBehaviorFeatures,
        prediction: ProbabilisticPrediction,
        active_patterns: List[str],
        strategy_mode: DecisionMode = DecisionMode.TECHNICAL_ONLY_RESEARCH,
        observable_events: Optional[List[EventIntelligenceRecord]] = None,
        currently_holding: bool = False,
        entry_price: Optional[float] = None,
        current_capital: float = 10_000.0,
    ) -> ResearchDecision:
        """Formulate hypothetical decision at current bar close."""
        dec_id = f"DEC-{uuid.uuid4().hex[:8]}"
        curr_price = features.close_price

        # If currently in position, evaluate exit criteria
        if currently_holding and entry_price:
            unrealized_ret = (curr_price - entry_price) / entry_price
            
            # Check for regime collapse
            if features.regime == MarketRegimeType.CASCADE_LIQUIDATION:
                return ResearchDecision(
                    decision_id=dec_id,
                    symbol="BTCUSDT",
                    timestamp_open=features.timestamp_open,
                    datetime_utc=features.datetime_utc,
                    action=DecisionAction.SELL_CANDIDATE,
                    decision_mode=strategy_mode,
                    reason="Emergency liquidation cascade detected; exiting position",
                    target_price=curr_price,
                    stop_loss_price=curr_price,
                    risk_score=0.9,
                )

            # Check context aware negative shock
            if strategy_mode == DecisionMode.CONTEXT_AWARE_RESEARCH and observable_events:
                severe_bear = [e for e in observable_events if e.event_severity >= 0.8 and e.event_direction_hypothesis == "BEARISH"]
                if severe_bear and unrealized_ret < 0:
                    return ResearchDecision(
                        decision_id=dec_id,
                        symbol="BTCUSDT",
                        timestamp_open=features.timestamp_open,
                        datetime_utc=features.datetime_utc,
                        action=DecisionAction.SELL_CANDIDATE,
                        decision_mode=strategy_mode,
                        reason=f"Severe macro risk event '{severe_bear[0].headline[:30]}...' active; risk mitigation exit",
                        target_price=curr_price,
                        stop_loss_price=curr_price,
                        risk_score=0.85,
                    )

            # Otherwise hold until stop-loss or take-profit triggered in simulator
            return ResearchDecision(
                decision_id=dec_id,
                symbol="BTCUSDT",
                timestamp_open=features.timestamp_open,
                datetime_utc=features.datetime_utc,
                action=DecisionAction.HOLD,
                decision_mode=strategy_mode,
                reason="Holding existing position; awaiting target or stop-loss",
            )

        # If NOT in position, evaluate entry criteria
        # Filter 1: Check prediction confidence
        if prediction.confidence_status == "NO_PREDICTION":
            return ResearchDecision(
                decision_id=dec_id,
                symbol="BTCUSDT",
                timestamp_open=features.timestamp_open,
                datetime_utc=features.datetime_utc,
                action=DecisionAction.NO_TRADE,
                decision_mode=strategy_mode,
                reason="Prediction confidence inadequate (NO_PREDICTION)",
            )

        # Filter 2: Check cascade liquidation regime
        if features.regime == MarketRegimeType.CASCADE_LIQUIDATION and not (
            "SHARP_DECLINE_VOLUME_EXHAUSTION" in active_patterns
            or "SUPPORT_BREAKDOWN_FAILED_CONTINUATION" in active_patterns
        ):
            return ResearchDecision(
                decision_id=dec_id,
                symbol="BTCUSDT",
                timestamp_open=features.timestamp_open,
                datetime_utc=features.datetime_utc,
                action=DecisionAction.NO_TRADE,
                decision_mode=strategy_mode,
                reason="Cascade liquidation in progress without volume exhaustion or failed breakdown confirmation",
            )

        # Filter 3: Context-Aware filter for Strategy B
        if strategy_mode == DecisionMode.CONTEXT_AWARE_RESEARCH and observable_events:
            unabsorbed_severe_neg = [
                e for e in observable_events
                if e.event_severity >= 0.75
                and e.event_direction_hypothesis == "BEARISH"
                and "NEGATIVE_EVENT_ABSORPTION" not in active_patterns
            ]
            if unabsorbed_severe_neg:
                return ResearchDecision(
                    decision_id=dec_id,
                    symbol="BTCUSDT",
                    timestamp_open=features.timestamp_open,
                    datetime_utc=features.datetime_utc,
                    action=DecisionAction.NO_TRADE,
                    decision_mode=strategy_mode,
                    reason=f"Context filter: Unabsorbed high-severity event active: '{unabsorbed_severe_neg[0].headline[:40]}...'",
                )

        # Filter 4: Minimum probability and expected return threshold
        min_p_up = 0.44 if strategy_mode != DecisionMode.RISK_CONTROLLED_RESEARCH else 0.48
        min_exp_ret = 0.30 if strategy_mode != DecisionMode.RISK_CONTROLLED_RESEARCH else 0.45

        if prediction.probability_up < min_p_up:
            return ResearchDecision(
                decision_id=dec_id,
                symbol="BTCUSDT",
                timestamp_open=features.timestamp_open,
                datetime_utc=features.datetime_utc,
                action=DecisionAction.NO_TRADE,
                decision_mode=strategy_mode,
                reason=f"Bullish probability insufficient: P(up)={prediction.probability_up:.2f} < threshold {min_p_up:.2f}",
            )

        if prediction.expected_return_pct < min_exp_ret:
            return ResearchDecision(
                decision_id=dec_id,
                symbol="BTCUSDT",
                timestamp_open=features.timestamp_open,
                datetime_utc=features.datetime_utc,
                action=DecisionAction.NO_TRADE,
                decision_mode=strategy_mode,
                reason=f"Expected return insufficient: {prediction.expected_return_pct:.2f}% < threshold {min_exp_ret:.2f}%",
            )

        # Entry criteria met! Compute position sizing & stops
        risk_profile = "STRICT" if strategy_mode == DecisionMode.RISK_CONTROLLED_RESEARCH else "STANDARD"
        pos_usd, qty, sl_price, tp_price = self.risk_engine.calculate_trade_parameters(
            curr_price, features, current_capital, risk_mode=risk_profile
        )

        pos_pct = round((pos_usd / current_capital) * 100.0, 2) if current_capital > 0 else 0.0

        return ResearchDecision(
            decision_id=dec_id,
            symbol="BTCUSDT",
            timestamp_open=features.timestamp_open,
            datetime_utc=features.datetime_utc,
            action=DecisionAction.BUY_CANDIDATE,
            decision_mode=strategy_mode,
            reason=f"Favorable scenario: P(up)={prediction.probability_up:.2f}, exp_ret={prediction.expected_return_pct:+.2f}%, patterns={active_patterns}",
            target_price=tp_price,
            stop_loss_price=sl_price,
            max_holding_bars=24,
            position_size_pct=pos_pct,
            risk_score=round(prediction.downside_risk_pct, 2),
        )

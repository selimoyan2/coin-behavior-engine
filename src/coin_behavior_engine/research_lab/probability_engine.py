"""Probabilistic prediction research engine with calibrated uncertainty and explainability.

Sprint 11.03: Market Behavior Research Lab.
Computes multi-horizon directional probabilities, expected returns, and downside risk.
Explicitly emits NO_PREDICTION when confidence is inadequate.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from coin_behavior_engine.research_lab.contracts import (
    CandleData,
    EventIntelligenceRecord,
    MarketBehaviorFeatures,
    MarketRegimeType,
    ProbabilisticPrediction,
)


class ProbabilityEngine:
    """Computes explainable, probabilistic scenario distributions without forward bias."""

    @classmethod
    def generate_prediction(
        cls,
        features: MarketBehaviorFeatures,
        active_patterns: List[str],
        observable_events: Optional[List[EventIntelligenceRecord]] = None,
        prediction_horizon: str = "60m",
    ) -> ProbabilisticPrediction:
        """Formulate probabilistic forecast based on empirical feature state and active patterns."""
        # 1. Check for insufficient warmup or invalid state -> NO_PREDICTION
        if features.close_price <= 0 or features.atr_14 <= 0 or features.regime == MarketRegimeType.UNCERTAIN:
            return ProbabilisticPrediction(
                symbol="BTCUSDT",
                decision_timestamp=features.timestamp_open,
                datetime_utc=features.datetime_utc,
                prediction_horizon=prediction_horizon,
                market_regime=features.regime,
                probability_up=0.333,
                probability_down=0.333,
                probability_neutral=0.334,
                expected_return_pct=0.0,
                downside_risk_pct=0.0,
                confidence_status="NO_PREDICTION",
                explanation="Insufficient warmup data or regime uncertain.",
            )

        # Baseline prior probabilities
        p_up = 0.33
        p_down = 0.33
        p_neutral = 0.34
        exp_return_pct = 0.0
        downside_risk_pct = round((features.atr_14 * 1.5 / features.close_price) * 100.0, 3)
        explanations = []

        # 2. Market Regime Base Adjustments
        if features.regime == MarketRegimeType.TRENDING_BULL:
            p_up += 0.12
            p_down -= 0.08
            p_neutral -= 0.04
            exp_return_pct += 0.45
            explanations.append("Trending bull regime favors continuation")
        elif features.regime == MarketRegimeType.TRENDING_BEAR:
            p_down += 0.12
            p_up -= 0.08
            p_neutral -= 0.04
            exp_return_pct -= 0.45
            explanations.append("Trending bear regime favors downside continuation")
        elif features.regime == MarketRegimeType.CASCADE_LIQUIDATION:
            p_down += 0.20
            p_up -= 0.15
            p_neutral -= 0.05
            exp_return_pct -= 1.20
            downside_risk_pct *= 1.8
            explanations.append("Severe liquidation cascade in progress; high downside tail risk")

        # HTF 1h & 4h Regime Alignment
        if features.htf_1h_regime == MarketRegimeType.TRENDING_BEAR:
            p_down += 0.08
            p_up -= 0.06
            exp_return_pct -= 0.25
            explanations.append("1h higher-timeframe bear trend dampens upside")
        elif features.htf_1h_regime == MarketRegimeType.TRENDING_BULL:
            p_up += 0.08
            p_down -= 0.06
            exp_return_pct += 0.25
            explanations.append("1h higher-timeframe bull trend reinforces upside")

        # Volatility compression
        if features.volatility_compression_ratio < 0.70:
            p_neutral += 0.15
            p_up -= 0.08
            p_down -= 0.07
            explanations.append("Volatility compression indicates range-bound chop")

        # Price-Volume Divergence
        if features.price_volume_divergence == "BULLISH_DIV":
            p_up += 0.10
            p_down -= 0.07
            exp_return_pct += 0.35
            explanations.append("Bullish price-volume divergence indicates fading sell pressure")
        elif features.price_volume_divergence == "BEARISH_DIV":
            p_down += 0.10
            p_up -= 0.07
            exp_return_pct -= 0.35
            explanations.append("Bearish price-volume divergence indicates fading buy momentum")

        # Scale expected return and downside risk according to prediction horizon
        horizon_scale = {"15m": 0.5, "1h": 1.0, "4h": 2.0}.get(prediction_horizon, 1.0)
        exp_return_pct *= horizon_scale
        downside_risk_pct *= math.sqrt(horizon_scale)

        # 3. Behavioral Pattern Adjustments
        if "SHARP_DECLINE_VOLUME_EXHAUSTION" in active_patterns:
            p_up += 0.16
            p_down -= 0.12
            p_neutral -= 0.04
            exp_return_pct += 0.65
            explanations.append("Volume exhaustion indicates selling climax")

        if "SUPPORT_BREAKDOWN_FAILED_CONTINUATION" in active_patterns:
            p_up += 0.18
            p_down -= 0.14
            p_neutral -= 0.04
            exp_return_pct += 0.80
            explanations.append("Failed support breakdown / bear trap sweep")

        if "BREAKOUT_WITH_VOLUME_CONFIRMATION" in active_patterns:
            p_up += 0.14
            p_down -= 0.10
            p_neutral -= 0.04
            exp_return_pct += 0.70
            explanations.append("Confirmed breakout above local resistance")

        if "HIGH_VOLATILITY_SELLOFF_STABILIZATION" in active_patterns:
            p_up += 0.12
            p_down -= 0.08
            p_neutral -= 0.04
            exp_return_pct += 0.50
            explanations.append("Price stabilizing after volatility spike")

        # 4. Event Context Adjustments (if observable events exist)
        relevant_evt_ids = []
        if observable_events:
            for evt in observable_events:
                relevant_evt_ids.append(evt.event_id)
                if evt.event_direction_hypothesis == "BEARISH":
                    if "NEGATIVE_EVENT_ABSORPTION" in active_patterns:
                        p_up += 0.08
                        p_down -= 0.06
                        exp_return_pct += 0.30
                        explanations.append(f"Negative event '{evt.headline[:35]}...' absorbed without breakdown")
                    else:
                        impact = evt.event_severity * 0.12
                        p_down += impact
                        p_up -= impact * 0.8
                        exp_return_pct -= impact * 5.0
                        explanations.append(f"Bearish event sentiment from '{evt.headline[:35]}...'")
                elif evt.event_direction_hypothesis == "BULLISH":
                    impact = evt.event_severity * 0.12
                    p_up += impact
                    p_down -= impact * 0.8
                    exp_return_pct += impact * 5.0
                    explanations.append(f"Bullish event sentiment from '{evt.headline[:35]}...'")

        # Normalize probabilities so sum = 1.0 and bounds are valid [0.05, 0.90]
        p_up = max(0.05, min(0.90, p_up))
        p_down = max(0.05, min(0.90, p_down))
        rem = 1.0 - (p_up + p_down)
        if rem < 0.05:
            scale = 0.95 / (p_up + p_down)
            p_up *= scale
            p_down *= scale
            p_neutral = 0.05
        else:
            p_neutral = rem

        p_up = round(p_up, 4)
        p_down = round(p_down, 4)
        p_neutral = round(1.0 - p_up - p_down, 4)

        conf = "CALIBRATED" if abs(p_up - p_down) > 0.10 else "LOW_CONFIDENCE"
        supp_zones = [features.support_zone] if features.support_zone > 0 else []
        res_zones = [features.resistance_zone] if features.resistance_zone > 0 else []

        return ProbabilisticPrediction(
            symbol="BTCUSDT",
            decision_timestamp=features.timestamp_open,
            datetime_utc=features.datetime_utc,
            prediction_horizon=prediction_horizon,
            market_regime=features.regime,
            probability_up=p_up,
            probability_down=p_down,
            probability_neutral=p_neutral,
            expected_return_pct=round(exp_return_pct, 3),
            downside_risk_pct=round(downside_risk_pct, 3),
            confidence_status=conf,
            support_zones=supp_zones,
            resistance_zones=res_zones,
            relevant_events=relevant_evt_ids,
            missing_context=[] if observable_events is not None else ["EVENT_CONTEXT_PENDING"],
            explanation="; ".join(explanations) if explanations else "Standard technical baseline",
        )

    @classmethod
    def evaluate_predictions(
        cls,
        predictions: List[ProbabilisticPrediction],
        candles: List[CandleData],
        horizon_bars: int = 12,
    ) -> List[Dict[str, Any]]:
        """Evaluate forward accuracy, calibration, and Brier score against realized price action."""
        evaluation_rows: List[Dict[str, Any]] = []
        n = min(len(predictions), len(candles))

        for i in range(n):
            pred = predictions[i]
            if pred.confidence_status == "NO_PREDICTION" or (i + horizon_bars) >= len(candles):
                continue

            entry_p = candles[i].close
            future_p = candles[i + horizon_bars].close
            realized_ret_pct = ((future_p - entry_p) / entry_p) * 100.0 if entry_p > 0 else 0.0

            # Realized direction
            realized_dir = "UP" if realized_ret_pct > 0.1 else ("DOWN" if realized_ret_pct < -0.1 else "NEUTRAL")
            predicted_dir = "UP" if pred.probability_up > pred.probability_down and pred.probability_up > pred.probability_neutral else (
                "DOWN" if pred.probability_down > pred.probability_up and pred.probability_down > pred.probability_neutral else "NEUTRAL"
            )

            is_correct = (predicted_dir == realized_dir)
            
            # Binary Brier Score for UP outcome
            actual_up_binary = 1.0 if realized_ret_pct > 0 else 0.0
            brier_score_up = round((pred.probability_up - actual_up_binary) ** 2, 4)

            # Max Adverse Excursion during horizon
            future_low = min(candles[k].low for k in range(i + 1, i + horizon_bars + 1))
            mae_pct = round(((future_low - entry_p) / entry_p) * 100.0, 3)

            evaluation_rows.append({
                "datetime_utc": pred.datetime_utc,
                "horizon": pred.prediction_horizon,
                "regime": pred.market_regime.value if hasattr(pred.market_regime, "value") else str(pred.market_regime),
                "prob_up": pred.probability_up,
                "prob_down": pred.probability_down,
                "prob_neutral": pred.probability_neutral,
                "predicted_direction": predicted_dir,
                "expected_return_pct": pred.expected_return_pct,
                "realized_return_pct": round(realized_ret_pct, 3),
                "realized_direction": realized_dir,
                "directional_correct": is_correct,
                "brier_score_up": brier_score_up,
                "predicted_downside_risk_pct": pred.downside_risk_pct,
                "realized_mae_pct": mae_pct,
                "confidence_status": pred.confidence_status,
            })

        return evaluation_rows

    @classmethod
    def export_prediction_evaluation_csv(
        cls,
        evaluation_rows: List[Dict[str, Any]],
        output_csv: Path,
    ) -> None:
        """Export prediction evaluation metrics to CSV."""
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        df = pd.DataFrame(evaluation_rows)
        df.to_csv(output_csv, index=False)

    @classmethod
    def export_predictions_csv(
        cls,
        predictions: List[ProbabilisticPrediction],
        output_csv: Path,
    ) -> None:
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        rows = [p.to_dict() for p in predictions]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

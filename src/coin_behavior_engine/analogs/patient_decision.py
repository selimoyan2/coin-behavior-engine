"""Patient Spot Position Decision Research Module.

Sprint 11.20 Phase 5:
Analyzes whether multi-horizon analog forecasts (1h, 6h, 24h, 7d) provide actionable
structure for patient spot position management:
- Distinguishes:
  1. TEMPORARY_DIP (oversold in bull trend; high 24h/7d upside expected)
  2. DEVELOPING_DOWNTREND (persistent breakdown across 1h, 6h, 24h)
  3. POTENTIAL_REVERSAL (divergence between short-term drop and multi-day analog support)
  4. SIDEWAYS_CONSOLIDATION (range bound with balanced boundary probabilities)
  5. FAILED_BREAKOUT (pierced high then rejected; high down probability)
  6. CONTINUATION_BREAKOUT (momentum expansion with volume confirmation)
- Audits multi-horizon alignment (whether 1h, 6h, 24h, and 7d horizons agree or conflict).
- Issues research-only action propositions: WAIT_USDT, ENTER_BTC, HOLD_BTC, EXIT_TO_USDT, ABSTAIN_CONFLICT.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import numpy as np

from coin_behavior_engine.analogs.probabilistic_forecaster import ProbabilisticPrediction


@dataclass(frozen=True)
class PatientDecisionState:
    """Decision state emitted by the patient position evaluator."""
    decision_timestamp_utc: str
    market_condition_type: str
    horizon_alignment: str  # FULLY_ALIGNED_BULL | FULLY_ALIGNED_BEAR | CONFLICTING_HORIZONS | NEUTRAL_CONSOLIDATION
    prob_direction_24h: str
    expected_magnitude_24h_pct: float
    estimated_adverse_excursion_pct: float
    forecast_uncertainty_score: float
    proposed_patient_action: str
    action_rationale: str
    horizon_breakdown: Dict[str, Dict[str, float]]


class PatientDecisionEvaluator:
    """Evaluates multi-horizon analog forecast coherence for patient spot allocation."""

    def evaluate(self, prediction: ProbabilisticPrediction, fv: Any) -> PatientDecisionState:
        """Synthesize multi-horizon predictions into a patient decision state."""
        if prediction.is_abstained or not prediction.forecasts:
            return PatientDecisionState(
                decision_timestamp_utc=prediction.query_timestamp_utc,
                market_condition_type="UNCERTAIN_MARKET",
                horizon_alignment="CONFLICTING_HORIZONS",
                prob_direction_24h="UNCERTAIN",
                expected_magnitude_24h_pct=0.0,
                estimated_adverse_excursion_pct=0.0,
                forecast_uncertainty_score=1.0,
                proposed_patient_action="WAIT_USDT",
                action_rationale=f"Forecast engine abstained: {prediction.abstention_reason}",
                horizon_breakdown={}
            )

        f1h = prediction.forecasts.get("1h")
        f6h = prediction.forecasts.get("6h")
        f24h = prediction.forecasts.get("24h")
        f7d = prediction.forecasts.get("7d")

        p_up_1h = f1h.prob_up if f1h else 0.50
        p_up_6h = f6h.prob_up if f6h else 0.50
        p_up_24h = f24h.prob_up if f24h else 0.50
        p_up_7d = f7d.prob_up if f7d else 0.50

        exp_ret_24h = f24h.expected_return if f24h else 0.0
        exp_mae_24h = f24h.expected_mae if f24h else 0.0

        # Horizon alignment
        bull_aligned = p_up_1h > 0.52 and p_up_6h > 0.52 and p_up_24h > 0.52 and p_up_7d > 0.50
        bear_aligned = p_up_1h < 0.48 and p_up_6h < 0.48 and p_up_24h < 0.48 and p_up_7d < 0.50

        if bull_aligned:
            alignment = "FULLY_ALIGNED_BULL"
        elif bear_aligned:
            alignment = "FULLY_ALIGNED_BEAR"
        elif abs(p_up_24h - 0.50) < 0.05:
            alignment = "NEUTRAL_CONSOLIDATION"
        else:
            alignment = "CONFLICTING_HORIZONS"

        # Market condition type classification
        condition = "SIDEWAYS_CONSOLIDATION"
        action = "WAIT_USDT"
        rationale = "Neutral conditions; waiting in USDT for clearer directional structure."

        if getattr(fv, "failed_breakout_high_24h", False):
            condition = "FAILED_BREAKOUT"
            action = "EXIT_TO_USDT"
            rationale = "Failed breakout at 24h resistance; high probability of mean-reverting rejection."
        elif getattr(fv, "failed_breakout_low_24h", False) and p_up_24h > 0.55:
            condition = "POTENTIAL_REVERSAL"
            action = "ENTER_BTC"
            rationale = "Bear trap / failed breakdown at 24h support confirmed by bullish analog skew."
        elif getattr(fv, "trend_strength", 0.0) > 1.2 and p_up_1h < 0.45 and p_up_24h > 0.58:
            condition = "TEMPORARY_DIP"
            action = "ENTER_BTC"
            rationale = "Short-term 1h pullback inside established macro bull trend; 24h analogs favor continuation."
        elif getattr(fv, "trend_strength", 0.0) < -1.2 and p_up_24h < 0.42:
            condition = "DEVELOPING_DOWNTREND"
            action = "WAIT_USDT"
            rationale = "Multi-horizon bearish momentum confirmed; capital preservation in USDT required."
        elif alignment == "FULLY_ALIGNED_BULL" and p_up_24h > 0.60:
            condition = "CONTINUATION_BREAKOUT"
            action = "HOLD_BTC"
            rationale = "All horizons aligned bullish with >60% analog continuation probability."
        elif alignment == "CONFLICTING_HORIZONS":
            action = "WAIT_USDT"
            rationale = "Short-term and medium-term analog distributions conflict; abstaining from position risk."

        uncertainty_score = 1.0 - abs(p_up_24h - 0.50) * 2.0  # 0.0 = high certainty, 1.0 = pure coin flip

        horizon_data = {
            h: {
                "prob_up": f.prob_up,
                "expected_return_pct": round(f.expected_return * 100.0, 3),
                "expected_mfe_pct": round(f.expected_mfe * 100.0, 3),
                "expected_mae_pct": round(f.expected_mae * 100.0, 3)
            }
            for h, f in prediction.forecasts.items()
        }

        return PatientDecisionState(
            decision_timestamp_utc=prediction.query_timestamp_utc,
            market_condition_type=condition,
            horizon_alignment=alignment,
            prob_direction_24h="BULLISH" if p_up_24h > 0.52 else ("BEARISH" if p_up_24h < 0.48 else "NEUTRAL"),
            expected_magnitude_24h_pct=round(exp_ret_24h * 100.0, 3),
            estimated_adverse_excursion_pct=round(exp_mae_24h * 100.0, 3),
            forecast_uncertainty_score=round(uncertainty_score, 3),
            proposed_patient_action=action,
            action_rationale=rationale,
            horizon_breakdown=horizon_data
        )

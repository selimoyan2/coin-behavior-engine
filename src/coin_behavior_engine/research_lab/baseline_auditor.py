"""Independent Research Baseline Auditor & Multi-Model Prediction Comparator.

Sprint 11.05: Verified Market Intelligence & Behavioral Prediction Validation.
Compares:
- Model A: Technical-Only Predictions
- Model B: Technical + Verified Market Context
- Model C: Context-Aware + Strict Risk Filtering
Against 4 rigorous statistical baselines:
1. Majority-Class Baseline
2. Persistence Baseline (trailing return sign)
3. Random Walk Baseline (50/50 coin-flip)
4. Simple Momentum Baseline (12-bar trend sign)

Explicitly audits overlapping vs non-overlapping sample independence.
Enforces honest reporting: marks performance INCONCLUSIVE if verified data does not prove edge.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from coin_behavior_engine.research_lab.contracts import (
    BaselineComparisonRecord,
    CandleData,
    MarketBehaviorFeatures,
    MarketContextImpact,
    MarketContextTimelineRecord,
    MarketRegimeType,
    ProbabilisticPrediction,
)
from coin_behavior_engine.research_lab.probability_engine import ProbabilityEngine

logger = logging.getLogger("cbe_baseline_auditor")


class BaselineAuditor:
    """Rigorous statistical comparator for predictive models against baseline null hypotheses."""

    @classmethod
    def generate_model_predictions(
        cls,
        candles: List[CandleData],
        features: List[MarketBehaviorFeatures],
        context_timeline: List[MarketContextTimelineRecord],
        horizon: str = "1h",
    ) -> Dict[str, List[ProbabilisticPrediction]]:
        """Generate predictions for Model A (Technical), Model B (Context), and Model C (Risk-Filtered)."""
        preds_a: List[ProbabilisticPrediction] = []
        preds_b: List[ProbabilisticPrediction] = []
        preds_c: List[ProbabilisticPrediction] = []

        n = min(len(candles), len(features), len(context_timeline))

        for i in range(n):
            f = features[i]
            ctx = context_timeline[i]

            # Model A: Technical-Only (No context input)
            pa = ProbabilityEngine.generate_prediction(
                f,
                active_patterns=[],
                observable_events=None,
                prediction_horizon=horizon,
            )
            preds_a.append(pa)

            # Model B: Technical + Verified Context
            # Context modifies base technical probability
            p_up = pa.probability_up
            p_down = pa.probability_down
            p_neutral = pa.probability_neutral

            if ctx.active_events_count > 0:
                if ctx.has_unabsorbed_negative_shock:
                    # Shift mass toward DOWN unless already contradicted
                    if not ctx.contradiction_detected:
                        shift = 0.15
                        p_down = min(0.85, p_down + shift)
                        p_up = max(0.05, p_up - shift)
                elif ctx.has_positive_catalyst:
                    shift = 0.12
                    p_up = min(0.85, p_up + shift)
                    p_down = max(0.05, p_down - shift)
                elif ctx.contradiction_detected:
                    # News absorption: soften extreme bearishness
                    p_up = min(0.85, p_up + 0.08)
                    p_down = max(0.05, p_down - 0.08)

                # Re-normalize
                rem = 1.0 - (p_up + p_down)
                p_neutral = max(0.05, rem)
                tot = p_up + p_down + p_neutral
                p_up = round(p_up / tot, 4)
                p_down = round(p_down / tot, 4)
                p_neutral = round(1.0 - p_up - p_down, 4)

            pb = ProbabilisticPrediction(
                symbol="BTCUSDT",
                decision_timestamp=f.timestamp_open,
                datetime_utc=f.datetime_utc,
                prediction_horizon=horizon,
                market_regime=f.regime,
                probability_up=p_up,
                probability_down=p_down,
                probability_neutral=p_neutral,
                expected_return_pct=pa.expected_return_pct,
                downside_risk_pct=pa.downside_risk_pct,
                confidence_status=pa.confidence_status,
                support_zones=pa.support_zones,
                resistance_zones=pa.resistance_zones,
                relevant_events=[ctx.primary_event_id] if ctx.primary_event_id else [],
                missing_context=[],
                explanation=f"Technical + Context (Sentiment={ctx.net_sentiment_score:.2f}, Shock={ctx.has_unabsorbed_negative_shock})",
                model_version="1.1.0-sprint11.05-B",
            )
            preds_b.append(pb)

            # Model C: Context-Aware + Strict Risk Filtering
            # Abstains (NEUTRAL) unless HTF trend is aligned and no unabsorbed negative shock exists
            is_htf_safe = f.is_htf_trend_aligned and not ctx.has_unabsorbed_negative_shock
            is_chop_free = f.volatility_compression_ratio >= 0.70

            if is_htf_safe and is_chop_free:
                # Retain Model B probabilities
                pc = ProbabilisticPrediction(
                    symbol="BTCUSDT",
                    decision_timestamp=f.timestamp_open,
                    datetime_utc=f.datetime_utc,
                    prediction_horizon=horizon,
                    market_regime=f.regime,
                    probability_up=p_up,
                    probability_down=p_down,
                    probability_neutral=p_neutral,
                    expected_return_pct=pa.expected_return_pct,
                    downside_risk_pct=pa.downside_risk_pct,
                    confidence_status=pa.confidence_status,
                    support_zones=pa.support_zones,
                    resistance_zones=pa.resistance_zones,
                    relevant_events=[ctx.primary_event_id] if ctx.primary_event_id else [],
                    missing_context=[],
                    explanation="Risk-filtered context approved",
                    model_version="1.1.0-sprint11.05-C",
                )
            else:
                # Force abstention
                pc = ProbabilisticPrediction(
                    symbol="BTCUSDT",
                    decision_timestamp=f.timestamp_open,
                    datetime_utc=f.datetime_utc,
                    prediction_horizon=horizon,
                    market_regime=f.regime,
                    probability_up=0.20,
                    probability_down=0.20,
                    probability_neutral=0.60,
                    expected_return_pct=0.0,
                    downside_risk_pct=pa.downside_risk_pct,
                    confidence_status="LOW_CONFIDENCE",
                    support_zones=pa.support_zones,
                    resistance_zones=pa.resistance_zones,
                    relevant_events=[ctx.primary_event_id] if ctx.primary_event_id else [],
                    missing_context=[],
                    explanation="Abstained due to HTF misalignment, chop, or adverse macro shock",
                    model_version="1.1.0-sprint11.05-C",
                )
            preds_c.append(pc)

        return {
            "Model_A_Technical_Only": preds_a,
            "Model_B_Context_Aware": preds_b,
            "Model_C_Risk_Filtered": preds_c,
        }

    @classmethod
    def evaluate_model_against_baselines(
        cls,
        model_name: str,
        predictions: List[ProbabilisticPrediction],
        candles: List[CandleData],
        horizon_name: str,
        horizon_bars: int,
    ) -> BaselineComparisonRecord:
        """Calculate complete statistical metrics, balanced accuracy, and baseline comparisons."""
        n = min(len(predictions), len(candles))
        valid_indices = [i for i in range(n - horizon_bars)]

        # 1. Forward realized returns and directions
        closes = np.array([candles[i].close for i in range(n)])
        realized_rets = np.zeros(len(valid_indices))
        realized_dirs = []

        for idx, i in enumerate(valid_indices):
            entry_p = closes[i]
            exit_p = closes[i + horizon_bars]
            ret = ((exit_p - entry_p) / entry_p) * 100.0 if entry_p > 0 else 0.0
            realized_rets[idx] = ret
            if ret > 0.10:
                realized_dirs.append("UP")
            elif ret < -0.10:
                realized_dirs.append("DOWN")
            else:
                realized_dirs.append("NEUTRAL")

        realized_dirs = np.array(realized_dirs)

        # 2. Predicted directions
        predicted_dirs = []
        brier_scores = []
        for i in valid_indices:
            p = predictions[i]
            if p.probability_up > p.probability_down and p.probability_up > p.probability_neutral:
                p_dir = "UP"
            elif p.probability_down > p.probability_up and p.probability_down > p.probability_neutral:
                p_dir = "DOWN"
            else:
                p_dir = "NEUTRAL"
            predicted_dirs.append(p_dir)

            actual_up_binary = 1.0 if realized_rets[i] > 0 else 0.0
            bs = (p.probability_up - actual_up_binary) ** 2
            brier_scores.append(bs)

        predicted_dirs = np.array(predicted_dirs)

        # 3. Model Accuracies
        acc_3class = round((predicted_dirs == realized_dirs).mean() * 100.0, 2)

        # Binary accuracy (only when predicting UP or DOWN)
        bin_mask = (predicted_dirs == "UP") | (predicted_dirs == "DOWN")
        if bin_mask.sum() > 0:
            bin_pred = predicted_dirs[bin_mask]
            bin_ret = realized_rets[bin_mask]
            bin_correct = ((bin_pred == "UP") & (bin_ret > 0)) | ((bin_pred == "DOWN") & (bin_ret < 0))
            acc_binary = round(bin_correct.mean() * 100.0, 2)
        else:
            acc_binary = 0.0

        # Balanced accuracy (mean recall across 3 classes)
        recalls = []
        for c_label in ["UP", "DOWN", "NEUTRAL"]:
            c_mask = (realized_dirs == c_label)
            if c_mask.sum() > 0:
                recalls.append((predicted_dirs[c_mask] == c_label).mean())
        balanced_acc = round(float(np.mean(recalls)) * 100.0, 2) if recalls else 0.0

        mean_brier = round(float(np.mean(brier_scores)), 4)

        # 4. Statistical Baselines
        # Baseline 1: Majority Class Baseline
        unique_classes, counts = np.unique(realized_dirs, return_counts=True)
        majority_class = unique_classes[np.argmax(counts)]
        majority_acc = round(float(np.max(counts) / len(realized_dirs)) * 100.0, 2)

        # Baseline 2: Persistence Baseline (previous trailing return sign)
        trailing_rets = np.zeros(len(valid_indices))
        for idx, i in enumerate(valid_indices):
            if i >= horizon_bars:
                trailing_rets[idx] = (closes[i] - closes[i - horizon_bars]) / closes[i - horizon_bars]
        persist_dir = np.where(trailing_rets > 0.001, "UP", np.where(trailing_rets < -0.001, "DOWN", "NEUTRAL"))
        persist_acc = round((persist_dir == realized_dirs).mean() * 100.0, 2)

        # Baseline 3: Random Walk (50% binary, 33.3% 3-class)
        random_walk_acc = 33.33

        # Baseline 4: Simple Momentum Baseline (12-bar trend sign)
        mom_dir = np.zeros(len(valid_indices), dtype=object)
        for idx, i in enumerate(valid_indices):
            look = min(i, 12)
            if look > 0:
                m_ret = (closes[i] - closes[i - look]) / closes[i - look]
                mom_dir[idx] = "UP" if m_ret > 0.001 else ("DOWN" if m_ret < -0.001 else "NEUTRAL")
            else:
                mom_dir[idx] = "NEUTRAL"
        momentum_acc = round((mom_dir == realized_dirs).mean() * 100.0, 2)

        edge_over_maj = round(acc_3class - majority_acc, 2)
        edge_over_rnd = round(acc_3class - random_walk_acc, 2)

        # Sample independence audit
        n_overlapping = len(valid_indices)
        n_independent = max(1, n_overlapping // horizon_bars)

        # Statistical Verdict
        if acc_3class < majority_acc and acc_binary <= 50.0:
            verdict = "NO_EDGE"
        elif n_independent < 30:
            verdict = "INCONCLUSIVE"
        elif edge_over_maj > 3.0 and edge_over_rnd > 5.0 and acc_binary > 53.0:
            verdict = "ADVANTAGE_PROVEN"
        else:
            verdict = "INCONCLUSIVE"

        return BaselineComparisonRecord(
            horizon=horizon_name,
            model_name=model_name,
            accuracy_3class=acc_3class,
            accuracy_binary=acc_binary,
            balanced_accuracy=balanced_acc,
            brier_score=mean_brier,
            majority_class_baseline_accuracy=majority_acc,
            persistence_baseline_accuracy=persist_acc,
            random_walk_baseline_accuracy=random_walk_acc,
            momentum_baseline_accuracy=momentum_acc,
            edge_over_majority=edge_over_maj,
            edge_over_random=edge_over_rnd,
            sample_count_overlapping=n_overlapping,
            sample_count_independent=n_independent,
            statistical_verdict=verdict,
        )

    @classmethod
    def run_full_baseline_comparison(
        cls,
        candles: List[CandleData],
        features: List[MarketBehaviorFeatures],
        context_timeline: List[MarketContextTimelineRecord],
    ) -> List[BaselineComparisonRecord]:
        """Run full grid of models across 15m, 1h, and 4h horizons."""
        records: List[BaselineComparisonRecord] = []
        horizons = [("15m", 3), ("1h", 12), ("4h", 48)]

        for h_name, h_bars in horizons:
            model_preds = cls.generate_model_predictions(
                candles, features, context_timeline, horizon=h_name
            )
            for m_name, preds in model_preds.items():
                rec = cls.evaluate_model_against_baselines(
                    model_name=m_name,
                    predictions=preds,
                    candles=candles,
                    horizon_name=h_name,
                    horizon_bars=h_bars,
                )
                records.append(rec)

        return records

    @classmethod
    def export_baseline_comparison_csv(
        cls,
        records: List[BaselineComparisonRecord],
        output_csv: Path,
    ) -> None:
        """Export prediction_baseline_comparison.csv deliverable."""
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        rows = [r.to_dict() for r in records]
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

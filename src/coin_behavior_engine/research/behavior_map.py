"""2026 BTC Behavior Map orchestrator."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional
import pandas as pd

from coin_behavior_engine.config.schema import ResearchConfig
from coin_behavior_engine.events.detector import EventDetector
from coin_behavior_engine.events.multitimeframe import MultiTimeframeLinker
from coin_behavior_engine.events.windows import EventWindowExtractor
from coin_behavior_engine.features.pipeline import FeaturePipeline
from coin_behavior_engine.regimes.classifier import RegimeClassifier
from coin_behavior_engine.research.september21 import audit_september_21_movement
from coin_behavior_engine.utils.logging import logger


class BehaviorMapEngine:
    """Orchestrates comprehensive 2026 behavioral research pipeline."""

    def __init__(self, config: Optional[ResearchConfig] = None):
        self.config = config or ResearchConfig()
        self.feature_pipeline = FeaturePipeline(self.config)
        self.regime_classifier = RegimeClassifier(self.config.regimes)
        self.event_detector = EventDetector(self.config.events)
        self.window_extractor = EventWindowExtractor(
            timeframe_minutes=5,
            failed_expansion_threshold_pct=self.config.events.failed_expansion_max_followthrough_pct
        )
        self.mtf_linker = MultiTimeframeLinker(
            tolerance_minutes=self.config.multitimeframe.linkage_tolerance_minutes
        )
        self.reports_dir = Path(self.config.paths.reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def run(
        self,
        timeframe_dfs: Dict[str, pd.DataFrame],
        include_september_audit: bool = True
    ) -> Dict[str, Any]:
        """
        Execute full research workflow:
        1. Feature extraction per timeframe
        2. Regime detection on primary (5m) and higher timeframes
        3. Event detection per timeframe
        4. Multi-timeframe event linkage
        5. Pre/Post event window outcome extraction (strictly separated)
        6. September 21 objective audit (optional post-hoc inspection)
        7. Export machine-readable datasets
        """
        logger.info("Starting 2026 BTC Behavior Map research run...")

        if "5m" not in timeframe_dfs:
            raise KeyError("timeframe_dfs must include canonical 5m candles.")

        features_by_tf: Dict[str, pd.DataFrame] = {}
        events_by_tf: Dict[str, pd.DataFrame] = {}
        regimes_by_tf: Dict[str, pd.DataFrame] = {}

        # 1 & 2. Features and Regimes per timeframe
        for tf, df in timeframe_dfs.items():
            feat_df = self.feature_pipeline.compute_all_features(df)
            bar_regimes, regime_blocks = self.regime_classifier.detect_regimes(feat_df)
            feat_df["regime_label"] = bar_regimes

            # Detect events
            scored_df, ev_df = self.event_detector.detect_events(feat_df, timeframe=tf)

            features_by_tf[tf] = scored_df
            events_by_tf[tf] = ev_df
            regimes_by_tf[tf] = regime_blocks

        # 3. Multi-timeframe linkage
        global_events_df, updated_events_by_tf = self.mtf_linker.link_events(events_by_tf)

        # 4. PRE/POST outcome evaluation on primary 5m events
        events_5m = updated_events_by_tf.get("5m", pd.DataFrame())
        evaluated_5m_events = self.window_extractor.evaluate_event_outcomes(
            events_5m, timeframe_dfs["5m"]
        )

        # 5. September 21 Audit (purely post-hoc read-only inspection)
        sept21_audit = None
        if include_september_audit:
            sept21_audit = audit_september_21_movement(
                evaluated_5m_events, features_by_tf["5m"], global_events_df
            )

        # 6. Save machine-readable outputs
        # 2026_events.parquet and csv
        events_pq_path = self.reports_dir / "2026_events.parquet"
        events_csv_path = self.reports_dir / "2026_events.csv"
        evaluated_5m_events.to_parquet(events_pq_path, index=False)
        evaluated_5m_events.to_csv(events_csv_path, index=False)
        logger.info(f"Saved {len(evaluated_5m_events)} 5m events to {events_pq_path} and {events_csv_path}")

        # 2026_regimes.parquet
        regimes_pq_path = self.reports_dir / "2026_regimes.parquet"
        regimes_5m = regimes_by_tf.get("5m", pd.DataFrame())
        regimes_5m.to_parquet(regimes_pq_path, index=False)
        logger.info(f"Saved {len(regimes_5m)} regime episodes to {regimes_pq_path}")

        # 2026_behavior_summary.json
        summary_path = self.reports_dir / "2026_behavior_summary.json"
        behavior_summary = self._build_behavior_summary(
            timeframe_dfs["5m"], features_by_tf["5m"], regimes_5m, evaluated_5m_events, global_events_df, sept21_audit
        )
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(behavior_summary, f, indent=2)
        logger.info(f"Saved behavior summary to {summary_path}")

        return {
            "features_by_tf": features_by_tf,
            "events_5m": evaluated_5m_events,
            "global_events": global_events_df,
            "regimes_5m": regimes_5m,
            "september_21_audit": sept21_audit,
            "behavior_summary": behavior_summary,
        }

    def _build_behavior_summary(
        self,
        df_5m: pd.DataFrame,
        features_5m: pd.DataFrame,
        regimes_5m: pd.DataFrame,
        events_5m: pd.DataFrame,
        global_events: pd.DataFrame,
        sept21: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Aggregate statistical summary metrics across the 2026 dataset."""
        ret_series = features_5m["return_simple"]
        abs_ret_series = ret_series.abs()

        # Regime breakdown
        regime_dist = {}
        if not regimes_5m.empty:
            for r_label, group in regimes_5m.groupby("regime_label"):
                regime_dist[r_label] = {
                    "count": len(group),
                    "total_hours": round(float(group["duration_hours"].sum()), 1),
                    "avg_duration_hours": round(float(group["duration_hours"].mean()), 2),
                }

        # Event breakdown
        event_dist = {}
        if not events_5m.empty:
            for etype, group in events_5m.groupby("event_type"):
                event_dist[etype] = {
                    "count": len(group),
                    "avg_score": round(float(group["event_score"].mean()), 4),
                    "max_score": round(float(group["event_score"].max()), 4),
                }

        # Outcome breakdown
        outcome_dist = {}
        if not events_5m.empty and "outcome_classification" in events_5m.columns:
            outcome_dist = events_5m["outcome_classification"].value_counts().to_dict()

        summary = {
            "research_period": {
                "start_utc": str(features_5m["datetime_open"].min()) if "datetime_open" in features_5m else None,
                "end_utc": str(features_5m["datetime_open"].max()) if "datetime_open" in features_5m else None,
                "total_candles_5m": len(features_5m),
            },
            "market_distributions": {
                "mean_5m_return": round(float(ret_series.mean()), 6),
                "std_5m_return": round(float(ret_series.std()), 6),
                "skewness_5m_return": round(float(ret_series.skew()), 4),
                "kurtosis_5m_return": round(float(ret_series.kurtosis()), 4),
                "quantiles_abs_return": {
                    "p50": round(float(abs_ret_series.quantile(0.50)), 6),
                    "p90": round(float(abs_ret_series.quantile(0.90)), 6),
                    "p99": round(float(abs_ret_series.quantile(0.99)), 6),
                    "p99_9": round(float(abs_ret_series.quantile(0.999)), 6),
                },
            },
            "regimes_summary": {
                "total_regime_blocks": len(regimes_5m),
                "distribution_by_type": regime_dist,
            },
            "events_summary": {
                "total_events_detected_5m": len(events_5m),
                "significant_events_count": int(events_5m["is_significant"].sum()) if not events_5m.empty else 0,
                "distribution_by_type": event_dist,
                "outcomes_classification": outcome_dist,
            },
            "multitimeframe_summary": {
                "total_global_events": len(global_events),
                "events_spanning_multiple_tfs": int((global_events["timeframe_count"] > 1).sum()) if not global_events.empty else 0,
            },
            "september_21_audit": sept21,
        }
        return summary

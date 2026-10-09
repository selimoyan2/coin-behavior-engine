"""CBE-0.8.0 Master Shadow Collector & Observation Engine.

Orchestrates:
- Source ingestion (offline fixture or protected live source).
- Bounded 350-candle rolling buffer management and atomic snapshots.
- Exact canonical 3-feature reconstruction.
- Dual-branch inference: Candidate C (global) and Candidate E (regime-conditional).
- Append-only immutable forecast event store with SHA-256 hash chaining.
- Contiguous forward outcome maturity resolution (1h, 4h, 24h).
- Deterministic 10-state fail-closed eligibility state machine.
- Local observation-only health monitoring.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from coin_behavior_engine.candidate_v080.capture_manager import (
    CaptureState,
    EligibilityStateMachineV080,
    FeatureQualityMetadata,
    FeatureQualityStatus,
    TimestampAuditRecord,
)
from coin_behavior_engine.candidate_v080.feed_adapter import (
    CANDLE_INTERVAL_MS,
    FULL_WARMUP_BARS,
    CandleData,
    FeedAdapterError,
    ReconstructedFeatures,
)
from coin_behavior_engine.shadow_v080.candle_source import (
    BaseCandleSource,
    OfflineFixtureSource,
    ReadOnlyLiveBinanceSource,
    SafetyInterlockError,
    SourceDataError,
)
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.event_integrity import EventIntegrityAuditorV080
from coin_behavior_engine.shadow_v080.feature_pipeline import FeaturePipelineV080
from coin_behavior_engine.shadow_v080.health_monitor import ShadowHealthMonitorV080
from coin_behavior_engine.shadow_v080.inference_runner import (
    DualBranchInferenceRunnerV080,
    DualBranchPredictionResult,
)
from coin_behavior_engine.shadow_v080.outcome_resolver import (
    OutcomeResolverV080,
    ShadowOutcomeEvent,
)
from coin_behavior_engine.shadow_v080.prediction_store import (
    ImmutablePredictionStoreV080,
    ShadowPredictionEvent,
)

logger = logging.getLogger("cbe_shadow_collector")


class ShadowCollectorV080:
    """Master orchestrator for CBE-0.8.0 shadow observation."""

    def __init__(
        self,
        config: ShadowCollectorConfig,
        source: BaseCandleSource,
        record_label: str = "HISTORICAL_REPLAY",
    ):
        self.config = config
        self.config.ensure_directories()
        self.source = source
        self.record_label = record_label

        self.feature_pipeline = FeaturePipelineV080(config)
        self.inference_runner = DualBranchInferenceRunnerV080(config)
        self.prediction_store = ImmutablePredictionStoreV080(config.prediction_dir)
        self.outcome_resolver = OutcomeResolverV080(config.outcome_dir)
        self.health_monitor = ShadowHealthMonitorV080(config)
        self.state_machine = EligibilityStateMachineV080(CaptureState.INITIALIZING)

        self.last_candle_close_utc = ""
        self.total_cycles = 0

    def initialize(self) -> bool:
        """Initialize buffer from local snapshot (Option C) or cold start (Option D)."""
        logger.info("Initializing CBE-0.8.0 Shadow Collector...")

        # 1. Attempt primary strategy: restore local snapshot
        restored, msg = self.feature_pipeline.restore_from_snapshot()
        if restored:
            buf_len = len(self.feature_pipeline.adapter.buffer)
            if buf_len >= self.config.full_warmup_bars:
                self.state_machine.transition_to(
                    CaptureState.FULL_WINDOW_READY, f"Restored {buf_len} bars from snapshot"
                )
            else:
                self.state_machine.transition_to(
                    CaptureState.WARMING_UP, f"Restored {buf_len} bars (below {self.config.full_warmup_bars})"
                )
            logger.info(f"Snapshot restore successful: {msg}")
            return True

        # 2. Fallback: Cold start in WARMING_UP
        self.state_machine.transition_to(CaptureState.WARMING_UP, "Cold start (no valid snapshot found)")
        logger.info("Starting in cold warm-up mode.")
        return True

    def audit_full_history(self):
        """Run complete bit-for-bit historical hash chain audit from genesis."""
        return EventIntegrityAuditorV080.audit_prediction_chain(self.prediction_store.events_file)

    def step(
        self,
        simulated_receipt_time_ms: Optional[int] = None,
        simulated_wall_time_ms: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Execute one complete 5-minute observation cycle.

        Ingests candle -> Reconstructs features -> Audits eligibility ->
        Runs dual inference -> Appends immutable events -> Resolves matured outcomes.
        """
        t0 = time.perf_counter()
        self.total_cycles += 1

        # 1. Fetch next closed candle
        try:
            candle = self.source.fetch_next_candle()
        except SafetyInterlockError as e:
            self.health_monitor.record_error(str(e))
            self.state_machine.transition_to(CaptureState.PAUSED, str(e))
            raise
        except SourceDataError as e:
            self.health_monitor.record_error(str(e))
            self.state_machine.transition_to(CaptureState.INVALID_CANDLE, str(e))
            return {"status": "ERROR_SOURCE_DATA", "error": str(e)}

        if candle is None:
            return {"status": "NO_CANDLE_AVAILABLE"}

        # 2. Timing and clock skew check
        rec_ms = simulated_receipt_time_ms if simulated_receipt_time_ms is not None else int(time.time() * 1000)
        wall_ms = simulated_wall_time_ms if simulated_wall_time_ms is not None else int(time.time() * 1000)
        clock_skew = abs(float(rec_ms - wall_ms))
        clock_trusted = clock_skew <= self.config.clock_skew_budget_ms

        if not clock_trusted:
            if self.state_machine.current_state in [
                CaptureState.INITIALIZING,
                CaptureState.WARMING_UP,
                CaptureState.FULL_WINDOW_READY,
                CaptureState.ELIGIBLE,
            ]:
                self.state_machine.transition_to(
                    CaptureState.CLOCK_UNTRUSTED, f"Clock skew {clock_skew:.1f}ms exceeds budget"
                )

        # 3. Add candle to buffer
        ok, msg = self.feature_pipeline.add_candle(candle)
        if not ok:
            if "GAP" in msg.upper() or "CONTINUITY" in msg.upper():
                self.health_monitor.record_gap()
                self.state_machine.transition_to(CaptureState.SOURCE_GAP, msg)
            else:
                self.state_machine.transition_to(CaptureState.INVALID_CANDLE, msg)
            return {"status": "CANDLE_REJECTED", "reason": msg}

        self.last_candle_close_utc = candle.datetime_close

        # 4. Check for staleness (> 10m since close)
        is_stale = (rec_ms - candle.timestamp_close) > (2 * CANDLE_INTERVAL_MS)
        if is_stale and self.state_machine.current_state in [CaptureState.FULL_WINDOW_READY, CaptureState.ELIGIBLE]:
            self.state_machine.transition_to(CaptureState.STALE_DATA, "Candle is stale (>10m old)")

        # 5. Reconstruct features & evaluate quality
        recon, quality = self.feature_pipeline.compute_features()

        # 6. State machine transitions
        buf_len = len(self.feature_pipeline.adapter.buffer)
        if self.state_machine.current_state == CaptureState.INITIALIZING:
            if buf_len >= self.config.full_warmup_bars:
                self.state_machine.transition_to(CaptureState.FULL_WINDOW_READY, f"Buffer reached {buf_len} bars")
            else:
                self.state_machine.transition_to(CaptureState.WARMING_UP, "Ingested first candle")
        elif self.state_machine.current_state == CaptureState.WARMING_UP:
            if buf_len >= self.config.full_warmup_bars:
                self.state_machine.transition_to(CaptureState.FULL_WINDOW_READY, f"Buffer reached {buf_len} bars")

        if self.state_machine.current_state == CaptureState.FULL_WINDOW_READY:
            if clock_trusted and not is_stale and quality.eligible_for_prospective_scoring:
                self.state_machine.transition_to(CaptureState.ELIGIBLE, "All eligibility conditions met")

        # 7. Run Dual-Branch Inference if features are computably available
        emitted_hashes = []
        if recon.status in ("READY", "READY_PARTIAL_WARMUP"):
            origin_utc = recon.forecast_origin_utc
            dual_pred = self.inference_runner.predict(recon.features, origin_utc)

            # Store predictions for both branches across all 3 horizons
            commit_utc = pd.Timestamp.now(tz="UTC").isoformat()
            component_hashes = {
                "bundle_sha256": "7755ddcb369c29825f9205f09e805b2e518526726b4bd5d948787d24c9419ad0",
                "thresholds_sha256": "3979ab8e37377f1d5cb2623c63c20081078ae49c5bcbedcbb860affe3dfd95d9",
                "cal_c_sha256": "d7ce73edf6595c9ef167a8ec69f4e40f102dff2f32d8f265cf3efe4f60ef89ce",
                "cal_e_sha256": "6821136ad71411b8778c481055d4204640d19be0acaedaf8db3cd18ee3b4bf50",
            }

            for branch_name, intervals_dict in [
                ("candidate_c", dual_pred.candidate_c_intervals),
                ("candidate_e", dual_pred.candidate_e_intervals),
            ]:
                for h, fc in intervals_dict.items():
                    # Calculate target maturity timestamp
                    h_mins = 60 if h == "1h" else (240 if h == "4h" else 1440)
                    mat_dt = pd.Timestamp(origin_utc) + pd.Timedelta(minutes=h_mins)
                    mat_utc = mat_dt.strftime("%Y-%m-%dT%H:%M:%SZ")

                    # Prospective eligibility flag
                    is_scored = self.state_machine.is_eligible and quality.eligible_for_prospective_scoring

                    ev = ShadowPredictionEvent(
                        event_id=f"PRED-{origin_utc[:16]}-{branch_name}-{h}",
                        experiment_id=self.config.experiment_id,
                        protocol_version=self.config.protocol_version,
                        candidate_branch=branch_name,
                        forecast_origin_utc=origin_utc,
                        durable_commit_time_utc=commit_utc,
                        target_horizon=h,
                        target_maturity_utc=mat_utc,
                        feature_fingerprint=recon.feature_fingerprint,
                        component_hashes=component_hashes,
                        data_quality={
                            "eligible_for_prospective_scoring": is_scored,
                            "feature_quality_status": quality.feature_quality_status,
                            "zero_variance_detected": quality.zero_variance_detected,
                            "fallback_applied": quality.fallback_applied,
                            "lookback_bars": recon.lookback_bars,
                        },
                        point_prediction=fc.point_forecast,
                        interval_80={"lower": fc.lower_80, "upper": fc.upper_80, "width": fc.width_80},
                        interval_95={"lower": fc.lower_95, "upper": fc.upper_95, "width": fc.width_95},
                        market_state=dual_pred.primary_state,
                        record_label=self.record_label,
                    )
                    h_rec = self.prediction_store.append_event(ev)
                    emitted_hashes.append(h_rec)

        # 8. Resolve Matured Outcomes
        unmatured = self.prediction_store.get_unmatured_events()
        available = self.feature_pipeline.adapter.buffer
        resolved_outcomes = self.outcome_resolver.resolve_matured_predictions(
            pending_events=unmatured,
            available_candles=available,
            current_time_ms=candle.timestamp_close,
        )
        if resolved_outcomes:
            matured_hashes = {o.prediction_event_hash for o in resolved_outcomes}
            self.prediction_store.prune_matured_events(matured_hashes)

        # 9. Persist snapshot
        self.feature_pipeline.persist_snapshot()

        # 10. Audit Chain & Record Telemetry
        cycle_ms = (time.perf_counter() - t0) * 1000.0
        hash_chain_valid = self.prediction_store.is_chain_intact

        req_count = getattr(self.source, "request_count", 0)
        telemetry = self.health_monitor.capture_telemetry(
            collector_status=self.state_machine.current_state.value,
            source_status="ACTIVE",
            last_candle_close_utc=self.last_candle_close_utc,
            buffer_count=len(self.feature_pipeline.adapter.buffer),
            warmup_status="FULL_WINDOW" if buf_len >= 288 else "WARMING_UP",
            clock_trusted=clock_trusted,
            total_predictions=self.prediction_store.event_count,
            pending_outcomes=len(self.prediction_store.get_unmatured_events()),
            matured_outcomes=len(self.outcome_resolver._seen_predictions),
            invalidated_outcomes=0,
            hash_chain_valid=hash_chain_valid,
            cpu_time_ms=cycle_ms,
            network_req_count=req_count,
        )

        return {
            "status": "SUCCESS",
            "state": self.state_machine.current_state.value,
            "candle_close_utc": self.last_candle_close_utc,
            "buffer_count": buf_len,
            "emitted_events": len(emitted_hashes),
            "matured_outcomes": len(resolved_outcomes),
            "cycle_latency_ms": round(cycle_ms, 2),
            "telemetry": telemetry.to_dict(),
        }

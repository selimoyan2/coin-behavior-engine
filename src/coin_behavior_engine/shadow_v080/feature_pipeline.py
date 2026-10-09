"""Feature Reconstruction & Buffer Management Pipeline for CBE-0.8.0 Shadow Collector.

Reuses the audited FeedAdapterV080 and SnapshotManagerV080 components.
Enforces:
- Bounded 350-candle rolling buffer.
- Exact canonical 3-feature computation.
- Quality metadata distinguishing genuine zero z-scores from fallbacks.
- Strict closed-candle causality.
"""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from coin_behavior_engine.candidate_v080.capture_manager import (
    FeatureQualityMetadata,
    FeatureQualityStatus,
    SnapshotHeader,
    SnapshotManagerV080,
)
from coin_behavior_engine.candidate_v080.feed_adapter import (
    BUFFER_CAPACITY,
    FULL_WARMUP_BARS,
    MIN_WARMUP_BARS,
    CandleData,
    FeedAdapterError,
    FeedAdapterV080,
    ReconstructedFeatures,
)
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig

logger = logging.getLogger("cbe_feature_pipeline")


class FeaturePipelineV080:
    """Encapsulates buffer management, snapshotting, and feature reconstruction."""

    def __init__(self, config: ShadowCollectorConfig):
        self.config = config
        self.adapter = FeedAdapterV080(buffer_capacity=config.max_buffer_candles)
        self.snapshot_manager = SnapshotManagerV080(config.snapshot_dir)
        self.sequence_number = 0

    def restore_from_snapshot(self) -> Tuple[bool, str]:
        """Attempt to restore buffer from local atomic snapshot."""
        if not self.snapshot_manager.snapshot_file.exists():
            return False, "No snapshot file found"

        try:
            header, candles = self.snapshot_manager.load_snapshot()
            self.adapter.reset()
            for c in candles:
                self.adapter.add_candle(c)
            self.sequence_number = header.last_sequence_number
            return True, f"Restored {len(candles)} candles (seq={self.sequence_number})"
        except Exception as e:
            logger.warning(f"Snapshot restore failed: {e}")
            self.adapter.reset()
            return False, str(e)

    def persist_snapshot(self) -> Optional[SnapshotHeader]:
        """Atomically persist current buffer state to disk."""
        if not self.adapter.buffer:
            return None
        return self.snapshot_manager.save_snapshot(self.adapter.buffer, self.sequence_number)

    def add_candle(self, candle: CandleData) -> Tuple[bool, str]:
        """Add candle to buffer with geometry and continuity checks."""
        self.sequence_number += 1
        return self.adapter.add_candle(candle)

    def compute_features(self) -> Tuple[ReconstructedFeatures, FeatureQualityMetadata]:
        """Reconstruct canonical features and evaluate quality metadata."""
        recon = self.adapter.reconstruct_features()
        quality = self._evaluate_quality(recon)
        return recon, quality

    def _evaluate_quality(self, recon: ReconstructedFeatures) -> FeatureQualityMetadata:
        """Inspect reconstructed features to separate genuine zeros from fallbacks."""
        buf_len = recon.lookback_bars
        feats = recon.features

        if recon.status not in ("READY", "READY_PARTIAL_WARMUP") or buf_len == 0:
            return FeatureQualityMetadata(
                raw_feature_available=False,
                rolling_window_count=buf_len,
                zero_variance_detected=False,
                missing_input_detected=True,
                fallback_applied=True,
                feature_quality_status=FeatureQualityStatus.INSUFFICIENT_WINDOW.value,
                eligible_for_prospective_scoring=False,
                quality_notes=["Buffer below minimum required lookback."],
            )

        volumes = [c.volume for c in self.adapter.buffer]
        recent_volumes = volumes[-self.config.full_warmup_bars:]
        vol_std = float(import_numpy_std(recent_volumes))

        zero_var = (vol_std == 0.0)
        missing_input = any(math.isnan(v) or math.isinf(v) for v in recent_volumes)
        fallback_applied = False
        quality_status = FeatureQualityStatus.PRISTINE
        notes = []

        if zero_var:
            fallback_applied = True
            quality_status = FeatureQualityStatus.ZERO_VARIANCE_FALLBACK
            notes.append("Volume standard deviation is 0.0.")
        elif missing_input:
            fallback_applied = True
            quality_status = FeatureQualityStatus.MISSING_INPUT_FALLBACK
            notes.append("Non-finite volume input detected.")
        elif buf_len < self.config.full_warmup_bars:
            quality_status = FeatureQualityStatus.INSUFFICIENT_WINDOW
            notes.append(f"Lookback {buf_len} is less than full window {self.config.full_warmup_bars}.")

        eligible = (
            quality_status == FeatureQualityStatus.PRISTINE
            and buf_len >= self.config.full_warmup_bars
            and not fallback_applied
        )

        return FeatureQualityMetadata(
            raw_feature_available=True,
            rolling_window_count=buf_len,
            zero_variance_detected=zero_var,
            missing_input_detected=missing_input,
            fallback_applied=fallback_applied,
            feature_quality_status=quality_status.value,
            eligible_for_prospective_scoring=eligible,
            quality_notes=notes,
        )


def import_numpy_std(vals: List[float]) -> float:
    import numpy as np
    if len(vals) > 1:
        return float(np.std(vals, ddof=1))
    return 0.0

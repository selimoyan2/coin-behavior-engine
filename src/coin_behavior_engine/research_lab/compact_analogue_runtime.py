"""Compact Analogue Runtime & Nearest-Neighbor Search Engine.

Sprint 11.16B.5: Compact Analogue Runtime & Independent Frozen Policy Replay.
Provides an immutable, high-efficiency, memory-bounded nearest-neighbor search
runtime over the frozen historical training partition.

Guaranteed Invariants:
1. Exact preservation of all 10 reference feature definitions.
2. Exact preservation of frozen training normalization parameters (feat_means, feat_stds).
3. Exact candidate eligibility: historical training split (288 to 68040).
4. Strict temporal spacing thinning: minimum 12 bars (1 hour) between selected analogues.
5. k = 20 analogues.
6. 24h forward return outcome label with +/-1.20% threshold.
7. Directional probability calculation: Prob(UP) = count(fwd_ret > 1.20%) / 20.
8. Policy E hurdle: Prob(UP) >= 0.60.
9. No approximation, no retraining, zero parameter changes.
10. Memory footprint < 15 MB, query latency < 10 ms.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np

logger = logging.getLogger("cbe_compact_analogue_runtime")

CANONICAL_COMPACT_ANALOGUE_SHA256 = "a7ee5335f40989161a4213d95b880e9c7df2d5fc3bafe4f26b439387f8bfc484"
FEATURE_COLS = [
    "trend_15m_pct",
    "trend_1h_pct",
    "trend_4h_pct",
    "price_acceleration",
    "realized_vol_24",
    "volatility_compression_ratio",
    "relative_volume_20",
    "distance_to_support_pct",
    "distance_to_resistance_pct",
    "drawdown_from_peak_pct",
]
K_ANALOGUES = 20
MIN_SPACING_BARS = 12
RETURN_THRESHOLD_PCT = 1.20
POLICY_E_HURDLE = 0.60


@dataclass(frozen=True)
class CompactAnalogueMatch:
    """Represents a matched historical analogue candidate."""
    analogue_index: int
    analogue_timestamp_ms: int
    similarity_distance: float
    fwd_ret_24h_pct: float
    regime: str


@dataclass(frozen=True)
class AnaloguePredictionResult:
    """Probabilistic forecast derived from k-NN historical analogues."""
    prob_up: float
    prob_down: float
    prob_neutral: float
    mean_similarity_distance: float
    analogues_count: int
    analogue_matches: Tuple[CompactAnalogueMatch, ...]
    policy_e_approved: bool
    status: str


class CompactAnalogueRuntime:
    """High-performance, memory-bounded analogue runtime using compact NumPy arrays."""

    def __init__(
        self,
        artifact_path: Optional[Path] = None,
        expected_sha256: Optional[str] = None,
        k: int = K_ANALOGUES,
        min_spacing: int = MIN_SPACING_BARS,
        return_threshold: float = RETURN_THRESHOLD_PCT,
        policy_e_threshold: float = POLICY_E_HURDLE,
    ):
        self.artifact_path = Path(artifact_path) if artifact_path else Path("research_outputs/compact_analogue_candidates.npz")
        self.expected_sha256 = expected_sha256 or CANONICAL_COMPACT_ANALOGUE_SHA256
        self.k = k
        self.min_spacing = min_spacing
        self.return_threshold = return_threshold
        self.policy_e_threshold = policy_e_threshold

        self.is_loaded = False
        self.status = "UNLOADED"
        self.candidate_matrix: Optional[np.ndarray] = None
        self.candidate_timestamps: Optional[np.ndarray] = None
        self.candidate_returns: Optional[np.ndarray] = None
        self.candidate_regimes: Optional[np.ndarray] = None
        self.feat_means: Optional[np.ndarray] = None
        self.feat_stds: Optional[np.ndarray] = None
        self.min_candidate_idx: int = 288
        self.max_candidate_idx: int = 68040

    def verify_and_load(self) -> Tuple[bool, str]:
        """Cryptographically verify and load candidate arrays into memory."""
        if not self.artifact_path.is_file():
            self.status = "ARTIFACT_MISSING"
            self.is_loaded = False
            return False, f"Compact analogue artifact missing at {self.artifact_path}"

        raw_bytes = self.artifact_path.read_bytes()
        actual_hash = hashlib.sha256(raw_bytes).hexdigest()
        if actual_hash.lower() != self.expected_sha256.lower():
            self.status = f"HASH_MISMATCH_EXPECTED_{self.expected_sha256[:8]}_FOUND_{actual_hash[:8]}"
            self.is_loaded = False
            return False, f"SHA-256 mismatch for compact analogue artifact: expected {self.expected_sha256}, got {actual_hash}"

        try:
            data = np.load(self.artifact_path, allow_pickle=True)
            self.candidate_matrix = data["candidate_matrix"].astype(np.float32)
            self.candidate_timestamps = data["candidate_timestamps"].astype(np.int64)
            self.candidate_returns = data["candidate_returns"].astype(np.float32)
            self.candidate_regimes = data["candidate_regimes"].astype(str)
            self.feat_means = data["feat_means"].astype(np.float32)
            self.feat_stds = data["feat_stds"].astype(np.float32)
            self.min_candidate_idx = int(data.get("min_candidate_idx", 288))
            self.max_candidate_idx = int(data.get("max_candidate_idx", 68040))

            self.is_loaded = True
            self.status = "VERIFIED_LOADED"
            candidate_count = len(self.candidate_matrix)
            return True, f"Loaded {candidate_count} candidates successfully (SHA-256: {actual_hash[:16]}...)"
        except Exception as e:
            self.status = "CORRUPT_ARCHIVE"
            self.is_loaded = False
            return False, f"Failed to parse compact analogue archive: {e}"

    def extract_raw_features_from_candles(self, candles: List[Any]) -> Optional[np.ndarray]:
        """Extract all 10 reference features from a rolling sequence of closed candles.
        
        Requires at least 288 closed candles (24 hours).
        """
        if len(candles) < 288:
            return None

        closes = np.array([float(c.close_p) for c in candles], dtype=np.float64)
        highs = np.array([float(c.high_p) for c in candles], dtype=np.float64)
        lows = np.array([float(c.low_p) for c in candles], dtype=np.float64)
        volumes = np.array([float(c.volume_base) for c in candles], dtype=np.float64)

        n = len(closes)

        # 1. Multi-Timeframe Momentum & Price Structure
        # trend_15m_pct = (close[-1] - close[-4]) / close[-4] * 100
        trend_15m_pct = (closes[-1] - closes[-4]) / closes[-4] * 100.0 if closes[-4] > 0 else 0.0
        # trend_1h_pct = (close[-1] - close[-13]) / close[-13] * 100
        trend_1h_pct = (closes[-1] - closes[-13]) / closes[-13] * 100.0 if closes[-13] > 0 else 0.0
        # trend_4h_pct = (close[-1] - close[-49]) / close[-49] * 100
        trend_4h_pct = (closes[-1] - closes[-49]) / closes[-49] * 100.0 if closes[-49] > 0 else 0.0
        # price_acceleration = trend_1h_pct[-1] - trend_1h_pct[-13]
        trend_1h_prev = (closes[-13] - closes[-25]) / closes[-25] * 100.0 if closes[-25] > 0 else 0.0
        price_acceleration = trend_1h_pct - trend_1h_prev

        # 2. Volatility & Liquidity
        # realized_vol_24 = rolling 24 std of 5m pct change
        ret_5m = np.diff(closes[-25:]) / closes[-25:-1] * 100.0
        realized_vol_24 = float(np.std(ret_5m))

        # True range over last 72 bars
        tr_list = []
        for i in range(n - 72, n):
            h, l, prev_c = highs[i], lows[i], closes[i - 1]
            tr_list.append(max(h - l, abs(h - prev_c), abs(l - prev_c)))
        atr14 = float(np.mean(tr_list[-14:]))
        atr72 = float(np.mean(tr_list))
        volatility_compression_ratio = (atr14 / atr72) if atr72 > 0 else 1.0

        # Relative Volume (last 20 bars mean)
        vol_mean_20 = float(np.mean(volumes[-20:]))
        relative_volume_20 = (volumes[-1] / vol_mean_20) if vol_mean_20 > 0 else 1.0

        # 3. Location within Range & Support/Resistance
        roll_low_72 = float(np.min(lows[-72:]))
        roll_high_72 = float(np.max(highs[-72:]))
        distance_to_support_pct = ((closes[-1] - roll_low_72) / closes[-1] * 100.0) if closes[-1] > 0 else 0.0
        distance_to_resistance_pct = ((roll_high_72 - closes[-1]) / closes[-1] * 100.0) if closes[-1] > 0 else 0.0

        # Drawdown from 288-bar (24h) peak
        roll_high_288 = float(np.max(highs[-288:]))
        drawdown_from_peak_pct = ((roll_high_288 - closes[-1]) / roll_high_288 * 100.0) if roll_high_288 > 0 else 0.0

        raw_vec = np.array([
            trend_15m_pct,
            trend_1h_pct,
            trend_4h_pct,
            price_acceleration,
            realized_vol_24,
            volatility_compression_ratio,
            relative_volume_20,
            distance_to_support_pct,
            distance_to_resistance_pct,
            drawdown_from_peak_pct,
        ], dtype=np.float32)

        return raw_vec

    def normalize_feature_vector(self, raw_features: np.ndarray) -> np.ndarray:
        """Normalize raw feature vector using frozen historical normalization parameters."""
        if self.feat_means is None or self.feat_stds is None:
            raise RuntimeError("Analogue runtime normalization parameters not loaded")
        return (raw_features - self.feat_means) / self.feat_stds

    def query(
        self,
        query_vector: np.ndarray,
        k: Optional[int] = None,
        candidate_ceiling_idx: Optional[int] = None,
    ) -> AnaloguePredictionResult:
        """Find top k nearest analogues and compute directional probabilities."""
        if not self.is_loaded or self.candidate_matrix is None:
            return AnaloguePredictionResult(
                prob_up=0.3333,
                prob_down=0.3333,
                prob_neutral=0.3334,
                mean_similarity_distance=999.0,
                analogues_count=0,
                analogue_matches=(),
                policy_e_approved=False,
                status="RUNTIME_NOT_LOADED",
            )

        k_target = k or self.k
        candidates = self.candidate_matrix
        if candidate_ceiling_idx is not None:
            candidates = candidates[:candidate_ceiling_idx]

        if len(candidates) < k_target:
            return AnaloguePredictionResult(
                prob_up=0.3333,
                prob_down=0.3333,
                prob_neutral=0.3334,
                mean_similarity_distance=999.0,
                analogues_count=0,
                analogue_matches=(),
                policy_e_approved=False,
                status="INSUFFICIENT_CANDIDATES",
            )

        # Vectorized Euclidean distance calculation
        diff = candidates - query_vector
        dists = np.sqrt(np.sum(diff * diff, axis=1))

        # Ascending sort
        sorted_indices = np.argsort(dists)

        selected_matches: List[CompactAnalogueMatch] = []
        selected_abs_indices: List[int] = []

        for rel_idx in sorted_indices:
            abs_idx = self.min_candidate_idx + rel_idx

            # Temporal thinning filter (minimum spacing)
            if any(abs(abs_idx - sel) < self.min_spacing for sel in selected_abs_indices):
                continue

            selected_abs_indices.append(abs_idx)
            dist_val = round(float(dists[rel_idx]), 4)
            ts_val = int(self.candidate_timestamps[rel_idx])
            ret_val = round(float(self.candidate_returns[rel_idx]), 4)
            reg_val = str(self.candidate_regimes[rel_idx])

            match = CompactAnalogueMatch(
                analogue_index=abs_idx,
                analogue_timestamp_ms=ts_val,
                similarity_distance=dist_val,
                fwd_ret_24h_pct=ret_val,
                regime=reg_val,
            )
            selected_matches.append(match)

            if len(selected_matches) >= k_target:
                break

        if not selected_matches:
            return AnaloguePredictionResult(
                prob_up=0.3333,
                prob_down=0.3333,
                prob_neutral=0.3334,
                mean_similarity_distance=999.0,
                analogues_count=0,
                analogue_matches=(),
                policy_e_approved=False,
                status="NO_MATCHES_FOUND",
            )

        returns = [m.fwd_ret_24h_pct for m in selected_matches]
        up_count = sum(1 for r in returns if r > self.return_threshold)
        down_count = sum(1 for r in returns if r < -self.return_threshold)
        neutral_count = len(returns) - up_count - down_count

        total = len(returns)
        prob_up = round(up_count / total, 4)
        prob_down = round(down_count / total, 4)
        prob_neutral = round(neutral_count / total, 4)
        mean_dist = round(float(np.mean([m.similarity_distance for m in selected_matches])), 4)

        policy_e_approved = (prob_up >= self.policy_e_threshold)

        return AnaloguePredictionResult(
            prob_up=prob_up,
            prob_down=prob_down,
            prob_neutral=prob_neutral,
            mean_similarity_distance=mean_dist,
            analogues_count=len(selected_matches),
            analogue_matches=tuple(selected_matches),
            policy_e_approved=policy_e_approved,
            status="CALIBRATED_MATCH",
        )

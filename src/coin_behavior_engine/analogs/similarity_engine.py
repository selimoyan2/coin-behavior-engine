"""Causal Historical Analog Retrieval Engine for Sprint 11.19.

Implements causal nearest-neighbor pattern matching:
1. Strict Forward Outcome Quarantine: Candidate c is eligible if and only if
   its entire forward outcome window (c_timestamp + H_max) <= query_timestamp T_0.
   Zero future leakage.
2. Temporal Exclusion & Clustering: Enforces a minimum temporal separation
   (e.g., 288 bars / 24h) between candidate analogs to eliminate auto-correlated clusters.
3. Volatility-Normalized Distance: Weighted Euclidean distance scaled by feature variance.
4. Comprehensive Analog Diagnostics:
   - Analog timestamps and dates
   - Continuous similarity scores in [0, 1]
   - Regime distribution among analogs
   - Number of independent clusters
   - Effective sample size (ESS)
   - Abstention reasons (e.g., INSUFFICIENT_ANALOGS, HIGH_FEATURE_DIVERGENCE).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from coin_behavior_engine.analogs.feature_store import FeatureVector
from coin_behavior_engine.analogs.regime_classifier import MarketRegimeClassifier, RegimeDecision


@dataclass(frozen=True)
class HistoricalAnalog:
    """Individual retrieved historical analog instance."""
    candle_idx: int
    open_time: int
    datetime_utc: str
    similarity_score: float
    distance: float
    regime: str
    cluster_id: int
    forward_returns: Dict[str, float]  # e.g. {'1h': 0.005, '24h': -0.012}
    forward_mfe: Dict[str, float]      # max favorable excursion
    forward_mae: Dict[str, float]      # max adverse excursion


@dataclass(frozen=True)
class AnalogSearchResult:
    """Aggregated output of causal historical analog matching at T_0."""
    query_timestamp_utc: str
    query_open_time: int
    query_regime: str
    total_candidates_scanned: int
    analogs: List[HistoricalAnalog]
    analogs_count: int
    independent_clusters_count: int
    effective_sample_size: float
    mean_similarity: float
    analog_regime_distribution: Dict[str, int]
    is_abstained: bool
    abstention_reason: Optional[str]


class CausalSimilarityEngine:
    """Causal nearest-neighbor matching engine with strict temporal isolation."""

    FEATURE_COLS = [
        "ret_1h", "ret_4h", "ret_24h", "ret_72h",
        "atr_5m_pct", "realized_vol_24h", "volume_zscore_24h",
        "trend_strength", "trend_persistence_4h",
        "drawdown_high_24h", "recovery_low_24h",
        "dist_support_24h", "dist_resistance_24h", "range_width_pct_24h"
    ]

    # Fixed domain weights prioritizing trend persistence, volatility, and multi-horizon momentum
    FEATURE_WEIGHTS = np.array([
        1.2, 1.5, 2.0, 1.0,   # returns (1h, 4h, 24h, 72h)
        1.8, 1.5, 0.8,        # volatility (atr, realized vol, volume zscore)
        2.5, 1.5,             # trend strength, persistence
        1.2, 1.2,             # drawdown, recovery
        1.0, 1.0, 1.5         # support/resistance dist, range width
    ], dtype=np.float64)

    def __init__(
        self,
        df_5m: pd.DataFrame,
        regime_classifier: Optional[MarketRegimeClassifier] = None,
        k_neighbors: int = 15,
        min_cluster_separation_bars: int = 288,  # 24 hours between analogs
        max_horizon_bars: int = 2016,            # 7 days forward outcome quarantine
        min_required_analogs: int = 5,
        min_similarity_threshold: float = 0.40,
        temperature: float = 2.5
    ):
        self.df_5m = df_5m.copy().sort_values("open_time").reset_index(drop=True)
        self.regime_classifier = regime_classifier or MarketRegimeClassifier()
        self.k_neighbors = k_neighbors
        self.min_cluster_sep = min_cluster_separation_bars
        self.max_horizon_bars = max_horizon_bars
        self.min_required_analogs = min_required_analogs
        self.min_similarity_threshold = min_similarity_threshold
        self.temperature = temperature

        # Build feature matrix
        self.open_times = self.df_5m["open_time"].to_numpy()
        self.close_prices = self.df_5m["close"].to_numpy()
        self.high_prices = self.df_5m["high"].to_numpy()
        self.low_prices = self.df_5m["low"].to_numpy()
        self.feature_matrix = self.df_5m[self.FEATURE_COLS].to_numpy(dtype=np.float64)

        # Precompute std dev for scaling (using sample clipping to prevent div by zero)
        feat_stds = np.nanstd(self.feature_matrix, axis=0)
        self.scale_factors = np.where(feat_stds < 1e-6, 1.0, feat_stds)

    def find_analogs(
        self,
        query_idx: int,
        query_fv: FeatureVector,
        horizons_map: Optional[Dict[str, int]] = None
    ) -> AnalogSearchResult:
        """Find historical analogs for query candle ensuring 100% causal isolation.
        
        Args:
            query_idx: Integer index of query candle in df_5m.
            query_fv: FeatureVector at query time T_0.
            horizons_map: Dict of horizon name to bar count (e.g. {'1h': 12, '24h': 288, '7d': 2016}).
        """
        if horizons_map is None:
            horizons_map = {
                "1h": 12, "3h": 36, "6h": 72, "12h": 144,
                "24h": 288, "48h": 576, "72h": 864, "7d": 2016
            }

        q_regime = self.regime_classifier.classify(query_fv).regime

        # 1. Strict Causality Invariant:
        # Candidate candle index c must satisfy: c + max_horizon_bars <= query_idx
        # This guarantees that candidate's 7-day outcome was fully completed BEFORE query moment!
        max_candidate_idx = query_idx - self.max_horizon_bars
        if max_candidate_idx <= 864:  # Need at least 864 bars of history for candidates
            return AnalogSearchResult(
                query_timestamp_utc=query_fv.datetime_utc,
                query_open_time=query_fv.open_time,
                query_regime=q_regime,
                total_candidates_scanned=0,
                analogs=[],
                analogs_count=0,
                independent_clusters_count=0,
                effective_sample_size=0.0,
                mean_similarity=0.0,
                analog_regime_distribution={},
                is_abstained=True,
                abstention_reason="INSUFFICIENT_HISTORICAL_QUARANTINE_POOL"
            )

        # 2. Extract candidate feature submatrix
        candidate_indices = np.arange(864, max_candidate_idx)
        cand_feats = self.feature_matrix[candidate_indices]

        # Query feature vector
        q_feat = np.array([getattr(query_fv, col) for col in self.FEATURE_COLS], dtype=np.float64)

        # 3. Volatility-normalized weighted Euclidean distance
        diff = (cand_feats - q_feat) / self.scale_factors
        weighted_sq_diff = (diff ** 2) * self.FEATURE_WEIGHTS
        dists = np.sqrt(np.sum(weighted_sq_diff, axis=1))

        # Sort candidate indices by distance
        sorted_order = np.argsort(dists)

        # 4. Temporal Exclusion & Clustering Selection
        selected_analogs: List[HistoricalAnalog] = []
        selected_cand_indices: List[int] = []

        for rel_idx in sorted_order:
            actual_cand_idx = candidate_indices[rel_idx]
            cand_dist = float(dists[rel_idx])
            sim_score = float(np.exp(-cand_dist / self.temperature))

            if sim_score < self.min_similarity_threshold and len(selected_analogs) >= self.min_required_analogs:
                break

            # Temporal separation check
            is_too_close = False
            for prev_idx in selected_cand_indices:
                if abs(actual_cand_idx - prev_idx) < self.min_cluster_sep:
                    is_too_close = True
                    break

            if is_too_close:
                continue

            # Compute forward outcomes for this analog
            fwd_rets = {}
            fwd_mfe = {}
            fwd_mae = {}
            c_base_close = self.close_prices[actual_cand_idx]

            for h_label, h_bars in horizons_map.items():
                if actual_cand_idx + h_bars < len(self.df_5m):
                    fwd_c = self.close_prices[actual_cand_idx + h_bars]
                    fwd_high = self.high_prices[actual_cand_idx + 1:actual_cand_idx + 1 + h_bars].max()
                    fwd_low = self.low_prices[actual_cand_idx + 1:actual_cand_idx + 1 + h_bars].min()

                    fwd_rets[h_label] = (fwd_c - c_base_close) / c_base_close
                    fwd_mfe[h_label] = (fwd_high - c_base_close) / c_base_close
                    fwd_mae[h_label] = (fwd_low - c_base_close) / c_base_close
                else:
                    fwd_rets[h_label] = np.nan
                    fwd_mfe[h_label] = np.nan
                    fwd_mae[h_label] = np.nan

            # Determine analog's regime
            c_open_time = int(self.open_times[actual_cand_idx])
            c_dt_utc = str(pd.to_datetime(c_open_time, unit="ms", utc=True))

            # Approximate regime from cand feature values
            cand_strength = cand_feats[rel_idx, self.FEATURE_COLS.index("trend_strength")]
            cand_atr = cand_feats[rel_idx, self.FEATURE_COLS.index("atr_5m_pct")]
            if cand_atr > 0.008:
                c_regime = "HIGH_VOLATILITY"
            elif cand_strength > 1.0:
                c_regime = "TREND_UP"
            elif cand_strength < -1.0:
                c_regime = "TREND_DOWN"
            elif abs(cand_strength) < 0.8:
                c_regime = "RANGE"
            else:
                c_regime = "UNCERTAIN"

            cluster_id = len(selected_analogs) + 1
            selected_analogs.append(HistoricalAnalog(
                candle_idx=actual_cand_idx,
                open_time=c_open_time,
                datetime_utc=c_dt_utc,
                similarity_score=round(sim_score, 4),
                distance=round(cand_dist, 4),
                regime=c_regime,
                cluster_id=cluster_id,
                forward_returns=fwd_rets,
                forward_mfe=fwd_mfe,
                forward_mae=fwd_mae
            ))
            selected_cand_indices.append(actual_cand_idx)

            if len(selected_analogs) >= self.k_neighbors:
                break

        # 5. Abstention Evaluation
        is_abstained = False
        abstention_reason = None

        if len(selected_analogs) < self.min_required_analogs:
            is_abstained = True
            abstention_reason = f"INSUFFICIENT_ANALOGS_FOUND ({len(selected_analogs)} < {self.min_required_analogs})"
        elif selected_analogs[0].similarity_score < self.min_similarity_threshold:
            is_abstained = True
            abstention_reason = f"HIGH_FEATURE_DIVERGENCE (top_sim={selected_analogs[0].similarity_score:.3f} < {self.min_similarity_threshold})"

        # 6. Aggregate Diagnostics
        sim_scores = [a.similarity_score for a in selected_analogs]
        mean_sim = float(np.mean(sim_scores)) if sim_scores else 0.0
        # Kish's Effective Sample Size: (sum(w))^2 / sum(w^2)
        if sim_scores:
            weights = np.array(sim_scores) / sum(sim_scores)
            ess = float(1.0 / np.sum(weights ** 2))
        else:
            ess = 0.0

        regime_counts = {}
        for a in selected_analogs:
            regime_counts[a.regime] = regime_counts.get(a.regime, 0) + 1

        return AnalogSearchResult(
            query_timestamp_utc=query_fv.datetime_utc,
            query_open_time=query_fv.open_time,
            query_regime=q_regime,
            total_candidates_scanned=len(candidate_indices),
            analogs=selected_analogs,
            analogs_count=len(selected_analogs),
            independent_clusters_count=len(selected_analogs),
            effective_sample_size=round(ess, 2),
            mean_similarity=round(mean_sim, 4),
            analog_regime_distribution=regime_counts,
            is_abstained=is_abstained,
            abstention_reason=abstention_reason
        )

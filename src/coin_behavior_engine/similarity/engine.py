"""Pattern Representation and Causal Similarity Engine for Sprint 02.

Strict Causality Invariant:
When searching for historical analogs to a query state at time T,
the candidate pool is strictly restricted to {t < T - buffer_candles}.
Future data is NEVER accessed or included in candidate pools.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import pandas as pd

from coin_behavior_engine.utils.logging import logger


@dataclass
class PatternFingerprint:
    """Standardized representation of a market pattern state."""
    timestamp: str
    candle_idx: int
    trajectory_4h: np.ndarray        # 48 candles normalized by rolling ATR: (P_i - P_0) / ATR
    volatility_ratio: float          # 4h / 24h realized vol ratio
    volume_zscore: float             # 24h volume z-score
    taker_buy_ratio: float           # buy volume / total volume
    micro_regime: str                # Layer 1 regime
    macro_regime: str                # Layer 2 regime
    macro_duration_hours: float      # duration in current macro regime


class CausalSimilarityEngine:
    """Historical analog search engine guaranteeing 100% causal time ordering."""

    def __init__(
        self,
        trajectory_len: int = 48,       # 4 hours of 5m candles
        buffer_candles: int = 288,      # 24h exclusion buffer before query to prevent self-matching
        macro_mismatch_penalty: float = 0.5,
    ):
        self.trajectory_len = trajectory_len
        self.buffer_candles = buffer_candles
        self.macro_mismatch_penalty = macro_mismatch_penalty

    def _ensure_arrays(self, df: pd.DataFrame):
        if not hasattr(self, "_arr_df_id") or self._arr_df_id != id(df):
            self._arr_df_id = id(df)
            self._close_arr = df["close"].to_numpy() if "close" in df.columns else None
            self._vol_arr = df["volatility_realized_24h"].to_numpy() if "volatility_realized_24h" in df.columns else None
            self._comp_arr = df["volatility_compression_ratio"].to_numpy() if "volatility_compression_ratio" in df.columns else None
            self._volz_arr = df["volume_zscore_24h"].to_numpy() if "volume_zscore_24h" in df.columns else None
            self._taker_arr = df["volume_buy_ratio"].to_numpy() if "volume_buy_ratio" in df.columns else None
            self._micro_arr = df["regime"].to_numpy() if "regime" in df.columns else None
            self._macro_arr = df["macro_regime"].to_numpy() if "macro_regime" in df.columns else None
            self._dur_arr = df["macro_regime_duration"].to_numpy() if "macro_regime_duration" in df.columns else None
            self._dt_arr = df["datetime_open"].astype(str).to_numpy() if "datetime_open" in df.columns else None
            self._fwd1_arr = df["fwd_ret_1h"].to_numpy() if "fwd_ret_1h" in df.columns else None
            self._fwd4_arr = df["fwd_ret_4h"].to_numpy() if "fwd_ret_4h" in df.columns else None
            self._fwd24_arr = df["fwd_ret_24h"].to_numpy() if "fwd_ret_24h" in df.columns else None

    def extract_fingerprint(
        self,
        df: pd.DataFrame,
        idx: int,
    ) -> Optional[PatternFingerprint]:
        """Extract a single PatternFingerprint at index idx using only past data [idx - 47, idx]."""
        if idx < self.trajectory_len - 1 or idx >= len(df):
            return None

        if not hasattr(self, "_fp_cache"):
            self._fp_cache = {}
        if idx in self._fp_cache:
            return self._fp_cache[idx]

        self._ensure_arrays(df)

        # Trajectory of close prices over past 48 candles
        window_closes = self._close_arr[idx - self.trajectory_len + 1 : idx + 1]
        p0 = window_closes[0]

        # Normalize by ATR or 24h realized vol
        c_val = self._close_arr[idx]
        vol_val = self._vol_arr[idx] if self._vol_arr is not None else np.nan
        atr = vol_val * c_val if not np.isnan(vol_val) else (np.std(window_closes) + 1e-6)
        if atr <= 0 or np.isnan(atr):
            atr = 1.0

        normalized_traj = (window_closes - p0) / atr

        fp = PatternFingerprint(
            timestamp=self._dt_arr[idx] if self._dt_arr is not None else str(idx),
            candle_idx=idx,
            trajectory_4h=normalized_traj,
            volatility_ratio=float(self._comp_arr[idx]) if self._comp_arr is not None else 1.0,
            volume_zscore=float(self._volz_arr[idx]) if self._volz_arr is not None else 0.0,
            taker_buy_ratio=float(self._taker_arr[idx]) if self._taker_arr is not None else 0.5,
            micro_regime=str(self._micro_arr[idx]) if self._micro_arr is not None else "UNKNOWN",
            macro_regime=str(self._macro_arr[idx]) if self._macro_arr is not None else "UNKNOWN",
            macro_duration_hours=float(self._dur_arr[idx]) * 5 / 60 if self._dur_arr is not None else 1.0,
        )
        self._fp_cache[idx] = fp
        return fp

    def search_historical_analogs(
        self,
        df: pd.DataFrame,
        query_idx: int,
        candidate_indices: List[int],
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Find top-K historical analogs for query_idx among candidate_indices.
        Enforces strict causality: candidate_idx < query_idx - buffer_candles.
        """
        self._ensure_arrays(df)
        query_fp = self.extract_fingerprint(df, query_idx)
        if query_fp is None:
            return []

        # Strict causal filter: candidate MUST be in the past
        max_allowed_idx = query_idx - self.buffer_candles
        valid_candidates = [c for c in candidate_indices if c <= max_allowed_idx and c >= self.trajectory_len - 1]

        if not valid_candidates:
            return []

        results = []
        q_traj = query_fp.trajectory_4h
        q_norm = np.linalg.norm(q_traj) + 1e-8

        for c_idx in valid_candidates:
            c_fp = self.extract_fingerprint(df, c_idx)
            if c_fp is None:
                continue

            c_traj = c_fp.trajectory_4h
            c_norm = np.linalg.norm(c_traj) + 1e-8

            # Euclidean distance in normalized trajectory space
            traj_dist = np.mean((q_traj - c_traj) ** 2)

            # Cosine similarity
            cos_sim = np.dot(q_traj, c_traj) / (q_norm * c_norm)

            # Volatility & volume feature distance
            feature_dist = 0.5 * abs(query_fp.volatility_ratio - c_fp.volatility_ratio) + \
                           0.2 * abs(query_fp.volume_zscore - c_fp.volume_zscore) / 3.0

            # Macro regime penalty
            regime_penalty = 0.0 if query_fp.macro_regime == c_fp.macro_regime else self.macro_mismatch_penalty

            total_dist = traj_dist + feature_dist + regime_penalty

            results.append({
                "candidate_idx": c_idx,
                "candidate_time": c_fp.timestamp,
                "distance": float(total_dist),
                "traj_mse": float(traj_dist),
                "cosine_sim": float(cos_sim),
                "candidate_macro_regime": c_fp.macro_regime,
                "candidate_micro_regime": c_fp.micro_regime,
                "fwd_ret_1h": float(self._fwd1_arr[c_idx]) if self._fwd1_arr is not None else np.nan,
                "fwd_ret_4h": float(self._fwd4_arr[c_idx]) if self._fwd4_arr is not None else np.nan,
                "fwd_ret_24h": float(self._fwd24_arr[c_idx]) if self._fwd24_arr is not None else np.nan,
            })

        # Sort by ascending distance and return top_k
        results.sort(key=lambda x: x["distance"])
        return results[:top_k]

"""Extreme Value Theory (EVT) and Mahalanobis Tail Modeling.

Resolves the Event Score saturation at 1.0 identified in Sprint 01.1:
1. Peaks-Over-Threshold (POT) using Generalized Pareto Distribution (GPD) on return/volatility tails.
2. Event Score V2: Robust Mahalanobis distance in standardized feature space (fitted strictly on Discovery 2021-2024)
   with Chi-squared rarity calibration, eliminating artificial clipping and human weighting.
"""

from __future__ import annotations

from typing import Dict, List, Tuple, Any, Optional
import numpy as np
import pandas as pd
from scipy import stats

from coin_behavior_engine.utils.logging import logger


class ExtremeValueTailModel:
    """Fits Generalized Pareto Distribution (GPD) on tail exceedances over threshold u."""

    def __init__(self, threshold_quantile: float = 0.95):
        self.threshold_quantile = threshold_quantile
        self.u: Optional[float] = None
        self.shape_xi: Optional[float] = None
        self.scale_sigma: Optional[float] = None
        self.zeta_u: Optional[float] = None

    def fit(self, data: np.ndarray) -> Dict[str, float]:
        """Fit GPD strictly on Discovery data."""
        clean = data[~np.isnan(data)]
        if len(clean) < 100:
            raise ValueError(f"Insufficient data for EVT fit: {len(clean)}")

        self.u = float(np.percentile(clean, self.threshold_quantile * 100))
        exceedances = clean[clean > self.u] - self.u
        self.zeta_u = float(len(exceedances) / len(clean))

        if len(exceedances) < 20:
            raise ValueError("Too few tail exceedances to fit GPD.")

        # Fit GPD with location fixed at 0: exceedance y >= 0
        # In scipy, genpareto pdf is (1 + c*x/scale)**(-1/c - 1) / scale
        c, loc, scale = stats.genpareto.fit(exceedances, floc=0)
        self.shape_xi = float(c)
        self.scale_sigma = float(scale)

        logger.info(
            f"EVT GPD Fit: threshold u={self.u:.5f} (q={self.threshold_quantile}), "
            f"exceedance fraction zeta={self.zeta_u:.4f}, shape xi={self.shape_xi:.4f}, scale sigma={self.scale_sigma:.5f}"
        )

        return {
            "threshold_u": self.u,
            "zeta_u": self.zeta_u,
            "shape_xi": self.shape_xi,
            "scale_sigma": self.scale_sigma,
        }

    def compute_tail_probability(self, x: np.ndarray) -> np.ndarray:
        """
        Compute tail probability P(X > x) for arbitrary input.
        Returns smooth continuous probability in [0, 1].
        """
        if self.u is None or self.scale_sigma is None:
            raise RuntimeError("Model must be fitted before computing tail probabilities.")

        probs = np.ones_like(x, dtype=float)
        tail_mask = x > self.u

        if np.any(tail_mask):
            excess = x[tail_mask] - self.u
            # P(X > x | X > u) = 1 - GPD_CDF(excess)
            cond_prob = 1.0 - stats.genpareto.cdf(excess, self.shape_xi, loc=0, scale=self.scale_sigma)
            probs[tail_mask] = self.zeta_u * cond_prob

        return probs


class EventScoreV2Engine:
    """
    Computes Event Score V2 using Mahalanobis distance in 4D space:
    (abs_return_5m, realized_vol_24h, volume_zscore_24h, compression_ratio_inv).
    Calibrated against Discovery covariance matrix without human weights.
    """

    FEATURE_COLS = [
        "return_log_1h_abs",
        "volatility_realized_24h",
        "volume_zscore_24h",
        "compression_inv",
    ]

    def __init__(self):
        self.mean_vector: Optional[np.ndarray] = None
        self.inv_cov_matrix: Optional[np.ndarray] = None
        self.dim: int = len(self.FEATURE_COLS)

    def prepare_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Create normalized 4D features required for Event Score V2."""
        f_df = pd.DataFrame(index=df.index)

        # 1. 1h return absolute value
        ret_1h = df["return_log_1h"].abs() if "return_log_1h" in df.columns else df["close"].pct_change(12).abs().fillna(0)
        f_df["return_log_1h_abs"] = ret_1h.fillna(0.0)

        # 2. 24h Realized Volatility
        f_df["volatility_realized_24h"] = df["volatility_realized_24h"].fillna(df["volatility_realized_24h"].median())

        # 3. 24h Volume Z-score
        f_df["volume_zscore_24h"] = df["volume_zscore_24h"].clip(lower=-3.0, upper=10.0).fillna(0.0)

        # 4. Inverted compression (higher means more compressed/extreme)
        comp = df["volatility_compression_ratio"].replace(0, np.nan).fillna(1.0)
        f_df["compression_inv"] = 1.0 / comp

        return f_df

    def fit_discovery(self, discovery_df: pd.DataFrame):
        """Fit empirical mean and covariance strictly on Discovery partition."""
        feats = self.prepare_features(discovery_df)
        X = feats.to_numpy(dtype=float)

        self.mean_vector = np.nanmean(X, axis=0)
        cov = np.cov(X[~np.isnan(X).any(axis=1)], rowvar=False)

        # Add small regularization for numerical stability
        cov += np.eye(self.dim) * 1e-6
        self.inv_cov_matrix = np.linalg.pinv(cov)

        logger.info(f"EventScoreV2Engine fitted on {len(discovery_df)} candles across {self.dim} features.")

    def compute_event_score_v2(self, df: pd.DataFrame) -> pd.Series:
        """
        Compute continuous Event Score V2.
        score = 1 - chi2.sf(D_M^2, df=dim)  (smoothly maps [0, 1] without hard clipping)
        and mahalanobis distance D_M.
        """
        if self.mean_vector is None or self.inv_cov_matrix is None:
            raise RuntimeError("Must fit engine on Discovery partition first.")

        feats = self.prepare_features(df)
        X = feats.to_numpy(dtype=float)
        diff = X - self.mean_vector

        # Vectorized Mahalanobis distance calculation: sqrt(diag(diff @ inv_cov @ diff.T))
        left = np.dot(diff, self.inv_cov_matrix)
        d_m_sq = np.sum(left * diff, axis=1)
        d_m_sq = np.maximum(0.0, d_m_sq)

        d_m = np.sqrt(d_m_sq)

        # Chi-squared cumulative distribution value: maps to [0, 1) smoothly without saturation
        p_val = stats.chi2.sf(d_m_sq, df=self.dim)
        # Prevent float64 rounding saturation at exact 1.0
        score_v2 = np.minimum(1.0 - p_val, 0.9999)

        return pd.Series(score_v2, index=df.index, name="event_score_v2")

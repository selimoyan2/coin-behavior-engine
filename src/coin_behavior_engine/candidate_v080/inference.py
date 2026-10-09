"""CBE-0.8.0 Pure Numerical Inference Engine.

Zero-dependency (sklearn-free) inference implementation executing deterministic Ridge predictions
directly from a validated ModelBundleV080.
Enforces strict fail-closed validation on missing features, wrong dimensions, and non-finite values.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import numpy as np
import pandas as pd

from coin_behavior_engine.candidate_v080.bundle import ModelBundleV080, BundleIntegrityError


class FeatureValidationError(Exception):
    """Raised when input feature dictionary violates schema, is missing keys, or contains non-finite values."""
    pass


class CandidateInferenceEngineV080:
    """Production candidate inference engine for CBE-0.8.0 SPOT_ONLY_U0 tier."""

    def __init__(self, bundle: Union[ModelBundleV080, Path, str], lockbox_path: Optional[Path] = None):
        if isinstance(bundle, (str, Path)):
            self.bundle = ModelBundleV080.load(Path(bundle), lockbox_path=lockbox_path)
        elif isinstance(bundle, ModelBundleV080):
            self.bundle = bundle
        else:
            raise TypeError(f"Expected ModelBundleV080 or Path, got {type(bundle)}")

        self.ordered_features = self.bundle.feature_manifest.get("ordered_features", [])
        if not self.ordered_features:
            raise BundleIntegrityError("Ordered features list is missing from bundle")

        if self.bundle.scaler is None:
            raise BundleIntegrityError("Bundle does not contain scaler parameters")

        self.scaler_mean = np.array(self.bundle.scaler.mean_, dtype=np.float64)
        self.scaler_scale = np.array(self.bundle.scaler.scale_, dtype=np.float64)
        self.clip_min = float(self.bundle.preprocessing_rules.get("feature_clip_min", -1e4))
        self.clip_max = float(self.bundle.preprocessing_rules.get("feature_clip_max", 1e4))
        self.sqrt_288 = math.sqrt(288.0)

        # Precompute weights & intercepts per horizon
        self._weights: Dict[str, np.ndarray] = {}
        self._intercepts: Dict[str, float] = {}
        for h, m in self.bundle.models.items():
            self._weights[h] = np.array(m.coefficients, dtype=np.float64)
            self._intercepts[h] = float(m.intercept)

    def validate_features_dict(self, features: Dict[str, Any]) -> np.ndarray:
        """Validate feature dictionary and return ordered numpy array. Fails closed on any defect."""
        if not isinstance(features, dict):
            raise FeatureValidationError(f"Expected dict of features, got {type(features)}")

        values = []
        for name in self.ordered_features:
            if name not in features:
                raise FeatureValidationError(
                    f"Missing required feature: '{name}'. Required features: {self.ordered_features}"
                )
            val = features[name]
            if val is None:
                raise FeatureValidationError(f"Feature '{name}' has None value")
            try:
                f_val = float(val)
            except (ValueError, TypeError):
                raise FeatureValidationError(f"Feature '{name}' cannot be converted to float: {val}")

            if math.isnan(f_val) or math.isinf(f_val):
                raise FeatureValidationError(f"Feature '{name}' is non-finite: {f_val}")

            values.append(f_val)

        return np.array(values, dtype=np.float64)

    def predict(self, features: Dict[str, Any], horizon: str) -> float:
        """Compute forecast for horizon (1h, 4h, 24h).
        Returns daily-scaled forward realized volatility (sigma_5m * sqrt(288)).
        """
        if horizon not in self._weights:
            raise ValueError(f"Unknown horizon '{horizon}'. Available: {list(self._weights.keys())}")

        x = self.validate_features_dict(features)

        # Preprocessing: clipping
        x_clipped = np.clip(x, self.clip_min, self.clip_max)

        # Standardize: (x - mean) / scale
        x_scaled = (x_clipped - self.scaler_mean) / self.scaler_scale

        # Ridge inference: x_scaled @ weights + intercept
        pred = float(np.dot(x_scaled, self._weights[horizon]) + self._intercepts[horizon])

        # Floor at 0.0 (volatility cannot be negative)
        return max(0.0, pred)

    def predict_unscaled_5m(self, features: Dict[str, Any], horizon: str) -> float:
        """Compute forecast in raw 5-minute standard deviation units (sigma_5m)."""
        daily_vol = self.predict(features, horizon)
        return daily_vol / self.sqrt_288

    def predict_batch(self, df: pd.DataFrame, horizon: str) -> np.ndarray:
        """Vectorized batch prediction over a dataframe for evaluation."""
        if horizon not in self._weights:
            raise ValueError(f"Unknown horizon '{horizon}'")

        # Verify columns exist
        missing = [c for c in self.ordered_features if c not in df.columns]
        if missing:
            raise FeatureValidationError(f"Missing columns in dataframe: {missing}")

        X = df[self.ordered_features].values.astype(np.float64)
        if np.isnan(X).any() or np.isinf(X).any():
            raise FeatureValidationError("Dataframe contains NaN or Inf in feature columns")

        X_clipped = np.clip(X, self.clip_min, self.clip_max)
        X_scaled = (X_clipped - self.scaler_mean) / self.scaler_scale
        preds = np.dot(X_scaled, self._weights[horizon]) + self._intercepts[horizon]
        return np.maximum(0.0, preds)

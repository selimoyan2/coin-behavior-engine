"""Feature extraction pipeline coordinating all feature modules."""

from __future__ import annotations

from typing import Dict, Optional
import pandas as pd

from coin_behavior_engine.config.schema import ResearchConfig
from coin_behavior_engine.features.adaptive import compute_adaptive_features
from coin_behavior_engine.features.distribution import compute_distribution_features
from coin_behavior_engine.features.returns import compute_displacement_and_drawdown, compute_returns
from coin_behavior_engine.features.volatility import compute_volatility_features
from coin_behavior_engine.features.volume import compute_volume_features
from coin_behavior_engine.utils.logging import logger


class FeaturePipeline:
    """Builds comprehensive, neutral statistical features without look-ahead bias."""

    def __init__(self, config: Optional[ResearchConfig] = None):
        self.config = config or ResearchConfig()
        # Window mappings
        w = self.config.features.windows
        self.windows = {
            "short": w.short,
            "medium": w.medium,
            "long": w.long,
            "baseline": w.baseline,
            "extended": w.extended,
        }
        self.dist_window = self.config.features.adaptive_normalization.rolling_distribution_window
        self.mad_mult = self.config.features.adaptive_normalization.mad_multiplier

    def compute_all_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Extract all neutral statistical and adaptive features for a candle dataframe.
        Guarantees that no future data is accessed.
        """
        logger.info(f"Computing feature pipeline on {len(df)} candles...")

        # 1. Base returns
        ret_df = compute_returns(df)

        # 2. Price displacements and drawdowns
        disp_df = compute_displacement_and_drawdown(df, self.windows)

        # 3. Volatility metrics
        vol_df = compute_volatility_features(df, self.windows)

        # 4. Volume metrics
        vlm_df = compute_volume_features(df, self.windows)

        # 5. Distributional & robust stats
        dist_df = compute_distribution_features(df, self.windows, self.mad_mult)

        # Partial intermediate dataframe for adaptive rank inputs
        interim = pd.concat([df, ret_df, vol_df, vlm_df], axis=1)

        # 6. Adaptive empirical percentile ranks
        adapt_df = compute_adaptive_features(df, interim, self.dist_window)

        # Combine all features into canonical output
        features = pd.concat([df, ret_df, disp_df, vol_df, vlm_df, dist_df, adapt_df], axis=1)

        # Remove duplicate column names if any
        features = features.loc[:, ~features.columns.duplicated()]

        logger.info(f"Feature extraction complete. Generated {features.shape[1]} columns.")
        return features

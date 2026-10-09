"""CBE-0.8.0 Market State Classifier & Taxonomy Engine.

Resolves Failure A (Market-State Collapse to DELEVERAGING_STRESS).
Enforces:
1. Fixed historical reference thresholds learned strictly on Discovery (< 2025-01-01).
2. Zero dynamic percentile evaluation on single input rows.
3. Mutually exclusive primary state (LOW_VOLATILITY, NORMAL_VOLATILITY, HIGH_VOLATILITY)
   plus independent secondary flags (VOLATILITY_COMPRESSION, VOLATILITY_EXPANSION).
4. Strictly refuses to emit DELEVERAGING_STRESS in SPOT_ONLY_U0 tier.
5. Fails closed with UNKNOWN_INSUFFICIENT_DATA on missing/invalid features.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


class ClassifierError(Exception):
    """Raised when classifier input violates schema or fails validation."""
    pass


@dataclass
class StateThresholdsV080:
    schema_version: str = "CBE-THRESHOLDS-0.8.0"
    training_partition: str = "DISCOVERY (< 2025-01-01)"
    training_sample_count: int = 420267
    source_commit: str = "81e5033"
    feature_thresholds: Dict[str, Dict[str, float]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, filepath: Path) -> None:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)

    @classmethod
    def load(cls, filepath: Path) -> "StateThresholdsV080":
        filepath = Path(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(**data)


@dataclass
class ClassificationResult:
    primary_state: str
    secondary_flags: List[str]
    classification_reason: str
    tier: str
    data_quality: str
    features_used: Dict[str, float]


class MarketStateClassifierV080:
    """Production candidate market state classifier for CBE-0.8.0 SPOT_ONLY_U0 tier."""

    PRIMARY_STATES = [
        "LOW_VOLATILITY",
        "NORMAL_VOLATILITY",
        "HIGH_VOLATILITY",
        "UNKNOWN_INSUFFICIENT_DATA",
    ]

    SECONDARY_FLAGS = [
        "VOLATILITY_COMPRESSION",
        "VOLATILITY_EXPANSION",
    ]

    def __init__(self, thresholds: Union[StateThresholdsV080, Path, Dict[str, Any]]):
        if isinstance(thresholds, (str, Path)):
            self.thresholds = StateThresholdsV080.load(Path(thresholds))
        elif isinstance(thresholds, StateThresholdsV080):
            self.thresholds = thresholds
        elif isinstance(thresholds, dict):
            self.thresholds = StateThresholdsV080(**thresholds)
        else:
            raise TypeError(f"Invalid thresholds type: {type(thresholds)}")

        # Extract fixed thresholds
        t_vol = self.thresholds.feature_thresholds.get("volatility_realized_24h", {})
        self.vol_p25 = float(t_vol.get("p25", 0.001140))
        self.vol_p75 = float(t_vol.get("p75", 0.002117))

        t_comp = self.thresholds.feature_thresholds.get("volatility_compression_ratio", {})
        self.comp_cutoff = float(t_comp.get("compression_cutoff", 0.80))
        self.exp_cutoff = float(t_comp.get("expansion_cutoff", 1.20))

    def classify_bar(
        self,
        features: Dict[str, Any],
        tier: str = "SPOT_ONLY_U0",
    ) -> ClassificationResult:
        """Classify a single bar deterministically without row-percentile collapse."""
        if not isinstance(features, dict):
            return ClassificationResult(
                primary_state="UNKNOWN_INSUFFICIENT_DATA",
                secondary_flags=[],
                classification_reason="Input features is not a dictionary",
                tier=tier,
                data_quality="INVALID_INPUT",
                features_used={},
            )

        # Check required features for SPOT_ONLY_U0
        val_vol = features.get("volatility_realized_24h")
        val_comp = features.get("volatility_compression_ratio")

        if val_vol is None or val_comp is None:
            return ClassificationResult(
                primary_state="UNKNOWN_INSUFFICIENT_DATA",
                secondary_flags=[],
                classification_reason="Missing core spot features (volatility_realized_24h or volatility_compression_ratio)",
                tier=tier,
                data_quality="INSUFFICIENT_DATA",
                features_used={},
            )

        try:
            f_vol = float(val_vol)
            f_comp = float(val_comp)
        except (ValueError, TypeError):
            return ClassificationResult(
                primary_state="UNKNOWN_INSUFFICIENT_DATA",
                secondary_flags=[],
                classification_reason="Feature value cannot be cast to float",
                tier=tier,
                data_quality="INVALID_DATA",
                features_used={},
            )

        if not (math.isfinite(f_vol) and math.isfinite(f_comp)):
            return ClassificationResult(
                primary_state="UNKNOWN_INSUFFICIENT_DATA",
                secondary_flags=[],
                classification_reason="Non-finite feature value (NaN or Inf)",
                tier=tier,
                data_quality="NON_FINITE_DATA",
                features_used={},
            )

        # 1. Mutually Exclusive Primary State
        if f_vol < self.vol_p25:
            primary_state = "LOW_VOLATILITY"
            reason = f"volatility_realized_24h ({f_vol:.6f}) < P25 ({self.vol_p25:.6f})"
        elif f_vol <= self.vol_p75:
            primary_state = "NORMAL_VOLATILITY"
            reason = f"P25 ({self.vol_p25:.6f}) <= volatility_realized_24h ({f_vol:.6f}) <= P75 ({self.vol_p75:.6f})"
        else:
            primary_state = "HIGH_VOLATILITY"
            reason = f"volatility_realized_24h ({f_vol:.6f}) > P75 ({self.vol_p75:.6f})"

        # 2. Independent Secondary Flags
        secondary_flags = []
        if f_comp < self.comp_cutoff:
            secondary_flags.append("VOLATILITY_COMPRESSION")
        elif f_comp >= self.exp_cutoff:
            secondary_flags.append("VOLATILITY_EXPANSION")

        return ClassificationResult(
            primary_state=primary_state,
            secondary_flags=secondary_flags,
            classification_reason=reason,
            tier=tier,
            data_quality="DATA_OK",
            features_used={
                "volatility_realized_24h": f_vol,
                "volatility_compression_ratio": f_comp,
            },
        )

    def classify_batch(self, df: Any) -> Tuple[np.ndarray, List[List[str]]]:
        """Vectorized classification over a dataframe."""
        vols = df["volatility_realized_24h"].values.astype(np.float64)
        comps = df["volatility_compression_ratio"].values.astype(np.float64)

        primary = np.where(
            np.isnan(vols) | np.isnan(comps),
            "UNKNOWN_INSUFFICIENT_DATA",
            np.where(
                vols < self.vol_p25,
                "LOW_VOLATILITY",
                np.where(vols <= self.vol_p75, "NORMAL_VOLATILITY", "HIGH_VOLATILITY"),
            ),
        )

        secondary = []
        for c, is_nan in zip(comps, np.isnan(comps)):
            if is_nan:
                secondary.append([])
            elif c < self.comp_cutoff:
                secondary.append(["VOLATILITY_COMPRESSION"])
            elif c >= self.exp_cutoff:
                secondary.append(["VOLATILITY_EXPANSION"])
            else:
                secondary.append([])

        return primary, secondary

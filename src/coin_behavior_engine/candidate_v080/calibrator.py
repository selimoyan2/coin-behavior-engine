"""CBE-0.8.0 Prediction Interval Calibrator Engine.

Resolves Failure B (Miscalibrated Forecast Intervals).
Implements empirical residual quantile / split-conformal calibration fitted strictly on
Validation (2025) residuals to guarantee nominal coverage on future observations.
Enforces strict monotonic non-negative bounds:
0 <= lower95 <= lower80 <= point_forecast <= upper80 <= upper95.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


class CalibrationError(Exception):
    """Raised when interval calibration fails or input is invalid."""
    pass


@dataclass
class HorizonCalibrationParameters:
    horizon: str
    calibration_sample_count: int
    global_quantiles: Dict[str, float]
    state_conditioned_quantiles: Dict[str, Dict[str, float]]
    calibration_mae: float
    calibration_rmse: float


@dataclass
class IntervalCalibrationV080:
    schema_version: str = "CBE-CALIBRATION-0.8.0"
    candidate_model_version: str = "CBE-0.8.0"
    calibration_partition: str = "VALIDATION_2025 (2025-01-01 to 2025-12-31)"
    calibration_method: str = "EMPIRICAL_RESIDUAL_QUANTILE_SPLIT_CONFORMAL"
    source_commit: str = "81e5033"
    target_units: str = "Daily-scaled standard deviation (sigma_5m * sqrt(288))"
    horizons: Dict[str, HorizonCalibrationParameters] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, filepath: Path) -> None:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)

    @classmethod
    def load(cls, filepath: Path) -> "IntervalCalibrationV080":
        filepath = Path(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        horizons_dict = {}
        for h, h_data in data.get("horizons", {}).items():
            horizons_dict[h] = HorizonCalibrationParameters(**h_data)

        data["horizons"] = horizons_dict
        return cls(**data)


class IntervalCalibratorV080:
    """Production candidate volatility uncertainty layer for CBE-0.8.0."""

    def __init__(self, calibration_data: Union[IntervalCalibrationV080, Path, Dict[str, Any]]):
        if isinstance(calibration_data, (str, Path)):
            self.calibration = IntervalCalibrationV080.load(Path(calibration_data))
        elif isinstance(calibration_data, IntervalCalibrationV080):
            self.calibration = calibration_data
        elif isinstance(calibration_data, dict):
            self.calibration = IntervalCalibrationV080(**calibration_data)
        else:
            raise TypeError(f"Invalid calibration data type: {type(calibration_data)}")

    def compute_intervals(
        self,
        point_forecast: float,
        horizon: str,
        market_state: Optional[str] = None,
        use_state_conditioned: bool = False,
    ) -> Dict[str, Any]:
        """Compute 80% and 95% calibrated prediction intervals around point forecast."""
        if horizon not in self.calibration.horizons:
            raise CalibrationError(
                f"Horizon '{horizon}' not found in calibration. Available: {list(self.calibration.horizons.keys())}"
            )

        try:
            p_val = float(point_forecast)
        except (ValueError, TypeError):
            raise CalibrationError(f"Point forecast cannot be converted to float: {point_forecast}")

        if not math.isfinite(p_val) or p_val < 0.0:
            raise CalibrationError(f"Point forecast must be a finite non-negative float, got {p_val}")

        h_cal = self.calibration.horizons[horizon]

        # Select quantiles
        fallback_used = False
        quantiles = None
        if use_state_conditioned and market_state:
            state_qs = h_cal.state_conditioned_quantiles.get(market_state)
            if state_qs and state_qs.get("sample_count", 0) >= 100:
                quantiles = state_qs
            else:
                fallback_used = True
                quantiles = h_cal.global_quantiles
        else:
            quantiles = h_cal.global_quantiles

        q025 = quantiles["q025"]
        q10 = quantiles["q10"]
        q90 = quantiles["q90"]
        q975 = quantiles["q975"]

        # Construct monotonic, non-negative intervals enclosing point_forecast:
        # lower80 = max(0.0, p_val + q10)
        # upper80 = max(p_val, p_val + q90)
        # lower95 = max(0.0, min(lower80, p_val + q025))
        # upper95 = max(upper80, p_val + q975)
        lower_80 = max(0.0, p_val + q10)
        upper_80 = max(p_val, p_val + q90)

        lower_95 = max(0.0, min(lower_80, p_val + q025))
        upper_95 = max(upper_80, p_val + q975)

        # Enforce strict ordering invariant
        assert 0.0 <= lower_95 <= lower_80 <= p_val <= upper_80 <= upper_95, (
            f"Ordering violation: 0 <= {lower_95} <= {lower_80} <= {p_val} <= {upper_80} <= {upper_95}"
        )

        return {
            "horizon": horizon,
            "point_forecast": p_val,
            "prediction_intervals": {
                "80_pct": {
                    "lower": lower_80,
                    "upper": upper_80,
                    "width": upper_80 - lower_80,
                },
                "95_pct": {
                    "lower": lower_95,
                    "upper": upper_95,
                    "width": upper_95 - lower_95,
                },
            },
            "calibration_version": self.calibration.schema_version,
            "calibration_method": self.calibration.calibration_method,
            "conditioning_state": market_state if (use_state_conditioned and not fallback_used) else "GLOBAL",
            "state_fallback_used": fallback_used,
        }

    def compute_batch_intervals(
        self,
        preds: np.ndarray,
        horizon: str,
        states: Optional[np.ndarray] = None,
        use_state_conditioned: bool = False,
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Vectorized computation of (lower80, upper80, lower95, upper95)."""
        h_cal = self.calibration.horizons[horizon]
        p_arr = np.maximum(0.0, preds.astype(np.float64))

        if use_state_conditioned and states is not None:
            l80 = np.empty_like(p_arr)
            u80 = np.empty_like(p_arr)
            l95 = np.empty_like(p_arr)
            u95 = np.empty_like(p_arr)

            for s_name, s_qs in h_cal.state_conditioned_quantiles.items():
                mask = states == s_name
                if not np.any(mask):
                    continue
                q025 = s_qs["q025"]
                q10 = s_qs["q10"]
                q90 = s_qs["q90"]
                q975 = s_qs["q975"]

                sub_p = p_arr[mask]
                sub_l80 = np.maximum(0.0, sub_p + q10)
                sub_u80 = np.maximum(sub_p, sub_p + q90)
                sub_l95 = np.maximum(0.0, np.minimum(sub_l80, sub_p + q025))
                sub_u95 = np.maximum(sub_u80, sub_p + q975)

                l80[mask] = sub_l80
                u80[mask] = sub_u80
                l95[mask] = sub_l95
                u95[mask] = sub_u95

            # Handle any remaining unmapped states with global quantiles
            unmapped = (states == "UNKNOWN_INSUFFICIENT_DATA") | ~np.isin(
                states, list(h_cal.state_conditioned_quantiles.keys())
            )
            if np.any(unmapped):
                g_qs = h_cal.global_quantiles
                sub_p = p_arr[unmapped]
                sub_l80 = np.maximum(0.0, sub_p + g_qs["q10"])
                sub_u80 = np.maximum(sub_p, sub_p + g_qs["q90"])
                sub_l95 = np.maximum(0.0, np.minimum(sub_l80, sub_p + g_qs["q025"]))
                sub_u95 = np.maximum(sub_u80, sub_p + g_qs["q975"])
                l80[unmapped] = sub_l80
                u80[unmapped] = sub_u80
                l95[unmapped] = sub_l95
                u95[unmapped] = sub_u95

            return l80, u80, l95, u95
        else:
            g_qs = h_cal.global_quantiles
            q025 = g_qs["q025"]
            q10 = g_qs["q10"]
            q90 = g_qs["q90"]
            q975 = g_qs["q975"]

            l80 = np.maximum(0.0, p_arr + q10)
            u80 = np.maximum(p_arr, p_arr + q90)
            l95 = np.maximum(0.0, np.minimum(l80, p_arr + q025))
            u95 = np.maximum(u80, p_arr + q975)

            return l80, u80, l95, u95

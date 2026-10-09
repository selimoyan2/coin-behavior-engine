"""CBE-0.8.0 / Sprint 09.5 High-Volatility Interval Calibrator Engine.

Implements regime-aware and volatility-normalized prediction interval calibration
to resolve high-volatility under-coverage while preserving strict interval monotonicity:
0 <= lower95 <= lower80 <= point_forecast <= upper80 <= upper95.

Supports:
1. Candidate B: State-conditioned empirical residual quantiles.
2. Candidate C: Volatility-normalized relative residual quantiles.
3. Candidate E: Conservative hybrid (state-conditioned with minimum sample fallback and tail protection).
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


class CalibrationV095Error(Exception):
    """Raised when interval calibration fails or input is invalid."""
    pass


@dataclass
class HorizonStateQuantiles:
    q025: float
    q10: float
    q90: float
    q975: float
    sample_count: int


@dataclass
class HorizonCalibrationV095:
    horizon: str
    calibration_sample_count: int
    global_quantiles: Dict[str, float]
    state_quantiles: Dict[str, Dict[str, float]]
    relative_quantiles: Dict[str, float]
    hybrid_quantiles: Dict[str, Dict[str, float]]
    calibration_mae: float
    calibration_rmse: float


@dataclass
class IntervalCalibrationV095:
    schema_version: str = "CBE-CALIBRATION-0.8.0-SPRINT09.5"
    candidate_model_version: str = "CBE-0.8.0"
    source_commit: str = "d6b326f"
    calibration_partition: str = "VALIDATION_2025_FIT (2025-01-01 to 2025-08-31)"
    evaluation_partition: str = "VALIDATION_2025_EVAL (2025-09-01 to 2025-12-31)"
    target_units: str = "Daily-scaled standard deviation (sigma_5m * sqrt(288))"
    horizons: Dict[str, HorizonCalibrationV095] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def save(self, filepath: Path) -> None:
        filepath = Path(filepath)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, sort_keys=True)

    @classmethod
    def load(cls, filepath: Path) -> "IntervalCalibrationV095":
        filepath = Path(filepath)
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        horizons_dict = {}
        for h, h_data in data.get("horizons", {}).items():
            horizons_dict[h] = HorizonCalibrationV095(**h_data)

        data["horizons"] = horizons_dict
        return cls(**data)


class IntervalCalibratorV095:
    """Production candidate volatility uncertainty layer with high-volatility repair."""

    def __init__(self, calibration_data: Union[IntervalCalibrationV095, Path, Dict[str, Any]]):
        if isinstance(calibration_data, (str, Path)):
            self.calibration = IntervalCalibrationV095.load(Path(calibration_data))
        elif isinstance(calibration_data, IntervalCalibrationV095):
            self.calibration = calibration_data
        elif isinstance(calibration_data, dict):
            self.calibration = IntervalCalibrationV095(**calibration_data)
        else:
            raise TypeError(f"Invalid calibration data type: {type(calibration_data)}")

    def compute_intervals(
        self,
        point_forecast: float,
        horizon: str,
        market_state: Optional[str] = None,
        method: str = "HYBRID",  # 'GLOBAL', 'STATE_CONDITIONED', 'VOL_NORMALIZED', 'HYBRID'
    ) -> Dict[str, Any]:
        """Compute 80% and 95% calibrated prediction intervals under selected method."""
        if horizon not in self.calibration.horizons:
            raise CalibrationV095Error(
                f"Horizon '{horizon}' not found. Available: {list(self.calibration.horizons.keys())}"
            )

        try:
            p_val = float(point_forecast)
        except (ValueError, TypeError):
            raise CalibrationV095Error(f"Point forecast cannot be converted to float: {point_forecast}")

        if not math.isfinite(p_val) or p_val < 0.0:
            raise CalibrationV095Error(f"Point forecast must be a finite non-negative float, got {p_val}")

        h_cal = self.calibration.horizons[horizon]

        fallback_used = False
        method_effective = method

        if method == "GLOBAL":
            q025 = h_cal.global_quantiles["q025"]
            q10 = h_cal.global_quantiles["q10"]
            q90 = h_cal.global_quantiles["q90"]
            q975 = h_cal.global_quantiles["q975"]

            lower_80 = max(0.0, p_val + q10)
            upper_80 = max(p_val, p_val + q90)
            lower_95 = max(0.0, min(lower_80, p_val + q025))
            upper_95 = max(upper_80, p_val + q975)

        elif method == "STATE_CONDITIONED":
            sq = h_cal.state_quantiles.get(market_state or "")
            if sq and sq.get("sample_count", 0) >= 500:
                q025 = sq["q025"]
                q10 = sq["q10"]
                q90 = sq["q90"]
                q975 = sq["q975"]
            else:
                fallback_used = True
                q025 = h_cal.global_quantiles["q025"]
                q10 = h_cal.global_quantiles["q10"]
                q90 = h_cal.global_quantiles["q90"]
                q975 = h_cal.global_quantiles["q975"]

            lower_80 = max(0.0, p_val + q10)
            upper_80 = max(p_val, p_val + q90)
            lower_95 = max(0.0, min(lower_80, p_val + q025))
            upper_95 = max(upper_80, p_val + q975)

        elif method == "VOL_NORMALIZED":
            rq = h_cal.relative_quantiles
            q025 = rq["q025"]
            q10 = rq["q10"]
            q90 = rq["q90"]
            q975 = rq["q975"]

            lower_80 = max(0.0, p_val * (1.0 + q10))
            upper_80 = max(p_val, p_val * (1.0 + q90))
            lower_95 = max(0.0, min(lower_80, p_val * (1.0 + q025)))
            upper_95 = max(upper_80, p_val * (1.0 + q975))

        elif method == "HYBRID":
            hq = h_cal.hybrid_quantiles.get(market_state or "")
            if hq:
                q025 = hq["q025"]
                q10 = hq["q10"]
                q90 = hq["q90"]
                q975 = hq["q975"]
            else:
                fallback_used = True
                q025 = h_cal.global_quantiles["q025"]
                q10 = h_cal.global_quantiles["q10"]
                q90 = h_cal.global_quantiles["q90"]
                q975 = h_cal.global_quantiles["q975"]

            lower_80 = max(0.0, p_val + q10)
            upper_80 = max(p_val, p_val + q90)
            lower_95 = max(0.0, min(lower_80, p_val + q025))
            upper_95 = max(upper_80, p_val + q975)

        else:
            raise CalibrationV095Error(f"Unknown calibration method: '{method}'")

        # Invariant check
        assert 0.0 <= lower_95 <= lower_80 <= p_val <= upper_80 <= upper_95, (
            f"Ordering invariant violated: 0 <= {lower_95} <= {lower_80} <= {p_val} <= {upper_80} <= {upper_95}"
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
            "method": method_effective,
            "market_state": market_state,
            "fallback_used": fallback_used,
            "schema_version": self.calibration.schema_version,
        }

    def compute_batch_intervals(
        self,
        preds: np.ndarray,
        horizon: str,
        states: Optional[np.ndarray] = None,
        method: str = "HYBRID",
    ) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """Vectorized computation of (lower80, upper80, lower95, upper95)."""
        h_cal = self.calibration.horizons[horizon]
        p_arr = np.maximum(0.0, preds.astype(np.float64))

        if method == "GLOBAL":
            g = h_cal.global_quantiles
            l80 = np.maximum(0.0, p_arr + g["q10"])
            u80 = np.maximum(p_arr, p_arr + g["q90"])
            l95 = np.maximum(0.0, np.minimum(l80, p_arr + g["q025"]))
            u95 = np.maximum(u80, p_arr + g["q975"])
            return l80, u80, l95, u95

        elif method == "VOL_NORMALIZED":
            rq = h_cal.relative_quantiles
            l80 = np.maximum(0.0, p_arr * (1.0 + rq["q10"]))
            u80 = np.maximum(p_arr, p_arr * (1.0 + rq["q90"]))
            l95 = np.maximum(0.0, np.minimum(l80, p_arr * (1.0 + rq["q025"])))
            u95 = np.maximum(u80, p_arr * (1.0 + rq["q975"]))
            return l80, u80, l95, u95

        elif method in ("STATE_CONDITIONED", "HYBRID"):
            q_dict = h_cal.state_quantiles if method == "STATE_CONDITIONED" else h_cal.hybrid_quantiles
            l80 = np.empty_like(p_arr)
            u80 = np.empty_like(p_arr)
            l95 = np.empty_like(p_arr)
            u95 = np.empty_like(p_arr)

            matched_mask = np.zeros(len(p_arr), dtype=bool)

            if states is not None:
                for s_name, qs in q_dict.items():
                    m = (states == s_name)
                    if np.any(m):
                        sub_p = p_arr[m]
                        sub_l80 = np.maximum(0.0, sub_p + qs["q10"])
                        sub_u80 = np.maximum(sub_p, sub_p + qs["q90"])
                        sub_l95 = np.maximum(0.0, np.minimum(sub_l80, sub_p + qs["q025"]))
                        sub_u95 = np.maximum(sub_u80, sub_p + qs["q975"])

                        l80[m] = sub_l80
                        u80[m] = sub_u80
                        l95[m] = sub_l95
                        u95[m] = sub_u95
                        matched_mask |= m

            # Global fallback for unmapped
            unmapped = ~matched_mask
            if np.any(unmapped):
                g = h_cal.global_quantiles
                sub_p = p_arr[unmapped]
                l80[unmapped] = np.maximum(0.0, sub_p + g["q10"])
                u80[unmapped] = np.maximum(sub_p, sub_p + g["q90"])
                l95[unmapped] = np.maximum(0.0, np.minimum(l80[unmapped], sub_p + g["q025"]))
                u95[unmapped] = np.maximum(u80[unmapped], sub_p + g["q975"])

            return l80, u80, l95, u95

        else:
            raise CalibrationV095Error(f"Unknown calibration method: '{method}'")

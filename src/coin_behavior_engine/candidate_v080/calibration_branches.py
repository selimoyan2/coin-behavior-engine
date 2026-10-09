"""CBE-0.8.0 Parallel Calibration Branches (Branch C and Branch E).

Implements independent, immutable calibration branches for the prospective shadow protocol:
- Branch C: Volatility-normalized relative residual quantiles.
- Branch E: Conservative hybrid regime-conditioned quantiles with tail safety factor 1.15x.

Both branches operate on identical frozen Ridge point forecasts, market states, and target units.
Neither branch is approved as a universally superior method; both remain frozen parallel candidates.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


class CalibrationBranchError(Exception):
    """Raised when calibration branch input or calculation is invalid."""
    pass


@dataclass
class BranchIntervals:
    branch_id: str
    horizon: str
    point_forecast: float
    lower_80: float
    upper_80: float
    width_80: float
    lower_95: float
    upper_95: float
    width_95: float
    method: str
    fallback_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "branch_id": self.branch_id,
            "horizon": self.horizon,
            "point_forecast": self.point_forecast,
            "intervals": {
                "80_pct": {
                    "lower": self.lower_80,
                    "upper": self.upper_80,
                    "width": self.width_80,
                },
                "95_pct": {
                    "lower": self.lower_95,
                    "upper": self.upper_95,
                    "width": self.width_95,
                },
            },
            "method": self.method,
            "fallback_used": self.fallback_used,
        }


class CalibrationBranchC:
    """Branch C: Volatility-Normalized Relative Residual Interval Calibration."""

    BRANCH_ID = "BRANCH_C_VOLATILITY_NORMALIZED"
    STATUS = "FROZEN_RESEARCH_BRANCH"

    def __init__(self, artifact_path: Union[str, Path]):
        self.artifact_path = Path(artifact_path)
        with open(self.artifact_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.horizons = self.data.get("horizons", {})

    def compute_intervals(self, point_forecast: float, horizon: str) -> BranchIntervals:
        if horizon not in self.horizons:
            raise CalibrationBranchError(f"Horizon '{horizon}' not found in Branch C calibration")

        p = float(point_forecast)
        if not math.isfinite(p) or p < 0.0:
            raise CalibrationBranchError(f"Point forecast must be non-negative finite float: {p}")

        rq = self.horizons[horizon]["relative_quantiles"]
        q025 = rq["q025"]
        q10 = rq["q10"]
        q90 = rq["q90"]
        q975 = rq["q975"]

        l80 = max(0.0, p * (1.0 + q10))
        u80 = max(p, p * (1.0 + q90))
        l95 = max(0.0, min(l80, p * (1.0 + q025)))
        u95 = max(u80, p * (1.0 + q975))

        assert 0.0 <= l95 <= l80 <= p <= u80 <= u95, f"Branch C monotonicity breach: 0 <= {l95} <= {l80} <= {p} <= {u80} <= {u95}"

        return BranchIntervals(
            branch_id=self.BRANCH_ID,
            horizon=horizon,
            point_forecast=p,
            lower_80=l80,
            upper_80=u80,
            width_80=u80 - l80,
            lower_95=l95,
            upper_95=u95,
            width_95=u95 - l95,
            method="VOL_NORMALIZED",
            fallback_used=False,
        )


class CalibrationBranchE:
    """Branch E: Conservative Hybrid Regime-Conditioned Interval Calibration."""

    BRANCH_ID = "BRANCH_E_CONSERVATIVE_HYBRID"
    STATUS = "FROZEN_RESEARCH_BRANCH"

    def __init__(self, artifact_path: Union[str, Path]):
        self.artifact_path = Path(artifact_path)
        with open(self.artifact_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)
        self.horizons = self.data.get("horizons", {})

    def compute_intervals(
        self, point_forecast: float, horizon: str, market_state: Optional[str] = None
    ) -> BranchIntervals:
        if horizon not in self.horizons:
            raise CalibrationBranchError(f"Horizon '{horizon}' not found in Branch E calibration")

        p = float(point_forecast)
        if not math.isfinite(p) or p < 0.0:
            raise CalibrationBranchError(f"Point forecast must be non-negative finite float: {p}")

        h_data = self.horizons[horizon]
        hq = h_data.get("hybrid_quantiles", {}).get(market_state or "")
        fallback_used = False

        if hq is not None and hq.get("sample_count", 0) >= 500:
            q025 = hq["q025"]
            q10 = hq["q10"]
            q90 = hq["q90"]
            q975 = hq["q975"]
        else:
            fallback_used = True
            gq = h_data["global_quantiles"]
            q025 = gq["q025"]
            q10 = gq["q10"]
            q90 = gq["q90"]
            q975 = gq["q975"]

        l80 = max(0.0, p + q10)
        u80 = max(p, p + q90)
        l95 = max(0.0, min(l80, p + q025))
        u95 = max(u80, p + q975)

        assert 0.0 <= l95 <= l80 <= p <= u80 <= u95, f"Branch E monotonicity breach: 0 <= {l95} <= {l80} <= {p} <= {u80} <= {u95}"

        return BranchIntervals(
            branch_id=self.BRANCH_ID,
            horizon=horizon,
            point_forecast=p,
            lower_80=l80,
            upper_80=u80,
            width_80=u80 - l80,
            lower_95=l95,
            upper_95=u95,
            width_95=u95 - l95,
            method="HYBRID",
            fallback_used=fallback_used,
        )


class DualBranchCalibrationManager:
    """Manages parallel inference across both Branch C and Branch E."""

    def __init__(
        self,
        branch_c_path: Union[str, Path] = "data/models/cbe_interval_calibration_v080_candidate_c.json",
        branch_e_path: Union[str, Path] = "data/models/cbe_interval_calibration_v080_095.json",
    ):
        self.branch_c = CalibrationBranchC(branch_c_path)
        self.branch_e = CalibrationBranchE(branch_e_path)

    def compute_dual_intervals(
        self,
        point_forecast: float,
        horizon: str,
        market_state: Optional[str] = None,
    ) -> Dict[str, BranchIntervals]:
        return {
            "branch_c": self.branch_c.compute_intervals(point_forecast, horizon),
            "branch_e": self.branch_e.compute_intervals(point_forecast, horizon, market_state=market_state),
        }

"""CBE-0.8.0 Unified Production Candidate Inference Pipeline.

Deterministic, fail-closed offline candidate inference engine unifying:
1. Frozen CBE-0.8.0 Ridge point forecasts (1h, 4h, 24h).
2. Discovery-trained causal market-state classifier (mutually exclusive primary state + secondary flags).
3. Calibrated volatility prediction intervals (satisfying strict monotonicity).
4. Strict unit enforcement: Daily-scaled standard deviation (sigma_5m * sqrt(288)).
5. Zero dynamic single-row thresholding, zero state mutation of point forecasts (DESCRIPTIVE_ONLY).
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from coin_behavior_engine.candidate_v080.bundle import ModelBundleV080
from coin_behavior_engine.candidate_v080.classifier import (
    ClassificationResult,
    MarketStateClassifierV080,
    StateThresholdsV080,
)
from coin_behavior_engine.candidate_v080.inference import (
    CandidateInferenceEngineV080,
    FeatureValidationError,
)
from coin_behavior_engine.candidate_v080.calibrator_v095 import (
    IntervalCalibrationV095,
    IntervalCalibratorV095,
)


TARGET_UNITS = "Daily-scaled standard deviation (sigma_5m * sqrt(288))"
MARKET_STATE_POINT_FORECAST_ROLE = "DESCRIPTIVE_ONLY"


@dataclass
class HorizonForecastResult:
    point_forecast: float
    intervals: Dict[str, Dict[str, float]]
    units: str = TARGET_UNITS
    point_forecast_role: str = MARKET_STATE_POINT_FORECAST_ROLE
    calibration_method: str = "HYBRID"
    fallback_used: bool = False


@dataclass
class CandidatePredictionResult:
    primary_state: str
    secondary_flags: List[str]
    classification_reason: str
    forecasts: Dict[str, HorizonForecastResult]
    timestamp: Optional[str] = None
    tier: str = "SPOT_ONLY_U0"
    data_quality: str = "VALID"
    diagnostics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        res = asdict(self)
        return res


class CandidateInferencePipelineV080:
    """Unified offline candidate inference pipeline for CBE-0.8.0."""

    SUPPORTED_HORIZONS = ["1h", "4h", "24h"]

    def __init__(
        self,
        bundle: Optional[Union[str, Path, ModelBundleV080, CandidateInferenceEngineV080]] = None,
        classifier: Optional[Union[str, Path, StateThresholdsV080, MarketStateClassifierV080]] = None,
        calibrator: Optional[Union[str, Path, IntervalCalibrationV095, IntervalCalibratorV095]] = None,
        calibration_method: str = "HYBRID",
        lockbox_path: Optional[Path] = None,
    ):
        base_models_dir = Path("data/models")

        # 1. Initialize Ridge Point Forecast Engine
        if bundle is None:
            bundle_path = base_models_dir / "cbe_model_bundle_v080.json"
            self.ridge_engine = CandidateInferenceEngineV080(bundle_path, lockbox_path=lockbox_path)
        elif isinstance(bundle, CandidateInferenceEngineV080):
            self.ridge_engine = bundle
        else:
            self.ridge_engine = CandidateInferenceEngineV080(bundle, lockbox_path=lockbox_path)

        # 2. Initialize Market State Classifier
        if classifier is None:
            classifier_path = base_models_dir / "cbe_state_thresholds_v080.json"
            self.classifier = MarketStateClassifierV080(classifier_path)
        elif isinstance(classifier, MarketStateClassifierV080):
            self.classifier = classifier
        else:
            self.classifier = MarketStateClassifierV080(classifier)

        # 3. Initialize Interval Calibrator
        if calibrator is None:
            calibrator_path = base_models_dir / "cbe_interval_calibration_v080_095.json"
            if not calibrator_path.exists():
                calibrator_path = base_models_dir / "cbe_interval_calibration_v080.json"
            self.calibrator = IntervalCalibratorV095(calibrator_path)
        elif isinstance(calibrator, IntervalCalibratorV095):
            self.calibrator = calibrator
        else:
            self.calibrator = IntervalCalibratorV095(calibrator)

        self.calibration_method = calibration_method
        self.ordered_features = self.ridge_engine.ordered_features

    def predict_bar(
        self,
        features: Dict[str, Any],
        horizons: Optional[List[str]] = None,
        timestamp: Optional[Union[str, pd.Timestamp]] = None,
    ) -> CandidatePredictionResult:
        """Compute integrated deterministic forecast and market state for a single bar.

        Fails closed on missing or non-finite features.
        Enforces:
        - 0 <= lower95 <= lower80 <= point_forecast <= upper80 <= upper95
        - MARKET_STATE_POINT_FORECAST_ROLE = DESCRIPTIVE_ONLY (market state never mutates point forecast)
        """
        t0 = time.perf_counter()
        target_horizons = horizons or self.SUPPORTED_HORIZONS

        for h in target_horizons:
            if h not in self.SUPPORTED_HORIZONS:
                raise ValueError(f"Unsupported horizon '{h}'. Supported: {self.SUPPORTED_HORIZONS}")

        # Validate features through Ridge engine (raises FeatureValidationError on missing/non-finite)
        _ = self.ridge_engine.validate_features_dict(features)

        # Classify market state (strictly causal, fixed thresholds)
        cls_result = self.classifier.classify_bar(features, tier="SPOT_ONLY_U0")

        forecasts: Dict[str, HorizonForecastResult] = {}

        for h in target_horizons:
            # 1. Compute point forecast strictly from Ridge weights
            pt_forecast = self.ridge_engine.predict(features, horizon=h)

            # Verification: Market state MUST NOT mutate point forecast
            # We explicitly compute intervals conditioned on state, but point forecast is preserved
            intervals_res = self.calibrator.compute_intervals(
                point_forecast=pt_forecast,
                horizon=h,
                market_state=cls_result.primary_state,
                method=self.calibration_method,
            )

            p_itv = intervals_res["prediction_intervals"]
            l80 = p_itv["80_pct"]["lower"]
            u80 = p_itv["80_pct"]["upper"]
            l95 = p_itv["95_pct"]["lower"]
            u95 = p_itv["95_pct"]["upper"]

            # Invariant check
            assert 0.0 <= l95 <= l80 <= pt_forecast <= u80 <= u95, (
                f"Interval ordering invariant violated for horizon {h}: "
                f"0.0 <= {l95:.6f} <= {l80:.6f} <= {pt_forecast:.6f} <= {u80:.6f} <= {u95:.6f}"
            )

            forecasts[h] = HorizonForecastResult(
                point_forecast=pt_forecast,
                intervals=p_itv,
                units=TARGET_UNITS,
                point_forecast_role=MARKET_STATE_POINT_FORECAST_ROLE,
                calibration_method=intervals_res["method"],
                fallback_used=intervals_res["fallback_used"],
            )

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        ts_str = str(timestamp) if timestamp is not None else None

        return CandidatePredictionResult(
            primary_state=cls_result.primary_state,
            secondary_flags=cls_result.secondary_flags,
            classification_reason=cls_result.classification_reason,
            forecasts=forecasts,
            timestamp=ts_str,
            tier=cls_result.tier,
            data_quality=cls_result.data_quality,
            diagnostics={
                "features_validated_count": len(self.ordered_features),
                "execution_time_ms": elapsed_ms,
                "calibration_method": self.calibration_method,
            },
        )

    def predict_batch(
        self,
        df: pd.DataFrame,
        horizons: Optional[List[str]] = None,
    ) -> List[CandidatePredictionResult]:
        """Compute predictions sequentially across dataframe rows."""
        results: List[CandidatePredictionResult] = []
        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            ts = row_dict.get("timestamp", idx)
            res = self.predict_bar(row_dict, horizons=horizons, timestamp=ts)
            results.append(res)
        return results

    def predict_batch_df(
        self,
        df: pd.DataFrame,
        horizons: Optional[List[str]] = None,
    ) -> pd.DataFrame:
        """Vectorized/batched prediction returning structured DataFrame."""
        target_horizons = horizons or self.SUPPORTED_HORIZONS
        records: List[Dict[str, Any]] = []

        for idx, row in df.iterrows():
            row_dict = row.to_dict()
            ts = row_dict.get("timestamp", idx)
            pred_res = self.predict_bar(row_dict, horizons=target_horizons, timestamp=ts)

            flat_rec: Dict[str, Any] = {
                "timestamp": ts,
                "primary_state": pred_res.primary_state,
                "secondary_flags": ",".join(pred_res.secondary_flags),
            }

            for h, fc in pred_res.forecasts.items():
                flat_rec[f"pred_{h}"] = fc.point_forecast
                flat_rec[f"lower80_{h}"] = fc.intervals["80_pct"]["lower"]
                flat_rec[f"upper80_{h}"] = fc.intervals["80_pct"]["upper"]
                flat_rec[f"lower95_{h}"] = fc.intervals["95_pct"]["lower"]
                flat_rec[f"upper95_{h}"] = fc.intervals["95_pct"]["upper"]

            records.append(flat_rec)

        return pd.DataFrame(records)

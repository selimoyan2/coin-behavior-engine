"""CBE-0.8.0 Candidate Research Package.

Isolated research and validation implementation for candidate model bundle, inference, and shadow replay.
"""

from coin_behavior_engine.candidate_v080.bundle import (
    BundleIntegrityError,
    ModelBundleV080,
    RidgeModelParameters,
    ScalerParameters,
)
from coin_behavior_engine.candidate_v080.inference import (
    CandidateInferenceEngineV080,
    FeatureValidationError,
)
from coin_behavior_engine.candidate_v080.calibrator import (
    CalibrationError,
    HorizonCalibrationParameters,
    IntervalCalibrationV080,
    IntervalCalibratorV080,
)
from coin_behavior_engine.candidate_v080.calibrator_v095 import (
    CalibrationV095Error,
    HorizonCalibrationV095,
    IntervalCalibrationV095,
    IntervalCalibratorV095,
)
from coin_behavior_engine.candidate_v080.classifier import (
    ClassificationResult,
    ClassifierError,
    MarketStateClassifierV080,
    StateThresholdsV080,
)
from coin_behavior_engine.candidate_v080.trainer import (
    CandidateTrainerV080,
)
from coin_behavior_engine.candidate_v080.replay import (
    ShadowReplayEngineV080,
)
from coin_behavior_engine.candidate_v080.metrics import (
    CanonicalMetricsEngine,
    PointMetrics,
    IntervalMetrics,
    StateDistributionMetrics,
    HorizonMetrics,
)
from coin_behavior_engine.candidate_v080.inference_pipeline import (
    CandidateInferencePipelineV080,
    CandidatePredictionResult,
    HorizonForecastResult,
    TARGET_UNITS,
    MARKET_STATE_POINT_FORECAST_ROLE,
)

__all__ = [
    "BundleIntegrityError",
    "CalibrationError",
    "CalibrationV095Error",
    "CandidateInferenceEngineV080",
    "CandidateInferencePipelineV080",
    "CandidatePredictionResult",
    "CandidateTrainerV080",
    "CanonicalMetricsEngine",
    "ClassificationResult",
    "ClassifierError",
    "FeatureValidationError",
    "HorizonCalibrationParameters",
    "HorizonCalibrationV095",
    "HorizonForecastResult",
    "HorizonMetrics",
    "IntervalCalibrationV080",
    "IntervalCalibrationV095",
    "IntervalCalibratorV080",
    "IntervalCalibratorV095",
    "IntervalMetrics",
    "MARKET_STATE_POINT_FORECAST_ROLE",
    "MarketStateClassifierV080",
    "ModelBundleV080",
    "PointMetrics",
    "RidgeModelParameters",
    "ScalerParameters",
    "ShadowReplayEngineV080",
    "StateDistributionMetrics",
    "StateThresholdsV080",
    "TARGET_UNITS",
]


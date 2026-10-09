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

__all__ = [
    "BundleIntegrityError",
    "CalibrationError",
    "CalibrationV095Error",
    "CandidateInferenceEngineV080",
    "CandidateTrainerV080",
    "ClassificationResult",
    "ClassifierError",
    "FeatureValidationError",
    "HorizonCalibrationParameters",
    "HorizonCalibrationV095",
    "IntervalCalibrationV080",
    "IntervalCalibrationV095",
    "IntervalCalibratorV080",
    "IntervalCalibratorV095",
    "MarketStateClassifierV080",
    "ModelBundleV080",
    "RidgeModelParameters",
    "ScalerParameters",
    "ShadowReplayEngineV080",
    "StateThresholdsV080",
]

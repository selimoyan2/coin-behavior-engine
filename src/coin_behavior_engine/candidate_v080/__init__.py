"""CBE-0.8.0 Candidate Research Package.

Isolated research and validation implementation for candidate model bundle and inference.
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
from coin_behavior_engine.candidate_v080.trainer import (
    CandidateTrainerV080,
)

__all__ = [
    "BundleIntegrityError",
    "CandidateInferenceEngineV080",
    "CandidateTrainerV080",
    "FeatureValidationError",
    "ModelBundleV080",
    "RidgeModelParameters",
    "ScalerParameters",
]

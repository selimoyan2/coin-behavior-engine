"""CBE-0.8.0 Isolated Shadow Observation Collector Package."""

from coin_behavior_engine.shadow_v080.candle_source import (
    BaseCandleSource,
    OfflineFixtureSource,
    ReadOnlyLiveBinanceSource,
    SafetyInterlockError,
    SourceDataError,
)
from coin_behavior_engine.shadow_v080.collector import ShadowCollectorV080
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.event_integrity import (
    ChainAuditReport,
    EventIntegrityAuditorV080,
)
from coin_behavior_engine.shadow_v080.feature_pipeline import FeaturePipelineV080
from coin_behavior_engine.shadow_v080.health_monitor import (
    HealthTelemetrySnapshot,
    ShadowHealthMonitorV080,
)
from coin_behavior_engine.shadow_v080.inference_runner import (
    DualBranchInferenceRunnerV080,
    DualBranchPredictionResult,
)
from coin_behavior_engine.shadow_v080.outcome_resolver import (
    OutcomeGapError,
    OutcomeResolverV080,
    PrematureOutcomeError,
    ShadowOutcomeEvent,
)
from coin_behavior_engine.shadow_v080.prediction_store import (
    DuplicateForecastError,
    EventTamperError,
    ImmutablePredictionStoreV080,
    SHADOW_GENESIS_HASH,
    ShadowPredictionEvent,
)

__all__ = [
    "BaseCandleSource",
    "ChainAuditReport",
    "DualBranchInferenceRunnerV080",
    "DualBranchPredictionResult",
    "DuplicateForecastError",
    "EventIntegrityAuditorV080",
    "EventTamperError",
    "FeaturePipelineV080",
    "HealthTelemetrySnapshot",
    "ImmutablePredictionStoreV080",
    "OfflineFixtureSource",
    "OutcomeGapError",
    "OutcomeResolverV080",
    "PrematureOutcomeError",
    "ReadOnlyLiveBinanceSource",
    "SHADOW_GENESIS_HASH",
    "SafetyInterlockError",
    "ShadowCollectorConfig",
    "ShadowCollectorV080",
    "ShadowHealthMonitorV080",
    "ShadowOutcomeEvent",
    "ShadowPredictionEvent",
    "SourceDataError",
]

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
from coin_behavior_engine.shadow_v080.gap_detector import (
    FULL_WARMUP_BARS,
    GapEvent,
    MarketDataGapDetector,
)
from coin_behavior_engine.shadow_v080.market_capture_engine import MarketCaptureEngineV080
from coin_behavior_engine.shadow_v080.market_data_contract import (
    BinanceSpotCandleValidator,
    CandleLifecycleState,
    MarketType,
    ProvenanceSource,
    ValidatedCandle,
    ValidationStatus,
)
from coin_behavior_engine.shadow_v080.prediction_store import (
    DuplicateForecastError,
    EventTamperError,
    ImmutablePredictionStoreV080,
    SHADOW_GENESIS_HASH,
    ShadowPredictionEvent,
)
from coin_behavior_engine.shadow_v080.raw_evidence_store import (
    ConflictingCandleError,
    EvidenceCorruptionError,
    EvidencePersistenceError,
    MarketEvidenceEntry,
    RawMarketEvidenceStore,
)
from coin_behavior_engine.shadow_v080.transport_adapter import (
    BaseMarketDataTransport,
    BinanceSpotRestAdapter,
    BinanceSpotWebSocketAdapter,
    MockMarketDataTransport,
    OversizedMessageError,
    QueueOverflowError,
    RateLimitExceededError,
    StaleFeedError,
    TransportConnectionError,
    calculate_backoff,
)

__all__ = [
    "BaseCandleSource",
    "BaseMarketDataTransport",
    "BinanceSpotCandleValidator",
    "BinanceSpotRestAdapter",
    "BinanceSpotWebSocketAdapter",
    "CandleLifecycleState",
    "ChainAuditReport",
    "ConflictingCandleError",
    "DualBranchInferenceRunnerV080",
    "DualBranchPredictionResult",
    "DuplicateForecastError",
    "EventIntegrityAuditorV080",
    "EventTamperError",
    "EvidenceCorruptionError",
    "EvidencePersistenceError",
    "FeaturePipelineV080",
    "FULL_WARMUP_BARS",
    "GapEvent",
    "HealthTelemetrySnapshot",
    "ImmutablePredictionStoreV080",
    "MarketCaptureEngineV080",
    "MarketDataGapDetector",
    "MarketEvidenceEntry",
    "MarketType",
    "MockMarketDataTransport",
    "OfflineFixtureSource",
    "OutcomeGapError",
    "OutcomeResolverV080",
    "OversizedMessageError",
    "PrematureOutcomeError",
    "ProvenanceSource",
    "QueueOverflowError",
    "RateLimitExceededError",
    "RawMarketEvidenceStore",
    "ReadOnlyLiveBinanceSource",
    "SHADOW_GENESIS_HASH",
    "SafetyInterlockError",
    "ShadowCollectorConfig",
    "ShadowCollectorV080",
    "ShadowHealthMonitorV080",
    "ShadowOutcomeEvent",
    "ShadowPredictionEvent",
    "SourceDataError",
    "StaleFeedError",
    "TransportConnectionError",
    "ValidatedCandle",
    "ValidationStatus",
    "calculate_backoff",
]

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
from coin_behavior_engine.shadow_v080.evidence_lookup import (
    ForwardWindowResult,
    ForwardWindowStatus,
    PersistentEvidenceLookupV080,
)
from coin_behavior_engine.shadow_v080.inference_runner import (
    DualBranchInferenceRunnerV080,
    DualBranchPredictionResult,
    verify_prospective_execution_boundary,
)
from coin_behavior_engine.shadow_v080.prediction_indexing import (
    DurableOutcomeIndexV080,
    DurablePredictionIndexV080,
    IPendingPredictionIndex,
    JournalPendingPredictionIndexV080,
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
from coin_behavior_engine.shadow_v080.prospective_guard import (
    CausalDataEligibilityGuard,
    DiscontinuousCandlesError,
    DuplicateTimestampError,
    IncompleteCandleError,
    InsufficientWarmupBarsError,
    InvalidMarketIdentityError,
    OFFLINE_RECORD_LABELS,
    PROSPECTIVE_RECORD_LABELS,
    ProspectiveAuthorizationError,
    ProspectiveAuthorizationGuard,
    ProspectiveSafetyError,
    SyntheticProvenanceError,
    TemporalAlignmentError,
    UnverifiedEvidenceError,
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
    "CausalDataEligibilityGuard",
    "ChainAuditReport",
    "ConflictingCandleError",
    "DiscontinuousCandlesError",
    "DualBranchInferenceRunnerV080",
    "DualBranchPredictionResult",
    "DuplicateForecastError",
    "DuplicateTimestampError",
    "DurableOutcomeIndexV080",
    "DurablePredictionIndexV080",
    "EventIntegrityAuditorV080",
    "EventTamperError",
    "EvidenceCorruptionError",
    "EvidencePersistenceError",
    "FeaturePipelineV080",
    "FULL_WARMUP_BARS",
    "ForwardWindowResult",
    "ForwardWindowStatus",
    "GapEvent",
    "HealthTelemetrySnapshot",
    "IPendingPredictionIndex",
    "ImmutablePredictionStoreV080",
    "IncompleteCandleError",
    "InsufficientWarmupBarsError",
    "InvalidMarketIdentityError",
    "JournalPendingPredictionIndexV080",
    "MarketCaptureEngineV080",
    "MarketDataGapDetector",
    "MarketEvidenceEntry",
    "MarketType",
    "MockMarketDataTransport",
    "OFFLINE_RECORD_LABELS",
    "OfflineFixtureSource",
    "OutcomeGapError",
    "OutcomeResolverV080",
    "OversizedMessageError",
    "PersistentEvidenceLookupV080",
    "PrematureOutcomeError",
    "PROSPECTIVE_RECORD_LABELS",
    "ProspectiveAuthorizationError",
    "ProspectiveAuthorizationGuard",
    "ProspectiveSafetyError",
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
    "SyntheticProvenanceError",
    "TemporalAlignmentError",
    "TransportConnectionError",
    "UnverifiedEvidenceError",
    "ValidatedCandle",
    "ValidationStatus",
    "calculate_backoff",
    "verify_prospective_execution_boundary",
]

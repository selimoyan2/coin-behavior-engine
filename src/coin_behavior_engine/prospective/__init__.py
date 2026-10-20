"""Prospective evaluation, immutable forecast logging, and model monitoring package (Sprint 08, Sprint 11.23.3 & Sprint 11.23.4)."""

from .freeze import verify_sprint07_freeze, ModelFreezeViolation
from .store import (
    ImmutablePredictionStore,
    OutcomeStore,
    AuditLogger,
    PredictionRecord,
    OutcomeRecord,
    ImmutableStoreViolation,
    HorizonNotMaturedError,
)
from .claim_v4 import ProspectiveClaimRegistry, TemporalClaimIntegrityViolation
from .monitoring import ProspectiveMonitor

# Sprint 11.23.3: Prospective Evidence Collection & Observation Readiness
from .event_models import (
    ProspectiveEventRecord,
    ProspectiveEventCategory,
    ProspectiveEventStatus,
    ConsensusRecord,
    ConsensusVerificationStatus,
    ReleaseDocument,
    AdapterFailureReason,
    EventRevisionRecord,
    TimestampProvenanceClassification,
)
from .prospective_event_registry import ProspectiveEventRegistry
from .source_adapters import (
    BaseSourceAdapter,
    BLSSourceAdapter,
    BEASourceAdapter,
    FederalReserveSourceAdapter,
    CryptoProtocolAdapter,
    ConsensusProviderAdapter,
)
from .consensus_registry import ConsensusEvidenceRegistry
from .evidence_vault import (
    ImmutableEvidenceVault,
    VaultCorruptionError,
    VaultSecurityError,
    VaultLockTimeoutError,
    VaultRecoveryStatus,
    CrossProcessVaultLock,
)
from .market_observer import ProspectiveMarketObserver, MarketCandle, EventObservationReport
from .event_state_machine import EventStateMachine, EventLifecycleTransitionError
from .simulation_scenarios import ProspectiveSimulationRunner
from .performance_guard import BoundedEventQueue, RateLimiter, CheckpointManager
from .governance import (
    ProspectiveGovernanceGuard,
    TradingIsolationViolation,
    CapabilityType,
    ProspectiveCapabilityToken,
)

# Sprint 11.23.4: Controlled Prospective Observation Pilot Hardening
from .research_transport import (
    ReadOnlyResearchTransport,
    TransportResponse,
    TransportSecurityError,
    NetworkAccessProhibitedError,
    InsecureSchemeError,
    DomainNotAllowedError,
    SSRFProtectionError,
    MethodNotAllowedError,
    SensitiveHeaderError,
    TradingEndpointAccessError,
    ResponseSizeExceededError,
    TransportTimeoutError,
    RateLimitExceededError,
    TLSVerificationError,
    RedirectSecurityError,
)
from .observability import ProspectiveObservability
from .pilot_runner import (
    ProspectivePilotRunner,
    PilotConfig,
    PilotAuthorizationToken,
    PilotExecutionError,
    CheckpointCorruptionError,
)
from .observation_authorization import (
    ObservationAuthorizationToken,
    ObservationAuthorizationEngine,
    AuthorizationCapability,
    AuthorizationStatus,
)
from .end_to_end_pilot_sim import EndToEndPilotSimulationSuite
from .recovery_simulation import EndToEndRecoverySimulationRunner

__all__ = [
    "verify_sprint07_freeze",
    "ModelFreezeViolation",
    "ImmutablePredictionStore",
    "OutcomeStore",
    "AuditLogger",
    "PredictionRecord",
    "OutcomeRecord",
    "ImmutableStoreViolation",
    "HorizonNotMaturedError",
    "ProspectiveClaimRegistry",
    "TemporalClaimIntegrityViolation",
    "ProspectiveMonitor",
    # Sprint 11.23.3 additions
    "ProspectiveEventRecord",
    "ProspectiveEventCategory",
    "ProspectiveEventStatus",
    "ConsensusRecord",
    "ConsensusVerificationStatus",
    "ReleaseDocument",
    "AdapterFailureReason",
    "EventRevisionRecord",
    "ProspectiveEventRegistry",
    "BaseSourceAdapter",
    "BLSSourceAdapter",
    "BEASourceAdapter",
    "FederalReserveSourceAdapter",
    "CryptoProtocolAdapter",
    "ConsensusProviderAdapter",
    "ConsensusEvidenceRegistry",
    "ImmutableEvidenceVault",
    "ProspectiveMarketObserver",
    "MarketCandle",
    "EventObservationReport",
    "EventStateMachine",
    "EventLifecycleTransitionError",
    "ProspectiveSimulationRunner",
    "BoundedEventQueue",
    "RateLimiter",
    "CheckpointManager",
    "ProspectiveGovernanceGuard",
    "TradingIsolationViolation",
    # Sprint 11.23.4 additions
    "TimestampProvenanceClassification",
    "VaultCorruptionError",
    "VaultSecurityError",
    "VaultLockTimeoutError",
    "VaultRecoveryStatus",
    "CrossProcessVaultLock",
    "CapabilityType",
    "ProspectiveCapabilityToken",
    "ReadOnlyResearchTransport",
    "TransportResponse",
    "TransportSecurityError",
    "NetworkAccessProhibitedError",
    "InsecureSchemeError",
    "DomainNotAllowedError",
    "SSRFProtectionError",
    "MethodNotAllowedError",
    "SensitiveHeaderError",
    "TradingEndpointAccessError",
    "ResponseSizeExceededError",
    "TransportTimeoutError",
    "RateLimitExceededError",
    "TLSVerificationError",
    "RedirectSecurityError",
    "ProspectiveObservability",
    "ProspectivePilotRunner",
    "PilotConfig",
    "PilotAuthorizationToken",
    "PilotExecutionError",
    "CheckpointCorruptionError",
    "ObservationAuthorizationToken",
    "ObservationAuthorizationEngine",
    "AuthorizationCapability",
    "AuthorizationStatus",
    "EndToEndPilotSimulationSuite",
    "EndToEndRecoverySimulationRunner",
]

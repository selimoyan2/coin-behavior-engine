"""CBE Historical Market Research Foundation.

Sprint 09.20: Historical Market Research Foundation — Architecture Discovery & Safe Offline Implementation.

Provides:
- Historical dataset contract, validation, and provenance tracking.
- Bounded-memory chunked dataset reader and idempotent storage.
- Price action features (Support/Resistance, Breakout, Failed Breakout, Retest, Pullback, Momentum, Reversal).
- Market sessions framework (Asian, London, New York, Overlaps, Opening Ranges: 5/10/15/30/60m with timezone/DST).
- Market context (Trend/Range, Volatility Regimes, Relative Volume, OHLCV Liquidity Proxies).
- Extensibility interfaces (News, Macro, Derivatives, Funding, Liquidations with availability timestamps).
- Purged and embargoed walk-forward time-series splitter.
- Investment-oriented net-return evaluation engine (TP/SL, fees, spread, slippage, drawdown, independent trade counts).
"""

from __future__ import annotations

from coin_behavior_engine.research.historical.dataset_contract import (
    BINANCE_SPOT_BTCUSDT_GENESIS_MS,
    BINANCE_SPOT_BTCUSDT_GENESIS_UTC,
    HistoricalDataBoundaryError,
    HistoricalDataStorageError,
    HistoricalDatasetContract,
    HistoricalDatasetProvenance,
    HistoricalDatasetReader,
    HistoricalDatasetStore,
    HistoricalMarketSpec,
)
from coin_behavior_engine.research.historical.validation import (
    HistoricalCandleValidator,
    HistoricalValidationReport,
)
from coin_behavior_engine.research.historical.price_action import (
    PriceActionFeatureExtractor,
    PriceActionSignals,
)
from coin_behavior_engine.research.historical.market_sessions import (
    MarketSession,
    MarketSessionConfig,
    MarketSessionDetector,
    OpeningRangeWindow,
)
from coin_behavior_engine.research.historical.market_context import (
    MarketContextExtractor,
    MarketContextFeatures,
)
from coin_behavior_engine.research.historical.extensibility_interfaces import (
    DerivativesContextItem,
    EconomicAnnouncementItem,
    EtfFlowItem,
    ExternalDataAvailabilityError,
    TimestampedNewsItem,
)
from coin_behavior_engine.research.historical.walkforward_purged import (
    PurgedEmbargoTimeSeriesSplitter,
    PurgedFold,
)
from coin_behavior_engine.research.historical.investment_evaluator import (
    InvestmentEvaluator,
    InvestmentOpportunity,
    PortfolioEvaluationReport,
    SimulatedTradeResult,
    TradeCostModel,
    TradeDirection,
)
from coin_behavior_engine.research.historical.binance_archival_ingestion import (
    BinanceArchivalDownloader,
    IngestionResult,
)
from coin_behavior_engine.research.historical.experiments import (
    HypothesisEvaluationResult,
    HypothesisExperimentConfig,
    ScientificExperimentRunner,
)
from coin_behavior_engine.research.historical.timeframe_aggregator import (
    AggregationReport,
    HistoricalTimeframeAggregator,
)
from coin_behavior_engine.research.historical.execution_model import (
    ExecutionMode,
    ExecutionParameters,
    ExecutionResult,
    OrderFillStatus,
    RealisticExecutionSimulator,
)
from coin_behavior_engine.research.historical.regime_filters import (
    FilterEvaluationReport,
    RegimeFilterBank,
    RegimeFilterType,
)
from coin_behavior_engine.research.historical.provenance import (
    AuditableTradeLedger,
    AuditableTradeRecord,
    ExperimentProvenanceRecord,
)
from coin_behavior_engine.research.historical.new_hypotheses import (
    NewHypothesesGenerator,
)
from coin_behavior_engine.research.historical.market_regime_intelligence import (
    ConditionalReturnDistribution,
    MarketRegimeEngine,
    MarketRegimeState,
    MomentumRegime,
    RegimeTransitionReport,
    TrendRegime,
    VolatilityRegime,
    VolumeRegime,
)
from coin_behavior_engine.research.historical.h4_conditional_research import (
    H4ConditionalExperimentRunner,
    H4ConditionalVariantResult,
)
from coin_behavior_engine.research.historical.behavioral_discovery import (
    BehavioralDiscoveryAnalyzer,
    BehavioralDiscoveryFinding,
    BehavioralEvidenceStatus,
)
from coin_behavior_engine.research.historical.extensibility_interfaces import (
    ExternalDataReadinessValidator,
    TimestampedSignalEnvelope,
)
from coin_behavior_engine.research.historical.regime_audit import (
    CausalityAttribution,
    NullModelTransitionStats,
    RegimeCausalityAuditReport,
    RegimeClassificationAuditor,
    SensitivityVariationResult,
)
from coin_behavior_engine.research.historical.executable_behaviors import (
    B3StrategyConfig,
    B5StrategyConfig,
    ExecutableBehaviorSimulator,
    ExecutableStrategyMetrics,
)
from coin_behavior_engine.research.historical.behavioral_validation import (
    BehavioralDecisionVerdict,
    BehavioralValidationOrchestrator,
    ConfirmatoryHoldoutResult,
    MultipleTestingCorrectionReport,
    PreRegistrationGate,
    WalkForwardFoldResult,
)
from coin_behavior_engine.research.historical.cross_sectional_universe import (
    AssetMetadata,
    CrossSectionalUniverseAuditReport,
    CrossSectionalUniverseAuditor,
    UniverseDatasetCoverage,
)
from coin_behavior_engine.research.historical.cross_sectional_relative_strength import (
    CrossSectionalFeatureSnapshot,
    CrossSectionalRelativeStrengthEngine,
    RankingPersistenceReport,
)
from coin_behavior_engine.research.historical.market_breadth import (
    MarketBreadthEngine,
    MarketBreadthSnapshot,
)
from coin_behavior_engine.research.historical.funding_research_contract import (
    FundingContractSpec,
    FundingPaymentConvention,
    FundingRateRecord,
    FundingRateResearchValidator,
    FundingReadinessReport,
    FundingReadinessStatus,
    SpotPerpetualAccountingContaminationError,
    SyntheticFundingProhibitionError,
)
from coin_behavior_engine.research.historical.cross_sectional_hypotheses import (
    CS1Config,
    CS2Config,
    CS3Config,
    CS4Config,
    CrossSectionalDecisionVerdict,
    CrossSectionalHypothesisResult,
    CrossSectionalPreRegistrationGate,
    CrossSectionalResearchRunner,
)
from coin_behavior_engine.research.historical.portfolio_accounting import (
    PortfolioAccountingReconciliationError,
    PortfolioAccountingSimulator,
    PortfolioAccountingVerifier,
    PortfolioLedgerEntry,
    PortfolioPerformanceSummary,
)
from coin_behavior_engine.research.historical.benchmark_comparison import (
    BenchmarkComparisonEngine,
    BenchmarkComparisonResult,
)
from coin_behavior_engine.research.historical.execution_sensitivity import (
    ExecutionScenarioResult,
    ExecutionSensitivityAuditor,
)
from coin_behavior_engine.research.historical.ranking_persistence_audit import (
    RankingPersistenceAuditReport,
    RankingPersistenceAuditor,
)
from coin_behavior_engine.research.historical.universe_quality_audit import (
    UniverseQualityAuditReport,
    UniverseQualityAuditor,
)
from coin_behavior_engine.research.historical.chronological_forward_validation import (
    CS1DecisionVerdict,
    ChronologicalForwardValidator,
    ConfirmatoryForwardValidationReport,
    PreRegistrationGateSprint29,
)
from coin_behavior_engine.research.historical.forensic_accounting_auditor import (
    ForensicLegAudit,
    ForensicLedgerReconciliationReport,
    ForensicReconciliationError,
    ForensicTransitionAudit,
    IndependentForensicPortfolioAuditor,
)
from coin_behavior_engine.research.historical.forward_validation_forensics import (
    BootstrapSensitivitySweep,
    ForwardValidationForensicAuditor,
    January2025ForensicReport,
    SampleConfigurationComparison,
)
from coin_behavior_engine.research.historical.benchmark_forensics import (
    BenchmarkForensicAuditor,
    BenchmarkForensicsReport,
    BenchmarkParityAuditRecord,
    EquityBridgeComponent,
    GrossToNetEquityBridge,
)
from coin_behavior_engine.research.historical.execution_realism_model import (
    ExecutionRealismAuditor,
    ExecutionRealismForensicsReport,
    ExecutionTierResult,
)
from coin_behavior_engine.research.historical.forensic_closure_sprint31 import (
    ForensicClosureAuditor,
    ForensicClosureReport,
    HistoricalGrossReconciliation,
    MakerFillParadoxAnalysis,
    TradedNotionalReconciliationRecord,
)
from coin_behavior_engine.research.historical.capital_preservation_research import (
    BootstrapConfidenceRecord,
    CapitalPreservationEngine,
    CapitalPreservationPerformanceRecord,
    CapitalPreservationResearchReport,
    CostSensitivityRecord,
)
from coin_behavior_engine.research.historical.passive_allocation_engine import (
    BootstrapValidationRecord,
    HistoricalAccountingParityRecord,
    PassiveAllocationEngine,
    PortfolioPerformanceRecord,
    RegimeIncrementalValueRecord,
    RobustnessSensitivityRecord,
    Sprint0932ResearchReport,
)
from coin_behavior_engine.research.historical.accounting_standard import (
    AccountingConceptDefinition,
    CanonicalAccountingStandard,
)
from coin_behavior_engine.research.historical.evidence_registry import (
    CanonicalEvidenceRegistry,
    DatasetExposureRecord,
    InfrastructureAuditReport,
    ResearchHypothesisRecord,
    StatisticalPolicyRule,
)
from coin_behavior_engine.research.historical.research_roadmap import (
    ResearchDomainFeasibilityAssessment,
    ResearchRoadmapEvaluator,
    ResearchRoadmapReport,
)
from coin_behavior_engine.research.historical.funding_data_contract import (
    DatasetReadinessClassification,
    DeltaNeutralAccountingSpec,
    FundingDescriptiveStatistics,
    FundingSettlementRecord,
    InstrumentType,
    PerpetualCandleRecord,
    PerpetualFundingMasterReport,
    SpotPerpAlignedBasisRecord,
)
from coin_behavior_engine.research.historical.funding_ingestion_pipeline import (
    BinancePerpetualFundingIngestionPipeline,
)
from coin_behavior_engine.research.historical.funding_integrity_verifier import (
    FundingIntegrityError,
    FundingIntegrityVerificationReport,
    PerpetualFundingIntegrityVerifier,
)
from coin_behavior_engine.research.historical.funding_diagnostics import (
    FundingDiagnosticsEngine,
)
from coin_behavior_engine.research.historical.delta_neutral_carry_simulator import (
    AccountingIdentityReconciliation,
    DeltaNeutralCarrySimulator,
    DeltaNeutralExecutionParams,
    DeltaNeutralScenarioResult,
    PortfolioSnapshot,
)
from coin_behavior_engine.research.historical.delta_neutral_ledger_verifier import (
    DeltaNeutralLedgerVerifier,
    LedgerAuditReport,
    PrimitiveLedgerEvent,
)
from coin_behavior_engine.research.historical.delta_neutral_forensics_sprint36 import (
    ExchangeMarginMechanicRule,
    IndependentDecimalReferenceAccountant,
    IndependentDecimalReferenceResult,
    S6LiquidationForensicReport,
    ScenarioPnLForensicReconciliation,
    SpotCandleOHLC,
    Sprint36ForensicValidator,
)
from coin_behavior_engine.research.historical.carry_accounting_closure_sprint37 import (
    CanonicalCarryScenarioResult,
    CanonicalDecimalCarryVerifier,
    CanonicalMaintenanceMarginRegistry,
    CollateralTransferEvent,
    LiquidationEventForensicClosure,
    MarkPriceIntegrityReport,
    PerpetualMarkPriceCandleRecord,
    Sprint36RowForensicAudit,
    Sprint37CarryClosureAuditor,
    VersionedMaintenanceMarginContract,
    VersionedMarginBracket,
)
from coin_behavior_engine.research.historical.funding_predictability_sprint38 import (
    DynamicCarryPolicyResult,
    EconomicBreakEvenResult,
    FundingTimestampForensicRecord,
    ModelForecastMetrics,
    PointInTimeFeatureRecord,
    Sprint38FundingAuditor,
    Sprint38MasterReport,
    compute_diebold_mariano,
    holm_bonferroni_correction,
)
from coin_behavior_engine.research.historical.cross_instrument_funding_sprint39 import (
    CrossInstrumentDispersionReport,
    InstrumentFundingStats,
    LiveCalibrationAuditRecord,
    LiveDashboardProvenanceAuditRecord,
    PassiveCarryCapitalAccountingAudit,
    PredictiveStrategyLedgerAuditRecord,
    SampleDenominatorAuditRecord,
    Sprint39CrossInstrumentAuditor,
    Sprint39MasterReport,
)
from coin_behavior_engine.research.historical.multi_asset_carry_sprint40 import (
    AssetDatasetCompletenessRecord,
    CapitalAllocationContract,
    FundingSpreadPersistenceReport,
    LiveOutcomeForensicClosure,
    PassiveCarryBenchmarkResult,
    Sprint40MasterReport,
    Sprint40MultiAssetCarryAuditor,
    StaticPortfolioAllocationResult,
    StressScenarioResult,
    SwitchingCostHurdleAudit,
    ZeroLiquidationRiskCorrectionAudit,
)
from coin_behavior_engine.research.historical.multi_asset_carry_sprint41 import (
    CarryBenchmarkStructureResult,
    DecimalBalanceSheetReconciliation,
    InstrumentAuthenticDatasetRecord,
    PortfolioMarginFeasibilityReport,
    RiskFreeBenchmarkComparisonReport,
    Sprint40ClaimsCorrectionAudit,
    Sprint41MasterReport,
    Sprint41MultiAssetAuditor,
)

__all__ = [
    "BINANCE_SPOT_BTCUSDT_GENESIS_MS",
    "BINANCE_SPOT_BTCUSDT_GENESIS_UTC",
    "HistoricalMarketSpec",
    "HistoricalDatasetProvenance",
    "HistoricalDatasetContract",
    "HistoricalDatasetStore",
    "HistoricalDatasetReader",
    "HistoricalCandleValidator",
    "HistoricalValidationReport",
    "PriceActionFeatureExtractor",
    "PriceActionSignals",
    "MarketSession",
    "OpeningRangeWindow",
    "MarketSessionConfig",
    "MarketSessionDetector",
    "MarketContextExtractor",
    "MarketContextFeatures",
    "TimestampedNewsItem",
    "EconomicAnnouncementItem",
    "DerivativesContextItem",
    "EtfFlowItem",
    "ExternalDataAvailabilityError",
    "PurgedEmbargoTimeSeriesSplitter",
    "PurgedFold",
    "TradeDirection",
    "InvestmentOpportunity",
    "TradeCostModel",
    "SimulatedTradeResult",
    "PortfolioEvaluationReport",
    "InvestmentEvaluator",
    "BinanceArchivalDownloader",
    "IngestionResult",
    "ScientificExperimentRunner",
    "HypothesisEvaluationResult",
    "HypothesisExperimentConfig",
    "HistoricalTimeframeAggregator",
    "AggregationReport",
    "ExecutionMode",
    "ExecutionParameters",
    "ExecutionResult",
    "OrderFillStatus",
    "RealisticExecutionSimulator",
    "FilterEvaluationReport",
    "RegimeFilterBank",
    "RegimeFilterType",
    "AuditableTradeLedger",
    "AuditableTradeRecord",
    "ExperimentProvenanceRecord",
    "NewHypothesesGenerator",
    "TrendRegime",
    "VolatilityRegime",
    "VolumeRegime",
    "MomentumRegime",
    "MarketRegimeState",
    "RegimeTransitionReport",
    "ConditionalReturnDistribution",
    "MarketRegimeEngine",
    "H4ConditionalVariantResult",
    "H4ConditionalExperimentRunner",
    "BehavioralEvidenceStatus",
    "BehavioralDiscoveryFinding",
    "BehavioralDiscoveryAnalyzer",
    "TimestampedSignalEnvelope",
    "ExternalDataReadinessValidator",
    "CausalityAttribution",
    "NullModelTransitionStats",
    "SensitivityVariationResult",
    "RegimeCausalityAuditReport",
    "RegimeClassificationAuditor",
    "B3StrategyConfig",
    "B5StrategyConfig",
    "ExecutableBehaviorSimulator",
    "ExecutableStrategyMetrics",
    "BehavioralDecisionVerdict",
    "PreRegistrationGate",
    "MultipleTestingCorrectionReport",
    "WalkForwardFoldResult",
    "ConfirmatoryHoldoutResult",
    "BehavioralValidationOrchestrator",
    "AssetMetadata",
    "UniverseDatasetCoverage",
    "CrossSectionalUniverseAuditReport",
    "CrossSectionalUniverseAuditor",
    "CrossSectionalFeatureSnapshot",
    "CrossSectionalRelativeStrengthEngine",
    "RankingPersistenceReport",
    "MarketBreadthSnapshot",
    "MarketBreadthEngine",
    "FundingPaymentConvention",
    "FundingReadinessStatus",
    "SyntheticFundingProhibitionError",
    "SpotPerpetualAccountingContaminationError",
    "FundingContractSpec",
    "FundingRateRecord",
    "FundingReadinessReport",
    "FundingRateResearchValidator",
    "CS1Config",
    "CS2Config",
    "CS3Config",
    "CS4Config",
    "CrossSectionalDecisionVerdict",
    "CrossSectionalPreRegistrationGate",
    "CrossSectionalHypothesisResult",
    "CrossSectionalResearchRunner",
    "PortfolioAccountingReconciliationError",
    "PortfolioLedgerEntry",
    "PortfolioPerformanceSummary",
    "PortfolioAccountingVerifier",
    "PortfolioAccountingSimulator",
    "BenchmarkComparisonResult",
    "BenchmarkComparisonEngine",
    "ExecutionScenarioResult",
    "ExecutionSensitivityAuditor",
    "RankingPersistenceAuditReport",
    "RankingPersistenceAuditor",
    "UniverseQualityAuditReport",
    "UniverseQualityAuditor",
    "CS1DecisionVerdict",
    "PreRegistrationGateSprint29",
    "ConfirmatoryForwardValidationReport",
    "ChronologicalForwardValidator",
    "ForensicReconciliationError",
    "ForensicLegAudit",
    "ForensicTransitionAudit",
    "ForensicLedgerReconciliationReport",
    "IndependentForensicPortfolioAuditor",
    "BootstrapSensitivitySweep",
    "SampleConfigurationComparison",
    "January2025ForensicReport",
    "ForwardValidationForensicAuditor",
    "EquityBridgeComponent",
    "GrossToNetEquityBridge",
    "BenchmarkParityAuditRecord",
    "BenchmarkForensicsReport",
    "BenchmarkForensicAuditor",
    "ExecutionTierResult",
    "ExecutionRealismForensicsReport",
    "ExecutionRealismAuditor",
    "TradedNotionalReconciliationRecord",
    "MakerFillParadoxAnalysis",
    "HistoricalGrossReconciliation",
    "ForensicClosureReport",
    "ForensicClosureAuditor",
    "CapitalPreservationPerformanceRecord",
    "CostSensitivityRecord",
    "BootstrapConfidenceRecord",
    "CapitalPreservationResearchReport",
    "CapitalPreservationEngine",
    "HistoricalAccountingParityRecord",
    "PortfolioPerformanceRecord",
    "RegimeIncrementalValueRecord",
    "RobustnessSensitivityRecord",
    "BootstrapValidationRecord",
    "Sprint0932ResearchReport",
    "PassiveAllocationEngine",
    "AccountingConceptDefinition",
    "CanonicalAccountingStandard",
    "ResearchHypothesisRecord",
    "DatasetExposureRecord",
    "StatisticalPolicyRule",
    "InfrastructureAuditReport",
    "CanonicalEvidenceRegistry",
    "ResearchDomainFeasibilityAssessment",
    "ResearchRoadmapReport",
    "ResearchRoadmapEvaluator",
    "InstrumentType",
    "DatasetReadinessClassification",
    "FundingSettlementRecord",
    "PerpetualCandleRecord",
    "SpotPerpAlignedBasisRecord",
    "FundingDescriptiveStatistics",
    "DeltaNeutralAccountingSpec",
    "PerpetualFundingMasterReport",
    "BinancePerpetualFundingIngestionPipeline",
    "FundingIntegrityError",
    "FundingIntegrityVerificationReport",
    "PerpetualFundingIntegrityVerifier",
    "FundingDiagnosticsEngine",
    "DeltaNeutralExecutionParams",
    "PortfolioSnapshot",
    "AccountingIdentityReconciliation",
    "DeltaNeutralScenarioResult",
    "DeltaNeutralCarrySimulator",
    "PrimitiveLedgerEvent",
    "LedgerAuditReport",
    "DeltaNeutralLedgerVerifier",
    "SpotCandleOHLC",
    "ScenarioPnLForensicReconciliation",
    "S6LiquidationForensicReport",
    "ExchangeMarginMechanicRule",
    "IndependentDecimalReferenceResult",
    "IndependentDecimalReferenceAccountant",
    "Sprint36ForensicValidator",
    "PerpetualMarkPriceCandleRecord",
    "MarkPriceIntegrityReport",
    "VersionedMarginBracket",
    "VersionedMaintenanceMarginContract",
    "CollateralTransferEvent",
    "LiquidationEventForensicClosure",
    "Sprint36RowForensicAudit",
    "CanonicalCarryScenarioResult",
    "CanonicalMaintenanceMarginRegistry",
    "CanonicalDecimalCarryVerifier",
    "Sprint37CarryClosureAuditor",
    "FundingTimestampForensicRecord",
    "PointInTimeFeatureRecord",
    "ModelForecastMetrics",
    "EconomicBreakEvenResult",
    "DynamicCarryPolicyResult",
    "Sprint38MasterReport",
    "Sprint38FundingAuditor",
    "compute_diebold_mariano",
    "holm_bonferroni_correction",
    "LiveDashboardProvenanceAuditRecord",
    "LiveCalibrationAuditRecord",
    "SampleDenominatorAuditRecord",
    "PassiveCarryCapitalAccountingAudit",
    "PredictiveStrategyLedgerAuditRecord",
    "InstrumentFundingStats",
    "CrossInstrumentDispersionReport",
    "Sprint39MasterReport",
    "Sprint39CrossInstrumentAuditor",
    "ZeroLiquidationRiskCorrectionAudit",
    "CapitalAllocationContract",
    "LiveOutcomeForensicClosure",
    "AssetDatasetCompletenessRecord",
    "PassiveCarryBenchmarkResult",
    "FundingSpreadPersistenceReport",
    "SwitchingCostHurdleAudit",
    "StaticPortfolioAllocationResult",
    "StressScenarioResult",
    "Sprint40MasterReport",
    "Sprint40MultiAssetCarryAuditor",
    "Sprint40ClaimsCorrectionAudit",
    "InstrumentAuthenticDatasetRecord",
    "DecimalBalanceSheetReconciliation",
    "CarryBenchmarkStructureResult",
    "PortfolioMarginFeasibilityReport",
    "RiskFreeBenchmarkComparisonReport",
    "Sprint41MasterReport",
    "Sprint41MultiAssetAuditor",
]

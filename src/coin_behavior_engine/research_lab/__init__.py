"""CBE Research Lab — Market Behavior Research Lab, Event Intelligence & Historical Simulation.

Sprint 11.03: Real-data market behavior research, multi-horizon probabilistic modeling,
event intelligence, and deterministic historical paper trading simulation.
"""

from coin_behavior_engine.research_lab.configuration import ResearchLabConfig
from coin_behavior_engine.research_lab.contracts import (
    BehavioralPattern,
    CandleData,
    CaseStudyResult,
    DecisionAction,
    DecisionMode,
    EventCategory,
    EventIntelligenceRecord,
    MarketBehaviorFeatures,
    MarketRegimeType,
    PaperTrade,
    ProbabilisticPrediction,
    ResearchDecision,
    Resolution,
    SimulationRunResult,
    TradeExitReason,
)
from coin_behavior_engine.research_lab.data_quality import (
    DataQualityReport,
    DataQualityValidator,
)
from coin_behavior_engine.research_lab.decision_engine import ResearchDecisionEngine
from coin_behavior_engine.research_lab.evaluation import StrategyEvaluator
from coin_behavior_engine.research_lab.event_alignment import (
    EventAlignmentResult,
    EventMarketAligner,
)
from coin_behavior_engine.research_lab.event_intelligence import EventIntelligenceStore
from coin_behavior_engine.research_lab.feature_engine import MarketBehaviorFeatureEngine
from coin_behavior_engine.research_lab.historical_data import (
    BinanceHistoricalAdapter,
    LiveCaptureEvidenceAdapter,
    TimeframeAggregator,
)
from coin_behavior_engine.research_lab.market_regime import MarketRegimeDetector
from coin_behavior_engine.research_lab.pattern_engine import BehavioralPatternEngine
from coin_behavior_engine.research_lab.probability_engine import ProbabilityEngine
from coin_behavior_engine.research_lab.reporting import ResearchLabReporter
from coin_behavior_engine.research_lab.risk_engine import RiskEngine
from coin_behavior_engine.research_lab.simulator import HistoricalPaperSimulator

__all__ = [
    "ResearchLabConfig",
    "CandleData",
    "Resolution",
    "MarketRegimeType",
    "DecisionAction",
    "DecisionMode",
    "TradeExitReason",
    "EventCategory",
    "MarketBehaviorFeatures",
    "EventIntelligenceRecord",
    "BehavioralPattern",
    "ProbabilisticPrediction",
    "ResearchDecision",
    "PaperTrade",
    "SimulationRunResult",
    "CaseStudyResult",
    "DataQualityReport",
    "DataQualityValidator",
    "BinanceHistoricalAdapter",
    "LiveCaptureEvidenceAdapter",
    "TimeframeAggregator",
    "MarketBehaviorFeatureEngine",
    "MarketRegimeDetector",
    "EventIntelligenceStore",
    "EventAlignmentResult",
    "EventMarketAligner",
    "BehavioralPatternEngine",
    "ProbabilityEngine",
    "RiskEngine",
    "ResearchDecisionEngine",
    "HistoricalPaperSimulator",
    "StrategyEvaluator",
    "ResearchLabReporter",
]

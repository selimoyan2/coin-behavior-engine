"""Next-Generation Research Roadmap & Domain Feasibility Scoring (Sprint 09.33).

Evaluates the feasibility of three future research domains based on economic rationale,
authentic data availability, implementation complexity, and empirical testability:
- Domain A: Cross-Market Liquidity and Price Relationships
- Domain B: Real Execution Microstructure
- Domain C: Perpetual Funding and Basis
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Mapping, Sequence


@dataclass(frozen=True)
class ResearchDomainFeasibilityAssessment:
    """Detailed feasibility evaluation for a candidate future research domain."""
    domain_id: str
    domain_name: str
    target_phenomena: str
    economic_rationale: str
    authentic_data_sources: List[str]
    data_authenticity_and_verification: str
    historical_coverage_and_depth: str
    microstructure_and_execution_realism: str
    pitfalls_and_delusions_to_avoid: str

    # Rubric Scores (1 to 10 scale, where 10 is most favorable)
    economic_rationale_score: float
    data_authenticity_score: float
    historical_coverage_score: float
    implementation_simplicity_score: float  # 10 = simplest, 1 = hardest
    execution_feasibility_score: float
    statistical_testability_score: float
    infrastructure_affordability_score: float  # 10 = cheapest, 1 = most expensive
    expected_research_value_score: float

    @property
    def total_score(self) -> float:
        """Weighted aggregate feasibility score out of 80.0."""
        return (
            self.economic_rationale_score
            + self.data_authenticity_score
            + self.historical_coverage_score
            + self.implementation_simplicity_score
            + self.execution_feasibility_score
            + self.statistical_testability_score
            + self.infrastructure_affordability_score
            + self.expected_research_value_score
        )

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["total_score"] = round(self.total_score, 2)
        return d


@dataclass(frozen=True)
class ResearchRoadmapReport:
    """Master next-generation research roadmap report with ranked domain priorities."""
    domains: List[ResearchDomainFeasibilityAssessment]
    ranked_domain_ids: List[str]
    top_recommended_domain: str
    strategic_roadmap_narrative: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domains": [d.to_dict() for d in self.domains],
            "ranked_domain_ids": self.ranked_domain_ids,
            "top_recommended_domain": self.top_recommended_domain,
            "strategic_roadmap_narrative": self.strategic_roadmap_narrative,
        }


class ResearchRoadmapEvaluator:
    """Evaluates and ranks prospective research directions."""

    @staticmethod
    def evaluate_all_domains() -> ResearchRoadmapReport:
        """Assess Domain A, Domain B, and Domain C across the standardized 8-dimension rubric."""
        domain_a = ResearchDomainFeasibilityAssessment(
            domain_id="DOMAIN_A_CROSS_MARKET_LIQUIDITY",
            domain_name="Cross-Market Liquidity & Price Relationships",
            target_phenomena="Spot price dispersion, liquidity fragmentation, order flow concentration, and lead-lag relationships across centralized exchanges (Binance vs Coinbase vs Kraken).",
            economic_rationale="Different venues host distinct participant pools (institutional USD on Coinbase vs offshore retail/algo USDT on Binance). Price discovery often initiates on one venue before diffusing.",
            authentic_data_sources=[
                "Binance Data Vision (official monthly klines/trades)",
                "Coinbase Exchange public historical archives / REST API",
                "Kraken public market data REST API",
            ],
            data_authenticity_and_verification="Medium-High. Multiple independent venue APIs exist, but cross-exchange clock synchronization and timestamp jitter present moderate ingestion overhead.",
            historical_coverage_and_depth="High for OHLCV; Medium for tick-level order flow across non-Binance venues without paid vendor subscriptions.",
            microstructure_and_execution_realism="Requires modeling transfer latency, cross-venue capital lockup, and separate withdrawal fee structures. Real arbitrage requires pre-positioned capital on both venues.",
            pitfalls_and_delusions_to_avoid="Assuming 'paper arbitrage' without modeling capital bifurcation, transfer friction, differing collateral haircuts, and venue counterparty risk.",
            economic_rationale_score=8.5,
            data_authenticity_score=8.0,
            historical_coverage_score=7.5,
            implementation_simplicity_score=6.0,
            execution_feasibility_score=6.5,
            statistical_testability_score=8.0,
            infrastructure_affordability_score=7.0,
            expected_research_value_score=8.0,
        )

        domain_b = ResearchDomainFeasibilityAssessment(
            domain_id="DOMAIN_B_REAL_EXECUTION_MICROSTRUCTURE",
            domain_name="Real Execution Microstructure & Order-Book Dynamics",
            target_phenomena="Order-book depth (L2/L3), bid-ask spread expansion, queue position dynamics, toxic flow detection, and order-flow imbalance (OFI).",
            economic_rationale="OHLCV candles conceal the true mechanism of transaction costs: passive orders are adversely filled when informed flow crosses the spread, while trending moves leave limit orders unfilled.",
            authentic_data_sources=[
                "Binance public monthly aggTrades archives",
                "Binance real-time depth stream (requires live collector)",
                "Historical L2/L3 order book data vendors (Tardis.dev, Kaiko - costly)",
            ],
            data_authenticity_and_verification="Very High if acquired, but public archival repositories rarely store full historical tick-by-tick depth snapshots for free.",
            historical_coverage_and_depth="Low for historical L2 depth without commercial expenditure; Medium for aggTrades archives.",
            microstructure_and_execution_realism="Highest scientific realism; completely eliminates the synthetic Maker Fill Paradox and reveals true queue dynamics.",
            pitfalls_and_delusions_to_avoid="Assuming queue priority without timestamp-priority modeling; assuming zero latency to cancel orders ahead of incoming toxic sweeps.",
            economic_rationale_score=9.5,
            data_authenticity_score=7.0,
            historical_coverage_score=5.0,
            implementation_simplicity_score=4.0,
            execution_feasibility_score=6.0,
            statistical_testability_score=8.5,
            infrastructure_affordability_score=4.0,  # High disk/network overhead
            expected_research_value_score=8.5,
        )

        domain_c = ResearchDomainFeasibilityAssessment(
            domain_id="DOMAIN_C_PERPETUAL_FUNDING_AND_BASIS",
            domain_name="Perpetual Funding Settlement & Spot-Perp Basis",
            target_phenomena="Cash-and-carry basis, persistent positive funding yield in bull regimes, spot/perp basis divergence, and funding settlement mechanics (8h intervals).",
            economic_rationale="In crypto markets, perpetual futures trade at an structural premium during bull runs because retail traders demand leveraged upside. Long perpetuals pay shorts an 8h funding fee. A Delta-neutral Spot-long / Perp-short position captures this funding fee with near-zero directional market risk.",
            authentic_data_sources=[
                "Binance Data Vision: data/futures/um/monthly/fundingRate/",
                "Binance Data Vision: data/futures/um/monthly/klines/premiumIndex/",
                "Binance Data Vision: data/futures/um/monthly/klines/indexPriceKlines/",
            ],
            data_authenticity_and_verification="Maximum (10/10). Official Binance Data Vision provides complete historical 8-hour funding rate settlement tables and premium index klines with official SHA-256 checksums.",
            historical_coverage_and_depth="Maximum (10/10). Multi-year official historical records for BTCUSDT, ETHUSDT, SOLUSDT dating back to contract genesis.",
            microstructure_and_execution_realism="High. Trades occur only once every 8 hours or upon basis widening/narrowing. Turnover is orders of magnitude lower than intraday directional churning.",
            pitfalls_and_delusions_to_avoid="Assuming zero liquidation risk on the short perpetual leg; conflating Spot cash with derivative margin; ignoring negative funding regimes (bear markets).",
            economic_rationale_score=9.5,
            data_authenticity_score=10.0,
            historical_coverage_score=10.0,
            implementation_simplicity_score=8.5,
            execution_feasibility_score=8.5,
            statistical_testability_score=9.5,
            infrastructure_affordability_score=9.5,
            expected_research_value_score=9.5,
        )

        domains = [domain_a, domain_b, domain_c]
        # Rank by total score descending
        ranked = sorted(domains, key=lambda d: d.total_score, reverse=True)
        ranked_ids = [d.domain_id for d in ranked]
        top_domain = ranked[0].domain_id

        narrative = (
            "STRATEGIC RECOMMENDATION: Sprints 09.20 through 09.32 conclusively demonstrated that "
            "pure directional price-action timing (H1-H7, B3, B5, CS1, CP1-4, RC1-3) suffers from "
            "whipsaw friction, execution delay, and fee drag, failing to beat simple passive asset allocation. "
            "The most promising and scientifically robust path forward is DOMAIN C: PERPETUAL FUNDING & BASIS. "
            "It offers 100% authentic, free public historical settlement data on Binance Data Vision, "
            "operates at an 8-hour horizon with minimal turnover, and exploits a structural economic transfer "
            "(leverage premium paid by perpetual speculators to liquidity providers) rather than attempting "
            "to forecast noisy directional price movements."
        )

        return ResearchRoadmapReport(
            domains=domains,
            ranked_domain_ids=ranked_ids,
            top_recommended_domain=top_domain,
            strategic_roadmap_narrative=narrative,
        )

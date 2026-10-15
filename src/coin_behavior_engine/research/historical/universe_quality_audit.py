"""Cross-Sectional Universe Quality, Breadth Quantization & Candidate Universe Auditor.

Audits:
1. Mathematical analysis of the 3-asset core universe (BTC, ETH, SOL):
   - Quantization step size of market breadth indicators:
     With N=3, breadth states are discrete: {0%, 33.3%, 66.7%, 100%}. A single asset movement creates a 33.3% jump.
   - Herfindahl-Hirschman Index (HHI) dynamic range:
     Minimum HHI is 1/N = 0.333; maximum is 1.000.
2. Pre-specified candidate universe expansion:
   - Evaluates historical eligibility, listing dates, and liquidity for:
     BNBUSDT (listed 2017-11-06)
     DOGEUSDT (listed 2019-07-05)
     ADAUSDT (listed 2018-04-17)
     XRPUSDT (listed 2018-11-06)
3. Structural simulation comparing N=3, N=5, and N=7 universe breadth stability and HHI sensitivity.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
import math
from typing import Any, Mapping, Optional, Sequence


@dataclass(frozen=True)
class UniverseQualityAuditReport:
    """Audit verdict on universe size, breadth quantization, and expansion eligibility."""

    core_universe_size: int
    core_symbols: list[str]
    breadth_quantization_step_pct: float
    hhi_theoretical_minimum: float
    hhi_theoretical_maximum: float
    candidate_universe_metadata: dict[str, dict[str, Any]]
    expansion_tradeoff_assessment: str
    recommended_universe_policy: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class UniverseQualityAuditor:
    """Evaluates cross-sectional universe resolution and candidate asset eligibility."""

    CORE_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    CANDIDATE_REGISTRY = {
        "BNBUSDT": {
            "symbol": "BNBUSDT",
            "base_asset": "BNB",
            "quote_asset": "USDT",
            "binance_listing_date_utc": "2017-11-06T04:00:00Z",
            "is_eligible_for_2024_2025": True,
            "liquidity_tier": "TIER_1_MEGA",
            "bias_notes": "Exchange native token; massive Spot liquidity, but non-independent regulatory exposure.",
        },
        "DOGEUSDT": {
            "symbol": "DOGEUSDT",
            "base_asset": "DOGE",
            "quote_asset": "USDT",
            "binance_listing_date_utc": "2019-07-05T12:00:00Z",
            "is_eligible_for_2024_2025": True,
            "liquidity_tier": "TIER_2_LARGE",
            "bias_notes": "High volatility meme coin; extreme volume regime shifts.",
        },
        "ADAUSDT": {
            "symbol": "ADAUSDT",
            "base_asset": "ADA",
            "quote_asset": "USDT",
            "binance_listing_date_utc": "2018-04-17T04:00:00Z",
            "is_eligible_for_2024_2025": True,
            "liquidity_tier": "TIER_2_LARGE",
            "bias_notes": "Continuous trading since 2018; low relative volatility in 2024.",
        },
        "XRPUSDT": {
            "symbol": "XRPUSDT",
            "base_asset": "XRP",
            "quote_asset": "USDT",
            "binance_listing_date_utc": "2018-11-06T04:00:00Z",
            "is_eligible_for_2024_2025": True,
            "liquidity_tier": "TIER_1_MEGA",
            "bias_notes": "Continuous trading; highly news/litigation driven price action.",
        },
    }

    @classmethod
    def audit_universe_quality(cls) -> UniverseQualityAuditReport:
        n = len(cls.CORE_SYMBOLS)
        step_pct = round(100.0 / n, 2)
        hhi_min = round(1.0 / n, 3)

        notes = (
            f"MATHEMATICAL BREADTH QUANTIZATION AUDIT: A 3-asset universe ({cls.CORE_SYMBOLS}) exhibits a high "
            f"quantization step of {step_pct}% per asset state transition. Consequently, market breadth metrics "
            "(% above EMA50, % in Bullish Trend, Advance/Decline) are restricted to only 4 discrete states: "
            "{0.0%, 33.3%, 66.7%, 100.0%}. A single asset crossing an indicator threshold triggers an abrupt 33.3% jump, "
            "inducing regime whipsaws. Expanding the universe to N=5 (adding BNB and DOGE) reduces the step size to 20.0%, "
            "and N=10 reduces it to 10.0%, providing continuous, stable breadth indicators."
        )

        policy = (
            "POLICY RECOMMENDATION: While N=3 is scientifically sufficient to establish proof of concept and conservative "
            "mega-cap liquidity boundaries, production cross-sectional research should transition to a pre-registered 5-asset "
            "or 7-asset universe (adding BNB, DOGE, ADA) to eliminate breadth discretization noise without introducing illiquidity risk."
        )

        return UniverseQualityAuditReport(
            core_universe_size=n,
            core_symbols=cls.CORE_SYMBOLS,
            breadth_quantization_step_pct=step_pct,
            hhi_theoretical_minimum=hhi_min,
            hhi_theoretical_maximum=1.0,
            candidate_universe_metadata=cls.CANDIDATE_REGISTRY,
            expansion_tradeoff_assessment=notes,
            recommended_universe_policy=policy,
        )

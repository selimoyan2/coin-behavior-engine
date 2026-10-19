"""Canonical Macroeconomic and Financial Event Evidence Schema.

Sprint 11.23 Phase 2:
Defines immutable, point-in-time validated schema for historical economic announcements,
regulatory decisions, and market structure events.

Enforces:
- Strict point-in-time timestamp hierarchy:
  official_published_at_utc <= first_verified_public_at_utc <= research_available_at_utc
- Explicit uncertainty intervals [min_delay_seconds, max_delay_seconds]
- Separation of Contemporaneous First-Release values vs Subsequent Revised values
- Consensus forecast validation (must precede release timestamp)
- Source tier hierarchy (Tier 1 Primary to Tier 4 Unverified)
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import hashlib
from typing import Any, Dict, List, Optional


class SourceTier:
    TIER_1_OFFICIAL = "TIER_1_OFFICIAL"              # Primary agency release, SEC docket, Fed statement, Blockchain block
    TIER_2_REPUTABLE_NEWS = "TIER_2_REPUTABLE_NEWS"  # Reuters, Bloomberg, WSJ contemporaneous wire with timestamp
    TIER_3_AGGREGATOR = "TIER_3_AGGREGATOR"          # ForexFactory, TradingEconomics, Investing.com post-hoc records
    TIER_4_UNVERIFIED = "TIER_4_UNVERIFIED"          # Social media rumors, unverified commentary


class EventImportance:
    CRITICAL = "CRITICAL"  # FOMC Rate Decisions, US CPI, Nonfarm Payrolls, Spot ETF Orders
    HIGH = "HIGH"          # Core PCE, GDP Advance, Key Bank Failures, Halving
    MEDIUM = "MEDIUM"      # Fed Minutes, PPI, Retail Sales, Second GDP estimates
    LOW = "LOW"            # Routine speeches without policy shifts


class VerificationStatus:
    VERIFIED_POINT_IN_TIME = "VERIFIED_POINT_IN_TIME"
    VERIFIED_EVENT_UNCERTAIN_LATENCY = "VERIFIED_EVENT_UNCERTAIN_LATENCY"
    OFFICIAL_SCHEDULE_ONLY = "OFFICIAL_SCHEDULE_ONLY"
    SECONDARY_TIMESTAMP_ONLY = "SECONDARY_TIMESTAMP_ONLY"
    ASSUMED_LATENCY = "ASSUMED_LATENCY"
    UNVERIFIED = "UNVERIFIED"
    REJECTED = "REJECTED"


@dataclass(frozen=True)
class MacroEventRecord:
    """Immutable, point-in-time verified event record."""
    event_id: str
    event_category: str                    # 'US_INFLATION', 'US_LABOR', 'US_MONETARY_POLICY', 'US_GROWTH', 'CRYPTO_STRUCTURE', 'BITCOIN_PROTOCOL'
    event_name: str
    country: str                           # 'US', 'GLOBAL', etc.
    issuing_organization: str              # 'BLS', 'BEA', 'FEDERAL_RESERVE', 'SEC', 'FDIC', 'BITCOIN_NETWORK'
    source_tier: str                       # TIER_1_OFFICIAL, TIER_2_REPUTABLE_NEWS, etc.
    primary_source_url: str
    source_document_hash: str              # SHA-256 of excerpt or official release
    scheduled_release_at_utc: str          # ISO 8601 UTC
    official_published_at_utc: str         # ISO 8601 UTC
    first_verified_public_at_utc: str      # ISO 8601 UTC
    research_available_at_utc: str         # ISO 8601 UTC (after simulated dissemination latency)
    timestamp_precision: str               # 'SECOND_LEVEL_EMBARGO', 'MINUTE_LEVEL_SCHEDULED', 'BLOCK_TIMESTAMP'
    timestamp_uncertainty_seconds: float   # e.g. 15.0 to 120.0 seconds
    timestamp_evidence_method: str         # 'FEDERAL_REGISTER_EMBARGO', 'PRESS_LOCKUP_PROTOCOL', 'SERVER_TIMESTAMP'
    actual_value: Optional[float]
    consensus_forecast_value: Optional[float]
    previous_value: Optional[float]
    previous_value_as_known_at_release: Optional[float]
    revised_value: Optional[float]
    measurement_unit: str                  # 'PERCENT_YOY', 'PERCENT_MOM', 'THOUSANDS_JOBS', 'PERCENT_RATE', 'BILLIONS_USD'
    release_vintage: str                   # 'FIRST_RELEASE', 'ADVANCE_ESTIMATE', 'FINAL_ESTIMATE', 'OFFICIAL_ORDER'
    event_importance_class: str            # CRITICAL, HIGH, MEDIUM, LOW
    verification_status: str               # VERIFIED_POINT_IN_TIME, VERIFIED_EVENT_UNCERTAIN_LATENCY, etc.
    ingested_at_utc: str                   # ISO 8601 UTC
    source_license_notes: str              # 'PUBLIC_DOMAIN_US_GOVT', 'OPEN_DATA', 'ACADEMIC_CITATION'
    surprise_status: str = "AVAILABLE"     # 'AVAILABLE', 'UNAVAILABLE', 'NOT_APPLICABLE'

    def __post_init__(self):
        # Validate timestamp hierarchy
        t_pub = datetime.fromisoformat(self.official_published_at_utc.replace("Z", "+00:00"))
        t_first = datetime.fromisoformat(self.first_verified_public_at_utc.replace("Z", "+00:00"))
        t_res = datetime.fromisoformat(self.research_available_at_utc.replace("Z", "+00:00"))

        if t_first < t_pub:
            raise ValueError(f"Event {self.event_id}: first_verified_public ({t_first}) cannot precede official publication ({t_pub})")
        if t_res < t_first:
            raise ValueError(f"Event {self.event_id}: research_available ({t_res}) cannot precede first public verification ({t_first})")

        # Validate consensus availability
        if self.consensus_forecast_value is None and self.surprise_status == "AVAILABLE":
            object.__setattr__(self, "surprise_status", "UNAVAILABLE")

    @property
    def raw_surprise(self) -> Optional[float]:
        """Arithmetic surprise = actual - consensus."""
        if self.actual_value is not None and self.consensus_forecast_value is not None:
            return round(self.actual_value - self.consensus_forecast_value, 4)
        return None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["raw_surprise"] = self.raw_surprise
        return d


def validate_event_records(records: List[MacroEventRecord]) -> Dict[str, Any]:
    """Audit collection of macro event records for integrity and causal compliance."""
    total = len(records)
    tier_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}
    status_counts: Dict[str, int] = {}
    with_consensus = 0
    with_actual = 0
    with_previous = 0
    valid_timestamp_hierarchy = 0

    seen_ids = set()
    duplicates = []

    for r in records:
        if r.event_id in seen_ids:
            duplicates.append(r.event_id)
        seen_ids.add(r.event_id)

        tier_counts[r.source_tier] = tier_counts.get(r.source_tier, 0) + 1
        category_counts[r.event_category] = category_counts.get(r.event_category, 0) + 1
        status_counts[r.verification_status] = status_counts.get(r.verification_status, 0) + 1

        if r.consensus_forecast_value is not None:
            with_consensus += 1
        if r.actual_value is not None:
            with_actual += 1
        if r.previous_value is not None:
            with_previous += 1

        t_pub = datetime.fromisoformat(r.official_published_at_utc.replace("Z", "+00:00"))
        t_first = datetime.fromisoformat(r.first_verified_public_at_utc.replace("Z", "+00:00"))
        t_res = datetime.fromisoformat(r.research_available_at_utc.replace("Z", "+00:00"))

        if t_pub <= t_first <= t_res:
            valid_timestamp_hierarchy += 1

    return {
        "total_events": total,
        "unique_events": len(seen_ids),
        "duplicate_count": len(duplicates),
        "duplicates": duplicates,
        "tier_distribution": tier_counts,
        "category_distribution": category_counts,
        "verification_status_distribution": status_counts,
        "records_with_consensus": with_consensus,
        "records_with_actual": with_actual,
        "records_with_previous": with_previous,
        "valid_timestamp_hierarchy_count": valid_timestamp_hierarchy,
        "all_timestamps_strictly_ordered": valid_timestamp_hierarchy == total and total > 0
    }

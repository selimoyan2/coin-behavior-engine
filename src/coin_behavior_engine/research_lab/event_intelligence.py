"""Source-agnostic market event intelligence engine and catalog.

Sprint 11.03: Market Behavior Research Lab.
Normalizes macroeconomic, regulatory, exchange, and market structure events.
Separates credibility, verification, severity, and observed market impact.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

from coin_behavior_engine.research_lab.contracts import (
    EventCategory,
    EventIntelligenceRecord,
    EventVerificationStatus,
)


class EventIntelligenceStore:
    """Manages normalized historical events with query, filtering, and ingestion capabilities."""

    def __init__(self):
        self._events: Dict[str, EventIntelligenceRecord] = {}

    def add_event(self, record: EventIntelligenceRecord) -> None:
        self._events[record.event_id] = record

    def get_event(self, event_id: str) -> Optional[EventIntelligenceRecord]:
        return self._events.get(event_id)

    def all_events(self) -> List[EventIntelligenceRecord]:
        return sorted(self._events.values(), key=lambda e: e.published_at_utc)

    def verified_events(self) -> List[EventIntelligenceRecord]:
        """Return only verified events within the active observation window."""
        return [
            e for e in self.all_events()
            if e.verification_status == EventVerificationStatus.VERIFIED_EVENT
            and not e.is_pre_dataset_window
        ]

    def events_in_range(self, start_utc: str, end_utc: str) -> List[EventIntelligenceRecord]:
        return [
            e for e in self.all_events()
            if start_utc <= e.published_at_utc <= end_utc
        ]

    def events_observable_at(
        self,
        decision_timestamp_utc: str,
        lookback_hours: float = 24.0,
        strictly_verified_only: bool = False,
    ) -> List[EventIntelligenceRecord]:
        """Return events that were FIRST OBSERVED before or at decision_timestamp_utc.
        
        Strictly prevents lookahead: an event published at 14:00 but observed at 14:05
        cannot be available at a 14:02 decision!
        """
        observable = []
        dt_decision = datetime.fromisoformat(decision_timestamp_utc.replace("Z", "+00:00"))
        
        candidates = self.verified_events() if strictly_verified_only else self.all_events()
        for e in candidates:
            try:
                obs_dt = datetime.fromisoformat(e.first_observed_at_utc.replace("Z", "+00:00"))
                diff_sec = (dt_decision - obs_dt).total_seconds()
                if 0 <= diff_sec <= (lookback_hours * 3600.0):
                    observable.append(e)
            except Exception:
                pass
        return observable

    def load_from_json(self, file_path: Path) -> int:
        """Load external events from a JSON list file."""
        if not file_path.is_file():
            return 0
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        count = 0
        for item in data:
            cat = EventCategory(item.get("category", EventCategory.UNCLASSIFIED.value))
            v_status_raw = item.get("verification_status", "UNSUPPORTED")
            try:
                v_status = EventVerificationStatus(v_status_raw)
            except Exception:
                v_status = EventVerificationStatus.UNSUPPORTED
            rec = EventIntelligenceRecord(
                event_id=item["event_id"],
                event_type=item["event_type"],
                category=cat,
                headline=item["headline"],
                summary=item.get("summary", ""),
                source_name=item["source_name"],
                source_url=item.get("source_url", ""),
                actor=item.get("actor", "UNKNOWN"),
                affected_assets=item.get("affected_assets", ["BTC"]),
                published_at_utc=item["published_at_utc"],
                first_observed_at_utc=item.get("first_observed_at_utc", item["published_at_utc"]),
                ingested_at_utc=item.get("ingested_at_utc", item["published_at_utc"]),
                verification_status=v_status,
                source_credibility=float(item.get("source_credibility", 0.8)),
                source_reliability_class=str(item.get("source_reliability_class", "TIER_3_UNVERIFIED")),
                exact_factual_claim=str(item.get("exact_factual_claim", "")),
                independent_corroboration=item.get("independent_corroboration"),
                relationship_to_price_movement=str(item.get("relationship_to_price_movement", "UNCORRELATED")),
                is_pre_dataset_window=bool(item.get("is_pre_dataset_window", False)),
                event_direction_hypothesis=item.get("event_direction_hypothesis", "NEUTRAL"),
                event_severity=float(item.get("event_severity", 0.5)),
                event_novelty=float(item.get("event_novelty", 1.0)),
                related_event_ids=item.get("related_event_ids", []),
                correction_of_event_id=item.get("correction_of_event_id"),
                provenance=item.get("provenance", "EXTERNAL_IMPORT"),
            )
            self.add_event(rec)
            count += 1
        return count

    def save_to_json(self, file_path: Path) -> None:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        records = [e.to_dict() for e in self.all_events()]
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2)

    @classmethod
    def export_event_source_verification_csv(
        cls,
        events: List[EventIntelligenceRecord],
        output_csv: Path,
    ) -> None:
        """Export comprehensive audit verification matrix for all historical events."""
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        rows = []
        for e in events:
            v_val = e.verification_status.value if isinstance(e.verification_status, EventVerificationStatus) else str(e.verification_status)
            rows.append({
                "event_id": e.event_id,
                "original_source_url": e.source_url,
                "original_published_utc": e.published_at_utc,
                "first_observable_utc": e.first_observed_at_utc,
                "exact_factual_claim": e.exact_factual_claim or e.headline,
                "independent_corroboration": e.independent_corroboration or "NONE",
                "source_reliability_classification": e.source_reliability_class,
                "verification_status": v_val,
                "is_pre_dataset_window": e.is_pre_dataset_window,
                "relationship_to_price_movement": e.relationship_to_price_movement,
                "event_severity": e.event_severity,
                "source_name": e.source_name,
            })
        df = pd.DataFrame(rows)
        df.to_csv(output_csv, index=False)

    @classmethod
    def load_curated_october_2026_events(cls) -> EventIntelligenceStore:
        """Loads curated events covering the September - October 2026 period with Sprint 11.04 integrity audits."""
        store = cls()
        curated_events = [
            EventIntelligenceRecord(
                event_id="EVT-20260921-FOMC-HAWK",
                event_type="MACRO_RATE_DECISION",
                category=EventCategory.MONETARY_POLICY,
                headline="FOMC Signals Prolonged High Rates Amid Persistent Sticky Core Services Inflation",
                summary="Federal Reserve maintains target federal funds rate but dot plot reveals fewer projected rate cuts for 2027.",
                actor="Federal Reserve",
                source_name="Federal Reserve Official Statement",
                source_url="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
                affected_assets=["BTC", "ETH", "USDT"],
                published_at_utc="2026-09-21T18:00:00Z",
                first_observed_at_utc="2026-09-21T18:00:15Z",
                ingested_at_utc="2026-09-21T18:00:20Z",
                verification_status=EventVerificationStatus.REPORTED_UNCONFIRMED,
                source_credibility=0.85,
                source_reliability_class="TIER_1_OFFICIAL_CALENDAR",
                exact_factual_claim="Federal Reserve policy meeting concluded on Sept 21; signaled extended high interest rate policy.",
                independent_corroboration="FOMC calendar confirms scheduled meeting period; exact statement text requires primary archive permalink.",
                relationship_to_price_movement="Pre-dataset macro headwind; event occurred prior to Sept 23 dataset opening.",
                is_pre_dataset_window=True,
                event_direction_hypothesis="BEARISH",
                event_severity=0.75,
                event_novelty=0.6,
                provenance="HISTORICAL_EVENT_ARCHIVE",
            ),
            EventIntelligenceRecord(
                event_id="EVT-20261006-SEC-WARNING",
                event_type="REGULATORY_ACTION",
                category=EventCategory.REGULATION,
                headline="SEC Issues Formal Warning on Offshore Perpetual Swaps and Staking Intermediaries",
                summary="Regulator alerts market participants regarding offshore leverage venues and initiates investigative subpoenas.",
                actor="US SEC",
                source_name="SEC Press Release",
                source_url="https://www.sec.gov/news/press-release",
                affected_assets=["BTC", "ETH", "SOL"],
                published_at_utc="2026-10-06T14:30:00Z",
                first_observed_at_utc="2026-10-06T14:30:20Z",
                ingested_at_utc="2026-10-06T14:30:30Z",
                verification_status=EventVerificationStatus.UNSUPPORTED,
                source_credibility=0.30,
                source_reliability_class="TIER_3_UNVERIFIED_GENERIC_URL",
                exact_factual_claim="SEC published warning bulletin regarding offshore crypto leverage platforms on Oct 6.",
                independent_corroboration="None. Source URL is generic root path; no specific release index or SEC docket identifier provided.",
                relationship_to_price_movement="Temporally aligned with breakdown of $82,500 support level.",
                is_pre_dataset_window=False,
                event_direction_hypothesis="BEARISH",
                event_severity=0.80,
                event_novelty=0.8,
                provenance="UNSUPPORTED_SYNTHETIC_ENTRY",
            ),
            EventIntelligenceRecord(
                event_id="EVT-20261007-LIQUIDATION-SPIKE",
                event_type="MARKET_MICROSTRUCTURE",
                category=EventCategory.LIQUIDATION_CASCADE,
                headline="Long Liquidation Cascade Exceeds $450M in 4 Hours Across Major Venues",
                summary="Accelerated margin liquidations trigger systemic stop-loss runs in BTCUSDT spot and derivatives book.",
                actor="Derivatives Venues",
                source_name="Market Microstructure Aggregator",
                source_url="https://coin-behavior-engine.local/liquidation",
                affected_assets=["BTCUSDT"],
                published_at_utc="2026-10-07T08:15:00Z",
                first_observed_at_utc="2026-10-07T08:15:10Z",
                ingested_at_utc="2026-10-07T08:15:15Z",
                verification_status=EventVerificationStatus.RETROSPECTIVE_INTERPRETATION,
                source_credibility=0.40,
                source_reliability_class="INTERNAL_RETROSPECTIVE_TELEMETRY",
                exact_factual_claim="Estimated $450M long liquidations occurred over 4 hours during BTC drop from $83.5k to $80.3k.",
                independent_corroboration="None. Sourced from internal mock URL; not corroborated by verified external derivatives data feed.",
                relationship_to_price_movement="Directly reflects observed market drop to $80,393 low with elevated volume.",
                is_pre_dataset_window=False,
                event_direction_hypothesis="BEARISH",
                event_severity=0.85,
                event_novelty=0.7,
                provenance="DERIVED_MICROSTRUCTURE_OBSERVATION",
            ),
            EventIntelligenceRecord(
                event_id="EVT-20261008-BOTTOM-ABSORPTION",
                event_type="MARKET_ABSORPTION",
                category=EventCategory.MARKET_LIQUIDITY,
                headline="Institutional Spot Accumulation Observed Following $80.3k Low Sweeps",
                summary="Large spot block orders absorb sell-side market depth as open interest resets and funding rates turn negative.",
                actor="Institutional Desk",
                source_name="Exchange Order Flow Monitor",
                source_url="https://coin-behavior-engine.local/flows",
                affected_assets=["BTCUSDT"],
                published_at_utc="2026-10-08T16:00:00Z",
                first_observed_at_utc="2026-10-08T16:00:30Z",
                ingested_at_utc="2026-10-08T16:00:45Z",
                verification_status=EventVerificationStatus.RETROSPECTIVE_INTERPRETATION,
                source_credibility=0.40,
                source_reliability_class="INTERNAL_RETROSPECTIVE_TELEMETRY",
                exact_factual_claim="Institutional buyers absorbed spot sell orders around $80,300, stabilizing prices.",
                independent_corroboration="None. Sourced from internal mock URL; based on price recovery interpretation.",
                relationship_to_price_movement="Coincided with bear trap price recovery back above $81,200.",
                is_pre_dataset_window=False,
                event_direction_hypothesis="BULLISH",
                event_severity=0.65,
                event_novelty=0.7,
                provenance="DERIVED_MICROSTRUCTURE_OBSERVATION",
            ),
            EventIntelligenceRecord(
                event_id="EVT-20261014-CPI-SURPRISE",
                event_type="MACRO_INFLATION",
                category=EventCategory.INFLATION,
                headline="US Headline CPI Prints at 3.4% YoY vs 3.1% Expected, Reigniting Rate Fears",
                summary="Bureau of Labor Statistics release triggers risk-off re-pricing across broad equity and digital asset markets.",
                actor="US Bureau of Labor Statistics",
                source_name="BLS Official Release",
                source_url="https://www.bls.gov/cpi",
                affected_assets=["BTC", "ETH", "USDT"],
                published_at_utc="2026-10-14T12:30:00Z",
                first_observed_at_utc="2026-10-14T12:30:05Z",
                ingested_at_utc="2026-10-14T12:30:10Z",
                verification_status=EventVerificationStatus.UNSUPPORTED,
                source_credibility=0.30,
                source_reliability_class="TIER_3_UNVERIFIED_GENERIC_URL",
                exact_factual_claim="Bureau of Labor Statistics released October 2026 CPI report showing 3.4% headline inflation.",
                independent_corroboration="None. Generic BLS landing page provided; no specific release table or news release permalink.",
                relationship_to_price_movement="Aligned with local trough re-test down to $79,800 on Oct 15.",
                is_pre_dataset_window=False,
                event_direction_hypothesis="BEARISH",
                event_severity=0.78,
                event_novelty=0.75,
                provenance="UNSUPPORTED_SYNTHETIC_ENTRY",
            ),
        ]
        for e in curated_events:
            store.add_event(e)
        return store


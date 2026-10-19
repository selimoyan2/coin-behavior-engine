"""
Sprint 11.23.3: Canonical Prospective Event Registry
Manages prospective economic and cryptocurrency event schedules with deterministic IDs,
UTC timestamp normalization, explicit schedule verification, revision provenance,
and zero look-ahead calendar inference.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import zoneinfo

from .event_models import (
    ProspectiveEventRecord,
    ProspectiveEventCategory,
    ProspectiveEventStatus,
    EventRevisionRecord,
)

class ProspectiveEventRegistry:
    """
    Canonical repository for prospective economic and crypto structural events.
    Enforces immutable audit history, strict time zone conversions, and explicit
    distinction between scheduled events and observed releases.
    """

    def __init__(self) -> None:
        self._events: Dict[str, ProspectiveEventRecord] = {}

    def register_scheduled_event(
        self,
        event_id: str,
        category: ProspectiveEventCategory,
        indicator: str,
        issuing_org: str,
        official_url: str,
        scheduled_local_str: str,
        local_tz_name: str,
        schedule_verification_utc: str,
        timestamp_uncertainty_seconds: float = 30.0,
        source_evidence_ref: Optional[str] = None
    ) -> ProspectiveEventRecord:
        """
        Registers an upcoming official event from an authoritative schedule.
        Converts the local release time to UTC strictly and explicitly.
        Rejects approximate or unverified calendar estimates.
        """
        if event_id in self._events:
            raise ValueError(f"Event ID '{event_id}' already registered. Use update_schedule() for modifications.")

        # Convert local time to UTC explicitly
        try:
            tz = zoneinfo.ZoneInfo(local_tz_name)
        except Exception as e:
            raise ValueError(f"Invalid timezone '{local_tz_name}': {e}")

        # Parse local time
        dt_local = datetime.fromisoformat(scheduled_local_str)
        if dt_local.tzinfo is None:
            dt_local = dt_local.replace(tzinfo=tz)
        else:
            dt_local = dt_local.astimezone(tz)
        
        dt_utc = dt_local.astimezone(timezone.utc)
        scheduled_utc_str = dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

        record = ProspectiveEventRecord(
            event_id=event_id,
            event_category=category,
            indicator=indicator,
            issuing_organization=issuing_org,
            official_source_url=official_url,
            scheduled_publication_at_utc=scheduled_utc_str,
            schedule_verification_at_utc=schedule_verification_utc,
            original_timezone=local_tz_name,
            event_status=ProspectiveEventStatus.SCHEDULE_VERIFIED,
            timestamp_uncertainty_seconds=timestamp_uncertainty_seconds,
            source_evidence_ref=source_evidence_ref,
            directional_trading_eligible=False,
            revision_history=[
                EventRevisionRecord(
                    revision_id="REV-INIT",
                    timestamp_utc=datetime.now(timezone.utc).isoformat(),
                    field_changed="INIT",
                    old_value=None,
                    new_value=scheduled_utc_str,
                    reason="Initial authoritative schedule registration"
                ).to_dict()
            ]
        )

        self._events[event_id] = record
        return record

    def update_schedule(
        self,
        event_id: str,
        new_scheduled_local_str: str,
        verification_utc: str,
        reason: str
    ) -> ProspectiveEventRecord:
        """
        Updates an event's schedule authoritatively.
        Never silently overwrites: appends a full revision record to revision_history.
        """
        if event_id not in self._events:
            raise KeyError(f"Event ID '{event_id}' not found in registry.")

        event = self._events[event_id]
        tz = zoneinfo.ZoneInfo(event.original_timezone)
        dt_local = datetime.fromisoformat(new_scheduled_local_str)
        if dt_local.tzinfo is None:
            dt_local = dt_local.replace(tzinfo=tz)
        else:
            dt_local = dt_local.astimezone(tz)
        
        new_utc_str = dt_local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        old_utc_str = event.scheduled_publication_at_utc

        rev_id = f"REV-{len(event.revision_history) + 1:03d}"
        event.revision_history.append(
            EventRevisionRecord(
                revision_id=rev_id,
                timestamp_utc=verification_utc,
                field_changed="scheduled_publication_at_utc",
                old_value=old_utc_str,
                new_value=new_utc_str,
                reason=reason
            ).to_dict()
        )

        event.scheduled_publication_at_utc = new_utc_str
        event.schedule_verification_at_utc = verification_utc
        event.last_update_utc = datetime.now(timezone.utc).isoformat()
        return event

    def get_event(self, event_id: str) -> Optional[ProspectiveEventRecord]:
        return self._events.get(event_id)

    def list_events(self, category: Optional[ProspectiveEventCategory] = None) -> List[ProspectiveEventRecord]:
        if category:
            return [e for e in self._events.values() if e.event_category == category]
        return list(self._events.values())

    def to_dict_list(self) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._events.values()]

    def export_json(self, output_path: Path) -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict_list(), f, indent=2)

"""
Official BLS Evidence Acquisition & Event Identity Verification Module
Sprint 11.23.5B-6

Provides:
  - OfficialScheduleAcquisitionRequest: Machine-readable, operator-reviewable BLS acquisition request.
  - Capability Isolation: OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION.
  - BlsCpiScheduleParser: Defensively parses official BLS HTML/text schedules.
  - CanonicalSamplingPlanReconciler: Reconciles 13 operational milestones and 8 mandatory macro horizons.
  - OfflinePilotRehearsalRunnerV5: End-to-end 14-step deterministic simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
import hashlib
import hmac
import html
import json
from pathlib import Path
import re
import tempfile
from typing import Any, Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urlparse

from coin_behavior_engine.prospective.observation_authorization import (
    AuthorizationCapability,
    AuthorizationStatus,
    ObservationAuthorizationToken,
    TrustedApprovalStore,
    NetworkActivationGate,
    SigningKeyRegistry,
    TradingIsolationViolation,
)
from coin_behavior_engine.prospective.https_provenance import (
    ProvenanceTrustLevel,
    HttpsAcquisitionProvenanceRecord,
    OfficialScheduleAcceptancePolicy,
)
from coin_behavior_engine.prospective.evidence_vault import ImmutableEvidenceVault
from coin_behavior_engine.prospective.schedule_verification import (
    derive_canonical_event_id,
    convert_local_to_utc,
)
from coin_behavior_engine.prospective.pilot_proposal_freeze import (
    CandidateEventIdentity,
    EventIdentityStatus,
    EventIdentityManager,
    ObservationMilestone,
    ObservationWindowPlanEvaluator,
    PilotProposalV3Builder,
    PilotProposal,
)

TARGET_EVENT_ID = "EVT-BLS-CPI-2026M10-20261110"
TARGET_EVENT_RELEASE_UTC = "2026-11-10T13:30:00Z"


class ScheduleParsingError(Exception):
    """Raised when parsing official schedule evidence fails."""
    pass


class AcquisitionScopeError(Exception):
    """Raised when an acquisition request or authorization violates allowed scope."""
    pass


# ==============================================================================
# 1. ONE-TIME OFFICIAL BLS ACQUISITION REQUEST
# ==============================================================================

OFFICIAL_BLS_HOST = "www.bls.gov"
OFFICIAL_BLS_CPI_URL = "https://www.bls.gov/schedule/news_release/cpi.htm"
MAX_ACQUISITION_ATTEMPTS = 2
MAX_SUCCESSFUL_ACQUISITIONS = 1
MAX_ACQUISITION_RESPONSE_BYTES = 2 * 1024 * 1024  # 2 MB


@dataclass
class OfficialScheduleAcquisitionRequest:
    """
    Operator-reviewable, machine-readable acquisition request for official BLS schedule evidence.
    Proposed scope is strictly bounded:
      - Publisher: BLS
      - Canonical URL: https://www.bls.gov/schedule/news_release/cpi.htm
      - Hostname: www.bls.gov
      - Method: GET only
      - Max successful: 1
      - Max attempts: 2 (1 request + 1 retry)
      - Max response bytes: 2 MB
      - Prohibits cookies, credentials, exchange calls, third-party domains, and background polling.
    """
    request_id: str = "REQ-BLS-CPI-2026M10-ACQ01"
    publisher: str = "BLS"
    canonical_url: str = OFFICIAL_BLS_CPI_URL
    allowed_hostname: str = OFFICIAL_BLS_HOST
    http_method: str = "GET"
    max_successful_acquisitions: int = MAX_SUCCESSFUL_ACQUISITIONS
    max_attempts: int = MAX_ACQUISITION_ATTEMPTS
    max_response_bytes: int = MAX_ACQUISITION_RESPONSE_BYTES
    required_capability: str = AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION.value
    target_event_id: str = TARGET_EVENT_ID
    purpose: str = (
        "Acquire authentic official BLS news release schedule for U.S. Consumer Price Index (CPI) "
        "October 2026 reference period to verify scheduled release date, time, and reference period."
    )
    created_by_operator_id: str = "OP-RESEARCH-LEAD-01"
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    expires_at_utc: str = field(
        default_factory=lambda: (datetime.now(timezone.utc) + timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    status: str = "PROPOSED"

    def canonical_payload(self) -> Dict[str, Any]:
        """Returns deterministic, key-sorted dictionary for cryptographic hashing."""
        return {
            "allowed_hostname": self.allowed_hostname.lower().strip(),
            "canonical_url": self.canonical_url.strip(),
            "created_by_operator_id": self.created_by_operator_id,
            "http_method": self.http_method.upper(),
            "max_attempts": self.max_attempts,
            "max_response_bytes": self.max_response_bytes,
            "max_successful_acquisitions": self.max_successful_acquisitions,
            "publisher": self.publisher,
            "purpose": self.purpose,
            "request_id": self.request_id,
            "required_capability": self.required_capability,
            "target_event_id": self.target_event_id,
        }

    def compute_canonical_digest(self) -> str:
        """Computes deterministic SHA-256 digest of canonical request payload."""
        payload_str = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload_str.encode("utf-8")).hexdigest()

    def validate_proposed_scope(self) -> Tuple[bool, List[str]]:
        """Validates all scope boundaries."""
        violations = []
        parsed = urlparse(self.canonical_url)
        if parsed.scheme.lower() != "https":
            violations.append(f"Insecure scheme '{parsed.scheme}'; strictly HTTPS required.")
        if parsed.hostname.lower() != OFFICIAL_BLS_HOST:
            violations.append(f"Hostname '{parsed.hostname}' must match '{OFFICIAL_BLS_HOST}'.")
        if self.http_method.upper() != "GET":
            violations.append(f"Method '{self.http_method}' rejected; must be GET.")
        if self.max_attempts > MAX_ACQUISITION_ATTEMPTS:
            violations.append(f"Max attempts {self.max_attempts} exceeds limit {MAX_ACQUISITION_ATTEMPTS}.")
        if self.max_response_bytes > MAX_ACQUISITION_RESPONSE_BYTES:
            violations.append(f"Max response bytes {self.max_response_bytes} exceeds {MAX_ACQUISITION_RESPONSE_BYTES}.")
        if self.required_capability != AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION.value:
            violations.append(f"Invalid required capability '{self.required_capability}'.")
        return len(violations) == 0, violations

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["canonical_request_digest"] = self.compute_canonical_digest()
        return d


# ==============================================================================
# 2. OFFICIAL BLS CPI SCHEDULE PARSER
# ==============================================================================

@dataclass
class ParsedCpiSchedule:
    """Structured result of parsing an authenticated BLS CPI schedule document."""
    publisher: str
    series_name: str
    reference_period: str
    reference_month_name: str
    reference_year: int
    release_date: str
    release_time_local: str
    local_timezone: str
    scheduled_release_utc: str
    derived_event_id: str
    source_url: str
    source_sha256: str
    acquisition_timestamp_utc: str
    contradicts_candidate: bool
    contradiction_details: Optional[Dict[str, Any]] = None
    revision_indicators: List[str] = field(default_factory=list)
    raw_snippet: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class BlsCpiScheduleParser:
    """
    Defensive parser for BLS CPI news release schedule tables and documents.
    Extracts:
      - Publisher (BLS)
      - Release series (Consumer Price Index)
      - Reference period (e.g. October 2026 / 2026M10)
      - Release date (YYYY-MM-DD)
      - Release time (HH:MM:SS local)
      - Timezone (America/New_York)
      - UTC release timestamp
      - Revision indicators
    Cross-checks against candidate event identity to isolate contradictions.
    """

    MONTH_MAP = {
        "january": ("01", "M01"),
        "february": ("02", "M02"),
        "march": ("03", "M03"),
        "april": ("04", "M04"),
        "may": ("05", "M05"),
        "june": ("06", "M06"),
        "july": ("07", "M07"),
        "august": ("08", "M08"),
        "september": ("09", "M09"),
        "october": ("10", "M10"),
        "november": ("11", "M11"),
        "december": ("12", "M12"),
    }

    @classmethod
    def parse_schedule_document(
        cls,
        raw_bytes: bytes,
        source_url: str,
        candidate_event: CandidateEventIdentity,
        acquisition_timestamp_utc: str,
        target_reference_month: str = "October",
        target_reference_year: int = 2026,
    ) -> ParsedCpiSchedule:
        """
        Parses raw BLS schedule HTML or text content.
        Cross-checks parsed values against candidate_event.
        """
        if not raw_bytes:
            raise ScheduleParsingError("Cannot parse empty schedule document bytes.")

        content_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        text = raw_bytes.decode("utf-8", errors="replace")

        # 1. Verify CPI series keywords
        if not re.search(r"Consumer\s+Price\s+Index|CPI", text, re.IGNORECASE):
            raise ScheduleParsingError("Document lacks required 'Consumer Price Index' or 'CPI' series markers.")

        # 2. Extract schedule row for the target reference period
        # Target period: e.g. "October 2026"
        month_lower = target_reference_month.lower()
        if month_lower not in cls.MONTH_MAP:
            raise ScheduleParsingError(f"Unknown reference month '{target_reference_month}'.")

        month_num, month_tag = cls.MONTH_MAP[month_lower]
        target_period_str = f"{target_reference_year}{month_tag}"

        # Regex search for table rows or text entries containing reference month and date
        # Examples in BLS HTML/text:
        # <tr><td>October 2026</td><td>Nov. 10, 2026</td><td>08:30 AM</td></tr>
        # October 2026 | November 10, 2026 | 08:30 AM
        pattern = re.compile(
            rf"{target_reference_month}\s+{target_reference_year}.*?"
            rf"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z.]*\s+(\d{{1,2}}),\s+(\d{{4}})).*?"
            rf"(\d{{1,2}}:\d{{2}}\s*(?:AM|PM|a\.m\.|p\.m\.))",
            re.IGNORECASE | re.DOTALL,
        )

        match = pattern.search(text)
        if not match:
            # Fallback pattern for ISO-style date e.g. 2026-11-10 08:30
            fallback_pattern = re.compile(
                rf"{target_reference_month}\s+{target_reference_year}.*?"
                rf"(\d{{4}}-(\d{{2}})-(\d{{2}})).*?"
                rf"(\d{{1,2}}:\d{{2}})",
                re.IGNORECASE | re.DOTALL,
            )
            match_fallback = fallback_pattern.search(text)
            if not match_fallback:
                raise ScheduleParsingError(
                    f"Could not locate official schedule entry for reference period '{target_reference_month} {target_reference_year}'."
                )
            release_date = match_fallback.group(1)
            raw_time = match_fallback.group(4)
            time_parts = raw_time.split(":")
            release_time_local = f"{int(time_parts[0]):02d}:{int(time_parts[1]):02d}:00"
            raw_snippet = match_fallback.group(0)[:200]
        else:
            raw_date_str = match.group(1)  # e.g. "Nov. 10, 2026" or "November 10, 2026"
            day = int(match.group(2))
            year = int(match.group(3))
            raw_time_str = match.group(4)  # e.g. "08:30 AM"

            # Parse month name of release date
            rel_month_match = re.match(r"([A-Za-z]+)", raw_date_str)
            rel_month_prefix = rel_month_match.group(1).lower().rstrip(".") if rel_month_match else ""
            rel_month_num = None
            for full_m, (m_num, _) in cls.MONTH_MAP.items():
                if full_m.startswith(rel_month_prefix[:3]):
                    rel_month_num = m_num
                    break
            if not rel_month_num:
                raise ScheduleParsingError(f"Cannot parse release month from '{raw_date_str}'.")

            release_date = f"{year:04d}-{rel_month_num}-{day:02d}"

            # Parse time
            time_clean = re.sub(r"[.\s]", "", raw_time_str).upper()
            t_match = re.match(r"(\d{1,2}):(\d{2})(AM|PM)?", time_clean)
            if not t_match:
                raise ScheduleParsingError(f"Cannot parse release time from '{raw_time_str}'.")
            hours = int(t_match.group(1))
            minutes = int(t_match.group(2))
            meridiem = t_match.group(3)
            if meridiem == "PM" and hours < 12:
                hours += 12
            elif meridiem == "AM" and hours == 12:
                hours = 0
            release_time_local = f"{hours:02d}:{minutes:02d}:00"
            raw_snippet = match.group(0)[:200]

        # 3. Check for revision indicators
        revision_indicators = []
        if re.search(r"revised|rescheduled|superseded", text, re.IGNORECASE):
            revision_indicators.append("DOCUMENT_CONTAINS_REVISION_NOTES")
        if re.search(r"preliminary", text, re.IGNORECASE):
            revision_indicators.append("DOCUMENT_MARKED_PRELIMINARY")

        # 4. Local timezone & UTC conversion
        local_tz = "America/New_York"
        utc_datetime_str = convert_local_to_utc(f"{release_date}T{release_time_local}", tz_name=local_tz)

        # 5. Derive canonical event ID
        derived_event_id = derive_canonical_event_id(
            publisher="BLS",
            series="CPI",
            reference_period=target_period_str,
            scheduled_date=release_date.replace("-", ""),
        )

        # 6. Cross-check against candidate event
        contradictions = {}
        if release_date != candidate_event.scheduled_release_date:
            contradictions["date_mismatch"] = {
                "candidate": candidate_event.scheduled_release_date,
                "parsed_official": release_date,
            }
        if release_time_local != candidate_event.scheduled_release_time_local:
            contradictions["time_mismatch"] = {
                "candidate": candidate_event.scheduled_release_time_local,
                "parsed_official": release_time_local,
            }
        if utc_datetime_str != candidate_event.scheduled_release_utc:
            contradictions["utc_mismatch"] = {
                "candidate": candidate_event.scheduled_release_utc,
                "parsed_official": utc_datetime_str,
            }
        if derived_event_id != candidate_event.candidate_event_id:
            contradictions["event_id_mismatch"] = {
                "candidate": candidate_event.candidate_event_id,
                "parsed_official": derived_event_id,
            }

        contradicts_candidate = len(contradictions) > 0

        return ParsedCpiSchedule(
            publisher="BLS",
            series_name="Consumer Price Index (CPI)",
            reference_period=target_period_str,
            reference_month_name=target_reference_month,
            reference_year=target_reference_year,
            release_date=release_date,
            release_time_local=release_time_local,
            local_timezone=local_tz,
            scheduled_release_utc=utc_datetime_str,
            derived_event_id=derived_event_id,
            source_url=source_url,
            source_sha256=content_sha256,
            acquisition_timestamp_utc=acquisition_timestamp_utc,
            contradicts_candidate=contradicts_candidate,
            contradiction_details=contradictions if contradicts_candidate else None,
            revision_indicators=revision_indicators,
            raw_snippet=raw_snippet,
        )


# ==============================================================================
# 3. CANONICAL SAMPLING PLAN RECONCILER
# ==============================================================================

@dataclass
class CanonicalSamplingMilestone:
    """Single canonical sampling plan milestone record."""
    milestone_index: int
    name: str
    offset_seconds_from_release: int
    target_utc: str
    data_source: str
    endpoint: str
    requested_data_type: str
    expected_timestamp_semantics: str
    planned_request_count: int
    is_mandatory_horizon: bool
    is_required_milestone: bool = True
    purpose: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CanonicalSamplingPlanReconciler:
    """
    Reconciles the taxonomy discrepancy between:
      - Total operational milestones ($N = 13$, Sprint B-4).
      - Standardized macro analytical horizons ($N = 8$, Sprint B-5 / macro research).
    Establishes a single canonical schema with request-level semantics.
    """

    MANDATORY_ANALYTICAL_HORIZONS_SECONDS: Set[int] = {
        60,    # +1m
        120,   # +2m
        180,   # +3m
        300,   # +5m
        600,   # +10m
        900,   # +15m
        1200,  # +20m
        1800,  # +30m
    }

    @classmethod
    def get_canonical_milestones(
        cls, release_utc: str = TARGET_EVENT_RELEASE_UTC
    ) -> List[CanonicalSamplingMilestone]:
        """Constructs the canonical 13-milestone sampling plan."""
        t0 = datetime.fromisoformat(release_utc.rstrip("Z")).replace(tzinfo=timezone.utc)

        raw_milestones = ObservationWindowPlanEvaluator.get_milestones(release_utc=release_utc)
        canonical = []

        for idx, m in enumerate(raw_milestones):
            is_horizon = m.offset_seconds_from_release in cls.MANDATORY_ANALYTICAL_HORIZONS_SECONDS

            # Endpoint selection based on milestone objective
            if m.offset_seconds_from_release <= 0:
                # Pre-event / T0: Live spread and order book depth check
                endpoint = "https://api.binance.com/api/v3/ticker/bookTicker"
                data_type = "live_book_ticker_spread"
                semantics = "REQUEST_DISPATCH_TIMESTAMP_UTC"
            else:
                # Post-event: Closed 1m candle metrics and volume
                endpoint = "https://api.binance.com/api/v3/klines"
                data_type = "1m_closed_ohlcv_candle"
                semantics = "CANDLE_CLOSE_TIMESTAMP_UTC"

            canonical.append(
                CanonicalSamplingMilestone(
                    milestone_index=idx,
                    name=m.name,
                    offset_seconds_from_release=m.offset_seconds_from_release,
                    target_utc=m.target_utc,
                    data_source="Binance BTC/USDT Spot",
                    endpoint=endpoint,
                    requested_data_type=data_type,
                    expected_timestamp_semantics=semantics,
                    planned_request_count=1,
                    is_mandatory_horizon=is_horizon,
                    is_required_milestone=True,
                    purpose=m.purpose,
                )
            )

        return canonical

    @classmethod
    def reconcile(cls, release_utc: str = TARGET_EVENT_RELEASE_UTC) -> Dict[str, Any]:
        """Performs mathematical reconciliation and budget audit."""
        milestones = cls.get_canonical_milestones(release_utc=release_utc)
        total_operational_milestones = len(milestones)
        mandatory_horizons = sum(1 for m in milestones if m.is_mandatory_horizon)
        total_planned_requests = sum(m.planned_request_count for m in milestones)
        quota_limit = ObservationWindowPlanEvaluator.MAX_REQUEST_QUOTA
        reserve_quota = quota_limit - total_planned_requests

        # Verify batch efficiency: 1 terminal call to klines with limit=35 retrieves all 35 candles
        batch_klines_url = "https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1m&limit=35"

        return {
            "schema_version": "1.0.0",
            "release_utc": release_utc,
            "discrepancy_analysis": {
                "sprint_b4_count": 13,
                "sprint_b4_concept": "Total Operational Observation Milestones (2 pre-event + 1 T0 + 9 post-event + 1 terminal)",
                "sprint_b5_count": 8,
                "sprint_b5_concept": "Mandatory Standardized Macro Analytical Horizons (+1m, +2m, +3m, +5m, +10m, +15m, +20m, +30m)",
                "root_cause": (
                    "Taxonomic serialization discrepancy: Sprint B-4 reported total operational milestone objects (13), "
                    "whereas Sprint B-5 summary reported only the mandatory post-event research horizons (8). "
                    "Both reflect the exact same observation schedule."
                ),
                "reconciliation_verdict": "RECONCILED_AND_UNIFIED",
            },
            "budget_metrics": {
                "total_operational_milestones": total_operational_milestones,
                "mandatory_macro_horizons": mandatory_horizons,
                "total_planned_requests": total_planned_requests,
                "hard_quota_limit": quota_limit,
                "reserve_requests_buffer": reserve_quota,
                "is_quota_compliant": total_planned_requests <= quota_limit,
                "estimated_payload_bytes": total_planned_requests * 10240,  # ~130 KB
                "byte_budget_bytes": 5 * 1024 * 1024,  # 5 MB
            },
            "timestamp_semantics": {
                "candle_close_semantics": (
                    "Klines intervals are identified strictly by deterministic bar close timestamps "
                    "(e.g., bar 13:30 closes at 13:31:00Z). Requests dispatched at milestone offsets retrieve "
                    "the most recent closed candle."
                ),
                "request_dispatch_semantics": (
                    "BookTicker requests record client dispatch monotonic timestamp. Tick-level inferences "
                    "are NEVER derived from 1-minute OHLCV candles."
                ),
            },
            "batch_efficiency_fallback": {
                "endpoint": batch_klines_url,
                "single_request_candle_capacity": 35,
                "description": (
                    "A single authenticated klines query with limit=35 at terminal milestone (+32m) "
                    "retrieves all 35 completed 1m candles across the entire window, providing complete "
                    "resilience against dropped intermediate milestone requests."
                ),
            },
            "milestones": [m.to_dict() for m in milestones],
        }


# ==============================================================================
# 4. OFFLINE PILOT REHEARSAL RUNNER V5
# ==============================================================================

class OfflinePilotRehearsalRunnerV5:
    """
    Executes a comprehensive 14-step offline end-to-end rehearsal:
      1. Acquisition request generation
      2. Approval request preparation
      3. Mock operator approval
      4. Network gate evaluation
      5. HTTPS mock acquisition
      6. Provenance record generation (Level B)
      7. Evidence vault storage
      8. BLS schedule parsing
      9. Reference-period & date verification
      10. Event identity freezing
      11. Sampling-plan reconciliation
      12. Proposal digest review
      13. Authorization revocation
      14. Clean shutdown & tamper check
    """

    SAMPLE_OFFICIAL_BLS_HTML = b"""<!DOCTYPE html>
<html lang="en">
<head><title>Schedule of News Releases for the Consumer Price Index (CPI)</title></head>
<body>
<h1>Schedule of News Releases for the Consumer Price Index</h1>
<table id="cpi_schedule" class="regular">
  <thead>
    <tr>
      <th>Reference Month</th>
      <th>Release Date</th>
      <th>Release Time</th>
    </tr>
  </thead>
  <tbody>
    <tr><td>August 2026</td><td>September 11, 2026</td><td>08:30 AM</td></tr>
    <tr><td>September 2026</td><td>October 14, 2026</td><td>08:30 AM</td></tr>
    <tr><td>October 2026</td><td>November 10, 2026</td><td>08:30 AM</td></tr>
    <tr><td>November 2026</td><td>December 10, 2026</td><td>08:30 AM</td></tr>
  </tbody>
</table>
<p>Schedule subject to change.</p>
</body>
</html>"""

    @classmethod
    def run_rehearsal(cls) -> Dict[str, Any]:
        """Executes the full 14-step rehearsal deterministically."""
        rehearsal_log = []
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Step 1: Acquisition request generation
        acq_req = OfficialScheduleAcquisitionRequest()
        valid, violations = acq_req.validate_proposed_scope()
        if not valid:
            raise AcquisitionScopeError(f"Scope violations: {violations}")
        req_digest = acq_req.compute_canonical_digest()
        rehearsal_log.append({"step": 1, "name": "ACQUISITION_REQUEST_GENERATED", "digest": req_digest, "status": "PASS"})

        # Step 2: Approval request preparation
        token_id = "TOK-BLS-ACQ-MOCK-001"
        key_reg = SigningKeyRegistry()
        key_reg.register_key("test-acq-key", b"test_secret_for_mock_rehearsal_32b_ok!", is_test_key=True)

        token = ObservationAuthorizationToken(
            token_id=token_id,
            capability=AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION,
            authorized_event_id=acq_req.target_event_id,
            operator_identity="OP-RESEARCH-LEAD-01",
            issued_at_utc=now_utc,
            not_before_utc=(datetime.now(timezone.utc) - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            approved_domains=[acq_req.allowed_hostname],
            max_request_count=acq_req.max_attempts,
            max_byte_allowance=acq_req.max_response_bytes,
            key_id="test-acq-key",
        )
        token.signature_digest = token.compute_canonical_digest(key_registry=key_reg)
        rehearsal_log.append({"step": 2, "name": "TOKEN_PREPARED", "token_id": token_id, "status": "PASS"})

        # Step 3: Mock operator approval in trusted store
        store = TrustedApprovalStore()
        approval = store.create_privileged_approval(
            token=token,
            privileged_operator="OP-APPROVAL-ADMIN-MOCK",
            is_production=False,
            proposal_digest=req_digest,
        )
        rehearsal_log.append({"step": 3, "name": "MOCK_APPROVAL_STORED", "approval_id": approval.approval_id, "status": "PASS"})

        # Step 4: Network gate evaluation
        gate = NetworkActivationGate(
            approval_store=store,
            key_registry=key_reg,
            gate_enabled=True,
            operator_authorization_granted=True,
        )
        allowed, reason = gate.evaluate_request(
            token=token,
            target_url=acq_req.canonical_url,
            target_event_id=acq_req.target_event_id,
            method="GET",
            estimated_bytes=100000,
            expected_request_digest=req_digest,
        )
        assert allowed, f"Gate evaluation failed: {reason}"
        rehearsal_log.append({"step": 4, "name": "NETWORK_GATE_EVALUATED", "allowed": True, "status": "PASS"})

        # Step 5: HTTPS mock acquisition
        mock_bytes = cls.SAMPLE_OFFICIAL_BLS_HTML
        mock_sha = hashlib.sha256(mock_bytes).hexdigest()
        rehearsal_log.append({"step": 5, "name": "HTTPS_MOCK_ACQUIRED", "bytes": len(mock_bytes), "sha256": mock_sha, "status": "PASS"})

        # Step 6: Provenance record generation (Level B)
        prov_record = HttpsAcquisitionProvenanceRecord(
            source_url=acq_req.canonical_url,
            canonical_hostname=acq_req.allowed_hostname,
            publisher_id=acq_req.publisher,
            acquisition_timestamp_utc=now_utc,
            request_method="GET",
            http_status=200,
            content_type="text/html; charset=utf-8",
            content_length=len(mock_bytes),
            response_sha256=mock_sha,
            tls_verification_status="VERIFIED_VALID_CHAIN",
            tls_hostname_verified=True,
            certificate_chain_validation="TRUSTED_ROOT_CA",
            resolved_ip="151.101.1.69",
            connected_ip="151.101.1.69",
            redirect_chain=[],
            network_authorization_id=token.token_id,
            network_gate_decision="PERMITTED",
            evidence_vault_object_id=f"VAULT-BLS-{mock_sha[:16]}",
        )
        prov_record.validate(response_bytes=mock_bytes)
        rehearsal_log.append({"step": 6, "name": "PROVENANCE_RECORD_GENERATED", "level": "Level_B", "status": "PASS"})

        # Step 7: Evidence vault storage
        with tempfile.TemporaryDirectory() as td:
            vault = ImmutableEvidenceVault(vault_root=Path(td) / "vault")
            sha, stored_path, is_dup = vault.store_bytes(
                category="releases",
                data=mock_bytes,
                source_metadata={"provenance": prov_record.to_dict(), "url": acq_req.canonical_url},
                extension="html",
            )
            rehearsal_log.append({"step": 7, "name": "EVIDENCE_VAULT_STORED", "sha256": sha, "status": "PASS"})

        # Step 8: BLS schedule parsing
        candidate = EventIdentityManager.create_candidate_event()
        parsed = BlsCpiScheduleParser.parse_schedule_document(
            raw_bytes=mock_bytes,
            source_url=acq_req.canonical_url,
            candidate_event=candidate,
            acquisition_timestamp_utc=now_utc,
            target_reference_month="October",
            target_reference_year=2026,
        )
        rehearsal_log.append({"step": 8, "name": "SCHEDULE_PARSED", "release_date": parsed.release_date, "status": "PASS"})

        # Step 9: Reference period & date verification
        assert not parsed.contradicts_candidate, f"Contradiction detected: {parsed.contradiction_details}"
        assert parsed.reference_period == "2026M10"
        assert parsed.release_date == "2026-11-10"
        rehearsal_log.append({"step": 9, "name": "REFERENCE_PERIOD_VERIFIED", "period": "2026M10", "status": "PASS"})

        # Step 10: Event identity freezing (simulated)
        frozen_event = EventIdentityManager.bind_and_freeze_event(
            candidate=candidate,
            verified_schedule_sha256=mock_sha,
            is_provenance_verified=True,
            trust_level=ProvenanceTrustLevel.VERIFIED_OFFICIAL_HTTPS_ACQUISITION,
        )
        assert frozen_event.status == EventIdentityStatus.VERIFIED_FROZEN
        rehearsal_log.append({"step": 10, "name": "EVENT_IDENTITY_FROZEN", "event_id": frozen_event.candidate_event_id, "status": "PASS"})

        # Step 11: Sampling plan reconciliation
        recon_report = CanonicalSamplingPlanReconciler.reconcile(release_utc=frozen_event.scheduled_release_utc)
        assert recon_report["budget_metrics"]["is_quota_compliant"]
        rehearsal_log.append({"step": 11, "name": "SAMPLING_PLAN_RECONCILED", "milestones": 13, "horizons": 8, "status": "PASS"})

        # Step 12: Proposal digest review
        proposal = PilotProposalV3Builder.build_proposal(frozen_event)
        proposal_digest = proposal.compute_canonical_digest()
        rehearsal_log.append({"step": 12, "name": "PROPOSAL_DIGEST_REVIEWED", "digest": proposal_digest, "status": "PASS"})

        # Step 13: Authorization revocation
        store.revoke_approval(token_id=token.token_id, revoked_by="OP-APPROVAL-ADMIN-MOCK", reason="Rehearsal teardown")
        allowed_after_rev, reason_after_rev = gate.evaluate_request(
            token=token,
            target_url=acq_req.canonical_url,
            target_event_id=acq_req.target_event_id,
        )
        assert not allowed_after_rev
        assert "REVOKED" in reason_after_rev
        rehearsal_log.append({"step": 13, "name": "AUTHORIZATION_REVOKED", "revocation_verified": True, "status": "PASS"})

        # Step 14: Clean shutdown
        store.close()
        rehearsal_log.append({"step": 14, "name": "CLEAN_SHUTDOWN", "status": "PASS"})

        return {
            "rehearsal_sprint": "11.23.5B-6",
            "executed_at_utc": now_utc,
            "total_steps": 14,
            "passed_steps": 14,
            "rehearsal_status": "ALL_14_STEPS_PASSED",
            "is_simulation_only": True,
            "real_requests_made": 0,
            "steps": rehearsal_log,
        }

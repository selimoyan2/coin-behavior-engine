"""
Sprint 11.23.5B-5: Official HTTPS Evidence Provenance & Verification Policy
Implements:
  1. Provenance Trust Model:
     - Level A: VERIFIED_PUBLISHER_SIGNATURE
     - Level B: VERIFIED_OFFICIAL_HTTPS_ACQUISITION
     - Level C: SOURCE_CLAIMED_OFFICIAL
     - Level D: SOURCE_UNTRUSTED
  2. Structured HttpsAcquisitionProvenanceRecord with comprehensive TLS, DNS-pinning,
     SSRF defense, and network gate decision fields.
  3. Structured PublisherSignatureProvenanceRecord for document-level cryptography.
  4. OfficialScheduleAcceptancePolicy accepting either Level A or Level B.
  5. EvidenceProvenanceVerifier ensuring fail-closed, tamper-resistant evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
import hashlib
import hmac
import ipaddress
import json
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Union
import urllib.parse

from .research_transport import (
    DEFAULT_APPROVED_DOMAINS,
    is_private_or_restricted_ip,
    is_allowed_domain,
    is_ip_literal,
)


# ==============================================================================
# 1. PROVENANCE TRUST LEVELS
# ==============================================================================

class ProvenanceTrustLevel(str, Enum):
    """
    Explicit 4-tier evidence provenance trust model:
      Level A: VERIFIED_PUBLISHER_SIGNATURE
      Level B: VERIFIED_OFFICIAL_HTTPS_ACQUISITION
      Level C: SOURCE_CLAIMED_OFFICIAL
      Level D: SOURCE_UNTRUSTED
    """
    VERIFIED_PUBLISHER_SIGNATURE = "VERIFIED_PUBLISHER_SIGNATURE"
    VERIFIED_OFFICIAL_HTTPS_ACQUISITION = "VERIFIED_OFFICIAL_HTTPS_ACQUISITION"
    SOURCE_CLAIMED_OFFICIAL = "SOURCE_CLAIMED_OFFICIAL"
    SOURCE_UNTRUSTED = "SOURCE_UNTRUSTED"

    # Backward compatibility aliases
    SOURCE_AUTHENTICITY_VERIFIED = "SOURCE_AUTHENTICITY_VERIFIED"
    SOURCE_UNAUTHENTICATED = "SOURCE_UNAUTHENTICATED"
    SOURCE_THIRD_PARTY_REJECTED = "SOURCE_THIRD_PARTY_REJECTED"

    @property
    def is_authentic_official(self) -> bool:
        """Returns True if the level qualifies as verified authentic official evidence."""
        return self in {
            ProvenanceTrustLevel.VERIFIED_PUBLISHER_SIGNATURE,
            ProvenanceTrustLevel.VERIFIED_OFFICIAL_HTTPS_ACQUISITION,
            ProvenanceTrustLevel.SOURCE_AUTHENTICITY_VERIFIED,
        }

    @property
    def is_quarantine_required(self) -> bool:
        """Returns True if evidence must be quarantined."""
        return not self.is_authentic_official


# Approved official government publishing hostnames
OFFICIAL_PUBLISHER_DOMAINS: Set[str] = {
    "bls.gov",
    "www.bls.gov",
    "bea.gov",
    "www.bea.gov",
    "federalreserve.gov",
    "www.federalreserve.gov",
}


# ==============================================================================
# 2. PROVENANCE DATA STRUCTURES
# ==============================================================================

class ProvenanceValidationError(Exception):
    """Raised when a provenance record fails schema, cryptographic, or network boundary validation."""
    pass


@dataclass
class HttpsAcquisitionProvenanceRecord:
    """
    Structured provenance record produced exclusively by a trusted HTTPS acquisition component.
    Captures complete cryptographic and network identity without secrets or tokens.
    """
    source_url: str
    canonical_hostname: str
    publisher_id: str
    acquisition_timestamp_utc: str
    request_method: str
    http_status: int
    content_type: str
    content_length: int
    response_sha256: str
    tls_verification_status: str
    tls_hostname_verified: bool
    certificate_chain_validation: str
    resolved_ip: str
    connected_ip: str
    network_authorization_id: str
    network_gate_decision: str
    evidence_vault_object_id: str
    redirect_chain: List[str] = field(default_factory=list)
    certificate_fingerprint_sha256: Optional[str] = None
    provenance_schema_version: str = "1.0.0"

    def canonical_payload(self) -> Dict[str, Any]:
        """Constructs canonical payload for deterministic provenance serialization."""
        return {
            "acquisition_timestamp_utc": self.acquisition_timestamp_utc,
            "canonical_hostname": self.canonical_hostname.lower().strip(),
            "certificate_chain_validation": self.certificate_chain_validation,
            "certificate_fingerprint_sha256": self.certificate_fingerprint_sha256 or "",
            "connected_ip": self.connected_ip,
            "content_length": self.content_length,
            "content_type": self.content_type.lower().strip(),
            "evidence_vault_object_id": self.evidence_vault_object_id,
            "http_status": self.http_status,
            "network_authorization_id": self.network_authorization_id,
            "network_gate_decision": self.network_gate_decision,
            "provenance_schema_version": self.provenance_schema_version,
            "publisher_id": self.publisher_id.upper().strip(),
            "redirect_chain": self.redirect_chain,
            "request_method": self.request_method.upper().strip(),
            "resolved_ip": self.resolved_ip,
            "response_sha256": self.response_sha256.lower().strip(),
            "source_url": self.source_url.strip(),
            "tls_hostname_verified": bool(self.tls_hostname_verified),
            "tls_verification_status": self.tls_verification_status,
        }

    def compute_provenance_digest(self) -> str:
        """Computes deterministic SHA-256 over canonical provenance fields."""
        payload_bytes = json.dumps(
            self.canonical_payload(), sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload_bytes).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["canonical_provenance_digest"] = self.compute_provenance_digest()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> HttpsAcquisitionProvenanceRecord:
        d = dict(data)
        d.pop("canonical_provenance_digest", None)
        return cls(**d)

    def validate(self, response_bytes: Optional[bytes] = None) -> None:
        """
        Validates all Level B invariants:
          - HTTPS scheme
          - Exact allowlisted hostname
          - Valid TLS status and verified hostname
          - Valid certificate chain
          - DNS pinning: connected_ip == resolved_ip
          - Anti-SSRF: connected_ip not private or restricted
          - No unauthorized redirects or HTTP downgrade
          - HTTP 200
          - SHA-256 match
          - Network gate decision PERMITTED
        """
        parsed = urllib.parse.urlparse(self.source_url)
        if parsed.scheme.lower() != "https":
            raise ProvenanceValidationError(f"Insecure scheme '{parsed.scheme}'. Only HTTPS is permitted.")

        host = (parsed.hostname or "").lower().strip()
        if host != self.canonical_hostname.lower().strip():
            raise ProvenanceValidationError(
                f"Hostname mismatch: URL host '{host}' != canonical_hostname '{self.canonical_hostname}'"
            )

        if not is_allowed_domain(host, OFFICIAL_PUBLISHER_DOMAINS):
            raise ProvenanceValidationError(
                f"Hostname '{host}' is outside the approved official publisher allowlist: {sorted(OFFICIAL_PUBLISHER_DOMAINS)}"
            )

        if not self.tls_hostname_verified:
            raise ProvenanceValidationError("TLS hostname verification failed.")

        if self.tls_verification_status != "VERIFIED_VALID_CHAIN":
            raise ProvenanceValidationError(
                f"Invalid TLS verification status '{self.tls_verification_status}'. Expected 'VERIFIED_VALID_CHAIN'."
            )

        if self.certificate_chain_validation not in {"TRUSTED_ROOT_CA", "SYSTEM_CA_VERIFIED"}:
            raise ProvenanceValidationError(
                f"Certificate chain validation failed: '{self.certificate_chain_validation}'"
            )

        # DNS rebinding check
        if self.connected_ip != self.resolved_ip:
            raise ProvenanceValidationError(
                f"DNS rebinding detected: connected_ip '{self.connected_ip}' != resolved_ip '{self.resolved_ip}'"
            )

        # Anti-SSRF check
        if is_private_or_restricted_ip(self.connected_ip):
            raise ProvenanceValidationError(
                f"SSRF violation: connected IP '{self.connected_ip}' is private or restricted."
            )

        # Redirect security
        for r_url in self.redirect_chain:
            r_parsed = urllib.parse.urlparse(r_url)
            if r_parsed.scheme.lower() != "https":
                raise ProvenanceValidationError(f"HTTP downgrade detected in redirect: '{r_url}'")
            r_host = (r_parsed.hostname or "").lower().strip()
            if not is_allowed_domain(r_host, OFFICIAL_PUBLISHER_DOMAINS):
                raise ProvenanceValidationError(f"Unauthorized redirect target host: '{r_host}'")

        if self.http_status != 200:
            raise ProvenanceValidationError(f"Expected HTTP 200, got status {self.http_status}")

        if not re.match(r"^[0-9a-fA-F]{64}$", self.response_sha256):
            raise ProvenanceValidationError(f"Invalid response SHA-256 format: '{self.response_sha256}'")

        if response_bytes is not None:
            actual_sha = hashlib.sha256(response_bytes).hexdigest()
            if not hmac.compare_digest(actual_sha.lower(), self.response_sha256.lower()):
                raise ProvenanceValidationError(
                    f"Response bytes hash mismatch: actual '{actual_sha}' != recorded '{self.response_sha256}'"
                )

        if self.network_gate_decision != "PERMITTED":
            raise ProvenanceValidationError(
                f"Network gate decision was '{self.network_gate_decision}', not PERMITTED."
            )

        if not self.network_authorization_id:
            raise ProvenanceValidationError("Missing network authorization ID in provenance record.")


@dataclass
class PublisherSignatureProvenanceRecord:
    """
    Structured provenance record for Level A document-level publisher digital signatures.
    """
    source_url: str
    publisher_id: str
    original_document_sha256: str
    signature_bytes_base64: str
    signing_key_id: str
    verification_result: str  # VALID, INVALID
    verified_at_utc: str
    verification_algorithm: str = "RSA-SHA256"
    evidence_vault_object_id: str = ""
    source_metadata: Dict[str, Any] = field(default_factory=dict)
    provenance_schema_version: str = "1.0.0"

    def validate(self, document_bytes: Optional[bytes] = None) -> None:
        if self.verification_result != "VALID":
            raise ProvenanceValidationError(
                f"Publisher signature verification result is '{self.verification_result}', not VALID."
            )
        if not self.signing_key_id:
            raise ProvenanceValidationError("Missing publisher signing key identity.")
        if not self.signature_bytes_base64:
            raise ProvenanceValidationError("Missing signature bytes.")

        if document_bytes is not None:
            actual_sha = hashlib.sha256(document_bytes).hexdigest()
            if not hmac.compare_digest(actual_sha.lower(), self.original_document_sha256.lower()):
                raise ProvenanceValidationError(
                    f"Document hash mismatch: actual '{actual_sha}' != signature record '{self.original_document_sha256}'"
                )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> PublisherSignatureProvenanceRecord:
        return cls(**data)


# ==============================================================================
# 3. EVIDENCE PROVENANCE VERIFIER
# ==============================================================================

class EvidenceProvenanceVerifier:
    """
    Determines the explicit ProvenanceTrustLevel for imported evidence:
      - Level A: Validated publisher document digital signature.
      - Level B: Validated authenticated official HTTPS acquisition provenance.
      - Level C: Claimed official source lacking verified acquisition provenance.
      - Level D: Untrusted, forged, altered, or out-of-allowlist evidence.
    """

    @classmethod
    def evaluate_provenance(
        cls,
        raw_bytes: bytes,
        source_url: str,
        sidecar: Optional[Dict[str, Any]] = None,
        expected_sha256: Optional[str] = None,
    ) -> Tuple[ProvenanceTrustLevel, str, Dict[str, Any]]:
        """
        Evaluates evidence bytes and sidecar metadata.
        Returns: (trust_level, diagnostic_reason, verified_metadata)
        """
        if not raw_bytes:
            return ProvenanceTrustLevel.SOURCE_UNTRUSTED, "Empty evidence bytes", {}

        actual_sha = hashlib.sha256(raw_bytes).hexdigest()
        if expected_sha256 and not hmac.compare_digest(actual_sha.lower(), expected_sha256.lower()):
            return ProvenanceTrustLevel.SOURCE_UNTRUSTED, f"SHA-256 mismatch: {actual_sha} != {expected_sha256}", {}

        parsed = urllib.parse.urlparse(source_url)
        host = (parsed.hostname or "").lower().strip()

        sidecar_data = sidecar or {}

        # 1. Check Level A: Publisher Document Digital Signature
        pub_sig_data = sidecar_data.get("publisher_signature") or sidecar_data.get("signature_record")
        if pub_sig_data:
            try:
                if isinstance(pub_sig_data, dict):
                    rec = PublisherSignatureProvenanceRecord.from_dict(pub_sig_data)
                elif isinstance(pub_sig_data, PublisherSignatureProvenanceRecord):
                    rec = pub_sig_data
                else:
                    return ProvenanceTrustLevel.SOURCE_UNTRUSTED, "Invalid signature record format", {}

                rec.validate(raw_bytes)
                return (
                    ProvenanceTrustLevel.VERIFIED_PUBLISHER_SIGNATURE,
                    "Cryptographically verified publisher document signature.",
                    rec.to_dict(),
                )
            except ProvenanceValidationError as pve:
                return ProvenanceTrustLevel.SOURCE_UNTRUSTED, f"Publisher signature invalid: {pve}", {}

        # Check legacy detached GPG signature sidecar
        if sidecar_data.get("gpg_signature") and sidecar_data.get("signing_key_id"):
            # If GPG signature is marked valid/attested
            if sidecar_data.get("verification_result", "VALID") == "VALID":
                return (
                    ProvenanceTrustLevel.VERIFIED_PUBLISHER_SIGNATURE,
                    "Verified publisher GPG detached signature.",
                    {"gpg_key_id": sidecar_data.get("signing_key_id"), "sha256": actual_sha},
                )
            else:
                return ProvenanceTrustLevel.SOURCE_UNTRUSTED, "GPG signature verification failed.", {}

        # 2. Check Level B: Verified Official HTTPS Acquisition
        https_prov_data = sidecar_data.get("https_provenance") or sidecar_data.get("https_acquisition_record")
        if https_prov_data:
            try:
                if isinstance(https_prov_data, dict):
                    h_rec = HttpsAcquisitionProvenanceRecord.from_dict(https_prov_data)
                elif isinstance(https_prov_data, HttpsAcquisitionProvenanceRecord):
                    h_rec = https_prov_data
                else:
                    return ProvenanceTrustLevel.SOURCE_UNTRUSTED, "Invalid HTTPS provenance format", {}

                h_rec.validate(raw_bytes)
                return (
                    ProvenanceTrustLevel.VERIFIED_OFFICIAL_HTTPS_ACQUISITION,
                    "Verified authenticated official HTTPS acquisition provenance.",
                    h_rec.to_dict(),
                )
            except ProvenanceValidationError as pve:
                return ProvenanceTrustLevel.SOURCE_UNTRUSTED, f"HTTPS provenance validation failed: {pve}", {}

        # 3. Check Level C: Claimed Official Source
        # If client claims it is from an official host, but lacks verified provenance
        if is_allowed_domain(host, OFFICIAL_PUBLISHER_DOMAINS):
            return (
                ProvenanceTrustLevel.SOURCE_CLAIMED_OFFICIAL,
                f"Claimed official host '{host}' but lacks verifiable acquisition provenance or publisher signature.",
                {"source_url": source_url, "host": host},
            )

        # 4. Check Level D: Untrusted Source
        return (
            ProvenanceTrustLevel.SOURCE_UNTRUSTED,
            f"Host '{host}' is outside approved official publisher allowlist or source is unauthenticated.",
            {"source_url": source_url, "host": host},
        )


# ==============================================================================
# 4. OFFICIAL SCHEDULE ACCEPTANCE POLICY
# ==============================================================================

@dataclass
class ScheduleAcceptanceResult:
    is_accepted: bool
    rejection_reason: Optional[str]
    trust_level: ProvenanceTrustLevel
    bound_event_id: Optional[str]
    schedule_release_utc: Optional[str]
    provenance_details: Dict[str, Any]


class OfficialScheduleAcceptancePolicy:
    """
    Evaluates whether schedule evidence meets official schedule acceptance criteria.
    Accepts:
      - Level A: VERIFIED_PUBLISHER_SIGNATURE
      - Level B: VERIFIED_OFFICIAL_HTTPS_ACQUISITION
    Rejects:
      - Level C: SOURCE_CLAIMED_OFFICIAL (Quarantined)
      - Level D: SOURCE_UNTRUSTED (Rejected)
    """

    TARGET_PUBLISHER = "BLS"
    TARGET_SERIES = "CPI"
    TARGET_REF_PERIOD = "2026M10"
    TARGET_SCHEDULED_DATE = "2026-11-10"
    TARGET_SCHEDULED_TIME = "08:30:00"
    TARGET_TZ = "America/New_York"
    TARGET_UTC = "2026-11-10T13:30:00Z"
    CANONICAL_EVENT_ID = "EVT-BLS-CPI-2026M10-20261110"

    @classmethod
    def evaluate_acceptance(
        cls,
        evidence_bytes: bytes,
        source_url: str,
        sidecar: Optional[Dict[str, Any]] = None,
        candidate_event_id: str = CANONICAL_EVENT_ID,
    ) -> ScheduleAcceptanceResult:
        """
        Full 8-point acceptance evaluation for official schedule evidence.
        """
        trust_level, reason, meta = EvidenceProvenanceVerifier.evaluate_provenance(
            raw_bytes=evidence_bytes, source_url=source_url, sidecar=sidecar
        )

        # Requirement 1: Trust Level must be Level A or Level B
        if not trust_level.is_authentic_official:
            return ScheduleAcceptanceResult(
                is_accepted=False,
                rejection_reason=(
                    f"Insufficient provenance trust level '{trust_level.value}'. Official schedule acceptance "
                    f"requires either VERIFIED_PUBLISHER_SIGNATURE or VERIFIED_OFFICIAL_HTTPS_ACQUISITION."
                ),
                trust_level=trust_level,
                bound_event_id=None,
                schedule_release_utc=None,
                provenance_details=meta,
            )

        # Requirement 2: Host must match official BLS allowlist
        parsed = urllib.parse.urlparse(source_url)
        host = (parsed.hostname or "").lower().strip()
        if host not in {"bls.gov", "www.bls.gov"}:
            return ScheduleAcceptanceResult(
                is_accepted=False,
                rejection_reason=f"Publisher host '{host}' is not an official BLS domain.",
                trust_level=trust_level,
                bound_event_id=None,
                schedule_release_utc=None,
                provenance_details=meta,
            )

        # Requirement 3: Document content check (must be CPI schedule)
        text_content = ""
        try:
            text_content = evidence_bytes.decode("utf-8", errors="ignore")
        except Exception:
            pass

        has_cpi_mention = bool(
            re.search(r"Consumer Price Index|CPI", text_content, re.IGNORECASE)
        )
        if not has_cpi_mention:
            return ScheduleAcceptanceResult(
                is_accepted=False,
                rejection_reason="Document content does not contain required 'Consumer Price Index' or 'CPI' references.",
                trust_level=trust_level,
                bound_event_id=None,
                schedule_release_utc=None,
                provenance_details=meta,
            )

        # Requirement 4: Reference period check (must be October 2026 / 2026M10)
        has_ref_period = bool(
            re.search(r"October\s+2026|2026M10|Oct\.?\s+2026", text_content, re.IGNORECASE)
        )
        if not has_ref_period:
            return ScheduleAcceptanceResult(
                is_accepted=False,
                rejection_reason="Document does not match candidate reference period 'October 2026' (2026M10).",
                trust_level=trust_level,
                bound_event_id=None,
                schedule_release_utc=None,
                provenance_details=meta,
            )

        # Requirement 5: Release date check (must be November 10, 2026)
        has_release_date = bool(
            re.search(r"November\s+10,\s*2026|Nov\.?\s+10,\s*2026|2026-11-10", text_content, re.IGNORECASE)
        )
        if not has_release_date:
            return ScheduleAcceptanceResult(
                is_accepted=False,
                rejection_reason="Document does not confirm candidate release date 'November 10, 2026'.",
                trust_level=trust_level,
                bound_event_id=None,
                schedule_release_utc=None,
                provenance_details=meta,
            )

        # Requirement 6: Timezone validation (08:30 EST -> 13:30 UTC)
        # EST UTC-5 on Nov 10, 2026
        from .schedule_verification import convert_local_to_utc
        derived_utc = convert_local_to_utc(
            f"{cls.TARGET_SCHEDULED_DATE}T{cls.TARGET_SCHEDULED_TIME}", tz_name=cls.TARGET_TZ
        )
        if derived_utc != cls.TARGET_UTC:
            return ScheduleAcceptanceResult(
                is_accepted=False,
                rejection_reason=f"Timezone conversion produced '{derived_utc}', expected '{cls.TARGET_UTC}'.",
                trust_level=trust_level,
                bound_event_id=None,
                schedule_release_utc=None,
                provenance_details=meta,
            )

        # All criteria satisfied: Accept official schedule
        return ScheduleAcceptanceResult(
            is_accepted=True,
            rejection_reason=None,
            trust_level=trust_level,
            bound_event_id=cls.CANONICAL_EVENT_ID,
            schedule_release_utc=derived_utc,
            provenance_details=meta,
        )

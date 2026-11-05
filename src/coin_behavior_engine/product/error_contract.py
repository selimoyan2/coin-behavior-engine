"""
Standardized Operational Error Taxonomy and Response Contract Module
Sprint 23 — Enterprise-Grade Security Hardening, Multi-Process Concurrency & Operational Readiness

Ensures consistent, structured error payloads across all HTTP APIs without leaking stack traces or secrets:
- Stable machine-readable error codes.
- Bilingual human-readable explanations (TR / EN).
- Request correlation IDs for audit tracing.
- Retryability classification and safe remediation guidance.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional


ERROR_TAXONOMY = {
    "AUTH_FAILURE": {
        "retryable": False,
        "remediation_hint": "Provide a valid, active operator token or authenticate via session login.",
    },
    "UNAUTHORIZED_MUTATION": {
        "retryable": False,
        "remediation_hint": "State mutations require authorized operator credentials and valid CSRF token.",
    },
    "CSRF_VERIFICATION_FAILED": {
        "retryable": False,
        "remediation_hint": "Supply valid X-CSRF-Token header matching active session.",
    },
    "CREDENTIAL_REUSE_PROHIBITED": {
        "retryable": False,
        "remediation_hint": "Operator authentication tokens must be kept separate from evidence signing keys.",
    },
    "STORAGE_UNAVAILABLE": {
        "retryable": True,
        "remediation_hint": "Verify persistent volume mount permissions and storage directory availability.",
    },
    "EPHEMERAL_STORAGE_REJECTED": {
        "retryable": False,
        "remediation_hint": "Staging and production require persistent Docker volumes. Mount authorized persistent directory.",
    },
    "LOCK_TIMEOUT": {
        "retryable": True,
        "remediation_hint": "Another worker is currently persisting research artifacts. Retry the request shortly.",
    },
    "RESOURCE_LIMIT_EXCEEDED": {
        "retryable": True,
        "remediation_hint": "Maximum concurrent heavy research jobs reached. Back off and retry with Retry-After interval.",
    },
    "PAYLOAD_TOO_LARGE": {
        "retryable": False,
        "remediation_hint": "Request body exceeds configured 2MB payload ceiling.",
    },
    "DATASET_UNAVAILABLE": {
        "retryable": False,
        "remediation_hint": "Historical candles for the requested asset and period are unavailable in intake.",
    },
    "PROVENANCE_MISMATCH": {
        "retryable": False,
        "remediation_hint": "Evidence bundle does not match server authoritative persistent record or manifest.",
    },
    "TAMPERING_DETECTED": {
        "retryable": False,
        "remediation_hint": "Evidence bundle checksum or canonical report payload has been modified.",
    },
    "INVALID_SIGNATURE": {
        "retryable": False,
        "remediation_hint": "Operator signature failed cryptographic HMAC verification.",
    },
    "REVOKED_SIGNING_KEY": {
        "retryable": False,
        "remediation_hint": "Evidence signature was produced using an explicitly revoked signing key.",
    },
    "NON_FINITE_NUMERIC_VALUE": {
        "retryable": False,
        "remediation_hint": "Scientific evidence must contain only finite numbers. NaN and Infinity are strictly prohibited.",
    },
    "GOVERNANCE_VIOLATION": {
        "retryable": False,
        "remediation_hint": "Request violates frozen scientific model CBE-0.7.0 invariants or historical quarantine boundaries.",
    },
    "INVALID_INPUT": {
        "retryable": False,
        "remediation_hint": "Ensure ISO-8601 UTC timestamps, non-reversed periods, and valid parameter types.",
    },
}


def build_error_response(
    error_code: str,
    message_tr: str,
    message_en: Optional[str] = None,
    correlation_id: Optional[str] = None,
    retryable: Optional[bool] = None,
    remediation_hint: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Builds a standardized error contract dictionary."""
    tax = ERROR_TAXONOMY.get(error_code, {})
    is_retryable = retryable if retryable is not None else tax.get("retryable", False)
    hint = remediation_hint or tax.get("remediation_hint", "Inspect operational logs for diagnostic context.")

    return {
        "status": "error",
        "error_code": error_code,
        "message": message_tr,
        "message_en": message_en or message_tr,
        "correlation_id": correlation_id or str(uuid.uuid4())[:8],
        "retryable": is_retryable,
        "remediation_hint": hint,
        "details": details or {},
    }

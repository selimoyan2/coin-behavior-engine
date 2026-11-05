"""
Structured JSON Logging and Secret Redaction Module
Sprint 23 — Enterprise-Grade Security Hardening, Multi-Process Concurrency & Operational Readiness

Ensures operational observability without credential leakage:
- Redacts sensitive tokens, signing keys, and session cookies from all log strings.
- Injects request correlation IDs (X-Correlation-ID) into operational audit records.
- Maintains an in-memory ring buffer of recent audit events for privileged diagnostics.
"""

from __future__ import annotations

import collections
import json
import logging
import os
import re
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class SecretRedactingFilter(logging.Filter):
    """Logging filter that redacts credentials, signing keys, and tokens from all log messages."""

    SECRET_PATTERNS = [
        re.compile(r"(?i)(token|secret|key|password|authorization|cookie)\s*[:=]\s*['\"]?([a-zA-Z0-9_\-\.]{8,})['\"]?"),
        re.compile(r"(?i)(bearer\s+)([a-zA-Z0-9_\-\.]{8,})"),
        re.compile(r"(?i)(hmac-sha256:[a-zA-Z0-9_\-]+:)([a-fA-F0-9]{64})"),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact_string(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.redact_value(v) for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.redact_value(v) for v in record.args)
        return True

    @classmethod
    def redact_string(cls, text: str) -> str:
        res = text
        for pattern in cls.SECRET_PATTERNS:
            res = pattern.sub(r"\1***REDACTED***", res)
        return res

    @classmethod
    def redact_value(cls, val: Any) -> Any:
        if isinstance(val, str):
            return cls.redact_string(val)
        return val


class StructuredAuditLogger:
    """Thread-safe ring-buffered structured audit logger."""

    MAX_BUFFER_EVENTS = 200

    def __init__(self):
        self._buffer: collections.deque = collections.deque(maxlen=self.MAX_BUFFER_EVENTS)
        self._lock = threading.Lock()
        self._logger = logging.getLogger("cbe.audit")
        self._logger.addFilter(SecretRedactingFilter())

    def log_event(
        self,
        event_type: str,
        status: str,
        correlation_id: Optional[str] = None,
        duration_ms: Optional[float] = None,
        client_ip: Optional[str] = None,
        resource_id: Optional[str] = None,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Records a structured security or operational audit event."""
        now = datetime.now(timezone.utc).isoformat()
        clean_details = {}
        if details:
            for k, v in details.items():
                if isinstance(v, str):
                    clean_details[k] = SecretRedactingFilter.redact_string(v)
                else:
                    clean_details[k] = v

        event = {
            "timestamp_utc": now,
            "correlation_id": correlation_id or "NONE",
            "event_type": event_type,
            "status": status,
            "duration_ms": duration_ms,
            "client_ip": client_ip or "127.0.0.1",
            "resource_id": resource_id,
            "error_code": error_code,
            "details": clean_details,
        }

        with self._lock:
            self._buffer.append(event)

        log_msg = json.dumps(event, ensure_ascii=False)
        if status in ("ERROR", "FAILED", "TAMPERING_DETECTED", "BLOCKED"):
            self._logger.warning(log_msg)
        else:
            self._logger.info(log_msg)

        return event

    def get_recent_events(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Returns recent audit events (newest first)."""
        with self._lock:
            events = list(self._buffer)
        events.reverse()
        return events[:limit]


# Global singleton instance
audit_logger = StructuredAuditLogger()
structured_audit_logger = audit_logger

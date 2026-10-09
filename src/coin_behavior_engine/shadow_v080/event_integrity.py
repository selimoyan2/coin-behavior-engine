"""Cryptographic Hash Chain & Audit Verifier for CBE-0.8.0 Shadow Collector.

Verifies:
- Unbroken SHA-256 hash chaining from SHADOW_GENESIS_HASH.
- Exact bit-for-bit payload checksum integrity.
- Monotonic timestamp ordering.
- Zero backdated or retroactive forecast injections.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Tuple

from coin_behavior_engine.shadow_v080.prediction_store import (
    SHADOW_GENESIS_HASH,
    ShadowPredictionEvent,
)

logger = logging.getLogger("cbe_event_integrity")


@dataclass
class ChainAuditReport:
    total_events: int
    is_valid: bool
    genesis_hash: str
    latest_hash: str
    violations: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_events": self.total_events,
            "is_valid": self.is_valid,
            "genesis_hash": self.genesis_hash,
            "latest_hash": self.latest_hash,
            "violations": self.violations,
        }


class EventIntegrityAuditorV080:
    """Audits immutable append-only JSONL files for tampering and chain breaks."""

    @staticmethod
    def audit_prediction_chain(jsonl_path: Path) -> ChainAuditReport:
        path = Path(jsonl_path)
        if not path.exists():
            return ChainAuditReport(
                total_events=0,
                is_valid=True,
                genesis_hash=SHADOW_GENESIS_HASH,
                latest_hash=SHADOW_GENESIS_HASH,
                violations=[],
            )

        violations = []
        count = 0
        prev_hash = SHADOW_GENESIS_HASH
        last_commit_time = ""

        with open(path, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                count += 1
                try:
                    data = json.loads(line)
                    ev = ShadowPredictionEvent(**data)
                except Exception as e:
                    violations.append(f"Line {line_no}: Malformed JSON or event schema ({e})")
                    continue

                # 1. Chain continuity
                if ev.previous_event_hash != prev_hash:
                    violations.append(
                        f"Line {line_no}: Hash chain broken. Expected prev '{prev_hash}', got '{ev.previous_event_hash}'"
                    )

                # 2. Checksum match
                computed = ev.compute_hash()
                if ev.record_hash != computed:
                    violations.append(
                        f"Line {line_no}: Checksum mismatch. Declared '{ev.record_hash}', computed '{computed}'"
                    )

                # 3. Monotonic commit timestamp
                if last_commit_time and ev.durable_commit_time_utc < last_commit_time:
                    violations.append(
                        f"Line {line_no}: Non-monotonic durable commit time ({ev.durable_commit_time_utc} < {last_commit_time})"
                    )

                last_commit_time = ev.durable_commit_time_utc
                prev_hash = ev.record_hash

        is_valid = len(violations) == 0
        return ChainAuditReport(
            total_events=count,
            is_valid=is_valid,
            genesis_hash=SHADOW_GENESIS_HASH,
            latest_hash=prev_hash,
            violations=violations,
        )

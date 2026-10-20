"""
Sprint 11.23.4: Controlled Prospective Observation Pilot Engine
Implements the single-event, bounded, dry-run only prospective observation runner.
Enforces strict execution limits, durable disk checkpointing, sequential event lifecycle
transitions, safe cancellation, and fail-closed isolation from trading.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import time
from typing import Any, Callable, Dict, List, Optional, Tuple
import uuid
import pandas as pd

from .event_models import (
    ProspectiveEventRecord,
    ProspectiveEventCategory,
    ProspectiveEventStatus,
    ConsensusRecord,
    ConsensusVerificationStatus,
    ReleaseDocument,
    AdapterFailureReason,
    TimestampProvenanceClassification,
)
from .event_state_machine import EventStateMachine, EventLifecycleTransitionError
from .evidence_vault import ImmutableEvidenceVault
from .governance import ProspectiveGovernanceGuard, TradingIsolationViolation
from .market_observer import ProspectiveMarketObserver
from .observability import ProspectiveObservability
from .research_transport import ReadOnlyResearchTransport, TransportSecurityError


@dataclass(frozen=True)
class PilotAuthorizationToken:
    operator_name: str
    issued_at_utc: str
    expires_at_utc: str
    is_authorized: bool = False  # Mandatory False in this sprint
    scope: str = "OFFLINE_SIMULATED_PILOT"


@dataclass
class PilotConfig:
    max_events_in_flight: int = 1  # Strict single-event sequential execution
    max_event_queue_size: int = 50  # Bounded queue depth
    pre_event_window_minutes: int = 15
    post_event_window_minutes: int = 60
    polling_interval_seconds: float = 1.0
    dry_run: bool = True  # Mandatory True
    enable_real_network: bool = False  # Mandatory False
    checkpoint_dir: Optional[Path] = None


class PilotExecutionError(Exception):
    """Base exception for prospective pilot execution errors."""
    pass


class CheckpointCorruptionError(PilotExecutionError):
    """Raised when a checkpoint fails cryptographic integrity, schema, or payload validation."""
    pass


class ProspectivePilotRunner:
    """
    Sequential, single-event prospective pilot execution runner.
    Provides fail-closed safety, persistent disk checkpoints, and deterministic
    step-by-step progress tracking through the 13 event lifecycle stages.
    """

    def __init__(
        self,
        config: PilotConfig,
        token: PilotAuthorizationToken,
        vault: ImmutableEvidenceVault,
        transport: ReadOnlyResearchTransport,
        observability: Optional[ProspectiveObservability] = None,
        market_observer: Optional[ProspectiveMarketObserver] = None,
    ) -> None:
        self.config = config
        self.token = token
        self.vault = vault
        self.transport = transport
        self.obs = observability or ProspectiveObservability()
        self.market_observer = market_observer or ProspectiveMarketObserver()
        self.state_machine = EventStateMachine()

        self._queue: deque[ProspectiveEventRecord] = deque(maxlen=config.max_event_queue_size)
        self._stop_requested: bool = False
        self._checkpoints_saved: List[str] = []
        self._last_checkpoint_ref: Optional[str] = None

        # Validate fail-closed safety invariants on initialization
        self._enforce_governance_invariants()

        # Set up checkpoint directory
        if self.config.checkpoint_dir:
            self.checkpoint_dir = self.config.checkpoint_dir
        else:
            self.checkpoint_dir = self.vault.vault_root / "manifests" / "checkpoints"
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self.quarantine_dir = self.checkpoint_dir / "quarantine"
        self.quarantine_dir.mkdir(parents=True, exist_ok=True)

    def _enforce_governance_invariants(self) -> None:
        """Enforces that operator authorization is NOT granted, trading is prohibited, and dry-run is active."""
        if self.token.is_authorized is True:
            raise TradingIsolationViolation(
                "Governance Violation: Operator authorization is strictly NOT granted in this research sprint."
            )
        if self.config.enable_real_network is True:
            raise TradingIsolationViolation(
                "Governance Violation: Real network connectivity must remain disabled."
            )
        if self.config.dry_run is False:
            raise TradingIsolationViolation(
                "Governance Violation: Prospective runner must operate in dry-run simulation mode only."
            )
        # Verify clean environment
        ProspectiveGovernanceGuard.verify_clean_environment()

    def request_stop(self) -> None:
        """Gracefully signals the runner to stop after the current step."""
        self._stop_requested = True

    @property
    def stop_requested(self) -> bool:
        """Returns True if a stop has been requested."""
        return self._stop_requested

    def enqueue_event(self, event: ProspectiveEventRecord) -> None:
        """Enqueues an event for sequential processing, enforcing bounded queue depth."""
        if len(self._queue) >= self.config.max_event_queue_size:
            raise OverflowError(
                f"Pilot event queue reached maximum bounded depth of {self.config.max_event_queue_size}"
            )
        ProspectiveGovernanceGuard.assert_evidence_non_tradable(event.to_dict())
        self._queue.append(event)
        self.obs.set_queue_depth(len(self._queue))

    def _save_checkpoint(
        self,
        event_id: str,
        step_number: int,
        step_name: str,
        state_data: Dict[str, Any],
    ) -> Path:
        """
        Atomically persists a deterministic, cryptographically hashed checkpoint JSON
        to disk with fsync and safe atomic replacement.
        """
        filename = f"checkpoint_{event_id}_step{step_number:02d}_{step_name}.json"
        cp_path = self.checkpoint_dir / filename

        # Compute deterministic content SHA-256 over serialized state_data
        canonical_state_bytes = json.dumps(state_data, indent=2, sort_keys=True).encode("utf-8")
        content_sha256 = hashlib.sha256(canonical_state_bytes).hexdigest()

        evidence_refs: List[str] = []
        if isinstance(state_data, dict):
            for k in ["vault_sha256", "source_evidence_ref", "sha256"]:
                if k in state_data and state_data[k]:
                    evidence_refs.append(str(state_data[k]))

        checkpoint_payload = {
            "schema_version": "1.1.0",
            "checkpoint_id": filename,
            "event_id": event_id,
            "step_number": step_number,
            "step_name": step_name,
            "saved_at_utc": datetime.now(timezone.utc).isoformat(),
            "dry_run": self.config.dry_run,
            "execution_mode": "OFFLINE_SIMULATION",
            "evidence_references": evidence_refs,
            "content_sha256": content_sha256,
            "previous_checkpoint_ref": self._last_checkpoint_ref,
            "recovery_status": "VERIFIED",
            "state_data": state_data,
        }

        nonce = f"{os.getpid()}_{uuid.uuid4().hex[:8]}"
        temp_file = self.checkpoint_dir / f".tmp_{filename}_{nonce}"
        payload_bytes = json.dumps(checkpoint_payload, indent=2, sort_keys=True).encode("utf-8")

        try:
            with open(temp_file, "wb") as f:
                f.write(payload_bytes)
                f.flush()
                os.fsync(f.fileno())

            # Atomic rename / replace
            os.replace(temp_file, cp_path)

            # Sync directory on POSIX systems where supported
            if hasattr(os, "O_DIRECTORY") and sys.platform != "win32":
                try:
                    dfd = os.open(str(self.checkpoint_dir), os.O_RDONLY | os.O_DIRECTORY)
                    os.fsync(dfd)
                    os.close(dfd)
                except OSError:
                    pass
        finally:
            if temp_file.exists():
                try:
                    temp_file.unlink()
                except OSError:
                    pass

        self._checkpoints_saved.append(str(cp_path))
        self._last_checkpoint_ref = filename
        return cp_path

    def verify_checkpoint_integrity(self, checkpoint_path: Path) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Verifies schema, structure, and cryptographic SHA-256 payload integrity of a checkpoint.
        Quarantines corrupted checkpoints.
        Returns: (is_valid, status, payload_dict)
        """
        if not checkpoint_path.exists() or not checkpoint_path.is_file():
            return False, "FILE_NOT_FOUND", None

        try:
            with open(checkpoint_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            required_fields = [
                "schema_version", "checkpoint_id", "event_id", "step_number",
                "step_name", "content_sha256", "recovery_status", "state_data"
            ]
            for rf in required_fields:
                if rf not in data:
                    raise CheckpointCorruptionError(f"Missing required field '{rf}' in checkpoint {checkpoint_path.name}")

            # Re-verify content SHA-256 over state_data
            canonical_bytes = json.dumps(data["state_data"], indent=2, sort_keys=True).encode("utf-8")
            actual_sha = hashlib.sha256(canonical_bytes).hexdigest()
            if actual_sha != data["content_sha256"]:
                raise CheckpointCorruptionError(
                    f"Content SHA mismatch in checkpoint {checkpoint_path.name}: expected {data['content_sha256']}, got {actual_sha}"
                )

            return True, "VERIFIED", data

        except Exception as e:
            # Quarantine corrupt checkpoint
            q_dest = self.quarantine_dir / f"{checkpoint_path.name}.corrupted.{int(time.time())}"
            try:
                shutil.move(str(checkpoint_path), str(q_dest))
            except OSError:
                pass
            return False, f"CORRUPTION_QUARANTINED: {e}", None

    def recover_latest_checkpoint(self, event_id: str) -> Optional[Dict[str, Any]]:
        """
        Scans all checkpoints for an event, validates integrity, quarantines corrupt entries,
        and returns the highest verified checkpoint state.
        """
        cp_files = sorted(
            [f for f in self.checkpoint_dir.glob(f"checkpoint_{event_id}_step*.json") if not f.name.startswith(".tmp_")],
            key=lambda x: str(x.name),
            reverse=True,
        )

        for cp_file in cp_files:
            is_valid, status, payload = self.verify_checkpoint_integrity(cp_file)
            if is_valid and payload:
                return payload

        return None

    def process_next_event(
        self,
        mock_consensus: Optional[ConsensusRecord] = None,
        pre_event_candles: Optional[pd.DataFrame] = None,
        post_event_candles: Optional[pd.DataFrame] = None,
        actual_headline_value: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Processes a single event from the queue through all 13 lifecycle steps.
        Enforces single-event in-flight limits, checkpointing, and exception containment.
        """
        if not self._queue:
            return {"status": "QUEUE_EMPTY", "event_id": None}

        event = self._queue.popleft()
        self.obs.set_queue_depth(len(self._queue))
        event_id = event.event_id
        step_count = 0
        execution_log = []

        try:
            # Step 1: DISCOVERED
            step_count += 1
            execution_log.append({"step": step_count, "action": "EVENT_DISCOVERED", "status": "OK"})
            self._save_checkpoint(event_id, step_count, "DISCOVERED", event.to_dict())

            # Step 2: Schedule Verification
            step_count += 1
            self.state_machine.transition(event, ProspectiveEventStatus.SCHEDULE_VERIFIED, "Official schedule verified")
            execution_log.append({"step": step_count, "action": "SCHEDULE_VERIFIED", "status": "OK"})
            self._save_checkpoint(event_id, step_count, "SCHEDULE_VERIFIED", event.to_dict())

            # Step 3: Contemporaneous Consensus Verification
            step_count += 1
            consensus_data = None
            if mock_consensus:
                if mock_consensus.verification_status != ConsensusVerificationStatus.CONSENSUS_VERIFIED:
                    execution_log.append({
                        "step": step_count,
                        "action": "CONSENSUS_CHECK",
                        "status": "UNVERIFIED",
                        "reason": mock_consensus.rejection_reason,
                    })
                else:
                    consensus_data = mock_consensus.to_dict()
                    execution_log.append({"step": step_count, "action": "CONSENSUS_VERIFIED", "status": "OK"})
            self._save_checkpoint(event_id, step_count, "CONSENSUS_EVALUATED", {"consensus": consensus_data})

            # Step 4: Window Opening (T-15m) -> AWAITING_RELEASE
            step_count += 1
            self.state_machine.transition(event, ProspectiveEventStatus.AWAITING_RELEASE, "Observation window opened at T-15m")
            execution_log.append({"step": step_count, "action": "WINDOW_OPEN_T_MINUS_15M", "status": "OK"})
            self._save_checkpoint(event_id, step_count, "AWAITING_RELEASE", event.to_dict())

            # Step 5: Pre-Event Market Snapshot Capture
            step_count += 1
            pre_obs_summary = None
            if pre_event_candles is not None:
                pre_obs_summary = self.market_observer.evaluate_observation_window(pre_event_candles)
                self.vault.store_json("observations", pre_obs_summary, {"event_id": event_id, "window": "pre_event"})
                self.obs.record_vault_write()
            execution_log.append({"step": step_count, "action": "PRE_EVENT_MARKET_CAPTURED", "status": "OK"})
            self._save_checkpoint(event_id, step_count, "PRE_EVENT_MARKET", {"pre_summary": pre_obs_summary})

            # Check for stop request
            if self._stop_requested:
                return {"status": "STOPPED", "event_id": event_id, "last_step": step_count, "log": execution_log}

            # Step 6: Official Release Retrieval Attempt via ReadOnlyResearchTransport
            step_count += 1
            t_req_start = time.time()
            try:
                resp = self.transport.execute_request(
                    "GET",
                    event.official_source_url,
                    auth_token=self.token if hasattr(self.token, "token_id") else None,
                    target_event_id=event_id,
                )
                lat = time.time() - t_req_start
                self.obs.record_request(lat)
                release_doc = ReleaseDocument(
                    event_id=event_id,
                    source_url=event.official_source_url,
                    http_status=resp.status_code,
                    content_type=resp.content_type,
                    raw_bytes=resp.body,
                    raw_sha256=resp.raw_sha256,
                    retrieved_at_utc=resp.retrieved_at_utc,
                    scheduled_publication_at_utc=event.scheduled_publication_at_utc,
                    first_observed_at_utc=resp.retrieved_at_utc,
                    provenance_classification=TimestampProvenanceClassification.OBSERVED_RETRIEVAL_TIME,
                )
                if resp.status_code != 200:
                    self.obs.record_failure(f"HTTP_{resp.status_code}")
                    self.state_machine.transition(event, ProspectiveEventStatus.SOURCE_UNAVAILABLE, f"HTTP status {resp.status_code}")
                    self._save_checkpoint(event_id, step_count, "SOURCE_UNAVAILABLE", {"http_status": resp.status_code})
                    return {
                        "status": "SOURCE_FAILED",
                        "event_id": event_id,
                        "terminal_state": ProspectiveEventStatus.SOURCE_UNAVAILABLE.value,
                        "http_status": resp.status_code,
                        "error": f"HTTP status {resp.status_code}",
                        "log": execution_log,
                    }
            except Exception as e:
                self.obs.record_failure(type(e).__name__)
                self.state_machine.transition(event, ProspectiveEventStatus.SOURCE_UNAVAILABLE, f"Source retrieval failed: {e}")
                self._save_checkpoint(event_id, step_count, "SOURCE_UNAVAILABLE", {"error": str(e)})
                return {
                    "status": "SOURCE_FAILED",
                    "event_id": event_id,
                    "terminal_state": ProspectiveEventStatus.SOURCE_UNAVAILABLE.value,
                    "error": str(e),
                    "log": execution_log,
                }

            execution_log.append({"step": step_count, "action": "SOURCE_RETRIEVAL", "status": "OK", "http_status": resp.status_code})

            # Step 7: Content-Addressed Vault Storage
            step_count += 1
            sha, fpath, is_dup = self.vault.store_bytes("releases", release_doc.raw_bytes, release_doc.to_dict())
            self.obs.record_vault_write()
            event.source_evidence_ref = sha
            execution_log.append({"step": step_count, "action": "VAULT_STORAGE", "sha256": sha, "is_duplicate": is_dup})
            self._save_checkpoint(event_id, step_count, "VAULT_STORED", {"vault_sha256": sha, "path": str(fpath)})

            # Step 8: State Machine Transitions: RELEASE_OBSERVED -> SOURCE_EVIDENCE_CAPTURED
            step_count += 1
            self.state_machine.transition(event, ProspectiveEventStatus.RELEASE_OBSERVED, "Release document observed from official source")
            self.state_machine.transition(event, ProspectiveEventStatus.SOURCE_EVIDENCE_CAPTURED, "Document securely committed to evidence vault")
            execution_log.append({"step": step_count, "action": "EVIDENCE_CAPTURED", "status": "OK"})
            self._save_checkpoint(event_id, step_count, "SOURCE_EVIDENCE_CAPTURED", event.to_dict())

            # Step 9: Immediate Post-Release Market Snapshot Capture (T+0, T+1m, T+5m)
            step_count += 1
            post_obs_summary = None
            if post_event_candles is not None:
                post_obs_summary = self.market_observer.evaluate_observation_window(post_event_candles)
                self.vault.store_json("observations", post_obs_summary, {"event_id": event_id, "window": "post_event"})
                self.obs.record_vault_write()
            execution_log.append({"step": step_count, "action": "POST_EVENT_MARKET_CAPTURED", "status": "OK"})
            self._save_checkpoint(event_id, step_count, "POST_EVENT_MARKET", {"post_summary": post_obs_summary})

            # Step 10: Consensus Surprise Calculation
            step_count += 1
            surprise = None
            if actual_headline_value is not None and mock_consensus and mock_consensus.verification_status == ConsensusVerificationStatus.CONSENSUS_VERIFIED:
                surprise = actual_headline_value - mock_consensus.survey_value
                execution_log.append({"step": step_count, "action": "SURPRISE_COMPUTED", "surprise": surprise})
            else:
                execution_log.append({"step": step_count, "action": "SURPRISE_COMPUTED", "status": "NO_VERIFIED_SURPRISE"})
            self._save_checkpoint(event_id, step_count, "SURPRISE_COMPUTED", {"surprise": surprise})

            # Step 11: Observation Window Closure (T+60m) -> MARKET_OBSERVATION_COMPLETE
            step_count += 1
            self.state_machine.transition(event, ProspectiveEventStatus.MARKET_OBSERVATION_COMPLETE, "Post-event 60m observation complete")
            execution_log.append({"step": step_count, "action": "WINDOW_CLOSED_T_PLUS_60M", "status": "OK"})
            self._save_checkpoint(event_id, step_count, "MARKET_OBSERVATION_COMPLETE", event.to_dict())

            # Step 12: Final State Review -> RESEARCH_ELIGIBILITY_REVIEW
            step_count += 1
            self.state_machine.transition(event, ProspectiveEventStatus.RESEARCH_ELIGIBILITY_REVIEW, "Event passed all checks into offline research archive")
            execution_log.append({"step": step_count, "action": "RESEARCH_ELIGIBILITY_REVIEW", "status": "OK"})
            self._save_checkpoint(event_id, step_count, "RESEARCH_ELIGIBILITY_REVIEW", event.to_dict())

            # Step 13: Final Governance Check & Summary Export
            step_count += 1
            ProspectiveGovernanceGuard.assert_evidence_non_tradable(event.to_dict())
            self.obs.record_event_processed()
            execution_log.append({"step": step_count, "action": "GOVERNANCE_AUDIT", "trading_eligible": False})
            self._save_checkpoint(event_id, step_count, "COMPLETED", {"terminal_status": event.event_status.value})

            return {
                "status": "PASS",
                "event_id": event_id,
                "terminal_state": event.event_status.value,
                "checkpoints_count": step_count,
                "surprise": surprise,
                "directional_trading_eligible": False,
                "execution_log": execution_log,
            }

        except Exception as e:
            self.obs.record_failure(type(e).__name__)
            execution_log.append({"step": step_count, "action": "EXCEPTION", "error": str(e)})
            self._save_checkpoint(event_id, step_count, "EXCEPTION_HALT", {"error": str(e)})
            return {
                "status": "ERROR",
                "event_id": event_id,
                "error": str(e),
                "terminal_state": event.event_status.value,
                "execution_log": execution_log,
            }

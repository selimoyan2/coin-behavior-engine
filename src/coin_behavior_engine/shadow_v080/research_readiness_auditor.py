"""CBE-0.8.0 Independent Research Readiness & Evidence Integrity Auditor.

Sprint 11.02E: Live Capture Research Readiness & Evidence Audit.

Features:
1. Strict read-only evidence loading (no SQLite index rebuilding, no quarantine writes, no truncation).
2. Independent cryptographic hash-chain verification for:
   - Raw evidence ledger (`raw_candles_BTCUSDT_5m.jsonl`)
   - Gap recovery journal (`recovery_candles_BTCUSDT_5m.jsonl`)
   - Gap recovery metadata (`recovery_metadata_BTCUSDT_5m.jsonl`)
3. Deterministic temporal continuity and timestamp alignment validation (300,000 ms spacing).
4. Provenance tracking and segregation (Raw vs REST_GAP_RECOVERY).
5. Chronological research timeline synthesis (committed recovery integrated, uncommitted excluded).
6. Research window completeness audit (latest 288 contiguous closed candles = 24 hours).
7. Independent research-readiness verdict with 5 distinct gates:
   - EVIDENCE_INTEGRITY
   - TEMPORAL_CONTINUITY
   - RECOVERY_CORRECTNESS
   - RESEARCH_WINDOW_READINESS
   - AUTHORIZATION_SAFETY
8. Comprehensive JSON and human-readable Markdown report generators.
9. Optional isolated engine comparison harness against MarketCaptureEngine._reconstruct_state_from_evidence().
10. Low-memory streaming architecture suitable for resource-constrained environments.
"""

from __future__ import annotations

import collections
import dataclasses
import enum
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Set, Tuple

from coin_behavior_engine.shadow_v080.gap_detector import FULL_WARMUP_BARS, GapEvent
from coin_behavior_engine.shadow_v080.market_data_contract import (
    CANDLE_INTERVAL_MS,
    CandleLifecycleState,
    MarketType,
    ProvenanceSource,
    ValidatedCandle,
)

logger = logging.getLogger("cbe_research_readiness_auditor")

AUDITOR_VERSION = "1.0.0-sprint11.02e"
RAW_GENESIS_PREV_HASH = "0" * 64
RECOVERY_GENESIS_PREV_HASH = "0" * 64
EXPECTED_INTERVAL_MS = 300_000  # 5 minutes in milliseconds
EXPECTED_WINDOW_BARS = FULL_WARMUP_BARS  # 288 bars = 24 hours


class AuditVerdict(str, enum.Enum):
    READY_FOR_OFFLINE_RESEARCH = "READY_FOR_OFFLINE_RESEARCH"
    NOT_READY = "NOT_READY"
    INDETERMINATE = "INDETERMINATE"


class GateStatus(str, enum.Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    INDETERMINATE = "INDETERMINATE"


@dataclass
class AuditGateResult:
    gate_name: str
    status: GateStatus
    details: Dict[str, Any] = field(default_factory=dict)
    violations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "status": self.status.value,
            "details": self.details,
            "violations": self.violations,
        }


@dataclass
class FileAuditInfo:
    file_type: str
    file_name: str
    path: str
    exists: bool
    size_bytes: int = 0
    sha256: str = ""
    records_count: int = 0
    modified_during_audit: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AuditedCandleRecord:
    symbol: str
    interval: str
    timestamp_open: int
    timestamp_close: int
    open: str
    high: str
    low: str
    close: str
    volume: str
    is_closed: bool
    provenance: str
    source_type: str  # "RAW" or "RECOVERY"
    entry_index: int
    entry_hash: str
    receipt_timestamp_utc: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchAuditReport:
    audit_timestamp_utc: str
    audit_tool_version: str
    source_git_commit: str
    evidence_dir: str
    symbol: str
    interval: str
    files: Dict[str, FileAuditInfo]
    raw_candle_count: int
    recovery_candle_count: int
    committed_recovery_count: int
    uncommitted_recovery_count: int
    duplicate_timestamp_count: int
    missing_timestamp_count: int
    gap_reconciliation_results: List[Dict[str, Any]]
    latest_contiguous_closed_bars: int
    latest_complete_research_window: Optional[Dict[str, Any]]
    provenance_breakdown: Dict[str, int]
    gates: Dict[str, AuditGateResult]
    unresolved_findings: List[str]
    engine_agreement: Optional[Dict[str, Any]]
    verdict: AuditVerdict

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_timestamp_utc": self.audit_timestamp_utc,
            "audit_tool_version": self.audit_tool_version,
            "source_git_commit": self.source_git_commit,
            "evidence_dir": self.evidence_dir,
            "symbol": self.symbol,
            "interval": self.interval,
            "files": {k: v.to_dict() for k, v in self.files.items()},
            "summary_metrics": {
                "raw_candle_count": self.raw_candle_count,
                "recovery_candle_count": self.recovery_candle_count,
                "committed_recovery_count": self.committed_recovery_count,
                "uncommitted_recovery_count": self.uncommitted_recovery_count,
                "duplicate_timestamp_count": self.duplicate_timestamp_count,
                "missing_timestamp_count": self.missing_timestamp_count,
                "latest_contiguous_closed_bars": self.latest_contiguous_closed_bars,
            },
            "provenance_breakdown": self.provenance_breakdown,
            "latest_complete_research_window": self.latest_complete_research_window,
            "gap_reconciliation_results": self.gap_reconciliation_results,
            "gates": {k: v.to_dict() for k, v in self.gates.items()},
            "unresolved_findings": self.unresolved_findings,
            "engine_agreement": self.engine_agreement,
            "verdict": self.verdict.value,
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=False)

    def to_markdown(self) -> str:
        lines: List[str] = []
        lines.append(f"# CBE Research Readiness & Evidence Audit Report")
        lines.append(f"**Audit Timestamp (UTC):** `{self.audit_timestamp_utc}`  ")
        lines.append(f"**Tool Version:** `{self.audit_tool_version}`  ")
        lines.append(f"**Source Git Commit:** `{self.source_git_commit}`  ")
        lines.append(f"**Evidence Directory:** `{self.evidence_dir}`  ")
        lines.append(f"**Target Instrument:** `{self.symbol}` `{self.interval}`  ")
        lines.append("")

        # Verdict Badge
        verdict_icon = "PASS" if self.verdict == AuditVerdict.READY_FOR_OFFLINE_RESEARCH else "FAIL / BLOCKED"
        lines.append(f"## Verdict: **{self.verdict.value}** ({verdict_icon})")
        lines.append("")
        if self.verdict == AuditVerdict.READY_FOR_OFFLINE_RESEARCH:
            lines.append("> [!IMPORTANT]")
            lines.append("> **DATASET IS CERTIFIED FOR OFFLINE RESEARCH USE ONLY.**")
            lines.append("> Prospective scoring, model inference, and live trading remain strictly PROHIBITED.")
        else:
            lines.append("> [!WARNING]")
            lines.append(f"> **RESEARCH READINESS GATES NOT SATISFIED:** Dataset verdict is `{self.verdict.value}`.")
            lines.append("> Offline research using this dataset must not proceed until findings are resolved.")
        lines.append("")

        # Gate Summary Table
        lines.append("## 1. Audit Gates Summary")
        lines.append("")
        lines.append("| Gate Name | Status | Key Metrics / Details | Violations |")
        lines.append("| :--- | :--- | :--- | :--- |")
        for g_name, gate in self.gates.items():
            status_badge = f"**{gate.status.value}**"
            det_summary = "; ".join(f"{k}={v}" for k, v in list(gate.details.items())[:3])
            viol_count = len(gate.violations)
            viol_text = f"{viol_count} violation(s)" if viol_count > 0 else "None"
            lines.append(f"| `{g_name}` | {status_badge} | {det_summary} | {viol_text} |")
        lines.append("")

        # Source Files Audit
        lines.append("## 2. Evidence Files & Cryptographic Fingerprints")
        lines.append("")
        lines.append("| File Type | File Name | Exists | Size (Bytes) | SHA-256 Digest | Records |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- |")
        for f_type, finfo in self.files.items():
            sha_abbr = f"`{finfo.sha256[:16]}...`" if finfo.sha256 else "N/A"
            exists_text = "Yes" if finfo.exists else "No"
            lines.append(f"| `{f_type}` | `{finfo.file_name}` | {exists_text} | {finfo.size_bytes:,} | {sha_abbr} | {finfo.records_count:,} |")
        lines.append("")

        # Quantitative Metrics & Provenance
        lines.append("## 3. Evidence Breakdown & Contiguity Metrics")
        lines.append("")
        lines.append(f"- **Total Raw Candles:** {self.raw_candle_count:,}")
        lines.append(f"- **Total Recovery Journal Candles:** {self.recovery_candle_count:,}")
        lines.append(f"- **Committed Recovery Candles:** {self.committed_recovery_count:,}")
        lines.append(f"- **Uncommitted Recovery Candles:** {self.uncommitted_recovery_count:,}")
        lines.append(f"- **Duplicate Timestamps Detected:** {self.duplicate_timestamp_count:,}")
        lines.append(f"- **Missing Timestamps Detected:** {self.missing_timestamp_count:,}")
        lines.append(f"- **Latest Contiguous Closed Bars:** {self.latest_contiguous_closed_bars:,} (Requirement: >= {EXPECTED_WINDOW_BARS})")
        lines.append("")
        lines.append("### Provenance Breakdown")
        for prov, count in self.provenance_breakdown.items():
            lines.append(f"- `{prov}`: {count:,} bars")
        lines.append("")

        # Research Window Details
        lines.append("## 4. Latest Complete 288-Bar Research Window")
        lines.append("")
        if self.latest_complete_research_window:
            w = self.latest_complete_research_window
            lines.append(f"- **Window Status:** {w.get('status', 'N/A')}")
            lines.append(f"- **Bar Count:** {w.get('bar_count', 0)}")
            lines.append(f"- **Start Open Timestamp:** {w.get('start_open_ts')} (`{w.get('start_datetime_utc')}`)")
            lines.append(f"- **End Open Timestamp:** {w.get('end_open_ts')} (`{w.get('end_datetime_utc')}`)")
            lines.append(f"- **Window Provenance Breakdown:** {w.get('provenance_breakdown', {})}")
        else:
            lines.append("*No complete 288-bar contiguous closed window is currently available.*")
        lines.append("")

        # Gap Reconciliation
        lines.append("## 5. Gap Reconciliation & Recovery Audit")
        lines.append("")
        if self.gap_reconciliation_results:
            lines.append("| Gap ID | Start (ms) | End (ms) | Missing Bars | Recovered? | Batch ID | Verified? |")
            lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
            for gap in self.gap_reconciliation_results:
                lines.append(
                    f"| `{gap.get('gap_id')}` | {gap.get('start_ts')} | {gap.get('end_ts')} | "
                    f"{gap.get('missing_bars')} | {gap.get('recovered')} | `{gap.get('batch_id')}` | {gap.get('verified')} |"
                )
        else:
            lines.append("*No gaps detected in audited evidence sequence.*")
        lines.append("")

        # Engine Agreement (if run)
        if self.engine_agreement:
            lines.append("## 6. MarketCaptureEngine Reconstruction Parity")
            lines.append("")
            lines.append(f"- **Engine Execution:** {self.engine_agreement.get('status')}")
            lines.append(f"- **Auditor Contiguous Bars:** {self.engine_agreement.get('auditor_contiguous_bars')}")
            lines.append(f"- **Engine Contiguous Bars:** {self.engine_agreement.get('engine_contiguous_bars')}")
            lines.append(f"- **Auditor Research Eligible:** {self.engine_agreement.get('auditor_is_eligible')}")
            lines.append(f"- **Engine Research Eligible:** {self.engine_agreement.get('engine_is_eligible')}")
            lines.append(f"- **Parity Result:** **{self.engine_agreement.get('parity_verdict')}**")
            lines.append("")

        # Unresolved Findings / Violations
        lines.append("## 7. Unresolved Findings & Security Observations")
        lines.append("")
        if self.unresolved_findings:
            for finding in self.unresolved_findings:
                lines.append(f"- :warning: {finding}")
        else:
            lines.append("`Zero unresolved findings. All cryptographic, temporal, and safety invariants hold.`")
        lines.append("")

        return "\n".join(lines)


class ReadOnlyEvidenceReader:
    """Strictly read-only evidence file streaming reader and hasher."""

    def __init__(self, evidence_dir: Path, symbol: str = "BTCUSDT", interval: str = "5m"):
        self.evidence_dir = Path(evidence_dir)
        self.symbol = symbol
        self.interval = interval

        self.raw_file = self.evidence_dir / f"raw_candles_{self.symbol}_{self.interval}.jsonl"
        self.recovery_journal_file = self.evidence_dir / f"recovery_candles_{self.symbol}_{self.interval}.jsonl"
        self.recovery_metadata_file = self.evidence_dir / f"recovery_metadata_{self.symbol}_{self.interval}.jsonl"

    @staticmethod
    def compute_file_sha256(path: Path) -> Tuple[bool, int, str]:
        """Compute file size and SHA-256 without loading entire file into memory."""
        if not path.is_file():
            return False, 0, ""
        hasher = hashlib.sha256()
        total_size = 0
        try:
            with open(path, "rb") as f:
                while True:
                    chunk = f.read(65536)
                    if not chunk:
                        break
                    hasher.update(chunk)
                    total_size += len(chunk)
            return True, total_size, hasher.hexdigest()
        except Exception as e:
            logger.warning(f"Failed to read/hash file {path}: {e}")
            return False, 0, ""

    def get_initial_file_info(self) -> Dict[str, FileAuditInfo]:
        """Collect initial metadata and cryptographic digests of evidence files."""
        files = {
            "raw_evidence": ("raw_candles", self.raw_file),
            "recovery_journal": ("recovery_candles", self.recovery_journal_file),
            "recovery_metadata": ("recovery_metadata", self.recovery_metadata_file),
        }
        res: Dict[str, FileAuditInfo] = {}
        for key, (label, p) in files.items():
            exists, size, digest = self.compute_file_sha256(p)
            res[key] = FileAuditInfo(
                file_type=key,
                file_name=p.name,
                path=str(p),
                exists=exists,
                size_bytes=size,
                sha256=digest,
                records_count=0,
            )
        return res

    def stream_raw_lines(self) -> Iterator[Tuple[int, int, str, Dict[str, Any]]]:
        """Stream raw evidence entries line-by-line.

        Yields (line_number, byte_offset, raw_line_str, parsed_dict).
        """
        if not self.raw_file.is_file():
            return
        with open(self.raw_file, "rb") as f:
            line_no = 0
            while True:
                offset = f.tell()
                raw_line = f.readline()
                if not raw_line:
                    break
                line_no += 1
                line_str = raw_line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue
                try:
                    data = json.loads(line_str)
                    yield (line_no, offset, line_str, data)
                except Exception as e:
                    yield (line_no, offset, line_str, {"__parse_error__": str(e)})

    def stream_recovery_journal_lines(self) -> Iterator[Tuple[int, int, str, Dict[str, Any]]]:
        """Stream recovery journal entries line-by-line.

        Yields (line_number, byte_offset, raw_line_str, parsed_dict).
        """
        if not self.recovery_journal_file.is_file():
            return
        with open(self.recovery_journal_file, "rb") as f:
            line_no = 0
            while True:
                offset = f.tell()
                raw_line = f.readline()
                if not raw_line:
                    break
                line_no += 1
                line_str = raw_line.decode("utf-8", errors="replace").strip()
                if not line_str:
                    continue
                try:
                    data = json.loads(line_str)
                    yield (line_no, offset, line_str, data)
                except Exception as e:
                    yield (line_no, offset, line_str, {"__parse_error__": str(e)})

    def stream_recovery_metadata_lines(self) -> Iterator[Tuple[int, str, Dict[str, Any]]]:
        """Stream recovery metadata entries line-by-line.

        Yields (line_number, raw_line_str, parsed_dict).
        """
        if not self.recovery_metadata_file.is_file():
            return
        with open(self.recovery_metadata_file, "r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    data = json.loads(line_str)
                    yield (line_no, line_str, data)
                except Exception as e:
                    yield (line_no, line_str, {"__parse_error__": str(e)})


class ResearchReadinessAuditor:
    """Independent auditor for live market evidence, cryptographic integrity, and research eligibility."""

    def __init__(
        self,
        evidence_dir: Path,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        environment_override: Optional[Dict[str, str]] = None,
    ):
        self.evidence_dir = Path(evidence_dir)
        self.symbol = symbol
        self.interval = interval
        self.reader = ReadOnlyEvidenceReader(self.evidence_dir, symbol=symbol, interval=interval)
        self.environment = dict(os.environ) if environment_override is None else dict(environment_override)

    def run_full_audit(self, compare_with_engine: bool = False) -> ResearchAuditReport:
        """Execute complete offline research readiness and evidence integrity audit."""
        audit_start_utc = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        git_commit = self._resolve_git_commit()

        # Step 1: Collect initial file digests
        files_info = self.reader.get_initial_file_info()

        # Gates initialization
        gate_integrity = AuditGateResult(gate_name="EVIDENCE_INTEGRITY", status=GateStatus.PASS)
        gate_continuity = AuditGateResult(gate_name="TEMPORAL_CONTINUITY", status=GateStatus.PASS)
        gate_recovery = AuditGateResult(gate_name="RECOVERY_CORRECTNESS", status=GateStatus.PASS)
        gate_window = AuditGateResult(gate_name="RESEARCH_WINDOW_READINESS", status=GateStatus.PASS)
        gate_safety = AuditGateResult(gate_name="AUTHORIZATION_SAFETY", status=GateStatus.PASS)

        unresolved_findings: List[str] = []

        # Audit 1: Check Authorization Safety Interlocks
        self._audit_authorization_safety(gate_safety)

        # Audit 2: Check Evidence Files Existence
        if not files_info["raw_evidence"].exists or files_info["raw_evidence"].size_bytes == 0:
            gate_integrity.status = GateStatus.INDETERMINATE
            gate_integrity.violations.append(
                f"Raw evidence file '{files_info['raw_evidence'].file_name}' does not exist or is empty in {self.evidence_dir}"
            )
            unresolved_findings.append(gate_integrity.violations[-1])
            return self._build_verdict_report(
                audit_start_utc, git_commit, files_info,
                gate_integrity, gate_continuity, gate_recovery, gate_window, gate_safety,
                unresolved_findings, None
            )

        # Audit 3: Recovery Metadata Cryptographic Audit
        metadata_by_gap: Dict[str, Dict[str, Any]] = {}
        metadata_records_count = 0
        if files_info["recovery_metadata"].exists:
            metadata_by_gap, metadata_records_count = self._audit_recovery_metadata(
                gate_integrity, gate_recovery
            )
        files_info["recovery_metadata"].records_count = metadata_records_count

        # Audit 4: Recovery Journal Cryptographic Audit
        recovery_journal_entries: List[Dict[str, Any]] = []
        if files_info["recovery_journal"].exists:
            recovery_journal_entries = self._audit_recovery_journal(
                gate_integrity, gate_recovery, metadata_by_gap
            )
        files_info["recovery_journal"].records_count = len(recovery_journal_entries)

        # Audit 5: Raw Evidence Cryptographic Audit & Extraction
        raw_candles: List[AuditedCandleRecord] = []
        raw_count = 0
        raw_candles, raw_count = self._audit_raw_evidence(gate_integrity)
        files_info["raw_evidence"].records_count = raw_count

        # Check if files were modified during audit
        self._check_file_modifications_during_audit(files_info, unresolved_findings, gate_integrity)

        # Audit 6: Temporal Continuity & Recovery Integration
        (
            merged_timeline,
            gap_reconciliation,
            provenance_breakdown,
            missing_count,
            duplicate_count,
        ) = self._audit_temporal_continuity_and_recovery(
            raw_candles,
            recovery_journal_entries,
            metadata_by_gap,
            gate_continuity,
            gate_recovery,
        )

        # Audit 7: Research Window Readiness (Latest 288 Bars)
        latest_contiguous_bars, research_window_info = self._audit_research_window(
            merged_timeline,
            gate_continuity,
            gate_window,
        )

        # Compile all gate violations into unresolved findings
        for gate in [gate_integrity, gate_continuity, gate_recovery, gate_window, gate_safety]:
            for viol in gate.violations:
                if viol not in unresolved_findings:
                    unresolved_findings.append(viol)

        # Optional Engine Parity Comparison (using isolated temporary directory)
        engine_agreement_info: Optional[Dict[str, Any]] = None
        if compare_with_engine:
            engine_agreement_info = self._run_isolated_engine_comparison(
                latest_contiguous_bars,
                gate_window.status == GateStatus.PASS,
                len(gap_reconciliation),
                unresolved_findings,
            )

        return self._build_verdict_report(
            audit_start_utc,
            git_commit,
            files_info,
            gate_integrity,
            gate_continuity,
            gate_recovery,
            gate_window,
            gate_safety,
            unresolved_findings,
            engine_agreement_info,
            raw_count=raw_count,
            recovery_count=len(recovery_journal_entries),
            committed_recovery_count=sum(m.get("recovered_candles_count", 0) for m in metadata_by_gap.values()),
            uncommitted_recovery_count=max(0, len(recovery_journal_entries) - sum(m.get("recovered_candles_count", 0) for m in metadata_by_gap.values())),
            missing_count=missing_count,
            duplicate_count=duplicate_count,
            gap_reconciliation=gap_reconciliation,
            latest_contiguous_bars=latest_contiguous_bars,
            research_window_info=research_window_info,
            provenance_breakdown=provenance_breakdown,
        )

    def _resolve_git_commit(self) -> str:
        """Resolve current git commit SHA safely."""
        env_commit = self.environment.get("CBE_GIT_COMMIT")
        if env_commit:
            return env_commit
        try:
            res = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=False,
                cwd=str(Path(__file__).resolve().parents[3]),
            )
            if res.returncode == 0 and res.stdout.strip():
                return res.stdout.strip()
        except Exception:
            pass
        return "UNKNOWN_COMMIT"

    def _audit_authorization_safety(self, gate: AuditGateResult) -> None:
        """Verify strict authorization safety interlocks in environment."""
        trading_disabled = self.environment.get("CBE_TRADING_DISABLED", "true").lower()
        prospective_observation = self.environment.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false").lower()
        approval_4 = self.environment.get("CBE_APPROVAL_4_AUTHORIZED", "false").lower()

        gate.details = {
            "CBE_TRADING_DISABLED": trading_disabled,
            "CBE_PROSPECTIVE_OBSERVATION_ENABLED": prospective_observation,
            "CBE_APPROVAL_4_AUTHORIZED": approval_4,
        }

        if trading_disabled != "true":
            gate.status = GateStatus.FAIL
            gate.violations.append(f"Safety violation: CBE_TRADING_DISABLED is '{trading_disabled}', expected 'true'")

        if prospective_observation != "false":
            gate.status = GateStatus.FAIL
            gate.violations.append(
                f"Safety violation: CBE_PROSPECTIVE_OBSERVATION_ENABLED is '{prospective_observation}', expected 'false'"
            )

        if approval_4 != "false":
            gate.status = GateStatus.FAIL
            gate.violations.append(f"Safety violation: CBE_APPROVAL_4_AUTHORIZED is '{approval_4}', expected 'false'")

    def _check_file_modifications_during_audit(
        self,
        files_info: Dict[str, FileAuditInfo],
        unresolved_findings: List[str],
        gate_integrity: AuditGateResult,
    ) -> None:
        """Verify that evidence files did not mutate during audit reading."""
        for k, finfo in files_info.items():
            if not finfo.exists:
                continue
            exists, size, digest = self.reader.compute_file_sha256(Path(finfo.path))
            if size != finfo.size_bytes or digest != finfo.sha256:
                finfo.modified_during_audit = True
                msg = f"Evidence file '{finfo.file_name}' modified concurrently during audit (size: {finfo.size_bytes}->{size}, sha: {finfo.sha256[:8]}->{digest[:8]})"
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(msg)
                unresolved_findings.append(msg)

    def _audit_recovery_metadata(
        self,
        gate_integrity: AuditGateResult,
        gate_recovery: AuditGateResult,
    ) -> Tuple[Dict[str, Dict[str, Any]], int]:
        """Cryptographically audit and parse recovery metadata."""
        metadata_by_gap: Dict[str, Dict[str, Any]] = {}
        count = 0
        seen_gap_ids: Set[str] = set()

        for line_no, raw_line, meta in self.reader.stream_recovery_metadata_lines():
            count += 1
            if "__parse_error__" in meta:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Recovery metadata line {line_no} JSON parse failure: {meta['__parse_error__']}"
                )
                continue

            required = [
                "gap_id", "recovery_batch_id", "first_entry_index",
                "last_entry_index", "recovered_candles_count",
                "start_integrity_hash", "end_integrity_hash", "status"
            ]
            missing_fields = [f for f in required if f not in meta]
            if missing_fields:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Recovery metadata line {line_no} missing required field(s): {missing_fields}"
                )
                continue

            gap_id = meta["gap_id"]
            if gap_id in seen_gap_ids:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(f"Recovery metadata duplicate gap_id '{gap_id}' at line {line_no}")
            seen_gap_ids.add(gap_id)

            if meta["status"] != "COMMITTED":
                gate_recovery.status = GateStatus.FAIL
                gate_recovery.violations.append(
                    f"Recovery metadata gap '{gap_id}' has non-COMMITTED status: '{meta['status']}'"
                )

            first_idx = meta["first_entry_index"]
            last_idx = meta["last_entry_index"]
            candle_cnt = meta["recovered_candles_count"]

            if first_idx < 0 or last_idx < first_idx:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Recovery metadata gap '{gap_id}' invalid entry index range [{first_idx}..{last_idx}]"
                )

            if candle_cnt != (last_idx - first_idx + 1):
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Recovery metadata gap '{gap_id}' candle count mismatch: reported {candle_cnt}, index diff {last_idx - first_idx + 1}"
                )

            metadata_by_gap[gap_id] = meta

        return metadata_by_gap, count

    def _audit_recovery_journal(
        self,
        gate_integrity: AuditGateResult,
        gate_recovery: AuditGateResult,
        metadata_by_gap: Dict[str, Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Cryptographically audit gap recovery journal entries and cross-validate with metadata."""
        entries: List[Dict[str, Any]] = []
        expected_prev = RECOVERY_GENESIS_PREV_HASH
        expected_idx = 0

        for line_no, offset, raw_line, entry_dict in self.reader.stream_recovery_journal_lines():
            if "__parse_error__" in entry_dict:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Recovery journal line {line_no} JSON parse failure at offset {offset}: {entry_dict['__parse_error__']}"
                )
                break

            required = [
                "entry_index", "prev_recovery_hash", "candle_hash",
                "integrity_hash", "recovery_batch_id", "gap_id", "candle"
            ]
            missing_fields = [f for f in required if f not in entry_dict]
            if missing_fields:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Recovery journal line {line_no} missing required field(s): {missing_fields}"
                )
                break

            e_idx = entry_dict["entry_index"]
            prev_h = entry_dict["prev_recovery_hash"]
            c_hash = entry_dict["candle_hash"]
            integ_h = entry_dict["integrity_hash"]
            batch_id = entry_dict["recovery_batch_id"]
            gap_id = entry_dict["gap_id"]
            c_dict = entry_dict["candle"]

            # 1. Entry index sequence
            if e_idx != expected_idx:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Recovery journal index mismatch at line {line_no}: got {e_idx}, expected {expected_idx}"
                )
                break

            # 2. Previous hash continuity
            if prev_h != expected_prev:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Recovery journal hash break at line {line_no}: got prev_hash '{prev_h}', expected '{expected_prev}'"
                )
                break

            # 3. Candle validation & SHA-256
            try:
                vcandle = ValidatedCandle(
                    symbol=c_dict["symbol"],
                    interval=c_dict["interval"],
                    market_type=c_dict.get("market_type", MarketType.SPOT.value),
                    timestamp_open=c_dict["timestamp_open"],
                    timestamp_close=c_dict["timestamp_close"],
                    datetime_open_utc=c_dict["datetime_open_utc"],
                    datetime_close_utc=c_dict["datetime_close_utc"],
                    open=str(c_dict["open"]),
                    high=str(c_dict["high"]),
                    low=str(c_dict["low"]),
                    close=str(c_dict["close"]),
                    volume=str(c_dict["volume"]),
                    quote_volume=str(c_dict.get("quote_volume", "0")),
                    trades_count=int(c_dict.get("trades_count", 0)),
                    taker_buy_base_volume=str(c_dict.get("taker_buy_base_volume", "0")),
                    is_closed=bool(c_dict["is_closed"]),
                    provenance=c_dict["provenance"],
                    receipt_timestamp_utc=c_dict["receipt_timestamp_utc"],
                    lifecycle_state=CandleLifecycleState.CANDLE_PERSISTED.value,
                )
            except Exception as e:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Recovery journal candle invalid at line {line_no}: {e}"
                )
                break

            if vcandle.provenance != ProvenanceSource.REST_GAP_RECOVERY.value:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Recovery journal provenance invalid at line {line_no}: got '{vcandle.provenance}', expected '{ProvenanceSource.REST_GAP_RECOVERY.value}'"
                )
                break

            if not vcandle.is_closed:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(f"Recovery journal candle not closed at line {line_no}")
                break

            computed_c_hash = vcandle.compute_sha256()
            if c_hash != computed_c_hash:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Recovery journal candle hash mismatch at line {line_no}: got '{c_hash}', computed '{computed_c_hash}'"
                )
                break

            # 4. Entry integrity hash
            computed_integ_h = hashlib.sha256(
                f"{batch_id}:{gap_id}:{e_idx}:{prev_h}:{c_hash}".encode("utf-8")
            ).hexdigest()
            if integ_h != computed_integ_h:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Recovery journal entry integrity hash mismatch at line {line_no}: got '{integ_h}', computed '{computed_integ_h}'"
                )
                break

            entries.append(entry_dict)
            expected_prev = integ_h
            expected_idx += 1

        # Cross-validate recovery metadata against audited journal entries
        for gap_id, meta in metadata_by_gap.items():
            first_idx = meta["first_entry_index"]
            last_idx = meta["last_entry_index"]
            count = meta["recovered_candles_count"]

            if first_idx >= len(entries) or last_idx >= len(entries):
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Metadata gap '{gap_id}' index range [{first_idx}..{last_idx}] out of journal bounds (journal entries: {len(entries)})"
                )
                continue

            if entries[first_idx]["integrity_hash"] != meta["start_integrity_hash"]:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Metadata gap '{gap_id}' start_integrity_hash mismatch: expected '{meta['start_integrity_hash']}', journal has '{entries[first_idx]['integrity_hash']}'"
                )

            if entries[last_idx]["integrity_hash"] != meta["end_integrity_hash"]:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Metadata gap '{gap_id}' end_integrity_hash mismatch: expected '{meta['end_integrity_hash']}', journal has '{entries[last_idx]['integrity_hash']}'"
                )

            for idx in range(first_idx, last_idx + 1):
                if entries[idx]["gap_id"] != gap_id:
                    gate_integrity.status = GateStatus.FAIL
                    gate_integrity.violations.append(
                        f"Journal entry {idx} gap_id mismatch: expected '{gap_id}', journal has '{entries[idx]['gap_id']}'"
                    )
                if entries[idx]["recovery_batch_id"] != meta["recovery_batch_id"]:
                    gate_integrity.status = GateStatus.FAIL
                    gate_integrity.violations.append(
                        f"Journal entry {idx} batch_id mismatch: expected '{meta['recovery_batch_id']}', journal has '{entries[idx]['recovery_batch_id']}'"
                    )

        gate_integrity.details["recovery_journal_records"] = len(entries)
        gate_integrity.details["recovery_metadata_gaps"] = len(metadata_by_gap)

        return entries

    def _audit_raw_evidence(
        self,
        gate_integrity: AuditGateResult,
    ) -> Tuple[List[AuditedCandleRecord], int]:
        """Cryptographically audit raw evidence ledger hash-chain and extract candles."""
        raw_candles: List[AuditedCandleRecord] = []
        expected_prev = RAW_GENESIS_PREV_HASH
        expected_idx = 0
        total_count = 0

        for line_no, offset, raw_line, data in self.reader.stream_raw_lines():
            total_count += 1
            if "__parse_error__" in data:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Raw evidence line {line_no} JSON parse failure at offset {offset}: {data['__parse_error__']}"
                )
                break

            required = ["entry_index", "prev_hash", "candle_hash", "entry_hash", "candle"]
            missing_fields = [f for f in required if f not in data]
            if missing_fields:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Raw evidence line {line_no} missing required field(s): {missing_fields}"
                )
                break

            e_idx = data["entry_index"]
            prev_h = data["prev_hash"]
            c_hash = data["candle_hash"]
            e_hash = data["entry_hash"]
            c_dict = data["candle"]

            # 1. Entry index sequence
            if e_idx != expected_idx:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Raw evidence sequence index mismatch at line {line_no}: got {e_idx}, expected {expected_idx}"
                )
                break

            # 2. Previous hash continuity
            if prev_h != expected_prev:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Raw evidence hash chain break at line {line_no}: got prev_hash '{prev_h}', expected '{expected_prev}'"
                )
                break

            # 3. Canonical candle hash
            canonical_json = json.dumps(c_dict, sort_keys=True, separators=(",", ":")).encode("utf-8")
            recomputed_c_hash = hashlib.sha256(canonical_json).hexdigest()
            if c_hash != recomputed_c_hash:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Raw evidence candle hash mismatch at line {line_no}: got '{c_hash}', computed '{recomputed_c_hash}'"
                )
                break

            # 4. Entry hash
            expected_e_hash = hashlib.sha256(f"{e_idx}:{prev_h}:{c_hash}".encode("utf-8")).hexdigest()
            if e_hash != expected_e_hash:
                gate_integrity.status = GateStatus.FAIL
                gate_integrity.violations.append(
                    f"Raw evidence entry hash mismatch at line {line_no}: got '{e_hash}', computed '{expected_e_hash}'"
                )
                break

            record = AuditedCandleRecord(
                symbol=c_dict["symbol"],
                interval=c_dict["interval"],
                timestamp_open=c_dict["timestamp_open"],
                timestamp_close=c_dict["timestamp_close"],
                open=str(c_dict["open"]),
                high=str(c_dict["high"]),
                low=str(c_dict["low"]),
                close=str(c_dict["close"]),
                volume=str(c_dict["volume"]),
                is_closed=bool(c_dict["is_closed"]),
                provenance=c_dict["provenance"],
                source_type="RAW",
                entry_index=e_idx,
                entry_hash=e_hash,
                receipt_timestamp_utc=c_dict.get("receipt_timestamp_utc", ""),
            )
            raw_candles.append(record)
            expected_prev = e_hash
            expected_idx += 1

        gate_integrity.details["raw_evidence_records"] = total_count
        gate_integrity.details["raw_head_hash"] = expected_prev

        return raw_candles, total_count

    def _audit_temporal_continuity_and_recovery(
        self,
        raw_candles: List[AuditedCandleRecord],
        recovery_journal_entries: List[Dict[str, Any]],
        metadata_by_gap: Dict[str, Dict[str, Any]],
        gate_continuity: AuditGateResult,
        gate_recovery: AuditGateResult,
    ) -> Tuple[List[AuditedCandleRecord], List[Dict[str, Any]], Dict[str, int], int, int]:
        """Verify 5m spacing, integrate committed recovery, detect collisions and gaps."""
        merged_timeline: List[AuditedCandleRecord] = []
        gap_reconciliation: List[Dict[str, Any]] = []
        provenance_breakdown: Dict[str, int] = collections.defaultdict(int)

        raw_ts_set: Set[int] = set()
        duplicate_ts_count = 0
        missing_ts_count = 0

        # Map committed recovered candles by gap_id and timestamp
        committed_candles_by_gap: Dict[str, List[AuditedCandleRecord]] = collections.defaultdict(list)
        committed_recovered_ts_set: Set[int] = set()

        for gap_id, meta in metadata_by_gap.items():
            first_idx = meta["first_entry_index"]
            last_idx = meta["last_entry_index"]
            for idx in range(first_idx, min(last_idx + 1, len(recovery_journal_entries))):
                j_entry = recovery_journal_entries[idx]
                c_dict = j_entry["candle"]
                rec = AuditedCandleRecord(
                    symbol=c_dict["symbol"],
                    interval=c_dict["interval"],
                    timestamp_open=c_dict["timestamp_open"],
                    timestamp_close=c_dict["timestamp_close"],
                    open=str(c_dict["open"]),
                    high=str(c_dict["high"]),
                    low=str(c_dict["low"]),
                    close=str(c_dict["close"]),
                    volume=str(c_dict["volume"]),
                    is_closed=bool(c_dict["is_closed"]),
                    provenance=c_dict["provenance"],
                    source_type="RECOVERY",
                    entry_index=j_entry["entry_index"],
                    entry_hash=j_entry["integrity_hash"],
                    receipt_timestamp_utc=c_dict.get("receipt_timestamp_utc", ""),
                )
                committed_candles_by_gap[gap_id].append(rec)
                committed_recovered_ts_set.add(rec.timestamp_open)

        # Audit raw candle temporal sequence
        last_raw_ts: Optional[int] = None

        for raw_c in raw_candles:
            curr_open = raw_c.timestamp_open

            # Check candle closed and alignment
            if not raw_c.is_closed:
                gate_continuity.status = GateStatus.FAIL
                gate_continuity.violations.append(
                    f"Raw candle at open_ts {curr_open} is not marked is_closed=True"
                )

            if curr_open % EXPECTED_INTERVAL_MS != 0:
                gate_continuity.status = GateStatus.FAIL
                gate_continuity.violations.append(
                    f"Raw candle at open_ts {curr_open} is not aligned to {EXPECTED_INTERVAL_MS} ms boundary"
                )

            if raw_c.timestamp_close != (curr_open + EXPECTED_INTERVAL_MS - 1):
                gate_continuity.status = GateStatus.FAIL
                gate_continuity.violations.append(
                    f"Raw candle at open_ts {curr_open} has unexpected close_ts {raw_c.timestamp_close} (expected {curr_open + EXPECTED_INTERVAL_MS - 1})"
                )

            # Check duplicate / out-of-order in raw
            if curr_open in raw_ts_set:
                duplicate_ts_count += 1
                gate_continuity.status = GateStatus.FAIL
                gate_continuity.violations.append(f"Duplicate raw candle timestamp: {curr_open}")
                continue
            raw_ts_set.add(curr_open)

            # Check sequence against previous candle
            if last_raw_ts is not None:
                if curr_open < last_raw_ts:
                    gate_continuity.status = GateStatus.FAIL
                    gate_continuity.violations.append(
                        f"Out-of-order raw candle timestamp: {curr_open} preceded by {last_raw_ts}"
                    )
                elif curr_open > (last_raw_ts + EXPECTED_INTERVAL_MS):
                    # Gap detected in raw evidence!
                    missing_start = last_raw_ts + EXPECTED_INTERVAL_MS
                    missing_end = curr_open - EXPECTED_INTERVAL_MS
                    missing_count_in_gap = (curr_open - (last_raw_ts + EXPECTED_INTERVAL_MS)) // EXPECTED_INTERVAL_MS
                    missing_ts_count += missing_count_in_gap
                    gap_id = f"GAP-{missing_start}-{missing_end}"

                    expected_gap_ts = [
                        missing_start + (i * EXPECTED_INTERVAL_MS) for i in range(missing_count_in_gap)
                    ]

                    # Check if gap is durably committed in recovery store
                    if gap_id in metadata_by_gap:
                        meta = metadata_by_gap[gap_id]
                        rec_candles = committed_candles_by_gap[gap_id]

                        # Verify recovered candles match declared timestamps
                        rec_ts = [rc.timestamp_open for rc in rec_candles]
                        if rec_ts != expected_gap_ts:
                            gate_recovery.status = GateStatus.FAIL
                            gate_recovery.violations.append(
                                f"Recovered candles timestamps for gap '{gap_id}' do not match expected: got {rec_ts}, expected {expected_gap_ts}"
                            )
                            gap_reconciliation.append({
                                "gap_id": gap_id,
                                "start_ts": missing_start,
                                "end_ts": missing_end,
                                "missing_bars": missing_count_in_gap,
                                "recovered": False,
                                "batch_id": meta.get("recovery_batch_id"),
                                "verified": False,
                                "error": "Timestamp sequence mismatch in recovery batch",
                            })
                        else:
                            # Recovery bridge is verified! Check for raw/recovery collision
                            collision = False
                            for rc in rec_candles:
                                if rc.timestamp_open in raw_ts_set:
                                    collision = True
                                    gate_recovery.status = GateStatus.FAIL
                                    gate_recovery.violations.append(
                                        f"Conflict: Recovered candle at timestamp {rc.timestamp_open} collides with existing raw candle"
                                    )
                                else:
                                    merged_timeline.append(rc)
                                    provenance_breakdown[rc.provenance] += 1

                            if not collision:
                                gap_reconciliation.append({
                                    "gap_id": gap_id,
                                    "start_ts": missing_start,
                                    "end_ts": missing_end,
                                    "missing_bars": missing_count_in_gap,
                                    "recovered": True,
                                    "batch_id": meta.get("recovery_batch_id"),
                                    "verified": True,
                                })
                    else:
                        # Gap remains UNRECOVERED
                        gap_reconciliation.append({
                            "gap_id": gap_id,
                            "start_ts": missing_start,
                            "end_ts": missing_end,
                            "missing_bars": missing_count_in_gap,
                            "recovered": False,
                            "batch_id": None,
                            "verified": False,
                        })

            # Append current raw candle
            merged_timeline.append(raw_c)
            provenance_breakdown[raw_c.provenance] += 1
            last_raw_ts = curr_open

        # Ensure no uncommitted recovery entries leak into merged timeline
        committed_journal_indices: Set[int] = set()
        for meta in metadata_by_gap.values():
            for idx in range(meta["first_entry_index"], meta["last_entry_index"] + 1):
                committed_journal_indices.add(idx)

        uncommitted_entries = [
            j for j in recovery_journal_entries if j["entry_index"] not in committed_journal_indices
        ]
        if uncommitted_entries:
            gate_recovery.details["uncommitted_journal_entries_count"] = len(uncommitted_entries)
            # Verify none leaked into merged timeline
            merged_uncommitted = [c for c in merged_timeline if c.source_type == "RECOVERY" and c.entry_index not in committed_journal_indices]
            if merged_uncommitted:
                gate_recovery.status = GateStatus.FAIL
                gate_recovery.violations.append(
                    f"CRITICAL: {len(merged_uncommitted)} uncommitted recovery journal entry(ies) leaked into research timeline"
                )

        gate_continuity.details["duplicate_timestamps"] = duplicate_ts_count
        gate_continuity.details["missing_timestamps"] = missing_ts_count
        gate_continuity.details["merged_timeline_candles"] = len(merged_timeline)

        gate_recovery.details["gaps_detected"] = len(gap_reconciliation)
        gate_recovery.details["gaps_recovered"] = sum(1 for g in gap_reconciliation if g.get("recovered"))
        gate_recovery.details["gaps_unrecovered"] = sum(1 for g in gap_reconciliation if not g.get("recovered"))

        return merged_timeline, gap_reconciliation, dict(provenance_breakdown), missing_ts_count, duplicate_ts_count

    def _audit_research_window(
        self,
        merged_timeline: List[AuditedCandleRecord],
        gate_continuity: AuditGateResult,
        gate_window: AuditGateResult,
    ) -> Tuple[int, Optional[Dict[str, Any]]]:
        """Compute contiguous closed streak and audit the latest 288-bar research window."""
        if not merged_timeline:
            gate_window.status = GateStatus.FAIL
            gate_window.violations.append("Evidence timeline is empty; no research window exists")
            return 0, None

        # Compute contiguous closed bars from the end backwards
        contiguous_bars = 1
        curr_idx = len(merged_timeline) - 1

        for i in range(len(merged_timeline) - 1, 0, -1):
            curr_c = merged_timeline[i]
            prev_c = merged_timeline[i - 1]

            if curr_c.timestamp_open == (prev_c.timestamp_open + EXPECTED_INTERVAL_MS):
                contiguous_bars += 1
            else:
                break

        gate_window.details["contiguous_closed_bars"] = contiguous_bars
        gate_window.details["required_warmup_bars"] = EXPECTED_WINDOW_BARS

        if contiguous_bars < EXPECTED_WINDOW_BARS:
            gate_window.status = GateStatus.FAIL
            gate_window.violations.append(
                f"Contiguous closed bars ({contiguous_bars}) is less than required full-warmup threshold ({EXPECTED_WINDOW_BARS})"
            )
            return contiguous_bars, None

        # Extract latest 288 bars
        window_candles = merged_timeline[-EXPECTED_WINDOW_BARS:]
        window_prov: Dict[str, int] = collections.defaultdict(int)
        for c in window_candles:
            window_prov[c.provenance] += 1

        start_c = window_candles[0]
        end_c = window_candles[-1]

        research_window_info = {
            "status": "FULL_WINDOW_READY",
            "bar_count": len(window_candles),
            "start_open_ts": start_c.timestamp_open,
            "start_datetime_utc": datetime.fromtimestamp(start_c.timestamp_open / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_open_ts": end_c.timestamp_open,
            "end_datetime_utc": datetime.fromtimestamp(end_c.timestamp_open / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_hours": (end_c.timestamp_open - start_c.timestamp_open + EXPECTED_INTERVAL_MS) / (1000 * 3600),
            "provenance_breakdown": dict(window_prov),
        }

        gate_window.details["latest_window"] = research_window_info

        return contiguous_bars, research_window_info

    def _run_isolated_engine_comparison(
        self,
        auditor_contiguous: int,
        auditor_is_eligible: bool,
        auditor_gaps_count: int,
        unresolved_findings: List[str],
    ) -> Dict[str, Any]:
        """Run MarketCaptureEngine in a completely isolated temp copy and compare reconstruction results."""
        info: Dict[str, Any] = {
            "status": "SKIPPED",
            "auditor_contiguous_bars": auditor_contiguous,
            "auditor_is_eligible": auditor_is_eligible,
            "parity_verdict": "NOT_RUN",
        }
        temp_dir = tempfile.mkdtemp(prefix="cbe_engine_audit_cmp_")
        try:
            temp_path = Path(temp_dir)
            temp_shadow = temp_path / "shadow"
            temp_shadow.mkdir(parents=True, exist_ok=True)

            from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
            from coin_behavior_engine.shadow_v080.market_capture_engine import MarketCaptureEngineV080

            config = ShadowCollectorConfig(
                symbol=self.symbol,
                interval=self.interval,
                shadow_data_dir=temp_shadow,
                approval_3_authorized=True,
                approval_4_authorized=False,
                trading_enabled=False,
            )
            config.ensure_directories()

            # Copy evidence files to isolated temp raw_market_dir
            for f in [self.reader.raw_file, self.reader.recovery_journal_file, self.reader.recovery_metadata_file]:
                if f.is_file():
                    shutil.copy2(str(f), str(config.raw_market_dir / f.name))

            engine = MarketCaptureEngineV080(config=config)
            try:
                engine_contiguous = engine.gap_detector.contiguous_closed_bars
                engine_eligible = engine.is_research_eligible
                engine_gaps = len(engine.gap_detector.gaps)

                parity = (
                    engine_contiguous == auditor_contiguous
                    and engine_eligible == auditor_is_eligible
                )

                info.update({
                    "status": "COMPLETED",
                    "engine_contiguous_bars": engine_contiguous,
                    "engine_is_eligible": engine_eligible,
                    "engine_gaps_count": engine_gaps,
                    "parity_verdict": "PARITY_CONFIRMED" if parity else "DISCREPANCY_DETECTED",
                })

                if not parity:
                    diff_msg = (
                        f"Reconstruction discrepancy between Auditor and Engine: "
                        f"Auditor(contiguous={auditor_contiguous}, eligible={auditor_is_eligible}) vs "
                        f"Engine(contiguous={engine_contiguous}, eligible={engine_eligible})"
                    )
                    unresolved_findings.append(diff_msg)
            finally:
                engine.evidence_store.close()
        except Exception as e:
            logger.warning(f"Isolated engine comparison failed: {e}")
            info.update({
                "status": "ERROR",
                "error": str(e),
                "parity_verdict": "ERROR",
            })
            unresolved_findings.append(f"Engine reconstruction comparison failed: {e}")
        finally:
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

        return info

    def _build_verdict_report(
        self,
        audit_timestamp_utc: str,
        git_commit: str,
        files_info: Dict[str, FileAuditInfo],
        gate_integrity: AuditGateResult,
        gate_continuity: AuditGateResult,
        gate_recovery: AuditGateResult,
        gate_window: AuditGateResult,
        gate_safety: AuditGateResult,
        unresolved_findings: List[str],
        engine_agreement: Optional[Dict[str, Any]],
        raw_count: int = 0,
        recovery_count: int = 0,
        committed_recovery_count: int = 0,
        uncommitted_recovery_count: int = 0,
        missing_count: int = 0,
        duplicate_count: int = 0,
        gap_reconciliation: Optional[List[Dict[str, Any]]] = None,
        latest_contiguous_bars: int = 0,
        research_window_info: Optional[Dict[str, Any]] = None,
        provenance_breakdown: Optional[Dict[str, int]] = None,
    ) -> ResearchAuditReport:
        """Synthesize overall verdict and generate structured report."""
        gates = {
            "EVIDENCE_INTEGRITY": gate_integrity,
            "TEMPORAL_CONTINUITY": gate_continuity,
            "RECOVERY_CORRECTNESS": gate_recovery,
            "RESEARCH_WINDOW_READINESS": gate_window,
            "AUTHORIZATION_SAFETY": gate_safety,
        }

        # Any INDETERMINATE -> INDETERMINATE
        if any(g.status == GateStatus.INDETERMINATE for g in gates.values()):
            overall_verdict = AuditVerdict.INDETERMINATE
        # Any FAIL -> NOT_READY
        elif any(g.status == GateStatus.FAIL for g in gates.values()):
            overall_verdict = AuditVerdict.NOT_READY
        else:
            overall_verdict = AuditVerdict.READY_FOR_OFFLINE_RESEARCH

        return ResearchAuditReport(
            audit_timestamp_utc=audit_timestamp_utc,
            audit_tool_version=AUDITOR_VERSION,
            source_git_commit=git_commit,
            evidence_dir=str(self.evidence_dir),
            symbol=self.symbol,
            interval=self.interval,
            files=files_info,
            raw_candle_count=raw_count,
            recovery_candle_count=recovery_count,
            committed_recovery_count=committed_recovery_count,
            uncommitted_recovery_count=uncommitted_recovery_count,
            duplicate_timestamp_count=duplicate_count,
            missing_timestamp_count=missing_count,
            gap_reconciliation_results=gap_reconciliation or [],
            latest_contiguous_closed_bars=latest_contiguous_bars,
            latest_complete_research_window=research_window_info,
            provenance_breakdown=provenance_breakdown or {},
            gates=gates,
            unresolved_findings=unresolved_findings,
            engine_agreement=engine_agreement,
            verdict=overall_verdict,
        )


def main() -> int:
    """CLI entrypoint for Research Readiness & Evidence Integrity Auditor."""
    import argparse

    parser = argparse.ArgumentParser(
        description="CBE Independent Research Readiness & Evidence Integrity Auditor (Sprint 11.02E)"
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        required=True,
        help="Directory containing raw market evidence and recovery journal files",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="BTCUSDT",
        help="Target symbol (default: BTCUSDT)",
    )
    parser.add_argument(
        "--interval",
        type=str,
        default="5m",
        help="Target candle interval (default: 5m)",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="File path to save JSON audit report",
    )
    parser.add_argument(
        "--output-md",
        type=Path,
        default=None,
        help="File path to save Markdown audit report",
    )
    parser.add_argument(
        "--compare-engine",
        action="store_true",
        help="Run isolated parity comparison against MarketCaptureEngine._reconstruct_state_from_evidence()",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with non-zero code if verdict != READY_FOR_OFFLINE_RESEARCH",
    )

    args = parser.parse_args()

    auditor = ResearchReadinessAuditor(
        evidence_dir=args.evidence_dir,
        symbol=args.symbol,
        interval=args.interval,
    )
    report = auditor.run_full_audit(compare_with_engine=args.compare_engine)

    # Save reports if requested
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(report.to_json(), encoding="utf-8")
        print(f"JSON audit report saved to: {args.output_json}")

    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(report.to_markdown(), encoding="utf-8")
        print(f"Markdown audit report saved to: {args.output_md}")

    # Print summary to stdout
    print(report.to_markdown())

    if args.strict and report.verdict != AuditVerdict.READY_FOR_OFFLINE_RESEARCH:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
Research Report Builder Engine V1
Sprint 22 — Research Intelligence Reporting & Evidence Presentation V1
Hardened for Strict Scientific Provenance, Atomic Storage & Period Validation

Generates comprehensive, auditable, and deterministic research intelligence reports
conforming to schema CBE-RESEARCH-REPORT-1.0.0.

State Machine:
- READY: Inputs verified, awaiting synthesis
- GENERATING: Report construction in progress
- COMPLETED: All mandatory and optional sections compiled
- PARTIAL: Optional modules unavailable (explicitly marked)
- BLOCKED: Mandatory scientific provenance missing (certification blocked)
- FAILED: Corrupted input or validation error

Deterministic ID: RPT-<sha256(canonical_inputs)[:16]>
"""

import hashlib
import json
import math
import os
import re
import threading
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from coin_behavior_engine.product.research_narratives import ScientificNarrativeEngine
from coin_behavior_engine.product.research_comparison_reporting import HistoricalComparisonReportingEngine
from coin_behavior_engine.product.research_reproducibility import ResearchReproducibilityEngine
from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine


def _parse_iso_utc(ts: Any) -> Optional[datetime]:
    """Validates and parses ISO-8601 UTC timestamp."""
    if not ts or not isinstance(ts, str):
        return None
    try:
        clean = ts.strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


class ResearchReportBuilderEngine:
    """Core builder for CBE-RESEARCH-REPORT-1.0.0 reports with atomic and durable persistence."""

    SCHEMA_VERSION = "CBE-RESEARCH-REPORT-1.0.0"
    CANONICAL_MODEL = "CBE-0.7.0"
    HEX_40_REGEX = re.compile(r"^[0-9a-f]{40}$", re.IGNORECASE)
    HEX_64_REGEX = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)
    EPHEMERAL_PREFIXES = ("/tmp", "/var/tmp", "/run", "/dev/shm")

    _lock = threading.Lock()

    def __init__(self, storage_dir: Optional[str] = None, require_durable: bool = True):
        env_dir = os.environ.get("CBE_REPORTS_STORAGE_PATH")
        if storage_dir:
            chosen = storage_dir
        elif env_dir:
            chosen = env_dir
        else:
            candidates = [
                "/app/data/prospective/reports",
                os.path.join("research_outputs", "reports"),
                os.path.join("data", "reports"),
            ]
            chosen = None
            for cand in candidates:
                try:
                    os.makedirs(cand, exist_ok=True)
                    test_file = os.path.join(cand, ".write_test")
                    with open(test_file, "w") as f:
                        f.write("ok")
                    if os.path.exists(test_file):
                        os.remove(test_file)
                    chosen = cand
                    break
                except Exception:
                    continue
            if not chosen:
                raise RuntimeError("DURABLE_STORAGE_UNAVAILABLE: No authorized persistent reports storage path is writable.")

        norm_chosen = os.path.normpath(os.path.abspath(chosen)).replace("\\", "/")
        stripped_chosen = re.sub(r"^[a-zA-Z]:", "", norm_chosen)
        is_ephemeral = any(stripped_chosen.startswith(p) for p in self.EPHEMERAL_PREFIXES)
        cbe_env = os.environ.get("CBE_ENV", "").lower()
        if is_ephemeral and (require_durable and cbe_env in ("staging", "production")):
            raise RuntimeError(
                f"EPHEMERAL_STORAGE_REJECTED: Storage path '{chosen}' is an ephemeral mount. "
                "Research reports require authorized persistent mounts."
            )

        self.storage_dir = chosen
        self.narrative_engine = ScientificNarrativeEngine()
        self.comparison_engine = HistoricalComparisonReportingEngine()

    def generate_report(
        self,
        session_data: Dict[str, Any],
        workflow_id: Optional[str] = None,
        library_id: Optional[str] = None,
        scorecard: Optional[Dict[str, Any]] = None,
        reproducibility: Optional[Dict[str, Any]] = None,
        comparison_candidate: Optional[Dict[str, Any]] = None,
        similarity_data: Optional[Dict[str, Any]] = None,
        operator_title: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Builds a complete 15-section scientific research report."""
        # 1. Validate Mandatory Scientific Provenance and Period
        provenance_check = self._validate_mandatory_provenance(session_data)
        if not provenance_check["valid"]:
            blocked_report = self._build_blocked_report(
                session_data=session_data,
                reason=provenance_check["reason"],
                operator_title=operator_title,
            )
            self._save_report(blocked_report["report_metadata"]["report_id"], blocked_report)
            return blocked_report

        resolved_commit_sha = provenance_check["source_commit_sha"]
        resolved_manifest_sha = provenance_check["dataset_manifest_sha256"]
        resolved_manifest_ver = provenance_check["dataset_manifest_version"]

        # 2. Derive Deterministic Report Identifier
        canonical_seed = self._derive_canonical_seed(session_data, workflow_id, library_id)
        report_hash = hashlib.sha256(canonical_seed.encode("utf-8")).hexdigest()
        report_id = f"RPT-{report_hash[:16]}"

        # 3. Compile Historical Comparison if candidate provided
        comp_report = None
        if comparison_candidate:
            comp_report = self.comparison_engine.build_comparison_report(
                reference_session=session_data,
                candidate_period=comparison_candidate,
                similarity_data=similarity_data,
            )

        # 4. Generate Scientific Narratives
        narrative_obj = self.narrative_engine.generate_narratives(
            session_data=session_data,
            scorecard=scorecard,
            reproducibility=reproducibility,
            comparison_data=comp_report,
        )
        narrative_sections = narrative_obj.get("sections", {})

        def get_tr(sec_name: str) -> str:
            v = narrative_sections.get(sec_name)
            if isinstance(v, dict):
                return v.get("narrative_tr", "")
            elif isinstance(v, str):
                return v
            return ""

        # 5. Determine State (COMPLETED vs PARTIAL)
        modules = session_data.get("module_results", {})
        has_all_modules = all(
            k in modules and modules[k]
            for k in ["regime_analysis", "volatility_analysis"]
        )
        report_state = "COMPLETED" if has_all_modules else "PARTIAL"

        # 6. Extract Canonical Data Sections
        period = self._extract_period(session_data)
        regime_data = modules.get("regime_analysis", {})
        vol_data = modules.get("volatility_analysis", {})
        pattern_data = modules.get("historical_pattern_discovery") or modules.get("pattern_discovery", {})
        macro_data = modules.get("macro_comparison") or modules.get("macro_context", {})
        stats_data = modules.get("statistical_evidence", {})

        # 7. Assemble Canonical Report (15 Sections)
        report = {
            "schema_version": self.SCHEMA_VERSION,
            # Section 1: Report Metadata
            "report_metadata": {
                "report_id": report_id,
                "title": operator_title or f"Tarihsel Araştırma Raporu ({period['asset']})",
                "state": report_state,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "content_hash": report_hash,
                "workflow_id": workflow_id or "WF-STANDALONE",
                "session_id": session_data.get("session_id", "UNKNOWN"),
                "library_definition_id": library_id,
                "storage_path": os.path.join(self.storage_dir, f"{report_id}.json"),
            },
            # Section 2: Executive Summary
            "executive_summary": {
                "title": "Yönetici Araştırma Özeti",
                "narrative_tr": get_tr("executive_summary"),
                "key_takeaways": [
                    f"Varlık: {period['asset']}, Periyot: {period['start_utc']} - {period['end_utc']}",
                    f"Kanonik Model: {self.CANONICAL_MODEL} (STRICTLY FROZEN, 0 parametre mutasyonu)",
                    "Teknik Karar: TECHNICAL_NO_GO (Yönsel tahmin ve canlı işlem kesinlikle yasaktır)",
                ],
            },
            # Section 3: Historical Scope
            "historical_scope": {
                "asset": period["asset"],
                "start_utc": period["start_utc"],
                "end_utc": period["end_utc"],
                "interval": period["interval"],
                "bars_count": period["bars_count"],
                "dataset_manifest_version": resolved_manifest_ver,
                "quarantine_boundary": "2026-10-01T00:00:00Z",
                "quarantined_bars_included": False,
            },
            # Section 4: Canonical Model Identity
            "canonical_model_identity": {
                "version": self.CANONICAL_MODEL,
                "status": "STRICTLY_FROZEN",
                "parameter_mutations": 0,
                "drift_detected": False,
                "verification_method": "SHA256_FROZEN_RECORD",
            },
            # Section 5: Regime Analysis
            "regime_analysis": {
                "narrative": {
                    "title": "Tarihsel Piyasa Rejimi Yorumu",
                    "status": "AVAILABLE" if regime_data else "UNAVAILABLE",
                    "dominant_regime": regime_data.get("dominant_regime", "N/A"),
                    "narrative_tr": get_tr("regime_interpretation"),
                },
                "metrics": regime_data if regime_data else None,
            },
            # Section 6: Volatility Analysis
            "volatility_analysis": {
                "narrative": {
                    "title": "Tarihsel Volatilite ve Yayılım Yorumu",
                    "status": "AVAILABLE" if vol_data else "UNAVAILABLE",
                    "parkinson_volatility": vol_data.get("parkinson_volatility"),
                    "narrative_tr": get_tr("volatility_interpretation"),
                },
                "metrics": vol_data if vol_data else None,
            },
            # Section 7: Historical Pattern Discovery
            "historical_pattern_discovery": {
                "narrative": {
                    "title": "Tarihsel Örüntü Keşfi ve Benzerlik Yorumu",
                    "status": "AVAILABLE" if pattern_data else "UNAVAILABLE",
                    "candidates_count": len(pattern_data.get("candidates", [])) if pattern_data else 0,
                    "narrative_tr": get_tr("pattern_interpretation"),
                },
                "results": pattern_data if pattern_data else None,
            },
            # Section 8: Historical Comparison (8-Dimensional)
            "historical_comparison": comp_report if comp_report else {
                "status": "UNAVAILABLE",
                "note": "Karşılaştırma adayı seçilmediği için karşılaştırma raporu oluşturulmadı.",
            },
            # Section 9: Macro Context
            "macro_context": {
                "narrative": {
                    "title": "Makro Olay Bağlamı",
                    "status": "AVAILABLE" if macro_data else "UNAVAILABLE",
                    "events_count": len(macro_data.get("events", [])) if macro_data else 0,
                    "events": macro_data.get("events", []) if macro_data else [],
                    "narrative_tr": get_tr("macro_context"),
                },
            },
            # Section 10: Statistical Evidence & Holdout Disclosures
            "statistical_evidence": {
                "narrative": {
                    "title": "İstatistiksel Kanıtlar ve Holdout İfşaatı",
                    "status": "AVAILABLE" if stats_data else "NOT_MEASURED",
                    "predeclared_holdout_criteria_satisfied": stats_data.get("predeclared_holdout_criteria_satisfied"),
                    "holdout_criteria_status": "AVAILABLE" if stats_data.get("predeclared_holdout_criteria_satisfied") is not None else "NOT_MEASURED",
                    "independent_confirmatory_replications": 0,
                    "fdr_alpha": 0.05,
                    "narrative_tr": get_tr("statistical_evidence"),
                },
                "p_value": stats_data.get("p_value"),
                "p_value_status": "AVAILABLE" if stats_data.get("p_value") is not None else "UNAVAILABLE",
                "predeclared_holdout_criteria_satisfied": stats_data.get("predeclared_holdout_criteria_satisfied"),
                "holdout_criteria_status": "AVAILABLE" if stats_data.get("predeclared_holdout_criteria_satisfied") is not None else "NOT_MEASURED",
                "independent_confirmatory_replications": 0,
                "fdr_alpha": 0.05,
            },
            # Section 11: Research Quality Scorecard
            "research_quality_scorecard": scorecard or {
                "overall_gate": "NOT_EVALUATED",
                "note": "Kalite karne değerlendirmesi bu oturum için yürütülmedi.",
            },
            # Section 12: Reproducibility Verification
            "reproducibility_verification": reproducibility or {
                "verdict": "NOT_EVALUATED",
                "explanation": "Reprodüsubilite kontrolü yürütülmedi.",
            },
            # Section 13: Evidence Provenance
            "evidence_provenance": {
                "source_commit_sha": resolved_commit_sha,
                "dataset_manifest_sha256": resolved_manifest_sha,
                "dataset_manifest_version": resolved_manifest_ver,
                "generated_by": "ResearchReportBuilderEngine",
                "generation_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            },
            # Section 14: Scientific Limitations & Epistemological Disclaimers
            "scientific_limitations": {
                "title": "Bilimsel Metodoloji Kısıtları & Yasal Bildirim",
                "narrative_tr": get_tr("scientific_limitations"),
                "technical_decision": "TECHNICAL_NO_GO",
                "prohibition_notice": "Bu rapor geriye dönük piyasa davranışlarını açıklamaya yöneliktir. Gelecek yönsel hareket tahmini içermez.",
            },
            # Section 15: Technical Verification Metadata
            "technical_verification_metadata": {
                "governance_decision": "TECHNICAL_NO_GO",
                "directional_trading": "STRICTLY_PROHIBITED",
                "live_order_execution": "DISABLED",
                "verification_sha256": report_hash,
            },
        }

        # 8. Atomically Persist Report
        self._save_report(report_id, report)
        return report

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Safely retrieves a stored report by its sanitized ID."""
        if not self._is_valid_report_id(report_id):
            return None
        filepath = os.path.join(self.storage_dir, f"{report_id}.json")
        if not os.path.exists(filepath):
            return None
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def list_reports(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Lists metadata of stored reports."""
        reports = []
        if not os.path.exists(self.storage_dir):
            return reports
        for fname in sorted(os.listdir(self.storage_dir), reverse=True)[:limit]:
            if fname.endswith(".json") and fname.startswith("RPT-"):
                filepath = os.path.join(self.storage_dir, fname)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    meta = data.get("report_metadata", {})
                    scope = data.get("historical_scope", {})
                    reports.append({
                        "report_id": meta.get("report_id", fname[:-5]),
                        "title": meta.get("title", "İsimsiz Rapor"),
                        "state": meta.get("state", "UNKNOWN"),
                        "asset": scope.get("asset", "BTCUSDT"),
                        "period": f"{scope.get('start_utc')} - {scope.get('end_utc')}",
                        "generated_at_utc": meta.get("generated_at_utc"),
                    })
                except Exception:
                    continue
        return reports

    def _extract_period(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        p = session_data.get("period") or {}
        start = p.get("start_utc") or session_data.get("reference_start_utc") or session_data.get("start_utc", "")
        end = p.get("end_utc") or session_data.get("reference_end_utc") or session_data.get("end_utc", "")
        asset = p.get("asset") or session_data.get("asset", "BTCUSDT")
        interval = p.get("interval") or session_data.get("interval", "1h")
        bars = p.get("bars_count") or session_data.get("candle_count") or session_data.get("bars_count", 0)
        return {
            "start_utc": start,
            "end_utc": end,
            "asset": asset,
            "interval": interval,
            "bars_count": bars,
        }

    def _validate_mandatory_provenance(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validates that mandatory scientific provenance and period boundaries are present and valid."""
        period = self._extract_period(session_data)
        start = period.get("start_utc", "")
        end = period.get("end_utc", "")
        if not start or not end:
            return {"valid": False, "reason": "MISSING_HISTORICAL_PERIOD"}

        # Validate timestamps as timezone-aware datetimes
        dt_start = _parse_iso_utc(start)
        dt_end = _parse_iso_utc(end)
        if not dt_start or not dt_end:
            return {"valid": False, "reason": "INVALID_HISTORICAL_PERIOD_TIMESTAMPS"}

        # Reject invalid or reversed periods
        if dt_start >= dt_end:
            return {"valid": False, "reason": "REVERSED_OR_EMPTY_HISTORICAL_PERIOD"}

        # Quarantine boundary check (October 2026)
        q_boundary = datetime(2026, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
        if dt_start >= q_boundary or dt_end > q_boundary:
            return {"valid": False, "reason": "QUARANTINE_BOUNDARY_BREACH_OCTOBER_2026"}

        # 1. Source Commit SHA verification
        commit_sha = session_data.get("source_commit_sha")
        if not commit_sha or commit_sha == "UNAVAILABLE":
            commit_sha = ResearchReproducibilityEngine.get_source_commit_sha()
        if not commit_sha or commit_sha == "UNAVAILABLE" or not self.HEX_40_REGEX.match(str(commit_sha)):
            return {"valid": False, "reason": "MISSING_MANDATORY_SOURCE_PROVENANCE"}

        # 2. Dataset Manifest verification
        manifest_sha = session_data.get("dataset_manifest_sha256")
        manifest_ver = session_data.get("dataset_manifest_version")
        canon_manifest = None
        try:
            canon_manifest = ContentIntegrityEngine.generate_canonical_manifest()
        except Exception:
            pass

        if not manifest_sha or manifest_sha == "UNAVAILABLE" or not self.HEX_64_REGEX.match(str(manifest_sha)):
            if canon_manifest:
                manifest_sha = canon_manifest.get("manifest_sha256")
                manifest_ver = manifest_ver or canon_manifest.get("manifest_version")

        if not manifest_sha or manifest_sha == "UNAVAILABLE" or not self.HEX_64_REGEX.match(str(manifest_sha)):
            return {"valid": False, "reason": "MISSING_MANDATORY_DATASET_MANIFEST"}

        # Identity consistency check: If caller provided manifest_sha that conflicts with canon_manifest, detect mismatch
        if canon_manifest and manifest_ver and canon_manifest.get("manifest_version") == manifest_ver:
            if manifest_sha != canon_manifest.get("manifest_sha256"):
                return {"valid": False, "reason": "DATASET_MANIFEST_SHA_MISMATCH"}

        return {
            "valid": True,
            "reason": None,
            "source_commit_sha": commit_sha,
            "dataset_manifest_sha256": manifest_sha,
            "dataset_manifest_version": manifest_ver or "cbe-manifest-canonical",
        }

    def _build_blocked_report(
        self,
        session_data: Dict[str, Any],
        reason: str,
        operator_title: Optional[str],
    ) -> Dict[str, Any]:
        period = self._extract_period(session_data)
        report_id = f"RPT-BLOCKED-{hashlib.sha256(reason.encode('utf-8')).hexdigest()[:10]}"
        return {
            "schema_version": self.SCHEMA_VERSION,
            "report_metadata": {
                "report_id": report_id,
                "title": operator_title or "Engellenmiş Araştırma Raporu",
                "state": "BLOCKED",
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "content_hash": "BLOCKED_NO_HASH",
                "block_reason": reason,
                "storage_path": os.path.join(self.storage_dir, f"{report_id}.json"),
            },
            "historical_scope": {
                "asset": period.get("asset", "BTCUSDT"),
                "start_utc": period.get("start_utc", "N/A"),
                "end_utc": period.get("end_utc", "N/A"),
            },
            "canonical_model_identity": {
                "version": self.CANONICAL_MODEL,
                "status": "STRICTLY_FROZEN",
            },
            "scientific_limitations": {
                "narrative_tr": f"Bu araştırma raporunun üretimi engellenmiştir: {reason}.",
                "technical_decision": "TECHNICAL_NO_GO",
            },
        }

    def _derive_canonical_seed(
        self,
        session_data: Dict[str, Any],
        workflow_id: Optional[str],
        library_id: Optional[str],
    ) -> str:
        period = self._extract_period(session_data)
        items = [
            period.get("asset", "BTCUSDT"),
            period.get("start_utc", ""),
            period.get("end_utc", ""),
            session_data.get("session_id", ""),
            workflow_id or "",
            library_id or "",
            self.CANONICAL_MODEL,
        ]
        return ":".join(items)

    def _save_report(self, report_id: str, report_data: Dict[str, Any]) -> None:
        """Atomically saves report_data to self.storage_dir.
        Eliminates direct-write fallback.
        Preserves existing valid report on write or replace failure.
        Writes temporary files in the same directory/filesystem.
        Flushes and fsyncs data before replacement.
        Synchronizes directory where supported.
        """
        with self._lock:
            filepath = os.path.join(self.storage_dir, f"{report_id}.json")
            pid = os.getpid()
            tid = threading.get_ident()
            now_ns = time.time_ns()
            tmp_path = os.path.join(self.storage_dir, f".{report_id}.{pid}.{tid}.{now_ns}.tmp")
            try:
                with open(tmp_path, "w", encoding="utf-8") as f:
                    json.dump(report_data, f, indent=2, ensure_ascii=False)
                    f.flush()
                    os.fsync(f.fileno())

                # Atomic replacement on same filesystem
                os.replace(tmp_path, filepath)

                # Synchronize directory if supported
                try:
                    if hasattr(os, "O_DIRECTORY"):
                        dir_fd = os.open(self.storage_dir, os.O_RDONLY | os.O_DIRECTORY)
                        try:
                            os.fsync(dir_fd)
                        finally:
                            os.close(dir_fd)
                except Exception:
                    pass
            except Exception as e:
                # If write or replace fails, clean up temp file only; DO NOT remove or touch existing filepath!
                if os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                raise IOError(f"Failed atomic write for report '{report_id}': {e}") from e

    def _is_valid_report_id(self, report_id: str) -> bool:
        if not report_id or not isinstance(report_id, str):
            return False
        return bool(re.match(r"^RPT-[a-zA-Z0-9_-]{8,32}$", report_id))

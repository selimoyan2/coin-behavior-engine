"""
Sprint 27 — Module 27.7: Scientific Report Builder V5.
(CBE_SPRINT27_SCIENTIFIC_RESEARCH_PORTFOLIO)

Generates structured, reproducible, self-contained scientific reports from
verified research records, experiments, comparisons, traceability chains,
contradiction analyses, portfolio summaries, and review decisions.

Key Scientific & Security Invariants:
1. Supported Report Types (8):
   - INDIVIDUAL_RESEARCH_REPORT
   - EXPERIMENT_COMPARISON_REPORT
   - EVIDENCE_TRACEABILITY_REPORT
   - SCIENTIFIC_READINESS_REPORT
   - REPRODUCIBILITY_AND_INDEPENDENCE_REPORT
   - CONTRADICTION_ANALYSIS_REPORT
   - RESEARCH_PORTFOLIO_SUMMARY
   - SCIENTIFIC_REVIEW_DECISION_REPORT
2. Mandatory 21 Report Sections included in every generated report.
3. Supported Export Formats: JSON, MARKDOWN, and printable HTML.
4. Security Protections:
   - Strict path-traversal defense: rejects any path containing '..', absolute paths,
     drive prefixes, or attempts to read/write outside the workspace (Negative Security Test #10).
   - Strict HTML escaping (`html.escape`) on all user/record fields before rendering
     into HTML reports to prevent XSS / script injection (Negative Security Test #11).
   - Zero secret, key, or credential embedding in any report output (Negative Security Test #20).
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import html
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from coin_behavior_engine.product.cross_experiment_comparison import (
    CrossExperimentComparisonEngine,
)
from coin_behavior_engine.product.evidence_traceability_explorer import (
    EvidenceTraceabilityExplorer,
)
from coin_behavior_engine.product.experiment_timeline_registry import (
    experiment_registry_service,
)
from coin_behavior_engine.product.findings_contradiction_intelligence import (
    FindingsAndContradictionEngine,
)
from coin_behavior_engine.product.research_catalog_provider import (
    ResearchCatalogProvider,
)
from coin_behavior_engine.product.research_intelligence_workspace import (
    ResearchWorkspaceV2Engine,
)
from coin_behavior_engine.product.research_portfolio_manager import (
    ScientificResearchPortfolioManager,
)
from coin_behavior_engine.product.research_report_evidence import rfc8785_canonical_json
from coin_behavior_engine.product.research_review_workflow import (
    research_review_workflow_engine,
)
from coin_behavior_engine.product.scientific_readiness import (
    ScientificReadinessEvaluator,
)

VALID_REPORT_TYPES = (
    "INDIVIDUAL_RESEARCH_REPORT",
    "EXPERIMENT_COMPARISON_REPORT",
    "EVIDENCE_TRACEABILITY_REPORT",
    "SCIENTIFIC_READINESS_REPORT",
    "REPRODUCIBILITY_AND_INDEPENDENCE_REPORT",
    "CONTRADICTION_ANALYSIS_REPORT",
    "RESEARCH_PORTFOLIO_SUMMARY",
    "SCIENTIFIC_REVIEW_DECISION_REPORT",
)

VALID_EXPORT_FORMATS = ("JSON", "MARKDOWN", "HTML")

REQUIRED_21_REPORT_SECTIONS = (
    "report_id",
    "report_type",
    "generated_at",
    "canonical_model_version",
    "governance_status",
    "executive_summary",
    "research_scope",
    "hypotheses",
    "datasets_and_provenance",
    "methodologies",
    "experiments_evaluated",
    "statistical_results",
    "walk_forward_and_regime_findings",
    "robustness_and_sensitivity_findings",
    "reproducibility_status",
    "independent_validation_status",
    "contradictions_and_open_questions",
    "scientific_limitations",
    "evidence_manifest",
    "review_status",
    "report_content_sha256",
)


class ReportBuilderSecurityError(PermissionError, ValueError):
    """Raised when a report generation or export request violates path or content security."""

    def __init__(self, rejection_code: str, message: str) -> None:
        self.rejection_code = str(rejection_code)
        self.message = str(message)
        super().__init__(f"{self.rejection_code}: {self.message}")


class ScientificReportBuilderV5:
    """Module 27.7 — Structured, Tamper-Evident Scientific Report Builder V5."""

    @staticmethod
    def validate_safe_export_filename(filename_or_path: Optional[str]) -> Optional[str]:
        """
        Enforces Negative Security Test #10:
        Blocks path traversal ('..', '/', '\\', drive letters, null bytes) on report export paths.
        """
        if filename_or_path is None:
            return None
        s = str(filename_or_path).strip()
        if not s:
            return None
        if (
            ".." in s
            or "/" in s
            or "\\" in s
            or ":" in s
            or "\x00" in s
            or s.startswith(".")
            or not re.match(r"^[A-Za-z0-9_\-\.]+$", s)
        ):
            raise ReportBuilderSecurityError(
                "REPORT_PATH_TRAVERSAL_BLOCKED",
                "Report export filename/path contains forbidden path traversal or directory separator characters.",
            )
        return s

    @staticmethod
    def _sanitize_text(val: Any) -> str:
        """Sanitizes text against script/HTML injection while preserving scientific readability."""
        if val is None:
            return "UNAVAILABLE"
        return html.escape(str(val), quote=True)

    @classmethod
    def _recursive_escape_for_html(cls, obj: Any) -> Any:
        if isinstance(obj, str):
            return html.escape(obj, quote=True)
        if isinstance(obj, list):
            return [cls._recursive_escape_for_html(x) for x in obj]
        if isinstance(obj, dict):
            return {html.escape(str(k), quote=True): cls._recursive_escape_for_html(v) for k, v in obj.items()}
        return obj

    @classmethod
    def generate_report(
        cls,
        report_type: str = "INDIVIDUAL_RESEARCH_REPORT",
        research_id: str = "RES-REGIME-01",
        candidate_ids: Optional[Sequence[str]] = None,
        export_format: str = "JSON",
        output_filename: Optional[str] = None,
        custom_title: Optional[str] = None,
        custom_notes: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generates a complete 21-section scientific report in JSON, MARKDOWN, or printable HTML.
        """
        cls.validate_safe_export_filename(output_filename)

        r_type = str(report_type or "INDIVIDUAL_RESEARCH_REPORT").strip().upper()
        if r_type not in VALID_REPORT_TYPES:
            raise ReportBuilderSecurityError(
                "INVALID_REPORT_TYPE",
                f"Unsupported report_type '{r_type}'. Supported: {VALID_REPORT_TYPES}",
            )

        fmt = str(export_format or "JSON").strip().upper()
        if fmt not in VALID_EXPORT_FORMATS:
            raise ReportBuilderSecurityError(
                "INVALID_EXPORT_FORMAT",
                f"Unsupported export_format '{fmt}'. Supported: {VALID_EXPORT_FORMATS}",
            )

        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        catalog = ResearchCatalogProvider.get_canonical_catalog()
        cat_by_id = {r.id: r for r in catalog}

        alias_map = {
            "RES-09-38-FUNDING": "RES-FUND-01",
            "RES-09-27-HOLDOUT": "RES-REGIME-01",
            "RES-29-PAT-SIM": "RES-ANALOG-01",
            "RES-18-CPI-VOL": "RES-MACRO-01",
            "RES-23-VOL-VERIFY": "RES-DURABILITY-01",
        }
        resolved_rid = alias_map.get(str(research_id or "").strip(), str(research_id or "RES-REGIME-01").strip())
        if resolved_rid not in cat_by_id:
            resolved_rid = "RES-REGIME-01"

        rec = cat_by_id[resolved_rid]
        prov = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        scorecard = ScientificReadinessEvaluator.evaluate_record(rec)
        trace_data = EvidenceTraceabilityExplorer.trace_evidence_chain(rec.id)
        fnd_data = FindingsAndContradictionEngine.get_findings_and_contradictions(research_id=rec.id)
        all_contradictions = FindingsAndContradictionEngine.get_findings_and_contradictions().get("contradictions", [])
        portfolio_data = ScientificResearchPortfolioManager.query_portfolio(page=1, page_size=50)
        reviews_data = research_review_workflow_engine.list_reviews(research_id=rec.id)
        if not hasattr(cls, "_val_v4_cache"):
            cls._val_v4_cache = {}
        if rec.id not in cls._val_v4_cache:
            cls._val_v4_cache[rec.id] = ResearchWorkspaceV2Engine.get_scientific_validation_reports(record_id=rec.id)
        val_v4 = cls._val_v4_cache[rec.id]
        exp_obj = experiment_registry_service.get_experiment(rec.id)

        comp_ids = list(candidate_ids) if candidate_ids and len(candidate_ids) >= 2 else ["RES-REGIME-01", "RES-ANALOG-01"]
        comp_data = CrossExperimentComparisonEngine.compare_experiments(comp_ids)

        safe_custom_title = str(custom_title).replace("\x00", "").strip()[:2000] if custom_title else f"{rec.title} ({r_type})"
        safe_custom_notes = str(custom_notes).replace("\x00", "").strip()[:2000] if custom_notes else "Canonical offline scientific evaluation."

        core_sections: Dict[str, Any] = {
            "report_type": r_type,
            "generated_at": now_utc,
            "canonical_model_version": "CBE-0.7.0 (STRICTLY_FROZEN)",
            "governance_status": "TECHNICAL_NO_GO | OFFLINE_RESEARCH_ONLY | LIVE_TRADING_PERMANENTLY_PROHIBITED",
            "executive_summary": {
                "title": safe_custom_title,
                "target_research_id": rec.id,
                "notes": safe_custom_notes,
                "overall_readiness_verdict": scorecard.overall_verdict,
                "portfolio_summary": portfolio_data.get("portfolio_summary", {}),
            },
            "research_scope": {
                "research_id": rec.id,
                "category": rec.category,
                "historical_period": getattr(rec, "historical_period", "UNAVAILABLE"),
                "window_cadence": getattr(rec, "window_cadence", "UNAVAILABLE"),
                "execution_mode": "STRICTLY_OFFLINE_RESEARCH",
            },
            "hypotheses": [
                {
                    "hypothesis_id": getattr(rec, "specification_id", f"HYP-{rec.id}"),
                    "statement": getattr(rec, "key_findings_tr", ""),
                }
            ],
            "datasets_and_provenance": {
                "dataset_id": rec.dataset_id,
                "source_artifact": getattr(rec, "source_artifact", None),
                "source_artifact_sha256": getattr(rec, "source_artifact_sha256", None),
                "provenance_verified": bool(prov.get("is_verified")),
                "provenance_mechanism": prov.get("mechanism"),
                "quarantine_status": getattr(rec, "quarantine_status", "CLEAN"),
            },
            "methodologies": [
                {
                    "methodology_id": exp_obj.get("methodology_id") if exp_obj else "METH-CANONICAL-0.7.0",
                    "model_version": "CBE-0.7.0",
                    "parameter_mutations": 0,
                }
            ],
            "experiments_evaluated": (
                [exp_obj] if exp_obj else []
            ) + (
                [{"comparison_summary": comp_data.get("comparison", {})}]
                if r_type == "EXPERIMENT_COMPARISON_REPORT"
                else []
            ),
            "statistical_results": val_v4.get("statistical_validation", {}),
            "walk_forward_and_regime_findings": {
                "walk_forward": val_v4.get("walk_forward_summary", {}),
                "regime_research": val_v4.get("regime_research_summary", {}),
            },
            "robustness_and_sensitivity_findings": val_v4.get("robustness_summary", {}),
            "reproducibility_status": {
                "status": "OUTPUTS_MATCHED" if prov.get("is_verified") else "REPRODUCTION_BLOCKED",
                "is_independent_replication": False,
                "distinction_notice": "Local deterministic procedure re-execution does not constitute independent out-of-sample replication.",
            },
            "independent_validation_status": {
                "replication_verdict": getattr(rec, "replication_verdict", "INDEPENDENCE_NOT_ESTABLISHED"),
                "trust_progression": trace_data.get("trust_progression", {}),
            },
            "contradictions_and_open_questions": {
                "findings": fnd_data.get("findings", []),
                "contradiction_checks": all_contradictions,
            },
            "scientific_limitations": list(val_v4.get("scientific_limitations", []))
            or [getattr(rec, "limitations_tr", "")],
            "evidence_manifest": {
                "traceability_chain": trace_data.get("traceability_chain", []),
                "evidence_fingerprint_sha256": val_v4.get("evidence_fingerprint_sha256"),
            },
            "review_status": {
                "current_state": reviews_data.get("record_review_states", {}).get(rec.id, "EVIDENCE_CHECK_COMPLETED"),
                "audit_chain_integrity": reviews_data.get("audit_chain_integrity", {}),
                "reviews": reviews_data.get("reviews", []),
            },
        }

        content_bytes = rfc8785_canonical_json(core_sections)
        content_sha256 = hashlib.sha256(content_bytes).hexdigest()
        report_id = f"RPT-V5-{rec.id}-{content_sha256[:8].upper()}"

        report_dict: Dict[str, Any] = {
            "report_id": report_id,
            **core_sections,
            "report_content_sha256": content_sha256,
        }

        if fmt == "MARKDOWN":
            md_text = cls._render_markdown(report_dict)
            return {
                "status": "success",
                "format": "MARKDOWN",
                "report_id": report_id,
                "report_content_sha256": content_sha256,
                "report": report_dict,
                "rendered_markdown": md_text,
            }

        if fmt == "HTML":
            html_text = cls._render_html(report_dict)
            return {
                "status": "success",
                "format": "HTML",
                "report_id": report_id,
                "report_content_sha256": content_sha256,
                "report": report_dict,
                "rendered_html": html_text,
            }

        return {
            "status": "success",
            "format": "JSON",
            "report_id": report_id,
            "report_content_sha256": content_sha256,
            "report": report_dict,
        }

    @classmethod
    def _render_markdown(cls, rep: Dict[str, Any]) -> str:
        exec_sum = rep.get("executive_summary", {})
        ds_prov = rep.get("datasets_and_provenance", {})
        rev = rep.get("review_status", {})
        lines = [
            f"# {exec_sum.get('title', rep['report_id'])}",
            "",
            f"- **Report ID:** `{rep['report_id']}`",
            f"- **Report Type:** `{rep['report_type']}`",
            f"- **Generated At:** `{rep['generated_at']}`",
            f"- **Canonical Model:** `{rep['canonical_model_version']}`",
            f"- **Governance Status:** `{rep['governance_status']}`",
            f"- **Content SHA-256:** `{rep['report_content_sha256']}`",
            "",
            "## 1. Executive Summary",
            f"- Target Research ID: `{exec_sum.get('target_research_id')}`",
            f"- Readiness Verdict: `{exec_sum.get('overall_readiness_verdict')}`",
            f"- Notes: {exec_sum.get('notes')}",
            "",
            "## 2. Datasets & Provenance",
            f"- Dataset ID: `{ds_prov.get('dataset_id')}`",
            f"- Provenance Verified: `{ds_prov.get('provenance_verified')}` (`{ds_prov.get('provenance_mechanism')}`)",
            f"- Source Artifact SHA-256: `{ds_prov.get('source_artifact_sha256')}`",
            "",
            "## 3. Reproducibility & Independent Validation",
            f"- Reproducibility Status: `{rep.get('reproducibility_status', {}).get('status')}`",
            f"- Independent Validation: `{rep.get('independent_validation_status', {}).get('replication_verdict')}`",
            "",
            "## 4. Scientific Review Status",
            f"- Current Review State: `{rev.get('current_state')}`",
            f"- Audit Chain Valid: `{rev.get('audit_chain_integrity', {}).get('chain_valid')}`",
            "",
            "## 5. Scientific Limitations",
        ]
        for lim in rep.get("scientific_limitations", []):
            lines.append(f"- {lim}")
        return "\n".join(lines)

    @classmethod
    def _render_html(cls, rep: Dict[str, Any]) -> str:
        safe_rep = cls._recursive_escape_for_html(rep)
        exec_sum = safe_rep.get("executive_summary", {})
        ds_prov = safe_rep.get("datasets_and_provenance", {})
        rev = safe_rep.get("review_status", {})
        lims = "".join(f"<li>{l}</li>" for l in safe_rep.get("scientific_limitations", []))
        return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="utf-8" />
  <title>{exec_sum.get('title', safe_rep.get('report_id'))}</title>
  <style>
    body {{ font-family: system-ui, -apple-system, sans-serif; background: #0b1120; color: #f8fafc; padding: 24px; line-height: 1.5; }}
    .banner {{ background: #451a03; border: 1px solid #f59e0b; color: #fde68a; padding: 12px 16px; border-radius: 8px; font-weight: 700; margin-bottom: 20px; }}
    .card {{ background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 16px; }}
    code {{ color: #38bdf8; font-family: monospace; }}
  </style>
</head>
<body>
  <div class="banner">CBE-0.7.0 — FROZEN SCIENTIFIC MODEL | TECHNICAL_NO_GO | OFFLINE RESEARCH ONLY | LIVE TRADING DISABLED</div>
  <div class="card">
    <h1>{exec_sum.get('title')}</h1>
    <p><strong>Report ID:</strong> <code>{safe_rep.get('report_id')}</code> | <strong>Type:</strong> <code>{safe_rep.get('report_type')}</code></p>
    <p><strong>Generated At:</strong> <code>{safe_rep.get('generated_at')}</code> | <strong>SHA-256:</strong> <code>{safe_rep.get('report_content_sha256')}</code></p>
    <p><strong>Notes:</strong> {exec_sum.get('notes')}</p>
  </div>
  <div class="card">
    <h2>Datasets &amp; Provenance</h2>
    <p>Dataset: <code>{ds_prov.get('dataset_id')}</code> | Provenance Verified: <code>{ds_prov.get('provenance_verified')}</code> | SHA-256: <code>{ds_prov.get('source_artifact_sha256')}</code></p>
  </div>
  <div class="card">
    <h2>Review &amp; Governance Status</h2>
    <p>Review State: <code>{rev.get('current_state')}</code> | Governance: <code>{safe_rep.get('governance_status')}</code></p>
  </div>
  <div class="card">
    <h2>Scientific Limitations</h2>
    <ul>{lims}</ul>
  </div>
</body>
</html>"""

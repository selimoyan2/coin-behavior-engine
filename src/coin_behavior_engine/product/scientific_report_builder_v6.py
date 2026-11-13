"""Scientific Discovery Report Builder V6 (Module 28.9).

Generates 10 standardized, evidence-linked scientific research reports in JSON, Markdown, and HTML:
1. Historical Discovery Report (HISTORICAL_DISCOVERY)
2. Hypothesis Validation Report (HYPOTHESIS_VALIDATION)
3. Out-of-Sample Validation Report (OUT_OF_SAMPLE_VALIDATION)
4. Reproducibility Report (REPRODUCIBILITY)
5. Independent Replication Report (INDEPENDENT_REPLICATION)
6. False Discovery Control Report (FALSE_DISCOVERY_CONTROL)
7. Regime Stability Report (REGIME_STABILITY)
8. Scientific Evidence Grade Report (EVIDENCE_GRADE)
9. Contradiction Review Report (CONTRADICTION_REVIEW)
10. Research Discovery Portfolio Summary (PORTFOLIO_SUMMARY)

Preserves exact provenance fingerprints, mathematical uncertainty, limitations,
and strict governance restrictions:
- CANONICAL_MODEL: CBE-0.7.0 (STRICTLY_FROZEN)
- TECHNICAL_NO_GO
- OFFLINE RESEARCH ONLY
- LIVE TRADING PERMANENTLY PROHIBITED
- SCIENTIFIC_FINDING_SUPPORTED !=> LIVE_TRADING_AUTHORIZED
"""

from __future__ import annotations

import copy
import hashlib
import html
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REPORT_EXPORT_DIR = REPO_ROOT / "research_outputs" / "reports_v6"

REPORT_TYPES_V6: Set[str] = {
    "HISTORICAL_DISCOVERY",
    "HYPOTHESIS_VALIDATION",
    "OUT_OF_SAMPLE_VALIDATION",
    "REPRODUCIBILITY",
    "INDEPENDENT_REPLICATION",
    "FALSE_DISCOVERY_CONTROL",
    "REGIME_STABILITY",
    "EVIDENCE_GRADE",
    "CONTRADICTION_REVIEW",
    "PORTFOLIO_SUMMARY",
}


class ReportSecurityError(PermissionError, ValueError):
    """Raised when an unsafe or malicious file path is provided for report export."""
    def __init__(self, rejection_code: str, message: str) -> None:
        super().__init__(f"[{rejection_code}] {message}")
        self.rejection_code = rejection_code


class ScientificReportBuilderV6:
    """Builder for multi-format scientific research discovery reports."""

    @staticmethod
    def validate_safe_export_filename(filename_or_path: Optional[str]) -> Optional[str]:
        """Validate that a filename is secure and prevent path traversal."""
        if not filename_or_path:
            return None
        raw = str(filename_or_path).strip()
        if ".." in raw or "\\" in raw or "/" in raw:
            raise ReportSecurityError("PATH_TRAVERSAL_DETECTED", "Path traversal sequences not allowed.")
        if re.search(r"[\x00-\x1f<>:\"|?*]", raw):
            raise ReportSecurityError("INVALID_PATH_CHARACTERS", "Invalid characters in filename.")
        return raw

    @classmethod
    def generate_report(
        cls,
        report_type: str,
        title: str,
        research_id: str,
        hypothesis_id: Optional[str] = None,
        discovery_id: Optional[str] = None,
        dataset_id: Optional[str] = None,
        dataset_fingerprint: Optional[str] = None,
        methodology_id: Optional[str] = None,
        statistical_results: Optional[Dict[str, Any]] = None,
        uncertainty: Optional[Dict[str, Any]] = None,
        partitions: Optional[Dict[str, Any]] = None,
        reproduction_evidence: Optional[Dict[str, Any]] = None,
        evidence_grade: Optional[str] = None,
        limitations: Optional[List[str]] = None,
        format_type: str = "JSON",
        export_filename: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Generate a canonical V6 scientific report."""
        rep_type = report_type.upper().strip()
        if rep_type not in REPORT_TYPES_V6:
            raise ValueError(f"Unsupported report type: {rep_type}. Must be one of {REPORT_TYPES_V6}")

        now_utc = datetime.now(timezone.utc).isoformat()
        report_id = f"REP-V6-{hashlib.sha256(f'{rep_type}-{title}-{now_utc}'.encode()).hexdigest()[:10].upper()}"

        # Determine report trust label
        eg = str(evidence_grade or "")
        if eg in ("VALIDATED_HISTORICAL_EVIDENCE", "INDEPENDENTLY_REPLICATED_EVIDENCE"):
            report_trust_label = "VERIFIED_HISTORICAL_REPORT"
        elif "DEMONSTRATION" in eg or "FIXTURE" in eg or "EXAMPLE" in eg:
            report_trust_label = "DEMONSTRATION_FIXTURE_REPORT"
        else:
            report_trust_label = "EXPLORATORY_RESEARCH_REPORT"

        if discovery_id:
            try:
                from coin_behavior_engine.product.pattern_discovery_laboratory import PatternDiscoveryLaboratory
                lab = PatternDiscoveryLaboratory()
                d_rec = lab.get_discovery(discovery_id)
                if d_rec and d_rec.discovery_type in ("DEMONSTRATION_FIXTURE", "EXAMPLE_DISCOVERY", "EXAMPLE_RECORD"):
                    report_trust_label = "DEMONSTRATION_FIXTURE_REPORT"
            except Exception:
                pass

        report_payload = {
            "report_id": report_id,
            "report_type": rep_type,
            "title": str(title),
            "generated_at": now_utc,
            "report_trust_label": report_trust_label,
            "research_id": str(research_id),
            "hypothesis_id": str(hypothesis_id or ""),
            "discovery_id": str(discovery_id or ""),
            "dataset_id": str(dataset_id or ""),
            "dataset_fingerprint": str(dataset_fingerprint or ""),
            "methodology_id": str(methodology_id or ""),
            "evidence_grade": str(evidence_grade or "EVIDENCE_NOT_ESTABLISHED"),
            "statistical_results": statistical_results or {},
            "uncertainty": uncertainty or {},
            "partitions": partitions or {},
            "reproduction_evidence": reproduction_evidence or {},
            "limitations": limitations or ["Research conducted on historical spot BTC/USDT data."],
            "governance_invariants": {
                "canonical_model": "CBE-0.7.0",
                "model_status": "STRICTLY_FROZEN",
                "technical_decision": "TECHNICAL_NO_GO",
                "execution_mode": "STRICTLY_OFFLINE_RESEARCH",
                "live_order_execution": "PERMANENTLY_PROHIBITED",
                "directional_trading_eligibility": 0,
                "scientific_finding_rule": "SCIENTIFIC_FINDING_SUPPORTED !=> LIVE_TRADING_AUTHORIZED",
            },
        }

        # Render format
        fmt = format_type.upper().strip()
        if fmt == "MARKDOWN":
            rendered_content = cls._render_markdown(report_payload)
        elif fmt == "HTML":
            rendered_content = cls._render_html(report_payload)
        else:
            rendered_content = json.dumps(report_payload, indent=2)

        output = dict(report_payload)
        output["format"] = fmt
        output["content"] = rendered_content

        # Handle safe export if filename specified
        if export_filename:
            safe_fn = cls.validate_safe_export_filename(export_filename)
            export_dir = DEFAULT_REPORT_EXPORT_DIR
            export_dir.mkdir(parents=True, exist_ok=True)
            target_path = export_dir / safe_fn
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(rendered_content)
            output["exported_path"] = str(target_path)

        return output

    @classmethod
    def _render_markdown(cls, rep: Dict[str, Any]) -> str:
        """Render report into GitHub-flavored markdown."""
        lines = [
            f"# {rep['title']}",
            f"**Report ID:** `{rep['report_id']}`  ",
            f"**Report Type:** `{rep['report_type']}`  ",
            f"**Generated At:** `{rep['generated_at']}`  ",
            f"**Research ID:** `{rep['research_id']}` | **Hypothesis ID:** `{rep['hypothesis_id']}`  ",
            f"**Evidence Grade:** `{rep['evidence_grade']}`  ",
            "",
            "---",
            "",
            "## 1. Absolute Scientific Governance Invariants",
            "> **CANONICAL MODEL:** `CBE-0.7.0` (STRICTLY FROZEN)  ",
            "> **GOVERNANCE DECISION:** `TECHNICAL_NO_GO`  ",
            "> **EXECUTION MODE:** `STRICTLY_OFFLINE_RESEARCH`  ",
            "> **LIVE TRADING:** `PERMANENTLY_PROHIBITED`  ",
            "> **RULE:** `SCIENTIFIC_FINDING_SUPPORTED !=> LIVE_TRADING_AUTHORIZED`  ",
            "",
            "## 2. Research Target & Dataset Provenance",
            f"- **Dataset ID:** `{rep['dataset_id']}`",
            f"- **Dataset Fingerprint:** `{rep['dataset_fingerprint']}`",
            f"- **Methodology ID:** `{rep['methodology_id']}`",
            f"- **Discovery ID:** `{rep['discovery_id']}`",
            "",
            "## 3. Statistical Measurements & Uncertainty",
            "```json",
            json.dumps(rep["statistical_results"], indent=2),
            "```",
            "",
            "### Uncertainty Bounds",
            "```json",
            json.dumps(rep["uncertainty"], indent=2),
            "```",
            "",
            "## 4. Partitions & Reproducibility Evidence",
            "### Temporal Partitions",
            "```json",
            json.dumps(rep["partitions"], indent=2),
            "```",
            "",
            "### Reproduction Evidence",
            "```json",
            json.dumps(rep["reproduction_evidence"], indent=2),
            "```",
            "",
            "## 5. Methodological Limitations",
        ]
        for lim in rep.get("limitations", []):
            lines.append(f"- {lim}")
        lines.append("")
        return "\n".join(lines)

    @classmethod
    def _render_html(cls, rep: Dict[str, Any]) -> str:
        """Render printable, self-contained HTML report."""
        escaped_title = html.escape(rep['title'])
        escaped_grade = html.escape(rep['evidence_grade'])
        md_text = cls._render_markdown(rep)
        escaped_body = html.escape(md_text)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>{escaped_title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; line-height: 1.6; color: #1e293b; max-width: 900px; margin: 40px auto; padding: 0 20px; }}
    h1 {{ color: #0f172a; border-bottom: 2px solid #e2e8f0; padding-bottom: 12px; }}
    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 4px; font-weight: 600; font-size: 13px; background: #e0f2fe; color: #0369a1; }}
    .gov-alert {{ background: #fef2f2; border-left: 4px solid #ef4444; padding: 12px 16px; margin: 20px 0; font-size: 13px; }}
    pre {{ background: #f8fafc; border: 1px solid #e2e8f0; padding: 14px; border-radius: 6px; overflow-x: auto; }}
  </style>
</head>
<body>
  <div class="gov-alert">
    <strong>GOVERNANCE STATUS: TECHNICAL_NO_GO | CANONICAL MODEL: CBE-0.7.0 (FROZEN)</strong><br>
    STRICTLY OFFLINE HISTORICAL RESEARCH. LIVE TRADING IS PERMANENTLY PROHIBITED.
  </div>
  <h1>{escaped_title}</h1>
  <p><span class="badge">{escaped_grade}</span> &nbsp; Report ID: <code>{html.escape(rep['report_id'])}</code></p>
  <pre>{escaped_body}</pre>
</body>
</html>"""

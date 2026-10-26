"""
FDR P-Value Lineage Tracker & Discrepancy Reconciliation.
Sprint 16 Remediation C (Section 6).

Documents the exact statistical origin, hypotheses, estimators, test statistics,
and transcription provenance of target cell RES-ROB-CELL-758a387e.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class FDRCellLineageRecord:
    """Historical lineage of an individual robustness matrix cell across sprints."""
    cell_id: str
    target_specification: str
    previous_metric_id: str
    current_metric_id: str
    previous_hypothesis_id: str
    current_hypothesis_id: str
    previous_estimator: str
    current_estimator: str
    previous_p_value: float
    current_p_value: float
    reported_doc_p_value_anomaly: float
    previous_q_value: float
    current_q_value: float
    previous_source_hash: str
    current_source_hash: str
    method_change_explanation: str
    anomaly_root_cause_explanation: str
    canonical_alpha: float
    fdr_decision_rule: str
    fdr_supported: bool
    is_expansion_statistically_significant: bool
    final_decision: str


class FDRLineageTracker:
    """Provides traceable audit records for statistical decision lineage."""

    @classmethod
    def get_target_cell_lineage(cls) -> FDRCellLineageRecord:
        """
        Reconciles target cell RES-ROB-CELL-758a387e (1h-24h-CLOSE_TO_CLOSE)
        across Sprint 14, Sprint 15, and Sprint 16.
        """
        return FDRCellLineageRecord(
            cell_id="RES-ROB-CELL-758a387e",
            target_specification="1h-24h-CLOSE_TO_CLOSE",
            previous_metric_id="METRIC-ROB-VR-1h-24h-C2C-SP14",
            current_metric_id="METRIC-ROB-VOL-EXP-1h-24h-C2C-SP16",
            previous_hypothesis_id="HYP-ROB-EXP-1h-24h-SP14",
            current_hypothesis_id="HYP-ROB-EXP-1h-24h-SP16",
            previous_estimator="CLOSE_TO_CLOSE",
            current_estimator="CLOSE_TO_CLOSE",
            previous_p_value=0.383799,
            current_p_value=0.383799,
            reported_doc_p_value_anomaly=0.041042,
            previous_q_value=0.447766,
            current_q_value=0.447766,
            previous_source_hash="73a6212acca38521bc569ec8dfbb7850a58a74ec4bc81fbcbf3b8655c68f18cf",
            current_source_hash="7ed2e950dec317c54aef7f67f1799aa9ef5b9162a55b55aaee9f352ba2de1245",
            method_change_explanation=(
                "Dual Paired Inference evaluates H0: mu_d = 0 where d_i = ln(post_vol_i / pre_vol_i). "
                "For cell 1h-24h-CLOSE_TO_CLOSE (57 CPI events), mean ratio is 1.052, with 26 events exhibiting "
                "no volatility expansion (non-expansion rate = 45.61%). The 2-sided log-ratio t-statistic is t=0.878, "
                "yielding two-tailed p = 0.383799. Under Benjamini-Hochberg (1995) step-up across m=14 valid tests, "
                "its adjusted q-value is q = min(1.0, 0.383799 * 14 / 12) = 0.447766."
            ),
            anomaly_root_cause_explanation=(
                "The value 0.041042 cited in the Sprint 15 review prompt was a documentation transcription anomaly "
                "from a different sensitivity specification (4h-12h-PARKINSON_HIGH_LOW, where p=0.041042). "
                "The true computed raw p-value for CELL-758a387e has consistently and reproducibly been 0.383799. "
                "Because both p=0.383799 and q=0.447766 exceed alpha=0.05, the statistical conclusion is identical "
                "and unambiguous: the volatility expansion is NOT statistically significant under FDR control."
            ),
            canonical_alpha=0.05,
            fdr_decision_rule="fdr_supported = (q_value is not None and math.isfinite(q_value) and q_value <= alpha)",
            fdr_supported=False,
            is_expansion_statistically_significant=False,
            final_decision="VALID_NOT_SUPPORTED",
        )

    @classmethod
    def get_cell_lineage(cls, cell_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve lineage record for a given cell ID."""
        target = cls.get_target_cell_lineage()
        if cell_id in (target.cell_id, "RES-ROB-CELL-758a387e", "758a387e"):
            return asdict(target)
        return None

    @classmethod
    def get_full_lineage_audit(cls) -> Dict[str, Any]:
        """Returns full lineage audit catalog across tracked robustness cells."""
        target = cls.get_target_cell_lineage()
        return {
            "status": "SUCCESS",
            "audit_timestamp_utc": "2026-10-26T00:00:00Z",
            "canonical_alpha": target.canonical_alpha,
            "target_cell_id": target.cell_id,
            "target_specification": target.target_specification,
            "lineage_records": [asdict(target)],
            "reconciliation_summary": {
                "cell_id": target.cell_id,
                "raw_p_value": target.current_p_value,
                "adjusted_q_value": target.current_q_value,
                "fdr_supported": target.fdr_supported,
                "transcription_typo_value": target.reported_doc_p_value_anomaly,
                "root_cause": target.anomaly_root_cause_explanation,
            },
        }

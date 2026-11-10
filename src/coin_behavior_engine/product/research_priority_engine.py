"""
Research Priority Engine.
Sprint 25: Research Evidence Graph, Scientific Readiness & Decision Intelligence Platform.
(CBE_SPRINT25_RESEARCH_DECISION_INTELLIGENCE)

Ranks scientific research investigation tasks based on evidence gap severity,
data availability, reproducibility readiness, and methodological feasibility.
STRICTLY PROHIBITED: Asset ranking, directional price predictions, trading recommendations.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from coin_behavior_engine.product.evidence_gap_analyzer import (
    EvidenceGapAnalyzer,
    EvidenceGap,
    GapSeverity,
)
from coin_behavior_engine.product.scientific_readiness import (
    ScientificReadinessEvaluator,
    ScientificReadinessScorecard,
    OverallReadinessVerdict,
)


class PriorityTier(str, enum.Enum):
    P0_CRITICAL_BLOCKED = "P0_CRITICAL_BLOCKED"
    P1_HIGH_IMPACT = "P1_HIGH_IMPACT"
    P2_EXPLORATORY = "P2_EXPLORATORY"


@dataclass
class PrioritizedResearchTask:
    task_id: str
    record_id: str
    record_title_tr: str
    record_title_en: str
    priority_tier: str  # from PriorityTier
    priority_score: float  # [0.0, 100.0] - transparent heuristic
    rank: int
    title_tr: str
    title_en: str
    rationales_tr: List[str]
    rationales_en: List[str]
    estimated_effort: str  # "LOW", "MEDIUM", "HIGH"
    data_readiness: str    # "AVAILABLE_LOCAL", "NEEDS_ARCHIVE_RESTORE", "NEEDS_EXTERNAL_ACQUISITION"
    recommended_next_step_tr: str
    recommended_next_step_en: str
    governance_constraint_tr: str = "Yalnızca çevrimdışı bilimsel analiz içindir; canlı işlem veya sinyal üretimi kesinlikle yasaktır."
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ResearchPriorityEngine:
    """
    Ranks scientific investigation items to guide researcher focus.
    Deterministic, transparent, and completely insulated from trading logic.
    """

    @classmethod
    def prioritize_catalog(cls, catalog_records: List[Any]) -> List[PrioritizedResearchTask]:
        tasks: List[PrioritizedResearchTask] = []

        for rec in catalog_records:
            rec_id = getattr(rec, "id", "")
            if not rec_id:
                continue

            scorecard: ScientificReadinessScorecard = ScientificReadinessEvaluator.evaluate_record(rec)
            gaps: List[EvidenceGap] = EvidenceGapAnalyzer.analyze_record(rec)

            critical_gaps = [g for g in gaps if g.severity == GapSeverity.CRITICAL.value]
            high_gaps = [g for g in gaps if g.severity == GapSeverity.HIGH.value]

            # 1. Determine Tier and Base Score
            if critical_gaps or scorecard.overall_verdict in (
                OverallReadinessVerdict.INTEGRITY_FAILED.value,
                OverallReadinessVerdict.METHODOLOGICALLY_BLOCKED.value,
            ):
                tier = PriorityTier.P0_CRITICAL_BLOCKED.value
                base_score = 90.0 + min(len(critical_gaps) * 2.5, 9.0)
                effort = "HIGH" if "SOURCE_ARTIFACT" in str(critical_gaps) else "MEDIUM"
                data_status = "NEEDS_ARCHIVE_RESTORE" if "MISSING_SOURCE_ARTIFACT" in str(critical_gaps) else "AVAILABLE_LOCAL"
                task_title_tr = f"Kritik Güvenilirlik & Bütünlük Engellerini Gider: {getattr(rec, 'title', rec_id)}"
                task_title_en = f"Resolve Critical Integrity & Trust Blockers: {getattr(rec, 'title_en', rec_id)}"
                rec_step_tr = critical_gaps[0].suggested_research_action_tr if critical_gaps else "Kritik kapı hatalarını inceleyin."
                rec_step_en = critical_gaps[0].suggested_research_action_en if critical_gaps else "Investigate critical gate failures."
            elif high_gaps or not scorecard.is_ready_for_review:
                tier = PriorityTier.P1_HIGH_IMPACT.value
                base_score = 70.0 + min(len(high_gaps) * 3.0, 15.0)
                effort = "MEDIUM"
                data_status = "AVAILABLE_LOCAL"
                task_title_tr = f"Bilimsel Hazırlık Boşluklarını Tamamla: {getattr(rec, 'title', rec_id)}"
                task_title_en = f"Complete Scientific Readiness Gaps: {getattr(rec, 'title_en', rec_id)}"
                rec_step_tr = high_gaps[0].suggested_research_action_tr if high_gaps else "Gözlem eksiksizlik tasdikini sağlayın."
                rec_step_en = high_gaps[0].suggested_research_action_en if high_gaps else "Attach observation completeness attestation."
            else:
                tier = PriorityTier.P2_EXPLORATORY.value
                base_score = 40.0 + (scorecard.heuristic_readiness_index * 0.2)
                effort = "LOW"
                data_status = "AVAILABLE_LOCAL"
                task_title_tr = f"Doğrulayıcı Replikasyon & Hipotez İncelemesi: {getattr(rec, 'title', rec_id)}"
                task_title_en = f"Confirmatory Replication & Hypothesis Review: {getattr(rec, 'title_en', rec_id)}"
                rec_step_tr = "Ayrı bir veri seti üzerinde bağımsız replikasyon denemesi planlayın."
                rec_step_en = "Plan an out-of-sample independent replication trial."

            # Rationales
            rationales_tr = [
                f"Hazırlık durumu: {scorecard.overall_verdict}",
                f"Tespit edilen kritik boşluk sayısı: {len(critical_gaps)}",
                f"Tespit edilen yüksek öncelikli boşluk sayısı: {len(high_gaps)}",
            ]
            rationales_en = [
                f"Readiness verdict: {scorecard.overall_verdict}",
                f"Critical gaps detected: {len(critical_gaps)}",
                f"High-priority gaps detected: {len(high_gaps)}",
            ]

            tasks.append(
                PrioritizedResearchTask(
                    task_id=f"TASK-PRIO-{rec_id}",
                    record_id=rec_id,
                    record_title_tr=getattr(rec, "title", rec_id),
                    record_title_en=getattr(rec, "title_en", rec_id),
                    priority_tier=tier,
                    priority_score=round(base_score, 1),
                    rank=0,  # assigned after sorting
                    title_tr=task_title_tr,
                    title_en=task_title_en,
                    rationales_tr=rationales_tr,
                    rationales_en=rationales_en,
                    estimated_effort=effort,
                    data_readiness=data_status,
                    recommended_next_step_tr=rec_step_tr,
                    recommended_next_step_en=rec_step_en,
                )
            )

        # Sort descending by priority_score, then tie-break by record_id
        tasks.sort(key=lambda t: (-t.priority_score, t.record_id))

        # Assign deterministic ranks (1, 2, 3...)
        for idx, task in enumerate(tasks, start=1):
            task.rank = idx

        return tasks


# Global priority engine instance
research_priority_engine = ResearchPriorityEngine()

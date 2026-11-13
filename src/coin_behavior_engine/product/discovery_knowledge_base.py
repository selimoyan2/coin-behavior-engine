"""Research Discovery Knowledge Base (Module 28.9).

Durable, searchable repository of validated historical scientific discoveries:
- Canonical knowledge record schema linking discoveries, hypotheses, evidence grades,
  reproduction verdicts, regime stability, and contradictions.
- Full-text search and faceted filtering.
- Bi-directional traceability to raw source artifacts and reports.
- Durable JSON persistence.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_KNOWLEDGE_BASE_PERSISTENCE = REPO_ROOT / "data" / "research_lab" / "discovery_knowledge_base.json"


@dataclass
class DiscoveryKnowledgeRecord:
    """Canonical discovery knowledge base record."""
    knowledge_record_id: str
    discovery_id: str
    research_id: str
    hypothesis_id: str
    finding_statement: str
    evidence_grade: str  # From CATEGORICAL_EVIDENCE_GRADES
    validation_verdict: str
    reproduction_verdict: str
    independence_verdict: str
    regime_stability_verdict: str
    contradiction_status: str  # RESOLVED, NO_CONTRADICTIONS, ACTIVE_CONTRADICTION
    limitations: List[str]
    supporting_evidence_ids: List[str]
    report_artifact_ids: List[str]
    record_type: str = "DEMONSTRATION_FIXTURE"  # VERIFIED_HISTORICAL_EVIDENCE, EXPLORATORY_DERIVED_RECORD, DEMONSTRATION_FIXTURE
    record_created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    record_updated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def status(self) -> str:
        return self.evidence_grade

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DiscoveryKnowledgeBase:
    """Searchable knowledge base for historical scientific discoveries."""

    def __init__(self, persistence_path: Optional[Path] = None):
        self.persistence_path = persistence_path or DEFAULT_KNOWLEDGE_BASE_PERSISTENCE
        self._records: Dict[str, DiscoveryKnowledgeRecord] = {}
        self._load_from_storage()
        if not self._records:
            self._seed_canonical_records()

    def _load_from_storage(self) -> None:
        """Load records from storage."""
        if not self.persistence_path.exists():
            return
        try:
            with open(self.persistence_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            for item in raw.get("knowledge_records", []):
                item_copy = dict(item)
                if item_copy.get("knowledge_record_id") == "KB-REG-SHIFT-002":
                    item_copy["evidence_grade"] = "PRELIMINARY_SUPPORT"
                    item_copy["reproduction_verdict"] = "PARTIALLY_REPRODUCED"
                    item_copy["independence_verdict"] = "DISTINCT_PARTITIONS_SAME_SOURCE"
                rec = DiscoveryKnowledgeRecord(**item_copy)
                self._records[rec.knowledge_record_id] = rec
        except Exception as e:
            logger.error(f"Error loading knowledge base: {e}")

    def save_to_storage(self) -> None:
        """Atomically persist knowledge base records."""
        self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.persistence_path.with_suffix(".tmp")
        payload = {
            "schema_version": "CBE-KNOWLEDGE-BASE-V28",
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "knowledge_records": [r.to_dict() for r in self._records.values()],
        }
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        tmp.replace(self.persistence_path)

    def _seed_canonical_records(self) -> None:
        """Seed foundational knowledge records."""
        # 1. Volatility Clustering
        k1 = DiscoveryKnowledgeRecord(
            knowledge_record_id="KB-VOL-CLUST-001",
            discovery_id="DISC-VOL-CLUST-001",
            research_id="RES-STAT-02",
            hypothesis_id="HYP-VOL-PERSIST-001",
            finding_statement="Historical BTC/USDT spot return variance exhibits statistically significant autoregressive conditional heteroskedasticity (ARCH effect p < 0.001) that persists across 2024 quarterly regimes.",
            evidence_grade="VALIDATED_HISTORICAL_EVIDENCE",
            validation_verdict="VALIDATION_CONFIRMED",
            reproduction_verdict="REPEATABILITY_VERIFIED",
            independence_verdict="SAME_DATASET",
            regime_stability_verdict="STABLE_ACROSS_EVALUATED_REGIMES",
            contradiction_status="NO_CONTRADICTIONS",
            limitations=[
                "Evaluated on spot hourly bars; structural intraday shocks not modeled.",
                "Finding describes historical statistical variance clustering, not directional predictability.",
            ],
            supporting_evidence_ids=["ART-VOL-001", "VAL-VOL-2024-01", "GRD-VOL-001"],
            report_artifact_ids=["REP-VOL-DISCOVERY-2024", "REP-OOS-VOL-2024"],
            record_type="DEMONSTRATION_FIXTURE",
        )
        self._records[k1.knowledge_record_id] = k1

        # 2. Distribution Shift - Reclassified from false independent replication
        k2 = DiscoveryKnowledgeRecord(
            knowledge_record_id="KB-REG-SHIFT-002",
            discovery_id="DISC-REG-SHIFT-002",
            research_id="RES-GEN-05",
            hypothesis_id="HYP-REG-SHIFT-002",
            finding_statement="15-minute return distributions in high-volatility expansion regimes differ significantly from low-volatility consolidation regimes (Kolmogorov-Smirnov distance = 0.082, p < 0.01), evaluated across non-overlapping quarters.",
            evidence_grade="PRELIMINARY_SUPPORT",
            validation_verdict="VALIDATION_CONFIRMED",
            reproduction_verdict="PARTIALLY_REPRODUCED",
            independence_verdict="DISTINCT_PARTITIONS_SAME_SOURCE",
            regime_stability_verdict="STABLE_ACROSS_EVALUATED_REGIMES",
            contradiction_status="NO_CONTRADICTIONS",
            limitations=[
                "Intraday seasonality remains present in both distributions.",
                "Independent dataset replication not established: Q1 and Q3 originate from the same exchange (Binance) and instrument.",
            ],
            supporting_evidence_ids=["ART-DIST-002", "REP-IND-DATA-003", "GRD-REG-SHIFT-002"],
            report_artifact_ids=["REP-REG-SHIFT-2024"],
            record_type="DEMONSTRATION_FIXTURE",
        )
        self._records[k2.knowledge_record_id] = k2

        # 3. Retrospective Analog Inconclusive
        k3 = DiscoveryKnowledgeRecord(
            knowledge_record_id="KB-ANALOG-EXP-003",
            discovery_id="DISC-ANALOG-EXP-003",
            research_id="RES-HIST-01",
            hypothesis_id="HYP-RETRO-ANALOG-003",
            finding_statement="Retrospective historical analog pattern matching fails to provide statistically significant directional accuracy over random walk expectations (accuracy = 51.8%, p = 0.485).",
            evidence_grade="EXPLORATORY_EVIDENCE",
            validation_verdict="VALIDATION_FAILED",
            reproduction_verdict="REPEATABILITY_VERIFIED",
            independence_verdict="SAME_DATASET",
            regime_stability_verdict="REGIME_DEPENDENT",
            contradiction_status="RESOLVED",
            limitations=[
                "Directional predictability null hypothesis could not be rejected.",
                "High sensitivity to distance metric hyperparameters.",
            ],
            supporting_evidence_ids=["ART-ANALOG-003", "GRD-ANALOG-EXP-003"],
            report_artifact_ids=["REP-ANALOG-EXP-2024"],
        )
        self._records[k3.knowledge_record_id] = k3

        self.save_to_storage()

    def search(
        self,
        query: Optional[str] = None,
        evidence_grade: Optional[str] = None,
        hypothesis_id: Optional[str] = None,
        research_id: Optional[str] = None,
    ) -> List[DiscoveryKnowledgeRecord]:
        """Search knowledge base with multi-criteria filtering."""
        results: List[DiscoveryKnowledgeRecord] = []
        q = (query or "").lower().strip()

        for rec in self._records.values():
            if evidence_grade and rec.evidence_grade != evidence_grade:
                continue
            if hypothesis_id and rec.hypothesis_id != hypothesis_id:
                continue
            if research_id and rec.research_id != research_id:
                continue
            if q:
                match = (
                    q in rec.knowledge_record_id.lower()
                    or q in rec.discovery_id.lower()
                    or q in rec.finding_statement.lower()
                    or any(q in lim.lower() for lim in rec.limitations)
                )
                if not match:
                    continue
            results.append(rec)

        return results

    def record_finding(self, record: DiscoveryKnowledgeRecord) -> None:
        self._records[record.knowledge_record_id] = record
        self.save_to_storage()

    def list_records(self) -> List[DiscoveryKnowledgeRecord]:
        return list(self._records.values())

    def get_record(self, record_id: str) -> Optional[DiscoveryKnowledgeRecord]:
        return self._records.get(record_id)

    def get_finding(self, discovery_id: str) -> Optional[DiscoveryKnowledgeRecord]:
        for rec in self._records.values():
            if rec.discovery_id == discovery_id or rec.knowledge_record_id == discovery_id:
                return rec
        return None

    def add_finding(
        self,
        discovery_id: str,
        hypothesis_id: str,
        research_id: str,
        finding_name: str,
        evidence_grade: str = "PRELIMINARY_SUPPORT",
        statistical_p_value: float = 0.01,
        limitations: Optional[List[str]] = None,
    ) -> DiscoveryKnowledgeRecord:
        rec = DiscoveryKnowledgeRecord(
            knowledge_record_id=f"KB-{discovery_id}",
            discovery_id=discovery_id,
            research_id=research_id,
            hypothesis_id=hypothesis_id,
            finding_statement=finding_name,
            evidence_grade=evidence_grade,
            validation_verdict="VALIDATED",
            reproduction_verdict="REPEATABILITY_VERIFIED",
            independence_verdict="SAME_DATASET",
            regime_stability_verdict="STABLE",
            contradiction_status="NO_CONTRADICTIONS",
            limitations=limitations or [],
            supporting_evidence_ids=[discovery_id],
            report_artifact_ids=[],
            record_type="VERIFIED_HISTORICAL_EVIDENCE",
        )
        self.record_finding(rec)
        return rec

    def invalidate_or_downgrade_finding(self, discovery_id: str, new_grade: str, reason: str = "") -> List[str]:
        """Propagate evidence grade downgrade or invalidation across knowledge base records."""
        affected: List[str] = []
        clean_id = str(discovery_id or "").strip()
        for rec in self._records.values():
            if rec.discovery_id == clean_id or clean_id in rec.supporting_evidence_ids:
                rec.evidence_grade = new_grade
                if reason:
                    rec.limitations.append(f"DOWNGRADE: {reason}")
                affected.append(rec.knowledge_record_id)
        if affected:
            self.save_to_storage()
        return affected

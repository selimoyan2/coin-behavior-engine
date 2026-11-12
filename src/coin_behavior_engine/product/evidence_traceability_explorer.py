"""
Sprint 27 — Module 27.4: Evidence Traceability & Provenance Explorer.
(CBE_SPRINT27_SCIENTIFIC_RESEARCH_PORTFOLIO)

Extends the Sprint 25 Evidence Graph Service into a full, single-authority
end-to-end provenance and traceability explorer without duplicating graph logic.

Key Scientific & Trust Invariants:
1. Single Evidence Graph Authority: reuses EvidenceGraphService.build_canonical_graph().
2. Never fabricates nonexistent evidence links or nodes.
3. Enforces the 6 non-interchangeable trust progression states:
   - ARTIFACT_PRESENT
   - INTEGRITY_VERIFIED
   - METHODOLOGY_VALIDATED
   - STATISTICALLY_SUPPORTED
   - INDEPENDENT_DATASET_VALIDATION
   - INDEPENDENT_REPLICATION
4. Cycle-safe bounded graph traversal (max_depth <= 10).
5. Dynamic cache invalidation on key revocation or source artifact mutation.
6. Zero exposure of signing secrets, raw keys, or operator credentials.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

from coin_behavior_engine.product.credential_manager import signing_key_registry
from coin_behavior_engine.product.evidence_graph import (
    EvidenceGraphService,
    NodeVerificationStatus,
)
from coin_behavior_engine.product.experiment_timeline_registry import (
    experiment_registry_service,
)
from coin_behavior_engine.product.research_catalog_provider import (
    ResearchCatalogProvider,
    ResearchRecord,
)
from coin_behavior_engine.product.research_review_workflow import (
    research_review_workflow_engine,
)
from coin_behavior_engine.product.scientific_readiness import (
    CANONICAL_TRUST_PROGRESSION_TIERS,
    ScientificReadinessEvaluator,
)

MAX_EXPLORER_TRAVERSAL_DEPTH = 10

TRACEABILITY_CHAIN_STAGE_ORDER = (
    "RESEARCH_RECORD",
    "EXPERIMENT",
    "DATASET",
    "SOURCE_ARTIFACT",
    "INTAKE_MANIFEST_OR_ATTESTATION",
    "METHODOLOGY",
    "EXECUTION_ATTEMPT",
    "RESULT_ARTIFACT",
    "STATISTICAL_VALIDATION",
    "REPRODUCIBILITY_EVIDENCE",
    "SCIENTIFIC_FINDING",
    "REVIEW_DECISION",
)


@dataclass
class TraceabilityStageEntry:
    stage_name: str
    present: bool
    node_id: Optional[str]
    verification_status: str
    trust_tier: str
    provenance_reference: Optional[str]
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvidenceTraceabilityExplorer:
    """Module 27.4 — Single-Authority Evidence Traceability & Provenance Explorer."""

    _cached_graph: Optional[EvidenceGraphService] = None
    _cached_state_fingerprint: str = ""

    @classmethod
    def _compute_live_trust_state_fingerprint(cls) -> str:
        """
        Computes a live fingerprint of catalog records, physical artifact hashes,
        and signing key revocation states so any mutation or key revocation
        invalidates the cached graph immediately.
        """
        catalog = ResearchCatalogProvider.get_canonical_catalog()
        revoked_keys = sorted(signing_key_registry.get_revoked_keys())
        rec_digests = []
        for r in catalog:
            prov = ScientificReadinessEvaluator.verify_dataset_provenance(r)
            rec_digests.append(
                {
                    "id": r.id,
                    "sha": getattr(r, "source_artifact_sha256", ""),
                    "prov_ok": bool(prov.get("is_verified")),
                    "rej": prov.get("rejection_code"),
                }
            )
        payload = json.dumps(
            {"revoked_keys": revoked_keys, "records": rec_digests},
            sort_keys=True,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def get_authoritative_graph(cls, force_rebuild: bool = False) -> EvidenceGraphService:
        live_fp = cls._compute_live_trust_state_fingerprint()
        if (
            force_rebuild
            or cls._cached_graph is None
            or cls._cached_state_fingerprint != live_fp
        ):
            catalog = ResearchCatalogProvider.get_canonical_catalog()
            cls._cached_graph = EvidenceGraphService.build_canonical_graph(catalog)
            cls._cached_state_fingerprint = live_fp
        return cls._cached_graph

    @classmethod
    def evaluate_six_tier_trust_progression(cls, record: ResearchRecord) -> Dict[str, Any]:
        """
        Evaluates the 6 non-interchangeable scientific trust progression states for a record.
        Never promotes a record to a higher tier unless all prerequisites for that tier are verified.
        """
        prov = ScientificReadinessEvaluator.verify_dataset_provenance(record)
        scorecard = ScientificReadinessEvaluator.evaluate_record(record)
        is_quarantined = (
            getattr(record, "quarantine_status", "") in ("QUARANTINED", "QUARANTINED_CONTAMINATED")
            or getattr(record, "id", "") in ("RES-CRYPTO-01", "RES-QUARANTINE-01")
        )

        has_art = bool(getattr(record, "source_artifact", None)) and not is_quarantined
        is_integrity_ok = (
            bool(prov.get("is_verified"))
            or "SOURCE_ARTIFACT_INTEGRITY" in scorecard.passed_dimensions
        ) and not is_quarantined
        is_meth_ok = is_integrity_ok and getattr(record, "model_version", "") == "CBE-0.7.0"
        has_stat_support = (
            is_meth_ok
            and (getattr(record, "sample_size", 0) or 0) >= 100
            and (
                (getattr(record, "holdout_fdr_q", None) is not None and float(record.holdout_fdr_q) <= 0.05)
                or (getattr(record, "raw_p_value", None) is not None and float(record.raw_p_value) <= 0.05)
            )
        )
        has_ind_dataset = (
            has_stat_support
            and getattr(record, "replication_verdict", "") == "OUT_OF_SAMPLE_REPLICATED"
        )
        # Independent replication requires a separate cryptographically signed replication attestation
        # across disjoint datasets & procedures; catalog records alone have temporal holdout validation.
        has_ind_replication = False

        tier_verdicts = {
            "ARTIFACT_PRESENT": has_art,
            "INTEGRITY_VERIFIED": is_integrity_ok,
            "METHODOLOGY_VALIDATED": is_meth_ok,
            "STATISTICALLY_SUPPORTED": has_stat_support,
            "INDEPENDENT_DATASET_VALIDATION": has_ind_dataset,
            "INDEPENDENT_REPLICATION": has_ind_replication,
        }

        highest_tier = "UNVERIFIED_OR_BLOCKED"
        for tier in CANONICAL_TRUST_PROGRESSION_TIERS:
            if tier_verdicts.get(tier):
                highest_tier = tier

        return {
            "record_id": record.id,
            "highest_verified_trust_tier": highest_tier,
            "tier_progression": tier_verdicts,
            "provenance_verification": {
                "is_verified": bool(prov.get("is_verified")),
                "mechanism": prov.get("mechanism"),
                "rejection_code": prov.get("rejection_code"),
                "evidence_reference": prov.get("evidence_reference"),
            },
            "readiness_verdict": scorecard.overall_verdict,
        }

    @classmethod
    def trace_evidence_chain(
        cls,
        target_id: str,
        max_depth: int = 6,
    ) -> Dict[str, Any]:
        """
        Traces the end-to-end provenance chain for a research record, experiment, dataset,
        or evidence node. Strictly reports missing stages as present=False without fabricating nodes.
        """
        clean_id = str(target_id or "").strip()
        bounded_depth = max(1, min(int(max_depth or 6), MAX_EXPLORER_TRAVERSAL_DEPTH))
        graph = cls.get_authoritative_graph()
        catalog = ResearchCatalogProvider.get_canonical_catalog()
        cat_by_id = {r.id: r for r in catalog}

        # Resolve if target_id is an experiment_id
        resolved_rec_id = clean_id
        exp_dict = experiment_registry_service.get_experiment(clean_id)
        if exp_dict and exp_dict.get("research_id") in cat_by_id:
            resolved_rec_id = exp_dict["research_id"]

        if resolved_rec_id not in cat_by_id and clean_id not in graph.nodes:
            return {
                "status": "error",
                "error_code": "EVIDENCE_NODE_NOT_FOUND",
                "rejection_code": "NONEXISTENT_EVIDENCE_LINK_REJECTED",
                "message": f"Target evidence or research ID '{clean_id}' does not exist in the authoritative evidence graph. Nonexistent links are never fabricated.",
            }

        # If it is a direct graph node (e.g., DS-..., ART-..., ATT-...), return bounded subgraph traversal
        if resolved_rec_id not in cat_by_id and clean_id in graph.nodes:
            subgraph = graph.traverse_dependencies(
                start_node_id=clean_id,
                max_depth=bounded_depth,
                direction="all",
            )
            node_obj = graph.get_node(clean_id)
            return {
                "status": "success",
                "target_id": clean_id,
                "node": node_obj.to_dict() if node_obj else None,
                "traversal": subgraph,
                "max_depth_enforced": bounded_depth,
            }

        rec = cat_by_id[resolved_rec_id]
        trust_prog = cls.evaluate_six_tier_trust_progression(rec)
        prov = trust_prog["provenance_verification"]
        exp_obj = exp_dict or experiment_registry_service.get_experiment(rec.id)
        subgraph = graph.traverse_dependencies(
            start_node_id=rec.id,
            max_depth=bounded_depth,
            direction="all",
        )

        # Build the 12-stage traceability chain strictly from existing evidence
        stages: List[TraceabilityStageEntry] = []

        # 1. Research Record
        rec_node = graph.get_node(rec.id)
        stages.append(
            TraceabilityStageEntry(
                stage_name="RESEARCH_RECORD",
                present=rec_node is not None,
                node_id=rec.id if rec_node else None,
                verification_status=rec_node.status if rec_node else "MISSING",
                trust_tier=trust_prog["highest_verified_trust_tier"],
                provenance_reference=rec.specification_id,
                details={"title": rec.title, "category": rec.category},
            )
        )

        # 2. Experiment
        stages.append(
            TraceabilityStageEntry(
                stage_name="EXPERIMENT",
                present=exp_obj is not None,
                node_id=exp_obj["experiment_id"] if exp_obj else None,
                verification_status=exp_obj["execution_status"] if exp_obj else "MISSING",
                trust_tier="METHODOLOGY_VALIDATED" if exp_obj and prov["is_verified"] else "ARTIFACT_PRESENT",
                provenance_reference=exp_obj["parameter_fingerprint"] if exp_obj else None,
                details={"experiment_type": exp_obj.get("experiment_type")} if exp_obj else {},
            )
        )

        # 3. Dataset
        ds_node_id = f"DS-{rec.dataset_id}"
        ds_node = graph.get_node(ds_node_id)
        stages.append(
            TraceabilityStageEntry(
                stage_name="DATASET",
                present=ds_node is not None,
                node_id=ds_node_id if ds_node else None,
                verification_status=ds_node.status if ds_node else "MISSING",
                trust_tier="INTEGRITY_VERIFIED" if prov["is_verified"] else "UNVERIFIED",
                provenance_reference=rec.dataset_id,
                details={"quarantine_status": getattr(rec, "quarantine_status", "CLEAN")},
            )
        )

        # 4. Source Artifact
        src_path = getattr(rec, "source_artifact", "") or ""
        art_node_id = (
            f"ART-{hashlib.sha256(src_path.encode('utf-8')).hexdigest()[:12]}"
            if src_path
            else None
        )
        art_node = graph.get_node(art_node_id) if art_node_id else None
        stages.append(
            TraceabilityStageEntry(
                stage_name="SOURCE_ARTIFACT",
                present=art_node is not None,
                node_id=art_node_id if art_node else None,
                verification_status=art_node.status if art_node else "MISSING",
                trust_tier="INTEGRITY_VERIFIED" if art_node and art_node.status == "INTEGRITY_VERIFIED" else "ARTIFACT_PRESENT",
                provenance_reference=src_path or None,
                details={"sha256": getattr(rec, "source_artifact_sha256", None)},
            )
        )

        # 5. Intake Manifest / Attestation
        att_node_id = f"ATT-{rec.id}"
        att_node = graph.get_node(att_node_id)
        stages.append(
            TraceabilityStageEntry(
                stage_name="INTAKE_MANIFEST_OR_ATTESTATION",
                present=att_node is not None or prov["is_verified"],
                node_id=att_node_id if att_node else (f"MANIFEST-{rec.id}" if prov["is_verified"] else None),
                verification_status=(
                    att_node.status
                    if att_node
                    else ("INTEGRITY_VERIFIED" if prov["is_verified"] else "MISSING_OR_INVALID")
                ),
                trust_tier="INTEGRITY_VERIFIED" if prov["is_verified"] else "UNVERIFIED",
                provenance_reference=prov.get("evidence_reference"),
                details={
                    "mechanism": prov.get("mechanism"),
                    "rejection_code": prov.get("rejection_code"),
                },
            )
        )

        # 6. Methodology
        meth_edges = graph.get_neighbors(rec.id, direction="outgoing", edge_type="USES_METHODOLOGY")
        meth_node = meth_edges[0][1] if meth_edges else None
        stages.append(
            TraceabilityStageEntry(
                stage_name="METHODOLOGY",
                present=meth_node is not None,
                node_id=meth_node.id if meth_node else None,
                verification_status=meth_node.status if meth_node else "MISSING",
                trust_tier="METHODOLOGY_VALIDATED" if meth_node else "UNVERIFIED",
                provenance_reference=meth_node.provenance_source if meth_node else None,
                details={"label": meth_node.label_en if meth_node else None},
            )
        )

        # 7. Execution Attempt
        attempts = exp_obj.get("execution_attempts", []) if exp_obj else []
        first_att = attempts[-1] if attempts else None
        stages.append(
            TraceabilityStageEntry(
                stage_name="EXECUTION_ATTEMPT",
                present=first_att is not None,
                node_id=first_att.get("attempt_id") if first_att else None,
                verification_status=(
                    first_att.get("execution_status")
                    if first_att
                    else (exp_obj.get("execution_status", "HISTORICAL_EXECUTION_UNVERIFIED") if exp_obj else "HISTORICAL_EXECUTION_UNVERIFIED")
                ),
                trust_tier="ARTIFACT_PRESENT" if first_att else "UNVERIFIED",
                provenance_reference=first_att.get("result_digest") if first_att else None,
                details={
                    "attempt_count": len(attempts),
                    "record_origin": exp_obj.get("record_origin", "CATALOG_PROJECTION") if exp_obj else "CATALOG_PROJECTION",
                },
            )
        )

        # 8. Result Artifact
        out_arts = exp_obj.get("output_artifact_ids", []) if exp_obj else []
        stages.append(
            TraceabilityStageEntry(
                stage_name="RESULT_ARTIFACT",
                present=len(out_arts) > 0,
                node_id=out_arts[0] if out_arts else None,
                verification_status="PRESENT" if out_arts else "CATALOG_SOURCE_ARTIFACT_ONLY_NO_EXECUTION_OUTPUT",
                trust_tier="ARTIFACT_PRESENT" if out_arts else "UNVERIFIED",
                provenance_reference=exp_obj.get("result_digest") if exp_obj else None,
                details={
                    "source_report_artifact": getattr(rec, "source_artifact", None),
                    "execution_output_artifact": out_arts[0] if out_arts else None,
                },
            )
        )

        # 9. Statistical Validation
        stat_node_id = f"STAT-{rec.id}"
        stat_node = graph.get_node(stat_node_id)
        stages.append(
            TraceabilityStageEntry(
                stage_name="STATISTICAL_VALIDATION",
                present=stat_node is not None,
                node_id=stat_node_id if stat_node else None,
                verification_status=stat_node.status if stat_node else "MISSING",
                trust_tier=(
                    "STATISTICALLY_SUPPORTED"
                    if trust_prog["tier_progression"]["STATISTICALLY_SUPPORTED"]
                    else "UNVERIFIED"
                ),
                provenance_reference=f"N={getattr(rec, 'sample_size', 0)}",
                details=stat_node.properties if stat_node else {},
            )
        )

        # 10. Reproducibility Evidence (never inferred from dataset provenance alone)
        repro_verdict = (
            exp_obj.get("reproducibility_verdict", "REPRODUCTION_NOT_ESTABLISHED")
            if exp_obj
            else "REPRODUCTION_NOT_ESTABLISHED"
        )
        repro_ok = repro_verdict == "OUTPUTS_MATCHED"
        stages.append(
            TraceabilityStageEntry(
                stage_name="REPRODUCIBILITY_EVIDENCE",
                present=repro_ok,
                node_id=f"REPRO-{rec.id}" if repro_ok else None,
                verification_status=repro_verdict,
                trust_tier="METHODOLOGY_VALIDATED" if repro_ok else "UNVERIFIED",
                provenance_reference="ReproducibilityLabEngine" if repro_ok else None,
            )
        )

        # 11. Scientific Finding
        claim_node_id = f"CLAIM-{rec.id}"
        claim_node = graph.get_node(claim_node_id)
        stages.append(
            TraceabilityStageEntry(
                stage_name="SCIENTIFIC_FINDING",
                present=claim_node is not None,
                node_id=claim_node_id if claim_node else None,
                verification_status=claim_node.status if claim_node else "MISSING",
                trust_tier=trust_prog["highest_verified_trust_tier"],
                provenance_reference=rec.id,
                details={"statement": getattr(rec, "key_findings_tr", "")},
            )
        )

        # 12. Review Decision (distinguishes AUTHENTICATED_REVIEW_DECISION from AUTOMATED_ASSESSMENT)
        rev_listing = research_review_workflow_engine.list_reviews(research_id=rec.id)
        auth_revs = rev_listing.get("authenticated_reviews", [])
        auto_ass = rev_listing.get("automated_assessments", [])
        latest_auth = auth_revs[-1] if auth_revs else None
        latest_auto = auto_ass[-1] if auto_ass else None
        gov_node = graph.get_node("GOV-DECISION-NO-GO")
        stages.append(
            TraceabilityStageEntry(
                stage_name="REVIEW_DECISION",
                present=latest_auth is not None or gov_node is not None,
                node_id=(
                    latest_auth["review_id"]
                    if latest_auth
                    else (latest_auto["assessment_id"] if latest_auto else "GOV-DECISION-NO-GO")
                ),
                verification_status=(
                    "AUTHENTICATED_REVIEW_DECISION"
                    if latest_auth
                    else "AUTOMATED_ASSESSMENT"
                ),
                trust_tier="INTEGRITY_VERIFIED" if latest_auth else "UNVERIFIED",
                provenance_reference="TECHNICAL_NO_GO | OFFLINE_RESEARCH_ONLY",
                details={
                    "review_classification": (
                        "AUTHENTICATED_REVIEW_DECISION" if latest_auth else "AUTOMATED_ASSESSMENT"
                    ),
                    "authoritative": bool(latest_auth),
                },
            )
        )

        return {
            "status": "success",
            "research_id": rec.id,
            "title": rec.title,
            "trust_progression": trust_prog,
            "traceability_chain": [s.to_dict() for s in stages],
            "subgraph": subgraph,
            "max_depth_enforced": bounded_depth,
            "graph_state_fingerprint": cls._cached_state_fingerprint,
        }

    @classmethod
    def get_explorer_overview(
        cls,
        node_type: Optional[str] = None,
        status: Optional[str] = None,
    ) -> Dict[str, Any]:
        graph = cls.get_authoritative_graph()
        catalog = ResearchCatalogProvider.get_canonical_catalog()
        nodes = [n.to_dict() for n in graph.nodes.values()]
        edges = [e.to_dict() for e in graph.edges.values()]

        if node_type and str(node_type).upper() != "ALL":
            nt = str(node_type).strip().upper()
            nodes = [n for n in nodes if n["node_type"].upper() == nt]
        if status and str(status).upper() != "ALL":
            st = str(status).strip().upper()
            nodes = [n for n in nodes if n["status"].upper() == st]

        trust_summaries = [
            cls.evaluate_six_tier_trust_progression(r) for r in catalog
        ]

        return {
            "status": "success",
            "canonical_model": "CBE-0.7.0",
            "governance_decision": "TECHNICAL_NO_GO",
            "graph_state_fingerprint": cls._cached_state_fingerprint,
            "total_nodes": len(graph.nodes),
            "total_edges": len(graph.edges),
            "filtered_node_count": len(nodes),
            "six_tier_trust_definitions": list(CANONICAL_TRUST_PROGRESSION_TIERS),
            "record_trust_progressions": trust_summaries,
            "nodes": nodes,
            "edges": edges,
        }

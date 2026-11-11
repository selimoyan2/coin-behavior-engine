"""
Scientific Evidence Graph Service.
Sprint 25: Research Evidence Graph, Scientific Readiness & Decision Intelligence Platform.
(CBE_SPRINT25_RESEARCH_DECISION_INTELLIGENCE)

Connects research hypotheses, datasets, research records, experimental procedures,
statistical results, source artifacts, attestations, replication attempts,
methodologies, scientific claims, and governance decisions into a deterministic,
fail-closed evidence relationship network.
Enforces Sprint 24 cryptographic verifier integration, physical source artifact integrity,
and separation of REGISTERED, PRESENT, INTEGRITY_VERIFIED, and SCIENTIFICALLY_VERIFIED statuses.
"""

from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from coin_behavior_engine.product.attestation_verifier import (
    ObservationCompletenessAttestationVerifier,
)


class EvidenceNodeType(str, enum.Enum):
    RESEARCH_HYPOTHESIS = "RESEARCH_HYPOTHESIS"
    DATASET = "DATASET"
    RESEARCH_RECORD = "RESEARCH_RECORD"
    EXPERIMENT = "EXPERIMENT"
    STATISTICAL_RESULT = "STATISTICAL_RESULT"
    SOURCE_ARTIFACT = "SOURCE_ARTIFACT"
    ATTESTATION = "ATTESTATION"
    REPLICATION_ATTEMPT = "REPLICATION_ATTEMPT"
    SCIENTIFIC_CLAIM = "SCIENTIFIC_CLAIM"
    METHODOLOGY = "METHODOLOGY"
    GOVERNANCE_DECISION = "GOVERNANCE_DECISION"


class EvidenceEdgeType(str, enum.Enum):
    USES_DATASET = "USES_DATASET"
    DERIVED_FROM = "DERIVED_FROM"
    SUPPORTED_BY = "SUPPORTED_BY"
    CONTRADICTED_BY = "CONTRADICTED_BY"
    VERIFIED_BY = "VERIFIED_BY"
    REPLICATED_BY = "REPLICATED_BY"
    TESTS_HYPOTHESIS = "TESTS_HYPOTHESIS"
    USES_METHODOLOGY = "USES_METHODOLOGY"
    BLOCKED_BY = "BLOCKED_BY"
    SUPERSEDES = "SUPERSEDES"


class NodeVerificationStatus(str, enum.Enum):
    REGISTERED = "REGISTERED"
    PRESENT = "PRESENT"
    INTEGRITY_VERIFIED = "INTEGRITY_VERIFIED"
    SCIENTIFICALLY_VERIFIED = "SCIENTIFICALLY_VERIFIED"
    VERIFIED = "VERIFIED"  # Kept for backward compatibility
    UNVERIFIED = "UNVERIFIED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


@dataclass
class EvidenceGraphNode:
    id: str
    node_type: str  # from EvidenceNodeType
    label: str
    label_en: str
    status: str = NodeVerificationStatus.UNVERIFIED.value
    provenance_source: str = ""
    source_artifact_sha256: Optional[str] = None
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceGraphEdge:
    id: str
    source_id: str
    target_id: str
    edge_type: str  # from EvidenceEdgeType
    label: str
    label_en: str
    is_verified: bool = False
    provenance_reference: str = ""
    properties: Dict[str, Any] = field(default_factory=dict)
    created_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvidenceGraphService:
    """
    Deterministic canonical in-memory evidence relationship graph.
    Provides node & edge registries, cycle-safe bounded traversal, provenance resolution,
    missing-link detection, and fail-closed integrity validation.
    """

    MAX_TRAVERSAL_DEPTH = 10
    MAX_QUERY_LIMIT = 500

    def __init__(self):
        self._nodes: Dict[str, EvidenceGraphNode] = {}
        self._edges: Dict[str, EvidenceGraphEdge] = {}
        self._adj_out: Dict[str, List[str]] = {}  # node_id -> [edge_id]
        self._adj_in: Dict[str, List[str]] = {}   # node_id -> [edge_id]
        self._evidence_fingerprint: str = ""

    @property
    def nodes(self) -> Dict[str, EvidenceGraphNode]:
        return self._nodes

    @property
    def edges(self) -> Dict[str, EvidenceGraphEdge]:
        return self._edges

    def add_node(self, node: EvidenceGraphNode) -> None:
        self._nodes[node.id] = node
        if node.id not in self._adj_out:
            self._adj_out[node.id] = []
        if node.id not in self._adj_in:
            self._adj_in[node.id] = []

    def add_edge(self, edge: EvidenceGraphEdge) -> None:
        if edge.source_id not in self._nodes or edge.target_id not in self._nodes:
            raise ValueError(
                f"Cannot add edge {edge.id}: source ({edge.source_id}) or target ({edge.target_id}) node does not exist."
            )
        self._edges[edge.id] = edge
        self._adj_out[edge.source_id].append(edge.id)
        self._adj_in[edge.target_id].append(edge.id)

    def get_node(self, node_id: str) -> Optional[EvidenceGraphNode]:
        return self._nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Optional[EvidenceGraphEdge]:
        return self._edges.get(edge_id)

    def get_neighbors(
        self,
        node_id: str,
        direction: str = "all",
        edge_type: Optional[str] = None,
    ) -> List[Tuple[EvidenceGraphEdge, EvidenceGraphNode]]:
        """
        Returns list of (edge, adjacent_node) with optional direction and edge_type filter.
        direction: 'outgoing'/'outbound', 'incoming'/'inbound', 'all'/'both'
        """
        if node_id not in self._nodes:
            return []

        norm_dir = direction.lower() if direction else "all"
        results = []
        if norm_dir in ("outgoing", "outbound", "all", "both"):
            for e_id in self._adj_out.get(node_id, []):
                e = self._edges[e_id]
                if edge_type is None or e.edge_type == edge_type:
                    target_node = self._nodes[e.target_id]
                    results.append((e, target_node))

        if norm_dir in ("incoming", "inbound", "all", "both"):
            for e_id in self._adj_in.get(node_id, []):
                e = self._edges[e_id]
                if edge_type is None or e.edge_type == edge_type:
                    source_node = self._nodes[e.source_id]
                    results.append((e, source_node))

        return results

    def traverse(
        self,
        start_node_id: str,
        max_depth: int = 4,
        direction: str = "outgoing",
        edge_types: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """
        Cycle-safe bounded depth-first search / breadth-first search traversal.
        Returns reachable subgraph nodes and edges.
        """
        depth_limit = min(max_depth, self.MAX_TRAVERSAL_DEPTH)
        if start_node_id not in self._nodes:
            return {"nodes": [], "edges": [], "root_id": start_node_id, "depth_reached": 0}

        visited_nodes: Set[str] = {start_node_id}
        visited_edges: Set[str] = set()
        queue: List[Tuple[str, int]] = [(start_node_id, 0)]
        max_seen_depth = 0

        while queue:
            curr_id, curr_depth = queue.pop(0)
            max_seen_depth = max(max_seen_depth, curr_depth)
            if curr_depth >= depth_limit:
                continue

            # Find edges based on direction
            norm_dir = direction.lower() if direction else "outgoing"
            edge_ids: List[str] = []
            if norm_dir in ("outgoing", "outbound", "all", "both"):
                edge_ids.extend(self._adj_out.get(curr_id, []))
            if norm_dir in ("incoming", "inbound", "all", "both"):
                edge_ids.extend(self._adj_in.get(curr_id, []))

            for e_id in edge_ids:
                if e_id in visited_edges:
                    continue
                edge = self._edges[e_id]
                if edge_types and edge.edge_type not in edge_types:
                    continue

                visited_edges.add(e_id)
                next_node_id = edge.target_id if edge.source_id == curr_id else edge.source_id
                if next_node_id not in visited_nodes:
                    visited_nodes.add(next_node_id)
                    queue.append((next_node_id, curr_depth + 1))

        return {
            "root_id": start_node_id,
            "depth_reached": max_seen_depth,
            "nodes": [self._nodes[nid].to_dict() for nid in visited_nodes],
            "edges": [self._edges[eid].to_dict() for eid in visited_edges],
        }

    def traverse_dependencies(
        self,
        start_node_id: str,
        max_depth: int = 10,
        direction: str = "outgoing",
    ) -> Dict[str, Any]:
        """
        Traverses dependency edges with cycle detection and depth boundedness.
        Returns visited nodes, edges, max depth, and cycle detection flag.
        """
        depth_limit = min(max_depth, self.MAX_TRAVERSAL_DEPTH)
        if start_node_id not in self._nodes:
            return {"nodes": [], "edges": [], "root_id": start_node_id, "depth_reached": 0, "has_cycle": False}

        visited_nodes: Set[str] = {start_node_id}
        visited_edges: Set[str] = set()
        queue: List[Tuple[str, int, List[str]]] = [(start_node_id, 0, [start_node_id])]
        max_seen_depth = 0
        has_cycle = False

        norm_dir = direction.lower() if direction else "outgoing"

        while queue:
            curr_id, curr_depth, path = queue.pop(0)
            max_seen_depth = max(max_seen_depth, curr_depth)
            if curr_depth >= depth_limit:
                continue

            edge_ids: List[str] = []
            if norm_dir in ("outgoing", "outbound", "all", "both"):
                edge_ids.extend(self._adj_out.get(curr_id, []))
            if norm_dir in ("incoming", "inbound", "all", "both"):
                edge_ids.extend(self._adj_in.get(curr_id, []))

            for e_id in edge_ids:
                edge = self._edges[e_id]
                next_node_id = edge.target_id if edge.source_id == curr_id else edge.source_id

                if next_node_id in path:
                    has_cycle = True

                if e_id not in visited_edges:
                    visited_edges.add(e_id)

                if next_node_id not in visited_nodes:
                    visited_nodes.add(next_node_id)
                    queue.append((next_node_id, curr_depth + 1, path + [next_node_id]))

        return {
            "root_id": start_node_id,
            "depth_reached": max_seen_depth,
            "has_cycle": has_cycle,
            "nodes": [self._nodes[nid].to_dict() for nid in visited_nodes],
            "edges": [self._edges[eid].to_dict() for eid in visited_edges],
        }

    def query_subgraph(
        self,
        node_type: Optional[str] = None,
        verification_status: Optional[str] = None,
        edge_type: Optional[str] = None,
        limit: int = 200,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Retrieves a filtered, paginated subgraph with nodes and interconnecting edges.
        """
        filtered_nodes = list(self._nodes.values())
        if node_type:
            filtered_nodes = [n for n in filtered_nodes if n.node_type == node_type]

        if verification_status:
            target_status = verification_status.upper()
            if target_status == "VERIFIED":
                filtered_nodes = [
                    n for n in filtered_nodes
                    if n.status in (
                        NodeVerificationStatus.VERIFIED.value,
                        NodeVerificationStatus.INTEGRITY_VERIFIED.value,
                        NodeVerificationStatus.SCIENTIFICALLY_VERIFIED.value,
                    )
                ]
            else:
                filtered_nodes = [n for n in filtered_nodes if n.status.upper() == target_status]

        total_nodes = len(filtered_nodes)
        paged_nodes = filtered_nodes[offset : offset + min(limit, self.MAX_QUERY_LIMIT)]
        paged_node_ids = {n.id for n in paged_nodes}

        filtered_edges = [
            e for e in self._edges.values()
            if e.source_id in paged_node_ids and e.target_id in paged_node_ids
        ]
        if edge_type:
            filtered_edges = [e for e in filtered_edges if e.edge_type == edge_type]

        return {
            "nodes": [n.to_dict() for n in paged_nodes],
            "edges": [e.to_dict() for e in filtered_edges],
            "node_count": len(paged_nodes),
            "edge_count": len(filtered_edges),
            "total_nodes": total_nodes,
        }

    def detect_missing_links(self) -> List[Dict[str, Any]]:
        """
        Scans graph for structural evidence deficiencies:
        - Research records without verified source artifacts.
        - Records without verified cryptographic completeness attestations.
        - Records using unverified or quarantined datasets.
        - Unverified statistical results and unsupported scientific claims.
        """
        missing_links: List[Dict[str, Any]] = []

        for node_id, node in self._nodes.items():
            if node.node_type == EvidenceNodeType.RESEARCH_RECORD.value:
                # 1. Check Source Artifact derivation
                art_edges = [
                    self._edges[e_id]
                    for e_id in self._adj_out.get(node_id, [])
                    if self._edges[e_id].edge_type == EvidenceEdgeType.DERIVED_FROM.value
                    and self._nodes[self._edges[e_id].target_id].node_type == EvidenceNodeType.SOURCE_ARTIFACT.value
                ]
                has_verified_art = False
                for ae in art_edges:
                    art_node = self._nodes[ae.target_id]
                    if art_node.status in (
                        NodeVerificationStatus.INTEGRITY_VERIFIED.value,
                        NodeVerificationStatus.VERIFIED.value,
                    ):
                        has_verified_art = True
                        break

                if not has_verified_art:
                    missing_links.append({
                        "node_id": node_id,
                        "record_label": node.label,
                        "missing_type": "SOURCE_ARTIFACT_INTEGRITY",
                        "severity": "CRITICAL",
                        "description_tr": "Araştırma kaydının fiziksel disk üzerindeki kaynak belgesi doğrulanmamıştır.",
                        "description_en": "Research record lacks physical source artifact integrity verification.",
                        "recommended_action": "Kaynak dosya varlığını ve SHA-256 bütünlüğünü doğrulayın.",
                    })

                # 2. Check Cryptographic Completeness Attestation
                att_edges = [
                    self._edges[e_id]
                    for e_id in self._adj_out.get(node_id, [])
                    if self._edges[e_id].edge_type == EvidenceEdgeType.VERIFIED_BY.value
                    and self._nodes[self._edges[e_id].target_id].node_type == EvidenceNodeType.ATTESTATION.value
                ]
                has_verified_att = False
                for ae in att_edges:
                    att_node = self._nodes[ae.target_id]
                    if att_node.status in (
                        NodeVerificationStatus.INTEGRITY_VERIFIED.value,
                        NodeVerificationStatus.VERIFIED.value,
                    ):
                        has_verified_att = True
                        break

                if not has_verified_att:
                    missing_links.append({
                        "node_id": node_id,
                        "record_label": node.label,
                        "missing_type": "CRYPTOGRAPHIC_ATTESTATION",
                        "severity": "HIGH",
                        "description_tr": "Araştırma kaydının RFC-8785 gözlem eksiksizliği tasdiki eksik veya geçersizdir.",
                        "description_en": "Missing or invalid RFC-8785 observation completeness attestation envelope.",
                        "recommended_action": "Yetkili veri otoritesinden imzalı tasdik temin edin.",
                    })

                # 3. Check Dataset Usage
                ds_edges = [
                    self._edges[e_id]
                    for e_id in self._adj_out.get(node_id, [])
                    if self._edges[e_id].edge_type == EvidenceEdgeType.USES_DATASET.value
                ]
                if not ds_edges:
                    missing_links.append({
                        "node_id": node_id,
                        "record_label": node.label,
                        "missing_type": "DATASET_LINEAGE",
                        "severity": "CRITICAL",
                        "description_tr": "Araştırma kaydının bağlı olduğu birincil veri seti bulunamadı.",
                        "description_en": "Research record has no primary dataset lineage link.",
                        "recommended_action": "Kayıtlı veri seti bağını tanımlayın.",
                    })
                else:
                    for de in ds_edges:
                        target_ds = self._nodes.get(de.target_id)
                        if target_ds:
                            if target_ds.status == NodeVerificationStatus.BLOCKED.value:
                                missing_links.append({
                                    "node_id": node_id,
                                    "record_label": node.label,
                                    "missing_type": "DATASET_QUARANTINED",
                                    "severity": "CRITICAL",
                                    "description_tr": f"Bağlı veri seti ({target_ds.label}) karantina altında bloke edilmiştir.",
                                    "description_en": f"Linked dataset ({target_ds.label_en}) is quarantined and blocked.",
                                    "recommended_action": "Karantina adli incelemesi tamamlanmadan bu kaydı incelemeye almayın.",
                                })
                            elif target_ds.status not in (
                                NodeVerificationStatus.INTEGRITY_VERIFIED.value,
                                NodeVerificationStatus.SCIENTIFICALLY_VERIFIED.value,
                                NodeVerificationStatus.VERIFIED.value,
                            ):
                                missing_links.append({
                                    "node_id": node_id,
                                    "record_label": node.label,
                                    "missing_type": "DATASET_PROVENANCE_UNVERIFIED",
                                    "severity": "CRITICAL",
                                    "description_tr": f"Bağlı veri setinin ({target_ds.label}) kriptografik soykütüğü doğrulanmamıştır ({target_ds.status}).",
                                    "description_en": f"Linked dataset ({target_ds.label_en}) lacks cryptographically verified provenance ({target_ds.status}).",
                                    "recommended_action": "Veri seti için RFC-8785 imzalı tasdik veya imzalı kabul manifestosu ekleyin.",
                                })

            elif node.node_type == EvidenceNodeType.SCIENTIFIC_CLAIM.value:
                # Claims without independent replication
                rep_edges = [
                    self._edges[e_id]
                    for e_id in self._adj_in.get(node_id, [])
                    if self._edges[e_id].edge_type == EvidenceEdgeType.REPLICATED_BY.value
                ]
                if not rep_edges:
                    missing_links.append({
                        "node_id": node_id,
                        "record_label": node.label,
                        "missing_type": "INDEPENDENT_REPLICATION",
                        "severity": "MEDIUM",
                        "description_tr": "Bilimsel iddia için henüz bağımsız doğrulayıcı replikasyon bulunmamaktadır.",
                        "description_en": "Scientific claim lacks confirmatory independent replication.",
                        "recommended_action": "Ayrı bir veri penceresinde bağımsız replikasyon prosedürü yürütün.",
                    })

        return missing_links

    def query_nodes(
        self,
        node_type: Optional[str] = None,
        verification_status: Optional[str] = None,
        search_query: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """
        Filtered, paginated retrieval of evidence nodes.
        Supports query by status, with 'VERIFIED' matching any of VERIFIED, INTEGRITY_VERIFIED,
        or SCIENTIFICALLY_VERIFIED for seamless API/UI integration.
        """
        filtered = list(self._nodes.values())

        if node_type:
            filtered = [n for n in filtered if n.node_type == node_type]

        if verification_status:
            target_status = verification_status.upper()
            if target_status == "VERIFIED":
                filtered = [
                    n for n in filtered
                    if n.status in (
                        NodeVerificationStatus.VERIFIED.value,
                        NodeVerificationStatus.INTEGRITY_VERIFIED.value,
                        NodeVerificationStatus.SCIENTIFICALLY_VERIFIED.value,
                    )
                ]
            else:
                filtered = [n for n in filtered if n.status.upper() == target_status]

        if search_query:
            sq = search_query.lower()
            filtered = [
                n for n in filtered
                if sq in n.id.lower() or sq in n.label.lower() or sq in n.label_en.lower()
            ]

        total_count = len(filtered)
        paged = filtered[offset : offset + min(limit, self.MAX_QUERY_LIMIT)]
        return [n.to_dict() for n in paged], total_count

    def to_canonical_json(self) -> Dict[str, Any]:
        """
        Deterministic, key-sorted serialization of the complete evidence graph.
        """
        sorted_nodes = sorted(
            [n.to_dict() for n in self._nodes.values()],
            key=lambda x: x["id"],
        )
        sorted_edges = sorted(
            [e.to_dict() for e in self._edges.values()],
            key=lambda x: x["id"],
        )
        payload = {
            "version": "1.0.0",
            "node_count": len(sorted_nodes),
            "edge_count": len(sorted_edges),
            "nodes": sorted_nodes,
            "edges": sorted_edges,
        }
        raw_json = json.dumps(payload, sort_keys=True, indent=2)
        graph_hash = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()
        payload["graph_sha256"] = graph_hash
        return payload

    @classmethod
    def compute_evidence_fingerprint(cls, catalog_records: List[Any]) -> str:
        """
        Computes cryptographic fingerprint of underlying source evidence.
        Invalidates derived graph statuses when source evidence changes.
        """
        h = hashlib.sha256()
        for rec in catalog_records:
            rec_id = getattr(rec, "id", "")
            src_path = getattr(rec, "source_artifact", "")
            att = getattr(rec, "observation_completeness_attestation", None) or {}
            sig = att.get("signature", "")
            h.update(f"{rec_id}:{src_path}:{sig}".encode("utf-8"))
            if src_path:
                p = Path(src_path)
                if p.exists() and p.is_file():
                    stat = p.stat()
                    h.update(f"{stat.st_mtime_ns}:{stat.st_size}".encode("utf-8"))
                else:
                    h.update(b"MISSING")
        return h.hexdigest()

    @classmethod
    def build_canonical_graph(cls, catalog_records: List[Any]) -> "EvidenceGraphService":
        """
        Builds the ground-truth evidence relationship graph from canonical catalog records,
        attestations, source artifacts, and scientific governance decisions.
        Enforces Sprint 24 cryptographic verifier integration, physical source artifact integrity,
        and separation of REGISTERED, PRESENT, INTEGRITY_VERIFIED, and SCIENTIFICALLY_VERIFIED statuses.
        """
        graph = cls()
        graph._evidence_fingerprint = cls.compute_evidence_fingerprint(catalog_records)

        # 1. Governance Decision Node (Mandatory Canonical Root)
        gov_node = EvidenceGraphNode(
            id="GOV-CBE-070",
            node_type=EvidenceNodeType.GOVERNANCE_DECISION.value,
            label="Yönetişim Kararı: TECHNICAL_NO_GO (CBE-0.7.0 Donduruldu)",
            label_en="Governance Decision: TECHNICAL_NO_GO (CBE-0.7.0 Strictly Frozen)",
            status=NodeVerificationStatus.SCIENTIFICALLY_VERIFIED.value,
            provenance_source="src/coin_behavior_engine/core/config.py",
            properties={
                "canonical_model": "CBE-0.7.0",
                "model_status": "STRICTLY_FROZEN",
                "governance_decision": "TECHNICAL_NO_GO",
                "trading_prohibition": "LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED",
            },
        )
        graph.add_node(gov_node)

        # 2. Add Methodology Nodes
        methodologies = {
            "METH-PARKINSON": EvidenceGraphNode(
                id="METH-PARKINSON",
                node_type=EvidenceNodeType.METHODOLOGY.value,
                label="Parkinson Ekstremum Volatilite Tahmincisi",
                label_en="Parkinson Extreme-Value Volatility Estimator",
                status=NodeVerificationStatus.REGISTERED.value,
                provenance_source="CBE-SPEC-METHOD-01",
            ),
            "METH-WALK-FORWARD": EvidenceGraphNode(
                id="METH-WALK-FORWARD",
                node_type=EvidenceNodeType.METHODOLOGY.value,
                label="Kronolojik İleriye Yürüyüş Rejim Kararlılığı",
                label_en="Chronological Walk-Forward Regime Stability",
                status=NodeVerificationStatus.REGISTERED.value,
                provenance_source="CBE-SPEC-METHOD-02",
            ),
            "METH-DTW": EvidenceGraphNode(
                id="METH-DTW",
                node_type=EvidenceNodeType.METHODOLOGY.value,
                label="Dinamik Zaman Bükmesi (DTW) Örüntü Benzerliği",
                label_en="Dynamic Time Warping Pattern Analogs",
                status=NodeVerificationStatus.REGISTERED.value,
                provenance_source="CBE-SPEC-METHOD-03",
            ),
            "METH-EVENT-STUDY": EvidenceGraphNode(
                id="METH-EVENT-STUDY",
                node_type=EvidenceNodeType.METHODOLOGY.value,
                label="Makro Olay İncelemesi (Event-Study T0)",
                label_en="Macroeconomic Event Study (T0 Window)",
                status=NodeVerificationStatus.REGISTERED.value,
                provenance_source="CBE-SPEC-METHOD-04",
            ),
            "METH-DURABILITY": EvidenceGraphNode(
                id="METH-DURABILITY",
                node_type=EvidenceNodeType.METHODOLOGY.value,
                label="Docker Çift Çekirdek Mountinfo Doğrulaması",
                label_en="Docker Dual-Kernel Mountinfo Storage Verification",
                status=NodeVerificationStatus.REGISTERED.value,
                provenance_source="CBE-SPEC-METHOD-05",
            ),
        }
        for m in methodologies.values():
            graph.add_node(m)

        # 3. Process Catalog Records
        registered_datasets: Set[str] = set()
        registered_artifacts: Set[str] = set()

        for rec in catalog_records:
            rec_id = getattr(rec, "id", "")
            if not rec_id:
                continue

            att = getattr(rec, "observation_completeness_attestation", None)
            src_path = getattr(rec, "source_artifact", "")
            expected_sha = getattr(rec, "source_artifact_sha256", "")
            ds_id = getattr(rec, "dataset_id", "")
            quarantine = getattr(rec, "quarantine_status", "")

            # ------------------------------------------------------------------
            # Verification Step 1: Physical source artifact integrity verification
            # ------------------------------------------------------------------
            art_status = NodeVerificationStatus.UNVERIFIED.value
            art_sha = ""
            art_rejection = None
            if src_path:
                is_valid_art, rej_code, rej_reason, actual_sha, _, _ = (
                    ObservationCompletenessAttestationVerifier.verify_source_artifact_integrity(
                        rec, att or {}
                    )
                )
                if is_valid_art:
                    art_status = NodeVerificationStatus.INTEGRITY_VERIFIED.value
                    art_sha = actual_sha or expected_sha
                else:
                    art_status = NodeVerificationStatus.FAILED.value
                    art_rejection = rej_code
            else:
                art_status = NodeVerificationStatus.INSUFFICIENT_EVIDENCE.value

            # ------------------------------------------------------------------
            # Verification Step 2: Cryptographic completeness attestation
            # ------------------------------------------------------------------
            att_status = NodeVerificationStatus.UNVERIFIED.value
            att_rejection = None
            att_claims = None
            if att and isinstance(att, dict):
                att_check = ObservationCompletenessAttestationVerifier.verify_attestation(
                    rec, att, use_cache=True, enforce_source_file_integrity=True
                )
                if att_check.get("is_valid"):
                    att_status = NodeVerificationStatus.INTEGRITY_VERIFIED.value
                    att_claims = att_check.get("verified_claims")
                else:
                    att_status = NodeVerificationStatus.FAILED.value
                    att_rejection = att_check.get("rejection_code")

            # ------------------------------------------------------------------
            # Verification Step 3: Record Node Status
            # ------------------------------------------------------------------
            if quarantine == "QUARANTINED" or "OCTOBER-2026-INTAKE" in ds_id:
                rec_status = NodeVerificationStatus.BLOCKED.value
            elif (
                art_status == NodeVerificationStatus.FAILED.value
                or att_status == NodeVerificationStatus.FAILED.value
            ):
                rec_status = NodeVerificationStatus.FAILED.value
            elif (
                art_status == NodeVerificationStatus.INTEGRITY_VERIFIED.value
                and att_status == NodeVerificationStatus.INTEGRITY_VERIFIED.value
            ):
                rec_status = NodeVerificationStatus.INTEGRITY_VERIFIED.value
            elif art_status == NodeVerificationStatus.INTEGRITY_VERIFIED.value:
                rec_status = NodeVerificationStatus.PRESENT.value
            else:
                rec_status = NodeVerificationStatus.UNVERIFIED.value

            # Record Node
            rec_node = EvidenceGraphNode(
                id=rec_id,
                node_type=EvidenceNodeType.RESEARCH_RECORD.value,
                label=f"Araştırma Kaydı: {getattr(rec, 'title', rec_id)}",
                label_en=f"Research Record: {getattr(rec, 'title_en', rec_id)}",
                status=rec_status,
                provenance_source=src_path,
                source_artifact_sha256=art_sha or expected_sha or None,
                properties={
                    "specification_id": getattr(rec, "specification_id", ""),
                    "dataset_id": ds_id,
                    "window_cadence": getattr(rec, "window_cadence", ""),
                    "sample_size": getattr(rec, "sample_size", 0),
                    "volatility_ratio": getattr(rec, "volatility_ratio", None),
                    "artifact_status": art_status,
                    "attestation_status": att_status,
                },
            )
            graph.add_node(rec_node)

            # Blocked by Governance if model frozen
            edge_gov = EvidenceGraphEdge(
                id=f"EDGE-GOV-{rec_id}",
                source_id=rec_id,
                target_id="GOV-CBE-070",
                edge_type=EvidenceEdgeType.BLOCKED_BY.value,
                label="Teknik Red (Canlı İşlem Yasak)",
                label_en="Technical Rejection (Live Execution Prohibited)",
                is_verified=True,
                provenance_reference="CBE-0.7.0 Governance Policy",
            )
            graph.add_edge(edge_gov)

            # ------------------------------------------------------------------
            # Dataset Node & Edge
            # ------------------------------------------------------------------
            if ds_id:
                from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator
                prov_res = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
                ds_status = prov_res["graph_status"]

                node_ds_id = f"DS-{ds_id}"
                if node_ds_id not in registered_datasets:
                    registered_datasets.add(node_ds_id)
                    ds_node = EvidenceGraphNode(
                        id=node_ds_id,
                        node_type=EvidenceNodeType.DATASET.value,
                        label=f"Veri Seti: {ds_id}",
                        label_en=f"Dataset: {ds_id}",
                        status=ds_status,
                        provenance_source=prov_res["evidence_reference"],
                        properties={
                            "dataset_id": ds_id,
                            "quarantine_status": quarantine,
                            "provenance_verified": bool(prov_res["is_verified"]),
                            "provenance_mechanism": prov_res["mechanism"],
                            "rejection_code": prov_res.get("rejection_code"),
                        },
                    )
                    graph.add_node(ds_node)
                else:
                    # Upgrade or reflect verified status if another record provides authenticated provenance for this dataset
                    existing_ds = graph.get_node(node_ds_id)
                    if existing_ds and prov_res["is_verified"]:
                        existing_ds.status = NodeVerificationStatus.INTEGRITY_VERIFIED.value
                        existing_ds.provenance_source = prov_res["evidence_reference"]
                        existing_ds.properties["provenance_verified"] = True
                        existing_ds.properties["provenance_mechanism"] = prov_res["mechanism"]
                        existing_ds.properties["rejection_code"] = None

                edge_ds = EvidenceGraphEdge(
                    id=f"EDGE-DS-{rec_id}",
                    source_id=rec_id,
                    target_id=node_ds_id,
                    edge_type=EvidenceEdgeType.USES_DATASET.value,
                    label="Veri Setini Kullanır",
                    label_en="Uses Dataset",
                    is_verified=bool(prov_res["is_verified"]),
                    provenance_reference=prov_res["evidence_reference"],
                )
                graph.add_edge(edge_ds)

            # ------------------------------------------------------------------
            # Source Artifact Node & Edge
            # ------------------------------------------------------------------
            if src_path:
                node_art_id = f"ART-{hashlib.sha256(src_path.encode('utf-8')).hexdigest()[:12]}"
                if node_art_id not in registered_artifacts:
                    registered_artifacts.add(node_art_id)
                    art_node = EvidenceGraphNode(
                        id=node_art_id,
                        node_type=EvidenceNodeType.SOURCE_ARTIFACT.value,
                        label=f"Kaynak Belge: {src_path.split('/')[-1]}",
                        label_en=f"Source Artifact: {src_path.split('/')[-1]}",
                        status=art_status,
                        provenance_source=src_path,
                        source_artifact_sha256=art_sha or expected_sha or None,
                        properties={
                            "path": src_path,
                            "sha256": art_sha or expected_sha,
                            "rejection_code": art_rejection,
                        },
                    )
                    graph.add_node(art_node)

                edge_art = EvidenceGraphEdge(
                    id=f"EDGE-ART-{rec_id}",
                    source_id=rec_id,
                    target_id=node_art_id,
                    edge_type=EvidenceEdgeType.DERIVED_FROM.value,
                    label="Kaynak Belgeden Türetilmiştir",
                    label_en="Derived From Source Artifact",
                    is_verified=(art_status == NodeVerificationStatus.INTEGRITY_VERIFIED.value),
                    provenance_reference=src_path,
                )
                graph.add_edge(edge_art)

            # ------------------------------------------------------------------
            # Attestation Node & Edge
            # ------------------------------------------------------------------
            if att and isinstance(att, dict):
                node_att_id = f"ATT-{rec_id}"
                att_node = EvidenceGraphNode(
                    id=node_att_id,
                    node_type=EvidenceNodeType.ATTESTATION.value,
                    label=f"Kriptografik Tasdik ({att.get('schema_version', 'CBE-ATTESTATION-2.0.0')})",
                    label_en=f"Cryptographic Attestation ({att.get('schema_version', 'CBE-ATTESTATION-2.0.0')})",
                    status=att_status,
                    provenance_source=att.get("issuer", "CBE_AUTHORITY"),
                    properties={
                        "issuer": att.get("issuer"),
                        "key_id": att.get("key_id"),
                        "observation_count": att.get("observation_count"),
                        "schema_version": att.get("schema_version"),
                        "rejection_code": att_rejection,
                    },
                )
                graph.add_node(att_node)

                edge_att = EvidenceGraphEdge(
                    id=f"EDGE-ATT-{rec_id}",
                    source_id=rec_id,
                    target_id=node_att_id,
                    edge_type=EvidenceEdgeType.VERIFIED_BY.value,
                    label="Kriptografik Olarak Tasdiklenmiştir",
                    label_en="Cryptographically Verified By",
                    is_verified=(att_status == NodeVerificationStatus.INTEGRITY_VERIFIED.value),
                    provenance_reference=att.get("signature", ""),
                )
                graph.add_edge(edge_att)

            # ------------------------------------------------------------------
            # Methodology Edge
            # ------------------------------------------------------------------
            cat = getattr(rec, "category", "")
            matched_meth = None
            if "Volatilite" in cat or "Volatility" in cat:
                matched_meth = "METH-PARKINSON"
            elif "Rejim" in cat or "Regime" in cat:
                matched_meth = "METH-WALK-FORWARD"
            elif "Örüntü" in cat or "Pattern" in cat or "Analog" in cat:
                matched_meth = "METH-DTW"
            elif "Makro" in cat or "Macro" in cat:
                matched_meth = "METH-EVENT-STUDY"
            elif "Depolama" in cat or "Durability" in cat or "Sistem" in cat:
                matched_meth = "METH-DURABILITY"

            if matched_meth and matched_meth in methodologies:
                edge_meth = EvidenceGraphEdge(
                    id=f"EDGE-METH-{rec_id}",
                    source_id=rec_id,
                    target_id=matched_meth,
                    edge_type=EvidenceEdgeType.USES_METHODOLOGY.value,
                    label="Metodolojiyi Uygular",
                    label_en="Uses Methodology",
                    is_verified=True,
                    provenance_reference=methodologies[matched_meth].provenance_source,
                )
                graph.add_edge(edge_meth)

            # ------------------------------------------------------------------
            # Hypothesis & Claim Nodes
            # ------------------------------------------------------------------
            hyp_id = f"HYP-{rec_id}"
            hyp_node = EvidenceGraphNode(
                id=hyp_id,
                node_type=EvidenceNodeType.RESEARCH_HYPOTHESIS.value,
                label=f"Hipotez: {getattr(rec, 'title', rec_id)}",
                label_en=f"Hypothesis: {getattr(rec, 'title_en', rec_id)}",
                status=NodeVerificationStatus.UNVERIFIED.value,
                provenance_source=getattr(rec, "specification_id", ""),
            )
            graph.add_node(hyp_node)

            edge_hyp = EvidenceGraphEdge(
                id=f"EDGE-HYP-{rec_id}",
                source_id=rec_id,
                target_id=hyp_id,
                edge_type=EvidenceEdgeType.TESTS_HYPOTHESIS.value,
                label="Hipotezi Sınar",
                label_en="Tests Hypothesis",
                is_verified=True,
            )
            graph.add_edge(edge_hyp)

            # ------------------------------------------------------------------
            # Statistical Result Node & Claim Node
            # ------------------------------------------------------------------
            stat_id = f"STAT-{rec_id}"
            sample_size = getattr(rec, "sample_size", 0) or 0
            p_val = getattr(rec, "raw_p_value", None)
            vol_ratio = getattr(rec, "volatility_ratio", None)

            # Verification contract for statistical results:
            # Requires sample_size >= 100, verified underlying artifact, and non-dummy statistical metrics
            has_valid_stats = (
                sample_size >= 100
                and art_status == NodeVerificationStatus.INTEGRITY_VERIFIED.value
                and (
                    (p_val is not None and 0.0 <= p_val < 1.0)
                    or (vol_ratio is not None and vol_ratio > 0.0)
                )
            )
            stat_status = (
                NodeVerificationStatus.INTEGRITY_VERIFIED.value
                if has_valid_stats
                else NodeVerificationStatus.UNVERIFIED.value
            )

            stat_node = EvidenceGraphNode(
                id=stat_id,
                node_type=EvidenceNodeType.STATISTICAL_RESULT.value,
                label=f"İstatistiksel Gözlem (N={sample_size})",
                label_en=f"Statistical Observation (N={sample_size})",
                status=stat_status,
                properties={
                    "sample_size": sample_size,
                    "volatility_ratio": vol_ratio,
                    "p_value": p_val,
                },
            )
            graph.add_node(stat_node)

            edge_stat = EvidenceGraphEdge(
                id=f"EDGE-STAT-{rec_id}",
                source_id=rec_id,
                target_id=stat_id,
                edge_type=EvidenceEdgeType.DERIVED_FROM.value,
                label="Gözlem Sonucu",
                label_en="Observation Result",
                is_verified=has_valid_stats,
            )
            graph.add_edge(edge_stat)

            claim_id = f"CLAIM-{rec_id}"
            claim_node = EvidenceGraphNode(
                id=claim_id,
                node_type=EvidenceNodeType.SCIENTIFIC_CLAIM.value,
                label=f"Bilimsel İddia: {getattr(rec, 'title', rec_id)}",
                label_en=f"Scientific Claim: {getattr(rec, 'title_en', rec_id)}",
                status=NodeVerificationStatus.UNVERIFIED.value,  # Stays unverified until confirmatory replication
                properties={"key_findings_tr": getattr(rec, "key_findings_tr", "")},
            )
            graph.add_node(claim_node)

            edge_claim = EvidenceGraphEdge(
                id=f"EDGE-CLAIM-{rec_id}",
                source_id=stat_id,
                target_id=claim_id,
                edge_type=EvidenceEdgeType.SUPPORTED_BY.value,
                label="İddiayı Destekler (Ön Bulgu)",
                label_en="Supports Claim (Preliminary Finding)",
                is_verified=False,  # Unverified until independent replication
            )
            graph.add_edge(edge_claim)

        return graph


# Global singleton instance
evidence_graph_service = EvidenceGraphService()

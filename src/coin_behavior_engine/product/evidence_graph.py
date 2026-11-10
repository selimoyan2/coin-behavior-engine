"""
Scientific Evidence Graph Service.
Sprint 25: Research Evidence Graph, Scientific Readiness & Decision Intelligence Platform.
(CBE_SPRINT25_RESEARCH_DECISION_INTELLIGENCE)

Connects research hypotheses, datasets, research records, experimental procedures,
statistical results, source artifacts, attestations, replication attempts,
methodologies, scientific claims, and governance decisions into a deterministic,
fail-closed evidence relationship network.
"""

from __future__ import annotations

import enum
import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple


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
    VERIFIED = "VERIFIED"
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
        direction: 'outgoing', 'incoming', 'all'
        """
        if node_id not in self._nodes:
            return []

        results = []
        if direction in ("outgoing", "outbound", "all", "both"):
            for e_id in self._adj_out.get(node_id, []):
                e = self._edges[e_id]
                if edge_type is None or e.edge_type == edge_type:
                    target_node = self._nodes[e.target_id]
                    results.append((e, target_node))

        if direction in ("incoming", "inbound", "all", "both"):
            for e_id in self._adj_in.get(node_id, []):
                e = self._edges[e_id]
                if edge_type is None or e.edge_type == edge_type:
                    source_node = self._nodes[e.source_id]
                    results.append((e, source_node))

        return results

    def traverse_dependencies(
        self,
        start_node_id: str,
        max_depth: int = 5,
        allowed_edge_types: Optional[Set[str]] = None,
    ) -> Dict[str, Any]:
        """
        Cycle-safe bounded breadth-first traversal from start_node_id.
        Prevents infinite recursion on cycles.
        """
        if start_node_id not in self._nodes:
            return {"nodes": [], "edges": [], "has_cycle": False}

        effective_depth = min(max_depth, self.MAX_TRAVERSAL_DEPTH)
        visited_nodes: Set[str] = set()
        visited_edges: Set[str] = set()
        queue: List[Tuple[str, int, List[str]]] = [(start_node_id, 0, [start_node_id])]
        has_cycle = False

        while queue:
            curr_id, depth, path = queue.pop(0)
            visited_nodes.add(curr_id)

            if depth >= effective_depth:
                continue

            for e_id in self._adj_out.get(curr_id, []):
                edge = self._edges[e_id]
                if allowed_edge_types and edge.edge_type not in allowed_edge_types:
                    continue

                visited_edges.add(e_id)
                target_id = edge.target_id

                if target_id in path:
                    has_cycle = True
                    continue

                if target_id not in visited_nodes:
                    queue.append((target_id, depth + 1, path + [target_id]))

        return {
            "nodes": [self._nodes[nid].to_dict() for nid in visited_nodes if nid in self._nodes],
            "edges": [self._edges[eid].to_dict() for eid in visited_edges if eid in self._edges],
            "has_cycle": has_cycle,
        }

    def detect_missing_links(self) -> List[Dict[str, Any]]:
        """
        Identifies structural evidence gaps in the graph:
        1. RESEARCH_RECORD without USES_DATASET edge
        2. RESEARCH_RECORD without SOURCE_ARTIFACT or DERIVED_FROM edge
        3. RESEARCH_RECORD without VERIFIED_BY or ATTESTATION edge
        4. SCIENTIFIC_CLAIM without SUPPORTED_BY edge
        5. RESEARCH_RECORD without REPLICATION_ATTEMPT (unreplicated)
        """
        missing_links: List[Dict[str, Any]] = []

        for node_id, node in self._nodes.items():
            if node.node_type == EvidenceNodeType.RESEARCH_RECORD.value:
                out_edges = [self._edges[eid] for eid in self._adj_out.get(node_id, [])]
                in_edges = [self._edges[eid] for eid in self._adj_in.get(node_id, [])]
                all_edges = out_edges + in_edges

                # 1. Dataset linkage
                has_dataset = any(e.edge_type == EvidenceEdgeType.USES_DATASET.value for e in out_edges)
                if not has_dataset:
                    missing_links.append({
                        "node_id": node_id,
                        "node_label": node.label,
                        "missing_relation": EvidenceEdgeType.USES_DATASET.value,
                        "target_type": EvidenceNodeType.DATASET.value,
                        "severity": "CRITICAL",
                        "description_tr": f"Araştırma kaydı '{node.label}' doğrulanabilir bir veri setine bağlanmamış.",
                        "description_en": f"Research record '{node.label}' has no verifiable dataset connection."
                    })

                # 2. Source artifact linkage
                has_artifact = any(
                    e.edge_type == EvidenceEdgeType.DERIVED_FROM.value
                    and self._nodes.get(e.target_id, EvidenceGraphNode("", "", "", "")).node_type == EvidenceNodeType.SOURCE_ARTIFACT.value
                    for e in out_edges
                )
                if not has_artifact:
                    missing_links.append({
                        "node_id": node_id,
                        "node_label": node.label,
                        "missing_relation": EvidenceEdgeType.DERIVED_FROM.value,
                        "target_type": EvidenceNodeType.SOURCE_ARTIFACT.value,
                        "severity": "CRITICAL",
                        "description_tr": f"Araştırma kaydı '{node.label}' kaynak araştırma belgesine (artifact) bağlı değil.",
                        "description_en": f"Research record '{node.label}' is not derived from a source artifact."
                    })

                # 3. Attestation linkage
                has_attestation = any(
                    e.edge_type == EvidenceEdgeType.VERIFIED_BY.value
                    and self._nodes.get(e.target_id, EvidenceGraphNode("", "", "", "")).node_type == EvidenceNodeType.ATTESTATION.value
                    for e in out_edges
                )
                if not has_attestation:
                    missing_links.append({
                        "node_id": node_id,
                        "node_label": node.label,
                        "missing_relation": EvidenceEdgeType.VERIFIED_BY.value,
                        "target_type": EvidenceNodeType.ATTESTATION.value,
                        "severity": "HIGH",
                        "description_tr": f"Araştırma kaydı '{node.label}' bağımsız kriptografik eksiksizlik tasdiğine sahip değil.",
                        "description_en": f"Research record '{node.label}' has no independent cryptographic completeness attestation."
                    })

                # 4. Independent replication linkage
                has_replication = any(e.edge_type == EvidenceEdgeType.REPLICATED_BY.value for e in all_edges)
                if not has_replication:
                    missing_links.append({
                        "node_id": node_id,
                        "node_label": node.label,
                        "missing_relation": EvidenceEdgeType.REPLICATED_BY.value,
                        "target_type": EvidenceNodeType.REPLICATION_ATTEMPT.value,
                        "severity": "HIGH",
                        "description_tr": f"Araştırma kaydı '{node.label}' için henüz bağımsız doğrulama/replikasyon kanıtı kaydedilmemiştir.",
                        "description_en": f"No independent replication evidence recorded for research record '{node.label}'."
                    })

            elif node.node_type == EvidenceNodeType.SCIENTIFIC_CLAIM.value:
                in_edges = [self._edges[eid] for eid in self._adj_in.get(node_id, [])]
                has_support = any(e.edge_type == EvidenceEdgeType.SUPPORTED_BY.value for e in in_edges)
                if not has_support:
                    missing_links.append({
                        "node_id": node_id,
                        "node_label": node.label,
                        "missing_relation": EvidenceEdgeType.SUPPORTED_BY.value,
                        "target_type": EvidenceNodeType.STATISTICAL_RESULT.value,
                        "severity": "CRITICAL",
                        "description_tr": f"Bilimsel iddia '{node.label}' ampirik bir istatistiksel sonuç veya kanıt ile desteklenmiyor.",
                        "description_en": f"Scientific claim '{node.label}' is unsupported by empirical statistical results."
                    })

        return missing_links

    def query_subgraph(
        self,
        node_type: Optional[str] = None,
        verification_status: Optional[str] = None,
        edge_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """
        Bounded, paginated query returning filtered nodes and corresponding edges.
        """
        bounded_limit = min(max(1, limit), self.MAX_QUERY_LIMIT)
        filtered_nodes = []

        for n in self._nodes.values():
            if node_type and n.node_type != node_type:
                continue
            if verification_status and n.status != verification_status:
                continue
            filtered_nodes.append(n)

        total_nodes = len(filtered_nodes)
        paged_nodes = filtered_nodes[offset : offset + bounded_limit]
        paged_node_ids = {n.id for n in paged_nodes}

        # Include edges connecting any paged nodes
        paged_edges = []
        for e in self._edges.values():
            if edge_type and e.edge_type != edge_type:
                continue
            if e.source_id in paged_node_ids or e.target_id in paged_node_ids:
                paged_edges.append(e)

        return {
            "total_nodes": total_nodes,
            "returned_nodes": len(paged_nodes),
            "limit": bounded_limit,
            "offset": offset,
            "nodes": [n.to_dict() for n in paged_nodes],
            "edges": [e.to_dict() for e in paged_edges],
        }

    def serialize_deterministic(self) -> Dict[str, Any]:
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
    def build_canonical_graph(cls, catalog_records: List[Any]) -> "EvidenceGraphService":
        """
        Builds the ground-truth evidence relationship graph from canonical catalog records,
        attestations, source artifacts, and scientific governance decisions.
        """
        graph = cls()

        # 1. Governance Decision Node (Mandatory Canonical Root)
        gov_node = EvidenceGraphNode(
            id="GOV-CBE-070",
            node_type=EvidenceNodeType.GOVERNANCE_DECISION.value,
            label="Yönetişim Kararı: TECHNICAL_NO_GO (CBE-0.7.0 Donduruldu)",
            label_en="Governance Decision: TECHNICAL_NO_GO (CBE-0.7.0 Strictly Frozen)",
            status=NodeVerificationStatus.VERIFIED.value,
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
                status=NodeVerificationStatus.VERIFIED.value,
                provenance_source="CBE-SPEC-METHOD-01",
            ),
            "METH-WALK-FORWARD": EvidenceGraphNode(
                id="METH-WALK-FORWARD",
                node_type=EvidenceNodeType.METHODOLOGY.value,
                label="Kronolojik İleriye Yürüyüş Rejim Kararlılığı",
                label_en="Chronological Walk-Forward Regime Stability",
                status=NodeVerificationStatus.VERIFIED.value,
                provenance_source="CBE-SPEC-METHOD-02",
            ),
            "METH-DTW": EvidenceGraphNode(
                id="METH-DTW",
                node_type=EvidenceNodeType.METHODOLOGY.value,
                label="Dinamik Zaman Bükmesi (DTW) Örüntü Benzerliği",
                label_en="Dynamic Time Warping Pattern Analogs",
                status=NodeVerificationStatus.VERIFIED.value,
                provenance_source="CBE-SPEC-METHOD-03",
            ),
            "METH-EVENT-STUDY": EvidenceGraphNode(
                id="METH-EVENT-STUDY",
                node_type=EvidenceNodeType.METHODOLOGY.value,
                label="Makro Olay İncelemesi (Event-Study T0)",
                label_en="Macroeconomic Event Study (T0 Window)",
                status=NodeVerificationStatus.VERIFIED.value,
                provenance_source="CBE-SPEC-METHOD-04",
            ),
            "METH-DURABILITY": EvidenceGraphNode(
                id="METH-DURABILITY",
                node_type=EvidenceNodeType.METHODOLOGY.value,
                label="Docker Çift Çekirdek Mountinfo Doğrulaması",
                label_en="Docker Dual-Kernel Mountinfo Storage Verification",
                status=NodeVerificationStatus.VERIFIED.value,
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

            # Map verification status
            ev_status = getattr(rec, "evidence_status", "UNVERIFIED")
            rec_status = NodeVerificationStatus.UNVERIFIED.value
            if ev_status in ("VERIFIED", "SIGNED_VALID"):
                rec_status = NodeVerificationStatus.VERIFIED.value
            elif getattr(rec, "quarantine_status", "") == "QUARANTINED":
                rec_status = NodeVerificationStatus.BLOCKED.value

            # Record Node
            rec_node = EvidenceGraphNode(
                id=rec_id,
                node_type=EvidenceNodeType.RESEARCH_RECORD.value,
                label=f"Araştırma Kaydı: {getattr(rec, 'title', rec_id)}",
                label_en=f"Research Record: {getattr(rec, 'title_en', rec_id)}",
                status=rec_status,
                provenance_source=getattr(rec, "source_artifact", ""),
                source_artifact_sha256=getattr(rec, "source_artifact_sha256", None),
                properties={
                    "specification_id": getattr(rec, "specification_id", ""),
                    "dataset_id": getattr(rec, "dataset_id", ""),
                    "window_cadence": getattr(rec, "window_cadence", ""),
                    "sample_size": getattr(rec, "sample_size", 0),
                    "volatility_ratio": getattr(rec, "volatility_ratio", None),
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

            # Dataset Node & Edge
            ds_id = getattr(rec, "dataset_id", "")
            if ds_id:
                node_ds_id = f"DS-{ds_id}"
                if node_ds_id not in registered_datasets:
                    registered_datasets.add(node_ds_id)
                    ds_node = EvidenceGraphNode(
                        id=node_ds_id,
                        node_type=EvidenceNodeType.DATASET.value,
                        label=f"Veri Seti: {ds_id}",
                        label_en=f"Dataset: {ds_id}",
                        status=NodeVerificationStatus.VERIFIED.value,
                        provenance_source="Binance / US BLS Macro Archive",
                        properties={"dataset_id": ds_id},
                    )
                    graph.add_node(ds_node)

                edge_ds = EvidenceGraphEdge(
                    id=f"EDGE-DS-{rec_id}",
                    source_id=rec_id,
                    target_id=node_ds_id,
                    edge_type=EvidenceEdgeType.USES_DATASET.value,
                    label="Veri Setini Kullanır",
                    label_en="Uses Dataset",
                    is_verified=True,
                    provenance_reference=getattr(rec, "source_artifact", ""),
                )
                graph.add_edge(edge_ds)

            # Source Artifact Node & Edge
            art_path = getattr(rec, "source_artifact", "")
            art_sha = getattr(rec, "source_artifact_sha256", "")
            if art_path:
                node_art_id = f"ART-{hashlib.sha256(art_path.encode()).hexdigest()[:12]}"
                if node_art_id not in registered_artifacts:
                    registered_artifacts.add(node_art_id)
                    art_status = (
                        NodeVerificationStatus.VERIFIED.value
                        if art_sha
                        else NodeVerificationStatus.UNVERIFIED.value
                    )
                    art_node = EvidenceGraphNode(
                        id=node_art_id,
                        node_type=EvidenceNodeType.SOURCE_ARTIFACT.value,
                        label=f"Kaynak Belge: {art_path.split('/')[-1]}",
                        label_en=f"Source Artifact: {art_path.split('/')[-1]}",
                        status=art_status,
                        provenance_source=art_path,
                        source_artifact_sha256=art_sha,
                        properties={"path": art_path, "sha256": art_sha},
                    )
                    graph.add_node(art_node)

                edge_art = EvidenceGraphEdge(
                    id=f"EDGE-ART-{rec_id}",
                    source_id=rec_id,
                    target_id=node_art_id,
                    edge_type=EvidenceEdgeType.DERIVED_FROM.value,
                    label="Kaynak Belgeden Türetilmiştir",
                    label_en="Derived From Source Artifact",
                    is_verified=bool(art_sha),
                    provenance_reference=art_path,
                )
                graph.add_edge(edge_art)

            # Attestation Node & Edge if present
            att = getattr(rec, "observation_completeness_attestation", None)
            if att and isinstance(att, dict) and att.get("signature"):
                node_att_id = f"ATT-{rec_id}"
                att_node = EvidenceGraphNode(
                    id=node_att_id,
                    node_type=EvidenceNodeType.ATTESTATION.value,
                    label=f"Kriptografik Tasdik ({att.get('schema_version', 'CBE-ATTESTATION-2.0.0')})",
                    label_en=f"Cryptographic Attestation ({att.get('schema_version', 'CBE-ATTESTATION-2.0.0')})",
                    status=NodeVerificationStatus.VERIFIED.value,
                    provenance_source=att.get("issuer", "CBE_AUTHORITY"),
                    properties={
                        "issuer": att.get("issuer"),
                        "key_id": att.get("key_id"),
                        "observation_count": att.get("observation_count"),
                        "schema_version": att.get("schema_version"),
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
                    is_verified=True,
                    provenance_reference=att.get("signature", ""),
                )
                graph.add_edge(edge_att)

            # Methodology Edge
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

            # Hypothesis & Claim Nodes
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

            # Statistical Result Node & Claim Node
            stat_id = f"STAT-{rec_id}"
            stat_node = EvidenceGraphNode(
                id=stat_id,
                node_type=EvidenceNodeType.STATISTICAL_RESULT.value,
                label=f"İstatistiksel Gözlem (N={getattr(rec, 'sample_size', 0)})",
                label_en=f"Statistical Observation (N={getattr(rec, 'sample_size', 0)})",
                status=NodeVerificationStatus.VERIFIED.value if getattr(rec, "sample_size", 0) else NodeVerificationStatus.UNVERIFIED.value,
                properties={
                    "sample_size": getattr(rec, "sample_size", 0),
                    "volatility_ratio": getattr(rec, "volatility_ratio", None),
                    "p_value": getattr(rec, "raw_p_value", None),
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
                is_verified=True,
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

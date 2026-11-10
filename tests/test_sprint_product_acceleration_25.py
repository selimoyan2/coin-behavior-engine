"""
Sprint 25 Test Suite: Research Evidence Graph, Scientific Readiness & Decision Intelligence Platform
Sprint ID: CBE_SPRINT25_RESEARCH_DECISION_INTELLIGENCE
Repository: selimoyan2/coin-behavior-engine
Branch: main

Covers:
1. Evidence Graph Integrity (11 node types, 10 edge types, cycle-safety, missing link detection)
2. Scientific Readiness Scorecard (10 dimensions, fail-closed critical gates, explanation strings)
3. Evidence Gap Analyzer (14 gap categories, severity grading, actionable remedies)
4. Scientific Reproducibility Lab (allowlist procedures, environment capture, rerun hash, non-replication invariant)
5. Research Priority Engine (gap severity ranking, feasibility, non-trading isolation)
6. Research Decision Reports (13 canonical sections, HTML formatting, governance statement)
7. Workspace Engine & Dashboard REST API Endpoints
8. Canonical Scientific & Governance Invariants (CBE-0.7.0, TECHNICAL_NO_GO, Zero Trading)
"""

import json
import pytest
from datetime import datetime, timezone

from coin_behavior_engine.product.evidence_graph import (
    EvidenceGraphService,
    EvidenceGraphNode,
    EvidenceGraphEdge,
    EvidenceNodeType,
    EvidenceEdgeType,
    NodeVerificationStatus,
)
from coin_behavior_engine.product.scientific_readiness import (
    ScientificReadinessEvaluator,
    ScientificReadinessScorecard,
    DimensionEvaluation,
    DimensionStatus,
    OverallReadinessVerdict,
)
from coin_behavior_engine.product.evidence_gap_analyzer import (
    EvidenceGapAnalyzer,
    EvidenceGap,
    GapCategory,
    GapSeverity,
)
from coin_behavior_engine.product.reproducibility_lab import (
    ReproducibilityLabEngine,
    ReproductionProvenance,
    ReproductionStatus,
)
from coin_behavior_engine.product.research_priority_engine import (
    ResearchPriorityEngine,
    PrioritizedResearchTask,
    PriorityTier,
)
from coin_behavior_engine.product.research_decision_reports import (
    DecisionReportBuilder,
    ResearchDecisionReport,
)
from coin_behavior_engine.product.research_intelligence_workspace import (
    ResearchWorkspaceV2Engine,
    CANONICAL_MODEL,
    CANONICAL_MODEL_STATUS,
    GOVERNANCE_DECISION,
    CBE_TRADING_DISABLED,
    LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService


# ==============================================================================
# 1. EVIDENCE GRAPH INTEGRITY TESTS
# ==============================================================================

class TestEvidenceGraph:
    """Tests for Module 25.1: Scientific Evidence Graph."""

    def test_canonical_node_and_edge_types(self):
        """Verify all 11 node types and 10 edge types are defined and distinct."""
        assert len(EvidenceNodeType) == 11
        assert len(EvidenceEdgeType) == 10

        assert EvidenceNodeType.RESEARCH_RECORD.value == "RESEARCH_RECORD"
        assert EvidenceNodeType.DATASET.value == "DATASET"
        assert EvidenceNodeType.SOURCE_ARTIFACT.value == "SOURCE_ARTIFACT"
        assert EvidenceNodeType.ATTESTATION.value == "ATTESTATION"
        assert EvidenceNodeType.METHODOLOGY.value == "METHODOLOGY"
        assert EvidenceNodeType.GOVERNANCE_DECISION.value == "GOVERNANCE_DECISION"

        assert EvidenceEdgeType.USES_DATASET.value == "USES_DATASET"
        assert EvidenceEdgeType.DERIVED_FROM.value == "DERIVED_FROM"
        assert EvidenceEdgeType.SUPPORTED_BY.value == "SUPPORTED_BY"
        assert EvidenceEdgeType.BLOCKED_BY.value == "BLOCKED_BY"

    def test_graph_service_build_canonical_graph(self):
        """Verify canonical graph builds successfully from catalog with rich topology."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        graph_svc = EvidenceGraphService.build_canonical_graph(catalog)

        assert len(graph_svc.nodes) > 30
        assert len(graph_svc.edges) > 30

        # Verify key root nodes exist
        assert graph_svc.get_node("GOV-CBE-070") is not None
        assert graph_svc.get_node("DS-BTCUSDT-SPOT-1H-2022-2026") is not None

        # Verify research record node exists
        rec_node = graph_svc.get_node("RES-REGIME-01")
        assert rec_node is not None
        assert rec_node.node_type == EvidenceNodeType.RESEARCH_RECORD.value

    def test_cycle_safety_and_bounded_traversal(self):
        """Verify cycle detection and bounded traversal prevent infinite recursion."""
        graph_svc = EvidenceGraphService()
        graph_svc.add_node(EvidenceGraphNode("N1", EvidenceNodeType.RESEARCH_RECORD.value, "Node 1", "Node 1"))
        graph_svc.add_node(EvidenceGraphNode("N2", EvidenceNodeType.DATASET.value, "Node 2", "Node 2"))
        graph_svc.add_node(EvidenceGraphNode("N3", EvidenceNodeType.METHODOLOGY.value, "Node 3", "Node 3"))

        # Create cycle N1 -> N2 -> N3 -> N1
        graph_svc.add_edge(EvidenceGraphEdge("E1", "N1", "N2", EvidenceEdgeType.USES_DATASET.value, "uses", "uses"))
        graph_svc.add_edge(EvidenceGraphEdge("E2", "N2", "N3", EvidenceEdgeType.USES_METHODOLOGY.value, "method", "method"))
        graph_svc.add_edge(EvidenceGraphEdge("E3", "N3", "N1", EvidenceEdgeType.SUPPORTED_BY.value, "supports", "supports"))

        # Traversal should detect cycles and terminate cleanly without infinite loop
        visited = graph_svc.traverse_dependencies("N1", max_depth=10)
        visited_ids = {n["id"] for n in visited["nodes"]}
        assert "N1" in visited_ids and "N2" in visited_ids and "N3" in visited_ids
        assert visited.get("has_cycle") is True

    def test_neighbor_queries(self):
        """Verify outbound, inbound and bidirectional neighbor queries."""
        graph_svc = EvidenceGraphService()
        graph_svc.add_node(EvidenceGraphNode("A", EvidenceNodeType.RESEARCH_RECORD.value, "Node A", "Node A"))
        graph_svc.add_node(EvidenceGraphNode("B", EvidenceNodeType.DATASET.value, "Node B", "Node B"))
        graph_svc.add_node(EvidenceGraphNode("C", EvidenceNodeType.METHODOLOGY.value, "Node C", "Node C"))

        graph_svc.add_edge(EvidenceGraphEdge("E1", "A", "B", EvidenceEdgeType.USES_DATASET.value, "uses", "uses"))
        graph_svc.add_edge(EvidenceGraphEdge("E2", "C", "A", EvidenceEdgeType.SUPPORTED_BY.value, "supports", "supports"))

        out_neighbors = graph_svc.get_neighbors("A", direction="outbound")
        assert len(out_neighbors) == 1
        assert out_neighbors[0][1].id == "B"

        in_neighbors = graph_svc.get_neighbors("A", direction="inbound")
        assert len(in_neighbors) == 1
        assert in_neighbors[0][1].id == "C"

        both = graph_svc.get_neighbors("A", direction="both")
        assert len(both) == 2

    def test_missing_link_detection(self):
        """Verify missing evidence links are detected for unverified or blocked components."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        graph_svc = EvidenceGraphService.build_canonical_graph(catalog)
        missing = graph_svc.detect_missing_links()

        assert isinstance(missing, list)
        assert len(missing) > 0

        # Quarantined / blocked items should trigger missing links or warnings
        severities = {m["severity"] for m in missing}
        assert "CRITICAL" in severities or "HIGH" in severities or "MEDIUM" in severities


# ==============================================================================
# 2. SCIENTIFIC READINESS SCORECARD TESTS
# ==============================================================================

class TestScientificReadiness:
    """Tests for Module 25.2: Scientific Readiness Scorecard."""

    def test_canonical_dimensions_count(self):
        """Verify all 10 canonical dimensions are evaluated on scorecards."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        evaluator = ScientificReadinessEvaluator()
        scorecard = evaluator.evaluate_record(catalog[0])

        assert isinstance(scorecard, ScientificReadinessScorecard)
        assert len(scorecard.dimensions) == 10
        dim_keys = {d.dimension_key for d in scorecard.dimensions}
        assert "DATASET_PROVENANCE" in dim_keys
        assert "SOURCE_ARTIFACT_INTEGRITY" in dim_keys
        assert "OBSERVATION_COMPLETENESS" in dim_keys
        assert "SAMPLE_SUFFICIENCY" in dim_keys
        assert "INDEPENDENT_REPLICATION" in dim_keys

    def test_evaluate_record_acceptable(self):
        """Verify eligible record evaluation produces complete scorecard with explanations."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        evaluator = ScientificReadinessEvaluator()
        scorecard = evaluator.evaluate_record(catalog[0])

        assert scorecard.record_id == catalog[0].id
        assert len(scorecard.dimensions) == 10
        assert 0.0 <= scorecard.heuristic_readiness_index <= 100.0
        assert scorecard.overall_verdict in [v.value for v in OverallReadinessVerdict]

        for d in scorecard.dimensions:
            assert len(d.explanation_tr) > 5

    def test_fail_closed_critical_gate(self):
        """Verify failure of critical gate produces appropriate verdict."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        evaluator = ScientificReadinessEvaluator()
        ineligible = [r for r in catalog if r.scientific_eligibility != "ELIGIBLE"]
        if ineligible:
            scorecard = evaluator.evaluate_record(ineligible[0])
            assert scorecard.overall_verdict != OverallReadinessVerdict.READY_FOR_CONFIRMATORY_REVIEW.value
            assert len(scorecard.failed_dimensions) > 0 or len(scorecard.unverified_dimensions) > 0


# ==============================================================================
# 3. EVIDENCE GAP ANALYZER TESTS
# ==============================================================================

class TestEvidenceGapAnalyzer:
    """Tests for Module 25.3: Evidence Gap Analyzer."""

    def test_all_14_gap_categories_present(self):
        """Verify all 14 canonical gap categories are defined."""
        assert len(GapCategory) == 14
        assert GapCategory.MISSING_DATASET_PROVENANCE.value == "MISSING_DATASET_PROVENANCE"
        assert GapCategory.MISSING_SOURCE_ARTIFACT.value == "MISSING_SOURCE_ARTIFACT"
        assert GapCategory.INCOMPLETE_OBSERVATION_HISTORY.value == "INCOMPLETE_OBSERVATION_HISTORY"
        assert GapCategory.MISSING_INDEPENDENT_REPLICATION.value == "MISSING_INDEPENDENT_REPLICATION"

    def test_analyze_record_identifies_defects(self):
        """Verify gap scanner detects specific gaps with severity, remedy and resolution criteria."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        analyzer = EvidenceGapAnalyzer()
        gaps = analyzer.analyze_record(catalog[0])

        assert len(gaps) > 0
        for g in gaps:
            assert isinstance(g, EvidenceGap)
            assert g.severity in [s.value for s in GapSeverity]
            assert len(g.suggested_research_action_tr) > 5
            assert len(g.resolution_criteria_tr) > 5

    def test_analyze_catalog(self):
        """Verify catalog gap scanning returns grounded gaps across catalog."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        analyzer = EvidenceGapAnalyzer()
        catalog_analysis = analyzer.analyze_catalog(catalog)

        assert catalog_analysis["total_gaps"] > 0
        severities = {g["severity"] for g in catalog_analysis["gaps"]}
        assert GapSeverity.CRITICAL.value in severities or GapSeverity.HIGH.value in severities


# ==============================================================================
# 4. SCIENTIFIC REPRODUCIBILITY LAB TESTS
# ==============================================================================

class TestReproducibilityLab:
    """Tests for Module 25.4: Scientific Reproducibility Lab."""

    def test_allowlist_procedures(self):
        """Verify allowlisted procedures exist and are restricted."""
        engine = ReproducibilityLabEngine()
        procedures = engine.get_supported_procedures()
        assert len(procedures) >= 5

        proc_ids = set(procedures.keys())
        assert "PROC_PARKINSON_VOLATILITY" in proc_ids
        assert "PROC_FUNDING_RATE_SUMMARY" in proc_ids
        assert "PROC_REGIME_STABILITY_EVAL" in proc_ids
        assert "PROC_STORAGE_VERIFICATION" in proc_ids

    def test_reject_unauthorized_procedure(self):
        """Verify non-allowlisted procedure fails closed with blocked status."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        engine = ReproducibilityLabEngine()
        prov = engine.execute_reproduction(catalog[0], "PROC_UNAUTHORIZED_HACK")
        assert prov.status == ReproductionStatus.REPRODUCTION_BLOCKED.value
        assert "onaylı" in prov.error_message_tr.lower() or "approved" in prov.error_message_en.lower()

    def test_execute_procedure_matched_determinism(self):
        """Verify offline procedure execution captures environment and outputs comparison."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        engine = ReproducibilityLabEngine()
        prov = engine.execute_reproduction(catalog[0], "PROC_PARKINSON_VOLATILITY")

        assert isinstance(prov, ReproductionProvenance)
        assert len(prov.reproduced_output_sha256) == 64
        assert prov.execution_environment["canonical_model"] == "CBE-0.7.0"

        # Comparison status must be in ReproductionStatus values
        assert prov.status in [s.value for s in ReproductionStatus]

    def test_local_rerun_is_never_independent_replication(self):
        """CRITICAL: Re-execution must NEVER be claimed as independent replication."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        engine = ReproducibilityLabEngine()
        prov = engine.execute_reproduction(catalog[0], "PROC_PARKINSON_VOLATILITY")

        assert prov.is_independent_replication is False
        notice = prov.comparison_details.get("governance_notice_tr", "")
        assert "bağımsız replikasyon" in notice.lower()


# ==============================================================================
# 5. RESEARCH PRIORITY ENGINE TESTS
# ==============================================================================

class TestResearchPriorityEngine:
    """Tests for Module 25.5: Research Priority Engine."""

    def test_prioritize_tasks_deterministic(self):
        """Verify prioritization sorts tasks deterministically by priority score."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        engine = ResearchPriorityEngine()
        priorities = engine.prioritize_catalog(catalog)

        assert len(priorities) > 0
        scores = [p.priority_score for p in priorities]
        assert scores == sorted(scores, reverse=True)

        for p in priorities:
            assert isinstance(p, PrioritizedResearchTask)
            assert p.priority_tier in [t.value for t in PriorityTier]
            assert len(p.recommended_next_step_tr) > 5

    def test_trading_logic_complete_insulation(self):
        """Verify priority items contain zero financial directional instructions."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        engine = ResearchPriorityEngine()
        priorities = engine.prioritize_catalog(catalog)

        forbidden_terms = ["buy", "sell", "long", "short", "take profit", "stop loss", "leverage"]
        for p in priorities:
            for term in forbidden_terms:
                assert term not in p.title_en.lower(), f"Forbidden financial term '{term}' in priority title"
                assert term not in p.recommended_next_step_tr.lower(), f"Forbidden term '{term}' in suggested step"


# ==============================================================================
# 6. RESEARCH DECISION REPORTS TESTS
# ==============================================================================

class TestResearchDecisionReports:
    """Tests for Module 25.6: Research Decision Reports."""

    def test_canonical_13_sections_present(self):
        """Verify all 13 canonical report sections are generated."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        builder = DecisionReportBuilder()
        report = builder.generate_report(catalog[0])

        assert isinstance(report, ResearchDecisionReport)
        assert report.record_id == catalog[0].id
        assert report.canonical_model == "CBE-0.7.0"
        assert report.governance_decision == "TECHNICAL_NO_GO"

        sections = report.sections
        assert len(sections) >= 13
        assert "sec_1_summary" in sections
        assert "sec_2_objective" in sections
        assert "sec_4_provenance" in sections
        assert "sec_10_readiness_status" in sections
        assert "sec_12_governance" in sections

    def test_html_export_generation(self):
        """Verify HTML decision report generation contains critical governance disclosures."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        builder = DecisionReportBuilder()
        report = builder.generate_report(catalog[0])
        html = report.to_html()

        assert isinstance(html, str)
        assert "<!DOCTYPE html>" in html
        assert "CBE-0.7.0" in html
        assert "TECHNICAL_NO_GO" in html
        assert catalog[0].id in html
        assert "Bilimsel Araştırma Karar" in html


# ==============================================================================
# 7. WORKSPACE ENGINE INTEGRATION TESTS
# ==============================================================================

class TestWorkspaceV2Integration:
    """Tests for ResearchWorkspaceV2Engine integration with Sprint 25 modules."""

    def test_workspace_overview_contains_decision_intelligence(self):
        """Verify get_workspace_overview includes grounded decision intelligence KPIs."""
        engine = ResearchWorkspaceV2Engine()
        overview = engine.get_workspace_overview()

        assert overview["status"] == "success"
        assert "decision_intelligence" in overview

        di = overview["decision_intelligence"]
        assert "graph_nodes_count" in di
        assert "graph_edges_count" in di
        assert "missing_links_count" in di
        assert "total_gaps_count" in di
        assert "critical_gaps_count" in di
        assert di["graph_nodes_count"] > 30

    def test_workspace_new_data_methods(self):
        """Verify workspace engine query methods for all new modules."""
        engine = ResearchWorkspaceV2Engine()

        # Evidence Graph Data
        graph_data = engine.get_evidence_graph_data()
        assert "graph" in graph_data
        assert len(graph_data["graph"]["nodes"]) > 30

        # Readiness Scorecards
        readiness_data = engine.get_readiness_scorecards()
        assert "scorecards" in readiness_data
        assert len(readiness_data["scorecards"]) > 0

        # Evidence Gaps
        gaps_data = engine.get_evidence_gaps()
        assert "gaps" in gaps_data
        assert "total_gaps_count" in gaps_data

        # Research Priorities
        priorities_data = engine.get_research_priorities()
        assert "priorities" in priorities_data
        assert len(priorities_data["priorities"]) > 0

        # Reproducibility Procedures
        proc_data = engine.get_reproducibility_procedures()
        assert "procedures" in proc_data
        assert len(proc_data["procedures"]) >= 5

        # Reproducibility Execution
        exec_res = engine.execute_offline_reproduction("RES-REGIME-01", "PROC_PARKINSON_VOLATILITY")
        assert exec_res["status"] == "success"
        assert "provenance" in exec_res

        # Decision Report
        report_res = engine.generate_decision_report("RES-REGIME-01")
        assert report_res["status"] == "success"
        assert "report" in report_res


# ==============================================================================
# 8. REST API ENDPOINTS TESTS
# ==============================================================================

class TestDashboardApiSprint25:
    """Tests for ProductDashboardApiService Sprint 25 endpoints."""

    @pytest.fixture
    def api_service(self):
        return ProductDashboardApiService()

    def test_api_evidence_graph_endpoint(self, api_service):
        """Verify GET /api/v1/product/workspace/evidence-graph."""
        status_code, body = api_service.handle_request("/api/v1/product/workspace/evidence-graph")
        assert status_code == 200
        assert body["status"] == "success"
        assert "graph" in body

    def test_api_readiness_endpoint(self, api_service):
        """Verify GET /api/v1/product/workspace/readiness."""
        status_code, body = api_service.handle_request("/api/v1/product/workspace/readiness")
        assert status_code == 200
        assert body["status"] == "success"
        assert "scorecards" in body

    def test_api_evidence_gaps_endpoint(self, api_service):
        """Verify GET /api/v1/product/workspace/evidence-gaps."""
        status_code, body = api_service.handle_request("/api/v1/product/workspace/evidence-gaps?severity=CRITICAL")
        assert status_code == 200
        assert body["status"] == "success"
        assert "gaps" in body

    def test_api_priorities_endpoint(self, api_service):
        """Verify GET /api/v1/product/workspace/priorities."""
        status_code, body = api_service.handle_request("/api/v1/product/workspace/priorities")
        assert status_code == 200
        assert body["status"] == "success"
        assert "priorities" in body

    def test_api_reproducibility_procedures_endpoint(self, api_service):
        """Verify GET /api/v1/product/workspace/reproducibility/procedures."""
        status_code, body = api_service.handle_request("/api/v1/product/workspace/reproducibility/procedures")
        assert status_code == 200
        assert body["status"] == "success"
        assert "procedures" in body

    def test_api_reproducibility_execute_endpoint(self, api_service):
        """Verify POST /api/v1/product/workspace/reproducibility/execute."""
        status_code, body = api_service.handle_post_request(
            "/api/v1/product/workspace/reproducibility/execute",
            body={"record_id": "RES-REGIME-01", "procedure_id": "PROC_PARKINSON_VOLATILITY"},
        )
        assert status_code == 200
        assert body["status"] == "success"
        assert "provenance" in body

    def test_api_decision_reports_endpoints(self, api_service):
        """Verify GET /api/v1/product/workspace/decision-reports JSON and HTML."""
        # JSON format
        status_code, body = api_service.handle_request(
            "/api/v1/product/workspace/decision-reports?record_id=RES-REGIME-01&format=json"
        )
        assert status_code == 200
        assert body["status"] == "success"
        assert "report" in body

        # HTML format
        status_code, body = api_service.handle_request(
            "/api/v1/product/workspace/decision-reports?record_id=RES-REGIME-01&format=html"
        )
        assert status_code == 200
        assert body["format"] == "html"
        assert "<!DOCTYPE html>" in body.get("html_content", "")


# ==============================================================================
# 9. CANONICAL MODEL & GOVERNANCE INVARIANTS
# ==============================================================================

class TestGovernanceInvariants:
    """Strict verification of canonical scientific governance invariants."""

    def test_model_cbe_070_strictly_frozen(self):
        """Ensure canonical model is strictly CBE-0.7.0 and frozen."""
        assert CANONICAL_MODEL == "CBE-0.7.0"
        assert CANONICAL_MODEL_STATUS == "STRICTLY_FROZEN"

    def test_governance_technical_no_go(self):
        """Ensure platform governance verdict is TECHNICAL_NO_GO."""
        assert GOVERNANCE_DECISION == "TECHNICAL_NO_GO"

    def test_directional_trading_permanently_prohibited(self):
        """Ensure all live order execution and directional trading are strictly disabled."""
        assert CBE_TRADING_DISABLED is True
        assert LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED is True

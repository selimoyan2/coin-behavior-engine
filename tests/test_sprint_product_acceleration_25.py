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

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
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
    ReferenceBlockedReason,
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
from coin_behavior_engine.product.attestation_verifier import (
    ObservationCompletenessAttestationVerifier,
    attestation_cache,
)
from coin_behavior_engine.product.credential_manager import signing_key_registry
from coin_behavior_engine.product.research_catalog_provider import ResearchRecord


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
        prov = engine.execute_reproduction(catalog[0], "PROC_FUNDING_RATE_SUMMARY")

        assert isinstance(prov, ReproductionProvenance)
        assert len(prov.reproduced_output_sha256) == 64
        assert len(prov.reference_output_sha256) == 64
        assert prov.execution_environment["canonical_model"] == "CBE-0.7.0"
        assert prov.status == ReproductionStatus.OUTPUTS_MATCHED.value

    def test_local_rerun_is_never_independent_replication(self):
        """CRITICAL: Re-execution must NEVER be claimed as independent replication."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        engine = ReproducibilityLabEngine()
        prov = engine.execute_reproduction(catalog[0], "PROC_FUNDING_RATE_SUMMARY")

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
        exec_res = engine.execute_offline_reproduction("RES-REGIME-01", "PROC_REGIME_STABILITY_EVAL")
        assert exec_res["status"] == "success"
        assert "provenance" in exec_res
        assert exec_res["provenance"]["status"] == ReproductionStatus.OUTPUTS_MATCHED.value

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
            body={"record_id": "RES-REGIME-01", "procedure_id": "PROC_REGIME_STABILITY_EVAL"},
        )
        assert status_code == 200
        assert body["status"] == "success"
        assert "provenance" in body
        assert body["provenance"]["status"] == ReproductionStatus.OUTPUTS_MATCHED.value

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


# ==============================================================================
# 10. SCIENTIFIC TRUST NEGATIVE TESTS (Sprint 25 Final Closure)
# ==============================================================================

class TestSprint25ScientificTrustNegativeCases:
    """Explicit negative test coverage for evidence verification and genuine reproduction."""

    @pytest.fixture(autouse=True)
    def setup_keys_and_cache(self):
        attestation_cache.clear()
        signing_key_registry.register_key("test-key-valid", "test-secret-1234567890", is_active=True)
        signing_key_registry.register_key("test-key-revoked", "test-secret-revoked-00", is_active=True)
        signing_key_registry.revoke_key("test-key-revoked")
        yield
        attestation_cache.clear()

    def test_negative_forged_attestation_rejected(self):
        """Negative: Forged attestation with valid-looking signature string is rejected."""
        rec = ResearchRecord(
            id="TEST-FORGED-01",
            title="Forged Attestation Test",
            title_en="Forged Attestation Test",
            category="Volatilite",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024",
            window_cadence="1h",
            specification_id="SP-01",
            observation_start_utc="2024-01-01T00:00:00Z",
            observation_end_utc="2024-01-06T00:00:00Z",
            observation_interval_count=120,
            source_artifact="data/test_artifact.json",
            source_artifact_sha256="46c4cb960dd36c613bb9826cb8d54185724d6060e11b822ed82fd9213a3e9598",
            sample_size=120,
            volatility_ratio=1.15,
        )
        forged_att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            record=rec,
            key_id="test-key-valid",
            secret="test-secret-1234567890",
            forged_signature="a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
        )
        rec.observation_completeness_attestation = forged_att

        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, forged_att)
        assert res["is_valid"] is False
        assert res["rejection_code"] in ("SIGNATURE_VERIFICATION_FAILED", "INVALID_SIGNATURE")

        scorecard = ScientificReadinessEvaluator.evaluate_record(rec)
        dim_comp = [d for d in scorecard.dimensions if d.dimension_key == "OBSERVATION_COMPLETENESS"][0]
        assert dim_comp.status == DimensionStatus.FAILED.value
        assert scorecard.is_ready_for_review is False
        assert scorecard.overall_verdict == OverallReadinessVerdict.INTEGRITY_FAILED.value

    def test_negative_revoked_signing_key_rejected(self):
        """Negative: Attestation signed with a revoked key is rejected."""
        rec = ResearchRecord(
            id="TEST-REVOKED-01",
            title="Revoked Key Test",
            title_en="Revoked Key Test",
            category="Volatilite",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024",
            window_cadence="1h",
            specification_id="SP-02",
            observation_start_utc="2024-01-01T00:00:00Z",
            observation_end_utc="2024-01-06T00:00:00Z",
            observation_interval_count=120,
            source_artifact="data/test_artifact.json",
            source_artifact_sha256="46c4cb960dd36c613bb9826cb8d54185724d6060e11b822ed82fd9213a3e9598",
            sample_size=120,
            volatility_ratio=1.15,
        )
        rev_att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            record=rec,
            key_id="test-key-revoked",
            secret="test-secret-revoked-00",
        )
        rec.observation_completeness_attestation = rev_att

        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, rev_att)
        assert res["is_valid"] is False
        assert res["rejection_code"] == "REVOKED_SIGNING_KEY"

        scorecard = ScientificReadinessEvaluator.evaluate_record(rec)
        dim_comp = [d for d in scorecard.dimensions if d.dimension_key == "OBSERVATION_COMPLETENESS"][0]
        assert dim_comp.status == DimensionStatus.FAILED.value
        assert scorecard.is_ready_for_review is False

    def test_negative_missing_source_artifact_fails_closed(self):
        """Negative: Missing source artifact file fails closed immediately."""
        rec = ResearchRecord(
            id="TEST-MISSING-FILE",
            title="Missing File Test",
            title_en="Missing File Test",
            category="Volatilite",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024",
            window_cadence="1h",
            specification_id="SP-03",
            observation_start_utc="2024-01-01T00:00:00Z",
            observation_end_utc="2024-01-06T00:00:00Z",
            observation_interval_count=120,
            source_artifact="data/nonexistent_missing_file_xyz.json",
            source_artifact_sha256="46c4cb960dd36c613bb9826cb8d54185724d6060e11b822ed82fd9213a3e9598",
            sample_size=120,
        )
        scorecard = ScientificReadinessEvaluator.evaluate_record(rec)
        dim_art = [d for d in scorecard.dimensions if d.dimension_key == "SOURCE_ARTIFACT_INTEGRITY"][0]
        assert dim_art.status == DimensionStatus.FAILED.value
        assert scorecard.overall_verdict == OverallReadinessVerdict.INTEGRITY_FAILED.value
        assert scorecard.is_ready_for_review is False

    def test_negative_altered_source_artifact_sha256_fails_closed(self):
        """Negative: Altered SHA-256 fails closed with integrity mismatch."""
        rec = ResearchRecord(
            id="TEST-CORRUPT-SHA",
            title="Corrupt SHA Test",
            title_en="Corrupt SHA Test",
            category="Volatilite",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024",
            window_cadence="1h",
            specification_id="SP-04",
            observation_start_utc="2024-01-01T00:00:00Z",
            observation_end_utc="2024-01-06T00:00:00Z",
            observation_interval_count=120,
            source_artifact="data/test_artifact.json",
            source_artifact_sha256="0000000000000000000000000000000000000000000000000000000000000000",
            sample_size=120,
        )
        scorecard = ScientificReadinessEvaluator.evaluate_record(rec)
        dim_art = [d for d in scorecard.dimensions if d.dimension_key == "SOURCE_ARTIFACT_INTEGRITY"][0]
        assert dim_art.status == DimensionStatus.FAILED.value
        assert scorecard.overall_verdict == OverallReadinessVerdict.INTEGRITY_FAILED.value
        assert scorecard.is_ready_for_review is False

    def test_negative_registered_dataset_without_verifiable_provenance(self):
        """Negative: Registered dataset ID without authentic lineage or attestation is UNVERIFIED or BLOCKED."""
        rec = ResearchRecord(
            id="TEST-SYNTHETIC-DS",
            title="Synthetic Dataset Test",
            title_en="Synthetic Dataset Test",
            category="Volatilite",
            dataset_id="OCTOBER-2026-INTAKE-SYNTHETIC",
            historical_period="2024",
            window_cadence="1h",
            specification_id="SP-05",
            observation_start_utc="2024-01-01T00:00:00Z",
            observation_end_utc="2024-01-06T00:00:00Z",
            observation_interval_count=120,
            source_artifact="data/test_artifact.json",
            source_artifact_sha256="46c4cb960dd36c613bb9826cb8d54185724d6060e11b822ed82fd9213a3e9598",
            sample_size=120,
        )
        scorecard = ScientificReadinessEvaluator.evaluate_record(rec)
        dim_ds = [d for d in scorecard.dimensions if d.dimension_key == "DATASET_PROVENANCE"][0]
        assert dim_ds.status == DimensionStatus.BLOCKED.value
        assert scorecard.is_ready_for_review is False

    def test_negative_altered_reference_output_yields_outputs_differ(self):
        """Negative: Discrepancy between reference and reproduced outputs yields OUTPUTS_DIFFER."""
        rec = ResearchWorkspaceV2Engine.get_canonical_catalog()[0]
        engine = ReproducibilityLabEngine()
        prov = engine.execute_reproduction(
            rec,
            procedure_name="PROC_FUNDING_RATE_SUMMARY",
            override_reference={"mean_funding_rate_bps": 999.9999},
            trusted_fixture_context=True,
        )
        assert prov.status == ReproductionStatus.OUTPUTS_DIFFER.value
        assert prov.comparison_details["matched"] is False

    def test_negative_missing_observations_yields_reproduction_blocked(self):
        """Negative: Missing raw observations blocks reproduction."""
        rec = ResearchWorkspaceV2Engine.get_canonical_catalog()[0]
        rec.category = "Volatilite"
        engine = ReproducibilityLabEngine()
        prov = engine.execute_reproduction(
            rec,
            procedure_name="PROC_PARKINSON_VOLATILITY",
            override_inputs={"highs": [100.0], "lows": [90.0]},
            trusted_fixture_context=True,
        )
        assert prov.status == ReproductionStatus.REPRODUCTION_BLOCKED.value
        assert "yetersiz" in prov.error_message_tr.lower() or "missing" in prov.error_message_en.lower() or "cannot" in prov.error_message_en.lower()

    def test_negative_unsupported_procedure_yields_reproduction_blocked(self):
        """Negative: Requesting non-allowlisted procedure yields REPRODUCTION_BLOCKED."""
        rec = ResearchWorkspaceV2Engine.get_canonical_catalog()[0]
        engine = ReproducibilityLabEngine()
        prov = engine.execute_reproduction(rec, procedure_name="PROC_FORBIDDEN_ALPHA_SEARCH")
        assert prov.status == ReproductionStatus.REPRODUCTION_BLOCKED.value
        assert "onaylı" in prov.error_message_tr.lower() or "approved" in prov.error_message_en.lower()

    def test_negative_cache_invalidation_on_source_file_modification(self):
        """Negative: Modifying the source artifact invalidates the verification cache."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as tf:
            tf.write('{"test": "content"}')
            temp_path = tf.name

        try:
            initial_sha = hashlib.sha256(Path(temp_path).read_bytes()).hexdigest()
            rec = ResearchRecord(
                id="TEST-CACHE-INV",
                title="Cache Invalidation Test",
                title_en="Cache Invalidation Test",
                category="Volatilite",
                dataset_id="BTCUSDT-SPOT-1H-2022-2026",
                historical_period="2024",
                window_cadence="1h",
                specification_id="SP-07",
                observation_start_utc="2024-01-01T00:00:00Z",
                observation_end_utc="2024-01-06T00:00:00Z",
                observation_interval_count=120,
                source_artifact=temp_path,
                source_artifact_sha256=initial_sha,
                sample_size=120,
            )
            att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
                record=rec,
                key_id="test-key-valid",
                secret="test-secret-1234567890",
            )
            # Verify and populate cache
            assert attestation_cache.stats["hit_count"] == 0
            res1 = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att, use_cache=True)
            assert res1["is_valid"] is True
            assert attestation_cache.stats["hit_count"] == 0

            # Subsequent verification hits cache
            res2 = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att, use_cache=True)
            assert res2["is_valid"] is True
            assert attestation_cache.stats["hit_count"] == 1

            # Mutate source file content and mtime
            time.sleep(0.05)
            Path(temp_path).write_text('{"test": "tampered_content"}')

            # Verification must fail and purge cache
            res3 = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att, use_cache=True)
            assert res3["is_valid"] is False
            assert "HASH_MISMATCH" in res3["rejection_code"]
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


# ==============================================================================
# 11. P0-1 DATASET PROVENANCE TRUST BOUNDARY TESTS (10 NEGATIVE + POSITIVE)
# ==============================================================================

class TestSprint25DatasetProvenanceTrustBoundary:
    """
    Tests for P0-1 Dataset Provenance Trust Boundary across ScientificReadinessEvaluator,
    EvidenceGraphService, EvidenceGapAnalyzer, ResearchPriorityEngine, and DecisionReportBuilder.
    """

    @pytest.fixture(autouse=True)
    def setup_keys_and_cache(self):
        attestation_cache.clear()
        signing_key_registry.register_key("prov-key-active", "prov-secret-active-9999", is_active=True)
        signing_key_registry.register_key("prov-key-revoked", "prov-secret-revoked-000", is_active=True)
        signing_key_registry.revoke_key("prov-key-revoked")
        yield
        attestation_cache.clear()

    def _make_record(self, tmp_file: str, sha256: str, ds_id: str = "BTCUSDT-SPOT-1H-2022-2026") -> ResearchRecord:
        return ResearchRecord(
            id="TEST-PROV-REC-01",
            title="Provenance Trust Boundary Record",
            title_en="Provenance Trust Boundary Record",
            category="Volatilite",
            dataset_id=ds_id,
            historical_period="2024-01-01 to 2024-01-06",
            window_cadence="1h",
            specification_id="SPEC-PROV-01",
            observation_start_utc="2024-01-01T00:00:00Z",
            observation_end_utc="2024-01-06T00:00:00Z",
            observation_interval_count=120,
            source_artifact=tmp_file,
            source_artifact_sha256=sha256,
            sample_size=120,
            volatility_ratio=1.18,
            raw_p_value=0.04,
            created_at_utc="2026-10-20T10:00:00Z",
        )

    def test_01_existing_directory_with_no_manifest_is_unverified(self, tmp_path):
        """1. Existing directory with no manifest -> UNVERIFIED (never VERIFIED from Path.exists())."""
        f = tmp_path / "artifact.json"
        f.write_text('{"status": "ok"}', encoding="utf-8")
        sha = hashlib.sha256(f.read_bytes()).hexdigest()

        # Even though data/binance_spot_multiyear/1h/ exists on disk, record has no attestation or manifest
        rec = self._make_record(str(f), sha, ds_id="BTCUSDT-SPOT-1H-2022-2026")
        assert Path("data/binance_spot_multiyear/1h/").exists()

        prov = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        assert prov["is_verified"] is False
        assert prov["readiness_status"] == DimensionStatus.UNVERIFIED.value
        assert prov["graph_status"] == "REGISTERED"
        assert prov["rejection_code"] == "MISSING_AUTHENTICATED_PROVENANCE"

        scorecard = ScientificReadinessEvaluator.evaluate_record(rec)
        d1 = next(d for d in scorecard.dimensions if d.dimension_key == "DATASET_PROVENANCE")
        assert d1.status == DimensionStatus.UNVERIFIED.value
        assert scorecard.is_ready_for_review is False

        # Cross-module consistency: Evidence Graph, Gap Analyzer, Decision Report
        graph = EvidenceGraphService.build_canonical_graph([rec])
        ds_node = graph.get_node("DS-BTCUSDT-SPOT-1H-2022-2026")
        assert ds_node is not None
        assert ds_node.status == "REGISTERED"
        assert any(m["missing_type"] == "DATASET_PROVENANCE_UNVERIFIED" for m in graph.detect_missing_links())

        gaps = EvidenceGapAnalyzer.analyze_record(rec)
        assert any(g.gap_category == GapCategory.MISSING_DATASET_PROVENANCE.value for g in gaps)

        rpt = DecisionReportBuilder.generate_report(rec)
        assert "UNVERIFIED" in rpt.sections["sec_4_provenance"]

    def test_02_existing_raw_file_with_no_trusted_lineage_is_unverified(self, tmp_path):
        """2. Existing raw file with no trusted lineage -> UNVERIFIED or FAILED."""
        f = tmp_path / "raw_data.json"
        f.write_text('{"raw": 123}', encoding="utf-8")
        sha = hashlib.sha256(f.read_bytes()).hexdigest()

        rec = self._make_record(str(f), sha, ds_id="CUSTOM-RAW-FILE-DATASET")
        prov = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        assert prov["is_verified"] is False
        assert prov["readiness_status"] == DimensionStatus.UNVERIFIED.value

        # Also test bare unauthenticated intake_manifest_path file without signature/lineage
        bad_manifest = tmp_path / "bare_manifest.json"
        bad_manifest.write_text('{"dataset_id": "CUSTOM-RAW-FILE-DATASET"}', encoding="utf-8")
        rec.intake_manifest_path = str(bad_manifest)
        prov2 = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        assert prov2["is_verified"] is False
        assert prov2["readiness_status"] == DimensionStatus.FAILED.value

    def test_03_forged_attestation_fails_provenance(self, tmp_path):
        """3. Valid-looking but forged attestation -> FAILED."""
        f = tmp_path / "art3.json"
        f.write_text('{"v": 3}', encoding="utf-8")
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        rec = self._make_record(str(f), sha)
        rec.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            record=rec,
            key_id="prov-key-active",
            secret="prov-secret-active-9999",
            forged_signature="hmac-sha256:prov-key-active:" + ("f" * 64),
        )

        prov = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        assert prov["is_verified"] is False
        assert prov["readiness_status"] == DimensionStatus.FAILED.value
        assert prov["rejection_code"] == "SIGNATURE_VERIFICATION_FAILED"

    def test_04_expired_attestation_fails_provenance(self, tmp_path):
        """4. Expired attestation -> FAILED."""
        f = tmp_path / "art4.json"
        f.write_text('{"v": 4}', encoding="utf-8")
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        rec = self._make_record(str(f), sha)
        rec.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            record=rec,
            key_id="prov-key-active",
            secret="prov-secret-active-9999",
            expires_at_utc="2020-01-01T00:00:00Z",
        )

        prov = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        assert prov["is_verified"] is False
        assert prov["readiness_status"] == DimensionStatus.FAILED.value
        assert prov["rejection_code"] == "ATTESTATION_EXPIRED"

    def test_05_revoked_signing_key_fails_provenance(self, tmp_path):
        """5. Revoked signing key -> FAILED."""
        f = tmp_path / "art5.json"
        f.write_text('{"v": 5}', encoding="utf-8")
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        rec = self._make_record(str(f), sha)
        rec.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            record=rec,
            key_id="prov-key-revoked",
            secret="prov-secret-revoked-000",
        )

        prov = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        assert prov["is_verified"] is False
        assert prov["readiness_status"] == DimensionStatus.FAILED.value
        assert prov["rejection_code"] == "REVOKED_SIGNING_KEY"

    def test_06_dataset_id_mismatch_fails_provenance(self, tmp_path):
        """6. Dataset ID mismatch -> FAILED."""
        f = tmp_path / "art6.json"
        f.write_text('{"v": 6}', encoding="utf-8")
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        rec = self._make_record(str(f), sha, ds_id="BTCUSDT-SPOT-1H-2022-2026")
        rec.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            record=rec,
            key_id="prov-key-active",
            secret="prov-secret-active-9999",
            override_dataset_id="DIFFERENT-DATASET-ID",
        )

        prov = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        assert prov["is_verified"] is False
        assert prov["readiness_status"] == DimensionStatus.FAILED.value
        assert prov["rejection_code"] == "DATASET_ID_MISMATCH"

    def test_07_source_sha256_mismatch_fails_provenance(self, tmp_path):
        """7. Source SHA-256 mismatch -> FAILED."""
        f = tmp_path / "art7.json"
        f.write_text('{"v": 7}', encoding="utf-8")
        wrong_sha = "1" * 64
        rec = self._make_record(str(f), wrong_sha)
        rec.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            record=rec,
            key_id="prov-key-active",
            secret="prov-secret-active-9999",
            override_sha256=wrong_sha,
        )

        prov = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        assert prov["is_verified"] is False
        assert prov["readiness_status"] == DimensionStatus.FAILED.value
        assert prov["rejection_code"] == "SOURCE_ARTIFACT_HASH_MISMATCH"

    def test_08_missing_physical_source_fails_provenance(self, tmp_path):
        """8. Missing physical source -> FAILED (enforce_source_file_integrity=True)."""
        missing_path = str(tmp_path / "nonexistent_source.json")
        fake_sha = "2" * 64
        rec = self._make_record(missing_path, fake_sha)
        rec.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            record=rec,
            key_id="prov-key-active",
            secret="prov-secret-active-9999",
            override_sha256=fake_sha,
        )

        prov = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        assert prov["is_verified"] is False
        assert prov["readiness_status"] == DimensionStatus.FAILED.value
        assert prov["rejection_code"] == "SOURCE_ARTIFACT_MISSING"

    def test_09_quarantined_dataset_is_blocked(self, tmp_path):
        """9. Quarantined dataset -> BLOCKED."""
        f = tmp_path / "art9.json"
        f.write_text('{"v": 9}', encoding="utf-8")
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        rec = self._make_record(str(f), sha, ds_id="BTCUSDT-OCTOBER-2026-INTAKE")
        rec.quarantine_status = "QUARANTINED"

        prov = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        assert prov["is_verified"] is False
        assert prov["readiness_status"] == DimensionStatus.BLOCKED.value
        assert prov["graph_status"] == "BLOCKED"
        assert prov["rejection_code"] == "DATASET_QUARANTINED"

    def test_10_source_mutation_after_verification_invalidates_provenance(self, tmp_path):
        """10. Source mutation after verification -> FAILED (cache invalidated)."""
        f = tmp_path / "art10.json"
        f.write_text('{"v": 10, "state": "clean"}', encoding="utf-8")
        sha = hashlib.sha256(f.read_bytes()).hexdigest()
        rec = self._make_record(str(f), sha)
        rec.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            record=rec,
            key_id="prov-key-active",
            secret="prov-secret-active-9999",
        )

        # Initial verification succeeds
        prov1 = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        assert prov1["is_verified"] is True
        assert prov1["readiness_status"] == DimensionStatus.VERIFIED.value

        # Mutate physical source file on disk
        time.sleep(0.02)
        f.write_text('{"v": 10, "state": "tampered_after_verification"}', encoding="utf-8")

        # Subsequent provenance check must fail closed
        prov2 = ScientificReadinessEvaluator.verify_dataset_provenance(rec)
        assert prov2["is_verified"] is False
        assert prov2["readiness_status"] == DimensionStatus.FAILED.value
        assert prov2["rejection_code"] == "SOURCE_ARTIFACT_HASH_MISMATCH"

    def test_11_positive_verified_provenance_via_attestation_and_intake_manifest(self, tmp_path):
        """Positive: Cryptographically signed attestation OR signed intake manifest grants VERIFIED provenance across all modules."""
        f = tmp_path / "art_pos.json"
        f.write_text('{"highs": [105,106,107,108,109,110,111,112,113,114], "lows": [100,101,102,103,104,105,106,107,108,109]}', encoding="utf-8")
        sha = hashlib.sha256(f.read_bytes()).hexdigest()

        # Path A: Signed Attestation
        rec_att = self._make_record(str(f), sha)
        rec_att.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            record=rec_att,
            key_id="prov-key-active",
            secret="prov-secret-active-9999",
        )
        sc_att = ScientificReadinessEvaluator.evaluate_record(rec_att)
        d1_att = next(d for d in sc_att.dimensions if d.dimension_key == "DATASET_PROVENANCE")
        assert d1_att.status == DimensionStatus.VERIFIED.value
        assert sc_att.is_ready_for_review is True
        assert sc_att.overall_verdict == OverallReadinessVerdict.READY_FOR_CONFIRMATORY_REVIEW.value

        graph_att = EvidenceGraphService.build_canonical_graph([rec_att])
        ds_node = graph_att.get_node("DS-BTCUSDT-SPOT-1H-2022-2026")
        assert ds_node.status == "INTEGRITY_VERIFIED"
        assert not any(m["missing_type"] == "DATASET_PROVENANCE_UNVERIFIED" for m in graph_att.detect_missing_links())

        gaps_att = EvidenceGapAnalyzer.analyze_record(rec_att)
        assert not any(g.gap_category == GapCategory.MISSING_DATASET_PROVENANCE.value for g in gaps_att)

        # Path B: Signed Intake Manifest
        rec_man = self._make_record(str(f), sha, ds_id="BTCUSDT-MANIFEST-VERIFIED-DS")
        manifest_obj = ScientificReadinessEvaluator.create_signed_intake_manifest(
            record=rec_man,
            key_id="prov-key-active",
            secret="prov-secret-active-9999",
        )
        manifest_path = tmp_path / "signed_intake_manifest.json"
        manifest_path.write_text(json.dumps(manifest_obj), encoding="utf-8")
        rec_man.intake_manifest_path = str(manifest_path)

        prov_man = ScientificReadinessEvaluator.verify_dataset_provenance(rec_man)
        assert prov_man["is_verified"] is True
        assert prov_man["readiness_status"] == DimensionStatus.VERIFIED.value
        assert prov_man["mechanism"] == "TRUSTED_INTAKE_MANIFEST"


# ==============================================================================
# 12. P0-2 INDEPENDENT REFERENCE VALIDATION TESTS (10 NEGATIVE + POSITIVE)
# ==============================================================================

class TestSprint25IndependentReferenceValidation:
    """
    Tests for P0-2 Independent Reference Validation in ReproducibilityLabEngine.
    Verifies zero computed-to-reference fallback across all 5 allowlisted procedures.
    """

    @pytest.fixture(autouse=True)
    def setup_keys(self):
        signing_key_registry.register_key("ref-key-active", "ref-secret-active-7777", is_active=True)
        yield

    def test_neg_01_missing_reference_blocks_reproduction(self, tmp_path):
        """1. Missing reference -> REPRODUCTION_BLOCKED (MISSING_TRUSTED_REFERENCE)."""
        # Create artifact with valid high/low observations but NO parkinson_volatility reference field
        f = tmp_path / "parkinson_no_ref.json"
        highs = [105.0 + i for i in range(20)]
        lows = [100.0 + i for i in range(20)]
        f.write_text(json.dumps({"highs": highs, "lows": lows}), encoding="utf-8")
        sha = hashlib.sha256(f.read_bytes()).hexdigest()

        rec = ResearchRecord(
            id="TEST-REF-MISS-01",
            title="Missing Reference Test",
            title_en="Missing Reference Test",
            category="Volatilite",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024",
            window_cadence="1h",
            specification_id="SP-REF-01",
            source_artifact=str(f),
            source_artifact_sha256=sha,
            sample_size=20,
            created_at_utc="2026-10-20T00:00:00Z",
        )
        prov = ReproducibilityLabEngine.execute_reproduction(
            rec, "PROC_PARKINSON_VOLATILITY", trusted_fixture_context=True
        )
        assert prov.status == ReproductionStatus.REPRODUCTION_BLOCKED.value
        assert ReferenceBlockedReason.MISSING_TRUSTED_REFERENCE.value in prov.comparison_details["blocked_reason"]

    def test_neg_02_reference_with_missing_provenance_blocks_reproduction(self, tmp_path):
        """2. Reference with missing provenance -> REPRODUCTION_BLOCKED (UNVERIFIED_REFERENCE_PROVENANCE)."""
        f = tmp_path / "unverified_prov_art.json"
        highs = [105.0 + i for i in range(20)]
        lows = [100.0 + i for i in range(20)]
        f.write_text(json.dumps({"highs": highs, "lows": lows, "parkinson_volatility": 2.5, "sample_size": 20}), encoding="utf-8")
        sha = hashlib.sha256(f.read_bytes()).hexdigest()

        rec = ResearchRecord(
            id="TEST-REF-UNVERIFIED-02",
            title="Unverified Artifact Reference",
            title_en="Unverified Artifact Reference",
            category="Volatilite",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024",
            window_cadence="1h",
            specification_id="SP-REF-02",
            source_artifact=str(f),
            source_artifact_sha256=sha,
            sample_size=20,
            created_at_utc="2026-10-20T00:00:00Z",
        )
        # Without trusted_fixture_context, signed attestation, or TRUSTED_ARTIFACT_REGISTRY entry -> blocked
        prov = ReproducibilityLabEngine.execute_reproduction(rec, "PROC_PARKINSON_VOLATILITY")
        assert prov.status == ReproductionStatus.REPRODUCTION_BLOCKED.value
        assert prov.comparison_details["blocked_reason"] == ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value

    def test_neg_03_reference_from_another_dataset_blocks_reproduction(self):
        """3. Reference from another dataset -> REPRODUCTION_BLOCKED (UNVERIFIED_REFERENCE_PROVENANCE)."""
        rec = ResearchWorkspaceV2Engine.get_canonical_catalog()[0]  # RES-FUND-01
        ref_out = {"mean_funding_bps": 1.0103, "sample_size": 1185}
        bad_prov = ReproducibilityLabEngine.create_signed_reference_provenance(
            record=rec,
            procedure_name="PROC_FUNDING_RATE_SUMMARY",
            reference_outputs=ref_out,
            key_id="ref-key-active",
            secret="ref-secret-active-7777",
            override_dataset_id="WRONG-OTHER-DATASET-ID",
        )
        prov = ReproducibilityLabEngine.execute_reproduction(
            rec,
            "PROC_FUNDING_RATE_SUMMARY",
            override_reference=ref_out,
            reference_provenance=bad_prov,
        )
        assert prov.status == ReproductionStatus.REPRODUCTION_BLOCKED.value
        assert prov.comparison_details["blocked_reason"] == ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value

    def test_neg_04_reference_from_another_methodology_blocks_reproduction(self):
        """4. Reference from another methodology -> REPRODUCTION_BLOCKED (UNVERIFIED_REFERENCE_PROVENANCE)."""
        # Calling PROC_PARKINSON_VOLATILITY on RES-FUND-01 (Funding category) or RES-REGIME-01 (Regime category)
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        fund_rec = next(r for r in catalog if r.id == "RES-FUND-01")
        prov = ReproducibilityLabEngine.execute_reproduction(fund_rec, "PROC_PARKINSON_VOLATILITY")
        assert prov.status == ReproductionStatus.REPRODUCTION_BLOCKED.value
        assert prov.comparison_details["blocked_reason"] == ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value

    def test_neg_05_reference_created_during_same_attempt_blocks_reproduction(self):
        """5. Reference created during the same reproduction attempt -> REPRODUCTION_BLOCKED."""
        rec = ResearchWorkspaceV2Engine.get_canonical_catalog()[0]
        ref_out = {"mean_funding_bps": 1.0103, "sample_size": 1185}
        same_run_prov = ReproducibilityLabEngine.create_signed_reference_provenance(
            record=rec,
            procedure_name="PROC_FUNDING_RATE_SUMMARY",
            reference_outputs=ref_out,
            key_id="ref-key-active",
            secret="ref-secret-active-7777",
            created_during_reproduction_attempt=True,
        )
        prov = ReproducibilityLabEngine.execute_reproduction(
            rec,
            "PROC_FUNDING_RATE_SUMMARY",
            override_reference=ref_out,
            reference_provenance=same_run_prov,
        )
        assert prov.status == ReproductionStatus.REPRODUCTION_BLOCKED.value
        assert prov.comparison_details["blocked_reason"] == ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value

    def test_neg_06_caller_supplied_untrusted_override_blocks_reproduction(self):
        """6. Caller-supplied untrusted override -> REPRODUCTION_BLOCKED (UNVERIFIED_REFERENCE_PROVENANCE)."""
        rec = ResearchWorkspaceV2Engine.get_canonical_catalog()[0]
        # Passing override_reference without trusted_fixture_context=True or signed reference_provenance
        prov = ReproducibilityLabEngine.execute_reproduction(
            rec,
            "PROC_FUNDING_RATE_SUMMARY",
            override_reference={"mean_funding_bps": 1.0103},
        )
        assert prov.status == ReproductionStatus.REPRODUCTION_BLOCKED.value
        assert prov.comparison_details["blocked_reason"] == ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value

    def test_neg_07_tampered_reference_artifact_blocks_reproduction(self, tmp_path):
        """7. Tampered reference artifact -> REPRODUCTION_BLOCKED."""
        f = tmp_path / "tampered_ref.json"
        f.write_text('{"break_even_analysis": {"observed_mean_funding_bps": 99.0}}', encoding="utf-8")
        rec = ResearchRecord(
            id="TEST-TAMPERED-07",
            title="Tampered Reference Artifact",
            title_en="Tampered Reference Artifact",
            category="Fonlama",
            dataset_id="BTCUSDT-PERP-FUNDING-2022-2026",
            historical_period="2024",
            window_cadence="8h",
            specification_id="SP-07",
            source_artifact=str(f),
            source_artifact_sha256="f" * 64,  # Mismatched SHA-256
            sample_size=1185,
        )
        prov = ReproducibilityLabEngine.execute_reproduction(rec, "PROC_FUNDING_RATE_SUMMARY")
        assert prov.status == ReproductionStatus.REPRODUCTION_BLOCKED.value

    def test_neg_08_changed_source_observations_yields_outputs_differ(self):
        """8. Changed source observations -> OUTPUTS_DIFFER (never masked by fallback!)."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        fund_rec = next(r for r in catalog if r.id == "RES-FUND-01")

        # Provide altered funding rate observations while keeping the canonical stored reference in sprint09_38 report
        altered_rates = [5.5 if i % 2 == 0 else -2.0 for i in range(200)]
        prov = ReproducibilityLabEngine.execute_reproduction(
            fund_rec,
            "PROC_FUNDING_RATE_SUMMARY",
            override_inputs={"rates": altered_rates},
        )
        assert prov.status == ReproductionStatus.OUTPUTS_DIFFER.value
        assert prov.comparison_details["matched"] is False
        assert prov.reference_output_sha256 != prov.reproduced_output_sha256

    def test_neg_09_different_computed_output_yields_outputs_differ(self):
        """9. Different computed output -> OUTPUTS_DIFFER across DTW and Regime procedures."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        analog_rec = next(r for r in catalog if r.id == "RES-ANALOG-01")

        # Mutate component distances so recomputed composite_distance differs from stored reference (0.0692)
        mutated_components = {
            "return_structure": {"weight": 0.5, "distance_value": 0.45},
            "volatility_profile": {"weight": 0.5, "distance_value": 0.55},
        }
        prov = ReproducibilityLabEngine.execute_reproduction(
            analog_rec,
            "PROC_DTW_PATTERN_DISTANCE",
            override_inputs={"components": mutated_components},
        )
        assert prov.status == ReproductionStatus.OUTPUTS_DIFFER.value
        assert prov.reference_outputs["composite_distance"] == 0.0692
        assert prov.reproduced_outputs["composite_distance"] == 0.5000

    def test_neg_10_missing_essential_raw_data_blocks_reproduction(self):
        """10. Missing essential raw data -> REPRODUCTION_BLOCKED."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        reg_rec = next(r for r in catalog if r.id == "RES-REGIME-01")
        prov = ReproducibilityLabEngine.execute_reproduction(
            reg_rec,
            "PROC_REGIME_STABILITY_EVAL",
            override_inputs={"candles": []},
        )
        assert prov.status == ReproductionStatus.REPRODUCTION_BLOCKED.value
        assert ReferenceBlockedReason.MISSING_RAW_OBSERVATIONS.value in prov.comparison_details["blocked_reason"]

    def test_neg_11_historical_storage_report_without_mountinfo_blocks_reexecution(self):
        """11. Historical storage report inspection without raw mountinfo -> REPRODUCTION_BLOCKED (HISTORICAL_REPORT_INSPECTION_ONLY)."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()
        dur_rec = next(r for r in catalog if r.id == "RES-DURABILITY-01")
        prov = ReproducibilityLabEngine.execute_reproduction(dur_rec, "PROC_STORAGE_VERIFICATION")
        assert prov.status == ReproductionStatus.REPRODUCTION_BLOCKED.value
        assert ReferenceBlockedReason.HISTORICAL_REPORT_INSPECTION_ONLY.value in prov.comparison_details["blocked_reason"]
        assert prov.comparison_details["audit_mode"] == "HISTORICAL_REPORT_INSPECTION"
        assert prov.comparison_details["storage_test_reexecuted"] is False

    def test_pos_12_all_five_procedures_match_independent_verified_references(self, tmp_path):
        """Positive: All 5 allowlisted procedures recompute from raw observations and match independent references."""
        catalog = ResearchWorkspaceV2Engine.get_canonical_catalog()

        # 1. PROC_FUNDING_RATE_SUMMARY (RES-FUND-01)
        fund_rec = next(r for r in catalog if r.id == "RES-FUND-01")
        p_fund = ReproducibilityLabEngine.execute_reproduction(fund_rec, "PROC_FUNDING_RATE_SUMMARY")
        assert p_fund.status == ReproductionStatus.OUTPUTS_MATCHED.value
        assert p_fund.is_independent_replication is False
        assert p_fund.reproduced_outputs["mean_funding_bps"] == 1.0103
        assert p_fund.reproduced_outputs["negative_funding_count"] == 103
        assert p_fund.reproduced_outputs["sample_size"] == 1185

        # 2. PROC_REGIME_STABILITY_EVAL (RES-REGIME-01 recomputed from 8,736 q1_2024 candles)
        reg_rec = next(r for r in catalog if r.id == "RES-REGIME-01")
        p_reg = ReproducibilityLabEngine.execute_reproduction(reg_rec, "PROC_REGIME_STABILITY_EVAL")
        assert p_reg.status == ReproductionStatus.OUTPUTS_MATCHED.value
        assert p_reg.is_independent_replication is False
        assert p_reg.reproduced_outputs["direct_transitions_observed_count"] == 5
        assert p_reg.reproduced_outputs["direct_transitions_total_evaluated"] == 822
        assert p_reg.reproduced_outputs["direct_transition_rate_pct"] == 0.61
        assert p_reg.reproduced_outputs["total_bars_evaluated"] == 8736

        # 3. PROC_DTW_PATTERN_DISTANCE (RES-ANALOG-01 recomputed from component vectors)
        analog_rec = next(r for r in catalog if r.id == "RES-ANALOG-01")
        p_dtw = ReproducibilityLabEngine.execute_reproduction(analog_rec, "PROC_DTW_PATTERN_DISTANCE")
        assert p_dtw.status == ReproductionStatus.OUTPUTS_MATCHED.value
        assert p_dtw.is_independent_replication is False
        assert p_dtw.reproduced_outputs["composite_distance"] == 0.0692
        assert p_dtw.reproduced_outputs["similarity_score_pct"] == 93.08

        # 4. PROC_PARKINSON_VOLATILITY (with signed independent reference provenance)
        f_park = tmp_path / "parkinson_verified.json"
        highs = [102.0] * 120
        lows = [100.0] * 120
        import math as _m
        expected_park = round(_m.sqrt(1.0 / (4.0 * _m.log(2.0)) * (_m.log(102.0 / 100.0) ** 2)) * _m.sqrt(8760.0), 4)
        f_park.write_text(
            json.dumps({
                "methodology": "PARKINSON_HIGH_LOW",
                "highs": highs,
                "lows": lows,
                "parkinson_volatility": expected_park,
                "sample_size": 120,
                "timestamp_utc": "2026-10-15T00:00:00Z",
            }),
            encoding="utf-8",
        )
        park_sha = hashlib.sha256(f_park.read_bytes()).hexdigest()
        park_rec = ResearchRecord(
            id="TEST-PARK-POS-01",
            title="Parkinson Verified Test",
            title_en="Parkinson Verified Test",
            category="Volatilite",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024-01-01 to 2024-01-06",
            window_cadence="1h",
            specification_id="SP-PARK-01",
            observation_start_utc="2024-01-01T00:00:00Z",
            observation_end_utc="2024-01-06T00:00:00Z",
            observation_interval_count=120,
            source_artifact=str(f_park),
            source_artifact_sha256=park_sha,
            sample_size=120,
            created_at_utc="2026-10-15T00:00:00Z",
        )
        ref_env = ReproducibilityLabEngine.create_signed_reference_provenance(
            record=park_rec,
            procedure_name="PROC_PARKINSON_VOLATILITY",
            reference_outputs={
                "methodology": "PARKINSON_HIGH_LOW",
                "sample_size": 120,
                "parkinson_volatility": expected_park,
            },
            key_id="ref-key-active",
            secret="ref-secret-active-7777",
            methodology="PARKINSON_HIGH_LOW",
        )
        p_park = ReproducibilityLabEngine.execute_reproduction(
            park_rec, "PROC_PARKINSON_VOLATILITY", reference_provenance=ref_env
        )
        assert p_park.status == ReproductionStatus.OUTPUTS_MATCHED.value
        assert p_park.reproduced_outputs["parkinson_volatility"] == expected_park

        # 5. PROC_STORAGE_VERIFICATION (RES-DURABILITY-01 with raw kernel mountinfo_content)
        dur_rec = next(r for r in catalog if r.id == "RES-DURABILITY-01")
        mountinfo_line = (
            "942 931 8:1 /var/lib/docker/volumes/dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f/_data "
            "/app/data/prospective rw,relatime - ext4 /dev/sda1 rw\n"
        )
        p_dur = ReproducibilityLabEngine.execute_reproduction(
            dur_rec,
            "PROC_STORAGE_VERIFICATION",
            override_inputs={"mountinfo_content": mountinfo_line},
        )
        assert p_dur.status == ReproductionStatus.OUTPUTS_MATCHED.value
        assert p_dur.is_independent_replication is False
        assert p_dur.reproduced_outputs["authorized_volume_id"] == "dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f"
        assert p_dur.reproduced_outputs["durability_verdict"] == "VERIFIED_DURABLE"


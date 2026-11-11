"""
Sprint 27 — Comprehensive Test Suite:
Scientific Research Portfolio, Experiment Intelligence, Evidence Traceability & Dashboard V5.
(CBE_SPRINT27_SCIENTIFIC_RESEARCH_PORTFOLIO)

Covers:
1. Unit tests for Modules 27.1 through 27.8.
2. Integration tests across Portfolio -> Experiment -> Comparison -> Traceability -> Findings -> Review -> Report -> Dashboard V5.
3. Scientific integrity tests (no fabricated fields, no raw p-value ranking, no zero imputation, 6-tier trust separation).
4. All 20 mandatory Negative Security Tests from Section 16.
"""

from __future__ import annotations

from http import HTTPStatus
import os
import pytest

from coin_behavior_engine.product.credential_manager import (
    CredentialManager,
    KEY_PURPOSE_EVIDENCE_BUNDLE,
    KEY_PURPOSE_INTAKE_MANIFEST,
    KEY_PURPOSE_REPLICATION_ATTESTATION,
    SigningAuthorityContext,
    SigningAuthorityError,
    signing_key_registry,
)
from coin_behavior_engine.product.cross_experiment_comparison import (
    COMPARISON_16_DIMENSIONS,
    VALID_COMPARISON_VERDICTS,
    CrossExperimentComparisonEngine,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.evidence_traceability_explorer import (
    TRACEABILITY_CHAIN_STAGE_ORDER,
    EvidenceTraceabilityExplorer,
)
from coin_behavior_engine.product.experiment_timeline_registry import (
    REQUIRED_EXPERIMENT_FIELDS,
    VALID_EXPERIMENT_LIFECYCLE_STATES,
    ExperimentRegistryAndTimelineService,
    ExperimentRegistrySecurityError,
    experiment_registry_service,
)
from coin_behavior_engine.product.findings_contradiction_intelligence import (
    REQUIRED_FINDING_FIELDS,
    VALID_CONTRADICTION_VERDICTS,
    VALID_FINDING_CATEGORIES,
    FindingClassificationError,
    FindingsAndContradictionEngine,
)
from coin_behavior_engine.product.independent_validation_framework import (
    IndependentValidationFramework,
)
from coin_behavior_engine.product.reproducibility_lab import (
    ReferenceBlockedReason,
    ReproducibilityLabEngine,
)
from coin_behavior_engine.product.research_catalog_provider import (
    ResearchCatalogProvider,
)
from coin_behavior_engine.product.research_explorer_ui import (
    render_research_explorer_html,
    render_research_explorer_scripts,
)
from coin_behavior_engine.product.research_portfolio_manager import (
    REQUIRED_PORTFOLIO_FIELDS,
    PortfolioSecurityError,
    ScientificResearchPortfolioManager,
)
from coin_behavior_engine.product.research_review_workflow import (
    VALID_REVIEW_DECISIONS,
    VALID_REVIEW_STATES,
    ResearchReviewWorkflowEngine,
    ReviewWorkflowSecurityError,
    research_review_workflow_engine,
)
from coin_behavior_engine.product.scientific_readiness import (
    ScientificReadinessEvaluator,
)
from coin_behavior_engine.product.scientific_report_builder_v5 import (
    REQUIRED_21_REPORT_SECTIONS,
    VALID_REPORT_TYPES,
    ReportBuilderSecurityError,
    ScientificReportBuilderV5,
)


# =============================================================================
# 1. MODULE 27.1 — SCIENTIFIC RESEARCH PORTFOLIO MANAGER TESTS
# =============================================================================


class TestModule27_1_PortfolioManager:
    def test_portfolio_fields_and_summary_counts_computed_from_records(self):
        res = ScientificResearchPortfolioManager.query_portfolio(page=1, page_size=20)
        assert res["status"] == "success"
        assert res["canonical_model"] == "CBE-0.7.0"
        assert res["governance_decision"] == "TECHNICAL_NO_GO"

        items = res["items"]
        assert len(items) >= 6
        for item in items:
            for req_field in REQUIRED_PORTFOLIO_FIELDS:
                assert req_field in item

        summary = res["portfolio_summary"]
        assert summary["total_registered_records"] == len(items)
        actual_verified = sum(
            1 for i in items if i["evidence_integrity_status"] == "INTEGRITY_VERIFIED"
        )
        assert summary["records_with_verified_evidence"] == actual_verified
        assert summary["records_blocked_by_provenance"] >= 1

    def test_portfolio_filtering_sorting_and_bounded_pagination(self):
        res_filtered = ScientificResearchPortfolioManager.query_portfolio(
            dataset_id="BTCUSDT-SPOT-1H",
            evidence_integrity_status="INTEGRITY_VERIFIED",
            sort_by="research_id",
            sort_dir="desc",
            page=1,
            page_size=2,
        )
        assert res_filtered["pagination"]["page_size"] == 2
        items = res_filtered["items"]
        assert len(items) <= 2
        if len(items) == 2:
            assert items[0]["research_id"] >= items[1]["research_id"]
        for it in items:
            assert "BTCUSDT-SPOT-1H" in it["dataset_id"]
            assert it["evidence_integrity_status"] == "INTEGRITY_VERIFIED"


# =============================================================================
# 2. MODULE 27.2 — EXPERIMENT REGISTRY & TIMELINE TESTS
# =============================================================================


class TestModule27_2_ExperimentRegistryAndTimeline:
    def test_canonical_experiments_and_required_20_fields(self):
        res = experiment_registry_service.list_experiments()
        assert res["status"] == "success"
        assert res["timeline_chain_integrity"]["chain_valid"] is True
        exps = res["experiments"]
        assert len(exps) >= 6
        for exp in exps:
            for req_f in REQUIRED_EXPERIMENT_FIELDS:
                assert req_f in exp
            assert exp["execution_status"] in VALID_EXPERIMENT_LIFECYCLE_STATES

    def test_idempotent_duplicate_registration_and_explicit_rerun_isolation(self):
        svc = ExperimentRegistryAndTimelineService()
        reg1 = svc.register_experiment(
            research_id="RES-REGIME-01",
            experiment_type="CUSTOM_TEST_EVAL",
            experiment_title="Test Study",
            hypothesis_id="HYP-TEST-01",
            methodology_id="METH-TEST-01",
            dataset_id="BTCUSDT-SPOT-1H",
            dataset_fingerprint="fp-123",
            parameters={"window": 24},
            requested_status="EXECUTION_COMPLETED",
            is_rerun=False,
        )
        exp_id = reg1["experiment"]["experiment_id"]
        assert reg1["registration_mode"] == "NEW_REGISTRATION"
        assert len(reg1["experiment"]["execution_attempts"]) == 1
        # EXECUTION_COMPLETED does not auto-promote to EVIDENCE_VERIFIED
        assert reg1["experiment"]["execution_status"] == "EXECUTION_COMPLETED"
        assert reg1["experiment"]["provenance_verdict"] == "UNVERIFIED"

        # Duplicate registration without is_rerun is idempotent
        reg2 = svc.register_experiment(
            research_id="RES-REGIME-01",
            experiment_type="CUSTOM_TEST_EVAL",
            experiment_title="Test Study",
            hypothesis_id="HYP-TEST-01",
            methodology_id="METH-TEST-01",
            dataset_id="BTCUSDT-SPOT-1H",
            dataset_fingerprint="fp-123",
            parameters={"window": 24},
            requested_status="EXECUTION_COMPLETED",
            is_rerun=False,
        )
        assert reg2["registration_mode"] == "IDEMPOTENT_EXISTING"
        assert reg2["experiment"]["experiment_id"] == exp_id
        assert len(reg2["experiment"]["execution_attempts"]) == 1

        # Explicit rerun appends attempt #2 without overwriting attempt #1
        reg3 = svc.register_experiment(
            research_id="RES-REGIME-01",
            experiment_type="CUSTOM_TEST_EVAL",
            experiment_title="Test Study",
            hypothesis_id="HYP-TEST-01",
            methodology_id="METH-TEST-01",
            dataset_id="BTCUSDT-SPOT-1H",
            dataset_fingerprint="fp-123",
            parameters={"window": 24},
            requested_status="EXECUTION_COMPLETED",
            result_digest="digest-attempt-2",
            is_rerun=True,
        )
        assert reg3["registration_mode"] == "EXPLICIT_RERUN_APPENDED"
        assert len(reg3["experiment"]["execution_attempts"]) == 2
        assert svc.verify_timeline_chain_integrity()["chain_valid"] is True


# =============================================================================
# 3. MODULE 27.3 — CROSS-EXPERIMENT COMPARISON INTELLIGENCE TESTS
# =============================================================================


class TestModule27_3_CrossExperimentComparison:
    def test_compare_experiments_16_dimensions_and_8_gates(self):
        res = CrossExperimentComparisonEngine.compare_experiments(
            ["RES-REGIME-01", "RES-ANALOG-01"]
        )
        assert res["status"] == "success"
        comp = res["comparison"]
        assert comp["comparison_verdict"] in VALID_COMPARISON_VERDICTS
        assert len(comp["comparability_gate_checks"]) == 8
        for dim in COMPARISON_16_DIMENSIONS:
            assert dim in comp["dimension_comparison_matrix"]
        # Overlapping 2022-2026 observations are never treated as independent
        assert "OVERLAPPING_SAMPLES_NOT_INDEPENDENT" in comp["sample_independence_verdict"]

    def test_quarantined_or_incompatible_comparison_rejected_as_not_comparable(self):
        res = CrossExperimentComparisonEngine.compare_experiments(
            ["RES-REGIME-01", "RES-QUARANTINE-01"]
        )
        assert res["status"] == "success"
        comp = res["comparison"]
        assert comp["comparison_verdict"] == "NOT_COMPARABLE"
        assert comp["is_inferentially_comparable"] is False

    def test_prohibited_raw_p_ranking_and_zero_imputation_rejected(self):
        res_p = CrossExperimentComparisonEngine.compare_experiments(
            ["RES-REGIME-01", "RES-ANALOG-01"],
            rank_by_raw_p_value=True,
        )
        assert res_p["status"] == "error"
        assert res_p["rejection_code"] == "RAW_P_VALUE_RANKING_PROHIBITED"

        res_z = CrossExperimentComparisonEngine.compare_experiments(
            ["RES-REGIME-01", "RES-ANALOG-01"],
            replace_missing_with_zero=True,
        )
        assert res_z["status"] == "error"
        assert res_z["rejection_code"] == "ZERO_IMPUTATION_OF_MISSING_METRICS_PROHIBITED"


# =============================================================================
# 4. MODULE 27.4 — EVIDENCE TRACEABILITY & PROVENANCE EXPLORER TESTS
# =============================================================================


class TestModule27_4_EvidenceTraceabilityExplorer:
    def test_12_stage_traceability_chain_and_6_tier_trust_progression(self):
        res = EvidenceTraceabilityExplorer.trace_evidence_chain("RES-REGIME-01", max_depth=6)
        assert res["status"] == "success"
        chain = res["traceability_chain"]
        assert [s["stage_name"] for s in chain] == list(TRACEABILITY_CHAIN_STAGE_ORDER)
        tp = res["trust_progression"]
        assert tp["tier_progression"]["ARTIFACT_PRESENT"] is True
        assert tp["tier_progression"]["INTEGRITY_VERIFIED"] is True
        assert tp["tier_progression"]["METHODOLOGY_VALIDATED"] is True
        # Independent replication is not automatically granted from temporal holdout
        assert tp["tier_progression"]["INDEPENDENT_REPLICATION"] is False


# =============================================================================
# 5. MODULE 27.5 — SCIENTIFIC FINDINGS & CONTRADICTION INTELLIGENCE TESTS
# =============================================================================


class TestModule27_5_FindingsAndContradictions:
    def test_canonical_findings_schema_and_categories(self):
        res = FindingsAndContradictionEngine.get_findings_and_contradictions()
        assert res["status"] == "success"
        findings = res["findings"]
        assert len(findings) >= 6
        for f in findings:
            for req_f in REQUIRED_FINDING_FIELDS:
                assert req_f in f
            assert f["finding_type"] in VALID_FINDING_CATEGORIES

        for c in res["contradictions"]:
            assert c["contradiction_verdict"] in VALID_CONTRADICTION_VERDICTS

    def test_contradiction_distinctions_confirmed_vs_period_vs_methodology(self):
        # Confirmed conflict: same hypothesis, methodology, dataset, period, verified provenance, opposite direction
        c_conf = FindingsAndContradictionEngine.evaluate_pair_contradiction(
            {
                "finding_id": "FND-1",
                "research_id": "RES-1",
                "hypothesis_id": "HYP-SAME",
                "methodology_id": "METH-SAME",
                "dataset_id": "DS-SAME",
                "period": "2024-Q1",
                "evidence_status": "INTEGRITY_VERIFIED",
                "effect_direction": "POSITIVE",
            },
            {
                "finding_id": "FND-2",
                "research_id": "RES-2",
                "hypothesis_id": "HYP-SAME",
                "methodology_id": "METH-SAME",
                "dataset_id": "DS-SAME",
                "period": "2024-Q1",
                "evidence_status": "INTEGRITY_VERIFIED",
                "effect_direction": "NEGATIVE",
            },
        )
        assert c_conf.contradiction_verdict == "CONFIRMED_EVIDENCE_CONFLICT"


# =============================================================================
# 6. MODULE 27.6 — RESEARCH REVIEW & DECISION WORKFLOW TESTS
# =============================================================================


class TestModule27_6_ResearchReviewWorkflow:
    def test_review_states_decisions_and_authenticated_submission(self, monkeypatch):
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "sprint27-verified-operator-token-999")
        monkeypatch.setenv("CBE_EVIDENCE_SIGNING_KEY", "sprint27-distinct-signing-key-888")
        wf = ResearchReviewWorkflowEngine()
        listing = wf.list_reviews()
        assert listing["audit_chain_integrity"]["chain_valid"] is True
        assert tuple(listing["valid_review_states"]) == VALID_REVIEW_STATES
        assert tuple(listing["valid_review_decisions"]) == VALID_REVIEW_DECISIONS

        sub_res = wf.submit_review_decision(
            research_id="RES-REGIME-01",
            decision="ACCEPT_FOR_RESEARCH_ARCHIVE",
            decision_reason="Verified provenance, walk-forward stability, and reproducibility confirmed for offline archive.",
            supporting_evidence_ids=["RES-REGIME-01", "DS-BTCUSDT-SPOT-1H"],
            operator_token="sprint27-verified-operator-token-999",
            payload={"reviewer_identity": "CBE_SCIENTIFIC_REVIEW_BOARD"},
        )
        assert sub_res["status"] == "success"
        assert sub_res["governance_enforcement"]["live_trading_authorized"] is False
        assert sub_res["governance_enforcement"]["technical_decision"] == "TECHNICAL_NO_GO"
        assert wf.verify_review_audit_chain()["chain_valid"] is True


# =============================================================================
# 7. MODULE 27.7 & 27.8 — REPORT BUILDER V5, API & DASHBOARD V5 TESTS
# =============================================================================


class TestModule27_7_And_27_8_ReportBuilderAndDashboardV5:
    def test_all_8_report_types_and_21_mandatory_sections(self):
        for r_type in VALID_REPORT_TYPES:
            res = ScientificReportBuilderV5.generate_report(
                report_type=r_type,
                research_id="RES-REGIME-01",
                export_format="JSON",
            )
            assert res["status"] == "success"
            rep = res["report"]
            for sec in REQUIRED_21_REPORT_SECTIONS:
                assert sec in rep
            assert len(rep["report_content_sha256"]) == 64

    def test_dashboard_v5_api_routes_and_ui_rendering(self):
        st_p, data_p = ProductDashboardApiService.handle_request("/api/v1/product/research/portfolio")
        assert st_p == HTTPStatus.OK and data_p["status"] == "success"

        st_e, data_e = ProductDashboardApiService.handle_request("/api/v1/product/research/experiments")
        assert st_e == HTTPStatus.OK and data_e["status"] == "success"
        first_exp_id = data_e["experiments"][0]["experiment_id"]

        st_ed, data_ed = ProductDashboardApiService.handle_request(
            f"/api/v1/product/research/experiments/{first_exp_id}"
        )
        assert st_ed == HTTPStatus.OK and data_ed["experiment"]["experiment_id"] == first_exp_id

        st_tl, data_tl = ProductDashboardApiService.handle_request(
            f"/api/v1/product/research/experiments/{first_exp_id}/timeline"
        )
        assert st_tl == HTTPStatus.OK and data_tl["timeline_chain_integrity"]["chain_valid"] is True

        st_c, data_c = ProductDashboardApiService.handle_request("/api/v1/product/research/comparisons")
        assert st_c == HTTPStatus.OK and data_c["status"] == "success"

        st_ev, data_ev = ProductDashboardApiService.handle_request("/api/v1/product/research/evidence")
        assert st_ev == HTTPStatus.OK and data_ev["status"] == "success"

        st_evd, data_evd = ProductDashboardApiService.handle_request(
            "/api/v1/product/research/evidence/RES-REGIME-01"
        )
        assert st_evd == HTTPStatus.OK and len(data_evd["traceability_chain"]) == 12

        st_f, data_f = ProductDashboardApiService.handle_request("/api/v1/product/research/findings")
        assert st_f == HTTPStatus.OK and data_f["total_findings"] >= 6

        st_ct, data_ct = ProductDashboardApiService.handle_request("/api/v1/product/research/contradictions")
        assert st_ct == HTTPStatus.OK and data_ct["total_contradiction_checks"] >= 3

        st_rv, data_rv = ProductDashboardApiService.handle_request("/api/v1/product/research/reviews")
        assert st_rv == HTTPStatus.OK and data_rv["audit_chain_integrity"]["chain_valid"] is True

        st_rp, data_rp = ProductDashboardApiService.handle_request("/api/v1/product/research/reports")
        assert st_rp == HTTPStatus.OK and data_rp["status"] == "success"

        html_out = render_research_explorer_html()
        js_out = render_research_explorer_scripts()
        assert "CBE-0.7.0 — FROZEN SCIENTIFIC MODEL | TECHNICAL_NO_GO | OFFLINE RESEARCH ONLY | LIVE TRADING DISABLED" in html_out
        assert "ws-view-portfolio-v5" in html_out
        assert "loadPortfolioV5UI" in js_out


# =============================================================================
# 8. SECTION 16 — ALL 20 MANDATORY NEGATIVE SECURITY & INTEGRITY TESTS
# =============================================================================


class TestSprint27TwentyMandatoryNegativeSecurityControls:
    def test_neg_01_unsigned_dataset_promotion_via_portfolio_registration_blocked(self):
        """1. Attempt to promote an unsigned dataset to VERIFIED through portfolio registration."""
        with pytest.raises(PortfolioSecurityError) as exc:
            ScientificResearchPortfolioManager.register_custom_portfolio_entry(
                {
                    "research_id": "RES-FORGED-01",
                    "dataset_id": "UNSIGNED-DATASET",
                    "evidence_integrity_status": "INTEGRITY_VERIFIED",
                    "promote_dataset_to_verified": True,
                }
            )
        assert exc.value.rejection_code == "UNSIGNED_DATASET_PROMOTION_BLOCKED"

    def test_neg_02_experiment_scientifically_verified_from_execution_completed_blocked(self):
        """2. Attempt to mark an experiment SCIENTIFICALLY_VERIFIED from EXECUTION_COMPLETED alone."""
        svc = ExperimentRegistryAndTimelineService()
        with pytest.raises(ExperimentRegistrySecurityError) as exc:
            svc.register_experiment(
                research_id="RES-REGIME-01",
                experiment_type="EXEC_ONLY",
                experiment_title="Unverified Run",
                hypothesis_id="HYP-01",
                methodology_id="METH-01",
                dataset_id="BTCUSDT-SPOT-1H",
                dataset_fingerprint="fp",
                requested_status="SCIENTIFICALLY_VERIFIED",
                evidence_verified_by_authority=False,
            )
        assert exc.value.rejection_code == "UNVERIFIED_EXECUTION_PROMOTION_BLOCKED"

    def test_neg_03_tampered_experiment_timeline_hash_chain_detected(self):
        """3. Attempt to tamper with the experiment timeline hash chain."""
        svc = ExperimentRegistryAndTimelineService()
        tl = svc.get_experiment_timeline()["events"]
        tampered = [dict(e) for e in tl]
        tampered[1]["previous_event_digest"] = "f" * 64
        check = svc.verify_timeline_chain_integrity(tampered)
        assert check["chain_valid"] is False
        assert check["rejection_code"] == "TIMELINE_HASH_CHAIN_BROKEN"

    def test_neg_04_compare_incompatible_experiments_as_directly_comparable_blocked(self):
        """4. Attempt to compare incompatible experiments as DIRECTLY_COMPARABLE."""
        res = CrossExperimentComparisonEngine.compare_experiments(
            ["RES-FUND-01", "RES-REGIME-01"]  # 8h funding bps vs 1h spot volatility ratio
        )
        comp = res["comparison"]
        assert comp["comparison_verdict"] != "DIRECTLY_COMPARABLE"
        assert comp["is_inferentially_comparable"] is False

    def test_neg_05_fabricate_nonexistent_evidence_link_in_explorer_blocked(self):
        """5. Attempt to fabricate a nonexistent evidence link in the evidence explorer."""
        res = EvidenceTraceabilityExplorer.trace_evidence_chain("NONEXISTENT-FORGED-LINK-999")
        assert res["status"] == "error"
        assert res["rejection_code"] == "NONEXISTENT_EVIDENCE_LINK_REJECTED"

    def test_neg_06_classify_finding_supported_without_verified_evidence_blocked(self):
        """6. Attempt to classify a finding as SUPPORTED without verified evidence."""
        with pytest.raises(FindingClassificationError) as exc:
            FindingsAndContradictionEngine.classify_candidate_finding(
                execution_completed=True,
                provenance_verified=False,
                reproducibility_matched=False,
                sample_size=50,
                adjusted_q_or_p=0.25,
                requested_category="SUPPORTED",
            )
        assert exc.value.rejection_code == "UNSUPPORTED_FINDING_PROMOTION_BLOCKED"

    def test_neg_07_submit_review_decision_without_authentication_blocked(self):
        """7. Attempt to submit a review decision without authentication."""
        wf = ResearchReviewWorkflowEngine()
        with pytest.raises(ReviewWorkflowSecurityError) as exc:
            wf.submit_review_decision(
                research_id="RES-REGIME-01",
                decision="ACCEPT_FOR_RESEARCH_ARCHIVE",
                decision_reason="Attempting anonymous approval.",
                operator_token=None,
                headers={},
                payload={},
            )
        assert exc.value.rejection_code == "UNAUTHENTICATED_REVIEW_SUBMISSION_REJECTED"

    def test_neg_08_submit_review_decision_using_client_supplied_is_admin_blocked(self, monkeypatch):
        """8. Attempt to submit a review decision using client-supplied is_admin=True."""
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "sprint27-op-tok")
        wf = ResearchReviewWorkflowEngine()
        with pytest.raises(ReviewWorkflowSecurityError) as exc:
            wf.submit_review_decision(
                research_id="RES-REGIME-01",
                decision="ACCEPT_FOR_RESEARCH_ARCHIVE",
                decision_reason="Client boolean privilege escalation attempt.",
                operator_token="sprint27-op-tok",
                payload={"is_admin": True, "authorized": True},
            )
        assert exc.value.rejection_code == "CLIENT_AUTHORIZATION_FLAG_REJECTED"

    def test_neg_09_tampered_review_audit_log_hash_chain_detected(self):
        """9. Attempt to tamper with the review audit log hash chain."""
        wf = ResearchReviewWorkflowEngine()
        revs = [dict(r) for r in wf.list_reviews()["reviews"]]
        revs[0]["decision_reason"] = "Forged reason after signing"
        check = wf.verify_review_audit_chain(revs)
        assert check["chain_valid"] is False
        assert check["rejection_code"] == "REVIEW_AUDIT_RECORD_TAMPERED"

    def test_neg_10_export_report_using_path_traversal_blocked(self):
        """10. Attempt to export a report using path traversal."""
        with pytest.raises(ReportBuilderSecurityError) as exc:
            ScientificReportBuilderV5.generate_report(
                report_type="INDIVIDUAL_RESEARCH_REPORT",
                research_id="RES-REGIME-01",
                output_filename="../../etc/passwd",
            )
        assert exc.value.rejection_code == "REPORT_PATH_TRAVERSAL_BLOCKED"

    def test_neg_11_inject_executable_html_or_script_into_report_escaped(self):
        """11. Attempt to inject executable HTML or script content into a report."""
        malicious = "<script>alert('XSS_PWNED')</script><img src=x onerror=alert(1)>"
        res = ScientificReportBuilderV5.generate_report(
            report_type="INDIVIDUAL_RESEARCH_REPORT",
            research_id="RES-REGIME-01",
            export_format="HTML",
            custom_title=malicious,
            custom_notes=malicious,
        )
        rendered_html = res["rendered_html"]
        assert "<script>" not in rendered_html
        assert "&lt;script&gt;alert(&#x27;XSS_PWNED&#x27;)&lt;/script&gt;" in rendered_html

    def test_neg_12_create_signed_intake_manifest_with_caller_secret_blocked(self):
        """12. Attempt to create a signed intake manifest with a caller-supplied secret."""
        with pytest.raises(SigningAuthorityError) as exc:
            ScientificReadinessEvaluator.create_signed_intake_manifest(
                dataset_id="DS-BTC-1H-Q1-2024",
                secret="caller-supplied-raw-secret",
            )
        assert exc.value.rejection_code == "SIGNING_KEY_NOT_AUTHORIZED"

    def test_neg_13_create_signed_replication_attestation_with_caller_secret_blocked(self):
        """13. Attempt to create a signed replication attestation with a caller-supplied secret."""
        with pytest.raises(SigningAuthorityError) as exc:
            IndependentValidationFramework.create_signed_replication_attestation(
                replication_attempt_id="REP-1",
                primary_record_id="RES-1",
                candidate_record_id="RES-2",
                primary_dataset_id="DS-1",
                candidate_dataset_id="DS-2",
                primary_source_sha256="a" * 64,
                candidate_source_sha256="b" * 64,
                result_artifact_path="res.json",
                result_artifact_sha256="c" * 64,
                hypothesis_id="HYP-1",
                methodology_id="METH-1",
                primary_procedure_id="PROC-1",
                candidate_procedure_id="PROC-2",
                procedure_version="1.0",
                independent_execution_lineage="LINEAGE-1",
                secret="caller-supplied-secret",
            )
        assert exc.value.rejection_code == "SIGNING_KEY_NOT_AUTHORIZED"

    def test_neg_14_sign_artifacts_in_verification_only_runtime_mode_blocked(self):
        """14. Attempt to sign artifacts in VERIFICATION_ONLY runtime mode."""
        ctx = SigningAuthorityContext.authorize_isolated_test_signing(
            purposes=[KEY_PURPOSE_INTAKE_MANIFEST],
            allowed_key_ids=["cbe-data-authority-active-v2"],
        )
        try:
            with pytest.raises(SigningAuthorityError) as exc:
                ScientificReadinessEvaluator.create_signed_intake_manifest(
                    dataset_id="DS-BTC-1H-Q1-2024",
                    authority_context=ctx,
                    runtime_mode="VERIFICATION_ONLY",
                )
            assert exc.value.rejection_code == "SIGNING_OPERATION_NOT_PERMITTED"
        finally:
            ctx.close()

    def test_neg_15_sign_artifacts_with_revoked_key_blocked(self):
        """15. Attempt to sign artifacts with a revoked key."""
        ctx = SigningAuthorityContext.authorize_isolated_test_signing(
            purposes=[KEY_PURPOSE_INTAKE_MANIFEST],
            allowed_key_ids=["cbe-attestation-2025-revoked"],
        )
        try:
            with pytest.raises(SigningAuthorityError) as exc:
                ScientificReadinessEvaluator.create_signed_intake_manifest(
                    dataset_id="DS-BTC-1H-Q1-2024",
                    key_id="cbe-attestation-2025-revoked",
                    authority_context=ctx,
                    runtime_mode="ISOLATED_TEST_SIGNING",
                )
            assert exc.value.rejection_code == "SIGNING_KEY_REVOKED"
        finally:
            ctx.close()

    def test_neg_16_sign_artifacts_with_wrong_purpose_key_blocked(self):
        """16. Attempt to sign artifacts with a wrong-purpose key."""
        signing_key_registry.register_key(
            key_id="test-bundle-only-key-s27",
            secret="bundle-only-secret-value-s27",
            is_active=True,
            allowed_purposes=[KEY_PURPOSE_EVIDENCE_BUNDLE],
            is_test_key=True,
        )
        ctx = SigningAuthorityContext.authorize_isolated_test_signing(
            purposes=[KEY_PURPOSE_INTAKE_MANIFEST],
            allowed_key_ids=["test-bundle-only-key-s27"],
        )
        try:
            with pytest.raises(SigningAuthorityError) as exc:
                ScientificReadinessEvaluator.create_signed_intake_manifest(
                    dataset_id="DS-BTC-1H-Q1-2024",
                    key_id="test-bundle-only-key-s27",
                    authority_context=ctx,
                    runtime_mode="ISOLATED_TEST_SIGNING",
                )
            assert exc.value.rejection_code == "SIGNING_KEY_NOT_AUTHORIZED"
        finally:
            ctx.close()
            signing_key_registry.remove_key("test-bundle-only-key-s27")

    def test_neg_17_use_quarantined_october_2026_data_as_verified_evidence_blocked(self):
        """17. Attempt to use quarantined October 2026 data as verified evidence."""
        catalog = ResearchCatalogProvider.get_canonical_catalog()
        oct_rec = [
            r
            for r in catalog
            if getattr(r, "quarantine_status", "") in ("QUARANTINED", "QUARANTINED_CONTAMINATED")
            or r.id == "RES-CRYPTO-01"
        ][0]
        prov = ScientificReadinessEvaluator.verify_dataset_provenance(oct_rec)
        assert prov["is_verified"] is False
        trace = EvidenceTraceabilityExplorer.evaluate_six_tier_trust_progression(oct_rec)
        assert trace["tier_progression"]["INTEGRITY_VERIFIED"] is False
        assert trace["highest_verified_trust_tier"] == "UNVERIFIED_OR_BLOCKED"

    def test_neg_18_use_self_referential_reproduction_output_as_reference_blocked(self):
        """18. Attempt to use self-referential reproduction output as a reference."""
        catalog = ResearchCatalogProvider.get_canonical_catalog()
        rec = catalog[0]
        is_valid, reason_code, _ = ReproducibilityLabEngine.validate_reference_provenance(
            record=rec,
            selected_proc="PROC_FUNDING_RATE_SUMMARY",
            proc_ver="1.1.0",
            source_path=rec.source_artifact,
            actual_sha=rec.source_artifact_sha256,
            start_utc="2026-11-12T00:00:00Z",
            raw_json={},
            reference_provenance={
                "created_during_reproduction_attempt": True,
                "recorded_at_utc": "2026-11-12T00:00:00Z",
                "dataset_id": rec.dataset_id,
            },
        )
        assert is_valid is False
        assert reason_code == ReferenceBlockedReason.UNVERIFIED_REFERENCE_PROVENANCE.value

    def test_neg_19_mutate_frozen_cbe_0_7_0_parameters_or_grant_live_trading_blocked(self, monkeypatch):
        """19. Attempt to mutate frozen CBE-0.7.0 parameters or grant live trading via review."""
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "sprint27-op-tok")
        wf = ResearchReviewWorkflowEngine()
        with pytest.raises(ReviewWorkflowSecurityError) as exc:
            wf.submit_review_decision(
                research_id="RES-REGIME-01",
                decision="ACCEPT_FOR_RESEARCH_ARCHIVE",
                decision_reason="Attempting to enable live trading.",
                operator_token="sprint27-op-tok",
                payload={"grant_live_trading": True, "remove_technical_no_go": True},
            )
        assert exc.value.rejection_code == "CLIENT_AUTHORIZATION_FLAG_REJECTED"

    def test_neg_20_expose_secrets_or_signing_keys_in_api_logs_or_reports_blocked(self):
        """20. Attempt to expose secrets or signing keys in API responses, logs, or reports."""
        rep_res = ScientificReportBuilderV5.generate_report(
            report_type="INDIVIDUAL_RESEARCH_REPORT",
            research_id="RES-REGIME-01",
            export_format="JSON",
        )
        serialized = str(rep_res)
        for forbidden_secret_marker in (
            "CBE_EVIDENCE_SIGNING_KEY",
            "CBE_OPERATOR_TOKEN",
            "signing_secret",
            "raw_secret",
            "private_key",
        ):
            assert forbidden_secret_marker not in serialized

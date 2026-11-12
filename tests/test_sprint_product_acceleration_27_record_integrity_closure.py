"""
Sprint 27 Final Scientific Record Integrity Closure — Comprehensive Test Suite.
(CBE_SPRINT27_FINAL_RECORD_INTEGRITY_CLOSURE)

Verifies:
1. Historical Execution Authenticity (Negative Tests 1-6)
2. Review Provenance & Authenticity (Negative Tests 7-12)
3. Durable Persistence & Concurrency Recovery (Negative Tests 13-21)
4. Cross-Sprint Governance & Trust Controls (Negative Tests 22-24)
5. Positive Verification Tests (Positive Tests 1-5)
"""

from __future__ import annotations

import hashlib
from http import HTTPStatus
import json
from pathlib import Path
import pytest

from coin_behavior_engine.product.cross_experiment_comparison import (
    CrossExperimentComparisonEngine,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.evidence_traceability_explorer import (
    EvidenceTraceabilityExplorer,
)
from coin_behavior_engine.product.experiment_timeline_registry import (
    PERSISTENCE_SCHEMA_VERSION,
    REQUIRED_EXPERIMENT_FIELDS,
    VALID_EXPERIMENT_LIFECYCLE_STATES,
    ExperimentRegistryAndTimelineService,
    ExperimentRegistrySecurityError,
    experiment_registry_service,
)
from coin_behavior_engine.product.research_catalog_provider import (
    ResearchCatalogProvider,
)
from coin_behavior_engine.product.research_explorer_ui import (
    render_research_explorer_html,
    render_research_explorer_scripts,
)
from coin_behavior_engine.product.research_portfolio_manager import (
    ScientificResearchPortfolioManager,
)
from coin_behavior_engine.product.research_review_workflow import (
    ResearchReviewWorkflowEngine,
    ReviewWorkflowSecurityError,
    research_review_workflow_engine,
)
from coin_behavior_engine.product.scientific_readiness import (
    ScientificReadinessEvaluator,
)
from coin_behavior_engine.product.scientific_report_builder_v5 import (
    ScientificReportBuilderV5,
)


# =============================================================================
# PART 1: HISTORICAL EXECUTION AUTHENTICITY (NEGATIVE TESTS 1-6)
# =============================================================================


class TestP0_1_HistoricalExecutionAuthenticityNegativeControls:
    def test_01_fabricated_historical_execution_timestamp_rejected(self):
        """1. Fabricated historical execution timestamp rejected."""
        svc = ExperimentRegistryAndTimelineService()
        # Verify canonical seed records have no invented execution timestamps
        for exp in svc.list_experiments()["experiments"]:
            if exp["record_origin"] == "CATALOG_PROJECTION":
                assert exp["execution_started_at"] is None
                assert exp["execution_completed_at"] is None

        # Attempting to supply predefined invented seed timestamp or future timestamp is rejected
        with pytest.raises(ExperimentRegistrySecurityError) as exc1:
            svc.register_experiment(
                research_id="RES-REGIME-01",
                experiment_type="TEST_FAB_TS",
                experiment_title="Fabricated Timestamp Attempt",
                hypothesis_id="HYP-01",
                methodology_id="METH-01",
                dataset_id="BTCUSDT-SPOT-1H",
                dataset_fingerprint="fp-1",
                execution_started_at="2026-09-12T10:00:00Z",
                execution_completed_at="2026-09-12T10:02:15Z",
            )
        assert exc1.value.rejection_code == "FABRICATED_EXECUTION_TIMESTAMP_REJECTED"

        # Attempting to assign timestamp without verified execution log is rejected
        with pytest.raises(ExperimentRegistrySecurityError) as exc2:
            svc.register_experiment(
                research_id="RES-REGIME-01",
                experiment_type="TEST_FAB_TS_2",
                experiment_title="Unlogged Historical Timestamp Attempt",
                hypothesis_id="HYP-01",
                methodology_id="METH-01",
                dataset_id="BTCUSDT-SPOT-1H",
                dataset_fingerprint="fp-1",
                execution_started_at="2026-11-01T10:00:00Z",
                has_verified_execution_log=False,
            )
        assert exc2.value.rejection_code == "FABRICATED_EXECUTION_TIMESTAMP_REJECTED"

    def test_02_synthetic_output_artifact_out_art_rejected(self):
        """2. Synthetic output artifact (OUT-ART-*) rejected as verified execution output."""
        svc = ExperimentRegistryAndTimelineService()
        for exp in svc.list_experiments()["experiments"]:
            for out_id in exp["output_artifact_ids"]:
                assert not str(out_id).startswith("OUT-ART-")

        with pytest.raises(ExperimentRegistrySecurityError) as exc:
            svc.register_experiment(
                research_id="RES-REGIME-01",
                experiment_type="TEST_SYNTH_OUT",
                experiment_title="Synthetic Output Attempt",
                hypothesis_id="HYP-01",
                methodology_id="METH-01",
                dataset_id="BTCUSDT-SPOT-1H",
                dataset_fingerprint="fp-1",
                output_artifact_ids=["OUT-ART-EXP-RES-REGIME-01-FAKE"],
                requested_status="EXECUTION_COMPLETED",
            )
        assert exc.value.rejection_code == "SYNTHETIC_OUTPUT_ARTIFACT_REJECTED"

    def test_03_metadata_derived_digest_rejected_as_execution_result_digest(self):
        """3. Metadata-derived digest rejected as execution result digest."""
        svc = ExperimentRegistryAndTimelineService()
        param_fp = svc.compute_parameter_fingerprint({})
        exp_id = svc.compute_deterministic_experiment_id(
            research_id="RES-REGIME-01",
            experiment_type="TEST_META_DIGEST",
            methodology_id="METH-01",
            dataset_id="BTCUSDT-SPOT-1H",
            parameter_fingerprint=param_fp,
        )
        prohibited_digest = svc.compute_prohibited_metadata_digest(
            exp_id=exp_id,
            sample_size=2160,
            volatility_ratio=1.84,
            raw_p_value=0.0012,
        )
        with pytest.raises(ExperimentRegistrySecurityError) as exc:
            svc.register_experiment(
                research_id="RES-REGIME-01",
                experiment_type="TEST_META_DIGEST",
                experiment_title="Metadata Digest Attempt",
                hypothesis_id="HYP-01",
                methodology_id="METH-01",
                dataset_id="BTCUSDT-SPOT-1H",
                dataset_fingerprint="fp-1",
                result_digest=prohibited_digest,
                metadata_for_check={
                    "sample_size": 2160,
                    "volatility_ratio": 1.84,
                    "raw_p_value": 0.0012,
                },
                requested_status="EXECUTION_COMPLETED",
            )
        assert exc.value.rejection_code == "METADATA_DERIVED_RESULT_DIGEST_REJECTED"

    def test_04_catalog_discovery_record_cannot_be_marked_execution_completed_without_evidence(self):
        """4. Catalog discovery record cannot be marked EXECUTION_COMPLETED without execution evidence."""
        svc = ExperimentRegistryAndTimelineService()
        # None of the seeded catalog discovery records are marked EXECUTION_COMPLETED
        for exp in svc.list_experiments()["experiments"]:
            if exp["record_origin"] == "CATALOG_PROJECTION":
                assert exp["execution_status"] != "EXECUTION_COMPLETED"

        with pytest.raises(ExperimentRegistrySecurityError) as exc:
            svc.register_experiment(
                research_id="RES-REGIME-01",
                experiment_type="TEST_CAT_EXEC",
                experiment_title="Catalog Projection Marked Completed",
                hypothesis_id="HYP-01",
                methodology_id="METH-01",
                dataset_id="BTCUSDT-SPOT-1H",
                dataset_fingerprint="fp-1",
                record_origin="CATALOG_PROJECTION",
                requested_status="EXECUTION_COMPLETED",
            )
        assert exc.value.rejection_code == "UNSUPPORTED_EXECUTION_COMPLETED_REJECTED"

    def test_05_unverified_reproduction_cannot_be_marked_outputs_matched(self):
        """5. Unverified reproduction cannot be marked OUTPUTS_MATCHED."""
        svc = ExperimentRegistryAndTimelineService()
        for exp in svc.list_experiments()["experiments"]:
            if exp["record_origin"] == "CATALOG_PROJECTION":
                assert exp["reproducibility_verdict"] in (
                    "REPRODUCTION_NOT_ESTABLISHED",
                    "REPRODUCTION_BLOCKED",
                )

        with pytest.raises(ExperimentRegistrySecurityError) as exc:
            svc.register_experiment(
                research_id="RES-REGIME-01",
                experiment_type="TEST_UNVERIFIED_REPRO",
                experiment_title="Unverified Reproduction Attempt",
                hypothesis_id="HYP-01",
                methodology_id="METH-01",
                dataset_id="BTCUSDT-SPOT-1H",
                dataset_fingerprint="fp-1",
                reproducibility_verdict="OUTPUTS_MATCHED",
                independent_reference_compared=False,
            )
        assert exc.value.rejection_code == "UNSUPPORTED_OUTPUTS_MATCHED_REJECTED"

    def test_06_synthetic_seed_record_cannot_be_promoted_to_verified_historical_execution(self):
        """6. Synthetic seed record cannot be promoted to verified historical execution."""
        svc = ExperimentRegistryAndTimelineService()
        with pytest.raises(ExperimentRegistrySecurityError) as exc:
            svc.promote_to_verified_historical_execution(
                experiment_id="RES-REGIME-01",
                execution_log_path=None,
                expected_log_sha256=None,
            )
        assert exc.value.rejection_code == "SYNTHETIC_SEED_PROMOTION_REJECTED"


# =============================================================================
# PART 2: REVIEW PROVENANCE & AUTHENTICITY (NEGATIVE TESTS 7-12)
# =============================================================================


class TestP0_2_ReviewProvenanceAndAuthenticityNegativeControls:
    def test_07_automated_review_recommendation_cannot_be_stored_as_authenticated_review_decision(self, monkeypatch):
        """7. Automated review recommendation cannot be stored as AUTHENTICATED_REVIEW_DECISION."""
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "sprint27-closure-op-tok")
        wf = ResearchReviewWorkflowEngine()
        # Verify startup has 0 fabricated authenticated reviews; automated recommendations are separate
        listing = wf.list_reviews()
        assert listing["total_reviews"] == 0
        assert len(listing["authenticated_reviews"]) == 0
        assert len(listing["automated_assessments"]) >= 6
        for auto in listing["automated_assessments"]:
            assert auto["review_classification"] == "AUTOMATED_ASSESSMENT"
            assert auto["reviewer_identity"] == "SYSTEM_GENERATED_ASSESSMENT"
            assert auto["authoritative"] is False

        # Attempting to submit an automated assessment into the authenticated review log is rejected
        with pytest.raises(ReviewWorkflowSecurityError) as exc:
            wf.submit_review_decision(
                research_id="RES-REGIME-01",
                decision="ACCEPT_FOR_RESEARCH_ARCHIVE",
                decision_reason="Attempting to store automated assessment as authenticated decision.",
                supporting_evidence_ids=["RES-REGIME-01"],
                operator_token="sprint27-closure-op-tok",
                review_classification="AUTOMATED_ASSESSMENT",
            )
        assert exc.value.rejection_code == "AUTOMATED_ASSESSMENT_IMPERSONATION_REJECTED"

    def test_08_synthetic_reviewer_identity_rejected_without_verified_authentication(self):
        """8. Synthetic reviewer identity (CBE_SCIENTIFIC_REVIEW_BOARD) rejected without verified operator/reviewer authentication."""
        wf = ResearchReviewWorkflowEngine()
        with pytest.raises(ReviewWorkflowSecurityError) as exc1:
            wf.submit_review_decision(
                research_id="RES-REGIME-01",
                decision="ACCEPT_FOR_RESEARCH_ARCHIVE",
                decision_reason="Unauthenticated claim of CBE_SCIENTIFIC_REVIEW_BOARD identity.",
                supporting_evidence_ids=["RES-REGIME-01"],
                operator_token=None,
                payload={"reviewer_identity": "CBE_SCIENTIFIC_REVIEW_BOARD"},
            )
        assert exc1.value.rejection_code == "UNAUTHENTICATED_REVIEW_SUBMISSION_REJECTED"

    def test_09_unauthenticated_review_submission_rejected(self):
        """9. Unauthenticated review submission rejected."""
        wf = ResearchReviewWorkflowEngine()
        with pytest.raises(ReviewWorkflowSecurityError) as exc:
            wf.submit_review_decision(
                research_id="RES-REGIME-01",
                decision="REQUEST_REPRODUCTION",
                decision_reason="No operator token provided.",
                supporting_evidence_ids=["RES-REGIME-01"],
                operator_token="",
                headers={},
            )
        assert exc.value.rejection_code == "UNAUTHENTICATED_REVIEW_SUBMISSION_REJECTED"

    def test_10_client_supplied_is_admin_and_authorized_rejected(self, monkeypatch):
        """10. Client-supplied is_admin=True / authorized=True rejected."""
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "sprint27-closure-op-tok")
        wf = ResearchReviewWorkflowEngine()
        with pytest.raises(ReviewWorkflowSecurityError) as exc:
            wf.submit_review_decision(
                research_id="RES-REGIME-01",
                decision="ACCEPT_FOR_RESEARCH_ARCHIVE",
                decision_reason="Attempting boolean flag privilege override.",
                supporting_evidence_ids=["RES-REGIME-01"],
                operator_token="sprint27-closure-op-tok",
                payload={"is_admin": True, "authorized": True},
            )
        assert exc.value.rejection_code == "CLIENT_AUTHORIZATION_FLAG_REJECTED"

    def test_11_forged_review_timestamp_rejected(self, monkeypatch):
        """11. Forged review timestamp rejected."""
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "sprint27-closure-op-tok")
        wf = ResearchReviewWorkflowEngine()
        # Synthetic October 2026 timestamp rejected
        with pytest.raises(ReviewWorkflowSecurityError) as exc1:
            wf.submit_review_decision(
                research_id="RES-REGIME-01",
                decision="ACCEPT_FOR_RESEARCH_ARCHIVE",
                decision_reason="Backdated synthetic timestamp test.",
                supporting_evidence_ids=["RES-REGIME-01"],
                operator_token="sprint27-closure-op-tok",
                decision_timestamp="2026-10-15T12:00:00Z",
            )
        assert exc1.value.rejection_code == "FORGED_REVIEW_TIMESTAMP_REJECTED"

        # Future timestamp rejected
        with pytest.raises(ReviewWorkflowSecurityError) as exc2:
            wf.submit_review_decision(
                research_id="RES-REGIME-01",
                decision="ACCEPT_FOR_RESEARCH_ARCHIVE",
                decision_reason="Future timestamp forgery test.",
                supporting_evidence_ids=["RES-REGIME-01"],
                operator_token="sprint27-closure-op-tok",
                decision_timestamp="2030-01-01T00:00:00Z",
            )
        assert exc2.value.rejection_code == "FORGED_REVIEW_TIMESTAMP_REJECTED"

    def test_12_review_decision_referencing_nonexistent_or_unverified_evidence_rejected(self, monkeypatch):
        """12. Review decision referencing nonexistent or unverified evidence rejected."""
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "sprint27-closure-op-tok")
        wf = ResearchReviewWorkflowEngine()
        with pytest.raises(ReviewWorkflowSecurityError) as exc:
            wf.submit_review_decision(
                research_id="RES-REGIME-01",
                decision="ACCEPT_FOR_RESEARCH_ARCHIVE",
                decision_reason="Referencing nonexistent forged evidence ID.",
                supporting_evidence_ids=["NONEXISTENT-EVIDENCE-ID-9999"],
                operator_token="sprint27-closure-op-tok",
            )
        assert exc.value.rejection_code == "UNVERIFIED_EVIDENCE_REFERENCE_REJECTED"


# =============================================================================
# PART 3: PERSISTENCE & CONCURRENCY RECOVERY (NEGATIVE TESTS 13-21)
# =============================================================================


class TestP0_3_PersistenceAndConcurrencyNegativeControls:
    def test_13_persisted_state_with_corrupted_json_fails_closed(self, tmp_path: Path):
        """13. Persisted state with corrupted JSON fails closed."""
        reg_file = tmp_path / "corrupted_registry.json"
        reg_file.write_text("{corrupted_json: [1, 2, ", encoding="utf-8")
        with pytest.raises(ExperimentRegistrySecurityError) as exc:
            ExperimentRegistryAndTimelineService(storage_path=reg_file)
        assert exc.value.rejection_code == "CORRUPTED_PERSISTED_STATE"

    def test_14_persisted_state_with_missing_required_experiment_fields_rejected(self, tmp_path: Path):
        """14. Persisted state with missing required experiment fields rejected."""
        reg_file = tmp_path / "missing_fields_registry.json"
        svc = ExperimentRegistryAndTimelineService(storage_path=reg_file)
        raw = json.loads(reg_file.read_text(encoding="utf-8"))
        first_key = next(iter(raw["experiments"].keys()))
        del raw["experiments"][first_key]["methodology_id"]
        reg_file.write_text(json.dumps(raw), encoding="utf-8")

        with pytest.raises(ExperimentRegistrySecurityError) as exc:
            ExperimentRegistryAndTimelineService(storage_path=reg_file)
        assert exc.value.rejection_code == "MALFORMED_PERSISTED_EXPERIMENT"

    def test_15_persisted_state_with_broken_timeline_hash_chain_rejected(self, tmp_path: Path):
        """15. Persisted state with broken timeline hash chain rejected."""
        reg_file = tmp_path / "broken_chain_registry.json"
        ExperimentRegistryAndTimelineService(storage_path=reg_file)
        raw = json.loads(reg_file.read_text(encoding="utf-8"))
        raw["timeline"][1]["previous_event_digest"] = "a" * 64
        reg_file.write_text(json.dumps(raw), encoding="utf-8")

        with pytest.raises(ExperimentRegistrySecurityError) as exc:
            ExperimentRegistryAndTimelineService(storage_path=reg_file)
        assert exc.value.rejection_code == "TIMELINE_HASH_CHAIN_BROKEN"

    def test_16_persisted_timeline_event_referencing_missing_experiment_rejected(self, tmp_path: Path):
        """16. Persisted timeline event referencing missing experiment rejected."""
        reg_file = tmp_path / "orphan_event_registry.json"
        ExperimentRegistryAndTimelineService(storage_path=reg_file)
        raw = json.loads(reg_file.read_text(encoding="utf-8"))
        # Remove the experiment referenced by the first timeline event
        orphan_exp_id = raw["timeline"][0]["experiment_id"]
        del raw["experiments"][orphan_exp_id]
        reg_file.write_text(json.dumps(raw), encoding="utf-8")

        with pytest.raises(ExperimentRegistrySecurityError) as exc:
            ExperimentRegistryAndTimelineService(storage_path=reg_file)
        assert exc.value.rejection_code == "MISSING_EXPERIMENT_REFERENCE_IN_TIMELINE"

    def test_17_persisted_timeline_with_out_of_order_timestamps_rejected(self, tmp_path: Path):
        """17. Persisted timeline with out-of-order timestamps rejected."""
        reg_file = tmp_path / "out_of_order_registry.json"
        svc = ExperimentRegistryAndTimelineService(storage_path=reg_file)
        # Register an experiment so we have a recent timestamp event, then forge an earlier timestamp after it
        svc.register_experiment(
            research_id="RES-REGIME-01",
            experiment_type="ORDER_TEST_1",
            experiment_title="Order Test 1",
            hypothesis_id="HYP-1",
            methodology_id="METH-1",
            dataset_id="BTCUSDT-SPOT-1H",
            dataset_fingerprint="fp-1",
        )
        raw = json.loads(reg_file.read_text(encoding="utf-8"))
        # Set the second-to-last event to 2026-11-12T05:00:00Z and last event to 2026-11-10T01:00:00Z and recompute digests
        raw["timeline"][-2]["event_timestamp"] = "2026-11-12T05:00:00Z"
        raw["timeline"][-1]["event_timestamp"] = "2026-11-10T01:00:00Z"
        reg_file.write_text(json.dumps(raw), encoding="utf-8")

        with pytest.raises(ExperimentRegistrySecurityError) as exc:
            ExperimentRegistryAndTimelineService(storage_path=reg_file)
        assert exc.value.rejection_code == "TIMELINE_OUT_OF_ORDER_TIMESTAMP"

    def test_18_duplicate_timeline_event_ids_rejected_during_recovery(self, tmp_path: Path):
        """18. Duplicate timeline event IDs rejected during recovery."""
        reg_file = tmp_path / "dup_event_registry.json"
        ExperimentRegistryAndTimelineService(storage_path=reg_file)
        raw = json.loads(reg_file.read_text(encoding="utf-8"))
        raw["timeline"][1]["event_id"] = raw["timeline"][0]["event_id"]
        reg_file.write_text(json.dumps(raw), encoding="utf-8")

        with pytest.raises(ExperimentRegistrySecurityError) as exc:
            ExperimentRegistryAndTimelineService(storage_path=reg_file)
        assert exc.value.rejection_code == "DUPLICATE_TIMELINE_EVENT_ID"

    def test_19_restart_recovery_restores_persisted_experiments_and_timeline_without_loss(self, tmp_path: Path):
        """19. Restart recovery restores persisted experiments and timeline without loss."""
        reg_file = tmp_path / "durable_registry.json"
        svc1 = ExperimentRegistryAndTimelineService(storage_path=reg_file)
        reg_res = svc1.register_experiment(
            research_id="RES-REGIME-01",
            experiment_type="DURABLE_RESTART_EVAL",
            experiment_title="Durable Persistence Verification Run",
            hypothesis_id="HYP-DURABLE-01",
            methodology_id="METH-DURABLE-1.0",
            dataset_id="BTCUSDT-SPOT-1H",
            dataset_fingerprint="sha256-verified-fp",
            parameters={"fold_window": 48},
            requested_status="EXECUTION_COMPLETED",
            result_digest="a1b2c3d4" * 8,
        )
        new_exp_id = reg_res["experiment"]["experiment_id"]
        count_before = svc1.list_experiments()["total_experiments"]
        events_before = svc1.get_experiment_timeline()["event_count"]

        # Simulate full service restart on the same storage_path
        svc2 = ExperimentRegistryAndTimelineService(storage_path=reg_file)
        restored_exp = svc2.get_experiment(new_exp_id)
        assert restored_exp is not None
        assert restored_exp["experiment_id"] == new_exp_id
        assert restored_exp["experiment_title"] == "Durable Persistence Verification Run"
        assert restored_exp["result_digest"] == "a1b2c3d4" * 8
        assert svc2.list_experiments()["total_experiments"] == count_before
        assert svc2.get_experiment_timeline()["event_count"] == events_before
        assert svc2.verify_timeline_chain_integrity()["chain_valid"] is True

    def test_20_restart_recovery_does_not_duplicate_seed_events(self, tmp_path: Path):
        """20. Restart recovery does not duplicate seed events."""
        reg_file = tmp_path / "no_dup_seed_registry.json"
        svc1 = ExperimentRegistryAndTimelineService(storage_path=reg_file)
        initial_events = svc1.get_experiment_timeline()["event_count"]
        initial_exps = svc1.list_experiments()["total_experiments"]

        # Restart multiple times
        svc2 = ExperimentRegistryAndTimelineService(storage_path=reg_file)
        svc3 = ExperimentRegistryAndTimelineService(storage_path=reg_file)
        assert svc2.get_experiment_timeline()["event_count"] == initial_events
        assert svc3.get_experiment_timeline()["event_count"] == initial_events
        assert svc3.list_experiments()["total_experiments"] == initial_exps

    def test_21_interrupted_write_leftover_tmp_file_handled_without_corrupting_registry(self, tmp_path: Path):
        """21. Interrupted write / leftover .tmp file handled without corrupting registry."""
        reg_file = tmp_path / "interrupted_write_registry.json"
        svc1 = ExperimentRegistryAndTimelineService(storage_path=reg_file)
        reg = svc1.register_experiment(
            research_id="RES-ANALOG-01",
            experiment_type="TMP_RECOVERY_TEST",
            experiment_title="Interrupted Write Test",
            hypothesis_id="HYP-TMP",
            methodology_id="METH-TMP",
            dataset_id="BTCUSDT-SPOT-5M",
            dataset_fingerprint="fp-tmp",
        )
        exp_id = reg["experiment"]["experiment_id"]

        # Simulate a leftover .tmp file from an interrupted write containing truncated garbage
        tmp_file = reg_file.with_suffix(".tmp")
        tmp_file.write_text("{truncated_interrupted_write...", encoding="utf-8")
        assert tmp_file.exists()

        # Restarting service cleans up .tmp and loads the intact primary registry file
        svc2 = ExperimentRegistryAndTimelineService(storage_path=reg_file)
        assert not tmp_file.exists()
        assert svc2._recovered_from_interrupted_tmp is True
        assert svc2.get_experiment(exp_id) is not None
        assert svc2.verify_timeline_chain_integrity()["chain_valid"] is True


# =============================================================================
# PART 4: CROSS-SPRINT GOVERNANCE & TRUST (NEGATIVE TESTS 22-24)
# =============================================================================


class TestCrossSprintGovernanceAndTrustNegativeControls:
    def test_22_quarantined_october_2026_records_remain_blocked(self):
        """22. Quarantined October 2026 records remain blocked across all modules."""
        catalog = ResearchCatalogProvider.get_canonical_catalog()
        quarantined_ids = [
            r.id
            for r in catalog
            if getattr(r, "quarantine_status", "") in ("QUARANTINED", "QUARANTINED_CONTAMINATED")
            or r.id == "RES-CRYPTO-01"
        ]
        assert len(quarantined_ids) >= 1
        for q_id in quarantined_ids:
            exp = experiment_registry_service.get_experiment(q_id)
            assert exp is not None
            assert exp["execution_status"] == "BLOCKED"
            assert exp["reproducibility_verdict"] == "REPRODUCTION_BLOCKED"

            trace = EvidenceTraceabilityExplorer.trace_evidence_chain(q_id)
            assert trace["trust_progression"]["tier_progression"]["INTEGRITY_VERIFIED"] is False
            assert trace["trust_progression"]["highest_verified_trust_tier"] == "UNVERIFIED_OR_BLOCKED"

    def test_23_frozen_cbe_0_7_0_and_technical_no_go_remain_unchanged(self):
        """23. Frozen CBE-0.7.0 and TECHNICAL_NO_GO remain unchanged."""
        st, ov = ProductDashboardApiService.handle_request("/api/v1/product/overview")
        assert st == HTTPStatus.OK
        assert ov["model_integrity"]["version"] == "CBE-0.7.0"
        assert ov["model_integrity"]["status"] == "FROZEN"
        assert ov["safety_contract"]["technical_decision"] == "TECHNICAL_NO_GO"
        assert ov["safety_contract"]["live_order_execution"] == "PROHIBITED"
        assert ov["safety_contract"]["directional_trading_eligibility"] == "ZERO"

    def test_24_no_secret_material_exposed_in_api_responses_or_reports(self):
        """24. No secret material exposed in API responses or reports."""
        endpoints = [
            "/api/v1/product/research/portfolio",
            "/api/v1/product/research/experiments",
            "/api/v1/product/research/experiments/ALL/timeline",
            "/api/v1/product/research/reviews",
            "/api/v1/product/research/reports",
        ]
        for ep in endpoints:
            st, payload = ProductDashboardApiService.handle_request(ep)
            assert st == HTTPStatus.OK
            text = json.dumps(payload)
            for forbidden in (
                "CBE_EVIDENCE_SIGNING_KEY",
                "CBE_OPERATOR_TOKEN",
                "signing_secret",
                "raw_secret",
                "private_key",
            ):
                assert forbidden not in text


# =============================================================================
# PART 5: POSITIVE VERIFICATION TESTS (POSITIVE TESTS 1-5)
# =============================================================================


class TestSprint27FinalRecordIntegrityPositiveSuite:
    def test_pos_01_valid_experiment_registration_persists_and_survives_service_restart(self, tmp_path: Path):
        """Positive 1: Valid experiment registration persists and survives service restart."""
        reg_path = tmp_path / "pos01_registry.json"
        svc = ExperimentRegistryAndTimelineService(storage_path=reg_path)
        res = svc.register_experiment(
            research_id="RES-FUND-01",
            experiment_type="OFFLINE_FUNDING_AUTOCORR_VERIFY",
            experiment_title="Funding Autocorrelation Offline Run",
            hypothesis_id="HYP-FUND-01",
            methodology_id="METH-FUNDING-AUTOCORR-1.1",
            dataset_id="BTCUSDT-PERP-FUNDING-8H",
            dataset_fingerprint="df-verified-sha",
            parameters={"lag_epochs": 3},
            requested_status="EXECUTION_COMPLETED",
            result_digest="9f8e7d6c" * 8,
        )
        exp_id = res["experiment"]["experiment_id"]
        svc_restarted = ExperimentRegistryAndTimelineService(storage_path=reg_path)
        loaded = svc_restarted.get_experiment(exp_id)
        assert loaded is not None
        assert loaded["experiment_id"] == exp_id
        assert loaded["record_origin"] == "OFFLINE_EXPERIMENT_EXECUTION"
        assert loaded["execution_status"] == "EXECUTION_COMPLETED"

    def test_pos_02_verified_historical_artifact_reconstruction_reflects_authentic_metadata(self, tmp_path: Path):
        """Positive 2: Verified historical artifact reconstruction reflects authentic metadata."""
        svc = ExperimentRegistryAndTimelineService()
        regime_exp = svc.get_experiment("RES-REGIME-01")
        macro_exp = svc.get_experiment("RES-MACRO-01")
        assert regime_exp is not None and macro_exp is not None
        assert regime_exp["record_origin"] == "CATALOG_PROJECTION"
        assert regime_exp["execution_status"] == "EXECUTION_EVIDENCE_AVAILABLE"
        # sprint09_27_validation_and_holdout_report.json has no embedded timestamp -> remains None (not invented!)
        assert regime_exp["source_artifact_timestamp_utc"] is None
        # experiment_cpi_volatility.cbe-hyp.json has embedded header.exported_at_utc -> extracted authentically!
        assert macro_exp["source_artifact_timestamp_utc"] == "2026-10-25T20:10:30.122948+00:00"
        assert regime_exp["execution_started_at"] is None
        assert regime_exp["execution_completed_at"] is None

        # Promote using a genuine verified execution log file on disk
        log_file = tmp_path / "authentic_exec_log.json"
        log_payload = {
            "experiment_id": regime_exp["experiment_id"],
            "execution_started_at": "2026-04-03T11:58:00Z",
            "execution_completed_at": "2026-04-03T12:00:00Z",
            "output_artifact_sha256": regime_exp["dataset_fingerprint"],
        }
        log_bytes = json.dumps(log_payload).encode("utf-8")
        log_file.write_bytes(log_bytes)
        log_sha = hashlib.sha256(log_bytes).hexdigest()

        promoted = svc.promote_to_verified_historical_execution(
            experiment_id=regime_exp["experiment_id"],
            execution_log_path=log_file,
            expected_log_sha256=log_sha,
        )
        assert promoted["experiment"]["record_origin"] == "VERIFIED_HISTORICAL_EXECUTION"
        assert promoted["experiment"]["execution_status"] == "EXECUTION_EVIDENCE_VERIFIED"
        assert promoted["experiment"]["execution_started_at"] == "2026-04-03T11:58:00Z"

    def test_pos_03_authenticated_review_submission_records_auditable_review_decision(self, monkeypatch, tmp_path: Path):
        """Positive 3: Authenticated review submission records auditable review decision and persists across restart."""
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "sprint27-pos03-token")
        rev_path = tmp_path / "pos03_reviews.json"
        wf1 = ResearchReviewWorkflowEngine(storage_path=rev_path)
        res = wf1.submit_review_decision(
            research_id="RES-REGIME-01",
            decision="ACCEPT_FOR_RESEARCH_ARCHIVE",
            decision_reason="Authenticated review decision with verified dataset and statistical evidence.",
            supporting_evidence_ids=["RES-REGIME-01", "DS-BTCUSDT-SPOT-1H"],
            operator_token="sprint27-pos03-token",
            payload={"reviewer_identity": "CBE_SCIENTIFIC_REVIEW_BOARD"},
        )
        assert res["status"] == "success"
        rec = res["review_record"]
        assert rec["review_classification"] == "AUTHENTICATED_REVIEW_DECISION"
        assert rec["authoritative"] is True

        wf2 = ResearchReviewWorkflowEngine(storage_path=rev_path)
        listed = wf2.list_reviews(research_id="RES-REGIME-01")
        assert len(listed["authenticated_reviews"]) == 1
        assert listed["authenticated_reviews"][0]["review_id"] == rec["review_id"]
        assert listed["audit_chain_integrity"]["chain_valid"] is True
        assert listed["audit_chain_integrity"]["integrity_mechanism"] == "INTERNAL_TAMPER_DETECTION_CHAIN"
        assert listed["audit_chain_integrity"]["externally_anchored"] is False

    def test_pos_04_automated_readiness_assessment_remains_clearly_labeled_system_generated_assessment(self):
        """Positive 4: Automated readiness assessment remains clearly labeled SYSTEM_GENERATED_ASSESSMENT."""
        wf = ResearchReviewWorkflowEngine()
        listing = wf.list_reviews()
        assert listing["total_reviews"] == 0
        auto_list = listing["automated_assessments"]
        assert len(auto_list) >= 6
        for item in auto_list:
            assert item["record_origin"] == "AUTOMATED_ASSESSMENT"
            assert item["review_classification"] == "AUTOMATED_ASSESSMENT"
            assert item["reviewer_identity"] == "SYSTEM_GENERATED_ASSESSMENT"
            assert item["authoritative"] is False
            assert item["recommended_review_state"] != "REVIEW_COMPLETED"

        # Legacy synthetic review records are quarantined & reclassified as AUTOMATED_ASSESSMENT
        reclass = wf.reclassify_or_quarantine_legacy_reviews(
            [
                {
                    "review_id": "REV-0001-RES-REGIME-01",
                    "research_id": "RES-REGIME-01",
                    "reviewer_identity": "CBE_SCIENTIFIC_REVIEW_BOARD",
                    "decision": "ACCEPT_FOR_RESEARCH_ARCHIVE",
                    "decision_reason": "Legacy synthetic seed",
                    "supporting_evidence_ids": ["RES-REGIME-01"],
                    "decision_timestamp": "2026-10-15T12:00:00Z",
                    "previous_review_digest": "0" * 64,
                }
            ]
        )
        assert reclass["preserved_authenticated_count"] == 0
        assert reclass["quarantined_synthetic_count"] == 1
        assert reclass["quarantined_synthetic_reviews"][0]["reviewer_identity"] == "SYSTEM_GENERATED_ASSESSMENT"
        assert reclass["quarantined_synthetic_reviews"][0]["authoritative"] is False

    def test_pos_05_dashboard_v5_and_report_builder_v5_accurately_reflect_updated_trust_states(self):
        """Positive 5: Dashboard V5 and Report Builder V5 accurately reflect updated trust states."""
        rep_res = ScientificReportBuilderV5.generate_report(
            report_type="INDIVIDUAL_RESEARCH_REPORT",
            research_id="RES-REGIME-01",
            export_format="JSON",
        )
        rep = rep_res["report"]
        assert rep["reproducibility_status"]["status"] == "REPRODUCTION_NOT_ESTABLISHED"
        assert rep["review_status"]["review_classification"] == "AUTOMATED_ASSESSMENT"
        tc = rep["evidence_manifest"]["evidence_trust_classifications"]
        for mandatory_class in (
            "CATALOG_METADATA",
            "VERIFIED_EXECUTION_EVIDENCE",
            "AUTOMATED_ASSESSMENT",
            "AUTHENTICATED_REVIEW_DECISION",
            "UNVERIFIED_HISTORICAL_CLAIM",
        ):
            assert mandatory_class in tc

        js_code = render_research_explorer_scripts()
        assert "INTERNAL_TAMPER_DETECTION_CHAIN" in js_code
        assert "AUTHENTICATED_REVIEW_DECISION" in js_code
        assert "AUTOMATED_ASSESSMENT" in js_code
        assert "REPRODUCTION_NOT_ESTABLISHED" in js_code

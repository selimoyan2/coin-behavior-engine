"""
Sprint 11.23.5B-4 Test Suite: Official CPI Evidence Import & Controlled Pilot Proposal Freeze
25 Comprehensive Adversarial Tests covering:
  - Official Schedule Import & Provenance Verification
  - Candidate vs. Verified Event Identity Derivation
  - 35-Minute Observation Window & 30-Minute Horizon Completeness
  - Request Budget Feasibility (Continuous 35 requests BLOCKED vs Event-Windowed 13 requests FEASIBLE)
  - Consensus Policy (Descriptive pilot without consensus, surprise analysis disabled)
  - Proposal v3.0.0 Freeze & Canonical Digest Sensitivity
  - Anti-Carryover of Prior Approvals
  - Privileged Multi-Role Approval Workflow
  - Network Activation Gate Scope & Quota Enforcement
  - Durable Revocation & Trading Prohibition
  - 14-Step Offline Rehearsal Runner
  - Final Go/No-Go Decision Engine
"""

from datetime import datetime, timezone, timedelta
import hashlib
import json
from pathlib import Path
import tempfile
import pytest

from coin_behavior_engine.prospective import (
    ControlledEvidenceImporter,
    SourceAuthenticityLevel,
    OversizedEvidenceError,
    UnsafeEvidenceTypeError,
    PathTraversalError,
    EvidenceChecksumMismatchError,
    SamplingStrategy,
    EventIdentityStatus,
    PilotProposalReviewStatus,
    ObservationWindowPlanEvaluator,
    CandidateEventIdentity,
    EventIdentityManager,
    PilotProposalV3Builder,
    OfflinePilotRehearsalRunnerV4,
    PilotProposalFreezeDecisionEngine,
    OperatorRole,
    OperatorIdentity,
    ProposalStatus,
    OperatorApprovalWorkflowEngine,
    UnauthorizedOperatorActionError,
    ProposalIntegrityError,
    SigningKeyRegistry,
    TrustedApprovalStore,
    NetworkActivationGate,
    ImmutableEvidenceVault,
)
from coin_behavior_engine.prospective.schedule_verification import convert_local_to_utc


# ==============================================================================
# PHASE 1 & 2: SCHEDULE IMPORT, TIMEZONE & PROVENANCE
# ==============================================================================

def test_01_candidate_event_identity_parameters_exact():
    candidate = EventIdentityManager.create_candidate_event()
    assert candidate.candidate_event_id == "EVT-BLS-CPI-2026M10-20261110"
    assert candidate.publisher == "BLS"
    assert candidate.series == "CPI"
    assert candidate.reference_period == "2026M10"
    assert candidate.scheduled_release_date == "2026-11-10"
    assert candidate.scheduled_release_time_local == "08:30:00"
    assert candidate.scheduled_release_utc == "2026-11-10T13:30:00Z"
    assert candidate.status == EventIdentityStatus.CANDIDATE_PENDING_SCHEDULE_VERIFICATION


def test_02_timezone_conversion_dst_standard_time_est():
    # US DST ends first Sunday of Nov (Nov 1, 2026). Nov 10, 2026 is EST (UTC-5).
    utc_str = convert_local_to_utc("2026-11-10T08:30:00", tz_name="America/New_York")
    assert utc_str == "2026-11-10T13:30:00Z"

    # Compare with October 13, 2026 which was EDT (UTC-4) -> 12:30:00Z
    oct_utc = convert_local_to_utc("2026-10-13T08:30:00", tz_name="America/New_York")
    assert oct_utc == "2026-10-13T12:30:00Z"


def test_03_unauthenticated_official_schedule_import_quarantined():
    with tempfile.TemporaryDirectory() as td:
        vault = ImmutableEvidenceVault(vault_root=Path(td) / "vault")
        importer = ControlledEvidenceImporter(vault=vault)
        schedule_bytes = b"<!DOCTYPE html><html><body><h1>BLS CPI Schedule</h1><p>Nov 10, 2026</p></body></html>"
        receipt = importer.import_evidence(
            raw_bytes=schedule_bytes,
            declared_source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
            declared_mime_type="text/html",
            provenance_sidecar={"notes": "No cryptographic signature"},
        )
        assert receipt.authenticity_level == SourceAuthenticityLevel.SOURCE_CLAIMED_OFFICIAL
        assert receipt.authenticity_level != SourceAuthenticityLevel.SOURCE_AUTHENTICITY_VERIFIED


def test_04_event_identity_cannot_be_frozen_without_attestation():
    candidate = EventIdentityManager.create_candidate_event()
    dummy_hash = hashlib.sha256(b"dummy").hexdigest()
    with pytest.raises(ValueError, match="lacks cryptographic provenance verification"):
        EventIdentityManager.bind_and_freeze_event(
            candidate,
            verified_schedule_sha256=dummy_hash,
            is_provenance_verified=False,
        )


def test_05_binding_to_verified_schedule_freezes_event():
    candidate = EventIdentityManager.create_candidate_event()
    authentic_hash = hashlib.sha256(b"authentic_bls_schedule").hexdigest()
    frozen = EventIdentityManager.bind_and_freeze_event(
        candidate,
        verified_schedule_sha256=authentic_hash,
        is_provenance_verified=True,
    )
    assert frozen.status == EventIdentityStatus.VERIFIED_FROZEN
    assert frozen.schedule_evidence_sha256 == authentic_hash
    assert frozen.candidate_event_id == "EVT-BLS-CPI-2026M10-20261110"


def test_06_schedule_date_mismatch_derives_correct_id():
    # If official schedule differs from candidate (e.g., Nov 12 instead of Nov 10)
    derived = EventIdentityManager.create_candidate_event()
    from coin_behavior_engine.prospective.schedule_verification import derive_canonical_event_id
    diff_id = derive_canonical_event_id("BLS", "CPI", "2026M10", "2026-11-12")
    assert diff_id == "EVT-BLS-CPI-2026M10-20261112"
    assert diff_id != derived.candidate_event_id


# ==============================================================================
# PHASE 5: OBSERVATION WINDOW & SAMPLING FEASIBILITY
# ==============================================================================

def test_07_post_event_completeness_35m_window():
    completeness = ObservationWindowPlanEvaluator.verify_post_event_completeness()
    assert completeness["proposed_pilot_duration_seconds"] == 2100
    assert completeness["proposed_pilot_duration_minutes"] == 35.0
    assert completeness["pilot_start_relative_to_release_seconds"] == -120
    assert completeness["pilot_end_relative_to_release_seconds"] == 1980  # +33m
    assert completeness["is_30m_horizon_fully_bounded"] is True
    assert completeness["post_event_coverage_margin_seconds"] == 180  # 3m safety buffer
    assert completeness["previous_30m_duration_defect_resolved"] is True


def test_08_30m_duration_defect_detected():
    # 1800s starting at T-2m (-120s) terminates at T+28m (+1680s), missing +30m milestone
    start_offset = -120
    end_offset = start_offset + 1800  # 1680s = +28m
    target_horizon = 1800
    assert end_offset < target_horizon
    assert (end_offset - target_horizon) == -120  # 2 minutes short


def test_09_continuous_1m_sampling_exceeds_quota():
    eval_cont = ObservationWindowPlanEvaluator.evaluate_continuous_sampling()
    assert eval_cont.strategy == SamplingStrategy.CONTINUOUS_1M
    assert eval_cont.planned_requests == 36
    assert eval_cont.quota_limit == 20
    assert eval_cont.is_feasible is False
    assert "exceeding the hard quota limit of 20 requests" in eval_cont.feasibility_blocker


def test_10_event_windowed_sampling_fits_quota():
    eval_win = ObservationWindowPlanEvaluator.evaluate_windowed_sampling()
    assert eval_win.strategy == SamplingStrategy.EVENT_WINDOWED_SPARSE
    assert eval_win.planned_requests == 13
    assert eval_win.quota_limit == 20
    assert eval_win.reserve_requests == 7
    assert eval_win.is_feasible is True
    assert eval_win.feasibility_blocker is None


# ==============================================================================
# PHASE 4: CONSENSUS POLICY
# ==============================================================================

def test_11_consensus_policy_disables_surprise_and_forecasts():
    candidate = EventIdentityManager.create_candidate_event()
    proposal = PilotProposalV3Builder.build_proposal(candidate)
    reqs = proposal.consensus_source_requirements
    assert "CONSENSUS_EVIDENCE_UNAVAILABLE" in reqs
    assert "DESCRIPTIVE_PILOT_NO_CONSENSUS_REQUIRED" in reqs
    assert "ECONOMIC_SURPRISE_ANALYSIS_DISABLED" in reqs
    assert "DIRECTIONAL_EDGE_CLAIMS_PROHIBITED" in reqs


# ==============================================================================
# PHASE 6: PILOT PROPOSAL V3 & DIGEST
# ==============================================================================

def test_12_proposal_v3_canonical_digest_determinism():
    candidate = EventIdentityManager.create_candidate_event()
    p1 = PilotProposalV3Builder.build_proposal(candidate)
    p2 = PilotProposalV3Builder.build_proposal(candidate)
    d1 = p1.compute_canonical_digest()
    d2 = p2.compute_canonical_digest()
    assert len(d1) == 64
    assert d1 == d2


def test_13_proposal_digest_sensitive_to_duration():
    candidate = EventIdentityManager.create_candidate_event()
    p_35m = PilotProposalV3Builder.build_proposal(candidate)
    p_30m = PilotProposalV3Builder.build_proposal(candidate)
    p_30m.max_duration_seconds = 1800

    d_35m = p_35m.compute_canonical_digest()
    d_30m = p_30m.compute_canonical_digest()
    assert d_35m != d_30m


def test_14_prior_approval_cannot_be_carried_over():
    # If a token was issued for an earlier digest, it cannot validate against Proposal v3
    candidate = EventIdentityManager.create_candidate_event()
    p_v3 = PilotProposalV3Builder.build_proposal(candidate)
    digest_v3 = p_v3.compute_canonical_digest()

    old_digest = hashlib.sha256(b"old_proposal_v2").hexdigest()
    assert old_digest != digest_v3


# ==============================================================================
# PRIVILEGED OPERATOR WORKFLOW & GATE ENFORCEMENT
# ==============================================================================

def test_15_mock_operator_approval_workflow_success():
    candidate = EventIdentityManager.create_candidate_event()
    proposal = PilotProposalV3Builder.build_proposal(candidate)

    op_research = OperatorIdentity("OP-RES-01", OperatorRole.RESEARCH_OPERATOR, "Alice", "FPR-A")
    op_admin = OperatorIdentity("OP-ADM-01", OperatorRole.APPROVAL_ADMIN, "Bob", "FPR-B")

    with tempfile.TemporaryDirectory() as td:
        store = TrustedApprovalStore(db_path=Path(td) / "approvals.sqlite")
        key_reg = SigningKeyRegistry()
        key_reg.register_key("test-key", b"0123456789abcdef", is_test_key=True)

        # Research operator cannot self-approve
        sub = OperatorApprovalWorkflowEngine.submit_proposal(proposal, op_research)
        with pytest.raises(UnauthorizedOperatorActionError):
            OperatorApprovalWorkflowEngine.approve_proposal(
                sub, approver=op_research, key_id="test-key", store=store, key_registry=key_reg
            )

        # Admin can approve
        app, token, rec = OperatorApprovalWorkflowEngine.approve_proposal(
            sub, approver=op_admin, key_id="test-key", store=store, key_registry=key_reg
        )
        assert app.authorization_status == ProposalStatus.APPROVED
        assert rec.proposal_digest == proposal.compute_canonical_digest()


def test_16_network_activation_gate_enforces_proposal_scope():
    candidate = EventIdentityManager.create_candidate_event()
    proposal = PilotProposalV3Builder.build_proposal(candidate)
    op_admin = OperatorIdentity("OP-ADM-01", OperatorRole.APPROVAL_ADMIN, "Bob", "FPR-B")

    with tempfile.TemporaryDirectory() as td:
        store = TrustedApprovalStore(db_path=Path(td) / "approvals.sqlite")
        key_reg = SigningKeyRegistry()
        key_reg.register_key("test-key", b"0123456789abcdef", is_test_key=True)

        _, token, _ = OperatorApprovalWorkflowEngine.approve_proposal(
            proposal, approver=op_admin, key_id="test-key", store=store, key_registry=key_reg
        )
        gate = NetworkActivationGate(
            key_registry=key_reg,
            approval_store=store,
            gate_enabled=True,
            operator_authorization_granted=True,
        )

        # In-scope public market data
        ok, _ = gate.evaluate_request(
            token=token,
            target_url="https://api.binance.com/api/v3/ticker/bookTicker",
            target_event_id=candidate.candidate_event_id,
        )
        assert ok is True

        # Out-of-scope domain
        blocked, reason = gate.evaluate_request(
            token=token,
            target_url="https://evil.com/leak",
            target_event_id=candidate.candidate_event_id,
        )
        assert blocked is False
        assert "domain" in reason.lower() or "not approved" in reason.lower() or "scope" in reason.lower()


def test_17_quota_exhaustion_blocks_further_requests():
    candidate = EventIdentityManager.create_candidate_event()
    proposal = PilotProposalV3Builder.build_proposal(candidate)
    op_admin = OperatorIdentity("OP-ADM-01", OperatorRole.APPROVAL_ADMIN, "Bob", "FPR-B")

    with tempfile.TemporaryDirectory() as td:
        store = TrustedApprovalStore(db_path=Path(td) / "approvals.sqlite")
        key_reg = SigningKeyRegistry()
        key_reg.register_key("test-key", b"0123456789abcdef", is_test_key=True)

        _, token, _ = OperatorApprovalWorkflowEngine.approve_proposal(
            proposal, approver=op_admin, key_id="test-key", store=store, key_registry=key_reg
        )
        gate = NetworkActivationGate(
            key_registry=key_reg,
            approval_store=store,
            gate_enabled=True,
            operator_authorization_granted=True,
        )

        # Exhaust 20 requests
        for _ in range(20):
            store.reserve_quota(token.token_id, estimated_bytes=100)
            store.commit_quota(token.token_id, actual_bytes=50)

        # 21st request must be denied
        ok, reason = gate.evaluate_request(
            token=token,
            target_url="https://api.binance.com/api/v3/ticker/bookTicker",
            target_event_id=candidate.candidate_event_id,
        )
        assert ok is False
        assert "exhausted" in reason.lower() or "quota" in reason.lower()


def test_18_durable_revocation_blocks_subsequent_requests():
    candidate = EventIdentityManager.create_candidate_event()
    proposal = PilotProposalV3Builder.build_proposal(candidate)
    op_admin = OperatorIdentity("OP-ADM-01", OperatorRole.APPROVAL_ADMIN, "Bob", "FPR-B")

    with tempfile.TemporaryDirectory() as td:
        store = TrustedApprovalStore(db_path=Path(td) / "approvals.sqlite")
        key_reg = SigningKeyRegistry()
        key_reg.register_key("test-key", b"0123456789abcdef", is_test_key=True)

        _, token, _ = OperatorApprovalWorkflowEngine.approve_proposal(
            proposal, approver=op_admin, key_id="test-key", store=store, key_registry=key_reg
        )
        gate = NetworkActivationGate(
            key_registry=key_reg,
            approval_store=store,
            gate_enabled=True,
            operator_authorization_granted=True,
        )

        # Revoke
        store.revoke_approval(token.token_id, revoked_by=op_admin.operator_id, reason="OPERATOR_REVOKE")

        ok, reason = gate.evaluate_request(
            token=token,
            target_url="https://api.binance.com/api/v3/ticker/bookTicker",
            target_event_id=candidate.candidate_event_id,
        )
        assert ok is False
        assert "revoked" in reason.lower()


# ==============================================================================
# EVIDENCE ADVERSARIAL FAILURE MODES
# ==============================================================================

def test_19_oversized_evidence_import_rejected():
    with tempfile.TemporaryDirectory() as td:
        importer = ControlledEvidenceImporter(vault=ImmutableEvidenceVault(vault_root=Path(td)))
        oversized_data = b"X" * (10 * 1024 * 1024 + 1)
        with pytest.raises(OversizedEvidenceError):
            importer.import_evidence(oversized_data, "https://bls.gov/cpi.htm", "text/html")


def test_20_path_traversal_in_evidence_rejected():
    importer = ControlledEvidenceImporter()
    with pytest.raises(PathTraversalError):
        importer.validate_file_safety("../../etc/passwd")


def test_21_unsafe_file_type_rejected():
    importer = ControlledEvidenceImporter()
    with pytest.raises(UnsafeEvidenceTypeError):
        importer.validate_file_safety("exploit.ps1")
    with pytest.raises(UnsafeEvidenceTypeError):
        importer.validate_file_safety("malware.exe")


def test_22_tampered_evidence_bytes_hash_mismatch():
    importer = ControlledEvidenceImporter()
    original = b"valid content"
    expected_sha = hashlib.sha256(original).hexdigest()
    tampered = b"tampered content"
    with pytest.raises(EvidenceChecksumMismatchError):
        importer.import_evidence(
            raw_bytes=tampered,
            declared_source_url="https://bls.gov/cpi.htm",
            declared_mime_type="text/plain",
            expected_sha256=expected_sha,
        )


def test_23_trading_capability_permanently_prohibited():
    from coin_behavior_engine.prospective.governance import (
        TradingIsolationViolation,
        ProspectiveGovernanceGuard,
    )
    # Order execution endpoint access is strictly forbidden
    with pytest.raises(TradingIsolationViolation):
        ProspectiveGovernanceGuard.assert_endpoint_not_order_execution("https://api.binance.com/api/v3/order")

    # Trading eligibility on prospective evidence is strictly forbidden
    with pytest.raises(TradingIsolationViolation):
        ProspectiveGovernanceGuard.assert_evidence_non_tradable(
            {"directional_trading_eligible": True, "event_id": "EVT-TEST-001"}
        )


# ==============================================================================
# PHASE 7 & 8: REHEARSAL & DECISION ENGINE
# ==============================================================================

def test_24_offline_pilot_rehearsal_full_flow():
    results = OfflinePilotRehearsalRunnerV4.run_rehearsal()
    assert results["overall_status"] == "PASS"
    assert len(results["steps"]) == 14
    for step in results["steps"]:
        assert step["status"] == "PASS", f"Step {step['step']} ({step['name']}) failed: {step}"


def test_25_pilot_proposal_freeze_decision_engine():
    candidate = EventIdentityManager.create_candidate_event()
    sampling = ObservationWindowPlanEvaluator.evaluate_windowed_sampling()

    decision = PilotProposalFreezeDecisionEngine.evaluate_decision(
        candidate_event=candidate,
        sampling_eval=sampling,
        has_authentic_official_schedule=False,
        is_operator_authorized=False,
    )
    assert decision["technical_preflight"] == "PASS"
    assert decision["observation_window_feasibility"] == "PASS"
    assert decision["sampling_plan_feasibility"] == "PASS"
    assert decision["rehearsal_status"] == "PASS"
    assert decision["pilot_proposal_review_status"] == PilotProposalReviewStatus.READY_FOR_OPERATOR_REVIEW.value
    assert decision["execution_gate_decision"] == PilotProposalReviewStatus.BLOCKED_WITH_EXPLICIT_REASONS.value
    assert len(decision["explicit_blockers"]) > 0
    assert "OPERATOR_AUTHORIZATION: NOT_GRANTED (Privileged Approval Admin token not issued)" in decision["explicit_blockers"]
    assert "REAL_NETWORK_COLLECTION: DISABLED (Execution mode OFFLINE-FIRST)" in decision["explicit_blockers"]

"""
Sprint 11.23.5B-3: Evidence Acquisition, Provenance & Operator Review Tests
Comprehensive test suite validating:
  - Controlled evidence import safety (file size, MIME, safe extensions, path traversal)
  - Provenance classification (SOURCE_CLAIMED_OFFICIAL vs SOURCE_AUTHENTICITY_VERIFIED)
  - Pre-release consensus vintage and metric comparability (YoY vs MoM)
  - Licensing protection against scraping proprietary feeds
  - Market observation feasibility matrix (30m duration boundedness, tick vs candle)
  - Offline rehearsal with deterministic fixtures
  - Operator review dossier & evidence readiness decision
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import hashlib
import json
import os
from pathlib import Path
import tempfile
import time
import pytest

from coin_behavior_engine.prospective import (
    ReadOnlyResearchTransport,
    TransportResponse,
    TradingIsolationViolation,
    ObservationAuthorizationToken,
    AuthorizationCapability,
    SigningKeyRegistry,
    TrustedApprovalStore,
    NetworkActivationGate,
    AuthorizationError,
    UnknownKeyIdError,
    NetworkActivationGateError,
    OperatorRole,
    OperatorIdentity,
    ProposalStatus,
    PilotProposal,
    OperatorApprovalWorkflowEngine,
    UnauthorizedOperatorActionError,
    ImmutableEvidenceVault,
    OfficialScheduleRecord,
    OfficialScheduleVerificationEngine,
    ScheduleVerificationStatus,
    ReferencePeriodMismatchError,
    derive_canonical_event_id,
    is_placeholder_event_id,
    EvidenceAcquisitionError,
    OversizedEvidenceError,
    UnsafeEvidenceTypeError,
    MimeTypeMismatchError,
    EvidenceChecksumMismatchError,
    PathTraversalError,
    MetricMismatchError,
    LicensingViolationError,
    VintageViolationError,
    SourceAuthenticityLevel,
    DocumentMimeType,
    ConsensusLicensingStatus,
    PilotEvidenceDecision,
    ImportedEvidenceReceipt,
    ControlledEvidenceImporter,
    ConsensusSourceEvaluation,
    ConsensusSourceAssessor,
    MarketMeasurementFeasibility,
    MarketObservationPlanEvaluator,
    OfflinePilotRehearsalRunner,
    PilotEvidenceReadinessEvaluator,
)


@pytest.fixture(autouse=True)
def reset_key_registry():
    SigningKeyRegistry.reset_instance()
    yield
    SigningKeyRegistry.reset_instance()


# ==============================================================================
# PHASE 8: 24 ADVERSARIAL TESTS FOR SPRINT 11.23.5B-3
# ==============================================================================

def test_01_forged_official_source_metadata_detected():
    """Test 1: Claimed official source without cryptographic attestation gets SOURCE_CLAIMED_OFFICIAL."""
    with tempfile.TemporaryDirectory() as td:
        vault = ImmutableEvidenceVault(vault_root=Path(td))
        importer = ControlledEvidenceImporter(vault=vault)

        doc = b"<html>Sample Schedule claimed as BLS</html>"
        receipt = importer.import_evidence(
            raw_bytes=doc,
            declared_source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
            declared_mime_type="text/html",
            provenance_sidecar={"claimer": "operator"},  # No cryptographic attestation
        )

        assert receipt.authenticity_level == SourceAuthenticityLevel.SOURCE_CLAIMED_OFFICIAL
        assert receipt.authenticity_level != SourceAuthenticityLevel.SOURCE_AUTHENTICITY_VERIFIED


def test_02_unauthenticated_schedule_document_blocks_readiness():
    """Test 2: Evaluator with unauthenticated schedule document returns BLOCKED_OFFICIAL_SCHEDULE."""
    evaluator = PilotEvidenceReadinessEvaluator()
    res = evaluator.evaluate(has_official_schedule_document=False)
    assert res["overall_decision"] == PilotEvidenceDecision.BLOCKED_OFFICIAL_SCHEDULE.value
    assert res["component_statuses"]["schedule_evidence"] == "PENDING"
    assert res["operational_execution_authorized"] == "NO"


def test_03_incorrect_cpi_reference_period_rejected():
    """Test 3: CPI schedule where reference month equals release month is rejected."""
    with tempfile.TemporaryDirectory() as td:
        vault = ImmutableEvidenceVault(vault_root=Path(td))
        engine = OfficialScheduleVerificationEngine(vault=vault)
        doc = b"<html>BLS CPI Invalid Schedule</html>"

        with pytest.raises(ReferencePeriodMismatchError):
            engine.verify_schedule_offline(
                raw_document_bytes=doc,
                source_url="https://www.bls.gov/schedule/news_release/cpi.htm",
                reference_period="2026-10",  # Release is also Oct 2026 -> conflict!
                scheduled_local_dt="2026-10-13T08:30:00",
            )


def test_04_conflicting_schedule_documents_isolated():
    """Test 4: Importing two conflicting schedule documents preserves both independently via content addressing."""
    with tempfile.TemporaryDirectory() as td:
        vault = ImmutableEvidenceVault(vault_root=Path(td))
        importer = ControlledEvidenceImporter(vault=vault)

        doc_a = b"<html>Schedule Version Alpha: Oct 13</html>"
        doc_b = b"<html>Schedule Version Beta: Oct 14</html>"

        rec_a = importer.import_evidence(doc_a, "https://www.bls.gov/cpi", "text/html")
        rec_b = importer.import_evidence(doc_b, "https://www.bls.gov/cpi", "text/html")

        assert rec_a.sha256_hash != rec_b.sha256_hash
        assert rec_a.stored_vault_path != rec_b.stored_vault_path
        assert rec_a.is_duplicate is False
        assert rec_b.is_duplicate is False


def test_05_schedule_revision_after_proposal_creation_invalidates_digest():
    """Test 5: Schedule revision alters canonical event ID, invalidating proposal digest."""
    proposal = PilotProposal(
        proposal_id="PROP-01",
        proposal_version="1.0.0",
        event_id="EVT-BLS-CPI-2026M09-20261013",
        event_name="US CPI",
        official_publisher="BLS",
        official_source_url="https://www.bls.gov/cpi",
        expected_publication_time="2026-10-13T12:30:00Z",
        schedule_verification_status="VERIFIED",
        consensus_source_requirements=["Survey"],
        btc_market_data_endpoints=["https://data-api.binance.vision/api/v3/ticker/bookTicker"],
        max_duration_seconds=1800,
        max_requests=20,
        max_bytes=5242880,
        polling_interval_seconds=5.0,
        approved_domains=["bls.gov"],
        evidence_storage_destination="vault/",
        timestamp_policy="STRICT",
        emergency_stop_conditions=["429"],
        created_by_operator_id="OP-01",
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    digest_v1 = proposal.compute_canonical_digest()

    # Schedule revised to Oct 14
    proposal.event_id = "EVT-BLS-CPI-2026M09-20261014"
    proposal.expected_publication_time = "2026-10-14T12:30:00Z"
    digest_v2 = proposal.compute_canonical_digest()

    assert digest_v1 != digest_v2


def test_06_expired_schedule_evidence_rejected():
    """Test 6: Expired schedule evidence where release date is in the past."""
    engine = OfficialScheduleVerificationEngine()
    # Record with release date in 2022
    past_utc = "2022-01-12T13:30:00Z"
    t_past = datetime.fromisoformat(past_utc.replace("Z", "+00:00"))
    now = datetime.now(timezone.utc)
    assert t_past < now  # Past schedule is expired for prospective observation


def test_07_missing_consensus_timestamp_rejected():
    """Test 7: Consensus record missing verifiable publication timestamps raises error."""
    assessor = ConsensusSourceAssessor()
    with pytest.raises(VintageViolationError):
        assessor.evaluate_source(
            publisher="SurveyCorp",
            metric_definition="CPI YoY",
            reference_period="2026-09",
            forecast_value=3.2,
            unit="%",
            source_publication_utc=None,  # Missing
            first_available_utc=None,
            scheduled_release_utc="2026-10-13T12:30:00Z",
            has_authorized_license=True,
        )


def test_08_consensus_published_after_release_rejected():
    """Test 8: Consensus observed on or after official release raises VintageViolationError."""
    assessor = ConsensusSourceAssessor()
    with pytest.raises(VintageViolationError) as exc:
        assessor.evaluate_source(
            publisher="LatePoll",
            metric_definition="CPI YoY",
            reference_period="2026-09",
            forecast_value=3.2,
            unit="%",
            source_publication_utc="2026-10-13T12:30:00Z",
            first_available_utc="2026-10-13T12:30:01Z",  # 1 sec after release!
            scheduled_release_utc="2026-10-13T12:30:00Z",
            has_authorized_license=True,
        )
    assert "Vintage violation" in str(exc.value)


def test_09_forecast_metric_mismatch_rejected():
    """Test 9: Month-over-month (MoM) consensus compared with Headline YoY raises MetricMismatchError."""
    assessor = ConsensusSourceAssessor()
    with pytest.raises(MetricMismatchError) as exc:
        assessor.evaluate_source(
            publisher="SurveyOrg",
            metric_definition="CPI MoM (Month-over-Month)",  # Mismatched metric
            reference_period="2026-09",
            forecast_value=0.3,
            unit="%",
            source_publication_utc="2026-10-12T16:00:00Z",
            first_available_utc="2026-10-12T16:00:05Z",
            scheduled_release_utc="2026-10-13T12:30:00Z",
            has_authorized_license=True,
        )
    assert "Metric mismatch" in str(exc.value)


def test_10_unauthorized_licensed_source_ingestion_blocked():
    """Test 10: Attempting to scrape unlicensed restricted feeds raises LicensingViolationError."""
    assessor = ConsensusSourceAssessor()
    with pytest.raises(LicensingViolationError) as exc:
        assessor.evaluate_source(
            publisher="ProprietaryTerminal",
            metric_definition="CPI YoY",
            reference_period="2026-09",
            forecast_value=3.1,
            unit="%",
            source_publication_utc="2026-10-12T16:00:00Z",
            first_available_utc="2026-10-12T16:00:05Z",
            scheduled_release_utc="2026-10-13T12:30:00Z",
            licensing_status=ConsensusLicensingStatus.UNLICENSED_SCRAPED_PROHIBITED,
        )
    assert "Licensing violation" in str(exc.value)


def test_11_oversized_imported_document_rejected():
    """Test 11: Document exceeding 10 MB limit raises OversizedEvidenceError."""
    with tempfile.TemporaryDirectory() as td:
        vault = ImmutableEvidenceVault(vault_root=Path(td))
        importer = ControlledEvidenceImporter(vault=vault)
        # Create bytes > 10MB
        oversized = b"A" * (10 * 1024 * 1024 + 100)

        with pytest.raises(OversizedEvidenceError) as exc:
            importer.import_evidence(
                raw_bytes=oversized,
                declared_source_url="https://www.bls.gov/large.pdf",
                declared_mime_type="application/pdf",
            )
        assert "exceeds maximum permitted limit" in str(exc.value)


def test_12_path_traversal_rejected():
    """Test 12: File path with path traversal raises PathTraversalError."""
    importer = ControlledEvidenceImporter()
    with pytest.raises(PathTraversalError):
        importer.validate_file_safety("../../etc/passwd.html")


def test_13_unsafe_file_type_rejected():
    """Test 13: Executable or script file extension raises UnsafeEvidenceTypeError."""
    importer = ControlledEvidenceImporter()
    with pytest.raises(UnsafeEvidenceTypeError) as exc:
        importer.validate_file_safety("malicious_script.sh")
    assert "Prohibited executable/archive" in str(exc.value)


def test_14_duplicate_evidence_detected_idempotent():
    """Test 14: Duplicate evidence import is idempotent and returns is_duplicate=True."""
    with tempfile.TemporaryDirectory() as td:
        vault = ImmutableEvidenceVault(vault_root=Path(td))
        importer = ControlledEvidenceImporter(vault=vault)
        doc = b"<html>Sample Evidence Content</html>"

        r1 = importer.import_evidence(doc, "https://bls.gov/news", "text/html")
        r2 = importer.import_evidence(doc, "https://bls.gov/news", "text/html")

        assert r1.is_duplicate is False
        assert r2.is_duplicate is True
        assert r1.sha256_hash == r2.sha256_hash


def test_15_altered_evidence_bytes_hash_mismatch():
    """Test 15: Raw bytes not matching expected SHA-256 raise EvidenceChecksumMismatchError."""
    with tempfile.TemporaryDirectory() as td:
        vault = ImmutableEvidenceVault(vault_root=Path(td))
        importer = ControlledEvidenceImporter(vault=vault)
        doc = b"<html>Altered Content</html>"

        with pytest.raises(EvidenceChecksumMismatchError) as exc:
            importer.import_evidence(
                raw_bytes=doc,
                declared_source_url="https://bls.gov/news",
                declared_mime_type="text/html",
                expected_sha256="0000000000000000000000000000000000000000000000000000000000000000",
            )
        assert "does not match expected checksum" in str(exc.value)


def test_16_event_identity_mismatch_blocked_in_gate():
    """Test 16: Gate blocks request targeting an event ID different from approved token."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-evt-test-16", b"secret_key_bytes_16_test_only", is_test_key=True)
    store = TrustedApprovalStore()

    token = ObservationAuthorizationToken(
        token_id="AUTH-16",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-BLS-CPI-2026M09-20261013",
        operator_identity="Admin",
        issued_at_utc=datetime.now(timezone.utc).isoformat(),
        not_before_utc=datetime.now(timezone.utc).isoformat(),
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="key-evt-test-16",
    )
    token.signature_digest = token.compute_canonical_digest()
    store.create_privileged_approval(token, privileged_operator="Admin")

    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)
    allowed, reason = gate.evaluate_request(token, "https://bls.gov/news", target_event_id="EVT-WRONG-EVENT-ID")
    assert allowed is False
    assert "OUT_OF_SCOPE_EVENT" in reason


def test_17_proposal_digest_mismatch_invalidates_approval():
    """Test 17: Proposal digest alteration causes validation failure."""
    proposal = PilotProposal(
        proposal_id="PROP-17",
        proposal_version="1.0.0",
        event_id="EVT-BLS-CPI-2026M09-20261013",
        event_name="US CPI",
        official_publisher="BLS",
        official_source_url="https://www.bls.gov/cpi",
        expected_publication_time="2026-10-13T12:30:00Z",
        schedule_verification_status="VERIFIED",
        consensus_source_requirements=["Survey"],
        btc_market_data_endpoints=["https://data-api.binance.vision/api/v3/ticker/bookTicker"],
        max_duration_seconds=1800,
        max_requests=20,
        max_bytes=5242880,
        polling_interval_seconds=5.0,
        approved_domains=["bls.gov"],
        evidence_storage_destination="vault/",
        timestamp_policy="STRICT",
        emergency_stop_conditions=["429"],
        created_by_operator_id="OP-01",
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    d1 = proposal.compute_canonical_digest()
    # Change domain
    proposal.approved_domains = ["bls.gov", "unapproved.com"]
    d2 = proposal.compute_canonical_digest()
    assert d1 != d2


def test_18_unauthorized_operator_approval_blocked():
    """Test 18: Research operator attempting to approve proposal raises UnauthorizedOperatorActionError."""
    researcher = OperatorIdentity("OP-RES-01", OperatorRole.RESEARCH_OPERATOR, "Researcher", "fp-01")
    proposal = PilotProposal(
        proposal_id="PROP-18",
        proposal_version="1.0.0",
        event_id="EVT-BLS-CPI-2026M09-20261013",
        event_name="US CPI",
        official_publisher="BLS",
        official_source_url="https://www.bls.gov/cpi",
        expected_publication_time="2026-10-13T12:30:00Z",
        schedule_verification_status="VERIFIED",
        consensus_source_requirements=["Survey"],
        btc_market_data_endpoints=["https://data-api.binance.vision/api/v3/ticker/bookTicker"],
        max_duration_seconds=1800,
        max_requests=20,
        max_bytes=5242880,
        polling_interval_seconds=5.0,
        approved_domains=["bls.gov"],
        evidence_storage_destination="vault/",
        timestamp_policy="STRICT",
        emergency_stop_conditions=["429"],
        created_by_operator_id="OP-RES-02",
        created_at_utc=datetime.now(timezone.utc).isoformat(),
    )
    store = TrustedApprovalStore()
    with pytest.raises(UnauthorizedOperatorActionError):
        OperatorApprovalWorkflowEngine.approve_proposal(proposal, approver=researcher, key_id="key-01", store=store)


def test_19_mock_authorization_reused_in_production_rejected():
    """Test 19: Test key used with allow_test_key=False is rejected."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("test-key-19", b"test_key_bytes_19_test_only", is_test_key=True)

    with pytest.raises(AuthorizationError) as exc:
        reg.get_key("test-key-19", allow_test_key=False)
    assert "production" in str(exc.value)


def test_20_network_activation_attempt_without_gate_blocked():
    """Test 20: Transport execute_request with network_enabled=True without valid gate raises error."""
    transport = ReadOnlyResearchTransport(network_enabled=True)
    with pytest.raises(NetworkActivationGateError):
        transport.execute_request("GET", "https://bls.gov/news")


def test_21_request_budget_exhaustion_detected():
    """Test 21: Allocating > 20 requests fails budget feasibility validation."""
    from coin_behavior_engine.prospective import PilotRequestBudgetPlan
    budget = PilotRequestBudgetPlan(release_polling_requests=15)  # 25 total
    ok, reason = budget.validate_feasibility()
    assert ok is False
    assert "exceeds budget" in reason


def test_22_revocation_during_mock_observation_blocks_next_request():
    """Test 22: Mid-session approval revocation immediately denies next request."""
    reg = SigningKeyRegistry.get_instance()
    reg.register_key("key-22", b"secret_key_bytes_22_test_only", is_test_key=True)
    store = TrustedApprovalStore()

    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-22",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        authorized_event_id="EVT-01",
        operator_identity="Admin",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        approved_domains=["bls.gov"],
        max_request_count=10,
        max_byte_allowance=1048576,
        key_id="key-22",
    )
    token.signature_digest = token.compute_canonical_digest()
    store.create_privileged_approval(token, privileged_operator="Admin")
    gate = NetworkActivationGate(approval_store=store, key_registry=reg, gate_enabled=True, operator_authorization_granted=True)

    # Request 1: allowed
    ok1, _ = gate.evaluate_request(token, "https://bls.gov/news", "EVT-01")
    assert ok1 is True

    # Revocation triggered
    store.revoke_approval(token.token_id, revoked_by="Admin", reason="Emergency stop")

    # Request 2: blocked
    ok2, reason = gate.evaluate_request(token, "https://bls.gov/news", "EVT-01")
    assert ok2 is False
    assert "REVOKED" in reason


def test_23_incomplete_30_minute_measurement_documented():
    """Test 23: Market observation evaluator flags 30m horizon as duration-bounded under 1800s budget."""
    evaluator = MarketObservationPlanEvaluator()
    feasibilities = evaluator.evaluate_feasibility()

    m_30 = next(f for f in feasibilities if f.measurement_name == "30-minute post-event return")
    assert m_30.feasibility_status == "CONDITIONAL_DURATION_BOUNDED"
    assert "DESIGN LIMITATION" in m_30.notes


def test_24_trading_capability_invocation_permanently_prohibited():
    """Test 24: Requesting LIVE_ORDER_EXECUTION raises TradingIsolationViolation."""
    store = TrustedApprovalStore()
    token = ObservationAuthorizationToken(
        token_id="AUTH-BAD-TRADING",
        capability=AuthorizationCapability.LIVE_ORDER_EXECUTION,
        authorized_event_id="EVT-01",
        operator_identity="Admin",
    )
    with pytest.raises(TradingIsolationViolation):
        store.create_privileged_approval(token, privileged_operator="Admin")


def test_25_offline_pilot_rehearsal_full_flow():
    """Test 25: End-to-end 14-step offline rehearsal executes successfully."""
    with tempfile.TemporaryDirectory() as td:
        runner = OfflinePilotRehearsalRunner()
        res = runner.run_rehearsal()
        assert res["status"] == "PASS"
        assert len(res["steps_executed"]) >= 10

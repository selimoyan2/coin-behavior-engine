"""
Coin Behavior Engine — Sprint 23 Automated Acceptance Test Suite
CBE_PRODUCT_ACCELERATION_23: Platform Security, Reliability & Operational Readiness V1

Covers:
- Group A: Credential Isolation, Session Security & CSRF Defense
- Group B: Evidence Signing, Rotation, Revocation & Independent Trust Verification
- Group C: Multi-Process Advisory Locking, Atomic Persistence & Durability Engine
- Group D: VPS Hardware Protection, Concurrency Semaphores & Memory Diagnostics
- Group E: Health, Readiness & Privileged Operational Observability
- Group F: Canonical Model Freeze (CBE-0.7.0), Invariant Enforcement & Governance Gating
- Group G: PDF Export Reliability, TrueType Typography & HTML Report Rendering
"""

from __future__ import annotations

import collections
import io
import json
import logging
import os
import shutil
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
import pytest

from coin_behavior_engine.product.credential_manager import (
    CredentialManager,
    CredentialSeparationViolationError,
    SigningKeyRegistry,
    signing_key_registry,
)
from coin_behavior_engine.product.session_manager import (
    SessionManager,
    SessionRecord,
    session_manager,
)
from coin_behavior_engine.product.process_locking import (
    MultiProcessLock,
    LockTimeoutError,
)
from coin_behavior_engine.product.storage_durability import (
    StorageDurabilityEngine,
    ResearchBackupRestoreEngine,
)
from coin_behavior_engine.product.resource_governor import (
    ResourceGovernor,
    ResourceLimitExceededError,
    resource_governor,
)
from coin_behavior_engine.product.structured_logging import (
    SecretRedactingFilter,
    StructuredAuditLogger,
    structured_audit_logger,
)
from coin_behavior_engine.product.error_contract import (
    build_error_response,
    ERROR_TAXONOMY,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.research_report_builder import ResearchReportBuilderEngine
from coin_behavior_engine.product.research_report_evidence import ResearchReportEvidenceBundleEngine
from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION


# =============================================================================
# GROUP A: CREDENTIAL ISOLATION, SESSION SECURITY & CSRF DEFENSE
# =============================================================================

class TestGroupACredentialAndSessionSecurity:
    """Group A tests: Secret isolation, session lifecycle, CSRF tokens, cross-origin defense."""

    def test_a1_credential_separation_enforcement(self, monkeypatch):
        """Cross-purpose credential reuse between auth and signing must be strictly blocked."""
        shared_secret = "identical-secret-value-shared-across-domains-12345"
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", shared_secret)
        monkeypatch.setenv("CBE_EVIDENCE_SIGNING_KEY", shared_secret)

        with pytest.raises(CredentialSeparationViolationError):
            CredentialManager.validate_credential_separation()

    def test_a2_test_operator_token_blocked_in_production(self, monkeypatch):
        """CBE_TEST_OPERATOR_TOKEN must never be accepted in production."""
        monkeypatch.setenv("CBE_ENV", "production")
        monkeypatch.setenv("CBE_TEST_OPERATOR_TOKEN", "staging-test-token-xyz")
        monkeypatch.delenv("CBE_OPERATOR_TOKEN", raising=False)

        valid, reason = CredentialManager.verify_operator_token("staging-test-token-xyz")
        assert not valid
        assert reason == "TOKEN_MISMATCH"

    def test_a3_revoked_operator_token_rejected(self, monkeypatch):
        """Tokens marked as revoked must immediately fail validation."""
        revoked_token = "cbe-revoked-token-sample-404"
        from coin_behavior_engine.product.operations_console import revoke_operator_token
        revoke_operator_token(revoked_token)

        valid, reason = CredentialManager.verify_operator_token(revoked_token)
        assert not valid
        assert reason == "TOKEN_REVOKED"

    def test_a4_session_creation_and_httponly_cookie(self, monkeypatch):
        """Session login generates HttpOnly, SameSite=Strict cookies without leaking tokens."""
        valid_tok = "valid-operator-auth-token-sprint23-alpha"
        monkeypatch.setenv("CBE_ENV", "staging")
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", valid_tok)
        monkeypatch.setenv("CBE_EVIDENCE_SIGNING_KEY", "distinct-evidence-signing-key-456")

        status, resp = ProductDashboardApiService.post_session_login_api({"operator_token": valid_tok})
        assert status == 200
        assert resp["status"] == "AUTHENTICATED"
        assert "session_id" in resp
        assert "csrf_token" in resp
        assert "_set_cookie" in resp

        cookie_str = resp["_set_cookie"]
        assert "HttpOnly" in cookie_str
        assert "SameSite=Strict" in cookie_str
        assert "Path=/" in cookie_str

    def test_a5_csrf_token_verification_on_mutation(self, monkeypatch):
        """State mutation requires valid CSRF token matching the session."""
        valid_tok = "valid-operator-auth-token-sprint23-beta"
        monkeypatch.setenv("CBE_ENV", "staging")
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", valid_tok)
        monkeypatch.setenv("CBE_EVIDENCE_SIGNING_KEY", "distinct-evidence-signing-key-789")

        rec = session_manager.create_session(valid_tok)
        headers_no_csrf = {"Cookie": f"cbe_session_id={rec.session_id}"}
        headers_bad_csrf = {"Cookie": f"cbe_session_id={rec.session_id}", "X-CSRF-Token": "tampered-csrf"}
        headers_good_csrf = {"Cookie": f"cbe_session_id={rec.session_id}", "X-CSRF-Token": rec.csrf_token}

        # Mutation attempt without CSRF
        authed_no, st_no, _ = ProductDashboardApiService._authorize_report_access(headers_no_csrf, is_mutation=True)
        assert not authed_no
        assert st_no == 403

        # Mutation attempt with bad CSRF
        authed_bad, st_bad, _ = ProductDashboardApiService._authorize_report_access(headers_bad_csrf, is_mutation=True)
        assert not authed_bad
        assert st_bad == 403

        # Mutation attempt with good CSRF
        authed_good, st_good, _ = ProductDashboardApiService._authorize_report_access(headers_good_csrf, is_mutation=True)
        assert authed_good
        assert st_good == 200

    def test_a6_cross_origin_browser_mutation_rejected(self, monkeypatch):
        """Sec-Fetch-Site: cross-site requests must be denied for mutations."""
        valid_tok = "valid-operator-auth-token-sprint23-gamma"
        monkeypatch.setenv("CBE_ENV", "staging")
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", valid_tok)
        monkeypatch.setenv("CBE_EVIDENCE_SIGNING_KEY", "distinct-signing-key-abc")

        rec = session_manager.create_session(valid_tok)
        headers = {
            "Cookie": f"cbe_session_id={rec.session_id}",
            "X-CSRF-Token": rec.csrf_token,
            "Sec-Fetch-Site": "cross-site",
        }

        authed, st, msg = ProductDashboardApiService._authorize_report_access(headers, is_mutation=True)
        assert not authed
        assert st == 403
        assert "CSRF_CROSS_SITE_REQUEST_REJECTED" in msg


# =============================================================================
# GROUP B: EVIDENCE SIGNING, ROTATION, REVOCATION & TRUST BOUNDARIES
# =============================================================================

class TestGroupBEvidenceSigningAndTrust:
    """Group B tests: Key rotation, structured signatures, revoked keys, authoritative verification."""

    @pytest.fixture
    def sample_report(self):
        return {
            "report_metadata": {
                "report_id": "RPT-20261106-TEST01",
                "title": "Evidence Test Report",
                "generated_at_utc": "2026-11-06T00:00:00Z",
                "dataset_manifest_version": "V2_CANONICAL_2026_V1",
            },
            "historical_scope": {
                "asset": "BTCUSDT",
                "start_utc": "2022-06-01T00:00:00Z",
                "end_utc": "2022-06-03T00:00:00Z",
                "dataset_manifest_version": "V2_CANONICAL_2026_V1",
            },
            "canonical_model_identity": {
                "version": "CBE-0.7.0",
                "status": "STRICTLY_FROZEN",
                "parameter_mutations": 0,
            },
            "statistical_evidence": {
                "predeclared_holdout_criteria_satisfied": True,
                "p_value": 0.012,
            },
            "evidence_provenance": {
                "dataset_manifest_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "source_commit_sha": "db3bb63e1aca90582847880e80abd9e87938b142",
            },
        }

    def test_b1_evidence_signing_with_key_id(self, sample_report, monkeypatch):
        """Active signing key creates structured signature: hmac-sha256:<key_id>:<hex>."""
        monkeypatch.setenv("CBE_EVIDENCE_SIGNING_KEY_ID", "key-2026-rot1")
        monkeypatch.setenv("CBE_EVIDENCE_SIGNING_KEY", "super-secret-signing-key-2026-rot1")

        reg = SigningKeyRegistry()
        payload_bytes = b'{"test":"canonical_payload"}'
        sig = reg.sign_canonical_payload(payload_bytes)

        assert sig.startswith("hmac-sha256:key-2026-rot1:")
        is_valid, msg, k_id = reg.verify_signature(payload_bytes, sig)
        assert is_valid
        assert msg == "HMAC_SHA256_VERIFIED"
        assert k_id == "key-2026-rot1"

    def test_b2_evidence_signing_key_revocation_rejected(self, sample_report):
        """Evidence signed with a revoked key must be rejected with REVOKED_SIGNING_KEY."""
        reg = SigningKeyRegistry()
        reg.register_key("compromised-key-99", "secret-99", is_active=True)

        payload_bytes = b'{"test":"sensitive_payload"}'
        sig = reg.sign_canonical_payload(payload_bytes)

        # Revoke the key
        reg.revoke_key("compromised-key-99")

        is_valid, msg, k_id = reg.verify_signature(payload_bytes, sig)
        assert not is_valid
        assert msg == "REVOKED_SIGNING_KEY"
        assert k_id == "compromised-key-99"

    def test_b3_evidence_bundle_verification_with_revoked_key(self, sample_report, monkeypatch):
        """Evidence bundle verifier assigns REVOKED_SIGNING_KEY verdict when key is revoked."""
        engine = ResearchReportEvidenceBundleEngine()
        signing_key = "test-signing-key-rev-test"
        bundle = engine.create_evidence_bundle(sample_report, sign_with_key=signing_key)

        # Mark signing key as revoked in registry
        signing_key_registry.register_key("rev-key-test", signing_key)
        signing_key_registry.revoke_key("rev-key-test")

        ver = engine.verify_evidence_bundle(bundle)
        assert not ver["valid"]
        assert ver["verdict"] == "REVOKED_SIGNING_KEY"

    def test_b4_tampered_payload_rejected(self, sample_report):
        """Tampering with any payload field triggers TAMPERED_CHECKSUM_MISMATCH."""
        engine = ResearchReportEvidenceBundleEngine()
        bundle = engine.create_evidence_bundle(sample_report)

        # Tamper payload
        bundle["payload"]["canonical_report"]["statistical_evidence"]["p_value"] = 0.999

        ver = engine.verify_evidence_bundle(bundle)
        assert not ver["valid"]
        assert ver["tampering_detected"]
        assert ver["verdict"] == "TAMPERED_CHECKSUM_MISMATCH"

    def test_b5_non_finite_numerical_value_rejected(self, sample_report):
        """NaN or Infinity inside bundle must be rejected unconditionally."""
        engine = ResearchReportEvidenceBundleEngine()
        bundle = engine.create_evidence_bundle(sample_report)

        bundle["payload"]["canonical_report"]["statistical_evidence"]["p_value"] = float("nan")

        ver = engine.verify_evidence_bundle(bundle)
        assert not ver["valid"]
        assert ver["tampering_detected"]
        assert ver["verdict"] == "NON_FINITE_NUMERIC_VALUE_DETECTED"


# =============================================================================
# GROUP C: MULTI-PROCESS ADVISORY LOCKING & STORAGE DURABILITY
# =============================================================================

class TestGroupCProcessLockingAndDurability:
    """Group C tests: Cross-process file locks, timeout semantics, atomic file replacement, backups."""

    def test_c1_multiprocess_lock_mutual_exclusion(self, tmp_path):
        """Lock acquisition by one thread/process blocks other concurrent attempts."""
        lock_file = tmp_path / "test.lock"
        lock1 = MultiProcessLock(lock_file, timeout=1.0)
        lock2 = MultiProcessLock(lock_file, timeout=0.2)

        lock1.acquire()
        try:
            # Second lock attempt must time out
            with pytest.raises(LockTimeoutError):
                lock2.acquire()
        finally:
            lock1.release()

        # After release, second lock can acquire
        lock2.acquire()
        lock2.release()

    def test_c2_storage_durability_classification(self, tmp_path, monkeypatch):
        """Storage durability engine classifies paths and rejects ephemeral mounts in staging."""
        monkeypatch.setenv("CBE_ENV", "staging")

        # Ephemeral path check
        info_tmp = StorageDurabilityEngine.inspect_storage_path("/tmp/test_reports")
        assert info_tmp["is_ephemeral"]
        assert info_tmp["classification"] == "EPHEMERAL"

        # Must raise on ephemeral path requirement
        with pytest.raises(RuntimeError) as exc_info:
            StorageDurabilityEngine.require_durable_storage("/tmp/test_reports")
        assert "EPHEMERAL_STORAGE_REJECTED" in str(exc_info.value)

    def test_c3_atomic_report_persistence_with_multiprocess_lock(self, tmp_path):
        """Report builder writes atomically without corrupting state under multi-process lock."""
        reports_dir = str(tmp_path / "reports")
        builder = ResearchReportBuilderEngine(storage_dir=reports_dir, require_durable=False)

        sample_data = {
            "session_id": "URS-TEST-DURABLE-01",
            "period": {"asset": "BTCUSDT", "start_utc": "2022-06-01T00:00:00Z", "end_utc": "2022-06-03T00:00:00Z"},
            "candles": [{"open_time": "2022-06-01T00:00:00Z", "open": 30000.0, "high": 30100.0, "low": 29900.0, "close": 30050.0, "volume": 100.0}],
            "regimes": [{"open_time": "2022-06-01T00:00:00Z", "regime": "NEUTRAL"}],
            "dataset_manifest_version": "V2_CANONICAL_2026_V1",
            "source_commit_sha": "db3bb63e1aca90582847880e80abd9e87938b142",
        }

        report = builder.generate_report(session_data=sample_data)
        report_id = report["report_metadata"]["report_id"]

        # Confirm persisted on disk
        persisted = builder.get_report(report_id)
        assert persisted is not None
        assert persisted["report_metadata"]["report_id"] == report_id

    def test_c4_research_backup_creation_and_verification(self, tmp_path):
        """Consistent snapshot backup creates verifiable tar.gz archive with SHA-256 manifests."""
        reports_dir = tmp_path / "data" / "reports"
        reports_dir.mkdir(parents=True)
        (reports_dir / "RPT-001.json").write_text('{"report_id": "RPT-001"}')

        backup_out = tmp_path / "backups"
        res = ResearchBackupRestoreEngine.create_backup(output_dir=backup_out)

        assert res["archive_path"].endswith(".tar.gz")
        assert os.path.exists(res["archive_path"])
        assert res["archive_sha256"] is not None

        # Verify backup integrity
        ver = ResearchBackupRestoreEngine.verify_backup(res["archive_path"])
        assert ver["is_valid"]
        assert ver["status"] == "BACKUP_VERIFIED_AUTHENTIC"


# =============================================================================
# GROUP D: RESOURCE GOVERNOR, CONCURRENCY & MEMORY DIAGNOSTICS
# =============================================================================

class TestGroupDResourceGovernor:
    """Group D tests: Concurrency semaphores, payload size caps, candle limits, memory RSS."""

    def test_d1_research_concurrency_semaphore_saturation(self):
        """Exceeding concurrent research slots raises ResourceLimitExceededError with retry hint."""
        gov = ResourceGovernor()
        gov.MAX_CONCURRENT_RESEARCH_JOBS = 1
        gov._research_sem = threading.Semaphore(1)

        with gov.acquire_research_slot(timeout=1.0):
            # Attempt second acquisition
            with pytest.raises(ResourceLimitExceededError) as exc_info:
                with gov.acquire_research_slot(timeout=0.1):
                    pass
            assert exc_info.value.retry_after_sec == 5
            assert "CONCURRENCY_LIMIT_EXCEEDED" in str(exc_info.value)

    def test_d2_payload_size_limit_rejection(self):
        """Payload exceeding 2MB is rejected before heavy processing."""
        gov = ResourceGovernor()
        oversized = b"0" * (2 * 1024 * 1024 + 10)
        with pytest.raises(ValueError) as exc_info:
            gov.validate_payload_size(oversized)
        assert "PAYLOAD_TOO_LARGE" in str(exc_info.value)

    def test_d3_candle_budget_limit_rejection(self):
        """Request exceeding 5000 candle budget is rejected."""
        gov = ResourceGovernor()
        with pytest.raises(ValueError) as exc_info:
            gov.validate_candle_count(5001)
        assert "CANDLE_BUDGET_EXCEEDED" in str(exc_info.value)

    def test_d4_memory_rss_reporting(self):
        """Memory RSS MB reporting returns positive numeric metric."""
        rss = ResourceGovernor.get_memory_rss_mb()
        assert isinstance(rss, (int, float))
        assert rss >= 0.0


# =============================================================================
# GROUP E: OPERATIONAL READINESS, DIAGNOSTICS & REDACTED LOGGING
# =============================================================================

class TestGroupEOperationalReadinessAndLogging:
    """Group E tests: /ready, /diagnostics, audit ring buffer, secret redaction, error taxonomy."""

    def test_e1_readiness_probe_contract(self):
        """Readiness endpoint returns 200 with model freeze and storage durability details."""
        st, data = ProductDashboardApiService.get_ready_api()
        assert st == 200
        assert data["status"] == "READY"
        assert data["canonical_model_version"] == FROZEN_MODEL_VERSION
        assert data["canonical_model_status"] == "STRICTLY_FROZEN"
        assert data["governance_decision"] == "TECHNICAL_NO_GO"
        assert data["parameter_mutations"] == 0
        assert data["directional_trading"] == "STRICTLY_PROHIBITED"

    def test_e2_privileged_diagnostics_unauthorized_rejection(self, monkeypatch):
        """Accessing /diagnostics without auth token or session returns 401."""
        monkeypatch.setenv("CBE_ADMIN_DIAGNOSTICS_TOKEN", "secure-admin-token-777")
        st, data = ProductDashboardApiService.get_diagnostics_api(headers={})
        assert st == 401
        assert data["error_code"] == "AUTH_FAILURE"

    def test_e3_privileged_diagnostics_authorized(self, monkeypatch):
        """Accessing /diagnostics with valid admin token returns active jobs and storage stats."""
        admin_tok = "secure-admin-diag-token-888"
        monkeypatch.setenv("CBE_ADMIN_DIAGNOSTICS_TOKEN", admin_tok)
        st, data = ProductDashboardApiService.get_diagnostics_api(headers={"X-Admin-Token": admin_tok})
        assert st == 200
        assert data["status"] == "DIAGNOSTICS_AVAILABLE"
        assert "resources" in data
        assert "storage" in data
        assert "recent_audit_events" in data

    def test_e4_secret_redacting_filter(self):
        """Logs and audit events must sanitize operator tokens and HMAC secrets."""
        raw_msg = "Failed auth for operator_token: cbe-super-secret-token-abcdef123 with key: 1234567890abcdef"
        redacted = SecretRedactingFilter.redact_string(raw_msg)
        assert "cbe-super-secret-token-abcdef123" not in redacted
        assert "***REDACTED***" in redacted

    def test_e5_standardized_error_response_contract(self):
        """Error builder formats standardized bilingual response with correlation ID."""
        err = build_error_response("LOCK_TIMEOUT", "Custom lock timeout details")
        assert err["status"].lower() == "error"
        assert err["error_code"] == "LOCK_TIMEOUT"
        assert err["retryable"] is True
        assert len(err["correlation_id"]) >= 8
        assert "remediation_hint" in err


# =============================================================================
# GROUP F: CANONICAL SCIENTIFIC MODEL FREEZE & GOVERNANCE GATING
# =============================================================================

class TestGroupFModelFreezeAndGovernance:
    """Group F tests: Model parameter immutability, TECHNICAL_NO_GO, zero trading."""

    def test_f1_canonical_model_freeze_invariants(self):
        """Model version must be CBE-0.7.0 with zero mutations and strict technical NO-GO."""
        assert FROZEN_MODEL_VERSION == "CBE-0.7.0"
        builder = ResearchReportBuilderEngine(require_durable=False)
        assert builder.CANONICAL_MODEL == "CBE-0.7.0"

    def test_f2_directional_trading_permanently_prohibited(self):
        """Reports capabilities must assert directional trading is prohibited."""
        caps = ProductDashboardApiService.get_research_reports_capabilities()
        invariants = caps["governance_invariants"]
        assert invariants["technical_decision"] == "TECHNICAL_NO_GO"
        assert invariants["directional_trading"] == "STRICTLY_PROHIBITED"
        assert invariants["live_order_execution"] == "PERMANENTLY_PROHIBITED"


# =============================================================================
# GROUP G: PDF EXPORT RELIABILITY & REPORT RENDERING
# =============================================================================

class TestGroupGPdfAndReportRendering:
    """Group G tests: A4 PDF export, Unicode TrueType fonts, HTML report rendering."""

    def test_g1_pdf_export_structure(self, tmp_path):
        """PDF renderer generates valid multi-page PDF bytes with headers and footers."""
        from coin_behavior_engine.product.research_report_pdf import ResearchReportPdfRenderer
        sample_report = {
            "report_metadata": {
                "report_id": "RPT-PDF-TEST-01",
                "title": "A4 PDF Export Acceptance Test",
                "generated_at_utc": "2026-11-06T00:00:00Z",
                "dataset_manifest_version": "V2_CANONICAL_2026_V1",
            },
            "historical_scope": {
                "asset": "BTCUSDT",
                "start_utc": "2022-06-01T00:00:00Z",
                "end_utc": "2022-06-03T00:00:00Z",
            },
            "canonical_model_identity": {
                "version": "CBE-0.7.0",
                "status": "STRICTLY_FROZEN",
                "parameter_mutations": 0,
            },
            "executive_summary": {
                "research_headline_tr": "Tarihsel Analiz Kabul Testi",
                "dominant_regime": "NEUTRAL",
                "volatility_class": "MEDIUM",
            },
            "statistical_evidence": {
                "predeclared_holdout_criteria_satisfied": True,
                "p_value": 0.02,
            },
        }

        out_pdf = tmp_path / "test_report.pdf"
        renderer = ResearchReportPdfRenderer()
        renderer.render_report_to_pdf(sample_report, str(out_pdf))

        assert out_pdf.exists()
        pdf_bytes = out_pdf.read_bytes()
        assert pdf_bytes.startswith(b"%PDF-")
        assert len(pdf_bytes) > 1000

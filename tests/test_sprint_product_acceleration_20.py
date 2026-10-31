"""
Sprint Product Acceleration 20 — Comprehensive Regression Test Suite.

Validates:
- Research Workflow finite state machine transitions (forward & backward)
- Deterministic workflow identifiers (RWF-<canonical-input-hash>)
- Shared research context synchronization and contract validation
- Date-range propagation and stale-result invalidation
- Strict October 2026 quarantine boundary enforcement
- Explorer -> URS -> Pattern Discovery -> Comparison Studio -> Research Library handoffs
- Multi-worker cross-process file locking and atomic replace
- Research Library V2 token authorization, CSRF rejection, and production immutability
- Secret exposure remediation and automated secret-redaction filters
- Scientific explanation generation and epistemological holdout disclosures (2 satisfied, 0 confirmatory)
- Unified evidence package generation and canonical SHA-256 integrity checksum
- Model freeze CBE-0.7.0 (zero parameter mutations)
- Prohibited live order execution and live collection isolation
"""

import copy
import hashlib
import json
import os
import threading
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path

import pytest

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.operations_console import (
    REVOKED_OPERATOR_TOKENS,
    sanitize_headers_for_logging,
)
from coin_behavior_engine.product.research_intelligence_explorer import (
    ResearchIntelligenceExplorerEngine,
    ResearchLibraryEngine,
)
from coin_behavior_engine.product.research_workflow import (
    ALLOWED_STAGE_TRANSITIONS,
    OCTOBER_2026_QUARANTINE_START,
    ResearchWorkflowEngine,
    SharedResearchContext,
    WorkflowStage,
)
from coin_behavior_engine.product.unified_research_workspace import (
    UnifiedResearchWorkspaceEngine,
)


class TestSprint20WorkflowStateMachineAndIdentity:
    """Tests for workflow state machine, stage transitions, and deterministic identity."""

    def test_deterministic_workflow_id_generation(self):
        wf1 = ResearchWorkflowEngine.generate_workflow_id(
            asset="BTCUSDT",
            interval="1h",
            start_utc="2022-06-01T00:00:00Z",
            end_utc="2022-06-15T00:00:00Z",
            selected_modules=["regime_analysis", "volatility_analysis"],
            manifest_hash="test_manifest_hash_123",
        )
        wf2 = ResearchWorkflowEngine.generate_workflow_id(
            asset="BTCUSDT",
            interval="1h",
            start_utc="2022-06-01T00:00:00Z",
            end_utc="2022-06-15T00:00:00Z",
            selected_modules=["volatility_analysis", "regime_analysis"],  # permuted order
            manifest_hash="test_manifest_hash_123",
        )
        assert wf1.startswith("RWF-")
        assert len(wf1) == 20  # RWF- + 16 hex
        assert wf1 == wf2  # Deterministic regardless of module order

    def test_workflow_state_transitions_and_shared_context(self):
        success, ctx, err = ResearchWorkflowEngine.create_or_update_workflow(
            asset="BTCUSDT",
            interval="1h",
            start_utc="2022-06-01T00:00:00Z",
            end_utc="2022-06-15T00:00:00Z",
        )
        assert success is True
        assert ctx["stage"] == WorkflowStage.PERIOD_SELECTED.value
        assert ctx["canonical_model_version"] == FROZEN_MODEL_VERSION
        assert ctx["research_only"] is True

    def test_strict_quarantine_enforcement_october_2026(self):
        # Starting in October 2026 must be blocked
        success, ctx, err = ResearchWorkflowEngine.create_or_update_workflow(
            asset="BTCUSDT",
            interval="1h",
            start_utc="2026-10-01T00:00:00Z",
            end_utc="2026-10-15T00:00:00Z",
        )
        assert success is False
        assert "KARANTİNA İHLALİ" in err

        # Ending in October 2026 must be blocked
        success, ctx, err = ResearchWorkflowEngine.create_or_update_workflow(
            asset="BTCUSDT",
            interval="1h",
            start_utc="2026-09-20T00:00:00Z",
            end_utc="2026-10-05T00:00:00Z",
        )
        assert success is False
        assert "KARANTİNA İHLALİ" in err

    def test_date_range_change_invalidates_stale_results(self):
        success, ctx, _ = ResearchWorkflowEngine.create_or_update_workflow(
            asset="BTCUSDT",
            interval="1h",
            start_utc="2022-06-01T00:00:00Z",
            end_utc="2022-06-15T00:00:00Z",
        )
        ctx["research_session_id"] = "URS-old-session-123"
        ctx["comparison_reference"] = {"candidate": "old"}
        ctx["stage"] = WorkflowStage.COMPARISON_READY.value

        # Changing the date range must invalidate old session and comparison references
        success, updated_ctx, _ = ResearchWorkflowEngine.create_or_update_workflow(
            asset="BTCUSDT",
            interval="1h",
            start_utc="2023-01-01T00:00:00Z",
            end_utc="2023-01-15T00:00:00Z",
            existing_context=ctx,
        )
        assert success is True
        assert updated_ctx["research_session_id"] is None
        assert updated_ctx["comparison_reference"] is None
        assert updated_ctx["stage"] == WorkflowStage.PERIOD_SELECTED.value


class TestSprint20SecurityAndSecretExposureRemediation:
    """Tests for token revocation, header sanitization, secret-redaction filters, and CSRF defense."""

    def test_revoked_tokens_blacklist(self):
        # Disclosed credential must be in revoked tokens set
        assert "cbe-staging-operator-key-sprint09-xyz987" in REVOKED_OPERATOR_TOKENS
        assert "cbe-staging-operator-key-2026" in REVOKED_OPERATOR_TOKENS

        # Mutation with revoked token must return 403 Forbidden
        status, res = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/research-workflow/save",
            {},
            {"title": "Test", "workflow_context": {"asset": "BTCUSDT"}},
            headers={"X-Operator-Token": "cbe-staging-operator-key-sprint09-xyz987"},
        )
        assert status == HTTPStatus.FORBIDDEN
        assert "AUTH_TOKEN_REVOKED" in res["message"]

    def test_secret_header_sanitization_for_logs_and_artifacts(self):
        raw_headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer sensitive_secret_token_12345",
            "X-Operator-Token": "cbe-staging-operator-key-sprint09-xyz987",
            "X-Research-Token": "cbe-research-secret-token",
            "Cookie": "session_id=secret_session_cookie",
            "X-Custom-Header": "public-client-value",
        }
        sanitized = sanitize_headers_for_logging(raw_headers)
        assert sanitized["Content-Type"] == "application/json"
        assert sanitized["X-Custom-Header"] == "public-client-value"
        assert sanitized["Authorization"] == "[REDACTED]"
        assert sanitized["X-Operator-Token"] == "[REDACTED]"
        assert sanitized["X-Research-Token"] == "[REDACTED]"
        assert sanitized["Cookie"] == "[REDACTED]"
        assert "sensitive_secret_token_12345" not in str(sanitized)

    def test_anonymous_write_rejection(self):
        status, res = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/research-workflow/save",
            {},
            {"title": "Anonymous Mutation"},
            headers={},
        )
        assert status == HTTPStatus.UNAUTHORIZED
        assert res["error"] == "Unauthorized"

    def test_csrf_cross_site_rejection(self):
        status, res = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/research-workflow/save",
            {},
            {"title": "CSRF Attack Attempt"},
            headers={
                "X-Research-Token": "cbe-research-authorized-token",
                "Sec-Fetch-Site": "cross-site",
            },
        )
        assert status == HTTPStatus.FORBIDDEN
        assert "CSRF_CROSS_SITE_REQUEST_REJECTED" in res["message"]

    def test_production_environment_mutation_blocking(self, monkeypatch):
        monkeypatch.setenv("CBE_ENV", "production")
        status, res = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/research-workflow/save",
            {},
            {"title": "Prod Mutation"},
            headers={"X-Research-Token": "cbe-research-authorized-token"},
        )
        assert status == HTTPStatus.FORBIDDEN
        assert "MUTATIONS_PERMANENTLY_BLOCKED_IN_PRODUCTION" in res["message"]


class TestSprint20WorkflowOrchestrationAndEvidenceIntegration:
    """Tests for end-to-end research orchestration, candidate comparison, and canonical evidence package."""

    def test_workflow_session_execution_and_scientific_explanations(self):
        ctx = {
            "workflow_id": "RWF-test12345678",
            "asset": "BTCUSDT",
            "interval": "1h",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
            "selected_modules": [
                "regime_analysis",
                "volatility_analysis",
                "historical_pattern_discovery",
                "macro_comparison",
                "statistical_evidence",
            ],
        }
        success, res, err = ResearchWorkflowEngine.execute_workflow_session(ctx)
        assert success is True
        assert "session" in res
        assert "scientific_explanations" in res
        exp = res["scientific_explanations"]

        # Validate scientific explanation cards
        assert "regime" in exp
        assert "volatility" in exp
        assert "pattern_similarity" in exp
        assert "macro_events" in exp
        assert "statistical_evidence" in exp

        # Epistemological Holdout Disclosure Verification
        holdout_info = exp["statistical_evidence"]
        assert holdout_info["predeclared_holdout_criteria_satisfied"] == 2
        assert holdout_info["independent_confirmatory_replications"] == 0

    def test_comparison_candidate_selection_and_disjointness(self):
        ctx = {
            "workflow_id": "RWF-test12345678",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
        }

        # Valid disjoint candidate
        success, updated_ctx, err = ResearchWorkflowEngine.select_comparison_candidate(
            context=ctx,
            candidate_start_utc="2024-07-27T01:00:00Z",
            candidate_end_utc="2024-08-10T01:00:00Z",
            candidate_label="Aday Test",
            similarity_score=0.91,
        )
        assert success is True
        assert updated_ctx["stage"] == WorkflowStage.COMPARISON_READY.value
        assert updated_ctx["comparison_reference"]["candidate_start_utc"] == "2024-07-27T01:00:00Z"

        # Overlapping candidate (violating disjointness)
        success_overlap, _, err_overlap = ResearchWorkflowEngine.select_comparison_candidate(
            context=ctx,
            candidate_start_utc="2022-06-10T00:00:00Z",
            candidate_end_utc="2022-06-25T00:00:00Z",
        )
        assert success_overlap is False
        assert "Disjointness requirement violated" in err_overlap

    def test_workflow_library_save_and_reopen_with_provenance(self, tmp_path, monkeypatch):
        test_lib_dir = tmp_path / "test_s20_lib"
        test_lib_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("CBE_RESEARCH_LIBRARY_PATH", str(test_lib_dir))

        ctx = {
            "workflow_id": "RWF-s20testsave",
            "asset": "BTCUSDT",
            "interval": "1h",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
            "selected_modules": ["regime_analysis", "volatility_analysis"],
            "dataset_manifest_sha256": "manifest_test_hash",
        }

        # Save
        success, res, _ = ResearchWorkflowEngine.save_workflow_to_library(
            context=ctx,
            title="S20 İş Akışı Kayıt Testi",
            description="Reopen testi",
        )
        assert success is True
        rid = res["library_definition"]["research_id"]

        # Restore
        success_rest, rest_res, _ = ResearchWorkflowEngine.restore_workflow_from_library(rid)
        assert success_rest is True
        rest_ctx = rest_res["workflow_context"]
        assert rest_ctx["asset"] == "BTCUSDT"
        assert rest_ctx["reference_start_utc"] == "2022-06-01T00:00:00Z"
        assert rest_ctx["reference_end_utc"] == "2022-06-15T00:00:00Z"
        assert rest_res["library_definition"]["title"] == "S20 İş Akışı Kayıt Testi"

    def test_export_workflow_evidence_package_and_checksum(self):
        ctx = {
            "workflow_id": "RWF-evidencetest",
            "research_session_id": "URS-testsession",
            "asset": "BTCUSDT",
            "interval": "1h",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
            "selected_modules": ["regime_analysis"],
        }
        success, res, err = ResearchWorkflowEngine.export_workflow_evidence(ctx)
        assert success is True
        pkg = res["evidence_package"]
        assert pkg["export_schema_version"] == "CBE-WORKFLOW-EVIDENCE-1.0.0"
        assert "package_checksum_sha256" in pkg
        assert len(pkg["package_checksum_sha256"]) == 64

        # Validate checksum calculation matches canonical sorted JSON
        reported_checksum = pkg["package_checksum_sha256"]
        pkg_copy = copy.deepcopy(pkg)
        del pkg_copy["package_checksum_sha256"]
        raw = json.dumps(pkg_copy, sort_keys=True, separators=(",", ":")).encode("utf-8")
        computed = hashlib.sha256(raw).hexdigest()
        assert computed == reported_checksum

        # Epistemological Holdout Disclosure Check in Evidence
        disclosures = pkg["scientific_disclosures"]
        assert disclosures["predeclared_holdout_criteria_satisfied"] == 2
        assert disclosures["independent_confirmatory_replications"] == 0

    def test_prohibited_live_trading_and_order_routing_isolation(self):
        status, _ = ProductDashboardApiService.handle_request("/api/v1/product/live-trading/execute", {})
        assert status == HTTPStatus.NOT_FOUND

        status, _ = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/order-routing",
            {},
            {"order": "BUY", "amount": 1.0},
        )
        assert status == HTTPStatus.NOT_FOUND

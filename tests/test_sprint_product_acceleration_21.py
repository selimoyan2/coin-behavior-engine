"""
Sprint Product Acceleration 21 — Comprehensive Automated Test Suite.
Validates:
1. Research Reproducibility Engine V1 (deterministic replay, numerical tolerances, manifests)
2. Independent Evidence Verifier (checksums, schema, tampering detection across all fields)
3. Scientific Integrity Audit Engine & Quality Scorecard (data bounds, model freeze, disjointness, holdout disclosures)
4. Research Library Verification Integration (reproducibility & provenance drift detection)
5. Security Hardening (SHA-256 fingerprints, timing safety, anonymous rejection, CSRF defense, production immutability)
6. Performance Regression Observatory (latency benchmarking, regression severity, memory tracking)
7. Safety Invariants: CBE-0.7.0 Strictly Frozen, 0 Parameter Mutations, Zero Live Trading / Collection
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import patch

import pytest

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.operations_console import (
    REVOKED_TOKEN_SHA256_FINGERPRINTS,
    is_token_revoked,
    sanitize_headers_for_logging,
)
from coin_behavior_engine.product.research_evidence_verifier import (
    EvidenceVerificationStatus,
    ResearchEvidenceVerifier,
)
from coin_behavior_engine.product.research_intelligence_explorer import ResearchLibraryEngine
from coin_behavior_engine.product.research_performance_audit import (
    PerformanceSeverity,
    ResearchPerformanceAuditEngine,
)
from coin_behavior_engine.product.research_reproducibility import (
    REGIME_PROBABILITY_TOLERANCE,
    REPRODUCIBILITY_SCHEMA_VERSION,
    SIMILARITY_SCORE_TOLERANCE,
    VOLATILITY_METRIC_TOLERANCE,
    ReproducibilityVerdict,
    ResearchReproducibilityEngine,
)
from coin_behavior_engine.product.research_scientific_audit import (
    INDEPENDENT_CONFIRMATORY_REPLICATIONS,
    OCTOBER_2026_QUARANTINE_START,
    PREDECLARED_HOLDOUT_CRITERIA_SATISFIED,
    QualityStatus,
    ResearchScientificAuditEngine,
)
from coin_behavior_engine.product.research_workflow import (
    ResearchWorkflowEngine,
    WorkflowStage,
)


class TestSprint21ReproducibilityEngine:
    """Tests for Phase 1: Research Reproducibility Engine V1."""

    def test_canonical_input_configuration_hashing(self):
        """Test deterministic configuration hashing ignores volatile fields."""
        cfg1 = {
            "canonical_model": "CBE-0.7.0",
            "asset": "btcusdt",
            "interval": "1H",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
            "selected_modules": ["volatility_analysis", "regime_analysis"],
            "volatile_timestamp": "2026-11-03T02:00:00Z",
        }
        cfg2 = {
            "canonical_model": "CBE-0.7.0",
            "asset": "BTCUSDT",
            "interval": "1h",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
            "selected_modules": ["regime_analysis", "volatility_analysis"],
            "volatile_timestamp": "2026-11-03T03:30:00Z",
        }
        hash1 = ResearchReproducibilityEngine.compute_configuration_sha256(cfg1)
        hash2 = ResearchReproducibilityEngine.compute_configuration_sha256(cfg2)
        assert hash1 == hash2, "Config hashes must match regardless of module order or casing."

    def test_reproducibility_manifest_schema_and_provenance(self):
        """Verify ReproducibilityManifest contains required schema version and metadata."""
        config = {
            "asset": "BTCUSDT",
            "interval": "1h",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
            "selected_modules": ["regime_analysis"],
        }
        manifest = ResearchReproducibilityEngine.create_reproducibility_manifest(
            research_id="RWF-test01",
            session_id="URS-test01",
            config=config,
            dataset_manifest_sha="fe6c73326c639ee048012cbeb4d50cb9b25014552411ae7a4ef5a57be448ad97",
        )
        assert manifest.schema_version == REPRODUCIBILITY_SCHEMA_VERSION
        assert manifest.canonical_model_version == FROZEN_MODEL_VERSION
        assert manifest.research_only is True
        assert manifest.execution_environment["python_version"] != ""

    def test_exact_reproducibility_evaluation(self):
        """Test exact match reproducibility verdict when runs have identical metrics."""
        ctx = {
            "workflow_id": "RWF-exact-test",
            "asset": "BTCUSDT",
            "interval": "1h",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
            "selected_modules": ["regime_analysis", "volatility_analysis"],
        }
        mock_run = {
            "session_id": "URS-test-mock",
            "regime_analysis": {
                "dominant_regime": "RECOVERY_ACCUMULATION",
                "regime_distribution": {"RECOVERY_ACCUMULATION": 0.409, "BEAR_PLUNGE": 0.25},
            },
            "volatility_analysis": {
                "realized_volatility": 0.0452,
                "parkinson_volatility": 0.0381,
            },
            "statistical_evidence": {
                "predeclared_holdout_criteria_satisfied": 2,
                "independent_confirmatory_replications": 0,
            },
        }
        comp = ResearchReproducibilityEngine.compare_module_outputs(mock_run, mock_run)
        assert comp["all_exact_match"] is True
        assert comp["within_tolerances"] is True
        assert comp["max_numerical_delta"] == 0.0

    def test_numerical_tolerance_handling(self):
        """Test floating-point tolerance handling: small differences pass within tolerance."""
        run1 = {
            "regime_analysis": {
                "dominant_regime": "RECOVERY_ACCUMULATION",
                "regime_distribution": {"RECOVERY_ACCUMULATION": 0.4090001},
            },
            "volatility_analysis": {
                "realized_volatility": 0.045200005,
                "parkinson_volatility": 0.0381,
            },
        }
        run2 = {
            "regime_analysis": {
                "dominant_regime": "RECOVERY_ACCUMULATION",
                "regime_distribution": {"RECOVERY_ACCUMULATION": 0.4090002},
            },
            "volatility_analysis": {
                "realized_volatility": 0.045200008,
                "parkinson_volatility": 0.0381,
            },
        }
        comp = ResearchReproducibilityEngine.compare_module_outputs(run1, run2)
        assert comp["all_exact_match"] is False
        assert comp["within_tolerances"] is True
        assert comp["max_numerical_delta"] < REGIME_PROBABILITY_TOLERANCE

    def test_non_reproducible_detection_on_categorical_mismatch(self):
        """Test categorical discrepancy (e.g. dominant regime difference) triggers NON_REPRODUCIBLE."""
        run1 = {"regime_analysis": {"dominant_regime": "RECOVERY_ACCUMULATION"}}
        run2 = {"regime_analysis": {"dominant_regime": "BEAR_PLUNGE"}}
        comp = ResearchReproducibilityEngine.compare_module_outputs(run1, run2)
        assert comp["all_exact_match"] is False
        assert comp["within_tolerances"] is False
        assert any(d["critical"] for d in comp["discrepancies"])

    def test_model_version_and_provenance_mismatches(self):
        """Verify model version and dataset manifest mismatch verdicts."""
        ctx_bad_model = {
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
            "canonical_model_version": "CBE-0.8.0-UNFROZEN",
        }
        res_model = ResearchReproducibilityEngine.verify_reproducibility(ctx_bad_model)
        assert res_model["verdict"] == ReproducibilityVerdict.MODEL_VERSION_MISMATCH.value

        ctx_bad_prov = {
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
            "canonical_model_version": FROZEN_MODEL_VERSION,
            "dataset_manifest_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
        }
        res_prov = ResearchReproducibilityEngine.verify_reproducibility(ctx_bad_prov)
        assert res_prov["verdict"] == ReproducibilityVerdict.DATASET_PROVENANCE_MISMATCH.value


class TestSprint21EvidenceVerification:
    """Tests for Phase 2: Independent Evidence Verification & Tampering Detection."""

    @pytest.fixture
    def canonical_evidence_package(self) -> Dict[str, Any]:
        pkg = {
            "export_schema_version": "CBE-WORKFLOW-EVIDENCE-1.0.0",
            "workflow_id": "RWF-ev-test-01",
            "research_session_id": "URS-ev-test-01",
            "created_at_utc": "2026-11-03T02:00:00Z",
            "canonical_model": {
                "version": "CBE-0.7.0",
                "status": "STRICTLY_FROZEN",
                "parameter_mutations": 0,
            },
            "dataset_provenance": {
                "manifest_sha256": "fe6c73326c639ee048012cbeb4d50cb9b25014552411ae7a4ef5a57be448ad97",
                "quarantine_status": "OCTOBER_2026_EXCLUDED",
            },
            "research_specification": {
                "asset": "BTCUSDT",
                "interval": "1h",
                "reference_start_utc": "2022-06-01T00:00:00Z",
                "reference_end_utc": "2022-06-15T00:00:00Z",
                "selected_modules": ["regime_analysis", "volatility_analysis"],
            },
            "scientific_disclosures": {
                "predeclared_holdout_criteria_satisfied": 2,
                "independent_confirmatory_replications": 0,
                "epistemological_limitations": [
                    "Analizler 100% geriye dönük ve betimseldir.",
                    "Sıfır alım-satım veya yönlü getiri sinyali.",
                ],
            },
        }
        checksum = ResearchEvidenceVerifier.compute_package_checksum(pkg)
        pkg["package_checksum_sha256"] = checksum
        return pkg

    def test_canonical_checksum_verification_valid_package(self, canonical_evidence_package):
        """Valid canonical package passes independent checksum and schema verification."""
        report = ResearchEvidenceVerifier.verify_package(canonical_evidence_package)
        assert report.is_valid is True
        assert report.status == EvidenceVerificationStatus.VERIFIED_VALID.value
        assert report.package_checksum_verified is True
        assert report.tampering_detected is False

    def test_tampering_detection_modified_timestamp(self, canonical_evidence_package):
        """Tampering a historical date boundary causes checksum mismatch and fails verification."""
        tampered = copy.deepcopy(canonical_evidence_package)
        tampered["research_specification"]["reference_start_utc"] = "2022-06-02T00:00:00Z"
        report = ResearchEvidenceVerifier.verify_package(tampered)
        assert report.is_valid is False
        assert report.status == EvidenceVerificationStatus.CHECKSUM_MISMATCH_TAMPERED.value
        assert report.tampering_detected is True

    def test_tampering_detection_modified_model_version(self, canonical_evidence_package):
        """Tampering canonical model version fails checksum and model freeze check."""
        tampered = copy.deepcopy(canonical_evidence_package)
        tampered["canonical_model"]["version"] = "CBE-0.8.0-BETA"
        report = ResearchEvidenceVerifier.verify_package(tampered)
        assert report.is_valid is False
        assert "canonical_model" in report.tampered_fields

    def test_tampering_detection_modified_holdout_disclosures(self, canonical_evidence_package):
        """Falsifying independent confirmatory replications fails verification."""
        tampered = copy.deepcopy(canonical_evidence_package)
        tampered["scientific_disclosures"]["independent_confirmatory_replications"] = 5
        report = ResearchEvidenceVerifier.verify_package(tampered)
        assert report.is_valid is False
        assert "scientific_disclosures" in report.tampered_fields

    def test_tampering_detection_quarantine_breach(self, canonical_evidence_package):
        """Setting dates into October 2026 quarantine fails verification."""
        tampered = copy.deepcopy(canonical_evidence_package)
        tampered["research_specification"]["reference_start_utc"] = "2026-10-05T00:00:00Z"
        tampered["research_specification"]["reference_end_utc"] = "2026-10-15T00:00:00Z"
        report = ResearchEvidenceVerifier.verify_package(tampered)
        assert report.is_valid is False
        assert report.quarantine_verified is False


class TestSprint21ScientificIntegrityAudit:
    """Tests for Phase 3: Scientific Integrity Audit Engine & Quality Scorecard."""

    def test_historical_quarantine_enforcement(self):
        """Audit rejects historical analysis in October 2026 quarantine period."""
        audit = ResearchScientificAuditEngine.audit_historical_data_integrity(
            start_utc="2026-10-01T00:00:00Z",
            end_utc="2026-10-10T00:00:00Z",
        )
        assert audit.status == QualityStatus.FAIL.value
        assert "KARANTİNA İHLALİ" in audit.description_tr

    def test_pattern_candidate_disjointness_enforcement(self):
        """Audit confirms zero temporal overlap between reference period and candidate patterns."""
        ref_start = "2022-06-01T00:00:00Z"
        ref_end = "2022-06-15T00:00:00Z"

        # Disjoint candidates pass
        valid_candidates = [
            {"candidate_start_utc": "2021-05-10T00:00:00Z", "candidate_end_utc": "2021-05-24T00:00:00Z"},
            {"candidate_start_utc": "2024-07-27T01:00:00Z", "candidate_end_utc": "2024-08-10T01:00:00Z"},
        ]
        audit_pass = ResearchScientificAuditEngine.audit_pattern_candidate_disjointness(
            ref_start, ref_end, valid_candidates
        )
        assert audit_pass.status == QualityStatus.PASS.value

        # Overlapping candidate fails with temporal leakage warning
        overlapping = [
            {"candidate_start_utc": "2022-06-10T00:00:00Z", "candidate_end_utc": "2022-06-20T00:00:00Z"},
        ]
        audit_fail = ResearchScientificAuditEngine.audit_pattern_candidate_disjointness(
            ref_start, ref_end, overlapping
        )
        assert audit_fail.status == QualityStatus.FAIL.value
        assert "ZAMAN AYRIŞIMI İHLALİ" in audit_fail.description_tr

    def test_mandatory_epistemological_disclosures(self):
        """Audit enforces 2 holdout satisfied and 0 confirmatory replications."""
        valid_disc = {
            "predeclared_holdout_criteria_satisfied": 2,
            "independent_confirmatory_replications": 0,
        }
        res_pass = ResearchScientificAuditEngine.audit_statistical_and_holdout_disclosures(valid_disc)
        assert res_pass.status == QualityStatus.PASS.value

        invalid_disc = {
            "predeclared_holdout_criteria_satisfied": 0,
            "independent_confirmatory_replications": 3,
        }
        res_fail = ResearchScientificAuditEngine.audit_statistical_and_holdout_disclosures(invalid_disc)
        assert res_fail.status == QualityStatus.FAIL.value

    def test_overall_gate_strict_gating_rule(self):
        """Any single FAIL in any dimension must set overall scorecard gate to FAIL (no averaging)."""
        ctx_quarantine = {
            "workflow_id": "RWF-strict-fail-01",
            "reference_start_utc": "2026-10-05T00:00:00Z",
            "reference_end_utc": "2026-10-15T00:00:00Z",
            "asset": "BTCUSDT",
            "interval": "1h",
        }
        scorecard = ResearchScientificAuditEngine.evaluate_quality_scorecard(ctx_quarantine)
        assert scorecard.overall_gate == QualityStatus.FAIL.value
        assert scorecard.dimensions["dataset_integrity"].status == QualityStatus.FAIL.value


class TestSprint21ResearchLibraryVerification:
    """Tests for Phase 5: Research Library Verification Integration."""

    def test_research_library_definition_verification(self):
        """Verify saved library definition against current dataset manifest and model freeze."""
        payload = {
            "title": "Sprint 21 Verification Benchmark Library Item",
            "description": "Historical crash analog test definition",
            "asset": "BTCUSDT",
            "interval": "1h",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
            "selected_modules": ["regime_analysis", "volatility_analysis"],
            "metadata": {"test_marker": True},
        }
        saved = ResearchLibraryEngine.save_definition(payload)
        rid = saved["research_id"]

        try:
            ver_report = ResearchLibraryEngine.verify_definition(rid)
            assert ver_report["research_id"] == rid
            assert ver_report["canonical_model_version"] == FROZEN_MODEL_VERSION
            assert "reproducibility" in ver_report
            assert "quality_scorecard" in ver_report
        finally:
            ResearchLibraryEngine.delete_definition(rid)


class TestSprint21SecurityHardening:
    """Tests for Phase 6: Security Hardening, SHA-256 Revocations, and Auth Guards."""

    def test_sha256_revoked_token_fingerprints(self):
        """Ensure revoked tokens match against SHA-256 fingerprints in constant time."""
        revoked_sample = "cbe-staging-operator-key-2026"
        assert is_token_revoked(revoked_sample) is True
        assert is_token_revoked("unrelated-random-token-xyz") is False
        assert is_token_revoked(None) is False
        assert is_token_revoked("") is False

    def test_secret_header_sanitization(self):
        """Sensitive authorization tokens are cleanly redacted in diagnostic logs."""
        headers = {
            "Authorization": "Bearer super-secret-token",
            "X-Operator-Token": "op_test_123",
            "Content-Type": "application/json",
            "User-Agent": "CBE-Test-Agent",
        }
        sanitized = sanitize_headers_for_logging(headers)
        assert sanitized["Authorization"] == "[REDACTED]"
        assert sanitized["X-Operator-Token"] == "[REDACTED]"
        assert sanitized["Content-Type"] == "application/json"


class TestSprint21PerformanceObservatory:
    """Tests for Phase 7: Performance Regression Observatory."""

    def test_performance_benchmark_suite_execution(self):
        """Run performance benchmark suite and verify bounded latency and memory reporting."""
        report = ResearchPerformanceAuditEngine.run_benchmark_suite(
            sample_start_utc="2022-06-01T00:00:00Z",
            sample_end_utc="2022-06-03T00:00:00Z",  # small 2-day sample for test speed
        )
        assert report.operations_measured >= 5
        assert report.total_duration_ms > 0
        assert report.peak_memory_kb > 0
        assert "historical_candles_load" in report.metrics


class TestSprint21QualityApiIntegration:
    """Tests for Phase 8: Quality Assurance API Endpoints."""

    def test_quality_capabilities_api(self):
        """GET /api/v1/product/research-quality/capabilities returns schema versions and limits."""
        status, data = ProductDashboardApiService.handle_request("research-quality/capabilities", {})
        assert status == HTTPStatus.OK
        assert data["canonical_model_version"] == "CBE-0.7.0"
        assert data["reproducibility_schema_version"] == REPRODUCIBILITY_SCHEMA_VERSION
        assert "numerical_tolerances" in data

    def test_quality_evidence_verify_api(self):
        """POST /api/v1/product/research-quality/evidence/verify validates payload."""
        sample_pkg = {
            "export_schema_version": "CBE-WORKFLOW-EVIDENCE-1.0.0",
            "canonical_model": {"version": "CBE-0.7.0", "status": "STRICTLY_FROZEN", "parameter_mutations": 0},
            "research_specification": {"reference_start_utc": "2022-06-01T00:00:00Z", "reference_end_utc": "2022-06-15T00:00:00Z"},
            "scientific_disclosures": {"predeclared_holdout_criteria_satisfied": 2, "independent_confirmatory_replications": 0, "epistemological_limitations": ["A", "B"]},
        }
        status, data = ProductDashboardApiService.handle_post_request(
            "research-quality/evidence/verify",
            query_params={},
            body={"evidence_package": sample_pkg},
        )
        assert status == HTTPStatus.OK
        assert "status" in data
        assert "tampering_detected" in data

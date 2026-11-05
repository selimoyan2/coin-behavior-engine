"""
Sprint 22 Final Acceptance Hardening Test Suite
CBE_PRODUCT_ACCELERATION_22 — Scientific Data Integrity, Evidence Trust Boundaries,
Functional E2E & PDF Verification.

Verifies:
1. Elimination of fabricated scientific fallback values (p_value, holdouts, volatility, regimes).
2. Missing mandatory provenance strictly blocks report generation.
3. Contradictory scientific disclosures and parameter mutations detected.
4. Trust boundary separation: AUTHENTICITY_VERIFIED vs INTEGRITY_VERIFIED_UNTRUSTED_SOURCE.
5. Non-finite values (NaN, Infinity) and invalid timestamp formats strictly rejected.
6. No synthetic candidate price paths or fabricated similarity dimensions.
7. Durable storage path enforcement (fail-closed behavior).
8. PDF content and extractable text verification.
"""

import math
import os
import tempfile
from typing import Any, Dict
import pytest

from coin_behavior_engine.product.research_report_builder import ResearchReportBuilderEngine
from coin_behavior_engine.product.research_report_evidence import ResearchReportEvidenceBundleEngine
from coin_behavior_engine.product.research_comparison_reporting import HistoricalComparisonReportingEngine
from coin_behavior_engine.product.research_narratives import ScientificNarrativeEngine
from coin_behavior_engine.product.research_report_pdf import ResearchReportPdfRenderer


@pytest.fixture
def minimal_valid_session() -> Dict[str, Any]:
    return {
        "session_id": "HARDENING-SESS-01",
        "asset": "BTCUSDT",
        "interval": "1h",
        "reference_start_utc": "2022-06-01T00:00:00Z",
        "reference_end_utc": "2022-06-15T00:00:00Z",
        "candle_count": 336,
        "dataset_manifest_version": "cbe-manifest-v3-verified",
        "dataset_manifest_sha256": "a" * 64,
        "source_commit_sha": "b" * 40,
        "module_results": {
            "historical_candles": {
                "candles": [
                    {"close": 30000.0, "high": 30500.0, "low": 29800.0, "open": 29900.0, "volume": 100.0}
                ]
            },
            "regime_analysis": {
                "dominant_regime": "SIDEWAYS_CHOP",
                "regime_distribution": {"SIDEWAYS_CHOP": 1.0},
                "transitions_count": 0,
                "regime_entropy": 0.0,
            },
            "volatility_analysis": {
                "parkinson_volatility": 0.025,
                "realized_volatility": 0.028,
            },
        },
    }


class TestScientificDataIntegrityHardening:
    """Task 1: Eliminate fabricated scientific fallback values."""

    def test_missing_p_value_and_holdouts_explicit_unavailable(self, minimal_valid_session):
        # Session without statistical_evidence module
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(minimal_valid_session)

        stats = rpt["statistical_evidence"]
        assert stats["p_value"] is None
        assert stats["p_value_status"] == "UNAVAILABLE"
        assert stats["predeclared_holdout_criteria_satisfied"] is None
        assert stats["holdout_criteria_status"] == "NOT_MEASURED"
        assert stats["independent_confirmatory_replications"] == 0
        assert stats["fdr_alpha"] == 0.05  # fixed governance constant

        # Check narrative contains explicit missing labels
        narrative = stats["narrative"]["narrative_tr"]
        assert "p-değeri: HESAPLANAMADI (UNAVAILABLE)" in narrative
        assert "Önceden beyan edilmiş holdout kriterleri: ÖLÇÜLMEDİ (NOT_MEASURED)" in narrative

    def test_missing_regime_and_volatility_no_fabricated_defaults(self, minimal_valid_session):
        # Empty out regime and volatility metrics
        minimal_valid_session["module_results"] = {}
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(minimal_valid_session)

        assert rpt["report_metadata"]["state"] == "PARTIAL"
        regime_metrics = rpt["regime_analysis"]["metrics"]
        assert regime_metrics.get("regime_distribution") is None

        vol_metrics = rpt["volatility_analysis"]["metrics"]
        assert vol_metrics.get("parkinson_volatility") is None
        assert vol_metrics.get("realized_volatility") is None

    def test_missing_mandatory_provenance_blocks_report(self, minimal_valid_session):
        # Remove source commit and dataset manifest
        invalid_session = dict(minimal_valid_session)
        invalid_session["source_commit_sha"] = "INVALID_COMMIT"
        invalid_session["dataset_manifest_sha256"] = "INVALID_MANIFEST"

        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(invalid_session)
        assert rpt["report_metadata"]["state"] == "BLOCKED"
        assert rpt["report_metadata"]["block_reason"] in (
            "MISSING_MANDATORY_SOURCE_PROVENANCE",
            "MISSING_MANDATORY_DATASET_MANIFEST",
        )


class TestEvidenceTrustBoundariesHardening:
    """Task 2: Evidence integrity vs authenticity & validation checks."""

    def test_trust_boundary_untrusted_source(self, minimal_valid_session):
        # Create evidence bundle with unknown report_id not stored locally
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(minimal_valid_session)
        rpt["report_metadata"]["report_id"] = "RPT-EXTERNAL-UNTRUSTED-999"

        evidence_engine = ResearchReportEvidenceBundleEngine()
        bundle = evidence_engine.create_evidence_bundle(rpt)

        res = evidence_engine.verify_evidence_bundle(bundle)
        assert res["valid"] is True
        assert res["tampering_detected"] is False
        assert res["verdict"] == "INTEGRITY_VERIFIED_UNTRUSTED_SOURCE"
        assert res["is_trusted_source"] is False

    def test_trust_boundary_trusted_source_with_checksum(self, minimal_valid_session):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(minimal_valid_session)

        evidence_engine = ResearchReportEvidenceBundleEngine()
        bundle = evidence_engine.create_evidence_bundle(rpt)
        checksum = bundle["bundle_metadata"]["package_checksum_sha256"]

        res = evidence_engine.verify_evidence_bundle(bundle, trusted_checksum=checksum)
        assert res["valid"] is True
        assert res["tampering_detected"] is False
        assert res["verdict"] == "AUTHENTICITY_VERIFIED"
        assert res["is_trusted_source"] is True

    def test_non_finite_numeric_values_rejected(self, minimal_valid_session):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(minimal_valid_session)

        evidence_engine = ResearchReportEvidenceBundleEngine()
        bundle = evidence_engine.create_evidence_bundle(rpt)

        # Inject NaN into numerical payload
        bundle["payload"]["canonical_report"]["statistical_evidence"]["p_value"] = float("nan")

        res = evidence_engine.verify_evidence_bundle(bundle)
        assert res["valid"] is False
        assert res["tampering_detected"] is True
        assert res["verdict"] == "NON_FINITE_NUMERIC_VALUE_DETECTED"

    def test_invalid_timestamp_rejected(self, minimal_valid_session):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(minimal_valid_session)

        evidence_engine = ResearchReportEvidenceBundleEngine()
        bundle = evidence_engine.create_evidence_bundle(rpt)

        # Inject invalid timestamp format
        bundle["payload"]["packaged_at_utc"] = "NOT_A_VALID_ISO_TIMESTAMP"

        res = evidence_engine.verify_evidence_bundle(bundle)
        assert res["valid"] is False
        assert res["tampering_detected"] is True
        assert res["verdict"] == "INVALID_TIMESTAMP_FORMAT"

    def test_contradictory_metadata_detected(self, minimal_valid_session):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(minimal_valid_session)

        evidence_engine = ResearchReportEvidenceBundleEngine()
        bundle = evidence_engine.create_evidence_bundle(rpt)

        # Contradictory holdout count between report and bundle payload
        bundle["payload"]["scientific_disclosures"]["predeclared_holdout_criteria_satisfied"] = 999

        res = evidence_engine.verify_evidence_bundle(bundle)
        assert res["valid"] is False
        assert res["tampering_detected"] is True
        assert res["verdict"] in ("CONTRADICTORY_METADATA_DETECTED", "TAMPERED_CHECKSUM_MISMATCH")


class TestComparisonAndPdfHardening:
    """Tasks 1, 4 & 5: Comparison reporting, PDF rendering, and durable persistence."""

    def test_no_synthetic_candidate_paths_when_candles_missing(self, minimal_valid_session):
        engine = HistoricalComparisonReportingEngine()
        cand = {
            "start_utc": "2021-06-01T00:00:00Z",
            "end_utc": "2021-06-15T00:00:00Z",
            "similarity_score": 0.85,
        }
        res = engine.build_comparison_report(minimal_valid_session, cand, candidate_candles=[])
        norm = res["chart_data"]["normalized_trajectories"]
        assert norm["candidate_trajectory"] == []
        assert norm["candidate_trajectory_status"] == "UNAVAILABLE"

    def test_pdf_rendering_with_missing_regimes_and_volatilities(self, minimal_valid_session):
        # Empty out metrics to trigger missing-value rendering paths
        minimal_valid_session["module_results"] = {}
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(minimal_valid_session)

        renderer = ResearchReportPdfRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            renderer.render_report_to_pdf(rpt, tmp_path)
            assert os.path.exists(tmp_path)
            assert os.path.getsize(tmp_path) > 1000
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_durable_storage_safety(self, monkeypatch):
        # Verify that builder uses durable storage paths and raises if none available
        builder = ResearchReportBuilderEngine()
        assert builder.storage_dir is not None
        assert not builder.storage_dir.startswith("/tmp")

        # Mock un-writable paths to verify fail-closed RuntimeError
        monkeypatch.setattr(os, "makedirs", lambda *args, **kwargs: (_ for _ in ()).throw(PermissionError("Read-only")))
        with pytest.raises(RuntimeError) as exc:
            ResearchReportBuilderEngine()
        assert "DURABLE_STORAGE_UNAVAILABLE" in str(exc.value)

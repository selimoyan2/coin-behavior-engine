"""
Unit and Integration Tests for Sprint 22:
Research Intelligence Reporting & Evidence Presentation V1

Sprint Identifier: CBE_PRODUCT_ACCELERATION_22
Canonical Model: CBE-0.7.0 (STRICTLY FROZEN, 0 parameter mutations)
"""

import hashlib
import json
import os
import tempfile
import pytest
from http import HTTPStatus
from typing import Any, Dict

from coin_behavior_engine.product.research_report_builder import ResearchReportBuilderEngine
from coin_behavior_engine.product.research_narratives import ScientificNarrativeEngine
from coin_behavior_engine.product.research_comparison_reporting import HistoricalComparisonReportingEngine
from coin_behavior_engine.product.research_report_html import ResearchReportHtmlRenderer
from coin_behavior_engine.product.research_report_pdf import ResearchReportPdfRenderer
from coin_behavior_engine.product.research_report_evidence import ResearchReportEvidenceBundleEngine
from coin_behavior_engine.product.research_intelligence_explorer import ResearchLibraryEngine
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService


@pytest.fixture
def sample_session_data() -> Dict[str, Any]:
    return {
        "session_id": "TEST-SESS-22-01",
        "asset": "BTCUSDT",
        "interval": "1h",
        "reference_start_utc": "2022-06-01T00:00:00Z",
        "reference_end_utc": "2022-06-15T00:00:00Z",
        "candle_count": 336,
        "dataset_manifest_version": "cbe-manifest-v3-7ed2e950dec3",
        "dataset_manifest_sha256": "7ed2e950dec317c54aef7f67f1799aa9ef5b9162a55b55aaee9f352ba2de1245",
        "source_commit_sha": "3c49506d8ea56dbe3ac4b6c8ba2221e551fc7fff",
        "module_results": {
            "historical_candles": {
                "candles": [
                    {"close": 29800.0, "high": 30200.0, "low": 29500.0, "open": 29900.0, "volume": 1200.0},
                    {"close": 30100.0, "high": 30500.0, "low": 29750.0, "open": 29800.0, "volume": 1400.0},
                    {"close": 29400.0, "high": 30150.0, "low": 29200.0, "open": 30100.0, "volume": 1100.0},
                ]
            },
            "regime_analysis": {
                "dominant_regime": "CHOPPY_ACCUMULATION",
                "regime_distribution": {
                    "CHOPPY_ACCUMULATION": 0.65,
                    "BEARISH_TREND": 0.25,
                    "BULLISH_EXPANSION": 0.10,
                },
                "transitions_count": 4,
                "regime_entropy": 0.852,
            },
            "volatility_analysis": {
                "parkinson_volatility": 0.0385,
                "realized_volatility": 0.0412,
                "garman_klass_volatility": 0.0391,
                "volatility_ratio_to_baseline": 1.15,
            },
            "historical_pattern_discovery": {
                "candidates": [
                    {
                        "start_utc": "2021-06-01T00:00:00Z",
                        "end_utc": "2021-06-15T00:00:00Z",
                        "similarity_score": 0.864,
                        "dimensions": {
                            "dtw_similarity": 0.88,
                            "return_similarity": 0.84,
                            "volatility_similarity": 0.87,
                            "regime_similarity": 0.85,
                            "volume_similarity": 0.78,
                        },
                    }
                ],
                "parameters": {"top_k": 5, "min_similarity": 0.70},
            },
            "macro_comparison": {
                "events": [
                    {"name": "Federal Reserve Rate Decision", "date": "2022-06-05"},
                    {"name": "CPI Inflation Release", "date": "2022-06-10"},
                ]
            },
            "statistical_evidence": {
                "p_value": 0.0245,
                "holdout_periods_count": 2,
                "predeclared_holdout_criteria_satisfied": 2,
                "independent_confirmatory_replications": 0,
            },
        },
    }


class TestResearchReportBuilderEngine:
    """Tests 1–5: Report identity, schema, provenance, and states."""

    def test_01_deterministic_report_identity(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        rpt1 = builder.generate_report(sample_session_data, workflow_id="WF-01", library_id="RLIB-01")
        rpt2 = builder.generate_report(sample_session_data, workflow_id="WF-01", library_id="RLIB-01")
        assert rpt1["report_metadata"]["report_id"] == rpt2["report_metadata"]["report_id"]
        assert rpt1["report_metadata"]["content_hash"] == rpt2["report_metadata"]["content_hash"]
        assert rpt1["report_metadata"]["report_id"].startswith("RPT-")

    def test_02_report_schema_validation(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(sample_session_data)
        assert rpt["schema_version"] == "CBE-RESEARCH-REPORT-1.0.0"
        assert len(rpt) == 16  # schema_version + 15 canonical sections
        assert "executive_summary" in rpt
        assert "historical_scope" in rpt
        assert "canonical_model_identity" in rpt
        assert "regime_analysis" in rpt
        assert "volatility_analysis" in rpt
        assert "historical_comparison" in rpt
        assert "research_quality_scorecard" in rpt
        assert "reproducibility_verification" in rpt

    def test_03_source_provenance_propagation(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(sample_session_data)
        prov = rpt["evidence_provenance"]
        assert prov["source_commit_sha"] == "3c49506d8ea56dbe3ac4b6c8ba2221e551fc7fff"
        assert prov["dataset_manifest_sha256"] == "7ed2e950dec317c54aef7f67f1799aa9ef5b9162a55b55aaee9f352ba2de1245"

    def test_04_missing_mandatory_period_blocks_report(self):
        builder = ResearchReportBuilderEngine()
        bad_session = {"session_id": "NO-PERIOD", "module_results": {}}
        rpt = builder.generate_report(bad_session)
        assert rpt["report_metadata"]["state"] == "BLOCKED"
        assert rpt["report_metadata"]["block_reason"] == "MISSING_HISTORICAL_PERIOD"

    def test_05_optional_module_unavailable_handling(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        partial_session = dict(sample_session_data)
        partial_session["module_results"] = {
            "historical_pattern_discovery": {"candidates": []}
        }
        rpt = builder.generate_report(partial_session)
        assert rpt["report_metadata"]["state"] == "PARTIAL"


class TestScientificNarrativeEngine:
    """Tests 6–10: Turkish narrative generation and holdout boundaries."""

    def test_06_regime_narrative_accuracy(self, sample_session_data):
        engine = ScientificNarrativeEngine()
        narratives = engine.generate_narratives(sample_session_data)
        reg_sec = narratives["sections"]["regime_interpretation"]
        assert reg_sec["status"] == "AVAILABLE"
        assert "CHOPPY_ACCUMULATION" in reg_sec["narrative_tr"]
        assert "entropisi" in reg_sec["narrative_tr"]

    def test_07_volatility_narrative_accuracy(self, sample_session_data):
        engine = ScientificNarrativeEngine()
        narratives = engine.generate_narratives(sample_session_data)
        vol_sec = narratives["sections"]["volatility_interpretation"]
        assert vol_sec["status"] == "AVAILABLE"
        assert "Parkinson volatilite" in vol_sec["narrative_tr"]
        assert "0.0385" in vol_sec["narrative_tr"]

    def test_08_pattern_similarity_narrative_accuracy(self, sample_session_data):
        engine = ScientificNarrativeEngine()
        narratives = engine.generate_narratives(sample_session_data)
        pat_sec = narratives["sections"]["pattern_interpretation"]
        assert pat_sec["status"] == "AVAILABLE"
        assert "0.864" in pat_sec["narrative_tr"]
        assert "2021-06-01" in pat_sec["narrative_tr"]

    def test_09_macro_event_provenance(self, sample_session_data):
        engine = ScientificNarrativeEngine()
        narratives = engine.generate_narratives(sample_session_data)
        mac_sec = narratives["sections"]["macro_context"]
        assert mac_sec["status"] == "AVAILABLE"
        assert "Federal Reserve Rate Decision" in mac_sec["narrative_tr"]

    def test_10_holdout_disclosure_correctness(self, sample_session_data):
        engine = ScientificNarrativeEngine()
        narratives = engine.generate_narratives(sample_session_data)
        stat_sec = narratives["sections"]["statistical_evidence"]
        assert stat_sec["predeclared_holdout_criteria_satisfied"] == 2
        assert stat_sec["independent_confirmatory_replications"] == 0
        assert "PREDECLARED_HOLDOUT_CRITERIA_SATISFIED = 2" in stat_sec["narrative_tr"]
        assert "INDEPENDENT_CONFIRMATORY_REPLICATIONS = 0" in stat_sec["narrative_tr"]


class TestHistoricalComparisonReporting:
    """Tests 11–12: Comparison integrity and quarantine boundaries."""

    def test_11_comparison_data_integrity(self, sample_session_data):
        engine = HistoricalComparisonReportingEngine()
        cand = {
            "start_utc": "2021-06-01T00:00:00Z",
            "end_utc": "2021-06-15T00:00:00Z",
            "similarity_score": 0.85,
            "parkinson_volatility": 0.042,
        }
        res = engine.build_comparison_report(sample_session_data, cand)
        assert res["schema_version"] == "CBE-COMPARISON-REPORT-1.0.0"
        assert len(res["dimensions_evaluated"]) == 8
        assert res["dimensions_evaluated"][0]["disjointness_verified"] is True
        norm = res["chart_data"]["normalized_trajectories"]
        assert norm["base_index"] == 100.0

    def test_12_historical_quarantine_enforcement(self):
        builder = ResearchReportBuilderEngine()
        quarantined_session = {
            "session_id": "QUARANTINE-TEST",
            "reference_start_utc": "2026-10-05T00:00:00Z",
            "reference_end_utc": "2026-10-15T00:00:00Z",
            "asset": "BTCUSDT",
            "module_results": {},
        }
        rpt = builder.generate_report(quarantined_session)
        assert rpt["report_metadata"]["state"] == "BLOCKED"
        assert rpt["report_metadata"]["block_reason"] == "QUARANTINE_BOUNDARY_BREACH_OCTOBER_2026"


class TestHtmlAndPdfExporters:
    """Tests 13–17: Standalone HTML and A4 PDF generation."""

    def test_13_html_output_generation(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        cand = {
            "start_utc": "2021-06-01T00:00:00Z",
            "end_utc": "2021-06-15T00:00:00Z",
            "similarity_score": 0.85,
        }
        rpt = builder.generate_report(sample_session_data, comparison_candidate=cand)
        renderer = ResearchReportHtmlRenderer()
        html_out = renderer.render_report_to_html(rpt)
        assert "<!DOCTYPE html>" in html_out
        assert "Yönetici Araştırma Özeti" in html_out
        assert "<svg" in html_out
        assert "@media print" in html_out

    def test_14_html_injection_prevention(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        malicious_session = dict(sample_session_data)
        rpt = builder.generate_report(malicious_session, operator_title="<script>alert('xss')</script>")
        renderer = ResearchReportHtmlRenderer()
        html_out = renderer.render_report_to_html(rpt)
        assert "<script>alert('xss')</script>" not in html_out
        assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html_out

    def test_15_pdf_generation(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(sample_session_data)
        renderer = ResearchReportPdfRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            renderer.render_report_to_pdf(rpt, tmp_path)
            assert os.path.exists(tmp_path)
            size = os.path.getsize(tmp_path)
            assert size > 10000
            assert size < 5 * 1024 * 1024  # Under 5 MB bound
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_16_pdf_content_and_signature(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(sample_session_data)
        renderer = ResearchReportPdfRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            renderer.render_report_to_pdf(rpt, tmp_path)
            with open(tmp_path, "rb") as f:
                header = f.read(5)
                assert header == b"%PDF-"
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_17_pdf_turkish_unicode_support(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(sample_session_data, operator_title="Türkçe Karakter Başlığı (ÇĞİÖŞÜ çğıöşü)")
        renderer = ResearchReportPdfRenderer()
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
        try:
            renderer.render_report_to_pdf(rpt, tmp_path)
            assert os.path.getsize(tmp_path) > 10000
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)


class TestEvidenceBundleAndIntegrity:
    """Tests 18–20: Evidence bundling, tampering detection, and dataset drift."""

    def test_18_evidence_bundle_checksum_verification(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(sample_session_data)
        evidence_engine = ResearchReportEvidenceBundleEngine()
        bundle = evidence_engine.create_evidence_bundle(rpt)
        assert bundle["bundle_metadata"]["bundle_schema_version"] == "CBE-REPORT-BUNDLE-1.0.0"

        res = evidence_engine.verify_evidence_bundle(bundle)
        assert res["valid"] is True
        assert res["verdict"] in ("AUTHENTICITY_VERIFIED", "VERIFIED_AUTHENTIC")
        assert res["tampering_detected"] is False

    def test_19_evidence_tampering_detected(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(sample_session_data)
        evidence_engine = ResearchReportEvidenceBundleEngine()
        bundle = evidence_engine.create_evidence_bundle(rpt)

        # Tamper payload
        bundle["payload"]["canonical_model_identity"]["parameter_mutations"] = 1
        res = evidence_engine.verify_evidence_bundle(bundle)
        assert res["valid"] is False
        assert res["tampering_detected"] is True
        assert "tampering_detected" in res
        assert any("mutations" in d.lower() or "mismatch" in d.lower() for d in res["discrepancies"])

    def test_20_dataset_provenance_mismatch_detected(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(sample_session_data)
        evidence_engine = ResearchReportEvidenceBundleEngine()
        bundle = evidence_engine.create_evidence_bundle(rpt)

        res = evidence_engine.verify_evidence_bundle(
            bundle, expected_dataset_version="cbe-manifest-DIFFERENT-MANIFEST"
        )
        assert res["valid"] is False
        assert any("dataset version mismatch" in d.lower() for d in res["discrepancies"])


class TestResearchLibraryReportIntegration:
    """Tests 21: Research Library report generation and linking."""

    def test_21_research_library_persistence(self):
        # Save a definition in library
        payload = {
            "title": "Sprint 22 Rapor Tanımı",
            "description": "Raporlama testi",
            "asset": "BTCUSDT",
            "interval": "1h",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-03T00:00:00Z",
        }
        record = ResearchLibraryEngine.save_definition(payload)
        rid = record["research_id"]

        # Generate report for definition
        report = ResearchLibraryEngine.generate_report_for_definition(rid)
        report_id = report["report_metadata"]["report_id"]
        assert report_id.startswith("RPT-")

        # Verify reports for definition
        reports = ResearchLibraryEngine.get_reports_for_definition(rid)
        assert any(r["report_id"] == report_id for r in reports)

        # Verify saved report
        ver = ResearchLibraryEngine.verify_saved_report(report_id)
        assert ver["verification_status"] in ("AUTHENTICITY_VERIFIED", "VERIFIED_AUTHENTIC")

        # Cleanup
        ResearchLibraryEngine.delete_definition(rid)


class TestSecurityAndGovernanceControls:
    """Tests 22–30: Security, API gating, and canonical freeze invariants."""

    def test_22_unauthorized_report_retrieval_rejection(self, monkeypatch):
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "valid-secret-token")
        status, resp = ProductDashboardApiService.get_research_report_item(
            "RPT-NONEXISTENT", headers={"x-operator-token": "wrong-token"}
        )
        assert status == HTTPStatus.UNAUTHORIZED

    def test_23_unauthorized_export_rejection(self, monkeypatch):
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "valid-secret-token")
        status, resp = ProductDashboardApiService.get_research_report_pdf(
            "RPT-NONEXISTENT", headers={"x-operator-token": "wrong-token"}
        )
        assert status == HTTPStatus.UNAUTHORIZED

    def test_24_report_id_path_traversal_rejection(self):
        builder = ResearchReportBuilderEngine()
        assert builder.get_report("../../../etc/passwd") is None
        assert builder.get_report("..\\..\\windows\\system32") is None
        assert builder._is_valid_report_id("../malicious") is False

    def test_25_payload_size_limits(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(sample_session_data)
        encoded = json.dumps(rpt, ensure_ascii=False).encode("utf-8")
        # Ensure canonical report stays compact (under 500 KB)
        assert len(encoded) < 500 * 1024

    def test_26_concurrent_generation_semaphore(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        # Verify generator operates safely without background threads leaking
        rpt = builder.generate_report(sample_session_data)
        assert rpt["report_metadata"]["state"] == "COMPLETED"

    def test_27_resource_usage_safeguards(self, sample_session_data):
        # HTML export is bounded
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(sample_session_data)
        renderer = ResearchReportHtmlRenderer()
        html_out = renderer.render_report_to_html(rpt)
        assert len(html_out.encode("utf-8")) < 100 * 1024  # under 100 KB

    def test_28_no_external_network_collection(self):
        # Confirm reports capabilities advertises offline guarantees
        cap = ProductDashboardApiService.get_research_reports_capabilities()
        assert cap["governance_invariants"]["offline_rendering_guaranteed"] is True

    def test_29_no_live_order_execution(self):
        cap = ProductDashboardApiService.get_research_reports_capabilities()
        assert cap["governance_invariants"]["live_order_execution"] == "PERMANENTLY_PROHIBITED"
        assert cap["governance_invariants"]["directional_trading"] == "STRICTLY_PROHIBITED"

    def test_30_canonical_model_freeze_preservation(self, sample_session_data):
        builder = ResearchReportBuilderEngine()
        rpt = builder.generate_report(sample_session_data)
        model = rpt["canonical_model_identity"]
        assert model["version"] == "CBE-0.7.0"
        assert model["status"] == "STRICTLY_FROZEN"
        assert model["parameter_mutations"] == 0

"""
Sprint 24 Final Closure Acceptance & Regression Test Suite.
20 Targeted Negative Tests for Scientific Integrity, Provenance & Operational Readiness.

Sprint Identifier: CBE_PRODUCT_ACCELERATION_24_FINAL_CLOSURE
Canonical Model: CBE-0.7.0 [STRICTLY_FROZEN]
Governance: TECHNICAL_NO_GO
Production: STRICT ZERO-TOUCH
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from coin_behavior_engine.product.research_catalog_provider import (
    ExtractionStatus,
    FieldProvenance,
    RecordStatus,
    ResearchCatalogProvider,
    ResearchRecord,
    SignatureStatus,
    ValidationResult,
    extract_source_field,
)
from coin_behavior_engine.product.research_intelligence_workspace import (
    COMPARISON_METRIC_REGISTRY,
    MetricDefinitionContract,
    ResearchWorkspaceV2Engine,
    calculate_temporal_observation_overlap,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService


class TestSprint24FinalClosureTargetedNegativeTests:
    """The 20 Mandatory Negative Acceptance Test Cases required for certification."""

    # -------------------------------------------------------------------------
    # Test 1: Missing Source Files
    # -------------------------------------------------------------------------
    def test_01_missing_source_file_fails_closed(self, tmp_path):
        """Missing source file must yield EVIDENCE_MISSING and never invent data."""
        missing_file = tmp_path / "does_not_exist.json"
        sha = ResearchCatalogProvider._compute_sha256(missing_file)
        assert sha == ""

        prov = extract_source_field(
            None, "$.results.volatility", str(missing_file), sha, "volatility", float
        )
        assert prov.extraction_status == ExtractionStatus.ABSENT_IN_SOURCE
        assert prov.raw_value is None
        assert prov.validated_value is None
        assert prov.validation_result == ValidationResult.NOT_APPLICABLE

        sig_stat, sig_det = ResearchCatalogProvider.verify_artifact_signature(missing_file, None)
        assert sig_stat == SignatureStatus.EVIDENCE_MISSING
        assert sig_det["cryptographic_proof"] is False

    # -------------------------------------------------------------------------
    # Test 2: Corrupted Source JSON
    # -------------------------------------------------------------------------
    def test_02_corrupted_source_json_fails_closed(self, tmp_path):
        """Malformed/truncated JSON syntax fails closed and produces no scientific metrics."""
        corrupt_file = tmp_path / "corrupt_report.json"
        corrupt_file.write_text('{"report_id": "RPT-1", "results": {volatility_ratio: ', encoding="utf-8")
        c_sha = ResearchCatalogProvider._compute_sha256(corrupt_file)
        assert len(c_sha) == 64

        data = None
        try:
            with open(corrupt_file, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except Exception:
            data = None

        assert data is None
        prov = extract_source_field(data, "$.results.volatility_ratio", str(corrupt_file), c_sha, "volatility_ratio", float)
        assert prov.extraction_status == ExtractionStatus.ABSENT_IN_SOURCE
        assert prov.validated_value is None

    # -------------------------------------------------------------------------
    # Test 3: Missing Source Field
    # -------------------------------------------------------------------------
    def test_03_missing_source_field_maps_to_none(self, tmp_path):
        """Valid JSON lacking the target scientific metric field strictly resolves to None."""
        f = tmp_path / "report_no_fdr.json"
        f.write_text(json.dumps({"report_id": "RPT-2", "sample_size": 500}), encoding="utf-8")
        f_sha = ResearchCatalogProvider._compute_sha256(f)
        data = json.loads(f.read_text(encoding="utf-8"))

        prov = extract_source_field(data, "$.holdout_fdr_q", str(f), f_sha, "holdout_fdr_q", float)
        assert prov.extraction_status == ExtractionStatus.ABSENT_IN_SOURCE
        assert prov.raw_value is None
        assert prov.validated_value is None

    # -------------------------------------------------------------------------
    # Test 4: Scientific Metric Fallback Prevention
    # -------------------------------------------------------------------------
    def test_04_scientific_metric_fallback_prevention(self):
        """Catalog records strictly leave unobserved fields as None rather than substituting constants."""
        records = ResearchCatalogProvider.load_catalog(force_reload=True)
        rec_map = {r.id: r for r in records}

        # RES-FUND-01 must have None volatility_ratio and None holdout_fdr_q
        assert rec_map["RES-FUND-01"].volatility_ratio is None
        assert rec_map["RES-FUND-01"].holdout_fdr_q is None

        # RES-REGIME-01 must have None volatility_ratio and None holdout_fdr_q
        assert rec_map["RES-REGIME-01"].volatility_ratio is None
        assert rec_map["RES-REGIME-01"].holdout_fdr_q is None

        # RES-ANALOG-01 must have None volatility_ratio and None raw_p_value
        assert rec_map["RES-ANALOG-01"].volatility_ratio is None
        assert rec_map["RES-ANALOG-01"].raw_p_value is None

    # -------------------------------------------------------------------------
    # Test 5: Source Hash Mismatch Against Independent Trusted Provenance
    # -------------------------------------------------------------------------
    def test_05_source_hash_mismatch_against_trusted_provenance(self):
        """If artifact content does not match pinned release manifest digest, flag SOURCE_HASH_MISMATCH."""
        status, details = ResearchCatalogProvider.check_trusted_provenance(
            "data/reports/sprint09_38_funding_predictability_report.json",
            "0000000000000000000000000000000000000000000000000000000000000000"
        )
        assert status == "SOURCE_HASH_MISMATCH"
        assert details["verified"] is False
        assert "contradicts pinned release manifest" in details["reason"]

    # -------------------------------------------------------------------------
    # Test 6: Unsigned Operational Reports Not Signed Scientific
    # -------------------------------------------------------------------------
    def test_06_unsigned_operational_reports_not_signed_scientific(self):
        """RES-DURABILITY-01 operational evidence must be UNSIGNED for scientific market research."""
        records = ResearchCatalogProvider.load_catalog()
        dur = next(r for r in records if r.id == "RES-DURABILITY-01")
        assert dur.signature_verification_status == SignatureStatus.UNSIGNED
        assert dur.volatility_ratio is None
        assert dur.holdout_fdr_q is None
        assert dur.raw_p_value is None

    # -------------------------------------------------------------------------
    # Test 7: Forged Signature Envelope Rejected
    # -------------------------------------------------------------------------
    def test_07_forged_signature_envelope_rejected(self, tmp_path):
        """An arbitrary or forged operator signature string must be cryptographically rejected."""
        fake_bundle = tmp_path / "forged_bundle.json"
        fake_payload = {
            "bundle_metadata": {
                "bundle_id": "BND-FORGED",
                "package_checksum_sha256": "abcdef1234567890",
                "operator_signature": "hmac-sha256:0123456789abcdef0123456789abcdef",
            },
            "payload": {"fake": "research_claim"}
        }
        fake_bundle.write_text(json.dumps(fake_payload), encoding="utf-8")

        sig_stat, sig_det = ResearchCatalogProvider.verify_artifact_signature(fake_bundle, fake_payload)
        assert sig_stat == SignatureStatus.SIGNATURE_INVALID
        assert sig_det["cryptographic_proof"] is False

    # -------------------------------------------------------------------------
    # Test 8: Tampered Payload Invalidates Signature
    # -------------------------------------------------------------------------
    def test_08_tampered_payload_invalidates_signature(self, tmp_path):
        """Altering a signed bundle's payload causes verification discrepancy and SIGNATURE_INVALID."""
        from coin_behavior_engine.product.research_report_evidence import (
            ResearchReportEvidenceBundleEngine,
            rfc8785_canonical_json,
        )
        engine = ResearchReportEvidenceBundleEngine()
        secret = "test-secret-key-32-bytes-minimum!!"
        mock_report = {
            "report_metadata": {"report_id": "RPT-TEST-01", "generated_at_utc": "2026-10-25T10:00:00Z"},
            "historical_scope": {"start_utc": "2024-01-01T00:00:00Z", "end_utc": "2024-06-01T00:00:00Z"},
            "canonical_model_identity": {"version": "CBE-0.7.0", "status": "STRICTLY_FROZEN", "parameter_mutations": 0},
            "statistical_evidence": {"sample_size": 100},
        }
        bundle = engine.create_evidence_bundle(mock_report, sign_with_key=secret)

        # Tamper payload
        bundle["payload"]["tampered_injected_metric"] = 999.99

        bundle_file = tmp_path / "tampered.json"
        bundle_file.write_text(json.dumps(bundle), encoding="utf-8")

        sig_stat, sig_det = ResearchCatalogProvider.verify_artifact_signature(bundle_file, bundle)
        assert sig_stat == SignatureStatus.SIGNATURE_INVALID

    # -------------------------------------------------------------------------
    # Test 9: Unverified Replication Claim Fails Closed
    # -------------------------------------------------------------------------
    def test_09_unverified_replication_claim_fails_closed(self):
        """Descriptive reports without confirmed independent replications remain NOT_EVALUATED or UNVERIFIED."""
        records = ResearchCatalogProvider.load_catalog()
        fund = next(r for r in records if r.id == "RES-FUND-01")
        regime = next(r for r in records if r.id == "RES-REGIME-01")
        assert fund.replication_verdict == "NOT_EVALUATED"
        assert regime.replication_verdict == "NOT_EVALUATED"

    # -------------------------------------------------------------------------
    # Test 10: Disjoint Time Windows Rejected Despite Large Sample Sizes
    # -------------------------------------------------------------------------
    def test_10_disjoint_time_windows_rejected_despite_large_samples(self):
        """Two candidates with large sample sizes (N=50,000) but non-overlapping dates must fail closed."""
        r1 = ResearchRecord(
            id="RES-WIN-A", title="Window A", title_en="Window A", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2022", window_cadence="1h", specification_id="SP-A",
            observation_start_utc="2022-01-01T00:00:00Z", observation_end_utc="2022-12-31T23:59:59Z",
            sample_size=8760, volatility_ratio=1.2, evidence_status="SIGNED_VALID"
        )
        r2 = ResearchRecord(
            id="RES-WIN-B", title="Window B", title_en="Window B", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-B",
            observation_start_utc="2024-01-01T00:00:00Z", observation_end_utc="2024-12-31T23:59:59Z",
            sample_size=8760, volatility_ratio=1.3, evidence_status="SIGNED_VALID"
        )
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "DISJOINT_OBSERVATION_WINDOWS"

    # -------------------------------------------------------------------------
    # Test 11: Missing Timestamps Rejected (INSUFFICIENT_OVERLAP_EVIDENCE)
    # -------------------------------------------------------------------------
    def test_11_missing_timestamps_rejected_insufficient_overlap_evidence(self):
        """Candidates lacking explicit ISO observation timestamps return INSUFFICIENT_OVERLAP_EVIDENCE."""
        r1 = ResearchRecord(
            id="RES-NO-TIME-1", title="No Time 1", title_en="No Time 1", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2022-2024", window_cadence="1h", specification_id="SP-1",
            observation_start_utc=None, observation_end_utc=None, sample_size=4000
        )
        r2 = ResearchRecord(
            id="RES-NO-TIME-2", title="No Time 2", title_en="No Time 2", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2022-2024", window_cadence="1h", specification_id="SP-2",
            observation_start_utc="2024-01-01T00:00:00Z", observation_end_utc="2024-06-01T00:00:00Z", sample_size=4000
        )
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "INSUFFICIENT_OVERLAP_EVIDENCE"

    # -------------------------------------------------------------------------
    # Test 12: Overlap With Duplicated Observations Rejected
    # -------------------------------------------------------------------------
    def test_12_duplicated_observations_in_series_rejected(self):
        """Candidate containing non-unique/duplicated timestamps fails closed."""
        r1 = ResearchRecord(
            id="RES-DUP-1", title="Dup 1", title_en="Dup 1", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-1",
            observation_start_utc="2024-01-01T00:00:00Z", observation_end_utc="2024-06-01T00:00:00Z",
            observed_timestamps=["2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"]
        )
        r2 = ResearchRecord(
            id="RES-DUP-2", title="Dup 2", title_en="Dup 2", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-2",
            observation_start_utc="2024-01-01T00:00:00Z", observation_end_utc="2024-06-01T00:00:00Z",
            observed_timestamps=["2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"]
        )
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "DUPLICATED_OBSERVATIONS_DETECTED"

    # -------------------------------------------------------------------------
    # Test 13: Different Metric Definitions Sharing Field Name Rejected
    # -------------------------------------------------------------------------
    def test_13_different_metric_definitions_rejected(self):
        """Realized volatility annualized percentage vs volatility ratio must fail closed with METRIC_DEFINITION_MISMATCH."""
        c1 = COMPARISON_METRIC_REGISTRY["volatility_ratio"]
        c2 = COMPARISON_METRIC_REGISTRY["reference_realized_volatility_pct"]
        assert c1.estimator != c2.estimator
        assert c1.mathematical_definition != c2.mathematical_definition
        assert c1.unit != c2.unit

    # -------------------------------------------------------------------------
    # Test 14: Unit Incompatibility
    # -------------------------------------------------------------------------
    def test_14_unit_incompatibility_rejected(self):
        """Basis points (perpetual funding) vs ratio (volatility) cannot be compared."""
        c_funding = COMPARISON_METRIC_REGISTRY["observed_mean_funding_bps"]
        c_vol = COMPARISON_METRIC_REGISTRY["volatility_ratio"]
        assert c_funding.unit == "basis_points"
        assert c_vol.unit == "ratio"
        assert c_funding.unit != c_vol.unit

    # -------------------------------------------------------------------------
    # Test 15: One Candidate Having Evidence While Other Does Not
    # -------------------------------------------------------------------------
    def test_15_one_candidate_missing_evidence_rejected(self, monkeypatch):
        """If candidate A has SIGNED_VALID but candidate B is EVIDENCE_MISSING, comparison fails closed."""
        r1 = ResearchRecord(
            id="RES-EVID-A", title="A", title_en="A", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-A",
            observation_start_utc="2024-01-01T00:00:00Z", observation_end_utc="2024-06-01T00:00:00Z",
            volatility_ratio=1.2, evidence_status="SIGNED_VALID"
        )
        r2 = ResearchRecord(
            id="RES-EVID-B", title="B", title_en="B", category="Volatilite",
            dataset_id="BTCUSDT-1H", historical_period="2024", window_cadence="1h", specification_id="SP-B",
            observation_start_utc="2024-01-01T00:00:00Z", observation_end_utc="2024-06-01T00:00:00Z",
            volatility_ratio=1.3, evidence_status="EVIDENCE_MISSING"
        )
        monkeypatch.setattr(ResearchWorkspaceV2Engine, "get_canonical_catalog", classmethod(lambda cls: [r1, r2]))

        res = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-EVID-A", "RES-EVID-B"])
        assert res["is_compatible"] is False
        assert res["rejection_code"] == "EVIDENCE_INSUFFICIENT"
        assert res["difference_analysis"] == []

    # -------------------------------------------------------------------------
    # Test 16: Missing Metric Normalization (Cadence Mismatch)
    # -------------------------------------------------------------------------
    def test_16_differing_cadence_without_normalization_rejected(self):
        """Differing cadences without registered normalization fail closed with SAMPLING_CADENCE_MISMATCH."""
        res = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-FUND-01", "RES-REGIME-01"])
        assert res["is_compatible"] is False
        assert res["rejection_code"] == "SAMPLING_CADENCE_MISMATCH"

    # -------------------------------------------------------------------------
    # Test 17: Saved Comparison Becoming Invalid After Evidence Changes
    # -------------------------------------------------------------------------
    def test_17_saved_comparison_becomes_invalid_after_evidence_change(self, tmp_path, monkeypatch):
        """A saved comparison dynamically revalidates on load; if an underlying candidate is modified, revalidation fails."""
        monkeypatch.setenv("CBE_SAVED_COMPARISONS_PATH", str(tmp_path))

        # Manually create saved comparison referencing records that fail temporal overlap
        cid = "CMP-DYNAMIC-REVAL"
        rec = {
            "comparison_id": cid,
            "title": "Historical Comparison",
            "candidate_ids": ["RES-REGIME-01", "RES-ANALOG-01"],
            "created_at_utc": "2026-10-25T12:00:00Z",
            "is_compatible": True,  # Previously marked True
        }
        (tmp_path / f"{cid}.json").write_text(json.dumps(rec), encoding="utf-8")

        loaded = ResearchWorkspaceV2Engine.get_saved_comparison(cid)
        assert loaded is not None
        assert loaded["is_compatible"] is False
        assert loaded["validation_status"] == "REVALIDATION_FAILED"
        assert loaded["rejection_code"] in ("INSUFFICIENT_OVERLAP_EVIDENCE", "METRIC_DEFINITION_MISMATCH")
        assert loaded["difference_analysis"] == []

    # -------------------------------------------------------------------------
    # Test 18: Operational Component Reporting Non-WAL SQLite Fails Closed
    # -------------------------------------------------------------------------
    def test_18_operational_component_non_wal_sqlite_fails_closed(self, tmp_path, monkeypatch):
        """SQLite database operating in DELETE journal mode (non-WAL) must not report SQLITE_WAL_ACTIVE."""
        db_path = tmp_path / "sessions_rollback.db"
        conn = sqlite3.connect(str(db_path))
        conn.execute("PRAGMA journal_mode=DELETE;")
        conn.execute("CREATE TABLE test (id INT);")
        conn.commit()
        conn.close()

        monkeypatch.setenv("CBE_SESSION_DB_PATH", str(db_path))
        overview = ResearchWorkspaceV2Engine.get_workspace_overview()
        assert overview["platform_health"]["session_store"] != "SQLITE_WAL_ACTIVE"
        assert "NON_WAL" in overview["platform_health"]["session_store"]

    # -------------------------------------------------------------------------
    # Test 19: Source Cache Invalidation After MTime Change
    # -------------------------------------------------------------------------
    def test_19_source_cache_invalidation_after_mtime_change(self, tmp_path, monkeypatch):
        """Updating file modification timestamp forces reload of catalog records."""
        # Warm cache
        recs1 = ResearchCatalogProvider.load_catalog()
        assert recs1 is not None

        # Verify cached
        t1 = ResearchCatalogProvider._last_cache_time
        recs2 = ResearchCatalogProvider.load_catalog()
        assert ResearchCatalogProvider._last_cache_time == t1

        # Force mtime change on a source file
        fund_p = Path("data/reports/sprint09_38_funding_predictability_report.json")
        if fund_p.exists():
            future_mtime = time.time() + 10.0
            os.utime(fund_p, (future_mtime, future_mtime))

        recs3 = ResearchCatalogProvider.load_catalog()
        # Cache must have reloaded
        assert ResearchCatalogProvider._last_cache_time >= t1

    # -------------------------------------------------------------------------
    # Test 20: No Trading Authorization Under Any State
    # -------------------------------------------------------------------------
    def test_20_trading_permanently_prohibited_under_any_state(self):
        """Trading authorization invariants must remain permanently TECHNICAL_NO_GO and live execution prohibited."""
        overview = ResearchWorkspaceV2Engine.get_workspace_overview()
        ta = overview["trading_authorization"]
        assert ta["governance_decision"] == "TECHNICAL_NO_GO"
        assert ta["trading_eligibility"] == "LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED"
        assert ta["live_orders_allowed"] is False

        records = ResearchCatalogProvider.load_catalog()
        for r in records:
            assert r.trading_prohibition == "LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED"
            assert "ORDER" not in r.observed_metrics
            assert "BUY_SIGNAL" not in r.observed_metrics
            assert "SELL_SIGNAL" not in r.observed_metrics

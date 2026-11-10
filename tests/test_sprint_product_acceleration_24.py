"""
Sprint 24 Comprehensive Test Suite.
Research Intelligence Workspace V2: Unified Discovery, Scientific Comparison,
Interactive Visualization, Product UX & Performance Maturity.

Sprint ID: CBE_PRODUCT_ACCELERATION_24
Canonical Model: CBE-0.7.0 [STRICTLY_FROZEN]
Governance: TECHNICAL_NO_GO
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import time
from dataclasses import asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List

import pytest

from coin_behavior_engine.product.research_intelligence_workspace import (
    ResearchWorkspaceV2Engine,
    ResearchRecord,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.storage_durability import StorageDurabilityEngine
from coin_behavior_engine.product.session_manager import session_manager, SessionManager
from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION

AUTH_VOL_ID = "dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f"
TEST_SIGNING_KEY = "test-volume-signing-key-sprint24-alpha"
TEST_OPERATOR_TOKEN = "cbe-test-operator-sprint24-token"


# =============================================================================
# GROUP 1: SPRINT 23 CARRY-FORWARD STRICT IDENTITY BINDING HARDENING
# =============================================================================

class TestGroup1StrictIdentityBindingHardening:
    """Verifies that missing container or image identity cannot silently bypass a required match."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        monkeypatch.setenv("CBE_ENV", "staging")
        monkeypatch.setenv("CBE_VOLUME_ATTESTATION_KEY", TEST_SIGNING_KEY)

    def _make_valid_claims(self, **overrides) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        claims = {
            "authorized_volume_id": AUTH_VOL_ID,
            "expected_destination": "/app/data/prospective",
            "expected_filesystem": "ext4",
            "bound_container_id": "container-sprint24-staging-01",
            "bound_image_id": "sha256:staging-image-closure-cbe24",
            "issued_at_utc": (now - timedelta(minutes=5)).isoformat(),
            "expires_at_utc": (now + timedelta(hours=24)).isoformat(),
        }
        claims.update(overrides)
        return claims

    def test_bound_container_id_with_missing_curr_cid_fails_closed(self, monkeypatch):
        """When attestation requires bound_container_id but curr_cid is None, must fail closed."""
        monkeypatch.delenv("CBE_CONTAINER_ID", raising=False)
        monkeypatch.setattr(StorageDurabilityEngine, "get_current_container_id", classmethod(lambda cls: None))
        monkeypatch.setattr(StorageDurabilityEngine, "get_current_image_id", classmethod(lambda cls: "sha256:staging-image-closure-cbe24"))

        claims = self._make_valid_claims(bound_container_id="container-sprint24-staging-01")
        att = StorageDurabilityEngine.create_signed_volume_attestation(claims, TEST_SIGNING_KEY)

        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]

        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            attestation_override=att,
        )
        assert info["classification"] == "UNVERIFIABLE_VOLUME_IDENTITY"
        assert "cannot be established" in (info["rejection_reason"] or "").lower()
        assert info["verified_durable"] is False

    def test_bound_image_id_with_missing_curr_img_fails_closed(self, monkeypatch):
        """When attestation requires bound_image_id but curr_img is None, must fail closed."""
        monkeypatch.delenv("CBE_IMAGE_ID", raising=False)
        monkeypatch.delenv("CBE_IMAGE_DIGEST", raising=False)
        monkeypatch.setattr(StorageDurabilityEngine, "get_current_container_id", classmethod(lambda cls: "container-sprint24-staging-01"))
        monkeypatch.setattr(StorageDurabilityEngine, "get_current_image_id", classmethod(lambda cls: None))

        claims = self._make_valid_claims(bound_image_id="sha256:staging-image-closure-cbe24")
        att = StorageDurabilityEngine.create_signed_volume_attestation(claims, TEST_SIGNING_KEY)

        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]

        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            attestation_override=att,
        )
        assert info["classification"] == "UNVERIFIABLE_VOLUME_IDENTITY"
        assert "cannot be established" in (info["rejection_reason"] or "").lower()
        assert info["verified_durable"] is False


# =============================================================================
# GROUP 2: RESEARCH DISCOVERY & COMPOSABLE FILTERING (UNIT & FUNCTIONAL)
# =============================================================================

class TestGroup2ResearchDiscoveryAndFiltering:
    """Verifies search, composable filtering, sorting, and bounded pagination."""

    def test_get_canonical_catalog_contains_expected_records(self):
        records = ResearchWorkspaceV2Engine.get_canonical_catalog()
        assert len(records) >= 6
        ids = {r.id for r in records}
        assert "RES-FUND-01" in ids
        assert "RES-REGIME-01" in ids
        assert "RES-ANALOG-01" in ids
        assert "RES-MACRO-01" in ids
        assert "RES-DURABILITY-01" in ids
        assert "RES-CRYPTO-01" in ids

    def test_filter_by_dataset(self):
        res = ResearchWorkspaceV2Engine.query_research(dataset_filter="BTCUSDT-SPOT-1H")
        assert res["total_count"] >= 2
        for item in res["items"]:
            assert "BTCUSDT-SPOT-1H" in item["dataset_id"]

    def test_filter_by_scientific_eligibility(self):
        res_eligible = ResearchWorkspaceV2Engine.query_research(eligibility_filter="ELIGIBLE")
        res_ineligible = ResearchWorkspaceV2Engine.query_research(eligibility_filter="INELIGIBLE")
        assert all(item["scientific_eligibility"] == "ELIGIBLE" for item in res_eligible["items"])
        assert all(item["scientific_eligibility"] == "INELIGIBLE" for item in res_ineligible["items"])
        assert any(item["id"] == "RES-CRYPTO-01" for item in res_ineligible["items"])

    def test_filter_by_cadence(self):
        res_8h = ResearchWorkspaceV2Engine.query_research(timeframe_filter="8h")
        assert res_8h["total_count"] >= 1
        assert res_8h["items"][0]["id"] == "RES-FUND-01"

    def test_sorting_by_volatility_and_sample_size(self):
        # Sort descending by volatility (filter None for verified observed values)
        res_vol = ResearchWorkspaceV2Engine.query_research(sort_by="volatility_ratio", sort_dir="desc")
        vol_vals = [r["volatility_ratio"] for r in res_vol["items"] if r["volatility_ratio"] is not None]
        assert vol_vals == sorted(vol_vals, reverse=True)

        # Sort descending by sample size
        res_sample = ResearchWorkspaceV2Engine.query_research(sort_by="sample_size", sort_dir="desc")
        sample_vals = [r["sample_size"] for r in res_sample["items"] if r["sample_size"] is not None]
        assert sample_vals == sorted(sample_vals, reverse=True)

    def test_bounded_pagination(self):
        res_p1 = ResearchWorkspaceV2Engine.query_research(page=1, limit=2)
        assert len(res_p1["items"]) == 2
        assert res_p1["page"] == 1
        assert res_p1["total_pages"] >= 3

        # Test limit bounds (max 100)
        res_huge = ResearchWorkspaceV2Engine.query_research(limit=500)
        assert res_huge["limit"] == 100

    def test_get_research_detail_exists(self):
        detail = ResearchWorkspaceV2Engine.get_research_detail("RES-FUND-01")
        assert detail is not None
        assert detail["id"] == "RES-FUND-01"
        assert detail["model_version"] == "CBE-0.7.0"
        assert "related_reports" in detail
        assert "available_exports" in detail
        assert detail["governance_status"]["technical_decision"] == "TECHNICAL_NO_GO"

    def test_get_research_detail_nonexistent(self):
        detail = ResearchWorkspaceV2Engine.get_research_detail("RES-NONEXISTENT-99")
        assert detail is None


# =============================================================================
# GROUP 3: SCIENTIFIC COMPARISON LAB & COMPATIBILITY GATE
# =============================================================================

class TestGroup3ScientificComparisonLab:
    """Verifies selection limits, compatibility gate, difference calculations, and persistence."""

    def test_selection_bounds_enforcement(self):
        # Less than 2
        res1 = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-FUND-01"])
        assert res1["is_compatible"] is False
        assert res1["rejection_code"] == "INSUFFICIENT_SELECTION"

        # More than 4
        res5 = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility([
            "RES-FUND-01", "RES-REGIME-01", "RES-ANALOG-01", "RES-MACRO-01", "RES-DURABILITY-01"
        ])
        assert res5["is_compatible"] is False
        assert res5["rejection_code"] == "SELECTION_LIMIT_EXCEEDED"

    def test_quarantined_record_rejected_by_compatibility_gate(self):
        """RES-CRYPTO-01 is FAILED_QUARANTINE / INELIGIBLE; gate must reject."""
        res = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-REGIME-01", "RES-CRYPTO-01"])
        assert res["is_compatible"] is False
        assert res["rejection_code"] in ("QUARANTINED_RECORD", "QUARANTINED_RESEARCH_INELIGIBLE")
        assert "RES-CRYPTO-01" in res["quarantined_ids"]

    def test_compatible_candidates_pass_gate(self, monkeypatch):
        # 1. First verify RES-REGIME-01 vs RES-ANALOG-01 fails closed under strict temporal overlap and metric rules
        res_fail = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-REGIME-01", "RES-ANALOG-01"])
        assert res_fail["is_compatible"] is False
        assert res_fail["rejection_code"] in ("INSUFFICIENT_OVERLAP_EVIDENCE", "METRIC_DEFINITION_MISMATCH")
        assert res_fail["difference_analysis"] == []

        # 2. Verify genuinely compatible pair sharing 1h cadence, >=100 overlapping intervals, and verified metric contract
        sample_ts = [f"2024-02-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]
        r1 = ResearchRecord(
            id="RES-COMPAT-01",
            title="Walk-Forward Baseline 2024",
            title_en="Walk-Forward Baseline 2024",
            category="Rejim Dinamikleri",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024-01-01 to 2024-06-01",
            window_cadence="1h",
            specification_id="SPEC-002-WF",
            observation_start_utc="2024-01-01T00:00:00Z",
            observation_end_utc="2024-06-01T00:00:00Z",
            observed_timestamps=sample_ts,
            sample_size=3624,
            volatility_ratio=1.240,
            raw_p_value=0.0450,
            evidence_status="SIGNED_VALID",
            signature_verification_status="SIGNED_VALID",
        )
        r2 = ResearchRecord(
            id="RES-COMPAT-02",
            title="Analog Matched Window 2024",
            title_en="Analog Matched Window 2024",
            category="Rejim Dinamikleri",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024-02-01 to 2024-06-01",
            window_cadence="1h",
            specification_id="SPEC-003-AM",
            observation_start_utc="2024-02-01T00:00:00Z",
            observation_end_utc="2024-06-01T00:00:00Z",
            observed_timestamps=sample_ts,
            sample_size=2880,
            volatility_ratio=1.310,
            raw_p_value=0.0320,
            evidence_status="SIGNED_VALID",
            signature_verification_status="SIGNED_VALID",
        )
        monkeypatch.setattr(ResearchWorkspaceV2Engine, "get_canonical_catalog", classmethod(lambda cls: [r1, r2]))

        res = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-COMPAT-01", "RES-COMPAT-02"])
        assert res["is_compatible"] is True
        assert res["rejection_code"] is None
        assert len(res["comparison_table"]) == 2
        assert len(res["difference_analysis"]) == 1

        # Check difference analysis fields
        diff = res["difference_analysis"][0]
        assert "volatility_ratio" in diff["metrics"]
        assert "disclaimer" in diff
        assert "kârlılığın kanıtı olarak yorumlanamaz" in diff["disclaimer"].lower()

    def test_cadence_mismatch_rejected_by_gate(self):
        """Differing sampling cadences (8h vs 1h) fail closed under scientific comparison rules."""
        res = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-FUND-01", "RES-REGIME-01"])
        assert res["is_compatible"] is False
        assert res["rejection_code"] == "SAMPLING_CADENCE_MISMATCH"
        assert res["difference_analysis"] == []

    def test_saved_comparison_persistence_lifecycle(self, tmp_path, monkeypatch):
        monkeypatch.setenv("CBE_SAVED_COMPARISONS_PATH", str(tmp_path))
        sample_ts = [f"2024-02-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]

        r1 = ResearchRecord(
            id="RES-COMPAT-01",
            title="Walk-Forward Baseline 2024",
            title_en="Walk-Forward Baseline 2024",
            category="Rejim Dinamikleri",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024-01-01 to 2024-06-01",
            window_cadence="1h",
            specification_id="SPEC-002-WF",
            observation_start_utc="2024-01-01T00:00:00Z",
            observation_end_utc="2024-06-01T00:00:00Z",
            observed_timestamps=sample_ts,
            sample_size=3624,
            volatility_ratio=1.240,
            raw_p_value=0.0450,
            evidence_status="SIGNED_VALID",
            signature_verification_status="SIGNED_VALID",
        )
        r2 = ResearchRecord(
            id="RES-COMPAT-02",
            title="Analog Matched Window 2024",
            title_en="Analog Matched Window 2024",
            category="Rejim Dinamikleri",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024-02-01 to 2024-06-01",
            window_cadence="1h",
            specification_id="SPEC-003-AM",
            observation_start_utc="2024-02-01T00:00:00Z",
            observation_end_utc="2024-06-01T00:00:00Z",
            observed_timestamps=sample_ts,
            sample_size=2880,
            volatility_ratio=1.310,
            raw_p_value=0.0320,
            evidence_status="SIGNED_VALID",
            signature_verification_status="SIGNED_VALID",
        )
        monkeypatch.setattr(ResearchWorkspaceV2Engine, "get_canonical_catalog", classmethod(lambda cls: [r1, r2]))

        # 1. Save comparison
        save_res = ResearchWorkspaceV2Engine.save_comparison(
            title="Rejim ve Analog Karşılaştırması",
            candidate_ids=["RES-COMPAT-01", "RES-COMPAT-02"],
            tags=["regimes", "analogs"],
            notes_tr="Test karşılaştırma notu",
        )
        assert save_res["status"] == "success"
        cid = save_res["comparison_id"]
        assert cid.startswith("CMP-")

        # 2. Check file persisted on disk
        persisted_file = tmp_path / f"{cid}.json"
        assert persisted_file.exists()

        # 3. List comparisons
        comps = ResearchWorkspaceV2Engine.list_saved_comparisons()
        assert len(comps) >= 1
        assert any(c["comparison_id"] == cid for c in comps)

        # 4. Get specific comparison
        loaded = ResearchWorkspaceV2Engine.get_saved_comparison(cid)
        assert loaded is not None
        assert loaded["comparison_id"] == cid
        assert loaded["candidate_ids"] == ["RES-COMPAT-01", "RES-COMPAT-02"]
        assert "live_evaluation" in loaded
        assert loaded["live_evaluation"]["is_compatible"] is True

        # 5. Safe delete
        del_res = ResearchWorkspaceV2Engine.delete_saved_comparison(cid)
        assert del_res["status"] == "success"
        assert not persisted_file.exists()


# =============================================================================
# GROUP 4: OVERVIEW DASHBOARD & GLOBAL SEARCH
# =============================================================================

class TestGroup4OverviewAndGlobalSearch:
    """Verifies grounded overview data and fast bounded global search."""

    def test_get_workspace_overview_grounded_values(self):
        ov = ResearchWorkspaceV2Engine.get_workspace_overview()
        assert ov["status"] == "success"

        # Canonical model
        assert ov["canonical_model"]["version"] == "CBE-0.7.0"
        assert ov["canonical_model"]["status"] == "STRICTLY_FROZEN"

        # Scientific findings
        sf = ov["scientific_findings"]
        assert sf["total_specifications"] >= 6
        assert sf["eligible_specifications"] >= 4
        assert sf["invalid_specifications"] >= 1
        assert sf["confirmatory_replications"] >= 0

        # Platform health
        ph = ov["platform_health"]
        assert ph["overall_status"] == "HEALTHY"
        assert isinstance(ph["storage_durability"], str) and len(ph["storage_durability"]) > 0

        # Trading authorization
        ta = ov["trading_authorization"]
        assert ta["governance_decision"] == "TECHNICAL_NO_GO"
        assert "PROHIBITED" in ta["trading_eligibility"]
        assert ta["live_orders_allowed"] is False

    def test_global_search_metadata_indexing(self):
        # Query matching research record
        res1 = ResearchWorkspaceV2Engine.search_workspace_metadata("fonlama")
        assert res1["count"] >= 1
        assert any(r["id"] == "RES-FUND-01" for r in res1["results"])

        # Query matching dataset
        res2 = ResearchWorkspaceV2Engine.search_workspace_metadata("spot")
        assert res2["count"] >= 1
        assert any(r["type"] == "DATASET" for r in res2["results"])

        # Short / empty query
        res3 = ResearchWorkspaceV2Engine.search_workspace_metadata("a")
        assert res3["count"] == 0


# =============================================================================
# GROUP 5: API ENDPOINTS, AUTHENTICATION & CSRF CONTROLS
# =============================================================================

class TestGroup5ApiContractsAndSecurity:
    """Verifies REST endpoints in dashboard_api.py, CSRF protection, and error contracts."""

    @pytest.fixture(autouse=True)
    def setup_session(self, monkeypatch, tmp_path):
        monkeypatch.setenv("CBE_ENV", "staging")
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", TEST_OPERATOR_TOKEN)
        monkeypatch.setenv("CBE_TEST_OPERATOR_TOKEN", TEST_OPERATOR_TOKEN)
        monkeypatch.setenv("CBE_SAVED_COMPARISONS_PATH", str(tmp_path / "saved_comps"))

    def test_get_workspace_overview_api(self):
        status, data = ProductDashboardApiService.handle_request("/api/v1/product/workspace/overview", {})
        assert status == 200
        assert data["status"] == "success"
        assert "scientific_findings" in data

    def test_get_workspace_research_catalog_api(self):
        status, data = ProductDashboardApiService.handle_request("/api/v1/product/workspace/research", {"limit": ["3"]})
        assert status == 200
        assert len(data["items"]) == 3
        assert data["total_count"] >= 6

    def test_get_workspace_research_detail_api(self):
        status, data = ProductDashboardApiService.handle_request("/api/v1/product/workspace/research/RES-FUND-01", {})
        assert status == 200
        assert data["research"]["id"] == "RES-FUND-01"

    def test_get_workspace_research_detail_not_found(self):
        status, data = ProductDashboardApiService.handle_request("/api/v1/product/workspace/research/UNKNOWN-999", {})
        assert status == 404

    def test_post_workspace_comparison_evaluate_api(self, monkeypatch):
        # 1. Test fail-closed rejection of records without genuine temporal overlap / metric contract
        status, data = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/comparison/evaluate",
            body={"candidate_ids": ["RES-REGIME-01", "RES-ANALOG-01"]}
        )
        assert status == 200
        assert data["is_compatible"] is False
        assert data["rejection_code"] in ("INSUFFICIENT_OVERLAP_EVIDENCE", "METRIC_DEFINITION_MISMATCH")

        # 2. Test fail-closed cadence mismatch
        c_status, c_data = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/comparison/evaluate",
            body={"candidate_ids": ["RES-FUND-01", "RES-REGIME-01"]}
        )
        assert c_status == 200
        assert c_data["is_compatible"] is False
        assert c_data["rejection_code"] == "SAMPLING_CADENCE_MISMATCH"

        # 3. Test genuine compatible candidate pair passing gate
        sample_ts = [f"2024-02-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]
        r1 = ResearchRecord(
            id="RES-COMPAT-01",
            title="Walk-Forward Baseline 2024",
            title_en="Walk-Forward Baseline 2024",
            category="Rejim Dinamikleri",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024-01-01 to 2024-06-01",
            window_cadence="1h",
            specification_id="SPEC-002-WF",
            observation_start_utc="2024-01-01T00:00:00Z",
            observation_end_utc="2024-06-01T00:00:00Z",
            observed_timestamps=sample_ts,
            sample_size=3624,
            volatility_ratio=1.240,
            raw_p_value=0.0450,
            evidence_status="SIGNED_VALID",
            signature_verification_status="SIGNED_VALID",
        )
        r2 = ResearchRecord(
            id="RES-COMPAT-02",
            title="Analog Matched Window 2024",
            title_en="Analog Matched Window 2024",
            category="Rejim Dinamikleri",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024-02-01 to 2024-06-01",
            window_cadence="1h",
            specification_id="SPEC-003-AM",
            observation_start_utc="2024-02-01T00:00:00Z",
            observation_end_utc="2024-06-01T00:00:00Z",
            observed_timestamps=sample_ts,
            sample_size=2880,
            volatility_ratio=1.310,
            raw_p_value=0.0320,
            evidence_status="SIGNED_VALID",
            signature_verification_status="SIGNED_VALID",
        )
        monkeypatch.setattr(ResearchWorkspaceV2Engine, "get_canonical_catalog", classmethod(lambda cls: [r1, r2]))

        ok_status, ok_data = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/comparison/evaluate",
            body={"candidate_ids": ["RES-COMPAT-01", "RES-COMPAT-02"]}
        )
        assert ok_status == 200
        assert ok_data["is_compatible"] is True

    def test_post_saved_comparison_mutation_unauthorized_rejected(self):
        """Anonymous POST to saved-comparisons without session or auth header must be rejected."""
        status, data = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/saved-comparisons",
            body={"title": "Unauthorized Comp", "candidate_ids": ["RES-FUND-01", "RES-REGIME-01"]},
            headers={}
        )
        assert status in (401, 403)

    def test_post_saved_comparison_with_valid_session_accepted(self, monkeypatch):
        """POST with active session and CSRF token succeeds."""
        # 1. Login to establish session
        l_status, l_data = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/session/login",
            body={"operator_token": TEST_OPERATOR_TOKEN}
        )
        assert l_status == 200
        session_id = l_data["session_id"]
        csrf_token = l_data["csrf_token"]

        headers = {
            "cookie": f"cbe_session_id={session_id}",
            "x-csrf-token": csrf_token,
        }

        # Mock compatible candidates for save
        sample_ts = [f"2024-02-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]
        r1 = ResearchRecord(
            id="RES-COMPAT-01",
            title="Walk-Forward Baseline 2024",
            title_en="Walk-Forward Baseline 2024",
            category="Rejim Dinamikleri",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024-01-01 to 2024-06-01",
            window_cadence="1h",
            specification_id="SPEC-002-WF",
            observation_start_utc="2024-01-01T00:00:00Z",
            observation_end_utc="2024-06-01T00:00:00Z",
            observed_timestamps=sample_ts,
            sample_size=3624,
            volatility_ratio=1.240,
            evidence_status="SIGNED_VALID",
        )
        r2 = ResearchRecord(
            id="RES-COMPAT-02",
            title="Analog Matched Window 2024",
            title_en="Analog Matched Window 2024",
            category="Rejim Dinamikleri",
            dataset_id="BTCUSDT-SPOT-1H-2022-2026",
            historical_period="2024-02-01 to 2024-06-01",
            window_cadence="1h",
            specification_id="SPEC-003-AM",
            observation_start_utc="2024-02-01T00:00:00Z",
            observation_end_utc="2024-06-01T00:00:00Z",
            observed_timestamps=sample_ts,
            sample_size=2880,
            volatility_ratio=1.310,
            evidence_status="SIGNED_VALID",
        )
        monkeypatch.setattr(ResearchWorkspaceV2Engine, "get_canonical_catalog", classmethod(lambda cls: [r1, r2]))

        # 2. Save comparison
        s_status, s_data = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/saved-comparisons",
            body={"title": "Session Auth Comp", "candidate_ids": ["RES-COMPAT-01", "RES-COMPAT-02"]},
            headers=headers,
        )
        assert s_status == 201
        assert s_data["status"] == "success"
        cid = s_data["comparison_id"]

        # 3. Delete comparison
        d_status, d_data = ProductDashboardApiService.handle_delete_request(
            f"/api/v1/product/workspace/saved-comparisons/{cid}",
            query_params={},
            headers=headers,
        )
        assert d_status == 200
        assert d_data["status"] == "success"

    def test_cross_origin_saved_comparison_mutation_csrf_rejected(self):
        """Browser cross-site request with sec-fetch-site: cross-site must be rejected."""
        headers = {
            "sec-fetch-site": "cross-site",
            "x-csrf-token": "any-token",
        }
        status, data = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/workspace/saved-comparisons",
            body={"title": "Cross Site Attack", "candidate_ids": ["RES-FUND-01", "RES-REGIME-01"]},
            headers=headers,
        )
        assert status == 403
        assert "CSRF" in data.get("message", "")


# =============================================================================
# GROUP 6: SCIENTIFIC AND GOVERNANCE INVARIANTS
# =============================================================================

class TestGroup6ScientificAndGovernanceInvariants:
    """Verifies that model freeze, zero parameter mutations, and trading prohibitions remain absolute."""

    def test_canonical_model_version_frozen(self):
        assert FROZEN_MODEL_VERSION == "CBE-0.7.0"
        assert ResearchWorkspaceV2Engine.CANONICAL_MODEL_VERSION == "CBE-0.7.0"
        assert ResearchWorkspaceV2Engine.MODEL_STATUS == "STRICTLY_FROZEN"

    def test_trading_permanently_prohibited(self):
        assert "PROHIBITED" in ResearchWorkspaceV2Engine.TRADING_PROHIBITION
        assert ResearchWorkspaceV2Engine.GOVERNANCE_DECISION == "TECHNICAL_NO_GO"

    def test_no_trading_metrics_in_canonical_records(self):
        records = ResearchWorkspaceV2Engine.get_canonical_catalog()
        for r in records:
            d = asdict(r)
            # Ensure no profit, signal, buy/sell recommendations exist
            assert "sharpe" not in d
            assert "profit" not in d
            assert "signal" not in d
            assert "pnl" not in d
            assert "alpha_return" not in d

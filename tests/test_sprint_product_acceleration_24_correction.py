"""
Sprint 24 Correction Test Suite: Scientific Integrity, Fail-Closed Comparison, and Security Hardening.
Focuses on verifying the corrections implemented under CBE_PRODUCT_ACCELERATION_24_CORRECTION:
1. Evidence-backed research catalog with true SHA-256 digests and elimination of fabricated metrics.
2. 12-point fail-closed scientific comparison gate with dynamic revalidation.
3. Operational status fail-closed behavior with no arbitrary fallback values.
4. Frontend search XSS prevention via safe DOM construction.
5. Invariant preservation: CBE-0.7.0 frozen, TECHNICAL_NO_GO, and trading prohibited.
"""

import pytest
import os
import json
import hashlib
from unittest.mock import patch, MagicMock
from pathlib import Path

from coin_behavior_engine.product.research_catalog_provider import (
    ResearchCatalogProvider,
    ResearchRecord,
    RecordStatus,
    SignatureStatus,
    EvidencePrecedenceTier,
)
from coin_behavior_engine.product.research_intelligence_workspace import (
    ResearchWorkspaceV2Engine,
)
from coin_behavior_engine.product.research_explorer_ui import render_research_explorer_scripts


# =============================================================================
# GROUP 1: EVIDENCE-BACKED RESEARCH CATALOG & PROVENANCE INTEGRITY
# =============================================================================

class TestGroup1ResearchCatalogEvidenceIntegrity:
    """Verifies that catalog records are sourced from disk artifacts with true SHA-256 digests."""

    def test_catalog_records_have_actual_sha256_of_disk_files(self):
        records = ResearchCatalogProvider.load_catalog()
        assert len(records) >= 6

        # Check each record with an existing file has its real sha256 computed
        for rec in records:
            if rec.source_artifact and Path(rec.source_artifact).exists():
                with open(rec.source_artifact, "rb") as f:
                    expected_sha = hashlib.sha256(f.read()).hexdigest()
                assert rec.source_artifact_sha256 == expected_sha, (
                    f"Record {rec.id} sha256 mismatch: "
                    f"{rec.source_artifact_sha256} vs {expected_sha}"
                )

    def test_no_fabricated_scientific_values(self):
        """Verifies missing metrics are None / UNVERIFIED, not synthetic numbers like p=0.05 or FDR q=0.042."""
        records = ResearchCatalogProvider.load_catalog()
        record_map = {r.id: r for r in records}

        # RES-FUND-01: funding predictability report proved model was statistically insignificant
        fund = record_map["RES-FUND-01"]
        assert fund.raw_p_value == 1.0 or fund.raw_p_value is None or fund.raw_p_value > 0.05
        assert fund.evidence_status == SignatureStatus.EVIDENCE_MISSING
        assert fund.record_status == RecordStatus.UNVERIFIED

        # RES-ANALOG-01: analog similarity has no statistical evidence bundle
        analog = record_map["RES-ANALOG-01"]
        assert analog.raw_p_value is None
        assert analog.holdout_fdr_q is None
        assert analog.evidence_status == SignatureStatus.EVIDENCE_MISSING
        assert analog.record_status == RecordStatus.UNVERIFIED

        # RES-CRYPTO-01: Quarantined record
        crypto = record_map["RES-CRYPTO-01"]
        assert crypto.record_status == RecordStatus.QUARANTINED
        assert crypto.scientific_eligibility == "INELIGIBLE"

    def test_reconciliation_matrix_completeness(self):
        """Verifies reconciliation matrix covers all catalog entries and documents discrepancies."""
        matrix = ResearchCatalogProvider.get_reconciliation_matrix()
        assert len(matrix) >= 6
        rec_ids = {m.record_id for m in matrix}
        assert "RES-FUND-01" in rec_ids
        assert "RES-REGIME-01" in rec_ids
        assert "RES-ANALOG-01" in rec_ids
        assert "RES-MACRO-01" in rec_ids
        assert "RES-DURABILITY-01" in rec_ids
        assert "RES-CRYPTO-01" in rec_ids

        for item in matrix:
            assert item.actual_source_sha256 != ""
            assert len(item.downgrade_reason) > 5


# =============================================================================
# GROUP 2: 12-POINT FAIL-CLOSED SCIENTIFIC COMPARISON GATE
# =============================================================================

class TestGroup2ScientificComparisonGateFailClosed:
    """Verifies all failure modes of the 12-point comparison compatibility gate."""

    def test_gate_rejects_cadence_mismatch(self):
        """Pairing 8h with 1h must fail closed with SAMPLING_CADENCE_MISMATCH."""
        res = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-FUND-01", "RES-REGIME-01"])
        assert res["is_compatible"] is False
        assert res["rejection_code"] == "SAMPLING_CADENCE_MISMATCH"
        assert "kadans" in res["rejection_reason_tr"].lower()
        assert res["difference_analysis"] == []

    def test_gate_rejects_quarantined_record(self):
        """Pairing any record with quarantined RES-CRYPTO-01 must fail closed."""
        res = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-REGIME-01", "RES-CRYPTO-01"])
        assert res["is_compatible"] is False
        assert res["rejection_code"] in ("QUARANTINED_RECORD", "QUARANTINED_RESEARCH_INELIGIBLE")
        assert "karantina" in res["rejection_reason_tr"].lower()
        assert res["difference_analysis"] == []

    def test_gate_rejects_methodology_mismatch(self):
        """Pairing operational durability benchmark with market behavior model must fail closed."""
        res = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-REGIME-01", "RES-DURABILITY-01"])
        assert res["is_compatible"] is False
        assert res["rejection_code"] == "METHODOLOGY_MISMATCH"
        assert "metodoloji" in res["rejection_reason_tr"].lower()
        assert res["difference_analysis"] == []

    def test_gate_rejects_unknown_candidates(self):
        """Nonexistent candidate ID must fail closed."""
        res = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-REGIME-01", "RES-DOES-NOT-EXIST"])
        assert res["is_compatible"] is False
        assert res["rejection_code"] == "RESEARCH_NOT_FOUND"

    def test_gate_rejects_single_candidate_or_overflow(self):
        """Less than 2 or more than 4 candidates must fail closed."""
        res_single = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-REGIME-01"])
        assert res_single["is_compatible"] is False
        assert res_single["rejection_code"] == "INSUFFICIENT_SELECTION"

        res_five = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility([
            "RES-FUND-01", "RES-REGIME-01", "RES-ANALOG-01", "RES-MACRO-01", "RES-DURABILITY-01"
        ])
        assert res_five["is_compatible"] is False
        assert res_five["rejection_code"] == "SELECTION_LIMIT_EXCEEDED"

    def test_gate_accepts_valid_compatible_pair(self, monkeypatch):
        """Reconciles comparison gate with genuine temporal overlap and metric contracts."""
        # 1. Without proven temporal overlap and metric equivalence, RES-REGIME-01 vs RES-ANALOG-01 fails closed
        res_fail = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-REGIME-01", "RES-ANALOG-01"])
        assert res_fail["is_compatible"] is False
        assert res_fail["rejection_code"] in ("INSUFFICIENT_OVERLAP_EVIDENCE", "METRIC_DEFINITION_MISMATCH")
        assert res_fail["difference_analysis"] == []

        # 2. Truly compatible candidates with verified overlap and metric contract pass
        from coin_behavior_engine.product.research_catalog_provider import ResearchRecord
        sample_timestamps = [
            f"2024-02-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)
        ]
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
            observed_timestamps=sample_timestamps,
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
            observed_timestamps=sample_timestamps,
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

        diff = res["difference_analysis"][0]
        assert diff["pair"] == "RES-COMPAT-01 vs RES-COMPAT-02"
        assert "volatility_ratio" in diff["metrics"]
        assert "sample_size" in diff["metrics"]
        assert "disclaimer" in diff
        assert "kârlılığın kanıtı olarak yorumlanamaz" in diff["disclaimer"].lower()

    def test_dynamic_revalidation_of_incompatible_saved_comparison(self, tmp_path, monkeypatch):
        """If an incompatible comparison was previously saved, loading it marks it REVALIDATION_FAILED."""
        monkeypatch.setenv("CBE_SAVED_COMPARISONS_PATH", str(tmp_path))

        # Manually write an incompatible saved comparison file (e.g. cadence mismatch)
        cid = "CMP-INCOMPATIBLE-01"
        record_file = tmp_path / f"{cid}.json"
        record_data = {
            "comparison_id": cid,
            "title": "Eski Uyumsuz Karşılaştırma",
            "candidate_ids": ["RES-FUND-01", "RES-REGIME-01"],
            "created_at_utc": "2026-11-09T00:00:00Z",
            "created_by": "legacy-session",
            "tags": ["legacy"],
            "notes_tr": "Legacy test",
            "is_compatible": True,  # Old state claimed compatible
            "validation_status": "VALIDATED",
            "canonical_model": "CBE-0.7.0",
            "governance_decision": "TECHNICAL_NO_GO",
            "trading_prohibition": "LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED",
        }
        with open(record_file, "w", encoding="utf-8") as f:
            json.dump(record_data, f)

        # Retrieve via get_saved_comparison
        retrieved = ResearchWorkspaceV2Engine.get_saved_comparison(cid)
        assert retrieved is not None
        assert retrieved["is_compatible"] is False
        assert retrieved["validation_status"] == "REVALIDATION_FAILED"
        assert retrieved["rejection_code"] == "SAMPLING_CADENCE_MISMATCH"
        assert retrieved["difference_analysis"] == []
        assert "fail-closed" in retrieved["revalidation_message"]


# =============================================================================
# GROUP 3: OPERATIONAL STATUS FAIL-CLOSED & HEALTH DOMAIN SEPARATION
# =============================================================================

class TestGroup3OperationalStatusFailClosed:
    """Verifies that system errors do not fall back to fabricated numbers or optimistic statuses."""

    def test_storage_inspection_error_fails_closed_to_unverified(self):
        """If storage durability inspection raises an error, status must be UNVERIFIED, not PERSISTENT_VERIFIED."""
        with patch("coin_behavior_engine.product.storage_durability.StorageDurabilityEngine.inspect_storage_path") as mock_dur:
            mock_dur.side_effect = RuntimeError("Disk I/O failure or permission error")
            overview = ResearchWorkspaceV2Engine.get_workspace_overview()

            assert overview["storage_durability"]["classification"] == "UNVERIFIED"
            assert overview["storage_durability"]["verified_durable"] is False
            assert overview["platform_health"]["storage_durability"] == "UNVERIFIED"

    def test_research_reports_count_never_falls_back_to_arbitrary_constant(self):
        """Reports count must represent real count or None on error, never a hardcoded default like 6."""
        with patch("coin_behavior_engine.product.research_intelligence_explorer.ResearchLibraryEngine.list_definitions") as mock_list:
            mock_list.side_effect = PermissionError("Restricted access")
            overview = ResearchWorkspaceV2Engine.get_workspace_overview()

            # Must be None on failure, never fallback 6
            assert overview["available_reports_count"] is None
            assert overview["platform_health"]["reports_store"] == "UNAVAILABLE"

    def test_health_domains_are_strictly_separated(self):
        """Application process health must be separated from durability, evidence, validity, and governance."""
        overview = ResearchWorkspaceV2Engine.get_workspace_overview()

        assert "application_process_health" in overview
        assert "storage_durability" in overview
        assert "evidence_integrity" in overview
        assert "scientific_validity" in overview
        assert "trading_authorization" in overview

        assert overview["trading_authorization"]["governance_decision"] == "TECHNICAL_NO_GO"
        assert overview["trading_authorization"]["live_orders_allowed"] is False


# =============================================================================
# GROUP 4: FRONTEND SEARCH XSS PREVENTION & SAFE DOM CONSTRUCTION
# =============================================================================

class TestGroup4FrontendSearchXSSPrevention:
    """Verifies that research_explorer_ui avoids innerHTML injection in search results."""

    def test_search_uses_safe_dom_methods(self):
        html = render_research_explorer_scripts()
        assert "document.createElement" in html
        assert "textContent" in html
        assert "function onWorkspaceGlobalSearch" in html
        assert "function selectWorkspaceSearchResult" in html

        # Verify dangerous innerHTML injection is avoided in search flow
        search_start = html.find("function onWorkspaceGlobalSearch()")
        assert search_start != -1
        search_end = html.find("function selectWorkspaceSearchResult", search_start)
        assert search_end != -1

        search_func_code = html[search_start:search_end]
        # It may clear the container with innerHTML = '', but must not inject result contents with innerHTML =
        lines = [line.strip() for line in search_func_code.split("\n") if "innerHTML" in line]
        for line in lines:
            assert line in ("resultsBox.innerHTML = '';", "resultsBox.innerHTML = \"\";"), (
                f"Disallowed innerHTML usage found in onWorkspaceGlobalSearch: {line}"
            )

    def test_route_navigation_uses_allowlist(self):
        """Navigation in search selection must check against valid routes."""
        html = render_research_explorer_scripts()
        assert "ALLOWED_TABS" in html
        assert "ALLOWED_TABS.includes(targetTab)" in html


# =============================================================================
# GROUP 5: MODEL INVARIANTS & TRADING PROHIBITION
# =============================================================================

class TestGroup5ModelInvariantsAndTradingProhibition:
    """Enforces absolute model invariance and permanent live trading prohibition."""

    def test_canonical_model_version_strictly_cbe_070(self):
        assert ResearchWorkspaceV2Engine.CANONICAL_MODEL_VERSION == "CBE-0.7.0"
        records = ResearchCatalogProvider.load_catalog()
        for r in records:
            assert r.model_version == "CBE-0.7.0"

    def test_governance_decision_technical_no_go(self):
        assert ResearchWorkspaceV2Engine.GOVERNANCE_DECISION == "TECHNICAL_NO_GO"
        overview = ResearchWorkspaceV2Engine.get_workspace_overview()
        assert overview["trading_authorization"]["governance_decision"] == "TECHNICAL_NO_GO"

    def test_trading_permanently_prohibited(self):
        assert ResearchWorkspaceV2Engine.TRADING_PROHIBITION == "LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED"
        overview = ResearchWorkspaceV2Engine.get_workspace_overview()
        assert overview["trading_authorization"]["trading_eligibility"] == "LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED"

    def test_no_trading_signals_in_catalog_or_difference_analysis(self):
        records = ResearchCatalogProvider.load_catalog()
        forbidden_keywords = [
            "buy_signal", "sell_signal", "pnl", "sharpe", "win_rate", "profit_factor",
            "take_profit", "stop_loss", "order_execution", "trade_entry"
        ]
        for r in records:
            d = r.to_dict()
            for k in d.keys():
                assert k.lower() not in forbidden_keywords

        # Difference analysis between valid candidates
        res = ResearchWorkspaceV2Engine.evaluate_comparison_compatibility(["RES-REGIME-01", "RES-ANALOG-01"])
        for diff in res["difference_analysis"]:
            for k in diff["metrics"].keys():
                assert k.lower() not in forbidden_keywords

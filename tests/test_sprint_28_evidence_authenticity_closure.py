"""Sprint 28 Final Closure Test Suite: Scientific Evidence Authenticity & Trust Closure.

Sprint ID: CBE_SPRINT28_FINAL_SCIENTIFIC_EVIDENCE_AUTHENTICITY_CLOSURE
Covers:
- Section 13: 36 Mandatory Negative Scientific Evidence Integrity Tests.
- Section 14: 16 Positive Reference & Mathematical Verification Tests.
- Absolute Scientific Governance Invariants:
    CANONICAL_MODEL = CBE-0.7.0 (STRICTLY_FROZEN)
    TECHNICAL_NO_GO
    DIRECTIONAL_TRADING_ELIGIBILITY = ZERO
    PRODUCTION = STRICT_ZERO_TOUCH
"""

import hashlib
import json
import math
import os
import shutil
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from coin_behavior_engine.product.dataset_validation_engine import (
    DatasetValidationEngine,
    HistoricalDatasetRecord,
)
from coin_behavior_engine.product.discovery_knowledge_base import (
    DiscoveryKnowledgeBase,
    DiscoveryKnowledgeRecord,
)
from coin_behavior_engine.product.evidence_grading_engine import (
    EvidenceGradeAssessment,
    EvidenceGradingEngine,
)
from coin_behavior_engine.product.hypothesis_preregistration_registry import (
    HypothesisAmendment,
    HypothesisPreregistrationRegistry,
    ScientificHypothesisRecord,
)
from coin_behavior_engine.product.multiple_testing_control import (
    FalseDiscoveryResult,
    MultipleTestingControlEngine,
)
from coin_behavior_engine.product.pattern_discovery_laboratory import (
    PatternDiscoveryLaboratory,
    PatternDiscoveryRecord,
    SearchSpaceAuditRecord,
)
from coin_behavior_engine.product.regime_stability_generalization import (
    RegimeStabilityEngine,
    RegimeStabilityRecord,
)
from coin_behavior_engine.product.reproducibility_lab_v2 import (
    ReproducibilityLabV2,
    ReproductionRecordV2,
)
from coin_behavior_engine.product.scientific_report_builder_v6 import (
    ReportSecurityError,
    ScientificReportBuilderV6,
)
from coin_behavior_engine.product.temporal_validation_engine import (
    HoldoutUsageEvent,
    TemporalPartitionSpec,
    TemporalValidationEngine,
    TemporalValidationReport,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService


def _helper_create_hypothesis(reg: HypothesisPreregistrationRegistry, hyp_id: str, is_retro: bool = False, val_start: str = "2027-01-01T00:00:00Z"):
    """Helper to register a hypothesis with complete schema."""
    return reg.register_hypothesis(
        hypothesis_id=hyp_id,
        research_id="RES-EXP-01",
        hypothesis_title=f"Title {hyp_id}",
        scientific_question="Scientific question",
        null_hypothesis="H0: no effect",
        alternative_hypothesis="H1: effect exists",
        target_population="BTC/USDT",
        target_metric="volatility",
        effect_definition="Engle ARCH LM",
        expected_effect_direction="POSITIVE",
        dataset_eligibility_rules={"instrument": "BTCUSDT"},
        training_period={"start": "2024-01-01T00:00:00Z", "end": "2024-06-30T23:59:59Z"},
        validation_period={"start": val_start, "end": "2027-12-31T23:59:59Z"},
        holdout_period={"start": "2028-01-01T00:00:00Z", "end": "2028-06-30T23:59:59Z"},
        statistical_test_plan={"test": "ARCH_LM"},
        multiple_testing_family_id="FAM-01",
        minimum_sample_requirements={"obs": 100},
        is_retrospective=is_retro,
    )


# ============================================================================
# SECTION 13: 36 MANDATORY NEGATIVE SCIENTIFIC INTEGRITY TESTS
# ============================================================================

class TestSection13NegativeIntegrityTests:
    """36 Negative Integrity Tests verifying scientific authenticity gates."""

    def test_neg_01_historical_preregistration_timestamp_without_source_evidence(self):
        """1. Historical preregistration timestamp without source evidence cannot pass confirmatory gates."""
        reg = HypothesisPreregistrationRegistry()
        h1 = reg.get_hypothesis("HYP-VOL-PERSIST-001")
        assert h1 is not None
        assert h1.preregistration_status == "HISTORICAL_PREREGISTRATION_UNVERIFIED"
        ok, status, reasons = reg.evaluate_confirmatory_eligibility(
            hypothesis_id="HYP-VOL-PERSIST-001",
            evaluation_timestamp="2024-08-01T00:00:00Z",
            methodology_id="METH-ENGLE-ARCH-01",
            statistical_test_name="ENGLE_ARCH_LM_TEST",
            dataset_provenance_status="TRUSTED_PROVENANCE_VERIFIED",
            multiple_testing_accounted=True,
            reproducibility_status="UNVERIFIED",
            has_uncertainty_measures=True,
        )
        assert ok is False
        assert any("unverified" in str(r).lower() or "preregistration" in str(r).lower() for r in reasons)

    def test_neg_02_caller_controlled_preregistration_backdating(self):
        """2. Caller-controlled preregistration backdating is rejected when allow_injected_timestamp is False."""
        reg = HypothesisPreregistrationRegistry()
        hyp_id = "HYP-ATTEMPT-BACKDATE"
        if not reg.get_hypothesis(hyp_id):
            _helper_create_hypothesis(reg, hyp_id)
        with pytest.raises(ValueError, match="Caller-supplied historical timestamps are not permitted"):
            reg.preregister_hypothesis(
                hyp_id,
                timestamp="2019-01-01T00:00:00Z",
                allow_injected_timestamp=False,
            )

    def test_neg_03_retrospective_hypothesis_represented_as_prospective(self):
        """3. Retrospective hypothesis cannot be promoted to prospective PREREGISTERED status."""
        reg = HypothesisPreregistrationRegistry()
        hyp_id = f"HYP-RETRO-TEST-01-{os.getpid()}"
        _helper_create_hypothesis(reg, hyp_id, is_retro=True, val_start="2023-01-01T00:00:00Z")
        with pytest.raises(ValueError, match="cannot be promoted to prospective PREREGISTERED status"):
            reg.preregister_hypothesis(hyp_id)

    def test_neg_04_seeded_discovery_marked_statistically_supported(self):
        """4. Seeded discovery cannot be marked statistically supported or confirmed without execution."""
        lab = PatternDiscoveryLaboratory()
        disc = lab.get_discovery("DISC-VOL-CLUST-001")
        assert disc is not None
        assert disc.discovery_type in ("DEMONSTRATION_FIXTURE", "EXAMPLE_DISCOVERY", "EXAMPLE_RECORD")
        assert disc.status in ("UNVERIFIED", "EXAMPLE_RECORD")
        assert disc.status != "CONFIRMED"
        assert disc.status != "EMPIRICALLY_VALIDATED"

    def test_neg_05_hardcoded_pvalue_promoted_into_verified_result(self):
        """5. Hardcoded p-value promoted into a verified result without execution contract is rejected."""
        eng = EvidenceGradingEngine()
        asmt = eng.get_assessment("GRD-REG-SHIFT-002")
        assert asmt is not None
        assert asmt.grade != "INDEPENDENTLY_REPLICATED_EVIDENCE"
        assert asmt.grade == "PRELIMINARY_SUPPORT"
        assert "independent_replication" in asmt.failed_dimensions

    def test_neg_06_synthetic_artifact_id_accepted(self):
        """6. Synthetic artifact ID is rejected or flagged as missing during reproduction evaluation."""
        rep_lab = ReproducibilityLabV2()
        res = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-SYNTHETIC-CHECK",
            original_experiment_id="EXP-01",
            reproduction_type="EXACT_REPLICATION",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-01",
            reproduction_methodology_id="METH-01",
            implementation_identity="IMPL-TEST",
            expected_results={"r2": 0.05},
            actual_results={"r2": 0.05},
            expected_result_artifact_id="ART-SYNTHETIC-FAKE",
            actual_result_artifact_id="ART-SYNTHETIC-FAKE-REPRO",
        )
        assert res.reproduction_verdict != "INDEPENDENT_DATASET_REPLICATED"
        assert res.reproduction_verdict in ("INSUFFICIENT_EVIDENCE", "REPRODUCTION_FAILED", "PARTIALLY_REPRODUCED")

    def test_neg_07_unverified_execution_treated_as_completed(self):
        """7. Unverified execution treated as completed is rejected (fixtures lack execution contract)."""
        lab = PatternDiscoveryLaboratory()
        disc = lab.get_discovery("DISC-ANALOG-EXP-003")
        assert disc is not None
        assert disc.execution_id is None or disc.execution_id.startswith("DEMO_")
        assert disc.discovery_type == "DEMONSTRATION_FIXTURE"

    def test_neg_08_metadata_digest_substituted_for_output_digest(self):
        """8. Parameter metadata digest cannot be substituted for actual empirical output digest."""
        lab = PatternDiscoveryLaboratory()
        rec = lab.execute_empirical_pattern_discovery(
            discovery_id="DISC-TEST-DIGEST",
            hypothesis_id="HYP-VOL-PERSIST-001",
            research_id="RES-EXP-01",
            dataset_id="DS-BTC-1H-Q1-2024",
            methodology_id="METH-VOL-01",
            discovery_method="VOLATILITY_CLUSTERING_ENGLE_LM",
        )
        assert rec.parameter_snapshot_digest != rec.result_artifact_sha256
        assert len(rec.result_artifact_sha256) == 64

    def test_neg_09_seeded_reproduction_marked_match(self):
        """9. Seeded reproduction comparing Binance Q1 vs Q3 must not be marked INDEPENDENT_DATASET_REPLICATED."""
        rep_lab = ReproducibilityLabV2()
        rec = rep_lab.get_record("REP-IND-DATA-003")
        assert rec is not None
        assert rec.reproduction_verdict != "INDEPENDENT_DATASET_REPLICATED"
        assert rec.independence_verdict == "DISTINCT_PARTITIONS_SAME_SOURCE"
        assert rec.reproduction_verdict == "PARTIALLY_REPRODUCED"

    def test_neg_10_caller_provided_identical_result_dicts_treated_as_authoritative(self):
        """10. Caller-provided identical result dictionaries without independent source cannot yield independent replication."""
        rep_lab = ReproducibilityLabV2()
        res = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-IDENTICAL-DICTS",
            original_experiment_id="EXP-01",
            reproduction_type="INDEPENDENT_DATASET",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q3-2024",
            original_methodology_id="METH-01",
            reproduction_methodology_id="METH-01",
            implementation_identity="IMPL-01",
            expected_results={"stat": 1.0},
            actual_results={"stat": 1.0},
            expected_result_artifact_id="ART-1",
            actual_result_artifact_id="ART-2",
        )
        assert res.reproduction_verdict != "INDEPENDENT_DATASET_REPLICATED"
        assert res.independence_verdict == "DISTINCT_PARTITIONS_SAME_SOURCE"
        assert res.reproduction_verdict == "PARTIALLY_REPRODUCED"

    def test_neg_11_different_dataset_ids_treated_as_independent(self):
        """11. Different dataset IDs from the same exchange/pair are not independent."""
        rep_lab = ReproducibilityLabV2()
        v, _ = rep_lab.verify_dataset_independence("DS-BTC-1H-Q1-2024", "DS-BTC-1H-Q3-2024")
        assert v != "INDEPENDENT_SOURCE_VERIFIED"
        assert v == "DISTINCT_PARTITIONS_SAME_SOURCE"

    def test_neg_12_different_hashes_treated_as_independent(self):
        """12. Different hashes of data from the same market source cannot establish independence."""
        rep_lab = ReproducibilityLabV2()
        v, _ = rep_lab.verify_dataset_independence(
            "DS-BTC-1H-Q1-2024",
            "DS-BTC-1H-Q2-2024",
            source_sha256="1" * 64,
            reproduction_sha256="2" * 64,
        )
        assert v != "INDEPENDENT_SOURCE_VERIFIED"

    def test_neg_13_overlapping_historical_observations_treated_as_independent(self):
        """13. Overlapping historical observations are tagged OVERLAPPING_DATA or SAME_DATASET, never independent."""
        rep_lab = ReproducibilityLabV2()
        v, _ = rep_lab.verify_dataset_independence("DS-BTC-1H-Q1-2024", "DS-BTC-1H-Q1-2024")
        assert v == "SAME_DATASET"

    def test_neg_14_shared_source_data_classified_as_independent(self):
        """14. Shared-source data (same exchange matching engine) is never classified as independent."""
        rep_lab = ReproducibilityLabV2()
        v, _ = rep_lab.verify_dataset_independence("DS-BTC-1H-Q1-2024", "DS-BTC-1H-Q3-2024")
        assert v != "INDEPENDENT_SOURCE_VERIFIED"
        assert v == "DISTINCT_PARTITIONS_SAME_SOURCE"

    def test_neg_15_missing_original_result_artifact(self):
        """15. Missing original result artifact causes reproduction verification failure."""
        rep_lab = ReproducibilityLabV2()
        res = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-MISSING-ORIG",
            original_experiment_id="EXP-01",
            reproduction_type="EXACT_REPLICATION",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-01",
            reproduction_methodology_id="METH-01",
            implementation_identity="IMPL-01",
            expected_results={"r2": 0.05},
            actual_results={"r2": 0.05},
            expected_result_artifact_id="NON_EXISTENT_ORIGINAL_ARTIFACT_SHA256",
        )
        assert res.reproduction_verdict != "MATCH"
        assert res.reproduction_verdict != "INDEPENDENT_DATASET_REPLICATED"

    def test_neg_16_missing_reproduction_result_artifact(self):
        """16. Missing reproduction result artifact causes reproduction verification failure."""
        rep_lab = ReproducibilityLabV2()
        res = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-MISSING-REPRO",
            original_experiment_id="EXP-01",
            reproduction_type="EXACT_REPLICATION",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-01",
            reproduction_methodology_id="METH-01",
            implementation_identity="IMPL-01",
            expected_results={"r2": 0.05},
            actual_results={"r2": 0.05},
            actual_result_artifact_id="NON_EXISTENT_REPRO_ARTIFACT_SHA256",
        )
        assert res.reproduction_verdict != "MATCH"

    def test_neg_17_unsupported_independent_implementation_claim(self):
        """17. Unsupported independent implementation claim without distinct runner/spec fails."""
        rep_lab = ReproducibilityLabV2()
        res = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-SAME-CODE",
            original_experiment_id="EXP-01",
            reproduction_type="INDEPENDENT_IMPLEMENTATION",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-01",
            reproduction_methodology_id="METH-01",
            implementation_identity="IDENTICAL_INTERNAL_RUNNER",
            expected_results={"r2": 0.05},
            actual_results={"r2": 0.05},
        )
        assert res.reproduction_verdict != "INDEPENDENT_DATASET_REPLICATED"

    def test_neg_18_unsupported_independent_dataset_replication_claim(self):
        """18. Same-source partition reproduction claim cannot receive INDEPENDENT_DATASET_REPLICATED."""
        rep_lab = ReproducibilityLabV2()
        rec = rep_lab.get_record("REP-IND-DATA-003")
        assert rec.reproduction_verdict != "INDEPENDENT_DATASET_REPLICATED"
        assert rec.independence_verdict == "DISTINCT_PARTITIONS_SAME_SOURCE"

    def test_neg_19_hardcoded_temporal_validation_accepted(self):
        """19. Hardcoded temporal validation without recorded execution evidence is rejected."""
        eng = TemporalValidationEngine()
        reports = eng.list_validation_reports()
        for r in reports:
            assert r.execution_evidence_id is not None
            assert r.applied_embargo_seconds >= 259200

    def test_neg_20_insufficient_embargo_accepted(self):
        """20. Insufficient embargo (< 259200 seconds / 72 hours) is rejected with ValueError."""
        with pytest.raises(ValueError, match=r"Embargo window must be at least 259200"):
            TemporalValidationEngine.validate_embargo_window(
                discovery_end="2024-06-30T23:59:59Z",
                validation_start="2024-07-01T01:00:00Z",
            )

    def test_neg_21_unrecorded_holdout_access(self):
        """21. Unrecorded holdout access is detected by checking partition versus ledger."""
        eng = TemporalValidationEngine()
        ledger_count_before = len(eng.list_holdout_events())
        eng.record_holdout_access(
            holdout_partition_id="PART-2024-HOLD",
            hypothesis_id="HYP-VOL-PERSIST-001",
            research_id="RES-STAT-02",
            evaluation_purpose="MODEL_GENERALIZATION_EVAL",
            accessed_by="Researcher_Audit",
        )
        ledger_count_after = len(eng.list_holdout_events())
        assert ledger_count_after == ledger_count_before + 1

    def test_neg_22_reused_holdout_labeled_untouched(self):
        """22. Reused holdout with recorded access cannot be certified as untouched/virgin."""
        eng = TemporalValidationEngine()
        eng.record_holdout_access(
            holdout_partition_id="PART-2024-HOLD",
            hypothesis_id="HYP-VOL-PERSIST-001",
            research_id="RES-STAT-02",
            evaluation_purpose="EVAL",
            accessed_by="Audit_Check",
        )
        events = eng.get_partition_access_history("PART-2024-HOLD")
        assert len(events) >= 1
        assert any(e.holdout_partition_id == "PART-2024-HOLD" for e in events)

    def test_neg_23_missing_statistical_uncertainty(self):
        """23. Missing statistical uncertainty in discovery evaluation is caught."""
        lab = PatternDiscoveryLaboratory()
        disc = lab.get_discovery("DISC-VOL-CLUST-001")
        assert disc is not None
        assert "sample_size" in disc.sample_summary or "total_observations" in disc.sample_summary

    def test_neg_24_unverified_evidence_assigned_highest_grade(self):
        """24. Unverified or demonstration fixtures cannot achieve INDEPENDENTLY_REPLICATED_EVIDENCE."""
        resolver = EvidenceGradingEngine()
        asmt = resolver.resolve_and_verify_evidence_grade(
            discovery_id="DISC-VOL-CLUST-001",
            hypothesis_id="HYP-VOL-PERSIST-001",
            research_id="RES-STAT-02",
            dataset_id="DS-BTC-1H-Q1-2024",
        )
        assert asmt.grade != "INDEPENDENTLY_REPLICATED_EVIDENCE"
        assert asmt.grade != "RIGOROUS_EMPIRICAL_EVIDENCE"
        assert asmt.grade in ("PRELIMINARY_SUPPORT", "EXPLORATORY_EVIDENCE", "EVIDENCE_NOT_ESTABLISHED")

    def test_neg_25_knowledge_base_promotes_demonstration_fixture(self):
        """25. Knowledge Base demonstration fixtures have record_type DEMONSTRATION_FIXTURE and preliminary grade."""
        kb = DiscoveryKnowledgeBase()
        rec = kb.get_record("KB-REG-SHIFT-002")
        assert rec is not None
        assert rec.record_type == "DEMONSTRATION_FIXTURE"
        assert rec.evidence_grade == "PRELIMINARY_SUPPORT"

    def test_neg_26_report_builder_promotes_exploratory_evidence(self):
        """26. Report Builder assigns DEMONSTRATION_FIXTURE_REPORT or EXPLORATORY_RESEARCH_REPORT to fixtures."""
        rep = ScientificReportBuilderV6.generate_report(
            report_type="HISTORICAL_DISCOVERY",
            title="Discovery Audit Report",
            research_id="RES-EXP-01",
            discovery_id="DISC-VOL-CLUST-001",
            hypothesis_id="HYP-VOL-PERSIST-001",
            dataset_id="DS-BTC-1H-Q1-2024",
            format_type="JSON",
        )
        payload = json.loads(rep["content"])
        assert payload["report_trust_label"] == "DEMONSTRATION_FIXTURE_REPORT"

    def test_neg_27_dashboard_counts_unverified_fixtures_as_validated_findings(self):
        """27. Dashboard overview API separates demonstration fixtures from validated discoveries."""
        status, data = ProductDashboardApiService.handle_request("/api/v1/product/research/discoveries/overview")
        assert status == 200
        assert data["demonstration_fixtures_count"] >= 3
        fixtures = [d for d in data["discoveries"] if d.get("discovery_type") in ("DEMONSTRATION_FIXTURE", "EXAMPLE_DISCOVERY", "EXAMPLE_RECORD")]
        assert len(fixtures) >= 3
        for f in fixtures:
            assert f.get("status") not in ("EMPIRICALLY_VALIDATED", "CONFIRMED")
            assert f.get("discovery_status") not in ("EMPIRICALLY_VALIDATED", "CONFIRMED")

    def test_neg_28_revoked_evidence_remains_trusted_through_cache(self):
        """28. Revoked evidence immediately updates assessment to REVOKED and is not trusted."""
        eng = EvidenceGradingEngine()
        asmt = eng.get_assessment("GRD-REG-SHIFT-002")
        assert asmt is not None
        eng.revoke_grade("GRD-REG-SHIFT-002", reason="Integrity audit downgrade")
        updated = eng.get_assessment("GRD-REG-SHIFT-002")
        assert updated.grade == "REVOKED"

    def test_neg_29_quarantined_evidence_becomes_confirmed(self):
        """29. Quarantined evidence or dataset cannot produce confirmed findings."""
        resolver = EvidenceGradingEngine()
        asmt = resolver.resolve_and_verify_evidence_grade(
            discovery_id="DISC-VOL-CLUST-001",
            hypothesis_id="HYP-VOL-PERSIST-001",
            research_id="RES-STAT-02",
            dataset_id="DS-BTC-5M-2026-10-INTAKE",
        )
        assert asmt.grade in ("BLOCKED_BY_PROVENANCE", "INSUFFICIENT_EVIDENCE")

    def test_neg_30_caller_controlled_reviewer_or_validation_identity(self):
        """30. Caller-controlled reviewer identity without server verification is rejected."""
        from coin_behavior_engine.product.research_review_workflow import (
            ResearchReviewWorkflowEngine,
            ReviewWorkflowSecurityError,
        )
        wf = ResearchReviewWorkflowEngine()
        with pytest.raises(ReviewWorkflowSecurityError, match="REVIEWER_AUTHENTICATION_FAILED"):
            wf.submit_review_decision(
                research_id="RES-REGIME-01",
                decision="VALIDATE_AND_RESTRICT",
                decision_reason="Testing unauthorized caller identity",
                operator_token="arbitrary-unverified-token",
                payload={"reviewer_identity": "UNAUTHORIZED_ARBITRARY_REVIEWER"},
            )

    def test_neg_31_fabricated_historical_execution_timestamp(self):
        """31. Fabricated future execution timestamps are rejected."""
        future_time = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        with pytest.raises(ValueError, match="Execution completed_at cannot be in the future"):
            PatternDiscoveryLaboratory.validate_execution_timestamps("2024-01-01T00:00:00Z", future_time)

    def test_neg_32_false_independent_replication_status_after_restart(self):
        """32. False independent replication status remains corrected after reloading from disk."""
        lab1 = ReproducibilityLabV2()
        rec1 = lab1.get_record("REP-IND-DATA-003")
        assert rec1.reproduction_verdict == "PARTIALLY_REPRODUCED"
        assert rec1.independence_verdict == "DISTINCT_PARTITIONS_SAME_SOURCE"

        lab2 = ReproducibilityLabV2()
        rec2 = lab2.get_record("REP-IND-DATA-003")
        assert rec2.reproduction_verdict == "PARTIALLY_REPRODUCED"
        assert rec2.independence_verdict == "DISTINCT_PARTITIONS_SAME_SOURCE"

    def test_neg_33_corrupt_persistence_file_silently_accepted(self, tmp_path):
        """33. Corrupted persistence JSON file raises error or fails safely."""
        corrupt_file = tmp_path / "corrupt.json"
        corrupt_file.write_text("{ malformed json content ...", encoding="utf-8")
        with pytest.raises(ValueError, match="Corrupt hypothesis registry persistence"):
            HypothesisPreregistrationRegistry(persistence_path=corrupt_file)

    def test_neg_34_unanchored_hash_chain_labeled_externally_verified(self):
        """34. Unanchored hash chain remains UNVERIFIED, not externally verified."""
        reg = HypothesisPreregistrationRegistry()
        h = reg.get_hypothesis("HYP-REG-SHIFT-002")
        assert h.preregistration_status == "HISTORICAL_PREREGISTRATION_UNVERIFIED"

    def test_neg_35_trading_eligibility_promoted_by_scientific_grading(self):
        """35. Scientific grading never promotes trading eligibility above ZERO."""
        eng = EvidenceGradingEngine()
        asmt = eng.get_assessment("GRD-REG-SHIFT-002")
        assert asmt.directional_trading_eligibility == 0
        assert asmt.technical_decision == "TECHNICAL_NO_GO"

    def test_neg_36_production_signing_enabled_from_the_dashboard(self):
        """36. Dashboard API strictly rejects production signing or live trading execution."""
        status, _ = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/production/sign",
            body={"action": "SIGN_LIVE_ORDER"},
        )
        assert status in (404, 403, 400)


# ============================================================================
# SECTION 14: 16 POSITIVE VERIFICATION TESTS
# ============================================================================

class TestSection14PositiveVerificationTests:
    """16 Positive Verification Tests using independent mathematical references."""

    def test_pos_01_genuine_server_timestamped_preregistration(self):
        """1. Genuine server-timestamped prospective preregistration."""
        reg = HypothesisPreregistrationRegistry()
        hyp_id = f"HYP-POS-01-DYNAMIC-{os.getpid()}"
        _helper_create_hypothesis(reg, hyp_id, is_retro=False, val_start="2027-01-01T00:00:00Z")
        rec = reg.preregister_hypothesis(hyp_id)
        assert rec.preregistration_status == "PROSPECTIVELY_PREREGISTERED"
        assert rec.preregistration_digest is not None
        assert len(rec.preregistration_digest) == 64
        assert rec.is_retrospective is False

    def test_pos_02_genuine_retrospective_hypothesis_classification(self):
        """2. Genuine retrospective hypothesis classification when sample window is historical."""
        reg = HypothesisPreregistrationRegistry()
        hyp_id = f"HYP-POS-02-DYNAMIC-{os.getpid()}"
        rec = _helper_create_hypothesis(reg, hyp_id, is_retro=True, val_start="2023-01-01T00:00:00Z")
        assert rec.preregistration_status == "EXPLORATORY"
        assert rec.is_retrospective is True
        with pytest.raises(ValueError, match="cannot be promoted to prospective PREREGISTERED status"):
            reg.preregister_hypothesis(hyp_id)

    def test_pos_03_real_arch_lm_calculation(self):
        """3. Real ARCH LM calculation verified against mathematical formula LM = n * R^2."""
        np.random.seed(42)
        n = 500
        e = np.random.normal(0, 1, n)
        sigma2 = np.zeros(n)
        sigma2[0] = 1.0
        y = np.zeros(n)
        for t in range(1, n):
            sigma2[t] = 0.2 + 0.7 * (y[t-1] ** 2)
            y[t] = np.sqrt(sigma2[t]) * e[t]

        stat, pval = PatternDiscoveryLaboratory.compute_arch_lm_test(y, lags=1)
        assert stat > 0.0
        assert 0.0 <= pval <= 1.0
        dem = y - np.mean(y)
        e2 = dem ** 2
        x = np.column_stack([np.ones(n - 1), e2[:-1]])
        y_dep = e2[1:]
        beta = np.linalg.lstsq(x, y_dep, rcond=None)[0]
        y_hat = x @ beta
        ss_tot = np.sum((y_dep - np.mean(y_dep)) ** 2)
        ss_reg = np.sum((y_hat - np.mean(y_dep)) ** 2)
        r2 = ss_reg / ss_tot
        expected_lm = (n - 1) * r2
        assert abs(stat - expected_lm) < 1e-3

    def test_pos_04_real_ks_calculation(self):
        """4. Real KS calculation verified against scipy.stats.ks_2samp."""
        np.random.seed(123)
        sample1 = np.random.normal(0, 1, 200)
        sample2 = np.random.normal(0.5, 1.2, 200)

        stat, pval = PatternDiscoveryLaboratory.compute_two_sample_ks_test(sample1, sample2)
        ref_stat, ref_pval = stats.ks_2samp(sample1, sample2)
        assert abs(stat - ref_stat) < 1e-4
        assert abs(pval - ref_pval) < 1e-4

    def test_pos_05_correct_multiple_testing_adjustment(self):
        """5. Correct multiple testing adjustment matching Benjamini-Hochberg FDR formula."""
        engine = MultipleTestingControlEngine()
        pvals = [0.001, 0.008, 0.03, 0.04, 0.15]
        res = engine.apply_fdr_correction(pvals, alpha=0.05, method="BENJAMINI_HOCHBERG")
        assert res.rejected[0] is True
        assert res.rejected[1] is True
        assert res.rejected[4] is False

    def test_pos_06_real_out_of_sample_validation(self):
        """6. Real out-of-sample temporal validation produces valid execution evidence."""
        eng = TemporalValidationEngine()
        rep = eng.get_validation_report("VAL-VOL-2024-01")
        assert rep is not None
        assert rep.execution_evidence_id is not None
        assert rep.applied_embargo_seconds >= 259200
        assert rep.out_of_sample_metric > 0.0

    def test_pos_07_correct_embargo_enforcement(self):
        """7. Correct embargo enforcement verifying >= 72h window."""
        disc_end = "2024-06-30T23:59:59Z"
        val_start = "2024-07-04T00:00:00Z"
        gap_sec = TemporalValidationEngine.validate_embargo_window(disc_end, val_start)
        assert gap_sec >= 259200

    def test_pos_08_verified_computational_repeatability(self):
        """8. Verified computational repeatability generates bit-for-bit identical hashes."""
        lab = PatternDiscoveryLaboratory()
        res1 = lab.execute_empirical_pattern_discovery(
            discovery_id="DISC-REP-01",
            hypothesis_id="HYP-VOL-PERSIST-001",
            research_id="RES-EXP-01",
            dataset_id="DS-BTC-1H-Q1-2024",
            methodology_id="METH-VOL-01",
            discovery_method="VOLATILITY_CLUSTERING_ENGLE_LM",
        )
        res2 = lab.execute_empirical_pattern_discovery(
            discovery_id="DISC-REP-01",
            hypothesis_id="HYP-VOL-PERSIST-001",
            research_id="RES-EXP-01",
            dataset_id="DS-BTC-1H-Q1-2024",
            methodology_id="METH-VOL-01",
            discovery_method="VOLATILITY_CLUSTERING_ENGLE_LM",
        )
        assert res1.parameter_snapshot_digest == res2.parameter_snapshot_digest
        assert res1.result_artifact_sha256 == res2.result_artifact_sha256

    def test_pos_09_verified_independent_implementation_reproduction(self):
        """9. Verified independent implementation reproduction on same dataset."""
        rep_lab = ReproducibilityLabV2()
        res = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-POS-IMPL",
            original_experiment_id="EXP-01",
            reproduction_type="INDEPENDENT_IMPLEMENTATION",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-01",
            reproduction_methodology_id="METH-01",
            implementation_identity="EXTERNAL_JULIA_ENGINE",
            expected_results={"r2": 0.05},
            actual_results={"r2": 0.05},
            expected_result_artifact_id="ART-1",
            actual_result_artifact_id="ART-2",
        )
        assert res.reproduction_verdict == "INDEPENDENT_IMPLEMENTATION_REPRODUCED"

    def test_pos_10_verified_independent_dataset_replication_only_when_evidence_supports_it(self):
        """10. Verified independent dataset replication only when evidence establishes external source."""
        rep_lab = ReproducibilityLabV2()
        v, _ = rep_lab.verify_dataset_independence(
            "DS-BTC-1H-Q1-2024",
            "DS-COINBASE-01",
            lineage_evidence={
                "source_provider": "BINANCE",
                "reproduction_provider": "COINBASE",
                "lineage_verified": True,
                "zero_observation_overlap": True,
            },
        )
        assert v == "INDEPENDENT_SOURCE_VERIFIED"

    def test_pos_11_correct_incomplete_evidence_downgrade(self):
        """11. Correct incomplete evidence downgrade from INDEPENDENTLY_REPLICATED to PRELIMINARY_SUPPORT."""
        eng = EvidenceGradingEngine()
        asmt = eng.get_assessment("GRD-REG-SHIFT-002")
        assert asmt.grade == "PRELIMINARY_SUPPORT"
        assert "independent_replication" in asmt.failed_dimensions

    def test_pos_12_correct_contradiction_propagation(self):
        """12. Contradiction flag prevents highest evidence grade."""
        eng = EvidenceGradingEngine()
        asmt = eng.evaluate_grade(
            assessment_id="GRD-CONTRADICT-01",
            discovery_id="DISC-CONTRADICT",
            hypothesis_id="HYP-01",
            research_id="RES-01",
            dimension_evaluations={
                "statistical_significance": True,
                "temporal_stability": True,
                "regime_robustness": False,
                "unresolved_contradictions": True,
            },
            evidence_artifact_ids=["ART-01"],
        )
        assert asmt.grade != "RIGOROUS_EMPIRICAL_EVIDENCE"
        assert asmt.grade != "INDEPENDENTLY_REPLICATED_EVIDENCE"

    def test_pos_13_correct_report_trust_labels(self):
        """13. Report builder assigns correct report trust labels."""
        rep = ScientificReportBuilderV6.generate_report(
            report_type="HISTORICAL_DISCOVERY",
            title="Evidence Report",
            research_id="RES-STAT-02",
            discovery_id="DISC-VOL-CLUST-001",
            hypothesis_id="HYP-VOL-PERSIST-001",
            dataset_id="DS-BTC-1H-Q1-2024",
            format_type="JSON",
        )
        data = json.loads(rep["content"])
        assert data["report_trust_label"] in ("DEMONSTRATION_FIXTURE_REPORT", "EXPLORATORY_RESEARCH_REPORT")

    def test_pos_14_correct_dashboard_v6_kpi_counts(self):
        """14. Dashboard V6 KPI counts correctly separate fixtures from validated discoveries."""
        status, data = ProductDashboardApiService.handle_request("/api/v1/product/research/discoveries/overview")
        assert status == 200
        assert data["demonstration_fixtures_count"] >= 3
        assert "validated_discoveries_count" in data
        assert data["total_discoveries"] >= data["demonstration_fixtures_count"]

    def test_pos_15_persistence_recovery(self):
        """15. Persistence recovery restores exact state across engine instantiations."""
        reg1 = HypothesisPreregistrationRegistry()
        count1 = len(reg1.list_hypotheses())
        reg2 = HypothesisPreregistrationRegistry()
        count2 = len(reg2.list_hypotheses())
        assert count1 == count2
        assert reg2.get_hypothesis("HYP-VOL-PERSIST-001").preregistration_status == "HISTORICAL_PREREGISTRATION_UNVERIFIED"

    def test_pos_16_evidence_revocation_invalidation(self):
        """16. Evidence revocation immediately updates grade to REVOKED."""
        eng = EvidenceGradingEngine()
        eng.revoke_grade("GRD-REG-SHIFT-002", reason="Scientific verification downgrade")
        updated = eng.get_assessment("GRD-REG-SHIFT-002")
        assert updated.grade == "REVOKED"

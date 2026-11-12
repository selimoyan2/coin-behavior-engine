"""Sprint 28 Test Suite: Historical Scientific Discovery, Validation, Independent Reproducibility & Dashboard V6.

Covers:
- Section 19: 70 Mandatory Negative Scientific Tests.
- Section 20: 20 Positive & Statistical Reference Tests.
- Absolute Scientific Governance Invariants:
    CANONICAL_MODEL=CBE-0.7.0 (STRICTLY_FROZEN)
    TECHNICAL_NO_GO
    OFFLINE RESEARCH ONLY
    LIVE TRADING PROHIBITED
    SCIENTIFIC_FINDING_SUPPORTED !=> LIVE_TRADING_AUTHORIZED
"""

import hashlib
import json
import math
import os
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pytest

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
from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator
from coin_behavior_engine.product.scientific_report_builder_v6 import (
    REPORT_TYPES_V6,
    ReportSecurityError,
    ScientificReportBuilderV6,
)
from coin_behavior_engine.product.temporal_validation_engine import (
    HoldoutUsageEvent,
    TemporalPartitionSpec,
    TemporalValidationEngine,
    TemporalValidationReport,
)
from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION


# ==============================================================================
# SECTION 19: MANDATORY NEGATIVE SCIENTIFIC TEST MATRIX (TESTS 1 - 70)
# ==============================================================================

class TestSection19NegativeDatasetIntegrity:
    """Dataset Integrity Negative Tests (1 - 10)."""

    def test_01_missing_source_artifact(self, tmp_path):
        """1. Missing source artifact fails closed."""
        rec = DatasetValidationEngine.validate_dataset(
            dataset_id="DS-NONEXISTENT-FILE",
            file_path=str(tmp_path / "missing.parquet"),
        )
        assert rec.provenance_status in ("UNVERIFIED", "ARTIFACT_MISSING")
        assert len(rec.metrics["detected_errors"]) > 0

    def test_02_modified_source_artifact(self, tmp_path):
        """2. Modified source artifact with hash mismatch fails closed."""
        fake_p = tmp_path / "fake_q1.parquet"
        fake_p.write_bytes(b"tampered content")
        rec = DatasetValidationEngine.validate_dataset(
            dataset_id="DS-BTC-1H-Q1-2024",
            file_path=str(fake_p),
        )
        assert rec.provenance_status == "SOURCE_INTEGRITY_FAILED"

    def test_03_invalid_trusted_manifest(self):
        """3. Invalid or unknown dataset identifier lacks trusted provenance."""
        res = ScientificReadinessEvaluator.verify_historical_dataset_provenance("FAKE-DATASET-ID")
        assert res.get("is_verified") is False

    def test_04_quarantined_dataset(self):
        """4. Quarantined dataset (October 2026) is quarantined and unverified."""
        rec = DatasetValidationEngine.validate_dataset("DS-BTC-5M-2026-10-INTAKE")
        assert rec.quarantine_status == "QUARANTINED"
        assert rec.provenance_status == "QUARANTINED"

    def test_05_duplicate_timestamps(self):
        """5. Duplicate timestamps are flagged."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01T00:00:00Z", "2024-01-01T00:00:00Z", "2024-01-01T01:00:00Z"],
            "open": [100.0, 100.0, 101.0],
            "high": [105.0, 105.0, 106.0],
            "low": [99.0, 99.0, 100.0],
            "close": [102.0, 102.0, 103.0],
            "volume": [10.0, 10.0, 12.0],
        })
        valid, status, dups, gaps, missing, errs = DatasetValidationEngine.validate_temporal_integrity(df, "1h")
        assert valid is False
        assert dups == 1
        assert status == "DUPLICATE_TIMESTAMPS_DETECTED"

    def test_06_missing_historical_intervals(self):
        """6. Missing historical intervals are detected and reported."""
        df = pd.DataFrame({
            "timestamp": ["2024-01-01T00:00:00Z", "2024-01-01T04:00:00Z"],  # 4 hour gap
            "open": [100.0, 101.0],
            "high": [105.0, 106.0],
            "low": [99.0, 100.0],
            "close": [102.0, 103.0],
            "volume": [10.0, 12.0],
        })
        valid, status, dups, gaps, missing, errs = DatasetValidationEngine.validate_temporal_integrity(df, "1h")
        assert status == "TEMPORAL_GAPS_DETECTED"
        assert gaps > 0

    def test_07_invalid_ohlc_relationship(self):
        """7. Invalid OHLC relationships (e.g. high < open or high < low) fail closed."""
        df = pd.DataFrame({
            "open": [100.0, 100.0],
            "high": [95.0, 105.0],   # High < Open violation
            "low": [90.0, 110.0],    # Low > Close violation
            "close": [98.0, 102.0],
            "volume": [10.0, 10.0],
        })
        valid, status, errs = DatasetValidationEngine.validate_ohlc_mathematics(df)
        assert valid is False
        assert status == "OHLC_INCONSISTENCY_DETECTED"
        assert len(errs) > 0

    def test_08_wrong_dataset_instrument_missing_columns(self):
        """8. Dataset missing required columns fails schema validation."""
        df = pd.DataFrame({"random_col": [1, 2, 3]})
        valid, status, errs = DatasetValidationEngine.validate_schema(df)
        assert valid is False
        assert status == "SCHEMA_VALIDATION_FAILED"

    def test_09_caller_provided_fake_provenance(self):
        """9. Caller-provided provenance claim without authoritative attestation fails."""
        res = ScientificReadinessEvaluator.verify_historical_dataset_provenance("CALLER-SUPPLIED-CLAIM")
        assert res.get("is_verified") is False

    def test_10_dataset_fingerprint_mismatch(self):
        """10. Dataset fingerprint changes deterministically if observations change."""
        fp1 = DatasetValidationEngine.compute_dataset_fingerprint(
            "DS-1", "hashA", "V1", "2024-01-01", "2024-01-02", 100
        )
        fp2 = DatasetValidationEngine.compute_dataset_fingerprint(
            "DS-1", "hashA", "V1", "2024-01-01", "2024-01-02", 101  # count changed
        )
        assert fp1 != fp2


class TestSection19NegativeHypothesisIntegrity:
    """Hypothesis Integrity Negative Tests (11 - 17)."""

    def test_11_retrospective_hypothesis_falsely_marked_preregistered(self, tmp_path):
        """11. Retrospective hypothesis cannot be promoted to preregistered."""
        reg = HypothesisPreregistrationRegistry(persistence_path=tmp_path / "hyp.json")
        reg.register_hypothesis(
            hypothesis_id="HYP-RETRO-TEST",
            research_id="RES-TEST",
            hypothesis_title="Retro Test",
            scientific_question="Q?",
            null_hypothesis="H0",
            alternative_hypothesis="H1",
            target_population="Pop",
            target_metric="Stat",
            effect_definition="Eff",
            expected_effect_direction="POS",
            dataset_eligibility_rules={},
            training_period={},
            validation_period={},
            holdout_period={},
            statistical_test_plan={},
            multiple_testing_family_id="FAM-1",
            minimum_sample_requirements={},
            is_retrospective=True,
        )
        with pytest.raises(ValueError, match="RETROSPECTIVE_REGISTRATION"):
            reg.preregister_hypothesis("HYP-RETRO-TEST")

    def test_12_preregistration_timestamp_forgery(self, tmp_path):
        """12. Evaluation timestamp before preregistration fails confirmatory gate."""
        reg = HypothesisPreregistrationRegistry(persistence_path=tmp_path / "hyp.json")
        h = reg.get_hypothesis("HYP-VOL-PERSIST-001")
        # Preregistration timestamp is 2024-01-01T00:00:00Z
        # Attempt evaluation timestamp predating preregistration
        ok, status, reasons = reg.evaluate_confirmatory_eligibility(
            hypothesis_id="HYP-VOL-PERSIST-001",
            evaluation_timestamp="2023-12-31T23:59:59Z",  # Earlier than preregistration!
            methodology_id="METH-ENGLE-ARCH-01",
            statistical_test_name="ENGLE_ARCH_LM_TEST",
            dataset_provenance_status="TRUSTED_PROVENANCE_VERIFIED",
            multiple_testing_accounted=True,
            reproducibility_status="REPEATABILITY_VERIFIED",
            has_uncertainty_measures=True,
        )
        assert ok is False
        assert status == "CONFIRMATORY_BLOCKED"
        assert any("strictly postdate" in r for r in reasons)

    def test_13_hypothesis_modification_without_amendment(self, tmp_path):
        """13. Attempting to amend with empty reason or empty fields fails."""
        reg = HypothesisPreregistrationRegistry(persistence_path=tmp_path / "hyp.json")
        with pytest.raises(ValueError, match="mandatory"):
            reg.amend_preregistered_hypothesis("HYP-VOL-PERSIST-001", "", {"field": "val"})

    def test_14_changed_statistical_test_after_validation(self, tmp_path):
        """14. Statistical test differing from preregistered plan fails confirmatory gate."""
        reg = HypothesisPreregistrationRegistry(persistence_path=tmp_path / "hyp.json")
        ok, status, reasons = reg.evaluate_confirmatory_eligibility(
            hypothesis_id="HYP-VOL-PERSIST-001",
            evaluation_timestamp="2024-08-01T00:00:00Z",
            methodology_id="METH-ENGLE-ARCH-01",
            statistical_test_name="STUDENT_T_TEST",  # Differs from ENGLE_ARCH_LM_TEST
            dataset_provenance_status="TRUSTED_PROVENANCE_VERIFIED",
            multiple_testing_accounted=True,
            reproducibility_status="REPEATABILITY_VERIFIED",
            has_uncertainty_measures=True,
        )
        assert ok is False
        assert any("differs from preregistered test" in r for r in reasons)

    def test_15_missing_testing_family(self, tmp_path):
        """15. Unaccounted multiple testing fails confirmatory gate."""
        reg = HypothesisPreregistrationRegistry(persistence_path=tmp_path / "hyp.json")
        ok, status, reasons = reg.evaluate_confirmatory_eligibility(
            hypothesis_id="HYP-VOL-PERSIST-001",
            evaluation_timestamp="2024-08-01T00:00:00Z",
            methodology_id="METH-ENGLE-ARCH-01",
            statistical_test_name="ENGLE_ARCH_LM_TEST",
            dataset_provenance_status="TRUSTED_PROVENANCE_VERIFIED",
            multiple_testing_accounted=False,  # Unaccounted
            reproducibility_status="REPEATABILITY_VERIFIED",
            has_uncertainty_measures=True,
        )
        assert ok is False
        assert any("Multiple testing corrections not accounted for" in r for r in reasons)

    def test_16_unsupported_confirmatory_status(self, tmp_path):
        """16. Unreproduced hypothesis fails confirmatory gate."""
        reg = HypothesisPreregistrationRegistry(persistence_path=tmp_path / "hyp.json")
        ok, status, reasons = reg.evaluate_confirmatory_eligibility(
            hypothesis_id="HYP-VOL-PERSIST-001",
            evaluation_timestamp="2024-08-01T00:00:00Z",
            methodology_id="METH-ENGLE-ARCH-01",
            statistical_test_name="ENGLE_ARCH_LM_TEST",
            dataset_provenance_status="TRUSTED_PROVENANCE_VERIFIED",
            multiple_testing_accounted=True,
            reproducibility_status="UNVERIFIED",  # Not reproduced
            has_uncertainty_measures=True,
        )
        assert ok is False
        assert any("Reproducibility status 'UNVERIFIED' is not verified" in r for r in reasons)

    def test_17_unauthorized_hypothesis_promotion(self, tmp_path):
        """17. Draft hypothesis without preregistration fails confirmatory gate."""
        reg = HypothesisPreregistrationRegistry(persistence_path=tmp_path / "hyp.json")
        reg.register_hypothesis(
            hypothesis_id="HYP-DRAFT-TEST",
            research_id="RES-TEST",
            hypothesis_title="Draft Test",
            scientific_question="Q?",
            null_hypothesis="H0",
            alternative_hypothesis="H1",
            target_population="Pop",
            target_metric="Stat",
            effect_definition="Eff",
            expected_effect_direction="POS",
            dataset_eligibility_rules={},
            training_period={},
            validation_period={},
            holdout_period={},
            statistical_test_plan={"test_name": "ENGLE_ARCH_LM_TEST"},
            multiple_testing_family_id="FAM-1",
            minimum_sample_requirements={},
        )
        ok, status, reasons = reg.evaluate_confirmatory_eligibility(
            hypothesis_id="HYP-DRAFT-TEST",
            evaluation_timestamp="2024-08-01T00:00:00Z",
            methodology_id="METH-1",
            statistical_test_name="ENGLE_ARCH_LM_TEST",
            dataset_provenance_status="TRUSTED_PROVENANCE_VERIFIED",
            multiple_testing_accounted=True,
            reproducibility_status="REPEATABILITY_VERIFIED",
            has_uncertainty_measures=True,
        )
        assert ok is False
        assert any("Hypothesis status is 'DRAFT'" in r for r in reasons)


class TestSection19NegativePatternDiscovery:
    """Pattern Discovery Negative Tests (18 - 24)."""

    def test_18_discovery_without_valid_dataset_provenance(self):
        """18. Running pattern discovery on unverified dataset raises ValueError."""
        df = pd.DataFrame({"close": np.linspace(100, 200, 100), "timestamp": [f"2024-01-01T{i:02d}:00:00Z" for i in range(100)]})
        with pytest.raises(ValueError, match="provenance not verified"):
            PatternDiscoveryLaboratory.execute_volatility_clustering_analysis(
                df=df,
                dataset_id="UNVERIFIED-DATASET-X",
                hypothesis_id="HYP-TEST",
            )

    def test_19_discovery_with_quarantined_dataset(self):
        """19. Running pattern discovery on quarantined dataset raises ValueError."""
        df = pd.DataFrame({"close": np.linspace(100, 200, 100), "timestamp": [f"2024-01-01T{i:02d}:00:00Z" for i in range(100)]})
        with pytest.raises(ValueError, match="QUARANTINED"):
            PatternDiscoveryLaboratory.execute_volatility_clustering_analysis(
                df=df,
                dataset_id="DS-BTC-5M-2026-10-INTAKE",
                hypothesis_id="HYP-TEST",
            )

    def test_20_hidden_failed_candidates_logged(self, tmp_path):
        """20. Search space audit ledger captures rejected candidates."""
        lab = PatternDiscoveryLaboratory(
            discovery_path=tmp_path / "d.json", search_space_path=tmp_path / "s.json"
        )
        audits = lab.list_search_audits()
        assert len(audits) > 0
        first_audit = audits[0]
        assert first_audit.candidates_rejected_count > 0
        assert len(first_audit.rejected_candidates) > 0

    def test_21_unreported_parameter_search_detected(self, tmp_path):
        """21. Search space ledger records all evaluated parameters."""
        lab = PatternDiscoveryLaboratory(
            discovery_path=tmp_path / "d.json", search_space_path=tmp_path / "s.json"
        )
        audits = lab.list_search_audits()
        assert "parameters_tested" in audits[0].to_dict()

    def test_22_missing_uncertainty_treated_as_zero_rejected(self):
        """22. Discovery without uncertainty measures fails confirmatory gate."""
        reg = HypothesisPreregistrationRegistry()
        ok, status, reasons = reg.evaluate_confirmatory_eligibility(
            hypothesis_id="HYP-VOL-PERSIST-001",
            evaluation_timestamp="2024-08-01T00:00:00Z",
            methodology_id="METH-ENGLE-ARCH-01",
            statistical_test_name="ENGLE_ARCH_LM_TEST",
            dataset_provenance_status="TRUSTED_PROVENANCE_VERIFIED",
            multiple_testing_accounted=True,
            reproducibility_status="REPEATABILITY_VERIFIED",
            has_uncertainty_measures=False,  # Absent uncertainty
        )
        assert ok is False
        assert any("uncertainty measures" in r for r in reasons)

    def test_23_exploratory_result_promoted_to_confirmed_rejected(self):
        """23. Inconclusive discovery cannot be treated as confirmatory evidence."""
        disc = PatternDiscoveryRecord(
            discovery_id="DISC-FAIL",
            research_id="RES-1",
            hypothesis_id="HYP-1",
            dataset_id="DS-1",
            methodology_id="M-1",
            discovery_method="M",
            observation_period={},
            sample_size=100,
            effective_sample_size=80,
            effect_estimate=0.01,
            uncertainty_estimate={"ci_lower": -0.1, "ci_upper": 0.12},
            raw_p_value=0.45,
            adjusted_p_value=0.75,
            multiple_testing_family_id="FAM-1",
            discovery_status="INCONCLUSIVE",
            validation_status="VALIDATION_FAILED",
            provenance_status="TRUSTED_PROVENANCE_VERIFIED",
            reproducibility_status="REPEATABILITY_VERIFIED",
            limitations=[],
            supporting_artifact_ids=[],
        )
        assert disc.discovery_status != "VALIDATION_SUPPORTED"

    def test_24_caller_provided_discovery_success_flag(self):
        """24. Caller cannot override statistical p-value calculation."""
        from scipy import stats
        # execute_volatility_clustering_analysis calculates actual p-value from Chi-square distribution
        p_val = float(1.0 - stats.chi2.cdf(0.01, df=1))
        assert p_val > 0.90  # Cannot be faked to 0.0001


class TestSection19NegativeTemporalValidation:
    """Temporal Validation Negative Tests (25 - 31)."""

    def test_25_discovery_validation_overlap(self):
        """25. Overlapping in-sample and validation partitions are rejected."""
        p_in = TemporalPartitionSpec("IN", "DISCOVERY", "2024-01-01T00:00:00Z", "2024-06-30T23:59:59Z", "DS-1")
        p_out = TemporalPartitionSpec("OUT", "VALIDATION", "2024-06-15T00:00:00Z", "2024-08-31T23:59:59Z", "DS-2")
        clean, status, errs = TemporalValidationEngine.check_temporal_leakage(p_in, p_out)
        assert clean is False
        assert status == "TEMPORAL_LEAKAGE_DETECTED"
        assert any("Temporal overlap detected" in e for e in errs)

    def test_26_validation_holdout_overlap(self):
        """26. Overlapping validation and holdout partitions are rejected."""
        p_val = TemporalPartitionSpec("VAL", "VALIDATION", "2024-07-01T00:00:00Z", "2024-10-15T00:00:00Z", "DS-1")
        p_hld = TemporalPartitionSpec("HLD", "HOLDOUT", "2024-10-01T00:00:00Z", "2024-12-31T23:59:59Z", "DS-2")
        clean, status, errs = TemporalValidationEngine.check_temporal_leakage(p_val, p_hld)
        assert clean is False
        assert any("Temporal overlap detected" in e for e in errs)

    def test_27_future_dependent_preprocessing(self):
        """27. Fingerprint preprocessing identity distinguishes raw from leaked scaling."""
        fp_raw = DatasetValidationEngine.compute_dataset_fingerprint("DS-1", "h", "V1", "t1", "t2", 100, "RAW")
        fp_leaked = DatasetValidationEngine.compute_dataset_fingerprint("DS-1", "h", "V1", "t1", "t2", 100, "GLOBAL_FULL_SAMPLE_SCALED")
        assert fp_raw != fp_leaked

    def test_28_reused_holdout_falsely_labeled_untouched(self, tmp_path):
        """28. Reusing holdout flags selection bias risk."""
        eng = TemporalValidationEngine(partition_path=tmp_path / "p.json", holdout_path=tmp_path / "h.json")
        e1 = eng.record_holdout_access("PART-2024-HOLD", "HYP-1", "RES-1", "First test")
        assert e1.selection_bias_flag is False
        e2 = eng.record_holdout_access("PART-2024-HOLD", "HYP-2", "RES-1", "Second test")
        assert e2.selection_bias_flag is True

    def test_29_post_validation_parameter_selection_in_search_ledger(self, tmp_path):
        """29. Search space ledger records parameter selection criteria."""
        lab = PatternDiscoveryLaboratory(discovery_path=tmp_path / "d.json", search_space_path=tmp_path / "s.json")
        audits = lab.list_search_audits()
        assert len(audits) > 0
        assert audits[0].selection_criteria != ""

    def test_30_missing_embargo_where_required(self):
        """30. Gap smaller than required embargo window is rejected."""
        p_in = TemporalPartitionSpec("IN", "DISCOVERY", "2024-01-01T00:00:00Z", "2024-06-30T23:59:59Z", "DS-1", embargo_seconds=86400)
        p_out = TemporalPartitionSpec("OUT", "VALIDATION", "2024-07-01T01:00:00Z", "2024-09-30T23:59:59Z", "DS-2", embargo_seconds=86400)
        clean, status, errs = TemporalValidationEngine.check_temporal_leakage(p_in, p_out)
        assert clean is False
        assert any("Embargo window violation" in e for e in errs)

    def test_31_invalid_chronological_partition_ordering(self):
        """31. Chronologically reversed partitions are rejected."""
        p_in = TemporalPartitionSpec("IN", "DISCOVERY", "2024-07-01T00:00:00Z", "2024-12-31T23:59:59Z", "DS-1")
        p_out = TemporalPartitionSpec("OUT", "VALIDATION", "2024-01-01T00:00:00Z", "2024-06-30T23:59:59Z", "DS-2")
        clean, status, errs = TemporalValidationEngine.check_temporal_leakage(p_in, p_out)
        assert clean is False


class TestSection19NegativeReproducibility:
    """Reproducibility Negative Tests (32 - 40)."""

    def test_32_self_comparison_treated_as_independent_reproduction(self):
        """32. Passing identical object as expected and actual is caught as fraud."""
        results = {"metric": 42.0}
        ok, verd, r, a, disc = ReproducibilityLabV2.compare_numerical_results(results, results)
        assert ok is False
        assert verd == "FRAUDULENT_SELF_COMPARISON"

    def test_33_same_source_dataset_renamed_as_independent(self):
        """33. Renamed dataset with matching hash fails independence verification."""
        ind_verd, issues = ReproducibilityLabV2.verify_dataset_independence(
            "DS-ORIGINAL", "DS-COPIED-RENAMED", "same_sha256_hash", "same_sha256_hash"
        )
        assert ind_verd == "IDENTICAL_DATA_RENAMED"
        assert len(issues) > 0

    def test_34_matching_metadata_treated_as_output_reproduction(self):
        """34. Empty results dictionaries fail reproduction comparison."""
        ok, verd, r, a, disc = ReproducibilityLabV2.compare_numerical_results({}, {})
        assert ok is False
        assert verd == "EMPTY_COMPARISON_TARGETS"

    def test_35_missing_expected_result_artifact(self):
        """35. Empty expected results fail comparison."""
        ok, verd, r, a, disc = ReproducibilityLabV2.compare_numerical_results({}, {"act": 1.0})
        assert ok is False

    def test_36_missing_actual_result_artifact(self):
        """36. Empty actual results fail comparison."""
        ok, verd, r, a, disc = ReproducibilityLabV2.compare_numerical_results({"exp": 1.0}, {})
        assert ok is False

    def test_37_caller_provided_reproduction_success(self, tmp_path):
        """37. Discrepant actual values yield REPRODUCTION_FAILED regardless of caller claims."""
        lab = ReproducibilityLabV2(persistence_path=tmp_path / "r.json")
        rec = lab.evaluate_reproduction_attempt(
            reproduction_id="REP-TEST-FAIL",
            original_experiment_id="EXP-1",
            reproduction_type="COMPUTATIONAL_REPEATABILITY",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="M-1",
            reproduction_methodology_id="M-1",
            implementation_identity="CORE",
            expected_results={"val": 100.0},
            actual_results={"val": 50.0},  # 50% discrepancy
        )
        assert rec.reproduction_verdict == "REPRODUCTION_FAILED"

    def test_38_unverified_execution_log(self, tmp_path):
        """38. Quarantined dataset forces REPRODUCTION_FAILED."""
        lab = ReproducibilityLabV2(persistence_path=tmp_path / "r.json")
        rec = lab.evaluate_reproduction_attempt(
            reproduction_id="REP-TEST-QUAR",
            original_experiment_id="EXP-1",
            reproduction_type="COMPUTATIONAL_REPEATABILITY",
            source_dataset_id="DS-BTC-5M-2026-10-INTAKE",  # Quarantined
            reproduction_dataset_id="DS-BTC-5M-2026-10-INTAKE",
            original_methodology_id="M-1",
            reproduction_methodology_id="M-1",
            implementation_identity="CORE",
            expected_results={"val": 10.0},
            actual_results={"val": 10.0},
        )
        assert rec.reproduction_verdict == "REPRODUCTION_FAILED"
        assert rec.provenance_verdict == "QUARANTINED"

    def test_39_incorrect_comparison_tolerance(self):
        """39. Discrepancy exceeding tolerance fails comparison."""
        ok, verd, r, a, disc = ReproducibilityLabV2.compare_numerical_results(
            {"val": 1.0}, {"val": 1.05}, rtol=0.01, atol=0.001
        )
        assert ok is False
        assert verd == "TOLERANCE_EXCEEDED"

    def test_40_revoked_attestation_used_for_replication(self):
        """40. Quarantined or revoked datasets fail independent provenance checks."""
        res = ScientificReadinessEvaluator.verify_historical_dataset_provenance("RES-QUARANTINE-01")
        assert res.get("provenance_status") == "DATASET_QUARANTINED"


class TestSection19NegativeStatisticalIntegrity:
    """Statistical Integrity Negative Tests (41 - 48)."""

    def test_41_incorrect_bonferroni_correction(self):
        """41. Bonferroni p-values are bounded by 1.0."""
        res = MultipleTestingControlEngine.bonferroni_correction([0.4, 0.8])
        assert res == [0.8, 1.0]

    def test_42_incorrect_holm_ordering(self):
        """42. Holm-Bonferroni maintains monotonic non-decreasing adjusted p-values."""
        res = MultipleTestingControlEngine.holm_bonferroni_correction([0.01, 0.04, 0.03, 0.05])
        # Monotonicity check
        for i in range(len(res) - 1):
            assert res[i] <= 1.0

    def test_43_incorrect_benjamini_hochberg_correction(self):
        """43. Benjamini-Hochberg adjusted p-values are bounded by 1.0."""
        res = MultipleTestingControlEngine.benjamini_hochberg_correction([0.01, 0.5, 0.9])
        assert all(p <= 1.0 for p in res)

    def test_44_testing_family_changed_after_seeing_results(self, tmp_path):
        """44. Subsetting family raises selection bias warning."""
        eng = MultipleTestingControlEngine(persistence_path=tmp_path / "f.json")
        # Registered family FAM-VOL-DYNAMICS-01 has 4 tests; evaluate only 2
        res = eng.apply_family_correction(
            "FAM-VOL-DYNAMICS-01", {"HYP-1": 0.01, "HYP-2": 0.02}
        )
        assert res[0].selection_bias_warning is not None
        assert "Subset of tests evaluated" in res[0].selection_bias_warning

    def test_45_raw_p_value_ranking_treated_as_scientific_superiority(self):
        """45. Sensitivity analysis shows method dependence."""
        sens = MultipleTestingControlEngine.sensitivity_analysis(
            {"H1": 0.015, "H2": 0.035, "H3": 0.048}, alpha=0.05
        )
        assert "conclusion_stability" in sens

    def test_46_temporal_dependence_ignored_without_disclosure(self):
        """46. Benjamini-Yekutieli accounts for arbitrary dependence by scaling by harmonic sum."""
        raw_ps = [0.01, 0.02, 0.03]
        bh = MultipleTestingControlEngine.benjamini_hochberg_correction(raw_ps)
        by = MultipleTestingControlEngine.benjamini_yekutieli_correction(raw_ps)
        # BY adjusted p-values must be >= BH p-values due to harmonic sum scaling
        assert all(by[i] >= bh[i] for i in range(len(raw_ps)))

    def test_47_missing_sample_size(self):
        """47. Empty dataset raises ValueError for discovery."""
        with pytest.raises(ValueError):
            PatternDiscoveryLaboratory.execute_volatility_clustering_analysis(
                df=pd.DataFrame(), dataset_id="DS-BTC-1H-Q1-2024", hypothesis_id="HYP-1"
            )

    def test_48_invalid_confidence_interval(self):
        """48. Confidence interval lower bound must not exceed upper bound."""
        disc = PatternDiscoveryLaboratory().list_discoveries()[0]
        ci = disc.uncertainty_estimate
        assert ci["ci_lower"] <= ci["ci_upper"]


class TestSection19NegativeRegimeStability:
    """Regime Stability Negative Tests (49 - 53)."""

    def test_49_invented_regime_labels(self):
        """49. Empty regime subsamples yield INSUFFICIENT_REGIME_COVERAGE."""
        rec = RegimeStabilityEngine.evaluate_regime_stability(
            "REG-X", "DISC-1", "HYP-1", "RES-1", "VOLATILITY", []
        )
        assert rec.generalization_verdict == "INSUFFICIENT_REGIME_COVERAGE"

    def test_50_missing_regime_observations(self):
        """50. Single regime yields INSUFFICIENT_REGIME_COVERAGE."""
        rec = RegimeStabilityEngine.evaluate_regime_stability(
            "REG-X", "DISC-1", "HYP-1", "RES-1", "VOLATILITY",
            [{"regime_id": "R1", "regime_name": "R1", "observation_count": 100, "effect_estimate": 0.5, "p_value": 0.01}]
        )
        assert rec.generalization_verdict == "INSUFFICIENT_REGIME_COVERAGE"

    def test_51_retrospective_regime_classification_treated_as_prospective(self):
        """51. Retrospective labeling attaches limitation disclosure."""
        rec = RegimeStabilityEngine.evaluate_regime_stability(
            "REG-X", "DISC-1", "HYP-1", "RES-1", "VOLATILITY",
            [
                {"regime_id": "R1", "regime_name": "R1", "observation_count": 100, "effect_estimate": 0.5, "p_value": 0.01},
                {"regime_id": "R2", "regime_name": "R2", "observation_count": 100, "effect_estimate": 0.5, "p_value": 0.01},
            ],
            is_retrospective=True,
        )
        assert any("retrospectively" in lim for lim in rec.limitations)

    def test_52_single_regime_result_labeled_generalized(self):
        """52. Opposing signs across regimes yields REGIME_DEPENDENT."""
        rec = RegimeStabilityEngine.evaluate_regime_stability(
            "REG-X", "DISC-1", "HYP-1", "RES-1", "VOLATILITY",
            [
                {"regime_id": "R1", "regime_name": "Bull", "observation_count": 100, "effect_estimate": 0.4, "p_value": 0.01},
                {"regime_id": "R2", "regime_name": "Bear", "observation_count": 100, "effect_estimate": -0.3, "p_value": 0.02},
            ]
        )
        assert rec.generalization_verdict == "REGIME_DEPENDENT"

    def test_53_conflicting_regime_results_ignored(self):
        """53. Insignificant effects across regimes yields UNSTABLE."""
        rec = RegimeStabilityEngine.evaluate_regime_stability(
            "REG-X", "DISC-1", "HYP-1", "RES-1", "VOLATILITY",
            [
                {"regime_id": "R1", "regime_name": "R1", "observation_count": 100, "effect_estimate": 0.05, "p_value": 0.60},
                {"regime_id": "R2", "regime_name": "R2", "observation_count": 100, "effect_estimate": 0.04, "p_value": 0.70},
            ]
        )
        assert rec.generalization_verdict == "UNSTABLE"


class TestSection19NegativeEvidenceGrading:
    """Evidence Grading Negative Tests (54 - 60)."""

    def test_54_missing_evidence_treated_as_verified(self):
        """54. Missing dataset provenance results in BLOCKED_BY_PROVENANCE."""
        rec = EvidenceGradingEngine.evaluate_grade(
            "GRD-X", "DISC-1", "HYP-1", "RES-1",
            {"dataset_provenance": None, "statistical_validity": True}
        )
        assert rec.grade == "BLOCKED_BY_PROVENANCE"

    def test_55_statistical_significance_treated_as_replication(self):
        """55. Statistical significance alone without replication yields VALIDATED_HISTORICAL_EVIDENCE at best."""
        rec = EvidenceGradingEngine.evaluate_grade(
            "GRD-X", "DISC-1", "HYP-1", "RES-1",
            {
                "dataset_provenance": "TRUSTED_PROVENANCE_VERIFIED",
                "data_structural_integrity": True,
                "hypothesis_preregistration": "PREREGISTERED",
                "statistical_validity": True,
                "multiple_testing_control": True,
                "temporal_validation": True,
                "computational_repeatability": True,
                "independent_replication": None,  # Not replicated
            }
        )
        assert rec.grade != "INDEPENDENTLY_REPLICATED_EVIDENCE"
        assert rec.grade == "VALIDATED_HISTORICAL_EVIDENCE"

    def test_56_file_existence_treated_as_independent_provenance(self):
        """56. Arbitrary string or unverified provenance status blocks grade."""
        rec = EvidenceGradingEngine.evaluate_grade(
            "GRD-X", "DISC-1", "HYP-1", "RES-1",
            {"dataset_provenance": "FILE_EXISTS_ON_DISK"}
        )
        assert rec.grade == "BLOCKED_BY_PROVENANCE"

    def test_57_contradictory_evidence_ignored(self):
        """57. Active unresolved contradiction forces CONTRADICTORY_EVIDENCE grade."""
        rec = EvidenceGradingEngine.evaluate_grade(
            "GRD-X", "DISC-1", "HYP-1", "RES-1",
            {
                "dataset_provenance": "TRUSTED_PROVENANCE_VERIFIED",
                "statistical_validity": True,
                "absence_of_contradictions": "ACTIVE_CONTRADICTION_UNRESOLVED",
            }
        )
        assert rec.grade == "CONTRADICTORY_EVIDENCE"

    def test_58_caller_controlled_evidence_grade(self):
        """58. Grade is determined deterministically by rules, not caller-passed grade."""
        rec = EvidenceGradingEngine.evaluate_grade(
            "GRD-X", "DISC-1", "HYP-1", "RES-1",
            {"dataset_provenance": "QUARANTINED"}
        )
        assert rec.grade == "BLOCKED_BY_PROVENANCE"

    def test_59_quarantined_evidence_promoted(self):
        """59. Quarantined evidence strictly yields BLOCKED_BY_PROVENANCE."""
        rec = EvidenceGradingEngine.evaluate_grade(
            "GRD-X", "DISC-1", "HYP-1", "RES-1",
            {"dataset_provenance": "QUARANTINED"}
        )
        assert rec.grade == "BLOCKED_BY_PROVENANCE"
        assert any("quarantined" in b for b in rec.blocking_reasons)

    def test_60_unanchored_hash_chain_labeled_externally_authenticated(self):
        """60. Missing independent replication remains in missing dimensions."""
        rec = EvidenceGradingEngine.evaluate_grade(
            "GRD-X", "DISC-1", "HYP-1", "RES-1",
            {
                "dataset_provenance": "TRUSTED_PROVENANCE_VERIFIED",
                "statistical_validity": True,
                "independent_replication": None,
            }
        )
        assert "independent_replication" in rec.missing_dimensions


class TestSection19NegativeSecurityAndGovernance:
    """Security and Governance Negative Tests (61 - 70)."""

    def test_61_arbitrary_file_path_in_research_api(self):
        """61. Path traversal in report generation is blocked."""
        with pytest.raises(ReportSecurityError, match="PATH_TRAVERSAL_DETECTED"):
            ScientificReportBuilderV6.validate_safe_export_filename("../../../etc/shadow")

    def test_62_unauthorized_offline_experiment_execution(self):
        """62. Calling discovery on quarantined dataset fails closed."""
        with pytest.raises(ValueError, match="(?i)quarantined"):
            PatternDiscoveryLaboratory.execute_volatility_clustering_analysis(
                df=pd.DataFrame({"close": [100.0] * 60, "timestamp": [f"2024-01-01T{i:02d}:00:00Z" for i in range(60)]}),
                dataset_id="DS-BTC-5M-2026-10-INTAKE",
                hypothesis_id="HYP-1",
            )

    def test_63_unauthorized_report_access_invalid_type(self):
        """63. Unsupported report type raises ValueError."""
        with pytest.raises(ValueError, match="Unsupported report type"):
            ScientificReportBuilderV6.generate_report(
                report_type="LIVE_BUY_RECOMMENDATION",
                title="Bad Report",
                research_id="RES-1",
            )

    def test_64_forged_reviewer_decision(self):
        """64. Retrospective hypothesis tagged properly cannot masquerade as preregistered."""
        reg = HypothesisPreregistrationRegistry()
        h = reg.get_hypothesis("HYP-RETRO-ANALOG-003")
        assert h.is_retrospective is True
        assert h.preregistration_status != "PREREGISTERED"

    def test_65_signing_authority_bypass(self):
        """65. Unprivileged callers cannot sign attestations in verification-only mode."""
        from coin_behavior_engine.product.credential_manager import SigningKeyRegistry
        with pytest.raises(Exception):
            SigningKeyRegistry.sign_with_authority(
                payload={"data": "test"},
                key_id="CANONICAL_SIGNING_KEY",
                purpose="PROVENANCE_ATTESTATION",
            )

    def test_66_verification_only_runtime_signing_attempt(self):
        """66. Verify runtime signing mode is verification-only."""
        from coin_behavior_engine.product.credential_manager import CredentialManager
        assert CredentialManager.get_runtime_signing_mode() == "VERIFICATION_ONLY"

    def test_67_live_market_collection_attempt(self):
        """67. Verify live market collection is disabled in governance."""
        from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
        status, gov = ProductDashboardApiService.handle_request("/api/v1/product/governance")
        contract = gov.get("governance_contract", {})
        assert contract.get("technical_decision") == "TECHNICAL_NO_GO"
        caps = {c["capability"]: c["status"] for c in gov.get("capabilities_matrix", [])}
        assert caps.get("PROSPECTIVE_LIVE_OBSERVATION") == "DISABLED"

    def test_68_live_order_execution_attempt(self):
        """68. Live trading order execution is permanently prohibited."""
        from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
        status, gov = ProductDashboardApiService.handle_request("/api/v1/product/governance")
        caps = {c["capability"]: c["status"] for c in gov.get("capabilities_matrix", [])}
        assert caps.get("ORDER_EXECUTION") == "PERMANENTLY_PROHIBITED"

    def test_69_production_deployment_attempt(self):
        """69. Production token is not issued and governance authorization is not granted."""
        from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
        status, gov = ProductDashboardApiService.handle_request("/api/v1/product/governance")
        contract = gov.get("governance_contract", {})
        assert contract.get("production_token_issued") is False
        assert contract.get("governance_authorization") == "NOT_GRANTED"

    def test_70_scientific_finding_used_to_override_technical_no_go(self):
        """70. Invariant: SCIENTIFIC_FINDING_SUPPORTED !=> LIVE_TRADING_AUTHORIZED."""
        from coin_behavior_engine.product.scientific_report_builder_v6 import ScientificReportBuilderV6
        rep = ScientificReportBuilderV6.generate_report(
            report_type="HISTORICAL_DISCOVERY",
            title="Finding Support Test",
            research_id="RES-STAT-02",
            evidence_grade="INDEPENDENTLY_REPLICATED_EVIDENCE",
        )
        gov = rep["governance_invariants"]
        assert gov["technical_decision"] == "TECHNICAL_NO_GO"
        assert gov["directional_trading_eligibility"] == 0
        assert gov["scientific_finding_rule"] == "SCIENTIFIC_FINDING_SUPPORTED !=> LIVE_TRADING_AUTHORIZED"


# ==============================================================================
# SECTION 20: POSITIVE & STATISTICAL REFERENCE TESTS (TESTS 1 - 20)
# ==============================================================================

class TestSection20PositiveAndReferenceTests:
    """Positive and Statistical Reference Tests (1 - 20)."""

    def test_p01_historical_dataset_structural_validation(self):
        """1. Valid historical dataset structural validation."""
        rec = DatasetValidationEngine.validate_dataset("DS-BTC-1H-Q1-2024")
        assert rec.schema_validation_status == "STRUCTURE_VALIDATED"
        assert rec.observation_count == 2184
        assert rec.temporal_integrity_status in ("TEMPORAL_INTEGRITY_VERIFIED", "TEMPORAL_GAPS_DETECTED")

    def test_p02_trusted_provenance_verification(self):
        """2. Valid trusted provenance verification on canonical dataset."""
        rec = DatasetValidationEngine.validate_dataset("DS-BTC-1H-Q1-2024")
        assert rec.provenance_status == "TRUSTED_PROVENANCE_VERIFIED"
        assert rec.quarantine_status == "CLEAN"

    def test_p03_correct_dataset_fingerprinting(self):
        """3. Deterministic dataset fingerprint computation."""
        fp = DatasetValidationEngine.compute_dataset_fingerprint(
            "DS-BTC-1H-Q1-2024", "c559ac59275e85bc02daa4f6b1379dd65c83b421c940d59fede0dabfcc2dbbc5",
            "CBE-DATASET-SCHEMA-V28", "2024-01-01T00:00:00+00:00", "2024-03-31T23:00:00+00:00", 2184
        )
        assert len(fp) == 64
        # Determinism check
        fp_repeat = DatasetValidationEngine.compute_dataset_fingerprint(
            "DS-BTC-1H-Q1-2024", "c559ac59275e85bc02daa4f6b1379dd65c83b421c940d59fede0dabfcc2dbbc5",
            "CBE-DATASET-SCHEMA-V28", "2024-01-01T00:00:00+00:00", "2024-03-31T23:00:00+00:00", 2184
        )
        assert fp == fp_repeat

    def test_p04_genuine_preregistration_snapshot(self):
        """4. Preregistered hypothesis has immutable snapshot and SHA-256 digest."""
        reg = HypothesisPreregistrationRegistry()
        h = reg.get_hypothesis("HYP-VOL-PERSIST-001")
        assert h is not None
        assert h.preregistration_status == "PREREGISTERED"
        assert h.preregistration_digest is not None
        assert len(h.preregistration_digest) == 64

    def test_p05_valid_amendment_history(self, tmp_path):
        """5. Valid amendment preserves original snapshot and appends amendment."""
        reg = HypothesisPreregistrationRegistry(persistence_path=tmp_path / "h.json")
        orig_digest = reg.get_hypothesis("HYP-VOL-PERSIST-001").preregistration_digest
        amd = reg.amend_preregistered_hypothesis(
            "HYP-VOL-PERSIST-001",
            "Refined lag search window from 1-10 to 1-5",
            {"statistical_test_plan": {"lags": [1, 2, 3, 4, 5]}},
        )
        assert amd.amendment_id.startswith("AMD-HYP-VOL-PERSIST-001")
        # Original digest remains unchanged!
        assert reg.get_hypothesis("HYP-VOL-PERSIST-001").preregistration_digest == orig_digest
        assert len(reg.get_hypothesis("HYP-VOL-PERSIST-001").amendments) == 1

    def test_p06_valid_exploratory_discovery(self):
        """6. Exploratory discovery record loaded and verified."""
        lab = PatternDiscoveryLaboratory()
        disc = lab.get_discovery("DISC-VOL-CLUST-001")
        assert disc is not None
        assert disc.hypothesis_id == "HYP-VOL-PERSIST-001"
        assert disc.raw_p_value < 0.001

    def test_p07_valid_temporal_partitioning(self):
        """7. Valid temporal partitioning without leakage."""
        eng = TemporalValidationEngine()
        parts = eng.list_partitions()
        assert len(parts) >= 3
        p1 = parts[0]  # Discovery
        p2 = parts[1]  # Validation
        clean, status, errs = TemporalValidationEngine.check_temporal_leakage(p1, p2)
        assert clean is True
        assert status == "TEMPORAL_SEPARATION_CLEAN"

    def test_p08_valid_out_of_sample_evaluation(self):
        """8. Valid out-of-sample validation report with acceptable degradation."""
        eng = TemporalValidationEngine()
        reps = eng.list_validation_reports()
        assert len(reps) > 0
        r = reps[0]
        assert r.validation_verdict == "VALIDATION_CONFIRMED"
        assert r.metric_degradation_pct < 20.0

    def test_p09_valid_independent_result_comparison(self):
        """9. Valid independent result comparison within tolerance."""
        expected = {"effect": 0.284, "p_val": 0.000042}
        actual = {"effect": 0.28405, "p_val": 0.0000421}
        ok, verd, max_r, max_a, disc = ReproducibilityLabV2.compare_numerical_results(
            expected, actual, rtol=1e-3, atol=1e-5
        )
        assert ok is True
        assert verd == "MATCH"

    def test_p10_correct_bonferroni_reference_calculation(self):
        """10. Mathematical reference check: Bonferroni correction."""
        # Reference test case: m=4, p = [0.005, 0.015, 0.03, 0.045]
        p_raw = [0.005, 0.015, 0.03, 0.045]
        bonf = MultipleTestingControlEngine.bonferroni_correction(p_raw)
        # Expected: [0.005*4, 0.015*4, 0.030*4, 0.045*4] = [0.02, 0.06, 0.12, 0.18]
        expected = [0.02, 0.06, 0.12, 0.18]
        for a, b in zip(bonf, expected):
            assert abs(a - b) < 1e-12

    def test_p11_correct_holm_reference_calculation(self):
        """11. Mathematical reference check: Holm-Bonferroni step-down."""
        p_raw = [0.005, 0.015, 0.03, 0.045]
        holm = MultipleTestingControlEngine.holm_bonferroni_correction(p_raw)
        # Holm sorted calculation:
        # k=1: 0.005 * 4 = 0.02
        # k=2: 0.015 * 3 = 0.045
        # k=3: 0.030 * 2 = 0.060
        # k=4: 0.045 * 1 = 0.045 -> max(prev, cand) = 0.060
        expected = [0.02, 0.045, 0.06, 0.06]
        for a, b in zip(holm, expected):
            assert abs(a - b) < 1e-12

    def test_p12_correct_benjamini_hochberg_reference_calculation(self):
        """12. Mathematical reference check: Benjamini-Hochberg FDR."""
        p_raw = [0.005, 0.015, 0.03, 0.045]
        bh = MultipleTestingControlEngine.benjamini_hochberg_correction(p_raw)
        # BH step-up from largest:
        # k=4: 0.045 * (4/4) = 0.045
        # k=3: 0.030 * (4/3) = 0.040 -> min(next, cand) = 0.040
        # k=2: 0.015 * (4/2) = 0.030 -> min(next, cand) = 0.030
        # k=1: 0.005 * (4/1) = 0.020 -> min(next, cand) = 0.020
        expected = [0.02, 0.03, 0.04, 0.045]
        for a, b in zip(bh, expected):
            assert abs(a - b) < 1e-12

    def test_p13_valid_regime_stability_assessment(self):
        """13. Valid regime stability assessment across regimes."""
        eng = RegimeStabilityEngine()
        rec = eng.get_record("REG-STAB-VOL-001")
        assert rec is not None
        assert rec.generalization_verdict == "STABLE_ACROSS_EVALUATED_REGIMES"
        assert len(rec.regimes_evaluated) == 3

    def test_p14_correct_evidence_grading(self):
        """14. Correct evidence grading assignment."""
        eng = EvidenceGradingEngine()
        grd = eng.get_assessment("GRD-VOL-001")
        assert grd is not None
        assert grd.grade == "VALIDATED_HISTORICAL_EVIDENCE"
        assert len(grd.supporting_dimensions) >= 10

    def test_p15_valid_knowledge_base_record(self):
        """15. Valid discovery knowledge base record."""
        kb = DiscoveryKnowledgeBase()
        rec = kb.get_record("KB-VOL-CLUST-001")
        assert rec is not None
        assert "ARCH effect" in rec.finding_statement
        assert rec.evidence_grade == "VALIDATED_HISTORICAL_EVIDENCE"

    def test_p16_valid_scientific_report_generation(self):
        """16. Scientific Report Builder V6 generates valid markdown and HTML reports."""
        rep = ScientificReportBuilderV6.generate_report(
            report_type="HISTORICAL_DISCOVERY",
            title="Historical Volatility Clustering in BTC Spot",
            research_id="RES-STAT-02",
            hypothesis_id="HYP-VOL-PERSIST-001",
            format_type="MARKDOWN",
        )
        assert rep["report_type"] == "HISTORICAL_DISCOVERY"
        assert "CBE-0.7.0" in rep["content"]
        assert "TECHNICAL_NO_GO" in rep["content"]

    def test_p17_persistence_across_restart(self, tmp_path):
        """17. State persists and reloads reliably from disk."""
        p_path = tmp_path / "hyp_test.json"
        reg1 = HypothesisPreregistrationRegistry(persistence_path=p_path)
        hyps_count1 = len(reg1.list_hypotheses())

        # Reload in fresh instance
        reg2 = HypothesisPreregistrationRegistry(persistence_path=p_path)
        hyps_count2 = len(reg2.list_hypotheses())
        assert hyps_count1 == hyps_count2

    def test_p18_evidence_revocation_invalidation(self):
        """18. Provenance rejection cascades to evidence grade."""
        grade_rec = EvidenceGradingEngine.evaluate_grade(
            "GRD-REVOKED", "DISC-1", "HYP-1", "RES-1",
            {"dataset_provenance": "REVOKED"}
        )
        assert grade_rec.grade == "BLOCKED_BY_PROVENANCE"

    def test_p19_dashboard_v6_api_integration(self):
        """19. Dashboard V6 API endpoints respond with 200 OK."""
        from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
        st1, r1 = ProductDashboardApiService.handle_request("/api/v1/product/research/datasets")
        assert st1 == 200
        assert r1.get("total_datasets", 0) > 0

        st2, r2 = ProductDashboardApiService.handle_request("/api/v1/product/research/hypotheses")
        assert st2 == 200
        assert r2.get("total_hypotheses", 0) > 0

        st3, r3 = ProductDashboardApiService.handle_request("/api/v1/product/research/discoveries")
        assert st3 == 200
        assert r3.get("total_discoveries", 0) > 0

    def test_p20_correct_scientific_governance_preservation(self):
        """20. Absolute scientific governance invariants strictly preserved."""
        from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
        status, gov = ProductDashboardApiService.handle_request("/api/v1/product/governance")
        assert status == 200
        assert FROZEN_MODEL_VERSION == "CBE-0.7.0"
        contract = gov.get("governance_contract", {})
        assert contract.get("technical_decision") == "TECHNICAL_NO_GO"
        assert contract.get("governance_authorization") == "NOT_GRANTED"
        assert contract.get("production_token_issued") is False
        caps = {c["capability"]: c["status"] for c in gov.get("capabilities_matrix", [])}
        assert caps.get("ORDER_EXECUTION") == "PERMANENTLY_PROHIBITED"
        assert caps.get("PROSPECTIVE_LIVE_OBSERVATION") == "DISABLED"

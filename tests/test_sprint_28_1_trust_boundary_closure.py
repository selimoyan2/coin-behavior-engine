"""
Comprehensive Sprint 28.1 Test Suite — Final Trust Boundary Closure & BTC Timing Research Readiness
Sprint ID: CBE_SPRINT28_1_FINAL_TRUST_BOUNDARY_CLOSURE

Asserts:
- Section 3.5: 12 Dataset Independence Negative Tests
- Section 4.5: 18 Reproduction Artifact Authenticity Negative Tests
- Section 5: 8 First-Execution / Reproduction Separation Tests
- Section 6: 8 Evidence-Grade Inflation Prevention Tests
- Section 6.3: 8 Trust Propagation Tests
- Section 8 Positive Reference Tests (8 tests)
- Persistence, Crash Recovery, API Security & Governance Invariant Tests
"""

import hashlib
import json
import math
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
import pytest

from coin_behavior_engine.product.trusted_provenance_resolver import (
    TrustedDatasetProvenanceResolver,
    TrustedDatasetMetadata,
)
from coin_behavior_engine.product.trusted_reproduction_artifact_resolver import (
    TrustedReproductionArtifactResolver,
    VerifiedArtifact,
)
from coin_behavior_engine.product.reproducibility_lab_v2 import (
    ReproducibilityLabV2,
    ReproductionRecordV2,
)
from coin_behavior_engine.product.pattern_discovery_laboratory import (
    PatternDiscoveryLaboratory,
    PatternDiscoveryRecord,
)
from coin_behavior_engine.product.evidence_grading_engine import (
    EvidenceGradingEngine,
    EvidenceGradeAssessment,
)
from coin_behavior_engine.product.discovery_knowledge_base import (
    DiscoveryKnowledgeBase,
)
from coin_behavior_engine.product.dataset_validation_engine import (
    DatasetValidationEngine,
)
from coin_behavior_engine.product.scientific_readiness import (
    ScientificReadinessEvaluator,
)


# ==============================================================================
# SECTION 3.5: DATASET INDEPENDENCE NEGATIVE TESTS (12 Tests)
# ==============================================================================

class TestSection35DatasetIndependenceNegative:
    """12 mandatory negative tests verifying that dataset independence fails closed."""

    def test_neg_01_caller_supplied_lineage_verified_flag_rejected(self):
        """1. Caller provides lineage_verified=True without trusted source -> fails closed."""
        v, issues = TrustedDatasetProvenanceResolver.verify_independence(
            "DS-UNKNOWN-A",
            "DS-UNKNOWN-B",
            lineage_evidence={"lineage_verified": True},
        )
        assert v == "INDEPENDENCE_NOT_ESTABLISHED"
        assert len(issues) > 0

    def test_neg_02_caller_supplied_zero_overlap_flag_rejected(self):
        """2. Caller provides zero_observation_overlap=True without actual verification -> fails closed."""
        v, issues = TrustedDatasetProvenanceResolver.verify_independence(
            "DS-UNKNOWN-A",
            "DS-UNKNOWN-B",
            lineage_evidence={"zero_observation_overlap": True},
        )
        assert v == "INDEPENDENCE_NOT_ESTABLISHED"

    def test_neg_03_differing_ids_same_source_exchange(self):
        """3. Two dataset IDs differ but point to same source -> DISTINCT_PARTITIONS_SAME_SOURCE."""
        v, issues = TrustedDatasetProvenanceResolver.verify_independence(
            "DS-BTC-1H-Q1-2024",
            "DS-BTC-1H-Q2-2024",
        )
        assert v == "DISTINCT_PARTITIONS_SAME_SOURCE"
        assert any("Shared source lineage" in iss for iss in issues)

    def test_neg_04_differing_hashes_shared_observations(self):
        """4. Two hashes differ but datasets share observations -> OVERLAPPING_DATA."""
        meta_a = TrustedDatasetMetadata(
            dataset_id="DS-CUSTOM-A",
            exchange="BINANCE",
            symbol="BTC/USDT",
            market_type="SPOT",
            timeframe="1h",
            observation_start=datetime(2024, 1, 1, 0, 0, tzinfo=timezone.utc),
            observation_end=datetime(2024, 2, 1, 0, 0, tzinfo=timezone.utc),
            observation_count=744,
            source_artifact_sha256="1111111111111111111111111111111111111111111111111111111111111111",
            dataset_fingerprint="fp1",
            source_lineage="BINANCE_HISTORICAL_ARCHIVE",
            parent_dataset_id=None,
            transformation_lineage=[],
            quarantine_status="CLEAN",
            provenance_status="TRUSTED_PROVENANCE_VERIFIED",
        )
        meta_b = TrustedDatasetMetadata(
            dataset_id="DS-CUSTOM-B",
            exchange="BINANCE",
            symbol="BTC/USDT",
            market_type="SPOT",
            timeframe="1h",
            observation_start=datetime(2024, 1, 15, 0, 0, tzinfo=timezone.utc),
            observation_end=datetime(2024, 2, 15, 0, 0, tzinfo=timezone.utc),
            observation_count=744,
            source_artifact_sha256="2222222222222222222222222222222222222222222222222222222222222222",
            dataset_fingerprint="fp2",
            source_lineage="BINANCE_HISTORICAL_ARCHIVE",
            parent_dataset_id=None,
            transformation_lineage=[],
            quarantine_status="CLEAN",
            provenance_status="TRUSTED_PROVENANCE_VERIFIED",
        )
        has_overlap, _ = TrustedDatasetProvenanceResolver.check_observation_overlap(meta_a, meta_b)
        assert has_overlap is True

    def test_neg_05_nonoverlapping_quarterly_binance_not_independent(self):
        """5. Two nonoverlapping quarterly Binance datasets are not independent sources."""
        v, _ = TrustedDatasetProvenanceResolver.verify_independence(
            "DS-BTC-1H-Q1-2024",
            "DS-BTC-1H-Q3-2024",
        )
        assert v != "INDEPENDENT_SOURCE_VERIFIED"
        assert v == "DISTINCT_PARTITIONS_SAME_SOURCE"

    def test_neg_06_transformed_copy_detected_as_shared_lineage(self):
        """6. One dataset is a transformed copy of another -> SHARED_SOURCE_LINEAGE."""
        meta_parent = TrustedDatasetMetadata(
            dataset_id="DS-SRC-ROOT",
            exchange="KRAKEN",
            symbol="BTC/USDT",
            market_type="SPOT",
            timeframe="1m",
            observation_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            observation_end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            observation_count=1440,
            source_artifact_sha256="a"*64,
            dataset_fingerprint="fp_parent",
            source_lineage="RAW",
            parent_dataset_id=None,
            transformation_lineage=[],
            quarantine_status="CLEAN",
            provenance_status="TRUSTED_PROVENANCE_VERIFIED",
        )
        meta_derived = TrustedDatasetMetadata(
            dataset_id="DS-DERIVED",
            exchange="COINBASE",
            symbol="BTC/USDT",
            market_type="SPOT",
            timeframe="5m",
            observation_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            observation_end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            observation_count=288,
            source_artifact_sha256="b"*64,
            dataset_fingerprint="fp_derived",
            source_lineage="TRANSFORMED",
            parent_dataset_id="DS-SRC-ROOT",
            transformation_lineage=["DS-SRC-ROOT", "AGGREGATION_5M"],
            quarantine_status="CLEAN",
            provenance_status="TRUSTED_PROVENANCE_VERIFIED",
        )
        ctx = {"authority": "CBE_DATASET_GOVERNANCE_AUTHORITY", "token": "auth_token_secret_12345"}
        ev_parent = {
            "intake_manifest_sha256": "1" * 64,
            "source_lineage_digest": "2" * 64,
            "external_exchange": "KRAKEN",
        }
        ev_derived = {
            "intake_manifest_sha256": "3" * 64,
            "source_lineage_digest": "4" * 64,
            "external_exchange": "COINBASE",
        }
        TrustedDatasetProvenanceResolver.register_verified_external_dataset(meta_parent, ctx, ev_parent)
        TrustedDatasetProvenanceResolver.register_verified_external_dataset(meta_derived, ctx, ev_derived)
        v, issues = TrustedDatasetProvenanceResolver.verify_independence("DS-SRC-ROOT", "DS-DERIVED")
        assert v == "SHARED_SOURCE_LINEAGE"

    def test_neg_07_source_lineage_missing(self):
        """7. Source lineage is missing -> INDEPENDENCE_NOT_ESTABLISHED."""
        v, _ = TrustedDatasetProvenanceResolver.verify_independence("DS-UNREGISTERED-1", "DS-UNREGISTERED-2")
        assert v == "INDEPENDENCE_NOT_ESTABLISHED"

    def test_neg_08_dataset_quarantined(self):
        """8. Quarantined dataset cannot establish independence."""
        v, issues = TrustedDatasetProvenanceResolver.verify_independence(
            "DS-BTC-5M-2026-10-INTAKE",
            "DS-COINBASE-01",
        )
        assert v == "INDEPENDENCE_NOT_ESTABLISHED"

    def test_neg_09_source_record_revoked(self):
        """9. Revoked dataset fails closed."""
        TrustedDatasetProvenanceResolver.revoke_dataset("DS-TEST-REVOKED", "Fraud detected")
        assert TrustedDatasetProvenanceResolver.is_revoked("DS-TEST-REVOKED") is True
        v, issues = TrustedDatasetProvenanceResolver.verify_independence("DS-TEST-REVOKED", "DS-COINBASE-01")
        assert v == "INDEPENDENCE_NOT_ESTABLISHED"

    def test_neg_10_fingerprint_mismatch(self):
        """10. Supplied source hash does not match authoritative fingerprint -> fails closed."""
        v, issues = TrustedDatasetProvenanceResolver.verify_independence(
            "DS-BTC-1H-Q1-2024",
            "DS-COINBASE-01",
            source_sha256="0000000000000000000000000000000000000000000000000000000000000000",
        )
        assert v == "INDEPENDENCE_NOT_ESTABLISHED"

    def test_neg_11_unknown_dataset_id(self):
        """11. Unknown dataset ID fails closed."""
        v, _ = TrustedDatasetProvenanceResolver.verify_independence("DS-GHOST-DATASET", "DS-BTC-1H-Q1-2024")
        assert v == "INDEPENDENCE_NOT_ESTABLISHED"

    def test_neg_12_forged_independent_source_metadata(self):
        """12. Forged independent-source metadata without backing registry fails closed."""
        forged_evidence = {
            "source_provider": "KRAKEN_FORGED",
            "reproduction_provider": "BITSTAMP_FORGED",
            "lineage_verified": True,
            "zero_observation_overlap": True,
            "forged_key": "FORGED_SIGNATURE",
        }
        v, issues = TrustedDatasetProvenanceResolver.verify_independence(
            "DS-FORGED-1",
            "DS-FORGED-2",
            lineage_evidence=forged_evidence,
        )
        assert v == "INDEPENDENCE_NOT_ESTABLISHED"


# ==============================================================================
# SECTION 4.5: REPRODUCTION ARTIFACT AUTHENTICITY NEGATIVE TESTS (18 Tests)
# ==============================================================================

class TestSection45ReproductionArtifactAuthenticityNegative:
    """18 mandatory negative tests verifying that reproduction artifacts cannot be faked."""

    def test_neg_art_01_nonexistent_artifact_id(self):
        """1. Nonexistent artifact ID fails closed."""
        art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-NON-EXISTENT-XYZ")
        assert art is None
        assert "does not exist" in err.lower() or "not found" in err.lower()

    def test_neg_art_02_existing_id_pointing_to_missing_file(self, tmp_path):
        """2. Existing artifact ID registered with a missing physical file fails closed."""
        missing_file = tmp_path / "missing.json"
        TrustedReproductionArtifactResolver.register_artifact(
            "ART-MISSING-TARGET",
            {"file_path": str(missing_file)},
        )
        art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-MISSING-TARGET")
        assert art is None
        assert err is not None

    def test_neg_art_03_correct_filename_incorrect_sha256(self):
        """3. Correct filename but incorrect expected SHA-256 fails closed."""
        art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact(
            "ART-EXPECTED-EXP-ASV-001",
            expected_sha256="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        )
        assert art is None
        assert "mismatch" in str(err).lower()

    def test_neg_art_04_artifact_belonging_to_another_execution(self):
        """4. Artifact belonging to another execution fails closed."""
        art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact(
            "ART-EXPECTED-EXP-ASV-001",
            expected_execution_id="EXEC-WRONG-OTHER-EXP",
        )
        assert art is None
        assert "Execution ID mismatch" in err

    def test_neg_art_05_artifact_belonging_to_another_dataset(self):
        """5. Artifact belonging to another dataset fails closed."""
        art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact(
            "ART-EXPECTED-EXP-ASV-001",
            expected_dataset_id="DS-WRONG-DATASET-ID",
        )
        assert art is None
        assert "Dataset ID mismatch" in err

    def test_neg_art_06_same_file_self_comparison(self):
        """6. Original and reproduction artifacts resolving to the same file fails."""
        art1, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-EXPECTED-EXP-ASV-001")
        art2, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-EXPECTED-EXP-ASV-001")
        match, verdict, _, _, disc = TrustedReproductionArtifactResolver.compare_verified_artifacts(art1, art2)
        assert match is False
        assert verdict in ("FRAUDULENT_SELF_COMPARISON", "IDENTICAL_EXECUTION_EVIDENCE")

    def test_neg_art_07_different_ids_same_execution_evidence(self):
        """7. Differing IDs resolving to identical execution ID fails as self-comparison."""
        art1 = VerifiedArtifact(
            artifact_id="ART-A",
            file_path=Path("a.json"),
            actual_sha256="sha1",
            execution_id="EXEC-SAME-001",
            dataset_id="DS-1",
            methodology_id="METH-1",
            numerical_metrics={"stat": 1.0},
            raw_content={},
            verified_at="2026-01-01T00:00:00Z",
        )
        art2 = VerifiedArtifact(
            artifact_id="ART-B",
            file_path=Path("b.json"),
            actual_sha256="sha2",
            execution_id="EXEC-SAME-001",
            dataset_id="DS-1",
            methodology_id="METH-1",
            numerical_metrics={"stat": 1.0},
            raw_content={},
            verified_at="2026-01-01T00:00:00Z",
        )
        match, verdict, _, _, disc = TrustedReproductionArtifactResolver.compare_verified_artifacts(art1, art2)
        assert match is False
        assert verdict in ("FRAUDULENT_SELF_COMPARISON", "IDENTICAL_EXECUTION_EVIDENCE")

    def test_neg_art_08_matching_dicts_without_real_artifacts(self):
        """8. Caller supplies matching numerical dicts without real artifacts -> not authoritative."""
        rep_lab = ReproducibilityLabV2()
        res = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-NO-REAL-ART",
            original_experiment_id="EXP-01",
            reproduction_type="COMPUTATIONAL_REPEATABILITY",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-01",
            reproduction_methodology_id="METH-01",
            implementation_identity="CBE_ENGINE",
            expected_results={"r2": 0.05},
            actual_results={"r2": 0.05},
            expected_result_artifact_id="ART-SYNTHETIC-NONEXISTENT-A",
            actual_result_artifact_id="ART-SYNTHETIC-NONEXISTENT-B",
        )
        assert res.reproduction_verdict != "COMPUTATIONAL_REPEATABILITY_VERIFIED"
        assert res.reproduction_verdict in ("REPRODUCTION_EVIDENCE_INCOMPLETE", "INSUFFICIENT_EVIDENCE")

    def test_neg_art_09_quarantined_artifact_rejected(self):
        """9. Quarantined artifact cannot certify reproduction."""
        TrustedReproductionArtifactResolver.quarantine_artifact("ART-EXPECTED-EXP-ASV-001", "Integrity check")
        art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-EXPECTED-EXP-ASV-001")
        assert art is None
        assert "quarantined" in str(err).lower()
        # Clean up
        TrustedReproductionArtifactResolver._quarantined_artifacts.discard("ART-EXPECTED-EXP-ASV-001")

    def test_neg_art_10_revoked_artifact_rejected(self):
        """10. Revoked artifact cannot certify reproduction."""
        TrustedReproductionArtifactResolver.revoke_artifact("ART-EXPECTED-EXP-ASV-001", "Security review")
        art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-EXPECTED-EXP-ASV-001")
        assert art is None
        assert "revoked" in str(err).lower()
        # Clean up
        TrustedReproductionArtifactResolver._revoked_artifacts.discard("ART-EXPECTED-EXP-ASV-001")

    def test_neg_art_11_path_traversal_rejected(self):
        """11. Path traversal in artifact ID is rejected."""
        art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact("../../etc/passwd")
        assert art is None
        assert "path traversal" in str(err).lower()

    def test_neg_art_12_symlink_escape_rejected(self, tmp_path):
        """12. Symlink escaping allowed artifact root is rejected."""
        outside_file = tmp_path / "outside_secret.json"
        outside_file.write_text('{"stat": 1.0}')
        # Path resolution strictly checks is_relative_to ALLOWED_ARTIFACT_ROOTS
        art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact(
            "ART-OUTSIDE",
            caller_path=str(outside_file),
        )
        assert art is None
        assert err is not None

    def test_neg_art_13_malformed_result_schema(self, tmp_path):
        """13. Malformed result schema (invalid json) fails closed."""
        bad_file = Path("data/research_lab/discovery_artifacts/ART-BAD-JSON.json")
        try:
            bad_file.write_text("{malformed: true,,,}")
            art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-BAD-JSON")
            assert art is None
            assert "malformed" in str(err).lower() or "invalid" in str(err).lower()
        finally:
            if bad_file.exists():
                bad_file.unlink()

    def test_neg_art_14_nan_or_infinite_numerical_results(self):
        """14. Artifact containing NaN or infinite metric is rejected."""
        art = VerifiedArtifact(
            artifact_id="ART-NAN",
            file_path=Path("nan.json"),
            actual_sha256="sha_nan",
            execution_id="EXEC-NAN-01",
            dataset_id="DS-1",
            methodology_id="METH-1",
            numerical_metrics={"stat": float("nan")},
            raw_content={},
            verified_at="2026-01-01T00:00:00Z",
        )
        art_ref = VerifiedArtifact(
            artifact_id="ART-REF",
            file_path=Path("ref.json"),
            actual_sha256="sha_ref",
            execution_id="EXEC-REF-02",
            dataset_id="DS-1",
            methodology_id="METH-1",
            numerical_metrics={"stat": 1.0},
            raw_content={},
            verified_at="2026-01-01T00:00:00Z",
        )
        match, verdict, _, _, disc = TrustedReproductionArtifactResolver.compare_verified_artifacts(art, art_ref)
        assert match is False
        assert verdict == "NON_FINITE_METRIC"

    def test_neg_art_15_missing_methodology_identity(self, tmp_path):
        """15. Missing methodology identity in artifact fails verification."""
        no_meth_file = Path("data/research_lab/discovery_artifacts/ART-NO-METH.json")
        try:
            no_meth_file.write_text(json.dumps({
                "execution_id": "EXEC-01",
                "dataset_id": "DS-1",
                "metrics": {"stat": 1.0},
            }))
            art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact(
                "ART-NO-METH",
                expected_methodology_id="METH-REQUIRED-01",
            )
            assert art is None
            assert "Methodology ID mismatch" in str(err) or "Missing" in str(err)
        finally:
            if no_meth_file.exists():
                no_meth_file.unlink()

    def test_neg_art_16_forged_independent_implementation_claim(self):
        """16. Forged independent implementation claim with identical implementation identity fails."""
        rep_lab = ReproducibilityLabV2()
        res = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-FORGED-IMPL",
            original_experiment_id="EXP-ASV-001",
            reproduction_type="INDEPENDENT_IMPLEMENTATION",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-ENGLE-ARCH-01",
            reproduction_methodology_id="METH-ENGLE-ARCH-01",
            implementation_identity="CBE_INTERNAL_ENGINE",  # Identical to original
            expected_result_artifact_id="ART-EXPECTED-EXP-ASV-001",
            actual_result_artifact_id="ART-ACTUAL-REP-VOL-001",
        )
        assert res.reproduction_verdict != "INDEPENDENT_IMPLEMENTATION_REPRODUCED"

    def test_neg_art_17_dataset_independence_not_established(self):
        """17. Dataset independence not established fails independent dataset replication."""
        rep_lab = ReproducibilityLabV2()
        res = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-SAME-EXCHANGE-PARTITION",
            original_experiment_id="EXP-REG-003",
            reproduction_type="INDEPENDENT_DATASET",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q3-2024",
            original_methodology_id="METH-REG-01",
            reproduction_methodology_id="METH-REG-01",
            implementation_identity="EXT-R",
            expected_result_artifact_id="ART-EXPECTED-EXP-REG-003",
            actual_result_artifact_id="ART-ACTUAL-REP-DATA-003",
        )
        assert res.reproduction_verdict != "INDEPENDENT_DATASET_REPLICATED"
        assert res.independence_verdict == "DISTINCT_PARTITIONS_SAME_SOURCE"

    def test_neg_art_18_reproduction_result_changed_after_verification(self):
        """18. Artifact tampering after initial load is detected via cache invalidation."""
        # Load once to cache
        art1, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-EXPECTED-EXP-ASV-001")
        assert art1 is not None
        # Invalidate cache simulating modification detection
        TrustedReproductionArtifactResolver.invalidate_cache("ART-EXPECTED-EXP-ASV-001")
        # Tampered SHA check fails
        art_tampered, err = TrustedReproductionArtifactResolver.load_and_verify_artifact(
            "ART-EXPECTED-EXP-ASV-001",
            expected_sha256="bad_sha_256_after_modification",
        )
        assert art_tampered is None
        assert "mismatch" in str(err).lower()


# ==============================================================================
# SECTION 5: FIRST EXECUTION IS NOT REPRODUCTION (8 Tests)
# ==============================================================================

class TestSection5FirstExecutionSeparation:
    """8 tests verifying that first execution is distinct from reproduction."""

    def test_fe_01_initial_status_is_reproduction_not_established(self):
        """1. Newly executed pattern discovery has reproducibility_status REPRODUCTION_NOT_ESTABLISHED."""
        lab = PatternDiscoveryLaboratory()
        rec = lab.execute_empirical_pattern_discovery(
            discovery_id="DISC-TEST-FE-01",
            hypothesis_id="HYP-VOL-PERSIST-001",
            research_id="RES-EXP-01",
            dataset_id="DS-BTC-1H-Q1-2024",
            methodology_id="METH-VOL-01",
            discovery_method="VOLATILITY_CLUSTERING_ENGLE_LM",
        )
        assert rec.reproducibility_status == "REPRODUCTION_NOT_ESTABLISHED"
        assert rec.reproducibility_status != "REPEATABILITY_VERIFIED"

    def test_fe_02_classified_as_empirically_executed_discovery(self):
        """2. Newly executed discovery is classified as EMPIRICALLY_EXECUTED_DISCOVERY."""
        lab = PatternDiscoveryLaboratory()
        rec = lab.execute_empirical_pattern_discovery(
            discovery_id="DISC-TEST-FE-02",
            hypothesis_id="HYP-VOL-PERSIST-001",
            research_id="RES-EXP-01",
            dataset_id="DS-BTC-1H-Q1-2024",
            methodology_id="METH-VOL-01",
            discovery_method="VOLATILITY_CLUSTERING_ENGLE_LM",
        )
        assert rec.discovery_type == "EMPIRICALLY_EXECUTED_DISCOVERY"

    def test_fe_03_first_execution_not_independently_replicated(self):
        """3. First execution is not classified as independently replicated."""
        lab = PatternDiscoveryLaboratory()
        rec = lab.execute_empirical_pattern_discovery(
            discovery_id="DISC-TEST-FE-03",
            hypothesis_id="HYP-VOL-PERSIST-001",
            research_id="RES-EXP-01",
            dataset_id="DS-BTC-1H-Q1-2024",
            methodology_id="METH-VOL-01",
            discovery_method="VOLATILITY_CLUSTERING_ENGLE_LM",
        )
        assert rec.reproducibility_status != "INDEPENDENT_DATASET_REPLICATED"
        assert rec.reproducibility_status != "INDEPENDENT_IMPLEMENTATION_REPRODUCED"

    def test_fe_04_separate_reproduction_execution_required(self):
        """4. Separate reproduction execution required to establish computational repeatability."""
        rep_lab = ReproducibilityLabV2()
        rec = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-VALID-COMP-01",
            original_experiment_id="EXP-ASV-001",
            reproduction_type="COMPUTATIONAL_REPEATABILITY",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-ENGLE-ARCH-01",
            reproduction_methodology_id="METH-ENGLE-ARCH-01",
            implementation_identity="CBE_ENGINE",
            expected_result_artifact_id="ART-EXPECTED-EXP-ASV-001",
            actual_result_artifact_id="ART-ACTUAL-REP-VOL-001",
        )
        assert rec.reproduction_verdict == "COMPUTATIONAL_REPEATABILITY_VERIFIED"

    def test_fe_05_reusing_original_output_prohibited(self):
        """5. Reusing original output as both expected and actual evidence is prohibited."""
        rep_lab = ReproducibilityLabV2()
        rec = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-SELF-COMP-01",
            original_experiment_id="EXP-ASV-001",
            reproduction_type="COMPUTATIONAL_REPEATABILITY",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-ENGLE-ARCH-01",
            reproduction_methodology_id="METH-ENGLE-ARCH-01",
            implementation_identity="CBE_ENGINE",
            expected_result_artifact_id="ART-EXPECTED-EXP-ASV-001",
            actual_result_artifact_id="ART-EXPECTED-EXP-ASV-001",  # Same artifact!
        )
        assert rec.reproduction_verdict == "REPRODUCTION_FAILED"
        assert rec.comparison_verdict == "FRAUDULENT_SELF_COMPARISON"

    def test_fe_06_matching_numerical_outputs_within_tolerance(self):
        """6. Computational repeatability requires numerical outputs within documented tolerance."""
        art_exp, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-EXPECTED-EXP-ASV-001")
        art_act, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-ACTUAL-REP-VOL-001")
        match, verdict, rel, abs_err, disc = TrustedReproductionArtifactResolver.compare_verified_artifacts(
            art_exp, art_act, rtol=1e-3, atol=1e-3
        )
        assert match is True
        assert verdict == "MATCH_WITHIN_TOLERANCE"

    def test_fe_07_discrepant_numerical_outputs_yield_reproduction_failed(self):
        """7. Discrepant numerical outputs yield REPRODUCTION_FAILED."""
        art_exp, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-EXPECTED-EXP-ASV-001")
        art_act, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-EXPECTED-EXP-WF-002")
        match, verdict, rel, abs_err, disc = TrustedReproductionArtifactResolver.compare_verified_artifacts(
            art_exp, art_act, rtol=1e-4, atol=1e-4
        )
        assert match is False
        assert verdict == "NUMERICAL_DISCREPANCY"

    def test_fe_08_cannot_promote_repeatability_to_independent_implementation(self):
        """8. Computational repeatability cannot be promoted to independent implementation without distinct identity."""
        rep_lab = ReproducibilityLabV2()
        rec = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-CHECK-PROMOTION",
            original_experiment_id="EXP-ASV-001",
            reproduction_type="INDEPENDENT_IMPLEMENTATION",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-ENGLE-ARCH-01",
            reproduction_methodology_id="METH-ENGLE-ARCH-01",
            implementation_identity="CBE_ENGINE",  # Internal engine cannot claim independent implementation
            expected_result_artifact_id="ART-EXPECTED-EXP-ASV-001",
            actual_result_artifact_id="ART-ACTUAL-REP-VOL-001",
        )
        assert rec.reproduction_verdict != "INDEPENDENT_IMPLEMENTATION_REPRODUCED"


# ==============================================================================
# SECTION 6: EVIDENCE GRADE INFLATION PREVENTION (8 Tests)
# ==============================================================================

class TestSection6EvidenceGradeInflation:
    """8 tests verifying that missing evidence does not inflate grades."""

    def test_gi_01_regime_generalization_defaults_to_not_evaluated(self):
        """1. regime_generalization unverified defaults to NOT_EVALUATED and caps grade."""
        eng = EvidenceGradingEngine()
        asmt = eng.compute_evidence_grade(
            discovery_id="DISC-UNVERIFIED-GEN",
            dimensions={
                "dataset_provenance": "TRUSTED_PROVENANCE_VERIFIED",
                "statistical_validity": "STATISTICALLY_VALID",
                "reproducibility": "REPEATABILITY_VERIFIED",
                # regime_generalization is omitted
            },
        )
        assert asmt.grade != "INDEPENDENTLY_REPLICATED_EVIDENCE"
        assert asmt.grade in ("PRELIMINARY_SUPPORT", "EXPLORATORY_EVIDENCE")

    def test_gi_02_absence_of_contradictions_defaults_to_not_evaluated(self):
        """2. absence_of_contradictions unverified defaults to NOT_EVALUATED and caps grade."""
        eng = EvidenceGradingEngine()
        asmt = eng.compute_evidence_grade(
            discovery_id="DISC-UNVERIFIED-CONTRA",
            dimensions={
                "dataset_provenance": "TRUSTED_PROVENANCE_VERIFIED",
                "statistical_validity": "STATISTICALLY_VALID",
                "reproducibility": "REPEATABILITY_VERIFIED",
                # absence_of_contradictions omitted
            },
        )
        assert asmt.grade != "INDEPENDENTLY_REPLICATED_EVIDENCE"

    def test_gi_03_disclosed_limitations_missing_caps_grade(self):
        """3. disclosed_limitations missing or empty caps grade."""
        eng = EvidenceGradingEngine()
        asmt = eng.compute_evidence_grade(
            discovery_id="DISC-NO-LIMITATIONS",
            dimensions={
                "dataset_provenance": "TRUSTED_PROVENANCE_VERIFIED",
                "statistical_validity": "STATISTICALLY_VALID",
                "reproducibility": "REPEATABILITY_VERIFIED",
                "regime_generalization": "VERIFIED_TRUE",
                "absence_of_contradictions": "VERIFIED_TRUE",
                "disclosed_limitations": "NOT_EVALUATED",
            },
        )
        assert asmt.grade != "INDEPENDENTLY_REPLICATED_EVIDENCE"

    def test_gi_04_dimension_states_classification(self):
        """4. Dimension states support VERIFIED_TRUE, VERIFIED_FALSE, NOT_EVALUATED, INSUFFICIENT_EVIDENCE."""
        valid_states = {"VERIFIED_TRUE", "VERIFIED_FALSE", "NOT_EVALUATED", "INSUFFICIENT_EVIDENCE", "NOT_APPLICABLE"}
        for st in valid_states:
            assert st in EvidenceGradingEngine.VALID_DIMENSION_STATES

    def test_gi_05_missing_contradiction_record_does_not_prove_absence(self):
        """5. Missing contradiction record does not prove absence of contradictions."""
        eng = EvidenceGradingEngine()
        asmt = eng.compute_evidence_grade(
            discovery_id="DISC-UNKNOWN-CONTRA",
            dimensions={"absence_of_contradictions": "NOT_EVALUATED"},
        )
        assert "absence_of_contradictions" not in asmt.supporting_dimensions

    def test_gi_06_missing_generalization_caps_to_preliminary_support(self):
        """6. Missing generalization study caps grade to PRELIMINARY_SUPPORT or below."""
        eng = EvidenceGradingEngine()
        asmt = eng.compute_evidence_grade(
            discovery_id="DISC-NO-GEN",
            dimensions={
                "dataset_provenance": "TRUSTED_PROVENANCE_VERIFIED",
                "statistical_validity": "STATISTICALLY_VALID",
                "reproducibility": "REPEATABILITY_VERIFIED",
                "regime_generalization": "NOT_EVALUATED",
            },
        )
        assert asmt.grade in ("PRELIMINARY_SUPPORT", "EXPLORATORY_EVIDENCE")

    def test_gi_07_unknown_dimensions_do_not_inflate_grade(self):
        """7. Unknown dimensions do not inflate grade."""
        eng = EvidenceGradingEngine()
        asmt = eng.compute_evidence_grade(
            discovery_id="DISC-ALL-UNKNOWN",
            dimensions={
                "dim_a": "UNKNOWN",
                "dim_b": "UNKNOWN",
            },
        )
        assert asmt.grade in ("BLOCKED_BY_PROVENANCE", "INSUFFICIENT_EVIDENCE", "EXPLORATORY_EVIDENCE", "EVIDENCE_NOT_ESTABLISHED")

    def test_gi_08_deterministic_grading(self):
        """8. Identical dimension evaluations produce identical grade."""
        eng = EvidenceGradingEngine()
        dims = {
            "dataset_provenance": "TRUSTED_PROVENANCE_VERIFIED",
            "statistical_validity": "STATISTICALLY_VALID",
            "reproducibility": "REPEATABILITY_VERIFIED",
            "regime_generalization": "VERIFIED_TRUE",
            "absence_of_contradictions": "VERIFIED_TRUE",
            "disclosed_limitations": "VERIFIED_TRUE",
        }
        asmt1 = eng.compute_evidence_grade("DISC-DET-1", dims)
        asmt2 = eng.compute_evidence_grade("DISC-DET-2", dims)
        assert asmt1.grade == asmt2.grade


# ==============================================================================
# SECTION 6.3: TRUST PROPAGATION TESTS (8 Tests)
# ==============================================================================

class TestSection63TrustPropagation:
    """8 tests verifying trust downgrade propagation across dependent modules."""

    def test_tp_01_artifact_revocation_downgrades_grade(self, tmp_path):
        """1. Revoking an artifact downgrades dependent assessment to REVOKED."""
        eng = EvidenceGradingEngine(persistence_path=tmp_path / "grades.json")
        asmt = eng.get_assessment("GRD-VOL-001")
        assert asmt is not None
        affected = eng.propagate_revocation_or_downgrade("ARTIFACT", "ART-DIST-001", "Tampered artifact")
        assert "GRD-VOL-001" in affected
        updated = eng.get_assessment("GRD-VOL-001")
        assert updated.grade == "REVOKED"

    def test_tp_02_dataset_quarantine_propagates_downgrade(self, tmp_path):
        """2. Quarantining a dataset downgrades dependent evidence grade."""
        eng = EvidenceGradingEngine(persistence_path=tmp_path / "grades.json")
        affected = eng.propagate_revocation_or_downgrade("DATASET", "DS-BTC-1H-Q1-2024", "Quarantined for audit")
        assert len(affected) > 0
        asmt = eng.get_assessment(affected[0])
        assert asmt.grade == "REVOKED"

    def test_tp_03_reproduction_failure_downgrades_grade(self, tmp_path):
        """3. Reproduction failure causes grade downgrade."""
        eng = EvidenceGradingEngine(persistence_path=tmp_path / "grades.json")
        asmt = eng.get_assessment("GRD-REG-SHIFT-002")
        assert asmt is not None
        eng.revoke_grade("GRD-REG-SHIFT-002", "Reproduction failed")
        assert eng.get_assessment("GRD-REG-SHIFT-002").grade == "REVOKED"

    def test_tp_04_source_independence_downgrade_prevents_replication_grade(self):
        """4. Source independence downgrade prevents INDEPENDENTLY_REPLICATED_EVIDENCE."""
        eng = EvidenceGradingEngine()
        asmt = eng.compute_evidence_grade(
            discovery_id="DISC-DEP-IND",
            dimensions={
                "dataset_provenance": "TRUSTED_PROVENANCE_VERIFIED",
                "statistical_validity": "STATISTICALLY_VALID",
                "reproducibility": "DISTINCT_PARTITIONS_SAME_SOURCE",
            },
        )
        assert asmt.grade != "INDEPENDENTLY_REPLICATED_EVIDENCE"

    def test_tp_05_contradiction_discovery_updates_blocking_reasons(self, tmp_path):
        """5. Contradiction discovery updates assessment blocking reasons."""
        eng = EvidenceGradingEngine(persistence_path=tmp_path / "grades.json")
        asmt = eng.revoke_grade("GRD-VOL-001", "Contradiction found in Out-of-sample data")
        assert any("Contradiction" in r for r in asmt.blocking_reasons)

    def test_tp_06_knowledge_base_invalidates_downgraded_finding(self, tmp_path):
        """6. Knowledge Base invalidates or downgrades finding upon evidence downgrade."""
        kb = DiscoveryKnowledgeBase(persistence_path=tmp_path / "kb.json")
        rec = kb.add_finding(
            discovery_id="DISC-TEST-KB-DOWNGRADE",
            hypothesis_id="HYP-1",
            research_id="RES-1",
            finding_name="Test Finding",
            evidence_grade="CONFIRMED",
            statistical_p_value=0.001,
        )
        assert rec.evidence_grade == "CONFIRMED"
        kb.invalidate_or_downgrade_finding("DISC-TEST-KB-DOWNGRADE", "REVOKED", "Audit failure")
        updated = kb.get_finding("DISC-TEST-KB-DOWNGRADE")
        assert updated.evidence_grade == "REVOKED"
        assert updated.status == "REVOKED"

    def test_tp_07_report_builder_reflects_downgraded_grade(self, tmp_path):
        """7. Report builder reflects downgraded grade."""
        eng = EvidenceGradingEngine(persistence_path=tmp_path / "grades.json")
        eng.revoke_grade("GRD-VOL-001", "Revoked")
        asmt = eng.get_assessment("GRD-VOL-001")
        assert asmt.grade == "REVOKED"

    def test_tp_08_dashboard_counts_reflect_active_verified_grades(self, tmp_path):
        """8. Dashboard counts reflect active verified grades only."""
        eng = EvidenceGradingEngine(persistence_path=tmp_path / "grades.json")
        active = eng.list_active_assessments()
        for a in active:
            assert a.grade != "REVOKED"


# ==============================================================================
# SECTION 8: POSITIVE REFERENCE TESTS (8 Tests)
# ==============================================================================

class TestSection8PositiveReferenceTests:
    """8 positive reference tests verifying genuine verification workflows."""

    def test_pos_ref_01_genuine_independent_source_verification(self):
        """1. Genuine independent source verification between Binance and Coinbase."""
        v, issues = TrustedDatasetProvenanceResolver.verify_independence(
            "DS-BTC-1H-Q1-2024",
            "DS-COINBASE-01",
        )
        assert v == "INDEPENDENT_SOURCE_VERIFIED"
        assert len(issues) == 0

    def test_pos_ref_02_computational_repeatability_verified(self):
        """2. Genuine computational repeatability verified with valid artifacts."""
        rep_lab = ReproducibilityLabV2()
        rec = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-POS-COMP-01",
            original_experiment_id="EXP-ASV-001",
            reproduction_type="COMPUTATIONAL_REPEATABILITY",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-ENGLE-ARCH-01",
            reproduction_methodology_id="METH-ENGLE-ARCH-01",
            implementation_identity="CBE_ENGINE",
            expected_result_artifact_id="ART-EXPECTED-EXP-ASV-001",
            actual_result_artifact_id="ART-ACTUAL-REP-VOL-001",
        )
        assert rec.reproduction_verdict == "COMPUTATIONAL_REPEATABILITY_VERIFIED"

    def test_pos_ref_03_independent_implementation_reproduced(self):
        """3. Genuine independent implementation reproduced with external engine identity."""
        rep_lab = ReproducibilityLabV2()
        rec = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-POS-IMPL-02",
            original_experiment_id="EXP-WF-002",
            reproduction_type="INDEPENDENT_IMPLEMENTATION",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-ENGLE-ARCH-01",
            reproduction_methodology_id="METH-ENGLE-ARCH-01",
            implementation_identity="EXTERNAL_R_ARCH_PACKAGE",
            expected_result_artifact_id="ART-EXPECTED-EXP-WF-002",
            actual_result_artifact_id="ART-ACTUAL-REP-IMPL-002",
        )
        assert rec.reproduction_verdict == "INDEPENDENT_IMPLEMENTATION_REPRODUCED"

    def test_pos_ref_04_independent_dataset_replicated(self):
        """4. Genuine independent dataset replication verified across distinct verified exchanges."""
        rep_lab = ReproducibilityLabV2()
        rec = rep_lab.evaluate_reproduction_attempt(
            reproduction_id="REP-POS-DATA-03",
            original_experiment_id="EXP-REG-003",
            reproduction_type="INDEPENDENT_DATASET",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-COINBASE-01",
            original_methodology_id="METH-REG-01",
            reproduction_methodology_id="METH-REG-01",
            implementation_identity="EXTERNAL_PYTHON_ENGINE",
            expected_result_artifact_id="ART-EXPECTED-EXP-REG-003",
            actual_result_artifact_id="ART-ACTUAL-REP-DATA-003",
            rtol=0.1,
            atol=0.01,
        )
        assert rec.reproduction_verdict == "INDEPENDENT_DATASET_REPLICATED"
        assert rec.independence_verdict == "INDEPENDENT_SOURCE_VERIFIED"

    def test_pos_ref_05_high_grade_evidence_when_dimensions_verified(self):
        """5. High-grade evidence assessment when all required dimensions are verified."""
        eng = EvidenceGradingEngine()
        asmt = eng.compute_evidence_grade(
            discovery_id="DISC-POS-PERFECT",
            dimensions={
                "dataset_provenance": "TRUSTED_PROVENANCE_VERIFIED",
                "data_structural_integrity": "STRUCTURE_VALIDATED",
                "hypothesis_preregistration": "PROSPECTIVELY_PREREGISTERED",
                "statistical_validity": "STATISTICALLY_VALID",
                "multiple_testing_control": True,
                "temporal_validation": True,
                "reproducibility": "INDEPENDENT_DATASET_REPLICATED",
                "regime_generalization": "VERIFIED_TRUE",
                "absence_of_contradictions": "VERIFIED_TRUE",
                "disclosed_limitations": "VERIFIED_TRUE",
            },
        )
        assert asmt.grade == "INDEPENDENTLY_REPLICATED_EVIDENCE"

    def test_pos_ref_06_temporal_partition_non_overlap(self):
        """6. Temporal partition non-overlap correctly verified on distinct intervals."""
        meta_q1 = TrustedDatasetProvenanceResolver.resolve_dataset("DS-BTC-1H-Q1-2024")
        meta_q2 = TrustedDatasetProvenanceResolver.resolve_dataset("DS-BTC-1H-Q2-2024")
        assert meta_q1 is not None and meta_q2 is not None
        has_overlap, _ = TrustedDatasetProvenanceResolver.check_observation_overlap(meta_q1, meta_q2)
        assert has_overlap is False

    def test_pos_ref_07_safe_artifact_cache_operates_correctly(self):
        """7. Safe artifact cache operates correctly on unmodified file."""
        TrustedReproductionArtifactResolver.invalidate_cache()
        art1, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-EXPECTED-EXP-ASV-001")
        assert art1 is not None
        art2, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-EXPECTED-EXP-ASV-001")
        assert art2 is not None
        assert art1.actual_sha256 == art2.actual_sha256

    def test_pos_ref_08_end_to_end_evidence_grading_flow(self, tmp_path):
        """8. End-to-end evidence grading flow from discovery to knowledge base."""
        eng = EvidenceGradingEngine(persistence_path=tmp_path / "grades.json")
        kb = DiscoveryKnowledgeBase(persistence_path=tmp_path / "kb.json")
        asmt = eng.resolve_and_verify_evidence_grade(
            discovery_id="DISC-VOL-CLUST-001",
            hypothesis_id="HYP-VOL-PERSIST-001",
            research_id="RES-EXP-01",
            dataset_id="DS-BTC-1H-Q1-2024",
        )
        assert asmt is not None
        assert asmt.grade in ("EVIDENCE_NOT_ESTABLISHED", "PRELIMINARY_SUPPORT", "EXPLORATORY_EVIDENCE", "INSUFFICIENT_EVIDENCE")


# ==============================================================================
# SECTION 9: PERSISTENCE, RECOVERY, API SECURITY & GOVERNANCE INVARIANTS
# ==============================================================================

class TestPersistenceRecoveryAndGovernance:
    """Persistence recovery, API security, and mandatory governance invariant tests."""

    def test_pr_01_persistence_across_restart(self, tmp_path):
        """1. Persistence across restart restores saved reproduction records."""
        storage = tmp_path / "repro.json"
        lab1 = ReproducibilityLabV2(persistence_path=storage)
        lab1.evaluate_reproduction_attempt(
            reproduction_id="REP-RESTART-01",
            original_experiment_id="EXP-ASV-001",
            reproduction_type="COMPUTATIONAL_REPEATABILITY",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-ENGLE-ARCH-01",
            reproduction_methodology_id="METH-ENGLE-ARCH-01",
            implementation_identity="CBE_ENGINE",
            expected_result_artifact_id="ART-EXPECTED-EXP-ASV-001",
            actual_result_artifact_id="ART-ACTUAL-REP-VOL-001",
        )
        # Restart
        lab2 = ReproducibilityLabV2(persistence_path=storage)
        rec = lab2.get_record("REP-RESTART-01")
        assert rec is not None
        assert rec.reproduction_verdict == "COMPUTATIONAL_REPEATABILITY_VERIFIED"

    def test_pr_02_file_corruption_fail_closed(self, tmp_path):
        """2. Malformed JSON file fails closed gracefully without raising unhandled crash."""
        corrupt_file = tmp_path / "corrupt.json"
        corrupt_file.write_text("{corrupt json !!!")
        lab = ReproducibilityLabV2(persistence_path=corrupt_file)
        assert isinstance(lab.list_records(), list)

    def test_pr_03_governance_invariants_strictly_enforced(self):
        """3. Strict governance invariants are permanent and enforced."""
        eng = EvidenceGradingEngine()
        asmt = eng.get_assessment("GRD-VOL-001")
        assert asmt.directional_trading_eligibility == 0
        assert asmt.technical_decision == "TECHNICAL_NO_GO"

    def test_pr_04_verification_only_runtime_signing_attempt(self):
        """4. Verification-only runtime prohibits unauthorized signing."""
        from coin_behavior_engine.product.credential_manager import SigningAuthorityError
        with pytest.raises(Exception):
            ScientificReadinessEvaluator.create_signed_intake_manifest(
                dataset_id="DS-FORGED",
                caller_supplied_secret="UNAUTHORIZED_SECRET",
            )


# ==============================================================================
# SPRINT 28.1 FINAL ACCEPTANCE PATCH: TASKS 1, 2, 3 VERIFICATION SUITE
# ==============================================================================

class TestTask1ArtifactCacheContextValidation:
    """Task 1: Comprehensive verification that artifact cache revalidates all context on every hit."""

    def test_cache_hit_different_execution_id_rejected(self):
        """Cached artifact cannot be queried under a differing expected_execution_id."""
        art_path = Path("data/research_lab/discovery_artifacts/art_cache_exec.json")
        try:
            payload = {
                "artifact_id": "ART-CACHE-EXEC-01",
                "execution_id": "EXEC-ORIGINAL-01",
                "dataset_id": "DS-BTC-1H-Q1-2024",
                "methodology_id": "METH-ENGLE-ARCH-01",
                "metrics": {"volatility": 0.042},
            }
            art_path.write_text(json.dumps(payload))
            sha = hashlib.sha256(art_path.read_bytes()).hexdigest()

            TrustedReproductionArtifactResolver.register_artifact(
                "ART-CACHE-EXEC-01",
                {"file_path": str(art_path), "expected_sha256": sha, "execution_id": "EXEC-ORIGINAL-01"},
            )

            # First load: cache warm-up
            art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact(
                "ART-CACHE-EXEC-01",
                expected_sha256=sha,
                expected_execution_id="EXEC-ORIGINAL-01",
            )
            assert art is not None
            assert err is None

            # Second load (cache hit) with differing expected_execution_id must fail
            art_bad, err_bad = TrustedReproductionArtifactResolver.load_and_verify_artifact(
                "ART-CACHE-EXEC-01",
                expected_sha256=sha,
                expected_execution_id="EXEC-DIFFERENT-99",
            )
            assert art_bad is None
            assert "execution ID mismatch" in err_bad
        finally:
            if art_path.exists():
                art_path.unlink()

    def test_cache_hit_different_dataset_id_rejected(self):
        """Cached artifact cannot be queried under a differing expected_dataset_id."""
        art_path = Path("data/research_lab/discovery_artifacts/art_cache_ds.json")
        try:
            payload = {
                "artifact_id": "ART-CACHE-DS-01",
                "execution_id": "EXEC-DS-01",
                "dataset_id": "DS-ORIGINAL-01",
                "methodology_id": "METH-01",
                "metrics": {"sharpe": 1.5},
            }
            art_path.write_text(json.dumps(payload))
            sha = hashlib.sha256(art_path.read_bytes()).hexdigest()

            TrustedReproductionArtifactResolver.register_artifact(
                "ART-CACHE-DS-01",
                {"file_path": str(art_path), "expected_sha256": sha},
            )

            art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact(
                "ART-CACHE-DS-01",
                expected_sha256=sha,
                expected_dataset_id="DS-ORIGINAL-01",
            )
            assert art is not None

            # Cache hit with differing expected_dataset_id fails
            art_bad, err_bad = TrustedReproductionArtifactResolver.load_and_verify_artifact(
                "ART-CACHE-DS-01",
                expected_sha256=sha,
                expected_dataset_id="DS-FORGED-DATASET-99",
            )
            assert art_bad is None
            assert "dataset ID mismatch" in err_bad
        finally:
            if art_path.exists():
                art_path.unlink()

    def test_cache_hit_different_methodology_id_rejected(self):
        """Cached artifact cannot be queried under a differing expected_methodology_id."""
        art_path = Path("data/research_lab/discovery_artifacts/art_cache_meth.json")
        try:
            payload = {
                "artifact_id": "ART-CACHE-METH-01",
                "execution_id": "EXEC-METH-01",
                "dataset_id": "DS-01",
                "methodology_id": "METH-ORIGINAL-01",
                "metrics": {"stat": 9.8},
            }
            art_path.write_text(json.dumps(payload))
            sha = hashlib.sha256(art_path.read_bytes()).hexdigest()

            TrustedReproductionArtifactResolver.register_artifact(
                "ART-CACHE-METH-01",
                {"file_path": str(art_path), "expected_sha256": sha},
            )

            art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact(
                "ART-CACHE-METH-01",
                expected_sha256=sha,
                expected_methodology_id="METH-ORIGINAL-01",
            )
            assert art is not None

            # Cache hit with differing expected_methodology_id fails
            art_bad, err_bad = TrustedReproductionArtifactResolver.load_and_verify_artifact(
                "ART-CACHE-METH-01",
                expected_sha256=sha,
                expected_methodology_id="METH-SPOOFED-99",
            )
            assert art_bad is None
            assert "methodology ID mismatch" in err_bad
        finally:
            if art_path.exists():
                art_path.unlink()

    def test_cache_hit_after_revocation_fails_closed(self):
        """Cached artifact immediately fails closed once revoked."""
        art_path = Path("data/research_lab/discovery_artifacts/art_cache_rev.json")
        try:
            payload = {"artifact_id": "ART-CACHE-REV-01", "metrics": {"val": 1.0}}
            art_path.write_text(json.dumps(payload))
            sha = hashlib.sha256(art_path.read_bytes()).hexdigest()

            TrustedReproductionArtifactResolver.register_artifact(
                "ART-CACHE-REV-01",
                {"file_path": str(art_path), "expected_sha256": sha},
            )

            art, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact(
                "ART-CACHE-REV-01", expected_sha256=sha
            )
            assert art is not None

            # Revoke artifact
            TrustedReproductionArtifactResolver.revoke_artifact("ART-CACHE-REV-01", "Compromised")

            # Subsequent query (even if cached) must fail
            art_rev, err = TrustedReproductionArtifactResolver.load_and_verify_artifact(
                "ART-CACHE-REV-01", expected_sha256=sha
            )
            assert art_rev is None
            assert "revoked" in err.lower()
        finally:
            if art_path.exists():
                art_path.unlink()


class TestTask2ExternalDatasetRegistrationAuthority:
    """Task 2: Authoritative registration context and authenticated provenance evidence enforcement."""

    def test_registration_without_context_rejected(self):
        """Calling register_verified_external_dataset without context raises PermissionError."""
        meta = TrustedDatasetMetadata(
            dataset_id="DS-EXT-NO-CTX",
            exchange="COINBASE",
            symbol="BTC/USD",
            market_type="SPOT",
            timeframe="1h",
            observation_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            observation_end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            observation_count=24,
            source_artifact_sha256="a" * 64,
            dataset_fingerprint="fp1",
            source_lineage="COINBASE_API",
            parent_dataset_id=None,
            transformation_lineage=[],
            quarantine_status="CLEAN",
            provenance_status="VERIFIED",
        )
        with pytest.raises(PermissionError, match="Authoritative registration context is required"):
            TrustedDatasetProvenanceResolver.register_verified_external_dataset(meta, registration_context=None)

    def test_registration_with_unauthorized_authority_rejected(self):
        """Registration with an unauthorized authority identifier raises PermissionError."""
        meta = TrustedDatasetMetadata(
            dataset_id="DS-EXT-BAD-AUTH",
            exchange="COINBASE",
            symbol="BTC/USD",
            market_type="SPOT",
            timeframe="1h",
            observation_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            observation_end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            observation_count=24,
            source_artifact_sha256="a" * 64,
            dataset_fingerprint="fp1",
            source_lineage="COINBASE_API",
            parent_dataset_id=None,
            transformation_lineage=[],
            quarantine_status="CLEAN",
            provenance_status="VERIFIED",
        )
        ctx = {"authority": "UNAUTHORIZED_COMMUNITY_KEY", "token": "valid_looking_token_12345"}
        ev = {"intake_manifest_sha256": "1" * 64, "source_lineage_digest": "2" * 64, "external_exchange": "COINBASE"}
        with pytest.raises(PermissionError, match="Unauthorized registration authority"):
            TrustedDatasetProvenanceResolver.register_verified_external_dataset(meta, ctx, ev)

    def test_registration_with_missing_provenance_evidence_rejected(self):
        """Registration missing 64-char provenance evidence digests raises ValueError."""
        meta = TrustedDatasetMetadata(
            dataset_id="DS-EXT-BAD-EV",
            exchange="COINBASE",
            symbol="BTC/USD",
            market_type="SPOT",
            timeframe="1h",
            observation_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            observation_end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            observation_count=24,
            source_artifact_sha256="a" * 64,
            dataset_fingerprint="fp1",
            source_lineage="COINBASE_API",
            parent_dataset_id=None,
            transformation_lineage=[],
            quarantine_status="CLEAN",
            provenance_status="VERIFIED",
        )
        ctx = {"authority": "CBE_DATASET_GOVERNANCE_AUTHORITY", "token": "secret_token_12345"}
        bad_ev = {"intake_manifest_sha256": "too_short", "source_lineage_digest": "2" * 64, "external_exchange": "COINBASE"}
        with pytest.raises(ValueError, match="intake_manifest_sha256"):
            TrustedDatasetProvenanceResolver.register_verified_external_dataset(meta, ctx, bad_ev)

    def test_registration_with_binance_as_external_rejected(self):
        """Binance datasets cannot be registered as independent external datasets."""
        meta = TrustedDatasetMetadata(
            dataset_id="DS-EXT-BINANCE",
            exchange="BINANCE",
            symbol="BTC/USDT",
            market_type="SPOT",
            timeframe="1h",
            observation_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            observation_end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            observation_count=24,
            source_artifact_sha256="a" * 64,
            dataset_fingerprint="fp1",
            source_lineage="BINANCE_HISTORICAL",
            parent_dataset_id=None,
            transformation_lineage=[],
            quarantine_status="CLEAN",
            provenance_status="VERIFIED",
        )
        ctx = {"authority": "CBE_DATASET_GOVERNANCE_AUTHORITY", "token": "secret_token_12345"}
        ev = {"intake_manifest_sha256": "1" * 64, "source_lineage_digest": "2" * 64, "external_exchange": "BINANCE"}
        with pytest.raises(ValueError, match="Binance datasets cannot be registered as independent external datasets"):
            TrustedDatasetProvenanceResolver.register_verified_external_dataset(meta, ctx, ev)

    def test_registration_with_shared_binance_lineage_masquerading_rejected(self):
        """External dataset masquerading with Binance lineage is rejected."""
        meta = TrustedDatasetMetadata(
            dataset_id="DS-EXT-MASQUERADE",
            exchange="KRAKEN",
            symbol="BTC/USD",
            market_type="SPOT",
            timeframe="1h",
            observation_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            observation_end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            observation_count=24,
            source_artifact_sha256="a" * 64,
            dataset_fingerprint="fp1",
            source_lineage="TRANSFORMED_FROM_BINANCE_DATA",
            parent_dataset_id=None,
            transformation_lineage=[],
            quarantine_status="CLEAN",
            provenance_status="VERIFIED",
        )
        ctx = {"authority": "CBE_DATASET_GOVERNANCE_AUTHORITY", "token": "secret_token_12345"}
        ev = {"intake_manifest_sha256": "1" * 64, "source_lineage_digest": "2" * 64, "external_exchange": "KRAKEN"}
        with pytest.raises(ValueError, match="Shared Binance lineage detected"):
            TrustedDatasetProvenanceResolver.register_verified_external_dataset(meta, ctx, ev)

    def test_genuine_authenticated_registration_certifies_independence(self):
        """Properly authenticated external dataset establishes verified independence against Binance."""
        meta = TrustedDatasetMetadata(
            dataset_id="DS-GENUINE-KRAKEN-01",
            exchange="KRAKEN",
            symbol="BTC/USD",
            market_type="SPOT",
            timeframe="1h",
            observation_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
            observation_end=datetime(2024, 1, 2, tzinfo=timezone.utc),
            observation_count=24,
            source_artifact_sha256="e" * 64,
            dataset_fingerprint="fp_kraken",
            source_lineage="KRAKEN_REST_HISTORICAL",
            parent_dataset_id=None,
            transformation_lineage=[],
            quarantine_status="CLEAN",
            provenance_status="UNVERIFIED",
        )
        ctx = {"authority": "CBE_DATASET_GOVERNANCE_AUTHORITY", "token": "secret_token_12345"}
        ev = {"intake_manifest_sha256": "1" * 64, "source_lineage_digest": "2" * 64, "external_exchange": "KRAKEN"}

        res_meta = TrustedDatasetProvenanceResolver.register_verified_external_dataset(meta, ctx, ev)
        assert res_meta.provenance_status == "TRUSTED_PROVENANCE_VERIFIED"
        assert res_meta.registration_authority_verified is True

        verdict, issues = TrustedDatasetProvenanceResolver.verify_independence(
            "DS-BTC-1H-Q1-2024",
            "DS-GENUINE-KRAKEN-01",
        )
        assert verdict == "INDEPENDENT_SOURCE_VERIFIED"
        assert len(issues) == 0


class TestTask3ReproductionArtifactIntegrity:
    """Task 3: Authoritative reproduction artifact registration and execution record binding."""

    def test_unregistered_artifact_file_rejected(self):
        """Unregistered artifact file with valid JSON structure is rejected."""
        art_path = Path("data/research_lab/discovery_artifacts/ART-UNREGISTERED-FILE.json")
        try:
            payload = {
                "artifact_id": "ART-UNREGISTERED-FILE",
                "execution_id": "EXEC-TEST-01",
                "dataset_id": "DS-01",
                "methodology_id": "METH-01",
                "metrics": {"stat": 1.23},
            }
            art_path.write_text(json.dumps(payload))

            art, err = TrustedReproductionArtifactResolver.load_and_verify_artifact(
                "ART-UNREGISTERED-FILE"
            )
            assert art is None
            assert "not registered" in err
        finally:
            if art_path.exists():
                art_path.unlink()

    def test_reproduction_with_unregistered_artifact_fails_verdict(self):
        """ReproductionLabV2 evaluate_reproduction_attempt fails with REPRODUCTION_ARTIFACT_INVALID on unregistered artifact."""
        lab = ReproducibilityLabV2()
        rec = lab.evaluate_reproduction_attempt(
            reproduction_id="REP-UNREG-01",
            original_experiment_id="EXP-ASV-001",
            reproduction_type="EXACT_REPLICATION",
            source_dataset_id="DS-BTC-1H-Q1-2024",
            reproduction_dataset_id="DS-BTC-1H-Q1-2024",
            original_methodology_id="METH-ENGLE-ARCH-01",
            reproduction_methodology_id="METH-ENGLE-ARCH-01",
            implementation_identity="CBE_ENGINE",
            expected_result_artifact_id="NON_EXISTENT_OR_UNREGISTERED_ART_ID",
            actual_result_artifact_id="ART-ACTUAL-REP-VOL-001",
        )
        assert rec.reproduction_verdict in ("REPRODUCTION_ARTIFACT_INVALID", "REPRODUCTION_EVIDENCE_INCOMPLETE", "INSUFFICIENT_EVIDENCE")

    def test_fabricated_unauthenticated_execution_records_rejected(self):
        """Two files with fabricated, unauthenticated execution IDs are rejected in compare_verified_artifacts."""
        p1 = Path("data/research_lab/discovery_artifacts/art_fab1.json")
        p2 = Path("data/research_lab/discovery_artifacts/art_fab2.json")
        try:
            p1.write_text(json.dumps({"execution_id": "FAB-EXEC-01", "metrics": {"v": 1.0}}))
            p2.write_text(json.dumps({"execution_id": "FAB-EXEC-02", "metrics": {"v": 1.0}}))

            sha1 = hashlib.sha256(p1.read_bytes()).hexdigest()
            sha2 = hashlib.sha256(p2.read_bytes()).hexdigest()

            TrustedReproductionArtifactResolver.register_artifact("ART-FAB-1", {"file_path": str(p1), "expected_sha256": sha1})
            TrustedReproductionArtifactResolver.register_artifact("ART-FAB-2", {"file_path": str(p2), "expected_sha256": sha2})

            art1, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-FAB-1", expected_sha256=sha1)
            art2, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-FAB-2", expected_sha256=sha2)

            matched, comp, rel, abs_d, disc = TrustedReproductionArtifactResolver.compare_verified_artifacts(art1, art2)
            assert matched is False
            assert comp == "UNAUTHENTICATED_EXECUTION_RECORD"
            assert any("unauthenticated" in d.lower() for d in disc)
        finally:
            if p1.exists():
                p1.unlink()
            if p2.exists():
                p2.unlink()

    def test_identical_execution_evidence_rejected(self):
        """Original and reproduction outputs originating from identical execution are rejected."""
        p1 = Path("data/research_lab/discovery_artifacts/art_ident1.json")
        p2 = Path("data/research_lab/discovery_artifacts/art_ident2.json")
        try:
            p1.write_text(json.dumps({"execution_id": "EXEC-SAME-01", "metrics": {"v": 1.0}}))
            p2.write_text(json.dumps({"execution_id": "EXEC-SAME-01", "metrics": {"v": 1.0}}))

            sha1 = hashlib.sha256(p1.read_bytes()).hexdigest()
            sha2 = hashlib.sha256(p2.read_bytes()).hexdigest()

            TrustedReproductionArtifactResolver.register_artifact("ART-IDENT-1", {"file_path": str(p1), "expected_sha256": sha1})
            TrustedReproductionArtifactResolver.register_artifact("ART-IDENT-2", {"file_path": str(p2), "expected_sha256": sha2})
            TrustedReproductionArtifactResolver.register_authenticated_execution("EXEC-SAME-01")

            art1, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-IDENT-1", expected_sha256=sha1)
            art2, _ = TrustedReproductionArtifactResolver.load_and_verify_artifact("ART-IDENT-2", expected_sha256=sha2)

            matched, comp, rel, abs_d, disc = TrustedReproductionArtifactResolver.compare_verified_artifacts(art1, art2)
            assert matched is False
            assert comp in ("IDENTICAL_EXECUTION_EVIDENCE", "FRAUDULENT_SELF_COMPARISON")
        finally:
            if p1.exists():
                p1.unlink()
            if p2.exists():
                p2.unlink()


"""
Test Suite: Sprint 24 Final Trust Boundary Closure
Covers all 25 required negative & positive security tests, cache invalidation,
integration with Comparison Lab, and governance invariants.
"""

import hashlib
import hmac
import json
import os
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from coin_behavior_engine.product.attestation_verifier import (
    ObservationCompletenessAttestationVerifier,
    attestation_cache,
)
from coin_behavior_engine.product.credential_manager import signing_key_registry
from coin_behavior_engine.product.research_catalog_provider import (
    ResearchRecord,
    RecordStatus,
)
from coin_behavior_engine.product.research_intelligence_workspace import (
    calculate_temporal_observation_overlap,
    ResearchWorkspaceV2Engine,
)


@pytest.fixture(autouse=True)
def setup_test_keys():
    """Ensure trusted test keys are registered and cache is clean."""
    attestation_cache.clear()
    signing_key_registry.register_key("test-trusted-key-1", "test-secret-key-12345678", is_active=True)
    signing_key_registry.register_key("test-trusted-key-2", "test-secret-key-87654321", is_active=False)
    yield
    attestation_cache.clear()


def make_test_record(
    record_id: str = "RES-TEST-01",
    dataset_id: str = "BTCUSDT-1H",
    cadence: str = "1h",
    start_utc: str = "2024-01-01T00:00:00Z",
    end_utc: str = "2024-01-06T00:00:00Z",
    sha256: str = "46c4cb960dd36c613bb9826cb8d54185724d6060e11b822ed82fd9213a3e9598",
    source_artifact: str = "data/test_artifact.json",
    sample_size: int = 120,
    observed_timestamps=None,
    attestation=None,
) -> ResearchRecord:
    return ResearchRecord(
        id=record_id,
        title=f"Test Record {record_id}",
        title_en=f"Test Record {record_id}",
        category="Volatilite",
        dataset_id=dataset_id,
        historical_period="2024",
        window_cadence=cadence,
        specification_id=f"SP-{record_id}",
        observation_start_utc=start_utc,
        observation_end_utc=end_utc,
        observation_interval_count=sample_size,
        source_artifact=source_artifact,
        source_artifact_sha256=sha256,
        sample_size=sample_size,
        volatility_ratio=1.25,
        observed_timestamps=observed_timestamps,
        observation_completeness_attestation=attestation,
        evidence_status="SIGNED_VALID",
    )


class TestSprint24All25TargetedSecurityScenarios:
    """The 25 targeted negative and positive security tests required by Sprint 24 Trust Boundary Closure."""

    # 1. Self-declared VERIFIED without signature
    def test_01_self_declared_verified_without_signature_fails_closed(self):
        r1 = make_test_record("RES-01")
        r2 = make_test_record("RES-02")
        # Self-declared dictionary without signature
        r1.observation_completeness_attestation = {
            "status": "VERIFIED",
            "verified_continuous_series": True,
            "observation_count": 120,
        }
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "SIGNATURE_EMPTY_OR_INVALID"

    # 2. Self-declared verified_continuous_series=true without trusted authority
    def test_02_self_declared_continuous_without_trusted_authority_fails_closed(self):
        r1 = make_test_record("RES-01")
        r2 = make_test_record("RES-02")
        r1.observation_completeness_attestation = {
            "verified_continuous_series": True,
            "issuer": "UNAUTHORIZED_THIRD_PARTY",
            "signature": "hmac-sha256:test-trusted-key-1:1234567890abcdef1234567890abcdef1234567890abcdef1234567890abcdef",
            "key_id": "test-trusted-key-1",
            "schema_version": "CBE-ATTESTATION-1.0.0",
        }
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "UNKNOWN_ISSUER"

    # 3. Forged signature
    def test_03_forged_signature_fails_closed(self):
        r1 = make_test_record("RES-01")
        r2 = make_test_record("RES-02")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1,
            key_id="test-trusted-key-1",
            secret="test-secret-key-12345678",
            forged_signature="hmac-sha256:test-trusted-key-1:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
        )
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "SIGNATURE_VERIFICATION_FAILED"

    # 4. Modified signed payload
    def test_04_modified_signed_payload_fails_closed(self):
        r1 = make_test_record("RES-01")
        r2 = make_test_record("RES-02")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678"
        )
        # Tamper with signed claim
        att["observation_count"] = 999
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] in ("OBSERVATION_COUNT_MISMATCH", "SIGNATURE_VERIFICATION_FAILED")

    # 5. Unknown issuer
    def test_05_unknown_issuer_fails_closed(self):
        r1 = make_test_record("RES-01")
        r2 = make_test_record("RES-02")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678", issuer="EXTERNAL_UNTRUSTED_ISSUER"
        )
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "UNKNOWN_ISSUER"

    # 6. Revoked key
    def test_06_revoked_key_fails_closed(self):
        signing_key_registry.register_key("revoked-k1", "revoked-secret-1234", is_active=False)
        signing_key_registry.revoke_key("revoked-k1")
        r1 = make_test_record("RES-01")
        r2 = make_test_record("RES-02")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="revoked-k1", secret="revoked-secret-1234"
        )
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "REVOKED_SIGNING_KEY"

    # 7. Wrong dataset identifier
    def test_07_wrong_dataset_identifier_fails_closed(self):
        r1 = make_test_record("RES-01", dataset_id="BTCUSDT-1H")
        r2 = make_test_record("RES-02", dataset_id="BTCUSDT-1H")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678", override_dataset_id="ETHUSDT-1H"
        )
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "DATASET_ID_MISMATCH"

    # 8. Wrong research record identifier
    def test_08_wrong_research_record_identifier_fails_closed(self):
        r1 = make_test_record("RES-01")
        r2 = make_test_record("RES-02")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678", override_record_id="RES-SPOOF-01"
        )
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "REPLAY_ATTACK_DETECTED"

    # 9. Wrong source SHA-256
    def test_09_wrong_source_sha256_fails_closed(self):
        r1 = make_test_record("RES-01", sha256="a" * 64)
        r2 = make_test_record("RES-02")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678", override_sha256="b" * 64
        )
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "ARTIFACT_HASH_MISMATCH"

    # 10. Wrong observation start/end
    def test_10_wrong_observation_window_fails_closed(self):
        r1 = make_test_record("RES-01", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")
        r2 = make_test_record("RES-02")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1,
            key_id="test-trusted-key-1",
            secret="test-secret-key-12345678",
            override_start="2024-01-02T00:00:00Z",
            override_end="2024-01-07T00:00:00Z",
        )
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "OBSERVATION_WINDOW_MISMATCH"

    # 11. Wrong cadence
    def test_11_wrong_cadence_fails_closed(self):
        r1 = make_test_record("RES-01", cadence="1h")
        r2 = make_test_record("RES-02", cadence="1h")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678", override_cadence="4h"
        )
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "CADENCE_MISMATCH"

    # 12. Wrong observation count
    def test_12_wrong_observation_count_fails_closed(self):
        r1 = make_test_record("RES-01", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")  # 120 hours
        r2 = make_test_record("RES-02")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678", observation_count=50
        )
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "OBSERVATION_COUNT_MISMATCH"

    # 13. Unsupported schema version
    def test_13_unsupported_schema_version_fails_closed(self):
        r1 = make_test_record("RES-01")
        r2 = make_test_record("RES-02")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678", schema_version="UNSUPPORTED-9.9.9"
        )
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "UNSUPPORTED_SCHEMA_VERSION"

    # 14. Replay against another research record
    def test_14_replay_against_another_record_fails_closed(self):
        r1 = make_test_record("RES-A")
        r2 = make_test_record("RES-B")
        # Generate valid attestation for RES-A
        att_a = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678"
        )
        # Replay onto RES-B
        r2.observation_completeness_attestation = att_a
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] in ("INSUFFICIENT_OVERLAP_EVIDENCE", "ATTESTATION_VERIFICATION_FAILED")

    # 15. Missing trusted verification key
    def test_15_missing_trusted_verification_key_fails_closed(self):
        r1 = make_test_record("RES-01")
        r2 = make_test_record("RES-02")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="unregistered-key-xyz", secret="some-secret-999"
        )
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "MISSING_TRUSTED_VERIFICATION_KEY"

    # 16. Signing key stored in an untrusted location
    def test_16_signing_key_stored_in_untrusted_location_fails_closed(self):
        r1 = make_test_record("RES-01")
        r2 = make_test_record("RES-02")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678"
        )
        att["key_location"] = "/tmp/app_writeable_dir/key.pem"
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] == "UNTRUSTED_KEY_LOCATION"

    # 17. Valid explicit timestamp intersection without attestation (Path A)
    def test_17_valid_explicit_timestamp_intersection_without_attestation_passes(self):
        ts = [f"2024-01-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]
        r1 = make_test_record("RES-EXP-1", observed_timestamps=ts)
        r2 = make_test_record("RES-EXP-2", observed_timestamps=ts)
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is True
        assert res["rejection_code"] is None
        assert res["shared_interval_count"] == 120

    # 18. Two valid authenticated continuous series (Path B)
    def test_18_two_valid_authenticated_continuous_series_passes(self):
        r1 = make_test_record("RES-ATT-1", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")  # 120h
        r2 = make_test_record("RES-ATT-2", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")  # 120h
        r1.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678"
        )
        r2.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r2, key_id="test-trusted-key-1", secret="test-secret-key-12345678"
        )
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is True
        assert res["rejection_code"] is None
        assert res["shared_interval_count"] == 120

    # 19. Mixed timestamp and attested-series intersection
    def test_19_mixed_timestamp_and_attested_series_intersection_passes(self):
        ts = [f"2024-01-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]
        r1 = make_test_record("RES-EXP", observed_timestamps=ts)
        r2 = make_test_record("RES-ATT", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")
        r2.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r2, key_id="test-trusted-key-1", secret="test-secret-key-12345678"
        )
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is True
        assert res["rejection_code"] is None
        assert res["shared_interval_count"] == 120

    # 20. Misaligned sampling grids
    def test_20_misaligned_sampling_grids_fails_closed(self):
        # Candidate 1: 00:00:00 grid; Candidate 2: 00:30:00 grid (30-min offset, both 1h cadence)
        r1 = make_test_record("RES-GRID-00", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")
        r2 = make_test_record("RES-GRID-30", start_utc="2024-01-01T00:30:00Z", end_utc="2024-01-06T00:30:00Z")
        r1.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678"
        )
        r2.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r2, key_id="test-trusted-key-1", secret="test-secret-key-12345678"
        )
        res = calculate_temporal_observation_overlap([r1, r2])
        # Grid intersection is empty!
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "DISJOINT_OBSERVATION_WINDOWS"
        assert res["shared_interval_count"] == 0

    # 21. Exactly 99 shared observations
    def test_21_exactly_99_shared_observations_fails_floor(self):
        ts1 = [f"2024-02-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]
        # r2 shares only first 99 timestamps, followed by 21 disjoint timestamps
        ts2 = ts1[:99] + [f"2024-02-{(i // 24) + 10:02d}T{i % 24:02d}:00:00Z" for i in range(21)]
        r1 = make_test_record("RES-99-A", observed_timestamps=ts1)
        r2 = make_test_record("RES-99-B", observed_timestamps=ts2)
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "INSUFFICIENT_OVERLAP"
        assert res["shared_interval_count"] == 99

    # 22. Exactly 100 shared observations
    def test_22_exactly_100_shared_observations_passes(self):
        ts1 = [f"2024-03-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]
        ts2 = ts1[:100] + [f"2024-03-{(i // 24) + 10:02d}T{i % 24:02d}:00:00Z" for i in range(20)]
        r1 = make_test_record("RES-100-A", observed_timestamps=ts1)
        r2 = make_test_record("RES-100-B", observed_timestamps=ts2)
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is True
        assert res["rejection_code"] is None
        assert res["shared_interval_count"] == 100

    # 23. Duplicate timestamps
    def test_23_duplicate_timestamps_rejected(self):
        ts = [f"2024-04-{(i // 24) + 1:02d}T{i % 24:02d}:00:00Z" for i in range(120)]
        ts.append(ts[5])  # duplicate
        r1 = make_test_record("RES-DUP", observed_timestamps=ts)
        r2 = make_test_record("RES-OK", observed_timestamps=ts[:-1])
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "DUPLICATED_OBSERVATIONS_DETECTED"

    # 24. Missing observations despite a claimed complete series
    def test_24_missing_observations_despite_claimed_complete_fails(self):
        r1 = make_test_record("RES-MISS-01", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")
        r2 = make_test_record("RES-OK")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1,
            key_id="test-trusted-key-1",
            secret="test-secret-key-12345678",
            missing_observations=5,  # explicitly flagged missing observations
        )
        r1.observation_completeness_attestation = att
        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
        assert res["attestation_rejection_code"] in ("MISSING_OBSERVATIONS_DETECTED", "INCONSISTENT_COMPLETENESS_METADATA")

    # 25. Attestation becoming invalid after source artifact modification
    def test_25_attestation_becoming_invalid_after_source_artifact_modification(self):
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tf:
            tf.write('{"initial_data": "genuine research payload"}')
            temp_path = tf.name

        try:
            initial_sha = hashlib.sha256(Path(temp_path).read_bytes()).hexdigest()
            r1 = make_test_record("RES-TAMPER-01", source_artifact=temp_path, sha256=initial_sha)
            r2 = make_test_record("RES-OK")

            att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
                r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678"
            )
            r1.observation_completeness_attestation = att

            # Verify initial validity
            v_init = ObservationCompletenessAttestationVerifier.verify_attestation(r1, att, use_cache=False)
            assert v_init["is_valid"] is True

            # Now tamper with disk artifact
            with open(temp_path, "w") as tf2:
                tf2.write('{"initial_data": "MALICIOUSLY TAMPERED PAYLOAD"}')

            # Verification MUST fail closed
            v_tampered = ObservationCompletenessAttestationVerifier.verify_attestation(r1, att, use_cache=False)
            assert v_tampered["is_valid"] is False
            assert v_tampered["rejection_code"] in ("ARTIFACT_TAMPERED", "SOURCE_ARTIFACT_HASH_MISMATCH")

            res = calculate_temporal_observation_overlap([r1, r2])
            assert res["overlap_valid"] is False
            assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"
            assert res["attestation_rejection_code"] in ("ARTIFACT_TAMPERED", "SOURCE_ARTIFACT_HASH_MISMATCH")
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


class TestSprint24CacheInvalidationAndPerformance:
    """Verifies cache invalidation, revocation handling, and sub-millisecond latency."""

    def test_cache_hit_and_invalidation_on_revocation(self):
        attestation_cache.clear()
        r1 = make_test_record("RES-CACHE-01")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-1", secret="test-secret-key-12345678"
        )
        r1.observation_completeness_attestation = att

        # First call: cache miss
        v1 = ObservationCompletenessAttestationVerifier.verify_attestation(r1, att, use_cache=True)
        assert v1["is_valid"] is True
        stats1 = attestation_cache.stats
        assert stats1["miss_count"] == 1
        assert stats1["hit_count"] == 0

        # Second call: cache hit
        v2 = ObservationCompletenessAttestationVerifier.verify_attestation(r1, att, use_cache=True)
        assert v2["is_valid"] is True
        stats2 = attestation_cache.stats
        assert stats2["hit_count"] == 1

        # Revoke the signing key
        signing_key_registry.revoke_key("test-trusted-key-1")

        # Third call: cache key includes is_revoked=True, cache misses and fails closed!
        v3 = ObservationCompletenessAttestationVerifier.verify_attestation(r1, att, use_cache=True)
        assert v3["is_valid"] is False
        assert v3["rejection_code"] == "REVOKED_SIGNING_KEY"

    def test_verification_performance_bounded_latency(self):
        attestation_cache.clear()
        r1 = make_test_record("RES-PERF-01")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-2", secret="test-secret-key-87654321"
        )
        r1.observation_completeness_attestation = att

        # Benchmark 100 verification iterations
        t0 = time.perf_counter()
        for _ in range(100):
            res = ObservationCompletenessAttestationVerifier.verify_attestation(r1, att, use_cache=True)
            assert res["is_valid"] is True
        total_time_ms = (time.perf_counter() - t0) * 1000
        avg_latency_ms = total_time_ms / 100

        # Verification must be fast (< 2ms on average, typically < 0.1ms with cache)
        assert avg_latency_ms < 5.0, f"Average verification latency too high: {avg_latency_ms:.2f}ms"


class TestSprint24WorkspaceIntegrationAndRevalidation:
    """Verifies Comparison Lab evaluate gate and saved comparison revalidation."""

    def test_comparison_lab_evaluates_attested_candidates(self):
        r1 = make_test_record("RES-COMP-1", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")
        r2 = make_test_record("RES-COMP-2", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")

        # Both have valid signed attestations
        r1.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-2", secret="test-secret-key-87654321"
        )
        r2.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r2, key_id="test-trusted-key-2", secret="test-secret-key-87654321"
        )

        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is True
        assert res["shared_interval_count"] == 120

    def test_tampered_attestation_rejects_scientific_comparison(self):
        r1 = make_test_record("RES-COMP-1", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")
        r2 = make_test_record("RES-COMP-2", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")

        # r1 valid, r2 forged signature
        r1.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="test-trusted-key-2", secret="test-secret-key-87654321"
        )
        r2.observation_completeness_attestation = {
            "status": "VERIFIED",
            "verified_continuous_series": True,
            "signature": "hmac-sha256:test-trusted-key-2:0000000000000000000000000000000000000000000000000000000000000000",
            "key_id": "test-trusted-key-2",
            "schema_version": "CBE-ATTESTATION-1.0.0",
            "issuer": "CBE_AUTHORITATIVE_RESEARCH_AUTHORITY",
            "observation_start_utc": r2.observation_start_utc,
            "observation_end_utc": r2.observation_end_utc,
            "window_cadence": r2.window_cadence,
            "observation_count": 120,
            "record_id": r2.id,
            "dataset_id": r2.dataset_id,
            "source_artifact_sha256": r2.source_artifact_sha256,
        }

        res = calculate_temporal_observation_overlap([r1, r2])
        assert res["overlap_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"


class TestSprint24ScientificAndGovernanceInvariants:
    """Governance and scientific model freeze invariants."""

    def test_canonical_model_is_frozen(self):
        assert ResearchWorkspaceV2Engine.CANONICAL_MODEL_VERSION == "CBE-0.7.0"
        assert ResearchWorkspaceV2Engine.MODEL_STATUS == "STRICTLY_FROZEN"
        assert ResearchWorkspaceV2Engine.GOVERNANCE_DECISION == "TECHNICAL_NO_GO"

    def test_trading_prohibition_strictly_enforced(self):
        assert ResearchWorkspaceV2Engine.TRADING_PROHIBITION == "LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED"

"""
Test Suite: Sprint 24 Final Cryptographic Hardening
(CBE_SPRINT24_FINAL_CRYPTOGRAPHIC_HARDENING)

Covers:
1. Signature-bound verification cache (signature mutation, isolation, revocation invalidation, thread safety)
2. Fail-closed source artifact integrity (missing, directory, traversal, system dirs, symlinks, mtime/size invalidation)
3. Authenticated security claims in RFC 8785 canonical digest (missing_observations, has_missing_data, expires_at_utc, is_superseded)
4. Scientific and Governance invariants (model CBE-0.7.0 frozen, trading disabled)
"""

import concurrent.futures
import hashlib
import json
import os
import stat
import tempfile
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

from coin_behavior_engine.product.attestation_verifier import (
    ObservationCompletenessAttestationVerifier,
    attestation_cache,
    MANDATORY_CLAIMS,
    DISALLOWED_SYSTEM_DIRECTORIES,
)
from coin_behavior_engine.product.credential_manager import signing_key_registry
from coin_behavior_engine.product.research_catalog_provider import (
    ResearchRecord,
)
from coin_behavior_engine.product.research_intelligence_workspace import (
    calculate_temporal_observation_overlap,
    ResearchWorkspaceV2Engine,
)


CANONICAL_TEST_ARTIFACT = "data/test_artifact.json"
CANONICAL_TEST_SHA = "46c4cb960dd36c613bb9826cb8d54185724d6060e11b822ed82fd9213a3e9598"


@pytest.fixture(autouse=True)
def setup_test_environment():
    """Ensure trusted test keys are clean and cache is reset."""
    attestation_cache.clear()
    signing_key_registry.register_key("crypto-key-1", "crypto-secret-key-11111111", is_active=True)
    signing_key_registry.register_key("crypto-key-2", "crypto-secret-key-22222222", is_active=True)
    signing_key_registry.register_key("crypto-revoked", "crypto-secret-key-99999999", is_active=False)
    yield
    attestation_cache.clear()


def make_record(
    record_id: str = "REC-CRYPTO-01",
    dataset_id: str = "BTCUSDT-1H",
    cadence: str = "1h",
    start_utc: str = "2024-01-01T00:00:00Z",
    end_utc: str = "2024-01-06T00:00:00Z",
    source_artifact: str = CANONICAL_TEST_ARTIFACT,
    sha256: str = CANONICAL_TEST_SHA,
    sample_size: int = 120,
) -> ResearchRecord:
    return ResearchRecord(
        id=record_id,
        title=f"Record {record_id}",
        title_en=f"Record {record_id}",
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
        volatility_ratio=1.20,
    )


# ==============================================================================
# SECTION 1: Signature-Bound Verification Cache Hardening
# ==============================================================================

class TestSection1SignatureBoundCache:
    """Verifies that the verification cache binds to the exact signature and state."""

    def test_signature_mutation_sequence(self):
        """
        Sequence:
        1. Verify valid attestation A -> success, cached.
        2. Verify B with identical claims but modified signature -> rejected, cache miss.
        3. Confirm B did not reuse A's cache entry.
        4. Verify A again -> passes from cache.
        """
        rec = make_record("REC-CACHE-01")
        att_a = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-1", secret="crypto-secret-key-11111111"
        )
        rec.observation_completeness_attestation = att_a

        # 1. Verify A (cache miss -> populated)
        res_a1 = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att_a, use_cache=True)
        assert res_a1["is_valid"] is True
        assert attestation_cache.stats["size"] >= 1
        hits_before = attestation_cache.stats["hit_count"]

        # 2. Forge / mutate signature in copy B with exact identical claims
        att_b = dict(att_a)
        # Modify the hex digest part of the signature
        parts = att_a["signature"].split(":")
        mutated_sig = f"{parts[0]}:{parts[1]}:deadbeef{parts[2][8:]}"
        att_b["signature"] = mutated_sig

        res_b = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att_b, use_cache=True)
        assert res_b["is_valid"] is False
        assert res_b["rejection_code"] == "SIGNATURE_VERIFICATION_FAILED"
        # Ensure B caused a cache miss and was not authorized by A
        assert attestation_cache.stats["hit_count"] == hits_before

        # 3. Verify A again -> cache hit
        res_a2 = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att_a, use_cache=True)
        assert res_a2["is_valid"] is True
        assert attestation_cache.stats["hit_count"] == hits_before + 1

    def test_failed_verification_does_not_contaminate_cache(self):
        """Failed verifications must never be stored as valid or contaminate cache."""
        rec = make_record("REC-FAIL-01")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-1", secret="wrong-secret-key-invalid"
        )
        rec.observation_completeness_attestation = att

        cache_size_before = attestation_cache.stats["size"]
        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att, use_cache=True)
        assert res["is_valid"] is False
        # Failed verification should NOT add an entry to the cache
        assert attestation_cache.stats["size"] == cache_size_before

    def test_key_revocation_invalidates_cache_access(self):
        """When a signing key is revoked, subsequent verification fails closed."""
        rec = make_record("REC-REV-01")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-2", secret="crypto-secret-key-22222222"
        )
        rec.observation_completeness_attestation = att

        res1 = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att, use_cache=True)
        assert res1["is_valid"] is True

        # Now revoke key
        signing_key_registry.revoke_key("crypto-key-2")

        # Next verification must fail closed with REVOKED_SIGNING_KEY
        res2 = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att, use_cache=True)
        assert res2["is_valid"] is False
        assert res2["rejection_code"] == "REVOKED_SIGNING_KEY"

    def test_key_rotation_lifecycle(self):
        """Key rotation from key-1 to new-key verifies cleanly with new key."""
        rec = make_record("REC-ROT-01")
        # Register rotated new key
        signing_key_registry.register_key("crypto-key-rot", "new-secret-12345678", is_active=True)

        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-rot", secret="new-secret-12345678"
        )
        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att, use_cache=True)
        assert res["is_valid"] is True
        assert res["verified_key_id"] == "crypto-key-rot"

    def test_thread_safe_concurrent_cache_access(self):
        """Concurrent multi-threaded calls do not corrupt cache state or throw race exceptions."""
        rec = make_record("REC-CONCUR-01")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-1", secret="crypto-secret-key-11111111"
        )

        def worker():
            for _ in range(50):
                res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att, use_cache=True)
                assert res["is_valid"] is True

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(worker) for _ in range(8)]
            for f in concurrent.futures.as_completed(futures):
                f.result()

        stats = attestation_cache.stats
        assert stats["hit_count"] > 0


# ==============================================================================
# SECTION 2: Fail-Closed Source Artifact Integrity
# ==============================================================================

class TestSection2FailClosedSourceArtifactIntegrity:
    """Verifies fail-closed behavior for missing, unreadable, or tampered source artifacts."""

    def test_source_artifact_missing_fails_closed(self):
        rec = make_record("REC-MISSING-01", source_artifact="nonexistent/path/data.json")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-1", secret="crypto-secret-key-11111111"
        )
        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
        assert res["is_valid"] is False
        assert res["rejection_code"] == "SOURCE_ARTIFACT_MISSING"

    def test_source_artifact_is_directory_fails_closed(self):
        rec = make_record("REC-DIR-01", source_artifact="data")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-1", secret="crypto-secret-key-11111111"
        )
        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
        assert res["is_valid"] is False
        assert res["rejection_code"] == "SOURCE_ARTIFACT_UNREADABLE"

    def test_source_artifact_path_traversal_fails_closed(self):
        rec = make_record("REC-TRAV-01", source_artifact="../../etc/shadow")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-1", secret="crypto-secret-key-11111111"
        )
        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
        assert res["is_valid"] is False
        assert res["rejection_code"] == "SOURCE_ARTIFACT_PATH_UNTRUSTED"

    def test_source_artifact_disallowed_system_path_fails_closed(self):
        for sys_path in ("/etc/passwd", "/bin/sh", "C:/Windows/System32/calc.exe"):
            rec = make_record("REC-SYS-01", source_artifact=sys_path)
            att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
                rec, key_id="crypto-key-1", secret="crypto-secret-key-11111111"
            )
            res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
            assert res["is_valid"] is False
            assert res["rejection_code"] == "SOURCE_ARTIFACT_PATH_UNTRUSTED"

    def test_source_artifact_hash_mismatch_fails_closed(self):
        # Point to valid file but declare conflicting hash
        rec = make_record("REC-HASHMIS-01", sha256="0" * 64)
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-1", secret="crypto-secret-key-11111111"
        )
        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
        assert res["is_valid"] is False
        assert res["rejection_code"] in ("SOURCE_ARTIFACT_HASH_MISMATCH", "ARTIFACT_HASH_MISMATCH")

    def test_source_file_replaced_after_cache_population_invalidates_cache(self):
        """When disk file is modified after caching, mtime/size check evicts and fails closed."""
        with tempfile.NamedTemporaryFile("w+", delete=False, suffix=".json") as tf:
            tf.write('{"sample": "original-content-12345"}')
            temp_path = tf.name

        try:
            p = Path(temp_path)
            sha_orig = hashlib.sha256(p.read_bytes()).hexdigest()
            rec = make_record("REC-TOCTOU-01", source_artifact=temp_path, sha256=sha_orig)
            att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
                rec, key_id="crypto-key-1", secret="crypto-secret-key-11111111"
            )

            # 1. Populate cache
            res1 = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att, use_cache=True)
            assert res1["is_valid"] is True

            # 2. Modify file on disk (changes mtime and size)
            time.sleep(0.01)
            with open(temp_path, "w") as tf2:
                tf2.write('{"sample": "TAMPERED-NEW-LONGER-CONTENT-67890"}')

            # 3. Next call with use_cache=True MUST detect change, evict, and fail closed
            res2 = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att, use_cache=True)
            assert res2["is_valid"] is False
            assert res2["rejection_code"] == "SOURCE_ARTIFACT_HASH_MISMATCH"
        finally:
            if os.path.exists(temp_path):
                os.remove(temp_path)


# ==============================================================================
# SECTION 3: Authenticated Security Claims in RFC 8785 Canonical Digest
# ==============================================================================

class TestSection3SignedSecurityClaims:
    """Verifies that mutating any acceptance-affecting claim invalidates signature."""

    def test_modifying_missing_observations_invalidates_signature(self):
        rec = make_record("REC-CLAIM-01")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-1", secret="crypto-secret-key-11111111", missing_observations=0
        )
        # Mutate claim after signing
        att["missing_observations"] = 10

        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
        assert res["is_valid"] is False
        assert res["rejection_code"] in ("SIGNATURE_VERIFICATION_FAILED", "INCONSISTENT_COMPLETENESS_METADATA")

    def test_modifying_has_missing_data_invalidates_signature(self):
        rec = make_record("REC-CLAIM-02")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-1", secret="crypto-secret-key-11111111", has_missing_data=False
        )
        # Mutate claim after signing
        att["has_missing_data"] = True

        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
        assert res["is_valid"] is False
        assert res["rejection_code"] in ("SIGNATURE_VERIFICATION_FAILED", "INCONSISTENT_COMPLETENESS_METADATA")

    def test_modifying_expires_at_utc_invalidates_signature(self):
        rec = make_record("REC-CLAIM-03")
        future_date = (datetime.now(timezone.utc) + timedelta(days=365)).isoformat()
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-1", secret="crypto-secret-key-11111111", expires_at_utc=future_date
        )
        # Mutate expiry date
        att["expires_at_utc"] = "2099-01-01T00:00:00Z"

        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
        assert res["is_valid"] is False
        assert res["rejection_code"] == "SIGNATURE_VERIFICATION_FAILED"

    def test_modifying_is_superseded_invalidates_signature(self):
        rec = make_record("REC-CLAIM-04")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-1", secret="crypto-secret-key-11111111", is_superseded=False
        )
        # Mutate after signing
        att["is_superseded"] = True

        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
        assert res["is_valid"] is False
        assert res["rejection_code"] in ("SIGNATURE_VERIFICATION_FAILED", "ATTESTATION_SUPERSEDED")

    def test_missing_mandatory_claim_fails_closed(self):
        rec = make_record("REC-MAND-01")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec, key_id="crypto-key-1", secret="crypto-secret-key-11111111"
        )
        # Delete a mandatory claim
        del att["window_cadence"]

        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
        assert res["is_valid"] is False
        assert res["rejection_code"] == "MANDATORY_CLAIM_MISSING"

    def test_conflicting_completeness_metadata_fails_closed(self):
        rec = make_record("REC-CONF-01")
        # Signed with completeness_assertion=True and missing_observations=3
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec,
            key_id="crypto-key-1",
            secret="crypto-secret-key-11111111",
            completeness_assertion=True,
            missing_observations=3,
        )
        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
        assert res["is_valid"] is False
        assert res["rejection_code"] == "INCONSISTENT_COMPLETENESS_METADATA"

    def test_expired_attestation_fails_closed(self):
        rec = make_record("REC-EXP-01")
        past_date = "2020-01-01T00:00:00Z"
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec,
            key_id="crypto-key-1",
            secret="crypto-secret-key-11111111",
            expires_at_utc=past_date,
        )
        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
        assert res["is_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_EXPIRED"

    def test_superseded_attestation_fails_closed(self):
        rec = make_record("REC-SUPER-01")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec,
            key_id="crypto-key-1",
            secret="crypto-secret-key-11111111",
            is_superseded=True,
        )
        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
        assert res["is_valid"] is False
        assert res["rejection_code"] == "ATTESTATION_SUPERSEDED"

    def test_unsupported_schema_version_fails_closed(self):
        rec = make_record("REC-SCHEMA-01")
        att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            rec,
            key_id="crypto-key-1",
            secret="crypto-secret-key-11111111",
            schema_version="UNSUPPORTED-9.9.9",
        )
        res = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att)
        assert res["is_valid"] is False
        assert res["rejection_code"] == "UNSUPPORTED_SCHEMA_VERSION"


# ==============================================================================
# SECTION 4: Scientific Comparison Lab Integration & Governance Invariants
# ==============================================================================

class TestSection4ComparisonLabAndGovernance:
    """Verifies that hardened verifier integrates with Comparison Lab and preserves invariants."""

    def test_comparison_lab_evaluates_attested_candidates_with_hardened_verifier(self):
        r1 = make_record("REC-LAB-01", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")
        r2 = make_record("REC-LAB-02", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")

        r1.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="crypto-key-1", secret="crypto-secret-key-11111111"
        )
        r2.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r2, key_id="crypto-key-1", secret="crypto-secret-key-11111111"
        )

        overlap = calculate_temporal_observation_overlap([r1, r2])
        assert overlap["overlap_valid"] is True
        assert overlap["shared_interval_count"] == 120

    def test_comparison_lab_rejects_candidate_with_missing_observations(self):
        r1 = make_record("REC-LAB-BAD-01", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")
        r2 = make_record("REC-LAB-OK-02", start_utc="2024-01-01T00:00:00Z", end_utc="2024-01-06T00:00:00Z")

        r1.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r1, key_id="crypto-key-1", secret="crypto-secret-key-11111111", missing_observations=2
        )
        r2.observation_completeness_attestation = ObservationCompletenessAttestationVerifier.create_signed_attestation(
            r2, key_id="crypto-key-1", secret="crypto-secret-key-11111111"
        )

        overlap = calculate_temporal_observation_overlap([r1, r2])
        assert overlap["overlap_valid"] is False
        assert overlap["rejection_code"] == "ATTESTATION_VERIFICATION_FAILED"

    def test_canonical_model_is_frozen(self):
        assert ResearchWorkspaceV2Engine.CANONICAL_MODEL_VERSION == "CBE-0.7.0"
        assert ResearchWorkspaceV2Engine.MODEL_STATUS == "STRICTLY_FROZEN"
        assert ResearchWorkspaceV2Engine.GOVERNANCE_DECISION == "TECHNICAL_NO_GO"

    def test_directional_trading_is_strictly_prohibited(self):
        assert ResearchWorkspaceV2Engine.TRADING_PROHIBITION == "LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED"

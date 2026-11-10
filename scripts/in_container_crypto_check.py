"""
In-container cryptographic verification script for staging container 2a68fded2156.
"""

from coin_behavior_engine.product.attestation_verifier import (
    ObservationCompletenessAttestationVerifier,
    attestation_cache,
    MANDATORY_CLAIMS,
)
from coin_behavior_engine.product.credential_manager import signing_key_registry
from coin_behavior_engine.product.research_catalog_provider import ResearchRecord
from coin_behavior_engine.product.research_intelligence_workspace import (
    calculate_temporal_observation_overlap,
    ResearchWorkspaceV2Engine,
)


def run_in_container_verification():
    print("Testing Invariants...")
    assert ResearchWorkspaceV2Engine.CANONICAL_MODEL_VERSION == "CBE-0.7.0"
    assert ResearchWorkspaceV2Engine.MODEL_STATUS == "STRICTLY_FROZEN"
    assert ResearchWorkspaceV2Engine.GOVERNANCE_DECISION == "TECHNICAL_NO_GO"
    assert ResearchWorkspaceV2Engine.TRADING_PROHIBITION == "LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED"
    print("[PASS] Invariants strictly frozen.")

    # Setup keys
    attestation_cache.clear()
    signing_key_registry.register_key("test-incontainer-key-1", "secret-test-incontainer-1234", is_active=True)

    rec = ResearchRecord(
        id="REC-CONT-01",
        title="Test Record",
        title_en="Test Record",
        category="Volatilite",
        dataset_id="BTCUSDT-1H",
        historical_period="2024",
        window_cadence="1h",
        specification_id="SP-REC-CONT-01",
        observation_start_utc="2024-01-01T00:00:00Z",
        observation_end_utc="2024-01-06T00:00:00Z",
        observation_interval_count=120,
        source_artifact="data/test_artifact.json",
        source_artifact_sha256="46c4cb960dd36c613bb9826cb8d54185724d6060e11b822ed82fd9213a3e9598",
        sample_size=120,
        volatility_ratio=1.20,
    )

    # 1. Create valid attestation
    att = ObservationCompletenessAttestationVerifier.create_signed_attestation(
        rec, key_id="test-incontainer-key-1", secret="secret-test-incontainer-1234"
    )

    # 2. Verify valid attestation -> should populate cache
    res1 = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att, use_cache=True)
    assert res1["is_valid"] is True
    print("[PASS] Valid attestation verified successfully.")

    # 3. Signature mutation test: modified signature on identical claims MUST cause cache miss and fail
    att_mutated = dict(att)
    parts = att["signature"].split(":")
    att_mutated["signature"] = f"{parts[0]}:{parts[1]}:bad00000{parts[2][8:]}"
    res_mut = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att_mutated, use_cache=True)
    assert res_mut["is_valid"] is False
    assert res_mut["rejection_code"] == "SIGNATURE_VERIFICATION_FAILED"
    print("[PASS] Mutated signature rejected (fail-closed, no cache leak).")

    # 4. Modifying missing_observations MUST invalidate signature
    att_claim_mut = dict(att)
    att_claim_mut["missing_observations"] = 5
    res_claim = ObservationCompletenessAttestationVerifier.verify_attestation(rec, att_claim_mut, use_cache=False)
    assert res_claim["is_valid"] is False
    print("[PASS] Modified missing_observations rejected.")

    # 5. Missing source file fail closed
    rec_bad_file = ResearchRecord(
        id="REC-BAD-01",
        title="Bad File",
        title_en="Bad File",
        category="Volatilite",
        dataset_id="BTCUSDT-1H",
        historical_period="2024",
        window_cadence="1h",
        specification_id="SP-01",
        observation_start_utc="2024-01-01T00:00:00Z",
        observation_end_utc="2024-01-06T00:00:00Z",
        observation_interval_count=120,
        source_artifact="data/nonexistent_file_12345.json",
        source_artifact_sha256="46c4cb960dd36c613bb9826cb8d54185724d6060e11b822ed82fd9213a3e9598",
        sample_size=120,
        volatility_ratio=1.20,
    )
    att_bad = ObservationCompletenessAttestationVerifier.create_signed_attestation(
        rec_bad_file, key_id="test-incontainer-key-1", secret="secret-test-incontainer-1234"
    )
    res_bad = ObservationCompletenessAttestationVerifier.verify_attestation(rec_bad_file, att_bad, use_cache=False)
    assert res_bad["is_valid"] is False
    assert res_bad["rejection_code"] == "SOURCE_ARTIFACT_MISSING"
    print("[PASS] Missing source artifact failed closed.")

    print("\nALL IN-CONTAINER CRYPTOGRAPHIC CHECKS PASSED.")


if __name__ == "__main__":
    run_in_container_verification()

"""
Sprint 11.23.2 Phase 5: Evidence Integrity Hardening & Research Revalidation Test Suite
Executes comprehensive executable tests covering:
1. Blockchain block hash vs source document SHA-256 separation and rejection of fake hashes.
2. Actual source document byte-level validation from local filesystem.
3. Rejection and quarantine of all 236 unarchived external events.
4. Independent reconstruction of control blackout windows and detection of prohibited overlaps.
5. Safe candle timestamp alignment and zero intra-candle close leakage.
6. Permutation p-value finite-sample correction bounds: p >= 1 / (N + 1).
7. Stale hardcoded numerical conclusion detection across text and tables.
8. Complete bar of quarantined events from directional trading signals.
9. Family-wise Benjamini-Hochberg FDR correction on macro surprise regressions.
10. Market candle continuity audit across 499,376 5-minute bars.
"""

import hashlib
import json
from pathlib import Path
import re
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research.canonical_event_verifier import (
    CanonicalEventVerifier,
    CanonicalVerificationStatus
)

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = ROOT_DIR / "research_outputs"

HALVING_BLOCK_HASH = "0000000000000000000320283a032748cef8227873ff4872689bf23f1cda83a5"
HALVING_BLOCK_HEIGHT = 840000
HALVING_PROOF_PATH = "data/macro_events/evidence_artifacts/bitcoin_block_840000_proof.json"

# ---------------------------------------------------------------------------
# TEST 1: Blockchain Block Hash Distinct from Source Document Hash
# ---------------------------------------------------------------------------
def test_01_blockchain_block_hash_distinct_from_document_hash():
    """Verifies that on-chain consensus hash and local file SHA-256 are distinct fields."""
    p = OUTPUTS_DIR / "canonical_event_verification_11_23_2.parquet"
    df = pd.read_parquet(p)
    halving = df[df["event_category"] == "BITCOIN_PROTOCOL"].iloc[0]

    # Block hash is PoW target hash
    assert halving["blockchain_block_hash"] == HALVING_BLOCK_HASH
    assert halving["blockchain_block_height"] == HALVING_BLOCK_HEIGHT

    # Source document hash is SHA-256 of physical proof file on disk
    doc_hash = halving["source_document_sha256"]
    assert doc_hash is not None
    assert doc_hash != HALVING_BLOCK_HASH
    assert len(doc_hash) == 64

    # Verify CanonicalEventVerifier validates true block and rejects fake block
    assert CanonicalEventVerifier.verify_blockchain_block(HALVING_BLOCK_HASH, HALVING_BLOCK_HEIGHT) is True
    fake_hash = "1111111111111111111111111111111111111111111111111111111111111111"
    assert CanonicalEventVerifier.verify_blockchain_block(fake_hash, HALVING_BLOCK_HEIGHT) is False

# ---------------------------------------------------------------------------
# TEST 2: Byte-Level Source Document Validation
# ---------------------------------------------------------------------------
def test_02_byte_level_source_document_validation():
    """Validates physical file bytes on disk and rejects missing or tampered files."""
    proof_file = ROOT_DIR / HALVING_PROOF_PATH
    assert proof_file.exists()

    with open(proof_file, "rb") as f:
        bytes_data = f.read()
    expected_sha256 = hashlib.sha256(bytes_data).hexdigest()

    # Valid byte check
    assert CanonicalEventVerifier.verify_document_bytes(proof_file, expected_sha256) is True

    # Tampered byte check
    corrupt_sha256 = "0000000000000000000000000000000000000000000000000000000000000000"
    assert CanonicalEventVerifier.verify_document_bytes(proof_file, corrupt_sha256) is False

    # Missing file check
    missing_file = ROOT_DIR / "non_existent_artifact_file.json"
    assert CanonicalEventVerifier.verify_document_bytes(missing_file, expected_sha256) is False

# ---------------------------------------------------------------------------
# TEST 3: Rejection and Quarantine of Unarchived External Events
# ---------------------------------------------------------------------------
def test_03_rejection_and_quarantine_of_unarchived_external_events():
    """Confirms all 236 external events have no byte validation and remain quarantined."""
    p = OUTPUTS_DIR / "canonical_event_verification_11_23_2.parquet"
    df = pd.read_parquet(p)
    external = df[df["event_category"] != "BITCOIN_PROTOCOL"]
    assert len(external) == 236

    for _, row in external.iterrows():
        assert row["source_document_bytes_verified"] is False
        assert row["source_document_sha256"] is None or pd.isna(row["source_document_sha256"])
        assert row["source_document_status"] == "SOURCE_UNAVAILABLE"
        assert row["canonical_verification_status"] in [
            CanonicalVerificationStatus.OFFICIAL_SCHEDULE_ONLY.value,
            CanonicalVerificationStatus.SECONDARY_TIMESTAMP_ONLY.value
        ]
        assert row["quarantine_reason"] is not None

# ---------------------------------------------------------------------------
# TEST 4: Reconstruct Control Blackout Windows and Detect Prohibited Overlaps
# ---------------------------------------------------------------------------
def test_04_control_blackout_window_overlap_detection():
    """Reconstructs the ±24h blackout window and asserts zero overlap for matched controls."""
    p_elig = OUTPUTS_DIR / "causal_event_eligibility_11_23_2.parquet"
    df_elig = pd.read_parquet(p_elig)
    event_indices = df_elig["safe_candle_idx"].dropna().astype(int).values

    # Reconstruct blackout set: ±288 bars around each event
    blackout_bars = set()
    for e_idx in event_indices:
        blackout_bars.update(range(e_idx - 288, e_idx + 288 + 1))

    p_ctrl = OUTPUTS_DIR / "matched_event_controls_11_23_2.parquet"
    df_ctrl = pd.read_parquet(p_ctrl)
    assert len(df_ctrl) == 231

    overlap_count = 0
    for _, row in df_ctrl.iterrows():
        c_idx = int(row["matched_control_candle_idx"])
        # Control's evaluation window: [c_idx, c_idx + 288]
        window = range(c_idx, c_idx + 288)
        if any(bar in blackout_bars for bar in window):
            overlap_count += 1

    assert overlap_count == 0, f"Found {overlap_count} controls overlapping with event blackout windows!"

    # Synthetic overlap test: injecting a candle inside blackout window must be detected
    synthetic_contaminated_candle = event_indices[0] + 10
    is_contaminated = any(bar in blackout_bars for bar in range(synthetic_contaminated_candle, synthetic_contaminated_candle + 288))
    assert is_contaminated is True

# ---------------------------------------------------------------------------
# TEST 5: Safe Candle Timestamp Alignment and Zero Intra-Candle Leakage
# ---------------------------------------------------------------------------
def test_05_timestamp_alignment_and_zero_intra_candle_leakage():
    """Confirms execution candles open strictly after t_pub + uncertainty with 0 leakage."""
    p_elig = OUTPUTS_DIR / "causal_event_eligibility_11_23_2.parquet"
    df_elig = pd.read_parquet(p_elig)

    for _, row in df_elig.iterrows():
        t_pub = pd.to_datetime(row["official_published_at_utc"])
        unc = row["publication_timestamp_uncertainty_seconds"]
        t_safe = pd.to_datetime(row["research_available_at_utc"])

        # Causal property: research safe availability must be at or after t_pub + uncertainty
        min_safe = t_pub + pd.Timedelta(seconds=unc)
        assert t_safe >= min_safe

        if pd.notna(row["safe_candle_open_utc"]):
            c_open = pd.to_datetime(row["safe_candle_open_utc"])
            assert c_open >= t_safe

    assert df_elig["intra_candle_close_leakage"].sum() == 0

# ---------------------------------------------------------------------------
# TEST 6: Finite-Sample Permutation Test Correction Bounds
# ---------------------------------------------------------------------------
def test_06_finite_sample_permutation_p_value_bounds():
    """Verifies permutation p-value includes finite sample correction (k + 1)/(N + 1) >= 1/(N+1)."""
    p_audit = OUTPUTS_DIR / "statistical_revalidation_11_23_2.json"
    with open(p_audit, "r", encoding="utf-8") as f:
        data = json.load(f)

    stats = data["statistical_revalidation_metrics"]["full_sample"]
    n_perms = stats["permutation_samples"]
    perm_p = stats["permutation_p_value"]

    min_possible_p = 1.0 / (n_perms + 1)
    assert perm_p >= min_possible_p
    assert perm_p > 0.0

    # Cluster heads and isolated sensitivity p-values
    for key in ["cluster_heads_sensitivity", "isolated_singletons_sensitivity"]:
        sub_stats = data["statistical_revalidation_metrics"][key]
        n_sub = sub_stats["permutation_samples"]
        p_sub = sub_stats["permutation_p_value"]
        assert p_sub >= 1.0 / (n_sub + 1)
        assert p_sub > 0.0

# ---------------------------------------------------------------------------
# TEST 7: Stale Hardcoded Numerical Conclusion Detector
# ---------------------------------------------------------------------------
def test_07_stale_hardcoded_numerical_conclusion_detector():
    """
    Parses conclusion strings and confirms all cited statistics match calculated metrics.
    Detects and rejects obsolete hardcoded text (e.g. 0.363% vs 0.230%).
    """
    p_audit = OUTPUTS_DIR / "statistical_revalidation_11_23_2.json"
    with open(p_audit, "r", encoding="utf-8") as f:
        data = json.load(f)

    conclusions = data["scientific_conclusions"]
    stats_full = data["statistical_revalidation_metrics"]["full_sample"]

    mean_e = stats_full["mean_event_15m_abs_return_pct"]
    mean_c = stats_full["mean_matched_control_15m_abs_return_pct"]
    mult = stats_full["volatility_expansion_multiplier"]
    reversal = data["statistical_revalidation_metrics"]["directional_behavior"]["reversal_rate_24h_pct"]

    # Check Conclusion 1
    c1 = conclusions[0]
    # Must contain actual calculated values
    assert f"{mean_e:.3f}%" in c1
    assert f"{mean_c:.3f}%" in c1
    assert f"{mult:.2f}x" in c1

    # Must NOT contain obsolete Sprint 11.23 hardcoded strings
    assert "0.363%" not in c1
    assert "0.230%" not in c1
    assert "1.38x" not in c1

    # Check Conclusion 3: reversal rate
    c3 = conclusions[2]
    assert f"{reversal:.1f}%" in c3
    assert "43.0%" not in c3 # obsolete number from 11.23

# ---------------------------------------------------------------------------
# TEST 8: Quarantined Events Barred from Directional Trading Signals
# ---------------------------------------------------------------------------
def test_08_quarantined_events_barred_from_directional_trading():
    """Asserts that directional trading eligibility is strictly False for all 237 events."""
    p_canon = OUTPUTS_DIR / "canonical_event_verification_11_23_2.parquet"
    df_canon = pd.read_parquet(p_canon)
    assert df_canon["directional_trading_eligible"].sum() == 0

    p_elig = OUTPUTS_DIR / "causal_event_eligibility_11_23_2.parquet"
    df_elig = pd.read_parquet(p_elig)
    assert df_elig["directional_trading_eligible"].sum() == 0

    p_causal = OUTPUTS_DIR / "causal_safety_audit_11_23_2.json"
    with open(p_causal, "r", encoding="utf-8") as f:
        audit = json.load(f)
    assert audit["causal_safety_metrics"]["directional_trading_eligible_events"] == 0
    assert audit["causal_safety_metrics"]["directional_trading_quarantine_rate_pct"] == 100.0

# ---------------------------------------------------------------------------
# TEST 9: Macro Surprise Hypothesis Family Benjamini-Hochberg FDR
# ---------------------------------------------------------------------------
def test_09_macro_surprise_hypothesis_family_fdr():
    """Verifies that multiple-testing correction is evaluated within distinct hypothesis families."""
    p_audit = OUTPUTS_DIR / "statistical_revalidation_11_23_2.json"
    with open(p_audit, "r", encoding="utf-8") as f:
        data = json.load(f)

    families = data["macro_surprise_audit"]["hypothesis_families"]
    assert "family_1_macro_surprise_to_15m_return" in families
    assert "family_2_macro_surprise_to_24h_return" in families

    f1 = families["family_1_macro_surprise_to_15m_return"]
    assert f1["hypotheses_evaluated"] == 4
    assert f1["statistically_significant_count"] == 0

    f2 = families["family_2_macro_surprise_to_24h_return"]
    assert f2["hypotheses_evaluated"] == 4
    assert f2["statistically_significant_count"] == 0

# ---------------------------------------------------------------------------
# TEST 10: Market Candle Continuity Audit
# ---------------------------------------------------------------------------
def test_10_market_candle_continuity_audit():
    """Verifies multiyear 5m candle continuity audit across 499,376 bars."""
    p_audit = OUTPUTS_DIR / "statistical_revalidation_11_23_2.json"
    with open(p_audit, "r", encoding="utf-8") as f:
        data = json.load(f)

    mkt = data["market_data_continuity_audit"]
    assert mkt["total_5m_bars"] == 499376
    assert mkt["non_5m_transitions"] == 1
    assert mkt["continuity_pct"] > 99.99
    assert mkt["known_maintenance_windows"][0]["duration_minutes"] == 85

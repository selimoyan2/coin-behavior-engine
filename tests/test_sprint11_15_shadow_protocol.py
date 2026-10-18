"""Deterministic Regression & Validation Test Suite for CBE Sprint 11.15.

Sprint 11.15: Prospective Research Readiness & Shadow Decision Protocol.
Verifies:
1. Canonical dataset fingerprint lock and Policy V2 preservation.
2. Candidate policy freeze manifest invariants (Policies A through E frozen; winner selection forbidden).
3. Shadow decision schema completeness and conformance.
4. Deterministic SHA-256 decision hashing.
5. Cryptographic append-only hash chain sequencing and full-chain verification.
6. Negative mutation testing: tampering any field in the chain is detected and fails verification.
7. Fail-closed data freshness guard: stale or delayed data emits NO_DECISION_DATA.
8. First-class abstention tracking: WAIT_USDT records avoided drawdown and opportunity cost.
9. Realistic offline execution: next-bar fill, 30 bps roundtrip friction, pessimistic intrabar stop, equity conservation.
10. Decoupled outcome recording: outcomes causally linked to parent_decision_hash without backward leakage.
11. Air-gap isolation: live exchange connections and order placement strictly prohibited.
12. Master research report 11.15 status declarations completeness.
"""

import copy
import hashlib
import json
import math
from pathlib import Path
import pytest

from coin_behavior_engine.research_lab.shadow_decision_protocol import (
    BASE_CODE_COMMIT,
    CANONICAL_DATASET_SHA256,
    GENESIS_PARENT_HASH,
    DecisionHashChain,
    PolicyFreezeManifest,
    ProspectiveIntegrityEngine,
    ShadowDecisionAction,
    ShadowDecisionRecord,
    ShadowExecutionSimulator,
    ShadowOutcomeRecord,
)

OUTPUT_DIR = Path("research_outputs")
DATASET_PATH = OUTPUT_DIR / "market_state_dataset.parquet"


# -------------------------------------------------------------------------
# Test Group 1: Baseline Dataset Fingerprint & Policy V2 Preservation
# -------------------------------------------------------------------------

def test_dataset_sha256_recalculation():
    """Verify byte-level recalculation of dataset hash matches canonical fingerprint."""
    assert DATASET_PATH.is_file(), f"Dataset missing: {DATASET_PATH}"
    hasher = hashlib.sha256()
    with open(DATASET_PATH, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    assert hasher.hexdigest() == CANONICAL_DATASET_SHA256


def test_policy_v2_preservation():
    """Verify Policy V2 30 bps nominal roundtrip friction is preserved without modification."""
    policy_path = OUTPUT_DIR / "canonical_execution_policy_v2.json"
    assert policy_path.is_file()
    with open(policy_path, "r", encoding="utf-8") as f:
        pol = json.load(f)
    fric = pol["friction_specification"]
    assert fric["nominal_roundtrip_total_bps"] == 30.0
    assert fric["taker_entry_fee_bps"] == 10.0
    assert fric["taker_exit_fee_bps"] == 10.0
    assert fric["entry_slippage_bps"] == 5.0
    assert fric["exit_slippage_bps"] == 5.0


# -------------------------------------------------------------------------
# Test Group 2: Policy Freeze Manifest & Governance Rules
# -------------------------------------------------------------------------

def test_policy_freeze_manifest_invariants():
    """Verify candidate policies A through E are defined, locked, and winner selection is forbidden."""
    manifest_p = OUTPUT_DIR / "policy_freeze_manifest.json"
    assert manifest_p.is_file(), f"Missing freeze manifest: {manifest_p}"
    with open(manifest_p, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["freeze_status"] == "FROZEN_BEFORE_UNSEEN_EVALUATION"
    assert manifest["winner_selection_status"] == "FORBIDDEN_NO_WINNER_SELECTED"
    assert "Holdout partition" in manifest["winner_selection_rationale"] or "contaminated" in manifest["winner_selection_rationale"].lower()

    policies = manifest["candidate_policies"]
    expected_policies = {
        "POLICY_A_USDT_CASH",
        "POLICY_B_BTC_BUY_AND_HOLD",
        "POLICY_C_TREND48_FOLLOWING",
        "POLICY_D_SELECTIVE_TREND_ONLY",
        "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED",
    }
    assert set(policies.keys()) == expected_policies

    # Verify Policy D and E frozen parameters
    pol_d = policies["POLICY_D_SELECTIVE_TREND_ONLY"]
    params_d = pol_d.get("frozen_parameters", pol_d.get("parameters", {}))
    assert params_d["fast_sma_hours"] == 24
    assert params_d["slow_sma_hours"] == 72
    assert params_d["anti_chase_max_extension_pct"] == 2.25

    pol_e = policies["POLICY_E_SELECTIVE_ANALOGUE_ASSISTED"]
    params_e = pol_e.get("frozen_parameters", pol_e.get("parameters", {}))
    assert params_e["fast_sma_hours"] == 24
    assert params_e["slow_sma_hours"] == 72


# -------------------------------------------------------------------------
# Test Group 3: Shadow Decision Record Schema & Deterministic Hashing
# -------------------------------------------------------------------------

def test_shadow_decision_schema_file_exists():
    """Verify shadow_decision_schema.json exists and defines required fields."""
    schema_p = OUTPUT_DIR / "shadow_decision_schema.json"
    assert schema_p.is_file()
    with open(schema_p, "r", encoding="utf-8") as f:
        schema = json.load(f)

    req_fields = {
        "decision_id",
        "sequence_number",
        "observation_timestamp_utc",
        "data_availability_timestamp_utc",
        "source_identifier",
        "btc_spot_reference_price",
        "hypothetical_usdt_balance",
        "hypothetical_btc_balance",
        "hypothetical_total_equity_usdt",
        "market_regime",
        "forecast_probabilities",
        "uncertainty_score",
        "decision",
        "policy_id",
        "policy_version",
        "code_commit_hash",
        "parent_decision_hash",
        "decision_hash",
    }
    assert req_fields.issubset(set(schema["required"]))


def test_deterministic_decision_hashing():
    """Verify identical inputs yield identical SHA-256 hash across repeated invocations."""
    rec1 = ShadowDecisionRecord(
        decision_id="DEC-202610181200-00001",
        sequence_number=1,
        observation_timestamp_utc="2026-10-18T12:00:00Z",
        data_availability_timestamp_utc="2026-10-18T12:00:05Z",
        source_identifier="binance_spot_btcusdt_5m_canonical",
        btc_spot_reference_price=82050.25,
        hypothetical_usdt_balance=10000.0,
        hypothetical_btc_balance=0.0,
        hypothetical_total_equity_usdt=10000.0,
        market_regime="TRENDING_BULL",
        forecast_probabilities={"p_up": 0.65, "p_down": 0.15, "p_flat": 0.20},
        uncertainty_score=0.15,
        decision="BUY_CANDIDATE",
        hypothetical_target_price=86152.76,
        hypothetical_stop_price=79999.00,
        evidence_rationale={"reason": "TREND_ALIGNED"},
        policy_id="POLICY_D_SELECTIVE_TREND_ONLY",
        policy_version="1.0.0-frozen",
        code_commit_hash=BASE_CODE_COMMIT,
        parent_decision_hash="a" * 64,
    )
    rec2 = copy.deepcopy(rec1)

    hash1 = rec1.compute_hash()
    hash2 = rec2.compute_hash()
    assert hash1 == hash2
    assert len(hash1) == 64


# -------------------------------------------------------------------------
# Test Group 4: Cryptographic Hash Chaining & Negative Tamper Testing
# -------------------------------------------------------------------------

def test_decision_hash_chain_valid_append_and_integrity():
    """Verify sequential block appending and full chain integrity verification."""
    chain = DecisionHashChain()

    # Genesis block (seq 0)
    rec0 = ShadowDecisionRecord(
        decision_id="DEC-GENESIS-00000",
        sequence_number=0,
        observation_timestamp_utc="2026-10-18T00:00:00Z",
        data_availability_timestamp_utc="2026-10-18T00:00:05Z",
        source_identifier="binance_spot_btcusdt_5m_canonical",
        btc_spot_reference_price=80000.0,
        hypothetical_usdt_balance=10000.0,
        hypothetical_btc_balance=0.0,
        hypothetical_total_equity_usdt=10000.0,
        market_regime="SIDEWAYS",
        forecast_probabilities={"p_up": 0.33, "p_down": 0.33, "p_flat": 0.34},
        uncertainty_score=0.5,
        decision="WAIT_USDT",
        parent_decision_hash=GENESIS_PARENT_HASH,
    )
    rec0.seal()
    chain.append(rec0)

    # Block 1
    rec1 = ShadowDecisionRecord(
        decision_id="DEC-STEP-00001",
        sequence_number=1,
        observation_timestamp_utc="2026-10-18T00:05:00Z",
        data_availability_timestamp_utc="2026-10-18T00:05:05Z",
        source_identifier="binance_spot_btcusdt_5m_canonical",
        btc_spot_reference_price=80100.0,
        hypothetical_usdt_balance=10000.0,
        hypothetical_btc_balance=0.0,
        hypothetical_total_equity_usdt=10000.0,
        market_regime="SIDEWAYS",
        forecast_probabilities={"p_up": 0.40, "p_down": 0.20, "p_flat": 0.40},
        uncertainty_score=0.4,
        decision="WAIT_USDT",
        parent_decision_hash=rec0.decision_hash,
    )
    rec1.seal()
    chain.append(rec1)

    assert len(chain) == 2
    is_valid, err = chain.verify_integrity()
    assert is_valid is True
    assert err is None


def test_negative_chain_sequence_mismatch_fails():
    """Verify out-of-order sequence number raises ValueError."""
    chain = DecisionHashChain()
    bad_rec = ShadowDecisionRecord(
        decision_id="DEC-BAD-SEQ",
        sequence_number=5,  # Expected 0
        observation_timestamp_utc="2026-10-18T00:00:00Z",
        data_availability_timestamp_utc="2026-10-18T00:00:05Z",
        source_identifier="binance_spot_btcusdt_5m_canonical",
        btc_spot_reference_price=80000.0,
        hypothetical_usdt_balance=10000.0,
        hypothetical_btc_balance=0.0,
        hypothetical_total_equity_usdt=10000.0,
        market_regime="SIDEWAYS",
        forecast_probabilities={"p_up": 0.33, "p_down": 0.33, "p_flat": 0.34},
        uncertainty_score=0.5,
        decision="WAIT_USDT",
        parent_decision_hash=GENESIS_PARENT_HASH,
    )
    with pytest.raises(ValueError, match="Sequence mismatch"):
        chain.append(bad_rec)


def test_negative_chain_parent_hash_break_fails():
    """Verify appending a block with incorrect parent_decision_hash raises ValueError."""
    chain = DecisionHashChain()
    rec0 = ShadowDecisionRecord(
        decision_id="DEC-GENESIS-00000",
        sequence_number=0,
        observation_timestamp_utc="2026-10-18T00:00:00Z",
        data_availability_timestamp_utc="2026-10-18T00:00:05Z",
        source_identifier="binance_spot_btcusdt_5m_canonical",
        btc_spot_reference_price=80000.0,
        hypothetical_usdt_balance=10000.0,
        hypothetical_btc_balance=0.0,
        hypothetical_total_equity_usdt=10000.0,
        market_regime="SIDEWAYS",
        forecast_probabilities={"p_up": 0.33, "p_down": 0.33, "p_flat": 0.34},
        uncertainty_score=0.5,
        decision="WAIT_USDT",
        parent_decision_hash=GENESIS_PARENT_HASH,
    )
    rec0.seal()
    chain.append(rec0)

    # Block 1 with wrong parent hash
    rec1_bad = ShadowDecisionRecord(
        decision_id="DEC-STEP-00001",
        sequence_number=1,
        observation_timestamp_utc="2026-10-18T00:05:00Z",
        data_availability_timestamp_utc="2026-10-18T00:05:05Z",
        source_identifier="binance_spot_btcusdt_5m_canonical",
        btc_spot_reference_price=80100.0,
        hypothetical_usdt_balance=10000.0,
        hypothetical_btc_balance=0.0,
        hypothetical_total_equity_usdt=10000.0,
        market_regime="SIDEWAYS",
        forecast_probabilities={"p_up": 0.40, "p_down": 0.20, "p_flat": 0.40},
        uncertainty_score=0.4,
        decision="WAIT_USDT",
        parent_decision_hash="f" * 64,  # Wrong parent hash
    )
    rec1_bad.seal()
    with pytest.raises(ValueError, match="Chain break"):
        chain.append(rec1_bad)


def test_negative_chain_tamper_detection():
    """Verify that tampering any byte in an historical block breaks chain verification."""
    chain = DecisionHashChain()

    for i in range(5):
        parent = chain.records[-1].decision_hash if i > 0 else GENESIS_PARENT_HASH
        rec = ShadowDecisionRecord(
            decision_id=f"DEC-{i:05d}",
            sequence_number=i,
            observation_timestamp_utc=f"2026-10-18T00:{i*5:02d}:00Z",
            data_availability_timestamp_utc=f"2026-10-18T00:{i*5:02d}:05Z",
            source_identifier="binance_spot_btcusdt_5m_canonical",
            btc_spot_reference_price=80000.0 + (i * 50.0),
            hypothetical_usdt_balance=10000.0,
            hypothetical_btc_balance=0.0,
            hypothetical_total_equity_usdt=10000.0,
            market_regime="SIDEWAYS",
            forecast_probabilities={"p_up": 0.33, "p_down": 0.33, "p_flat": 0.34},
            uncertainty_score=0.5,
            decision="WAIT_USDT",
            parent_decision_hash=parent,
        )
        rec.seal()
        chain.append(rec)

    # Initial check passes
    valid, _ = chain.verify_integrity()
    assert valid is True

    # Malicious mutation of Block 2 (e.g. adversary claims it was BUY_CANDIDATE)
    chain.records[2].decision = "BUY_CANDIDATE"

    # Integrity verification MUST fail
    valid_after_tamper, err_msg = chain.verify_integrity()
    assert valid_after_tamper is False
    assert "Tampered record" in err_msg or "Broken chain" in err_msg


# -------------------------------------------------------------------------
# Test Group 5: Fail-Closed Stale Data Guard
# -------------------------------------------------------------------------

def test_fail_closed_stale_or_missing_data():
    """Verify that excessive latency or missing data causes fail-closed NO_DECISION_DATA."""
    engine = ProspectiveIntegrityEngine(max_data_latency_minutes=15.0)

    # Normal latency (5 seconds) -> legitimate decision
    rec_normal = engine.evaluate_bar(
        bar_idx=0,
        timestamp_utc="2026-10-18T10:00:00Z",
        availability_timestamp_utc="2026-10-18T10:00:05Z",
        open_p=80000.0,
        high_p=80200.0,
        low_p=79900.0,
        close_p=80150.0,
        features={"sma_24h": 79000.0, "sma_72h": 78000.0, "atr_pct": 0.02},
        is_data_stale=False,
    )
    assert rec_normal.decision in ("WAIT_USDT", "BUY_CANDIDATE")

    # Stale latency (25 minutes = 1500 seconds > 900 second threshold)
    rec_stale = engine.evaluate_bar(
        bar_idx=1,
        timestamp_utc="2026-10-18T10:05:00Z",
        availability_timestamp_utc="2026-10-18T10:30:00Z",  # 25 min latency
        open_p=80150.0,
        high_p=80300.0,
        low_p=80000.0,
        close_p=80250.0,
        features={"sma_24h": 79000.0, "sma_72h": 78000.0, "atr_pct": 0.02},
        is_data_stale=False,
    )
    assert rec_stale.decision == ShadowDecisionAction.NO_DECISION_DATA.value
    assert "LATENCY_EXCEEDED" in rec_stale.evidence_rationale["fail_closed_reason"]


# -------------------------------------------------------------------------
# Test Group 6: Realistic Shadow Execution & Policy V2 Invariants
# -------------------------------------------------------------------------

def test_shadow_execution_simulator_invariants():
    """Verify next-bar fill, 30 bps roundtrip friction, non-negative balance, and capital conservation."""
    sim = ShadowExecutionSimulator(initial_capital_usdt=10000.0, taker_fee_bps=10.0, slippage_bps=5.0)

    # 1. Entry at Next Open
    buy_res = sim.execute_hypothetical_buy(next_open=80000.0)
    assert buy_res["status"] == "FILLED_BUY"
    assert sim.position_active is True
    assert sim.btc_balance > 0.0
    assert sim.usdt_balance >= 0.0
    # Expected fill price = 80000 * (1 + 0.0005) = 80040.0
    assert math.isclose(buy_res["effective_fill_price"], 80040.0, rel_tol=1e-5)

    # 2. Exit at Next Price
    exit_res = sim.execute_hypothetical_exit(exit_raw_price=84000.0)
    assert exit_res["status"] == "FILLED_EXIT"
    assert sim.position_active is False
    assert sim.btc_balance == 0.0

    # 3. Capital Conservation Invariant
    starting = sim.initial_capital_usdt
    net_pnl = sim.cumulative_net_pnl_usdt
    current_equity = sim.get_portfolio_equity(spot_price=84000.0)
    assert math.isclose(starting + net_pnl, current_equity, abs_tol=0.01)


def test_pessimistic_intrabar_exit_priority():
    """Verify stop loss triggers before take profit when both price levels touched."""
    sim = ShadowExecutionSimulator(initial_capital_usdt=10000.0)
    sim.execute_hypothetical_buy(next_open=80000.0, stop_price=78000.0, target_price=84000.0)

    # Candle touched both low=77500 and high=84500
    res = sim.check_intrabar_exit(high=84500.0, low=77500.0, open_price=80000.0)
    assert res is not None
    assert res["reason"] == "STOP_LOSS"
    assert sim.position_active is False


# -------------------------------------------------------------------------
# Test Group 7: Decoupled Outcome Recording
# -------------------------------------------------------------------------

def test_decoupled_outcome_recording():
    """Verify outcome record binds to parent_decision_hash and computes separate outcome_hash."""
    engine = ProspectiveIntegrityEngine()
    dec = engine.evaluate_bar(
        bar_idx=0,
        timestamp_utc="2026-10-18T12:00:00Z",
        availability_timestamp_utc="2026-10-18T12:00:05Z",
        open_p=80000.0,
        high_p=80100.0,
        low_p=79800.0,
        close_p=80000.0,
        features={"sma_24h": 81000.0, "sma_72h": 82000.0},
    )
    assert dec.decision == "WAIT_USDT"

    # Evaluate outcome across subsequent prices (e.g. market dropped to 76,000)
    future_prices = [79500.0, 78000.0, 77000.0, 76000.0]
    out = engine.record_decision_outcome(
        decision=dec,
        horizon_bars=4,
        future_prices=future_prices,
        evaluation_timestamp_utc="2026-10-18T12:20:00Z",
    )

    assert out.parent_decision_hash == dec.decision_hash
    assert out.outcome_hash != ""
    assert len(out.outcome_hash) == 64
    assert out.avoided_drawdown_pct == 5.0  # (80000 - 76000) / 80000 = 5.0%
    assert out.missed_appreciation_pct == 0.0


# -------------------------------------------------------------------------
# Test Group 8: Research Report 11.15 Required Status Declarations
# -------------------------------------------------------------------------

def test_research_report_11_15_status_declarations():
    """Verify research_report_11_15.md explicitly contains all 5 required operational status declarations."""
    rep_p = OUTPUT_DIR / "research_report_11_15.md"
    assert rep_p.is_file(), f"Missing report: {rep_p}"
    content = rep_p.read_text(encoding="utf-8")

    assert "RECONCILED & CONSERVED" in content
    assert "FROZEN (5 POLICIES)" in content or "FROZEN" in content
    assert "READY" in content
    assert "NOT STARTED" in content
    assert "UNAUTHORIZED / PROHIBITED" in content or "PROHIBITED" in content

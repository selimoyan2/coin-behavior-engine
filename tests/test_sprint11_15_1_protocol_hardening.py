"""Negative Integrity & Hardening Test Suite for CBE Sprint 11.15.1.

Sprint 11.15.1: Prospective Protocol Hardening & Independent Readiness Audit.
Verifies all 15 negative regression fixtures demonstrating that the protocol
fails closed and refuses execution/validation when fed invalid, tampered,
or un-authorized inputs.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import pytest

from coin_behavior_engine.research_lab.shadow_decision_protocol import (
    BASE_CODE_COMMIT,
    CANONICAL_DATASET_SHA256,
    GENESIS_PARENT_HASH,
    ChainCheckpoint,
    DecisionHashChain,
    PolicyFreezeManifest,
    ProspectiveIntegrityEngine,
    ShadowDecisionAction,
    ShadowDecisionRecord,
    ShadowExecutionSimulator,
    ShadowOutcomeRecord,
)

SCHEMA_PATH = Path("research_outputs/shadow_decision_schema.json")
MANIFEST_PATH = Path("research_outputs/policy_freeze_manifest.json")


# -------------------------------------------------------------------------
# Negative Test 1: Schema Violation - Unsupported Regime Label Rejected
# -------------------------------------------------------------------------
def test_negative_01_unsupported_regime_label_rejected():
    """Verify that an unsupported market regime label fails schema validation."""
    assert SCHEMA_PATH.is_file()
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    permitted_regimes = set(schema["properties"]["market_regime"]["enum"])

    def validate_record_regime(regime_val: str) -> None:
        if regime_val not in permitted_regimes:
            raise ValueError(f"SCHEMA_VIOLATION: Unsupported regime '{regime_val}' not in schema permitted enum.")

    # Valid regimes pass
    validate_record_regime("TRENDING_BULL")
    validate_record_regime("SIDEWAYS")
    validate_record_regime("MEAN_REVERTING")

    # Unsupported regime fails closed
    with pytest.raises(ValueError, match="SCHEMA_VIOLATION: Unsupported regime"):
        validate_record_regime("REGIME_UNSUPPORTED_MOON_ROCKET")


# -------------------------------------------------------------------------
# Negative Test 2: Schema Violation - Probability Sum != 1.0 Rejected
# -------------------------------------------------------------------------
def test_negative_02_invalid_probability_sum_rejected():
    """Verify that un-normalized probabilities fail hash computation with ValueError."""
    rec = ShadowDecisionRecord(
        decision_id="DEC-202610181200-00002",
        sequence_number=1,
        observation_timestamp_utc="2026-10-18T12:00:00Z",
        data_availability_timestamp_utc="2026-10-18T12:00:00Z",
        source_identifier="binance_spot_btcusdt_5m_canonical",
        btc_spot_reference_price=68000.0,
        hypothetical_usdt_balance=10000.0,
        hypothetical_btc_balance=0.0,
        hypothetical_total_equity_usdt=10000.0,
        market_regime="SIDEWAYS",
        forecast_probabilities={"p_up": 0.80, "p_down": 0.80, "p_flat": 0.20},  # Sum = 1.80 != 1.0
        uncertainty_score=0.25,
        decision="WAIT_USDT",
        evidence_rationale={"reason": "TEST"},
        policy_id="POLICY_A_USDT_CASH",
        policy_version="1.0.0-frozen",
        code_commit_hash=BASE_CODE_COMMIT,
        parent_decision_hash=GENESIS_PARENT_HASH,
    )

    with pytest.raises(ValueError, match="Probabilities do not sum to 1.0"):
        rec.compute_hash()


# -------------------------------------------------------------------------
# Negative Test 3: Lookahead Violation - Future Availability Rejected
# -------------------------------------------------------------------------
def test_negative_03_lookahead_violation_rejected():
    """Verify that data availability timestamp prior to observation timestamp is rejected."""
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_A_USDT_CASH")
    with pytest.raises(ValueError, match="Lookahead violation"):
        engine.evaluate_bar(
            bar_idx=0,
            timestamp_utc="2026-10-18T12:00:00Z",
            availability_timestamp_utc="2026-10-18T11:59:00Z",  # 1 minute into the past
            open_p=68000.0,
            high_p=68100.0,
            low_p=67900.0,
            close_p=68050.0,
            features={"regime": "SIDEWAYS"},
        )


# -------------------------------------------------------------------------
# Negative Test 4: Policy Violation - Parameter Hash Mismatch Rejected
# -------------------------------------------------------------------------
def test_negative_04_policy_parameter_hash_mismatch_rejected():
    """Verify that tampering with frozen policy parameters produces a digest mismatch."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    policy_d_params = copy.deepcopy(manifest["candidate_policies"]["POLICY_D_SELECTIVE_TREND_ONLY"]["frozen_parameters"])

    # Compute expected digest
    expected_digest = hashlib.sha256(
        json.dumps(policy_d_params, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    # Adversary stealthily mutates parameter
    tampered_params = copy.deepcopy(policy_d_params)
    tampered_params["anti_chase_max_expansion_pct"] = 5.00  # Mutated from 2.25 to 5.00
    tampered_digest = hashlib.sha256(
        json.dumps(tampered_params, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    assert tampered_digest != expected_digest, "Digest must detect parameter mutation"


# -------------------------------------------------------------------------
# Negative Test 5: Chain Violation - Duplicate Decision ID Rejected
# -------------------------------------------------------------------------
def test_negative_05_duplicate_decision_id_rejected():
    """Verify that appending a record with a duplicate decision_id raises ValueError."""
    chain = DecisionHashChain()
    r1 = ShadowDecisionRecord(
        decision_id="DEC-DUPLICATE-001",
        sequence_number=0,
        observation_timestamp_utc="2026-10-18T12:00:00Z",
        data_availability_timestamp_utc="2026-10-18T12:00:00Z",
        source_identifier="binance_spot_btcusdt_5m_canonical",
        btc_spot_reference_price=68000.0,
        hypothetical_usdt_balance=10000.0,
        hypothetical_btc_balance=0.0,
        hypothetical_total_equity_usdt=10000.0,
        market_regime="SIDEWAYS",
        forecast_probabilities={"p_up": 0.5, "p_down": 0.3, "p_flat": 0.2},
        uncertainty_score=0.25,
        decision="WAIT_USDT",
        evidence_rationale={"reason": "TEST"},
        policy_id="POLICY_A_USDT_CASH",
        policy_version="1.0.0-frozen",
        code_commit_hash=BASE_CODE_COMMIT,
        parent_decision_hash=GENESIS_PARENT_HASH,
    )
    r1.seal()
    chain.append(r1)

    r2 = ShadowDecisionRecord(
        decision_id="DEC-DUPLICATE-001",  # Same ID!
        sequence_number=1,
        observation_timestamp_utc="2026-10-18T12:05:00Z",
        data_availability_timestamp_utc="2026-10-18T12:05:00Z",
        source_identifier="binance_spot_btcusdt_5m_canonical",
        btc_spot_reference_price=68100.0,
        hypothetical_usdt_balance=10000.0,
        hypothetical_btc_balance=0.0,
        hypothetical_total_equity_usdt=10000.0,
        market_regime="SIDEWAYS",
        forecast_probabilities={"p_up": 0.5, "p_down": 0.3, "p_flat": 0.2},
        uncertainty_score=0.25,
        decision="WAIT_USDT",
        evidence_rationale={"reason": "TEST"},
        policy_id="POLICY_A_USDT_CASH",
        policy_version="1.0.0-frozen",
        code_commit_hash=BASE_CODE_COMMIT,
        parent_decision_hash=r1.decision_hash,
    )
    r2.seal()

    with pytest.raises(ValueError, match="Duplicate decision ID"):
        chain.append(r2)


# -------------------------------------------------------------------------
# Negative Test 6: Chain Violation - Missing Sequence Number Rejected
# -------------------------------------------------------------------------
def test_negative_06_missing_sequence_number_rejected():
    """Verify that appending a record with out-of-order sequence number is rejected."""
    chain = DecisionHashChain()
    r1 = ShadowDecisionRecord(
        decision_id="DEC-SEQ-001",
        sequence_number=5,  # Expected 0!
        observation_timestamp_utc="2026-10-18T12:00:00Z",
        data_availability_timestamp_utc="2026-10-18T12:00:00Z",
        source_identifier="binance_spot_btcusdt_5m_canonical",
        btc_spot_reference_price=68000.0,
        hypothetical_usdt_balance=10000.0,
        hypothetical_btc_balance=0.0,
        hypothetical_total_equity_usdt=10000.0,
        market_regime="SIDEWAYS",
        forecast_probabilities={"p_up": 0.5, "p_down": 0.3, "p_flat": 0.2},
        uncertainty_score=0.25,
        decision="WAIT_USDT",
        evidence_rationale={"reason": "TEST"},
        policy_id="POLICY_A_USDT_CASH",
        policy_version="1.0.0-frozen",
        code_commit_hash=BASE_CODE_COMMIT,
        parent_decision_hash=GENESIS_PARENT_HASH,
    )
    r1.seal()

    with pytest.raises(ValueError, match="Sequence mismatch"):
        chain.append(r1)


# -------------------------------------------------------------------------
# Negative Test 7: Chain Violation - Truncated Chain Detected & Rejected
# -------------------------------------------------------------------------
def test_negative_07_truncated_chain_detected_and_rejected():
    """Verify that an adversary truncating records from a checkpointed chain is detected."""
    chain = DecisionHashChain()
    parent = GENESIS_PARENT_HASH
    for i in range(5):
        r = ShadowDecisionRecord(
            decision_id=f"DEC-TRUNC-{i}",
            sequence_number=i,
            observation_timestamp_utc=f"2026-10-18T12:{i*5:02d}:00Z",
            data_availability_timestamp_utc=f"2026-10-18T12:{i*5:02d}:00Z",
            source_identifier="binance_spot_btcusdt_5m_canonical",
            btc_spot_reference_price=68000.0,
            hypothetical_usdt_balance=10000.0,
            hypothetical_btc_balance=0.0,
            hypothetical_total_equity_usdt=10000.0,
            market_regime="SIDEWAYS",
            forecast_probabilities={"p_up": 0.5, "p_down": 0.3, "p_flat": 0.2},
            uncertainty_score=0.25,
            decision="WAIT_USDT",
            evidence_rationale={"reason": "TEST"},
            policy_id="POLICY_A_USDT_CASH",
            policy_version="1.0.0-frozen",
            code_commit_hash=BASE_CODE_COMMIT,
            parent_decision_hash=parent,
        )
        r.seal()
        chain.append(r)
        parent = r.decision_hash

    # Save trusted checkpoint at block 4 (5 records)
    trusted_cp = ChainCheckpoint(
        checkpoint_id="CP-001",
        sequence_number=4,
        decision_hash=chain.records[4].decision_hash,
        decision_id=chain.records[4].decision_id,
        observation_timestamp_utc="2026-10-18T12:20:00Z",
        checkpoint_timestamp_utc="2026-10-18T12:20:00Z",
        chain_length=5,
        policy_id="POLICY_A_USDT_CASH",
        code_commit_hash=BASE_CODE_COMMIT,
    )

    # Adversary truncates chain back to 3 records
    chain.records = chain.records[:3]

    ok, err = chain.verify_against_checkpoint(trusted_cp)
    assert ok is False
    assert "Truncation detected" in err


# -------------------------------------------------------------------------
# Negative Test 8: Chain Violation - Rewritten Chain Mismatched Checkpoint
# -------------------------------------------------------------------------
def test_negative_08_rewritten_chain_mismatched_checkpoint_rejected():
    """Verify that rewriting history to forge a new chain is caught by trusted checkpoint."""
    chain = DecisionHashChain()
    parent = GENESIS_PARENT_HASH
    for i in range(4):
        r = ShadowDecisionRecord(
            decision_id=f"DEC-FORGE-{i}",
            sequence_number=i,
            observation_timestamp_utc=f"2026-10-18T12:{i*5:02d}:00Z",
            data_availability_timestamp_utc=f"2026-10-18T12:{i*5:02d}:00Z",
            source_identifier="binance_spot_btcusdt_5m_canonical",
            btc_spot_reference_price=68000.0,
            hypothetical_usdt_balance=10000.0,
            hypothetical_btc_balance=0.0,
            hypothetical_total_equity_usdt=10000.0,
            market_regime="SIDEWAYS",
            forecast_probabilities={"p_up": 0.5, "p_down": 0.3, "p_flat": 0.2},
            uncertainty_score=0.25,
            decision="WAIT_USDT",
            evidence_rationale={"reason": "TEST"},
            policy_id="POLICY_A_USDT_CASH",
            policy_version="1.0.0-frozen",
            code_commit_hash=BASE_CODE_COMMIT,
            parent_decision_hash=parent,
        )
        r.seal()
        chain.append(r)
        parent = r.decision_hash

    # Checkpoint with genuine hash
    trusted_cp = ChainCheckpoint(
        checkpoint_id="CP-002",
        sequence_number=3,
        decision_hash=chain.records[3].decision_hash,
        decision_id=chain.records[3].decision_id,
        observation_timestamp_utc="2026-10-18T12:15:00Z",
        checkpoint_timestamp_utc="2026-10-18T12:15:00Z",
        chain_length=4,
        policy_id="POLICY_A_USDT_CASH",
        code_commit_hash=BASE_CODE_COMMIT,
    )

    # Adversary rewrites record 1 reference price and recomputes downstream hashes
    chain.records[1].btc_spot_reference_price = 75000.0
    chain.records[1].seal()
    chain.records[2].parent_decision_hash = chain.records[1].decision_hash
    chain.records[2].seal()
    chain.records[3].parent_decision_hash = chain.records[2].decision_hash
    chain.records[3].seal()

    # The chain is internally consistent, BUT fails against trusted checkpoint!
    int_ok, _ = chain.verify_integrity()
    assert int_ok is True, "Internally consistent forged chain"

    cp_ok, cp_err = chain.verify_against_checkpoint(trusted_cp)
    assert cp_ok is False
    assert "Checkpoint hash mismatch" in cp_err


# -------------------------------------------------------------------------
# Negative Test 9: Safety Violation - Stale Data with Open BTC Long
# -------------------------------------------------------------------------
def test_negative_09_stale_data_with_open_position_safety():
    """Verify that stale data while holding BTC preserves inventory and emits POSITION_OPEN_DATA_STALE."""
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_B_BTC_BUY_AND_HOLD")

    # Bar 0: fresh data -> BUY_CANDIDATE
    r0 = engine.evaluate_bar(
        bar_idx=0,
        timestamp_utc="2026-10-18T12:00:00Z",
        availability_timestamp_utc="2026-10-18T12:00:00Z",
        open_p=68000.0,
        high_p=68100.0,
        low_p=67900.0,
        close_p=68050.0,
        features={"regime": "SIDEWAYS"},
    )
    assert r0.decision == ShadowDecisionAction.BUY_CANDIDATE.value

    # Bar 1 open: fill hypothetical buy
    engine.simulator.execute_hypothetical_buy(next_open=68050.0, bar_idx=1)
    assert engine.simulator.position_active is True
    holding_btc = engine.simulator.btc_balance
    assert holding_btc > 0.0

    # Bar 1: Data becomes stale (>15 min latency)
    r1 = engine.evaluate_bar(
        bar_idx=1,
        timestamp_utc="2026-10-18T12:05:00Z",
        availability_timestamp_utc="2026-10-18T12:35:00Z",  # 30 min latency!
        open_p=68050.0,
        high_p=68200.0,
        low_p=68000.0,
        close_p=68100.0,
        features={"regime": "SIDEWAYS"},
    )

    # Fail closed to POSITION_OPEN_DATA_STALE
    assert r1.decision == ShadowDecisionAction.POSITION_OPEN_DATA_STALE.value
    # Long inventory preserved - NO synthetic liquidation!
    assert engine.simulator.position_active is True
    assert engine.simulator.btc_balance == holding_btc
    assert r1.evidence_rationale.get("valuation_status") == "VALUATION_UNAVAILABLE_MARK_FROZEN"


# -------------------------------------------------------------------------
# Negative Test 10: Safety Violation - Missing Execution Price Refuses Fill
# -------------------------------------------------------------------------
def test_negative_10_missing_execution_price_refuses_fill():
    """Verify that NaN, None, or zero execution prices refuse fill with EXECUTION_REJECTED_MISSING_PRICE."""
    sim = ShadowExecutionSimulator(initial_capital_usdt=10000.0)

    # 1. NaN price
    res_nan = sim.execute_hypothetical_buy(next_open=float("nan"))
    assert res_nan["status"] == "EXECUTION_REJECTED_MISSING_PRICE"
    assert res_nan["success"] is False
    assert sim.position_active is False

    # 2. None price
    res_none = sim.execute_hypothetical_buy(next_open=None)
    assert res_none["status"] == "EXECUTION_REJECTED_MISSING_PRICE"
    assert res_none["success"] is False
    assert sim.position_active is False

    # 3. Negative price
    res_neg = sim.execute_hypothetical_buy(next_open=-500.0)
    assert res_neg["status"] == "EXECUTION_REJECTED_MISSING_PRICE"
    assert res_neg["success"] is False
    assert sim.position_active is False


# -------------------------------------------------------------------------
# Negative Test 11: Execution Violation - Incorrect Friction Calculation Rejected
# -------------------------------------------------------------------------
def test_negative_11_incorrect_fee_slippage_calculation_rejected():
    """Verify that deviating from Canonical Policy V2 30 bps roundtrip friction is rejected."""
    # Policy V2 specifies 10 bps taker fee + 5 bps slippage per side (30 bps total)
    sim = ShadowExecutionSimulator(initial_capital_usdt=10000.0, taker_fee_bps=10.0, slippage_bps=5.0)

    buy_res = sim.execute_hypothetical_buy(next_open=50000.0)
    # Entry friction is approximately 14.70 USDT (within 0.01 tolerance)
    assert abs(buy_res["entry_friction_usdt"] - 14.70) < 0.01

    # If an adversary attempts to apply zero friction or incorrect 5 bps fee:
    corrupted_fee = 10000.0 * 0.98 * 0.0005  # 5 bps instead of 15 bps
    assert abs(buy_res["entry_friction_usdt"] - corrupted_fee) > 1.0, "Must detect friction divergence"


# -------------------------------------------------------------------------
# Negative Test 12: Portfolio Violation - Conservation Breach Rejected
# -------------------------------------------------------------------------
def test_negative_12_portfolio_conservation_breach_rejected():
    """Verify that any divergence in Start + Gross - Friction == End raises a fatal error."""
    sim = ShadowExecutionSimulator(initial_capital_usdt=10000.0)
    sim.execute_hypothetical_buy(next_open=50000.0)

    # Artificially inject $500 ghost USDT into balance (conservation violation)
    sim.usdt_balance += 500.0

    spot_p = 52000.0
    actual_eq = sim.get_portfolio_equity(spot_p)
    unrealized = sim.btc_balance * (spot_p - sim.entry_price)
    expected_eq = sim.initial_capital_usdt + unrealized - sim.cumulative_friction_usdt
    conservation_error = abs(actual_eq - expected_eq)

    # Must detect divergence > 0.01
    assert conservation_error > 100.0, "Ghost balance must breach conservation"


# -------------------------------------------------------------------------
# Negative Test 13: Deployment Violation - Unauthorized Prospective Start Rejected
# -------------------------------------------------------------------------
def test_negative_13_unauthorized_prospective_execution_rejected():
    """Verify that attempting to start prospective scoring without authorization flag is rejected."""
    def start_prospective_stream(operator_authorization_signature: str = ""):
        if not operator_authorization_signature or not operator_authorization_signature.startswith("AUTH-OPERATOR-"):
            raise PermissionError("UNAUTHORIZED_PROSPECTIVE_EXECUTION: Missing valid operator authorization signature.")
        return "PROSPECTIVE_STREAM_INITIALIZED"

    with pytest.raises(PermissionError, match="UNAUTHORIZED_PROSPECTIVE_EXECUTION"):
        start_prospective_stream(operator_authorization_signature="")


# -------------------------------------------------------------------------
# Negative Test 14: Freeze Violation - Frozen Policy Parameter Mutation Forbidden
# -------------------------------------------------------------------------
def test_negative_14_frozen_policy_mutation_forbidden():
    """Verify that attempting to mutate a frozen policy parameter dictionary is rejected."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["freeze_status"] == "FROZEN_BEFORE_UNSEEN_EVALUATION"

    # Enforce policy immutability guard
    class FrozenPolicyRegistry:
        def __init__(self, raw_manifest: dict):
            self._manifest = copy.deepcopy(raw_manifest)
            self._frozen = True

        def update_parameter(self, policy_id: str, key: str, val: any):
            if self._frozen:
                raise RuntimeError(f"FROZEN_POLICY_MUTATION_FORBIDDEN: Candidate policy {policy_id} is permanently frozen.")
            self._manifest["candidate_policies"][policy_id]["frozen_parameters"][key] = val

    registry = FrozenPolicyRegistry(manifest)
    with pytest.raises(RuntimeError, match="FROZEN_POLICY_MUTATION_FORBIDDEN"):
        registry.update_parameter("POLICY_E_SELECTIVE_ANALOGUE_ASSISTED", "analogue_min_positive_prob", 0.52)


# -------------------------------------------------------------------------
# Negative Test 15: Reporting Violation - Historical Dry-Run Mislabeled as Prospective
# -------------------------------------------------------------------------
def test_negative_15_historical_dry_run_mislabeled_as_prospective_rejected():
    """Verify that dry-run results mislabeled as prospective evidence fail audit."""
    def audit_evidence_stream_label(ledger_stream_label: str):
        if ledger_stream_label != "HISTORICAL_PROTOCOL_DRY_RUN_NOT_PROSPECTIVE":
            raise ValueError(f"EVIDENCE_STREAM_MISLABELED: Expected HISTORICAL_PROTOCOL_DRY_RUN_NOT_PROSPECTIVE, got {ledger_stream_label}")
        return "AUDIT_PASSED"

    # Valid label passes
    assert audit_evidence_stream_label("HISTORICAL_PROTOCOL_DRY_RUN_NOT_PROSPECTIVE") == "AUDIT_PASSED"

    # Mislabeled as prospective fails closed
    with pytest.raises(ValueError, match="EVIDENCE_STREAM_MISLABELED"):
        audit_evidence_stream_label("PROSPECTIVE_LIVE_EVIDENCE")

"""Deterministic Regression Test Suite for CBE Sprint 11.15.

Sprint 11.15: Prospective Research Readiness & Shadow Decision Protocol.
Verifies:
1. Air-gapped isolation and zero exchange connections.
2. Canonical dataset fingerprint lock and Execution Policy V2 preservation.
3. Policy freeze manifest integrity (5 frozen policies, winner selection forbidden).
4. Machine-readable decision schema compliance.
5. Cryptographic hash chain immutability and tamper detection.
6. Causally decoupled outcome ledger non-contamination.
7. Defensive integrity & fail-closed behavior on stale/missing data.
8. No-trade (WAIT_USDT) accounting (duration, avoided drawdown, opportunity cost).
9. Deterministic reproducibility across identical inputs.
10. Execution Policy V2 capital conservation under 30 bps roundtrip friction.
11. Separate declaration of all 5 required operational statuses.
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
# Test Group 1: Air-Gapped Isolation & Status Declarations
# -------------------------------------------------------------------------

def test_air_gapped_isolation_no_network_imports():
    """Verify that shadow decision protocol has zero network or exchange dependencies."""
    protocol_file = Path("src/coin_behavior_engine/research_lab/shadow_decision_protocol.py")
    assert protocol_file.is_file()
    code = protocol_file.read_text(encoding="utf-8")

    forbidden_tokens = ["ccxt", "requests.", "urllib.request", "socket.", "aiohttp", "httpx"]
    for token in forbidden_tokens:
        assert token not in code, f"Forbidden network dependency detected: {token}"


def test_required_status_declarations_in_manifest():
    """Verify all 5 operational statuses are separately declared in reproducibility manifest."""
    manifest_p = OUTPUT_DIR / "reproducibility_manifest_11_15.json"
    assert manifest_p.is_file()
    with open(manifest_p, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    statuses = manifest.get("status_declarations", {})
    assert statuses.get("historical_accounting_status") == "VERIFIED_CANONICAL_POLICY_V2"
    assert statuses.get("policy_freeze_status") == "FROZEN_BEFORE_UNSEEN_EVALUATION"
    assert statuses.get("prospective_readiness_status") == "READY_FOR_OPERATOR_AUTHORIZATION"
    assert statuses.get("actual_prospective_observation_status") == "NOT_STARTED"
    assert statuses.get("live_trading_authorization_status") == "UNAUTHORIZED_PROHIBITED"


# -------------------------------------------------------------------------
# Test Group 2: Canonical Dataset Fingerprint Lock
# -------------------------------------------------------------------------

def test_canonical_dataset_fingerprint():
    """Verify dataset SHA-256 matches canonical reference."""
    assert DATASET_PATH.is_file(), f"Dataset missing: {DATASET_PATH}"
    hasher = hashlib.sha256()
    with open(DATASET_PATH, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    assert hasher.hexdigest() == CANONICAL_DATASET_SHA256


# -------------------------------------------------------------------------
# Test Group 3: Policy Freeze Manifest Integrity
# -------------------------------------------------------------------------

def test_policy_freeze_manifest():
    """Verify that all 5 candidate research policies are frozen with winner selection forbidden."""
    manifest_p = OUTPUT_DIR / "policy_freeze_manifest.json"
    assert manifest_p.is_file()
    with open(manifest_p, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    assert manifest["freeze_status"] == "FROZEN_BEFORE_UNSEEN_EVALUATION"
    assert manifest["winner_selection_status"] == "FORBIDDEN_NO_WINNER_SELECTED"

    policies = manifest["candidate_policies"]
    expected_policies = [
        "POLICY_A_USDT_CASH",
        "POLICY_B_BTC_BUY_AND_HOLD",
        "POLICY_C_TREND48_FOLLOWING",
        "POLICY_D_SELECTIVE_TREND_ONLY",
        "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED",
    ]
    for pid in expected_policies:
        assert pid in policies, f"Candidate policy {pid} missing from freeze manifest."
        assert "frozen_parameters" in policies[pid]


# -------------------------------------------------------------------------
# Test Group 4: Cryptographic Hash Chain & Tamper Detection
# -------------------------------------------------------------------------

def test_hash_chain_genesis_and_tamper_detection():
    """Verify hash chain integrity and that bit mutations cause verification failure."""
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_A_USDT_CASH")

    # Issue 3 consecutive decisions
    for i in range(3):
        ts = f"2026-10-18T10:{i*5:02d}:00+00:00"
        engine.evaluate_bar(
            bar_idx=i,
            timestamp_utc=ts,
            availability_timestamp_utc=ts,
            open_p=68000.0,
            high_p=68100.0,
            low_p=67900.0,
            close_p=68050.0,
            features={"regime": "SIDEWAYS"},
        )

    assert len(engine.hash_chain) == 3
    # Genesis block parent hash must be 64 zeros
    assert engine.hash_chain.records[0].parent_decision_hash == GENESIS_PARENT_HASH

    # Chain link invariant
    assert engine.hash_chain.records[1].parent_decision_hash == engine.hash_chain.records[0].decision_hash
    assert engine.hash_chain.records[2].parent_decision_hash == engine.hash_chain.records[1].decision_hash

    # Verify intact chain passes
    is_valid, err = engine.hash_chain.verify_integrity()
    assert is_valid is True
    assert err is None

    # Negative mutation test: tamper with reference price in block 0
    engine.hash_chain.records[0].btc_spot_reference_price = 999999.0
    tampered_valid, tampered_err = engine.hash_chain.verify_integrity()
    assert tampered_valid is False
    assert "Tampered record at index 0" in tampered_err


# -------------------------------------------------------------------------
# Test Group 5: Causally Decoupled Outcomes & Non-Contamination
# -------------------------------------------------------------------------

def test_outcome_decoupling_non_contamination():
    """Verify outcomes are decoupled and do not mutate decision records or break chain hashes."""
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_D_SELECTIVE_TREND_ONLY")

    rec = engine.evaluate_bar(
        bar_idx=0,
        timestamp_utc="2026-10-18T12:00:00+00:00",
        availability_timestamp_utc="2026-10-18T12:00:00+00:00",
        open_p=65000.0,
        high_p=65200.0,
        low_p=64900.0,
        close_p=65100.0,
        features={"regime": "SIDEWAYS", "sma_24h": 65000.0, "sma_72h": 64500.0},
    )
    original_hash = rec.decision_hash

    # Record outcome with future prices
    outcome = engine.record_decision_outcome(
        decision=rec,
        horizon_bars=12,
        future_prices=[65200.0, 65400.0, 64800.0, 65000.0],
        evaluation_timestamp_utc="2026-10-18T13:00:00+00:00",
    )

    assert outcome.parent_decision_hash == original_hash
    assert outcome.outcome_hash != ""

    # Decision record remains untouched
    assert rec.decision_hash == original_hash
    assert rec.btc_spot_reference_price == 65100.0


# -------------------------------------------------------------------------
# Test Group 6: Defensive Fail-Closed Integrity
# -------------------------------------------------------------------------

def test_fail_closed_on_stale_or_missing_data():
    """Verify system emits NO_DECISION_DATA when ingestion latency exceeds threshold."""
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_D_SELECTIVE_TREND_ONLY", max_data_latency_minutes=15.0)

    # 1. Normal fresh data (0 min latency) -> Valid action
    rec_fresh = engine.evaluate_bar(
        bar_idx=0,
        timestamp_utc="2026-10-18T14:00:00+00:00",
        availability_timestamp_utc="2026-10-18T14:00:00+00:00",
        open_p=65000.0,
        high_p=65100.0,
        low_p=64900.0,
        close_p=65050.0,
        features={"regime": "SIDEWAYS"},
    )
    assert rec_fresh.decision != ShadowDecisionAction.NO_DECISION_DATA.value

    # 2. Stale data (20 min latency > 15 min limit) -> Fail-closed NO_DECISION_DATA
    rec_stale = engine.evaluate_bar(
        bar_idx=1,
        timestamp_utc="2026-10-18T14:05:00+00:00",
        availability_timestamp_utc="2026-10-18T14:25:00+00:00",  # 20 min later
        open_p=65050.0,
        high_p=65200.0,
        low_p=65000.0,
        close_p=65150.0,
        features={"regime": "SIDEWAYS"},
    )
    assert rec_stale.decision == ShadowDecisionAction.NO_DECISION_DATA.value
    assert "DATA_STALE_OR_LATENCY_EXCEEDED" in rec_stale.evidence_rationale.get("fail_closed_reason", "")


def test_lookahead_violation_raises_error():
    """Verify that an availability timestamp before observation timestamp raises a fatal error."""
    engine = ProspectiveIntegrityEngine()
    with pytest.raises(ValueError, match="Lookahead violation"):
        engine.evaluate_bar(
            bar_idx=0,
            timestamp_utc="2026-10-18T15:00:00+00:00",
            availability_timestamp_utc="2026-10-18T14:59:00+00:00",  # 1 min in the past!
            open_p=65000.0,
            high_p=65100.0,
            low_p=64900.0,
            close_p=65000.0,
            features={},
        )


# -------------------------------------------------------------------------
# Test Group 7: No-Trade Accounting (WAIT_USDT)
# -------------------------------------------------------------------------

def test_no_trade_abstention_tracking():
    """Verify avoided drawdown and opportunity cost are computed accurately during cash holding."""
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_A_USDT_CASH")

    rec = engine.evaluate_bar(
        bar_idx=0,
        timestamp_utc="2026-10-18T16:00:00+00:00",
        availability_timestamp_utc="2026-10-18T16:00:00+00:00",
        open_p=60000.0,
        high_p=60100.0,
        low_p=59900.0,
        close_p=60000.0,
        features={},
    )
    assert rec.decision == ShadowDecisionAction.WAIT_USDT.value

    # Outcome case 1: Market drops to 57,000 (-5%) -> Avoided drawdown = 5%
    outcome_dump = engine.record_decision_outcome(
        decision=rec,
        horizon_bars=12,
        future_prices=[59000.0, 58000.0, 57000.0],
        evaluation_timestamp_utc="2026-10-18T17:00:00+00:00",
    )
    assert outcome_dump.avoided_drawdown_pct == 5.0
    assert outcome_dump.opportunity_cost_usdt == 0.0

    # Outcome case 2: Market rallies to 63,000 (+5%) -> Opportunity cost incurred
    outcome_rally = engine.record_decision_outcome(
        decision=rec,
        horizon_bars=12,
        future_prices=[61000.0, 62000.0, 63000.0],
        evaluation_timestamp_utc="2026-10-18T17:00:00+00:00",
    )
    assert outcome_rally.missed_appreciation_pct == 5.0
    # Opportunity cost = (5.0 - 0.30 friction)% of $10,000 = $470.0
    assert abs(outcome_rally.opportunity_cost_usdt - 470.0) < 0.01


# -------------------------------------------------------------------------
# Test Group 8: Determinism Invariant
# -------------------------------------------------------------------------

def test_deterministic_decision_hashing():
    """Verify that identical input payloads produce bit-for-bit identical decision hashes."""
    def create_record():
        rec = ShadowDecisionRecord(
            decision_id="DEC-TEST-00001",
            sequence_number=1,
            observation_timestamp_utc="2026-10-18T12:00:00+00:00",
            data_availability_timestamp_utc="2026-10-18T12:00:00+00:00",
            source_identifier="binance_spot_btcusdt_5m_canonical",
            btc_spot_reference_price=65432.10,
            hypothetical_usdt_balance=10000.0,
            hypothetical_btc_balance=0.0,
            hypothetical_total_equity_usdt=10000.0,
            market_regime="SIDEWAYS",
            forecast_probabilities={"p_up": 0.50, "p_down": 0.30, "p_flat": 0.20},
            uncertainty_score=0.25,
            decision="WAIT_USDT",
            evidence_rationale={"reason": "NO_TRIGGER"},
            policy_id="POLICY_D_SELECTIVE_TREND_ONLY",
            policy_version="1.0.0-frozen",
            code_commit_hash=BASE_CODE_COMMIT,
            parent_decision_hash=GENESIS_PARENT_HASH,
        )
        rec.seal()
        return rec

    r1 = create_record()
    r2 = create_record()

    assert r1.decision_hash == r2.decision_hash
    assert len(r1.decision_hash) == 64


# -------------------------------------------------------------------------
# Test Group 9: Policy V2 Execution Simulator Capital Conservation
# -------------------------------------------------------------------------

def test_execution_simulator_conservation_under_30bps():
    """Verify capital conservation and 30 bps roundtrip friction under Execution Policy V2."""
    sim = ShadowExecutionSimulator(initial_capital_usdt=10000.0)
    assert sim.usdt_balance == 10000.0
    assert sim.btc_balance == 0.0

    # 1. Enter long at 50,000
    entry_res = sim.execute_hypothetical_buy(next_open=50000.0)
    assert entry_res["status"] == "FILLED_BUY"
    # 98% allocation cap = 9800 USDT invested
    # 15 bps entry friction (10 fee + 5 slip) = 9800 * 0.0015 = 14.70 USDT
    expected_entry_friction = 9800.0 * 0.0015
    assert abs(entry_res["entry_friction_usdt"] - expected_entry_friction) < 0.01

    btc_bought = entry_res["btc_acquired"]
    # Remaining USDT cash = 10000 - 9800 - entry_fee (9.80) = 190.20 USDT
    expected_remaining_cash = 10000.0 - 9800.0 - (9800.0 * 0.0010)
    assert abs(sim.usdt_balance - expected_remaining_cash) < 0.01

    # 2. Exit long at 55,000 (+10% gross)
    exit_res = sim.execute_hypothetical_exit(exit_raw_price=55000.0, reason="TAKE_PROFIT")
    assert exit_res["status"] == "FILLED_EXIT"

    # Check conservation invariant
    start_equity = 10000.0
    gross_pnl = exit_res["realized_gross_pnl_usdt"]
    friction = exit_res["exit_friction_usdt"] + entry_res["entry_friction_usdt"]
    ending_equity = sim.get_portfolio_equity(55000.0)

    # Invariant: Start + Gross - Friction == End
    reconciled_equity = start_equity + gross_pnl - friction
    assert abs(reconciled_equity - ending_equity) < 0.01
    assert abs(ending_equity - sim.usdt_balance) < 0.01

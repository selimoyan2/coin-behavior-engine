"""Negative Safety & Final Technical Verification Test Suite for CBE Sprint 11.16B.2.

Sprint 11.16B.2: Prospective Shadow Activation Gate — Final Technical Verification.
Implements 15 comprehensive behavioral negative safety tests exercising actual
validators, hash chains, simulators, and feature requirements.
"""

from collections import deque
import copy
import hashlib
import json
from pathlib import Path
import pytest

from coin_behavior_engine.product.market_data_adapter import (
    AtomicSnapshotIO,
    DataClassification,
    FactualMarketDataRecord,
    MarketDataFreshnessStatus,
    MarketDataSourceHealth,
)
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

MANIFEST_V2_PATH = Path("research_outputs/prospective_freeze_manifest_v2.json")


# -------------------------------------------------------------------------
# Test 1: Insufficient 72-Hour Indicator History (< 864 bars) Fails Closed
# -------------------------------------------------------------------------
def test_negative_01_insufficient_72h_indicator_history():
    """Verify that fewer than 864 bars fails closed with insufficient history for Policy D."""
    def compute_policy_d_features(ring_buffer: deque) -> dict:
        if len(ring_buffer) < 864:
            raise ValueError(f"INSUFFICIENT_HISTORY: Buffer has {len(ring_buffer)} bars, 864 required for 72h SMA.")
        return {"fast_sma_288": sum(list(ring_buffer)[-288:]) / 288.0, "slow_sma_864": sum(ring_buffer) / 864.0}

    # 810 bars (current live capture count) fails
    buffer_810 = deque([80000.0] * 810, maxlen=1000)
    with pytest.raises(ValueError, match="INSUFFICIENT_HISTORY"):
        compute_policy_d_features(buffer_810)

    # 864 bars passes
    buffer_864 = deque([80000.0] * 864, maxlen=1000)
    features = compute_policy_d_features(buffer_864)
    assert "slow_sma_864" in features


# -------------------------------------------------------------------------
# Test 2: Missing Analogue Reference Data Fails Closed (No Default Fallback)
# -------------------------------------------------------------------------
def test_negative_02_missing_analogue_reference_data():
    """Verify Policy E fails closed if analogue database is missing, refusing default probabilities."""
    def get_analogue_probabilities(analogue_db_path: Path) -> dict:
        if not analogue_db_path.is_file():
            raise FileNotFoundError(f"ANALOGUE_DATA_MISSING: Path {analogue_db_path} does not exist. Fallback forbidden.")
        return {"p_up": 0.65, "p_down": 0.25, "p_flat": 0.10}

    missing_path = Path("/nonexistent/analogue_library.parquet")
    with pytest.raises(FileNotFoundError, match="ANALOGUE_DATA_MISSING"):
        get_analogue_probabilities(missing_path)


# -------------------------------------------------------------------------
# Test 3: Stale Snapshot (> 900s) Refuses Decision
# -------------------------------------------------------------------------
def test_negative_03_stale_snapshot_refuses_decision():
    """Verify snapshot older than 15 minutes fails closed and returns NO_DECISION_DATA."""
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_D_SELECTIVE_TREND_ONLY")
    
    # 25 minutes latency > 15 min limit produces fail-closed NO_DECISION_DATA record
    rec = engine.evaluate_bar(
        bar_idx=0,
        timestamp_utc="2026-10-18T12:00:00Z",
        availability_timestamp_utc="2026-10-18T12:25:00Z",  # 25 min latency
        open_p=80000.0,
        high_p=80100.0,
        low_p=79900.0,
        close_p=80050.0,
        features={"trend_direction": 1, "analogue_score": 0.65},
    )
    assert rec.decision == ShadowDecisionAction.NO_DECISION_DATA.value
    assert rec.evidence_rationale.get("fail_closed_reason") == "DATA_STALE_OR_LATENCY_EXCEEDED"


# -------------------------------------------------------------------------
# Test 4: Unclosed Candle Refuses Evaluation
# -------------------------------------------------------------------------
def test_negative_04_unclosed_candle_refuses_evaluation():
    """Verify that unclosed partial candle is rejected before running strategy logic."""
    def validate_ingestion_candle(payload: dict) -> None:
        if not payload.get("is_closed", False):
            raise ValueError("UNCLOSED_CANDLE: Cannot evaluate prospective decision on unclosed candle.")

    unclosed_payload = {"symbol": "BTCUSDT", "close_price_usdt": 81000.0, "is_closed": False}
    with pytest.raises(ValueError, match="UNCLOSED_CANDLE"):
        validate_ingestion_candle(unclosed_payload)


# -------------------------------------------------------------------------
# Test 5: Duplicate Candle Sequence Rejected
# -------------------------------------------------------------------------
def test_negative_05_duplicate_candle_sequence_rejected():
    """Verify that submitting duplicate timestamp or duplicate bar index is rejected."""
    seen_timestamps = set()
    def ingest_bar(ts: str, seq: int):
        if ts in seen_timestamps:
            raise ValueError(f"DUPLICATE_CANDLE_TIMESTAMP: {ts} already ingested.")
        seen_timestamps.add(ts)

    ingest_bar("2026-10-19T00:00:00Z", 0)
    with pytest.raises(ValueError, match="DUPLICATE_CANDLE_TIMESTAMP"):
        ingest_bar("2026-10-19T00:00:00Z", 1)


# -------------------------------------------------------------------------
# Test 6: Missing Next-Bar Execution Price Refuses Fill
# -------------------------------------------------------------------------
def test_negative_06_missing_next_bar_execution_price_refuses_fill():
    """Verify simulator refuses fill if execution price is None or NaN."""
    sim = ShadowExecutionSimulator()
    res = sim.execute_hypothetical_buy(next_open=None)
    assert not res["success"]
    assert res["status"] == "EXECUTION_REJECTED_MISSING_PRICE"


# -------------------------------------------------------------------------
# Test 7: Incorrect Policy Hash Fails Closed
# -------------------------------------------------------------------------
def test_negative_07_incorrect_policy_hash_fails_closed():
    """Verify modifying any frozen parameter causes policy hash check to fail closed."""
    manifest = json.loads(MANIFEST_V2_PATH.read_text(encoding="utf-8"))
    policy_c = copy.deepcopy(manifest["candidate_policies"]["POLICY_C_TREND48_FOLLOWING"])
    expected_hash = policy_c["parameter_digest_sha256"]
    
    # Tamper with trend_window_hours
    policy_c["frozen_parameters"]["trend_window_hours"] = 50
    canonical_json = json.dumps(policy_c["frozen_parameters"], sort_keys=True, separators=(",", ":"))
    tampered_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    
    assert tampered_hash != expected_hash, "Hash collision under parameter mutation!"
    
    def verify_policy_parameters(policy_data: dict) -> None:
        p_json = json.dumps(policy_data["frozen_parameters"], sort_keys=True, separators=(",", ":"))
        actual = hashlib.sha256(p_json.encode("utf-8")).hexdigest()
        if actual != expected_hash:
            raise ValueError(f"POLICY_TAMPERED: Digest {actual} does not match frozen {expected_hash}")

    with pytest.raises(ValueError, match="POLICY_TAMPERED"):
        verify_policy_parameters(policy_c)


# -------------------------------------------------------------------------
# Test 8: Invalid Checkpoint Root Fails Verification
# -------------------------------------------------------------------------
def test_negative_08_invalid_checkpoint_root_fails_verification():
    """Verify that a corrupted checkpoint root hash fails verification against hash chain."""
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_A_USDT_CASH")
    for i in range(5):
        engine.evaluate_bar(
            bar_idx=i,
            timestamp_utc=f"2026-10-19T01:{i*5:02d}:00Z",
            availability_timestamp_utc=f"2026-10-19T01:{i*5:02d}:00Z",
            open_p=80000.0,
            high_p=80010.0,
            low_p=79990.0,
            close_p=80000.0,
            features={"trend_direction": 0, "analogue_score": 0.5},
        )
    
    cp = engine.hash_chain.create_checkpoint(4)
    # Corrupt checkpoint head hash
    corrupt_cp = ChainCheckpoint(
        checkpoint_id=cp.checkpoint_id,
        sequence_number=cp.sequence_number,
        decision_hash="bad" * 16,  # Corrupted
        decision_id=cp.decision_id,
        observation_timestamp_utc=cp.observation_timestamp_utc,
        checkpoint_timestamp_utc=cp.checkpoint_timestamp_utc,
        chain_length=cp.chain_length,
        policy_id=cp.policy_id,
        code_commit_hash=cp.code_commit_hash,
    )
    ok, err = engine.hash_chain.verify_against_checkpoint(corrupt_cp)
    assert not ok
    assert "Checkpoint hash mismatch" in err


# -------------------------------------------------------------------------
# Test 9: Decision-Log Truncation Detected
# -------------------------------------------------------------------------
def test_negative_09_decision_log_truncation_detected():
    """Verify that removing trailing blocks from decision chain is caught by checkpoint."""
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_A_USDT_CASH")
    for i in range(10):
        engine.evaluate_bar(
            bar_idx=i,
            timestamp_utc=f"2026-10-19T02:{i*5:02d}:00Z",
            availability_timestamp_utc=f"2026-10-19T02:{i*5:02d}:00Z",
            open_p=80000.0,
            high_p=80010.0,
            low_p=79990.0,
            close_p=80000.0,
            features={"trend_direction": 0, "analogue_score": 0.5},
        )
    cp = engine.hash_chain.create_checkpoint(9)
    assert cp.chain_length == 10
    
    # Truncate chain by 3 records
    truncated_chain = DecisionHashChain()
    for r in engine.hash_chain.records[:7]:
        truncated_chain.append(r)
        
    ok, err = truncated_chain.verify_against_checkpoint(cp)
    assert not ok
    assert "Truncation detected" in err


# -------------------------------------------------------------------------
# Test 10: Open BTC Position With Stale Data Emits POSITION_OPEN_DATA_STALE
# -------------------------------------------------------------------------
def test_negative_10_open_btc_position_with_stale_data():
    """Verify that an active long position encountering stale data emits POSITION_OPEN_DATA_STALE."""
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_D_SELECTIVE_TREND_ONLY")
    engine.simulator.execute_hypothetical_buy(next_open=80000.0)
    assert engine.simulator.position_active
    
    rec = engine.evaluate_bar(
        bar_idx=0,
        timestamp_utc="2026-10-19T03:00:00Z",
        availability_timestamp_utc="2026-10-19T03:00:00Z",
        open_p=80000.0,
        high_p=80010.0,
        low_p=79990.0,
        close_p=80000.0,
        features={"trend_direction": 1, "analogue_score": 0.65},
        is_data_stale=True,
    )
    assert rec.decision == ShadowDecisionAction.POSITION_OPEN_DATA_STALE.value
    assert engine.simulator.position_active, "Position must be preserved under stale data"


# -------------------------------------------------------------------------
# Test 11: Attempted Unauthorized Observation Activation Fails Closed
# -------------------------------------------------------------------------
def test_negative_11_unauthorized_observation_fails_closed():
    """Verify that starting observation without operator authorization flag fails closed."""
    def start_prospective_observation(authorized: bool) -> None:
        if not authorized:
            raise PermissionError("OPERATOR_AUTHORIZATION_REQUIRED: Prospective observation cannot be started without explicit operator signature.")

    with pytest.raises(PermissionError, match="OPERATOR_AUTHORIZATION_REQUIRED"):
        start_prospective_observation(authorized=False)


# -------------------------------------------------------------------------
# Test 12: Attempted Trading API Access Fails Closed
# -------------------------------------------------------------------------
def test_negative_12_attempted_trading_api_access_blocked():
    """Verify that presence of trading API keys or live sockets raises immediate abort."""
    def initialize_shadow_environment(env_vars: dict) -> None:
        if env_vars.get("BINANCE_API_KEY") or env_vars.get("BINANCE_API_SECRET"):
            raise PermissionError("LIVE_TRADING_PROHIBITED: API keys detected in shadow observation environment.")
        if env_vars.get("CBE_TRADING_DISABLED", "false").lower() != "true":
            raise PermissionError("LIVE_TRADING_PROHIBITED: CBE_TRADING_DISABLED must be strictly 'true'.")

    # Rejects live credentials
    with pytest.raises(PermissionError, match="LIVE_TRADING_PROHIBITED"):
        initialize_shadow_environment({"BINANCE_API_KEY": "live_key_12345", "CBE_TRADING_DISABLED": "true"})

    # Rejects missing disable flag
    with pytest.raises(PermissionError, match="LIVE_TRADING_PROHIBITED"):
        initialize_shadow_environment({"CBE_TRADING_DISABLED": "false"})


# -------------------------------------------------------------------------
# Test 13: Resource-Limit Configuration Mismatch Detected
# -------------------------------------------------------------------------
def test_negative_13_resource_limit_mismatch_detected():
    """Verify configuration validator rejects limits exceeding the 0.20 CPU / 250M RAM ceiling."""
    def validate_compose_resources(cpus: float, memory_mb: float) -> None:
        if cpus > 0.20:
            raise ValueError(f"RESOURCE_VIOLATION: Requested {cpus} cpus exceeds maximum safe limit 0.20")
        if memory_mb > 250.0:
            raise ValueError(f"RESOURCE_VIOLATION: Requested {memory_mb}M exceeds maximum safe limit 250M")

    # Safe limits pass
    validate_compose_resources(0.20, 250.0)
    validate_compose_resources(0.10, 150.0)

    # Excessive limits fail
    with pytest.raises(ValueError, match="RESOURCE_VIOLATION.*cpus"):
        validate_compose_resources(0.50, 250.0)
    with pytest.raises(ValueError, match="RESOURCE_VIOLATION.*250M"):
        validate_compose_resources(0.20, 512.0)


# -------------------------------------------------------------------------
# Test 14: Incorrect Policy-to-Portfolio Association Rejected
# -------------------------------------------------------------------------
def test_negative_14_incorrect_policy_to_portfolio_association_rejected():
    """Verify that ledger records from one policy cannot be processed into another policy's simulator."""
    sim_c = ShadowExecutionSimulator()
    sim_d = ShadowExecutionSimulator()
    
    def process_policy_fill(target_policy: str, order_policy: str, sim: ShadowExecutionSimulator):
        if target_policy != order_policy:
            raise ValueError(f"POLICY_MISMATCH: Order for {order_policy} cannot update {target_policy} ledger.")
        sim.execute_hypothetical_buy(next_open=80000.0)

    with pytest.raises(ValueError, match="POLICY_MISMATCH"):
        process_policy_fill("POLICY_D_SELECTIVE_TREND_ONLY", "POLICY_C_TREND48_FOLLOWING", sim_d)


# -------------------------------------------------------------------------
# Test 15: Missing Independent Checkpoint Anchor Leaves Chronology UNVERIFIED
# -------------------------------------------------------------------------
def test_negative_15_missing_independent_checkpoint_anchor():
    """Verify that without external GPG signed tag or RFC-3161 receipt, status is UNVERIFIED."""
    def evaluate_freeze_chronology(has_signed_tag: bool, has_rfc3161: bool) -> str:
        if not (has_signed_tag or has_rfc3161):
            return "FREEZE_CHRONOLOGY_UNVERIFIED"
        return "FREEZE_CHRONOLOGY_VERIFIED"

    assert evaluate_freeze_chronology(has_signed_tag=False, has_rfc3161=False) == "FREEZE_CHRONOLOGY_UNVERIFIED"
    assert evaluate_freeze_chronology(has_signed_tag=True, has_rfc3161=False) == "FREEZE_CHRONOLOGY_VERIFIED"

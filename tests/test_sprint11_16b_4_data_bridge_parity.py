"""Deterministic Negative Regression & Policy Parity Test Suite for Sprint 11.16B.4.

Sprint 11.16B.4: Frozen Policy Parity, Analogue Integrity & Crash-Safe Data Bridge.
Covers all 18 required negative regression test scenarios:
1. Reject unclosed candle.
2. Reject out-of-order candle.
3. Reject duplicate timestamp candle.
4. Invalidate warmup on detected gap (>300s).
5. Disallow feature evaluation with 863 candles.
6. Allow feature evaluation with exactly 864 contiguous candles.
7. Reject seed with modified OHLCV data (SHA-256 mismatch).
8. Reject seed with non-contiguous timestamps.
9. Reject seed with fewer than 864 candles.
10. Fail closed on truncated state file.
11. Fail closed on corrupt JSON state file.
12. Fail closed on state file with invalid candle data.
13. Prevent duplicate execution after restart.
14. Reject lookahead timestamps (T_avail < T_close).
15. Reject execution at current close price.
16. Reject execution when next open price is unavailable.
17. Reject execution when decision timestamp is after next candle close.
18. Confirm Policy E fails closed (no trades) when analogue is blocked.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import pytest

from coin_behavior_engine.research_lab.shadow_decision_protocol import (
    ProspectiveIntegrityEngine,
    ShadowDecisionAction,
    ShadowExecutionSimulator,
)
from coin_behavior_engine.research_lab.shadow_market_data_bridge import (
    AnalogueArtifactLoader,
    BridgeStatus,
    CandleStreamType,
    FrozenFeatureAdapter,
    HistoricalSeedProvenance,
    MarketCandle,
    PersistentRollingBuffer,
    ShadowMarketDataBridge,
    CANONICAL_ANALOGUE_CSV_SHA256,
    MINIMUM_WARMUP_BARS,
)


def _generate_synthetic_candle(idx: int, base_time: datetime, price: float = 80000.0, is_closed: bool = True) -> MarketCandle:
    t_open = base_time + timedelta(minutes=5 * idx)
    t_close = t_open + timedelta(minutes=4, seconds=59)
    return MarketCandle(
        symbol="BTCUSDT",
        interval="5m",
        timestamp_open_utc=t_open.strftime("%Y-%m-%dT%H:%M:%SZ"),
        timestamp_close_utc=t_close.strftime("%Y-%m-%dT%H:%M:%SZ"),
        open_p=price,
        high_p=price * 1.001,
        low_p=price * 0.999,
        close_p=price,
        volume_base=10.0,
        volume_usdt=price * 10.0,
        is_closed=is_closed,
        stream_type=CandleStreamType.HISTORICAL_SEED_WARMUP,
        sequence_number=idx,
        provenance="TEST_FIXTURE_11_16B_4",
    )


def _generate_snapshot_dict(idx: int, base_time: datetime, price: float = 80000.0, is_closed: bool = True) -> dict:
    t_open = base_time + timedelta(minutes=5 * idx)
    t_close = t_open + timedelta(minutes=4, seconds=59)
    return {
        "symbol": "BTCUSDT",
        "candle_interval": "5m",
        "timestamp_open_utc": t_open.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "timestamp_close_utc": t_close.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "open_price_usdt": price,
        "high_price_usdt": price * 1.001,
        "low_price_usdt": price * 0.999,
        "close_price_usdt": price,
        "volume_base": 10.0,
        "volume_usdt": price * 10.0,
        "is_closed": is_closed,
        "writer_heartbeat_utc": t_close.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "snapshot_generation_timestamp_utc": t_close.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def _create_seed_and_prov(count: int, base_time: datetime, seed_id: str = "SEED-VALID"):
    seed = [_generate_synthetic_candle(i, base_time) for i in range(count)]
    digest = HistoricalSeedProvenance.compute_canonical_digest(seed)
    prov = HistoricalSeedProvenance(
        seed_id=seed_id,
        dataset_name="canonical_test_dataset",
        dataset_sha256=digest,
        start_timestamp_utc=seed[0].timestamp_open_utc,
        end_timestamp_utc=seed[-1].timestamp_open_utc,
        candle_count=count,
        is_authorized=True,
    )
    return seed, prov


# -------------------------------------------------------------------------
# Test 1: Reject unclosed candle
# -------------------------------------------------------------------------
def test_01_reject_unclosed_candle():
    bridge = ShadowMarketDataBridge(min_warmup_bars=10)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    snap = _generate_snapshot_dict(0, base_t, is_closed=False)
    payload = bridge.ingest_snapshot_payload(snap, snap["timestamp_close_utc"])

    assert payload.status == BridgeStatus.UNCLOSED_CANDLE
    assert not payload.execution_eligible
    assert "UNCLOSED_CANDLE" in payload.message

    candle = _generate_synthetic_candle(0, base_t, is_closed=False)
    ok, err = bridge.buffer.append_candle(candle)
    assert not ok
    assert "UNCLOSED_CANDLE" in str(err)


# -------------------------------------------------------------------------
# Test 2: Reject out-of-order candle
# -------------------------------------------------------------------------
def test_02_reject_out_of_order_candle():
    buffer = PersistentRollingBuffer(capacity=100, min_warmup_bars=10)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    c1 = _generate_synthetic_candle(1, base_t)
    c0 = _generate_synthetic_candle(0, base_t)

    ok1, _ = buffer.append_candle(c1)
    assert ok1

    ok0, err0 = buffer.append_candle(c0)
    assert not ok0
    assert "TIME_INVERSION" in str(err0)


# -------------------------------------------------------------------------
# Test 3: Reject duplicate timestamp candle
# -------------------------------------------------------------------------
def test_03_reject_duplicate_timestamp_candle():
    bridge = ShadowMarketDataBridge(min_warmup_bars=10)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    snap0 = _generate_snapshot_dict(0, base_t)

    p0 = bridge.ingest_snapshot_payload(snap0, snap0["timestamp_close_utc"])
    assert p0.status == BridgeStatus.WARMUP_BUFFERING

    # Attempt appending exact same candle again
    p0_dup = bridge.ingest_snapshot_payload(snap0, snap0["timestamp_close_utc"])
    assert p0_dup.status == BridgeStatus.DUPLICATE_CANDLE
    assert not p0_dup.execution_eligible


# -------------------------------------------------------------------------
# Test 4: Invalidate warmup on detected gap (>300s)
# -------------------------------------------------------------------------
def test_04_invalidate_warmup_on_detected_gap():
    bridge = ShadowMarketDataBridge(min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    seed, prov = _create_seed_and_prov(864, base_t)

    ok, _ = bridge.buffer.ingest_seed_candles(seed, prov)
    assert ok
    assert bridge.buffer.is_warmup_ready

    # Next candle skips 1 bar (10m gap = 600s > 300s)
    gap_snap = _generate_snapshot_dict(865, base_t)
    payload = bridge.ingest_snapshot_payload(gap_snap, gap_snap["timestamp_close_utc"])

    assert payload.status == BridgeStatus.GAP_DETECTED
    assert not payload.is_warmup_ready
    assert not payload.execution_eligible
    assert not bridge.buffer.is_warmup_ready
    assert bridge.buffer.gap_detected
    assert len(bridge.buffer) == 0  # Pre-gap disjoint bars cleared


# -------------------------------------------------------------------------
# Test 5: Disallow feature evaluation with 863 candles
# -------------------------------------------------------------------------
def test_05_disallow_feature_evaluation_with_863_candles():
    bridge = ShadowMarketDataBridge(min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Ingest 863 candles manually into buffer
    for i in range(863):
        c = _generate_synthetic_candle(i, base_t)
        ok, _ = bridge.buffer.append_candle(c)
        assert ok

    assert not bridge.buffer.is_warmup_ready
    assert len(bridge.buffer) == 863

    ok_feat, feat, err = bridge.feature_adapter.extract_features()
    assert not ok_feat
    assert feat is None
    assert "INSUFFICIENT_WARMUP" in str(err)


# -------------------------------------------------------------------------
# Test 6: Allow feature evaluation with exactly 864 contiguous candles
# -------------------------------------------------------------------------
def test_06_allow_feature_evaluation_with_exactly_864_contiguous_candles():
    bridge = ShadowMarketDataBridge(min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    seed, prov = _create_seed_and_prov(864, base_t)

    ok, msg = bridge.buffer.ingest_seed_candles(seed, prov)
    assert ok
    assert bridge.buffer.is_warmup_ready
    assert len(bridge.buffer) == 864

    ok_feat, feat, err = bridge.feature_adapter.extract_features()
    assert ok_feat
    assert feat is not None
    assert err is None
    assert feat["sma_864"] == 80000.0
    assert feat["sma_288"] == 80000.0


# -------------------------------------------------------------------------
# Test 7: Reject seed with modified OHLCV data (SHA-256 mismatch)
# -------------------------------------------------------------------------
def test_07_reject_seed_with_modified_ohlcv_data_sha256_mismatch():
    bridge = ShadowMarketDataBridge(min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    seed, prov = _create_seed_and_prov(864, base_t)

    # Tamper with single candle's price
    tampered_seed = list(seed)
    c_tampered = MarketCandle(
        symbol=seed[100].symbol,
        interval=seed[100].interval,
        timestamp_open_utc=seed[100].timestamp_open_utc,
        timestamp_close_utc=seed[100].timestamp_close_utc,
        open_p=seed[100].open_p,
        high_p=seed[100].high_p,
        low_p=seed[100].low_p,
        close_p=seed[100].close_p + 1.0,  # Tampered +$1.0
        volume_base=seed[100].volume_base,
        volume_usdt=seed[100].volume_usdt,
        is_closed=seed[100].is_closed,
        stream_type=seed[100].stream_type,
        sequence_number=seed[100].sequence_number,
        provenance=seed[100].provenance,
    )
    tampered_seed[100] = c_tampered

    ok, err = bridge.buffer.ingest_seed_candles(tampered_seed, prov)
    assert not ok
    assert "HASH_MISMATCH" in str(err)
    assert not bridge.buffer.is_warmup_ready
    assert len(bridge.buffer) == 0


# -------------------------------------------------------------------------
# Test 8: Reject seed with non-contiguous timestamps
# -------------------------------------------------------------------------
def test_08_reject_seed_with_non_contiguous_timestamps():
    bridge = ShadowMarketDataBridge(min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    seed, _ = _create_seed_and_prov(864, base_t)

    # Introduce gap at bar 50
    non_contiguous_seed = list(seed[:50])
    for i in range(50, 864):
        # Shift time forward by 10 minutes (gap)
        c = _generate_synthetic_candle(i + 2, base_t)
        non_contiguous_seed.append(c)

    digest = HistoricalSeedProvenance.compute_canonical_digest(non_contiguous_seed)
    prov = HistoricalSeedProvenance(
        seed_id="SEED-NON-CONTIG",
        dataset_name="canonical",
        dataset_sha256=digest,
        start_timestamp_utc=non_contiguous_seed[0].timestamp_open_utc,
        end_timestamp_utc=non_contiguous_seed[-1].timestamp_open_utc,
        candle_count=864,
        is_authorized=True,
    )

    ok, err = bridge.buffer.ingest_seed_candles(non_contiguous_seed, prov)
    assert not ok
    assert "NON_CONTIGUOUS_TIMESTAMPS" in str(err)
    assert len(bridge.buffer) == 0


# -------------------------------------------------------------------------
# Test 9: Reject seed with fewer than 864 candles
# -------------------------------------------------------------------------
def test_09_reject_seed_with_fewer_than_864_candles():
    bridge = ShadowMarketDataBridge(min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    seed, prov = _create_seed_and_prov(500, base_t)

    ok, err = bridge.buffer.ingest_seed_candles(seed, prov)
    assert not ok
    assert "INSUFFICIENT_CANDLES" in str(err)
    assert not bridge.buffer.is_warmup_ready
    assert len(bridge.buffer) == 0


# -------------------------------------------------------------------------
# Test 10: Fail closed on truncated state file
# -------------------------------------------------------------------------
def test_10_fail_closed_on_truncated_state_file():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
        state_path = Path(f.name)

    buffer = PersistentRollingBuffer(capacity=100, min_warmup_bars=10, state_file=state_path)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    for i in range(20):
        buffer.append_candle(_generate_synthetic_candle(i, base_t))
    buffer.save_state()

    # Truncate state file by 50%
    content = state_path.read_text(encoding="utf-8")
    state_path.write_text(content[: len(content) // 2], encoding="utf-8")

    new_buffer = PersistentRollingBuffer(capacity=100, min_warmup_bars=10, state_file=state_path)
    ok = new_buffer.load_state()
    assert not ok
    assert len(new_buffer) == 0
    assert not new_buffer.is_warmup_ready

    state_path.unlink()


# -------------------------------------------------------------------------
# Test 11: Fail closed on corrupt JSON state file
# -------------------------------------------------------------------------
def test_11_fail_closed_on_corrupt_json_state_file():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
        f.write("{ INVALID_JSON_SYNTAX_CORRUPT: true, ")
        state_path = Path(f.name)

    buffer = PersistentRollingBuffer(capacity=100, min_warmup_bars=10, state_file=state_path)
    ok = buffer.load_state()
    assert not ok
    assert len(buffer) == 0
    assert not buffer.is_warmup_ready

    state_path.unlink()


# -------------------------------------------------------------------------
# Test 12: Fail closed on state file with invalid candle data
# -------------------------------------------------------------------------
def test_12_fail_closed_on_state_file_with_invalid_candle_data():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
        state_path = Path(f.name)

    buffer = PersistentRollingBuffer(capacity=100, min_warmup_bars=10, state_file=state_path)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    for i in range(15):
        buffer.append_candle(_generate_synthetic_candle(i, base_t))
    buffer.save_state()

    # Corrupt a candle's price in the file and re-compute digest
    raw_data = json.loads(state_path.read_text(encoding="utf-8"))
    raw_data["payload"]["candles"][5]["close_p"] = -500.0  # Invalid negative price
    import hashlib
    canon = json.dumps(raw_data["payload"], sort_keys=True, separators=(",", ":"))
    raw_data["state_sha256"] = hashlib.sha256(canon.encode("utf-8")).hexdigest()
    state_path.write_text(json.dumps(raw_data), encoding="utf-8")

    new_buffer = PersistentRollingBuffer(capacity=100, min_warmup_bars=10, state_file=state_path)
    ok = new_buffer.load_state()
    assert not ok
    assert len(new_buffer) == 0
    assert not new_buffer.is_warmup_ready

    state_path.unlink()


# -------------------------------------------------------------------------
# Test 13: Prevent duplicate execution after restart
# -------------------------------------------------------------------------
def test_13_prevent_duplicate_execution_after_restart():
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json") as f:
        state_path = Path(f.name)

    bridge = ShadowMarketDataBridge(state_file=state_path)
    sim = ShadowExecutionSimulator(initial_capital_usdt=10000.0)

    # Initial fill
    res1 = bridge.execute_causal_fill(sim, "BUY", next_open_price=80000.0, decision_id="DEC-CRASH-SAFE-001")
    assert res1["success"]
    assert bridge.buffer.is_executed("DEC-CRASH-SAFE-001")

    # Persist state
    bridge.buffer.save_state()

    # Recover in new bridge instance
    recovered_bridge = ShadowMarketDataBridge(state_file=state_path)
    recovered_bridge.buffer.load_state()
    assert recovered_bridge.buffer.is_executed("DEC-CRASH-SAFE-001")

    # Re-executing same decision must be rejected
    res_dup = recovered_bridge.execute_causal_fill(sim, "BUY", next_open_price=80000.0, decision_id="DEC-CRASH-SAFE-001")
    assert not res_dup["success"]
    assert res_dup["status"] == "REJECTED_DUPLICATE_EXECUTION"

    state_path.unlink()


# -------------------------------------------------------------------------
# Test 14: Reject lookahead timestamps (T_avail < T_close)
# -------------------------------------------------------------------------
def test_14_reject_lookahead_timestamps():
    bridge = ShadowMarketDataBridge(min_warmup_bars=10)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    snap = _generate_snapshot_dict(0, base_t)

    # Availability earlier than candle close
    avail_ts = "2026-01-01T00:03:00Z"
    payload = bridge.ingest_snapshot_payload(snap, avail_ts)

    assert payload.status == BridgeStatus.SNAPSHOT_CORRUPT
    assert not payload.execution_eligible
    assert "LOOKAHEAD_VIOLATION" in payload.message


# -------------------------------------------------------------------------
# Test 15: Reject execution at current close price
# -------------------------------------------------------------------------
def test_15_reject_execution_at_current_close_price():
    bridge = ShadowMarketDataBridge()
    sim = ShadowExecutionSimulator(initial_capital_usdt=10000.0)

    # Next open price exactly equal to current close price violates causality check
    res = bridge.execute_causal_fill(
        sim,
        "BUY",
        next_open_price=80000.0,
        current_close_price=80000.0,
    )
    assert not res["success"]
    assert res["status"] == "EXECUTION_REFUSED_AT_CLOSE_PRICE"


# -------------------------------------------------------------------------
# Test 16: Reject execution when next open price is unavailable
# -------------------------------------------------------------------------
def test_16_reject_execution_when_next_open_price_is_unavailable():
    bridge = ShadowMarketDataBridge()
    sim = ShadowExecutionSimulator(initial_capital_usdt=10000.0)

    # None
    res_none = bridge.execute_causal_fill(sim, "BUY", next_open_price=None)
    assert not res_none["success"]
    assert res_none["status"] == "EXECUTION_REFUSED_MISSING_NEXT_OPEN"

    # NaN
    res_nan = bridge.execute_causal_fill(sim, "BUY", next_open_price=float("nan"))
    assert not res_nan["success"]
    assert res_nan["status"] == "EXECUTION_REFUSED_MISSING_NEXT_OPEN"

    # <= 0
    res_zero = bridge.execute_causal_fill(sim, "BUY", next_open_price=-10.0)
    assert not res_zero["success"]
    assert res_zero["status"] == "EXECUTION_REFUSED_MISSING_NEXT_OPEN"


# -------------------------------------------------------------------------
# Test 17: Reject execution when decision timestamp is after next candle close
# -------------------------------------------------------------------------
def test_17_reject_execution_when_decision_timestamp_is_after_next_candle_close():
    bridge = ShadowMarketDataBridge()
    sim = ShadowExecutionSimulator(initial_capital_usdt=10000.0)

    # T_dec = 00:10:05, T_next_close = 00:09:59 (decision arrived late, window expired)
    res = bridge.execute_causal_fill(
        sim,
        "BUY",
        next_open_price=80050.0,
        decision_timestamp_utc="2026-01-01T00:10:05Z",
        next_candle_close_utc="2026-01-01T00:09:59Z",
        current_close_price=80000.0,
    )
    assert not res["success"]
    assert res["status"] == "EXECUTION_REFUSED_EXPIRED_WINDOW"


# -------------------------------------------------------------------------
# Test 18: Confirm Policy E fails closed (no trades) when analogue is blocked
# -------------------------------------------------------------------------
def test_18_confirm_policy_e_fails_closed_when_analogue_is_blocked():
    bridge = ShadowMarketDataBridge(min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    seed, prov = _create_seed_and_prov(864, base_t)
    bridge.buffer.ingest_seed_candles(seed, prov)

    bridge.initialize_analogue_library()
    ok_feat, feat, _ = bridge.feature_adapter.extract_features()
    assert ok_feat

    # Hardcoded probability 0.65 must be gone; analogue_prob is None, status is BLOCKED
    assert feat["analogue_prob"] is None
    assert feat["analogue_ok"] is False
    assert feat["policy_e_status"] == "BLOCKED_ANALOGUE_PARITY"

    # Evaluate Policy E with features
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_E_SELECTIVE_ANALOGUE_ASSISTED")
    dec = engine.evaluate_bar(
        bar_idx=0,
        timestamp_utc="2026-01-04T00:00:00Z",
        availability_timestamp_utc="2026-01-04T00:00:30Z",
        open_p=80000.0,
        high_p=80050.0,
        low_p=79950.0,
        close_p=80000.0,
        features=feat,
    )

    # Must fail closed to WAIT_USDT (or abstention), 0 positions, 0 trades
    assert dec.decision == ShadowDecisionAction.WAIT_USDT.value
    assert not engine.simulator.position_active
    assert engine.simulator.trade_count == 0

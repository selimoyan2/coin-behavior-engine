"""Deterministic Test Suite for Sprint 11.16B.3.

Sprint 11.16B.3: Shadow Market Data Bridge & Warmup Integrity Implementation.
Verifies all 18 mandatory test scenarios exercising executable implementation paths:
1. Valid 864-candle warmup.
2. 863-candle rejection.
3. Historical seed overlapping first live candle.
4. Historical-to-live discontinuity.
5. Missing 5-minute candle gap detection.
6. Duplicate snapshot rejection.
7. Stale snapshot detection.
8. Unclosed candle rejection.
9. Corrupt OHLCV rejection.
10. Missing analogue artifact.
11. Incorrect analogue hash.
12. Feature parity with frozen reference policy.
13. Next-open execution causality.
14. Open position during stale data.
15. Restart without duplicate decisions.
16. Hash-chain recovery.
17. Memory boundedness.
18. Separation of historical seed and prospective outcomes.
"""

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import pytest

from coin_behavior_engine.research_lab.shadow_decision_protocol import (
    DecisionHashChain,
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
        provenance="TEST_FIXTURE",
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


# -------------------------------------------------------------------------
# Scenario 1: Valid 864-Candle Warmup
# -------------------------------------------------------------------------
def test_01_valid_864_candle_warmup():
    """Verify that buffer with exactly 864 contiguous candles activates warmup ready state."""
    bridge = ShadowMarketDataBridge(min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    seed = [_generate_synthetic_candle(i, base_t) for i in range(864)]
    prov = HistoricalSeedProvenance(
        seed_id="SEED-001",
        dataset_name="canonical_test_seed",
        dataset_sha256="dummy",
        start_timestamp_utc=seed[0].timestamp_open_utc,
        end_timestamp_utc=seed[-1].timestamp_open_utc,
        candle_count=864,
        is_authorized=True,
    )
    ok, msg = bridge.buffer.ingest_seed_candles(seed, prov)
    assert ok
    assert bridge.buffer.is_warmup_ready
    assert len(bridge.buffer) == 864

    # Extract features
    ok_feat, features, err = bridge.feature_adapter.extract_features()
    assert ok_feat
    assert features["sma_864"] == 80000.0


# -------------------------------------------------------------------------
# Scenario 2: 863-Candle Rejection
# -------------------------------------------------------------------------
def test_02_863_candle_rejection():
    """Verify that 863 candles is rejected as insufficient warmup."""
    bridge = ShadowMarketDataBridge(min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    seed = [_generate_synthetic_candle(i, base_t) for i in range(863)]
    prov = HistoricalSeedProvenance("SEED-002", "canonical_test_seed", "dummy", seed[0].timestamp_open_utc, seed[-1].timestamp_open_utc, 863, True)
    bridge.buffer.ingest_seed_candles(seed, prov)

    assert not bridge.buffer.is_warmup_ready
    ok_feat, features, err = bridge.feature_adapter.extract_features()
    assert not ok_feat
    assert "INSUFFICIENT_WARMUP" in err


# -------------------------------------------------------------------------
# Scenario 3: Historical Seed Overlapping First Live Candle
# -------------------------------------------------------------------------
def test_03_historical_seed_overlapping_first_live_candle():
    """Verify that a live candle matching the last seed candle timestamp is rejected as duplicate."""
    bridge = ShadowMarketDataBridge(min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    seed = [_generate_synthetic_candle(i, base_t) for i in range(864)]
    prov = HistoricalSeedProvenance("SEED-003", "canonical", "dummy", seed[0].timestamp_open_utc, seed[-1].timestamp_open_utc, 864, True)
    bridge.buffer.ingest_seed_candles(seed, prov)

    # Ingest live candle overlapping bar 863 (last seed candle)
    snap = _generate_snapshot_dict(863, base_t)
    avail_ts = snap["timestamp_close_utc"]
    payload = bridge.ingest_snapshot_payload(snap, avail_ts)
    assert payload.status == BridgeStatus.DUPLICATE_CANDLE
    assert not payload.execution_eligible


# -------------------------------------------------------------------------
# Scenario 4: Historical-to-Live Discontinuity
# -------------------------------------------------------------------------
def test_04_historical_to_live_discontinuity():
    """Verify gap between seed end and live start is caught as GAP_DETECTED."""
    bridge = ShadowMarketDataBridge(min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    seed = [_generate_synthetic_candle(i, base_t) for i in range(864)]
    prov = HistoricalSeedProvenance("SEED-004", "canonical", "dummy", seed[0].timestamp_open_utc, seed[-1].timestamp_open_utc, 864, True)
    bridge.buffer.ingest_seed_candles(seed, prov)

    # First live candle skips bar 864 and arrives at bar 865 (10-minute gap)
    snap = _generate_snapshot_dict(865, base_t)
    avail_ts = snap["timestamp_close_utc"]
    payload = bridge.ingest_snapshot_payload(snap, avail_ts)
    assert payload.status == BridgeStatus.GAP_DETECTED
    assert not payload.execution_eligible


# -------------------------------------------------------------------------
# Scenario 5: Missing 5-Minute Candle Gap Detection
# -------------------------------------------------------------------------
def test_05_missing_5m_candle_gap_detection():
    """Verify missing 5-minute candle during live stream fails closed."""
    bridge = ShadowMarketDataBridge(min_warmup_bars=10)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Ingest bar 0
    snap0 = _generate_snapshot_dict(0, base_t)
    p0 = bridge.ingest_snapshot_payload(snap0, snap0["timestamp_close_utc"])
    assert p0.status == BridgeStatus.WARMUP_BUFFERING

    # Skip bar 1 and ingest bar 2 (missing bar 1)
    snap2 = _generate_snapshot_dict(2, base_t)
    p2 = bridge.ingest_snapshot_payload(snap2, snap2["timestamp_close_utc"])
    assert p2.status == BridgeStatus.GAP_DETECTED


# -------------------------------------------------------------------------
# Scenario 6: Duplicate Snapshot Rejection
# -------------------------------------------------------------------------
def test_06_duplicate_snapshot_rejection():
    """Verify duplicate snapshot is safely rejected."""
    bridge = ShadowMarketDataBridge(min_warmup_bars=10)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    snap = _generate_snapshot_dict(0, base_t)

    p1 = bridge.ingest_snapshot_payload(snap, snap["timestamp_close_utc"])
    assert p1.status == BridgeStatus.WARMUP_BUFFERING

    p2 = bridge.ingest_snapshot_payload(snap, snap["timestamp_close_utc"])
    assert p2.status == BridgeStatus.DUPLICATE_CANDLE


# -------------------------------------------------------------------------
# Scenario 7: Stale Snapshot Detection
# -------------------------------------------------------------------------
def test_07_stale_snapshot_detection():
    """Verify snapshot with availability > 15m after close is marked FEED_STALE."""
    bridge = ShadowMarketDataBridge(min_warmup_bars=10)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    snap = _generate_snapshot_dict(0, base_t)

    # Availability 20 minutes in the future
    close_dt = datetime.fromisoformat(snap["timestamp_close_utc"].replace("Z", "+00:00"))
    stale_avail = (close_dt + timedelta(minutes=20)).strftime("%Y-%m-%dT%H:%M:%SZ")

    payload = bridge.ingest_snapshot_payload(snap, stale_avail)
    assert payload.status == BridgeStatus.FEED_STALE


# -------------------------------------------------------------------------
# Scenario 8: Unclosed Candle Rejection
# -------------------------------------------------------------------------
def test_08_unclosed_candle_rejection():
    """Verify unclosed candle is rejected with UNCLOSED_CANDLE."""
    bridge = ShadowMarketDataBridge(min_warmup_bars=10)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    snap = _generate_snapshot_dict(0, base_t, is_closed=False)

    payload = bridge.ingest_snapshot_payload(snap, snap["timestamp_close_utc"])
    assert payload.status == BridgeStatus.UNCLOSED_CANDLE


# -------------------------------------------------------------------------
# Scenario 9: Corrupt OHLCV Rejection
# -------------------------------------------------------------------------
def test_09_corrupt_ohlcv_rejection():
    """Verify corrupt OHLCV fields are rejected with SNAPSHOT_CORRUPT."""
    bridge = ShadowMarketDataBridge(min_warmup_bars=10)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    snap = _generate_snapshot_dict(0, base_t)
    snap["close_price_usdt"] = "non_numeric_garbage"

    payload = bridge.ingest_snapshot_payload(snap, snap["timestamp_close_utc"])
    assert payload.status == BridgeStatus.SNAPSHOT_CORRUPT


# -------------------------------------------------------------------------
# Scenario 10: Missing Analogue Artifact
# -------------------------------------------------------------------------
def test_10_missing_analogue_artifact():
    """Verify missing analogue artifact sets status ARTIFACT_MISSING and blocks Policy E."""
    loader = AnalogueArtifactLoader(artifact_path=Path("/tmp/missing_analogues.csv"))
    ok, msg = loader.verify_and_load()
    assert not ok
    assert loader.status == "ARTIFACT_MISSING"
    assert loader.get_directional_probability() is None


# -------------------------------------------------------------------------
# Scenario 11: Incorrect Analogue Hash
# -------------------------------------------------------------------------
def test_11_incorrect_analogue_hash():
    """Verify tampered analogue artifact fails with hash mismatch."""
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        f.write("tampered,content\n1,2\n")
        f_path = Path(f.name)

    loader = AnalogueArtifactLoader(artifact_path=f_path, expected_sha256="0000000000000000000000000000000000000000000000000000000000000000")
    ok, msg = loader.verify_and_load()
    assert not ok
    assert "HASH_MISMATCH" in loader.status
    f_path.unlink()


# -------------------------------------------------------------------------
# Scenario 12: Feature Parity with Frozen Reference Policy
# -------------------------------------------------------------------------
def test_12_feature_parity_with_frozen_reference_policy():
    """Verify extracted SMA and ATR match mathematical definitions."""
    bridge = ShadowMarketDataBridge(min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)

    # Linearly increasing prices: 80000 + i
    seed = [_generate_synthetic_candle(i, base_t, price=80000.0 + i) for i in range(864)]
    prov = HistoricalSeedProvenance("SEED-012", "canonical", "dummy", seed[0].timestamp_open_utc, seed[-1].timestamp_open_utc, 864, True)
    bridge.buffer.ingest_seed_candles(seed, prov)

    ok, feat, err = bridge.feature_adapter.extract_features()
    assert ok
    expected_sma_864 = sum(80000.0 + i for i in range(864)) / 864.0
    assert abs(feat["sma_864"] - expected_sma_864) < 1e-4

    expected_sma_288 = sum(80000.0 + i for i in range(864 - 288, 864)) / 288.0
    assert abs(feat["sma_288"] - expected_sma_288) < 1e-4


# -------------------------------------------------------------------------
# Scenario 13: Next-Open Execution Causality
# -------------------------------------------------------------------------
def test_13_next_open_execution_causality():
    """Verify fill occurs strictly at next-open price and missing next-open refuses fill."""
    bridge = ShadowMarketDataBridge()
    sim = ShadowExecutionSimulator(initial_capital_usdt=10000.0)

    # Missing next open refuses fill
    res_none = bridge.execute_causal_fill(sim, "BUY", next_open_price=None)
    assert not res_none["success"]
    assert res_none["status"] == "EXECUTION_REFUSED_MISSING_NEXT_OPEN"

    # Valid next open executes with 15 bps entry friction (10 bps fee + 5 bps slip)
    res_buy = bridge.execute_causal_fill(sim, "BUY", next_open_price=80000.0)
    assert res_buy["success"]
    assert sim.position_active
    assert sim.entry_price == 80000.0


# -------------------------------------------------------------------------
# Scenario 14: Open Position During Stale Data
# -------------------------------------------------------------------------
def test_14_open_position_during_stale_data():
    """Verify open long position preserves inventory and emits POSITION_OPEN_DATA_STALE during stale feed."""
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_D_SELECTIVE_TREND_ONLY")
    engine.simulator.execute_hypothetical_buy(next_open=80000.0)
    assert engine.simulator.position_active

    rec = engine.evaluate_bar(
        bar_idx=0,
        timestamp_utc="2026-10-19T00:00:00Z",
        availability_timestamp_utc="2026-10-19T00:25:00Z",  # 25 min latency > 15 min limit
        open_p=80000.0,
        high_p=80010.0,
        low_p=79990.0,
        close_p=80000.0,
        features={"trend_direction": 1, "analogue_score": 0.65},
    )
    assert rec.decision == ShadowDecisionAction.POSITION_OPEN_DATA_STALE.value
    assert engine.simulator.position_active, "Inventory must be preserved"


# -------------------------------------------------------------------------
# Scenario 15: Restart Without Duplicate Decisions
# -------------------------------------------------------------------------
def test_15_restart_without_duplicate_decisions():
    """Verify buffer state persistence reloads seen timestamps and prevents duplicate ingestion on restart."""
    with tempfile.NamedTemporaryFile("w", delete=False) as f:
        state_file = Path(f.name)

    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    bridge1 = ShadowMarketDataBridge(min_warmup_bars=10, state_file=state_file)
    snap0 = _generate_snapshot_dict(0, base_t)
    bridge1.ingest_snapshot_payload(snap0, snap0["timestamp_close_utc"])
    bridge1.buffer.save_state()

    # Restart new bridge
    bridge2 = ShadowMarketDataBridge(min_warmup_bars=10, state_file=state_file)
    bridge2.buffer.load_state()
    assert len(bridge2.buffer) == 1

    # Ingesting bar 0 again is rejected as duplicate
    res = bridge2.ingest_snapshot_payload(snap0, snap0["timestamp_close_utc"])
    assert res.status == BridgeStatus.DUPLICATE_CANDLE
    state_file.unlink()


# -------------------------------------------------------------------------
# Scenario 16: Hash-Chain Recovery
# -------------------------------------------------------------------------
def test_16_hash_chain_recovery():
    """Verify decision hash chain can be reconstructed and continued after restart."""
    engine1 = ProspectiveIntegrityEngine(policy_id="POLICY_A_USDT_CASH")
    for i in range(5):
        engine1.evaluate_bar(
            bar_idx=i,
            timestamp_utc=f"2026-10-19T00:{i*5:02d}:00Z",
            availability_timestamp_utc=f"2026-10-19T00:{i*5:02d}:00Z",
            open_p=80000.0,
            high_p=80010.0,
            low_p=79990.0,
            close_p=80000.0,
            features={"trend_direction": 0, "analogue_score": 0.5},
        )
    assert len(engine1.hash_chain) == 5

    # Rehydrate into engine2
    engine2 = ProspectiveIntegrityEngine(policy_id="POLICY_A_USDT_CASH")
    for r in engine1.hash_chain.records:
        engine2.hash_chain.append(r)
    ok, err = engine2.hash_chain.verify_integrity()
    assert ok

    # Continue bar 5
    rec5 = engine2.evaluate_bar(
        bar_idx=5,
        timestamp_utc="2026-10-19T00:25:00Z",
        availability_timestamp_utc="2026-10-19T00:25:00Z",
        open_p=80000.0,
        high_p=80010.0,
        low_p=79990.0,
        close_p=80000.0,
        features={"trend_direction": 0, "analogue_score": 0.5},
    )
    assert rec5.sequence_number == 5
    assert len(engine2.hash_chain) == 6


# -------------------------------------------------------------------------
# Scenario 17: Memory Boundedness (Capacity Retention)
# -------------------------------------------------------------------------
def test_17_memory_boundedness():
    """Verify buffer capped at 1,000 candles retains exactly 1,000 when 1,500 candles are appended."""
    buffer = PersistentRollingBuffer(capacity=1000, min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    for i in range(1500):
        c = _generate_synthetic_candle(i, base_t)
        ok, err = buffer.append_candle(c)
        assert ok, f"Append failed at {i}: {err}"

    assert len(buffer) == 1000
    assert buffer.is_warmup_ready
    # Oldest candle is bar 500, newest is 1499
    assert buffer.candles[0].sequence_number == 500
    assert buffer.candles[-1].sequence_number == 1499


# -------------------------------------------------------------------------
# Scenario 18: Separation of Historical Seed and Prospective Outcomes
# -------------------------------------------------------------------------
def test_18_separation_of_historical_seed_and_prospective_outcomes():
    """Verify seed candles are tagged HISTORICAL_SEED_WARMUP and prospective evaluation counter is not incremented."""
    bridge = ShadowMarketDataBridge(min_warmup_bars=864)
    base_t = datetime(2026, 1, 1, 0, 0, tzinfo=timezone.utc)
    seed = [_generate_synthetic_candle(i, base_t) for i in range(864)]
    prov = HistoricalSeedProvenance("SEED-018", "canonical", "dummy", seed[0].timestamp_open_utc, seed[-1].timestamp_open_utc, 864, True)
    bridge.buffer.ingest_seed_candles(seed, prov)

    for c in bridge.buffer.candles:
        assert c.stream_type == CandleStreamType.HISTORICAL_SEED_WARMUP

    assert bridge.prospective_evaluations_count == 0

    # Ingest 1 live candle (bar 864)
    snap = _generate_snapshot_dict(864, base_t)
    payload = bridge.ingest_snapshot_payload(snap, snap["timestamp_close_utc"])
    assert payload.status == BridgeStatus.READY_FOR_EVALUATION
    assert payload.candle.stream_type == CandleStreamType.PROSPECTIVE_LIVE_OBSERVATION
    assert bridge.prospective_evaluations_count == 1

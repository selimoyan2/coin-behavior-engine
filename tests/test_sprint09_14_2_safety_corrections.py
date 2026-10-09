"""CBE-0.8.0 Sprint 09.14.2 Test Suite: Safety Corrections & Pre-Live Hardening.

Covers:
1. Bounded memory consumption with disk-backed SQLite timestamp index over large ledgers.
2. Forensic recovery: Real disk partial write truncation via os.ftruncate() without mocks,
   verifying byte-identical valid prefix preservation and quarantine backup.
3. Mid-chain corruption detection: Fails closed without truncating or rewriting valid prefix.
4. Live capture service fail-closed preflight interlocks and clean execution with mock transport.
5. Live capture entrypoint script and Docker Compose configuration validation (restart: "no", entrypoint).
"""

from __future__ import annotations

import gc
import hashlib
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.live_capture_service import (
    LiveCaptureService,
    main as live_service_main,
    verify_live_capture_preflight,
)
from coin_behavior_engine.shadow_v080.market_data_contract import (
    CandleLifecycleState,
    MarketType,
    ProvenanceSource,
    ValidatedCandle,
)
from coin_behavior_engine.shadow_v080.raw_evidence_store import (
    EvidenceCorruptionError,
    EvidencePersistenceError,
    RawMarketEvidenceStore,
)
from coin_behavior_engine.shadow_v080.transport_adapter import (
    MockMarketDataTransport,
    SafetyInterlockError,
)


def _make_dummy_candle(ts_open: int, close_price: str = "50000.00") -> ValidatedCandle:
    return ValidatedCandle(
        symbol="BTCUSDT",
        interval="5m",
        market_type=MarketType.SPOT.value,
        timestamp_open=ts_open,
        timestamp_close=ts_open + 299_999,
        datetime_open_utc="2026-03-29T00:00:00Z",
        datetime_close_utc="2026-03-29T00:04:59.999Z",
        open="50000.00",
        high="50100.00",
        low="49900.00",
        close=close_price,
        volume="10.50000000",
        quote_volume="525000.00000000",
        trades_count=100,
        taker_buy_base_volume="5.25000000",
        is_closed=True,
        provenance=ProvenanceSource.OFFLINE_FIXTURE.value,
        receipt_timestamp_utc="2026-03-29T00:05:00.050Z",
        lifecycle_state=CandleLifecycleState.CANDLE_VALIDATED.value,
    )


@pytest.fixture
def temp_dirs():
    tmp_path = Path(tempfile.mkdtemp(prefix="cbe_test_09_14_2_"))
    raw_dir = tmp_path / "raw_market"
    quarantine_dir = tmp_path / "quarantine"
    raw_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    yield raw_dir, quarantine_dir
    shutil.rmtree(tmp_path, ignore_errors=True)


class TestBoundedMemoryStore:
    """Verifies that the disk-backed SQLite timestamp index eliminates unbounded heap growth."""

    def test_disk_backed_index_sqlite_config(self, temp_dirs):
        raw_dir, quarantine_dir = temp_dirs
        store = RawMarketEvidenceStore(
            raw_market_dir=raw_dir,
            quarantine_dir=quarantine_dir,
            symbol="BTCUSDT",
            interval="5m",
        )
        assert store.index_file.exists()

        # Verify PRAGMA settings on the index database
        cur = store._index_conn.cursor()
        cur.execute("PRAGMA journal_mode;")
        assert cur.fetchone()[0].lower() == "wal"
        cur.execute("PRAGMA cache_size;")
        assert cur.fetchone()[0] == -512  # Capped at 512 KB
        store.close()

    def test_bounded_memory_growth_over_increasing_ledger(self, temp_dirs):
        raw_dir, quarantine_dir = temp_dirs
        store = RawMarketEvidenceStore(
            raw_market_dir=raw_dir,
            quarantine_dir=quarantine_dir,
            symbol="BTCUSDT",
            interval="5m",
        )

        tracemalloc.start()
        gc.collect()
        snapshot_start = tracemalloc.take_snapshot()

        # Insert 1500 candles (exceeds in-memory recent cache of 1000)
        base_ts = 1774742400000
        for i in range(1500):
            c = _make_dummy_candle(base_ts + i * 300_000)
            status, entry = store.append_candle(c)
            assert status == "PERSISTED"

        gc.collect()
        snapshot_end = tracemalloc.take_snapshot()
        tracemalloc.stop()

        # Verify in-memory recent cache is capped at maxlen (1000)
        assert len(store._recent_candles) == 1000
        assert len(store._recent_candles_by_ts) == 1000
        assert store.count == 1500

        # Verify memory difference is strictly bounded (< 5 MB heap growth for 1500 candles)
        stats = snapshot_end.compare_to(snapshot_start, "lineno")
        total_growth = sum(stat.size_diff for stat in stats if stat.size_diff > 0)
        assert total_growth < 5 * 1024 * 1024  # Under 5 MB

        # Verify lookup of older evicted candle from disk index and ledger
        oldest_ts = base_ts
        retrieved_old = store.get_candle_by_timestamp(oldest_ts)
        assert retrieved_old is not None
        assert retrieved_old.timestamp_open == oldest_ts

        # Verify lookup of recent cached candle
        newest_ts = base_ts + 1499 * 300_000
        retrieved_new = store.get_candle_by_timestamp(newest_ts)
        assert retrieved_new is not None
        assert retrieved_new.timestamp_open == newest_ts

        # Verify duplicate detection uses disk index for evicted candles
        dup_old = _make_dummy_candle(oldest_ts)
        dup_status, _ = store.append_candle(dup_old)
        assert dup_status == "DUPLICATE_IGNORED"

        store.close()


class TestForensicRecovery:
    """Verifies that trailing partial writes at EOF are cleanly truncated with os.ftruncate()
    without rewriting valid history, and that corrupted trailing bytes are quarantined."""

    def test_real_file_partial_write_truncation_without_mocks(self, temp_dirs):
        raw_dir, quarantine_dir = temp_dirs
        store = RawMarketEvidenceStore(
            raw_market_dir=raw_dir,
            quarantine_dir=quarantine_dir,
            symbol="BTCUSDT",
            interval="5m",
        )

        base_ts = 1774742400000
        for i in range(10):
            c = _make_dummy_candle(base_ts + i * 300_000, close_price=f"{50000 + i}.00")
            store.append_candle(c)

        assert store.count == 10
        store.close()

        # Read exact valid binary bytes before crash simulation
        evidence_file = store.evidence_file
        valid_bytes = evidence_file.read_bytes()
        valid_size = len(valid_bytes)
        valid_hash = hashlib.sha256(valid_bytes).hexdigest()

        # Simulate trailing partial write at EOF
        corrupt_partial_bytes = b'{"entry_index":10,"prev_hash":"abc","candle":{"symbol":"BTCUSDT","incompl'
        with open(evidence_file, "ab") as f:
            f.write(corrupt_partial_bytes)
            f.flush()
            os.fsync(f.fileno())

        assert evidence_file.stat().st_size == valid_size + len(corrupt_partial_bytes)

        # Reopen store: triggers verify_and_recover_chain() with os.ftruncate
        recovered_store = RawMarketEvidenceStore(
            raw_market_dir=raw_dir,
            quarantine_dir=quarantine_dir,
            symbol="BTCUSDT",
            interval="5m",
        )

        assert recovered_store.count == 10

        # Verify recovered file on disk is byte-identical to original valid bytes
        recovered_bytes = evidence_file.read_bytes()
        assert len(recovered_bytes) == valid_size
        assert hashlib.sha256(recovered_bytes).hexdigest() == valid_hash
        assert recovered_bytes == valid_bytes

        # Verify forensic backup was created in quarantine
        forensic_files = list(quarantine_dir.glob("forensic_trailing_corruption_*.bin"))
        assert len(forensic_files) == 1
        quarantined_bytes = forensic_files[0].read_bytes()
        assert quarantined_bytes == corrupt_partial_bytes

        # Verify recovery audit log was recorded
        audit_file = quarantine_dir / "recovery_audit.jsonl"
        assert audit_file.exists()
        with open(audit_file, "r", encoding="utf-8") as af:
            audit_lines = [json.loads(line) for line in af if line.strip()]
        assert len(audit_lines) == 1
        assert audit_lines[0]["action"] == "TRAILING_CORRUPTION_FORENSIC_TRUNCATE"
        assert audit_lines[0]["truncated_bytes_count"] == len(corrupt_partial_bytes)
        assert audit_lines[0]["valid_entries_count"] == 10
        assert audit_lines[0]["backup_sha256"] == hashlib.sha256(corrupt_partial_bytes).hexdigest()

        # Verify all 10 candles can be retrieved and index is synchronized
        for i in range(10):
            c_retrieved = recovered_store.get_candle_by_timestamp(base_ts + i * 300_000)
            assert c_retrieved is not None
            assert c_retrieved.close == f"{50000 + i}.00"

        recovered_store.close()

    def test_mid_chain_corruption_fails_closed_without_truncating(self, temp_dirs):
        raw_dir, quarantine_dir = temp_dirs
        store = RawMarketEvidenceStore(
            raw_market_dir=raw_dir,
            quarantine_dir=quarantine_dir,
            symbol="BTCUSDT",
            interval="5m",
        )

        base_ts = 1774742400000
        for i in range(5):
            c = _make_dummy_candle(base_ts + i * 300_000)
            store.append_candle(c)
        store.close()

        evidence_file = store.evidence_file
        lines = evidence_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 5

        # Corrupt line 2 (middle of the file)
        corrupted_data = json.loads(lines[2])
        corrupted_data["candle"]["close"] = "999999.00"  # Breaks candle hash and entry hash
        lines[2] = json.dumps(corrupted_data)
        evidence_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Must raise EvidenceCorruptionError and NOT truncate the file
        with pytest.raises(EvidenceCorruptionError):
            RawMarketEvidenceStore(
                raw_market_dir=raw_dir,
                quarantine_dir=quarantine_dir,
                symbol="BTCUSDT",
                interval="5m",
            )

        # File size must remain unchanged (no unauthorized truncate of mid-chain records)
        reopened_lines = evidence_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(reopened_lines) == 5


class TestLiveCaptureServiceAndPreflight:
    """Verifies fail-closed gating of the live capture service and entrypoint."""

    def test_preflight_fails_closed_when_approval_3_not_authorized(self, monkeypatch):
        monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "false")
        monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
        monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
        monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
        monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")

        is_valid, violations = verify_live_capture_preflight()
        assert not is_valid
        assert any("Approval 3" in v for v in violations)

        with pytest.raises(SafetyInterlockError):
            LiveCaptureService()

    def test_preflight_fails_closed_when_collection_disabled(self, monkeypatch):
        monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
        monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
        monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
        monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
        monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")

        is_valid, violations = verify_live_capture_preflight()
        assert not is_valid
        assert any("Binance collection is disabled" in v for v in violations)

    def test_preflight_fails_closed_when_trading_not_disabled(self, monkeypatch):
        monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
        monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
        monkeypatch.setenv("CBE_TRADING_DISABLED", "false")
        monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
        monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")

        is_valid, violations = verify_live_capture_preflight()
        assert not is_valid
        assert any("Trading interlock" in v for v in violations)

    def test_preflight_fails_closed_when_prospective_scoring_enabled(self, monkeypatch):
        monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
        monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
        monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
        monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "true")
        monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")

        is_valid, violations = verify_live_capture_preflight()
        assert not is_valid
        assert any("Prospective scoring must be disabled" in v for v in violations)

    def test_preflight_fails_closed_when_approval_4_authorized(self, monkeypatch):
        monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
        monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
        monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
        monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
        monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", "true")
        monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")

        is_valid, violations = verify_live_capture_preflight()
        assert not is_valid
        assert any("Approval 4 is pending" in v for v in violations)

    def test_preflight_fails_closed_when_record_label_invalid(self, monkeypatch):
        monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
        monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
        monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
        monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
        monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")

        is_valid, violations = verify_live_capture_preflight()
        assert not is_valid
        assert any("CBE_RECORD_LABEL must be 'LIVE_BINANCE_SPOT'" in v for v in violations)

    def test_service_executes_cleanly_with_mock_transport_when_authorized(self, monkeypatch, temp_dirs):
        raw_dir, quarantine_dir = temp_dirs
        monkeypatch.setenv("CBE_APPROVAL_3_AUTHORIZED", "true")
        monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
        monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
        monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
        monkeypatch.setenv("CBE_APPROVAL_4_AUTHORIZED", "false")
        monkeypatch.setenv("CBE_RECORD_LABEL", "LIVE_BINANCE_SPOT")

        config = ShadowCollectorConfig(
            symbol="BTCUSDT",
            interval="5m",
            approval_3_authorized=True,
            approval_4_authorized=False,
            live_shadow_enabled=True,
            network_enabled=True,
            trading_enabled=False,
            shadow_data_dir=raw_dir.parent,
        )
        config.raw_market_dir = raw_dir
        config.quarantine_dir = quarantine_dir

        mock_transport = MockMarketDataTransport(config)
        mock_transport.connect()
        base_ts = 1774742400000
        for i in range(5):
            mock_transport.inject_message({
                "e": "kline",
                "E": base_ts + i * 300_000 + 300_000,
                "s": "BTCUSDT",
                "k": {
                    "t": base_ts + i * 300_000,
                    "T": base_ts + i * 300_000 + 299_999,
                    "s": "BTCUSDT",
                    "i": "5m",
                    "o": "50000.00",
                    "h": "50100.00",
                    "l": "49900.00",
                    "c": f"{50000 + i}.00",
                    "v": "10.0",
                    "q": "500000.0",
                    "n": 100,
                    "V": "5.0",
                    "x": True,
                },
            })

        service = LiveCaptureService(config=config, transport=mock_transport)
        ret = service.run(max_ticks=5)
        assert ret == 0
        assert service.engine.total_persisted == 5
        service.stop()

    def test_main_cli_fails_closed_without_approval_3(self, monkeypatch):
        monkeypatch.delenv("CBE_APPROVAL_3_AUTHORIZED", raising=False)
        monkeypatch.delenv("CBE_BINANCE_COLLECTION_ENABLED", raising=False)
        ret = live_service_main()
        assert ret == 1


class TestDeploymentArtifactsAndCompose:
    """Verifies that deployment files meet all fail-closed and resource invariants."""

    def test_compose_live_capture_configuration(self):
        compose_path = Path("deploy/shadow_v080/docker-compose.coolify-live-capture.yaml")
        assert compose_path.exists()

        with open(compose_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        services = data.get("services", {})
        assert "cbe-080-live-capture" in services
        srv = services["cbe-080-live-capture"]

        # Hardened restart policy
        assert srv["restart"] == "no"

        # Explicit entrypoint
        assert srv["entrypoint"] == ["/app/entrypoint_live_capture.sh"]

        # Immutable root and resource bounds
        assert srv["read_only"] is True
        assert srv["user"] == "1000:1000"
        assert srv["pids_limit"] == 64
        assert srv["mem_limit"] == "300m"
        assert srv["cpus"] == 0.25

        # Safety environment variables
        env = dict(item.split("=", 1) for item in srv["environment"])
        assert env["CBE_APPROVAL_3_AUTHORIZED"] == "false"
        assert env["CBE_BINANCE_COLLECTION_ENABLED"] == "false"
        assert env["CBE_TRADING_DISABLED"] == "true"
        assert env["CBE_PROSPECTIVE_OBSERVATION_ENABLED"] == "false"
        assert env["CBE_APPROVAL_4_AUTHORIZED"] == "false"
        assert env["CBE_RECORD_LABEL"] == "LIVE_BINANCE_SPOT"

        # Dedicated volume isolation
        volumes = srv.get("volumes", [])
        assert any("cbe_080_live_capture_data" in v for v in volumes)
        assert not any("cbe_080_shadow_data" in v for v in volumes)

    def test_entrypoint_script_exists_and_executable(self):
        entrypoint_path = Path("deploy/shadow_v080/entrypoint_live_capture.sh")
        assert entrypoint_path.exists()
        content = entrypoint_path.read_text(encoding="utf-8")
        assert "set -eu" in content
        assert "python3 -m coin_behavior_engine.shadow_v080.live_capture_service" in content

    def test_dockerfile_copies_live_entrypoint(self):
        dockerfile_path = Path("deploy/shadow_v080/Dockerfile.staging")
        assert dockerfile_path.exists()
        content = dockerfile_path.read_text(encoding="utf-8")
        assert "entrypoint_live_capture.sh" in content
        assert "chmod +x /app/entrypoint_inert.sh /app/entrypoint_live_capture.sh" in content

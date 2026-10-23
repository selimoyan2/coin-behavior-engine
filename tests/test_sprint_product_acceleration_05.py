"""Sprint Product Acceleration 05 — Test Suite.

Verifies:
1. Build identity contract (/api/v1/product/runtime-build)
2. Dynamic dataset catalog (/api/v1/product/dataset-catalog)
3. Dataset coverage & monthly completeness calendar (/api/v1/product/dataset-coverage)
4. Dataset quality & import receipts (/api/v1/product/dataset-quality)
5. Available dates & latest candle navigation (/api/v1/product/available-dates)
6. Unimported month empty data behavior (2026-10 explicit no-data alert)
7. Timeline navigation (day & time-slot filtering)
8. Offline historical data importer: valid file validation
9. Offline historical data importer: structural OHLC corruption rejection
10. Offline historical data importer: duplicate timestamp rejection
11. Offline historical data importer: conflicting candle overlap rejection
12. Isolated synthetic October 2026 test fixture verification (partial month)
13. Fail-closed governance invariants
"""

from datetime import datetime, timezone
from http import HTTPStatus
import json
from pathlib import Path
import tempfile
import uuid

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.data_import import (
    HistoricalDataImporter,
    OverlapConflictError,
    ValidationError,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.dataset_manager import DatasetManager

REPO_ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------------------
# 1. Build Identity Contract
# -----------------------------------------------------------------------------
def test_01_build_identity_contract():
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/runtime-build")
    assert status == HTTPStatus.OK
    assert data["status"] == "success"
    assert "environment" in data
    assert "application_version" in data
    assert "build_commit" in data
    assert "build_commit_short" in data
    assert "dataset_manifest_version" in data
    assert data["runtime_identity_verified"] is True
    assert len(data["build_commit_short"]) <= 8
    assert data["build_commit"] != "69027de4bd8baf79aa1a6c7874e52ec623e41dcc"


# -----------------------------------------------------------------------------
# 2. Dynamic Dataset Catalog
# -----------------------------------------------------------------------------
def test_02_dynamic_dataset_catalog():
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/dataset-catalog")
    assert status == HTTPStatus.OK
    datasets = data["datasets"]
    spot = datasets["binance_spot_multiyear"]

    assert spot["symbol"] == "BTCUSDT"
    assert spot["total_partitions"] >= 280
    assert "manifest_version" in spot
    assert "5m" in spot["supported_intervals"]
    assert "1h" in spot["supported_intervals"]
    assert spot["supported_intervals"]["5m"]["months_count"] >= 50


# -----------------------------------------------------------------------------
# 3. Dataset Coverage & Completeness Calendar
# -----------------------------------------------------------------------------
def test_03_dataset_coverage_and_completeness_calendar():
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/dataset-coverage")
    assert status == HTTPStatus.OK
    assert "manifest_version" in data
    assert "available_months" in data
    assert len(data["available_months"]) >= 50

    cal = data["completeness_calendar"]
    assert len(cal) > 0
    # Every calendar month should have a recognized status
    for entry in cal:
        assert entry["status"] in ("COMPLETE", "PARTIAL", "EMPTY", "NOT_IMPORTED")
        assert entry["actual_candles"] >= 0
        assert entry["expected_candles"] > 0


# -----------------------------------------------------------------------------
# 4. Dataset Quality & Audit Endpoint
# -----------------------------------------------------------------------------
def test_04_dataset_quality_endpoint():
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/dataset-quality")
    assert status == HTTPStatus.OK
    assert data["integrity_verdict"] == "VERIFIED_PASS"
    assert data["total_partitions"] >= 280
    assert "latest_month_status" in data
    assert data["latest_month_status"]["status"] in ("COMPLETE", "PARTIAL")
    assert data["governance_classification"] == "OFFLINE_AUDITED_HISTORICAL_DATA"


# -----------------------------------------------------------------------------
# 5. Available Dates & Latest Candle Navigation
# -----------------------------------------------------------------------------
def test_05_available_dates_endpoint():
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/available-dates?interval=5m")
    assert status == HTTPStatus.OK
    assert data["interval"] == "5m"
    assert len(data["available_years"]) >= 4
    assert "2026" in data["available_years"]
    assert data["latest_month"] == "2026-09"

    latest_candle = data["latest_available_candle"]
    assert latest_candle is not None
    assert latest_candle["timestamp_utc"].startswith("2026-09-30")
    assert latest_candle["close"] > 0


# -----------------------------------------------------------------------------
# 6. Unimported Month Empty Data Behavior (October 2026)
# -----------------------------------------------------------------------------
def test_06_unimported_month_empty_data_behavior():
    # When requesting 2026-10 (which is not yet imported in canonical datasets)
    status, data = ProductDashboardApiService.handle_request(
        "/api/v1/product/historical-candles?interval=5m&month=2026-10"
    )
    assert status == HTTPStatus.OK
    assert data["status"] == "no_data"
    assert data["available"] is False
    assert "Ekim 2026 için doğrulanmış tarihsel mum verisi henüz bulunmuyor." in data["message"]
    assert data["latest_available_month"] == "2026-09"
    assert data["candles"] == []
    assert data["count"] == 0


# -----------------------------------------------------------------------------
# 7. Timeline Navigation (Day and Time Slot Filtering)
# -----------------------------------------------------------------------------
def test_07_day_and_time_slot_filtering():
    status, data = ProductDashboardApiService.handle_request(
        "/api/v1/product/historical-candles?interval=5m&month=2026-09&day=15&time_slot=12-18&limit=100"
    )
    assert status == HTTPStatus.OK
    assert data["available"] is True
    candles = data["candles"]
    assert len(candles) > 0

    for c in candles:
        # All candles must be on day 15
        assert c["datetime_utc"].startswith("2026-09-15")
        # All candles must be within 12:00 to 18:00 UTC
        hour_int = int(c["datetime_utc"][11:13])
        assert 12 <= hour_int < 18


# -----------------------------------------------------------------------------
# 8. Data Importer: Valid File Validation
# -----------------------------------------------------------------------------
def test_08_data_importer_validation_valid_file():
    importer = HistoricalDataImporter()
    source_file = REPO_ROOT / "data" / "binance_spot_multiyear" / "5m" / "BTCUSDT-5m-2026-09.parquet"
    res = importer.validate_file(source_file, symbol="BTCUSDT", interval="5m")

    assert res["valid"] is True
    assert res["target_month"] == "2026-09"
    assert res["records_count"] == 8640
    assert res["first_open_price"] > 0
    assert res["last_close_price"] > 0
    assert res["gaps_count"] == 0


# -----------------------------------------------------------------------------
# 9. Data Importer: Rejects Corrupted OHLC (High < Low)
# -----------------------------------------------------------------------------
def test_09_data_importer_rejects_corrupted_ohlc():
    importer = HistoricalDataImporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        bad_csv = Path(tmpdir) / "corrupted_ohlc.csv"
        # Create CSV where High < Low on row 2
        bad_csv.write_text(
            "open_time,open,high,low,close,volume\n"
            "1788220800000,80000.0,80500.0,79500.0,80200.0,10.5\n"
            "1788221100000,80200.0,79000.0,80500.0,80100.0,12.0\n",
            encoding="utf-8",
        )

        with pytest.raises(ValidationError, match="OHLC Mantık Hatası"):
            importer.validate_file(bad_csv, interval="5m")


# -----------------------------------------------------------------------------
# 10. Data Importer: Rejects Duplicate Timestamps
# -----------------------------------------------------------------------------
def test_10_data_importer_rejects_duplicate_timestamps():
    importer = HistoricalDataImporter()
    with tempfile.TemporaryDirectory() as tmpdir:
        dup_csv = Path(tmpdir) / "duplicate_times.csv"
        dup_csv.write_text(
            "open_time,open,high,low,close,volume\n"
            "1788220800000,80000.0,80500.0,79500.0,80200.0,10.5\n"
            "1788220800000,80200.0,80600.0,80100.0,80500.0,15.0\n",
            encoding="utf-8",
        )

        with pytest.raises(ValidationError, match="Tekrarlanan"):
            importer.validate_file(dup_csv, interval="5m")


# -----------------------------------------------------------------------------
# 11. Data Importer: Detects and Rejects Conflicting Candle Overlaps
# -----------------------------------------------------------------------------
def test_11_data_importer_detects_overlap_conflicts():
    with tempfile.TemporaryDirectory() as tmpdir:
        base_dir = Path(tmpdir) / "multiyear"
        intv_dir = base_dir / "5m"
        intv_dir.mkdir(parents=True, exist_ok=True)

        # Create canonical partition
        canon_file = intv_dir / "BTCUSDT-5m-2026-08.parquet"
        df_canon = pd.DataFrame({
            "open_time": [1785628800000],  # 2026-08-01 00:00:00 UTC
            "open": [75000.0],
            "high": [75500.0],
            "low": [74800.0],
            "close": [75200.0],
            "volume": [50.0],
        })
        df_canon.to_parquet(canon_file)

        importer = HistoricalDataImporter(base_dir=base_dir)

        # Candidate file with DIFFERENT price at the exact same timestamp
        conflict_csv = Path(tmpdir) / "conflict.csv"
        conflict_csv.write_text(
            "open_time,open,high,low,close,volume\n"
            "1785628800000,99999.0,100000.0,99500.0,99800.0,10.0\n",
            encoding="utf-8",
        )

        with pytest.raises(OverlapConflictError, match="çelişen"):
            importer.validate_file(conflict_csv, symbol="BTCUSDT", interval="5m")


# -----------------------------------------------------------------------------
# 12. Synthetic Current-Month Test Fixture Isolation (October 2026 Partial)
# -----------------------------------------------------------------------------
def test_12_synthetic_current_month_test_fixture_isolation():
    """Verify that a synthetic October 2026 partial month can be imported into an isolated test manager without polluting canonical datasets."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_base_dir = Path(tmpdir) / "isolated_data"
        receipts_dir = Path(tmpdir) / "receipts"
        test_5m_dir = test_base_dir / "5m"
        test_5m_dir.mkdir(parents=True, exist_ok=True)

        # Generate synthetic October 2026 partial dataset (Oct 1 to Oct 23, 23 days)
        # Clearly marked SYNTHETIC_TEST_FIXTURE_NOT_MARKET_DATA
        start_ts = int(datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
        bars_count = 23 * 24 * 12  # 6,624 bars
        step_ms = 300_000

        timestamps = [start_ts + i * step_ms for i in range(bars_count)]
        opens = [80000.0 + (i % 500) * 2.0 for i in range(bars_count)]
        highs = [o + 50.0 for o in opens]
        lows = [o - 50.0 for o in opens]
        closes = [o + 10.0 for o in opens]
        volumes = [5.0 + (i % 20) for i in range(bars_count)]

        synth_df = pd.DataFrame({
            "open_time": timestamps,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "fixture_tag": ["SYNTHETIC_TEST_FIXTURE_NOT_MARKET_DATA"] * bars_count,
        })

        synth_file = Path(tmpdir) / "BTCUSDT-5m-2026-10-synthetic.parquet"
        synth_df.to_parquet(synth_file)

        importer = HistoricalDataImporter(base_dir=test_base_dir, receipt_dir=receipts_dir)

        # Validate
        val = importer.validate_file(synth_file, symbol="BTCUSDT", interval="5m", allow_partial=True)
        assert val["valid"] is True
        assert val["target_month"] == "2026-10"
        assert val["records_count"] == 6624

        # Atomic Import into isolated test harness
        receipt = importer.import_file(synth_file, symbol="BTCUSDT", interval="5m", allow_partial=True)
        assert receipt["status"] == "ACCEPTED_AND_PUBLISHED"
        assert receipt["records_accepted"] == 6624
        assert receipt["target_partition"] == "BTCUSDT-5m-2026-10.parquet"

        # Check completeness via DatasetManager
        dm_isolated = DatasetManager(base_dir=test_base_dir)
        comp = dm_isolated.get_month_completeness("2026-10", interval="5m")
        assert comp.status == "PARTIAL"
        assert comp.actual_candles == 6624
        assert comp.expected_candles == 31 * 24 * 12  # 8,928 expected in 31-day October
        assert comp.missing_candles_count == 8928 - 6624

        # CRITICAL VERIFICATION: Ensure real canonical repository has NOT been altered
        canonical_october = REPO_ROOT / "data" / "binance_spot_multiyear" / "5m" / "BTCUSDT-5m-2026-10.parquet"
        assert not canonical_october.exists(), "CRITICAL: Canonical repository must NOT be polluted with synthetic fixtures!"


# -----------------------------------------------------------------------------
# 13. Fail-Closed Governance Invariants
# -----------------------------------------------------------------------------
def test_13_governance_invariants():
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/governance")
    assert status == HTTPStatus.OK
    contract = data["governance_contract"]

    assert contract["technical_decision"] == "TECHNICAL_NO_GO"
    assert contract["governance_authorization"] == "NOT_GRANTED"
    assert contract["production_token_issued"] is False

    # Capabilities matrix verifies fail-closed observation and trading
    obs_cap = next(c for c in data["capabilities_matrix"] if c["capability"] == "PROSPECTIVE_LIVE_OBSERVATION")
    assert obs_cap["status"] == "DISABLED"

    exec_cap = next(c for c in data["capabilities_matrix"] if c["capability"] == "ORDER_EXECUTION")
    assert exec_cap["status"] == "PERMANENTLY_PROHIBITED"

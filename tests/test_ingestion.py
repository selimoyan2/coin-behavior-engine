"""Tests for raw storage manager and idempotent ingestion."""

import shutil
from pathlib import Path
import pytest

from coin_behavior_engine.ingestion.binance import BinanceMarketDataProvider
from coin_behavior_engine.ingestion.storage import RawStorageManager


@pytest.fixture
def temp_raw_storage(tmp_path):
    return RawStorageManager(raw_dir=tmp_path / "raw")


def test_idempotent_raw_storage(temp_raw_storage):
    sample_records = [
        [1767225600000, "90000.0", "90100.0", "89950.0", "90050.0", "15.0", 1767225899999, "1350000.0", 500, "7.0", "630000.0", "0"],
        [1767225900000, "90050.0", "90200.0", "90000.0", "90150.0", "20.0", 1767226199999, "1800000.0", 650, "10.0", "900000.0", "0"],
    ]

    # First save
    added_1 = temp_raw_storage.save_raw_batches("BTCUSDT", "5m", sample_records)
    assert added_1 == 2
    df_1 = temp_raw_storage.load_raw_data("BTCUSDT", "5m")
    assert len(df_1) == 2

    # Second save with exact same records (idempotent duplicate rejection)
    added_2 = temp_raw_storage.save_raw_batches("BTCUSDT", "5m", sample_records)
    assert added_2 == 0
    df_2 = temp_raw_storage.load_raw_data("BTCUSDT", "5m")
    assert len(df_2) == 2

    # Add third record with one overlap
    third_batch = [
        [1767225900000, "90050.0", "90200.0", "90000.0", "90150.0", "20.0", 1767226199999, "1800000.0", 650, "10.0", "900000.0", "0"],
        [1767226200000, "90150.0", "90300.0", "90100.0", "90250.0", "12.0", 1767226499999, "1080000.0", 420, "6.0", "540000.0", "0"],
    ]
    added_3 = temp_raw_storage.save_raw_batches("BTCUSDT", "5m", third_batch)
    assert added_3 == 1
    df_3 = temp_raw_storage.load_raw_data("BTCUSDT", "5m")
    assert len(df_3) == 3


def test_binance_response_validation():
    provider = BinanceMarketDataProvider()
    valid_kline = [[1767225600000, "90000", "90100", "89900", "90050", "10", 1767225899999, "900000", 100, "5", "450000", "0"]]
    assert provider.validate_response(valid_kline) is True
    assert provider.validate_response([]) is True
    assert provider.validate_response("not a list") is False
    assert provider.validate_response([[1, 2]]) is False

"""Sprint 35 Comprehensive Targeted Test Suite.

Covers:
- October 2026 Complete Data Recovery (8,928 5m bars, zero gaps, zero duplicates)
- November 2026 Partial Verification (4,280 5m bars, cutoff 15 Nov 21:15, zero synthetic bars)
- Multi-Timeframe Integrity & Resampling Conservation
- Dataset Registry V2.0 capabilities
- Importer Security & Candle Physics Validation
- Dashboard V12 UI elements & Navigation
- Dashboard API historical-candles endpoints
- Strict Live Trading Prohibition (HTTP 403)
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import tempfile

import pandas as pd
import pytest

from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.dashboard_ui import render_product_dashboard_html
from coin_behavior_engine.product.dataset_manager import DatasetManager
from coin_behavior_engine.product.dataset_registry import (
    HistoricalDatasetRegistry,
    DatasetStatus,
    TIMEFRAME_BARS_PER_DAY,
)
from scripts.import_offline_historical_partition import (
    validate_and_harden_partition,
    import_partition_atomic,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestSprint35HistoricalDataAndDashboardV12:

    # 1. October 2026 Complete Recovery
    def test_01_october_2026_complete_verification(self):
        p_5m = REPO_ROOT / "data" / "binance_spot_multiyear" / "5m" / "BTCUSDT-5m-2026-10.parquet"
        assert p_5m.exists()
        df_5m = pd.read_parquet(p_5m)
        assert len(df_5m) == 8928  # 31 days * 288 bars/day
        assert df_5m["open_time"].is_monotonic_increasing
        assert df_5m["open_time"].duplicated().sum() == 0

        # Check 1h
        p_1h = REPO_ROOT / "data" / "binance_spot_multiyear" / "1h" / "BTCUSDT-1h-2026-10.parquet"
        assert p_1h.exists()
        df_1h = pd.read_parquet(p_1h)
        assert len(df_1h) == 744  # 31 days * 24 hours/day

        # Check 1d
        p_1d = REPO_ROOT / "data" / "binance_spot_multiyear" / "1d" / "BTCUSDT-1d-2026-10.parquet"
        assert p_1d.exists()
        df_1d = pd.read_parquet(p_1d)
        assert len(df_1d) == 31

    # 2. November 2026 Partial Verification
    def test_02_november_2026_partial_verification(self):
        p_5m = REPO_ROOT / "data" / "binance_spot_multiyear" / "5m" / "BTCUSDT-5m-2026-11.parquet"
        assert p_5m.exists()
        df_5m = pd.read_parquet(p_5m)
        assert len(df_5m) == 4280
        assert df_5m["open_time"].is_monotonic_increasing
        assert df_5m["open_time"].duplicated().sum() == 0

        # Verified cutoff check
        df_5m["datetime"] = pd.to_datetime(df_5m["datetime"], utc=True)
        max_dt = df_5m["datetime"].max()
        assert max_dt == pd.Timestamp("2026-11-15 21:15:00", tz="UTC")

        # Check 1h and 1d
        p_1h = REPO_ROOT / "data" / "binance_spot_multiyear" / "1h" / "BTCUSDT-1h-2026-11.parquet"
        df_1h = pd.read_parquet(p_1h)
        assert len(df_1h) == 358

        p_1d = REPO_ROOT / "data" / "binance_spot_multiyear" / "1d" / "BTCUSDT-1d-2026-11.parquet"
        df_1d = pd.read_parquet(p_1d)
        assert len(df_1d) == 15

    # 3. Multi-Timeframe Consistency & Resampling Conservation
    def test_03_multitimeframe_consistency(self):
        intervals = ["5m", "15m", "1h", "4h", "1d"]
        for tf in intervals:
            p = REPO_ROOT / "data" / "binance_spot_multiyear" / tf / "BTCUSDT-5m-2026-10.parquet".replace("5m", tf)
            assert p.exists(), f"Missing file for {tf}"
            df = pd.read_parquet(p)
            df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
            if tf == "1h":
                assert (df["datetime"].dt.minute == 0).all()
            elif tf == "4h":
                assert (df["datetime"].dt.minute == 0).all()
                assert (df["datetime"].dt.hour % 4 == 0).all()
            elif tf == "1d":
                assert (df["datetime"].dt.minute == 0).all()
                assert (df["datetime"].dt.hour == 0).all()

    # 4. Dataset Registry V2 Capabilities
    def test_04_dataset_registry_v2_capabilities(self):
        reg = HistoricalDatasetRegistry()

        # Audit October across timeframes
        oct_all = reg.audit_all_timeframes_for_partition(2026, 10)
        assert len(oct_all) == 5
        assert oct_all["5m"].status == DatasetStatus.COMPLETE_VERIFIED.value
        assert oct_all["5m"].row_count == 8928
        assert oct_all["1h"].status == DatasetStatus.COMPLETE_VERIFIED.value
        assert oct_all["1h"].row_count == 744
        assert oct_all["1d"].status == DatasetStatus.COMPLETE_VERIFIED.value
        assert oct_all["1d"].row_count == 31

        # Audit November across timeframes
        nov_all = reg.audit_all_timeframes_for_partition(2026, 11)
        assert nov_all["5m"].status == DatasetStatus.PARTIAL_VERIFIED.value
        assert nov_all["5m"].row_count == 4280
        assert nov_all["1h"].status == DatasetStatus.PARTIAL_VERIFIED.value
        assert nov_all["1h"].row_count == 358

        # Full reconciliation audit
        full_rec = reg.generate_full_reconciliation()
        assert full_rec["registry_version"] == "CBE-DATASET-REGISTRY-V2.0"
        assert full_rec["summary"]["total_partitions_audited"] == 59
        assert full_rec["summary"]["status_distribution"]["COMPLETE_VERIFIED"] == 58
        assert full_rec["summary"]["status_distribution"]["PARTIAL_VERIFIED"] == 1
        assert full_rec["summary"]["status_distribution"]["MISSING"] == 0

    # 5. Importer Security & Candle Physics Validation
    def test_05_importer_security_and_physics(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            corrupt_df = pd.DataFrame([{
                "open_time": 1700000000000,
                "datetime": pd.Timestamp("2026-10-01 00:00:00", tz="UTC"),
                "open": 50000.0,
                "high": 40000.0,  # Corrupt
                "low": 45000.0,
                "close": 48000.0,
                "volume": 10.0,
            }])
            corrupt_csv = tmp / "corrupt.csv"
            corrupt_df.to_csv(corrupt_csv, index=False)
            with pytest.raises(ValueError, match="violates candle physics"):
                validate_and_harden_partition(corrupt_csv, expected_interval_minutes=5)

    # 6. Dashboard UI V12 Elements
    def test_06_dashboard_ui_v12_elements(self):
        html = render_product_dashboard_html()
        assert "Araştırma Portalı & Piyasa İstihbaratı V12" in html
        assert "candle-month-select" in html
        assert "2026-11" in html
        assert "2026-10" in html
        assert "2026-09" in html
        assert "Son Mevcut Veriye Git" in html
        assert "En Son Doğrulanmış Veriye Git" in html
        assert "EKİM 2026: TAM DOĞRULANMIŞ VERİ" in html
        assert "KASIM 2026: KISMİ DOĞRULANMIŞ VERİ" in html
        assert "CBE-0.7.0 DONDURULDU" in html
        assert "CANLI İŞLEM: YASAK" in html

    # 7. Dashboard API Historical Candles Endpoint
    def test_07_api_historical_candles_oct_nov(self):
        # 2026-10
        st_oct, res_oct = ProductDashboardApiService.handle_request(
            "/api/v1/product/historical-candles",
            {"interval": ["5m"], "month": ["2026-10"], "limit": ["10"]}
        )
        assert st_oct == 200
        assert len(res_oct["candles"]) == 10
        assert res_oct["candles"][0]["open"] > 0

        # 2026-11
        st_nov, res_nov = ProductDashboardApiService.handle_request(
            "/api/v1/product/historical-candles",
            {"interval": ["5m"], "month": ["2026-11"], "limit": ["10"]}
        )
        assert st_nov == 200
        assert len(res_nov["candles"]) == 10
        assert res_nov["candles"][0]["open"] > 0

        # 2026-12 (Missing month)
        st_dec, res_dec = ProductDashboardApiService.handle_request(
            "/api/v1/product/historical-candles",
            {"interval": ["5m"], "month": ["2026-12"], "limit": ["10"]}
        )
        assert st_dec == 200
        assert res_dec["status"] == "no_data"
        assert res_dec["available"] is False

    # 8. Live Trading Prohibition HTTP 403
    def test_08_live_trading_prohibition_http_403(self):
        trading_endpoints = [
            "/api/v1/product/research/btc-timing/live-trade/execute",
            "/api/v1/order/execute",
            "/api/v1/trade/live",
            "/api/v1/execution/submit",
        ]
        for ep in trading_endpoints:
            status, res = ProductDashboardApiService.handle_post_request(ep, {})
            assert status == 403, f"Endpoint {ep} did not block live trading!"
            assert res["error"] == "GOVERNANCE_VIOLATION"
            assert "permanently prohibited" in res["message"]

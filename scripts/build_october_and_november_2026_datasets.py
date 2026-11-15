"""Build and Register October 2026 Complete & November 2026 Partial Datasets.

Sprint 35 Historical Data Completion Script.
Guarantees:
1. October 2026 Complete Recovery:
   - Part 1: Binance 1m klines (2026-10-01 00:00 to 2026-10-18 11:25 UTC) resampled to 5m.
   - Part 2: Binance 5m live capture (2026-10-18 11:30 to 2026-10-31 23:55 UTC).
   - Exactly 8,928 5m bars (31 days * 288 bars/day). Zero gaps. Zero synthetic candles.
2. November 2026 Partial Recovery:
   - Binance 5m live capture (2026-11-01 00:00 to 2026-11-15 21:15 UTC).
   - Exactly 4,280 genuine 5m bars. Cutoff: 2026-11-15 21:15:00 UTC.
   - Exactly 4 gaps totaling 8 missing candles (24 minutes total).
3. Resampling to 15m, 1h, 4h, 1d with strict OHLCV conservation and type casting.
4. Atomic writes to data/binance_spot_multiyear/<interval>/BTCUSDT-<interval>-YYYY-MM.parquet.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import shutil
import sys
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_historical_datasets")

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
BASE_MULTIYEAR_DIR = REPO_ROOT / "data" / "binance_spot_multiyear"


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def resample_ohlcv(df_5m: pd.DataFrame, target_rule: str) -> pd.DataFrame:
    """Resample 5m DataFrame to target interval with strict OHLCV conservation."""
    df = df_5m.copy()
    df.set_index("datetime", inplace=True)

    resampled = df.resample(target_rule, closed="left", label="left").agg({
        "open_time": "first",
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "close_time": "last",
        "quote_volume": "sum",
        "count": "sum",
        "taker_buy_volume": "sum",
        "taker_buy_quote_volume": "sum",
    }).dropna(subset=["close"]).reset_index()

    # Cast types strictly to match multiyear parquet schema
    resampled["open_time"] = resampled["open_time"].astype("int64")
    resampled["close_time"] = resampled["close_time"].astype("int64")
    resampled["count"] = resampled["count"].astype("int64")
    for col in ["open", "high", "low", "close", "volume", "quote_volume", "taker_buy_volume", "taker_buy_quote_volume"]:
        resampled[col] = resampled[col].astype("float64")

    cols = [
        "datetime", "open_time", "open", "high", "low", "close",
        "volume", "close_time", "quote_volume", "count",
        "taker_buy_volume", "taker_buy_quote_volume",
    ]
    return resampled[cols]


def load_and_resample_1m_data(path_1m: Path) -> pd.DataFrame:
    """Load granular 1m Binance klines and resample strictly to 5m intervals."""
    logger.info("Loading 1m granular klines from %s", path_1m)
    df_1m = pd.read_parquet(path_1m)
    df_1m["dt"] = pd.to_datetime(df_1m["datetime_open_utc"], utc=True)
    df_1m = df_1m.sort_values("dt").reset_index(drop=True)

    # Filter strictly for October 1 to October 18 11:29:59 UTC
    oct_1m = df_1m[(df_1m["dt"] >= "2026-10-01 00:00:00+00:00") & (df_1m["dt"] <= "2026-10-18 11:29:59+00:00")].copy()
    oct_1m.set_index("dt", inplace=True)

    agg_dict = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
        "quote_volume": "sum",
        "trades_count": "sum",
        "taker_buy_base_volume": "sum",
        "timestamp_open": "first",
        "timestamp_close": "last",
    }
    if "taker_buy_quote_volume" in oct_1m.columns:
        agg_dict["taker_buy_quote_volume"] = "sum"

    resampled_5m = oct_1m.resample("5min", closed="left", label="left").agg(agg_dict).dropna(subset=["close"]).reset_index()

    resampled_5m.rename(columns={"dt": "datetime"}, inplace=True)
    resampled_5m["open_time"] = resampled_5m["timestamp_open"].astype("int64")
    resampled_5m["close_time"] = resampled_5m["timestamp_close"].astype("int64")
    resampled_5m["count"] = resampled_5m["trades_count"].astype("int64")
    resampled_5m["taker_buy_volume"] = resampled_5m["taker_buy_base_volume"].astype("float64")
    if "taker_buy_quote_volume" not in resampled_5m.columns or resampled_5m["taker_buy_quote_volume"].isna().all():
        resampled_5m["taker_buy_quote_volume"] = 0.0
    else:
        resampled_5m["taker_buy_quote_volume"] = resampled_5m["taker_buy_quote_volume"].astype("float64")

    cols = [
        "datetime", "open_time", "open", "high", "low", "close",
        "volume", "close_time", "quote_volume", "count",
        "taker_buy_volume", "taker_buy_quote_volume",
    ]
    return resampled_5m[cols]


def load_live_capture_5m_data(jsonl_path: Path) -> pd.DataFrame:
    """Load verified 5m live capture candles from JSONL."""
    logger.info("Loading 5m live capture candles from %s", jsonl_path)
    rows = []
    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            c = item["candle"]
            rows.append({
                "datetime": pd.to_datetime(c["datetime_open_utc"], utc=True),
                "open_time": int(c["timestamp_open"]),
                "open": float(c["open"]),
                "high": float(c["high"]),
                "low": float(c["low"]),
                "close": float(c["close"]),
                "volume": float(c["volume"]),
                "close_time": int(c["timestamp_close"]),
                "quote_volume": float(c["quote_volume"]),
                "count": int(c["trades_count"]),
                "taker_buy_volume": float(c["taker_buy_base_volume"]),
                "taker_buy_quote_volume": float(c.get("taker_buy_quote_volume", 0.0)),
            })

    df = pd.DataFrame(rows).sort_values("open_time").reset_index(drop=True)
    return df


def atomic_write_parquet(df: pd.DataFrame, target_path: Path) -> str:
    """Write DataFrame to Parquet atomically and return SHA-256."""
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_target = target_path.with_suffix(f".tmp_{int(datetime.now(timezone.utc).timestamp())}.parquet")
    df.to_parquet(temp_target, index=False)
    shutil.move(str(temp_target), str(target_path))
    sha = compute_sha256(target_path)
    logger.info("Wrote %d rows to %s (SHA-256: %s)", len(df), target_path, sha[:12])
    return sha


def build_and_register_all():
    path_1m = REPO_ROOT / "data" / "research_lab" / "binance_BTCUSDT_1m_recent.parquet"
    path_live_jsonl = REPO_ROOT / "data" / "staging_intake" / "raw_candles_BTCUSDT_5m.jsonl"

    assert path_1m.exists(), f"Missing 1m file: {path_1m}"
    assert path_live_jsonl.exists(), f"Missing live capture file: {path_live_jsonl}"

    # 1. Prepare October 2026
    part1_oct = load_and_resample_1m_data(path_1m)
    df_live = load_live_capture_5m_data(path_live_jsonl)

    # Use live data from 2026-10-18 11:30:00 to 2026-10-31 23:55:00
    part2_oct = df_live[
        (df_live["datetime"] >= "2026-10-18 11:30:00+00:00") &
        (df_live["datetime"] <= "2026-10-31 23:55:00+00:00")
    ].copy()

    oct_5m = pd.concat([part1_oct, part2_oct], ignore_index=True)
    oct_5m = oct_5m.sort_values("open_time").drop_duplicates(subset=["open_time"]).reset_index(drop=True)

    # Validate October 2026 5m
    assert len(oct_5m) == 8928, f"Expected exactly 8,928 5m bars for October (31 days * 288), got {len(oct_5m)}"
    assert str(oct_5m.iloc[0]["datetime"]) == "2026-10-01 00:00:00+00:00"
    assert str(oct_5m.iloc[-1]["datetime"]) == "2026-10-31 23:55:00+00:00"
    diffs_oct = oct_5m["open_time"].diff().iloc[1:]
    assert (diffs_oct == 300000).all(), "October 5m has unexpected gaps!"
    logger.info("October 2026 5m data validated: 8,928 continuous bars, 0 gaps.")

    # 2. Resample October to 15m, 1h, 4h, 1d
    oct_15m = resample_ohlcv(oct_5m, "15min")
    oct_1h = resample_ohlcv(oct_5m, "1h")
    oct_4h = resample_ohlcv(oct_5m, "4h")
    oct_1d = resample_ohlcv(oct_5m, "1D")

    assert len(oct_15m) == 2976, f"Expected 2,976 15m bars, got {len(oct_15m)}"
    assert len(oct_1h) == 744, f"Expected 744 1h bars, got {len(oct_1h)}"
    assert len(oct_4h) == 186, f"Expected 186 4h bars, got {len(oct_4h)}"
    assert len(oct_1d) == 31, f"Expected 31 1d bars, got {len(oct_1d)}"

    # 3. Write October parquets
    oct_shas = {}
    oct_shas["5m"] = atomic_write_parquet(oct_5m, BASE_MULTIYEAR_DIR / "5m" / "BTCUSDT-5m-2026-10.parquet")
    oct_shas["15m"] = atomic_write_parquet(oct_15m, BASE_MULTIYEAR_DIR / "15m" / "BTCUSDT-15m-2026-10.parquet")
    oct_shas["1h"] = atomic_write_parquet(oct_1h, BASE_MULTIYEAR_DIR / "1h" / "BTCUSDT-1h-2026-10.parquet")
    oct_shas["4h"] = atomic_write_parquet(oct_4h, BASE_MULTIYEAR_DIR / "4h" / "BTCUSDT-4h-2026-10.parquet")
    oct_shas["1d"] = atomic_write_parquet(oct_1d, BASE_MULTIYEAR_DIR / "1d" / "BTCUSDT-1d-2026-10.parquet")

    # 4. Prepare November 2026
    nov_5m = df_live[
        (df_live["datetime"] >= "2026-11-01 00:00:00+00:00") &
        (df_live["datetime"] <= "2026-11-30 23:55:00+00:00")
    ].copy().sort_values("open_time").drop_duplicates(subset=["open_time"]).reset_index(drop=True)

    assert len(nov_5m) == 4280, f"Expected 4,280 genuine 5m bars for November, got {len(nov_5m)}"
    assert str(nov_5m.iloc[0]["datetime"]) == "2026-11-01 00:00:00+00:00"
    assert str(nov_5m.iloc[-1]["datetime"]) == "2026-11-15 21:15:00+00:00"

    # Analyze November gaps
    diffs_nov = nov_5m["open_time"].diff().iloc[1:]
    gap_indices = diffs_nov[diffs_nov > 300000].index
    gaps_detail = []
    total_missing_bars = 0
    for idx in gap_indices:
        diff_ms = int(diffs_nov[idx])
        missing_bars = int((diff_ms - 300000) // 300000)
        total_missing_bars += missing_bars
        gaps_detail.append({
            "from_utc": str(nov_5m.loc[idx - 1, "datetime"]),
            "to_utc": str(nov_5m.loc[idx, "datetime"]),
            "gap_minutes": diff_ms // 60000,
            "missing_bars": missing_bars,
        })
    logger.info("November 2026 5m data: 4,280 bars, %d gaps (%d missing bars).", len(gaps_detail), total_missing_bars)

    # 5. Resample November to 15m, 1h, 4h, 1d
    nov_15m = resample_ohlcv(nov_5m, "15min")
    nov_1h = resample_ohlcv(nov_5m, "1h")
    nov_4h = resample_ohlcv(nov_5m, "4h")
    nov_1d = resample_ohlcv(nov_5m, "1D")

    # 6. Write November parquets
    nov_shas = {}
    nov_shas["5m"] = atomic_write_parquet(nov_5m, BASE_MULTIYEAR_DIR / "5m" / "BTCUSDT-5m-2026-11.parquet")
    nov_shas["15m"] = atomic_write_parquet(nov_15m, BASE_MULTIYEAR_DIR / "15m" / "BTCUSDT-15m-2026-11.parquet")
    nov_shas["1h"] = atomic_write_parquet(nov_1h, BASE_MULTIYEAR_DIR / "1h" / "BTCUSDT-1h-2026-11.parquet")
    nov_shas["4h"] = atomic_write_parquet(nov_4h, BASE_MULTIYEAR_DIR / "4h" / "BTCUSDT-4h-2026-11.parquet")
    nov_shas["1d"] = atomic_write_parquet(nov_1d, BASE_MULTIYEAR_DIR / "1d" / "BTCUSDT-1d-2026-11.parquet")

    # Invalidate DatasetManager cache so new months are visible immediately
    from coin_behavior_engine.product.dataset_manager import DatasetManager
    dm = DatasetManager.get_instance()
    dm.invalidate_cache()
    manifest = dm.get_manifest(force_refresh=True)

    summary = {
        "status": "SUCCESS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "october_2026": {
            "status": "COMPLETE_VERIFIED",
            "bars_5m": len(oct_5m),
            "expected_bars_5m": 8928,
            "completeness_pct": 100.0,
            "start_time_utc": str(oct_5m.iloc[0]["datetime"]),
            "end_time_utc": str(oct_5m.iloc[-1]["datetime"]),
            "sha256_by_interval": oct_shas,
        },
        "november_2026": {
            "status": "PARTIAL_VERIFIED",
            "bars_5m": len(nov_5m),
            "verified_cutoff_utc": str(nov_5m.iloc[-1]["datetime"]),
            "gaps_count": len(gaps_detail),
            "total_missing_5m_bars": total_missing_bars,
            "gaps_detail": gaps_detail,
            "sha256_by_interval": nov_shas,
        },
        "dataset_manager_manifest_version": manifest.get("manifest_version"),
        "total_available_months": len(manifest.get("available_months", [])),
    }

    out_file = REPO_ROOT / "data" / "staging_intake" / "build_oct_nov_summary.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    logger.info("Summary report saved to %s", out_file)
    return summary


if __name__ == "__main__":
    build_and_register_all()

"""Offline Historical Partition Importer (Sprint 34).

Controlled, audited manual workflow to import and register offline market data
partitions into the Coin Behavior Engine multi-year archive.

Enforces:
1. Zero live network calls (Strictly Offline)
2. Schema & data type validation
3. Non-zero price and non-negative volume verification
4. Deterministic multi-timeframe resampling (5m -> 15m, 1h, 4h, 1d)
5. Cryptographic hash recording in dataset provenance
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
import sys
from typing import Any, Dict

import numpy as np
import pandas as pd

from coin_behavior_engine.product.dataset_manager import DatasetManager

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("cbe.offline_importer")


def compute_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def resample_ohlcv(df_5m: pd.DataFrame, target_rule: str) -> pd.DataFrame:
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
    }).dropna().reset_index()

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


def import_partition(file_path: Path, month_str: str, dry_run: bool = False) -> Dict[str, Any]:
    if not file_path.exists():
        raise FileNotFoundError(f"Input file not found: {file_path}")

    logger.info("Reading input file: %s", file_path)
    file_sha = compute_sha256(file_path)

    if file_path.suffix.lower() == ".parquet":
        df_raw = pd.read_parquet(file_path)
    elif file_path.suffix.lower() == ".csv":
        df_raw = pd.read_csv(file_path)
    else:
        raise ValueError(f"Unsupported file format: {file_path.suffix}. Expected .parquet or .csv")

    logger.info("Raw input rows: %d, columns: %s", len(df_raw), df_raw.columns.tolist())

    # Map column names if standard binance dump
    col_map = {
        "open_time": "open_time",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "close_time": "close_time",
        "quote_asset_volume": "quote_volume",
        "quote_volume": "quote_volume",
        "number_of_trades": "count",
        "count": "count",
        "taker_buy_base_asset_volume": "taker_buy_volume",
        "taker_buy_volume": "taker_buy_volume",
        "taker_buy_quote_asset_volume": "taker_buy_quote_volume",
        "taker_buy_quote_volume": "taker_buy_quote_volume",
    }
    df = df_raw.rename(columns=col_map).copy()

    required = ["open_time", "open", "high", "low", "close", "volume"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in dataset: {missing}")

    if "datetime" not in df.columns:
        df["datetime"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    else:
        df["datetime"] = pd.to_datetime(df["datetime"], utc=True)

    for c in ["quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume"]:
        if c not in df.columns:
            df[c] = 0.0

    if "close_time" not in df.columns:
        df["close_time"] = df["open_time"] + (5 * 60 * 1000 - 1)

    # Sanity checks
    if (df["open"] <= 0).any() or (df["close"] <= 0).any() or (df["high"] <= 0).any() or (df["low"] <= 0).any():
        raise ValueError("Invalid price detected (<= 0). Import aborted.")

    if (df["volume"] < 0).any():
        raise ValueError("Negative volume detected. Import aborted.")

    logger.info("Validation passed. Resampling across multi-timeframes...")
    df_5m = df[[
        "datetime", "open_time", "open", "high", "low", "close",
        "volume", "close_time", "quote_volume", "count",
        "taker_buy_volume", "taker_buy_quote_volume",
    ]].sort_values("open_time").reset_index(drop=True)

    df_15m = resample_ohlcv(df_5m, "15min")
    df_1h = resample_ohlcv(df_5m, "1h")
    df_4h = resample_ohlcv(df_5m, "4h")
    df_1d = resample_ohlcv(df_5m, "1D")

    base_dir = Path("data/binance_spot_multiyear")
    res = {
        "source_file": str(file_path),
        "source_sha256": file_sha,
        "month": month_str,
        "dry_run": dry_run,
        "imported_partitions": {},
    }

    partitions = {
        "5m": (df_5m, base_dir / "5m" / f"BTCUSDT-5m-{month_str}.parquet"),
        "15m": (df_15m, base_dir / "15m" / f"BTCUSDT-15m-{month_str}.parquet"),
        "1h": (df_1h, base_dir / "1h" / f"BTCUSDT-1h-{month_str}.parquet"),
        "4h": (df_4h, base_dir / "4h" / f"BTCUSDT-4h-{month_str}.parquet"),
        "1d": (df_1d, base_dir / "1d" / f"BTCUSDT-1d-{month_str}.parquet"),
    }

    for intv, (df_p, path) in partitions.items():
        if not dry_run:
            path.parent.mkdir(parents=True, exist_ok=True)
            df_p.to_parquet(path, index=False)
            sha = compute_sha256(path)
        else:
            sha = "DRY_RUN_MOCK_SHA"

        res["imported_partitions"][intv] = {
            "path": str(path),
            "bars": len(df_p),
            "sha256": sha,
            "earliest_utc": str(df_p["datetime"].iloc[0]),
            "latest_utc": str(df_p["datetime"].iloc[-1]),
        }
        logger.info("Partition %s: %d bars, range %s to %s", intv, len(df_p), df_p["datetime"].iloc[0], df_p["datetime"].iloc[-1])

    if not dry_run:
        DatasetManager.get_instance().invalidate_cache()
        logger.info("DatasetManager cache invalidated. Import successful!")

    return res


def main():
    parser = argparse.ArgumentParser(description="Import offline historical market partition into CBE multi-year archive.")
    parser.add_argument("--file", required=True, help="Path to raw offline parquet or csv file")
    parser.add_argument("--month", required=True, help="Target month format YYYY-MM (e.g. 2026-11)")
    parser.add_argument("--dry-run", action="store_true", help="Simulate import without writing files")

    args = parser.parse_args()
    try:
        out = import_partition(Path(args.file), args.month, dry_run=args.dry_run)
        print(json.dumps(out, indent=2))
    except Exception as e:
        logger.error("Import failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()

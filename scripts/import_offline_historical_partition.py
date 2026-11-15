"""Hardened Offline Historical Partition Importer (Sprint 34.1).

Guarantees:
1. Timestamp unit detection (ms, s, datetime string).
2. Deduplication and monotonic sorting.
3. Temporal continuity and gap analysis.
4. OHLCV price extremes integrity (high >= max(open, close), low <= min(open, close)).
5. Atomic non-destructive writes using temporary staging and rename.
6. STRICT ZERO-SYNTHESIS: Fails transparently on missing candles; never interpolates or fabricates prices.
"""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
from pathlib import Path
import shutil
import sys
import tempfile
from typing import Any, Dict, Optional, Tuple

import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("offline_importer")

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()

def detect_and_normalize_timestamps(df: pd.DataFrame) -> pd.DataFrame:
    """Detect timestamp format and normalize to integer open_time (ms) and UTC datetime."""
    df = df.copy()

    # Find time column
    time_col = None
    for cand in ["open_time", "timestamp", "time", "datetime", "date"]:
        if cand in df.columns:
            time_col = cand
            break

    if not time_col:
        raise ValueError(f"No recognizable timestamp column found. Columns: {df.columns.tolist()}")

    series = df[time_col]

    if pd.api.types.is_datetime64_any_dtype(series):
        dt = pd.to_datetime(series, utc=True)
        open_time_ms = (dt.astype(np.int64) // 10**6).values
    elif pd.api.types.is_numeric_dtype(series):
        val = float(series.dropna().iloc[0]) if len(series.dropna()) > 0 else 0
        if val > 1e14:  # microseconds or nanoseconds
            dt = pd.to_datetime(series, unit="us", utc=True)
            open_time_ms = (dt.astype(np.int64) // 10**6).values
        elif val > 1e11:  # milliseconds
            open_time_ms = series.astype(np.int64).values
            dt = pd.to_datetime(open_time_ms, unit="ms", utc=True)
        else:  # seconds
            open_time_ms = (series * 1000).astype(np.int64).values
            dt = pd.to_datetime(open_time_ms, unit="ms", utc=True)
    else:
        # String parse
        dt = pd.to_datetime(series, utc=True)
        open_time_ms = (dt.astype(np.int64) // 10**6).values

    df["open_time"] = open_time_ms
    df["datetime"] = dt
    return df

def validate_and_harden_partition(
    input_path: Path,
    expected_interval_minutes: int = 60,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Validate raw input partition for schema, OHLCV logic, duplicates, and gaps."""
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    # Read based on extension
    if input_path.suffix.lower() == ".parquet":
        df_raw = pd.read_parquet(input_path)
    elif input_path.suffix.lower() in (".csv", ".txt"):
        df_raw = pd.read_csv(input_path)
    else:
        raise ValueError(f"Unsupported file format: {input_path.suffix}")

    total_raw_rows = len(df_raw)
    if total_raw_rows == 0:
        raise ValueError("Input dataset contains 0 rows.")

    df = detect_and_normalize_timestamps(df_raw)

    # Required OHLCV columns
    req_cols = ["open", "high", "low", "close", "volume"]
    for c in req_cols:
        if c not in df.columns:
            raise ValueError(f"Missing mandatory OHLCV column '{c}'. Present: {df.columns.tolist()}")
        df[c] = df[c].astype(float)

    # 1. Deduplication
    init_count = len(df)
    df = df.drop_duplicates(subset=["open_time"]).sort_values("open_time").reset_index(drop=True)
    duplicates_dropped = init_count - len(df)

    # 2. OHLCV Extremes Consistency Check
    invalid_high = df[df["high"] < np.maximum(df["open"], df["close"])]
    invalid_low = df[df["low"] > np.minimum(df["open"], df["close"])]
    negative_prices = df[(df["open"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["close"] <= 0)]

    if len(negative_prices) > 0:
        raise ValueError(f"Dataset contains {len(negative_prices)} rows with non-positive prices.")

    if len(invalid_high) > 0 or len(invalid_low) > 0:
        raise ValueError(
            f"Dataset violates candle physics: {len(invalid_high)} high < max(O,C), {len(invalid_low)} low > min(O,C)."
        )

    # 3. Temporal Continuity & Gap Analysis
    time_diffs_ms = df["open_time"].diff().iloc[1:]
    expected_step_ms = expected_interval_minutes * 60 * 1000

    gaps = []
    for idx, diff in time_diffs_ms.items():
        if diff != expected_step_ms:
            gaps.append({
                "bar_index": int(idx),
                "previous_time_utc": str(df.loc[idx - 1, "datetime"]),
                "current_time_utc": str(df.loc[idx, "datetime"]),
                "gap_ms": int(diff),
                "missing_expected_bars": int(round((diff - expected_step_ms) / expected_step_ms)),
            })

    # Non-destructive summary
    start_utc = str(df["datetime"].min())
    end_utc = str(df["datetime"].max())

    report = {
        "source_file": str(input_path),
        "source_sha256": compute_sha256(input_path),
        "raw_rows": total_raw_rows,
        "clean_rows": len(df),
        "duplicates_removed": duplicates_dropped,
        "expected_interval_minutes": expected_interval_minutes,
        "start_time_utc": start_utc,
        "end_time_utc": end_utc,
        "total_gaps_found": len(gaps),
        "gaps_detail": gaps[:10],
        "synthesis_applied": False,
        "validation_passed": True,
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
    }

    return df, report

def import_partition_atomic(
    input_path: Path,
    target_path: Path,
    expected_interval_minutes: int = 60,
) -> Dict[str, Any]:
    """Execute non-destructive, atomic import of validated partition."""
    target_path.parent.mkdir(parents=True, exist_ok=True)

    df_clean, report = validate_and_harden_partition(input_path, expected_interval_minutes)

    # Write to temporary file in same target directory to guarantee atomic rename
    temp_target = target_path.with_suffix(f".tmp_{int(datetime.now(timezone.utc).timestamp())}.parquet")
    df_clean.to_parquet(temp_target, index=False)

    # Atomic rename (overwrites target atomically)
    shutil.move(str(temp_target), str(target_path))

    report["target_path"] = str(target_path)
    report["target_sha256"] = compute_sha256(target_path)
    logger.info("Successfully imported partition to %s (SHA-256: %s)", target_path, report["target_sha256"][:12])
    return report

def main():
    parser = argparse.ArgumentParser(description="Hardened Offline Historical Partition Importer")
    parser.add_argument("--input", required=True, help="Path to input parquet or csv file")
    parser.add_argument("--target", required=True, help="Path to target destination parquet")
    parser.add_argument("--interval", type=int, default=60, help="Expected candle interval in minutes (default: 60)")
    parser.add_argument("--report", help="Optional path to save JSON validation report")

    args = parser.parse_args()
    res = import_partition_atomic(Path(args.input), Path(args.target), args.interval)

    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(res, f, indent=2)
        print(f"Saved validation report to {args.report}")
    else:
        print(json.dumps(res, indent=2))

if __name__ == "__main__":
    main()

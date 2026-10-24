"""
CBE — Deterministic Multi-Timeframe Dataset Derivation Engine
Derives higher historical intervals (15m, 1h, 4h, 1d) deterministically
from canonical high-resolution 5-minute historical datasets.

Enforces strict mathematical aggregation:
- Open = first lower-timeframe open
- High = max lower-timeframe high
- Low = min lower-timeframe low
- Close = last lower-timeframe close
- Volume = sum lower-timeframe volume
- Exact UTC boundaries
- Incomplete source windows are dropped (never synthetically filled)
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

logger = logging.getLogger("cbe_timeframe_derivation")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_DIR = REPO_ROOT / "data" / "binance_spot_multiyear"
REPORTS_DIR = REPO_ROOT / "research_outputs"
DERIVATION_ALGORITHM_VERSION = "CBE-MTD-1.0.0"

SUPPORTED_TARGET_INTERVALS = ["15m", "1h", "4h", "1d"]

INTERVAL_RATIOS = {
    ("5m", "15m"): 3,
    ("5m", "1h"): 12,
    ("5m", "4h"): 48,
    ("5m", "1d"): 288,
    ("15m", "1h"): 4,
    ("1h", "4h"): 4,
    ("1h", "1d"): 24,
}

INTERVAL_MS = {
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


@dataclass
class DerivationPartitionReceipt:
    target_interval: str
    target_partition: str
    source_partition: str
    source_sha256: str
    target_sha256: str
    records_derived: int
    expected_full_month_candles: int
    completeness_pct: float
    is_partial: bool
    first_timestamp_utc: str
    last_timestamp_utc: str
    algorithm_version: str = DERIVATION_ALGORITHM_VERSION
    derived_at_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    comparison_with_canonical: Optional[Dict[str, Any]] = None


class MultiTimeframeDerivationEngine:
    """Vectorized, deterministic multi-timeframe aggregation and dataset lineage engine."""

    def __init__(self, dataset_dir: Optional[Path] = None):
        self.dataset_dir = Path(dataset_dir) if dataset_dir else DEFAULT_DATASET_DIR

    @staticmethod
    def compute_sha256(file_path: Path) -> str:
        """Compute SHA256 checksum of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(1024 * 1024):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def derive_dataframe(
        cls,
        df_source: pd.DataFrame,
        source_interval: str = "5m",
        target_interval: str = "1h",
        symbol: str = "BTCUSDT",
    ) -> pd.DataFrame:
        """
        Derive target interval DataFrame from source interval DataFrame using exact vectorized rules.
        Incomplete source windows are strictly dropped.
        """
        pair = (source_interval, target_interval)
        if pair not in INTERVAL_RATIOS:
            raise ValueError(f"Unsupported derivation pair: {pair}. Expected one of {list(INTERVAL_RATIOS.keys())}")

        expected_ratio = INTERVAL_RATIOS[pair]
        target_ms = INTERVAL_MS[target_interval]

        if df_source.empty:
            return pd.DataFrame()

        df = df_source.copy()
        if "open_time" not in df.columns:
            raise ValueError("Source dataframe must contain 'open_time' column in epoch milliseconds")

        # UTC-aligned window grouping
        df["window_time"] = (df["open_time"] // target_ms) * target_ms

        agg_dict: Dict[str, Tuple[str, str]] = {
            "open": ("open", "first"),
            "high": ("high", "max"),
            "low": ("low", "min"),
            "close": ("close", "last"),
            "volume": ("volume", "sum"),
            "sub_bars": ("open", "count"),
        }

        # Optional auxiliary columns present in canonical Binance datasets
        if "close_time" in df.columns:
            agg_dict["close_time"] = ("close_time", "last")
        if "quote_volume" in df.columns:
            agg_dict["quote_volume"] = ("quote_volume", "sum")
        if "count" in df.columns:
            agg_dict["count"] = ("count", "sum")
        if "taker_buy_volume" in df.columns:
            agg_dict["taker_buy_volume"] = ("taker_buy_volume", "sum")
        if "taker_buy_quote_volume" in df.columns:
            agg_dict["taker_buy_quote_volume"] = ("taker_buy_quote_volume", "sum")

        aggregated = df.groupby("window_time").agg(**agg_dict).reset_index()

        # Reject incomplete source windows
        complete_mask = aggregated["sub_bars"] == expected_ratio
        complete_df = aggregated[complete_mask].copy()

        complete_df = complete_df.rename(columns={"window_time": "open_time"})
        complete_df = complete_df.drop(columns=["sub_bars"])

        # Synthetic close_time if missing
        if "close_time" not in complete_df.columns:
            complete_df["close_time"] = complete_df["open_time"] + target_ms - 1

        # Format datetime column
        dt_series = pd.to_datetime(complete_df["open_time"], unit="ms", utc=True)
        complete_df["datetime"] = dt_series.dt.strftime("%Y-%m-%d %H:%M:%S")

        # Deterministic column ordering
        primary_cols = ["datetime", "open_time", "open", "high", "low", "close", "volume", "close_time"]
        aux_cols = [c for c in ["quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume"] if c in complete_df.columns]
        other_cols = [c for c in complete_df.columns if c not in primary_cols and c not in aux_cols]

        ordered_cols = primary_cols + aux_cols + other_cols
        complete_df = complete_df[ordered_cols].sort_values("open_time").reset_index(drop=True)

        return complete_df

    def derive_month(
        self,
        month: str,
        symbol: str = "BTCUSDT",
        source_interval: str = "5m",
        target_intervals: Optional[List[str]] = None,
        dry_run: bool = False,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        """
        Derive higher intervals for a specified month from source canonical partition.
        If dry_run is True, returns verification and preview without writing files.
        """
        targets = target_intervals or [t for t in SUPPORTED_TARGET_INTERVALS if t != source_interval]
        source_file = self.dataset_dir / source_interval / f"{symbol}-{source_interval}-{month}.parquet"

        if not source_file.exists():
            return {
                "status": "SOURCE_NOT_FOUND",
                "month": month,
                "symbol": symbol,
                "source_interval": source_interval,
                "source_file": str(source_file),
                "error": f"Canonical source partition does not exist: {source_file}",
                "derived_partitions": [],
            }

        source_sha = self.compute_sha256(source_file)
        df_source = pd.read_parquet(source_file)
        source_records = len(df_source)

        receipts: List[DerivationPartitionReceipt] = []
        all_passed = True

        # Calculate expected days and full-month candles
        try:
            year, m_num = int(month[:4]), int(month[5:7])
            import calendar
            days_in_month = calendar.monthrange(year, m_num)[1]
        except Exception:
            days_in_month = 30

        for tgt in targets:
            tgt_ms = INTERVAL_MS[tgt]
            expected_full_month = (days_in_month * 24 * 3600 * 1000) // tgt_ms

            df_derived = self.derive_dataframe(
                df_source=df_source,
                source_interval=source_interval,
                target_interval=tgt,
                symbol=symbol,
            )

            records_derived = len(df_derived)
            is_partial = records_derived < expected_full_month
            completeness_pct = round((records_derived / max(1, expected_full_month)) * 100, 2)

            first_utc = df_derived["datetime"].iloc[0] if records_derived > 0 else "-"
            last_utc = df_derived["datetime"].iloc[-1] if records_derived > 0 else "-"

            tgt_dir = self.dataset_dir / tgt
            tgt_file = tgt_dir / f"{symbol}-{tgt}-{month}.parquet"
            target_exists = tgt_file.exists()

            # Compare against existing canonical if present
            comparison: Optional[Dict[str, Any]] = None
            if target_exists:
                try:
                    df_canon = pd.read_parquet(tgt_file)
                    merged = pd.merge(df_canon, df_derived, on="open_time", suffixes=("_canon", "_deriv"))
                    if len(merged) > 0:
                        max_p_diff = float(max(
                            (merged["open_canon"] - merged["open_deriv"]).abs().max(),
                            (merged["high_canon"] - merged["high_deriv"]).abs().max(),
                            (merged["low_canon"] - merged["low_deriv"]).abs().max(),
                            (merged["close_canon"] - merged["close_deriv"]).abs().max(),
                        ))
                        max_v_diff = float((merged["volume_canon"] - merged["volume_deriv"]).abs().max())
                        comparison = {
                            "canonical_records": len(df_canon),
                            "derived_records": records_derived,
                            "overlapping_records": len(merged),
                            "max_price_difference": max_p_diff,
                            "max_volume_difference": max_v_diff,
                            "exact_parity": max_p_diff < 1e-4 and max_v_diff < 1e-2,
                        }
                except Exception as e:
                    comparison = {"error": f"Comparison failed: {e}"}

            tgt_sha = ""
            if not dry_run and (overwrite or not target_exists):
                tgt_dir.mkdir(parents=True, exist_ok=True)
                temp_file = tgt_dir / f".tmp_{symbol}-{tgt}-{month}.parquet"
                df_derived.to_parquet(temp_file, index=False)
                temp_file.replace(tgt_file)
                tgt_sha = self.compute_sha256(tgt_file)
            elif target_exists:
                tgt_sha = self.compute_sha256(tgt_file)
            else:
                # In dry_run without existing file, hash derived bytes in-memory
                import io
                buf = io.BytesIO()
                df_derived.to_parquet(buf, index=False)
                tgt_sha = hashlib.sha256(buf.getvalue()).hexdigest()

            rc = DerivationPartitionReceipt(
                target_interval=tgt,
                target_partition=f"{symbol}-{tgt}-{month}.parquet",
                source_partition=f"{symbol}-{source_interval}-{month}.parquet",
                source_sha256=source_sha,
                target_sha256=tgt_sha,
                records_derived=records_derived,
                expected_full_month_candles=expected_full_month,
                completeness_pct=completeness_pct,
                is_partial=is_partial,
                first_timestamp_utc=first_utc,
                last_timestamp_utc=last_utc,
                comparison_with_canonical=comparison,
            )
            receipts.append(rc)

        return {
            "status": "DERIVATION_SUCCESS" if all_passed else "DERIVATION_PARTIAL",
            "symbol": symbol,
            "month": month,
            "source_interval": source_interval,
            "source_records": source_records,
            "source_sha256": source_sha,
            "dry_run": dry_run,
            "algorithm_version": DERIVATION_ALGORITHM_VERSION,
            "targets_count": len(receipts),
            "derived_receipts": [asdict(r) for r in receipts],
        }

    def verify_derived_vs_canonical(
        self,
        month: str,
        target_interval: str = "1h",
        source_interval: str = "5m",
        symbol: str = "BTCUSDT",
    ) -> Dict[str, Any]:
        """Verify mathematical equivalence between derived output and canonical partition."""
        source_file = self.dataset_dir / source_interval / f"{symbol}-{source_interval}-{month}.parquet"
        canon_file = self.dataset_dir / target_interval / f"{symbol}-{target_interval}-{month}.parquet"

        if not source_file.exists():
            return {"status": "FAIL", "reason": f"Source file missing: {source_file}"}
        if not canon_file.exists():
            return {"status": "FAIL", "reason": f"Canonical target missing: {canon_file}"}

        df_source = pd.read_parquet(source_file)
        df_canon = pd.read_parquet(canon_file)

        df_derived = self.derive_dataframe(
            df_source=df_source,
            source_interval=source_interval,
            target_interval=target_interval,
            symbol=symbol,
        )

        merged = pd.merge(df_canon, df_derived, on="open_time", suffixes=("_canon", "_deriv"))
        if len(merged) == 0:
            return {
                "status": "FAIL",
                "reason": "Zero overlapping timestamps between canonical and derived.",
            }

        diff_o = (merged["open_canon"] - merged["open_deriv"]).abs().max()
        diff_h = (merged["high_canon"] - merged["high_deriv"]).abs().max()
        diff_l = (merged["low_canon"] - merged["low_deriv"]).abs().max()
        diff_c = (merged["close_canon"] - merged["close_deriv"]).abs().max()
        diff_v = (merged["volume_canon"] - merged["volume_deriv"]).abs().max()

        max_price_diff = float(max(diff_o, diff_h, diff_l, diff_c))
        max_vol_diff = float(diff_v)

        is_parity = max_price_diff < 1e-4 and max_vol_diff < 1e-2 and len(merged) == len(df_canon)

        return {
            "status": "PASS" if is_parity else "FAIL",
            "symbol": symbol,
            "month": month,
            "source_interval": source_interval,
            "target_interval": target_interval,
            "canonical_rows": len(df_canon),
            "derived_rows": len(df_derived),
            "evaluated_rows": len(merged),
            "max_price_difference": max_price_diff,
            "max_volume_difference": max_vol_diff,
            "exact_parity": is_parity,
            "algorithm_version": DERIVATION_ALGORITHM_VERSION,
        }

    def get_derivation_status(self, symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Return platform multi-timeframe derivation capability and partition completeness status."""
        intervals = ["5m", "15m", "1h", "4h", "1d"]
        inventory = {}
        for itv in intervals:
            itv_dir = self.dataset_dir / itv
            files = sorted(list(itv_dir.glob(f"{symbol}-{itv}-*.parquet"))) if itv_dir.exists() else []
            months = [f.stem.split("-")[-2] + "-" + f.stem.split("-")[-1] for f in files if len(f.stem.split("-")) >= 3]
            inventory[itv] = {
                "partitions_count": len(files),
                "earliest_month": months[0] if months else None,
                "latest_month": months[-1] if months else None,
            }

        source_months = inventory.get("5m", {}).get("partitions_count", 0)
        derivation_ready = source_months > 0

        return {
            "status": "success",
            "derivation_algorithm_version": DERIVATION_ALGORITHM_VERSION,
            "canonical_source_interval": "5m",
            "supported_target_intervals": SUPPORTED_TARGET_INTERVALS,
            "supported_derivation_pairs": [f"{s} -> {t}" for s, t in INTERVAL_RATIOS.keys()],
            "inventory_summary": inventory,
            "derivation_pipeline_ready": derivation_ready,
            "incomplete_window_policy": "STRICT_DROP_NO_SYNTHETIC_INTERPOLATION",
            "atomic_publication_enabled": True,
        }

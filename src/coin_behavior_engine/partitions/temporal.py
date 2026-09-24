"""Strict temporal partition manager for Sprint 02 research.

Partitions:
- DISCOVERY: 2021-01-01 00:00:00 UTC to 2024-12-31 23:59:59 UTC
  All hypothesis generation, model parameter fitting, feature calibration.
- VALIDATION: 2025-01-01 00:00:00 UTC to 2025-12-31 23:59:59 UTC
  Frozen out-of-sample testing. Zero parameter fitting.
- OBSERVED_HOLDOUT_2026: 2026-01-01 00:00:00 UTC onward
  Preserved from Sprint 01/01.1. Post-hoc audit check only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Dict, Tuple, Any
import pandas as pd

from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.utils.timestamp import to_utc_datetime


PARTITION_RANGES = {
    "DISCOVERY": ("2021-01-01 00:00:00", "2024-12-31 23:59:59"),
    "VALIDATION": ("2025-01-01 00:00:00", "2025-12-31 23:59:59"),
    "OBSERVED_HOLDOUT_2026": ("2026-01-01 00:00:00", "2026-12-31 23:59:59"),
}


def compute_partition_hash(df: pd.DataFrame) -> str:
    """Compute deterministic SHA256 hash of open timestamps and close prices."""
    if df.empty:
        return ""
    data_str = df["timestamp_open"].astype(str) + "_" + df["close"].round(4).astype(str)
    return hashlib.sha256(data_str.str.cat(sep=";").encode("utf-8")).hexdigest()


class TemporalPartitionManager:
    """Slices canonical datasets into frozen temporal partitions and generates provenance manifest."""

    def __init__(self, output_dir: str | Path = "data/reports/sprint02"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def slice_partitions(
        self, df: pd.DataFrame
    ) -> Dict[str, pd.DataFrame]:
        """Slice full canonical dataframe into Discovery, Validation, and Observed Holdout."""
        if "datetime_open" not in df.columns:
            raise ValueError("Input DataFrame must contain 'datetime_open' column.")

        partitions = {}
        manifest_meta = {}

        for part_name, (start_str, end_str) in PARTITION_RANGES.items():
            start_dt = to_utc_datetime(start_str)
            end_dt = to_utc_datetime(end_str)

            mask = (df["datetime_open"] >= start_dt) & (df["datetime_open"] <= end_dt)
            part_df = df.loc[mask].copy().reset_index(drop=True)

            partitions[part_name] = part_df
            hash_val = compute_partition_hash(part_df)

            manifest_meta[part_name] = {
                "start_utc": str(start_dt),
                "end_utc": str(end_dt),
                "actual_start": str(part_df["datetime_open"].min()) if not part_df.empty else None,
                "actual_end": str(part_df["datetime_open"].max()) if not part_df.empty else None,
                "candle_count": len(part_df),
                "sha256": hash_val,
                "columns": list(part_df.columns),
                "null_count": int(part_df.isnull().sum().sum()),
            }

            logger.info(
                f"Partition [{part_name}]: {len(part_df)} candles "
                f"({manifest_meta[part_name]['actual_start']} to {manifest_meta[part_name]['actual_end']})"
            )

        manifest_path = self.output_dir / "partition_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_meta, f, indent=2)
        logger.info(f"Saved partition manifest to {manifest_path}")

        return partitions

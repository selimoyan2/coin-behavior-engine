"""Dataset Manager for Coin Behavior Engine.

Provides versioned, append-capable historical dataset cataloging,
partition pruning, candle querying, completeness verification,
and gap detection across multi-year historical archives.
"""

from __future__ import annotations

import calendar
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("cbe.dataset_manager")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_DIR = REPO_ROOT / "data" / "binance_spot_multiyear"
SUPPORTED_INTERVALS = ("5m", "15m", "1h", "4h", "1d")

# Nominal interval duration in milliseconds
INTERVAL_DURATIONS_MS: Dict[str, int] = {
    "1m": 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


MONTH_NAMES_TR = {
    "01": "Ocak", "02": "Şubat", "03": "Mart", "04": "Nisan",
    "05": "Mayıs", "06": "Haziran", "07": "Temmuz", "08": "Ağustos",
    "09": "Eylül", "10": "Ekim", "11": "Kasım", "12": "Aralık"
}


def format_tr_month(m_str: str) -> str:
    """Format YYYY-MM into Turkish readable month, e.g. 2026-10 -> Ekim 2026."""
    if len(m_str) >= 7 and m_str[4] == "-":
        yr, mn = m_str[:4], m_str[5:7]
        return f"{MONTH_NAMES_TR.get(mn, mn)} {yr}"
    return m_str


@dataclass(frozen=True)
class PartitionInfo:
    interval: str
    year: int
    month: int
    month_str: str  # YYYY-MM
    file_path: Path
    file_size_bytes: int
    file_mtime_utc: str
    sha256_hash: str


@dataclass
class MonthCompleteness:
    month_str: str
    interval: str
    status: str  # COMPLETE, PARTIAL, MISSING, EMPTY
    expected_candles: int
    actual_candles: int
    earliest_candle_utc: Optional[str]
    latest_candle_utc: Optional[str]
    missing_candles_count: int
    gaps_count: int


class DatasetManager:
    """Manages the versioned historical dataset archive and catalog."""

    _lock = threading.Lock()
    _instance: Optional["DatasetManager"] = None

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_DATASET_DIR
        self._manifest_cache: Optional[Dict[str, Any]] = None
        self._manifest_cache_time: float = 0.0
        self._cache_ttl_sec: float = 60.0
        self._candle_cache: Dict[str, List[Dict[str, Any]]] = {}

    @classmethod
    def get_instance(cls, base_dir: Optional[Path] = None) -> "DatasetManager":
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(base_dir)
            elif base_dir and cls._instance.base_dir != Path(base_dir):
                cls._instance = cls(base_dir)
            return cls._instance

    def invalidate_cache(self) -> None:
        """Clear cached manifest and candle stores after imports."""
        with self._lock:
            self._manifest_cache = None
            self._manifest_cache_time = 0.0
            self._candle_cache.clear()
            logger.info("DatasetManager cache invalidated.")

    def get_manifest(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Compute or retrieve deterministic dataset manifest."""
        now = time.time()
        with self._lock:
            if (
                not force_refresh
                and self._manifest_cache is not None
                and (now - self._manifest_cache_time) < self._cache_ttl_sec
            ):
                return self._manifest_cache

        manifest = self._build_manifest()
        with self._lock:
            self._manifest_cache = manifest
            self._manifest_cache_time = time.time()
        return manifest

    def _build_manifest(self) -> Dict[str, Any]:
        """Scan directory and build comprehensive catalog."""
        if not self.base_dir.exists():
            return {
                "dataset_id": "BTCUSDT_BINANCE_SPOT_MULTIYEAR",
                "status": "NOT_FOUND",
                "manifest_version": "UNKNOWN",
                "base_dir": str(self.base_dir),
                "total_partitions": 0,
                "intervals": {},
                "earliest_candle_utc": None,
                "latest_candle_utc": None,
                "available_months": [],
            }

        intervals_info: Dict[str, Any] = {}
        all_months_set: Set[str] = set()
        total_partitions = 0
        total_size_bytes = 0
        hash_entries: List[str] = []

        global_earliest_utc: Optional[str] = None
        global_latest_utc: Optional[str] = None

        for intv in SUPPORTED_INTERVALS:
            intv_dir = self.base_dir / intv
            if not intv_dir.exists():
                intervals_info[intv] = {
                    "partition_count": 0,
                    "months": [],
                    "size_mb": 0.0,
                    "earliest_month": None,
                    "latest_month": None,
                }
                continue

            parquet_files = sorted(intv_dir.glob(f"BTCUSDT-{intv}-*.parquet"))
            intv_months: List[str] = []
            intv_size = 0

            for p in parquet_files:
                stem = p.stem  # e.g. BTCUSDT-5m-2026-09
                m_str = stem.replace(f"BTCUSDT-{intv}-", "")
                if len(m_str) == 7 and m_str[4] == "-":
                    intv_months.append(m_str)
                    all_months_set.add(m_str)

                stat = p.stat()
                intv_size += stat.st_size
                hash_entries.append(f"{intv}:{p.name}:{stat.st_size}:{int(stat.st_mtime)}")

            total_partitions += len(parquet_files)
            total_size_bytes += intv_size

            intervals_info[intv] = {
                "partition_count": len(parquet_files),
                "months": sorted(intv_months),
                "size_mb": round(intv_size / (1024 * 1024), 2),
                "earliest_month": intv_months[0] if intv_months else None,
                "latest_month": intv_months[-1] if intv_months else None,
            }

        sorted_months = sorted(list(all_months_set))
        if sorted_months:
            # Approximate boundaries from earliest/latest month
            global_earliest_utc = f"{sorted_months[0]}-01T00:00:00Z"
            latest_m = sorted_months[-1]
            try:
                yr, mn = int(latest_m[:4]), int(latest_m[5:7])
                last_day = calendar.monthrange(yr, mn)[1]
                global_latest_utc = f"{latest_m}-{last_day:02d}T23:59:59Z"
            except Exception:
                global_latest_utc = f"{latest_m}-28T23:59:59Z"

        # Deterministic manifest digest
        manifest_digest = hashlib.sha256(
            "\n".join(sorted(hash_entries)).encode("utf-8")
        ).hexdigest()

        return {
            "dataset_id": "BTCUSDT_BINANCE_SPOT_MULTIYEAR",
            "symbol": "BTCUSDT",
            "market_type": "SPOT",
            "source_provenance": "Binance Official Monthly Historical Kline Archive",
            "manifest_version": f"cbe-manifest-v2-{manifest_digest[:12]}",
            "manifest_hash": manifest_digest,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "base_dir": str(self.base_dir),
            "total_partitions": total_partitions,
            "total_size_mb": round(total_size_bytes / (1024 * 1024), 2),
            "supported_intervals": list(SUPPORTED_INTERVALS),
            "available_months": sorted_months,
            "earliest_month": sorted_months[0] if sorted_months else None,
            "latest_month": sorted_months[-1] if sorted_months else None,
            "earliest_candle_utc": global_earliest_utc,
            "latest_candle_utc": global_latest_utc,
            "intervals_detail": intervals_info,
            "governance_classification": "OFFLINE_HISTORICAL_RESEARCH_DATASET",
        }

    def get_available_dates(self, interval: str = "5m") -> Dict[str, Any]:
        """Return available years, months, and days for UI navigation."""
        intv = interval.lower() if interval.lower() in SUPPORTED_INTERVALS else "5m"
        manifest = self.get_manifest()
        intv_detail = manifest.get("intervals_detail", {}).get(intv, {})
        months = intv_detail.get("months", [])

        years_dict: Dict[str, List[str]] = {}
        for m in months:
            y = m[:4]
            years_dict.setdefault(y, []).append(m)

        latest_candle = self.get_latest_candle(intv)

        return {
            "status": "success",
            "interval": intv,
            "total_months": len(months),
            "available_years": sorted(list(years_dict.keys())),
            "available_months": months,
            "months_by_year": years_dict,
            "earliest_month": months[0] if months else None,
            "latest_month": months[-1] if months else None,
            "latest_available_candle": latest_candle,
            "manifest_version": manifest.get("manifest_version"),
        }

    def get_latest_candle(self, interval: str = "5m") -> Optional[Dict[str, Any]]:
        """Retrieve the exact latest verified candle in the dataset."""
        intv = interval.lower() if interval.lower() in SUPPORTED_INTERVALS else "5m"
        manifest = self.get_manifest()
        months = manifest.get("intervals_detail", {}).get(intv, {}).get("months", [])
        if not months:
            return None

        latest_m = months[-1]
        target_file = self.base_dir / intv / f"BTCUSDT-{intv}-{latest_m}.parquet"
        if not target_file.exists():
            return None

        try:
            import pandas as pd
            df = pd.read_parquet(target_file)
            if df.empty:
                return None
            last_row = df.iloc[-1]
            ot = int(last_row["open_time"])
            sec = ot // 1000
            dt_str = datetime.fromtimestamp(sec, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            return {
                "timestamp_utc": dt_str,
                "open_time": ot,
                "interval": intv,
                "month": latest_m,
                "open": float(last_row["open"]),
                "high": float(last_row["high"]),
                "low": float(last_row["low"]),
                "close": float(last_row["close"]),
                "volume": float(last_row["volume"]),
            }
        except Exception as e:
            logger.warning("Failed to read latest candle from %s: %s", target_file, e)
            return None

    def get_month_completeness(self, month: str, interval: str = "5m") -> MonthCompleteness:
        """Analyze completeness and missing candles for a given month."""
        intv = interval.lower() if interval.lower() in SUPPORTED_INTERVALS else "5m"
        target_file = self.base_dir / intv / f"BTCUSDT-{intv}-{month}.parquet"

        if not target_file.exists():
            return MonthCompleteness(
                month_str=month,
                interval=intv,
                status="NOT_IMPORTED",
                expected_candles=0,
                actual_candles=0,
                earliest_candle_utc=None,
                latest_candle_utc=None,
                missing_candles_count=0,
                gaps_count=0,
            )

        try:
            yr, mn = int(month[:4]), int(month[5:7])
            days_in_month = calendar.monthrange(yr, mn)[1]
        except Exception:
            days_in_month = 30

        duration_ms = INTERVAL_DURATIONS_MS.get(intv, 300_000)
        expected_total = (days_in_month * 24 * 60 * 60 * 1000) // duration_ms

        try:
            import pandas as pd
            df = pd.read_parquet(target_file, columns=["open_time"])
            actual_count = len(df)
            if actual_count == 0:
                return MonthCompleteness(
                    month_str=month,
                    interval=intv,
                    status="EMPTY",
                    expected_candles=expected_total,
                    actual_candles=0,
                    earliest_candle_utc=None,
                    latest_candle_utc=None,
                    missing_candles_count=expected_total,
                    gaps_count=1,
                )

            times = df["open_time"].sort_values().values
            first_ts = int(times[0])
            last_ts = int(times[-1])
            first_utc = datetime.fromtimestamp(first_ts // 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            last_utc = datetime.fromtimestamp(last_ts // 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            # Check gaps
            diffs = times[1:] - times[:-1]
            gap_indices = (diffs > duration_ms).nonzero()[0]
            gaps_count = len(gap_indices)

            # Determine status
            if actual_count >= expected_total and gaps_count == 0:
                status = "COMPLETE"
                missing = 0
            elif actual_count > 0:
                status = "PARTIAL"
                missing = max(0, expected_total - actual_count)
            else:
                status = "MISSING"
                missing = expected_total

            return MonthCompleteness(
                month_str=month,
                interval=intv,
                status=status,
                expected_candles=expected_total,
                actual_candles=actual_count,
                earliest_candle_utc=first_utc,
                latest_candle_utc=last_utc,
                missing_candles_count=missing,
                gaps_count=gaps_count,
            )
        except Exception as e:
            logger.error("Error evaluating completeness for %s: %s", target_file, e)
            return MonthCompleteness(
                month_str=month,
                interval=intv,
                status="ERROR",
                expected_candles=expected_total,
                actual_candles=0,
                earliest_candle_utc=None,
                latest_candle_utc=None,
                missing_candles_count=expected_total,
                gaps_count=0,
            )

    def query_candles(
        self,
        interval: str = "5m",
        month: Optional[str] = None,
        day: Optional[str] = None,
        time_slot: Optional[str] = None,
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
        regime_map: Optional[Dict[int, str]] = None,
    ) -> Dict[str, Any]:
        """Query bounded candles with timeline, day, or slot filtering."""
        intv = interval.lower() if interval.lower() in SUPPORTED_INTERVALS else "5m"
        manifest = self.get_manifest()
        available_months = manifest.get("intervals_detail", {}).get(intv, {}).get("months", [])

        if not available_months:
            return {
                "status": "no_data",
                "available": False,
                "message": f"'{intv}' zaman aralığı için doğrulanmış veri bulunmuyor.",
                "candles": [],
                "total_records": 0,
            }

        # Resolve target month
        target_month = month.strip() if month else None
        if not target_month:
            # If start_utc is provided, parse month from it
            if start_utc:
                try:
                    target_month = start_utc[:7]
                except Exception:
                    pass

        if not target_month:
            target_month = available_months[-1]

        # Verify month availability
        if target_month not in available_months:
            latest_m = available_months[-1]
            return {
                "status": "no_data",
                "available": False,
                "message": f"{format_tr_month(target_month)} için doğrulanmış tarihsel mum verisi henüz bulunmuyor.",
                "requested_month": target_month,
                "latest_available_month": latest_m,
                "available_months": available_months,
                "candles": [],
                "total_records": 0,
            }

        target_file = self.base_dir / intv / f"BTCUSDT-{intv}-{target_month}.parquet"
        if not target_file.exists():
            return {
                "status": "no_data",
                "available": False,
                "message": f"{target_month} ayı veri dosyası disk üzerinde bulunamadı.",
                "requested_month": target_month,
                "candles": [],
                "total_records": 0,
            }

        # Cache key based on file mtime
        file_mtime = target_file.stat().st_mtime
        cache_key = f"{intv}_{target_month}_{file_mtime}"

        with self._lock:
            if cache_key in self._candle_cache:
                all_candles = self._candle_cache[cache_key]
            else:
                all_candles = self._read_and_format_parquet(target_file, reg_map=regime_map or {})
                self._candle_cache[cache_key] = all_candles

        # Apply filtering
        filtered = all_candles

        # Day filtering (e.g. "2026-09-15" or "15")
        if day and day.strip() and day.strip().lower() != "all":
            d_val = day.strip()
            if len(d_val) <= 2:
                d_str = f"{target_month}-{int(d_val):02d}"
            else:
                d_str = d_val[:10]
            filtered = [c for c in filtered if c["datetime"].startswith(d_str)]

        # Time slot filtering (UTC)
        if time_slot and time_slot.strip() and time_slot.strip().lower() != "all":
            slot = time_slot.strip().lower()
            if slot in ("00-06", "0-6"):
                filtered = [c for c in filtered if "T00:" <= c["datetime"][10:14] < "T06:"]
            elif slot in ("06-12", "6-12"):
                filtered = [c for c in filtered if "T06:" <= c["datetime"][10:14] < "T12:"]
            elif slot in ("12-18"):
                filtered = [c for c in filtered if "T12:" <= c["datetime"][10:14] < "T18:"]
            elif slot in ("18-24", "18-00"):
                filtered = [c for c in filtered if "T18:" <= c["datetime"][10:14] <= "T23:"]

        # Timestamp range filtering
        if start_utc:
            filtered = [c for c in filtered if c["datetime"] >= start_utc]
        if end_utc:
            filtered = [c for c in filtered if c["datetime"] <= end_utc]

        total_filtered = len(filtered)
        clamped_limit = min(1000, max(1, limit))
        clamped_offset = max(0, offset)
        sliced = filtered[clamped_offset : clamped_offset + clamped_limit]

        return {
            "status": "success",
            "available": True,
            "interval": intv,
            "month": target_month,
            "total_records": total_filtered,
            "limit": clamped_limit,
            "offset": clamped_offset,
            "returned_count": len(sliced),
            "manifest_version": manifest.get("manifest_version"),
            "first_returned_timestamp": sliced[0]["datetime"] if sliced else None,
            "last_returned_timestamp": sliced[-1]["datetime"] if sliced else None,
            "candles": sliced,
        }

    def _read_and_format_parquet(
        self,
        file_path: Path,
        reg_map: Dict[int, str],
    ) -> List[Dict[str, Any]]:
        """Read parquet quickly using vectorized operations."""
        import pandas as pd
        df = pd.read_parquet(
            file_path,
            columns=["open_time", "open", "high", "low", "close", "volume"],
        )

        candles: List[Dict[str, Any]] = []
        # Pre-convert to python records
        records = df.to_dict(orient="records")
        for r in records:
            ot = int(r["open_time"])
            sec = ot // 1000
            dt_str = datetime.fromtimestamp(sec, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            reg = reg_map.get(ot, "SIDEWAYS")
            candles.append({
                "open_time": ot,
                "datetime": dt_str,
                "open": float(r["open"]),
                "high": float(r["high"]),
                "low": float(r["low"]),
                "close": float(r["close"]),
                "volume": float(r["volume"]),
                "regime": reg,
            })
        return candles

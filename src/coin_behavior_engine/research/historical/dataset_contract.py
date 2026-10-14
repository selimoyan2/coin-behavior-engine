"""Historical Market Dataset Contract, Specification & Isolated Storage.

Sprint 09.20: Historical Market Research Foundation.

Enforces:
1. Legitimate historical exchange boundaries (e.g., Binance Spot BTCUSDT began on 2017-08-17T04:00:00Z;
   prior timestamps are rejected as impossible historical data).
2. Clean separation of historical backfill from prospectively captured live evidence.
3. Bounded-memory chunked/streaming dataset reading (preventing multi-year OOMs).
4. Idempotent storage with provenance metadata tracking.
5. Storage isolation: data/historical/ is completely isolated from live capture and prospective scoring volumes.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

import pandas as pd

from coin_behavior_engine.shadow_v080.market_data_contract import (
    CANDLE_INTERVAL_MS,
    MarketType,
    ProvenanceSource,
    ValidatedCandle,
)

logger = logging.getLogger("cbe_historical_dataset")

# Binance Spot BTCUSDT began trading on August 17, 2017 at 04:00:00 UTC (timestamp 1502942400000 ms)
BINANCE_SPOT_BTCUSDT_GENESIS_UTC = "2017-08-17T04:00:00Z"
BINANCE_SPOT_BTCUSDT_GENESIS_MS = 1502942400000


class HistoricalDataBoundaryError(ValueError):
    """Raised when historical dataset requests or contains data preceding exchange launch."""
    pass


class HistoricalDataStorageError(ValueError, RuntimeError):
    """Raised when historical storage operations fail or violate isolation rules."""
    pass


@dataclass(frozen=True)
class HistoricalMarketSpec:
    """Specification of a historical market dataset slice."""
    symbol: str = "BTCUSDT"
    interval: str = "5m"
    exchange: str = "BINANCE"
    market_type: str = MarketType.SPOT.value
    start_time_utc: Optional[str] = None
    end_time_utc: Optional[str] = None
    start_timestamp_ms: Optional[int] = None
    end_timestamp_ms: Optional[int] = None
    timeframe: Optional[str] = None
    dataset_tag: Optional[str] = None

    def __post_init__(self) -> None:
        if self.timeframe is not None:
            object.__setattr__(self, "interval", self.timeframe)

        if self.symbol != "BTCUSDT":
            logger.info(f"HistoricalMarketSpec initialized for non-default symbol '{self.symbol}'.")
        if self.interval != "5m":
            logger.info(f"HistoricalMarketSpec initialized for non-default interval '{self.interval}'.")

        # Normalize start timestamps
        start_ms = self.start_timestamp_ms
        if start_ms is None and self.start_time_utc is not None:
            start_dt = pd.Timestamp(self.start_time_utc, tz="UTC")
            start_ms = int(start_dt.timestamp() * 1000)
            object.__setattr__(self, "start_timestamp_ms", start_ms)
        elif start_ms is not None and self.start_time_utc is None:
            start_utc = pd.Timestamp(start_ms, unit="ms", tz="UTC").isoformat()
            object.__setattr__(self, "start_time_utc", start_utc)

        # Normalize end timestamps
        end_ms = self.end_timestamp_ms
        if end_ms is None and self.end_time_utc is not None:
            end_dt = pd.Timestamp(self.end_time_utc, tz="UTC")
            end_ms = int(end_dt.timestamp() * 1000)
            object.__setattr__(self, "end_timestamp_ms", end_ms)
        elif end_ms is not None and self.end_time_utc is None:
            end_utc = pd.Timestamp(end_ms, unit="ms", tz="UTC").isoformat()
            object.__setattr__(self, "end_time_utc", end_utc)

        # Validate exchange genesis boundary
        if self.exchange.upper() == "BINANCE" and self.symbol.upper() == "BTCUSDT":
            if start_ms is not None and start_ms < BINANCE_SPOT_BTCUSDT_GENESIS_MS:
                raise HistoricalDataBoundaryError(
                    f"Requested start timestamp ({start_ms} ms) precedes "
                    f"Binance Spot BTCUSDT launch ({BINANCE_SPOT_BTCUSDT_GENESIS_UTC}, {BINANCE_SPOT_BTCUSDT_GENESIS_MS} ms). "
                    "Binance history cannot be assumed to exist before Binance began operating."
                )

        # Validate range ordering
        if start_ms is not None and end_ms is not None:
            if end_ms <= start_ms:
                raise ValueError(
                    f"end_timestamp_ms ({end_ms}) must be > start_timestamp_ms ({start_ms})"
                )

    @property
    def interval_ms(self) -> int:
        if self.interval == "5m":
            return 300_000
        elif self.interval == "1m":
            return 60_000
        elif self.interval == "15m":
            return 900_000
        elif self.interval == "1h":
            return 3_600_000
        elif self.interval == "4h":
            return 14_400_000
        elif self.interval == "1d":
            return 86_400_000
        raise ValueError(f"Unsupported interval: {self.interval}")


@dataclass
class HistoricalDatasetProvenance:
    """Authoritative audit record of historical dataset origin and coverage."""
    dataset_id: str
    symbol: str
    interval: str
    exchange: str
    market_type: str
    provenance_source: str  # e.g., "HISTORICAL_BINANCE_ARCHIVE", "OFFLINE_RESEARCH_FIXTURE"
    earliest_candle_open_utc: str
    earliest_candle_open_ms: int
    latest_candle_open_utc: str
    latest_candle_open_ms: int
    total_bars: int
    sha256_checksum: str
    created_at_utc: str
    documentation_url: str = "https://data.binance.vision/"
    license_or_coverage_notes: str = "Binance public historical market klines"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HistoricalDatasetProvenance":
        return cls(**data)


class HistoricalDatasetReader:
    """Memory-bounded streaming reader for historical candle datasets."""

    def __init__(self, filepath: Union[str, Path]):
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            raise FileNotFoundError(f"Historical dataset file not found: {self.filepath}")

    def get_row_count(self) -> int:
        """Return total row count without loading all data into memory."""
        if self.filepath.suffix == ".parquet":
            import pyarrow.parquet as pq
            meta = pq.read_metadata(self.filepath)
            return meta.num_rows
        elif self.filepath.suffix in (".jsonl", ".ndjson"):
            count = 0
            with open(self.filepath, "r", encoding="utf-8") as f:
                for _ in f:
                    count += 1
            return count
        elif self.filepath.suffix == ".csv":
            count = 0
            with open(self.filepath, "r", encoding="utf-8") as f:
                next(f, None)  # header
                for _ in f:
                    count += 1
            return count
        df = pd.read_parquet(self.filepath)
        return len(df)

    def iter_chunks(self, chunk_size: int = 2000) -> Iterator[pd.DataFrame]:
        """Stream dataset in memory-bounded batches to prevent OOM across multi-year data."""
        if self.filepath.suffix == ".parquet":
            import pyarrow.parquet as pq
            parquet_file = pq.ParquetFile(self.filepath)
            for batch in parquet_file.iter_batches(batch_size=chunk_size):
                yield batch.to_pandas()
        elif self.filepath.suffix in (".jsonl", ".ndjson"):
            chunk: List[Dict[str, Any]] = []
            with open(self.filepath, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        chunk.append(json.loads(line))
                        if len(chunk) >= chunk_size:
                            yield pd.DataFrame(chunk)
                            chunk = []
            if chunk:
                yield pd.DataFrame(chunk)
        elif self.filepath.suffix == ".csv":
            for chunk_df in pd.read_csv(self.filepath, chunksize=chunk_size):
                yield chunk_df
        else:
            df = pd.read_parquet(self.filepath)
            for start_idx in range(0, len(df), chunk_size):
                yield df.iloc[start_idx : start_idx + chunk_size]


class HistoricalDatasetStore:
    """Isolated, crash-safe storage manager for historical research datasets."""

    def __init__(self, base_dir: Optional[Union[str, Path]] = None):
        if base_dir is None:
            # Default to isolated data/historical directory
            repo_root = Path(__file__).resolve().parents[4]
            self.base_dir = repo_root / "data" / "historical"
        else:
            self.base_dir = Path(base_dir)

        # STRICT ISOLATION INVARIANT:
        # Cannot point to live capture volume or prospective scoring live volume
        norm_str = str(self.base_dir.resolve()).lower().replace("\\", "/")
        if "live_capture" in norm_str or "cbe_080_live_capture" in norm_str:
            raise HistoricalDataStorageError(
                "Violation: HistoricalDatasetStore cannot point to live capture directory. "
                "Historical backfill must remain strictly separate from live evidence."
            )

        self.base_dir.mkdir(parents=True, exist_ok=True)

    def get_dataset_filepath(self, spec: HistoricalMarketSpec, ext: str = "parquet") -> Path:
        """Return standardized path for dataset."""
        tag_str = f"_{spec.dataset_tag}" if spec.dataset_tag else ""
        fname = f"historical_{spec.exchange.lower()}_{spec.symbol.lower()}_{spec.interval}{tag_str}.{ext}"
        return self.base_dir / fname

    def get_provenance_filepath(self, spec: HistoricalMarketSpec) -> Path:
        """Return path for dataset provenance metadata JSON."""
        tag_str = f"_{spec.dataset_tag}" if spec.dataset_tag else ""
        fname = f"historical_{spec.exchange.lower()}_{spec.symbol.lower()}_{spec.interval}{tag_str}_provenance.json"
        return self.base_dir / fname

    def save_dataset_atomic(
        self,
        spec: HistoricalMarketSpec,
        df: pd.DataFrame,
        provenance_source: str = "HISTORICAL_BINANCE_ARCHIVE",
    ) -> HistoricalDatasetProvenance:
        """Save historical dataset atomically with SHA-256 checksum and provenance."""
        if df.empty:
            raise ValueError("Cannot save empty historical dataframe.")

        if "timestamp_open" not in df.columns:
            raise KeyError("DataFrame must contain 'timestamp_open'.")

        # Sort chronologically and deduplicate on timestamp_open
        df_clean = df.drop_duplicates(subset=["timestamp_open"], keep="first")
        df_clean = df_clean.sort_values("timestamp_open").reset_index(drop=True)

        # Check earliest candle against genesis boundary
        earliest_ms = int(df_clean["timestamp_open"].min())
        latest_ms = int(df_clean["timestamp_open"].max())

        if spec.exchange.upper() == "BINANCE" and spec.symbol.upper() == "BTCUSDT":
            if earliest_ms < BINANCE_SPOT_BTCUSDT_GENESIS_MS:
                raise HistoricalDataBoundaryError(
                    f"Earliest candle timestamp {earliest_ms} precedes Binance Spot BTCUSDT launch ({BINANCE_SPOT_BTCUSDT_GENESIS_MS})."
                )

        target_file = self.get_dataset_filepath(spec, ext="parquet")
        tmp_file = target_file.with_suffix(".tmp.parquet")

        df_clean.to_parquet(tmp_file, index=False)

        # Compute SHA-256
        sha = hashlib.sha256()
        with open(tmp_file, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        file_hash = sha.hexdigest()

        # Atomic replace
        os.replace(tmp_file, target_file)

        earliest_utc = pd.Timestamp(earliest_ms, unit="ms", tz="UTC").isoformat()
        latest_utc = pd.Timestamp(latest_ms, unit="ms", tz="UTC").isoformat()

        prov = HistoricalDatasetProvenance(
            dataset_id=f"HIST-{spec.exchange.upper()}-{spec.symbol.upper()}-{spec.interval}-{earliest_ms}_{latest_ms}",
            symbol=spec.symbol.upper(),
            interval=spec.interval,
            exchange=spec.exchange.upper(),
            market_type=spec.market_type,
            provenance_source=provenance_source,
            earliest_candle_open_utc=earliest_utc,
            earliest_candle_open_ms=earliest_ms,
            latest_candle_open_utc=latest_utc,
            latest_candle_open_ms=latest_ms,
            total_bars=len(df_clean),
            sha256_checksum=file_hash,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
        )

        prov_path = self.get_provenance_filepath(spec)
        tmp_prov = prov_path.with_suffix(".tmp.json")
        with open(tmp_prov, "w", encoding="utf-8") as f:
            json.dump(prov.to_dict(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_prov, prov_path)

        logger.info(
            f"Saved historical dataset: {len(df_clean)} bars from {earliest_utc} to {latest_utc} (SHA-256: {file_hash[:12]}...)"
        )
        return prov

    def save_dataset(
        self,
        candles: Any,
        spec: HistoricalMarketSpec,
        file_format: str = "parquet",
        provenance_source: str = "HISTORICAL_RESEARCH_STREAM",
    ) -> Tuple[Path, Path]:
        """Save historical candles to file_format with atomic replace and provenance JSON.

        Returns (data_filepath, provenance_filepath).
        """
        if isinstance(candles, pd.DataFrame):
            df = candles.copy()
        else:
            df = pd.DataFrame(candles)

        if df.empty:
            raise ValueError("Cannot save empty historical candles.")

        if "timestamp_open" not in df.columns:
            if "open_time" in df.columns:
                df["timestamp_open"] = df["open_time"]
            elif "timestamp_ms" in df.columns:
                df["timestamp_open"] = df["timestamp_ms"]
            elif "timestamp" in df.columns:
                df["timestamp_open"] = df["timestamp"]
            else:
                raise KeyError("Candles must contain 'timestamp_open', 'open_time', or 'timestamp_ms'.")

        target_file = self.get_dataset_filepath(spec, ext=file_format)
        tmp_file = target_file.with_suffix(f".tmp.{file_format}")

        if file_format == "parquet":
            df.to_parquet(tmp_file, index=False)
        elif file_format in ("jsonl", "ndjson"):
            df.to_json(tmp_file, orient="records", lines=True)
        elif file_format == "csv":
            df.to_csv(tmp_file, index=False)
        else:
            raise ValueError(f"Unsupported file format: {file_format}")

        sha = hashlib.sha256()
        with open(tmp_file, "rb") as f:
            while chunk := f.read(65536):
                sha.update(chunk)
        file_hash = sha.hexdigest()

        os.replace(tmp_file, target_file)

        earliest_ms = int(df["timestamp_open"].min())
        latest_ms = int(df["timestamp_open"].max())
        earliest_utc = pd.Timestamp(earliest_ms, unit="ms", tz="UTC").isoformat()
        latest_utc = pd.Timestamp(latest_ms, unit="ms", tz="UTC").isoformat()

        prov = HistoricalDatasetProvenance(
            dataset_id=f"HIST-{spec.exchange.upper()}-{spec.symbol.upper()}-{spec.interval}-{earliest_ms}_{latest_ms}",
            symbol=spec.symbol.upper(),
            interval=spec.interval,
            exchange=spec.exchange.upper(),
            market_type=spec.market_type,
            provenance_source=provenance_source,
            earliest_candle_open_utc=earliest_utc,
            earliest_candle_open_ms=earliest_ms,
            latest_candle_open_utc=latest_utc,
            latest_candle_open_ms=latest_ms,
            total_bars=len(df),
            sha256_checksum=file_hash,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
        )

        prov_path = self.get_provenance_filepath(spec)
        tmp_prov = prov_path.with_suffix(".tmp.json")
        with open(tmp_prov, "w", encoding="utf-8") as f:
            json.dump(prov.to_dict(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_prov, prov_path)

        return target_file, prov_path

    def load_reader(self, spec: HistoricalMarketSpec) -> HistoricalDatasetReader:
        """Return chunked reader for dataset."""
        path = self.get_dataset_filepath(spec, ext="parquet")
        return HistoricalDatasetReader(path)


class HistoricalDatasetContract:
    """Static schema definitions and contract rules for historical research datasets."""
    REQUIRED_COLUMNS = [
        "timestamp_open",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "timestamp_close",
        "is_closed",
    ]
    OPTIONAL_COLUMNS = [
        "quote_volume",
        "trades_count",
        "taker_buy_base_volume",
        "datetime_open_utc",
        "datetime_close_utc",
        "provenance",
    ]

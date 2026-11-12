"""Historical Research Dataset Validation Engine (Module 28.1).

Provides rigorous scientific validation for historical research datasets:
- Schema and column validation.
- Timestamp parsing, ordering, timezone consistency, duplicate detection.
- Missing interval detection without synthetic imputation.
- OHLC mathematical integrity validation:
    high >= max(open, close)
    low <= min(open, close)
    high >= low
    positive prices and non-negative volume.
- Deterministic dataset fingerprinting.
- Integration with ScientificReadinessEvaluator for grounded provenance.
- Strict containment of quarantined datasets (e.g. October 2026 data).
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from coin_behavior_engine.product.scientific_readiness import ScientificReadinessEvaluator

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]

# Known quarantined dataset identifiers and file signatures
QUARANTINED_DATASET_IDS: Set[str] = {
    "RES-CRYPTO-01",
    "RES-QUARANTINE-01",
    "DS-BTC-5M-2026-10-INTAKE",
    "QUARANTINED_CONTAMINATED",
}

QUARANTINED_FILE_PATTERNS: Set[str] = {
    "BTCUSDT-5m-2026-10-intake.parquet",
    "2026-10",
    "quarantined",
}

# Cadence to timedelta in seconds
CADENCE_SECONDS: Dict[str, int] = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


@dataclass
class DatasetValidationReport:
    """Detailed structural and integrity validation report for a historical dataset."""
    dataset_id: str
    is_valid: bool
    schema_status: str
    temporal_status: str
    ohlc_status: str
    provenance_status: str
    quarantine_status: str
    observation_count: int
    observation_start: Optional[str] = None
    observation_end: Optional[str] = None
    duplicate_count: int = 0
    missing_interval_count: int = 0
    missing_intervals: List[Dict[str, Any]] = field(default_factory=list)
    detected_errors: List[str] = field(default_factory=list)
    validation_timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class HistoricalDatasetRecord:
    """Canonical historical research dataset record."""
    dataset_id: str
    dataset_version: str
    market: str
    instrument: str
    market_type: str
    timeframe: str
    observation_start: Optional[str]
    observation_end: Optional[str]
    observation_count: int
    source_artifact_ids: List[str]
    source_artifact_sha256: str
    source_manifest_id: Optional[str]
    source_manifest_verification_status: str
    provenance_status: str
    schema_validation_status: str
    temporal_integrity_status: str
    missing_observation_count: int
    duplicate_observation_count: int
    quarantine_status: str
    dataset_fingerprint: str
    validation_timestamp: str
    file_path: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DatasetValidationEngine:
    """Engine responsible for schema, temporal, mathematical and provenance validation

    of historical datasets.
    """

    @classmethod
    def compute_sha256(cls, path: Path) -> str:
        """Compute SHA-256 digest of a physical file."""
        if not path.exists() or not path.is_file():
            return ""
        hasher = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @classmethod
    def compute_dataset_fingerprint(
        cls,
        dataset_id: str,
        source_sha256: str,
        schema_version: str,
        observation_start: Optional[str],
        observation_end: Optional[str],
        observation_count: int,
        preprocessing_identity: str = "RAW_UNMODIFIED",
    ) -> str:
        """Create a deterministic fingerprint incorporating dataset identity,

        source artifact digest, schema version, observation boundaries and
        preprocessing identity.
        """
        payload = {
            "dataset_id": str(dataset_id),
            "source_sha256": str(source_sha256),
            "schema_version": str(schema_version),
            "observation_start": str(observation_start or ""),
            "observation_end": str(observation_end or ""),
            "observation_count": int(observation_count),
            "preprocessing_identity": str(preprocessing_identity),
        }
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    @classmethod
    def is_quarantined(cls, dataset_id: str, file_path: Optional[Path] = None) -> bool:
        """Check whether a dataset or file matches known quarantine restrictions."""
        ds_upper = str(dataset_id or "").upper().strip()
        for qid in QUARANTINED_DATASET_IDS:
            if qid in ds_upper:
                return True

        if file_path:
            fp_str = str(file_path).lower()
            for pattern in QUARANTINED_FILE_PATTERNS:
                if pattern.lower() in fp_str:
                    return True

        return False

    @classmethod
    def validate_schema(cls, df: pd.DataFrame) -> Tuple[bool, str, List[str]]:
        """Verify required columns and data types for OHLCV dataset."""
        errors: List[str] = []
        if df.empty:
            return False, "EMPTY_DATASET", ["Dataset contains zero observations."]

        # Check timestamp column
        ts_cols = [c for c in df.columns if c in ("timestamp", "open_time", "datetime", "date")]
        if not ts_cols:
            errors.append("Missing required timestamp column ('timestamp' or 'open_time').")

        # Check required price and volume columns
        required_numeric = ["open", "high", "low", "close", "volume"]
        missing_numeric = [col for col in required_numeric if col not in df.columns]
        if missing_numeric:
            errors.append(f"Missing required numeric columns: {missing_numeric}")

        if errors:
            return False, "SCHEMA_VALIDATION_FAILED", errors

        # Check data types for numeric columns
        for col in required_numeric:
            if not pd.api.types.is_numeric_dtype(df[col]):
                errors.append(f"Column '{col}' must be numeric, got {df[col].dtype}.")

        if errors:
            return False, "SCHEMA_TYPE_ERROR", errors

        return True, "STRUCTURE_VALIDATED", []

    @classmethod
    def validate_temporal_integrity(
        cls, df: pd.DataFrame, timeframe: str
    ) -> Tuple[bool, str, int, int, List[Dict[str, Any]], List[str]]:
        """Validate timestamp ordering, timezone consistency, duplicate detection,

        and missing interval detection without modifying or imputing the data.
        """
        errors: List[str] = []
        duplicates = 0
        missing_intervals: List[Dict[str, Any]] = []

        ts_col = "timestamp" if "timestamp" in df.columns else "open_time"
        if ts_col not in df.columns:
            return False, "TIMESTAMP_COLUMN_MISSING", 0, 0, [], ["No timestamp column found."]

        ts_series = df[ts_col]
        # Parse timestamps to UTC datetime
        try:
            if pd.api.types.is_numeric_dtype(ts_series):
                # Likely epoch milliseconds or seconds
                sample_val = float(ts_series.iloc[0])
                unit = "ms" if sample_val > 1e11 else "s"
                parsed_ts = pd.to_datetime(ts_series, unit=unit, utc=True)
            else:
                parsed_ts = pd.to_datetime(ts_series, utc=True)
        except Exception as e:
            return False, "TIMESTAMP_PARSE_FAILED", 0, 0, [], [f"Failed to parse timestamps: {str(e)}"]

        # Check monotonic ordering
        is_monotonic = parsed_ts.is_monotonic_increasing
        if not is_monotonic:
            errors.append("Timestamps are not strictly monotonically increasing.")

        # Check duplicates
        dup_mask = parsed_ts.duplicated()
        duplicates = int(dup_mask.sum())
        if duplicates > 0:
            errors.append(f"Detected {duplicates} duplicate timestamps.")

        # Check cadence intervals
        expected_sec = CADENCE_SECONDS.get(timeframe.lower())
        if expected_sec and len(parsed_ts) > 1:
            diffs = parsed_ts.diff().dropna()
            diff_secs = diffs.dt.total_seconds()

            # Any interval greater than 1.5 * expected_sec indicates a missing interval
            gap_mask = diff_secs > (expected_sec * 1.5)
            gap_indices = gap_mask[gap_mask].index

            for idx in gap_indices[:50]:  # limit detailed list to top 50
                prev_ts = parsed_ts.loc[idx - 1] if (idx - 1) in parsed_ts.index else None
                curr_ts = parsed_ts.loc[idx]
                gap_sec = diff_secs.loc[idx]
                missing_intervals.append({
                    "start": prev_ts.isoformat() if prev_ts is not None else None,
                    "end": curr_ts.isoformat(),
                    "gap_seconds": gap_sec,
                    "estimated_missing_candles": int(round(gap_sec / expected_sec)) - 1,
                })

        status = "TEMPORAL_INTEGRITY_VERIFIED"
        if duplicates > 0:
            status = "DUPLICATE_TIMESTAMPS_DETECTED"
        elif not is_monotonic:
            status = "TEMPORAL_ORDERING_FAILED"
        elif missing_intervals:
            status = "TEMPORAL_GAPS_DETECTED"

        is_valid = len(errors) == 0
        return is_valid, status, duplicates, len(missing_intervals), missing_intervals, errors

    @classmethod
    def validate_ohlc_mathematics(cls, df: pd.DataFrame) -> Tuple[bool, str, List[str]]:
        """Validate mathematical sanity for OHLC prices:

        high >= max(open, close)
        low <= min(open, close)
        high >= low
        prices > 0, volume >= 0
        """
        errors: List[str] = []
        req_cols = ["open", "high", "low", "close", "volume"]
        for c in req_cols:
            if c not in df.columns:
                return False, "MISSING_OHLC_COLUMNS", [f"Missing {c} column for OHLC check."]

        # Non-positive prices
        invalid_prices = (df["open"] <= 0) | (df["high"] <= 0) | (df["low"] <= 0) | (df["close"] <= 0)
        invalid_price_count = int(invalid_prices.sum())
        if invalid_price_count > 0:
            errors.append(f"Detected {invalid_price_count} observations with non-positive prices.")

        # Negative volume
        neg_volume = df["volume"] < 0
        neg_vol_count = int(neg_volume.sum())
        if neg_vol_count > 0:
            errors.append(f"Detected {neg_vol_count} observations with negative volume.")

        # High >= max(open, close)
        max_oc = df[["open", "close"]].max(axis=1)
        high_violations = df["high"] < (max_oc - 1e-8)
        high_viol_count = int(high_violations.sum())
        if high_viol_count > 0:
            errors.append(f"High price lower than max(open, close) in {high_viol_count} observations.")

        # Low <= min(open, close)
        min_oc = df[["open", "close"]].min(axis=1)
        low_violations = df["low"] > (min_oc + 1e-8)
        low_viol_count = int(low_violations.sum())
        if low_viol_count > 0:
            errors.append(f"Low price higher than min(open, close) in {low_viol_count} observations.")

        # High >= Low
        hl_violations = df["high"] < (df["low"] - 1e-8)
        hl_viol_count = int(hl_violations.sum())
        if hl_viol_count > 0:
            errors.append(f"High price lower than Low price in {hl_viol_count} observations.")

        is_valid = len(errors) == 0
        status = "OHLC_MATHEMATICALLY_CONSISTENT" if is_valid else "OHLC_INCONSISTENCY_DETECTED"
        return is_valid, status, errors

    @classmethod
    def validate_dataset(
        cls,
        dataset_id: str,
        file_path: Optional[str] = None,
        market: str = "BINANCE",
        instrument: str = "BTC/USDT",
        market_type: str = "SPOT",
        timeframe: Optional[str] = None,
        override_df: Optional[pd.DataFrame] = None,
    ) -> HistoricalDatasetRecord:
        """Validate a historical dataset completely across schema, temporal integrity,

        mathematical sanity, and trusted provenance.
        """
        ds_id = str(dataset_id or "").strip()
        if not ds_id:
            raise ValueError("dataset_id is mandatory for historical dataset validation.")

        detected_errors: List[str] = []

        # 1. Check Quarantine
        target_path = Path(file_path) if file_path else None
        if not target_path and ds_id in ScientificReadinessEvaluator.CANONICAL_HISTORICAL_DATASET_SPECIFICATIONS:
            spec = ScientificReadinessEvaluator.CANONICAL_HISTORICAL_DATASET_SPECIFICATIONS[ds_id]
            target_path = REPO_ROOT / spec["source_artifact"]

        is_quar = cls.is_quarantined(ds_id, target_path)
        quarantine_status = "QUARANTINED" if is_quar else "CLEAN"

        # 2. Check File Existence & Physical SHA-256
        source_sha256 = ""
        artifact_present = False
        if target_path and target_path.exists() and target_path.is_file():
            artifact_present = True
            source_sha256 = cls.compute_sha256(target_path)
        elif override_df is not None:
            artifact_present = True
            source_sha256 = hashlib.sha256(str(len(override_df)).encode()).hexdigest()
        else:
            detected_errors.append(f"Source artifact not found at {target_path}")

        # 3. Read Data
        df = override_df
        if df is None and artifact_present and target_path:
            try:
                if target_path.suffix == ".parquet":
                    df = pd.read_parquet(target_path)
                elif target_path.suffix == ".csv":
                    df = pd.read_csv(target_path)
                else:
                    detected_errors.append(f"Unsupported file format: {target_path.suffix}")
            except Exception as e:
                detected_errors.append(f"Failed to load dataset: {str(e)}")

        # Infer timeframe if not provided
        if not timeframe:
            if ds_id in ScientificReadinessEvaluator.CANONICAL_HISTORICAL_DATASET_SPECIFICATIONS:
                timeframe = ScientificReadinessEvaluator.CANONICAL_HISTORICAL_DATASET_SPECIFICATIONS[ds_id].get("window_cadence", "1h")
            elif "15m" in ds_id.lower() or (target_path and "15m" in target_path.name.lower()):
                timeframe = "15m"
            elif "5m" in ds_id.lower() or (target_path and "5m" in target_path.name.lower()):
                timeframe = "5m"
            elif "1h" in ds_id.lower() or (target_path and "1h" in target_path.name.lower()):
                timeframe = "1h"
            elif "1d" in ds_id.lower() or (target_path and "1d" in target_path.name.lower()):
                timeframe = "1d"
            else:
                timeframe = "1h"

        obs_count = len(df) if df is not None else 0
        obs_start = None
        obs_end = None
        schema_status = "UNVERIFIED"
        temporal_status = "UNVERIFIED"
        ohlc_status = "UNVERIFIED"
        duplicates = 0
        missing_count = 0

        if df is not None and not df.empty:
            # Schema
            schema_ok, schema_status, s_errs = cls.validate_schema(df)
            detected_errors.extend(s_errs)

            # Temporal
            temp_ok, temporal_status, duplicates, missing_count, missing_list, t_errs = (
                cls.validate_temporal_integrity(df, timeframe)
            )
            detected_errors.extend(t_errs)

            # OHLC
            ohlc_ok, ohlc_status, o_errs = cls.validate_ohlc_mathematics(df)
            detected_errors.extend(o_errs)

            # Extract start and end
            ts_col = "timestamp" if "timestamp" in df.columns else "open_time"
            if ts_col in df.columns:
                try:
                    if pd.api.types.is_numeric_dtype(df[ts_col]):
                        s_val = float(df[ts_col].iloc[0])
                        unit = "ms" if s_val > 1e11 else "s"
                        obs_start = pd.to_datetime(df[ts_col].iloc[0], unit=unit, utc=True).isoformat()
                        obs_end = pd.to_datetime(df[ts_col].iloc[-1], unit=unit, utc=True).isoformat()
                    else:
                        obs_start = pd.to_datetime(df[ts_col].iloc[0], utc=True).isoformat()
                        obs_end = pd.to_datetime(df[ts_col].iloc[-1], utc=True).isoformat()
                except Exception:
                    pass

        # 4. Provenance Status Determination
        # Delegate to ScientificReadinessEvaluator
        prov_result = ScientificReadinessEvaluator.verify_historical_dataset_provenance(ds_id)
        raw_prov_status = prov_result.get("provenance_status", "UNVERIFIED")

        if is_quar:
            provenance_status = "QUARANTINED"
        elif prov_result.get("is_verified") is True:
            # Check if source SHA matches spec
            if ds_id in ScientificReadinessEvaluator.CANONICAL_HISTORICAL_DATASET_SPECIFICATIONS:
                spec = ScientificReadinessEvaluator.CANONICAL_HISTORICAL_DATASET_SPECIFICATIONS[ds_id]
                expected_sha = spec.get("expected_sha256", "")
                if source_sha256 and expected_sha and source_sha256 != expected_sha:
                    provenance_status = "SOURCE_INTEGRITY_FAILED"
                    detected_errors.append(f"SHA-256 mismatch: actual={source_sha256}, expected={expected_sha}")
                else:
                    provenance_status = "TRUSTED_PROVENANCE_VERIFIED"
            else:
                provenance_status = "TRUSTED_PROVENANCE_VERIFIED"
        elif schema_status == "STRUCTURE_VALIDATED" and artifact_present:
            provenance_status = "STRUCTURE_VALIDATED"
        elif artifact_present:
            provenance_status = "ARTIFACT_PRESENT"
        else:
            provenance_status = "UNVERIFIED"

        # 5. Compute Deterministic Fingerprint
        dataset_fingerprint = cls.compute_dataset_fingerprint(
            dataset_id=ds_id,
            source_sha256=source_sha256,
            schema_version="CBE-DATASET-SCHEMA-V28",
            observation_start=obs_start,
            observation_end=obs_end,
            observation_count=obs_count,
        )

        return HistoricalDatasetRecord(
            dataset_id=ds_id,
            dataset_version="1.0.0",
            market=market,
            instrument=instrument,
            market_type=market_type,
            timeframe=timeframe,
            observation_start=obs_start,
            observation_end=obs_end,
            observation_count=obs_count,
            source_artifact_ids=[str(target_path.relative_to(REPO_ROOT)).replace("\\", "/")] if target_path and target_path.is_relative_to(REPO_ROOT) else ([str(target_path)] if target_path else []),
            source_artifact_sha256=source_sha256,
            source_manifest_id=prov_result.get("manifest_id"),
            source_manifest_verification_status="VERIFIED" if prov_result.get("is_verified") else "UNVERIFIED",
            provenance_status=provenance_status,
            schema_validation_status=schema_status,
            temporal_integrity_status=temporal_status,
            missing_observation_count=missing_count,
            duplicate_observation_count=duplicates,
            quarantine_status=quarantine_status,
            dataset_fingerprint=dataset_fingerprint,
            validation_timestamp=datetime.now(timezone.utc).isoformat(),
            file_path=str(target_path) if target_path else None,
            metrics={
                "detected_errors": detected_errors,
                "is_quarantined": is_quar,
                "prov_result": prov_result,
            },
        )

    _cached_inventory: Optional[List[HistoricalDatasetRecord]] = None

    @classmethod
    def get_dataset_inventory(cls, force_refresh: bool = False) -> List[HistoricalDatasetRecord]:
        """Produce the complete inventory of all canonical and local historical datasets."""
        if not force_refresh and cls._cached_inventory is not None:
            return list(cls._cached_inventory)

        records: List[HistoricalDatasetRecord] = []

        # 1. Pinned Canonical Datasets
        for ds_id, spec in ScientificReadinessEvaluator.CANONICAL_HISTORICAL_DATASET_SPECIFICATIONS.items():
            f_path = REPO_ROOT / spec["source_artifact"]
            rec = cls.validate_dataset(
                dataset_id=ds_id,
                file_path=str(f_path),
                timeframe=spec.get("window_cadence", "1h"),
            )
            records.append(rec)

        # 2. Quarantined October 2026 dataset
        quar_path = REPO_ROOT / "data" / "staging_intake" / "BTCUSDT-5m-2026-10-intake.parquet"
        if quar_path.exists():
            rec_quar = cls.validate_dataset(
                dataset_id="DS-BTC-5M-2026-10-INTAKE",
                file_path=str(quar_path),
                timeframe="5m",
            )
            records.append(rec_quar)

        cls._cached_inventory = records
        return list(records)

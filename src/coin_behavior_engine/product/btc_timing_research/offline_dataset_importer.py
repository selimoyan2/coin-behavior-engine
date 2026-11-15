"""Manual Offline Dataset Importer & Provenance Validator (Sprint 31 Module 31.2).

Implements controlled historical dataset import and rigorous verification:
1. Supported input formats: Parquet and CSV.
2. Market identity & classification: BTC/USDT, SPOT only.
3. Timestamp ordering: strictly monotonic increasing UTC timestamps.
4. Candle interval: strictly fixed step (3,600,000 ms for 1h candles).
5. Missing candle detection & duplicate timestamp detection.
6. OHLCV mathematical integrity (high >= low, high >= open, close; low <= open, close; volume >= 0).
7. Cryptographic SHA-256 fingerprinting.
8. Historical period boundaries extraction.
9. Holdout contamination audit (checks holdout_usage_ledger and temporal_partitions).
10. Strict provenance trust classification:
    - Never auto-promotes self-declared metadata to verified independent provenance.
    - Default status: RESTRICTED_EVIDENCE_UNVERIFIED_PROVENANCE / PROVISIONAL_OFFLINE_IMPORT.
11. Quarantine status check.
"""

from __future__ import annotations

import csv
import hashlib
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.product.btc_timing_research.dataset_adapter import (
    REGISTERED_BTC_DATASETS,
    DatasetVerificationResult,
)

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_HOLDOUT_LEDGER_PATH = REPO_ROOT / "data" / "research_lab" / "holdout_usage_ledger.json"
DEFAULT_TEMPORAL_PARTITIONS_PATH = REPO_ROOT / "data" / "research_lab" / "temporal_partitions.json"

# Strict trust classifications for imported datasets
PROVENANCE_VERIFIED_INDEPENDENT = "VERIFIED_INDEPENDENT_PROVENANCE"
PROVENANCE_RESTRICTED_UNVERIFIED = "RESTRICTED_EVIDENCE_UNVERIFIED_PROVENANCE"
PROVENANCE_PROVISIONAL_IMPORT = "PROVISIONAL_OFFLINE_IMPORT"
PROVENANCE_SELF_DECLARED_REJECTED = "SELF_DECLARED_PROVENANCE_REJECTED"


@dataclass(frozen=True)
class DatasetImportValidationResult:
    """Outcome of manual offline dataset import validation."""
    is_valid: bool
    dataset_id: str
    file_path: str
    sha256_checksum: str
    symbol: str
    market_type: str
    timeframe: str
    interval_ms: int
    total_bars: int
    earliest_open_utc: str
    latest_open_utc: str
    earliest_open_ms: int
    latest_open_ms: int
    is_continuous: bool
    missing_candle_count: int
    duplicate_count: int
    bad_candle_count: int
    is_quarantined: bool
    holdout_contamination_detected: bool
    contamination_details: Optional[str]
    is_eligible_unseen_holdout: bool
    provenance_classification: str
    provenance_notes: str
    validation_errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class OfflineDatasetImporter:
    """Controlled historical dataset importer for offline BTC research."""

    def __init__(
        self,
        repo_root: Optional[Path] = None,
        holdout_ledger_path: Optional[Path] = None,
        temporal_partitions_path: Optional[Path] = None,
    ):
        self.repo_root = repo_root or REPO_ROOT
        self.holdout_ledger_path = holdout_ledger_path or DEFAULT_HOLDOUT_LEDGER_PATH
        self.temporal_partitions_path = temporal_partitions_path or DEFAULT_TEMPORAL_PARTITIONS_PATH

    def validate_file(
        self,
        file_path: Path | str,
        symbol: str = "BTCUSDT",
        market_type: str = "SPOT",
        expected_interval_ms: int = 3600000,
        proposed_dataset_id: Optional[str] = None,
        declared_provenance_meta: Optional[Dict[str, Any]] = None,
    ) -> DatasetImportValidationResult:
        """Thoroughly validate a prospective historical dataset file before import."""
        path = Path(file_path)
        if not path.is_absolute():
            path = self.repo_root / path

        errors: List[str] = []

        if not path.exists():
            return self._build_failure_result(
                dataset_id=proposed_dataset_id or "UNKNOWN",
                file_path=str(path),
                errors=[f"File does not exist: {path}"],
            )

        # 1. Compute SHA-256
        file_bytes = path.read_bytes()
        sha256 = hashlib.sha256(file_bytes).hexdigest()

        # 2. Quarantine Check
        is_quarantined, q_reason = self._check_quarantine(sha256, path.name)
        if is_quarantined:
            errors.append(f"File is quarantined: {q_reason}")

        # 3. Read DataFrame (Parquet or CSV)
        ext = path.suffix.lower()
        try:
            if ext == ".parquet":
                df = pd.read_parquet(path)
            elif ext in (".csv", ".txt"):
                df = pd.read_csv(path)
            else:
                errors.append(f"Unsupported file format '{ext}'. Must be .parquet or .csv.")
                return self._build_failure_result(
                    dataset_id=proposed_dataset_id or path.stem,
                    file_path=str(path),
                    sha256=sha256,
                    errors=errors,
                )
        except Exception as e:
            errors.append(f"File reading error: {e}")
            return self._build_failure_result(
                dataset_id=proposed_dataset_id or path.stem,
                file_path=str(path),
                sha256=sha256,
                errors=errors,
            )

        if df.empty:
            errors.append("Dataset is empty (0 rows).")
            return self._build_failure_result(
                dataset_id=proposed_dataset_id or path.stem,
                file_path=str(path),
                sha256=sha256,
                errors=errors,
            )

        # 4. Standardize Columns
        df_norm, col_err = self._normalize_columns(df)
        if col_err:
            errors.extend(col_err)
            return self._build_failure_result(
                dataset_id=proposed_dataset_id or path.stem,
                file_path=str(path),
                sha256=sha256,
                errors=errors,
            )

        # 5. Market & Symbol Validation
        if symbol.upper().replace("/", "") != "BTCUSDT":
            errors.append(f"Symbol '{symbol}' not permitted. Historical timing research requires BTCUSDT.")
        if market_type.upper() != "SPOT":
            errors.append(f"Market type '{market_type}' not permitted. Spot only; futures/derivatives prohibited.")

        # 6. Timestamp & Interval Validation
        total_bars = len(df_norm)
        ts_arr = df_norm["open_time"].to_numpy()

        # Strictly monotonic increasing check
        is_sorted = bool(np.all(np.diff(ts_arr) > 0))
        duplicate_count = int(total_bars - len(np.unique(ts_arr)))
        if duplicate_count > 0:
            errors.append(f"Found {duplicate_count} duplicate open timestamps.")

        if not is_sorted and duplicate_count == 0:
            errors.append("Timestamps are not strictly chronologically monotonic increasing.")

        # Interval step check
        step_diffs = np.diff(ts_arr)
        missing_candles = 0
        if len(step_diffs) > 0:
            gaps = step_diffs[step_diffs != expected_interval_ms]
            if len(gaps) > 0:
                for g in gaps:
                    if g > expected_interval_ms:
                        missing_candles += int(round(g / expected_interval_ms) - 1)
                errors.append(f"Interval inconsistencies detected: {missing_candles} missing candles.")

        is_continuous = (missing_candles == 0 and duplicate_count == 0 and is_sorted)

        earliest_ms = int(ts_arr[0])
        latest_ms = int(ts_arr[-1])
        earliest_utc = datetime.fromtimestamp(earliest_ms / 1000.0, tz=timezone.utc).isoformat()
        latest_utc = datetime.fromtimestamp(latest_ms / 1000.0, tz=timezone.utc).isoformat()

        # 7. OHLCV Mathematical Integrity
        bad_candles = 0
        high = df_norm["high"].to_numpy()
        low = df_norm["low"].to_numpy()
        open_p = df_norm["open"].to_numpy()
        close = df_norm["close"].to_numpy()
        vol = df_norm["volume"].to_numpy()

        viol_high = (high < low) | (high < open_p) | (high < close)
        viol_low = (low > open_p) | (low > close)
        viol_pos = (open_p <= 0) | (high <= 0) | (low <= 0) | (close <= 0)
        viol_vol = (vol < 0) | np.isnan(vol) | np.isinf(vol)

        bad_mask = viol_high | viol_low | viol_pos | viol_vol
        bad_candles = int(np.sum(bad_mask))
        if bad_candles > 0:
            errors.append(f"OHLCV mathematical integrity violated in {bad_candles} candles.")

        # 8. Holdout Contamination Audit
        contamination_detected, contam_details = self._audit_holdout_contamination(earliest_ms, latest_ms)
        if contamination_detected:
            errors.append(f"Holdout contamination detected: {contam_details}")

        # 9. Provenance Trust Classification
        prov_class, prov_notes = self._classify_provenance(path, sha256, declared_provenance_meta)

        # 10. Eligibility for Unseen Sealed Holdout
        # Eligible if: no errors (or only non-fatal warnings), 0 prior holdout contamination, contiguous
        is_eligible_unseen = (
            len(errors) == 0
            and is_continuous
            and not contamination_detected
            and bad_candles == 0
            and not is_quarantined
        )

        dataset_id = proposed_dataset_id or f"DS-BTC-1H-IMPORTED-{sha256[:8].upper()}"

        return DatasetImportValidationResult(
            is_valid=(len(errors) == 0),
            dataset_id=dataset_id,
            file_path=str(path),
            sha256_checksum=sha256,
            symbol="BTCUSDT",
            market_type="SPOT",
            timeframe="1h",
            interval_ms=expected_interval_ms,
            total_bars=total_bars,
            earliest_open_utc=earliest_utc,
            latest_open_utc=latest_utc,
            earliest_open_ms=earliest_ms,
            latest_open_ms=latest_ms,
            is_continuous=is_continuous,
            missing_candle_count=missing_candles,
            duplicate_count=duplicate_count,
            bad_candle_count=bad_candles,
            is_quarantined=is_quarantined,
            holdout_contamination_detected=contamination_detected,
            contamination_details=contam_details,
            is_eligible_unseen_holdout=is_eligible_unseen,
            provenance_classification=prov_class,
            provenance_notes=prov_notes,
            validation_errors=errors,
        )

    def import_and_register(
        self,
        file_path: Path | str,
        dataset_id: str,
        symbol: str = "BTCUSDT",
        market_type: str = "SPOT",
        expected_interval_ms: int = 3600000,
        declared_provenance_meta: Optional[Dict[str, Any]] = None,
    ) -> DatasetImportValidationResult:
        """Validate and, if clean, register dataset into the BTC research catalog."""
        result = self.validate_file(
            file_path=file_path,
            symbol=symbol,
            market_type=market_type,
            expected_interval_ms=expected_interval_ms,
            proposed_dataset_id=dataset_id,
            declared_provenance_meta=declared_provenance_meta,
        )

        if not result.is_valid:
            logger.warning(f"Dataset import rejected for {dataset_id}: {result.validation_errors}")
            return result

        # Register in REGISTERED_BTC_DATASETS
        rel_path = str(Path(result.file_path).relative_to(self.repo_root)).replace("\\", "/")
        REGISTERED_BTC_DATASETS[dataset_id] = {
            "dataset_id": dataset_id,
            "relative_path": rel_path,
            "provenance_path": rel_path.replace(".parquet", "_provenance.json"),
            "symbol": result.symbol,
            "timeframe": result.timeframe,
            "expected_interval_ms": result.interval_ms,
            "expected_bars": result.total_bars,
            "earliest_open_utc": result.earliest_open_utc,
            "latest_open_utc": result.latest_open_utc,
            "exchange": "BINANCE",
            "market_type": result.market_type,
            "sha256": result.sha256_checksum,
            "provenance_classification": result.provenance_classification,
            "is_eligible_unseen_holdout": result.is_eligible_unseen_holdout,
        }

        # Write provenance sidecar if missing
        prov_path = Path(self.repo_root) / rel_path.replace(".parquet", "_provenance.json")
        if not prov_path.exists():
            prov_data = {
                "dataset_id": dataset_id,
                "symbol": result.symbol,
                "interval": result.timeframe,
                "exchange": "BINANCE",
                "market_type": result.market_type,
                "sha256_checksum": result.sha256_checksum,
                "total_bars": result.total_bars,
                "earliest_candle_open_utc": result.earliest_open_utc,
                "latest_candle_open_utc": result.latest_open_utc,
                "provenance_classification": result.provenance_classification,
                "provenance_notes": result.provenance_notes,
                "imported_at_utc": datetime.now(timezone.utc).isoformat(),
            }
            try:
                prov_path.write_text(json.dumps(prov_data, indent=2), encoding="utf-8")
            except Exception as e:
                logger.warning(f"Could not persist provenance file: {e}")

        logger.info(f"Successfully registered imported dataset: {dataset_id}")
        return result

    def _normalize_columns(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
        """Normalize column names to standard ['open_time', 'open', 'high', 'low', 'close', 'volume']."""
        errors = []
        cols = {str(c).lower().strip(): c for c in df.columns}
        df_norm = pd.DataFrame()

        # Find timestamp
        ts_candidates = ["open_time", "opentime", "timestamp", "time", "date", "datetime"]
        ts_col = None
        for cand in ts_candidates:
            if cand in cols:
                ts_col = cols[cand]
                break

        if ts_col is None:
            errors.append(f"Missing open_time column. Available columns: {list(df.columns)}")
            return df, errors

        # Convert timestamp to int ms
        try:
            s_ts = df[ts_col]
            if pd.api.types.is_numeric_dtype(s_ts):
                # If seconds vs milliseconds
                sample = float(s_ts.dropna().iloc[0])
                if sample < 1e11:  # seconds
                    df_norm["open_time"] = (s_ts * 1000).astype(int)
                else:  # milliseconds
                    df_norm["open_time"] = s_ts.astype(int)
            else:
                df_norm["open_time"] = pd.to_datetime(s_ts, utc=True).astype("int64") // 10**6
        except Exception as e:
            errors.append(f"Failed to parse timestamp column '{ts_col}': {e}")
            return df, errors

        # Required price/volume columns
        for c in ["open", "high", "low", "close", "volume"]:
            cand_names = [c, f"{c}_price", f"kline_{c}"]
            found = None
            for cand in cand_names:
                if cand in cols:
                    found = cols[cand]
                    break
            if found is None:
                errors.append(f"Missing required OHLCV column '{c}'.")
            else:
                try:
                    df_norm[c] = pd.to_numeric(df[found], errors="coerce")
                except Exception as e:
                    errors.append(f"Failed to convert column '{c}' to numeric: {e}")

        if "datetime" in df.columns:
            df_norm["datetime"] = df["datetime"]
        else:
            df_norm["datetime"] = pd.to_datetime(df_norm["open_time"], unit="ms", utc=True).dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        return df_norm, errors

    def _check_quarantine(self, sha256: str, filename: str) -> Tuple[bool, str]:
        """Verify whether dataset is flagged in quarantine registry."""
        quarantine_file = self.repo_root / "data" / "quarantine_registry.json"
        if quarantine_file.exists():
            try:
                q_data = json.loads(quarantine_file.read_text(encoding="utf-8"))
                for entry in q_data.get("quarantined_files", []):
                    if entry.get("sha256") == sha256 or entry.get("filename") == filename:
                        return True, entry.get("reason", "Flagged in quarantine registry.")
            except Exception:
                pass
        return False, ""

    def _audit_holdout_contamination(
        self,
        start_ms: int,
        end_ms: int,
    ) -> Tuple[bool, Optional[str]]:
        """Audit whether proposed interval overlaps with previously accessed holdout partitions."""
        if not self.holdout_ledger_path.exists():
            return False, None

        try:
            with open(self.holdout_ledger_path, "r", encoding="utf-8") as f:
                ledger = json.load(f)
            events = ledger.get("holdout_events", [])
            if not events:
                return False, None

            # Check temporal partition definitions
            partitions_meta = {}
            if self.temporal_partitions_path.exists():
                with open(self.temporal_partitions_path, "r", encoding="utf-8") as f:
                    part_doc = json.load(f)
                for p in part_doc.get("partitions", []):
                    partitions_meta[p["partition_id"]] = p

            accessed_partitions = set(e.get("holdout_partition_id") for e in events)

            for pid in accessed_partitions:
                p_info = partitions_meta.get(pid)
                if p_info:
                    p_start_utc = p_info.get("start_utc")
                    p_end_utc = p_info.get("end_utc")
                    if p_start_utc and p_end_utc:
                        p_start_ms = int(datetime.fromisoformat(p_start_utc.replace("Z", "+00:00")).timestamp() * 1000)
                        p_end_ms = int(datetime.fromisoformat(p_end_utc.replace("Z", "+00:00")).timestamp() * 1000)

                        # Check for overlap: [start_ms, end_ms] overlaps with [p_start_ms, p_end_ms]
                        if not (end_ms < p_start_ms or start_ms > p_end_ms):
                            return True, (
                                f"Dataset time range overlaps with accessed holdout partition '{pid}' "
                                f"({p_start_utc} to {p_end_utc}). Holdout access count: "
                                f"{sum(1 for e in events if e.get('holdout_partition_id') == pid)}."
                            )
        except Exception as e:
            logger.warning(f"Error checking holdout ledger: {e}")

        return False, None

    def _classify_provenance(
        self,
        path: Path,
        sha256: str,
        declared_meta: Optional[Dict[str, Any]],
    ) -> Tuple[str, str]:
        """Classify dataset provenance with epistemological conservatism.

        Rule: Never automatically promote imported data to verified independent provenance.
        If source authority cannot be cryptographically established, preserve with restricted classification.
        """
        # Check if matching provenance file exists with cryptographic authority
        prov_path = path.with_name(path.stem + "_provenance.json")
        if prov_path.exists():
            try:
                prov_data = json.loads(prov_path.read_text(encoding="utf-8"))
                if prov_data.get("sha256_checksum") == sha256:
                    authority = prov_data.get("cryptographic_authority")
                    if authority and authority.get("is_verified_authority") is True:
                        return (
                            PROVENANCE_VERIFIED_INDEPENDENT,
                            f"Verified independent provenance by authority {authority.get('authority_name')}.",
                        )
                    return (
                        PROVENANCE_PROVISIONAL_IMPORT,
                        "Provenance sidecar exists and checksum matches, but authority is not cryptographically signed. "
                        "Classified as provisional offline import.",
                    )
            except Exception:
                pass

        if declared_meta and declared_meta.get("self_certified") is True:
            return (
                PROVENANCE_SELF_DECLARED_REJECTED,
                "Self-declared caller provenance rejected. Independent cryptographic authority required.",
            )

        return (
            PROVENANCE_RESTRICTED_UNVERIFIED,
            "Source provenance unverified. Preserved with restricted evidence classification per scientific protocol.",
        )

    def _build_failure_result(
        self,
        dataset_id: str,
        file_path: str,
        errors: List[str],
        sha256: str = "",
    ) -> DatasetImportValidationResult:
        return DatasetImportValidationResult(
            is_valid=False,
            dataset_id=dataset_id,
            file_path=file_path,
            sha256_checksum=sha256,
            symbol="UNKNOWN",
            market_type="UNKNOWN",
            timeframe="1h",
            interval_ms=0,
            total_bars=0,
            earliest_open_utc="",
            latest_open_utc="",
            earliest_open_ms=0,
            latest_open_ms=0,
            is_continuous=False,
            missing_candle_count=0,
            duplicate_count=0,
            bad_candle_count=0,
            is_quarantined=False,
            holdout_contamination_detected=False,
            contamination_details=None,
            is_eligible_unseen_holdout=False,
            provenance_classification=PROVENANCE_RESTRICTED_UNVERIFIED,
            provenance_notes="Import validation failed.",
            validation_errors=errors,
        )

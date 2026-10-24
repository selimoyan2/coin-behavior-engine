"""Secure Offline Historical Data Import Engine for Coin Behavior Engine.

Validates and atomically imports operator-supplied historical market data
files (Parquet or CSV) into canonical monthly partitions without external
network access, runtime dependencies, or synthetic price fabrication.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import tempfile
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

import numpy as np
import pandas as pd

from coin_behavior_engine.product.dataset_manager import (
    INTERVAL_DURATIONS_MS,
    SUPPORTED_INTERVALS,
    DatasetManager,
)

logger = logging.getLogger("cbe.data_import")

REPO_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_DATA_DIR = REPO_ROOT / "data" / "binance_spot_multiyear"
DEFAULT_RECEIPT_DIR = REPO_ROOT / "research_outputs" / "import_receipts"


class ValidationError(Exception):
    """Raised when imported data fails structural or financial validation."""


class OverlapConflictError(ValidationError):
    """Raised when imported data conflicts with existing canonical records."""


class HistoricalDataImporter:
    """Validates and atomically ingests offline historical market data files."""

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        receipt_dir: Optional[Path] = None,
    ):
        self.base_dir = Path(base_dir) if base_dir else CANONICAL_DATA_DIR
        self.receipt_dir = Path(receipt_dir) if receipt_dir else DEFAULT_RECEIPT_DIR
        self.receipt_dir.mkdir(parents=True, exist_ok=True)

    def compute_sha256(self, file_path: Path) -> str:
        """Compute SHA256 hash of a file."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def validate_file(
        self,
        source_path: Path,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        allow_partial: bool = True,
    ) -> Dict[str, Any]:
        """Perform comprehensive offline validation of a candidate market data file."""
        source = Path(source_path)
        if not source.exists():
            raise ValidationError(f"Kaynak dosya mevcut değil: {source}")

        if not source.is_file():
            raise ValidationError(f"Kaynak bir dosya değil: {source}")

        size_b = source.stat().st_size
        if size_b == 0:
            raise ValidationError("Dosya boş (0 bayt).")
        if size_b > 1024 * 1024 * 1024:  # 1 GB safety limit
            raise ValidationError(f"Dosya boyutu güvenlik limitini aşıyor: {size_b} bayt")

        sha256 = self.compute_sha256(source)
        ext = source.suffix.lower()

        # 1. Parse file into DataFrame
        try:
            if ext == ".parquet":
                df = pd.read_parquet(source)
            elif ext in (".csv", ".txt"):
                df = pd.read_csv(source)
            else:
                raise ValidationError(f"Desteklenmeyen dosya uzantısı: {ext}. Parquet veya CSV gereklidir.")
        except Exception as e:
            raise ValidationError(f"Dosya ayrıştırma hatası ({ext}): {e}")

        if df.empty:
            raise ValidationError("Ayrıştırılan veri kümesi sıfır satır içeriyor.")

        # 2. Schema Normalization & Validation
        df_cols_lower = {str(c).lower(): c for c in df.columns}
        required_fields = ["open", "high", "low", "close", "volume"]
        missing_fields = [f for f in required_fields if f not in df_cols_lower]
        if missing_fields:
            raise ValidationError(f"Eksik zorunlu OHLCV sütunları: {missing_fields}")

        # Timestamp column resolution
        time_col = None
        for cand in ("open_time", "opentime", "timestamp", "datetime", "date", "time"):
            if cand in df_cols_lower:
                time_col = df_cols_lower[cand]
                break

        if time_col is None:
            raise ValidationError("Zaman damgası sütunu (open_time, timestamp veya datetime) bulunamadı.")

        # Extract normalized columns
        norm_df = pd.DataFrame()

        # Timestamp normalization
        raw_times = df[time_col]
        if pd.api.types.is_numeric_dtype(raw_times):
            # Numeric unix timestamp: verify whether in seconds or milliseconds
            sample_val = float(raw_times.iloc[0])
            if sample_val < 1e11:  # seconds (e.g. 1.7e9)
                norm_df["open_time"] = (raw_times * 1000).astype("int64")
            else:  # milliseconds (e.g. 1.7e12)
                norm_df["open_time"] = raw_times.astype("int64")
        else:
            # Datetime string parsing
            parsed_dt = pd.to_datetime(raw_times, utc=True)
            norm_df["open_time"] = (parsed_dt.astype("int64") // 10**6).astype("int64")

        # Numeric OHLCV normalization
        for field in ("open", "high", "low", "close", "volume"):
            actual_col = df_cols_lower[field]
            try:
                norm_df[field] = pd.to_numeric(df[actual_col], errors="coerce").astype("float64")
            except Exception as e:
                raise ValidationError(f"'{field}' sütunu sayısal değere dönüştürülemedi: {e}")

        # Optional auxiliary fields
        for aux in ("close_time", "quote_volume", "count", "taker_buy_volume", "taker_buy_quote_volume"):
            if aux in df_cols_lower:
                norm_df[aux] = pd.to_numeric(df[df_cols_lower[aux]], errors="coerce")
            else:
                if aux == "close_time":
                    duration = INTERVAL_DURATIONS_MS.get(interval, 300_000)
                    norm_df["close_time"] = norm_df["open_time"] + duration - 1
                elif aux == "count":
                    norm_df["count"] = 0
                else:
                    norm_df[aux] = 0.0

        # Construct datetime UTC column
        norm_df["datetime"] = pd.to_datetime(norm_df["open_time"], unit="ms", utc=True)

        # 3. Numeric Integrity & Finiteness
        if norm_df.isna().any().any():
            nan_cols = norm_df.columns[norm_df.isna().any()].tolist()
            raise ValidationError(f"Veri kümesinde eksik (NaN / Null) değerler tespit edildi: {nan_cols}")

        if not np.isfinite(norm_df[["open", "high", "low", "close", "volume"]].values).all():
            raise ValidationError("OHLCV verisinde sonsuz (Inf) değerler mevcut.")

        if (norm_df[["open", "high", "low", "close"]] <= 0).any().any():
            raise ValidationError("OHLC fiyatları kesinlikle sıfırdan büyük olmalıdır (> 0).")

        if (norm_df["volume"] < 0).any():
            raise ValidationError("İşlem hacmi negatif olamaz (volume >= 0).")

        # 4. OHLC Logical Consistency
        # High must be >= max(Open, Close) and Low must be <= min(Open, Close)
        invalid_high = norm_df["high"] < norm_df[["open", "close"]].max(axis=1) - 1e-6
        if invalid_high.any():
            bad_idx = np.where(invalid_high)[0][0]
            bad_row = norm_df.iloc[bad_idx]
            raise ValidationError(
                f"OHLC Mantık Hatası: High ({bad_row['high']}) < max(Open, Close) "
                f"at {bad_row['datetime']} (Index {bad_idx})"
            )

        invalid_low = norm_df["low"] > norm_df[["open", "close"]].min(axis=1) + 1e-6
        if invalid_low.any():
            bad_idx = np.where(invalid_low)[0][0]
            bad_row = norm_df.iloc[bad_idx]
            raise ValidationError(
                f"OHLC Mantık Hatası: Low ({bad_row['low']}) > min(Open, Close) "
                f"at {bad_row['datetime']} (Index {bad_idx})"
            )

        # 5. Chronological Ordering & Duplicates
        if not norm_df["open_time"].is_monotonic_increasing:
            # Check if sorted fixes it
            diffs = norm_df["open_time"].diff().iloc[1:]
            if (diffs < 0).any():
                raise ValidationError("Zaman damgaları kronolojik sırada değil (monoton artan olmalıdır).")

        dup_times = norm_df["open_time"].duplicated()
        if dup_times.any():
            dup_count = dup_times.sum()
            raise ValidationError(f"Tekrarlanan (duplicate) {dup_count} adet zaman damgası tespit edildi.")

        # 6. Target Partition & Month Verification
        first_dt = norm_df["datetime"].iloc[0]
        last_dt = norm_df["datetime"].iloc[-1]
        first_month = first_dt.strftime("%Y-%m")
        last_month = last_dt.strftime("%Y-%m")

        if first_month != last_month:
            # Files spanning multiple months must be partitioned or rejected
            raise ValidationError(
                f"Dosya birden fazla ayı kapsıyor ({first_month} ve {last_month}). "
                "İçe aktarma aylık partisyonlar bazında yapılmalıdır."
            )

        target_month = first_month
        expected_step = INTERVAL_DURATIONS_MS.get(interval, 300_000)

        # Days in month and expected row count
        days_in_month = pd.Period(target_month, freq="M").days_in_month
        expected_month_candles = int((days_in_month * 86400 * 1000) / expected_step)
        completeness_pct = round((len(norm_df) / max(1, expected_month_candles)) * 100, 2)
        is_partial_month = len(norm_df) < expected_month_candles

        # Check gap frequency
        step_diffs = norm_df["open_time"].diff().iloc[1:]
        gap_count = (step_diffs > expected_step).sum()

        # 7. Overlap and Conflict Detection against existing canonical partition
        existing_partition = self.base_dir / interval / f"{symbol}-{interval}-{target_month}.parquet"
        conflict_records = 0
        exact_duplicates = 0

        if existing_partition.exists():
            try:
                exist_df = pd.read_parquet(existing_partition)
                exist_times = set(exist_df["open_time"].values)
                overlap_mask = norm_df["open_time"].isin(exist_times)
                overlap_count = overlap_mask.sum()

                if overlap_count > 0:
                    # Check whether OHLCV matches or conflicts
                    merged = pd.merge(
                        norm_df[overlap_mask],
                        exist_df,
                        on="open_time",
                        suffixes=("_new", "_exist"),
                    )
                    price_diff = (
                        (merged["open_new"] - merged["open_exist"]).abs()
                        + (merged["high_new"] - merged["high_exist"]).abs()
                        + (merged["low_new"] - merged["low_exist"]).abs()
                        + (merged["close_new"] - merged["close_exist"]).abs()
                    )
                    conflicts = price_diff > 1e-4
                    conflict_records = int(conflicts.sum())
                    exact_duplicates = int((~conflicts).sum())

                    if conflict_records > 0:
                        raise OverlapConflictError(
                            f"Mevcut {existing_partition.name} partisyonu ile çelişen "
                            f"{conflict_records} mum tespit edildi. Değer uyuşmazlığı nedeniyle "
                            "içe aktarma reddedildi."
                        )
            except OverlapConflictError:
                raise
            except Exception as e:
                logger.warning("Mevcut partisyon çakışma analizi hatası: %s", e)

        return {
            "valid": True,
            "source_file": str(source.resolve()),
            "source_filename": source.name,
            "source_sha256": sha256,
            "source_size_bytes": size_b,
            "symbol": symbol,
            "interval": interval,
            "target_month": target_month,
            "records_count": len(norm_df),
            "expected_month_candles": expected_month_candles,
            "completeness_pct": completeness_pct,
            "is_partial_month": is_partial_month,
            "first_timestamp_utc": first_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "last_timestamp_utc": last_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "first_open_price": float(norm_df["open"].iloc[0]),
            "last_close_price": float(norm_df["close"].iloc[-1]),
            "gaps_count": int(gap_count),
            "existing_partition_exists": existing_partition.exists(),
            "exact_duplicates": exact_duplicates,
            "conflict_records": conflict_records,
            "normalized_df": norm_df,
        }

    def import_file(
        self,
        source_path: Path,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        allow_partial: bool = True,
    ) -> Dict[str, Any]:
        """Atomically validate, transform, and publish historical dataset partition."""
        import_id = f"IMP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
        start_time = time.time()

        # Step 1: Pre-import manifest revision
        dm = DatasetManager.get_instance(self.base_dir)
        manifest_before = dm.get_manifest()
        rev_before = manifest_before.get("manifest_version", "UNKNOWN")

        # Step 2: Full Validation
        val_result = self.validate_file(
            source_path=source_path,
            symbol=symbol,
            interval=interval,
            allow_partial=allow_partial,
        )

        norm_df = val_result["normalized_df"]
        target_month = val_result["target_month"]
        target_dir = self.base_dir / interval
        target_dir.mkdir(parents=True, exist_ok=True)
        canonical_target = target_dir / f"{symbol}-{interval}-{target_month}.parquet"

        # Step 3: Handle existing partition merging (if append/merge applicable)
        if canonical_target.exists():
            exist_df = pd.read_parquet(canonical_target)
            # Combine and deduplicate by open_time
            combined = pd.concat([exist_df, norm_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=["open_time"], keep="last")
            combined = combined.sort_values(by="open_time").reset_index(drop=True)
            final_df = combined
        else:
            final_df = norm_df.sort_values(by="open_time").reset_index(drop=True)

        # Step 4: Atomic Write via Staging File
        staging_file = target_dir / f"{canonical_target.stem}.tmp.{uuid.uuid4().hex[:8]}"
        try:
            final_df.to_parquet(staging_file, index=False, engine="pyarrow", compression="snappy")

            # Verify written staging file
            verify_df = pd.read_parquet(staging_file)
            if len(verify_df) != len(final_df):
                raise ValidationError("Staging dosyası satır sayısı doğrulaması başarısız.")

            # Step 5: Atomic Rename
            if os.name == "nt" and canonical_target.exists():
                # On Windows, replace requires explicit atomic replace
                os.replace(staging_file, canonical_target)
            else:
                staging_file.replace(canonical_target)

        except Exception as e:
            if staging_file.exists():
                try:
                    staging_file.unlink()
                except Exception:
                    pass
            raise ValidationError(f"Atomik yazma işlemi başarısız oldu: {e}")

        # Step 6: Invalidate Caches
        dm.invalidate_cache()
        manifest_after = dm.get_manifest(force_refresh=True)
        rev_after = manifest_after.get("manifest_version", "UNKNOWN")

        # Step 7: Generate Machine-Readable Receipt
        duration_sec = round(time.time() - start_time, 3)
        receipt = {
            "receipt_id": import_id,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "execution_duration_sec": duration_sec,
            "status": "ACCEPTED_AND_PUBLISHED",
            "source_filename": val_result["source_filename"],
            "source_sha256": val_result["source_sha256"],
            "source_size_bytes": val_result["source_size_bytes"],
            "symbol": symbol,
            "interval": interval,
            "target_partition": canonical_target.name,
            "target_month": target_month,
            "records_accepted": len(norm_df),
            "final_partition_records": len(final_df),
            "first_timestamp_utc": val_result["first_timestamp_utc"],
            "last_timestamp_utc": val_result["last_timestamp_utc"],
            "dataset_revision_before": rev_before,
            "dataset_revision_after": rev_after,
            "governance_classification": "OFFLINE_AUDITED_IMPORT",
            "fail_closed_mode": "STRICTLY_OFFLINE",
        }

        receipt_file = self.receipt_dir / f"{import_id}_{val_result['target_month']}_{interval}.json"
        with open(receipt_file, "w", encoding="utf-8") as f:
            json.dump(receipt, f, indent=2)

        try:
            rel_path = str(receipt_file.relative_to(REPO_ROOT)).replace("\\", "/")
        except Exception:
            rel_path = str(receipt_file).replace("\\", "/")
        receipt["receipt_file"] = rel_path
        logger.info("Successfully imported %s into %s (Receipt: %s)", source_path, canonical_target, import_id)
        return receipt

    def preview_file(
        self,
        source_path: Union[str, Path],
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        allow_partial: bool = True,
    ) -> Dict[str, Any]:
        """Dry-run preview candidate file without publishing to canonical partitions."""
        val = self.validate_file(source_path, symbol, interval, allow_partial=allow_partial)
        dm = DatasetManager.get_instance(self.base_dir)
        cur_manifest = dm.get_manifest()

        target_month = val["target_month"]
        canonical_target = self.base_dir / interval / f"{symbol}-{interval}-{target_month}.parquet"
        target_exists = canonical_target.exists()

        preview_candles = []
        try:
            if str(source_path).endswith(".parquet"):
                sample_df = pd.read_parquet(source_path).head(5)
            else:
                sample_df = pd.read_csv(source_path).head(5)
            for _, r in sample_df.iterrows():
                preview_candles.append({
                    "open_time": int(r["open_time"]),
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "volume": float(r["volume"]),
                })
        except Exception:
            pass

        preview = {
            "valid": val["valid"],
            "status": "PREVIEW_READY",
            "source_path": str(source_path),
            "symbol": symbol,
            "interval": interval,
            "target_month": target_month,
            "target_partition_path": str(canonical_target),
            "partition_already_exists": target_exists,
            "records_count": val["records_count"],
            "preview_candles": preview_candles,
            "is_partial_month": val.get("is_partial_month", False),
            "completeness_pct": val.get("completeness_pct", 100.0),
            "date_range": {
                "first_timestamp_utc": val["first_timestamp_utc"],
                "last_timestamp_utc": val["last_timestamp_utc"],
            },
            "price_envelope": {
                "first_open": val["first_open_price"],
                "last_close": val["last_close_price"],
            },
            "completeness": {
                "is_partial": val["is_partial_month"],
                "expected_month_candles": val["expected_month_candles"],
                "completeness_pct": val["completeness_pct"],
                "detected_gaps": val["gaps_count"],
            },
            "source_sha256": val["source_sha256"],
            "current_manifest_version": cur_manifest.get("manifest_version", "UNKNOWN"),
            "publication_impact": "WOULD_CREATE_NEW_PARTITION" if not target_exists else "WOULD_APPEND_PARTITION",
        }
        return preview

    def verify_partition(
        self,
        symbol: str = "BTCUSDT",
        interval: str = "5m",
        month: str = "2026-09",
    ) -> Dict[str, Any]:
        """Verify an existing canonical partition against all ingestion validation criteria."""
        partition_file = self.base_dir / interval / f"{symbol}-{interval}-{month}.parquet"
        if not partition_file.exists():
            raise FileNotFoundError(f"Kanonik partisyon bulunamadı: {partition_file}")

        val = self.validate_file(partition_file, symbol, interval, allow_partial=True)
        return {
            "valid": val["valid"],
            "status": "VERIFIED",
            "partition_file": str(partition_file),
            "symbol": symbol,
            "interval": interval,
            "month": month,
            "records_count": val["records_count"],
            "missing_candles": max(0, val.get("expected_month_candles", val["records_count"]) - val["records_count"]),
            "first_timestamp_utc": val["first_timestamp_utc"],
            "last_timestamp_utc": val["last_timestamp_utc"],
            "sha256": val["source_sha256"],
            "completeness_pct": val["completeness_pct"],
            "gaps_count": val["gaps_count"],
        }

    def list_receipts(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List past import receipts sorted by newest first."""
        receipts = []
        if not self.receipt_dir.exists():
            return receipts

        for f in sorted(self.receipt_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:limit]:
            try:
                with open(f, "r", encoding="utf-8") as rf:
                    data = json.load(rf)
                    receipts.append(data)
            except Exception as e:
                logger.warning("Could not read receipt %s: %s", f, e)
        return receipts

    def get_receipt(self, receipt_id: str) -> Optional[Dict[str, Any]]:
        """Find and parse a specific receipt by import_id."""
        if not self.receipt_dir.exists():
            return None
        for f in self.receipt_dir.glob(f"{receipt_id}*.json"):
            try:
                with open(f, "r", encoding="utf-8") as rf:
                    return json.load(rf)
            except Exception:
                pass
        return None


def main():
    """CLI Entrypoint for offline data import."""
    parser = argparse.ArgumentParser(
        description="Coin Behavior Engine — Offline Historical Market Data Importer"
    )
    parser.add_argument("--source", "-s", default=None, help="Path to candidate data file (Parquet or CSV)")
    parser.add_argument("--symbol", default="BTCUSDT", help="Target market symbol (default: BTCUSDT)")
    parser.add_argument("--interval", "-i", default="5m", choices=SUPPORTED_INTERVALS, help="Interval (default: 5m)")
    parser.add_argument(
        "--mode",
        "-m",
        choices=("validate", "preview", "import", "verify"),
        default="validate",
        help="Execution mode (default: validate)",
    )
    parser.add_argument("--month", default=None, help="Target month for verify mode (e.g. 2026-09)")
    parser.add_argument("--list-imports", action="store_true", help="List recent import receipts")
    parser.add_argument("--inspect-receipt", default=None, help="Inspect specific receipt by ID")
    parser.add_argument("--allow-partial", action="store_true", default=True, help="Allow partial month datasets")
    parser.add_argument("--base-dir", default=None, help="Custom dataset target directory")
    parser.add_argument("--receipt-dir", default=None, help="Custom receipt output directory")

    args = parser.parse_args()

    importer = HistoricalDataImporter(
        base_dir=Path(args.base_dir) if args.base_dir else None,
        receipt_dir=Path(args.receipt_dir) if args.receipt_dir else None,
    )

    if args.list_imports:
        receipts = importer.list_receipts()
        print(f"=== CBE IMPORT RECEIPTS AUDIT ({len(receipts)} found) ===")
        for r in receipts:
            print(f"  [{r.get('import_timestamp_utc')}] {r.get('receipt_id')} | {r.get('target_partition')} | {r.get('records_accepted')} rows | {r.get('status')}")
        sys.exit(0)

    if args.inspect_receipt:
        rec = importer.get_receipt(args.inspect_receipt)
        if rec:
            print(json.dumps(rec, indent=2))
            sys.exit(0)
        else:
            print(f"Receipt ID '{args.inspect_receipt}' not found.", file=sys.stderr)
            sys.exit(1)

    if args.mode == "verify":
        target_m = args.month or "2026-09"
        try:
            res = importer.verify_partition(symbol=args.symbol, interval=args.interval, month=target_m)
            print(f"\n[PARTITION VERIFICATION PASSED: {target_m}]")
            print(json.dumps(res, indent=2))
            sys.exit(0)
        except Exception as e:
            print(f"\n[PARTITION VERIFICATION FAILED: {target_m}] {e}", file=sys.stderr)
            sys.exit(1)

    if not args.source:
        print("Error: --source is required for validate, preview, and import modes.", file=sys.stderr)
        sys.exit(1)

    print(f"=== CBE OFFLINE DATA IMPORTER (Mode: {args.mode.upper()}) ===")
    print(f"Source:   {args.source}")
    print(f"Symbol:   {args.symbol}")
    print(f"Interval: {args.interval}")

    try:
        if args.mode == "validate":
            res = importer.validate_file(
                source_path=Path(args.source),
                symbol=args.symbol,
                interval=args.interval,
                allow_partial=args.allow_partial,
            )
            print("\n[VALIDATION PASSED]")
            print(f"  Target Month:     {res['target_month']}")
            print(f"  Records Count:    {res['records_count']:,}")
            print(f"  Range:            {res['first_timestamp_utc']} -> {res['last_timestamp_utc']}")
            print(f"  First Open Price: ${res['first_open_price']:,.2f}")
            print(f"  Last Close Price: ${res['last_close_price']:,.2f}")
            print(f"  Gaps Detected:    {res['gaps_count']}")
            print(f"  Source SHA256:    {res['source_sha256']}")
            sys.exit(0)

        elif args.mode == "preview":
            preview = importer.preview_file(
                source_path=Path(args.source),
                symbol=args.symbol,
                interval=args.interval,
                allow_partial=args.allow_partial,
            )
            print("\n[IMPORT PREVIEW]")
            print(json.dumps(preview, indent=2))
            sys.exit(0)

        elif args.mode == "import":
            receipt = importer.import_file(
                source_path=Path(args.source),
                symbol=args.symbol,
                interval=args.interval,
                allow_partial=args.allow_partial,
            )
            print("\n[IMPORT SUCCESSFUL]")
            print(f"  Receipt ID:       {receipt['receipt_id']}")
            print(f"  Partition:        {receipt['target_partition']}")
            print(f"  Records Accepted: {receipt['records_accepted']:,}")
            print(f"  Total In File:    {receipt['final_partition_records']:,}")
            print(f"  Revision After:   {receipt['dataset_revision_after']}")
            print(f"  Receipt File:     {receipt['receipt_file']}")
            sys.exit(0)

    except ValidationError as e:
        print(f"\n[VALIDATION FAILED] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()

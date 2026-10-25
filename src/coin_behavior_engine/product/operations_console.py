"""
CBE — Secure Data Operations Console Engine
Provides authenticated operator workflows for historical data file intake, validation preview,
controlled partition publication, and deterministic multi-timeframe derivation with an immutable audit trail.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import hmac
import logging
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Dict, List, Optional, Tuple
import uuid

logger = logging.getLogger("cbe.operations_console")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_INTAKE_DIR = REPO_ROOT / "data" / "staging_intake"
AUDIT_LOG_FILE = REPO_ROOT / "research_outputs" / "operations_audit_log.jsonl"

SAFE_FILENAME_REGEX = re.compile(r"^[A-Za-z0-9_\-\.]+$")
ALLOWED_EXTENSIONS = (".parquet", ".csv", ".gz")

# Revoked tokens blacklist - any attempt to use these will be explicitly rejected as security violations
REVOKED_OPERATOR_TOKENS = {
    "cbe-staging-operator-key-2026",
    "default-insecure-key",
    "admin",
    "operator",
    "secret",
}


@dataclass
class ImportPreviewTicket:
    preview_id: str
    filename: str
    source_sha256: str
    symbol: str
    interval: str
    month: str
    record_count: int
    first_timestamp_utc: Optional[str]
    last_timestamp_utc: Optional[str]
    duplicates_count: int
    missing_count: int
    invalid_ohlc_count: int
    conflicting_count: int
    validation_verdict: str  # VALIDATED, REJECTED
    provenance_verdict: str  # VERIFIED_IMPORTABLE, PARTIAL_VERIFIED_IMPORTABLE, QUARANTINED, INVALID_SOURCE
    quarantine_reason: Optional[str]
    completeness_pct: float
    covered_dates: str
    created_at_utc: str
    expires_at_utc: str
    expected_partitions: List[str]
    expected_derived_intervals: List[str]


class OperationsConsoleEngine:
    """Manages intake, validation preview, authorized publication, and audit logging."""

    _lock = threading.Lock()
    _active_previews: Dict[str, ImportPreviewTicket] = {}
    _job_history: List[Dict[str, Any]] = []
    _failed_attempts: Dict[str, List[float]] = {}
    MAX_FAILED_ATTEMPTS = 5
    LOCKOUT_WINDOW_SECONDS = 60.0

    @classmethod
    def get_intake_dir(cls) -> Path:
        """Resolve and ensure authorized intake directory exists."""
        intake = DEFAULT_INTAKE_DIR
        intake.mkdir(parents=True, exist_ok=True)
        return intake

    @classmethod
    def is_authorized_operator(cls, token: Optional[str], client_ip: str = "127.0.0.1") -> Tuple[bool, str]:
        """
        Validate operator token against environment configuration.
        Enforces token revocation, brute-force lockout, and fail-closed security.
        """
        env = os.environ.get("CBE_ENV", "staging").lower()
        if env == "production":
            return False, "MUTATIONS_PERMANENTLY_BLOCKED_IN_PRODUCTION"

        now = time.time()
        with cls._lock:
            attempts = cls._failed_attempts.get(client_ip, [])
            attempts = [t for t in attempts if (now - t) < cls.LOCKOUT_WINDOW_SECONDS]
            cls._failed_attempts[client_ip] = attempts
            if len(attempts) >= cls.MAX_FAILED_ATTEMPTS:
                return False, "OPERATOR_AUTH_RATE_LIMITED_LOCKOUT"

        if not token or not token.strip():
            with cls._lock:
                cls._failed_attempts.setdefault(client_ip, []).append(now)
            return False, "INVALID_OR_MISSING_OPERATOR_TOKEN"

        clean_token = token.strip()
        if clean_token in REVOKED_OPERATOR_TOKENS:
            with cls._lock:
                cls._failed_attempts.setdefault(client_ip, []).append(now)
            return False, "OPERATOR_TOKEN_REVOKED"

        expected_token = os.environ.get("CBE_OPERATOR_TOKEN") or os.environ.get("OPERATOR_TOKEN")
        if not expected_token or not expected_token.strip():
            return False, "OPERATOR_AUTH_NOT_CONFIGURED"

        if not hmac.compare_digest(clean_token.encode("utf-8"), expected_token.strip().encode("utf-8")):
            with cls._lock:
                cls._failed_attempts.setdefault(client_ip, []).append(now)
            return False, "INVALID_OR_MISSING_OPERATOR_TOKEN"

        return True, "AUTHORIZED_STAGING_OPERATOR"

    @classmethod
    def list_intake_candidates(cls) -> List[Dict[str, Any]]:
        """List verified intake candidate files available in staging intake."""
        intake_dir = cls.get_intake_dir()
        candidates = []
        for f in sorted(intake_dir.iterdir()):
            if f.is_file() and any(f.name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
                try:
                    stat = f.stat()
                    candidates.append({
                        "filename": f.name,
                        "size_bytes": stat.st_size,
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                        "modified_utc": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                        "extension": f.suffix,
                    })
                except Exception as e:
                    logger.warning("Error reading intake file %s: %s", f.name, e)
        return candidates

    @classmethod
    def create_import_preview(
        cls,
        filename: str,
        declared_symbol: str = "BTCUSDT",
        declared_interval: str = "5m",
    ) -> Dict[str, Any]:
        """
        Inspect and validate an intake file without publishing data.
        Generates an immutable preview ticket with SHA256 checksum.
        """
        # Strict path safety check
        if not SAFE_FILENAME_REGEX.match(filename) or ".." in filename or "/" in filename or "\\" in filename:
            return {"status": "error", "error": "SECURITY_VIOLATION", "message": "Geçersiz dosya adı veya dizin aşımı girişimi."}

        target_file = cls.get_intake_dir() / filename
        if not target_file.exists() or not target_file.is_file():
            return {"status": "error", "error": "FILE_NOT_FOUND", "message": f"İçe aktarma dosya kuyruğunda '{filename}' bulunamadı."}

        # Checksum calculation
        hasher = hashlib.sha256()
        with open(target_file, "rb") as bf:
            while chunk := bf.read(65536):
                hasher.update(chunk)
        file_sha256 = hasher.hexdigest()

        # Parse and validate with HistoricalDataImporter logic
        import pandas as pd
        try:
            if filename.endswith(".parquet"):
                df = pd.read_parquet(target_file)
            else:
                df = pd.read_csv(target_file)
        except Exception as e:
            return {"status": "error", "error": "CORRUPTED_FILE", "message": f"Dosya okuma hatası: {e}"}

        record_count = len(df)
        if record_count == 0:
            return {"status": "error", "error": "EMPTY_DATASET", "message": "Dosya boş, mum kaydı bulunamadı."}

        # Check required columns
        req_cols = {"open_time", "open", "high", "low", "close", "volume"}
        if not req_cols.issubset(df.columns):
            return {
                "status": "error",
                "error": "SCHEMA_MISMATCH",
                "message": f"Eksik kolonlar: {req_cols - set(df.columns)}",
            }

        # Monotonicity & duplicates
        dups = int(df.duplicated(subset=["open_time"]).sum())
        sorted_times = df["open_time"].sort_values().values
        first_ms = int(sorted_times[0])
        last_ms = int(sorted_times[-1])
        first_utc = datetime.fromtimestamp(first_ms // 1000, tz=timezone.utc).isoformat()
        last_utc = datetime.fromtimestamp(last_ms // 1000, tz=timezone.utc).isoformat()

        # Target month resolution and expected candles
        target_month = first_utc[:7]
        # Calculate expected candles based on interval and month length
        try:
            year, mon = int(target_month[:4]), int(target_month[5:7])
            import calendar
            days_in_m = calendar.monthrange(year, mon)[1]
        except Exception:
            days_in_m = 31
        
        bars_per_day = 288 if declared_interval == "5m" else (24 if declared_interval == "1h" else 1440)
        expected_full_month = days_in_m * bars_per_day
        completeness_pct = min(100.0, round((record_count / expected_full_month) * 100.0, 2))
        covered_dates = f"{first_utc[:10]} - {last_utc[:10]}"

        # OHLC Geometric constraints
        invalid_ohlc = int((
            (df["high"] < df["low"]) |
            (df["high"] < df["open"]) |
            (df["high"] < df["close"]) |
            (df["low"] > df["open"]) |
            (df["low"] > df["close"]) |
            (df["open"] <= 0) |
            (df["close"] <= 0)
        ).sum())

        structural_valid = (dups == 0 and invalid_ohlc == 0)
        verdict = "VALIDATED" if structural_valid else "REJECTED"

        # Synthetic fixture & provenance checks (Phase C)
        vol_nunique = int(df["volume"].nunique()) if "volume" in df.columns else 0
        open_diffs = df["open"].diff().dropna()
        open_diffs_nunique = int(open_diffs.nunique()) if len(open_diffs) > 0 else 0
        
        is_synthetic = False
        quarantine_reason = None
        if vol_nunique <= 1 and record_count >= 50:
            is_synthetic = True
            quarantine_reason = f"SYNTHETIC_FIXTURE_NO_AUTHENTIC_PROVENANCE: Sabit hacim ({float(df['volume'].iloc[0]) if len(df) > 0 else 0}) tespit edildi. Orijinal borsa soykütüğü doğrulanamadı."
        elif open_diffs_nunique <= 2 and record_count >= 50:
            is_synthetic = True
            quarantine_reason = "SYNTHETIC_FIXTURE_NO_AUTHENTIC_PROVENANCE: Yapay doğrusal adım fiyatları tespit edildi."

        if is_synthetic:
            provenance_verdict = "QUARANTINED"
        elif not structural_valid:
            provenance_verdict = "INVALID_SOURCE"
            quarantine_reason = f"Bütünlük hatası: {dups} mükerrer zaman damgası, {invalid_ohlc} geçersiz OHLC kaydı."
        elif completeness_pct < 95.0:
            provenance_verdict = "PARTIAL_VERIFIED_IMPORTABLE"
        else:
            provenance_verdict = "VERIFIED_IMPORTABLE"

        preview_id = f"prev_{uuid.uuid4().hex[:12]}"
        now_utc = datetime.now(timezone.utc)
        exp_utc = datetime.fromtimestamp(now_utc.timestamp() + 900, tz=timezone.utc)

        expected_partitions = [f"{declared_symbol}-{declared_interval}-{target_month}.parquet"]
        expected_derived = ["15m", "1h", "4h", "1d"] if declared_interval == "5m" else []

        ticket = ImportPreviewTicket(
            preview_id=preview_id,
            filename=filename,
            source_sha256=file_sha256,
            symbol=declared_symbol.upper(),
            interval=declared_interval.lower(),
            month=target_month,
            record_count=record_count,
            first_timestamp_utc=first_utc,
            last_timestamp_utc=last_utc,
            duplicates_count=dups,
            missing_count=max(0, expected_full_month - record_count) if completeness_pct < 100.0 else 0,
            invalid_ohlc_count=invalid_ohlc,
            conflicting_count=0,
            validation_verdict=verdict,
            provenance_verdict=provenance_verdict,
            quarantine_reason=quarantine_reason,
            completeness_pct=completeness_pct,
            covered_dates=covered_dates,
            created_at_utc=now_utc.isoformat(),
            expires_at_utc=exp_utc.isoformat(),
            expected_partitions=expected_partitions,
            expected_derived_intervals=expected_derived,
        )

        with cls._lock:
            cls._active_previews[preview_id] = ticket

        cls._record_audit_log(
            operation_id=preview_id,
            action="IMPORT_PREVIEW",
            actor="operator",
            source_hash=file_sha256,
            verdict=provenance_verdict,
            details={
                "filename": filename,
                "records": record_count,
                "month": target_month,
                "provenance_verdict": provenance_verdict,
                "quarantine_reason": quarantine_reason,
            },
        )

        safe_to_publish = (verdict == "VALIDATED" and provenance_verdict in ("VERIFIED_IMPORTABLE", "PARTIAL_VERIFIED_IMPORTABLE"))

        return {
            "status": "success",
            "preview_id": preview_id,
            "preview": asdict(ticket),
            "safe_to_publish": safe_to_publish,
            "provenance_verdict": provenance_verdict,
            "quarantine_reason": quarantine_reason,
            "message": (
                "Önizleme başarıyla oluşturuldu. Yayın için doğrulama anahtarı gereklidir."
                if safe_to_publish
                else f"Dosya yayınlanamaz ({provenance_verdict}): {quarantine_reason or 'Bütünlük denetiminden geçemedi.'}"
            ),
        }

    @classmethod
    def publish_import(
        cls,
        preview_id: str,
        operator_token: Optional[str],
        confirmed: bool = False,
    ) -> Dict[str, Any]:
        """
        Publish an import ticket to the canonical historical archive with strict authorization.
        """
        # Auth check
        authorized, reason = cls.is_authorized_operator(operator_token)
        if not authorized:
            cls._record_audit_log(
                operation_id=preview_id,
                action="IMPORT_PUBLISH",
                actor="unauthorized_actor",
                source_hash="UNKNOWN",
                verdict="REJECTED_UNAUTHORIZED",
                details={"reason": reason},
            )
            return {"status": "error", "error": "UNAUTHORIZED", "message": f"Yetkilendirme başarısız: {reason}"}

        if not confirmed:
            return {"status": "error", "error": "CONFIRMATION_REQUIRED", "message": "İçe aktarımı kesinleştirmek için onay ('confirmed: true') gereklidir."}

        ticket: Optional[ImportPreviewTicket] = None
        with cls._lock:
            ticket = cls._active_previews.get(preview_id)

        if not ticket:
            return {"status": "error", "error": "TICKET_NOT_FOUND_OR_EXPIRED", "message": "Geçerli bir önizleme bileti bulunamadı veya süresi doldu."}

        if ticket.validation_verdict != "VALIDATED":
            return {"status": "error", "error": "INTEGRITY_FAILURE", "message": "Geçersiz kılınmış veri partisyonu yayınlanamaz."}

        if ticket.provenance_verdict == "QUARANTINED" or ticket.provenance_verdict not in ("VERIFIED_IMPORTABLE", "PARTIAL_VERIFIED_IMPORTABLE"):
            cls._record_audit_log(
                operation_id=preview_id,
                action="IMPORT_PUBLISH",
                actor="authenticated_operator",
                source_hash=ticket.source_sha256,
                verdict="REJECTED_QUARANTINED",
                details={"reason": ticket.quarantine_reason or "Karantinaya alınmış kaynak yayınlanamaz."},
            )
            return {
                "status": "error",
                "error": "QUARANTINED_SOURCE_CANNOT_BE_PUBLISHED",
                "message": f"Karantinaya alınmış aday dosya yayınlanamaz ({ticket.provenance_verdict}): {ticket.quarantine_reason or 'Yapay kurgu veya doğrulanmamış kaynak'}",
            }

        target_file = cls.get_intake_dir() / ticket.filename
        if not target_file.exists():
            return {"status": "error", "error": "SOURCE_REMOVED", "message": "Kaynak dosya içe aktarma dizininden silinmiş."}

        from coin_behavior_engine.data_import import HistoricalDataImporter
        from coin_behavior_engine.product.dataset_manager import DatasetManager

        dm = DatasetManager.get_instance()
        manifest_before = dm.get_manifest().get("manifest_version", "UNKNOWN")

        importer = HistoricalDataImporter()
        receipt = importer.import_file(
            file_path=target_file,
            symbol=ticket.symbol,
            interval=ticket.interval,
            month=ticket.month,
            dry_run=False,
            auto_derive=(ticket.interval == "5m"),
        )

        manifest_after = dm.get_manifest().get("manifest_version", "UNKNOWN")

        # Cleanup ticket from active cache
        with cls._lock:
            cls._active_previews.pop(preview_id, None)

        cls._record_audit_log(
            operation_id=preview_id,
            action="IMPORT_PUBLISH",
            actor="authenticated_operator",
            source_hash=ticket.source_sha256,
            verdict=receipt.get("status", "PUBLISHED"),
            revision_before=manifest_before,
            revision_after=manifest_after,
            details=receipt,
        )

        return {
            "status": "success",
            "operation_id": preview_id,
            "receipt": receipt,
            "dataset_revision_before": manifest_before,
            "dataset_revision_after": manifest_after,
            "message": f"Partisyon '{ticket.filename}' başarıyla yayınlandı ve manifest güncellendi.",
        }

    @classmethod
    def preview_derivation(
        cls,
        month: str,
        symbol: str = "BTCUSDT",
        target_intervals: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Preview multi-timeframe derivation before executing publication."""
        from coin_behavior_engine.data_import import HistoricalDataImporter
        importer = HistoricalDataImporter()
        targets = target_intervals or ["15m", "1h", "4h", "1d"]
        res = importer.derive_timeframes(
            source_interval="5m",
            target_intervals=targets,
            month=month,
            symbol=symbol,
            dry_run=True,
        )
        return res

    @classmethod
    def publish_derivation(
        cls,
        month: str,
        operator_token: Optional[str],
        symbol: str = "BTCUSDT",
        target_intervals: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Execute and publish derived multi-timeframe partitions."""
        authorized, reason = cls.is_authorized_operator(operator_token)
        if not authorized:
            return {"status": "error", "error": "UNAUTHORIZED", "message": f"Yetkilendirme başarısız: {reason}"}

        from coin_behavior_engine.data_import import HistoricalDataImporter
        from coin_behavior_engine.product.dataset_manager import DatasetManager

        dm = DatasetManager.get_instance()
        manifest_before = dm.get_manifest().get("manifest_version", "UNKNOWN")

        importer = HistoricalDataImporter()
        targets = target_intervals or ["15m", "1h", "4h", "1d"]
        res = importer.derive_timeframes(
            source_interval="5m",
            target_intervals=targets,
            month=month,
            symbol=symbol,
            dry_run=False,
            overwrite=True,
        )

        manifest_after = dm.get_manifest().get("manifest_version", "UNKNOWN")

        op_id = f"drv_{uuid.uuid4().hex[:12]}"
        cls._record_audit_log(
            operation_id=op_id,
            action="DERIVE_PUBLISH",
            actor="authenticated_operator",
            source_hash="CANONICAL_5M",
            verdict=res.get("status", "SUCCESS"),
            revision_before=manifest_before,
            revision_after=manifest_after,
            details={"month": month, "symbol": symbol, "targets": targets},
        )

        return {
            "status": "success",
            "operation_id": op_id,
            "derivation_result": res,
            "dataset_revision_before": manifest_before,
            "dataset_revision_after": manifest_after,
        }

    @classmethod
    def get_operations_status(cls) -> Dict[str, Any]:
        """Compile complete operational console overview."""
        from coin_behavior_engine.product.dataset_manager import DatasetManager
        dm = DatasetManager.get_instance()
        manifest = dm.get_manifest()

        intake_candidates = cls.list_intake_candidates()
        recent_audit = cls.get_audit_trail(limit=10)

        return {
            "status": "success",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "environment": os.environ.get("CBE_ENV", "staging"),
            "dataset_revision": manifest.get("manifest_version", "UNKNOWN"),
            "manifest_hash": manifest.get("manifest_hash", "UNKNOWN"),
            "available_symbols": ["BTCUSDT"],
            "supported_symbols_schema": ["BTCUSDT", "ETHUSDT", "SOLUSDT"],
            "supported_intervals": ["5m", "15m", "1h", "4h", "1d"],
            "total_partitions": manifest.get("total_partitions", 0),
            "total_size_mb": manifest.get("total_size_mb", 0.0),
            "earliest_month": manifest.get("earliest_month"),
            "latest_month": manifest.get("latest_month"),
            "latest_candle_utc": manifest.get("latest_candle_utc"),
            "intake_candidates_count": len(intake_candidates),
            "intake_candidates": intake_candidates,
            "active_previews_count": len(cls._active_previews),
            "recent_audit_trail": recent_audit,
            "governance_contract": {
                "technical_decision": "TECHNICAL_NO_GO",
                "governance_authorization": "NOT_GRANTED",
                "live_trading": "PERMANENTLY_PROHIBITED",
                "data_policy": "OFFLINE_AUTHORIZED_ONLY",
            }
        }

    @classmethod
    def get_audit_trail(cls, limit: int = 50) -> List[Dict[str, Any]]:
        """Read recent audit records from immutable JSONL ledger."""
        if not AUDIT_LOG_FILE.exists():
            return []
        records = []
        try:
            with open(AUDIT_LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            records.append(json.loads(line))
                        except Exception:
                            pass
        except Exception as e:
            logger.warning("Error reading audit log: %s", e)
        return records[-limit:]

    @classmethod
    def _record_audit_log(
        cls,
        operation_id: str,
        action: str,
        actor: str,
        source_hash: str,
        verdict: str,
        revision_before: Optional[str] = None,
        revision_after: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Append an immutable audit entry to operations_audit_log.jsonl."""
        entry = {
            "operation_id": operation_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "actor": actor,
            "action": action,
            "source_hash": source_hash,
            "verdict": verdict,
            "revision_before": revision_before,
            "revision_after": revision_after,
            "details": details or {},
        }
        try:
            AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Failed to write operations audit log: %s", e)

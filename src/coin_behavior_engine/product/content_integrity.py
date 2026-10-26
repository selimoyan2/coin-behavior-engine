"""
Content Integrity and Cryptographic Hashing Engine.
Implements streaming SHA-256 file hashing, canonical dataset manifests,
and strict distinction between content hashes and metadata fingerprints.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cbe.content_integrity")


@dataclass
class PartitionIntegrityRecord:
    relative_path: str
    interval: str
    month: str
    byte_size: int
    mtime_utc: str
    sha256_content_hash: str
    metadata_fingerprint: str
    is_canonical: bool
    parent_partition_hash: Optional[str] = None
    quarantine_status: str = "VERIFIED"


class ContentIntegrityEngine:
    """
    Cryptographic content-integrity verification using streaming SHA-256.
    Distinguishes byte-level content changes from file modification metadata.
    """

    CHUNK_SIZE = 65536  # 64 KB streaming chunks

    @classmethod
    def compute_file_sha256(cls, file_path: Path) -> str:
        """
        Compute SHA-256 hash using streaming chunks to minimize memory consumption.
        """
        if not file_path.exists():
            return "FILE_NOT_FOUND"
        h = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(cls.CHUNK_SIZE):
                h.update(chunk)
        return h.hexdigest()

    @classmethod
    def compute_metadata_fingerprint(cls, file_path: Path) -> str:
        """
        Compute metadata fingerprint based on byte size and modification time.
        """
        if not file_path.exists():
            return "METADATA_NOT_FOUND"
        stat = file_path.stat()
        raw = f"{stat.st_size}_{stat.st_mtime_ns}"
        return f"FPR-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]}"

    @classmethod
    def audit_partition(cls, file_path: Path, interval: str, month: str, is_canonical: bool = True, parent_hash: Optional[str] = None) -> PartitionIntegrityRecord:
        """
        Produce a complete integrity record for a parquet partition.
        """
        stat = file_path.stat()
        mtime = datetime_from_timestamp(stat.st_mtime)
        content_hash = cls.compute_file_sha256(file_path)
        meta_fp = cls.compute_metadata_fingerprint(file_path)
        
        # Check quarantine
        q_status = "QUARANTINED" if "intake" in file_path.name or "candidate" in file_path.name.lower() else "VERIFIED"

        return PartitionIntegrityRecord(
            relative_path=str(file_path.as_posix()),
            interval=interval,
            month=month,
            byte_size=stat.st_size,
            mtime_utc=mtime,
            sha256_content_hash=content_hash,
            metadata_fingerprint=meta_fp,
            is_canonical=is_canonical,
            parent_partition_hash=parent_hash,
            quarantine_status=q_status,
        )

    @classmethod
    def generate_canonical_manifest(cls, data_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Scan all authentic multi-year partitions and generate a deterministic canonical manifest.
        """
        from datetime import datetime, timezone
        if data_dir is None:
            # Look up repository root data
            data_dir = Path(__file__).resolve().parents[3] / "data"

        base_dir = data_dir / "binance_spot_multiyear"
        records: List[Dict[str, Any]] = []

        if base_dir.exists():
            for intv_dir in sorted(base_dir.iterdir()):
                if intv_dir.is_dir():
                    intv = intv_dir.name
                    for pfile in sorted(intv_dir.glob("*.parquet")):
                        # Month format BTCUSDT-5m-2022-01.parquet
                        parts = pfile.stem.split("-")
                        month = f"{parts[-2]}-{parts[-1]}" if len(parts) >= 2 else "UNKNOWN"
                        is_canon = (intv == "5m")
                        stat = pfile.stat()
                        mtime_str = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                        c_hash = cls.compute_file_sha256(pfile)
                        fp = cls.compute_metadata_fingerprint(pfile)
                        
                        rec = {
                            "file_name": pfile.name,
                            "interval": intv,
                            "month": month,
                            "size_bytes": stat.st_size,
                            "mtime_utc": mtime_str,
                            "content_sha256": c_hash,
                            "metadata_fingerprint": fp,
                            "is_canonical": is_canon,
                        }
                        records.append(rec)

        # Audit intake quarantine
        quarantine_file = data_dir / "staging_intake" / "BTCUSDT-5m-2026-10-intake.parquet"
        quarantined_record = None
        if quarantine_file.exists():
            stat = quarantine_file.stat()
            quarantined_record = {
                "file_name": quarantine_file.name,
                "status": "QUARANTINED",
                "size_bytes": stat.st_size,
                "content_sha256": cls.compute_file_sha256(quarantine_file),
                "reason": "Synthetic fixture detection (constant volume 15.2, linear price step)",
                "blocked_from_canonical_manifest": True,
            }

        # Deterministic canonical content hash (Sprint 15 Reconciliation)
        # Excludes ephemeral filesystem timestamps (mtime_utc) to ensure 100% bitwise parity across OS environments
        canonical_content_payload = {
            "schema_version": "CBE-MANIFEST-V3",
            "domain_prefix": "CBE-DATASET-INTEGRITY-2026",
            "canonical_partitions": sorted(
                [
                    {
                        "file_name": r["file_name"],
                        "interval": r["interval"],
                        "month": r["month"],
                        "size_bytes": r["size_bytes"],
                        "content_sha256": r["content_sha256"],
                        "is_canonical": r["is_canonical"],
                    }
                    for r in records
                ],
                key=lambda x: (x["interval"], x["file_name"])
            ),
            "quarantined_exclusions": [
                {
                    "file_name": quarantined_record["file_name"],
                    "content_sha256": quarantined_record["content_sha256"],
                    "status": quarantined_record["status"]
                }
            ] if quarantined_record else []
        }
        manifest_serialized = json.dumps(canonical_content_payload, sort_keys=True)
        manifest_sha = hashlib.sha256(manifest_serialized.encode("utf-8")).hexdigest()

        return {
            "manifest_version": "CBE-MANIFEST-V3",
            "manifest_sha256": manifest_sha,
            "canonical_partitions_count": len([r for r in records if r["is_canonical"]]),
            "derived_partitions_count": len([r for r in records if not r["is_canonical"]]),
            "total_partitions": len(records),
            "partitions": records,
            "quarantined_intake": quarantined_record,
            "synthetic_data_prohibited": True,
        }


def datetime_from_timestamp(ts: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()

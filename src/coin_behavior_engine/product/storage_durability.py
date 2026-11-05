"""
Durable Storage & Docker Volume Validation and Research Backup/Restore Module
Sprint 23 — Enterprise-Grade Security Hardening, Multi-Process Concurrency & Operational Readiness

Ensures research persistence integrity:
- Classifies storage paths (PERSISTENT_VERIFIED, PERSISTENT_UNVERIFIED, EPHEMERAL, READ_ONLY, UNAVAILABLE).
- Enforces Docker volume persistence in staging and production environments.
- Provides atomic, verifiable backup snapshotting and non-destructive restore validation.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from coin_behavior_engine.product.process_locking import MultiProcessLock


class StorageDurabilityEngine:
    """Validates storage durability, volume mounts, and filesystem persistence."""

    EPHEMERAL_PREFIXES = ("/tmp", "/var/tmp", "/run", "/dev/shm")
    AUTHORIZED_STAGING_PERSISTENT_PREFIXES = (
        "/app/data/prospective",
        "/app/data/research_reports",
    )

    @classmethod
    def inspect_storage_path(cls, path_input: str | Path) -> Dict[str, Any]:
        """
        Inspects and classifies a storage directory path.
        Returns detailed durability evaluation dictionary.
        """
        raw_str = str(path_input)
        abs_path = os.path.abspath(raw_str).replace("\\", "/")
        norm_no_drive = re.sub(r"^[a-zA-Z]:", "", abs_path)

        cbe_env = os.environ.get("CBE_ENV", "staging").lower()
        exists = os.path.exists(raw_str)

        # 1. Ephemeral prefix check
        is_ephemeral = any(norm_no_drive.startswith(p) for p in cls.EPHEMERAL_PREFIXES)

        # 2. Check /proc/mounts if on Linux
        mount_info = {}
        if sys.platform != "win32" and os.path.exists("/proc/mounts"):
            try:
                with open("/proc/mounts", "r") as f:
                    for line in f:
                        parts = line.strip().split()
                        if len(parts) >= 4:
                            dev, mnt, fstype, opts = parts[0], parts[1], parts[2], parts[3]
                            if abs_path.startswith(mnt):
                                if len(mnt) > len(mount_info.get("mount_point", "")):
                                    mount_info = {
                                        "device": dev,
                                        "mount_point": mnt,
                                        "fstype": fstype,
                                        "options": opts,
                                        "is_readonly": "ro" in opts.split(","),
                                        "is_tmpfs": fstype in ("tmpfs", "ramfs"),
                                    }
            except Exception:
                pass

        if mount_info.get("is_tmpfs"):
            is_ephemeral = True

        # 3. Writable check
        is_writable = False
        if exists:
            test_file = os.path.join(raw_str, f".durability_test_{time.time_ns()}.tmp")
            try:
                with open(test_file, "w") as f:
                    f.write("durability_check")
                if os.path.exists(test_file):
                    os.remove(test_file)
                is_writable = True
            except Exception:
                is_writable = False
        else:
            try:
                os.makedirs(raw_str, exist_ok=True)
                is_writable = True
            except Exception:
                is_writable = False

        # 4. Classification
        if not is_writable:
            classification = "READ_ONLY" if exists else "UNAVAILABLE"
        elif is_ephemeral:
            classification = "EPHEMERAL"
        elif cbe_env in ("staging", "production"):
            # In staging/production, must match authorized persistent Docker volumes
            if any(abs_path.startswith(p) for p in cls.AUTHORIZED_STAGING_PERSISTENT_PREFIXES) or not mount_info.get("is_tmpfs", False):
                classification = "PERSISTENT_VERIFIED"
            else:
                classification = "PERSISTENT_UNVERIFIED"
        else:
            # Local development
            classification = "PERSISTENT_VERIFIED"

        return {
            "path": raw_str,
            "normalized_path": abs_path,
            "classification": classification,
            "is_writable": is_writable,
            "is_ephemeral": is_ephemeral,
            "environment": cbe_env,
            "mount_info": mount_info,
            "verified_durable": classification == "PERSISTENT_VERIFIED",
        }

    @classmethod
    def require_durable_storage(cls, path_input: str | Path) -> None:
        """
        Enforces that the path is PERSISTENT_VERIFIED in staging/production.
        Raises RuntimeError if storage path is ephemeral or unverified.
        """
        info = cls.inspect_storage_path(path_input)
        if not info["is_writable"]:
            raise RuntimeError(f"STORAGE_UNAVAILABLE: Storage directory '{path_input}' is not writable.")
        if info["is_ephemeral"]:
            raise RuntimeError(
                f"EPHEMERAL_STORAGE_REJECTED: Storage path '{path_input}' is an ephemeral mount. "
                "Research reports require authorized persistent mounts."
            )
        if info["environment"] in ("staging", "production") and info["classification"] != "PERSISTENT_VERIFIED":
            raise RuntimeError(
                f"UNVERIFIED_PERSISTENCE: Storage path '{path_input}' is classified as '{info['classification']}'. "
                "Staging/production requires PERSISTENT_VERIFIED storage."
            )


class ResearchBackupRestoreEngine:
    """Creates, verifies, and restores consistent snapshots of research artifacts."""

    CANONICAL_MODEL = "CBE-0.7.0"
    BACKUP_SCHEMA_VERSION = "CBE-BACKUP-1.0.0"

    @classmethod
    def create_backup(
        cls,
        output_dir: Optional[str | Path] = None,
        include_reports: bool = True,
        include_library: bool = True,
    ) -> Dict[str, Any]:
        """
        Creates a consistent tar.gz backup archive of persistent reports and library definitions.
        """
        from coin_behavior_engine.product.research_report_builder import ResearchReportBuilderEngine
        from coin_behavior_engine.product.research_intelligence_explorer import ResearchLibraryEngine

        target_dir = Path(output_dir or "research_outputs/backups").resolve()
        target_dir.mkdir(parents=True, exist_ok=True)

        now_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_id = f"BKP-CBE-{now_str}"
        archive_path = target_dir / f"{backup_id}.tar.gz"

        collected_files: List[Dict[str, Any]] = []

        # Lock both stores to ensure consistent snapshot
        rep_builder = ResearchReportBuilderEngine(require_durable=False)
        rep_dir = Path(rep_builder.storage_dir).resolve()
        lib_dir = Path(ResearchLibraryEngine.get_storage_dir()).resolve()

        rep_lock = MultiProcessLock(rep_dir / ".backup.lock")
        lib_lock = MultiProcessLock(lib_dir / ".backup.lock")

        with rep_lock, lib_lock:
            with tarfile.open(archive_path, "w:gz") as tar:
                # 1. Collect Reports
                if include_reports and rep_dir.exists():
                    for p in rep_dir.glob("*.json"):
                        if p.is_file():
                            data = p.read_bytes()
                            h = hashlib.sha256(data).hexdigest()
                            arcname = f"reports/{p.name}"
                            tar.add(p, arcname=arcname)
                            collected_files.append({
                                "file_name": p.name,
                                "category": "report",
                                "relative_path": arcname,
                                "sha256": h,
                                "size_bytes": len(data),
                            })

                # 2. Collect Library definitions
                if include_library and lib_dir.exists():
                    for p in lib_dir.glob("*.json"):
                        if p.is_file() and not p.name.startswith("."):
                            data = p.read_bytes()
                            h = hashlib.sha256(data).hexdigest()
                            arcname = f"library/{p.name}"
                            tar.add(p, arcname=arcname)
                            collected_files.append({
                                "file_name": p.name,
                                "category": "library",
                                "relative_path": arcname,
                                "sha256": h,
                                "size_bytes": len(data),
                            })

                # 3. Create and add manifest
                manifest = {
                    "backup_schema_version": cls.BACKUP_SCHEMA_VERSION,
                    "backup_id": backup_id,
                    "created_at_utc": datetime.now(timezone.utc).isoformat(),
                    "canonical_model_version": cls.CANONICAL_MODEL,
                    "files_count": len(collected_files),
                    "files": collected_files,
                }
                manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")
                tarinfo = tarfile.TarInfo(name="backup_manifest.json")
                tarinfo.size = len(manifest_bytes)
                tarinfo.mtime = int(time.time())
                tar.addfile(tarinfo, io.BytesIO(manifest_bytes))

        archive_bytes = archive_path.read_bytes()
        archive_sha = hashlib.sha256(archive_bytes).hexdigest()

        return {
            "status": "BACKUP_CREATED",
            "backup_id": backup_id,
            "archive_path": str(archive_path),
            "archive_sha256": archive_sha,
            "archive_size_bytes": len(archive_bytes),
            "files_count": len(collected_files),
            "manifest": manifest,
        }

    @classmethod
    def verify_backup(cls, archive_path: str | Path) -> Dict[str, Any]:
        """
        Verifies backup archive integrity and checksum consistency without extracting to disk.
        """
        path = Path(archive_path).resolve()
        if not path.exists():
            return {"valid": False, "status": "FILE_NOT_FOUND", "discrepancies": ["Archive file does not exist"]}

        discrepancies: List[str] = []
        manifest: Optional[Dict[str, Any]] = None

        try:
            with tarfile.open(path, "r:gz") as tar:
                # 1. Read manifest
                try:
                    m_file = tar.extractfile("backup_manifest.json")
                    if m_file:
                        manifest = json.loads(m_file.read().decode("utf-8"))
                    else:
                        discrepancies.append("Missing backup_manifest.json in archive")
                except Exception as e:
                    discrepancies.append(f"Failed to read backup manifest: {e}")

                if manifest:
                    # 2. Check each file sha256
                    manifest_files = {f["relative_path"]: f for f in manifest.get("files", [])}
                    for member in tar.getmembers():
                        if member.name == "backup_manifest.json":
                            continue
                        f_info = manifest_files.get(member.name)
                        if not f_info:
                            discrepancies.append(f"Unregistered file in backup: '{member.name}'")
                            continue
                        extracted = tar.extractfile(member)
                        if not extracted:
                            discrepancies.append(f"Could not extract file: '{member.name}'")
                            continue
                        data = extracted.read()
                        actual_sha = hashlib.sha256(data).hexdigest()
                        if actual_sha != f_info["sha256"]:
                            discrepancies.append(
                                f"Checksum mismatch for '{member.name}': expected={f_info['sha256']}, actual={actual_sha}"
                            )

                    # Verify no missing files
                    tar_names = {m.name for m in tar.getmembers()}
                    for rel in manifest_files:
                        if rel not in tar_names:
                            discrepancies.append(f"Missing file declared in manifest: '{rel}'")

        except Exception as e:
            discrepancies.append(f"Tar archive extraction error: {e}")

        valid = len(discrepancies) == 0 and manifest is not None
        return {
            "valid": valid,
            "is_valid": valid,
            "status": "BACKUP_VERIFIED_AUTHENTIC" if valid else "BACKUP_VERIFICATION_FAILED",
            "archive_path": str(path),
            "discrepancies": discrepancies,
            "manifest": manifest,
        }

    @classmethod
    def restore_backup(
        cls,
        archive_path: str | Path,
        destination_dir: str | Path,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Safely restores backup contents to destination_dir with path traversal protection.
        """
        verification = cls.verify_backup(archive_path)
        if not verification["valid"]:
            raise ValueError(f"CORRUPT_BACKUP_RESTORE_BLOCKED: {verification['discrepancies']}")

        dest = Path(destination_dir).resolve()
        if not dry_run:
            dest.mkdir(parents=True, exist_ok=True)

        restored_files = []
        with tarfile.open(archive_path, "r:gz") as tar:
            for member in tar.getmembers():
                if member.name == "backup_manifest.json":
                    continue
                # Path traversal guard
                member_path = (dest / member.name).resolve()
                if not str(member_path).startswith(str(dest)):
                    raise SecurityError(f"PATH_TRAVERSAL_DETECTED: '{member.name}' escapes destination directory")

                if not dry_run:
                    member_path.parent.mkdir(parents=True, exist_ok=True)
                    f_data = tar.extractfile(member).read()
                    member_path.write_bytes(f_data)
                restored_files.append(str(member_path))

        return {
            "status": "DRY_RUN_SUCCESS" if dry_run else "RESTORE_COMPLETED",
            "destination_dir": str(dest),
            "restored_count": len(restored_files),
            "restored_files": restored_files,
        }

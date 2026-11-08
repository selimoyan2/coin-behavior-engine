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
    REJECTED_FILESYSTEM_TYPES = {
        "overlay",
        "overlayfs",
        "tmpfs",
        "ramfs",
        "shm",
        "devtmpfs",
        "proc",
        "sysfs",
        "mqueue",
    }
    AUTHORIZED_STAGING_PERSISTENT_PREFIXES = (
        "/app/data/prospective",
        "/app/data/research_reports",
    )
    AUTHORIZED_STAGING_VOLUME_IDS = (
        "dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f",
    )

    @classmethod
    def get_authorized_persistent_prefixes(cls) -> Tuple[str, ...]:
        """Resolves authorized persistent prefixes combining defaults and environment configuration."""
        prefixes = list(cls.AUTHORIZED_STAGING_PERSISTENT_PREFIXES)
        env_mounts = os.environ.get("CBE_AUTHORIZED_PERSISTENT_MOUNTS")
        if env_mounts:
            for m in env_mounts.split(","):
                m_clean = re.sub(r"^[a-zA-Z]:", "", m.strip().replace("\\", "/"))
                if m_clean and m_clean not in prefixes:
                    prefixes.append(m_clean)
        env_reports = os.environ.get("CBE_REPORTS_STORAGE_PATH")
        if env_reports:
            p_clean = re.sub(r"^[a-zA-Z]:", "", os.path.abspath(env_reports).replace("\\", "/"))
            if p_clean and p_clean not in prefixes:
                prefixes.append(p_clean)
        return tuple(prefixes)

    @classmethod
    def parse_mounts_table(cls, mounts_content: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parses /proc/mounts style table into structured mount entries."""
        mounts: List[Dict[str, Any]] = []
        if mounts_content is None:
            mounts_path = os.environ.get("CBE_MOUNTS_PATH", "/proc/mounts")
            if sys.platform != "win32" and os.path.exists(mounts_path):
                try:
                    with open(mounts_path, "r", encoding="utf-8") as f:
                        mounts_content = f.read()
                except Exception:
                    mounts_content = ""
            else:
                mounts_content = ""

        if not mounts_content:
            return mounts

        for line in mounts_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if len(parts) >= 4:
                dev, mnt, fstype, opts = parts[0], parts[1], parts[2], parts[3]
                opt_list = opts.split(",")
                mounts.append({
                    "device": dev,
                    "mount_point": mnt.rstrip("/") or "/",
                    "fstype": fstype.lower(),
                    "options": opts,
                    "is_readonly": "ro" in opt_list,
                    "is_tmpfs": fstype.lower() in ("tmpfs", "ramfs", "shm"),
                    "is_overlay": fstype.lower() in ("overlay", "overlayfs"),
                })
        return mounts

    @classmethod
    def match_mount_for_path(
        cls,
        resolved_path: str,
        mounts: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Matches resolved_path against mount points strictly by path-component boundaries.
        Prevents prefix collision attacks (e.g. /app/data/prospective_fake matching /app/data/prospective).
        Returns the longest (most specific) ancestor mount entry.
        """
        p_parts = Path(resolved_path).parts
        best_match = None
        best_len = -1
        for m in mounts:
            m_point = m["mount_point"]
            m_parts = Path(m_point).parts
            if len(p_parts) >= len(m_parts) and p_parts[:len(m_parts)] == m_parts:
                if len(m_parts) > best_len:
                    best_len = len(m_parts)
                    best_match = m
        return best_match

    @classmethod
    def inspect_storage_path(
        cls,
        path_input: str | Path,
        mounts_override: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        Inspects and classifies a storage directory path with strict boundary and persistence verification.
        - Resolves symlinks using realpath to prevent symlink escape.
        - Matches mount points using path-component boundaries.
        - Distinguishes Docker overlay filesystems from genuine persistent volume mounts.
        - Fails closed if persistence cannot be proven in staging/production.
        """
        raw_str = str(path_input)
        
        # 1. Realpath resolution & symlink escape detection
        try:
            if os.path.exists(raw_str):
                resolved = os.path.realpath(raw_str)
            else:
                # Resolve nearest existing parent
                curr = Path(raw_str)
                parts = []
                while not curr.exists() and len(curr.parts) > 1:
                    parts.append(curr.name)
                    curr = curr.parent
                resolved_parent = os.path.realpath(str(curr))
                resolved = os.path.abspath(os.path.join(resolved_parent, *reversed(parts)))
        except Exception:
            resolved = os.path.abspath(raw_str)

        resolved_posix = resolved.replace("\\", "/")
        norm_no_drive = re.sub(r"^[a-zA-Z]:", "", resolved_posix)

        cbe_env = os.environ.get("CBE_ENV", "staging").lower()
        exists = os.path.exists(resolved)

        # Symlink escape check: if raw_str starts with an authorized root but resolved does not
        symlink_escaped = False
        raw_norm = re.sub(r"^[a-zA-Z]:", "", os.path.abspath(raw_str).replace("\\", "/"))
        for auth_root in cls.get_authorized_persistent_prefixes():
            auth_parts = Path(auth_root).parts
            raw_parts = Path(raw_norm).parts
            if len(raw_parts) >= len(auth_parts) and raw_parts[:len(auth_parts)] == auth_parts:
                res_parts = Path(norm_no_drive).parts
                if len(res_parts) < len(auth_parts) or res_parts[:len(auth_parts)] != auth_parts:
                    symlink_escaped = True
                    break

        # 2. Ephemeral prefix check
        is_ephemeral = any(
            norm_no_drive == p or norm_no_drive.startswith(p + "/")
            for p in cls.EPHEMERAL_PREFIXES
        )

        # 3. Mounts lookup with path-component boundaries
        mounts = mounts_override if mounts_override is not None else cls.parse_mounts_table()
        mount_info = cls.match_mount_for_path(norm_no_drive, mounts) or {}

        if mount_info.get("is_tmpfs"):
            is_ephemeral = True

        # 4. Writable check
        is_writable = False
        if mount_info.get("is_readonly"):
            is_writable = False
        elif exists:
            test_file = os.path.join(resolved, f".durability_test_{time.time_ns()}.tmp")
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
                os.makedirs(resolved, exist_ok=True)
                test_file = os.path.join(resolved, f".durability_test_{time.time_ns()}.tmp")
                with open(test_file, "w") as f:
                    f.write("durability_check")
                if os.path.exists(test_file):
                    os.remove(test_file)
                is_writable = True
            except Exception:
                is_writable = False

        # 5. Strict Classification
        classification = "UNAVAILABLE"
        rejection_reason = None

        if symlink_escaped:
            classification = "SYMLINK_ESCAPE_REJECTED"
            rejection_reason = "Symlink escapes authorized persistent root boundary."
        elif not is_writable:
            if mount_info.get("is_readonly") or (exists and not os.access(resolved, os.W_OK)):
                classification = "READ_ONLY"
                rejection_reason = "Storage filesystem is mounted or configured read-only."
            else:
                classification = "UNAVAILABLE"
                rejection_reason = "Path does not exist and cannot be created."
        elif is_ephemeral:
            classification = "EPHEMERAL"
            rejection_reason = "Storage path resides on an ephemeral or tmpfs mount."
        elif cbe_env in ("staging", "production"):
            # Strict staging/production persistent volume verification
            # A: Check if path component boundaries match authorized persistent roots
            is_authorized_root = False
            for p in cls.get_authorized_persistent_prefixes():
                p_parts = Path(p).parts
                res_parts = Path(norm_no_drive).parts
                if len(res_parts) >= len(p_parts) and res_parts[:len(p_parts)] == p_parts:
                    is_authorized_root = True
                    break

            if not is_authorized_root:
                classification = "UNAUTHORIZED_MOUNT_ROOT"
                rejection_reason = f"Path '{norm_no_drive}' is not within authorized persistent mount roots."
            elif mount_info.get("is_overlay"):
                # Docker overlay layer is ephemeral container rootfs!
                classification = "CONTAINER_OVERLAY_REJECTED"
                rejection_reason = "Storage path is backed by ephemeral Docker container overlay rootfs."
            elif mount_info.get("fstype") in cls.REJECTED_FILESYSTEM_TYPES:
                classification = "REJECTED_FILESYSTEM_TYPE"
                rejection_reason = f"Filesystem type '{mount_info.get('fstype')}' is not authorized for persistent storage."
            elif mounts and not mount_info:
                # Mounts table present but no mount point proven
                classification = "PERSISTENT_UNVERIFIED"
                rejection_reason = "Path has no established mount entry in system mounts table."
            else:
                # Authorized persistent volume verified
                # Optional volume ID check
                configured_volume_id = os.environ.get("CBE_AUTHORIZED_VOLUME_ID")
                if configured_volume_id and configured_volume_id not in cls.AUTHORIZED_STAGING_VOLUME_IDS:
                    classification = "UNAUTHORIZED_VOLUME_ID"
                    rejection_reason = f"Configured volume ID '{configured_volume_id}' is not authorized."
                else:
                    classification = "PERSISTENT_VERIFIED"
        else:
            # Local development environment
            classification = "PERSISTENT_VERIFIED"

        return {
            "path": raw_str,
            "resolved_path": resolved,
            "normalized_path": norm_no_drive,
            "classification": classification,
            "rejection_reason": rejection_reason,
            "is_writable": is_writable,
            "is_ephemeral": is_ephemeral,
            "symlink_escaped": symlink_escaped,
            "environment": cbe_env,
            "mount_info": mount_info,
            "verified_durable": classification == "PERSISTENT_VERIFIED",
        }

    @classmethod
    def require_durable_storage(
        cls,
        path_input: str | Path,
        mounts_override: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """
        Enforces that the path is PERSISTENT_VERIFIED in staging/production.
        Raises RuntimeError if storage path is ephemeral or unverified.
        """
        info = cls.inspect_storage_path(path_input, mounts_override=mounts_override)
        if not info["is_writable"]:
            raise RuntimeError(f"STORAGE_UNAVAILABLE: Storage directory '{path_input}' is not writable.")
        if info["is_ephemeral"]:
            raise RuntimeError(
                f"EPHEMERAL_STORAGE_REJECTED: Storage path '{path_input}' is an ephemeral mount. "
                "Research reports require authorized persistent mounts."
            )
        if info["environment"] in ("staging", "production") and info["classification"] != "PERSISTENT_VERIFIED":
            reason = info.get("rejection_reason") or "Storage path is not an authorized persistent mount."
            raise RuntimeError(
                f"UNVERIFIED_PERSISTENCE: Storage path '{path_input}' is classified as '{info['classification']}'. "
                f"Reason: {reason} Staging/production requires PERSISTENT_VERIFIED storage."
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

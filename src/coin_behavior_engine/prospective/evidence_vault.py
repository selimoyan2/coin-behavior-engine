"""
Sprint 11.23.4: Hardened Content-Addressed Immutable Evidence Vault
Provides atomic, multi-writer thread-safe, content-addressed storage for prospective
releases, schedules, consensus, and market observations with append-only journaling,
crash recovery, corruption quarantine, path traversal protection, and partial write handling.
"""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple
import uuid

VAULT_SUBDIRS = [
    "events",
    "schedules",
    "consensus",
    "releases",
    "observations",
    "manifests",
    "quarantine",
]

SCHEMA_VERSION = "1.1.0"


class VaultSecurityError(Exception):
    """Raised when path traversal or symlink tampering is detected in the evidence vault."""
    pass


class VaultCorruptionError(Exception):
    """Raised when byte corruption is detected in existing vault objects."""
    pass


class ImmutableEvidenceVault:
    """
    Local content-addressed evidence vault with crash durability and concurrency guards.
    Features:
      - Multi-writer thread-safe atomic writes via unique temporary staging.
      - Append-only journaling with fsync persistence.
      - Automatic quarantine of corrupt objects.
      - Resilient journal parser ignoring incomplete/truncated crash lines.
      - Deterministic vault audit and self-healing recovery.
      - Strict path traversal and symlink prevention.
    """

    def __init__(self, vault_root: Optional[Path] = None) -> None:
        if vault_root is None:
            base = Path(__file__).resolve().parent.parent.parent.parent
            self.vault_root = (base / "data" / "prospective").resolve()
        else:
            self.vault_root = vault_root.resolve()

        self._lock = threading.Lock()
        self._init_vault_directories()
        self.journal_path = self.vault_root / "manifests" / "vault_journal.jsonl"

    def _init_vault_directories(self) -> None:
        self.vault_root.mkdir(parents=True, exist_ok=True)
        for sdir in VAULT_SUBDIRS:
            (self.vault_root / sdir).mkdir(parents=True, exist_ok=True)

    def _validate_path_safety(self, path: Path) -> Path:
        """Ensures that the resolved path is strictly within the vault root and not a symlink."""
        resolved = path.resolve()
        if not str(resolved).startswith(str(self.vault_root)):
            raise VaultSecurityError(
                f"Path traversal violation: Target '{path}' resolves outside vault root '{self.vault_root}'"
            )
        if path.is_symlink():
            raise VaultSecurityError(f"Symlink violation: Path '{path}' is a symbolic link.")
        return resolved

    def store_bytes(
        self,
        category: str,
        data: bytes,
        source_metadata: Dict[str, Any],
        extension: str = "bin",
    ) -> Tuple[str, Path, bool]:
        """
        Stores raw bytes atomically using content-addressing (SHA-256).
        Returns: (sha256_hash, stored_file_path, is_duplicate).
        """
        if category not in VAULT_SUBDIRS or category == "quarantine":
            raise ValueError(f"Category '{category}' must be one of {VAULT_SUBDIRS} excluding quarantine")

        sha256_hash = hashlib.sha256(data).hexdigest()
        target_dir = self.vault_root / category
        target_file = target_dir / f"{sha256_hash}.{extension}"
        self._validate_path_safety(target_file)

        with self._lock:
            # Duplicate / corruption check if file exists
            if target_file.exists():
                existing_sha = self._compute_file_sha256(target_file)
                if existing_sha == sha256_hash:
                    return sha256_hash, target_file, True
                else:
                    # Corruption detected in existing file -> quarantine it!
                    quarantine_name = f"{target_file.name}.corrupted.{int(time.time())}"
                    quarantine_dest = self.vault_root / "quarantine" / quarantine_name
                    shutil.move(str(target_file), str(quarantine_dest))
                    raise VaultCorruptionError(
                        f"Integrity corruption detected in existing vault file {target_file}! Quarantined to {quarantine_dest}"
                    )

            # Atomic staging write with unique nonce
            nonce = f"{os.getpid()}_{threading.get_ident()}_{uuid.uuid4().hex[:8]}"
            temp_file = target_dir / f".tmp_{sha256_hash}_{nonce}"
            try:
                with open(temp_file, "wb") as f:
                    f.write(data)
                    f.flush()
                    os.fsync(f.fileno())
                # Atomic replace
                os.replace(temp_file, target_file)
            finally:
                if temp_file.exists():
                    try:
                        temp_file.unlink()
                    except OSError:
                        pass

            # Append to journal
            self._append_journal_entry(
                category=category,
                sha256=sha256_hash,
                relative_path=str(target_file.relative_to(self.vault_root)).replace("\\", "/"),
                byte_size=len(data),
                metadata=source_metadata,
            )

        return sha256_hash, target_file, False

    def store_json(
        self,
        category: str,
        obj: Any,
        source_metadata: Dict[str, Any],
    ) -> Tuple[str, Path, bool]:
        """Serializes and stores structured JSON content atomically."""
        data_str = json.dumps(obj, indent=2, sort_keys=True)
        data_bytes = data_str.encode("utf-8")
        return self.store_bytes(category, data_bytes, source_metadata, extension="json")

    def _append_journal_entry(
        self,
        category: str,
        sha256: str,
        relative_path: str,
        byte_size: int,
        metadata: Dict[str, Any],
    ) -> None:
        """Appends an immutable entry to vault_journal.jsonl with fsync."""
        entry = {
            "schema_version": SCHEMA_VERSION,
            "timestamp_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "category": category,
            "sha256": sha256,
            "relative_path": relative_path,
            "byte_size": byte_size,
            "metadata": metadata,
        }
        line = json.dumps(entry, sort_keys=True) + "\n"
        with open(self.journal_path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def _compute_file_sha256(self, path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(65536):
                h.update(chunk)
        return h.hexdigest().lower()

    def read_journal_entries(self) -> Tuple[List[Dict[str, Any]], int]:
        """
        Reads journal entries resiliently.
        Gracefully ignores incomplete/truncated lines resulting from simulated crashes.
        Returns: (valid_entries, corrupted_or_truncated_lines_count).
        """
        if not self.journal_path.exists():
            return [], 0

        valid_entries: List[Dict[str, Any]] = []
        truncated_count = 0

        with open(self.journal_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    entry = json.loads(s)
                    if isinstance(entry, dict) and "sha256" in entry:
                        valid_entries.append(entry)
                    else:
                        truncated_count += 1
                except json.JSONDecodeError:
                    truncated_count += 1

        return valid_entries, truncated_count

    def recover_vault(self) -> Dict[str, Any]:
        """
        Performs a full audit and crash-recovery pass over the vault:
          1. Scans all files across categories.
          2. Quarantines corrupt files (hash mismatch).
          3. Detects orphaned valid files not in journal, and appends them to journal.
          4. Returns structured recovery summary with statuses: VERIFIED, RECOVERED, QUARANTINED.
        """
        with self._lock:
            journal_entries, truncated_lines = self.read_journal_entries()
            journaled_shas = {e["sha256"] for e in journal_entries}

            verified_files: List[str] = []
            recovered_files: List[str] = []
            quarantined_files: List[str] = []

            for category in VAULT_SUBDIRS:
                if category in ("manifests", "quarantine"):
                    continue
                target_dir = self.vault_root / category
                if not target_dir.exists():
                    continue

                for fpath in target_dir.glob("*"):
                    if not fpath.is_file() or fpath.name.startswith(".tmp_"):
                        continue

                    stem = fpath.stem.lower()
                    actual_sha = self._compute_file_sha256(fpath)
                    rel = str(fpath.relative_to(self.vault_root)).replace("\\", "/")

                    # Corrupt check
                    if len(stem) == 64 and actual_sha != stem:
                        quarantine_name = f"{fpath.name}.corrupted.{int(time.time())}"
                        quarantine_dest = self.vault_root / "quarantine" / quarantine_name
                        shutil.move(str(fpath), str(quarantine_dest))
                        quarantined_files.append(rel)
                        continue

                    # Valid file
                    if actual_sha in journaled_shas:
                        verified_files.append(rel)
                    else:
                        # Orphaned valid file: recover into journal
                        self._append_journal_entry(
                            category=category,
                            sha256=actual_sha,
                            relative_path=rel,
                            byte_size=fpath.stat().st_size,
                            metadata={"recovered_at_utc": datetime.now(timezone.utc).isoformat(), "source": "crash_recovery"},
                        )
                        journaled_shas.add(actual_sha)
                        recovered_files.append(rel)

            status = "HEALTHY"
            if quarantined_files:
                status = "CORRUPTION_QUARANTINED"
            elif recovered_files:
                status = "ORPHANS_RECOVERED"

            return {
                "vault_root": str(self.vault_root),
                "status": status,
                "verified_count": len(verified_files),
                "recovered_count": len(recovered_files),
                "quarantined_count": len(quarantined_files),
                "truncated_journal_lines": truncated_lines,
                "quarantined_files": quarantined_files,
                "recovered_files": recovered_files,
            }

    def verify_vault_integrity(self) -> Dict[str, Any]:
        """
        Audits all files in the vault and verifies their SHA-256 matches their filename.
        """
        scanned_files = 0
        corrupt_files = []
        verified_files = []

        for category in VAULT_SUBDIRS:
            if category == "quarantine":
                continue
            target_dir = self.vault_root / category
            if not target_dir.exists():
                continue
            for fpath in target_dir.glob("*"):
                if fpath.is_file() and not fpath.name.startswith(".tmp_") and fpath.name != "vault_journal.jsonl":
                    scanned_files += 1
                    stem = fpath.stem
                    actual_sha = self._compute_file_sha256(fpath)
                    if len(stem) == 64 and actual_sha != stem:
                        corrupt_files.append({
                            "path": str(fpath.relative_to(self.vault_root)).replace("\\", "/"),
                            "expected_sha": stem,
                            "actual_sha": actual_sha,
                        })
                    else:
                        verified_files.append(str(fpath.relative_to(self.vault_root)).replace("\\", "/"))

        journal_entries, truncated_lines = self.read_journal_entries()

        status = "HEALTHY"
        if corrupt_files:
            status = "CORRUPTION_DETECTED"
        elif truncated_lines > 0:
            status = "AUDIT_WARNING"

        return {
            "vault_root": str(self.vault_root),
            "status": status,
            "schema_version": SCHEMA_VERSION,
            "total_objects_scanned": scanned_files,
            "total_verified": len(verified_files),
            "total_corrupt": len(corrupt_files),
            "corrupt_files": corrupt_files,
            "journal_entries": len(journal_entries),
            "truncated_journal_lines": truncated_lines,
            "trust_model": "LOCAL_CONTENT_ADDRESSED_APPEND_ONLY_JOURNAL",
        }

    def export_manifest(self) -> Dict[str, Any]:
        """Exports a deterministic cryptographic manifest of all stored vault artifacts."""
        audit = self.verify_vault_integrity()
        manifest_items = {}
        for category in VAULT_SUBDIRS:
            if category == "quarantine":
                continue
            target_dir = self.vault_root / category
            if not target_dir.exists():
                continue
            for fpath in sorted(list(target_dir.glob("*"))):
                if fpath.is_file() and not fpath.name.startswith(".tmp_") and fpath.name != "vault_journal.jsonl":
                    rel = str(fpath.relative_to(self.vault_root)).replace("\\", "/")
                    sha = self._compute_file_sha256(fpath)
                    manifest_items[rel] = {
                        "sha256": sha,
                        "byte_size": fpath.stat().st_size,
                        "category": category,
                    }

        return {
            "schema_version": SCHEMA_VERSION,
            "exported_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "vault_status": audit["status"],
            "total_artifacts": len(manifest_items),
            "artifacts": manifest_items,
        }

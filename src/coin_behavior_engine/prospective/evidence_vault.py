"""
Sprint 11.23.5A: Cross-Process Hardened Content-Addressed Immutable Evidence Vault
Provides atomic, cross-process and multi-writer thread-safe, content-addressed storage
for prospective releases, schedules, consensus, and market observations with append-only
journaling, crash recovery, corruption quarantine, path traversal protection, and partial write handling.
Coordinates concurrent access across separate OS processes via advisory OS file locking.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
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

SCHEMA_VERSION = "1.2.0"


class VaultSecurityError(Exception):
    """Raised when path traversal or symlink tampering is detected in the evidence vault."""
    pass


class VaultCorruptionError(Exception):
    """Raised when byte corruption is detected in existing vault objects."""
    pass


class VaultLockTimeoutError(Exception):
    """Raised when cross-process lock acquisition exceeds the configured timeout."""
    pass


class VaultRecoveryStatus(str, Enum):
    VERIFIED = "VERIFIED"
    RECOVERABLE = "RECOVERABLE"
    INCOMPLETE = "INCOMPLETE"
    CORRUPTED = "CORRUPTED"
    QUARANTINED = "QUARANTINED"


class CrossProcessVaultLock:
    """
    Cross-process advisory file lock context manager.
    Coordinates concurrent vault operations across separate operating-system processes
    using OS-level primitives (msvcrt on Windows, fcntl on Unix).
    """

    def __init__(self, lock_file_path: Path, timeout: float = 30.0, poll_interval: float = 0.01) -> None:
        self.lock_file_path = lock_file_path
        self.timeout = timeout
        self.poll_interval = poll_interval
        self._fd: Optional[int] = None

    def __enter__(self) -> CrossProcessVaultLock:
        self.acquire()
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()

    def acquire(self) -> None:
        """Acquires exclusive cross-process lock with timeout."""
        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        start_time = time.time()

        while True:
            try:
                # Open or create lock file with read/write access
                self._fd = os.open(str(self.lock_file_path), os.O_CREAT | os.O_RDWR)
                # Ensure at least 1 byte exists for Windows locking
                if os.path.getsize(str(self.lock_file_path)) == 0:
                    os.write(self._fd, b"L")
                    os.fsync(self._fd)

                os.lseek(self._fd, 0, os.SEEK_SET)

                if sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)

                # Successfully acquired lock
                return
            except (OSError, IOError):
                if self._fd is not None:
                    try:
                        os.close(self._fd)
                    except OSError:
                        pass
                    self._fd = None

                if time.time() - start_time >= self.timeout:
                    raise VaultLockTimeoutError(
                        f"Failed to acquire cross-process vault lock at '{self.lock_file_path}' within {self.timeout}s"
                    )
                time.sleep(self.poll_interval)

    def release(self) -> None:
        """Releases the cross-process lock and closes file descriptor."""
        if self._fd is not None:
            try:
                os.lseek(self._fd, 0, os.SEEK_SET)
                if sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fd, fcntl.LOCK_UN)
            except OSError:
                pass
            finally:
                try:
                    os.close(self._fd)
                except OSError:
                    pass
                self._fd = None


class ImmutableEvidenceVault:
    """
    Local content-addressed evidence vault with cross-process concurrency and crash durability.
    Features:
      - Cross-process advisory file locking paired with thread-level reentrancy.
      - Create-if-absent verification to eliminate silent overwrites.
      - Multi-writer atomic writes via unique temporary staging and fsync.
      - Append-only journaling with explicit recovery statuses (VERIFIED, RECOVERABLE, INCOMPLETE, CORRUPTED, QUARANTINED).
      - Resilient journal parser ignoring incomplete/truncated crash lines.
      - Deterministic vault audit and self-healing recovery.
      - Strict path traversal and symlink prevention.
    """

    def __init__(self, vault_root: Optional[Path] = None, lock_timeout: float = 30.0) -> None:
        if vault_root is None:
            base = Path(__file__).resolve().parent.parent.parent.parent
            self.vault_root = (base / "data" / "prospective").resolve()
        else:
            self.vault_root = vault_root.resolve()

        self.lock_timeout = lock_timeout
        self._thread_lock = threading.Lock()
        self._init_vault_directories()
        self.journal_path = self.vault_root / "manifests" / "vault_journal.jsonl"
        self.lock_file_path = self.vault_root / "manifests" / ".vault.lock"

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

    def _get_process_lock(self) -> CrossProcessVaultLock:
        return CrossProcessVaultLock(self.lock_file_path, timeout=self.lock_timeout)

    def store_bytes(
        self,
        category: str,
        data: bytes,
        source_metadata: Dict[str, Any],
        extension: str = "bin",
    ) -> Tuple[str, Path, bool]:
        """
        Stores raw bytes atomically using content-addressing (SHA-256).
        Coordinates across threads and separate OS processes to guarantee:
          1. Concurrent processes cannot silently overwrite conflicting evidence.
          2. Verified objects are never replaced.
          3. Duplicate writes are strictly idempotent.
        Returns: (sha256_hash, stored_file_path, is_duplicate).
        """
        if category not in VAULT_SUBDIRS or category == "quarantine":
            raise ValueError(f"Category '{category}' must be one of {VAULT_SUBDIRS} excluding quarantine")

        sha256_hash = hashlib.sha256(data).hexdigest()
        target_dir = self.vault_root / category
        target_file = target_dir / f"{sha256_hash}.{extension}"
        self._validate_path_safety(target_file)

        with self._thread_lock:
            with self._get_process_lock():
                # 1. Check if target file already exists
                if target_file.exists():
                    existing_sha = self._compute_file_sha256(target_file)
                    if existing_sha == sha256_hash:
                        return sha256_hash, target_file, True
                    else:
                        # Existing file corrupted: quarantine it
                        quarantine_name = f"{target_file.name}.corrupted.{int(time.time())}_{uuid.uuid4().hex[:6]}"
                        quarantine_dest = self.vault_root / "quarantine" / quarantine_name
                        shutil.move(str(target_file), str(quarantine_dest))
                        raise VaultCorruptionError(
                            f"Integrity corruption detected in existing vault file {target_file}! Quarantined to {quarantine_dest}"
                        )

                # 2. Stage write to unique temporary file with fsync
                nonce = f"{os.getpid()}_{threading.get_ident()}_{uuid.uuid4().hex}"
                temp_file = target_dir / f".tmp_{sha256_hash}_{nonce}"
                try:
                    with open(temp_file, "wb") as f:
                        f.write(data)
                        f.flush()
                        os.fsync(f.fileno())

                    # 3. Create-if-absent verification before publish
                    if target_file.exists():
                        # Another process created the file while we were staging
                        existing_sha = self._compute_file_sha256(target_file)
                        if existing_sha == sha256_hash:
                            return sha256_hash, target_file, True
                        else:
                            quarantine_name = f"{target_file.name}.corrupted.{int(time.time())}_{uuid.uuid4().hex[:6]}"
                            quarantine_dest = self.vault_root / "quarantine" / quarantine_name
                            shutil.move(str(target_file), str(quarantine_dest))
                            raise VaultCorruptionError(
                                f"Concurrent corrupt object detected at {target_file}! Quarantined to {quarantine_dest}"
                            )

                    # 4. Atomic publish
                    os.replace(temp_file, target_file)

                    # 5. Append to journal under the same lock
                    self._append_journal_entry(
                        category=category,
                        sha256=sha256_hash,
                        relative_path=str(target_file.relative_to(self.vault_root)).replace("\\", "/"),
                        byte_size=len(data),
                        metadata=source_metadata,
                    )
                finally:
                    if temp_file.exists():
                        try:
                            temp_file.unlink()
                        except OSError:
                            pass

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
        Gracefully isolates and skips incomplete/truncated lines resulting from crashes.
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
                    if isinstance(entry, dict) and "sha256" in entry and "category" in entry:
                        valid_entries.append(entry)
                    else:
                        truncated_count += 1
                except json.JSONDecodeError:
                    truncated_count += 1

        return valid_entries, truncated_count

    def recover_vault(self) -> Dict[str, Any]:
        """
        Performs a full cross-process audit and crash-recovery pass over the vault:
          1. Scans all files across categories.
          2. Quarantines corrupt files (hash mismatch) -> STATUS: QUARANTINED.
          3. Quarantines incomplete/abandoned .tmp_* files -> STATUS: INCOMPLETE.
          4. Detects orphaned valid files not in journal, and appends them to journal -> STATUS: RECOVERABLE.
          5. Verifies existing journaled objects -> STATUS: VERIFIED.
          6. Returns structured recovery summary with explicit recovery statuses.
        """
        with self._thread_lock:
            with self._get_process_lock():
                journal_entries, truncated_lines = self.read_journal_entries()
                journaled_shas = {e["sha256"] for e in journal_entries}

                verified_files: List[str] = []
                recovered_files: List[str] = []
                quarantined_files: List[str] = []
                incomplete_files: List[str] = []

                for category in VAULT_SUBDIRS:
                    if category in ("manifests", "quarantine"):
                        continue
                    target_dir = self.vault_root / category
                    if not target_dir.exists():
                        continue

                    for fpath in list(target_dir.glob("*")):
                        if not fpath.is_file():
                            continue

                        # Detect incomplete staging files from interrupted writes
                        if fpath.name.startswith(".tmp_"):
                            quarantine_name = f"{fpath.name}.incomplete.{int(time.time())}_{uuid.uuid4().hex[:6]}"
                            quarantine_dest = self.vault_root / "quarantine" / quarantine_name
                            try:
                                shutil.move(str(fpath), str(quarantine_dest))
                                incomplete_files.append(str(fpath.name))
                            except OSError:
                                pass
                            continue

                        stem = fpath.stem.lower()
                        actual_sha = self._compute_file_sha256(fpath)
                        rel = str(fpath.relative_to(self.vault_root)).replace("\\", "/")

                        # Corrupt check
                        if len(stem) == 64 and actual_sha != stem:
                            quarantine_name = f"{fpath.name}.corrupted.{int(time.time())}_{uuid.uuid4().hex[:6]}"
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
                                metadata={
                                    "recovered_at_utc": datetime.now(timezone.utc).isoformat(),
                                    "source": "cross_process_crash_recovery",
                                    "recovery_status": VaultRecoveryStatus.RECOVERABLE.value,
                                },
                            )
                            journaled_shas.add(actual_sha)
                            recovered_files.append(rel)

                status = "HEALTHY"
                if quarantined_files:
                    status = "CORRUPTION_QUARANTINED"
                elif recovered_files:
                    status = "ORPHANS_RECOVERED"
                elif incomplete_files:
                    status = "INCOMPLETE_STAGES_CLEANED"

                return {
                    "vault_root": str(self.vault_root),
                    "status": status,
                    "recovery_status_verdict": (
                        VaultRecoveryStatus.CORRUPTED.value if quarantined_files
                        else (VaultRecoveryStatus.RECOVERABLE.value if recovered_files
                        else (VaultRecoveryStatus.INCOMPLETE.value if incomplete_files
                        else VaultRecoveryStatus.VERIFIED.value))
                    ),
                    "verified_count": len(verified_files),
                    "recovered_count": len(recovered_files),
                    "quarantined_count": len(quarantined_files),
                    "incomplete_count": len(incomplete_files),
                    "truncated_journal_lines": truncated_lines,
                    "quarantined_files": quarantined_files,
                    "recovered_files": recovered_files,
                    "incomplete_files": incomplete_files,
                }

    def verify_vault_integrity(self) -> Dict[str, Any]:
        """Audits all files in the vault and verifies their SHA-256 matches their filename."""
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
                if fpath.is_file() and not fpath.name.startswith(".tmp_") and fpath.name != "vault_journal.jsonl" and not fpath.name.endswith(".lock"):
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
                if fpath.is_file() and not fpath.name.startswith(".tmp_") and fpath.name != "vault_journal.jsonl" and not fpath.name.endswith(".lock"):
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

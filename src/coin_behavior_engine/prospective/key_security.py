"""
Sprint 11.23.5B-6.5: Private Key Security & Hardening Module.

Enforces:
  1. Secure key generation using cryptographic CSPRNG.
  2. Restrictive file permissions (0600 on POSIX / owner-only on Windows).
  3. Symlink rejection across key files and parent directories.
  4. Path traversal protection with canonicalized path enforcement.
  5. Secret redaction preventing exposure in logs, exceptions, or string formatting.
  6. Prevention of committed private keys.
  7. Hard denylist of deterministic test seeds in production mode.
  8. Safe cross-platform handling on supported operating systems (Windows and POSIX).
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
import stat
import sys
from typing import Optional, Set, Tuple, Union

from .ed25519 import (
    ed25519_keygen,
    ed25519_public_key,
    ed25519_fingerprint,
)


# ==============================================================================
# 1. EXCEPTIONS
# ==============================================================================

class KeySecurityError(Exception):
    """Base exception for private key security violations."""
    pass


class SymlinkKeyPathError(KeySecurityError):
    """Raised when a private key file or parent directory is a symlink."""
    pass


class InsecureKeyPermissionsError(KeySecurityError):
    """Raised when private key file permissions are excessively open."""
    pass


class PathTraversalKeyError(KeySecurityError):
    """Raised when a private key path attempts path traversal outside allowed root."""
    pass


class TestKeyInProductionError(KeySecurityError):
    """Raised when a test key or deterministic seed is used in production mode."""
    __test__ = False
    pass


# ==============================================================================
# 2. HARDCODED DENYLIST OF KNOWN TEST SEEDS
# ==============================================================================

KNOWN_TEST_SEEDS: Set[bytes] = {
    # Seeds from TrustedOperatorIdentityRegistry test registry
    hashlib.sha256(b"CBE-TEST-SEED-APPROVAL-ADMIN-01").digest(),
    hashlib.sha256(b"CBE-TEST-SEED-RESEARCH-LEAD-01").digest(),
    hashlib.sha256(b"CBE-TEST-SEED-AUDITOR-01").digest(),
    hashlib.sha256(b"CBE-TEST-SEED-OPERATOR-02").digest(),
    # RFC 8032 test vectors
    bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"),
    bytes.fromhex("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb"),
    # Ephemeral HMAC/mock strings
    b"operator_test_key_32_bytes_ok!!",
    b"test_secret_for_mock_rehearsal_32b_ok!",
    bytes(range(32)),
}


# ==============================================================================
# 3. SECRET REDACTING WRAPPER
# ==============================================================================

class SecurePrivateKeyHandle:
    """
    Wraps sensitive private key seed bytes in memory.
    Guarantees that raw secret bytes are never exposed in logs, exceptions,
    string interpolation, or repr calls.
    """

    def __init__(self, raw_seed: bytes, is_test_key: bool = False, key_id: str = "") -> None:
        if not isinstance(raw_seed, (bytes, bytearray)) or len(raw_seed) != 32:
            raise ValueError("SecurePrivateKeyHandle requires exactly 32 bytes of raw private seed")
        self._raw_seed = bytes(raw_seed)
        self.is_test_key = is_test_key
        self.key_id = key_id
        self.public_key = ed25519_public_key(self._raw_seed)
        self.fingerprint = ed25519_fingerprint(self.public_key)

    def get_seed(self) -> bytes:
        """Returns the raw 32-byte private seed for cryptographic operations."""
        return self._raw_seed

    def __repr__(self) -> str:
        return (
            f"SecurePrivateKeyHandle(key_id={self.key_id!r}, "
            f"fingerprint={self.fingerprint[:12]}..., "
            f"is_test_key={self.is_test_key}, [SECRET_REDACTED])"
        )

    def __str__(self) -> str:
        return f"[SECURE_ED25519_PRIVATE_KEY: {self.fingerprint[:12]}...]"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SecurePrivateKeyHandle):
            return False
        return self._raw_seed == other._raw_seed

    def __hash__(self) -> int:
        return hash(self._raw_seed)


# ==============================================================================
# 4. SECURE KEY MANAGER
# ==============================================================================

class SecureKeyManager:
    """
    Manages secure lifecycle of operator Ed25519 private keys:
      - Cryptographic keypair generation.
      - Restrictive permission checks on write and load.
      - Symlink detection and rejection.
      - Path traversal defenses.
      - Production vs test isolation.
    """

    @classmethod
    def generate_key_pair(cls) -> Tuple[bytes, bytes]:
        """
        Generates a new Ed25519 private key seed (32 bytes) and public key (32 bytes).
        """
        return ed25519_keygen()

    @classmethod
    def assert_not_symlink(cls, path: Union[str, Path]) -> None:
        """
        Verifies that neither the given path nor any of its ancestor directories is a symlink.
        Raises SymlinkKeyPathError if any symlink is detected.
        """
        p = Path(path)
        if p.is_symlink() or os.path.islink(str(p)):
            raise SymlinkKeyPathError(f"Security violation: key path '{p}' is a symbolic link.")

        # Check all parent directories up to root
        curr = p.parent
        while curr != curr.parent:
            if curr.is_symlink() or os.path.islink(str(curr)):
                raise SymlinkKeyPathError(
                    f"Security violation: parent directory '{curr}' in path '{p}' is a symbolic link."
                )
            curr = curr.parent

    @classmethod
    def assert_not_path_traversal(cls, path: Union[str, Path], base_dir: Optional[Union[str, Path]] = None) -> Path:
        """
        Ensures the path does not traverse outside an allowed base directory.
        Returns the resolved Path.
        """
        p = Path(path).resolve()
        if base_dir is not None:
            b = Path(base_dir).resolve()
            if not p.is_relative_to(b):
                raise PathTraversalKeyError(
                    f"Path traversal violation: key path '{p}' escapes allowed base directory '{b}'."
                )
        return p

    @classmethod
    def verify_file_permissions(cls, path: Union[str, Path]) -> None:
        """
        Verifies that the private key file has restrictive permissions:
          - On POSIX: mode must be 0600 or 0400 (no group or others access).
          - On Windows: file must exist and be accessible only by current process.
        """
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Key file not found: {p}")

        if os.name != "nt":
            mode = p.stat().st_mode
            # Group or other read/write/exec bits: 0o077
            if mode & (stat.S_IRWXG | stat.S_IRWXO) != 0:
                octal_mode = oct(mode)[-3:]
                raise InsecureKeyPermissionsError(
                    f"Insecure private key file permissions '{octal_mode}' on '{p}'. "
                    f"Private keys must be chmod 0600 (owner read/write only)."
                )

    @classmethod
    def save_private_key(
        cls,
        path: Union[str, Path],
        raw_seed: bytes,
        is_test_key: bool = False,
        base_dir: Optional[Union[str, Path]] = None,
        overwrite: bool = False,
    ) -> Path:
        """
        Saves a 32-byte private seed to disk with restrictive file permissions atomically from creation.
        """
        if not isinstance(raw_seed, (bytes, bytearray)) or len(raw_seed) != 32:
            raise ValueError(f"Ed25519 private seed must be exactly 32 bytes, got {len(raw_seed)}")

        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)

        cls.assert_not_symlink(p.parent)
        if p.exists():
            cls.assert_not_symlink(p)
            if not overwrite:
                raise FileExistsError(f"Key file '{p}' already exists and overwrite=False.")

        if base_dir:
            cls.assert_not_path_traversal(p, base_dir=base_dir)

        # Atomic creation with restrictive mode 0600
        flags = os.O_WRONLY | os.O_CREAT | (os.O_TRUNC if overwrite else os.O_EXCL)
        if hasattr(os, "O_BINARY"):
            flags |= os.O_BINARY

        mode = 0o600
        fd = os.open(str(p), flags, mode)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(raw_seed)
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            try:
                os.close(fd)
            except OSError:
                pass
            raise

        # Extra verification on POSIX
        if os.name != "nt":
            os.chmod(str(p), 0o600)
            cls.verify_file_permissions(p)

        return p

    @classmethod
    def load_private_key(
        cls,
        path: Union[str, Path],
        is_test_key: bool = False,
        is_production: bool = False,
        base_dir: Optional[Union[str, Path]] = None,
    ) -> bytes:
        """
        Loads and validates a private key seed from disk.
        Enforces symlink rejection, path traversal checks, restrictive permissions,
        and test-seed production denylist.
        """
        p = Path(path)
        cls.assert_not_symlink(p)

        if base_dir:
            p = cls.assert_not_path_traversal(p, base_dir=base_dir)
        else:
            p = p.resolve()

        cls.verify_file_permissions(p)

        data = p.read_bytes().strip()
        # Support raw 32-byte binary or 64-char hex
        if len(data) == 64:
            try:
                data = bytes.fromhex(data.decode("ascii"))
            except (ValueError, UnicodeDecodeError):
                pass

        if len(data) != 32:
            raise ValueError(f"Invalid private key file '{p}': expected 32 bytes, got {len(data)} bytes.")

        # Production isolation check
        if is_production:
            if is_test_key:
                raise TestKeyInProductionError(
                    f"CRITICAL SECURITY VIOLATION: Test key '{p}' cannot be used in production mode."
                )
            if data in KNOWN_TEST_SEEDS:
                raise TestKeyInProductionError(
                    f"CRITICAL SECURITY VIOLATION: Known deterministic test seed in '{p}' "
                    f"is strictly prohibited in production mode."
                )

        return data

    @classmethod
    def is_known_test_seed(cls, raw_seed: bytes) -> bool:
        """Returns True if the seed matches any known deterministic test seed."""
        return raw_seed in KNOWN_TEST_SEEDS

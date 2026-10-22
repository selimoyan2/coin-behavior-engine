"""
Cryptographically Hardened Ed25519 Digital Signature Implementation.

Sprint 11.23.5B-6.5: Replaces custom pure-Python arithmetic with the audited,
maintained standard 'cryptography' library (RFC 8032 compliant).
Silent fallback to custom cryptography is strictly prohibited.
"""

from __future__ import annotations

import hashlib
import os
from typing import Tuple, Union

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.exceptions import InvalidSignature
except ImportError as exc:
    raise ImportError(
        "CRITICAL SECURITY REQUIREMENT: The audited 'cryptography' library is required "
        "for Ed25519 digital signatures. Silent fallback to unmaintained custom cryptography "
        "is strictly prohibited by CBE governance policy."
    ) from exc


CRYPTOGRAPHY_PROVIDER = "cryptography.hazmat.primitives.asymmetric.ed25519"
IS_AUDITED_LIBRARY = True
ZERO_CUSTOM_FALLBACK = True


def ed25519_keygen() -> Tuple[bytes, bytes]:
    """
    Generate an Ed25519 private key seed (32 bytes) and public key (32 bytes).
    Uses the audited standard cryptography library CSPRNG.
    """
    priv = Ed25519PrivateKey.generate()
    seed = priv.private_bytes_raw()
    pub = priv.public_key().public_bytes_raw()
    return seed, pub


def ed25519_public_key(seed: bytes) -> bytes:
    """
    Derive 32-byte Ed25519 public key from 32-byte private seed.
    Raises ValueError if seed length is invalid or not bytes.
    """
    if not isinstance(seed, (bytes, bytearray)):
        raise TypeError(f"Ed25519 seed must be bytes, got {type(seed).__name__}")
    if len(seed) != 32:
        raise ValueError(f"Ed25519 seed must be exactly 32 bytes, got {len(seed)}")
    try:
        priv = Ed25519PrivateKey.from_private_bytes(bytes(seed))
        return priv.public_key().public_bytes_raw()
    except Exception as exc:
        raise ValueError(f"Failed to derive Ed25519 public key from seed: {exc}") from exc


def ed25519_sign(seed: bytes, message: bytes) -> bytes:
    """
    Sign message bytes using 32-byte secret seed. Returns 64-byte signature.
    Complies with RFC 8032 pure Ed25519.
    """
    if not isinstance(seed, (bytes, bytearray)):
        raise TypeError(f"Ed25519 seed must be bytes, got {type(seed).__name__}")
    if len(seed) != 32:
        raise ValueError(f"Ed25519 seed must be exactly 32 bytes, got {len(seed)}")
    if not isinstance(message, (bytes, bytearray)):
        raise TypeError(f"Message must be bytes, got {type(message).__name__}")

    priv = Ed25519PrivateKey.from_private_bytes(bytes(seed))
    return priv.sign(bytes(message))


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """
    Verify 64-byte signature against 32-byte public key and message bytes.
    Returns True if cryptographically valid, False if invalid or malformed.
    """
    if not isinstance(public_key, (bytes, bytearray)) or len(public_key) != 32:
        return False
    if not isinstance(signature, (bytes, bytearray)) or len(signature) != 64:
        return False
    if not isinstance(message, (bytes, bytearray)):
        return False

    try:
        pub = Ed25519PublicKey.from_public_bytes(bytes(public_key))
        pub.verify(bytes(signature), bytes(message))
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def ed25519_fingerprint(public_key: bytes) -> str:
    """
    Compute SHA-256 fingerprint formatted as hex for a 32-byte public key.
    """
    if not isinstance(public_key, (bytes, bytearray)) or len(public_key) != 32:
        raise ValueError("Ed25519 public key must be exactly 32 bytes")
    return hashlib.sha256(public_key).hexdigest()

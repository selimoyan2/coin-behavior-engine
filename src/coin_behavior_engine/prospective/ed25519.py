"""
Pure-Python RFC 8032 Ed25519 Digital Signature Implementation.

Zero-external-dependency implementation of Edwards-curve Digital Signature
Algorithm (Ed25519) using SHA-512 and Curve25519 extended coordinates.
Complies with RFC 8032 test vectors.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from typing import Tuple, Union


# Curve25519 parameters
_Q = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493


def _inv(x: int) -> int:
    return pow(x, _Q - 2, _Q)


_D = -121665 * _inv(121666) % _Q
_I = pow(2, (_Q - 1) // 4, _Q)


def _xrecover(y: int) -> int:
    xx = (y * y - 1) * _inv(_D * y * y + 1)
    x = pow(xx, (_Q + 3) // 8, _Q)
    if (x * x - xx) % _Q != 0:
        x = (x * _I) % _Q
    if x % 2 != 0:
        x = _Q - x
    return x


_BY = 4 * _inv(5) % _Q
_BX = _xrecover(_BY)
# Base point in extended coordinates (X, Y, Z, T) where T = X * Y / Z
_B = (_BX, _BY, 1, (_BX * _BY) % _Q)


def _pt_add(P: Tuple[int, int, int, int], Q: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    X1, Y1, Z1, T1 = P
    X2, Y2, Z2, T2 = Q
    A = ((Y1 - X1) * (Y2 - X2)) % _Q
    B = ((Y1 + X1) * (Y2 + X2)) % _Q
    C = (T1 * 2 * _D * T2) % _Q
    D = (Z1 * 2 * Z2) % _Q
    E = (B - A) % _Q
    F = (D - C) % _Q
    G = (D + C) % _Q
    H = (B + A) % _Q
    return ((E * F) % _Q, (G * H) % _Q, (F * G) % _Q, (E * H) % _Q)


def _pt_double(P: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    X1, Y1, Z1, _ = P
    A = (X1 * X1) % _Q
    B = (Y1 * Y1) % _Q
    C = (2 * Z1 * Z1) % _Q
    H = (A + B) % _Q
    E = (H - pow(X1 + Y1, 2, _Q)) % _Q
    G = (A - B) % _Q
    F = (C + G) % _Q
    return ((E * F) % _Q, (G * H) % _Q, (F * G) % _Q, (E * H) % _Q)


def _pt_mul(P: Tuple[int, int, int, int], s: int) -> Tuple[int, int, int, int]:
    R = (0, 1, 1, 0)
    for bit in bin(s)[2:]:
        R = _pt_double(R)
        if bit == "1":
            R = _pt_add(R, P)
    return R


def _pt_to_bytes(P: Tuple[int, int, int, int]) -> bytes:
    X, Y, Z, _ = P
    zi = _inv(Z)
    x = (X * zi) % _Q
    y = (Y * zi) % _Q
    b_arr = bytearray(y.to_bytes(32, "little"))
    if x & 1:
        b_arr[31] |= 0x80
    return bytes(b_arr)


def _bytes_to_pt(s: bytes) -> Union[Tuple[int, int, int, int], None]:
    if len(s) != 32:
        return None
    s_arr = bytearray(s)
    sign = (s_arr[31] >> 7) & 1
    s_arr[31] &= 0x7F
    y = int.from_bytes(s_arr, "little")
    if y >= _Q:
        return None
    x = _xrecover(y)
    if x is None:
        return None
    if x & 1 != sign:
        x = _Q - x
    if (-x * x + y * y - 1 - _D * x * x * y * y) % _Q != 0:
        return None
    return (x, y, 1, (x * y) % _Q)


def ed25519_keygen() -> Tuple[bytes, bytes]:
    """
    Generate an Ed25519 private key seed (32 bytes) and public key (32 bytes).
    """
    seed = os.urandom(32)
    pub = ed25519_public_key(seed)
    return seed, pub


def ed25519_public_key(seed: bytes) -> bytes:
    """
    Derive 32-byte Ed25519 public key from 32-byte seed.
    """
    if len(seed) != 32:
        raise ValueError("Ed25519 seed must be exactly 32 bytes")
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    A = _pt_mul(_B, a)
    return _pt_to_bytes(A)


def ed25519_sign(seed: bytes, message: bytes) -> bytes:
    """
    Sign message bytes using 32-byte secret seed. Returns 64-byte signature.
    """
    if len(seed) != 32:
        raise ValueError("Ed25519 seed must be exactly 32 bytes")
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    prefix = h[32:]
    A_bytes = _pt_to_bytes(_pt_mul(_B, a))
    r = int.from_bytes(hashlib.sha512(prefix + message).digest(), "little") % _L
    R_bytes = _pt_to_bytes(_pt_mul(_B, r))
    k = int.from_bytes(hashlib.sha512(R_bytes + A_bytes + message).digest(), "little") % _L
    S = (r + k * a) % _L
    return R_bytes + S.to_bytes(32, "little")


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    """
    Verify 64-byte signature against 32-byte public key and message bytes.
    Returns True if signature is cryptographically valid, False otherwise.
    """
    if len(public_key) != 32 or len(signature) != 64:
        return False
    R_bytes = signature[:32]
    S_bytes = signature[32:]
    S = int.from_bytes(S_bytes, "little")
    if S >= _L:
        return False
    A_pt = _bytes_to_pt(public_key)
    if A_pt is None:
        return False
    R_pt = _bytes_to_pt(R_bytes)
    if R_pt is None:
        return False
    k = int.from_bytes(hashlib.sha512(R_bytes + public_key + message).digest(), "little") % _L
    lhs = _pt_to_bytes(_pt_mul(_B, S))
    rhs = _pt_to_bytes(_pt_add(R_pt, _pt_mul(A_pt, k)))
    return hmac.compare_digest(lhs, rhs)


def ed25519_fingerprint(public_key: bytes) -> str:
    """
    Compute SHA-256 fingerprint formatted as hex for a 32-byte public key.
    """
    if len(public_key) != 32:
        raise ValueError("Ed25519 public key must be exactly 32 bytes")
    return hashlib.sha256(public_key).hexdigest()

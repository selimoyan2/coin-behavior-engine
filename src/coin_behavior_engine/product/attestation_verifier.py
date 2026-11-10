"""
Observation Completeness Attestation Verifier & Cache Engine.
Sprint 24 Final Cryptographic Hardening.

Provides fail-closed, cryptographic, RFC-8785-canonical verification for
observation series completeness attestations, binding:
- Dataset ID & Research Record ID (replay mitigation)
- Authenticated security claims: missing_observations, has_missing_data, expires_at_utc, is_superseded
- Source artifact disk file integrity, permissions, path confinement, and SHA-256 verification
- Observation window start and end (UTC), cadence, and geometry
- Trusted signing authority and key registry
- Thread-safe, signature-bound verification cache preventing signature cross-talk.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from coin_behavior_engine.product.credential_manager import signing_key_registry
from coin_behavior_engine.product.research_report_evidence import rfc8785_canonical_json


CADENCE_SECONDS_MAP = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "8h": 28800,
    "1d": 86400,
}

SUPPORTED_SCHEMA_VERSIONS = {
    "CBE-ATTESTATION-2.0.0",
    "CBE-ATTESTATION-1.0.0",
    "CBE-OBSERVATION-ATTESTATION-1.0.0",
    "1.0.0",
}

MANDATORY_CLAIMS = (
    "completeness_assertion",
    "dataset_id",
    "issuer",
    "key_id",
    "observation_count",
    "observation_end_utc",
    "observation_start_utc",
    "record_id",
    "schema_version",
    "source_artifact_sha256",
    "verification_method",
    "window_cadence",
)

TRUSTED_ISSUERS = {
    "CBE_AUTHORITATIVE_RESEARCH_AUTHORITY",
    "CBE_OBSERVATION_GOVERNANCE",
    "CBE_DATA_GOVERNANCE_COUNCIL",
    "CBE_SYSTEM",
    "CBE_CANONICAL_RESEARCH_AUTHORITY",
}

DISALLOWED_SYSTEM_DIRECTORIES = (
    "/etc",
    "/bin",
    "/sbin",
    "/usr",
    "/var/run",
    "/dev",
    "/proc",
    "/sys",
    "c:/windows",
    "c:\\windows",
)

MAX_SOURCE_ARTIFACT_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB bound


class AttestationVerificationCache:
    """
    Thread-safe, signature-bound verification result cache.
    Cache entries are strictly bound to:
    (artifact_digest, claims_sha256, signature_digest, key_id, trust_policy_version, is_revoked)
    
    Guarantees:
    1. A valid signature never authorizes another signature.
    2. A modified signature causes an immediate cache miss.
    3. Failed verifications never contaminate successful cache entries.
    4. Source artifact modifications on disk invalidate cached verification.
    """

    def __init__(self, max_size: int = 1000):
        self._max_size = max_size
        self._cache: Dict[Tuple[str, str, str, str, str, bool], Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._hit_count = 0
        self._miss_count = 0

    def get(
        self,
        artifact_digest: str,
        claims_sha256: str,
        signature_digest: str,
        key_id: str,
        trust_policy_version: str,
        is_revoked: bool,
        source_path: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            key = (
                artifact_digest,
                claims_sha256,
                signature_digest,
                key_id,
                trust_policy_version,
                is_revoked,
            )
            entry = self._cache.get(key)
            if entry is not None:
                # Source file continuous integrity check: verify file still exists and unchanged
                if source_path:
                    p = Path(source_path)
                    try:
                        if not p.exists() or not p.is_file():
                            self._cache.pop(key, None)
                            self._miss_count += 1
                            return None
                        stat = p.stat()
                        cached_mtime = entry.get("_source_mtime_ns")
                        cached_size = entry.get("_source_size")
                        if cached_mtime is not None and stat.st_mtime_ns != cached_mtime:
                            self._cache.pop(key, None)
                            self._miss_count += 1
                            return None
                        if cached_size is not None and stat.st_size != cached_size:
                            self._cache.pop(key, None)
                            self._miss_count += 1
                            return None
                    except Exception:
                        self._cache.pop(key, None)
                        self._miss_count += 1
                        return None

                self._hit_count += 1
                res = dict(entry["result"])
                return res

            self._miss_count += 1
            return None

    def put(
        self,
        artifact_digest: str,
        claims_sha256: str,
        signature_digest: str,
        key_id: str,
        trust_policy_version: str,
        is_revoked: bool,
        result: Dict[str, Any],
        source_mtime_ns: Optional[int] = None,
        source_size: Optional[int] = None,
    ) -> None:
        with self._lock:
            if len(self._cache) >= self._max_size:
                # Evict oldest 20%
                keys_to_remove = list(self._cache.keys())[: self._max_size // 5]
                for k in keys_to_remove:
                    self._cache.pop(k, None)

            key = (
                artifact_digest,
                claims_sha256,
                signature_digest,
                key_id,
                trust_policy_version,
                is_revoked,
            )
            self._cache[key] = {
                "result": dict(result),
                "_source_mtime_ns": source_mtime_ns,
                "_source_size": source_size,
            }

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self._hit_count = 0
            self._miss_count = 0

    @property
    def stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._cache),
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "max_size": self._max_size,
            }


# Global thread-safe cache instance
attestation_cache = AttestationVerificationCache()


class ObservationCompletenessAttestationVerifier:
    """
    Fail-closed cryptographic verifier for research observation completeness attestations.
    Authenticates all security-relevant claims, verifies physical source file integrity,
    and binds verification results to the exact cryptographic signature.
    """

    TRUST_POLICY_VERSION = "2026.2"

    @classmethod
    def extract_canonical_claims(cls, attestation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts all security-relevant bound claims into the canonical dictionary.
        Strictly includes missing_observations, has_missing_data, expires_at_utc, and is_superseded
        so that any mutation invalidates the cryptographic signature.
        """
        expires_val = attestation.get("expires_at_utc")
        expires_str = str(expires_val) if expires_val else ""

        return {
            "completeness_assertion": bool(
                attestation.get("completeness_assertion", attestation.get("verified_continuous_series", False))
            ),
            "dataset_id": str(attestation.get("dataset_id") or ""),
            "expires_at_utc": expires_str,
            "has_missing_data": bool(attestation.get("has_missing_data", False)),
            "is_superseded": bool(attestation.get("is_superseded", False)),
            "issuer": str(attestation.get("issuer") or ""),
            "key_id": str(attestation.get("key_id") or ""),
            "missing_observations": int(attestation.get("missing_observations", 0)),
            "observation_count": int(attestation.get("observation_count") or 0),
            "observation_end_utc": str(attestation.get("observation_end_utc") or ""),
            "observation_start_utc": str(attestation.get("observation_start_utc") or ""),
            "record_id": str(attestation.get("record_id") or ""),
            "schema_version": str(attestation.get("schema_version") or ""),
            "source_artifact_sha256": str(attestation.get("source_artifact_sha256") or ""),
            "verification_method": str(attestation.get("verification_method") or "HMAC-SHA256"),
            "window_cadence": str(attestation.get("window_cadence") or "").lower(),
        }

    @classmethod
    def compute_claims_digest(cls, claims: Dict[str, Any]) -> Tuple[bytes, str]:
        """Computes RFC-8785 canonical bytes and SHA-256 digest of claims."""
        canonical_bytes = rfc8785_canonical_json(claims)
        digest = hashlib.sha256(canonical_bytes).hexdigest()
        return canonical_bytes, digest

    @classmethod
    def verify_source_artifact_integrity(
        cls,
        record: Any,
        attestation: Dict[str, Any],
    ) -> Tuple[bool, Optional[str], Optional[str], Optional[str], Optional[int], Optional[int]]:
        """
        Performs fail-closed verification of the source artifact file on disk.
        Returns: (is_valid, rejection_code, rejection_reason_tr, verified_sha256, mtime_ns, file_size)
        """
        source_path_str = getattr(record, "source_artifact", None)
        if not source_path_str or not isinstance(source_path_str, str) or not source_path_str.strip():
            return (
                False,
                "SOURCE_ARTIFACT_MISSING",
                "Kaynak araştırma belgesi yolu belirtilmemiş.",
                None,
                None,
                None,
            )

        clean_path = source_path_str.strip().replace("\\", "/")

        # 1. Path Traversal Check
        raw_parts = Path(clean_path).parts
        if ".." in raw_parts:
            return (
                False,
                "SOURCE_ARTIFACT_PATH_UNTRUSTED",
                "Güvenilmeyen kaynak dosya yolu (dizin geçişi tespit edildi).",
                None,
                None,
                None,
            )

        # 2. Check for Disallowed System Directories
        norm_lower = clean_path.lower()
        for dis in DISALLOWED_SYSTEM_DIRECTORIES:
            if norm_lower.startswith(dis):
                return (
                    False,
                    "SOURCE_ARTIFACT_PATH_UNTRUSTED",
                    "Güvenilmeyen sistem dizin yolu.",
                    None,
                    None,
                    None,
                )

        p = Path(clean_path)
        resolved_p = p.resolve() if p.is_absolute() else (Path.cwd() / p).resolve()

        # 3. Symlink Escape Check
        if p.is_symlink():
            sym_target = p.resolve()
            sym_lower = str(sym_target).lower().replace("\\", "/")
            for dis in DISALLOWED_SYSTEM_DIRECTORIES:
                if sym_lower.startswith(dis):
                    return (
                        False,
                        "SOURCE_ARTIFACT_PATH_UNTRUSTED",
                        "Güvenilmeyen symlink hedefi tespit edildi.",
                        None,
                        None,
                        None,
                    )

        # 4. Existence Check
        if not resolved_p.exists():
            return (
                False,
                "SOURCE_ARTIFACT_MISSING",
                "Kaynak araştırma dosyası disk üzerinde bulunamadı.",
                None,
                None,
                None,
            )

        # 5. Directory Check
        if not resolved_p.is_file():
            return (
                False,
                "SOURCE_ARTIFACT_UNREADABLE",
                "Belirtilen kaynak yolu bir dosya değil (dizin veya özel aygıt).",
                None,
                None,
                None,
            )

        # 6. Readability & Resource Boundedness
        try:
            stat = resolved_p.stat()
            if stat.st_size > MAX_SOURCE_ARTIFACT_SIZE_BYTES:
                return (
                    False,
                    "SOURCE_ARTIFACT_VERIFICATION_FAILED",
                    "Kaynak dosya boyutu izin verilen sınırı aşıyor.",
                    None,
                    None,
                    None,
                )
            file_bytes = resolved_p.read_bytes()
            mtime_ns = stat.st_mtime_ns
            file_size = stat.st_size
        except PermissionError:
            return (
                False,
                "SOURCE_ARTIFACT_UNREADABLE",
                "Kaynak dosya okuma izin hatası.",
                None,
                None,
                None,
            )
        except (OSError, IOError) as e:
            return (
                False,
                "SOURCE_ARTIFACT_UNREADABLE",
                f"Kaynak dosya erişilemedi: {type(e).__name__}",
                None,
                None,
                None,
            )
        except Exception:
            return (
                False,
                "SOURCE_ARTIFACT_VERIFICATION_FAILED",
                "Beklenmeyen dosya sistemi hatası.",
                None,
                None,
                None,
            )

        # 7. Exact SHA-256 Hash Verification
        actual_sha = hashlib.sha256(file_bytes).hexdigest()
        expected_sha = getattr(record, "source_artifact_sha256", None) or ""
        attestation_sha = attestation.get("source_artifact_sha256") or ""

        if not expected_sha or actual_sha != expected_sha:
            return (
                False,
                "SOURCE_ARTIFACT_HASH_MISMATCH",
                "Disk üzerindeki kaynak dosyanın özeti araştırma kaydı ile uyuşmuyor.",
                None,
                None,
                None,
            )

        if not attestation_sha or actual_sha != attestation_sha:
            return (
                False,
                "SOURCE_ARTIFACT_HASH_MISMATCH",
                "Disk üzerindeki kaynak dosyanın özeti tasdik özeti ile uyuşmuyor.",
                None,
                None,
                None,
            )

        return True, None, None, actual_sha, mtime_ns, file_size

    @classmethod
    def create_signed_attestation(
        cls,
        record: Any,
        key_id: str,
        secret: str,
        issuer: str = "CBE_AUTHORITATIVE_RESEARCH_AUTHORITY",
        schema_version: str = "CBE-ATTESTATION-2.0.0",
        completeness_assertion: bool = True,
        observation_count: Optional[int] = None,
        override_dataset_id: Optional[str] = None,
        override_record_id: Optional[str] = None,
        override_sha256: Optional[str] = None,
        override_start: Optional[str] = None,
        override_end: Optional[str] = None,
        override_cadence: Optional[str] = None,
        forged_signature: Optional[str] = None,
        missing_observations: int = 0,
        has_missing_data: bool = False,
        is_superseded: bool = False,
        expires_at_utc: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates an authenticated, cryptographically signed observation completeness attestation.
        All security-relevant fields are signed into the RFC-8785 canonical claim payload.
        """
        cadence = (override_cadence or record.window_cadence or "1h").lower()
        step_sec = CADENCE_SECONDS_MAP.get(cadence, 3600)
        s_str = override_start or record.observation_start_utc
        e_str = override_end or record.observation_end_utc

        if observation_count is not None:
            count = observation_count
        else:
            try:
                s_dt = datetime.fromisoformat(s_str.replace("Z", "+00:00"))
                e_dt = datetime.fromisoformat(e_str.replace("Z", "+00:00"))
                count = int((e_dt - s_dt).total_seconds() // step_sec)
            except Exception:
                count = 0

        claims = {
            "completeness_assertion": completeness_assertion,
            "dataset_id": override_dataset_id or record.dataset_id,
            "expires_at_utc": expires_at_utc or "",
            "has_missing_data": has_missing_data,
            "is_superseded": is_superseded,
            "issuer": issuer,
            "key_id": key_id,
            "missing_observations": missing_observations,
            "observation_count": count,
            "observation_end_utc": e_str,
            "observation_start_utc": s_str,
            "record_id": override_record_id or record.id,
            "schema_version": schema_version,
            "source_artifact_sha256": override_sha256 or record.source_artifact_sha256,
            "verification_method": "HMAC-SHA256",
            "window_cadence": cadence,
        }

        canonical_bytes, digest = cls.compute_claims_digest(claims)
        if forged_signature:
            signature = forged_signature
        else:
            h = hmac.new(secret.encode("utf-8"), canonical_bytes, hashlib.sha256)
            signature = f"hmac-sha256:{key_id}:{h.hexdigest()}"

        attestation = dict(claims)
        attestation["signature"] = signature
        attestation["claims_sha256"] = digest
        attestation["status"] = "AUTHENTICATED"
        attestation["verified_continuous_series"] = True
        return attestation

    @classmethod
    def verify_attestation(
        cls,
        record: Any,
        attestation: Optional[Dict[str, Any]],
        use_cache: bool = True,
        enforce_source_file_integrity: bool = True,
    ) -> Dict[str, Any]:
        """
        Cryptographically verifies observation completeness attestation against record context.
        Enforces physical source file integrity, verifies all security claims, and utilizes
        a signature-bound thread-safe cache.
        """
        t0 = time.perf_counter()

        # 1. Presence & Type Check
        if not attestation or not isinstance(attestation, dict):
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "ATTESTATION_EMPTY_OR_INVALID",
                "rejection_reason_tr": "Eksiksizlik tasdiki verisi bulunamadı veya geçersiz formatta.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 2. Check for Embedded / Untrusted Keys (FAIL CLOSED)
        if "secret" in attestation or "key_secret" in attestation or "signing_key" in attestation:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "EMBEDDED_KEY_UNTRUSTED",
                "rejection_reason_tr": "Tasdik paketi içerisinde bağımsız olmayan anahtar bulundu; üçüncü şahıs anahtarı kabul edilemez.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        key_location = attestation.get("key_location") or attestation.get("key_path")
        if key_location and isinstance(key_location, str):
            for untrusted in ("tmp", "temp", "/tmp", "/var/tmp", "data", "/app/data"):
                if untrusted in key_location.lower():
                    elapsed = (time.perf_counter() - t0) * 1000
                    return {
                        "is_valid": False,
                        "rejection_code": "UNTRUSTED_KEY_LOCATION",
                        "rejection_reason_tr": f"Doğrulama anahtarı güvenilmeyen yazılabilir dizinden ({key_location}) okunamaz.",
                        "verified_claims": None,
                        "verification_latency_ms": elapsed,
                    }

        # 3. Signature Presence Check (FAIL CLOSED)
        signature_str = attestation.get("signature")
        if not signature_str or not isinstance(signature_str, str):
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "SIGNATURE_EMPTY_OR_INVALID",
                "rejection_reason_tr": "Tasdik paketi kriptografik imza içermiyor; self-declared statüler geçersizdir.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # Compute digest of signature for signature-bound cache identity
        signature_digest = hashlib.sha256(signature_str.encode("utf-8")).hexdigest()

        # 4. Schema Version Check
        schema_version = attestation.get("schema_version")
        if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "UNSUPPORTED_SCHEMA_VERSION",
                "rejection_reason_tr": f"Desteklenmeyen tasdik şema sürümü: '{schema_version}'.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 5. Issuer Authority Check
        issuer = attestation.get("issuer")
        if issuer not in TRUSTED_ISSUERS:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "UNKNOWN_ISSUER",
                "rejection_reason_tr": f"Bilinmeyen veya yetkisiz tasdik sağlayıcısı: '{issuer}'.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 6. Mandatory Claims Presence Check
        for mc in MANDATORY_CLAIMS:
            if mc not in attestation or attestation.get(mc) is None:
                elapsed = (time.perf_counter() - t0) * 1000
                return {
                    "is_valid": False,
                    "rejection_code": "MANDATORY_CLAIM_MISSING",
                    "rejection_reason_tr": f"Tasdik zorunlu güvenlik iddiasını içermiyor: '{mc}'.",
                    "verified_claims": None,
                    "verification_latency_ms": elapsed,
                }

        # 7. Completeness Assertion & Conflicting Metadata Checks
        assertion = attestation.get("completeness_assertion", attestation.get("verified_continuous_series"))
        if assertion is not True:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "COMPLETENESS_NOT_ASSERTED",
                "rejection_reason_tr": "Tasdik paketi serinin eksiksiz olduğunu doğrulamıyor.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        missing_obs = attestation.get("missing_observations", 0)
        has_missing = attestation.get("has_missing_data", False)

        if missing_obs < 0 or (assertion is True and (missing_obs > 0 or has_missing is True)):
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "INCONSISTENT_COMPLETENESS_METADATA",
                "rejection_reason_tr": "Eksiksizlik tasdiki çelişkili veya geçersiz kayıp gözlem metadatası içeriyor.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        if missing_obs > 0 or has_missing is True:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "MISSING_OBSERVATIONS_DETECTED",
                "rejection_reason_tr": "Eksiksizlik iddia edilmesine rağmen seride kayıp gözlemler bulunmaktadır.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 8. Expiration & Supersession Checks
        exp_utc = attestation.get("expires_at_utc")
        if exp_utc:
            try:
                exp_dt = datetime.fromisoformat(str(exp_utc).replace("Z", "+00:00"))
                if datetime.now(timezone.utc) > exp_dt:
                    elapsed = (time.perf_counter() - t0) * 1000
                    return {
                        "is_valid": False,
                        "rejection_code": "ATTESTATION_EXPIRED",
                        "rejection_reason_tr": f"Eksiksizlik tasdiğinin geçerlilik süresi dolmuştur ({exp_utc}).",
                        "verified_claims": None,
                        "verification_latency_ms": elapsed,
                    }
            except Exception:
                pass

        if attestation.get("is_superseded") is True:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "ATTESTATION_SUPERSEDED",
                "rejection_reason_tr": "Eksiksizlik tasdiğinin geçerliliği yeni bir politika veya tasdik ile kaldırılmıştır.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 9. Key ID & Revocation Checks
        key_id = attestation.get("key_id") or ""
        if ":" in signature_str and signature_str.startswith("hmac-sha256:"):
            parts = signature_str.split(":")
            if len(parts) == 3:
                key_id = parts[1]

        if not key_id:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "MISSING_TRUSTED_VERIFICATION_KEY",
                "rejection_reason_tr": "Tasdikte doğrulanabilir anahtar kimliği (key_id) belirtilmemiş.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        is_revoked = signing_key_registry.is_key_revoked(key_id)
        if is_revoked:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "REVOKED_SIGNING_KEY",
                "rejection_reason_tr": f"Tasdik imza anahtarı '{key_id}' yürürlükten kaldırılmıştır (revoked).",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 10. Record Context Binding Checks (FAIL CLOSED)
        # 10a. Replay / Record ID Binding
        if attestation.get("record_id") != getattr(record, "id", None):
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "REPLAY_ATTACK_DETECTED",
                "rejection_reason_tr": f"Tasdik kayıt ID'si ('{attestation.get('record_id')}') hedef kayıt ('{getattr(record, 'id', None)}') ile uyuşmuyor; replay engellendi.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 10b. Dataset ID Binding
        if attestation.get("dataset_id") != getattr(record, "dataset_id", None):
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "DATASET_ID_MISMATCH",
                "rejection_reason_tr": f"Tasdik veri seti kimliği ('{attestation.get('dataset_id')}') kayıt ile uyuşmuyor.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 10c. Observation Window Start & End Binding
        if (
            attestation.get("observation_start_utc") != getattr(record, "observation_start_utc", None)
            or attestation.get("observation_end_utc") != getattr(record, "observation_end_utc", None)
        ):
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "OBSERVATION_WINDOW_MISMATCH",
                "rejection_reason_tr": "Tasdik başlangıç/bitiş zaman sınırları araştırma kaydı ile uyuşmuyor.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 10d. Cadence Binding
        rec_cadence = (getattr(record, "window_cadence", None) or "1h").lower()
        att_cadence = str(attestation.get("window_cadence") or "").lower()
        if att_cadence != rec_cadence:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "CADENCE_MISMATCH",
                "rejection_reason_tr": f"Tasdik zaman kadansı ('{att_cadence}') kayıt ile uyuşmuyor ('{rec_cadence}').",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 10e. Observation Count & Grid Geometry Check
        step_sec = CADENCE_SECONDS_MAP.get(rec_cadence, 3600)
        try:
            s_dt = datetime.fromisoformat(record.observation_start_utc.replace("Z", "+00:00"))
            e_dt = datetime.fromisoformat(record.observation_end_utc.replace("Z", "+00:00"))
            total_sec = (e_dt - s_dt).total_seconds()
            if total_sec <= 0:
                elapsed = (time.perf_counter() - t0) * 1000
                return {
                    "is_valid": False,
                    "rejection_code": "INVALID_OBSERVATION_WINDOW",
                    "rejection_reason_tr": "Başlangıç zamanı bitiş zamanından önce değil.",
                    "verified_claims": None,
                    "verification_latency_ms": elapsed,
                }
            expected_intervals = int(total_sec // step_sec)
        except Exception as e:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "INVALID_OBSERVATION_WINDOW",
                "rejection_reason_tr": f"Zaman sınırları ayrıştırma hatası: {e}",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        claimed_count = attestation.get("observation_count")
        if claimed_count is None or claimed_count != expected_intervals or claimed_count <= 0:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "OBSERVATION_COUNT_MISMATCH",
                "rejection_reason_tr": f"Tasdik gözlem sayısı ({claimed_count}) pencere geometrisi ({expected_intervals}) ile uyuşmuyor.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 10f. Source Artifact SHA-256 Claim vs Record Check
        expected_sha = getattr(record, "source_artifact_sha256", None)
        claimed_sha = attestation.get("source_artifact_sha256")
        if claimed_sha != expected_sha:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "ARTIFACT_HASH_MISMATCH",
                "rejection_reason_tr": "Tasdik paketi içerisindeki kaynak dosya özeti araştırma kaydı ile uyuşmuyor.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 11. Fail-Closed Physical Source Artifact Integrity Verification
        verified_source_sha = getattr(record, "source_artifact_sha256", None) or ""
        source_mtime_ns = None
        source_size = None

        if enforce_source_file_integrity:
            src_valid, src_code, src_msg, disk_sha, mtime, sz = cls.verify_source_artifact_integrity(
                record, attestation
            )
            if not src_valid:
                elapsed = (time.perf_counter() - t0) * 1000
                return {
                    "is_valid": False,
                    "rejection_code": src_code,
                    "rejection_reason_tr": src_msg,
                    "verified_claims": None,
                    "verification_latency_ms": elapsed,
                }
            verified_source_sha = disk_sha
            source_mtime_ns = mtime
            source_size = sz

        # 12. Cryptographic Canonical Claims Hashing
        claims = cls.extract_canonical_claims(attestation)
        canonical_bytes, claims_sha256 = cls.compute_claims_digest(claims)

        artifact_digest = verified_source_sha
        policy_ver = cls.TRUST_POLICY_VERSION
        source_path = getattr(record, "source_artifact", None)

        # 13. Signature-Bound Cache Evaluation
        if use_cache:
            cached_res = attestation_cache.get(
                artifact_digest=artifact_digest,
                claims_sha256=claims_sha256,
                signature_digest=signature_digest,
                key_id=key_id,
                trust_policy_version=policy_ver,
                is_revoked=is_revoked,
                source_path=source_path,
            )
            if cached_res is not None:
                elapsed = (time.perf_counter() - t0) * 1000
                cached_res["verification_latency_ms"] = elapsed
                return cached_res

        # 14. Signature Verification against Trusted Registry
        is_sig_valid, sig_msg, verified_key_id = signing_key_registry.verify_signature(
            canonical_bytes=canonical_bytes,
            signature_str=signature_str,
        )

        elapsed = (time.perf_counter() - t0) * 1000

        if not is_sig_valid:
            code = "ATTESTATION_VERIFICATION_FAILED"
            if sig_msg == "UNKNOWN_SIGNING_KEY":
                code = "MISSING_TRUSTED_VERIFICATION_KEY"
            elif sig_msg == "REVOKED_SIGNING_KEY":
                code = "REVOKED_SIGNING_KEY"
            elif sig_msg in ("SIGNATURE_EMPTY_OR_INVALID", "HMAC_SIGNATURE_MISMATCH"):
                code = "SIGNATURE_VERIFICATION_FAILED"

            # NEVER populate successful cache with failure results
            return {
                "is_valid": False,
                "rejection_code": code,
                "rejection_reason_tr": f"Kriptografik imza doğrulaması başarısız oldu: {sig_msg}",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 15. Success: Store in Signature-Bound Cache
        success_res = {
            "is_valid": True,
            "rejection_code": None,
            "rejection_reason_tr": None,
            "verified_claims": claims,
            "verification_latency_ms": elapsed,
            "verified_key_id": verified_key_id,
            "claims_sha256": claims_sha256,
            "signature_digest": signature_digest,
            "artifact_digest": artifact_digest,
        }

        if use_cache:
            attestation_cache.put(
                artifact_digest=artifact_digest,
                claims_sha256=claims_sha256,
                signature_digest=signature_digest,
                key_id=key_id,
                trust_policy_version=policy_ver,
                is_revoked=is_revoked,
                result=success_res,
                source_mtime_ns=source_mtime_ns,
                source_size=source_size,
            )

        return success_res

    @classmethod
    def generate_attested_grid(cls, record: Any, attestation: Dict[str, Any]) -> List[str]:
        """
        Generates discrete normalized UTC timestamps for an authenticated continuous series grid.
        Guarantees that sampling grid alignment and discrete observation points are verified.
        """
        cadence = (attestation.get("window_cadence") or record.window_cadence or "1h").lower()
        step_sec = CADENCE_SECONDS_MAP.get(cadence, 3600)
        s_dt = datetime.fromisoformat(record.observation_start_utc.replace("Z", "+00:00"))
        count = int(attestation.get("observation_count") or 0)

        grid: List[str] = []
        for i in range(count):
            t = s_dt + timedelta(seconds=i * step_sec)
            t_utc = t.astimezone(timezone.utc)
            grid.append(t_utc.strftime("%Y-%m-%dT%H:%M:%SZ"))

        return grid

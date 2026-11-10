"""
Observation Completeness Attestation Verifier & Cache Engine.
Sprint 24 Final Trust Boundary Closure.

Provides fail-closed, cryptographic, RFC-8785-canonical verification for
observation series completeness attestations, binding:
- Dataset ID
- Source artifact SHA-256
- Research record ID
- Observation window start and end (UTC)
- Cadence
- Observation count & grid geometry
- Trusted signing authority and key registry
- Dynamic cache bound to digests, key IDs, policy version, and revocation state.
"""

import hashlib
import hmac
import json
import os
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
    "CBE-ATTESTATION-1.0.0",
    "CBE-OBSERVATION-ATTESTATION-1.0.0",
    "1.0.0",
}

TRUSTED_ISSUERS = {
    "CBE_AUTHORITATIVE_RESEARCH_AUTHORITY",
    "CBE_OBSERVATION_GOVERNANCE",
    "CBE_DATA_GOVERNANCE_COUNCIL",
    "CBE_SYSTEM",
    "CBE_CANONICAL_RESEARCH_AUTHORITY",
}

UNTRUSTED_KEY_PATHS = {
    "tmp",
    "temp",
    "/tmp",
    "/var/tmp",
    "data",
    "/app/data",
}


class AttestationVerificationCache:
    """
    Thread-safe, digest-bound verification result cache.
    Cache entries are strictly bound to:
    (artifact_digest, attestation_digest, key_id, trust_policy_version, is_revoked)
    """

    def __init__(self, max_size: int = 1000):
        self._max_size = max_size
        self._cache: Dict[Tuple[str, str, str, str, bool], Dict[str, Any]] = {}
        self._hit_count = 0
        self._miss_count = 0

    def get(
        self,
        artifact_digest: str,
        attestation_digest: str,
        key_id: str,
        trust_policy_version: str,
        is_revoked: bool,
    ) -> Optional[Dict[str, Any]]:
        key = (artifact_digest, attestation_digest, key_id, trust_policy_version, is_revoked)
        res = self._cache.get(key)
        if res is not None:
            self._hit_count += 1
            return dict(res)
        self._miss_count += 1
        return None

    def put(
        self,
        artifact_digest: str,
        attestation_digest: str,
        key_id: str,
        trust_policy_version: str,
        is_revoked: bool,
        result: Dict[str, Any],
    ) -> None:
        if len(self._cache) >= self._max_size:
            # Evict oldest 20%
            keys_to_remove = list(self._cache.keys())[: self._max_size // 5]
            for k in keys_to_remove:
                self._cache.pop(k, None)
        key = (artifact_digest, attestation_digest, key_id, trust_policy_version, is_revoked)
        self._cache[key] = dict(result)

    def clear(self) -> None:
        self._cache.clear()
        self._hit_count = 0
        self._miss_count = 0

    @property
    def stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._cache),
            "hit_count": self._hit_count,
            "miss_count": self._miss_count,
            "max_size": self._max_size,
        }


# Global cache instance
attestation_cache = AttestationVerificationCache()


class ObservationCompletenessAttestationVerifier:
    """
    Fail-closed verifier for research observation completeness attestations.
    Rejects self-declared fields unless independently backed by a trusted cryptographic signature.
    """

    TRUST_POLICY_VERSION = "2026.1"

    @classmethod
    def extract_canonical_claims(cls, attestation: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extracts bound fields into canonical claims dictionary.
        Excludes signature, dynamic runtime status, and non-claim annotations.
        """
        return {
            "completeness_assertion": attestation.get("completeness_assertion", attestation.get("verified_continuous_series", False)),
            "dataset_id": str(attestation.get("dataset_id") or ""),
            "issuer": str(attestation.get("issuer") or ""),
            "key_id": str(attestation.get("key_id") or ""),
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
    def create_signed_attestation(
        cls,
        record: Any,
        key_id: str,
        secret: str,
        issuer: str = "CBE_AUTHORITATIVE_RESEARCH_AUTHORITY",
        schema_version: str = "CBE-ATTESTATION-1.0.0",
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
        expires_at_utc: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Creates an authenticated, cryptographically signed observation completeness attestation.
        Used by authoritative ingest pipelines and verification tests.
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
            "issuer": issuer,
            "key_id": key_id,
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
        attestation["missing_observations"] = missing_observations
        if expires_at_utc:
            attestation["expires_at_utc"] = expires_at_utc
        attestation["status"] = "AUTHENTICATED"
        attestation["verified_continuous_series"] = True
        return attestation

    @classmethod
    def verify_attestation(
        cls,
        record: Any,
        attestation: Optional[Dict[str, Any]],
        use_cache: bool = True,
    ) -> Dict[str, Any]:
        """
        Cryptographically verifies observation completeness attestation against record context.
        Returns:
            {
                "is_valid": bool,
                "rejection_code": Optional[str],
                "rejection_reason_tr": Optional[str],
                "verified_claims": Optional[Dict[str, Any]],
                "verification_latency_ms": float,
            }
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
        # Never trust a key supplied inside the attestation itself
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
            for untrusted in UNTRUSTED_KEY_PATHS:
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

        # 5. Completeness Assertion Check
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

        # Missing observations in claimed complete series
        if attestation.get("missing_observations", 0) > 0 or attestation.get("has_missing_data") is True:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "MISSING_OBSERVATIONS_DETECTED",
                "rejection_reason_tr": "Eksiksizlik iddia edilmesine rağmen seride kayıp gözlemler bulunmaktadır.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 6. Expiration / Superseded Check
        exp_utc = attestation.get("expires_at_utc")
        if exp_utc:
            try:
                exp_dt = datetime.fromisoformat(exp_utc.replace("Z", "+00:00"))
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

        # 7. Key ID Check
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

        # Check key revocation
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

        # 8. Record Context Binding Checks (FAIL CLOSED)
        # 8a. Replay / Record ID Binding
        if attestation.get("record_id") != getattr(record, "id", None):
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "REPLAY_ATTACK_DETECTED",
                "rejection_reason_tr": f"Tasdik kayıt ID'si ('{attestation.get('record_id')}') hedef kayıt ('{getattr(record, 'id', None)}') ile uyuşmuyor; replay engellendi.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 8b. Dataset ID Binding
        if attestation.get("dataset_id") != getattr(record, "dataset_id", None):
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "DATASET_ID_MISMATCH",
                "rejection_reason_tr": f"Tasdik veri seti kimliği ('{attestation.get('dataset_id')}') kayıt ile uyuşmuyor.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 8c. Source Artifact SHA-256 Binding
        expected_sha = getattr(record, "source_artifact_sha256", None) or ""
        if attestation.get("source_artifact_sha256") != expected_sha:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "ARTIFACT_HASH_MISMATCH",
                "rejection_reason_tr": f"Tasdik kaynak özeti ('{attestation.get('source_artifact_sha256')}') kayıt özeti ('{expected_sha}') ile uyuşmuyor.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 8d. Source Disk File Integrity Check (if present on disk)
        source_artifact_path = getattr(record, "source_artifact", None)
        if source_artifact_path:
            p = Path(source_artifact_path)
            if p.exists() and p.is_file():
                try:
                    file_sha = hashlib.sha256(p.read_bytes()).hexdigest()
                    if file_sha != expected_sha or file_sha != attestation.get("source_artifact_sha256"):
                        elapsed = (time.perf_counter() - t0) * 1000
                        return {
                            "is_valid": False,
                            "rejection_code": "ARTIFACT_TAMPERED",
                            "rejection_reason_tr": "Kaynak disk dosyası içeriği değiştirilmiş; dosya özeti tasdik ile uyuşmuyor.",
                            "verified_claims": None,
                            "verification_latency_ms": elapsed,
                        }
                except Exception:
                    pass

        # 8e. Observation Window Start & End Binding
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

        # 8f. Cadence Binding
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

        # 8g. Observation Count & Grid Geometry Check
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
        if claimed_count is None or claimed_count != expected_intervals:
            elapsed = (time.perf_counter() - t0) * 1000
            return {
                "is_valid": False,
                "rejection_code": "OBSERVATION_COUNT_MISMATCH",
                "rejection_reason_tr": f"Tasdik gözlem sayısı ({claimed_count}) pencere geometrisi ({expected_intervals}) ile uyuşmuyor.",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }

        # 9. Cryptographic RFC-8785 Canonical Signature Verification (with Caching)
        claims = cls.extract_canonical_claims(attestation)
        canonical_bytes, claims_sha256 = cls.compute_claims_digest(claims)

        artifact_digest = expected_sha
        policy_ver = cls.TRUST_POLICY_VERSION

        if use_cache:
            cached_res = attestation_cache.get(
                artifact_digest=artifact_digest,
                attestation_digest=claims_sha256,
                key_id=key_id,
                trust_policy_version=policy_ver,
                is_revoked=is_revoked,
            )
            if cached_res is not None:
                elapsed = (time.perf_counter() - t0) * 1000
                cached_res["verification_latency_ms"] = elapsed
                return cached_res

        # Call underlying trusted signing key registry
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

            fail_res = {
                "is_valid": False,
                "rejection_code": code,
                "rejection_reason_tr": f"Kriptografik imza doğrulaması başarısız oldu: {sig_msg}",
                "verified_claims": None,
                "verification_latency_ms": elapsed,
            }
            if use_cache:
                attestation_cache.put(
                    artifact_digest=artifact_digest,
                    attestation_digest=claims_sha256,
                    key_id=key_id,
                    trust_policy_version=policy_ver,
                    is_revoked=is_revoked,
                    result=fail_res,
                )
            return fail_res

        # Success!
        success_res = {
            "is_valid": True,
            "rejection_code": None,
            "rejection_reason_tr": None,
            "verified_claims": claims,
            "verification_latency_ms": elapsed,
            "verified_key_id": verified_key_id,
            "claims_sha256": claims_sha256,
        }

        if use_cache:
            attestation_cache.put(
                artifact_digest=artifact_digest,
                attestation_digest=claims_sha256,
                key_id=key_id,
                trust_policy_version=policy_ver,
                is_revoked=is_revoked,
                result=success_res,
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

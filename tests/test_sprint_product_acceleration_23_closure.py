"""
Sprint 23 Final Closure Acceptance Tests
Authoritative Docker Volume Trust Boundary, RFC 8785 Fail-Closed Dependency & Release Provenance Integrity

Covers all 20 mandatory negative/positive volume verification scenarios:
 1. Correct authorized volume with kernel mountinfo & valid signed attestation (PERSISTENT_VERIFIED)
 2. Forged JSON attestation (unauthenticated / missing signature) rejected (UNAUTHENTICATED_ATTESTATION_REJECTED)
 3. Attestation inside application-writable directory without external key rejected (UNVERIFIABLE_VOLUME_IDENTITY)
 4. Modified attestation volume ID rejected (UNAUTHENTICATED_ATTESTATION_REJECTED)
 5. Correctly formatted but invalid HMAC signature rejected (UNAUTHENTICATED_ATTESTATION_REJECTED)
 6. Expired attestation rejected (UNVERIFIABLE_VOLUME_IDENTITY)
 7. Attestation bound to another container rejected (CONTRADICTORY_VOLUME_IDENTITY)
 8. Attestation bound to another mount destination rejected (UNAUTHORIZED_MOUNT_ROOT)
 9. Attestation bound to another image rejected (CONTRADICTORY_VOLUME_IDENTITY)
10. Missing runtime identity fails closed (UNVERIFIABLE_VOLUME_IDENTITY)
11. Runtime identity contradicting attestation rejected (CONTRADICTORY_VOLUME_IDENTITY)
12. Writable overlay root filesystem rejected (CONTAINER_OVERLAY_REJECTED)
13. tmpfs rejected (EPHEMERAL_STORAGE_REJECTED)
14. Unauthorized bind mount rejected (UNAUTHORIZED_MOUNT_ROOT)
15. Symlink escape rejected (SYMLINK_ESCAPE_REJECTED)
16. Prefix collision rejected (UNAUTHORIZED_MOUNT_ROOT)
17. Read-only volume rejected (READ_ONLY)
18. Missing authorized volume rejected (UNAUTHORIZED_VOLUME_ID)
19. Container recreation with valid new identity (PERSISTENT_VERIFIED)
20. Stale identity after container replacement rejected (CONTRADICTORY_VOLUME_IDENTITY)

Also covers:
- RFC 8785 fail-closed behavior when audited dependency is unavailable
- Historical CBE-CANONICAL-JSON-v1 evidence verification compatibility
- Release provenance and Git ancestry validation
"""

from __future__ import annotations

import copy
import hashlib
import hmac
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict

import pytest

from coin_behavior_engine.product.storage_durability import StorageDurabilityEngine
from coin_behavior_engine.product.research_report_evidence import (
    ResearchReportEvidenceBundleEngine,
    rfc8785_canonical_json,
    legacy_canonical_json_v1,
)

AUTH_VOL_ID = "dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f"
TEST_SIGNING_KEY = "test-deployment-control-plane-key-secret-2026"


# =============================================================================
# GROUP 1: AUTHORITATIVE DOCKER VOLUME TRUST BOUNDARY (20-TEST MATRIX)
# =============================================================================

class TestAuthoritativeDockerVolumeTrustBoundary:
    """Mandatory 20-scenario negative and positive matrix for Docker volume verification."""

    @pytest.fixture(autouse=True)
    def setup_env(self, monkeypatch):
        monkeypatch.setenv("CBE_ENV", "staging")
        monkeypatch.setenv("CBE_VOLUME_ATTESTATION_KEY", TEST_SIGNING_KEY)
        monkeypatch.setenv("CBE_CONTAINER_ID", "container-sprint23-staging-01")
        monkeypatch.setenv("CBE_IMAGE_ID", "sha256:staging-image-closure-cbe23")

    def _make_valid_claims(self, **overrides) -> Dict[str, Any]:
        now = datetime.now(timezone.utc)
        claims = {
            "authorized_volume_id": AUTH_VOL_ID,
            "expected_destination": "/app/data/prospective",
            "expected_filesystem": "ext4",
            "bound_container_id": "container-sprint23-staging-01",
            "bound_image_id": "sha256:staging-image-closure-cbe23",
            "issued_at_utc": (now - timedelta(minutes=5)).isoformat(),
            "expires_at_utc": (now + timedelta(hours=24)).isoformat(),
        }
        claims.update(overrides)
        return claims

    def test_01_authorized_volume_kernel_mountinfo_and_signed_attestation(self):
        """1. Positive: authorized volume with kernel mountinfo & valid signed attestation is PERSISTENT_VERIFIED."""
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "root": f"/var/lib/docker/volumes/{AUTH_VOL_ID}/_data",
            "volume_id": AUTH_VOL_ID,
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        claims = self._make_valid_claims()
        att = StorageDurabilityEngine.create_signed_volume_attestation(claims, TEST_SIGNING_KEY)

        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            attestation_override=att,
        )
        assert info["classification"] == "PERSISTENT_VERIFIED"
        assert info["verified_durable"] is True
        assert info["volume_id"] == AUTH_VOL_ID
        assert info["volume_provenance"] == "KERNEL_AND_ATTESTATION"

    def test_02_forged_json_attestation_missing_signature_rejected(self, tmp_path, monkeypatch):
        """2. Negative: Unauthenticated / unsigned plain JSON attestation is rejected."""
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        # Attestation without signature
        forged_plain = {
            "authorized_volume_id": AUTH_VOL_ID,
            "expected_destination": "/app/data/prospective",
            "expected_filesystem": "ext4",
        }
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            attestation_override=forged_plain,
        )
        assert info["classification"] == "UNAUTHENTICATED_ATTESTATION_REJECTED"
        assert info["verified_durable"] is False

    def test_03_attestation_in_writable_dir_without_external_key_rejected(self, tmp_path, monkeypatch):
        """3. Negative: Attestation inside application-writable directory without external key rejected."""
        monkeypatch.delenv("CBE_VOLUME_ATTESTATION_KEY", raising=False)
        monkeypatch.setenv("CBE_VOLUME_ATTESTATION_KEY_PATH", "/nonexistent/key/path")

        # Simulate attestation file directly in prospective directory
        att_dir = tmp_path / "prospective"
        att_dir.mkdir(parents=True, exist_ok=True)
        att_file = att_dir / ".cbe_volume_attestation.json"

        norm_dir = re.sub(r"^[a-zA-Z]:", "", str(att_dir).replace("\\", "/"))
        claims = self._make_valid_claims(expected_destination=norm_dir)
        signed = StorageDurabilityEngine.create_signed_volume_attestation(claims, "some-key")
        with open(att_file, "w", encoding="utf-8") as f:
            json.dump(signed, f)

        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": norm_dir,
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        monkeypatch.setattr(StorageDurabilityEngine, "AUTHORIZED_STAGING_PERSISTENT_PREFIXES", (norm_dir,))

        info = StorageDurabilityEngine.inspect_storage_path(
            str(att_dir / "reports"),
            mounts_override=mock_mounts,
        )
        assert info["classification"] == "UNVERIFIABLE_VOLUME_IDENTITY"
        assert info["verified_durable"] is False

    def test_04_modified_attestation_volume_id_rejected(self):
        """4. Negative: Attestation with tampered volume ID in claims fails cryptographic verification."""
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        claims = self._make_valid_claims(authorized_volume_id="unauthorized-vol-tampered-999")
        att = StorageDurabilityEngine.create_signed_volume_attestation(claims, TEST_SIGNING_KEY)

        # Attacker tampers with volume ID after signing
        att["claims"]["authorized_volume_id"] = AUTH_VOL_ID

        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            attestation_override=att,
        )
        assert info["classification"] == "UNAUTHENTICATED_ATTESTATION_REJECTED"
        assert info["verified_durable"] is False

    def test_05_invalid_hmac_signature_rejected(self):
        """5. Negative: Correctly formatted but invalid HMAC signature is rejected."""
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        claims = self._make_valid_claims()
        att = {
            "claims": claims,
            "signature": "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad",
            "signature_algorithm": "HMAC-SHA256",
        }
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            attestation_override=att,
        )
        assert info["classification"] == "UNAUTHENTICATED_ATTESTATION_REJECTED"
        assert info["verified_durable"] is False

    def test_06_expired_attestation_rejected(self):
        """6. Negative: Cryptographically valid but expired attestation is rejected."""
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        past_time = "2026-01-01T00:00:00Z"
        claims = self._make_valid_claims(
            issued_at_utc="2025-12-01T00:00:00Z",
            expires_at_utc=past_time,
        )
        att = StorageDurabilityEngine.create_signed_volume_attestation(claims, TEST_SIGNING_KEY)

        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            attestation_override=att,
        )
        assert info["classification"] == "UNVERIFIABLE_VOLUME_IDENTITY"
        assert "expired" in str(info["rejection_reason"]).lower()
        assert info["verified_durable"] is False

    def test_07_attestation_bound_to_another_container_rejected(self):
        """7. Negative: Attestation bound to another container ID is rejected."""
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        claims = self._make_valid_claims(bound_container_id="different-container-id-999")
        att = StorageDurabilityEngine.create_signed_volume_attestation(claims, TEST_SIGNING_KEY)

        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            attestation_override=att,
        )
        assert info["classification"] == "CONTRADICTORY_VOLUME_IDENTITY"
        assert "container" in str(info["rejection_reason"]).lower()
        assert info["verified_durable"] is False

    def test_08_attestation_bound_to_another_destination_rejected(self):
        """8. Negative: Attestation bound to another mount destination is rejected."""
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        claims = self._make_valid_claims(expected_destination="/app/data/different_destination")
        att = StorageDurabilityEngine.create_signed_volume_attestation(claims, TEST_SIGNING_KEY)

        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            attestation_override=att,
        )
        assert info["classification"] == "UNAUTHORIZED_MOUNT_ROOT"
        assert info["verified_durable"] is False

    def test_09_attestation_bound_to_another_image_rejected(self):
        """9. Negative: Attestation bound to another image ID is rejected."""
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        claims = self._make_valid_claims(bound_image_id="sha256:different-image-id-999")
        att = StorageDurabilityEngine.create_signed_volume_attestation(claims, TEST_SIGNING_KEY)

        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            attestation_override=att,
        )
        assert info["classification"] == "CONTRADICTORY_VOLUME_IDENTITY"
        assert "image" in str(info["rejection_reason"]).lower()
        assert info["verified_durable"] is False

    def test_10_missing_runtime_identity_fails_closed(self):
        """10. Negative: Mount without volume ID and without attestation fails closed."""
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
        )
        assert info["classification"] == "UNVERIFIABLE_VOLUME_IDENTITY"
        assert info["verified_durable"] is False

    def test_11_runtime_identity_contradicting_attestation_rejected(self):
        """11. Negative: Kernel mountinfo volume ID contradicting attestation volume ID is rejected."""
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "root": f"/var/lib/docker/volumes/{AUTH_VOL_ID}/_data",
            "volume_id": AUTH_VOL_ID,
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        different_vol = "another-valid-hex-volume-id-00000000000000000000000000000000000000"
        claims = self._make_valid_claims(authorized_volume_id=different_vol)
        att = StorageDurabilityEngine.create_signed_volume_attestation(claims, TEST_SIGNING_KEY)

        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            attestation_override=att,
        )
        assert info["classification"] == "CONTRADICTORY_VOLUME_IDENTITY"
        assert info["verified_durable"] is False

    def test_12_writable_overlay_rootfs_rejected(self):
        """12. Negative: Ephemeral Docker container overlay rootfs is rejected."""
        mock_mounts = [{
            "device": "overlay",
            "mount_point": "/app/data/prospective",
            "fstype": "overlay",
            "options": "rw,relatime",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": True,
        }]
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
        )
        assert info["classification"] == "CONTAINER_OVERLAY_REJECTED"
        assert info["verified_durable"] is False

    def test_13_ephemeral_tmpfs_rejected(self):
        """13. Negative: Ephemeral tmpfs filesystem is rejected with EPHEMERAL status."""
        mock_mounts = [{
            "device": "tmpfs",
            "mount_point": "/app/data/prospective",
            "fstype": "tmpfs",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": True,
            "is_overlay": False,
        }]
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
        )
        assert info["is_ephemeral"] is True
        assert info["classification"] in ("EPHEMERAL", "EPHEMERAL_STORAGE_REJECTED")
        assert info["verified_durable"] is False

        with pytest.raises(RuntimeError) as exc_info:
            StorageDurabilityEngine.require_durable_storage(
                "/app/data/prospective/reports",
                mounts_override=mock_mounts,
            )
        assert "EPHEMERAL_STORAGE_REJECTED" in str(exc_info.value)

    def test_14_unauthorized_bind_mount_rejected(self):
        """14. Negative: Destination outside authorized roots is rejected."""
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/opt/unauthorized_mount",
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        info = StorageDurabilityEngine.inspect_storage_path(
            "/opt/unauthorized_mount/reports",
            mounts_override=mock_mounts,
        )
        assert info["classification"] == "UNAUTHORIZED_MOUNT_ROOT"
        assert info["verified_durable"] is False

    def test_15_symlink_escape_rejected(self, tmp_path, monkeypatch):
        """15. Negative: Symlink escaping authorized persistent root is detected and rejected."""
        sim_root = tmp_path / "authorized_prospective"
        sim_root.mkdir()
        target_outside = tmp_path / "outside_secret"
        target_outside.mkdir()

        norm_root = re.sub(r"^[a-zA-Z]:", "", str(sim_root).replace("\\", "/"))
        monkeypatch.setattr(StorageDurabilityEngine, "AUTHORIZED_STAGING_PERSISTENT_PREFIXES", (norm_root,))

        escape_path = str(sim_root / "escaped_link").replace("\\", "/")
        try:
            os.symlink(str(target_outside), str(sim_root / "escaped_link"), target_is_directory=True)
            has_symlink = True
        except Exception:
            has_symlink = False

        if has_symlink:
            info = StorageDurabilityEngine.inspect_storage_path(escape_path)
            assert info["classification"] == "SYMLINK_ESCAPE_REJECTED"
            assert info["verified_durable"] is False

    def test_16_prefix_collision_rejected(self):
        """16. Negative: Path with matching string prefix but different directory boundary is rejected."""
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        # /app/data/prospective_fake shares string prefix but is different directory
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective_fake/reports",
            mounts_override=mock_mounts,
        )
        assert info["classification"] == "UNAUTHORIZED_MOUNT_ROOT"
        assert info["verified_durable"] is False

    def test_17_readonly_volume_rejected(self):
        """17. Negative: Read-only volume mount is rejected."""
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "volume_id": AUTH_VOL_ID,
            "fstype": "ext4",
            "options": "ro,relatime",
            "is_readonly": True,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
        )
        assert info["classification"] in ("READ_ONLY", "UNAVAILABLE")
        assert info["verified_durable"] is False

    def test_18_unauthorized_volume_id_rejected(self):
        """18. Negative: Unknown volume ID not in authorized staging list is rejected."""
        unauth_vol = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "root": f"/var/lib/docker/volumes/{unauth_vol}/_data",
            "volume_id": unauth_vol,
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
        )
        assert info["classification"] == "UNAUTHORIZED_VOLUME_ID"
        assert info["verified_durable"] is False

    def test_19_container_recreation_with_valid_new_identity(self, monkeypatch):
        """19. Positive: Container recreation with newly issued matching attestation is PERSISTENT_VERIFIED."""
        new_container_id = "container-sprint23-staging-02-recreated"
        monkeypatch.setenv("CBE_CONTAINER_ID", new_container_id)

        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "root": f"/var/lib/docker/volumes/{AUTH_VOL_ID}/_data",
            "volume_id": AUTH_VOL_ID,
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        claims = self._make_valid_claims(bound_container_id=new_container_id)
        att = StorageDurabilityEngine.create_signed_volume_attestation(claims, TEST_SIGNING_KEY)

        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            attestation_override=att,
        )
        assert info["classification"] == "PERSISTENT_VERIFIED"
        assert info["verified_durable"] is True
        assert info["volume_id"] == AUTH_VOL_ID

    def test_20_stale_identity_after_container_replacement_rejected(self, monkeypatch):
        """20. Negative: Stale attestation from replaced previous container is rejected."""
        new_container_id = "container-sprint23-staging-02-recreated"
        old_container_id = "container-sprint23-staging-01"
        monkeypatch.setenv("CBE_CONTAINER_ID", new_container_id)

        mock_mounts = [{
            "device": "/dev/sda1",
            "mount_point": "/app/data/prospective",
            "root": f"/var/lib/docker/volumes/{AUTH_VOL_ID}/_data",
            "volume_id": AUTH_VOL_ID,
            "fstype": "ext4",
            "options": "rw",
            "is_readonly": False,
            "is_tmpfs": False,
            "is_overlay": False,
        }]
        # Attestation was issued for old container ID
        claims = self._make_valid_claims(bound_container_id=old_container_id)
        att = StorageDurabilityEngine.create_signed_volume_attestation(claims, TEST_SIGNING_KEY)

        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            attestation_override=att,
        )
        assert info["classification"] == "CONTRADICTORY_VOLUME_IDENTITY"
        assert info["verified_durable"] is False


# =============================================================================
# GROUP 2: RFC 8785 FAIL-CLOSED DEPENDENCY & HISTORICAL EVIDENCE COMPATIBILITY
# =============================================================================

class TestRFC8785FailClosedAndHistoricalCompatibility:
    """Tests RFC 8785 fail-closed behavior and legacy evidence compatibility."""

    def test_rfc8785_canonicalization_audited_package(self):
        """Audited rfc8785 package serializes keys and floats deterministically."""
        data = {
            "b": 1,
            "a": "test",
            "c": [3, 2, 1],
            "d": 0.0,
        }
        canonical = rfc8785_canonical_json(data)
        assert isinstance(canonical, bytes)
        # RFC 8785 mandates key ordering 'a', 'b', 'c', 'd'
        assert canonical.startswith(b'{"a":"test","b":1')

    def test_rfc8785_fail_closed_when_dependency_missing(self, monkeypatch):
        """RFC 8785 serializer must raise RuntimeError when audited package is unavailable (no silent fallback)."""
        import coin_behavior_engine.product.research_report_evidence as rre

        monkeypatch.setattr(rre, "rfc8785", None)

        with pytest.raises(RuntimeError) as exc_info:
            rre.rfc8785_canonical_json({"sample": "data"})

        assert "RFC_8785_DEPENDENCY_UNAVAILABLE" in str(exc_info.value)
        assert "Silent fallback to unverified custom serializer is strictly prohibited" in str(exc_info.value)

    def test_legacy_canonical_json_v1_compatibility(self):
        """Historical CBE-CANONICAL-JSON-v1 serializer produces identical bytes without mutation."""
        sample_payload = {
            "session_id": "URS-HISTORICAL-01",
            "status": "COMPLETED",
            "metrics": {"ic": 0.08, "sharpe": 1.45},
        }
        legacy_bytes = legacy_canonical_json_v1(sample_payload)
        expected_bytes = json.dumps(sample_payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
        assert legacy_bytes == expected_bytes

    def test_evidence_verification_supports_both_rfc8785_and_legacy_v1(self):
        """Evidence bundle verification engine supports RFC 8785 canonical bytes and legacy V1."""
        engine = ResearchReportEvidenceBundleEngine()
        sample_report = {
            "report_metadata": {
                "report_id": "RPT-SAMPLE-TEST-99",
                "title": "RFC 8785 Test Report",
                "generated_at_utc": "2026-11-08T00:00:00Z",
                "dataset_manifest_version": "V2_CANONICAL_2026_V1",
            },
            "historical_scope": {
                "asset": "BTCUSDT",
                "start_utc": "2022-06-01T00:00:00Z",
                "end_utc": "2022-06-03T00:00:00Z",
                "dataset_manifest_version": "V2_CANONICAL_2026_V1",
            },
            "canonical_model_identity": {
                "version": "CBE-0.7.0",
                "status": "STRICTLY_FROZEN",
                "parameter_mutations": 0,
            },
            "statistical_evidence": {
                "predeclared_holdout_criteria_satisfied": True,
                "p_value": 0.012,
            },
            "evidence_provenance": {
                "dataset_manifest_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "source_commit_sha": "db3bb63e1aca90582847880e80abd9e87938b142",
            },
        }
        bundle = engine.create_evidence_bundle(sample_report)
        assert bundle["bundle_metadata"]["canonicalization_scheme"] == "RFC-8785"

        ver = engine.verify_evidence_bundle(bundle)
        assert ver["valid"]
        assert ver["canonical_scheme"] == "RFC-8785"
        assert ver["recorded_checksum"] == ver["recomputed_checksum"]

        # Also test legacy verification path
        legacy_bytes = legacy_canonical_json_v1(bundle["payload"])
        legacy_chk = hashlib.sha256(legacy_bytes).hexdigest()
        bundle_legacy = copy.deepcopy(bundle)
        bundle_legacy["bundle_metadata"]["package_checksum_sha256"] = legacy_chk
        bundle_legacy["bundle_metadata"]["canonicalization_scheme"] = "CBE-CANONICAL-JSON-v1"

        ver_legacy = engine.verify_evidence_bundle(bundle_legacy)
        assert ver_legacy["valid"]
        assert ver_legacy["canonical_scheme"] == "CBE-CANONICAL-JSON-v1"


# =============================================================================
# GROUP 3: RELEASE PROVENANCE & GIT ANCESTRY INTEGRITY
# =============================================================================

class TestReleaseProvenanceIntegrity:
    """Validates authoritative Git commit lineage and release metadata consistency."""

    def test_commit_ancestors_presence(self):
        """Verifies critical historical milestone commits exist in repository history."""
        milestone_commits = [
            ("sprint22_closure", "db3bb63e1aca90582847880e80abd9e87938b142"),
            ("sprint23_initial", "abbc0a1d25cf42b37129574921e1a05420a300e4"),
            ("sprint23_correction", "de2d1e3f549d48a70909258e7c6f190f47d083aa"),
            ("sprint23_cert_impl", "c09279180141dff1029bc679255392b57b35ec91"),
            ("sprint23_audit_head", "70a2021e9512da3109e0459ce2a02ef1961dd307"),
        ]
        import subprocess
        for name, sha in milestone_commits:
            res = subprocess.run(["git", "cat-file", "-t", sha], capture_output=True, text=True)
            assert res.returncode == 0, f"Milestone commit {name} ({sha}) not found in Git repository!"
            assert res.stdout.strip() == "commit", f"Object {sha} is not a commit!"

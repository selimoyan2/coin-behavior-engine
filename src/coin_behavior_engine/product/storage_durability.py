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
import hmac
import io
import json
import os
import re
import sys
import tarfile
import time
from datetime import datetime, timezone, timedelta
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
    def parse_mountinfo_table(cls, mountinfo_content: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parses /proc/self/mountinfo into structured mount entries with volume identity extraction."""
        mounts: List[Dict[str, Any]] = []
        if mountinfo_content is None:
            mountinfo_path = os.environ.get("CBE_MOUNTINFO_PATH", "/proc/self/mountinfo")
            if sys.platform != "win32" and os.path.exists(mountinfo_path):
                try:
                    with open(mountinfo_path, "r", encoding="utf-8") as f:
                        mountinfo_content = f.read()
                except Exception:
                    mountinfo_content = ""
            else:
                mountinfo_content = ""

        if not mountinfo_content:
            return mounts

        for line in mountinfo_content.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if "-" not in parts:
                continue
            sep_idx = parts.index("-")
            if len(parts) < sep_idx + 3 or len(parts) < 5:
                continue

            root = parts[3]
            mount_point = parts[4].rstrip("/") or "/"
            mount_opts = parts[5].split(",")
            fstype = parts[sep_idx + 1].lower()
            mount_source = parts[sep_idx + 2]
            super_opts = parts[sep_idx + 3].split(",") if len(parts) > sep_idx + 3 else []

            # Extract Docker volume ID from kernel mount root path
            vol_id = None
            vm = re.search(r"/(?:var/lib/)?(?:docker|containers)/volumes/([^/]+)/_data", root)
            if not vm:
                vm = re.search(r"/volumes/([a-zA-Z0-9_\.-]+)/_data", root)
            if not vm:
                vm = re.search(r"/volumes/([a-zA-Z0-9_\.-]+)", root)
            if vm:
                vol_id = vm.group(1)

            opt_all = set(mount_opts + super_opts)

            mounts.append({
                "device": mount_source,
                "mount_point": mount_point,
                "root": root,
                "volume_id": vol_id,
                "fstype": fstype,
                "options": ",".join(mount_opts),
                "is_readonly": "ro" in opt_all,
                "is_tmpfs": fstype in ("tmpfs", "ramfs", "shm"),
                "is_overlay": fstype in ("overlay", "overlayfs"),
            })
        return mounts

    @classmethod
    def parse_mounts_table(cls, mounts_content: Optional[str] = None) -> List[Dict[str, Any]]:
        """Parses /proc/self/mountinfo or /proc/mounts style table into structured mount entries."""
        if mounts_content is None:
            mountinfo_path = os.environ.get("CBE_MOUNTINFO_PATH", "/proc/self/mountinfo")
            if sys.platform != "win32" and os.path.exists(mountinfo_path):
                m_info = cls.parse_mountinfo_table()
                if m_info:
                    return m_info

        if mounts_content is not None and any(" - " in line for line in mounts_content.splitlines()):
            return cls.parse_mountinfo_table(mountinfo_content=mounts_content)

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
    def get_current_container_id(cls) -> Optional[str]:
        """Retrieves current container ID from CBE_CONTAINER_ID, /etc/hostname, or /proc/self/cgroup."""
        env_cid = os.environ.get("CBE_CONTAINER_ID")
        if env_cid:
            return env_cid.strip()
        if sys.platform != "win32" and os.path.exists("/etc/hostname"):
            try:
                with open("/etc/hostname", "r", encoding="utf-8") as f:
                    host = f.read().strip()
                if re.match(r"^[0-9a-fA-F]{12,64}$", host):
                    return host
            except Exception:
                pass
        if sys.platform != "win32" and os.path.exists("/proc/self/cgroup"):
            try:
                with open("/proc/self/cgroup", "r", encoding="utf-8") as f:
                    content = f.read()
                m = re.search(r"(?:docker/|containers/|docker-)([0-9a-fA-F]{12,64})", content)
                if m:
                    return m.group(1)
            except Exception:
                pass
        return None

    @classmethod
    def get_current_image_id(cls) -> Optional[str]:
        """Retrieves current container image ID from CBE_IMAGE_ID or CBE_IMAGE_DIGEST."""
        return os.environ.get("CBE_IMAGE_ID") or os.environ.get("CBE_IMAGE_DIGEST")

    @classmethod
    def get_deployment_attestation_key(cls, resolved_path: Optional[str] = None) -> Optional[str]:
        """
        Retrieves deployment signing key from a secure location outside application-writable storage.
        Prevents using signing keys stored inside application-writable directories.
        """
        key_env = os.environ.get("CBE_VOLUME_ATTESTATION_KEY")
        if key_env:
            return key_env.strip()

        key_path = os.environ.get("CBE_VOLUME_ATTESTATION_KEY_PATH", "/etc/cbe/keys/volume_attestation_key")
        if resolved_path and os.path.isabs(key_path):
            try:
                rp = Path(os.path.realpath(resolved_path))
                kp = Path(os.path.realpath(key_path))
                if rp == kp or rp in kp.parents:
                    # Key stored inside application-writable storage is rejected
                    return None
            except Exception:
                pass

        if os.path.exists(key_path):
            try:
                with open(key_path, "r", encoding="utf-8") as f:
                    return f.read().strip()
            except Exception:
                pass
        return None

    @classmethod
    def create_signed_volume_attestation(
        cls,
        claims: Dict[str, Any],
        signing_key: str | bytes,
    ) -> Dict[str, Any]:
        """
        Creates a tamper-evident signed volume attestation for deployment control plane.
        Serializes claims using RFC 8785 canonical JSON and signs with HMAC-SHA256.
        """
        from coin_behavior_engine.product.research_report_evidence import rfc8785_canonical_json

        canonical_bytes = rfc8785_canonical_json(claims)
        key_bytes = signing_key.encode("utf-8") if isinstance(signing_key, str) else signing_key
        sig = hmac.new(key_bytes, canonical_bytes, hashlib.sha256).hexdigest()

        return {
            "claims": claims,
            "signature": sig,
            "signature_algorithm": "HMAC-SHA256",
        }

    @classmethod
    def load_and_verify_volume_attestation(
        cls,
        resolved_path: str,
        norm_no_drive: str,
        mount_info: Dict[str, Any],
        attestation_override: Optional[Dict[str, Any]] = None,
        contract_override: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """
        Loads and cryptographically verifies the deployment volume attestation.
        Returns: (verified_volume_id, rejection_code, rejection_reason)
        """
        # 1. Compatibility check for in-memory contract_override without signature
        if contract_override is not None and not contract_override.get("signature") and not contract_override.get("_require_signature"):
            c_dest = contract_override.get("expected_destination")
            c_fs = contract_override.get("expected_filesystem")
            c_vol = contract_override.get("authorized_volume_id")

            dest_match = False
            if c_dest:
                c_dest_clean = re.sub(r"^[a-zA-Z]:", "", c_dest.strip().replace("\\", "/"))
                cd_parts = Path(c_dest_clean).parts
                res_parts = Path(norm_no_drive).parts
                if len(res_parts) >= len(cd_parts):
                    if res_parts[:len(cd_parts)] == cd_parts or res_parts[-len(cd_parts):] == cd_parts:
                        dest_match = True
            else:
                dest_match = True

            if not dest_match:
                return None, "UNAUTHORIZED_MOUNT_ROOT", f"Deployment contract destination '{c_dest}' does not match path '{norm_no_drive}'."

            if mount_info.get("fstype") and c_fs:
                if c_fs.lower() != mount_info.get("fstype", "").lower():
                    return None, "REJECTED_FILESYSTEM_TYPE", f"Deployment contract filesystem '{c_fs}' contradicts runtime filesystem '{mount_info.get('fstype')}'."

            return c_vol, None, None

        # 2. Locate candidate attestation source
        data = None
        source_path = None

        if attestation_override is not None:
            data = attestation_override
            source_path = None
        elif contract_override is not None and (contract_override.get("signature") or contract_override.get("_require_signature")):
            data = contract_override
            source_path = None
        else:
            candidate_paths: List[str] = []
            env_att = os.environ.get("CBE_VOLUME_ATTESTATION_PATH")
            if env_att:
                candidate_paths.append(env_att)
            env_contract = os.environ.get("CBE_VOLUME_CONTRACT_PATH")
            if env_contract:
                candidate_paths.append(env_contract)

            curr_d = Path(resolved_path)
            candidate_dirs = [curr_d, *curr_d.parents]
            for d in candidate_dirs[:4]:
                candidate_paths.append(str(d / ".cbe_volume_attestation.json"))
                candidate_paths.append(str(d / ".cbe_volume_contract.json"))

            candidate_paths.extend([
                "/etc/cbe/volume_attestation.json",
                "/etc/cbe/volume_contract.json",
            ])

            for cp in candidate_paths:
                if os.path.exists(cp):
                    try:
                        with open(cp, "r", encoding="utf-8") as f:
                            parsed = json.load(f)
                        if isinstance(parsed, dict):
                            data = parsed
                            source_path = cp
                            break
                    except Exception:
                        continue

        if data is None:
            return None, None, None

        # 3. Check trust boundary: attestation file inside application-writable storage requires external key
        is_in_writable_storage = False
        if source_path:
            try:
                sp_real = os.path.realpath(source_path)
                rp_real = os.path.realpath(resolved_path)
                if sp_real == rp_real or sp_real.startswith(rp_real + os.sep) or sp_real.startswith(rp_real + "/"):
                    is_in_writable_storage = True
            except Exception:
                is_in_writable_storage = False

        signing_key = cls.get_deployment_attestation_key(resolved_path=resolved_path)
        if is_in_writable_storage and not signing_key:
            return None, "UNVERIFIABLE_VOLUME_IDENTITY", "Attestation document resides in application-writable storage without external signing key."

        # 4. Check signature presence (unauthenticated / plain JSON files rejected)
        signature = data.get("signature")
        if not signature:
            return None, "UNAUTHENTICATED_ATTESTATION_REJECTED", "Attestation is missing cryptographic signature (plain unauthenticated JSON document rejected)."

        if not signing_key:
            return None, "UNVERIFIABLE_VOLUME_IDENTITY", "No deployment signing key configured to verify signed attestation."

        # 5. Extract claims
        if isinstance(data.get("claims"), dict):
            claims = data["claims"]
        else:
            claims = {k: v for k, v in data.items() if k not in ("signature", "signature_algorithm", "signature_hex")}

        # 6. Cryptographic verification via HMAC-SHA256 over RFC 8785 canonical claims
        try:
            from coin_behavior_engine.product.research_report_evidence import rfc8785_canonical_json
            canonical_bytes = rfc8785_canonical_json(claims)
        except Exception as e:
            return None, "UNAUTHENTICATED_ATTESTATION_REJECTED", f"RFC 8785 canonicalization failed: {e}"

        key_bytes = signing_key.encode("utf-8") if isinstance(signing_key, str) else signing_key
        expected_sig = hmac.new(key_bytes, canonical_bytes, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(str(signature).lower(), expected_sig.lower()):
            return None, "UNAUTHENTICATED_ATTESTATION_REJECTED", "Cryptographic signature verification failed (invalid HMAC)."

        # 7. Freshness / Expiration check
        expires_at_utc = claims.get("expires_at_utc")
        if expires_at_utc:
            try:
                exp_dt = datetime.fromisoformat(expires_at_utc.replace("Z", "+00:00"))
                if exp_dt < datetime.now(timezone.utc):
                    return None, "UNVERIFIABLE_VOLUME_IDENTITY", f"Attestation expired at {expires_at_utc}."
            except Exception as e:
                return None, "UNVERIFIABLE_VOLUME_IDENTITY", f"Invalid expiration timestamp '{expires_at_utc}': {e}"

        # 8. Container binding check
        bound_cid = claims.get("bound_container_id")
        if bound_cid:
            curr_cid = cls.get_current_container_id()
            if curr_cid:
                if not (curr_cid.startswith(bound_cid) or bound_cid.startswith(curr_cid)):
                    return None, "CONTRADICTORY_VOLUME_IDENTITY", f"Attestation bound to container '{bound_cid}' contradicts current container '{curr_cid}'."
            else:
                return None, "UNVERIFIABLE_VOLUME_IDENTITY", f"Attestation requires container binding '{bound_cid}' but current container ID cannot be established."

        # 9. Destination binding check
        c_dest = claims.get("expected_destination")
        if c_dest:
            c_dest_clean = re.sub(r"^[a-zA-Z]:", "", c_dest.strip().replace("\\", "/"))
            cd_parts = Path(c_dest_clean).parts
            res_parts = Path(norm_no_drive).parts
            dest_match = False
            if len(res_parts) >= len(cd_parts):
                if res_parts[:len(cd_parts)] == cd_parts or res_parts[-len(cd_parts):] == cd_parts:
                    dest_match = True
            if not dest_match:
                return None, "UNAUTHORIZED_MOUNT_ROOT", f"Attestation destination '{c_dest}' does not match path '{norm_no_drive}'."

        # 10. Image binding check
        bound_img = claims.get("bound_image_id")
        if bound_img:
            curr_img = cls.get_current_image_id()
            if curr_img:
                if curr_img != bound_img:
                    return None, "CONTRADICTORY_VOLUME_IDENTITY", f"Attestation bound to image '{bound_img}' contradicts current image '{curr_img}'."
            else:
                return None, "UNVERIFIABLE_VOLUME_IDENTITY", f"Attestation requires image binding '{bound_img}' but current image ID cannot be established."

        # 11. Filesystem check
        c_fs = claims.get("expected_filesystem")
        if c_fs and mount_info.get("fstype"):
            if c_fs.lower() != mount_info["fstype"].lower():
                return None, "REJECTED_FILESYSTEM_TYPE", f"Attestation filesystem '{c_fs}' contradicts runtime '{mount_info['fstype']}'."

        auth_vol = claims.get("authorized_volume_id")
        if not auth_vol:
            return None, "UNVERIFIABLE_VOLUME_IDENTITY", "Attestation contains no authorized_volume_id."

        return auth_vol, None, None

    @classmethod
    def load_deployment_volume_contract(
        cls,
        resolved_path: str,
        contract_override: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Loads deployment-provided volume verification contract or attestation for inspection."""
        if contract_override is not None:
            return contract_override

        candidate_paths = [
            os.path.join(resolved_path, ".cbe_volume_attestation.json"),
            os.path.join(resolved_path, ".cbe_volume_contract.json"),
            "/etc/cbe/volume_attestation.json",
            "/etc/cbe/volume_contract.json",
        ]
        env_contract = os.environ.get("CBE_VOLUME_ATTESTATION_PATH") or os.environ.get("CBE_VOLUME_CONTRACT_PATH")
        if env_contract:
            candidate_paths.insert(0, env_contract)

        for c_path in candidate_paths:
            if os.path.exists(c_path):
                try:
                    with open(c_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        return data
                except Exception:
                    continue
        return None

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
        contract_override: Optional[Dict[str, Any]] = None,
        attestation_override: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Inspects and classifies a storage directory path with strict boundary and persistence verification.
        - Resolves symlinks using realpath to prevent symlink escape.
        - Matches mount points using path-component boundaries.
        - Distinguishes Docker overlay filesystems from genuine persistent volume mounts.
        - Requires authoritative runtime Docker volume identity or verified cryptographic deployment attestation.
        - Never trusts an environment variable as proof of actual mount identity.
        - Fails closed if persistence cannot be proven in staging/production.
        """
        raw_str = str(path_input)

        # 1. Realpath resolution & symlink escape detection
        try:
            if os.path.exists(raw_str):
                resolved = os.path.realpath(raw_str)
            else:
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
        established_vol_id: Optional[str] = None
        volume_provenance: str = "NONE"

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
            rejection_reason = "Storage path resides on an ephemeral or tmpfs mount (EPHEMERAL_STORAGE_REJECTED)."
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
                classification = "CONTAINER_OVERLAY_REJECTED"
                rejection_reason = "Storage path is backed by ephemeral Docker container overlay rootfs."
            elif mount_info.get("fstype") in cls.REJECTED_FILESYSTEM_TYPES:
                classification = "REJECTED_FILESYSTEM_TYPE"
                rejection_reason = f"Filesystem type '{mount_info.get('fstype')}' is not authorized for persistent storage."
            elif mounts and not mount_info:
                classification = "PERSISTENT_UNVERIFIED"
                rejection_reason = "Path has no established mount entry in system mounts table."
            else:
                # 6. Authoritative Docker volume identity verification
                # A: Independently obtained runtime volume ID from kernel mountinfo
                runtime_volume_id = mount_info.get("volume_id")
                if not runtime_volume_id and mount_info.get("root"):
                    root_val = mount_info.get("root", "")
                    vm = re.search(r"/(?:var/lib/)?(?:docker|containers)/volumes/([^/]+)/_data", root_val)
                    if not vm:
                        vm = re.search(r"/volumes/([a-zA-Z0-9_\.-]+)/_data", root_val)
                    if not vm:
                        vm = re.search(r"/volumes/([a-zA-Z0-9_\.-]+)", root_val)
                    if vm:
                        runtime_volume_id = vm.group(1)

                # B: Deployment-provided cryptographically verified attestation
                att_vol_id, att_rej_code, att_rej_reason = cls.load_and_verify_volume_attestation(
                    resolved,
                    norm_no_drive,
                    mount_info,
                    attestation_override=attestation_override,
                    contract_override=contract_override,
                )

                if att_rej_code:
                    classification = att_rej_code
                    rejection_reason = att_rej_reason
                else:
                    attestation_volume_id = att_vol_id

                    # Check if an environment variable was provided (potential spoofing or contradiction)
                    env_vol_id = os.environ.get("CBE_AUTHORIZED_VOLUME_ID") or os.environ.get("CBE_DOCKER_VOLUME_ID")

                    if runtime_volume_id and attestation_volume_id and runtime_volume_id != attestation_volume_id:
                        classification = "CONTRADICTORY_VOLUME_IDENTITY"
                        rejection_reason = f"Runtime volume ID '{runtime_volume_id}' contradicts deployment attestation volume ID '{attestation_volume_id}'."
                    else:
                        established_vol_id = runtime_volume_id or attestation_volume_id

                        if runtime_volume_id and attestation_volume_id:
                            volume_provenance = "KERNEL_AND_ATTESTATION"
                        elif runtime_volume_id:
                            volume_provenance = "KERNEL_MOUNTINFO"
                        elif attestation_volume_id:
                            volume_provenance = "DEPLOYMENT_CONTRACT"

                        # Anti-spoofing rule: Environment variable ALONE is never accepted as proof
                        if env_vol_id and not established_vol_id:
                            classification = "UNVERIFIABLE_VOLUME_IDENTITY"
                            rejection_reason = "Environment variable alone cannot establish volume identity without independently obtained runtime metadata or deployment contract."
                        elif env_vol_id and established_vol_id and env_vol_id != established_vol_id:
                            classification = "CONTRADICTORY_VOLUME_IDENTITY"
                            rejection_reason = f"Configured environment volume ID '{env_vol_id}' contradicts verified runtime volume identity '{established_vol_id}'."
                        elif not established_vol_id:
                            classification = "UNVERIFIABLE_VOLUME_IDENTITY"
                            rejection_reason = "No authoritative Docker volume identity could be established from kernel runtime metadata or deployment contract."
                        elif established_vol_id not in cls.AUTHORIZED_STAGING_VOLUME_IDS:
                            classification = "UNAUTHORIZED_VOLUME_ID"
                            rejection_reason = f"Verified volume ID '{established_vol_id}' is not in authorized staging volume list."
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
            "volume_id": established_vol_id if classification == "PERSISTENT_VERIFIED" else None,
            "volume_provenance": volume_provenance,
        }

    @classmethod
    def require_durable_storage(
        cls,
        path_input: str | Path,
        mounts_override: Optional[List[Dict[str, Any]]] = None,
        contract_override: Optional[Dict[str, Any]] = None,
        attestation_override: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Enforces that the path is PERSISTENT_VERIFIED in staging/production.
        Raises RuntimeError if storage path is ephemeral or unverified.
        """
        info = cls.inspect_storage_path(
            path_input,
            mounts_override=mounts_override,
            contract_override=contract_override,
            attestation_override=attestation_override,
        )
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

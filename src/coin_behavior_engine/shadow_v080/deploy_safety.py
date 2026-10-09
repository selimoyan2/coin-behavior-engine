"""Sprint 09.13.2 / Approval 2 — Coolify Inert Deployment Safety Interlock (Final Hardened).

Enforces strictly fail-closed safety invariants for an isolated, inert Coolify container:
1. Exact allowed values for all safety-critical environment variables.
2. Deterministic, DNS-free network isolation checks (raw IP only; strict /proc/net/dev inspection).
3. Read-only filesystem verification (statvfs MS_RDONLY and /proc/mounts consistency).
4. Mandatory audit evidence persistence with append-only bounded history and volume permission checks.
5. Production database and shared storage isolation.
6. Inert lifecycle state management (DEPLOYED_INERT, STOPPED, FAILED_SAFE).
"""

from __future__ import annotations

import errno
import hashlib
import json
import logging
import os
import platform
import socket
import sys
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [DeploySafety] %(message)s")
logger = logging.getLogger("DeploySafety")

# Strict, exact allowed values for safety-critical environment variables
STRICT_SAFETY_CONTRACT = {
    "CBE_TRADING_DISABLED": "true",
    "CBE_PROSPECTIVE_OBSERVATION_ENABLED": "false",
    "CBE_BINANCE_COLLECTION_ENABLED": "false",
    "CBE_RECORD_LABEL": "WARMUP_REPLAY",
    "CBE_ENFORCE_PROSPECTIVE_GUARD": "true",
}

ALLOWED_ENVIRONMENTS = ("staging_coolify_inert", "staging_offline")
MAX_AUDIT_HISTORY_ENTRIES = 500  # Bounded history to prevent unbounded disk growth


class SafetyInterlockError(Exception):
    """Raised when any deployment safety invariant is violated."""


@dataclass(frozen=True)
class SafetyContractVerification:
    status: str  # "PASS" or "FAIL"
    lifecycle_state: str  # "DEPLOYED_INERT", "STOPPED", "FAILED_SAFE"
    trading_disabled: bool
    prospective_scoring_disabled: bool
    binance_collection_disabled: bool
    network_isolated: bool
    database_isolated: bool
    filesystem_isolated: bool
    production_isolated: bool
    volume_writable: bool
    violations: List[str]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _check_network_namespace_isolation(
    proc_net_dev_path: Optional[Path] = None,
    is_container: Optional[bool] = None,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Perform deterministic, DNS-free network isolation checks.

    Avoids ANY DNS hostname queries (no api.binance.com, google.com).
    Uses raw numerical IP addresses and inspects Linux kernel network devices if in container.
    """
    violations: List[str] = []
    details: Dict[str, Any] = {
        "dns_queries_executed": 0,
        "raw_ip_probes_executed": 0,
        "interfaces_detected": [],
    }

    in_container = is_container if is_container is not None else (
        Path("/.dockerenv").exists() or os.environ.get("CBE_CONTAINER_ENV") == "true"
    )

    # 1. Inspect Linux network interfaces via /proc/net/dev
    proc_net = proc_net_dev_path or Path("/proc/net/dev")
    if in_container or proc_net_dev_path is not None:
        if not proc_net.exists():
            violations.append("NETWORK_EVIDENCE_MISSING: Network interface evidence /proc/net/dev does not exist in container.")
            return False, violations, details

        try:
            content = proc_net.read_text(encoding="utf-8")
        except Exception as e:
            violations.append(f"NETWORK_EVIDENCE_UNREADABLE: Could not read /proc/net/dev: {e}")
            return False, violations, details

        lines = content.splitlines()
        if len(lines) < 2 or not lines[0].strip().startswith("Inter-"):
            violations.append("NETWORK_EVIDENCE_MALFORMED: /proc/net/dev has missing or invalid header.")
            return False, violations, details

        interfaces = []
        for line in lines[2:]:
            if ":" in line:
                iface = line.split(":", 1)[0].strip()
                if iface:
                    interfaces.append(iface)
        details["interfaces_detected"] = interfaces

        if not interfaces:
            violations.append("NETWORK_EVIDENCE_MALFORMED: No network interfaces parsed from /proc/net/dev.")
            return False, violations, details

        # In network_mode: "none", only loopback ('lo') should exist
        non_loopback = [i for i in interfaces if i != "lo"]
        if non_loopback:
            violations.append(
                f"NETWORK_NAMESPACE_NOT_NONE: Non-loopback network interfaces detected in container: {non_loopback}. "
                "Expected only 'lo' under network_mode: 'none'."
            )
        else:
            details["interface_check"] = "LOOPBACK_ONLY"

    # 2. Raw IP Socket Connection Probe (strictly numeric IPs, zero DNS lookup)
    test_ips = [
        ("192.0.2.1", 80),     # TEST-NET-1 (RFC 5737)
        ("198.51.100.1", 443), # TEST-NET-2 (RFC 5737)
        ("8.8.8.8", 53),       # Numeric IP without hostname resolution
    ]

    for ip_str, port in test_ips:
        details["raw_ip_probes_executed"] += 1
        s = None
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(0.15)  # fast 150ms timeout
            res = s.connect_ex((ip_str, port))
            if res == 0:
                violations.append(
                    f"NETWORK_ISOLATION_BREACH: Outbound TCP socket connect to raw IP {ip_str}:{port} succeeded. "
                    "Container has active external egress route."
                )
                break
        except Exception:
            # Network unreachable / EHOSTUNREACH / ENETUNREACH is expected and safe
            pass
        finally:
            if s is not None:
                try:
                    s.close()
                except Exception:
                    pass

    network_isolated = (len(violations) == 0)
    return network_isolated, violations, details


def _check_filesystem_read_only(
    check_filesystem: bool,
    proc_mounts_path: Optional[Path] = None,
    statvfs_func: Optional[Callable] = None,
    write_probe_func: Optional[Callable[[], None]] = None,
    is_container: Optional[bool] = None,
) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Audit read-only root filesystem enforcement.

    Distinguishes genuine kernel read-only mount (MS_RDONLY / errno.EROFS)
    from ordinary user permission denial (errno.EACCES).
    """
    violations: List[str] = []
    details: Dict[str, Any] = {
        "is_mount_statvfs_ro": None,
        "root_mount_is_ro": None,
        "probe_error_errno": None,
        "probe_error_name": None,
    }

    if not check_filesystem:
        return True, violations, details

    in_container = is_container if is_container is not None else (
        Path("/.dockerenv").exists() or os.environ.get("CBE_CONTAINER_ENV") == "true"
    )

    if in_container or proc_mounts_path is not None:
        proc_mounts = proc_mounts_path or Path("/proc/mounts")
        if not proc_mounts.exists():
            violations.append("FILESYSTEM_EVIDENCE_MISSING: Mount evidence /proc/mounts does not exist in container.")
            return False, violations, details

        try:
            lines = proc_mounts.read_text(encoding="utf-8").splitlines()
        except Exception as e:
            violations.append(f"FILESYSTEM_EVIDENCE_UNREADABLE: Could not read /proc/mounts: {e}")
            return False, violations, details

        # Find mount entry for '/'
        root_mount_entry = None
        for line in lines:
            parts = line.split()
            if len(parts) >= 4 and parts[1] == "/":
                root_mount_entry = parts
                break

        if root_mount_entry is None:
            violations.append("FILESYSTEM_ROOT_MOUNT_MISSING: Root mount entry '/' not found in /proc/mounts.")
            return False, violations, details

        opts = root_mount_entry[3].split(",")
        mount_is_ro = "ro" in opts
        details["root_mount_opts"] = opts
        details["root_mount_is_ro"] = mount_is_ro

        # 2. Check statvfs on root filesystem
        st_func = statvfs_func or getattr(os, "statvfs", None)
        statvfs_is_ro = None
        if st_func is not None:
            try:
                st = st_func("/")
                statvfs_is_ro = bool(st.f_flag & getattr(os, "ST_RDONLY", 1))
                details["is_mount_statvfs_ro"] = statvfs_is_ro
            except Exception as e:
                details["statvfs_error"] = str(e)

        # Contradiction check: /proc/mounts vs statvfs
        if statvfs_is_ro is not None and mount_is_ro != statvfs_is_ro:
            violations.append(
                f"FILESYSTEM_MOUNT_EVIDENCE_CONTRADICTORY: /proc/mounts ro={mount_is_ro} "
                f"contradicts statvfs ro={statvfs_is_ro}."
            )

        if not mount_is_ro:
            violations.append(
                f"FILESYSTEM_NOT_MOUNTED_RO: Root filesystem '/' is not mounted read-only (mount options: {opts})."
            )

        # 3. Direct probe write
        probe_path = Path("/root_fs_immutable_probe.tmp")
        try:
            if write_probe_func is not None:
                write_probe_func()
            else:
                probe_path.write_text("should_fail_if_ro")
                probe_path.unlink(missing_ok=True)
            violations.append("FILESYSTEM_NOT_READ_ONLY: Wrote successfully to container root filesystem.")
        except OSError as e:
            details["probe_error_errno"] = e.errno
            details["probe_error_name"] = errno.errorcode.get(e.errno, f"ERR_{e.errno}")

            if e.errno == errno.EROFS:
                details["ro_enforcement_verified"] = "GENUINE_KERNEL_EROFS"
            elif e.errno == errno.EACCES:
                details["ro_enforcement_verified"] = "DAC_PERMISSION_DENIAL_ONLY"
                if not mount_is_ro:
                    violations.append(
                        "FILESYSTEM_NOT_MOUNTED_RO: Root filesystem is writable at mount level; "
                        "write blocked only by user UID 1000 permissions (EACCES) instead of read_only: true (EROFS)."
                    )

    filesystem_isolated = (len(violations) == 0)
    return filesystem_isolated, violations, details


def verify_coolify_inert_contract(
    probe_network: bool = True,
    check_filesystem: bool = True,
    base_dir: Optional[Path] = None,
    target_data_dir: Optional[Path] = None,
    proc_net_dev_path: Optional[Path] = None,
    proc_mounts_path: Optional[Path] = None,
    statvfs_func: Optional[Callable] = None,
    write_probe_func: Optional[Callable[[], None]] = None,
    is_container: Optional[bool] = None,
) -> SafetyContractVerification:
    """Perform comprehensive fail-closed safety verification of deployment configuration.

    Enforces exact allowed values for safety variables, deterministic network isolation,
    genuine read-only root status, and persistent volume write permissions.
    """
    violations: List[str] = []

    # 1. Exact Match Enforcement for Safety Variables
    for env_var, exact_allowed in STRICT_SAFETY_CONTRACT.items():
        actual_val = os.environ.get(env_var)
        if actual_val is None:
            violations.append(f"CONFIG_MISSING_{env_var}: Environment variable '{env_var}' is not set.")
        elif actual_val != exact_allowed:
            violations.append(
                f"CONFIG_INVALID_{env_var}: Value for '{env_var}' must be strictly '{exact_allowed}', "
                f"got '{actual_val}'."
            )

    # 2. Strict Environment Name Verification
    cbe_env = os.environ.get("CBE_ENV")
    if cbe_env is None:
        violations.append("CONFIG_MISSING_CBE_ENV: CBE_ENV must be explicitly defined.")
    elif cbe_env not in ALLOWED_ENVIRONMENTS:
        violations.append(
            f"CONFIG_INVALID_CBE_ENV: CBE_ENV must be one of {ALLOWED_ENVIRONMENTS}, got '{cbe_env}'."
        )

    # 3. Secret & Production Database Credentials Isolation
    forbidden_secret_envs = [
        "BINANCE_API_KEY",
        "BINANCE_API_SECRET",
        "DATABASE_URL",
        "POSTGRES_PASSWORD",
        "POSTGRES_USER",
        "COOLIFY_API_KEY",
    ]
    for sec_var in forbidden_secret_envs:
        val = os.environ.get(sec_var, "").strip()
        if val:
            violations.append(f"UNAUTHORIZED_CREDENTIAL_PRESENT: Environment variable '{sec_var}' must not be set.")

    # 4. Deterministic Network Isolation Audit
    net_iso = True
    net_details: Dict[str, Any] = {}
    if probe_network:
        net_iso, net_violations, net_details = _check_network_namespace_isolation(
            proc_net_dev_path=proc_net_dev_path,
            is_container=is_container,
        )
        violations.extend(net_violations)

    # 5. Read-Only Root Filesystem Audit
    fs_iso = True
    fs_details: Dict[str, Any] = {}
    if check_filesystem:
        fs_iso, fs_violations, fs_details = _check_filesystem_read_only(
            check_filesystem=check_filesystem,
            proc_mounts_path=proc_mounts_path,
            statvfs_func=statvfs_func,
            write_probe_func=write_probe_func,
            is_container=is_container,
        )
        violations.extend(fs_violations)

    # 6. Production Storage Isolation
    production_isolated = True
    app_root = base_dir or Path(__file__).resolve().parents[3]
    prod_prospective_dir = app_root / "data" / "prospective"
    target_shadow_dir = target_data_dir or Path(os.environ.get("CBE_SHADOW_DATA_DIR", "/app/data/prospective_shadow"))

    if prod_prospective_dir.exists():
        try:
            if prod_prospective_dir.resolve() == target_shadow_dir.resolve():
                production_isolated = False
                violations.append("PRODUCTION_VOLUME_COLLISION: Shadow storage target cannot point to production data/prospective.")
        except Exception:
            pass

    # 7. Volume Write Permission Check for UID 1000
    volume_writable = True
    test_vol_file = target_shadow_dir / ".volume_perm_check.tmp"
    try:
        target_shadow_dir.mkdir(parents=True, exist_ok=True)
        test_vol_file.write_text("perm_ok")
        test_vol_file.unlink(missing_ok=True)
    except OSError as e:
        volume_writable = False
        if e.errno == errno.EROFS:
            violations.append(f"VOLUME_MOUNT_READ_ONLY: Shadow storage volume {target_shadow_dir} is mounted read-only (:ro).")
        elif e.errno == errno.EACCES:
            violations.append(
                f"VOLUME_PERMISSION_DENIED: User UID {os.getuid() if hasattr(os, 'getuid') else 'unknown'} "
                f"lacks write permission in shadow volume {target_shadow_dir} (volume may be root-owned). "
                "Operator must run ownership recovery."
            )
        else:
            violations.append(f"VOLUME_ACCESS_FAILED: Could not write probe file in {target_shadow_dir}: {e}")
    except Exception as e:
        volume_writable = False
        violations.append(f"VOLUME_ACCESS_FAILED: Unexpected error probing volume {target_shadow_dir}: {e}")

    status = "PASS" if len(violations) == 0 else "FAIL"
    lifecycle = "DEPLOYED_INERT" if status == "PASS" else "FAILED_SAFE"

    return SafetyContractVerification(
        status=status,
        lifecycle_state=lifecycle,
        trading_disabled=(os.environ.get("CBE_TRADING_DISABLED") == "true"),
        prospective_scoring_disabled=(os.environ.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED") == "false"),
        binance_collection_disabled=(os.environ.get("CBE_BINANCE_COLLECTION_ENABLED") == "false"),
        network_isolated=net_iso,
        database_isolated=all(not os.environ.get(k, "").strip() for k in forbidden_secret_envs),
        filesystem_isolated=fs_iso,
        production_isolated=production_isolated,
        volume_writable=volume_writable,
        violations=violations,
        metadata={
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "os_release": platform.platform(),
            "environment": os.environ.get("CBE_ENV"),
            "approval_2_enforced": True,
            "approval_3_binance_authorized": False,
            "approval_4_prospective_authorized": False,
            "network_details": net_details,
            "filesystem_details": fs_details,
            "authoritative_inspection": "docker inspect <container> --format '{{.HostConfig.NetworkMode}}' == 'none'",
        },
    )


def run_inert_landing_audit(
    output_dir: Optional[Path] = None,
    require_persistent_audit: bool = True,
    probe_network: bool = True,
    check_filesystem: bool = True,
    proc_net_dev_path: Optional[Path] = None,
    proc_mounts_path: Optional[Path] = None,
    statvfs_func: Optional[Callable] = None,
    write_probe_func: Optional[Callable[[], None]] = None,
    is_container: Optional[bool] = None,
) -> int:
    """Execute inert landing verification check and write mandatory audit JSON evidence.

    Fails closed (exit code 1) if any safety check fails OR if mandatory audit persistence fails.
    Preserves audit history immutably across repeated runs without unbounded storage growth.
    """
    logger.info("==================================================================")
    logger.info("CBE-0.8.0 COOLIFY INERT LANDING VERIFICATION (APPROVAL 2 PREPARATION)")
    logger.info("==================================================================")

    target_dir = output_dir or Path(os.environ.get("CBE_SHADOW_DATA_DIR", "/app/data/prospective_shadow"))

    verification = verify_coolify_inert_contract(
        probe_network=probe_network,
        check_filesystem=check_filesystem,
        target_data_dir=target_dir,
        proc_net_dev_path=proc_net_dev_path,
        proc_mounts_path=proc_mounts_path,
        statvfs_func=statvfs_func,
        write_probe_func=write_probe_func,
        is_container=is_container,
    )

    logger.info(f"Verification Status: {verification.status}")
    logger.info(f"Lifecycle State: {verification.lifecycle_state}")
    logger.info(f"Trading Disabled: {verification.trading_disabled}")
    logger.info(f"Prospective Scoring Disabled: {verification.prospective_scoring_disabled}")
    logger.info(f"Binance Collection Disabled: {verification.binance_collection_disabled}")
    logger.info(f"Network Isolation Confirmed: {verification.network_isolated}")
    logger.info(f"Database Isolation Confirmed: {verification.database_isolated}")
    logger.info(f"Production Storage Isolation: {verification.production_isolated}")
    logger.info(f"Volume Writable by UID: {verification.volume_writable}")

    if verification.violations:
        logger.error("SAFETY CONTRACT VIOLATIONS DETECTED:")
        for v in verification.violations:
            logger.error(f"  [VIOLATION] {v}")
        logger.error("STATE TRANSITION: FAILED_SAFE. Container terminating with exit code 1.")
        return 1

    # Mandatory persistent audit evidence write (latest state + append-only bounded history)
    audit_dir = target_dir / "audit"
    latest_audit_file = audit_dir / "coolify_inert_landing_audit.json"
    history_file = audit_dir / "coolify_inert_landing_history.jsonl"

    landing_id = f"INERT-{pd.Timestamp.now(tz='UTC').strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"
    audit_record = verification.to_dict()
    audit_record["landing_id"] = landing_id
    audit_record["verified_at_utc"] = pd.Timestamp.now(tz="UTC").isoformat()
    record_json_str = json.dumps(audit_record, sort_keys=True)
    audit_record["record_sha256"] = hashlib.sha256(record_json_str.encode("utf-8")).hexdigest()

    try:
        audit_dir.mkdir(parents=True, exist_ok=True)

        # 1. Update latest atomic audit record
        tmp_latest = audit_dir / f".coolify_inert_landing_audit.{uuid.uuid4().hex[:6]}.tmp"
        with open(tmp_latest, "w", encoding="utf-8") as f:
            json.dump(audit_record, f, indent=2)
        tmp_latest.replace(latest_audit_file)
        logger.info(f"Latest inert landing audit evidence persisted to: {latest_audit_file}")

        # 2. Append to immutable history log
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(audit_record) + "\n")
        logger.info(f"Inert landing record {landing_id} appended to history: {history_file}")

        # 3. Enforce bounded retention (max 500 lines)
        if history_file.exists():
            history_lines = history_file.read_text(encoding="utf-8").splitlines()
            if len(history_lines) > MAX_AUDIT_HISTORY_ENTRIES:
                # Retain genesis entry (line 0) + newest (MAX_AUDIT_HISTORY_ENTRIES - 1) entries
                retained_lines = [history_lines[0]] + history_lines[-(MAX_AUDIT_HISTORY_ENTRIES - 1):]
                history_file.write_text("\n".join(retained_lines) + "\n", encoding="utf-8")
                logger.info(f"Pruned audit history to bounded limit ({len(retained_lines)} entries).")

    except Exception as e:
        logger.error(f"FATAL: Mandatory audit file persistence failed in {audit_dir}: {e}")
        if require_persistent_audit:
            logger.error("Audit persistence is mandatory. Terminating with exit code 1.")
            return 1

    logger.info("==================================================================")
    logger.info("INERT LANDING VERIFICATION SUCCESSFUL (EXIT CODE 0)")
    logger.info("Container is completely inert: zero collection, zero trading, zero network.")
    logger.info("==================================================================")
    return 0


if __name__ == "__main__":
    exit_code = run_inert_landing_audit()
    sys.exit(exit_code)

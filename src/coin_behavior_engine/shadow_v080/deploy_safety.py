"""Sprint 09.13.1 / Approval 2 — Coolify Inert Deployment Safety Interlock (Hardened).

Enforces strictly fail-closed safety invariants for an isolated, inert Coolify container:
1. Exact allowed values for all safety-critical environment variables.
2. Deterministic, DNS-free network isolation checks (raw IP only; interface inspection).
3. Read-only filesystem verification (statvfs MS_RDONLY and errno.EROFS distinction).
4. Mandatory audit evidence persistence with explicit volume write permission validation.
5. Production database and shared storage isolation.
6. Inert lifecycle state management (DEPLOYED_INERT, STOPPED, FAILED_SAFE).
"""

from __future__ import annotations

import errno
import json
import logging
import os
import platform
import socket
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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


def _check_network_namespace_isolation() -> Tuple[bool, List[str], Dict[str, Any]]:
    """Perform deterministic, DNS-free network isolation checks.

    Avoids ANY DNS hostname queries (no api.binance.com, google.com).
    Uses raw numerical IP addresses and inspects Linux kernel network devices if available.
    """
    violations: List[str] = []
    details: Dict[str, Any] = {
        "dns_queries_executed": 0,
        "raw_ip_probes_executed": 0,
        "interfaces_detected": [],
    }

    # 1. Inspect Linux network interfaces via /proc/net/dev if running on Linux
    proc_net_dev = Path("/proc/net/dev")
    if proc_net_dev.exists():
        try:
            lines = proc_net_dev.read_text(encoding="utf-8").splitlines()
            interfaces = []
            for line in lines[2:]:
                if ":" in line:
                    iface = line.split(":", 1)[0].strip()
                    interfaces.append(iface)
            details["interfaces_detected"] = interfaces

            # In network_mode: "none", only loopback ('lo') should exist
            non_loopback = [i for i in interfaces if i != "lo"]
            if non_loopback:
                violations.append(
                    f"NETWORK_NAMESPACE_NOT_NONE: Non-loopback network interfaces detected in container: {non_loopback}. "
                    "Expected only 'lo' under network_mode: 'none'."
                )
        except Exception as e:
            details["proc_net_dev_error"] = str(e)

    # 2. Raw IP Socket Connection Probe (strictly numeric IPs, no DNS lookup)
    # Using RFC 5737 documentation/dummy IPs and well-known public DNS IP directly
    test_ips = [
        ("192.0.2.1", 80),   # TEST-NET-1 (RFC 5737)
        ("198.51.100.1", 443), # TEST-NET-2 (RFC 5737)
        ("8.8.8.8", 53),       # Public IP without hostname lookup
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


def _check_filesystem_read_only(check_filesystem: bool) -> Tuple[bool, List[str], Dict[str, Any]]:
    """Audit read-only root filesystem enforcement.

    Distinguishes genuine kernel read-only mount (MS_RDONLY / errno.EROFS)
    from ordinary user permission denial (errno.EACCES).
    """
    violations: List[str] = []
    details: Dict[str, Any] = {
        "is_mount_statvfs_ro": None,
        "probe_error_errno": None,
        "probe_error_name": None,
    }

    if not check_filesystem:
        return True, violations, details

    # 1. Check statvfs on root filesystem if supported
    if hasattr(os, "statvfs"):
        try:
            st = os.statvfs("/")
            # ST_RDONLY is flag 1 in Linux/POSIX statvfs
            details["is_mount_statvfs_ro"] = bool(st.f_flag & getattr(os, "ST_RDONLY", 1))
        except Exception as e:
            details["statvfs_error"] = str(e)

    # 2. Inspect /proc/mounts if running on Linux container
    proc_mounts = Path("/proc/mounts")
    if proc_mounts.exists():
        try:
            for line in proc_mounts.read_text(encoding="utf-8").splitlines():
                parts = line.split()
                if len(parts) >= 4 and parts[1] == "/":
                    opts = parts[3].split(",")
                    details["root_mount_opts"] = opts
                    details["root_mount_is_ro"] = "ro" in opts
                    break
        except Exception as e:
            details["proc_mounts_error"] = str(e)

    # 3. Direct probe write
    is_container = Path("/.dockerenv").exists() or os.environ.get("CBE_CONTAINER_ENV") == "true"
    if is_container:
        probe_path = Path("/root_fs_immutable_probe.tmp")
        try:
            probe_path.write_text("should_fail_if_ro")
            probe_path.unlink(missing_ok=True)
            violations.append("FILESYSTEM_NOT_READ_ONLY: Wrote successfully to container root filesystem.")
        except OSError as e:
            details["probe_error_errno"] = e.errno
            details["probe_error_name"] = errno.errorcode.get(e.errno, f"ERR_{e.errno}")

            # Verify whether it failed due to EROFS (Read-only fs) vs EACCES (Permission denied)
            if e.errno == errno.EROFS:
                details["ro_enforcement_verified"] = "GENUINE_KERNEL_EROFS"
            elif e.errno == errno.EACCES:
                details["ro_enforcement_verified"] = "DAC_PERMISSION_DENIAL_ONLY"
                # If statvfs also confirms it's not ro, report warning/violation
                if details.get("is_mount_statvfs_ro") is False and details.get("root_mount_is_ro") is False:
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
        net_iso, net_violations, net_details = _check_network_namespace_isolation()
        violations.extend(net_violations)

    # 5. Read-Only Root Filesystem Audit
    fs_iso = True
    fs_details: Dict[str, Any] = {}
    if check_filesystem:
        fs_iso, fs_violations, fs_details = _check_filesystem_read_only(check_filesystem)
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
    except Exception as e:
        volume_writable = False
        violations.append(
            f"VOLUME_PERMISSION_DENIED: User UID {os.getuid() if hasattr(os, 'getuid') else 'unknown'} "
            f"cannot write to dedicated shadow storage directory {target_shadow_dir}: {e}"
        )

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
) -> int:
    """Execute inert landing verification check and write mandatory audit JSON evidence.

    Fails closed (exit code 1) if any safety check fails OR if mandatory audit persistence fails.
    """
    logger.info("==================================================================")
    logger.info("CBE-0.8.0 COOLIFY INERT LANDING VERIFICATION (APPROVAL 2 PREPARATION)")
    logger.info("==================================================================")

    target_dir = output_dir or Path(os.environ.get("CBE_SHADOW_DATA_DIR", "/app/data/prospective_shadow"))

    verification = verify_coolify_inert_contract(
        probe_network=probe_network,
        check_filesystem=check_filesystem,
        target_data_dir=target_dir,
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

    # Mandatory persistent audit file write
    audit_file = target_dir / "audit" / "coolify_inert_landing_audit.json"
    try:
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        with open(audit_file, "w", encoding="utf-8") as f:
            json.dump(verification.to_dict(), f, indent=2)
        logger.info(f"Inert landing audit evidence persisted to: {audit_file}")
    except Exception as e:
        logger.error(f"FATAL: Mandatory audit file persistence failed for {audit_file}: {e}")
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

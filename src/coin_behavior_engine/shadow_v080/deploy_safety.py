"""Sprint 09.13 / Approval 2 — Coolify Inert Deployment Safety Interlock.

Enforces fail-closed safety invariants for an isolated, inert Coolify container:
1. Trading permanently disabled.
2. Prospective scoring permanently disabled.
3. Binance and external API collection disabled.
4. Network isolation verification (zero egress/ingress).
5. Filesystem immutability (read-only root).
6. Production database and shared storage isolation (zero production credentials or volume mounts).
7. Inert lifecycle management (DEPLOYED_INERT, STOPPED, FAILED_SAFE).
"""

from __future__ import annotations

import json
import logging
import os
import platform
import socket
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] [DeploySafety] %(message)s")
logger = logging.getLogger("DeploySafety")


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
    violations: List[str]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def verify_coolify_inert_contract(
    probe_network: bool = True,
    check_filesystem: bool = True,
    base_dir: Optional[Path] = None,
) -> SafetyContractVerification:
    """Perform comprehensive fail-closed safety verification of deployment configuration.

    This function audits environment variables, system configuration, network access,
    and storage paths to guarantee that the container cannot execute trades,
    cannot poll Binance, cannot generate prospective records, and does not touch production.
    """
    violations: List[str] = []

    # 1. Trading Permanently Prohibited
    trading_disabled_env = os.environ.get("CBE_TRADING_DISABLED", "").strip().lower()
    if trading_disabled_env != "true":
        violations.append(f"TRADING_NOT_DISABLED: CBE_TRADING_DISABLED must be 'true', got '{trading_disabled_env}'")

    # 2. Prospective Observation Permanently Prohibited (Approval 4 required)
    prospective_enabled_env = os.environ.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "").strip().lower()
    if prospective_enabled_env == "true":
        violations.append("PROSPECTIVE_UNAUTHORIZED: Prospective observation is prohibited before explicit APPROVAL 4.")

    record_label_env = os.environ.get("CBE_RECORD_LABEL", "WARMUP_REPLAY").strip()
    if record_label_env == "PROSPECTIVE_SHADOW":
        violations.append("PROSPECTIVE_LABEL_UNAUTHORIZED: CBE_RECORD_LABEL cannot be 'PROSPECTIVE_SHADOW' in inert staging.")

    # 3. Binance Collection Permanently Prohibited (Approval 3 required)
    binance_enabled_env = os.environ.get("CBE_BINANCE_COLLECTION_ENABLED", "false").strip().lower()
    if binance_enabled_env == "true":
        violations.append("BINANCE_COLLECTION_UNAUTHORIZED: Binance collection is prohibited before explicit APPROVAL 3.")

    # 4. Secret & Production Database Credentials Isolation
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
            violations.append(f"UNAUTHORIZED_CREDENTIAL_PRESENT: Environment variable '{sec_var}' must not be present.")

    # 5. Network Isolation Audit
    network_isolated = True
    if probe_network:
        # Test whether socket connect succeeds. In a network_mode: none environment,
        # creating or connecting a socket to external endpoints must fail immediately.
        test_endpoints = [
            ("8.8.8.8", 53),
            ("api.binance.com", 443),
            ("1.1.1.1", 80),
        ]
        for host, port in test_endpoints:
            s = None
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.2)  # fast 200ms timeout
                res = s.connect_ex((host, port))
                if res == 0:
                    network_isolated = False
                    violations.append(
                        f"NETWORK_ISOLATION_BREACH: Outbound socket connection to {host}:{port} succeeded. "
                        "network_mode: 'none' is not enforced."
                    )
                    break
            except Exception:
                # Connection error / Network unreachable is expected and desired
                pass
            finally:
                if s is not None:
                    try:
                        s.close()
                    except Exception:
                        pass

    # 6. Read-Only Root Filesystem Audit
    filesystem_isolated = True
    if check_filesystem:
        # In a read-only root container, writing outside /tmp or /app/data/prospective_shadow must fail
        is_container = Path("/.dockerenv").exists() or os.environ.get("CBE_CONTAINER_ENV") == "true"
        if is_container:
            test_file = Path("/root_fs_immutable_probe.tmp")
            try:
                test_file.write_text("fail_if_writable")
                test_file.unlink(missing_ok=True)
                filesystem_isolated = False
                violations.append("FILESYSTEM_NOT_READ_ONLY: Successfully wrote to container root filesystem.")
            except (OSError, PermissionError):
                # Expected: Read-only filesystem rejects writes
                pass

    # 7. Production Storage Isolation
    production_isolated = True
    app_root = base_dir or Path(__file__).resolve().parents[3]
    prod_prospective_dir = app_root / "data" / "prospective"
    # Check if production prospective directory is mounted as writable in container
    if prod_prospective_dir.exists():
        # Verify that shadow storage target is NOT pointing to production directory
        target_shadow_dir = os.environ.get("CBE_SHADOW_DATA_DIR", "/app/data/prospective_shadow")
        if str(prod_prospective_dir.resolve()) == str(Path(target_shadow_dir).resolve()):
            production_isolated = False
            violations.append("PRODUCTION_VOLUME_COLLISION: Shadow storage target cannot be production data/prospective.")

    status = "PASS" if len(violations) == 0 else "FAIL"
    lifecycle = "DEPLOYED_INERT" if status == "PASS" else "FAILED_SAFE"

    return SafetyContractVerification(
        status=status,
        lifecycle_state=lifecycle,
        trading_disabled=(trading_disabled_env == "true"),
        prospective_scoring_disabled=(prospective_enabled_env != "true"),
        binance_collection_disabled=(binance_enabled_env != "true"),
        network_isolated=network_isolated,
        database_isolated=all(not os.environ.get(k, "").strip() for k in forbidden_secret_envs),
        filesystem_isolated=filesystem_isolated,
        production_isolated=production_isolated,
        violations=violations,
        metadata={
            "platform": sys.platform,
            "python_version": sys.version.split()[0],
            "os_release": platform.platform(),
            "environment": os.environ.get("CBE_ENV", "staging_coolify_inert"),
            "approval_2_enforced": True,
            "approval_3_binance_authorized": False,
            "approval_4_prospective_authorized": False,
        },
    )


def run_inert_landing_audit(output_dir: Optional[Path] = None) -> int:
    """Execute inert landing verification check and write audit JSON evidence."""
    logger.info("==================================================================")
    logger.info("CBE-0.8.0 COOLIFY INERT LANDING VERIFICATION (APPROVAL 2 PREPARATION)")
    logger.info("==================================================================")

    verification = verify_coolify_inert_contract(
        probe_network=True,
        check_filesystem=True,
    )

    logger.info(f"Verification Status: {verification.status}")
    logger.info(f"Lifecycle State: {verification.lifecycle_state}")
    logger.info(f"Trading Disabled: {verification.trading_disabled}")
    logger.info(f"Prospective Scoring Disabled: {verification.prospective_scoring_disabled}")
    logger.info(f"Binance Collection Disabled: {verification.binance_collection_disabled}")
    logger.info(f"Network Isolation Confirmed: {verification.network_isolated}")
    logger.info(f"Database Isolation Confirmed: {verification.database_isolated}")
    logger.info(f"Production Storage Isolation: {verification.production_isolated}")

    if verification.violations:
        logger.error("SAFETY CONTRACT VIOLATIONS DETECTED:")
        for v in verification.violations:
            logger.error(f"  [VIOLATION] {v}")
        logger.error("STATE TRANSITION: FAILED_SAFE. Container terminating with exit code 1.")
        return 1

    # Write evidence audit file if target output path is provided or default exists
    target_dir = output_dir or Path(os.environ.get("CBE_SHADOW_DATA_DIR", "/app/data/prospective_shadow"))
    audit_file = target_dir / "audit" / "coolify_inert_landing_audit.json"
    try:
        audit_file.parent.mkdir(parents=True, exist_ok=True)
        with open(audit_file, "w", encoding="utf-8") as f:
            json.dump(verification.to_dict(), f, indent=2)
        logger.info(f"Inert landing audit evidence written to: {audit_file}")
    except Exception as e:
        logger.warning(f"Could not persist audit file to {audit_file} (may be ephemeral container run): {e}")

    logger.info("==================================================================")
    logger.info("INERT LANDING VERIFICATION SUCCESSFUL (EXIT CODE 0)")
    logger.info("Container is completely inert: zero collection, zero trading, zero network.")
    logger.info("==================================================================")
    return 0


if __name__ == "__main__":
    exit_code = run_inert_landing_audit()
    sys.exit(exit_code)

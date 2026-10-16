#!/usr/bin/env python3
"""CBE-0.8.0 Live Capture Deployment Preflight & Drift Verification.

Sprint 11.02D: Durable Gap Recovery, Evidence Integrity & Deployment Continuity.

Performs strictly read-only, non-mutating preflight checks to guarantee:
1. Dockerfile alignment: deploy/shadow_v080/Dockerfile.staging
2. Entrypoint alignment: /app/entrypoint_live_capture.sh
3. Persistent volume alignment: zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data mounted at /app/data/live_capture:rw
4. Approval 3 & Approval 4 safety interlocks:
   - CBE_APPROVAL_3_AUTHORIZED=true (for live capture)
   - CBE_APPROVAL_4_AUTHORIZED=false (strictly prohibited)
   - CBE_TRADING_DISABLED=true (trading permanently disabled)
   - CBE_PROSPECTIVE_OBSERVATION_ENABLED=false (scoring disabled)
5. Compose configuration drift detection against expected defaults.
6. Fails closed with non-zero exit code if ANY mismatch is detected.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPECTED_DOCKERFILE = REPO_ROOT / "deploy" / "shadow_v080" / "Dockerfile.staging"
EXPECTED_ENTRYPOINT = REPO_ROOT / "deploy" / "shadow_v080" / "entrypoint_live_capture.sh"
LIVE_CAPTURE_COMPOSE = REPO_ROOT / "deploy" / "shadow_v080" / "docker-compose.coolify-live-capture.yaml"
STAGING_COMPOSE = REPO_ROOT / "deploy" / "staging" / "docker-compose.market-intelligence-staging.yaml"

EXPECTED_VOLUME_NAME = "zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data"
EXPECTED_CONTAINER_MOUNT = "/app/data/live_capture"
EXPECTED_ENTRYPOINT_STR = "/app/entrypoint_live_capture.sh"

SECRET_PATTERNS = {"KEY", "SECRET", "PASS", "TOKEN", "CREDENTIAL", "AUTH"}


def redact_secrets(env_dict: Dict[str, str]) -> Dict[str, str]:
    """Return a copy of environment variables with sensitive values redacted."""
    redacted: Dict[str, str] = {}
    for k, v in env_dict.items():
        if any(pat in k.upper() for pat in SECRET_PATTERNS):
            redacted[k] = "[REDACTED]"
        else:
            redacted[k] = v
    return redacted


def verify_deployment_preflight(
    compose_path: Optional[Path] = None,
    env_vars: Optional[Dict[str, str]] = None,
) -> Tuple[bool, List[str]]:
    """Run read-only preflight verification checks.

    Returns:
        (is_valid, violations)
    """
    violations: List[str] = []
    compose_file = Path(compose_path) if compose_path else LIVE_CAPTURE_COMPOSE

    # 1. Verify existence of required build files if inspecting repository compose
    # For standalone VPS compose paths, only verify build files if local to repo
    if EXPECTED_DOCKERFILE.exists() is False and compose_file == LIVE_CAPTURE_COMPOSE:
        violations.append(f"MISSING_DOCKERFILE: Expected {EXPECTED_DOCKERFILE} does not exist.")
    if EXPECTED_ENTRYPOINT.exists() is False and compose_file == LIVE_CAPTURE_COMPOSE:
        violations.append(f"MISSING_ENTRYPOINT: Expected {EXPECTED_ENTRYPOINT} does not exist.")

    if not compose_file.exists():
        violations.append(f"MISSING_COMPOSE_FILE: Expected {compose_file} does not exist.")
        return False, violations

    # 2. Inspect Compose configuration
    try:
        with open(compose_file, "r", encoding="utf-8") as f:
            compose_data = yaml.safe_load(f)
    except Exception as e:
        violations.append(f"INVALID_COMPOSE_YAML: {e}")
        return False, violations

    services = compose_data.get("services", {}) if isinstance(compose_data, dict) else {}
    if not services:
        violations.append("NO_SERVICES: No services defined in Compose configuration.")
        return False, violations

    # Service resolution: match by service name or by volume mount
    cap_svc: Optional[Dict[str, Any]] = None
    matched_svc_name: Optional[str] = None

    for svc_name, svc_cfg in services.items():
        if not isinstance(svc_cfg, dict):
            continue
        # Check explicit service names first
        if svc_name in ("cbe-080-live-capture", "cbe_080_coolify_live_capture", "live-capture"):
            cap_svc = svc_cfg
            matched_svc_name = svc_name
            break
        # Otherwise check if service mounts the live capture directory
        vols = svc_cfg.get("volumes", [])
        for v in vols:
            v_target = ""
            if isinstance(v, str):
                parts = v.split(":")
                v_target = parts[1] if len(parts) > 1 else parts[0]
            elif isinstance(v, dict):
                v_target = v.get("target", "")
            if v_target == EXPECTED_CONTAINER_MOUNT:
                cap_svc = svc_cfg
                matched_svc_name = svc_name
                break
        if cap_svc is not None:
            break

    if not cap_svc:
        violations.append(
            "MISSING_SERVICE: No service found matching 'cbe-080-live-capture' or mounting '/app/data/live_capture'."
        )
        return False, violations

    # Dockerfile reference check (if build block is present)
    build_cfg = cap_svc.get("build")
    if isinstance(build_cfg, dict):
        df = build_cfg.get("dockerfile", "")
        if "Dockerfile.staging" not in df:
            violations.append(f"DOCKERFILE_MISMATCH: Compose specifies '{df}', expected 'deploy/shadow_v080/Dockerfile.staging'.")
    elif isinstance(build_cfg, str):
        if "Dockerfile.staging" not in build_cfg:
            violations.append(f"DOCKERFILE_MISMATCH: Build context '{build_cfg}' does not specify Dockerfile.staging.")

    # Entrypoint check
    entrypoint = cap_svc.get("entrypoint", [])
    ep_str = entrypoint[0] if isinstance(entrypoint, list) and entrypoint else str(entrypoint)
    if EXPECTED_ENTRYPOINT_STR not in ep_str:
        violations.append(f"ENTRYPOINT_MISMATCH: Compose entrypoint is '{ep_str}', expected '{EXPECTED_ENTRYPOINT_STR}'.")

    # Volume mount and mode check
    volumes = cap_svc.get("volumes", [])
    found_cap_mount = False
    mounted_vol_source = ""
    mount_mode = "rw"

    for v in volumes:
        v_source = ""
        v_target = ""
        v_mode = "rw"
        if isinstance(v, str):
            parts = v.split(":")
            v_source = parts[0]
            v_target = parts[1] if len(parts) > 1 else ""
            v_mode = parts[2] if len(parts) > 2 else "rw"
        elif isinstance(v, dict):
            v_source = v.get("source", "")
            v_target = v.get("target", "")
            v_mode = "ro" if v.get("read_only", False) else "rw"

        if v_target == EXPECTED_CONTAINER_MOUNT:
            found_cap_mount = True
            mounted_vol_source = v_source
            mount_mode = v_mode
            break

    if not found_cap_mount:
        violations.append(f"VOLUME_MOUNT_MISSING: Service lacks '{EXPECTED_CONTAINER_MOUNT}' volume mount.")
    else:
        if mount_mode != "rw" and "ro" in mount_mode.lower():
            violations.append(f"VOLUME_READONLY_ERROR: Mount at '{EXPECTED_CONTAINER_MOUNT}' must be read/write (got mode='{mount_mode}').")

        # Resolve named volume source against top-level volumes declaration
        declared_vols = compose_data.get("volumes", {}) if isinstance(compose_data, dict) else {}
        resolved_name = mounted_vol_source
        if isinstance(declared_vols, dict) and mounted_vol_source in declared_vols:
            vol_def = declared_vols[mounted_vol_source]
            if isinstance(vol_def, dict) and "name" in vol_def:
                resolved_name = str(vol_def["name"])

        if EXPECTED_VOLUME_NAME not in resolved_name:
            violations.append(
                f"VOLUME_NAME_MISMATCH: Mounted volume source '{mounted_vol_source}' resolves to '{resolved_name}', expected '{EXPECTED_VOLUME_NAME}'."
            )

    # Top-level named volume declaration check
    declared_vols = compose_data.get("volumes", {})
    if isinstance(declared_vols, dict):
        found_vol_target = False
        for v_key, v_def in declared_vols.items():
            if isinstance(v_def, dict):
                name_val = str(v_def.get("name", ""))
                if EXPECTED_VOLUME_NAME in name_val:
                    found_vol_target = True
                    break
            elif isinstance(v_key, str) and EXPECTED_VOLUME_NAME in v_key:
                found_vol_target = True
                break
        if not found_vol_target:
            violations.append(f"VOLUME_NAME_DRIFT: Declared top-level volumes do not reference '{EXPECTED_VOLUME_NAME}'.")
    else:
        violations.append("MISSING_VOLUMES_SECTION: Top-level 'volumes' section is missing or invalid.")

    # Environment safety checks
    env_source = env_vars if env_vars is not None else {}
    compose_env: Dict[str, str] = {}
    c_env = cap_svc.get("environment", [])
    if isinstance(c_env, list):
        for item in c_env:
            if isinstance(item, str) and "=" in item:
                k, v = item.split("=", 1)
                compose_env[k.strip()] = v.strip()
    elif isinstance(c_env, dict):
        compose_env = {str(k): str(v) for k, v in c_env.items()}

    active_env = {**compose_env, **env_source}

    if active_env.get("CBE_TRADING_DISABLED") != "true":
        violations.append("SAFETY_VIOLATION: CBE_TRADING_DISABLED must be 'true'.")

    if active_env.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED") != "false":
        violations.append("SAFETY_VIOLATION: CBE_PROSPECTIVE_OBSERVATION_ENABLED must be 'false'.")

    if active_env.get("CBE_APPROVAL_4_AUTHORIZED") == "true":
        violations.append("SAFETY_VIOLATION: CBE_APPROVAL_4_AUTHORIZED must not be 'true'.")

    if active_env.get("CBE_APPROVAL_3_AUTHORIZED") != "true":
        violations.append("APPROVAL3_UNAUTHORIZED: CBE_APPROVAL_3_AUTHORIZED must be 'true' for live capture.")

    return len(violations) == 0, violations


def main(args: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="verify_deployment_preflight.py",
        description=(
            "CBE-0.8.0 Live Capture Deployment Preflight & Drift Verification Tool.\n"
            "Performs strictly read-only, non-mutating validation of Docker Compose files, "
            "verifying Dockerfile, entrypoint, persistent volume mount (/app/data/live_capture:rw), "
            "Approval 3/4 interlocks, and safety flags."
        ),
    )
    parser.add_argument(
        "--compose-path",
        type=str,
        default=None,
        help="Path to docker-compose file to verify (default: deploy/shadow_v080/docker-compose.coolify-live-capture.yaml)",
    )

    parsed = parser.parse_args(args)
    compose_path = Path(parsed.compose_path) if parsed.compose_path else None

    print("==================================================================")
    print("CBE-0.8.0 LIVE CAPTURE: READ-ONLY DEPLOYMENT PREFLIGHT AUDIT")
    if compose_path:
        print(f"TARGET COMPOSE: {compose_path}")
    else:
        print(f"TARGET COMPOSE: {LIVE_CAPTURE_COMPOSE} (default)")
    print("==================================================================")

    is_valid, violations = verify_deployment_preflight(compose_path=compose_path)
    if not is_valid:
        print("[PREFLIGHT FAILED] Configuration drift or safety violations detected:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print("[PREFLIGHT PASSED] All Dockerfile, volume, entrypoint, and safety interlocks verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())


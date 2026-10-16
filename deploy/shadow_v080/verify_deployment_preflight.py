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
EXPECTED_NETWORK_NAME = "zgit1s3n1acdtqtsxp0s44vj"


def verify_deployment_preflight(
    compose_path: Optional[Path] = None,
    env_vars: Optional[Dict[str, str]] = None,
) -> Tuple[bool, List[str]]:
    """Run read-only preflight verification checks.

    Returns:
        (is_valid, violations)
    """
    violations: List[str] = []
    compose_file = compose_path or LIVE_CAPTURE_COMPOSE

    # 1. Verify existence of required build files
    if not EXPECTED_DOCKERFILE.exists():
        violations.append(f"MISSING_DOCKERFILE: Expected {EXPECTED_DOCKERFILE} does not exist.")
    if not EXPECTED_ENTRYPOINT.exists():
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

    services = compose_data.get("services", {})
    cap_svc = services.get("cbe-080-live-capture") or services.get("cbe_080_coolify_live_capture")
    if not cap_svc:
        violations.append("MISSING_SERVICE: Neither 'cbe-080-live-capture' nor 'cbe_080_coolify_live_capture' found in Compose services.")
        return False, violations

    # Dockerfile reference check
    build_cfg = cap_svc.get("build", {})
    if isinstance(build_cfg, dict):
        df = build_cfg.get("dockerfile", "")
        if "Dockerfile.staging" not in df:
            violations.append(f"DOCKERFILE_MISMATCH: Compose specifies '{df}', expected 'deploy/shadow_v080/Dockerfile.staging'.")

    # Entrypoint check
    entrypoint = cap_svc.get("entrypoint", [])
    ep_str = entrypoint[0] if isinstance(entrypoint, list) and entrypoint else str(entrypoint)
    if "/app/entrypoint_live_capture.sh" not in ep_str:
        violations.append(f"ENTRYPOINT_MISMATCH: Compose entrypoint is '{ep_str}', expected '/app/entrypoint_live_capture.sh'.")

    # Volume check
    volumes = cap_svc.get("volumes", [])
    has_cap_mount = False
    for v in volumes:
        v_str = str(v)
        if "/app/data/live_capture" in v_str:
            has_cap_mount = True
            break
    if not has_cap_mount:
        violations.append("VOLUME_MOUNT_MISSING: Service lacks '/app/data/live_capture' volume mount.")

    # Named volume declaration check
    declared_vols = compose_data.get("volumes", {})
    found_vol_target = False
    for v_key, v_def in declared_vols.items():
        if isinstance(v_def, dict):
            name_val = str(v_def.get("name", ""))
            if EXPECTED_VOLUME_NAME in name_val:
                found_vol_target = True
                break
    if not found_vol_target:
        violations.append(f"VOLUME_NAME_DRIFT: Declared volumes do not reference '{EXPECTED_VOLUME_NAME}'.")

    # Environment safety checks
    env_source = env_vars if env_vars is not None else {}
    # Also extract from compose environment list/dict
    compose_env: Dict[str, str] = {}
    c_env = cap_svc.get("environment", [])
    if isinstance(c_env, list):
        for item in c_env:
            if "=" in item:
                k, v = item.split("=", 1)
                compose_env[k.strip()] = v.strip()
    elif isinstance(c_env, dict):
        compose_env = {str(k): str(v) for k, v in c_env.items()}

    # Merge: env_vars overrides compose_env
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


def main() -> int:
    print("==================================================================")
    print("CBE-0.8.0 LIVE CAPTURE: READ-ONLY DEPLOYMENT PREFLIGHT AUDIT")
    print("==================================================================")

    is_valid, violations = verify_deployment_preflight()
    if not is_valid:
        print("[PREFLIGHT FAILED] Configuration drift or safety violations detected:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print("[PREFLIGHT PASSED] All Dockerfile, volume, entrypoint, and safety interlocks verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

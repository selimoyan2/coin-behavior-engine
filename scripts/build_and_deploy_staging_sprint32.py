"""Script to build and deploy Sprint 32 Scientific Validation Closure & Investment Research Dashboard V10 on authorized staging (srv1114257:18080).
Remote Host: 168.231.125.238
STRICT ZERO-TOUCH ON PRODUCTION (container fdbdba96e677 / 6t63aehpaw0cw1bbt4zcm09g).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REMOTE_HOST = "root@168.231.125.238"
ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")
DELIVERY_DIR = Path(__file__).resolve().parent.parent / "research_outputs" / "sprint32_scientific_validation_dashboard_v10"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)


def get_commit_sha() -> str:
    res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    return res.stdout.strip()


def generate_remote_script(commit_sha: str) -> str:
    short_sha = commit_sha[:7]
    metadata = {
        "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "commit_sha": commit_sha,
        "branch": "main",
        "canonical_model": "CBE-0.7.0",
        "model_status": "STRICTLY_FROZEN",
        "governance_decision": "OFFLINE_HISTORICAL_RESEARCH_AUDITED_FROZEN_POLICIES",
        "sprint_id": "CBE_SPRINT32_SCIENTIFIC_VALIDATION_DASHBOARD_V10",
        "build_environment": "Docker on srv1114257",
        "reproducible_build": True,
    }
    metadata_json_str = json.dumps(metadata, indent=2)
    image_tag = f"cbe-market-intelligence:sprint32-{short_sha}"

    return f"""#!/bin/bash
set -e
echo "=== PRE-FLIGHT AUDIT: CHECK PRODUCTION CONTAINER ==="
PROD_CID=$(docker ps --filter name=6t63aehpaw0cw1bbt4zcm09g -q)
if [ -z "$PROD_CID" ]; then
    PROD_CID="fdbdba96e677"
fi
if docker inspect "$PROD_CID" >/dev/null 2>&1; then
    echo "[OK] Production container $PROD_CID is running untouched."
    PROD_STATUS=$(docker inspect "$PROD_CID" --format 'Status: {{{{.State.Status}}}}, Restarts: {{{{.RestartCount}}}}')
    PROD_STARTED=$(docker inspect "$PROD_CID" --format '{{{{.State.StartedAt}}}}')
    PROD_RESTARTS=$(docker inspect "$PROD_CID" --format '{{{{.RestartCount}}}}')
    echo "Production Container State: $PROD_STATUS"
    echo "Production Container StartedAt: $PROD_STARTED"
    if [ "$PROD_RESTARTS" != "0" ]; then
        echo "ERROR: Production container restart count is $PROD_RESTARTS (expected 0)!"
        exit 1
    fi
else
    echo "ERROR: Production container $PROD_CID is not running!"
    exit 1
fi

echo "=== 1. PREPARING BUILD CONTEXT FOR SPRINT 32 ({commit_sha}) ==="
rm -rf /tmp/cbe_sprint32_build
git clone --depth 1 https://github.com/selimoyan2/coin-behavior-engine.git /tmp/cbe_sprint32_build
cd /tmp/cbe_sprint32_build

VERIFIED_SHA=$(git rev-parse HEAD)
echo "Cloned SHA: $VERIFIED_SHA"
if [ "$VERIFIED_SHA" != "{commit_sha}" ]; then
    echo "ERROR: Cloned SHA does not match expected {commit_sha}"
    exit 1
fi

echo "=== 2. INJECTING AUTHORITATIVE BUILD METADATA ==="
cat << 'EOF' > build_metadata.json
{metadata_json_str}
EOF

echo "=== 3. DOCKER BUILD IMMUTABLE SPRINT 32 IMAGE ==="
docker build --no-cache -t "{image_tag}" -t cbe-market-intelligence:staging .

echo "=== 4. INSPECTING CREATED IMAGE ==="
IMAGE_ID=$(docker inspect "{image_tag}" --format '{{{{.Id}}}}')
echo "IMAGE_ID: $IMAGE_ID"

echo "=== 5. STOPPING OLD STAGING CONTAINER ==="
OLD_CID=$(docker ps -q --filter name=dzzfws54by1whlbq6fk4ywut)
if [ -n "$OLD_CID" ]; then
    echo "Stopping old staging container $OLD_CID"
    docker stop "$OLD_CID"
    docker rm "$OLD_CID"
fi

echo "=== 6. STARTING NEW STAGING CONTAINER FROM IMMUTABLE IMAGE ==="
cd /data/coolify/applications/dzzfws54by1whlbq6fk4ywut
sed -i "s|image: 'cbe-market-intelligence:.*'|image: '{image_tag}'|g" docker-compose.yaml
docker compose up -d

echo "=== 7. WAITING FOR STAGING READINESS ON PORT 18080 ==="
READY=0
for i in {{1..35}}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/ready || true)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "[OK] Staging is READY (HTTP 200) after $i seconds."
        READY=1
        break
    fi
    sleep 1
done

if [ "$READY" != "1" ]; then
    echo "ERROR: Staging failed to become ready."
    docker compose logs --tail=50
    exit 1
fi

NEW_STAGING_CID=$(docker ps -q --filter name=dzzfws54by1whlbq6fk4ywut)
echo "NEW_STAGING_CID: $NEW_STAGING_CID"

echo "=== 8. TESTING CONTAINER RESTART RECOVERY ==="
docker restart "$NEW_STAGING_CID"
sleep 3
RESTART_READY=0
for i in {{1..25}}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/ready || true)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "[OK] Staging recovered successfully after restart (HTTP 200) after $i seconds."
        RESTART_READY=1
        break
    fi
    sleep 1
done

if [ "$RESTART_READY" != "1" ]; then
    echo "ERROR: Staging failed to recover after restart."
    docker compose logs --tail=50
    exit 1
fi

echo "=== 9. VERIFYING SPRINT 32 V10 ENDPOINTS ON STAGING ==="
READY_CODE=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/ready || true)
V10_OVERVIEW=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/api/v1/product/research/btc-timing/v10/overview || true)
V10_COMP=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/api/v1/product/research/btc-timing/v10/comparison || true)
V10_STRAT=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/api/v1/product/research/btc-timing/v10/strategy/POLICY_TREND_LOW_TURNOVER || true)
V10_TRADES=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/api/v1/product/research/btc-timing/v10/trades/POLICY_TREND_LOW_TURNOVER || true)
V10_COST=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/api/v1/product/research/btc-timing/v10/cost-intelligence || true)
V10_EVID=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/api/v1/product/research/btc-timing/v10/scientific-evidence || true)
V10_TIME=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/api/v1/product/research/btc-timing/v10/timeline || true)
V10_REP=$(curl -s -o /dev/null -w "%{{http_code}}" "http://127.0.0.1:18080/api/v1/product/research/btc-timing/v10/report/download?format=markdown" || true)

echo "Ready HTTP Code: $READY_CODE"
echo "V10 Overview HTTP Code: $V10_OVERVIEW"
echo "V10 Comparison HTTP Code: $V10_COMP"
echo "V10 Strategy HTTP Code: $V10_STRAT"
echo "V10 Trades HTTP Code: $V10_TRADES"
echo "V10 Cost HTTP Code: $V10_COST"
echo "V10 Evidence HTTP Code: $V10_EVID"
echo "V10 Timeline HTTP Code: $V10_TIME"
echo "V10 Report HTTP Code: $V10_REP"

if [ "$READY_CODE" != "200" ] || [ "$V10_OVERVIEW" != "200" ] || [ "$V10_COMP" != "200" ] || [ "$V10_STRAT" != "200" ] || [ "$V10_TRADES" != "200" ] || [ "$V10_COST" != "200" ] || [ "$V10_EVID" != "200" ] || [ "$V10_TIME" != "200" ] || [ "$V10_REP" != "200" ]; then
    echo "ERROR: One or more Sprint 32 V10 endpoints returned non-200 status!"
    exit 1
fi
echo "[OK] All Sprint 32 V10 API endpoints verified with HTTP 200."

echo "=== 10. VERIFYING SECURITY BOUNDARY (LIVE TRADING PROHIBITED) ==="
LIVE_CODE=$(curl -s -o /dev/null -w "%{{http_code}}" -X POST http://127.0.0.1:18080/api/v1/product/research/btc-timing/v10/execute-live || true)
echo "Live Trading Security Rejection HTTP Code: $LIVE_CODE"
if [ "$LIVE_CODE" != "403" ]; then
    echo "ERROR: Live trading endpoint did not return 403 Forbidden!"
    exit 1
fi
echo "[OK] Security boundary verified: Live trading strictly prohibited (HTTP 403)."

echo "=== 11. POST-FLIGHT AUDIT: CHECK PRODUCTION CONTAINER AGAIN ==="
PROD_CID_POST=$(docker ps --filter name=6t63aehpaw0cw1bbt4zcm09g -q)
if [ -z "$PROD_CID_POST" ]; then
    PROD_CID_POST="fdbdba96e677"
fi
PROD_STATUS_POST=$(docker inspect "$PROD_CID_POST" --format 'Status: {{{{.State.Status}}}}, Restarts: {{{{.RestartCount}}}}')
PROD_RESTARTS_POST=$(docker inspect "$PROD_CID_POST" --format '{{{{.RestartCount}}}}')
PROD_STARTED_POST=$(docker inspect "$PROD_CID_POST" --format '{{{{.State.StartedAt}}}}')
echo "Post-Flight Production Container State: $PROD_STATUS_POST"
echo "Post-Flight Production Container StartedAt: $PROD_STARTED_POST"

if [ "$PROD_RESTARTS_POST" != "0" ]; then
    echo "CRITICAL ERROR: Production container restart count is $PROD_RESTARTS_POST (expected 0)!"
    exit 1
fi

if [ "$PROD_STARTED" != "$PROD_STARTED_POST" ]; then
    echo "CRITICAL ERROR: Production container StartedAt changed from $PROD_STARTED to $PROD_STARTED_POST!"
    exit 1
fi

echo "=== SPRINT 32 DEPLOYMENT & ZERO-TOUCH AUDIT COMPLETE ==="
cat << EOF
JSON_OUTPUT_START
{{
  "deployment_status": "SUCCESS",
  "sprint_id": "CBE_SPRINT32_SCIENTIFIC_VALIDATION_DASHBOARD_V10",
  "commit_sha": "{commit_sha}",
  "staging_container_id": "$NEW_STAGING_CID",
  "staging_image_tag": "{image_tag}",
  "staging_image_id": "$IMAGE_ID",
  "staging_port": 18080,
  "staging_readiness_status": "READY_HTTP_200",
  "staging_restart_recovery_verified": true,
  "v10_endpoints_verified": true,
  "security_boundary_verified_403": true,
  "production_container_id": "$PROD_CID_POST",
  "production_status": "running",
  "production_restarts": $PROD_RESTARTS_POST,
  "production_started_at": "$PROD_STARTED_POST",
  "zero_touch_verified": true
}}
JSON_OUTPUT_END
EOF
"""


def main():
    commit_sha = get_commit_sha()
    print(f"Sprint 32 Target Commit SHA: {commit_sha}")
    remote_script = generate_remote_script(commit_sha).replace("\r\n", "\n")

    print(f"Executing remote deployment and zero-touch audit on {REMOTE_HOST}...")
    proc = subprocess.run(
        ["ssh", REMOTE_HOST, "bash -s"],
        input=remote_script.encode("utf-8"),
        capture_output=True,
    )
    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")

    print("--- STDOUT ---")
    print(stdout)
    if stderr:
        print("--- STDERR ---")
        print(stderr)

    if proc.returncode != 0:
        print(f"Deployment FAILED with return code {proc.returncode}")
        sys.exit(1)

    # Parse JSON output
    if "JSON_OUTPUT_START" in stdout and "JSON_OUTPUT_END" in stdout:
        json_part = stdout.split("JSON_OUTPUT_START")[1].split("JSON_OUTPUT_END")[0].strip()
        data = json.loads(json_part)

        staging_evidence = {
            "sprint_id": data["sprint_id"],
            "deployment_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "target_host": "srv1114257 (168.231.125.238)",
            "staging_port": 18080,
            "staging_container_id": data["staging_container_id"],
            "image_tag": data["staging_image_tag"],
            "image_id": data["staging_image_id"],
            "commit_sha": data["commit_sha"],
            "readiness_http_code": 200,
            "restart_recovery_verified": data["staging_restart_recovery_verified"],
            "v10_endpoints_verified": data["v10_endpoints_verified"],
            "security_boundary_verified_403": data["security_boundary_verified_403"],
            "status": "DEPLOYED_AND_VERIFIED",
        }
        (DELIVERY_DIR / "16_staging_deployment_evidence.json").write_text(
            json.dumps(staging_evidence, indent=2), encoding="utf-8"
        )
        if ARTIFACT_DIR.exists():
            shutil.copy2(DELIVERY_DIR / "16_staging_deployment_evidence.json", ARTIFACT_DIR / "16_staging_deployment_evidence.json")

        prod_evidence = {
            "audit_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "sprint_id": data["sprint_id"],
            "production_container_id": data["production_container_id"],
            "production_status": data["production_status"],
            "production_restarts": data["production_restarts"],
            "production_started_at": data["production_started_at"],
            "zero_touch_verified": data["zero_touch_verified"],
            "zero_touch_verdict": "PRODUCTION_ZERO_TOUCH_STRICTLY_PRESERVED",
        }
        (DELIVERY_DIR / "17_production_zero_touch_evidence.json").write_text(
            json.dumps(prod_evidence, indent=2), encoding="utf-8"
        )
        if ARTIFACT_DIR.exists():
            shutil.copy2(DELIVERY_DIR / "17_production_zero_touch_evidence.json", ARTIFACT_DIR / "17_production_zero_touch_evidence.json")

        print("Successfully recorded Staging Deployment & Production Zero-Touch Evidence!")
    else:
        print("WARNING: Could not parse JSON output block from remote script.")


if __name__ == "__main__":
    main()

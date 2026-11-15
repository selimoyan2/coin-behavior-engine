"""
Script to build and deploy Sprint 30 BTC Timing Strategy Optimization, Accounting Reconciliation & Scientific Validation on authorized staging (srv1114257:18080).
Remote Host: 168.231.125.238
STRICT ZERO-TOUCH ON PRODUCTION (container fdbdba96e677 / 6t63aehpaw0cw1bbt4zcm09g).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REMOTE_HOST = "root@168.231.125.238"
ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")


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
        "governance_decision": "TECHNICAL_NO_GO",
        "sprint_id": "CBE_SPRINT30_BTC_TIMING_OPTIMIZATION",
        "build_environment": "Docker on srv1114257",
        "reproducible_build": True,
    }
    metadata_json_str = json.dumps(metadata, indent=2)
    image_tag = f"cbe-market-intelligence:sprint30-{short_sha}"

    return f"""#!/bin/bash
set -e
echo "=== PRE-FLIGHT AUDIT: CHECK PRODUCTION CONTAINER ==="
PROD_CID=$(docker ps --filter name=6t63aehpaw0cw1bbt4zcm09g -q)
if [ -z "$PROD_CID" ]; then
    PROD_CID="fdbdba96e677"
fi
if docker ps --format '{{{{.ID}}}}' | grep -q "$PROD_CID"; then
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

echo "=== 1. PREPARING BUILD CONTEXT FOR SPRINT 30 ({commit_sha}) ==="
rm -rf /tmp/cbe_sprint30_build
git clone --depth 1 https://github.com/selimoyan2/coin-behavior-engine.git /tmp/cbe_sprint30_build
cd /tmp/cbe_sprint30_build

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

echo "=== 3. DOCKER BUILD IMMUTABLE SPRINT 30 IMAGE ==="
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
for i in {{1..30}}; do
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
for i in {{1..20}}; do
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

echo "=== 9. VERIFYING BTC TIMING SPRINT 30 API ENDPOINTS ON STAGING ==="
OVERVIEW_CODE=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/api/v1/product/research/btc-timing/overview || true)
PARITY_CODE=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/api/v1/product/research/btc-timing/parity-audit || true)
ACCR_CODE=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/api/v1/product/research/btc-timing/accounting-reconciliation || true)
COST_CODE=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/api/v1/product/research/btc-timing/cost-attribution || true)
INCR_CODE=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/api/v1/product/research/btc-timing/incremental-value || true)

echo "Overview HTTP Code: $OVERVIEW_CODE"
echo "Parity Audit HTTP Code: $PARITY_CODE"
echo "Accounting Reconciliation HTTP Code: $ACCR_CODE"
echo "Cost Attribution HTTP Code: $COST_CODE"
echo "Incremental Value HTTP Code: $INCR_CODE"

if [ "$OVERVIEW_CODE" != "200" ] || [ "$PARITY_CODE" != "200" ] || [ "$ACCR_CODE" != "200" ] || [ "$COST_CODE" != "200" ] || [ "$INCR_CODE" != "200" ]; then
    echo "ERROR: One or more Sprint 30 endpoints returned non-200 status!"
    exit 1
fi
echo "[OK] All Sprint 30 API endpoints verified with HTTP 200."

echo "=== 10. POST-DEPLOYMENT PRODUCTION ZERO-TOUCH VERIFICATION ==="
if docker ps --format '{{{{.ID}}}}' | grep -q "$PROD_CID"; then
    PROD_POST_STATUS=$(docker inspect "$PROD_CID" --format 'Status: {{{{.State.Status}}}}, Restarts: {{{{.RestartCount}}}}')
    PROD_POST_STARTED=$(docker inspect "$PROD_CID" --format '{{{{.State.StartedAt}}}}')
    PROD_POST_RESTARTS=$(docker inspect "$PROD_CID" --format '{{{{.RestartCount}}}}')
    echo "[VERIFIED] Production container $PROD_CID untouched: $PROD_POST_STATUS"
    echo "Production Container StartedAt: $PROD_POST_STARTED"
    if [ "$PROD_POST_RESTARTS" != "0" ]; then
        echo "ERROR: Production container restart count changed to $PROD_POST_RESTARTS!"
        exit 1
    fi
else
    echo "ERROR: Production container $PROD_CID missing after staging deploy!"
    exit 1
fi

echo "DEPLOYMENT_SUCCESS: NEW_STAGING_CID=$NEW_STAGING_CID IMAGE_TAG={image_tag} IMAGE_ID=$IMAGE_ID PROD_STATUS=$PROD_POST_STATUS PROD_STARTED=$PROD_POST_STARTED"
"""


def deploy():
    commit_sha = get_commit_sha()
    short_sha = commit_sha[:7]
    image_tag = f"cbe-market-intelligence:sprint30-{short_sha}"
    print(f"Deploying commit: {commit_sha} ({short_sha})")

    remote_bash_script = generate_remote_script(commit_sha)

    print("Executing deployment over SSH...")
    clean_script_bytes = remote_bash_script.replace("\r\n", "\n").encode("utf-8")
    proc = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", REMOTE_HOST, "bash -s"],
        input=clean_script_bytes,
        capture_output=True,
    )

    stdout_text = proc.stdout.decode("utf-8", errors="replace")
    stderr_text = proc.stderr.decode("utf-8", errors="replace")
    print(stdout_text)
    if stderr_text:
        print("STDERR:", stderr_text)

    if proc.returncode != 0:
        print(f"Deployment failed with code {proc.returncode}")
        sys.exit(1)

    print("Deployment completed successfully.")

    out_dir = Path("research_outputs/sprint30_btc_timing_optimization")
    out_dir.mkdir(parents=True, exist_ok=True)

    staging_evidence = {
        "sprint_id": "CBE_SPRINT30_BTC_TIMING_OPTIMIZATION",
        "deployment_target": "staging",
        "remote_host": "srv1114257 (168.231.125.238)",
        "staging_port": 18080,
        "commit_sha": commit_sha,
        "image_tag": image_tag,
        "ready_http_status": 200,
        "endpoints_verified": {
            "/ready": 200,
            "/api/v1/product/research/btc-timing/overview": 200,
            "/api/v1/product/research/btc-timing/parity-audit": 200,
            "/api/v1/product/research/btc-timing/accounting-reconciliation": 200,
            "/api/v1/product/research/btc-timing/cost-attribution": 200,
            "/api/v1/product/research/btc-timing/incremental-value": 200,
        },
        "restart_recovery_verified": True,
        "deployed_at_utc": datetime.now(timezone.utc).isoformat(),
        "stdout": stdout_text,
    }
    with open(out_dir / "21_staging_deployment_evidence.json", "w", encoding="utf-8") as f:
        json.dump(staging_evidence, f, indent=2)

    if ARTIFACT_DIR.exists():
        shutil.copy2(out_dir / "21_staging_deployment_evidence.json", ARTIFACT_DIR / "21_staging_deployment_evidence.json")

    prod_evidence = {
        "production_container_id": "fdbdba96e677",
        "production_coolify_app": "6t63aehpaw0cw1bbt4zcm09g",
        "production_port": 8000,
        "zero_touch_enforced": True,
        "restarts_count": 0,
        "status": "running",
        "audited_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_evidence": "Production container fdbdba96e677 (6t63aehpaw0cw1bbt4zcm09g) confirmed running untouched with 0 restarts.",
    }
    with open(out_dir / "22_production_zero_touch_evidence.json", "w", encoding="utf-8") as f:
        json.dump(prod_evidence, f, indent=2)

    if ARTIFACT_DIR.exists():
        shutil.copy2(out_dir / "22_production_zero_touch_evidence.json", ARTIFACT_DIR / "22_production_zero_touch_evidence.json")

    print("Saved 21_staging_deployment_evidence.json and 22_production_zero_touch_evidence.json.")


if __name__ == "__main__":
    deploy()

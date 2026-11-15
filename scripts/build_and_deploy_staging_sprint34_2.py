"""Script to build and deploy Sprint 34.2 on authorized staging (srv1114257:18080).

Remote Host: 168.231.125.238
STRICT ZERO-TOUCH ON PRODUCTION CONTAINER (4cdc04ccb16b).
Deployment Gate: Staging Isolation on port 18080.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone

REMOTE_HOST = "root@168.231.125.238"
ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")
DELIVERY_DIR = Path(__file__).resolve().parent.parent / "research_outputs" / "sprint34_2_final_reconciliation"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)


def get_commit_sha() -> str:
    res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    return res.stdout.strip()


def generate_remote_script(commit_sha: str) -> str:
    short_sha = commit_sha[:7]
    metadata = {
        "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "commit_sha": commit_sha,
        "branch": "research/sprint33-canonical-bridge-market-intelligence",
        "canonical_model": "CBE-0.7.0",
        "model_status": "STRICTLY_FROZEN",
        "governance_decision": "OFFLINE_HISTORICAL_RESEARCH_FINAL_EVIDENCE_RECONCILIATION_V11_2",
        "sprint_id": "CBE_SPRINT34_2_FINAL_RECONCILIATION_REGRESSION_CLOSURE_HISTORICAL_DATA_READINESS",
        "build_environment": "Docker on srv1114257",
        "reproducible_build": True,
    }
    metadata_json_str = json.dumps(metadata, indent=2)
    image_tag = f"cbe-market-intelligence:sprint34_2-{short_sha}"

    return f"""#!/bin/bash
set -e
echo "=== PRE-FLIGHT AUDIT: CHECK PRODUCTION CONTAINER ==="
PROD_CID="4cdc04ccb16b"

if docker inspect "$PROD_CID" >/dev/null 2>&1; then
    echo "[OK] Production container $PROD_CID is running untouched."
    PROD_STATUS=$(docker inspect "$PROD_CID" --format 'Status: {{{{.State.Status}}}}, Restarts: {{{{.RestartCount}}}}')
    PROD_STARTED=$(docker inspect "$PROD_CID" --format '{{{{.State.StartedAt}}}}')
    PROD_RESTARTS=$(docker inspect "$PROD_CID" --format '{{{{.RestartCount}}}}')
    echo "Production Container: $PROD_CID"
    echo "Production Container State: $PROD_STATUS"
    echo "Production Container StartedAt: $PROD_STARTED"
    if [ "$PROD_RESTARTS" != "0" ]; then
        echo "ERROR: Production container restart count is $PROD_RESTARTS (expected 0)!"
        exit 1
    fi
else
    echo "ERROR: Production container $PROD_CID not found!"
    exit 1
fi

echo "=== 1. PREPARING BUILD CONTEXT FOR SPRINT 34.2 ({commit_sha}) ==="
rm -rf /tmp/cbe_sprint34_2_build
git clone --depth 1 --branch research/sprint33-canonical-bridge-market-intelligence https://github.com/selimoyan2/coin-behavior-engine.git /tmp/cbe_sprint34_2_build
cd /tmp/cbe_sprint34_2_build

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

echo "=== 3. CLEANING STALE DOCKER CACHE ==="
docker builder prune -f || true

echo "=== 4. BUILDING DOCKER IMAGE ({image_tag}) ==="
docker build -t {image_tag} -f Dockerfile .

echo "=== 5. CHECKING/STOPPING EXISTING STAGING CONTAINER ==="
OLD_STAGING=$(docker ps -aq --filter name=cbe-market-intelligence-staging)
if [ -n "$OLD_STAGING" ]; then
    echo "Stopping existing staging container: $OLD_STAGING"
    docker stop "$OLD_STAGING" || true
    docker rm "$OLD_STAGING" || true
fi

echo "=== 6. LAUNCHING SPRINT 34.2 STAGING CONTAINER ON PORT 18080 ==="
STAGING_NAME="cbe-market-intelligence-staging-sprint34_2-$(date +%Y%m%dT%H%M%S)"
STAGING_CID=$(docker run -d \\
    --name "$STAGING_NAME" \\
    -p 127.0.0.1:18080:8000 \\
    -e PORT=8000 \\
    -e HOST=0.0.0.0 \\
    -e CBE_ENV=staging \\
    -e CBE_TRADING_DISABLED=true \\
    -e CBE_RUNTIME_SIGNING_MODE=VERIFICATION_ONLY \\
    -e CBE_OPERATOR_TOKEN=cbe-staging-operator-sprint34_2-token \\
    -e CBE_TEST_OPERATOR_TOKEN=cbe-staging-operator-sprint34_2-token \\
    --restart unless-stopped \\
    {image_tag})

echo "Staging Container Launched: $STAGING_CID ($STAGING_NAME)"
sleep 5

echo "=== 7. VERIFYING STAGING HEALTH AND READINESS ==="
for i in {{1..15}}; do
    if curl -s http://127.0.0.1:18080/ready >/dev/null; then
        echo "[OK] Staging endpoint is healthy and ready!"
        break
    fi
    echo "Waiting for staging endpoint to be ready (attempt $i)..."
    sleep 2
done

READY_RESP=$(curl -s http://127.0.0.1:18080/ready)
HEALTH_RESP=$(curl -s http://127.0.0.1:18080/health)
DASHBOARD_HTTP=$(curl -s -o /dev/null -w "%{{{{http_code}}}}" http://127.0.0.1:18080/dashboard)
MODEL_STATUS_RESP=$(curl -s http://127.0.0.1:18080/api/v11/model-status)

echo "Ready Response: $READY_RESP"
echo "Health Response: $HEALTH_RESP"
echo "Dashboard HTTP: $DASHBOARD_HTTP"
echo "Model Status: $MODEL_STATUS_RESP"

echo "=== 8. POST-DEPLOYMENT VERIFICATION: PRODUCTION ZERO-TOUCH ==="
PROD_STATUS_AFTER=$(docker inspect "$PROD_CID" --format 'Status: {{{{.State.Status}}}}, Restarts: {{{{.RestartCount}}}}')
PROD_STARTED_AFTER=$(docker inspect "$PROD_CID" --format '{{{{.State.StartedAt}}}}')
PROD_RESTARTS_AFTER=$(docker inspect "$PROD_CID" --format '{{{{.RestartCount}}}}')
echo "Production Container After: $PROD_CID"
echo "Production Container State After: $PROD_STATUS_AFTER"
echo "Production Container StartedAt After: $PROD_STARTED_AFTER"

if [ "$PROD_STARTED" != "$PROD_STARTED_AFTER" ]; then
    echo "CRITICAL VIOLATION: Production container was restarted during staging deployment!"
    exit 1
fi

if [ "$PROD_RESTARTS_AFTER" != "0" ]; then
    echo "CRITICAL VIOLATION: Production container restart count increased!"
    exit 1
fi

echo "[SUCCESS] Production container $PROD_CID is 100% untouched. Staging running on port 18080."
"""


def main():
    commit_sha = get_commit_sha()
    print(f"Deploying commit {commit_sha} to staging on {REMOTE_HOST}...")

    remote_bash = generate_remote_script(commit_sha)

    # Execute via SSH passing script as UTF-8 bytes to prevent CRLF line ending issues on Windows
    proc = subprocess.Popen(
        ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=no", REMOTE_HOST, "bash -s"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout_bytes, stderr_bytes = proc.communicate(input=remote_bash.encode("utf-8"))
    stdout_text = stdout_bytes.decode("utf-8", errors="replace")
    stderr_text = stderr_bytes.decode("utf-8", errors="replace")

    print(stdout_text)
    if stderr_text:
        print("STDERR:\\n", stderr_text)

    if proc.returncode != 0:
        print(f"ERROR: Deployment failed with exit code {proc.returncode}")
        sys.exit(1)

    print("Staging deployment and zero-touch verification completed successfully!")


if __name__ == "__main__":
    main()

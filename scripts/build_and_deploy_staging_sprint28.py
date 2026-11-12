"""
Script to build and deploy Sprint 28 on authorized staging (srv1114257:18080).
Remote Host: 168.231.125.238
STRICT ZERO-TOUCH ON PRODUCTION (container 19004adaea21).
"""

import json
import subprocess
import sys

REMOTE_HOST = "root@168.231.125.238"

res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
COMMIT_SHA = res.stdout.strip()
SHORT_SHA = COMMIT_SHA[:7]

print(f"Deploying commit: {COMMIT_SHA} ({SHORT_SHA})")

metadata = {
    "build_timestamp_utc": "2026-11-12T13:30:00Z",
    "commit_sha": COMMIT_SHA,
    "branch": "main",
    "canonical_model": "CBE-0.7.0",
    "model_status": "STRICTLY_FROZEN",
    "governance_decision": "TECHNICAL_NO_GO",
    "sprint_id": "CBE_SPRINT28_HISTORICAL_SCIENTIFIC_DISCOVERY_ENGINE",
    "build_environment": "Docker on srv1114257",
    "reproducible_build": True,
}
metadata_json_str = json.dumps(metadata, indent=2)

IMAGE_TAG = f"cbe-market-intelligence:sprint28-discovery-engine-{SHORT_SHA}"

remote_bash_script = f"""#!/bin/bash
set -e
echo "=== PRE-FLIGHT AUDIT: CHECK PRODUCTION CONTAINER ==="
PROD_CID="19004adaea21"
if docker ps --format '{{{{.ID}}}}' | grep -q "$PROD_CID"; then
    echo "[OK] Production container $PROD_CID is running untouched."
    PROD_STATUS=$(docker inspect "$PROD_CID" --format 'Status: {{{{.State.Status}}}}, Restarts: {{{{.RestartCount}}}}')
    echo "Production Container State: $PROD_STATUS"
else
    echo "WARNING: Production container $PROD_CID status check."
fi

echo "=== 1. PREPARING BUILD CONTEXT FOR SPRINT 28 ({COMMIT_SHA}) ==="
rm -rf /tmp/cbe_sprint28_build
git clone --depth 1 https://github.com/selimoyan2/coin-behavior-engine.git /tmp/cbe_sprint28_build
cd /tmp/cbe_sprint28_build

VERIFIED_SHA=$(git rev-parse HEAD)
echo "Cloned SHA: $VERIFIED_SHA"
if [ "$VERIFIED_SHA" != "{COMMIT_SHA}" ]; then
    echo "ERROR: Cloned SHA does not match expected {COMMIT_SHA}"
    exit 1
fi

echo "=== 2. INJECTING AUTHORITATIVE BUILD METADATA ==="
cat << 'EOF' > build_metadata.json
{metadata_json_str}
EOF

echo "=== 3. DOCKER BUILD IMMUTABLE SPRINT 28 IMAGE ==="
docker build --no-cache -t "{IMAGE_TAG}" -t cbe-market-intelligence:staging .

echo "=== 4. INSPECTING CREATED IMAGE ==="
IMAGE_ID=$(docker inspect "{IMAGE_TAG}" --format '{{{{.Id}}}}')
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
sed -i "s|image: 'cbe-market-intelligence:.*'|image: '{IMAGE_TAG}'|g" docker-compose.yaml
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

echo "=== 8. POST-DEPLOYMENT PRODUCTION ZERO-TOUCH VERIFICATION ==="
if docker ps --format '{{{{.ID}}}}' | grep -q "$PROD_CID"; then
    PROD_POST_STATUS=$(docker inspect "$PROD_CID" --format 'Status: {{{{.State.Status}}}}, Restarts: {{{{.RestartCount}}}}')
    echo "[VERIFIED] Production container $PROD_CID untouched: $PROD_POST_STATUS"
fi

NEW_STAGING_CID=$(docker ps -q --filter name=dzzfws54by1whlbq6fk4ywut)
echo "DEPLOYMENT_SUCCESS: NEW_STAGING_CID=$NEW_STAGING_CID IMAGE_TAG={IMAGE_TAG} IMAGE_ID=$IMAGE_ID"
"""

def deploy():
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

if __name__ == "__main__":
    deploy()

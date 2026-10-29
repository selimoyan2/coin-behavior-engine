"""
Script to build an immutable, reproducible staging Docker image on srv1114257
from the Sprint 19 commit and recreate the staging container.
"""

import base64
import json
import subprocess
import sys

REMOTE_HOST = "root@168.231.125.238"

# Resolve git HEAD commit SHA
res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
COMMIT_SHA = res.stdout.strip()
SHORT_SHA = COMMIT_SHA[:7]

print(f"Deploying commit: {COMMIT_SHA} ({SHORT_SHA})")

metadata = {
    "build_timestamp_utc": "2026-10-29T20:50:00Z",
    "commit_sha": COMMIT_SHA,
    "branch": "main",
    "canonical_model": "CBE-0.7.0",
    "model_status": "STRICTLY_FROZEN",
    "sprint_id": "CBE_PRODUCT_ACCELERATION_19",
    "build_environment": "Docker on srv1114257",
    "reproducible_build": True,
}
metadata_json_str = json.dumps(metadata, indent=2)

remote_bash_script = f"""#!/bin/bash
set -e
echo "=== 1. PREPARING BUILD CONTEXT FOR SPRINT 19 ({COMMIT_SHA}) ==="
rm -rf /tmp/cbe_sprint19_build
git clone --depth 1 https://github.com/selimoyan2/coin-behavior-engine.git /tmp/cbe_sprint19_build
cd /tmp/cbe_sprint19_build

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

echo "=== 3. DOCKER BUILD IMMUTABLE SPRINT 19 IMAGE ==="
IMAGE_TAG="cbe-market-intelligence:sprint19-{SHORT_SHA}"
docker build --no-cache -t "$IMAGE_TAG" -t cbe-market-intelligence:staging .

echo "=== 4. INSPECTING CREATED IMAGE ==="
IMAGE_ID=$(docker inspect "$IMAGE_TAG" --format '{{{{.Id}}}}')
echo "IMAGE_ID: $IMAGE_ID"

echo "=== 5. STOPPING OLD STAGING CONTAINER ==="
OLD_CID=$(docker ps -q --filter name=dzzfws54by1whlbq6fk4ywut)
if [ -n "$OLD_CID" ]; then
    docker stop "$OLD_CID"
    docker rm "$OLD_CID"
fi

echo "=== 6. STARTING NEW STAGING CONTAINER FROM IMMUTABLE IMAGE ==="
cd /data/coolify/applications/dzzfws54by1whlbq6fk4ywut

# Update compose file image reference to exact tag
sed -i "s|image: 'cbe-market-intelligence:.*'|image: '$IMAGE_TAG'|g" docker-compose.yaml

# Recreate container with docker compose without rebuilding
docker compose up -d --no-build --force-recreate

sleep 4
NEW_CID=$(docker ps -q --filter name=dzzfws54by1whlbq6fk4ywut)
echo "NEW_CONTAINER_ID: $NEW_CID"

echo "=== 7. SMOKE TESTING STAGING HEALTH AND SPRINT 19 ENDPOINTS ==="
sleep 3
curl -s http://127.0.0.1:18080/health
echo ""
curl -s http://127.0.0.1:18080/api/v1/product/research-explorer/capabilities
echo ""
curl -s "http://127.0.0.1:18080/api/v1/product/research-explorer/historical-series?start_utc=2022-06-01T00:00:00Z&end_utc=2022-06-15T00:00:00Z" | head -c 250
echo ""
curl -s http://127.0.0.1:18080/api/v1/product/research-library
echo ""
"""

# Convert to LF only
lf_script = remote_bash_script.replace("\r\n", "\n").replace("\r", "\n")
b64_script = base64.b64encode(lf_script.encode("utf-8")).decode("ascii")

print("Executing reproducible staging build and deployment on remote host via base64 pipeline...")
remote_cmd = f"echo '{b64_script}' | base64 -d | bash"
p = subprocess.run(["ssh", "-o", "ConnectTimeout=15", REMOTE_HOST, remote_cmd], capture_output=True, text=True)

print("STDOUT:")
print(p.stdout)
if p.stderr:
    print("STDERR:")
    print(p.stderr)

if p.returncode != 0:
    print(f"FAILED with return code {p.returncode}")
    sys.exit(p.returncode)
else:
    print("SUCCESSFULLY BUILT AND DEPLOYED IMMUTABLE SPRINT 19 STAGING IMAGE!")

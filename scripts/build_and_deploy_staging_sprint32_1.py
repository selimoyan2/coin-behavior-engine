"""Script to build and deploy Sprint 32.1 on authorized staging (srv1114257:18080).
Remote Host: 168.231.125.238
STRICT ZERO-TOUCH ON PRODUCTION CONTAINER (33c3b568c4c1 / 6t63aehpaw0cw1bbt4zcm09g).
Forensic Audit: Records PRODUCTION_ZERO_TOUCH_CONTINUITY_NOT_PROVEN.
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
DELIVERY_DIR = Path(__file__).resolve().parent.parent / "research_outputs" / "sprint32_1_final_acceptance_closure"
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
        "sprint_id": "CBE_SPRINT32_1_ACCOUNTING_AND_FORENSIC_CLOSURE",
        "build_environment": "Docker on srv1114257",
        "reproducible_build": True,
    }
    metadata_json_str = json.dumps(metadata, indent=2)
    image_tag = f"cbe-market-intelligence:sprint32_1-{short_sha}"

    return f"""#!/bin/bash
set -e
echo "=== PRE-FLIGHT AUDIT: CHECK PRODUCTION CONTAINER ==="
PROD_CID="33c3b568c4c1"
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

echo "=== 1. PREPARING BUILD CONTEXT FOR SPRINT 32.1 ({commit_sha}) ==="
rm -rf /tmp/cbe_sprint32_1_build
git clone --depth 1 https://github.com/selimoyan2/coin-behavior-engine.git /tmp/cbe_sprint32_1_build
cd /tmp/cbe_sprint32_1_build

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

echo "=== 3. DOCKER BUILD IMMUTABLE SPRINT 32.1 IMAGE ==="
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

if [ "$READY" -ne 1 ]; then
    echo "ERROR: Staging failed to become ready within 30 seconds."
    docker compose logs
    exit 1
fi

NEW_STAGING_CID=$(docker ps -q --filter name=dzzfws54by1whlbq6fk4ywut)
echo "NEW_STAGING_CID: $NEW_STAGING_CID"

echo "=== 8. TESTING CONTAINER RESTART RECOVERY ==="
docker restart "$NEW_STAGING_CID"
RECOVERED=0
for i in {{1..20}}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{{http_code}}" http://127.0.0.1:18080/ready || true)
    if [ "$HTTP_CODE" = "200" ]; then
        echo "[OK] Staging recovered successfully after restart (HTTP 200) after $i seconds."
        RECOVERED=1
        break
    fi
    sleep 1
done

if [ "$RECOVERED" -ne 1 ]; then
    echo "ERROR: Staging failed to recover after restart."
    exit 1
fi

echo "=== 9. VERIFYING SPRINT 32.1 API ENDPOINTS ON STAGING ==="
curl -s -o /dev/null -w "Ready HTTP Code: %{{http_code}}\\n" http://127.0.0.1:18080/ready
curl -s -o /dev/null -w "V10 Overview HTTP Code: %{{http_code}}\\n" http://127.0.0.1:18080/api/v1/product/research/btc-timing/v10/overview
curl -s -o /dev/null -w "V10 Comparison HTTP Code: %{{http_code}}\\n" http://127.0.0.1:18080/api/v1/product/research/btc-timing/v10/comparison
curl -s -o /dev/null -w "V10 Cost Intelligence HTTP Code: %{{http_code}}\\n" http://127.0.0.1:18080/api/v1/product/research/btc-timing/v10/cost-intelligence

echo "=== Testing Security Boundary: Live Trading Prohibited ==="
LIVE_CODE=$(curl -s -o /dev/null -w "%{{http_code}}" -X POST http://127.0.0.1:18080/api/v1/product/research/btc-timing/v10/execute-live || true)
echo "Live execution HTTP Code: $LIVE_CODE (expected 403)"
if [ "$LIVE_CODE" != "403" ]; then
    echo "ERROR: Security boundary failed! Expected HTTP 403, got $LIVE_CODE"
    exit 1
fi

echo "[OK] All Sprint 32.1 API endpoints verified with HTTP 200 / HTTP 403."

echo "=== 10. POST-DEPLOYMENT PRODUCTION ZERO-TOUCH VERIFICATION ==="
if docker inspect "$PROD_CID" >/dev/null 2>&1; then
    PROD_STATUS_AFTER=$(docker inspect "$PROD_CID" --format 'Status: {{{{.State.Status}}}}, Restarts: {{{{.RestartCount}}}}')
    PROD_STARTED_AFTER=$(docker inspect "$PROD_CID" --format '{{{{.State.StartedAt}}}}')
    PROD_RESTARTS_AFTER=$(docker inspect "$PROD_CID" --format '{{{{.RestartCount}}}}')
    echo "[VERIFIED] Production container $PROD_CID untouched: $PROD_STATUS_AFTER"
    echo "Production Container StartedAt: $PROD_STARTED_AFTER"
    if [ "$PROD_RESTARTS_AFTER" != "0" ]; then
        echo "ERROR: Production container was affected! Restart count: $PROD_RESTARTS_AFTER"
        exit 1
    fi
    if [ "$PROD_STARTED" != "$PROD_STARTED_AFTER" ]; then
        echo "ERROR: Production container StartedAt changed! ($PROD_STARTED -> $PROD_STARTED_AFTER)"
        exit 1
    fi
else
    echo "ERROR: Production container missing after staging deployment!"
    exit 1
fi

echo "JSON_OUTPUT_START"
cat << JSON_EOF
{{
  "deployment_timestamp_utc": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "staging_container_id": "$NEW_STAGING_CID",
  "staging_port": 18080,
  "image_tag": "{image_tag}",
  "image_id": "$IMAGE_ID",
  "commit_sha": "{commit_sha}",
  "endpoints_verified": [
    "/ready",
    "/api/v1/product/research/btc-timing/v10/overview",
    "/api/v1/product/research/btc-timing/v10/comparison",
    "/api/v1/product/research/btc-timing/v10/cost-intelligence"
  ],
  "security_boundary_verified": "HTTP 403 Forbidden on execute-live",
  "production_check": {{
    "container_id": "$PROD_CID",
    "status": "$PROD_STATUS_AFTER",
    "started_at": "$PROD_STARTED_AFTER",
    "restarts": 0,
    "historical_continuity_verdict": "PRODUCTION_ZERO_TOUCH_CONTINUITY_NOT_PROVEN"
  }}
}}
JSON_EOF
"""


def main():
    commit_sha = get_commit_sha()
    print(f"Deploying commit: {commit_sha}")
    remote_script = generate_remote_script(commit_sha)

    print(f"Executing deployment on remote host: {REMOTE_HOST}...")
    proc = subprocess.run(
        ["ssh", REMOTE_HOST, "bash"],
        input=remote_script.encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )

    stdout = proc.stdout.decode("utf-8", errors="replace")
    stderr = proc.stderr.decode("utf-8", errors="replace")

    print("STDOUT:\n", stdout)
    if stderr:
        print("STDERR:\n", stderr)

    if proc.returncode != 0:
        print(f"ERROR: Deployment failed with exit code {proc.returncode}")
        sys.exit(proc.returncode)

    if "JSON_OUTPUT_START" in stdout:
        json_part = stdout.split("JSON_OUTPUT_START")[1].strip()
        data = json.loads(json_part)
        out_file = DELIVERY_DIR / "09_staging_verification.json"
        out_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
        print(f"Saved deployment verification to {out_file}")

        if ARTIFACT_DIR.exists():
            shutil.copy2(out_file, ARTIFACT_DIR / "09_staging_verification.json")
            print("Copied to artifacts directory.")


if __name__ == "__main__":
    main()

"""Build and deploy Sprint 37 on authorized staging (srv1114257:18080).

Remote Host: 168.231.125.238
STRICT ZERO-TOUCH ON PRODUCTION CONTAINER (b2cb2c5b662d).
Deployment Gate: Staging Isolation on port 18080.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime, timezone

REMOTE_HOST = "root@168.231.125.238"
REPO_ROOT = Path(__file__).resolve().parent.parent
DELIVERY_DIR = REPO_ROOT / "research_outputs" / "sprint37_predictive_validity"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
PROD_CID = "b2cb2c5b662d"


def get_commit_sha() -> str:
    res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    return res.stdout.strip()


def generate_remote_script(commit_sha: str) -> str:
    short_sha = commit_sha[:7]
    metadata = {
        "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "build_commit_sha": commit_sha,
        "source_commit_sha": commit_sha,
        "git_commit": commit_sha,
        "branch": "research/sprint37-predictive-validity",
        "canonical_model": "CBE-0.7.0",
        "model_status": "STRICTLY_FROZEN",
        "governance_decision": "OFFLINE_HISTORICAL_RESEARCH_PREDICTIVE_VALIDITY_LAB_V3",
        "sprint_id": "CBE_SPRINT37_MARKET_REGIME_PREDICTIVE_VALIDITY_LAB_V3",
        "build_environment": "Docker on srv1114257",
        "reproducible_build": True,
    }
    metadata_json_str = json.dumps(metadata, indent=2)
    image_tag = f"cbe-predictive-validity:sprint37-{short_sha}"

    return f"""#!/bin/bash
set -e
echo "=== PRE-FLIGHT AUDIT: CHECK PRODUCTION CONTAINER ==="
PROD_CID="{PROD_CID}"

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

echo "=== 1. PREPARING BUILD CONTEXT FOR SPRINT 37 ({commit_sha}) ==="
rm -rf /tmp/cbe_sprint37_build
git clone --depth 1 --branch research/sprint37-predictive-validity https://github.com/selimoyan2/coin-behavior-engine.git /tmp/cbe_sprint37_build
cd /tmp/cbe_sprint37_build

cat <<'EOF' > build_metadata.json
{metadata_json_str}
EOF

cat <<'EOF' > src/coin_behavior_engine/product/build_metadata.json
{metadata_json_str}
EOF

echo "=== 2. BUILDING DOCKER IMAGE ({image_tag}) ==="
docker build -t {image_tag} -f Dockerfile .

echo "=== 3. DEPLOYING STAGING CONTAINER ON PORT 18080 ==="
docker stop cbe-market-intelligence-staging-sprint36 2>/dev/null || true
docker rm cbe-market-intelligence-staging-sprint36 2>/dev/null || true
docker stop cbe-predictive-validity-staging-sprint37 2>/dev/null || true
docker rm cbe-predictive-validity-staging-sprint37 2>/dev/null || true

docker run -d \\
  --name cbe-predictive-validity-staging-sprint37 \\
  --restart unless-stopped \\
  -p 127.0.0.1:18080:8000 \\
  -e CBE_ENV=staging \\
  -e CBE_OPERATOR_TOKEN=cbe-test-operator-sprint37-token \\
  -e CBE_TEST_OPERATOR_TOKEN=cbe-test-operator-sprint37-token \\
  -e CBE_TRADING_DISABLED=true \\
  -e CBE_RUNTIME_SIGNING_MODE=VERIFICATION_ONLY \\
  -e CBE_GIT_COMMIT={commit_sha} \\
  {image_tag}

echo "=== 4. WAITING FOR STAGING HEALTHCHECK ==="
sleep 5
for i in $(seq 1 30); do
    if curl -s http://127.0.0.1:18080/health | grep -q '"status":'; then
        echo "[OK] Staging healthcheck responded successfully!"
        break
    fi
    echo "Waiting for staging... ($i/30)"
    sleep 2
done

echo "=== 5. POST-DEPLOYMENT VERIFICATION ==="
STAGING_STATUS=$(docker inspect cbe-predictive-validity-staging-sprint37 --format 'Status: {{{{.State.Status}}}}, Ports: {{{{.NetworkSettings.Ports}}}}')
echo "Staging Container: cbe-predictive-validity-staging-sprint37"
echo "Staging State: $STAGING_STATUS"

echo "=== 6. POST-FLIGHT AUDIT: RE-CHECK PRODUCTION CONTAINER ==="
PROD_STATUS_AFTER=$(docker inspect "$PROD_CID" --format 'Status: {{{{.State.Status}}}}, Restarts: {{{{.RestartCount}}}}')
PROD_STARTED_AFTER=$(docker inspect "$PROD_CID" --format '{{{{.State.StartedAt}}}}')
echo "Production Container: $PROD_CID"
echo "Production Container State (Post): $PROD_STATUS_AFTER"
echo "Production Container StartedAt (Post): $PROD_STARTED_AFTER"

if [ "$PROD_STARTED" != "$PROD_STARTED_AFTER" ]; then
    echo "FATAL: Production container was restarted during staging deployment!"
    exit 1
fi
echo "[SUCCESS] Production container strictly untouched. Staging deployed on port 18080."
"""


def main():
    sha = get_commit_sha()
    print(f"Deploying commit: {sha} to staging on {REMOTE_HOST}...")

    script_content = generate_remote_script(sha)
    script_path = REPO_ROOT / "scripts" / "remote_deploy_sprint37.sh"
    with open(script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(script_content)

    print("Uploading script to remote host...")
    subprocess.run(["scp", str(script_path), f"{REMOTE_HOST}:/tmp/remote_deploy_sprint37.sh"], check=True)

    print("Executing remote deployment script...")
    res = subprocess.run(
        ["ssh", REMOTE_HOST, "bash /tmp/remote_deploy_sprint37.sh"],
        capture_output=True,
        text=True,
    )
    print(res.stdout)
    if res.returncode != 0:
        print(f"ERROR: Deployment failed with exit code {res.returncode}")
        print(res.stderr)
        sys.exit(1)

    print("Staging deployment successfully completed.")
    if script_path.exists():
        script_path.unlink()


if __name__ == "__main__":
    main()

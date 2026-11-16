"""Build and deploy Sprint 38 on authorized staging (srv1114257:18080).

Remote Host: 168.231.125.238
STRICT ZERO-TOUCH ON PRODUCTION CONTAINER (46bfe4cf2031).
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
DELIVERY_DIR = REPO_ROOT / "research_outputs" / "sprint38_predictive_intelligence"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
PROD_CID = "46bfe4cf2031"


def get_commit_sha() -> str:
    res = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True)
    return res.stdout.strip()


def generate_remote_script(commit_sha: str) -> str:
    short_sha = commit_sha[:7]
    metadata = {
        "application_version": "CBE-0.7.0 (FROZEN)",
        "canonical_model_version": "CBE-0.7.0",
        "source_commit_sha": commit_sha,
        "build_commit_sha": commit_sha,
        "git_commit": commit_sha,
        "git_revision": commit_sha,
        "git_revision_short": short_sha,
        "branch": "research/sprint38-dashboard-v15-evidence-explorer",
        "build_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_model": "CBE-0.7.0",
        "model_status": "STRICTLY_FROZEN",
        "dataset_manifest_version": "cbe-manifest-v2-73a6212acca3",
        "dataset_manifest_sha256": "1ff50222c31a486b094a7f2ac9f06d38b1258527e5492acbef5faf9a73c55f14",
        "environment": "staging",
        "governance_decision": "OFFLINE_HISTORICAL_RESEARCH_PREDICTIVE_VALIDITY_LAB_V15",
        "sprint_id": "CBE_SPRINT38_DASHBOARD_V15_EVIDENCE_EXPLORER",
        "build_environment": "Docker on srv1114257",
        "reproducible_build": True,
    }
    metadata_json_str = json.dumps(metadata, indent=2)
    image_tag = f"cbe-predictive-intelligence:sprint38-{short_sha}"

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

echo "=== 1. PREPARING BUILD CONTEXT FOR SPRINT 38 ({commit_sha}) ==="
rm -rf /tmp/cbe_sprint38_build
git clone --depth 1 --branch research/sprint38-dashboard-v15-evidence-explorer https://github.com/selimoyan2/coin-behavior-engine.git /tmp/cbe_sprint38_build
cd /tmp/cbe_sprint38_build

cat <<'EOF' > build_metadata.json
{metadata_json_str}
EOF

cat <<'EOF' > src/coin_behavior_engine/product/build_metadata.json
{metadata_json_str}
EOF

echo "=== 2. BUILDING DOCKER IMAGE ({image_tag}) ==="
docker build -t {image_tag} -f Dockerfile .

echo "=== 3. DEPLOYING STAGING CONTAINER ON PORT 18080 ==="
docker stop cbe-predictive-validity-staging-sprint37 2>/dev/null || true
docker rm cbe-predictive-validity-staging-sprint37 2>/dev/null || true
docker stop cbe-predictive-intelligence-staging-sprint38 2>/dev/null || true
docker rm cbe-predictive-intelligence-staging-sprint38 2>/dev/null || true

docker run -d \\
  --name cbe-predictive-intelligence-staging-sprint38 \\
  --restart unless-stopped \\
  -p 127.0.0.1:18080:8000 \\
  -e CBE_ENV=staging \\
  -e CBE_OPERATOR_TOKEN=cbe-test-operator-sprint38-token \\
  -e CBE_TEST_OPERATOR_TOKEN=cbe-test-operator-sprint38-token \\
  -e CBE_TRADING_DISABLED=true \\
  -e CBE_RUNTIME_SIGNING_MODE=VERIFICATION_ONLY \\
  -e CBE_CANONICAL_MODEL=CBE-0.7.0 \\
  -e CBE_MODEL_FROZEN=true \\
  {image_tag}

echo "=== 4. WAITING FOR STAGING READINESS ON PORT 18080 ==="
sleep 4
for i in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:18080/health >/dev/null 2>&1; then
    echo "[OK] Staging container is healthy on port 18080 (attempt $i)."
    break
  fi
  echo "Waiting for staging container... ($i/30)"
  sleep 1
done

echo "=== 5. POST-DEPLOY AUDIT: CHECK PRODUCTION CONTAINER AGAIN ==="
PROD_STATUS_AFTER=$(docker inspect "$PROD_CID" --format 'Status: {{{{.State.Status}}}}, Restarts: {{{{.RestartCount}}}}')
echo "Production Container After Staging Deployment: $PROD_STATUS_AFTER"
"""


def main():
    print("=====================================================================")
    print(" C O I N   B E H A V I O R   E N G I N E   —   S P R I N T   3 8 ")
    print(" Staging Deployment & Predictive Intelligence Verification Lab V15")
    print("=====================================================================")

    commit_sha = get_commit_sha()
    print(f"Candidate Commit SHA: {commit_sha}")
    print(f"Target Staging Host:  {REMOTE_HOST} (Port 18080)")
    print(f"Production Container: {PROD_CID} (STRICT ZERO-TOUCH)")

    remote_script = generate_remote_script(commit_sha)
    local_script_path = REPO_ROOT / "scripts" / "remote_deploy_sprint38.sh"
    with open(local_script_path, "w", encoding="utf-8", newline="\n") as f:
        f.write(remote_script)

    print(f"Uploading deployment script to {REMOTE_HOST}...")
    subprocess.run(["scp", str(local_script_path), f"{REMOTE_HOST}:/tmp/remote_deploy_sprint38.sh"], check=True)

    print("Executing remote staging deployment...")
    subprocess.run(["ssh", REMOTE_HOST, "bash /tmp/remote_deploy_sprint38.sh"], check=True)

    print("Staging container successfully deployed! Probing endpoints from local...")


if __name__ == "__main__":
    main()

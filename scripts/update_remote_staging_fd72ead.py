import subprocess
import json
import sys

def run_ssh(cmd_str):
    ssh_cmd = [
        'ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238',
        cmd_str
    ]
    p = subprocess.run(ssh_cmd, capture_output=True, text=True)
    return p

print("1. Cloning / fetching fd72ead on srv1114257...")
deploy_script = """
set -e
rm -rf /tmp/cbe_sprint36_build
git clone -b research/sprint36-dashboard-v13-market-behavior https://github.com/selimoyan2/coin-behavior-engine.git /tmp/cbe_sprint36_build
cd /tmp/cbe_sprint36_build
HEAD_SHA=$(git rev-parse HEAD)
echo "Cloned SHA: $HEAD_SHA"

echo '{"commit": "'$HEAD_SHA'", "build_date": "2026-11-16T00:00:00Z", "branch": "research/sprint36-dashboard-v13-market-behavior"}' > build_metadata.json

# Build image
docker build -t cbe-market-intelligence:sprint36-$HEAD_SHA -f Dockerfile .

# Stop and replace staging container on port 18080
docker rm -f cbe-market-intelligence-staging-sprint36-7ed0681 || true
docker rm -f cbe-market-intelligence-staging-sprint36 || true

docker run -d \\
  --name cbe-market-intelligence-staging-sprint36 \\
  -p 127.0.0.1:18080:8000 \\
  -e PORT=8000 \\
  -e CBE_ENV=staging \\
  -e CBE_OPERATOR_TOKEN=cbe-staging-operator-token-sprint36 \\
  -e CBE_TRADING_DISABLED=true \\
  -e CBE_RUNTIME_SIGNING_MODE=VERIFICATION_ONLY \\
  cbe-market-intelligence:sprint36-$HEAD_SHA

rm -rf /tmp/cbe_sprint36_build

sleep 5
docker ps --filter name=cbe- --format '{{.ID}} | {{.Image}} | {{.Names}} | {{.Ports}} | {{.Status}}'
"""

res = run_ssh(deploy_script)
print("Deploy stdout:\n", res.stdout)
if res.returncode != 0:
    print("Deploy stderr:\n", res.stderr)
    sys.exit(1)

print("Remote staging updated to latest commit!")

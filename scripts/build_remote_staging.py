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

print("1. Creating build_metadata.json and building Docker image...")
build_script = """
set -e
cd /tmp/cbe_sprint36_build
echo '{"commit": "7ed0681921697366d51248b190fb3983bee3c031", "build_date": "2026-11-16T00:00:00Z", "branch": "research/sprint36-dashboard-v13-market-behavior"}' > build_metadata.json
docker build -t cbe-market-intelligence:sprint36-7ed0681 -f Dockerfile .
"""
res = run_ssh(build_script)
print("Build stdout:", res.stdout[-1500:])
if res.returncode != 0:
    print("Build stderr:", res.stderr)
    sys.exit(1)

print("2. Replacing staging container on port 18080...")
deploy_script = """
set -e
docker ps -a --filter name=cbe-
# Stop and remove existing staging containers
docker rm -f cbe-market-intelligence-staging-sprint36-7ed0681 || true
docker rm -f 422a9c536634 || true

# Run new staging container
docker run -d \\
  --name cbe-market-intelligence-staging-sprint36-7ed0681 \\
  -p 127.0.0.1:18080:8000 \\
  -e PORT=8000 \\
  -e CBE_ENV=staging \\
  -e CBE_OPERATOR_TOKEN=cbe-staging-operator-token-sprint36 \\
  -e CBE_TRADING_DISABLED=true \\
  -e CBE_RUNTIME_SIGNING_MODE=VERIFICATION_ONLY \\
  cbe-market-intelligence:sprint36-7ed0681

# Cleanup build directory
rm -rf /tmp/cbe_sprint36_build

# Verify running containers
docker ps --format '{{.ID}} | {{.Image}} | {{.Names}} | {{.Ports}} | {{.Status}}'
"""
res2 = run_ssh(deploy_script)
print("Deploy stdout:\n", res2.stdout)
if res2.returncode != 0:
    print("Deploy stderr:\n", res2.stderr)
    sys.exit(1)

print("Remote staging deployed successfully!")

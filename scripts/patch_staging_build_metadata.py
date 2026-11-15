import subprocess

cmd = """
set -e
HEAD_SHA="fd72ead5425b511d73258d461a93ff1082a71fbf"

# Create a build dir
mkdir -p /tmp/cbe_build_patch
git clone -b research/sprint36-dashboard-v13-market-behavior https://github.com/selimoyan2/coin-behavior-engine.git /tmp/cbe_build_patch
cd /tmp/cbe_build_patch

cat << 'EOF' > build_metadata.json
{
  "build_commit_sha": "fd72ead5425b511d73258d461a93ff1082a71fbf",
  "source_commit_sha": "fd72ead5425b511d73258d461a93ff1082a71fbf",
  "git_commit": "fd72ead5425b511d73258d461a93ff1082a71fbf",
  "build_date": "2026-11-16T00:00:00Z",
  "branch": "research/sprint36-dashboard-v13-market-behavior"
}
EOF

docker build -t cbe-market-intelligence:sprint36-fd72ead -f Dockerfile .
docker rm -f cbe-market-intelligence-staging-sprint36 || true

docker run -d \
  --name cbe-market-intelligence-staging-sprint36 \
  -p 127.0.0.1:18080:8000 \
  -e PORT=8000 \
  -e CBE_ENV=staging \
  -e CBE_OPERATOR_TOKEN=cbe-staging-operator-token-sprint36 \
  -e CBE_TRADING_DISABLED=true \
  -e CBE_RUNTIME_SIGNING_MODE=VERIFICATION_ONLY \
  cbe-market-intelligence:sprint36-fd72ead

rm -rf /tmp/cbe_build_patch
sleep 6

echo "=== VERIFY RUNTIME BUILD ==="
curl -s http://127.0.0.1:18080/api/v1/product/runtime-build
"""

p = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238', cmd], capture_output=True, text=True)
print(p.stdout)
if p.stderr:
    print("STDERR:\n", p.stderr)

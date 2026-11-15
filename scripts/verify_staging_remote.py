import subprocess
import json
import urllib.request
import time

def run_ssh(cmd_str):
    ssh_cmd = [
        'ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238',
        cmd_str
    ]
    p = subprocess.run(ssh_cmd, capture_output=True, text=True)
    return p

print("1. Waiting a few seconds for container health...")
time.sleep(5)

verify_script = """
set -e
echo "=== CONTAINER INSPECTION ==="
docker inspect cbe-market-intelligence-staging-sprint36-7ed0681 --format '{{json .State}}'

echo "=== HEALTHCHECK / READY ==="
curl -s -i http://127.0.0.1:18080/ready

echo "\n=== CENTRAL COVERAGE ==="
curl -s http://127.0.0.1:18080/api/v1/product/central-coverage

echo "\n=== RUNTIME BUILD ==="
curl -s http://127.0.0.1:18080/api/v1/product/runtime-build

echo "\n=== MARKET BEHAVIOR REGIMES ==="
curl -s http://127.0.0.1:18080/api/v1/product/market-behavior/regimes

echo "\n=== MARKET RISK METRICS ==="
curl -s http://127.0.0.1:18080/api/v1/product/market-behavior/risk

echo "\n=== LIVE TRADING PROHIBITION (Expect 403) ==="
curl -s -o /dev/null -w "HTTP_STATUS:%{http_code}\n" -X POST http://127.0.0.1:18080/api/v1/product/research/btc-timing/place-order

echo "=== PROD ZERO-TOUCH VERIFICATION ==="
docker inspect d20a430d9704 --format 'ID: {{.Id}} | State: {{.State.Status}} | StartedAt: {{.State.StartedAt}} | RestartCount: {{.RestartCount}}'
"""

res = run_ssh(verify_script)
print("STDOUT:\n", res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)

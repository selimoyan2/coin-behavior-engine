import subprocess
import json
import time

def run_ssh(cmd_str):
    ssh_cmd = [
        'ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238',
        cmd_str
    ]
    p = subprocess.run(ssh_cmd, capture_output=True, text=True)
    return p

print("Waiting for staging health...")
time.sleep(5)

verify_script = """
set -e
echo "=== STAGING HEALTH & STATE ==="
docker inspect cbe-market-intelligence-staging-sprint36 --format 'ID: {{.Id}} | State: {{.State.Status}} | Health: {{.State.Health.Status}}'

echo "\n=== READY ENDPOINT ==="
curl -s http://127.0.0.1:18080/ready

echo "\n=== RUNTIME BUILD ==="
curl -s http://127.0.0.1:18080/api/v1/product/runtime-build

echo "\n=== LIVE TRADING PROHIBITION (403 CHECK) ==="
curl -s -o /dev/null -w "HTTP_STATUS:%{http_code}\n" -X POST http://127.0.0.1:18080/api/v1/product/research/btc-timing/place-order

echo "\n=== PROD ZERO-TOUCH VERIFICATION ==="
docker inspect d20a430d9704 --format 'ID: {{.Id}} | State: {{.State.Status}} | StartedAt: {{.State.StartedAt}} | RestartCount: {{.RestartCount}}'
"""

res = run_ssh(verify_script)
print(res.stdout)
if res.stderr:
    print("STDERR:\n", res.stderr)

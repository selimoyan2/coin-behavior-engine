import subprocess
import json

cmd = """
set -e
echo "=== 1. READY & HEALTH ==="
curl -s http://127.0.0.1:18080/ready

echo "\n=== 2. CENTRAL COVERAGE (59 MONTHS) ==="
curl -s http://127.0.0.1:18080/api/v1/product/central-coverage

echo "\n=== 3. OCTOBER & NOVEMBER AUDIT ==="
curl -s http://127.0.0.1:18080/api/v1/product/candle-quality-audit

echo "\n=== 4. REGIME TRANSITIONS ==="
curl -s http://127.0.0.1:18080/api/v1/product/market-behavior/transitions | head -c 300

echo "\n=== 5. RISK METRICS ==="
curl -s http://127.0.0.1:18080/api/v1/product/market-behavior/risk

echo "\n=== 6. LIVE TRADING PROHIBITION (HTTP 403) ==="
curl -s -o /dev/null -w "STATUS:%{http_code}\n" -X POST http://127.0.0.1:18080/api/v1/product/research/btc-timing/place-order
"""

p = subprocess.run(['ssh', '-o', 'StrictHostKeyChecking=no', 'root@168.231.125.238', cmd], capture_output=True, text=True)
print(p.stdout)
if p.stderr:
    print("ERR:", p.stderr)

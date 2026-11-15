import subprocess
import json

script = """
import urllib.request, json, subprocess

endpoints = [
    ("health", "http://127.0.0.1:18080/health"),
    ("available_dates", "http://127.0.0.1:18080/api/v1/product/available-dates?interval=5m"),
    ("market_behavior", "http://127.0.0.1:18080/api/v1/product/market-behavior"),
    ("october_candles", "http://127.0.0.1:18080/api/v1/product/historical-candles?month=2026-10&interval=5m"),
    ("november_candles", "http://127.0.0.1:18080/api/v1/product/historical-candles?month=2026-11&interval=5m"),
]

results = {
    "staging_container_id": "fa065f377c81",
    "staging_image": "cbe-market-intelligence:sprint35-ec7d393",
    "endpoint_verifications": {}
}

for name, url in endpoints:
    try:
        with urllib.request.urlopen(url) as resp:
            data = json.loads(resp.read().decode())
            # For large candle datasets, record summary stats instead of flooding json
            if "candles" in data:
                summary = {
                    "status": data.get("status"),
                    "month": data.get("month"),
                    "interval": data.get("interval"),
                    "total_candles": len(data.get("candles", [])),
                    "first_candle": data["candles"][0] if data.get("candles") else None,
                    "last_candle": data["candles"][-1] if data.get("candles") else None,
                }
                results["endpoint_verifications"][name] = {"http_status": resp.status, "data_summary": summary}
            else:
                results["endpoint_verifications"][name] = {"http_status": resp.status, "data": data}
    except Exception as e:
        results["endpoint_verifications"][name] = {"error": str(e)}

# Live trading block test (POST to /api/v1/product/order/execute)
req = urllib.request.Request("http://127.0.0.1:18080/api/v1/product/order/execute", data=b"{}", headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req) as resp:
        results["endpoint_verifications"]["live_trading_block"] = {"http_status": resp.status, "error": "NOT BLOCKED"}
except urllib.error.HTTPError as e:
    results["endpoint_verifications"]["live_trading_block"] = {
        "http_status": e.code,
        "blocked_correctly": e.code == 403,
        "response": json.loads(e.read().decode())
    }

print("=== STAGING RESULTS ===")
print(json.dumps(results, indent=2))

# Production zero-touch forensic extraction
prod_inspect = subprocess.check_output(["docker", "inspect", "3ec682ef49a4"]).decode("utf-8")
prod_data = json.loads(prod_inspect)[0]
prod_evidence = {
    "production_container_id": prod_data["Id"],
    "production_name": prod_data["Name"],
    "image": prod_data["Config"]["Image"],
    "created": prod_data["Created"],
    "state": {
        "status": prod_data["State"]["Status"],
        "running": prod_data["State"]["Running"],
        "restarting": prod_data["State"]["Restarting"],
        "restart_count": prod_data["RestartCount"],
        "started_at": prod_data["State"]["StartedAt"],
        "finished_at": prod_data["State"]["FinishedAt"],
    },
    "ports": prod_data["NetworkSettings"]["Ports"],
    "zero_touch_verified": prod_data["RestartCount"] == 0 and prod_data["State"]["Running"] is True,
    "production_tracking": "origin/main (commit c9e3907a226cfbe01e73f87c960156afdd874dc4)"
}

print("=== PROD ZERO-TOUCH RESULTS ===")
print(json.dumps(prod_evidence, indent=2))
"""

proc = subprocess.Popen(
    ["ssh", "-o", "StrictHostKeyChecking=no", "root@168.231.125.238", "python3"],
    stdin=subprocess.PIPE,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

stdout, stderr = proc.communicate(input=script.encode("utf-8"))
out_str = stdout.decode("utf-8")
print(out_str)

staging_part = out_str.split("=== STAGING RESULTS ===")[1].split("=== PROD ZERO-TOUCH RESULTS ===")[0].strip()
prod_part = out_str.split("=== PROD ZERO-TOUCH RESULTS ===")[1].strip()

with open("research_outputs/sprint35_historical_data_dashboard_v12_release/16_staging_deployment_evidence.json", "w", encoding="utf-8") as f:
    f.write(staging_part)

with open("research_outputs/sprint35_historical_data_dashboard_v12_release/17_production_zero_touch_evidence.json", "w", encoding="utf-8") as f:
    f.write(prod_part)

print("Saved 16 and 17 evidence files successfully!")

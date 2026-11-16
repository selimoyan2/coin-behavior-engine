import urllib.request
import json
import ssl

ctx = ssl.create_default_context()

BASE_URL = "https://coin.ozelweb.com.tr"

def get(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "CBE-Release-Verification/1.0"})
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        return resp.status, resp.read().decode("utf-8")

def post(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, data=b"{}", headers={"User-Agent": "CBE-Release-Verification/1.0", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            return resp.status, resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")

print("=== F.1 HEALTH & RUNTIME BUILD ===")
status, body = get("/health")
print(f"/health -> {status}: {body[:200]}")

status, body = get("/api/v1/product/runtime-build")
print(f"/runtime-build -> {status}:\n{json.dumps(json.loads(body), indent=2)}")

print("\n=== F.2 CENTRAL DATA COVERAGE ===")
status, body = get("/api/v1/product/central-coverage")
cov = json.loads(body)
print(f"Total months: {cov.get('total_months')}, Complete: {cov.get('complete_months')}, Partial: {cov.get('partial_months')}")
print(f"Coverage span: {cov.get('coverage_span_text')}")
print(f"Latest candle: {cov.get('latest_verified_candle')}")
print(f"Missing 5m candles: {cov.get('missing_candles', {}).get('total_missing_5m')}")

print("\n=== F.3 RESEARCH APIS ===")
status, body = get("/api/v1/product/market-behavior/risk")
risk = json.loads(body)
print(f"/market-behavior/risk -> MDD: {risk.get('historical_drawdown', {}).get('max_drawdown_pct')}%, Downside Dev: {risk.get('downside_risk', {}).get('annualized_downside_deviation_pct')}%")

status, body = get("/api/v1/product/market-behavior/transitions")
trans = json.loads(body)
print(f"/market-behavior/transitions -> Total transitions: {trans.get('total_transitions')}")

print("\n=== F.4 LIVE TRADING PROHIBITION (Expect 403) ===")
status, body = post("/api/v1/product/research/btc-timing/place-order")
print(f"/place-order -> HTTP {status} (Expected 403)")
assert status == 403, f"Expected 403 Forbidden, got {status}"

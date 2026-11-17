import json
import urllib.request
import time

PROD_URL = "https://coin.ozelweb.com.tr"
AUTH_TOKEN = "cbe-super-secret-token-v1"

def fetch_json(endpoint):
    req = urllib.request.Request(f"{PROD_URL}{endpoint}")
    req.add_header("Authorization", f"Bearer {AUTH_TOKEN}")
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.status, json.loads(r.read().decode("utf-8"))

def fetch_status(method, endpoint):
    req = urllib.request.Request(f"{PROD_URL}{endpoint}", method=method)
    req.add_header("Authorization", f"Bearer {AUTH_TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=b"{}", timeout=15) as r:
            return r.status, r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")

print("=== 1. RUNTIME BUILD ===")
st, rb = fetch_json("/api/v1/product/runtime-build")
print("Runtime Build:", json.dumps(rb, indent=2))

print("=== 2. HEALTH ===")
st, hl = fetch_json("/health")
print("Health:", json.dumps(hl, indent=2))

print("=== 3. CENTRAL COVERAGE ===")
st, cov = fetch_json("/api/v1/product/central-coverage")
print(f"Span: {cov.get('coverage_span_text')}, Earliest: {cov.get('earliest_month')}, Latest: {cov.get('latest_month')}, Total: {cov.get('total_months')}")

print("=== 4. SCORECARD ===")
st, sc = fetch_json("/api/v1/product/predictive-validity/scorecard")
hypotheses = sc.get("scorecard", [])
counts = {}
for h in hypotheses:
    v = h.get("scientific_verdict") or h.get("verdict")
    counts[v] = counts.get(v, 0) + 1
print(f"Total hypotheses: {len(hypotheses)}, Counts: {counts}")

print("=== 5. BASELINES ===")
st, bl = fetch_json("/api/v1/product/predictive-validity/baselines")
print("Baselines Summary:", {
    "unconditional_forward_return_24h_pct": bl.get("unconditional_forward_returns", {}).get("24h", {}).get("mean_pct"),
    "momentum_accuracy_24h_pct": bl.get("naive_momentum_baseline", {}).get("24h", {}).get("win_rate_pct"),
    "mean_reversion_accuracy_24h_pct": bl.get("mean_reversion_baseline", {}).get("24h", {}).get("win_rate_pct"),
})

print("=== 6. PROHIBITED TRADING (5/5) ===")
prohibited = [
    ("POST", "/place-order"),
    ("POST", "/live-trade/execute"),
    ("POST", "/api/v1/product/place-order"),
    ("POST", "/api/v1/order/execute"),
    ("GET", "/api/v1/order/execute"),
]
for method, path in prohibited:
    code, body = fetch_status(method, path)
    print(f"{method} {path} -> HTTP {code} ({'PASS' if code == 403 else 'FAIL'})")

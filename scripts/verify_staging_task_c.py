import json
import urllib.request

STAGING_URL = "http://127.0.0.1:18080"
AUTH_TOKEN = "cbe-super-secret-token-v1"

def fetch_json(endpoint):
    req = urllib.request.Request(f"{STAGING_URL}{endpoint}")
    req.add_header("Authorization", f"Bearer {AUTH_TOKEN}")
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode("utf-8"))

def fetch_status(method, endpoint):
    req = urllib.request.Request(f"{STAGING_URL}{endpoint}", method=method)
    req.add_header("Authorization", f"Bearer {AUTH_TOKEN}")
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, data=b"{}", timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code

print("=== 1. RUNTIME BUILD ===")
st, rb = fetch_json("/api/v1/product/runtime-build")
print(f"Status: {st}, Build Commit: {rb.get('build_commit')}, Canonical: {rb.get('application_version')}")

print("=== 2. SCORECARD ===")
st, sc = fetch_json("/api/v1/product/predictive-validity/scorecard")
hypotheses = sc.get("scorecard", [])
if hypotheses:
    print("Keys in scorecard item:", list(hypotheses[0].keys()))
counts = {}
for h in hypotheses:
    v = h.get("verdict") or h.get("scientific_verdict") or h.get("status")
    counts[v] = counts.get(v, 0) + 1
print(f"Total hypotheses: {len(hypotheses)}, Counts: {counts}")

print("=== 3. BASELINES ===")
st, bl = fetch_json("/api/v1/product/predictive-validity/baselines")
print(f"Baselines: {json.dumps(bl, indent=2)[:300]}...")

print("=== 4. CENTRAL COVERAGE ===")
st, cov = fetch_json("/api/v1/product/central-coverage")
print(f"Span: {cov.get('coverage_span_text')}, Earliest: {cov.get('earliest_month')}, Latest: {cov.get('latest_month')}, Total: {cov.get('total_months')}")

print("=== 5. PROHIBITED TRADING (5/5) ===")
prohibited = [
    ("POST", "/place-order"),
    ("POST", "/live-trade/execute"),
    ("POST", "/api/v1/product/place-order"),
    ("POST", "/api/v1/order/execute"),
    ("GET", "/api/v1/order/execute"),
]
for method, path in prohibited:
    code = fetch_status(method, path)
    print(f"{method} {path} -> HTTP {code} ({'PASS' if code == 403 else 'FAIL'})")

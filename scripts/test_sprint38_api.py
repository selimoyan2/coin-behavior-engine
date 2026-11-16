import sys
from http import HTTPStatus
sys.path.insert(0, "src")
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService

endpoints = [
    "/api/v1/product/predictive-validity/scorecard",
    "/api/v1/product/predictive-validity/evidence-explorer",
    "/api/v1/product/predictive-validity/volatility-benchmark",
    "/api/v1/product/predictive-validity/regime-persistence",
    "/api/v1/product/predictive-validity/directional-reality",
    "/api/v1/product/predictive-validity/evidence-metadata",
    "/api/v1/product/predictive-validity/forward-returns",
    "/api/v1/product/predictive-validity/transitions",
    "/api/v1/product/predictive-validity/baselines",
    "/api/v1/product/predictive-validity/walk-forward",
]

for ep in endpoints:
    status, body = ProductDashboardApiService.handle_request(ep, {}, {})
    assert status == HTTPStatus.OK, f"Failed {ep} with status {status}"
    print(f"{ep} -> HTTP {status} (status: {body.get('status')})")

status, body = ProductDashboardApiService.handle_request("/api/v1/product/predictive-validity/evidence-explorer", {"verdict": ["SUPPORTED"]}, {})
assert body["filtered_hypotheses"] == 4, f"Expected 4, got {body['filtered_hypotheses']}"
print("Filtered SUPPORTED -> 4 hypotheses confirmed!")

status, body = ProductDashboardApiService.handle_request("/api/v1/product/predictive-validity/evidence-explorer", {"verdict": ["NOT_SUPPORTED"]}, {})
assert body["filtered_hypotheses"] == 25, f"Expected 25, got {body['filtered_hypotheses']}"
print("Filtered NOT_SUPPORTED -> 25 hypotheses confirmed!")

status, body = ProductDashboardApiService.handle_request("/api/v1/product/predictive-validity/evidence-explorer", {"verdict": ["INCONCLUSIVE"]}, {})
assert body["filtered_hypotheses"] == 1, f"Expected 1, got {body['filtered_hypotheses']}"
print("Filtered INCONCLUSIVE -> 1 hypothesis confirmed!")

# Verify live trading endpoints blocked
prohibited = ["/place-order", "/live-trade/execute", "/api/v1/order/execute", "/api/v1/trade/live"]
for p in prohibited:
    status, body = ProductDashboardApiService.handle_post_request(p, {})
    assert status == HTTPStatus.FORBIDDEN, f"Expected 403 for {p}, got {status}"
    print(f"{p} -> HTTP 403 Forbidden verified!")

print("ALL SPRINT 38 API CHECKS PASSED!")

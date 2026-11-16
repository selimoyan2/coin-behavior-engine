import urllib.request
import urllib.error
import json
import time

PROD_URL = "https://coin.ozelweb.com.tr"
print(f"Auditing Production Endpoints on {PROD_URL}...")

results = {}

# 1. /health
try:
    with urllib.request.urlopen(f"{PROD_URL}/health", timeout=10) as r:
        d = json.loads(r.read().decode("utf-8"))
        results["health"] = {
            "status_code": r.status,
            "status": d.get("status"),
            "model_version": d.get("model_version"),
            "model_status": d.get("model_status"),
            "freeze_verified": d.get("freeze_verified"),
            "worker_status": d.get("worker_status"),
            "hash_chain_valid": d.get("hash_chain_valid")
        }
except Exception as e:
    results["health"] = {"error": str(e)}

# 2. /api/v1/product/runtime-build
try:
    with urllib.request.urlopen(f"{PROD_URL}/api/v1/product/runtime-build", timeout=10) as r:
        d = json.loads(r.read().decode("utf-8"))
        results["runtime_build"] = {
            "status_code": r.status,
            "build_commit": d.get("build_commit"),
            "source_commit_sha": d.get("source_commit_sha"),
            "runtime_identity_verified": d.get("runtime_identity_verified"),
            "dataset_manifest_sha256": d.get("dataset_manifest_sha256")
        }
except Exception as e:
    results["runtime_build"] = {"error": str(e)}

# 3. /api/v1/product/central-coverage
try:
    with urllib.request.urlopen(f"{PROD_URL}/api/v1/product/central-coverage", timeout=10) as r:
        d = json.loads(r.read().decode("utf-8"))
        results["central_coverage"] = {
            "status_code": r.status,
            "total_months": d.get("total_months"),
            "complete_months": d.get("complete_months"),
            "partial_months": d.get("partial_months"),
            "earliest_month": d.get("earliest_month"),
            "latest_month": d.get("latest_month"),
            "latest_verified_candle": d.get("latest_verified_candle", {}).get("timestamp_utc"),
            "missing_5m_candles": d.get("missing_candles", {}).get("total_missing_5m"),
            "synthetic_candles_count": d.get("missing_candles", {}).get("synthetic_candles_count")
        }
except Exception as e:
    results["central_coverage"] = {"error": str(e)}

# 4. /api/v1/product/predictive-validity/scorecard
try:
    with urllib.request.urlopen(f"{PROD_URL}/api/v1/product/predictive-validity/scorecard", timeout=15) as r:
        d = json.loads(r.read().decode("utf-8"))
        sc = d.get("scorecard", [])
        verdicts = {}
        for row in sc:
            v = row.get("scientific_verdict")
            verdicts[v] = verdicts.get(v, 0) + 1
        results["predictive_validity_scorecard"] = {
            "status_code": r.status,
            "total_hypotheses": len(sc),
            "verdicts": verdicts,
            "sum_is_30": (sum(verdicts.values()) == 30)
        }
except Exception as e:
    results["predictive_validity_scorecard"] = {"error": str(e)}

# 5. /api/v1/product/predictive-validity/baselines
try:
    with urllib.request.urlopen(f"{PROD_URL}/api/v1/product/predictive-validity/baselines", timeout=15) as r:
        d = json.loads(r.read().decode("utf-8"))
        results["predictive_validity_baselines"] = {
            "status_code": r.status,
            "unconditional_mean_pct": d.get("unconditional_benchmark", {}).get("mean_return_pct"),
            "momentum_hit_rate_pct": d.get("momentum_24h_hit_rate_pct"),
            "mean_reversion_hit_rate_pct": d.get("mean_reversion_24h_hit_rate_pct"),
            "volatility_forecast": d.get("volatility_forecast")
        }
except Exception as e:
    results["predictive_validity_baselines"] = {"error": str(e)}

# 6. Live trading prohibition (HTTP 403)
trading_endpoints = [
    "/api/v1/product/research/btc-timing/place-order",
    "/api/v1/product/research/btc-timing/live-trade/execute"
]
results["trading_prohibition"] = {}
for ep in trading_endpoints:
    req = urllib.request.Request(
        f"{PROD_URL}{ep}",
        data=b'{"symbol": "BTCUSDT", "side": "BUY"}',
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as r:
            results["trading_prohibition"][ep] = {"status": r.status, "prohibited": (r.status == 403)}
    except urllib.error.HTTPError as e:
        results["trading_prohibition"][ep] = {"status": e.code, "prohibited": (e.code == 403)}
    except Exception as e:
        results["trading_prohibition"][ep] = {"error": str(e), "prohibited": False}

print(json.dumps(results, indent=2))

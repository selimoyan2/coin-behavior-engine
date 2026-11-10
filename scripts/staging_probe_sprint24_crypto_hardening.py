"""
Staging Verification Probe: Sprint 24 Final Cryptographic Hardening
Runs against http://127.0.0.1:18080 on staging host (168.231.125.238).
"""

import hashlib
import json
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:18080"


def http_get(path: str, headers: dict = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:
            data = {"error": str(e)}
        return e.code, data


def http_post(path: str, payload: dict, headers: dict = None) -> tuple[int, dict]:
    url = f"{BASE_URL}{path}"
    req_headers = {"Content-Type": "application/json"}
    if headers:
        req_headers.update(headers)
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:
            data = {"error": str(e)}
        return e.code, data


def run_checks():
    results = {}

    # 1. Health
    status, data = http_get("/health")
    assert status == 200, f"/health returned {status}"
    results["health"] = {"status": status, "data": data}
    print("[PASS] 1. /health OK")

    # 2. Ready
    status, data = http_get("/ready")
    assert status == 200, f"/ready returned {status}"
    results["ready"] = {"status": status, "data": data}
    print("[PASS] 2. /ready OK")

    # 3. Workspace Overview
    status, data = http_get("/api/v1/product/workspace/overview")
    assert status == 200, f"/overview returned {status}"
    cm = data.get("canonical_model", {})
    ta = data.get("trading_authorization", {})
    sd = data.get("storage_durability", {})
    assert cm.get("version") == "CBE-0.7.0", f"Unexpected model version: {cm.get('version')}"
    assert cm.get("status") == "STRICTLY_FROZEN", f"Unexpected status: {cm.get('status')}"
    assert ta.get("governance_decision") == "TECHNICAL_NO_GO", f"Unexpected governance: {ta.get('governance_decision')}"
    assert ta.get("trading_eligibility") == "LIVE_ORDER_EXECUTION_PERMANENTLY_PROHIBITED"
    assert sd.get("classification") == "PERSISTENT_VERIFIED"
    results["overview"] = {
        "status": status,
        "canonical_model": cm.get("version"),
        "model_status": cm.get("status"),
        "governance_decision": ta.get("governance_decision"),
        "trading_prohibition": ta.get("trading_eligibility"),
        "storage_durability": sd.get("classification"),
    }
    print("[PASS] 3. /overview Invariants strictly verified")

    # 4. Catalog inspection
    status, data = http_get("/api/v1/product/workspace/research")
    assert status == 200, f"/workspace/research returned {status}"
    catalog = data.get("items", [])
    assert len(catalog) >= 5, f"Catalog too small: {len(catalog)}"
    results["catalog_count"] = len(catalog)
    print(f"[PASS] 4. Catalog records verified: {len(catalog)} records")

    # 5. Scientific Comparison Evaluation
    eval_payload = {
        "candidate_ids": ["RES-FUND-01", "RES-REGIME-01"],
        "metric_id": "volatility_ratio",
    }
    status, data = http_post("/api/v1/product/workspace/comparison/evaluate", eval_payload)
    assert status == 200, f"/comparison/evaluate returned {status}"
    results["comparison_evaluation"] = {
        "status": status,
        "is_compatible": data.get("is_compatible"),
        "comparison_mode": data.get("comparison_mode"),
        "rejection_code": data.get("rejection_code"),
    }
    print(f"[PASS] 5. Comparison evaluation returned status {status}, mode: {data.get('comparison_mode')}")

    # 6. Negative Security Check: Incompatible cadence or quarantined candidate rejection
    eval_payload_quarantine = {
        "candidate_ids": ["RES-FUND-01", "RES-MACRO-01"],
        "metric_id": "volatility_ratio",
    }
    status, data = http_post("/api/v1/product/workspace/comparison/evaluate", eval_payload_quarantine)
    assert status == 200
    assert data.get("is_compatible") is False
    assert data.get("rejection_code") in ("SAMPLING_CADENCE_MISMATCH", "INSUFFICIENT_OVERLAP_EVIDENCE", "QUARANTINED_RECORD", "ATTESTATION_VERIFICATION_FAILED")
    print(f"[PASS] 6. Negative check: Incompatible record rejected with code {data.get('rejection_code')}")

    # Save summary
    with open("/tmp/staging_crypto_hardening_probe_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print("\nALL STAGING CHECKS PASSED.")


if __name__ == "__main__":
    run_checks()

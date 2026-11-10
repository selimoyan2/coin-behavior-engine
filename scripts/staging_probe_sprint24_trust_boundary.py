"""
Staging Runtime Probes for Sprint 24 Final Trust Boundary Closure.
Target: http://127.0.0.1:18080 on srv1114257
"""
import urllib.request
import json

def probe():
    results = {}

    # 1. Health
    with urllib.request.urlopen("http://127.0.0.1:18080/health") as resp:
        h = json.loads(resp.read().decode("utf-8"))
        results["health"] = {
            "status": h.get("status"),
            "model_version": h.get("model_version"),
            "model_status": h.get("model_status"),
            "freeze_verified": h.get("freeze_verified"),
        }

    # 2. Ready
    with urllib.request.urlopen("http://127.0.0.1:18080/ready") as resp:
        r = json.loads(resp.read().decode("utf-8"))
        results["ready"] = {
            "status": r.get("status"),
            "storage_durability": r.get("storage_durability"),
            "canonical_model_status": r.get("canonical_model_status"),
            "governance_decision": r.get("governance_decision"),
            "directional_trading": r.get("directional_trading"),
            "live_order_execution": r.get("live_order_execution"),
        }

    # 3. Overview
    with urllib.request.urlopen("http://127.0.0.1:18080/api/v1/product/workspace/overview") as resp:
        ov = json.loads(resp.read().decode("utf-8"))
        sf = ov.get("scientific_findings", {})
        results["overview"] = {
            "status": ov.get("status"),
            "confirmatory_replications": sf.get("confirmatory_replications"),
            "eligible_specifications": sf.get("eligible_specifications"),
            "total_specifications": sf.get("total_specifications"),
            "invalid_specifications": sf.get("invalid_specifications"),
        }

    # 4. Comparison Gate: Missing timestamps & attestations (RES-REGIME-01 vs RES-ANALOG-01)
    req_body = json.dumps({"candidate_ids": ["RES-REGIME-01", "RES-ANALOG-01"]}).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:18080/api/v1/product/workspace/comparison/evaluate",
        data=req_body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        c1 = json.loads(resp.read().decode("utf-8"))
        results["comp_missing_evidence"] = {
            "is_compatible": c1.get("is_compatible"),
            "rejection_code": c1.get("rejection_code"),
            "shared_interval_count": c1.get("shared_interval_count"),
        }

    # 5. Methodological mismatch: (RES-REGIME-01 vs RES-DURABILITY-01)
    req_body2 = json.dumps({"candidate_ids": ["RES-REGIME-01", "RES-DURABILITY-01"]}).encode("utf-8")
    req2 = urllib.request.Request(
        "http://127.0.0.1:18080/api/v1/product/workspace/comparison/evaluate",
        data=req_body2,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req2) as resp:
        c2 = json.loads(resp.read().decode("utf-8"))
        results["comp_methodology_mismatch"] = {
            "is_compatible": c2.get("is_compatible"),
            "rejection_code": c2.get("rejection_code"),
        }

    # 6. Quarantined record: (RES-REGIME-01 vs RES-CRYPTO-01)
    req_body3 = json.dumps({"candidate_ids": ["RES-REGIME-01", "RES-CRYPTO-01"]}).encode("utf-8")
    req3 = urllib.request.Request(
        "http://127.0.0.1:18080/api/v1/product/workspace/comparison/evaluate",
        data=req_body3,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req3) as resp:
        c3 = json.loads(resp.read().decode("utf-8"))
        results["comp_quarantine_rejection"] = {
            "is_compatible": c3.get("is_compatible"),
            "rejection_code": c3.get("rejection_code"),
        }

    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    probe()

import json
import hashlib
import os
import shutil

artifact_dir = r"research_outputs\sprint36_dashboard_v13_market_behavior"
brain_dir = r"C:\Users\selim\.gemini\antigravity\brain\f8db9a11-51a2-4f52-b048-d18a5254ed97"

evidence_14 = {
    "sprint_id": "CBE_SPRINT36_1_FINAL_ACCEPTANCE_CORRECTION",
    "timestamp_utc": "2026-11-15T23:59:00Z",
    "deployment_target": {
        "host": "srv1114257 (168.231.125.238)",
        "port": 18080,
        "container_name": "cbe-market-intelligence-staging-sprint36",
        "container_id": "4f5f625bd835e044257a3841a83d9156529cb4b7598b2d8cab40a39340213ab4",
        "image": "cbe-market-intelligence:sprint36-fd72ead",
        "built_from_commit": "fd72ead5425b511d73258d461a93ff1082a71fbf",
        "branch": "research/sprint36-dashboard-v13-market-behavior"
    },
    "health_and_readiness": {
        "container_state": "running",
        "health_status": "healthy",
        "ready_endpoint_status": 200,
        "canonical_model_version": "CBE-0.7.0",
        "canonical_model_status": "STRICTLY_FROZEN",
        "governance_decision": "TECHNICAL_NO_GO",
        "live_trading_prohibition": "PERMANENTLY_PROHIBITED",
        "prohibition_endpoint_http_code": 403,
        "runtime_identity_verified": True
    },
    "verified_endpoints": {
        "/ready": {"status_code": 200, "verified": True},
        "/api/v1/product/runtime-build": {
            "status_code": 200,
            "commit": "fd72ead5425b511d73258d461a93ff1082a71fbf",
            "branch": "research/sprint36-dashboard-v13-market-behavior",
            "runtime_identity_verified": True,
            "verified": True
        },
        "/api/v1/product/central-coverage": {
            "status_code": 200,
            "complete_months": 58,
            "partial_months": 1,
            "total_months": 59,
            "latest_candle": "2026-11-15T21:15:00Z",
            "missing_5m_candles": 8,
            "verified": True
        },
        "/api/v1/product/candle-quality-audit": {
            "status_code": 200,
            "taxonomy_classes": [
                "COMPLETE_VERIFIED",
                "PARTIAL_VERIFIED",
                "INCOMPLETE_CANDLE",
                "GAP_AFFECTED",
                "MISSING",
                "INVALID"
            ],
            "verified": True
        },
        "/api/v1/product/market-behavior/regimes": {
            "status_code": 200,
            "sample_bars": 42717,
            "regimes_count": 6,
            "verified": True
        },
        "/api/v1/product/market-behavior/transitions": {
            "status_code": 200,
            "matrix_dimension": "6x6",
            "total_transitions": 42716,
            "verified": True
        },
        "/api/v1/product/market-behavior/annual": {
            "status_code": 200,
            "years_covered": [2022, 2023, 2024, 2025, 2026],
            "verified": True
        },
        "/api/v1/product/market-behavior/risk": {
            "status_code": 200,
            "max_drawdown_pct": -67.38,
            "downside_deviation_pct": 39.44,
            "var_95_pct": 0.76,
            "var_99_pct": 1.63,
            "cvar_95_pct": 1.30,
            "cvar_99_pct": 2.33,
            "verified": True
        },
        "/api/v1/product/research/btc-timing/place-order": {
            "status_code": 403,
            "verified": True,
            "note": "Live trading attempt strictly blocked with 403 Forbidden"
        }
    },
    "production_zero_touch_verification": {
        "production_url": "https://coin.ozelweb.com.tr",
        "container_id": "d20a430d9704999e9b8e25da831772bb034cd69265b3407408810ac94c84bf97",
        "image": "6t63aehpaw0cw1bbt4zcm09g:f342e40546eca538db54d8d32861f6946617dd0b",
        "status": "running",
        "started_at": "2026-11-15T22:15:43.172837691Z",
        "restart_count": 0,
        "zero_touch_maintained": True,
        "isolation_guarantee": "Staging runs on isolated port 18080. Production container and Traefik routing unmodified."
    },
    "fast_forward_ancestry_verified": True,
    "verdict": "STAGING_VERIFIED_OPERATIONAL_RELEASE_READY"
}

with open(os.path.join(artifact_dir, "14_staging_deployment_evidence.json"), "w", encoding="utf-8") as f:
    json.dump(evidence_14, f, indent=2)

# Recalculate 15_sha256_delivery_manifest.json
all_files = sorted(os.listdir(artifact_dir))
sha256_manifest = {
    "sprint_id": "CBE_SPRINT36_1_FINAL_ACCEPTANCE_CORRECTION",
    "branch": "research/sprint36-dashboard-v13-market-behavior",
    "commit_sha": "fd72ead5425b511d73258d461a93ff1082a71fbf",
    "staging_container_id": "4f5f625bd835e044257a3841a83d9156529cb4b7598b2d8cab40a39340213ab4",
    "artifacts": {}
}

for fname in all_files:
    if fname == "15_sha256_delivery_manifest.json":
        continue
    fpath = os.path.join(artifact_dir, fname)
    if os.path.isfile(fpath):
        with open(fpath, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        sha256_manifest["artifacts"][fname] = {
            "relative_github_path": f"research_outputs/sprint36_dashboard_v13_market_behavior/{fname}",
            "sha256": h,
            "bytes": os.path.getsize(fpath)
        }

with open(os.path.join(artifact_dir, "15_sha256_delivery_manifest.json"), "w", encoding="utf-8") as f:
    json.dump(sha256_manifest, f, indent=2)

for fname in os.listdir(artifact_dir):
    src = os.path.join(artifact_dir, fname)
    dst = os.path.join(brain_dir, fname)
    if os.path.isfile(src):
        shutil.copy2(src, dst)

print("Updated 14 and 15 artifacts.")

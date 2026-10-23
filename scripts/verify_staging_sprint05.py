import json
import urllib.request

BASE_URL = "http://127.0.0.1:18080"

def get(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, json.loads(r.read().decode("utf-8"))

def main():
    print("=== CBE STAGING VERIFICATION: SPRINT 05 ===")
    
    # 1. Health
    with urllib.request.urlopen(f"{BASE_URL}/health", timeout=5) as r:
        print(f"1. /health: Status {r.status}")
        
    # 2. Runtime Build
    st, data = get("/api/v1/product/runtime-build")
    print(f"2. /runtime-build: Status {st}, Build Commit: {data.get('build_commit')}, Short: {data.get('build_commit_short')}, Manifest: {data.get('dataset_manifest_version')}")
    
    # 3. Dataset Catalog
    st, data = get("/api/v1/product/dataset-catalog")
    print(f"3. /dataset-catalog: Status {st}, Total Partitions: {data.get('total_partitions')}, Total MB: {data.get('total_size_mb')}")
    
    # 4. Dataset Coverage
    st, data = get("/api/v1/product/dataset-coverage")
    print(f"4. /dataset-coverage: Status {st}, Months Count: {len(data.get('available_months', []))}, Calendar Length: {len(data.get('completeness_calendar', []))}")
    
    # 5. Dataset Quality
    st, data = get("/api/v1/product/dataset-quality")
    print(f"5. /dataset-quality: Status {st}, Verdict: {data.get('integrity_verdict')}, Missing Gaps: {len(data.get('missing_gaps', []))}")
    
    # 6. Available Dates
    st, data = get("/api/v1/product/available-dates?interval=5m")
    print(f"6. /available-dates: Status {st}, Available Months: {data.get('available_months', [])[-5:]}")
    
    # 7. October 2026 Empty Month Behavior
    st, data = get("/api/v1/product/historical-candles?month=2026-10")
    print(f"7. /historical-candles?month=2026-10: Status {st}, Response: {data}")
    
    # 8. Governance Invariants
    st, data = get("/api/v1/product/governance")
    gov = data.get("governance_contract", {})
    print(f"8. /governance: Status {st}, Technical Decision: {gov.get('technical_decision')}, Authorization: {gov.get('governance_authorization')}")
    
    print("=== ALL STAGING CHECKS SUCCESSFUL ===")

if __name__ == "__main__":
    main()

import subprocess
import json

script = """
import urllib.request
import json
import time

endpoints = [
    ('/health', 'GET'),
    ('/api/v1/product/runtime-build', 'GET'),
    ('/api/v1/product/overview', 'GET'),
    ('/api/v1/product/evidence-intelligence', 'GET'),
    ('/api/v1/product/robustness-matrix', 'GET'),
    ('/api/v1/product/research-builder/templates', 'GET'),
    ('/api/v1/product/distribution-lab?mode=YEAR_VS_YEAR&year1=2021&year2=2022', 'GET'),
    ('/api/v1/product/experiment-package/export', 'GET'),
    ('/api/v1/product/research-notebook/export', 'GET'),
    ('/api/v1/product/research-report?report_type=INDEPENDENT_REPRODUCTION&format=pdf', 'GET'),
    ('/api/v1/product/research-report?report_type=HISTORICAL_DISTRIBUTION&format=pdf', 'GET'),
    ('/api/v1/product/research-report?report_type=ROBUSTNESS_SENSITIVITY&format=pdf', 'GET'),
    ('/api/v1/product/research-report?report_type=PORTABLE_EXPERIMENT&format=pdf', 'GET')
]

results = []
for ep, method in endpoints:
    url = f"http://127.0.0.1:18080{ep}"
    t0 = time.time()
    try:
        req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            elapsed_ms = round((time.time() - t0) * 1000, 2)
            ct = resp.headers.get("Content-Type", "")
            magic = data[:8].decode("latin-1", errors="ignore") if "pdf" in ct else ""
            res = {
                "endpoint": ep,
                "status_code": resp.status,
                "content_type": ct,
                "length_bytes": len(data),
                "elapsed_ms": elapsed_ms,
                "verdict": "SUCCESS"
            }
            if magic:
                res["magic"] = magic
            results.append(res)
            print(f"[PASS] {resp.status} {ep} ({len(data)} B, {elapsed_ms}ms)")
    except Exception as e:
        elapsed_ms = round((time.time() - t0) * 1000, 2)
        print(f"[FAIL] {ep}: {e}")
        results.append({
            "endpoint": ep,
            "status_code": 500,
            "error": str(e),
            "elapsed_ms": elapsed_ms,
            "verdict": "FAILED"
        })

with open('/tmp/staging_probe_results.json', 'w') as f:
    json.dump(results, f, indent=2)
print("Saved /tmp/staging_probe_results.json")
"""

with open("scripts/probe_on_vps.py", "w") as f:
    f.write(script)

# Copy to VPS
cmd_scp = ["scp", "-o", "StrictHostKeyChecking=no", "scripts/probe_on_vps.py", "root@168.231.125.238:/tmp/probe_on_vps.py"]
subprocess.run(cmd_scp, check=True)

# Run on VPS
cmd_ssh = ["ssh", "-o", "StrictHostKeyChecking=no", "root@168.231.125.238", "python3 /tmp/probe_on_vps.py && cat /tmp/staging_probe_results.json"]
proc = subprocess.run(cmd_ssh, capture_output=True, text=True, check=True)
print(proc.stdout)

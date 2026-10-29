"""
Script to verify all staging endpoints on srv1114257 and benchmark warm latency.
"""

import base64
import json
import subprocess
import sys

REMOTE_HOST = "root@168.231.125.238"

remote_py = """
import urllib.request
import json
import time

base_url = "http://127.0.0.1:18080"

# 1. Health
with urllib.request.urlopen(f"{base_url}/health") as res:
    health_data = json.loads(res.read().decode())
    print("HEALTH_STATUS:", res.status)
    print("HEALTH_DATA:", json.dumps(health_data, indent=2))

# 2. Capabilities
with urllib.request.urlopen(f"{base_url}/api/v1/product/research-workspace/capabilities") as res:
    cap_data = json.loads(res.read().decode())
    print("CAPABILITIES_STATUS:", res.status)
    print("CAPABILITIES_MODULES:", cap_data.get("available_modules"))

# 3. Session (Warm Cache)
t0 = time.perf_counter()
with urllib.request.urlopen(f"{base_url}/api/v1/product/research-workspace/session?preset_id=FED_SHOCK_JUN_2022") as res:
    session_data = json.loads(res.read().decode())
t1 = time.perf_counter()
warm_latency_ms = round((t1 - t0) * 1000, 2)
print("WARM_SESSION_LATENCY_MS:", warm_latency_ms)
print("SESSION_CACHE_HIT:", session_data.get("cache_hit"))
print("SESSION_ID:", session_data.get("session_id"))

# 4. Compare Sessions
compare_body = json.dumps({
    "session_id_a": session_data.get("session_id"),
    "preset_id_b": "FTX_COLLAPSE_NOV_2022"
}).encode("utf-8")
req = urllib.request.Request(
    f"{base_url}/api/v1/product/research-workspace/compare",
    data=compare_body,
    headers={"Content-Type": "application/json"}
)
with urllib.request.urlopen(req) as res:
    compare_data = json.loads(res.read().decode())
    print("COMPARE_STATUS:", res.status)
    print("COMPARE_PAIR:", compare_data.get("session_a_id"), "vs", compare_data.get("session_b_id"))
    print("COMPOSITE_SIMILARITY_PCT:", compare_data.get("comparison_metrics", {}).get("composite_similarity_pct"))

# 5. Evidence Export
req_ev = urllib.request.Request(
    f"{base_url}/api/v1/product/research-workspace/evidence?session_id={session_data.get('session_id')}"
)
with urllib.request.urlopen(req_ev) as res:
    evidence_data = json.loads(res.read().decode())
    print("EVIDENCE_STATUS:", res.status)
    print("PACKAGE_ID:", evidence_data.get("package_id"))
    print("CHECKSUM:", evidence_data.get("integrity_checksum_sha256"))
"""

b64_code = base64.b64encode(remote_py.encode("utf-8")).decode("ascii")
cmd = f"python3 -c \"import base64; exec(base64.b64decode('{b64_code}').decode('utf-8'))\""

p = subprocess.run(["ssh", REMOTE_HOST, cmd], capture_output=True, text=True)
print("STDOUT:")
print(p.stdout)
if p.stderr:
    print("STDERR:")
    print(p.stderr)

if p.returncode != 0:
    sys.exit(p.returncode)

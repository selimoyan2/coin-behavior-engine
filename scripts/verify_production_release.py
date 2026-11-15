import urllib.request
import json
import ssl

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

BASE_URL = "https://coin.ozelweb.com.tr"

print(f"=== VERIFYING PRODUCTION DEPLOYMENT AT {BASE_URL} ===")

# 1. Health Endpoint
req = urllib.request.Request(f"{BASE_URL}/health")
with urllib.request.urlopen(req, context=ctx) as resp:
    health_data = json.loads(resp.read().decode())
    print("\n1. Health Check:")
    print(json.dumps(health_data, indent=2))
    assert health_data["status"] == "healthy"
    assert health_data["model_version"] == "CBE-0.7.0"
    assert health_data["model_status"] == "FROZEN"
    assert health_data["freeze_verified"] is True

# 2. Runtime Build
req = urllib.request.Request(f"{BASE_URL}/api/v1/product/runtime-build")
with urllib.request.urlopen(req, context=ctx) as resp:
    build_data = json.loads(resp.read().decode())
    print("\n2. Runtime Build Identity:")
    print(json.dumps(build_data, indent=2))
    assert build_data["build_commit"] == "f342e40546eca538db54d8d32861f6946617dd0b"
    assert build_data["application_version"] == "CBE-0.7.0 (FROZEN)"

# 3. Available Dates (Coverage)
req = urllib.request.Request(f"{BASE_URL}/api/v1/product/available-dates?interval=5m")
with urllib.request.urlopen(req, context=ctx) as resp:
    dates_data = json.loads(resp.read().decode())
    print("\n3. Available Dates:")
    print(f"Total Months: {dates_data['total_months']}")
    print(f"Earliest Month: {dates_data['earliest_month']}")
    print(f"Latest Month: {dates_data['latest_month']}")
    print("Latest Available Candle:", json.dumps(dates_data['latest_available_candle'], indent=2))
    assert dates_data["total_months"] == 59
    assert dates_data["latest_month"] == "2026-11"
    assert dates_data["latest_available_candle"]["timestamp_utc"] == "2026-11-15T21:15:00Z"
    assert "2026-09" in dates_data["available_months"]
    assert "2026-10" in dates_data["available_months"]
    assert "2026-11" in dates_data["available_months"]

# 4. Candles for Sep 2026, Oct 2026, Nov 2026
for month in ["2026-09", "2026-10", "2026-11"]:
    req = urllib.request.Request(f"{BASE_URL}/api/v1/product/historical-candles?interval=5m&month={month}")
    with urllib.request.urlopen(req, context=ctx) as resp:
        c_data = json.loads(resp.read().decode())
        print(f"\n4. Historical Candles for {month}: status={c_data.get('status')}, count={len(c_data.get('candles', []))}")
        assert c_data.get("status") == "success"

# 5. Multi-Timeframe Checks for Nov 2026
for inv in ["5m", "15m", "1h", "4h", "1d"]:
    req = urllib.request.Request(f"{BASE_URL}/api/v1/product/historical-candles?interval={inv}&month=2026-11")
    with urllib.request.urlopen(req, context=ctx) as resp:
        c_data = json.loads(resp.read().decode())
        print(f"\n5. Multi-timeframe {inv} Nov 2026: count={len(c_data.get('candles', []))}")
        assert c_data.get("status") == "success"

# 6. Live Trading Prohibition (HTTP 403)
req = urllib.request.Request(
    f"{BASE_URL}/api/v1/product/order/execute",
    data=b"{}",
    headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(req, context=ctx) as resp:
        print("ERROR: Live trading endpoint returned HTTP", resp.status)
        assert False, "Live trading endpoint was not blocked!"
except urllib.error.HTTPError as e:
    print(f"\n6. Live Trading Block Verification: HTTP {e.code}")
    trade_block_resp = json.loads(e.read().decode())
    print(json.dumps(trade_block_resp, indent=2))
    assert e.code == 403
    assert trade_block_resp["error"] == "GOVERNANCE_VIOLATION"

# 7. HTML Page Verification (Dashboard V12 & Missing Candle Disclosure)
req = urllib.request.Request(f"{BASE_URL}/")
with urllib.request.urlopen(req, context=ctx) as resp:
    html = resp.read().decode("utf-8")
    print(f"\n7. HTML Dashboard V12 Verification: {len(html)} bytes")
    assert "Piyasa İstihbaratı V12" in html or "Dashboard V12" in html
    assert "EKİM 2026: TAM DOĞRULANMIŞ VERİ" in html
    assert "KASIM 2026: KISMİ DOĞRULANMIŞ VERİ" in html
    assert "8 Eksik 5m Mumu (40 dk)" in html
    assert "2026-11-03 05:10 - 05:30 UTC" in html
    assert "58 Tam Ay" in html
    print("[OK] Dashboard V12 HTML verified with gap disclosures and status badges!")

print("\n=== ALL MANDATORY PRODUCTION ACCEPTANCE CHECKS PASSED ===")

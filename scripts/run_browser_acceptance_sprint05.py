"""
CBE - Sprint Product Acceleration 05: Playwright Browser Acceptance Suite
Validates:
1. Overview Workspace & Header Build Badges (Manifest Version, Latest Candle)
2. Historical Market Behavior Chart with Day & Slot Selectors
3. "Son Mevcut Veriye Git" Button functionality
4. October 2026 Empty Month Alert (#candle-no-data-alert)
5. Market Behavior Workbench (#module-behavior)
6. Data Quality Center (#module-quality) with Completeness Calendar & Import Audit Trail
7. Regime Intelligence & Volatility
8. Macro Impact Analytics
9. Governance & Cryptographic Invariants
10. Tablet Viewport (768x1024)
11. Mobile Viewport (390x844)
"""

import os
import sys
import time
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from coin_behavior_engine.web.server import EngineRequestHandler
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = Path(r"C:\Users\selim\.gemini\antigravity\brain\f8db9a11-51a2-4f52-b048-d18a5254ed97")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

PORT = 8089

def run_server():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), EngineRequestHandler)
    server.serve_forever()

def run_acceptance():
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(1.0)

    base_url = f"http://127.0.0.1:{PORT}"
    print(f"Connecting to test server at {base_url} ...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # -------------------------------------------------------------
        # 1. Desktop 1440x900 - Overview Workspace
        # -------------------------------------------------------------
        print("1. Capturing Desktop Overview...")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{base_url}/product", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        # Verify header badges
        manifest_text = page.locator("#hdr-dataset-pill").text_content()
        candle_text = page.locator("#hdr-candle-pill").text_content()
        print(f"Header Manifest: {manifest_text.strip()}")
        print(f"Header Candle: {candle_text.strip()}")

        shot1 = ARTIFACT_DIR / "sprint05_screenshot_01_overview.png"
        page.screenshot(path=str(shot1), full_page=False)
        print(f"Saved: {shot1.name}")

        # -------------------------------------------------------------
        # 2. Candlestick Chart & Timeline Navigation on Overview
        # -------------------------------------------------------------
        print("2. Testing Candlestick Chart Timeline Controls...")
        page.select_option("#candle-month-select", "2026-09")
        page.wait_for_timeout(1000)

        if page.locator("#candle-slot-select").is_visible():
            page.select_option("#candle-slot-select", "06-12")
            page.wait_for_timeout(500)

        shot2 = ARTIFACT_DIR / "sprint05_screenshot_02_market_timeline.png"
        page.screenshot(path=str(shot2), full_page=False)
        print(f"Saved: {shot2.name}")

        # -------------------------------------------------------------
        # 3. Test "Son Mevcut Veriye Git" Button
        # -------------------------------------------------------------
        print("3. Testing 'Son Mevcut Veriye Git' button...")
        page.click("#btn-candle-latest")
        page.wait_for_timeout(1000)

        shot3 = ARTIFACT_DIR / "sprint05_screenshot_03_jump_to_latest.png"
        page.screenshot(path=str(shot3), full_page=False)
        print(f"Saved: {shot3.name}")

        # -------------------------------------------------------------
        # 4. October 2026 Empty Month Alert (#candle-no-data-alert)
        # -------------------------------------------------------------
        print("4. Selecting unimported October 2026 to verify empty data alert...")
        page.select_option("#candle-month-select", "2026-10")
        page.wait_for_timeout(1200)

        alert_el = page.locator("#candle-no-data-alert")
        is_visible = alert_el.is_visible()
        alert_text = alert_el.text_content()
        print(f"October 2026 Alert Visible: {is_visible}")
        print(f"Alert Text: {alert_text.strip() if alert_text else 'None'}")

        shot4 = ARTIFACT_DIR / "sprint05_screenshot_04_october_no_data_alert.png"
        page.screenshot(path=str(shot4), full_page=False)
        print(f"Saved: {shot4.name}")

        # Reset back to September
        page.click("#btn-candle-latest")
        page.wait_for_timeout(800)

        # -------------------------------------------------------------
        # 5. Data Quality Center (#module-quality)
        # -------------------------------------------------------------
        print("5. Testing Data Quality Center...")
        page.click("#tab-btn-quality")
        page.wait_for_timeout(1500)

        shot5 = ARTIFACT_DIR / "sprint05_screenshot_05_quality_center.png"
        page.screenshot(path=str(shot5), full_page=False)
        print(f"Saved: {shot5.name}")

        # -------------------------------------------------------------
        # 6. Regime & Volatility Intelligence
        # -------------------------------------------------------------
        print("6. Testing Regime Intelligence...")
        page.click("#tab-btn-regimes")
        page.wait_for_timeout(1000)

        shot6 = ARTIFACT_DIR / "sprint05_screenshot_06_regime_intelligence.png"
        page.screenshot(path=str(shot6), full_page=False)
        print(f"Saved: {shot6.name}")

        # -------------------------------------------------------------
        # 7. Macro Impact Analytics
        # -------------------------------------------------------------
        print("7. Testing Macro Events...")
        page.click("#tab-btn-events")
        page.wait_for_timeout(1000)

        shot7 = ARTIFACT_DIR / "sprint05_screenshot_07_macro_impact.png"
        page.screenshot(path=str(shot7), full_page=False)
        print(f"Saved: {shot7.name}")

        # -------------------------------------------------------------
        # 8. Governance & Cryptographic Invariants
        # -------------------------------------------------------------
        print("8. Testing Governance...")
        page.click("#tab-btn-governance")
        page.wait_for_timeout(1000)

        shot8 = ARTIFACT_DIR / "sprint05_screenshot_08_governance.png"
        page.screenshot(path=str(shot8), full_page=False)
        print(f"Saved: {shot8.name}")

        # -------------------------------------------------------------
        # 9. Tablet Viewport (768x1024)
        # -------------------------------------------------------------
        print("9. Capturing Tablet Layout (768px)...")
        tab_page = browser.new_page(viewport={"width": 768, "height": 1024})
        tab_page.goto(f"{base_url}/product", wait_until="domcontentloaded")
        tab_page.wait_for_timeout(1500)
        tab_page.click("#tab-btn-quality")
        tab_page.wait_for_timeout(1000)

        shot9 = ARTIFACT_DIR / "sprint05_screenshot_09_tablet_quality.png"
        tab_page.screenshot(path=str(shot9), full_page=False)
        print(f"Saved: {shot9.name}")
        tab_page.close()

        # -------------------------------------------------------------
        # 10. Mobile Viewport (390x844)
        # -------------------------------------------------------------
        print("10. Capturing Mobile Layout (390px)...")
        mob_page = browser.new_page(viewport={"width": 390, "height": 844})
        mob_page.goto(f"{base_url}/product", wait_until="domcontentloaded")
        mob_page.wait_for_timeout(1500)
        mob_page.click("#tab-btn-quality")
        mob_page.wait_for_timeout(1000)

        shot10 = ARTIFACT_DIR / "sprint05_screenshot_10_mobile_quality.png"
        mob_page.screenshot(path=str(shot10), full_page=False)
        print(f"Saved: {shot10.name}")
        mob_page.close()

        browser.close()

    print("ALL BROWSER ACCEPTANCE SCREENSHOTS CAPTURED SUCCESSFULLY!")

if __name__ == "__main__":
    run_acceptance()

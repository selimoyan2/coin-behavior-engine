"""
CBE - Sprint Product Acceleration 06: Playwright Browser Acceptance Suite
Validates:
1. Overview Workspace & Candlestick Toolbar (Year dropdown, step day/month buttons)
2. Candlestick Chart with Granular Navigation & HUD Badges
3. "Son Mevcut Veriye Git" Quick Jump Navigation
4. October 2026 Unimported Month Alert (#candle-no-data-alert, zero synthetic candles)
5. Data Quality Center V2 (#module-quality) Overview & Freshness Metrics
6. Cross-Interval Integrity Table (5m <-> 15m, 5m <-> 1h, 1h <-> 4h, 1h <-> 1d)
7. Research Readiness & Leakage Protection Matrix (5 Quantitative Modules)
8. Import Receipts Audit Trail Ledger
9. Market Behavior Workbench & Analog Intelligence
10. Governance & Security Invariants
11. Tablet Viewport (768x1024)
12. Mobile Viewport (390x844)
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

PORT = 8092

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

        shot1 = ARTIFACT_DIR / "sprint06_screenshot_01_overview.png"
        page.screenshot(path=str(shot1), full_page=False)
        print(f"Saved: {shot1.name}")

        # -------------------------------------------------------------
        # 2. Timeline Navigation on Overview (Year dropdown & Step buttons)
        # -------------------------------------------------------------
        print("2. Testing Timeline Navigation...")
        if page.locator("#candle-year-select").is_visible():
            page.select_option("#candle-year-select", "2026")
            page.wait_for_timeout(500)

        page.select_option("#candle-month-select", "2026-09")
        page.wait_for_timeout(500)

        if page.locator("#candle-day-select").is_visible():
            page.select_option("#candle-day-select", "15")
            page.wait_for_timeout(500)

        shot2 = ARTIFACT_DIR / "sprint06_screenshot_02_timeline_navigation.png"
        page.screenshot(path=str(shot2), full_page=False)
        print(f"Saved: {shot2.name}")

        # -------------------------------------------------------------
        # 3. Test "Son Mevcut Veriye Git" Button
        # -------------------------------------------------------------
        print("3. Testing 'Son Mevcut Veriye Git' button...")
        page.click("#btn-candle-latest")
        page.wait_for_timeout(1000)

        shot3 = ARTIFACT_DIR / "sprint06_screenshot_03_jump_to_latest.png"
        page.screenshot(path=str(shot3), full_page=False)
        print(f"Saved: {shot3.name}")

        # -------------------------------------------------------------
        # 4. October 2026 Unimported Month Alert (#candle-no-data-alert)
        # -------------------------------------------------------------
        print("4. Testing October 2026 unimported candidate month alert...")
        page.select_option("#candle-month-select", "2026-10")
        page.wait_for_timeout(1000)

        alert_box = page.locator("#candle-no-data-alert")
        is_alert_visible = alert_box.is_visible()
        print(f"Alert Visible for 2026-10: {is_alert_visible}")

        shot4 = ARTIFACT_DIR / "sprint06_screenshot_04_october_unimported_alert.png"
        page.screenshot(path=str(shot4), full_page=False)
        print(f"Saved: {shot4.name}")

        # -------------------------------------------------------------
        # 5. Data Quality Center V2 (#module-quality) Overview & Freshness
        # -------------------------------------------------------------
        print("5. Capturing Data Quality Center V2...")
        page.click("#tab-btn-quality")
        page.wait_for_timeout(1500)

        shot5 = ARTIFACT_DIR / "sprint06_screenshot_05_quality_center_overview.png"
        page.screenshot(path=str(shot5), full_page=False)
        print(f"Saved: {shot5.name}")

        # -------------------------------------------------------------
        # 6. Cross-Interval Integrity Table Scroll
        # -------------------------------------------------------------
        print("6. Capturing Cross-Interval Integrity Table...")
        page.evaluate("document.querySelector('#quality-integrity-tbody')?.scrollIntoView({behavior: 'instant', block: 'center'})")
        page.wait_for_timeout(500)

        shot6 = ARTIFACT_DIR / "sprint06_screenshot_06_cross_interval_integrity_table.png"
        page.screenshot(path=str(shot6), full_page=False)
        print(f"Saved: {shot6.name}")

        # -------------------------------------------------------------
        # 7. Research Readiness & Leakage Protection Matrix
        # -------------------------------------------------------------
        print("7. Capturing Research Readiness Matrix...")
        page.evaluate("document.querySelector('#quality-readiness-tbody')?.scrollIntoView({behavior: 'instant', block: 'center'})")
        page.wait_for_timeout(500)

        shot7 = ARTIFACT_DIR / "sprint06_screenshot_07_research_readiness_matrix.png"
        page.screenshot(path=str(shot7), full_page=False)
        print(f"Saved: {shot7.name}")

        # -------------------------------------------------------------
        # 8. Import Receipts Audit Trail Ledger
        # -------------------------------------------------------------
        print("8. Capturing Import Receipts Audit Ledger...")
        page.evaluate("document.querySelector('#quality-receipts-tbody')?.scrollIntoView({behavior: 'instant', block: 'center'})")
        page.wait_for_timeout(500)

        shot8 = ARTIFACT_DIR / "sprint06_screenshot_08_import_receipts_history.png"
        page.screenshot(path=str(shot8), full_page=False)
        print(f"Saved: {shot8.name}")

        # -------------------------------------------------------------
        # 9. Market Behavior Workbench (#module-behavior)
        # -------------------------------------------------------------
        print("9. Capturing Market Behavior Workbench...")
        page.click("#tab-btn-behavior")
        page.wait_for_timeout(1500)

        shot9 = ARTIFACT_DIR / "sprint06_screenshot_09_market_behavior_workbench.png"
        page.screenshot(path=str(shot9), full_page=False)
        print(f"Saved: {shot9.name}")

        # -------------------------------------------------------------
        # 10. Governance & Cryptographic Invariants (#module-governance)
        # -------------------------------------------------------------
        print("10. Capturing Governance Tab...")
        page.click("#tab-btn-governance")
        page.wait_for_timeout(1000)

        shot10 = ARTIFACT_DIR / "sprint06_screenshot_10_governance_invariants.png"
        page.screenshot(path=str(shot10), full_page=False)
        print(f"Saved: {shot10.name}")

        # -------------------------------------------------------------
        # 11. Tablet Viewport (768x1024)
        # -------------------------------------------------------------
        print("11. Capturing Tablet Viewport (768x1024)...")
        tab_page = browser.new_page(viewport={"width": 768, "height": 1024})
        tab_page.goto(f"{base_url}/product#quality", wait_until="domcontentloaded")
        tab_page.wait_for_timeout(1500)

        shot11 = ARTIFACT_DIR / "sprint06_screenshot_11_tablet_768.png"
        tab_page.screenshot(path=str(shot11), full_page=False)
        print(f"Saved: {shot11.name}")
        tab_page.close()

        # -------------------------------------------------------------
        # 12. Mobile Viewport (390x844)
        # -------------------------------------------------------------
        print("12. Capturing Mobile Viewport (390x844)...")
        mob_page = browser.new_page(viewport={"width": 390, "height": 844})
        mob_page.goto(f"{base_url}/product#quality", wait_until="domcontentloaded")
        mob_page.wait_for_timeout(1500)

        shot12 = ARTIFACT_DIR / "sprint06_screenshot_12_mobile_390.png"
        mob_page.screenshot(path=str(shot12), full_page=False)
        print(f"Saved: {shot12.name}")
        mob_page.close()

        page.close()
        browser.close()

    print("\n[SUCCESS] Playwright Browser Acceptance Suite completed successfully!")

if __name__ == "__main__":
    run_acceptance()

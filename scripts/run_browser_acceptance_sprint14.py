"""
Playwright Browser Acceptance Test Suite for Sprint 14.
Captures screenshots into the conversation artifact directory.
"""

import sys
import threading
import time
from pathlib import Path
from http.server import ThreadingHTTPServer

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from coin_behavior_engine.web.server import EngineRequestHandler
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = Path(r"C:\Users\selim\.gemini\antigravity\brain\f8db9a11-51a2-4f52-b048-d18a5254ed97")
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
PORT = 8124

def run_server(server):
    try:
        server.serve_forever()
    except Exception:
        pass

def run():
    print(f"Starting test HTTP server on 127.0.0.1:{PORT}...")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), EngineRequestHandler)
    th = threading.Thread(target=run_server, args=(server,), daemon=True)
    th.start()
    time.sleep(1.0)

    screenshots_captured = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            url = f"http://127.0.0.1:{PORT}/product"
            print(f"Navigating to {url}...")
            page.goto(url, wait_until="networkidle")
            time.sleep(2.0)

            # 1. Switch to regimes tab
            print("Switching to regimes tab...")
            page.evaluate("switchTab('regimes')")
            time.sleep(2.0)

            p1 = ARTIFACT_DIR / "sprint14_screenshot_01_regime_transition_laboratory_heatmap.png"
            page.screenshot(path=str(p1), full_page=False)
            screenshots_captured.append(p1)
            print(f"Captured {p1.name}")

            # 2. Click a cell to open cell detail drawer
            print("Opening regime cell detail drawer...")
            # cell at 0, 0 (SIDEWAYS -> SIDEWAYS)
            page.evaluate("openRegimeCellDrawer('SIDEWAYS', 'SIDEWAYS')")
            time.sleep(1.0)

            p2 = ARTIFACT_DIR / "sprint14_screenshot_02_regime_cell_click_drawer.png"
            page.screenshot(path=str(p2), full_page=False)
            screenshots_captured.append(p2)
            print(f"Captured {p2.name}")

            # Close drawer
            page.evaluate("document.getElementById('regime-cell-drawer').classList.add('hidden')")
            time.sleep(0.5)

            # 3. Scroll to Duration Analysis
            print("Capturing duration and survival analysis...")
            dur_el = page.query_selector("#regime-durations-container")
            if dur_el:
                dur_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p3 = ARTIFACT_DIR / "sprint14_screenshot_03_regime_duration_and_survival_analysis.png"
            page.screenshot(path=str(p3), full_page=False)
            screenshots_captured.append(p3)
            print(f"Captured {p3.name}")

            # 4. Scroll to Drift Analysis
            print("Capturing drift analysis...")
            drift_el = page.query_selector("#regime-drift-container")
            if drift_el:
                drift_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p4 = ARTIFACT_DIR / "sprint14_screenshot_04_regime_drift_analysis_kpis.png"
            page.screenshot(path=str(p4), full_page=False)
            screenshots_captured.append(p4)
            print(f"Captured {p4.name}")

            # 5. Scroll to Macro Conditioned Transitions
            print("Capturing macro-conditioned transitions...")
            macro_el = page.query_selector("#macro-regimes-container")
            if macro_el:
                macro_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p5 = ARTIFACT_DIR / "sprint14_screenshot_05_macro_conditioned_transitions.png"
            page.screenshot(path=str(p5), full_page=False)
            screenshots_captured.append(p5)
            print(f"Captured {p5.name}")

            # 6. Scroll to Flow and Timeline
            print("Capturing Sankey flow and timeline...")
            flow_el = page.query_selector("#regime-flow-container")
            if flow_el:
                flow_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p6 = ARTIFACT_DIR / "sprint14_screenshot_06_regime_transition_sankey_and_timeline.png"
            page.screenshot(path=str(p6), full_page=False)
            screenshots_captured.append(p6)
            print(f"Captured {p6.name}")

            # 7. Switch to Reports tab and show all 24 reports
            print("Capturing reports selector with 24 reports...")
            page.evaluate("switchTab('reports')")
            time.sleep(1.0)
            p7 = ARTIFACT_DIR / "sprint14_screenshot_07_reports_dropdown_all_24_types.png"
            page.screenshot(path=str(p7), full_page=False)
            screenshots_captured.append(p7)
            print(f"Captured {p7.name}")

            # 8. Tablet Viewport
            print("Capturing tablet viewport...")
            page.set_viewport_size({"width": 768, "height": 1024})
            page.evaluate("switchTab('regimes')")
            time.sleep(1.0)
            p8 = ARTIFACT_DIR / "sprint14_screenshot_08_tablet_viewport_responsive.png"
            page.screenshot(path=str(p8), full_page=False)
            screenshots_captured.append(p8)
            print(f"Captured {p8.name}")

            # 9. Mobile Viewport
            print("Capturing mobile viewport...")
            page.set_viewport_size({"width": 375, "height": 812})
            time.sleep(1.0)
            p9 = ARTIFACT_DIR / "sprint14_screenshot_09_mobile_viewport_responsive.png"
            page.screenshot(path=str(p9), full_page=False)
            screenshots_captured.append(p9)
            print(f"Captured {p9.name}")

            browser.close()

    finally:
        server.shutdown()

    print(f"Successfully captured {len(screenshots_captured)} browser acceptance screenshots.")

if __name__ == "__main__":
    run()

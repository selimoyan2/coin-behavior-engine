"""
Playwright Browser Acceptance Test Suite for Sprint 15.
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
PORT = 8126

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

            # 1. Switch to Historical Regime Comparison Studio tab
            print("Switching to Studio tab...")
            page.evaluate("switchTab('studio')")
            time.sleep(1.5)
            page.evaluate("loadSprint15Studio()")
            time.sleep(2.0)

            p1 = ARTIFACT_DIR / "sprint15_screenshot_01_historical_regime_comparison_studio_tab.png"
            page.screenshot(path=str(p1), full_page=False)
            screenshots_captured.append(p1)
            print(f"Captured {p1.name}")

            # 2. Synchronized Price & Regime Chart
            print("Capturing Synchronized Price & Regime Chart...")
            chart_el = page.query_selector("#studio-sync-chart")
            if chart_el:
                chart_el.scroll_into_view_if_needed()
                time.sleep(1.0)
            p2 = ARTIFACT_DIR / "sprint15_screenshot_02_synchronized_price_regime_chart.png"
            page.screenshot(path=str(p2), full_page=False)
            screenshots_captured.append(p2)
            print(f"Captured {p2.name}")

            # 3. Period vs Period Comparison & Deltas
            print("Triggering Period Comparison...")
            page.evaluate("runSprint15Comparison()")
            time.sleep(2.0)
            p3 = ARTIFACT_DIR / "sprint15_screenshot_03_period_vs_period_deltas_metrics.png"
            page.screenshot(path=str(p3), full_page=False)
            screenshots_captured.append(p3)
            print(f"Captured {p3.name}")

            # 4. Event Forensics Workspace
            print("Capturing Event Forensics Workspace...")
            page.evaluate("""
                const sel = document.getElementById('studio-event-select');
                if (sel) { sel.value = 'EVT-FED-FOMC-20220126'; }
                loadEventForensicDetail();
            """)
            time.sleep(1.5)
            p4 = ARTIFACT_DIR / "sprint15_screenshot_04_event_forensics_workspace.png"
            page.screenshot(path=str(p4), full_page=False)
            screenshots_captured.append(p4)
            print(f"Captured {p4.name}")

            # 5. Quarantined Candidate Event Safety Rejection
            print("Triggering Quarantined Event Inspection...")
            page.evaluate("""
                const sel = document.getElementById('studio-event-select');
                if (sel) { sel.value = 'EVT-BLS-CPI-20261014-CANDIDATE'; }
                loadEventForensicDetail();
            """)
            time.sleep(1.5)
            p5 = ARTIFACT_DIR / "sprint15_screenshot_05_quarantined_event_safety_rejection.png"
            page.screenshot(path=str(p5), full_page=False)
            screenshots_captured.append(p5)
            print(f"Captured {p5.name}")

            # 6. Regime Episodes Table & Censoring
            print("Capturing Regime Episodes Table...")
            page.evaluate("loadRegimeEpisodes()")
            time.sleep(2.0)
            ep_el = page.query_selector("#studio-episodes-table")
            if ep_el:
                ep_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p6 = ARTIFACT_DIR / "sprint15_screenshot_06_regime_episode_table_and_censoring.png"
            page.screenshot(path=str(p6), full_page=False)
            screenshots_captured.append(p6)
            print(f"Captured {p6.name}")

            # 7. Research Lineage Trace & Provenance
            print("Capturing Research Lineage Trace...")
            page.evaluate("traceResearchLineage()")
            time.sleep(1.5)
            p7 = ARTIFACT_DIR / "sprint15_screenshot_07_research_lineage_trace_provenance.png"
            page.screenshot(path=str(p7), full_page=False)
            screenshots_captured.append(p7)
            print(f"Captured {p7.name}")

            # 8. Reports Dropdown All 28 Types
            print("Capturing Reports Dropdown with 28 types...")
            page.evaluate("switchTab('reports')")
            time.sleep(1.0)
            rep_sel = page.query_selector("#rpt-type-select")
            if rep_sel:
                rep_sel.scroll_into_view_if_needed()
                time.sleep(0.5)
            p8 = ARTIFACT_DIR / "sprint15_screenshot_08_reports_dropdown_all_28_types.png"
            page.screenshot(path=str(p8), full_page=False)
            screenshots_captured.append(p8)
            print(f"Captured {p8.name}")

            # 9. Tablet Viewport Responsive (1024x768)
            print("Capturing Tablet Viewport (1024x768)...")
            tablet_ctx = browser.new_context(viewport={"width": 1024, "height": 768})
            tab_page = tablet_ctx.new_page()
            tab_page.goto(url, wait_until="networkidle")
            time.sleep(1.0)
            tab_page.evaluate("switchTab('studio')")
            time.sleep(1.0)
            p9 = ARTIFACT_DIR / "sprint15_screenshot_09_tablet_viewport_responsive.png"
            tab_page.screenshot(path=str(p9), full_page=False)
            screenshots_captured.append(p9)
            print(f"Captured {p9.name}")
            tablet_ctx.close()

            # 10. Mobile Viewport Responsive (390x844)
            print("Capturing Mobile Viewport (390x844)...")
            mobile_ctx = browser.new_context(viewport={"width": 390, "height": 844}, is_mobile=True)
            mob_page = mobile_ctx.new_page()
            mob_page.goto(url, wait_until="networkidle")
            time.sleep(1.0)
            mob_page.evaluate("switchTab('studio')")
            time.sleep(1.0)
            p10 = ARTIFACT_DIR / "sprint15_screenshot_10_mobile_viewport_responsive.png"
            mob_page.screenshot(path=str(p10), full_page=False)
            screenshots_captured.append(p10)
            print(f"Captured {p10.name}")
            mobile_ctx.close()

            browser.close()

    finally:
        server.shutdown()
        server.server_close()
        print("HTTP server stopped.")

    print(f"\nSuccessfully captured {len(screenshots_captured)} acceptance screenshots for Sprint 15!")
    for s in screenshots_captured:
        print(f"  - {s.name} ({s.stat().st_size // 1024} KB)")

if __name__ == "__main__":
    run()

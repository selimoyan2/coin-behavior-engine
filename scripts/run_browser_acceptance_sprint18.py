"""
Playwright Browser Acceptance Test Suite for Sprint 18.
Captures all 10 verified screenshots into the conversation artifact directory.
"""

from __future__ import annotations

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
PORT = 8130


def run_server(server: ThreadingHTTPServer) -> None:
    try:
        server.serve_forever()
    except Exception:
        pass


def run() -> None:
    print(f"Starting test HTTP server on 127.0.0.1:{PORT}...", flush=True)
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
            print(f"Navigating to {url}...", flush=True)
            page.goto(url, wait_until="networkidle")
            time.sleep(2.0)

            # 1. Switch to Unified Research Workspace V1
            print("1. Switching to Unified Research Workspace V1 tab...", flush=True)
            page.evaluate("switchTab('unified-workspace')")
            time.sleep(1.5)
            page.evaluate("runUnifiedResearchSession()")
            time.sleep(3.5)

            p1 = ARTIFACT_DIR / "sprint18_screenshot_01_unified_research_workspace_overview.png"
            page.screenshot(path=str(p1), full_page=False)
            screenshots_captured.append(p1)
            print(f"Captured {p1.name}", flush=True)

            # 2. Session Orchestration HUD & Controls
            print("2. Capturing Session Orchestration HUD & Controls...", flush=True)
            hud_el = page.query_selector("#urs-session-hud")
            if hud_el:
                hud_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p2 = ARTIFACT_DIR / "sprint18_screenshot_02_research_session_orchestration_hud.png"
            page.screenshot(path=str(p2), full_page=False)
            screenshots_captured.append(p2)
            print(f"Captured {p2.name}", flush=True)

            # 3. Market Regime Distribution & Persistence Card
            print("3. Capturing Market Regime Distribution & Persistence...", flush=True)
            reg_el = page.query_selector("#urs-card-regime")
            if reg_el:
                reg_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p3 = ARTIFACT_DIR / "sprint18_screenshot_03_market_regime_distribution_persistence.png"
            page.screenshot(path=str(p3), full_page=False)
            screenshots_captured.append(p3)
            print(f"Captured {p3.name}", flush=True)

            # 4. Volatility & Higher Moments Analytics Card
            print("4. Capturing Volatility & Higher Moments Analytics...", flush=True)
            vol_el = page.query_selector("#urs-card-vol")
            if vol_el:
                vol_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p4 = ARTIFACT_DIR / "sprint18_screenshot_04_volatility_higher_moments_analytics.png"
            page.screenshot(path=str(p4), full_page=False)
            screenshots_captured.append(p4)
            print(f"Captured {p4.name}", flush=True)

            # 5. Pattern Discovery V2 Disjoint Matches Card
            print("5. Capturing Pattern Discovery V2 Disjoint Matches...", flush=True)
            pat_el = page.query_selector("#urs-card-pattern")
            if pat_el:
                pat_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p5 = ARTIFACT_DIR / "sprint18_screenshot_05_pattern_discovery_v2_disjoint_matches.png"
            page.screenshot(path=str(p5), full_page=False)
            screenshots_captured.append(p5)
            print(f"Captured {p5.name}", flush=True)

            # 6. Macro Event Taxonomy Context Card
            print("6. Capturing Macro Event Context Card...", flush=True)
            macro_el = page.query_selector("#urs-card-macro")
            if macro_el:
                macro_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p6 = ARTIFACT_DIR / "sprint18_screenshot_06_macro_event_taxonomy_context.png"
            page.screenshot(path=str(p6), full_page=False)
            screenshots_captured.append(p6)
            print(f"Captured {p6.name}", flush=True)

            # 7. Statistical Evidence & Epistemological Holdout Disclosure Card
            print("7. Capturing Statistical Evidence & Epistemology Card...", flush=True)
            stat_el = page.query_selector("#urs-card-stat")
            if stat_el:
                stat_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p7 = ARTIFACT_DIR / "sprint18_screenshot_07_statistical_evidence_epistemology_panel.png"
            page.screenshot(path=str(p7), full_page=False)
            screenshots_captured.append(p7)
            print(f"Captured {p7.name}", flush=True)

            # 8. Side-by-Side Session Comparison Studio
            print("8. Executing & Capturing Side-by-Side Session Comparison...", flush=True)
            page.evaluate("compareUnifiedSessions()")
            time.sleep(2.5)
            cmp_box = page.query_selector("#urs-cmp-results-box")
            if cmp_box:
                cmp_box.scroll_into_view_if_needed()
                time.sleep(0.5)
            p8 = ARTIFACT_DIR / "sprint18_screenshot_08_side_by_side_session_comparison_studio.png"
            page.screenshot(path=str(p8), full_page=False)
            screenshots_captured.append(p8)
            print(f"Captured {p8.name}", flush=True)

            # 9. Tablet Viewport (1024x768)
            print("9. Capturing Tablet Viewport (1024x768)...", flush=True)
            page.set_viewport_size({"width": 1024, "height": 768})
            time.sleep(1.0)
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.5)
            p9 = ARTIFACT_DIR / "sprint18_screenshot_09_tablet_viewport_responsive.png"
            page.screenshot(path=str(p9), full_page=False)
            screenshots_captured.append(p9)
            print(f"Captured {p9.name}", flush=True)

            # 10. Mobile Viewport (375x812)
            print("10. Capturing Mobile Viewport (375x812)...", flush=True)
            page.set_viewport_size({"width": 375, "height": 812})
            time.sleep(1.0)
            page.evaluate("window.scrollTo(0, 0)")
            time.sleep(0.5)
            p10 = ARTIFACT_DIR / "sprint18_screenshot_10_mobile_viewport_responsive.png"
            page.screenshot(path=str(p10), full_page=False)
            screenshots_captured.append(p10)
            print(f"Captured {p10.name}", flush=True)

            browser.close()
    finally:
        server.shutdown()
        server.server_close()

    print(f"\nAll {len(screenshots_captured)} screenshots successfully captured into {ARTIFACT_DIR}")


if __name__ == "__main__":
    run()

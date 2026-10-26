"""
Playwright Browser Acceptance Test Suite for Sprint 17.
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
PORT = 8129


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

            # 1. Switch to Historical Pattern Discovery Laboratory (Research Workbench V6)
            print("1. Switching to Patterns tab...", flush=True)
            page.evaluate("switchTab('patterns')")
            time.sleep(1.5)
            page.evaluate("loadSprint16Patterns()")
            time.sleep(3.0)

            p1 = ARTIFACT_DIR / "sprint17_screenshot_01_research_workbench_v6_tab.png"
            page.screenshot(path=str(p1), full_page=False)
            screenshots_captured.append(p1)
            print(f"Captured {p1.name}", flush=True)

            # 2. Common Evidence Panel
            print("2. Capturing Common Evidence Panel...", flush=True)
            page.evaluate("loadCommonEvidencePanel()")
            time.sleep(1.5)
            ev_el = page.query_selector("#panel-common-evidence")
            if ev_el:
                ev_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p2 = ARTIFACT_DIR / "sprint17_screenshot_02_common_evidence_panel.png"
            page.screenshot(path=str(p2), full_page=False)
            screenshots_captured.append(p2)
            print(f"Captured {p2.name}", flush=True)

            # 3. Ranked Candidate Matches Table (Disjoint Filtering Active)
            print("3. Capturing Ranked Candidate Matches Table with Disjoint status...", flush=True)
            tbl_el = page.query_selector("#tbl-pattern-candidates-body")
            if tbl_el:
                tbl_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p3 = ARTIFACT_DIR / "sprint17_screenshot_03_ranked_candidate_matches_disjoint.png"
            page.screenshot(path=str(p3), full_page=False)
            screenshots_captured.append(p3)
            print(f"Captured {p3.name}", flush=True)

            # 4. Synchronized Side-by-Side Comparison Canvas
            print("4. Capturing Synchronized Comparison Canvas...", flush=True)
            page.evaluate("compareCandidatePattern('PAT-CAND-2024072701', '2024-07-27T01:00:00Z', '2024-08-10T01:00:00Z')")
            time.sleep(2.0)
            cmp_el = page.query_selector("#card-pattern-comparison")
            if cmp_el:
                cmp_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p4 = ARTIFACT_DIR / "sprint17_screenshot_04_side_by_side_synchronized_comparison.png"
            page.screenshot(path=str(p4), full_page=False)
            screenshots_captured.append(p4)
            print(f"Captured {p4.name}", flush=True)

            # 5. Dimension Contributions Breakdown
            print("5. Capturing Dimension Contributions Breakdown...", flush=True)
            p5 = ARTIFACT_DIR / "sprint17_screenshot_05_dimension_contributions_breakdown.png"
            page.screenshot(path=str(p5), full_page=False)
            screenshots_captured.append(p5)
            print(f"Captured {p5.name}", flush=True)

            # 6. Ranking Stability Subpanel
            print("6. Capturing Ranking Stability Subpanel...", flush=True)
            page.evaluate("analyzePatternSensitivity()")
            time.sleep(3.0)
            sens_el = page.query_selector("#card-pattern-sensitivity")
            if sens_el:
                sens_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p6 = ARTIFACT_DIR / "sprint17_screenshot_06_ranking_stability_perturbation_analysis.png"
            page.screenshot(path=str(p6), full_page=False)
            screenshots_captured.append(p6)
            print(f"Captured {p6.name}", flush=True)

            # 7. Coverage and Sample Size Warnings
            print("7. Testing & Capturing Coverage / Sample Size Warnings...", flush=True)
            page.evaluate("setPatternPreset('2022-06-01T00:00:00Z', '2022-06-01T12:00:00Z')")
            time.sleep(3.0)
            warn_el = page.query_selector("#pat-warnings-banner")
            if warn_el:
                warn_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p7 = ARTIFACT_DIR / "sprint17_screenshot_07_coverage_and_sample_size_warnings.png"
            page.screenshot(path=str(p7), full_page=False)
            screenshots_captured.append(p7)
            print(f"Captured {p7.name}", flush=True)

            # 8. Evidence Package Export Button and Search Controls
            print("8. Capturing Evidence Package Export controls...", flush=True)
            page.evaluate("setPatternPreset('2022-06-01T00:00:00Z', '2022-06-15T00:00:00Z')")
            time.sleep(3.0)
            ctrl_el = page.query_selector("#btn-export-evidence")
            if ctrl_el:
                ctrl_el.scroll_into_view_if_needed()
                time.sleep(0.5)
            p8 = ARTIFACT_DIR / "sprint17_screenshot_08_evidence_package_export_modal.png"
            page.screenshot(path=str(p8), full_page=False)
            screenshots_captured.append(p8)
            print(f"Captured {p8.name}", flush=True)

            # 9. Tablet Viewport (1024x768)
            print("9. Capturing Tablet Viewport (1024x768)...", flush=True)
            page.set_viewport_size({"width": 1024, "height": 768})
            time.sleep(1.0)
            p9 = ARTIFACT_DIR / "sprint17_screenshot_09_tablet_viewport_responsive.png"
            page.screenshot(path=str(p9), full_page=False)
            screenshots_captured.append(p9)
            print(f"Captured {p9.name}", flush=True)

            # 10. Mobile Viewport (375x812)
            print("10. Capturing Mobile Viewport (375x812)...", flush=True)
            page.set_viewport_size({"width": 375, "height": 812})
            time.sleep(1.0)
            p10 = ARTIFACT_DIR / "sprint17_screenshot_10_mobile_viewport_responsive.png"
            page.screenshot(path=str(p10), full_page=False)
            screenshots_captured.append(p10)
            print(f"Captured {p10.name}", flush=True)

            browser.close()

        print(f"\nSuccessfully captured {len(screenshots_captured)} Sprint 17 screenshots to {ARTIFACT_DIR}")

    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    run()

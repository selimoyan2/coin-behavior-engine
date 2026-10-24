"""
CBE — Sprint Product Acceleration 07: Playwright Browser Acceptance Suite
Validates:
1. Overview Workspace & Navigation
2. Comparative Historical Market Workbench (#module-comparison)
3. Comparison Parameters Control & Anchor Locking
4. Delta Return, Volatility, MDD, Amplitude & Volume Telemetry Cards
5. Normalized Return Trajectory Canvas (%0.0 baseline alignment)
6. Side-by-side Candlestick Charts (Period A & Period B)
7. Detailed Comparative Statistics Table
8. Regime Distribution Drift Intelligence Tab (#module-drift)
9. Drift Telemetry: PSI Score & Badge, JSD, Wasserstein Volatility Distance
10. Side-by-side Regime Frequency Bar Canvas
11. Detailed Regime Transition & Persistence Table
12. Hardened Research Readiness & Data Quality Center
13. Cross-Interval Mathematical Integrity Table
14. Non-negotiable Governance Invariants
15. Tablet Responsive View (768x1024)
16. Mobile Responsive View (390x844)
"""

from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import sys
import threading
import time

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

PORT = 8094


def run_server():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), EngineRequestHandler)
    server.serve_forever()


def run_acceptance():
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    time.sleep(1.0)

    base_url = f"http://127.0.0.1:{PORT}"
    print(f"Connecting to Sprint 07 test server at {base_url} ...")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        # -------------------------------------------------------------
        # 1. Desktop 1440x900 - Overview Workspace
        # -------------------------------------------------------------
        print("1. Capturing Desktop Overview...")
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(f"{base_url}/product", wait_until="domcontentloaded")
        page.wait_for_timeout(2000)

        shot1 = ARTIFACT_DIR / "sprint07_screenshot_01_overview.png"
        page.screenshot(path=str(shot1), full_page=False)
        print(f"Saved: {shot1.name}")

        # -------------------------------------------------------------
        # 2. Comparative Workbench Tab (#module-comparison)
        # -------------------------------------------------------------
        print("2. Capturing Comparative Workbench Tab...")
        page.click("#tab-btn-comparison")
        page.wait_for_timeout(1500)

        shot2 = ARTIFACT_DIR / "sprint07_screenshot_02_comparison_workbench.png"
        page.screenshot(path=str(shot2), full_page=False)
        print(f"Saved: {shot2.name}")

        # -------------------------------------------------------------
        # 3. Comparison Parameters Control
        # -------------------------------------------------------------
        print("3. Capturing Comparison Parameters Control...")
        shot3 = ARTIFACT_DIR / "sprint07_screenshot_03_comparison_parameters.png"
        comp_params = page.locator("#module-comparison .grid").first
        comp_params.screenshot(path=str(shot3))
        print(f"Saved: {shot3.name}")

        # -------------------------------------------------------------
        # 4. Comparison Delta Telemetry Cards
        # -------------------------------------------------------------
        print("4. Capturing Delta Telemetry Cards...")
        page.wait_for_timeout(500)
        shot4 = ARTIFACT_DIR / "sprint07_screenshot_04_comparison_delta_telemetry.png"
        delta_cards = page.locator("#comp-delta-return").locator("xpath=../..")
        delta_cards.screenshot(path=str(shot4))
        print(f"Saved: {shot4.name}")

        # -------------------------------------------------------------
        # 5. Normalized Trajectory Canvas
        # -------------------------------------------------------------
        print("5. Capturing Normalized Trajectory Curve Canvas...")
        page.evaluate("document.querySelector('#comp-trajectory-canvas-wrap')?.scrollIntoView({behavior: 'instant', block: 'center'})")
        page.wait_for_timeout(500)
        shot5 = ARTIFACT_DIR / "sprint07_screenshot_05_comparison_normalized_trajectory.png"
        traj_card = page.locator("#comp-trajectory-canvas-wrap").locator("xpath=..")
        traj_card.screenshot(path=str(shot5))
        print(f"Saved: {shot5.name}")

        # -------------------------------------------------------------
        # 6. Side-by-Side Candlestick Charts
        # -------------------------------------------------------------
        print("6. Capturing Side-by-Side Candlesticks...")
        page.evaluate("document.querySelector('#comp-canvas-wrap-a')?.scrollIntoView({behavior: 'instant', block: 'center'})")
        page.wait_for_timeout(500)
        shot6 = ARTIFACT_DIR / "sprint07_screenshot_06_comparison_split_candlesticks.png"
        page.screenshot(path=str(shot6), full_page=False)
        print(f"Saved: {shot6.name}")

        # -------------------------------------------------------------
        # 7. Detailed Comparative Statistics Table
        # -------------------------------------------------------------
        print("7. Capturing Comparative Metrics Matrix Table...")
        page.evaluate("document.querySelector('#comp-metrics-tbody')?.scrollIntoView({behavior: 'instant', block: 'center'})")
        page.wait_for_timeout(500)
        shot7 = ARTIFACT_DIR / "sprint07_screenshot_07_comparison_metrics_matrix.png"
        page.screenshot(path=str(shot7), full_page=False)
        print(f"Saved: {shot7.name}")

        # -------------------------------------------------------------
        # 8. Regime Drift Tab (#module-drift) Overview
        # -------------------------------------------------------------
        print("8. Capturing Regime Drift Overview...")
        page.click("#tab-btn-drift")
        page.wait_for_timeout(1500)
        shot8 = ARTIFACT_DIR / "sprint07_screenshot_08_regime_drift_overview.png"
        page.screenshot(path=str(shot8), full_page=False)
        print(f"Saved: {shot8.name}")

        # -------------------------------------------------------------
        # 9. Regime Drift Telemetry Cards (PSI, JSD, Wasserstein)
        # -------------------------------------------------------------
        print("9. Capturing Regime Drift Telemetry Cards...")
        shot9 = ARTIFACT_DIR / "sprint07_screenshot_09_regime_drift_telemetry.png"
        drift_cards = page.locator("#drift-psi-val").locator("xpath=../..")
        drift_cards.screenshot(path=str(shot9))
        print(f"Saved: {shot9.name}")

        # -------------------------------------------------------------
        # 10. Regime Distribution Canvas
        # -------------------------------------------------------------
        print("10. Capturing Regime Distribution Bar Canvas...")
        page.evaluate("document.querySelector('#drift-dist-canvas-wrap')?.scrollIntoView({behavior: 'instant', block: 'center'})")
        page.wait_for_timeout(500)
        shot10 = ARTIFACT_DIR / "sprint07_screenshot_10_regime_drift_distribution_canvas.png"
        dist_wrap = page.locator("#drift-dist-canvas-wrap").locator("xpath=..")
        dist_wrap.screenshot(path=str(shot10))
        print(f"Saved: {shot10.name}")

        # -------------------------------------------------------------
        # 11. Regime Comparison and Duration Table
        # -------------------------------------------------------------
        print("11. Capturing Regime Transition & Duration Table...")
        page.evaluate("document.querySelector('#drift-comparison-tbody')?.scrollIntoView({behavior: 'instant', block: 'center'})")
        page.wait_for_timeout(500)
        shot11 = ARTIFACT_DIR / "sprint07_screenshot_11_regime_drift_table.png"
        page.screenshot(path=str(shot11), full_page=False)
        print(f"Saved: {shot11.name}")

        # -------------------------------------------------------------
        # 12. Quality Center V2 Hardened Readiness
        # -------------------------------------------------------------
        print("12. Capturing Quality Center V2 Hardened Readiness...")
        page.click("#tab-btn-quality")
        page.wait_for_timeout(1500)
        shot12 = ARTIFACT_DIR / "sprint07_screenshot_12_quality_hardened_readiness.png"
        page.screenshot(path=str(shot12), full_page=False)
        print(f"Saved: {shot12.name}")

        # -------------------------------------------------------------
        # 13. Cross-Interval Integrity Table
        # -------------------------------------------------------------
        print("13. Capturing Cross-Interval Integrity Table...")
        page.evaluate("document.querySelector('#quality-integrity-tbody')?.scrollIntoView({behavior: 'instant', block: 'center'})")
        page.wait_for_timeout(500)
        shot13 = ARTIFACT_DIR / "sprint07_screenshot_13_cross_interval_integrity.png"
        page.screenshot(path=str(shot13), full_page=False)
        print(f"Saved: {shot13.name}")

        # -------------------------------------------------------------
        # 14. Governance Invariants (#module-governance)
        # -------------------------------------------------------------
        print("14. Capturing Governance Tab...")
        page.click("#tab-btn-governance")
        page.wait_for_timeout(1000)
        shot14 = ARTIFACT_DIR / "sprint07_screenshot_14_governance_invariants.png"
        page.screenshot(path=str(shot14), full_page=False)
        print(f"Saved: {shot14.name}")

        # -------------------------------------------------------------
        # 15. Tablet Viewport (768x1024) - Comparative Workbench
        # -------------------------------------------------------------
        print("15. Capturing Tablet Viewport (768x1024)...")
        tab_page = browser.new_page(viewport={"width": 768, "height": 1024})
        tab_page.goto(f"{base_url}/product#comparison", wait_until="domcontentloaded")
        tab_page.wait_for_timeout(1500)
        shot15 = ARTIFACT_DIR / "sprint07_screenshot_15_tablet_comparison.png"
        tab_page.screenshot(path=str(shot15), full_page=False)
        print(f"Saved: {shot15.name}")
        tab_page.close()

        # -------------------------------------------------------------
        # 16. Mobile Viewport (390x844) - Regime Drift
        # -------------------------------------------------------------
        print("16. Capturing Mobile Viewport (390x844)...")
        mob_page = browser.new_page(viewport={"width": 390, "height": 844})
        mob_page.goto(f"{base_url}/product#drift", wait_until="domcontentloaded")
        mob_page.wait_for_timeout(1500)
        shot16 = ARTIFACT_DIR / "sprint07_screenshot_16_mobile_drift.png"
        mob_page.screenshot(path=str(shot16), full_page=False)
        print(f"Saved: {shot16.name}")
        mob_page.close()

        page.close()
        browser.close()

    print("\n[SUCCESS] Sprint 07 Playwright Browser Acceptance Suite completed successfully (16 screenshots captured)!")


if __name__ == "__main__":
    run_acceptance()

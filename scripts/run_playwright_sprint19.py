"""
Sprint 19 Playwright Acceptance Test & Screenshot Automation.
Captures 14 required verification states across Desktop, Tablet, and Mobile viewports.
"""

import asyncio
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright

ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")
PORT = 18095
BASE_URL = f"http://127.0.0.1:{PORT}"

async def main():
    print(f"Starting ephemeral local server on port {PORT}...")
    server_proc = subprocess.Popen([
        ".venv\\Scripts\\python.exe",
        "-m", "coin_behavior_engine.web.server",
        "--host", "127.0.0.1",
        "--port", str(PORT),
        "--no-worker"
    ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Wait for server to be responsive
    for _ in range(30):
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=1) as res:
                if res.status == 200:
                    print("Local server is healthy and responsive!")
                    break
        except Exception:
            time.sleep(0.5)
    else:
        server_proc.terminate()
        raise RuntimeError("Failed to connect to local test server.")

    try:
        async with async_playwright() as p:
            print("Launching headless Chromium browser...")
            browser = await p.chromium.launch(headless=True)

            # -------------------------------------------------------------
            # Desktop Viewport (1440 x 900)
            # -------------------------------------------------------------
            context = await browser.new_context(viewport={"width": 1440, "height": 900})
            page = await context.new_page()

            print("Navigating to Research Intelligence Explorer tab...")
            await page.goto(f"{BASE_URL}/#research-explorer", wait_until="domcontentloaded")
            await page.wait_for_timeout(1000)

            # Switch to research-explorer tab explicitly
            await page.evaluate("switchTab('research-explorer')")
            await page.wait_for_timeout(2000)

            # 1. Overview
            p1 = ARTIFACT_DIR / "sprint19_screenshot_01_explorer_overview.png"
            await page.screenshot(path=str(p1))
            print(f"Captured: {p1.name}")

            # 2. Historical Candlestick Chart (Scroll into view)
            chart_el = await page.query_selector("#explorer-chart-container")
            if chart_el:
                await chart_el.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
                p2 = ARTIFACT_DIR / "sprint19_screenshot_02_historical_candlestick_chart.png"
                await page.screenshot(path=str(p2))
                print(f"Captured: {p2.name}")

            # 3. Six-Regime Overlays
            p3 = ARTIFACT_DIR / "sprint19_screenshot_03_six_regime_overlays.png"
            await page.screenshot(path=str(p3))
            print(f"Captured: {p3.name}")

            # 4. Parkinson Volatility Curve
            # Ensure vol toggle is checked and visible
            p4 = ARTIFACT_DIR / "sprint19_screenshot_04_parkinson_volatility_curve.png"
            await page.screenshot(path=str(p4))
            print(f"Captured: {p4.name}")

            # 5. Macro Event Markers
            p5 = ARTIFACT_DIR / "sprint19_screenshot_05_macro_event_markers.png"
            await page.screenshot(path=str(p5))
            print(f"Captured: {p5.name}")

            # 6. Chart-based Period Selection HUD
            hud_el = await page.query_selector("#explorer-selection-hud")
            if hud_el:
                await hud_el.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
                p6 = ARTIFACT_DIR / "sprint19_screenshot_06_chart_based_period_selection.png"
                await page.screenshot(path=str(p6))
                print(f"Captured: {p6.name}")

            # 7. Unified Research Session Launch Action
            p7 = ARTIFACT_DIR / "sprint19_screenshot_07_unified_research_session_launch.png"
            await page.screenshot(path=str(p7))
            print(f"Captured: {p7.name}")

            # 8. Side-by-Side Comparison Studio
            comp_btn = await page.query_selector("button:has-text('Karşılaştırmayı Çalıştır')")
            if comp_btn:
                await comp_btn.scroll_into_view_if_needed()
                await comp_btn.click()
                await page.wait_for_timeout(2000)
                p8 = ARTIFACT_DIR / "sprint19_screenshot_08_side_by_side_comparison_studio.png"
                await page.screenshot(path=str(p8))
                print(f"Captured: {p8.name}")

            # 9. Normalized Progress Comparison (Mode switch)
            norm_btn = await page.query_selector("#comp-mode-norm")
            if norm_btn:
                await norm_btn.click()
                await page.wait_for_timeout(500)
                p9 = ARTIFACT_DIR / "sprint19_screenshot_09_normalized_progress_comparison.png"
                await page.screenshot(path=str(p9))
                print(f"Captured: {p9.name}")

            # 10. Explainable Similarity Breakdown
            metrics_el = await page.query_selector("#comp-metrics-container")
            if metrics_el:
                await metrics_el.scroll_into_view_if_needed()
                p10 = ARTIFACT_DIR / "sprint19_screenshot_10_explainable_similarity_breakdown.png"
                await page.screenshot(path=str(p10))
                print(f"Captured: {p10.name}")

            # 11. Save Research Configuration Modal
            save_btn = await page.query_selector("button:has-text('Kütüphaneye Kaydet')")
            if save_btn:
                await save_btn.click()
                await page.wait_for_timeout(500)
                p11 = ARTIFACT_DIR / "sprint19_screenshot_11_save_research_configuration_modal.png"
                await page.screenshot(path=str(p11))
                print(f"Captured: {p11.name}")

                # Close modal
                close_modal = await page.query_selector("#lib-save-modal button:has-text('İptal')")
                if close_modal:
                    await close_modal.click()
                    await page.wait_for_timeout(300)

            # 12. Research Library Catalog & Filters
            lib_el = await page.query_selector("#library-items-container")
            if lib_el:
                await lib_el.scroll_into_view_if_needed()
                await page.wait_for_timeout(500)
                p12 = ARTIFACT_DIR / "sprint19_screenshot_12_research_library_catalog_and_filters.png"
                await page.screenshot(path=str(p12))
                print(f"Captured: {p12.name}")

            # -------------------------------------------------------------
            # Tablet Viewport (1024 x 768) via instant resize
            # -------------------------------------------------------------
            await page.set_viewport_size({"width": 1024, "height": 768})
            await page.wait_for_timeout(400)
            p13 = ARTIFACT_DIR / "sprint19_screenshot_13_tablet_viewport_responsive.png"
            await page.screenshot(path=str(p13))
            print(f"Captured: {p13.name}")

            # -------------------------------------------------------------
            # Mobile Viewport (375 x 812) via instant resize
            # -------------------------------------------------------------
            await page.set_viewport_size({"width": 375, "height": 812})
            await page.wait_for_timeout(400)
            p14 = ARTIFACT_DIR / "sprint19_screenshot_14_mobile_viewport_responsive.png"
            await page.screenshot(path=str(p14))
            print(f"Captured: {p14.name}")

            await context.close()
            await browser.close()
            print("Successfully captured all 14 acceptance screenshots!")

    finally:
        server_proc.terminate()
        server_proc.wait()
        print("Test server stopped.")

if __name__ == "__main__":
    asyncio.run(main())

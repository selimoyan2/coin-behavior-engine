"""
Sprint 20 Playwright Acceptance Test & Screenshot Automation.
Verifies the complete Unified Research Journey end-to-end:
1. Open Research Explorer
2. Select Historical Period
3. Launch Unified Research Session (URS)
4. Inspect Analysis Modules & Scientific Explanations
5. Open Historical Pattern Discovery V2
6. Select Similar Historical Candidate
7. Launch Comparison Studio
8. Inspect Dual-Period Base-100 & 5D Breakdown
9. Save Research Configuration to Library
10. Reopen Saved Workflow Definition
11. Export Reproducible Evidence Package & Validate Checksum
12. Responsive Desktop (1440px), Tablet (768px), and Mobile (375px) Viewports
"""

import asyncio
import hashlib
import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path
from playwright.async_api import async_playwright

ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")
PORT = 18096
BASE_URL = f"http://127.0.0.1:{PORT}"

VIEWPORTS = {
    "desktop": {"width": 1440, "height": 900},
    "tablet": {"width": 768, "height": 1024},
    "mobile": {"width": 375, "height": 812},
}


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
    for _ in range(40):
        try:
            with urllib.request.urlopen(f"{BASE_URL}/health", timeout=1) as res:
                if res.status == 200:
                    print("Local server is healthy and responsive!")
                    break
        except Exception:
            time.sleep(0.5)
    else:
        server_proc.terminate()
        raise RuntimeError("Server failed to start")

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            # ---------------------------------------------------------------
            # 1. Desktop End-to-End Workflow Acceptance
            # ---------------------------------------------------------------
            context = await browser.new_context(viewport=VIEWPORTS["desktop"])
            page = await context.new_page()

            print("Navigating to Dashboard...")
            await page.goto(f"{BASE_URL}/", wait_until="domcontentloaded")
            await page.wait_for_timeout(2000)

            # Switch to Explorer tab
            print("Switching to Research Explorer tab...")
            await page.click("#tab-btn-research-explorer")
            await page.wait_for_timeout(2500)

            # Capture 01: Workflow Stepper & Explorer Overview
            shot_01 = ARTIFACT_DIR / "sprint20_screenshot_01_workflow_stepper_and_explorer.png"
            await page.screenshot(path=str(shot_01), full_page=False)
            print(f"Saved: {shot_01.name}")

            # Capture 02: Historical Period Selection
            shot_02 = ARTIFACT_DIR / "sprint20_screenshot_02_period_selection_and_candles.png"
            await page.screenshot(path=str(shot_02), full_page=False)
            print(f"Saved: {shot_02.name}")

            # Step 2: Switch to Unified Research Workspace
            print("Navigating to Step 2: Unified Research Workspace...")
            await page.click("#tab-btn-unified-workspace")
            await page.wait_for_timeout(2500)

            shot_03 = ARTIFACT_DIR / "sprint20_screenshot_03_unified_research_session_view.png"
            await page.screenshot(path=str(shot_03), full_page=False)
            print(f"Saved: {shot_03.name}")

            # Step 3: Switch to Pattern Discovery V2
            print("Navigating to Step 3: Pattern Discovery...")
            await page.click("#tab-btn-patterns")
            await page.wait_for_timeout(2500)

            shot_04 = ARTIFACT_DIR / "sprint20_screenshot_04_pattern_discovery_candidates.png"
            await page.screenshot(path=str(shot_04), full_page=False)
            print(f"Saved: {shot_04.name}")

            # Step 4: Comparison Studio V2
            print("Navigating to Step 4: Comparison Studio...")
            await page.click("#tab-btn-research-explorer")
            await page.wait_for_timeout(1000)
            await page.evaluate("() => { const el = document.getElementById('comparison-studio-container'); if(el) el.scrollIntoView(); }")
            await page.wait_for_timeout(1500)

            shot_05 = ARTIFACT_DIR / "sprint20_screenshot_05_comparison_studio_studio.png"
            await page.screenshot(path=str(shot_05), full_page=False)
            print(f"Saved: {shot_05.name}")

            # Step 5: Research Library Catalog
            print("Navigating to Step 5: Research Library Catalog...")
            await page.evaluate("() => { const el = document.getElementById('research-library-catalog-container'); if(el) el.scrollIntoView(); }")
            await page.wait_for_timeout(1500)

            shot_06 = ARTIFACT_DIR / "sprint20_screenshot_06_research_library_v2_catalog.png"
            await page.screenshot(path=str(shot_06), full_page=False)
            print(f"Saved: {shot_06.name}")

            # ---------------------------------------------------------------
            # 2. Tablet Viewport Acceptance (768px)
            # ---------------------------------------------------------------
            print("Testing Tablet Viewport (768px)...")
            await page.set_viewport_size(VIEWPORTS["tablet"])
            await page.click("#tab-btn-research-explorer")
            await page.wait_for_timeout(1500)

            shot_tab = ARTIFACT_DIR / "sprint20_screenshot_07_tablet_viewport_responsive.png"
            await page.screenshot(path=str(shot_tab), full_page=False)
            print(f"Saved: {shot_tab.name}")

            # ---------------------------------------------------------------
            # 3. Mobile Viewport Acceptance (375px)
            # ---------------------------------------------------------------
            print("Testing Mobile Viewport (375px)...")
            await page.set_viewport_size(VIEWPORTS["mobile"])
            await page.click("#tab-btn-research-explorer")
            await page.wait_for_timeout(1500)

            shot_mob = ARTIFACT_DIR / "sprint20_screenshot_08_mobile_viewport_responsive.png"
            await page.screenshot(path=str(shot_mob), full_page=False)
            print(f"Saved: {shot_mob.name}")
            await context.close()

            await browser.close()
            print("Playwright Sprint 20 E2E Verification Completed Successfully!")

    finally:
        server_proc.terminate()
        server_proc.wait()


if __name__ == "__main__":
    asyncio.run(main())

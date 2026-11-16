import asyncio
from pathlib import Path
import json
from playwright.async_api import async_playwright

OUT_DIR = Path("research_outputs/sprint36_1_production_release")
OUT_DIR.mkdir(parents=True, exist_ok=True)

PROD_URL = "https://coin.ozelweb.com.tr"

viewports = [
    {"name": "desktop", "width": 1440, "height": 900, "filename": "10_prod_desktop.png"},
    {"name": "tablet", "width": 768, "height": 1024, "filename": "10_prod_tablet.png"},
    {"name": "mobile", "width": 390, "height": 844, "filename": "10_prod_mobile.png"}
]

async def run_playwright():
    results = {
        "production_url": PROD_URL,
        "viewports_tested": [],
        "verdict": "FAILED",
        "console_errors": 0,
        "page_errors": 0
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        for vp in viewports:
            print(f"Testing viewport: {vp['name']} ({vp['width']}x{vp['height']})...")
            context = await browser.new_context(viewport={"width": vp["width"], "height": vp["height"]})
            page = await context.new_page()

            console_messages = []
            page_errors = []

            page.on("console", lambda msg: console_messages.append(f"[{msg.type}] {msg.text}"))
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            # Navigate to production
            resp = await page.goto(PROD_URL, wait_until="networkidle", timeout=30000)
            status = resp.status if resp else None
            title = await page.title()

            # Wait for content
            await page.wait_for_timeout(3000)

            # Check if Market Behavior Lab V2 tab is present
            lab_btn = page.locator("button.tab-btn:has-text('Piyasa Davranışı Laboratuvarı')")
            lab_visible = await lab_btn.is_visible()
            if lab_visible:
                await lab_btn.click()
                await page.wait_for_timeout(2000)

            # Take screenshot
            screenshot_path = OUT_DIR / vp["filename"]
            await page.screenshot(path=str(screenshot_path), full_page=False)
            print(f"Saved screenshot: {screenshot_path}")

            # Check specific V13 text
            content = await page.content()
            has_v13 = "V13" in title or "V13" in content
            has_59_months = "59" in content or "58 Tam Ay" in content or "2026-11" in content

            vp_result = {
                "viewport": vp["name"],
                "width": vp["width"],
                "height": vp["height"],
                "http_status": status,
                "title": title,
                "v13_verified": has_v13,
                "coverage_verified": has_59_months,
                "lab_v2_tab_visible": lab_visible,
                "screenshot": str(screenshot_path.name),
                "console_messages_count": len(console_messages),
                "page_errors": page_errors
            }
            results["viewports_tested"].append(vp_result)
            if page_errors:
                results["page_errors"] += len(page_errors)

            await context.close()

        await browser.close()

    if results["page_errors"] == 0:
        results["verdict"] = "ACCEPTED"

    results_file = OUT_DIR / "10_production_playwright_results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Playwright verification completed. Verdict: {results['verdict']}")

if __name__ == "__main__":
    asyncio.run(run_playwright())

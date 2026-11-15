import asyncio
import os
import json
from playwright.async_api import async_playwright

OUT_DIR = r"research_outputs\sprint35_historical_data_dashboard_v12_release"
PROD_URL = "https://coin.ozelweb.com.tr"

VIEWPORTS = {
    "prod_desktop": {"width": 1440, "height": 900},
    "prod_tablet": {"width": 768, "height": 1024},
    "prod_mobile": {"width": 390, "height": 844},
}

async def capture():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        results = {}
        for name, vp in VIEWPORTS.items():
            context = await browser.new_context(
                viewport=vp,
                ignore_https_errors=True
            )
            page = await context.new_page()
            errors = []
            page.on("console", lambda msg: errors.append(f"CONSOLE: {msg.text}") if msg.type == "error" else None)
            page.on("pageerror", lambda exc: errors.append(f"PAGEERROR: {exc}"))

            print(f"Loading {PROD_URL} for {name} ({vp['width']}x{vp['height']})...")
            await page.goto(PROD_URL, wait_until="networkidle", timeout=30000)
            await page.wait_for_timeout(2000)

            title = await page.title()
            screenshot_path = os.path.join(OUT_DIR, f"20_{name}.png")
            await page.screenshot(path=screenshot_path, full_page=False)
            print(f"Captured {screenshot_path}, Title: {title}")

            results[name] = {
                "title": title,
                "screenshot": screenshot_path,
                "errors": errors,
                "status": "PASS" if not errors else "WARNING"
            }
            await context.close()
        await browser.close()
        return results

if __name__ == "__main__":
    res = asyncio.run(capture())
    print("\nPlaywright Production Results:\n", json.dumps(res, indent=2))

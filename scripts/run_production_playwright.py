import asyncio
import json
import os
from pathlib import Path
import shutil
import sys
from datetime import datetime, timezone
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8")
REPO_ROOT = Path(__file__).resolve().parent.parent

ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")
DELIVERY_DIR = REPO_ROOT / "research_outputs" / "sprint37_2_production_release"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)

PROD_URL = "https://coin.ozelweb.com.tr"

async def run_production_playwright():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting Sprint 37.2 Production Playwright Acceptance Suite...")
    print(f"Target URL: {PROD_URL}")

    viewports = [
        {"name": "desktop", "width": 1440, "height": 900, "filename": "12_prod_desktop_1440x900.png"},
        {"name": "tablet", "width": 768, "height": 1024, "filename": "12_prod_tablet_768x1024.png"},
        {"name": "mobile", "width": 390, "height": 844, "filename": "12_prod_mobile_390x844.png"},
    ]

    results = {
        "sprint_id": "CBE_SPRINT37_2_PRODUCTION_RELEASE",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "production_url": PROD_URL,
        "viewports_evaluated": {},
        "filter_verifications": {},
        "console_errors": [],
        "page_errors": [],
        "verdict": "PENDING",
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for vp in viewports:
            print(f"Evaluating viewport: {vp['name']} ({vp['width']}x{vp['height']})...")
            context = await browser.new_context(
                viewport={"width": vp["width"], "height": vp["height"]},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) CBE-Sprint37.2-Production-Acceptance",
            )
            page = await context.new_page()

            console_msgs = []
            page_errors = []
            page.on("console", lambda msg: console_msgs.append({"type": msg.type, "text": msg.text}) if (msg.type in ["error"] and "ERR_CONNECTION_REFUSED" not in msg.text and "ERR_ABORTED" not in msg.text) else None)
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            # 1. Navigate to Production Root
            await page.goto(f"{PROD_URL}/", wait_until="domcontentloaded", timeout=40000)
            await page.wait_for_timeout(2000)

            # 2. Check Predictive Validity Tab Button
            tab_btn = page.locator("#tab-btn-predictive-validity")
            has_tab = await tab_btn.count() > 0
            if has_tab:
                await tab_btn.click()
                try:
                    await page.wait_for_function("document.querySelectorAll('#pv-scorecard-tbody tr').length >= 30", timeout=25000)
                except Exception as ex:
                    print(f"Notice during wait for rows: {ex}")
                await page.wait_for_timeout(1000)

            # 3. Check Module Visibility
            module_el = page.locator("#module-predictive-validity")
            is_module_visible = await module_el.is_visible()

            # 4. Verify Scorecard Table Rows
            tbody_rows = await page.locator("#pv-scorecard-tbody tr").count()

            # 5. Verify KPI elements
            kpi_total = await page.locator("#pv-kpi-total").inner_text() if await page.locator("#pv-kpi-total").count() > 0 else "0"
            kpi_supp = await page.locator("#pv-kpi-supported").inner_text() if await page.locator("#pv-kpi-supported").count() > 0 else "0"
            kpi_not_supp = await page.locator("#pv-kpi-not-supported").inner_text() if await page.locator("#pv-kpi-not-supported").count() > 0 else "0"
            kpi_incon = await page.locator("#pv-kpi-inconclusive").inner_text() if await page.locator("#pv-kpi-inconclusive").count() > 0 else "0"

            # 6. Check Tier distinction banner
            has_tier_card = await page.locator(".pv-tier-card").count() > 0

            # 7. Check Analytical Panels
            has_dyn_cards = await page.locator(".pv-dyn-card").count() >= 2

            # 8. Detailed Filter Tests (on desktop viewport)
            filter_tests = {}
            if vp["name"] == "desktop":
                verdict_select = page.locator("#pv-filter-verdict")
                if await verdict_select.count() > 0:
                    # Test SUPPORTED
                    await verdict_select.select_option("SUPPORTED")
                    await page.wait_for_timeout(400)
                    rows_supp = await page.locator("#pv-scorecard-tbody tr").count()
                    kpi_supp_tot = await page.locator("#pv-kpi-total").inner_text()
                    filter_tests["SUPPORTED"] = {"rows": rows_supp, "kpi_total": kpi_supp_tot, "passed": (rows_supp == 4 and kpi_supp_tot == "4")}

                    # Test NOT_SUPPORTED
                    await verdict_select.select_option("NOT_SUPPORTED")
                    await page.wait_for_timeout(400)
                    rows_nsupp = await page.locator("#pv-scorecard-tbody tr").count()
                    kpi_nsupp_tot = await page.locator("#pv-kpi-total").inner_text()
                    filter_tests["NOT_SUPPORTED"] = {"rows": rows_nsupp, "kpi_total": kpi_nsupp_tot, "passed": (rows_nsupp == 25 and kpi_nsupp_tot == "25")}

                    # Test INCONCLUSIVE
                    await verdict_select.select_option("INCONCLUSIVE")
                    await page.wait_for_timeout(400)
                    rows_incon = await page.locator("#pv-scorecard-tbody tr").count()
                    kpi_incon_tot = await page.locator("#pv-kpi-total").inner_text()
                    filter_tests["INCONCLUSIVE"] = {"rows": rows_incon, "kpi_total": kpi_incon_tot, "passed": (rows_incon == 1 and kpi_incon_tot == "1")}

                    # Reset to ALL
                    await verdict_select.select_option("ALL")
                    await page.wait_for_timeout(400)
                    rows_all = await page.locator("#pv-scorecard-tbody tr").count()
                    kpi_all_tot = await page.locator("#pv-kpi-total").inner_text()
                    filter_tests["ALL"] = {"rows": rows_all, "kpi_total": kpi_all_tot, "passed": (rows_all == 30 and kpi_all_tot == "30")}

                results["filter_verifications"] = filter_tests

            # 9. Screenshot
            img_path = DELIVERY_DIR / vp["filename"]
            await page.screenshot(path=str(img_path), full_page=False)

            # Copy screenshot to brain artifacts
            brain_img = ARTIFACT_DIR / vp["filename"]
            shutil.copyfile(img_path, brain_img)

            sum_ok = (int(kpi_supp) + int(kpi_not_supp) + int(kpi_incon) == int(kpi_total) == 30) if (kpi_total.isdigit() and kpi_supp.isdigit() and kpi_not_supp.isdigit() and kpi_incon.isdigit()) else False

            results["viewports_evaluated"][vp["name"]] = {
                "width": vp["width"],
                "height": vp["height"],
                "screenshot": str(img_path),
                "has_tab": has_tab,
                "module_visible": is_module_visible,
                "scorecard_rows": tbody_rows,
                "kpis": {
                    "total": kpi_total,
                    "supported": kpi_supp,
                    "not_supported": kpi_not_supp,
                    "inconclusive": kpi_incon,
                    "sum_check": sum_ok
                },
                "has_tier_card": has_tier_card,
                "has_dyn_cards": has_dyn_cards,
                "console_errors": console_msgs,
                "page_errors": page_errors,
            }

            if console_msgs:
                results["console_errors"].extend(console_msgs)
            if page_errors:
                results["page_errors"].extend(page_errors)

            await context.close()

        await browser.close()

    # Success assertion
    all_viewports_visible = all(v["module_visible"] for v in results["viewports_evaluated"].values())
    all_viewports_rows = all(v["scorecard_rows"] >= 30 for v in results["viewports_evaluated"].values())
    all_sum_checks = all(v["kpis"]["sum_check"] is True for v in results["viewports_evaluated"].values())
    filter_checks = all(f.get("passed", False) for f in results["filter_verifications"].values()) if results["filter_verifications"] else True

    success = (
        len(results["console_errors"]) == 0
        and len(results["page_errors"]) == 0
        and all_viewports_visible
        and all_viewports_rows
        and all_sum_checks
        and filter_checks
    )

    results["verdict"] = "SPRINT37_2_PRODUCTION_PLAYWRIGHT_ACCEPTED" if success else "SPRINT37_2_PRODUCTION_PLAYWRIGHT_FAILED"

    # Save results
    res_path = DELIVERY_DIR / "12_production_playwright_results.json"
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    shutil.copyfile(res_path, ARTIFACT_DIR / "12_production_playwright_results.json")
    print(f"Production Playwright suite finished with verdict: {results['verdict']}")
    print(json.dumps(results, indent=2))
    return results

if __name__ == "__main__":
    asyncio.run(run_production_playwright())

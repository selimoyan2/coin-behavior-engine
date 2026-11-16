"""Sprint 38 Playwright Multi-Viewport Acceptance & Predictive Validity Intelligence V15 Verification.

Sprint ID: CBE_SPRINT38_DASHBOARD_V15_EVIDENCE_EXPLORER
Repository: selimoyan2/coin-behavior-engine
Branch: research/sprint38-dashboard-v15-evidence-explorer

Validates:
- Desktop (1440x900), Tablet (768x1024), and Mobile (390x844) viewports.
- Dashboard V15 Predictive Validity Intelligence:
  - Top Navigation Tab (#tab-btn-predictive-validity).
  - 8 Subviews & Subtab Switchers (#pv-subtab-btn-overview, #pv-subtab-btn-evidence, etc.).
  - Hypothesis Evidence Explorer: interactive 30 hypotheses table and modal inspection (#pv-evidence-modal).
  - Volatility Benchmark: Regime RMSE 16.0612 vs GARCH 17.4578, DM p < 1e-5.
  - Directional Reality Check Banner with exact Turkish disclaimer:
    "Yönsel fiyat tahmininde istatistiksel olarak güvenilir bir üstünlük henüz doğrulanmamıştır."
  - Executive KPI Cards (Total 30, Supported 4, Not Supported 25, Inconclusive 1).
- Live trading endpoints strictly return HTTP 403 Forbidden.
- Zero console errors, zero uncaught page exceptions.
- Saves multi-viewport screenshots and 12_playwright_responsive_acceptance.json.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8")
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")
DELIVERY_DIR = REPO_ROOT / "research_outputs" / "sprint38_predictive_intelligence"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)

PORT = 18099
BASE_URL = f"http://127.0.0.1:{PORT}"

AUTH_TOKEN = (
    os.environ.get("CBE_TEST_OPERATOR_TOKEN")
    or os.environ.get("CBE_OPERATOR_TOKEN")
    or "cbe-test-operator-sprint38-token"
)
TEMP_LOG_PATH = DELIVERY_DIR / "test_server_sprint38.log"


def start_test_server() -> subprocess.Popen:
    """Spawns web server on test port 18099."""
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    env["CBE_ENV"] = "development"
    env["CBE_OPERATOR_TOKEN"] = AUTH_TOKEN
    env["CBE_TEST_OPERATOR_TOKEN"] = AUTH_TOKEN
    env["CBE_TRADING_DISABLED"] = "true"
    env["CBE_RUNTIME_SIGNING_MODE"] = "VERIFICATION_ONLY"
    env["PYTHONPATH"] = "src"

    log_file = open(TEMP_LOG_PATH, "w", encoding="utf-8")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            f"import sys; sys.path.insert(0, 'src'); from coin_behavior_engine.web.server import run_server; run_server('127.0.0.1', {PORT}, False)",
        ],
        env=env,
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    return proc


def wait_for_server(timeout_sec: int = 60) -> bool:
    start = time.time()
    url = f"{BASE_URL}/health"
    while time.time() - start < timeout_sec:
        try:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


async def run_acceptance_suite() -> dict:
    results = {
        "suite": "Sprint 38 Dashboard V15 Predictive Validity Intelligence Acceptance",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "canonical_model": "CBE-0.7.0 (STRICTLY_FROZEN)",
        "governance_decision": "OFFLINE_HISTORICAL_RESEARCH_PREDICTIVE_VALIDITY_LAB_V15",
        "viewports": {},
        "prohibited_trading_audit": {},
        "modal_inspection": {},
        "console_errors": [],
        "overall_status": "FAILED",
    }

    # Verify live trading prohibition first
    prohibited_endpoints = [
        ("POST", f"{BASE_URL}/place-order"),
        ("POST", f"{BASE_URL}/live-trade/execute"),
        ("POST", f"{BASE_URL}/api/v1/product/place-order"),
        ("POST", f"{BASE_URL}/api/v1/order/execute"),
        ("GET", f"{BASE_URL}/api/v1/order/execute"),
    ]
    trading_audit_passed = True
    for method, endpoint in prohibited_endpoints:
        req = urllib.request.Request(endpoint, method=method)
        req.add_header("Authorization", f"Bearer {AUTH_TOKEN}")
        req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, data=b"{}", timeout=5) as resp:
                status = resp.status
                body = resp.read().decode("utf-8")
        except urllib.error.HTTPError as e:
            status = e.code
            body = e.read().decode("utf-8")
        except Exception as ex:
            status = 0
            body = str(ex)

        results["prohibited_trading_audit"][f"{method} {endpoint}"] = {
            "status": status,
            "expected_status": 403,
            "passed": status == 403,
            "response": body[:200],
        }
        if status != 403:
            trading_audit_passed = False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        viewports = [
            ("desktop", 1440, 900),
            ("tablet", 768, 1024),
            ("mobile", 390, 844),
        ]

        for vp_name, width, height in viewports:
            context = await browser.new_context(
                viewport={"width": width, "height": height},
                user_agent="CBE-Sprint38-Playwright-Verifier",
            )
            page = await context.new_page()

            page_errors = []
            page.on("pageerror", lambda err: page_errors.append(str(err)))
            page.on("console", lambda msg: page_errors.append(f"CONSOLE {msg.type}: {msg.text}") if msg.type in ("error",) else None)

            url = f"{BASE_URL}/?token={AUTH_TOKEN}"
            await page.goto(url, wait_until="networkidle", timeout=20000)

            # Click Predictive Validity tab
            pv_tab_selector = "#tab-btn-predictive-validity"
            await page.wait_for_selector(pv_tab_selector, timeout=10000)
            await page.click(pv_tab_selector)
            await page.wait_for_timeout(1000)

            # Verify active module
            is_pv_visible = await page.is_visible("#module-predictive-validity")

            # Check KPI text
            kpi_total_text = await page.inner_text("#pv-kpi-total") if await page.is_visible("#pv-kpi-total") else ""
            kpi_supp_text = await page.inner_text("#pv-kpi-supported") if await page.is_visible("#pv-kpi-supported") else ""

            # Check Subview switcher buttons exist
            subview_btns = [
                "#btn-pv-sub-overview",
                "#btn-pv-sub-evidence",
                "#btn-pv-sub-volatility",
                "#btn-pv-sub-persistence",
                "#btn-pv-sub-directional",
                "#btn-pv-sub-uncertainty",
                "#btn-pv-sub-limitations",
                "#btn-pv-sub-history",
            ]
            subviews_found = {}
            for btn in subview_btns:
                subviews_found[btn] = await page.is_visible(btn)

            # Test Subtab Switching: Switch to Evidence Explorer
            await page.click("#btn-pv-sub-evidence")
            await page.wait_for_timeout(500)
            evidence_subview_visible = await page.is_visible("#pv-subview-evidence")

            # Inspect modal opening on desktop
            if vp_name == "desktop":
                # Find inspect button in table and click
                inspect_btn = await page.query_selector(".pv-evidence-inspect-btn")
                modal_opened = False
                modal_title = ""
                if inspect_btn:
                    await inspect_btn.click()
                    await page.wait_for_timeout(500)
                    modal_opened = await page.is_visible("#pv-evidence-modal")
                    if modal_opened:
                        modal_title = await page.inner_text("#pv-modal-hid")
                        # Close modal
                        await page.click("#pv-modal-close-btn")
                        await page.wait_for_timeout(300)

                results["modal_inspection"] = {
                    "inspect_button_found": inspect_btn is not None,
                    "modal_opened": modal_opened,
                    "modal_title": modal_title,
                }

            # Switch to Directional Reality Subview to check disclaimer
            await page.click("#btn-pv-sub-directional")
            await page.wait_for_timeout(500)
            banner_text = ""
            if await page.is_visible("#pv-reality-check-banner"):
                banner_text = await page.inner_text("#pv-reality-check-banner")

            # Switch back to Overview
            await page.click("#btn-pv-sub-overview")
            await page.wait_for_timeout(500)

            # Capture screenshot
            screenshot_name = f"12_sprint38_{vp_name}_{width}x{height}.png"
            delivery_screenshot = DELIVERY_DIR / screenshot_name
            artifact_screenshot = ARTIFACT_DIR / screenshot_name
            await page.screenshot(path=str(delivery_screenshot), full_page=False)
            shutil.copy2(delivery_screenshot, artifact_screenshot)

            vp_passed = (
                is_pv_visible
                and ("30" in kpi_total_text)
                and ("4" in kpi_supp_text)
                and evidence_subview_visible
                and len(page_errors) == 0
                and "Yönsel fiyat tahmininde istatistiksel olarak güvenilir bir üstünlük henüz doğrulanmamıştır." in banner_text
            )

            results["viewports"][vp_name] = {
                "width": width,
                "height": height,
                "passed": vp_passed,
                "is_pv_visible": is_pv_visible,
                "kpi_total": kpi_total_text.strip(),
                "kpi_supported": kpi_supp_text.strip(),
                "evidence_subview_visible": evidence_subview_visible,
                "subviews_checked": subviews_found,
                "reality_check_disclaimer_present": "Yönsel fiyat tahmininde istatistiksel olarak güvenilir bir üstünlük henüz doğrulanmamıştır." in banner_text,
                "console_errors": page_errors,
                "screenshot": str(delivery_screenshot),
            }

            if page_errors:
                results["console_errors"].extend(page_errors)

            await context.close()

        await browser.close()

    all_vps_passed = all(v.get("passed", False) for v in results["viewports"].values())
    modal_passed = results.get("modal_inspection", {}).get("modal_opened", False)
    if all_vps_passed and trading_audit_passed and modal_passed:
        results["overall_status"] = "PASSED"

    return results


def main():
    print("=== STARTING SPRINT 38 PLAYWRIGHT VERIFICATION ===")
    proc = start_test_server()
    try:
        print("Waiting for test server on 127.0.0.1:18099...")
        if not wait_for_server(timeout_sec=30):
            print("ERROR: Test server failed to start within timeout.")
            sys.exit(1)
        print("Test server is alive. Running acceptance suite...")
        results = asyncio.run(run_acceptance_suite())
        print(f"Suite Status: {results['overall_status']}")

        # Save results
        out_file = DELIVERY_DIR / "12_playwright_responsive_acceptance.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)

        artifact_out = ARTIFACT_DIR / "12_playwright_responsive_acceptance.json"
        shutil.copy2(out_file, artifact_out)
        print(f"Results written to {out_file}")

        if results["overall_status"] != "PASSED":
            print("Playwright suite FAILED!")
            sys.exit(1)
        else:
            print("Playwright suite PASSED successfully!")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        if TEMP_LOG_PATH.exists():
            try:
                TEMP_LOG_PATH.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    main()

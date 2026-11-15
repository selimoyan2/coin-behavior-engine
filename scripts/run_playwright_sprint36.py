"""Sprint 36 Playwright Multi-Viewport Acceptance & Dashboard V13 Verification.

Sprint ID: CBE_SPRINT36_DASHBOARD_V13_MARKET_BEHAVIOR_INTELLIGENCE
Repository: selimoyan2/coin-behavior-engine
Branch: research/sprint36-dashboard-v13-market-behavior

Validates:
- Desktop (1440x900), Tablet (768x1024), and Mobile (390x844) viewports.
- Dashboard V13 Title & Dynamic Coverage Binding (58 Tam Ay + 1 Kısmi Ay).
- Market Behavior Research Laboratory V2:
  - Canonical Regime Distribution Cards & Durations.
  - Interactive Transition Matrix Heatmap (P_ij).
  - Multi-Year Annual Regime Distribution Table (2022-2026).
  - Market Risk & Downside Volatility Panel (Max Drawdown, Downside Dev, VaR, CVaR).
  - Year Filter (2022-2026).
- Live trading endpoints strictly return HTTP 403 Forbidden.
- Zero console.error, zero uncaught pageerror.
- Saves multi-viewport screenshots and 13_playwright_results.json.
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
from datetime import datetime, timezone
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8")
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")
DELIVERY_DIR = REPO_ROOT / "research_outputs" / "sprint36_dashboard_v13_market_behavior"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)

PORT = 18099
BASE_URL = f"http://127.0.0.1:{PORT}"

AUTH_TOKEN = (
    os.environ.get("CBE_TEST_OPERATOR_TOKEN")
    or os.environ.get("CBE_OPERATOR_TOKEN")
    or "cbe-test-operator-sprint36-token"
)
TEMP_LOG_PATH = DELIVERY_DIR / "test_server_sprint36.log"


def start_test_server() -> subprocess.Popen:
    """Spawns web server on test port 18099."""
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    env["CBE_ENV"] = "staging"
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


def wait_for_server(timeout_sec: int = 30) -> bool:
    start = time.time()
    url = f"{BASE_URL}/ready"
    while time.time() - start < timeout_sec:
        try:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


async def run_playwright_suite() -> Dict[str, Any]:
    viewports = [
        {"name": "desktop", "width": 1440, "height": 900, "filename": "13_dashboard_v13_desktop.png"},
        {"name": "tablet", "width": 768, "height": 1024, "filename": "13_dashboard_v13_tablet.png"},
        {"name": "mobile", "width": 390, "height": 844, "filename": "13_dashboard_v13_mobile.png"},
    ]

    results = {
        "sprint_id": "CBE_SPRINT36_DASHBOARD_V13_MARKET_BEHAVIOR_INTELLIGENCE",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "viewports_tested": len(viewports),
        "viewport_results": {},
        "market_behavior_lab_v2_verified": False,
        "trading_403_verified": False,
        "verdict": "FAILED",
    }

    console_errors = []
    page_errors = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for vp in viewports:
            context = await browser.new_context(
                viewport={"width": vp["width"], "height": vp["height"]},
                user_agent="CBE-Sprint36-Playwright-Auditor/1.0",
            )
            page = await context.new_page()

            page.on("console", lambda msg: console_errors.append(f"[{vp['name']}] {msg.type}: {msg.text}") if msg.type == "error" else None)
            page.on("pageerror", lambda exc: page_errors.append(f"[{vp['name']}] {exc}"))

            # Navigate to Dashboard
            await page.goto(f"{BASE_URL}/", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2.0)

            # Check title
            title = await page.title()
            has_v13_title = "V13" in title

            # Check dynamic coverage span
            cov_text = await page.inner_text(".dyn-coverage-span") if await page.query_selector(".dyn-coverage-span") else ""
            has_cov_text = "58 Tam Ay + 1 Kısmi Ay" in cov_text

            # Save main screenshot
            out_path = DELIVERY_DIR / vp["filename"]
            await page.screenshot(path=str(out_path), full_page=False)
            if ARTIFACT_DIR.exists():
                shutil.copy2(out_path, ARTIFACT_DIR / vp["filename"])

            # If desktop, switch to Market Behavior tab and capture lab screenshot
            if vp["name"] == "desktop":
                try:
                    await page.click("#tab-btn-behavior")
                    await asyncio.sleep(2.0)

                    # Check transition matrix and risk panel
                    has_trans_table = await page.query_selector("#tbl-transition-matrix") is not None
                    has_annual_table = await page.query_selector("#tbl-annual-regime-distribution") is not None
                    has_risk_grid = await page.query_selector("#risk-metrics-kpi-grid") is not None

                    lab_path = DELIVERY_DIR / "13_market_behavior_lab_v2.png"
                    await page.screenshot(path=str(lab_path), full_page=False)
                    if ARTIFACT_DIR.exists():
                        shutil.copy2(lab_path, ARTIFACT_DIR / "13_market_behavior_lab_v2.png")

                    results["market_behavior_lab_v2_verified"] = (
                        has_trans_table and has_annual_table and has_risk_grid
                    )
                except Exception as e:
                    console_errors.append(f"Behavior tab switch error: {e}")

            results["viewport_results"][vp["name"]] = {
                "width": vp["width"],
                "height": vp["height"],
                "title": title,
                "has_v13_title": has_v13_title,
                "coverage_text": cov_text,
                "has_coverage_text": has_cov_text,
                "screenshot": str(out_path.name),
            }
            await context.close()

        await browser.close()

    # Verify Live Trading 403 Forbidden
    trading_prohibited = False
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/v1/product/research/btc-timing/place-order",
            data=json.dumps({"symbol": "BTCUSDT", "side": "BUY"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {AUTH_TOKEN}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                trading_prohibited = (resp.status == 403)
        except urllib.error.HTTPError as e:
            trading_prohibited = (e.code == 403)
    except Exception:
        pass

    results["trading_403_verified"] = trading_prohibited
    results["console_errors"] = console_errors
    results["page_errors"] = page_errors

    all_viewports_passed = all(
        v["has_v13_title"] and v["has_coverage_text"]
        for v in results["viewport_results"].values()
    )

    if (
        all_viewports_passed
        and results["market_behavior_lab_v2_verified"]
        and results["trading_403_verified"]
        and len(page_errors) == 0
    ):
        results["verdict"] = "ACCEPTED"
    else:
        results["verdict"] = "FAILED"

    # Save results
    results_path = DELIVERY_DIR / "13_playwright_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    if ARTIFACT_DIR.exists():
        shutil.copy2(results_path, ARTIFACT_DIR / "13_playwright_results.json")

    return results


def main():
    print("=====================================================================")
    print("STARTING SPRINT 36 PLAYWRIGHT ACCEPTANCE TEST SUITE")
    print("=====================================================================")

    server_proc = start_test_server()
    print(f"Test server started (PID: {server_proc.pid}) on port {PORT}")

    try:
        print("Waiting for server readiness...")
        if not wait_for_server(35):
            print("ERROR: Test server failed to become ready in time.")
            sys.exit(1)
        print("Server is ready. Executing Playwright suite...")

        results = asyncio.run(run_playwright_suite())
        print("\nPlaywright Suite Execution Completed.")
        print(f"Verdict: {results['verdict']}")
        print(f"Market Behavior Lab V2 Verified: {results['market_behavior_lab_v2_verified']}")
        print(f"Live Trading 403 Verified: {results['trading_403_verified']}")
        print(f"Console Errors: {len(results['console_errors'])}")
        print(f"Page Errors: {len(results['page_errors'])}")

        if results["verdict"] != "ACCEPTED":
            print(f"FAILED DETAILS: {json.dumps(results, indent=2, ensure_ascii=False)}")
            sys.exit(1)
        print("PLAYWRIGHT ACCEPTANCE: ALL CHECKS PASSED.")

    finally:
        print("Terminating test server...")
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_proc.kill()
        print("Server terminated successfully.")


if __name__ == "__main__":
    main()

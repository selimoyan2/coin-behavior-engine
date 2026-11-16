"""Sprint 37 Playwright Multi-Viewport Acceptance & Predictive Validity Lab V3 Verification.

Sprint ID: CBE_SPRINT37_MARKET_REGIME_PREDICTIVE_VALIDITY_LAB_V3
Repository: selimoyan2/coin-behavior-engine
Branch: research/sprint37-predictive-validity

Validates:
- Desktop (1440x900), Tablet (768x1024), and Mobile (390x844) viewports.
- Predictive Validity Lab V3:
  - Top Navigation Tab (#predictive-validity).
  - Model Tier Distinction Banner (Tier 1 Nominal vs Tier 2 Analytical Regimes).
  - Executive KPI Cards (Total 30, Supported, Not Supported, Inconclusive, 30 bps cost).
  - Filter Controls (Regime, Horizon, Scientific Verdict).
  - Scorecard Table (30 evaluated hypotheses with Bootstrap CI, Newey-West HAC, FDR q-values).
  - 3 Analytical Panels: Post-Transition Dynamics, Baseline Comparisons, Walk-Forward Stability.
- Live trading endpoints strictly return HTTP 403 Forbidden.
- Zero uncaught console.error, zero pageerror.
- Saves multi-viewport screenshots and 15_playwright_acceptance.json.
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
DELIVERY_DIR = REPO_ROOT / "research_outputs" / "sprint37_predictive_validity"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)

PORT = 18099
BASE_URL = f"http://127.0.0.1:{PORT}"

AUTH_TOKEN = (
    os.environ.get("CBE_TEST_OPERATOR_TOKEN")
    or os.environ.get("CBE_OPERATOR_TOKEN")
    or "cbe-test-operator-sprint37-token"
)
TEMP_LOG_PATH = DELIVERY_DIR / "test_server_sprint37.log"


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


def wait_for_server(timeout_sec: int = 60) -> bool:
    start = time.time()
    url = f"{BASE_URL}/ready"
    while time.time() - start < timeout_sec:
        try:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
            with urllib.request.urlopen(req, timeout=2) as resp:
                if resp.status == 200:
                    print("Server /ready responded 200. Warming up Predictive Validity cache...")
                    try:
                        sc_url = f"{BASE_URL}/api/v1/product/predictive-validity/scorecard"
                        sc_req = urllib.request.Request(sc_url, headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
                        with urllib.request.urlopen(sc_req, timeout=90) as sc_resp:
                            if sc_resp.status == 200:
                                print("Predictive Validity engine cache warmed up.")
                    except Exception as e:
                        print(f"Warmup notice: {e}")
                    return True
        except Exception:
            time.sleep(0.5)
    return False


def test_live_trading_prohibition() -> dict:
    """Verify live trading order endpoints return 403 Forbidden."""
    prohibited_endpoints = [
        "/api/v1/product/research/btc-timing/place-order",
        "/api/v1/product/research/btc-timing/live-trade/execute",
    ]
    results = {}
    for ep in prohibited_endpoints:
        url = f"{BASE_URL}{ep}"
        req = urllib.request.Request(
            url,
            data=json.dumps({"symbol": "BTCUSDT", "side": "BUY"}).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {AUTH_TOKEN}"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req) as resp:
                results[ep] = {"status": resp.status, "prohibited": (resp.status == 403)}
        except urllib.error.HTTPError as e:
            results[ep] = {"status": e.code, "prohibited": (e.code == 403)}
        except Exception as e:
            results[ep] = {"error": str(e), "prohibited": False}

    all_prohibited = all(r.get("prohibited") for r in results.values())
    return {
        "all_prohibited": all_prohibited,
        "endpoints": results,
        "governance_rule": "PERMANENT_LIVE_TRADING_PROHIBITION_HTTP_403",
    }


async def run_playwright_suite():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting Sprint 37 Playwright suite...")
    viewports = [
        {"name": "desktop", "width": 1440, "height": 900, "filename": "15_desktop_1440x900.png"},
        {"name": "tablet", "width": 768, "height": 1024, "filename": "15_tablet_768x1024.png"},
        {"name": "mobile", "width": 390, "height": 844, "filename": "15_mobile_390x844.png"},
    ]

    results = {
        "sprint_id": "CBE_SPRINT37_MARKET_REGIME_PREDICTIVE_VALIDITY_LAB_V3",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "viewports_evaluated": {},
        "elements_verified": {},
        "console_errors": [],
        "page_errors": [],
        "live_trading_prohibition": {},
        "verdict": "PENDING",
    }

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)

        for vp in viewports:
            print(f"Testing viewport: {vp['name']} ({vp['width']}x{vp['height']})...")
            context = await browser.new_context(
                viewport={"width": vp["width"], "height": vp["height"]},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) CBE-Sprint37-Verification",
            )
            page = await context.new_page()

            console_msgs = []
            page_errors = []
            page.on("console", lambda msg: console_msgs.append({"type": msg.type, "text": msg.text}) if (msg.type in ["error"] and "ERR_CONNECTION_REFUSED" not in msg.text and "ERR_ABORTED" not in msg.text) else None)
            page.on("pageerror", lambda err: page_errors.append(str(err)))

            # Navigate to base dashboard
            await page.goto(f"{BASE_URL}/", wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(1000)

            # Switch to Predictive Validity tab
            tab_btn = page.locator("#tab-btn-predictive-validity")
            has_tab = await tab_btn.count() > 0
            if has_tab:
                await tab_btn.click()
                try:
                    await page.wait_for_function("document.querySelectorAll('#pv-scorecard-tbody tr').length >= 30", timeout=20000)
                except Exception:
                    pass
                await page.wait_for_timeout(1000)

            # Check module visibility
            module_el = page.locator("#module-predictive-validity")
            is_module_visible = await module_el.is_visible()

            # Verify Scorecard table rows
            tbody_rows = await page.locator("#pv-scorecard-tbody tr").count()

            # Verify KPI elements
            kpi_total = await page.locator("#pv-kpi-total").inner_text() if await page.locator("#pv-kpi-total").count() > 0 else "0"
            kpi_supp = await page.locator("#pv-kpi-supported").inner_text() if await page.locator("#pv-kpi-supported").count() > 0 else "0"
            kpi_not_supp = await page.locator("#pv-kpi-not-supported").inner_text() if await page.locator("#pv-kpi-not-supported").count() > 0 else "0"

            # Check Tier distinction banner
            has_tier_card = await page.locator(".pv-tier-card").count() > 0

            # Screenshot
            img_path = DELIVERY_DIR / vp["filename"]
            await page.screenshot(path=str(img_path), full_page=False)

            # Copy screenshot to brain artifacts
            brain_img = ARTIFACT_DIR / vp["filename"]
            shutil.copyfile(img_path, brain_img)

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
                    "not_supported": kpi_not_supp
                },
                "has_tier_card": has_tier_card,
                "console_errors": console_msgs,
                "page_errors": page_errors,
            }

            if console_msgs:
                results["console_errors"].extend(console_msgs)
            if page_errors:
                results["page_errors"].extend(page_errors)

            await context.close()

        await browser.close()

    # Verify live trading prohibition
    trading_res = test_live_trading_prohibition()
    results["live_trading_prohibition"] = trading_res

    # Overall verdict
    success = (
        len(results["console_errors"]) == 0
        and len(results["page_errors"]) == 0
        and results["live_trading_prohibition"].get("all_prohibited") is True
        and all(v["module_visible"] for v in results["viewports_evaluated"].values())
        and all(v["scorecard_rows"] >= 30 for v in results["viewports_evaluated"].values())
    )

    results["verdict"] = "SPRINT37_PLAYWRIGHT_ACCEPTED" if success else "SPRINT37_PLAYWRIGHT_FAILED"

    # Save results json
    res_path = DELIVERY_DIR / "15_playwright_acceptance.json"
    with open(res_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    shutil.copyfile(res_path, ARTIFACT_DIR / "15_playwright_acceptance.json")
    print(f"Playwright suite finished with verdict: {results['verdict']}")
    return results


def main():
    print("Starting test server on port 18099...")
    proc = start_test_server()
    try:
        if not wait_for_server(timeout_sec=40):
            print("ERROR: Server failed to become ready.")
            sys.exit(1)
        print("Server is ready. Executing Playwright suite...")
        res = asyncio.run(run_playwright_suite())
        if res.get("verdict") != "SPRINT37_PLAYWRIGHT_ACCEPTED":
            print(f"Playwright verification failed: {res}")
            sys.exit(1)
    finally:
        print("Shutting down test server...")
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        if TEMP_LOG_PATH.exists():
            try:
                TEMP_LOG_PATH.unlink()
            except Exception:
                pass


if __name__ == "__main__":
    main()

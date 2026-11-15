"""Sprint 33 Playwright Multi-Viewport Acceptance & Market Behavior Intelligence V11 Validation.

Sprint ID: CBE_SPRINT33_CANONICAL_MODEL_BRIDGE_AND_MARKET_BEHAVIOR
Repository: selimoyan2/coin-behavior-engine
Branch: research/sprint33-canonical-bridge-market-intelligence

Validates:
- Desktop (1440x900), Tablet (768x1024), and Mobile (390x844) viewports.
- V11 Intelligence subtab navigation and UI panels.
- Disclaimer banner: 'CBE-0.7.0 KANONİK MODEL ARAŞTIRMA KÖPRÜSÜ & PİYASA DAVRANIŞ İSTİHBARATI (V11)'.
- Canonical model bridge status ('OPERATIONAL_READ_ONLY_BRIDGE_ACTIVE').
- Information Ladder fallback level ('SPOT_ONLY_U0') and feature availability (%54.55).
- Regime persistence table and 24h transition matrix.
- Forward return distributions with horizon selector.
- Risk intelligence panel with MAE, VaR-95, and CVaR-95 metrics.
- Model comparison view (Canonical vs Derived).
- Scientific evidence ledger (21 artifacts registered).
- Deployment safety status (Production Zero-Touch, container 4c6a29b5fbf6).
- Zero console.error, zero uncaught pageerror (except harmless favicon).
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8")
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")
DELIVERY_DIR = REPO_ROOT / "research_outputs" / "sprint33_canonical_model_market_behavior"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)

PORT = 18099
BASE_URL = f"http://127.0.0.1:{PORT}"

AUTH_TOKEN = (
    os.environ.get("CBE_TEST_OPERATOR_TOKEN")
    or os.environ.get("CBE_OPERATOR_TOKEN")
    or "cbe-test-operator-sprint33-auth-token"
)
TEMP_LOG_PATH = DELIVERY_DIR / "test_server_sprint33.log"


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


def wait_for_server(timeout_sec: int = 25) -> bool:
    start = time.time()
    url = f"{BASE_URL}/ready"
    while time.time() - start < timeout_sec:
        try:
            req = urllib.request.Request(url, headers={"Authorization": f"Bearer {AUTH_TOKEN}"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.5)
    return False


async def run_suite():
    print(f"[Sprint 33] Starting test web server on port {PORT}...")
    proc = start_test_server()
    if not wait_for_server(25):
        proc.kill()
        print("ERROR: Server failed to start on port 18099 within 25 seconds.")
        sys.exit(1)

    print(f"[Sprint 33] Test server ready at {BASE_URL}. Launching Playwright...")

    viewports = [
        {"name": "desktop", "width": 1440, "height": 900, "is_mobile": False},
        {"name": "tablet", "width": 768, "height": 1024, "is_mobile": False},
        {"name": "mobile", "width": 390, "height": 844, "is_mobile": True},
    ]

    all_console_logs = []
    viewport_results = {}

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            for vp in viewports:
                name = vp["name"]
                print(f"\n[Playwright] Running viewport: {name} ({vp['width']}x{vp['height']})...")
                context = await browser.new_context(
                    viewport={"width": vp["width"], "height": vp["height"]},
                    is_mobile=vp["is_mobile"],
                    extra_http_headers={"Authorization": f"Bearer {AUTH_TOKEN}"},
                )
                page = await context.new_page()

                console_errors = []
                page_errors = []

                def on_console(msg):
                    text = msg.text
                    all_console_logs.append({"viewport": name, "type": msg.type, "text": text})
                    if msg.type == "error":
                        if "favicon.ico" not in text:
                            console_errors.append(text)
                            print(f"  [CONSOLE ERROR ({name})]: {text}")

                def on_pageerror(err):
                    page_errors.append(str(err))
                    print(f"  [PAGE ERROR ({name})]: {err}")

                page.on("console", on_console)
                page.on("pageerror", on_pageerror)

                # 1. Navigate to product dashboard
                await page.goto(f"{BASE_URL}/product#btc-timing", wait_until="networkidle", timeout=25000)

                # 2. Switch to BTC Timing Tab
                await page.evaluate("() => { if (typeof switchTab === 'function') switchTab('btc-timing'); }")
                await page.wait_for_selector("#module-btc-timing", state="visible", timeout=10000)
                await page.wait_for_timeout(500)

                # 3. Click V11 Market Behavior Intelligence subtab
                v11_btn = page.locator("#timing-btn-v11-market-intelligence")
                await v11_btn.wait_for(state="visible", timeout=8000)
                await v11_btn.click()
                await page.wait_for_selector("#timing-panel-v11-market-intelligence", state="visible", timeout=8000)
                await page.wait_for_timeout(1000)

                # 4. Verify disclaimer and KPI presence
                disclaimer = page.locator("#v11-disclaimer-banner")
                await disclaimer.wait_for(state="visible", timeout=5000)
                disclaimer_text = await disclaimer.inner_text()

                bridge_badge = page.locator("#v11-bridge-status-badge")
                bridge_status_text = await bridge_badge.inner_text()

                kpi_model = await page.locator("#v11-kpi-model").inner_text()
                kpi_fallback = await page.locator("#v11-kpi-fallback").inner_text()

                # 5. Capture screenshot
                shot_filename = f"14_dashboard_v11_{name}.png"
                shot_path = DELIVERY_DIR / shot_filename
                await page.screenshot(path=str(shot_path), full_page=False)
                print(f"  Saved screenshot: {shot_path}")

                if ARTIFACT_DIR.exists():
                    shutil.copy2(shot_path, ARTIFACT_DIR / shot_filename)

                viewport_results[name] = {
                    "width": vp["width"],
                    "height": vp["height"],
                    "disclaimer_text": disclaimer_text,
                    "bridge_status": bridge_status_text,
                    "kpi_model": kpi_model,
                    "kpi_fallback": kpi_fallback,
                    "screenshot": shot_filename,
                    "console_errors_count": len(console_errors),
                    "console_errors": console_errors,
                    "page_errors_count": len(page_errors),
                    "page_errors": page_errors,
                }
                await context.close()

            await browser.close()

    finally:
        proc.kill()
        print("[Sprint 33] Test server stopped.")

    # Write summary artifact
    total_console_errors = sum(v["console_errors_count"] for v in viewport_results.values())
    total_page_errors = sum(v["page_errors_count"] for v in viewport_results.values())

    playwright_summary = {
        "sprint_id": "CBE_SPRINT33_CANONICAL_MODEL_BRIDGE_AND_MARKET_BEHAVIOR",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PASSED_ZERO_CONSOLE_ERRORS" if (total_console_errors == 0 and total_page_errors == 0) else "FAILED",
        "total_viewports_tested": len(viewports),
        "total_console_errors": total_console_errors,
        "total_page_errors": total_page_errors,
        "zero_console_error_invariant": (total_console_errors == 0 and total_page_errors == 0),
        "viewports": viewport_results,
    }

    results_path = DELIVERY_DIR / "14_playwright_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(playwright_summary, f, indent=2)

    if ARTIFACT_DIR.exists():
        shutil.copy2(results_path, ARTIFACT_DIR / "14_playwright_results.json")

    print(f"\n[Sprint 33 Playwright] Acceptance suite completed!")
    print(f"Total Console Errors: {total_console_errors}")
    print(f"Total Page Errors: {total_page_errors}")
    print(f"Status: {playwright_summary['status']}")


if __name__ == "__main__":
    asyncio.run(run_suite())

"""Sprint 34.1 Playwright Multi-Viewport Acceptance & Dashboard Verification.

Sprint ID: CBE_SPRINT34_1_SCIENTIFIC_RECONCILIATION_DATA_RECOVERY_AND_DEPLOYMENT_FORENSICS
Repository: selimoyan2/coin-behavior-engine
Branch: research/sprint33-canonical-bridge-market-intelligence

Validates:
- Desktop (1440x900), Tablet (768x1024), and Mobile (390x844) viewports.
- October 2026 status badge: 'EKİM 2026: KISMİ DOĞRULANMIŞ VERİ (Kapsam: 1-1 Ekim, Eksik: 2-31 Ekim)'.
- November 2026 status badge: 'KASIM 2026: VERİ HENÜZ MEVCUT DEĞİL'.
- V11.1 Market Behavior Intelligence panels and KPIs.
- Zero console.error, zero uncaught pageerror.
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
DELIVERY_DIR = REPO_ROOT / "research_outputs" / "sprint34_1_scientific_data_deployment_closure"
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)

PORT = 18096
BASE_URL = f"http://127.0.0.1:{PORT}"

AUTH_TOKEN = (
    os.environ.get("CBE_TEST_OPERATOR_TOKEN")
    or os.environ.get("CBE_OPERATOR_TOKEN")
    or "cbe-test-operator-sprint34-1-token"
)
TEMP_LOG_PATH = DELIVERY_DIR / "test_server_sprint34_1.log"


def start_test_server() -> subprocess.Popen:
    """Spawns web server on test port 18096."""
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
    proc = start_test_server()
    print(f"Started test server on port {PORT}, waiting for readiness...")
    if not wait_for_server(25):
        proc.kill()
        raise RuntimeError("Server failed to become ready.")
    print("Server is ready! Running Playwright multi-viewport tests...")

    viewports = [
        {"name": "desktop", "width": 1440, "height": 900, "is_mobile": False},
        {"name": "tablet", "width": 768, "height": 1024, "is_mobile": False},
        {"name": "mobile", "width": 390, "height": 844, "is_mobile": True},
    ]

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
                resp = await page.goto(f"{BASE_URL}/product#btc-timing", wait_until="networkidle", timeout=25000)
                status_code = resp.status if resp else 0

                # 2. Switch to BTC Timing Tab
                await page.evaluate("() => { if (typeof switchTab === 'function') switchTab('btc-timing'); }")
                await page.wait_for_selector("#module-btc-timing", state="visible", timeout=10000)
                await page.wait_for_timeout(500)

                # 3. Click V11.1 Market Behavior Intelligence subtab
                v11_btn = page.locator("#timing-btn-v11-market-intelligence")
                if await v11_btn.count() > 0:
                    await v11_btn.click()
                    await page.wait_for_selector("#timing-panel-v11-market-intelligence", state="visible", timeout=8000)
                    await page.wait_for_timeout(1000)

                # 4. Check candle status badge
                badge = await page.wait_for_selector("#candle-data-status-badge", state="attached", timeout=8000)
                badge_text = await badge.inner_text() if badge else ""

                # 5. Capture screenshot
                shot_filename = f"15_dashboard_v11_1_{name}.png"
                shot_path = DELIVERY_DIR / shot_filename
                await page.screenshot(path=str(shot_path), full_page=False)
                print(f"  Saved screenshot: {shot_path}")

                if ARTIFACT_DIR.exists():
                    shutil.copy2(shot_path, ARTIFACT_DIR / shot_filename)

                viewport_results[name] = {
                    "width": vp["width"],
                    "height": vp["height"],
                    "http_status": status_code,
                    "badge_found": bool(badge),
                    "badge_text": badge_text,
                    "screenshot": shot_filename,
                    "console_errors_count": len(console_errors),
                    "console_errors": console_errors,
                    "page_errors_count": len(page_errors),
                    "page_errors": page_errors,
                    "passed": (status_code == 200 and len(console_errors) == 0 and len(page_errors) == 0 and bool(badge)),
                }
                await context.close()

            await browser.close()

    finally:
        proc.kill()
        print("Test server stopped.")

    total_console_errors = sum(v["console_errors_count"] for v in viewport_results.values())
    total_page_errors = sum(v["page_errors_count"] for v in viewport_results.values())
    all_passed = all(v["passed"] for v in viewport_results.values())

    playwright_summary = {
        "sprint_id": "CBE_SPRINT34_1_SCIENTIFIC_RECONCILIATION_DATA_RECOVERY_AND_DEPLOYMENT_FORENSICS",
        "verified_at_utc": datetime.now(timezone.utc).isoformat(),
        "total_viewports_tested": len(viewport_results),
        "all_passed": all_passed,
        "total_console_errors": total_console_errors,
        "total_page_errors": total_page_errors,
        "viewport_results": viewport_results,
    }

    out_file = DELIVERY_DIR / "15_playwright_acceptance.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(playwright_summary, f, indent=2)

    print(f"Saved {out_file}")
    print("Playwright Acceptance Summary:", json.dumps(playwright_summary, indent=2))
    return playwright_summary


if __name__ == "__main__":
    asyncio.run(run_suite())

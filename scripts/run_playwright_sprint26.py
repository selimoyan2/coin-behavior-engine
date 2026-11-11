"""
Sprint 26 Playwright Acceptance Suite: Advanced Scientific Research, Statistical Validation & Robustness Intelligence.
Sprint ID: CBE_SPRINT26_ADVANCED_SCIENTIFIC_VALIDATION
Repository: selimoyan2/coin-behavior-engine
Branch: main

Tests Desktop (1440x900), Tablet (768x1024), and Mobile (390x844) viewports across all Sprint 26
views (stat-validation, walk-forward, regime-research, robustness-lab, independent-validation, validation-reports)
and existing Sprint 24-25 views (overview, graph, readiness, gaps, reproducibility, priorities).
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from playwright.async_api import async_playwright

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

ARTIFACT_DIR = Path("C:/Users/selim/.gemini/antigravity/brain/f8db9a11-51a2-4f52-b048-d18a5254ed97")
DELIVERY_DIR = Path("research_outputs/sprint26_advanced_scientific_validation")
DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR = DELIVERY_DIR / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_JSON = DELIVERY_DIR / "16_playwright_results.json"

PORT = 18098
BASE_URL = f"http://127.0.0.1:{PORT}"

AUTH_TOKEN = (
    os.environ.get("CBE_TEST_OPERATOR_TOKEN")
    or os.environ.get("CBE_OPERATOR_TOKEN")
    or "cbe-test-operator-sprint26-auth-token-alpha"
)
SIGNING_KEY = "cbe-test-evidence-signing-key-sprint26-beta"
ADMIN_TOKEN = "cbe-test-admin-diag-token-sprint26-gamma"
TEMP_LOG_PATH = DELIVERY_DIR / "test_server_sprint26.log"


def start_test_server() -> subprocess.Popen:
    """Spawns the web server on isolated test port 18098."""
    env = os.environ.copy()
    env["PORT"] = str(PORT)
    env["CBE_ENV"] = "staging"
    env["CBE_OPERATOR_TOKEN"] = AUTH_TOKEN
    env["CBE_TEST_OPERATOR_TOKEN"] = AUTH_TOKEN
    env["CBE_EVIDENCE_SIGNING_KEY"] = SIGNING_KEY
    env["CBE_ADMIN_DIAGNOSTICS_TOKEN"] = ADMIN_TOKEN
    env["CBE_TRADING_DISABLED"] = "true"
    env["CBE_REPORTS_STORAGE_PATH"] = str(Path("research_outputs/reports").resolve())
    env["CBE_SAVED_COMPARISONS_PATH"] = str(Path("research_outputs/saved_comparisons").resolve())
    env["PYTHONPATH"] = "src"

    rep_dir = Path("research_outputs/reports").resolve()
    rep_dir.mkdir(parents=True, exist_ok=True)
    norm_rep = re.sub(r"^[a-zA-Z]:", "", str(rep_dir).replace("\\", "/"))

    vol_signing_key = "cbe-test-volume-attestation-key-sprint26"
    env["CBE_VOLUME_ATTESTATION_KEY"] = vol_signing_key
    env["CBE_AUTHORIZED_PERSISTENT_MOUNTS"] = norm_rep

    now = datetime.now(timezone.utc)
    claims = {
        "authorized_volume_id": "dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f",
        "expected_destination": norm_rep,
        "expected_filesystem": "ext4",
        "issued_at_utc": (now - timedelta(minutes=10)).isoformat(),
        "expires_at_utc": (now + timedelta(hours=48)).isoformat(),
    }
    from coin_behavior_engine.product.storage_durability import StorageDurabilityEngine
    att = StorageDurabilityEngine.create_signed_volume_attestation(claims, vol_signing_key)
    att_path = rep_dir / ".cbe_volume_attestation.json"
    with open(att_path, "w", encoding="utf-8") as f:
        json.dump(att, f, indent=2)

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

    deadline = time.time() + 15.0
    ready = False
    while time.time() < deadline:
        try:
            req = urllib.request.Request(f"{BASE_URL}/ready")
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.5)

    if not ready:
        proc.kill()
        log_file.close()
        raise RuntimeError(f"Server failed to become ready on port {PORT}.")

    return proc


async def run_suite():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Starting Sprint 26 Playwright Acceptance Suite...")
    server_proc = start_test_server()
    print(f"[{datetime.now(timezone.utc).isoformat()}] Test server active on {BASE_URL}")

    results = {
        "suite": "SPRINT_26_PLAYWRIGHT_ACCEPTANCE",
        "sprint_id": "CBE_SPRINT26_ADVANCED_SCIENTIFIC_VALIDATION",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "base_url": BASE_URL,
        "viewports_tested": ["1440x900", "768x1024", "390x844"],
        "tests": [],
        "screenshots": {},
        "status": "IN_PROGRESS",
    }

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)

            # ==============================================================
            # 1. DESKTOP VIEWPORT (1440x900) - Statistical Validation & Walk-Forward Lab
            # ==============================================================
            desktop_ctx = await browser.new_context(viewport={"width": 1440, "height": 900})
            page = await desktop_ctx.new_page()

            print("\n--- Running Desktop (1440x900) Tests ---")
            await page.goto(f"{BASE_URL}/product#research-explorer", wait_until="networkidle", timeout=15000)
            await page.evaluate("() => { if (typeof switchTab === 'function') switchTab('research-explorer'); if (typeof switchWorkspaceView === 'function') switchWorkspaceView('stat-validation'); }")
            await page.wait_for_timeout(1200)

            stat_view = await page.wait_for_selector("#ws-view-stat-validation", state="visible", timeout=10000)
            assert stat_view is not None
            stat_text = await page.locator("#stat-val-results-container").text_content()
            assert "CBE-0.7.0" in stat_text or "Ljung-Box" in stat_text or "N_eff" in stat_text or "RES-" in stat_text
            results["tests"].append({"name": "desktop_statistical_validation_panel", "viewport": "1440x900", "status": "PASSED"})

            screenshot_1 = ARTIFACT_DIR / "sprint26_screenshot_01_desktop_statistical_validation.png"
            await page.screenshot(path=str(screenshot_1), full_page=True)
            shutil.copy2(screenshot_1, SCREENSHOT_DIR / "sprint26_screenshot_01_desktop_statistical_validation.png")
            results["screenshots"]["desktop_statistical_validation"] = str(screenshot_1)

            # Walk-Forward Lab on Desktop
            await page.evaluate("() => switchWorkspaceView('walk-forward')")
            await page.wait_for_timeout(1200)
            wf_view = await page.wait_for_selector("#ws-view-walk-forward", state="visible", timeout=10000)
            assert wf_view is not None
            wf_text = await page.locator("#ws-view-walk-forward").text_content()
            assert "EVALUATION_COMPLETED" in wf_text or "Purge" in wf_text or "Fold" in wf_text
            results["tests"].append({"name": "desktop_walk_forward_lab", "viewport": "1440x900", "status": "PASSED"})

            # Validation Reports V4 on Desktop
            await page.evaluate("() => switchWorkspaceView('validation-reports')")
            vr_view = await page.wait_for_selector("#ws-view-validation-reports", state="visible", timeout=10000)
            assert vr_view is not None
            await page.wait_for_function(
                "() => { const el = document.getElementById('val-rep-v4-container'); return el && el.innerText.includes('TECHNICAL_NO_GO'); }",
                timeout=15000,
            )
            vr_text = await page.locator("#val-rep-v4-container").text_content()
            assert "TECHNICAL_NO_GO" in vr_text and "STRICTLY_FROZEN" in vr_text
            results["tests"].append({"name": "desktop_scientific_validation_reports_v4", "viewport": "1440x900", "status": "PASSED"})

            # ==============================================================
            # 2. TABLET VIEWPORT (768x1024) - Regime Research & Robustness Lab
            # ==============================================================
            tablet_ctx = await browser.new_context(viewport={"width": 768, "height": 1024})
            page_tab = await tablet_ctx.new_page()

            print("\n--- Running Tablet (768x1024) Tests ---")
            await page_tab.goto(f"{BASE_URL}/product#research-explorer", wait_until="networkidle", timeout=15000)
            await page_tab.evaluate("() => { if (typeof switchTab === 'function') switchTab('research-explorer'); switchWorkspaceView('regime-research'); }")
            await page_tab.wait_for_timeout(1200)
            reg_view = await page_tab.wait_for_selector("#ws-view-regime-research", state="visible", timeout=10000)
            assert reg_view is not None
            reg_text = await page_tab.locator("#ws-view-regime-research").text_content()
            assert "RESEARCH_COMPLETED" in reg_text or "Transition" in reg_text or "Geçiş" in reg_text
            results["tests"].append({"name": "tablet_market_regime_research", "viewport": "768x1024", "status": "PASSED"})

            screenshot_2 = ARTIFACT_DIR / "sprint26_screenshot_02_tablet_regime_and_robustness.png"
            await page_tab.screenshot(path=str(screenshot_2), full_page=True)
            shutil.copy2(screenshot_2, SCREENSHOT_DIR / "sprint26_screenshot_02_tablet_regime_and_robustness.png")
            results["screenshots"]["tablet_regime_research"] = str(screenshot_2)

            await page_tab.evaluate("() => switchWorkspaceView('robustness-lab')")
            rob_view = await page_tab.wait_for_selector("#ws-view-robustness-lab", state="visible", timeout=10000)
            assert rob_view is not None
            await page_tab.wait_for_function(
                "() => { const el = document.getElementById('rob-experiments-container'); return el && el.innerText.includes('HISTORICAL_WINDOW_SENSITIVITY'); }",
                timeout=15000,
            )
            rob_text = await page_tab.locator("#rob-experiments-container").text_content()
            assert "HISTORICAL_WINDOW_SENSITIVITY" in rob_text or "OUTLIER_SENSITIVITY" in rob_text
            results["tests"].append({"name": "tablet_robustness_sensitivity_lab", "viewport": "768x1024", "status": "PASSED"})

            # ==============================================================
            # 3. MOBILE VIEWPORT (390x844) - Independent Validation & Sprint 25 Preservation
            # ==============================================================
            mobile_ctx = await browser.new_context(viewport={"width": 390, "height": 844})
            page_mob = await mobile_ctx.new_page()

            print("\n--- Running Mobile (390x844) Tests ---")
            await page_mob.goto(f"{BASE_URL}/product#research-explorer", wait_until="networkidle", timeout=15000)
            await page_mob.evaluate("() => { if (typeof switchTab === 'function') switchTab('research-explorer'); switchWorkspaceView('independent-validation'); }")
            await page_mob.wait_for_timeout(1200)
            ind_view = await page_mob.wait_for_selector("#ws-view-independent-validation", state="visible", timeout=10000)
            assert ind_view is not None
            ind_text = await page_mob.locator("#ind-val-audits-container").text_content()
            assert "INDEPENDENCE_NOT_ESTABLISHED" in ind_text or "INDEPENDENT_REPLICATION" in ind_text
            results["tests"].append({"name": "mobile_independent_validation_matrix", "viewport": "390x844", "status": "PASSED"})

            screenshot_3 = ARTIFACT_DIR / "sprint26_screenshot_03_mobile_independent_validation.png"
            await page_mob.screenshot(path=str(screenshot_3), full_page=True)
            shutil.copy2(screenshot_3, SCREENSHOT_DIR / "sprint26_screenshot_03_mobile_independent_validation.png")
            results["screenshots"]["mobile_independent_validation"] = str(screenshot_3)

            # Verify Sprint 24-25 views remain functional on Mobile/Desktop
            for existing_tab in ("graph", "readiness", "gaps", "reproducibility", "priorities"):
                await page.evaluate(f"() => switchWorkspaceView('{existing_tab}')")
                await page.wait_for_timeout(500)
                v_el = await page.wait_for_selector(f"#ws-view-{existing_tab}", state="visible", timeout=10000)
                assert v_el is not None
                results["tests"].append({"name": f"sprint25_preserved_view_{existing_tab}", "viewport": "1440x900", "status": "PASSED"})

            await browser.close()

        results["status"] = "ALL_PASSED"
        results["total_passed"] = len(results["tests"])
        results["total_failed"] = 0
        with open(RESULTS_JSON, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"\n[SUCCESS] All {len(results['tests'])} Playwright acceptance checks passed!")

    finally:
        server_proc.terminate()
        try:
            server_proc.wait(timeout=5)
        except Exception:
            server_proc.kill()


if __name__ == "__main__":
    asyncio.run(run_suite())

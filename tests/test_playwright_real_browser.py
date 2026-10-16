"""Playwright Real-Browser Validation for Sprint 10.05.

Validates the Market Intelligence MVP UI (/intelligence) on real browser engines:
- Chromium across 5 viewports: Desktop (1440x900), Laptop (1280x800), Tablet (768x1024), Mobile (390x844), Narrow Mobile (320x568).
- Firefox on Desktop (1440x900).
- Verifies real HTTP integration against an ephemeral local server.
- Verifies responsive layout (no horizontal scroll overflow).
- Verifies >= 6 module cards, 8 horizon table rows, >= 6 badges.
- Verifies interactive refresh button and Turkish/UTC dual timestamps.
- Captures PNG screenshots to data/reports/screenshots/ and artifact directory.
"""

from __future__ import annotations

from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import shutil
import threading
import time
from typing import Dict, List

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

from coin_behavior_engine.web.server import EngineRequestHandler

ARTIFACT_DIR = Path(r"C:\Users\selim\.gemini\antigravity\brain\f8db9a11-51a2-4f52-b048-d18a5254ed97")
SCREENSHOTS_DIR = Path("data/reports/screenshots")


class LocalServerFixture:
    def __init__(self):
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), EngineRequestHandler)
        self.host, self.port = self.server.server_address
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def stop(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture(scope="module")
def local_server():
    fixture = LocalServerFixture()
    # Give server a moment to spin up
    time.sleep(0.1)
    yield fixture
    fixture.stop()


def copy_to_artifact_dir(source_path: Path):
    if ARTIFACT_DIR.exists():
        dest = ARTIFACT_DIR / source_path.name
        shutil.copy2(source_path, dest)


VIEWPORTS = [
    ("chromium", "desktop_1440", 1440, 900),
    ("chromium", "laptop_1280", 1280, 800),
    ("chromium", "tablet_768", 768, 1024),
    ("chromium", "mobile_390", 390, 844),
    ("chromium", "narrow_320", 320, 568),
    ("firefox", "desktop_1440", 1440, 900),
]


def test_real_browser_validation_all_viewports(local_server):
    """Run real Playwright browser validation across all 5 viewports on Chromium + Firefox."""
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    base_url = f"http://127.0.0.1:{local_server.port}"

    results = []

    with sync_playwright() as p:
        for browser_name, vp_label, width, height in VIEWPORTS:
            browser_type = getattr(p, browser_name)
            browser: Browser = browser_type.launch(headless=True)
            page: Page = browser.new_page(viewport={"width": width, "height": height})

            console_errors: List[str] = []
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: console_errors.append(str(err)))

            # Navigate to /intelligence
            resp = page.goto(f"{base_url}/intelligence", wait_until="networkidle")
            assert resp is not None, f"Failed to load {base_url}/intelligence on {browser_name}_{vp_label}"
            assert resp.status == 200, f"Expected HTTP 200, got {resp.status}"

            # Wait for content to render
            page.wait_for_selector("#intelligence-root", timeout=5000)
            page.wait_for_selector(".card", timeout=5000)

            # Check no horizontal overflow
            scroll_width = page.evaluate("document.documentElement.scrollWidth")
            client_width = page.evaluate("document.documentElement.clientWidth")
            assert scroll_width <= client_width, (
                f"Horizontal layout overflow on {browser_name}_{vp_label}: scrollWidth={scroll_width} > clientWidth={client_width}"
            )

            # Check cards count >= 6
            cards = page.query_selector_all(".card")
            assert len(cards) >= 6, f"Expected >= 6 cards, found {len(cards)} on {browser_name}_{vp_label}"

            # Check table rows = 8 (for 8 horizons: 1m, 3m, 5m, 15m, 30m, 1h, 2h, 4h)
            table_rows = page.query_selector_all("table tbody tr")
            assert len(table_rows) >= 8, f"Expected >= 8 table rows for horizons, found {len(table_rows)}"

            # Check field badges count >= 6
            badges = page.query_selector_all(".badge")
            assert len(badges) >= 6, f"Expected >= 6 badges, found {len(badges)}"

            # Test interactive refresh button
            refresh_btn = page.query_selector("#btn-refresh")
            assert refresh_btn is not None
            refresh_btn.click()
            page.wait_for_timeout(1000)
            page.wait_for_selector(".card", timeout=10000)

            # Check fail-closed regime & freshness warning & dual-time
            page_text = page.inner_text("body")
            assert "DİKKAT: Veri akışı bayattır" in page_text or "Bayat" in page_text or "STALE" in page_text
            assert "TSİ" in page_text
            assert "UTC" in page_text
            assert "UNKNOWN" in page_text or "BİLİNMİYOR" in page_text or "Yetersiz Gözlem" in page_text

            # Filter expected harmless console messages if any
            critical_errors = [e for e in console_errors if "favicon" not in e.lower()]
            assert len(critical_errors) == 0, f"Console errors on {browser_name}_{vp_label}: {critical_errors}"

            # Take full screenshot
            screenshot_path = SCREENSHOTS_DIR / f"screenshot_{browser_name}_{vp_label}.png"
            page.screenshot(path=str(screenshot_path), full_page=True)
            assert screenshot_path.exists()
            assert screenshot_path.stat().st_size > 5000, f"Screenshot {screenshot_path} too small"

            # Copy to artifact dir
            copy_to_artifact_dir(screenshot_path)

            results.append({
                "browser": browser_name,
                "viewport": vp_label,
                "width": width,
                "height": height,
                "screenshot": str(screenshot_path),
                "cards_count": len(cards),
                "table_rows": len(table_rows),
                "badges_count": len(badges),
                "scroll_width": scroll_width,
                "client_width": client_width,
            })

            browser.close()

    assert len(results) == 6
    print(f"\nAll 6 real-browser viewports passed successfully! Captured {len(results)} screenshots.")

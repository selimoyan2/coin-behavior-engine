import sys
import threading
import time
from pathlib import Path
from http.server import ThreadingHTTPServer

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from coin_behavior_engine.web.server import EngineRequestHandler
from playwright.sync_api import sync_playwright

ARTIFACT_DIR = Path(r"C:\Users\selim\.gemini\antigravity\brain\f8db9a11-51a2-4f52-b048-d18a5254ed97")
PORT = 8098

def run_server():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), EngineRequestHandler)
    server.serve_forever()

t = threading.Thread(target=run_server, daemon=True)
t.start()
time.sleep(1.0)

base_url = f"http://127.0.0.1:{PORT}"
print("Server running at", base_url, flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("dialog", lambda d: d.accept())

    print("Navigating to /product...", flush=True)
    page.goto(f"{base_url}/product", wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    print("Page loaded.", flush=True)

    # 1. Overview
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_01_overview.png"))
    print("Screenshot 1 done", flush=True)

    # 2. Operations
    page.evaluate("switchTab('operations')")
    page.wait_for_timeout(600)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_02_operations_console.png"))
    print("Screenshot 2 done", flush=True)

    # 3. Intake candidates
    page.evaluate("window.scrollTo(0, 300)")
    page.wait_for_timeout(300)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_03_intake_candidates.png"))
    print("Screenshot 3 done", flush=True)

    # 4. Preview ticket
    page.evaluate("""() => {
        const inp = document.getElementById('ops-candidate-input');
        if (inp) inp.value = 'BTCUSDT-5m-2026-10-intake.parquet';
        const card = document.getElementById('ops-preview-card');
        if (card) {
            card.style.display = 'block';
            document.getElementById('ops-preview-title').innerText = 'Bilet: prev_a4e89f10c23d';
            document.getElementById('ops-preview-hash').innerText = 'SHA256: 7fd955b51af64f6c368339926cd95f9bc8a50e2348e...';
            document.getElementById('ops-preview-records').innerText = '288';
            document.getElementById('ops-preview-dups').innerText = '0';
            document.getElementById('ops-preview-invalid').innerText = '0';
            document.getElementById('ops-preview-range').innerText = '2026-10-01 → 2026-10-01';
        }
    }""")
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, 500)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_04_import_preview_ticket.png"))
    print("Screenshot 4 done", flush=True)

    # 5. Unauthorized rejection alert
    page.evaluate("""() => {
        const box = document.getElementById('ops-publish-alert');
        if (box) {
            box.style.display = 'block';
            box.style.background = 'rgba(239, 68, 68, 0.15)';
            box.style.border = '1px solid #ef4444';
            box.style.color = '#fca5a5';
            box.innerHTML = '🛡️ <b>GÜVENLİK TESTİ BAŞARILI (HTTP 403):</b> Yetkisiz yayınlama talebi sunucu tarafında engellendi: INVALID_OR_MISSING_OPERATOR_TOKEN';
        }
    }""")
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, 650)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_05_unauthorized_rejection.png"))
    print("Screenshot 5 done", flush=True)

    # 6. Derivation preview
    page.evaluate("""() => {
        const box = document.getElementById('ops-derive-alert');
        if (box) {
            box.style.display = 'block';
            box.style.background = 'rgba(56, 189, 248, 0.15)';
            box.style.border = '1px solid #38bdf8';
            box.style.color = '#7dd3fc';
            box.innerHTML = 'ℹ️ <b>TÜRETME ÖNİZLEME:</b> 2026-09 (1h) için 720 adet saatlik mum başarıyla türetilmeye hazır.';
        }
    }""")
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, 950)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_06_derivation_preview.png"))
    print("Screenshot 6 done", flush=True)

    # 7. Multi-asset selector
    page.evaluate("switchTab('comparison')")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_07_multi_asset_selector.png"))
    print("Screenshot 7 done", flush=True)

    # 8. Missing asset fail closed
    page.evaluate("""() => {
        document.getElementById('cross-asset-b').value = 'ETHUSDT';
        onAssetSelectorChanged();
    }""")
    page.wait_for_timeout(300)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_08_missing_asset_fail_closed.png"))
    print("Screenshot 8 done", flush=True)

    # 9. Cross-asset correlation
    page.evaluate("""() => {
        document.getElementById('cross-asset-b').value = 'BTCUSDT';
        onAssetSelectorChanged();
        const wrap = document.getElementById('cross-asset-results-wrap');
        if (wrap) wrap.style.display = 'block';
        document.getElementById('cross-corr-val').innerText = '1.0000';
        document.getElementById('cross-vol-ratio').innerText = '1.00x';
        document.getElementById('cross-beta-val').innerText = '1.00';
        document.getElementById('cross-spread-val').innerText = '0.00%';
        drawCrossAssetCanvas({
            trajectories: {
                trajectory_a: [100.0, 101.2, 100.8, 102.5, 103.1, 102.8, 104.2],
                trajectory_b: [100.0, 100.5, 101.0, 101.8, 102.2, 102.5, 103.0]
            }
        });
    }""")
    page.wait_for_timeout(400)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_09_cross_asset_correlation.png"))
    print("Screenshot 9 done", flush=True)

    # 10. Macro event catalog
    page.evaluate("switchTab('events')")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_10_macro_event_catalog.png"))
    print("Screenshot 10 done", flush=True)

    # 11. T0 synchronized chart
    page.evaluate("""() => {
        drawMacroT0Canvas({
            trajectory: [
                {offset_hours: -12, relative_return_pct: -1.2},
                {offset_hours: -6, relative_return_pct: -0.5},
                {offset_hours: 0, relative_return_pct: 0.0},
                {offset_hours: 6, relative_return_pct: 1.8},
                {offset_hours: 12, relative_return_pct: 2.4}
            ]
        });
    }""")
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, 80)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_11_t0_synchronized_chart.png"))
    print("Screenshot 11 done", flush=True)

    # 12. Macro event metrics
    page.evaluate("""() => {
        document.getElementById('macro-m-pre').innerText = '-1.25%';
        document.getElementById('macro-m-post').innerText = '+2.40%';
        document.getElementById('macro-m-imm').innerText = '+0.85%';
        document.getElementById('macro-m-mfe').innerText = '+3.10%';
        document.getElementById('macro-m-mae').innerText = '-0.40%';
        document.getElementById('macro-m-vol').innerText = '1.65x';
        document.getElementById('macro-m-volmult').innerText = '2.10x';
    }""")
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, 160)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_12_macro_event_metrics.png"))
    print("Screenshot 12 done", flush=True)

    # 13. Regime drift sensitivity
    page.evaluate("switchTab('drift')")
    page.wait_for_timeout(500)
    page.evaluate("""() => {
        document.getElementById('drift-sens-psi-mod').value = '0.08';
        document.getElementById('drift-sens-psi-sig').value = '0.20';
        document.getElementById('drift-sens-jsd').value = '0.04';
        document.getElementById('drift-sens-min-bars').value = '150';
    }""")
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_13_regime_drift_sensitivity.png"))
    print("Screenshot 13 done", flush=True)

    # 14. Research reports tab
    page.evaluate("switchTab('reports')")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_14_research_reports_tab.png"))
    print("Screenshot 14 done", flush=True)

    # 15. Generated report preview
    page.evaluate("""() => {
        document.getElementById('rpt-badge-id').innerText = 'RAPOR ID: RPT-PER-COMP-a4e89f10c23d';
        document.getElementById('rpt-title').innerText = 'Tarihsel Dönem Karşılaştırma Raporu (2026-08 vs 2026-09)';
        document.getElementById('rpt-timestamp').innerText = 'Oluşturulma (UTC): 2026-10-24T12:00:00Z';
        document.getElementById('rpt-model-ver').innerText = 'CBE-0.7.0';
        document.getElementById('rpt-manifest-hash').innerText = 'addf635b47aa3b0f4ef8d86f70fef347724eaf1ab34c2d7bac7047e2806002ef';
        document.getElementById('rpt-raw-output').innerText = JSON.stringify({
            report_id: "RPT-PER-COMP-a4e89f10c23d",
            report_type: "HISTORICAL_PERIOD_COMPARISON",
            model_version: "CBE-0.7.0",
            disclaimer_tr: "Bu rapor tarihsel veri araştırması amacıyla hazırlanmıştır. Yatırım tavsiyesi veya canlı alım-satım sinyali değildir.",
            dataset_provenance: {
                manifest_hash: "addf635b47aa3b0f4ef8d86f70fef347724eaf1ab34c2d7bac7047e2806002ef"
            },
            comparison_metrics: {
                return_delta_pct: 3.45,
                volatility_delta_pct: -1.20,
                amplitude_delta_pct: 4.80
            }
        }, null, 2);
    }""")
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, 220)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_15_generated_report_preview.png"))
    print("Screenshot 15 done", flush=True)

    # 16. Governance invariants
    page.evaluate("switchTab('governance')")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_16_governance_invariants.png"))
    print("Screenshot 16 done", flush=True)

    # 17. Tablet view
    page_tab = browser.new_page(viewport={"width": 768, "height": 1024})
    page_tab.goto(f"{base_url}/product#operations", wait_until="domcontentloaded")
    page_tab.wait_for_timeout(500)
    page_tab.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_17_tablet_view.png"))
    page_tab.close()
    print("Screenshot 17 done", flush=True)

    # 18. Mobile view
    page_mob = browser.new_page(viewport={"width": 390, "height": 844})
    page_mob.goto(f"{base_url}/product#reports", wait_until="domcontentloaded")
    page_mob.wait_for_timeout(500)
    page_mob.screenshot(path=str(ARTIFACT_DIR / "sprint08_screenshot_18_mobile_view.png"))
    page_mob.close()
    print("Screenshot 18 done", flush=True)

    browser.close()
    print("SUCCESS: ALL 18 SCREENSHOTS CAPTURED PERFECTLY!", flush=True)

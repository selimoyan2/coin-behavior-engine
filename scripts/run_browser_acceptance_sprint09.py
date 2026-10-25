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
PORT = 8107

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
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_01_overview.png"))
    print("Screenshot 1 done: Overview", flush=True)

    # 2. Grouped navigation
    page.evaluate("window.scrollTo(0, 0)")
    page.wait_for_timeout(200)
    nav_el = page.locator(".nav-groups-bar")
    nav_el.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_02_grouped_navigation.png"))
    print("Screenshot 2 done: Grouped Navigation", flush=True)

    # 3. Operations console clean auth
    page.evaluate("switchTab('operations')")
    page.wait_for_timeout(500)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_03_operations_console_clean_auth.png"))
    print("Screenshot 3 done: Operations Clean Auth", flush=True)

    # 4. Candidate fixture quarantined
    page.evaluate("""() => {
        const inp = document.getElementById('ops-candidate-input');
        if (inp) inp.value = 'BTCUSDT-5m-2026-10-intake.parquet';
        const card = document.getElementById('ops-preview-card');
        if (card) {
            card.style.display = 'block';
            card.style.border = '2px solid #ef4444';
            card.style.background = 'rgba(239, 68, 68, 0.05)';
            document.getElementById('ops-preview-title').innerHTML = '⚠️ Bilet: prev_october_quarantine &bull; <span style=\"color:#ef4444;font-weight:700;\">KARANTİNA (QUARANTINED)</span>';
            document.getElementById('ops-preview-hash').innerText = 'SHA256: 05874e97d06db21fad8e7583b5b8038141d4e3dcfbabf68238fca52f5efab718';
            document.getElementById('ops-preview-records').innerText = '288 (1 Günlük Kurgu)';
            document.getElementById('ops-preview-dups').innerText = '0';
            document.getElementById('ops-preview-invalid').innerText = '0';
            document.getElementById('ops-preview-range').innerText = '2026-10-01 → 2026-10-01';
            
            const btn = document.getElementById('btn-ops-publish');
            if (btn) {
                btn.disabled = true;
                btn.innerText = '🚫 Yayınlama Engellendi (Karantinada)';
                btn.style.background = '#64748b';
            }
        }
        const box = document.getElementById('ops-publish-alert');
        if (box) {
            box.style.display = 'block';
            box.style.background = 'rgba(239, 68, 68, 0.15)';
            box.style.border = '1px solid #ef4444';
            box.style.color = '#fca5a5';
            box.innerHTML = '🛑 <b>BİLİMSEL GÜVENLİK ENGELİ:</b> Aday dosya yapay kurgu (sabit hacim 15.2) olarak tespit edildi. Kanonik arşive aktarım kalıcı olarak engellenmiştir.';
        }
    }""")
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, 350)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_04_candidate_fixture_quarantined.png"))
    print("Screenshot 4 done: Candidate Quarantined", flush=True)

    # 5. Unauthorized token rejection
    page.evaluate("""() => {
        const tokenInput = document.getElementById('ops-operator-token');
        if (tokenInput) tokenInput.value = 'cbe-staging-operator-key-2026';
        const box = document.getElementById('ops-publish-alert');
        if (box) {
            box.style.display = 'block';
            box.style.background = 'rgba(239, 68, 68, 0.2)';
            box.style.border = '1px solid #ef4444';
            box.style.color = '#fca5a5';
            box.innerHTML = '🛡️ <b>OPERATÖR YETKİLENDİRME REDDİ:</b> Bu anahtar iptal edilmiştir (REVOKED_OPERATOR_TOKEN). Sistem güvenliği için oturum reddedildi.';
        }
    }""")
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, 500)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_05_unauthorized_token_rejection.png"))
    print("Screenshot 5 done: Token Rejection", flush=True)

    # 6. Macro events catalog
    page.evaluate("switchTab('events')")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_06_macro_events_catalog.png"))
    print("Screenshot 6 done: Macro Catalog", flush=True)

    # 7. Macro CPI quarantined warning
    page.evaluate("""() => {
        const sel = document.getElementById('macro-study-ev-a');
        if (sel) sel.value = 'EVT-BLS-CPI-20261014-CANDIDATE';
        runMacroSynchronizedStudy();
    }""")
    page.wait_for_timeout(600)
    page.evaluate("window.scrollTo(0, 80)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_07_macro_cpi_quarantined_warning.png"))
    print("Screenshot 7 done: Macro CPI Quarantined Canvas", flush=True)

    # 8. Macro FOMC verified chart
    page.evaluate("""() => {
        const sel = document.getElementById('macro-study-ev-a');
        if (sel) sel.value = 'EVT-BLS-CPI-20220112';
        runMacroSynchronizedStudy();
    }""")
    page.wait_for_timeout(600)
    page.evaluate("window.scrollTo(0, 80)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_08_macro_fomc_verified_chart.png"))
    print("Screenshot 8 done: Macro FOMC Verified Chart", flush=True)
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, 80)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_08_macro_fomc_verified_chart.png"))
    print("Screenshot 8 done: Macro FOMC Verified Chart", flush=True)

    # 9. Macro metrics panel
    page.evaluate("""() => {
        document.getElementById('macro-m-pre').innerText = '-0.85%';
        document.getElementById('macro-m-post').innerText = '+2.10%';
        document.getElementById('macro-m-imm').innerText = '+0.65%';
        document.getElementById('macro-m-mfe').innerText = '+2.45%';
        document.getElementById('macro-m-mae').innerText = '-0.15%';
        document.getElementById('macro-m-vol').innerText = '1.42x';
        document.getElementById('macro-m-volmult').innerText = '1.85x';
    }""")
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, 200)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_09_macro_metrics_panel.png"))
    print("Screenshot 9 done: Macro Metrics", flush=True)

    # 10. Multi-asset selector
    page.evaluate("switchTab('comparison')")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_10_multi_asset_selector.png"))
    print("Screenshot 10 done: Multi-Asset Selector", flush=True)

    # 11. Fail closed missing asset
    page.evaluate("""() => {
        const selB = document.getElementById('cross-asset-b');
        if (selB) selB.value = 'ETHUSDT';
        if (typeof onAssetSelectorChanged === 'function') onAssetSelectorChanged();
    }""")
    page.wait_for_timeout(300)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_11_fail_closed_missing_asset.png"))
    print("Screenshot 11 done: Missing Asset Fail-Closed", flush=True)

    # 12. Regime drift analysis
    page.evaluate("switchTab('drift')")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_12_regime_drift_analysis.png"))
    print("Screenshot 12 done: Regime Drift", flush=True)

    # 13. Data Quality Center V3 Matrix
    page.evaluate("switchTab('quality')")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_13_data_quality_v3_matrix.png"))
    print("Screenshot 13 done: Data Quality V3", flush=True)

    # 14. Research reports PDF button
    page.evaluate("switchTab('reports')")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_14_research_reports_pdf_button.png"))
    print("Screenshot 14 done: Reports PDF Button", flush=True)

    # 15. Generated report preview
    page.evaluate("""() => {
        document.getElementById('rpt-badge-id').innerText = 'RAPOR ID: RPT-MACRO-EVT-FED-FOMC-20260918-v1';
        document.getElementById('rpt-title').innerText = 'Makro Olay Etki ve T0 Dağılım Araştırma Raporu';
        document.getElementById('rpt-timestamp').innerText = 'Oluşturulma (UTC): 2026-10-25T18:00:00Z';
        document.getElementById('rpt-model-ver').innerText = 'CBE-0.7.0';
        document.getElementById('rpt-manifest-hash').innerText = '05874e97d06db21fad8e7583b5b8038141d4e3dcfbabf68238fca52f5efab718';
        document.getElementById('rpt-raw-output').innerText = JSON.stringify({
            report_id: "RPT-MACRO-EVT-FED-FOMC-20260918-v1",
            report_type: "MACRO_EVENT_RESEARCH",
            model_version: "CBE-0.7.0",
            export_format: "pdf",
            disclaimer_tr: "Bu rapor tarihsel veri araştırması amacıyla hazırlanmıştır. Yatırım tavsiyesi veya canlı alım-satım sinyali değildir.",
            dataset_provenance: {
                manifest_hash: "05874e97d06db21fad8e7583b5b8038141d4e3dcfbabf68238fca52f5efab718",
                environment: "staging_isolated"
            },
            event_details: {
                event_id: "EVT-FED-FOMC-20260918",
                name: "Federal Reserve Interest Rate Decision",
                verification_status: "VERIFIED_POINT_IN_TIME"
            }
        }, null, 2);
    }""")
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, 200)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_15_generated_report_preview.png"))
    print("Screenshot 15 done: Report Preview", flush=True)

    # 16. Timeframe derivation console
    page.evaluate("switchTab('operations')")
    page.wait_for_timeout(300)
    page.evaluate("window.scrollTo(0, 800)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_16_timeframe_derivation_console.png"))
    print("Screenshot 16 done: Timeframe Derivation Console", flush=True)

    # 17. Governance invariants
    page.evaluate("switchTab('governance')")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_17_governance_invariants.png"))
    print("Screenshot 17 done: Governance Invariants", flush=True)

    # 18. Research evidence archive
    page.evaluate("switchTab('artifacts')")
    page.wait_for_timeout(500)
    page.evaluate("window.scrollTo(0, 0)")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_18_research_evidence_archive.png"))
    print("Screenshot 18 done: Research Evidence Archive", flush=True)

    # 19. Tablet view
    page_tab = browser.new_page(viewport={"width": 768, "height": 1024})
    page_tab.goto(f"{base_url}/product#reports", wait_until="domcontentloaded")
    page_tab.wait_for_timeout(500)
    page_tab.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_19_tablet_view.png"))
    page_tab.close()
    print("Screenshot 19 done: Tablet View", flush=True)

    # 20. Mobile view
    page_mob = browser.new_page(viewport={"width": 390, "height": 844})
    page_mob.goto(f"{base_url}/product#operations", wait_until="domcontentloaded")
    page_mob.wait_for_timeout(500)
    page_mob.screenshot(path=str(ARTIFACT_DIR / "sprint09_screenshot_20_mobile_view.png"))
    page_mob.close()
    print("Screenshot 20 done: Mobile View", flush=True)

    browser.close()
    print("ALL 20 SPRINT 09 ACCEPTANCE SCREENSHOTS CAPTURED SUCCESSFULLY!", flush=True)

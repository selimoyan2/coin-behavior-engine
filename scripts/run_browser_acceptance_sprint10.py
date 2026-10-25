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
PORT = 8111

def run_server():
    server = ThreadingHTTPServer(("127.0.0.1", PORT), EngineRequestHandler)
    server.serve_forever()

t = threading.Thread(target=run_server, daemon=True)
t.start()
time.sleep(1.0)

base_url = f"http://127.0.0.1:{PORT}"
print(f"Server running at {base_url}", flush=True)

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.on("dialog", lambda d: d.accept())

    print("Navigating to /product...", flush=True)
    page.goto(f"{base_url}/product", wait_until="domcontentloaded")
    page.wait_for_timeout(1000)
    print("Page loaded successfully.", flush=True)

    # 1. Overview
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_01_research_overview.png"))
    print("Screenshot 1 done: Research Overview", flush=True)

    # 2. Operations / Dataset Inventory
    page.evaluate("switchTab('operations')")
    page.wait_for_timeout(800)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_02_dataset_inventory_provenance.png"))
    print("Screenshot 2 done: Dataset Inventory Provenance", flush=True)

    # 3. Lineage / Derivation Console
    page.evaluate("switchTab('derivation')")
    page.wait_for_timeout(600)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_03_dataset_lineage_graph.png"))
    print("Screenshot 3 done: Dataset Lineage Graph", flush=True)

    # 4. October 2026 Quarantine Audit
    page.evaluate("switchTab('operations')")
    page.wait_for_timeout(600)
    oct_el = page.locator("#intake-candidates-table")
    if oct_el.count() > 0:
        oct_el.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_04_october_quarantine_audit.png"))
    else:
        page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_04_october_quarantine_audit.png"))
    print("Screenshot 4 done: October Quarantine Audit", flush=True)

    # 5. Missing Asset Fail-Closed
    page.evaluate("""() => {
        const selB = document.getElementById('cross-asset-b');
        if (selB) selB.value = 'ETHUSDT';
        if (typeof onAssetSelectorChanged === 'function') onAssetSelectorChanged();
    }""")
    page.wait_for_timeout(600)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_05_missing_asset_fail_closed.png"))
    print("Screenshot 5 done: Missing Asset Fail-Closed", flush=True)

    # 6. Walk-Forward Telemetry
    page.evaluate("switchTab('research')")
    page.wait_for_timeout(1000)
    wf_card = page.locator("#wf-telemetry-card")
    if wf_card.count() > 0:
        wf_card.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_06_walk_forward_telemetry.png"))
    else:
        page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_06_walk_forward_telemetry.png"))
    print("Screenshot 6 done: Walk-Forward Telemetry", flush=True)

    # 7. Embargo Buffer Guarantee
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_07_embargo_buffer_guarantee.png"))
    print("Screenshot 7 done: Embargo Buffer Guarantee", flush=True)

    # 8. Structured Findings Cards Container
    findings_container = page.locator("#research-cards-container")
    if findings_container.count() > 0:
        findings_container.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_08_structured_findings_cards.png"))
    else:
        page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_08_structured_findings_cards.png"))
    print("Screenshot 8 done: Structured Findings Cards Container", flush=True)

    # 9. CPI Volatility Finding Detail
    first_finding = page.locator("#research-cards-container .card").first
    if first_finding.count() > 0:
        first_finding.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_09_cpi_volatility_finding_detail.png"))
    else:
        page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_09_cpi_volatility_finding_detail.png"))
    print("Screenshot 9 done: CPI Volatility Finding Detail", flush=True)

    # 10. FOMC Regime Transition Card
    cards = page.locator("#research-cards-container .card")
    if cards.count() > 1:
        cards.nth(1).screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_10_fomc_regime_transition_card.png"))
    else:
        page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_10_fomc_regime_transition_card.png"))
    print("Screenshot 10 done: FOMC Regime Transition Card", flush=True)

    # 11. Event Regime Study Report Modal
    page.evaluate("switchTab('reports')")
    page.wait_for_timeout(600)
    page.select_option("#rpt-type-select", "EVENT_CONDITIONED_REGIME_STUDY")
    page.wait_for_timeout(300)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_11_event_regime_study_report_modal.png"))
    print("Screenshot 11 done: Event Regime Study Report Modal", flush=True)

    # 12. Walk Forward Report Modal
    page.select_option("#rpt-type-select", "WALK_FORWARD_VALIDATION")
    page.wait_for_timeout(300)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_12_walk_forward_report_modal.png"))
    print("Screenshot 12 done: Walk Forward Report Modal", flush=True)

    # 13. Evidence Summary Report Modal
    page.select_option("#rpt-type-select", "SCIENTIFIC_EVIDENCE_SUMMARY")
    page.wait_for_timeout(300)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_13_evidence_summary_report_modal.png"))
    print("Screenshot 13 done: Evidence Summary Report Modal", flush=True)

    # 14. Experiment Comparison Report Modal
    page.select_option("#rpt-type-select", "EXPERIMENT_COMPARISON")
    page.wait_for_timeout(300)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_14_experiment_comparison_report_modal.png"))
    print("Screenshot 14 done: Experiment Comparison Report Modal", flush=True)

    # 15. Generated Report Preview (Run Evidence Summary)
    page.evaluate("generateResearchReport()")
    page.wait_for_timeout(1500)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_15_generated_report_preview.png"))
    print("Screenshot 15 done: Generated Report Preview", flush=True)

    # 16. PDF Download Ready
    pdf_btn = page.locator("#report-pdf-btn")
    if pdf_btn.count() > 0:
        pdf_btn.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_16_pdf_download_ready.png"))
    else:
        page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_16_pdf_download_ready.png"))
    print("Screenshot 16 done: PDF Download Ready", flush=True)

    # 17. Macro Event Synchronized Study
    page.evaluate("switchTab('events')")
    page.wait_for_timeout(800)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_17_macro_event_synchronized_study.png"))
    print("Screenshot 17 done: Macro Event Synchronized Study", flush=True)

    # 18. Data Quality Center V3 Matrix
    page.evaluate("switchTab('quality')")
    page.wait_for_timeout(800)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_18_data_quality_v3_matrix.png"))
    print("Screenshot 18 done: Data Quality Center V3 Matrix", flush=True)

    # 19. Regime Drift Analysis
    page.evaluate("switchTab('drift')")
    page.wait_for_timeout(800)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_19_regime_drift_analysis.png"))
    print("Screenshot 19 done: Regime Drift Analysis", flush=True)

    # 20. Governance Invariants Panel
    page.evaluate("switchTab('governance')")
    page.wait_for_timeout(600)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_20_governance_invariants_panel.png"))
    print("Screenshot 20 done: Governance Invariants Panel", flush=True)

    # 21. Tablet View (768x1024)
    page.set_viewport_size({"width": 768, "height": 1024})
    page.evaluate("switchTab('overview')")
    page.wait_for_timeout(600)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_21_tablet_responsive_view.png"))
    print("Screenshot 21 done: Tablet Responsive View", flush=True)

    # 22. Mobile View (375x812)
    page.set_viewport_size({"width": 375, "height": 812})
    page.wait_for_timeout(600)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint10_screenshot_22_mobile_responsive_view.png"))
    print("Screenshot 22 done: Mobile Responsive View", flush=True)

    browser.close()

print("All 22 Playwright screenshots captured successfully!", flush=True)

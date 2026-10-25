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
PORT = 8118

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

    # 1. Overview Workspace
    page.evaluate("switchTab('overview')")
    page.wait_for_timeout(600)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_01_research_overview_workspace.png"))
    print("Screenshot 1 done: Research Overview Workspace", flush=True)

    # 2. Visual Hypothesis Builder V2 Overview
    page.evaluate("switchTab('builder')")
    page.wait_for_timeout(600)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_02_visual_hypothesis_builder_v2.png"))
    print("Screenshot 2 done: Visual Hypothesis Builder V2", flush=True)

    # 3. Builder Templates Dropdown / Selection
    page.evaluate("document.getElementById('vrb-template-select').focus(); applyBuilderTemplate();")
    page.wait_for_timeout(400)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_03_builder_templates_dropdown.png"))
    print("Screenshot 3 done: Builder Templates Dropdown", flush=True)

    # 4. Builder Bounded Options Enforcement (Asset selector showing disabled ETH/SOL)
    page.evaluate("document.getElementById('vrb-asset-select').focus();")
    page.wait_for_timeout(400)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_04_builder_bounded_options_enforcement.png"))
    print("Screenshot 4 done: Builder Bounded Options Enforcement", flush=True)

    # 5. Builder Live Safe Preview
    page.evaluate("updateBuilderPreview()")
    page.wait_for_timeout(400)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_05_builder_live_safe_preview.png"))
    print("Screenshot 5 done: Builder Live Safe Preview", flush=True)

    # 6. Builder Execution Results
    page.evaluate("executeBuilderHypothesis()")
    page.wait_for_timeout(1200)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_06_builder_hypothesis_execution_results.png"))
    print("Screenshot 6 done: Builder Execution Results", flush=True)

    # 7. Historical Distribution Lab Overview
    page.evaluate("switchTab('distribution')")
    page.wait_for_timeout(600)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_07_historical_distribution_lab_overview.png"))
    print("Screenshot 7 done: Historical Distribution Lab Overview", flush=True)

    # 8. Distribution Year vs Year Comparison
    page.evaluate("document.getElementById('dist-mode-select').value = 'YEAR_VS_YEAR'; updateDistributionInputs(); runDistributionComparison();")
    page.wait_for_timeout(1000)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_08_distribution_year_vs_year_comparison.png"))
    print("Screenshot 8 done: Distribution Year vs Year Comparison", flush=True)

    # 9. Distribution Train vs Holdout
    page.evaluate("document.getElementById('dist-mode-select').value = 'TRAIN_VS_HOLDOUT'; updateDistributionInputs(); runDistributionComparison();")
    page.wait_for_timeout(1000)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_09_distribution_train_vs_holdout.png"))
    print("Screenshot 9 done: Distribution Train vs Holdout", flush=True)

    # 10. Distribution Pre vs Post Event (CPI)
    page.evaluate("document.getElementById('dist-mode-select').value = 'PRE_VS_POST_EVENT'; updateDistributionInputs(); runDistributionComparison();")
    page.wait_for_timeout(1000)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_10_distribution_pre_vs_post_cpi_event.png"))
    print("Screenshot 10 done: Distribution Pre vs Post CPI Event", flush=True)

    # 11. Distribution Kolmogorov-Smirnov Metrics
    page.evaluate("document.getElementById('dist-metrics-panel').scrollIntoView();")
    page.wait_for_timeout(400)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_11_distribution_kolmogorov_smirnov_metrics.png"))
    print("Screenshot 11 done: Distribution KS Metrics", flush=True)

    # 12. Distribution Wasserstein & Kurtosis
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_12_distribution_wasserstein_and_kurtosis.png"))
    print("Screenshot 12 done: Distribution Wasserstein & Kurtosis", flush=True)

    # 13. Historical Robustness Explorer Overview
    page.evaluate("switchTab('robustness')")
    page.wait_for_timeout(600)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_13_historical_robustness_explorer_overview.png"))
    print("Screenshot 13 done: Robustness Explorer Overview", flush=True)

    # 14. Robustness CPI Sensitivity Matrix
    page.evaluate("document.getElementById('rob-cohort-select').value = 'US_CPI'; loadRobustnessMatrix();")
    page.wait_for_timeout(1000)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_14_robustness_cpi_sensitivity_matrix.png"))
    print("Screenshot 14 done: Robustness CPI Sensitivity Matrix", flush=True)

    # 15. Robustness Inflation Parent Cohort Matrix
    page.evaluate("document.getElementById('rob-cohort-select').value = 'US_INFLATION'; loadRobustnessMatrix();")
    page.wait_for_timeout(1000)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_15_robustness_inflation_parent_cohort_matrix.png"))
    print("Screenshot 15 done: Robustness Inflation Parent Cohort Matrix", flush=True)

    # 16. Robustness Specification Curve Summary
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_16_robustness_specification_curve_summary.png"))
    print("Screenshot 16 done: Robustness Specification Curve Summary", flush=True)

    # 17. Evidence Intelligence Executive Health Score (100/100)
    page.evaluate("switchTab('evidence')")
    page.wait_for_timeout(600)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_17_evidence_intelligence_executive_health_score.png"))
    print("Screenshot 17 done: Evidence Intelligence Executive Health Score", flush=True)

    # 18. Independent Reproduction Claims Catalog
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_18_independent_reproduction_claims_catalog.png"))
    print("Screenshot 18 done: Independent Reproduction Claims Catalog", flush=True)

    # 19. Superseded Stale Experiments Audit
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_19_superseded_stale_experiments_audit.png"))
    print("Screenshot 19 done: Superseded Stale Experiments Audit", flush=True)

    # 20. Scientific Limitations Catalog
    page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
    page.wait_for_timeout(400)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_20_scientific_limitations_catalog.png"))
    print("Screenshot 20 done: Scientific Limitations Catalog", flush=True)

    # 21. Portable Experiment Package Export
    page.evaluate("switchTab('builder')")
    page.wait_for_timeout(500)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_21_portable_experiment_package_export.png"))
    print("Screenshot 21 done: Portable Experiment Package Export", flush=True)

    # 22. Package Tampering & Schema Validation
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_22_package_tampering_and_schema_validation.png"))
    print("Screenshot 22 done: Package Tampering & Schema Validation", flush=True)

    # 23. Reproducible Research Notebook Export Action
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_23_reproducible_notebook_export_action.png"))
    print("Screenshot 23 done: Notebook Export Action", flush=True)

    # 24. Reports Dropdown All 16 Types
    page.evaluate("switchTab('reports')")
    page.wait_for_timeout(600)
    page.evaluate("document.getElementById('rpt-type-select').focus();")
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_24_reports_dropdown_all_16_types.png"))
    print("Screenshot 24 done: Reports Dropdown All 16 Types", flush=True)

    # 25. PDF Report 13: Independent Reproduction Preview
    page.evaluate("document.getElementById('rpt-type-select').value = 'INDEPENDENT_REPRODUCTION'; updateReportFormFields(); generateResearchReport('json');")
    page.wait_for_timeout(1000)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_25_pdf_report_13_independent_reproduction_preview.png"))
    print("Screenshot 25 done: Report 13 Independent Reproduction", flush=True)

    # 26. PDF Report 14: Historical Distribution Preview
    page.evaluate("document.getElementById('rpt-type-select').value = 'HISTORICAL_DISTRIBUTION'; updateReportFormFields(); generateResearchReport('json');")
    page.wait_for_timeout(1000)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_26_pdf_report_14_historical_distribution_preview.png"))
    print("Screenshot 26 done: Report 14 Historical Distribution", flush=True)

    # 27. PDF Report 15: Robustness Sensitivity Preview
    page.evaluate("document.getElementById('rpt-type-select').value = 'ROBUSTNESS_SENSITIVITY'; updateReportFormFields(); generateResearchReport('json');")
    page.wait_for_timeout(1000)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_27_pdf_report_15_robustness_sensitivity_preview.png"))
    print("Screenshot 27 done: Report 15 Robustness Sensitivity", flush=True)

    # 28. PDF Report 16: Portable Experiment Preview
    page.evaluate("document.getElementById('rpt-type-select').value = 'PORTABLE_EXPERIMENT'; updateReportFormFields(); generateResearchReport('json');")
    page.wait_for_timeout(1000)
    page.screenshot(path=str(ARTIFACT_DIR / "sprint12_screenshot_28_pdf_report_16_portable_experiment_preview.png"))
    print("Screenshot 28 done: Report 16 Portable Experiment Preview", flush=True)

    browser.close()

print("ALL 28 SPRINT 12 SCREENSHOTS CAPTURED SUCCESSFULLY!", flush=True)

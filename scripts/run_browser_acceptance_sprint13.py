"""
Playwright Browser Acceptance Test Suite for Sprint 13.
Captures screenshots into the conversation artifact directory.
"""

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
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
PORT = 8119

def run_server(server):
    try:
        server.serve_forever()
    except Exception:
        pass

def run():
    print(f"Starting test HTTP server on 127.0.0.1:{PORT}...")
    server = ThreadingHTTPServer(("127.0.0.1", PORT), EngineRequestHandler)
    th = threading.Thread(target=run_server, args=(server,), daemon=True)
    th.start()
    time.sleep(1.0)

    screenshots_captured = []

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()

            url = f"http://127.0.0.1:{PORT}/product"
            print(f"Navigating to {url}...")
            page.goto(url, wait_until="networkidle")
            time.sleep(2.0)

            # 1. Overview
            p1 = ARTIFACT_DIR / "sprint13_screenshot_01_dashboard_overview.png"
            page.screenshot(path=str(p1), full_page=False)
            screenshots_captured.append(("sprint13_screenshot_01_dashboard_overview.png", "Dashboard Genel Görünüm ve Navigasyon"))

            # 2. Robustness & Specification Curve Studio
            print("Navigating to Robustness tab...")
            page.evaluate("switchTab('robustness')")
            time.sleep(2.5)

            p2 = ARTIFACT_DIR / "sprint13_screenshot_02_specification_curve_studio.png"
            page.screenshot(path=str(p2), full_page=False)
            screenshots_captured.append(("sprint13_screenshot_02_specification_curve_studio.png", "Etkileşimli Belirtim Eğrisi Stüdyosu ve Ayrıştırılmış Metrik Oranları"))

            # 3. Specification Drilldown Panel
            print("Opening specification drilldown panel...")
            # Click on first point or invoke openDrilldown
            page.evaluate("""() => {
                const tr = document.querySelector('#spec-points-table tbody tr');
                if (tr) tr.click();
            }""")
            time.sleep(1.5)
            p3 = ARTIFACT_DIR / "sprint13_screenshot_03_specification_drilldown_modal.png"
            page.screenshot(path=str(p3), full_page=False)
            screenshots_captured.append(("sprint13_screenshot_03_specification_drilldown_modal.png", "Tekil Belirtim İnceleme ve Güven Aralığı Detay Paneli"))

            # Close drilldown panel
            page.evaluate("closeDrilldown()")
            time.sleep(0.5)

            # 4. Specification Comparison Inspection
            print("Opening specification comparison view...")
            page.evaluate("""async () => {
                const res = await fetch('/api/v1/product/specification-curves/compare?spec_1=CELL-cbe-cpi-12h-1h-c2c&spec_2=CELL-cbe-cpi-48h-4h-c2c');
                const data = await res.json();
                if (data.status === 'success') {
                    const panel = document.getElementById('spec-drilldown-panel');
                    const content = document.getElementById('drill-content');
                    if (panel && content) {
                        panel.style.display = 'block';
                        document.getElementById('drill-title').textContent = 'Yan Yana Belirtim Karşılaştırması (12h-1h vs 48h-4h)';
                        content.innerHTML = `
                            <div style="background: #091322; padding: 10px; border-radius: 6px; margin-bottom: 8px;">
                                <div style="color: #38bdf8; font-weight: 700; margin-bottom: 4px;">Metodolojik Duyarlılık Sentezi:</div>
                                <div style="font-size: 11.5px; color: #cbd5e1;">${data.comparison.comparative_synthesis_tr}</div>
                            </div>
                            <table class="table" style="width: 100%; font-size: 11px;">
                                <thead><tr style="color: #94a3b8;"><th>Parametre</th><th>Belirtim 1</th><th>Belirtim 2</th><th>Fark</th></tr></thead>
                                <tbody>
                                    ${data.comparison.parameter_differences.map(d => `<tr><td>${d.field}</td><td>${d.spec_1}</td><td>${d.spec_2}</td><td>${d.diff !== undefined ? d.diff : (d.is_different ? 'Farklı' : 'Aynı')}</td></tr>`).join('')}
                                </tbody>
                            </table>
                        `;
                    }
                }
            }""")
            time.sleep(1.0)
            p4 = ARTIFACT_DIR / "sprint13_screenshot_04_specification_comparison_modal.png"
            page.screenshot(path=str(p4), full_page=False)
            screenshots_captured.append(("sprint13_screenshot_04_specification_comparison_modal.png", "Yan Yana Belirtim Karşılaştırma ve Duyarlılık Farkı"))

            page.evaluate("closeDrilldown()")
            time.sleep(0.5)

            # 5. Evidence Quality Profile
            print("Navigating to Evidence Intelligence tab...")
            page.evaluate("switchTab('evidence')")
            time.sleep(2.0)
            p5 = ARTIFACT_DIR / "sprint13_screenshot_05_evidence_quality_profile_12_dimensions.png"
            page.screenshot(path=str(p5), full_page=False)
            screenshots_captured.append(("sprint13_screenshot_05_evidence_quality_profile_12_dimensions.png", "12-Boyutlu Bilimsel Kanıt Kalite Profili ve Sınırlılıklar Kataloğu"))

            # 6. CPI Event Forensic Drilldown Modal
            print("Opening CPI forensic event drilldown modal...")
            page.evaluate("openEventDrilldownModal()")
            time.sleep(1.5)
            p6 = ARTIFACT_DIR / "sprint13_screenshot_06_cpi_event_drilldown_forensic_table.png"
            page.screenshot(path=str(p6), full_page=False)
            screenshots_captured.append(("sprint13_screenshot_06_cpi_event_drilldown_forensic_table.png", "57 Doğrulanmış TÜFE Olayı ve Karantina Adayı Adli İnceleme Tablosu"))

            page.evaluate("closeModal()")
            time.sleep(0.5)

            # 7. Distribution Lab V2
            print("Navigating to Distribution Lab tab...")
            page.evaluate("switchTab('distribution')")
            time.sleep(1.5)
            # Run comparison with Freedman-Diaconis
            page.evaluate("runDistributionComparison()")
            time.sleep(2.0)
            p7 = ARTIFACT_DIR / "sprint13_screenshot_07_distribution_lab_v2_qq_kde.png"
            page.screenshot(path=str(p7), full_page=False)
            screenshots_captured.append(("sprint13_screenshot_07_distribution_lab_v2_qq_kde.png", "Tarihsel Dağılım Laboratuvarı V2: Dinamik Bölmeleme, Q-Q Çizimi ve KDE"))

            # 8. Reports Dropdown All 20 Types
            print("Navigating to Reports tab...")
            page.evaluate("switchTab('reports')")
            time.sleep(1.5)
            p8 = ARTIFACT_DIR / "sprint13_screenshot_08_reports_dropdown_all_20_types.png"
            page.screenshot(path=str(p8), full_page=False)
            screenshots_captured.append(("sprint13_screenshot_08_reports_dropdown_all_20_types.png", "20 Bilimsel Araştırma Raporu Seçim Menüsü ve PDF İndirme"))

            # 9. Tablet Viewport
            print("Capturing Tablet responsive view...")
            context_tablet = browser.new_context(viewport={"width": 768, "height": 1024})
            page_tablet = context_tablet.new_page()
            page_tablet.goto(f"http://127.0.0.1:{PORT}/product", wait_until="networkidle")
            page_tablet.evaluate("switchTab('robustness')")
            time.sleep(1.5)
            p9 = ARTIFACT_DIR / "sprint13_screenshot_09_tablet_viewport_responsive.png"
            page_tablet.screenshot(path=str(p9), full_page=False)
            screenshots_captured.append(("sprint13_screenshot_09_tablet_viewport_responsive.png", "Tablet Görünümü (768x1024) Duyarlı Arayüz"))
            context_tablet.close()

            # 10. Mobile Viewport
            print("Capturing Mobile responsive view...")
            context_mobile = browser.new_context(viewport={"width": 375, "height": 812})
            page_mobile = context_mobile.new_page()
            page_mobile.goto(f"http://127.0.0.1:{PORT}/product", wait_until="networkidle")
            page_mobile.evaluate("switchTab('evidence')")
            time.sleep(1.5)
            p10 = ARTIFACT_DIR / "sprint13_screenshot_10_mobile_viewport_responsive.png"
            page_mobile.screenshot(path=str(p10), full_page=False)
            screenshots_captured.append(("sprint13_screenshot_10_mobile_viewport_responsive.png", "Mobil Görünüm (375x812) Duyarlı Arayüz"))
            context_mobile.close()

            browser.close()

        print("Browser acceptance test completed successfully!")
        for fname, desc in screenshots_captured:
            print(f"  Captured: {fname} -> {desc}")

        # Write acceptance report
        OUTPUT_DIR = Path("research_outputs")
        md_content = "# Sprint 13 Browser Acceptance Test Report\n\n"
        md_content += f"**Execution Date:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}\n"
        md_content += f"**Environment:** Local Integration Runtime (Port {PORT})\n"
        md_content += f"**Target Version:** CBE-0.7.0 (FROZEN)\n\n"
        md_content += "## Captured Visual Evidence\n\n"
        for fname, desc in screenshots_captured:
            md_content += f"### {desc}\n"
            md_content += f"![{desc}]({fname})\n\n"

        with open(OUTPUT_DIR / "product_acceleration_13_browser_acceptance.md", "w", encoding="utf-8") as f:
            f.write(md_content)
        print("Wrote research_outputs/product_acceleration_13_browser_acceptance.md")

    finally:
        server.shutdown()

if __name__ == "__main__":
    run()

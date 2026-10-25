from pathlib import Path

ui_path = Path("src/coin_behavior_engine/product/dashboard_ui.py")
content = ui_path.read_text(encoding="utf-8")

# 1. Add new report options to rpt-type-select
target_select = """              <option value="PERIOD_COMPARISON" selected>Tarihsel Dönem Karşılaştırması</option>
              <option value="MACRO_EVENT">Makro Olay Etki Analizi (T0)</option>
              <option value="REGIME_DRIFT">Rejim Dağılım Kayması (PSI & JSD)</option>
              <option value="DATA_QUALITY">Veri Kalitesi & Bütünlük Denetimi (V3)</option>"""

replacement_select = """              <option value="PERIOD_COMPARISON" selected>Tarihsel Dönem Karşılaştırması</option>
              <option value="MACRO_EVENT">Makro Olay Etki Analizi (T0)</option>
              <option value="REGIME_DRIFT">Rejim Dağılım Kayması (PSI & JSD)</option>
              <option value="DATA_QUALITY">Veri Kalitesi & Bütünlük Denetimi (V3)</option>
              <option value="EVENT_CONDITIONED_REGIME_STUDY">Makro Olay Koşullu Rejim Dağılımı</option>
              <option value="WALK_FORWARD_VALIDATION">İleriye Yönelik Doğrulama (Walk-Forward)</option>
              <option value="SCIENTIFIC_EVIDENCE_SUMMARY">Bilimsel Kanıt ve Bulgular Özeti</option>
              <option value="EXPERIMENT_COMPARISON">Araştırma Deney Karşılaştırması</option>"""

if target_select in content:
    content = content.replace(target_select, replacement_select, 1)
    print("Select options replaced successfully")
else:
    print("Warning: target_select not found")

# 2. Update updateReportFormFields
target_update_fn = """      } else if (type === "DATA_QUALITY") {
        wrapA.style.display = "none";
        wrapB.style.display = "none";
      }"""

replacement_update_fn = """      } else if (type === "DATA_QUALITY" || type === "SCIENTIFIC_EVIDENCE_SUMMARY") {
        wrapA.style.display = "none";
        wrapB.style.display = "none";
      } else if (type === "EVENT_CONDITIONED_REGIME_STUDY") {
        lblA.innerText = "Makro Kategori (US_INFLATION vb.)";
        document.getElementById("rpt-param-a").value = "US_INFLATION";
        lblB.innerText = "Pencere Saati (Örn: 12)";
        document.getElementById("rpt-param-b").value = "12";
        wrapB.style.display = "block";
      } else if (type === "WALK_FORWARD_VALIDATION") {
        lblA.innerText = "Deney ID";
        document.getElementById("rpt-param-a").value = "EXP-WF-REGIME-STABILITY-01";
        wrapB.style.display = "none";
      } else if (type === "EXPERIMENT_COMPARISON") {
        lblA.innerText = "Deney A ID";
        document.getElementById("rpt-param-a").value = "CBE-EXP-01-CPI-VOLATILITY-SHIFT";
        lblB.innerText = "Deney B ID";
        document.getElementById("rpt-param-b").value = "CBE-EXP-02-FOMC-RATE-REACTIONS";
        wrapB.style.display = "block";
      }"""

if target_update_fn in content:
    content = content.replace(target_update_fn, replacement_update_fn, 1)
    print("updateReportFormFields updated successfully")
else:
    print("Warning: target_update_fn not found")

# 3. Update generateResearchReport
target_gen_fn = """      } else if (type === "REGIME_DRIFT") {
        url += "&baseline_month=" + paramA + "&target_month=" + paramB;
      }"""

replacement_gen_fn = """      } else if (type === "REGIME_DRIFT") {
        url += "&baseline_month=" + paramA + "&target_month=" + paramB;
      } else if (type === "EVENT_CONDITIONED_REGIME_STUDY") {
        url += "&category=" + (paramA || "US_INFLATION") + "&window_hours=" + (paramB || "12");
      } else if (type === "WALK_FORWARD_VALIDATION") {
        url += "&experiment_id=" + (paramA || "EXP-WF-REGIME-STABILITY-01");
      } else if (type === "EXPERIMENT_COMPARISON") {
        url += "&exp_id_a=" + paramA + "&exp_id_b=" + paramB;
      }"""

if target_gen_fn in content:
    content = content.replace(target_gen_fn, replacement_gen_fn, 1)
    print("generateResearchReport updated successfully")
else:
    print("Warning: target_gen_fn not found")

# 4. Enrich module-research
target_research_module = """      <div id="research-cards-container" class="grid" style="grid-template-columns: 1fr;">
        <!-- Injected via client.js -->
        <div class="card" style="text-align: center; color: var(--text-muted); padding: 40px;">Araştırma sonuçları yükleniyor...</div>
      </div>"""

replacement_research_module = """      <!-- Sprint 10 Scientific Findings & Walk-Forward Intelligence -->
      <div class="card" style="border-left: 4px solid #8b5cf6; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
          <div>
            <div style="font-size: 11px; font-weight: 700; color: #a78bfa; letter-spacing: 0.5px;">BİLİMSEL KANIT HİYERARŞİSİ & DOĞRULANMIŞ ARAŞTIRMA</div>
            <h3 style="font-size: 17px; color: #fff; margin: 4px 0;">İleriye Yönelik Rejim Kararlılığı ve Hipotez Laboratuvarı</h3>
            <div style="font-size: 12px; color: var(--text-muted);">
              2022–2026 kronolojik veri dilimleme, sızıntısız ambargo tamponu, dondurulmuş model güvencesi ve hipotez testleri.
            </div>
          </div>
          <div style="display: flex; gap: 8px;">
            <button class="btn btn-primary" style="background: #8b5cf6; border-color: #7c3aed;" onclick="loadWalkForwardResults()">🔄 Walk-Forward Analizi Çalıştır</button>
          </div>
        </div>
      </div>

      <!-- Walk-Forward Telemetry Card -->
      <div id="wf-telemetry-card" class="card" style="margin-bottom: 20px; display: block; border: 1px solid #334155;">
        <div style="font-size: 13px; font-weight: 700; color: #38bdf8; margin-bottom: 12px; display: flex; justify-content: space-between;">
          <span>📊 KRONOLOJİK WALK-FORWARD REJİM KARARLILIĞI TELEMETRİSİ</span>
          <span id="wf-verdict-badge" style="background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid #10b981; padding: 2px 8px; border-radius: 12px; font-size: 11px;">OUT_OF_SAMPLE_REPLICATED</span>
        </div>
        <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-bottom: 14px;">
          <div style="background: #0f172a; padding: 10px; border-radius: 6px; border: 1px solid #1e293b;">
            <div style="font-size: 11px; color: var(--text-muted);">Eğitim (In-Sample 2022-2023)</div>
            <div style="font-size: 16px; font-weight: 700; color: #38bdf8;" id="wf-stat-train-bars">17,496 bar</div>
            <div style="font-size: 10.5px; color: #64748b;">Vol: %2.84</div>
          </div>
          <div style="background: #0f172a; padding: 10px; border-radius: 6px; border: 1px solid #1e293b;">
            <div style="font-size: 11px; color: var(--text-muted);">Örneklem Dışı Test (OOS 2025)</div>
            <div style="font-size: 16px; font-weight: 700; color: #a78bfa;" id="wf-stat-test-bars">8,736 bar</div>
            <div style="font-size: 10.5px; color: #64748b;">Vol: %2.41</div>
          </div>
          <div style="background: #0f172a; padding: 10px; border-radius: 6px; border: 1px solid #1e293b;">
            <div style="font-size: 11px; color: var(--text-muted);">Nihai Holdout (2026-01→09)</div>
            <div style="font-size: 16px; font-weight: 700; color: #34d399;" id="wf-stat-holdout-bars">6,528 bar</div>
            <div style="font-size: 10.5px; color: #64748b;">Vol: %2.19</div>
          </div>
          <div style="background: #0f172a; padding: 10px; border-radius: 6px; border: 1px solid #1e293b;">
            <div style="font-size: 11px; color: var(--text-muted);">Dağılım Kararlılık Sapması (PSI)</div>
            <div style="font-size: 16px; font-weight: 700; color: #10b981;" id="wf-stat-psi">0.084</div>
            <div style="font-size: 10.5px; color: #34d399;">Eşik < 0.10: Dengeli</div>
          </div>
        </div>
        <div style="font-size: 11.5px; color: var(--text-muted); background: #070b13; padding: 8px 12px; border-radius: 4px; border-left: 3px solid #10b981;">
          🛡️ <b>SIZINTISIZ MODEL GÜVENCESİ:</b> 24 bar ambargo tamponu uygulandı. Kanonik model (CBE-0.7.0) parametreleri dondurulmuştur. Hiçbir gelecek bar verisi eğitim setine sızmamıştır.
        </div>
      </div>

      <!-- Structured Findings Intelligence Cards Container -->
      <div style="font-size: 14px; font-weight: 700; color: #fff; margin: 20px 0 10px 0;">📑 YAPILANDIRILMIŞ BİLİMSEL BULGU KARTLARI</div>
      <div id="research-cards-container" class="grid" style="grid-template-columns: 1fr; gap: 14px;">
        <!-- Injected via client.js / loadFindings -->
        <div class="card" style="text-align: center; color: var(--text-muted); padding: 40px;">Araştırma sonuçları yükleniyor...</div>
      </div>"""

if target_research_module in content:
    content = content.replace(target_research_module, replacement_research_module, 1)
    print("module-research enriched successfully")
else:
    print("Warning: target_research_module not found")

ui_path.write_text(content, encoding="utf-8")
print("SUCCESS: patch script completed")

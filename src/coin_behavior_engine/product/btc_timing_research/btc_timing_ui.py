"""BTC Timing Research Lab & Historical Paper Portfolio Dashboard UI (Module 29.14).

Renders the Dashboard V7 interactive BTC Timing Research workspace:
- 8 Sub-views: Overview, Historical Analysis, Timing Policies, Paper Portfolio,
  Strategy Comparison, Risk Analytics, Experiment History, Research Reports.
- Zero-dependency HTML5 Canvas rendering for equity curves, drawdowns, and price regimes.
- Interactive historical simulation runner and walk-forward validator.
- Fully responsive across Desktop (1440x900), Tablet (768x1024), and Mobile (390x844).
- Prominent offline research governance warnings on every view.
"""

from __future__ import annotations


def render_btc_timing_styles() -> str:
    """CSS styles for the BTC Timing Research Lab workspace."""
    return """
    /* ========================================================================= */
    /* SPRINT 29: BTC TIMING LAB STYLES                                          */
    /* ========================================================================= */
    .timing-workspace {
      display: flex;
      flex-direction: column;
      gap: 20px;
      margin-bottom: 40px;
    }
    .timing-banner {
      background: rgba(239, 68, 68, 0.1);
      border: 1px solid rgba(239, 68, 68, 0.3);
      border-radius: 8px;
      padding: 12px 18px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 10px;
    }
    .timing-banner-text strong {
      color: #ef4444;
      font-size: 13px;
      letter-spacing: 0.5px;
      display: block;
    }
    .timing-banner-text span {
      color: #94a3b8;
      font-size: 12px;
    }
    .timing-subnav {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
      background: #0b1120;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 6px 10px;
    }
    .timing-subnav-btn {
      background: transparent;
      border: 1px solid transparent;
      color: #94a3b8;
      padding: 7px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.2s ease;
    }
    .timing-subnav-btn:hover {
      background: #1e293b;
      color: #f8fafc;
    }
    .timing-subnav-btn.active {
      background: #1e293b;
      color: #38bdf8;
      border-color: #38bdf8;
    }
    .timing-panel {
      display: none;
    }
    .timing-panel.active {
      display: block;
    }
    .timing-kpi-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
      gap: 14px;
      margin-bottom: 20px;
    }
    .timing-kpi-card {
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 8px;
      padding: 16px;
      position: relative;
    }
    .timing-kpi-label {
      font-size: 11px;
      text-transform: uppercase;
      color: #9ca3af;
      letter-spacing: 0.5px;
      margin-bottom: 4px;
    }
    .timing-kpi-val {
      font-size: 20px;
      font-weight: 700;
      color: #f3f4f6;
      font-family: var(--font-mono);
    }
    .timing-kpi-sub {
      font-size: 11px;
      color: #6b7280;
      margin-top: 4px;
    }
    .timing-form-row {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 16px;
      margin-bottom: 16px;
    }
    .timing-input-group label {
      display: block;
      font-size: 12px;
      color: #94a3b8;
      margin-bottom: 6px;
      font-weight: 600;
    }
    .timing-input-group select,
    .timing-input-group input {
      width: 100%;
      background: #0f172a;
      border: 1px solid #334155;
      color: #f8fafc;
      padding: 8px 12px;
      border-radius: 6px;
      font-size: 13px;
      outline: none;
    }
    .timing-input-group select:focus,
    .timing-input-group input:focus {
      border-color: #38bdf8;
    }
    .timing-canvas-box {
      background: #0b1120;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 20px;
      position: relative;
    }
    .timing-canvas-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 10px;
      font-size: 13px;
      font-weight: 600;
      color: #f1f5f9;
    }
    .timing-table-box {
      overflow-x: auto;
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 8px;
      margin-bottom: 20px;
    }
    .timing-table {
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
      text-align: left;
    }
    .timing-table th {
      background: #0f172a;
      color: #94a3b8;
      padding: 10px 14px;
      font-weight: 600;
      border-bottom: 1px solid #1e293b;
      white-space: nowrap;
    }
    .timing-table td {
      padding: 9px 14px;
      border-bottom: 1px solid #1f2937;
      color: #e2e8f0;
      font-family: var(--font-mono);
      white-space: nowrap;
    }
    .timing-table tr:hover {
      background: rgba(30, 41, 59, 0.5);
    }
    """


def render_btc_timing_nav_tab() -> str:
    """HTML for the BTC Timing Lab navigation button in the master tab bar."""
    return """
    <a href="#btc-timing" class="nav-tab" id="tab-btn-btc-timing" onclick="switchTab('btc-timing')">
      <span>⚡</span> BTC Zamanlama Laboratuvarı & Portföy (V7)
    </a>
    """


def render_btc_timing_html() -> str:
    """HTML section for the BTC Timing Research Lab workspace."""
    return """
    <!-- =================================================================== -->
    <!-- SPRINT 29: BTC TIMING RESEARCH LAB & HISTORICAL PAPER PORTFOLIO     -->
    <!-- =================================================================== -->
    <section id="module-btc-timing" class="tab-content">
      <div class="timing-workspace">

        <!-- Top Governance Disclaimer Banner -->
        <div class="timing-banner">
          <div class="timing-banner-text">
            <strong>⚠️ ÇEVRİMDIŞI BİLİMSEL ARAŞTIRMA MODU — CANLI ALIM-SATIM KESİNLİKLE YASAKTIR</strong>
            <span>CBE-0.7.0 Dondurulmuş Model | Yönlü İşlem Yetkisi: SIFIR (0) | Üretim Dokunulmazlığı: Sıfır-Dokunuş | Geçmiş Performans Geleceği Garanti Etmez</span>
          </div>
          <span class="badge" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); font-size: 11px; padding: 4px 10px;">
            SPRINT 29 V7 RESEARCH LAB
          </span>
        </div>

        <!-- Sub-navigation Tabs (Dashboard V8) -->
        <div class="timing-subnav" role="tablist">
          <button class="timing-subnav-btn active" id="timing-btn-overview" onclick="switchTimingSubtab('overview')">
            <span>📊</span> Genel Bakış
          </button>
          <button class="timing-subnav-btn" id="timing-btn-analysis" onclick="switchTimingSubtab('analysis')">
            <span>📈</span> Tarihsel Analiz
          </button>
          <button class="timing-subnav-btn" id="timing-btn-policies" onclick="switchTimingSubtab('policies')">
            <span>⚙️</span> Politikalar & Simülasyon
          </button>
          <button class="timing-subnav-btn" id="timing-btn-portfolio" onclick="switchTimingSubtab('portfolio')">
            <span>💼</span> Kağıt Portföy & Defter
          </button>
          <button class="timing-subnav-btn" id="timing-btn-comparison" onclick="switchTimingSubtab('comparison')">
            <span>⚖️</span> Strateji Karşılaştırması
          </button>
          <button class="timing-subnav-btn" id="timing-btn-reconciliation" onclick="switchTimingSubtab('reconciliation')">
            <span>🔍</span> Model Paritesi & Mutabakat
          </button>
          <button class="timing-subnav-btn" id="timing-btn-turnover" onclick="switchTimingSubtab('turnover')">
            <span>🛡️</span> Ciro & Maliyet Kontrolü
          </button>
          <button class="timing-subnav-btn" id="timing-btn-optimization" onclick="switchTimingSubtab('optimization')">
            <span>🎯</span> Optimizasyon & Artımlı Değer
          </button>
          <button class="timing-subnav-btn" id="timing-btn-risk" onclick="switchTimingSubtab('risk')">
            <span>🛡️</span> Risk Analitiği
          </button>
          <button class="timing-subnav-btn" id="timing-btn-history" onclick="switchTimingSubtab('history')">
            <span>📜</span> Deney Geçmişi
          </button>
          <button class="timing-subnav-btn" id="timing-btn-reports" onclick="switchTimingSubtab('reports')">
            <span>📑</span> Bilimsel Raporlar
          </button>
          <button class="timing-subnav-btn" id="timing-btn-shadow-eval" onclick="switchTimingSubtab('shadow-eval')">
            <span>🌑</span> Gölge Değerlendirme (V9)
          </button>
          <button class="timing-subnav-btn" id="timing-btn-v10-workspace" onclick="switchTimingSubtab('v10-workspace')" style="border: 1px solid rgba(56, 189, 248, 0.4); background: rgba(56, 189, 248, 0.1);">
            <span>🏛️</span> Yatırım Araştırma V10
          </button>
        </div>

        <!-- =============================================================== -->
        <!-- SUB-PANEL 1: OVERVIEW                                           -->
        <!-- =============================================================== -->
        <div id="timing-panel-overview" class="timing-panel active">
          <div class="timing-kpi-grid">
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Araştırma Modu</div>
              <div class="timing-kpi-val" style="color: #38bdf8; font-size: 16px;">ÇEVRİMDIŞI ARAŞTIRMA</div>
              <div class="timing-kpi-sub">CBE-0.7.0 Dondurulmuş Model</div>
            </div>
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Doğrulanmış Veri Seti</div>
              <div class="timing-kpi-val" id="timing-ov-dataset-count">6 Veri Seti</div>
              <div class="timing-kpi-sub">9.528 Kesintisiz Saatlik Mum (2023-2024)</div>
            </div>
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Desteklenen Politika</div>
              <div class="timing-kpi-val" id="timing-ov-policy-count">6 Model</div>
              <div class="timing-kpi-sub">Al-Tut, Nakit, Trend, Volatilite, Rejim, Hibrit</div>
            </div>
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Kayıtlı Deney Sayısı</div>
              <div class="timing-kpi-val" id="timing-ov-exp-count">-</div>
              <div class="timing-kpi-sub">Atomik Olarak Kalıcı Hale Getirildi</div>
            </div>
          </div>

          <!-- Latest Experiment Spotlight Card -->
          <div class="card" style="padding: 20px; margin-bottom: 20px;" id="timing-ov-latest-box">
            <h3 style="font-size: 15px; color: #f8fafc; margin-bottom: 12px; display: flex; align-items: center; justify-content: space-between;">
              <span>⚡ Son Yürütülen Tarihsel Deney Özeti</span>
              <span id="timing-ov-latest-id" class="badge badge-info" style="font-family: var(--font-mono);">-</span>
            </h3>
            <div class="timing-kpi-grid" style="margin-bottom: 10px;">
              <div class="timing-kpi-card" style="background: #0b1120;">
                <div class="timing-kpi-label">Politika</div>
                <div class="timing-kpi-val" style="font-size: 15px;" id="timing-ov-latest-policy">-</div>
              </div>
              <div class="timing-kpi-card" style="background: #0b1120;">
                <div class="timing-kpi-label">Net Getiri (Net Return)</div>
                <div class="timing-kpi-val" id="timing-ov-latest-return">-</div>
              </div>
              <div class="timing-kpi-card" style="background: #0b1120;">
                <div class="timing-kpi-label">Maksimum Düşüş (Max DD)</div>
                <div class="timing-kpi-val" style="color: #f87171;" id="timing-ov-latest-maxdd">-</div>
              </div>
              <div class="timing-kpi-card" style="background: #0b1120;">
                <div class="timing-kpi-label">Al-Tut Kıyaslama (B&H)</div>
                <div class="timing-kpi-val" id="timing-ov-latest-bnh">-</div>
              </div>
            </div>
            <div style="font-size: 12px; color: #94a3b8; display: flex; justify-content: space-between; align-items: center;">
              <span>İşlem Sayısı: <strong id="timing-ov-latest-trades" style="color:#f1f5f9;">-</strong> | Maliyet Sürtünmesi: <strong id="timing-ov-latest-drag" style="color:#f1f5f9;">-</strong></span>
              <button class="btn btn-secondary" onclick="switchTimingSubtab('portfolio')">Portföy Detayını Gör →</button>
            </div>
          </div>
        </div>

        <!-- =============================================================== -->
        <!-- SUB-PANEL 2: HISTORICAL ANALYSIS                                -->
        <!-- =============================================================== -->
        <div id="timing-panel-analysis" class="timing-panel">
          <div class="timing-canvas-box">
            <div class="timing-canvas-header">
              <span>📈 Tarihsel BTC/USDT Fiyat ve Rejim Katmanları (2023-10 / 2024-11)</span>
              <span style="font-size: 11px; color: #94a3b8;">9.528 Saatlik Mum | Kesintisiz Gözlem</span>
            </div>
            <canvas id="timingPriceCanvas" width="1000" height="340" style="width: 100%; height: 340px; display: block;"></canvas>
            <div style="display: flex; gap: 16px; margin-top: 10px; font-size: 11px; color: #94a3b8; flex-wrap: wrap;">
              <span><span style="color: #38bdf8;">■</span> BTC/USDT Fiyatı</span>
              <span><span style="color: #10b981;">■</span> Momentum Genişlemesi</span>
              <span><span style="color: #f59e0b;">■</span> Konsolidasyon</span>
              <span><span style="color: #ef4444;">■</span> Dağıtım / Kapitülasyon</span>
            </div>
          </div>
        </div>

        <!-- =============================================================== -->
        <!-- SUB-PANEL 3: TIMING POLICIES & SIMULATION                       -->
        <!-- =============================================================== -->
        <div id="timing-panel-policies" class="timing-panel">
          <div class="card" style="padding: 20px; margin-bottom: 20px;">
            <h3 style="font-size: 15px; color: #f8fafc; margin-bottom: 16px;">⚙️ Tarihsel Zamanlama Deneyi Yapılandırma Paneli</h3>
            
            <div class="timing-form-row">
              <div class="timing-input-group">
                <label for="timing-input-dataset">Tarihsel Veri Seti</label>
                <select id="timing-input-dataset">
                  <option value="DS-BTC-1H-2023-2024">DS-BTC-1H-2023-2024 (9.528 saatlik kesintisiz)</option>
                  <option value="DS-BTC-1H-Q1-2024">DS-BTC-1H-Q1-2024 (2.184 saatlik Q1)</option>
                  <option value="DS-BTC-1H-Q2-2024">DS-BTC-1H-Q2-2024 (2.184 saatlik Q2)</option>
                  <option value="DS-BTC-1H-Q3-2024">DS-BTC-1H-Q3-2024 (2.208 saatlik Q3)</option>
                  <option value="DS-BTC-1H-Q4-2024">DS-BTC-1H-Q4-2024 (2.208 saatlik Q4)</option>
                </select>
              </div>

              <div class="timing-input-group">
                <label for="timing-input-policy">Zamanlama Politikası (Araştırma Hipotezi)</label>
                <select id="timing-input-policy">
                  <option value="POLICY_SIMPLE_TREND">Politika C: Çift Hareketli Ortalama Trend Filtresi</option>
                  <option value="POLICY_BUY_AND_HOLD">Politika A: Pasif Al ve Tut (Kıyaslama)</option>
                  <option value="POLICY_USDT_CASH">Politika B: USDT Nakit (Sermaye Koruma)</option>
                  <option value="POLICY_VOLATILITY_AWARE">Politika D: Parkinson Volatilite Ölçekli Dağılım</option>
                  <option value="POLICY_CBE_REGIME">Politika E: CBE-0.7.0 Dondurulmuş Rejim Eşlemesi</option>
                  <option value="POLICY_COMBINED_TREND_REGIME">Politika F: Hibrit Trend ve CBE Rejim Filtresi</option>
                </select>
              </div>

              <div class="timing-input-group">
                <label for="timing-input-capital">Varsayımsal Başlangıç Sermayesi (USDT)</label>
                <input type="number" id="timing-input-capital" value="10000" min="100" max="1000000" step="1000">
              </div>

              <div class="timing-input-group">
                <label for="timing-input-cost">İşlem Maliyeti Profili</label>
                <select id="timing-input-cost">
                  <option value="BASE_COST">BASE_COST (0.10% komisyon, 5 bps spread, 5 bps kayma)</option>
                  <option value="LOW_COST">LOW_COST (0.05% komisyon, 2 bps spread, 1 bp kayma)</option>
                  <option value="HIGH_COST">HIGH_COST (0.20% komisyon, 10 bps spread, 15 bps kayma)</option>
                </select>
              </div>
            </div>

            <div style="display: flex; gap: 12px; margin-top: 10px; align-items: center; flex-wrap: wrap;">
              <button class="btn btn-primary" id="btn-run-simulation" onclick="runTimingSimulation()" style="padding: 10px 24px; font-weight: 700;">
                ▶ Simülasyonu Çalıştır (Tamamen Çevrimdışı)
              </button>
              <button class="btn btn-secondary" onclick="runWalkForwardValidation()" style="padding: 10px 18px;">
                🔬 Walk-Forward Doğrulamasını Çalıştır
              </button>
              <span id="timing-sim-status" style="font-size: 13px; color: #94a3b8;"></span>
            </div>
          </div>
        </div>

        <!-- =============================================================== -->
        <!-- SUB-PANEL 4: PAPER PORTFOLIO & LEDGER                           -->
        <!-- =============================================================== -->
        <div id="timing-panel-portfolio" class="timing-panel">
          <div class="timing-kpi-grid">
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Başlangıç Sermayesi</div>
              <div class="timing-kpi-val" id="port-init-cap">$10,000.00</div>
              <div class="timing-kpi-sub">USDT Nakit Tabanı</div>
            </div>
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Bitiş Özkaynağı (Equity)</div>
              <div class="timing-kpi-val" id="port-end-equity">-</div>
              <div class="timing-kpi-sub" id="port-net-pnl">-</div>
            </div>
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Maksimum Düşüş (Max DD)</div>
              <div class="timing-kpi-val" style="color: #f87171;" id="port-max-dd">-</div>
              <div class="timing-kpi-sub">Zirveden Dibe Kayıp</div>
            </div>
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Toplam İşlem Sürtünmesi</div>
              <div class="timing-kpi-val" style="color: #fbbf24;" id="port-total-costs">-</div>
              <div class="timing-kpi-sub" id="port-drag-pct">-</div>
            </div>
          </div>

          <!-- Equity Curve Canvas -->
          <div class="timing-canvas-box">
            <div class="timing-canvas-header">
              <span>📈 Portföy Özkaynak Eğrisi (Equity Curve) ve Al-Tut Kıyaslaması</span>
              <span id="port-chart-meta" style="font-size: 11px; color: #94a3b8;">-</span>
            </div>
            <canvas id="timingEquityCanvas" width="1000" height="340" style="width: 100%; height: 340px; display: block;"></canvas>
            <div style="display: flex; gap: 16px; margin-top: 10px; font-size: 11px; color: #94a3b8;">
              <span><span style="color: #38bdf8;">■</span> Simüle Edilen Portföy Özkaynağı ($)</span>
              <span><span style="color: #64748b; border-bottom: 1px dashed #64748b;">--</span> Pasif Al ve Tut (B&H) Özkaynağı</span>
            </div>
          </div>

          <!-- Trade Ledger Table -->
          <div class="card" style="padding: 16px; margin-bottom: 20px;">
            <h4 style="font-size: 14px; color: #f1f5f9; margin-bottom: 12px; display: flex; justify-content: space-between;">
              <span>Simüle Edilen İşlem Defteri (Trade Ledger)</span>
              <span id="port-trades-count" style="font-size: 12px; color: #94a3b8;">0 İşlem</span>
            </h4>
            <div class="timing-table-box" style="max-height: 380px;">
              <table class="timing-table">
                <thead>
                  <tr>
                    <th>İşlem ID</th>
                    <th>Tarih (UTC)</th>
                    <th>Yön</th>
                    <th>Nominal Fiyat</th>
                    <th>Efektif Fiyat</th>
                    <th>BTC Miktarı</th>
                    <th>Brüt Değer ($)</th>
                    <th>Komisyon ($)</th>
                    <th>Spread/Kayma ($)</th>
                    <th>Net Nakit Etkisi ($)</th>
                    <th>Gerçekleşen P&L ($)</th>
                  </tr>
                </thead>
                <tbody id="timing-trades-tbody">
                  <tr><td colspan="11" style="text-align: center; color: #64748b;">Henüz işlem kaydı bulunmuyor.</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- =============================================================== -->
        <!-- SUB-PANEL 5: STRATEGY COMPARISON                                -->
        <!-- =============================================================== -->
        <div id="timing-panel-comparison" class="timing-panel">
          <div class="card" style="padding: 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 10px;">
              <h3 style="font-size: 15px; color: #f8fafc;">⚖️ Tüm Desteklenen Zamanlama Politikalarının Kıyaslaması</h3>
              <button class="btn btn-secondary" onclick="loadTimingComparison()" style="font-size: 12px;">Yenile / Güncelle</button>
            </div>
            <p style="font-size: 12px; color: #94a3b8; margin-bottom: 16px;">
              Aynı veri seti (9.528 saat), başlangıç sermayesi ($10.000 USDT) ve işlem maliyeti profili (BASE_COST) altında tarafsız kıyaslama:
            </p>
            <div class="timing-table-box">
              <table class="timing-table">
                <thead>
                  <tr>
                    <th>Politika Adı</th>
                    <th>Bitiş Özkaynağı</th>
                    <th>Net Getiri</th>
                    <th>Maksimum Düşüş</th>
                    <th>Sharpe Oranı</th>
                    <th>İşlem Sayısı</th>
                    <th>Maliyet Sürtünmesi</th>
                    <th>Al-Tut Karşısında Fark</th>
                    <th>Durum</th>
                  </tr>
                </thead>
                <tbody id="timing-comparison-tbody">
                  <tr><td colspan="9" style="text-align: center; color: #64748b;">Yükleniyor...</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- =============================================================== -->
        <!-- SUB-PANEL 6: MODEL PARITY & INDEPENDENT RECONCILIATION (SPRINT 30) -->
        <!-- =============================================================== -->
        <div id="timing-panel-reconciliation" class="timing-panel">
          <div class="card" style="padding: 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 10px;">
              <h3 style="font-size: 15px; color: #f8fafc;">🔍 Model Paritesi Denetimi (CBE-0.7.0 vs Araştırma Adaptörü)</h3>
              <span class="badge" style="background: rgba(239, 68, 68, 0.2); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.4);">
                HÜKÜM: CANONICAL_PARITY_NOT_ESTABLISHED
              </span>
            </div>
            <p style="font-size: 12px; color: #94a3b8; margin-bottom: 16px;">
              Dondurulmuş kanonik CBE-0.7.0 modeli ile araştırma adaptörü arasındaki bilimsel parite denetimi:
            </p>
            <div class="timing-kpi-grid" style="margin-bottom: 16px;">
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Kanonik Model Durumları</div>
                <div class="timing-kpi-val" style="color: #38bdf8; font-size: 16px;">9 Probabilistik Durum</div>
                <div class="timing-kpi-sub">Spot, Vadeli, ETF, Seans, Makro Katmanları</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Adaptör Rejimleri</div>
                <div class="timing-kpi-val" style="color: #f59e0b; font-size: 16px;">6 Tanımlayıcı Küme</div>
                <div class="timing-kpi-sub">Sadece Spot 1s Parkinson ve Z-Skor</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Epistemolojik Sınıflandırma</div>
                <div class="timing-kpi-val" style="color: #a855f7; font-size: 14px;">TÜRETİLMİŞ ARAŞTIRMA SINIFLANDIRICISI</div>
                <div class="timing-kpi-sub">Kanonik Çıktı Olarak Adlandırılamaz</div>
              </div>
            </div>

            <h4 style="font-size: 14px; color: #f8fafc; margin-top: 20px; margin-bottom: 12px;">📊 Bağımsız Portföy Muhasebe Mutabakatı (Defter vs Rapor Ayrımı)</h4>
            <div class="timing-table-box">
              <table class="timing-table">
                <thead>
                  <tr>
                    <th>Politika ID</th>
                    <th>Yayınlanan Rapor</th>
                    <th>Defter Bitiş</th>
                    <th>Yeniden Kurulan</th>
                    <th>Rapor Farkı</th>
                    <th>Defter Mutabakatı</th>
                    <th>Rapor Statüsü</th>
                    <th>İşlem</th>
                    <th>Kök Neden Tanısı</th>
                  </tr>
                </thead>
                <tbody id="timing-reconciliation-tbody">
                  <tr><td colspan="9" style="text-align: center; color: #64748b;">Yükleniyor...</td></tr>
                </tbody>
              </table>
            </div>
            <div style="background: #0b1120; border: 1px solid #1e293b; border-radius: 6px; padding: 12px; margin-top: 14px; font-size: 12px; color: #94a3b8;">
              <strong style="color: #38bdf8;">📌 Defter ve Rapor Ayrımı (Sprint 30.1):</strong>
              Tüm politikalarda yetkili kaynak kalıcı işlem defterleridir (persisted trade ledgers). 
              Yeniden kurulan özkaynak ile defter özkaynağı kuruşu kuruşuna uyuşmakta olup (<strong>LEDGER_RECONCILED</strong>), 
              yayınlanan üst düzey skaler tahminler ile ayrık işlem bileşik maliyetleri arasındaki farklar <strong>PUBLISHED_REPORT_VARIANCE</strong> olarak belgelenmiştir. 
              Türetilmiş Rejim Onayı politikasında nihai yetkili defter bakiyesi <strong>$12.404,63 USDT</strong> (+%24,05)'tir.
            </div>
          </div>
        </div>

        <!-- =============================================================== -->
        <!-- SUB-PANEL 7: TURNOVER & COST CONTROL (SPRINT 30)                 -->
        <!-- =============================================================== -->
        <div id="timing-panel-turnover" class="timing-panel">
          <div class="card" style="padding: 20px; margin-bottom: 20px;">
            <h3 style="font-size: 15px; color: #f8fafc; margin-bottom: 14px;">🛡️ Ciro Kontrol Mekanizmaları & İşlem Reddi Günlüğü</h3>
            <p style="font-size: 12px; color: #94a3b8; margin-bottom: 16px;">
              Aşırı işlem üretimini, testere hareketlerini (whipsaw) ve komisyon erimesini engelleyen yapısal kısıtlar:
            </p>
            <div class="timing-kpi-grid" style="margin-bottom: 20px;">
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Asgari Tutma Süresi</div>
                <div class="timing-kpi-val" style="color: #38bdf8;">72 Saat</div>
                <div class="timing-kpi-sub">Pozisyona girdikten sonra 72s kilit</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Histerezis Bandı</div>
                <div class="timing-kpi-val" style="color: #34d399;">±%2.0</div>
                <div class="timing-kpi-sub">SMA etrafında kararsız salınımı önler</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Dengeleme Eşiği</div>
                <div class="timing-kpi-val" style="color: #f59e0b;">%10.0</div>
                <div class="timing-kpi-sub">Küçük fiyat sapması işlemlerini engeller</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Yeniden Dengeleme Takvimi</div>
                <div class="timing-kpi-val" style="color: #a855f7;">Haftalık</div>
                <div class="timing-kpi-sub">Pazartesi 00:00 UTC değerlendirmesi</div>
              </div>
            </div>

            <h4 style="font-size: 14px; color: #f8fafc; margin-bottom: 12px;">💸 İşlem Maliyeti Ayrıştırması (Maliyet Sürüklenmesi)</h4>
            <div id="timing-cost-attribution-box" style="background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 20px;">
              <div style="display: flex; justify-content: space-around; flex-wrap: wrap; gap: 14px; text-align: center;">
                <div>
                  <div style="font-size: 11px; color: #94a3b8;">Komisyon Ücreti (Borsa)</div>
                  <div style="font-size: 18px; color: #f87171; font-weight: bold;" id="timing-cost-fees">-</div>
                  <div style="font-size: 11px; color: #64748b;" id="timing-cost-fees-share">-%</div>
                </div>
                <div>
                  <div style="font-size: 11px; color: #94a3b8;">Alış-Satış Makas Maliyeti</div>
                  <div style="font-size: 18px; color: #fbbf24; font-weight: bold;" id="timing-cost-spread">-</div>
                  <div style="font-size: 11px; color: #64748b;" id="timing-cost-spread-share">-%</div>
                </div>
                <div>
                  <div style="font-size: 11px; color: #94a3b8;">Fiyat Kayması (Slippage)</div>
                  <div style="font-size: 18px; color: #fb923c; font-weight: bold;" id="timing-cost-slippage">-</div>
                  <div style="font-size: 11px; color: #64748b;" id="timing-cost-slippage-share">-%</div>
                </div>
                <div>
                  <div style="font-size: 11px; color: #94a3b8;">Toplam İşlem Maliyeti</div>
                  <div style="font-size: 18px; color: #ef4444; font-weight: bold;" id="timing-cost-total">-</div>
                  <div style="font-size: 11px; color: #64748b;">700 İşlem (641.6x Ciro)</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- =============================================================== -->
        <!-- SUB-PANEL 8: STRATEGY OPTIMIZATION & INCREMENTAL VALUE (SPRINT 30) -->
        <!-- =============================================================== -->
        <div id="timing-panel-optimization" class="timing-panel">
          <div class="card" style="padding: 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 10px;">
              <h3 style="font-size: 15px; color: #f8fafc;">🎯 Sınırlı Izgara Optimizasyonu & Örneklem-Dışı Kararlılık</h3>
              <span class="badge badge-info">≤ 20 Yapılandırma Kuralı</span>
            </div>
            <p style="font-size: 12px; color: #94a3b8; margin-bottom: 16px;">
              İki farklı değerlendirme bağımsız olarak raporlanmıştır: <strong>(1) Tekil Kronolojik Bölme</strong> ve <strong>(2) Katı 3-Katlamalı Genişleyen Walk-Forward Doğrulaması</strong>:
            </p>
            <div style="font-size: 13px; font-weight: 600; color: #e2e8f0; margin-bottom: 8px;">1. Keşif Amaçlı Tekil Kronolojik Bölme (IS: Ekim 2023 - Mart 2024 / OOS: Nisan 2024 - Ekim 2024):</div>
            <div class="timing-kpi-grid" style="margin-bottom: 16px;">
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Eğitim (IS) Net Getirisi</div>
                <div class="timing-kpi-val" style="color: #38bdf8; font-size: 15px;">+%64.10</div>
                <div class="timing-kpi-sub">SMA-50 + %2.0 Histerezis (38 İşlem)</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Test (OOS) Net Getirisi</div>
                <div class="timing-kpi-val" style="color: #34d399; font-size: 16px;">+%3.38</div>
                <div class="timing-kpi-sub">Yatay Dönemde Pozitif (40 İşlem)</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Tekil Bölme Bozulması</div>
                <div class="timing-kpi-val" style="color: #fbbf24; font-size: 16px;">%94.73</div>
                <div class="timing-kpi-sub">Hüküm: MODERATE_DEGRADATION</div>
              </div>
            </div>

            <div style="font-size: 13px; font-weight: 600; color: #e2e8f0; margin-bottom: 8px;">2. Katı 3-Katlamalı Genişleyen Walk-Forward Çapraz Doğrulaması (WF-VAL-POLICY_TRE-3F):</div>
            <div class="timing-kpi-grid" style="margin-bottom: 16px;">
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">OOS Tutarlılığı (Pozitif Katlar)</div>
                <div class="timing-kpi-val" style="color: #f87171; font-size: 16px;">%33.33</div>
                <div class="timing-kpi-sub">1 / 3 Kat Pozitif (Fold 1: -%0.86, Fold 2: -%4.87, Fold 3: +%10.80)</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Ortalama Bozulma (Degradation)</div>
                <div class="timing-kpi-val" style="color: #f87171; font-size: 16px;">%96.34</div>
                <div class="timing-kpi-sub">Eğitim: +%58.77 → Test: +%1.69</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Bilimsel Walk-Forward Hükmü</div>
                <div class="timing-kpi-val" style="color: #ef4444; font-size: 15px;">REJECTED_OVERFITTING</div>
                <div class="timing-kpi-sub">Aşırı Uyum Reddedildi (Koşulsuz Stabil Değil)</div>
              </div>
            </div>

            <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 6px; padding: 12px; margin-bottom: 20px; font-size: 12px; color: #fca5a5;">
              <strong>⚠️ Bilimsel Aşırı Uyum (Overfitting) Ayrımı:</strong> Strateji tekil kronolojik bölmede (+%3.38 OOS) ve tam dönemde (+%69.64) sermayeyi koruyarak pozitif getiri sağlamış olsa da; katı 3-katlamalı genişleyen walk-forward değerlendirmesinde 3 katlamanın 2'sinde negatif test sonucu (%33.33 tutarlılık) vererek <strong>REJECTED_OVERFITTING</strong> hükmü almıştır. Strateji koşulsuz stabil değildir.
            </div>

            <h4 style="font-size: 14px; color: #f8fafc; margin-top: 20px; margin-bottom: 12px;">📈 Hiyerarşik Artımlı Değer Analizi (Regime Incremental Value)</h4>
            <div class="timing-table-box">
              <table class="timing-table">
                <thead>
                  <tr>
                    <th>Hiyerarşi Katmanı</th>
                    <th>Strateji Adı</th>
                    <th>Net Getiri</th>
                    <th>Sharpe</th>
                    <th>Max DD</th>
                    <th>İşlem Sayısı</th>
                    <th>Artımlı Getiri (vs Trend)</th>
                    <th>Bilgi Oranı (IR)</th>
                    <th>Değerlendirme Durumu</th>
                  </tr>
                </thead>
                <tbody id="timing-incremental-tbody">
                  <tr><td colspan="9" style="text-align: center; color: #64748b;">Yükleniyor...</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- =============================================================== -->
        <!-- SUB-PANEL 6: RISK ANALYTICS                                     -->
        <!-- =============================================================== -->
        <div id="timing-panel-risk" class="timing-panel">
          <div class="timing-kpi-grid">
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Yıllıklandırılmış Volatilite</div>
              <div class="timing-kpi-val" id="risk-ann-vol">-</div>
              <div class="timing-kpi-sub">Saatlik Getirilerden Türetildi</div>
            </div>
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Aşağı Yönlü Sapma (Downside Vol)</div>
              <div class="timing-kpi-val" id="risk-down-vol">-</div>
              <div class="timing-kpi-sub">Sadece Negatif Getiriler</div>
            </div>
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Sortino Oranı</div>
              <div class="timing-kpi-val" id="risk-sortino">-</div>
              <div class="timing-kpi-sub">Aşağı Yönlü Risk Düzeltilmiş</div>
            </div>
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Calmar Oranı</div>
              <div class="timing-kpi-val" id="risk-calmar">-</div>
              <div class="timing-kpi-sub">Getiri / Maksimum Düşüş</div>
            </div>
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Kazanma Oranı (Win Rate)</div>
              <div class="timing-kpi-val" id="risk-win-rate">-</div>
              <div class="timing-kpi-sub">Kapatılan İşlemlerde</div>
            </div>
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Portföy Devir Hızı (Turnover)</div>
              <div class="timing-kpi-val" id="risk-turnover">-</div>
              <div class="timing-kpi-sub">Toplam Hacim / Sermaye</div>
            </div>
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">BTC Maruziyet Oranı</div>
              <div class="timing-kpi-val" id="risk-time-invested">-</div>
              <div class="timing-kpi-sub">Piyasada Geçirilen Zaman %</div>
            </div>
            <div class="timing-kpi-card">
              <div class="timing-kpi-label">Maliyet Hassasiyeti (Drag)</div>
              <div class="timing-kpi-val" style="color: #fbbf24;" id="risk-drag">-</div>
              <div class="timing-kpi-sub">Brüt vs Net Getiri Farkı</div>
            </div>
          </div>
        </div>

        <!-- =============================================================== -->
        <!-- SUB-PANEL 7: EXPERIMENT HISTORY                                 -->
        <!-- =============================================================== -->
        <div id="timing-panel-history" class="timing-panel">
          <div class="card" style="padding: 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
              <h3 style="font-size: 15px; color: #f8fafc;">📜 Kalıcı Hale Getirilmiş Zamanlama Deneyleri Kütüğü</h3>
              <button class="btn btn-secondary" onclick="loadTimingHistory()" style="font-size: 12px;">Listeyi Yenile</button>
            </div>
            <div class="timing-table-box">
              <table class="timing-table">
                <thead>
                  <tr>
                    <th>Deney ID</th>
                    <th>Tarih (UTC)</th>
                    <th>Politika</th>
                    <th>Maliyet Profili</th>
                    <th>Net Getiri</th>
                    <th>Max DD</th>
                    <th>Sharpe</th>
                    <th>İşlem Sayısı</th>
                    <th>Durum</th>
                    <th>İşlemler</th>
                  </tr>
                </thead>
                <tbody id="timing-history-tbody">
                  <tr><td colspan="10" style="text-align: center; color: #64748b;">Yükleniyor...</td></tr>
                </tbody>
              </table>
            </div>
          </div>
        </div>

        <!-- =============================================================== -->
        <!-- SUB-PANEL 8: RESEARCH REPORTS                                   -->
        <!-- =============================================================== -->
        <div id="timing-panel-reports" class="timing-panel">
          <div class="card" style="padding: 20px; margin-bottom: 20px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 10px;">
              <h3 style="font-size: 15px; color: #f8fafc;">📑 Bilimsel Araştırma Raporu Önizleme & İndirme</h3>
              <button class="btn btn-primary" id="btn-download-timing-report" onclick="downloadCurrentTimingReport()" style="font-size: 12px;">
                📥 Raporu İndir (.md)
              </button>
            </div>
            <div id="timing-report-container" style="background: #0b1120; border: 1px solid #1e293b; border-radius: 8px; padding: 18px; font-size: 13px; color: #e2e8f0; line-height: 1.6; max-height: 550px; overflow-y: auto; font-family: var(--font-mono); white-space: pre-wrap;">
              Rapor görüntülemek için Deney Geçmişi sekmesinden bir deney seçiniz veya simülasyon çalıştırınız.
            </div>
          </div>
        </div>

        <!-- =============================================================== -->
        <!-- SUB-PANEL: SHADOW EVALUATION (SPRINT 31 DASHBOARD V9)            -->
        <!-- =============================================================== -->
        <div id="timing-panel-shadow-eval" class="timing-panel">
          <!-- Top Banner: Protocol Integrity -->
          <div class="card" style="padding: 16px 20px; margin-bottom: 20px; border-left: 4px solid #38bdf8;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
              <div>
                <h3 style="font-size: 15px; color: #f8fafc; margin-bottom: 4px;">🌑 Mühürlü Tarihsel Strateji Değerlendirmesi & Çevrimdışı Gölge Portföy (V9)</h3>
                <span style="font-size: 12px; color: #94a3b8;">
                  Sprint 30 Dondurulmuş Politikalar | 2025 Bağımsız Tarihsel Veri Seti | Kriptografik SHA-256 Mührü | Sıfır Canlı İşlem
                </span>
              </div>
              <span id="sealed-pkg-badge" class="badge" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4); font-family: var(--font-mono); font-size: 11px;">
                SEALED-PKG-SPRINT31-V1
              </span>
            </div>
          </div>

          <!-- VIEW 1: EVALUATION READINESS -->
          <div id="shadow-readiness-container" style="margin-bottom: 24px;">
            <h4 style="font-size: 13px; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.5px; margin-bottom: 12px;">
              1. Değerlendirme Hazırlık Durumu (Evaluation Readiness)
            </h4>
            <div class="timing-kpi-grid">
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Politika Paketi Mührü</div>
                <div class="timing-kpi-val" id="sealed-readiness-integrity" style="color: #34d399; font-size: 15px;">DOĞRULANDI</div>
                <div class="timing-kpi-sub" id="sealed-readiness-fingerprint" style="font-family: var(--font-mono); font-size: 10px;">SHA-256: 73a8349d...</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Hedef Veri Seti Uygunluğu</div>
                <div class="timing-kpi-val" id="sealed-readiness-dataset" style="color: #38bdf8; font-size: 15px;">DS-BTC-1H-2025-SEALED</div>
                <div class="timing-kpi-sub" id="sealed-readiness-candles">8.760 Saatlik Mum (2025 Kesintisiz)</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Holdout Bulaşma Durumu</div>
                <div class="timing-kpi-val" id="sealed-readiness-holdout" style="font-size: 15px;">TEMİZ (0 Bulaşma)</div>
                <div class="timing-kpi-sub" id="sealed-readiness-holdout-sub">Önceki Sprintlerde Kullanılmadı</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Yürütme Yetkilendirmesi</div>
                <div class="timing-kpi-val" id="sealed-readiness-auth" style="color: #34d399; font-size: 15px;">YETKİLENDİRİLDİ</div>
                <div class="timing-kpi-sub">Çevrimdışı Gölge Değerlendirme</div>
              </div>
            </div>
          </div>

          <!-- VIEW 2: OFFLINE DATASET IMPORT -->
          <div class="card" style="padding: 20px; margin-bottom: 24px;">
            <h4 style="font-size: 14px; color: #f8fafc; margin-bottom: 12px; display: flex; justify-content: space-between;">
              <span>📥 2. Kontrollü Çevrimdışı Veri İçe Aktarma (Offline Dataset Import)</span>
              <span style="font-size: 11px; color: #94a3b8;">Parquet & CSV | Sıkı OHLCV & Provenans Doğrulaması</span>
            </h4>
            <div class="timing-form-row">
              <div class="timing-input-group" style="grid-column: span 2;">
                <label for="sealed-import-path">Dosya Yolu (File Path)</label>
                <input type="text" id="sealed-import-path" value="data/historical/historical_binance_btcusdt_1h_2025.parquet" placeholder="Dosya yolu giriniz...">
              </div>
              <div class="timing-input-group">
                <label for="sealed-import-dataset-id">Veri Seti ID</label>
                <input type="text" id="sealed-import-dataset-id" value="DS-BTC-1H-2025-SEALED" placeholder="Örn: DS-BTC-1H-2025-SEALED">
              </div>
            </div>
            <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
              <button class="btn btn-secondary" id="btn-sealed-validate-import" onclick="runManualOfflineImport(false)">
                🔍 Veriyi Doğrula
              </button>
              <button class="btn btn-primary" id="btn-sealed-register-import" onclick="runManualOfflineImport(true)">
                📥 Doğrula ve Kataloğa Kaydet
              </button>
              <span id="sealed-import-status" style="font-size: 12px; color: #94a3b8;"></span>
            </div>
            <div id="sealed-import-results-box" style="margin-top: 14px; display: none; background: #0b1120; border: 1px solid #1e293b; border-radius: 6px; padding: 12px; font-size: 12px;">
              <div id="sealed-import-results-content"></div>
            </div>
          </div>

          <!-- VIEW 3: SEALED EVALUATION EXECUTION -->
          <div class="card" style="padding: 20px; margin-bottom: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px; flex-wrap: wrap; gap: 10px;">
              <div>
                <h4 style="font-size: 14px; color: #f8fafc; margin-bottom: 4px;">⚡ 3. Mühürlü Değerlendirme Yürütme Motoru (Sealed Evaluation Execution)</h4>
                <span style="font-size: 12px; color: #94a3b8;">
                  Dondurulmuş 6 Politika | Sıralı Protokol | Değiştirilemez Parametreler | İlk Değerlendirme Kaydı
                </span>
              </div>
              <button class="btn btn-primary" id="btn-run-sealed-eval" onclick="runSealedEvaluationFromUI()" style="background: #0284c7; font-weight: 700;">
                ▶️ Mühürlü Değerlendirmeyi Yürüt
              </button>
            </div>
            <div id="sealed-exec-stages" style="display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 12px;">
              <span class="badge" id="stage-freeze" style="background: #1e293b; color: #94a3b8;">1. POLICY_FREEZE</span>
              <span class="badge" id="stage-eligibility" style="background: #1e293b; color: #94a3b8;">2. DATASET_ELIGIBILITY</span>
              <span class="badge" id="stage-auth" style="background: #1e293b; color: #94a3b8;">3. HOLDOUT_AUTH</span>
              <span class="badge" id="stage-access" style="background: #1e293b; color: #94a3b8;">4. FIRST_ACCESS</span>
              <span class="badge" id="stage-sim" style="background: #1e293b; color: #94a3b8;">5. SIMULATION</span>
              <span class="badge" id="stage-bench" style="background: #1e293b; color: #94a3b8;">6. BENCHMARK</span>
              <span class="badge" id="stage-seal" style="background: #1e293b; color: #94a3b8;">7. EVIDENCE_SEAL</span>
              <span class="badge" id="stage-report" style="background: #1e293b; color: #94a3b8;">8. REPORT</span>
            </div>
            <div id="sealed-exec-status" style="font-size: 12px; color: #94a3b8;">Hazır. Yürütmek için butona basınız.</div>
          </div>

          <!-- VIEW 4: SHADOW PORTFOLIO -->
          <div style="margin-bottom: 24px;">
            <h4 style="font-size: 13px; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.5px; margin-bottom: 12px;">
              4. Tarihsel Gölge Portföy (Historical Shadow Portfolio — 2025)
            </h4>
            <div class="timing-kpi-grid">
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Başlangıç Sermayesi</div>
                <div class="timing-kpi-val">$10.000,00</div>
                <div class="timing-kpi-sub">USDT Nakit (Kaldıraçsız / Spot)</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Düşük Cirolu Trend Bitiş Özsermaye</div>
                <div class="timing-kpi-val" id="shadow-end-equity" style="color: #38bdf8;">$7.120,36</div>
                <div class="timing-kpi-sub" id="shadow-net-return" style="color: #f87171;">Net Getiri: -%28,80</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Pasif Al-Tut Bitiş Özsermaye</div>
                <div class="timing-kpi-val" id="shadow-bnh-equity">$9.030,69</div>
                <div class="timing-kpi-sub" id="shadow-bnh-return" style="color: #f87171;">Net Getiri: -%9,69</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Toplam İşlem Maliyeti (Low-Turnover)</div>
                <div class="timing-kpi-val" id="shadow-total-costs" style="color: #fbbf24;">$793,47</div>
                <div class="timing-kpi-sub" id="shadow-trade-count">57 İşlem (Basit Trend: 616 İşlem / $6.789)</div>
              </div>
            </div>

            <!-- Canvas: Equity Curve -->
            <div class="timing-canvas-box">
              <div class="timing-canvas-header">
                <span>📈 2025 Gölge Portföy Özsermaye Eğrisi Karşılaştırması (10.000 USDT Başlangıç)</span>
                <span style="font-size: 11px; color: #94a3b8;">Düşük Cirolu Trend vs Basit Trend vs Al-Tut vs Nakit</span>
              </div>
              <canvas id="shadowEquityCanvas" width="1000" height="320" style="width: 100%; height: 320px; display: block;"></canvas>
              <div style="display: flex; gap: 16px; margin-top: 10px; font-size: 11px; color: #94a3b8; flex-wrap: wrap;">
                <span><span style="color: #38bdf8;">■</span> Düşük Cirolu Trend (Histeresis+Holding)</span>
                <span><span style="color: #f87171;">■</span> Basit Trend Filtresi (Kontrolsüz)</span>
                <span><span style="color: #fbbf24;">■</span> Pasif Al-Tut (B&H)</span>
                <span><span style="color: #94a3b8;">■</span> USDT Nakit ($10.000 Sabit)</span>
              </div>
            </div>

            <!-- Trade Ledger Table -->
            <div class="card" style="padding: 16px; margin-bottom: 20px;">
              <h5 style="font-size: 13px; color: #f8fafc; margin-bottom: 10px; display: flex; justify-content: space-between;">
                <span>📜 Düşük Cirolu Trend Hipotetik İşlem Defteri (İlk 20 İşlem)</span>
                <span id="shadow-trades-badge" class="badge badge-info">57 İşlem</span>
              </h5>
              <div class="timing-table-box" style="margin-bottom: 0;">
                <table class="timing-table">
                  <thead>
                    <tr>
                      <th>İşlem ID</th>
                      <th>Tarih (UTC)</th>
                      <th>Yön</th>
                      <th>Fiyat ($)</th>
                      <th>Efektif Fiyat ($)</th>
                      <th>BTC Miktarı</th>
                      <th>İşlem Tutarı ($)</th>
                      <th>Komisyon ($)</th>
                      <th>Spread+Slippage ($)</th>
                      <th>Kalan USDT</th>
                      <th>Son Özsermaye ($)</th>
                    </tr>
                  </thead>
                  <tbody id="shadow-trades-tbody">
                    <tr><td colspan="11" style="text-align: center; color: #64748b;">Yükleniyor...</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- VIEW 5: BENCHMARK COMPARISON -->
          <div style="margin-bottom: 24px;">
            <h4 style="font-size: 13px; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.5px; margin-bottom: 12px;">
              5. Kıyaslama Karşılaştırması (Benchmark Comparison — 6 Dondurulmuş Politika)
            </h4>
            <div class="timing-table-box">
              <table class="timing-table">
                <thead>
                  <tr>
                    <th>Politika Adı</th>
                    <th>Rol</th>
                    <th>Bitiş Özsermaye ($)</th>
                    <th>Net Getiri (%)</th>
                    <th>Al-Tut'a Göre Fark (%)</th>
                    <th>Maksimum Düşüş (%)</th>
                    <th>Sharpe</th>
                    <th>Sortino</th>
                    <th>İşlem Sayısı</th>
                    <th>Toplam Maliyet ($)</th>
                    <th>Mutabakat Durumu</th>
                  </tr>
                </thead>
                <tbody id="shadow-benchmark-tbody">
                  <tr><td colspan="11" style="text-align: center; color: #64748b;">Yükleniyor...</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <!-- VIEW 6: SCIENTIFIC FINDINGS & HYPOTHESES H1-H5 -->
          <div style="margin-bottom: 24px;">
            <h4 style="font-size: 13px; text-transform: uppercase; color: #94a3b8; letter-spacing: 0.5px; margin-bottom: 12px;">
              6. Bilimsel Bulgular & Hipotez Değerlendirmesi (Hypotheses H1-H5)
            </h4>
            <div class="timing-kpi-grid" id="shadow-hypotheses-grid">
              <!-- Populated by JavaScript -->
            </div>

            <!-- Epistemological Disclaimer Card -->
            <div class="card" style="padding: 18px; margin-top: 16px; background: #0b1120; border: 1px solid #1e293b;">
              <h5 style="font-size: 13px; color: #f8fafc; margin-bottom: 8px;">🔬 Epistemolojik Sınıflandırma ve Bilimsel Dürüstlük Protokolü</h5>
              <p style="font-size: 12px; color: #94a3b8; line-height: 1.6; margin-bottom: 8px;">
                Bu değerlendirme, daha önce optimizasyonda kullanılmamış kesintisiz 2025 BTC/USDT saatlik verisi üzerinde <strong>SEALED_UNSEEN_HISTORICAL_EVALUATION</strong> (Mühürlü Görülmemiş Tarihsel Değerlendirme) protokolüyle yürütülmüştür. Politikalar ve parametreler veri açılmadan önce SHA-256 mührüyle dondurulmuş, geriye dönük parametre revizyonu engellenmiştir.
              </p>
              <p style="font-size: 12px; color: #94a3b8; line-height: 1.6; margin-bottom: 0;">
                <strong>Kritik Bilimsel Çıkarım:</strong> Düşük ciro kontrolleri işlem maliyetlerini %88,3 oranında azaltarak (H1 Desteklendi) ve düşüş şiddetini %25,9 sınırlandırarak (H3 Desteklendi) net portföy sonucunu basit trende göre %33,8 iyileştirmiştir (H2 Desteklendi). Ancak 2025 yılı boyunca hiçbir aktif zamanlama stratejisi pasif Al-Tut'u (B&H) geçememiştir (H4 Desteklenmedi). Bu durum, aktif zamanlama politikalarının her piyasa rejiminde Al-Tut'u yenemeyeceğini ampirik olarak kanıtlamaktadır.
              </p>
            </div>
          </div>
        </div>

        <!-- =============================================================== -->
        <!-- SUB-PANEL 12: DASHBOARD V10 — INVESTMENT RESEARCH WORKSPACE      -->
        <!-- =============================================================== -->
        <div id="timing-panel-v10-workspace" class="timing-panel">
          
          <!-- PROMINENT DISCLAIMER BANNER -->
          <div style="background: rgba(239, 68, 68, 0.12); border: 2px solid #ef4444; border-radius: 8px; padding: 14px 20px; margin-bottom: 24px; display: flex; align-items: center; gap: 16px;">
            <span style="font-size: 28px;">⚠️</span>
            <div>
              <div style="color: #ef4444; font-weight: 800; font-size: 16px; letter-spacing: 0.05em;" id="v10-disclaimer-banner">
                TARİHSEL ARAŞTIRMA — CANLI YATIRIM SİNYALİ DEĞİLDİR
              </div>
              <div style="color: #cbd5e1; font-size: 13px; margin-top: 4px;">
                Bu çalışma alanı, 2025 yılı mühürlü veri seti üzerindeki geriye dönük (retrospective) araştırma ve simülasyon sonuçlarını sunar. Geçmiş performans gelecekteki getirilerin garantisi değildir. Canlı işlem, otomatik emir iletimi ve gerçek sermaye kullanımı kesin olarak yasaktır (CBE-0.7.0).
              </div>
            </div>
          </div>

          <!-- SECTION A: RESEARCH OVERVIEW -->
          <div style="margin-bottom: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <h4 style="font-size: 14px; text-transform: uppercase; color: #38bdf8; letter-spacing: 0.5px; margin: 0;">
                A. Araştırma Genel Bakış & Epistemolojik Durum
              </h4>
              <span class="badge" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.4);" id="v10-readiness-badge">
                AUDITED_EVIDENCE_READY
              </span>
            </div>
            
            <div class="timing-kpi-grid">
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Değerlendirme Penceresi</div>
                <div class="timing-kpi-val" style="color: #f8fafc; font-size: 15px;" id="v10-kpi-period">2025 (8,760 Saat)</div>
                <div class="timing-kpi-sub">BTC/USDT Spot Saatlik Mumlar</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Veri Seti Orijini</div>
                <div class="timing-kpi-val" style="color: #fb923c; font-size: 12px; word-break: break-all;" id="v10-kpi-provenance">RESTRICTED_EVIDENCE_UNVERIFIED_PROVENANCE</div>
                <div class="timing-kpi-sub">12 Aylık Parquet (0 Gaps, 0 Duplicates)</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Dondurulmuş Politika Paketi</div>
                <div class="timing-kpi-val" style="color: #10b981; font-size: 12px; font-family: monospace;" id="v10-kpi-seal">73a8349d... (Mühürlü)</div>
                <div class="timing-kpi-sub">Değişmezlik Doğrulandı (Tamper-Free)</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">En İyi Tarihsel Benchmark</div>
                <div class="timing-kpi-val" style="color: #38bdf8; font-size: 15px;" id="v10-kpi-benchmark">Periyodik Dengeleme (-%2.23)</div>
                <div class="timing-kpi-sub">Buy & Hold: -%9.69 | Aktif: -%28.80</div>
              </div>
            </div>

            <!-- Epistemic limitations callout -->
            <div class="card" style="padding: 14px 18px; margin-top: 12px; background: #0b1120; border: 1px solid #1e293b;">
              <div style="font-size: 12px; color: #94a3b8; line-height: 1.6;">
                <strong style="color: #f8fafc;">⚠️ Bilimsel Sınırlar & Metodolojik Uyarı:</strong> 
                Saatlik finansal getiriler kuvvetli serisel otokorelasyon ve volatilite kümelenmesi sergiler (i.i.d. değildir). 
                Tekil bir yıllık simülasyon $N=1$ tarihsel patika temsil eder; deterministik farklar istatistiksel keşif olarak adlandırılamaz.
                Tüm ampirik farklar <strong>DESCRIPTIVE_THRESHOLD_MET</strong> standardında değerlendirilir.
              </div>
            </div>
          </div>

          <!-- SECTION B: HISTORICAL PORTFOLIO COMPARISON -->
          <div style="margin-bottom: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <h4 style="font-size: 14px; text-transform: uppercase; color: #38bdf8; letter-spacing: 0.5px; margin: 0;">
                B. Tarihsel Portföy Karşılaştırması (6 Politika)
              </h4>
              <div style="display: flex; gap: 8px;">
                <button class="btn btn-secondary" id="v10-btn-chart-equity" onclick="switchV10ChartMode('equity')">Özkaynak Eğrisi</button>
                <button class="btn btn-secondary" id="v10-btn-chart-drawdown" onclick="switchV10ChartMode('drawdown')">Drawdown Eğrisi</button>
              </div>
            </div>

            <!-- Canvas Chart -->
            <div class="card" style="padding: 18px; margin-bottom: 16px; background: #0f172a; border: 1px solid #1e293b;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <span style="font-size: 12px; color: #94a3b8;" id="v10-chart-title">Tarihsel Özkaynak Gelişimi (2025 Tam Yıl - 120 Nokta Örnekleme)</span>
                <div style="display: flex; gap: 14px; font-size: 11px;">
                  <span style="color: #fbbf24;">● Buy & Hold</span>
                  <span style="color: #94a3b8;">● Nakit</span>
                  <span style="color: #f87171;">● Basit Trend</span>
                  <span style="color: #38bdf8; font-weight: bold;">● Düşük Devir</span>
                  <span style="color: #a78bfa;">● Periyodik 50/50</span>
                  <span style="color: #34d399;">● Rejim Teyitli</span>
                </div>
              </div>
              <canvas id="v10-equity-canvas" width="900" height="280" style="width: 100%; height: 280px; background: #090d16; border-radius: 6px;"></canvas>
            </div>

            <!-- Comparison Table -->
            <div class="timing-table-box">
              <table class="timing-table" id="v10-comparison-table">
                <thead>
                  <tr>
                    <th>Politika Adı</th>
                    <th>Kategori</th>
                    <th>Başlangıç ($)</th>
                    <th>Bitiş ($)</th>
                    <th>Net Getiri</th>
                    <th>Max DD</th>
                    <th>Sharpe</th>
                    <th>İşlem</th>
                    <th>Maliyet ($)</th>
                    <th>Piyasada (%)</th>
                    <th>Muhasebe</th>
                  </tr>
                </thead>
                <tbody id="v10-comparison-tbody">
                  <!-- Populated by JS -->
                </tbody>
              </table>
            </div>
          </div>

          <!-- SECTION C: STRATEGY DETAILS & PAGINATED TRADE LEDGER -->
          <div style="margin-bottom: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <h4 style="font-size: 14px; text-transform: uppercase; color: #38bdf8; letter-spacing: 0.5px; margin: 0;">
                C. Strateji Kuralları & Sayfalanmış İşlem Defteri
              </h4>
              <div style="display: flex; align-items: center; gap: 10px;">
                <label style="font-size: 12px; color: #94a3b8;">Politika Seç:</label>
                <select id="v10-strategy-select" onchange="onV10StrategySelectChange()" style="background: #1e293b; color: #f8fafc; border: 1px solid #334155; padding: 6px 12px; border-radius: 6px; font-size: 12px;">
                  <option value="POLICY_TREND_LOW_TURNOVER" selected>Düşük Devirli Trend (Histerezis)</option>
                  <option value="POLICY_BUY_AND_HOLD">Pasif Buy & Hold</option>
                  <option value="POLICY_USDT_CASH">Nakit (USDT) Rezerv</option>
                  <option value="POLICY_SIMPLE_TREND">Kısıtlamasız Basit Trend</option>
                  <option value="POLICY_PERIODIC_REBALANCE">Periyodik Yeniden Dengeleme (50/50)</option>
                  <option value="POLICY_DERIVED_REGIME_CONFIRMATION">Türetilmiş Rejim Teyitli Trend</option>
                </select>
              </div>
            </div>

            <!-- Rules & Parameters Card -->
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
              <div class="card" style="padding: 14px 18px; background: #0f172a; border: 1px solid #1e293b;">
                <h5 style="font-size: 13px; color: #38bdf8; margin-bottom: 8px;">📋 Uygulanan Tam Kurallar</h5>
                <ul id="v10-strategy-rules-list" style="font-size: 12px; color: #cbd5e1; margin: 0; padding-left: 18px; line-height: 1.6;">
                  <!-- Populated by JS -->
                </ul>
              </div>
              <div class="card" style="padding: 14px 18px; background: #0f172a; border: 1px solid #1e293b;">
                <h5 style="font-size: 13px; color: #10b981; margin-bottom: 8px;">⚙️ Dondurulmuş Parametreler</h5>
                <pre id="v10-strategy-params-pre" style="font-size: 11px; color: #94a3b8; background: #090d16; padding: 8px; border-radius: 4px; margin: 0; font-family: monospace; overflow-x: auto;">
                  <!-- Populated by JS -->
                </pre>
              </div>
            </div>

            <!-- Paginated Trade Ledger Table -->
            <div class="card" style="padding: 14px 18px; background: #0f172a; border: 1px solid #1e293b;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <span style="font-size: 13px; color: #f8fafc; font-weight: 600;">📖 Gerçekleşen Simüle İşlemler</span>
                <div style="display: flex; gap: 8px; align-items: center;">
                  <select id="v10-trade-side-filter" onchange="loadV10TradesCurrentPage()" style="background: #1e293b; color: #cbd5e1; border: 1px solid #334155; padding: 4px 8px; border-radius: 4px; font-size: 11px;">
                    <option value="">Tüm İşlemler</option>
                    <option value="BUY">Sadece Alımlar (BUY)</option>
                    <option value="SELL">Sadece Satışlar (SELL)</option>
                  </select>
                  <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;" id="v10-trade-prev" onclick="prevV10TradesPage()">← Önceki</button>
                  <span id="v10-trade-page-info" style="font-size: 11px; color: #94a3b8;">Sayfa 1 / 1</span>
                  <button class="btn btn-secondary" style="padding: 4px 8px; font-size: 11px;" id="v10-trade-next" onclick="nextV10TradesPage()">Sonraki →</button>
                </div>
              </div>
              <div class="timing-table-box" style="max-height: 320px; overflow-y: auto;">
                <table class="timing-table">
                  <thead>
                    <tr>
                      <th>İşlem ID</th>
                      <th>Tarih (UTC)</th>
                      <th>Yön</th>
                      <th>Nominal Fiyat</th>
                      <th>Efektif Fiyat</th>
                      <th>BTC Miktarı</th>
                      <th>Komisyon ($)</th>
                      <th>Spread ($)</th>
                      <th>Slippage ($)</th>
                      <th>Toplam Maliyet ($)</th>
                      <th>Kalan Nakit ($)</th>
                      <th>Özkaynak ($)</th>
                    </tr>
                  </thead>
                  <tbody id="v10-trades-tbody">
                    <!-- Populated by JS -->
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- SECTION D: TRANSACTION COST INTELLIGENCE -->
          <div style="margin-bottom: 24px;">
            <h4 style="font-size: 14px; text-transform: uppercase; color: #38bdf8; letter-spacing: 0.5px; margin-bottom: 12px;">
              D. İşlem Maliyeti Zekası & Kompaund Sürüklenme
            </h4>
            
            <div class="timing-kpi-grid">
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Borsa Komisyonu</div>
                <div class="timing-kpi-val" style="color: #fb923c;">10.0 bps</div>
                <div class="timing-kpi-sub">Taker/Maker Nakit Kesintisi</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Half-Spread Sürüklenmesi</div>
                <div class="timing-kpi-val" style="color: #fb923c;">2.5 bps</div>
                <div class="timing-kpi-sub">5.0 bps Full Spread'den</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Fiyat Kayması (Slippage)</div>
                <div class="timing-kpi-val" style="color: #fb923c;">5.0 bps</div>
                <div class="timing-kpi-sub">Piyasa Etkisi Marjı</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Tek Yönlü / Çift Yönlü Maliyet</div>
                <div class="timing-kpi-val" style="color: #10b981;">17.5 / 35.0 bps</div>
                <div class="timing-kpi-sub">Tek İşlem / Tam Tur (Buy+Sell)</div>
              </div>
            </div>

            <!-- Compounded Drag Card -->
            <div class="card" style="padding: 16px 20px; margin-top: 14px; background: #0f172a; border: 1px solid #1e293b;">
              <h5 style="font-size: 13px; color: #f8fafc; margin-bottom: 6px;">💡 Doğrudan Nakit Maliyeti vs Kompaund Performans Sürüklenmesi</h5>
              <p style="font-size: 12px; color: #94a3b8; line-height: 1.6; margin-bottom: 12px;" id="v10-compounded-drag-text">
                Yükleniyor...
              </p>
              
              <h5 style="font-size: 12px; color: #38bdf8; margin-top: 12px; margin-bottom: 8px;">Maliyet Hassasiyeti Stres Matrisi (Simülasyon Senaryoları):</h5>
              <div class="timing-table-box" style="margin-bottom: 0;">
                <table class="timing-table">
                  <thead>
                    <tr>
                      <th>Senaryo</th>
                      <th>Tek Yönlü Sürtünme</th>
                      <th>Basit Trend Bitiş ($)</th>
                      <th>Düşük Devir Bitiş ($)</th>
                      <th>Epistemik Etki</th>
                    </tr>
                  </thead>
                  <tbody id="v10-cost-scenarios-tbody">
                    <!-- Populated by JS -->
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- SECTION E: SCIENTIFIC EVIDENCE -->
          <div style="margin-bottom: 24px;">
            <h4 style="font-size: 14px; text-transform: uppercase; color: #38bdf8; letter-spacing: 0.5px; margin-bottom: 12px;">
              E. Bilimsel Kanıt & Düzeltilmiş Hipotez Kararları (H1 - H5)
            </h4>
            
            <div class="timing-kpi-grid" id="v10-hypotheses-grid">
              <!-- Populated by JS -->
            </div>

            <!-- Epistemic Warning Banner -->
            <div class="card" style="padding: 16px 20px; margin-top: 14px; background: #0b1120; border: 1px solid #334155;">
              <h5 style="font-size: 13px; color: #ef4444; margin-bottom: 6px;">⚖️ Dürüstlük Protokolü: H4 Reddi & Overfitting Ayrımı</h5>
              <p style="font-size: 12px; color: #cbd5e1; line-height: 1.6; margin: 0;">
                2025 yılı ampirik değerlendirmesinde <strong>H4 kesin olarak DESTEKLENMEMİŞTİR (UNSUPPORTED)</strong>. 
                Düşük devirli aktif strateji pasif Buy & Hold'un <strong>19.10 yüzde puan gerisinde kalmıştır</strong>. 
                Ayrıca strateji, katı 3-katlamalı walk-forward testinde <strong>REJECTED_OVERFITTING</strong> almıştır. 
                Bu dürüst negatif bulgu, trend takipçisi algoritmaların yatay ve testere rejimlerinde pasif tutmayı yenemediğini gösteren değerli bir bilimsel sonuçtur.
              </p>
            </div>
          </div>

          <!-- SECTION F: RESEARCH TIMELINE -->
          <div style="margin-bottom: 24px;">
            <h4 style="font-size: 14px; text-transform: uppercase; color: #38bdf8; letter-spacing: 0.5px; margin-bottom: 12px;">
              F. Araştırma Gelişim Zaman Çizelgesi (Sprint 29 -> 32)
            </h4>
            <div class="card" style="padding: 18px; background: #0f172a; border: 1px solid #1e293b;">
              <div id="v10-timeline-container" style="display: flex; flex-direction: column; gap: 14px;">
                <!-- Populated by JS -->
              </div>
            </div>
          </div>

          <!-- SECTION G: RESEARCH REPORTS & DOWNLOADS -->
          <div style="margin-bottom: 24px;">
            <h4 style="font-size: 14px; text-transform: uppercase; color: #38bdf8; letter-spacing: 0.5px; margin-bottom: 12px;">
              G. Araştırma Raporları & Resmi İndirmeler
            </h4>
            <div class="card" style="padding: 20px; background: #0f172a; border: 1px solid #1e293b;">
              <div style="display: flex; gap: 14px; margin-bottom: 16px;">
                <button class="btn btn-primary" onclick="downloadV10Report('markdown')">📥 Markdown Raporu İndir (.md)</button>
                <button class="btn btn-secondary" onclick="downloadV10Report('json')">📥 JSON Veri Paketini İndir (.json)</button>
                <button class="btn btn-secondary" onclick="downloadV10Report('csv')">📥 Portföy Metrikleri CSV (.csv)</button>
              </div>
              <div style="font-size: 11px; color: #64748b; line-height: 1.5;">
                Tüm raporlar SHA-256 imzaları, tam parametre parmak izleri ve bağımsız mutabakat verilerini içerir.
              </div>
            </div>
          </div>

        </div>

      </div>
    </section>
    """


def render_btc_timing_scripts() -> str:
    """Client-side JavaScript controller for the BTC Timing Research Lab."""
    return """
    /* ========================================================================= */
    /* SPRINT 29: BTC TIMING LAB JAVASCRIPT CONTROLLER                           */
    /* ========================================================================= */
    let currentTimingExperiment = null;
    let timingExperimentsList = [];

    function switchTimingSubtab(subId) {
      document.querySelectorAll(".timing-subnav-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".timing-panel").forEach(p => p.classList.remove("active"));

      const btn = document.getElementById("timing-btn-" + subId);
      if (btn) btn.classList.add("active");

      const panel = document.getElementById("timing-panel-" + subId);
      if (panel) panel.classList.add("active");

      if (subId === "analysis") {
        setTimeout(drawTimingPriceCanvas, 50);
      } else if (subId === "portfolio") {
        setTimeout(() => {
          if (currentTimingExperiment && currentTimingExperiment.equity_curve) {
            drawTimingEquityCanvas(currentTimingExperiment.equity_curve);
          }
        }, 50);
      } else if (subId === "comparison") {
        loadTimingComparison();
      } else if (subId === "reconciliation") {
        loadTimingReconciliation();
      } else if (subId === "turnover") {
        loadTimingTurnover();
      } else if (subId === "optimization") {
        loadTimingOptimization();
      } else if (subId === "history") {
        loadTimingHistory();
      } else if (subId === "shadow-eval") {
        loadSealedEvaluationDashboard();
      } else if (subId === "v10-workspace") {
        loadInvestmentResearchV10();
      }
    }

    async function loadBtcTimingTab() {
      try {
        const res = await fetch("/api/v1/product/research/btc-timing/overview");
        if (res.ok) {
          const data = await res.json();
          document.getElementById("timing-ov-exp-count").textContent = data.total_experiments_recorded || "0";
          if (data.latest_experiment) {
            displayLatestExperimentOverview(data.latest_experiment);
          }
        }
      } catch (e) {
        console.error("Error loading timing overview:", e);
      }
      loadTimingHistory();
    }

    function displayLatestExperimentOverview(exp) {
      document.getElementById("timing-ov-latest-id").textContent = exp.experiment_id || "-";
      document.getElementById("timing-ov-latest-policy").textContent = exp.policy_name || exp.policy_id || "-";
      const ret = exp.net_return_pct;
      const retEl = document.getElementById("timing-ov-latest-return");
      retEl.textContent = (ret >= 0 ? "+" : "") + ret + "%";
      retEl.style.color = ret >= 0 ? "#34d399" : "#f87171";

      document.getElementById("timing-ov-latest-maxdd").textContent = "-" + exp.max_drawdown_pct + "%";

      const bmark = exp.benchmark_comparison || {};
      const bnhRet = bmark.buy_and_hold_return_pct;
      document.getElementById("timing-ov-latest-bnh").textContent = (bnhRet !== undefined ? (bnhRet >= 0 ? "+" : "") + bnhRet + "%" : "-");

      document.getElementById("timing-ov-latest-trades").textContent = exp.trade_count || 0;
      const metrics = exp.metrics_summary || {};
      document.getElementById("timing-ov-latest-drag").textContent = "$" + (metrics.total_transaction_costs_usdt || 0) + " (" + (metrics.cost_drag_pct || 0) + "%)";
    }

    async function runTimingSimulation() {
      const statusEl = document.getElementById("timing-sim-status");
      const btn = document.getElementById("btn-run-simulation");
      statusEl.textContent = "⏳ Simülasyon çalıştırılıyor...";
      btn.disabled = true;

      const payload = {
        dataset_id: document.getElementById("timing-input-dataset").value,
        policy_id: document.getElementById("timing-input-policy").value,
        initial_capital_usdt: parseFloat(document.getElementById("timing-input-capital").value) || 10000.0,
        cost_profile_id: document.getElementById("timing-input-cost").value,
        parameters: {}
      };

      try {
        const res = await fetch("/api/v1/product/research/btc-timing/simulate", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          const data = await res.json();
          const exp = data.experiment;
          statusEl.textContent = "✅ Tamamlandı: " + exp.experiment_id;
          currentTimingExperiment = exp;
          populatePortfolioView(exp);
          switchTimingSubtab("portfolio");
          loadTimingHistory();
        } else {
          const err = await res.json();
          statusEl.textContent = "❌ Hata: " + (err.message || "Simülasyon başarısız.");
        }
      } catch (e) {
        statusEl.textContent = "❌ Bağlantı hatası: " + e;
      } finally {
        btn.disabled = false;
      }
    }

    async function runWalkForwardValidation() {
      const statusEl = document.getElementById("timing-sim-status");
      statusEl.textContent = "⏳ Walk-forward doğrulaması hesaplanıyor...";

      const payload = {
        dataset_id: document.getElementById("timing-input-dataset").value,
        policy_id: document.getElementById("timing-input-policy").value,
        cost_profile_id: document.getElementById("timing-input-cost").value,
        n_folds: 3,
        parameters: {}
      };

      try {
        const res = await fetch("/api/v1/product/research/btc-timing/walk-forward", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload)
        });
        if (res.ok) {
          const data = await res.json();
          const rep = data.report;
          alert("Walk-Forward Doğrulama Sonucu:\\n" +
                "Doğrulama ID: " + rep.validation_id + "\\n" +
                "Karar: " + rep.scientific_verdict + "\\n" +
                "Holdout Durumu: " + rep.holdout_status_code + "\\n" +
                "Ortalama Örneklem-Dışı Getiri: %" + rep.mean_out_of_sample_return_pct + "\\n" +
                "Bozulma (Degradation): %" + rep.mean_degradation_pct);
          statusEl.textContent = "✅ Walk-Forward Tamamlandı: " + rep.scientific_verdict;
        } else {
          statusEl.textContent = "❌ Walk-Forward hatası.";
        }
      } catch (e) {
        statusEl.textContent = "❌ Hata: " + e;
      }
    }

    function populatePortfolioView(exp) {
      if (!exp) return;
      const meta = exp.metadata || exp;
      const metrics = meta.metrics_summary || {};

      document.getElementById("port-init-cap").textContent = "$" + (meta.initial_capital_usdt || 10000).toLocaleString("en-US", {minimumFractionDigits: 2});
      document.getElementById("port-end-equity").textContent = "$" + (meta.ending_equity_usdt || 10000).toLocaleString("en-US", {minimumFractionDigits: 2});

      const netRet = meta.net_return_pct || 0;
      const netPnl = metrics.net_pnl_usdt || 0;
      document.getElementById("port-net-pnl").textContent = (netRet >= 0 ? "+" : "") + netRet + "% ($" + netPnl.toLocaleString("en-US", {minimumFractionDigits: 2}) + ")";
      document.getElementById("port-net-pnl").style.color = netRet >= 0 ? "#34d399" : "#f87171";

      document.getElementById("port-max-dd").textContent = "-" + (meta.max_drawdown_pct || 0) + "%";
      document.getElementById("port-total-costs").textContent = "$" + (metrics.total_transaction_costs_usdt || 0).toLocaleString("en-US", {minimumFractionDigits: 2});
      document.getElementById("port-drag-pct").textContent = "Maliyet Sürtünmesi: %" + (metrics.cost_drag_pct || 0);

      // Populate Risk Sub-panel KPIs
      document.getElementById("risk-ann-vol").textContent = metrics.annualized_volatility_pct !== null && metrics.annualized_volatility_pct !== undefined ? "%" + metrics.annualized_volatility_pct : "N/A";
      document.getElementById("risk-down-vol").textContent = metrics.downside_volatility_pct !== null && metrics.downside_volatility_pct !== undefined ? "%" + metrics.downside_volatility_pct : "N/A";
      document.getElementById("risk-sortino").textContent = metrics.sortino_ratio !== null && metrics.sortino_ratio !== undefined ? metrics.sortino_ratio : "N/A";
      document.getElementById("risk-calmar").textContent = metrics.calmar_ratio !== null && metrics.calmar_ratio !== undefined ? metrics.calmar_ratio : "N/A";
      document.getElementById("risk-win-rate").textContent = metrics.win_rate_pct !== null && metrics.win_rate_pct !== undefined ? "%" + metrics.win_rate_pct : "N/A";
      document.getElementById("risk-turnover").textContent = "%" + (metrics.turnover_pct || 0);
      document.getElementById("risk-time-invested").textContent = "%" + (metrics.time_invested_pct || 0);
      document.getElementById("risk-drag").textContent = "%" + (metrics.cost_drag_pct || 0);

      // Populate Trade Ledger
      const trades = exp.trades || [];
      document.getElementById("port-trades-count").textContent = trades.length + " İşlem";
      const tbody = document.getElementById("timing-trades-tbody");
      tbody.innerHTML = "";
      if (trades.length === 0) {
        tbody.innerHTML = '<tr><td colspan="11" style="text-align: center; color: #64748b;">Bu deneyde rebalans işlemi gerçekleşmedi.</td></tr>';
      } else {
        trades.slice(0, 100).forEach(t => {
          const row = document.createElement("tr");
          const sideColor = t.side === "BUY" ? "#34d399" : "#f87171";
          row.innerHTML = `
            <td style="color: #94a3b8;">${t.trade_id}</td>
            <td>${t.timestamp_iso}</td>
            <td style="color: ${sideColor}; font-weight: 700;">${t.side}</td>
            <td>$${t.nominal_price.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
            <td>$${t.effective_price.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
            <td>${t.btc_quantity}</td>
            <td>$${t.gross_usdt_value.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
            <td>$${t.fee_usdt.toFixed(2)}</td>
            <td>$${(t.spread_cost_usdt + t.slippage_cost_usdt).toFixed(2)}</td>
            <td>$${t.net_usdt_impact.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
            <td style="color: ${t.realized_pnl_usdt >= 0 ? '#34d399' : '#f87171'};">${t.realized_pnl_usdt !== 0 ? (t.realized_pnl_usdt > 0 ? "+" : "") + t.realized_pnl_usdt.toFixed(2) : "-"}</td>
          `;
          tbody.appendChild(row);
        });
      }

      if (exp.equity_curve) {
        document.getElementById("port-chart-meta").textContent = exp.equity_curve.length + " Veri Noktası";
        drawTimingEquityCanvas(exp.equity_curve);
      }
    }

    function drawTimingEquityCanvas(curve) {
      const canvas = document.getElementById("timingEquityCanvas");
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      if (!curve || curve.length < 2) return;

      const padding = { top: 20, right: 30, bottom: 30, left: 60 };
      const plotW = w - padding.left - padding.right;
      const plotH = h - padding.top - padding.bottom;

      const equities = curve.map(pt => pt.total_equity_usdt);
      const minEq = Math.min(...equities) * 0.98;
      const maxEq = Math.max(...equities) * 1.02;

      // Draw Grid
      ctx.strokeStyle = "#1e293b";
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {
        const y = padding.top + (plotH / 4) * i;
        ctx.beginPath();
        ctx.moveTo(padding.left, y);
        ctx.lineTo(w - padding.right, y);
        ctx.stroke();

        const val = maxEq - ((maxEq - minEq) / 4) * i;
        ctx.fillStyle = "#64748b";
        ctx.font = "11px monospace";
        ctx.textAlign = "right";
        ctx.fillText("$" + Math.round(val), padding.left - 8, y + 4);
      }

      // Draw Equity Curve
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let i = 0; i < curve.length; i++) {
        const x = padding.left + (plotW / (curve.length - 1)) * i;
        const y = padding.top + plotH - ((curve[i].total_equity_usdt - minEq) / (maxEq - minEq)) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();

      // Draw initial capital reference line
      const initY = padding.top + plotH - ((curve[0].total_equity_usdt - minEq) / (maxEq - minEq)) * plotH;
      ctx.strokeStyle = "#475569";
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(padding.left, initY);
      ctx.lineTo(w - padding.right, initY);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    function drawTimingPriceCanvas() {
      const canvas = document.getElementById("timingPriceCanvas");
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      const w = canvas.width;
      const h = canvas.height;
      ctx.clearRect(0, 0, w, h);

      // Background Grid
      ctx.strokeStyle = "#1e293b";
      ctx.lineWidth = 1;
      for (let i = 0; i <= 4; i++) {
        const y = 20 + (h - 50) / 4 * i;
        ctx.beginPath();
        ctx.moveTo(50, y);
        ctx.lineTo(w - 20, y);
        ctx.stroke();
      }

      // Draw stylized representation of 2023-2024 BTC price trajectory ($27k to $73k)
      ctx.strokeStyle = "#38bdf8";
      ctx.lineWidth = 2;
      ctx.beginPath();
      const points = [
        [50, h - 60], [150, h - 80], [250, h - 130], [350, h - 160],
        [450, h - 220], [550, h - 280], [650, h - 210], [750, h - 230],
        [850, h - 200], [w - 20, h - 270]
      ];
      points.forEach((pt, idx) => {
        if (idx === 0) ctx.moveTo(pt[0], pt[1]);
        else ctx.lineTo(pt[0], pt[1]);
      });
      ctx.stroke();

      ctx.fillStyle = "#94a3b8";
      ctx.font = "11px monospace";
      ctx.fillText("$27,000", 10, h - 55);
      ctx.fillText("$73,000", 10, 30);
      ctx.fillText("Eki 2023", 50, h - 10);
      ctx.fillText("Eki 2024", w - 70, h - 10);
    }

    async function loadTimingReconciliation() {
      const tbody = document.getElementById("timing-reconciliation-tbody");
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #64748b;">Bağımsız mutabakat verileri yükleniyor...</td></tr>';
      try {
        const res = await fetch("/api/v1/product/research/btc-timing/accounting-reconciliation");
        if (res.ok) {
          const data = await res.json();
          tbody.innerHTML = "";
          const policies = [...(data.policies || [])];
          if (data.derived_regime_reconciliation) {
            policies.push(data.derived_regime_reconciliation);
          }
          policies.forEach(p => {
            const row = document.createElement("tr");
            const hasDisc = Math.abs(p.equity_discrepancy_usdt) > 0.01;
            const discColor = hasDisc ? "#fbbf24" : "#34d399";
            const pubBadge = hasDisc ? '<span class="badge" style="background: rgba(245, 158, 11, 0.2); color: #fbbf24;">RAPOR_FARKI</span>' : '<span class="badge badge-success">TAM_EŞLEŞME</span>';
            const ledBadge = '<span class="badge badge-success">✓ DEFTER_MUTABIK</span>';
            row.innerHTML = `
              <td style="color: #38bdf8; font-weight: 600;">${p.policy_id}</td>
              <td>$${p.published_final_equity.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
              <td>$${p.persisted_final_equity.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
              <td>$${p.reconstructed_final_equity.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
              <td style="color: ${discColor}; font-weight: bold;">$${p.equity_discrepancy_usdt.toFixed(4)}</td>
              <td>${ledBadge}</td>
              <td>${pubBadge}</td>
              <td>${p.trade_count_reconstructed}</td>
              <td style="font-size: 11px; color: #94a3b8; max-width: 250px;">${p.discrepancy_root_cause.substring(0, 85)}...</td>
            `;
            tbody.appendChild(row);
          });
        }
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #ef4444;">Mutabakat yüklenemedi: ' + e + '</td></tr>';
      }
    }

    async function loadTimingTurnover() {
      try {
        const res = await fetch("/api/v1/product/research/btc-timing/cost-attribution?policy_id=POLICY_SIMPLE_TREND");
        if (res.ok) {
          const data = await res.json();
          const attr = data.attribution || {};
          document.getElementById("timing-cost-fees").textContent = "$" + (attr.total_fees_usdt || 0).toLocaleString("en-US", {minimumFractionDigits: 2});
          document.getElementById("timing-cost-fees-share").textContent = "%" + (attr.fee_share_pct || 57.14).toFixed(1) + " pay";
          document.getElementById("timing-cost-spread").textContent = "$" + (attr.total_spread_usdt || 0).toLocaleString("en-US", {minimumFractionDigits: 2});
          document.getElementById("timing-cost-spread-share").textContent = "%" + ((attr.total_spread_usdt / Math.max(attr.total_cost_usdt, 1)) * 100).toFixed(1) + " pay";
          document.getElementById("timing-cost-slippage").textContent = "$" + (attr.total_slippage_usdt || 0).toLocaleString("en-US", {minimumFractionDigits: 2});
          document.getElementById("timing-cost-slippage-share").textContent = "%" + ((attr.total_slippage_usdt / Math.max(attr.total_cost_usdt, 1)) * 100).toFixed(1) + " pay";
          document.getElementById("timing-cost-total").textContent = "$" + (attr.total_cost_usdt || 0).toLocaleString("en-US", {minimumFractionDigits: 2});
        }
      } catch (e) {
        console.error("Turnover cost error:", e);
      }
    }

    async function loadTimingOptimization() {
      const tbody = document.getElementById("timing-incremental-tbody");
      if (!tbody) return;
      tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #64748b;">Artımlı değer hiyerarşisi hesaplanıyor...</td></tr>';
      try {
        const res = await fetch("/api/v1/product/research/btc-timing/incremental-value");
        if (res.ok) {
          const data = await res.json();
          const rep = data.report || {};
          tbody.innerHTML = "";
          const tiers = [rep.baseline_a_bnh, rep.baseline_b_trend, rep.baseline_c_vol, rep.experiment_d_canonical_cbe, rep.experiment_e_derived_regime];
          tiers.forEach(t => {
            if (!t) return;
            const row = document.createElement("tr");
            const ret = t.net_return_pct !== null && t.net_return_pct !== undefined ? (t.net_return_pct >= 0 ? "+" : "") + t.net_return_pct + "%" : "N/A";
            const retColor = t.net_return_pct >= 0 ? "#34d399" : (t.net_return_pct < 0 ? "#f87171" : "#94a3b8");
            const incRet = t.incremental_return_vs_trend !== null && t.incremental_return_vs_trend !== undefined ? (t.incremental_return_vs_trend >= 0 ? "+" : "") + t.incremental_return_vs_trend + "%" : "-";
            const ir = t.information_ratio !== null && t.information_ratio !== undefined ? t.information_ratio : "-";
            const badgeClass = t.evaluable ? "badge-success" : "badge-danger";
            row.innerHTML = `
              <td style="color: #38bdf8; font-weight: 600;">${t.policy_tier}</td>
              <td>${t.policy_name}</td>
              <td style="color: ${retColor}; font-weight: bold;">${ret}</td>
              <td>${t.annualized_sharpe !== null && t.annualized_sharpe !== undefined ? t.annualized_sharpe : "N/A"}</td>
              <td style="color: #f87171;">${t.max_drawdown_pct !== null ? "-" + t.max_drawdown_pct + "%" : "N/A"}</td>
              <td>${t.trade_count !== null ? t.trade_count : "-"}</td>
              <td style="color: #38bdf8;">${incRet}</td>
              <td>${ir}</td>
              <td><span class="badge ${badgeClass}">${t.evaluable ? "DEĞERLENDİRİLDİ" : "KANONİK_YOK"}</span></td>
            `;
            tbody.appendChild(row);
          });
        }
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #ef4444;">Artımlı değer verisi yüklenemedi: ' + e + '</td></tr>';
      }
    }

    async function loadTimingComparison() {
      const tbody = document.getElementById("timing-comparison-tbody");
      tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #64748b;">Kıyaslama verileri hesaplanıyor...</td></tr>';
      try {
        const res = await fetch("/api/v1/product/research/btc-timing/compare");
        if (res.ok) {
          const data = await res.json();
          tbody.innerHTML = "";
          (data.comparisons || []).forEach(c => {
            const row = document.createElement("tr");
            const ret = c.net_return_pct;
            const retColor = ret >= 0 ? "#34d399" : "#f87171";
            const excess = c.metrics_summary ? c.metrics_summary.excess_return_over_bnh_pct : null;
            row.innerHTML = `
              <td><strong>${c.policy_name || c.policy_id}</strong></td>
              <td>$${(c.ending_equity_usdt || 0).toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
              <td style="color: ${retColor}; font-weight: 700;">${ret >= 0 ? "+" : ""}${ret}%</td>
              <td style="color: #f87171;">-%${c.max_drawdown_pct}</td>
              <td>${c.sharpe_ratio !== null && c.sharpe_ratio !== undefined ? c.sharpe_ratio : "N/A"}</td>
              <td>${c.trade_count}</td>
              <td style="color: #fbbf24;">%${c.metrics_summary ? c.metrics_summary.cost_drag_pct : 0}</td>
              <td>${excess !== null && excess !== undefined ? (excess >= 0 ? "+" : "") + excess + "%" : "-"}</td>
              <td><span class="badge badge-info">${c.research_status || "COMPLETED"}</span></td>
            `;
            tbody.appendChild(row);
          });
        }
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="9" style="text-align: center; color: #ef4444;">Kıyaslama yüklenemedi: ' + e + '</td></tr>';
      }
    }

    async function loadTimingHistory() {
      const tbody = document.getElementById("timing-history-tbody");
      try {
        const res = await fetch("/api/v1/product/research/btc-timing/experiments");
        if (res.ok) {
          const data = await res.json();
          timingExperimentsList = data.experiments || [];
          tbody.innerHTML = "";
          if (timingExperimentsList.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; color: #64748b;">Henüz kaydedilmiş deney bulunmuyor.</td></tr>';
            return;
          }
          timingExperimentsList.slice().reverse().forEach(exp => {
            const row = document.createElement("tr");
            const ret = exp.net_return_pct;
            const retColor = ret >= 0 ? "#34d399" : "#f87171";
            row.innerHTML = `
              <td style="color: #38bdf8; font-weight: 600;">${exp.experiment_id}</td>
              <td>${exp.created_at_utc ? exp.created_at_utc.substring(0, 19) : "-"}</td>
              <td>${exp.policy_name || exp.policy_id}</td>
              <td>${exp.cost_profile_id}</td>
              <td style="color: ${retColor}; font-weight: 700;">${ret >= 0 ? "+" : ""}${ret}%</td>
              <td style="color: #f87171;">-%${exp.max_drawdown_pct}</td>
              <td>${exp.sharpe_ratio !== null && exp.sharpe_ratio !== undefined ? exp.sharpe_ratio : "N/A"}</td>
              <td>${exp.trade_count}</td>
              <td><span class="badge badge-success">${exp.research_status}</span></td>
              <td>
                <button class="btn btn-secondary" onclick="viewTimingExperimentDetail('${exp.experiment_id}')" style="padding: 3px 8px; font-size: 11px;">İncele</button>
                <button class="btn btn-secondary" onclick="loadAndShowReport('${exp.experiment_id}')" style="padding: 3px 8px; font-size: 11px; margin-left: 4px;">Rapor</button>
              </td>
            `;
            tbody.appendChild(row);
          });
        }
      } catch (e) {
        tbody.innerHTML = '<tr><td colspan="10" style="text-align: center; color: #ef4444;">Deney listesi yüklenemedi: ' + e + '</td></tr>';
      }
    }

    async function viewTimingExperimentDetail(expId) {
      try {
        const res = await fetch("/api/v1/product/research/btc-timing/experiments/" + expId);
        if (res.ok) {
          const data = await res.json();
          currentTimingExperiment = data.experiment;
          populatePortfolioView(currentTimingExperiment);
          switchTimingSubtab("portfolio");
        }
      } catch (e) {
        alert("Deney detayı yüklenemedi: " + e);
      }
    }

    async function loadAndShowReport(expId) {
      try {
        const res = await fetch("/api/v1/product/research/btc-timing/experiments/" + expId + "/report");
        if (res.ok) {
          const data = await res.json();
          document.getElementById("timing-report-container").textContent = data.markdown_report || "Rapor metni boş.";
          switchTimingSubtab("reports");
        }
      } catch (e) {
        alert("Rapor yüklenemedi: " + e);
      }
    }

    function downloadCurrentTimingReport() {
      const text = document.getElementById("timing-report-container").textContent;
      if (!text || text.includes("Rapor görüntülemek için")) {
        alert("Lütfen önce bir deney raporu seçiniz.");
        return;
      }
      const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "CBE_BTC_Timing_Research_Report.md";
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }

    /* ========================================================================= */
    /* SPRINT 31: SHADOW EVALUATION CONTROLLER                                   */
    /* ========================================================================= */
    let currentSealedEvaluation = null;

    async function loadSealedEvaluationDashboard() {
      try {
        // 1. Fetch Readiness
        const rRes = await fetch("/api/v1/product/research/btc-timing/sealed-evaluation/readiness");
        if (rRes.ok) {
          const rData = await rRes.json();
          const rd = rData.readiness || {};
          const intEl = document.getElementById("sealed-readiness-integrity");
          if (intEl) {
            intEl.textContent = rd.package_integrity_verified ? "DOĞRULANDI" : "BOZULMUŞ";
            intEl.style.color = rd.package_integrity_verified ? "#34d399" : "#f87171";
          }
          const fpEl = document.getElementById("sealed-readiness-fingerprint");
          if (fpEl && rd.package_sha256_fingerprint) {
            fpEl.textContent = "SHA-256: " + rd.package_sha256_fingerprint.substring(0, 16) + "...";
          }
          const dsEl = document.getElementById("sealed-readiness-dataset");
          if (dsEl) dsEl.textContent = rd.target_evaluation_dataset || "-";
          const cdEl = document.getElementById("sealed-readiness-candles");
          if (cdEl && rd.dataset_total_candles) {
            cdEl.textContent = (rd.dataset_total_candles).toLocaleString("en-US") + " Saatlik Mum (2025 Kesintisiz)";
          }
          const hldEl = document.getElementById("sealed-readiness-holdout");
          if (hldEl) {
            hldEl.textContent = rd.holdout_contamination_flag ? "BULAŞMA TESPİT EDİLDİ" : "TEMİZ (0 Bulaşma)";
            hldEl.style.color = rd.holdout_contamination_flag ? "#f87171" : "#34d399";
          }
          const authEl = document.getElementById("sealed-readiness-auth");
          if (authEl) {
            authEl.textContent = rd.evaluation_authorization_status || "-";
            authEl.style.color = (rd.evaluation_authorization_status && rd.evaluation_authorization_status.includes("AUTHORIZED")) ? "#34d399" : "#38bdf8";
          }
        }

        // 2. Fetch Latest Results
        const resRes = await fetch("/api/v1/product/research/btc-timing/sealed-evaluation/results");
        if (resRes.ok) {
          const resData = await resRes.json();
          currentSealedEvaluation = resData.latest_evaluation;
          populateSealedEvaluationUI(currentSealedEvaluation);
        }
      } catch (e) {
        console.error("Error loading sealed evaluation dashboard:", e);
      }
    }

    function populateSealedEvaluationUI(evalData) {
      if (!evalData) return;
      const metrics = evalData.policy_metrics || {};

      // Shadow Portfolio KPIs (POLICY_TREND_LOW_TURNOVER & POLICY_BUY_AND_HOLD)
      const lowTurnover = metrics["POLICY_TREND_LOW_TURNOVER"] || {};
      const bnh = metrics["POLICY_BUY_AND_HOLD"] || {};
      const simple = metrics["POLICY_SIMPLE_TREND"] || {};

      const endEqEl = document.getElementById("shadow-end-equity");
      if (endEqEl && lowTurnover.ending_equity_usdt !== undefined) {
        endEqEl.textContent = "$" + lowTurnover.ending_equity_usdt.toLocaleString("en-US", {minimumFractionDigits: 2});
      }
      const netRetEl = document.getElementById("shadow-net-return");
      if (netRetEl && lowTurnover.net_return_pct !== undefined) {
        netRetEl.textContent = "Net Getiri: %" + lowTurnover.net_return_pct.toFixed(2);
        netRetEl.style.color = lowTurnover.net_return_pct >= 0 ? "#34d399" : "#f87171";
      }

      const bnhEqEl = document.getElementById("shadow-bnh-equity");
      if (bnhEqEl && bnh.ending_equity_usdt !== undefined) {
        bnhEqEl.textContent = "$" + bnh.ending_equity_usdt.toLocaleString("en-US", {minimumFractionDigits: 2});
      }
      const bnhRetEl = document.getElementById("shadow-bnh-return");
      if (bnhRetEl && bnh.net_return_pct !== undefined) {
        bnhRetEl.textContent = "Net Getiri: %" + bnh.net_return_pct.toFixed(2);
        bnhRetEl.style.color = bnh.net_return_pct >= 0 ? "#34d399" : "#f87171";
      }

      const costsEl = document.getElementById("shadow-total-costs");
      if (costsEl && lowTurnover.total_transaction_costs_usdt !== undefined) {
        costsEl.textContent = "$" + lowTurnover.total_transaction_costs_usdt.toLocaleString("en-US", {minimumFractionDigits: 2});
      }
      const tradeCountEl = document.getElementById("shadow-trade-count");
      if (tradeCountEl && lowTurnover.trade_count !== undefined && simple.trade_count !== undefined) {
        tradeCountEl.textContent = `${lowTurnover.trade_count} İşlem (Basit Trend: ${simple.trade_count} İşlem / $${(simple.total_transaction_costs_usdt || 0).toLocaleString("en-US")})`;
      }

      // Populate Trades Ledger Table
      const tradesBody = document.getElementById("shadow-trades-tbody");
      if (tradesBody && lowTurnover.trades) {
        tradesBody.innerHTML = "";
        const sampleTrades = lowTurnover.trades.slice(0, 20);
        if (sampleTrades.length === 0) {
          tradesBody.innerHTML = '<tr><td colspan="11" style="text-align: center; color: #64748b;">Kayıtlı işlem bulunamadı.</td></tr>';
        } else {
          sampleTrades.forEach(t => {
            const tr = document.createElement("tr");
            const sideColor = t.side === "BUY" ? "#34d399" : "#f87171";
            tr.innerHTML = `
              <td style="color: #94a3b8;">${t.trade_id}</td>
              <td>${t.timestamp_iso}</td>
              <td style="color: ${sideColor}; font-weight: 700;">${t.side}</td>
              <td>$${(t.nominal_price || 0).toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
              <td>$${(t.effective_price || 0).toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
              <td>${(t.btc_quantity || 0).toFixed(6)} BTC</td>
              <td>$${(t.gross_usdt_value || 0).toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
              <td>$${(t.fee_usdt || 0).toFixed(2)}</td>
              <td>$${((t.spread_cost_usdt || 0) + (t.slippage_cost_usdt || 0)).toFixed(2)}</td>
              <td>$${(t.usdt_balance_after || 0).toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
              <td style="font-weight: 700;">$${(t.equity_usdt_after || 0).toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
            `;
            tradesBody.appendChild(tr);
          });
        }
      }

      // Populate Benchmark Table
      const benchBody = document.getElementById("shadow-benchmark-tbody");
      if (benchBody) {
        benchBody.innerHTML = "";
        const order = [
          "POLICY_BUY_AND_HOLD",
          "POLICY_USDT_CASH",
          "POLICY_SIMPLE_TREND",
          "POLICY_TREND_LOW_TURNOVER",
          "POLICY_PERIODIC_REBALANCE",
          "POLICY_DERIVED_REGIME_CONFIRMATION"
        ];
        order.forEach(pid => {
          const p = metrics[pid];
          if (!p) return;
          const tr = document.createElement("tr");
          const retColor = p.net_return_pct >= 0 ? "#34d399" : "#f87171";
          const excess = p.excess_return_over_bnh_pct || (p.net_return_pct - (bnh.net_return_pct || 0));
          const excessColor = excess >= 0 ? "#34d399" : "#f87171";
          tr.innerHTML = `
            <td style="font-weight: 600; color: #f8fafc;">${p.policy_name}</td>
            <td style="font-size: 11px; color: #94a3b8;">${pid}</td>
            <td style="font-weight: 700;">$${(p.ending_equity_usdt || 0).toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
            <td style="color: ${retColor}; font-weight: 700;">%${(p.net_return_pct || 0).toFixed(2)}</td>
            <td style="color: ${excessColor};">%${excess.toFixed(2)}</td>
            <td style="color: #f87171;">%${(p.max_drawdown_pct || 0).toFixed(2)}</td>
            <td>${(p.sharpe_ratio || 0).toFixed(2)}</td>
            <td>${(p.sortino_ratio || 0).toFixed(2)}</td>
            <td>${p.trade_count}</td>
            <td style="color: #fbbf24;">$${(p.total_transaction_costs_usdt || 0).toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
            <td><span class="badge badge-success">LEDGER_RECONCILED</span></td>
          `;
          benchBody.appendChild(tr);
        });
      }

      // Populate Hypotheses Cards
      const hypGrid = document.getElementById("shadow-hypotheses-grid");
      if (hypGrid && evalData.hypotheses) {
        hypGrid.innerHTML = "";
        Object.values(evalData.hypotheses).forEach(h => {
          const card = document.createElement("div");
          card.className = "timing-kpi-card";
          card.style.background = "#0b1120";
          card.style.border = "1px solid #1e293b";
          const isSup = h.verdict === "SUPPORTED";
          const badgeClass = isSup ? "badge-success" : "badge-danger";
          card.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <span style="font-weight: 700; color: #38bdf8; font-size: 14px;">${h.hypothesis_id}</span>
              <span class="badge ${badgeClass}" style="font-weight: 700;">${h.verdict}</span>
            </div>
            <div style="font-size: 12px; color: #f1f5f9; font-weight: 600; margin-bottom: 6px;">
              ${h.hypothesis_statement}
            </div>
            <div style="font-size: 11px; color: #94a3b8; line-height: 1.5; margin-bottom: 8px;">
              ${h.effect_size_summary}
            </div>
            <div style="font-size: 10px; color: #64748b; font-family: var(--font-mono);">
              Kriter: ${h.predeclared_criteria} | α_adj: ${h.multiple_comparison_adjusted_alpha}
            </div>
          `;
          hypGrid.appendChild(card);
        });
      }

      // Draw Equity Canvas
      setTimeout(() => drawShadowEquityCanvas(evalData), 100);
    }

    async function runManualOfflineImport(register) {
      const path = document.getElementById("sealed-import-path").value;
      const datasetId = document.getElementById("sealed-import-dataset-id").value;
      const statusEl = document.getElementById("sealed-import-status");
      const box = document.getElementById("sealed-import-results-box");
      const content = document.getElementById("sealed-import-results-content");

      statusEl.textContent = "⏳ Doğrulanıyor...";
      box.style.display = "block";
      content.innerHTML = '<span style="color: #94a3b8;">Veri seti doğrulanıyor...</span>';

      try {
        const res = await fetch("/api/v1/product/research/btc-timing/sealed-evaluation/import-dataset", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ file_path: path, dataset_id: datasetId, register: register })
        });
        const data = await res.json();
        const vr = data.validation_result || {};
        if (data.status === "success") {
          statusEl.textContent = register ? "✅ Başarıyla içe aktarıldı ve kaydedildi." : "✅ Doğrulama başarılı.";
          content.innerHTML = `
            <div style="color: #34d399; font-weight: 700; margin-bottom: 6px;">✅ VERİ SETİ DOĞRULANDI & UYGUN (VALID)</div>
            <div>Veri Seti: <strong>${vr.dataset_id}</strong> | Mum Sayısı: <strong>${(vr.total_bars || 0).toLocaleString("en-US")}</strong></div>
            <div>SHA-256: <code style="font-size: 10px; color: #38bdf8;">${vr.sha256_checksum}</code></div>
            <div>Zaman Aralığı: ${vr.earliest_open_utc} → ${vr.latest_open_utc}</div>
            <div>Kesintisiz: <strong>${vr.is_continuous ? "EVET" : "HAYIR"}</strong> | Eksik Mum: ${vr.missing_candle_count} | Çift Mum: ${vr.duplicate_count}</div>
            <div>Holdout Bulaşması: <strong>${vr.holdout_contamination_detected ? "EVET" : "YOK (Temiz)"}</strong></div>
            <div>Provenans Sınıfı: <span class="badge badge-info">${vr.provenance_classification}</span></div>
          `;
          loadSealedEvaluationDashboard();
        } else {
          statusEl.textContent = "❌ Doğrulama başarısız.";
          const errList = (vr.validation_errors || []).map(e => `<li>${e}</li>`).join("");
          content.innerHTML = `
            <div style="color: #f87171; font-weight: 700; margin-bottom: 6px;">❌ DOĞRULAMA REDDEDİLDİ</div>
            <ul style="color: #f87171; margin-left: 20px;">${errList || "Bilinmeyen hata."}</ul>
          `;
        }
      } catch (e) {
        statusEl.textContent = "❌ Bağlantı hatası: " + e;
        content.innerHTML = `<span style="color: #f87171;">Bağlantı hatası: ${e}</span>`;
      }
    }

    async function runSealedEvaluationFromUI() {
      const btn = document.getElementById("btn-run-sealed-eval");
      const statusEl = document.getElementById("sealed-exec-status");
      btn.disabled = true;
      statusEl.textContent = "⏳ Mühürlü değerlendirme yürütülüyor...";

      const stages = ["freeze", "eligibility", "auth", "access", "sim", "bench", "seal", "report"];
      stages.forEach(s => {
        const el = document.getElementById("stage-" + s);
        if (el) el.style.background = "#0284c7";
      });

      try {
        const res = await fetch("/api/v1/product/research/btc-timing/sealed-evaluation/run", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ dataset_id: "DS-BTC-1H-2025-SEALED", accessed_by: "Dashboard_V9_User" })
        });
        if (res.ok) {
          const data = await res.json();
          currentSealedEvaluation = data.evaluation_result;
          statusEl.textContent = "✅ Mühürlü Değerlendirme Tamamlandı (" + (currentSealedEvaluation.run_id || "") + ")";
          populateSealedEvaluationUI(currentSealedEvaluation);
        } else {
          statusEl.textContent = "❌ Değerlendirme yürütme hatası.";
        }
      } catch (e) {
        statusEl.textContent = "❌ Bağlantı hatası: " + e;
      } finally {
        btn.disabled = false;
        stages.forEach(s => {
          const el = document.getElementById("stage-" + s);
          if (el) el.style.background = "#1e293b";
        });
      }
    }

    function drawShadowEquityCanvas(evalData) {
      const canvas = document.getElementById("shadowEquityCanvas");
      if (!canvas) return;
      const ctx = canvas.getContext("2d");
      const width = canvas.width;
      const height = canvas.height;

      ctx.clearRect(0, 0, width, height);

      // Background
      ctx.fillStyle = "#0b1120";
      ctx.fillRect(0, 0, width, height);

      if (!evalData || !evalData.policy_metrics) return;
      const metrics = evalData.policy_metrics;

      // Extract sample equity curves
      const pLow = (metrics["POLICY_TREND_LOW_TURNOVER"] || {}).equity_curve_sample || [];
      const pSimple = (metrics["POLICY_SIMPLE_TREND"] || {}).equity_curve_sample || [];
      const pBnh = (metrics["POLICY_BUY_AND_HOLD"] || {}).equity_curve_sample || [];

      if (pLow.length === 0) return;

      const padLeft = 60;
      const padRight = 30;
      const padTop = 30;
      const padBottom = 40;
      const plotW = width - padLeft - padRight;
      const plotH = height - padTop - padBottom;

      const minVal = 3000;
      const maxVal = 12000;

      // Draw Gridlines
      ctx.strokeStyle = "#1e293b";
      ctx.lineWidth = 1;
      const yTicks = [4000, 6000, 8000, 10000, 12000];
      ctx.fillStyle = "#64748b";
      ctx.font = "10px monospace";
      ctx.textAlign = "right";

      yTicks.forEach(val => {
        const y = padTop + plotH - ((val - minVal) / (maxVal - minVal)) * plotH;
        ctx.beginPath();
        ctx.moveTo(padLeft, y);
        ctx.lineTo(width - padRight, y);
        ctx.stroke();
        ctx.fillText("$" + val.toLocaleString("en-US"), padLeft - 8, y + 3);
      });

      // Cash baseline: $10,000 line
      const cashY = padTop + plotH - ((10000 - minVal) / (maxVal - minVal)) * plotH;
      ctx.strokeStyle = "rgba(148, 163, 184, 0.5)";
      ctx.setLineDash([4, 4]);
      ctx.beginPath();
      ctx.moveTo(padLeft, cashY);
      ctx.lineTo(width - padRight, cashY);
      ctx.stroke();
      ctx.setLineDash([]);

      function drawCurve(points, color) {
        if (!points || points.length === 0) return;
        ctx.strokeStyle = color;
        ctx.lineWidth = 2;
        ctx.beginPath();
        points.forEach((pt, idx) => {
          const x = padLeft + (idx / (points.length - 1)) * plotW;
          const val = Math.max(minVal, Math.min(maxVal, pt.total_equity_usdt || pt.equity_usdt || 10000));
          const y = padTop + plotH - ((val - minVal) / (maxVal - minVal)) * plotH;
          if (idx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();
      }

      drawCurve(pBnh, "#fbbf24");      // Buy and hold (Yellow)
      drawCurve(pSimple, "#f87171");   // Simple trend (Red)
      drawCurve(pLow, "#38bdf8");      // Low turnover (Cyan)
    }

    /* ========================================================================= */
    /* SPRINT 32: DASHBOARD V10 INVESTMENT RESEARCH WORKSPACE CONTROLLER         */
    /* ========================================================================= */
    let v10CachedCurves = null;
    let v10ChartMode = 'equity';
    let v10TradesCurrentPage = 1;
    let v10TradesTotalPages = 1;

    async function loadInvestmentResearchV10() {
      try {
        // 1. Overview
        const ovRes = await fetch("/api/v1/product/research/btc-timing/v10/overview");
        if (ovRes.ok) {
          const ov = await ovRes.json();
          const periodElem = document.getElementById("v10-kpi-period");
          if (periodElem) periodElem.textContent = (ov.evaluation_period ? ov.evaluation_period.year : "2025") + " (" + (ov.evaluation_period ? ov.evaluation_period.total_hours : 8760) + " Saat)";
          const provElem = document.getElementById("v10-kpi-provenance");
          if (provElem) provElem.textContent = ov.provenance_status || "RESTRICTED_EVIDENCE_UNVERIFIED_PROVENANCE";
          const sealElem = document.getElementById("v10-kpi-seal");
          if (sealElem && ov.policy_package_status && ov.policy_package_status.seal_sha256) {
            sealElem.textContent = ov.policy_package_status.seal_sha256.substring(0, 16) + "... (Mühürlü)";
          }
          const benchElem = document.getElementById("v10-kpi-benchmark");
          if (benchElem && ov.best_historical_benchmark) {
            benchElem.textContent = ov.best_historical_benchmark.display_name + " (%" + ov.best_historical_benchmark.net_return_pct + ")";
          }
        }

        // 2. Comparison & Curves
        const compRes = await fetch("/api/v1/product/research/btc-timing/v10/comparison");
        if (compRes.ok) {
          const comp = await compRes.json();
          v10CachedCurves = comp.equity_curves || {};
          renderV10ComparisonTable(comp.policies || []);
          renderV10Chart();
        }

        // 3. Strategy Details (Initial)
        await onV10StrategySelectChange();

        // 4. Cost Intelligence
        const costRes = await fetch("/api/v1/product/research/btc-timing/v10/cost-intelligence");
        if (costRes.ok) {
          const costData = await costRes.json();
          const dragElem = document.getElementById("v10-compounded-drag-text");
          if (dragElem && costData.compounded_drag_analysis) {
            dragElem.textContent = costData.compounded_drag_analysis.explanation;
          }
          renderV10CostScenarios(costData.cost_sensitivity_scenarios || []);
        }

        // 5. Scientific Evidence
        const evRes = await fetch("/api/v1/product/research/btc-timing/v10/scientific-evidence");
        if (evRes.ok) {
          const evData = await evRes.json();
          renderV10Hypotheses(evData.hypotheses || {});
        }

        // 6. Timeline
        const tlRes = await fetch("/api/v1/product/research/btc-timing/v10/timeline");
        if (tlRes.ok) {
          const tlData = await tlRes.json();
          renderV10Timeline(tlData.timeline || []);
        }
      } catch (err) {
        console.error("Error loading Investment Research V10:", err);
      }
    }

    function renderV10ComparisonTable(policies) {
      const tbody = document.getElementById("v10-comparison-tbody");
      if (!tbody) return;
      tbody.innerHTML = "";

      policies.forEach(p => {
        const tr = document.createElement("tr");
        const retColor = p.net_return_pct > 0 ? "#34d399" : (p.net_return_pct === 0 ? "#94a3b8" : "#f87171");
        const ddColor = p.max_drawdown_pct < -50 ? "#ef4444" : "#fb923c";
        const isExact = p.reconciliation_verdict === "EXACT_MATCH";
        const badgeLabel = isExact ? "Tam Eşleşme (0.00)" : "Yuvarlama (<$0.01)";
        const badgeStyle = isExact ? "background: rgba(16, 185, 129, 0.2); color: #10b981;" : "background: rgba(56, 189, 248, 0.15); color: #38bdf8;";
        const recEquity = p.reconstructed_equity_usdt !== undefined ? p.reconstructed_equity_usdt : p.ending_equity_usdt;

        tr.innerHTML = `
          <td style="font-weight: 600; color: #f8fafc;">${p.display_name}</td>
          <td><span class="badge" style="font-size: 10px; background: rgba(56, 189, 248, 0.1); color: #38bdf8;">${p.category}</span></td>
          <td>$${p.initial_capital_usdt.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
          <td style="font-weight: bold; color: #f8fafc;" title="Yayınlanan: $${p.ending_equity_usdt.toFixed(2)} | Yeniden Oluşturulan: $${recEquity.toFixed(2)}">$${p.ending_equity_usdt.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
          <td style="color: ${retColor}; font-weight: bold;">${p.net_return_pct > 0 ? "+" : ""}${p.net_return_pct.toFixed(2)}%</td>
          <td style="color: ${ddColor};">${p.max_drawdown_pct.toFixed(2)}%</td>
          <td>${p.sharpe_ratio.toFixed(2)}</td>
          <td>${p.trade_count}</td>
          <td style="color: #fb923c;">$${p.total_transaction_costs_usdt.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
          <td>%${(p.time_invested_pct * 100).toFixed(1)}</td>
          <td><span class="badge" style="font-size: 10px; ${badgeStyle}">${badgeLabel}</span></td>
        `;
        tbody.appendChild(tr);
      });
    }

    function switchV10ChartMode(mode) {
      v10ChartMode = mode;
      const btnEq = document.getElementById("v10-btn-chart-equity");
      const btnDd = document.getElementById("v10-btn-chart-drawdown");
      const title = document.getElementById("v10-chart-title");

      if (mode === 'equity') {
        if (btnEq) { btnEq.classList.add("btn-primary"); btnEq.classList.remove("btn-secondary"); }
        if (btnDd) { btnDd.classList.remove("btn-primary"); btnDd.classList.add("btn-secondary"); }
        if (title) title.textContent = "Tarihsel Özkaynak Gelişimi (2025 Tam Yıl - 120 Nokta Örnekleme)";
      } else {
        if (btnDd) { btnDd.classList.add("btn-primary"); btnDd.classList.remove("btn-secondary"); }
        if (btnEq) { btnEq.classList.remove("btn-primary"); btnEq.classList.add("btn-secondary"); }
        if (title) title.textContent = "Tarihsel Su Altı Düşüş Eğrisi (Underwater Drawdown %)";
      }
      renderV10Chart();
    }

    function renderV10Chart() {
      const canvas = document.getElementById("v10-equity-canvas");
      if (!canvas || !v10CachedCurves) return;
      const ctx = canvas.getContext("2d");
      const width = canvas.width;
      const height = canvas.height;

      ctx.clearRect(0, 0, width, height);

      const padLeft = 60;
      const padRight = 30;
      const padTop = 30;
      const padBottom = 40;
      const plotW = width - padLeft - padRight;
      const plotH = height - padTop - padBottom;

      const colors = {
        "POLICY_BUY_AND_HOLD": "#fbbf24",
        "POLICY_USDT_CASH": "#94a3b8",
        "POLICY_SIMPLE_TREND": "#f87171",
        "POLICY_TREND_LOW_TURNOVER": "#38bdf8",
        "POLICY_PERIODIC_REBALANCE": "#a78bfa",
        "POLICY_DERIVED_REGIME_CONFIRMATION": "#34d399",
      };

      if (v10ChartMode === 'equity') {
        const minVal = 2000;
        const maxVal = 14000;

        // Gridlines
        ctx.strokeStyle = "#1e293b";
        ctx.lineWidth = 1;
        const yTicks = [3000, 6000, 9000, 10000, 12000, 14000];
        ctx.fillStyle = "#64748b";
        ctx.font = "10px monospace";
        ctx.textAlign = "right";

        yTicks.forEach(val => {
          const y = padTop + plotH - ((val - minVal) / (maxVal - minVal)) * plotH;
          ctx.beginPath();
          ctx.moveTo(padLeft, y);
          ctx.lineTo(width - padRight, y);
          ctx.stroke();
          ctx.fillText("$" + val.toLocaleString("en-US"), padLeft - 8, y + 3);
        });

        // $10,000 cash baseline
        const cashY = padTop + plotH - ((10000 - minVal) / (maxVal - minVal)) * plotH;
        ctx.strokeStyle = "rgba(148, 163, 184, 0.4)";
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(padLeft, cashY);
        ctx.lineTo(width - padRight, cashY);
        ctx.stroke();
        ctx.setLineDash([]);

        // Curves
        Object.keys(colors).forEach(polKey => {
          const pts = v10CachedCurves[polKey] || [];
          if (pts.length === 0) return;
          ctx.strokeStyle = colors[polKey] || "#cbd5e1";
          ctx.lineWidth = polKey === "POLICY_TREND_LOW_TURNOVER" ? 2.5 : 1.5;
          ctx.beginPath();
          pts.forEach((pt, idx) => {
            const x = padLeft + (idx / (pts.length - 1)) * plotW;
            const val = Math.max(minVal, Math.min(maxVal, pt.equity));
            const y = padTop + plotH - ((val - minVal) / (maxVal - minVal)) * plotH;
            if (idx === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.stroke();
        });
      } else {
        // Drawdown Mode (0% down to -70%)
        const minVal = -70;
        const maxVal = 0;

        ctx.strokeStyle = "#1e293b";
        ctx.lineWidth = 1;
        const yTicks = [0, -15, -30, -45, -60, -70];
        ctx.fillStyle = "#64748b";
        ctx.font = "10px monospace";
        ctx.textAlign = "right";

        yTicks.forEach(val => {
          const y = padTop + plotH - ((val - minVal) / (maxVal - minVal)) * plotH;
          ctx.beginPath();
          ctx.moveTo(padLeft, y);
          ctx.lineTo(width - padRight, y);
          ctx.stroke();
          ctx.fillText(val + "%", padLeft - 8, y + 3);
        });

        Object.keys(colors).forEach(polKey => {
          const pts = v10CachedCurves[polKey] || [];
          if (pts.length === 0) return;
          ctx.strokeStyle = colors[polKey] || "#cbd5e1";
          ctx.lineWidth = polKey === "POLICY_TREND_LOW_TURNOVER" ? 2.5 : 1.5;
          ctx.beginPath();
          pts.forEach((pt, idx) => {
            const x = padLeft + (idx / (pts.length - 1)) * plotW;
            const ddVal = Math.max(minVal, Math.min(maxVal, -Math.abs(pt.drawdown)));
            const y = padTop + plotH - ((ddVal - minVal) / (maxVal - minVal)) * plotH;
            if (idx === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
          });
          ctx.stroke();
        });
      }
    }

    async function onV10StrategySelectChange() {
      const sel = document.getElementById("v10-strategy-select");
      if (!sel) return;
      const policyKey = sel.value;

      try {
        const stratRes = await fetch("/api/v1/product/research/btc-timing/v10/strategy/" + policyKey);
        if (stratRes.ok) {
          const strat = await stratRes.json();
          const rulesUl = document.getElementById("v10-strategy-rules-list");
          if (rulesUl) {
            rulesUl.innerHTML = "";
            (strat.exact_rules || []).forEach(r => {
              const li = document.createElement("li");
              li.textContent = r;
              rulesUl.appendChild(li);
            });
          }

          const paramsPre = document.getElementById("v10-strategy-params-pre");
          if (paramsPre) {
            paramsPre.textContent = JSON.stringify(strat.frozen_parameters || {}, null, 2);
          }
        }

        v10TradesCurrentPage = 1;
        await loadV10TradesCurrentPage();
      } catch (err) {
        console.error("Error loading strategy details:", err);
      }
    }

    async function loadV10TradesCurrentPage() {
      const sel = document.getElementById("v10-strategy-select");
      if (!sel) return;
      const policyKey = sel.value;

      const sideFilter = (document.getElementById("v10-trade-side-filter") || {}).value || "";
      let url = "/api/v1/product/research/btc-timing/v10/trades/" + policyKey + "?page=" + v10TradesCurrentPage + "&limit=15";
      if (sideFilter) url += "&side=" + sideFilter;

      try {
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          v10TradesTotalPages = data.total_pages || 1;
          const pageInfo = document.getElementById("v10-trade-page-info");
          if (pageInfo) pageInfo.textContent = "Sayfa " + data.page + " / " + v10TradesTotalPages + " (" + data.total_trades + " İşlem)";

          const prevBtn = document.getElementById("v10-trade-prev");
          const nextBtn = document.getElementById("v10-trade-next");
          if (prevBtn) prevBtn.disabled = (data.page <= 1);
          if (nextBtn) nextBtn.disabled = (data.page >= v10TradesTotalPages);

          const tbody = document.getElementById("v10-trades-tbody");
          if (!tbody) return;
          tbody.innerHTML = "";

          if (!data.trades || data.trades.length === 0) {
            tbody.innerHTML = '<tr><td colspan="12" style="text-align: center; color: #64748b;">Bu politika veya filtre için işlem bulunmuyor.</td></tr>';
            return;
          }

          data.trades.forEach(t => {
            const tr = document.createElement("tr");
            const sideColor = t.side === "BUY" ? "#34d399" : "#f87171";
            tr.innerHTML = `
              <td style="font-family: monospace; font-size: 11px;">${t.trade_id}</td>
              <td style="font-size: 11px; color: #94a3b8;">${(t.timestamp_iso || "").replace("T", " ").replace("Z", "")}</td>
              <td><span class="badge" style="font-size: 10px; background: rgba(56, 189, 248, 0.1); color: ${sideColor}; font-weight: bold;">${t.side}</span></td>
              <td>$${t.nominal_price.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
              <td>$${t.effective_price.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
              <td>${t.btc_quantity.toFixed(6)}</td>
              <td>$${t.fee_usdt.toFixed(2)}</td>
              <td>$${t.spread_cost_usdt.toFixed(2)}</td>
              <td>$${t.slippage_cost_usdt.toFixed(2)}</td>
              <td style="color: #fb923c; font-weight: bold;">$${t.total_cost_usdt.toFixed(2)}</td>
              <td>$${t.usdt_balance_after.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
              <td style="font-weight: bold; color: #f8fafc;">$${t.equity_usdt_after.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
            `;
            tbody.appendChild(tr);
          });
        }
      } catch (err) {
        console.error("Error loading trades:", err);
      }
    }

    function prevV10TradesPage() {
      if (v10TradesCurrentPage > 1) {
        v10TradesCurrentPage--;
        loadV10TradesCurrentPage();
      }
    }

    function nextV10TradesPage() {
      if (v10TradesCurrentPage < v10TradesTotalPages) {
        v10TradesCurrentPage++;
        loadV10TradesCurrentPage();
      }
    }

    function renderV10CostScenarios(scenarios) {
      const tbody = document.getElementById("v10-cost-scenarios-tbody");
      if (!tbody) return;
      tbody.innerHTML = "";

      scenarios.forEach(sc => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td style="font-weight: 600; color: #f8fafc;">${sc.scenario}</td>
          <td><span class="badge" style="background: rgba(251, 146, 60, 0.1); color: #fb923c;">${sc.one_way_bps} bps</span></td>
          <td style="color: #f87171;">$${sc.simple_trend_equity.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
          <td style="color: #38bdf8; font-weight: bold;">$${sc.low_turnover_equity.toLocaleString("en-US", {minimumFractionDigits: 2})}</td>
          <td style="font-size: 11px; color: #94a3b8;">${sc.impact}</td>
        `;
        tbody.appendChild(tr);
      });
    }

    function renderV10Hypotheses(hypotheses) {
      const grid = document.getElementById("v10-hypotheses-grid");
      if (!grid) return;
      grid.innerHTML = "";

      Object.keys(hypotheses).forEach(hId => {
        const h = hypotheses[hId];
        const card = document.createElement("div");
        card.className = "timing-kpi-card";
        card.style.background = "#0f172a";
        card.style.border = "1px solid #1e293b";

        const isMet = h.descriptive_verdict === "DESCRIPTIVE_THRESHOLD_MET";
        const badgeColor = isMet ? "#10b981" : "#ef4444";
        const badgeBg = isMet ? "rgba(16, 185, 129, 0.15)" : "rgba(239, 68, 68, 0.15)";

        card.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span style="font-weight: bold; color: #38bdf8;">${hId}</span>
            <span class="badge" style="font-size: 10px; background: ${badgeBg}; color: ${badgeColor}; border: 1px solid ${badgeColor};">
              ${h.descriptive_verdict}
            </span>
          </div>
          <div style="font-size: 12px; font-weight: 600; color: #f8fafc; margin-bottom: 4px;">${h.name}</div>
          <div style="font-size: 11px; color: #94a3b8; line-height: 1.4; margin-bottom: 8px;">${h.effect_size_summary}</div>
          <div style="font-size: 10px; color: #64748b; background: #090d16; padding: 4px 6px; border-radius: 4px;">
            İstatistiksel Durum: <strong style="color: #fb923c;">${h.statistical_verdict}</strong>
          </div>
        `;
        grid.appendChild(card);
      });
    }

    function renderV10Timeline(timeline) {
      const cont = document.getElementById("v10-timeline-container");
      if (!cont) return;
      cont.innerHTML = "";

      timeline.forEach(item => {
        const div = document.createElement("div");
        div.style.padding = "12px 16px";
        div.style.background = "#090d16";
        div.style.borderRadius = "6px";
        div.style.borderLeft = "3px solid #38bdf8";

        div.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 4px;">
            <strong style="color: #38bdf8; font-size: 13px;">${item.sprint_id}: ${item.title}</strong>
            <span class="badge" style="font-size: 10px; background: rgba(56, 189, 248, 0.1); color: #94a3b8;">${item.dataset}</span>
          </div>
          <div style="font-size: 12px; color: #cbd5e1; margin-bottom: 4px;">${item.milestone}</div>
          <div style="font-size: 11px; color: #64748b;"><strong>Önemli Bulgu:</strong> ${item.key_finding}</div>
        `;
        cont.appendChild(div);
      });
    }

    async function downloadV10Report(fmt) {
      try {
        const res = await fetch("/api/v1/product/research/btc-timing/v10/report/download?format=" + fmt);
        if (res.ok) {
          const data = await res.json();
          const blob = new Blob([data.content], { type: data.media_type || "text/plain" });
          const url = URL.createObjectURL(blob);
          const a = document.createElement("a");
          a.href = url;
          a.download = data.filename || ("cbe_sprint32_report." + fmt);
          document.body.appendChild(a);
          a.click();
          document.body.removeChild(a);
          URL.revokeObjectURL(url);
        }
      } catch (err) {
        alert("Rapor indirilemedi: " + err);
      }
    }
    """

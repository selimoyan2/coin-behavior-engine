import re
from pathlib import Path

UI_PATH = Path("src/coin_behavior_engine/product/btc_timing_research/btc_timing_ui.py")

NAV_BTN = """          <button class="timing-subnav-btn" id="timing-btn-v10-workspace" onclick="switchTimingSubtab('v10-workspace')" style="border: 1px solid rgba(56, 189, 248, 0.4); background: rgba(56, 189, 248, 0.1);">
            <span>🏛️</span> Yatırım Araştırma V10
          </button>
          <button class="timing-subnav-btn" id="timing-btn-v11-market-intelligence" onclick="switchTimingSubtab('v11-market-intelligence')" style="border: 1px solid rgba(16, 185, 129, 0.5); background: rgba(16, 185, 129, 0.15); color: #34d399; font-weight: bold;">
            <span>🔬</span> Piyasa Davranış İstihbaratı V11
          </button>"""

PANEL_V11_HTML = """
        <!-- =============================================================== -->
        <!-- SUB-PANEL 13: SPRINT 33 MARKET BEHAVIOR INTELLIGENCE V11         -->
        <!-- =============================================================== -->
        <div id="timing-panel-v11-market-intelligence" class="timing-panel">
          
          <!-- PROMINENT DISCLAIMER BANNER -->
          <div style="background: rgba(16, 185, 129, 0.1); border: 2px solid #10b981; border-radius: 8px; padding: 14px 20px; margin-bottom: 24px; display: flex; align-items: center; gap: 16px;">
            <span style="font-size: 28px;">🔬</span>
            <div>
              <div style="color: #10b981; font-weight: 800; font-size: 16px; letter-spacing: 0.05em;" id="v11-disclaimer-banner">
                CBE-0.7.0 KANONİK MODEL ARAŞTIRMA KÖPRÜSÜ & PİYASA DAVRANIŞ İSTİHBARATI (V11)
              </div>
              <div style="color: #cbd5e1; font-size: 13px; margin-top: 4px;">
                Dondurulmuş kanonik CBE-0.7.0 olasılıksal piyasa durumu motoru üzerinden tarihsel Bitcoin (BTC/USDT) davranış analitiği. Canlı al-sat, otomatik emir iletimi ve gerçek sermaye riski KESİNLİKLE YASAKTIR. Tüm çıktılar saf araştırma ve istihbarat amaçlıdır.
              </div>
            </div>
          </div>

          <!-- SECTION I1: MODEL & BRIDGE STATUS -->
          <div style="margin-bottom: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <h4 style="font-size: 14px; text-transform: uppercase; color: #34d399; letter-spacing: 0.5px; margin: 0;">
                I1. Kanonik Model Durumu & Araştırma Köprüsü
              </h4>
              <span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.4);" id="v11-bridge-status-badge">
                OPERATIONAL_READ_ONLY_BRIDGE_ACTIVE
              </span>
            </div>
            
            <div class="timing-kpi-grid">
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Kanonik Bilimsel Model</div>
                <div class="timing-kpi-val" style="color: #f8fafc; font-size: 15px;" id="v11-kpi-model">CBE-0.7.0</div>
                <div class="timing-kpi-sub">Dondurulmuş (Commit: 849e76e...)</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Aktif Geri Çekilme Seviyesi</div>
                <div class="timing-kpi-val" style="color: #38bdf8; font-size: 15px;" id="v11-kpi-fallback">SPOT_ONLY_U0</div>
                <div class="timing-kpi-sub">Oynaklık Sıkışması + Hacim Z-Skoru</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Özellik Erişilebilirliği</div>
                <div class="timing-kpi-val" style="color: #10b981; font-size: 15px;" id="v11-kpi-avail">%54.55 (8/16)</div>
                <div class="timing-kpi-sub">%100 Spot & Seans Özellikleri Tam</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Kilitli Kasa Güvencesi</div>
                <div class="timing-kpi-val" style="color: #f59e0b; font-size: 15px;" id="v11-kpi-lockbox">29/29 Doğrulandı</div>
                <div class="timing-kpi-sub">Kriptografik SHA-256 Değişmezliği</div>
              </div>
            </div>
          </div>

          <!-- SECTION I2: REGIME EXPLORER -->
          <div style="margin-bottom: 24px;">
            <h4 style="font-size: 14px; text-transform: uppercase; color: #34d399; letter-spacing: 0.5px; margin-bottom: 12px;">
              I2. Rejim Gezgini: Tarihsel Dağılım, Süreklilik & Geçiş Dinamikleri
            </h4>
            
            <div class="card" style="padding: 18px; margin-bottom: 16px; background: #0b1120; border: 1px solid #1e293b;">
              <h5 style="color: #f8fafc; font-size: 13px; margin-bottom: 10px;">📊 Tarihsel Rejim Süreklilik İstatistikleri (Toplam: 18,288 Saat)</h5>
              <div style="overflow-x: auto;">
                <table class="timing-table" style="width: 100%; font-size: 12px;" id="v11-persistence-table">
                  <thead>
                    <tr>
                      <th>Rejim</th>
                      <th>Oluşum Sayısı</th>
                      <th>Toplam Saat</th>
                      <th>Ortalama Süre (Saat)</th>
                      <th>Medyan Süre (Saat)</th>
                      <th>%75 Dilim (Saat)</th>
                      <th>Maksimum Süre (Saat)</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr><td>Yükleniyor...</td><td colspan="6">-</td></tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="card" style="padding: 18px; background: #0b1120; border: 1px solid #1e293b;">
              <h5 style="color: #f8fafc; font-size: 13px; margin-bottom: 10px;">🔄 Ampirik 24-Saatlik Rejim Geçiş Matrisi P(Regime_{t+24h} | Regime_t)</h5>
              <div style="overflow-x: auto;">
                <table class="timing-table" style="width: 100%; font-size: 12px;" id="v11-transition-table">
                  <thead>
                    <tr>
                      <th>Başlangıç Rejimi</th>
                      <th>NORMAL</th>
                      <th>HIGH_VOL</th>
                      <th>EXP_WATCH</th>
                      <th>TAIL_RISK</th>
                      <th>QUIET</th>
                      <th>COMPRESSION</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr><td>Yükleniyor...</td><td colspan="6">-</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- SECTION I3: FORWARD RETURN EXPLORER -->
          <div style="margin-bottom: 24px;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <h4 style="font-size: 14px; text-transform: uppercase; color: #34d399; letter-spacing: 0.5px; margin: 0;">
                I3. İleri Yönlü Getiri Gezgini (Forward Return Distributions)
              </h4>
              <div class="btn-group" style="display: flex; gap: 8px;">
                <button class="btn btn-sm btn-outline-info active" onclick="switchV11Horizon('6h')" id="v11-btn-h6">6 Saat</button>
                <button class="btn btn-sm btn-outline-info" onclick="switchV11Horizon('24h')" id="v11-btn-h24">24 Saat</button>
                <button class="btn btn-sm btn-outline-info" onclick="switchV11Horizon('72h')" id="v11-btn-h72">72 Saat</button>
                <button class="btn btn-sm btn-outline-info" onclick="switchV11Horizon('168h')" id="v11-btn-h168">7 Gün (168h)</button>
              </div>
            </div>

            <div class="card" style="padding: 18px; background: #0b1120; border: 1px solid #1e293b;">
              <div style="overflow-x: auto;">
                <table class="timing-table" style="width: 100%; font-size: 12px;" id="v11-forward-returns-table">
                  <thead>
                    <tr>
                      <th>Kanonik Rejim</th>
                      <th>Örneklem</th>
                      <th>Ort. Getiri (%)</th>
                      <th>Medyan (%)</th>
                      <th>Oynaklık (Std %)</th>
                      <th>Çarpıklık (Skew)</th>
                      <th>Basıklık (Kurt)</th>
                      <th>Kazanma Oranı (%)</th>
                      <th>%5 Dilim (VaR)</th>
                      <th>%95 Dilim</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr><td>Yükleniyor...</td><td colspan="9">-</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- SECTION I4: RISK INTELLIGENCE PANEL -->
          <div style="margin-bottom: 24px;">
            <h4 style="font-size: 14px; text-transform: uppercase; color: #34d399; letter-spacing: 0.5px; margin-bottom: 12px;">
              I4. Risk İstihbaratı & Aşağı Yönlü Kuyruk Riski (MAE & CVaR)
            </h4>
            
            <div class="timing-kpi-grid" style="margin-bottom: 16px;">
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">En Tehlikeli Rejim</div>
                <div class="timing-kpi-val" style="color: #ef4444; font-size: 15px;">TAIL_RISK_ELEVATED</div>
                <div class="timing-kpi-sub">Aşırı Sol Kuyruk Asimetrisi (-1.24 Skew)</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">24h CVaR-95 (Beklenen Kayıp)</div>
                <div class="timing-kpi-val" style="color: #ef4444; font-size: 15px;">-%9.14</div>
                <div class="timing-kpi-sub">Sakin Rejime Kıyasla 3 Kat Yüksek</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Ortalama 24h MAE</div>
                <div class="timing-kpi-val" style="color: #f59e0b; font-size: 15px;">-%4.92</div>
                <div class="timing-kpi-sub">Giriş Sonrası Maksimum İçsel Çekilme</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Çöküş Sınırlama Potansiyeli</div>
                <div class="timing-kpi-val" style="color: #10b981; font-size: 15px;">+6.49% Puan</div>
                <div class="timing-kpi-sub">Maksimum Portföy Çekilmesinde İyileşme</div>
              </div>
            </div>

            <div class="card" style="padding: 18px; background: #0b1120; border: 1px solid #1e293b;">
              <h5 style="color: #f8fafc; font-size: 13px; margin-bottom: 10px;">🛡️ Rejim Bazında 24-Saatlik Aşağı Yönlü Risk Özet Tablosu</h5>
              <div style="overflow-x: auto;">
                <table class="timing-table" style="width: 100%; font-size: 12px;" id="v11-risk-table">
                  <thead>
                    <tr>
                      <th>Rejim</th>
                      <th>Ortalama MAE (%)</th>
                      <th>Medyan MAE (%)</th>
                      <th>Maksimum Çekilme (%)</th>
                      <th>%5 MAE Eşiği (%)</th>
                      <th>VaR-95 (%)</th>
                      <th>CVaR-95 (Expected Shortfall)</th>
                      <th>CVaR-99</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr><td>Yükleniyor...</td><td colspan="7">-</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- SECTION I5: MODEL COMPARISON VIEW -->
          <div style="margin-bottom: 24px;">
            <h4 style="font-size: 14px; text-transform: uppercase; color: #34d399; letter-spacing: 0.5px; margin-bottom: 12px;">
              I5. Model Karşılaştırma Görünümü: Kanonik CBE-0.7.0 vs Türetilmiş Sezgisel
            </h4>
            
            <div class="card" style="padding: 18px; background: #0b1120; border: 1px solid #1e293b; margin-bottom: 16px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                <span style="font-weight: 600; color: #f8fafc; font-size: 13px;">Kavramsal Uyuşma ve Örtüşme Analizi</span>
                <span class="badge" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8;" id="v11-concordance-badge">%67.4 UYUŞMA</span>
              </div>
              <p style="font-size: 12px; color: #94a3b8; line-height: 1.6; margin: 0;" id="v11-comparison-explanation">
                Kanonik model oynaklık sıkışma oranları ve hacim z-skorlarına dayanırken, türetilmiş sezgisel Parkinson oynaklığı ve fiyat ortalamalarını kullanmaktadır. Genel oynaklık rejimlerinde %65-67 örtüşme görülürken, yönsel kırılımlarda modeller ayrışmaktadır.
              </p>
            </div>
          </div>

          <!-- SECTION I6: SCIENTIFIC EVIDENCE LEDGER -->
          <div style="margin-bottom: 24px;">
            <h4 style="font-size: 14px; text-transform: uppercase; color: #34d399; letter-spacing: 0.5px; margin-bottom: 12px;">
              I6. Bilimsel Kanıt Defteri (21 Doğrulanmış Artefakt)
            </h4>
            <div class="card" style="padding: 18px; background: #0b1120; border: 1px solid #1e293b;">
              <div style="overflow-x: auto;">
                <table class="timing-table" style="width: 100%; font-size: 12px;" id="v11-evidence-table">
                  <thead>
                    <tr>
                      <th>Artefakt Dosyası</th>
                      <th>Açıklama</th>
                      <th>Format</th>
                      <th>Doğrulama Durumu</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr><td>Yükleniyor...</td><td colspan="3">-</td></tr>
                  </tbody>
                </table>
              </div>
            </div>
          </div>

          <!-- SECTION I7: DEPLOYMENT SAFETY STATUS -->
          <div style="margin-bottom: 24px;">
            <h4 style="font-size: 14px; text-transform: uppercase; color: #34d399; letter-spacing: 0.5px; margin-bottom: 12px;">
              I7. Dağıtım Güvenliği & Üretim Sıfır-Dokunuş Durumu
            </h4>
            <div class="timing-kpi-grid">
              <div class="timing-kpi-card" style="border: 1px solid rgba(16, 185, 129, 0.4);">
                <div class="timing-kpi-label">Üretim Konteyneri</div>
                <div class="timing-kpi-val" style="color: #10b981; font-family: monospace; font-size: 14px;" id="v11-prod-container">4c6a29b5fbf6</div>
                <div class="timing-kpi-sub">Port 8000 | 0 Yeniden Başlatma | Sağlıklı</div>
              </div>
              <div class="timing-kpi-card" style="border: 1px solid rgba(56, 189, 248, 0.4);">
                <div class="timing-kpi-label">Staging Ortamı</div>
                <div class="timing-kpi-val" style="color: #38bdf8; font-family: monospace; font-size: 14px;" id="v11-staging-port">Port 18080</div>
                <div class="timing-kpi-sub">cbe-market-intelligence-staging</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Yalıtım Stratejisi</div>
                <div class="timing-kpi-val" style="color: #f8fafc; font-size: 13px;">OPSİYON 3</div>
                <div class="timing-kpi-sub">Araştırma Branşı & Staging Dağıtımı</div>
              </div>
              <div class="timing-kpi-card">
                <div class="timing-kpi-label">Canlı Ticaret Kilidi</div>
                <div class="timing-kpi-val" style="color: #ef4444; font-size: 13px;">KESİNLİKLE YASAK</div>
                <div class="timing-kpi-sub">HTTP 403 Sıkı Uygulama</div>
              </div>
            </div>
          </div>

        </div>
"""

JS_CONTROLLER = """
  // -------------------------------------------------------------------------
  // SPRINT 33: V11 MARKET BEHAVIOR INTELLIGENCE CONTROLLER
  // -------------------------------------------------------------------------
  let currentV11Horizon = '24h';

  async function loadTimingV11Intelligence() {
    console.log('[V11 Intelligence] Loading market behavior telemetry...');
    try {
      // 1. Model Status
      const stRes = await fetch('/api/v1/product/btc-timing/v11/model-status');
      if (stRes.ok) {
        const stData = await stRes.json();
        const badge = document.getElementById('v11-bridge-status-badge');
        if (badge) badge.innerText = stData.bridge_status || 'ACTIVE';
        const kpiModel = document.getElementById('v11-kpi-model');
        if (kpiModel) kpiModel.innerText = stData.canonical_model_version || 'CBE-0.7.0';
        const kpiFallback = document.getElementById('v11-kpi-fallback');
        if (kpiFallback) kpiFallback.innerText = stData.active_fallback_level || 'SPOT_ONLY_U0';
        const kpiAvail = document.getElementById('v11-kpi-avail');
        if (kpiAvail) kpiAvail.innerText = '%' + stData.feature_availability_pct;
      }

      // 2. Regime Explorer
      const regRes = await fetch('/api/v1/product/btc-timing/v11/regime-explorer');
      if (regRes.ok) {
        const regData = await regRes.json();
        renderV11PersistenceTable(regData.persistence_stats || {});
        renderV11TransitionTable(regData.transition_matrix_24h || {});
      }

      // 3. Forward Returns
      await loadV11ForwardReturns(currentV11Horizon);

      // 4. Risk Intelligence
      const riskRes = await fetch('/api/v1/product/btc-timing/v11/risk-intelligence');
      if (riskRes.ok) {
        const riskData = await riskRes.json();
        renderV11RiskTable(riskData.risk_metrics_24h || {});
      }

      // 5. Evidence Ledger
      const evRes = await fetch('/api/v1/product/btc-timing/v11/evidence-ledger');
      if (evRes.ok) {
        const evData = await evRes.json();
        renderV11EvidenceTable(evData.artifacts || []);
      }

      // 6. Deployment Safety
      const safeRes = await fetch('/api/v1/product/btc-timing/v11/deployment-safety');
      if (safeRes.ok) {
        const safeData = await safeRes.json();
        const pCont = document.getElementById('v11-prod-container');
        if (pCont) pCont.innerText = safeData.production_container_id || '4c6a29b5fbf6';
      }
    } catch (e) {
      console.error('[V11 Intelligence] Error loading data:', e);
    }
  }

  async function loadV11ForwardReturns(horizon) {
    try {
      const res = await fetch('/api/v1/product/btc-timing/v11/forward-returns?horizon=' + horizon);
      if (res.ok) {
        const data = await res.json();
        renderV11ForwardReturnsTable(data.horizon_data || {});
      }
    } catch (e) {
      console.error('[V11] Error loading forward returns:', e);
    }
  }

  function switchV11Horizon(h) {
    currentV11Horizon = h;
    ['6h', '24h', '72h', '168h'].forEach(hz => {
      const b = document.getElementById('v11-btn-h' + hz.replace('h', ''));
      if (b) {
        if (hz === h) b.classList.add('active');
        else b.classList.remove('active');
      }
    });
    loadV11ForwardReturns(h);
  }

  function renderV11PersistenceTable(stats) {
    const tbody = document.querySelector('#v11-persistence-table tbody');
    if (!tbody) return;
    let html = '';
    for (const [r, d] of Object.entries(stats)) {
      html += `<tr>
        <td style="font-weight:600; color:#38bdf8;">${r}</td>
        <td>${d.total_occurrences || '-'}</td>
        <td>${d.total_bars || '-'}</td>
        <td style="color:#10b981; font-weight:600;">${d.mean_duration_hours || '-'} sa</td>
        <td>${d.median_duration_hours || '-'} sa</td>
        <td>${d.p75_duration_hours || '-'} sa</td>
        <td>${d.max_duration_hours || '-'} sa</td>
      </tr>`;
    }
    tbody.innerHTML = html;
  }

  function renderV11TransitionTable(matrix) {
    const tbody = document.querySelector('#v11-transition-table tbody');
    if (!tbody) return;
    let html = '';
    const cols = ['NORMAL', 'HIGH_VOLATILITY', 'EXPANSION_WATCH', 'TAIL_RISK_ELEVATED', 'QUIET', 'COMPRESSION'];
    for (const [r, row] of Object.entries(matrix)) {
      html += `<tr><td style="font-weight:600; color:#f8fafc;">${r}</td>`;
      cols.forEach(c => {
        const val = row[c] !== undefined ? row[c] : 0;
        const pct = (val * 100).toFixed(1) + '%';
        const color = val > 0.4 ? '#34d399' : (val > 0.15 ? '#38bdf8' : '#94a3b8');
        html += `<td style="color:${color}; font-weight:${val > 0.3 ? '600' : 'normal'};">${pct}</td>`;
      });
      html += `</tr>`;
    }
    tbody.innerHTML = html;
  }

  function renderV11ForwardReturnsTable(data) {
    const tbody = document.querySelector('#v11-forward-returns-table tbody');
    if (!tbody) return;
    let html = '';
    for (const [r, d] of Object.entries(data)) {
      const meanColor = d.mean_return_pct >= 0 ? '#10b981' : '#ef4444';
      html += `<tr>
        <td style="font-weight:600; color:#38bdf8;">${r}</td>
        <td>${d.sample_size || '-'}</td>
        <td style="color:${meanColor}; font-weight:600;">${d.mean_return_pct > 0 ? '+' : ''}${d.mean_return_pct}%</td>
        <td>${d.median_return_pct > 0 ? '+' : ''}${d.median_return_pct}%</td>
        <td>${d.std_return_pct}%</td>
        <td style="color:${d.skewness < 0 ? '#ef4444' : '#10b981'};">${d.skewness}</td>
        <td>${d.excess_kurtosis}</td>
        <td style="color:${d.win_rate_pct >= 50 ? '#10b981' : '#ef4444'}; font-weight:600;">%${d.win_rate_pct}</td>
        <td style="color:#ef4444;">${d.p05_return_pct}%</td>
        <td style="color:#10b981;">${d.p95_return_pct}%</td>
      </tr>`;
    }
    tbody.innerHTML = html;
  }

  function renderV11RiskTable(data) {
    const tbody = document.querySelector('#v11-risk-table tbody');
    if (!tbody) return;
    let html = '';
    for (const [r, d] of Object.entries(data)) {
      const isTail = r === 'TAIL_RISK_ELEVATED';
      const rowStyle = isTail ? 'style="background:rgba(239, 68, 68, 0.08);"' : '';
      html += `<tr ${rowStyle}>
        <td style="font-weight:600; color:${isTail ? '#ef4444' : '#38bdf8'};">${r}</td>
        <td>${d.mean_mae_pct}%</td>
        <td>${d.median_mae_pct}%</td>
        <td style="color:#ef4444; font-weight:600;">${d.max_drawdown_pct}%</td>
        <td>${d.p05_mae_pct}%</td>
        <td>${d.var_95_pct}%</td>
        <td style="color:#ef4444; font-weight:700;">${d.cvar_95_pct}%</td>
        <td style="color:#dc2626;">${d.cvar_99_pct}%</td>
      </tr>`;
    }
    tbody.innerHTML = html;
  }

  function renderV11EvidenceTable(artifacts) {
    const tbody = document.querySelector('#v11-evidence-table tbody');
    if (!tbody) return;
    let html = '';
    artifacts.forEach(a => {
      html += `<tr>
        <td style="font-family:monospace; color:#38bdf8;">${a.id}</td>
        <td style="color:#f8fafc;">${a.title}</td>
        <td><span class="badge" style="background:#1e293b; color:#94a3b8;">${a.type}</span></td>
        <td><span class="badge" style="background:rgba(16, 185, 129, 0.2); color:#34d399; border:1px solid rgba(16,185,129,0.4);">${a.status}</span></td>
      </tr>`;
    });
    tbody.innerHTML = html;
  }
"""

def patch_ui():
    content = UI_PATH.read_text(encoding="utf-8")

    # 1. Patch Navigation Button
    if "timing-btn-v11-market-intelligence" not in content:
        content = content.replace(
            """          <button class="timing-subnav-btn" id="timing-btn-v10-workspace" onclick="switchTimingSubtab('v10-workspace')" style="border: 1px solid rgba(56, 189, 248, 0.4); background: rgba(56, 189, 248, 0.1);">
            <span>🏛️</span> Yatırım Araştırma V10
          </button>""",
            NAV_BTN
        )
        print("Patched Navigation Button!")

    # 2. Patch HTML Panel
    if "timing-panel-v11-market-intelligence" not in content:
        # find the end of timing-panel-v10-workspace
        hook = "        </div>\n\n      </div>\n    </section>"
        replacement = "        </div>\n\n" + PANEL_V11_HTML + "\n      </div>\n    </section>"
        if hook in content:
            content = content.replace(hook, replacement, 1)
            print("Patched HTML Panel!")
        else:
            print("WARNING: Could not find hook for HTML panel!")

    # 3. Patch switchTimingSubtab
    if "v11-market-intelligence" not in content:
        pass
    else:
        hook_js = """      } else if (subId === "v10-workspace") {
        loadTimingV10Workspace();
      }"""
        replacement_js = """      } else if (subId === "v10-workspace") {
        loadTimingV10Workspace();
      } else if (subId === "v11-market-intelligence") {
        loadTimingV11Intelligence();
      }"""
        if hook_js in content and 'loadTimingV11Intelligence();' not in content:
            content = content.replace(hook_js, replacement_js, 1)
            print("Patched switchTimingSubtab JS handler!")

    # 4. Append JS Controller functions
    if "loadTimingV11Intelligence" not in content:
        hook_end_script = "  // Expose API to window for console/external calls"
        content = content.replace(hook_end_script, JS_CONTROLLER + "\n\n  " + hook_end_script, 1)
        print("Patched JS Controller functions!")

    UI_PATH.write_text(content, encoding="utf-8")
    print("UI file saved successfully!")

if __name__ == '__main__':
    patch_ui()

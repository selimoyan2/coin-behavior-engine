"""Script to patch dashboard_ui.py for Sprint 18 Unified Research Workspace."""
from pathlib import Path

path = Path("src/coin_behavior_engine/product/dashboard_ui.py")
text = path.read_text(encoding="utf-8")

crlf = "\r\n" if "\r\n" in text else "\n"

# 1. Add nav tab
nav_target = '    <a href="#overview" class="nav-tab active" id="tab-btn-overview" onclick="switchTab(\'overview\')">'
nav_replacement = '''    <a href="#unified-workspace" class="nav-tab" id="tab-btn-unified-workspace" onclick="switchTab('unified-workspace')">
      <span>🔬</span> Birleşik Araştırma Alanı V1 (Sprint 18)
    </a>
    <a href="#overview" class="nav-tab active" id="tab-btn-overview" onclick="switchTab('overview')">'''

if crlf == "\r\n":
    nav_target = nav_target.replace("\n", "\r\n")
    nav_replacement = nav_replacement.replace("\n", "\r\n")

if nav_target not in text:
    raise RuntimeError("Could not find nav_target in dashboard_ui.py")

text = text.replace(nav_target, nav_replacement, 1)

# 2. Add tabGroupsMap entry
grp_target = '      overview: "market",'
grp_replacement = '''      "unified-workspace": "market",
      overview: "market",'''

if crlf == "\r\n":
    grp_target = grp_target.replace("\n", "\r\n")
    grp_replacement = grp_replacement.replace("\n", "\r\n")

if grp_target not in text:
    raise RuntimeError("Could not find grp_target in dashboard_ui.py")

text = text.replace(grp_target, grp_replacement, 1)

# 3. Add switchTab lazy loader
switch_target = "    function switchTab(tabId) {"
switch_replacement = """    function switchTab(tabId) {
      if (tabId === 'unified-workspace') setTimeout(loadUnifiedWorkspace, 50);"""

if crlf == "\r\n":
    switch_target = switch_target.replace("\n", "\r\n")
    switch_replacement = switch_replacement.replace("\n", "\r\n")

if switch_target not in text:
    raise RuntimeError("Could not find switch_target in dashboard_ui.py")

text = text.replace(switch_target, switch_replacement, 1)

# 4. Insert section module-unified-workspace before module-overview
section_target = '    <!-- MODULE 1: RESEARCH WORKSPACE (OVERVIEW REDESIGN)                     -->'
section_html = '''    <!-- =================================================================== -->
    <!-- MODULE 0: UNIFIED RESEARCH WORKSPACE V1 (SPRINT 18)                 -->
    <!-- =================================================================== -->
    <section id="module-unified-workspace" class="tab-content">
      <div class="card" style="border-left: 4px solid #38bdf8; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
          <div>
            <div style="font-size: 11px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px;">BİRLEŞİK TARİHSEL PİYASA ARAŞTIRMA ÇALIŞMA ALANI V1 (SPRINT 18)</div>
            <h2 style="font-size: 20px; color: #fff; margin: 4px 0;">Çok Modüllü Tarihsel Analiz, Oturum Orkestrasyonu &amp; Kanıt Bütünleşmesi</h2>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
              Model: <b style="color: #4ade80;">CBE-0.7.0 (STRICTLY FROZEN)</b> &bull;
              Kapsam: <b>2022-01 — 2026-09 (41.615 Saatlik Bar)</b> &bull;
              Rejim &amp; Volatilite &amp; Örüntü V2 &amp; Makro &amp; İstatistiki Kanıt &bull;
              <span class="badge badge-success">ÇEVRİMDIŞI ORKESTRASYON</span>
              <span class="badge badge-warn">CANLI TİCARET: YASAKLI</span>
            </div>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button class="btn btn-primary" id="btn-urs-run" onclick="runUnifiedResearchSession()">▶ Araştırmayı Çalıştır</button>
            <button class="btn" id="btn-urs-export" onclick="exportUnifiedEvidencePackage()">📦 Birleşik Kanıt Paketini İndir</button>
          </div>
        </div>
      </div>

      <!-- Research Configuration Panel -->
      <div class="card" style="margin-bottom: 20px;">
        <div class="section-title" style="margin-bottom: 12px;"><span>⚙️</span> Araştırma Oturumu Yapılandırması</div>
        
        <!-- Preset Shortcuts -->
        <div style="margin-bottom: 14px;">
          <span style="font-size: 12px; color: var(--text-muted); font-weight: 600; margin-right: 8px;">Tarihsel Olay Şablonları:</span>
          <div style="display: flex; gap: 6px; flex-wrap: wrap; margin-top: 6px;">
            <button class="pill-btn" onclick="selectUrsPreset('FED_SHOCK_JUN_2022')">Fed Faiz Şoku (Haz 2022)</button>
            <button class="pill-btn" onclick="selectUrsPreset('FTX_COLLAPSE_NOV_2022')">FTX Çöküşü (Kas 2022)</button>
            <button class="pill-btn" onclick="selectUrsPreset('SVB_BANKING_CRISIS_MAR_2023')">SVB &amp; USDC (Mar 2023)</button>
            <button class="pill-btn" onclick="selectUrsPreset('SPOT_ETF_APPROVAL_JAN_2024')">Spot ETF (Oca 2024)</button>
            <button class="pill-btn" onclick="selectUrsPreset('BITCOIN_HALVING_APR_2024')">Bitcoin Halving (Nis 2024)</button>
            <button class="pill-btn" onclick="selectUrsPreset('YEN_CARRY_UNWIND_AUG_2024')">Yen Carry Çözülmesi (Ağu 2024)</button>
          </div>
        </div>

        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 14px; margin-bottom: 14px;">
          <div>
            <label style="font-size: 11px; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 4px;">Varlık (Asset):</label>
            <select id="urs-asset" class="select-dropdown" style="width: 100%;">
              <option value="BTCUSDT" selected>BTCUSDT (Binance Spot)</option>
            </select>
          </div>
          <div>
            <label style="font-size: 11px; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 4px;">Zaman Aralığı (Interval):</label>
            <select id="urs-interval" class="select-dropdown" style="width: 100%;">
              <option value="1h" selected>1h (Saatlik - Önerilen)</option>
              <option value="15m">15m (15 Dakika)</option>
              <option value="5m">5m (5 Dakika)</option>
              <option value="4h">4h (4 Saat)</option>
              <option value="1d">1d (Günlük)</option>
            </select>
          </div>
          <div>
            <label style="font-size: 11px; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 4px;">Başlangıç (UTC):</label>
            <input type="text" id="urs-start-utc" class="input-text" style="width: 100%;" value="2022-06-01T00:00:00Z">
          </div>
          <div>
            <label style="font-size: 11px; color: var(--text-muted); font-weight: 600; display: block; margin-bottom: 4px;">Bitiş (UTC):</label>
            <input type="text" id="urs-end-utc" class="input-text" style="width: 100%;" value="2022-06-15T00:00:00Z">
          </div>
        </div>

        <!-- Modules Checkboxes -->
        <div style="border-top: 1px solid rgba(255,255,255,0.06); padding-top: 12px; margin-top: 10px;">
          <div style="font-size: 11px; color: var(--text-muted); font-weight: 600; margin-bottom: 8px;">Yürütülecek Analiz Modülleri:</div>
          <div style="display: flex; gap: 16px; flex-wrap: wrap;">
            <label style="font-size: 12px; display: inline-flex; align-items: center; gap: 6px; cursor: pointer; color: #e2e8f0;">
              <input type="checkbox" id="urs-mod-regime" checked> 🏛️ Rejim Analizi
            </label>
            <label style="font-size: 12px; display: inline-flex; align-items: center; gap: 6px; cursor: pointer; color: #e2e8f0;">
              <input type="checkbox" id="urs-mod-vol" checked> ⚡ Volatilite &amp; Momentler
            </label>
            <label style="font-size: 12px; display: inline-flex; align-items: center; gap: 6px; cursor: pointer; color: #e2e8f0;">
              <input type="checkbox" id="urs-mod-pattern" checked> 🔍 V2 Ayrık Örüntü Keşfi
            </label>
            <label style="font-size: 12px; display: inline-flex; align-items: center; gap: 6px; cursor: pointer; color: #e2e8f0;">
              <input type="checkbox" id="urs-mod-macro" checked> 📰 Makro Olay Bağlamı
            </label>
            <label style="font-size: 12px; display: inline-flex; align-items: center; gap: 6px; cursor: pointer; color: #e2e8f0;">
              <input type="checkbox" id="urs-mod-stat" checked> 📊 İstatistiki Kanıt &amp; Epistemoloji
            </label>
          </div>
        </div>
      </div>

      <!-- Active Session Status HUD -->
      <div id="urs-session-hud" class="card" style="display: none; margin-bottom: 20px; background: rgba(15, 23, 42, 0.6); border: 1px solid #334155;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
          <div>
            <span style="font-size: 11px; color: var(--text-muted);">Aktif Oturum Kimliği:</span>
            <span id="urs-hud-session-id" style="font-family: monospace; font-size: 13px; font-weight: 700; color: #38bdf8; margin-left: 6px;">-</span>
          </div>
          <div style="display: flex; gap: 16px; font-size: 12px;">
            <div><span style="color: var(--text-muted);">Gözlem Sayısı:</span> <b id="urs-hud-bars" style="color: #fff;">-</b> bar</div>
            <div><span style="color: var(--text-muted);">Süre:</span> <b id="urs-hud-duration" style="color: #fff;">-</b> saat</div>
            <div><span style="color: var(--text-muted);">Yürütme:</span> <b id="urs-hud-time" style="color: #4ade80;">-</b></div>
            <div><span style="color: var(--text-muted);">Durum:</span> <span id="urs-hud-status" class="badge badge-success">-</span></div>
          </div>
        </div>
      </div>

      <!-- Warnings Banner -->
      <div id="urs-warnings-banner" class="card" style="display: none; border-left: 4px solid var(--yellow); margin-bottom: 16px; background: rgba(245, 158, 11, 0.08);">
        <div style="font-weight: 700; color: var(--yellow); font-size: 13px;" id="urs-warnings-title">⚠️ Örneklem &amp; Kapsam Uyarısı</div>
        <div style="font-size: 12px; color: #cbd5e1; margin-top: 4px;" id="urs-warnings-body"></div>
      </div>

      <!-- Orchestrated Multi-Module Results Grid -->
      <div id="urs-results-container" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); gap: 16px; margin-bottom: 24px;">
        
        <!-- Card 1: Rejim Dağılımı -->
        <div class="card" id="urs-card-regime" style="display: none;">
          <div class="section-title"><span>🏛️</span> Piyasa Rejimi Dağılımı &amp; Kalıcılık</div>
          <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 10px;">Baskın Rejim: <b id="urs-regime-dominant" style="color:#fff;">-</b></div>
          <div id="urs-regime-bars" style="display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px;"></div>
          <div style="font-size: 11px; color: #94a3b8; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px;" id="urs-regime-expl">-</div>
        </div>

        <!-- Card 2: Volatilite ve Getiri -->
        <div class="card" id="urs-card-vol" style="display: none;">
          <div class="section-title"><span>⚡</span> Volatilite &amp; Getiri Momentleri</div>
          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 12px;">
            <div style="background: rgba(255,255,255,0.02); padding: 8px; border-radius: 4px;">
              <div style="font-size: 11px; color: var(--text-muted);">Gerçekleşen Vol (Yıllık)</div>
              <div id="urs-vol-realized" style="font-size: 16px; font-weight: 700; color: #38bdf8;">-%</div>
            </div>
            <div style="background: rgba(255,255,255,0.02); padding: 8px; border-radius: 4px;">
              <div style="font-size: 11px; color: var(--text-muted);">Parkinson Vol (Yıllık)</div>
              <div id="urs-vol-parkinson" style="font-size: 16px; font-weight: 700; color: #a78bfa;">-%</div>
            </div>
            <div style="background: rgba(255,255,255,0.02); padding: 8px; border-radius: 4px;">
              <div style="font-size: 11px; color: var(--text-muted);">Ortalama Getiri</div>
              <div id="urs-vol-mean-ret" style="font-size: 14px; font-weight: 600; color: #fff;">-%</div>
            </div>
            <div style="background: rgba(255,255,255,0.02); padding: 8px; border-radius: 4px;">
              <div style="font-size: 11px; color: var(--text-muted);">Basıklık (Kurtosis)</div>
              <div id="urs-vol-kurtosis" style="font-size: 14px; font-weight: 600; color: #fff;">-</div>
            </div>
          </div>
          <div style="font-size: 11px; color: #94a3b8; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px;" id="urs-vol-expl">-</div>
        </div>

        <!-- Card 3: Makro Olay Bağlamı -->
        <div class="card" id="urs-card-macro" style="display: none;">
          <div class="section-title"><span>📰</span> Makroekonomik Olay Bağlamı</div>
          <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">Dönem İçi Olaylar: <b id="urs-macro-count" style="color:#fff;">0</b> &bull; Baskın Tema: <b id="urs-macro-theme" style="color:#38bdf8;">-</b></div>
          <div id="urs-macro-list" style="max-height: 160px; overflow-y: auto; font-size: 11px; display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px;"></div>
          <div style="font-size: 11px; color: #94a3b8; border-top: 1px solid rgba(255,255,255,0.06); padding-top: 8px;" id="urs-macro-expl">-</div>
        </div>

        <!-- Card 4: İstatistiki Kanıt & Epistemoloji -->
        <div class="card" id="urs-card-stat" style="display: none;">
          <div class="section-title"><span>📊</span> İstatistiki Kanıt &amp; Holdout Açıklığı</div>
          <div style="font-size: 12px; margin-bottom: 8px;">
            <div style="color: var(--text-muted);">Getiri %95 Güven Aralığı: <b id="urs-stat-ci" style="color: #fff;">-</b></div>
            <div style="color: var(--text-muted); margin-top: 4px;">Holdout Durumu: <span class="badge badge-warn" id="urs-stat-holdout">HOLDOUT_PREVIOUSLY_EXPOSED</span></div>
          </div>
          <div style="background: rgba(239, 68, 68, 0.06); border: 1px solid rgba(239, 68, 68, 0.2); padding: 8px; border-radius: 4px; font-size: 11px; color: #fca5a5; margin-bottom: 8px;">
            <b>Epistemolojik Şeffaflık:</b> 14 şartnameden 2'si (Parkinson 1h-6h ve 1h-12h) holdout kriterlerini karşılamış olsa da holdout seti daha önce gözlendiğinden bağımsız doğrulayıcı değil keşifseldir.
          </div>
          <div style="font-size: 11px; color: #94a3b8;" id="urs-stat-fdr">FDR Denetimi: RES-ROB-CELL-758a387e (raw p: 0.3838, FDR q: 0.4478).</div>
        </div>

      </div>

      <!-- Card 5: Tarihsel Örüntü Keşfi V2 (Full width) -->
      <div class="card" id="urs-card-pattern" style="display: none; margin-bottom: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; margin-bottom: 12px;">
          <div class="section-title"><span>🔍</span> V2 Tarihsel Örüntü Keşfi &amp; Kararlılık Analizi</div>
          <div style="display: flex; gap: 8px; align-items: center;">
            <span class="badge badge-info" id="urs-pat-exp-id">EXP-PAT-V2-</span>
            <span class="badge badge-success" id="urs-pat-stability">HIGH_STABILITY (%93.3)</span>
          </div>
        </div>
        <div style="overflow-x: auto;">
          <table class="table" style="width: 100%; font-size: 12px;">
            <thead>
              <tr>
                <th>Sıra</th>
                <th>Aday Dönem (UTC)</th>
                <th>Benzerlik (%)</th>
                <th>Bileşik Mesafe</th>
                <th>Volatilite (%)</th>
                <th>Örtüşme Durumu</th>
                <th>Açıklama (TR)</th>
              </tr>
            </thead>
            <tbody id="urs-pat-candidates-tbody"></tbody>
          </table>
        </div>
        <div style="font-size: 11px; color: #94a3b8; margin-top: 8px;" id="urs-pat-expl">-</div>
      </div>

      <!-- Section: Research Session Comparison Studio -->
      <div class="card" style="margin-bottom: 24px;">
        <div class="section-title" style="margin-bottom: 12px;"><span>⚖️</span> İki Tarihsel Dönemi Karşılaştırma Laboratuvarı</div>
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; margin-bottom: 14px;">
          <div style="background: rgba(255,255,255,0.02); padding: 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.06);">
            <div style="font-weight: 700; color: #38bdf8; font-size: 12px; margin-bottom: 6px;">Dönem A (Referans):</div>
            <input type="text" id="urs-cmp-start-a" class="input-text" style="width: 100%; margin-bottom: 6px;" value="2022-06-01T00:00:00Z">
            <input type="text" id="urs-cmp-end-a" class="input-text" style="width: 100%;" value="2022-06-15T00:00:00Z">
          </div>
          <div style="background: rgba(255,255,255,0.02); padding: 10px; border-radius: 6px; border: 1px solid rgba(255,255,255,0.06);">
            <div style="font-weight: 700; color: #a78bfa; font-size: 12px; margin-bottom: 6px;">Dönem B (Karşılaştırma):</div>
            <input type="text" id="urs-cmp-start-b" class="input-text" style="width: 100%; margin-bottom: 6px;" value="2024-07-27T01:00:00Z">
            <input type="text" id="urs-cmp-end-b" class="input-text" style="width: 100%;" value="2024-08-10T01:00:00Z">
          </div>
        </div>
        <button class="btn btn-primary" onclick="compareUnifiedSessions()">⚖️ İki Dönemi Karşılaştır</button>

        <!-- Comparison Results Box -->
        <div id="urs-cmp-results-box" style="display: none; margin-top: 16px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 14px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; margin-bottom: 10px;">
            <div style="font-weight: 700; font-size: 14px; color: #fff;">Karşılaştırma Sonucu: <span id="urs-cmp-id" style="font-family: monospace; color: #38bdf8;">-</span></div>
            <div class="badge badge-success" id="urs-cmp-similarity" style="font-size: 13px;">Bileşik Benzerlik: -%</div>
          </div>
          <div style="overflow-x: auto; margin-bottom: 10px;">
            <table class="table" style="width: 100%; font-size: 12px;">
              <thead>
                <tr>
                  <th>Boyut</th>
                  <th>Dönem A Değeri</th>
                  <th>Dönem B Değeri</th>
                  <th>Fark / Uyum</th>
                  <th>Bilimsel Açıklama (TR)</th>
                </tr>
              </thead>
              <tbody id="urs-cmp-tbody"></tbody>
            </table>
          </div>
          <div style="background: rgba(56, 189, 248, 0.06); border-left: 3px solid #38bdf8; padding: 10px; border-radius: 4px; font-size: 12px; color: #e2e8f0;" id="urs-cmp-synthesis"></div>
        </div>
      </div>

      <!-- Legal & Governance Footer Card -->
      <div class="card" style="border-left: 4px solid var(--border-color); background: rgba(0,0,0,0.2);">
        <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); margin-bottom: 4px;">BİLİMSEL YÖNETİŞİM &amp; YASAL UYARI</div>
        <div style="font-size: 11px; color: var(--text-muted); line-height: 1.5;">
          Bu çalışma alanındaki tüm veriler geriye dönük (retrospektif) offline gözlemlere dayanmaktadır. Model dondurulmuş olup (CBE-0.7.0), hiçbir canlı alım-satım sinyali, getiri vaadi veya yönsel fiyat tahmini üretilmez. Tüm holdout ve FDR soy kütüğü denetimleri doğrulanmış bilimsel standartlara tabidir.
        </div>
      </div>
    </section>

    <!-- MODULE 1: RESEARCH WORKSPACE (OVERVIEW REDESIGN)                     -->'''

if crlf == "\r\n":
    section_target = section_target.replace("\n", "\r\n")
    section_html = section_html.replace("\n", "\r\n")

if section_target not in text:
    raise RuntimeError("Could not find section_target in dashboard_ui.py")

text = text.replace(section_target, section_html, 1)

# 5. Add JavaScript functions at bottom of script
js_code = '''
    // =======================================================================
    // Sprint 18 — Unified Research Workspace V1 Scripts
    // =======================================================================
    let currentUrsSession = null;
    let currentUrsComparison = null;

    async function loadUnifiedWorkspace() {
      if (!currentUrsSession) {
        runUnifiedResearchSession();
      }
    }

    function selectUrsPreset(presetId) {
      const presets = {
        'FED_SHOCK_JUN_2022': { start: '2022-06-01T00:00:00Z', end: '2022-06-15T00:00:00Z' },
        'FTX_COLLAPSE_NOV_2022': { start: '2022-11-06T00:00:00Z', end: '2022-11-20T00:00:00Z' },
        'SVB_BANKING_CRISIS_MAR_2023': { start: '2023-03-08T00:00:00Z', end: '2023-03-22T00:00:00Z' },
        'SPOT_ETF_APPROVAL_JAN_2024': { start: '2024-01-08T00:00:00Z', end: '2024-01-22T00:00:00Z' },
        'BITCOIN_HALVING_APR_2024': { start: '2024-04-14T00:00:00Z', end: '2024-04-28T00:00:00Z' },
        'YEN_CARRY_UNWIND_AUG_2024': { start: '2024-08-01T00:00:00Z', end: '2024-08-15T00:00:00Z' }
      };
      if (presets[presetId]) {
        document.getElementById('urs-start-utc').value = presets[presetId].start;
        document.getElementById('urs-end-utc').value = presets[presetId].end;
        runUnifiedResearchSession();
      }
    }

    async function runUnifiedResearchSession() {
      const start = document.getElementById('urs-start-utc').value.trim();
      const end = document.getElementById('urs-end-utc').value.trim();
      const asset = document.getElementById('urs-asset').value;
      const interval = document.getElementById('urs-interval').value;

      const mods = [];
      if (document.getElementById('urs-mod-regime').checked) mods.push('regime_analysis');
      if (document.getElementById('urs-mod-vol').checked) mods.push('volatility_analysis');
      if (document.getElementById('urs-mod-pattern').checked) mods.push('historical_pattern_discovery');
      if (document.getElementById('urs-mod-macro').checked) mods.push('macro_comparison');
      if (document.getElementById('urs-mod-stat').checked) mods.push('statistical_evidence');

      const hud = document.getElementById('urs-session-hud');
      const hudStatus = document.getElementById('urs-hud-status');
      hud.style.display = 'block';
      hudStatus.textContent = 'Yürütülüyor...';
      hudStatus.className = 'badge badge-info';

      try {
        const url = `/api/v1/product/research-workspace/session?reference_start_utc=${encodeURIComponent(start)}&reference_end_utc=${encodeURIComponent(end)}&asset=${encodeURIComponent(asset)}&interval=${encodeURIComponent(interval)}&modules=${encodeURIComponent(mods.join(','))}`;
        const res = await fetch(url);
        if (!res.ok) {
          const err = await res.json();
          throw new Error(err.message || 'Oturum yürütme hatası');
        }
        const data = await res.json();
        currentUrsSession = data;

        // Render HUD
        document.getElementById('urs-hud-session-id').textContent = data.session_id;
        document.getElementById('urs-hud-bars').textContent = data.candle_count;
        document.getElementById('urs-hud-duration').textContent = data.duration_hours;
        document.getElementById('urs-hud-time').textContent = data.total_execution_time_ms + ' ms';
        hudStatus.textContent = data.execution_status;
        hudStatus.className = data.execution_status === 'COMPLETED' ? 'badge badge-success' : 'badge badge-warn';

        // Set comparison input A defaults
        document.getElementById('urs-cmp-start-a').value = data.reference_start_utc;
        document.getElementById('urs-cmp-end-a').value = data.reference_end_utc;

        // Render Card 1: Rejim Analizi
        const regCard = document.getElementById('urs-card-regime');
        if (data.module_results && data.module_results.regime_analysis && data.module_results.regime_analysis.status === 'SUCCESS') {
          regCard.style.display = 'block';
          const rData = data.module_results.regime_analysis;
          document.getElementById('urs-regime-dominant').textContent = rData.dominant_regime + ' (%' + rData.dominant_share_pct + ')';
          document.getElementById('urs-regime-expl').textContent = rData.explanation_tr;

          let barsHtml = '';
          const dist = rData.regime_distribution || {};
          for (const [rName, rShare] of Object.entries(dist)) {
            const pct = (rShare * 100).toFixed(1);
            barsHtml += `<div>
              <div style="display: flex; justify-content: space-between; font-size: 11px; margin-bottom: 2px;">
                <span>${rName}</span>
                <span style="font-weight: 600; color: #fff;">%${pct}</span>
              </div>
              <div style="background: rgba(255,255,255,0.06); height: 6px; border-radius: 3px; overflow: hidden;">
                <div style="background: #38bdf8; width: ${pct}%; height: 100%;"></div>
              </div>
            </div>`;
          }
          document.getElementById('urs-regime-bars').innerHTML = barsHtml;
        } else {
          regCard.style.display = 'none';
        }

        // Render Card 2: Volatilite
        const volCard = document.getElementById('urs-card-vol');
        if (data.module_results && data.module_results.volatility_analysis && data.module_results.volatility_analysis.status === 'SUCCESS') {
          volCard.style.display = 'block';
          const vData = data.module_results.volatility_analysis;
          document.getElementById('urs-vol-realized').textContent = '%' + vData.realized_volatility_annual_pct;
          document.getElementById('urs-vol-parkinson').textContent = '%' + vData.parkinson_volatility_annual_pct;
          document.getElementById('urs-vol-mean-ret').textContent = '%' + vData.mean_return_pct;
          document.getElementById('urs-vol-kurtosis').textContent = vData.excess_kurtosis;
          document.getElementById('urs-vol-expl').textContent = vData.explanation_tr;

          // Warnings banner
          const warnBanner = document.getElementById('urs-warnings-banner');
          if (vData.warnings && vData.warnings.length > 0) {
            warnBanner.style.display = 'block';
            document.getElementById('urs-warnings-body').textContent = vData.warnings.join(' | ');
          } else {
            warnBanner.style.display = 'none';
          }
        } else {
          volCard.style.display = 'none';
        }

        // Render Card 3: Makro Olaylar
        const macroCard = document.getElementById('urs-card-macro');
        if (data.module_results && data.module_results.macro_comparison && data.module_results.macro_comparison.status === 'SUCCESS') {
          macroCard.style.display = 'block';
          const mData = data.module_results.macro_comparison;
          document.getElementById('urs-macro-count').textContent = mData.in_period_events_count;
          document.getElementById('urs-macro-theme').textContent = mData.dominant_macro_theme;
          document.getElementById('urs-macro-expl').textContent = mData.explanation_tr;

          let listHtml = '';
          const evts = mData.in_period_events || [];
          if (evts.length === 0) {
            listHtml = '<div style="color: var(--text-muted);">Bu pencere içinde doğrudan makro olay bulunmamaktadır.</div>';
          } else {
            evts.forEach(e => {
              listHtml += `<div style="background: rgba(255,255,255,0.02); padding: 4px 6px; border-radius: 4px; display: flex; justify-content: space-between;">
                <span>${e.event_name}</span>
                <span class="badge badge-info" style="font-size: 10px;">${e.cohort}</span>
              </div>`;
            });
          }
          document.getElementById('urs-macro-list').innerHTML = listHtml;
        } else {
          macroCard.style.display = 'none';
        }

        // Render Card 4: İstatistiki Kanıt
        const statCard = document.getElementById('urs-card-stat');
        if (data.module_results && data.module_results.statistical_evidence && data.module_results.statistical_evidence.status === 'SUCCESS') {
          statCard.style.display = 'block';
          const sData = data.module_results.statistical_evidence;
          const ci = sData.confidence_interval_95_mean_return_pct || [0, 0];
          document.getElementById('urs-stat-ci').textContent = `[%${ci[0]}, %${ci[1]}]`;
          document.getElementById('urs-stat-holdout').textContent = sData.holdout_exposure_status;
        } else {
          statCard.style.display = 'none';
        }

        // Render Card 5: Örüntü Keşfi V2
        const patCard = document.getElementById('urs-card-pattern');
        if (data.module_results && data.module_results.historical_pattern_discovery && data.module_results.historical_pattern_discovery.status === 'SUCCESS') {
          patCard.style.display = 'block';
          const pData = data.module_results.historical_pattern_discovery;
          document.getElementById('urs-pat-exp-id').textContent = pData.experiment_id || 'EXP-PAT-V2';
          document.getElementById('urs-pat-stability').textContent = `${pData.ranking_stability_verdict} (%${(pData.ranking_stability_score * 100).toFixed(1)})`;
          document.getElementById('urs-pat-expl').textContent = pData.explanation_tr;

          let tbHtml = '';
          const cands = pData.ranked_candidates || [];
          cands.forEach(c => {
            tbHtml += `<tr>
              <td><b>#${c.rank}</b></td>
              <td style="font-family: monospace;">${c.start_utc.substring(0,10)} &rarr; ${c.end_utc.substring(0,10)}</td>
              <td><b style="color: #4ade80;">%${c.similarity_score_pct.toFixed(1)}</b></td>
              <td>${c.composite_distance.toFixed(4)}</td>
              <td>%${c.realized_volatility_pct.toFixed(1)}</td>
              <td><span class="badge badge-success">${c.overlap_status}</span></td>
              <td style="font-size: 11px; color: var(--text-muted);">${c.explanation_tr}</td>
            </tr>`;
          });
          document.getElementById('urs-pat-candidates-tbody').innerHTML = tbHtml;
        } else {
          patCard.style.display = 'none';
        }

      } catch (err) {
        hudStatus.textContent = 'HATA: ' + err.message;
        hudStatus.className = 'badge badge-warn';
      }
    }

    async function compareUnifiedSessions() {
      const startA = document.getElementById('urs-cmp-start-a').value.trim();
      const endA = document.getElementById('urs-cmp-end-a').value.trim();
      const startB = document.getElementById('urs-cmp-start-b').value.trim();
      const endB = document.getElementById('urs-cmp-end-b').value.trim();
      const interval = document.getElementById('urs-interval').value;

      const resBox = document.getElementById('urs-cmp-results-box');
      resBox.style.display = 'block';
      document.getElementById('urs-cmp-synthesis').textContent = 'İki tarihsel oturum karşılaştırılıyor...';

      try {
        const url = `/api/v1/product/research-workspace/compare?start_a=${encodeURIComponent(startA)}&end_a=${encodeURIComponent(endA)}&start_b=${encodeURIComponent(startB)}&end_b=${encodeURIComponent(endB)}&interval=${encodeURIComponent(interval)}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error('Karşılaştırma hatası: ' + res.status);
        const data = await res.json();
        currentUrsComparison = data;

        document.getElementById('urs-cmp-id').textContent = data.comparison_id;
        document.getElementById('urs-cmp-similarity').textContent = 'Bileşik Benzerlik: %' + data.composite_similarity_pct;
        document.getElementById('urs-cmp-synthesis').textContent = data.scientific_summary_tr;

        const dims = data.dimension_comparisons || {};
        let tbHtml = `
          <tr>
            <td><b>Rejim Kompozisyonu (JSD)</b></td>
            <td>${data.session_a.dominant_regime}</td>
            <td>${data.session_b.dominant_regime}</td>
            <td><b style="color: #38bdf8;">%${dims.regime_composition.similarity_pct} Benzerlik</b> (JSD: ${dims.regime_composition.jsd_divergence})</td>
            <td>${dims.regime_composition.explanation_tr}</td>
          </tr>
          <tr>
            <td><b>Gerçekleşen Volatilite</b></td>
            <td>%${data.session_a.realized_volatility_annual_pct}</td>
            <td>%${data.session_b.realized_volatility_annual_pct}</td>
            <td><b style="color: #a78bfa;">%${dims.volatility.similarity_pct} Benzerlik</b> (Fark: %${dims.volatility.realized_vol_gap_pct})</td>
            <td>${dims.volatility.explanation_tr}</td>
          </tr>
          <tr>
            <td><b>Ortalama Getiri</b></td>
            <td>%${data.session_a.mean_return_pct}</td>
            <td>%${data.session_b.mean_return_pct}</td>
            <td>Fark: %${dims.return_mean.mean_return_gap_pct}</td>
            <td>${dims.return_mean.explanation_tr}</td>
          </tr>
          <tr>
            <td><b>Makro Olay Sayısı</b></td>
            <td>${data.session_a.macro_events_count} olay</td>
            <td>${data.session_b.macro_events_count} olay</td>
            <td>${dims.macro_context.events_a_count} vs ${dims.macro_context.events_b_count}</td>
            <td>${dims.macro_context.explanation_tr}</td>
          </tr>
        `;
        document.getElementById('urs-cmp-tbody').innerHTML = tbHtml;
      } catch (e) {
        document.getElementById('urs-cmp-synthesis').textContent = 'HATA: ' + e.message;
      }
    }

    async function exportUnifiedEvidencePackage() {
      if (!currentUrsSession) {
        alert('Lütfen önce bir araştırma oturumu yürütün.');
        return;
      }
      try {
        let url = `/api/v1/product/research-workspace/evidence?session_id=${encodeURIComponent(currentUrsSession.session_id)}`;
        if (currentUrsComparison && currentUrsComparison.session_b && currentUrsComparison.session_b.session_id) {
          url += `&session_b_id=${encodeURIComponent(currentUrsComparison.session_b.session_id)}`;
        }
        const res = await fetch(url);
        if (!res.ok) throw new Error('Kanıt paketi dışa aktarma hatası: ' + res.status);
        const pkg = await res.json();

        const jsonStr = JSON.stringify(pkg, null, 2);
        const blob = new Blob([jsonStr], { type: 'application/json' });
        const a = document.createElement('a');
        a.href = URL.createObjectURL(blob);
        a.download = `CBE_UNIFIED_EVIDENCE_${pkg.package_id}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
      } catch (e) {
        alert('Dışa aktarma hatası: ' + e.message);
      }
    }
'''

js_target = '    window.addEventListener("DOMContentLoaded", () => {'
if crlf == "\r\n":
    js_target = js_target.replace("\n", "\r\n")
    js_code = js_code.replace("\n", "\r\n")

if js_target not in text:
    raise RuntimeError("Could not find js_target in dashboard_ui.py")

text = text.replace(js_target, js_code + crlf + js_target, 1)

path.write_text(text, encoding="utf-8")
print("Successfully patched dashboard_ui.py for Sprint 18!")

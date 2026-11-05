"""
Sprint Product Acceleration 19 — Research Intelligence Explorer V1 & Research Library V1 UI.

Renders:
1. Interactive Historical Candlestick, Volume, Regime Overlays & Macro-Event Markers (SVG/JS)
2. Interactive Time Navigation, Zoom/Pan, and Drag-to-Select Brush
3. Selected Period Research Session & Pattern Discovery Orchestration HUD
4. Comparison Studio V2 (Side-by-Side Dual Time & Normalized Elapsed Progress Base-100)
5. Research Library V1 (Search, Filter, Save, Open, Rename, Duplicate, Export, Import, Delete)
6. Research Intelligence Scientific Explanation Cards in clear, descriptive Turkish
"""

from __future__ import annotations


def render_research_explorer_styles() -> str:
    """CSS styles for the Research Intelligence Explorer and Research Library."""
    return """
    /* Research Explorer V1 Styles */
    .explorer-chart-wrapper {
      position: relative;
      background: #090d16;
      border: 1px solid #1e293b;
      border-radius: 10px;
      overflow: hidden;
      margin-bottom: 20px;
    }
    .explorer-svg-container {
      width: 100%;
      height: 480px;
      cursor: crosshair;
      user-select: none;
    }
    .chart-tooltip {
      position: absolute;
      display: none;
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid #38bdf8;
      border-radius: 8px;
      padding: 10px 14px;
      font-size: 12px;
      color: #f1f5f9;
      pointer-events: none;
      z-index: 100;
      box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.5);
      max-width: 320px;
      line-height: 1.4;
    }
    .regime-legend-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 600;
      margin-right: 6px;
      margin-bottom: 6px;
    }
    .selection-hud {
      background: #0f172a;
      border: 1px solid #38bdf8;
      border-radius: 8px;
      padding: 14px 18px;
      margin-bottom: 20px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
    }
    .library-card {
      background: #0d1322;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 14px;
      margin-bottom: 12px;
      transition: all 0.15s ease;
    }
    .library-card:hover {
      border-color: #38bdf8;
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(0,0,0,0.3);
    }
    .comp-dual-container {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
      margin-bottom: 20px;
    }
    @media (max-width: 900px) {
      .comp-dual-container {
        grid-template-columns: 1fr;
      }
    }
    """


def render_research_explorer_html() -> str:
    """Render the full HTML template for the Research Intelligence Explorer tab."""
    return """
    <!-- =================================================================== -->
    <!-- MODULE: RESEARCH INTELLIGENCE EXPLORER V1 & LIBRARY (SPRINT 19)     -->
    <!-- =================================================================== -->
    <section id="module-research-explorer" class="tab-content">

      <!-- Executive Header Card -->
      <div class="card" style="border-left: 4px solid #818cf8; margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
          <div>
            <div style="font-size: 11px; font-weight: 700; color: #818cf8; letter-spacing: 0.5px;">ARAŞTIRMA İSTİHBARAT GEZGİNİ V1 & KÜTÜPHANE (SPRINT 19)</div>
            <h2 style="font-size: 20px; font-weight: 700; margin: 4px 0 6px 0; color: #f8fafc;">
              🔭 İnteraktif Tarihsel Piyasa Gezgini, Karşılaştırma Stüdyosu V2 & Araştırma Kütüphanesi
            </h2>
            <div style="font-size: 13px; color: #94a3b8; max-width: 950px; line-height: 1.5;">
              Tarihsel BTCUSDT fiyat serilerini, 6 kanonik piyasa rejimini, Parkinson oynaklık katmanlarını ve doğrulanmış makroekonomik olay işaretçilerini interaktif olarak görselleştirin. Grafik üzerinden doğrudan tarihsel dönem seçimi yaparak Birleşik Araştırma Oturumu (URS) başlatın, V2 örüntü keşfini tetikleyin, iki dönemi karşılaştırın ve araştırma tanımlarınızı kütüphanede kalıcı olarak saklayın.
            </div>
          </div>
          <div style="display: flex; flex-direction: column; align-items: flex-end; gap: 6px;">
            <div style="display: flex; gap: 6px;">
              <span class="badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3);">
                🛡️ MODEL: CBE-0.7.0 (FROZEN)
              </span>
              <span class="badge" style="background: rgba(129, 140, 248, 0.15); color: #818cf8; border: 1px solid rgba(129, 140, 248, 0.3);">
                ⚡ SPRINT 19 V1
              </span>
            </div>
            <span class="badge" style="background: rgba(239, 68, 68, 0.15); color: #ef4444; border: 1px solid rgba(239, 68, 68, 0.3);">
              🚫 YALNIZCA TARİHSEL BETİMLEME — SIFIR ALIM-SATIM
            </span>
          </div>
        </div>
      </div>

      <!-- Sprint 23: Operational Status & Session Security Panel -->
      <div class="card" id="operational-status-panel" style="margin-bottom: 20px; background: #0f172a; border: 1px solid #334155; border-radius: 10px; padding: 14px 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
          <div style="display: flex; align-items: center; gap: 14px; flex-wrap: wrap;">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 14px;">🟢</span>
              <span style="font-size: 12px; font-weight: 700; color: #10b981;" id="op-platform-health">PLATFORM: HEALTHY</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 14px;">💾</span>
              <span style="font-size: 12px; font-weight: 700; color: #38bdf8;" id="op-storage-durability">PERSISTENT_VERIFIED</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 14px;">🧊</span>
              <span style="font-size: 12px; font-weight: 700; color: #a78bfa;" id="op-model-freeze">CBE-0.7.0 [STRICTLY_FROZEN]</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 14px;">⚖️</span>
              <span style="font-size: 12px; font-weight: 700; color: #f59e0b;" id="op-governance-decision">TECHNICAL_NO_GO</span>
            </div>
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-size: 14px;">⛔</span>
              <span style="font-size: 12px; font-weight: 700; color: #ef4444;" id="op-trading-eligibility">ALIM-SATIM: PERMANENTLY_PROHIBITED</span>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 10px;">
            <div id="session-active-controls" style="display: none; align-items: center; gap: 8px;">
              <span class="badge" style="background: rgba(16, 185, 129, 0.2); color: #10b981; border: 1px solid #10b981; font-size: 11px;">
                🔐 Oturum Aktif (<span id="session-id-display">...</span>)
              </span>
              <span id="session-csrf-badge" class="badge" style="background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid #38bdf8; font-size: 11px;">
                🛡️ CSRF Korumalı
              </span>
              <button class="btn btn-sm btn-secondary" onclick="sessionLogout()" style="padding: 3px 8px; font-size: 11px;">Çıkış</button>
            </div>
            <div id="session-login-controls" style="display: flex; align-items: center; gap: 8px;">
              <input type="password" id="session-operator-token-input" placeholder="Operatör Belirteci..." style="background: #1e293b; border: 1px solid #475569; border-radius: 4px; padding: 4px 8px; color: #f8fafc; font-size: 11px; width: 160px;" />
              <button class="btn btn-sm btn-primary" onclick="sessionLogin()" style="padding: 4px 10px; font-size: 11px; background: #6366f1;">Oturum Aç</button>
            </div>
          </div>
        </div>
      </div>

      <!-- Sprint 20: Guided Research Journey Workflow Navigation Header -->
      <div class="card" id="workflow-journey-card" style="margin-bottom: 20px; background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%); border: 1px solid #4338ca; border-radius: 12px; padding: 18px 24px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 14px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 20px;">🧭</span>
            <div>
              <div style="font-size: 14px; font-weight: 700; color: #e0e7ff; letter-spacing: 0.5px;">BİRLEŞİK ARAŞTIRMA YOLCULUĞU (RESEARCH WORKFLOW V1)</div>
              <div style="font-size: 12px; color: #a5b4fc;" id="workflow-id-badge">İş Akışı Kimliği: Hazırlanıyor...</div>
            </div>
          </div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <span id="workflow-stage-pill" class="badge" style="background: rgba(99, 102, 241, 0.25); color: #c7d2fe; border: 1px solid #6366f1; font-weight: 700; padding: 6px 12px; font-size: 12px;">
              Aşama: BAŞLANGIÇ
            </span>
            <button class="btn btn-sm btn-secondary" onclick="workflowResetJourney()" title="İş akışını sıfırla">🔄 Sıfırla</button>
          </div>
        </div>

        <!-- 5-Step Visual Stepper Bar -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 10px; margin-top: 10px;">
          <!-- Step 1: Historical Period -->
          <div id="step-node-1" class="workflow-step-node active" onclick="workflowNavigateStep(1)" style="background: #1e293b; border: 1px solid #475569; border-radius: 8px; padding: 10px 14px; cursor: pointer; transition: all 0.2s;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span id="step-num-1" style="background: #6366f1; color: white; border-radius: 50%; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700;">1</span>
              <span style="font-size: 13px; font-weight: 600; color: #f8fafc;">Tarihsel Dönem</span>
            </div>
            <div id="step-desc-1" style="font-size: 11px; color: #94a3b8; margin-top: 4px; margin-left: 30px;">Dönem Seçimi & Gezinti</div>
          </div>

          <!-- Step 2: Research Analysis -->
          <div id="step-node-2" class="workflow-step-node" onclick="workflowNavigateStep(2)" style="background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px 14px; cursor: pointer; transition: all 0.2s;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span id="step-num-2" style="background: #334155; color: #94a3b8; border-radius: 50%; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700;">2</span>
              <span style="font-size: 13px; font-weight: 600; color: #cbd5e1;">Araştırma Analizi</span>
            </div>
            <div id="step-desc-2" style="font-size: 11px; color: #64748b; margin-top: 4px; margin-left: 30px;">5 Modüllü URS Oturumu</div>
          </div>

          <!-- Step 3: Similar Patterns -->
          <div id="step-node-3" class="workflow-step-node" onclick="workflowNavigateStep(3)" style="background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px 14px; cursor: pointer; transition: all 0.2s;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span id="step-num-3" style="background: #334155; color: #94a3b8; border-radius: 50%; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700;">3</span>
              <span style="font-size: 13px; font-weight: 600; color: #cbd5e1;">Benzer Örüntüler</span>
            </div>
            <div id="step-desc-3" style="font-size: 11px; color: #64748b; margin-top: 4px; margin-left: 30px;">Pattern Discovery V2</div>
          </div>

          <!-- Step 4: Comparison Studio -->
          <div id="step-node-4" class="workflow-step-node" onclick="workflowNavigateStep(4)" style="background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px 14px; cursor: pointer; transition: all 0.2s;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span id="step-num-4" style="background: #334155; color: #94a3b8; border-radius: 50%; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700;">4</span>
              <span style="font-size: 13px; font-weight: 600; color: #cbd5e1;">Karşılaştırma</span>
            </div>
            <div id="step-desc-4" style="font-size: 11px; color: #64748b; margin-top: 4px; margin-left: 30px;">Base-100 & 5D Benzerlik</div>
          </div>

          <!-- Step 5: Save & Evidence -->
          <div id="step-node-5" class="workflow-step-node" onclick="workflowNavigateStep(5)" style="background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px 14px; cursor: pointer; transition: all 0.2s;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span id="step-num-5" style="background: #334155; color: #94a3b8; border-radius: 50%; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700;">5</span>
              <span style="font-size: 13px; font-weight: 600; color: #cbd5e1;">Kayıt & Kanıt</span>
            </div>
            <div id="step-desc-5" style="font-size: 11px; color: #64748b; margin-top: 4px; margin-left: 30px;">Kütüphane & Kanıt Paketi</div>
          </div>

          <!-- Step 6: Quality Assurance & Reproducibility (Sprint 21) -->
          <div id="step-node-6" class="workflow-step-node" onclick="workflowNavigateStep(6)" style="background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px 14px; cursor: pointer; transition: all 0.2s;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span id="step-num-6" style="background: #334155; color: #94a3b8; border-radius: 50%; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700;">6</span>
              <span style="font-size: 13px; font-weight: 600; color: #cbd5e1;">Kalite Güvencesi</span>
            </div>
            <div id="step-desc-6" style="font-size: 11px; color: #64748b; margin-top: 4px; margin-left: 30px;">Tekrarlanabilirlik & Denetim</div>
          </div>
          <!-- Step 7: Research Intelligence Report (Sprint 22) -->
          <div id="step-node-7" class="workflow-step-node" onclick="workflowNavigateStep(7)" style="background: #0f172a; border: 1px solid #334155; border-radius: 8px; padding: 10px 14px; cursor: pointer; transition: all 0.2s;">
            <div style="display: flex; align-items: center; gap: 8px;">
              <span id="step-num-7" style="background: #334155; color: #94a3b8; border-radius: 50%; width: 22px; height: 22px; display: flex; align-items: center; justify-content: center; font-size: 11px; font-weight: 700;">7</span>
              <span style="font-size: 13px; font-weight: 600; color: #cbd5e1;">Araştırma Raporu</span>
            </div>
            <div id="step-desc-7" style="font-size: 11px; color: #64748b; margin-top: 4px; margin-left: 30px;">Rapor & Kanıt Dışa Aktarımı</div>
          </div>
        </div>

        <!-- Stale Results Warning Banner (Hidden by default) -->
        <div id="workflow-stale-warning" style="display: none; margin-top: 14px; background: rgba(245, 158, 11, 0.15); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 8px; padding: 10px 16px; color: #f59e0b; font-size: 12px; display: flex; align-items: center; justify-content: space-between;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 16px;">⚠️</span>
            <span>Tarih aralığı değiştirildi! Mevcut analiz sonuçları geçersiz kılındı. Lütfen yeni oturumu çalıştırın.</span>
          </div>
          <button class="btn btn-sm btn-primary" onclick="workflowExecuteActiveSession()">Yeni Oturumu Başlat</button>
        </div>
      </div>

      <!-- Presets & Range Navigation Toolbar -->
      <div class="card" style="margin-bottom: 20px; background: #0c1220; border: 1px solid #1e293b;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 14px;">
          <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
            <span style="font-size: 12px; font-weight: 700; color: #94a3b8;">📌 TARİHSEL OLAY ŞABLONLARI:</span>
            <button class="btn btn-sm" onclick="explorerApplyPreset('FED_SHOCK_JUN_2022')">🏛️ Fed 75bps Şoku (Haz 22)</button>
            <button class="btn btn-sm" onclick="explorerApplyPreset('FTX_COLLAPSE_NOV_2022')">💥 FTX Çöküşü (Kas 22)</button>
            <button class="btn btn-sm" onclick="explorerApplyPreset('SVB_BANKING_CRISIS_MAR_2023')">🏦 SVB Kriz Rejimi (Mar 23)</button>
            <button class="btn btn-sm" onclick="explorerApplyPreset('SPOT_ETF_APPROVAL_JAN_2024')">📈 Spot ETF Onayı (Oca 24)</button>
            <button class="btn btn-sm" onclick="explorerApplyPreset('BITCOIN_HALVING_APR_2024')">⛏️ 4. Yarılanma (Nis 24)</button>
            <button class="btn btn-sm" onclick="explorerApplyPreset('YEN_CARRY_UNWIND_AUG_2024')">💴 Yen Arbitraj Tasfiyesi (Ağu 24)</button>
          </div>
          <div style="display: flex; align-items: center; gap: 6px;">
            <span style="font-size: 11px; color: #64748b;">Doğrulanmış Kapsam: 2022-01 — 2026-09</span>
            <span class="badge" style="background: rgba(234, 179, 8, 0.15); color: #eab308; border: 1px solid rgba(234, 179, 8, 0.3); font-size: 10px;">
              🔒 Ekim 2026 Karantina Altında
            </span>
          </div>
        </div>

        <!-- Custom Date Range Form -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)) 120px 140px; gap: 12px; align-items: flex-end;">
          <div>
            <label style="font-size: 11px; font-weight: 600; color: #94a3b8; display: block; margin-bottom: 4px;">Başlangıç (UTC):</label>
            <input type="datetime-local" id="exp-start-utc" class="input" style="width: 100%; font-size: 12px;" value="2022-06-01T00:00">
          </div>
          <div>
            <label style="font-size: 11px; font-weight: 600; color: #94a3b8; display: block; margin-bottom: 4px;">Bitiş (UTC):</label>
            <input type="datetime-local" id="exp-end-utc" class="input" style="width: 100%; font-size: 12px;" value="2022-06-15T00:00">
          </div>
          <div>
            <label style="font-size: 11px; font-weight: 600; color: #94a3b8; display: block; margin-bottom: 4px;">Zaman Aralığı:</label>
            <select id="exp-interval" class="input" style="width: 100%; font-size: 12px;">
              <option value="1h" selected>1 Saatlik (1h)</option>
              <option value="15m">15 Dakikalık (15m)</option>
              <option value="5m">5 Dakikalık (5m)</option>
              <option value="4h">4 Saatlik (4h)</option>
              <option value="1d">1 Günlük (1d)</option>
            </select>
          </div>
          <div>
            <label style="font-size: 11px; font-weight: 600; color: #94a3b8; display: block; margin-bottom: 4px;">Varlık:</label>
            <input type="text" class="input" value="BTCUSDT" disabled style="width: 100%; font-size: 12px; opacity: 0.7;">
          </div>
          <div>
            <button class="btn btn-primary" id="exp-btn-load" onclick="explorerLoadData()" style="width: 100%; justify-content: center; height: 34px;">
              <span>📊</span> Verileri Yükle
            </button>
          </div>
        </div>
      </div>

      <!-- Main Interactive Candlestick Chart Card -->
      <div class="card" style="margin-bottom: 20px; padding: 16px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 12px;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-weight: 700; font-size: 15px; color: #f1f5f9;">📈 BTCUSDT Tarihsel Fiyat & Katman Görünümü</span>
            <span id="exp-coverage-badge" class="badge" style="background: rgba(16, 185, 129, 0.15); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3);">
              Kapsam: %100 (Doğrulandı)
            </span>
            <span id="exp-downsample-badge" class="badge" style="display: none; background: rgba(56, 189, 248, 0.15); color: #38bdf8;">
              İndirgenmiş (Downsampled)
            </span>
          </div>

          <!-- Chart Visual Layer Toggles -->
          <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
            <label style="font-size: 12px; color: #cbd5e1; display: inline-flex; align-items: center; gap: 6px; cursor: pointer;">
              <input type="checkbox" id="exp-toggle-regimes" checked onchange="explorerRedrawChart()">
              <span style="color: #38bdf8; font-weight: 600;">6 Rejim Katmanı</span>
            </label>
            <label style="font-size: 12px; color: #cbd5e1; display: inline-flex; align-items: center; gap: 6px; cursor: pointer;">
              <input type="checkbox" id="exp-toggle-vol" checked onchange="explorerRedrawChart()">
              <span style="color: #a855f7; font-weight: 600;">Parkinson Volatilite</span>
            </label>
            <label style="font-size: 12px; color: #cbd5e1; display: inline-flex; align-items: center; gap: 6px; cursor: pointer;">
              <input type="checkbox" id="exp-toggle-macro" checked onchange="explorerRedrawChart()">
              <span style="color: #f59e0b; font-weight: 600;">Makro Olay İşaretçileri</span>
            </label>
            <label style="font-size: 12px; color: #cbd5e1; display: inline-flex; align-items: center; gap: 6px; cursor: pointer;">
              <input type="checkbox" id="exp-toggle-volume" checked onchange="explorerRedrawChart()">
              <span>İşlem Hacmi</span>
            </label>
          </div>
        </div>

        <!-- Regime Legend Bar -->
        <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; padding: 8px 12px; background: #080d1a; border-radius: 6px; border: 1px solid #1e293b;">
          <span style="font-size: 11px; font-weight: 700; color: #94a3b8; margin-right: 4px; display: inline-flex; align-items: center;">REJİM LEJANTI:</span>
          <span class="regime-legend-pill" style="background: rgba(239, 68, 68, 0.18); color: #ef4444; border: 1px solid #ef4444;">● KAPİTÜLASYON</span>
          <span class="regime-legend-pill" style="background: rgba(249, 115, 22, 0.18); color: #f97316; border: 1px solid #f97316;">● YÜKSEK VOLATİLİTE</span>
          <span class="regime-legend-pill" style="background: rgba(16, 185, 129, 0.18); color: #10b981; border: 1px solid #10b981;">● MOMENTUM GENİŞLEMESİ</span>
          <span class="regime-legend-pill" style="background: rgba(234, 179, 8, 0.18); color: #eab308; border: 1px solid #eab308;">● DAĞITIM</span>
          <span class="regime-legend-pill" style="background: rgba(100, 116, 139, 0.18); color: #94a3b8; border: 1px solid #64748b;">● YATAY / KONSOLİDASYON</span>
          <span class="regime-legend-pill" style="background: rgba(6, 182, 212, 0.18); color: #06b6d4; border: 1px solid #06b6d4;">● TOPARLANMA & BİRİKİM</span>
        </div>

        <!-- The SVG Canvas Chart Container -->
        <div class="explorer-chart-wrapper" id="explorer-chart-container">
          <div id="explorer-loading-overlay" style="display: none; position: absolute; inset: 0; background: rgba(9,13,22,0.8); z-index: 10; display: flex; align-items: center; justify-content: center; flex-direction: column; gap: 8px;">
            <div style="font-size: 24px; animation: spin 1s infinite linear;">⚙️</div>
            <div style="font-size: 13px; color: #38bdf8; font-weight: 600;">Tarihsel Parquet Verileri Yükleniyor...</div>
          </div>
          <svg id="explorer-chart-svg" class="explorer-svg-container" preserveAspectRatio="none">
            <!-- Dynamic elements drawn via JS -->
          </svg>
          <div id="explorer-tooltip" class="chart-tooltip"></div>
        </div>

        <!-- Chart Time Navigation & Zoom Buttons -->
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px; font-size: 12px; color: #94a3b8;">
          <div style="display: flex; gap: 6px; align-items: center;">
            <span>Hızlı Aralık:</span>
            <button class="btn btn-sm" onclick="explorerZoomQuick(7)">7G</button>
            <button class="btn btn-sm" onclick="explorerZoomQuick(14)">14G</button>
            <button class="btn btn-sm" onclick="explorerZoomQuick(30)">30G</button>
            <button class="btn btn-sm" onclick="explorerZoomQuick(90)">90G</button>
            <button class="btn btn-sm" onclick="explorerZoomQuick(365)">1 Yıl</button>
            <button class="btn btn-sm" onclick="explorerZoomQuick(0)">Tümü</button>
          </div>
          <div style="display: flex; gap: 8px; align-items: center;">
            <button class="btn btn-sm" onclick="explorerPan(-0.2)">◀ Sola Kaydır</button>
            <button class="btn btn-sm" onclick="explorerZoom(1.25)">🔍+ Yakınlaş</button>
            <button class="btn btn-sm" onclick="explorerZoom(0.8)">🔍- Uzaklaş</button>
            <button class="btn btn-sm" onclick="explorerPan(0.2)">Sağa Kaydır ▶</button>
          </div>
          <div>
            <span style="font-size: 11px; color: #64748b;">İpucu: Grafik üzerinde fareyle sürükleyerek alt-aralık seçebilirsiniz.</span>
          </div>
        </div>
      </div>

      <!-- Selected Historical Range Orchestration HUD -->
      <div id="explorer-selection-hud" class="selection-hud">
        <div style="display: flex; align-items: center; gap: 14px; flex-wrap: wrap;">
          <div>
            <div style="font-size: 10px; font-weight: 700; color: #38bdf8; letter-spacing: 0.5px;">SEÇİLİ TARİHSEL PENCERE</div>
            <div id="hud-selected-range" style="font-size: 14px; font-weight: 700; color: #f8fafc;">
              2022-06-01T00:00Z → 2022-06-15T00:00Z (336 Saat / 14 Gün)
            </div>
          </div>
          <div style="border-left: 1px solid #334155; padding-left: 14px;">
            <div style="font-size: 10px; font-weight: 700; color: #94a3b8;">GÖZLEM & BASKIN REJİM</div>
            <div id="hud-selected-stats" style="font-size: 13px; font-weight: 600; color: #cbd5e1;">
              337 Bar | Baskın: RECOVERY_ACCUMULATION (%40.9)
            </div>
          </div>
        </div>

        <!-- Integrated Research Action Buttons -->
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <button class="btn btn-primary" onclick="explorerLaunchUnifiedSession()">
            <span>🚀</span> Birleşik Oturum Başlat (URS)
          </button>
          <button class="btn" onclick="explorerLaunchPatternDiscovery()">
            <span>🔍</span> Örüntü Keşfi V2
          </button>
          <button class="btn" onclick="explorerSetComparisonPeriod('A')">
            <span>⚖️</span> Dönem A Yap
          </button>
          <button class="btn" onclick="explorerSetComparisonPeriod('B')">
            <span>⚖️</span> Dönem B Yap
          </button>
          <button class="btn" onclick="explorerOpenSaveLibraryModal()">
            <span>💾</span> Kütüphaneye Kaydet
          </button>
          <button class="btn" onclick="explorerClearSelection()" style="color: #94a3b8;">
            ✕ Temizle
          </button>
        </div>
      </div>

      <!-- Interactive Comparison Studio V2 -->
      <div class="card" style="margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
          <div>
            <div style="font-size: 11px; font-weight: 700; color: #818cf8; letter-spacing: 0.5px;">KARŞILAŞTIRMA STÜDYOSU V2</div>
            <h3 style="font-size: 16px; font-weight: 700; color: #f8fafc; margin: 2px 0 0 0;">
              ⚖️ İki Tarihsel Dönemi Yan Yana veya Normalleştirilmiş İlerleme ile Karşılaştır
            </h3>
          </div>
          <div style="display: flex; gap: 8px; align-items: center;">
            <div style="display: flex; border: 1px solid #334155; border-radius: 6px; overflow: hidden;">
              <button id="comp-mode-dual" class="btn btn-sm" onclick="compSetMode('dual')" style="background: #2563eb; border-radius: 0;">
                Bağımsız UTC Zamanı
              </button>
              <button id="comp-mode-norm" class="btn btn-sm" onclick="compSetMode('norm')" style="background: transparent; border-radius: 0;">
                Normalleştirilmiş İlerleme (Taban 100)
              </button>
            </div>
            <button class="btn btn-primary btn-sm" onclick="compRunComparison()">
              <span>🔄</span> Karşılaştırmayı Çalıştır
            </button>
          </div>
        </div>

        <!-- Period Selectors -->
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px;">
          <!-- Period A Box -->
          <div style="background: #090e1a; padding: 12px; border-radius: 8px; border: 1px solid #1e293b;">
            <div style="font-weight: 700; font-size: 13px; color: #38bdf8; margin-bottom: 8px;">DÖNEM A (Referans / Baz)</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
              <input type="datetime-local" id="comp-start-a" class="input" style="font-size: 12px;" value="2022-06-01T00:00">
              <input type="datetime-local" id="comp-end-a" class="input" style="font-size: 12px;" value="2022-06-15T00:00">
            </div>
          </div>
          <!-- Period B Box -->
          <div style="background: #090e1a; padding: 12px; border-radius: 8px; border: 1px solid #1e293b;">
            <div style="font-weight: 700; font-size: 13px; color: #a855f7; margin-bottom: 8px;">DÖNEM B (Aday / Karşılaştırılan)</div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px;">
              <input type="datetime-local" id="comp-start-b" class="input" style="font-size: 12px;" value="2024-07-27T01:00">
              <input type="datetime-local" id="comp-end-b" class="input" style="font-size: 12px;" value="2024-08-10T01:00">
            </div>
          </div>
        </div>

        <!-- Dual Chart Containers -->
        <div id="comp-dual-view" class="comp-dual-container">
          <div style="background: #090d16; border: 1px solid #1e293b; border-radius: 8px; padding: 10px;">
            <div style="font-size: 12px; font-weight: 700; color: #38bdf8; margin-bottom: 6px;">Dönem A Grafiği</div>
            <svg id="comp-svg-a" style="width: 100%; height: 220px;"></svg>
          </div>
          <div style="background: #090d16; border: 1px solid #1e293b; border-radius: 8px; padding: 10px;">
            <div style="font-size: 12px; font-weight: 700; color: #a855f7; margin-bottom: 6px;">Dönem B Grafiği</div>
            <svg id="comp-svg-b" style="width: 100%; height: 220px;"></svg>
          </div>
        </div>

        <!-- Normalized Overlaid View (Initially Hidden) -->
        <div id="comp-norm-view" style="display: none; background: #090d16; border: 1px solid #1e293b; border-radius: 8px; padding: 12px; margin-bottom: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-size: 12px; font-weight: 700; color: #f8fafc;">Normalleştirilmiş İlerleme Eğrileri (T=0 Başlangıç, Taban 100)</div>
            <div style="display: flex; gap: 12px; font-size: 11px;">
              <span style="color: #38bdf8;">━━━ Dönem A</span>
              <span style="color: #a855f7;">━━━ Dönem B</span>
            </div>
          </div>
          <svg id="comp-svg-norm" style="width: 100%; height: 280px;"></svg>
        </div>

        <!-- Comparison Metrics & 5D Breakdown -->
        <div id="comp-metrics-container" style="display: none; margin-top: 14px;">
          <div class="table-container">
            <table>
              <thead>
                <tr>
                  <th>Boyut / İstatistiksel Metrik</th>
                  <th>Dönem A Değeri</th>
                  <th>Dönem B Değeri</th>
                  <th>Fark / Ayrışım</th>
                  <th>Ağırlık</th>
                  <th>Katkı %</th>
                  <th>Açıklama</th>
                </tr>
              </thead>
              <tbody id="comp-metrics-tbody">
                <!-- Populated via JS -->
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Research Library V1 Card -->
      <div class="card" style="margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
          <div>
            <div style="font-size: 11px; font-weight: 700; color: #10b981; letter-spacing: 0.5px;">ARŞİV & YAPILANDIRMA YÖNETİMİ</div>
            <h3 style="font-size: 16px; font-weight: 700; color: #f8fafc; margin: 2px 0 0 0;">
              📚 Araştırma Kütüphanesi V1 (Kayıtlı Araştırma Tanımları)
            </h3>
          </div>
          <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            <input type="text" id="lib-search-input" class="input" placeholder="Başlığa veya etikete göre ara..." style="width: 220px; font-size: 12px;" oninput="libraryFilter()">
            <select id="lib-interval-filter" class="input" style="font-size: 12px;" onchange="libraryFilter()">
              <option value="">Tüm Aralıklar</option>
              <option value="1h">1h</option>
              <option value="15m">15m</option>
              <option value="5m">5m</option>
              <option value="4h">4h</option>
              <option value="1d">1d</option>
            </select>
            <button class="btn btn-sm" onclick="libraryRefresh()">🔄 Yenile</button>
            <button class="btn btn-primary btn-sm" onclick="explorerOpenSaveLibraryModal()">➕ Yeni Kaydet</button>
            <label class="btn btn-sm" style="cursor: pointer; margin: 0;">
              📥 JSON İçe Aktar
              <input type="file" id="lib-import-file" style="display: none;" accept=".json" onchange="libraryImportJson(event)">
            </label>
          </div>
        </div>

        <!-- Library Items Grid/List -->
        <div id="library-items-container">
          <div style="text-align: center; padding: 24px; color: #64748b; font-size: 13px;">
            Kayıtlı araştırma tanımları taranıyor...
          </div>
        </div>
      </div>

      <!-- Research Intelligence Scientific Explanation Cards -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px;">
        <!-- Card 1 -->
        <div class="card" style="border-top: 3px solid #38bdf8;">
          <div style="font-weight: 700; font-size: 13px; color: #38bdf8; margin-bottom: 6px;">🏛️ Bilimsel Rejim Analizi</div>
          <div style="font-size: 12px; color: #cbd5e1; line-height: 1.5;">
            6 kanonik rejim (Kapitülasyon, Yüksek Volatilite, Momentum, Dağıtım, Yatay, Toparlanma) kural tabanlı dondurulmuş parametrelerle ayrıştırılır. Elde edilen dağılım ve geçiş matrisi retrospektif kalıcılık analizi sunar; gelecekteki rejim yönünü garanti etmez.
          </div>
        </div>

        <!-- Card 2 -->
        <div class="card" style="border-top: 3px solid #a855f7;">
          <div style="font-weight: 700; font-size: 13px; color: #a855f7; margin-bottom: 6px;">📊 Oynaklık ve Kuyruk Riski</div>
          <div style="font-size: 12px; color: #cbd5e1; line-height: 1.5;">
            Parkinson oynaklığı bar içi en yüksek/en düşük salınımları hesaba katarak gerçekleşen getiri sapmasından bağımsız bir oynaklık profili çıkarır. Yüksek basıklık (kurtosis), standart normale kıyasla uç kuyruk olaylarının sıklığını temsil eder.
          </div>
        </div>

        <!-- Card 3 -->
        <div class="card" style="border-top: 3px solid #f59e0b;">
          <div style="font-weight: 700; font-size: 13px; color: #f59e0b; margin-bottom: 6px;">📰 Makroekonomik Taksonomi</div>
          <div style="font-size: 12px; color: #cbd5e1; line-height: 1.5;">
            238 doğrulanmış kanonik makro olay (CPI, FOMC, NFP vb.) tarihsel fiyat serisiyle zaman eşzamanlı ilişkilendirilir. Olay anlarındaki sürpriz katsayıları piyasa reaksiyon genişliğini ve kalıcılığını betimler.
          </div>
        </div>

        <!-- Card 4 -->
        <div class="card" style="border-top: 3px solid #10b981;">
          <div style="font-weight: 700; font-size: 13px; color: #10b981; margin-bottom: 6px;">🛡️ Epistemolojik Holdout İfşası</div>
          <div style="font-size: 12px; color: #cbd5e1; line-height: 1.5;">
            Tarihsel holdout verileri geçmiş araştırmalarda önceden gözlemlendiğinden (exposed), holdout kriterlerini sağlayan spesifikasyonlar bağımsız doğrulayıcı değil, kesinlikle <b>keşifsel (exploratory)</b> olarak sınıflandırılır.
          </div>
        </div>
      </div>

      <!-- =================================================================== -->
      <!-- SPRINT 21: RESEARCH QUALITY ASSURANCE & REPRODUCIBILITY V1 PANEL    -->
      <!-- =================================================================== -->
      <div id="research-quality-assurance-panel" class="card" style="margin-bottom: 20px; border: 1px solid #3b82f6; background: #0a0f1d; border-radius: 12px; padding: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;">
          <div>
            <div style="font-size: 11px; font-weight: 700; color: #60a5fa; letter-spacing: 0.5px;">ARAŞTIRMA KALİTE GÜVENCESİ & TEKRARLANABİLİRLİK V1 (SPRINT 21)</div>
            <h3 style="font-size: 18px; font-weight: 700; color: #f8fafc; margin: 4px 0 0 0;">
              🛡️ Deterministik Doğrulama, Kanıt Bütünlüğü & Bilimsel Kalite Puan Kartı
            </h3>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button class="btn btn-primary btn-sm" onclick="runReproducibilityVerification()" id="btn-run-reproducibility">
              <span>🔬</span> Tekrarlanabilirlik Doğrula
            </button>
            <button class="btn btn-sm" onclick="runScientificAuditScorecard()" id="btn-run-scorecard" style="background: #1e293b; border: 1px solid #475569; color: #f8fafc;">
              <span>📊</span> Kalite Puan Kartı
            </button>
            <button class="btn btn-sm" onclick="runEvidencePackageVerification()" id="btn-verify-evidence" style="background: #1e293b; border: 1px solid #475569; color: #f8fafc;">
              <span>📦</span> Kanıt Bütünlüğü Denetle
            </button>
            <button class="btn btn-sm" onclick="runPerformanceAuditBenchmark()" id="btn-run-performance" style="background: #1e293b; border: 1px solid #475569; color: #f8fafc;">
              <span>⚡</span> Performans Gözlemevi
            </button>
          </div>
        </div>

        <!-- High-level Status Overview Badges -->
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; margin-bottom: 16px;">
          <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px;">
            <div style="font-size: 11px; color: #94a3b8; font-weight: 600;">GENEL KALİTE KAPISI (OVERALL GATE)</div>
            <div id="qsc-overall-gate-badge" style="font-size: 16px; font-weight: 700; color: #38bdf8; margin-top: 4px;">
              BEKLENİYOR
            </div>
            <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Katı kapı: Tek bir FAIL tüm kapıyı FAIL yapar.</div>
          </div>
          <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px;">
            <div style="font-size: 11px; color: #94a3b8; font-weight: 600;">TEKRARLANABİLİRLİK KARARI</div>
            <div id="qsc-reproducibility-badge" style="font-size: 15px; font-weight: 700; color: #10b981; margin-top: 4px;">
              DEĞERLENDİRİLMEDİ
            </div>
            <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Çift çalıştırma & kanonik fark denetimi.</div>
          </div>
          <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px;">
            <div style="font-size: 11px; color: #94a3b8; font-weight: 600;">KANONİK MODEL DONDURMA</div>
            <div style="font-size: 15px; font-weight: 700; color: #10b981; margin-top: 4px;">
              CBE-0.7.0 (FROZEN)
            </div>
            <div style="font-size: 11px; color: #64748b; margin-top: 2px;">0 parametre mutasyonu, kesin dondurulmuş.</div>
          </div>
          <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 12px;">
            <div style="font-size: 11px; color: #94a3b8; font-weight: 600;">HOLDOUT LİNEAGE VE İFŞA</div>
            <div style="font-size: 15px; font-weight: 700; color: #f59e0b; margin-top: 4px;">
              2 Karşılandı / 0 Bağımsız Doğrulama
            </div>
            <div style="font-size: 11px; color: #64748b; margin-top: 2px;">Geçmişte ifşa edilmiş keşifsel kanıt.</div>
          </div>
        </div>

        <!-- 6-Dimensions Scorecard Grid -->
        <div id="qsc-dimensions-grid" style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 12px; margin-bottom: 16px;">
          <!-- Dynamically populated dimension cards -->
        </div>

        <!-- Performance / Tamper Results Container -->
        <div id="quality-aux-results-container" style="display: none; background: #080d1a; border: 1px solid #1e293b; border-radius: 8px; padding: 14px; margin-top: 10px;">
          <!-- Filled dynamically by JS -->
        </div>
      </div>

            <!-- Sprint 22: Step 7 Research Intelligence Report Panel -->
      <div id="research-report-panel" class="card" style="margin-bottom: 20px; border: 1px solid #6366f1; background: #0d1117; border-radius: 12px; padding: 22px;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 18px; border-bottom: 1px solid #334155; padding-bottom: 14px;">
          <div>
            <div style="font-size: 11px; font-weight: 700; color: #818cf8; letter-spacing: 0.05em; text-transform: uppercase;">Sprint 22 • Araştırma Zekası Raporlama & Kanıt Sunumu V1</div>
            <h3 style="font-size: 17px; font-weight: 700; color: #f8fafc; margin-top: 2px;">Bilimsel Araştırma Raporu & Veri Kanıt Paketi</h3>
            <div style="font-size: 12px; color: #94a3b8; margin-top: 2px;">Çevrimdışı HTML, basılabilir A4 PDF ve tahrifat korumalı kanıt paketi oluşturma.</div>
          </div>
          <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
            <button id="btn-generate-research-report" class="btn btn-primary" onclick="generateResearchReport()" style="display: inline-flex; align-items: center; gap: 6px; font-size: 13px; padding: 8px 16px;">
              <span>📑 Rapor Oluştur / Güncelle</span>
            </button>
            <span id="report-status-badge" class="badge" style="background: #1e1b4b; color: #818cf8; border: 1px solid #4f46e5; padding: 6px 12px; font-size: 12px;">HAZIR DEĞİL</span>
          </div>
        </div>

        <!-- Report Overview Bar (Hidden until generated) -->
        <div id="report-overview-container" style="display: none; margin-bottom: 20px;">
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 16px;">
            <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px;">
              <div style="font-size: 11px; color: #8b949e; text-transform: uppercase;">Rapor ID</div>
              <div id="report-id-val" style="font-size: 13px; font-weight: 700; color: #58a6ff; font-family: monospace;">-</div>
            </div>
            <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px;">
              <div style="font-size: 11px; color: #8b949e; text-transform: uppercase;">Tarihsel Kapsam</div>
              <div id="report-period-val" style="font-size: 12px; font-weight: 600; color: #f0f6fc;">-</div>
            </div>
            <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px;">
              <div style="font-size: 11px; color: #8b949e; text-transform: uppercase;">Kanonik Model</div>
              <div style="font-size: 13px; font-weight: 700; color: #3fb950;">CBE-0.7.0 (FROZEN)</div>
            </div>
            <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 12px;">
              <div style="font-size: 11px; color: #8b949e; text-transform: uppercase;">Teknik Karar</div>
              <div style="font-size: 13px; font-weight: 700; color: #f85149;">TECHNICAL_NO_GO</div>
            </div>
          </div>

          <!-- Export Action Buttons -->
          <div style="display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 18px; padding: 12px; background: #161b22; border: 1px solid #30363d; border-radius: 8px;">
            <button id="btn-export-report-html" class="btn btn-secondary" onclick="exportReportHtml()" style="font-size: 12px; padding: 6px 12px;">
              📄 HTML İndir
            </button>
            <button id="btn-export-report-pdf" class="btn btn-secondary" onclick="exportReportPdf()" style="font-size: 12px; padding: 6px 12px;">
              📑 PDF İndir (A4)
            </button>
            <button id="btn-export-report-evidence" class="btn btn-secondary" onclick="exportReportEvidence()" style="font-size: 12px; padding: 6px 12px;">
              📦 Kanıt Paketini İndir
            </button>
            <button id="btn-verify-report-evidence" class="btn btn-secondary" onclick="verifyReportEvidence()" style="font-size: 12px; padding: 6px 12px; border-color: #3fb950; color: #3fb950;">
              🛡️ Kanıt Bütünlüğünü Doğrula
            </button>
            <div style="display: flex; align-items: center; gap: 6px;">
              <select id="report-library-select" style="background: #0d1117; color: #c9d1d9; border: 1px solid #30363d; border-radius: 6px; padding: 5px 8px; font-size: 11px; max-width: 220px;">
                <option value="">-- Araştırma Tanımı Seçiniz --</option>
              </select>
              <button id="btn-save-report-to-library" class="btn btn-secondary" onclick="saveReportToLibrary()" style="font-size: 12px; padding: 6px 12px;">
                💾 Kütüphaneye Kaydet
              </button>
            </div>
          </div>

          <!-- Section 1: Executive Summary -->
          <div style="margin-bottom: 18px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px;">
            <h4 style="font-size: 14px; font-weight: 700; color: #58a6ff; margin-bottom: 8px;">1. Yönetici Araştırma Özeti</h4>
            <p id="report-exec-summary-text" style="font-size: 13px; color: #c9d1d9; line-height: 1.6; margin: 0; text-align: justify;">-</p>
          </div>

          <!-- Section 2: Regime & Volatility Findings -->
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-bottom: 18px;">
            <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px;">
              <h4 style="font-size: 13px; font-weight: 700; color: #f0f6fc; margin-bottom: 8px;">2. Tarihsel Rejim Yorumu</h4>
              <p id="report-regime-text" style="font-size: 12px; color: #8b949e; line-height: 1.5; margin: 0;">-</p>
            </div>
            <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px;">
              <h4 style="font-size: 13px; font-weight: 700; color: #f0f6fc; margin-bottom: 8px;">3. Parkinson Volatilite Göstergesi</h4>
              <p id="report-volatility-text" style="font-size: 12px; color: #8b949e; line-height: 1.5; margin: 0;">-</p>
            </div>
          </div>

          <!-- Section 3: Pattern Discovery & Disjointness -->
          <div style="margin-bottom: 18px; background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px;">
            <h4 style="font-size: 14px; font-weight: 700; color: #d29922; margin-bottom: 8px;">4. Tarihsel Örüntü Benzerliği ve Ayrıklık</h4>
            <p id="report-pattern-text" style="font-size: 13px; color: #c9d1d9; line-height: 1.6; margin: 0;">-</p>
          </div>

          <!-- Section 4: Evidence Integrity & Disclosures -->
          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 14px; margin-bottom: 18px;">
            <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px;">
              <h4 style="font-size: 13px; font-weight: 700; color: #f0f6fc; margin-bottom: 8px;">5. Holdout ve İstatistiksel Kanıt</h4>
              <p id="report-stats-text" style="font-size: 12px; color: #8b949e; line-height: 1.5; margin: 0;">-</p>
            </div>
            <div style="background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px;">
              <h4 style="font-size: 13px; font-weight: 700; color: #f0f6fc; margin-bottom: 8px;">6. Kanıt Doğrulama & Tahrifat</h4>
              <div id="report-integrity-val" style="font-size: 12px; color: #3fb950; line-height: 1.5;">Doğrulama hazır.</div>
            </div>
          </div>

          <!-- Section 5: Methodology Limitations & Legal Disclaimers -->
          <div style="background: rgba(248, 81, 73, 0.1); border: 1px solid rgba(248, 81, 73, 0.4); border-radius: 8px; padding: 14px;">
            <div style="font-size: 12px; font-weight: 700; color: #f85149; margin-bottom: 4px;">⚠️ Bilimsel Metodoloji Kısıtları & Yasal Bildirim</div>
            <div style="font-size: 11px; color: #ff7b72; line-height: 1.4;">
              Bu raporda yer alan tüm bulgular geçmişe dönük ve betimleyicidir. Geleceğe dönük alım-satım tavsiyesi teşkil etmez.
              Kanonik model CBE-0.7.0 kesin olarak dondurulmuştur. Canlı emir iletimi kalıcı olarak engellenmiştir.
            </div>
          </div>
        </div>
      </div>

      <!-- Save to Library Modal -->
      <div id="lib-save-modal" style="display: none; position: fixed; inset: 0; background: rgba(0,0,0,0.7); z-index: 1000; align-items: center; justify-content: center;">
        <div style="background: #0f172a; border: 1px solid #38bdf8; border-radius: 10px; width: 90%; max-width: 500px; padding: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.6);">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 14px;">
            <h4 style="margin: 0; font-size: 16px; color: #f8fafc;">💾 Araştırma Tanımını Kütüphaneye Kaydet</h4>
            <button onclick="document.getElementById('lib-save-modal').style.display='none'" style="background: none; border: none; color: #94a3b8; font-size: 18px; cursor: pointer;">✕</button>
          </div>
          <div style="margin-bottom: 12px;">
            <label style="font-size: 12px; color: #94a3b8; display: block; margin-bottom: 4px;">Araştırma Başlığı:</label>
            <input type="text" id="modal-save-title" class="input" style="width: 100%;" placeholder="Örn: Haziran 2022 Fed Şoku Rejim Analizi">
          </div>
          <div style="margin-bottom: 12px;">
            <label style="font-size: 12px; color: #94a3b8; display: block; margin-bottom: 4px;">Açıklama / Hipotez Notları:</label>
            <textarea id="modal-save-desc" class="input" style="width: 100%; height: 70px; resize: vertical;" placeholder="Tarihsel gözlem amacı, rejim beklentisi..."></textarea>
          </div>
          <div style="font-size: 11px; color: #64748b; margin-bottom: 16px;">
            Seçili aralık ve konfigürasyon (URS parametreleri) diske atomik JSON olarak kaydedilecek; büyük mum verisi kopyalanmayacaktır.
          </div>
          <div style="display: flex; justify-content: flex-end; gap: 8px;">
            <button class="btn" onclick="document.getElementById('lib-save-modal').style.display='none'">İptal</button>
            <button class="btn btn-primary" onclick="librarySubmitSave()">💾 Kaydet</button>
          </div>
        </div>
      </div>

    </section>
    """


def render_research_explorer_scripts() -> str:
    """JavaScript client logic for the Research Intelligence Explorer and Research Library."""
    return """
    // -------------------------------------------------------------------------
    // Sprint 19: Research Intelligence Explorer Client Engine
    // -------------------------------------------------------------------------

    let expCurrentCandles = [];
    let expCurrentSegments = [];
    let expCurrentEvents = [];
    let expViewWindow = { start: 0, end: 0 };
    let expSelectionBrush = null;
    let expIsBrushing = false;
    let expBrushStartX = 0;
    let compCurrentData = null;
    let compMode = 'dual';

    async function loadResearchExplorer() {
      if (expCurrentCandles.length === 0) {
        await explorerLoadData();
        await libraryRefresh();
      }
    }

    function explorerApplyPreset(presetId) {
      const presets = {
        'FED_SHOCK_JUN_2022': { start: '2022-06-01T00:00', end: '2022-06-15T00:00' },
        'FTX_COLLAPSE_NOV_2022': { start: '2022-11-06T00:00', end: '2022-11-20T00:00' },
        'SVB_BANKING_CRISIS_MAR_2023': { start: '2023-03-08T00:00', end: '2023-03-22T00:00' },
        'SPOT_ETF_APPROVAL_JAN_2024': { start: '2024-01-08T00:00', end: '2024-01-22T00:00' },
        'BITCOIN_HALVING_APR_2024': { start: '2024-04-14T00:00', end: '2024-04-28T00:00' },
        'YEN_CARRY_UNWIND_AUG_2024': { start: '2024-08-01T00:00', end: '2024-08-15T00:00' }
      };
      if (presets[presetId]) {
        document.getElementById('exp-start-utc').value = presets[presetId].start;
        document.getElementById('exp-end-utc').value = presets[presetId].end;
        explorerLoadData();
      }
    }

    async function explorerLoadData() {
      const startStr = document.getElementById('exp-start-utc').value;
      const endStr = document.getElementById('exp-end-utc').value;
      const interval = document.getElementById('exp-interval').value;

      const startUtc = startStr.includes('Z') ? startStr : startStr + ':00Z';
      const endUtc = endStr.includes('Z') ? endStr : endStr + ':00Z';

      const overlay = document.getElementById('explorer-loading-overlay');
      if (overlay) overlay.style.display = 'flex';

      try {
        // 1. Fetch Candlesticks
        const seriesUrl = `/api/v1/product/research-explorer/historical-series?start_utc=${encodeURIComponent(startUtc)}&end_utc=${encodeURIComponent(endUtc)}&interval=${interval}&downsample_max_points=400`;
        const resSeries = await fetch(seriesUrl);
        const dataSeries = await resSeries.json();

        // 2. Fetch Regime Overlays
        const regUrl = `/api/v1/product/research-explorer/regime-overlay?start_utc=${encodeURIComponent(startUtc)}&end_utc=${encodeURIComponent(endUtc)}&interval=${interval}`;
        const resReg = await fetch(regUrl);
        const dataReg = await resReg.json();

        // 3. Fetch Macro Events
        const macUrl = `/api/v1/product/research-explorer/macro-events?start_utc=${encodeURIComponent(startUtc)}&end_utc=${encodeURIComponent(endUtc)}`;
        const resMac = await fetch(macUrl);
        const dataMac = await resMac.json();

        expCurrentCandles = dataSeries.candles || [];
        expCurrentSegments = dataReg.segments || [];
        expCurrentEvents = dataMac.events || [];

        expViewWindow = { start: 0, end: expCurrentCandles.length - 1 };

        // Update badges
        const dsBadge = document.getElementById('exp-downsample-badge');
        if (dsBadge) dsBadge.style.display = dataSeries.downsampled ? 'inline-block' : 'none';

        const covBadge = document.getElementById('exp-coverage-badge');
        if (covBadge) covBadge.textContent = `Kapsam: %${dataSeries.data_coverage_pct || 100} (Doğrulandı)`;

        // Update HUD
        updateSelectionHud(
          dataSeries.reference_start_utc,
          dataSeries.reference_end_utc,
          expCurrentCandles.length,
          dataReg.dominant_regime,
          dataReg.dominant_share_pct
        );

        explorerRedrawChart();
      } catch (err) {
        console.error('explorerLoadData error:', err);
        alert('Veriler yüklenirken hata oluştu: ' + err.message);
      } finally {
        if (overlay) overlay.style.display = 'none';
      }
    }

    function updateSelectionHud(startUtc, endUtc, count, dominantRegime, dominantShare) {
      const hudRange = document.getElementById('hud-selected-range');
      const hudStats = document.getElementById('hud-selected-stats');
      if (hudRange) {
        hudRange.textContent = `${startUtc} → ${endUtc} (${count} Bar)`;
      }
      if (hudStats) {
        hudStats.textContent = `${count} Gözlem | Baskın Rejim: ${dominantRegime || 'SIDEWAYS'} (%${dominantShare || 0})`;
      }
    }

    function explorerRedrawChart() {
      const svg = document.getElementById('explorer-chart-svg');
      if (!svg || expCurrentCandles.length === 0) return;

      const showRegimes = document.getElementById('exp-toggle-regimes')?.checked ?? true;
      const showVol = document.getElementById('exp-toggle-vol')?.checked ?? true;
      const showMacro = document.getElementById('exp-toggle-macro')?.checked ?? true;
      const showVolume = document.getElementById('exp-toggle-volume')?.checked ?? true;

      const width = svg.clientWidth || 1000;
      const height = 480;
      const mainHeight = showVolume ? 360 : 440;
      const volTop = mainHeight + 20;
      const volHeight = height - volTop - 20;

      const visible = expCurrentCandles.slice(expViewWindow.start, expViewWindow.end + 1);
      if (visible.length === 0) return;

      const minPrice = Math.min(...visible.map(c => c.low)) * 0.995;
      const maxPrice = Math.max(...visible.map(c => c.high)) * 1.005;
      const maxVol = Math.max(...visible.map(c => c.volume), 1);
      const maxPVol = Math.max(...visible.map(c => c.parkinson_vol), 0.001);

      const n = visible.length;
      const stepX = (width - 100) / Math.max(1, n);

      let html = '';

      // Grid lines
      for (let i = 0; i <= 5; i++) {
        const y = 20 + (mainHeight - 40) * (i / 5);
        const p = maxPrice - (maxPrice - minPrice) * (i / 5);
        html += `<line x1="60" y1="${y}" x2="${width - 20}" y2="${y}" stroke="#1e293b" stroke-dasharray="3,3" />`;
        html += `<text x="55" y="${y + 4}" fill="#64748b" font-size="10" text-anchor="end">$${p.toFixed(0)}</text>`;
      }

      // Regime Background Bands
      if (showRegimes && expCurrentSegments.length > 0) {
        expCurrentSegments.forEach(seg => {
          const sIdx = Math.max(0, seg.start_index - expViewWindow.start);
          const eIdx = Math.min(n - 1, seg.end_index - expViewWindow.start);
          if (sIdx <= eIdx && sIdx < n && eIdx >= 0) {
            const rx = 60 + sIdx * stepX;
            const rw = Math.max(4, (eIdx - sIdx + 1) * stepX);
            html += `<rect x="${rx}" y="20" width="${rw}" height="${mainHeight - 20}" fill="${seg.bg_rgba}" />`;
          }
        });
      }

      // Macro Event Flags
      if (showMacro && expCurrentEvents.length > 0) {
        expCurrentEvents.forEach(ev => {
          const evTs = ev.release_at_utc;
          const matchIdx = visible.findIndex(c => c.timestamp.startsWith(evTs.substring(0, 13)));
          if (matchIdx !== -1) {
            const mx = 60 + matchIdx * stepX;
            html += `<line x1="${mx}" y1="20" x2="${mx}" y2="${mainHeight}" stroke="#f59e0b" stroke-width="1.5" stroke-dasharray="4,4" />`;
            html += `<circle cx="${mx}" cy="26" r="6" fill="#f59e0b" style="cursor: pointer;" />`;
            html += `<text x="${mx}" y="29" fill="#000" font-size="9" font-weight="bold" text-anchor="middle">★</text>`;
          }
        });
      }

      // Candlesticks
      visible.forEach((c, i) => {
        const cx = 60 + i * stepX;
        const candleW = Math.max(2, Math.min(18, stepX * 0.75));

        const yOpen = 20 + (maxPrice - c.open) / (maxPrice - minPrice) * (mainHeight - 40);
        const yClose = 20 + (maxPrice - c.close) / (maxPrice - minPrice) * (mainHeight - 40);
        const yHigh = 20 + (maxPrice - c.high) / (maxPrice - minPrice) * (mainHeight - 40);
        const yLow = 20 + (maxPrice - c.low) / (maxPrice - minPrice) * (mainHeight - 40);

        const isUp = c.close >= c.open;
        const color = isUp ? '#10b981' : '#ef4444';

        // High-Low Wick
        html += `<line x1="${cx}" y1="${yHigh}" x2="${cx}" y2="${yLow}" stroke="${color}" stroke-width="1.2" />`;

        // Body
        const topY = Math.min(yOpen, yClose);
        const h = Math.max(2, Math.abs(yClose - yOpen));
        html += `<rect x="${cx - candleW / 2}" y="${topY}" width="${candleW}" height="${h}" fill="${color}" rx="1" />`;

        // Volume bar
        if (showVolume) {
          const vH = (c.volume / maxVol) * volHeight;
          const vY = height - 20 - vH;
          html += `<rect x="${cx - candleW / 2}" y="${vY}" width="${candleW}" height="${vH}" fill="${isUp ? 'rgba(16,185,129,0.35)' : 'rgba(239,68,68,0.35)'}" />`;
        }
      });

      // Parkinson Volatility Line Overlay
      if (showVol) {
        let volPath = '';
        visible.forEach((c, i) => {
          const cx = 60 + i * stepX;
          const vScaled = (c.parkinson_vol / maxPVol) * (mainHeight - 80);
          const vy = mainHeight - 20 - vScaled;
          volPath += (i === 0 ? `M ${cx} ${vy}` : ` L ${cx} ${vy}`);
        });
        html += `<path d="${volPath}" fill="none" stroke="#a855f7" stroke-width="1.8" opacity="0.85" />`;
      }

      svg.innerHTML = html;
      attachChartInteractiveEvents(svg, visible, stepX);
    }

    function attachChartInteractiveEvents(svg, visible, stepX) {
      const tooltip = document.getElementById('explorer-tooltip');
      const container = document.getElementById('explorer-chart-container');

      svg.onmousemove = (e) => {
        const rect = svg.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const idx = Math.floor((mouseX - 60 + stepX / 2) / stepX);
        if (idx >= 0 && idx < visible.length) {
          const c = visible[idx];
          if (tooltip && container) {
            tooltip.style.display = 'block';
            tooltip.style.left = Math.min(rect.width - 240, mouseX + 15) + 'px';
            tooltip.style.top = Math.max(10, mouseY - 70) + 'px';
            tooltip.innerHTML = `
              <div style="font-weight:700; color:#38bdf8; border-bottom:1px solid #334155; padding-bottom:3px; margin-bottom:4px;">
                📅 ${c.timestamp}
              </div>
              <div style="display:grid; grid-template-columns: 1fr 1fr; gap:4px;">
                <div>Açılış: <b style="color:#fff;">$${c.open}</b></div>
                <div>Kapanış: <b style="color:${c.close >= c.open ? '#10b981':'#ef4444'};">$${c.close}</b></div>
                <div>En Yüksek: <b style="color:#fff;">$${c.high}</b></div>
                <div>En Düşük: <b style="color:#fff;">$${c.low}</b></div>
              </div>
              <div style="margin-top:4px; font-size:11px;">
                <div>Hacim: <b style="color:#94a3b8;">${c.volume} BTC</b></div>
                <div>Rejim: <span class="badge" style="background:#1e293b; color:#38bdf8; padding:2px 6px;">${c.regime}</span></div>
                <div>Parkinson Vol: <b style="color:#a855f7;">${(c.parkinson_vol * 100).toFixed(2)}%</b></div>
              </div>
            `;
          }
        }
      };

      svg.onmouseleave = () => {
        if (tooltip) tooltip.style.display = 'none';
      };

      // Brush Selection Drag
      svg.onmousedown = (e) => {
        expIsBrushing = true;
        const rect = svg.getBoundingClientRect();
        expBrushStartX = e.clientX - rect.left;
      };

      svg.onmouseup = (e) => {
        if (!expIsBrushing) return;
        expIsBrushing = false;
        const rect = svg.getBoundingClientRect();
        const endX = e.clientX - rect.left;
        const x1 = Math.min(expBrushStartX, endX);
        const x2 = Math.max(expBrushStartX, endX);

        if (Math.abs(x2 - x1) > 20) {
          const idx1 = Math.max(0, Math.floor((x1 - 60) / stepX));
          const idx2 = Math.min(visible.length - 1, Math.floor((x2 - 60) / stepX));
          if (idx1 < idx2) {
            const selectedCandles = visible.slice(idx1, idx2 + 1);
            const startUtc = selectedCandles[0].timestamp;
            const endUtc = selectedCandles[selectedCandles.length - 1].timestamp;
            document.getElementById('exp-start-utc').value = startUtc.substring(0, 16);
            document.getElementById('exp-end-utc').value = endUtc.substring(0, 16);
            updateSelectionHud(startUtc, endUtc, selectedCandles.length, selectedCandles[0].regime, 40);
          }
        }
      };
    }

    function explorerZoom(factor) {
      const len = expCurrentCandles.length;
      if (len === 0) return;
      const curSpan = expViewWindow.end - expViewWindow.start;
      const newSpan = Math.max(10, Math.min(len - 1, Math.round(curSpan / factor)));
      const mid = Math.round((expViewWindow.start + expViewWindow.end) / 2);
      expViewWindow.start = Math.max(0, mid - Math.round(newSpan / 2));
      expViewWindow.end = Math.min(len - 1, expViewWindow.start + newSpan);
      explorerRedrawChart();
    }

    function explorerPan(fraction) {
      const len = expCurrentCandles.length;
      if (len === 0) return;
      const span = expViewWindow.end - expViewWindow.start;
      const shift = Math.round(span * fraction);
      let newStart = expViewWindow.start + shift;
      let newEnd = expViewWindow.end + shift;
      if (newStart < 0) { newStart = 0; newEnd = span; }
      if (newEnd >= len) { newEnd = len - 1; newStart = Math.max(0, len - 1 - span); }
      expViewWindow.start = newStart;
      expViewWindow.end = newEnd;
      explorerRedrawChart();
    }

    function explorerZoomQuick(days) {
      const len = expCurrentCandles.length;
      if (len === 0) return;
      if (days === 0) {
        expViewWindow = { start: 0, end: len - 1 };
      } else {
        const bars = days * 24;
        expViewWindow.end = len - 1;
        expViewWindow.start = Math.max(0, len - 1 - bars);
      }
      explorerRedrawChart();
    }

    function explorerClearSelection() {
      if (expCurrentCandles.length > 0) {
        const start = expCurrentCandles[0].timestamp;
        const end = expCurrentCandles[expCurrentCandles.length - 1].timestamp;
        document.getElementById('exp-start-utc').value = start.substring(0, 16);
        document.getElementById('exp-end-utc').value = end.substring(0, 16);
        updateSelectionHud(start, end, expCurrentCandles.length, expCurrentCandles[0].regime, 35);
      }
    }

    // -------------------------------------------------------------------------
    // Comparison Studio V2 Client Methods
    // -------------------------------------------------------------------------

    function explorerSetComparisonPeriod(periodKey) {
      const start = document.getElementById('exp-start-utc').value;
      const end = document.getElementById('exp-end-utc').value;
      if (periodKey === 'A') {
        document.getElementById('comp-start-a').value = start;
        document.getElementById('comp-end-a').value = end;
        alert('Seçili aralık Karşılaştırma Dönem A olarak ayarlandı!');
      } else {
        document.getElementById('comp-start-b').value = start;
        document.getElementById('comp-end-b').value = end;
        alert('Seçili aralık Karşılaştırma Dönem B olarak ayarlandı!');
      }
    }

    function compSetMode(mode) {
      compMode = mode;
      document.getElementById('comp-mode-dual').style.background = mode === 'dual' ? '#2563eb' : 'transparent';
      document.getElementById('comp-mode-norm').style.background = mode === 'norm' ? '#2563eb' : 'transparent';
      document.getElementById('comp-dual-view').style.display = mode === 'dual' ? 'grid' : 'none';
      document.getElementById('comp-norm-view').style.display = mode === 'norm' ? 'block' : 'none';
    }

    async function compRunComparison() {
      const sa = document.getElementById('comp-start-a').value + ':00Z';
      const ea = document.getElementById('comp-end-a').value + ':00Z';
      const sb = document.getElementById('comp-start-b').value + ':00Z';
      const eb = document.getElementById('comp-end-b').value + ':00Z';

      try {
        const url = `/api/v1/product/research-explorer/comparison?start_utc_a=${encodeURIComponent(sa)}&end_utc_a=${encodeURIComponent(ea)}&start_utc_b=${encodeURIComponent(sb)}&end_utc_b=${encodeURIComponent(eb)}`;
        const res = await fetch(url);
        const data = await res.json();
        compCurrentData = data;

        renderComparisonCharts(data);
        renderComparisonMetrics(data);
      } catch (err) {
        console.error('compRunComparison error:', err);
        alert('Karşılaştırma hesaplanırken hata: ' + err.message);
      }
    }

    function renderComparisonCharts(data) {
      renderMiniChart('comp-svg-a', data.period_a?.candles || [], '#38bdf8');
      renderMiniChart('comp-svg-b', data.period_b?.candles || [], '#a855f7');
      renderNormalizedChart('comp-svg-norm', data.period_a?.normalized_series || [], data.period_b?.normalized_series || []);
    }

    function renderMiniChart(svgId, candles, color) {
      const svg = document.getElementById(svgId);
      if (!svg || candles.length === 0) return;
      const w = svg.clientWidth || 400;
      const h = 200;
      const minP = Math.min(...candles.map(c => c.low));
      const maxP = Math.max(...candles.map(c => c.high));
      const step = w / Math.max(1, candles.length);

      let path = '';
      candles.forEach((c, i) => {
        const x = i * step;
        const y = h - ((c.close - minP) / (maxP - minP || 1)) * (h - 20) - 10;
        path += (i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`);
      });
      svg.innerHTML = `
        <path d="${path}" fill="none" stroke="${color}" stroke-width="2" />
        <text x="10" y="20" fill="#94a3b8" font-size="11">Fiyat: $${minP.toFixed(0)} - $${maxP.toFixed(0)}</text>
      `;
    }

    function renderNormalizedChart(svgId, normA, normB) {
      const svg = document.getElementById(svgId);
      if (!svg) return;
      const w = svg.clientWidth || 800;
      const h = 260;
      const allVals = [...normA.map(p => p.normalized_index_base_100), ...normB.map(p => p.normalized_index_base_100)];
      const minV = Math.min(...allVals, 90);
      const maxV = Math.max(...allVals, 110);

      let pA = '', pB = '';
      normA.forEach((p, i) => {
        const x = 50 + (p.elapsed_progress_pct / 100) * (w - 70);
        const y = h - 30 - ((p.normalized_index_base_100 - minV) / (maxV - minV || 1)) * (h - 60);
        pA += (i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`);
      });

      normB.forEach((p, i) => {
        const x = 50 + (p.elapsed_progress_pct / 100) * (w - 70);
        const y = h - 30 - ((p.normalized_index_base_100 - minV) / (maxV - minV || 1)) * (h - 60);
        pB += (i === 0 ? `M ${x} ${y}` : ` L ${x} ${y}`);
      });

      svg.innerHTML = `
        <line x1="50" y1="20" x2="50" y2="${h-30}" stroke="#334155" />
        <line x1="50" y1="${h-30}" x2="${w-20}" y2="${h-30}" stroke="#334155" />
        <path d="${pA}" fill="none" stroke="#38bdf8" stroke-width="2" />
        <path d="${pB}" fill="none" stroke="#a855f7" stroke-width="2" />
        <text x="10" y="30" fill="#64748b" font-size="10">${maxV.toFixed(1)}</text>
        <text x="10" y="${h-30}" fill="#64748b" font-size="10">${minV.toFixed(1)}</text>
        <text x="50" y="${h-10}" fill="#64748b" font-size="10">%0 Başlangıç</text>
        <text x="${w-60}" y="${h-10}" fill="#64748b" font-size="10">%100 Bitiş</text>
      `;
    }

    function renderComparisonMetrics(data) {
      const container = document.getElementById('comp-metrics-container');
      const tbody = document.getElementById('comp-metrics-tbody');
      if (!container || !tbody) return;

      container.style.display = 'block';
      const m = data.comparison_metrics || {};
      const dims = data.dimension_breakdown || [];

      let rows = `
        <tr>
          <td><b>Rejim Dağılım Ayrışımı (JSD)</b></td>
          <td>Dönem A Rejimleri</td>
          <td>Dönem B Rejimleri</td>
          <td><b style="color:#38bdf8;">${m.regime_jsd_divergence || 0}</b></td>
          <td>0.30</td>
          <td>-</td>
          <td>Jensen-Shannon simetrik olasılık ıraksaması (0=özdeş, 1=ayrık).</td>
        </tr>
        <tr>
          <td><b>Volatilite Açıklığı (Parkinson / Gerçekleşen)</b></td>
          <td>-</td>
          <td>-</td>
          <td><b style="color:#a855f7;">%${m.volatility_gap_pct || 0}</b></td>
          <td>0.25</td>
          <td>-</td>
          <td>İki dönem arasındaki yıllıklandırılmış oynaklık farkı.</td>
        </tr>
        <tr>
          <td><b>Getiri Ortalaması Farkı</b></td>
          <td>-</td>
          <td>-</td>
          <td><b>%${m.return_mean_diff_pct || 0}</b></td>
          <td>0.20</td>
          <td>-</td>
          <td>Bar bazlı getiri ortalamaları arasındaki fark.</td>
        </tr>
      `;

      dims.forEach(d => {
        rows += `
          <tr>
            <td>${d.dimension_name_tr || d.dimension_id}</td>
            <td>${d.reference_value || '-'}</td>
            <td>${d.candidate_value || '-'}</td>
            <td>${d.distance_value || '-'}</td>
            <td>${d.weight}</td>
            <td><b style="color:#10b981;">%${d.contribution_pct}</b></td>
            <td>${d.explanation_tr || ''}</td>
          </tr>
        `;
      });

      tbody.innerHTML = rows;
    }

    // -------------------------------------------------------------------------
    // Session Security & Authentication (Sprint 23)
    // -------------------------------------------------------------------------
    window.cbeSessionId = '';
    window.cbeCsrfToken = '';

    function getAuthHeaders(contentType = 'application/json') {
      const headers = {};
      if (contentType) headers['Content-Type'] = contentType;
      if (window.cbeCsrfToken) headers['X-CSRF-Token'] = window.cbeCsrfToken;
      if (window.cbeSessionId) headers['X-Session-ID'] = window.cbeSessionId;
      const opToken = (document.getElementById('session-operator-token-input')?.value || document.getElementById('ops-token-input')?.value || '').trim();
      if (opToken) headers['X-Operator-Token'] = opToken;
      return headers;
    }

    async function sessionLogin() {
      const tokInput = document.getElementById('session-operator-token-input');
      const token = (tokInput ? tokInput.value : '').trim();
      if (!token) {
        alert('Lütfen geçerli bir operatör belirteci giriniz.');
        return;
      }
      try {
        const res = await fetch('/api/v1/product/session/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ operator_token: token })
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          alert('Oturum açma başarısız: ' + (err.message || res.statusText));
          return;
        }
        const data = await res.json();
        window.cbeSessionId = data.session_id || '';
        window.cbeCsrfToken = data.csrf_token || '';
        if (tokInput) tokInput.value = '';
        updateSessionUI(true, data.session_id);
      } catch (e) {
        alert('Oturum açma hatası: ' + e.message);
      }
    }

    async function sessionLogout() {
      try {
        await fetch('/api/v1/product/session/logout', {
          method: 'POST',
          headers: getAuthHeaders()
        });
        window.cbeSessionId = '';
        window.cbeCsrfToken = '';
        updateSessionUI(false, null);
      } catch (e) {
        console.error('Logout error:', e);
      }
    }

    async function checkSessionStatus() {
      try {
        const res = await fetch('/api/v1/product/session/status');
        if (res.ok) {
          const data = await res.json();
          if (data.authenticated) {
            window.cbeSessionId = data.session_id || '';
            window.cbeCsrfToken = data.csrf_token || '';
            updateSessionUI(true, data.session_id);
            return;
          }
        }
        updateSessionUI(false, null);
      } catch (e) {
        updateSessionUI(false, null);
      }
    }

    function updateSessionUI(isAuthed, sessionId) {
      const loginBox = document.getElementById('session-login-controls');
      const activeBox = document.getElementById('session-active-controls');
      const sidSpan = document.getElementById('session-id-display');
      const csrfBadge = document.getElementById('session-csrf-badge');
      if (isAuthed) {
        if (loginBox) loginBox.style.display = 'none';
        if (activeBox) activeBox.style.display = 'flex';
        if (sidSpan) sidSpan.textContent = sessionId ? sessionId.substring(0, 10) + '...' : 'Aktif';
        if (csrfBadge) csrfBadge.style.display = 'inline-block';
      } else {
        if (loginBox) loginBox.style.display = 'flex';
        if (activeBox) activeBox.style.display = 'none';
        if (csrfBadge) csrfBadge.style.display = 'none';
      }
    }

    async function checkOperationalStatus() {
      try {
        const res = await fetch('/ready');
        if (res.ok) {
          const data = await res.json();
          const pHealth = document.getElementById('op-platform-health');
          const sDur = document.getElementById('op-storage-durability');
          if (pHealth) pHealth.textContent = 'PLATFORM: ' + data.status;
          if (sDur && data.storage_durability) sDur.textContent = data.storage_durability;
        }
      } catch (e) {}
    }

    // Initialize session and status checks
    setTimeout(() => {
      checkSessionStatus();
      checkOperationalStatus();
    }, 200);

    // -------------------------------------------------------------------------
    // Research Library V1 Client Methods
    // -------------------------------------------------------------------------

    let libraryCachedItems = [];

    function getLibraryMutationHeaders() {
      const headers = {
        'Content-Type': 'application/json',
        'X-Requested-With': 'CoinBehaviorEngineClient'
      };
      if (window.cbeCsrfToken) headers['X-CSRF-Token'] = window.cbeCsrfToken;
      const opsToken = (document.getElementById('session-operator-token-input')?.value || document.getElementById('ops-token-input')?.value || '').trim();
      if (opsToken) {
        headers['X-Research-Token'] = opsToken;
        headers['X-Operator-Token'] = opsToken;
      }
      return headers;
    }

    async function libraryRefresh() {
      try {
        const res = await fetch('/api/v1/product/research-library');
        const data = await res.json();
        libraryCachedItems = data.items || [];
        libraryRender(libraryCachedItems);
      } catch (err) {
        console.error('libraryRefresh error:', err);
      }
    }

    function libraryFilter() {
      const q = (document.getElementById('lib-search-input')?.value || '').toLowerCase();
      const intv = document.getElementById('lib-interval-filter')?.value || '';

      const filtered = libraryCachedItems.filter(item => {
        const matchQ = !q || item.title.toLowerCase().includes(q) || item.description.toLowerCase().includes(q);
        const matchInt = !intv || item.interval === intv;
        return matchQ && matchInt;
      });
      libraryRender(filtered);
    }

    function libraryRender(items) {
      const container = document.getElementById('library-items-container');
      const selectEl = document.getElementById('report-library-select');
      if (selectEl) {
        const cur = selectEl.value;
        selectEl.innerHTML = '<option value="">-- Araştırma Tanımı Seçiniz --</option>' +
          items.map(it => `<option value="${it.research_id}">${it.title} (${it.research_id})</option>`).join('');
        if (cur) selectEl.value = cur;
      }
      if (!container) return;

      if (items.length === 0) {
        container.innerHTML = `
          <div style="text-align: center; padding: 30px; color: #64748b; font-size: 13px;">
            Kayıtlı araştırma tanımı bulunamadı. "➕ Yeni Kaydet" ile yeni bir yapılandırma ekleyebilirsiniz.
          </div>
        `;
        return;
      }

      let html = '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: 14px;">';
      items.forEach(it => {
        html += `
          <div class="library-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 6px;">
              <span class="badge" style="background:#1e293b; color:#38bdf8; font-family:var(--font-mono); font-size:10px;">
                ${it.research_id}
              </span>
              <span class="badge" style="background:rgba(16,185,129,0.15); color:#10b981; font-size:10px;">
                ${it.interval}
              </span>
            </div>
            <h4 style="margin: 0 0 6px 0; font-size: 14px; color: #f1f5f9;">${it.title}</h4>
            <div style="font-size: 12px; color: #94a3b8; margin-bottom: 8px; line-height: 1.4;">
              ${it.description || 'Açıklama belirtilmedi.'}
            </div>
            <div style="font-size: 11px; color: #64748b; font-family: var(--font-mono); margin-bottom: 10px;">
              📅 ${it.reference_start_utc} → ${it.reference_end_utc}
            </div>
            <div style="display: flex; gap: 6px; flex-wrap: wrap;">
              <button class="btn btn-sm btn-primary" onclick="libraryOpenItem('${it.research_id}')">Aç</button>
              <button class="btn btn-sm" onclick="libraryDuplicate('${it.research_id}')">Kopyala</button>
              <button class="btn btn-sm" onclick="libraryRename('${it.research_id}')">Adlandır</button>
              <button class="btn btn-sm" onclick="libraryExport('${it.research_id}')">Dışa Aktar</button>
              <button class="btn btn-sm btn-danger" onclick="libraryDelete('${it.research_id}')">Sil</button>
            </div>
          </div>
        `;
      });
      html += '</div>';
      container.innerHTML = html;
    }

    function explorerOpenSaveLibraryModal() {
      const modal = document.getElementById('lib-save-modal');
      if (modal) modal.style.display = 'flex';
    }

    async function librarySubmitSave() {
      const title = document.getElementById('modal-save-title')?.value;
      const desc = document.getElementById('modal-save-desc')?.value;
      const start = document.getElementById('exp-start-utc')?.value + ':00Z';
      const end = document.getElementById('exp-end-utc')?.value + ':00Z';
      const interval = document.getElementById('exp-interval')?.value || '1h';

      if (!title) {
        alert('Lütfen bir başlık giriniz.');
        return;
      }

      try {
        const res = await fetch('/api/v1/product/research-library', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            title: title,
            description: desc,
            asset: 'BTCUSDT',
            interval: interval,
            reference_start_utc: start,
            reference_end_utc: end,
            selected_modules: ['regime_analysis', 'volatility_analysis', 'historical_pattern_discovery', 'macro_comparison', 'statistical_evidence']
          })
        });
        const data = await res.json();
        if (res.ok) {
          alert('Araştırma tanımı başarıyla kaydedildi: ' + data.research_id);
          document.getElementById('lib-save-modal').style.display = 'none';
          await libraryRefresh();
        } else {
          alert('Kayıt hatası: ' + (data.message || data.error));
        }
      } catch (err) {
        alert('Bağlantı hatası: ' + err.message);
      }
    }

    async function libraryOpenItem(researchId) {
      const item = libraryCachedItems.find(i => i.research_id === researchId);
      if (item) {
        document.getElementById('exp-start-utc').value = item.reference_start_utc.substring(0, 16);
        document.getElementById('exp-end-utc').value = item.reference_end_utc.substring(0, 16);
        document.getElementById('exp-interval').value = item.interval;
        const selectEl = document.getElementById('report-library-select');
        if (selectEl) selectEl.value = researchId;
        explorerLoadData();

        try {
          const repRes = await fetch(`/api/v1/product/research-library/${encodeURIComponent(researchId)}/reports`, {
            headers: getAuthHeaders()
          });
          if (repRes.ok) {
            const repData = await repRes.json();
            const repList = repData.reports || [];
            if (repList.length > 0) {
              await openSavedReport(repList[0].report_id);
              return;
            }
          }
        } catch (e) {
          console.error('Error fetching definition reports:', e);
        }
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    }

    async function libraryDuplicate(researchId) {
      try {
        const res = await fetch('/api/v1/product/research-library/duplicate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ research_id: researchId })
        });
        if (res.ok) {
          await libraryRefresh();
        } else {
          alert('Kopyalama başarısız oldu.');
        }
      } catch (err) {
        alert('Hata: ' + err.message);
      }
    }

    async function libraryRename(researchId) {
      const newTitle = prompt('Yeni başlığı giriniz:');
      if (!newTitle) return;
      try {
        const res = await fetch(`/api/v1/product/research-library/${researchId}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ title: newTitle })
        });
        if (res.ok) {
          await libraryRefresh();
        } else {
          alert('Güncelleme başarısız oldu.');
        }
      } catch (err) {
        alert('Hata: ' + err.message);
      }
    }

    function libraryExport(researchId) {
      window.open(`/api/v1/product/research-library/export/${researchId}`, '_blank');
    }

    async function libraryDelete(researchId) {
      if (!confirm(`'${researchId}' kimlikli araştırma tanımını silmek istediğinize emin misiniz?`)) return;
      try {
        const res = await fetch(`/api/v1/product/research-library/${researchId}`, {
          method: 'DELETE'
        });
        if (res.ok) {
          await libraryRefresh();
        } else {
          alert('Silme işlemi başarısız oldu.');
        }
      } catch (err) {
        alert('Hata: ' + err.message);
      }
    }

    async function libraryImportJson(event) {
      const file = event.target.files[0];
      if (!file) return;
      const reader = new FileReader();
      reader.onload = async (e) => {
        try {
          const jsonPayload = JSON.parse(e.target.result);
          const res = await fetch('/api/v1/product/research-library/import', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(jsonPayload)
          });
          const data = await res.json();
          if (res.ok) {
            alert('Yapılandırma başarıyla içe aktarıldı: ' + data.research_id);
            await libraryRefresh();
          } else {
            alert('İçe aktarma hatası: ' + (data.message || data.error));
          }
        } catch (err) {
          alert('Geçersiz JSON dosyası: ' + err.message);
        }
      };
      reader.readAsText(file);
    }

    function explorerLaunchUnifiedSession() {
      const start = document.getElementById('exp-start-utc').value + ':00Z';
      const end = document.getElementById('exp-end-utc').value + ':00Z';
      switchTab('unified-workspace');
      // Set values in unified workspace form if present
      const uStart = document.getElementById('urs-start-utc');
      const uEnd = document.getElementById('urs-end-utc');
      if (uStart && uEnd) {
        uStart.value = start.substring(0, 16);
        uEnd.value = end.substring(0, 16);
        if (typeof executeUnifiedSession === 'function') executeUnifiedSession();
      }
    }

    function explorerLaunchPatternDiscovery() {
      switchTab('patterns');
    }
// ---------------------------------------------------------------------------
    // Sprint 20: Unified Research Journey Orchestrator & Context Synchronization
    // ---------------------------------------------------------------------------

    window.cbeWorkflowContext = {
      workflow_id: '',
      stage: 'INITIAL',
      asset: 'BTCUSDT',
      interval: '1h',
      reference_start_utc: '2022-06-01T00:00:00Z',
      reference_end_utc: '2022-06-15T00:00:00Z',
      selected_modules: ['regime_analysis', 'volatility_analysis', 'historical_pattern_discovery', 'macro_event_context', 'statistical_evidence'],
      research_session_id: null,
      pattern_experiment_id: null,
      comparison_reference: null,
      research_library_id: null,
      context_version: 1
    };

    function workflowSyncInputs(startUtc, endUtc, asset, interval) {
      if (startUtc) {
        const inp = document.getElementById('exp-start-utc');
        if (inp) inp.value = startUtc;
        cbeWorkflowContext.reference_start_utc = startUtc;
      }
      if (endUtc) {
        const inp = document.getElementById('exp-end-utc');
        if (inp) inp.value = endUtc;
        cbeWorkflowContext.reference_end_utc = endUtc;
      }
      if (asset) cbeWorkflowContext.asset = asset;
      if (interval) cbeWorkflowContext.interval = interval;

      // Update backend workflow context and validate
      fetch('/api/v1/product/research-workflow/validate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          start_utc: cbeWorkflowContext.reference_start_utc,
          end_utc: cbeWorkflowContext.reference_end_utc,
          asset: cbeWorkflowContext.asset,
          interval: cbeWorkflowContext.interval,
          existing_context: cbeWorkflowContext
        })
      })
      .then(res => res.json())
      .then(data => {
        if (data.workflow_context) {
          cbeWorkflowContext = data.workflow_context;
          workflowUpdateUiStepper();
        }
      })
      .catch(err => console.error('Workflow validation error:', err));
    }

    function workflowUpdateUiStepper() {
      const badge = document.getElementById('workflow-id-badge');
      if (badge && cbeWorkflowContext.workflow_id) {
        badge.innerText = 'İş Akışı Kimliği: ' + cbeWorkflowContext.workflow_id;
      }

      const stagePill = document.getElementById('workflow-stage-pill');
      if (stagePill && cbeWorkflowContext.stage) {
        stagePill.innerText = 'Aşama: ' + cbeWorkflowContext.stage;
      }

      // Step states
      const stage = cbeWorkflowContext.stage;
      const stageOrder = {
        'INITIAL': 1,
        'PERIOD_SELECTED': 1,
        'SESSION_READY': 2,
        'ANALYSIS_COMPLETED': 2,
        'PATTERNS_REVIEWED': 3,
        'COMPARISON_READY': 4,
        'RESEARCH_SAVED': 5,
        'EVIDENCE_EXPORTED': 5
      };

      const currentStep = stageOrder[stage] || 1;

      for (let i = 1; i <= 7; i++) {
        const node = document.getElementById('step-node-' + i);
        const num = document.getElementById('step-num-' + i);
        if (!node || !num) continue;

        if (i < currentStep) {
          // Completed
          node.style.background = 'rgba(16, 185, 129, 0.1)';
          node.style.borderColor = '#10b981';
          num.style.background = '#10b981';
          num.innerHTML = '✓';
        } else if (i === currentStep) {
          // Active
          node.style.background = '#1e293b';
          node.style.borderColor = '#6366f1';
          num.style.background = '#6366f1';
          num.innerHTML = i;
        } else {
          // Inactive
          node.style.background = '#0f172a';
          node.style.borderColor = '#334155';
          num.style.background = '#334155';
          num.innerHTML = i;
        }
      }
    }

    
    // Sprint 22: Research Intelligence Reporting Client Logic
    let currentReportData = null;

    async function generateResearchReport() {
      const b = document.getElementById('btn-generate-research-report');
      if (b) b.disabled = true;
      try {
        const sInput = document.getElementById('exp-start-utc');
        const eInput = document.getElementById('exp-end-utc');
        let startUtc = sInput && sInput.value ? sInput.value : '2022-06-01T00:00:00Z';
        let endUtc = eInput && eInput.value ? eInput.value : '2022-06-15T00:00:00Z';
        if (startUtc.length === 16) startUtc += ':00Z';
        if (endUtc.length === 16) endUtc += ':00Z';

        const body = {
          start_utc: startUtc,
          end_utc: endUtc,
          asset: 'BTCUSDT',
          interval: '1h',
          title: 'Tarihsel Araştırma Raporu (BTCUSDT)'
        };

        const reqHeaders = getAuthHeaders('application/json');

        const res = await fetch('/api/v1/product/research-reports/generate', {
          method: 'POST',
          headers: reqHeaders,
          body: JSON.stringify(body)
        });

        if (!res.ok) {
          throw new Error('Rapor oluşturma hatası: HTTP ' + res.status);
        }

        const report = await res.json();
        currentReportData = report;
        renderReportView(report);
      } catch (err) {
        console.error('generateResearchReport error:', err);
        alert('Rapor oluşturulamadı: ' + err.message);
      } finally {
        if (b) b.disabled = false;
      }
    }

    function renderReportView(report) {
      if (!report) return;
      const meta = report.report_metadata || {};
      const scope = report.historical_scope || {};
      const exec = report.executive_summary || {};
      const regime = report.regime_analysis || {};
      const vol = report.volatility_analysis || {};
      const pattern = report.historical_pattern_discovery || {};
      const stats = report.statistical_evidence || {};

      const cont = document.getElementById('report-overview-container');
      if (cont) cont.style.display = 'block';

      const idVal = document.getElementById('report-id-val');
      if (idVal) idVal.innerText = meta.report_id || '-';

      const perVal = document.getElementById('report-period-val');
      if (perVal) perVal.innerText = (scope.start_utc || '') + ' → ' + (scope.end_utc || '');

      const badge = document.getElementById('report-status-badge');
      if (badge) {
        badge.innerText = meta.state || 'TAMAMLANDI';
        badge.style.background = '#064e3b';
        badge.style.color = '#34d399';
        badge.style.borderColor = '#059669';
      }

      const execText = document.getElementById('report-exec-summary-text');
      if (execText) execText.innerText = exec.narrative_tr || '-';

      const regText = document.getElementById('report-regime-text');
      if (regText) regText.innerText = (regime.narrative && regime.narrative.narrative_tr) || '-';

      const volText = document.getElementById('report-volatility-text');
      if (volText) volText.innerText = (vol.narrative && vol.narrative.narrative_tr) || '-';

      const patText = document.getElementById('report-pattern-text');
      if (patText) patText.innerText = (pattern.narrative && pattern.narrative.narrative_tr) || '-';

      const statsText = document.getElementById('report-stats-text');
      if (statsText) statsText.innerText = (stats.narrative && stats.narrative.narrative_tr) || '-';

      const qp = document.getElementById('research-report-panel');
      if (qp) qp.scrollIntoView({ behavior: 'smooth' });
    }

    function exportReportHtml() {
      if (!currentReportData || !currentReportData.report_metadata) {
        alert('Lütfen önce bir rapor oluşturunuz.');
        return;
      }
      const rid = currentReportData.report_metadata.report_id;
      window.open('/api/v1/product/research-reports/' + rid + '/html', '_blank');
    }

    function exportReportPdf() {
      if (!currentReportData || !currentReportData.report_metadata) {
        alert('Lütfen önce bir rapor oluşturunuz.');
        return;
      }
      const rid = currentReportData.report_metadata.report_id;
      window.open('/api/v1/product/research-reports/' + rid + '/pdf', '_blank');
    }

    async function exportReportEvidence() {
      if (!currentReportData || !currentReportData.report_metadata) {
        alert('Lütfen önce bir rapor oluşturunuz.');
        return;
      }
      const rid = currentReportData.report_metadata.report_id;
      const res = await fetch('/api/v1/product/research-reports/' + rid + '/evidence', { headers: getAuthHeaders() });
      if (res.ok) {
        const bundle = await res.json();
        const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'evidence-bundle-' + rid + '.json';
        a.click();
        URL.revokeObjectURL(url);
      } else {
        alert('Kanıt paketi alınamadı: HTTP ' + res.status);
      }
    }

    async function verifyReportEvidence() {
      if (!currentReportData || !currentReportData.report_metadata) {
        alert('Lütfen önce bir rapor oluşturunuz.');
        return;
      }
      const rid = currentReportData.report_metadata.report_id;
      const reqHeaders = getAuthHeaders('application/json');
      try {
        const res = await fetch('/api/v1/product/research-reports/verify', {
          method: 'POST',
          headers: reqHeaders,
          body: JSON.stringify({ report_id: rid })
        });
        const vres = await res.json();
        const intVal = document.getElementById('report-integrity-val');
        if (intVal) {
          if (vres.verdict === 'VERIFIED_AUTHENTIC' || vres.verdict === 'AUTHENTICITY_VERIFIED') {
            intVal.innerText = '🛡️ DOĞRULANDI: Tahrifat tespit edilmedi. Sağlama: ' + (vres.recomputed_checksum || '').substring(0, 16) + '...';
            intVal.style.color = '#3fb950';
          } else {
            intVal.innerText = '⚠️ TAHRİFAT TESPİT EDİLDİ: ' + (vres.discrepancies || [vres.verdict]).join(', ');
            intVal.style.color = '#f85149';
          }
        }
      } catch (err) {
        alert('Doğrulama hatası: ' + err.message);
      }
    }

    async function openSavedReport(reportId) {
      try {
        const res = await fetch(`/api/v1/product/research-reports/${encodeURIComponent(reportId)}`, { headers: getAuthHeaders() });
        if (res.ok) {
          const report = await res.json();
          currentReportData = report;
          renderReportView(report);
          const rp = document.getElementById('research-report-panel');
          if (rp) {
            rp.style.display = 'block';
            rp.scrollIntoView({ behavior: 'smooth' });
          }
        }
      } catch (err) {
        console.error('Failed to open saved report:', err);
      }
    }

    async function saveReportToLibrary() {
      if (!currentReportData || !currentReportData.report_metadata) {
        alert('Lütfen önce bir rapor oluşturunuz.');
        return;
      }
      const reportId = currentReportData.report_metadata.report_id;
      const selectEl = document.getElementById('report-library-select');
      const researchId = selectEl ? selectEl.value : null;
      if (!researchId) {
        alert('Lütfen raporu kaydetmek için geçerli bir araştırma tanımı seçiniz.');
        return;
      }

      const headers = getAuthHeaders('application/json');

      try {
        const res = await fetch(`/api/v1/product/research-library/${encodeURIComponent(researchId)}/report`, {
          method: 'POST',
          headers: headers,
          body: JSON.stringify({ report_id: reportId })
        });
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          alert('Rapor kaydedilemedi: ' + (errData.message || res.statusText));
          return;
        }
        const data = await res.json();
        alert('Rapor başarıyla araştırma kütüphanesine kaydedildi (ID: ' + reportId + ')');
        await libraryRefresh();
      } catch (err) {
        alert('Ağ hatası: ' + err.message);
      }
    }

    function workflowNavigateStep(stepNum) {
      if (stepNum === 1) {
        switchTab('research-explorer');
        const c = document.getElementById('historical-candlestick-chart');
        if (c) c.scrollIntoView({ behavior: 'smooth' });
      } else if (stepNum === 2) {
        switchTab('unified-workspace');
      } else if (stepNum === 3) {
        switchTab('patterns');
      } else if (stepNum === 4) {
        switchTab('research-explorer');
        const comp = document.getElementById('comparison-studio-container');
        if (comp) comp.scrollIntoView({ behavior: 'smooth' });
      } else if (stepNum === 5) {
        switchTab('research-explorer');
        const lib = document.getElementById('research-library-catalog-container');
        if (lib) lib.scrollIntoView({ behavior: 'smooth' });
      } else if (stepNum === 6) {
        switchTab('research-explorer');
        const qp = document.getElementById('research-quality-assurance-panel');
        if (qp) qp.scrollIntoView({ behavior: 'smooth' });
      } else if (stepNum === 7) {
        switchTab('research-explorer');
        const rp = document.getElementById('research-report-panel');
        if (rp) rp.scrollIntoView({ behavior: 'smooth' });
      }
    }

    // Sprint 21: Research Quality Assurance Client Logic
    async function runReproducibilityVerification() {
      const b = document.getElementById('btn-run-reproducibility');
      if (b) b.disabled = true;
      try {
        const sInput = document.getElementById('exp-start-utc');
        const eInput = document.getElementById('exp-end-utc');
        let startUtc = sInput && sInput.value ? sInput.value : '2022-06-01T00:00:00Z';
        let endUtc = eInput && eInput.value ? eInput.value : '2022-06-15T00:00:00Z';
        if (!startUtc.includes('Z')) startUtc += (startUtc.length === 16 ? ':00Z' : 'Z');
        if (!endUtc.includes('Z')) endUtc += (endUtc.length === 16 ? ':00Z' : 'Z');

        const payload = {
          workflow_context: {
            asset: 'BTCUSDT',
            interval: '1h',
            reference_start_utc: startUtc,
            reference_end_utc: endUtc,
            selected_modules: ['regime_analysis', 'volatility_analysis'],
            canonical_model_version: 'CBE-0.7.0'
          }
        };
        const resp = await fetch('/api/v1/product/research-quality/verify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await resp.json();
        if (data.reproducibility) {
          const rBadge = document.getElementById('qsc-reproducibility-badge');
          if (rBadge) {
            rBadge.textContent = data.reproducibility.verdict;
            rBadge.style.color = data.reproducibility.reproducible ? '#10b981' : '#ef4444';
          }
        }
        if (data.quality_scorecard) {
          renderQualityScorecardUI(data.quality_scorecard);
        }
      } catch (err) {
        console.error('Reproducibility verification error:', err);
      } finally {
        if (b) b.disabled = false;
      }
    }

    async function runScientificAuditScorecard() {
      const b = document.getElementById('btn-run-scorecard');
      if (b) b.disabled = true;
      try {
        const payload = {
          workflow_context: cbeWorkflowContext || {
            asset: 'BTCUSDT',
            interval: '1h',
            reference_start_utc: '2022-06-01T00:00:00Z',
            reference_end_utc: '2022-06-15T00:00:00Z',
            selected_modules: ['regime_analysis', 'volatility_analysis']
          }
        };
        const resp = await fetch('/api/v1/product/research-quality/scientific-audit', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        const data = await resp.json();
        renderQualityScorecardUI(data);
      } catch (err) {
        console.error('Scientific audit scorecard error:', err);
      } finally {
        if (b) b.disabled = false;
      }
    }

    function renderQualityScorecardUI(scorecard) {
      if (!scorecard) return;
      const gBadge = document.getElementById('qsc-overall-gate-badge');
      if (gBadge) {
        gBadge.textContent = scorecard.overall_gate;
        gBadge.style.color = scorecard.overall_gate === 'PASS' ? '#10b981' : (scorecard.overall_gate === 'WARNING' ? '#f59e0b' : '#ef4444');
      }

      const grid = document.getElementById('qsc-dimensions-grid');
      if (!grid || !scorecard.dimensions) return;
      grid.innerHTML = '';

      Object.values(scorecard.dimensions).forEach(dim => {
        const dCard = document.createElement('div');
        dCard.style.cssText = 'background: #0d1322; border: 1px solid #1e293b; border-radius: 8px; padding: 12px;';
        const color = dim.status === 'PASS' ? '#10b981' : (dim.status === 'WARNING' ? '#f59e0b' : '#ef4444');
        dCard.innerHTML = `
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span style="font-size: 12px; font-weight: 700; color: #f8fafc;">${dim.display_title_tr}</span>
            <span class="badge" style="background: rgba(255,255,255,0.08); color: ${color}; font-weight: 700;">${dim.status}</span>
          </div>
          <div style="font-size: 11px; color: #94a3b8; line-height: 1.4;">${dim.description_tr}</div>
          <div style="font-size: 10px; color: #64748b; margin-top: 6px;">Ref: ${dim.evidence_reference}</div>
        `;
        grid.appendChild(dCard);
      });
    }

    async function runEvidencePackageVerification() {
      const container = document.getElementById('quality-aux-results-container');
      if (container) {
        container.style.display = 'block';
        container.innerHTML = '<div style="font-size: 12px; color: #94a3b8;">Kanıt paketi bütünlüğü denetleniyor...</div>';
      }
      try {
        const samplePkg = {
          export_schema_version: 'CBE-WORKFLOW-EVIDENCE-1.0.0',
          workflow_id: cbeWorkflowContext ? cbeWorkflowContext.workflow_id : 'RWF-SAMPLE-01',
          canonical_model: { version: 'CBE-0.7.0', status: 'STRICTLY_FROZEN', parameter_mutations: 0 },
          dataset_provenance: { manifest_sha256: 'fe6c73326c639ee048012cbeb4d50cb9b25014552411ae7a4ef5a57be448ad97', quarantine_status: 'OCTOBER_2026_EXCLUDED' },
          research_specification: { asset: 'BTCUSDT', interval: '1h', reference_start_utc: '2022-06-01T00:00:00Z', reference_end_utc: '2022-06-15T00:00:00Z' },
          scientific_disclosures: { predeclared_holdout_criteria_satisfied: 2, independent_confirmatory_replications: 0, epistemological_limitations: ['Betimsel analiz', 'Tahmin içermez'] }
        };
        // Recompute hash
        const resp = await fetch('/api/v1/product/research-quality/evidence/verify', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ evidence_package: samplePkg })
        });
        const rep = await resp.json();
        if (container) {
          container.innerHTML = `
            <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-bottom: 6px;">📦 Kanıt Paketi Doğrulama Raporu</div>
            <div style="font-size: 12px; color: ${rep.is_valid ? '#10b981' : '#ef4444'};">Durum: ${rep.status} | Sağlama Özeti: ${rep.computed_checksum ? rep.computed_checksum.slice(0, 16) + '...' : 'N/A'}</div>
            <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">${rep.epistemological_boundary_notice}</div>
          `;
        }
      } catch (err) {
        if (container) container.innerHTML = `<div style="font-size: 12px; color: #ef4444;">Doğrulama hatası: ${err}</div>`;
      }
    }

    async function runPerformanceAuditBenchmark() {
      const container = document.getElementById('quality-aux-results-container');
      if (container) {
        container.style.display = 'block';
        container.innerHTML = '<div style="font-size: 12px; color: #94a3b8;">Performans gözlemevi benchmark ölçümleri yapılıyor...</div>';
      }
      const reqHeaders = getAuthHeaders('application/json');
      try {
        const resp = await fetch('/api/v1/product/research-quality/performance-audit', {
          method: 'POST',
          headers: reqHeaders,
          body: JSON.stringify({ start_utc: '2022-06-01T00:00:00Z', end_utc: '2022-06-03T00:00:00Z' })
        });
        const rep = await resp.json();
        if (container) {
          let rows = '';
          if (rep.metrics) {
            Object.values(rep.metrics).forEach(m => {
              const col = m.status === 'PASS' ? '#10b981' : (m.status === 'WARNING' ? '#f59e0b' : '#ef4444');
              rows += `<tr>
                <td style="padding: 4px 8px; border-bottom: 1px solid #1e293b;">${m.display_title_tr}</td>
                <td style="padding: 4px 8px; border-bottom: 1px solid #1e293b;">${m.latency_ms} ms</td>
                <td style="padding: 4px 8px; border-bottom: 1px solid #1e293b;">${m.threshold_ms} ms</td>
                <td style="padding: 4px 8px; border-bottom: 1px solid #1e293b; color: ${col}; font-weight: 700;">${m.status}</td>
              </tr>`;
            });
          }
          container.innerHTML = `
            <div style="font-size: 13px; font-weight: 700; color: #f8fafc; margin-bottom: 6px;">⚡ Performans Gözlemevi Benchmark Sonuçları</div>
            <div style="font-size: 11px; color: #94a3b8; margin-bottom: 8px;">${rep.summary_tr}</div>
            <table style="width: 100%; border-collapse: collapse; font-size: 11px; color: #cbd5e1;">
              <thead>
                <tr style="text-align: left; color: #94a3b8;">
                  <th style="padding: 4px 8px;">Operasyon</th>
                  <th style="padding: 4px 8px;">Gecikme</th>
                  <th style="padding: 4px 8px;">Eşik</th>
                  <th style="padding: 4px 8px;">Durum</th>
                </tr>
              </thead>
              <tbody>${rows}</tbody>
            </table>
          `;
        }
      } catch (err) {
        if (container) container.innerHTML = `<div style="font-size: 12px; color: #ef4444;">Performans benchmark hatası: ${err}</div>`;
      }
    }

    function workflowResetJourney() {
      cbeWorkflowContext = {
        workflow_id: '',
        stage: 'INITIAL',
        asset: 'BTCUSDT',
        interval: '1h',
        reference_start_utc: '2022-06-01T00:00:00Z',
        reference_end_utc: '2022-06-15T00:00:00Z',
        selected_modules: ['regime_analysis', 'volatility_analysis', 'historical_pattern_discovery', 'macro_event_context', 'statistical_evidence'],
        research_session_id: null,
        pattern_experiment_id: null,
        comparison_reference: null,
        research_library_id: null,
        context_version: 1
      };
      workflowSyncInputs('2022-06-01T00:00:00Z', '2022-06-15T00:00:00Z', 'BTCUSDT', '1h');
    }

    // Auto-initialize workflow sync on page load
    document.addEventListener('DOMContentLoaded', function() {
      workflowSyncInputs('2022-06-01T00:00:00Z', '2022-06-15T00:00:00Z', 'BTCUSDT', '1h');
    });
    """

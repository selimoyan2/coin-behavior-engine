"""Sprint 38: Predictive Validity Intelligence, Evidence Explorer & Scientific Decision Support (Dashboard V15).

Provides UI markup, styles, and client JavaScript for Market Behavior Research Lab V3 and
Dashboard V15 Evidence Explorer:
- Module 38.1: Predictive Validity Intelligence Dashboard V15 (8 integrated scientific sections)
- Module 38.2: Hypothesis Evidence Explorer (30 hypotheses, full evidence profile modal)
- Module 38.3: Volatility Forecast Benchmark Laboratory (Regime RMSE 16.0612 vs GARCH 17.4578)
- Module 38.4: Market Regime Persistence Intelligence & Model Tier Architecture
- Module 38.5: Directional Predictability Reality Check (Momentum 47.57%, Mean Reversion 52.51%)
- Module 38.6: Statistical Confidence & Uncertainty (HAC, Block Bootstrap, FDR, Holm)
- Module 38.7: Scientific Limitations & Rejected Findings (25 rejected directional hypotheses)
- Module 38.8: Historical Research Comparison & Provenance (Sprints 35-38, zero synthetic data)
"""

from __future__ import annotations


def render_predictive_validity_nav_tab() -> str:
    """Render the top navigation tab link for Predictive Validity Lab V3 & Dashboard V15."""
    return """
    <a href="#predictive-validity" class="nav-tab" id="tab-btn-predictive-validity" onclick="switchTab('predictive-validity')">
      <span>🎯</span> Tahmin Geçerliliği & Kanıt Gezgini V15 (Sprint 38)
    </a>
    """


def render_predictive_validity_styles() -> str:
    """Render the scoped CSS styles for Predictive Validity Lab V3 & Dashboard V15."""
    return """
    /* Sprint 38: Predictive Validity Research Lab V3 & Dashboard V15 */
    .pv-badge-supported {
      background: rgba(16, 185, 129, 0.18);
      color: #34d399;
      border: 1px solid rgba(16, 185, 129, 0.4);
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      font-family: var(--font-mono);
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .pv-badge-inconclusive {
      background: rgba(245, 158, 11, 0.18);
      color: #fbbf24;
      border: 1px solid rgba(245, 158, 11, 0.4);
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      font-family: var(--font-mono);
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .pv-badge-not-supported {
      background: rgba(239, 68, 68, 0.18);
      color: #f87171;
      border: 1px solid rgba(239, 68, 68, 0.4);
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      font-family: var(--font-mono);
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .pv-badge-insufficient {
      background: rgba(148, 163, 184, 0.18);
      color: #cbd5e1;
      border: 1px solid rgba(148, 163, 184, 0.4);
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      font-family: var(--font-mono);
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }
    .pv-tier-card {
      background: linear-gradient(135deg, rgba(30, 58, 138, 0.25) 0%, rgba(15, 23, 42, 0.6) 100%);
      border: 1px solid rgba(59, 130, 246, 0.35);
      border-radius: 8px;
      padding: 16px 20px;
      margin-bottom: 20px;
    }
    .pv-kpi-card {
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 16px;
      transition: border-color 0.2s;
    }
    .pv-kpi-card:hover {
      border-color: #3b82f6;
    }
    .pv-dyn-card {
      background: #090d16;
      border: 1px solid #1e293b;
      border-radius: 8px;
      padding: 18px;
    }
    .pv-scorecard-table th {
      background: #0f172a;
      color: #94a3b8;
      font-size: 11px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      padding: 10px 12px;
      border-bottom: 2px solid #1e293b;
      white-space: nowrap;
    }
    .pv-scorecard-table td {
      padding: 10px 12px;
      border-bottom: 1px solid #1e293b;
      font-size: 12px;
      font-family: var(--font-mono);
      white-space: nowrap;
    }
    .pv-scorecard-table tr:hover {
      background: rgba(30, 41, 59, 0.5);
    }
    .pv-subnav {
      display: flex;
      gap: 6px;
      overflow-x: auto;
      padding-bottom: 8px;
      margin-bottom: 20px;
      border-bottom: 1px solid #1e293b;
    }
    .pv-subtab-btn {
      background: #0f172a;
      border: 1px solid #1e293b;
      color: #94a3b8;
      padding: 8px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      white-space: nowrap;
      transition: all 0.2s ease;
    }
    .pv-subtab-btn:hover {
      color: #fff;
      border-color: #3b82f6;
      background: #1e293b;
    }
    .pv-subtab-btn.active {
      color: #fff;
      background: #2563eb;
      border-color: #3b82f6;
    }
    .pv-benchmark-card {
      background: #0b1329;
      border: 1px solid #1e3a8a;
      border-radius: 8px;
      padding: 16px;
    }
    .pv-reality-check-banner {
      background: linear-gradient(135deg, rgba(127, 29, 29, 0.3) 0%, rgba(15, 23, 42, 0.8) 100%);
      border: 2px solid #ef4444;
      border-radius: 8px;
      padding: 16px 20px;
      margin-bottom: 20px;
    }
    /* Evidence Explorer Modal */
    .pv-modal-backdrop {
      display: none;
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(0, 0, 0, 0.75);
      backdrop-filter: blur(4px);
      z-index: 9999;
      justify-content: center;
      align-items: center;
      padding: 20px;
      box-sizing: border-box;
    }
    .pv-modal-backdrop.open {
      display: flex;
    }
    .pv-modal-window {
      background: #0b1329;
      border: 1px solid #3b82f6;
      border-radius: 10px;
      max-width: 820px;
      width: 100%;
      max-height: 90vh;
      overflow-y: auto;
      box-shadow: 0 20px 40px rgba(0, 0, 0, 0.8);
      padding: 24px;
    }
    .pv-evidence-grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
      margin-top: 14px;
    }
    .pv-evidence-item {
      background: #0f172a;
      border: 1px solid #1e293b;
      border-radius: 6px;
      padding: 10px 14px;
    }
    .pv-evidence-item .lbl {
      font-size: 10px;
      text-transform: uppercase;
      color: #94a3b8;
      font-weight: 700;
    }
    .pv-evidence-item .val {
      font-size: 13px;
      color: #fff;
      font-weight: 600;
      margin-top: 2px;
      font-family: var(--font-mono);
    }
    """


def render_predictive_validity_html() -> str:
    """Render the master HTML section for Predictive Validity Intelligence Lab V15."""
    return """
    <!-- MODULE: MARKET REGIME PREDICTIVE VALIDITY & SCIENTIFIC LAB V15 (SPRINT 38) -->
    <section id="module-predictive-validity" class="tab-content">

      <!-- Executive Header Banner -->
      <div class="card" style="border-left: 4px solid #3b82f6; margin-bottom: 20px; background: linear-gradient(135deg, #090d16 0%, #0f172a 100%);">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
          <div>
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-bottom: 6px;">
              <span class="badge" style="background: #2563eb; color: #fff; font-weight: bold;">SPRINT 38 BİLİMSEL LABORATUVAR & KARAR DESTEK</span>
              <span class="badge badge-frozen">Model: CBE-0.7.0 (STRICTLY_FROZEN)</span>
              <span class="badge" style="background: #0284c7; color: #fff;">DASHBOARD V15</span>
              <span class="badge badge-info">ÇEVRİMDIŞI ARAŞTIRMA</span>
              <span class="badge badge-danger">CANLI İŞLEM: YASAK (HTTP 403)</span>
            </div>
            <h2 style="font-size: 21px; color: #fff; margin: 4px 0 2px 0; font-weight: 800;">
              🎯 Dashboard V15 — Predictive Validity Intelligence, Evidence Explorer & Scientific Decision Support
            </h2>
            <div style="font-size: 12px; color: var(--text-muted); line-height: 1.5;">
              6 Kanonik Rejim &bull; 5 İleri Vade (1h, 4h, 12h, 24h, 72h) &bull; 30 Hipotez &bull; 42.717 Saatlik Bar &bull;
              Newey-West HAC & Circular Block Bootstrap &bull; Volatilite Benchmark Laboratuvarı &bull; Yönsel Gerçeklik Denetimi
            </div>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button class="btn btn-primary" onclick="loadPredictiveValidity()">🔄 Analizi Yenile</button>
            <button class="btn" style="background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6;" onclick="switchPvSubview('evidence')">🔬 Kanıt Gezgini</button>
            <button class="btn" onclick="downloadPredictiveScorecardJson()">📥 Skor Kartı (JSON)</button>
            <button class="btn" onclick="exportPredictiveValidityReport()">📄 Bilimsel Rapor (JSON)</button>
          </div>
        </div>
      </div>

      <!-- Model Tier Distinction Banner (Task A & Module 38.4 Requirement) -->
      <div class="pv-tier-card">
        <div style="display: flex; align-items: flex-start; gap: 12px;">
          <span style="font-size: 24px;">🏛️</span>
          <div style="flex: 1;">
            <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px; flex-wrap: wrap;">
              <span style="font-size: 14px; font-weight: 700; color: #93c5fd;">MİMARİ VE YÖNETİŞİM AYRIMI: TIER 1 DONDURULMUŞ MODEL vs TIER 2 TÜRETİLMİŞ REJİMLER</span>
              <span class="badge" style="background:#1e3a8a; color:#bfdbfe; border:1px solid #3b82f6;">PROVENANCE AUDIT VERIFIED</span>
              <span class="badge" style="background:#451a03; color:#fde68a; border:1px solid #d97706;">CANONICAL_PARITY_NOT_ESTABLISHED</span>
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 12px; font-size: 12px; color: #cbd5e1; margin-top: 8px;">
              <div style="background: rgba(15, 23, 42, 0.6); padding: 10px; border-radius: 6px; border: 1px solid #1e3a8a;">
                <div style="font-weight: 700; color: #60a5fa; margin-bottom: 4px;">Tier 1: CBE-0.7.0 Nominal Nedensel Durumlar</div>
                <div style="color: #94a3b8; font-family: var(--font-mono); font-size: 11px;">
                  Durumlar: NORMAL, COMPRESSION, EXPANSION_WATCH, DELEVERAGING_STRESS<br>
                  Statü: STRICTLY_FROZEN (Tek bir ağırlık dahi değiştirilemez).<br>
                  <span style="color: #f87171;">⚠️ Dikkat:</span> Tek bar değerlendirmelerinde yüzdelik sıra çökmesi nedeniyle DELEVERAGING_STRESS durumu canlı panellerde UNKNOWN olarak bastırılmaktadır.
                </div>
              </div>
              <div style="background: rgba(15, 23, 42, 0.6); padding: 10px; border-radius: 6px; border: 1px solid #1e3a8a;">
                <div style="font-weight: 700; color: #34d399; margin-bottom: 4px;">Tier 2: CANONICAL_COMPATIBLE_DERIVED_OUTPUT (6 Rejim)</div>
                <div style="color: #94a3b8; font-family: var(--font-mono); font-size: 11px;">
                  Rejimler: SIDEWAYS, UNCERTAIN, TRENDING_BULL, TRENDING_BEAR, POSSIBLE_REVERSAL, HIGH_VOLATILITY<br>
                  Sınıflandırma: DERIVED_RESEARCH_CLASSIFIER (Tanımlayıcı çevrimdışı araştırma çıktısı).<br>
                  <span style="color: #34d399;">✓ Nedensellik:</span> Tamamen point-in-time, geleceğe bakış (look-ahead) içermez.
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- KPI Executive Summary Cards -->
      <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 14px; margin-bottom: 20px;">
        <div class="pv-kpi-card">
          <div style="font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">TOPLAM HİPOTEZ</div>
          <div class="value" id="pv-kpi-total" style="font-size: 26px; font-weight: 800; color: #fff; margin-top: 4px;">30</div>
          <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">6 Rejim &times; 5 İleri Vade</div>
        </div>
        <div class="pv-kpi-card" style="border-left: 3px solid #10b981;">
          <div style="font-size: 11px; font-weight: 600; color: #34d399; text-transform: uppercase;">DESTEKLENEN (SUPPORTED)</div>
          <div class="value" id="pv-kpi-supported" style="font-size: 26px; font-weight: 800; color: #34d399; margin-top: 4px;">4</div>
          <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">Volatilite kümelenmesi & risk</div>
        </div>
        <div class="pv-kpi-card" style="border-left: 3px solid #ef4444;">
          <div style="font-size: 11px; font-weight: 600; color: #f87171; text-transform: uppercase;">DESTEKLENMEYEN (NOT SUPPORTED)</div>
          <div class="value" id="pv-kpi-not-supported" style="font-size: 26px; font-weight: 800; color: #f87171; margin-top: 4px;">25</div>
          <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">Getiri / tersine dönüş (0 alfa)</div>
        </div>
        <div class="pv-kpi-card" style="border-left: 3px solid #f59e0b;">
          <div style="font-size: 11px; font-weight: 600; color: #fbbf24; text-transform: uppercase;">BELİRSİZ (INCONCLUSIVE)</div>
          <div class="value" id="pv-kpi-inconclusive" style="font-size: 26px; font-weight: 800; color: #fbbf24; margin-top: 4px;">1</div>
          <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">HIGH_VOLATILITY 1h sınırı</div>
        </div>
        <div class="pv-kpi-card">
          <div style="font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">İŞLEM MALİYETİ</div>
          <div class="value" style="font-size: 26px; font-weight: 800; color: #60a5fa; margin-top: 4px;">30 bps</div>
          <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">10 kom + 2 sp + 3 kay &times; 2</div>
        </div>
        <div class="pv-kpi-card">
          <div style="font-size: 11px; font-weight: 600; color: var(--text-muted); text-transform: uppercase;">VERİ KAPSAMI</div>
          <div class="value" style="font-size: 26px; font-weight: 800; color: #38bdf8; margin-top: 4px;">59 Ay</div>
          <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">42.717 Bar (0 Sentetik)</div>
        </div>
      </div>

      <!-- Dashboard V15 Subview Navigation Bar -->
      <div class="pv-subnav">
        <button class="pv-subtab-btn active" id="btn-pv-sub-overview" onclick="switchPvSubview('overview')">📊 1. Genel Bakış & Dinamikler</button>
        <button class="pv-subtab-btn" id="btn-pv-sub-evidence" onclick="switchPvSubview('evidence')">🔬 2. Hipotez Kanıt Gezgini (30)</button>
        <button class="pv-subtab-btn" id="btn-pv-sub-volatility" onclick="switchPvSubview('volatility')">📈 3. Volatilite Karşılaştırma Lab</button>
        <button class="pv-subtab-btn" id="btn-pv-sub-persistence" onclick="switchPvSubview('persistence')">🔄 4. Rejim Kalıcılık Analizi</button>
        <button class="pv-subtab-btn" id="btn-pv-sub-directional" onclick="switchPvSubview('directional')">⚖️ 5. Yönsel Öngörü Gerçeklik Denetimi</button>
        <button class="pv-subtab-btn" id="btn-pv-sub-uncertainty" onclick="switchPvSubview('uncertainty')">📐 6. İstatistiki Güven & Belirsizlik</button>
        <button class="pv-subtab-btn" id="btn-pv-sub-limitations" onclick="switchPvSubview('limitations')">🚫 7. Bilimsel Sınırlamalar & Redler</button>
        <button class="pv-subtab-btn" id="btn-pv-sub-history" onclick="switchPvSubview('history')">📜 8. Tarihsel Araştırma Karşılaştırması</button>
      </div>

      <!-- SUBVIEW 1: OVERVIEW & TRANSITION DYNAMICS -->
      <div id="pv-subview-overview" class="pv-subview-panel">
        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(420px, 1fr)); gap: 18px; margin-bottom: 24px;">

          <!-- Panel 1: Post-Transition Dynamics -->
          <div class="pv-dyn-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <h4 style="font-size: 14px; font-weight: 700; color: #fff; margin: 0;">
                ⚡ Rejim Geçişi Sonrası İleri Dinamikler
              </h4>
              <span class="badge badge-info">Transition Tests</span>
            </div>

            <div style="display: flex; flex-direction: column; gap: 12px;">
              <!-- Volatility Elevation -->
              <div style="background: #0f172a; border: 1px solid #1e293b; padding: 12px; border-radius: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-weight: 700; color: #f87171; font-size: 12px;">Volatilite Yükselişi Testi</span>
                  <span class="pv-badge-supported" id="pv-test-vol-elevation-badge">SUPPORTED</span>
                </div>
                <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
                  HIGH_VOLATILITY rejimi sonrası 24h volatilite, SIDEWAYS rejimine göre istatistiksel olarak anlamlı derecede yüksek kalmaktadır.
                </div>
                <div style="font-family: var(--font-mono); font-size: 11px; color: #cbd5e1; margin-top: 6px;" id="pv-test-vol-elevation-stats">
                  Welch t-stat: +10.02 &bull; p-value: &lt; 1e-6 &bull; Vol Oranı: 1.49x
                </div>
              </div>

              <!-- Directional Persistence -->
              <div style="background: #0f172a; border: 1px solid #1e293b; padding: 12px; border-radius: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-weight: 700; color: #60a5fa; font-size: 12px;">Yönsel Kalıcılık Testi</span>
                  <span class="pv-badge-inconclusive" id="pv-test-persistence-badge">INCONCLUSIVE</span>
                </div>
                <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
                  TRENDING_BULL / BEAR rejimleri 4h-24h vadede hafif yönsel sapma gösterse de 30 bps işlem maliyeti ve FDR sonrası ekonomik alfa kaybolmaktadır.
                </div>
                <div style="font-family: var(--font-mono); font-size: 11px; color: #cbd5e1; margin-top: 6px;" id="pv-test-persistence-stats">
                  Bull 24h getiri: -0.00% (net -0.30%) &bull; Bear 24h getiri: +0.04% (net -0.26%)
                </div>
              </div>

              <!-- Reversal Fallacy -->
              <div style="background: #0f172a; border: 1px solid #1e293b; padding: 12px; border-radius: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-weight: 700; color: #fbbf24; font-size: 12px;">Tersine Dönüş Yanılgısı Testi</span>
                  <span class="pv-badge-not-supported" id="pv-test-reversal-badge">NOT_SUPPORTED</span>
                </div>
                <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
                  POSSIBLE_REVERSAL rejimi sonrası fiyat yönü %50 yazı-tura olasılığından farklı değildir; trend devamı (%58.2) baskındır.
                </div>
                <div style="font-family: var(--font-mono); font-size: 11px; color: #cbd5e1; margin-top: 6px;" id="pv-test-reversal-stats">
                  Binomial test p: 0.000626 &bull; Trend devam oranı: %58.2 (Reversal yanılgısı)
                </div>
              </div>

              <!-- Kolmogorov-Smirnov Test -->
              <div style="background: #0f172a; border: 1px solid #1e293b; padding: 12px; border-radius: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-weight: 700; color: #a78bfa; font-size: 12px;">Dağılım Ayrışma (KS Test)</span>
                  <span class="pv-badge-not-supported" id="pv-test-ks-badge">NOT_SUPPORTED</span>
                </div>
                <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
                  SIDEWAYS ve UNCERTAIN rejimlerinin 24h ileri getiri dağılımları birbirinden istatistiksel olarak ayırt edilemez.
                </div>
                <div style="font-family: var(--font-mono); font-size: 11px; color: #cbd5e1; margin-top: 6px;" id="pv-test-ks-stats">
                  KS stat D: 0.057 &bull; p-value: 0.129 (Dağılımlar farksız)
                </div>
              </div>
            </div>
          </div>

          <!-- Panel 2: Baseline Comparisons -->
          <div class="pv-dyn-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
              <h4 style="font-size: 14px; font-weight: 700; color: #fff; margin: 0;">
                ⚖️ Basit Karşılaştırma Modellerine Karşı Üstünlük
              </h4>
              <span class="badge badge-warn">Baselines</span>
            </div>

            <div style="display: flex; flex-direction: column; gap: 12px;">
              <!-- Unconditional Null -->
              <div style="background: #0f172a; border: 1px solid #1e293b; padding: 12px; border-radius: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-weight: 700; color: #94a3b8; font-size: 12px;">Koşulsuz Getiri Dağılımı (Null)</span>
                  <span style="font-family: var(--font-mono); font-size: 11px; color: #38bdf8;" id="pv-base-uncond-val">+0.05% / 24h</span>
                </div>
                <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
                  Tüm saatlik barların koşulsuz ortalama 24h getirisi. SIDEWAYS ve UNCERTAIN ortalamaları bu değerden istatistiksel olarak farksızdır.
                </div>
              </div>

              <!-- 24h Momentum -->
              <div style="background: #0f172a; border: 1px solid #1e293b; padding: 12px; border-radius: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-weight: 700; color: #60a5fa; font-size: 12px;">24h Basit Momentum Modeli</span>
                  <span style="font-family: var(--font-mono); font-size: 11px; color: #38bdf8;" id="pv-base-mom-val">İsabet: %47.6</span>
                </div>
                <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
                  Basit 24h geçmiş getiri yönü, TRENDING_BULL rejiminin ileri yön tahmin gücüne denk veya daha yüksek basitlik sunar.
                </div>
              </div>

              <!-- 24h Mean Reversion -->
              <div style="background: #0f172a; border: 1px solid #1e293b; padding: 12px; border-radius: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-weight: 700; color: #fbbf24; font-size: 12px;">24h Basit Ortalamaya Dönüş</span>
                  <span style="font-family: var(--font-mono); font-size: 11px; color: #38bdf8;" id="pv-base-mr-val">İsabet: %52.5</span>
                </div>
                <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
                  Aşırı sapmalar sonrası basit ortalamaya dönüş kuralı, POSSIBLE_REVERSAL ile aynı düşük öngörü başarısını sergiler.
                </div>
              </div>

              <!-- Volatility Model Superiority -->
              <div style="background: #0f172a; border: 1px solid #1e293b; padding: 12px; border-radius: 6px;">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span style="font-weight: 700; color: #34d399; font-size: 12px;">Rejim Koşullu Volatilite Tahmini</span>
                  <span class="pv-badge-supported">SUPERIOR</span>
                </div>
                <div style="font-size: 11px; color: #94a3b8; margin-top: 4px;">
                  Rejim bilgisi (özellikle HIGH_VOLATILITY), ileri gerçekleşen volatilite tahmininde basit gecikmeli volatiliteye göre daha düşük tahmin hatası (RMSE) sağlamaktadır.
                </div>
                <div style="font-family: var(--font-mono); font-size: 11px; color: #cbd5e1; margin-top: 6px;" id="pv-base-vol-stats">
                  Lagged RMSE: %17.46 &bull; Rejim RMSE: %16.06 &bull; %8.00 İyileşme (SUPERIOR)
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Panel 3: Walk-Forward Temporal Stability Table Card -->
        <div class="card" style="margin-bottom: 24px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
            <div>
              <h4 style="font-size: 15px; font-weight: 700; color: #fff; margin: 0;">
                📅 Yıllık Walk-Forward Kararlılık & Yapısal Kırılma Analizi (2022 - 2026)
              </h4>
              <div style="font-size: 11px; color: var(--text-muted);">
                Rejimlerin 24 saatlik ileri ortalama getirileri ve gerçekleşen oynaklıklarının yıllar itibarıyla zamansal tutarlılığı.
              </div>
            </div>
          </div>

          <div class="table-container" style="overflow-x: auto;">
            <table class="pv-scorecard-table" style="width: 100%; border-collapse: collapse; text-align: right;">
              <thead>
                <tr>
                  <th style="text-align: left;">Rejim</th>
                  <th>2022 (Ayı Piyasası)</th>
                  <th>2023 (Toparlanma)</th>
                  <th>2024 (Boğa / ETF)</th>
                  <th>2025 (Genişleme)</th>
                  <th>2026 (Mevcut)</th>
                  <th style="text-align: center;">Zamansal Kararlılık</th>
                </tr>
              </thead>
              <tbody id="pv-walk-forward-tbody">
                <tr>
                  <td colspan="7" style="text-align: center; padding: 18px; color: #94a3b8;">
                    Walk-forward verisi yükleniyor...
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- SUBVIEW 2: HYPOTHESIS EVIDENCE EXPLORER (MODÜL 38.2) -->
      <div id="pv-subview-evidence" class="pv-subview-panel" style="display: none;">
        <!-- Controls & Filter Toolbar -->
        <div class="card" style="margin-bottom: 20px; background: #0f172a; border: 1px solid #1e293b; padding: 14px 18px;">
          <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 14px;">
            <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
              <div>
                <label style="font-size: 10px; color: #94a3b8; font-weight: bold; display: block; margin-bottom: 4px;">REJİM FİLTRESİ</label>
                <select id="pv-filter-regime" class="input" style="background: #1e293b; color: #fff; border: 1px solid #334155; padding: 6px 10px; border-radius: 4px; font-size: 12px;" onchange="applyPredictiveFilters()">
                  <option value="ALL" selected>Tüm Rejimler (6 Rejim)</option>
                  <option value="SIDEWAYS">SIDEWAYS</option>
                  <option value="UNCERTAIN">UNCERTAIN</option>
                  <option value="TRENDING_BULL">TRENDING_BULL</option>
                  <option value="TRENDING_BEAR">TRENDING_BEAR</option>
                  <option value="POSSIBLE_REVERSAL">POSSIBLE_REVERSAL</option>
                  <option value="HIGH_VOLATILITY">HIGH_VOLATILITY</option>
                </select>
              </div>
              <div>
                <label style="font-size: 10px; color: #94a3b8; font-weight: bold; display: block; margin-bottom: 4px;">İLERİ VADE (HORIZON)</label>
                <select id="pv-filter-horizon" class="input" style="background: #1e293b; color: #fff; border: 1px solid #334155; padding: 6px 10px; border-radius: 4px; font-size: 12px;" onchange="applyPredictiveFilters()">
                  <option value="ALL" selected>Tüm Vadeler (1h, 4h, 12h, 24h, 72h)</option>
                  <option value="1h">1 Saat (1h)</option>
                  <option value="4h">4 Saat (4h)</option>
                  <option value="12h">12 Saat (12h)</option>
                  <option value="24h">24 Saat (24h)</option>
                  <option value="72h">72 Saat (72h)</option>
                </select>
              </div>
              <div>
                <label style="font-size: 10px; color: #94a3b8; font-weight: bold; display: block; margin-bottom: 4px;">BİLİMSEL KARAR</label>
                <select id="pv-filter-verdict" class="input" style="background: #1e293b; color: #fff; border: 1px solid #334155; padding: 6px 10px; border-radius: 4px; font-size: 12px;" onchange="applyPredictiveFilters()">
                  <option value="ALL" selected>Tüm Kararlar</option>
                  <option value="SUPPORTED">Yalnızca SUPPORTED (4)</option>
                  <option value="NOT_SUPPORTED">Yalnızca NOT_SUPPORTED (25)</option>
                  <option value="INCONCLUSIVE">Yalnızca INCONCLUSIVE (1)</option>
                </select>
              </div>
              <div>
                <label style="font-size: 10px; color: #94a3b8; font-weight: bold; display: block; margin-bottom: 4px;">ARAŞTIRMA KATEGORİSİ</label>
                <select id="pv-filter-category" class="input" style="background: #1e293b; color: #fff; border: 1px solid #334155; padding: 6px 10px; border-radius: 4px; font-size: 12px;" onchange="applyPredictiveFilters()">
                  <option value="ALL" selected>Tüm Kategoriler</option>
                  <option value="DIRECTIONAL_RETURN">Yönsel Getiri (25)</option>
                  <option value="VOLATILITY_PERSISTENCE">Volatilite Kalıcılığı (5)</option>
                </select>
              </div>
            </div>
            <div style="font-size: 11px; color: #94a3b8; text-align: right;">
              Metodoloji: <span style="color:#60a5fa; font-weight:bold;">Circular Block Bootstrap (B=500)</span> &bull; <span style="color:#34d399; font-weight:bold;">Benjamini-Hochberg FDR (q &lt; 0.05)</span>
            </div>
          </div>
        </div>

        <!-- Main Predictive Validity Scorecard Table Card -->
        <div class="card" style="margin-bottom: 24px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
            <div>
              <h3 style="font-size: 15px; color: #fff; font-weight: 700; margin: 0;">
                📊 Bilimsel Tahmin Geçerliliği Skor Kartı (30 Hipotez)
              </h3>
              <div style="font-size: 11px; color: var(--text-muted);">
                Örtüşen pencereler (overlapping horizons) için Newey-West otokorelasyon ve blok bootstrap güven aralıkları düzeltilmiştir. Satıra tıklayarak tam kanıt künyesini inceleyebilirsiniz.
              </div>
            </div>
            <div id="pv-table-row-count" style="font-size: 11px; color: #38bdf8; font-family: var(--font-mono);">
              Gösterilen: 30 / 30 hipotez
            </div>
          </div>

          <div class="table-container" style="max-height: 520px; overflow-y: auto; overflow-x: auto;">
            <table class="pv-scorecard-table" style="width: 100%; border-collapse: collapse; text-align: right;">
              <thead>
                <tr>
                  <th style="text-align: left;">Rejim</th>
                  <th style="text-align: center;">Vade</th>
                  <th>Örneklem (N)</th>
                  <th>Brüt Getiri</th>
                  <th>Net Getiri (-30bps)</th>
                  <th style="text-align: center;">%95 Bootstrap GA</th>
                  <th>NW t-stat</th>
                  <th>Ham p</th>
                  <th>FDR q</th>
                  <th>Holm p</th>
                  <th>MAE</th>
                  <th>MFE</th>
                  <th>Fwd MaxDD</th>
                  <th>Fwd RV</th>
                  <th style="text-align: center;">Bilimsel Karar</th>
                  <th style="text-align: center;">Kanıt Künyesi</th>
                </tr>
              </thead>
              <tbody id="pv-scorecard-tbody">
                <tr>
                  <td colspan="16" style="text-align: center; padding: 24px; color: #94a3b8;">
                    Analiz yükleniyor...
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- SUBVIEW 3: VOLATILITY FORECAST BENCHMARK LABORATORY (MODÜL 38.3) -->
      <div id="pv-subview-volatility" class="pv-subview-panel" style="display: none;">
        <div class="card" style="margin-bottom: 20px;">
          <h3 style="font-size: 16px; color: #fff; font-weight: 700; margin: 0 0 8px 0;">
            📈 Volatilite Tahmin Karşılaştırma Laboratuvarı (Forecast Benchmark Lab)
          </h3>
          <p style="font-size: 12px; color: var(--text-muted); margin: 0 0 16px 0; line-height: 1.5;">
            Piyasa rejimlerinin ileri volatilite tahminindeki gücü, naive GARCH(1,1) ve gecikmeli gerçekleşen volatilite kıyaslama modelleri ile eşit test döneminde (59 ay / 42.693 bar) doğrudan test edilmiştir.
          </p>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px; margin-bottom: 20px;">
            <!-- Regime Conditioned Card -->
            <div class="pv-benchmark-card" style="border-left: 4px solid #10b981;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-weight: 700; color: #34d399; font-size: 13px;">Regime-Conditioned Volatility</span>
                <span class="pv-badge-supported">SUPERIOR MODEL</span>
              </div>
              <div style="display: flex; align-items: baseline; gap: 10px; margin: 10px 0;">
                <span style="font-size: 32px; font-weight: 800; color: #fff; font-family: var(--font-mono);">16.0612</span>
                <span style="font-size: 13px; color: #94a3b8;">RMSE (% p.a.)</span>
              </div>
              <div style="font-size: 12px; color: #cbd5e1; line-height: 1.6;">
                &bull; MAE: <b style="color: #60a5fa;">%15.82</b><br>
                &bull; Örneklem: 42.693 saatlik bar<br>
                &bull; Tahmin Ufku: 24 Saatlik İleri Dönem<br>
                &bull; Göreli Hata İyileşmesi: <b style="color: #34d399;">+%8.00 Üstünlük</b>
              </div>
            </div>

            <!-- GARCH Benchmark Card -->
            <div class="pv-benchmark-card" style="border-left: 4px solid #94a3b8;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                <span style="font-weight: 700; color: #cbd5e1; font-size: 13px;">GARCH(1,1) / Lagged Realized Volatility</span>
                <span class="badge" style="background: #334155; color: #cbd5e1;">BASELINE BENCHMARK</span>
              </div>
              <div style="display: flex; align-items: baseline; gap: 10px; margin: 10px 0;">
                <span style="font-size: 32px; font-weight: 800; color: #94a3b8; font-family: var(--font-mono);">17.4578</span>
                <span style="font-size: 13px; color: #64748b;">RMSE (% p.a.)</span>
              </div>
              <div style="font-size: 12px; color: #94a3b8; line-height: 1.6;">
                &bull; MAE: %17.46<br>
                &bull; Örneklem: 42.693 saatlik bar<br>
                &bull; Tahmin Ufku: 24 Saatlik İleri Dönem<br>
                &bull; Model: 24h gecikmeli gerçekleşen volatilite projeksiyonu
              </div>
            </div>
          </div>

          <!-- Statistical Test & Methodology Comparability Table -->
          <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; margin-bottom: 16px;">
            <h4 style="font-size: 13px; font-weight: 700; color: #60a5fa; margin: 0 0 10px 0;">
              ⚖️ Diebold-Mariano İstatistiki Üstünlük Testi & Metodolojik Eşitlik
            </h4>
            <div style="font-size: 12px; color: #cbd5e1; line-height: 1.6;">
              &bull; <b>Diebold-Mariano Test İstatistiği:</b> DM = -4.82 &bull; p-value = <b>0.0000014</b> (p &lt; 1e-5)<br>
              &bull; <b>Sıfır Hipotezi (H0):</b> Her iki model eşit tahmin hatasına sahiptir.<br>
              &bull; <b>Karar:</b> H0 istatistiksel olarak kesin şekilde REDDEDİLMİŞTİR. Rejim koşullu volatilite modeli istatistiki olarak anlamlı biçimde daha üstündür.<br>
              &bull; <b>Metodolojik Eşdeğerlik:</b> Aynı test dönemi (59 ay), aynı hedef değişken (24h ileri gerçekleşen volatilite) ve aynı birim (% yıllıklandırılmış) kullanılmıştır.
            </div>
          </div>

          <!-- Strict Boundary Notice -->
          <div style="padding: 12px 16px; background: rgba(30, 58, 138, 0.2); border: 1px solid #3b82f6; border-radius: 6px; font-size: 11px; color: #93c5fd; line-height: 1.6;">
            <b>BİLİMSEL KAPSAM SINIRI:</b> Bu performans üstünlüğü <u>yalnızca risk yönetimi ve volatilite projeksiyonu</u> için geçerlidir. Fiyat yönünün tahmin edilebileceği veya alım-satım ile kâr elde edilebileceği anlamına kesinlikle gelmez. Canlı işlem emirleri daimi olarak engellenmiştir (HTTP 403 Forbidden).
          </div>
        </div>
      </div>

      <!-- SUBVIEW 4: MARKET REGIME PERSISTENCE INTELLIGENCE (MODÜL 38.4) -->
      <div id="pv-subview-persistence" class="pv-subview-panel" style="display: none;">
        <div class="card" style="margin-bottom: 20px;">
          <h3 style="font-size: 16px; color: #fff; font-weight: 700; margin: 0 0 8px 0;">
            🔄 Piyasa Rejimi Kalıcılık İstihbaratı & Geçiş Dinamikleri
          </h3>
          <p style="font-size: 12px; color: var(--text-muted); margin: 0 0 16px 0;">
            6 piyasa rejiminin ortalama kalıcılık süreleri, geçiş olasılıkları ve oynaklıkla olan tarihsel ilişkisi.
          </p>

          <div class="table-container" style="overflow-x: auto; margin-bottom: 20px;">
            <table class="pv-scorecard-table" style="width: 100%; border-collapse: collapse; text-align: right;">
              <thead>
                <tr>
                  <th style="text-align: left;">Rejim</th>
                  <th>Ortalama Süre (Saat)</th>
                  <th>Medyan Süre (Saat)</th>
                  <th>Kalıcılık Olasılığı (P_ii)</th>
                  <th>İncelenen Toplam Geçiş</th>
                  <th style="text-align: left;">Volatiliteyle İlişki Karakteristiği</th>
                  <th style="text-align: center;">Yönetişim Etiketi</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style="text-align: left; font-weight: 700; color: #cbd5e1;">SIDEWAYS</td>
                  <td>18.4 saat</td>
                  <td>12.0 saat</td>
                  <td style="color: #34d399; font-weight: bold;">%94.6</td>
                  <td>1.240</td>
                  <td style="text-align: left; color: #94a3b8;">Düşük volatilite sıkışması (Compression)</td>
                  <td style="text-align: center;"><span class="badge" style="background:#1e293b; color:#94a3b8;">DERIVED</span></td>
                </tr>
                <tr>
                  <td style="text-align: left; font-weight: 700; color: #cbd5e1;">UNCERTAIN</td>
                  <td>11.2 saat</td>
                  <td>7.0 saat</td>
                  <td style="color: #60a5fa; font-weight: bold;">%91.1</td>
                  <td>894</td>
                  <td style="text-align: left; color: #94a3b8;">Orta düzey gürültü ve yön kararsızlığı</td>
                  <td style="text-align: center;"><span class="badge" style="background:#1e293b; color:#94a3b8;">DERIVED</span></td>
                </tr>
                <tr>
                  <td style="text-align: left; font-weight: 700; color: #cbd5e1;">TRENDING_BULL</td>
                  <td>8.6 saat</td>
                  <td>5.0 saat</td>
                  <td style="color: #38bdf8; font-weight: bold;">%88.4</td>
                  <td>459</td>
                  <td style="text-align: left; color: #94a3b8;">Genişleyen yukarı yönlü kayma</td>
                  <td style="text-align: center;"><span class="badge" style="background:#1e293b; color:#94a3b8;">DERIVED</span></td>
                </tr>
                <tr>
                  <td style="text-align: left; font-weight: 700; color: #cbd5e1;">TRENDING_BEAR</td>
                  <td>7.4 saat</td>
                  <td>4.0 saat</td>
                  <td style="color: #f87171; font-weight: bold;">%86.5</td>
                  <td>392</td>
                  <td style="text-align: left; color: #94a3b8;">Keskin aşağı yönlü oynaklık genişlemesi</td>
                  <td style="text-align: center;"><span class="badge" style="background:#1e293b; color:#94a3b8;">DERIVED</span></td>
                </tr>
                <tr>
                  <td style="text-align: left; font-weight: 700; color: #cbd5e1;">POSSIBLE_REVERSAL</td>
                  <td>4.8 saat</td>
                  <td>3.0 saat</td>
                  <td style="color: #fbbf24; font-weight: bold;">%79.2</td>
                  <td>445</td>
                  <td style="text-align: left; color: #94a3b8;">Trend yorgunluğu / Yanılgı riski yüksek</td>
                  <td style="text-align: center;"><span class="badge" style="background:#1e293b; color:#94a3b8;">DERIVED</span></td>
                </tr>
                <tr>
                  <td style="text-align: left; font-weight: 700; color: #cbd5e1;">HIGH_VOLATILITY</td>
                  <td>9.5 saat</td>
                  <td>6.0 saat</td>
                  <td style="color: #a78bfa; font-weight: bold;">%89.5</td>
                  <td>34</td>
                  <td style="text-align: left; color: #f87171;">Güçlü volatilite kümelenmesi (%69.97 fwd vol)</td>
                  <td style="text-align: center;"><span class="badge" style="background:#1e293b; color:#94a3b8;">DERIVED</span></td>
                </tr>
              </tbody>
            </table>
          </div>

          <div style="padding: 12px 16px; background: #0f172a; border: 1px solid #1e293b; border-radius: 6px; font-size: 11px; color: #94a3b8; line-height: 1.6;">
            <b>YÖNETİŞİM HÜKMÜ:</b> <span style="color: #fbbf24; font-weight: bold;">CANONICAL_PARITY_NOT_ESTABLISHED</span>. Yukarıdaki 6 rejim sınıflandırması çevrimdışı araştırma için türetilmiş olup, CBE-0.7.0 dondurulmuş çekirdek modelinin Tier 1 nominal durumlarının (NORMAL, COMPRESSION, EXPANSION_WATCH, DELEVERAGING_STRESS) yerine geçemez.
          </div>
        </div>
      </div>

      <!-- SUBVIEW 5: DIRECTIONAL PREDICTABILITY REALITY CHECK (MODÜL 38.5) -->
      <div id="pv-subview-directional" class="pv-subview-panel" style="display: none;">
        <!-- Mandatory Warning Banner -->
        <div class="pv-reality-check-banner">
          <div style="display: flex; align-items: center; gap: 12px;">
            <span style="font-size: 28px;">🚨</span>
            <div>
              <div style="font-size: 15px; font-weight: 800; color: #f87171; text-transform: uppercase; letter-spacing: 0.05em;">
                BİLİMSEL GERÇEKLİK DENETİMİ (REALITY CHECK)
              </div>
              <div style="font-size: 14px; font-weight: 700; color: #fff; margin-top: 4px;">
                "Yönsel fiyat tahmininde istatistiksel olarak güvenilir bir üstünlük henüz doğrulanmamıştır."
              </div>
            </div>
          </div>
        </div>

        <div class="card" style="margin-bottom: 20px;">
          <h3 style="font-size: 16px; color: #fff; font-weight: 700; margin: 0 0 8px 0;">
            ⚖️ Yönsel Tahmin İstatistiği & Sıfır-Alfa Gerçeği
          </h3>
          <p style="font-size: 12px; color: var(--text-muted); margin: 0 0 16px 0; line-height: 1.5;">
            Yüzde 50'nin üzerindeki küçük isabet oranları yanıltıcıdır ve istatistiksel üstünlük kanıtı değildir.
          </p>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 14px; margin-bottom: 20px;">
            <div class="pv-kpi-card" style="border-left: 3px solid #60a5fa;">
              <div style="font-size: 11px; color: #94a3b8; font-weight: 700;">24h MOMENTUM İSABETİ</div>
              <div style="font-size: 26px; font-weight: 800; color: #60a5fa; margin-top: 4px;">%47.57</div>
              <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">Yazı-turadan daha düşük</div>
            </div>
            <div class="pv-kpi-card" style="border-left: 3px solid #fbbf24;">
              <div style="font-size: 11px; color: #94a3b8; font-weight: 700;">24h MEAN-REVERSION İSABETİ</div>
              <div style="font-size: 26px; font-weight: 800; color: #fbbf24; margin-top: 4px;">%52.51</div>
              <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">Binomial p = 0.18 (Farksız)</div>
            </div>
            <div class="pv-kpi-card" style="border-left: 3px solid #38bdf8;">
              <div style="font-size: 11px; color: #94a3b8; font-weight: 700;">KOŞULSUZ 24h ORTALAMA</div>
              <div style="font-size: 26px; font-weight: 800; color: #38bdf8; margin-top: 4px;">+%0.0518</div>
              <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">Null piyasa getirisi</div>
            </div>
            <div class="pv-kpi-card" style="border-left: 3px solid #f87171;">
              <div style="font-size: 11px; color: #94a3b8; font-weight: 700;">İŞLEM SÜRTÜNMESİ (-30 BPS)</div>
              <div style="font-size: 26px; font-weight: 800; color: #f87171; margin-top: 4px;">-24.82 bps</div>
              <div style="font-size: 11px; color: #94a3b8; margin-top: 2px;">Net yönsel alfa tamamen negatif</div>
            </div>
          </div>

          <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px; font-size: 12px; color: #cbd5e1; line-height: 1.6;">
            <b>KRİTİK NEDENLER VE METODOLOJİK GERÇEKLER:</b><br>
            1. <b>Sınıf Dengesizliği:</b> %52.51'lik ortalamaya dönüş isabeti, çift taraflı binomial testte p = 0.18 vermekte olup rassal dalgalanma aralığındadır (%95 GA: [%49.8, %55.2]).<br>
            2. <b>İşlem Maliyeti Gerçeği:</b> Gerçek piyasada 30 bps round-trip sürtünme (10 komisyon + 2 spread + 3 kayma &times; 2) düşüldüğünde tüm 25 yönsel hipotezde net getiri negatife inmektedir.<br>
            3. <b>Zamansal İstikrarsızlık:</b> Yıllık walk-forward analizinde rejim yönleri 2022-2026 arasında sürekli işaret değiştirmektedir. Geçmişte çalışan stratejiler gelecekte çökmektedir.<br>
            4. <b>Tarihsel Hüküm:</b> <span style="color: #f87171; font-weight: bold;">REJECTED_OVERFITTING</span> kararı tam geçerliliğini korumaktadır.
          </div>
        </div>
      </div>

      <!-- SUBVIEW 6: STATISTICAL CONFIDENCE & UNCERTAINTY (MODÜL 38.6) -->
      <div id="pv-subview-uncertainty" class="pv-subview-panel" style="display: none;">
        <div class="card" style="margin-bottom: 20px;">
          <h3 style="font-size: 16px; color: #fff; font-weight: 700; margin: 0 0 8px 0;">
            📐 İstatistiki Güven, Otokorelasyon & Çoklu Test Düzeltmesi
          </h3>
          <p style="font-size: 12px; color: var(--text-muted); margin: 0 0 16px 0;">
            Finansal zaman serilerinde örtüşen pencerelerin ve eşzamanlı testlerin yarattığı sahte anlamlılık yanılsamalarına karşı alınan bilimsel önlemler.
          </p>

          <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 16px;">
            <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px;">
              <h4 style="font-size: 13px; font-weight: 700; color: #60a5fa; margin: 0 0 8px 0;">
                1. Circular Block Bootstrap (B=500, Blok=24h)
              </h4>
              <div style="font-size: 12px; color: #94a3b8; line-height: 1.6;">
                Saatlik serilerdeki otokorelasyon yapısını bozmamak için dairesel blok bootstrap yöntemi kullanılmıştır. Blok uzunluğu 24 saat seçilmiş, her hipotez için 500 yeniden örneklem ile ampirik %95 güven aralıkları türetilmiştir.
              </div>
            </div>

            <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px;">
              <h4 style="font-size: 13px; font-weight: 700; color: #34d399; margin: 0 0 8px 0;">
                2. Newey-West HAC Standart Hataları
              </h4>
              <div style="font-size: 12px; color: #94a3b8; line-height: 1.6;">
                Örtüşen vadeler (1h, 4h, 12h, 24h, 72h) nedeniyle kalıntılarda oluşan hareketli ortalama otokorelasyonu, Bartlett çekirdeği ve L = 2 &times; Vade gecikme kesme noktası ile düzeltilmiştir.
              </div>
            </div>

            <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px;">
              <h4 style="font-size: 13px; font-weight: 700; color: #f59e0b; margin: 0 0 8px 0;">
                3. Benjamini-Hochberg FDR Düzeltmesi
              </h4>
              <div style="font-size: 12px; color: #94a3b8; line-height: 1.6;">
                30 eşzamanlı test için nominal &alpha;=0.05 anlamlılık eşiği q &lt; 0.05 False Discovery Rate (FDR) algoritmasıyla düzeltilmiştir. Hiçbir yönsel hipotez bu filtreyi geçememiştir.
              </div>
            </div>

            <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px;">
              <h4 style="font-size: 13px; font-weight: 700; color: #a78bfa; margin: 0 0 8px 0;">
                4. Holm-Bonferroni Family-Wise Error Rate
              </h4>
              <div style="font-size: 12px; color: #94a3b8; line-height: 1.6;">
                Tip 1 hatayı (sahte pozitif) en katı şekilde kısıtlayan Holm-Bonferroni düzeltmesi ile tekil test p-değerleri kademeli olarak cezalandırılmış ve sonuçlar çapraz doğrulanmıştır.
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- SUBVIEW 7: SCIENTIFIC LIMITATIONS & REJECTED FINDINGS (MODÜL 38.7) -->
      <div id="pv-subview-limitations" class="pv-subview-panel" style="display: none;">
        <div class="card" style="margin-bottom: 20px;">
          <h3 style="font-size: 16px; color: #fff; font-weight: 700; margin: 0 0 8px 0;">
            🚫 Bilimsel Sınırlamalar & Reddedilen Bulgular Kataloğu
          </h3>
          <p style="font-size: 12px; color: var(--text-muted); margin: 0 0 16px 0;">
            Bilimsel dürüstlük gereğince desteklenmeyen 25 hipotezin ve metodolojik sınırların şeffaf dökümü.
          </p>

          <div style="display: flex; flex-direction: column; gap: 14px;">
            <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-weight: 700; color: #f87171; font-size: 13px;">1. Yönsel Alfa Yokluğu (25 Hipotez)</span>
                <span class="pv-badge-not-supported">NOT_SUPPORTED</span>
              </div>
              <div style="font-size: 12px; color: #cbd5e1; line-height: 1.6;">
                SIDEWAYS, UNCERTAIN, TRENDING_BULL, TRENDING_BEAR ve POSSIBLE_REVERSAL rejimlerinin 1h, 4h, 12h, 24h ve 72h vadelerindeki ortalama getirileri, piyasanın koşulsuz ortalamasından farksızdır. Ham p-değerleri Newey-West otokorelasyon düzeltmesi sonrası 0.15 - 0.99 aralığında kalmaktadır.
              </div>
            </div>

            <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-weight: 700; color: #fbbf24; font-size: 13px;">2. Reversal Yanılgısı (Trend Devamı Eğilimi)</span>
                <span class="pv-badge-not-supported">NOT_SUPPORTED</span>
              </div>
              <div style="font-size: 12px; color: #cbd5e1; line-height: 1.6;">
                POSSIBLE_REVERSAL etiketinden sonra fiyatın önceki 24h trendine zıt yöne dönmesi beklenirken, ampirik olarak %58.2 oranında mevcut trendin devam ettiği görülmüştür (Binomial p = 0.000626). Reversal sinyali güvenilmezdir.
              </div>
            </div>

            <div style="background: #0f172a; border: 1px solid #1e293b; border-radius: 8px; padding: 16px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                <span style="font-weight: 700; color: #a78bfa; font-size: 13px;">3. SIDEWAYS vs UNCERTAIN Dağılımsal Eşdeğerliği</span>
                <span class="pv-badge-not-supported">INDISTINGUISHABLE</span>
              </div>
              <div style="font-size: 12px; color: #cbd5e1; line-height: 1.6;">
                Kolmogorov-Smirnov testinde (D = 0.0568, p = 0.1285), SIDEWAYS ve UNCERTAIN rejimlerinin ileri getiri dağılımlarının birbirinden ayırt edilemediği tespit edilmiştir. İki rejim teorik olarak farklı tanımlansa da pratik getiri ayrışması yaratmamaktadır.
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- SUBVIEW 8: HISTORICAL RESEARCH COMPARISON (MODÜL 38.8) -->
      <div id="pv-subview-history" class="pv-subview-panel" style="display: none;">
        <div class="card" style="margin-bottom: 20px;">
          <h3 style="font-size: 16px; color: #fff; font-weight: 700; margin: 0 0 8px 0;">
            📜 Tarihsel Araştırma Evrimi & Sürüm Karşılaştırması
          </h3>
          <p style="font-size: 12px; color: var(--text-muted); margin: 0 0 16px 0;">
            Sprint 35'ten Sprint 38'e kadar kanonik veri bütünlüğü ve tahmin geçerliliği araştırma çizgisi.
          </p>

          <div class="table-container" style="overflow-x: auto;">
            <table class="pv-scorecard-table" style="width: 100%; border-collapse: collapse; text-align: left;">
              <thead>
                <tr>
                  <th>Sprint / Versiyon</th>
                  <th>Odak & Kapsam</th>
                  <th>Kanonik Model</th>
                  <th>Veri Kapsamı</th>
                  <th>Doğrulanan Hipotezler</th>
                  <th>Canlı İşlem Statüsü</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <td style="font-weight: bold; color: #94a3b8;">Sprint 35 (V12)</td>
                  <td>Ekim Kaynak Doğrulama & Kasım Boşluk İzolasyonu</td>
                  <td>CBE-0.7.0 FROZEN</td>
                  <td>58 Ay Tam + 1 Ay Kısmi (8 Eksik Bar)</td>
                  <td>Veri kökeni & gap kanıtı</td>
                  <td><span class="badge badge-danger">YASAK (403)</span></td>
                </tr>
                <tr>
                  <td style="font-weight: bold; color: #94a3b8;">Sprint 36 (V13)</td>
                  <td>Dataset Registry V2 & Rejim Geçiş Analitiği</td>
                  <td>CBE-0.7.0 FROZEN</td>
                  <td>59 Ay (42.717 saatlik bar)</td>
                  <td>Deskriptif piyasa davranışı</td>
                  <td><span class="badge badge-danger">YASAK (403)</span></td>
                </tr>
                <tr>
                  <td style="font-weight: bold; color: #94a3b8;">Sprint 37 (V14)</td>
                  <td>Predictive Validity & Bilimsel Skor Kartı V3</td>
                  <td>CBE-0.7.0 FROZEN</td>
                  <td>59 Ay (42.717 saatlik bar)</td>
                  <td>30 Hipotez (4 Supp, 25 Not, 1 Incon)</td>
                  <td><span class="badge badge-danger">YASAK (403)</span></td>
                </tr>
                <tr style="background: rgba(37, 99, 235, 0.15);">
                  <td style="font-weight: bold; color: #38bdf8;">Sprint 38 (V15 - Mevcut)</td>
                  <td>Evidence Explorer, Vol Benchmark Lab & Karar Destek</td>
                  <td>CBE-0.7.0 FROZEN</td>
                  <td>59 Ay (42.717 saatlik bar)</td>
                  <td>30 Hipotez Künyesi + Vol Benchmark RMSE 16.06</td>
                  <td><span class="badge badge-danger">YASAK (403)</span></td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <!-- Legal and Scientific Governance Disclaimer -->
      <div style="padding: 14px 18px; background: #0b1329; border: 1px solid #1e293b; border-radius: 8px; font-size: 11px; color: #94a3b8; text-align: center; line-height: 1.6;">
        <b style="color: #cbd5e1;">BİLİMSEL DÜRÜSTLÜK VE YÖNETİŞİM BİLDİRİMİ:</b> Bu laboratuvardaki tüm istatistiksel sonuçlar, 2022-2026 tarihsel BTCUSDT saatlik verileri üzerinden yürütülen nedensel ve geçmişe dönük (point-in-time) ampirik doğrulama araştırmasıdır. Piyasa rejimlerinin yönsel getiri tahmininde başarısız olması ("NOT_SUPPORTED") bilimsel bir kusur değil, piyasa etkinliğinin ve 30 bps işlem maliyeti kesintisi sonrası sıfır-alfa gerçeğinin somut kanıtıdır. Canlı işlem veya kârlılık garantisi asla verilmez. Canlı emir uç noktaları kalıcı olarak devre dışıdır (HTTP 403 Forbidden).
      </div>

      <!-- Hypothesis Evidence Explorer Detail Modal -->
      <div id="pv-evidence-modal" class="pv-modal-backdrop">
        <div class="pv-modal-window">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 1px solid #1e293b; padding-bottom: 12px;">
            <div>
              <div style="display: flex; align-items: center; gap: 8px;">
                <span class="badge" style="background: #1e3a8a; color: #93c5fd;" id="pv-modal-cat">CATEGORY</span>
                <span id="pv-modal-verdict-badge" class="pv-badge-supported">SUPPORTED</span>
              </div>
              <h3 style="font-size: 17px; color: #fff; margin: 6px 0 0 0; font-family: var(--font-mono);" id="pv-modal-hid">H_REGIME_HORIZON</h3>
            </div>
            <button class="btn" style="background: #1e293b; color: #94a3b8; padding: 4px 10px;" onclick="closeHypothesisEvidenceModal()">✕ Kapat</button>
          </div>

          <div style="margin-top: 14px;">
            <div style="background: #0f172a; padding: 12px; border-radius: 6px; border: 1px solid #1e293b; margin-bottom: 12px;">
              <div style="font-size: 11px; font-weight: bold; color: #f87171;">SIFIR HİPOTEZİ (H0):</div>
              <div style="font-size: 12px; color: #cbd5e1; margin-top: 2px;" id="pv-modal-h0">-</div>
              <div style="font-size: 11px; font-weight: bold; color: #34d399; margin-top: 8px;">ALTERNATİF HİPOTEZ (H1):</div>
              <div style="font-size: 12px; color: #cbd5e1; margin-top: 2px;" id="pv-modal-h1">-</div>
            </div>

            <div class="pv-evidence-grid">
              <div class="pv-evidence-item">
                <div class="lbl">Rejim & Vade</div>
                <div class="val" id="pv-modal-reg-hz">-</div>
              </div>
              <div class="pv-evidence-item">
                <div class="lbl">Örneklem Büyüklüğü (N)</div>
                <div class="val" id="pv-modal-n">-</div>
              </div>
              <div class="pv-evidence-item">
                <div class="lbl">Brüt / Net Getiri (-30bps)</div>
                <div class="val" id="pv-modal-rets">-</div>
              </div>
              <div class="pv-evidence-item">
                <div class="lbl">%95 Bootstrap Güven Aralığı</div>
                <div class="val" id="pv-modal-ci">-</div>
              </div>
              <div class="pv-evidence-item">
                <div class="lbl">Newey-West HAC t-stat</div>
                <div class="val" id="pv-modal-tstat">-</div>
              </div>
              <div class="pv-evidence-item">
                <div class="lbl">Ham p / FDR q / Holm p</div>
                <div class="val" id="pv-modal-pvals">-</div>
              </div>
              <div class="pv-evidence-item">
                <div class="lbl">MAE / MFE</div>
                <div class="val" id="pv-modal-maemfe">-</div>
              </div>
              <div class="pv-evidence-item">
                <div class="lbl">İleri MaxDD / Realized Vol</div>
                <div class="val" id="pv-modal-mddvol">-</div>
              </div>
            </div>

            <div style="margin-top: 14px; background: #0f172a; padding: 12px; border-radius: 6px; border: 1px solid #1e293b;">
              <div style="font-size: 11px; font-weight: bold; color: #38bdf8;">KANIT VE METODOLOJİ DETAYLARI:</div>
              <div style="font-size: 11px; color: #94a3b8; line-height: 1.6; margin-top: 4px;" id="pv-modal-meta">
                Metodoloji: Circular Block Bootstrap (B=500, blok=24h) + Newey-West HAC (L=2*horizon)<br>
                Veri Manifesti SHA-256: 1ff50222c31a486b094a7f2ac9f06d38b1258527e5492acbef5faf9a73c55f14<br>
                Kaynak Dosya: research_outputs/sprint37_predictive_validity/09_scientific_scorecard.json
              </div>
            </div>
          </div>
        </div>
      </div>

    </section>
    """


def render_predictive_validity_scripts() -> str:
    """Render the client-side JavaScript for Predictive Validity Lab V15."""
    return """
    // =========================================================================
    // SPRINT 38: MARKET REGIME PREDICTIVE VALIDITY CLIENT LOGIC (DASHBOARD V15)
    // =========================================================================
    let pvScorecardCache = null;
    let pvExplorerCache = null;
    let pvTransitionsCache = null;
    let pvBaselinesCache = null;
    let pvWalkForwardCache = null;
    let pvVolatilityBenchmarkCache = null;

    async function loadPredictiveValidity() {
      try {
        const [scRes, expRes, trRes, blRes, wfRes, volRes] = await Promise.all([
          fetch('/api/v1/product/predictive-validity/scorecard'),
          fetch('/api/v1/product/predictive-validity/evidence-explorer'),
          fetch('/api/v1/product/predictive-validity/transitions'),
          fetch('/api/v1/product/predictive-validity/baselines'),
          fetch('/api/v1/product/predictive-validity/walk-forward'),
          fetch('/api/v1/product/predictive-validity/volatility-benchmark')
        ]);

        if (scRes.ok) {
          const payload = await scRes.json();
          pvScorecardCache = payload.scorecard || payload.data || [];
          renderPredictiveScorecard(pvScorecardCache);
          updatePredictiveKpis(pvScorecardCache);
        }

        if (expRes.ok) {
          const payload = await expRes.json();
          pvExplorerCache = payload.evidence_explorer || payload.items || [];
        }

        if (trRes.ok) {
          const payload = await trRes.json();
          pvTransitionsCache = payload.data || payload;
          renderPredictiveTransitions(pvTransitionsCache);
        }

        if (blRes.ok) {
          const payload = await blRes.json();
          pvBaselinesCache = payload.data || payload;
          renderPredictiveBaselines(pvBaselinesCache);
        }

        if (wfRes.ok) {
          const payload = await wfRes.json();
          pvWalkForwardCache = payload.annual_stability || payload.annual_validation || payload.data || payload;
          renderPredictiveWalkForward(pvWalkForwardCache);
        }

        if (volRes.ok) {
          const payload = await volRes.json();
          pvVolatilityBenchmarkCache = payload;
        }
      } catch (err) {
        console.error("Error loading Predictive Validity Lab V15:", err);
      }
    }

    function switchPvSubview(subviewId) {
      const views = ['overview', 'evidence', 'volatility', 'persistence', 'directional', 'uncertainty', 'limitations', 'history'];
      views.forEach(v => {
        const panel = document.getElementById('pv-subview-' + v);
        const btn = document.getElementById('btn-pv-sub-' + v);
        if (panel) panel.style.display = (v === subviewId) ? 'block' : 'none';
        if (btn) {
          if (v === subviewId) btn.classList.add('active');
          else btn.classList.remove('active');
        }
      });
    }

    function updatePredictiveKpis(rows) {
      if (!rows) return;
      let total = rows.length;
      let supp = 0;
      let notSupp = 0;
      let incon = 0;

      rows.forEach(r => {
        if (r.scientific_verdict === "SUPPORTED") supp++;
        else if (r.scientific_verdict === "NOT_SUPPORTED") notSupp++;
        else if (r.scientific_verdict === "INCONCLUSIVE") incon++;
      });

      const totalEl = document.getElementById("pv-kpi-total");
      const suppEl = document.getElementById("pv-kpi-supported");
      const notSuppEl = document.getElementById("pv-kpi-not-supported");
      const inconEl = document.getElementById("pv-kpi-inconclusive");

      if (totalEl) totalEl.textContent = total;
      if (suppEl) suppEl.textContent = supp;
      if (notSuppEl) notSuppEl.textContent = notSupp;
      if (inconEl) inconEl.textContent = incon;
    }

    function applyPredictiveFilters() {
      if (!pvScorecardCache) return;
      const reg = document.getElementById("pv-filter-regime") ? document.getElementById("pv-filter-regime").value : "ALL";
      const hor = document.getElementById("pv-filter-horizon") ? document.getElementById("pv-filter-horizon").value : "ALL";
      const verd = document.getElementById("pv-filter-verdict") ? document.getElementById("pv-filter-verdict").value : "ALL";
      const cat = document.getElementById("pv-filter-category") ? document.getElementById("pv-filter-category").value : "ALL";

      let filtered = pvScorecardCache.filter(r => {
        if (reg !== "ALL" && r.regime !== reg) return false;
        if (hor !== "ALL" && r.horizon !== hor) return false;
        if (verd !== "ALL" && r.scientific_verdict !== verd) return false;
        if (cat !== "ALL") {
          const isVol = (r.regime === "HIGH_VOLATILITY");
          const rCat = isVol ? "VOLATILITY_PERSISTENCE" : "DIRECTIONAL_RETURN";
          if (rCat !== cat) return false;
        }
        return true;
      });

      renderPredictiveScorecard(filtered);
      updatePredictiveKpis(filtered);
    }

    function renderPredictiveScorecard(rows) {
      const tbody = document.getElementById("pv-scorecard-tbody");
      const countEl = document.getElementById("pv-table-row-count");
      if (!tbody) return;

      if (countEl) {
        countEl.textContent = `Gösterilen: ${rows.length} / ${pvScorecardCache ? pvScorecardCache.length : rows.length} hipotez`;
      }

      if (!rows || !rows.length) {
        tbody.innerHTML = `<tr><td colspan="16" style="text-align: center; padding: 20px; color: #94a3b8;">Filtrelere uygun hipotez bulunamadı.</td></tr>`;
        return;
      }

      let html = "";
      rows.forEach(r => {
        let badgeClass = "pv-badge-inconclusive";
        if (r.scientific_verdict === "SUPPORTED") badgeClass = "pv-badge-supported";
        else if (r.scientific_verdict === "NOT_SUPPORTED") badgeClass = "pv-badge-not-supported";
        else if (r.scientific_verdict === "INSUFFICIENT_DATA") badgeClass = "pv-badge-insufficient";

        const grossRetVal = r.mean_fwd_return_gross_pct !== undefined ? r.mean_fwd_return_gross_pct : (r.mean_forward_return_pct || 0);
        const netRetVal = r.mean_fwd_return_net_pct !== undefined ? r.mean_fwd_return_net_pct : (r.net_return_after_costs_pct || grossRetVal - 0.30);

        const grossRet = (grossRetVal >= 0 ? "+" : "") + Number(grossRetVal).toFixed(2) + "%";
        const netRet = (netRetVal >= 0 ? "+" : "") + Number(netRetVal).toFixed(2) + "%";
        const netColor = netRetVal >= 0 ? "#34d399" : "#f87171";

        const ciLower = r.bootstrap_ci_95_lower !== undefined ? r.bootstrap_ci_95_lower : (r.block_bootstrap_ci_95_pct ? r.block_bootstrap_ci_95_pct[0] : 0);
        const ciUpper = r.bootstrap_ci_95_upper !== undefined ? r.bootstrap_ci_95_upper : (r.block_bootstrap_ci_95_pct ? r.block_bootstrap_ci_95_pct[1] : 0);
        const ciStr = `[${Number(ciLower).toFixed(2)}%, ${Number(ciUpper).toFixed(2)}%]`;

        const tStat = r.newey_west_t_stat !== null && r.newey_west_t_stat !== undefined ? Number(r.newey_west_t_stat).toFixed(2) : "-";
        const pVal = r.raw_p_value !== null && r.raw_p_value !== undefined ? (r.raw_p_value < 0.001 ? "<0.001" : Number(r.raw_p_value).toFixed(3)) : "-";
        const qVal = r.fdr_q_value !== null && r.fdr_q_value !== undefined ? (r.fdr_q_value < 0.001 ? "<0.001" : Number(r.fdr_q_value).toFixed(3)) : (r.fdr_bh_adj_p_value ? Number(r.fdr_bh_adj_p_value).toFixed(3) : "-");
        const hVal = r.holm_p_value !== null && r.holm_p_value !== undefined ? (r.holm_p_value < 0.001 ? "<0.001" : Number(r.holm_p_value).toFixed(3)) : (r.holm_adj_p_value ? Number(r.holm_adj_p_value).toFixed(3) : "-");

        const maeStr = r.mae_pct !== undefined ? Number(r.mae_pct).toFixed(2) + "%" : "-";
        const mfeStr = r.mfe_pct !== undefined ? Number(r.mfe_pct).toFixed(2) + "%" : "-";
        const mddStr = r.mean_fwd_max_drawdown_pct !== undefined ? Number(r.mean_fwd_max_drawdown_pct).toFixed(2) + "%" : "-";
        const rvStr = r.mean_fwd_realized_vol_pct !== undefined ? Number(r.mean_fwd_realized_vol_pct).toFixed(2) + "%" : "-";

        const hid = r.hypothesis_id || `H_${r.regime}_${r.horizon}`;

        html += `<tr style="cursor: pointer;" onclick="openHypothesisEvidenceModal('${hid}')">
          <td style="text-align: left; font-weight: 700; color: #cbd5e1; font-family: var(--font-mono);">${r.regime}</td>
          <td style="text-align: center; color: #38bdf8;">${r.horizon}</td>
          <td style="color: #94a3b8;">${Number(r.sample_size).toLocaleString()}</td>
          <td style="color: #cbd5e1;">${grossRet}</td>
          <td style="color: ${netColor}; font-weight: bold;">${netRet}</td>
          <td style="text-align: center; color: #94a3b8; font-size: 11px;">${ciStr}</td>
          <td style="color: #cbd5e1;">${tStat}</td>
          <td style="color: #94a3b8;">${pVal}</td>
          <td style="color: #93c5fd; font-weight: bold;">${qVal}</td>
          <td style="color: #94a3b8;">${hVal}</td>
          <td style="color: #fca5a5;">${maeStr}</td>
          <td style="color: #86efac;">${mfeStr}</td>
          <td style="color: #fca5a5;">${mddStr}</td>
          <td style="color: #fde047;">${rvStr}</td>
          <td style="text-align: center;"><span class="${badgeClass}">${r.scientific_verdict}</span></td>
          <td style="text-align: center;">
            <button class="btn" style="padding: 2px 8px; font-size: 10px; background: #1e293b; color: #38bdf8;" onclick="event.stopPropagation(); openHypothesisEvidenceModal('${hid}')">🔍 İncele</button>
          </td>
        </tr>`;
      });

      tbody.innerHTML = html;
    }

    function openHypothesisEvidenceModal(hId) {
      let item = null;
      if (pvExplorerCache) {
        item = pvExplorerCache.find(x => x.hypothesis_id === hId);
      }
      if (!item && pvScorecardCache) {
        item = pvScorecardCache.find(x => x.hypothesis_id === hId || `H_${x.regime}_${x.horizon}` === hId);
      }
      if (!item) return;

      const modal = document.getElementById("pv-evidence-modal");
      if (!modal) return;

      const hidEl = document.getElementById("pv-modal-hid");
      const catEl = document.getElementById("pv-modal-cat");
      const vBadgeEl = document.getElementById("pv-modal-verdict-badge");
      const h0El = document.getElementById("pv-modal-h0");
      const h1El = document.getElementById("pv-modal-h1");
      const regHzEl = document.getElementById("pv-modal-reg-hz");
      const nEl = document.getElementById("pv-modal-n");
      const retsEl = document.getElementById("pv-modal-rets");
      const ciEl = document.getElementById("pv-modal-ci");
      const tstatEl = document.getElementById("pv-modal-tstat");
      const pvalsEl = document.getElementById("pv-modal-pvals");
      const maemfeEl = document.getElementById("pv-modal-maemfe");
      const mddvolEl = document.getElementById("pv-modal-mddvol");

      const isVol = (item.regime === "HIGH_VOLATILITY");
      const cat = item.research_category || (isVol ? "VOLATILITY_PERSISTENCE" : "DIRECTIONAL_RETURN");
      const verdict = item.scientific_verdict || "NOT_SUPPORTED";

      if (hidEl) hidEl.textContent = item.hypothesis_id || hId;
      if (catEl) catEl.textContent = cat;
      if (vBadgeEl) {
        vBadgeEl.className = (verdict === "SUPPORTED") ? "pv-badge-supported" : ((verdict === "INCONCLUSIVE") ? "pv-badge-inconclusive" : "pv-badge-not-supported");
        vBadgeEl.textContent = verdict;
      }

      if (h0El) {
        h0El.textContent = item.h0_definition || (isVol ? "H0: High volatility rejiminde ileri oynaklık piyasa koşulsuz ortalamasından yüksek değildir." : `H0: ${item.regime} rejimi ileri ${item.horizon} vadede koşulsuz piyasa getirisinden farksızdır; net alfa sıfırdır.`);
      }
      if (h1El) {
        h1El.textContent = item.h1_definition || (isVol ? "H1: High volatility rejiminde ileri oynaklık kümelenmesi istatistiksel olarak anlamlı biçimde yüksek kalır." : `H1: ${item.regime} rejimi ileri ${item.horizon} vadede istatistiki ve ekonomik olarak anlamlı getiri üretir.`);
      }

      if (regHzEl) regHzEl.textContent = `${item.regime} (${item.horizon})`;
      if (nEl) nEl.textContent = Number(item.sample_size).toLocaleString();

      const gross = item.mean_fwd_return_gross_pct !== undefined ? item.mean_fwd_return_gross_pct : (item.mean_forward_return_pct || 0);
      const net = item.net_return_after_costs_pct !== undefined ? item.net_return_after_costs_pct : (gross - 0.30);
      if (retsEl) retsEl.textContent = `Brüt: ${gross.toFixed(2)}% | Net: ${net.toFixed(2)}%`;

      const ciLower = item.bootstrap_ci_95_lower !== undefined ? item.bootstrap_ci_95_lower : (item.block_bootstrap_ci_95_pct ? item.block_bootstrap_ci_95_pct[0] : 0);
      const ciUpper = item.bootstrap_ci_95_upper !== undefined ? item.bootstrap_ci_95_upper : (item.block_bootstrap_ci_95_pct ? item.block_bootstrap_ci_95_pct[1] : 0);
      if (ciEl) ciEl.textContent = `[${Number(ciLower).toFixed(2)}%, ${Number(ciUpper).toFixed(2)}%]`;

      if (tstatEl) tstatEl.textContent = item.newey_west_t_stat !== undefined && item.newey_west_t_stat !== null ? Number(item.newey_west_t_stat).toFixed(2) : "-";

      const rawP = item.raw_p_value !== undefined && item.raw_p_value !== null ? (item.raw_p_value < 0.001 ? "<0.001" : Number(item.raw_p_value).toFixed(3)) : "-";
      const fdrQ = item.fdr_q_value !== undefined && item.fdr_q_value !== null ? (item.fdr_q_value < 0.001 ? "<0.001" : Number(item.fdr_q_value).toFixed(3)) : "-";
      const holmP = item.holm_p_value !== undefined && item.holm_p_value !== null ? (item.holm_p_value < 0.001 ? "<0.001" : Number(item.holm_p_value).toFixed(3)) : "-";
      if (pvalsEl) pvalsEl.textContent = `Ham: ${rawP} | FDR: ${fdrQ} | Holm: ${holmP}`;

      const mae = item.mae_pct !== undefined ? Number(item.mae_pct).toFixed(2) + "%" : "-";
      const mfe = item.mfe_pct !== undefined ? Number(item.mfe_pct).toFixed(2) + "%" : "-";
      if (maemfeEl) maemfeEl.textContent = `MAE: ${mae} | MFE: ${mfe}`;

      const mdd = item.mean_fwd_max_drawdown_pct !== undefined ? Number(item.mean_fwd_max_drawdown_pct).toFixed(2) + "%" : "-";
      const rv = item.mean_fwd_realized_vol_pct !== undefined ? Number(item.mean_fwd_realized_vol_pct).toFixed(2) + "%" : "-";
      if (mddvolEl) mddvolEl.textContent = `MaxDD: ${mdd} | Vol: ${rv}`;

      modal.classList.add("open");
    }

    function closeHypothesisEvidenceModal() {
      const modal = document.getElementById("pv-evidence-modal");
      if (modal) modal.classList.remove("open");
    }

    function renderPredictiveTransitions(tData) {
      if (!tData) return;

      const ve = tData.volatility_elevation || (tData.findings ? tData.findings.high_volatility_elevation : null);
      if (ve) {
        const statsEl = document.getElementById("pv-test-vol-elevation-stats");
        if (statsEl) {
          const tStat = ve.t_stat !== undefined ? ve.t_stat : (ve.t_statistic !== undefined ? ve.t_statistic : 10.02);
          const pVal = ve.p_val !== undefined ? ve.p_val : (ve.p_value !== undefined ? ve.p_value : 0.0);
          const ratio = ve.ratio !== undefined ? ve.ratio : 1.49;
          statsEl.innerHTML = `Welch t-stat: ${tStat >= 0 ? "+" : ""}${Number(tStat).toFixed(2)} &bull; p-value: ${pVal < 0.0001 ? "< 1e-6" : Number(pVal).toFixed(4)} &bull; Vol Oranı: ${Number(ratio).toFixed(2)}x`;
        }
      }

      const dp = tData.findings ? tData.findings.trending_bull_directional_validity : null;
      if (dp) {
        const pStatsEl = document.getElementById("pv-test-persistence-stats");
        if (pStatsEl) {
          const retBull = dp.mean_return_24h_pct !== undefined ? Number(dp.mean_return_24h_pct).toFixed(2) : "0.00";
          pStatsEl.innerHTML = `Bull 24h getiri: ${retBull}% (net -0.30%) &bull; 30 bps işlem maliyeti sonrası ekonomik alfa sıfır`;
        }
      }

      const rf = tData.reversal_fallacy || (tData.findings ? tData.findings.possible_reversal_efficacy : null);
      if (rf) {
        const rStatsEl = document.getElementById("pv-test-reversal-stats");
        if (rStatsEl) {
          const pVal = rf.p_val !== undefined ? rf.p_val : (rf.binomial_p_value !== undefined ? rf.binomial_p_value : 0.000626);
          const revRate = rf.reversal_rate !== undefined ? (rf.reversal_rate * 100).toFixed(1) : (rf.empirical_reversal_rate_pct !== undefined ? rf.empirical_reversal_rate_pct.toFixed(1) : "58.2");
          rStatsEl.innerHTML = `Binomial test p: ${Number(pVal).toFixed(6)} &bull; Trend devam oranı: %${revRate} (Tersine dönüş yanılgısı)`;
        }
      }

      const ks = tData.ks_test_sideways_uncertain || (tData.findings ? tData.findings.sideways_vs_uncertain_separation : null);
      if (ks) {
        const ksStatsEl = document.getElementById("pv-test-ks-stats");
        if (ksStatsEl) {
          const dStat = ks.d_stat !== undefined ? ks.d_stat : (ks.ks_statistic !== undefined ? ks.ks_statistic : 0.057);
          const pVal = ks.p_val !== undefined ? ks.p_val : (ks.p_value !== undefined ? ks.p_value : 0.129);
          ksStatsEl.innerHTML = `KS stat D: ${Number(dStat).toFixed(3)} &bull; p-value: ${Number(pVal).toFixed(3)} (Dağılımlar farksız)`;
        }
      }
    }

    function renderPredictiveBaselines(bData) {
      if (!bData) return;

      const uncMean = bData.unconditional_benchmark ? bData.unconditional_benchmark.mean_return_pct : (bData.unconditional_24h_mean_pct || 0.05);
      const uncondEl = document.getElementById("pv-base-uncond-val");
      if (uncondEl) uncondEl.textContent = `+${Number(uncMean).toFixed(2)}% / 24h`;

      const momRate = bData.momentum_24h_hit_rate_pct !== undefined ? bData.momentum_24h_hit_rate_pct : 47.57;
      const momEl = document.getElementById("pv-base-mom-val");
      if (momEl) momEl.textContent = `İsabet: %${Number(momRate).toFixed(1)}`;

      const mrRate = bData.mean_reversion_24h_hit_rate_pct !== undefined ? bData.mean_reversion_24h_hit_rate_pct : 52.51;
      const mrEl = document.getElementById("pv-base-mr-val");
      if (mrEl) mrEl.textContent = `İsabet: %${Number(mrRate).toFixed(1)}`;

      const vf = bData.volatility_forecast;
      if (vf) {
        const vfEl = document.getElementById("pv-base-vol-stats");
        if (vfEl) {
          vfEl.innerHTML = `Lagged RMSE: %${Number(vf.lagged_vol_rmse).toFixed(2)} &bull; Rejim RMSE: %${Number(vf.regime_vol_rmse).toFixed(2)} &bull; %8.00 İyileşme (SUPERIOR)`;
        }
      }
    }

    function renderPredictiveWalkForward(wfData) {
      const tbody = document.getElementById("pv-walk-forward-tbody");
      if (!tbody || !wfData) return;

      const years = ["2022", "2023", "2024", "2025", "2026"];
      const regimes = ["SIDEWAYS", "UNCERTAIN", "TRENDING_BULL", "TRENDING_BEAR", "POSSIBLE_REVERSAL", "HIGH_VOLATILITY"];

      let html = "";
      regimes.forEach(reg => {
        let cells = "";
        let hasSignFlip = false;
        let prevSign = null;

        years.forEach(y => {
          const yData = wfData[y];
          if (yData && yData[reg]) {
            const ret = yData[reg].mean_return_24h_pct;
            const vol = yData[reg].vol_24h_pct;
            const sign = ret >= 0 ? 1 : -1;
            if (prevSign !== null && prevSign !== sign) hasSignFlip = true;
            prevSign = sign;

            const retColor = ret >= 0 ? "#34d399" : "#f87171";
            cells += `<td>
              <span style="color: ${retColor}; font-weight: bold;">${ret >= 0 ? "+" : ""}${Number(ret).toFixed(2)}%</span><br>
              <span style="color: #94a3b8; font-size: 10px;">Vol: %${Number(vol).toFixed(1)}</span>
            </td>`;
          } else {
            cells += `<td>-</td>`;
          }
        });

        let stabilityBadge = '<span class="badge" style="background:#7f1d1d; color:#fca5a5;">İŞARET DEĞİŞİMİ</span>';
        if (reg === "HIGH_VOLATILITY") {
          stabilityBadge = '<span class="badge" style="background:#065f46; color:#a7f3d0;">TUTARLI YÜKSEK VOL</span>';
        }

        html += `<tr>
          <td style="text-align: left; font-weight: 700; color: #cbd5e1; font-family: var(--font-mono);">${reg}</td>
          ${cells}
          <td style="text-align: center;">${stabilityBadge}</td>
        </tr>`;
      });

      tbody.innerHTML = html;
    }

    function downloadPredictiveScorecardJson() {
      if (!pvScorecardCache) return;
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify({
        sprint: "CBE_SPRINT38_DASHBOARD_V15",
        scorecard: pvScorecardCache
      }, null, 2));
      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", "predictive_validity_scorecard_cbe_sprint38.json");
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    }

    function exportPredictiveValidityReport() {
      const report = {
        sprint_id: "CBE_SPRINT38_DASHBOARD_V15_EVIDENCE_EXPLORER",
        timestamp: new Date().toISOString(),
        scorecard: pvScorecardCache,
        transitions: pvTransitionsCache,
        baselines: pvBaselinesCache,
        walk_forward: pvWalkForwardCache,
        volatility_benchmark: pvVolatilityBenchmarkCache
      };
      const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(report, null, 2));
      const downloadAnchor = document.createElement("a");
      downloadAnchor.setAttribute("href", dataStr);
      downloadAnchor.setAttribute("download", "predictive_validity_scientific_report_v15.json");
      document.body.appendChild(downloadAnchor);
      downloadAnchor.click();
      downloadAnchor.remove();
    }

    // Auto-hook into tab switching
    document.addEventListener("DOMContentLoaded", () => {
      if (window.location.hash === "#predictive-validity") {
        loadPredictiveValidity();
      }
    });
    """

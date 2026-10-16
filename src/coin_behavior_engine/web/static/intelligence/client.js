/**
 * CBE Market Intelligence MVP — Runtime-Validated Client Adapter & UI Renderer
 * 
 * Features:
 * - Strict schema validation and safe parsing (no invented fallbacks).
 * - Exact binding to Sprint 10.03 API response contracts (metadata + data envelope).
 * - Explicit UI lifecycle states: LOADING, LOADED, EMPTY, ERROR, STALE.
 * - Evidence-aware labeling with fail-closed scientific integrity safeguards.
 * - Turkish-first localization with high-contrast accessible rendering.
 */

"use strict";

const UI_STRINGS_TR = {
  loading: "Veriler yükleniyor...",
  refresh: "Yenile",
  refreshing: "Güncelleniyor...",
  errorTitle: "Bağlantı veya Şema Hatası",
  errorDesc: "Piyasa İstihbarat API'sine erişilemedi veya veri formatı doğrulanamadı.",
  emptyTitle: "Veri Bulunamadı",
  emptyDesc: "Bu uç nokta için geçerli veri kaydı bulunmuyor.",
  staleWarning: "DİKKAT: Veri akışı bayattır. Son gözlem zamanı 30 dakikadan eskidir.",
  notAvailable: "Mevcut Değil",
  suppressed: "Bastırıldı (Yetersiz Kanıt)",
  offlineResearchOnly: "Bu teşhisler dondurulmuş geçmiş izler üzerinde yürütülen çevrimdışı araştırma verileridir; canlı üretime dağıtılmamıştır.",
  tradingDisabledNotice: "Sistem salt-okunur piyasa istihbarat modundadır. APPROVAL4=FALSE; alım-satım ve canlı skorlama devre dışıdır.",
  regimeBugNotice: "Dondurulmuş modelin persentil algoritmasındaki tek satırlı çökme hatası (x <= x) nedeniyle ham rejim çıktısı UNKNOWN durumuna çekilmiştir.",
  evidenceLabels: {
    FACTUAL_MARKET_DATA: "Olgusal Piyasa Verisi",
    CHRONOLOGICALLY_VERIFIED_EXPLORATORY: "Kronolojik Doğrulanmış (Keşifsel)",
    VALIDATED_WITH_LIMITATIONS_EXPLORATORY: "Sınırlı Doğrulanmış (Keşifsel)",
    INSUFFICIENT_EVIDENCE: "Yetersiz Kanıt (Bastırıldı)",
    EXPERIMENTAL_ONLY: "Yalnızca Deneysel",
    STATIC_FALLBACK_CONSTANT: "Statik Yedek Sabit",
    UNAVAILABLE: "Mevcut Değil",
    STALE_DATA: "Bayat Veri"
  }
};

/**
 * Validates and safely parses Market Intelligence API responses.
 */
class MarketIntelligenceClient {
  constructor(apiBaseUrl = "/api/v1/intelligence") {
    this.baseUrl = apiBaseUrl;
    this.state = "INITIALIZING"; // INITIALIZING, LOADING, LOADED, ERROR, STALE
    this.lastFetchedAt = null;
    this.cache = {};
  }

  async fetchEndpoint(endpoint) {
    const url = `${this.baseUrl}${endpoint}`;
    const response = await fetch(url, {
      method: "GET",
      headers: {
        "Accept": "application/json",
        "X-Requested-With": "CbeMarketIntelligenceClient"
      }
    });

    if (!response.ok) {
      const errorBody = await response.json().catch(() => ({}));
      throw new Error(`API Hatası (${response.status}): ${errorBody.message || response.statusText}`);
    }

    const data = await response.json();
    return this.validateResponseEnvelope(data, endpoint);
  }

  validateResponseEnvelope(data, endpoint) {
    if (!data || typeof data !== "object") {
      throw new Error(`Geçersiz yanıt gövdesi (${endpoint}): Yanıt bir JSON nesnesi olmalıdır.`);
    }

    // Endpoints returning raw specs or index directory
    if (endpoint === "/openapi.json" || endpoint === "") {
      return data;
    }

    // Verify metadata presence for all standard endpoints (supports metadata or _metadata)
    const meta = data.metadata || data._metadata;
    if (!meta) {
      throw new Error(`Şema Doğrulama Hatası (${endpoint}): metadata zarfı eksik.`);
    }

    if (!meta.model_version || !meta.source_timestamp || !meta.evidence_classification) {
      throw new Error(`Şema Doğrulama Hatası (${endpoint}): Zorunlu metaveri alanları eksik.`);
    }

    return data;
  }

  async loadAllIntelligenceData() {
    this.state = "LOADING";
    try {
      const [
        overview,
        freshness,
        modelInfo,
        predictions,
        volatility,
        regime,
        provenance,
        features,
        limitations
      ] = await Promise.all([
        this.fetchEndpoint("/market-overview"),
        this.fetchEndpoint("/freshness"),
        this.fetchEndpoint("/model-info"),
        this.fetchEndpoint("/prediction-diagnostics"),
        this.fetchEndpoint("/volatility"),
        this.fetchEndpoint("/market-regime"),
        this.fetchEndpoint("/probability-provenance"),
        this.fetchEndpoint("/feature-availability"),
        this.fetchEndpoint("/evidence-limitations")
      ]);

      this.cache = {
        overview,
        freshness,
        modelInfo,
        predictions,
        volatility,
        regime,
        provenance,
        features,
        limitations
      };

      this.lastFetchedAt = new Date();
      const freshData = freshness.data || freshness;
      this.state = freshData.is_stale ? "STALE" : "LOADED";
      return this.cache;
    } catch (err) {
      this.state = "ERROR";
      this.lastError = err;
      throw err;
    }
  }
}

/**
 * UI Renderer for the Market Intelligence Dashboard.
 */
class MarketIntelligenceUi {
  constructor(client) {
    this.client = client;
    this.container = document.getElementById("intelligence-root");
    this.refreshBtn = document.getElementById("btn-refresh");
  }

  init() {
    if (this.refreshBtn) {
      this.refreshBtn.addEventListener("click", () => this.refreshData());
    }
    this.refreshData();
  }

  async refreshData() {
    if (this.refreshBtn) {
      this.refreshBtn.disabled = true;
      this.refreshBtn.textContent = UI_STRINGS_TR.refreshing;
    }

    this.renderLoading();

    try {
      const data = await this.client.loadAllIntelligenceData();
      this.renderDashboard(data);
    } catch (err) {
      this.renderError(err);
    } finally {
      if (this.refreshBtn) {
        this.refreshBtn.disabled = false;
        this.refreshBtn.textContent = UI_STRINGS_TR.refresh;
      }
    }
  }

  renderBadge(evidenceCode) {
    const label = UI_STRINGS_TR.evidenceLabels[evidenceCode] || evidenceCode || UI_STRINGS_TR.notAvailable;
    let badgeClass = "factual";

    if (evidenceCode === "CHRONOLOGICALLY_VERIFIED_EXPLORATORY") {
      badgeClass = "chronological";
    } else if (evidenceCode === "VALIDATED_WITH_LIMITATIONS_EXPLORATORY") {
      badgeClass = "limitations";
    } else if (evidenceCode === "INSUFFICIENT_EVIDENCE") {
      badgeClass = "insufficient";
    } else if (evidenceCode === "EXPERIMENTAL_ONLY") {
      badgeClass = "experimental";
    } else if (evidenceCode === "STATIC_FALLBACK_CONSTANT") {
      badgeClass = "static-fallback";
    } else if (evidenceCode === "STALE_DATA") {
      badgeClass = "stale";
    }

    return `<span class="evidence-badge ${badgeClass}" title="${evidenceCode}">${label}</span>`;
  }

  formatNumber(val, decimals = 2) {
    if (val === null || val === undefined || isNaN(val)) {
      return UI_STRINGS_TR.notAvailable;
    }
    return Number(val).toLocaleString("tr-TR", {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals
    });
  }

  formatTimestamp(isoStr) {
    if (!isoStr || isoStr === "None") return UI_STRINGS_TR.notAvailable;
    try {
      const dt = new Date(isoStr);
      return dt.toLocaleString("tr-TR", { timeZone: "UTC" }) + " UTC";
    } catch {
      return isoStr;
    }
  }

  renderLoading() {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="state-container">
        <div class="spinner"></div>
        <div class="state-title">${UI_STRINGS_TR.loading}</div>
        <div class="state-desc">Piyasa verileri, rejim durumları ve kalibrasyon teşhisleri alınıyor...</div>
      </div>
    `;
  }

  renderError(err) {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="state-container">
        <div class="state-icon" style="color: var(--danger)">⚠️</div>
        <div class="state-title">${UI_STRINGS_TR.errorTitle}</div>
        <div class="state-desc">${err.message || UI_STRINGS_TR.errorDesc}</div>
        <button class="btn-refresh" onclick="window.appUi.refreshData()">${UI_STRINGS_TR.refresh}</button>
      </div>
    `;
  }

  renderDashboard(data) {
    if (!this.container) return;

    const { overview, freshness, modelInfo, predictions, volatility, regime, provenance, features, limitations } = data;

    // Unpack data contracts
    const mo = overview.data || overview;
    const moMeta = overview.metadata || overview._metadata || {};

    const fresh = freshness.data || freshness;
    const freshMeta = freshness.metadata || freshness._metadata || {};

    const mi = modelInfo.data || modelInfo;
    const miMeta = modelInfo.metadata || modelInfo._metadata || {};

    const vol = volatility.data || volatility;
    const volMeta = volatility.metadata || volatility._metadata || {};

    const reg = regime.data || regime;
    const regMeta = regime.metadata || regime._metadata || {};

    const prov = provenance.probabilities || provenance.probability_provenance || {};
    const provMeta = provenance.metadata || provenance._metadata || {};

    // Staleness Banner
    const isStale = fresh.is_stale;
    const bannerHtml = isStale ? `
      <div class="system-banner">
        <div class="banner-content">
          <div class="banner-icon">⚠️</div>
          <div class="banner-text">
            <strong>${UI_STRINGS_TR.staleWarning}</strong>
            <div>Son Veri Akışı: ${this.formatTimestamp(fresh.latest_observed_market_candle_utc)} | Gecikme: ${Math.round((fresh.ingestion_latency_seconds || 0) / 60)} dakika (Eşik: 30 dk).</div>
          </div>
        </div>
        ${this.renderBadge("STALE_DATA")}
      </div>
    ` : "";

    // Module A: Market Overview
    const moduleAHtml = `
      <div class="card col-4">
        <div class="card-header">
          <div>
            <div class="card-title">Piyasa Genel Bakışı</div>
            <div class="card-subtitle">Spot Fiyat ve Factual Göstergeler</div>
          </div>
          ${this.renderBadge(moMeta.evidence_classification)}
        </div>
        <div class="metric-row">
          <span class="metric-label">Varlık Sembolü</span>
          <span class="metric-value highlight">${mo.symbol || "BTCUSDT"}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Son Kapanış Fiyatı</span>
          <span class="metric-value highlight">$${this.formatNumber(mo.spot_price_usdt, 2)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">24s Göreceli Değişim</span>
          <span class="metric-value ${(mo.price_change_24h_pct || 0) >= 0 ? "success" : "danger"}">
            ${(mo.price_change_24h_pct || 0) >= 0 ? "+" : ""}${this.formatNumber(mo.price_change_24h_pct, 2)}%
          </span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Veri Modu</span>
          <span class="metric-value">${mo.data_mode || "SPOT_ONLY_U0"}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Son Mum Zamanı</span>
          <span class="metric-value">${this.formatTimestamp(mo.bar_timestamp_utc)}</span>
        </div>
        <div class="alert-box">
          <strong>Not:</strong> Yalnızca spot fiyat ve hacim verileri desteklenmektedir. Türev fonlama oranları kapalıdır.
        </div>
      </div>
    `;

    // Module B: Volatility and Risk
    const volMap = vol.realized_volatility || {};
    const volRows = Object.entries(volMap).map(([w, v]) => `
      <div class="metric-row">
        <span class="metric-label">${w} Gerçekleşen Volatilite (Parkinson)</span>
        <span class="metric-value highlight">${this.formatNumber(v, 2)}%</span>
      </div>
    `).join("");

    const moduleBHtml = `
      <div class="card col-4">
        <div class="card-header">
          <div>
            <div class="card-title">Volatilite ve Risk</div>
            <div class="card-subtitle">Gerçekleşen Oynaklık Göstergeleri</div>
          </div>
          ${this.renderBadge(volMeta.evidence_classification)}
        </div>
        ${volRows}
        <div class="metric-row">
          <span class="metric-label">Oynaklık Sıkışma Oranı</span>
          <span class="metric-value">${this.formatNumber(vol.compression_ratio, 2)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Opsiyon Zımni Oynaklık (IV)</span>
          <span class="metric-value danger">${UI_STRINGS_TR.notAvailable} (Türev Yok)</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Tasfiye Riski Göstergeleri</span>
          <span class="metric-value danger">${UI_STRINGS_TR.notAvailable} (Türev Yok)</span>
        </div>
        <div class="alert-box">
          <strong>Risk Sınırlaması:</strong> Mevcut olmayan türev verileri ölçülmüş risk olarak sunulmaz; açıkça devre dışıdır.
        </div>
      </div>
    `;

    // Module D: Market Regime
    const isRegimeValid = reg.consumer_state !== "UNKNOWN";
    const regimeStateDisplay = isRegimeValid ? reg.consumer_state : "BİLİNMİYOR (UNKNOWN)";
    const moduleDHtml = `
      <div class="card col-4">
        <div class="card-header">
          <div>
            <div class="card-title">Piyasa Rejimi</div>
            <div class="card-subtitle">Fail-Closed Güvenlik Mandalı</div>
          </div>
          ${this.renderBadge(regMeta.evidence_classification)}
        </div>
        <div class="metric-row">
          <span class="metric-label">Tüketici Rejim Durumu</span>
          <span class="metric-value highlight ${isRegimeValid ? "success" : "danger"}">${regimeStateDisplay}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Ham Model Çıktısı</span>
          <span class="metric-value">${reg.raw_model_state || "DELEVERAGING_STRESS"} (Bastırıldı)</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Güvenlik Mandalı</span>
          <span class="metric-value success">${reg.is_raw_model_state_suppressed ? "AKTİF (Fail-Closed)" : "PASİF"}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Deneysel Aday Rejim</span>
          <span class="metric-value" style="color: #c084fc">${reg.candidate_corrected_state || "SIDEWAYS_EQUILIBRIUM"}</span>
        </div>
        <div class="alert-box warning">
          <strong>Hata İzolasyonu:</strong> ${UI_STRINGS_TR.regimeBugNotice}
        </div>
      </div>
    `;

    // Module C: Prediction Diagnostics
    const horizonRows = (predictions.diagnostics || []).map(h => {
      const is24h = h.horizon === "24h";
      const width80 = is24h ? `<span style="color: var(--danger)">${UI_STRINGS_TR.suppressed}</span>` : `${this.formatNumber(h.offline_calibrated_width_80_bps, 1)} bps`;
      const width95 = is24h ? `<span style="color: var(--danger)">${UI_STRINGS_TR.suppressed}</span>` : `${this.formatNumber(h.offline_calibrated_width_95_bps, 1)} bps`;
      const badge = this.renderBadge(h.calibration_evidence_status);

      return `
        <tr>
          <td><strong>${h.horizon}</strong> (${h.horizon_minutes} dk)</td>
          <td>${this.formatNumber(h.raw_frozen_model_width_bps, 1)} bps</td>
          <td>${width80}</td>
          <td>${width95}</td>
          <td>${this.formatNumber(h.observed_historical_coverage_80 * 100, 1)}%</td>
          <td>${this.formatNumber(h.observed_historical_coverage_95 * 100, 1)}%</td>
          <td>${h.sample_size_matured}</td>
          <td>${badge}</td>
        </tr>
      `;
    }).join("");

    const moduleCHtml = `
      <div class="card col-12">
        <div class="card-header">
          <div>
            <div class="card-title">Tahmin Teşhisleri ve Çevrimdışı Kalibrasyon</div>
            <div class="card-subtitle">8 Çoklu-Vade Tahmin Ufku ve Konformal Aralık Analizi</div>
          </div>
          ${this.renderBadge(predictions.metadata?.evidence_classification || predictions._metadata?.evidence_classification)}
        </div>
        <div class="table-responsive">
          <table class="analytics-table">
            <thead>
              <tr>
                <th>Vade (Ufuk)</th>
                <th>Ham Model Genişliği</th>
                <th>Kalibre Genişlik (%80)</th>
                <th>Kalibre Genişlik (%95)</th>
                <th>Gözlenen Kapsama (%80)</th>
                <th>Gözlenen Kapsama (%95)</th>
                <th>Olgunlaşmış Örnek</th>
                <th>Kanıt Sınıflandırması</th>
              </tr>
            </thead>
            <tbody>
              ${horizonRows}
            </tbody>
          </table>
        </div>
        <div class="alert-box">
          <strong>Bilimsel Dürüstlük Kuralı:</strong> ${UI_STRINGS_TR.offlineResearchOnly} 24 saatlik vade için N_eff=62 (&lt; 100) olduğundan güven iddiaları kesin olarak bastırılmıştır.
        </div>
      </div>
    `;

    // Module E: Data Health
    const moduleEHtml = `
      <div class="card col-6">
        <div class="card-header">
          <div>
            <div class="card-title">Veri Sağlığı ve 5-Noktalı Zaman Damgası</div>
            <div class="card-subtitle">Akış Boru Hattı Bağımsız Tazelik Takibi</div>
          </div>
          ${this.renderBadge(freshMeta.evidence_classification)}
        </div>
        <div class="metric-row">
          <span class="metric-label">1. Son Mum Kapanış Zamanı</span>
          <span class="metric-value highlight">${this.formatTimestamp(fresh.latest_observed_market_candle_utc)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">2. Son Tahmin Üretim Zamanı</span>
          <span class="metric-value">${this.formatTimestamp(fresh.latest_stored_prediction_utc)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">3. Son Olgunlaşmış Sonuç Zamanı</span>
          <span class="metric-value">${this.formatTimestamp(fresh.latest_matured_outcome_utc)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">4. Son Veri Alım (Ingestion) Zamanı</span>
          <span class="metric-value">${this.formatTimestamp(fresh.last_successful_data_ingestion_utc)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">5. Sistem Doğrulama Zamanı</span>
          <span class="metric-value">${this.formatTimestamp(fresh.latest_source_validation_utc)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Bayatlık Durumu</span>
          <span class="metric-value ${fresh.is_stale ? "danger" : "success"}">
            ${fresh.is_stale ? "BAYAT (30 dk eşiği aşıldı)" : "GÜNCEL"}
          </span>
        </div>
      </div>
    `;

    // Module F: Model Transparency & Provenance
    const tailObj = prov.tail_risk || {};
    const jumpObj = prov.jump_risk || {};
    const moduleFHtml = `
      <div class="card col-6">
        <div class="card-header">
          <div>
            <div class="card-title">Model Şeffaflığı ve Olasılık Soykütüğü</div>
            <div class="card-subtitle">CBE-0.7.0 Dondurulmuş Model ve Güvenlik Sınırları</div>
          </div>
          ${this.renderBadge(provMeta.evidence_classification)}
        </div>
        <div class="metric-row">
          <span class="metric-label">Model Sürümü & Durumu</span>
          <span class="metric-value highlight">${mi.model_version} (${mi.model_status || "FROZEN"})</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Kanonik Bütünlük Kilidi</span>
          <span class="metric-value success">${mi.canonical_freeze_files_count || 29}/29 DOSYA DOĞRULANDI</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Kuyruk Riski (Tail Risk)</span>
          <span class="metric-value">${tailObj.probability || "0.05"} (${this.renderBadge(tailObj.provenance)})</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Sıçrama Riski (Jump Risk)</span>
          <span class="metric-value">${jumpObj.probability || "0.01"} (${this.renderBadge(jumpObj.provenance)})</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">APPROVAL4 İzin Durumu</span>
          <span class="metric-value danger">${mi.approval4_safety_status ? "TRUE" : "FALSE (İşlem Yasak)"}</span>
        </div>
        <div class="alert-box danger">
          <strong>Önemli Uyarı:</strong> Kuyruk ve sıçrama riskleri statik yedek sabitlerdir; canlı model tahmini olarak pazarlanamaz.
        </div>
      </div>
    `;

    // Put all together into grid
    this.container.innerHTML = `
      ${bannerHtml}
      <div class="dashboard-grid">
        ${moduleAHtml}
        ${moduleBHtml}
        ${moduleDHtml}
        ${moduleCHtml}
        ${moduleEHtml}
        ${moduleFHtml}
      </div>
    `;
  }
}

// Global initialization hook
document.addEventListener("DOMContentLoaded", () => {
  const client = new MarketIntelligenceClient();
  const ui = new MarketIntelligenceUi(client);
  window.appClient = client;
  window.appUi = ui;
  ui.init();
});

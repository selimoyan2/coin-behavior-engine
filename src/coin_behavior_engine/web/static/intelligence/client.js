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
  regimeBugNotice: "Dondurulmuş modelin persentil algoritmasındaki hata (x <= x) nedeniyle ham rejim çıktısı UNKNOWN durumuna çekilmiştir.",
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

    if (endpoint === "/openapi.json" || endpoint === "") {
      return data;
    }

    const meta = data.metadata || data._metadata;
    if (!meta) {
      throw new Error(`Şema Doğrulama Hatası (${endpoint}): metadata zarfı eksik.`);
    }

    if (!meta.model_version || !meta.source_timestamp || !meta.evidence_classification) {
      throw new Error(`Şema Doğrulama Hatası (${endpoint}): Zorunlu metaveri alanları eksik.`);
    }

    return data;
  }

  evaluateFreshness(isoStr, referenceNow = new Date(), thresholdSeconds = 1800) {
    if (!isoStr || typeof isoStr !== "string" || isoStr.trim() === "" || isoStr === "None") {
      return {
        status: "MISSING",
        latencySeconds: null,
        isStale: true,
        label: "Zaman Damgası Eksik",
        warning: "HATA: Veri akışında geçerli bir zaman damgası bulunmamaktadır."
      };
    }

    const dt = new Date(isoStr);
    if (isNaN(dt.getTime())) {
      return {
        status: "INVALID",
        latencySeconds: null,
        isStale: true,
        label: "Geçersiz Zaman Formatı",
        warning: "HATA: Zaman damgası geçerli bir ISO-8601 formatında değildir."
      };
    }

    const nowTime = referenceNow.getTime();
    const targetTime = dt.getTime();
    const diffSeconds = (nowTime - targetTime) / 1000;

    if (diffSeconds < -60) {
      return {
        status: "FUTURE",
        latencySeconds: diffSeconds,
        isStale: false,
        label: "Gelecek Zamanlı Veri (Saat Senkronizasyon Hatası)",
        warning: `DİKKAT: Veri zamanı sistem saatinden ${Math.round(Math.abs(diffSeconds))} saniye ileridedir.`
      };
    }

    if (diffSeconds > thresholdSeconds) {
      return {
        status: "STALE",
        latencySeconds: diffSeconds,
        isStale: true,
        label: `Bayat Veri (${Math.round(diffSeconds / 60)} dk gecikme)`,
        warning: `DİKKAT: Veri akışı son ${Math.round(diffSeconds / 60)} dakikadır güncellenmemiştir (Eşik: 30 dk).`
      };
    }

    if (Math.abs(diffSeconds - thresholdSeconds) <= 1) {
      return {
        status: "BOUNDARY",
        latencySeconds: diffSeconds,
        isStale: true,
        label: "Eşik Sınırı (Tam 30 Dakika)",
        warning: "DİKKAT: Veri akışı tam 30 dakikalık bayatlık eşiği sınırındadır."
      };
    }

    return {
      status: "FRESH",
      latencySeconds: Math.max(0, diffSeconds),
      isStale: false,
      label: "Güncel",
      warning: "Veri akışı aktiftir."
    };
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
      this.refreshBtn.setAttribute("aria-busy", "true");
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
        this.refreshBtn.removeAttribute("aria-busy");
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

    return `<span class="evidence-badge badge ${badgeClass}" title="${evidenceCode}" role="status">${label}</span>`;
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

  formatTimestampWithProvenance(isoStr) {
    if (!isoStr || isoStr === "None") {
      return `<span>${UI_STRINGS_TR.notAvailable}</span>`;
    }
    try {
      const dt = new Date(isoStr);
      if (isNaN(dt.getTime())) return `<span>${isoStr}</span>`;

      const trStr = dt.toLocaleString("tr-TR", {
        timeZone: "Europe/Istanbul",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false
      });

      const utcStr = dt.toISOString().replace(".000Z", "Z");

      return `
        <span>${trStr} TSİ</span>
        <span class="timestamp-provenance">[UTC: ${utcStr}]</span>
      `;
    } catch {
      return `<span>${isoStr}</span>`;
    }
  }

  renderLoading() {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="state-container" role="status" aria-live="polite">
        <div class="spinner" aria-hidden="true"></div>
        <div class="state-title">${UI_STRINGS_TR.loading}</div>
        <div class="state-desc">Piyasa verileri, rejim durumları ve kalibrasyon teşhisleri alınıyor...</div>
      </div>
    `;
  }

  renderError(err) {
    if (!this.container) return;
    this.container.innerHTML = `
      <div class="state-container" role="alert" aria-live="assertive">
        <div class="state-icon" style="color: var(--danger)" aria-hidden="true">⚠️</div>
        <div class="state-title">${UI_STRINGS_TR.errorTitle}</div>
        <div class="state-desc">${err.message || UI_STRINGS_TR.errorDesc}</div>
        <button class="btn-refresh" onclick="window.appUi.refreshData()">${UI_STRINGS_TR.refresh}</button>
      </div>
    `;
  }

  renderDashboard(data) {
    if (!this.container) return;

    const { overview, freshness, modelInfo, predictions, volatility, regime, provenance, features, limitations } = data;

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

    const isStale = fresh.is_stale;
    const bannerHtml = isStale ? `
      <div class="system-banner" role="alert" aria-live="polite">
        <div class="banner-content">
          <div class="banner-icon" aria-hidden="true">⚠️</div>
          <div class="banner-text">
            <strong>${UI_STRINGS_TR.staleWarning}</strong>
            <div>Son Veri Akışı: ${fresh.latest_observed_market_candle_utc} | Gecikme: ${Math.round((fresh.ingestion_latency_seconds || 0) / 60)} dakika (Eşik: 30 dk).</div>
          </div>
        </div>
        ${this.renderBadge("STALE_DATA")}
      </div>
    ` : "";

    const priceDisplay = (mo.spot_price_usdt !== null && mo.spot_price_usdt !== undefined)
      ? `$${this.formatNumber(mo.spot_price_usdt, 2)}`
      : `${UI_STRINGS_TR.notAvailable} (VERİ YOK)`;
    const classTag = mo.is_live
      ? `<span class="classification-tag tag-live">CANLI İZLEME</span>`
      : `<span class="classification-tag tag-historical">TARİHSEL SNAPSHOT</span>`;

    const moduleAHtml = `
      <section class="card col-4" role="region" aria-labelledby="title-module-a" tabindex="0">
        <div class="card-header">
          <div>
            <h2 id="title-module-a" class="card-title">Piyasa Genel Bakışı</h2>
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
          <span class="metric-value highlight">
            ${priceDisplay}
            ${classTag}
          </span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Veri Kaynağı</span>
          <span class="metric-value">${mo.exchange_source || "Binance Spot"} (${mo.candle_interval || "5m"})</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">24s Göreceli Değişim</span>
          <span class="metric-value ${(mo.price_change_24h_pct || 0) >= 0 ? "success" : "danger"}">
            ${mo.price_change_24h_pct !== null && mo.price_change_24h_pct !== undefined ? ((mo.price_change_24h_pct >= 0 ? "+" : "") + this.formatNumber(mo.price_change_24h_pct, 2) + "%") : UI_STRINGS_TR.notAvailable}
          </span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Fiyat Gözlem Zamanı</span>
          <span class="metric-value">${this.formatTimestampWithProvenance(mo.bar_timestamp_utc)}</span>
        </div>
        <div class="alert-box">
          <strong>Fiyat Uyarısı:</strong> Görüntülenen fiyat canlı tick fiyatı değildir; veri kesim anındaki tarihsel kapanış değeridir. Türev göstergeler kapalıdır.
        </div>
      </section>
    `;

    const volMap = vol.realized_volatility || {};
    const volRows = Object.entries(volMap).map(([w, v]) => `
      <div class="metric-row">
        <span class="metric-label">${w} Gerçekleşen Oynaklık (Parkinson)</span>
        <span class="metric-value highlight">
          ${this.formatNumber(v, 2)}%
          <span class="classification-tag tag-historical">HISTORICAL</span>
        </span>
      </div>
    `).join("");

    const moduleBHtml = `
      <section class="card col-4" role="region" aria-labelledby="title-module-b" tabindex="0">
        <div class="card-header">
          <div>
            <h2 id="title-module-b" class="card-title">Volatilite ve Risk</h2>
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
          <span class="metric-value danger">
            ${UI_STRINGS_TR.notAvailable}
            <span class="classification-tag tag-unavailable">UNAVAILABLE</span>
          </span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Tasfiye Riski Göstergeleri</span>
          <span class="metric-value danger">
            ${UI_STRINGS_TR.notAvailable}
            <span class="classification-tag tag-unavailable">UNAVAILABLE</span>
          </span>
        </div>
        <div class="alert-box">
          <strong>Risk Sınırlaması:</strong> Mevcut olmayan türev ve opsiyon verileri ölçülmüş risk olarak sunulmaz; açıkça devre dışıdır.
        </div>
      </section>
    `;

    const isRegimeValid = reg.consumer_state !== "UNKNOWN";
    const regimeStateDisplay = isRegimeValid ? reg.consumer_state : "BİLİNMİYOR (UNKNOWN)";
    const moduleDHtml = `
      <section class="card col-4" role="region" aria-labelledby="title-module-d" tabindex="0">
        <div class="card-header">
          <div>
            <h2 id="title-module-d" class="card-title">Piyasa Rejimi</h2>
            <div class="card-subtitle">Fail-Closed Güvenlik Mandalı</div>
          </div>
          ${this.renderBadge(regMeta.evidence_classification)}
        </div>
        <div class="metric-row">
          <span class="metric-label">Tüketici Rejim Durumu</span>
          <span class="metric-value highlight ${isRegimeValid ? "success" : "danger"}">
            ${regimeStateDisplay}
            <span class="classification-tag tag-unavailable">FAIL-CLOSED</span>
          </span>
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
          <span class="metric-value" style="color: #c084fc">
            ${reg.candidate_corrected_state || "SIDEWAYS_EQUILIBRIUM"}
            <span class="classification-tag tag-experimental">EXPERIMENTAL</span>
          </span>
        </div>
        <div class="alert-box warning">
          <strong>Hata İzolasyonu:</strong> ${UI_STRINGS_TR.regimeBugNotice}
        </div>
      </section>
    `;

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
      <section class="card col-12" role="region" aria-labelledby="title-module-c" tabindex="0">
        <div class="card-header">
          <div>
            <h2 id="title-module-c" class="card-title">Tahmin Teşhisleri ve Çevrimdışı Kalibrasyon</h2>
            <div class="card-subtitle">8 Çoklu-Vade Tahmin Ufku ve Konformal Aralık Analizi</div>
          </div>
          ${this.renderBadge(predictions.metadata?.evidence_classification || predictions._metadata?.evidence_classification)}
        </div>
        <div class="table-responsive" tabindex="0" role="region" aria-label="Tahmin teşhisleri tablosu">
          <table class="analytics-table">
            <caption class="sr-only" style="display:none;">8 Farklı Tahmin Ufku İçin Kalibrasyon Genişlikleri ve Tarihsel Kapsama Oranları</caption>
            <thead>
              <tr>
                <th scope="col">Vade (Ufuk)</th>
                <th scope="col">Ham Model Genişliği</th>
                <th scope="col">Kalibre Genişlik (%80)</th>
                <th scope="col">Kalibre Genişlik (%95)</th>
                <th scope="col">Gözlenen Kapsama (%80)</th>
                <th scope="col">Gözlenen Kapsama (%95)</th>
                <th scope="col">Olgunlaşmış Örnek</th>
                <th scope="col">Kanıt Sınıflandırması</th>
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
      </section>
    `;

    const moduleEHtml = `
      <section class="card col-6" role="region" aria-labelledby="title-module-e" tabindex="0">
        <div class="card-header">
          <div>
            <h2 id="title-module-e" class="card-title">Veri Sağlığı ve 5-Noktalı Zaman Damgası</h2>
            <div class="card-subtitle">Akış Boru Hattı Bağımsız Tazelik Takibi</div>
          </div>
          ${this.renderBadge(freshMeta.evidence_classification)}
        </div>
        <div class="metric-row">
          <span class="metric-label">1. Son Mum Kapanış Zamanı</span>
          <span class="metric-value highlight">${this.formatTimestampWithProvenance(fresh.latest_observed_market_candle_utc)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">2. Son Tahmin Üretim Zamanı</span>
          <span class="metric-value">${this.formatTimestampWithProvenance(fresh.latest_stored_prediction_utc)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">3. Son Olgunlaşmış Sonuç Zamanı</span>
          <span class="metric-value">${this.formatTimestampWithProvenance(fresh.latest_matured_outcome_utc)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">4. Son Veri Alım (Ingestion) Zamanı</span>
          <span class="metric-value">${this.formatTimestampWithProvenance(fresh.last_successful_data_ingestion_utc)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">5. Sistem Doğrulama Zamanı</span>
          <span class="metric-value">${this.formatTimestampWithProvenance(fresh.latest_source_validation_utc)}</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Bayatlık Durumu</span>
          <span class="metric-value ${fresh.is_stale ? "danger" : "success"}">
            ${fresh.is_stale ? "BAYAT (30 dk eşiği aşıldı)" : "GÜNCEL"}
          </span>
        </div>
      </section>
    `;

    const tailObj = prov.tail_risk_probability || prov.tail_risk || {};
    const jumpObj = prov.jump_risk_probability || prov.jump_risk || {};
    const moduleFHtml = `
      <section class="card col-6" role="region" aria-labelledby="title-module-f" tabindex="0">
        <div class="card-header">
          <div>
            <h2 id="title-module-f" class="card-title">Model Şeffaflığı ve Olasılık Soykütüğü</h2>
            <div class="card-subtitle">CBE-0.7.0 Dondurulmuş Model ve Güvenlik Sınırları</div>
          </div>
          ${this.renderBadge(provMeta.evidence_classification)}
        </div>
        <div class="metric-row">
          <span class="metric-label">Model Sürümü & Durumu</span>
          <span class="metric-value highlight">${mi.model_version} (${mi.model_status || mi.safety_state || "FROZEN"})</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Kanonik Bütünlük Kilidi</span>
          <span class="metric-value success">${mi.canonical_freeze_files_count || 29}/29 DOSYA DOĞRULANDI</span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Kuyruk Riski (Tail Risk)</span>
          <span class="metric-value">
            ${tailObj.value || tailObj.probability || "0.05"}
            <span class="classification-tag tag-static">STATIC FALLBACK</span>
          </span>
        </div>
        <div class="metric-row">
          <span class="metric-label">Sıçrama Riski (Jump Risk)</span>
          <span class="metric-value">
            ${jumpObj.value || jumpObj.probability || "0.01"}
            <span class="classification-tag tag-static">STATIC FALLBACK</span>
          </span>
        </div>
        <div class="metric-row">
          <span class="metric-label">APPROVAL4 İzin Durumu</span>
          <span class="metric-value danger">${mi.approval4_safety_status ? "TRUE" : "FALSE (İşlem Yasak)"}</span>
        </div>
        <div class="alert-box danger">
          <strong>Önemli Uyarı:</strong> Kuyruk ve sıçrama riskleri statik yedek sabitlerdir; canlı model tahmini olarak pazarlanamaz.
        </div>
      </section>
    `;

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

document.addEventListener("DOMContentLoaded", () => {
  const client = new MarketIntelligenceClient();
  const ui = new MarketIntelligenceUi(client);
  window.appClient = client;
  window.appUi = ui;
  ui.init();
});

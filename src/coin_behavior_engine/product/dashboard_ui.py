"""Sprint Product Acceleration 01 — Product Dashboard UI Renderer & Assets.

Provides a unified, responsive, dark-mode research dashboard:
- 7 Integrated Modules: Overview, Research Results, Market Behavior, News & Events,
  Governance Center, Artifact Browser, Operations & System Status.
- Zero-dependency client-side tab switching & hash routing.
- Real-time bounded fetch integration with /api/v1/product/* endpoints.
- 100% offline-resilient: zero external CDN scripts or stylesheet links.
- Fully accessible and responsive (Desktop, Laptop, Tablet, Mobile).
"""

from __future__ import annotations


def render_product_dashboard_html() -> str:
    """Render the master CBE Product Dashboard HTML."""
    return """<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Coin Behavior Engine | Ürün & Araştırma Portalı</title>
  <meta name="description" content="Coin Behavior Engine piyasa davranışı, araştırma sonuçları, yönetişim ve kanıt arşivi.">
  <style>
    :root {
      --bg-dark: #090d16;
      --card-bg: #111827;
      --card-hover: #172033;
      --border: #1f2937;
      --border-focus: #3b82f6;
      --text: #f3f4f6;
      --text-muted: #9ca3af;
      --text-dim: #6b7280;
      --accent: #3b82f6;
      --accent-hover: #60a5fa;
      --green: #10b981;
      --green-bg: rgba(16, 185, 129, 0.12);
      --green-border: rgba(16, 185, 129, 0.3);
      --yellow: #f59e0b;
      --yellow-bg: rgba(245, 158, 11, 0.12);
      --yellow-border: rgba(245, 158, 11, 0.3);
      --red: #ef4444;
      --red-bg: rgba(239, 68, 68, 0.12);
      --red-border: rgba(239, 68, 68, 0.3);
      --blue-bg: rgba(59, 130, 246, 0.12);
      --blue-border: rgba(59, 130, 246, 0.3);
      --purple: #8b5cf6;
      --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      background: var(--bg-dark);
      color: var(--text);
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
      line-height: 1.5;
      padding: 0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
    }

    /* Header */
    .top-header {
      background: #0d1322;
      border-bottom: 1px solid var(--border);
      padding: 14px 24px;
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      position: sticky;
      top: 0;
      z-index: 100;
    }
    .brand-group {
      display: flex;
      align-items: center;
      gap: 12px;
    }
    .brand-logo {
      font-size: 20px;
      font-weight: 800;
      letter-spacing: -0.5px;
      display: flex;
      align-items: center;
      gap: 8px;
      color: #fff;
    }
    .brand-logo span { color: var(--accent); }
    .header-badges {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      gap: 5px;
      font-size: 11px;
      font-weight: 700;
      padding: 3px 8px;
      border-radius: 9999px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    .badge-frozen { background: #1e3a8a; color: #93c5fd; border: 1px solid #3b82f6; }
    .badge-success { background: var(--green-bg); color: #6ee7b7; border: 1px solid var(--green-border); }
    .badge-warn { background: var(--yellow-bg); color: #fde68a; border: 1px solid var(--yellow-border); }
    .badge-danger { background: var(--red-bg); color: #fca5a5; border: 1px solid var(--red-border); }
    .badge-info { background: var(--blue-bg); color: #bfdbfe; border: 1px solid var(--blue-border); }

    .btn {
      background: #1f2937;
      color: var(--text);
      border: 1px solid var(--border);
      padding: 6px 14px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
    }
    .btn:hover { background: #374151; color: #fff; border-color: var(--accent); }
    .btn-primary { background: var(--accent); color: #fff; border-color: var(--accent); }
    .btn-primary:hover { background: var(--accent-hover); }

    /* Navigation Tabs */
    .nav-tabs {
      background: #111827;
      border-bottom: 1px solid var(--border);
      padding: 0 24px;
      display: flex;
      gap: 4px;
      overflow-x: auto;
      white-space: nowrap;
    }
    .nav-tab {
      padding: 12px 16px;
      font-size: 13px;
      font-weight: 600;
      color: var(--text-muted);
      border-bottom: 2px solid transparent;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      text-decoration: none;
      transition: all 0.15s ease;
    }
    .nav-tab:hover { color: var(--text); }
    .nav-tab.active {
      color: #fff;
      border-bottom-color: var(--accent);
      background: rgba(59, 130, 246, 0.05);
    }

    /* Main Container */
    .container {
      max-width: 1380px;
      margin: 0 auto;
      padding: 24px;
      width: 100%;
      flex: 1;
    }

    /* Content Modules */
    .tab-content { display: none; }
    .tab-content.active { display: block; animation: fadeIn 0.2s ease; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

    /* Grids & Cards */
    .grid {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }
    .card {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      padding: 20px;
      position: relative;
    }
    .card h3 {
      font-size: 12px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.75px;
      margin-bottom: 8px;
    }
    .card .value {
      font-size: 24px;
      font-weight: 700;
      color: #fff;
    }
    .card .subtext {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 6px;
      line-height: 1.4;
    }

    /* Banner / Alerts */
    .alert-banner {
      background: var(--yellow-bg);
      border: 1px solid var(--yellow-border);
      border-radius: 8px;
      padding: 14px 18px;
      margin-bottom: 24px;
      font-size: 13px;
      color: #fde68a;
      line-height: 1.5;
    }
    .alert-banner.info {
      background: var(--blue-bg);
      border-color: var(--blue-border);
      color: #bfdbfe;
    }
    .alert-banner.danger {
      background: var(--red-bg);
      border-color: var(--red-border);
      color: #fca5a5;
    }

    /* Section Titles */
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin: 28px 0 16px 0;
      flex-wrap: wrap;
      gap: 12px;
    }
    .section-header:first-child { margin-top: 0; }
    .section-title {
      font-size: 18px;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    /* Tables */
    .table-container {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 10px;
      overflow-x: auto;
      margin-bottom: 24px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }
    th, td {
      padding: 12px 16px;
      text-align: left;
      border-bottom: 1px solid var(--border);
    }
    th {
      background: #0d1322;
      color: var(--text-muted);
      font-weight: 600;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.5px;
    }
    tr:hover td { background: rgba(255, 255, 255, 0.02); }
    code {
      font-family: var(--font-mono);
      background: #1f2937;
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 12px;
      color: #93c5fd;
    }

    /* Filter Controls */
    .filter-bar {
      display: flex;
      gap: 10px;
      margin-bottom: 16px;
      flex-wrap: wrap;
      align-items: center;
    }
    .search-input {
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: #fff;
      padding: 8px 14px;
      border-radius: 6px;
      font-size: 13px;
      min-width: 260px;
      outline: none;
    }
    .search-input:focus { border-color: var(--accent); }
    .pill-btn {
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 6px 12px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.15s ease;
    }
    .pill-btn:hover { background: #1f2937; color: #fff; }
    .pill-btn.active {
      background: #1e3a8a;
      color: #93c5fd;
      border-color: var(--accent);
    }

    /* Pagination */
    .pagination-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 12px 16px;
      font-size: 12px;
      color: var(--text-muted);
      border-top: 1px solid var(--border);
    }


    /* Chart and Explorer Controls */
    .chart-panel {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 20px;
      margin-bottom: 24px;
    }
    .chart-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 12px;
    }
    .chart-controls-group {
      display: flex;
      align-items: center;
      gap: 8px;
      flex-wrap: wrap;
    }
    .select-dropdown {
      background: #0d1322;
      border: 1px solid var(--border);
      color: #fff;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-family: var(--font-mono);
      outline: none;
      cursor: pointer;
    }
    .select-dropdown:focus { border-color: var(--accent); }
    .chart-hud {
      background: #080c14;
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 8px 14px;
      font-family: var(--font-mono);
      font-size: 12px;
      color: #cbd5e1;
      display: flex;
      gap: 14px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 12px;
      min-height: 38px;
    }
    .chart-hud span.val { color: #fff; font-weight: 600; }
    .chart-canvas-wrap {
      position: relative;
      width: 100%;
      height: 420px;
      background: #070b13;
      border: 1px solid var(--border);
      border-radius: 8px;
      overflow: hidden;
      cursor: crosshair;
    }
    .chart-canvas {
      display: block;
      width: 100%;
      height: 100%;
    }
    .chart-legend {
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
      margin-top: 12px;
      font-size: 11px;
      color: var(--text-muted);
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 5px;
    }
    .legend-color {
      width: 10px;
      height: 10px;
      border-radius: 2px;
    }
    .analog-grid {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 20px;
    }
    @media (max-width: 1024px) {
      .analog-grid { grid-template-columns: 1fr; }
    }
    .ret-pos { color: var(--green); font-weight: 600; }
    .ret-neg { color: var(--red); font-weight: 600; }

    /* Preview Modal */
    .modal-overlay {
      display: none;
      position: fixed;
      top: 0; left: 0; right: 0; bottom: 0;
      background: rgba(0, 0, 0, 0.75);
      z-index: 200;
      backdrop-filter: blur(2px);
      align-items: center;
      justify-content: center;
      padding: 24px;
    }
    .modal-overlay.active { display: flex; }
    .modal-window {
      background: #0e1526;
      border: 1px solid var(--border);
      border-radius: 12px;
      width: 100%;
      max-width: 900px;
      max-height: 85vh;
      display: flex;
      flex-direction: column;
      box-shadow: 0 20px 40px rgba(0,0,0,0.6);
    }
    .modal-header {
      padding: 16px 20px;
      border-bottom: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .modal-header h4 { font-size: 15px; color: #fff; font-family: var(--font-mono); }
    .modal-body {
      padding: 20px;
      overflow-y: auto;
      font-family: var(--font-mono);
      font-size: 12px;
      line-height: 1.6;
      color: #d1d5db;
      white-space: pre-wrap;
      word-break: break-word;
      background: #080c14;
    }
    .modal-footer {
      padding: 12px 20px;
      border-top: 1px solid var(--border);
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 12px;
      color: var(--text-muted);
    }

    /* Footer */
    .app-footer {
      background: #0d1322;
      border-top: 1px solid var(--border);
      padding: 16px 24px;
      font-size: 12px;
      color: var(--text-muted);
      display: flex;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 8px;
    }

    /* Responsive */
    @media (max-width: 768px) {
      .container { padding: 16px; }
      .grid { grid-template-columns: 1fr; }
      .top-header { padding: 12px 16px; }
      .nav-tabs { padding: 0 16px; }
      .search-input { min-width: 100%; }
    }
  </style>
</head>
<body>

  <!-- Top Global Header -->
  <header class="top-header" role="banner">
    <div class="brand-group">
      <div class="brand-logo">
        <span>⚡</span> Coin Behavior Engine
      </div>
      <span class="badge badge-frozen">CBE-0.7.0 FROZEN</span>
      <span class="badge badge-danger">TECHNICAL NO-GO</span>
    </div>
    <div class="header-badges">
      <span class="badge badge-warn">YÖNETİŞİM: ONAYLANMADI</span>
      <span class="badge badge-info">ÇEVRİMDIŞI ARAŞTIRMA MODU</span>
      <span class="badge badge-danger">CANLI İŞLEM: YASAK</span>
      <button class="btn" id="btn-refresh" onclick="refreshCurrentTab()">
        <span>↻</span> Şimdi Güncelle
      </button>
    </div>
  </header>

  <!-- Top Navigation Tabs (7 Core Modules) -->
  <nav class="nav-tabs" role="navigation" aria-label="Ürün Modülleri">
    <a href="#overview" class="nav-tab active" id="tab-btn-overview" onclick="switchTab('overview')">
      <span>📊</span> Genel Bakış
    </a>
    <a href="#research" class="nav-tab" id="tab-btn-research" onclick="switchTab('research')">
      <span>🔬</span> Araştırma Bulguları
    </a>
    <a href="#behavior" class="nav-tab" id="tab-btn-behavior" onclick="switchTab('behavior')">
      <span>📈</span> Piyasa Davranışı
    </a>
    <a href="#events" class="nav-tab" id="tab-btn-events" onclick="switchTab('events')">
      <span>📰</span> Olay & Makro Araştırması
    </a>
    <a href="#governance" class="nav-tab" id="tab-btn-governance" onclick="switchTab('governance')">
      <span>🔐</span> Yönetişim & Güvenlik
    </a>
    <a href="#artifacts" class="nav-tab" id="tab-btn-artifacts" onclick="switchTab('artifacts')">
      <span>📁</span> Kanıt Arşivi (540+)
    </a>
    <a href="#operations" class="nav-tab" id="tab-btn-operations" onclick="switchTab('operations')">
      <span>⚙️</span> Sistem & Operasyon
    </a>
  </nav>

  <!-- Main Work Area -->
  <main class="container" role="main">

    <!-- =================================================================== -->
    <!-- MODULE 1: OVERVIEW                                                  -->
    <!-- =================================================================== -->
    <section id="module-overview" class="tab-content active">
      <div class="alert-banner">
        <strong>⚠️ GÜVENLİK SÖZLEŞMESİ & TEKNİK KISITLAMALAR:</strong><br>
        Sistem kesin olarak <code>OFFLINE_RESEARCH_AND_PRODUCT_DEVELOPMENT</code> modunda çalışmaktadır.
        Gerçek borsa ağ erişimi, canlı BTCUSDT gözlemi ve otonom piyasa izleme <strong>DEVRE DIŞIDIR</strong>.
        Canlı emir iletimi politik ve teknik olarak <strong>KALICI OLARAK YASAKLANMIŞTIR</strong>.
        Geçmiş ve sentetik veriler kesinlikle canlı veri olarak nitelendirilmez.
      </div>

      <div class="grid">
        <div class="card">
          <h3>Model Bütünlüğü & Dondurma</h3>
          <div class="value">CBE-0.7.0</div>
          <div class="subtext">
            Kanonik Dosyalar: <b style="color:#6ee7b7">29 / 29 Doğrulandı</b><br>
            İhlal / Drift: <b>0</b> | Lockbox: <b>Aktif</b><br>
            SHA-256: <code>c3e5dfbe3bf637f9...</code>
          </div>
        </div>

        <div class="card">
          <h3>Test Paketi & Yeterlilik</h3>
          <div class="value" style="color: #6ee7b7;">2,102 / 2,107</div>
          <div class="subtext">
            Geçiş Oranı: <b>%99.76</b> | Sprint 11.23: <b>422/422 (%100)</b><br>
            Fonlama Gecikmesi: <b style="color:#6ee7b7">21.38 ms</b> (&lt; 50.0 ms sınır)<br>
            Kalan 5 Hata: WSL2 VHDX disk fsync senkronizasyon sınırları
          </div>
        </div>

        <div class="card">
          <h3>Son Araştırma Aşaması</h3>
          <div class="value" style="font-size: 18px; color: #93c5fd;">Sprint 11.23.5B-6.5.5C</div>
          <div class="subtext">
            Başlık: <b>Offline Regression Closure & Durability Forensics</b><br>
            Hesaplama / Disk Oranı: <b>0.41 ms (%1.1) / 36.19 ms (%98.9)</b><br>
            Taahhüt: <code>2e7ad236ba07f71...</code>
          </div>
        </div>

        <div class="card">
          <h3>Veri Seti & Kanıt Varlıkları</h3>
          <div class="value" id="overview-artifact-count">540+ Dosya</div>
          <div class="subtext">
            Binance Spot Zaman Dilimleri: <b>1m, 5m, 15m, 1h, 4h, 1d</b><br>
            Doğrulanmış Makro Olaylar: <b>40 Adet</b> (SEC, Fed, Hazine)<br>
            BLS CPI Adayı: <b style="color:#fde68a">Doğrulanmadı (Ağ Kapalı)</b>
          </div>
        </div>
      </div>

      <div class="section-header">
        <div class="section-title"><span>🛡️</span> Veri Kökeni ve Ayrım Prensipleri</div>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Veri Sınıfı</th>
              <th>Kaynak ve Doğrulama Durumu</th>
              <th>Kullanım Amacı</th>
              <th>Yetkilendirme Kısıtı</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Geçmiş Gözlemler</strong></td>
              <td>Binance Spot multi-year arşivleri (2022-2026 Parquet)</td>
              <td>Çevrimdışı rejim, volatilite ve korelasyon araştırması</td>
              <td><span class="badge badge-warn">ARAŞTIRMA KONTAMİNASYONLU</span></td>
            </tr>
            <tr>
              <td><strong>Sentetik Test Verisi</strong></td>
              <td>İzole edilmiş deterministic mock veri yükleri</td>
              <td>Yazılım regresyon ve stres testleri</td>
              <td><span class="badge badge-info">SENTETİK</span></td>
            </tr>
            <tr>
              <td><strong>Çevrimdışı Araştırma</strong></td>
              <td><code>research_outputs/</code> (540 dosya)</td>
              <td>İstatistiki ve ekonomik hipotez doğrulama</td>
              <td><span class="badge badge-success">KANIT ARŞİVİNDE</span></td>
            </tr>
            <tr>
              <td><strong>Canlı Piyasa Akışı</strong></td>
              <td>Gerçek borsa API / WebSocket akışı</td>
              <td>Operasyonel gözlem</td>
              <td><span class="badge badge-danger">YETKİLENDİRİLMEDİ</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- MODULE 2: RESEARCH RESULTS                                          -->
    <!-- =================================================================== -->
    <section id="module-research" class="tab-content">
      <div class="section-header">
        <div class="section-title"><span>🔬</span> Kanonik Araştırma Bulguları & Hipotez Değerlendirmeleri</div>
      </div>

      <div class="filter-bar">
        <input type="text" id="research-search" class="search-input" placeholder="Bulgularda veya başlıklarda ara..." oninput="filterResearch()">
        <button class="pill-btn active" onclick="setResearchCat('all', this)">Tümü</button>
        <button class="pill-btn" onclick="setResearchCat('derivatives', this)">Türev & Fonlama</button>
        <button class="pill-btn" onclick="setResearchCat('market structure', this)">Piyasa Yapısı</button>
        <button class="pill-btn" onclick="setResearchCat('pattern recognition', this)">Analog Gezgin</button>
        <button class="pill-btn" onclick="setResearchCat('macro', this)">Makro & Olaylar</button>
        <button class="pill-btn" onclick="setResearchCat('durability', this)">Kalıcılık & Disk</button>
        <button class="pill-btn" onclick="setResearchCat('security', this)">Kripto & Güvenlik</button>
      </div>

      <div id="research-cards-container" class="grid" style="grid-template-columns: 1fr;">
        <!-- Injected via client.js -->
        <div class="card" style="text-align: center; color: var(--text-muted); padding: 40px;">Araştırma sonuçları yükleniyor...</div>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- MODULE 3: MARKET BEHAVIOR & HISTORICAL EXPLORER                     -->
    <!-- =================================================================== -->
    <section id="module-behavior" class="tab-content">
      <div class="alert-banner info">
        <strong>ℹ️ MODEL REJİMİ GÜVENLİK KALKANI:</strong><br>
        Dondurulmuş modelin (CBE-0.7.0) persentil hesaplama algoritmasındaki mantık hatası (<code>x &lt;= x</code> eşitlik durumu)
        nedeniyle ham <code>DELEVERAGING_STRESS</code> çıktısı fail-closed korumasıyla <strong>UNKNOWN</strong> durumuna çekilmiştir.
        Aşağıdaki tüm grafik ve veriler geçmiş doğrulanmış çok yıllık spot veri setleri (2022-2026 Parquet) ve kanonik rejim çizelgesi üzerinden hesaplanmaktadır.
      </div>

      <!-- SECTION 1: HISTORICAL CANDLESTICK & REGIME CHART -->
      <div class="section-header">
        <div class="section-title"><span>📈</span> Tarihsel Fiyat & Piyasa Rejimi Gezgini (BTCUSDT Multi-Year)</div>
      </div>

      <div class="chart-panel">
        <div class="chart-toolbar">
          <div class="chart-controls-group">
            <span style="font-size: 12px; color: var(--text-muted); font-weight: 600;">Aralık:</span>
            <button class="pill-btn" onclick="setCandleInterval('5m', this)">5m</button>
            <button class="pill-btn" onclick="setCandleInterval('15m', this)">15m</button>
            <button class="pill-btn active" onclick="setCandleInterval('1h', this)">1h</button>
            <button class="pill-btn" onclick="setCandleInterval('4h', this)">4h</button>
            <button class="pill-btn" onclick="setCandleInterval('1d', this)">1d</button>
          </div>
          <div class="chart-controls-group">
            <span style="font-size: 12px; color: var(--text-muted); font-weight: 600;">Dönem / Ay:</span>
            <select id="candle-month-select" class="select-dropdown" onchange="changeCandleMonth(this.value)">
              <option value="2026-09">2026-09 (Eylül 2026)</option>
            </select>
            <span style="font-size: 12px; color: var(--text-muted); font-weight: 600; margin-left: 6px;">Bar Sayısı:</span>
            <select id="candle-limit-select" class="select-dropdown" onchange="changeCandleLimit(this.value)">
              <option value="50">50 Bar</option>
              <option value="100" selected>100 Bar</option>
              <option value="200">200 Bar</option>
              <option value="500">500 Bar</option>
            </select>
            <div style="display: flex; gap: 4px; margin-left: 6px;">
              <button class="btn" style="padding: 4px 10px; font-size: 11px;" onclick="panCandles(-25)" title="Önceki Barlar">◀ Önceki</button>
              <button class="btn" style="padding: 4px 10px; font-size: 11px;" onclick="panCandles(25)" title="Sonraki Barlar">Sonraki ▶</button>
            </div>
          </div>
        </div>

        <div class="chart-hud" id="candle-hud">
          <div><span style="color:var(--text-muted);">Zaman:</span> <span class="val" id="hud-time">-</span></div>
          <div><span style="color:var(--text-muted);">A:</span> <span class="val" id="hud-open">-</span></div>
          <div><span style="color:var(--text-muted);">Y:</span> <span class="val" id="hud-high">-</span></div>
          <div><span style="color:var(--text-muted);">D:</span> <span class="val" id="hud-low">-</span></div>
          <div><span style="color:var(--text-muted);">K:</span> <span class="val" id="hud-close">-</span></div>
          <div><span style="color:var(--text-muted);">Hacim:</span> <span class="val" id="hud-volume">-</span></div>
          <div><span style="color:var(--text-muted);">Rejim:</span> <span id="hud-regime" class="badge badge-info">-</span></div>
        </div>

        <div class="chart-canvas-wrap" id="candle-canvas-container">
          <canvas id="candlestick-canvas" class="chart-canvas"></canvas>
        </div>

        <div class="chart-legend">
          <span style="font-weight: 600; color: #fff;">Piyasa Rejimi Renk Kodları:</span>
          <div class="legend-item"><span class="legend-color" style="background: #64748b;"></span> <span>SIDEWAYS (Yatay)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #f59e0b;"></span> <span>UNCERTAIN (Belirsiz)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #10b981;"></span> <span>TRENDING_BULL (Boğa Trendi)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #8b5cf6;"></span> <span>HIGH_VOLATILITY (Yüksek Volatilite)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #ef4444;"></span> <span>TRENDING_BEAR (Ayı Trendi)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #f97316;"></span> <span>POSSIBLE_REVERSAL (Olası Dönüş)</span></div>
        </div>
      </div>

      <!-- SECTION 2: HISTORICAL ANALOG SIMILARITY EXPLORER -->
      <div class="section-header">
        <div class="section-title"><span>🧬</span> Tarihsel Analog Benzerlik Gezgini & Yörünge Dağılımı</div>
      </div>

      <div class="alert-banner warn" style="margin-bottom: 16px;">
        <strong>⚠️ ARAŞTIRMA DEĞERLENDİRMESİ — STATISTICALLY_INTERESTING_BUT_NOT_ECONOMIC:</strong><br>
        Geçmiş piyasa fraktallarının ve analog benzerlik skorlarının gelecekteki fiyat hareketlerini öngörmede ekonomik bir üstünlük (alfa) sağlamadığı kanıtlanmıştır.
        Yörüngeler 15m, 1h, 4h ve 24h vadelerde hızla dağılmakta; taker komisyonu, fonlama ve alış-satış spreadi net kar beklentisini sıfırlamaktadır.
      </div>

      <div class="chart-panel">
        <div class="chart-toolbar">
          <div class="chart-controls-group" style="width: 100%;">
            <span style="font-size: 12px; color: var(--text-muted); font-weight: 600;">Referans Karar Noktası:</span>
            <select id="analog-pattern-select" class="select-dropdown" style="flex: 1; max-width: 560px;" onchange="selectAnalogPattern(this.value)">
              <option value="">Yükleniyor...</option>
            </select>
          </div>
        </div>

        <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); margin-bottom: 18px;" id="analog-stats-grid">
          <div class="card" style="padding: 14px;">
            <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Ortalama 24h Getiri</div>
            <div class="value" id="analog-stat-mean" style="font-size: 20px;">-%</div>
          </div>
          <div class="card" style="padding: 14px;">
            <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Medyan 24h Getiri</div>
            <div class="value" id="analog-stat-median" style="font-size: 20px;">-%</div>
          </div>
          <div class="card" style="padding: 14px;">
            <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">24h Dağılım Genişliği (Max-Min)</div>
            <div class="value" id="analog-stat-range" style="font-size: 20px;">-%</div>
          </div>
          <div class="card" style="padding: 14px;">
            <div style="font-size: 11px; color: var(--text-muted); text-transform: uppercase;">Ekonomik Alfa Tespiti</div>
            <div class="value" style="font-size: 16px; color: var(--red);">YOK (SIFIR)</div>
          </div>
        </div>

        <div class="analog-grid">
          <div>
            <div style="font-size: 13px; font-weight: 700; color: #fff; margin-bottom: 10px;">
              En Yakın 5 Tarihsel Eşleşme (KNN Benzerlik)
            </div>
            <div class="table-container" style="max-height: 380px; overflow-y: auto;">
              <table>
                <thead>
                  <tr>
                    <th>Sıra</th>
                    <th>Analog Tarihi (UTC)</th>
                    <th>Skor</th>
                    <th>15m</th>
                    <th>1h</th>
                    <th>4h</th>
                    <th>24h</th>
                    <th>MFE / MAE</th>
                  </tr>
                </thead>
                <tbody id="analog-table-body">
                  <tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:20px;">Yükleniyor...</td></tr>
                </tbody>
              </table>
            </div>
          </div>

          <div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
              <div style="font-size: 13px; font-weight: 700; color: #fff;">
                İleriye Dönük Normalize Yörünge Dağılımı (%)
              </div>
              <div style="font-size: 11px; font-family: var(--font-mono); color: var(--text-muted);">
                0m → 15m → 1h → 4h → 24h
              </div>
            </div>
            <div class="chart-canvas-wrap" id="analog-canvas-container" style="height: 340px;">
              <canvas id="analog-canvas" class="chart-canvas"></canvas>
            </div>
          </div>
        </div>
      </div>

      <!-- SECTION 3: REGIME DISTRIBUTION & TRANSITIONS (PRESERVED) -->
      <div class="section-header">
        <div class="section-title"><span>📊</span> Tarihsel Piyasa Rejimi Dağılımı (BTCUSDT 2022-2026)</div>
      </div>
      <div class="grid" id="regime-grid">
        <!-- Injected via client.js -->
      </div>

      <div class="section-header">
        <div class="section-title"><span>🔄</span> Rejimler Arası Geçiş Olasılıkları Matrisi</div>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Mevcut Rejim</th>
              <th>COMPRESSION (Sıkışma)</th>
              <th>NORMAL (Denge)</th>
              <th>EXPANSION WATCH (Genişleme)</th>
              <th>HIGH VOLATILITY (Yüksek Volatilite)</th>
            </tr>
          </thead>
          <tbody id="regime-transitions-tbody">
            <!-- Injected via client.js -->
          </tbody>
        </table>
      </div>

      <div class="grid" style="grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));">
        <div class="card">
          <h3>5 Dakikalık Getiri Volatilitesi Kuantilleri</h3>
          <div class="subtext" style="font-size: 13px; line-height: 1.8; margin-top: 10px;">
            Q10 (Alt Kuyruk): <code>-0.34%</code><br>
            Q25 (Birinci Çeyrek): <code>-0.11%</code><br>
            Medyan (Q50): <code>0.00%</code><br>
            Q75 (Üçüncü Çeyrek): <code>+0.12%</code><br>
            Q90 (Üst Kuyruk): <code>+0.36%</code><br>
            Ortalama Mutlak Getiri (|r|): <code>0.18% / 5m</code>
          </div>
        </div>

        <div class="card">
          <h3>Perpetual Fonlama Oranı Karakteristikleri</h3>
          <div class="subtext" style="font-size: 13px; line-height: 1.8; margin-top: 10px;">
            Ortalama 8h Fonlama: <code>+0.0108%</code> (Yıllık ~%11.82)<br>
            Medyan 8h Fonlama: <code>+0.0100%</code><br>
            Negatif Fonlama Dönemi Oranı: <code>%14.6</code><br>
            Kalıcılık Yarılanma Ömrü: <code>2.4 Periyot (19.2 saat)</code><br>
            Ticari Değerlendirme: <b>İşlem komisyonları net carry getirisini sıfırlar.</b>
          </div>
        </div>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- MODULE 4: NEWS & EVENT RESEARCH                                     -->
    <!-- =================================================================== -->
    <section id="module-events" class="tab-content">
      <!-- Special BLS CPI Candidate Callout -->
      <div class="card" style="border-left: 4px solid var(--yellow); margin-bottom: 24px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px;">
          <div>
            <h3 style="color: var(--yellow);">⚠️ RESMİ BLS CPI TAKVİM ADAYI (DOĞRULANMAMIŞ)</h3>
            <div style="font-size: 16px; font-weight: 700; color: #fff; margin-top: 4px;">
              Talep ID: <code>REQ-BLS-CPI-2026M10-ACQ01</code> | Olay: <code>EVT-BLS-CPI-2026M10-20261110</code>
            </div>
          </div>
          <span class="badge badge-warn">ADAY — DOĞRULANMADI</span>
        </div>
        <div class="subtext" style="margin-top: 10px; font-size: 13px;">
          Yayıncı: <b>U.S. Bureau of Labor Statistics (BLS)</b> | Hedef URL: <code>https://www.bls.gov/schedule/news_release/cpi.htm</code><br>
          Operatör Yetkilendirmesi: <b style="color: var(--red);">NOT_GRANTED (Verilmedi)</b> | Gerçek Ağ İletişimi: <b style="color: var(--red);">DISABLED (Kapalı)</b><br>
          Açıklama: Resmi BLS API veya web sayfalarına ağ erişimi yapılmamıştır. Veri karantinada tutulmakta olup kesinlikle canlı modele beslenmez.
        </div>
      </div>

      <div class="section-header">
        <div class="section-title"><span>📰</span> Doğrulanmış Düzenleyici ve Makro Ekonomik Olaylar (N=40)</div>
      </div>

      <div class="filter-bar">
        <input type="text" id="events-search" class="search-input" placeholder="Olay başlığı, aktör veya ID ile ara..." oninput="filterEvents()">
        <button class="pill-btn active" onclick="setEventCat('ALL', this)">Tümü</button>
        <button class="pill-btn" onclick="setEventCat('REGULATION', this)">Düzenleyici (SEC)</button>
        <button class="pill-btn" onclick="setEventCat('MONETARY_POLICY', this)">Para Politikası (Fed)</button>
        <button class="pill-btn" onclick="setEventCat('MACRO', this)">Makro Göstergeler</button>
      </div>

      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Olay ID</th>
              <th>Kategori</th>
              <th>Yayın Tarihi (UTC)</th>
              <th>Kaynak & Güvenilirlik</th>
              <th>Başlık & Factual Claim</th>
              <th>Yön Hipotezi</th>
              <th>Şiddet</th>
            </tr>
          </thead>
          <tbody id="events-tbody">
            <!-- Injected via client.js -->
          </tbody>
        </table>
        <div class="pagination-bar">
          <span id="events-page-info">Sayfa 1 / 1</span>
          <div style="display: flex; gap: 8px;">
            <button class="btn" id="btn-events-prev" onclick="changeEventsPage(-1)">Önceki</button>
            <button class="btn" id="btn-events-next" onclick="changeEventsPage(1)">Sonraki</button>
          </div>
        </div>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- MODULE 5: GOVERNANCE & SECURITY                                     -->
    <!-- =================================================================== -->
    <section id="module-governance" class="tab-content">
      <div class="grid">
        <div class="card">
          <h3>Teknik Karar</h3>
          <div class="value" style="color: var(--red);">TECHNICAL NO-GO</div>
          <div class="subtext">Canlı üretime geçiş teknik olarak onaylanmamıştır.</div>
        </div>

        <div class="card">
          <h3>Yönetişim Yetkisi</h3>
          <div class="value" style="color: var(--yellow);">NOT_GRANTED</div>
          <div class="subtext">Operatör yetki tokeni oluşturulmamış ve yayınlanmamıştır.</div>
        </div>

        <div class="card">
          <h3>Kriptografik Motor</h3>
          <div class="value" style="font-size: 16px; color: #6ee7b7;">Ed25519 (PyCA / OpenSSL)</div>
          <div class="subtext">
            RFC 8032 Uyumluluğu: <b>Tam Doğrulandı</b><br>
            Saf-Python Yedek Kripto: <b style="color: #6ee7b7;">Kalıcı Olarak Kaldırıldı</b>
          </div>
        </div>

        <div class="card">
          <h3>Tekrar Oynatma Koruması</h3>
          <div class="value" style="font-size: 16px; color: #6ee7b7;">SQLite Nonce Tablosu</div>
          <div class="subtext">TTL zaman aşımı ve request digest doğrulaması aktif.</div>
        </div>
      </div>

      <div class="section-header">
        <div class="section-title"><span>👥</span> Kayıtlı Operatör Kimlikleri & Rolleri</div>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Operatör ID</th>
              <th>Rol Tanımı</th>
              <th>Anahtar Tipi</th>
              <th>Durum</th>
              <th>Yetki Sınırı</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>OP-RESEARCH-LEAD-01</code></td>
              <td>RESEARCH_LEAD</td>
              <td>Ed25519 (RFC 8032)</td>
              <td><span class="badge badge-success">AKTİF</span></td>
              <td>Salt-Okunur Araştırma & Takvim Talebi</td>
            </tr>
            <tr>
              <td><code>OP-SECURITY-AUDITOR-01</code></td>
              <td>SECURITY_AUDITOR</td>
              <td>Ed25519 (RFC 8032)</td>
              <td><span class="badge badge-success">AKTİF</span></td>
              <td>Güvenlik Denetimi & Token İptal</td>
            </tr>
            <tr>
              <td><code>OP-GOVERNANCE-ADMIN-01</code></td>
              <td>GOVERNANCE_ADMIN</td>
              <td>Ed25519 (RFC 8032)</td>
              <td><span class="badge badge-success">AKTİF</span></td>
              <td>Yönetişim Onayı (Şu an kapalı)</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="section-header">
        <div class="section-title"><span>🚫</span> Kalıcı Olarak Engellenen Borsa Emir Uç Noktaları</div>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Yasaklı URL / Endpoint</th>
              <th>Kısıtlama Derecesi</th>
              <th>Açıklama</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>/api/v3/order</code> & <code>/api/v3/order/test</code></td>
              <td><span class="badge badge-danger">KALICI YASAK</span></td>
              <td>Binance Spot alım/satım emir oluşturma</td>
            </tr>
            <tr>
              <td><code>/fapi/v1/order</code> & <code>/fapi/v2/order</code></td>
              <td><span class="badge badge-danger">KALICI YASAK</span></td>
              <td>Binance USD-M Vadeli İşlem emir oluşturma</td>
            </tr>
            <tr>
              <td><code>/dapi/v1/order</code></td>
              <td><span class="badge badge-danger">KALICI YASAK</span></td>
              <td>Binance COIN-M Vadeli İşlem emir oluşturma</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- MODULE 6: ARTIFACT BROWSER                                          -->
    <!-- =================================================================== -->
    <section id="module-artifacts" class="tab-content">
      <div class="section-header">
        <div class="section-title"><span>📁</span> Araştırma Kanıtı ve Rapor Arşivi (540+ Dosya)</div>
      </div>

      <div class="filter-bar">
        <input type="text" id="artifacts-search" class="search-input" placeholder="Dosya adı, sprint veya kategori ile ara..." oninput="filterArtifacts()">
        <button class="pill-btn active" onclick="setArtifactExt('all', this)">Tüm Formatlar</button>
        <button class="pill-btn" onclick="setArtifactExt('.json', this)">JSON</button>
        <button class="pill-btn" onclick="setArtifactExt('.md', this)">Markdown</button>
        <button class="pill-btn" onclick="setArtifactExt('.csv', this)">CSV</button>
        <button class="pill-btn" onclick="setArtifactExt('.xml', this)">XML</button>
      </div>

      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Dosya Adı</th>
              <th>Kategori</th>
              <th>Format</th>
              <th>Boyut</th>
              <th>Son Değişiklik (UTC)</th>
              <th>İşlem</th>
            </tr>
          </thead>
          <tbody id="artifacts-tbody">
            <!-- Injected via client.js -->
          </tbody>
        </table>
        <div class="pagination-bar">
          <span id="artifacts-page-info">Sayfa 1 / 1 (0 Dosya)</span>
          <div style="display: flex; gap: 8px;">
            <button class="btn" id="btn-artifacts-prev" onclick="changeArtifactsPage(-1)">Önceki</button>
            <button class="btn" id="btn-artifacts-next" onclick="changeArtifactsPage(1)">Sonraki</button>
          </div>
        </div>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- MODULE 7: OPERATIONS & SYSTEM STATUS                                -->
    <!-- =================================================================== -->
    <section id="module-operations" class="tab-content">
      <div class="grid">
        <div class="card">
          <h3>Uygulama Sürümü</h3>
          <div class="value">CBE-0.7.0</div>
          <div class="subtext">
            Git Taahhüdü: <code>2e7ad236ba07f71...</code><br>
            Dal: <code>main</code> | Python: <b>3.11</b>
          </div>
        </div>

        <div class="card">
          <h3>Dağıtım & Altyapı</h3>
          <div class="value" style="font-size: 16px; color: #93c5fd;">Coolify Linux VPS</div>
          <div class="subtext">
            Alan Adı: <code>coin.ozelweb.com.tr</code><br>
            Staging Servisi: <code>cbe-market-intelligence-staging</code><br>
            Üretim Servisi: <code>coin-behavior-engine</code>
          </div>
        </div>

        <div class="card">
          <h3>Arka Plan Görevi</h3>
          <div class="value" style="font-size: 18px; color: var(--yellow);">DURDURULDU</div>
          <div class="subtext">
            ProspectiveWorker: <b>Okuma-modu güvenlik kilidi aktif</b><br>
            Otonom piyasa izleme kapalıdır.
          </div>
        </div>

        <div class="card">
          <h3>Kalıcı Depolama Durumu</h3>
          <div class="value" id="ops-storage-mb">0 MB</div>
          <div class="subtext">
            Araştırma Çıktıları: <code>research_outputs/</code><br>
            İndekslenen Kanıt Dosyası: <b id="ops-artifacts-count">540</b>
          </div>
        </div>
      </div>

      <div class="section-header">
        <div class="section-title"><span>📋</span> Ortam ve Donanım Yeterlilik Bilgisi</div>
      </div>
      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Bileşen</th>
              <th>Mevcut Durum</th>
              <th>Teknik Açıklama</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Kalıcılık Birimi (ext4)</strong></td>
              <td><span class="badge badge-success">DOĞRULANDI</span></td>
              <td><code>cbe-655b-durability-volume</code> atomik dosya adı değiştirme ve <code>os.fsync</code> tam uyumlu.</td>
            </tr>
            <tr>
              <td><strong>WSL2 VHDX Disk Gecikmesi</strong></td>
              <td><span class="badge badge-warn">AÇIKLANMIŞ KISIT</span></td>
              <td>30.000 sıralı fsync çağrısı sanal SCSI sürücüsünde ~36 ms sürer; 5 dakikalık üretim döngüsünü etkilemez.</td>
            </tr>
            <tr>
              <td><strong>Fonlama Hesaplama Motoru</strong></td>
              <td><span class="badge badge-success">BAŞARILI</span></td>
              <td>Medyan saf hesaplama gecikmesi 21.38 ms (&lt; 50.0 ms sınır).</td>
            </tr>
            <tr>
              <td><strong>Borsa Ağ İzolasyonu</strong></td>
              <td><span class="badge badge-success">TAM İZOLASYON</span></td>
              <td><code>--network none</code> veya kapalı çıkış kuralları ile sıfır harici ağ çağrısı.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

  </main>

  <!-- Safe Artifact Preview Modal -->
  <div id="preview-modal" class="modal-overlay" onclick="closeModalOnOverlay(event)">
    <div class="modal-window" onclick="event.stopPropagation()">
      <div class="modal-header">
        <h4 id="modal-title">Dosya Önizleme</h4>
        <button class="btn" onclick="closeModal()">✕ Kapat</button>
      </div>
      <div class="modal-body" id="modal-content">Yükleniyor...</div>
      <div class="modal-footer">
        <span id="modal-meta">Boyut: 0 KB</span>
        <button class="btn btn-primary" onclick="closeModal()">Tamam</button>
      </div>
    </div>
  </div>

  <!-- App Footer -->
  <footer class="app-footer" role="contentinfo">
    <div>
      <strong>CBE-0.7.0 Dondurulmuş Model</strong> | Git: <code>2e7ad236ba07f71...</code> | Canlı Alım-Satım Kesinlikle Yasaktır.
    </div>
    <div>
      Coin Behavior Engine &copy; 2026 | Salt-Okunur Ürün & Araştırma Portalı
    </div>
  </footer>

  <!-- Master Client Script -->
  <script>
    "use strict";

    let currentTab = "overview";
    let researchData = [];
    let eventsData = [];
    let eventsPage = 1;
    let eventsLimit = 15;
    let artifactsData = [];
    let artifactsPage = 1;
    let artifactsLimit = 25;

    let selectedResearchCat = "all";
    let selectedEventCat = "ALL";
    let selectedArtifactExt = "all";

    // Tab Navigation
    function switchTab(tabId) {
      currentTab = tabId;
      document.querySelectorAll(".nav-tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll(".tab-content").forEach(c => c.classList.remove("active"));

      const tabBtn = document.getElementById("tab-btn-" + tabId);
      if (tabBtn) tabBtn.classList.add("active");

      const mod = document.getElementById("module-" + tabId);
      if (mod) mod.classList.add("active");

      window.location.hash = tabId;

      // Lazy load tab data
      if (tabId === "research" && researchData.length === 0) loadResearch();
      if (tabId === "behavior") loadBehavior();
      if (tabId === "events" && eventsData.length === 0) loadEvents();
      if (tabId === "governance") loadGovernance();
      if (tabId === "artifacts" && artifactsData.length === 0) loadArtifacts();
      if (tabId === "operations") loadOperations();
    }

    function refreshCurrentTab() {
      if (currentTab === "overview") loadOverview();
      else if (currentTab === "research") loadResearch();
      else if (currentTab === "behavior") loadBehavior();
      else if (currentTab === "events") loadEvents();
      else if (currentTab === "governance") loadGovernance();
      else if (currentTab === "artifacts") loadArtifacts();
      else if (currentTab === "operations") loadOperations();
    }

    // Module 1: Overview
    async function loadOverview() {
      try {
        const res = await fetch("/api/v1/product/overview");
        if (!res.ok) return;
        const data = await res.json();
        if (data.datasets) {
          const el = document.getElementById("overview-artifact-count");
          if (el) el.innerText = data.datasets.research_artifacts_count + "+ Dosya";
        }
      } catch (e) {
        console.warn("Overview fetch error:", e);
      }
    }

    // Module 2: Research Results
    async function loadResearch() {
      try {
        const res = await fetch("/api/v1/product/research-results");
        if (!res.ok) return;
        const data = await res.json();
        researchData = data.results || [];
        renderResearch();
      } catch (e) {
        console.warn("Research fetch error:", e);
      }
    }

    function setResearchCat(cat, btn) {
      selectedResearchCat = cat;
      document.querySelectorAll("#module-research .pill-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      renderResearch();
    }

    function filterResearch() {
      renderResearch();
    }

    function renderResearch() {
      const container = document.getElementById("research-cards-container");
      if (!container) return;

      const q = (document.getElementById("research-search")?.value || "").toLowerCase();
      let list = researchData;

      if (selectedResearchCat !== "all") {
        list = list.filter(r => r.category.toLowerCase().includes(selectedResearchCat));
      }
      if (q) {
        list = list.filter(r =>
          r.title.toLowerCase().includes(q) ||
          r.statistical_findings.toLowerCase().includes(q) ||
          r.id.toLowerCase().includes(q)
        );
      }

      if (list.length === 0) {
        container.innerHTML = '<div class="card" style="text-align: center; color: var(--text-muted); padding: 40px;">Kriterlere uygun araştırma bulgusu bulunamadı.</div>';
        return;
      }

      container.innerHTML = list.map(r => `
        <div class="card" style="border-left: 4px solid var(--accent);">
          <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 8px;">
            <div>
              <span style="font-size: 11px; font-weight: 700; color: var(--accent);">${r.id} &bull; ${r.sprint}</span>
              <h3 style="font-size: 16px; color: #fff; text-transform: none; margin: 4px 0;">${r.title}</h3>
            </div>
            <span class="badge ${r.classification_badge || 'badge-info'}">${r.classification}</span>
          </div>
          <div style="font-size: 12px; color: var(--text-muted); margin: 6px 0;">
            Veri Seti: <code>${r.dataset_id}</code> | Örneklem: <b>${r.sample_size}</b> | Rejim: <b>${r.market_regime}</b>
          </div>
          <div style="margin-top: 10px; font-size: 13px; line-height: 1.6;">
            <p><strong>İstatistiki Bulgular:</strong> ${r.statistical_findings}</p>
            <p style="margin-top: 6px;"><strong>Ekonomik Geçerlilik:</strong> ${r.economic_validity}</p>
            <p style="margin-top: 6px; color: #fde68a;"><strong>Güven / Belirsizlik:</strong> ${r.confidence_uncertainty}</p>
          </div>
          <div style="margin-top: 10px; font-size: 11px; color: var(--text-dim); border-top: 1px solid var(--border); padding-top: 8px;">
            Sınırlamalar: ${r.limitations.join(" &bull; ")}
          </div>
        </div>
      `).join("");
    }

    // Module 3: Market Behavior & Explorers
    let candleInterval = '1h';
    let candleMonth = '2026-09';
    let candleLimit = 100;
    let candleOffset = 0;
    let candlesData = [];
    let candleMonthsList = [];
    let currentAnalogData = null;
    let crosshairPos = null;

    async function loadBehavior() {
      // 1. Load Summary & Transitions
      try {
        const res = await fetch("/api/v1/product/market-behavior");
        if (res.ok) {
          const data = await res.json();
          const rGrid = document.getElementById("regime-grid");
          if (rGrid && data.regime_distribution) {
            rGrid.innerHTML = data.regime_distribution.map(r => `
              <div class="card">
                <h3>${r.regime}</h3>
                <div class="value">${r.frequency_percent}%</div>
                <div class="subtext">${r.description}</div>
              </div>
            `).join("");
          }

          const tBody = document.getElementById("regime-transitions-tbody");
          if (tBody && data.regime_transitions) {
            tBody.innerHTML = Object.entries(data.regime_transitions).map(([curr, targets]) => `
              <tr>
                <td><strong>${curr}</strong></td>
                <td>%${(targets.COMPRESSION * 100).toFixed(1)}</td>
                <td>%${(targets.NORMAL * 100).toFixed(1)}</td>
                <td>%${(targets.EXPANSION_WATCH * 100).toFixed(1)}</td>
                <td>%${(targets.HIGH_VOLATILITY * 100).toFixed(1)}</td>
              </tr>
            `).join("");
          }
        }
      } catch (e) {
        console.warn("Market behavior fetch error:", e);
      }

      // 2. Load Candlesticks
      await loadHistoricalCandles();

      // 3. Load Analog Patterns
      await loadAnalogPatterns();
    }

    function setCandleInterval(intv, btn) {
      candleInterval = intv;
      candleOffset = 0;
      document.querySelectorAll("#module-behavior .pill-btn").forEach(b => {
        if (['5m', '15m', '1h', '4h', '1d'].includes(b.innerText.trim())) {
          b.classList.remove("active");
        }
      });
      btn.classList.add("active");
      loadHistoricalCandles();
    }

    function changeCandleMonth(m) {
      candleMonth = m;
      candleOffset = 0;
      loadHistoricalCandles();
    }

    function changeCandleLimit(lim) {
      candleLimit = parseInt(lim);
      candleOffset = 0;
      loadHistoricalCandles();
    }

    function panCandles(delta) {
      candleOffset = Math.max(0, candleOffset + delta);
      loadHistoricalCandles();
    }

    async function loadHistoricalCandles() {
      try {
        const res = await fetch(`/api/v1/product/historical-candles?interval=${candleInterval}&month=${candleMonth}&limit=${candleLimit}&offset=${candleOffset}`);
        if (!res.ok) return;
        const data = await res.json();
        candlesData = data.candles || [];

        // Update month select if changed
        if (data.available_months && JSON.stringify(data.available_months) !== JSON.stringify(candleMonthsList)) {
          candleMonthsList = data.available_months;
          const select = document.getElementById("candle-month-select");
          if (select) {
            select.innerHTML = candleMonthsList.slice().reverse().map(m => `
              <option value="${m}" ${m === data.month ? 'selected' : ''}>${m}</option>
            `).join("");
          }
        }

        // Update HUD with latest bar by default
        if (candlesData.length > 0) {
          updateCandleHUD(candlesData[candlesData.length - 1]);
        }

        drawCandlestickChart();
      } catch (e) {
        console.warn("Candles fetch error:", e);
      }
    }

    function updateCandleHUD(c) {
      if (!c) return;
      const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
      setEl("hud-time", c.datetime_utc.replace("T", " ").replace("Z", " UTC"));
      setEl("hud-open", "$" + c.open.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}));
      setEl("hud-high", "$" + c.high.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}));
      setEl("hud-low", "$" + c.low.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}));
      setEl("hud-close", "$" + c.close.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}));
      setEl("hud-volume", c.volume.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}) + " BTC");
      const regEl = document.getElementById("hud-regime");
      if (regEl) {
        regEl.innerText = c.regime;
        regEl.className = "badge " + (c.regime.includes("BULL") ? "badge-success" : (c.regime.includes("BEAR") ? "badge-danger" : "badge-info"));
      }
    }

    function drawCandlestickChart() {
      const container = document.getElementById("candle-canvas-container");
      const canvas = document.getElementById("candlestick-canvas");
      if (!container || !canvas) return;

      const dpr = window.devicePixelRatio || 1;
      const w = container.clientWidth;
      const h = container.clientHeight || 420;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      const ctx = canvas.getContext("2d");
      ctx.scale(dpr, dpr);

      // Background
      ctx.fillStyle = "#070b13";
      ctx.fillRect(0, 0, w, h);

      if (!candlesData || candlesData.length === 0) {
        ctx.fillStyle = "#64748b";
        ctx.font = "14px monospace";
        ctx.textAlign = "center";
        ctx.fillText("Veri yükleniyor veya bu dönem için mum kaydı bulunamadı...", w / 2, h / 2);
        return;
      }

      const padTop = 20;
      const padBottom = 26;
      const padRight = 70;
      const padLeft = 10;
      const chartW = w - padLeft - padRight;
      const chartH = h - padTop - padBottom;
      const priceH = chartH * 0.72;
      const volH = chartH * 0.22;
      const volTop = padTop + priceH + chartH * 0.06;

      let minP = Infinity;
      let maxP = -Infinity;
      let maxV = 0;

      for (let i = 0; i < candlesData.length; i++) {
        const c = candlesData[i];
        if (c.low < minP) minP = c.low;
        if (c.high > maxP) maxP = c.high;
        if (c.volume > maxV) maxV = c.volume;
      }

      const pRange = (maxP - minP) || 1;
      minP -= pRange * 0.02;
      maxP += pRange * 0.02;
      const effRange = maxP - minP;

      const regColors = {
        "SIDEWAYS": "rgba(100, 116, 139, 0.12)",
        "UNCERTAIN": "rgba(245, 158, 11, 0.12)",
        "TRENDING_BULL": "rgba(16, 185, 129, 0.15)",
        "HIGH_VOLATILITY": "rgba(139, 92, 246, 0.15)",
        "TRENDING_BEAR": "rgba(239, 68, 68, 0.15)",
        "POSSIBLE_REVERSAL": "rgba(249, 115, 22, 0.15)"
      };

      const n = candlesData.length;
      const barW = chartW / n;
      const candleW = Math.max(1.2, barW * 0.7);

      // 1. Regime background bands
      for (let i = 0; i < n; i++) {
        const c = candlesData[i];
        ctx.fillStyle = regColors[c.regime] || "rgba(100, 116, 139, 0.06)";
        ctx.fillRect(padLeft + i * barW, padTop, barW, priceH);
      }

      // 2. Price grid horizontal lines
      ctx.strokeStyle = "rgba(31, 41, 55, 0.6)";
      ctx.fillStyle = "#64748b";
      ctx.font = "10px monospace";
      ctx.textAlign = "left";
      const gridSteps = 4;
      for (let g = 0; g <= gridSteps; g++) {
        const pVal = minP + (effRange * (g / gridSteps));
        const y = padTop + priceH - (g / gridSteps) * priceH;
        ctx.beginPath();
        ctx.moveTo(padLeft, y);
        ctx.lineTo(w - padRight, y);
        ctx.stroke();
        ctx.fillText("$" + Math.round(pVal).toLocaleString("en-US"), w - padRight + 6, y + 3);
      }

      // 3. Draw Candles & Volume
      for (let i = 0; i < n; i++) {
        const c = candlesData[i];
        const isUp = c.close >= c.open;
        const col = isUp ? "#10b981" : "#ef4444";
        const xCenter = padLeft + i * barW + barW / 2;

        // Wick
        const yHigh = padTop + (maxP - c.high) / effRange * priceH;
        const yLow = padTop + (maxP - c.low) / effRange * priceH;
        ctx.strokeStyle = col;
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(xCenter, yHigh);
        ctx.lineTo(xCenter, yLow);
        ctx.stroke();

        // Body
        const yOpen = padTop + (maxP - c.open) / effRange * priceH;
        const yClose = padTop + (maxP - c.close) / effRange * priceH;
        const bodyTop = Math.min(yOpen, yClose);
        const bodyH = Math.max(1.5, Math.abs(yOpen - yClose));
        ctx.fillStyle = col;
        ctx.fillRect(xCenter - candleW / 2, bodyTop, candleW, bodyH);

        // Volume Bar
        const vHeight = (c.volume / (maxV || 1)) * volH;
        ctx.fillStyle = isUp ? "rgba(16, 185, 129, 0.4)" : "rgba(239, 68, 68, 0.4)";
        ctx.fillRect(xCenter - candleW / 2, volTop + volH - vHeight, candleW, vHeight);
      }

      // 4. Time labels on bottom
      ctx.fillStyle = "#64748b";
      ctx.font = "10px monospace";
      ctx.textAlign = "center";
      const timeInterval = Math.max(1, Math.floor(n / 6));
      for (let i = 0; i < n; i += timeInterval) {
        const c = candlesData[i];
        const x = padLeft + i * barW + barW / 2;
        const label = c.datetime_utc.substring(5, 16).replace("T", " ");
        ctx.fillText(label, x, h - 8);
      }

      // 5. Crosshair if mouse hover
      if (crosshairPos) {
        ctx.strokeStyle = "rgba(148, 163, 184, 0.5)";
        ctx.lineWidth = 1;
        ctx.setLineDash([3, 3]);

        // Vertical
        ctx.beginPath();
        ctx.moveTo(crosshairPos.x, padTop);
        ctx.lineTo(crosshairPos.x, h - padBottom);
        ctx.stroke();

        // Horizontal Price
        if (crosshairPos.y <= padTop + priceH) {
          ctx.beginPath();
          ctx.moveTo(padLeft, crosshairPos.y);
          ctx.lineTo(w - padRight, crosshairPos.y);
          ctx.stroke();

          // Price badge on right
          const pCross = maxP - ((crosshairPos.y - padTop) / priceH) * effRange;
          ctx.fillStyle = "#1e293b";
          ctx.fillRect(w - padRight + 2, crosshairPos.y - 8, 65, 16);
          ctx.fillStyle = "#93c5fd";
          ctx.font = "10px monospace";
          ctx.textAlign = "left";
          ctx.fillText("$" + pCross.toFixed(1), w - padRight + 6, crosshairPos.y + 4);
        }

        ctx.setLineDash([]);
      }
    }

    // Attach canvas mouse events once
    function initCandleCanvasEvents() {
      const canvas = document.getElementById("candlestick-canvas");
      if (!canvas || canvas._events_bound) return;
      canvas._events_bound = true;

      canvas.addEventListener("mousemove", (e) => {
        const rect = canvas.getBoundingClientRect();
        const mouseX = e.clientX - rect.left;
        const mouseY = e.clientY - rect.top;

        const padLeft = 10;
        const padRight = 70;
        const chartW = rect.width - padLeft - padRight;
        if (!candlesData.length || chartW <= 0) return;

        const barW = chartW / candlesData.length;
        const idx = Math.floor((mouseX - padLeft) / barW);

        if (idx >= 0 && idx < candlesData.length) {
          crosshairPos = { x: mouseX, y: mouseY };
          updateCandleHUD(candlesData[idx]);
          drawCandlestickChart();
        }
      });

      canvas.addEventListener("mouseleave", () => {
        crosshairPos = null;
        if (candlesData.length > 0) {
          updateCandleHUD(candlesData[candlesData.length - 1]);
        }
        drawCandlestickChart();
      });
    }

    // Module 3 - Section 2: Analog Explorer
    async function loadAnalogPatterns() {
      try {
        const res = await fetch("/api/v1/product/analogs/patterns");
        if (!res.ok) return;
        const data = await res.json();
        const patterns = data.patterns || [];
        const select = document.getElementById("analog-pattern-select");
        if (select && patterns.length > 0) {
          select.innerHTML = patterns.map(p => `
            <option value="${p.decision_datetime_utc}">${p.label}</option>
          `).join("");

          // Load first pattern
          await loadAnalogs(patterns[0].decision_datetime_utc);
        }
      } catch (e) {
        console.warn("Analog patterns fetch error:", e);
      }
    }

    async function selectAnalogPattern(dt) {
      if (!dt) return;
      await loadAnalogs(dt);
    }

    async function loadAnalogs(decisionTime) {
      try {
        const res = await fetch(`/api/v1/product/analogs?decision_time=${encodeURIComponent(decisionTime)}`);
        if (!res.ok) return;
        const data = await res.json();
        currentAnalogData = data;

        // Dispersion Stats
        const disp = data.trajectory_dispersion || {};
        const setEl = (id, val) => { const el = document.getElementById(id); if (el) el.innerText = val; };
        setEl("analog-stat-mean", (disp.mean_24h_return_percent >= 0 ? "+" : "") + (disp.mean_24h_return_percent || 0).toFixed(2) + "%");
        setEl("analog-stat-median", (disp.median_24h_return_percent >= 0 ? "+" : "") + (disp.median_24h_return_percent || 0).toFixed(2) + "%");
        setEl("analog-stat-range", (disp.dispersion_range_percent || 0).toFixed(2) + "%");

        // Table
        const tBody = document.getElementById("analog-table-body");
        if (tBody) {
          const analogs = data.analogs || [];
          if (analogs.length === 0) {
            tBody.innerHTML = '<tr><td colspan="8" style="text-align:center; color:var(--text-muted); padding:20px;">Eşleşme bulunamadı.</td></tr>';
          } else {
            tBody.innerHTML = analogs.map(a => {
              const fmtRet = (r) => `<span class="${r >= 0 ? 'ret-pos' : 'ret-neg'}">${r >= 0 ? '+' : ''}${r.toFixed(2)}%</span>`;
              return `
                <tr>
                  <td><strong>#${a.rank}</strong></td>
                  <td><code>${a.analogue_datetime_utc.substring(0, 16).replace("T", " ")}</code></td>
                  <td><span class="badge badge-info">%${a.similarity_score_percent}</span></td>
                  <td>${fmtRet(a.fwd_ret_15m_percent)}</td>
                  <td>${fmtRet(a.fwd_ret_1h_percent)}</td>
                  <td>${fmtRet(a.fwd_ret_4h_percent)}</td>
                  <td>${fmtRet(a.fwd_ret_24h_percent)}</td>
                  <td><span class="ret-pos">+${a.max_favorable_excursion_percent}%</span> / <span class="ret-neg">${a.max_adverse_excursion_percent}%</span></td>
                </tr>
              `;
            }).join("");
          }
        }

        drawAnalogTrajectoryChart(data);
      } catch (e) {
        console.warn("Analog load error:", e);
      }
    }

    function drawAnalogTrajectoryChart(data) {
      const container = document.getElementById("analog-canvas-container");
      const canvas = document.getElementById("analog-canvas");
      if (!container || !canvas || !data) return;

      const dpr = window.devicePixelRatio || 1;
      const w = container.clientWidth;
      const h = container.clientHeight || 340;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      const ctx = canvas.getContext("2d");
      ctx.scale(dpr, dpr);

      // Background
      ctx.fillStyle = "#070b13";
      ctx.fillRect(0, 0, w, h);

      const analogs = data.analogs || [];
      if (analogs.length === 0) return;

      const padTop = 20;
      const padBottom = 30;
      const padLeft = 45;
      const padRight = 20;
      const chartW = w - padLeft - padRight;
      const chartH = h - padTop - padBottom;

      // Find global min and max return
      let minRet = 0;
      let maxRet = 0;
      analogs.forEach(a => {
        (a.trajectory_points || []).forEach(pt => {
          if (pt < minRet) minRet = pt;
          if (pt > maxRet) maxRet = pt;
        });
      });

      const retRange = Math.max(1.0, (maxRet - minRet));
      minRet -= retRange * 0.15;
      maxRet += retRange * 0.15;
      const effRetRange = maxRet - minRet;

      const xSteps = [0, 0.25, 0.5, 0.75, 1.0];
      const stepLabels = ["0m", "+15m", "+1h", "+4h", "+24h"];

      // 1. Gridlines & 0% baseline
      ctx.strokeStyle = "rgba(31, 41, 55, 0.6)";
      ctx.lineWidth = 1;
      const yZero = padTop + (maxRet - 0.0) / effRetRange * chartH;

      // 0% line
      ctx.beginPath();
      ctx.strokeStyle = "rgba(148, 163, 184, 0.4)";
      ctx.setLineDash([4, 4]);
      ctx.moveTo(padLeft, yZero);
      ctx.lineTo(w - padRight, yZero);
      ctx.stroke();
      ctx.setLineDash([]);

      // Vertical steps
      xSteps.forEach((s, idx) => {
        const x = padLeft + s * chartW;
        ctx.strokeStyle = "rgba(31, 41, 55, 0.5)";
        ctx.beginPath();
        ctx.moveTo(x, padTop);
        ctx.lineTo(x, padTop + chartH);
        ctx.stroke();

        ctx.fillStyle = "#64748b";
        ctx.font = "10px monospace";
        ctx.textAlign = "center";
        ctx.fillText(stepLabels[idx], x, h - 10);
      });

      // Y-axis labels
      ctx.fillStyle = "#64748b";
      ctx.font = "10px monospace";
      ctx.textAlign = "right";
      [minRet, 0, maxRet].forEach(val => {
        const y = padTop + (maxRet - val) / effRetRange * chartH;
        ctx.fillText((val >= 0 ? "+" : "") + val.toFixed(1) + "%", padLeft - 6, y + 3);
      });

      // 2. Dispersion corridor (Min to Max envelope at each step)
      ctx.fillStyle = "rgba(59, 130, 246, 0.07)";
      ctx.beginPath();
      for (let sIdx = 0; sIdx < 5; sIdx++) {
        const stepVals = analogs.map(a => a.trajectory_points[sIdx]);
        const sMax = Math.max(...stepVals);
        const x = padLeft + xSteps[sIdx] * chartW;
        const y = padTop + (maxRet - sMax) / effRetRange * chartH;
        if (sIdx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      for (let sIdx = 4; sIdx >= 0; sIdx--) {
        const stepVals = analogs.map(a => a.trajectory_points[sIdx]);
        const sMin = Math.min(...stepVals);
        const x = padLeft + xSteps[sIdx] * chartW;
        const y = padTop + (maxRet - sMin) / effRetRange * chartH;
        ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.fill();

      // 3. Draw each analog trajectory
      const trajColors = ["#38bdf8", "#a855f7", "#f59e0b", "#10b981", "#f43f5e"];
      analogs.forEach((a, aIdx) => {
        const pts = a.trajectory_points || [];
        ctx.strokeStyle = trajColors[aIdx % trajColors.length];
        ctx.lineWidth = 1.8;
        ctx.beginPath();
        pts.forEach((pt, sIdx) => {
          const x = padLeft + xSteps[sIdx] * chartW;
          const y = padTop + (maxRet - pt) / effRetRange * chartH;
          if (sIdx === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.stroke();

        // Draw dots at step points
        pts.forEach((pt, sIdx) => {
          const x = padLeft + xSteps[sIdx] * chartW;
          const y = padTop + (maxRet - pt) / effRetRange * chartH;
          ctx.fillStyle = trajColors[aIdx % trajColors.length];
          ctx.beginPath();
          ctx.arc(x, y, 3, 0, Math.PI * 2);
          ctx.fill();
        });
      });
    }

    // Module 4: Events
    async function loadEvents() {
      try {
        const q = (document.getElementById("events-search")?.value || "");
        const res = await fetch(`/api/v1/product/events?page=${eventsPage}&limit=${eventsLimit}&category=${selectedEventCat}&search=${encodeURIComponent(q)}`);
        if (!res.ok) return;
        const data = await res.json();
        eventsData = data.events || [];

        const tBody = document.getElementById("events-tbody");
        if (tBody) {
          if (eventsData.length === 0) {
            tBody.innerHTML = '<tr><td colspan="7" style="text-align:center; color:var(--text-muted); padding:20px;">Olay kaydı bulunamadı.</td></tr>';
          } else {
            tBody.innerHTML = eventsData.map(e => `
              <tr>
                <td><code>${e.event_id}</code></td>
                <td><span class="badge badge-info">${e.category}</span></td>
                <td>${e.published_at_utc ? e.published_at_utc.substring(0, 16).replace('T', ' ') : '-'}</td>
                <td>${e.source_name || '-'}</td>
                <td><strong>${e.headline}</strong></td>
                <td><span class="badge ${e.event_direction_hypothesis === 'BEARISH' ? 'badge-danger' : 'badge-warn'}">${e.event_direction_hypothesis || 'NEUTRAL'}</span></td>
                <td>${e.event_severity || '-'}</td>
              </tr>
            `).join("");
          }
        }

        const pageInfo = document.getElementById("events-page-info");
        if (pageInfo) pageInfo.innerText = `Sayfa ${data.page} / ${data.total_pages} (Toplam ${data.total_events} Olay)`;

        const btnPrev = document.getElementById("btn-events-prev");
        if (btnPrev) btnPrev.disabled = data.page <= 1;

        const btnNext = document.getElementById("btn-events-next");
        if (btnNext) btnNext.disabled = data.page >= data.total_pages;

      } catch (e) {
        console.warn("Events fetch error:", e);
      }
    }

    function setEventCat(cat, btn) {
      selectedEventCat = cat;
      eventsPage = 1;
      document.querySelectorAll("#module-events .pill-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      loadEvents();
    }

    function filterEvents() {
      eventsPage = 1;
      loadEvents();
    }

    function changeEventsPage(delta) {
      eventsPage += delta;
      if (eventsPage < 1) eventsPage = 1;
      loadEvents();
    }

    // Module 5: Governance
    async function loadGovernance() {
      // Governance data is mostly static / declarative, fetch overview
      try {
        await fetch("/api/v1/product/governance");
      } catch (e) {}
    }

    // Module 6: Artifacts
    async function loadArtifacts() {
      try {
        const q = (document.getElementById("artifacts-search")?.value || "");
        const res = await fetch(`/api/v1/product/artifacts?page=${artifactsPage}&limit=${artifactsLimit}&extension=${selectedArtifactExt}&search=${encodeURIComponent(q)}`);
        if (!res.ok) return;
        const data = await res.json();
        artifactsData = data.artifacts || [];

        const tBody = document.getElementById("artifacts-tbody");
        if (tBody) {
          if (artifactsData.length === 0) {
            tBody.innerHTML = '<tr><td colspan="6" style="text-align:center; color:var(--text-muted); padding:20px;">Kanıt dosyası bulunamadı.</td></tr>';
          } else {
            tBody.innerHTML = artifactsData.map(a => `
              <tr>
                <td><strong>${a.name}</strong></td>
                <td><span class="badge badge-info">${a.category}</span></td>
                <td><code>${a.extension}</code></td>
                <td>${(a.size_bytes / 1024).toFixed(1)} KB</td>
                <td>${a.modified_at_utc ? a.modified_at_utc.substring(0, 19).replace('T', ' ') : '-'}</td>
                <td>
                  <button class="btn" style="padding: 3px 8px; font-size: 11px;" onclick="previewArtifact('${a.relative_path}', '${a.name}')">
                    Önizle
                  </button>
                </td>
              </tr>
            `).join("");
          }
        }

        const pageInfo = document.getElementById("artifacts-page-info");
        if (pageInfo) pageInfo.innerText = `Sayfa ${data.page} / ${data.total_pages} (Toplam ${data.total_artifacts} Dosya)`;

        const btnPrev = document.getElementById("btn-artifacts-prev");
        if (btnPrev) btnPrev.disabled = data.page <= 1;

        const btnNext = document.getElementById("btn-artifacts-next");
        if (btnNext) btnNext.disabled = data.page >= data.total_pages;

      } catch (e) {
        console.warn("Artifacts fetch error:", e);
      }
    }

    function setArtifactExt(ext, btn) {
      selectedArtifactExt = ext;
      artifactsPage = 1;
      document.querySelectorAll("#module-artifacts .pill-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      loadArtifacts();
    }

    function filterArtifacts() {
      artifactsPage = 1;
      loadArtifacts();
    }

    function changeArtifactsPage(delta) {
      artifactsPage += delta;
      if (artifactsPage < 1) artifactsPage = 1;
      loadArtifacts();
    }

    async function previewArtifact(relPath, fileName) {
      const modal = document.getElementById("preview-modal");
      const title = document.getElementById("modal-title");
      const content = document.getElementById("modal-content");
      const meta = document.getElementById("modal-meta");

      if (title) title.innerText = fileName;
      if (content) content.innerText = "Yükleniyor...";
      if (modal) modal.classList.add("active");

      try {
        const res = await fetch(`/api/v1/product/artifacts/preview?path=${encodeURIComponent(relPath)}`);
        const data = await res.json();
        if (!res.ok) {
          if (content) content.innerText = "Hata: " + (data.message || res.statusText);
          return;
        }

        if (content) content.innerText = data.content;
        if (meta) {
          meta.innerText = `Boyut: ${(data.file_size_bytes / 1024).toFixed(1)} KB | Satır: ${data.line_count || '-'} ${data.is_truncated ? '(Önizleme 256 KB ile sınırlandırıldı)' : ''}`;
        }
      } catch (e) {
        if (content) content.innerText = "Bağlantı hatası: " + e;
      }
    }

    function closeModal() {
      const modal = document.getElementById("preview-modal");
      if (modal) modal.classList.remove("active");
    }

    function closeModalOnOverlay(e) {
      if (e.target.id === "preview-modal") closeModal();
    }

    // Module 7: Operations
    async function loadOperations() {
      try {
        const res = await fetch("/api/v1/product/operations");
        if (!res.ok) return;
        const data = await res.json();

        const sEl = document.getElementById("ops-storage-mb");
        if (sEl && data.storage_status) {
          sEl.innerText = (data.storage_status.research_outputs_mb + data.storage_status.data_directory_mb).toFixed(1) + " MB";
        }
        const aEl = document.getElementById("ops-artifacts-count");
        if (aEl && data.storage_status) {
          aEl.innerText = data.storage_status.artifacts_indexed_count;
        }
      } catch (e) {
        console.warn("Operations fetch error:", e);
      }
    }

    // Init with hash or default
    window.addEventListener("DOMContentLoaded", () => {
      const hash = window.location.hash.replace("#", "");
      if (hash && ["overview", "research", "behavior", "events", "governance", "artifacts", "operations"].includes(hash)) {
        switchTab(hash); initCandleCanvasEvents();
      } else {
        switchTab("overview"); initCandleCanvasEvents();
      }
      loadOverview();
    });
  </script>
</body>
</html>
"""

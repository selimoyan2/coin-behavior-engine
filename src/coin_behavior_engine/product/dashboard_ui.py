"""Sprint Product Acceleration 03 — Product Dashboard UI Renderer & Assets.

Provides a unified, responsive, dark-mode research workspace:
- 7 Integrated Modules: Overview (Research Workspace), Research Results (Visualizations),
  Market Behavior (Interactive Candlesticks, Regimes, Analog Explorer),
  News & Macro Research (Audited Event Reactions), Governance Center,
  Artifact Browser (550+ files), Operations & System Status.
- Zero-dependency client-side Canvas rendering (candlesticks, volume, regimes, analog dispersion).
- Macroeconomic and regulatory event overlay pins on historical price chart.
- Dynamic runtime git revision reporting (eliminating hardcoded hashes).
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
  <title>Coin Behavior Engine | Araştırma Portalı & Piyasa İstihbaratı</title>
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
      gap: 10px;
      flex-wrap: wrap;
    }
    .brand-logo {
      font-size: 19px;
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
      padding: 3px 8px;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      letter-spacing: 0.3px;
      font-family: var(--font-mono);
    }
    .badge-frozen { background: #1e293b; color: #94a3b8; border: 1px solid #334155; }
    .badge-success { background: var(--green-bg); color: #34d399; border: 1px solid var(--green-border); }
    .badge-danger { background: var(--red-bg); color: #f87171; border: 1px solid var(--red-border); }
    .badge-warn { background: var(--yellow-bg); color: #fbbf24; border: 1px solid var(--yellow-border); }
    .badge-info { background: var(--blue-bg); color: #60a5fa; border: 1px solid var(--blue-border); }
    .badge-purple { background: rgba(139, 92, 246, 0.12); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.3); }

    /* Navigation Tabs */
    .nav-tabs {
      background: #0b101c;
      border-bottom: 1px solid var(--border);
      padding: 0 24px;
      display: flex;
      gap: 4px;
      overflow-x: auto;
      white-space: nowrap;
    }
    .nav-tab {
      padding: 12px 16px;
      color: var(--text-muted);
      text-decoration: none;
      font-size: 13px;
      font-weight: 600;
      border-bottom: 2px solid transparent;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
      cursor: pointer;
    }
    .nav-tab:hover { color: #fff; background: rgba(255, 255, 255, 0.02); }
    .nav-tab.active {
      color: var(--accent);
      border-bottom-color: var(--accent);
      background: rgba(59, 130, 246, 0.06);
    }

    /* Container & Layout */
    .container {
      max-width: 1440px;
      width: 100%;
      margin: 0 auto;
      padding: 24px;
      flex: 1;
    }
    .tab-content { display: none; }
    .tab-content.active { display: block; }

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
      padding: 18px;
      transition: border-color 0.15s ease;
    }
    .card:hover { border-color: #374151; }
    .card h3 {
      font-size: 12px;
      font-weight: 600;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.5px;
      margin-bottom: 8px;
    }
    .card .value {
      font-size: 24px;
      font-weight: 800;
      font-family: var(--font-mono);
      color: #fff;
    }
    .card .subtext {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 6px;
      line-height: 1.4;
    }

    /* Alert Banner */
    .alert-banner {
      background: rgba(239, 68, 68, 0.08);
      border: 1px solid var(--red-border);
      border-radius: 8px;
      padding: 12px 16px;
      font-size: 13px;
      color: #fca5a5;
      margin-bottom: 20px;
      line-height: 1.5;
    }
    .alert-banner.info {
      background: rgba(59, 130, 246, 0.08);
      border-color: var(--blue-border);
      color: #93c5fd;
    }
    .alert-banner.warn {
      background: rgba(245, 158, 11, 0.08);
      border-color: var(--yellow-border);
      color: #fde68a;
    }

    /* Section Headers */
    .section-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin: 24px 0 14px 0;
      flex-wrap: wrap;
      gap: 10px;
    }
    .section-title {
      font-size: 15px;
      font-weight: 700;
      color: #fff;
      display: flex;
      align-items: center;
      gap: 8px;
    }

    /* Buttons */
    .btn {
      background: #1f2937;
      color: #fff;
      border: 1px solid #374151;
      padding: 6px 12px;
      border-radius: 6px;
      font-size: 12px;
      font-weight: 600;
      cursor: pointer;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: all 0.15s ease;
      text-decoration: none;
    }
    .btn:hover { background: #374151; border-color: #4b5563; }
    .btn-primary { background: #2563eb; border-color: #1d4ed8; }
    .btn-primary:hover { background: #1d4ed8; }

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
      text-align: left;
      font-size: 13px;
    }
    th, td {
      padding: 10px 14px;
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
      gap: 8px;
      margin-bottom: 16px;
      flex-wrap: wrap;
      align-items: center;
    }
    .search-input {
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: #fff;
      padding: 7px 12px;
      border-radius: 6px;
      font-size: 12px;
      min-width: 240px;
      outline: none;
    }
    .search-input:focus { border-color: var(--accent); }
    .pill-btn {
      background: var(--card-bg);
      border: 1px solid var(--border);
      color: var(--text-muted);
      padding: 5px 12px;
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

    /* Chart and Explorer Controls */
    .chart-panel {
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 12px;
      padding: 18px;
      margin-bottom: 24px;
    }
    .chart-toolbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      flex-wrap: wrap;
      gap: 10px;
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
      padding: 5px 10px;
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

    /* Event Tooltip on Canvas */
    .event-popover {
      display: none;
      position: absolute;
      background: #111827;
      border: 1px solid var(--border-focus);
      border-radius: 8px;
      padding: 10px 14px;
      font-size: 12px;
      color: #fff;
      z-index: 50;
      box-shadow: 0 10px 25px rgba(0,0,0,0.7);
      max-width: 320px;
      pointer-events: none;
    }

    /* Modal Overlay */
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

    /* Pagination */
    .pagination-bar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 10px 14px;
      font-size: 12px;
      color: var(--text-muted);
      border-top: 1px solid var(--border);
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
      .container { padding: 14px; }
      .grid { grid-template-columns: 1fr; }
      .top-header { padding: 12px 14px; }
      .nav-tabs { padding: 0 14px; }
      .search-input { min-width: 100%; }
      .chart-hud { font-size: 11px; gap: 8px; }
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
      <span class="badge badge-frozen">CBE-0.7.0 DONDURULDU</span>
      <span class="badge badge-info" id="hdr-git-pill">Build: <code class="dyn-git-rev-short">69027de4</code></span>
      <span class="badge badge-danger">TECHNICAL NO-GO</span>
    </div>
    <div class="header-badges">
      <span class="badge badge-warn">YÖNETİŞİM: ONAYLANMADI</span>
      <span class="badge badge-info">ÇEVRİMDIŞI ARAŞTIRMA MODU</span>
      <span class="badge badge-danger">CANLI İŞLEM: YASAK</span>
      <button class="btn" id="btn-refresh" onclick="refreshCurrentTab()">
        <span>↻</span> Yenile
      </button>
    </div>
  </header>

  <!-- Top Navigation Tabs (7 Core Modules) -->
  <nav class="nav-tabs" role="navigation" aria-label="Ürün Modülleri">
    <a href="#overview" class="nav-tab active" id="tab-btn-overview" onclick="switchTab('overview')">
      <span>🔬</span> Araştırma Alanı (Genel Bakış)
    </a>
    <a href="#behavior" class="nav-tab" id="tab-btn-behavior" onclick="switchTab('behavior')">
      <span>📈</span> Piyasa Davranışı & Rejimler
    </a>
    <a href="#events" class="nav-tab" id="tab-btn-events" onclick="switchTab('events')">
      <span>📰</span> Olay & Makro Araştırması
    </a>
    <a href="#research" class="nav-tab" id="tab-btn-research" onclick="switchTab('research')">
      <span>📊</span> Araştırma Bulguları
    </a>
    <a href="#governance" class="nav-tab" id="tab-btn-governance" onclick="switchTab('governance')">
      <span>🔐</span> Yönetişim & Güvenlik
    </a>
    <a href="#artifacts" class="nav-tab" id="tab-btn-artifacts" onclick="switchTab('artifacts')">
      <span>📁</span> Kanıt Arşivi (550+)
    </a>
    <a href="#operations" class="nav-tab" id="tab-btn-operations" onclick="switchTab('operations')">
      <span>⚙️</span> Sistem & Operasyon
    </a>
  </nav>

  <!-- Main Work Area -->
  <main class="container" role="main">

    <!-- =================================================================== -->
    <!-- MODULE 1: RESEARCH WORKSPACE (OVERVIEW REDESIGN)                     -->
    <!-- =================================================================== -->
    <section id="module-overview" class="tab-content active">
      <!-- Research Workspace Banner -->
      <div class="card" style="border-left: 4px solid var(--accent); margin-bottom: 20px;">
        <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 12px;">
          <div>
            <div style="font-size: 11px; font-weight: 700; color: var(--accent); letter-spacing: 0.5px;">TARİHSEL PİYASA ARAŞTIRMA ÇALIŞMA ALANI</div>
            <h2 style="font-size: 18px; color: #fff; margin: 4px 0;">BTCUSDT Binance Spot Multi-Year Analiz Platformu</h2>
            <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
              Kapsam: <b>2022-01 — 2026-09 (57 Kesintisiz Ay)</b> &bull;
              Desteklenen Aralıklar: <b>5m, 15m, 1h, 4h, 1d</b> &bull;
              Rejim Etiketleri: <b>105.120 Bar</b> &bull;
              Denetlenmiş Makro Olaylar: <b>236 Kayıt</b>
            </div>
          </div>
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <button class="btn btn-primary" onclick="switchTab('behavior')">📈 Detaylı Grafik & Analog Gezgini</button>
            <button class="btn" onclick="switchTab('events')">📰 Olay Reaksiyonları</button>
            <button class="btn" onclick="switchTab('research')">📊 Bilimsel Bulgular</button>
          </div>
        </div>
      </div>

      <!-- Main Historical Chart embedded on Overview -->
      <div class="section-header">
        <div class="section-title"><span>📈</span> Tarihsel Fiyat & Rejim Gözlemi (BTCUSDT)</div>
        <div style="display: flex; gap: 6px;">
          <span class="badge badge-info">ÇEVRİMDIŞI PARQUET ARŞİVİ</span>
          <span class="badge badge-warn">ARAŞTIRMA KONTAMİNASYONLU</span>
        </div>
      </div>

      <div class="chart-panel">
        <div class="chart-toolbar">
          <div class="chart-controls-group">
            <span style="font-size: 12px; color: var(--text-muted); font-weight: 600;">Zaman Dilimi:</span>
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
            <span style="font-size: 12px; color: var(--text-muted); font-weight: 600;">Bar Sayısı:</span>
            <select id="candle-limit-select" class="select-dropdown" onchange="changeCandleLimit(this.value)">
              <option value="50">50 Bar</option>
              <option value="100" selected>100 Bar</option>
              <option value="200">200 Bar</option>
              <option value="500">500 Bar</option>
            </select>
            <div style="display: flex; gap: 4px;">
              <button class="btn" style="padding: 4px 8px; font-size: 11px;" onclick="panCandles(-25)" title="Önceki Barlar">◀ Önceki</button>
              <button class="btn" style="padding: 4px 8px; font-size: 11px;" onclick="panCandles(25)" title="Sonraki Barlar">Sonraki ▶</button>
              <button class="btn" style="padding: 4px 8px; font-size: 11px;" onclick="resetCandleZoom()" title="Görünümü Sıfırla">Sıfırla</button>
            </div>
            <label style="font-size: 11px; display: inline-flex; align-items: center; gap: 4px; color: #93c5fd; cursor: pointer;">
              <input type="checkbox" id="toggle-events-overlay" checked onchange="toggleEventOverlay(this.checked)"> Makro Olay Pinleri
            </label>
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
          <div id="event-popover" class="event-popover"></div>
        </div>

        <div class="chart-legend">
          <span style="font-weight: 600; color: #fff;">Piyasa Rejimleri:</span>
          <div class="legend-item"><span class="legend-color" style="background: #64748b;"></span> <span>SIDEWAYS (Yatay)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #f59e0b;"></span> <span>UNCERTAIN (Belirsiz)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #10b981;"></span> <span>TRENDING_BULL (Boğa)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #8b5cf6;"></span> <span>HIGH_VOLATILITY (Volatil)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #ef4444;"></span> <span>TRENDING_BEAR (Ayı)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #f97316;"></span> <span>POSSIBLE_REVERSAL (Dönüş)</span></div>
          <span style="margin-left: 12px; font-weight: 600; color: #fff;">Olay Pinleri:</span>
          <span>🏛️ SEC/Düzenleyici</span> &bull; <span>🏦 Fed/Para Politikası</span> &bull; <span>📈 Enflasyon (CPI)</span> &bull; <span>💼 İstihdam</span>
        </div>
      </div>

      <!-- Secondary Section: Empirical Research Intelligence Cards -->
      <div class="section-header">
        <div class="section-title"><span>🧠</span> Temel Araştırma Çıkarımları & Kanıt Özeti</div>
      </div>

      <div class="grid">
        <div class="card">
          <h3>Perpetual Fonlama & Carry Gerçeği</h3>
          <div class="value" style="color: #fbbf24;">+0.0108% / 8h</div>
          <div class="subtext">
            Yıllık Brüt: <b>~%11.82</b> | Yarılanma Ömrü: <b>19.2 Saat</b><br>
            Taker Komisyonu: <b>19 — 36 bps</b> (Tur Başına)<br>
            <b style="color:#f87171;">Sonuç:</b> İşlem sürtünmesi net carry getirisini sıfırlar ve negatif değere çeker.
          </div>
        </div>

        <div class="card">
          <h3>Fraktal / Analog Desen Dağılımı</h3>
          <div class="value" style="color: #60a5fa;">%51.4 Yönsel Başarım</div>
          <div class="subtext">
            Örneklem: <b>306 Karar Noktası, 1.530 Eşleşme</b><br>
            İleriye Dönük Yörünge: <b>Geniş Dağılım Koridoru</b><br>
            <b style="color:#f87171;">Sonuç:</b> STATISTICALLY_INTERESTING_BUT_NOT_ECONOMIC. Alım/satım alfası üretmez.
          </div>
        </div>

        <div class="card">
          <h3>Çoklu Varlık Fonlama Korelasyonu</h3>
          <div class="value" style="color: #c084fc;">%83 — %88 Korelasyon</div>
          <div class="subtext">
            Varlıklar: <b>BTC, ETH, SOL (14 Aylık Veri)</b><br>
            Varlıklar Arası Fark: <b>0.71 bps</b> | Rotasyon Masrafı: <b>38-72 bps</b><br>
            <b style="color:#f87171;">Sonuç:</b> Çapraz fonlama arbitrajı rotasyon sürtünmesini aşamaz.
          </div>
        </div>

        <div class="card">
          <h3>Makro & Düzenleyici Olay Reaksiyonu</h3>
          <div class="value" style="color: #34d399;">236 Denetlenmiş Olay</div>
          <div class="subtext">
            Kapsam: <b>CPI, FOMC, Tarım Dışı İstihdam, SEC</b><br>
            Tepki Karakteristiği: <b>Volatilite Sıçraması</b><br>
            <b style="color:#fde68a;">Sonuç:</b> Olay anı oynaklık artışı mevcuttur; yönsel öngörü tek başına kanıtlanmamıştır.
          </div>
        </div>
      </div>

      <!-- Lower Section: Compact Governance & Safety Status Bar -->
      <div class="card" style="background: #0b111e; border: 1px solid #1e293b;">
        <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
          <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
            <span style="font-size: 13px; font-weight: 700; color: #fff;">Güvenlik Kontratı:</span>
            <span class="badge badge-danger">TECHNICAL NO-GO</span>
            <span class="badge badge-warn">YÖNETİŞİM: NOT_GRANTED</span>
            <span class="badge badge-frozen">CBE-0.7.0 FROZEN</span>
            <span class="badge badge-success">Ed25519 (RFC 8032)</span>
            <span class="badge badge-info">Çalışan Taahhüt: <code class="dyn-git-rev-short">69027de4</code></span>
          </div>
          <button class="btn" style="font-size: 11px;" onclick="switchTab('governance')">Yönetişim Detayları ➔</button>
        </div>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- MODULE 3: MARKET BEHAVIOR & HISTORICAL EXPLORERS                     -->
    <!-- =================================================================== -->
    <section id="module-behavior" class="tab-content">
      <div class="alert-banner info">
        <strong>ℹ️ MODEL REJİMİ GÜVENLİK KALKANI:</strong><br>
        Dondurulmuş modelin (CBE-0.7.0) persentil hesaplama algoritmasındaki mantık hatası (<code>x &lt;= x</code> eşitlik durumu)
        nedeniyle ham <code>DELEVERAGING_STRESS</code> çıktısı fail-closed korumasıyla <strong>UNKNOWN</strong> durumuna çekilmiştir.
        Aşağıdaki tüm grafik ve veriler geçmiş doğrulanmış çok yıllık spot veri setleri (2022-2026 Parquet) ve kanonik rejim çizelgesi üzerinden hesaplanmaktadır.
      </div>

      <!-- SECTION 1: DETAILED HISTORICAL CANDLESTICK & REGIME CHART -->
      <div class="section-header">
        <div class="section-title"><span>📈</span> Derinlikli Fiyat & Piyasa Rejimi Gezgini (BTCUSDT Multi-Year)</div>
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
            <select id="candle-month-select-2" class="select-dropdown" onchange="changeCandleMonth(this.value)">
              <option value="2026-09">2026-09 (Eylül 2026)</option>
            </select>
            <span style="font-size: 12px; color: var(--text-muted); font-weight: 600;">Bar:</span>
            <select id="candle-limit-select-2" class="select-dropdown" onchange="changeCandleLimit(this.value)">
              <option value="50">50 Bar</option>
              <option value="100" selected>100 Bar</option>
              <option value="200">200 Bar</option>
              <option value="500">500 Bar</option>
            </select>
            <div style="display: flex; gap: 4px;">
              <button class="btn" style="padding: 4px 8px; font-size: 11px;" onclick="panCandles(-25)">◀ Önceki</button>
              <button class="btn" style="padding: 4px 8px; font-size: 11px;" onclick="panCandles(25)">Sonraki ▶</button>
              <button class="btn" style="padding: 4px 8px; font-size: 11px;" onclick="resetCandleZoom()">Sıfırla</button>
            </div>
            <label style="font-size: 11px; display: inline-flex; align-items: center; gap: 4px; color: #93c5fd; cursor: pointer;">
              <input type="checkbox" id="toggle-events-overlay-2" checked onchange="toggleEventOverlay(this.checked)"> Olay Pinleri
            </label>
          </div>
        </div>

        <div class="chart-hud" id="candle-hud-2">
          <div><span style="color:var(--text-muted);">Zaman:</span> <span class="val" id="hud-time-2">-</span></div>
          <div><span style="color:var(--text-muted);">A:</span> <span class="val" id="hud-open-2">-</span></div>
          <div><span style="color:var(--text-muted);">Y:</span> <span class="val" id="hud-high-2">-</span></div>
          <div><span style="color:var(--text-muted);">D:</span> <span class="val" id="hud-low-2">-</span></div>
          <div><span style="color:var(--text-muted);">K:</span> <span class="val" id="hud-close-2">-</span></div>
          <div><span style="color:var(--text-muted);">Hacim:</span> <span class="val" id="hud-volume-2">-</span></div>
          <div><span style="color:var(--text-muted);">Rejim:</span> <span id="hud-regime-2" class="badge badge-info">-</span></div>
        </div>

        <div class="chart-canvas-wrap" id="candle-canvas-container-2">
          <canvas id="candlestick-canvas-2" class="chart-canvas"></canvas>
          <div id="event-popover-2" class="event-popover"></div>
        </div>

        <div class="chart-legend">
          <span style="font-weight: 600; color: #fff;">Piyasa Rejimleri:</span>
          <div class="legend-item"><span class="legend-color" style="background: #64748b;"></span> <span>SIDEWAYS (Yatay)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #f59e0b;"></span> <span>UNCERTAIN (Belirsiz)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #10b981;"></span> <span>TRENDING_BULL (Boğa)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #8b5cf6;"></span> <span>HIGH_VOLATILITY (Volatil)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #ef4444;"></span> <span>TRENDING_BEAR (Ayı)</span></div>
          <div class="legend-item"><span class="legend-color" style="background: #f97316;"></span> <span>POSSIBLE_REVERSAL (Dönüş)</span></div>
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
    <!-- MODULE 4: NEWS & MACRO RESEARCH (AUDITED EVENT REACTIONS)           -->
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
        <div class="section-title"><span>📰</span> Denetlenmiş Makro Ekonomik Olaylar & Fiyat Reaksiyonları (N=236)</div>
        <span class="badge badge-info">TARİHSEL REAKSİYON DEFTERİ</span>
      </div>

      <div class="filter-bar">
        <input type="text" id="macro-search" class="search-input" placeholder="Olay başlığı, aktör veya ID ile ara..." oninput="filterMacroReactions()">
        <button class="pill-btn active" onclick="setMacroCat('ALL', this)">Tümü</button>
        <button class="pill-btn" onclick="setMacroCat('US_INFLATION', this)">Enflasyon (CPI)</button>
        <button class="pill-btn" onclick="setMacroCat('US_MONETARY_POLICY', this)">Para Politikası (Fed)</button>
        <button class="pill-btn" onclick="setMacroCat('US_LABOR', this)">İstihdam (Labor)</button>
        <button class="pill-btn" onclick="setMacroCat('REGULATION', this)">Düzenleyici (SEC)</button>
        <button class="pill-btn" onclick="setMacroCat('US_GROWTH', this)">Büyüme (GDP)</button>
      </div>

      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Olay ID</th>
              <th>Kategori</th>
              <th>Yayın Tarihi (UTC)</th>
              <th>Kurum</th>
              <th>Olay Başlığı</th>
              <th>Açılış ($)</th>
              <th>15m Tepki</th>
              <th>1h Tepki</th>
              <th>24h Tepki</th>
            </tr>
          </thead>
          <tbody id="macro-tbody">
            <!-- Injected via client.js -->
          </tbody>
        </table>
        <div class="pagination-bar">
          <span id="macro-page-info">Yükleniyor...</span>
        </div>
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
              <td>Güvenlik Denetimi & Token İptali</td>
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
        <div class="section-title"><span>📁</span> Doğrulanmış Araştırma Kanıt Arşivi (550+ Dosya)</div>
      </div>

      <div class="filter-bar">
        <input type="text" id="artifacts-search" class="search-input" placeholder="Dosya adı veya göreli yolla ara..." oninput="filterArtifacts()">
        <button class="pill-btn active" onclick="setArtifactExt('all', this)">Tümü</button>
        <button class="pill-btn" onclick="setArtifactExt('.json', this)">JSON</button>
        <button class="pill-btn" onclick="setArtifactExt('.md', this)">Markdown</button>
        <button class="pill-btn" onclick="setArtifactExt('.csv', this)">CSV</button>
        <button class="pill-btn" onclick="setArtifactExt('.parquet', this)">Parquet</button>
      </div>

      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Dosya Adı</th>
              <th>Kategori</th>
              <th>Tür</th>
              <th>Boyut</th>
              <th>Son Değişiklik (UTC)</th>
              <th>Eylem</th>
            </tr>
          </thead>
          <tbody id="artifacts-tbody">
            <!-- Injected via client.js -->
          </tbody>
        </table>
        <div class="pagination-bar">
          <span id="artifacts-page-info">Sayfa 1 / 1</span>
          <div style="display: flex; gap: 8px;">
            <button class="btn" id="btn-artifacts-prev" onclick="changeArtifactsPage(-1)">Önceki</button>
            <button class="btn" id="btn-artifacts-next" onclick="changeArtifactsPage(1)">Sonraki</button>
          </div>
        </div>
      </div>
    </section>

    <!-- =================================================================== -->
    <!-- MODULE 7: OPERATIONS & SYSTEM STATUS (ENVIRONMENT SEPARATION)       -->
    <!-- =================================================================== -->
    <section id="module-operations" class="tab-content">
      <!-- Section A: Current Running Staging Environment -->
      <div class="section-header">
        <div class="section-title"><span>🚀</span> Mevcut Çalışan Ortam (Coolify Linux VPS Staging)</div>
        <span class="badge badge-success">CANLI SERVİS DOĞRULANDI</span>
      </div>

      <div class="grid">
        <div class="card">
          <h3>Çalışan Git Taahhüdü</h3>
          <div class="value" style="font-size: 16px;"><code class="dyn-git-rev">69027de4bd8baf79...</code></div>
          <div class="subtext">
            Dal: <code>main</code> &bull; Durum: <b>Senkronize</b><br>
            Model Sürümü: <b>CBE-0.7.0 (Donduruldu)</b>
          </div>
        </div>

        <div class="card">
          <h3>Çalışma Zamanı & Bellek</h3>
          <div class="value" id="ops-runtime-platform" style="font-size: 18px;">Linux (Container)</div>
          <div class="subtext">
            Python: <b id="ops-python-ver">3.11</b> &bull; RSS: <b id="ops-memory-rss">- MB</b><br>
            Çalışma Süresi: <b id="ops-uptime">- sn</b>
          </div>
        </div>

        <div class="card">
          <h3>Çok Yıllık Parquet Veri Seti</h3>
          <div class="value" style="font-size: 18px; color: #34d399;">57 Ay (2022-2026)</div>
          <div class="subtext">
            Zaman Dilimleri: <b>5m, 15m, 1h, 4h, 1d</b> (285 Parquet Dosyası)<br>
            Durum: <b style="color:#6ee7b7">Bileşenler İmaj İçinde Hazır</b>
          </div>
        </div>

        <div class="card">
          <h3>Depolama & Kanıt Arşivi</h3>
          <div class="value" id="ops-storage-mb" style="font-size: 20px;">- MB</div>
          <div class="subtext">
            İndekslenen Kanıt Dosyası: <b id="ops-artifacts-count">550+</b><br>
            Ağ İzolasyonu: <b>127.0.0.1:8080 (Loopback Korumalı)</b>
          </div>
        </div>
      </div>

      <!-- Section B: Historical Test Environments (WSL2 disk benchmarks) -->
      <div class="section-header">
        <div class="section-title"><span>🧪</span> Geçmiş Test ve Sanallaştırma Ortamı (Windows WSL2 VHDX)</div>
        <span class="badge badge-info">SENTETİK BENCHMARK ARŞİVİ</span>
      </div>

      <div class="card" style="margin-bottom: 24px; border-left: 4px solid #8b5cf6;">
        <h3 style="color: #c084fc;">WINDOWS 11 / WSL2 SENTETİK BENCHMARK GEÇMİŞİ</h3>
        <p style="font-size: 13px; color: #d1d5db; line-height: 1.6; margin-top: 6px;">
          Önceki sprint raporlarında belgelenen 5 adet disk benchmark hatası, sanallaştırılmış Windows WSL2 VHDX disk alt sistemindeki
          (Windows <code>FlushFileBuffers</code> kuyruk gecikmesi) sentetik 10.000 olaylık ardışık fsync testlerine aittir.
        </p>
        <div class="subtext" style="margin-top: 8px; font-size: 12px;">
          Linux VPS Üretim/Staging Etkisi: <b style="color: #34d399;">SIFIR (0)</b> &bull;
          Fonksiyonel Hata: <b style="color: #34d399;">YOK</b> &bull;
          Uygulama Mantığı: <b style="color: #34d399;">%100 SAĞLIKLI</b>
        </div>
      </div>

      <!-- Section C: Model Integrity & Security Latch -->
      <div class="section-header">
        <div class="section-title"><span>🛡️</span> Model Bütünlüğü ve Yönetişim Kontratı</div>
      </div>

      <div class="table-container">
        <table>
          <thead>
            <tr>
              <th>Özellik</th>
              <th>Mevcut Durum</th>
              <th>Açıklama</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><strong>Model Sürümü</strong></td>
              <td><code>CBE-0.7.0</code> (FROZEN)</td>
              <td>29 kanonik araştırma bileşeni SHA-256 ile kilitlendi.</td>
            </tr>
            <tr>
              <td><strong>Teknik Karar</strong></td>
              <td><span class="badge badge-danger">TECHNICAL NO-GO</span></td>
              <td>Canlı borsa emir iletimi politik ve teknik olarak yasaktır.</td>
            </tr>
            <tr>
              <td><strong>Yönetişim Yetkisi</strong></td>
              <td><span class="badge badge-warn">NOT_GRANTED</span></td>
              <td>Operatör üretim anahtarı yayınlanmamıştır.</td>
            </tr>
            <tr>
              <td><strong>Gerçek Borsa Ağ Erişimi</strong></td>
              <td><span class="badge badge-danger">DEVRE DIŞI (DISABLED)</span></td>
              <td>Tüm veri analitiği çevrimdışı arşivler üzerinden yürütülür.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

  </main>

  <!-- Global Preview Modal -->
  <div id="preview-modal" class="modal-overlay" onclick="closeModalOnOverlay(event)" role="dialog" aria-modal="true">
    <div class="modal-window">
      <div class="modal-header">
        <h4 id="modal-title">Dosya Önizleme</h4>
        <button class="btn" onclick="closeModal()" aria-label="Kapat">✕</button>
      </div>
      <div class="modal-body" id="modal-content">Yükleniyor...</div>
      <div class="modal-footer">
        <span id="modal-meta">-</span>
        <button class="btn" onclick="closeModal()">Kapat</button>
      </div>
    </div>
  </div>

  <!-- Global Footer -->
  <footer class="app-footer" role="contentinfo">
    <div>
      <strong>CBE-0.7.0 Dondurulmuş Model</strong> | Build: <code class="dyn-git-rev-short">69027de4</code> | Canlı Alım-Satım Kesinlikle Yasaktır.
    </div>
    <div>
      Çevrimdışı Araştırma &bull; Kanonik Parquet Arşivi &bull; Ed25519 RFC 8032
    </div>
  </footer>

  <!-- Client-side Zero-Dependency JavaScript Controller -->
  <script>
    let currentTab = "overview";
    let researchData = [];
    let macroData = [];
    let macroCategory = "ALL";
    let artifactsData = [];
    let artifactsPage = 1;
    let artifactsLimit = 25;
    let selectedResearchCat = "all";
    let selectedArtifactExt = "all";

    // Candlestick State
    let candleInterval = '1h';
    let candleMonth = '2026-09';
    let candleLimit = 100;
    let candleOffset = 0;
    let candlesData = [];
    let candleEventMarkers = [];
    let candleMonthsList = [];
    let showEventMarkers = true;
    let crosshairPos = null;
    let currentAnalogData = null;

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
      if (tabId === "overview") {
        loadOverview();
        setTimeout(() => { initCandleCanvasEvents(); drawCandlestickChart(); }, 60);
      } else if (tabId === "behavior") {
        loadBehavior();
        setTimeout(() => { initCandleCanvasEvents(); drawCandlestickChart(); if (currentAnalogData) drawAnalogTrajectoryChart(currentAnalogData); }, 60);
      } else if (tabId === "events" && macroData.length === 0) {
        loadMacroReactions();
      } else if (tabId === "research" && researchData.length === 0) {
        loadResearch();
      } else if (tabId === "artifacts" && artifactsData.length === 0) {
        loadArtifacts();
      } else if (tabId === "operations") {
        loadOperations();
      }
    }

    function refreshCurrentTab() {
      if (currentTab === "overview") { loadOverview(); loadHistoricalCandles(); }
      else if (currentTab === "behavior") { loadBehavior(); }
      else if (currentTab === "events") { loadMacroReactions(); }
      else if (currentTab === "research") { loadResearch(); }
      else if (currentTab === "artifacts") { loadArtifacts(); }
      else if (currentTab === "operations") { loadOperations(); }
    }

    // Module 1: Overview
    async function loadOverview() {
      try {
        const res = await fetch("/api/v1/product/overview");
        if (!res.ok) return;
        const data = await res.json();

        // Update dynamic git commit
        if (data.git_revision) {
          const rev = data.git_revision;
          const shortRev = rev.substring(0, 8);
          document.querySelectorAll(".dyn-git-rev").forEach(el => el.innerText = rev);
          document.querySelectorAll(".dyn-git-rev-short").forEach(el => el.innerText = shortRev);
        }
      } catch (e) {
        console.warn("Overview fetch error:", e);
      }
    }

    // Candlestick Chart Engine
    function setCandleInterval(intv, btn) {
      candleInterval = intv;
      candleOffset = 0;
      document.querySelectorAll(".pill-btn").forEach(b => {
        if (['5m', '15m', '1h', '4h', '1d'].includes(b.innerText.trim())) {
          b.classList.remove("active");
        }
      });
      if (btn) btn.classList.add("active");
      loadHistoricalCandles();
    }

    function changeCandleMonth(m) {
      candleMonth = m;
      candleOffset = 0;
      // Sync both dropdowns if present
      const sel1 = document.getElementById("candle-month-select");
      const sel2 = document.getElementById("candle-month-select-2");
      if (sel1) sel1.value = m;
      if (sel2) sel2.value = m;
      loadHistoricalCandles();
    }

    function changeCandleLimit(lim) {
      candleLimit = parseInt(lim);
      candleOffset = 0;
      const sel1 = document.getElementById("candle-limit-select");
      const sel2 = document.getElementById("candle-limit-select-2");
      if (sel1) sel1.value = lim;
      if (sel2) sel2.value = lim;
      loadHistoricalCandles();
    }

    function panCandles(delta) {
      candleOffset = Math.max(0, candleOffset + delta);
      loadHistoricalCandles();
    }

    function resetCandleZoom() {
      candleLimit = 100;
      candleOffset = 0;
      loadHistoricalCandles();
    }

    function toggleEventOverlay(checked) {
      showEventMarkers = checked;
      const cb1 = document.getElementById("toggle-events-overlay");
      const cb2 = document.getElementById("toggle-events-overlay-2");
      if (cb1) cb1.checked = checked;
      if (cb2) cb2.checked = checked;
      drawCandlestickChart();
    }

    async function loadHistoricalCandles() {
      showCandleStatus("Veriler yükleniyor...");
      try {
        const res = await fetch(`/api/v1/product/historical-candles?interval=${candleInterval}&month=${candleMonth}&limit=${candleLimit}&offset=${candleOffset}`);
        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          showCandleStatus(errData.message || `Veri dosyasına erişilemiyor (HTTP ${res.status})`, true);
          return;
        }
        const data = await res.json();
        candlesData = data.candles || [];
        candleEventMarkers = data.event_markers || [];

        // Update month select options if changed
        if (data.available_months && JSON.stringify(data.available_months) !== JSON.stringify(candleMonthsList)) {
          candleMonthsList = data.available_months;
          const optionsHtml = candleMonthsList.slice().reverse().map(m => `
            <option value="${m}" ${m === data.month ? 'selected' : ''}>${m}</option>
          `).join("");
          const sel1 = document.getElementById("candle-month-select");
          const sel2 = document.getElementById("candle-month-select-2");
          if (sel1) sel1.innerHTML = optionsHtml;
          if (sel2) sel2.innerHTML = optionsHtml;
        }

        if (candlesData.length > 0) {
          updateCandleHUD(candlesData[candlesData.length - 1]);
        }
        drawCandlestickChart();
      } catch (e) {
        showCandleStatus("Grafik servisi yanıt vermiyor: " + e, true);
      }
    }

    function showCandleStatus(msg, isError = false) {
      const getActiveCanvas = () => {
        if (currentTab === "overview") return document.getElementById("candlestick-canvas");
        return document.getElementById("candlestick-canvas-2") || document.getElementById("candlestick-canvas");
      };
      const canvas = getActiveCanvas();
      if (!canvas) return;
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth || 800;
      const h = canvas.clientHeight || 420;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      const ctx = canvas.getContext("2d");
      ctx.scale(dpr, dpr);
      ctx.fillStyle = "#070b13";
      ctx.fillRect(0, 0, w, h);
      ctx.fillStyle = isError ? "#f87171" : "#94a3b8";
      ctx.font = "14px monospace";
      ctx.textAlign = "center";
      ctx.fillText(msg, w / 2, h / 2 - 10);
      if (isError) {
        ctx.fillStyle = "#38bdf8";
        ctx.font = "12px sans-serif";
        ctx.fillText("Lütfen üst menüden geçerli bir dönem seçin veya 'Yenile'ye tıklayın.", w / 2, h / 2 + 16);
      }
    }

    function updateCandleHUD(c) {
      if (!c) return;
      const setBoth = (id1, id2, val) => {
        const el1 = document.getElementById(id1); if (el1) el1.innerText = val;
        const el2 = document.getElementById(id2); if (el2) el2.innerText = val;
      };
      const dtStr = c.datetime_utc.replace("T", " ").replace("Z", " UTC");
      const fmtMoney = (n) => "$" + n.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2});
      setBoth("hud-time", "hud-time-2", dtStr);
      setBoth("hud-open", "hud-open-2", fmtMoney(c.open));
      setBoth("hud-high", "hud-high-2", fmtMoney(c.high));
      setBoth("hud-low", "hud-low-2", fmtMoney(c.low));
      setBoth("hud-close", "hud-close-2", fmtMoney(c.close));
      setBoth("hud-volume", "hud-volume-2", c.volume.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2}) + " BTC");

      const updateRegimeBadge = (id) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.innerText = c.regime;
        el.className = "badge " + (c.regime.includes("BULL") ? "badge-success" : (c.regime.includes("BEAR") ? "badge-danger" : "badge-info"));
      };
      updateRegimeBadge("hud-regime");
      updateRegimeBadge("hud-regime-2");
    }

    function drawCandlestickChart() {
      const getActiveContainer = () => {
        if (currentTab === "overview") return document.getElementById("candle-canvas-container");
        return document.getElementById("candle-canvas-container-2") || document.getElementById("candle-canvas-container");
      };
      const container = getActiveContainer();
      if (!container) return;
      const canvas = container.querySelector("canvas");
      if (!canvas) return;

      const dpr = window.devicePixelRatio || 1;
      const w = container.clientWidth || 800;
      const h = container.clientHeight || 420;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      const ctx = canvas.getContext("2d");
      ctx.scale(dpr, dpr);

      // Background
      ctx.fillStyle = "#070b13";
      ctx.fillRect(0, 0, w, h);

      if (!candlesData || candlesData.length === 0) {
        showCandleStatus("Bu tarih aralığında veri bulunamadı.");
        return;
      }

      const padTop = 22;
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

      // 4. Macro Event Pins Overlay
      if (showEventMarkers && candleEventMarkers && candleEventMarkers.length > 0) {
        // Map interval to ms
        const intvMs = { '5m': 300000, '15m': 900000, '1h': 3600000, '4h': 14400000, '1d': 86400000 }[candleInterval] || 3600000;
        candleEventMarkers.forEach(evt => {
          // Find matching candle index
          const cIdx = candlesData.findIndex(c => evt.timestamp_ms >= c.open_time_ms && evt.timestamp_ms < (c.open_time_ms + intvMs));
          if (cIdx >= 0) {
            const c = candlesData[cIdx];
            const xCenter = padLeft + cIdx * barW + barW / 2;
            const yHigh = padTop + (maxP - c.high) / effRange * priceH;

            // Draw pin icon
            ctx.font = "14px sans-serif";
            ctx.textAlign = "center";
            ctx.fillText(evt.icon || "📌", xCenter, Math.max(16, yHigh - 8));
          }
        });
      }

      // 5. Time labels on bottom
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

      // 6. Crosshair if mouse hover
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

    // Canvas Events Binding
    function initCandleCanvasEvents() {
      const canvases = [document.getElementById("candlestick-canvas"), document.getElementById("candlestick-canvas-2")];
      canvases.forEach(canvas => {
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

        // Mouse Wheel Zoom
        canvas.addEventListener("wheel", (e) => {
          e.preventDefault();
          if (e.deltaY < 0) {
            // Zoom in
            candleLimit = Math.max(25, candleLimit - 15);
          } else {
            // Zoom out
            candleLimit = Math.min(500, candleLimit + 15);
          }
          loadHistoricalCandles();
        }, { passive: false });
      });
    }

    // Module 3: Market Behavior & Analog Explorer
    async function loadBehavior() {
      // 1. Load Market Regimes & Transitions
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
      const w = container.clientWidth || 400;
      const h = container.clientHeight || 340;
      canvas.width = w * dpr;
      canvas.height = h * dpr;
      const ctx = canvas.getContext("2d");
      ctx.scale(dpr, dpr);

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

      // Gridlines & 0% baseline
      ctx.strokeStyle = "rgba(31, 41, 55, 0.6)";
      ctx.lineWidth = 1;
      const yZero = padTop + (maxRet - 0.0) / effRetRange * chartH;

      ctx.beginPath();
      ctx.strokeStyle = "rgba(148, 163, 184, 0.4)";
      ctx.setLineDash([4, 4]);
      ctx.moveTo(padLeft, yZero);
      ctx.lineTo(w - padRight, yZero);
      ctx.stroke();
      ctx.setLineDash([]);

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

      ctx.fillStyle = "#64748b";
      ctx.font = "10px monospace";
      ctx.textAlign = "right";
      [minRet, 0, maxRet].forEach(val => {
        const y = padTop + (maxRet - val) / effRetRange * chartH;
        ctx.fillText((val >= 0 ? "+" : "") + val.toFixed(1) + "%", padLeft - 6, y + 3);
      });

      // Dispersion corridor
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

      // Analog trajectory lines
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

    // Module 4: News & Macro Research
    async function loadMacroReactions() {
      try {
        const res = await fetch(`/api/v1/product/macro-reactions?category=${macroCategory}&limit=100`);
        if (!res.ok) return;
        const data = await res.json();
        macroData = data.events || [];
        renderMacroTable(macroData);
      } catch (e) {
        console.warn("Macro reactions fetch error:", e);
      }
    }

    function setMacroCat(cat, btn) {
      macroCategory = cat;
      document.querySelectorAll("#module-events .pill-btn").forEach(b => b.classList.remove("active"));
      if (btn) btn.classList.add("active");
      loadMacroReactions();
    }

    function filterMacroReactions() {
      const q = (document.getElementById("macro-search")?.value || "").toLowerCase();
      const filtered = macroData.filter(e =>
        e.event_id.toLowerCase().includes(q) ||
        e.event_name.toLowerCase().includes(q) ||
        (e.issuing_organization && e.issuing_organization.toLowerCase().includes(q))
      );
      renderMacroTable(filtered);
    }

    function renderMacroTable(list) {
      const tBody = document.getElementById("macro-tbody");
      if (!tBody) return;
      if (list.length === 0) {
        tBody.innerHTML = '<tr><td colspan="9" style="text-align:center; color:var(--text-muted); padding:20px;">Kayıt bulunamadı.</td></tr>';
        return;
      }
      tBody.innerHTML = list.map(e => {
        const fmtRet = (r) => `<span class="${r >= 0 ? 'ret-pos' : 'ret-neg'}">${r >= 0 ? '+' : ''}${r.toFixed(2)}%</span>`;
        return `
          <tr>
            <td><code>${e.event_id}</code></td>
            <td><span class="badge badge-info">${e.event_category}</span></td>
            <td>${e.published_at_utc.substring(0, 16).replace("T", " ")}</td>
            <td>${e.issuing_organization || '-'}</td>
            <td>${e.icon || ''} <strong>${e.event_name}</strong></td>
            <td>$${e.exec_open_price.toLocaleString("en-US", {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
            <td>${fmtRet(e.ret_post_15m_pct)}</td>
            <td>${fmtRet(e.ret_post_1h_pct)}</td>
            <td>${fmtRet(e.ret_post_24h_pct)}</td>
          </tr>
        `;
      }).join("");

      const pageInfo = document.getElementById("macro-page-info");
      if (pageInfo) pageInfo.innerText = `Toplam ${list.length} Denetlenmiş Makro Olay Gösteriliyor`;
    }

    // Module 2: Research Results
    async function loadResearch() {
      try {
        const res = await fetch("/api/v1/product/research-results");
        if (!res.ok) return;
        const data = await res.json();
        researchData = data.results || [];
        filterResearch();
      } catch (e) {
        console.warn("Research fetch error:", e);
      }
    }

    function setResearchCat(cat, btn) {
      selectedResearchCat = cat;
      document.querySelectorAll("#module-research .pill-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      filterResearch();
    }

    function filterResearch() {
      const q = (document.getElementById("research-search")?.value || "").toLowerCase();
      const container = document.getElementById("research-cards-container");
      if (!container) return;

      let list = researchData;
      if (selectedResearchCat !== "all") {
        list = list.filter(r => r.topic.toLowerCase().includes(selectedResearchCat.toLowerCase()));
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

    // Module 6: Artifacts Browser
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

    // Module 7: Operations & System Status
    async function loadOperations() {
      try {
        const res = await fetch("/api/v1/product/operations");
        if (!res.ok) return;
        const data = await res.json();

        // Dynamic git commit update
        if (data.git_revision) {
          const rev = data.git_revision;
          const shortRev = rev.substring(0, 8);
          document.querySelectorAll(".dyn-git-rev").forEach(el => el.innerText = rev);
          document.querySelectorAll(".dyn-git-rev-short").forEach(el => el.innerText = shortRev);
        }

        const sEl = document.getElementById("ops-storage-mb");
        if (sEl && data.storage_status) {
          sEl.innerText = (data.storage_status.research_outputs_mb + data.storage_status.data_directory_mb).toFixed(1) + " MB";
        }
        const aEl = document.getElementById("ops-artifacts-count");
        if (aEl && data.storage_status) {
          aEl.innerText = data.storage_status.artifacts_indexed_count;
        }
        const rEl = document.getElementById("ops-runtime-platform");
        if (rEl && data.runtime_platform) {
          rEl.innerText = data.runtime_platform.toUpperCase();
        }
        const pEl = document.getElementById("ops-python-ver");
        if (pEl && data.python_version) {
          pEl.innerText = data.python_version;
        }
        const mEl = document.getElementById("ops-memory-rss");
        if (mEl && data.memory_usage_mb) {
          mEl.innerText = data.memory_usage_mb + " MB";
        }
        const uEl = document.getElementById("ops-uptime");
        if (uEl && data.uptime_seconds) {
          uEl.innerText = data.uptime_seconds + " sn";
        }
      } catch (e) {
        console.warn("Operations fetch error:", e);
      }
    }

    // Window Init & Resize Listeners
    window.addEventListener("DOMContentLoaded", () => {
      const hash = window.location.hash.replace("#", "");
      if (hash && ["overview", "research", "behavior", "events", "governance", "artifacts", "operations"].includes(hash)) {
        switchTab(hash);
      } else {
        switchTab("overview");
      }
      initCandleCanvasEvents();
      loadHistoricalCandles();
    });

    window.addEventListener("resize", () => {
      drawCandlestickChart();
      if (currentAnalogData) drawAnalogTrajectoryChart(currentAnalogData);
    });
  </script>
</body>
</html>
"""


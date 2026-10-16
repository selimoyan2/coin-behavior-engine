"""Market Intelligence MVP UI HTML Renderer and Static Asset Server.

Provides isolated frontend prototype rendering for the CBE Market Intelligence
module, consuming Sprint 10.03 read-only API endpoints under /api/v1/intelligence/.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).resolve().parents[1] / "web" / "static" / "intelligence"
CSS_PATH = STATIC_DIR / "style.css"
JS_PATH = STATIC_DIR / "client.js"


def get_intelligence_css() -> str:
    """Read the CSS file for Market Intelligence."""
    if CSS_PATH.exists():
        return CSS_PATH.read_text(encoding="utf-8")
    return "/* CSS file not found */"


def get_intelligence_js() -> str:
    """Read the client adapter JS for Market Intelligence."""
    if JS_PATH.exists():
        return JS_PATH.read_text(encoding="utf-8")
    return "// JS file not found"


def render_intelligence_ui_html(inline_assets: bool = False) -> str:
    """Generate clean, accessible, modern Market Intelligence UI HTML.

    Args:
        inline_assets: If True, inlines CSS and JS directly into the HTML document
                       to support standalone zero-dependency file viewing or testing.
                       If False, links to /intelligence/style.css and /intelligence/client.js.
    """
    if inline_assets:
        style_tag = f"<style>\n{get_intelligence_css()}\n</style>"
        script_tag = f"<script>\n{get_intelligence_js()}\n</script>"
    else:
        style_tag = '<link rel="stylesheet" href="/intelligence/style.css">'
        script_tag = '<script src="/intelligence/client.js" defer></script>'

    return f"""<!DOCTYPE html>
<html lang="tr">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CBE Piyasa İstihbarat Portalı (Market Intelligence MVP)</title>
  <meta name="description" content="Coin Behavior Engine kanıta duyarlı, salt-okunur piyasa istihbaratı ve belirsizlik teşhisleri.">
  {style_tag}
</head>
<body>
  <header class="app-header">
    <div class="brand-section">
      <div class="brand-title">
        <span>⚡</span> Coin Behavior Engine
      </div>
      <span class="brand-badge">Market Intelligence MVP</span>
    </div>
    <div class="header-controls">
      <div style="font-size: 12px; color: var(--text-muted); font-family: var(--font-mono);">
        API: /api/v1/intelligence/
      </div>
      <button id="btn-refresh" class="btn-refresh" type="button" aria-label="Verileri Yenile">
        <span>🔄</span> Yenile
      </button>
    </div>
  </header>

  <main class="container">
    <div id="intelligence-root">
      <div class="state-container">
        <div class="spinner"></div>
        <div class="state-title">Piyasa İstihbarat Paneli Yükleniyor...</div>
        <div class="state-desc">Bağlantı kuruluyor: /api/v1/intelligence/</div>
      </div>
    </div>
  </main>

  <footer class="app-footer">
    <div>
      <strong>CBE-0.7.0 Dondurulmuş Model</strong> | APPROVAL4 = FALSE | Alım-satım ve canlı skorlama devre dışıdır.
    </div>
    <div>
      Salt-Okunur Piyasa İstihbarat Arayüzü &copy; 2026 Coin Behavior Engine
    </div>
  </footer>

  {script_tag}
</body>
</html>
"""

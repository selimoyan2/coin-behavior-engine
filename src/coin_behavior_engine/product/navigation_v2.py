"""Navigation System V2 — Module Discoverability, Horizontal Overflow Remediation & Accessible UX.

Sprint ID: CBE_SPRINT38_DASHBOARD_V15_EVIDENCE_EXPLORER
Repository: selimoyan2/coin-behavior-engine
Canonical Model: CBE-0.7.0 (STRICTLY_FROZEN)

Provides:
- Central Module Registry (MODULE_REGISTRY) with all metadata:
  id, name, group, group_name, hash, enabled, auth_required, order, icon, description.
- Visible horizontal scroll controls (Left/Right arrows with auto-hide/disable).
- Auto-scroll active tab into view (smooth centering for direct hash/route landings).
- "Diğer Modüller" (More Modules) accessible dropdown menu with categorized items.
- Full keyboard accessibility (Tab, Arrow keys, Enter/Space, focus-visible, ARIA roles).
"""

from __future__ import annotations

import json
from typing import Any, Dict, List

MODULE_REGISTRY: List[Dict[str, Any]] = [
    # Piyasa Araştırması (market)
    {
        "id": "overview",
        "name": "Araştırma Alanı",
        "icon": "🔬",
        "group": "market",
        "group_name": "Piyasa Araştırması",
        "hash": "#overview",
        "enabled": True,
        "auth_required": False,
        "order": 10,
        "description": "BTCUSDT 59 aylık tarihsel mum grafiği, rejim tespiti ve temel metrikler.",
    },
    {
        "id": "predictive-validity",
        "name": "Tahmin Geçerliliği",
        "icon": "🎯",
        "group": "market",
        "group_name": "Piyasa Araştırması",
        "hash": "#predictive-validity",
        "enabled": True,
        "auth_required": False,
        "order": 20,
        "description": "Piyasa rejimlerinin ileri dönem volatilite, risk ve fiyat davranışıyla ilişkilerini bilimsel olarak inceleyin.",
    },
    {
        "id": "behavior",
        "name": "Piyasa Davranışı",
        "icon": "📈",
        "group": "market",
        "group_name": "Piyasa Araştırması",
        "hash": "#behavior",
        "enabled": True,
        "auth_required": False,
        "order": 30,
        "description": "Piyasa davranışı, analog döngüler ve fiyat dinamikleri inceleme alanı.",
    },
    {
        "id": "comparison",
        "name": "Karşılaştırma Laboratuvarı",
        "icon": "⚖️",
        "group": "market",
        "group_name": "Piyasa Araştırması",
        "hash": "#comparison",
        "enabled": True,
        "auth_required": False,
        "order": 40,
        "description": "Farklı rejim ve zaman dilimlerinin karşılaştırmalı analizi.",
    },
    {
        "id": "drift",
        "name": "Rejim Dağılım & Değişim",
        "icon": "🧬",
        "group": "market",
        "group_name": "Piyasa Araştırması",
        "hash": "#drift",
        "enabled": True,
        "auth_required": False,
        "order": 50,
        "description": "Rejim dağılımı, geçiş matrisleri ve olasılık değişimleri.",
    },
    {
        "id": "regimes",
        "name": "Rejim İstihbaratı",
        "icon": "🏛️",
        "group": "market",
        "group_name": "Piyasa Araştırması",
        "hash": "#regimes",
        "enabled": True,
        "auth_required": False,
        "order": 60,
        "description": "Piyasa rejimlerinin detaylı istatistiksel ve yapısal profilleri.",
    },
    {
        "id": "btc-timing",
        "name": "BTC Zamanlama Analitiği",
        "icon": "⏱️",
        "group": "market",
        "group_name": "Piyasa Araştırması",
        "hash": "#btc-timing",
        "enabled": True,
        "auth_required": False,
        "order": 70,
        "description": "BTC zamanlama araştırmaları, simülasyon ve walk-forward analizleri.",
    },
    {
        "id": "builder",
        "name": "Görsel Hipotez Oluşturucu",
        "icon": "🛠️",
        "group": "market",
        "group_name": "Piyasa Araştırması",
        "hash": "#builder",
        "enabled": True,
        "auth_required": False,
        "order": 80,
        "description": "Kullanıcı tanımlı hipotez kurgulama ve analiz aracı.",
    },
    {
        "id": "distribution",
        "name": "Dağılım Laboratuvarı",
        "icon": "📊",
        "group": "market",
        "group_name": "Piyasa Araştırması",
        "hash": "#distribution",
        "enabled": True,
        "auth_required": False,
        "order": 90,
        "description": "Getiri dağılımları, basıklık ve çarpıklık incelemeleri.",
    },
    {
        "id": "unified-workspace",
        "name": "Birleşik Araştırma Alanı V1",
        "icon": "🔬",
        "group": "market",
        "group_name": "Piyasa Araştırması",
        "hash": "#unified-workspace",
        "enabled": True,
        "auth_required": False,
        "order": 100,
        "description": "Çok modüllü araştırma oturumu ve kanıt bütünleşmesi.",
    },
    {
        "id": "research-explorer",
        "name": "Araştırma İstihbarat Gezgini V1",
        "icon": "🔭",
        "group": "market",
        "group_name": "Piyasa Araştırması",
        "hash": "#research-explorer",
        "enabled": True,
        "auth_required": False,
        "order": 110,
        "description": "Araştırma kütüphanesi ve kanıt grafiği gezgini.",
    },
    {
        "id": "patterns",
        "name": "Tarihsel Örüntü Keşfi V2",
        "icon": "🔍",
        "group": "market",
        "group_name": "Piyasa Araştırması",
        "hash": "#patterns",
        "enabled": True,
        "auth_required": False,
        "order": 120,
        "description": "Geçmiş piyasa örüntülerinin aranması ve eşleştirilmesi.",
    },
    {
        "id": "studio",
        "name": "Olay Adli İnceleme",
        "icon": "🔬",
        "group": "market",
        "group_name": "Piyasa Araştırması",
        "hash": "#studio",
        "enabled": True,
        "auth_required": False,
        "order": 130,
        "description": "Özel piyasa olaylarının adli mikro-analizi.",
    },

    # Makro ve Senaryo (macro)
    {
        "id": "events",
        "name": "Makro Olaylar",
        "icon": "📰",
        "group": "macro",
        "group_name": "Makro ve Senaryo",
        "hash": "#events",
        "enabled": True,
        "auth_required": False,
        "order": 200,
        "description": "Makroekonomik duyurular ve piyasa tepki dinamikleri.",
    },
    {
        "id": "scenarios",
        "name": "Senaryo Laboratuvarı",
        "icon": "🧪",
        "group": "macro",
        "group_name": "Makro ve Senaryo",
        "hash": "#scenarios",
        "enabled": True,
        "auth_required": False,
        "order": 210,
        "description": "Stres testi senaryoları ve simüle edilmiş şok tepkileri.",
    },

    # Veri ve Raporlar (data)
    {
        "id": "quality",
        "name": "Veri Kapsamı & Kalite",
        "icon": "🛡️",
        "group": "data",
        "group_name": "Veri ve Raporlar",
        "hash": "#quality",
        "enabled": True,
        "auth_required": False,
        "order": 300,
        "description": "59 aylık Parquet veri seti bütünlüğü, mum kalitesi ve boşluk denetimi.",
    },
    {
        "id": "research",
        "name": "Araştırma Bulguları",
        "icon": "📊",
        "group": "data",
        "group_name": "Veri ve Raporlar",
        "hash": "#research",
        "enabled": True,
        "auth_required": False,
        "order": 310,
        "description": "Yürütülen araştırma döngülerinin ampirik özetleri.",
    },
    {
        "id": "reports",
        "name": "Araştırma Raporları",
        "icon": "📑",
        "group": "data",
        "group_name": "Veri ve Raporlar",
        "hash": "#reports",
        "enabled": True,
        "auth_required": False,
        "order": 320,
        "description": "Resmi araştırma kabul raporları ve PDF çıktıları.",
    },
    {
        "id": "robustness",
        "name": "Dayanıklılık Gezgini",
        "icon": "📐",
        "group": "data",
        "group_name": "Veri ve Raporlar",
        "hash": "#robustness",
        "enabled": True,
        "auth_required": False,
        "order": 330,
        "description": "Model duyarlılığı ve parametre dayanıklılık matrisi.",
    },
    {
        "id": "artifacts",
        "name": "Kanıt Arşivi",
        "icon": "📁",
        "group": "data",
        "group_name": "Veri ve Raporlar",
        "hash": "#artifacts",
        "enabled": True,
        "auth_required": False,
        "order": 340,
        "description": "Sistem tarafından üretilen imzalı kanıt dosyaları ve manifestolar.",
    },

    # Sistem Yönetimi (system)
    {
        "id": "operations",
        "name": "Sistem & Operasyon",
        "icon": "⚙️",
        "group": "system",
        "group_name": "Sistem Yönetimi",
        "hash": "#operations",
        "enabled": True,
        "auth_required": False,
        "order": 400,
        "description": "Çalışma zamanı durumu, sunucu sağlığı ve kaynak kullanımı.",
    },
    {
        "id": "governance",
        "name": "Yönetişim & Güvenlik",
        "icon": "🔐",
        "group": "system",
        "group_name": "Sistem Yönetimi",
        "hash": "#governance",
        "enabled": True,
        "auth_required": False,
        "order": 410,
        "description": "Model dondurma durumu, alım-satım yasağı ve güvenlik denetimleri.",
    },
    {
        "id": "evidence",
        "name": "Kanıt & Çoğaltım Merkezi",
        "icon": "🛡️",
        "group": "system",
        "group_name": "Sistem Yönetimi",
        "hash": "#evidence",
        "enabled": True,
        "auth_required": False,
        "order": 420,
        "description": "Bilimsel çoğaltılabilirlik kanıtları ve doğrulama araçları.",
    },
]


def get_module_registry() -> List[Dict[str, Any]]:
    """Return the official registered list of CBE modules."""
    return sorted(MODULE_REGISTRY, key=lambda m: m["order"])


def render_navigation_system_v2_styles() -> str:
    """CSS styles for Navigation System V2 (scroll controls, dropdown, accessibility)."""
    return """
    /* ========================================================================= */
    /* NAVIGATION SYSTEM V2 — SCROLL CONTROLS, MORE MODULES & ACCESSIBILITY     */
    /* ========================================================================= */
    .nav-tabs-wrapper {
      position: relative;
      display: flex;
      align-items: center;
      background: #0b101c;
      border-bottom: 1px solid var(--border);
      padding: 0 4px;
      width: 100%;
      box-sizing: border-box;
      z-index: 100;
    }

    .nav-scroll-btn {
      flex: 0 0 32px;
      height: 38px;
      display: none; /* dynamically toggled */
      align-items: center;
      justify-content: center;
      background: rgba(15, 23, 42, 0.95);
      border: 1px solid #1e293b;
      color: #38bdf8;
      font-size: 20px;
      font-weight: 800;
      border-radius: 6px;
      cursor: pointer;
      z-index: 105;
      transition: all 0.2s ease;
      user-select: none;
      box-shadow: 0 2px 8px rgba(0, 0, 0, 0.4);
    }
    .nav-scroll-btn:hover:not(:disabled) {
      background: #1e293b;
      border-color: #38bdf8;
      color: #fff;
      transform: scale(1.05);
    }
    .nav-scroll-btn:disabled {
      opacity: 0.25;
      cursor: default;
      pointer-events: none;
    }
    #nav-scroll-left {
      margin-left: 4px;
      margin-right: 2px;
    }
    #nav-scroll-right {
      margin-left: 2px;
      margin-right: 4px;
    }

    /* Scrollable Tabs Bar */
    .nav-tabs {
      flex: 1 1 auto;
      display: flex;
      gap: 4px;
      padding: 0 6px;
      overflow-x: auto;
      white-space: nowrap;
      scrollbar-width: none; /* Firefox */
      -ms-overflow-style: none; /* IE/Edge */
      scroll-behavior: smooth;
      touch-action: pan-x;
      -webkit-overflow-scrolling: touch;
      border-bottom: none !important;
      background: transparent !important;
    }
    .nav-tabs::-webkit-scrollbar {
      display: none; /* Chrome/Safari */
    }

    /* Tab Button Styles */
    .nav-tab {
      padding: 11px 15px;
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
      user-select: none;
      flex-shrink: 0;
      border-radius: 4px 4px 0 0;
    }
    .nav-tab:hover {
      color: #fff;
      background: rgba(255, 255, 255, 0.04);
    }
    .nav-tab:focus-visible {
      outline: 2px solid #38bdf8;
      outline-offset: -2px;
    }
    .nav-tab.active {
      color: #38bdf8 !important;
      border-bottom-color: #38bdf8 !important;
      background: rgba(56, 189, 248, 0.12) !important;
      font-weight: 700 !important;
      box-shadow: inset 0 -2px 0 #38bdf8;
    }

    /* "Diğer Modüller" Dropdown Controls */
    .nav-more-wrapper {
      position: relative;
      flex: 0 0 auto;
      margin-left: 4px;
      margin-right: 6px;
      z-index: 110;
    }
    .nav-more-btn {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      background: #0f172a;
      border: 1px solid #334155;
      color: #94a3b8;
      font-size: 12px;
      font-weight: 600;
      padding: 7px 12px;
      border-radius: 6px;
      cursor: pointer;
      transition: all 0.2s ease;
      white-space: nowrap;
    }
    .nav-more-btn:hover, .nav-more-btn[aria-expanded="true"] {
      background: #1e293b;
      border-color: #38bdf8;
      color: #fff;
    }
    .nav-more-btn:focus-visible {
      outline: 2px solid #38bdf8;
      outline-offset: 1px;
    }
    .nav-more-arrow {
      font-size: 10px;
      transition: transform 0.2s ease;
    }
    .nav-more-btn[aria-expanded="true"] .nav-more-arrow {
      transform: rotate(180deg);
    }

    .nav-more-dropdown {
      position: absolute;
      top: calc(100% + 6px);
      right: 0;
      width: 360px;
      max-width: 90vw;
      max-height: 480px;
      overflow-y: auto;
      background: #0b1329;
      border: 1px solid #1e3a8a;
      border-radius: 8px;
      box-shadow: 0 12px 32px rgba(0, 0, 0, 0.7);
      padding: 8px 0;
      z-index: 120;
      display: none;
    }
    .nav-more-dropdown.open {
      display: block !important;
    }
    .nav-dropdown-group-header {
      padding: 8px 14px 4px;
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #64748b;
      border-top: 1px solid #1e293b;
      margin-top: 6px;
    }
    .nav-dropdown-group-header:first-child {
      border-top: none;
      margin-top: 0;
    }
    .nav-dropdown-item {
      display: flex;
      flex-direction: column;
      padding: 8px 14px;
      color: #cbd5e1;
      text-decoration: none;
      cursor: pointer;
      transition: background 0.15s ease;
      border-left: 3px solid transparent;
    }
    .nav-dropdown-item:hover, .nav-dropdown-item:focus-visible {
      background: #1e293b;
      color: #fff;
      border-left-color: #38bdf8;
      outline: none;
    }
    .nav-dropdown-item.active {
      background: rgba(56, 189, 248, 0.1);
      border-left-color: #38bdf8;
      color: #38bdf8;
      font-weight: 700;
    }
    .nav-dropdown-item-title {
      display: flex;
      align-items: center;
      gap: 6px;
      font-size: 13px;
      font-weight: 600;
    }
    .nav-dropdown-item-desc {
      font-size: 11px;
      color: #94a3b8;
      margin-top: 3px;
      line-height: 1.35;
    }

    @media (max-width: 768px) {
      .nav-tabs-wrapper { padding: 0 2px; }
      .nav-tab { padding: 8px 10px; font-size: 11px; gap: 4px; }
      .nav-scroll-btn { flex: 0 0 24px; height: 32px; font-size: 16px; }
      .nav-more-wrapper { margin-left: 2px; margin-right: 2px; }
      .nav-more-btn { padding: 6px 8px; font-size: 11px; }
      .nav-more-text { display: none; } /* Hide label on mobile to maximize scrollable area */
      .nav-more-dropdown { width: 290px; }
    }
    """


def render_more_modules_dropdown_html() -> str:
    """Generate categorized HTML items for the Diğer Modüller dropdown."""
    groups = [
        ("market", "📈 Piyasa Araştırması"),
        ("macro", "📰 Makro ve Senaryo"),
        ("data", "📑 Veri ve Raporlar"),
        ("system", "🛡️ Sistem Yönetimi"),
    ]
    html_parts = []
    for grp_id, grp_title in groups:
        mods = [m for m in get_module_registry() if m["group"] == grp_id and m["enabled"]]
        if not mods:
            continue
        html_parts.append(f'<div class="nav-dropdown-group-header">{grp_title}</div>')
        for m in mods:
            html_parts.append(f"""
            <a class="nav-dropdown-item" id="dropdown-item-{m['id']}" onclick="navigateFromMenu('{m['id']}')" role="menuitem" tabindex="0">
              <div class="nav-dropdown-item-title">
                <span>{m['icon']}</span>
                <span>{m['name']}</span>
              </div>
              <div class="nav-dropdown-item-desc">{m['description']}</div>
            </a>
            """)
    return "".join(html_parts)


def render_navigation_system_v2_scripts() -> str:
    """Render JavaScript runtime for Navigation System V2."""
    registry_json = json.dumps(get_module_registry(), ensure_ascii=False)
    return f"""
    // =========================================================================
    // NAVIGATION SYSTEM V2 RUNTIME JAVASCRIPT
    // =========================================================================
    window.MODULE_REGISTRY = {registry_json};

    function updateNavScrollArrows() {{
      const nav = document.getElementById("main-nav-tabs") || document.querySelector(".nav-tabs");
      const leftBtn = document.getElementById("nav-scroll-left");
      const rightBtn = document.getElementById("nav-scroll-right");
      if (!nav || !leftBtn || !rightBtn) return;

      const hasOverflow = nav.scrollWidth > nav.clientWidth + 4;
      if (!hasOverflow) {{
        leftBtn.style.display = "none";
        rightBtn.style.display = "none";
        return;
      }}

      leftBtn.style.display = "flex";
      rightBtn.style.display = "flex";

      const isAtStart = nav.scrollLeft <= 4;
      const isAtEnd = Math.ceil(nav.scrollLeft + nav.clientWidth) >= nav.scrollWidth - 4;

      leftBtn.disabled = isAtStart;
      leftBtn.style.opacity = isAtStart ? "0.25" : "1";
      leftBtn.style.cursor = isAtStart ? "default" : "pointer";

      rightBtn.disabled = isAtEnd;
      rightBtn.style.opacity = isAtEnd ? "0.25" : "1";
      rightBtn.style.cursor = isAtEnd ? "default" : "pointer";
    }}

    function scrollNavTabs(direction) {{
      const nav = document.getElementById("main-nav-tabs") || document.querySelector(".nav-tabs");
      if (!nav) return;
      const scrollStep = Math.max(220, Math.floor(nav.clientWidth * 0.65));
      const delta = direction === "left" ? -scrollStep : scrollStep;
      nav.scrollBy({{ left: delta, behavior: "smooth" }});
      setTimeout(updateNavScrollArrows, 320);
    }}

    function scrollTabIntoView(tabBtn) {{
      if (!tabBtn) return;
      const nav = document.getElementById("main-nav-tabs") || document.querySelector(".nav-tabs");
      if (!nav) return;

      // Determine center position
      const navWidth = nav.clientWidth;
      const tabLeft = tabBtn.offsetLeft;
      const tabWidth = tabBtn.offsetWidth;
      const targetScrollLeft = tabLeft - (navWidth / 2) + (tabWidth / 2);

      nav.scrollTo({{
        left: Math.max(0, targetScrollLeft),
        behavior: "smooth"
      }});

      setTimeout(updateNavScrollArrows, 350);
    }}

    function toggleMoreModulesMenu(e) {{
      if (e) e.stopPropagation();
      const menu = document.getElementById("menu-more-modules");
      const btn = document.getElementById("btn-more-modules");
      if (!menu || !btn) return;
      const isOpen = menu.classList.contains("open");
      if (isOpen) {{
        closeMoreModulesMenu();
      }} else {{
        menu.classList.add("open");
        btn.setAttribute("aria-expanded", "true");
        // Highlight active item in dropdown
        const activeTab = window.currentTab || "overview";
        document.querySelectorAll(".nav-dropdown-item").forEach(el => {{
          el.classList.remove("active");
        }});
        const activeItem = document.getElementById("dropdown-item-" + activeTab);
        if (activeItem) activeItem.classList.add("active");
      }}
    }}

    function closeMoreModulesMenu() {{
      const menu = document.getElementById("menu-more-modules");
      const btn = document.getElementById("btn-more-modules");
      if (menu) menu.classList.remove("open");
      if (btn) btn.setAttribute("aria-expanded", "false");
    }}

    function navigateFromMenu(modId) {{
      closeMoreModulesMenu();
      if (typeof switchTab === "function") {{
        switchTab(modId);
      }}
    }}

    // Global click listener to close dropdown on click outside
    document.addEventListener("click", (e) => {{
      const wrapper = document.querySelector(".nav-more-wrapper");
      if (wrapper && !wrapper.contains(e.target)) {{
        closeMoreModulesMenu();
      }}
    }});

    // Keyboard support: Escape closes menu
    document.addEventListener("keydown", (e) => {{
      if (e.key === "Escape") {{
        closeMoreModulesMenu();
      }}
    }});

    // Enhance switchTab to support Navigation System V2
    const _originalSwitchTab = window.switchTab;
    window.switchTab = function(tabId) {{
      // Call original switchTab if present
      if (typeof _originalSwitchTab === "function") {{
        _originalSwitchTab(tabId);
      }}

      // Update ARIA attributes
      document.querySelectorAll(".nav-tab").forEach(t => {{
        t.setAttribute("aria-selected", "false");
      }});
      const activeBtn = document.getElementById("tab-btn-" + tabId);
      if (activeBtn) {{
        activeBtn.classList.add("active");
        activeBtn.setAttribute("aria-selected", "true");
        scrollTabIntoView(activeBtn);
      }}

      // Sync dropdown active item
      document.querySelectorAll(".nav-dropdown-item").forEach(item => {{
        item.classList.remove("active");
      }});
      const dropItem = document.getElementById("dropdown-item-" + tabId);
      if (dropItem) dropItem.classList.add("active");

      // Update scroll arrows
      setTimeout(updateNavScrollArrows, 350);
    }};

    // Setup events on DOMContentLoaded
    function initNavigationSystemV2() {{
      const nav = document.getElementById("main-nav-tabs") || document.querySelector(".nav-tabs");
      if (nav) {{
        // Mouse wheel horizontal scroll
        nav.addEventListener("wheel", (e) => {{
          if (e.deltaY !== 0) {{
            e.preventDefault();
            nav.scrollLeft += e.deltaY;
            updateNavScrollArrows();
          }}
        }}, {{ passive: false }});

        // Scroll event listener
        nav.addEventListener("scroll", updateNavScrollArrows);

        // Keyboard arrow navigation on tabs
        nav.addEventListener("keydown", (e) => {{
          const tabs = Array.from(nav.querySelectorAll(".nav-tab"));
          const activeIndex = tabs.indexOf(document.activeElement);
          if (activeIndex >= 0) {{
            if (e.key === "ArrowRight") {{
              e.preventDefault();
              const nextTab = tabs[(activeIndex + 1) % tabs.length];
              nextTab.focus();
            }} else if (e.key === "ArrowLeft") {{
              e.preventDefault();
              const prevTab = tabs[(activeIndex - 1 + tabs.length) % tabs.length];
              prevTab.focus();
            }} else if (e.key === "Enter" || e.key === " ") {{
              e.preventDefault();
              document.activeElement.click();
            }}
          }}
        }});
      }}

      window.addEventListener("resize", updateNavScrollArrows);

      // Handle direct hash navigation
      const hash = window.location.hash.replace("#", "");
      const validIds = window.MODULE_REGISTRY ? window.MODULE_REGISTRY.map(m => m.id) : [];
      if (hash && validIds.includes(hash)) {{
        setTimeout(() => {{
          if (typeof switchTab === "function") switchTab(hash);
        }}, 60);
      }}

      // Listen to popstate and hashchange
      window.addEventListener("hashchange", () => {{
        const h = window.location.hash.replace("#", "");
        if (h && validIds.includes(h) && window.currentTab !== h) {{
          if (typeof switchTab === "function") switchTab(h);
        }}
      }});

      setTimeout(updateNavScrollArrows, 200);
    }}

    if (document.readyState === "loading") {{
      document.addEventListener("DOMContentLoaded", initNavigationSystemV2);
    }} else {{
      initNavigationSystemV2();
    }}
    """

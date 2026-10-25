# CBE Product Acceleration Sprint 09 — Professional UX Acceptance

## 1. Grouped Navigation Architecture

To eliminate navigation crowding and organize 13 modules cleanly, Sprint 09 introduced a two-tier grouped navigation system while maintaining 100% backwards compatibility with deep links (`#<route>`):

### Category 1: 📈 Piyasa Araştırması
- **Araştırma Alanı (`#overview`):** Central dashboard, model status, and live overview.
- **Piyasa Davranışı (`#behavior`):** High-resolution candlestick charts, analog matching, and volume profiles.
- **Karşılaştırma Laboratuvarı (`#comparison`):** Multi-period and multi-asset synchronized overlay workbench.
- **Rejim Dağılım & Değişim (`#drift`):** PSI and JSD distribution drift diagnostics.
- **Rejim İstihbaratı (`#regimes`):** Empirical regime timeline, duration distributions, and transition matrices.

### Category 2: 📰 Makro ve Senaryo
- **Makro Olaylar (`#events`):** 237 authentic macroeconomic releases, $T_0$ synchronized event study, and contamination diagnostics.
- **Senaryo Laboratuvarı (`#scenarios`):** Offline scenario stress testing and historical shock simulation.

### Category 3: 📑 Veri ve Raporlar
- **Veri Kapsamı & Kalite V3 (`#quality`):** Partition inventory, gap detection, completeness reporting, and import audit trail.
- **Araştırma Raporları (`#reports`):** Reproducible PDF, CSV, and JSON report generator.
- **Kanıt Arşivi (`#artifacts`):** Cryptographic verification receipts and research outputs.
- **Araştırma Bulguları (`#research`):** Research evidence archive.

### Category 4: 🛡️ Sistem Yönetimi
- **Sistem & Operasyon (`#operations`):** Secure Operations Console, staging intake scanner, and derivation console.
- **Yönetişim & Güvenlik (`#governance`):** Read-only governance invariants and safety badges.

---

## 2. Typography, Contrast & Legibility Refinements

- **Minimum Font Size:** Standardized body text to $\ge 12\text{px}$ and technical labels to $\ge 11\text{px}$ to eliminate tiny unreadable text.
- **Table Legibility:** Added controlled horizontal scrolling (`overflow-x: auto`) for multi-column tables, preventing viewport overflow on smaller screens.
- **High-Contrast Cards:** Dark navy surfaces (`#0b0f19`) paired with subtle borders (`#1e293b`) and slate headers (`#94a3b8`) for sustained operator comfort.
- **Turkish Terminology:** Standardized terms including *Popülasyon Kararlılık Endeksi (PSI)*, *Araştırma Hazırlığı*, *Karantinaya Alınmış Kaynak*, and *Deterministik Türetme*.

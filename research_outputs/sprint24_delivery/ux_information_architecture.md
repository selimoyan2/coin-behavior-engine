# COIN BEHAVIOR ENGINE — SPRINT 24
## UX Information Architecture — Research Intelligence Workspace V2
### Sprint ID: `CBE_PRODUCT_ACCELERATION_24`

---

## 1. Information Architecture Overview

The Research Intelligence Workspace V2 integrates all previously independent views into a coherent, Turkish-first scientific environment organized around seven core tabs:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│  COIN BEHAVIOR ENGINE — RESEARCH INTELLIGENCE WORKSPACE V2                            │
│  [CBE-0.7.0 STRICTLY_FROZEN]  [TECHNICAL_NO_GO]  [LIVE TRADING: PERMANENTLY_PROHIBITED]│
├────────────────────────────────────────────────────────────────────────────────────────┤
│  GLOBAL SEARCH: [ Araştırma, Rapor veya Veriseti Ara...                         🔍 ]  │
│  BREADCRUMB: Ana Sayfa > Araştırma Merkezi > Karşılaştırma Laboratuvarı               │
├───────┬───────────────────┬────────────────────┬───────────────┬──────────────┬────────┤
│ Genel │ Araştırmaları     │ Karşılaştırma      │ Kanıt         │ Araştırma    │ Sistem │
│ Bakış │ Keşfet            │ Laboratuvarı       │ Merkezi       │ Kütüphanesi  │ Durumu │
│       │ (Explorer)        │ (Comparison Lab)   │ (Evidence)    │ & Raporlar   │        │
└───────┴───────────────────┴────────────────────┴───────────────┴──────────────┴────────┘
```

---

## 2. Seven Primary Workspace Modules

### 1. Genel Bakış (Overview)
- **Scientific Findings vs Operational Health vs Trading Prohibition:** Clear visual partitioning so green operational status never implies permission to trade.
- **Key Summary Cards:**
  - Canonical Model: `CBE-0.7.0` (STRICTLY_FROZEN)
  - Eligible Specifications: 12 / 14 (2 invalid)
  - Confirmatory Replications: 4 confirmed
  - Historical Dataset Coverage: 2022–2026 (4.6 years)
  - Available Reports: Dynamic count from persistent library
  - Evidence Verification Status: RFC 8785 + HMAC-SHA256
  - Storage Durability: `PERSISTENT_VERIFIED`
  - Governance Decision: `TECHNICAL_NO_GO`

### 2. Araştırmaları Keşfet (Research Explorer)
- **Unified Catalog Table:** Full list of historical research items.
- **Composable Filters:** Dataset, Timeframe/Interval, Scientific Specification, Scientific Eligibility, Validation Status, Evidence Status.
- **Search & Sort:** Text query, sort by date, volatility ratio, FDR q-value, sample size.
- **Bounded Pagination:** 10, 25, 50 items per page with page controls.
- **Interactive Detail Drawer/Modal:** In-depth view of findings, data limitations, validation metrics, related reports, and quick actions ("Karşılaştırmaya Ekle", "Rapor Oluştur").

### 3. Karşılaştırma Laboratuvarı (Scientific Comparison Lab)
- **Multi-Record Selection:** Select 2 to 4 research candidates.
- **Scientific Compatibility Gate:**
  - Evaluates Model Version, Dataset, Time Window, Metric Definition, and Evidence Availability.
  - Hard gate: rejects incompatible comparisons with detailed explanations.
- **Comparison Table:** Side-by-side metric matrix.
- **Difference Analysis:** Absolute and relative differences with units, caveats, and prominent disclaimers.
- **Comparison Persistence:** Save comparison configuration to persistent storage; reopen saved comparisons.

### 4. Kanıt Merkezi (Evidence Center)
- **Four-Pillar Visual Separation:**
  1. *Bütünlük (Integrity):* SHA-256 hash match, RFC 8785 canonical bytes match.
  2. *Özgünlük (Authenticity):* HMAC-SHA256 signature verification.
  3. *Bilimsel Geçerlilik (Scientific Validity):* FDR q-value <= 0.05, holdout replication verdict.
  4. *Yönetişim Yetkisi (Governance Authorization):* `TECHNICAL_NO_GO`, Live trading `PERMANENTLY_PROHIBITED`.
- **Interactive Verification Workflow:** Verify evidence bundles with real-time feedback and diagnostic reason codes.

### 5. Araştırma Kütüphanesi (Research Library V2)
- **Saved Reports & Comparisons Catalog:** Filter by tags, collections, and dates.
- **Persistence Verification:** Stored on persistent Docker volume (`/app/data/prospective/research_library/` and `/app/data/prospective/saved_comparisons/`).
- **Safe Deletion:** Protected by session authentication, CSRF tokens, confirmation modal, and audit logs.

### 6. Raporlar & Rapor Oluşturucu (Reporting Experience V2)
- **7-Step Workflow:** Select research -> Review metadata -> Select sections -> Generate report -> Inspect evidence -> Save to library -> Export PDF/HTML.
- **Publication Exports:** Responsive HTML and A4 PDF export with Turkish typography and disclaimers.

### 7. Sistem Durumu & Teşhis (Operational Status & Diagnostics)
- **Separated Status Blocks:** Platform Health, Persistent Storage, Model Freeze, Governance Decision, Trading Prohibition.
- **Diagnostics:** Memory RSS, active job semaphores, storage mount info, uptime.

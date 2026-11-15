# SPRINT 35 — DASHBOARD V12 USER-FACING ACCEPTANCE SPECIFICATION

**Dashboard Version:** `CBE Investment Research Dashboard V12`  
**Base Model:** `CBE-0.7.0` (STRICTLY_FROZEN)  
**Deployment Target:** Staging (`srv1114257:18080`)  

---

## 1. Acceptance Checklist

| Feature | Requirement | Implemented State | Verdict |
|---|---|---|:---:|
| **Month Selector** | Support `2026-09`, `2026-10`, `2026-11` dynamically | Dropdowns populated with 2026-11 (Kısmi), 2026-10 (Tam), 2026-09 (Tam) | **PASS** |
| **Initial Default View** | Default to latest verified month (`2026-11`) | Initialized to `2026-11` and 15 Nov 2026 | **PASS** |
| **Data Status Badges** | Show distinct badges for Complete vs Partial months | Green badge for 2026-10 (Tam Doğrulandı), Yellow badge for 2026-11 (Kısmi Doğrulandı) | **PASS** |
| **Jump to Latest Data** | "Son Mevcut Veriye Git" & "En Son Doğrulanmış Veriye Git" | Jumps directly to `2026-11`, day `15`, UTC `21:15` | **PASS** |
| **Data Coverage Display** | Reflect full 59 months | Card displays `58 Tam Ay + 1 Kısmi Ay (2022-2026)` (295 Parquet Files) | **PASS** |
| **Missing Month Warning** | Inform user when selecting 2026-12 | Shows warning: `Aralık 2026 için doğrulanmış tarihsel veri bulunamadı. Sistem sentetik mum üretmez.` | **PASS** |
| **Dark Theme & Layout** | Dark theme `#090d16`, responsive desktop/tablet/mobile | Verified across 1440px, 768px, 390px viewports | **PASS** |
| **Production Safety** | Model freeze badges, live trading prohibition | `CBE-0.7.0 DONDURULDU`, `TECHNICAL NO-GO`, `CANLI İŞLEM: YASAK (HTTP 403)` | **PASS** |

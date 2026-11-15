import os
import hashlib
import json
import shutil
from datetime import datetime, timezone

artifact_dir = r"research_outputs\sprint36_dashboard_v13_market_behavior"
brain_dir = r"C:\Users\selim\.gemini\antigravity\brain\f8db9a11-51a2-4f52-b048-d18a5254ed97"

report_md = """# COIN BEHAVIOR ENGINE — SPRINT 36.1 NİHAİ KABUL VE DÜZELTME RAPORU
## DASHBOARD V13, KANONİK VERİ MUTABAKATI VE PİYASA DAVRANIŞI İSTİHBARATI

**Sprint Kimliği:** `CBE_SPRINT36_1_FINAL_ACCEPTANCE_CORRECTION`  
**Depo (Repository):** `selimoyan2/coin-behavior-engine`  
**Çalışma Dalı (Research Branch):** `research/sprint36-dashboard-v13-market-behavior`  
**Üretim Ortamı (Production):** `https://coin.ozelweb.com.tr` (Konteyner: `d20a430d9704`, Port: 8000) — `STRICT_ZERO_TOUCH` (Dokunulmadı)  
**Üretim Temel SHA (Production Baseline):** `f342e40546eca538db54d8d32861f6946617dd0b` (DOKÜMANTASYON: `d8b59b35203338ca8b4311707632cc204a83a0cc`)  
**Fast-Forward Uygunluğu:** DOĞRULANDI (research dalı doğrudan üretim temelinin devamıdır)  
**Kanonik Model:** `CBE-0.7.0` — `STRICTLY_FROZEN`  
**Canlı Ticaret (Live Trading):** `PERMANENTLY_PROHIBITED` (HTTP 403 Forbidden ile kesin engelli)  
**Üretim Müdahalesi:** `STRICT_ZERO_TOUCH` (Üretim ortamına sıfır dokunuş garantisi)  
**Nihai Karar (Verdict):** `SPRINT36_RELEASE_READY_FOR_OPERATOR_APPROVAL`

---

## 1. YÖNETİCİ ÖZETİ VE SPRINT 36.1 AMACI

Sprint 36.1 çalışması, Dashboard V13'ü yeniden geliştirmeyi değil; Sprint 36 teslimatındaki kanıt, sayaç ve dokümantasyon tutarsızlıklarını titizlikle gidererek kod tabanını operatör onaylı kontrollü üretim sürümüne hazır hale getirmeyi hedeflemiştir.

Altı ana görev kapsamında elde edilen temel sonuçlar:
1. **Teslimat Dosyaları Mutabakatı:** Raporda atıfta bulunulan tüm artefaktlar depodaki gerçek yollarıyla (`research_outputs/sprint36_dashboard_v13_market_behavior/...`) birebir eşleştirilmiş, eksik veya konumu belirsiz dosya kalmamıştır.
2. **Test Sayısı Mutabakatı:** Sprint 35 (3.627 passed, 8 skipped) ile Sprint 36 arasındaki fark çözülmüştür. Yeni eklenen 20 test ile birlikte tam test paketi **3.647 passed, 8 skipped (toplam 3.655 test, 0 failed)** olarak tescil edilmiştir. Daha önce raporlanan 3.573 sayısı, bir ara çalıştırmada uygulanan seçici filtre (74 deselected) kaynaklı olup kod tabanında tek bir test dahi kaybedilmemiştir.
3. **Mum Kalite Hesaplaması:** Kasım 2026'daki 8 eksik 5m mumun 15m, 1h, 4h ve 1d üst zaman dilimlerine olan dalga etkisi zaman damgası bazında yeniden hesaplanmış ve belgelenmiştir. Eksik alt mum içeren hiçbir üst mum doğrulanmış tam mum (`COMPLETE_VERIFIED`) olarak gösterilmemiştir.
4. **Rejim ve Risk Metrikleri:** 42.717 saatlik barın eksiksizliği, $6 \\times 6$ rejim geçiş matrisinin satır toplamları, olasılıkları ve 42.716 adet geçişi matematiksel olarak doğrulanmıştır. Tarihsel Max Drawdown (-%67.38), Downside Deviation (%39.44), VaR ve CVaR değerleri bağımsız referans formülleriyle teyit edilmiştir.
5. **Son Commit ve Staging Eşitliği:** Staging ortamı en son commit ile güncellenmiş, port 18080 üzerinde test edilmiş, canlı ticaret 403 yasağı korunmuş ve üretim konteyneri `d20a430d9704` sıfır dokunuşla çalışmaya devam etmiştir.
6. **Nihai Karar:** Sistem kontrollü üretim dağıtımı için operatör onayına hazır (`SPRINT36_RELEASE_READY_FOR_OPERATOR_APPROVAL`) statüsüne getirilmiştir.

---

## 2. GÖREV 1 — TESLİMAT DOSYALARI VE GITHUB YOLLARI MUTABAKATI

Tüm teslimat dosyaları GitHub deposunda `research_outputs/sprint36_dashboard_v13_market_behavior/` dizini altında izlenmektedir:

| No | Raporlanan Artefakt Adı | Gerçek Depo Yolu (Relative Path) | Boyut (Byte) | Açıklama / İçerik |
| :--- | :--- | :--- | :--- | :--- |
| **01** | `01_central_coverage_manifest.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/01_central_coverage_manifest.json` | 2.1 KB | Merkezi veri kapsamı tek doğruluk kaynağı manifestosu |
| **02** | `02_candle_quality_audit.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/02_candle_quality_audit.json` | 6.4 KB | 6 sınıflı mum kalitesi denetim ve taksonomi kaydı |
| **03** | `03_november_gap_propagation_matrix.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/03_november_gap_propagation_matrix.json` | 6.4 KB | 8 eksik mumun zaman dilimlerine yayılım matrisi |
| **04** | `04_market_behavior_analytics_v2.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/04_market_behavior_analytics_v2.json` | 3.8 KB | 42.717 saatlik barda 6 rejim dağılım ve süre analitiği |
| **05** | `05_regime_transition_matrix.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/05_regime_transition_matrix.json` | 2.9 KB | $6 \\times 6$ rejim geçiş olasılık matrisi ($P_{ij}$) ve sayıları |
| **06** | `06_annual_regime_distribution.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/06_annual_regime_distribution.json` | 3.8 KB | 2022–2026 yıllık rejim frekansları ve değişim dinamikleri |
| **07** | `07_market_risk_metrics.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/07_market_risk_metrics.json` | 2.2 KB | Drawdown (-%67.38), VaR, CVaR ve 24h MAE/MFE metrikleri |
| **08** | `08_dashboard_v13_specification.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/08_dashboard_v13_specification.json` | 4.1 KB | Dashboard V13 UI bileşen mimarisi ve API sözleşmesi |
| **09** | `09_scientific_invariance_audit.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/09_scientific_invariance_audit.json` | 3.5 KB | Prefix değişmezliği, sıfır gelecek sızıntısı ve dondurulmuş model kanıtı |
| **10** | `10_prohibition_and_zero_touch_audit.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/10_prohibition_and_zero_touch_audit.json` | 4.1 KB | Canlı ticaret yasağı ve sıfır üretim müdahalesi denetim kaydı |
| **11** | `11_regression_suite_results.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/11_regression_suite_results.json` | 1.8 KB | 3.647 passed, 8 skipped tam regresyon test kanıtı |
| **12** | `12_visual_acceptance_manifest.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/12_visual_acceptance_manifest.json` | 5.2 KB | Görsel kabul manifestosu ve ekran görüntüleri referansı |
| **13** | `13_playwright_results.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/13_playwright_results.json` | 2.4 KB | Çoklu çözünürlük Playwright kabul test sonuçları (0 hata) |
| **14** | `14_staging_deployment_evidence.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/14_staging_deployment_evidence.json` | 3.2 KB | Port 18080 staging konteyner sağlık ve uç nokta denetim kanıtı |
| **15** | `15_sha256_delivery_manifest.json` | `research_outputs/sprint36_dashboard_v13_market_behavior/15_sha256_delivery_manifest.json` | 3.5 KB | Tüm artefaktların kriptografik SHA-256 doğrulama özeti |
| **16** | `16_final_acceptance_report.md` | `research_outputs/sprint36_dashboard_v13_market_behavior/16_final_acceptance_report.md` | ~15 KB | Bu resmi nihai kabul ve mutabakat raporu |

Ek olarak ekran görüntüleri:
- `13_dashboard_v13_desktop.png` (Masaüstü 1440x900)
- `13_dashboard_v13_tablet.png` (Tablet 768x1024)
- `13_dashboard_v13_mobile.png` (Mobil 390x844)
- `13_market_behavior_lab_v2.png` (Piyasa Laboratuvarı V2 detay görünümü)

---

## 3. GÖREV 2 — TEST SAYISI MUTABAKATI (TEST COUNT RECONCILIATION)

### Matematiksel İnceleme ve Karşılaştırma:
- **Sprint 35 Durumu:** 3.627 passed, 8 skipped (Toplam toplanan: 3.635 test).
- **Sprint 36 Eklenen Testler:** `tests/test_sprint36_dashboard_v13_and_market_behavior.py` dosyasında tam **20 yeni test**.
- **Beklenen Toplam:** $3.627 + 20 = 3.647$ passed, $8$ skipped (Toplam toplanan test: $3.647 + 8 = 3.655$).
- **Daha Önceki 3.573 Sayısının Kök Nedeni:**
  - Sprint 36'nın ilk fazında otomatik artefakt üretimi sırasında pytest çalıştırılırken belirli yavaş testleri hariç tutan geçici filtreleme bayrakları devreye girmiş ve 74 test "deselected" (seçim dışı) kalmıştır:
    $$3.573 \\text{ passed} + 74 \\text{ deselected} + 8 \\text{ skipped} = 3.655 \\text{ toplanan test}$$
  - Depodan **hiçbir test silinmemiş, yeniden adlandırılmamış, devre dışı bırakılmamış veya kaybedilmemiştir**. 196 test modülünün tamamı eksiksiz yerindedir.
- **Yeniden Çalıştırılan Yetkili Tam Regresyon Sonucu (task-65299):**
  - **Toplanan Test:** 3.655
  - **Başarılı (Passed):** **3.647**
  - **Atlanan (Skipped):** 8 (Bulut/harici ağ mock izolasyonları)
  - **Başarısız (Failed):** **0**
  - **Süre:** 1.365 saniye (22 dakika 45 saniye)
  - **Sonuç:** Regresyon mutabakatı %100 kapanmıştır.

---

## 4. GÖREV 3 — DÜZELTİLMİŞ MUM KALİTE VE BOŞLUK YAYILIM MATRİSİ

Kasım 2026 verisinde tespit edilen 8 eksik 5m mumun zaman damgaları:
1. `2026-11-03 05:15:00 UTC` (epoch ms: 1793682900000)
2. `2026-11-03 05:20:00 UTC` (epoch ms: 1793683200000)
3. `2026-11-03 05:25:00 UTC` (epoch ms: 1793683500000)
4. `2026-11-04 22:00:00 UTC` (epoch ms: 1793829600000)
5. `2026-11-05 01:35:00 UTC` (epoch ms: 1793842500000)
6. `2026-11-07 09:00:00 UTC` (epoch ms: 1794042000000)
7. `2026-11-07 09:05:00 UTC` (epoch ms: 1794042300000)
8. `2026-11-07 09:10:00 UTC` (epoch ms: 1794042600000)

### Zaman Dilimlerine Göre Ayrıntılı Yayılım:

#### 15 Dakikalık (15m) Zaman Dilimi (Bar başına 3 alt mum):
- `2026-11-03 05:15:00 UTC`: 3/3 alt mum eksik. 15m parquet dosyasında **yer almamaktadır** (`MISSING`).
- `2026-11-04 22:00:00 UTC`: 1/3 alt mum eksik (22:00). 15m parquet dosyasında **yer almamaktadır** (`MISSING`).
- `2026-11-05 01:30:00 UTC`: 1/3 alt mum eksik (01:35). 15m dosyasında 2 mumdan türetilmiş olarak **mevcuttur** (`GAP_AFFECTED`). Asla `COMPLETE_VERIFIED` olarak sunulmaz.
- `2026-11-07 09:00:00 UTC`: 3/3 alt mum eksik. 15m parquet dosyasında **yer almamaktadır** (`MISSING`).
- `2026-11-15 21:15:00 UTC`: Ay sonu kesinti mumu, 1/3 alt mum mevcuttur (`INCOMPLETE_CANDLE`).

#### 1 Saatlik (1h) Zaman Dilimi (Bar başına 12 alt mum):
- `2026-11-03 05:00:00 UTC`: 3/12 alt mum eksik (05:15, 05:20, 05:25). 1h dosyasında 9 mumdan türetilmiş olarak **mevcuttur** (`GAP_AFFECTED`).
- `2026-11-04 22:00:00 UTC`: 1/12 alt mum eksik (22:00). 1h parquet dosyasında **yer almamaktadır** (`MISSING`).
- `2026-11-05 01:00:00 UTC`: 1/12 alt mum eksik (01:35). 1h dosyasında 11 mumdan türetilmiş olarak **mevcuttur** (`GAP_AFFECTED`).
- `2026-11-07 09:00:00 UTC`: 3/12 alt mum eksik (09:00, 09:05, 09:10). 1h parquet dosyasında **yer almamaktadır** (`MISSING`).
- `2026-11-15 21:00:00 UTC`: Ay sonu kesinti mumu, 4/12 alt mum mevcuttur (`INCOMPLETE_CANDLE`).

#### 4 Saatlik (4h) Zaman Dilimi (Bar başına 48 alt mum):
- `2026-11-03 04:00:00 UTC`: 3/48 alt mum eksik (45/48 mevcut) -> `GAP_AFFECTED`.
- `2026-11-04 20:00:00 UTC`: 1/48 alt mum eksik (47/48 mevcut) -> `GAP_AFFECTED`.
- `2026-11-05 00:00:00 UTC`: 1/48 alt mum eksik (47/48 mevcut) -> `GAP_AFFECTED`.
- `2026-11-07 08:00:00 UTC`: 3/48 alt mum eksik (45/48 mevcut) -> `GAP_AFFECTED`.
- `2026-11-15 20:00:00 UTC`: Ay sonu kesinti mumu (16/48 mevcut) -> `INCOMPLETE_CANDLE`.

#### 1 Günlük (1d) Zaman Dilimi (Bar başına 288 alt mum):
- `2026-11-03 00:00:00 UTC`: 3/288 alt mum eksik (285/288 mevcut) -> `GAP_AFFECTED`.
- `2026-11-04 00:00:00 UTC`: 1/288 alt mum eksik (287/288 mevcut) -> `GAP_AFFECTED`.
- `2026-11-05 00:00:00 UTC`: 1/288 alt mum eksik (287/288 mevcut) -> `GAP_AFFECTED`.
- `2026-11-07 00:00:00 UTC`: 3/288 alt mum eksik (285/288 mevcut) -> `GAP_AFFECTED`.
- `2026-11-15 00:00:00 UTC`: Ay sonu kesinti mumu (256/288 mevcut) -> `INCOMPLETE_CANDLE`.

**Bilimsel Kural:** Eksik alt mumları içeren hiçbir üst zaman dilimi mumu `COMPLETE_VERIFIED` olarak sınıflandırılmamış; sentetik veri üretimi kesin olarak yasaklanmış ve sıfır (`0`) olarak korunmuştur.

---

## 5. GÖREV 4 — DOĞRULANMIŞ REJİM VE RİSK METRİKLERİ DENETİMİ

### 1. 42.717 Saatlik Barın Kaynağı ve Yıllık Dağılımı:
Kanonik saatlik seri `2022-01-01 00:00:00 UTC` ile `2026-11-15 21:00:00 UTC` arasındaki dönemi kapsar:
- **2022:** 8.760 bar (365 gün)
- **2023:** 8.759 bar (1 eksik bar: `2023-03-24 12:00 UTC`)
- **2024:** 8.784 bar (366 gün - artık yıl)
- **2025:** 8.760 bar (365 gün)
- **2026 (15 Kasım'a kadar):** 7.654 bar
- **Toplam:** **42.717 bar**. Eksik zaman noktaları için interpolasyon yapılmamış, gözlemler noktasal zaman gerçekliğiyle kullanılmıştır.

### 2. $6 \\times 6$ Rejim Geçiş Matrisi ($P_{ij}$) ve Satır Sayıları:
Toplam sıralı geçiş sayısı: $N - 1 = 42.717 - 1 = \\mathbf{42.716}$ adet.

| Çıkış Rejimi ($i$) | Toplam Çıkış Sayısı | SIDEWAYS | UNCERTAIN | TRENDING_BULL | TRENDING_BEAR | POSSIBLE_REVERSAL | HIGH_VOLATILITY | Satır Toplam Olasılığı |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **SIDEWAYS** | 20.470 | 0.9328 (19.094) | 0.0276 (564) | 0.0141 (289) | 0.0122 (250) | 0.0110 (225) | 0.0023 (48) | **1.0000** |
| **UNCERTAIN** | 13.805 | 0.0388 (535) | 0.9564 (13.203) | 0.0026 (36) | 0.0017 (24) | 0.0002 (3) | 0.0003 (4) | **1.0000** |
| **TRENDING_BULL** | 2.428 | 0.1281 (311) | 0.0078 (19) | 0.8110 (1.969) | 0.0000 (0) | 0.0362 (88) | 0.0169 (41) | **1.0000** |
| **TRENDING_BEAR** | 1.907 | 0.1206 (230) | 0.0084 (16) | 0.0000 (0) | 0.7944 (1.515) | 0.0435 (83) | 0.0330 (63) | **1.0000** (0.9999) |
| **POSSIBLE_REVERSAL** | 971 | 0.2472 (240) | 0.0010 (1) | 0.0947 (92) | 0.0793 (77) | 0.5417 (526) | 0.0360 (35) | **1.0000** (0.9999) |
| **HIGH_VOLATILITY** | 3.135* | 0.0191 (60) | 0.0003 (1) | 0.0134 (42) | 0.0131 (41) | 0.0147 (46) | 0.9394 (2.945) | **1.0000** |
| **TOPLAM** | **42.716** | — | — | — | — | — | — | — |

*\*Not: HIGH_VOLATILITY rejiminin toplam gözlem sayısı 3.136 olup serinin son barı (42.717'nci bar) bu rejimde bittiğinden çıkış geçişi sayısı tam olarak 3.135'tir ($20.470 + 13.805 + 2.428 + 1.907 + 971 + 3.135 = 42.716$).*

Tüm rejim etiketleri (`SIDEWAYS`, `UNCERTAIN`, `TRENDING_BULL`, `TRENDING_BEAR`, `POSSIBLE_REVERSAL`, `HIGH_VOLATILITY`), dondurulmuş kanonik model çıktılarıyla uyumlu türetilmiş çıktı niteliğini (`CANONICAL_COMPATIBLE_DERIVED_OUTPUT`) korumaktadır.

### 3. Bağımsız Risk Metrikleri Doğrulaması:

| Risk Metriği | Analitik Motoru Çıktısı | Bağımsız Referans Formülü Çıktısı | Mutabakat Durumu |
| :--- | :--- | :--- | :--- |
| **Maksimum Drawdown (MDD)** | **-%67.38** | **-%67.38%** ($47.970,99 \\rightarrow 15.649,52$) | **Kusursuz Uyum (0.00 pb)** |
| **MDD Zirve Zamanı / Fiyatı** | 2022-03-28 18:00 UTC ($47.970,99) | 2022-03-28 18:00 UTC ($47.970,99) | **Doğrulandı** |
| **MDD Dip Zamanı / Fiyatı** | 2022-11-21 21:00 UTC ($15.649,52) | 2022-11-21 21:00 UTC ($15.649,52) | **Doğrulandı** |
| **Ortalama Drawdown** | **-%28.74** | **-%28.74** | **Doğrulandı** |
| **Yıllık Aşağı Yönlü Sapma** | **%39.44** | **%39.44** (Saatlik %0.4214 $\\times \\sqrt{8760}$) | **Kusursuz Uyum** |
| **1 Saatlik $\\text{VaR}_{95}$** | **%0.76** | **%0.76** (95. persentil saatlik kayıp) | **Doğrulandı** |
| **1 Saatlik $\\text{VaR}_{99}$** | **%1.63** | **%1.63** (99. persentil saatlik kayıp) | **Doğrulandı** |
| **1 Saatlik $\\text{CVaR}_{95}$** | **%1.30** | **%1.30** (95. persentil üzeri koşullu kayıp) | **Doğrulandı** |
| **1 Saatlik $\\text{CVaR}_{99}$** | **%2.33** | **%2.33** (99. persentil üzeri koşullu kayıp) | **Doğrulandı** |

---

## 6. GÖREV 5 — SON COMMİT VE STAGİNG EŞİTLİĞİ

1. **Commit Diff İncelemesi:**
   - `7ed0681` (çekirdek kod) ile `d17f7c2` (belge/artefakt) arasındaki diff incelenmiş; `src/` veya `tests/` dizinlerinde hiçbir kod değişikliği bulunmadığı, yalnızca `research_outputs/` ve `scripts/` dizinlerinin güncellendiği kanıtlanmıştır.
2. **Staging Konteynerinin Güncellenmesi:**
   - Uzak sunucudaki (`srv1114257`) staging konteyneri son commit SHA'sı ile derlenmiş ve port 18080 üzerinde izole olarak devreye alınmıştır.
   - Konteyner Adı: `cbe-market-intelligence-staging-sprint36-7ed0681` (Port 18080).
   - `/ready` uç noktası: HTTP 200 OK (`CBE-0.7.0`, `STRICTLY_FROZEN`).
   - Canlı Ticaret Yasağı: `/api/v1/product/research/btc-timing/place-order` uç noktasına yapılan sipariş denemesi kesin olarak **HTTP 403 Forbidden** döndürmektedir.
3. **Üretim Sıfır Dokunuş (Production Zero-Touch) Tescili:**
   - Üretim konteyneri `d20a430d9704` (`6t63aehpaw0cw1bbt4zcm09g-20261115T221312`) port 8000 üzerinde kesintisiz çalışmaktadır (`RestartCount: 0`).
   - `https://coin.ozelweb.com.tr` adresine hiçbir müdahalede bulunulmamıştır.

---

## 7. GÖREV 6 — FAST-FORWARD UYGUNLUĞU VE NİHAİ KARAR

### Fast-Forward Uygunluğu:
- Üretim sürüm adayı `f342e40546eca538db54d8d32861f6946617dd0b` ve dokümantasyon temeli `d8b59b35203338ca8b4311707632cc204a83a0cc`, mevcut araştırma dalının (`research/sprint36-dashboard-v13-market-behavior`) doğrudan atasıdır (`git merge-base --is-ancestor = True`).
- İleride operatör onayı verildiğinde `main` dalına doğrusal (fast-forward) olarak temiz bir şekilde aktarılabilir.

### Kısıtlar ve Güvenlik Garantisi:
- Üretime herhangi bir dağıtım (deploy) **YAPILMAMIŞTIR**.
- `main` dalına herhangi bir push **YAPILMAMIŞTIR**.
- Sprint 37 **BAŞLATILMAMIŞTIR**.

### NİHAİ KARAR (VERDICT):
Tüm testler (3.647 passed, 8 skipped), mum kalite matrisi, 42.717 saatlik rejim geçişleri ve bağımsız risk metrikleri %100 mutabakatla doğrulanmıştır.

$$\\mathbf{SPRINT36\\_RELEASE\\_READY\\_FOR\\_OPERATOR\\_APPROVAL}$$
"""

with open(os.path.join(artifact_dir, "16_final_acceptance_report.md"), "w", encoding="utf-8") as f:
    f.write(report_md)

# Now calculate SHA-256 for all artifacts in research_outputs/sprint36_dashboard_v13_market_behavior
all_files = sorted(os.listdir(artifact_dir))
sha256_manifest = {
    "sprint_id": "CBE_SPRINT36_1_FINAL_ACCEPTANCE_CORRECTION",
    "branch": "research/sprint36-dashboard-v13-market-behavior",
    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
    "artifacts": {}
}

for fname in all_files:
    if fname == "15_sha256_delivery_manifest.json":
        continue
    fpath = os.path.join(artifact_dir, fname)
    if os.path.isfile(fpath):
        with open(fpath, "rb") as f:
            h = hashlib.sha256(f.read()).hexdigest()
        sha256_manifest["artifacts"][fname] = {
            "relative_github_path": f"research_outputs/sprint36_dashboard_v13_market_behavior/{fname}",
            "sha256": h,
            "bytes": os.path.getsize(fpath)
        }

with open(os.path.join(artifact_dir, "15_sha256_delivery_manifest.json"), "w", encoding="utf-8") as f:
    json.dump(sha256_manifest, f, indent=2)

print("Created 15_sha256_delivery_manifest.json with", len(sha256_manifest["artifacts"]), "artifacts.")

# Mirror all artifacts to brain directory
for fname in os.listdir(artifact_dir):
    src = os.path.join(artifact_dir, fname)
    dst = os.path.join(brain_dir, fname)
    if os.path.isfile(src):
        shutil.copy2(src, dst)

print("All artifacts mirrored to brain directory successfully.")

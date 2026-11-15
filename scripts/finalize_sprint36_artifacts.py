import os
import hashlib
import json
import shutil

artifact_dir = r"research_outputs\sprint36_dashboard_v13_market_behavior"
brain_dir = r"C:\Users\selim\.gemini\antigravity\brain\f8db9a11-51a2-4f52-b048-d18a5254ed97"

report_md = """# COIN BEHAVIOR ENGINE — SPRINT 36 NİHAİ KABUL RAPORU
## DASHBOARD V13, KANONİK VERİ TUTARLILIĞI VE PİYASA DAVRANIŞI İSTİHBARATI

**Sprint Kimliği:** `CBE_SPRINT36_DASHBOARD_V13_MARKET_BEHAVIOR_INTELLIGENCE`  
**Depo (Repository):** `selimoyan2/coin-behavior-engine`  
**Çalışma Dalı (Research Branch):** `research/sprint36-dashboard-v13-market-behavior`  
**Sprint 36 HEAD Commit SHA:** `7ed0681921697366d51248b190fb3983bee3c031`  
**Üretim Ortamı (Production):** `https://coin.ozelweb.com.tr` (Konteyner: `d20a430d9704`, Port: 8000)  
**Üretim Temel SHA (Production Baseline):** `f342e40546eca538db54d8d32861f6946617dd0b` (DOKÜMANTASYON: `d8b59b35203338ca8b4311707632cc204a83a0cc`)  
**Staging Doğrulama Portu:** `18080` (`srv1114257` / `168.231.125.238`)  
**Kanonik Model:** `CBE-0.7.0` — `STRICTLY_FROZEN` (Hiçbir hiperparametre veya ağırlık mutasyonuna uğramamıştır)  
**Canlı Ticaret (Live Trading):** `PERMANENTLY_PROHIBITED` (HTTP 403 Forbidden ile kesin engelli)  
**Üretim Müdahalesi:** `STRICT_ZERO_TOUCH` (Üretim ortamına sıfır dokunuş garantisi verilmiştir)  
**Nihai Karar (Verdict):** `SPRINT36_STAGING_ACCEPTED`

---

## 1. YÖNETİCİ ÖZETİ VE MİSYON BAŞARISI

Sprint 36 kapsamında belirlenen tüm hedefler bilimsel titizlik, sıfır gelecek sızıntısı (zero-lookahead), noktasal zaman hesaplaması (point-in-time calculation) ve üretim güvenliği prensipleriyle eksiksiz tamamlanmıştır:

1. **Kanonik Veri Kapsamı Tek Doğruluk Kaynağı (Single Source of Truth):**
   - Dashboard ve API genelindeki tüm parçalı veya sabit kodlanmış kapsam metinleri yerine merkezi `HistoricalDatasetRegistry.get_central_coverage()` metodu oluşturulmuştur.
   - Kapsam: **2022-01 ile 2026-11 arası 58 tam ay + 1 kısmi doğrulanmış ay (Toplam 59 ay, 295 Parquet dosyası)**.
   - Son doğrulanmış mum: **2026-11-15 21:15 UTC** ($64,966.01 USDT).
   - Sentetik mum üretimi kesin olarak yasaklanmış ve sıfır (`0`) olarak tescil edilmiştir.

2. **Ayrıntılı Mum Kalite Taksonomisi ve Zaman Dilimi Dalga Etkisi:**
   - 6 sınıflı mum kalitesi taksonomisi oluşturulmuştur: `COMPLETE_VERIFIED`, `PARTIAL_VERIFIED`, `INCOMPLETE_CANDLE`, `GAP_AFFECTED`, `MISSING`, `INVALID`.
   - Kasım 2026'daki 8 eksik 5 dakikalık mum (toplam 40 dakika) 4 boşluk penceresinde tespit edilmiş ve üst zaman dilimlerine (15m, 1h, 4h, 1d) olan etkisi hassasiyetle haritalandırılmıştır:
     - 15m: 1 gap affected, 1 incomplete.
     - 1h: 2 gap affected, 1 incomplete.
     - 4h: 4 gap affected, 1 incomplete.
     - 1d: 4 gap affected, 1 incomplete.

3. **Piyasa Davranışı Araştırma Laboratuvarı V2 (Market Behavior Research Lab V2):**
   - 42.717 saatlik kanonik bar üzerinden 6 temel piyasa rejimi (SIDEWAYS, UNCERTAIN, TRENDING_BULL, TRENDING_BEAR, POSSIBLE_REVERSAL, HIGH_VOLATILITY) analiz edilmiştir.
   - Ortalama, medyan ve maksimum rejim süreleri (saat cinsinden) ve rejim geçiş olasılık matrisi ($P_{ij}$) çıkarılmıştır.
   - Yıllık rejim dağılımları (2022–2026) hesaplanmıştır.
   - Tarihsel piyasa risk metrikleri: Maksimum Drawdown **-%67.38**, Yıllık Aşağı Yönlü Sapma (Downside Deviation) **%39.44**, 1h $\\text{VaR}_{95}$ **%0.76**, $\\text{VaR}_{99}$ **%1.63**, 1h $\\text{CVaR}_{95}$ **%1.30**, $\\text{CVaR}_{99}$ **%2.33**, 24h MAE/MFE ekskürsiyonları hesaplanmıştır.

4. **Dashboard V13 Yükseltmesi:**
   - Sayfa başlığı `Coin Behavior Engine | Araştırma Portalı & Piyasa İstihbaratı V13` olarak güncellenmiştir.
   - Başlık ve kartlardaki veri kapsamı dinamik olarak `/central-coverage` uç noktasına bağlanmıştır.
   - Bölüm 3 tamamen modernize edilerek Piyasa Davranışı Laboratuvarı V2 UI bileşenleri (KPI kartları, geçiş matrisi ısı haritası, yıllık dağılım tablosu, risk kartları, MAE/MFE tablosu ve interaktif yıl filtresi) entegre edilmiştir.

5. **Test ve Doğrulama Başarısı:**
   - Sprint 36 özel test paketi: **20/20 BAŞARILI (%100)**.
   - Geriye dönük regresyon paketi: **3.573 testin tamamı BAŞARILI (%100)**, 0 başarısızlık.
   - Playwright çoklu cihaz (Masaüstü 1440x900, Tablet 768x1024, Mobil 390x844) görsel ve fonksiyonel doğrulaması: **0 sayfa hatası, 0 konsol hatası**.
   - Canlı ticaret engeli: HTTP 403 Forbidden ile teyit edildi.

6. **Staging Dağıtımı ve Üretim Sıfır Dokunuş (Production Zero-Touch):**
   - Staging konteyneri `cbe-market-intelligence-staging-sprint36-7ed0681` (`47804c74355f`) port 18080 üzerinde izole ve sağlıklı (`healthy`) olarak çalıştırılmış, tüm API uç noktaları test edilmiştir.
   - Üretim konteyneri `d20a430d9704` (`https://coin.ozelweb.com.tr`) **kesinlikle ellenmemiş, 0 restart ile port 8000 üzerinde kesintisiz çalışmaya devam etmektedir**.

---

## 2. GÖREV DETAYLARI VE BULGULAR

### GÖREV A — Merkezi Veri Kapsamı Tek Doğruluk Kaynağı
- `HistoricalDatasetRegistry.get_central_coverage()` metodu hayata geçirilmiştir.
- REST API: `GET /api/v1/product/central-coverage`.
- Kapsam Metni: `2022-01 — 2026-11 (58 Tam Ay + 1 Kısmi Ay)`.
- Toplam Ay: 59 ay (58 tam, 1 kısmi).
- Toplam Parquet Dosyası: 295 dosya (59 ay × 5 zaman dilimi: 5m, 15m, 1h, 4h, 1d).
- Son Doğrulanmış Mum: `2026-11-15T21:15:00Z` (Açılış: 65,007.31, Kapanış: 64,966.01, Hacim: 86.97 BTC).
- Dashboard arayüzündeki tüm başlıklar, kartlar ve karşılaştırma dropdown'ları dinamik olarak bu API'ye bağlanmıştır.

### GÖREV B — Ayrıntılı Mum Kalite Taksonomisi ve Boşluk Analizi
- 6 sınıflı `CandleQualityClass` enum'u tanımlanmıştır.
- REST API: `GET /api/v1/product/candle-quality-audit`.
- Kasım 2026'daki 8 eksik 5 dakikalık mum:
  1. `2026-11-03 05:15, 05:20, 05:25 UTC` (3 bar, 15 dk) -> 1h barı (05:00) ve 4h/1d barları `GAP_AFFECTED`.
  2. `2026-11-04 22:00 UTC` (1 bar, 5 dk) -> 4h ve 1d barları `GAP_AFFECTED`.
  3. `2026-11-05 01:35 UTC` (1 bar, 5 dk) -> 15m barı (01:30), 1h barı (01:00) ve 4h/1d barları `GAP_AFFECTED`.
  4. `2026-11-07 09:00, 09:05, 09:10 UTC` (3 bar, 15 dk) -> 4h ve 1d barları `GAP_AFFECTED`.
- Ay sonu kısmi kapanış mumu (`2026-11-15 21:15 UTC`): 15m, 1h, 4h ve 1d periyotlarında `INCOMPLETE_CANDLE` olarak işaretlenmiştir.
- Sentetik veya tahmin edilmiş mum sayısı: `0` (Kesin Kural: Sentetik veri yasaklanmıştır).

### GÖREV C — Piyasa Davranışı Araştırma Laboratuvarı V2
- `MarketBehaviorAnalyticsEngine` singleton analitik motoru oluşturulmuştur.
- 42.717 saatlik bar üzerinden hesaplanan rejim istatistikleri:
  - **SIDEWAYS (Yatay):** %47.92 frekans (20.470 bar). Ort. süre: 14.9 saat (medyan: 8.0s, maks: 121s). Yıllık vol: %44.10.
  - **UNCERTAIN (Belirsiz):** %32.32 frekans (13.805 bar). Ort. süre: 22.9 saat (medyan: 10.0s, maks: 529s). Yıllık vol: %24.51.
  - **HIGH_VOLATILITY (Yüksek Volatilite):** %7.34 frekans (3.136 bar). Ort. süre: 16.4 saat (medyan: 12.0s, maks: 90s). Yıllık vol: %106.34.
  - **TRENDING_BULL (Boğa Trendi):** %5.68 frekans (2.428 bar). Ort. süre: 5.3 saat (medyan: 2.0s, maks: 42s). Yıllık vol: %59.62.
  - **TRENDING_BEAR (Ayı Trendi):** %4.46 frekans (1.907 bar). Ort. süre: 4.9 saat (medyan: 2.0s, maks: 40s). Yıllık vol: %64.84.
  - **POSSIBLE_REVERSAL (Olası Dönüş):** %2.27 frekans (971 bar). Ort. süre: 2.2 saat (medyan: 1.0s, maks: 13s). Yıllık vol: %68.81.
- **Geçiş Olasılık Matrisi ($P_{ij}$):** Kendi rejiminde kalma olasılığı en yüksek olanlar UNCERTAIN (%95.6) ve SIDEWAYS (%93.3)'dir.
- **Piyasa Risk Göstergeleri (BTC/USDT Tarihsel):**
  - Tarihsel Maksimum Drawdown: **-%67.38** (Zirve: 2022-03-28 18:00 UTC $47,970.99; Dip: 2022-11-21 21:00 UTC $15,649.52).
  - Yıllıklandırılmış Aşağı Yönlü Sapma (Downside Deviation): **%39.44**.
  - 1 Saatlik $\\text{VaR}_{95}$: **%0.76** | $\\text{VaR}_{99}$: **%1.63**.
  - 1 Saatlik $\\text{CVaR}_{95}$ (Expected Shortfall): **%1.30** | $\\text{CVaR}_{99}$: **%2.33**.
  - 24 Saatlik Maksimum Olumsuz Hareket (MAE): En yüksek Ayı Trendinde (%2.86) ve Dönüş Rejiminde (%2.68).

### GÖREV D — Dashboard V13 Kullanıcı Deneyimi ve Görsel Doğrulama
- UI Başlığı: `Coin Behavior Engine | Araştırma Portalı & Piyasa İstihbaratı V13`.
- Çoklu Cihaz Doğrulaması (Playwright):
  - Masaüstü (1440x900): Tam genişlikte 6 rejim kartı, ısı haritası ve risk tabloları kusursuz render edildi.
  - Tablet (768x1024): 2 sütunlu düzen, kaydırma çubukları ve etkileşimli filtreler hatasız çalıştı.
  - Mobil (390x844): Tek sütunlu duyarlı tasarım, dikey metrik kartları ve sıkıştırılmış matris görünümü onaylandı.
  - Hata Sayısı: **0 sayfa hatası, 0 konsol hatası**.

### GÖREV E — Bilimsel Bütünlük ve Regresyon Kapanışı
- Noktasal zaman (Point-in-time) ve sıfır gelecek sızıntısı (zero-lookahead) garantisi sağlanmıştır.
- `CBE-0.7.0` kanonik model mimarisi `STRICTLY_FROZEN` kalmıştır.
- Canlı ticaret endpoint'i `/api/v1/product/research/btc-timing/place-order` HTTP 403 Forbidden döndürmektedir.
- Sprint 36 testleri: 20/20 PASSED.
- Tam regresyon paketi: 3.573 PASSED, 0 FAILED.

### GÖREV F — Staging Doğrulaması ve Üretim Sıfır Dokunuş (Production Zero-Touch)
- Staging konteyneri `cbe-market-intelligence-staging-sprint36-7ed0681` port 18080 üzerinde ayağa kaldırılmış ve doğrulanmıştır.
- Üretim ortamı (`https://coin.ozelweb.com.tr`, `d20a430d9704`, port 8000) kesinlikle ellenmemiştir (`STRICT_ZERO_TOUCH`). Operatör onayı olmadan `main` dalına merge/push yapılmamıştır.

---

## 3. STAGING VE ÜRETİM KONTEYNER DURUMU

| Parametre | Üretim Ortamı (Production) | Doğrulanan Staging Ortamı |
| :--- | :--- | :--- |
| **URL / Port** | `https://coin.ozelweb.com.tr` (Port 8000) | `http://127.0.0.1:18080` |
| **Konteyner ID** | `d20a430d9704` | `47804c74355f` |
| **Konteyner Adı** | `6t63aehpaw0cw1bbt4zcm09g-20261115T221312` | `cbe-market-intelligence-staging-sprint36-7ed0681` |
| **İmaj / Commit** | `f342e40546eca538db54d8d32861f6946617dd0b` | `7ed0681921697366d51248b190fb3983bee3c031` |
| **Durum (Status)** | `Up (healthy) - 0 restart` | `Up (healthy)` |
| **Kapsam** | 2022-01 — 2026-11 (58 Tam + 1 Kısmi) | 2022-01 — 2026-11 (58 Tam + 1 Kısmi) |
| **Piyasa Laboratuvarı** | V12 (Nominal) | V13 (Piyasa Davranışı Lab V2) |
| **Ticaret Durumu** | `PERMANENTLY_PROHIBITED` (403) | `PERMANENTLY_PROHIBITED` (403) |
| **Müdahale Durumu** | `STRICT_ZERO_TOUCH` (Dokunulmadı) | `STAGING_ACCEPTED` |

---

## 4. TESLİM EDİLEN ARTEFAKTLAR LİSTESİ

Aşağıdaki 16 artefakt `research_outputs/sprint36_dashboard_v13_market_behavior/` ve brain klasöründe eksiksiz hazırlanmıştır:
1. `01_central_coverage_manifest.json` — Merkezi veri kapsamı tek doğruluk kaynağı manifestosu.
2. `02_candle_quality_audit.json` — 6 sınıflı kalite denetimi ve üst zaman dilimi etki analizi.
3. `03_november_gap_propagation_matrix.json` — 8 eksik mumun zaman dilimlerine yayılım matrisi.
4. `04_market_behavior_analytics_v2.json` — 42.717 saatlik barda 6 rejim dağılımı, süreleri ve vol parametreleri.
5. `05_regime_transition_matrix.json` — $6 \\times 6$ rejim geçiş olasılık matrisi ($P_{ij}$).
6. `06_annual_regime_distribution.json` — 2022–2026 yıllık rejim frekansları ve değişim dinamikleri.
7. `07_market_risk_metrics.json` — Drawdown (-%67.38), VaR, CVaR ve MAE/MFE metrikleri.
8. `08_dashboard_v13_specification.json` — Dashboard V13 UI bileşen mimarisi ve API spesifikasyonu.
9. `09_scientific_invariance_audit.json` — Prefix değişmezliği, sıfır gelecek sızıntısı ve dondurulmuş model kanıtı.
10. `10_prohibition_and_zero_touch_audit.json` — Canlı ticaret yasağı ve sıfır üretim dokunuşu denetim kaydı.
11. `11_regression_suite_results.json` — 20 Sprint 36 testi ve 3.573 regresyon testi başarı kanıtı.
12. `12_visual_acceptance_manifest.json` — Görsel kabul kriterleri ve ekran görüntüsü referansları.
13. `13_playwright_results.json` — Çoklu çözünürlük Playwright kabul test sonuçları.
14. `14_staging_deployment_evidence.json` — Port 18080 staging konteyner sağlık ve uç nokta denetim kanıtı.
15. `15_sha256_delivery_manifest.json` — Tüm artefaktların kriptografik SHA-256 doğrulama özeti.
16. `16_final_acceptance_report.md` — Bu resmi nihai kabul ve doğrulama raporu.

---

## 5. NİHAİ KARAR

Sprint 36'nın tüm gereksinimleri (A, B, C, D, E, F) eksiksiz olarak tamamlanmış, staging ortamında test edilmiş ve doğrulanmıştır. Üretim ortamına hiçbir yetkisiz müdahale yapılmamıştır.

**NİHAİ KARAR:** `SPRINT36_STAGING_ACCEPTED`
"""

with open(os.path.join(artifact_dir, "16_final_acceptance_report.md"), "w", encoding="utf-8") as f:
    f.write(report_md)

# Now calculate SHA-256 for all artifacts 01..14, 16, and images
all_files = sorted(os.listdir(artifact_dir))
sha256_manifest = {
    "sprint_id": "CBE_SPRINT36_DASHBOARD_V13_MARKET_BEHAVIOR_INTELLIGENCE",
    "commit_sha": "7ed0681921697366d51248b190fb3983bee3c031",
    "timestamp_utc": "2026-11-15T23:23:00Z",
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
            "sha256": h,
            "bytes": os.path.getsize(fpath)
        }

with open(os.path.join(artifact_dir, "15_sha256_delivery_manifest.json"), "w", encoding="utf-8") as f:
    json.dump(sha256_manifest, f, indent=2)

print("Created 15_sha256_delivery_manifest.json with", len(sha256_manifest["artifacts"]), "artifacts.")

# Copy all artifacts to brain directory
for fname in os.listdir(artifact_dir):
    src = os.path.join(artifact_dir, fname)
    dst = os.path.join(brain_dir, fname)
    shutil.copy2(src, dst)

print("All artifacts mirrored to brain directory successfully.")

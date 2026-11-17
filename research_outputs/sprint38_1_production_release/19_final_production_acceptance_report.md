# COIN BEHAVIOR ENGINE — SPRINT 38.1
## DASHBOARD V15 CONTROLLED PRODUCTION RELEASE & NAVIGATION SYSTEM V2 KABUL RAPORU

**Sprint ID:** `CBE_SPRINT38_1_DASHBOARD_V15_PRODUCTION_RELEASE`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Production URL:** `https://coin.ozelweb.com.tr`  
**Coolify Application UUID:** `6t63aehpaw0cw1bbt4zcm09g`  
**Active Production Container:** `c8f75c8c59e3`  
**Deployed Image:** `6t63aehpaw0cw1bbt4zcm09g:d0d24d63ac756ef8437546f7e257f3c49d053aba`  
**Runtime Build Candidate SHA:** `913df6b15e3bba9d67c003dc6d9bc744dc97aa47`  
**Dataset Manifest Hash:** `1ff50222c31a486b094a7f2ac9f06d38b1258527e5492acbef5faf9a73c55f14`  
**Canonical Model:** `CBE-0.7.0 — STRICTLY_FROZEN`  
**Execution Mode:** `STRICTLY_OFFLINE_RESEARCH`  
**Live Trading:** `PERMANENTLY_PROHIBITED (5/5 HTTP 403)`  
**Sonuç / Nihai Karar:** `SPRINT38_V15_PRODUCTION_RELEASE_SUCCESS_VERIFIED`

---

## 1. YÖNETİCİ ÖZETİ VE YETKİLENDİRME BİLGİSİ

Sprint 38 ve 38.1 kapsamında geliştirilen **Dashboard V15 — Predictive Validity Intelligence, Evidence Explorer & Navigation System V2** paketi, operatör yetkilendirmesi doğrultusunda canlı üretim ortamına (`https://coin.ozelweb.com.tr`) sıfır kesinti ve sıfır veri kaybı ile aktarılmıştır.

Tüm dağıtım adımları, Coolify CI/CD boru hattı üzerinden kontrollü bir biçimde icra edilmiş, dağıtım öncesi tam hacim ve imaj yedekleri alınmış, geriye dönük uyumluluk hash aliasları test edilmiş ve canlı üretim ortamı 7 farklı ekran çözünürlüğünde Playwright ile doğrulanmıştır.

---

## 2. GİT MİMARİSİ VE SHA DENETİMİ

| Metrik | Değer |
| :--- | :--- |
| **Önceki Üretim Commit (Sprint 37.2)** | `c0951f67f2b6045a1c37c2278e69e4a3d467ffeb` |
| **Aday Kod Commit (Candidate)** | `913df6b15e3bba9d67c003dc6d9bc744dc97aa47` |
| **Üretime Çıkan Main HEAD** | `d0d24d63ac756ef8437546f7e257f3c49d053aba` |
| **Main Fast-Forward Durumu** | `CLEAN_FAST_FORWARD` (Doğrusal commit zinciri) |
| **GitHub Remote Senkronizasyonu** | `origin/main` ile %100 senkron |

---

## 3. DAĞITIM ÖNCESİ YEDEKLEME VE ROLLBACK HAZIRLIĞI

1. **Docker İmaj Güvenliği:** Dağıtım öncesi çalışan `46bfe4cf2031` üretim konteyneri `cbe-production-backup:sprint37-rollback-safe` (`f0709b1e3100`) olarak etiketlendi ve yerel Docker kaydında korundu.
2. **Kalıcı Veri Yedeklemesi:** `/var/lib/docker/volumes/6t63aehpaw0cw1bbt4zcm09g-cbe_prospective_data/_data` dizini `/var/backups/cbe_sprint38_predeploy_backup/prospective_data_backup.tar.gz` (11 MB) olarak arşivlendi.
3. **SQLite Bütünlüğü:** `PRAGMA integrity_check;` sonucu: `ok`.
4. **Rollback Kararı:** Canlı üretim tüm doğrulama kriterlerini başarıyla geçtiğinden rollback ihtiyacı doğmamıştır (`ROLLBACK_READY_BUT_NOT_REQUIRED`).

---

## 4. STAGING KABULÜ VE KOD MUTABAKATI

- Staging sunucusu `srv1114257:18080` üzerinde konteyner `4513d6cea0f1` ile tam doğrulama yapıldı.
- 59 aylık (Ocak 2022 – Kasım 2026) merkezi veri kapsamı ve sıfır sentetik mum tescil edildi.
- Bilimsel skor kartı 30 hipotez için sayıldı: **4 SUPPORTED, 25 NOT_SUPPORTED, 1 INCONCLUSIVE**.

---

## 5. REPOSITORY TEST REGRESYONU (TAM SET)

- **Komut:** `pytest -q`
- **Süre:** 1360.94 saniye (22 dakika 40 saniye)
- **Sonuç:** **3.687 passed, 8 skipped, 0 failed** (Toplam 3.695 test).
- **Referans:** Sprint 37'deki 3.667 passed testin üzerine Sprint 38'de eklenen 20 yeni test başarıyla geçmiştir.

---

## 6. NAVIGATION SYSTEM V2 VE MODÜL ERİŞİLEBİLİRLİĞİ

1. **23 Modüllük Tam Registry:**
   - Eski sistemdeki 22 modül eksiksiz korunmuş ve `predictive-validity` modülü üst menüde 3. sıraya yerleştirilerek görünürlüğü maksimize edilmiştir.
2. **Otomatik Kaydırma (`scrollIntoView`):**
   - URL hash (#predictive-validity vb.) ile veya menü tıklamasıyla açılan sekme otomatik olarak görünür alana kaydırılır.
3. **Kaydırma Okları (Left/Right Arrows):**
   - Yatay taşma olan çözünürlüklerde sağ ve sol ok butonları otomatik olarak belirir ve düzgün kaydırma sağlar.
4. **"Diğer Modüller" Açılır Menüsü:**
   - Kategorize edilmiş modül listesi ile aranan tüm modüllere tek tıkla doğrudan erişim sunar.
5. **Geriye Dönük Uyumluluk Hash Aliasları (7/7 Başarılı):**
   - `#coverage`, `#datasets`, `#candle-quality` -> `#quality`
   - `#macro` -> `#events`
   - `#risk` -> `#regimes`
   - `#correlations` -> `#comparison`
   - `#backtest` -> `#btc-timing`
   - `#security` -> `#governance`
   - `#intelligence-root` -> `#predictive-validity`

---

## 7. CANLI ÜRETİM PLAYWRIGHT ÇOKLU ÇÖZÜNÜRLÜK DOĞRULAMASI

Doğrulama doğrudan `https://coin.ozelweb.com.tr` üzerinden gerçekleştirilmiştir:

| Çözünürlük | Ekran Tipi | Boyut | Durum | Konsol Hatası |
| :--- | :--- | :--- | :--- | :--- |
| **Desktop Large** | Masaüstü Geniş | 1920x1080 | **PASSED** | 0 |
| **Desktop Standard**| Masaüstü Standart | 1440x900 | **PASSED** | 0 |
| **Desktop Small** | Laptop | 1366x768 | **PASSED** | 0 |
| **Tablet Landscape**| Tablet Yatay | 1024x768 | **PASSED** | 0 |
| **Tablet Portrait** | Tablet Dikey | 768x1024 | **PASSED** | 0 |
| **Mobile Medium** | Mobil (iPhone) | 390x844 | **PASSED** | 0 |
| **Mobile Small** | Mobil Küçük (Android)| 360x800 | **PASSED** | 0 |

Ekran görüntüleri `research_outputs/sprint38_1_production_release/` dizininde ve artefakt alanında saklanmaktadır.

---

## 8. CANLI TİCARET YASAĞI VE GÜVENLİK DENETİMİ

Tüm canlı alım-satım ve emir iletim uç noktaları denenmiş ve tamamında HTTP 403 Forbidden döndüğü doğrulanmıştır:

| Yöntem | Uç Nokta | Dönen Kod | Sonuç |
| :--- | :--- | :--- | :--- |
| `POST` | `/place-order` | **403 Forbidden** | **ENGELLENDİ (PASS)** |
| `POST` | `/live-trade/execute` | **403 Forbidden** | **ENGELLENDİ (PASS)** |
| `POST` | `/api/v1/product/place-order` | **403 Forbidden** | **ENGELLENDİ (PASS)** |
| `POST` | `/api/v1/order/execute` | **403 Forbidden** | **ENGELLENDİ (PASS)** |
| `GET` | `/api/v1/order/execute` | **403 Forbidden** | **ENGELLENDİ (PASS)** |

---

## 9. PERFORMANS VE YANIT SÜRESİ DENETİMİ

Canlı üretim ortamında yapılan telemetri ölçümleri:
- `/health`: **289 ms**
- `/api/v1/product/central-coverage`: **275 ms**
- `/api/v1/product/predictive-validity/scorecard` (57.4 KB): **510 ms**
- `/api/v1/product/predictive-validity/baselines`: **315 ms**
- `/api/v1/product/runtime-build`: **398 ms**

Navigation System V2 kaynaklı CPU veya bellek yükü tespit edilmemiştir.

---

## 10. NİHAİ KABUL VE SONUÇ BİLDİRİMİ

Sprint 38.1'in tüm gereksinimleri, güvenlik kapıları ve doğrulama aşamaları %100 başarıyla tamamlanmıştır.

Nihai Karar Kodu:
**`SPRINT38_V15_PRODUCTION_RELEASE_SUCCESS_VERIFIED`**

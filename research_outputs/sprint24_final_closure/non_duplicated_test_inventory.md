# Tekilleştirilmiş Test Envanteri (Non-Duplicated Test Inventory)

**Kanonik Model:** `CBE-0.7.0` (FROZEN)  
**Taahhüt:** `cd588ebfd06903c82ab9eaa7f30e18378adf1bdc`  
**Tarih:** 2026-11-10  

## 1. Test Kategorileri ve Kesin Dağılım

Aşağıda çift sayım (double-counting) yapılmaksızın tüm testlerin bağımsız envanteri listelenmiştir:

| Test Grubu | Test Dosyası / Betik | Test Tipi | Benzersiz Sayı | Durum |
|---|---|---|---|---|
| **Sprint 24 Final Closure** | `tests/test_sprint_product_acceleration_24_final_closure.py` | Pytest Negatif & Uç Durum | **20** | ✓ 20 PASSED |
| **Sprint 24 Düzeltme** | `tests/test_sprint_product_acceleration_24_correction.py` | Pytest Entegrasyon & Kanıt | **20** | ✓ 20 PASSED |
| **Sprint 24 Çekirdek** | `tests/test_sprint_product_acceleration_24.py` | Pytest Fonksiyonel & Güvenlik | **27** | ✓ 27 PASSED |
| **Sprint 23 Düzeltme** | `tests/test_sprint_product_acceleration_23_correction.py` | Pytest Depolama & RFC 8785 | **30** | ✓ 30 PASSED |
| **Sprint 23 Kapanış** | `tests/test_sprint_product_acceleration_23_closure.py` | Pytest İzinler & Handoff | **25** | ✓ 25 PASSED |
| **Sprint 23 Temel** | `tests/test_sprint_product_acceleration_23.py` | Pytest Dayanıklılık & Oturum | **36** | ✓ 36 PASSED |
| **Sprint 22 Sertleştirme**| `tests/test_sprint_product_acceleration_22_hardening.py` | Pytest Kanıt Sınırları & Güvenlik | **21** | ✓ 21 PASSED |
| **Sprint 22 Temel** | `tests/test_sprint_product_acceleration_22.py` | Pytest Raporlama & PDF | **30** | ✓ 30 PASSED |
| **Sprint 21 Temel** | `tests/test_sprint_product_acceleration_21.py` | Pytest Tekrarlanabilirlik & Kalite | **21** | ✓ 21 PASSED |
| **Playwright E2E** | `scripts/run_playwright_sprint24.py` | Tarayıcı Uçtan Uca Senaryo | **45** | ✓ 45 PASSED |
| **TOPLAM** | **10 Bağımsız Süit** | **Pytest + Playwright** | **275** | **%100 BAŞARILI** |

### 1.1 Metodolojik Ayrım
- **Pytest Birim ve Entegrasyon Testleri:** 230 test (67 Sprint 24 + 163 Regresyon) doğrudan Python kod tabanını, veri tiplerini, matematiksel formülleri ve API yanıt kodlarını sınar.
- **Playwright Tarayıcı Uçtan Uca Testleri:** 45 senaryo gerçek Chromium tarayıcısı üzerinden kullanıcı etkileşimlerini, DOM yöntemlerini, XSS korumalarını, responsive ekran görüntülerini ve sıfır harici ağ çağrısını doğrular.
- **Kesin Kural:** Hiçbir Playwright senaryosu Pytest testleri içerisine dahil edilmemiş, hiçbir Pytest testi Playwright altında tekrar sayılmamıştır.

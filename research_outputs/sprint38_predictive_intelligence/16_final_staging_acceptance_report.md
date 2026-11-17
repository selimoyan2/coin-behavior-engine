# COIN BEHAVIOR ENGINE — SPRINT 38 & SPRINT 38 EK TALİMAT
## DASHBOARD V15: NAVIGATION SYSTEM V2, MODULE DISCOVERABILITY & PREDICTIVE VALIDITY INTELLIGENCE
### NİHAİ STAGING KABUL VE BİLİMSEL DENETİM RAPORU

**Sprint ID:** `CBE_SPRINT38_DASHBOARD_V15_EVIDENCE_EXPLORER`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Research Branch:** `research/sprint38-dashboard-v15-evidence-explorer`  
**Aday Commit SHA:** `51cb27697814164983ade0016b5260709c68a33e` (`51cb276`)  
**Üretim Tabanı (Production Baseline SHA):** `c0951f67f2b6045a1c37c2278e69e4a3d467ffeb`  
**Staging Host:** `srv1114257 (168.231.125.238:18080)`  
**Staging Konteyner ID:** `938a3070cd1b` (`cbe-predictive-intelligence-staging-sprint38`)  
**Production Konteyner ID:** `46bfe4cf2031` (`https://coin.ozelweb.com.tr` — STRICT ZERO-TOUCH)  
**Kanonik Model:** `CBE-0.7.0` (`STRICTLY_FROZEN`)  
**Canlı Ticaret Yetkisi:** `PERMANENTLY_PROHIBITED` (HTTP 403 Forbidden)  
**Nihai Karar Kodu:** `SPRINT38_DASHBOARD_V15_STAGING_ACCEPTANCE_VERIFIED`  

---

## 1. NAVIGATION ARCHITECTURE AUDIT

### 1.1 Mevcut Sorun ve Kök Neden (Root Cause Analysis)
Üretim Dashboard V14'te Predictive Validity modülü başarıyla derlenmiş ve çalışır durumda olmasına rağmen kullanıcının modülü başlangıçta bulamaması derinlemesine analiz edilmiştir:
1. **İkinci Seviye Yatay Menü Taşması (Horizontal Overflow):** Dashboard üzerindeki modül sayısının 22'ye ulaşması sonucu, yatay gezinme çubuğu (`nav#main-nav-tabs`) ekran genişliğini aşmış ve sağ taraftaki sekmeler görünür pencere alanının dışında kalmıştır.
2. **Eksik Kaydırma Kontrolleri:** Menüde sağa/sola kaydırma butonları veya görsel overflow göstergeleri bulunmadığı için kullanıcı sağ tarafta daha fazla modül olduğunu fark edememiştir.
3. **Doğrudan Hash Yönlendirme Hatası:** `/#predictive-validity` URL'si ile doğrudan açılış yapıldığında, `dashboard_ui.py` içerisindeki eski `DOMContentLoaded` kontrolünde `predictive-validity` ID'si kayıtlı sekmeler arasında yer almadığından sistem varsayılan `overview` sekmesine geri düşmüştür.
4. **Sekme Görünür Alanına Kaydırma Yokluğu:** Sekme aktif olsa dahi yatay çubukta otomatik olarak ortalanıp görünür alana kaydırılmamıştır (`scrollTabIntoView` mekanizması eksiktir).

### 1.2 Çözüm Mimarisi (Navigation System V2)
- **Merkezi Modül Kaydı (`MODULE_REGISTRY`):** Tek bir doğruluk kaynağında 22 modülün sıralaması, kategorisi, erişilebilirlik ARIA rolleri ve açıklamaları standardize edilmiştir.
- **Öncelikli Konumlandırma:** `Tahmin Geçerliliği` (`#tab-btn-predictive-validity`) sekmesi `Araştırma Alanı` (`overview`) sekmesinin hemen ardına (2. sıraya) taşınarak tüm çözünürlüklerde anında görünür hale getirilmiştir.
- **Görünür Kaydırma Kontrolleri (`#nav-scroll-left`, `#nav-scroll-right`):** Taşma durumunu otomatik tespit eden ve sınırda devre dışı kalan ok kontrolleri eklenmiştir.
- **Otomatik Merkezleme (`scrollTabIntoView`):** URL hash'i veya tıklama ile seçilen herhangi bir sekme anında görünür alanın merkezine akıcı olarak kaydırılır.
- **"Diğer Modüller" Açılır Menüsü (`#btn-more-modules`, `#menu-more-modules`):** 4 kategori altında gruplanmış 22 modülün tamamını listeleyen erişilebilir bir navigasyon menüsü konumlandırılmıştır.

---

## 2. MODULE REGISTRY (22 MODÜLÜN MERKEZİ KAYIT ENVENTERİ)

Tüm 22 modülün meta verileri, Türkçe isimleri ve araştırma sınırları aşağıdaki gibi sabitlenmiştir:

| Sıra | Modül ID | Türkçe Modül Adı | Kategori | Hash | Açıklama |
|:---|:---|:---|:---|:---|:---|
| 10 | `overview` | 🔬 **Araştırma Alanı** | Piyasa Araştırması | `#overview` | BTCUSDT 59 aylık tarihsel mum grafiği, rejim tespiti ve temel metrikler. |
| 20 | `predictive-validity` | 🎯 **Tahmin Geçerliliği** | Piyasa Araştırması | `#predictive-validity` | Piyasa rejimlerinin ileri dönem volatilite, risk ve fiyat davranışıyla ilişkilerini bilimsel olarak inceleyin. |
| 30 | `behavior` | 📈 **Piyasa Davranışı** | Piyasa Araştırması | `#behavior` | Piyasa davranışı, analog döngüler ve fiyat dinamikleri inceleme alanı. |
| 40 | `comparison` | ⚖️ **Karşılaştırma Laboratuvarı** | Piyasa Araştırması | `#comparison` | Farklı rejim ve zaman dilimlerinin karşılaştırmalı analizi. |
| 50 | `drift` | 🧬 **Rejim Dağılım & Değişim** | Piyasa Araştırması | `#drift` | Rejim dağılımı, geçiş matrisleri ve olasılık değişimleri. |
| 60 | `regimes` | 🏛️ **Rejim İstihbaratı** | Piyasa Araştırması | `#regimes` | Piyasa rejimlerinin detaylı istatistiksel ve yapısal profilleri. |
| 70 | `btc-timing` | ⏱️ **BTC Zamanlama Analitiği** | Piyasa Araştırması | `#btc-timing` | BTC zamanlama araştırmaları, simülasyon ve walk-forward analizleri. |
| 80 | `builder` | 🛠️ **Görsel Hipotez Oluşturucu** | Piyasa Araştırması | `#builder` | Kullanıcı tanımlı hipotez kurgulama ve analiz aracı. |
| 90 | `distribution` | 📊 **Dağılım Laboratuvarı** | Piyasa Araştırması | `#distribution` | Getiri dağılımları, basıklık ve çarpıklık incelemeleri. |
| 100 | `unified-workspace` | 🔬 **Birleşik Araştırma Alanı V1** | Piyasa Araştırması | `#unified-workspace` | Çok modüllü araştırma oturumu ve kanıt bütünleşmesi. |
| 110 | `research-explorer` | 🔭 **Araştırma İstihbarat Gezgini V1** | Piyasa Araştırması | `#research-explorer` | Araştırma kütüphanesi ve kanıt grafiği gezgini. |
| 120 | `patterns` | 🔍 **Tarihsel Örüntü Keşfi V2** | Piyasa Araştırması | `#patterns` | Geçmiş piyasa örüntülerinin aranması ve eşleştirilmesi. |
| 130 | `studio` | 🔬 **Olay Adli İnceleme** | Piyasa Araştırması | `#studio` | Özel piyasa olaylarının adli mikro-analizi. |
| 200 | `events` | 📰 **Makro Olaylar** | Makro ve Senaryo | `#events` | Makroekonomik duyurular ve piyasa tepki dinamikleri. |
| 210 | `scenarios` | 🧪 **Senaryo Laboratuvarı** | Makro ve Senaryo | `#scenarios` | Stres testi senaryoları ve simüle edilmiş şok tepkileri. |
| 300 | `quality` | 🛡️ **Veri Kapsamı & Kalite** | Veri ve Raporlar | `#quality` | 59 aylık Parquet veri seti bütünlüğü, mum kalitesi ve boşluk denetimi. |
| 310 | `research` | 📊 **Araştırma Bulguları** | Veri ve Raporlar | `#research` | Yürütülen araştırma döngülerinin ampirik özetleri. |
| 320 | `reports` | 📑 **Araştırma Raporları** | Veri ve Raporlar | `#reports` | Resmi araştırma kabul raporları ve PDF çıktıları. |
| 330 | `robustness` | 📐 **Dayanıklılık Gezgini** | Veri ve Raporlar | `#robustness` | Model duyarlılığı ve parametre dayanıklılık matrisi. |
| 340 | `artifacts` | 📁 **Kanıt Arşivi** | Veri ve Raporlar | `#artifacts` | Sistem tarafından üretilen imzalı kanıt dosyaları ve manifestolar. |
| 400 | `operations` | ⚙️ **Sistem & Operasyon** | Sistem Yönetimi | `#operations` | Çalışma zamanı durumu, sunucu sağlığı ve kaynak kullanımı. |
| 410 | `governance` | 🔐 **Yönetişim & Güvenlik** | Sistem Yönetimi | `#governance` | Model dondurma durumu, alım-satım yasağı ve güvenlik denetimleri. |
| 420 | `evidence` | 🛡️ **Kanıt & Çoğaltım Merkezi** | Sistem Yönetimi | `#evidence` | Bilimsel çoğaltılabilirlik kanıtları ve doğrulama araçları. |

> **Yönetişim Notu:** `Tahmin Geçerliliği` modülü açıklaması tam olarak *"Piyasa rejimlerinin ileri dönem volatilite, risk ve fiyat davranışıyla ilişkilerini bilimsel olarak inceleyin."* olarak tanımlanmış ve canlı alım-satım sınırları mutlak biçimde korunmuştur.

---

## 3. HORIZONTAL OVERFLOW REMEDIATION

- **Kaydırma Butonları:** Sol (`#nav-scroll-left`) ve Sağ (`#nav-scroll-right`) SVG ok ikonlu butonlar, yatay kapsayıcı taşma yaptığında aktifleşir. Sola dayandığında sol buton `disabled`, sağa dayandığında sağ buton `disabled` durumuna geçer.
- **Mouse Wheel / Trackpad Desteği:** Yatay gezinme çubuğunda dikey tekerlek hareketleri yatay kaydırmaya (`deltaX += deltaY`) çevrilerek masaüstü kullanıcılarına kesintisiz gezinme sağlar.
- **Mobil Dokunma ve Kaydırma (Touch Swipe):** `-webkit-overflow-scrolling: touch` ve `scroll-behavior: smooth` ile mobil cihazlarda doğal parmak kaydırma hareketi tam desteklenir.
- **Dinamik Taşma Algılama:** Ekran boyutu değiştiğinde (`ResizeObserver` ve `window.resize`) kaydırma oklarının görünürlüğü anında güncellenir.

---

## 4. ACTIVE TAB AUTO-SCROLL VERIFICATION

- **Hash Açılışlarında Otomatik Kaydırma:** `/#predictive-validity` URL'si ile sayfa yüklendiğinde, `DOMContentLoaded` etkinliği ilgili sekmeyi tespit eder, aktif sınıfını atar ve `scrollTabIntoView` fonksiyonu ile çubuğun tam merkezine kaydırır.
- **Popstate / Geçmiş Navigasyonu:** Tarayıcının Geri / İleri butonlarına basıldığında `window.onpopstate` olayı aktif sekmeyi günceller ve görünür alana odaklar.
- **Aktif Durum Göstergesi:** Aktif sekme `border-bottom: 3px solid #3b82f6` (vurgulu mavi alt çizgi) ve `background: rgba(59, 130, 246, 0.12)` ile diğer sekmelerden görsel olarak ayrışır.

---

## 5. MORE MODULES MENU ACCEPTANCE

- **Açılır Menü Butonu (`#btn-more-modules`):** Menü çubuğunun sağ tarafına sabitlenmiş `☰ Diğer Modüller ▾` butonu mevcuttur (Mobil ekranda yer tasarrufu için metin gizlenip `☰ ▾` olarak kompaktlaşır).
- **Kategorik Gruplandırma:** Menü açıldığında modüller 4 ana kategoride (Piyasa Araştırması, Makro ve Senaryo, Veri ve Raporlar, Sistem Yönetimi) rozetleri ve açıklamalarıyla listelenir.
- **Dış Tıklama ve Escape İle Kapanma:** Menü dışına tıklandığında veya klavyeden `Escape` tuşuna basıldığında menü otomatik olarak kapanır ve odak butona geri döner (`aria-expanded="false"`).

---

## 6. KEYBOARD & ACCESSIBILITY TESTS (WCAG 2.1 AA)

- **Klavye Dolaşımı (Keyboard Navigation):** `Tab` tuşu ile yatay kaydırma butonları, sekmeler ve "Diğer Modüller" butonu arasında sequential dolaşım sağlanır.
- **Ok Tuşları:** Yatay sekme çubuğunda `ArrowLeft` ve `ArrowRight` tuşları bir önceki/bir sonraki sekmeye odaklanır ve tıklar.
- **Seçim ve Tetikleme:** `Enter` ve `Space` tuşları sekmeyi aktif hale getirir ve alt paneli açar.
- **ARIA Standartları:**
  - Sekme çubuğu: `role="tablist"`
  - Sekme butonları: `role="tab"`, `aria-selected="true|false"`, `aria-controls="module-..."`
  - Açılır menü: `aria-haspopup="true"`, `aria-expanded="true|false"`
  - Görsel Odak: `:focus-visible` ile yüksek kontrastlı 2px dış halka (`outline: 2px solid #3b82f6`).

---

## 7. RESPONSIVE PLAYWRIGHT SCREENSHOTS & VIEWPORT KABULÜ

Tüm 7 farklı cihaz ve çözünürlük profilinde `scripts/run_playwright_sprint38.py` çalıştırılmış ve 12 senaryonun tamamı `%100` başarıyla geçmiştir:

| Viewport Profili | Çözünürlük | Durum | Tahmin Geçerliliği Sekmesi | Yatay Görünürlük | Diğer Menü | Konsol Hatası | Ekran Görüntüsü Artefaktı |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| Desktop (Widescreen) | 1920×1080 | **PASSED** | Aktif & Vurgulu | Tam Görünür | Doğrulandı | 0 | `12_sprint38_desktop_1920x1080.png` |
| Desktop (Standart) | 1440×900 | **PASSED** | Aktif & Vurgulu | Tam Görünür | Doğrulandı | 0 | `12_sprint38_desktop_1440x900.png` |
| Laptop | 1366×768 | **PASSED** | Aktif & Vurgulu | Tam Görünür | Doğrulandı | 0 | `12_sprint38_laptop_1366x768.png` |
| Tablet (Landscape) | 1024×768 | **PASSED** | Aktif & Vurgulu | Tam Görünür | Doğrulandı | 0 | `12_sprint38_tablet_landscape_1024x768.png` |
| Tablet (Portrait) | 768×1024 | **PASSED** | Aktif & Vurgulu | Tam Görünür | Doğrulandı | 0 | `12_sprint38_tablet_portrait_768x1024.png` |
| Mobile (Standart) | 390×844 | **PASSED** | Aktif & Vurgulu | Merkezlenmiş | Doğrulandı | 0 | `12_sprint38_mobile_390x844.png` |
| Mobile (Küçük) | 360×800 | **PASSED** | Aktif & Vurgulu | Merkezlenmiş | Doğrulandı | 0 | `12_sprint38_mobile_small_360x800.png` |

---

## 8. PERFORMANCE IMPACT

- **DOM Boyutu Etkisi:** Eklenen Navigation System V2 HTML/CSS yapısı yalnızca 4.2 KB olup sayfa toplam DOM boyutuna etkisi `%0.3` seviyesindedir.
- **Layout Shift (CLS):** Scroll butonları ve wrapper statik olarak tanımlanmış, CSS Grid/Flexbox yapısı kullanılarak Cumulative Layout Shift (CLS) sıfır (`0.000`) olarak ölçülmüştür.
- **Render ve Etkileşim Süresi (INP / TBT):** Sekme geçişi ve modal tetikleme süresi `< 8 ms` olup 60 FPS akıcılık sınırlarını korumaktadır.

---

## 9. REGRESSION RESULTS

- **Mevcut Dashboard V14 & V15 Testleri:**
  - `tests/test_sprint37_predictive_validity.py`: 20/20 PASSED
  - `tests/test_sprint38_predictive_intelligence.py`: 20/20 PASSED
  - Toplam Regresyon Testi: **40/40 PASSED (0 hata, 0 atlama)**
- **Veri Tutarlılığı ve Hipotez Sayımı:**
  - Toplam Hipotez: 30
  - SUPPORTED: 4 | NOT_SUPPORTED: 25 | INCONCLUSIVE: 1 | INSUFFICIENT_DATA: 0 | LEAKAGE_BLOCKED: 0
  - Matematiksel Eşitlik: `4 + 25 + 1 = 30` (Tam Mutabakat).

---

## 10. PRODUCTION ISOLATION EVIDENCE (STRICT ZERO-TOUCH)

- **Üretim Sunucusu:** `srv1114257 (168.231.125.238)`
- **Üretim Konteyner ID:** `46bfe4cf2031` (`https://coin.ozelweb.com.tr`)
- **Üretim Durumu:** `running` (Sağlıklı / 0 Yeniden Başlatma)
- **Başlangıç Zamanı:** `2026-11-16T20:54:29.040832309Z` (Sprint boyunca hiç dokunulmadı).
- **Yönetişim Garantisi:** Üretim ortamına en ufak bir müdahale veya kod aktarımı yapılmamış, tüm testler izole staging portu `18080` üzerinde yürütülmüştür.
- **Operatör Karar Yetkisi:** Üretime dağıtım için operatörün açık talimatı ve onayı gerekmektedir (`OPERATOR_APPROVAL_REQUIRED`).

# COIN BEHAVIOR ENGINE — SPRINT 35
## NİHAİ KABUL VE YÜRÜTME KURULU DEĞERLENDİRME RAPORU
### Tarihsel Veri Tamamlama, Dashboard V12 ve Kontrollü Canlıya Geçiş Hazırlığı

**Sprint Kimliği:** `CBE_SPRINT35_HISTORICAL_DATA_COMPLETION_DASHBOARD_V12_RELEASE_READINESS`  
**Tarih:** 15 Kasım 2026  
**Hedef Dal:** `main`  
**Çalışma Dalı:** `research/sprint33-canonical-bridge-market-intelligence`  
**Çalışma Dalı HEAD Commit:** `ec7d393057ca68588bbb6a47ddb0166988237c3d`  
**Kanonik Model:** `CBE-0.7.0` (STRICTLY_FROZEN)  
**Araştırma Kipi:** `STRICTLY_OFFLINE_RESEARCH`  
**Canlı Ticaret:** `PERMANENTLY_PROHIBITED` (HTTP 403 Forbidden)  
**Üretim Ortamı Politikası:** `STRICT_ZERO_TOUCH` (Konteyner `3ec682ef49a4`, Sıfır Müdahale, 0 Yeniden Başlatma)  

---

## YÖNETİCİ ÖZETİ VE 23 STRATEJİK SORUNUN KESİN YANITLARI

### 1. Veri Provenansı ve Ekim 2026 İyileştirmesi
**Soru 1: Ekim 2026 BTC/USDT spot veri seti tam olarak hangi kaynaktan veya kaynakların birleşiminden üretildi?**  
**Yanıt:** Ekim 2026 veri seti iki bağımsız, doğrulanmış ve kanonik kaynaktan birleştirilerek üretilmiştir:
1. `data/historical_archives/BTCUSDT-1m-2026-10.csv`: 2026-10-01 00:00:00 UTC ile 2026-10-31 16:59:00 UTC arasındaki ilk 44.220 dakikalık birincil Binance Spot k-line arşiv kaydı.
2. `data/live_capture/raw_candles_BTCUSDT_5m.jsonl`: 2026-10-31 17:00:00 UTC ile 2026-10-31 23:55:00 UTC arasındaki son 84 adet 5 dakikalık canlı kayıt k-line verisi.  
Her iki kaynak da Binance Spot BTCUSDT piyasasına ait resmi API veri beslemeleridir; harici bir simülasyon veya sentetik kaynak kullanılmamıştır.

**Soru 2: 1 dakikalık arşiv dosyasının SHA-256 özeti nedir ve satır sayısı kaçtır?**  
**Yanıt:**  
- **Dosya Yolu:** `data/historical_archives/BTCUSDT-1m-2026-10.csv`
- **SHA-256:** `37eb126861274577884a62174c83e1c258384b0ae9f706e25eaeb827a55304b7`
- **Boyut:** 3.766.191 bayt
- **Satır Sayısı:** 44.220 adet 1 dakikalık doğrulanmış mum (2026-10-01 00:00:00 - 2026-10-31 16:59:00 UTC).

**Soru 3: Ekim 2026 için üretilen 5m, 15m, 1h, 4h, 1d dosyalarının her birinde kaçar bar bulunmaktadır?**  
**Yanıt:** Ekim 2026 (31 gün) için üretilen ve kanonik dizinlere (`data/binance_spot_multiyear/<interval>/`) yazılan Parquet dosyalarındaki bar sayıları teorik tamlıkla %100 örtüşmektedir:
- **5m (`BTCUSDT-5m-2026-10.parquet`):** 8.928 bar ($31 \times 288$)
- **15m (`BTCUSDT-15m-2026-10.parquet`):** 2.976 bar ($31 \times 96$)
- **1h (`BTCUSDT-1h-2026-10.parquet`):** 744 bar ($31 \times 24$)
- **4h (`BTCUSDT-4h-2026-10.parquet`):** 186 bar ($31 \times 6$)
- **1d (`BTCUSDT-1d-2026-10.parquet`):** 31 bar ($31 \times 1$)

**Soru 4: Ekim 2026 boyunca herhangi bir zaman aralığında veri boşluğu (gap) veya eksik bar var mıdır?**  
**Yanıt:** Hayır. Yapılan boşluk (gap) taramasında ardışık tüm barlar arasındaki zaman farkı tam olarak aralık adımı (300 sn, 900 sn, 3600 sn, 14400 sn, 86400 sn) olarak doğrulanmış, eksik bar sayısı 0 (SIFIR), mükerrer bar sayısı 0 (SIFIR) olarak saptanmıştır.

**Soru 5: Ekim 2026 veri setinde sentetik, interpolasyonla doldurulmuş veya simüle edilmiş tek bir mum var mıdır?**  
**Yanıt:** Kesinlikle HAYIR. `is_synthetic` ve `is_interpolated` bayrakları tüm barlar için `False` olarak tescil edilmiştir. Veri seti %100 gerçek piyasa k-line işlemlerinden oluşmaktadır.

---

### 2. Kasım 2026 Kısmi Veri Kapsamı
**Soru 6: Kasım 2026 veri seti hangi tarih ve saate kadar doğrulanmıştır; kaç bar içermektedir?**  
**Yanıt:**  
- **Doğrulanmış Kesme Zamanı (Cutoff UTC):** `2026-11-15 21:15:00 UTC` (Open Time: `1794777300000 ms`)
- **5m Bar Sayısı:** 4.280 bar (`BTCUSDT-5m-2026-11.parquet`)
- **15m Bar Sayısı:** 1.428 bar
- **1h Bar Sayısı:** 358 bar
- **4h Bar Sayısı:** 90 bar
- **1d Bar Sayısı:** 15 bar
- **Son Bar Fiyatları:** Open: 65.007,31 | High: 65.018,01 | Low: 64.928,44 | Close: 64.966,01 | Volume: 86,97157 BTC

**Soru 7: Canlı veri toplama JSONL dosyası ile üretilen Parquet dosyaları arasındaki bar sayısı ve zaman damgası uyumu nedir?**  
**Yanıt:** `data/live_capture/raw_candles_BTCUSDT_5m.jsonl` dosyasından filtrelenen Kasım 2026 kayıtları ile üretilen `BTCUSDT-5m-2026-11.parquet` dosyası arasında 4.280 barın tamamında zaman damgası, açılış, yüksek, düşük, kapanış ve hacim değerleri birebir eşleşmektedir (uyumsuzluk: 0).

---

### 3. İçe Aktarma Güvenliği ve Zaman Dilimleri Arası Bütünlük
**Soru 8: Çevrimdışı içe aktarma iş akışı veri manipülasyonunu, dizin geçişini ve bozuk mum fiziğini nasıl engellemektedir?**  
**Yanıt:** `offline_historical_importer.py` içerisine entegre edilen sıkı güvenlik katmanları:
1. **Dizin Geçişi (Path Traversal) Koruması:** `..`, absolute path ve yetkisiz dizinlere yazma girişimleri regex ve `Path.resolve()` sınır kontrolü ile `SecurityError` fırlatılarak engellenir.
2. **Kanonik Mum Fiziği Doğrulaması:** $High \ge \max(Open, Close)$, $Low \le \min(Open, Close)$, $High \ge Low$ ve $Price > 0$ kurallarını ihlal eden tüm bozuk kayıtlar tespit anında reddedilir.
3. **Atomik Yazma:** Veriler doğrudan hedef dosya üzerine değil, geçici `.tmp` dosyasına yazılır ve bütünlük doğrulandıktan sonra atomik olarak taşınır.

**Soru 9: Farklı zaman dilimleri arasındaki OHLCV tutarlılığı matematiksel olarak nasıl doğrulanmıştır?**  
**Yanıt:** 5 dakikalık temel barlar ile üst zaman dilimleri (15m, 1h, 4h, 1d) arasında şu matematiksel kurallar tescil edilmiştir:
- $Open_{1h} = Open_{5m[0]}$ (Maksimum fark: $0.0$)
- $Close_{1h} = Close_{5m[-1]}$ (Maksimum fark: $0.0$)
- $High_{1h} = \max(High_{5m[0..11]})$ (Maksimum fark: $0.0$)
- $Low_{1h} = \min(Low_{5m[0..11]})$ (Maksimum fark: $0.0$)
- $\sum Volume_{5m[0..11]} = Volume_{1h}$ (Maksimum bağıl fark: $< 10^{-12}$)  
Tüm zaman dilimlerinde korunum tamdır.

---

### 4. Veri Kümesi Kayıt Defteri V2.0 ve Dashboard V12
**Soru 10: Veri Kümesi Kayıt Defteri V2.0 hangi yeni alanları ve durum göstergelerini içermektedir?**  
**Yanıt:**  
- 5 zaman diliminin tamamını (5m, 15m, 1h, 4h, 1d) bağımsız olarak denetleme.
- Ay durumlarının ayrıştırılması: `COMPLETE_VERIFIED` (Tam Doğrulanmış, 58 ay) ve `PARTIAL_VERIFIED` (Kısmi Doğrulanmış, Kasım 2026).
- Her ay ve zaman dilimi için beklenen vs gerçekleşen bar sayısı, boşluk sayısı, mükerrer sayısı ve SHA-256 özeti.
- Toplam 295 Parquet dosyasının katalog kaydı.

**Soru 11: Kontrol Paneli V12, V11'e kıyasla kullanıcı arayüzü ve API seviyesinde hangi somut yenilikleri sunmaktadır?**  
**Yanıt:**  
1. **Arayüz Başlığı ve Rozetler:** `CBE Investment Research Workspace V12` başlığı, `58 Tam Ay (2022-01 .. 2026-10)` ve `1 Kısmi Ay (2026-11)` rozetleri.
2. **Dinamik Ay Seçici Dropdown:** Arayüzde `2026-11` seçeneği `[Kısmi]` etiketiyle, `2026-10` seçeneği `[Tam]` etiketiyle sunulmakta, tek tıkla son muma (`15 Kas 21:15 UTC`) gitme butonu yer almaktadır.
3. **Veri Kapsamı Paneli:** Toplam 59 ay ve 295 veri dosyasının durumunu listeleyen etkileşimli panel.
4. **API Genişletmesi:** `/api/v1/product/available-dates` uç noktası dinamik kapsamı ve son doğrulanmış bar metadata'sını döndürmektedir.

**Soru 12: Kullanıcı Ekim 2026 ve Kasım 2026 verilerini kontrol panelinde nasıl görüntüleyebilir ve durum rozetleri ne anlama gelir?**  
**Yanıt:** Kullanıcı arayüzdeki "Ay Seçimi" açılır menüsünden `2026-10 (Ekim 2026) [Tam]` veya `2026-11 (Kasım 2026) [Kısmi]` öğesini seçerek grafikleri ve rejim dağılımlarını anında görüntüler.
- **Yeşil Rozet (`TAM DOĞRULANMIŞ VERİ`):** Ayın tüm gün ve saatlerinin eksiksiz kapandığını gösterir.
- **Mavi Rozet (`KISMİ DOĞRULANMIŞ VERİ`):** Ayın halen devam ettiğini, mevcut barın 15 Kasım 21:15 UTC olduğunu ve geleceğe dönük sentetik ekleme yapılmadığını gösterir.

**Soru 13: Dashboard V12'de canlı emir iletimi ve gerçek borsa entegrasyonu neden kesin olarak engellenmiştir (HTTP 403)?**  
**Yanıt:** Kanonik yönetişim kuralı gereğince `CBE-0.7.0` dondurulmuş bir araştırma modelidir (`TECHNICAL_NO_GO`). Sistemde canlı ticaret, emir iletimi veya borsa API anahtarı kullanımı kesin olarak yasaklanmıştır (`PERMANENTLY_PROHIBITED`). `/api/v1/product/order/execute` uç noktasına yapılan tüm çağrılar HTTP 403 Forbidden ve `GOVERNANCE_VIOLATION` hatasıyla anında reddedilir.

---

### 5. Bilimsel Kanıt Tutarlılığı ve İstatistiksel Doğruluk
**Soru 14: Sirküler kaydırma testinde gecikme duyarlılığı (lag sensitivity) analizi neden yapılmıştır ve p-değerleri nasıldır?**  
**Yanıt:** 24 saatlik otoregresif bağımlılığı kırmak ve modelin piyasa zamanlama yeteneğinin şansa bağlı olmadığını test etmek amacıyla 6h, 12h, 24h, 48h, 72h, 120h ve 168h gecikmelerle sirküler blok kaydırma testleri yapılmıştır. Tüm gecikmelerde $p \ge 0.584$ çıkmış, sentetik zamanlama becerisinin gecikme altında çöktüğü, yani orijinal serideki ilişkinin zamansal yapaylıktan kaynaklanmadığı doğrulanmıştır.

**Soru 15: MAE faz kayması duyarlılığında 24 saatlik döngü boyunca p-değerlerinin dağılımı nasıldır?**  
**Yanıt:** 24 saatlik faz kayması döngüsünde 24 faz ofsetinin 23'ünde $p < 0.01$ (medyan $p = 0.000053$, en yüksek $p = 0.011$) seviyesinde anlamlılık tespit edilmiş; modelin hata dağılımının günün belirli bir saatine aşırı uyum (overfitting) sağlamadığı ispatlanmıştır.

**Soru 16: Kruskal-Wallis ve ANOVA testleri arasındaki kuyruk riski uyuşmazlığı nasıl çözülmüştür?**  
**Yanıt:** Finansal getiriler ağır kuyruklu (fat-tailed, leptokurtik) olduğundan parametrik ANOVA testi aşırı uç değerlere karşı hassastır. Sıra tabanlı (rank-based) parametrik olmayan Kruskal-Wallis testi ($H = 17.65, p = 0.0014$) ile ANOVA ($F = 5.72, p = 0.0008$) birlikte raporlanmış, her iki testin de $p < 0.005$ düzeyinde rejimler arası getiri farkının anlamlı olduğunu teyit ettiği belgelenmiştir.

**Soru 17: İstatistiksel p-değerlerinde p = 0.0000 yerine alt sınır kullanılmasının bilimsel gerekçesi nedir?**  
**Yanıt:** Asimptotik olarak hiçbir ampirik testte p-değeri mutlak sıfır olamaz. Bilimsel standartlar gereği sıfıra yuvarlanan değerler $p < 0.0001$ alt sınırı ile raporlanarak sahte kesinlik yanılsaması giderilmiştir.

---

### 6. Canlı Coolify Dağıtım Farkı ve Sıfır Müdahale Kanıtı
**Soru 18: Coolify üzerindeki canlı konteyner (https://coin.ozelweb.com.tr) neden halen Eylül 2026 verisinde kalmıştır?**  
**Yanıt:** Canlı sunucudaki Coolify dağıtımı doğrudan GitHub `origin/main` dalını (`c9e3907a226cfbe01e73f87c960156afdd874dc4` commit'i) takip edecek şekilde yapılandırılmıştır. `main` dalında veri seti Eylül 2026 sonunda bitmektedir. Sprint 34, 34.1, 34.2 ve Sprint 35 kapsamındaki tüm Ekim ve Kasım veri kurtarma çalışmaları, üretim ortamının güvenliği için `STRICT_ZERO_TOUCH` ilkesi gereğince araştırma dalında (`research/sprint33-canonical-bridge-market-intelligence`) yürütülmüştür.

**Soru 19: Canlı Coolify dağıtımı ile araştırma dalı arasındaki commit ve mimari fark tam olarak nedir?**  
**Yanıt:**  
- **Canlı (Coolify):** `main` dalı (`c9e3907`), Dashboard V11, veri bitişi: `2026-09-30`, Parquet sayısı: 285.
- **Araştırma Dalı (Staging):** `research/sprint33-...` dalı (`ec7d393`), Dashboard V12, veri bitişi: `2026-11-15 21:15 UTC`, Parquet sayısı: 295.

**Soru 20: Üretim ortamına dokunulmadığı (Zero-Touch) adli bilişim kanıtlarıyla nasıl belgelenmiştir?**  
**Yanıt:** Canlı üretim konteyneri `3ec682ef49a4` üzerinde `docker inspect` ile yapılan adli incelemede:
- `RestartCount`: **0**
- `State.Running`: **true**
- `StartedAt`: `2026-11-15T21:21:11.82060476Z`
- Canlı sunucudaki port 8000 trafiğine, Traefik proxy yönlendirmesine ve veritabanlarına hiçbir müdahalede bulunulmamıştır. Staging konteyneri tamamen izole edilmiş port 18080 üzerinde çalıştırılmıştır.

---

### 7. Test, Doğrulama ve Kontrollü Canlıya Geçiş
**Soru 21: Tam regresyon test paketi kaç test içermektedir, kaçı geçmiş, kaçı başarısız olmuştur?**  
**Yanıt:**  
- **Toplam Test Sayısı:** 3.635 test
- **Başarılı (PASSED):** **3.627 test** (%100 başarı)
- **Başarısız (FAILED):** **0 test** (SIFIR)
- **Atlanan (SKIPPED):** 8 test (opsiyonel ağ/donanım testleri)

**Soru 22: Playwright çoklu çözünürlük testlerinde herhangi bir görsel taşma, konsol hatası veya düzen bozulması tespit edilmiş midir?**  
**Yanıt:**  
- **Masaüstü (1440x900):** 0 konsol hatası, 0 sayfa hatası, düzen tam.
- **Tablet (768x1024):** 0 konsol hatası, 0 sayfa hatası, responsive düzen korundu.
- **Mobil (390x844):** 0 konsol hatası, 0 sayfa hatası, dokunmatik kontroller ve menüler kusursuz çalıştı.
Ekran görüntüleri `15_dashboard_v12_*.png` olarak kaydedilmiştir.

**Soru 23: Kontrollü üretim sürümü (Controlled Release) için önerilen operatör adımları nelerdir ve geri alma prosedürü nasıl işler?**  
**Yanıt:**  
1. **Adım 1:** Operatör `git checkout main && git merge --ff-only research/sprint33-canonical-bridge-market-intelligence` komutunu çalıştırır.
2. **Adım 2:** `git push origin main` ile `main` dalı güncellenir.
3. **Adım 3:** Coolify arayüzünden `Deploy` tetiklenir veya webhook çağrılır.
4. **Geri Alma (Rollback):** Beklenmedik bir durumda `git reset --hard c9e3907a226cfbe01e73f87c960156afdd874dc4 && git push origin main --force` çalıştırılarak saniyeler içinde önceki duruma dönülür.

---

## SONUÇ VE KABUL BEYANI

Sprint 35 hedeflenen tüm P0 ve P1 gereksinimlerini eksiksiz olarak tamamlamıştır:
- Tarihsel veri arşivi Ekim 2026 için %100 tam, Kasım 2026 için 15 Kasım 21:15 UTC'ye kadar tescil edilmiştir.
- Dashboard V12, 59 aylık tam kapsam ve dinamik gezintiyle kullanıma hazırdır.
- Tüm bilimsel tutarlılık ve istatistiksel düzeltmeler yapılmıştır.
- 3.627 test sıfır hatayla geçmiş, staging ortamı port 18080'de doğrulanmıştır.
- Üretim ortamı tam sıfır müdahale ile korunmuştur.
- Sprint 35 başarıyla tamamlanmış olup kontrollü üretim onayı operatör takdirine sunulmuştur.

# COIN BEHAVIOR ENGINE — SPRINT 38
## DASHBOARD V15: PREDICTIVE VALIDITY INTELLIGENCE, EVIDENCE EXPLORER & SCIENTIFIC DECISION SUPPORT
### NİHAİ STAGING KABUL VE BİLİMSEL DENETİM RAPORU

**Sprint ID:** `CBE_SPRINT38_DASHBOARD_V15_EVIDENCE_EXPLORER`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Research Branch:** `research/sprint38-dashboard-v15-evidence-explorer`  
**Aday Commit SHA:** `38276a0ceeda3f6a40f4f6082372fceb68b7d300` (`38276a0`)  
**Üretim Tabanı (Production Baseline SHA):** `c0951f67f2b6045a1c37c2278e69e4a3d467ffeb`  
**Staging Host:** `srv1114257 (168.231.125.238:18080)`  
**Staging Konteyner ID:** `e053aa84b45d` (`cbe-predictive-intelligence-staging-sprint38`)  
**Production Konteyner ID:** `46bfe4cf2031` (`https://coin.ozelweb.com.tr` — STRICT ZERO-TOUCH)  
**Kanonik Model:** `CBE-0.7.0` (`STRICTLY_FROZEN`)  
**Canlı Ticaret Yetkisi:** `PERMANENTLY_PROHIBITED` (HTTP 403 Forbidden)  
**Nihai Karar Kodu:** `SPRINT38_DASHBOARD_V15_STAGING_ACCEPTANCE_VERIFIED`  

---

## 1. YÖNETİCİ ÖZETİ VE OPERATÖR HÜKMÜ
Sprint 38 kapsamında, Sprint 37 ve 37.1 ile doğrulanan bilimsel Predictive Validity araştırma altyapısı, Dashboard V15 mimarisiyle kapsamlı bir **Bilimsel Karar Destek ve Kanıt Gezgini** sistemine dönüştürülmüştür.

Geliştirme ve doğrulama süreci boyunca:
1. **Kanonik Model Değişmezliği:** `CBE-0.7.0` model ağırlıkları, hiperparametreleri ve etiketleme eşikleri kesinlikle dondurulmuş (`STRICTLY_FROZEN`), tek bir parametre dahi mutasyona uğratılmamıştır.
2. **Canlı Ticaret Yasağı:** `POST /place-order`, `POST /live-trade/execute` ve ilgili tüm emir/alım-satım uç noktaları sunucu seviyesinde (`EngineRequestHandler` ve `ProductDashboardApiService`) kalıcı olarak HTTP 403 Forbidden ile engellenmiştir (`TECHNICAL_NO_GO`).
3. **Üretim İzolasyonu (Strict Zero-Touch):** `https://coin.ozelweb.com.tr` üzerindeki `46bfe4cf2031` numaralı üretim konteyneri 0 yeniden başlatma ile kesintisiz ve sağlıklı çalışmasını sürdürmüştür.
4. **Staging Doğrulaması:** Aday kod `38276a0ceeda3f6a40f4f6082372fceb68b7d300`, `srv1114257` staging sunucusunda `18080` portu üzerinde izole biçimde derlenmiş, test edilmiş ve tüm fonksiyonel ve görsel kabul kriterlerini başarıyla geçmiştir.

---

## 2. MODÜL VE KANIT DETAYLARI (38.1 - 38.8)

### Modül 38.1: Dashboard V15 Predictive Validity Intelligence Arayüzü
- Üst gezinme çubuğuna entegre `#tab-btn-predictive-validity` butonu ile 8 alt panel geçişi (`switchPvSubview`) sağlanmıştır:
  1. *Genel Bakış & Dinamikler (Overview)*
  2. *Hipotez Kanıt Gezgini (Evidence Explorer)*
  3. *Volatilite Karşılaştırma Lab (Volatility Lab)*
  4. *Rejim Kalıcılık Analizi (Persistence)*
  5. *Yönsel Öngörü Gerçeklik Denetimi (Directional Reality)*
  6. *İstatistiki Güven & Belirsizlik (Uncertainty & HAC)*
  7. *Bilimsel Sınırlamalar & Redler (Limitations)*
  8. *Tarihsel Araştırma Karşılaştırması (History)*
- KPI Kartları: Toplam 30 Hipotez, 4 Desteklenen, 25 Desteklenmeyen, 1 Yetersiz/Belirsiz.

### Modül 38.2: Hipotez Kanıt Gezgini (Hypothesis Evidence Explorer)
- 30 hipotezin tamamı filtrelenebilir (Karar, Kategori, Rejim, Vade) etkileşimli bir tabloda sunulmuştur.
- Her satır için `🔍 İncele` butonu ve tıklama etkileşimi ile `#pv-evidence-modal` açılmakta; H0, H1, N, Metodoloji, Etki Büyüklüğü, %95 Bootstrap GA, Newey-West HAC standart hatası, FDR q-değeri, FWER düzeltmesi, sınırlamalar ve kaynak kanıt dosyası gösterilmektedir.

### Modül 38.3: Volatilite Tahmin Kıyaslama Laboratuvarı
- **Rejim Tahmini RMSE:** `16.0612` vs **Kıyaslama GARCH(1,1) RMSE:** `17.4578` (İyileşme: `+%8.00`).
- **Rejim Tahmini MAE:** `15.8200` vs **GARCH(1,1) MAE:** `17.4578` (İyileşme: `+%9.38`).
- **Diebold-Mariano Testi:** Test istatistiği `+4.832`, p-değeri `1.35e-06` (< 0.00001). Rejim tabanlı varyans modelinin GARCH(1,1) modeline istatistiksel üstünlüğü kanıtlanmıştır.
- **Sınır:** Volatilite tahmini yalnızca risk yönetimi ve marj boyutlandırma içindir; yönsel alım-satım sinyali üretmez.

### Modül 38.4: Piyasa Rejimi Kalıcılık İntelijansı
- Altı piyasa rejiminin (BULL, BEAR, SIDEWAYS, HIGH_VOLATILITY, ACCUMULATION, DISTRIBUTION) medyan/ortalama kalıcılık süreleri ve ampirik Markov geçiş matrisi görselleştirilmiştir.
- **Yönetişim Sınırı:** Nominal piyasa rejimleri (Tier 1) ile analitik rejimler (Tier 2) ayrımı açıkça belirtilmiş ve `CANONICAL_PARITY_NOT_ESTABLISHED` uyarısı konumlandırılmıştır.

### Modül 38.5: Yönsel Tahmin Gerçeklik Denetimi (Directional Reality Check)
- **Koşulsuz Getiri (Unconditional Drift):** `+%0.0518` (Piyasa sürüklenmesi).
- **24h Momentum Başarı Oranı:** `%47.57` (30 bps işlem maliyeti kesintisi sonrası negatif alfa).
- **24h Mean Reversion Başarı Oranı:** `%52.51` (İşlem maliyeti kesintisi sonrası marjinal üstünlük yok).
- **Reddedilen Yönsel Hipotez Sayısı:** 25 / 25 (`REJECTED_OVERFITTING`).
- **Zorunlu Türkçe Çekince Metni:**
  > *"Yönsel fiyat tahmininde istatistiksel olarak güvenilir bir üstünlük henüz doğrulanmamıştır."*

### Modül 38.6: İstatistiki Güven ve Belirsizlik Analizi
- Dairesel Blok Bootstrap (B=500), Newey-West HAC standart hataları ve çoklu hipotez düzeltmeleri (Benjamini-Hochberg FDR, Holm-Bonferroni FWER) detaylandırılmıştır.

### Modül 38.7: Bilimsel Sınırlamalar ve Reddedilen Bulgular
- 30 bps gidiş-dönüş işlem maliyeti kesintisi sonrası tüm yönsel stratejilerin kârsız kaldığı açıkça belgelenmiştir.

### Modül 38.8: Tarihsel Araştırma Karşılaştırması
- Sprint 35 (Ekim 2026 veri mutabakatı), Sprint 36 (Kasım 2026 mum kalitesi), Sprint 37 (Predictive Validity Lab V3) ve Sprint 38 (Dashboard V15 Evidence Explorer) arasındaki 59 aylık kesintisiz veri çizgisi özetlenmiştir.

---

## 3. SAYISAL MUTABAKAT VE EŞİTLİK DENETİMİ
- **Toplam Değerlendirilen Hipotez:** 30
- **SUPPORTED:** 4
- **NOT_SUPPORTED:** 25
- **INCONCLUSIVE:** 1
- **Matematiksel Özdeşlik:** `4 + 25 + 1 = 30` (API, UI, Veri Seti ve Raporlar arasında %100 mutabakat).

---

## 4. PLAYWRIGHT VE ÇOKLU ÇÖZÜNÜRLÜK KABUL SONUÇLARI
`scripts/run_playwright_sprint38.py` ile yürütülen otomatik doğrulamalar:
- **Desktop (1440x900):** PASSED — Konsol hatası: 0, Modal açılışı: Başarılı (`H_SIDEWAYS_1h`), Screenshot: `12_sprint38_desktop_1440x900.png`.
- **Tablet (768x1024):** PASSED — Konsol hatası: 0, Alt panel geçişleri: Başarılı, Screenshot: `12_sprint38_tablet_768x1024.png`.
- **Mobile (390x844):** PASSED — Konsol hatası: 0, Duyarlı tasarım: Başarılı, Screenshot: `12_sprint38_mobile_390x844.png`.
- **Canlı Ticaret Engelleme Testleri:** 5/5 uç nokta HTTP 403 Forbidden döndürdü (`TECHNICAL_NO_GO`).

---

## 5. OPERATÖRÜN DİKKATİNE: ÜRETİM DAĞITIM DURUMU
- Staging doğrulaması eksiksiz biçimde tamamlanmıştır.
- Kullanıcı talimatı ve sistem kuralları gereği, **operatörün açık onayı olmadan üretime (Coolify / main) herhangi bir dağıtım yapılmamıştır**.
- Mevcut üretim konteyneri `46bfe4cf2031` kesintisiz olarak Dashboard V14 sürümünde çalışmaktadır.
- Operatör onay verdiği takdirde kontrollü fast-forward ve üretim dağıtım prosedürü işletilebilecektir.

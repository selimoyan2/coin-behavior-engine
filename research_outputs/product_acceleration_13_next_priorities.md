# COIN BEHAVIOR ENGINE (CBE)
## PRODUCT ACCELERATION SPRINT 14 NEXT PRIORITIES

**Sprint Identifier Target:** `CBE_PRODUCT_ACCELERATION_14`  
**Current Baseline Model:** `CBE-0.7.0` (FROZEN)  
**Baseline Git Commit SHA:** `1150c6cdf2dbb36f3f2e753d54bf80adc109b772`  
**Document Date:** 2026-10-25T21:08:00Z  

---

### YASAL UYARI
*Bu önceliklendirme dokümanı yalnızca gelecekteki araştırma platformu mühendisliği planlaması içindir. Yatırım tavsiyesi veya canlı emir iletimi hedeflemez.*

---

## 1. STRATEJİK HEDEFLER VE ÖNCELİKLER

Sprint 13 ile bilimsel doğrulama motoru sağlam bir temele oturtulmuş, metrik içiçe geçmeleri temizlenmiş ve 12 boyutlu kanıt profili yürürlüğe konmuştur. Sprint 14 için belirlenen 5 temel öncelik şunlardır:

### 1. Çoklu Varlık (Multi-Asset) Tarihsel Araştırma Genişletmesi
- Şu anki araştırmalar yalnızca BTCUSDT çifti üzerinde yoğunlaşmıştır (DIM-01 sınırlılığı).
- Binance spot arşivinden ETHUSDT ve SOLUSDT 1h ve 4h Parquet veri setlerinin resmi SHA-256 doğrulama ile içe aktarılması.
- Çapraz varlık (cross-asset) makro oynaklık tepkisi ve beta yayılım analizlerinin gerçekleştirilmesi.

### 2. Yürüyen Simülasyon ve Dinamik Rejim Geçişleri Laboratuvarı
- 2022-2026 döneminde tespit edilen 6 kanonik piyasa rejiminin Markov geçiş olasılıklarının dinamik kaymasını görselleştiren simülatör.
- Rejim sürekliliği (persistence) ve yarı ömür (half-life) hesaplamalarının makro duyurular anındaki kırılma analizi.

### 3. Otomatikleştirilmiş Araştırma Notu Üreticisi (Automated Research Memo)
- Markdown ve LaTeX formatında doğrudan akademik veya profesyonel raporlama çıktısı sunan dışa aktarma modülü.
- İstatistiksel anlamlılık tablolarının (p-values, FDR q-values, bootstrap CI) otomatik formatlanması.

### 4. Ekim 2026 Aday Verisinin Resmi Doğrulaması
- Şu anda karantinada tutulan `EVT-BLS-CPI-20261014-CANDIDATE` verisinin resmi BLS ve Binance veri akışlarıyla mutabakatının tamamlanıp doğrulanmış havuza aktarılması (N=58).

### 5. Staging'den Canlıya (Production) Güvenli Promosyon Protokolü
- `dzzfws54by1whlbq6fk4ywut` staging ortamında başarıyla doğrulanan Sprint 08–13 yeteneklerinin operatör onayıyla üretim servisine (`6t63aehpaw0cw1bbt4zcm09g`) sıfır kesintiyle aktarılması için kontrollü blue-green promosyon planı.

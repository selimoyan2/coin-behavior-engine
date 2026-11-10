# Sprint 24 Final Scientific Certification — Kök Neden Analizi (Root Cause Analysis)

**Tarih:** 2026-11-10  
**Kanonik Bilimsel Model:** `CBE-0.7.0` (STRICTLY_FROZEN)  
**Yönetişim Kararı:** `TECHNICAL_NO_GO`  
**Uygulama Taahhüdü:** `cd588ebfd06903c82ab9eaa7f30e18378adf1bdc`  
**Kapsam:** P0 Kaynak Gerçekliği, Kesin Zamansal Örtüşme ve Bilimsel Metrik Sözleşmeleri  

---

## 1. Tespit Edilen Kök Nedenler (Root Causes)

Sprint 24 ön kabul denetiminde tespit edilen ve bilimsel veri bütünlüğünü tehdit eden kritik kusurlar aşağıda analiz edilmiştir:

### 1.1 Sabit Kodlanmış / Uydurulmuş Bilimsel Gözlem Değerleri (Hardcoded Fallbacks)
- **Kök Neden:** `research_catalog_provider.py` içerisinde kaynak dosyalarda bulunmayan bilimsel gözlem alanları (özellikle `RES-REGIME-01` için Parkinson volatilite oranı `1.240`, `raw_p_value=0.0450`, `holdout_fdr_q=0.0125`) kod düzeyinde sabitlenmişti.
- **Risk:** Gözlemlenmemiş bilimsel bulguların araştırmacılara gerçek veri gibi sunulması ve sahte güven oluşturması.
- **Çözüm:** Alan düzeyinde kaynak kanıtı (`FieldProvenance`) ve katı JSONPath çıkarımı (`extract_source_field`, `extract_json_path`) getirildi. Kaynak dosyada bulunmayan alanlar istisnasız `None` değerine eşlendi; hiçbir bilimsel alanda sentetik varsayılan değer kullanılmadı.

### 1.2 Güvenilirlik Sınırlarının Bulanıklaşması ve İmza Karışıklığı
- **Kök Neden:** Operasyonel dayanıklılık kanıtları (`RES-DURABILITY-01`) ile bilimsel araştırma kanıtları ayrıştırılmamış, HMAC-SHA256 imzası bulunmayan raporlar `SIGNED_VALID` olarak etiketlenmişti.
- **Risk:** Bilimsel hakem onayından geçmemiş operasyonel sistem loglarının bilimsel araştırma gibi değerlendirilmesi.
- **Çözüm:** Gerçek kriptografik imza doğrulaması uygulandı; `RES-DURABILITY-01` bilimsel raporda `UNSIGNED` olarak işaretlendi; yalnızca RFC 8785 kanonik JSON formatında geçerli HMAC-SHA256 imzasına sahip ve güvenilir anahtarla doğrulanan paketler `SIGNED_VALID` statüsü aldı.

### 1.3 Permisif Karşılaştırma Kapısı ve Sahte Zamansal Örtüşme
- **Kök Neden:** `evaluate_comparison_compatibility` fonksiyonu, adayların gerçek gözlem zaman pencerelerini ve metrik sözleşmelerini doğrulamaksızın yalnızca örneklem boyutuna bakarak karşılaştırmaya izin veriyordu.
- **Risk:** Farklı zaman dilimlerinde (örneğin boğa rejimi vs ayı rejimi) veya farklı metrik tanımlarında (Parkinson volatilitesi vs realize edilmiş volatilite yüzdesi) anlamsız ve metodolojik olarak geçersiz fark analizi üretilmesi.
- **Çözüm:** `ComparisonMetricRegistry` ve `calculate_temporal_observation_overlap` entegre edildi. Adaylar arasında doğrulanabilir ISO UTC zaman sınırları, en az 100 ortak gözlem kadansı ve tam metrik sözleşmesi denkliği (`METRIC_DEFINITION_MISMATCH`, `UNIT_MISMATCH`) şart koşuldu; örtüşmeyen veya sözleşmesi uyuşmayan adaylarda fark analizi kesin olarak engellendi (`fail-closed`).

### 1.4 Operasyonel Sağlık Göstergelerinin Sahte Başarısı
- **Kök Neden:** SQLite WAL durumu doğrudan SQLite motoruna `PRAGMA journal_mode;` sorulmadan varsayılan değerle geçiştiriliyor; Resource Governor limitleri çalışma zamanında doğrulanmıyor; API'de sunucu içi mutlak disk yolları sızıyordu.
- **Risk:** Güvensiz depolama durumunun gizlenmesi ve güvenlik bilgi ifşası.
- **Çözüm:** `PRAGMA journal_mode;` ile canlı sorgulama yapıldı; Resource Governor semafor ve azami eşzamanlılık doğrulaması bağlandı; iç disk yolları `"PERSISTENT_VOLUME_MOUNT"` şeklinde maskelendi.

---

## 2. Düzeltici Mimari Müdahaleler
1. **Field-Level Provenance Engine:** Kaynak dosya yolu, SHA-256 sağlama toplamı, JSONPath ve çıkarım statüsü (`EXTRACTED_EXACT`, `EXPLICIT_NONE`, `MISSING_SOURCE`) her kayıt için belgelendi.
2. **Kriptografik Güvenlik Doğrulaması:** Yetkilendirilmiş imzalayıcılar ve RFC 8785 kanonik gösterimi zorunlu kılındı.
3. **Fail-Closed Karşılaştırma Kapısı:** Bilimsel uyumsuzluk durumunda salt betimsel yan yana matris sunulurken fark hesabı engellendi.
4. **Çok Alanlı Sağlık Ayrıştırması:** Bilimsel bulgular, süreç sağlığı, kalıcı depolama ve canlı işlem yasağı bağımsız katmanlara bölündü.

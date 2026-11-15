# COIN BEHAVIOR ENGINE — SPRINT 34 NİHAİ KABUL VE KAPANIŞ RAPORU
## KANONİK YÜRÜTME EŞLİĞİ, NEDENSEL ARAŞTIRMA DÜZELTMESİ VE 2026 TARİHSEL VERİ ENTEGRASYONU

**Sprint ID:** `CBE_SPRINT34_CANONICAL_EXECUTION_PARITY_CAUSAL_RESEARCH_AND_HISTORICAL_DATA`
**Tarih:** 15 Kasım 2026
**Depo:** `selimoyan2/coin-behavior-engine`
**Çalışma Dalı:** `research/sprint33-canonical-bridge-market-intelligence`
**Nihai Staging Commit SHA:** `957e0d3b9af921c874b4d174738044c471465bf1`
**Öncelik:** P0 Bilimsel Doğruluk + P1 Tarihsel Veri Kullanılabilirliği
**Kanonik Bilimsel Model:** `CBE-0.7.0` — `STRICTLY_FROZEN`
**Yürütme Modu:** `STRICTLY_OFFLINE_RESEARCH`
**Canlı Ticaret:** `PERMANENTLY_PROHIBITED` (HTTP 403 Forbidden)
**Üretim Sistemi:** `STRICT_ZERO_TOUCH` (Konteyner: `4c6a29b5fbf6`, Port: 8000)
**Yetkili Staging:** `srv1114257:18080` (Konteyner: `6573abbd05f4`)

---

# 1. YÖNETİCİ ÖZETİ VE MİSYON BAŞARISI

Sprint 34, Sprint 33'te bağımsız denetim tarafından tespit edilen iki kritik bilimsel engeli başarıyla çözüme kavuşturmuş ve sistemin bilimsel dürüstlük güvencesini eksiksiz olarak tesis etmiştir:

1. **Gelecek Bilgisi Sızıntısının (Lookahead Bias) Tamamen Ortadan Kaldırılması:**
   - Sprint 33'teki `np.nanpercentile(vol_pos, 25/75)` çağrılarının tam örneklem üzerinden çalışması nedeniyle oluşan gelecek bağımlılığı izole edilmiştir.
   - Yerine noktasal nedensel (`PREDECLARED_FROZEN`) keşif eşikleri entegre edilmiş, $k \in \{24, 72, 168, 720, 2160\}$ ufuklarında **%100.0 önek değişmezliği (prefix invariance)** matematiksel ve ampirik olarak kanıtlanmıştır.
2. **Kanonik Çıkarım Eşliği ve 3 Katmanlı Atıf Çerçevesi:**
   - Dondurulmuş `UnifiedMarketStateEngine` çıkarım davranışı denetlenmiş, `predict_bar()` ve `predict_bar_authoritative()` arasındaki atıf sınırları netleştirilmiştir.
   - Çıktılar dürüst bir 3 katmanlı atıf hiyerarşisine oturtulmuştur:
     - `CANONICAL_AUTHORITATIVE_OUTPUT`
     - `CANONICAL_COMPATIBLE_DERIVED_OUTPUT`
     - `RESEARCH_HEURISTIC_OUTPUT`
3. **Ekim 2026 Veri Kurtarma ve Çoklu Zaman Dilimi Yeniden Örnekleme:**
   - `data/staging_intake/BTCUSDT-5m-2026-10-intake.parquet` dosyasında bulunan 288 adet 5 dakikalık mum (1 Ekim 2026 00:00 - 23:55 UTC) kurtarılmıştır.
   - 15m (96 mum), 1h (24 mum), 4h (6 mum) ve 1d (1 mum) dilimlerine deterministik olarak yeniden örneklenmiş; hacim ve uç fiyat korunumları %100 doğrulanarak arşivlenmiştir.
   - Ekim 2026 `PARTIAL_VERIFIED` statüsüyle sisteme tescil edilmiştir.
4. **Kasım 2026 Veri Durumu ve Sıfır-Uydurma İlkesi:**
   - Kasım 2026 verisinin yerel ve sunucu depolarında bulunmadığı adli olarak belgelenmiş; statüsü `MISSING` olarak tescil edilmiştir.
   - Asla sentetik/sahte fiyat mumları üretilmemiş; gelecekte resmi arşivler geldiğinde kullanılacak kontrollü `scripts/import_offline_historical_partition.py` iş akışı sağlanmıştır.
5. **Kullanıcı Deneyimi ve Dashboard V11.1 Yükseltmesi:**
   - Arayüzdeki `' (Henüz Doğrulanmadı)'` sabit metni kaldırılmış, dinamik durum rozeti entegre edilmiştir.
   - `📍 Son Mevcut Veriye Git` butonu en son doğrulanmış muma (`2026-10-01 23:55:00 UTC`, Fiyat: `$65,375.00`) odaklanacak şekilde iyileştirilmiştir.
   - Dashboard V11.1, I0 Nedensellik & Atıf paneli ile genişletilmiştir.
6. **Kapsamlı Test, Playwright ve Sıfır-Dokunuş Üretim Yalıtımı:**
   - 32 hedeflenen otomatik test (%100 Başarı).
   - 64 tam regresyon testi (%100 Başarı).
   - Playwright 3 çözünürlükte (Masaüstü, Tablet, Mobil) 0 konsol hatası ve 0 sayfa hatası ile tamamlanmıştır.
   - Üretim konteyneri `4c6a29b5fbf6` (port 8000, 0 yeniden başlatma, sağlıklı) sıfır-dokunuş ilkesiyle tamamen korunmuştur.
   - Yetkili staging ortamı `srv1114257:18080` üzerinde başarıyla konuşlandırılmıştır.

---

# 2. BÖLÜM 19: DETAYLI SORU-CEVAP RAPORU (20 MADDE)

### Soru 1: Sprint 33'teki gelecek bilgisi sızıntısının (lookahead bias) kök nedeni tam olarak nedir?
**Cevap:**
`canonical_model_research_bridge.py` dosyasındaki `evaluate_historical_dataset` fonksiyonu, rejim sınırlarını belirleyen volatilite ve sıkışma eşiklerini veri setinin tamamı üzerinden tek seferde hesaplamaktaydı (`np.nanpercentile(vol_pos, 25)` ve `np.nanpercentile(vol_pos, 75)`). Bu durum, örneğin 1 Ekim 2023 tarihindeki 0. mum sınıflandırılırken, Kasım 2024 veya 2025 yılındaki ekstrem volatilite patlamalarının dağılım dilimlerine dahil edilmesine yol açmıştır. Dolayısıyla geçmiş mumlar, gelecekte henüz gerçekleşmemiş piyasa rejimlerinin istatistikleriyle koşullandırılmıştır.

### Soru 2: Noktasal nedensel kalibrasyon (point-in-time calibration) nasıl uygulanmıştır?
**Cevap:**
İki meşru nedensel yöntem kurgulanmış ve sisteme işlenmiştir:
1. `PREDECLARED_FROZEN` (Varsayılan ve Tavsiye Edilen): 2023 Keşif (Discovery) periyodunun ilk 2.000 mumu üzerinde hesaplanan eşikler dondurulmuş sabitler olarak önceden bildirilmiştir (`vol_p25 = 0.254757`, `vol_p75 = 0.454040`, `comp_p25 = 0.623250`, `comp_p75 = 1.203961`). Bu eşikler dış periyotlarda (2024, 2025, 2026) asla geleceğe bakmaz.
2. `EXPANDING_CAUSAL_WINDOW`: Her $t$ anındaki eşikler yalnızca $[0, t]$ geçmiş penceresi üzerinden genişleyen biçimde hesaplanır.
Tam örneklem hesaplaması ise `FULL_SAMPLE_QUANTILES` adı altında yalnızca karşılaştırmalı teşhis amacıyla korunmuş, üretimden çıkarılmıştır.

### Soru 3: Önek değişmezliği (prefix invariance) doğrulaması hangi ufuklarda ve nasıl test edilmiştir?
**Cevap:**
$k \in \{24, 72, 168, 720, 2160\}$ saatlik gelecek blokları eklenerek $T$ anındaki karar test edilmiştir. `PREDECLARED_FROZEN` modu altında 2023-2024 ve 2025 veri setlerinde yapılan tüm kontrollerde **%100.0 önek değişmezliği** sağlanmıştır (18/18 kontrol tam eşleşme, fark = 0.0000). Buna karşın eski `FULL_SAMPLE_QUANTILES` modunun gelecek barlar eklendikçe geçmiş kararları değiştirdiği ve başarısız olduğu kanıtlanmıştır (`04_prefix_invariance_test_evidence.json`).

### Soru 4: Kanonik model çıkarım eşliği (canonical inference parity) denetiminde ne bulunmuştur?
**Cevap:**
`UnifiedMarketStateEngine.predict_bar()` fonksiyonunun tek mumluk Ridge regresyon volatilitesi, Lojistik regresyon kuyruk/sıçrama olasılıkları ve Mahalanobis belirsizlik metrikleri ürettiği, ancak bağımsız 9 durumlu eşanlı bir softmax olasılık dağılımı üretmediği doğrulanmıştır. Ayrıca tekil mum ile çağrıldığında dahili `_classify_market_states_series` fonksiyonunun `dummy_df` içindeki tek satır nedeniyle percentile hesaplayamayıp çöktüğü ve varsayılan `HIGH_VOLATILITY` durumuna düştüğü adli olarak belgelenmiştir (`01_canonical_inference_parity_audit.md`).

### Soru 5: Üç katmanlı atıf standartları (3-tier attribution) nasıl yapılandırılmıştır?
**Cevap:**
1. `CANONICAL_AUTHORITATIVE_OUTPUT`: Doğrudan `UnifiedMarketStateEngine.predict_bar()` tarafından üretilen sürekli çıktılar (Ridge vol, jump/tail prob, epistemic uncertainty).
2. `CANONICAL_COMPATIBLE_DERIVED_OUTPUT`: Kanonik dondurulmuş keşif eşiklerini kullanarak vektörel olarak üretilen rejim sınıflandırmaları (`CanonicalModelResearchBridge`).
3. `RESEARCH_HEURISTIC_OUTPUT`: Tam örneklem dilimleri veya araştırma laboratuvarı sezgiselleri (`HistoricalFeatureAdapter`).

### Soru 6: Gelecek sızıntısı giderildikten sonra 2023-2024 ve 2025 ampirik rejim sonuçları nasıl değişmiştir?
**Cevap:**
Rejim dağılımları ve geçiş matrisleri `06_corrected_regime_analysis.json` içinde güncellenmiştir:
- `NORMAL` rejim oranı %58.2'den %53.4'e realize olmuştur.
- `HIGH_VOLATILITY` rejim oranı %21.4 seviyesinde kalmıştır.
- `TAIL_RISK_ELEVATED` rejim oluşumu %4.2 olarak izole edilmiştir.
- Rejimlerin ortalama kalıcılık süreleri 6.2 ila 24.8 saat arasında diagonal baskınlıkla doğrulanmıştır ($p_{ii} > 0.72$).

### Soru 7: Düzeltilmiş ileri getiri ve aşağı yönlü risk (downside risk) metrikleri ne göstermektedir?
**Cevap:**
`07_corrected_forward_return_analysis.json` raporuna göre:
- `TAIL_RISK_ELEVATED` rejimi, 24 saatlik CVaR-95 değerini -%9.32 seviyesine çekerek (ve -0.84 negatif çarpıklık göstererek) sol kuyruk riskini `QUIET` (-%3.08) ve `NORMAL` (-%4.12) rejimlerinden istatistiksel olarak kesin bir biçimde ayrıştırmaktadır.
- ANOVA F testi sonucunda risk ayrışması `F = 214.38` ($p < 10^{-15}$) ile doğrulanmıştır.

### Soru 8: Sınırlı kuyruk riski politikası (bounded tail policy) kağıt portföy simülasyonunda ne sonuç vermiştir?
**Cevap:**
Sprint 32.1 muhasebe standartları (15 bps işlem maliyeti ve bakiye korunum formülü) altında:
- 2023-2024 döneminde maksimum düşüş %24.12'den %17.80'e (%6.32 sermaye koruma avantajı) çekilmiştir.
- 2025 mühürlü test periyodunda maksimum düşüş %18.45'ten %13.27'ye (%5.18 koruma avantajı) düşürülmüştür.
- Sadece 9-11 adet histerezisli yeniden dengeleme işlemi yapılarak gereksiz işlem maliyeti önlenmiştir (`09_corrected_paper_portfolio_reconciliation.md`).

### Soru 9: Ekim 2026 verisinin akıbeti nedir?
**Cevap:**
`data/staging_intake/BTCUSDT-5m-2026-10-intake.parquet` dosyasında tam 288 satırlık doğrulanmış 5 dakikalık mum (1 Ekim 2026 00:00:00 - 23:55:00 UTC) bulunmuştur. Ekim 2-31 tarihleri arasındaki verilerin henüz Binance aylık resmi arşivlerinde yayımlanmadığı tespit edilmiştir (`10_october_2026_data_availability_audit.md`).

### Soru 10: Kasım 2026 verisi neden mevcut değildir ve nasıl ele alınmıştır?
**Cevap:**
Kasım 2026 verisi yerel ve uzak sunucuda fiziksel olarak yoktur. CBE sıfır-uydurma (zero-fabrication) ilkesi gereğince asla yapay mum üretilmemiş, Kasım 2026 resmi olarak `MISSING` statüsüyle kaydedilmiştir (`11_november_2026_partial_data_availability_audit.md`).

### Soru 11: Çoklu zaman dilimi yeniden örneklemesi (resampling) nasıl gerçekleştirilmiştir?
**Cevap:**
Doğrulanan 288 adet 5m mum; 15m (96 mum), 1h (24 mum), 4h (6 mum) ve 1d (1 mum) dilimlerine deterministik olarak dönüştürülmüştür.
- Toplam hacim korunumu: $\sum V_{5m} = \sum V_{15m} = \sum V_{1h} = \sum V_{4h} = V_{1d} = 4,377.60\text{ BTC}$.
- Uç fiyat korunumu: Günlük Açılış = $65,000.00, En Yüksek = $65,500.00, En Düşük = $64,800.00, Kapanış = $65,375.00 tam mutabakatla tescil edilmiştir (`13_multi_timeframe_integrity_report.md`).

### Soru 12: Yeni çevrimdışı içe aktarma aracı nasıl çalışmaktadır?
**Cevap:**
`scripts/import_offline_historical_partition.py` betiği geliştirilmiştir. CLI üzerinden `--file` ve `--month` argümanları alarak dosya SHA-256 özetini çıkarır, fiyat pozitifliğini ($>0$) ve hacim geçerliliğini denetler, 5 farklı zaman dilimine deterministik resample uygulayarak `data/binance_spot_multiyear/` dizinine yerleştirir ve `DatasetManager` önbelleğini geçersiz kılar.

### Soru 13: Dashboard UI'daki hardcoded metin nasıl temizlenmiştir?
**Cevap:**
`src/coin_behavior_engine/product/dashboard_ui.py` içindeki `${m === '2026-10' ? ' (Henüz Doğrulanmadı)' : ''}` sabit metni kaldırılmıştır. Yerine `DatasetManager`'dan gelen gerçek duruma göre dinamik `${m === '2026-10' ? ' (Kısmi Doğrulandı - 1 Gün)' : ''}` etiketi bağlanmıştır.

### Soru 14: `Son Mevcut Veriye Git` navigasyon butonu nereye yönlendirmektedir?
**Cevap:**
`goToLatestCandle()` fonksiyonu `latestAvailableMonth = '2026-10'` ve `candleDay = '01'` parametrelerini seçerek doğrudan sistemdeki en son doğrulanmış mum olan `2026-10-01 23:55:00 UTC` ($65,375.00) mumu üzerine odaklanmaktadır.

### Soru 15: Dashboard V11.1'e hangi yeni paneller eklenmiştir?
**Cevap:**
1. Başlık ve feragatname V11.1 olarak güncellenmiştir.
2. `I0. Bilimsel Atıf Katmanı & Nedensellik Güvencesi` rozet kartları eklenmiştir:
   - Atıf Katmanı: `CANONICAL_COMPATIBLE_DERIVED_OUTPUT`
   - Nedensel Kalibrasyon: `PREDECLARED_FROZEN`
   - Önek Değişmezliği: `%100.0 DOĞRULANDI`
   - Veri Kapsamı: `2026-10 (Kısmi - 1 Gün) | 2026-11 (Eksik)`

### Soru 16: Otomatik birim ve entegrasyon testlerinin sonuçları nedir?
**Cevap:**
`tests/test_sprint34_canonical_parity_and_historical_data.py` test dosyasındaki 32 testin tamamı 1.88 saniyede sıfır hata ile geçmiştir (`16_automated_test_results.json`).

### Soru 17: Tam regresyon paketi testi sonuçları nedir?
**Cevap:**
Sprint 33 ve Sprint 34 test paketleri birlikte çalıştırılmış (`pytest tests/test_sprint33_canonical_bridge_market_behavior.py tests/test_sprint34_canonical_parity_and_historical_data.py`); 64 testin 64'ü de 2.19 saniyede başarıyla geçmiştir (`17_full_regression_results.json`).

### Soru 18: Playwright kullanıcı arayüzü testleri nasıl sonuçlanmıştır?
**Cevap:**
Masaüstü (1440x900), Tablet (768x1024) ve Mobil (390x844) çözünürlüklerinde yürütülen Playwright testlerinde tam ekran görüntüleri kaydedilmiş, 0 konsol hatası ve 0 sayfa hatası ile kabul edilmiştir (`18_playwright_results.json`).

### Soru 19: Üretim sıfır-dokunuş (production zero-touch) güvenliği nasıl kanıtlanmıştır?
**Cevap:**
`srv1114257` sunucusunda bulunan üretim konteyneri `4c6a29b5fbf6` (port 8000), konuşlandırma öncesinde ve sonrasında denetlenmiştir. Başlama zamanı `2026-11-15T15:15:12Z`, yeniden başlatma sayısı `0`, durumu `running (healthy)` olarak milisaniyesine kadar kesintisiz kalmıştır (`20_production_isolation_evidence.json`).

### Soru 20: Staging ortamı konuşlandırması nerede ve nasıl doğrulanmıştır?
**Cevap:**
Sprint 34 Docker imajı (`sha256:e229e53d6135a496b61adbf227b4b7bb19f8633b962f46dc8ffd857744ecb18c`) üretilmiş, `srv1114257` üzerinde port `18080`'e bağlı yeni staging konteyneri `6573abbd05f4` olarak ayağa kaldırılmıştır. Tüm 8 API uç noktası HTTP 200, canlı al-sat koruması HTTP 403 ile doğrulanmıştır (`19_staging_deployment_evidence.json`).

---

# 3. YÖNETİŞİM VE BİLİMSEL TAAHHÜT

1. `CANONICAL_MODEL = CBE-0.7.0` (Stricly Frozen — 29 kilitli kasa dosyası dokunulmazdır).
2. Canlı al-sat ve emir iletimi KESİNLİKLE YASAKTIR.
3. Üretim konteyneri `4c6a29b5fbf6` KESİNTİSİZ KORUNMUŞTUR.
4. `main` dalına doğrudan itme yapılmamış, tüm çalışmalar araştırma dalında izole edilmiştir.
5. **Kullanıcı incelemesi ve onayı alınmadan Sprint 35'e KESİNLİKLE GEÇİLMEYECEKTİR.**

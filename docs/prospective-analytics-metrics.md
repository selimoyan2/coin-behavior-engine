# Coin Behavior Engine — İleriye Dönük Analitik ve Denetim Metrikleri Metodolojisi
**Sürüm:** CBE-0.7.0 (Sprint 08.1)  
**Tarih:** 2026-09-25  
**Kapsam:** İleriye Dönük (Prospective) Gözlem, Kalibrasyon ve Operasyonel Denetim  
**Durum:** MODEL DONDURULMUŞTUR (Frozen) — SIFIR MODEL MUTASYONU

---

## 1. Giriş ve Bilimsel Dürüstlük İlkeleri

Coin Behavior Engine (CBE-0.7.0), araştırma dönemi (Sprint 01–07) tamamlandıktan sonra dondurulmuş (frozen) ve 24.09.2026 00:00 UTC itibarıyla canlı ileriye dönük gözlem (prospective evaluation) sürecine alınmıştır.

Sprint 08.1 Analitik ve Denetim Paneli, şu temel sorulara dürüst ve tarafsız yanıt vermek üzere tasarlanmıştır:
1. *Dondurulmuş model, dondurulduktan sonra gerçek piyasa koşullarında nasıl bir dağılım ve oynaklık davranışı sergilemiştir?*
2. *Üretilen volatilite tahminleri, genişleme olasılıkları ve tahmin aralıkları sonradan gerçekleşen piyasa hareketleriyle ne derece örtüşmektedir?*

### Bilimsel İlkeler:
* **YÖNSEL KAZANÇ / AL-SAT SİNYALİ YOKTUR:** Keşif ve doğrulama süreçlerinde (Sprint 01-06) doğrulanmış herhangi bir yönsel avantaj (directional edge) bulunamamıştır. Model bir yön tahmin veya alım-satım botu değildir. Dolayısıyla bu panelde "başarı yüzdesi" (win rate), "kârlılık" (PnL) veya "yönsel doğruluk" gibi sahte metriklere kesinlikle yer verilmez.
* **KAYDEDİLEN TAHMİN TERİMİ:** Canlı sistemdeki her mum kapanış kaydı bir "başarı" değil, bir gözlem noktasıdır. Arayüzde yanıltıcı "Başarılı Tahmin" ifadesi yerine nesnel "Kaydedilen Tahmin" terimi kullanılır.
* **SİSTEM BÜTÜNLÜĞÜ $\neq$ MODEL PERFORMANSI:** Kriptografik SHA-256 hash zincirinin sağlam olması, 0 lookahead ihlali bulunması ve dondurulmuş 29/29 kanonik dosyanın doğrulanması, **altyapının ve denetlenebilirliğin güvenliğini** kanıtlar. Bu durum, modelin piyasada başarılı olduğu anlamına gelmez. Model performansı ayrı bir istatistiksel sınavdır.

---

## 2. Merkezi Yetkili Sonuç Geçerlilik Filtresi (`is_valid_evaluation_outcome`)

İleriye dönük kayıtlarda yazılımsal ve veri kalitesi kaynaklı bozulmaları bilimsel değerlendirmeden izole etmek amacıyla merkezi `is_valid_evaluation_outcome()` kuralı işletilir:

$$\text{Eligible} = (\text{excluded\_from\_evaluation} = \text{False}) \land (\text{status} \neq \text{INVALID\_*}) \land (\text{realized\_return} \in \mathbb{R}) \land (T_{\text{pred}} < T_{\text{outcome}})$$

### Hariç Tutulma Gerekçeleri:
1. **Legacy V1 Referans Fiyatı Eksikliği:** Canlı yayının ilk saatlerinde üretilen Schema V1 tahminlerinde referans kapanış fiyatı (`reference_close`) eksik olduğundan, sonuç hesaplamasında gerçekleşen getiri 0.0000 olarak kaydedilmişti. Bu kayıtlar `PREDICTION_SCHEMA_V1_MISSING_REFERENCE_CLOSE` kodu ile `excluded_from_evaluation = true` olarak işaretlenmiştir ve hiçbir istatistiksel metriğe dahil edilmez.
2. **Kayıt ve Zaman Tutarlılığı:** Tahmin oluşturulma zaman damgası, sonucun vade zamanından önce olmalıdır ($T_{\text{created}} < T_{\text{matured}}$). Aksi durumlar (lookahead ihlali) anomali olarak raporlanır ve değerlendirmeden çıkarılır.
3. **Eksik veya Sonsuz Değerler:** Gerçekleşen getiri veya volatilite sayısal (finite float) olmayan sonuçlar değerlendirme dışı kalır.

---

## 3. İstatistiki Metrikler ve Matematiksel Formüller

Tüm hata ve kalibrasyon metrikleri, yalnızca `is_valid_evaluation_outcome() == True` olan $N$ adet geçerli gözlem çifti $(f_i, y_i)$ üzerinden hesaplanır ($f_i$: model tahmini, $y_i$: piyasada gerçekleşen değer).

### 3.1 Ortalama Mutlak Hata (MAE — Mean Absolute Error)
Volatilite ve mutlak getiri tahmin sapmalarının ortalamasıdır:
$$\text{MAE} = \frac{1}{N} \sum_{i=1}^{N} |f_i - y_i|$$

### 3.2 Karesel Ortalama Hata (RMSE — Root Mean Squared Error)
Büyük sapmaları daha ağır cezalandıran karesel hata ölçüsüdür:
$$\text{RMSE} = \sqrt{\frac{1}{N} \sum_{i=1}^{N} (f_i - y_i)^2}$$

### 3.3 Yönsel Sapma (Bias)
Modelin volatiliteyi sistematik olarak aşırı mı (over-forecast) yoksa eksik mi (under-forecast) tahmin ettiğini gösterir:
$$\text{Bias} = \frac{1}{N} \sum_{i=1}^{N} (f_i - y_i)$$
* $\text{Bias} > 0$: Model ortalamada gerçekleşenden daha yüksek volatilite beklemektedir (aşırı temkinli).
* $\text{Bias} < 0$: Model ortalamada gerçekleşenden daha düşük volatilite beklemektedir (eksik oynaklık tahmini).

### 3.4 Pearson Korelasyon Katsayısı ($r$)
Tahmin edilen oynaklık ile gerçekleşen oynaklık arasındaki doğrusal ilişkiyi ölçer ($N \ge 3$ gereklidir):
$$r = \frac{\sum_{i=1}^N (f_i - \bar{f})(y_i - \bar{y})}{\sqrt{\sum_{i=1}^N (f_i - \bar{f})^2 \sum_{i=1}^N (y_i - \bar{y})^2}}$$

### 3.5 Spearman Sıra Korelasyon Katsayısı ($\rho$)
Tahmin ve gerçekleşmelerin göreceli sıralamalarının monotonik uyumunu ölçer:
$$\rho = 1 - \frac{6 \sum_{i=1}^N d_i^2}{N(N^2 - 1)}$$
burada $d_i = \text{rank}(f_i) - \text{rank}(y_i)$'dir.

---

## 4. Olasılık Kalibrasyonu ve Brier Skoru

### 4.1 Brier Skoru
Volatilite genişleme olayı ($o_i \in \{0, 1\}$) için modelin ürettiği olasılık tahmini ($p_i \in [0, 1]$) arasındaki ortalama karesel farktır:
$$\text{Brier} = \frac{1}{N} \sum_{i=1}^N (p_i - o_i)^2$$
* Mükemmel kalibrasyonda Brier skoru 0.0'a yaklaşır.
* Sprint 07 Holdout hedefi: $\le 0.0475$.

### 4.2 5-Bin Güvenilirlik Dağılımı (Reliability Diagram)
Tahmin edilen olasılıklar 5 eşit genişlikteki aralığa bölünür:
* Bin 1: $[0.0, 0.2)$
* Bin 2: $[0.2, 0.4)$
* Bin 3: $[0.4, 0.6)$
* Bin 4: $[0.6, 0.8)$
* Bin 5: $[0.8, 1.0]$

Her aralık için:
* $\bar{p}_b = \frac{1}{|B_b|} \sum_{i \in B_b} p_i$ (Aralıktaki ortalama tahmin olasılığı)
* $\bar{o}_b = \frac{1}{|B_b|} \sum_{i \in B_b} o_i$ (Aralıktaki gerçekleşme frekansı)
Mükemmel kalibre edilmiş bir sistemde $\bar{p}_b \approx \bar{o}_b$ olmalıdır.

---

## 5. Tahmin Aralığı Kapsama Oranı (Predictive Interval Coverage)

Modelin nominal $\%80$ ve $\%95$ güven aralıklarının ($[L_i^{(80)}, U_i^{(80)}]$ ve $[L_i^{(95)}, U_i^{(95)}]$) gerçekleşen değeri kapsama oranıdır:

$$\text{Coverage}_{\alpha} = \frac{1}{N} \sum_{i=1}^N \mathbb{I}(L_i^{(\alpha)} \le y_i \le U_i^{(\alpha)})$$

* **Nominal %80 Hedefi:** Gerçekleşen değerlerin yaklaşık $\%80$'inin bant içinde kalması beklenir.
* **Nominal %95 Hedefi:** Gerçekleşen değerlerin yaklaşık $\%95$'inin bant içinde kalması beklenir.
* **Düşük Kapsama (Under-coverage):** Aşırı güven sendromu (aralıklar piyasa oynaklığına göre fazla dar).
* **Yüksek Kapsama (Over-coverage):** Aşırı temkinli geniş aralıklar (bilgi içeriği düşük).

---

## 6. Sabit Fallback Olasılıkları Adli İncelemesi (Tail & Jump)

Canlı tahmin kayıtlarında `tail_95_probability` değerinin sürekli `0.05` ve `jump_probability` değerinin sürekli `0.01` olduğu tespit edilmiştir.

### Kaynak Analizi (Provenance Diagnosis):
* Model, türev/olay verilerinin bulunmadığı `SPOT_ONLY_U0` koruyucu modunda çalışmaktadır.
* Bu modda kuyruk ve sıçrama olasılıkları, Sprint 01-07 Discovery aşamasında belirlenen **koşulsuz taban oran (unconditional prior base-rate)** sabitlerine (`0.05` ve `0.01`) dönmektedir.
* **Bilimsel Hüküm:** Bu değerler değişken bir dinamik model çıktısı değildir. Bu nedenle yanıltıcı bir izlenim yaratmamak adına dinamik kalibrasyon değerlendirmesinden hariç tutulmuş ve arayüzde açıkça **`MODEL ÇIKTISI DEĞİL / FALLBACK`** olarak etiketlenmiştir.

---

## 7. Model Tahmin Vadeleri ve Geçerli Null Temsili

CBE-0.7.0 mimarisi, araştırma tasarımında yalnızca 3 vade için eğitilmiştir:
* **Aktif Vadeler:** `1h` (1 Saat), `4h` (4 Saat), `24h` (24 Saat).
* **Tanımsız Vadeler:** `15m`, `30m`, `2h`, `8h`, `12h`.

Bu ara vadeler model mimarisinde yer almadığı için Schema V2'de geçerli bir biçimde `null` olarak kaydedilir. Bu durum bir hata veya eksiklik değil, dondurulmuş modelin bilimsel sınırlarının doğru bir temsilidir.

---

## 8. Örneklem Boyutu Güvenilirlik Sınıflandırması

Küçük örneklem boyutlarında istatistiki metriklerin yüksek varyans göstermesi nedeniyle katı ve şeffaf bir güvenilirlik ölçeği uygulanır:

| Örneklem Boyutu ($N$) | Durum | Güvenilirlik | Açıklama |
|---|---|---|---|
| $N < 10$ | **YETERSİZ ÖRNEK** | Güvenilir Değil | İstatistiksel sonuçlar rastlantısaldır; bilimsel yorum yapılamaz. |
| $10 \le N < 30$ | **ERKEN GÖZLEM** | Güvenilir Değil | Erken gözlem aşaması; yüksek varyans barındırır. |
| $30 \le N < 100$ | **GELİŞEN ÖRNEK** | Kısmen Güvenilir | Gelişen örneklem; ilk yapısal eğilimleri gösterir. |
| $N \ge 100$ | **YETERLİ GÖZLEM** | Güvenilir | İstatistiksel karşılaştırma ve hipotez testi için yeterli örneklem. |

---

## 9. Çalışma Zamanı Veri Kalitesi ve Fallback Kısıtı (SPOT ONLY U0)

Canlı ortamda şu anda yalnızca Binance Spot 5m mum akışı ve UTC seans bilgisi aktiftir:
* **Aktif Katmanlar:** Spot Fiyat/Hacim, Seans/Zaman.
* **Eksik Katmanlar:** Türev Piyasalar (Fonlama/OI), Spot ETF Akışları, Makro Göstergeler, Olay Şokları.
* **Sonuç:** Model koruyucu `SPOT_ONLY_U0` seviyesinde ve `DEGRADED_STREAM` veri durumunda çalışmaktadır. Bu gözlem dönemi, modelin tüm bilgi katmanlarının birleşik gücünü temsil etmez.

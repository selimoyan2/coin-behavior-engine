# COIN BEHAVIOR ENGINE — SPRINT 37 NİHAİ KABUL VE BİLİMSEL GEÇERLİLİK RAPORU

**Sprint ID:** `CBE_SPRINT37_MARKET_REGIME_PREDICTIVE_VALIDITY_LAB_V3`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Çalışma Dalı (Branch):** `research/sprint37-predictive-validity`  
**Doğrulanmış Üretim Uygulama SHA:** `313fc5ca242e497f1e221002c798fc5910bd6284`  
**Kanonik Model:** `CBE-0.7.0 — STRICTLY_FROZEN`  
**Yürütme Modu:** `STRICTLY_OFFLINE_RESEARCH`  
**Canlı İşlem (Live Trading):** `PERMANENTLY_PROHIBITED`  
**Üretim Dağıtımı:** `NOT_AUTHORIZED` (`STRICT_ZERO_TOUCH`)  
**Nihai Karar (Verdict):** `SPRINT37_V14_RELEASE_READY_FOR_OPERATOR_APPROVAL`

---

## 1. YÜRÜTME ÖZETİ VE YÖNETİŞİM KARARI

Sprint 37 kapsamında, Coin Behavior Engine bünyesindeki 6 kanonik piyasa rejiminin (`SIDEWAYS`, `UNCERTAIN`, `TRENDING_BULL`, `TRENDING_BEAR`, `POSSIBLE_REVERSAL`, `HIGH_VOLATILITY`) geçmişe dönük yalnızca betimsel (ex-post) birer etiket mi olduğu, yoksa gelecekteki fiyat hareketleri, oynaklık ve düşüş riskleri üzerinde istatistiksel ve ekonomik olarak geçerli tahmin bilgisi (predictive validity) taşıyıp taşımadığı araştırılmıştır.

Araştırma, **bilimsel dürüstlük ve negatif bulguların şeffaf biçimde raporlanması** ilkesiyle yürütülmüştür. Hiçbir spekülatif veya uydurma kârlılık iddiasına yer verilmemiş; modellerin yönsel tahmin gücünün olmadığı durumlar açıkça `NOT_SUPPORTED` olarak belgelenmiştir.

### Temel Yönetişim ve Bilimsel Bulgular:
1. **Mimari Ayrım (Provenance & Architecture Disconnect):** 
   - **Tier 1 (Nominal Dondurulmuş Model CBE-0.7.0):** `NORMAL`, `COMPRESSION`, `EXPANSION_WATCH`, `DELEVERAGING_STRESS` durumları üretmektedir. Tek barlık canlı değerlendirmede yüzdelik sıra çökmesi hatası nedeniyle `DELEVERAGING_STRESS` durumu canlı panellerde `UNKNOWN` olarak bastırılmaktadır. Bu model kesin olarak dondurulmuştur (`STRICTLY_FROZEN`).
   - **Tier 2 (Analitik Türetilmiş Rejimler):** 6 kanonik rejim (`SIDEWAYS`, `UNCERTAIN`, `TRENDING_BULL`, `TRENDING_BEAR`, `POSSIBLE_REVERSAL`, `HIGH_VOLATILITY`) 24h yuvarlanan volatilite ve momentum göstergeleri üzerinden geçmişe dönük genişleyen çeyrekliklerle (expanding quantiles) türetilmektedir. Geleceğe bakış (lookahead) içermez, kesin olarak nedenseldir (point-in-time).
2. **Volatilite Kümelenmesi ve Risk Tahmini Güçlü Şekilde Desteklenmiştir (`SUPPORTED`):**
   - `HIGH_VOLATILITY` rejimine geçiş yapıldığında, takip eden 24 saatlik ileri gerçekleşen volatilite ($RV_{t, t+24h}$), `SIDEWAYS` rejimine kıyasla ortalama 1.49 kat daha yüksek kalmaktadır (Welch $t = +10.02$, $p < 10^{-6}$). Volatilite kümelenmesi ve risk tahmin üstünlüğü ampirik olarak doğrulanmıştır (4h, 12h, 24h, 72h vadelerinde `SUPPORTED`).
3. **Yönsel Getiri ve Naif Tersine Dönüş Hipotezleri Desteklenmemiştir (`NOT_SUPPORTED`):**
   - `SIDEWAYS` ve `UNCERTAIN` rejimlerinde ileri ortalama getiriler tüm vadelerde %0.00'dan farksızdır ($p > 0.50$, FDR $q > 0.90$).
   - `POSSIBLE_REVERSAL` rejimi sonrası tersine dönüş oranı beklenenin aksine düşüktür; trend devamı (%58.2) istatistiksel olarak baskındır (Binomial test $p = 0.000626$).
   - `TRENDING_BULL` ve `TRENDING_BEAR` rejimlerinde 4h-24h vadelerde görülen yönsel sapmalar, **30 bps işlem maliyeti kesintisi** ve **Benjamini-Hochberg FDR düzeltmesi** uygulandığında tamamen erimekte ve istatistiksel/ekonomik alfanın sıfır olduğu görülmektedir.
4. **Örtüşen Veri (Overlapping Sample) Düzeltmesi:**
   - Standart i.i.d. standart hatalarının $\sqrt{H}$ oranında yapay olarak daraldığı ispatlanmış, Newey-West HAC ($H-1$ lag) ve Circular Block Bootstrap (B=500) düzeltmeleriyle gerçek güven aralıklarının sıfırı kestiği kanıtlanmıştır.

---

## 2. GÖREV BAZLI BİLİMSEL ANALİZ VE BULGULAR

### Görev A — Rejim Kökeni ve Nedensellik (Point-in-Time Causal Audit)
- 42.717 saatlik bar (2022-01-01 ile 2026-11-15 arası) taranmıştır.
- Her $t$ anındaki rejim sınıflandırması kesinlikle $t$ anı ve öncesindeki verilerle yapılmıştır.
- Prefix invariance (önek değişmezliği) testi uygulanmış, geleceğe bakış sızıntısı (lookahead leakage) %0 bulunmuştur.

### Görev B — İleri Getiri ve Risk Dağılımları (5 Vade x 6 Rejim)
Her bar için 5 ileri vade incelenmiştir: 1h, 4h, 12h, 24h, 72h.
- İleri Basit ve Log Getiriler: $R_{t, t+H} = \frac{P_{t+H} - P_t}{P_t}$
- Maksimum Olumlu/Olumsuz Sapma: $MFE_{t, t+H} = \frac{\max(P) - P_t}{P_t}$, $MAE_{t, t+H} = \frac{\min(P) - P_t}{P_t}$
- İleri Maksimum Düşüş (Forward Max Drawdown): Pencere içi tepe-dip kaybı
- İleri Gerçekleşen Oynaklık (Forward Realized Volatility)

### Görev C & G — Çoklu Hipotez Düzeltmesi ve Çıkarım Bütünlüğü
- Değerlendirilen toplam hipotez sayısı: $m = 30$ (6 Rejim $\times$ 5 Vade).
- **Benjamini-Hochberg FDR:** Yanlış keşif oranı $q < 0.05$ düzeyinde kontrol edilmiştir.
- **Holm-Bonferroni:** Aile bazlı hata oranı (FWER) basamaklı olarak kontrol edilmiştir.
- Çoklu test düzeltmesi sonucunda ham $p < 0.05$ olan yönsel getiri testlerinin tamamının $q > 0.05$ veya maliyet sonrası negatif getiriye dönüştüğü tespit edilmiştir.

### Görev D — Rejim Geçişi Sonrası İleri Dinamikler (Transition Dynamics)
| Test Hipotezi | Test Türü | Test İstatistiği | $p$-değeri | Bilimsel Karar |
| :--- | :--- | :--- | :--- | :--- |
| **Volatilite Yükselişi** (`HIGH_VOLATILITY` vs `SIDEWAYS`) | Welch iki örneklem t-testi | $t = +10.02$ | $< 10^{-6}$ | **SUPPORTED** |
| **Yönsel Boğa Sürüklenmesi** (`TRENDING_BULL` 24h getiri) | Newey-West HAC t-testi | $t = -0.005$ | $p = 0.996$ | **NOT_SUPPORTED** |
| **Yönsel Ayı Sürüklenmesi** (`TRENDING_BEAR` 24h getiri) | Newey-West HAC t-testi | $t = +0.161$ | $p = 0.872$ | **NOT_SUPPORTED** |
| **Tersine Dönüş Başarısı** (`POSSIBLE_REVERSAL` vs %50) | Binomial Test | $k/n = 58.2\%$ | $p = 0.000626$ | **NOT_SUPPORTED (Devam Yanılgısı)** |
| **Dağılım Ayrışması** (`SIDEWAYS` vs `UNCERTAIN`) | Kolmogorov-Smirnov | $D = 0.057$ | $p = 0.129$ | **NOT_SUPPORTED (Farksız Dağılım)** |

*Not:* `POSSIBLE_REVERSAL` rejiminde binomial test, trendin tersine dönmesinden ziyade trend devamının (%58.2) istatistiksel olarak baskın olduğunu göstermiştir. Bu bulgu, piyasadaki "reversal avcılığı" stratejilerinin yüksek riskini ve getiri yanılgısını ampirik olarak kanıtlamaktadır.

### Görev E — Basit Karşılaştırma Modellerine Karşı Üstünlük (Baselines)
1. **Koşulsuz Getiri (Unconditional Null):** 24 saatlik koşulsuz ortalama getiri $+0.0518\%$ ($+0.05\%$) düzeyindedir (N=42,693, std=2.6064%, pozitif bar frekansı %50.95). `SIDEWAYS` ve `UNCERTAIN` rejimlerinin ortalamaları bu değerden farksızdır.
2. **24h Basit Momentum Modeli:** %47.57 (%47.6) isabet oranı ile rastlantısal yazı-tura sınırındadır.
3. **24h Basit Ortalamaya Dönüş Modeli:** %52.51 (%52.5) isabet oranı vermektedir.
4. **Volatilite Tahmin Üstünlüğü:** Rejim tabanlı oynaklık tahminleri, basit gecikmeli volatilite modeline (Lagged RMSE %17.46) kıyasla Rejim RMSE %16.06 vererek **%8.00 RMSE iyileşmesi** sağlamıştır (`SUPERIOR`).

### Görev F — Yıllık Walk-Forward Kararlılık (2022 - 2026)
Yıllar itibarıyla rejimlerin 24h gerçekleşen volatilite ve ileri ortalama getirileri incelendiğinde:
- `HIGH_VOLATILITY` 24h gerçekleşen forward volatilite her 5 yılda da `SIDEWAYS` rejimini açık ara aşmıştır (2022: %94.06 vs %54.26; 2023: %56.05 vs %36.97; 2024: %65.15 vs %43.23; 2025: %66.87 vs %38.23; 2026: %57.74 vs %36.86).
- Yönsel getirilerde ise 2022 (Sert Ayı) yılında `TRENDING_BULL` negatif forward getiri üretirken, 2024 (ETF Boğası) yılında tüm rejimler yukarı yönlü sürüklenmiştir. Bu durum yönsel alfanın piyasa döngüsünden bağımsız olmadığını doğrulamıştır.

### Görev H — Gerçekçi Ekonomik İşlem Maliyeti Kesintisi
Modelde Binance spot piyasası için standart 30 bps round-trip taker maliyeti uygulanmıştır:
- Taker Komisyonu: 10 bps $\times 2 = 20$ bps
- Alış-Satış Makası (Spread): 2 bps $\times 2 = 4$ bps
- Kayma (Slippage): 3 bps $\times 2 = 6$ bps
- **Toplam Round-Trip Maliyet:** 30 bps (%0.30)
Brüt getirisi pozitif görünen vadelerin dahi net getirisi eksiye inmekte ve ekonomik olarak alfa üretmediği belgelenmektedir.

---

## 3. BİLİMSEL SKOR KARTI ÖZETİ (30 HİPOTEZ)

| Rejim | 1h Vade | 4h Vade | 12h Vade | 24h Vade | 72h Vade |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **SIDEWAYS** | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED |
| **UNCERTAIN** | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED |
| **TRENDING_BULL** | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED |
| **TRENDING_BEAR** | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED |
| **POSSIBLE_REVERSAL**| NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED | NOT_SUPPORTED |
| **HIGH_VOLATILITY** | INCONCLUSIVE | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** | **SUPPORTED** |

- **Toplam Değerlendirilen Hipotez:** 30
- **Desteklenen (SUPPORTED):** 4 (`HIGH_VOLATILITY` oynaklık ve risk öngörüsü — 4h, 12h, 24h, 72h)
- **Desteklenmeyen (NOT_SUPPORTED):** 25 (Yönsel getiri ve tersine dönüş hipotezleri)
- **Belirsiz (INCONCLUSIVE):** 1 (`HIGH_VOLATILITY` 1h vade)
- **Yetersiz Veri (INSUFFICIENT_DATA):** 0
- **Sızıntı Bloke (LEAKAGE_BLOCKED):** 0
- **Matematiksel Toplam Doğrulaması:** $4 + 25 + 1 + 0 + 0 = 30$ (Tam mutabakat)

---

## 4. KULLANICI ARAYÜZÜ (DASHBOARD V14 ADAYI) VE PLAYWRIGHT KABULÜ

Dashboard arayüzü yeni modül ile zenginleştirilmiştir:
1. **Navigasyon:** Üst barda `#predictive-validity` sekmesi eklendi.
2. **Mimari Uyarı Kartı:** Tier 1 Frozen Model ile Tier 2 Analitik Rejimler ayrımı kullanıcıya açıklandı.
3. **Filtreler:** Rejim, Vade ve Karar filtreleri entegre edildi.
4. **Skor Kartı Tablosu:** 30 hipotezin Newey-West HAC, Bootstrap %95 GA ve FDR $q$-değerleri gösterildi.
5. **3 Analitik Panel:** Geçiş dinamikleri, baseline kıyaslamaları ve walk-forward kararlılık panelleri eklendi.
6. **Playwright Otomasyonu:**
   - Masaüstü (1440x900): Kabul edildi (`15_desktop_1440x900.png`)
   - Tablet (768x1024): Kabul edildi (`15_tablet_768x1024.png`)
   - Mobil (390x844): Kabul edildi (`15_mobile_390x844.png`)
   - Konsol ve Sayfa Hataları: 0 hata
   - Canlı İşlem Uç Noktaları: HTTP 403 Forbidden teyit edildi.
   - Karar: `SPRINT37_PLAYWRIGHT_ACCEPTED`

---

## 5. TEST VE REGRESYON METRİKLERİ

- **Sprint 37 Yeni Testleri:** 20 test (`tests/test_sprint37_predictive_validity.py`), 20 passed (%100 başarı).
- **Tam Regresyon Süiti:**
  - Sprint 35: 3.627 passed, 8 skipped
  - Sprint 36: 3.647 passed, 8 skipped
  - **Sprint 37: 3.667 passed, 8 skipped (Toplam 3.675 test)**
  - Başarısızlık (Failures): 0
  - Hata (Errors): 0

---

## 6. SPRINT 37 TESLİMAT MANİFESTİ (17 ARTEFAKT)

1. `01_repository_baseline_and_scope.md`
2. `02_regime_provenance_and_point_in_time.json`
3. `03_forward_return_distributions.json`
4. `04_transition_predictive_validity.json`
5. `05_baseline_comparison.json`
6. `06_walk_forward_validation.json`
7. `07_multiple_testing_correction.json`
8. `08_economic_significance.json`
9. `09_scientific_scorecard.json`
10. `10_dashboard_v14_candidate_spec.json`
11. `11_leakage_and_invariance_audit.json`
12. `12_performance_benchmarks.json`
13. `13_targeted_tests.json`
14. `14_full_regression_results.json`
15. `15_playwright_acceptance.json` (ve `15_desktop_1440x900.png`, `15_tablet_768x1024.png`, `15_mobile_390x844.png`)
16. `16_sha256_delivery_manifest.json`
17. `17_final_acceptance_report.md`

---

## 7. NİHAİ KARAR VE YÖNETİŞİM ONAYI

- **Sprint 37 Kararı:** `SPRINT37_V14_RELEASE_READY_FOR_OPERATOR_APPROVAL`
- **Üretim Dağıtımı:** `NOT_AUTHORIZED` — Operatörün açık onayı olmadan `main` dalına birleştirilmeyecek ve üretim sunucusuna dağıtılmayacaktır.
- **Canlı İşlem:** `PERMANENTLY_PROHIBITED`
- **Sprint 38:** Başlatılmayacaktır. Operatör kararı beklenmektedir.

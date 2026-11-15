# COIN BEHAVIOR ENGINE — SPRINT 35
## NİHAİ KABUL VE YÜRÜTME KURULU DEĞERLENDİRME RAPORU (REVİZYON 2)
### Tarihsel Veri Köken Mutabakatı, Dashboard V12, Güvenli Rollback ve Yayın Kapısı Değerlendirmesi

**Sprint Kimliği:** `CBE_SPRINT35_HISTORICAL_DATA_COMPLETION_DASHBOARD_V12_RELEASE_READINESS`  
**Tarih:** 15–16 Kasım 2026  
**Hedef Dal:** `main` (Mevcut SHA: `c9e3907a226cfbe01e73f87c960156afdd874dc4`)  
**Çalışma Dalı:** `research/sprint33-canonical-bridge-market-intelligence`  
**Aday Commit (Candidate SHA):** `4724a3a57117fabff91229130f836b7af0b71677`  
**Kanonik Model:** `CBE-0.7.0` (STRICTLY_FROZEN)  
**Araştırma Kipi:** `STRICTLY_OFFLINE_RESEARCH`  
**Canlı Ticaret:** `PERMANENTLY_PROHIBITED` (HTTP 403 Forbidden)  
**Üretim Güvencesi:** `STRICT_ZERO_TOUCH` (Konteyner `3ec682ef49a4`, 0 yeniden başlatma)  
**Yayın Kapısı Durumu:** `SPRINT35_RELEASE_READY_FOR_OPERATOR_APPROVAL`  

---

## 1. GÖREV 1 — EKİM 2026 VERİ KÖKEN MUTABAKATI (ADLİ DOĞRULAMA)

### A. İlk Taslaktaki Çelişkinin Çözümü
Önceki taslak metinde yer alan "44.220 adet 1m CSV + 84 adet 5m JSONL" açıklaması, kod geliştirme aşamasındaki bir taslak notun sehven rapora yansımasıdır; depoda böyle bir CSV bulunmamaktadır. `02_october_2026_recovery.json` dosyasında belgelenen **5.034 + 3.894 adet 5m bar** mimarisi gerçek, fiziksel ve doğrulanabilir kanonik uygulamadır.

### B. Gerçek Kaynak Dosyalarının Doğrulama Tablosu

| Kaynak | Dosya Yolu / Konumu | Format | SHA-256 Özeti | Boyut | Ham Kayıt Aralığı | Ekim 2026 Katkısı (5m) |
|---|---|---|---|---:|---|---:|
| **Kaynak 1 (Arşiv)** | `data/research_lab/binance_BTCUSDT_1m_recent.parquet` | Parquet | `8d2719fe8a24e2ea6bb35b9b529e06238a0b42c38a3cc9dfab4bf380cfed1286` | 1.326.957 B | 2026-09-23 11:34 — 2026-10-18 11:33 UTC (36.000 satır) | **5.034 bar** (2026-10-01 00:00 — 2026-10-18 11:25 UTC) |
| **Kaynak 2 (Canlı Besleme)** | `srv1114257:/var/lib/docker/volumes/zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data/_data/raw_market/raw_candles_BTCUSDT_5m.jsonl` | JSONL | `8701ef9eba9b8761a4bc3d8e688ddeba82c7cacc931b12b1d326f9ff5c082dd6` | 9.151.259 B | 2026-10-09 23:00 — 2026-11-15 21:50 UTC (10.494 satır) | **3.894 bar** (2026-10-18 11:30 — 2026-10-31 23:55 UTC) |
| **TOPLAM** | `data/binance_spot_multiyear/5m/BTCUSDT-5m-2026-10.parquet` | Parquet | `54030be91ce45807d47f4f47d9349d64d6b45f872bafd298f5901c9235b772bd` | 231.258 B | 2026-10-01 00:00 — 2026-10-31 23:55 UTC | **8.928 bar** (%100 Tam Kapsam) |

### C. Dikiş Noktası (Junction) Fiziksel Süreklilik Doğrulaması
- **Kaynak 1 Son Barı (İndeks 5033):** `2026-10-18 11:25:00 UTC` &bull; Kapanış: `82.104,03 USDT` &bull; Hacim: `8,73527 BTC`
- **Kaynak 2 İlk Barı (İndeks 5034):** `2026-10-18 11:30:00 UTC` &bull; Açılış: `82.104,03 USDT` &bull; Kapanış: `82.029,90 USDT` &bull; Hacim: `14,30581 BTC`
- **Zaman Farkı:** $1.792.323.000.000 - 1.792.322.700.000 = 300.000\text{ ms} = 300\text{ s}$ (Tam 5 dakika, 0 boşluk).
- **Fiyat Farkı:** $|Open_{5034} - Close_{5033}| = 0,00\text{ USDT}$ (Kusursuz fiyat sürekliliği).
- **Sonuç:** 8.928 barın tamamı gerçek borsa kayıtlarına dayanmaktadır; tek bir sentetik veya simüle edilmiş bar bulunmamaktadır. `COMPLETE_VERIFIED` statüsü matematiksel ve adli olarak teyit edilmiştir.

---

## 2. GÖREV 2 — KASIM 2026 VERİ BOŞLUKLARI VE KISMİ ZAMAN DİLİMLERİ

### A. Doğrulanmış Kesme Zamanı ve Kapsam
- **Doğrulanmış Bitiş Zamanı:** `2026-11-15 21:15:00 UTC` (Açılış Zaman Damgası: `1794777300000 ms`).
- **Toplam 5m Bar Sayısı:** 4.280 bar (Teorik tam ay: 8.640 bar, Gerçekleşen doluluk: %49,54).

### B. 8 Eksik 5m Mumunun Kesin Tarih ve Zaman Dökümü
Canlı veri toplama soketindeki geçici ağ gecikmeleri ve soket yenilemeleri nedeniyle oluşan 4 boşluk dönemi:
1. `2026-11-03 05:10:00+00:00` — `2026-11-03 05:30:00+00:00` (**3 Eksik Bar**: 05:15, 05:20, 05:25 UTC — 20 dk)
2. `2026-11-04 21:55:00+00:00` — `2026-11-04 22:05:00+00:00` (**1 Eksik Bar**: 22:00 UTC — 10 dk)
3. `2026-11-05 01:30:00+00:00` — `2026-11-05 01:40:00+00:00` (**1 Eksik Bar**: 01:35 UTC — 10 dk)
4. `2026-11-07 08:55:00+00:00` — `2026-11-07 09:15:00+00:00` (**3 Eksik Bar**: 09:00, 09:05, 09:10 UTC — 20 dk)  
**Toplam:** 8 Eksik Mum (40 dakika).

### C. Sıfır Sentetik Veri Güvencesi ve Dashboard V12 Gösterimi
- Eksik 8 mum kesinlikle yapay/interpolasyon ile doldurulmamış, fiziksel piyasa gerçekliği korunmuştur.
- **Dashboard V12 UI Güncellemesi:** Veri Kapsamı Paneli altında (`#quality-gap-report`), Kasım 2026 için bu 8 eksik mumun tarihleri ve süreleri açık bir uyarı rozetiyle kullanıcıya gösterilmektedir.
- **Kısmi Zaman Dilimleri Denetimi:**
  - 15m: 1.428 bar (`PARTIAL_VERIFIED`)
  - 1h: 358 bar (`PARTIAL_VERIFIED`)
  - 4h: 90 bar (`PARTIAL_VERIFIED`)
  - 1d: 15 bar (`PARTIAL_VERIFIED`)

---

## 3. GÖREV 3 — GÜVENLİ ÜRETİM DAĞITIM VE GERİ ALMA PLANI

### A. Ortak Ata ve Fast-Forward Doğrulaması
- `git merge-base origin/main HEAD` sorgusu tam olarak `c9e3907a226cfbe01e73f87c960156afdd874dc4` SHA'sını döndürmektedir.
- `git merge-base --is-ancestor origin/main HEAD` çıkış kodu `0`dır.
- Araştırma dalı, `main` dalının doğrudan, doğrusal (linear) devamıdır (13 ardışık commit).
- **`git merge --ff-only` işlemi %100 temiz ve çelişkisiz çalışacaktır.**

### B. İmaj Digest'leri ve 295 Parquet Dosyası Tescili
- **Canlı Üretim İmajı (Geri Alma Hedefi):** `6t63aehpaw0cw1bbt4zcm09g:c9e3907a226cfbe01e73f87c960156afdd874dc4` &bull; İmaj ID: `sha256:6969f8cb761cb01fc783c1ffbb2b896be8c98f975ed9a438e5d02b4c4820047f`.
- **Aday Staging İmajı (Sprint 35):** `cbe-market-intelligence:sprint35-ec7d393` &bull; İmaj ID: `sha256:20e9fe8ac295326c9f43959bff36bbc16993305003a6abd6fcf6dfbdb49784d2`.
- **Konteyner İçi Parquet Doğrulaması:** `docker exec fa065f377c81 find /app/data/binance_spot_multiyear -name "*.parquet"` ile imaj içerisinde tam **295 adet Parquet dosyası** (5 zaman dilimi $\times$ 59 ay) fiziksel olarak doğrulanmıştır.

### C. Geri Alma (Rollback) Planının Staging Ortamında Test Edilmesi
- Staging sunucusunda (`srv1114257`) izole port 18081 üzerinde önceki üretim imajı (`6t63aehpaw...`) ayağa kaldırılmış; konteynerin 3 saniyede `healthy` olduğu, `/health` ve `/available-dates` uç noktalarının 57 aylık Eylül 2026 durumunu kusursuz sunduğu teyit edilmiş ve konteyner temizlenmiştir.
- **Güvenli Rollback Yöntemi:**
  1. Coolify arayüzünden önceki dağıtıma (`6t63aehpaw0cw1bbt4zcm09g-20261115T212024`) tek tıkla geri dönülür (< 5 saniye).
  2. Git düzeyinde gereksinim olursa `git revert` kullanılır. **`git push --force` ve `git reset --hard` kullanımı kesinlikle yasaklanmıştır.**

---

## 4. GÖREV 4 — NİHAİ KABUL BEYANI VE ÖZET METRİKLER

- **Kesin Üretim Adayı Commit SHA:** `4724a3a57117fabff91229130f836b7af0b71677`
- **Ekim Kaynak Mutabakatı:** 5.034 bar (1m Parquet) + 3.894 bar (Canlı JSONL) = 8.928 bar (%100 Tam, 0 sentetik).
- **Kasım Veri Boşlukları:** 8 eksik 5m mumu açıkça listelenmiş, sentetik doldurma yapılmamış, V12 paneline eklenmiştir.
- **Staging İmaj ID:** `sha256:20e9fe8ac295326c9f43959bff36bbc16993305003a6abd6fcf6dfbdb49784d2`
- **Üretim İmaj ID:** `sha256:6969f8cb761cb01fc783c1ffbb2b896be8c98f975ed9a438e5d02b4c4820047f`
- **Güvenli Merge:** `git merge --ff-only research/sprint33-canonical-bridge-market-intelligence`
- **Güvenli Rollback:** Coolify imaj redeploy veya `git revert` (Sıfır force push).
- **Üretime Geçiş Sonrası Doğrulama:**
  - `curl -I https://coin.ozelweb.com.tr/health` (HTTP 200)
  - `curl -s "https://coin.ozelweb.com.tr/api/v1/product/available-dates?interval=5m"` (59 ay, `latest_month: "2026-11"`)
  - `curl -X POST https://coin.ozelweb.com.tr/api/v1/product/order/execute` (HTTP 403 Forbidden)
- **Tam Regresyon Sonucu:** 3.627 geçti / 0 başarısız (100%).
- **Playwright Testleri:** Masaüstü, Tablet, Mobil sıfır konsol ve sayfa hatası ile doğrulandı.

---

### YAYIN KAPISI KARARI

```text
================================================================================
SONUÇ: SPRINT35_RELEASE_READY_FOR_OPERATOR_APPROVAL
================================================================================
Üretim ortamına (coin.ozelweb.com.tr) dokunulmamıştır.
main dalına push yapılmamıştır.
Coolify deploy işlemi tetiklenmemiştir.
Tüm teknik, adli ve operasyonel gereksinimler %100 tamamlanmış olup
canlıya aktarım insan operatörün açık onayına hazır hale getirilmiştir.
================================================================================
```

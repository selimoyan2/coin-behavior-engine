# COIN BEHAVIOR ENGINE — SPRINT 37.2
## NİHAİ ÜRETİM DAĞITIM VE BİLİMSEL GEÇERLİLİK KABUL RAPORU

**Sprint ID:** `CBE_SPRINT37_2_PRODUCTION_RELEASE`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Üretim Dalı (Branch):** `main`  
**Üretim HEAD SHA:** `057d0af32b9de15a8d54ed9bcf0605727960ea6c`  
**Üretim URL:** `https://coin.ozelweb.com.tr`  
**Coolify Uygulama UUID:** `6t63aehpaw0cw1bbt4zcm09g`  
**Yeni Üretim Konteyner ID:** `46bfe4cf2031` (`6t63aehpaw0cw1bbt4zcm09g-20261116T205140`)  
**Önceki Üretim Konteyner ID:** `b2cb2c5b662d`  
**Önceki Korunan İmaj:** `6t63aehpaw0cw1bbt4zcm09g:313fc5ca242e497f1e221002c798fc5910bd6284`  
**Kanonik Model:** `CBE-0.7.0 — STRICTLY_FROZEN`  
**Yürütme Modu:** `STRICTLY_OFFLINE_RESEARCH`  
**Canlı İşlem:** `PERMANENTLY_PROHIBITED (HTTP 403)`  
**Nihai Karar (Verdict):** `SPRINT37_V14_PRODUCTION_RELEASE_SUCCESS_VERIFIED`

---

## 1. YÜRÜTME ÖZETİ VE YÖNETİŞİM BEYANI

Sprint 37 ve 37.1 kapsamında geliştirilen ve doğrulanan **Dashboard V14 — Market Regime Predictive Validity & Scientific Research Lab V3**, operatör onayıyla kontrollü olarak `https://coin.ozelweb.com.tr` üretim ortamına aktarılmıştır.

Tüm dağıtım kapıları (release gates) sırasıyla işletilmiş, ön yedekleme tamamlanmış, fast-forward merge uygulanmış, Coolify üzerinden tekil kontrollü derleme yürütülmüş ve canlı üretim ortamında API, veri kapsamı, bilimsel skor kartı, live trading kısıtlaması ve multi-viewport Playwright görsel kabul testleri tam başarıyla tamamlanmıştır.

---

## 2. GÖREV BAZLI KABUL KANITLARI

### Görev A — Git ve Kaynak Kodu Doğrulaması
- `origin/research/sprint37-predictive-validity` HEAD SHA: `057d0af32b9de15a8d54ed9bcf0605727960ea6c`.
- `origin/main` öncesi SHA: `4512791508d562c960a79e25be7a99ef83ed7293`.
- `git merge-base --is-ancestor origin/main origin/research/sprint37-predictive-validity` sıfır çıkış koduyla teyit edildi.
- Değişiklik kapsamı: CBE-0.7.0 model dondurma durumu korunmuş, 0 parametre mutasyonu yapılmıştır.

### Görev B — Üretim Öncesi Güvenlik ve Yedekleme
- Önceki aktif konteyner: `b2cb2c5b662d` (0 restart, kesintisiz çalışır durumda denetlendi).
- Önceki imaj korundu: `6t63aehpaw0cw1bbt4zcm09g:313fc5ca242e497f1e221002c798fc5910bd6284` (`cbe-production-rollback-baseline:sprint36.1` olarak etiketlendi).
- Kalıcı veri yedeklemesi: `/var/lib/docker/volumes/6t63aehpaw0cw1bbt4zcm09g-cbe_prospective_data/_data` dizinindeki 7 dosya (`current_state.json`, `lockbox_manifest.json`, `sessions.db`, `outcomes.jsonl`, `audit_log.jsonl`, `predictions.jsonl`) `/root/cbe_backups/sprint37_2_predeploy` altına güvenle yedeklendi (SQLite online backup uygulandı).

### Görev C — Bilimsel Sonuçların Doğrulanması
- **Toplam 30 Hipotez:**
  - `SUPPORTED`: 4 (`HIGH_VOLATILITY` rejiminde 4h, 12h, 24h, 72h vadeleri)
  - `NOT_SUPPORTED`: 25 (Tüm vadelerde yönsel getiri ve tersine dönüş hipotezleri)
  - `INCONCLUSIVE`: 1 (`HIGH_VOLATILITY` 1h vadesi)
  - Toplam kontrolü: $4 + 25 + 1 = 30$ (Tam mutabakat).
- **Basit Kıyaslama (Baselines):**
  - Koşulsuz 24h ortalama getiri: $+0.0518\%$
  - 24h Momentum hit rate: %47.57
  - 24h Mean-reversion hit rate: %52.51
  - Gecikmeli Volatilite RMSE: %17.46, Rejim Volatilitesi RMSE: %16.06 (%8.00 iyileşme, `SUPERIOR`).

### Görev D — Staging Kabulü
- `srv1114257:18080` üzerinde `cbe-predictive-validity-staging-sprint37` denetlendi:
  - `/health`: HTTP 200, CBE-0.7.0 FROZEN.
  - Skor kartı: 30 hipotez (4 SUPPORTED, 25 NOT_SUPPORTED, 1 INCONCLUSIVE).
  - Canlı işlem uç noktaları: HTTP 403.
  - Tam regresyon: 3.667 passed, 8 skipped, 0 failed.

### Görev E & F — Main Terfisi ve Coolify Dağıtımı
- `main` dalı `057d0af32b9de15a8d54ed9bcf0605727960ea6c` SHA'sına fast-forward merge ile terfi ettirildi ve `origin/main`e pushlandı.
- Coolify Deployment `76ddf881-263e-4865-8a52-9011ef55575f` 218 saniyede başarıyla tamamlandı.
- Yeni konteyner `46bfe4cf2031` ayağa kalktı ve healthy durumuna geçti.

### Görev G — Üretim Kabul Testleri
Doğrudan `https://coin.ozelweb.com.tr` URL'sinde:
1. `GET /health` -> HTTP 200, `status: healthy`, `model_version: CBE-0.7.0`, `model_status: FROZEN`.
2. `GET /api/v1/product/runtime-build` -> HTTP 200, `build_commit: 057d0af32b9de15a8d54ed9bcf0605727960ea6c`, `runtime_identity_verified: true`.
3. `GET /api/v1/product/central-coverage` -> HTTP 200, 59 ay (2022-01..2026-11), 58 tam + 1 kısmi, son mum 2026-11-15 21:15 UTC, 8 eksik 5m mum, 0 sentetik mum.
4. `GET /api/v1/product/predictive-validity/scorecard` -> HTTP 200, 30 hipotez (4 SUPPORTED, 25 NOT_SUPPORTED, 1 INCONCLUSIVE, toplam=30).
5. `GET /api/v1/product/predictive-validity/baselines` -> HTTP 200, uncond: +0.0518%, mom: 47.57%, mr: 52.51%, vol RMSE: 17.46 vs 16.06.
6. `POST /place-order` ve `/live-trade/execute` -> HTTP 403 Forbidden.

### Görev H — Dashboard V14 Görsel Kabul (Playwright)
Canlı üretim URL'sinde masaüstü, tablet ve mobilde Playwright çalıştırıldı:
- Masaüstü (1440x900): `12_prod_desktop_1440x900.png` — Kabul edildi.
- Tablet (768x1024): `12_prod_tablet_768x1024.png` — Kabul edildi.
- Mobil (390x844): `12_prod_mobile_390x844.png` — Kabul edildi.
- Filtre Testi: `SUPPORTED` (4 satır, KPI=4), `NOT_SUPPORTED` (25 satır, KPI=25), `INCONCLUSIVE` (1 satır, KPI=1), `ALL` (30 satır, KPI=30) kusursuz çalıştı.
- Konsol ve Sayfa Hataları: 0 hata.
- Karar: `SPRINT37_2_PRODUCTION_PLAYWRIGHT_ACCEPTED`.

### Görev I — Performans ve Kaynak Kullanımı
- CPU Kullanımı: %0.01
- Bellek: 306.8 MiB / 7.755 GiB (%3.86)
- Uç Nokta Yanıt Süreleri: 250 - 430 ms (ortalama).

### Görev J — Rollback Hazırlığı
- Rollback imajı `6t63aehpaw0cw1bbt4zcm09g:313fc5ca242e497f1e221002c798fc5910bd6284` yerel olarak korunmaktadır.
- Dağıtım %100 başarılı olduğu için rollback tetiklenmemiştir.

---

## 3. NİHAİ KABUL VE YÖNETİŞİM BİLGİLENDİRMESİ

- **Sprint 37.2 Nihai Kararı:** `SPRINT37_V14_PRODUCTION_RELEASE_SUCCESS_VERIFIED`
- **Üretim Durumu:** Dashboard V14 canlıda aktiftir (`https://coin.ozelweb.com.tr`).
- **Canlı Alım-Satım:** `PERMANENTLY_PROHIBITED` (HTTP 403).
- **Sprint 38:** Başlatılmamıştır. Operatörün bir sonraki talimatı beklenmektedir.

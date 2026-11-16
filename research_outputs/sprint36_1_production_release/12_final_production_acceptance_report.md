# COIN BEHAVIOR ENGINE — SPRINT 36.1 KONTROLLÜ ÜRETİM DAĞITIM RAPORU
## DASHBOARD V13 VE PİYASA DAVRANIŞI LABORATUVARI V2 CANLI YAYIN TESCİLİ

**Sprint:** `CBE_SPRINT36_1_CONTROLLED_PRODUCTION_RELEASE`  
**Tarih / Saat:** 2026-11-16T10:16:00+03:00 (07:16:00Z)  
**Canlı Üretim URL:** `https://coin.ozelweb.com.tr`  
**Üretim Konteyner ID:** `b2cb2c5b662d` (`6t63aehpaw0cw1bbt4zcm09g:313fc5ca242e497f1e221002c798fc5910bd6284`)  
**Dağıtılan Üretim Commit SHA:** `313fc5ca242e497f1e221002c798fc5910bd6284`  
**Önceki Üretim Temeli:** `d8b59b35203338ca8b4311707632cc204a83a0cc` / `f342e40546eca538db54d8d32861f6946617dd0b`  
**Kanonik Model:** `CBE-0.7.0` — `STRICTLY_FROZEN`  
**Canlı Ticaret (Live Trading):** `PERMANENTLY_PROHIBITED` (HTTP 403 Forbidden ile kesin engelli)  
**Nihai Karar (Verdict):** `SPRINT36_V13_PRODUCTION_RELEASE_SUCCESS_VERIFIED`

---

## 1. YÖNETİCİ ÖZETİ

Operatörün açık onayı (`APPROVED — DASHBOARD V13 RESEARCH RELEASE ONLY`) doğrultusunda, Dashboard V13 ve Piyasa Davranışı Araştırma Laboratuvarı V2 başarıyla `main` dalına terfi ettirilmiş ve Coolify üzerinden `https://coin.ozelweb.com.tr` üretim ortamına kontrollü biçimde aktarılmıştır.

Dağıtım süreci tüm güvenlik kapılarını (sıfır veri kaybı, dondurulmuş model mimarisi, canlı alım-satım yasağı, geriye dönük tam uyumluluk ve anlık rollback hazırlığı) %100 başarıyla geçmiştir.

---

## 2. GÖREV TAMAMLAMA VE DOĞRULAMA KANITLARI

### Görev A — Git ve Commit Doğrulaması
- `origin/main` dalının araştırma dalının atası olduğu `git merge-base --is-ancestor` ile doğrulanmıştır.
- `main` dalına yalnızca doğrusal (fast-forward, `--ff-only`) birleşme uygulanmıştır.
- Dağıtılan commit: `313fc5ca242e497f1e221002c798fc5910bd6284`.

### Görev B — Dağıtım Öncesi Yedekleme
- Önceki üretim konteyneri `d20a430d9704` üzerinden tüm prospective kayıtları, lockbox manifestoları ve denetim günlükleri `/root/cbe_backups/sprint36_predeploy_20261116_070935` dizinine yedeklenmiştir.
- Önceki üretim imajı anında geri dönüş için `cbe-production-rollback-sprint35:f342e40` olarak etiketlenmiştir.
- Yedeklenen 9 dosyanın SHA-256 özetleri doğrulanmış ve okunabilirlik testi yapılmıştır.

### Görev C — Son Staging Doğrulaması
- Port 18080 üzerindeki staging konteyneri 10 kritik kontrol noktasından (Dashboard V13, 59 ay kapsam, Ekim tam, Kasım kısmi, 8 eksik mum, rejim geçişleri, risk metrikleri, tarih filtreleri, duyarlı arayüz ve 403 yasağı) başarıyla geçmiştir.
- Tam regresyon paketi: **3.647 passed, 8 skipped, 0 failed**.

### Görev D — Kontrollü Main Terfisi
- `main` dalı yerel olarak `origin/main` ile senkronize edilmiş, ardından `git merge --ff-only` ile araştırma dalı merge edilmiştir.
- `git push origin main` komutuyla `origin/main` güncellenmiştir.

### Görev E — Coolify Üretim Dağıtımı
- Coolify üzerinde uygulama kimliği `6t63aehpaw0cw1bbt4zcm09g` doğrulanmış, `37396965-40cc-4978-861b-731140dc7cc6` dağıtım kimliğiyle imaj derlenmiştir.
- Yeni konteyner `b2cb2c5b662d` port 8000 üzerinde `healthy` durumuna geçmiştir.
- Traefik reverse proxy yönlendirmesi kesintisiz olarak yeni konteyneri karşılamaktadır.

### Görev F — Canlı Üretim Kabul Testleri
1. **Sağlık ve Sürüm:**
   - `GET https://coin.ozelweb.com.tr/health` -> HTTP 200 OK (CBE-0.7.0 FROZEN).
   - `GET https://coin.ozelweb.com.tr/api/v1/product/runtime-build` -> `build_commit: 313fc5ca242e497f1e221002c798fc5910bd6284`, `runtime_identity_verified: true`.
2. **Merkezi Veri Kapsamı:**
   - `GET https://coin.ozelweb.com.tr/api/v1/product/central-coverage` -> 58 tam ay + 1 kısmi ay (toplam 59 ay, 2022-01..2026-11). Son doğrulanmış mum: `2026-11-15 21:15 UTC` ($64.966,01 USDT). 8 eksik mum doğru bildirilmektedir.
3. **Piyasa Laboratuvarı API'leri:**
   - Rejim Geçişleri: 42.716 adet geçiş, $6 \times 6$ matris.
   - Risk Göstergeleri: Tarihsel Max Drawdown -%67.38, Yıllık Downside Dev %39.44, $\text{VaR}_{95}$ %0.76, $\text{VaR}_{99}$ %1.63, $\text{CVaR}_{95}$ %1.30, $\text{CVaR}_{99}$ %2.33.
4. **Canlı Ticaret Yasağı:**
   - `POST https://coin.ozelweb.com.tr/api/v1/product/research/btc-timing/place-order` -> **HTTP 403 Forbidden**.
5. **Playwright Doğrulaması:**
   - Masaüstü (1440x900), Tablet (768x1024), Mobil (390x844) çözünürlüklerinde doğrudan canlı ortam test edilmiş; 0 sayfa hatası ile kabul edilmiştir.

### Görev G — Rollback Hazırlığı
- Rollback imajı ve yedek veri dizini hazırdır. Acil durumda 60 saniye içinde Sprint 35 temeline dönülebilir.

---

## 3. ÜRETİLEN ARTEFAKTLAR LİSTESİ

`research_outputs/sprint36_1_production_release/` dizininde üretilen ve doğrulanabilir teslimat dosyaları:
1. `01_operator_authorization.md`
2. `02_git_sha_and_fast_forward_verification.json`
3. `03_predeployment_backup_manifest.json`
4. `04_staging_final_verification.json`
5. `05_coolify_deployment_evidence.json`
6. `06_production_runtime_identity.json`
7. `07_production_data_coverage.json`
8. `08_market_behavior_api_acceptance.json`
9. `09_live_trading_prohibition.json`
10. `10_production_playwright_results.json` (+ `10_prod_desktop.png`, `10_prod_tablet.png`, `10_prod_mobile.png`)
11. `11_rollback_readiness.json`
12. `12_final_production_acceptance_report.md`

---

## 4. NİHAİ KARAR

Tüm ön koşullar, dağıtım adımları, canlı sağlık kontrolleri ve kabul testleri eksiksiz ve sıfır hatayla tescil edilmiştir.

$$\mathbf{SPRINT36\_V13\_PRODUCTION\_RELEASE\_SUCCESS\_VERIFIED}$$

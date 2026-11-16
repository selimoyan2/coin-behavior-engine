# SPRINT 36.1 — OPERATÖR YETKİLENDİRME VE DAĞITIM SINIRLARI

**Sprint:** `CBE_SPRINT36_1_CONTROLLED_PRODUCTION_RELEASE`  
**Tarih / Saat:** 2026-11-16T07:10:00Z  
**Operatör Onayı:** `APPROVED — DASHBOARD V13 RESEARCH RELEASE ONLY`  
**Hedef URL:** `https://coin.ozelweb.com.tr`  
**Kanonik Model:** `CBE-0.7.0` — `STRICTLY_FROZEN`  
**Canlı Ticaret:** `PERMANENTLY_PROHIBITED`  

## Kapsam ve İzinler
Operatör tarafından yalnızca aşağıdaki araştırma ve arayüz kabiliyetlerinin canlıya alınmasına onay verilmiştir:
1. Dashboard V13 arayüzü ve Piyasa Davranışı Laboratuvarı V2 bileşenleri.
2. Merkezi veri kapsamı servisi (2022-01 .. 2026-11, 58 tam + 1 kısmi ay).
3. 6 sınıflı mum kalitesi göstergeleri ve Kasım ayı boşluk analizleri.
4. $6 \times 6$ rejim geçiş matrisi ($P_{ij}$) ve süre göstergeleri.
5. Tarihsel piyasa riski göstergeleri (Max Drawdown -%67.38, Downside Dev %39.44, VaR, CVaR).
6. Salt-okunur araştırma API uç noktaları.

## Kesin Yasaklar (Invariants)
- Canlı alım-satım ve emir gönderme yetkisi kesinlikle açılamaz (HTTP 403 Forbidden).
- CBE-0.7.0 model ağırlıkları ve parametreleri dondurulmuştur; hiçbir mutasyona izin verilmez.
- Lockbox ve prospective denetim günlükleri üzerine yazılamaz veya değiştirilemez.
- Otomatik ticaret veya portföy yürütme botları devreye alınamaz.

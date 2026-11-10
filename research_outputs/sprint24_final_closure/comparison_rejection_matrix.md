# Bilimsel Karşılaştırma Reddetme Matrisi (Comparison Rejection Matrix)

**Model:** `CBE-0.7.0` (FROZEN)  
**Yönetişim:** `TECHNICAL_NO_GO`  
**Taahhüt:** `cd588ebfd06903c82ab9eaa7f30e18378adf1bdc`  

Aşağıdaki matris, mevcut kanonik katalog kayıtları arasındaki karşılaştırma taleplerinin bilimsel uyumluluk kapısındaki (`evaluate_comparison_compatibility`) nihai sonuçlarını özetler:

| Aday Çifti | Kadans Uyumu | Zaman Örtüşmesi | Metrik Sözleşmesi | Karar | Red Kodu | Bilimsel Gerekçe |
|---|---|---|---|---|---|---|
| `RES-REGIME-01` ↔ `RES-ANALOG-01` | Uyumlu (1h) | ✕ Yetersiz | ✕ Uyumsuz | **FAIL-CLOSED** | `INSUFFICIENT_OVERLAP_EVIDENCE` | REGIME-01 zaman sınırları eksik; Parkinson oranı ile realize volatilite yüzdesi karıştırılamaz. |
| `RES-FUND-01` ↔ `RES-REGIME-01` | ✕ Uyumsuz (8h vs 1h) | - | - | **FAIL-CLOSED** | `SAMPLING_CADENCE_MISMATCH` | Farklı zaman kadansları normalizasyon olmaksızın karşılaştırılamaz. |
| `RES-FUND-01` ↔ `RES-ANALOG-01` | ✕ Uyumsuz (8h vs 1h) | - | - | **FAIL-CLOSED** | `SAMPLING_CADENCE_MISMATCH` | Farklı zaman kadansları normalizasyon olmaksızın karşılaştırılamaz. |
| `RES-REGIME-01` ↔ `RES-CRYPTO-01` | Uyumlu (1h) | - | - | **FAIL-CLOSED** | `QUARANTINED_RECORD` | `RES-CRYPTO-01` karantinaya alınmış veridir; bilimsel karşılaştırmaya dahil edilemez. |
| `RES-ANALOG-01` ↔ `RES-MACRO-01` | ✕ Uyumsuz (1h vs 24h) | - | - | **FAIL-CLOSED** | `SAMPLING_CADENCE_MISMATCH` | Kadans uyuşmazlığı. |
| `RES-DURABILITY-01` ↔ (Herhangi Biri) | - | - | - | **FAIL-CLOSED** | `NON_SCIENTIFIC_RECORD` | Durability raporu bilimsel araştırma değil, operasyonel dayanıklılık kanıtıdır. |
| `RES-COMPAT-01` ↔ `RES-COMPAT-02` | Uyumlu (1h) | ✓ 3624 Bar | ✓ Volatility Ratio | **PASS** | `VALIDATED` | Tam zaman örtüşmesi ve aynı metrik sözleşmesi altında fark analizi hesaplanır. |

# Comparison Negative Test Matrix
**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_24_CORRECTION`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Branch:** `main`  
**Implementation Commit:** `54c43cdceedf22214bb0f01cb908b8ba6fabe48e`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY_FROZEN)

---

## 1. Overview

The Comparison Negative Test Matrix validates that all invalid candidate combinations are rejected fail-closed by the 12-Point Scientific Compatibility Gate, with complete suppression of difference analysis calculations and explicit diagnostic error messages.

---

## 2. Negative Test Scenarios Matrix

| Case ID | Input Candidates | Failure Mode | Expected Rejection Code | Actual Rejection Code | Difference Analysis Suppressed? | Turkish Diagnostic Reason | Verification Reference |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **NEG-01** | `["RES-FUND-01"]` | Insufficient selection ($N=1$) | `INSUFFICIENT_SELECTION` | `INSUFFICIENT_SELECTION` | Yes (`[]`) | "Karşılaştırma için en az 2 araştırma kaydı seçilmelidir." | `test_gate_rejects_single_candidate_or_overflow` |
| **NEG-02** | 5 candidate IDs | Limit exceeded ($N=5$) | `SELECTION_LIMIT_EXCEEDED` | `SELECTION_LIMIT_EXCEEDED` | Yes (`[]`) | "CPU ve bellek güvenliği için en fazla 4 araştırma kaydı karşılaştırılabilir." | `test_gate_rejects_single_candidate_or_overflow` |
| **NEG-03** | `["RES-REGIME-01", "NONEXISTENT-99"]` | Missing candidate record | `RESEARCH_NOT_FOUND` | `RESEARCH_NOT_FOUND` | Yes (`[]`) | "Belirtilen araştırma kaydı bulunamadı: 'NONEXISTENT-99'." | `test_gate_rejects_unknown_candidates` |
| **NEG-04** | `["RES-REGIME-01", "RES-CRYPTO-01"]` | Contaminated / quarantined data | `QUARANTINED_RECORD` | `QUARANTINED_RECORD` | Yes (`[]`) | "Karantinaya alınmış veya uygun olmayan kayıtlar (RES-CRYPTO-01) bilimsel karşılaştırmaya dahil edilemez." | `test_gate_rejects_quarantined_record`<br>Playwright Scenario 24 |
| **NEG-05** | `["RES-FUND-01", "RES-REGIME-01"]` | Cadence mismatch (`8h` vs `1h`) | `SAMPLING_CADENCE_MISMATCH` | `SAMPLING_CADENCE_MISMATCH` | Yes (`[]`) | "Farklı zaman kadansları saptandı (1h, 8h). Bilimsel olarak onaylanmış bir kadans normalizasyonu bulunmadığından karşılaştırma fail-closed kuralı gereği engellenmiştir." | `test_gate_rejects_cadence_mismatch`<br>Playwright Scenario 24 |
| **NEG-06** | `["RES-REGIME-01", "RES-DURABILITY-01"]` | Methodology mismatch (Market vs Disk Durability) | `METHODOLOGY_MISMATCH` | `METHODOLOGY_MISMATCH` | Yes (`[]`) | "Metodoloji uyumsuzluğu: Sistem Güvenilirliği ile diğer kategoriler doğrudan karşılaştırılamaz." | `test_gate_rejects_methodology_mismatch` |
| **NEG-07** | Stored comparison with cadence mismatch | Dynamic revalidation on load | `SAMPLING_CADENCE_MISMATCH` | `SAMPLING_CADENCE_MISMATCH` | Yes (`[]`) | "Bu kayıt kaydedildikten sonra bilimsel uyumluluk kuralları sıkılaştırılmış olup, fail-closed doğrulaması başarısız olmuştur (SAMPLING_CADENCE_MISMATCH)." | `test_dynamic_revalidation_of_incompatible_saved_comparison` |

---

## 3. Dynamic Revalidation Verification on Remote Staging

On `srv1114257:18080`, persistent comparison record `CMP-C0A448A7F8A0` (saved in Sprint 24 with `['RES-FUND-01', 'RES-REGIME-01', 'RES-MACRO-01']`) was queried via `/api/v1/product/workspace/overview`.

* **Returned `is_compatible`:** `false`
* **Returned `rejection_code`:** `SAMPLING_CADENCE_MISMATCH`
* **Returned `validation_status`:** `REVALIDATION_FAILED`
* **Difference Analysis:** Suppressed

This confirms that the fail-closed compatibility gate dynamically re-evaluates and blocks invalid comparisons loaded from persistent disk storage.

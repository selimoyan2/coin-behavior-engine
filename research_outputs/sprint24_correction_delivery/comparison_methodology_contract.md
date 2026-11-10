# Scientific Comparison Methodology Contract
**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_24_CORRECTION`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Branch:** `main`  
**Implementation Commit:** `54c43cdceedf22214bb0f01cb908b8ba6fabe48e`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY_FROZEN)

---

## 1. Purpose & Guiding Principles

The Scientific Comparison Lab provides multi-candidate analytical comparison across historical research outputs. To prevent invalid inferences, the system enforces a formal **12-Point Scientific Compatibility Gate** that operates in a **fail-closed** manner. If any gate rule fails, numerical difference analysis is entirely suppressed and an explicit rejection reason is returned.

---

## 2. 12-Point Scientific Compatibility Gate Rules

| Gate # | Name | Rule Specification | Failure Code |
| :--- | :--- | :--- | :--- |
| **1** | **Selection Bounds** | Number of selected candidates must satisfy $2 \le N \le 4$. | `INSUFFICIENT_SELECTION` ($N < 2$)<br>`SELECTION_LIMIT_EXCEEDED` ($N > 4$) |
| **2** | **Record Existence** | Every candidate ID must resolve to a valid catalog record. | `RESEARCH_NOT_FOUND` |
| **3** | **Quarantine Boundary** | Any candidate flagged as `QUARANTINED` or `INELIGIBLE` is rejected. | `QUARANTINED_RECORD` |
| **4** | **Model Version Match** | Candidates must match the canonical model version `CBE-0.7.0`. | `MODEL_VERSION_MISMATCH` |
| **5** | **Provenance Conflict** | Candidates with `SOURCE_CONFLICT` or unresolvable lineage are rejected. | `PROVENANCE_CONFLICT` |
| **6** | **Methodology Compatibility** | Candidates must share an analytical methodology domain. Operational durability benchmarks cannot be compared with market behavioral models. | `METHODOLOGY_MISMATCH` |
| **7** | **Sampling Cadence Equality** | Time-series sampling cadences must match exactly (e.g. `1h` vs `1h`). Pairing `8h` with `1h` fails closed. | `SAMPLING_CADENCE_MISMATCH` |
| **8** | **Observation Window Overlap**| Candidates must share $\ge 100$ discrete sampling intervals within their historical periods. | `INSUFFICIENT_OVERLAP` |
| **9** | **Metric Definition Equivalency**| Compared metrics must use identical mathematical estimators (e.g. Parkinson extreme-value volatility estimator). | `METRIC_DEFINITION_MISMATCH` |
| **10**| **Unit Compatibility** | Compared metrics must share identical dimensional units ($x$, $\%$, bars). | `UNIT_MISMATCH` |
| **11**| **Evidence Sufficiency** | If difference analysis requires statistical comparison, at least one candidate must have recorded sample data. | `EVIDENCE_INSUFFICIENT` |
| **12**| **Explicit Missing Value Handling**| When a candidate lacks an observed metric (value is `None`), numerical difference is omitted and marked `N/A`. | Handled per-metric |

---

## 3. Difference Analysis Formulation

For compatible candidate pairs $(A, B)$ sharing an observed scalar metric $M$:

### 3.1 Absolute Difference
$$\Delta_{abs} = |M_B - M_A|$$

### 3.2 Relative Difference Percentage
$$\Delta_{rel} = \begin{cases} \left|\frac{M_B - M_A}{M_A}\right| \times 100\%, & \text{if } M_A \neq 0 \\ 0.0\%, & \text{if } M_A = 0 \end{cases}$$

### 3.3 Metric Units & Caveat Annotations
* **Parkinson Volatility:** Unit `x (çarpan)`. Caveat: *"Parkinson volatilite farkı istatistiksel dağılım genişliğidir; alım-satım kârı değildir."*
* **Sample Size:** Unit `gözlem (bar)`. Caveat: *"Farklı örneklem boyutları p-değeri istatistiksel gücünü etkiler."*

---

## 4. Mandatory Scientific Disclaimer

Every rendered difference analysis payload includes the following immutable legal and scientific disclaimer:

> **Türkçe:** *"Tarihsel sayısal farklar gelecekteki kârlılığın kanıtı olarak yorumlanamaz. Canlı emir iletimi kalıcı olarak yasaktır."*  
> **English:** *"Historical numerical differences cannot be interpreted as proof of future profitability. Live order transmission is permanently prohibited."*

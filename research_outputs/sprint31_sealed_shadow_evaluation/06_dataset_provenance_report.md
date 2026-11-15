# 06 — Dataset Provenance & Cryptographic Attestation Report

**Sprint ID:** `CBE_SPRINT31_SEALED_SHADOW_EVALUATION`  
**Dataset ID:** `DS-BTC-1H-2025-SEALED`  
**Provenance Status:** **`PROVISIONAL_OFFLINE_IMPORT`**  
**Attestation Timestamp:** `2026-11-15T10:41:01.642189+00:00`  

---

## 1. Provenance Lineage

The evaluation dataset was constructed from authentic Binance Spot multi-year 1-hour archive partitions (`data/binance_spot_multiyear/1h/BTCUSDT-1h-2025-*.parquet`).

- **Origin Partition Count:** 12 monthly partitions (January 2025 to December 2025).
- **Concatenation Script:** Verified offline merge without resampling or price modification.
- **Resulting File:** `data/historical/historical_binance_btcusdt_1h_2025.parquet`
- **Accompanying Metadata:** `data/historical/historical_binance_btcusdt_1h_2025_provenance.json`

## 2. Cryptographic Fingerprints

- **File SHA-256:** `897351f6fd0cebd8d487236df15a0b4e83439aab196d3a5e8d284f8ba4d584bd`
- **Byte Count:** 479,252 bytes
- **First Bar Timestamp:** `1735689600000` (2025-01-01 00:00:00 UTC, Close: $93,391.99)
- **Final Bar Timestamp:** `1767222000000` (2025-12-31 23:00:00 UTC, Close: $87,557.06)
- **Price Range:** Low $74,400.00 / High $108,980.00

## 3. Trust Boundary Compliance

In compliance with the Sprint 28.1 and Sprint 30 trust-boundary protocols:
- Self-declared external provenance claims are explicitly disallowed from achieving `CANONICAL_PROVENANCE`.
- The dataset is classified conservatively as `PROVISIONAL_OFFLINE_IMPORT` / `RESTRICTED_EVIDENCE_UNVERIFIED_PROVENANCE`.
- This ensures full transparency that the dataset was imported from local storage for offline research purposes.

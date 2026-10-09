# CBE-0.8.0 Training Reproducibility & Provenance Report
**Sprint:** 09.2 — Offline Model Reconstruction & Immutable Bundle  
**Date:** 2026-10-09T15:14:06.565349+00:00  
**Candidate Version:** CBE-0.8.0  
**Source Commit:** b5ffdfe  

---

## 1. Provenance & Dataset Fingerprints
- **Primary Parquet:** `data/derived/features_with_outcomes_5m.parquet`
- **SHA-256:** `78ae578f4f16aeec073c6c6a8cd3b784275e2854146fe2dc7da855f73028d354`
- **Row Counts:** Discovery=420555, Validation=105120, Holdout=76565
- **Partition Cutoffs:**
  - Discovery: < 2025-01-01T00:00:00Z
  - Validation: 2025-01-01T00:00:00Z to 2025-12-31T23:55:00Z
  - Holdout: 2026-01-01T00:00:00Z to 2026-09-23T20:20:00Z

---

## 2. Model Architecture & Hyperparameters
- **Estimator:** Ridge Regression (`sklearn.linear_model.Ridge`)
- **Regularization:** $\alpha = 100.0$ (L2 penalty)
- **Solver:** Closed-form analytical normal equations $(X^T X + \alpha I)^{-1} X^T y$
- **Preprocessing:** `StandardScaler` fitted strictly on Discovery partition.
- **Ordered Features (3):**
  1. `volatility_realized_24h` (rolling 288-bar 5m return standard deviation)
  2. `volatility_compression_ratio` (short/long realized vol ratio)
  3. `volume_zscore_24h` (24h volume standard deviations)

---

## 3. Training Fit Results (Discovery Partition)
- **1h Horizon:**
  - Intercept: 0.027086
  - Coefficients: [0.014439674463136381, 0.004558716606375888, 0.0031051195768639177]
  - Training $R^2$: 0.4458
  - Training MAE: 0.009479
- **4h Horizon:**
  - Intercept: 0.028541
  - Coefficients: [0.014188008934928796, 0.003303385781924615, 0.0018298001709193298]
  - Training $R^2$: 0.4714
  - Training MAE: 0.008944
- **24h Horizon:**
  - Intercept: 0.030285
  - Coefficients: [0.012650343622764992, 0.002183904896363974, 0.0005899929116662454]
  - Training $R^2$: 0.4650
  - Training MAE: 0.008265

---

## 4. Boundary Protection
To strictly prevent lookahead across partitions, the final $H$ bars of each partition ($H=12$ for 1h, $H=48$ for 4h, $H=288$ for 24h) were dropped from training and evaluation.

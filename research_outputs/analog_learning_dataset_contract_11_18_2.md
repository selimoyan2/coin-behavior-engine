# Historical Analog Learning Dataset Contract
## Specification & Governance for Multi-Year Causal Feature & Label Matrix

**Sprint:** CBE — SPRINT 11.18.2  
**Status:** READY (DESIGN SPECIFICATION ONLY — NO MODEL TRAINING)  
**Execution Mode:** STRICTLY OFFLINE RESEARCH ONLY  
**Asset:** BTC/USDT Spot — Long-Only — No Leverage — No Shorting  
**Author:** CBE Autonomous Architecture & Research Engine  
**Date:** 2026-10-19  

---

## 1. Executive Summary & Scientific Purpose

This contract establishes the formal specification, schema, point-in-time availability rules, and contamination governance for the upcoming **Historical Analog Learning Engine**. 

> [!IMPORTANT]
> **Zero Model Training Mandate:** In strict compliance with Sprint 11.18.2 objectives, no predictive models, neural architectures, k-NN analogs, or policy optimizations are trained in this sprint. This document serves as the binding structural and temporal contract governing dataset synthesis in future sprints.

### Core Objectives
1. **Causal Decoupling:** Complete separation of retrospective decision features (available at $t \le T_0$) from forward-looking labels (realized on $(T_0, T_0 + H]$).
2. **Multi-Horizon Excursions:** Explicit modeling of Maximum Favorable Excursion (MFE), Maximum Adverse Excursion (MAE), time-to-target, and time-to-invalidation.
3. **Multi-Dimensional Conditioning:** Conditioning price trajectories on volatility regime, global market session phases, and macroeconomic surprise vectors.
4. **Honest Contamination Accounting:** Formal designation of previously inspected historical periods as `RESEARCH_CONTAMINATED` to prevent fraudulent out-of-sample claims.

---

## 2. Dataset Architecture & Primary Key

Each observation row represents an atomic decision candidate evaluated at a discrete timestamp $T_0$.

- **Primary Composite Key:** `(decision_timestamp_utc, symbol)`
- **Sampling Frequency:** Regular 5-minute intervals synchronized to UTC candle boundaries (`:00`, `:05`, `:10`, ..., `:55`).
- **Candle Alignment Rule:** The observation at $T_0$ incorporates only candles whose `close_time <= T_0`. For a 5-minute bar opening at 12:25:00 UTC and closing at 12:29:59.999 UTC, it becomes causally eligible at $T_0 = \text{12:30:00 UTC}$.

---

## 3. Feature Space Specification (Point-in-Time Inputs: $t \le T_0$)

Every feature must possess an unequivocal proof of availability at or before $T_0$. Future values, forming candles, or post-dated revisions are strictly prohibited.

```mermaid
flowchart LR
    subgraph Past_and_Present["Causally Visible (t <= T_0)"]
        OHLCV["Closed OHLCV Candles\n(1m, 5m, 15m, 1h, 4h, 1d)"]
        SESS["Global Session Clocks\n(TSE, HKEX, LSE, NYSE)"]
        NEWS["Point-in-Time Events\n(Available with Latency Delta)"]
        REGIME["Historical Regimes\n(Trend, ATR, Volatility)"]
    end
    
    subgraph Decision_Gate["Causal Decision Point T_0"]
        STATE_HASH["State Hash SHA-256\nSealed Information Set"]
    end
    
    subgraph Future_Horizon["Quarantined Labels (t > T_0)"]
        DIRECTION["Future Direction\n(H = 1h, 3h, 6h, 24h)"]
        EXCURSION["MFE / MAE\nPath Extremes"]
        TIME_TO_HIT["Time to Target /\nInvalidation"]
    end
    
    Past_and_Present --> Decision_Gate
    Decision_Gate -.->|NEVER LEAK| Future_Horizon
```

### 3.1. Price Action & Volatility Features

| Field Name | Type | Description | Earliest Valid Availability | Lookback Window |
| :--- | :--- | :--- | :--- | :--- |
| `ret_log_1bar` | `float64` | Continuous log return of the last closed 5m bar | $T_0$ | 1 bar (5m) |
| `ret_log_12bars` | `float64` | Rolling 1-hour continuous log return | $T_0$ | 12 bars (1h) |
| `ret_log_72bars` | `float64` | Rolling 6-hour continuous log return | $T_0$ | 72 bars (6h) |
| `ret_log_288bars`| `float64` | Rolling 24-hour continuous log return | $T_0$ | 288 bars (24h) |
| `atr_5m_pct` | `float64` | Proposed corrected 5m ATR as percentage of close | $T_0$ | 14 bars (70m) |
| `atr_1h_pct` | `float64` | Rolling 1-hour ATR as percentage of close | $T_0$ | 14 bars (14h) |
| `realized_vol_24h`| `float64` | Rolling 24h annualized volatility of 5m log returns | $T_0$ | 288 bars (24h) |
| `volume_ratio_24h`| `float64` | Ratio of last 1h volume to 24h average hourly volume | $T_0$ | 288 bars (24h) |
| `taker_buy_ratio` | `float64` | Ratio of taker buy volume to total base volume | $T_0$ | 12 bars (1h) |

### 3.2. Market Regime & Range Geometry Features

| Field Name | Type | Description | Earliest Valid Availability | Lookback Window |
| :--- | :--- | :--- | :--- | :--- |
| `regime_trend_class` | `string` | Categorical trend state (`BULL_TREND`, `BEAR_TREND`, `CHOP_SIDEWAYS`) | $T_0$ | 288 bars |
| `range_width_pct_24h`| `float64` | (24h High - 24h Low) / 24h Low | $T_0$ | 288 bars |
| `position_in_range_24h`| `float64` | (Close - 24h Low) / (24h High - 24h Low), bounded [0, 1] | $T_0$ | 288 bars |
| `breakout_24h_high` | `bool` | True if last closed bar marked a new 24h rolling high | $T_0$ | 288 bars |
| `breakout_24h_low` | `bool` | True if last closed bar marked a new 24h rolling low | $T_0$ | 288 bars |

### 3.3. Global Market Session Features

| Field Name | Type | Description | Earliest Valid Availability | Reference Schedule |
| :--- | :--- | :--- | :--- | :--- |
| `active_sessions_count`| `int32` | Number of major equity exchanges concurrently open | $T_0$ | TSE, HKEX, LSE, NYSE |
| `session_is_tokyo_open`| `bool` | True if Tokyo Stock Exchange regular session is active | $T_0$ | TSE calendar |
| `session_is_london_open`| `bool` | True if London Stock Exchange regular session is active | $T_0$ | LSE calendar |
| `session_is_nyse_open` | `bool` | True if NYSE regular equity trading session is active | $T_0$ | NYSE calendar |
| `minutes_to_nyse_open` | `float64` | Signed minutes to next NYSE open (negative = pre-open) | $T_0$ | NYSE calendar |
| `session_phase_tag` | `string` | Categorical window (`ASIA_CORE`, `LONDON_OPEN_10M`, etc.) | $T_0$ | GlobalSessionCalendar |

### 3.4. Macroeconomic & News Intelligence Features

| Field Name | Type | Description | Earliest Valid Availability | Provenance Rule |
| :--- | :--- | :--- | :--- | :--- |
| `macro_event_active_1h`| `bool` | True if an official macro release occurred in $[T_0 - 1\text{h}, T_0]$ | $T_0$ | Verified release + max latency |
| `macro_event_id` | `string` | Unique identifier of most recent confirmed event | $T_0$ | Point-in-time catalog |
| `macro_surprise_zscore`| `float64` | Standardized surprise: $(\text{Actual} - \text{Consensus}) / \sigma_{historical}$ | $T_0$ | Published actual vs pre-event survey |
| `event_uncertainty_flag`| `bool` | True if an event occurred within its $[t_{min}, t_{max}]$ window | $T_0$ | Uncertainty interval logic |
| `sentiment_label` | `string` | NLP classification (`BULLISH`, `BEARISH`, `NEUTRAL`) | $T_0$ | Frozen pre-trained model |

---

## 4. Target Label Contract (Future Outcomes: $t > T_0$)

> [!CAUTION]
> **Strict Quarantine Rule:** The labels below represent future market realizations. Under no circumstances may any label column be used as an input to pattern matching, analog lookup, or policy scoring at $T_0$.

### 4.1. Multi-Horizon Future Excursions & Returns

For horizons $H \in \{12, 36, 72, 288\}$ bars corresponding to 1 hour, 3 hours, 6 hours, and 24 hours:

$$\text{MFE}_H = \frac{\max_{1 \le k \le H} \text{High}_{T_0 + k} - \text{Close}_{T_0}}{\text{Close}_{T_0}}$$

$$\text{MAE}_H = \frac{\min_{1 \le k \le H} \text{Low}_{T_0 + k} - \text{Close}_{T_0}}{\text{Close}_{T_0}}$$

$$\text{Net Return}_H = \frac{\text{Close}_{T_0 + H} - \text{Close}_{T_0}}{\text{Close}_{T_0}}$$

| Label Name | Type | Description | Unit |
| :--- | :--- | :--- | :--- |
| `label_mfe_pct_12b` | `float64` | 1-hour Maximum Favorable Excursion | % relative to $P_0$ |
| `label_mae_pct_12b` | `float64` | 1-hour Maximum Adverse Excursion | % relative to $P_0$ (negative) |
| `label_return_pct_12b` | `float64` | 1-hour terminal price change | % relative to $P_0$ |
| `label_mfe_pct_72b` | `float64` | 6-hour Maximum Favorable Excursion | % relative to $P_0$ |
| `label_mae_pct_72b` | `float64` | 6-hour Maximum Adverse Excursion | % relative to $P_0$ (negative) |
| `label_return_pct_72b` | `float64` | 6-hour terminal price change | % relative to $P_0$ |
| `label_mfe_pct_288b` | `float64` | 24-hour Maximum Favorable Excursion | % relative to $P_0$ |
| `label_mae_pct_288b` | `float64` | 24-hour Maximum Adverse Excursion | % relative to $P_0$ (negative) |
| `label_return_pct_288b`| `float64` | 24-hour terminal price change | % relative to $P_0$ |
| `label_future_dir_288b`| `int32` | Direction sign: $+1$ if return $> 0$, $-1$ if return $< 0$, $0$ if flat | Categorical |

### 4.2. Path-Dependent Invalidation & Target Metrics

| Label Name | Type | Description | Evaluation Rule |
| :--- | :--- | :--- | :--- |
| `label_hit_target_2pct_first` | `bool` | True if $+2.0\%$ target was touched before $-1.0\%$ invalidation | Bounded within 288 bars |
| `label_bars_to_target_2pct` | `int32` | Number of 5m bars elapsed until $+2.0\%$ hit | Null if invalidation hit first |
| `label_bars_to_invalidation_1pct`| `int32` | Number of 5m bars elapsed until $-1.0\%$ hit | Null if target hit first |

---

## 5. Historical Data Governance & Contamination Classification

To ensure scientific honesty and prevent over-optimistic overfitting, the multi-year dataset (2022-01 through 2026-09) is partitioned into three strictly segregated partitions:

```
+-----------------------------------+-----------------------------------+-----------------------------------+
|      PARTITION A (CONTAMINATED)   |     PARTITION B (CROSS-VAL)       |    PARTITION C (LOCKED BENCHMARK) |
|      2022-01-01 to 2024-06-30     |     2024-07-01 to 2025-12-31      |     2026-01-01 to 2026-09-30      |
+-----------------------------------+-----------------------------------+-----------------------------------+
| - 30 Months                       | - 18 Months                       | - 9 Months                        |
| - 1,313,280 1m bars               | - 789,120 1m bars                 | - 394,480 1m bars                 |
| - Status: RESEARCH_CONTAMINATED   | - Status: CROSS_VALIDATION_TUNING | - Status: PROSPECTIVE_BENCHMARK   |
+-----------------------------------+-----------------------------------+-----------------------------------+
```

### 5.1. Partition A: `RESEARCH_CONTAMINATED` (2022-01-01 → 2024-06-30)
- **Status:** Extensively researched across Sprints 11.16 through 11.18.2.
- **Rules:**
  1. This partition has been repeatedly exposed to algorithmic design, indicator parameter audits, and backtest evaluations.
  2. Any model or analog engine trained on this partition **MUST NOT** claim performance as "out-of-sample".
  3. It serves strictly as the *Historical Analog Training Library* (the past memory from which analogs are retrieved).

### 5.2. Partition B: `CROSS_VALIDATION_TUNING` (2024-07-01 → 2025-12-31)
- **Status:** Validated multi-year data with newly acquired Binance archives.
- **Rules:**
  1. Designated for hyperparameter selection, analog similarity threshold tuning ($k$, distance metric, feature weights).
  2. K-fold or rolling walk-forward evaluation only.

### 5.3. Partition C: `LOCKED_PROSPECTIVE_BENCHMARK` (2026-01-01 → 2026-09-30)
- **Status:** Virgin historical test partition.
- **Rules:**
  1. Quarantined from feature selection, parameter tuning, and metric optimization.
  2. Replay execution allowed only for final evaluation of frozen analog policies.

---

## 6. Normalization & Anti-Leakage Protocol

1. **Expanding Window Scaling:** All standardization routines (e.g. z-score of volume, volatility percentiles) must use strictly historical expanding windows ($\min(t) \le \tau \le T_0$). Global full-sample `StandardScaler` or `MinMaxScaler` across the entire 2022–2026 dataset is strictly forbidden.
2. **Missing Bar Policy:** As verified in Phase 1, the Binance spot matching engine outage on 2023-03-24 (80 missing bars) must remain absent; no synthetic imputation or interpolation is permitted.
3. **Point-in-Time Event Sealing:** Every training record must record the SHA-256 state hash generated by `HistoricalReplayEngine`, verifying that event content matches the primary historical audit.

---

## 7. Contract Verification Sign-Off

- **Contract Status:** `LEARNING_DATASET_CONTRACT=READY`
- **Model Training:** `MODEL_TRAINING=NOT_STARTED`
- **Historical Data Status:** `HISTORICAL_DATA_STATUS=RESEARCH_CONTAMINATED`
- **Prospective Observation:** `PROSPECTIVE_OBSERVATION=NOT_STARTED`
- **Live Trading:** `LIVE_TRADING=PROHIBITED`
- **Operator Authorization:** `OPERATOR_AUTHORIZATION=NOT_GRANTED`

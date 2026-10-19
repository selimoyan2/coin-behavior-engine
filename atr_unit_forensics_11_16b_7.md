# CBE — SPRINT 11.16B.7: ATR UNIT FORENSICS & HISTORICAL CODE TIMELINE
**Document ID:** `research_outputs/atr_unit_forensics_11_16b_7.md`  
**Base Commit:** `6f0122e95d0f69b80178dca6d4badf392fcc45d1`  
**Target Canonical Dataset SHA-256:** `2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487`  
**Audit Date:** 2026-10-19  
**Mode:** Offline Scientific Forensics Only — Strictly No Policy Parameter Mutation  

---

## 1. EXECUTIVE SUMMARY & FORENSIC VERDICT

During the Trade-Active Parity Replay of Sprint 11.16B.6, `POLICY_D_SELECTIVE_TREND_ONLY` and `POLICY_E_SELECTIVE_ANALOGUE_ASSISTED` exhibited **zero executed trades (0 entries, 0 exits, 0 fills)** across the entire 105,120-bar (365-day) canonical dataset.

This forensic investigation proves conclusively that:
1. **The zero-trade behavior is NOT a display of prudent selective risk filtering.**
2. **The zero-trade behavior is caused by a catastrophic unit/timeframe conflation error** originating in Sprint 11.15 when converting Sprint 11.14 research code into the prospective shadow protocol.
3. The frozen volatility filter `0.015 <= atr_pct <= 0.065` was evaluated against a **14-bar 5-minute candle ATR percentage** ($\text{ATR}_{14} / \text{close}$), where median BTC volatility is **0.001337 (0.134% or 13.4 bps)**.
4. An ATR percentage of $0.015$ ($1.5\%$ per 5-minute bar) corresponds to an annualized volatility exceeding **$340\%$**. Across 104,256 valid historical bars, 5-minute candle ATR met this threshold on only **4 isolated bars (0.0038%)**, all occurring during an extreme price collapse where multi-timeframe trend filters were strongly negative.
5. In Sprint 11.15, this defect was masked because test fixtures and demo simulations **hardcoded `"atr_pct": 0.025`**, never calculating ATR from real market candles.
6. **Scientific Policy Identity Enforcement:** In strict accordance with prospective protocol rules, **the frozen parameters of Policy D and Policy E are NOT altered or rewritten.** The historical zero-trade record of the frozen policies stands as observed. Any repaired parameterization is classified as a new candidate policy (`POLICY_D_V2_CORRECTED_ATR`) requiring separate prospective freezing.

---

## 2. HISTORICAL SOURCE CODE TIMELINE & COMMIT PROVENANCE

### Commit 1: Sprint 11.14 (`7ee1104` / `7ee1104e13d11b2ff361491cf1c1f727c97ef050`)
*Component:* `selective_entry_engine.py` (lines 502–540) & `market_regime.py` (lines 50–75).

- In `selective_entry_engine.py`, Strategy H (the research precursor to Policy D) defined volatility as:
  ```python
  # 24-hour rolling log-return standard deviation annualized to percentage:
  log_rets = pd.Series(np.log(c[1:] / c[:-1]))
  vol_24h = log_rets.rolling(288, min_periods=48).std().values * math.sqrt(105120) * 100.0
  gate_vol = (15.0 <= vol_24h <= 80.0)
  ```
  Here, `15.0` and `80.0` represented **15.0% to 80.0% annualized volatility**, a standard and reasonable filter for BTC spot market trading. Strategy H produced **28 executed trades** over the evaluation split.

- Simultaneously, in `market_regime.py`:
  ```python
  atr_pct = (atr / curr_close) if curr_close > 0 else 0.0
  if atr_pct > 0.015:  # > 1.5% per bar interval -> High volatility expansion
  if atr_pct < 0.003:  # < 0.3% per bar interval -> Low volatility compression
  ```
  Here, `0.015` was defined as the regime boundary for **extreme volatility expansion** on individual 5-minute bars.

### Commit 2: Sprint 11.15 (`0977362` / `09773621f7026ac2630fb7674cd11aadaf934a70`)
*Component:* `src/coin_behavior_engine/research_lab/shadow_decision_protocol.py` & `research_outputs/policy_freeze_manifest.json`.

- When codifying Policy D and Policy E for prospective freezing, the author merged the threshold numbers (`0.015` and `0.065`) into a feature named `atr_pct`:
  ```python
  # shadow_decision_protocol.py (lines 670-675):
  atr_pct = features.get("atr_pct", 0.02)
  vol_ok = bool(0.015 <= atr_pct <= 0.065)
  ```
  ```json
  // policy_freeze_manifest.json (lines 80-81, 100-101):
  "min_volatility_atr_pct": 0.015,
  "max_volatility_atr_pct": 0.065
  ```
- **Masking Mechanism 1 (Hardcoded Simulation):** In `run_shadow_demo_simulation` (line 827):
  ```python
  "features": {"sma_24h": p * 0.99, "sma_72h": p * 0.98, "atr_pct": 0.025, "analogue_prob": 0.65}
  ```
  The simulation passed because `0.025` was injected directly into mock features, bypassing any candle calculation.
- **Masking Mechanism 2 (Synthetic Test Fixtures):** In `tests/test_sprint11_15_shadow_protocol.py` (lines 351, 365), tests passed because tests explicitly asserted with `{"atr_pct": 0.02}`.

### Commit 3: Sprint 11.16B.3 (`a04abc9` / `a04abc9b99c891a6a6099bc9e99394405ba967fb`)
*Component:* `src/coin_behavior_engine/research_lab/shadow_market_data_bridge.py` (lines 525–545).

- The Shadow Market Data Bridge implemented genuine feature calculation from real 5-minute candles:
  ```python
  atr_14 = sum(tr_list) / 14.0
  vol_atr_pct = (atr_14 / current_close) if current_close > 0 else 0.0
  vol_ok = (0.015 <= vol_atr_pct <= 0.065)
  ```
- Because real 5-minute candle ATR was now computed, `vol_atr_pct` evaluated to genuine market values ($\sim 0.0013$), immediately locking the gate closed for 100% of structurally valid trend bars.

### Commit 4: Sprint 11.16B.6 (`dbc8253` / `dbc825315e58c0b71263a3f5bb9b2d383d4d46ea`)
*Component:* `tests/test_sprint11_16b_6_active_trade_replay.py`.

- The multi-regime active trade replay independently confirmed that Policy D and Policy E produced **0 trades**, exposing that the frozen policies were structurally incapable of execution on authentic BTC spot market data.

---

## 3. MATHEMATICAL UNIT & TIMEFRAME FORENSICS

### Timeframe and Normalization Comparison
| Timeframe / Metric | Typical BTC Range | Equivalent Annualized Volatility | Evaluated Threshold Range | Compatibility Status |
| :--- | :--- | :--- | :--- | :--- |
| **5-Minute Candle ATR %** | 0.05% to 0.35% (0.0005 to 0.0035) | ~11% to ~80% | **0.015 to 0.065 (1.5% to 6.5%)** | **CATASTROPHIC MISMATCH** (Requires >340% vol) |
| **1-Hour Candle ATR %** | 0.20% to 1.20% (0.0020 to 0.0120) | ~19% to ~112% | 0.015 to 0.065 (1.5% to 6.5%) | Severe Mismatch (Requires >140% vol) |
| **24-Hour (Daily) ATR %** | 1.50% to 6.50% (0.0150 to 0.0650) | ~29% to ~124% | **0.015 to 0.065 (1.5% to 6.5%)** | **MATHEMATICAL INTENT** (Daily Range Normalization) |
| **24-Hour Rolling Vol (Ann %)** | 15.0% to 80.0% | 15% to 80% | 15.0 to 80.0 | Original Sprint 11.14 Strategy H Definition |

### Empirical BTC/USDT 5-Minute ATR Distribution ($N=104,256$ valid bars)
- **Minimum:** 0.000148 (0.015% or 1.48 bps)
- **10th Percentile:** 0.000624 (0.062% or 6.24 bps)
- **50th Percentile (Median):** **0.001337 (0.134% or 13.37 bps)**
- **90th Percentile:** 0.002681 (0.268% or 26.81 bps)
- **99th Percentile:** 0.005162 (0.516% or 51.62 bps)
- **Maximum:** 0.024971 (2.497% or 249.71 bps) — Bar 31843 (Flash Crash)

### The 4 Anomalous Bars Exceeding 0.015
Only 4 bars out of 104,256 reached `atr_pct >= 0.015`:
1. Bar 31841 (2026-02-06 08:05 UTC): `atr_pct = 0.015312` | Trend Aligned: False (Downtrend crash)
2. Bar 31842 (2026-02-06 08:10 UTC): `atr_pct = 0.019441` | Trend Aligned: False (Downtrend crash)
3. Bar 31843 (2026-02-06 08:15 UTC): `atr_pct = 0.024971` | Trend Aligned: False (Downtrend crash)
4. Bar 31844 (2026-02-06 08:20 UTC): `atr_pct = 0.017892` | Trend Aligned: False (Downtrend crash)

Because these four bars occurred during a severe downward liquidation spiral, `close > sma_288` was false for all four. Consequently, **the intersection of trend alignment and the frozen ATR filter is exactly 0 bars across the entire canonical dataset.**

---

## 4. SCIENTIFIC ATTRIBUTION VERDICT

The zero-trade behavior of Policy D and Policy E is **100% attributable to the 5-minute candle ATR unit mismatch.**
- Structural trend alignment (`close > sma_288 AND close > sma_864`) occurred on **38,569 bars (36.99%)**.
- Anti-chase extension (`close <= sma_288 * 1.0225`) was satisfied on **100,330 bars (96.23%)**.
- Joint structural eligibility occurred on **34,813 bars (33.39%)**.
- The frozen ATR filter rejected **34,813 out of 34,813 structurally eligible bars (100.0% rejection rate)**.

Treating this zero-trade outcome as "superior risk management" or "intentional capital preservation" is scientifically fraudulent. The policy was incapacitated by an unvetted unit error.

---

## 5. POLICY IDENTITY PRESERVATION & CANDIDATE GOVERNANCE

Under prospective research governance, when a defect is uncovered in a frozen policy:
1. **The frozen definition must NOT be retroactively patched in place.** Rewriting the threshold from `0.015` to `0.0015` in `policy_freeze_manifest.json` would constitute unacknowledged post-hoc parameter tuning and destroy the provenance of Sprint 11.15.
2. **Policy D and Policy E remain registered with their frozen parameters.** Their scientific evaluation record accurately reflects `0 trades, return 0.00%, status: BLOCKED_BY_UNIT_DEFECT`.
3. **Proposed Remedy:** A new candidate policy, `POLICY_D_V2_CORRECTED_ATR`, is formally proposed with:
   - `atr_timeframe: "14_bars_5m"`
   - `min_volatility_atr_pct: 0.0005` (0.05% per bar)
   - `max_volatility_atr_pct: 0.0035` (0.35% per bar)
   This proposed candidate yields **31,092 eligible bars (29.82%)** and awaits operator authorization and a formal prospective freeze manifest before any prospective evaluation.

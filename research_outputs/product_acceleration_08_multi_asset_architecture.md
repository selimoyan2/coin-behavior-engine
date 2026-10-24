# CBE Product Acceleration Sprint 08 — Multi-Asset Historical Research Architecture

## 1. Architectural Mission
Coin Behavior Engine has traditionally operated on single-symbol historical market archives (`BTCUSDT`). Sprint 08 introduces the **Multi-Asset Historical Research Foundation**, enabling multi-symbol catalog discovery, standardized cross-asset schema alignment, synchronized timeline comparison (Pearson rolling correlation, relative trajectory, volatility ratio, tracking spread), and strict fail-closed governance for unimported digital assets.

---

## 2. Supported Symbols and Schema Standardization
The multi-asset architecture standardizes historical candle representation across all supported cryptocurrency pairs:
- **Primary Base Asset:** `BTCUSDT` (Bitcoin / Tether Spot)
- **Extensible Base Assets:** `ETHUSDT` (Ethereum / Tether Spot), `SOLUSDT` (Solana / Tether Spot)
- **Standardized Field Contract:**
  - `open_time`: Unix millisecond integer timestamp
  - `datetime_utc`: ISO-8601 UTC string (`YYYY-MM-DDTHH:MM:SSZ`)
  - `open`, `high`, `low`, `close`: IEEE 754 float prices
  - `volume`: Floating-point base-asset volume
  - `regime`: Quantitative market regime classification (`BULL_TREND`, `BEAR_TREND`, `SIDEWAYS`, `VOLATILE_BREAKOUT`, `CONSOLIDATION`)

---

## 3. Strict Fail-Closed Policy & Zero-Synthetic Data Guarantee
In adherence to the core CBE scientific principles:
> **GOVERNANCE INVARIANT: ZERO SYNTHETIC MARKET DATA FABRICATION**
> When a researcher requests analysis or comparison involving a symbol whose genuine historical archive has not been ingested (such as `ETHUSDT` or `SOLUSDT`), the system **STRICTLY FAILS CLOSED** (`UNAVAILABLE_NO_DATA` / `BLOCKED_NO_DATA`).
> Under no circumstances does the engine fabricate synthetic geometric Brownian motion, mock bars, or interpolated placeholder candles.

---

## 4. Cross-Asset Synchronized Comparison Methodology
When multiple genuine assets are available:
1. **Timestamp Key Alignment:** Candlestick sequences are joined on exact UTC timestamp matches ($t_k$). Missing bars in either series are flagged rather than silently filled.
2. **Normalized Return Trajectories:** Starting at anchor $t_0$, both series are rebased to index $100.0$:
   $$I_{A, t} = \frac{P_{A, t}}{P_{A, t_0}} \times 100.0$$
   $$I_{B, t} = \frac{P_{B, t}}{P_{B, t_0}} \times 100.0$$
3. **Rolling Pearson Correlation:** For return series $R_{A}$ and $R_{B}$ across window $W$:
   $$r_t = \frac{\sum_{i=0}^{W-1} (R_{A, t-i} - \bar{R}_A)(R_{B, t-i} - \bar{R}_B)}{\sqrt{\sum_{i=0}^{W-1} (R_{A, t-i} - \bar{R}_A)^2 \sum_{i=0}^{W-1} (R_{B, t-i} - \bar{R}_B)^2}}$$
4. **Volatility Ratio & Relative Beta:**
   $$\text{VolRatio} = \frac{\sigma(R_B)}{\sigma(R_A)}$$
   $$\beta_{B \to A} = \frac{\text{Cov}(R_A, R_B)}{\text{Var}(R_A)}$$

---

## 5. Storage Hierarchy & Partitioning
Multi-asset files are stored deterministically under:
```
data/binance_spot_multiyear/
  ├── {interval}/
  │     ├── {SYMBOL}-{interval}-{YYYY}-{MM}.parquet
  │     └── ...
```
Dynamic discovery automatically scans partition counts, size in MB, earliest and latest covered months, and exposes them through `GET /api/v1/product/available-symbols`.

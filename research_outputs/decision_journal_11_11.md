# CBE Sprint 11.11 Human-Readable Decision Journal & Case Studies

**Date:** 2026-10-18  
**Scope:** Chronological Decision Journal, Forensic Evidence Traces, and Failure Case Studies  
**System:** Coin Behavior Engine (CBE) — Research Lab  

---

## 1. Decision Timeline & Contemporaneous Evidence Log

The following chronological log details state transitions, evidence thresholds, costs, and subsequent realized outcomes:

### Decision Entry 1: Bear Waterfall Protection (Capital Preservation)
- **Timestamp & UTC:** `2026-08-23 11:30:00 UTC` (Bar 88,992)
- **BTC Price:** \$76,420.00 USD
- **Portfolio State:** Available USDT: \$10,000.00 | BTC Quantity: 0.000000
- **Market Regime:** `TRENDING_BEAR` (4h trend: $-1.85\%$, 24h SMA: \$77,150.00)
- **Decision & Action:** `WAIT_USDT` (FSM State: `WAIT_USDT`)
- **Contemporaneous Rationale:** Price broke below 24h and 72h SMAs with accelerating negative momentum. Bearish confidence reached 85%. Capital preservation mandated.
- **Estimated Risk & Friction:** 0 bps friction incurred; 100% portfolio shielded from downside.
- **Subsequent Observed Outcome (Kept Separate):** Over the next 48 hours, BTC declined from \$76,420 to \$71,180 ($-6.86\%$ crash).
- **Forensic Assessment:** **Perfect Abstention Alpha.** Zero drawdown experienced by remaining 100% in safe USDT cash.

---

### Decision Entry 2: Absorption Trough & Confirmation Hysteresis
- **Timestamp & UTC:** `2026-08-25 18:45:00 UTC` (Bar 89,655)
- **BTC Price:** \$71,850.00 USD
- **Portfolio State:** Available USDT: \$10,000.00 | BTC Quantity: 0.000000
- **Market Regime:** `POSSIBLE_REVERSAL` (Absorption wick formed at \$71,180 support)
- **Decision & Action:** `NO_TRADE` (FSM State: `WATCH_REVERSAL`)
- **Contemporaneous Rationale:** While a high-volume capitulation hammer printed, price remains below the 24h SMA (\$73,400). In accordance with the Patient Policy, counter-trend knife catching is strictly prohibited until structural confirmation is observed.
- **Hysteresis & Cooldown Status:** Cooldown: Inactive (0 bars). Confirmation Counter: 1 of 3 required bars.
- **Subsequent Observed Outcome:** Rather than immediately rocketing upward, BTC chopped between \$71,400 and \$72,200 for 14 hours. In Sprint 11.10, Strategy H bought here and was chopped up by whipsaws. The Patient Policy waited patiently for confirmation.

---

### Decision Entry 3: Confirmed Trend Expansion Entry
- **Timestamp & UTC:** `2026-08-26 14:20:00 UTC` (Bar 89,890)
- **BTC Price:** \$73,650.00 USD
- **Portfolio State:** Available USDT: \$10,000.00 | BTC Quantity: 0.000000
- **Market Regime:** `TRENDING_BULL` (Price > 24h SMA \$73,100, 4h trend: $+1.12\%$)
- **Decision & Action:** `BUY_CANDIDATE` (FSM State: `BUY_READY` $	o$ `HOLD_BTC`)
- **Contemporaneous Rationale:** Price cleanly crossed above the 24h SMA with 3 consecutive confirmation bars. Macro regime transitioned to `TRENDING_BULL`.
- **Execution & Position Parameters:**
  - Allocated Capital: \$9,500.00 (95.0% spot allocation)
  - Fill Price (Next-Bar Open + 5 bps slippage): \$73,686.82
  - BTC Purchased: 0.128815 BTC (Entry fee: \$7.13)
  - Structural Stop Loss: \$71,100.00 (-3.5% structural swing support)
  - Profit Target: \$77,700.00 (+5.5%)
- **Subsequent Observed Outcome:** BTC steadily expanded over 40 hours to \$77,850, hitting profit target and locking in **+\$518.20 net profit (+5.45% return)**.

---

### Decision Entry 4: Cooldown Churn Prevention (Avoided Whipsaw)
- **Timestamp & UTC:** `2026-09-04 08:15:00 UTC` (Bar 92,415)
- **BTC Price:** \$74,200.00 USD
- **Portfolio State:** Available USDT: \$10,480.00 | BTC Quantity: 0.000000
- **Context:** An earlier position was stopped out at \$74,100 during a sharp 15-minute liquidation wick.
- **Decision & Action:** `NO_TRADE` (FSM Transition Blocked by `COOLDOWN_ACTIVE`)
- **Contemporaneous Rationale:** Only 12 bars (1 hour) had elapsed since exit. Cooldown counter = 24 bars remaining. Price delta from exit is only $+0.13\%$. Re-entry is strictly suppressed to avoid friction churn.
- **Subsequent Observed Outcome:** BTC immediately plunged another \$1,400 to \$72,800.
- **Forensic Assessment:** In Strategy G (Sprint 11.10), this trade was immediately entered and stopped out for an additional $-\$320$ loss plus $\$30$ in fees. The Patient Policy's 36-bar cooldown **saved \$350 in capital**.

---

## 2. In-Depth Failure Forensic Case Studies

### Case Study A: The Anatomy of a Fee-Driven Loss (Strategy G Trade #42)
- **Entry:** \$64,200.00 | **Exit:** \$64,280.00 (Gross Gain: +\$12.40)
- **Total Friction:** Entry fee \$7.12 + Exit fee \$7.13 + Slippage \$9.50 = \$23.75
- **Net Outcome:** **-\$11.35 Net Loss**
- **Diagnosis:** `FEE_DRIVEN_LOSS`. A micro-trailing stop was triggered after price rose by only 40 bps. While the trader was directionally correct, the institutional transaction friction of 25 bps roundtrip devoured 190% of the gross profit!
- **Mitigation Implemented:** Structural trailing stops only tighten after discrete milestones ($\ge +1.5\%$), never on micro-fluctuations.

### Case Study B: The Premature Stop-Out Trap (Strategy G Trade #67)
- **Entry:** \$66,100.00 | **Initial Stop:** \$64,117.00 (-3.0%)
- **Dynamic Update:** When price reached \$67,100 (+1.51%), stop was moved to \$66,232 (breakeven + 20 bps).
- **Execution:** A normal 5-minute liquidity wick dipped to \$66,200, stopping out the position for a meager +\$15.00 net gain.
- **Subsequent Price Move:** Over the next 24 hours, Bitcoin rallied without interruption to \$70,500 (+6.6%).
- **Diagnosis:** `PREMATURE_STOP_OUT`. Tightening trailing stops too close to market price prevents positions from enduring ordinary random walk volatility.
- **Mitigation Implemented:** Patient policy uses a minimum 1.50% buffer on breakeven stops and requires 48-hour holding horizons.

### Case Study C: The Counter-Trend Reversal Trap (Strategy H Trade #18)
- **Entry:** \$68,500.00 during an active bear waterfall.
- **Rationale in Strategy H:** Absorption wick probability = 0.65.
- **Outcome:** Bitcoin continued dropping to \$65,200. Stopped out for **-\$285.00 net loss (-2.85%)**.
- **Diagnosis:** `FALSE_REVERSAL`. In a cascade liquidation, local absorption wicks are repeatedly overrun by forced margin liquidations.
- **Mitigation Implemented:** Reversal entries must wait for 24h SMA recovery and positive 4h momentum.

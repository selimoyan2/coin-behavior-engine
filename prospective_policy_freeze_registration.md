# CBE Sprint 11.16B.2 — Prospective Policy Freeze Registration & Baseline Verification

**Document Version:** 2.0.0-prospective  
**Sprint:** 11.16B.2  
**Target Environment:** Prospective Shadow Observer Environment  
**Base Commit:** `b5bc3f69c2027fc23984eb5d661400437cdd9f97`  
**Execution Standard:** Strictly Empirical Pre-Registration — Zero Retrospective Backdating  
**Auditor:** Quantitative Systems Architect & Research Protocol Auditor  

---

## 1. Executive Summary & Required Status Declarations

Sprint 11.16B.2 establishes the definitive **Prospective Policy Freeze Registration** for the five candidate research policies evaluated by the Coin Behavior Engine.

In strict adherence to empirical research standards, this document formally separates:
1. **The historical policy freeze claim** (`2026-10-18T21:00:00Z` in `policy_freeze_manifest.json`),
2. **The actual Git commit chronology** (`2026-10-18T18:31:03Z` in commit `0977362`),
3. **The new prospective freeze registration timestamp** (`2026-10-19T00:50:00Z`), and
4. **The formal classification status**:
   ```
   FREEZE_CHRONOLOGY=UNVERIFIED
   ```

A new prospective freeze registration and future operator-signed Git tag provide a forward-looking cryptographic anchor for prospective evaluation. **Under no circumstances may a new signature or registration be represented as retrospective proof of the historical freeze timestamp.**

---

## 2. Five Candidate Research Policies — Frozen Parameter Hashes & Specifications

All five policies are implemented in `src/coin_behavior_engine/research_lab/shadow_decision_protocol.py` and locked against runtime modification.

### 2.1 Verification Matrix
| Policy ID | Policy Name | Role | Active Trading | Parameter Digest (SHA-256) | Required History |
|---|---|---|:---:|---|:---:|
| **`POLICY_A_USDT_CASH`** | USDT Cash Capital Preservation | Risk-Free Benchmark | No | `08f5376a30e5fa54902b13df8d012f218d8e8279986dceec4368b362e4ad0fed` | 0 bars |
| **`POLICY_B_BTC_BUY_AND_HOLD`** | BTC Spot Buy-and-Hold | Beta Benchmark | No | `40a72dedfd4daf722ab8f49dab9f1741827530d51c88ff8f8b2e9df1e47bc461` | 1 bar |
| **`POLICY_C_TREND48_FOLLOWING`** | Classic 48h Trend Following | Momentum Baseline | Yes | `0bd242a12943b9e58f6cf0047c2def95fbd74334eeb74a91bda4ccf4f5aa37e7` | 576 bars (48h) |
| **`POLICY_D_SELECTIVE_TREND_ONLY`** | Selective Regime-Aware Trend | Multi-Timeframe Structural | Yes | `ef5e193beebcade0eef74b3804c72f1bd6212d2a73d9520284c830d28f9e1065` | 864 bars (72h) |
| **`POLICY_E_SELECTIVE_ANALOGUE_ASSISTED`** | Selective Analogue-Assisted | Hybrid Structural + Behavioral | Yes | `f64eab504192d969af4ac2aaeb6d875f33ccc5dffae5582a16ff120c2128d994` | 864 bars + Analogue DB |

### 2.2 Detailed Frozen Parameters
- **Policy A (`USDT_CASH`):**
  - `allocation_pct`: `0.0%`
  - Action emitted: strictly `WAIT_USDT` on every observation.
- **Policy B (`BTC_BUY_AND_HOLD`):**
  - `initial_allocation_cap_pct`: `98.0%`
  - Action emitted: `BUY_CANDIDATE` on bar 0; strictly `HOLD_BTC` thereafter.
- **Policy C (`TREND48_FOLLOWING`):**
  - `trend_window_hours`: `48` (576 contiguous 5m bars).
  - Gating: Long if Close > 48h SMA; Exit if Close < 48h SMA. Allocation cap: `98.0%`.
- **Policy D (`SELECTIVE_TREND_ONLY`):**
  - `fast_sma_hours`: `24` (288 bars), `slow_sma_hours`: `72` (864 bars).
  - `anti_chase_max_extension_pct`: `2.25%`.
  - `min_volatility_atr_pct`: `0.015`, `max_volatility_atr_pct`: `0.065`.
  - `fixed_stop_loss_pct`: `2.50%`, `fixed_take_profit_pct`: `5.00%`.
  - `post_exit_cooldown_bars`: `72` (6 hours). Allocation cap: `98.0%`.
- **Policy E (`SELECTIVE_ANALOGUE_ASSISTED`):**
  - All Policy D structural gating parameters (288-bar and 864-bar SMA, anti-chase, volatility band, stops).
  - `analogue_min_similarity`: `0.75`.
  - `analogue_min_positive_prob`: `0.60` (hurdle rate). Allocation cap: `98.0%`.

---

## 3. Canonical Execution Policy V2 Standard

All policies execute under the immutable **Canonical Execution Policy V2** standards:
- **Nominal Roundtrip Friction:** **30.0 bps** (0.30% of trade value).
  - Taker Entry Fee: 10.0 bps.
  - Taker Exit Fee: 10.0 bps.
  - Entry Slippage: 5.0 bps.
  - Exit Slippage: 5.0 bps.
- **Fill Timing:** Strictly `NEXT_BAR_OPEN` (zero lookahead).
- **Intrabar Stop Execution:** Pessimistic priority: if both `stop_loss` and `take_profit` levels are penetrated within the same bar, `stop_loss` is filled.
- **Cash Floor:** 0.0 USDT; **Inventory Floor:** 0.0 BTC.

---

## 4. Scientific Invariants: Dataset Boundary & Winner Prohibition

1. **Canonical Benchmark Dataset:**
   - File: `market_state_dataset.parquet`
   - SHA-256 Fingerprint: `2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487`
   - Total Candles: 105,120 (365 days of 5-minute bars).
2. **Research Contamination Boundary:**
   - Partition bars 86,724 through 105,120 have been repeatedly inspected across Sprints 11.10 through 11.14.
   - **Winner Selection Status:** **`FORBIDDEN_NO_WINNER_SELECTED`**.
   - Selecting a preferred policy using repeatedly inspected historical data constitutes survivorship/selection bias. All five policies must enter prospective shadow evaluation as equal candidates.

---

## 5. Chronological Reconciliation & Operator Anchor Procedure

### 5.1 Chronological Discrepancy Breakdown
```
Historical Claim String:   2026-10-18T21:00:00Z  (asserted in policy_freeze_manifest.json)
Actual Git Commit Date:    2026-10-18T18:31:03Z  (commit 0977362, recorded as 21:31:03 +0300)
Timezone Conflation:       +2 hours 28 minutes forward mismatch due to Turkey Time (TRT / UTC+3)
Prospective Registration:  2026-10-19T00:50:00Z  (prospective_freeze_manifest_v2.json)
```

Because Git commit author timestamps are locally controllable and no third-party RFC-3161 timestamp or external notarization exists, the historical claim cannot be retroactively validated.
```
FREEZE_CHRONOLOGY=UNVERIFIED
```

### 5.2 Operator Action: Creating an External Cryptographic Anchor
To establish an indisputable chronological baseline *forward in time* before prospective observation begins, the human operator must execute the following commands:

```bash
# 1. Verify working tree is clean and on main
git status

# 2. Create an operator-signed Git tag anchoring the prospective baseline
git tag -s v11.16b2-prospective-freeze-baseline -m "Operator signed prospective freeze baseline: Sprint 11.16B.2 at commit $(git rev-parse HEAD)"

# 3. Verify the signature and commit hash
git tag -v v11.16b2-prospective-freeze-baseline

# 4. Push the tag to remote repository
git push origin v11.16b2-prospective-freeze-baseline
```

> [!IMPORTANT]
> This command sequence must be executed manually by the authorized human operator using their private GPG signing key. The assistant is strictly prohibited from creating or pushing signed tags automatically.

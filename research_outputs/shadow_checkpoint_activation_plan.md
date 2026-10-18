# CBE Sprint 11.16B.2 — Shadow Storage & Cryptographic Checkpoint Activation Plan

**Document Version:** 1.0.0-sprint11.16b.2  
**Target Architecture:** Append-Only Cryptographic Decision Hash Chain & Daily Anchoring  
**Security Standard:** Strict Air-Gap Compliance (`network_mode: "none"`) — Zero External Sockets  
**Auditor:** Quantitative Systems Security & Cryptographic Protocol Auditor  

---

## 1. Executive Summary & Verification Matrix

This activation plan specifies the storage architecture, cryptographic hash chaining, and external anchoring workflow for the prospective shadow observation protocol.

All 10 storage and cryptographic integrity dimensions defined in Sprint 11.16B.2 have been audited and verified:

| # | Integrity Dimension | Implementation Mechanism | Verification Result |
|:---:|---|---|:---:|
| **1** | **Canonical JSON Serialization** | Deterministic UTF-8 byte serialization: `json.dumps(payload, sort_keys=True, separators=(",", ":"))` with float rounding rules. | **VERIFIED** |
| **2** | **Decision Sequence Continuity** | Strict monotonic integer sequence enforcement: $S_i = S_{i-1} + 1$. Sequence gaps or inversions cause immediate validation abort. | **VERIFIED** |
| **3** | **Parent-Hash Chaining** | SHA-256 recursive linkage: $H_i = \text{SHA256}(\text{CanonicalPayload}(S_i, H_{i-1}, \dots))$. Block 0 binds to `GENESIS_PARENT_HASH`. | **VERIFIED** |
| **4** | **Duplicate Prevention** | Primary key enforcement on `decision_id` and hash set deduplication prevents replaying or duplicate entries. | **VERIFIED** |
| **5** | **Checkpoint Verification** | `ChainCheckpoint` dataclass captures `(block_index, block_hash, records_count, state_root)`. Verified via `verify_against_checkpoint()`. | **VERIFIED** |
| **6** | **Restart Recovery** | Engine rehydrates existing records from persistent append-only storage, verifies full cryptographic lineage, and resumes seamless evaluation. | **VERIFIED** |
| **7** | **Truncation Detection** | If trailing blocks are removed, comparing the chain head against a published external checkpoint detects length deficits and mismatched hashes. | **VERIFIED** |
| **8** | **Independent Policy Identity** | Each candidate policy maintains its own dedicated `DecisionHashChain` and independent portfolio ledger with separate cryptographic roots. | **VERIFIED** |
| **9** | **Outcome-to-Decision Linking** | Forward market outcomes are sealed into distinct `ShadowOutcomeRecord` entities referencing `parent_decision_hash`, eliminating backward data leakage. | **VERIFIED** |
| **10**| **Timestamp Integrity** | Monotonic ISO 8601 UTC timestamps with fail-closed lookahead checks ($T_{\text{avail}} \ge T_{\text{obs}}$) and clock skew verification. | **VERIFIED** |

---

## 2. Storage Topology & Filesystem Layout

All prospective decision and outcome records are stored in a dedicated, isolated named Docker volume (`cbe_prospective_shadow_data_v1`):

```
/app/data/shadow/
├── decisions/
│   ├── policy_a_usdt_cash_decisions.jsonl
│   ├── policy_b_btc_buy_and_hold_decisions.jsonl
│   ├── policy_c_trend48_following_decisions.jsonl
│   ├── policy_d_selective_trend_only_decisions.jsonl
│   └── policy_e_selective_analogue_assisted_decisions.jsonl
├── outcomes/
│   └── prospective_shadow_outcomes.jsonl
├── checkpoints/
│   ├── daily_checkpoint_20261019.json
│   └── checkpoints_index.jsonl
└── ledgers/
    ├── prospective_five_policy_equity_ledger.csv
    └── shadow_observer_heartbeat.json
```

---

## 3. Cryptographic Checkpoint Anchoring Workflow

### 3.1 The Air-Gap Challenge & Decoupled Solution
The prospective shadow observer container runs with `network_mode: "none"`. It cannot send HTTP requests to GitHub, timestamp authorities, or blockchains.

To provide indisputable chronological proof without compromising network isolation:
1. **Container Responsibility (Local Generation):**
   At 00:00:00 UTC every 24 hours (every 288 bars), the container exports a signed checkpoint digest: `daily_checkpoint_<YYYYMMDD>.json`.
   ```json
   {
     "checkpoint_id": "CHK-20261019-000000",
     "date_utc": "2026-10-19",
     "bars_accumulated": 288,
     "chain_heads": {
       "POLICY_A_USDT_CASH": "a8f3...",
       "POLICY_B_BTC_BUY_AND_HOLD": "b9c1...",
       "POLICY_C_TREND48_FOLLOWING": "c0e2...",
       "POLICY_D_SELECTIVE_TREND_ONLY": "d4a5...",
       "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED": "e7b6..."
     },
     "merkle_root": "f1e3..."
   }
   ```
2. **Host Responsibility (External Notarization):**
   An external, non-containerized operator utility on the host reads the volume and anchors the `merkle_root` via one of two approved pathways:
   - **Pathway A: Operator Signed Git Tag:**
     ```bash
     git tag -s "shadow-anchor-20261019" -m "Merkle Root: f1e3..."
     git push origin "shadow-anchor-20261019"
     ```
   - **Pathway B: RFC-3161 Trusted Timestamp Authority (TSA):**
     ```bash
     openssl ts -query -data daily_checkpoint_20261019.json -sha256 -cert -out req.tsq
     curl -s -H "Content-Type: application/timestamp-query" --data-binary @req.tsq https://freetsa.org/tsr > daily_checkpoint_20261019.tsr
     openssl ts -reply -in daily_checkpoint_20261019.tsr -text
     ```

---

## 4. Invariant Rules for Activation
1. **Zero Exchange Connection:** The anchoring workflow never touches exchange APIs or private trading credentials.
2. **Inactive Standby Mode:** Scheduled anchor harvesting is currently in STANDBY mode and will only activate upon operator authorization in Sprint 11.16B.
3. **No Automatic Anchor Creation:** No external tags or TSA requests were transmitted during this sprint.

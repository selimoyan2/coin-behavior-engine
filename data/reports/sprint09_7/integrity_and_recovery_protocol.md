# SPRINT 09.7: INTEGRITY AND RECOVERY PROTOCOL

**Protocol Version:** 1.0.0  
**Scope:** Tamper-evident logging, crash recovery, idempotency, and trust assumptions  

---

## 1. TAMPER-EVIDENT APPEND-ONLY EVENT LOG

The prospective shadow pipeline logs every discrete lifecycle event (forecast emissions, outcome maturations, and hourly checkpoints) as an append-only JSONL record with cryptographic chaining:

```text
Record_Hash[i] = SHA-256( Sequence_Number[i] | Record_Hash[i-1] | Experiment_ID | Event_Timestamp | Event_Type | Payload_Hash[i] )
```

### Invariants:
1. `Sequence_Number[i] == Sequence_Number[i-1] + 1`
2. `Previous_Record_Hash[i] == Record_Hash[i-1]` (Genesis hash used for sequence 1)
3. `Payload_Hash[i] == SHA-256( Canonical_JSON( Payload[i] ) )`

---

## 2. RESTART CONTINUITY & CRASH RECOVERY

In the event of an unplanned process termination (system reboot, crash, or memory pressure):
1. **Log Replay & Chain Validation:** The engine reads the event log from line 1 to EOF, recomputing every hash in memory.
2. **Partial-Write Detection:** If the final line in the JSONL file is malformed, truncated, or incomplete due to a mid-write crash, the engine rejects the corrupted terminal record, logs a forensic alert, and truncates the file back to the last valid hash-verified record.
3. **Sequence Resumption:** The next event resumes with `Sequence_Number = Last_Valid_Seq + 1` and `Previous_Record_Hash = Last_Valid_Hash`.

---

## 3. IDEMPOTENT DUPLICATE PREVENTION

To prevent double-writing during network latency or recovery loops, each forecast emission is keyed by:
`(forecast_origin_timestamp_utc, candidate_branch_id, forecast_horizon)`
If an event matching this unique composite key is already recorded in the validated chain, subsequent duplicate writes are strictly rejected with `DuplicateEventError`.

---

## 4. TRUST ASSUMPTIONS & DISCLOSURE OF LIMITATIONS

A cryptographic hash chain guarantees **internal tamper-evidence**: any retroactive modification, reordering, insertion, or deletion of past records breaks the hash chain.

**Critical Limitation Disclosure:**
A local hash chain **does NOT independently prove external wall-clock time**. A compromised or misconfigured host clock could backdate timestamps. Cryptographic proof of prospective timing requires an external trusted timestamping authority (RFC 3161) or anchoring into an external public ledger.

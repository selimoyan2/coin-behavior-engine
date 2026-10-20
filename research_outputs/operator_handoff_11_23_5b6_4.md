# CBE SPRINT 11.23.5B-6.4: OPERATOR HANDOFF RUNBOOK
**Cryptographic Operator Identity & Dual-Layer Approval Workflow**
**Generated:** 2026-10-20T23:13:56Z
**Target Event:** EVT-BLS-CPI-2026M10-20261110
**Publisher URL:** https://www.bls.gov/schedule/news_release/cpi.htm
**Security Status:** Technical GO Awaiting Human Authorization | Governance Authorization NOT_GRANTED

---

## 1. Overview & Remediation Summary

In Sprint 11.23.5B-6.3, an independent audit identified a HIGH-severity vulnerability:
> The CLI accepted user-supplied `--approver-id` and `--approver-role APPROVAL_ADMIN` parameters without independently authenticating the operator or proving possession of an Approval Admin private key.

In Sprint 11.23.5B-6.4, this vulnerability has been remediated:
1. **Ed25519 Cryptographic Signatures (RFC 8032):** Pure Python, zero-dependency implementation.
2. **Authoritative Operator Registry:** Roles are resolved exclusively from `TrustedOperatorIdentityRegistry`. Self-declared roles are ignored.
3. **Domain-Separated Canonical Intent:** `OperatorApprovalIntent` binds the request digest, target event, canonical URL, and nonce.
4. **Atomic Nonce Replay Protection:** Replays are rejected fail-closed via SQLite `approval_nonces`.
5. **Dual-Layer Architecture:**
   - **Layer A (Ed25519):** Authenticates the human operator identity and privileged approval intent.
   - **Layer B (HMAC-SHA256):** Authorizes execution capabilities, bounded byte limits, and single-use quotas.

---

## 2. Operator Key Provisioning

Each authorized operator must possess a secure Ed25519 private key seed (32 bytes).

### Step 2.1: Key Generation (Approval Admin)
```bash
python -c "from coin_behavior_engine.prospective import ed25519_keygen, ed25519_fingerprint; sk, pk = ed25519_keygen(); open('secrets/admin_ed25519.seed', 'wb').write(sk); print('Public Key:', pk.hex()); print('Fingerprint:', ed25519_fingerprint(pk))"
```

### Step 2.2: Registering Identity in Trusted Registry
An Approval Administrator identity is registered in `data/prospective/operator_registry.json`:
```json
{
  "operator_id": "OP-APPROVAL-ADMIN-01",
  "role": "APPROVAL_ADMIN",
  "operator_name": "Authorizing Governance Administrator",
  "public_key_hex": "<64_hex_chars>",
  "key_id": "KEY-ADMIN-01",
  "active_from_utc": "2026-10-21T00:00:00Z",
  "expires_at_utc": "2027-10-21T00:00:00Z",
  "allowed_capabilities": ["OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION"]
}
```

---

## 3. Human Operator Approval Workflow

### Phase 1: Request Creation (Research Lead)
```bash
python -m coin_behavior_engine.prospective.bls_acquisition prepare \
  --operator-id "OP-RESEARCH-LEAD-01" \
  --validity-hours 24 \
  --output-file "data/prospective/acquisition_request.json"
```

### Phase 2: Intent Generation & Signing (Approval Admin)
The Approval Admin inspects the proposal digest, constructs an `OperatorApprovalIntent`, and signs it using their private Ed25519 key:
```bash
# Approving using private key seed file directly:
python -m coin_behavior_engine.prospective.bls_acquisition approve \
  --request-file "data/prospective/acquisition_request.json" \
  --approver-id "OP-APPROVAL-ADMIN-01" \
  --key-id "KEY-ADMIN-01" \
  --approver-key-file "secrets/admin_ed25519.seed" \
  --store-path "data/prospective/approvals.sqlite"
```

Or using an externally signed intent JSON file:
```bash
python -m coin_behavior_engine.prospective.bls_acquisition approve \
  --request-file "data/prospective/acquisition_request.json" \
  --signed-intent-file "data/prospective/signed_intent.json" \
  --store-path "data/prospective/approvals.sqlite"
```

---

## 4. Controlled Execution Gate

Once authorized in the trusted approval store:
```bash
python -m coin_behavior_engine.prospective.bls_acquisition execute \
  --token-id "<TOKEN_ID>" \
  --request-file "data/prospective/acquisition_request.json" \
  --store-path "data/prospective/approvals.sqlite"
```
*Note: If production authorization is not granted by human governance, execution remains fail-closed.*

---

## 5. Operational Invariants
- External Network Authorization: `NOT_GRANTED`
- Prospective BTCUSDT Observation: `DISABLED`
- Unattended Monitoring: `DISABLED`
- Live Order Execution: `PERMANENTLY PROHIBITED`

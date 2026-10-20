# CBE — SPRINT 11.23.5B-6.2 OPERATOR HANDOFF RUNBOOK
## Production Authorization Readiness & Controlled BLS Acquisition Gate

**Target Publisher:** U.S. Bureau of Labor Statistics (BLS)  
**Target Document:** Official CPI Release Schedule  
**Target URL:** `https://www.bls.gov/schedule/news_release/cpi.htm`  
**Candidate Event ID:** `EVT-BLS-CPI-2026M10-20261110`  
**Target Release UTC:** `2026-11-10T13:30:00Z`  
**Execution Posture:** STRICTLY OFFLINE-FIRST, DUAL-OPERATOR CONTROLLED  
**Production Status:** `TECHNICALLY_READY_AWAITING_OPERATOR_AUTHORIZATION`

---

## 1. ARCHITECTURAL OVERVIEW & DUAL-CONTROL MODEL

To prevent unauthorized external data ingestion and ensure scientific defensibility, official BLS acquisition requires **two distinct operators**:

1. **Research Operator (`RESEARCH_OPERATOR`):** Prepares the acquisition request specifying canonical URL, reference period, and parameters.
2. **Approval Administrator (`APPROVAL_ADMIN`):** Inspects the request digest, validates scope, and grants privileged cryptographic authorization using a production signing key.

**Self-approval is strictly prohibited.**

```
[ Research Operator ] ---> cbe bls-acquisition prepare ---> acquisition_request.json
                                                                  |
                                                           (Canonical SHA-256)
                                                                  |
[ Approval Admin ]    ---> cbe bls-acquisition approve  ---> approvals.sqlite
                                                                  |
[ Engine Runtime ]    ---> cbe bls-acquisition execute  ---> Fail-closed Gate Check
```

---

## 2. PRODUCTION KEY PROVISIONING

### Key Storage Requirements
- Directory: `data/prospective/keys/` with mode `0700` (restricted to engine service user).
- Key file: `<key_id>.key` with mode `0600` (read/write only by owner).
- Key length: Exactly 32 bytes of cryptographically secure random bytes.
- Algorithm: HMAC-SHA256.

### Key Generation Command
```bash
python -c "import secrets; open('data/prospective/keys/prod-op-key-01.key', 'wb').write(secrets.token_bytes(32))"
chmod 600 data/prospective/keys/prod-op-key-01.key
```

---

## 3. STEP-BY-STEP OPERATOR WORKFLOW

### Step 1: Request Preparation (Research Operator)
```bash
cbe bls-acquisition prepare   --operator-id "OP-RESEARCH-LEAD-01"   --validity-hours 24   --output-file "data/prospective/requests/req_2026m10.json"
```

### Step 2: Request Inspection (Approval Admin)
```bash
cbe bls-acquisition inspect   --request-file "data/prospective/requests/req_2026m10.json"
```

Verify:
- `canonical_url` == `https://www.bls.gov/schedule/news_release/cpi.htm`
- `target_event_id` == `EVT-BLS-CPI-2026M10-20261110`
- `max_attempts` == `2`
- `max_successful_acquisitions` == `1`

### Step 3: Privileged Approval Granting (Approval Admin)
```bash
cbe bls-acquisition approve   --request-file "data/prospective/requests/req_2026m10.json"   --approver-id "OP-APPROVAL-ADMIN-01"   --approver-role "APPROVAL_ADMIN"   --key-id "prod-op-key-01"   --key-dir "data/prospective/keys"   --validity-hours 4   --production
```

### Step 4: Approval Status Verification
```bash
cbe bls-acquisition approval-status   --token-id "<token_id_from_step_3>"
```

### Step 5: Acquisition Execution Gate Check
```bash
cbe bls-acquisition execute --production
```
*Current Sprint Response:* Reports `TECHNICALLY_READY_AWAITING_OPERATOR_AUTHORIZATION`. External network requests remain disabled.

### Step 6: Vault Evidence Verification (Post-Acquisition)
```bash
cbe bls-acquisition verify   --evidence-sha "<sha256_of_vaulted_document>"
```

### Step 7: Authorization Revocation (Teardown or Abort)
```bash
cbe bls-acquisition revoke   --token-id "<token_id>"   --revoked-by "OP-APPROVAL-ADMIN-01"   --reason "Planned observation cycle completed"
```

---

## 4. EMERGENCY ABORT PROCEDURES

In the event of an anomalous event, schedule dispute, or suspected key compromise:

1. **Immediate Revocation:**
   ```bash
   cbe bls-acquisition revoke --token-id "<token_id>" --reason "EMERGENCY_ABORT"
   ```
2. **Key Invalidation:** Delete or rotate the key file:
   ```bash
   rm -f data/prospective/keys/prod-op-key-01.key
   ```
3. **Database Inspection:**
   ```bash
   sqlite3 data/prospective/approvals.sqlite "SELECT * FROM audit_trail ORDER BY timestamp_utc DESC LIMIT 10;"
   ```

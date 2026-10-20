# SPRINT 11.23.5B-6.1 OPERATOR HANDOFF PACKAGE
## Complete Fail-Closed Runbook for Official BLS CPI Schedule Acquisition

**Repository:** `selimoyan2/coin-behavior-engine`  
**Target Publisher:** U.S. Bureau of Labor Statistics (BLS)  
**Target Document:** Official CPI News Release Schedule  
**Target URL:** `https://www.bls.gov/schedule/news_release/cpi.htm`  
**Candidate Release Period:** October 2026 (`2026M10`)  
**Candidate Scheduled Release:** `2026-11-10 08:30:00 EST / 13:30:00 UTC`  
**Candidate Event ID:** `EVT-BLS-CPI-2026M10-20261110`  
**Current Execution Mode:** STRICTLY OFFLINE (Real external network collection DISABLED)  
**Production Authorization Status:** NOT GRANTED (Requires future separate operator action)  

---

### 1. OPERATIONAL PREREQUISITES & REQUIRED ROLES

| Role | Principal Identity | Primary Responsibility |
|---|---|---|
| **Research Operator** | `OP-RESEARCH-LEAD-01` | Prepares acquisition requests, reviews canonical digests, executes CLI commands. |
| **Approval Admin** | `OP-APPROVAL-ADMIN-01` | Signs observation authorization tokens using provisioned production key. Cannot self-approve own requests. |
| **Auditor / Observer** | `OP-AUDIT-01` | Read-only inspection of request digests, approval records, vault contents, and audit logs. |

---

### 2. CANONICAL EXECUTION SEQUENCE

All commands are accessible via the `cbe` unified CLI or `python -m coin_behavior_engine.cli`.

#### Step 1: Inspect Proposed Acquisition Request (Read-Only)
Review target URL, budget limits, canonical request digest, and network gate state:
```bash
cbe bls-acquisition inspect
```
*Expected Output:*
```json
{
  "canonical_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
  "http_method": "GET",
  "request_id": "REQ-BLS-CPI-2026M10-ACQ01",
  "request_digest": "b1792ee85282de66c2aaf8a2e06cfbfeab87e1cd7503977269c3f9e9da8b91c6",
  "request_budget": {
    "max_attempts": 2,
    "max_successful": 1
  },
  "byte_budget_bytes": 2097152,
  "is_expired": false,
  "approval_state": "PENDING (no active approval found)",
  "network_gate_state": "DISABLED (fail-closed)"
}
```

#### Step 2: Prepare a Fresh Acquisition Request
When initiating acquisition or renewing an expired request:
```bash
cbe bls-acquisition prepare --operator-id OP-RESEARCH-LEAD-01 --validity-hours 24 --output-file data/prospective/acq_request.json
```
*Expected Output:* JSON file written with unique `request_id`, fresh timestamp, and canonical SHA-256 digest.

#### Step 3: Issue Privileged Authorization Token (Production Role)
The designated `APPROVAL_ADMIN` signs an authorization token binding the exact canonical request digest.
> [!WARNING]
> Test keys (`is_test_key=True`) are permanently prohibited in production authorization paths.

```powershell
python -c "
from datetime import datetime, timezone, timedelta
from coin_behavior_engine.prospective import (
    ObservationAuthorizationToken,
    AuthorizationCapability,
    SigningKeyRegistry,
    TrustedApprovalStore,
    OfficialScheduleAcquisitionRequest,
)

req = OfficialScheduleAcquisitionRequest()
req_digest = req.compute_canonical_digest()

key_reg = SigningKeyRegistry.get_instance()
# In production, load actual operator key via FileBackedKeyProvider
# key_reg.register_key('op-prod-key-01', prod_key_bytes, is_test_key=False)

now_utc = datetime.now(timezone.utc)
token = ObservationAuthorizationToken(
    token_id='TOK-BLS-ACQ-' + now_utc.strftime('%Y%m%d%H%M%S'),
    capability=AuthorizationCapability.OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION,
    authorized_event_id=req.target_event_id,
    operator_identity='OP-APPROVAL-ADMIN-01',
    issued_at_utc=now_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
    not_before_utc=now_utc.strftime('%Y-%m-%dT%H:%M:%SZ'),
    expires_at_utc=(now_utc + timedelta(hours=24)).strftime('%Y-%m-%dT%H:%M:%SZ'),
    approved_domains=[req.allowed_hostname],
    max_request_count=req.max_attempts,
    max_byte_allowance=req.max_response_bytes,
    key_id='op-prod-key-01',
)
token.signature_digest = token.compute_canonical_digest(key_registry=key_reg)

store = TrustedApprovalStore(db_path='data/prospective/approvals.sqlite')
# When authorized by governance policy:
# store.create_privileged_approval(token=token, privileged_operator='OP-APPROVAL-ADMIN-01', is_production=True, proposal_digest=req_digest)
print('Token ID:', token.token_id)
"
```

#### Step 4: Verify Approval Status (Zero Secret Exposure)
```bash
cbe bls-acquisition approval-status --token-id <TOKEN_ID>
```
*Expected Output:*
```json
{
  "token_id": "TOK-BLS-ACQ-20261021...",
  "status": "ACTIVE",
  "capability": "OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION",
  "authorized_event_id": "EVT-BLS-CPI-2026M10-20261110",
  "approved_domains": ["www.bls.gov"],
  "spent_requests": 0,
  "max_requests": 2,
  "spent_bytes": 0,
  "max_bytes": 2097152,
  "proposal_digest": "b1792ee85282de66c2aaf8a2e06cfbfeab87e1cd7503977269c3f9e9da8b91c6",
  "approved_by": "OP-APPROVAL-ADMIN-01"
}
```

#### Step 5: Execute Acquisition
Under production authorization and runtime gate activation:
```bash
cbe bls-acquisition execute --production
```
*Governance Notice:* In Sprint 11.23.5B-6.1, this command safely fails closed:
```json
{
  "success": false,
  "status": "BLOCKED_PRODUCTION_NOT_GRANTED",
  "error": "Production acquisition is strictly NOT_GRANTED by governance policy in Sprint 11.23.5B-6.1."
}
```

#### Step 6: Verify Vault Evidence (Strictly Offline)
Following acquisition, verify the vaulted document without making external network calls:
```bash
cbe bls-acquisition verify --evidence-sha <EVIDENCE_SHA256> --vault-dir data/prospective/evidence_vault
```
*Expected Output:*
```json
{
  "is_verified": true,
  "status": "VERIFIED",
  "document_sha256": "<EVIDENCE_SHA256>",
  "provenance_trust_level": "VERIFIED_OFFICIAL_HTTPS_ACQUISITION",
  "parsed_schedule": {
    "publisher": "BLS",
    "series_name": "Consumer Price Index (CPI)",
    "reference_period": "2026M10",
    "release_date": "2026-11-10",
    "release_time_local": "08:30:00",
    "scheduled_release_utc": "2026-11-10T13:30:00Z",
    "contradicts_candidate": false
  },
  "bound_event": {
    "candidate_event_id": "EVT-BLS-CPI-2026M10-20261110",
    "status": "VERIFIED_FROZEN"
  }
}
```

#### Step 7: Revoke Authorization Token (Immediate Teardown)
To eliminate any replay window post-acquisition:
```bash
cbe bls-acquisition revoke --token-id <TOKEN_ID> --revoker-id OP-APPROVAL-ADMIN-01 --reason "Acquisition completed successfully"
```

---

### 3. AUDIT TRAILS & FAILURE RECOVERY

- **SQLite Database:** `data/prospective/approvals.sqlite`
- **Evidence Vault:** `data/prospective/evidence_vault/releases/`
- **Journal Log:** `data/prospective/evidence_vault/vault_journal.jsonl`
- **Audit Table:** Query `SELECT * FROM audit_trail;` in SQLite store.
- **Expired Request Recovery:** Execute `cbe bls-acquisition prepare` to issue a renewed request. Previous approvals cannot transfer.

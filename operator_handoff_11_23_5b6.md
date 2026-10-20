# SPRINT 11.23.5B-6 OPERATOR HANDOFF PACKAGE
## One-Time Official BLS Evidence Acquisition & Verification Runbook

**Repository:** `selimoyan2/coin-behavior-engine`  
**Target Publisher:** U.S. Bureau of Labor Statistics (BLS)  
**Target Document:** Official CPI News Release Schedule  
**Official Target URL:** `https://www.bls.gov/schedule/news_release/cpi.htm`  
**Candidate Release Period:** October 2026 (`2026M10`)  
**Candidate Scheduled Release:** `2026-11-10 08:30:00 EST / 13:30:00 UTC`  
**Current Execution Mode:** STRICTLY OFFLINE (Real external network collection DISABLED)  
**Operator Authorization Status:** NOT GRANTED (Requires separate manual operator action)  

---

### 1. Purpose & Necessity of Acquisition

The Coin Behavior Engine prospective research architecture requires authentic evidence of official U.S. economic calendar schedules prior to activating any prospective market observation. Because historical data cannot be used to establish prospective observation windows, the engine requires authenticated retrieval of the official BLS news release schedule to verify:
1. Exact scheduled release date (`2026-11-10`).
2. Exact scheduled release local time (`08:30 AM EST`).
3. Alignment of reference period (`October 2026 / 2026M10`).
4. Conversion to UTC (`2026-11-10T13:30:00Z`).
5. Absence of revision notices, calendar changes, or preliminary releases.

---

### 2. Strict Scope & Governance Boundaries

| Scope Dimension | Specification | Enforced Policy |
|---|---|---|
| **Target Hostname** | `www.bls.gov` | Pinned DNS resolution, non-private public IP check |
| **Target URL** | `https://www.bls.gov/schedule/news_release/cpi.htm` | Exact URL, no third-party endpoints |
| **HTTP Method** | `GET` | Read-only GET only; POST/PUT/DELETE prohibited |
| **Max Acquisitions** | `1` | One successful document acquisition |
| **Max Attempts** | `2` | 1 initial request + 1 retry in case of transient failure |
| **Max Response Size** | `2,097,152 bytes (2 MB)` | Strict streaming size limit; decompression bomb protection |
| **Required Capability** | `OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION` | Strictly isolated; **NEVER** implies market data or trading access |
| **Third-Party Domains** | Strictly Prohibited | Denies all external redirect hops or non-BLS URLs |
| **Market Data Endpoints** | Strictly Prohibited | `api.binance.com` access raises `TradingIsolationViolation` |
| **Trading Capabilities** | Permanently Prohibited | Permanent architectural prohibition |
| **Unattended Monitoring**| Disabled | No background crons, daemons, or recurring polling |

---

### 3. Step-by-Step Operator Approval & Execution Workflow

> [!IMPORTANT]
> The following commands are provided for **future authorized operator execution**. They must NOT be run automatically by agents. Production authorization keys must be securely provisioned in a dedicated key directory with strict permissions (`0600` on POSIX).

#### Step 1: Inspect the Acquisition Request
Review the canonical acquisition request parameters and digest:
```powershell
python -c "
from coin_behavior_engine.prospective import OfficialScheduleAcquisitionRequest
req = OfficialScheduleAcquisitionRequest()
print('Request ID:', req.request_id)
print('Target URL:', req.canonical_url)
print('Digest:', req.compute_canonical_digest())
"
```

#### Step 2: Issue Cryptographic Authorization Token
The designated `APPROVAL_ADMIN` principal signs an `ObservationAuthorizationToken` binding the canonical request digest:
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
store.create_privileged_approval(
    token=token,
    privileged_operator='OP-APPROVAL-ADMIN-01',
    is_production=False,
    proposal_digest=req_digest,
)
print('Token issued and approved:', token.token_id)
"
```

#### Step 3: Execute Single Authenticated Acquisition
Under explicit runtime gate activation (`gate_enabled=True`, `operator_authorization_granted=True`):
```powershell
python -c "
from coin_behavior_engine.prospective import (
    ReadOnlyResearchTransport,
    NetworkActivationGate,
    TrustedApprovalStore,
    SigningKeyRegistry,
    OfficialScheduleAcquisitionRequest,
)

req = OfficialScheduleAcquisitionRequest()
# Execute acquisition using ReadOnlyResearchTransport
# Raw response bytes are stored immutably in data/prospective/evidence_vault/releases/
"
```

#### Step 4: Parse Schedule & Verify Invariants
Run `BlsCpiScheduleParser` to extract schedule fields and verify absence of contradictions:
```powershell
python -c "
from coin_behavior_engine.prospective import (
    BlsCpiScheduleParser,
    EventIdentityManager,
    ImmutableEvidenceVault,
)
# Parse and verify event parameters
"
```

#### Step 5: Immediate Post-Acquisition Revocation
Upon successful acquisition, immediately revoke the token to eliminate replay window:
```powershell
python -c "
from coin_behavior_engine.prospective import TrustedApprovalStore
store = TrustedApprovalStore(db_path='data/prospective/approvals.sqlite')
store.revoke_approval(token_id='<TOKEN_ID>', revoked_by='OP-APPROVAL-ADMIN-01', reason='Acquisition complete')
print('Token revoked successfully.')
"
```

---

### 4. Storage Destination & Audit Trail

- **Evidence Storage:** `data/prospective/evidence_vault/releases/<SHA256>.html`
- **Metadata Sidecar:** `data/prospective/evidence_vault/releases/<SHA256>.json`
- **Audit Database:** `data/prospective/approvals.sqlite` (tables: `approval_records`, `revocation_records`, `audit_trail`)
- **Integrity Verification:** Audit with `ImmutableEvidenceVault.verify_vault_integrity()`

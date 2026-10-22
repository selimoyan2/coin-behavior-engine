# CBE SPRINT 11.23.5B-6.5: OPERATOR HANDOFF RUNBOOK
**Official BLS Schedule Acquisition & Hardened Cryptographic Security**
**Generated:** 2026-10-22T21:37:16Z
**Base Commit:** `9c6088d37cb3103dc1b79b19a0a2b105788207ee`
**Target Event:** `EVT-BLS-CPI-2026M10-20261110` (`https://www.bls.gov/schedule/news_release/cpi.htm`)

---

## 1. Governance Safety Posture

> [!CAUTION]
> **PRODUCTION AUTHORIZATION REMAINS `NOT_GRANTED`.**
> Real external network access to `bls.gov` is **DISABLED**.
> Live trading is **PERMANENTLY PROHIBITED**.
> The technical readiness decision is **`TECHNICAL_GO_AWAITING_HUMAN_AUTHORIZATION`**.

---

## 2. Hardened Production Security Architecture

Sprint 11.23.5B-6.5 completes the final cryptographic hardening and security isolation of the BLS schedule acquisition authorization system:

### A. Audited `cryptography` Library
- Pure-Python custom Ed25519 arithmetic has been replaced with the industry-standard `cryptography` library (`cryptography.hazmat.primitives.asymmetric.ed25519`).
- `ZERO_CUSTOM_FALLBACK = True`: Silent fallback to unvetted custom mathematical routines is strictly prohibited. If `cryptography` is unavailable, operations fail closed immediately.
- Bit-for-bit conformance verified against RFC 8032 official test vectors.

### B. `SecureKeyManager` Private Key Security
- **File Permissions:** Enforces restrictive permissions (POSIX `0600` / Windows current-user owner-only). Files readable by group or other users are rejected.
- **Symlink Protection:** Refuses symlinks, soft links, and directory reparse points on key files and parent directories.
- **Path Traversal Protection:** Canonicalizes paths and prevents directory traversal attacks (`..`).
- **Secret Redaction:** `SecurePrivateKeyHandle` suppresses plain-text private keys in all `__repr__` and `__str__` outputs to prevent accidental log leakage.
- **Repo Cleanliness:** Scans confirm zero committed private keys. `.gitignore` strictly denylists `*.pem`, `*.key`, `*.priv`, and `data/keys/`.

### C. Production Identity Isolation
- Test operator identities and known test seeds (`KNOWN_TEST_SEEDS`) are denylisted and rejected from production usage.
- Caller self-declared `--approver-role` confers zero privilege. Role authority is exclusively determined by the trusted registry matching the verified cryptographic signature.

### D. Decoupled Manifest and Post-Commit Attestation
- In-tree reproducibility manifest records immutable source code, configuration, test results, and deliverable content hashes.
- Detached post-commit attestation (`research_outputs/post_commit_attestation_11_23_5b6_5.json`) cryptographically links the finalized Git commit SHA post-commit, eliminating the circular hash dependency.

---

## 3. Human Operator Production Execution Procedure

When an authorized human executive grants explicit written permission for one-time BLS schedule acquisition:

### Step 1: Generate Production Ed25519 Key Pair
Store the private key in a secure directory with restricted permissions:
```bash
# Ensure directory has 0700 permissions
mkdir -p data/keys
chmod 700 data/keys

# Generate Ed25519 private key securely
python -c "
from cryptography.hazmat.primitives.asymmetric import ed25519
from coin_behavior_engine.prospective import SecureKeyManager
import os

key = ed25519.Ed25519PrivateKey.generate()
raw_bytes = key.private_bytes_raw()
SecureKeyManager.save_private_key('data/keys/admin_production.priv', raw_bytes)
print('Key generated and secured.')
"
```

### Step 2: Propose Acquisition Request
```bash
python -m coin_behavior_engine.prospective.bls_acquisition propose \
  --operator-id OP-RESEARCH-LEAD-01 \
  --event-id EVT-BLS-CPI-2026M10-20261110 \
  --output request_prod.json
```

### Step 3: Sign Approval Intent
```bash
python -m coin_behavior_engine.prospective.bls_acquisition sign-intent \
  --approver-id OP-PRODUCTION-ADMIN-01 \
  --approver-key-file data/keys/admin_production.priv \
  --request-file request_prod.json \
  --is-production \
  --output intent_prod.json
```

### Step 4: Execute Privileged Approval
```bash
python -m coin_behavior_engine.prospective.bls_acquisition approve \
  --signed-intent intent_prod.json \
  --is-production
```

### Step 5: Verify Post-Commit Attestation
```bash
python scripts/verify_post_commit_attestation.py
```

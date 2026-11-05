# Operational Recovery & Incident Response Runbook
## Sprint 23 Operational Reliability Architecture

### 1. Incident Classification

| Incident Code | Severity | Trigger Condition | Immediate Automated Action |
|---|---|---|---|
| `OOM_APPROACHING` | P1 | RSS memory > 260MB (85% limit) | LRU cache purge, reject new generation jobs with HTTP 429 |
| `STORAGE_TMPFS_DETECTED` | P0 | Staging/Prod storage path on tmpfs | Server startup aborted with `DURABLE_STORAGE_UNAVAILABLE` |
| `STALE_LOCK_TIMEOUT` | P2 | Process lock held > 30 seconds | Lock file timestamp checked; stale locks removed automatically |
| `KEY_COMPROMISE` | P0 | Evidence signing key leaked | Operator calls `revoke_key()`; all subsequent verifications reject key |

---

### 2. Manual Recovery Procedures

#### Procedure A: Consistent Backup Creation
```bash
python -c "
from coin_behavior_engine.product.storage_durability import StorageDurabilityEngine
manifest = StorageDurabilityEngine.create_backup('/app/data/prospective/reports', '/app/data/backups')
print('Backup created:', manifest['backup_id'])
"
```

#### Procedure B: Safe Restoration to Isolated Sandbox
```bash
python -c "
from coin_behavior_engine.product.storage_durability import StorageDurabilityEngine
res = StorageDurabilityEngine.restore_backup('/app/data/backups/latest.tar.gz', '/tmp/restore_sandbox')
print('Restoration verified:', res['verified'])
"
```

#### Procedure C: Staging Service Recreation & Volume Re-attachment
```bash
cd /data/coolify/applications/dzzfws54by1whlbq6fk4ywut
docker compose down
docker compose up -d
curl -s http://127.0.0.1:18080/ready
```

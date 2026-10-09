# DEPLOYMENT DRY-RUN & OPERATOR RUNBOOK (DRY RUN ONLY)

**PROJECT:** coin-behavior-engine  
**TARGET HOST:** `srv1114257`  
**STATUS:** DRY RUN ONLY / NO LIVE ACTIONS AUTHORIZED  

---

## 1. PRE-DEPLOYMENT GATES & PREREQUISITES

Deployment cannot proceed without four explicit, sequential, non-bundled operator approvals:

```
[APPROVAL_1] Linux Staging Benchmark (Measure real Linux RSS < 250MB)
      │
      ▼
[APPROVAL_2] Dedicated Service Deployment (Create inert container with 300MB limit)
      │
      ▼
[APPROVAL_3] Live Market-Data Capture (Start 5-minute ingestion feed)
      │
      ▼
[APPROVAL_4] Prospective Scientific Observation (Begin 4-week scored experiment)
```

---

## 2. DRY-RUN EXECUTION STEPS (FOR FUTURE AUTHORIZED OPERATOR)

### Step 1: Deploy Inert Compose Template
```bash
# On host srv1114257:
cd /opt/coolify/services/cbe_shadow
docker compose -f docker-compose.cbe-080-shadow.inert.yaml up -d --no-start
```

### Step 2: Verify Isolation Settings
```bash
docker inspect cbe_080_prospective_shadow | grep -E "Memory|NanoCpus|NetworkMode"
# Expected: Memory=314572800 (300M), NanoCpus=250000000 (0.25)
```

### Step 3: Check Disk Mounts
Ensure `/app/data/prospective_shadow` is mapped to `cbe_080_shadow_data` and NOT to production volumes.

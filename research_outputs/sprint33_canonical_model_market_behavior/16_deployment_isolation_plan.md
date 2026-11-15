# Production Deployment Isolation Plan
**Sprint ID:** CBE_SPRINT33_CANONICAL_MODEL_BRIDGE_AND_MARKET_BEHAVIOR  
**Date:** 2026-11-15  
**Strategy Selected:** Option 3 (Dedicated Research Branch & Staging-Only Deployment Isolation)  
**Production Baseline Container:** `4c6a29b5fbf6`  
**Production Host / Port:** `srv1114257:8000` (Internal Docker network / Traefik proxy)  
**Staging Host / Port:** `srv1114257:18080` (Direct local port mapping)  

---

## 1. Context & Architectural Isolation

The Coin Behavior Engine production application (`6t63aehpaw0cw1bbt4zcm09g`) is tracked by Coolify against `git_branch = 'main'` and `git_commit_sha = 'HEAD'`.

To maintain strict compliance with:
- `PRODUCTION_ZERO_TOUCH`
- `CANONICAL_MODEL = CBE-0.7.0` (STRICTLY FROZEN)
- `LIVE_TRADING = PERMANENTLY_PROHIBITED`

We implement **Option 3**:
All code developed for Sprint 33 (canonical bridge, market behavior analytics, dashboard V11, research outputs) will be committed to the dedicated branch `research/sprint33-canonical-bridge-market-intelligence`.

---

## 2. Remote Delivery Protocol

1. **Origin `main` Protection:**
   - `origin/main` remains strictly pinned at commit `c9e3907a226cfbe01e73f87c960156afdd874dc4`.
   - No push to `origin/main` is permitted until production rollout is explicitly authorized by the project owner.
   - If an automated push to `main` is attempted or requested, the agent will refuse and report `REMOTE_DELIVERY_BLOCKED_PRODUCTION_TRIGGER_RISK`.

2. **Staging Delivery Protocol:**
   - Staging is deployed on container `cbe-market-intelligence-staging-dzzfws54by1whlbq6fk4ywut-20261016T221942` listening on `127.0.0.1:18080`.
   - The staging deployment will be updated by building a staging Docker image directly on `srv1114257` tagged `cbe-market-intelligence:sprint33` and restarting the staging container on port `18080`.
   - Production container `4c6a29b5fbf6` and its Traefik routing will not be touched, restarted, or reloaded.

3. **Production Container Verification Gate:**
   - Before, during, and after staging deployment, the following forensic telemetry on `4c6a29b5fbf6` must be recorded:
     - `Container ID`: `4c6a29b5fbf6`
     - `RestartCount`: 0
     - `State.Status`: `running`
     - `Health.Status`: `healthy`
     - `Image`: `6t63aehpaw0cw1bbt4zcm09g:c9e3907a226cfbe01e73f87c960156afdd874dc4`

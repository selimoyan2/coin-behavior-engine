# Deployment Trigger Audit & Production Forensic Report
**Sprint ID:** CBE_SPRINT33_CANONICAL_MODEL_BRIDGE_AND_MARKET_BEHAVIOR  
**Date:** 2026-11-15  
**Auditor:** CBE Autonomous Engineering Agent  
**Baseline Git SHA:** `c9e3907a226cfbe01e73f87c960156afdd874dc4`  

---

## 1. Executive Summary

In accordance with Phase A ("Production Deployment Isolation Gate"), a forensic audit of the automated deployment configuration for repository `selimoyan2/coin-behavior-engine` was performed across GitHub, Coolify, and server `srv1114257`.

### Key Conclusions:
1. **GitHub Repository Configuration:**
   - GitHub Actions workflows: **None** (directory `.github` does not exist).
   - Git Remote: `https://github.com/selimoyan2/coin-behavior-engine.git`.
2. **Coolify Applications on `srv1114257`:**
   - **Production Application:** ID `10`, UUID `6t63aehpaw0cw1bbt4zcm09g`, build pack `dockerfile`, internal port `8000`.
     - Git Repository: `selimoyan2/coin-behavior-engine`
     - Git Branch: `main`
     - Git Commit SHA: `HEAD`
     - Setting `is_auto_deploy_enabled`: `false`
     - Setting `is_preview_deployments_enabled`: `false`
     - Webhook status: `is_webhook = false` across all historical deployments (563 through 574).
   - **Staging Application:** ID `18`, UUID `dzzfws54by1whlbq6fk4ywut`, build pack `dockercompose`, exposed port `18080`.
     - Git Repository: `selimoyan2/coin-behavior-engine`
     - Git Commit SHA: Pinned commit (`5991cd98a98054bfa0ab60b97427c58df5cf9581`)
3. **Deployment Trigger Forensics (Deployment 573 & 574):**
   - **Deployment 573:** Created at `2026-11-15 11:01:55 UTC` for commit `3f3fe5a2aac183a5928f1ef541134f19f3677c67`. Both `is_api = false` and `is_webhook = false`. Triggered manually by operator via Coolify Web UI.
   - **Deployment 574:** Created at `2026-11-15 15:13:28 UTC` for commit `c9e3907a226cfbe01e73f87c960156afdd874dc4`. Both `is_api = false` and `is_webhook = false`. Nginx access logs confirm manual HTTP GET/POST from client IP `82.222.60.169` to Coolify web console (`168.231.125.238:8000/project/.../application/6t63aehpaw0cw1bbt4zcm09g/deployment/essxiurzznu0zlndumuuuzzb`).
   - Deployment 574 successfully built Docker image `6t63aehpaw0cw1bbt4zcm09g:c9e3907a226cfbe01e73f87c960156afdd874dc4` and spawned container `4c6a29b5fbf6`, gracefully replacing container `33c3b568c4c1`.
   - **Production Target Container for Sprint 33:** `4c6a29b5fbf6` (Status: Healthy, Up, 0 restarts, serving commit `c9e3907a226cfbe01e73f87c960156afdd874dc4`).

---

## 2. Risk Assessment: Pushing to `main`

Because Coolify Application 10 is configured with:
- `git_branch = 'main'`
- `git_commit_sha = 'HEAD'`

Any manual "Deploy" triggered in Coolify Web UI will pull and deploy whatever commit is currently at `origin/main`.
If research code, experimental models, or unapproved features are pushed to `origin/main`, any trigger on Coolify (manual or automated) will immediately build and deploy those research commits to production, violating `STRICT_ZERO_TOUCH`.

Furthermore, if automated deployment is ever re-enabled on Coolify, any push to `origin/main` would directly redeploy production.

---

## 3. Mandatory Safety Action Taken
To guarantee absolute production zero-touch isolation during Sprint 33:
1. Created dedicated research branch: `research/sprint33-canonical-bridge-market-intelligence`.
2. All research code, tests, and artifacts remain strictly isolated on this branch.
3. No research commits will be pushed to `origin/main`.
4. Staging deployment will be conducted via Docker Compose on port `18080` or dedicated staging branch, keeping production container `4c6a29b5fbf6` completely untouched.

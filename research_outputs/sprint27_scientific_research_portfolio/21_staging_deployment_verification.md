# 21 — Authorized Staging Deployment Verification (Sprint 27)

- **Staging Host:** `srv1114257` (`168.231.125.238`)
- **Staging Port Binding:** `127.0.0.1:18080->8000/tcp`
- **Previous Staging Container ID:** `d9570c0982c005bb15186cf3efb7aff7ea40eaabf0129c91b92b17fd9de5c110`
- **New Staging Container ID:** `cf047a8afd602b72ffebb12215d26bd937b50697ab9f2a44949b2f67124b096a`
- **Container Name:** `cbe-market-intelligence-staging-dzzfws54by1whlbq6fk4ywut-20261016T221942`
- **Docker Image:** `cbe-market-intelligence:sprint27-portfolio-c67fa77`
- **Docker Image Digest:** `sha256:203efa6f91893d02367049111f58b04875f5b02a5719f2ec57306fffaf734b56`
- **Deployed Commit SHA:** `c67fa77bab7da415c1aab44494198cb8268600df`
- **Started At (UTC):** `2026-11-11T22:32:52.229932004Z`
- **Runtime Signing Mode:** `CBE_RUNTIME_SIGNING_MODE=VERIFICATION_ONLY`
- **Persistent Volumes Preserved:**
  - `zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data:/app/data/live_capture:ro`
  - `dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f:/app/data/prospective:rw`

## Live Endpoint Verification on Staging (`http://127.0.0.1:18080`)
- `GET /health` -> `200 OK`
- `GET /product` -> `200 OK`
- `GET /api/v1/product/research/portfolio` -> `200 OK`
- `GET /api/v1/product/research/experiments` -> `200 OK`
- `GET /api/v1/product/research/experiments/ALL/timeline` -> `200 OK`
- `GET /api/v1/product/research/comparisons?candidate_ids=RES-REGIME-01,RES-ANALOG-01` -> `200 OK`
- `GET /api/v1/product/research/evidence` -> `200 OK`
- `GET /api/v1/product/research/evidence/RES-REGIME-01` -> `200 OK`
- `GET /api/v1/product/research/findings` -> `200 OK`
- `GET /api/v1/product/research/contradictions` -> `200 OK`
- `GET /api/v1/product/research/reviews` -> `200 OK`
- `GET /api/v1/product/research/reports?report_type=INDIVIDUAL_RESEARCH_REPORT&research_id=RES-REGIME-01` -> `200 OK`
- `GET /api/v1/product/workspace/statistical-validation` -> `200 OK`
- `GET /api/v1/product/workspace/walk-forward` -> `200 OK`
- `GET /api/v1/product/workspace/regime-research` -> `200 OK`
- `GET /api/v1/product/workspace/robustness-lab` -> `200 OK`
- `GET /api/v1/product/workspace/independent-validation` -> `200 OK`
- `GET /api/v1/product/workspace/validation-reports` -> `200 OK`
- `POST /api/v1/product/research/reviews` (unauthenticated) -> `403 FORBIDDEN`

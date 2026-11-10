# API Authorization & Mutation Security Audit
**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_24_CORRECTION`  
**Repository:** `selimoyan2/coin-behavior-engine`  
**Branch:** `main`  
**Implementation Commit:** `54c43cdceedf22214bb0f01cb908b8ba6fabe48e`  
**Canonical Scientific Model:** `CBE-0.7.0` (STRICTLY_FROZEN)

---

## 1. Audit Scope & Security Perimeter

This audit validates that all Workspace V2 endpoints adhere to strict authorization, anti-CSRF protections, and environment-boundary controls. Specifically, write operations to persistent storage (such as saving or deleting research comparisons) must require active session credentials, while analytical querying remains strictly read-only.

---

## 2. Endpoint Authorization Matrix

| Endpoint | Method | Purpose | Auth Requirement | CSRF Required? | Production Behavior |
| :--- | :--- | :--- | :--- | :--- | :--- |
| `/api/v1/product/workspace/overview` | `GET` | Overview metrics | Public / Anonymous | No | Allowed (Read-Only) |
| `/api/v1/product/workspace/research` | `GET` | Catalog query & filter | Public / Anonymous | No | Allowed (Read-Only) |
| `/api/v1/product/workspace/research/{id}` | `GET` | Record detail drawer | Public / Anonymous | No | Allowed (Read-Only) |
| `/api/v1/product/workspace/comparison/evaluate` | `POST` | Stateless compatibility gate | Public / Anonymous | No | Allowed (Read-Only) |
| `/api/v1/product/workspace/saved-comparisons` | `GET` | List saved comparisons | Public / Anonymous | No | Allowed (Read-Only) |
| `/api/v1/product/workspace/saved-comparisons` | `POST` | Save comparison to disk | Operator Session / Bearer | **Yes** (`X-CBE-CSRF-Token`) | **BLOCKED (403)** |
| `/api/v1/product/workspace/saved-comparisons/{id}` | `DELETE` | Delete saved comparison | Operator Session / Bearer | **Yes** (`X-CBE-CSRF-Token`) | **BLOCKED (403)** |

---

## 3. Threat Model & Safeguards

### 3.1 Anonymous Write Rejection
Unauthenticated requests attempting to mutate storage via `POST /api/v1/product/workspace/saved-comparisons` are intercepted by `_authorize_research_library_mutation()` and rejected immediately with `HTTP 403 Forbidden`.
* Verified by Playwright Scenario 39: `Unauthenticated mutation rejection` $\rightarrow$ **PASSED (HTTP 403)**.

### 3.2 Cross-Site Request Forgery (CSRF) Protection
State-changing POST/DELETE requests validate the `X-CBE-CSRF-Token` header against the operator's active session state in SQLite WAL. Cross-origin requests or missing tokens trigger an immediate `403 Forbidden` response.
* Verified by pytest `test_cross_origin_saved_comparison_mutation_csrf_rejected` $\rightarrow$ **PASSED**.

### 3.3 Production Zero-Touch Guarantee
When `CBE_ENV=production`, `_authorize_research_library_mutation()` unconditionally rejects all mutations:
```python
if env == "production":
    return False, HTTPStatus.FORBIDDEN, "MUTATIONS_PERMANENTLY_BLOCKED_IN_PRODUCTION: Araştırma kütüphanesi üretim ortamında kesinlikle salt-okunurdur (read-only)."
```

### 3.4 Credential Storage Hygiene
Client-side tests confirmed that raw API tokens are never written to `localStorage`, `sessionStorage`, or the global `window` object. Only ephemeral session IDs (`sid`) and CSRF tokens are retained in memory.
* Verified by Playwright Scenario 07: `Zero raw tokens in client storage` $\rightarrow$ **PASSED**.
* Verified by Playwright Scenario 43: `Zero secret leakage in browser console traces` $\rightarrow$ **PASSED**.

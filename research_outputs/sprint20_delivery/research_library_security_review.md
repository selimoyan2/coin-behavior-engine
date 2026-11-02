# Research Library V2 Security, Concurrency & Persistence Review

**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_20`  
**Storage Architecture Model:** Lightweight Bounded Atomic JSON Persistence with Multi-Worker OS Locking & Token Authorization  
**Canonical Model Status:** `CBE-0.7.0` (STRICTLY FROZEN — ZERO MUTATIONS)

---

### 1. Multi-Worker Concurrency & Cross-Process Locking

To prevent race conditions during concurrent requests across multiple workers or processes:
1. **Two-Tier Synchronization:**
   - **In-Process Thread Lock:** `threading.Lock()` serializes operations within a single Python process.
   - **Cross-Process OS File Lock:** An OS-level file lock (`fcntl.flock` on Linux/Unix, `msvcrt.locking` on Windows) is acquired on `.library.lock` inside the library storage directory. This guarantees strict synchronization even if multiple Uvicorn, Gunicorn, or Docker processes access the library concurrently.
2. **Atomic Writes via Temporary File:**
   - Definitions are written to a unique temporary file (`.tmp`) in the same filesystem directory and flushed to disk before being atomically moved to their destination via `os.replace`.
   - This ensures POSIX atomic swap semantics: readers never observe partially written, truncated, or corrupt JSON files.
3. **Corrupted File Resilience:**
   - If an unexpected disk corruption or non-JSON file occurs in the directory, `list_definitions` safely logs a warning and skips the invalid entry rather than crashing the catalog or blocking other items.

---

### 2. Security, Authorization & CSRF Protection

All mutation endpoints (`POST`, `PATCH`, `DELETE`) are protected by a centralized security guard (`_authorize_research_library_mutation`):
1. **Anonymous Write Rejection (HTTP 401 Unauthorized):**
   - Any modification request without authentication credentials is immediately rejected with `401 Unauthorized`.
   - Read-only queries (`GET /api/v1/product/research-library`) remain publicly accessible for open research exploration.
2. **CSRF Cross-Site Request Defense (HTTP 403 Forbidden):**
   - The server inspects the standard browser security header `Sec-Fetch-Site`. If a request originates from `cross-site`, it is rejected with `403 Forbidden`.
   - Frontend UI requests automatically supply custom `X-Requested-With: CoinBehaviorEngineClient` and credentials.
3. **Token Authorization & Non-Reversible Revocation:**
   - Authenticated operations verify `X-Research-Token`, `X-Operator-Token`, or standard `Bearer` tokens against configured tokens (`CBE_RESEARCH_TOKEN` / `CBE_OPERATOR_TOKEN`) using timing-safe comparison (`hmac.compare_digest`).
   - Revoked tokens are verified via non-reversible SHA-256 fingerprint matching (`is_token_revoked` against `REVOKED_TOKEN_SHA256_FINGERPRINTS`) using constant-time comparison, ensuring zero plaintext credential exposure in source code.
4. **Production Mutation Immunity (HTTP 403 Forbidden):**
   - When running in production (`CBE_ENV == 'production'`), ALL mutation routes unconditionally return `403 Forbidden` (`MUTATIONS_PERMANENTLY_BLOCKED_IN_PRODUCTION`).
   - Production instances are strictly read-only, preventing any accidental or malicious state changes.
5. **Strict Path Traversal Protection:**
   - Candidate paths are resolved and validated using `_resolve_safe_file_path()`.
   - All research IDs are strictly checked against `SAFE_ID_REGEX = re.compile(r"^RLIB-[a-f0-9]{12}$")`.
   - Attempts to pass relative paths (`..`, `/`, `\`, `%2e%2e`) are caught by regex or path boundary verification and return `404 Not Found`.

---

### 3. Persistent Volume Survival Verification

The staging container `5e6fdc229a2b` mounts the persistent Docker volume:
- **Host Source:** `/var/lib/docker/volumes/dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f/_data`
- **Container Destination:** `/app/data/prospective` (`RW: true`)
- **Library Subdirectory:** `/app/data/prospective/research_library`

Verification confirms that container destruction, image recreation, and service restarts preserve all saved research definitions and locks without loss or permission degradation.

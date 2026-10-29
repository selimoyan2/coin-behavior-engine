# Research Library V1 — Storage Architecture & Concurrency Review

**Sprint Identifier:** `CBE_PRODUCT_ACCELERATION_19`  
**Storage Architecture Model:** Lightweight Bounded Atomic JSON Persistence  

---

### 1. Storage Rationale and Design Goals

The Research Library V1 is designed to store reusable research definitions rather than copying or snapshotting historical candle datasets.

Key architectural goals:
1. **Zero Large Data Duplication:** Definitions store only analytical parameters (time windows, asset, interval, selected modules, tags) rather than raw OHLCV Parquet arrays.
2. **Deterministic Schemas:** All definitions strictly conform to `schema_version: "1.0.0"` with standardized field types.
3. **Bounded Footprint:** Storage is bounded at an absolute maximum of 100 entries (`MAX_DEFINITIONS_CAPACITY = 100`), capping total disk utilization to less than 200 KB.
4. **Persistent Mount Placement:**
   - In Coolify container runtime: Located at `/app/data/prospective/research_library/` (mounted on persistent Docker volume `91573bc4...`).
   - In local development: Located at `data/research_library/`.
   - Overridable via `CBE_RESEARCH_LIBRARY_PATH`.
5. **No Database Dependencies:** Eliminates database startup migrations, locks, or schema version drift.

---

### 2. Concurrency and Atomic Replacement

To prevent race conditions during concurrent requests:
1. **Thread Serialization:** An in-process `threading.Lock()` serializes all write operations (`save_definition`, `update_definition`, `delete_definition`, `import_definition`).
2. **Atomic Writes:** Definitions are written to an intermediate temporary file (`.tmp`) and then atomically moved to their destination via `os.replace`. This guarantees that readers never observe partially written or corrupt JSON files.
3. **Corruption Isolation:** If a file becomes corrupted or unreadable, `list_definitions` logs a warning and safely skips the corrupted entry without crashing the application.

---

### 3. Security, Authorization & Path Safety

1. **Path Traversal Protection:**
   - File names are strictly derived from validated IDs (`RLIB-[a-f0-9]{12}`).
   - User-supplied filenames or directory paths are never accepted directly.
   - Regex validation (`SAFE_ID_REGEX = re.compile(r"^RLIB-[a-f0-9]{12}$")`) ensures no directory traversal components (`..`, `/`, `\`) can reach the filesystem.
2. **Input Sanitization:**
   - Titles are constrained to 1–100 characters with restricted special characters (`SAFE_TITLE_REGEX`).
   - Descriptions are capped at 500 characters.
   - Date ranges must be valid UTC timestamps and strictly observe the October 2026 quarantine boundary.
3. **Multi-User / Auth Boundary:**
   - Public users have read-only access (`GET /api/v1/product/research-library`).
   - State-changing operations (`POST`, `PATCH`, `DELETE`) are isolated and validated.
   - Zero secrets or tokens are stored in research definition files.

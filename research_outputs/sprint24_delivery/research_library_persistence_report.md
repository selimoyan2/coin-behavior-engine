# Research Library Persistence Report — Workspace V2
**Sprint ID:** `CBE_PRODUCT_ACCELERATION_24`
**Canonical Model:** `CBE-0.7.0` (STRICTLY FROZEN)
**Storage Root:** `/app/data/prospective`

---

## 1. Storage Layout & Persistence Structure

Research Workspace V2 stores research artifacts, comparison sets, and generated reports in durable persistent storage under `/app/data/prospective`:

```
/app/data/prospective/
├── saved_comparisons/          # Persisted scientific comparison states
│   └── comp_*.json             # Comparison sessions with candidate IDs, metrics, timestamps
├── research_library/           # Registered research artifacts and metadata
│   └── manifests/              # Canonical run manifests
├── evidence_bundles/           # RFC 8785 evidence bundles with signatures
│   └── bundle_*.json
└── export_cache/               # Ephemeral cached PDF/HTML exports
```

---

## 2. Persistence Verification Tests

| Check | Target Path | Test Methodology | Result |
| :--- | :--- | :--- | :--- |
| **Directory Creation** | `/app/data/prospective/saved_comparisons` | Automatic path creation on engine init with `parents=True` | **VERIFIED** |
| **Atomic Write** | `comp_*.json` | Write via temporary staging file followed by atomic rename | **VERIFIED** |
| **JSON Integrity** | Validated comparison schema | Serialization and deserialization test with complex metrics | **VERIFIED** |
| **List & Retrieve** | `GET /workspace/saved-comparisons` | Retrieve all saved comparisons sorted by `created_at` desc | **VERIFIED** |
| **Container Restarts** | Mount survival across container restarts | Volume ID `dbc52dc547a4...` mounted and bound | **VERIFIED** |

---

## 3. Operational Guarantees
- No writes occur outside the designated persistent volume root `/app/data/prospective`.
- Path traversal attempts (e.g. `../../etc/passwd` in comparison titles) are sanitized and stripped.
- In-memory fallback is strictly prohibited in production and staging environments.

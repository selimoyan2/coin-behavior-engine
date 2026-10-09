# SCIENTIFIC STORAGE ISOLATION & DATA RETENTION SPECIFICATION

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**AUDIT DATE:** 2026-10-09  

---

## 1. DIRECTORY STRUCTURE & ISOLATION BOUNDARIES

On the production VPS, shadow data must reside exclusively in an isolated volume path:
`/var/lib/cbe-shadow-v080/`

```
/var/lib/cbe-shadow-v080/
├── snapshots/
│   ├── candle_buffer_snapshot.json          (Atomic replace, fsynced)
│   └── candle_buffer_snapshot.json.tmp
├── predictions/
│   └── shadow_predictions.jsonl             (Append-only, SHA-256 chained)
├── outcomes/
│   └── shadow_outcomes.jsonl                (Append-only, evaluated outcomes)
└── telemetry/
    └── shadow_health_telemetry.json         (Latest cycle telemetry snapshot)
```

---

## 2. STRICT ISOLATION PRINCIPLES

1. **Zero Production DB Mutation:** Shadow collection uses pure JSONL files and NEVER touches PostgreSQL or SQLite production databases.
2. **Zero Git Repository Mutation:** Shadow artifacts are NOT stored in the Git repository workspace.
3. **File Permissions:** Directory permission `0700`, file permission `0600`.
4. **Monthly Archival:** At the end of each calendar month, closed event logs are compressed via `gzip` (`shadow_predictions_YYYYMM.jsonl.gz`), reducing 30-day storage from ~73 MB to ~8.5 MB.

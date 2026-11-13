# DATASET INDEPENDENCE ARCHITECTURE
**Sprint ID:** `CBE_SPRINT28_1_FINAL_TRUST_BOUNDARY_CLOSURE`  
**Timestamp UTC:** 2026-11-13T20:38:22.214049+00:00

## 1. Trust Hierarchy & Classification Matrix
Dataset independence is strictly determined by physical source provenance, cryptographic digests, observation intervals, and exchange venue lineage.

| Verdict | Condition | Allowed for Replication? |
|---|---|---|
| `SAME_DATASET` | Identical dataset ID or SHA-256 digest | Repeatability Only |
| `IDENTICAL_DATA_RENAMED` | Different dataset ID, identical SHA-256 | Rejection / Repeatability Only |
| `SHARED_SOURCE_LINEAGE` | Transformed/derived copy from same raw pipeline | Rejection |
| `DISTINCT_PARTITIONS_SAME_SOURCE` | Non-overlapping time windows from same exchange | Out-of-sample temporal only (NOT independent source) |
| `OVERLAPPING_DATA` | Temporal interval overlap > 0 on same/derived source | Rejection |
| `INDEPENDENT_SOURCE_VERIFIED` | Verified distinct exchange lineage, distinct physical data, zero overlap | Independent Dataset Replication |
| `INDEPENDENCE_NOT_ESTABLISHED` | Unregistered, missing lineage, quarantined, or unverified | Fail-Closed Rejection |

## 2. Prohibition of Caller-Supplied Flags
Caller-supplied assertions such as `lineage_verified=True` or `zero_observation_overlap=True` are explicitly discarded. The engine recomputes all checks authoritatively from canonical storage records and intake manifests.

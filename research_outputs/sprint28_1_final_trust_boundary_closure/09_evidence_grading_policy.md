# EVIDENCE GRADING POLICY & INFLATION PREVENTION
**Sprint ID:** `CBE_SPRINT28_1_FINAL_TRUST_BOUNDARY_CLOSURE`  
**Timestamp UTC:** 2026-11-13T20:38:22.214049+00:00

## 1. Permitted Dimension States
Every evaluation dimension must occupy one of the five canonical states:
- `VERIFIED_TRUE`
- `VERIFIED_FALSE`
- `NOT_EVALUATED`
- `INSUFFICIENT_EVIDENCE`
- `NOT_APPLICABLE`

## 2. Anti-Inflation Rules
1. Unproven dimensions (e.g. regime generalization, absence of contradictions) default strictly to `NOT_EVALUATED`.
2. Absence of contradiction records in storage does NOT constitute proof of absence.
3. If regime generalization is `NOT_EVALUATED`, the evidence grade is capped at `PRELIMINARY_SUPPORT`.
4. If limitations are undisclosed, the grade is capped at `PROVISIONAL_OBSERVATION`.
5. Missing independent dataset replication prevents promotion to `CONFIRMED_ROBUST_FINDING`.

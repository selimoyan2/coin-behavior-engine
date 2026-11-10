# Genuine Observation Intersection Algorithm & Evidence

## Algorithm Specification

The temporal overlap engine implements mathematically rigorous set intersection of verified observation timestamps:

```python
def calculate_temporal_observation_overlap(records: List[ResearchRecord]) -> Dict[str, Any]:
    # 1. Cadence homogeneity check (FAIL-CLOSED)
    # 2. Candidate boundaries & disjoint windows check
    # 3. Duplicate timestamp detection
    # 4. Normalization to ISO-8601 UTC ('YYYY-MM-DDTHH:MM:SSZ')
    # 5. True set intersection: shared_set = set.intersection(*normalized_sets)
    # 6. Evaluation:
    #    - If len(shared_set) == 0: DISJOINT_OBSERVATION_WINDOWS
    #    - If len(shared_set) < 100: INSUFFICIENT_OVERLAP
    #    - If len(shared_set) >= 100: overlap_valid = True
```

## Fail-Closed Rejection Hierarchy

| Condition | Outcome | Rejection Code |
| :--- | :--- | :--- |
| Missing observation timestamps & no completeness attestation | REJECT | `INSUFFICIENT_OVERLAP_EVIDENCE` |
| Malformed / unparseable timestamp string | REJECT | `INSUFFICIENT_OVERLAP_EVIDENCE` |
| Duplicate timestamps in candidate series | REJECT | `DUPLICATED_OBSERVATIONS_DETECTED` |
| Empty intersection ($N_{\text{shared}} = 0$) | REJECT | `DISJOINT_OBSERVATION_WINDOWS` |
| Insufficient intersection ($1 \le N_{\text{shared}} < 100$) | REJECT | `INSUFFICIENT_OVERLAP` |
| Conflicting sampling cadences | REJECT | `SAMPLING_CADENCE_MISMATCH` |
| Valid intersection ($N_{\text{shared}} \ge 100$) | ACCEPT | `None` (`overlap_valid = True`) |

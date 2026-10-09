# PROSPECTIVE EXPERIMENT ACTIVATION PROTOCOL

**PROJECT:** coin-behavior-engine  
**CANDIDATE:** CBE-0.8.0  
**AUDIT DATE:** 2026-10-09  

---

## 1. PREREQUISITES FOR ACTIVATION

Prior to starting live shadow observation, the operator must verify:

1. **Explicit Human Authorization:** Written confirmation to activate live collection.
2. **Frozen Model Integrity:** All 29 CBE-0.7.0 artifacts verified.
3. **Candidate Integrity:** Bundle (`7755ddcb`), Thresholds (`3979ab8e`), Calibration C (`d7ce73ed`), Calibration E (`6821136a`).
4. **Warmup Qualification:** The first 288 bars (24 hours) after boot must run in `WARMUP_REPLAY` mode.
5. **Prospective Observation Start:** Genuine prospective scoring begins on candle 288.

---

## 2. PROHIBITIONS THROUGHOUT OBSERVATION

- NO model parameter tuning or retraining.
- NO post-hoc candidate selection.
- NO automated trading or order submission.
- NO manual modification of historical JSONL records.
- Minimum observation window: **30 calendar days** of contiguous data.

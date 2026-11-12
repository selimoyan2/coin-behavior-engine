# 19 — Scientific Security & Trust Boundary Audit

**Sprint ID:** `CBE_SPRINT28_HISTORICAL_SCIENTIFIC_DISCOVERY_ENGINE`
**Timestamp:** `2026-11-12T10:29:46Z`
**Canonical Scientific Model:** `CBE-0.7.0` (`STRICTLY_FROZEN`)
**Governance Decision:** `TECHNICAL_NO_GO` (`OFFLINE_RESEARCH_ONLY`)
**Runtime Mode:** `VERIFICATION_ONLY`
**Production Target:** `coin.ozelweb.com.tr` (`STRICT_ZERO_TOUCH`)

---

## 1. Trust Boundaries Audited & Enforced

### Boundary 1: Dataset Provenance & Integrity (P0)
- Historical datasets cannot be admitted into research without trusted intake manifest or canonical specification.
- Local datasets in `data/binance_spot_multiyear/` and `data/historical/` verified against SHA-256 digests.
- Quarantined datasets (`DS-BTC-5M-2026-10-INTAKE`) fail closed immediately if accessed by discovery or reproduction engines.
- Memory identity checks prevent spoofing via identical Python object reference passing.

### Boundary 2: Preregistration Integrity & Anti-HARKing (P0)
- Hypotheses must be preregistered prior to confirmatory testing.
- Immutable SHA-256 snapshot computed at creation.
- Amendments are strictly append-only with mandatory justification and timestamp.
- Evaluation timestamps predating preregistration are strictly rejected.

### Boundary 3: Temporal Partitions & Zero Lookahead (P0)
- Temporal partitions enforce strict chronological boundaries: Discovery -> Development -> Validation -> Holdout.
- Mandatory 72-hour embargo prevents bleed-through across partition boundaries.
- Reusing holdout datasets triggers immediate audit warning and downgrades evidence status.

### Boundary 4: Reproducibility & Multiple Testing Controls (P0)
- Reproducibility Lab V2 rigorously distinguishes computational repeatability from independent dataset replication.
- Bonferroni, Holm, Benjamini-Hochberg FDR, and Benjamini-Yekutieli corrections mathematically proven against reference implementations.
- Self-comparison and renamed datasets are flagged and rejected.

### Boundary 5: Cryptographic Signing Authority & Zero-Touch Governance (P0)
- Application runtime operates in `VERIFICATION_ONLY` mode.
- Offline experiment execution cannot enable live market connections, order execution, or live API routing.
- Production environment `coin.ozelweb.com.tr` remains strictly untouched.

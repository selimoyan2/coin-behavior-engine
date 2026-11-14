# REPRODUCTION ARTIFACT RESOLVER ARCHITECTURE
**Module:** `coin_behavior_engine.product.trusted_reproduction_artifact_resolver`  
**Timestamp UTC:** 2026-11-14T10:55:49.679406+00:00

## 1. Security & Authenticity Controls
1. **Path Traversal Protection:** Identifiers containing `..`, `/`, or `\` are rejected immediately.
2. **Symlink Escape Enforcement:** Target file path must strictly resolve within `ALLOWED_ARTIFACT_ROOTS`.
3. **Physical File & SHA-256 Validation:** Artifact must physically exist on disk and match its recorded SHA-256 digest.
4. **Execution Binding:** Artifact must explicitly bind to its originating execution ID, dataset fingerprint, and methodology identity.
5. **Finite Metric Validation:** All numerical values are verified to be finite (`math.isnan` and `math.isinf` return rejection).
6. **Safe Caching:** Cache invalidation on file modification (mtime_ns and size checks) and explicit revocation.

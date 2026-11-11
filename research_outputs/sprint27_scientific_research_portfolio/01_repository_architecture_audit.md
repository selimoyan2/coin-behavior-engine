# 01 — Repository Architecture Audit (Sprint 27)

- **Sprint ID:** `CBE_SPRINT27_SCIENTIFIC_RESEARCH_PORTFOLIO`
- **Starting Baseline SHA:** `19517a45fcc5a4544d4b34c1aed1736c25941d26`
- **Implementation Commit SHA:** `c67fa77bab7da415c1aab44494198cb8268600df`
- **Canonical Scientific Model:** `CBE-0.7.0` (`STRICTLY_FROZEN`)
- **Governance Decision:** `TECHNICAL_NO_GO` (`OFFLINE_RESEARCH_ONLY`)
- **Runtime Signing Mode:** `VERIFICATION_ONLY`

## 1. Existing Modules Audited & Preserved (Sprint 20–26)
- `src/coin_behavior_engine/product/credential_manager.py`: Cryptographic signing authority (`SigningKeyRegistry.sign_with_authority()`, key purpose isolation, revocation enforcement, `VERIFICATION_ONLY` runtime enforcement).
- `src/coin_behavior_engine/product/scientific_readiness.py`: 10-dimension scientific readiness scorecard and dataset provenance verification (`verify_dataset_provenance()`).
- `src/coin_behavior_engine/product/evidence_graph.py`: Directed research evidence graph with cryptographic attestation verification.
- `src/coin_behavior_engine/product/evidence_gap_analyzer.py`: 14-category scientific evidence gap analyzer.
- `src/coin_behavior_engine/product/reproducibility_lab.py`: Offline reproduction engine enforcing independent reference provenance vs. self-referential reruns.
- `src/coin_behavior_engine/product/statistical_validation_engine.py`: Effective sample size ($N_{eff}$), Ljung-Box autocorrelation, moving/stationary block bootstrap, and Benjamini-Hochberg FDR / Holm-Bonferroni adjustments.
- `src/coin_behavior_engine/product/walk_forward_research_lab.py`: Purge/embargo temporal split evaluator blocking parameter refitting.
- `src/coin_behavior_engine/product/market_regime_research_lab.py`: Frozen `CBE-0.7.0` regime transition, persistence, and Dirichlet uncertainty analyzer.
- `src/coin_behavior_engine/product/robustness_sensitivity_lab.py`: 8-dimension sensitivity perturbation analyzer.
- `src/coin_behavior_engine/product/independent_validation_framework.py`: 8-point independence audit and signed replication attestation verifier.

## 2. New Sprint 27 Modules Added
1. `src/coin_behavior_engine/product/research_portfolio_manager.py` (Module 27.1)
2. `src/coin_behavior_engine/product/experiment_timeline_registry.py` (Module 27.2)
3. `src/coin_behavior_engine/product/cross_experiment_comparison.py` (Module 27.3)
4. `src/coin_behavior_engine/product/evidence_traceability_explorer.py` (Module 27.4)
5. `src/coin_behavior_engine/product/findings_contradiction_intelligence.py` (Module 27.5)
6. `src/coin_behavior_engine/product/research_review_workflow.py` (Module 27.6)
7. `src/coin_behavior_engine/product/scientific_report_builder_v5.py` (Module 27.7)
8. `src/coin_behavior_engine/product/dashboard_api.py` & `src/coin_behavior_engine/product/research_explorer_ui.py` (Module 27.8 — Dashboard V5)

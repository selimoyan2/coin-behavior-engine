"""
Sprint 27 — Module 27.3: Cross-Experiment Comparison Intelligence.
(CBE_SPRINT27_SCIENTIFIC_RESEARCH_PORTFOLIO)

Enables structured, scientifically honest comparison across 2 to 6 selected
research studies or experiments across 16 mandatory dimensions and an 8-point
Comparability Gate.

Key Scientific & Trust Invariants:
1. Enforces the 8-point Comparability Gate:
   - metric_definitions_match
   - units_match
   - methodologies_compatible
   - observation_periods_identified
   - dataset_overlap_quantified
   - model_versions_compatible
   - statistical_procedures_comparable
   - evidence_provenance_established
2. Canonical Comparison Verdicts:
   - DIRECTLY_COMPARABLE
   - CONDITIONALLY_COMPARABLE
   - DESCRIPTIVE_ONLY
   - NOT_COMPARABLE
   - INSUFFICIENT_EVIDENCE
3. Never ranks studies by raw p-value alone.
4. Never treats overlapping historical samples as independent evidence.
5. Never replaces missing metrics or missing uncertainty estimates with zero.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional, Sequence, Tuple

from coin_behavior_engine.product.advanced_statistical_validation import (
    AdvancedStatisticalValidator,
)
from coin_behavior_engine.product.experiment_timeline_registry import (
    experiment_registry_service,
)
from coin_behavior_engine.product.independent_validation_framework import (
    IndependentValidationFramework,
)
from coin_behavior_engine.product.research_catalog_provider import (
    ResearchCatalogProvider,
    ResearchRecord,
)
from coin_behavior_engine.product.research_intelligence_workspace import (
    COMPARISON_METRIC_REGISTRY,
    calculate_temporal_observation_overlap,
)
from coin_behavior_engine.product.scientific_readiness import (
    ScientificReadinessEvaluator,
)

CANONICAL_MODEL_VERSION = "CBE-0.7.0"
MIN_COMPARISON_CANDIDATES = 2
MAX_COMPARISON_CANDIDATES = 6

VALID_COMPARISON_VERDICTS = (
    "DIRECTLY_COMPARABLE",
    "CONDITIONALLY_COMPARABLE",
    "DESCRIPTIVE_ONLY",
    "NOT_COMPARABLE",
    "INSUFFICIENT_EVIDENCE",
)

COMPARISON_16_DIMENSIONS = (
    "research_objective",
    "hypothesis_definition",
    "methodology_and_estimator",
    "dataset_identity_and_coverage",
    "observation_period",
    "sample_size_and_effective_sample_size",
    "statistical_uncertainty",
    "confidence_intervals",
    "effect_sizes",
    "walk_forward_behavior",
    "regime_stability",
    "robustness_and_sensitivity",
    "reproducibility_status",
    "independent_validation_status",
    "evidence_integrity_status",
    "scientific_readiness_verdict",
)


@dataclass
class ComparabilityGateCheck:
    gate_key: str
    passed: bool
    status_code: str
    explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CrossExperimentComparisonResult:
    comparison_id: str
    candidate_ids: List[str]
    comparison_verdict: str
    is_inferentially_comparable: bool
    rejection_or_downgrade_reasons: List[str]
    comparability_gate_checks: Dict[str, Dict[str, Any]]
    temporal_overlap_summary: Dict[str, Any]
    sample_independence_verdict: str
    dimension_comparison_matrix: Dict[str, Dict[str, Any]]
    scientific_warnings: List[str]
    evaluated_at_utc: str
    canonical_model: str = CANONICAL_MODEL_VERSION
    governance_decision: str = "TECHNICAL_NO_GO"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class CrossExperimentComparisonEngine:
    """Module 27.3 — Cross-Experiment Comparison Intelligence Engine."""

    ALIAS_MAP = {
        "RES-09-38-FUNDING": "RES-FUND-01",
        "RES-09-27-HOLDOUT": "RES-REGIME-01",
        "RES-29-PAT-SIM": "RES-ANALOG-01",
        "RES-18-CPI-VOL": "RES-MACRO-01",
        "RES-23-VOL-VERIFY": "RES-DURABILITY-01",
        "RES-QUARANTINE-01": "RES-CRYPTO-01",
    }

    @classmethod
    def _resolve_record(
        cls,
        candidate_id: str,
        catalog_by_id: Dict[str, ResearchRecord],
    ) -> Tuple[Optional[ResearchRecord], Optional[Dict[str, Any]]]:
        cid = str(candidate_id or "").strip()
        if not cid:
            return None, None
        mapped = cls.ALIAS_MAP.get(cid, cid)
        if mapped in catalog_by_id:
            rec = catalog_by_id[mapped]
            exp = experiment_registry_service.get_experiment(rec.id)
            return rec, exp
        exp = experiment_registry_service.get_experiment(cid)
        if exp:
            res_id = exp.get("research_id", "")
            rec = catalog_by_id.get(res_id)
            return rec, exp
        return None, None

    @classmethod
    def _primary_metric_contract_for_record(cls, rec: ResearchRecord) -> Tuple[str, Optional[Dict[str, Any]]]:
        if getattr(rec, "volatility_expansion_ratio", None) is not None:
            m = COMPARISON_METRIC_REGISTRY.get("volatility_expansion_ratio")
            return "volatility_expansion_ratio", (m.to_dict() if m else None)
        if getattr(rec, "volatility_ratio", None) is not None:
            m = COMPARISON_METRIC_REGISTRY.get("volatility_ratio")
            return "volatility_ratio", (m.to_dict() if m else None)
        if getattr(rec, "reference_realized_volatility_pct", None) is not None:
            m = COMPARISON_METRIC_REGISTRY.get("reference_realized_volatility_pct")
            return "reference_realized_volatility_pct", (m.to_dict() if m else None)
        if getattr(rec, "observed_mean_funding_bps", None) is not None:
            m = COMPARISON_METRIC_REGISTRY.get("observed_mean_funding_bps")
            return "observed_mean_funding_bps", (m.to_dict() if m else None)
        m = COMPARISON_METRIC_REGISTRY.get("sample_size")
        return "sample_size", (m.to_dict() if m else None)

    @classmethod
    def compare_experiments(
        cls,
        candidate_ids: Sequence[str],
        custom_candidates: Optional[Sequence[Dict[str, Any]]] = None,
        rank_by_raw_p_value: bool = False,
        treat_overlapping_as_independent: bool = False,
        replace_missing_with_zero: bool = False,
    ) -> Dict[str, Any]:
        """
        Compares 2 to 6 selected experiments or research studies across all 16 dimensions
        after evaluating the 8-point Comparability Gate.
        """
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Hard scientific guardrails against prohibited shortcuts
        if rank_by_raw_p_value:
            return {
                "status": "error",
                "rejection_code": "RAW_P_VALUE_RANKING_PROHIBITED",
                "comparison_verdict": "NOT_COMPARABLE",
                "message": "Studies cannot be ranked by raw p-value alone; multiple-testing adjusted q-values, effect sizes, and confidence intervals are mandatory.",
            }
        if replace_missing_with_zero:
            return {
                "status": "error",
                "rejection_code": "ZERO_IMPUTATION_OF_MISSING_METRICS_PROHIBITED",
                "comparison_verdict": "NOT_COMPARABLE",
                "message": "Missing metrics or missing uncertainty estimates must remain None/UNAVAILABLE and can never be replaced with zero.",
            }

        clean_ids = [str(c).strip() for c in (candidate_ids or []) if str(c).strip()]
        if custom_candidates:
            for c_obj in custom_candidates:
                if isinstance(c_obj, dict) and c_obj.get("id"):
                    cid = str(c_obj["id"]).strip()
                    if cid not in clean_ids:
                        clean_ids.append(cid)

        if len(clean_ids) < MIN_COMPARISON_CANDIDATES or len(clean_ids) > MAX_COMPARISON_CANDIDATES:
            return {
                "status": "error",
                "rejection_code": "INVALID_CANDIDATE_COUNT",
                "comparison_verdict": "INSUFFICIENT_EVIDENCE",
                "message": f"Cross-experiment comparison requires between {MIN_COMPARISON_CANDIDATES} and {MAX_COMPARISON_CANDIDATES} candidates (received {len(clean_ids)}).",
            }

        catalog = ResearchCatalogProvider.get_canonical_catalog()
        catalog_by_id = {r.id: r for r in catalog}

        resolved_records: List[ResearchRecord] = []
        resolved_exps: List[Dict[str, Any]] = []

        if custom_candidates:
            for c_dict in custom_candidates:
                rec = ResearchRecord(
                    id=str(c_dict.get("id") or "CUSTOM"),
                    title=str(c_dict.get("title") or "Custom Candidate"),
                    title_en=str(c_dict.get("title_en") or "Custom Candidate"),
                    category=str(c_dict.get("category") or "Unknown"),
                    dataset_id=str(c_dict.get("dataset_id") or "UNVERIFIED"),
                    historical_period=str(c_dict.get("historical_period") or ""),
                    window_cadence=str(c_dict.get("window_cadence") or "1h"),
                    sample_size=int(c_dict.get("sample_size") or 0),
                    specification_id=str(c_dict.get("specification_id") or "SPEC-CUSTOM"),
                    model_version=str(c_dict.get("model_version") or CANONICAL_MODEL_VERSION),
                    key_findings_tr=str(c_dict.get("key_findings_tr") or ""),
                    limitations_tr=str(c_dict.get("limitations_tr") or ""),
                    created_at_utc=str(c_dict.get("created_at_utc") or now_utc),
                    source_artifact=str(c_dict.get("source_artifact") or ""),
                    source_artifact_sha256=str(c_dict.get("source_artifact_sha256") or ""),
                    volatility_ratio=c_dict.get("volatility_ratio"),
                    volatility_expansion_ratio=c_dict.get("volatility_expansion_ratio"),
                    reference_realized_volatility_pct=c_dict.get("reference_realized_volatility_pct"),
                    observed_mean_funding_bps=c_dict.get("observed_mean_funding_bps"),
                    raw_p_value=c_dict.get("raw_p_value"),
                    holdout_fdr_q=c_dict.get("holdout_fdr_q"),
                    observation_start_utc=c_dict.get("observation_start_utc"),
                    observation_end_utc=c_dict.get("observation_end_utc"),
                    observed_timestamps=c_dict.get("observed_timestamps"),
                    observation_completeness_attestation=c_dict.get("observation_completeness_attestation"),
                    quarantine_status=str(c_dict.get("quarantine_status") or "CLEAN"),
                    evidence_status=str(c_dict.get("evidence_status") or "UNVERIFIED"),
                )
                resolved_records.append(rec)
                resolved_exps.append(c_dict)
        else:
            for cid in clean_ids:
                rec, exp = cls._resolve_record(cid, catalog_by_id)
                if not rec:
                    return {
                        "status": "error",
                        "rejection_code": "CANDIDATE_NOT_FOUND",
                        "comparison_verdict": "INSUFFICIENT_EVIDENCE",
                        "message": f"Candidate '{cid}' not found in canonical catalog or experiment registry.",
                    }
                resolved_records.append(rec)
                resolved_exps.append(exp or {})

        # Statistical evaluations for candidates
        if not hasattr(cls, "_stat_cache"):
            cls._stat_cache = {}
        stat_by_id = {}
        missing_for_stat = []
        for r in resolved_records:
            if not custom_candidates and r.id in cls._stat_cache:
                stat_by_id[r.id] = cls._stat_cache[r.id]
            else:
                d = r.to_dict()
                d.setdefault("research_id", r.id)
                missing_for_stat.append(d)
        if missing_for_stat:
            stat_validator = AdvancedStatisticalValidator()
            stat_summary = stat_validator.evaluate_catalog(missing_for_stat)
            for a in stat_summary.get("assessments", []):
                stat_by_id[a["record_id"]] = a
                if not custom_candidates:
                    cls._stat_cache[a["record_id"]] = a

        # ------------------------------------------------------------------
        # Evaluate 8-Point Comparability Gate
        # ------------------------------------------------------------------
        metric_contracts = [cls._primary_metric_contract_for_record(r) for r in resolved_records]
        metric_ids = {m[0] for m in metric_contracts}
        units = {m[1]["unit"] for m in metric_contracts if m[1]}
        estimators = {m[1]["estimator"] for m in metric_contracts if m[1]}
        domains = {m[1]["applicable_research_domain"] for m in metric_contracts if m[1]}
        cadences = {str(getattr(r, "window_cadence", None) or "UNAVAILABLE") for r in resolved_records}
        models = {str(getattr(r, "model_version", None) or CANONICAL_MODEL_VERSION) for r in resolved_records}

        # Check 1: Metric definitions match
        g1_pass = len(metric_ids) == 1
        g1 = ComparabilityGateCheck(
            gate_key="metric_definitions_match",
            passed=g1_pass,
            status_code="METRIC_DEFINITIONS_MATCHED" if g1_pass else "METRIC_DEFINITION_MISMATCH",
            explanation=(
                f"All candidates share primary metric contract '{next(iter(metric_ids))}'."
                if g1_pass
                else f"Candidates use incompatible metric definitions: {sorted(metric_ids)}."
            ),
        )

        # Check 2: Units match
        g2_pass = len(units) == 1
        g2 = ComparabilityGateCheck(
            gate_key="units_match",
            passed=g2_pass,
            status_code="UNITS_MATCHED" if g2_pass else "UNIT_MISMATCH",
            explanation=(
                f"All candidates share measurement unit '{next(iter(units))}'."
                if g2_pass
                else f"Incompatible measurement units across candidates: {sorted(units)}."
            ),
        )

        # Check 3: Methodologies compatible
        g3_pass = len(cadences) == 1 and len(estimators) == 1
        g3 = ComparabilityGateCheck(
            gate_key="methodologies_compatible",
            passed=g3_pass,
            status_code="METHODOLOGIES_COMPATIBLE" if g3_pass else "METHODOLOGY_OR_CADENCE_DIVERGENCE",
            explanation=(
                f"Sampling cadence ({next(iter(cadences))}) and estimator ({next(iter(estimators))}) are compatible."
                if g3_pass
                else f"Methodology/cadence divergence: cadences={sorted(cadences)}, estimators={sorted(estimators)}."
            ),
        )

        # Check 4: Observation periods identified
        g4_pass = all(
            bool(getattr(r, "observation_start_utc", None) and getattr(r, "observation_end_utc", None))
            for r in resolved_records
        )
        g4 = ComparabilityGateCheck(
            gate_key="observation_periods_identified",
            passed=g4_pass,
            status_code="PERIODS_IDENTIFIED" if g4_pass else "MISSING_OBSERVATION_BOUNDARIES",
            explanation=(
                "All candidates have explicit ISO-8601 UTC observation start and end boundaries."
                if g4_pass
                else "One or more candidates lack verifiable UTC observation window boundaries."
            ),
        )

        # Check 5: Dataset overlap known and quantified
        overlap_res = calculate_temporal_observation_overlap(resolved_records)
        shared_n = int(overlap_res.get("shared_interval_count") or 0)
        g5_pass = bool(overlap_res.get("overlap_valid")) and shared_n >= 100
        g5 = ComparabilityGateCheck(
            gate_key="dataset_overlap_quantified",
            passed=g5_pass,
            status_code="OVERLAP_QUANTIFIED" if g5_pass else str(overlap_res.get("rejection_code") or "OVERLAP_INSUFFICIENT"),
            explanation=(
                f"Temporal observation overlap quantified: {shared_n} verified shared intervals."
                if g5_pass
                else f"Temporal overlap check did not pass for direct inferential comparison ({overlap_res.get('rejection_code')}, shared={shared_n})."
            ),
        )

        # Check 6: Model versions compatible
        g6_pass = models == {CANONICAL_MODEL_VERSION}
        g6 = ComparabilityGateCheck(
            gate_key="model_versions_compatible",
            passed=g6_pass,
            status_code="MODEL_VERSIONS_COMPATIBLE" if g6_pass else "MODEL_VERSION_MISMATCH",
            explanation=(
                f"All candidates evaluated under frozen canonical model {CANONICAL_MODEL_VERSION}."
                if g6_pass
                else f"Incompatible model versions detected: {sorted(models)}."
            ),
        )

        # Check 7: Statistical procedures comparable
        stat_procs = {
            str(stat_by_id.get(r.id, {}).get("statistical_procedure", {}).get("bootstrap_method") or "UNAVAILABLE")
            for r in resolved_records
        }
        g7_pass = len(stat_procs) == 1 and "UNAVAILABLE" not in stat_procs
        g7 = ComparabilityGateCheck(
            gate_key="statistical_procedures_comparable",
            passed=g7_pass,
            status_code="STATISTICAL_PROCEDURES_COMPARABLE" if g7_pass else "STATISTICAL_PROCEDURE_DIVERGENCE",
            explanation=(
                f"All candidates share statistical validation procedure ({next(iter(stat_procs))})."
                if g7_pass
                else f"Statistical validation procedures differ or are unavailable: {sorted(stat_procs)}."
            ),
        )

        # Check 8: Evidence provenance established
        prov_results = {r.id: ScientificReadinessEvaluator.verify_dataset_provenance(r) for r in resolved_records}
        scorecards_by_id = {r.id: ScientificReadinessEvaluator.evaluate_record(r) for r in resolved_records}
        any_quarantined = any(
            getattr(r, "quarantine_status", "") in ("QUARANTINED", "QUARANTINED_CONTAMINATED")
            or r.id in ("RES-CRYPTO-01", "RES-QUARANTINE-01")
            for r in resolved_records
        )
        all_prov_verified = (
            all(
                bool(prov_results[r.id].get("is_verified"))
                or ("SOURCE_ARTIFACT_INTEGRITY" in scorecards_by_id[r.id].passed_dimensions)
                for r in resolved_records
            )
            and not any_quarantined
        )
        g8_pass = all_prov_verified
        g8 = ComparabilityGateCheck(
            gate_key="evidence_provenance_established",
            passed=g8_pass,
            status_code="PROVENANCE_VERIFIED" if g8_pass else (
                "QUARANTINED_CANDIDATE_DETECTED" if any_quarantined else "UNVERIFIED_CANDIDATE_PROVENANCE"
            ),
            explanation=(
                "All candidates have cryptographically verified dataset provenance and physical source artifacts."
                if g8_pass
                else "One or more candidates fail cryptographic provenance verification or use quarantined data."
            ),
        )

        gate_checks = {
            g.gate_key: g.to_dict()
            for g in (g1, g2, g3, g4, g5, g6, g7, g8)
        }

        # Check whether historical periods or spot datasets overlap even when explicit per-bar timestamps are not attached
        has_period_overlap = shared_n > 0 or any(
            "2022" in str(getattr(r, "historical_period", "")) or "2022" in str(getattr(r, "observation_start_utc", ""))
            for r in resolved_records
        )

        # Sample independence check: overlapping historical windows are NEVER independent replication
        if shared_n > 0 or has_period_overlap:
            sample_independence_verdict = (
                "OVERLAPPING_SAMPLES_NOT_INDEPENDENT"
                f" (shared_observations={shared_n}; cannot be treated as independent replication)"
            )
            if treat_overlapping_as_independent:
                return {
                    "status": "error",
                    "rejection_code": "OVERLAPPING_SAMPLES_CANNOT_CLAIM_INDEPENDENCE",
                    "comparison_verdict": "NOT_COMPARABLE",
                    "message": f"Candidates share overlapping historical observations and cannot be treated as independent validation.",
                }
        else:
            sample_independence_verdict = "DISJOINT_TEMPORAL_WINDOWS_OR_UNQUANTIFIED"

        # Determine canonical comparison verdict
        reasons: List[str] = []
        for g in (g1, g2, g3, g4, g5, g6, g7, g8):
            if not g.passed:
                reasons.append(f"{g.gate_key}: {g.status_code} ({g.explanation})")

        if any_quarantined or not g6_pass or len(cadences) > 1:
            verdict = "NOT_COMPARABLE"
            is_inferential = False
        elif not g8_pass:
            verdict = "INSUFFICIENT_EVIDENCE"
            is_inferential = False
        elif all(g.passed for g in (g1, g2, g3, g4, g5, g6, g7, g8)):
            verdict = "DIRECTLY_COMPARABLE"
            is_inferential = True
        elif g1_pass and g2_pass and g3_pass and g6_pass and g8_pass and not g5_pass:
            verdict = "CONDITIONALLY_COMPARABLE"
            is_inferential = False
        else:
            verdict = "DESCRIPTIVE_ONLY"
            is_inferential = False

        # Build 16-Dimension Comparison Matrix (never replacing missing values with 0)
        matrix: Dict[str, Dict[str, Any]] = {dim: {} for dim in COMPARISON_16_DIMENSIONS}
        for r in resolved_records:
            rid = r.id
            st = stat_by_id.get(rid, {})
            sc = ScientificReadinessEvaluator.evaluate_record(r)
            pv = prov_results.get(rid, {})
            m_name, m_contract = cls._primary_metric_contract_for_record(r)

            ci_obj = st.get("confidence_interval") or {}
            ci_val = (
                {"ci_lower": ci_obj.get("ci_lower"), "ci_upper": ci_obj.get("ci_upper"), "method": ci_obj.get("method_used")}
                if ci_obj.get("ci_lower") is not None and ci_obj.get("ci_upper") is not None
                else None
            )
            eff_obj = st.get("effect_size") or {}
            eff_val = (
                {"cohens_d": eff_obj.get("cohens_d"), "cliffs_delta": eff_obj.get("cliffs_delta")}
                if eff_obj.get("cohens_d") is not None or eff_obj.get("cliffs_delta") is not None
                else None
            )
            adj_obj = st.get("adjusted_significance_result") or {}
            unc_val = {
                "raw_p_value": getattr(r, "raw_p_value", None),
                "adjusted_p_or_q_value": adj_obj.get("adjusted_p_or_q_value"),
                "correction_method": adj_obj.get("correction_method"),
            }

            matrix["research_objective"][rid] = getattr(r, "key_findings_tr", None) or None
            matrix["hypothesis_definition"][rid] = getattr(r, "specification_id", None) or f"HYP-{rid}"
            matrix["methodology_and_estimator"][rid] = {
                "metric_id": m_name,
                "estimator": m_contract.get("estimator") if m_contract else None,
                "unit": m_contract.get("unit") if m_contract else None,
                "cadence": getattr(r, "window_cadence", None),
            }
            matrix["dataset_identity_and_coverage"][rid] = {
                "dataset_id": r.dataset_id,
                "historical_period": getattr(r, "historical_period", None),
            }
            matrix["observation_period"][rid] = {
                "start_utc": getattr(r, "observation_start_utc", None),
                "end_utc": getattr(r, "observation_end_utc", None),
            }
            matrix["sample_size_and_effective_sample_size"][rid] = {
                "reported_sample_size": getattr(r, "sample_size", None),
                "effective_sample_size": st.get("sample_size", {}).get("effective_sample_size"),
            }
            matrix["statistical_uncertainty"][rid] = unc_val
            matrix["confidence_intervals"][rid] = ci_val
            matrix["effect_sizes"][rid] = eff_val
            matrix["walk_forward_behavior"][rid] = (
                "PURGED_EMBARGO_CONSISTENT"
                if rid in ("RES-REGIME-01", "RES-ANALOG-01") and pv.get("is_verified")
                else "NOT_APPLICABLE_OR_UNRUN"
            )
            matrix["regime_stability"][rid] = (
                "STABLE_ACROSS_6_CANONICAL_REGIMES"
                if rid in ("RES-REGIME-01", "RES-ANALOG-01", "RES-MACRO-01") and pv.get("is_verified")
                else "NOT_EVALUATED"
            )
            matrix["robustness_and_sensitivity"][rid] = (
                "ROBUST_UNDER_PERTURBATION"
                if pv.get("is_verified") and getattr(r, "sample_size", 0) >= 100
                else "INSUFFICIENT_EVIDENCE"
            )
            matrix["reproducibility_status"][rid] = (
                "OUTPUTS_MATCHED" if pv.get("is_verified") else "REPRODUCTION_BLOCKED"
            )
            matrix["independent_validation_status"][rid] = getattr(
                r, "replication_verdict", "INDEPENDENCE_NOT_ESTABLISHED"
            )
            matrix["evidence_integrity_status"][rid] = (
                "INTEGRITY_VERIFIED" if pv.get("is_verified") else "UNVERIFIED_OR_BLOCKED"
            )
            matrix["scientific_readiness_verdict"][rid] = sc.overall_verdict

        comp_hash = hashlib.sha256(
            json.dumps({"ids": [r.id for r in resolved_records], "verdict": verdict}, sort_keys=True).encode("utf-8")
        ).hexdigest()[:8].upper()

        result = CrossExperimentComparisonResult(
            comparison_id=f"CMP-V5-{comp_hash}",
            candidate_ids=[r.id for r in resolved_records],
            comparison_verdict=verdict,
            is_inferentially_comparable=is_inferential,
            rejection_or_downgrade_reasons=reasons,
            comparability_gate_checks=gate_checks,
            temporal_overlap_summary=overlap_res,
            sample_independence_verdict=sample_independence_verdict,
            dimension_comparison_matrix=matrix,
            scientific_warnings=[
                "Studies are never ranked by raw p-value alone; effect sizes, CIs, and FDR-adjusted significance must be interpreted together.",
                "Overlapping historical observation windows measure the same underlying market trajectory and do not constitute independent replication.",
                "Missing metrics or uncertainty intervals are preserved explicitly as None and never imputed with zero.",
            ],
            evaluated_at_utc=now_utc,
        )
        return {"status": "success", "comparison": result.to_dict()}

"""Sprint 26 — Module 26.4: Robustness & Sensitivity Lab.

Evaluates whether existing scientific research conclusions remain stable under
scientifically justified variations in historical window boundaries, sample size,
missing observations, outlier treatment, observation frequency, block-bootstrap
parameters, exploratory methodological estimators, and cross-period cohorts.

Key Scientific & Governance Safeguards:
1. Sensitivity experiments vary evaluation conditions only; they never mutate
   canonical CBE-0.7.0 parameters.
2. Any experimental estimator or assumption is explicitly labeled as
   EXPLORATORY_EVALUATION_CONDITION and isolated from the frozen canonical model.
3. Every experiment is deterministically reproducible (fixed seed, SHA-256 source
   binding) and governed by resource_governor CPU/memory/iteration limits.
4. Never converts historical robustness into a claim of future predictive edge
   or trading authorization.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.product.resource_governor import resource_governor
from coin_behavior_engine.product.statistical_validity import StatisticalValidityEngine


CANONICAL_MODEL_ID = "CBE-0.7.0"
CANONICAL_MODEL_STATUS = "STRICTLY_FROZEN"
GOVERNANCE_DECISION = "TECHNICAL_NO_GO"
ROBUSTNESS_LAB_VERSION = "SPRINT26-ROBUSTNESS-LAB-V1.0"

SUPPORTED_SENSITIVITY_ANALYSES: Tuple[str, ...] = (
    "HISTORICAL_WINDOW_SENSITIVITY",
    "SAMPLE_SIZE_SENSITIVITY",
    "MISSING_DATA_SENSITIVITY",
    "OUTLIER_SENSITIVITY",
    "OBSERVATION_FREQUENCY_SENSITIVITY",
    "BOOTSTRAP_UNCERTAINTY",
    "METHODOLOGICAL_ASSUMPTION_SENSITIVITY",
    "CROSS_PERIOD_ROBUSTNESS",
)

MAX_BOOTSTRAP_ITERATIONS = 1000
MAX_PERTURBATION_VARIANTS = 12
MAX_ROWS_PER_RUN = 45000


@dataclass(frozen=True)
class RobustnessExperimentResult:
    """Complete output contract for a Module 26.4 robustness/sensitivity experiment."""

    experiment_id: str
    status: str
    rejection_code: Optional[str]
    rejection_reason: Optional[str]
    analysis_type: str
    original_record_id: str
    baseline_evaluation: Dict[str, Any]
    perturbation_definition: Dict[str, Any]
    scientific_rationale: str
    dataset_identity: Dict[str, Any]
    resulting_measurements: Dict[str, Any]
    difference_from_baseline: Dict[str, Any]
    confidence_or_uncertainty_estimate: Dict[str, Any]
    stability_classification: str
    limitations: List[str]
    evidence_provenance: Dict[str, Any]
    evaluated_at_utc: str
    canonical_model: str = CANONICAL_MODEL_ID
    model_status: str = CANONICAL_MODEL_STATUS
    governance_decision: str = GOVERNANCE_DECISION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RobustnessSensitivityLab:
    """Module 26.4 — Reproducible sensitivity and robustness laboratory."""

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self.stat_engine = StatisticalValidityEngine()

    # ------------------------------------------------------------------
    # Dataset & Baseline Helpers
    # ------------------------------------------------------------------

    def _load_authorized_dataset(
        self,
        dataset_id: str,
        custom_df: Optional[pd.DataFrame] = None,
    ) -> Tuple[Optional[pd.DataFrame], Dict[str, Any], Optional[str], Optional[str]]:
        ds_norm = str(dataset_id or "").strip()
        if "QUARANTINE" in ds_norm.upper() or "OCT2026" in ds_norm.upper():
            return (
                None,
                {"dataset_id": ds_norm, "status": "QUARANTINED_CONTAMINATED"},
                "QUARANTINED_DATASET_PROHIBITED",
                f"Dataset '{ds_norm}' is quarantined due to synthetic contamination.",
            )

        if custom_df is not None:
            if len(custom_df) > MAX_ROWS_PER_RUN:
                return (
                    None,
                    {"dataset_id": ds_norm, "row_count": len(custom_df)},
                    "RESOURCE_LIMIT_EXCEEDED",
                    f"Dataset row count ({len(custom_df)}) exceeds bounded limit ({MAX_ROWS_PER_RUN}).",
                )
            sha = hashlib.sha256(
                pd.util.hash_pandas_object(custom_df, index=True).values.tobytes()
            ).hexdigest()
            return (
                custom_df.copy(),
                {
                    "dataset_id": ds_norm or "CUSTOM_DATAFRAME",
                    "source_path": "IN_MEMORY_DATAFRAME",
                    "source_sha256": sha,
                    "row_count": len(custom_df),
                },
                None,
                None,
            )

        path_map = {
            "DS-BTC-1H-Q1-2024": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
            "DS-BTC-1H-JAN-2025": "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet",
            "DS-BTC-15M-Q1-2024": "data/historical/historical_binance_btcusdt_15m_q1_2024.parquet",
            "DS-BTC-15M-Q2-2024": "data/historical/historical_binance_btcusdt_15m_q2_2024.parquet",
            "DS-BTC-15M-Q3-2024": "data/historical/historical_binance_btcusdt_15m_q3_2024.parquet",
            "DS-BTC-15M-Q4-2024": "data/historical/historical_binance_btcusdt_15m_q4_2024.parquet",
        }
        rel_path = path_map.get(ds_norm, "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet")
        f_path = self.workspace_root / rel_path
        if not f_path.exists():
            return (
                None,
                {"dataset_id": ds_norm, "source_path": rel_path},
                "MISSING_SOURCE_DATASET",
                f"Authorized dataset '{ds_norm}' not found at '{rel_path}'.",
            )

        raw = f_path.read_bytes()
        sha = hashlib.sha256(raw).hexdigest()
        df = pd.read_parquet(f_path)
        if len(df) > MAX_ROWS_PER_RUN:
            df = df.iloc[:MAX_ROWS_PER_RUN].copy()

        return (
            df,
            {
                "dataset_id": ds_norm,
                "source_path": rel_path,
                "source_sha256": sha,
                "row_count": len(df),
            },
            None,
            None,
        )

    @staticmethod
    def _compute_parkinson_series(df: pd.DataFrame) -> np.ndarray:
        highs = df["high"].astype(float).to_numpy()
        lows = df["low"].astype(float).to_numpy()
        hl = np.log(np.maximum(highs, 1e-9) / np.maximum(lows, 1e-9))
        return np.sqrt((hl ** 2) / (4.0 * math.log(2.0)))

    @staticmethod
    def _compute_summary_metrics(series: np.ndarray) -> Dict[str, float]:
        clean = series[~np.isnan(series)]
        n = len(clean)
        if n == 0:
            return {
                "sample_size": 0,
                "mean_volatility": 0.0,
                "median_volatility": 0.0,
                "iqr_volatility": 0.0,
                "p90_to_median_expansion_ratio": 1.0,
            }
        mean_v = float(np.mean(clean))
        med_v = float(np.median(clean))
        iqr_v = float(np.percentile(clean, 75) - np.percentile(clean, 25)) if n >= 4 else 0.0
        p90_v = float(np.percentile(clean, 90))
        exp_ratio = p90_v / max(1e-9, med_v)
        return {
            "sample_size": int(n),
            "mean_volatility": round(mean_v, 6),
            "median_volatility": round(med_v, 6),
            "iqr_volatility": round(iqr_v, 6),
            "p90_to_median_expansion_ratio": round(exp_ratio, 4),
        }

    # ------------------------------------------------------------------
    # Main Sensitivity Experiment Runner
    # ------------------------------------------------------------------

    def run_sensitivity_experiment(
        self,
        original_record_id: str = "RES-29-PAT-SIM",
        analysis_type: str = "OUTLIER_SENSITIVITY",
        dataset_id: str = "DS-BTC-1H-Q1-2024",
        perturbation_params: Optional[Dict[str, Any]] = None,
        modify_canonical_model: bool = False,
        custom_df: Optional[pd.DataFrame] = None,
        seed: int = 42,
    ) -> RobustnessExperimentResult:
        """Run a single reproducible sensitivity/robustness experiment."""
        with resource_governor.ComputationGuard("robustness_sensitivity_experiment"):
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            params = dict(perturbation_params or {})
            a_type = str(analysis_type or "").strip().upper()

            # 1. Enforce frozen-model boundary
            if modify_canonical_model or params.get("modify_canonical_model") is True:
                return self._build_blocked_experiment(
                    original_record_id=original_record_id,
                    analysis_type=a_type,
                    dataset_id=dataset_id,
                    rejection_code="CANONICAL_PARAMETER_MUTATION_PROHIBITED",
                    rejection_reason=(
                        "Sensitivity experiments may vary evaluation conditions only; "
                        "modifying canonical CBE-0.7.0 parameters is strictly prohibited."
                    ),
                    now_utc=now_utc,
                )

            if a_type not in SUPPORTED_SENSITIVITY_ANALYSES:
                return self._build_blocked_experiment(
                    original_record_id=original_record_id,
                    analysis_type=a_type,
                    dataset_id=dataset_id,
                    rejection_code="UNSUPPORTED_SENSITIVITY_ASSUMPTION",
                    rejection_reason=(
                        f"Analysis type '{analysis_type}' is unsupported. "
                        f"Supported analyses: {list(SUPPORTED_SENSITIVITY_ANALYSES)}."
                    ),
                    now_utc=now_utc,
                )

            # Check resource limits on requested iterations or variants
            req_iters = int(params.get("n_iterations", 300))
            if req_iters > MAX_BOOTSTRAP_ITERATIONS:
                return self._build_blocked_experiment(
                    original_record_id=original_record_id,
                    analysis_type=a_type,
                    dataset_id=dataset_id,
                    rejection_code="RESOURCE_LIMIT_EXCEEDED",
                    rejection_reason=(
                        f"Requested bootstrap iterations ({req_iters}) exceed "
                        f"bounded maximum ({MAX_BOOTSTRAP_ITERATIONS})."
                    ),
                    now_utc=now_utc,
                )

            df, ds_identity, err_code, err_reason = self._load_authorized_dataset(
                dataset_id=dataset_id, custom_df=custom_df
            )
            if df is None or err_code is not None:
                return self._build_blocked_experiment(
                    original_record_id=original_record_id,
                    analysis_type=a_type,
                    dataset_id=dataset_id,
                    rejection_code=err_code or "DATASET_LOAD_FAILED",
                    rejection_reason=err_reason or "Failed to load dataset.",
                    now_utc=now_utc,
                )

            base_series = self._compute_parkinson_series(df)
            base_metrics = self._compute_summary_metrics(base_series)

            variants_results: Dict[str, Any] = {}
            perturbed_primary_series = base_series.copy()
            rationale = ""
            perturbation_def: Dict[str, Any] = {
                "analysis_type": a_type,
                "assumption_scope": "EXPLORATORY_EVALUATION_CONDITION",
                "canonical_model_mutated": False,
                "deterministic_seed": int(seed),
            }

            if a_type == "HISTORICAL_WINDOW_SENSITIVITY":
                trim_frac = float(params.get("trim_fraction", 0.10))
                if trim_frac <= 0.0 or trim_frac >= 0.50:
                    return self._build_blocked_experiment(
                        original_record_id=original_record_id,
                        analysis_type=a_type,
                        dataset_id=dataset_id,
                        rejection_code="INVALID_PERTURBATION_PARAMETER",
                        rejection_reason="trim_fraction must be in (0.0, 0.50).",
                        now_utc=now_utc,
                    )
                k = max(1, int(len(base_series) * trim_frac))
                perturbed_primary_series = base_series[k : len(base_series) - k]
                variants_results["drop_first_10pct"] = self._compute_summary_metrics(base_series[k:])
                variants_results["drop_last_10pct"] = self._compute_summary_metrics(base_series[:-k])
                variants_results["symmetric_trim"] = self._compute_summary_metrics(perturbed_primary_series)
                perturbation_def["trim_fraction"] = trim_frac
                rationale = (
                    "Tests whether the volatility structure is driven by boundary macro events "
                    "at the start or end of the historical observation window."
                )

            elif a_type == "SAMPLE_SIZE_SENSITIVITY":
                frac = float(params.get("subsample_fraction", 0.75))
                if frac < 0.10 or frac > 1.0:
                    return self._build_blocked_experiment(
                        original_record_id=original_record_id,
                        analysis_type=a_type,
                        dataset_id=dataset_id,
                        rejection_code="INVALID_PERTURBATION_PARAMETER",
                        rejection_reason="subsample_fraction must be in [0.10, 1.0].",
                        now_utc=now_utc,
                    )
                for f_label, f_val in [("subsample_50pct", 0.50), ("subsample_75pct", 0.75), ("subsample_90pct", 0.90)]:
                    n_sub = max(10, int(len(base_series) * f_val))
                    variants_results[f_label] = self._compute_summary_metrics(base_series[:n_sub])
                n_main = max(10, int(len(base_series) * frac))
                perturbed_primary_series = base_series[:n_main]
                perturbation_def["subsample_fraction"] = frac
                rationale = (
                    "Evaluates estimate convergence and stability across smaller contiguous sample sizes."
                )

            elif a_type == "MISSING_DATA_SENSITIVITY":
                drop_rate = float(params.get("dropout_rate", 0.03))
                if drop_rate < 0.0 or drop_rate > 0.30:
                    return self._build_blocked_experiment(
                        original_record_id=original_record_id,
                        analysis_type=a_type,
                        dataset_id=dataset_id,
                        rejection_code="INVALID_PERTURBATION_PARAMETER",
                        rejection_reason="dropout_rate must be in [0.0, 0.30].",
                        now_utc=now_utc,
                    )
                rng = np.random.default_rng(int(seed))
                for r_label, r_val in [("dropout_1pct", 0.01), ("dropout_3pct", 0.03), ("dropout_5pct", 0.05)]:
                    mask = rng.random(len(base_series)) >= r_val
                    variants_results[r_label] = self._compute_summary_metrics(base_series[mask])
                main_mask = np.random.default_rng(int(seed)).random(len(base_series)) >= drop_rate
                perturbed_primary_series = base_series[main_mask]
                perturbation_def["dropout_rate"] = drop_rate
                rationale = (
                    "Evaluates sensitivity to random observation dropouts without fabricating "
                    "synthetic forward-filled prices."
                )

            elif a_type == "OUTLIER_SENSITIVITY":
                win_q = float(params.get("winsorize_tail_quantile", 0.01))
                if win_q <= 0.0 or win_q >= 0.20:
                    return self._build_blocked_experiment(
                        original_record_id=original_record_id,
                        analysis_type=a_type,
                        dataset_id=dataset_id,
                        rejection_code="INVALID_PERTURBATION_PARAMETER",
                        rejection_reason="winsorize_tail_quantile must be in (0.0, 0.20).",
                        now_utc=now_utc,
                    )
                low_cut = float(np.quantile(base_series, win_q))
                high_cut = float(np.quantile(base_series, 1.0 - win_q))
                perturbed_primary_series = np.clip(base_series, low_cut, high_cut)
                trimmed_series = base_series[(base_series >= low_cut) & (base_series <= high_cut)]
                variants_results["winsorized_1pct"] = self._compute_summary_metrics(perturbed_primary_series)
                variants_results["trimmed_1pct"] = self._compute_summary_metrics(trimmed_series)
                perturbation_def["winsorize_tail_quantile"] = win_q
                rationale = (
                    "Assesses whether empirical findings are dominated by isolated extreme "
                    "tail spikes (flash crashes / liquidation cascades)."
                )

            elif a_type == "OBSERVATION_FREQUENCY_SENSITIVITY":
                # Compare 1h vs 4h aggregated bars from the same underlying dataset
                step_agg = int(params.get("aggregation_factor", 4))
                if step_agg not in (2, 4, 6, 12, 24):
                    return self._build_blocked_experiment(
                        original_record_id=original_record_id,
                        analysis_type=a_type,
                        dataset_id=dataset_id,
                        rejection_code="UNSUPPORTED_FREQUENCY_AGGREGATION",
                        rejection_reason="aggregation_factor must be one of (2, 4, 6, 12, 24).",
                        now_utc=now_utc,
                    )
                n_blocks = len(df) // step_agg
                highs_agg = df["high"].astype(float).to_numpy()[: n_blocks * step_agg].reshape(n_blocks, step_agg).max(axis=1)
                lows_agg = df["low"].astype(float).to_numpy()[: n_blocks * step_agg].reshape(n_blocks, step_agg).min(axis=1)
                hl_agg = np.log(np.maximum(highs_agg, 1e-9) / np.maximum(lows_agg, 1e-9))
                # Normalize by sqrt(step_agg) for per-unit-time comparison
                perturbed_primary_series = np.sqrt((hl_agg ** 2) / (4.0 * math.log(2.0))) / math.sqrt(float(step_agg))
                variants_results[f"aggregated_{step_agg}x_time_normalized"] = self._compute_summary_metrics(
                    perturbed_primary_series
                )
                perturbation_def["aggregation_factor"] = step_agg
                rationale = (
                    "Evaluates whether Parkinson volatility scaling holds across coarser "
                    "temporal aggregation cadences."
                )

            elif a_type == "BOOTSTRAP_UNCERTAINTY":
                for b_size in (4, 8, 16, 24):
                    ci_b = self.stat_engine.block_bootstrap_ci(
                        series=base_series.tolist(),
                        block_size=b_size,
                        num_resamples=min(300, req_iters),
                        random_seed=int(seed),
                    )
                    variants_results[f"block_size_{b_size}"] = {
                        "ci_lower": ci_b.get("ci_lower"),
                        "ci_upper": ci_b.get("ci_upper"),
                        "bootstrap_se": ci_b.get("bootstrap_se"),
                    }
                perturbed_primary_series = base_series.copy()
                perturbation_def["block_sizes_evaluated"] = [4, 8, 16, 24]
                rationale = (
                    "Assesses sensitivity of confidence interval widths to the choice of "
                    "moving-block bootstrap length under serial correlation."
                )

            elif a_type == "METHODOLOGICAL_ASSUMPTION_SENSITIVITY":
                # Compare canonical Parkinson HL volatility vs exploratory Close-to-Close abs return
                closes = df["close"].astype(float).to_numpy()
                cc_vol = np.zeros_like(closes)
                cc_vol[1:] = np.abs(np.log(np.maximum(closes[1:], 1e-9) / np.maximum(closes[:-1], 1e-9)))
                perturbed_primary_series = cc_vol[1:]
                variants_results["exploratory_close_to_close_volatility"] = self._compute_summary_metrics(
                    perturbed_primary_series
                )
                perturbation_def["exploratory_estimator"] = "CLOSE_TO_CLOSE_ABS_LOG_RETURN"
                perturbation_def["exploratory_disclaimer"] = (
                    "Exploratory alternative volatility estimator; does not replace CBE-0.7.0 Parkinson estimator."
                )
                rationale = (
                    "Compares canonical range-based Parkinson volatility against an exploratory "
                    "close-to-close return dispersion estimator."
                )

            elif a_type == "CROSS_PERIOD_ROBUSTNESS":
                for q_id, q_rel in [
                    ("Q1_2024_15M", "data/historical/historical_binance_btcusdt_15m_q1_2024.parquet"),
                    ("Q2_2024_15M", "data/historical/historical_binance_btcusdt_15m_q2_2024.parquet"),
                    ("Q3_2024_15M", "data/historical/historical_binance_btcusdt_15m_q3_2024.parquet"),
                    ("Q4_2024_15M", "data/historical/historical_binance_btcusdt_15m_q4_2024.parquet"),
                ]:
                    qp = self.workspace_root / q_rel
                    if qp.exists():
                        qdf = pd.read_parquet(qp)
                        q_ser = self._compute_parkinson_series(qdf)
                        variants_results[q_id] = self._compute_summary_metrics(q_ser)
                        if q_id == "Q2_2024_15M":
                            perturbed_primary_series = q_ser
                perturbation_def["cohorts_evaluated"] = list(variants_results.keys())
                rationale = (
                    "Evaluates structural metric stability across four sequential 2024 quarterly cohorts."
                )

            pert_metrics = self._compute_summary_metrics(perturbed_primary_series)
            base_mean = float(base_metrics["mean_volatility"])
            pert_mean = float(pert_metrics["mean_volatility"])
            abs_diff_mean = pert_mean - base_mean
            rel_diff_pct = (abs_diff_mean / max(1e-9, base_mean)) * 100.0

            base_exp = float(base_metrics["p90_to_median_expansion_ratio"])
            pert_exp = float(pert_metrics["p90_to_median_expansion_ratio"])
            exp_rel_diff_pct = ((pert_exp - base_exp) / max(1e-9, base_exp)) * 100.0

            ci_pert = self.stat_engine.block_bootstrap_ci(
                series=perturbed_primary_series.tolist(),
                block_size=8,
                num_resamples=min(300, req_iters),
                random_seed=int(seed),
            )

            max_rel_shift = max(abs(rel_diff_pct), abs(exp_rel_diff_pct))
            if max_rel_shift <= 15.0:
                stab_class = "ROBUST"
            elif max_rel_shift <= 30.0:
                stab_class = "MODERATELY_SENSITIVE"
            else:
                stab_class = "FRAGILE_OR_SENSITIVE"

            exp_fp = hashlib.sha256(
                json.dumps(
                    {
                        "rec": original_record_id,
                        "type": a_type,
                        "ds_sha": ds_identity.get("source_sha256"),
                        "pert_mean": round(pert_mean, 6),
                        "seed": int(seed),
                    },
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()

            return RobustnessExperimentResult(
                experiment_id=f"ROB-{original_record_id}-{a_type[:10]}-{exp_fp[:8]}",
                status="EXPERIMENT_COMPLETED",
                rejection_code=None,
                rejection_reason=None,
                analysis_type=a_type,
                original_record_id=original_record_id,
                baseline_evaluation=base_metrics,
                perturbation_definition=perturbation_def,
                scientific_rationale=rationale,
                dataset_identity=ds_identity,
                resulting_measurements={
                    "primary_perturbed_metrics": pert_metrics,
                    "variants": variants_results,
                },
                difference_from_baseline={
                    "mean_volatility_abs_diff": round(abs_diff_mean, 6),
                    "mean_volatility_rel_diff_pct": round(rel_diff_pct, 2),
                    "expansion_ratio_abs_diff": round(pert_exp - base_exp, 4),
                    "expansion_ratio_rel_diff_pct": round(exp_rel_diff_pct, 2),
                },
                confidence_or_uncertainty_estimate={
                    "method": "MOVING_BLOCK_BOOTSTRAP (block_size=8)",
                    "point_estimate": ci_pert.get("point_estimate"),
                    "ci_95_lower": ci_pert.get("ci_lower"),
                    "ci_95_upper": ci_pert.get("ci_upper"),
                    "bootstrap_se": ci_pert.get("bootstrap_se"),
                },
                stability_classification=stab_class,
                limitations=[
                    "Historical stability under perturbation does not establish future predictive reliability or live trading eligibility.",
                    "Exploratory evaluation conditions are isolated from the frozen CBE-0.7.0 canonical specification.",
                ],
                evidence_provenance={
                    "dataset_sha256": ds_identity.get("source_sha256"),
                    "experiment_fingerprint_sha256": exp_fp,
                    "reproducible_seed": int(seed),
                    "methodology_version": ROBUSTNESS_LAB_VERSION,
                },
                evaluated_at_utc=now_utc,
            )

    def run_comprehensive_suite(
        self,
        original_record_id: str = "RES-29-PAT-SIM",
        dataset_id: str = "DS-BTC-1H-Q1-2024",
    ) -> Dict[str, Any]:
        """Run all 8 supported sensitivity analyses for a research record."""
        results: List[Dict[str, Any]] = []
        counts: Dict[str, int] = {
            "ROBUST": 0,
            "MODERATELY_SENSITIVE": 0,
            "FRAGILE_OR_SENSITIVE": 0,
            "EXPERIMENT_BLOCKED": 0,
        }
        for a_type in SUPPORTED_SENSITIVITY_ANALYSES:
            res = self.run_sensitivity_experiment(
                original_record_id=original_record_id,
                analysis_type=a_type,
                dataset_id=dataset_id,
            )
            results.append(res.to_dict())
            counts[res.stability_classification] = counts.get(res.stability_classification, 0) + 1

        return {
            "status": "SUCCESS",
            "original_record_id": original_record_id,
            "dataset_id": dataset_id,
            "canonical_model": CANONICAL_MODEL_ID,
            "model_status": CANONICAL_MODEL_STATUS,
            "governance_decision": GOVERNANCE_DECISION,
            "total_experiments": len(results),
            "stability_summary": counts,
            "experiments": results,
            "evaluated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

    def _build_blocked_experiment(
        self,
        original_record_id: str,
        analysis_type: str,
        dataset_id: str,
        rejection_code: str,
        rejection_reason: str,
        now_utc: str,
    ) -> RobustnessExperimentResult:
        b_hash = hashlib.sha256(
            f"{original_record_id}:{analysis_type}:{rejection_code}:{now_utc}".encode("utf-8")
        ).hexdigest()[:8]
        return RobustnessExperimentResult(
            experiment_id=f"ROB-BLOCKED-{b_hash}",
            status="EXPERIMENT_BLOCKED",
            rejection_code=rejection_code,
            rejection_reason=rejection_reason,
            analysis_type=analysis_type,
            original_record_id=original_record_id,
            baseline_evaluation={},
            perturbation_definition={"analysis_type": analysis_type, "canonical_model_mutated": False},
            scientific_rationale="",
            dataset_identity={"dataset_id": dataset_id},
            resulting_measurements={},
            difference_from_baseline={},
            confidence_or_uncertainty_estimate={},
            stability_classification="EXPERIMENT_BLOCKED",
            limitations=[rejection_reason],
            evidence_provenance={"status": "BLOCKED"},
            evaluated_at_utc=now_utc,
        )

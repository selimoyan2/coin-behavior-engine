"""CBE-0.8.0 Canonical Scientific Metrics Engine.

Single, centralized calculation engine that computes all evaluation metrics
from raw predictions, intervals, market states, and realized outcomes.
Ensures that all JSON reports and Markdown summaries originate from a single,
authoritative metrics computation with deterministic random seeds.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd


@dataclass
class PointMetrics:
    sample_count: int
    mae: float
    rmse: float
    pearson_r: float
    spearman_rho: float
    mae_se: float
    rmse_se: float


@dataclass
class IntervalMetrics:
    coverage_80: float
    coverage_95: float
    mean_width_80: float
    mean_width_95: float
    relative_width_80: float
    relative_width_95: float
    winkler_80: float
    winkler_95: float
    sample_count: int


@dataclass
class StateDistributionMetrics:
    counts: Dict[str, int]
    percentages: Dict[str, float]
    total_samples: int


@dataclass
class HorizonMetrics:
    horizon: str
    sample_count: int
    point: PointMetrics
    intervals_marginal: IntervalMetrics
    intervals_by_state: Dict[str, IntervalMetrics]
    non_overlapping: Dict[str, Any]
    bootstrap_comparison: Dict[str, Any]


class CanonicalMetricsEngine:
    """Authoritative calculator for prospective and retrospective model evaluation metrics."""

    HORIZON_STEPS = {
        "1h": 12,
        "4h": 48,
        "24h": 288,
    }

    @staticmethod
    def compute_sample_counts(
        total_rows: int,
        valid_features: int,
        valid_targets: int,
        eligible_samples: int,
        excluded_reasons: Optional[Dict[str, int]] = None,
    ) -> Dict[str, Any]:
        """Compute sample accounting."""
        excluded = total_rows - eligible_samples
        return {
            "total_rows": int(total_rows),
            "valid_features": int(valid_features),
            "valid_targets": int(valid_targets),
            "eligible_samples": int(eligible_samples),
            "excluded_samples": int(excluded),
            "excluded_reasons": excluded_reasons or {},
        }

    @staticmethod
    def compute_state_distribution(states: List[str] | np.ndarray) -> StateDistributionMetrics:
        """Compute exact market state counts and percentages summing to 100.0%."""
        states_arr = np.asarray(states)
        total = len(states_arr)
        if total == 0:
            return StateDistributionMetrics(counts={}, percentages={}, total_samples=0)

        unique, counts = np.unique(states_arr, return_counts=True)
        counts_dict = {str(k): int(v) for k, v in zip(unique, counts)}
        pcts_dict = {str(k): round(float(v) / total * 100.0, 4) for k, v in zip(unique, counts)}

        return StateDistributionMetrics(
            counts=counts_dict,
            percentages=pcts_dict,
            total_samples=total,
        )

    @staticmethod
    def compute_point_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> PointMetrics:
        """Compute point forecast metrics with standard errors."""
        y_t = np.asarray(y_true, dtype=np.float64)
        y_p = np.asarray(y_pred, dtype=np.float64)

        mask = np.isfinite(y_t) & np.isfinite(y_p)
        y_t = y_t[mask]
        y_p = y_p[mask]
        n = len(y_t)
        if n == 0:
            return PointMetrics(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)

        errors = y_p - y_t
        abs_errors = np.abs(errors)
        sq_errors = errors ** 2

        mae = float(np.mean(abs_errors))
        rmse = float(np.sqrt(np.mean(sq_errors)))

        mae_se = float(np.std(abs_errors, ddof=1) / np.sqrt(n)) if n > 1 else 0.0
        rmse_se = float(np.std(sq_errors, ddof=1) / (2.0 * rmse * np.sqrt(n))) if (n > 1 and rmse > 0) else 0.0

        # Pearson correlation
        if n > 2 and np.std(y_t) > 1e-12 and np.std(y_p) > 1e-12:
            r = float(np.corrcoef(y_t, y_p)[0, 1])
            # Spearman rank correlation
            rank_t = pd.Series(y_t).rank().values
            rank_p = pd.Series(y_p).rank().values
            rho = float(np.corrcoef(rank_t, rank_p)[0, 1])
        else:
            r = 0.0
            rho = 0.0

        return PointMetrics(
            sample_count=n,
            mae=mae,
            rmse=rmse,
            pearson_r=r,
            spearman_rho=rho,
            mae_se=mae_se,
            rmse_se=rmse_se,
        )

    @staticmethod
    def compute_winkler_score(y_true: np.ndarray, lower: np.ndarray, upper: np.ndarray, alpha: float) -> float:
        """Compute interval Winkler score for (1 - alpha) coverage interval."""
        n = len(y_true)
        if n == 0:
            return 0.0

        width = upper - lower
        penalty_lower = np.maximum(0.0, lower - y_true) * (2.0 / alpha)
        penalty_upper = np.maximum(0.0, y_true - upper) * (2.0 / alpha)
        score = width + penalty_lower + penalty_upper
        return float(np.mean(score))

    @classmethod
    def compute_interval_metrics(
        cls,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        lower_80: np.ndarray,
        upper_80: np.ndarray,
        lower_95: np.ndarray,
        upper_95: np.ndarray,
    ) -> IntervalMetrics:
        """Compute empirical coverage, widths, relative widths, and Winkler scores."""
        y_t = np.asarray(y_true, dtype=np.float64)
        y_p = np.asarray(y_pred, dtype=np.float64)
        l80 = np.asarray(lower_80, dtype=np.float64)
        u80 = np.asarray(upper_80, dtype=np.float64)
        l95 = np.asarray(lower_95, dtype=np.float64)
        u95 = np.asarray(upper_95, dtype=np.float64)

        mask = np.isfinite(y_t) & np.isfinite(y_p) & np.isfinite(l80) & np.isfinite(u80) & np.isfinite(l95) & np.isfinite(u95)
        y_t, y_p = y_t[mask], y_p[mask]
        l80, u80 = l80[mask], u80[mask]
        l95, u95 = l95[mask], u95[mask]

        n = len(y_t)
        if n == 0:
            return IntervalMetrics(0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)

        cov_80 = float(np.mean((y_t >= l80) & (y_t <= u80)) * 100.0)
        cov_95 = float(np.mean((y_t >= l95) & (y_t <= u95)) * 100.0)

        w80 = u80 - l80
        w95 = u95 - l95
        mean_w80 = float(np.mean(w80))
        mean_w95 = float(np.mean(w95))

        mean_pred = float(np.mean(y_p)) if np.mean(y_p) > 1e-12 else 1.0
        rel_w80 = float(mean_w80 / mean_pred)
        rel_w95 = float(mean_w95 / mean_pred)

        wink_80 = cls.compute_winkler_score(y_t, l80, u80, alpha=0.20)
        wink_95 = cls.compute_winkler_score(y_t, l95, u95, alpha=0.05)

        return IntervalMetrics(
            coverage_80=cov_80,
            coverage_95=cov_95,
            mean_width_80=mean_w80,
            mean_width_95=mean_w95,
            relative_width_80=rel_w80,
            relative_width_95=rel_w95,
            winkler_80=wink_80,
            winkler_95=wink_95,
            sample_count=n,
        )

    @classmethod
    def compute_metrics_by_state(
        cls,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        lower_80: np.ndarray,
        upper_80: np.ndarray,
        lower_95: np.ndarray,
        upper_95: np.ndarray,
        states: np.ndarray,
    ) -> Dict[str, IntervalMetrics]:
        """Compute interval metrics conditioned on each unique market state."""
        states_arr = np.asarray(states)
        unique_states = np.unique(states_arr)
        results: Dict[str, IntervalMetrics] = {}

        for state in unique_states:
            mask = (states_arr == state)
            results[str(state)] = cls.compute_interval_metrics(
                y_true[mask],
                y_pred[mask],
                lower_80[mask],
                upper_80[mask],
                lower_95[mask],
                upper_95[mask],
            )
        return results

    @classmethod
    def compute_non_overlapping_metrics(
        cls,
        y_true: np.ndarray,
        y_pred: np.ndarray,
        horizon: str,
        lower_80: Optional[np.ndarray] = None,
        upper_80: Optional[np.ndarray] = None,
        lower_95: Optional[np.ndarray] = None,
        upper_95: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """Compute metrics on non-overlapping subsamples with step = horizon_steps."""
        step = cls.HORIZON_STEPS.get(horizon, 12)
        idx = np.arange(0, len(y_true), step)
        if len(idx) == 0:
            return {"step": step, "sample_count": 0}

        sub_yt = y_true[idx]
        sub_yp = y_pred[idx]
        pt = cls.compute_point_metrics(sub_yt, sub_yp)

        res: Dict[str, Any] = {
            "step": step,
            "sample_count": len(idx),
            "point": asdict(pt),
        }

        if lower_80 is not None and upper_80 is not None and lower_95 is not None and upper_95 is not None:
            itv = cls.compute_interval_metrics(
                sub_yt, sub_yp, lower_80[idx], upper_80[idx], lower_95[idx], upper_95[idx]
            )
            res["intervals"] = asdict(itv)

        return res

    @staticmethod
    def compute_paired_block_bootstrap(
        errors_cand: np.ndarray,
        errors_base: np.ndarray,
        block_size: int = 288,
        n_boot: int = 500,
        random_seed: int = 42,
    ) -> Dict[str, Any]:
        """Compute circular block bootstrap for paired MAE difference (cand - base).

        Uses fixed deterministic seed `rng = np.random.default_rng(seed)`.
        Negative delta_mae indicates candidate has lower MAE (improvement).
        """
        cand_loss = np.abs(errors_cand)
        base_loss = np.abs(errors_base)
        n = len(cand_loss)

        if n < block_size or n == 0:
            return {
                "n_samples": n,
                "delta_mae_mean": 0.0,
                "ci_95_lower": 0.0,
                "ci_95_upper": 0.0,
                "p_value": 1.0,
                "significant": False,
            }

        diff = cand_loss - base_loss
        obs_delta = float(np.mean(diff))

        # Circular block bootstrap
        rng = np.random.default_rng(random_seed)
        num_blocks = int(math.ceil(n / block_size))
        boot_deltas = np.empty(n_boot, dtype=np.float64)

        for b in range(n_boot):
            start_indices = rng.integers(0, n, size=num_blocks)
            sample_indices = []
            for s in start_indices:
                sample_indices.extend([(s + i) % n for i in range(block_size)])
            sample_indices = np.array(sample_indices[:n])
            boot_deltas[b] = np.mean(diff[sample_indices])

        ci_lower = float(np.percentile(boot_deltas, 2.5))
        ci_upper = float(np.percentile(boot_deltas, 97.5))

        # Two-tailed p-value
        p_val = float(2.0 * min(np.mean(boot_deltas >= 0.0), np.mean(boot_deltas <= 0.0)))
        p_val = min(1.0, max(0.0, p_val))
        significant = (ci_lower > 0.0 and ci_upper > 0.0) or (ci_lower < 0.0 and ci_upper < 0.0)

        return {
            "n_samples": n,
            "block_size": block_size,
            "n_boot": n_boot,
            "random_seed": random_seed,
            "delta_mae_mean": obs_delta,
            "ci_95_lower": ci_lower,
            "ci_95_upper": ci_upper,
            "p_value": p_val,
            "significant": bool(significant),
        }

    @staticmethod
    def aggregate_claims(claims_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate scientific claim registry ensuring strict summation invariant."""
        total = len(claims_list)
        status_counts = {
            "SUPPORTED": 0,
            "SUPPORTED_WITH_LIMITATIONS": 0,
            "REFUTED": 0,
            "NOT_VERIFIED": 0,
            "NOT_EVALUABLE": 0,
        }

        for c in claims_list:
            st = c.get("status", "NOT_VERIFIED")
            if st in status_counts:
                status_counts[st] += 1
            else:
                status_counts["NOT_VERIFIED"] += 1

        sum_statuses = sum(status_counts.values())
        assert sum_statuses == total, f"Claim status sum {sum_statuses} != total {total}"

        return {
            "total_claims": total,
            "status_counts": status_counts,
            "integrity_verified": True,
        }

    @staticmethod
    def aggregate_gates(gates_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate scientific gate evaluation list."""
        total = len(gates_list)
        passed = sum(1 for g in gates_list if g.get("status") == "PASS")
        failed = sum(1 for g in gates_list if g.get("status") == "FAIL")

        return {
            "total_gates": total,
            "gates_passed": passed,
            "gates_failed": failed,
            "pass_rate_pct": round(passed / total * 100.0, 2) if total > 0 else 0.0,
            "verdict": "READY_FOR_CANDIDATE_INTEGRATION" if (passed == total and total > 0) else "GATES_BLOCKED",
        }

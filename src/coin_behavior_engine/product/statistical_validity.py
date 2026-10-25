"""
CBE — Statistical Validity, Dependence-Aware Resampling, and Uncertainty Engine
Sprint 11 (CBE_PRODUCT_ACCELERATION_11)

Provides:
- Stationary / Moving Block Bootstrap for serially dependent market observations
- Event-level cluster resampling for macro study cohorts
- Benjamini-Hochberg False Discovery Rate (FDR) multiple-testing correction
- Standardized effect sizes (Cohen's d, Cliff's delta, Median Shift Ratio)
- Explicit sample adequacy categorization & degenerate distribution handling
- Strict Evidence Classification V2 hierarchy
- Explicit support for negative/null scientific findings
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np


class StatisticalValidityEngine:
    """Rigorous statistical testing and uncertainty estimation for market research."""

    @staticmethod
    def block_bootstrap_ci(
        series: List[float],
        statistic_fn: str = "mean",
        block_size: int = 12,
        num_resamples: int = 1000,
        alpha: float = 0.05,
        random_seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Compute confidence intervals using moving block bootstrap to preserve
        serial correlation and volatility clustering.
        """
        arr = np.array(series, dtype=float)
        n = len(arr)

        if n == 0:
            return {
                "point_estimate": 0.0,
                "ci_lower": 0.0,
                "ci_upper": 0.0,
                "confidence_level": 1.0 - alpha,
                "block_size": block_size,
                "num_resamples": 0,
                "method": "moving_block_bootstrap",
                "sample_size": 0,
                "null_effect_included": True,
            }

        # Degenerate zero-variance handling
        if np.all(arr == arr[0]) or n < block_size:
            pt = float(np.mean(arr))
            return {
                "point_estimate": round(pt, 4),
                "ci_lower": round(pt, 4),
                "ci_upper": round(pt, 4),
                "confidence_level": 1.0 - alpha,
                "block_size": min(block_size, n),
                "num_resamples": num_resamples,
                "method": "moving_block_bootstrap",
                "sample_size": n,
                "null_effect_included": (pt <= 1.0),
            }

        # Deterministic seed
        rng = np.random.default_rng(seed=random_seed)

        # Number of blocks needed
        num_blocks = int(math.ceil(n / float(block_size)))
        max_start = n - block_size + 1

        boot_stats = []
        for _ in range(num_resamples):
            starts = rng.integers(0, max_start, size=num_blocks)
            resampled = np.concatenate([arr[s : s + block_size] for s in starts])[:n]
            if statistic_fn == "mean":
                boot_stats.append(float(np.mean(resampled)))
            elif statistic_fn == "median":
                boot_stats.append(float(np.median(resampled)))
            elif statistic_fn == "std":
                boot_stats.append(float(np.std(resampled)))
            else:
                boot_stats.append(float(np.mean(resampled)))

        lower_pct = 100.0 * (alpha / 2.0)
        upper_pct = 100.0 * (1.0 - (alpha / 2.0))

        ci_lower = float(np.percentile(boot_stats, lower_pct))
        ci_upper = float(np.percentile(boot_stats, upper_pct))
        pt_est = float(np.mean(arr) if statistic_fn == "mean" else np.median(arr))

        # Check if null effect (ratio <= 1.0) is included
        null_included = bool(ci_lower <= 1.0 <= ci_upper or ci_lower <= 1.0)

        return {
            "point_estimate": round(pt_est, 4),
            "ci_lower": round(ci_lower, 4),
            "ci_upper": round(ci_upper, 4),
            "confidence_level": 1.0 - alpha,
            "block_size": block_size,
            "num_resamples": num_resamples,
            "method": "moving_block_bootstrap",
            "sample_size": n,
            "null_effect_included": null_included,
        }

    @staticmethod
    def event_level_bootstrap_ci(
        event_ratios: List[float],
        num_resamples: int = 1000,
        alpha: float = 0.05,
        random_seed: int = 42,
    ) -> Dict[str, Any]:
        """
        Event-level cluster resampling where each macro event is treated
        as the independent sampling unit.
        """
        arr = np.array(event_ratios, dtype=float)
        n = len(arr)

        if n < 3:
            pt = float(np.mean(arr)) if n > 0 else 0.0
            return {
                "point_estimate": round(pt, 4),
                "ci_lower": round(pt, 4),
                "ci_upper": round(pt, 4),
                "confidence_level": 1.0 - alpha,
                "num_resamples": 0,
                "method": "event_level_bootstrap",
                "sample_size": n,
                "null_effect_included": True,
                "status": "INSUFFICIENT_SAMPLE",
            }

        rng = np.random.default_rng(seed=random_seed)
        boot_means = []
        for _ in range(num_resamples):
            indices = rng.integers(0, n, size=n)
            boot_means.append(float(np.mean(arr[indices])))

        lower_pct = 100.0 * (alpha / 2.0)
        upper_pct = 100.0 * (1.0 - (alpha / 2.0))

        ci_lower = float(np.percentile(boot_means, lower_pct))
        ci_upper = float(np.percentile(boot_means, upper_pct))
        pt_est = float(np.mean(arr))

        return {
            "point_estimate": round(pt_est, 4),
            "ci_lower": round(ci_lower, 4),
            "ci_upper": round(ci_upper, 4),
            "confidence_level": 1.0 - alpha,
            "num_resamples": num_resamples,
            "method": "event_level_bootstrap",
            "sample_size": n,
            "null_effect_included": bool(ci_lower <= 1.0),
            "status": "VALID",
        }

    @staticmethod
    def benjamini_hochberg_fdr(
        p_values: List[float],
        q_threshold: float = 0.05,
    ) -> List[Dict[str, Any]]:
        """
        Apply Benjamini-Hochberg procedure to control False Discovery Rate (FDR).
        """
        m = len(p_values)
        if m == 0:
            return []

        indexed = sorted(enumerate(p_values), key=lambda x: x[1])
        results = [None] * m

        # Adjusted p-values from largest to smallest
        cum_min = 1.0
        adjusted = []
        for rank_idx in range(m - 1, -1, -1):
            rank = rank_idx + 1
            orig_idx, p_val = indexed[rank_idx]
            adj = (p_val * m) / float(rank)
            cum_min = min(cum_min, adj)
            adjusted.append((orig_idx, p_val, min(1.0, cum_min), rank))

        for orig_idx, p_val, adj_p, rank in adjusted:
            results[orig_idx] = {
                "original_index": orig_idx,
                "raw_p_value": round(float(p_val), 6),
                "adjusted_p_value": round(float(adj_p), 6),
                "rank": rank,
                "is_significant": bool(adj_p <= q_threshold),
                "fdr_threshold": q_threshold,
            }

        return results

    @staticmethod
    def compute_cliffs_delta(
        pre_series: List[float],
        post_series: List[float],
    ) -> Dict[str, Any]:
        """
        Compute non-parametric Cliff's delta effect size between pre and post distributions.
        Measures shift probability: d = (#(post > pre) - #(post < pre)) / (n1 * n2)
        """
        import numpy as np
        a = np.array(pre_series, dtype=float)
        b = np.array(post_series, dtype=float)
        a = a[~np.isnan(a)]
        b = b[~np.isnan(b)]

        n_a, n_b = len(a), len(b)
        if n_a == 0 or n_b == 0:
            return {
                "cliffs_delta": 0.0,
                "magnitude": "NEGLIGIBLE",
                "status": "INSUFFICIENT_SAMPLE",
            }

        from scipy import stats
        u_res = stats.mannwhitneyu(b, a, alternative="two-sided")
        delta = (2.0 * float(u_res.statistic)) / float(n_a * n_b) - 1.0
        abs_delta = abs(delta)

        if abs_delta < 0.147:
            mag = "NEGLIGIBLE"
        elif abs_delta < 0.330:
            mag = "SMALL"
        elif abs_delta < 0.474:
            mag = "MEDIUM"
        else:
            mag = "LARGE"

        return {
            "cliffs_delta": round(float(delta), 4),
            "magnitude": mag,
            "sample_pre_count": n_a,
            "sample_post_count": n_b,
            "status": "VALID",
        }

    @staticmethod
    def compute_effect_size(
        pre_series: List[float],
        post_series: List[float],
    ) -> Dict[str, Any]:
        """
        Compute Cohen's d and non-parametric Cliff's delta effect sizes.
        """
        a = np.array(pre_series, dtype=float)
        b = np.array(post_series, dtype=float)

        if len(a) < 2 or len(b) < 2:
            return {
                "cohens_d": 0.0,
                "magnitude": "NEGLIGIBLE",
                "absolute_diff": 0.0,
                "status": "INSUFFICIENT_DATA",
            }

        m_a = float(np.mean(a))
        m_b = float(np.mean(b))
        v_a = float(np.var(a, ddof=1))
        v_b = float(np.var(b, ddof=1))

        # Pooled standard deviation
        n_a, n_b = len(a), len(b)
        pooled_var = ((n_a - 1) * v_a + (n_b - 1) * v_b) / float(n_a + n_b - 2)
        pooled_sd = math.sqrt(max(1e-9, pooled_var))

        cohens_d = (m_b - m_a) / pooled_sd

        # Non-parametric Cliff's delta (vectorized via Mann-Whitney U)
        from scipy import stats
        u_res = stats.mannwhitneyu(b, a, alternative="two-sided")
        cliffs_delta = (2.0 * float(u_res.statistic)) / float(n_a * n_b) - 1.0

        abs_d = abs(cohens_d)
        if abs_d < 0.2:
            mag = "NEGLIGIBLE"
        elif abs_d < 0.5:
            mag = "SMALL"
        elif abs_d < 0.8:
            mag = "MEDIUM"
        elif abs_d < 1.2:
            mag = "LARGE"
        else:
            mag = "VERY_LARGE"

        return {
            "cohens_d": round(cohens_d, 4),
            "cliffs_delta": round(cliffs_delta, 4),
            "magnitude": mag,
            "absolute_diff": round(m_b - m_a, 4),
            "mean_pre": round(m_a, 4),
            "mean_post": round(m_b, 4),
            "pooled_std": round(pooled_sd, 4),
            "status": "VALID",
        }

    @staticmethod
    def evaluate_sample_adequacy(
        sample_count: int,
        independent_units: Optional[int] = None,
        is_contaminated: bool = False,
        missing_rate: float = 0.0,
        min_required: int = 30,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Enforce strict minimum sample size policies to prevent premature claims.
        Backward-compatible with Sprint 10 and Sprint 11 callers.
        """
        eff_units = independent_units if independent_units is not None else sample_count

        if is_contaminated:
            return {
                "status": "DATA_CONTAMINATED",
                "label_tr": "Veri Kirliliği / Karantina",
                "is_adequate": False,
                "reason": "Veri seti veya olay karantinaya alınmış ya da yapay kurgu içeriyor.",
                "sample_count": sample_count,
                "independent_units": eff_units,
                "adequacy_status": "DATA_CONTAMINATED",
                "scientific_notes": "Veri seti veya olay karantinaya alınmış ya da yapay kurgu içeriyor.",
            }

        if missing_rate > 0.10:
            return {
                "status": "DATA_CONTAMINATED",
                "label_tr": "Aşırı Veri Kaybı",
                "is_adequate": False,
                "reason": f"Kayıp veri oranı (%{round(missing_rate * 100, 1)}) güven eşiğini aşıyor.",
                "sample_count": sample_count,
                "independent_units": eff_units,
                "adequacy_status": "DATA_CONTAMINATED",
                "scientific_notes": f"Kayıp veri oranı (%{round(missing_rate * 100, 1)}) güven eşiğini aşıyor.",
            }

        if eff_units < 5:
            status = "INSUFFICIENT_SAMPLE"
            label_tr = "Yetersiz Örneklem (Kritik)"
            is_adequate = False
            notes = f"Bağımsız birim sayısı ({eff_units}) minimum istatistiksel eşiğin (<5) altında."
        elif eff_units < 15:
            status = "LIMITED_EVIDENCE"
            label_tr = "Sınırlı İstatistiksel Kanıt"
            is_adequate = True
            notes = f"Örneklem ({eff_units}) keşifsel analiz için yeterli, ancak genelleme için sınırlı."
        else:
            status = "SUFFICIENT_EVIDENCE"
            label_tr = "Yeterli İstatistiksel Kanıt"
            is_adequate = True
            notes = f"Örneklem büyüklüğü ({eff_units}) istatistiksel güvenilirlik için yeterlidir."

        return {
            "status": status,
            "label_tr": label_tr,
            "is_adequate": is_adequate,
            "reason": notes,
            "sample_count": sample_count,
            "independent_units": eff_units,
            "min_required": min_required,
            "adequacy_status": status,
            "scientific_notes": notes,
        }

    @classmethod
    def classify_scientific_evidence(
        cls,
        sample_count: int,
        p_value_fdr: float,
        effect_magnitude: str,
        null_included_in_ci: bool,
        is_holdout_evaluated: bool = False,
        is_holdout_replicated: bool = False,
        is_data_contaminated: bool = False,
    ) -> str:
        """
        Derive strict Scientific Evidence Classification V2 based on validation gates.
        """
        if is_data_contaminated:
            return "DATA_CONTAMINATED"
        if sample_count < 10:
            return "INSUFFICIENT_EVIDENCE"
        if null_included_in_ci or p_value_fdr > 0.05:
            return "EXPLORATORY_ASSOCIATION" if sample_count >= 20 else "DESCRIPTIVE_ONLY"

        # If statistically significant with medium or higher effect size
        if effect_magnitude in ("MEDIUM", "LARGE", "VERY_LARGE"):
            if is_holdout_evaluated and is_holdout_replicated:
                return "OUT_OF_SAMPLE_EFFECT_REPLICATED"
            return "STATISTICALLY_SUPPORTED_ASSOCIATION"

        return "EXPLORATORY_ASSOCIATION"

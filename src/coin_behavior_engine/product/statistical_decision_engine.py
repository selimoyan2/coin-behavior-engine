"""
Statistical Decision Engine for Coin Behavior Engine (CBE).
Enforces the Canonical Significance Contract and provides an independent,
mathematically rigorous Benjamini-Hochberg (1995) FDR reference implementation.
Guarantees that statistical decision flags (unadjusted_supported, fdr_supported)
are derived exclusively by this engine and never independently assigned or fabricated.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import math


@dataclass(frozen=True)
class StatisticalDecisionRecord:
    """
    Canonical Significance Contract Record.
    Every statistical result in CBE must adhere to this schema.
    """
    experiment_id: str
    hypothesis_id: str
    metric_id: str
    estimator_id: str
    null_hypothesis: str
    alternative_hypothesis: str
    test_method: str
    test_statistic: Optional[float]
    p_value: Optional[float]
    multiple_testing_family_id: str
    fdr_method: str
    fdr_q_value: Optional[float]
    alpha: float
    confidence_interval: Optional[Tuple[Optional[float], Optional[float]]]
    confidence_level: float
    confidence_interval_method: str
    effect_size: Optional[float]
    practical_effect_threshold: Optional[float]
    sample_size: int
    source_data_hash: str
    calculation_version: str

    # Derived decision flags (read-only, derived by engine)
    unadjusted_supported: bool
    fdr_supported: bool
    ci_excludes_null: bool
    practical_effect_supported: bool
    decision_status: str  # VALID_SUPPORTED, VALID_NOT_SUPPORTED, INVALID_DATA, UNAVAILABLE
    justification_tr: str


class StatisticalDecisionEngine:
    """
    Centralized statistical decision service.
    Controls significance classifications and validates FDR adjustments.
    """
    VERSION = "2.0.0"
    DEFAULT_ALPHA = 0.05
    CANONICAL_ALPHA = 0.05
    DEFAULT_CI_LEVEL = 0.95

    @classmethod
    def compute_benjamini_hochberg_fdr(
        cls,
        p_values: List[Optional[float]],
        alpha: float = DEFAULT_ALPHA,
    ) -> List[Optional[float]]:
        """
        Independent reference implementation of Benjamini-Hochberg (1995) procedure.
        Strictly satisfies:
        1. Correctly indexes 1-based ranks i = 1, ..., m
        2. q_(i) = min_{k >= i} ( (m / k) * p_(k) )
        3. Monotonicity: q_(i) <= q_(i+1)
        4. Bounds: 0.0 <= q <= 1.0
        5. Preserves original order and handles ties, zero p-values, one p-values,
           missing (None) values, and invalid non-finite numbers.
        """
        m_total = len(p_values)
        if m_total == 0:
            return []

        # Filter valid indices and values
        valid_pairs = []
        for orig_idx, p in enumerate(p_values):
            if p is not None and not math.isnan(p) and not math.isinf(p) and 0.0 <= p <= 1.0:
                valid_pairs.append((orig_idx, float(p)))

        m_valid = len(valid_pairs)
        if m_valid == 0:
            return [None] * m_total

        # Sort by p-value ascending (stable sort)
        valid_pairs.sort(key=lambda x: x[1])

        # Compute raw adjusted values: q_k = (m_valid / k) * p_k
        raw_q = []
        for rank_1based, (orig_idx, p_val) in enumerate(valid_pairs, start=1):
            val = (m_valid / float(rank_1based)) * p_val
            raw_q.append(min(1.0, max(0.0, val)))

        # Enforce step-up monotonicity from right to left: q_i = min(q_i, q_{i+1})
        adjusted_q = [0.0] * m_valid
        running_min = 1.0
        for i in range(m_valid - 1, -1, -1):
            running_min = min(running_min, raw_q[i])
            adjusted_q[i] = running_min

        # Re-map to original positions
        results: List[Optional[float]] = [None] * m_total
        for k, (orig_idx, _) in enumerate(valid_pairs):
            results[orig_idx] = round(adjusted_q[k], 6)

        return results

    @classmethod
    def evaluate_significance(
        cls,
        experiment_id: str,
        hypothesis_id: str,
        metric_id: str,
        estimator_id: str,
        null_hypothesis: str,
        alternative_hypothesis: str,
        test_method: str,
        p_value: Optional[float],
        fdr_q_value: Optional[float],
        multiple_testing_family_id: str,
        sample_size: int,
        source_data_hash: str,
        confidence_interval: Optional[Tuple[Optional[float], Optional[float]]] = None,
        test_statistic: Optional[float] = None,
        alpha: float = DEFAULT_ALPHA,
        confidence_level: float = DEFAULT_CI_LEVEL,
        confidence_interval_method: str = "MOVING_BLOCK_BOOTSTRAP",
        effect_size: Optional[float] = None,
        practical_effect_threshold: Optional[float] = None,
        null_value: float = 1.0,
        calculation_version: Optional[str] = None,
    ) -> StatisticalDecisionRecord:
        """
        Derives decision flags strictly from inputs following canonical decision rules.
        """
        calc_ver = calculation_version or cls.VERSION

        # 1. Validate p-value
        p_valid = (
            p_value is not None
            and not math.isnan(p_value)
            and not math.isinf(p_value)
            and 0.0 <= p_value <= 1.0
        )

        # 2. Validate FDR q-value
        q_valid = (
            fdr_q_value is not None
            and not math.isnan(fdr_q_value)
            and not math.isinf(fdr_q_value)
            and 0.0 <= fdr_q_value <= 1.0
        )

        # 3. Decision flags derived strictly
        unadj_supp = bool(p_valid and p_value <= alpha)
        fdr_supp = bool(q_valid and fdr_q_value <= alpha)

        # 4. Confidence interval check against null
        ci_excludes = False
        if confidence_interval is not None and len(confidence_interval) == 2:
            c_low, c_high = confidence_interval
            if (
                c_low is not None
                and c_high is not None
                and not math.isnan(c_low)
                and not math.isnan(c_high)
            ):
                ci_excludes = bool(c_low > null_value or c_high < null_value)

        # 5. Practical effect check
        practical_supp = True
        if practical_effect_threshold is not None and effect_size is not None:
            practical_supp = bool(abs(effect_size) >= practical_effect_threshold)

        # 6. Overall status determination
        if not p_valid:
            status = "INVALID_DATA" if p_value is not None else "UNAVAILABLE"
            justification = f"Geçersiz veya eksik p-değeri (p={p_value})."
        elif sample_size < 4:
            status = "INVALID_DATA"
            justification = f"Yetersiz örneklem boyutu (N={sample_size} < 4)."
        elif fdr_supp and practical_supp:
            status = "VALID_SUPPORTED"
            justification = f"Hipotez FDR anlamlılık eşiğini (q={fdr_q_value} <= {alpha}) ve pratik etki eşiğini sağlamaktadır."
        elif unadj_supp and not fdr_supp:
            status = "VALID_NOT_SUPPORTED"
            justification = f"Ham p={p_value} <= {alpha} olmasına rağmen, çoklu test düzeltmesi sonrası q={fdr_q_value} > {alpha} nedeniyle reddedilemez."
        else:
            status = "VALID_NOT_SUPPORTED"
            justification = f"İstatistiki anlamlılık bulunamamıştır (p={p_value} > {alpha}, q={fdr_q_value} > {alpha})."

        return StatisticalDecisionRecord(
            experiment_id=experiment_id,
            hypothesis_id=hypothesis_id,
            metric_id=metric_id,
            estimator_id=estimator_id,
            null_hypothesis=null_hypothesis,
            alternative_hypothesis=alternative_hypothesis,
            test_method=test_method,
            test_statistic=test_statistic,
            p_value=p_value,
            multiple_testing_family_id=multiple_testing_family_id,
            fdr_method="BENJAMINI_HOCHBERG_1995",
            fdr_q_value=fdr_q_value,
            alpha=alpha,
            confidence_interval=confidence_interval,
            confidence_level=confidence_level,
            confidence_interval_method=confidence_interval_method,
            effect_size=effect_size,
            practical_effect_threshold=practical_effect_threshold,
            sample_size=sample_size,
            source_data_hash=source_data_hash,
            calculation_version=calc_ver,
            unadjusted_supported=unadj_supp,
            fdr_supported=fdr_supp,
            ci_excludes_null=ci_excludes,
            practical_effect_supported=practical_supp,
            decision_status=status,
            justification_tr=justification,
        )

    @classmethod
    def evaluate_multiple_testing_family(
        cls,
        family_id: str,
        items: List[Dict[str, Any]],
        alpha: float = DEFAULT_ALPHA,
    ) -> List[StatisticalDecisionRecord]:
        """
        Evaluates an entire multiple-testing family simultaneously.
        Computes reference BH FDR values and derives decision records for each hypothesis.
        """
        p_values = [it.get("p_value") for it in items]
        q_values = cls.compute_benjamini_hochberg_fdr(p_values, alpha=alpha)

        records = []
        for idx, it in enumerate(items):
            rec = cls.evaluate_significance(
                experiment_id=it.get("experiment_id", "EXP-UNKNOWN"),
                hypothesis_id=it.get("hypothesis_id", f"HYP-{idx+1:02d}"),
                metric_id=it.get("metric_id", "METRIC-UNKNOWN"),
                estimator_id=it.get("estimator_id", "EST-UNKNOWN"),
                null_hypothesis=it.get("null_hypothesis", "mu = 0"),
                alternative_hypothesis=it.get("alternative_hypothesis", "mu != 0"),
                test_method=it.get("test_method", "DUAL_PAIRED_INFERENCE"),
                p_value=it.get("p_value"),
                fdr_q_value=q_values[idx],
                multiple_testing_family_id=family_id,
                sample_size=it.get("sample_size", 0),
                source_data_hash=it.get("source_data_hash", "UNKNOWN"),
                confidence_interval=it.get("confidence_interval"),
                test_statistic=it.get("test_statistic"),
                alpha=alpha,
                effect_size=it.get("effect_size"),
                practical_effect_threshold=it.get("practical_effect_threshold"),
                null_value=it.get("null_value", 1.0),
            )
            records.append(rec)
        return records

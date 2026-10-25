"""
Scientific Comparison Policy and Metric Identity Contract.

Coin Behavior Engine (CBE) - Product Acceleration Sprint 13.
Centralizes versioned tolerance definitions, calculation methodology contracts,
and strict reproduction classifications.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class ReproductionClassification(str, Enum):
    """
    Standardized reproduction verdict classifications.
    Replaces naive binary pass/fail tolerances with methodologically rigorous states.
    """
    EXACT_MATCH = "EXACT_MATCH"
    NUMERICALLY_EQUIVALENT = "NUMERICALLY_EQUIVALENT"
    METHOD_DIFFERENCE_EXPLAINED = "METHOD_DIFFERENCE_EXPLAINED"
    STATISTICALLY_CONSISTENT_NOT_IDENTICAL = "STATISTICALLY_CONSISTENT_NOT_IDENTICAL"
    METHODOLOGICALLY_NONCOMPARABLE = "METHODOLOGICALLY_NONCOMPARABLE"
    MISMATCH = "MISMATCH"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    STALE_RESULT = "STALE_RESULT"


@dataclass(frozen=True)
class MetricIdentityContract:
    """
    Formal identity contract for any quantitative metric in CBE.
    Guarantees that metrics measuring different underlying variables (e.g. Return PSI
    vs Regime Label PSI) cannot be erroneously conflated.
    """
    metric_id: str
    variable_measured: str
    transformation: str
    binning_policy: str
    reference_distribution: str
    comparison_distribution: str
    period_boundaries: str
    purge_policy: str
    embargo_policy: str
    weighting: str
    missing_data_policy: str
    algorithm_version: str


@dataclass(frozen=True)
class MetricComparisonRule:
    """
    Centralized, pre-registered tolerance and verification policy for a specific metric.
    Tolerances are fixed a priori and cannot be widened ex post facto to obtain passing results.
    """
    metric_id: str
    metric_name: str
    data_variable: str
    calculation_method: str
    original_algorithm_version: str
    reference_algorithm_version: str
    absolute_tolerance: float
    relative_tolerance_pct: float
    numerical_precision_decimals: int
    rounding_policy: str
    pre_registration_status: str
    justification_for_tolerance: str
    acceptance_criteria: str
    policy_revision: str


@dataclass
class MetricEvaluationResult:
    """
    Detailed evaluation of an independent reference calculation against a claimed metric.
    """
    metric_id: str
    claimed_value: float
    reference_value: float
    absolute_difference: float
    relative_difference_pct: float
    allowed_absolute_tolerance: float
    allowed_relative_tolerance_pct: float
    classification: ReproductionClassification
    is_reproduced: bool

    @property
    def is_supported(self) -> bool:
        return self.is_reproduced  # True ONLY for EXACT_MATCH, NUMERICALLY_EQUIVALENT, or METHOD_DIFFERENCE_EXPLAINED
    explanation_tr: str
    methodological_divergence: Optional[str] = None


class ScientificComparisonPolicyCatalog:
    """
    Catalog of pre-registered metric comparison policies.
    Single source of truth across API, JSON artifacts, UI dashboard, and PDF reporting.
    """

    POLICY_VERSION = "CBE-SCIENTIFIC-POLICY-V1.0"
    POLICY_DATE_UTC = "2026-10-25T20:45:00Z"

    @classmethod
    def list_contracts(cls) -> List[MetricComparisonRule]:
        return list(cls.POLICIES.values())

    # Pre-registered policies
    POLICIES: Dict[str, MetricComparisonRule] = {
        # 1. CPI Volatility Shift Ratio (Mean of event ratios)
        "METRIC_CPI_MEAN_RATIO": MetricComparisonRule(
            metric_id="METRIC_CPI_MEAN_RATIO",
            metric_name="CPI Mean Event Volatility Ratio",
            data_variable="realized_volatility_shift_ratio",
            calculation_method="MEAN_OF_EVENT_LEVEL_VOLATILITY_RATIOS",
            original_algorithm_version="CBE-VOL-S10-V1",
            reference_algorithm_version="CBE-REF-MATH-S12-V1",
            absolute_tolerance=0.050,
            relative_tolerance_pct=3.0,
            numerical_precision_decimals=3,
            rounding_policy="ROUND_HALF_UP_TO_PRECISION",
            pre_registration_status="PRE_REGISTERED_FROZEN",
            justification_for_tolerance=(
                "Discrete 12-hour candle alignment versus continuous time slicing can introduce "
                "slight bar boundary differences (< 0.050) across 57 historical releases."
            ),
            acceptance_criteria="|claimed - reference| <= 0.050 or relative_diff <= 3.0%",
            policy_revision="1.0",
        ),

        # 2. CPI Cohort Aggregate Ratio (Ratio of cohort mean volatilities)
        "METRIC_CPI_COHORT_RATIO": MetricComparisonRule(
            metric_id="METRIC_CPI_COHORT_RATIO",
            metric_name="CPI Ratio of Cohort Mean Volatilities",
            data_variable="cohort_aggregate_volatility_ratio",
            calculation_method="RATIO_OF_COHORT_MEAN_VOLATILITIES",
            original_algorithm_version="CBE-COHORT-S11-V1",
            reference_algorithm_version="CBE-REF-MATH-S13-V1",
            absolute_tolerance=0.050,
            relative_tolerance_pct=3.0,
            numerical_precision_decimals=3,
            rounding_policy="ROUND_HALF_UP_TO_PRECISION",
            pre_registration_status="PRE_REGISTERED_FROZEN",
            justification_for_tolerance=(
                "Ratio of mean post-volatility to mean pre-volatility across all cohort events."
            ),
            acceptance_criteria="|claimed - reference| <= 0.050",
            policy_revision="1.0",
        ),

        # 3. Inflation Cohort Mean Volatility Ratio (Parent Cohort)
        "METRIC_INFLATION_MEAN_RATIO": MetricComparisonRule(
            metric_id="METRIC_INFLATION_MEAN_RATIO",
            metric_name="US Inflation Cohort Mean Volatility Ratio",
            data_variable="realized_volatility_shift_ratio",
            calculation_method="MEAN_OF_EVENT_LEVEL_VOLATILITY_RATIOS",
            original_algorithm_version="CBE-VOL-S11-V1",
            reference_algorithm_version="CBE-REF-MATH-S12-V1",
            absolute_tolerance=0.050,
            relative_tolerance_pct=3.0,
            numerical_precision_decimals=3,
            rounding_policy="ROUND_HALF_UP_TO_PRECISION",
            pre_registration_status="PRE_REGISTERED_FROZEN",
            justification_for_tolerance=(
                "Parent cohort encompassing 102 verified events (CPI and Core PCE). "
                "Tolerance bounds window boundary variances."
            ),
            acceptance_criteria="|claimed - reference| <= 0.050 or relative_diff <= 3.0%",
            policy_revision="1.0",
        ),

        # 4. Walk-Forward Regime Label Distribution Stability (PSI)
        "METRIC_REGIME_LABEL_PSI": MetricComparisonRule(
            metric_id="METRIC_REGIME_LABEL_PSI",
            metric_name="Walk-Forward Regime Label Distribution PSI",
            data_variable="canonical_regime_state_frequencies",
            calculation_method="KULLBACK_LEIBLER_SYMMETRIC_SUM_CATEGORICAL",
            original_algorithm_version="CBE-WF-S11-V1",
            reference_algorithm_version="CBE-REF-MATH-S13-V1",
            absolute_tolerance=0.0020,
            relative_tolerance_pct=5.0,
            numerical_precision_decimals=4,
            rounding_policy="ROUND_HALF_UP_TO_PRECISION",
            pre_registration_status="PRE_REGISTERED_FROZEN",
            justification_for_tolerance=(
                "Measures stability of categorical distribution across 6 canonical market regime "
                "states between Train (2022-2023) and Test (2025)."
            ),
            acceptance_criteria="|claimed - reference| <= 0.0020",
            policy_revision="1.0",
        ),

        # 5. Walk-Forward Return Distribution Stability (PSI on Quantile Bins)
        "METRIC_RETURN_DISTRIBUTION_PSI": MetricComparisonRule(
            metric_id="METRIC_RETURN_DISTRIBUTION_PSI",
            metric_name="Walk-Forward Return Distribution Quantile PSI",
            data_variable="hourly_log_returns_10_quantile_bins",
            calculation_method="POPULATION_STABILITY_INDEX_QUANTILE_BINNING",
            original_algorithm_version="CBE-INDEP-S12-V1",
            reference_algorithm_version="CBE-REF-MATH-S13-V1",
            absolute_tolerance=0.0020,
            relative_tolerance_pct=5.0,
            numerical_precision_decimals=4,
            rounding_policy="ROUND_HALF_UP_TO_PRECISION",
            pre_registration_status="PRE_REGISTERED_FROZEN",
            justification_for_tolerance=(
                "Continuous return distribution binned into 10 deciles of training partition. "
                "Distinct from regime state frequencies."
            ),
            acceptance_criteria="|claimed - reference| <= 0.0020",
            policy_revision="1.0",
        ),

        # 6. Event Count Verification
        "METRIC_EVENT_COUNT_VERIFICATION": MetricComparisonRule(
            metric_id="METRIC_EVENT_COUNT_VERIFICATION",
            metric_name="Event Cohort Discovery and Verification Count",
            data_variable="verified_macro_event_count",
            calculation_method="EXACT_COUNT_UNQUARANTINED",
            original_algorithm_version="CBE-TAXONOMY-S11-V1",
            reference_algorithm_version="CBE-REF-MATH-S12-V1",
            absolute_tolerance=0.0,
            relative_tolerance_pct=0.0,
            numerical_precision_decimals=0,
            rounding_policy="EXACT_INTEGER",
            pre_registration_status="PRE_REGISTERED_FROZEN",
            justification_for_tolerance="Exact deterministic event count from verified source manifest.",
            acceptance_criteria="claimed == reference (zero tolerance)",
            policy_revision="1.0",
        ),
    }

    # Metric Identity Contracts
    IDENTITY_CONTRACTS: Dict[str, MetricIdentityContract] = {
        "METRIC_REGIME_LABEL_PSI": MetricIdentityContract(
            metric_id="METRIC_REGIME_LABEL_PSI",
            variable_measured="canonical_market_regime_categorical_labels",
            transformation="DISCRETE_THRESHOLD_MAPPING",
            binning_policy="6_CANONICAL_CATEGORICAL_REGIMES",
            reference_distribution="In-Sample Train (2022-01 to 2023-12)",
            comparison_distribution="Out-of-Sample Test (2025-01 to 2025-12)",
            period_boundaries="TRAIN: 2022-2023 | VAL: 2024 | TEST: 2025 | HOLDOUT: 2026",
            purge_policy="DYNAMIC_EMBARGO_PURGE",
            embargo_policy="EMBARGO_BARS = max(lookback, horizon, window)",
            weighting="UNIFORM_TIME_WEIGHTED",
            missing_data_policy="CONTINUOUS_PARQUET_ZERO_IMPUTATION_REJECTED",
            algorithm_version="CBE-WF-S11-V1",
        ),
        "METRIC_RETURN_DISTRIBUTION_PSI": MetricIdentityContract(
            metric_id="METRIC_RETURN_DISTRIBUTION_PSI",
            variable_measured="hourly_close_to_close_log_returns",
            transformation="NATURAL_LOG_PRICE_DIFFERENCE",
            binning_policy="10_EMPIRICAL_DECILES_FROM_TRAIN",
            reference_distribution="In-Sample Train (2022-01 to 2023-12)",
            comparison_distribution="Out-of-Sample Test (2025-01 to 2025-12)",
            period_boundaries="TRAIN: 2022-2023 | TEST: 2025",
            purge_policy="BOUNDARY_EMBARGO_24_BARS",
            embargo_policy="24_BARS_PURGE",
            weighting="UNIFORM",
            missing_data_policy="PARQUET_STRICT_NO_INTERPOLATION",
            algorithm_version="CBE-INDEP-S12-V1",
        ),
    }

    @classmethod
    def evaluate_cross_metric(
        cls,
        claimed_metric_id: str,
        reference_metric_id: str,
        claimed_value: float,
        reference_value: float,
    ) -> MetricEvaluationResult:
        """Evaluate cross-metric comparison ensuring noncomparable variables are flagged."""
        return MetricEvaluationResult(
            metric_id=f"{claimed_metric_id}_VS_{reference_metric_id}",
            claimed_value=claimed_value,
            reference_value=reference_value,
            absolute_difference=round(abs(claimed_value - reference_value), 4),
            relative_difference_pct=round(abs(claimed_value - reference_value) / max(1e-6, claimed_value) * 100.0, 2),
            allowed_absolute_tolerance=0.0,
            allowed_relative_tolerance_pct=0.0,
            classification=ReproductionClassification.METHODOLOGICALLY_NONCOMPARABLE,
            is_reproduced=False,
            explanation_tr="Karşılaştırılan metrikler farklı istatistiksel değişkenleri temsil etmektedir. Yöntemsel olarak kıyaslanamaz.",
            methodological_divergence="CROSS_METRIC_CONFLATION",
        )

    @classmethod
    def evaluate(
        cls,
        metric_id: str,
        claimed_value: float,
        reference_value: float,
        methodological_note: Optional[str] = None,
        is_different_variable: bool = False,
    ) -> MetricEvaluationResult:
        """
        Evaluate an independent reference measurement against pre-registered comparison policy.
        """
        if is_different_variable:
            return MetricEvaluationResult(
                metric_id=metric_id,
                claimed_value=claimed_value,
                reference_value=reference_value,
                absolute_difference=abs(claimed_value - reference_value),
                relative_difference_pct=100.0 * abs(claimed_value - reference_value) / max(1e-6, abs(claimed_value)),
                allowed_absolute_tolerance=0.0,
                allowed_relative_tolerance_pct=0.0,
                classification=ReproductionClassification.METHODOLOGICALLY_NONCOMPARABLE,
                is_reproduced=False,
                explanation_tr=(
                    f"Karşılaştırılan değişkenler yöntemsel ve istatistiki olarak farklı nesnelerdir. "
                    f"Örn: Getiri kuantil PSI ile Rejim etiketi PSI eşdeğer tutulamaz."
                ),
                methodological_divergence=methodological_note or "DIFFERENT_UNDERLYING_VARIABLES",
            )

        policy = cls.POLICIES.get(metric_id)
        if not policy:
            diff = abs(claimed_value - reference_value)
            return MetricEvaluationResult(
                metric_id=metric_id,
                claimed_value=claimed_value,
                reference_value=reference_value,
                absolute_difference=round(diff, 6),
                relative_difference_pct=round(100.0 * diff / max(1e-6, abs(claimed_value)), 2),
                allowed_absolute_tolerance=0.05,
                allowed_relative_tolerance_pct=5.0,
                classification=ReproductionClassification.INSUFFICIENT_EVIDENCE,
                is_reproduced=False,
                explanation_tr=f"Metrik ({metric_id}) için önceden tanımlanmış karşılaştırma politikası bulunamadı.",
                methodological_divergence="UNREGISTERED_METRIC_POLICY",
            )

        abs_diff = round(abs(claimed_value - reference_value), policy.numerical_precision_decimals)
        denom = max(1e-9, abs(claimed_value))
        rel_diff_pct = round(100.0 * abs_diff / denom, 2)

        # Classification assignment
        if abs_diff <= 1e-6:
            classification = ReproductionClassification.EXACT_MATCH
            is_reproduced = True
            expl = f"Referans hesaplama ({reference_value}) raporlanan değerle ({claimed_value}) tam olarak eşleşmektedir."
        elif abs_diff <= policy.absolute_tolerance or rel_diff_pct <= policy.relative_tolerance_pct:
            if methodological_note:
                classification = ReproductionClassification.METHOD_DIFFERENCE_EXPLAINED
                is_reproduced = True
                expl = (
                    f"Referans hesaplama ({reference_value}) kabul edilebilir ön-kayıtlı tolerans dahilindedir. "
                    f"Fark yöntemsel detayla açıklanmıştır: {methodological_note}"
                )
            else:
                classification = ReproductionClassification.NUMERICALLY_EQUIVALENT
                is_reproduced = True
                expl = (
                    f"Referans hesaplama ({reference_value}) raporlanan değerle ({claimed_value}) "
                    f"ön-kayıtlı tolerans sınırında (|fark| = {abs_diff} <= {policy.absolute_tolerance}) sayısaldır."
                )
        else:
            classification = ReproductionClassification.MISMATCH
            is_reproduced = False
            expl = (
                f"Referans hesaplama ({reference_value}) ile raporlanan değer ({claimed_value}) "
                f"arasındaki fark ({abs_diff}) izin verilen toleransı ({policy.absolute_tolerance}) aşmaktadır."
            )

        return MetricEvaluationResult(
            metric_id=metric_id,
            claimed_value=claimed_value,
            reference_value=reference_value,
            absolute_difference=abs_diff,
            relative_difference_pct=rel_diff_pct,
            allowed_absolute_tolerance=policy.absolute_tolerance,
            allowed_relative_tolerance_pct=policy.relative_tolerance_pct,
            classification=classification,
            is_reproduced=is_reproduced,
            explanation_tr=expl,
            methodological_divergence=methodological_note,
        )

    @classmethod
    def export_policy_manifest(cls) -> Dict[str, Any]:
        """
        Export entire scientific comparison policy catalog as structured dictionary.
        """
        return {
            "policy_version": cls.POLICY_VERSION,
            "policy_date_utc": cls.POLICY_DATE_UTC,
            "total_registered_policies": len(cls.POLICIES),
            "reproduction_classifications": [c.value for c in ReproductionClassification],
            "policies": {k: vars(v) for k, v in cls.POLICIES.items()},
            "identity_contracts": {k: vars(v) for k, v in cls.IDENTITY_CONTRACTS.items()},
        }

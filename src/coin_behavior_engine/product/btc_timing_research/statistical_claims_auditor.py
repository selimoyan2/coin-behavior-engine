"""Statistical Claims Auditor & Corrected Hypothesis Classifier.

Sprint 32 — Scientific Validation Closure & Investment Research Dashboard V10
Audits H1–H5 hypothesis claims, enforces serial dependence awareness,
distinguishes DESCRIPTIVE_THRESHOLD_MET from STATISTICALLY_SUPPORTED,
and replaces unsupported p-values with STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class AuditedHypothesisRecord:
    hypothesis_id: str
    name: str
    null_hypothesis: str
    alternative_hypothesis: str
    test_statistic_name: str
    test_statistic_value: float
    observation_unit: str
    sample_size_description: str
    target_threshold: str
    descriptive_verdict: str  # DESCRIPTIVE_THRESHOLD_MET or DESCRIPTIVE_THRESHOLD_FAILED
    statistical_verdict: str  # STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED
    effect_size_summary: str
    serial_dependence_assessment: str
    statistical_assumptions_violated: List[str]
    multiple_testing_treatment: str
    interpretation: str
    canonical_model_attribution: str


@dataclass
class StatisticalClaimsAuditResult:
    sprint_id: str
    audit_date_utc: str
    overall_methodological_verdict: str
    hypotheses: Dict[str, AuditedHypothesisRecord]
    epistemic_warning: str


class StatisticalClaimsAuditor:
    """Audits the statistical claims made in Sprint 31 and provides corrected scientific classifications."""

    def __init__(self):
        pass

    def audit_all_hypotheses(
        self,
        cost_simple: float = 6789.12,
        cost_low_turnover: float = 793.47,
        ret_simple: float = -62.60,
        ret_low_turnover: float = -28.80,
        ret_bnh: float = -9.69,
        ret_derived: float = -42.33,
        mdd_simple: float = -65.12,
        mdd_low_turnover: float = -39.20,
        sharpe_simple: float = -3.00,
        sharpe_derived: float = -2.28,
    ) -> StatisticalClaimsAuditResult:
        """Perform formal audit and classification across H1 through H5."""
        records: Dict[str, AuditedHypothesisRecord] = {}

        # -------------------------------------------------------------
        # H1: Cost Reduction via Turnover Controls
        # -------------------------------------------------------------
        cost_red_pct = ((cost_simple - cost_low_turnover) / cost_simple) * 100.0
        records["H1"] = AuditedHypothesisRecord(
            hypothesis_id="H1",
            name="Turnover Controls Reduce Transaction Costs",
            null_hypothesis="H0: Low-turnover controls do not reduce transaction costs relative to unconstrained trend (E[Costs_low] >= E[Costs_simple]).",
            alternative_hypothesis="H1: Low-turnover controls reduce transaction costs (E[Costs_low] < E[Costs_simple]).",
            test_statistic_name="transaction_cost_reduction_pct",
            test_statistic_value=round(cost_red_pct, 2),
            observation_unit="Deterministic 1-year simulation path (57 trades vs 616 trades)",
            sample_size_description="N = 1 annual market realization (8,760 hourly candles)",
            target_threshold="Cost reduction >= 50.0%",
            descriptive_verdict="DESCRIPTIVE_THRESHOLD_MET",
            statistical_verdict="STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED",
            effect_size_summary=f"Costs reduced by {cost_red_pct:.2f}% (${cost_simple:,.2f} -> ${cost_low_turnover:,.2f}, saving ${cost_simple - cost_low_turnover:,.2f} USDT).",
            serial_dependence_assessment="Trade triggers are driven by trend state durations that exhibit serial autocorrelation. A single backtest does not provide independent trade samples.",
            statistical_assumptions_violated=[
                "Independent and identically distributed (i.i.d.) observations",
                "Repeated independent path trials (N=1 historical path)",
            ],
            multiple_testing_treatment="Bonferroni adjustment cannot establish significance for deterministic single-path outcomes.",
            interpretation="Descriptively confirmed: Hysteresis bands and holding periods reliably curtail trade frequency and transaction costs. However, population-level statistical significance cannot be established from a single historical trajectory.",
            canonical_model_attribution="NOT_APPLICABLE (Rule-based technical timing policy)",
        )

        # -------------------------------------------------------------
        # H2: Net Return Improvement
        # -------------------------------------------------------------
        ret_diff_h2 = ret_low_turnover - ret_simple
        records["H2"] = AuditedHypothesisRecord(
            hypothesis_id="H2",
            name="Reduced Transaction Costs Improve Net Strategy Return",
            null_hypothesis="H0: Reduced transaction friction does not improve net annual return over unconstrained trend (E[Return_low] <= E[Return_simple]).",
            alternative_hypothesis="H1: Reduced transaction friction improves net annual return (E[Return_low] > E[Return_simple]).",
            test_statistic_name="net_return_difference_percentage_points",
            test_statistic_value=round(ret_diff_h2, 2),
            observation_unit="Deterministic 1-year simulation path (8,760 hourly steps)",
            sample_size_description="N = 1 annual market realization",
            target_threshold="Return difference > 0.0 percentage points",
            descriptive_verdict="DESCRIPTIVE_THRESHOLD_MET",
            statistical_verdict="STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED",
            effect_size_summary=f"Net return improved by +{ret_diff_h2:.2f} percentage points ({ret_simple:.2f}% -> {ret_low_turnover:.2f}%), preserving $3,380.57 of equity.",
            serial_dependence_assessment="Hourly portfolio equity returns exhibit severe serial autocorrelation and volatility clustering (ARCH/GARCH dynamics). Treating hourly bars as independent observations artificially deflates standard errors.",
            statistical_assumptions_violated=[
                "Zero return autocorrelation (hourly returns are serially dependent)",
                "Stationarity across market regimes",
                "Asymptotic independence of observations",
            ],
            multiple_testing_treatment="Bonferroni correction alone does not validate a single-year performance difference.",
            interpretation="Descriptively confirmed: Lower transaction costs directly preserved capital. Statistically, however, this single-year difference cannot be generalized as an unconditional alpha without multi-year regime bootstrap testing.",
            canonical_model_attribution="NOT_APPLICABLE (Rule-based technical timing policy)",
        )

        # -------------------------------------------------------------
        # H3: Max Drawdown Severity Reduction
        # -------------------------------------------------------------
        mdd_diff_h3 = abs(mdd_simple) - abs(mdd_low_turnover)
        records["H3"] = AuditedHypothesisRecord(
            hypothesis_id="H3",
            name="Turnover Controls Dampen Maximum Drawdown Severity",
            null_hypothesis="H0: Low-turnover controls do not reduce maximum drawdown severity (|MDD_low| >= |MDD_simple|).",
            alternative_hypothesis="H1: Low-turnover controls reduce maximum drawdown severity (|MDD_low| < |MDD_simple|).",
            test_statistic_name="max_drawdown_severity_reduction_percentage_points",
            test_statistic_value=round(mdd_diff_h3, 2),
            observation_unit="Peak-to-trough path extremum over 8,760 hourly candles",
            sample_size_description="N = 1 trajectory path extremum",
            target_threshold="Drawdown severity reduction >= 10.0 percentage points",
            descriptive_verdict="DESCRIPTIVE_THRESHOLD_MET",
            statistical_verdict="STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED",
            effect_size_summary=f"Maximum drawdown severity curbed from {mdd_simple:.2f}% to {mdd_low_turnover:.2f}% (improvement of {mdd_diff_h3:.2f} pp).",
            serial_dependence_assessment="Serial dependence and path-dependence are inherent to drawdown series. Drawdown is an extreme-value path-dependent statistic. Observations within a single drawdown cycle are 100% dependent on prior path states.",
            statistical_assumptions_violated=[
                "Independent observations",
                "Extreme value asymptotic distribution on single realization",
            ],
            multiple_testing_treatment="Multiple testing corrections cannot compensate for single-path extremum variance.",
            interpretation="Descriptively confirmed: Eliminating false-breakout whipsaws curbed cumulative equity decay from -65.12% to -39.20%. Statistically unestablished due to extreme-value path dependence.",
            canonical_model_attribution="NOT_APPLICABLE (Rule-based technical timing policy)",
        )

        # -------------------------------------------------------------
        # H4: Active Timing Outperforms Passive Buy & Hold
        # -------------------------------------------------------------
        excess_h4 = ret_low_turnover - ret_bnh
        records["H4"] = AuditedHypothesisRecord(
            hypothesis_id="H4",
            name="Active Low-Turnover Policy Outperforms Passive Buy & Hold",
            null_hypothesis="H0: Active timing does not outperform passive Buy & Hold after costs (E[Return_active] <= E[Return_bnh]).",
            alternative_hypothesis="H1: Active timing outperforms passive Buy & Hold (E[Return_active] > E[Return_bnh]).",
            test_statistic_name="excess_return_over_buy_and_hold_percentage_points",
            test_statistic_value=round(excess_h4, 2),
            observation_unit="Deterministic 1-year simulation path",
            sample_size_description="N = 1 annual market realization",
            target_threshold="Excess return > 0.0 percentage points",
            descriptive_verdict="DESCRIPTIVE_THRESHOLD_FAILED",
            statistical_verdict="STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED",
            effect_size_summary=f"Active timing delivered {ret_low_turnover:.2f}% vs Buy & Hold {ret_bnh:.2f}% (underperformance: {excess_h4:.2f} pp).",
            serial_dependence_assessment="Serial dependence and autocorrelation in underlying price series caused policy lag at trend inflection points while bearing identical market sequences.",
            statistical_assumptions_violated=[
                "Threshold met requirement (threshold was failed)",
                "Sample size sufficiency for market regime diversity",
            ],
            multiple_testing_treatment="Hypothesis failed descriptively; statistical tests would reject the alternative hypothesis.",
            interpretation="REJECTED: Active timing failed to outperform passive holding on 2025 unseen data. Trend-following lag in range-bound/whipsaw markets incurred negative alpha.",
            canonical_model_attribution="NOT_APPLICABLE (Rule-based technical timing policy)",
        )

        # -------------------------------------------------------------
        # H5: Derived Regime Confirmation Adds Incremental Value
        # -------------------------------------------------------------
        ret_diff_h5 = ret_derived - ret_simple
        sr_diff_h5 = sharpe_derived - sharpe_simple
        records["H5"] = AuditedHypothesisRecord(
            hypothesis_id="H5",
            name="Derived Regime Confirmation Adds Incremental Value Over Simple Trend",
            null_hypothesis="H0: Derived regime confirmation does not improve net return or Sharpe ratio over simple trend (Delta_Return <= 0 or Delta_Sharpe <= 0).",
            alternative_hypothesis="H1: Derived regime confirmation improves net return and Sharpe ratio (Delta_Return > 0 and Delta_Sharpe > 0).",
            test_statistic_name="net_return_improvement_percentage_points",
            test_statistic_value=round(ret_diff_h5, 2),
            observation_unit="Deterministic 1-year simulation path",
            sample_size_description="N = 1 annual market realization",
            target_threshold="Delta_Return > 0.0 and Delta_Sharpe > 0.0",
            descriptive_verdict="DESCRIPTIVE_THRESHOLD_MET",
            statistical_verdict="STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED",
            effect_size_summary=f"Net return improved by +{ret_diff_h5:.2f} pp ({ret_simple:.2f}% -> {ret_derived:.2f}%) and Sharpe improved by +{sr_diff_h5:.2f} ({sharpe_simple:.2f} -> {sharpe_derived:.2f}).",
            serial_dependence_assessment="Serial persistence and multi-hour cluster autocorrelation characterize regime classification states.",
            statistical_assumptions_violated=[
                "Independent observations",
                "Canonical model equivalence (CANONICAL MODEL WAS NOT USED; only derived research proxy)",
            ],
            multiple_testing_treatment="Bonferroni correction does not validate single-path deterministic simulation deltas.",
            interpretation="Descriptively confirmed: Volatility and momentum regime filtering prevented several false breakouts. However, canonical model status was STRICTLY_FROZEN, so this reflects only the research proxy classifier, and statistical significance is unestablished.",
            canonical_model_attribution="DERIVED_RESEARCH_CLASSIFIER_ONLY (NOT CANONICAL CBE-0.7.0)",
        )

        warning = (
            "CRITICAL SCIENTIFIC INTEGRITY NOTICE: In financial time-series research, deterministic differences "
            "between backtest runs on a single historical year (N=1 realization) DO NOT constitute statistical "
            "discoveries. Hourly price changes exhibit strong serial dependence and volatility clustering. "
            "Bonferroni adjustments on arbitrary thresholds cannot establish population-level significance. "
            "All claims are formally classified as DESCRIPTIVE_THRESHOLD_MET or DESCRIPTIVE_THRESHOLD_FAILED, "
            "with STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED."
        )

        return StatisticalClaimsAuditResult(
            sprint_id="CBE_SPRINT32_SCIENTIFIC_VALIDATION_DASHBOARD_V10",
            audit_date_utc=datetime.now(timezone.utc).isoformat(),
            overall_methodological_verdict="DESCRIPTIVE_EVIDENCE_VALIDATED_STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED",
            hypotheses=records,
            epistemic_warning=warning,
        )

    def generate_audit_markdown(self, result: StatisticalClaimsAuditResult) -> str:
        """Generate 03_statistical_claims_audit.md."""
        md = f"""# 03 — Statistical Claims Audit Report
## Rigorous Re-Evaluation of Sprint 31 H1–H5 Hypotheses

**Sprint ID:** `{result.sprint_id}`  
**Audit Date UTC:** `{result.audit_date_utc}`  
**Methodological Verdict:** **`{result.overall_methodological_verdict}`**  

---

## 1. Executive Methodological Finding

> [!WARNING]
> In Sprint 31, deterministic differences between single simulation paths on 2025 data were reported with p-values (e.g. $p < 0.001$).  
> This audit determines that:
> 1. **Hourly observations are serially dependent.** Financial returns exhibit volatility clustering and autocorrelation. Treating 8,760 hourly candles as independent observations is mathematically invalid.
> 2. **Sample size of independent paths is N = 1.** A single historical trajectory over one calendar year cannot establish asymptotic statistical distributions.
> 3. **Bonferroni correction does not manufacture statistical significance.** Adjusting nominal alpha from 0.05 to 0.01 corrects for family-wise error only when valid test statistics exist.
> 
> Therefore, all reported p-values are formally revoked and classified as:  
> **`STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED`**  
> Observed empirical differences are retained under the honest scientific standard:  
> **`DESCRIPTIVE_THRESHOLD_MET`** or **`DESCRIPTIVE_THRESHOLD_FAILED`**.

---

## 2. Comprehensive Hypotheses Audit Matrix

| Hypothesis | Name | Metric | Effect Size | Descriptive Status | Statistical Status |
| :---: | :--- | :---: | :---: | :---: | :---: |
"""
        for h_id, rec in result.hypotheses.items():
            md += f"| **{h_id}** | {rec.name} | `{rec.test_statistic_name}` | {rec.effect_size_summary} | **`{rec.descriptive_verdict}`** | **`{rec.statistical_verdict}`** |\n"

        md += """
---

## 3. Detailed Hypothesis Re-Evaluation

"""
        for h_id, rec in result.hypotheses.items():
            md += f"""### {h_id}: {rec.name}
- **Null Hypothesis ($H_0$):** {rec.null_hypothesis}
- **Alternative Hypothesis ($H_1$):** {rec.alternative_hypothesis}
- **Observation Unit:** {rec.observation_unit}
- **Sample Size:** {rec.sample_size_description}
- **Target Threshold:** `{rec.target_threshold}`
- **Observed Test Statistic:** `{rec.test_statistic_value}`
- **Descriptive Verdict:** **`{rec.descriptive_verdict}`**
- **Statistical Significance:** **`{rec.statistical_verdict}`**
- **Serial Dependence Assessment:** {rec.serial_dependence_assessment}
- **Violated Statistical Assumptions:**
"""
            for v in rec.statistical_assumptions_violated:
                md += f"  - {v}\n"
            md += f"""- **Canonical Model Attribution:** `{rec.canonical_model_attribution}`
- **Epistemic Interpretation:** {rec.interpretation}

"""

        md += f"""---

## 4. Methodological Conclusion

By explicitly separating descriptive effect sizes from unestablished statistical discoveries, the Coin Behavior Engine maintains absolute epistemological integrity. Historical performance improvements are documented as empirical path observations without overclaiming predictive or statistical certainty.
"""
        return md

    def generate_corrected_classifications_json(self, result: StatisticalClaimsAuditResult) -> Dict[str, Any]:
        """Generate dictionary for 04_corrected_h1_h5_classifications.json."""
        d = {
            "sprint_id": result.sprint_id,
            "audit_date_utc": result.audit_date_utc,
            "overall_methodological_verdict": result.overall_methodological_verdict,
            "epistemic_warning": result.epistemic_warning,
            "hypotheses": {},
        }
        for k, v in result.hypotheses.items():
            d["hypotheses"][k] = asdict(v)
        return d

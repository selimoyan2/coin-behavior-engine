"""
Script to apply estimand and confidence interval consistency fix to holdout_validation_engine.py.
"""
from pathlib import Path

file_path = Path("src/coin_behavior_engine/product/holdout_validation_engine.py")
text = file_path.read_text(encoding="utf-8")

target1 = """    # Canonical Classification
    replication_classification: str         # REPLICATED_WITH_PREDECLARED_CRITERIA, DIRECTION_ONLY_REPLICATED, EFFECT_ATTENUATED, NOT_REPLICATED, INSUFFICIENT_HOLDOUT_SAMPLE, HOLDOUT_PREVIOUSLY_EXPOSED, METHODOLOGICALLY_NONCOMPARABLE
    justification_tr: str"""

replacement1 = """    # Canonical Classification
    replication_classification: str         # REPLICATED_WITH_PREDECLARED_CRITERIA, DIRECTION_ONLY_REPLICATED, EFFECT_ATTENUATED, NOT_REPLICATED, INSUFFICIENT_HOLDOUT_SAMPLE, HOLDOUT_PREVIOUSLY_EXPOSED, METHODOLOGICALLY_NONCOMPARABLE
    justification_tr: str

    # Additional Estimand Disclosures (Sprint 16 Scientific Reconciliation)
    train_arithmetic_mean_ratio: Optional[float] = None
    holdout_arithmetic_mean_ratio: Optional[float] = None
    estimand_type: str = "GEOMETRIC_MEAN_RATIO_EXP_MEAN_LOG_RATIO" """

assert target1 in text, "target1 not found"
text = text.replace(target1, replacement1)

target2 = """                    # Training metrics
                    t_mean_r = float(np.mean(train_ratios))
                    t_log_mean = float(np.mean(train_log_diffs))
                    t_log_std = float(np.std(train_log_diffs, ddof=1)) if len(train_log_diffs) > 1 else 1e-4
                    t_se = t_log_std / math.sqrt(len(train_log_diffs))
                    t_ci_log = (t_log_mean - 1.96 * t_se, t_log_mean + 1.96 * t_se)
                    t_ci = (round(math.exp(t_ci_log[0]), 3), round(math.exp(t_ci_log[1]), 3))
                    t_d = t_log_mean / t_log_std if t_log_std > 0 else 0.0
                    from scipy import stats
                    t_p = float(2.0 * (1.0 - stats.t.cdf(abs(t_log_mean / t_se), df=len(train_log_diffs) - 1)))
                    t_sig = bool(t_ci[0] > 1.0 or t_ci[1] < 1.0)

                    # Holdout metrics
                    h_mean_r = float(np.mean(holdout_ratios))
                    h_log_mean = float(np.mean(holdout_log_diffs))
                    h_log_std = float(np.std(holdout_log_diffs, ddof=1)) if len(holdout_log_diffs) > 1 else 1e-4
                    h_se = h_log_std / math.sqrt(len(holdout_log_diffs))
                    h_ci_log = (h_log_mean - 1.96 * h_se, h_log_mean + 1.96 * h_se)
                    h_ci = (round(math.exp(h_ci_log[0]), 3), round(math.exp(h_ci_log[1]), 3))
                    h_d = h_log_mean / h_log_std if h_log_std > 0 else 0.0
                    h_p = float(2.0 * (1.0 - stats.t.cdf(abs(h_log_mean / h_se), df=len(holdout_log_diffs) - 1)))
                    h_sig = bool(h_ci[0] > 1.0 or h_ci[1] < 1.0)

                    # Comparison
                    dir_agree = bool((t_mean_r > 1.0 and h_mean_r > 1.0) or (t_mean_r < 1.0 and h_mean_r < 1.0))
                    retention = h_mean_r / t_mean_r if t_mean_r > 0 else 1.0
                    practical_ret = bool(h_mean_r >= 1.10 and abs(h_d) >= 0.20)
                    stab_score = round(1.0 - abs(t_mean_r - h_mean_r) / max(t_mean_r, h_mean_r), 3)

                    # Classification
                    if not dir_agree:
                        classification = "NOT_REPLICATED"
                        just = f"Yön uyumsuzluğu: Train={t_mean_r:.2f}x, Holdout={h_mean_r:.2f}x."
                    elif retention < 0.50:
                        classification = "EFFECT_ATTENUATED"
                        just = f"Etki büyüklüğü zayıfladı (%{retention*100:.1f} tutunma)."
                    elif h_sig and practical_ret:
                        classification = "REPLICATED_WITH_PREDECLARED_CRITERIA"
                        just = f"Holdout verisinde etki yönü, pratik büyüklük ({h_mean_r:.2f}x) ve istatistiki destek korundu."
                    else:
                        classification = "DIRECTION_ONLY_REPLICATED"
                        just = f"Yön pozitif korundu ({h_mean_r:.2f}x) ancak holdout istatistiki destek sınırda kaldı."

                    evaluations.append(
                        SpecificationHoldoutDetail(
                            cell_id=cell_id,
                            cohort=cohort,
                            interval=intv,
                            window_hours=win_h,
                            estimator=est,
                            is_valid_specification=True,
                            exclusion_reason_tr=None,
                            train_event_count=len(train_ratios),
                            train_mean_ratio=round(t_mean_r, 3),
                            train_ci_95=t_ci,
                            train_cohens_d=round(t_d, 3),
                            train_p_value=round(t_p, 6),
                            train_statistically_supported=t_sig,
                            holdout_event_count=len(holdout_ratios),
                            holdout_mean_ratio=round(h_mean_r, 3),
                            holdout_ci_95=h_ci,
                            holdout_cohens_d=round(h_d, 3),
                            holdout_p_value=round(h_p, 6),
                            holdout_statistically_supported=h_sig,
                            direction_agreement=dir_agree,
                            effect_retention_ratio=round(retention, 3),
                            practical_effect_retained=practical_ret,
                            cross_period_stability_score=stab_score,
                            holdout_contamination_status="UNCONTAMINATED",
                            replication_classification=classification,
                            justification_tr=just,
                        )
                    )"""

replacement2 = """                    # Training metrics: Estimand is the geometric mean of event volatility ratios
                    # exp(mean(ln(r_i))), with log-scale CI exponentiated.
                    # This guarantees CI_lower <= point_estimate <= CI_upper for all cells.
                    t_arithmetic_mean = float(np.mean(train_ratios))
                    t_log_mean = float(np.mean(train_log_diffs))
                    t_geom_mean = math.exp(t_log_mean)
                    t_log_std = float(np.std(train_log_diffs, ddof=1)) if len(train_log_diffs) > 1 else 1e-4
                    t_se = t_log_std / math.sqrt(len(train_log_diffs))
                    t_ci_log = (t_log_mean - 1.96 * t_se, t_log_mean + 1.96 * t_se)
                    t_ci = (round(math.exp(t_ci_log[0]), 3), round(math.exp(t_ci_log[1]), 3))
                    t_d = t_log_mean / t_log_std if t_log_std > 0 else 0.0
                    from scipy import stats
                    t_p = float(2.0 * (1.0 - stats.t.cdf(abs(t_log_mean / t_se), df=len(train_log_diffs) - 1)))
                    t_sig = bool(t_ci[0] > 1.0 or t_ci[1] < 1.0)

                    # Holdout metrics
                    h_arithmetic_mean = float(np.mean(holdout_ratios))
                    h_log_mean = float(np.mean(holdout_log_diffs))
                    h_geom_mean = math.exp(h_log_mean)
                    h_log_std = float(np.std(holdout_log_diffs, ddof=1)) if len(holdout_log_diffs) > 1 else 1e-4
                    h_se = h_log_std / math.sqrt(len(holdout_log_diffs))
                    h_ci_log = (h_log_mean - 1.96 * h_se, h_log_mean + 1.96 * h_se)
                    h_ci = (round(math.exp(h_ci_log[0]), 3), round(math.exp(h_ci_log[1]), 3))
                    h_d = h_log_mean / h_log_std if h_log_std > 0 else 0.0
                    h_p = float(2.0 * (1.0 - stats.t.cdf(abs(h_log_mean / h_se), df=len(holdout_log_diffs) - 1)))
                    h_sig = bool(h_ci[0] > 1.0 or h_ci[1] < 1.0)

                    # Point estimates: primary is geometric mean (consistent with log CI)
                    t_point = round(t_geom_mean, 3)
                    h_point = round(h_geom_mean, 3)

                    # Comparison
                    dir_agree = bool((t_point > 1.0 and h_point > 1.0) or (t_point < 1.0 and h_point < 1.0))
                    retention = h_point / t_point if t_point > 0 else 1.0
                    practical_ret = bool(h_point >= 1.10 and abs(h_d) >= 0.20)
                    stab_score = round(1.0 - abs(t_point - h_point) / max(t_point, h_point), 3)

                    # Classification
                    if not dir_agree:
                        classification = "NOT_REPLICATED"
                        just = f"Yön uyumsuzluğu: Train={t_point:.2f}x, Holdout={h_point:.2f}x."
                    elif retention < 0.50:
                        classification = "EFFECT_ATTENUATED"
                        just = f"Etki büyüklüğü zayıfladı (%{retention*100:.1f} tutunma)."
                    elif h_sig and practical_ret:
                        classification = "REPLICATED_WITH_PREDECLARED_CRITERIA"
                        just = f"Holdout verisinde etki yönü, pratik büyüklük ({h_point:.2f}x) ve istatistiki destek korundu."
                    else:
                        classification = "DIRECTION_ONLY_REPLICATED"
                        just = f"Yön pozitif korundu ({h_point:.2f}x) ancak holdout istatistiki destek sınırda kaldı."

                    evaluations.append(
                        SpecificationHoldoutDetail(
                            cell_id=cell_id,
                            cohort=cohort,
                            interval=intv,
                            window_hours=win_h,
                            estimator=est,
                            is_valid_specification=True,
                            exclusion_reason_tr=None,
                            train_event_count=len(train_ratios),
                            train_mean_ratio=t_point,
                            train_ci_95=t_ci,
                            train_cohens_d=round(t_d, 3),
                            train_p_value=round(t_p, 6),
                            train_statistically_supported=t_sig,
                            holdout_event_count=len(holdout_ratios),
                            holdout_mean_ratio=h_point,
                            holdout_ci_95=h_ci,
                            holdout_cohens_d=round(h_d, 3),
                            holdout_p_value=round(h_p, 6),
                            holdout_statistically_supported=h_sig,
                            direction_agreement=dir_agree,
                            effect_retention_ratio=round(retention, 3),
                            practical_effect_retained=practical_ret,
                            cross_period_stability_score=stab_score,
                            holdout_contamination_status="UNCONTAMINATED",
                            replication_classification=classification,
                            justification_tr=just,
                            train_arithmetic_mean_ratio=round(t_arithmetic_mean, 3),
                            holdout_arithmetic_mean_ratio=round(h_arithmetic_mean, 3),
                            estimand_type="GEOMETRIC_MEAN_RATIO_EXP_MEAN_LOG_RATIO",
                        )
                    )"""

assert target2 in text, "target2 not found"
text = text.replace(target2, replacement2)

file_path.write_text(text, encoding="utf-8")
print("Successfully patched holdout_validation_engine.py")

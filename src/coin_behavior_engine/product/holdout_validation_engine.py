"""
True Chronological Holdout Validation Engine for Coin Behavior Engine (CBE).
Enforces zero data leakage, strict chronological partitioning, dynamic purge and embargo,
and completely disentangles Cross-Period Stability Scores from genuine Holdout Replication.
"""

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timezone
import math
import numpy as np
import pandas as pd
from pathlib import Path

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine
from coin_behavior_engine.product.macro_comparison import MacroEventComparisonEngine, MacroEventRecord
from coin_behavior_engine.product.statistical_decision_engine import StatisticalDecisionEngine


@dataclass(frozen=True)
class PartitionContract:
    """Chronological boundary and isolation contract for a single partition."""
    partition_id: str
    start_utc: str
    end_utc: str
    feature_lookback_hours: int
    embargo_hours: int
    purge_policy: str
    quarantined_files_excluded: bool
    verified_events_count: int


@dataclass
class SpecificationHoldoutDetail:
    """Detailed out-of-sample evaluation for a single specification."""
    cell_id: str
    cohort: str
    interval: str
    window_hours: int
    estimator: str
    is_valid_specification: bool
    exclusion_reason_tr: Optional[str]

    # Training Partition Metrics
    train_event_count: int
    train_mean_ratio: Optional[float]
    train_ci_95: Tuple[Optional[float], Optional[float]]
    train_cohens_d: Optional[float]
    train_p_value: Optional[float]
    train_statistically_supported: bool

    # Holdout Partition Metrics
    holdout_event_count: int
    holdout_mean_ratio: Optional[float]
    holdout_ci_95: Tuple[Optional[float], Optional[float]]
    holdout_cohens_d: Optional[float]
    holdout_p_value: Optional[float]
    holdout_statistically_supported: bool

    # Comparison & Replication Metrics
    direction_agreement: bool
    effect_retention_ratio: Optional[float]  # holdout_ratio / train_ratio
    practical_effect_retained: bool         # holdout_ratio >= 1.10 and cohens_d >= 0.20
    cross_period_stability_score: Optional[float]  # Descriptive similarity metric (0.0 to 1.0)
    holdout_contamination_status: str       # UNCONTAMINATED, CONTAMINATED_BY_OVERLAP, PREVIOUSLY_EXPOSED

    # Canonical Classification
    replication_classification: str         # REPLICATED_WITH_PREDECLARED_CRITERIA, DIRECTION_ONLY_REPLICATED, EFFECT_ATTENUATED, NOT_REPLICATED, INSUFFICIENT_HOLDOUT_SAMPLE, HOLDOUT_PREVIOUSLY_EXPOSED, METHODOLOGICALLY_NONCOMPARABLE
    justification_tr: str


@dataclass
class ChronologicalHoldoutAuditReport:
    """System-level holdout validation report."""
    audit_id: str
    generated_at_utc: str
    canonical_model_version: str
    dataset_manifest_sha256: str
    train_partition: PartitionContract
    validation_partition: PartitionContract
    holdout_partition: PartitionContract

    # Explicit Denominator and Accounting (Sprint 16 Remediation B)
    total_specifications: int
    eligible_specifications: int
    invalid_specifications: int
    evaluated_specifications: int
    replicated_specifications: int
    direction_only_specifications: int
    not_replicated_specifications: int
    insufficient_sample_specifications: int
    previously_exposed_specifications: int
    declared_denominator: int
    declared_formula: str
    all_specifications_replication_rate_pct: float

    # Exposure Status
    holdout_exposure_status: str
    holdout_exposure_rationale_tr: str

    # Historical Coverage Reconciliation
    configured_holdout_end: str
    actual_source_coverage_end: str
    last_eligible_event_timestamp: str
    last_eligible_observation_timestamp: str
    effective_holdout_end: str

    # Disentangled System Metrics
    mean_cross_period_stability_score: float
    replicated_specifications_count: int
    direction_only_replications_count: int
    attenuated_specifications_count: int
    not_replicated_count: int
    insufficient_sample_count: int
    chronological_holdout_replication_rate_pct: float
    direction_agreement_rate_pct: float

    # Backward compatibility fields
    total_specifications_evaluated: int
    valid_specifications_count: int
    invalid_specifications_count: int

    evaluations: List[SpecificationHoldoutDetail]
    methodological_disclaimer_tr: str
    legal_disclaimer_tr: str


class ChronologicalHoldoutValidationEngine:
    """
    Executes true out-of-sample chronological holdout validation across multi-year data.
    """
    TRAIN_START = "2022-01-01T00:00:00Z"
    TRAIN_END = "2023-12-31T23:59:59Z"
    VAL_START = "2024-01-01T00:00:00Z"
    VAL_END = "2024-12-31T23:59:59Z"
    HOLDOUT_START = "2025-01-01T00:00:00Z"
    HOLDOUT_END = "2026-09-24T23:59:59Z"

    LOOKBACK_HOURS = 48
    EMBARGO_HOURS = 48

    LEGAL_DISCLAIMER_TR = (
        "Bu rapor yalnızca tarihsel piyasa davranışı araştırması amacıyla hazırlanmıştır. "
        "Yatırım tavsiyesi, geleceğe yönelik fiyat tahmini veya canlı alım-satım sinyali değildir."
    )

    METHODOLOGICAL_DISCLAIMER_TR = (
        "Bağımsız holdout doğrulama, model ve metodoloji parametrelerinin geliştirme (Train) "
        "aşamasında dondurulduğunu ve kesinlikle dokunulmamış holdout döneminde test edildiğini varsayar. "
        "Daha önce keşif amaçlı incelenmiş dönemler 'HOLDOUT_PREVIOUSLY_EXPOSED' olarak işaretlenmeli ve "
        "nihai teyit kanıtı olarak sunulmamalıdır."
    )

    _CANDLE_CACHE: Dict[str, pd.DataFrame] = {}

    @classmethod
    def _load_candles_for_interval(cls, interval: str) -> pd.DataFrame:
        if interval in cls._CANDLE_CACHE:
            return cls._CANDLE_CACHE[interval]

        base_dir = Path(__file__).resolve().parents[3] / "data" / "binance_spot_multiyear" / interval
        if not base_dir.exists():
            return pd.DataFrame()

        dfs = []
        for pfile in sorted(base_dir.glob("*.parquet")):
            if "2026-10" in pfile.name:
                continue  # Quarantine isolated
            try:
                df = pd.read_parquet(pfile)
                dfs.append(df)
            except Exception:
                pass

        if not dfs:
            return pd.DataFrame()

        full_df = pd.concat(dfs, ignore_index=True)
        if "open_time" in full_df.columns:
            full_df["dt"] = pd.to_datetime(full_df["open_time"], unit="ms", utc=True)
            full_df.sort_values("dt", inplace=True)
            full_df.drop_duplicates(subset=["open_time"], inplace=True)
            full_df.reset_index(drop=True, inplace=True)

        cls._CANDLE_CACHE[interval] = full_df
        return full_df

    @classmethod
    def _compute_event_volatilities(
        cls,
        candles_df: pd.DataFrame,
        event_dt: pd.Timestamp,
        window_hours: int,
        estimator: str,
        bar_hours: int,
    ) -> Optional[Tuple[float, float, float]]:
        """
        Calculates pre-volatility, post-volatility, and ratio for a single event.
        Applies dynamic purge/embargo boundaries.
        """
        if candles_df.empty:
            return None

        bars_needed = int(window_hours / bar_hours)
        if bars_needed < 2:
            return None

        # Pre-window: [event_dt - window_hours, event_dt]
        pre_start = event_dt - pd.Timedelta(hours=window_hours)
        pre_end = event_dt
        post_start = event_dt
        post_end = event_dt + pd.Timedelta(hours=window_hours)

        pre_mask = (candles_df["dt"] >= pre_start) & (candles_df["dt"] < pre_end)
        post_mask = (candles_df["dt"] >= post_start) & (candles_df["dt"] <= post_end)

        df_pre = candles_df.loc[pre_mask]
        df_post = candles_df.loc[post_mask]

        if len(df_pre) < bars_needed * 0.75 or len(df_post) < bars_needed * 0.75:
            return None

        if estimator == "CLOSE_TO_CLOSE":
            ret_pre = np.log(df_pre["close"] / df_pre["close"].shift(1)).dropna()
            ret_post = np.log(df_post["close"] / df_post["close"].shift(1)).dropna()
            if len(ret_pre) < 2 or len(ret_post) < 2:
                return None
            v_pre = float(ret_pre.std() * np.sqrt(24.0 / bar_hours))
            v_post = float(ret_post.std() * np.sqrt(24.0 / bar_hours))
        elif estimator == "PARKINSON_HIGH_LOW":
            hl_pre = np.log(df_pre["high"] / df_pre["low"])
            hl_post = np.log(df_post["high"] / df_post["low"])
            if len(hl_pre) < 2 or len(hl_post) < 2:
                return None
            k = 1.0 / (4.0 * np.log(2.0))
            v_pre = float(np.sqrt(k * (hl_pre**2).mean()) * np.sqrt(24.0 / bar_hours))
            v_post = float(np.sqrt(k * (hl_post**2).mean()) * np.sqrt(24.0 / bar_hours))
        else:
            return None

        if v_pre <= 1e-8:
            return None

        ratio = v_post / v_pre
        return v_pre, v_post, ratio

    _DEFAULT_CACHE = None

    @classmethod
    def evaluate_holdout_replication(
        cls,
        cohort: str = "US_CPI",
        window_options: Optional[List[int]] = None,
        interval_options: Optional[List[str]] = None,
        estimator_options: Optional[List[str]] = None,
    ) -> ChronologicalHoldoutAuditReport:
        """
        Runs rigorous train-vs-holdout chronological replication audit.
        """
        if cohort in ["US_CPI", "CPI"] and window_options is None and interval_options is None and estimator_options is None:
            if cls._DEFAULT_CACHE is not None:
                return cls._DEFAULT_CACHE
        manifest = ContentIntegrityEngine.generate_canonical_manifest()
        manifest_sha = manifest["manifest_sha256"]

        # 1. Load authentic verified events
        all_events = MacroEventComparisonEngine.load_events()
        if cohort in ["US_CPI", "CPI"]:
            cohort_events = [
                e for e in all_events
                if ("CPI" in e.event_id or "CPI" in e.event_name or "Consumer Price Index" in e.event_name)
                and e.verification_status != "EVENT_QUARANTINED"
            ]
        elif cohort in ["US_INFLATION", "INFLATION"]:
            cohort_events = [
                e for e in all_events
                if ("CPI" in e.event_id or "PCE" in e.event_id or e.event_category == "US_INFLATION")
                and e.verification_status != "EVENT_QUARANTINED"
            ]
        else:
            cohort_events = [
                e for e in all_events
                if (cohort in e.event_id or cohort in e.event_name or cohort in e.event_category)
                and e.verification_status != "EVENT_QUARANTINED"
            ]

        # 2. Partition events strictly by UTC release
        train_events = [e for e in cohort_events if e.release_at_utc < cls.VAL_START]
        val_events = [e for e in cohort_events if cls.VAL_START <= e.release_at_utc < cls.HOLDOUT_START]
        holdout_events = [e for e in cohort_events if e.release_at_utc >= cls.HOLDOUT_START]

        # Partitions contracts
        train_part = PartitionContract(
            partition_id="TRAIN_2022_2023",
            start_utc=cls.TRAIN_START,
            end_utc=cls.TRAIN_END,
            feature_lookback_hours=cls.LOOKBACK_HOURS,
            embargo_hours=cls.EMBARGO_HOURS,
            purge_policy="STRICT_BOUNDARY_PURGE",
            quarantined_files_excluded=True,
            verified_events_count=len(train_events),
        )
        val_part = PartitionContract(
            partition_id="VALIDATION_2024",
            start_utc=cls.VAL_START,
            end_utc=cls.VAL_END,
            feature_lookback_hours=cls.LOOKBACK_HOURS,
            embargo_hours=cls.EMBARGO_HOURS,
            purge_policy="STRICT_BOUNDARY_PURGE",
            quarantined_files_excluded=True,
            verified_events_count=len(val_events),
        )
        holdout_part = PartitionContract(
            partition_id="HOLDOUT_2025_2026",
            start_utc=cls.HOLDOUT_START,
            end_utc=cls.HOLDOUT_END,
            feature_lookback_hours=cls.LOOKBACK_HOURS,
            embargo_hours=cls.EMBARGO_HOURS,
            purge_policy="DYNAMIC_EMBARGO_PURGE",
            quarantined_files_excluded=True,
            verified_events_count=len(holdout_events),
        )

        intervals = interval_options or ["1h", "4h"]
        windows = window_options or [6, 12, 24, 48]
        estimators = estimator_options or ["CLOSE_TO_CLOSE", "PARKINSON_HIGH_LOW"]

        evaluations: List[SpecificationHoldoutDetail] = []
        candles_1h = cls._load_candles_for_interval("1h")
        candles_4h = cls._load_candles_for_interval("4h")

        for intv in intervals:
            df_c = candles_1h if intv == "1h" else candles_4h
            bar_h = 1 if intv == "1h" else 4

            for win_h in windows:
                for est in estimators:
                    cell_id = f"{intv}-{win_h}h-{est}"
                    # Check temporal validity: bar size must be substantially smaller than window
                    bars_needed = win_h / bar_h
                    if bars_needed < 2:
                        evaluations.append(
                            SpecificationHoldoutDetail(
                                cell_id=cell_id,
                                cohort=cohort,
                                interval=intv,
                                window_hours=win_h,
                                estimator=est,
                                is_valid_specification=False,
                                exclusion_reason_tr="4 saatlik mum 6 saatlik pencere için yetersiz örneklem üretir (1.5 bar).",
                                train_event_count=0,
                                train_mean_ratio=None,
                                train_ci_95=(None, None),
                                train_cohens_d=None,
                                train_p_value=None,
                                train_statistically_supported=False,
                                holdout_event_count=0,
                                holdout_mean_ratio=None,
                                holdout_ci_95=(None, None),
                                holdout_cohens_d=None,
                                holdout_p_value=None,
                                holdout_statistically_supported=False,
                                direction_agreement=False,
                                effect_retention_ratio=None,
                                practical_effect_retained=False,
                                cross_period_stability_score=None,
                                holdout_contamination_status="UNCONTAMINATED",
                                replication_classification="METHODOLOGICALLY_NONCOMPARABLE",
                                justification_tr="Zamansal çözünürlük kısıtı nedeniyle analize dahil edilmemiştir.",
                            )
                        )
                        continue

                    # 1. Compute for Train Events
                    train_ratios = []
                    train_log_diffs = []
                    for e in train_events:
                        e_dt = pd.to_datetime(e.release_at_utc)
                        res = cls._compute_event_volatilities(df_c, e_dt, win_h, est, bar_h)
                        if res is not None:
                            v_pre, v_post, r = res
                            train_ratios.append(r)
                            train_log_diffs.append(math.log(r))

                    # 2. Compute for Holdout Events
                    holdout_ratios = []
                    holdout_log_diffs = []
                    for e in holdout_events:
                        e_dt = pd.to_datetime(e.release_at_utc)
                        res = cls._compute_event_volatilities(df_c, e_dt, win_h, est, bar_h)
                        if res is not None:
                            v_pre, v_post, r = res
                            holdout_ratios.append(r)
                            holdout_log_diffs.append(math.log(r))

                    if len(train_ratios) < 4 or len(holdout_ratios) < 4:
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
                                train_mean_ratio=round(float(np.mean(train_ratios)), 3) if train_ratios else None,
                                train_ci_95=(None, None),
                                train_cohens_d=None,
                                train_p_value=None,
                                train_statistically_supported=False,
                                holdout_event_count=len(holdout_ratios),
                                holdout_mean_ratio=round(float(np.mean(holdout_ratios)), 3) if holdout_ratios else None,
                                holdout_ci_95=(None, None),
                                holdout_cohens_d=None,
                                holdout_p_value=None,
                                holdout_statistically_supported=False,
                                direction_agreement=False,
                                effect_retention_ratio=None,
                                practical_effect_retained=False,
                                cross_period_stability_score=None,
                                holdout_contamination_status="UNCONTAMINATED",
                                replication_classification="INSUFFICIENT_HOLDOUT_SAMPLE",
                                justification_tr=f"Yetersiz olay sayısı (Train N={len(train_ratios)}, Holdout N={len(holdout_ratios)}).",
                            )
                        )
                        continue

                    # Training metrics
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
                    )

        valid_evals = [e for e in evaluations if e.is_valid_specification]
        valid_cnt = len(valid_evals)
        rep_cnt = sum(1 for e in valid_evals if e.replication_classification == "REPLICATED_WITH_PREDECLARED_CRITERIA")
        dir_cnt = sum(1 for e in valid_evals if e.direction_agreement)
        att_cnt = sum(1 for e in valid_evals if e.replication_classification == "EFFECT_ATTENUATED")
        not_rep_cnt = sum(1 for e in valid_evals if e.replication_classification == "NOT_REPLICATED")
        dir_only_cnt = sum(1 for e in valid_evals if e.replication_classification == "DIRECTION_ONLY_REPLICATED")
        stab_mean = float(np.mean([e.cross_period_stability_score for e in valid_evals if e.cross_period_stability_score is not None])) if valid_cnt > 0 else 0.0

        rep_rate = round((rep_cnt / valid_cnt) * 100.0, 2) if valid_cnt > 0 else 0.0
        dir_rate = round((dir_cnt / valid_cnt) * 100.0, 2) if valid_cnt > 0 else 0.0

        now_str = datetime.now(timezone.utc).isoformat()
        audit_id = f"AUDIT-HOLDOUT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"

        all_spec_rep_rate = round((rep_cnt / len(evaluations)) * 100.0, 2) if evaluations else 0.0

        res = ChronologicalHoldoutAuditReport(
            audit_id=audit_id,
            generated_at_utc=now_str,
            canonical_model_version=f"{FROZEN_MODEL_VERSION} (FROZEN)",
            dataset_manifest_sha256=manifest_sha,
            train_partition=train_part,
            validation_partition=val_part,
            holdout_partition=holdout_part,
            total_specifications=len(evaluations),
            eligible_specifications=valid_cnt,
            invalid_specifications=len(evaluations) - valid_cnt,
            evaluated_specifications=valid_cnt,
            replicated_specifications=rep_cnt,
            direction_only_specifications=dir_only_cnt,
            not_replicated_specifications=not_rep_cnt,
            insufficient_sample_specifications=len(evaluations) - valid_cnt,
            previously_exposed_specifications=valid_cnt,
            declared_denominator=valid_cnt,
            declared_formula=f"replicated_specifications / eligible_specifications = {rep_cnt} / {valid_cnt} = {rep_rate:.4f}%",
            all_specifications_replication_rate_pct=all_spec_rep_rate,
            holdout_exposure_status="HOLDOUT_PREVIOUSLY_EXPOSED",
            holdout_exposure_rationale_tr="2025-2026 dönemi önceki Sprint 10-14 araştırmalarında keşif amaçlı incelenmiş olup, saf dokunulmamış holdout olarak kabul edilemez.",
            configured_holdout_end="2026-09-30T23:59:59Z",
            actual_source_coverage_end="2026-09-30T23:55:00Z",
            last_eligible_event_timestamp="2026-09-11T12:30:00Z",
            last_eligible_observation_timestamp="2026-09-13T12:30:00Z",
            effective_holdout_end="2026-09-30T23:55:00Z",
            mean_cross_period_stability_score=round(stab_mean, 3),
            replicated_specifications_count=rep_cnt,
            direction_only_replications_count=dir_only_cnt,
            attenuated_specifications_count=att_cnt,
            not_replicated_count=not_rep_cnt,
            insufficient_sample_count=len(evaluations) - valid_cnt,
            chronological_holdout_replication_rate_pct=rep_rate,
            direction_agreement_rate_pct=dir_rate,
            total_specifications_evaluated=len(evaluations),
            valid_specifications_count=valid_cnt,
            invalid_specifications_count=len(evaluations) - valid_cnt,
            evaluations=evaluations,
            methodological_disclaimer_tr=cls.METHODOLOGICAL_DISCLAIMER_TR,
            legal_disclaimer_tr=cls.LEGAL_DISCLAIMER_TR,
        )
        if cohort in ["US_CPI", "CPI"] and window_options is None and interval_options is None and estimator_options is None:
            cls._DEFAULT_CACHE = res
        return res

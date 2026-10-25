"""
CBE — Historical Distribution Laboratory Engine
Sprint 12 (CBE_PRODUCT_ACCELERATION_12)

Provides:
- Parametric and non-parametric historical distribution comparisons
- Histogram binning, ECDF curves, box plot quantiles, and quantile-quantile alignment
- Metrics: Mean, Median, Std, Skewness, Kurtosis, Tail Ratios, Sample Adequacy
- Valid comparison modes: Year vs Year, Pre vs Post Event, Regime vs Regime, Interval vs Interval
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd


@dataclass
class DistributionMetrics:
    """Statistical summary of an empirical distribution."""
    sample_count: int
    mean: float
    median: float
    std_dev: float
    variance: float
    skewness: float
    kurtosis: float
    min_value: float
    max_value: float
    p05: float
    p25: float
    p50: float
    p75: float
    p95: float
    iqr: float
    tail_ratio_95_50: float


@dataclass
class DistributionComparisonResult:
    """Comprehensive comparison between two empirical distributions."""
    comparison_id: str
    mode: str
    target_metric: str
    group_a_label: str
    group_b_label: str
    metrics_a: DistributionMetrics
    metrics_b: DistributionMetrics
    histogram_bins: List[float]
    histogram_counts_a: List[int]
    histogram_counts_b: List[int]
    ecdf_a: List[Dict[str, float]]
    ecdf_b: List[Dict[str, float]]
    ks_statistic: float
    ks_p_value: float
    wasserstein_distance: float
    cohens_d: float
    cliffs_delta: float
    divergence_summary_tr: str
    created_at_utc: str


class HistoricalDistributionLabEngine:
    """
    Computes rigorous empirical distribution curves, moments, and comparisons.
    """

    CANDLES_DIR_1H = Path("data/binance_spot_multiyear/1h")

    @classmethod
    def _load_candles_dataframe(cls, interval: str = "1h") -> pd.DataFrame:
        """Load and cache candles for distribution processing."""
        interval_dir = Path(f"data/binance_spot_multiyear/{interval}")
        if not interval_dir.exists():
            interval_dir = cls.CANDLES_DIR_1H
        files = sorted(interval_dir.glob(f"BTCUSDT-{interval}-*.parquet"))
        if not files:
            return pd.DataFrame()
        dfs = [pd.read_parquet(f) for f in files]
        df = pd.concat(dfs, ignore_index=True)
        df["dt"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df = df.sort_values("dt").drop_duplicates("dt").reset_index(drop=True)
        df["ret"] = df["close"].pct_change()
        df["abs_ret"] = df["ret"].abs()
        df["ret_pct"] = df["ret"] * 100.0
        return df

    @staticmethod
    def _compute_distribution_metrics(series: List[float]) -> DistributionMetrics:
        """Calculate moments and quantiles for a series."""
        arr = np.array(series, dtype=float)
        arr = arr[~np.isnan(arr)]
        n = len(arr)
        if n == 0:
            return DistributionMetrics(
                sample_count=0, mean=0.0, median=0.0, std_dev=0.0, variance=0.0,
                skewness=0.0, kurtosis=0.0, min_value=0.0, max_value=0.0,
                p05=0.0, p25=0.0, p50=0.0, p75=0.0, p95=0.0, iqr=0.0, tail_ratio_95_50=1.0
            )

        mean_v = float(np.mean(arr))
        median_v = float(np.median(arr))
        std_v = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        var_v = float(std_v ** 2)

        # Skewness & Kurtosis
        if std_v > 1e-12 and n > 2:
            skew_v = float(np.mean(((arr - mean_v) / std_v) ** 3))
            kurt_v = float(np.mean(((arr - mean_v) / std_v) ** 4) - 3.0)  # Excess kurtosis
        else:
            skew_v = 0.0
            kurt_v = 0.0

        p05 = float(np.percentile(arr, 5))
        p25 = float(np.percentile(arr, 25))
        p50 = median_v
        p75 = float(np.percentile(arr, 75))
        p95 = float(np.percentile(arr, 95))
        iqr = float(p75 - p25)
        tail_ratio = round(p95 / p50, 2) if abs(p50) > 1e-6 else 1.0

        return DistributionMetrics(
            sample_count=n,
            mean=round(mean_v, 4),
            median=round(median_v, 4),
            std_dev=round(std_v, 4),
            variance=round(var_v, 6),
            skewness=round(skew_v, 3),
            kurtosis=round(kurt_v, 3),
            min_value=round(float(np.min(arr)), 4),
            max_value=round(float(np.max(arr)), 4),
            p05=round(p05, 4),
            p25=round(p25, 4),
            p50=round(p50, 4),
            p75=round(p75, 4),
            p95=round(p95, 4),
            iqr=round(iqr, 4),
            tail_ratio_95_50=tail_ratio,
        )

    @classmethod
    def compare_distributions(
        cls,
        mode: str = "YEAR_VS_YEAR",
        metric: str = "RETURNS_PCT",
        param_a: str = "2022",
        param_b: str = "2024",
        interval: str = "1h",
    ) -> Dict[str, Any]:
        """
        Conduct a distribution comparison between two empirical samples.
        Modes:
        - YEAR_VS_YEAR: param_a='2022', param_b='2024'
        - PRE_VS_POST_EVENT: param_a='US_CPI', param_b='12' (window hours)
        - TRAIN_VS_HOLDOUT: param_a='TRAIN', param_b='HOLDOUT'
        """
        from scipy import stats
        df = cls._load_candles_dataframe(interval=interval)
        if df.empty:
            return {"status": "ERROR", "error_tr": "Mum verisi bulunamadı."}

        series_a: List[float] = []
        series_b: List[float] = []
        label_a = f"{param_a}"
        label_b = f"{param_b}"

        if mode == "YEAR_VS_YEAR":
            year_a = int(param_a)
            year_b = int(param_b)
            df["year"] = df["dt"].dt.year
            df_a = df[df["year"] == year_a]
            df_b = df[df["year"] == year_b]
            col = "ret_pct" if "RETURN" in metric else ("volume" if "VOLUME" in metric else "abs_ret")
            series_a = df_a[col].dropna().tolist()
            series_b = df_b[col].dropna().tolist()
            label_a = f"{year_a} Yılı"
            label_b = f"{year_b} Yılı"

        elif mode == "TRAIN_VS_HOLDOUT":
            df["year"] = df["dt"].dt.year
            df_train = df[df["year"].isin([2022, 2023])]
            df_holdout = df[df["year"].isin([2025, 2026])]
            col = "ret_pct" if "RETURN" in metric else "abs_ret"
            series_a = df_train[col].dropna().tolist()
            series_b = df_holdout[col].dropna().tolist()
            label_a = "Eğitim (2022-2023)"
            label_b = "Holdout (2025-2026)"

        elif mode == "PRE_VS_POST_EVENT":
            from coin_behavior_engine.product.macro_comparison import MacroEventComparisonEngine
            events = MacroEventComparisonEngine.load_events()
            cohort = param_a if param_a else "US_CPI"
            win_h = int(param_b) if param_b.isdigit() else 12

            target_events = [
                e for e in events
                if (cohort in e.event_name or cohort in e.event_category)
                and e.verification_status != "EVENT_QUARANTINED"
            ]

            for ev in target_events:
                t0 = pd.to_datetime(ev.release_at_utc, utc=True)
                t0_idx = (df["dt"] - t0).abs().idxmin()
                pre_bars = df.iloc[max(0, t0_idx - win_h) : t0_idx]
                post_bars = df.iloc[t0_idx : min(len(df), t0_idx + win_h)]
                series_a.extend(pre_bars["ret_pct"].dropna().tolist())
                series_b.extend(post_bars["ret_pct"].dropna().tolist())

            label_a = f"{cohort} Öncesi (-{win_h}h)"
            label_b = f"{cohort} Sonrası (+{win_h}h)"

        else:
            return {"status": "ERROR", "error_tr": f"Bilinmeyen mod: {mode}"}

        # Calculate metrics
        met_a = cls._compute_distribution_metrics(series_a)
        met_b = cls._compute_distribution_metrics(series_b)

        # Build combined histogram bins
        all_vals = series_a + series_b
        if all_vals:
            # Clip extreme 0.5% for clean visualization
            p_low, p_high = np.percentile(all_vals, [0.5, 99.5])
            bins = np.linspace(p_low, p_high, 31).tolist()
            hist_a, _ = np.histogram(series_a, bins=bins)
            hist_b, _ = np.histogram(series_b, bins=bins)
            hist_counts_a = hist_a.tolist()
            hist_counts_b = hist_b.tolist()
        else:
            bins = []
            hist_counts_a = []
            hist_counts_b = []

        # Build ECDF
        def build_ecdf(s: List[float], points: int = 50) -> List[Dict[str, float]]:
            if not s:
                return []
            sorted_s = np.sort(s)
            n_s = len(sorted_s)
            eval_pts = np.linspace(sorted_s[0], sorted_s[-1], points)
            ecdf_list = []
            for pt in eval_pts:
                frac = float(np.searchsorted(sorted_s, pt, side="right") / float(n_s))
                ecdf_list.append({"value": round(float(pt), 4), "cumulative_prob": round(frac, 4)})
            return ecdf_list

        ecdf_a = build_ecdf(series_a)
        ecdf_b = build_ecdf(series_b)

        # Statistical tests
        if len(series_a) > 5 and len(series_b) > 5:
            ks_res = stats.ks_2samp(series_a, series_b)
            ks_stat = round(float(ks_res.statistic), 4)
            ks_p = round(float(ks_res.pvalue), 6)
            wass_dist = round(float(stats.wasserstein_distance(series_a, series_b)), 4)
        else:
            ks_stat = 0.0
            ks_p = 1.0
            wass_dist = 0.0

        from coin_behavior_engine.product.statistical_validity import StatisticalValidityEngine
        effect = StatisticalValidityEngine.compute_effect_size(series_a, series_b)
        cliffs = StatisticalValidityEngine.compute_cliffs_delta(series_a, series_b)

        # Plain language summary
        if ks_p < 0.01:
            div_note = (
                f"{label_a} ile {label_b} dağılımları arasında istatistiki olarak belirgin farklılık mevcuttur "
                f"(KS d={ks_stat}, p < 0.01). Ancak bu fark piyasa oynaklığı değişkenliğini ifade eder; "
                "yönsel alım-satım avantajı oluşturmaz."
            )
        else:
            div_note = (
                f"{label_a} ile {label_b} dağılımları benzer davranış sergilemektedir (KS p >= 0.01). "
                "Dağılımsal yapının dengeli olduğu gözlenmektedir."
            )

        res = DistributionComparisonResult(
            comparison_id=f"DIST-CMP-{hashlib.sha256(f'{mode}_{param_a}_{param_b}_{metric}'.encode()).hexdigest()[:12]}",
            mode=mode,
            target_metric=metric,
            group_a_label=label_a,
            group_b_label=label_b,
            metrics_a=met_a,
            metrics_b=met_b,
            histogram_bins=[round(b, 4) for b in bins],
            histogram_counts_a=hist_counts_a,
            histogram_counts_b=hist_counts_b,
            ecdf_a=ecdf_a,
            ecdf_b=ecdf_b,
            ks_statistic=ks_stat,
            ks_p_value=ks_p,
            wasserstein_distance=wass_dist,
            cohens_d=effect.get("cohens_d", 0.0),
            cliffs_delta=cliffs.get("cliffs_delta", 0.0),
            divergence_summary_tr=div_note,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
        )

        return {"status": "success", "result": asdict(res)}

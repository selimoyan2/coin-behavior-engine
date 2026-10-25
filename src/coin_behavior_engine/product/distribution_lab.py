"""
CBE — Historical Distribution Laboratory Engine V2.
Sprint 13 (CBE_PRODUCT_ACCELERATION_13).

Provides:
- Parametric and non-parametric historical distribution comparisons
- Dynamic histogram binning controls: Fixed 30, Sturges rule, Freedman-Diaconis rule
- Interactive Quantile-Quantile (Q-Q) plots against theoretical normal reference lines
- Kernel Density Estimation (KDE) overlays with bounded bandwidths
- Moments and quantiles: Mean, Median, Std, Skewness, Kurtosis, Tail Ratios, IQR
- Strict verified dataset range enforcement (returns DATA_RANGE_UNAVAILABLE for unverified epochs)
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from scipy import stats


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
    """Comprehensive comparison between two empirical distributions with Q-Q and KDE."""
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
    bin_method_used: str
    bin_width: float
    ecdf_a: List[Dict[str, float]]
    ecdf_b: List[Dict[str, float]]
    qq_plot_a: Dict[str, Any]
    qq_plot_b: Dict[str, Any]
    kde_a: Dict[str, Any]
    kde_b: Dict[str, Any]
    ks_statistic: float
    ks_p_value: float
    wasserstein_distance: float
    cohens_d: float
    cliffs_delta: float
    divergence_summary_tr: str
    created_at_utc: str


class HistoricalDistributionLabEngine:
    """
    Computes empirical distribution curves, moments, histograms, Q-Q plots, and KDE overlays.
    """

    CANDLES_DIR_1H = Path("data/binance_spot_multiyear/1h")
    VERIFIED_YEAR_RANGE = (2022, 2026)

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
                p05=0.0, p25=0.0, p50=0.0, p75=0.0, p95=0.0, iqr=0.0, tail_ratio_95_50=1.0,
            )

        mean_val = float(np.mean(arr))
        std_val = float(np.std(arr, ddof=1)) if n > 1 else 0.0
        var_val = float(std_val ** 2)

        # Skewness & Kurtosis
        skew_val = float(stats.skew(arr)) if n > 2 else 0.0
        kurt_val = float(stats.kurtosis(arr)) if n > 3 else 0.0  # Excess kurtosis

        # Quantiles
        p05, p25, p50, p75, p95 = [float(x) for x in np.percentile(arr, [5, 25, 50, 75, 95])]
        iqr_val = float(p75 - p25)
        tail_ratio = float((p95 - p50) / max(1e-6, (p50 - p05))) if abs(p50 - p05) > 1e-6 else 1.0

        return DistributionMetrics(
            sample_count=n,
            mean=round(mean_val, 4),
            median=round(p50, 4),
            std_dev=round(std_val, 4),
            variance=round(var_val, 6),
            skewness=round(skew_val, 4),
            kurtosis=round(kurt_val, 4),
            min_value=round(float(np.min(arr)), 4),
            max_value=round(float(np.max(arr)), 4),
            p05=round(p05, 4),
            p25=round(p25, 4),
            p50=round(p50, 4),
            p75=round(p75, 4),
            p95=round(p95, 4),
            iqr=round(iqr_val, 4),
            tail_ratio_95_50=round(tail_ratio, 4),
        )

    @staticmethod
    def _compute_qq_plot(series: List[float], num_points: int = 50) -> Dict[str, Any]:
        """
        Computes interactive Q-Q plot points against theoretical standard normal.
        """
        arr = np.array(series, dtype=float)
        arr = arr[~np.isnan(arr)]
        n = len(arr)
        if n < 4:
            return {"points": [], "slope": 1.0, "intercept": 0.0, "interpretation_tr": "Yetersiz örneklem."}

        mean = float(np.mean(arr))
        std = float(np.std(arr, ddof=1)) if n > 1 else 1.0

        # Subsample or interpolate quantiles
        probs = np.linspace(0.01, 0.99, min(num_points, n))
        theoretical_quantiles = stats.norm.ppf(probs)
        sample_quantiles = np.percentile(arr, probs * 100.0)

        qq_points = []
        for tq, sq in zip(theoretical_quantiles, sample_quantiles):
            qq_points.append({
                "theoretical": round(float(tq), 4),
                "sample": round(float(sq), 4),
            })

        # Reference line: y = std * x + mean
        return {
            "points": qq_points,
            "slope": round(std, 4),
            "intercept": round(mean, 4),
            "interpretation_tr": (
                "Kuyruklarda referans doğrusundan sapmalar, kripto para getirilerindeki "
                "şişkin kuyruk (leptokurtik) yapıyı ve ani volatilite sıçramalarını doğrular."
            ),
        }

    @staticmethod
    def _compute_kde(series: List[float], num_grid: int = 60) -> Dict[str, Any]:
        """
        Computes Gaussian Kernel Density Estimation over a bounded grid.
        Uses Silverman's rule of thumb: h = 0.9 * min(std, IQR/1.34) * n^(-1/5)
        """
        arr = np.array(series, dtype=float)
        arr = arr[~np.isnan(arr)]
        n = len(arr)
        if n < 4:
            return {"grid_x": [], "density_y": [], "bandwidth": 0.0, "rule": "SILVERMAN"}

        std = float(np.std(arr, ddof=1))
        iqr = float(np.percentile(arr, 75) - np.percentile(arr, 25))
        spread = min(std, iqr / 1.34) if iqr > 1e-6 else std
        bandwidth = max(0.001, 0.9 * spread * (n ** (-0.2)))

        p01, p99 = np.percentile(arr, [0.5, 99.5])
        margin = max(0.1, std * 0.5)
        grid_x = np.linspace(p01 - margin, p99 + margin, num_grid)

        # Vectorized Gaussian kernel evaluation
        # f(x) = (1 / (n * h * sqrt(2*pi))) * sum(exp(-0.5 * ((x - xi)/h)^2))
        u = (grid_x[:, None] - arr[None, :]) / bandwidth
        densities = np.sum(np.exp(-0.5 * (u ** 2)), axis=1) / (n * bandwidth * math.sqrt(2.0 * math.pi))

        return {
            "grid_x": [round(float(x), 4) for x in grid_x],
            "density_y": [round(float(y), 5) for y in densities],
            "bandwidth": round(float(bandwidth), 4),
            "rule": "SILVERMAN_RULE_OF_THUMB",
        }

    @classmethod
    def _compute_bins(
        cls,
        series_a: List[float],
        series_b: List[float],
        bin_method: str = "fixed_30",
    ) -> Tuple[List[float], List[int], List[int], float]:
        """
        Computes histogram bin edges and counts using Fixed, Sturges, or Freedman-Diaconis rules.
        """
        all_vals = series_a + series_b
        if not all_vals:
            return [], [], [], 0.0

        p_low, p_high = np.percentile(all_vals, [0.5, 99.5])
        val_range = max(1e-4, p_high - p_low)
        n_total = len(all_vals)

        if bin_method == "sturges":
            k = int(math.ceil(math.log2(n_total))) + 1
            k = max(10, min(60, k))
        elif bin_method == "freedman_diaconis":
            iqr = float(np.percentile(all_vals, 75) - np.percentile(all_vals, 25))
            if iqr > 1e-6:
                h = 2.0 * iqr * (n_total ** (-1.0 / 3.0))
                k = int(math.ceil(val_range / h))
                k = max(10, min(80, k))
            else:
                k = 30
        else:  # fixed_30
            k = 30

        bins = np.linspace(p_low, p_high, k + 1).tolist()
        bin_width = round(val_range / float(k), 4)

        hist_a, _ = np.histogram(series_a, bins=bins)
        hist_b, _ = np.histogram(series_b, bins=bins)

        return [round(b, 4) for b in bins], hist_a.tolist(), hist_b.tolist(), bin_width

    @classmethod
    def compare_distributions(
        cls,
        mode: str = "YEAR_VS_YEAR",
        metric: str = "RETURNS_PCT",
        param_a: str = "2022",
        param_b: str = "2024",
        interval: str = "1h",
        bin_method: str = "fixed_30",
        binning_method: str = None,
        **kwargs,
    ) -> Dict[str, Any]:
        if binning_method:
            bin_method = binning_method
        bin_method = str(bin_method).lower()
        if bin_method == "freedman-diaconis":
            bin_method = "freedman_diaconis"
        if "param_a" in kwargs:
            param_a = kwargs["param_a"]
        if "param_b" in kwargs:
            param_b = kwargs["param_b"]
        """
        Executes empirical distribution comparison across epochs, events, or walk-forward sets.
        Validates date bounds and returns structured error if requested range is unverified.
        """
        # Range validation for YEAR_VS_YEAR mode
        if mode == "YEAR_VS_YEAR":
            try:
                y_a = int(param_a)
                y_b = int(param_b)
                if y_a < cls.VERIFIED_YEAR_RANGE[0] or y_a > cls.VERIFIED_YEAR_RANGE[1] or \
                   y_b < cls.VERIFIED_YEAR_RANGE[0] or y_b > cls.VERIFIED_YEAR_RANGE[1]:
                    return {
                        "status": "DATA_RANGE_UNAVAILABLE",
                        "error_code": 404,
                        "error_tr": (
                            f"Seçilen yıl ({param_a} veya {param_b}) doğrulanmış veri aralığında "
                            f"({cls.VERIFIED_YEAR_RANGE[0]}-{cls.VERIFIED_YEAR_RANGE[1]}) bulunmamaktadır."
                        ),
                        "error_en": (
                            f"Requested year ({param_a} or {param_b}) is outside verified historical "
                            f"range ({cls.VERIFIED_YEAR_RANGE[0]}-{cls.VERIFIED_YEAR_RANGE[1]})."
                        ),
                        "verified_range": list(cls.VERIFIED_YEAR_RANGE),
                    }
            except ValueError:
                return {
                    "status": "DATA_RANGE_UNAVAILABLE",
                    "error_code": 422,
                    "error_tr": f"Geçersiz yıl parametresi: {param_a}, {param_b}",
                }

        df = cls._load_candles_dataframe(interval="1h")
        if df.empty:
            return {
                "status": "DATA_RANGE_UNAVAILABLE",
                "error_code": 404,
                "error_tr": "Doğrulanmış piyasa verisi bulunamadı.",
            }

        series_a: List[float] = []
        series_b: List[float] = []
        label_a = str(param_a)
        label_b = str(param_b)

        if mode == "YEAR_VS_YEAR":
            y1 = int(param_a)
            y2 = int(param_b)
            df_a = df[df["dt"].dt.year == y1]
            df_b = df[df["dt"].dt.year == y2]

            col = "abs_ret" if metric == "abs_ret" else "ret_pct"
            series_a = df_a[col].dropna().tolist()
            series_b = df_b[col].dropna().tolist()
            label_a = f"{y1} Yılı"
            label_b = f"{y2} Yılı"

        elif mode == "TRAIN_VS_HOLDOUT":
            train_mask = df["dt"].dt.year.isin([2022, 2023])
            holdout_mask = df["dt"].dt.year == 2025
            col = "ret_pct"
            series_a = df[train_mask][col].dropna().tolist()
            series_b = df[holdout_mask][col].dropna().tolist()
            label_a = "Eğitim Kümesi (2022-2023)"
            label_b = "Test Kümesi (2025 OOS)"

        elif mode == "PRE_VS_POST_EVENT":
            from coin_behavior_engine.product.macro_comparison import MacroEventComparisonEngine
            events = MacroEventComparisonEngine.load_events()
            cohort = param_a or "US_CPI"
            win_h = int(param_b) if param_b.isdigit() else 12

            cohort_str = str(cohort)
            target_events = [
                e for e in events
                if (cohort_str in e.event_id or cohort_str in e.event_name or cohort_str in e.event_category or
                    (cohort_str.upper() in ["US_CPI", "CPI"] and ("CPI" in e.event_id or "CPI" in e.event_name)))
                and e.verification_status != "EVENT_QUARANTINED"
            ]

            for ev in target_events:
                t0 = pd.to_datetime(ev.release_at_utc, utc=True)
                t0_idx = (df["dt"] - t0).abs().idxmin()
                pre_bars = df.iloc[max(0, t0_idx - win_h): t0_idx]
                post_bars = df.iloc[t0_idx: min(len(df), t0_idx + win_h)]
                series_a.extend(pre_bars["ret_pct"].dropna().tolist())
                series_b.extend(post_bars["ret_pct"].dropna().tolist())

            label_a = f"{cohort} Öncesi (-{win_h}h)"
            label_b = f"{cohort} Sonrası (+{win_h}h)"

        else:
            return {"status": "ERROR", "error_tr": f"Bilinmeyen mod: {mode}"}

        if not series_a or not series_b:
            return {
                "status": "DATA_RANGE_UNAVAILABLE",
                "error_code": 404,
                "error_tr": "Seçilen dönem için yeterli veri gözlemi bulunamadı.",
            }

        # Calculate metrics
        met_a = cls._compute_distribution_metrics(series_a)
        met_b = cls._compute_distribution_metrics(series_b)

        # Dynamic histogram binning
        bins, hist_counts_a, hist_counts_b, bin_w = cls._compute_bins(series_a, series_b, bin_method=bin_method)

        # ECDF
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

        # Q-Q Plots and KDE Overlays
        qq_a = cls._compute_qq_plot(series_a)
        qq_b = cls._compute_qq_plot(series_b)
        kde_a = cls._compute_kde(series_a)
        kde_b = cls._compute_kde(series_b)

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
                f"(KS d={ks_stat}, p < 0.01, Wasserstein={wass_dist}). Bu durum oynaklık ve kuyruk kalınlığı "
                "değişkenliğini ifade eder; yönsel alım-satım avantajı oluşturmaz."
            )
        else:
            div_note = (
                f"{label_a} ile {label_b} dağılımları benzer davranış sergilemektedir (KS p >= 0.01). "
                "Dağılımsal yapının dengeli olduğu gözlenmektedir."
            )

        res = DistributionComparisonResult(
            comparison_id=f"DIST-CMP-{hashlib.sha256(f'{mode}_{param_a}_{param_b}_{metric}_{bin_method}'.encode()).hexdigest()[:12]}",
            mode=mode,
            target_metric=metric,
            group_a_label=label_a,
            group_b_label=label_b,
            metrics_a=met_a,
            metrics_b=met_b,
            histogram_bins=bins,
            histogram_counts_a=hist_counts_a,
            histogram_counts_b=hist_counts_b,
            bin_method_used=bin_method,
            bin_width=bin_w,
            ecdf_a=ecdf_a,
            ecdf_b=ecdf_b,
            qq_plot_a=qq_a,
            qq_plot_b=qq_b,
            kde_a=kde_a,
            kde_b=kde_b,
            ks_statistic=ks_stat,
            ks_p_value=ks_p,
            wasserstein_distance=wass_dist,
            cohens_d=effect.get("cohens_d", 0.0),
            cliffs_delta=cliffs.get("cliffs_delta", 0.0),
            divergence_summary_tr=div_note,
            created_at_utc=datetime.now(timezone.utc).isoformat(),
        )

        return {"status": "success", "result": asdict(res)}

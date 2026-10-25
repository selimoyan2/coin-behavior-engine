"""
Historical Robustness and Sensitivity Explorer for Coin Behavior Engine.

Evaluates whether historical macro event research findings (e.g. volatility expansion)
are robust to specification variations:
- Window lengths: 6h, 12h, 24h, 48h
- Timeframe intervals: 1h, 4h
- Estimators: Close-to-Close realized volatility vs Parkinson High-Low volatility
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.product.independent_reproduction import (
    IndependentScientificReproductionEngine,
)
from coin_behavior_engine.product.macro_comparison import MacroEventComparisonEngine


@dataclass
class RobustnessCell:
    """A single evaluation cell in the multi-dimensional sensitivity matrix."""
    cell_id: str
    cohort: str
    interval: str
    window_hours: int
    estimator: str
    event_count: int
    mean_pre_vol: float
    mean_post_vol: float
    mean_ratio: float
    median_ratio: float
    ci_lower_95: float
    ci_upper_95: float
    cohens_d: float
    cohens_d_magnitude: str
    cliffs_delta: float
    cliffs_delta_magnitude: str
    stability_score: float
    is_expansion_statistically_significant: bool


@dataclass
class RobustnessMatrixResult:
    """Full sensitivity evaluation matrix and specification curve."""
    matrix_id: str
    cohort: str
    analyzed_at_utc: str
    cells: List[RobustnessCell]
    min_ratio: float
    max_ratio: float
    ratio_spread: float
    robustness_status: str  # ROBUST, MODERATELY_SENSITIVE, HIGHLY_SENSITIVE
    conclusion_tr: str
    legal_disclaimer_tr: str


class HistoricalRobustnessExplorer:
    """
    Computes multi-dimensional parameter sensitivity matrices
    across window lengths, sampling intervals, and volatility estimators.
    """

    SUPPORTED_WINDOWS = [6, 12, 24, 48]
    SUPPORTED_INTERVALS = ["1h", "4h"]
    SUPPORTED_ESTIMATORS = ["CLOSE_TO_CLOSE", "PARKINSON_HIGH_LOW"]

    DISCLAIMER_TR = (
        "Bu duyarlılık ve dayanıklılık analizi yalnızca tarihsel araştırma amaçlıdır. "
        "Yatırım tavsiyesi, alım-satım stratejisi veya canlı piyasa sinyali teşkil etmez."
    )

    @classmethod
    def _load_candles_for_interval(cls, interval: str = "1h") -> pd.DataFrame:
        """Loads and formats candle dataset for given interval."""
        interval_dir = Path(f"data/binance_spot_multiyear/{interval}")
        if not interval_dir.exists():
            interval_dir = Path("data/binance_spot_multiyear/1h")
        files = sorted(interval_dir.glob(f"BTCUSDT-{interval}-*.parquet"))
        if not files:
            return pd.DataFrame()
        dfs = [pd.read_parquet(f) for f in files]
        df = pd.concat(dfs, ignore_index=True)
        df["dt"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
        df = df.sort_values("dt").drop_duplicates("dt").reset_index(drop=True)
        return df

    @staticmethod
    def _parkinson_volatility(highs: np.ndarray, lows: np.ndarray) -> float:
        """
        Computes Parkinson high-low volatility estimator.
        sigma_P = sqrt( 1 / (4 * ln(2) * N) * sum( ln(H_i / L_i)^2 ) )
        """
        n = len(highs)
        if n == 0:
            return 0.0
        h = np.maximum(highs, 1e-9)
        l = np.maximum(lows, 1e-9)
        log_hl = np.log(h / l)
        sum_sq = np.sum(log_hl ** 2)
        factor = 1.0 / (4.0 * np.log(2.0) * n)
        return float(np.sqrt(factor * sum_sq))

    @classmethod
    def compute_robustness_matrix(
        cls,
        cohort: str = "US_CPI",
        window_options: Optional[List[int]] = None,
        interval_options: Optional[List[str]] = None,
        estimator_options: Optional[List[str]] = None,
    ) -> RobustnessMatrixResult:
        """
        Evaluates the sensitivity matrix across all parameter combinations.
        """
        windows = window_options or cls.SUPPORTED_WINDOWS
        intervals = interval_options or cls.SUPPORTED_INTERVALS
        estimators = estimator_options or cls.SUPPORTED_ESTIMATORS

        # 1. Load canonical events
        all_events = MacroEventComparisonEngine.load_events()
        if cohort in ["US_CPI", "CPI"]:
            target_events = [
                e for e in all_events
                if ("CPI" in e.event_id or "CPI" in e.event_name or "Consumer Price Index" in e.event_name)
                and e.verification_status != "EVENT_QUARANTINED"
            ]
        elif cohort in ["US_INFLATION", "INFLATION"]:
            target_events = [
                e for e in all_events
                if ("CPI" in e.event_id or "PCE" in e.event_id or e.event_category == "US_INFLATION")
                and e.verification_status != "EVENT_QUARANTINED"
            ]
        else:
            target_events = [
                e for e in all_events
                if (cohort in e.event_id or cohort in e.event_name or cohort in e.event_category)
                and e.verification_status != "EVENT_QUARANTINED"
            ]

        cells: List[RobustnessCell] = []
        ratios_all: List[float] = []

        # 2. Iterate intervals and compute metrics
        for interval in intervals:
            df_candles = cls._load_candles_for_interval(interval)
            if df_candles.empty:
                continue

            bar_hours = 1 if interval == "1h" else 4

            for win_h in windows:
                bars_count = max(1, win_h // bar_hours)

                for estimator in estimators:
                    pre_vols: List[float] = []
                    post_vols: List[float] = []
                    event_ratios: List[float] = []

                    for ev in target_events:
                        t0 = pd.to_datetime(ev.release_at_utc, utc=True)
                        t0_idx = int((df_candles["dt"] - t0).abs().idxmin())

                        pre_slice = df_candles.iloc[max(0, t0_idx - bars_count) : t0_idx]
                        post_slice = df_candles.iloc[t0_idx : min(len(df_candles), t0_idx + bars_count)]

                        if len(pre_slice) < 2 or len(post_slice) < 2:
                            continue

                        if estimator == "CLOSE_TO_CLOSE":
                            pre_v = IndependentScientificReproductionEngine.reference_realized_volatility(pre_slice["close"].tolist())
                            post_v = IndependentScientificReproductionEngine.reference_realized_volatility(post_slice["close"].tolist())
                        else:  # PARKINSON_HIGH_LOW
                            pre_v = cls._parkinson_volatility(pre_slice["high"].values, pre_slice["low"].values)
                            post_v = cls._parkinson_volatility(post_slice["high"].values, post_slice["low"].values)

                        if pre_v > 1e-9:
                            r = post_v / pre_v
                            pre_vols.append(pre_v)
                            post_vols.append(post_v)
                            event_ratios.append(r)

                    if not event_ratios:
                        continue

                    m_pre = float(np.mean(pre_vols))
                    m_post = float(np.mean(post_vols))
                    m_ratio = float(np.mean(event_ratios))
                    med_ratio = float(np.median(event_ratios))
                    ratios_all.append(m_ratio)

                    # Bootstrap CI for mean ratio
                    ci_res = IndependentScientificReproductionEngine.reference_bootstrap_ci(event_ratios, num_resamples=500, random_seed=42)
                    ci_low = float(ci_res["ci_lower"])
                    ci_high = float(ci_res["ci_upper"])

                    # Effect sizes
                    c_d = float(IndependentScientificReproductionEngine.reference_cohens_d(pre_vols, post_vols))
                    c_delta = float(IndependentScientificReproductionEngine.reference_cliffs_delta(pre_vols, post_vols))

                    abs_d = abs(c_d)
                    if abs_d < 0.2:
                        d_mag = "NEGLIGIBLE"
                    elif abs_d < 0.5:
                        d_mag = "SMALL"
                    elif abs_d < 0.8:
                        d_mag = "MEDIUM"
                    elif abs_d < 1.2:
                        d_mag = "LARGE"
                    else:
                        d_mag = "VERY_LARGE"

                    abs_delta = abs(c_delta)
                    if abs_delta < 0.147:
                        delta_mag = "NEGLIGIBLE"
                    elif abs_delta < 0.330:
                        delta_mag = "SMALL"
                    elif abs_delta < 0.474:
                        delta_mag = "MEDIUM"
                    else:
                        delta_mag = "LARGE"

                    # Stability score based on distance from baseline ratio and CI width
                    is_sig = ci_low > 1.0
                    ci_width = max(0.01, ci_high - ci_low)
                    stab_score = round(max(0.0, min(1.0, 1.0 - (ci_width / 4.0))), 3)

                    cell_hash = hashlib.sha256(f"{cohort}_{interval}_{win_h}_{estimator}".encode()).hexdigest()[:8]
                    cells.append(
                        RobustnessCell(
                            cell_id=f"CELL-{cell_hash}",
                            cohort=cohort,
                            interval=interval,
                            window_hours=win_h,
                            estimator=estimator,
                            event_count=len(event_ratios),
                            mean_pre_vol=round(m_pre * 100.0, 4),
                            mean_post_vol=round(m_post * 100.0, 4),
                            mean_ratio=round(m_ratio, 3),
                            median_ratio=round(med_ratio, 3),
                            ci_lower_95=round(ci_low, 3),
                            ci_upper_95=round(ci_high, 3),
                            cohens_d=round(c_d, 3),
                            cohens_d_magnitude=d_mag,
                            cliffs_delta=round(c_delta, 3),
                            cliffs_delta_magnitude=delta_mag,
                            stability_score=stab_score,
                            is_expansion_statistically_significant=is_sig,
                        )
                    )

        min_r = round(min(ratios_all), 3) if ratios_all else 0.0
        max_r = round(max(ratios_all), 3) if ratios_all else 0.0
        spread = round(max_r - min_r, 3)

        # Classification of robustness
        # If all specifications preserve ratio > 1.2x and statistically significant expansion
        sig_count = sum(1 for c in cells if c.is_expansion_statistically_significant)
        sig_pct = (sig_count / len(cells)) if cells else 0.0

        if sig_pct >= 0.85 and min_r >= 1.20:
            rob_status = "ROBUST"
            conc_tr = (
                f"{cohort} kohortu için test edilen {len(cells)} farklı parametre kombinasyonunun "
                f"%{int(sig_pct * 100)}'inde istatistiki olarak belirgin oynaklık genişlemesi gözlenmiştir. "
                f"En düşük oran {min_r}x, en yüksek oran {max_r}x (fark: {spread}x) seviyesindedir. "
                "Bulgular pencere uzunluğu ve volatilite hesaplayıcı seçimlerine karşı yüksek oranda dayanıklıdır."
            )
        elif sig_pct >= 0.60:
            rob_status = "MODERATELY_SENSITIVE"
            conc_tr = (
                f"{cohort} analizi pencere uzunluğuna karşı orta düzeyde duyarlılık göstermektedir. "
                f"Spesifikasyonların %{int(sig_pct * 100)}'inde genişleme anlamlıdır (Min: {min_r}x, Maks: {max_r}x)."
            )
        else:
            rob_status = "HIGHLY_SENSITIVE"
            conc_tr = (
                f"{cohort} kohortu için oynaklık genişlemesi seçilen pencere veya hesaplayıcı parametrelerine "
                f"yüksek derecede bağımlıdır ve genel bir piyasa kuralı olarak yorumlanamaz."
            )

        matrix_id = f"ROB-MAT-{hashlib.sha256(f'{cohort}_{len(cells)}_{spread}'.encode()).hexdigest()[:12]}"

        return RobustnessMatrixResult(
            matrix_id=matrix_id,
            cohort=cohort,
            analyzed_at_utc=datetime.now(timezone.utc).isoformat(),
            cells=cells,
            min_ratio=min_r,
            max_ratio=max_r,
            ratio_spread=spread,
            robustness_status=rob_status,
            conclusion_tr=conc_tr,
            legal_disclaimer_tr=cls.DISCLAIMER_TR,
        )

    @classmethod
    def export_matrix_dict(cls, result: RobustnessMatrixResult) -> Dict[str, Any]:
        """Convert matrix result to clean JSON-serializable dictionary."""
        d = asdict(result)
        return d

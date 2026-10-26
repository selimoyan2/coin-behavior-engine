"""
Historical Regime Comparison Studio for Coin Behavior Engine (CBE).
Enables researchers to compare historical BTCUSDT market behavior,
return distributions, realized volatility, regime occupancy, and transition dynamics
across years, custom periods, canonical regimes, and train vs holdout partitions.
All research is offline, historical, descriptive, and non-predictive.
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
from coin_behavior_engine.product.historical_regime_transition_lab import HistoricalRegimeTransitionLabEngine


@dataclass
class PeriodProfile:
    """Statistical summary of a single historical period."""
    label: str
    start_utc: str
    end_utc: str
    candle_count: int
    mean_return_pct: float
    volatility_annualized_pct: float
    skewness: float
    kurtosis: float
    regime_occupancy_pct: Dict[str, float]
    mean_regime_duration_hours: Dict[str, float]
    data_gap_count: int
    data_coverage_pct: float


@dataclass
class ComparisonMetricDelta:
    """Difference metrics between Period A and Period B."""
    frobenius_distance: float
    jensen_shannon_divergence: float
    occupancy_psi: float
    volatility_difference_pct: float
    transition_difference_matrix: Dict[str, Dict[str, float]]
    regime_occupancy_shifts: Dict[str, float]


@dataclass
class RegimeComparisonResult:
    """Complete result object for Historical Regime Comparison Studio."""
    comparison_id: str
    mode: str
    asset: str
    interval: str
    timestamp_utc: str
    period_a: PeriodProfile
    period_b: PeriodProfile
    deltas: ComparisonMetricDelta
    methodological_notes_tr: List[str]
    disclaimer_tr: str


class HistoricalRegimeComparisonStudio:
    """
    Tarihsel Rejim Karşılaştırma Stüdyosu Engine.
    """
    ASSET = "BTCUSDT"
    SUPPORTED_MODES = [
        "YEAR_VS_YEAR",
        "PERIOD_VS_PERIOD",
        "REGIME_VS_REGIME",
        "EVENT_WINDOW_VS_BASELINE",
        "TRAIN_VS_HOLDOUT",
    ]
    SUPPORTED_INTERVALS = ["1h", "4h", "5m"]

    DISCLAIMER_TR = (
        "Bu rapor ve karşılaştırma aracı yalnızca tarihsel piyasa davranışı araştırması amacıyla "
        "hazırlanmıştır. Geleceğe yönelik fiyat tahmini, getiri vaadi, yatırım tavsiyesi veya "
        "canlı alım-satım sinyali değildir."
    )

    _CANDLE_CACHE: Dict[str, pd.DataFrame] = {}

    @classmethod
    def _load_candles(cls, interval: str = "1h") -> pd.DataFrame:
        if interval in cls._CANDLE_CACHE:
            return cls._CANDLE_CACHE[interval]

        base_dir = Path(__file__).resolve().parents[3] / "data" / "binance_spot_multiyear" / interval
        if not base_dir.exists():
            return pd.DataFrame()

        dfs = []
        for pfile in sorted(base_dir.glob("*.parquet")):
            if "2026-10" in pfile.name:
                continue
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
    def get_synchronized_chart_data(
        cls,
        start_utc: str,
        end_utc: str,
        interval: str = "1h",
        max_candles: int = 1000,
    ) -> Dict[str, Any]:
        """
        Generates synchronized chart series:
        - Candlestick OHLC series
        - Canonical regime background bands (colored segments)
        - Macro event markers
        - Data gaps
        """
        df = cls._load_candles(interval)
        if df.empty:
            return {"error": "Candle data unavailable"}

        dt_start = pd.to_datetime(start_utc)
        dt_end = pd.to_datetime(end_utc)

        mask = (df["dt"] >= dt_start) & (df["dt"] <= dt_end)
        sub_df = df.loc[mask].copy()

        if sub_df.empty:
            return {"error": "No data in range"}

        # Check for downsampling requirement
        total_in_range = len(sub_df)
        is_downsampled = total_in_range > max_candles
        step = max(1, total_in_range // max_candles) if is_downsampled else 1
        plot_df = sub_df.iloc[::step].copy() if is_downsampled else sub_df

        candles = []
        for _, row in plot_df.iterrows():
            candles.append({
                "time": int(row["dt"].timestamp()),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0.0)),
            })

        # Generate timeline regime bands from HistoricalRegimeTransitionLabEngine
        timeline_data = HistoricalRegimeTransitionLabEngine.get_regime_timeline_data(
            interval=interval,
            max_segments=250,
        )
        bands = []
        for seg in timeline_data.get("segments", []):
            s_str = seg.get("start_utc") or seg.get("start_time_utc")
            e_str = seg.get("end_utc") or seg.get("end_time_utc")
            if not s_str or not e_str:
                continue
            s_dt = pd.to_datetime(s_str)
            e_dt = pd.to_datetime(e_str)
            dur_h = seg.get("duration_hours", seg.get("bars", 0) * (5.0 / 60.0))
            if e_dt >= dt_start and s_dt <= dt_end:
                bands.append({
                    "regime": seg["regime"],
                    "start_time": int(max(s_dt, dt_start).timestamp()),
                    "end_time": int(min(e_dt, dt_end).timestamp()),
                    "start_utc": str(s_str),
                    "end_utc": str(e_str),
                    "duration_hours": round(dur_h, 2),
                })

        # Macro event markers in range
        from coin_behavior_engine.product.macro_comparison import MacroEventComparisonEngine
        all_events = MacroEventComparisonEngine.load_events()
        event_markers = []
        for ev in all_events:
            if ev.verification_status == "EVENT_QUARANTINED":
                continue
            ev_dt = pd.to_datetime(ev.release_at_utc)
            if dt_start <= ev_dt <= dt_end:
                event_markers.append({
                    "event_id": ev.event_id,
                    "event_name": ev.event_name,
                    "category": ev.event_category,
                    "time": int(ev_dt.timestamp()),
                    "release_at_utc": ev.release_at_utc,
                    "importance": ev.importance,
                    "actual": ev.actual_value,
                    "consensus": ev.consensus_value,
                })

        return {
            "asset": cls.ASSET,
            "interval": interval,
            "start_utc": start_utc,
            "end_utc": end_utc,
            "total_candles": total_in_range,
            "displayed_candles": len(candles),
            "is_downsampled": is_downsampled,
            "candles": candles,
            "regime_bands": bands,
            "macro_events": event_markers,
            "disclaimer_tr": cls.DISCLAIMER_TR,
        }

    @classmethod
    def _compute_period_profile(
        cls,
        df: pd.DataFrame,
        label: str,
        start_dt: pd.Timestamp,
        end_dt: pd.Timestamp,
        interval: str,
    ) -> PeriodProfile:
        mask = (df["dt"] >= start_dt) & (df["dt"] <= end_dt)
        sub = df.loc[mask].copy()

        if sub.empty or len(sub) < 5:
            return PeriodProfile(
                label=label,
                start_utc=start_dt.isoformat(),
                end_utc=end_dt.isoformat(),
                candle_count=0,
                mean_return_pct=0.0,
                volatility_annualized_pct=0.0,
                skewness=0.0,
                kurtosis=0.0,
                regime_occupancy_pct={},
                mean_regime_duration_hours={},
                data_gap_count=0,
                data_coverage_pct=0.0,
            )

        bar_hours = 1 if interval == "1h" else (4 if interval == "4h" else 5/60)
        sub["return"] = np.log(sub["close"] / sub["close"].shift(1))
        rets = sub["return"].dropna()

        mean_ret = float(rets.mean() * 100.0) if len(rets) > 0 else 0.0
        vol = float(rets.std() * np.sqrt(365.25 * 24.0 / bar_hours) * 100.0) if len(rets) > 1 else 0.0
        from scipy import stats
        skew = float(stats.skew(rets)) if len(rets) > 2 else 0.0
        kurt = float(stats.kurtosis(rets)) if len(rets) > 3 else 0.0

        # Regime occupancy from lab matrix
        mat = HistoricalRegimeTransitionLabEngine.compute_transition_matrix(
            interval=interval,
            period="ALL",
            start_utc=start_dt.isoformat(),
            end_utc=end_dt.isoformat(),
        )
        total_obs = max(1, mat.total_transitions_observed)
        occupancy = {}
        for r_idx, reg in enumerate(mat.regimes):
            row_sum = sum(mat.counts_matrix[r_idx])
            occupancy[reg] = round((row_sum / total_obs) * 100.0, 2)

        durations_dict = HistoricalRegimeTransitionLabEngine.compute_regime_durations(
            interval=interval,
            start_utc=start_dt.isoformat(),
            end_utc=end_dt.isoformat(),
        )
        mean_durations = {
            k: round(v.mean_duration_hours, 1) for k, v in durations_dict.items()
        }

        # Expected candles
        total_hours = (end_dt - start_dt).total_seconds() / 3600.0
        expected_bars = max(1, int(total_hours / bar_hours))
        coverage = min(100.0, round((len(sub) / expected_bars) * 100.0, 2))

        return PeriodProfile(
            label=label,
            start_utc=start_dt.isoformat(),
            end_utc=end_dt.isoformat(),
            candle_count=len(sub),
            mean_return_pct=round(mean_ret, 4),
            volatility_annualized_pct=round(vol, 2),
            skewness=round(skew, 3),
            kurtosis=round(kurt, 3),
            regime_occupancy_pct=occupancy,
            mean_regime_duration_hours=mean_durations,
            data_gap_count=mat.data_gap_count,
            data_coverage_pct=coverage,
        )

    @classmethod
    def compare_periods(
        cls,
        mode: str = "YEAR_VS_YEAR",
        param_a: str = "2023",
        param_b: str = "2025",
        interval: str = "1h",
    ) -> RegimeComparisonResult:
        """
        Executes comparative analysis between two historical periods.
        """
        if mode not in cls.SUPPORTED_MODES:
            raise ValueError(f"Unsupported comparison mode: {mode}")

        df = cls._load_candles(interval)

        # Parse date bounds based on mode
        if mode == "YEAR_VS_YEAR":
            start_a = pd.to_datetime(f"{param_a}-01-01T00:00:00Z")
            end_a = pd.to_datetime(f"{param_a}-12-31T23:59:59Z")
            start_b = pd.to_datetime(f"{param_b}-01-01T00:00:00Z")
            end_b = pd.to_datetime(f"{param_b}-12-31T23:59:59Z")
            label_a = f"Yıl {param_a}"
            label_b = f"Yıl {param_b}"
        elif mode == "TRAIN_VS_HOLDOUT":
            start_a = pd.to_datetime("2022-01-01T00:00:00Z")
            end_a = pd.to_datetime("2023-12-31T23:59:59Z")
            start_b = pd.to_datetime("2025-01-01T00:00:00Z")
            end_b = pd.to_datetime("2026-09-24T23:59:59Z")
            label_a = "Geliştirme / Eğitim (Train 2022-2023)"
            label_b = "Nihai Teyit (Holdout 2025-2026)"
        else:
            # PERIOD_VS_PERIOD or generic
            start_a = pd.to_datetime(param_a.split("/")[0] if "/" in param_a else "2022-01-01")
            end_a = pd.to_datetime(param_a.split("/")[1] if "/" in param_a else "2023-12-31")
            start_b = pd.to_datetime(param_b.split("/")[0] if "/" in param_b else "2025-01-01")
            end_b = pd.to_datetime(param_b.split("/")[1] if "/" in param_b else "2026-09-24")
            label_a = f"Dönem A ({param_a})"
            label_b = f"Dönem B ({param_b})"

        prof_a = cls._compute_period_profile(df, label_a, start_a, end_a, interval)
        prof_b = cls._compute_period_profile(df, label_b, start_b, end_b, interval)

        # Transition matrix comparison via lab drift engine
        drift = HistoricalRegimeTransitionLabEngine.compute_regime_drift(
            mode="PERIOD_VS_PERIOD",
            param_a=f"{start_a.strftime('%Y%m%d')}_{end_a.strftime('%Y%m%d')}",
            param_b=f"{start_b.strftime('%Y%m%d')}_{end_b.strftime('%Y%m%d')}",
            interval=interval,
        )

        # Occupancy shifts
        occ_shifts = {}
        for reg in HistoricalRegimeTransitionLabEngine.CANONICAL_REGIMES:
            pct_a = prof_a.regime_occupancy_pct.get(reg, 0.0)
            pct_b = prof_b.regime_occupancy_pct.get(reg, 0.0)
            occ_shifts[reg] = round(pct_b - pct_a, 2)

        vol_diff = round(prof_b.volatility_annualized_pct - prof_a.volatility_annualized_pct, 2)

        deltas = ComparisonMetricDelta(
            frobenius_distance=drift.frobenius_distance,
            jensen_shannon_divergence=drift.jensen_shannon_divergence,
            occupancy_psi=drift.occupancy_shift_psi,
            volatility_difference_pct=vol_diff,
            transition_difference_matrix=drift.difference_matrix,
            regime_occupancy_shifts=occ_shifts,
        )

        notes = [
            f"Karşılaştırılan dönemler ({label_a} vs {label_b}) arasındaki rejim geçiş matrisi Frobenius uzaklığı {drift.frobenius_distance:.3f} olarak hesaplanmıştır.",
            f"Durum doluluk dağılımı Kararlılık İndeksi (PSI) = {drift.occupancy_shift_psi:.4f} (Eşik 0.10 altında: kararlı rejim yapısı).",
            f"Yıllıklandırılmış volatilite farkı: %{vol_diff:+.2f} puan.",
        ]

        now_str = datetime.now(timezone.utc).isoformat()
        comp_id = f"CMP-{mode}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"

        return RegimeComparisonResult(
            comparison_id=comp_id,
            mode=mode,
            asset=cls.ASSET,
            interval=interval,
            timestamp_utc=now_str,
            period_a=prof_a,
            period_b=prof_b,
            deltas=deltas,
            methodological_notes_tr=notes,
            disclaimer_tr=cls.DISCLAIMER_TR,
        )

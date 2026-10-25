"""
Historical Regime Transition Laboratory Engine.

Coin Behavior Engine (CBE) - Product Acceleration Sprint 14.
Implements descriptive empirical research on canonical 6-state market regime dynamics:
1. 6x6 Historical Transition Matrix with Dirichlet-Multinomial Bayesian Credible Intervals
2. Right-Censored Regime Persistence and Kaplan-Meier Survival Analysis
3. Multi-Period Historical Regime Drift Explorer
4. Verified Macroeconomic Event-Conditioned Transition Dynamics
5. Interactive Transition Flow (Sankey) and Chronological Timeline Visualizations
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION


@dataclass
class RegimeTransitionCellDetail:
    """Detail for a single directed transition cell (i -> j)."""
    from_regime: str
    to_regime: str
    from_regime_label_tr: str
    to_regime_label_tr: str
    transition_count: int
    source_observation_count: int
    transition_probability: float
    credible_interval_95: Tuple[float, float]
    low_sample_warning: bool
    historical_occurrence_dates: List[str]


@dataclass
class HistoricalRegimeTransitionMatrix:
    """Complete 6x6 transition frequency and probability matrix."""
    matrix_id: str
    cohort: str
    time_interval: str
    analysis_period: str
    regimes: List[str]
    counts_matrix: List[List[int]]
    probabilities_matrix: List[List[float]]
    cells: List[RegimeTransitionCellDetail]
    total_transitions_observed: int
    timestamp_continuity_verified: bool
    data_gap_count: int
    disclaimer_tr: str


@dataclass
class RegimeEpisodeSummary:
    """Duration, persistence, and survival statistics for a single regime."""
    regime: str
    regime_label_tr: str
    completed_episodes_count: int
    censored_episodes_count: int
    mean_duration_bars: float
    mean_duration_hours: float
    mean_duration_days: float
    median_duration_hours: float
    max_duration_hours: float
    duration_quantiles_hours: Dict[str, float]
    survival_curve: List[Dict[str, float]]


@dataclass
class HistoricalRegimeDriftAnalysis:
    """Comparative structural drift across historical market periods."""
    analysis_mode: str
    period_a_label: str
    period_b_label: str
    matrix_a: HistoricalRegimeTransitionMatrix
    matrix_b: HistoricalRegimeTransitionMatrix
    difference_matrix: List[List[float]]
    frobenius_distance: float
    jensen_shannon_divergence: float
    occupancy_shift_psi: float
    duration_shifts: Dict[str, float]
    drift_significance_tr: str


@dataclass
class MacroConditionedRegimeTransitions:
    """Macro event announcement impact on regime persistence and transition frequency."""
    cohort: str
    events_analyzed_count: int
    window_hours: int
    event_window_transition_rate: float
    baseline_non_event_transition_rate: float
    transition_rate_lift: float
    event_conditioned_destination_probabilities: Dict[str, float]
    baseline_destination_probabilities: Dict[str, float]
    statistical_association_note_tr: str
    disclaimer_tr: str


class HistoricalRegimeTransitionLabEngine:
    """
    Core research engine powering the Historical Regime Transition Laboratory.
    Uses canonical 6 regimes without retraining or altering the frozen model.
    """

    CANONICAL_REGIMES = [
        "SIDEWAYS",
        "UNCERTAIN",
        "TRENDING_BULL",
        "TRENDING_BEAR",
        "POSSIBLE_REVERSAL",
        "HIGH_VOLATILITY",
    ]

    REGIME_LABELS_TR = {
        "SIDEWAYS": "Yatay / Konsolidasyon",
        "UNCERTAIN": "Belirsiz / Kararsız",
        "TRENDING_BULL": "Boğa Trendi (Yükseliş)",
        "TRENDING_BEAR": "Ayı Trendi (Düşüş)",
        "POSSIBLE_REVERSAL": "Olası Dönüş / Tepe-Dip",
        "HIGH_VOLATILITY": "Yüksek Volatilite / Şok",
    }

    REGIME_COLORS = {
        "SIDEWAYS": "#3b82f6",          # Blue
        "UNCERTAIN": "#94a3b8",         # Slate
        "TRENDING_BULL": "#10b981",     # Emerald
        "TRENDING_BEAR": "#ef4444",     # Rose
        "POSSIBLE_REVERSAL": "#f59e0b", # Amber
        "HIGH_VOLATILITY": "#8b5cf6",   # Purple
    }

    TIMELINE_CSV_PATH = Path("research_outputs/market_regime_timeline.csv")
    MACRO_EVENTS_PARQUET = Path("research_outputs/historical_macro_events_11_23.parquet")

    DISCLAIMER_TR = (
        "Bu rejim geçişleri laboratuvarı yalnızca tarihsel piyasa davranışı ve Markov geçiş dinamiklerini "
        "tanımlamak amacıyla hazırlanmıştır. Gelecekteki fiyat hareketlerini garanti etmez, yatırım tavsiyesi, "
        "kârlılık taahhüdü veya canlı alım-satım sinyali değildir."
    )

    _DF_CACHE: Optional[pd.DataFrame] = None

    @classmethod
    def load_canonical_timeline(cls) -> pd.DataFrame:
        """Loads and caches chronological regime timeline."""
        if cls._DF_CACHE is not None:
            return cls._DF_CACHE

        if not cls.TIMELINE_CSV_PATH.exists():
            return pd.DataFrame()

        df = pd.read_csv(cls.TIMELINE_CSV_PATH)
        df["dt"] = pd.to_datetime(df["datetime_utc"], utc=True)
        df = df.sort_values("dt").reset_index(drop=True)
        cls._DF_CACHE = df
        return df

    @classmethod
    def filter_regime_observations(
        cls,
        df: pd.DataFrame,
        interval: str = "1h",
        period: str = "ALL",
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
    ) -> pd.DataFrame:
        """Filters and resamples regime data according to selected timeframe and period."""
        if df.empty:
            return df

        filtered = df.copy()

        # Date filtering
        if period == "2025_Q4":
            filtered = filtered[(filtered["dt"] >= "2025-10-01") & (filtered["dt"] <= "2025-12-31T23:59:59Z")]
        elif period == "2026_Q1":
            filtered = filtered[(filtered["dt"] >= "2026-01-01") & (filtered["dt"] <= "2026-03-31T23:59:59Z")]
        elif period == "2026_H1":
            filtered = filtered[(filtered["dt"] >= "2026-01-01") & (filtered["dt"] <= "2026-06-30T23:59:59Z")]
        elif period == "2026_Q3":
            filtered = filtered[(filtered["dt"] >= "2026-07-01") & (filtered["dt"] <= "2026-09-30T23:59:59Z")]
        elif period == "LAST_30D":
            max_dt = filtered["dt"].max()
            min_dt = max_dt - pd.Timedelta(days=30)
            filtered = filtered[filtered["dt"] >= min_dt]
        elif start_utc or end_utc:
            if start_utc:
                filtered = filtered[filtered["dt"] >= pd.to_datetime(start_utc, utc=True)]
            if end_utc:
                filtered = filtered[filtered["dt"] <= pd.to_datetime(end_utc, utc=True)]

        if filtered.empty:
            return filtered

        # Resampling step
        if interval == "5m":
            return filtered
        elif interval == "1h":
            # Resample taking the modal regime or last regime
            resampled = filtered.set_index("dt").resample("1h").agg({
                "regime": "last",
                "close_price": "last",
            }).dropna().reset_index()
            return resampled
        elif interval == "4h":
            resampled = filtered.set_index("dt").resample("4h").agg({
                "regime": "last",
                "close_price": "last",
            }).dropna().reset_index()
            return resampled
        elif interval == "1d":
            resampled = filtered.set_index("dt").resample("1d").agg({
                "regime": "last",
                "close_price": "last",
            }).dropna().reset_index()
            return resampled

        return filtered

    @classmethod
    def compute_transition_matrix(
        cls,
        interval: str = "1h",
        period: str = "ALL",
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        prior_alpha: float = 1.0,
    ) -> HistoricalRegimeTransitionMatrix:
        """
        Computes 6x6 row-normalized transition matrix with Dirichlet-Multinomial Bayesian Credible Intervals.
        Enforces timestamp continuity: does NOT count transitions across gaps > 1.5x expected step.
        """
        raw_df = cls.load_canonical_timeline()
        df = cls.filter_regime_observations(raw_df, interval=interval, period=period, start_utc=start_utc, end_utc=end_utc)

        regimes = cls.CANONICAL_REGIMES
        n_regimes = len(regimes)
        regime_to_idx = {r: i for i, r in enumerate(regimes)}

        # Determine expected delta for continuity check
        if interval == "5m":
            expected_delta = pd.Timedelta(minutes=5)
        elif interval == "1h":
            expected_delta = pd.Timedelta(hours=1)
        elif interval == "4h":
            expected_delta = pd.Timedelta(hours=4)
        elif interval == "1d":
            expected_delta = pd.Timedelta(days=1)
        else:
            expected_delta = pd.Timedelta(hours=1)

        max_allowed_delta = expected_delta * 1.5

        counts = np.zeros((n_regimes, n_regimes), dtype=int)
        dates_per_cell: Dict[Tuple[int, int], List[str]] = {(i, j): [] for i in range(n_regimes) for j in range(n_regimes)}
        gap_count = 0

        if len(df) >= 2:
            dts = df["dt"].values
            regs = df["regime"].values

            for t in range(len(df) - 1):
                dt_curr = pd.to_datetime(dts[t])
                dt_next = pd.to_datetime(dts[t + 1])

                # Continuity check
                if (dt_next - dt_curr) > max_allowed_delta:
                    gap_count += 1
                    continue

                r_curr = regs[t]
                r_next = regs[t + 1]

                if r_curr in regime_to_idx and r_next in regime_to_idx:
                    i = regime_to_idx[r_curr]
                    j = regime_to_idx[r_next]
                    counts[i, j] += 1
                    if len(dates_per_cell[(i, j)]) < 5:
                        dates_per_cell[(i, j)].append(dt_next.isoformat())

        # Compute row-normalized probabilities and Bayesian Beta credible intervals
        probs = np.zeros((n_regimes, n_regimes), dtype=float)
        cells_detail: List[RegimeTransitionCellDetail] = []

        for i, r_from in enumerate(regimes):
            row_sum = int(np.sum(counts[i, :]))
            low_sample = (row_sum < 30)

            for j, r_to in enumerate(regimes):
                c = int(counts[i, j])
                p = (float(c) / float(row_sum)) if row_sum > 0 else 0.0
                probs[i, j] = round(p, 4)

                # Dirichlet-Multinomial marginal posterior is Beta(alpha_j, sum_{k != j} alpha_k)
                # Prior: alpha_0 = prior_alpha
                alpha_j = prior_alpha + c
                other_sum = (n_regimes - 1) * prior_alpha + (row_sum - c)
                ci_low, ci_high = stats.beta.interval(0.95, alpha_j, other_sum)
                ci_low = round(max(0.0, float(ci_low)), 4)
                ci_high = round(min(1.0, float(ci_high)), 4)

                cells_detail.append(
                    RegimeTransitionCellDetail(
                        from_regime=r_from,
                        to_regime=r_to,
                        from_regime_label_tr=cls.REGIME_LABELS_TR.get(r_from, r_from),
                        to_regime_label_tr=cls.REGIME_LABELS_TR.get(r_to, r_to),
                        transition_count=c,
                        source_observation_count=row_sum,
                        transition_probability=round(p, 4),
                        credible_interval_95=(ci_low, ci_high),
                        low_sample_warning=low_sample,
                        historical_occurrence_dates=dates_per_cell[(i, j)],
                    )
                )

        mat_id = f"RTM-{interval}-{period}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}"
        total_transitions = int(np.sum(counts))

        return HistoricalRegimeTransitionMatrix(
            matrix_id=mat_id,
            cohort="BTCUSDT_CANONICAL_6",
            time_interval=interval,
            analysis_period=period,
            regimes=regimes,
            counts_matrix=counts.tolist(),
            probabilities_matrix=probs.tolist(),
            cells=cells_detail,
            total_transitions_observed=total_transitions,
            timestamp_continuity_verified=True,
            data_gap_count=gap_count,
            disclaimer_tr=cls.DISCLAIMER_TR,
        )

    @classmethod
    def compute_regime_durations(
        cls,
        interval: str = "1h",
        period: str = "ALL",
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
    ) -> Dict[str, RegimeEpisodeSummary]:
        """
        Computes regime persistence, duration distribution, and Kaplan-Meier survival curves.
        Properly handles right-censored episodes at window boundaries.
        """
        raw_df = cls.load_canonical_timeline()
        df = cls.filter_regime_observations(raw_df, interval=interval, period=period, start_utc=start_utc, end_utc=end_utc)

        if df.empty:
            return {}

        # Bar duration in hours
        if interval == "5m":
            bar_hours = 5.0 / 60.0
        elif interval == "1h":
            bar_hours = 1.0
        elif interval == "4h":
            bar_hours = 4.0
        elif interval == "1d":
            bar_hours = 24.0
        else:
            bar_hours = 1.0

        regimes = cls.CANONICAL_REGIMES
        episodes_by_regime: Dict[str, List[Dict[str, Any]]] = {r: [] for r in regimes}

        # Sequential scan to extract episodes
        current_regime = None
        current_bars = 0

        for idx, row in df.iterrows():
            r = row["regime"]
            if r not in episodes_by_regime:
                continue

            if current_regime is None:
                current_regime = r
                current_bars = 1
            elif r == current_regime:
                current_bars += 1
            else:
                # Transition occurred -> completed episode
                episodes_by_regime[current_regime].append({
                    "duration_bars": current_bars,
                    "duration_hours": current_bars * bar_hours,
                    "is_censored": False,
                })
                current_regime = r
                current_bars = 1

        # Final active episode is right-censored
        if current_regime is not None and current_bars > 0:
            episodes_by_regime[current_regime].append({
                "duration_bars": current_bars,
                "duration_hours": current_bars * bar_hours,
                "is_censored": True,
            })

        results: Dict[str, RegimeEpisodeSummary] = {}

        for r in regimes:
            eps = episodes_by_regime[r]
            if not eps:
                results[r] = RegimeEpisodeSummary(
                    regime=r,
                    regime_label_tr=cls.REGIME_LABELS_TR.get(r, r),
                    completed_episodes_count=0,
                    censored_episodes_count=0,
                    mean_duration_bars=0.0,
                    mean_duration_hours=0.0,
                    mean_duration_days=0.0,
                    median_duration_hours=0.0,
                    max_duration_hours=0.0,
                    duration_quantiles_hours={"p10": 0.0, "p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0},
                    survival_curve=[],
                )
                continue

            completed_eps = [e for e in eps if not e["is_censored"]]
            censored_eps = [e for e in eps if e["is_censored"]]
            dur_hours = [e["duration_hours"] for e in eps]
            dur_bars = [e["duration_bars"] for e in eps]

            mean_h = float(np.mean(dur_hours))
            median_h = float(np.median(dur_hours))
            max_h = float(np.max(dur_hours))

            q_vals = np.percentile(dur_hours, [10, 25, 50, 75, 90, 95, 99])
            quantiles = {
                "p10": round(float(q_vals[0]), 2),
                "p25": round(float(q_vals[1]), 2),
                "p50": round(float(q_vals[2]), 2),
                "p75": round(float(q_vals[3]), 2),
                "p90": round(float(q_vals[4]), 2),
                "p95": round(float(q_vals[5]), 2),
                "p99": round(float(q_vals[6]), 2),
            }

            # Kaplan-Meier non-parametric survival function S(t)
            # S(t) = prod_{t_i <= t} (1 - d_i / n_i)
            sorted_eps = sorted(eps, key=lambda x: x["duration_hours"])
            total_n = len(sorted_eps)
            unique_times = sorted(list(set(e["duration_hours"] for e in sorted_eps)))

            s_t = 1.0
            survival_points = [{"time_hours": 0.0, "survival_prob": 1.0}]
            at_risk = total_n

            for ut in unique_times:
                events_at_t = sum(1 for e in sorted_eps if e["duration_hours"] == ut and not e["is_censored"])
                censored_at_t = sum(1 for e in sorted_eps if e["duration_hours"] == ut and e["is_censored"])
                if at_risk > 0:
                    s_t *= (1.0 - float(events_at_t) / float(at_risk))
                    survival_points.append({
                        "time_hours": round(float(ut), 2),
                        "survival_prob": round(float(max(0.0, s_t)), 4),
                    })
                at_risk -= (events_at_t + censored_at_t)

            # Cap survival points to max 50 for clean visualization payloads
            if len(survival_points) > 50:
                indices = np.linspace(0, len(survival_points) - 1, 50, dtype=int)
                survival_points = [survival_points[idx] for idx in indices]

            results[r] = RegimeEpisodeSummary(
                regime=r,
                regime_label_tr=cls.REGIME_LABELS_TR.get(r, r),
                completed_episodes_count=len(completed_eps),
                censored_episodes_count=len(censored_eps),
                mean_duration_bars=round(float(np.mean(dur_bars)), 2),
                mean_duration_hours=round(mean_h, 2),
                mean_duration_days=round(mean_h / 24.0, 2),
                median_duration_hours=round(median_h, 2),
                max_duration_hours=round(max_h, 2),
                duration_quantiles_hours=quantiles,
                survival_curve=survival_points,
            )

        return results

    @classmethod
    def compute_regime_drift(
        cls,
        mode: str = "YEAR_VS_YEAR",
        param_a: str = "2025_Q4",
        param_b: str = "2026_Q1",
        interval: str = "1h",
    ) -> HistoricalRegimeDriftAnalysis:
        """
        Computes transition difference matrix, Frobenius matrix distance, and occupancy PSI.
        """
        mat_a = cls.compute_transition_matrix(interval=interval, period=param_a)
        mat_b = cls.compute_transition_matrix(interval=interval, period=param_b)

        p_a = np.array(mat_a.probabilities_matrix)
        p_b = np.array(mat_b.probabilities_matrix)

        diff_mat = p_b - p_a
        frobenius = float(np.linalg.norm(diff_mat, ord="fro"))

        # Occupancy distributions
        counts_a = np.sum(np.array(mat_a.counts_matrix), axis=1)
        counts_b = np.sum(np.array(mat_b.counts_matrix), axis=1)

        tot_a = max(1, int(np.sum(counts_a)))
        tot_b = max(1, int(np.sum(counts_b)))

        freq_a = counts_a / float(tot_a)
        freq_b = counts_b / float(tot_b)

        # PSI on occupancy
        psi = 0.0
        for fa, fb in zip(freq_a, freq_b):
            fa_adj = max(0.0001, fa)
            fb_adj = max(0.0001, fb)
            psi += (fb_adj - fa_adj) * math.log(fb_adj / fa_adj)

        # Jensen-Shannon Divergence
        m = 0.5 * (freq_a + freq_b)
        kl_am = stats.entropy(freq_a, m) if np.all(freq_a > 0) else 0.0
        kl_bm = stats.entropy(freq_b, m) if np.all(freq_b > 0) else 0.0
        jsd = float(0.5 * (kl_am + kl_bm))

        # Duration shifts
        dur_a = cls.compute_regime_durations(interval=interval, period=param_a)
        dur_b = cls.compute_regime_durations(interval=interval, period=param_b)
        dur_shifts = {
            r: round(dur_b[r].mean_duration_hours - dur_a[r].mean_duration_hours, 2)
            for r in cls.CANONICAL_REGIMES
            if r in dur_a and r in dur_b
        }

        significance_note = (
            f"{param_a} ile {param_b} dönemleri arasında Frobenius matris mesafesi {round(frobenius, 4)} ve "
            f"dağılım PSI değeri {round(psi, 4)} olarak hesaplanmıştır. "
            f"{'Yapısal geçiş kararlılığı yüksektir (PSI < 0.10).' if psi < 0.10 else 'Ilımlı rejim kayması gözlenmektedir.'} "
            "Bu değişimler tarihsel rejim sürekliliğinin dönemsel dalgalanmasını yansıtır; geleceğe yönelik kârlılık taahhüdü değildir."
        )

        return HistoricalRegimeDriftAnalysis(
            analysis_mode=mode,
            period_a_label=param_a,
            period_b_label=param_b,
            matrix_a=mat_a,
            matrix_b=mat_b,
            difference_matrix=[[round(float(v), 4) for v in row] for row in diff_mat.tolist()],
            frobenius_distance=round(frobenius, 4),
            jensen_shannon_divergence=round(jsd, 4),
            occupancy_shift_psi=round(psi, 4),
            duration_shifts=dur_shifts,
            drift_significance_tr=significance_note,
        )

    @classmethod
    def compute_macro_conditioned_transitions(
        cls,
        cohort: str = "US_CPI",
        window_hours: int = 12,
        interval: str = "1h",
    ) -> MacroConditionedRegimeTransitions:
        """
        Analyzes regime transition frequency and destination probabilities near verified macro events.
        """
        raw_df = cls.load_canonical_timeline()
        df = cls.filter_regime_observations(raw_df, interval=interval)

        if not cls.MACRO_EVENTS_PARQUET.exists() or df.empty:
            return MacroConditionedRegimeTransitions(
                cohort=cohort,
                events_analyzed_count=0,
                window_hours=window_hours,
                event_window_transition_rate=0.0,
                baseline_non_event_transition_rate=0.0,
                transition_rate_lift=1.0,
                event_conditioned_destination_probabilities={},
                baseline_destination_probabilities={},
                statistical_association_note_tr="Makro olay veri seti bulunamadı.",
                disclaimer_tr=cls.DISCLAIMER_TR,
            )

        events_df = pd.read_parquet(cls.MACRO_EVENTS_PARQUET)
        target_events = events_df[
            (events_df["event_category"] == cohort) |
            (events_df["event_id"].str.contains(cohort)) |
            (events_df["event_name"].str.contains(cohort))
        ]
        target_events = target_events[target_events["verification_status"] != "EVENT_QUARANTINED"]

        if target_events.empty:
            target_events = events_df[events_df["event_name"] == "US Consumer Price Index (CPI YoY)"]

        event_window_transitions = 0
        event_window_bars_total = 0
        event_dest_counts: Dict[str, int] = {r: 0 for r in cls.CANONICAL_REGIMES}

        # Baseline overall transition rate in the entire dataset
        total_transitions = int(np.sum(df["regime"].values[:-1] != df["regime"].values[1:]))
        total_pairs = max(1, len(df) - 1)
        baseline_rate = float(total_transitions) / float(total_pairs)

        analyzed_events_count = 0
        for _, ev in target_events.iterrows():
            t0 = pd.to_datetime(ev["scheduled_release_at_utc"], utc=True)
            w_start = t0 - pd.Timedelta(hours=window_hours)
            w_end = t0 + pd.Timedelta(hours=window_hours)

            ev_slice = df[(df["dt"] >= w_start) & (df["dt"] <= w_end)]
            if len(ev_slice) >= 2:
                analyzed_events_count += 1
                regs = ev_slice["regime"].values
                for k in range(len(regs) - 1):
                    event_window_bars_total += 1
                    if regs[k] != regs[k + 1]:
                        event_window_transitions += 1
                        event_dest_counts[regs[k + 1]] = event_dest_counts.get(regs[k + 1], 0) + 1

        ev_trans_rate = (float(event_window_transitions) / float(max(1, event_window_bars_total))) if event_window_bars_total > 0 else baseline_rate
        lift = round(ev_trans_rate / max(1e-6, baseline_rate), 3)

        # Destination probabilities
        tot_dest = max(1, sum(event_dest_counts.values()))
        event_dest_probs = {r: round(event_dest_counts[r] / float(tot_dest), 4) for r in cls.CANONICAL_REGIMES}

        # Baseline destination probabilities
        baseline_dest_counts = {r: int(np.sum(df["regime"] == r)) for r in cls.CANONICAL_REGIMES}
        tot_base = max(1, sum(baseline_dest_counts.values()))
        baseline_dest_probs = {r: round(baseline_dest_counts[r] / float(tot_base), 4) for r in cls.CANONICAL_REGIMES}

        note = (
            f"{cohort} kohortundaki {analyzed_events_count} doğrulanmış olay çevresinde (±{window_hours}h) "
            f"rejim geçiş frekansı %{round(ev_trans_rate * 100, 2)} olarak gözlenmiştir "
            f"(Genel taban oranı: %{round(baseline_rate * 100, 2)}, Göreli Değişim: {lift}x). "
            "Bu istatistiki ilişki olayların geçişe doğrudan neden olduğunu kanıtlamaz; piyasa oynaklığı "
            "kümelenmesinin doğal bir korelasyonudur."
        )

        return MacroConditionedRegimeTransitions(
            cohort=cohort,
            events_analyzed_count=analyzed_events_count,
            window_hours=window_hours,
            event_window_transition_rate=round(ev_trans_rate, 4),
            baseline_non_event_transition_rate=round(baseline_rate, 4),
            transition_rate_lift=lift,
            event_conditioned_destination_probabilities=event_dest_probs,
            baseline_destination_probabilities=baseline_dest_probs,
            statistical_association_note_tr=note,
            disclaimer_tr=cls.DISCLAIMER_TR,
        )

    @classmethod
    def get_sankey_flow_data(cls, interval: str = "1h", period: str = "ALL") -> Dict[str, Any]:
        """Generates nodes and links for interactive Sankey-style transition flow diagram."""
        matrix = cls.compute_transition_matrix(interval=interval, period=period)
        nodes = [
            {"id": r, "label": cls.REGIME_LABELS_TR.get(r, r), "color": cls.REGIME_COLORS.get(r, "#64748b")}
            for r in cls.CANONICAL_REGIMES
        ]

        links = []
        for cell in matrix.cells:
            # Include self transitions or focus on state shifts
            if cell.transition_count > 0:
                links.append({
                    "source": cell.from_regime,
                    "target": cell.to_regime,
                    "count": cell.transition_count,
                    "probability": cell.transition_probability,
                    "source_label": cell.from_regime_label_tr,
                    "target_label": cell.to_regime_label_tr,
                    "color": cls.REGIME_COLORS.get(cell.from_regime, "#64748b"),
                })

        return {
            "status": "success",
            "interval": interval,
            "period": period,
            "nodes": nodes,
            "links": links,
            "total_transitions": matrix.total_transitions_observed,
            "disclaimer_tr": cls.DISCLAIMER_TR,
        }

    @classmethod
    def get_regime_timeline_data(cls, interval: str = "1h", max_segments: int = 250) -> Dict[str, Any]:
        """Generates bounded chronological timeline segments with verified macro event markers."""
        raw_df = cls.load_canonical_timeline()
        df = cls.filter_regime_observations(raw_df, interval=interval)

        if df.empty:
            return {"status": "success", "segments": [], "event_markers": []}

        segments = []
        curr_r = None
        curr_start = None
        curr_end = None
        curr_bars = 0

        for idx, row in df.iterrows():
            r = row["regime"]
            dt_str = row["dt"].isoformat()
            if curr_r is None:
                curr_r = r
                curr_start = dt_str
                curr_end = dt_str
                curr_bars = 1
            elif r == curr_r:
                curr_end = dt_str
                curr_bars += 1
            else:
                segments.append({
                    "regime": curr_r,
                    "regime_label_tr": cls.REGIME_LABELS_TR.get(curr_r, curr_r),
                    "color": cls.REGIME_COLORS.get(curr_r, "#64748b"),
                    "start_utc": curr_start,
                    "end_utc": curr_end,
                    "bars": curr_bars,
                })
                curr_r = r
                curr_start = dt_str
                curr_end = dt_str
                curr_bars = 1

        if curr_r is not None:
            segments.append({
                "regime": curr_r,
                "regime_label_tr": cls.REGIME_LABELS_TR.get(curr_r, curr_r),
                "color": cls.REGIME_COLORS.get(curr_r, "#64748b"),
                "start_utc": curr_start,
                "end_utc": curr_end,
                "bars": curr_bars,
            })

        # Downsample segments if too many for fluid UI rendering
        if len(segments) > max_segments:
            step = max(1, len(segments) // max_segments)
            segments = segments[::step]

        # Extract macro event markers
        event_markers = []
        if cls.MACRO_EVENTS_PARQUET.exists():
            ev_df = pd.read_parquet(cls.MACRO_EVENTS_PARQUET)
            cpi_evs = ev_df[ev_df["event_name"] == "US Consumer Price Index (CPI YoY)"].tail(20)
            for _, ev in cpi_evs.iterrows():
                event_markers.append({
                    "event_id": ev["event_id"],
                    "event_name": ev["event_name"],
                    "release_utc": ev["scheduled_release_at_utc"],
                    "category": ev["event_category"],
                })

        return {
            "status": "success",
            "interval": interval,
            "total_segments_count": len(segments),
            "segments": segments,
            "event_markers": event_markers,
            "disclaimer_tr": cls.DISCLAIMER_TR,
        }

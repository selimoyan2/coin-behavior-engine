"""
CBE — Market Regime Distribution Drift Intelligence Engine
Measures structural drift in cryptocurrency market regimes between two historical observation windows.
Evaluates Population Stability Index (PSI), Jensen-Shannon Divergence (JSD), Wasserstein distance
over volatility states, regime transition probability dynamics, and mean persistence durations.
"""

from __future__ import annotations

from datetime import datetime, timezone
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cbe.regime_drift")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REGIME_FILE = REPO_ROOT / "research_outputs" / "market_regime_timeline.csv"

ORDERED_REGIMES = [
    "SIDEWAYS",
    "UNCERTAIN",
    "TRENDING_BULL",
    "TRENDING_BEAR",
    "POSSIBLE_REVERSAL",
    "HIGH_VOLATILITY",
]

REGIME_NAMES_TR = {
    "SIDEWAYS": "Yatay / Konsolidasyon",
    "UNCERTAIN": "Belirsiz / Kararsız",
    "TRENDING_BULL": "Boğa Trendi (Yükseliş)",
    "TRENDING_BEAR": "Ayı Trendi (Düşüş)",
    "POSSIBLE_REVERSAL": "Olası Dönüş / Tepe-Dip",
    "HIGH_VOLATILITY": "Yüksek Volatilite / Şok",
}


class RegimeDriftEngine:
    """Computes distribution divergence and transition dynamics across historical market regimes."""

    @classmethod
    def get_preset_windows(cls) -> List[Dict[str, Any]]:
        """Return predefined historical drift comparison windows."""
        return [
            {
                "id": "q4_2025_vs_q1_2026",
                "name": "2025-Q4 vs 2026-Q1",
                "window_a": {"start_utc": "2025-10-18T00:00:00Z", "end_utc": "2025-12-31T23:59:59Z", "label": "2025 Q4"},
                "window_b": {"start_utc": "2026-01-01T00:00:00Z", "end_utc": "2026-03-31T23:59:59Z", "label": "2026 Q1"},
            },
            {
                "id": "h1_2026_vs_h2_2026",
                "name": "2026-H1 vs 2026-H2",
                "window_a": {"start_utc": "2026-01-01T00:00:00Z", "end_utc": "2026-06-30T23:59:59Z", "label": "2026 Yılın İlk Yarısı"},
                "window_b": {"start_utc": "2026-07-01T00:00:00Z", "end_utc": "2026-10-18T23:59:59Z", "label": "2026 Yılın İkinci Yarısı"},
            },
            {
                "id": "q1_2026_vs_q3_2026",
                "name": "2026-Q1 vs 2026-Q3",
                "window_a": {"start_utc": "2026-01-01T00:00:00Z", "end_utc": "2026-03-31T23:59:59Z", "label": "2026 Q1"},
                "window_b": {"start_utc": "2026-07-01T00:00:00Z", "end_utc": "2026-09-30T23:59:59Z", "label": "2026 Q3"},
            },
            {
                "id": "last_30d_vs_prior_30d",
                "name": "Son 30 Gün vs Önceki 30 Gün",
                "window_a": {"start_utc": "2026-08-19T00:00:00Z", "end_utc": "2026-09-18T23:59:59Z", "label": "Önceki 30 Gün"},
                "window_b": {"start_utc": "2026-09-19T00:00:00Z", "end_utc": "2026-10-18T23:59:59Z", "label": "Son 30 Gün"},
            },
        ]

    @classmethod
    def load_regimes_for_window(
        cls,
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        csv_path: Optional[Path] = None,
    ) -> List[Dict[str, Any]]:
        """Load regime rows filtered by UTC timestamps."""
        import pandas as pd
        path = csv_path or DEFAULT_REGIME_FILE
        if not path.exists():
            return []

        df = pd.read_csv(path)
        if start_utc:
            df = df[df["datetime_utc"] >= start_utc]
        if end_utc:
            df = df[df["datetime_utc"] <= end_utc]

        return df.to_dict(orient="records")

    @classmethod
    def compute_regime_frequencies(
        cls,
        records: List[Dict[str, Any]],
        regimes: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Compute frequency distribution vector for market regimes."""
        target_regimes = regimes or ORDERED_REGIMES
        counts = {r: 0 for r in target_regimes}
        for rec in records:
            reg = str(rec.get("regime", "")).strip().upper()
            if reg in counts:
                counts[reg] += 1
            else:
                counts["UNCERTAIN"] = counts.get("UNCERTAIN", 0) + 1

        total = len(records)
        proportions = {}
        distribution_list = []
        for r in target_regimes:
            cnt = counts[r]
            pct = round((cnt / total) * 100.0, 2) if total > 0 else 0.0
            prop = (cnt / total) if total > 0 else 0.0
            proportions[r] = prop
            distribution_list.append({
                "regime": r,
                "regime_name_tr": REGIME_NAMES_TR.get(r, r),
                "count": cnt,
                "percentage": pct,
                "proportion": prop,
            })

        return {
            "total_bars": total,
            "counts": counts,
            "proportions": proportions,
            "distribution": distribution_list,
        }

    @classmethod
    def compute_mean_durations(cls, records: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
        """Calculate mean persistence duration in consecutive bars and hours per regime."""
        if not records:
            return {r: {"mean_bars": 0.0, "mean_hours": 0.0, "max_hours": 0.0, "episodes_count": 0} for r in ORDERED_REGIMES}

        episodes: Dict[str, List[int]] = {r: [] for r in ORDERED_REGIMES}
        current_regime = str(records[0].get("regime", "")).strip().upper()
        current_run = 1

        for i in range(1, len(records)):
            r = str(records[i].get("regime", "")).strip().upper()
            if r == current_regime:
                current_run += 1
            else:
                if current_regime in episodes:
                    episodes[current_regime].append(current_run)
                current_regime = r
                current_run = 1
        if current_regime in episodes:
            episodes[current_regime].append(current_run)

        durations: Dict[str, Dict[str, float]] = {}
        for r in ORDERED_REGIMES:
            runs = episodes[r]
            if runs:
                mean_bars = round(sum(runs) / len(runs), 1)
                mean_hrs = round((mean_bars * 5) / 60, 2)
                max_hrs = round((max(runs) * 5) / 60, 2)
                ep_cnt = len(runs)
            else:
                mean_bars = 0.0
                mean_hrs = 0.0
                max_hrs = 0.0
                ep_cnt = 0
            durations[r] = {
                "mean_bars": mean_bars,
                "mean_hours": mean_hrs,
                "max_hours": max_hrs,
                "episodes_count": ep_cnt,
            }
        return durations

    @classmethod
    def compute_transition_matrix(
        cls,
        records: List[Dict[str, Any]],
        regimes: Optional[List[str]] = None,
    ) -> Dict[str, Dict[str, float]]:
        """Compute conditional transition probability matrix P(to | from)."""
        target_regimes = regimes or ORDERED_REGIMES
        matrix = {r1: {r2: 0 for r2 in target_regimes} for r1 in target_regimes}

        for i in range(1, len(records)):
            r_from = str(records[i - 1].get("regime", "")).strip().upper()
            r_to = str(records[i].get("regime", "")).strip().upper()
            if r_from in matrix and r_to in matrix[r_from]:
                matrix[r_from][r_to] += 1

        prob_matrix = {}
        for r_from, transitions in matrix.items():
            tot = sum(transitions.values())
            prob_matrix[r_from] = {}
            for r_to, count in transitions.items():
                prob_matrix[r_from][r_to] = round((count / tot), 4) if tot > 0 else 0.0

        return prob_matrix

    @classmethod
    def compute_jsd(
        cls,
        p_props: Dict[str, float],
        q_props: Dict[str, float],
        regimes: Optional[List[str]] = None,
    ) -> float:
        """Compute Jensen-Shannon Divergence between two distributions P and Q."""
        target_regimes = regimes or ORDERED_REGIMES
        # M = 0.5 * (P + Q)
        kl_pm = 0.0
        kl_qm = 0.0

        for r in target_regimes:
            p = p_props.get(r, 0.0)
            q = q_props.get(r, 0.0)
            m = 0.5 * (p + q)
            if p > 0.0 and m > 0.0:
                kl_pm += p * math.log2(p / m)
            if q > 0.0 and m > 0.0:
                kl_qm += q * math.log2(q / m)

        jsd = 0.5 * kl_pm + 0.5 * kl_qm
        return round(float(jsd), 4)

    @classmethod
    def compute_psi(
        cls,
        p_props: Dict[str, float],
        q_props: Dict[str, float],
        regimes: Optional[List[str]] = None,
        epsilon: float = 1e-5,
        threshold_moderate: float = 0.10,
        threshold_significant: float = 0.25,
    ) -> Tuple[float, str, str]:
        """
        Compute Population Stability Index (PSI).
        PSI = sum((Q_i - P_i) * ln(Q_i / P_i))
        """
        target_regimes = regimes or ORDERED_REGIMES
        total_psi = 0.0

        for r in target_regimes:
            p = max(p_props.get(r, 0.0), epsilon)
            q = max(q_props.get(r, 0.0), epsilon)
            component = (q - p) * math.log(q / p)
            total_psi += component

        rounded_psi = round(float(total_psi), 4)

        if rounded_psi < threshold_moderate:
            status = "STABLE"
            label_tr = "Dengeli (Düşük Yapısal Değişim)"
        elif rounded_psi < threshold_significant:
            status = "MODERATE_DRIFT"
            label_tr = "Orta Düzey Rejim Kayması (İzlenmeli)"
        else:
            status = "SIGNIFICANT_DRIFT"
            label_tr = "Yüksek Yapısal Rejim Kayması"

        return rounded_psi, status, label_tr

    @classmethod
    def compute_wasserstein_volatility(
        cls,
        p_props: Dict[str, float],
        q_props: Dict[str, float],
        regimes: Optional[List[str]] = None,
    ) -> float:
        """
        Compute Wasserstein-1 distance on ordered volatility rank states.
        W_1(P, Q) = sum |F_P(k) - F_Q(k)|
        """
        target_regimes = regimes or ORDERED_REGIMES
        cum_p = 0.0
        cum_q = 0.0
        total_w = 0.0

        for r in target_regimes:
            cum_p += p_props.get(r, 0.0)
            cum_q += q_props.get(r, 0.0)
            total_w += abs(cum_p - cum_q)

        return round(float(total_w), 4)

    @classmethod
    def analyze_drift(
        cls,
        window_a: Dict[str, Any],
        window_b: Dict[str, Any],
        psi_threshold_moderate: float = 0.10,
        psi_threshold_significant: float = 0.25,
        jsd_threshold_moderate: float = 0.05,
        jsd_threshold_significant: float = 0.15,
        min_sample_bars: int = 100,
    ) -> Dict[str, Any]:
        """Perform comprehensive comparative regime distribution drift analysis with configurable evaluation thresholds."""
        records_a = cls.load_regimes_for_window(
            start_utc=window_a.get("start_utc"),
            end_utc=window_a.get("end_utc"),
        )
        records_b = cls.load_regimes_for_window(
            start_utc=window_b.get("start_utc"),
            end_utc=window_b.get("end_utc"),
        )

        freq_a = cls.compute_regime_frequencies(records_a)
        freq_b = cls.compute_regime_frequencies(records_b)

        dur_a = cls.compute_mean_durations(records_a)
        dur_b = cls.compute_mean_durations(records_b)

        trans_a = cls.compute_transition_matrix(records_a)
        trans_b = cls.compute_transition_matrix(records_b)

        jsd = cls.compute_jsd(freq_a["proportions"], freq_b["proportions"])
        psi_score, psi_status, psi_label = cls.compute_psi(
            freq_a["proportions"],
            freq_b["proportions"],
            threshold_moderate=psi_threshold_moderate,
            threshold_significant=psi_threshold_significant,
        )
        wasserstein = cls.compute_wasserstein_volatility(freq_a["proportions"], freq_b["proportions"])

        # Sample size warning check
        sample_warning = None
        if len(records_a) < min_sample_bars or len(records_b) < min_sample_bars:
            sample_warning = (
                f"Örneklem büyüklüğü minimum güven eşiğinin ({min_sample_bars} bar) altında: "
                f"Pencere A: {len(records_a)}, Pencere B: {len(records_b)} bar."
            )

        # Side-by-side distribution comparison table
        comparison_rows = []
        for r in ORDERED_REGIMES:
            pct_a = freq_a["counts"].get(r, 0)
            pct_b = freq_b["counts"].get(r, 0)
            prop_a = freq_a["proportions"].get(r, 0.0)
            prop_b = freq_b["proportions"].get(r, 0.0)
            pct_val_a = round(prop_a * 100.0, 2)
            pct_val_b = round(prop_b * 100.0, 2)
            delta_pct = round(pct_val_b - pct_val_a, 2)

            comparison_rows.append({
                "regime": r,
                "regime_name_tr": REGIME_NAMES_TR.get(r, r),
                "count_a": pct_a,
                "pct_a": pct_val_a,
                "count_b": pct_b,
                "pct_b": pct_val_b,
                "delta_pct": delta_pct,
                "mean_hours_a": dur_a.get(r, {}).get("mean_hours", 0.0),
                "mean_hours_b": dur_b.get(r, {}).get("mean_hours", 0.0),
            })

        return {
            "status": "success",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "model_version": "CBE-0.7.0",
            "window_a": {
                "label": window_a.get("label", "Window A"),
                "start_utc": window_a.get("start_utc"),
                "end_utc": window_a.get("end_utc"),
                "total_bars": len(records_a),
                "frequencies": freq_a,
                "mean_durations": dur_a,
                "transition_matrix": trans_a,
            },
            "window_b": {
                "label": window_b.get("label", "Window B"),
                "start_utc": window_b.get("start_utc"),
                "end_utc": window_b.get("end_utc"),
                "total_bars": len(records_b),
                "frequencies": freq_b,
                "mean_durations": dur_b,
                "transition_matrix": trans_b,
            },
            "drift_telemetry": {
                "population_stability_index": psi_score,
                "psi_status": psi_status,
                "psi_label_tr": psi_label,
                "jensen_shannon_divergence": jsd,
                "wasserstein_distance": wasserstein,
                "sample_size_warning": sample_warning,
            },
            "sensitivity_parameters": {
                "psi_threshold_moderate": psi_threshold_moderate,
                "psi_threshold_significant": psi_threshold_significant,
                "jsd_threshold_moderate": jsd_threshold_moderate,
                "jsd_threshold_significant": jsd_threshold_significant,
                "min_sample_bars": min_sample_bars,
                "model_mutation_prohibited": True,
            },
            "comparison_rows": comparison_rows,
            "governance_safeguard": {
                "predictive_alpha": "NOT_CLAIMED",
                "purpose": "STRUCTURAL_MARKET_REGIME_DRIFT_RESEARCH",
                "scientific_status": "OFFLINE_DETERMINISTIC_EVALUATION",
            },
        }

    @classmethod
    def analyze_drift_for_months(
        cls,
        baseline_month: str,
        target_month: str,
        psi_threshold_moderate: float = 0.10,
        psi_threshold_significant: float = 0.25,
        jsd_threshold_moderate: float = 0.05,
        jsd_threshold_significant: float = 0.15,
        min_sample_bars: int = 100,
    ) -> Dict[str, Any]:
        """Convenience method to compare two calendar months directly."""
        import calendar
        try:
            yr_a, mn_a = int(baseline_month[:4]), int(baseline_month[5:7])
            last_a = calendar.monthrange(yr_a, mn_a)[1]
            start_a = f"{baseline_month}-01T00:00:00Z"
            end_a = f"{baseline_month}-{last_a:02d}T23:59:59Z"
        except Exception:
            start_a = f"{baseline_month}-01T00:00:00Z"
            end_a = f"{baseline_month}-28T23:59:59Z"

        try:
            yr_b, mn_b = int(target_month[:4]), int(target_month[5:7])
            last_b = calendar.monthrange(yr_b, mn_b)[1]
            start_b = f"{target_month}-01T00:00:00Z"
            end_b = f"{target_month}-{last_b:02d}T23:59:59Z"
        except Exception:
            start_b = f"{target_month}-01T00:00:00Z"
            end_b = f"{target_month}-28T23:59:59Z"

        window_a = {"label": f"{baseline_month} (Referans)", "start_utc": start_a, "end_utc": end_a}
        window_b = {"label": f"{target_month} (Gözlem)", "start_utc": start_b, "end_utc": end_b}

        return cls.analyze_drift(
            window_a=window_a,
            window_b=window_b,
            psi_threshold_moderate=psi_threshold_moderate,
            psi_threshold_significant=psi_threshold_significant,
            jsd_threshold_moderate=jsd_threshold_moderate,
            jsd_threshold_significant=jsd_threshold_significant,
            min_sample_bars=min_sample_bars,
        )

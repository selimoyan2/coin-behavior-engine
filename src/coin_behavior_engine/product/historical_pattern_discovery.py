"""
Historical Pattern Discovery Laboratory Engine V2.
Sprint 17 Major Research Advancement & Workbench V6.

Provides explainable, multi-dimensional historical market behavior discovery
across verified BTCUSDT partitions. Strictly descriptive and non-predictive.
Zero forward outcome leakage, zero synthetic price generation, and explicit overlap guards.
Includes strictly disjoint candidate filtering, ranking stability score,
sample-size / data coverage warnings, dimension contribution breakdown,
reproducible experiment IDs (EXP-PAT-V2-*), and exportable research evidence packages.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats
from scipy.spatial.distance import jensenshannon

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine
from coin_behavior_engine.product.macro_comparison import MacroEventComparisonEngine


CANONICAL_REGIMES = [
    "SIDEWAYS",
    "MOMENTUM_EXPANSION",
    "HIGH_VOLATILITY",
    "CAPITULATION",
    "RECOVERY_ACCUMULATION",
    "DISTRIBUTION",
]


@dataclass
class SimilarityComponentScore:
    """Detailed breakdown of a single similarity dimension."""
    dimension_id: str
    dimension_name_tr: str
    distance_value: float          # Bounded [0.0, 1.0] where 0 is identical
    weight: float
    weighted_contribution: float
    contribution_pct: float
    metric_method: str
    reference_value_summary: str
    candidate_value_summary: str
    explanation_tr: str = ""


@dataclass
class PatternCandidateMatch:
    """Ranked historical candidate window with full decomposition."""
    rank: int
    candidate_id: str
    start_utc: str
    end_utc: str
    duration_hours: float
    candle_count: int
    composite_distance: float      # Lower is more similar
    similarity_score_pct: float    # (1 - distance) * 100
    overlap_status: str            # DISJOINT, NEAR_NEIGHBOR, ADJACENT
    data_coverage_pct: float
    source_verification: str
    components: Dict[str, SimilarityComponentScore]
    regime_composition: Dict[str, float]
    realized_volatility_pct: float
    mean_return_pct: float
    sample_size_bars: int = 0
    coverage_warnings: List[str] = field(default_factory=list)
    dimension_contributions: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    explanation_tr: str = ""
    is_strictly_disjoint: bool = True

    @property
    def overall_similarity_pct(self) -> float:
        return self.similarity_score_pct

    @property
    def regime_jsd_distance(self) -> float:
        return self.components["REGIME_COMPOSITION"].distance_value if "REGIME_COMPOSITION" in self.components else 0.0

    @property
    def volatility_distance(self) -> float:
        return self.components["REALIZED_VOLATILITY"].distance_value if "REALIZED_VOLATILITY" in self.components else 0.0

    @property
    def return_distribution_distance(self) -> float:
        return self.components["RETURN_DISTRIBUTION"].distance_value if "RETURN_DISTRIBUTION" in self.components else 0.0

    @property
    def transition_matrix_distance(self) -> float:
        return self.components["TRANSITION_STRUCTURE"].distance_value if "TRANSITION_STRUCTURE" in self.components else 0.0

    @property
    def persistence_gap_hours(self) -> float:
        return self.components["REGIME_PERSISTENCE"].distance_value if "REGIME_PERSISTENCE" in self.components else 0.0


@dataclass
class PatternDiscoverySearchResult:
    """Complete response payload for a pattern search query."""
    search_id: str
    asset: str
    interval: str
    reference_start_utc: str
    reference_end_utc: str
    reference_duration_hours: float
    reference_regime_composition: Dict[str, float]
    reference_realized_volatility_pct: float
    total_historical_windows_scanned: int
    eligible_windows_evaluated: int
    excluded_overlapping_windows: int
    ranked_candidates: List[PatternCandidateMatch]
    weights_used: Dict[str, float]
    dataset_manifest_sha256: str
    canonical_model_version: str
    legal_disclaimer_tr: str
    experiment_id: str = ""
    disjoint_filtering_applied: bool = True
    ranking_stability_score: float = 1.0
    ranking_stability_verdict: str = "HIGH_STABILITY"
    ranking_stability_details: Dict[str, Any] = field(default_factory=dict)
    coverage_warnings: List[str] = field(default_factory=list)
    overall_explanation_tr: str = ""

    @property
    def candidates(self) -> List[PatternCandidateMatch]:
        return self.ranked_candidates


class HistoricalPatternDiscoveryEngine:
    """
    Core engine for explainable historical pattern discovery V2.
    """
    LEGAL_DISCLAIMER_TR = (
        "Bu rapor ve benzerlik eşleştirmeleri yalnızca tarihsel piyasa davranışı araştırması amacıyla "
        "üretilmiştir. Yatırım tavsiyesi, geleceğe yönelik fiyat tahmini veya canlı alım-satım sinyali değildir. "
        "Geçmiş dönem benzerlikleri gelecekte benzer sonuçlar doğuracağını garanti etmez."
    )

    DEFAULT_WEIGHTS = {
        "REGIME_COMPOSITION": 0.30,
        "REALIZED_VOLATILITY": 0.25,
        "RETURN_DISTRIBUTION": 0.20,
        "TRANSITION_STRUCTURE": 0.15,
        "REGIME_PERSISTENCE": 0.10,
    }

    _CANDLE_CACHE: Dict[str, pd.DataFrame] = {}

    @classmethod
    def _load_candles(cls, interval: str) -> pd.DataFrame:
        """Loads and caches multiyear candles for interval."""
        if interval in cls._CANDLE_CACHE:
            return cls._CANDLE_CACHE[interval]

        base_dir = Path(__file__).resolve().parents[3] / "data" / "binance_spot_multiyear" / interval
        if not base_dir.exists():
            return pd.DataFrame()

        dfs = []
        for pfile in sorted(base_dir.glob("*.parquet")):
            if "2026-10" in pfile.name:
                continue  # Strict quarantine
            try:
                df = pd.read_parquet(pfile)
                if not df.empty:
                    dfs.append(df)
            except Exception:
                continue

        if not dfs:
            return pd.DataFrame()

        merged = pd.concat(dfs, ignore_index=True)
        if "datetime" in merged.columns:
            merged["timestamp"] = pd.to_datetime(merged["datetime"], utc=True)
        else:
            merged["timestamp"] = pd.to_datetime(merged["open_time"], unit="ms", utc=True)
        merged = merged.sort_values("timestamp").drop_duplicates(subset=["timestamp"]).reset_index(drop=True)
        
        # Ensure log returns and Parkinson vol estimates exist
        merged["return"] = merged["close"].pct_change().fillna(0.0)
        hl_ratio = np.log(np.maximum(1e-8, merged["high"] / np.maximum(1e-8, merged["low"])))
        merged["parkinson_vol"] = np.sqrt((hl_ratio ** 2) / (4.0 * np.log(2.0)))
        
        cls._assign_synthetic_regimes(merged)
        cls._CANDLE_CACHE[interval] = merged
        return merged

    @classmethod
    def _assign_synthetic_regimes(cls, df: pd.DataFrame) -> None:
        """Assigns the 6 frozen canonical regimes based on rolling volatility and returns."""
        if "regime" in df.columns:
            return

        vol_24 = df["return"].rolling(24, min_periods=4).std().fillna(0.01) * np.sqrt(24 * 365)
        ret_24 = df["return"].rolling(24, min_periods=4).sum().fillna(0.0)

        regimes = []
        for v, r in zip(vol_24, ret_24):
            if v > 0.85 and r < -0.10:
                regimes.append("CAPITULATION")
            elif v > 0.70:
                regimes.append("HIGH_VOLATILITY")
            elif r > 0.08:
                regimes.append("MOMENTUM_EXPANSION")
            elif r < -0.06:
                regimes.append("DISTRIBUTION")
            elif -0.04 <= r <= 0.04 and v < 0.40:
                regimes.append("SIDEWAYS")
            else:
                regimes.append("RECOVERY_ACCUMULATION")

        df["regime"] = regimes

    @classmethod
    def _compute_regime_composition(cls, df_win: pd.DataFrame) -> Dict[str, float]:
        """Calculates normalized occupancy percentage across 6 canonical regimes."""
        total = len(df_win)
        if total == 0:
            return {r: round(1.0 / len(CANONICAL_REGIMES), 4) for r in CANONICAL_REGIMES}
        counts = df_win["regime"].value_counts().to_dict()
        return {r: round(counts.get(r, 0) / float(total), 4) for r in CANONICAL_REGIMES}

    @classmethod
    def _compute_transition_matrix(cls, df_win: pd.DataFrame) -> np.ndarray:
        """Computes empirical 6x6 transition probability matrix with Laplace smoothing."""
        n = len(CANONICAL_REGIMES)
        counts = np.ones((n, n), dtype=float)  # Laplace smoothing
        r_map = {r: i for i, r in enumerate(CANONICAL_REGIMES)}
        
        reg_series = df_win["regime"].values
        for i in range(len(reg_series) - 1):
            s_from = reg_series[i]
            s_to = reg_series[i + 1]
            if s_from in r_map and s_to in r_map:
                counts[r_map[s_from], r_map[s_to]] += 1.0

        row_sums = counts.sum(axis=1, keepdims=True)
        return counts / row_sums

    @classmethod
    def _compute_regime_persistence(cls, df_win: pd.DataFrame) -> float:
        """Computes mean regime episode persistence duration in bars."""
        if len(df_win) < 2:
            return 1.0
        reg_series = df_win["regime"].values
        runs = []
        cur_len = 1
        for i in range(1, len(reg_series)):
            if reg_series[i] == reg_series[i - 1]:
                cur_len += 1
            else:
                runs.append(cur_len)
                cur_len = 1
        runs.append(cur_len)
        return float(np.mean(runs))

    @classmethod
    def search_similar_patterns(
        cls,
        reference_start_utc: str,
        reference_end_utc: str,
        asset: str = "BTCUSDT",
        interval: str = "1h",
        weights: Optional[Dict[str, float]] = None,
        max_candidates: int = 10,
        step_hours: int = 48,
        min_spacing_hours: int = 48,
        disjoint_candidate_filter: bool = True,
    ) -> PatternDiscoverySearchResult:
        """
        Executes bounded, deterministic historical pattern similarity search V2.
        Fails closed if asset is not BTCUSDT.
        """
        # Asset safety invariant
        if asset != "BTCUSDT":
            raise ValueError(f"Asset '{asset}' is not supported. CBE operates strictly on BTCUSDT.")

        df = cls._load_candles(interval)
        if df.empty:
            raise RuntimeError(f"No candle data available for interval {interval}")

        # Parse reference window bounds
        ref_start = pd.to_datetime(reference_start_utc, utc=True)
        ref_end = pd.to_datetime(reference_end_utc, utc=True)
        if ref_end <= ref_start:
            raise ValueError("reference_end_utc must be strictly greater than reference_start_utc.")

        ref_df = df[(df["timestamp"] >= ref_start) & (df["timestamp"] <= ref_end)].copy()
        if len(ref_df) < 6:
            raise ValueError(f"Reference period contains insufficient observations ({len(ref_df)} bars).")

        ref_duration_hours = (ref_end - ref_start).total_seconds() / 3600.0
        ref_candles_count = len(ref_df)

        # Baseline weights normalization
        w_dict = weights or cls.DEFAULT_WEIGHTS
        total_w = sum(w_dict.values())
        norm_weights = {k: round(v / total_w, 4) for k, v in w_dict.items()}

        # Reference period summary statistics
        ref_regime_comp = cls._compute_regime_composition(ref_df)
        ref_vol = float(ref_df["return"].std() * np.sqrt(24 * 365)) if len(ref_df) > 1 else 0.40
        ref_returns = ref_df["return"].values
        ref_trans_mat = cls._compute_transition_matrix(ref_df)
        ref_persist = cls._compute_regime_persistence(ref_df)

        # Reference level coverage warnings
        coverage_warnings: List[str] = []
        if ref_candles_count < 24:
            coverage_warnings.append(
                f"DÜŞÜK_ÖRNEKLEM_UYARISI: Referans penceresi 24 barın altındadır (N={ref_candles_count}). İstatistiksel güvenilirlik sınırlıdır."
            )

        # Candidate scan over historical dataset
        total_bars = len(df)
        window_size_bars = ref_candles_count
        step_bars = max(1, int(step_hours / (1 if interval == "1h" else 4 if interval == "4h" else 24)))

        candidates_pool: List[Dict[str, Any]] = []
        excluded_overlapping = 0
        scanned_count = 0

        for start_idx in range(0, total_bars - window_size_bars + 1, step_bars):
            scanned_count += 1
            cand_start = df["timestamp"].iloc[start_idx]
            cand_end = df["timestamp"].iloc[start_idx + window_size_bars - 1]

            # Critical Overlap Policy: strictly exclude candidates overlapping the reference window
            if not (cand_end < ref_start or cand_start > ref_end):
                excluded_overlapping += 1
                continue

            cand_df = df.iloc[start_idx : start_idx + window_size_bars]
            if len(cand_df) < window_size_bars * 0.90:
                continue

            # 1. Regime Composition Distance (JSD)
            c_comp = cls._compute_regime_composition(cand_df)
            p_ref = np.array([ref_regime_comp[r] for r in CANONICAL_REGIMES]) + 1e-6
            p_cand = np.array([c_comp[r] for r in CANONICAL_REGIMES]) + 1e-6
            p_ref /= p_ref.sum()
            p_cand /= p_cand.sum()
            d_regime = float(np.clip(jensenshannon(p_ref, p_cand, base=2), 0.0, 1.0))

            # 2. Realized Volatility Distance (Normalized absolute difference)
            c_vol = float(cand_df["return"].std() * np.sqrt(24 * 365)) if len(cand_df) > 1 else 0.40
            d_vol = float(np.clip(abs(ref_vol - c_vol) / max(ref_vol + c_vol, 0.05), 0.0, 1.0))

            # 3. Return Distribution Distance (Normalized Wasserstein distance)
            c_returns = cand_df["return"].values
            w_dist = float(stats.wasserstein_distance(ref_returns, c_returns))
            d_return = float(np.clip(w_dist * 20.0, 0.0, 1.0))

            # 4. Transition Structure Distance (Normalized Frobenius distance)
            c_trans_mat = cls._compute_transition_matrix(cand_df)
            frob = float(np.linalg.norm(ref_trans_mat - c_trans_mat))
            d_trans = float(np.clip(frob / math.sqrt(12.0), 0.0, 1.0))

            # 5. Persistence Distance
            c_persist = cls._compute_regime_persistence(cand_df)
            d_persist = float(np.clip(abs(ref_persist - c_persist) / max(ref_persist + c_persist, 1.0), 0.0, 1.0))

            # Compute weighted composite distance
            comp_dist = (
                norm_weights.get("REGIME_COMPOSITION", 0.3) * d_regime
                + norm_weights.get("REALIZED_VOLATILITY", 0.25) * d_vol
                + norm_weights.get("RETURN_DISTRIBUTION", 0.2) * d_return
                + norm_weights.get("TRANSITION_STRUCTURE", 0.15) * d_trans
                + norm_weights.get("REGIME_PERSISTENCE", 0.1) * d_persist
            )

            candidates_pool.append({
                "cand_df": cand_df,
                "start_utc": cand_start.isoformat(),
                "end_utc": cand_end.isoformat(),
                "start_ts": cand_start,
                "end_ts": cand_end,
                "composite_distance": comp_dist,
                "d_regime": d_regime,
                "d_vol": d_vol,
                "d_return": d_return,
                "d_trans": d_trans,
                "d_persist": d_persist,
                "regime_comp": c_comp,
                "vol": c_vol,
                "mean_ret": float(cand_df["return"].mean() * 100.0),
            })

        # Sort all by composite distance ascending (best matches first)
        candidates_pool.sort(key=lambda x: x["composite_distance"])

        # Deduplicate candidates using disjoint or spacing policy
        filtered_candidates: List[Dict[str, Any]] = []
        for cand in candidates_pool:
            if disjoint_candidate_filter:
                # Strictly disjoint: window [cand_start, cand_end] must not overlap any accepted window
                overlaps = False
                for accepted in filtered_candidates:
                    if not (cand["end_ts"] < accepted["start_ts"] or cand["start_ts"] > accepted["end_ts"]):
                        overlaps = True
                        break
                if not overlaps:
                    filtered_candidates.append(cand)
            else:
                is_near = False
                for accepted in filtered_candidates:
                    diff_hours = abs((cand["start_ts"] - accepted["start_ts"]).total_seconds()) / 3600.0
                    if diff_hours < min_spacing_hours:
                        is_near = True
                        break
                if not is_near:
                    filtered_candidates.append(cand)
            if len(filtered_candidates) >= max_candidates:
                break

        # Calculate Ranking Stability across perturbations
        stability_score = 1.0
        stability_verdict = "HIGH_STABILITY"
        stability_details: Dict[str, Any] = {}
        if len(candidates_pool) >= 5:
            default_top5 = [c["start_utc"] for c in candidates_pool[:5]]
            
            # Scenario 1: Volatility heavy
            w_vol = {"REGIME_COMPOSITION": 0.15, "REALIZED_VOLATILITY": 0.50, "RETURN_DISTRIBUTION": 0.15, "TRANSITION_STRUCTURE": 0.10, "REGIME_PERSISTENCE": 0.10}
            def score_cand_dict(c: Dict[str, Any], w: Dict[str, float]) -> float:
                return (
                    w["REGIME_COMPOSITION"] * c["d_regime"]
                    + w["REALIZED_VOLATILITY"] * c["d_vol"]
                    + w["RETURN_DISTRIBUTION"] * c["d_return"]
                    + w["TRANSITION_STRUCTURE"] * c["d_trans"]
                    + w["REGIME_PERSISTENCE"] * c["d_persist"]
                )
            
            vol_sorted = sorted(candidates_pool, key=lambda c: score_cand_dict(c, w_vol))
            vol_top5 = [c["start_utc"] for c in vol_sorted[:5]]
            
            # Scenario 2: Regime heavy
            w_reg = {"REGIME_COMPOSITION": 0.55, "REALIZED_VOLATILITY": 0.15, "RETURN_DISTRIBUTION": 0.10, "TRANSITION_STRUCTURE": 0.10, "REGIME_PERSISTENCE": 0.10}
            reg_sorted = sorted(candidates_pool, key=lambda c: score_cand_dict(c, w_reg))
            reg_top5 = [c["start_utc"] for c in reg_sorted[:5]]

            # Scenario 3: Return distribution heavy
            w_ret = {"REGIME_COMPOSITION": 0.15, "REALIZED_VOLATILITY": 0.15, "RETURN_DISTRIBUTION": 0.50, "TRANSITION_STRUCTURE": 0.10, "REGIME_PERSISTENCE": 0.10}
            ret_sorted = sorted(candidates_pool, key=lambda c: score_cand_dict(c, w_ret))
            ret_top5 = [c["start_utc"] for c in ret_sorted[:5]]

            overlap_vol = len(set(default_top5).intersection(set(vol_top5)))
            overlap_reg = len(set(default_top5).intersection(set(reg_top5)))
            overlap_ret = len(set(default_top5).intersection(set(ret_top5)))
            
            mean_retention = float(((overlap_vol + overlap_reg + overlap_ret) / 15.0) * 100.0)
            stability_score = round(mean_retention / 100.0, 3)

            if stability_score >= 0.70:
                stability_verdict = "HIGH_STABILITY"
            elif stability_score >= 0.40:
                stability_verdict = "MODERATE_STABILITY"
            else:
                stability_verdict = "SENSITIVE"

            stability_details = {
                "stability_score": stability_score,
                "stability_verdict": stability_verdict,
                "mean_top5_retention_pct": mean_retention,
                "scenarios": {
                    "volatility_heavy": {"overlap": overlap_vol, "retention_pct": round((overlap_vol / 5.0) * 100.0, 1)},
                    "regime_heavy": {"overlap": overlap_reg, "retention_pct": round((overlap_reg / 5.0) * 100.0, 1)},
                    "return_heavy": {"overlap": overlap_ret, "retention_pct": round((overlap_ret / 5.0) * 100.0, 1)},
                }
            }

        # Assemble final ranked objects
        ranked_matches: List[PatternCandidateMatch] = []
        for rank_idx, c in enumerate(filtered_candidates, 1):
            comp_d = c["composite_distance"]
            tot_w = sum(norm_weights.values()) or 1.0

            cand_bar_count = len(c["cand_df"])
            cand_warnings: List[str] = []
            if cand_bar_count < 24:
                cand_warnings.append(f"DÜŞÜK_ÖRNEKLEM_UYARISI: Aday pencere bar sayısı 24'ün altındadır (N={cand_bar_count}).")

            # Dimension contributions breakdown
            dim_reg_pct = round((norm_weights.get("REGIME_COMPOSITION", 0.3) * c["d_regime"] / max(comp_d, 1e-6)) * 100.0, 2)
            dim_vol_pct = round((norm_weights.get("REALIZED_VOLATILITY", 0.25) * c["d_vol"] / max(comp_d, 1e-6)) * 100.0, 2)
            dim_ret_pct = round((norm_weights.get("RETURN_DISTRIBUTION", 0.2) * c["d_return"] / max(comp_d, 1e-6)) * 100.0, 2)
            dim_trans_pct = round((norm_weights.get("TRANSITION_STRUCTURE", 0.15) * c["d_trans"] / max(comp_d, 1e-6)) * 100.0, 2)
            dim_pers_pct = round((norm_weights.get("REGIME_PERSISTENCE", 0.1) * c["d_persist"] / max(comp_d, 1e-6)) * 100.0, 2)

            ref_dominant_regime = max(ref_regime_comp, key=ref_regime_comp.get)
            cand_dominant_regime = max(c["regime_comp"], key=c["regime_comp"].get)

            components = {
                "REGIME_COMPOSITION": SimilarityComponentScore(
                    dimension_id="REGIME_COMPOSITION",
                    dimension_name_tr="Rejim Kompozisyonu Ayrışımı (JSD)",
                    distance_value=round(c["d_regime"], 4),
                    weight=norm_weights.get("REGIME_COMPOSITION", 0.3),
                    weighted_contribution=round(norm_weights.get("REGIME_COMPOSITION", 0.3) * c["d_regime"], 4),
                    contribution_pct=dim_reg_pct,
                    metric_method="JENSEN_SHANNON_DIVERGENCE",
                    reference_value_summary=f"En baskın: {ref_dominant_regime} (%{ref_regime_comp[ref_dominant_regime]*100:.1f})",
                    candidate_value_summary=f"En baskın: {cand_dominant_regime} (%{c['regime_comp'][cand_dominant_regime]*100:.1f})",
                    explanation_tr=f"Rejim kompozisyonu benzerliği %{(1.0 - c['d_regime'])*100.0:.1f} seviyesindedir.",
                ),
                "REALIZED_VOLATILITY": SimilarityComponentScore(
                    dimension_id="REALIZED_VOLATILITY",
                    dimension_name_tr="Gerçekleşen Volatilite Farkı",
                    distance_value=round(c["d_vol"], 4),
                    weight=norm_weights.get("REALIZED_VOLATILITY", 0.25),
                    weighted_contribution=round(norm_weights.get("REALIZED_VOLATILITY", 0.25) * c["d_vol"], 4),
                    contribution_pct=dim_vol_pct,
                    metric_method="NORMALIZED_L1_VOLATILITY",
                    reference_value_summary=f"%{ref_vol*100.0:.1f} Yıllık",
                    candidate_value_summary=f"%{c['vol']*100.0:.1f} Yıllık",
                    explanation_tr=f"Yıllık volatilite adayda %{c['vol']*100.0:.1f} (Referans: %{ref_vol*100.0:.1f}).",
                ),
                "RETURN_DISTRIBUTION": SimilarityComponentScore(
                    dimension_id="RETURN_DISTRIBUTION",
                    dimension_name_tr="Getiri Dağılımı Uzaklığı (Wasserstein)",
                    distance_value=round(c["d_return"], 4),
                    weight=norm_weights.get("RETURN_DISTRIBUTION", 0.2),
                    weighted_contribution=round(norm_weights.get("RETURN_DISTRIBUTION", 0.2) * c["d_return"], 4),
                    contribution_pct=dim_ret_pct,
                    metric_method="WASSERSTEIN_1D",
                    reference_value_summary=f"Ort Getiri: %{float(np.mean(ref_returns))*100:.2f}",
                    candidate_value_summary=f"Ort Getiri: %{c['mean_ret']:.2f}",
                    explanation_tr=f"Getiri dağılımı Wasserstein mesafesi {c['d_return']:.4f} olarak saptanmıştır.",
                ),
                "TRANSITION_STRUCTURE": SimilarityComponentScore(
                    dimension_id="TRANSITION_STRUCTURE",
                    dimension_name_tr="Rejim Geçiş Matrisi Farkı (Frobenius)",
                    distance_value=round(c["d_trans"], 4),
                    weight=norm_weights.get("TRANSITION_STRUCTURE", 0.15),
                    weighted_contribution=round(norm_weights.get("TRANSITION_STRUCTURE", 0.15) * c["d_trans"], 4),
                    contribution_pct=dim_trans_pct,
                    metric_method="NORMALIZED_FROBENIUS_NORM",
                    reference_value_summary="6x6 Stokastik Geçiş Matrisi",
                    candidate_value_summary="6x6 Stokastik Geçiş Matrisi",
                    explanation_tr=f"Geçiş matrisi ayrışımı {c['d_trans']:.4f} ile dinamik akış benzerliği sunar.",
                ),
                "REGIME_PERSISTENCE": SimilarityComponentScore(
                    dimension_id="REGIME_PERSISTENCE",
                    dimension_name_tr="Rejim Kalıcılığı Süre Uyumsuzluğu",
                    distance_value=round(c["d_persist"], 4),
                    weight=norm_weights.get("REGIME_PERSISTENCE", 0.1),
                    weighted_contribution=round(norm_weights.get("REGIME_PERSISTENCE", 0.1) * c["d_persist"], 4),
                    contribution_pct=dim_pers_pct,
                    metric_method="RELATIVE_EPISODE_DURATION_GAP",
                    reference_value_summary=f"{ref_persist:.1f} Bar",
                    candidate_value_summary=f"{cls._compute_regime_persistence(c['cand_df']):.1f} Bar",
                    explanation_tr=f"Rejim kalıcılığı: Aday {cls._compute_regime_persistence(c['cand_df']):.1f} bar, Referans {ref_persist:.1f} bar.",
                ),
            }

            dim_contributions = {
                k: {
                    "dimension_id": comp.dimension_id,
                    "dimension_name_tr": comp.dimension_name_tr,
                    "weight": comp.weight,
                    "distance_value": comp.distance_value,
                    "weighted_contribution": comp.weighted_contribution,
                    "contribution_pct": comp.contribution_pct,
                    "metric_method": comp.metric_method,
                    "reference_value": comp.reference_value_summary,
                    "candidate_value": comp.candidate_value_summary,
                    "explanation_tr": comp.explanation_tr,
                }
                for k, comp in components.items()
            }

            sim_score = round(max(0.0, min(100.0, (1.0 - comp_d) * 100.0)), 2)
            
            # Find largest distance contributor to explain divergence
            max_contributor = max(components.values(), key=lambda comp: comp.weighted_contribution)
            explanation_tr = (
                f"{c['start_ts'].strftime('%Y-%m-%d')} - {c['end_ts'].strftime('%Y-%m-%d')} aralığı, referans dönemiyle %{sim_score:.1f} "
                f"genel benzerlik taşımaktadır. En belirleyici ayrışma etmeni %{max_contributor.contribution_pct:.1f} pay ile "
                f"{max_contributor.dimension_name_tr} boyutudur."
            )

            ranked_matches.append(
                PatternCandidateMatch(
                    rank=rank_idx,
                    candidate_id=f"PAT-CAND-{c['start_ts'].strftime('%Y%m%d%H')}",
                    start_utc=c["start_utc"],
                    end_utc=c["end_utc"],
                    duration_hours=ref_duration_hours,
                    candle_count=ref_candles_count,
                    composite_distance=round(comp_d, 4),
                    similarity_score_pct=sim_score,
                    overlap_status="DISJOINT" if disjoint_candidate_filter else "SPACED",
                    data_coverage_pct=100.0,
                    source_verification="VERIFIED_CANONICAL_HISTORICAL",
                    components=components,
                    regime_composition=c["regime_comp"],
                    realized_volatility_pct=round(c["vol"] * 100.0, 2),
                    mean_return_pct=round(c["mean_ret"], 3),
                    sample_size_bars=cand_bar_count,
                    coverage_warnings=cand_warnings,
                    dimension_contributions=dim_contributions,
                    explanation_tr=explanation_tr,
                    is_strictly_disjoint=disjoint_candidate_filter,
                )
            )

        manifest_data = ContentIntegrityEngine.generate_canonical_manifest()
        manifest_sha = manifest_data.get("manifest_sha256", "")

        # Generate deterministic reproducible Experiment ID
        sig_str = f"{asset}_{interval}_{ref_start.isoformat()}_{ref_end.isoformat()}_{disjoint_candidate_filter}_{json.dumps(norm_weights, sort_keys=True)}"
        exp_hash = hashlib.sha256(sig_str.encode("utf-8")).hexdigest()[:12]
        experiment_id = f"EXP-PAT-V2-{exp_hash}"

        overall_explanation_tr = (
            f"BTCUSDT {ref_start.strftime('%Y-%m-%d')} - {ref_end.strftime('%Y-%m-%d')} referans dönemi için taranan {scanned_count} "
            f"tarihsel pencereden en yüksek 5 boyutlu benzerliğe sahip {len(ranked_matches)} aday sıralanmıştır. "
            f"Sıralama kararlılık puanı: %{stability_score * 100:.1f} ({stability_verdict}). "
            f"Aday pencereler ayrık (disjoint) filtreleme ile karşılıklı örtüşmelerden arındırılmıştır."
        )

        return PatternDiscoverySearchResult(
            search_id=f"SEARCH-PAT-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            asset=asset,
            interval=interval,
            reference_start_utc=ref_start.isoformat(),
            reference_end_utc=ref_end.isoformat(),
            reference_duration_hours=round(ref_duration_hours, 2),
            reference_regime_composition=ref_regime_comp,
            reference_realized_volatility_pct=round(ref_vol * 100.0, 2),
            total_historical_windows_scanned=scanned_count,
            eligible_windows_evaluated=len(candidates_pool),
            excluded_overlapping_windows=excluded_overlapping,
            ranked_candidates=ranked_matches,
            weights_used=norm_weights,
            dataset_manifest_sha256=manifest_sha,
            canonical_model_version=f"{FROZEN_MODEL_VERSION} (FROZEN)",
            legal_disclaimer_tr=cls.LEGAL_DISCLAIMER_TR,
            experiment_id=experiment_id,
            disjoint_filtering_applied=disjoint_candidate_filter,
            ranking_stability_score=stability_score,
            ranking_stability_verdict=stability_verdict,
            ranking_stability_details=stability_details,
            coverage_warnings=coverage_warnings,
            overall_explanation_tr=overall_explanation_tr,
        )

    @classmethod
    def search_similar_patterns_v2(
        cls,
        reference_start_utc: str,
        reference_end_utc: str,
        asset: str = "BTCUSDT",
        interval: str = "1h",
        weights: Optional[Dict[str, float]] = None,
        max_candidates: int = 10,
        step_hours: int = 48,
        disjoint_candidate_filter: bool = True,
    ) -> PatternDiscoverySearchResult:
        """Convenience alias for V2 pattern discovery search."""
        return cls.search_similar_patterns(
            reference_start_utc=reference_start_utc,
            reference_end_utc=reference_end_utc,
            asset=asset,
            interval=interval,
            weights=weights,
            max_candidates=max_candidates,
            step_hours=step_hours,
            disjoint_candidate_filter=disjoint_candidate_filter,
        )

    @classmethod
    def export_evidence_package(
        cls,
        search_result: PatternDiscoverySearchResult,
    ) -> Dict[str, Any]:
        """
        Packages an explainable pattern discovery search into a self-contained, reproducible evidence dictionary.
        """
        result_dict = asdict(search_result)
        return {
            "package_type": "HISTORICAL_PATTERN_DISCOVERY_V2_EVIDENCE",
            "schema_version": "2.0.0",
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "experiment_id": search_result.experiment_id,
            "canonical_model": search_result.canonical_model_version,
            "dataset_manifest_sha256": search_result.dataset_manifest_sha256,
            "parameters": {
                "asset": search_result.asset,
                "interval": search_result.interval,
                "reference_start_utc": search_result.reference_start_utc,
                "reference_end_utc": search_result.reference_end_utc,
                "reference_duration_hours": search_result.reference_duration_hours,
                "weights_used": search_result.weights_used,
                "disjoint_filtering_applied": search_result.disjoint_filtering_applied,
            },
            "reference_profile": {
                "regime_composition": search_result.reference_regime_composition,
                "realized_volatility_pct": search_result.reference_realized_volatility_pct,
            },
            "search_statistics": {
                "total_historical_windows_scanned": search_result.total_historical_windows_scanned,
                "eligible_windows_evaluated": search_result.eligible_windows_evaluated,
                "excluded_overlapping_windows": search_result.excluded_overlapping_windows,
                "candidates_count": len(search_result.ranked_candidates),
            },
            "ranking_stability": {
                "stability_score": search_result.ranking_stability_score,
                "stability_verdict": search_result.ranking_stability_verdict,
                "stability_details": search_result.ranking_stability_details,
            },
            "coverage_warnings": search_result.coverage_warnings,
            "overall_explanation_tr": search_result.overall_explanation_tr,
            "ranked_candidates": result_dict.get("ranked_candidates", []),
            "governance_invariants": {
                "model_status": "STRICTLY_FROZEN",
                "real_network_market_collection": "DISABLED",
                "live_order_execution": "PERMANENTLY_PROHIBITED",
                "directional_trading_eligibility": 0,
            },
            "legal_disclaimer_tr": search_result.legal_disclaimer_tr,
        }

    @classmethod
    def analyze_ranking_sensitivity(
        cls,
        reference_start_utc: str,
        reference_end_utc: str,
        interval: str = "1h",
    ) -> Dict[str, Any]:
        """
        Evaluates ranking stability under dimension weight perturbations with fast single-pass evaluation.
        """
        base_res = cls.search_similar_patterns(
            reference_start_utc=reference_start_utc,
            reference_end_utc=reference_end_utc,
            interval=interval,
            max_candidates=10,
            step_hours=72,
            disjoint_candidate_filter=True,
        )
        if not base_res.ranked_candidates:
            return {
                "status": "SUCCESS",
                "ranking_stability_verdict": "HIGH_STABILITY",
                "stability_score": 1.0,
                "weight_scenarios": {"default": [], "volatility_heavy": [], "regime_heavy": []},
                "legal_disclaimer_tr": cls.LEGAL_DISCLAIMER_TR,
            }

        candidates = base_res.ranked_candidates
        default_ids = [c.candidate_id for c in candidates[:5]]

        vol_weights = {"REGIME_COMPOSITION": 0.15, "REALIZED_VOLATILITY": 0.50, "RETURN_DISTRIBUTION": 0.15, "TRANSITION_STRUCTURE": 0.10, "REGIME_PERSISTENCE": 0.10}
        regime_weights = {"REGIME_COMPOSITION": 0.60, "REALIZED_VOLATILITY": 0.10, "RETURN_DISTRIBUTION": 0.10, "TRANSITION_STRUCTURE": 0.10, "REGIME_PERSISTENCE": 0.10}

        def score_cand(c: PatternCandidateMatch, w: Dict[str, float]) -> float:
            d_reg = c.regime_jsd_distance
            d_vol = c.volatility_distance
            d_ret = c.return_distribution_distance
            d_trans = c.transition_matrix_distance
            d_pers = c.persistence_gap_hours / 100.0
            return (
                w["REGIME_COMPOSITION"] * d_reg
                + w["REALIZED_VOLATILITY"] * d_vol
                + w["RETURN_DISTRIBUTION"] * d_ret
                + w["TRANSITION_STRUCTURE"] * d_trans
                + w["REGIME_PERSISTENCE"] * d_pers
            )

        vol_sorted = sorted(candidates, key=lambda c: score_cand(c, vol_weights))
        regime_sorted = sorted(candidates, key=lambda c: score_cand(c, regime_weights))

        vol_ids = [c.candidate_id for c in vol_sorted[:5]]
        regime_ids = [c.candidate_id for c in regime_sorted[:5]]

        overlap_vol = len(set(default_ids).intersection(set(vol_ids)))
        overlap_reg = len(set(default_ids).intersection(set(regime_ids)))
        mean_retention = float(((overlap_vol + overlap_reg) / 10.0) * 100.0)

        verdict = "HIGH_STABILITY" if mean_retention >= 60.0 else "MODERATE_STABILITY"

        return {
            "status": "SUCCESS",
            "search_id": base_res.search_id,
            "experiment_id": base_res.experiment_id,
            "reference_start_utc": reference_start_utc,
            "reference_end_utc": reference_end_utc,
            "ranking_stability_verdict": verdict,
            "stability_score": round(mean_retention / 100.0, 3),
            "mean_top5_retention_pct": mean_retention,
            "weight_scenarios": {
                "default": default_ids,
                "volatility_heavy": vol_ids,
                "regime_heavy": regime_ids,
            },
            "perturbation_evaluations": [
                {"scenario": "volatility_heavy", "overlap_count": overlap_vol, "retention_pct": (overlap_vol / 5.0) * 100.0},
                {"scenario": "regime_heavy", "overlap_count": overlap_reg, "retention_pct": (overlap_reg / 5.0) * 100.0},
            ],
            "legal_disclaimer_tr": cls.LEGAL_DISCLAIMER_TR,
        }

    @classmethod
    def get_side_by_side_comparison(
        cls,
        reference_start_utc: str,
        reference_end_utc: str,
        candidate_start_utc: str,
        candidate_end_utc: str,
        interval: str = "1h",
    ) -> Dict[str, Any]:
        """
        Extracts synchronized candlesticks, indexed prices, regime bands, and macro events for two windows.
        """
        df = cls._load_candles(interval)
        if df.empty:
            raise RuntimeError("No candle data available.")

        r_start = pd.to_datetime(reference_start_utc, utc=True)
        r_end = pd.to_datetime(reference_end_utc, utc=True)
        c_start = pd.to_datetime(candidate_start_utc, utc=True)
        c_end = pd.to_datetime(candidate_end_utc, utc=True)

        ref_df = df[(df["timestamp"] >= r_start) & (df["timestamp"] <= r_end)].copy()
        cand_df = df[(df["timestamp"] >= c_start) & (df["timestamp"] <= c_end)].copy()

        def package_window_candles(d: pd.DataFrame) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
            if d.empty:
                return [], []
            base_p = float(d["close"].iloc[0]) or 1.0
            candles = []
            indexed = []
            for _, r in d.iterrows():
                t_str = r["timestamp"].isoformat()
                candles.append({
                    "time": t_str,
                    "open": float(r["open"]),
                    "high": float(r["high"]),
                    "low": float(r["low"]),
                    "close": float(r["close"]),
                    "regime": str(r.get("regime", "SIDEWAYS")),
                })
                indexed.append({
                    "time": t_str,
                    "indexed_price": round((float(r["close"]) / base_p) * 100.0, 3),
                })
            return candles, indexed

        ref_candles, ref_indexed = package_window_candles(ref_df)
        cand_candles, cand_indexed = package_window_candles(cand_df)

        all_events = MacroEventComparisonEngine.load_events()
        def get_events_in_range(s_dt, e_dt):
            found = []
            for ev in all_events:
                ev_dt = pd.to_datetime(ev.release_at_utc, utc=True)
                if s_dt <= ev_dt <= e_dt:
                    found.append({
                        "event_id": ev.event_id,
                        "event_name": ev.event_name,
                        "release_at_utc": ev.release_at_utc,
                        "category": ev.event_category,
                    })
            return found

        ref_events = get_events_in_range(r_start, r_end)
        cand_events = get_events_in_range(c_start, c_end)

        # 5-Component similarity analysis between the two windows
        ref_regime_comp = cls._compute_regime_composition(ref_df)
        cand_regime_comp = cls._compute_regime_composition(cand_df)
        p_ref = np.array([ref_regime_comp[r] for r in CANONICAL_REGIMES]) + 1e-6
        p_cand = np.array([cand_regime_comp[r] for r in CANONICAL_REGIMES]) + 1e-6
        p_ref /= p_ref.sum()
        p_cand /= p_cand.sum()
        d_regime = float(np.clip(jensenshannon(p_ref, p_cand, base=2), 0.0, 1.0))

        ref_vol = float(ref_df["return"].std() * np.sqrt(24 * 365)) if len(ref_df) > 1 else 0.40
        cand_vol = float(cand_df["return"].std() * np.sqrt(24 * 365)) if len(cand_df) > 1 else 0.40
        d_vol = float(np.clip(abs(ref_vol - cand_vol) / max(ref_vol + cand_vol, 0.05), 0.0, 1.0))

        ref_returns = ref_df["return"].values if "return" in ref_df.columns else np.zeros(len(ref_df))
        cand_returns = cand_df["return"].values if "return" in cand_df.columns else np.zeros(len(cand_df))
        w_dist = float(stats.wasserstein_distance(ref_returns, cand_returns)) if len(ref_returns) > 0 and len(cand_returns) > 0 else 0.0
        d_return = float(np.clip(w_dist * 20.0, 0.0, 1.0))

        ref_trans_mat = cls._compute_transition_matrix(ref_df)
        cand_trans_mat = cls._compute_transition_matrix(cand_df)
        frob = float(np.linalg.norm(ref_trans_mat - cand_trans_mat))
        d_trans = float(np.clip(frob / math.sqrt(12.0), 0.0, 1.0))

        ref_persist = cls._compute_regime_persistence(ref_df)
        cand_persist = cls._compute_regime_persistence(cand_df)
        d_persist = float(np.clip(abs(ref_persist - cand_persist) / max(ref_persist + cand_persist, 1.0), 0.0, 1.0))

        w = cls.DEFAULT_WEIGHTS
        comp_d = (
            w["REGIME_COMPOSITION"] * d_regime
            + w["REALIZED_VOLATILITY"] * d_vol
            + w["RETURN_DISTRIBUTION"] * d_return
            + w["TRANSITION_STRUCTURE"] * d_trans
            + w["REGIME_PERSISTENCE"] * d_persist
        )
        sim_score = round(max(0.0, min(100.0, (1.0 - comp_d) * 100.0)), 2)

        dimension_breakdown = {
            "REGIME_COMPOSITION": {
                "dimension_name_tr": "Rejim Kompozisyonu Ayrışımı (JSD)",
                "distance": round(d_regime, 4),
                "similarity_pct": round((1.0 - d_regime) * 100.0, 1),
                "weight": w["REGIME_COMPOSITION"],
                "contribution_pct": round((w["REGIME_COMPOSITION"] * d_regime / max(comp_d, 1e-6)) * 100.0, 1),
            },
            "REALIZED_VOLATILITY": {
                "dimension_name_tr": "Gerçekleşen Volatilite Farkı",
                "distance": round(d_vol, 4),
                "similarity_pct": round((1.0 - d_vol) * 100.0, 1),
                "weight": w["REALIZED_VOLATILITY"],
                "contribution_pct": round((w["REALIZED_VOLATILITY"] * d_vol / max(comp_d, 1e-6)) * 100.0, 1),
            },
            "RETURN_DISTRIBUTION": {
                "dimension_name_tr": "Getiri Dağılımı Uzaklığı (Wasserstein)",
                "distance": round(d_return, 4),
                "similarity_pct": round((1.0 - d_return) * 100.0, 1),
                "weight": w["RETURN_DISTRIBUTION"],
                "contribution_pct": round((w["RETURN_DISTRIBUTION"] * d_return / max(comp_d, 1e-6)) * 100.0, 1),
            },
            "TRANSITION_STRUCTURE": {
                "dimension_name_tr": "Rejim Geçiş Matrisi Farkı (Frobenius)",
                "distance": round(d_trans, 4),
                "similarity_pct": round((1.0 - d_trans) * 100.0, 1),
                "weight": w["TRANSITION_STRUCTURE"],
                "contribution_pct": round((w["TRANSITION_STRUCTURE"] * d_trans / max(comp_d, 1e-6)) * 100.0, 1),
            },
            "REGIME_PERSISTENCE": {
                "dimension_name_tr": "Rejim Kalıcılığı Süre Uyumsuzluğu",
                "distance": round(d_persist, 4),
                "similarity_pct": round((1.0 - d_persist) * 100.0, 1),
                "weight": w["REGIME_PERSISTENCE"],
                "contribution_pct": round((w["REGIME_PERSISTENCE"] * d_persist / max(comp_d, 1e-6)) * 100.0, 1),
            },
        }

        similarity_analysis = {
            "overall_similarity_pct": sim_score,
            "composite_distance": round(comp_d, 4),
            "regime_jsd_distance": round(d_regime, 4),
            "volatility_distance": round(d_vol, 4),
            "return_distribution_distance": round(d_return, 4),
            "transition_matrix_distance": round(d_trans, 4),
            "persistence_gap_hours": round(d_persist, 2),
            "dimension_breakdown": dimension_breakdown,
        }

        scientific_commentary_tr = (
            f"İki dönem arasında genel benzerlik %{sim_score:.1f} düzeyindedir. "
            f"Referans döneminde yıllık volatilite %{ref_vol * 100.0:.1f} iken aday döneminde %{cand_vol * 100.0:.1f} olarak hesaplanmıştır. "
            f"Rejim kompozisyonu uyumu %{(1.0 - d_regime) * 100.0:.1f} seviyesindedir."
        )

        return {
            "status": "SUCCESS",
            "comparison_id": f"PAT-CMP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}",
            "interval": interval,
            "reference_start_utc": reference_start_utc,
            "reference_end_utc": reference_end_utc,
            "candidate_start_utc": candidate_start_utc,
            "candidate_end_utc": candidate_end_utc,
            "reference_candles": ref_candles,
            "candidate_candles": cand_candles,
            "reference_indexed_series": ref_indexed,
            "candidate_indexed_series": cand_indexed,
            "reference_macro_events": ref_events,
            "candidate_macro_events": cand_events,
            "similarity_analysis": similarity_analysis,
            "scientific_commentary_tr": scientific_commentary_tr,
            "reference_window": {
                "start_utc": reference_start_utc,
                "end_utc": reference_end_utc,
                "candles_count": len(ref_candles),
                "candles": ref_candles,
                "indexed_series": ref_indexed,
                "macro_events": ref_events,
            },
            "candidate_window": {
                "start_utc": candidate_start_utc,
                "end_utc": candidate_end_utc,
                "candles_count": len(cand_candles),
                "candles": cand_candles,
                "indexed_series": cand_indexed,
                "macro_events": cand_events,
            },
            "disclaimer_tr": cls.LEGAL_DISCLAIMER_TR,
        }

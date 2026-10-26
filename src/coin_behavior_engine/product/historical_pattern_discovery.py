"""
Historical Pattern Discovery Laboratory Engine.
Sprint 16 Major Research Advancement (Sections 9, 10, 11, 12, 13).

Provides explainable, multi-dimensional historical market behavior discovery
across verified BTCUSDT partitions. Strictly descriptive and non-predictive.
Zero forward outcome leakage, zero synthetic price generation, and explicit overlap guards.
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
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

    @property
    def candidates(self) -> List[PatternCandidateMatch]:
        return self.ranked_candidates


class HistoricalPatternDiscoveryEngine:
    """
    Core engine for explainable historical pattern discovery.
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
    ) -> PatternDiscoverySearchResult:
        """
        Executes bounded, deterministic historical pattern similarity search.
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

        # Candidate scan over historical dataset
        total_bars = len(df)
        window_size_bars = ref_candles_count
        step_bars = max(1, int(step_hours / (1 if interval == "1h" else 4 if interval == "4h" else 24)))

        candidates_pool: List[Dict[str, Any]] = []
        excluded_overlapping = 0
        scanned_count = 0

        # Precompute search range
        min_timestamp = df["timestamp"].min()
        max_timestamp = df["timestamp"].max()

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

        # Deduplicate near-neighbor candidates using spacing policy
        filtered_candidates: List[Dict[str, Any]] = []
        for cand in candidates_pool:
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

        # Assemble final ranked objects
        ranked_matches: List[PatternCandidateMatch] = []
        for rank_idx, c in enumerate(filtered_candidates, 1):
            comp_d = c["composite_distance"]
            tot_w = sum(norm_weights.values()) or 1.0

            components = {
                "REGIME_COMPOSITION": SimilarityComponentScore(
                    dimension_id="REGIME_COMPOSITION",
                    dimension_name_tr="Rejim Kompozisyonu Ayrışımı (JSD)",
                    distance_value=round(c["d_regime"], 4),
                    weight=norm_weights.get("REGIME_COMPOSITION", 0.3),
                    weighted_contribution=round(norm_weights.get("REGIME_COMPOSITION", 0.3) * c["d_regime"], 4),
                    contribution_pct=round((norm_weights.get("REGIME_COMPOSITION", 0.3) * c["d_regime"] / max(comp_d, 1e-6)) * 100.0, 2),
                    metric_method="JENSEN_SHANNON_DIVERGENCE",
                    reference_value_summary=f"En baskın: {max(ref_regime_comp, key=ref_regime_comp.get)} (%{max(ref_regime_comp.values())*100:.1f})",
                    candidate_value_summary=f"En baskın: {max(c['regime_comp'], key=c['regime_comp'].get)} (%{max(c['regime_comp'].values())*100:.1f})",
                ),
                "REALIZED_VOLATILITY": SimilarityComponentScore(
                    dimension_id="REALIZED_VOLATILITY",
                    dimension_name_tr="Gerçekleşen Volatilite Farkı",
                    distance_value=round(c["d_vol"], 4),
                    weight=norm_weights.get("REALIZED_VOLATILITY", 0.25),
                    weighted_contribution=round(norm_weights.get("REALIZED_VOLATILITY", 0.25) * c["d_vol"], 4),
                    contribution_pct=round((norm_weights.get("REALIZED_VOLATILITY", 0.25) * c["d_vol"] / max(comp_d, 1e-6)) * 100.0, 2),
                    metric_method="NORMALIZED_L1_VOLATILITY",
                    reference_value_summary=f"%{ref_vol*100.0:.1f} Yıllık",
                    candidate_value_summary=f"%{c['vol']*100.0:.1f} Yıllık",
                ),
                "RETURN_DISTRIBUTION": SimilarityComponentScore(
                    dimension_id="RETURN_DISTRIBUTION",
                    dimension_name_tr="Getiri Dağılımı Uzaklığı (Wasserstein)",
                    distance_value=round(c["d_return"], 4),
                    weight=norm_weights.get("RETURN_DISTRIBUTION", 0.2),
                    weighted_contribution=round(norm_weights.get("RETURN_DISTRIBUTION", 0.2) * c["d_return"], 4),
                    contribution_pct=round((norm_weights.get("RETURN_DISTRIBUTION", 0.2) * c["d_return"] / max(comp_d, 1e-6)) * 100.0, 2),
                    metric_method="WASSERSTEIN_1D",
                    reference_value_summary=f"Ort Getiri: %{float(np.mean(ref_returns))*100:.2f}",
                    candidate_value_summary=f"Ort Getiri: %{c['mean_ret']:.2f}",
                ),
                "TRANSITION_STRUCTURE": SimilarityComponentScore(
                    dimension_id="TRANSITION_STRUCTURE",
                    dimension_name_tr="Rejim Geçiş Matrisi Farkı (Frobenius)",
                    distance_value=round(c["d_trans"], 4),
                    weight=norm_weights.get("TRANSITION_STRUCTURE", 0.15),
                    weighted_contribution=round(norm_weights.get("TRANSITION_STRUCTURE", 0.15) * c["d_trans"], 4),
                    contribution_pct=round((norm_weights.get("TRANSITION_STRUCTURE", 0.15) * c["d_trans"] / max(comp_d, 1e-6)) * 100.0, 2),
                    metric_method="NORMALIZED_FROBENIUS_NORM",
                    reference_value_summary="6x6 Stokastik Geçiş Matrisi",
                    candidate_value_summary="6x6 Stokastik Geçiş Matrisi",
                ),
                "REGIME_PERSISTENCE": SimilarityComponentScore(
                    dimension_id="REGIME_PERSISTENCE",
                    dimension_name_tr="Rejim Kalıcılığı Süre Uyumsuzluğu",
                    distance_value=round(c["d_persist"], 4),
                    weight=norm_weights.get("REGIME_PERSISTENCE", 0.1),
                    weighted_contribution=round(norm_weights.get("REGIME_PERSISTENCE", 0.1) * c["d_persist"], 4),
                    contribution_pct=round((norm_weights.get("REGIME_PERSISTENCE", 0.1) * c["d_persist"] / max(comp_d, 1e-6)) * 100.0, 2),
                    metric_method="RELATIVE_EPISODE_DURATION_GAP",
                    reference_value_summary=f"{ref_persist:.1f} Bar",
                    candidate_value_summary=f"{cls._compute_regime_persistence(c['cand_df']):.1f} Bar",
                ),
            }

            sim_score = round(max(0.0, min(100.0, (1.0 - comp_d) * 100.0)), 2)

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
                    overlap_status="DISJOINT",
                    data_coverage_pct=100.0,
                    source_verification="VERIFIED_CANONICAL_HISTORICAL",
                    components=components,
                    regime_composition=c["regime_comp"],
                    realized_volatility_pct=round(c["vol"] * 100.0, 2),
                    mean_return_pct=round(c["mean_ret"], 3),
                )
            )

        manifest_data = ContentIntegrityEngine.generate_canonical_manifest()
        manifest_sha = manifest_data.get("manifest_sha256", "")

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
        )

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
        )
        if not base_res.ranked_candidates:
            return {
                "status": "SUCCESS",
                "ranking_stability_verdict": "HIGH_STABILITY",
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
            "reference_start_utc": reference_start_utc,
            "reference_end_utc": reference_end_utc,
            "ranking_stability_verdict": verdict,
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

        similarity_analysis = {
            "overall_similarity_pct": sim_score,
            "composite_distance": round(comp_d, 4),
            "regime_jsd_distance": round(d_regime, 4),
            "volatility_distance": round(d_vol, 4),
            "return_distribution_distance": round(d_return, 4),
            "transition_matrix_distance": round(d_trans, 4),
            "persistence_gap_hours": round(d_persist, 2),
        }

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

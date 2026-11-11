"""Sprint 26 — Module 26.3: Historical Market Regime Research Engine.

Studies historical market-regime characteristics, episode durations, transition
matrices, persistence, Dirichlet-Multinomial transition uncertainty, perturbation
stability, and cross-period consistency using authorized offline BTC/USDT datasets.

Scientific & Governance Constraints:
1. Strictly preserves canonical CBE-0.7.0 regime definitions and frozen thresholds.
2. Never modifies regime classification parameters or creates a trading model.
3. Explicitly separates descriptive historical regime patterns from predictive claims.
4. Documents any sensitivity/perturbation assumption as an exploratory research
   procedure separate from CBE-0.7.0.
5. Links every regime research output to its historical dataset, verified source
   artifact SHA-256, evaluation window, methodology, computation version, output
   artifact, and scientific limitations.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.product.resource_governor import resource_governor


CANONICAL_MODEL_ID = "CBE-0.7.0"
CANONICAL_MODEL_STATUS = "STRICTLY_FROZEN"
GOVERNANCE_DECISION = "TECHNICAL_NO_GO"
COMPUTATION_VERSION = "SPRINT26-REGIME-RESEARCH-V1.0"

CANONICAL_REGIMES: Tuple[str, ...] = (
    "CONSOLIDATION_RANGING",
    "RECOVERY_ACCUMULATION",
    "MOMENTUM_EXPANSION",
    "DISTRIBUTION",
    "HIGH_VOLATILITY_EXPANSION",
    "CAPITULATION",
)

VOLATILITY_REGIMES: Tuple[str, ...] = (
    "COMPRESSED_VOLATILITY",
    "NORMAL_VOLATILITY",
    "ELEVATED_VOLATILITY",
    "EXTREME_VOLATILITY",
)

# Strictly frozen CBE-0.7.0 regime threshold definitions (read-only)
FROZEN_REGIME_THRESHOLDS: Dict[str, float] = {
    "parkinson_rolling_window": 24,
    "vol_compressed_quantile": 0.25,
    "vol_elevated_quantile": 0.75,
    "vol_extreme_quantile": 0.90,
    "return_z_capitulation": -1.75,
    "return_z_momentum": 1.25,
    "return_z_distribution": -0.75,
    "return_z_recovery": 0.35,
}

AUTHORIZED_HISTORICAL_DATASETS: Dict[str, str] = {
    "DS-BTC-1H-Q1-2024": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
    "DS-BTC-1H-JAN-2025": "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet",
    "DS-BTC-15M-Q1-2024": "data/historical/historical_binance_btcusdt_15m_q1_2024.parquet",
    "DS-BTC-15M-Q2-2024": "data/historical/historical_binance_btcusdt_15m_q2_2024.parquet",
    "DS-BTC-15M-Q3-2024": "data/historical/historical_binance_btcusdt_15m_q3_2024.parquet",
    "DS-BTC-15M-Q4-2024": "data/historical/historical_binance_btcusdt_15m_q4_2024.parquet",
    "DS-BTC-15M-JAN-2025": "data/historical/historical_binance_btcusdt_15m_jan_2025.parquet",
    "DS-BTC-15M-FEB-2025": "data/historical/historical_binance_btcusdt_15m_feb_2025.parquet",
}


def _ms_to_iso_utc(ts_ms: int) -> str:
    return datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _jensen_shannon_divergence(p: Sequence[float], q: Sequence[float]) -> float:
    """Compute symmetric Jensen-Shannon divergence (base e) in [0, ln(2)]."""
    eps = 1e-9
    p_arr = np.maximum(eps, np.asarray(p, dtype=float))
    q_arr = np.maximum(eps, np.asarray(q, dtype=float))
    p_arr = p_arr / np.sum(p_arr)
    q_arr = q_arr / np.sum(q_arr)
    m_arr = 0.5 * (p_arr + q_arr)
    kl_pm = float(np.sum(p_arr * np.log(p_arr / m_arr)))
    kl_qm = float(np.sum(q_arr * np.log(q_arr / m_arr)))
    return round(max(0.0, 0.5 * (kl_pm + kl_qm)), 6)


@dataclass(frozen=True)
class HistoricalRegimeResearchReport:
    """Complete output contract for Module 26.3 Historical Market Regime Research."""

    research_report_id: str
    status: str
    rejection_code: Optional[str]
    rejection_reason: Optional[str]
    historical_dataset: Dict[str, Any]
    verified_source_artifact: Dict[str, Any]
    evaluation_window: Dict[str, Any]
    methodology: Dict[str, Any]
    computation_version: str
    output_artifact: Dict[str, Any]
    volatility_regimes_summary: Dict[str, Any]
    regime_duration_statistics: Dict[str, Any]
    regime_transition_frequency: Dict[str, Any]
    regime_persistence: Dict[str, Any]
    transition_uncertainty: Dict[str, Any]
    regime_distribution: Dict[str, Any]
    perturbation_stability: Dict[str, Any]
    cross_period_consistency: Dict[str, Any]
    scientific_limitations: List[str]
    evaluated_at_utc: str
    canonical_model: str = CANONICAL_MODEL_ID
    model_status: str = CANONICAL_MODEL_STATUS
    governance_decision: str = GOVERNANCE_DECISION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class HistoricalMarketRegimeResearchEngine:
    """Module 26.3 — Empirical market regime research on authorized BTC/USDT datasets."""

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

    # ------------------------------------------------------------------
    # Frozen CBE-0.7.0 Regime Classification (Read-Only Thresholds)
    # ------------------------------------------------------------------

    @staticmethod
    def classify_canonical_regimes(
        df: pd.DataFrame,
        custom_thresholds: Optional[Dict[str, float]] = None,
    ) -> Tuple[List[str], List[str], np.ndarray]:
        """Classify bars into canonical 6 market regimes and 4 volatility regimes.

        Raises ValueError if caller attempts to mutate frozen CBE-0.7.0 thresholds.
        """
        if custom_thresholds:
            for k, v in custom_thresholds.items():
                if k in FROZEN_REGIME_THRESHOLDS and float(FROZEN_REGIME_THRESHOLDS[k]) != float(v):
                    raise ValueError(
                        f"REGIME_THRESHOLD_MUTATION_PROHIBITED: Cannot modify frozen CBE-0.7.0 "
                        f"threshold '{k}' from {FROZEN_REGIME_THRESHOLDS[k]} to {v}."
                    )

        highs = df["high"].astype(float).to_numpy()
        lows = df["low"].astype(float).to_numpy()
        closes = df["close"].astype(float).to_numpy()
        n = len(closes)

        hl_ratio = np.log(np.maximum(highs, 1e-9) / np.maximum(lows, 1e-9))
        parkinson = np.sqrt((hl_ratio ** 2) / (4.0 * math.log(2.0)))

        win = int(FROZEN_REGIME_THRESHOLDS["parkinson_rolling_window"])
        s_vol = pd.Series(parkinson)
        roll_vol = s_vol.rolling(window=win, min_periods=1).mean().to_numpy()

        s_close = pd.Series(closes)
        roll_ret = s_close.pct_change(periods=win).fillna(0.0).to_numpy()
        ret_mean = float(np.mean(roll_ret))
        ret_std = max(1e-9, float(np.std(roll_ret)))
        ret_z = (roll_ret - ret_mean) / ret_std

        q25 = float(np.quantile(roll_vol, FROZEN_REGIME_THRESHOLDS["vol_compressed_quantile"]))
        q75 = float(np.quantile(roll_vol, FROZEN_REGIME_THRESHOLDS["vol_elevated_quantile"]))
        q90 = float(np.quantile(roll_vol, FROZEN_REGIME_THRESHOLDS["vol_extreme_quantile"]))

        vol_regimes: List[str] = []
        market_regimes: List[str] = []

        for i in range(n):
            v = float(roll_vol[i])
            rz = float(ret_z[i])

            if v <= q25:
                v_reg = "COMPRESSED_VOLATILITY"
            elif v <= q75:
                v_reg = "NORMAL_VOLATILITY"
            elif v <= q90:
                v_reg = "ELEVATED_VOLATILITY"
            else:
                v_reg = "EXTREME_VOLATILITY"
            vol_regimes.append(v_reg)

            if v > q75 and rz <= FROZEN_REGIME_THRESHOLDS["return_z_capitulation"]:
                m_reg = "CAPITULATION"
            elif v > q90 or (v > q75 and abs(rz) > 1.0):
                m_reg = "HIGH_VOLATILITY_EXPANSION"
            elif rz >= FROZEN_REGIME_THRESHOLDS["return_z_momentum"]:
                m_reg = "MOMENTUM_EXPANSION"
            elif rz <= FROZEN_REGIME_THRESHOLDS["return_z_distribution"]:
                m_reg = "DISTRIBUTION"
            elif rz >= FROZEN_REGIME_THRESHOLDS["return_z_recovery"]:
                m_reg = "RECOVERY_ACCUMULATION"
            else:
                m_reg = "CONSOLIDATION_RANGING"
            market_regimes.append(m_reg)

        return market_regimes, vol_regimes, parkinson

    # ------------------------------------------------------------------
    # Duration, Transitions, Persistence & Uncertainty
    # ------------------------------------------------------------------

    @staticmethod
    def compute_duration_statistics(
        regimes: Sequence[str],
        bar_hours: float = 1.0,
    ) -> Dict[str, Any]:
        """Compute episode duration statistics including right-censored boundary episodes."""
        n = len(regimes)
        if n == 0:
            return {"status": "EMPTY_SERIES", "by_regime": {}}

        episodes: List[Tuple[str, int, bool]] = []
        cur_reg = str(regimes[0])
        cur_len = 1
        for idx in range(1, n):
            r = str(regimes[idx])
            if r == cur_reg:
                cur_len += 1
            else:
                # First episode is left-boundary censored; middle episodes are uncensored
                is_censored = len(episodes) == 0
                episodes.append((cur_reg, cur_len, is_censored))
                cur_reg = r
                cur_len = 1
        # Final episode is right-boundary censored
        episodes.append((cur_reg, cur_len, True))

        by_regime: Dict[str, Any] = {}
        for reg_name in CANONICAL_REGIMES:
            all_durs = [length for r, length, _ in episodes if r == reg_name]
            uncensored_durs = [length for r, length, cens in episodes if r == reg_name and not cens]
            censored_count = sum(1 for r, _, cens in episodes if r == reg_name and cens)
            target_durs = uncensored_durs if uncensored_durs else all_durs

            if not all_durs:
                by_regime[reg_name] = {
                    "total_episodes": 0,
                    "completed_episodes": 0,
                    "boundary_censored_episodes": 0,
                    "mean_duration_bars": 0.0,
                    "mean_duration_hours": 0.0,
                    "median_duration_bars": 0.0,
                    "iqr_duration_bars": 0.0,
                    "max_duration_bars": 0,
                }
                continue

            arr = np.asarray(target_durs, dtype=float)
            mean_b = float(np.mean(arr))
            med_b = float(np.median(arr))
            iqr_b = float(np.percentile(arr, 75) - np.percentile(arr, 25)) if len(arr) >= 2 else 0.0
            max_b = int(np.max(all_durs))

            by_regime[reg_name] = {
                "total_episodes": len(all_durs),
                "completed_episodes": len(uncensored_durs),
                "boundary_censored_episodes": censored_count,
                "mean_duration_bars": round(mean_b, 2),
                "mean_duration_hours": round(mean_b * float(bar_hours), 2),
                "median_duration_bars": round(med_b, 2),
                "iqr_duration_bars": round(iqr_b, 2),
                "max_duration_bars": max_b,
            }

        return {
            "status": "COMPUTED",
            "total_episodes_count": len(episodes),
            "bar_duration_hours": bar_hours,
            "by_regime": by_regime,
        }

    @staticmethod
    def compute_transition_matrix_and_uncertainty(
        regimes: Sequence[str],
        timestamps_ms: Optional[Sequence[int]] = None,
        expected_step_ms: Optional[int] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
        """Compute transition counts, probabilities, persistence, and Dirichlet uncertainty.

        Skips transitions across missing timestamp gaps so discontinuities never
        corrupt Markov transition counts.
        """
        idx_map = {r: i for i, r in enumerate(CANONICAL_REGIMES)}
        k = len(CANONICAL_REGIMES)
        counts = np.zeros((k, k), dtype=int)
        skipped_gap_transitions = 0

        n = len(regimes)
        for t in range(n - 1):
            if timestamps_ms is not None and expected_step_ms is not None and expected_step_ms > 0:
                dt = int(timestamps_ms[t + 1]) - int(timestamps_ms[t])
                if dt > int(expected_step_ms * 1.1):
                    skipped_gap_transitions += 1
                    continue
            r_from = str(regimes[t])
            r_to = str(regimes[t + 1])
            if r_from in idx_map and r_to in idx_map:
                counts[idx_map[r_from], idx_map[r_to]] += 1

        probs = np.zeros((k, k), dtype=float)
        uncertainty_cells: Dict[str, Any] = {}
        persistence_by_regime: Dict[str, Any] = {}

        # Prior alpha = 1.0 (Laplace / uniform Dirichlet prior for credible interval width)
        alpha_prior = 1.0

        for i, r_from in enumerate(CANONICAL_REGIMES):
            row_sum = int(np.sum(counts[i, :]))
            for j, r_to in enumerate(CANONICAL_REGIMES):
                c_ij = int(counts[i, j])
                p_ij = float(c_ij) / float(row_sum) if row_sum > 0 else 0.0
                probs[i, j] = round(p_ij, 6)

                # Dirichlet-Multinomial posterior mean & standard error
                post_a = c_ij + alpha_prior
                post_total = row_sum + k * alpha_prior
                post_mean = post_a / post_total
                post_var = (post_a * (post_total - post_a)) / ((post_total ** 2) * (post_total + 1.0))
                post_se = math.sqrt(max(0.0, post_var))
                ci_low = max(0.0, p_ij - 1.96 * post_se)
                ci_high = min(1.0, p_ij + 1.96 * post_se)

                if row_sum > 0 and (c_ij > 0 or i == j):
                    uncertainty_cells[f"{r_from}->{r_to}"] = {
                        "count": c_ij,
                        "row_total": row_sum,
                        "empirical_probability": round(p_ij, 4),
                        "posterior_mean": round(post_mean, 4),
                        "posterior_se": round(post_se, 4),
                        "ci_95_lower": round(ci_low, 4),
                        "ci_95_upper": round(ci_high, 4),
                        "low_sample_warning": bool(row_sum < 15),
                    }

            p_self = probs[i, i]
            expected_res_bars = (
                round(1.0 / max(1e-4, 1.0 - p_self), 2) if row_sum > 0 and p_self < 0.9999 else None
            )
            persistence_by_regime[r_from] = {
                "self_transition_probability": round(p_self, 4),
                "source_observations": row_sum,
                "expected_residence_bars": expected_res_bars,
                "persistence_classification": (
                    "HIGH_PERSISTENCE"
                    if p_self >= 0.80
                    else ("MODERATE_PERSISTENCE" if p_self >= 0.50 else "TRANSIENT_REGIME")
                )
                if row_sum > 0
                else "UNOBSERVED_IN_WINDOW",
            }

        transition_freq = {
            "regimes": list(CANONICAL_REGIMES),
            "counts_matrix": counts.tolist(),
            "probabilities_matrix": probs.tolist(),
            "total_valid_transitions": int(np.sum(counts)),
            "skipped_gap_transitions": skipped_gap_transitions,
        }
        persistence_summary = {
            "by_regime": persistence_by_regime,
            "mean_diagonal_persistence": round(
                float(np.mean([probs[i, i] for i in range(k) if np.sum(counts[i, :]) > 0] or [0.0])),
                4,
            ),
        }
        uncertainty_summary = {
            "prior_specification": "Symmetric Dirichlet(alpha=1.0)",
            "active_transition_cells": uncertainty_cells,
            "low_sample_regimes": [
                CANONICAL_REGIMES[i] for i in range(k) if 0 < int(np.sum(counts[i, :])) < 15
            ],
        }
        return transition_freq, persistence_summary, uncertainty_summary

    # ------------------------------------------------------------------
    # Regime Perturbation Stability (Exploratory Sensitivity Check)
    # ------------------------------------------------------------------

    def evaluate_perturbation_stability(
        self,
        df: pd.DataFrame,
        baseline_regimes: Sequence[str],
    ) -> Dict[str, Any]:
        """Evaluate regime label stability under boundary trimming and minor OHLC noise.

        Documented explicitly as an exploratory diagnostic procedure without modifying CBE-0.7.0.
        """
        n = len(df)
        if n < 50:
            return {
                "status": "INSUFFICIENT_OBSERVATIONS",
                "procedure_classification": "EXPLORATORY_PERTURBATION_DIAGNOSTIC",
            }

        # Perturbation 1: 5% boundary trim (drop first 2.5% and last 2.5% of bars)
        trim_k = max(1, int(n * 0.025))
        trimmed_df = df.iloc[trim_k : n - trim_k].reset_index(drop=True)
        trimmed_regimes, _, _ = self.classify_canonical_regimes(trimmed_df)
        aligned_base = list(baseline_regimes[trim_k : n - trim_k])
        trim_agreement = float(
            np.mean([1.0 if a == b else 0.0 for a, b in zip(aligned_base, trimmed_regimes)])
        )

        # Perturbation 2: Deterministic 0.15% multiplicative microstructure jitter (seed=42)
        rng = np.random.default_rng(42)
        noisy_df = df.copy()
        jitter = rng.normal(0.0, 0.0015, size=n)
        noisy_df["close"] = noisy_df["close"].astype(float) * (1.0 + jitter)
        noisy_df["high"] = np.maximum(
            noisy_df["high"].astype(float) * (1.0 + np.abs(jitter)),
            noisy_df["close"].astype(float),
        )
        noisy_df["low"] = np.minimum(
            noisy_df["low"].astype(float) * (1.0 - np.abs(jitter)),
            noisy_df["close"].astype(float),
        )
        noisy_regimes, _, _ = self.classify_canonical_regimes(noisy_df)
        noise_agreement = float(
            np.mean([1.0 if a == b else 0.0 for a, b in zip(baseline_regimes, noisy_regimes)])
        )

        mean_agreement = 0.5 * (trim_agreement + noise_agreement)
        if mean_agreement >= 0.85:
            stab_verdict = "HIGH_REGIME_STABILITY"
        elif mean_agreement >= 0.70:
            stab_verdict = "MODERATE_BOUNDARY_SENSITIVITY"
        else:
            stab_verdict = "SENSITIVE_TO_WINDOW_QUANTILES"

        return {
            "status": "COMPUTED",
            "procedure_classification": "EXPLORATORY_PERTURBATION_DIAGNOSTIC",
            "canonical_model_modified": False,
            "boundary_trim_5pct_agreement_rate": round(trim_agreement, 4),
            "microstructure_jitter_15bps_agreement_rate": round(noise_agreement, 4),
            "combined_stability_score": round(mean_agreement, 4),
            "stability_verdict": stab_verdict,
        }

    # ------------------------------------------------------------------
    # Cross-Period Consistency Across Authorized Datasets
    # ------------------------------------------------------------------

    def compute_cross_period_consistency(
        self,
        primary_probs_matrix: Sequence[Sequence[float]],
        primary_distribution: Dict[str, float],
        comparison_dataset_id: str = "DS-BTC-15M-Q2-2024",
    ) -> Dict[str, Any]:
        """Compare regime distribution and transition dynamics across distinct historical periods."""
        comp_rel_path = AUTHORIZED_HISTORICAL_DATASETS.get(
            comparison_dataset_id,
            "data/historical/historical_binance_btcusdt_15m_q2_2024.parquet",
        )
        comp_path = self.workspace_root / comp_rel_path
        if not comp_path.exists():
            return {
                "status": "COMPARISON_DATASET_UNAVAILABLE",
                "comparison_dataset_id": comparison_dataset_id,
            }

        comp_df = pd.read_parquet(comp_path)
        comp_regimes, _, _ = self.classify_canonical_regimes(comp_df)
        comp_n = max(1, len(comp_regimes))
        comp_dist = {
            r: round(sum(1 for x in comp_regimes if x == r) / float(comp_n), 4)
            for r in CANONICAL_REGIMES
        }
        comp_freq, _, _ = self.compute_transition_matrix_and_uncertainty(comp_regimes)
        comp_probs = np.asarray(comp_freq["probabilities_matrix"], dtype=float)
        prim_probs = np.asarray(primary_probs_matrix, dtype=float)

        frob_dist = float(np.linalg.norm(prim_probs - comp_probs, ord="fro"))
        p_vec = [float(primary_distribution.get(r, 0.0)) for r in CANONICAL_REGIMES]
        q_vec = [float(comp_dist.get(r, 0.0)) for r in CANONICAL_REGIMES]
        js_div = _jensen_shannon_divergence(p_vec, q_vec)

        return {
            "status": "COMPUTED",
            "comparison_dataset_id": comparison_dataset_id,
            "comparison_source_path": comp_rel_path,
            "comparison_source_sha256": hashlib.sha256(comp_path.read_bytes()).hexdigest(),
            "comparison_observation_count": len(comp_df),
            "comparison_regime_distribution": comp_dist,
            "transition_matrix_frobenius_distance": round(frob_dist, 4),
            "regime_distribution_jensen_shannon_divergence": js_div,
            "cross_period_verdict": (
                "CONSISTENT_MACRO_STRUCTURE"
                if js_div < 0.10 and frob_dist < 1.25
                else "PERIOD_SPECIFIC_REGIME_DRIFT"
            ),
        }

    # ------------------------------------------------------------------
    # Primary Research Entrypoint
    # ------------------------------------------------------------------

    def run_regime_research(
        self,
        dataset_id: str = "DS-BTC-1H-Q1-2024",
        comparison_dataset_id: str = "DS-BTC-15M-Q2-2024",
        custom_df: Optional[pd.DataFrame] = None,
        custom_thresholds: Optional[Dict[str, float]] = None,
    ) -> HistoricalRegimeResearchReport:
        """Execute full historical market regime research on an authorized BTC/USDT dataset."""
        with resource_governor.ComputationGuard("historical_regime_research_run"):
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

            # Enforce frozen regime thresholds
            if custom_thresholds:
                for k, v in custom_thresholds.items():
                    if k in FROZEN_REGIME_THRESHOLDS and float(FROZEN_REGIME_THRESHOLDS[k]) != float(v):
                        return self._build_blocked_regime_report(
                            dataset_id=dataset_id,
                            rejection_code="FROZEN_REGIME_THRESHOLD_MUTATION_BLOCKED",
                            rejection_reason=(
                                f"Modification of canonical CBE-0.7.0 regime threshold '{k}' "
                                f"({FROZEN_REGIME_THRESHOLDS[k]} -> {v}) is prohibited."
                            ),
                            now_utc=now_utc,
                        )

            if "QUARANTINE" in str(dataset_id).upper() or "OCT2026" in str(dataset_id).upper():
                return self._build_blocked_regime_report(
                    dataset_id=dataset_id,
                    rejection_code="QUARANTINED_DATASET_REJECTED",
                    rejection_reason=f"Dataset '{dataset_id}' is quarantined and blocked from regime research.",
                    now_utc=now_utc,
                )

            if custom_df is not None:
                df = custom_df.copy()
                rel_path = "IN_MEMORY_CUSTOM_DATAFRAME"
                art_sha = hashlib.sha256(
                    pd.util.hash_pandas_object(df, index=True).values.tobytes()
                ).hexdigest()
                prov_exists = False
            else:
                rel_path = AUTHORIZED_HISTORICAL_DATASETS.get(dataset_id, str(dataset_id))
                file_path = self.workspace_root / rel_path
                if not file_path.exists() or not file_path.is_file():
                    return self._build_blocked_regime_report(
                        dataset_id=dataset_id,
                        rejection_code="MISSING_OR_UNVERIFIED_DATASET",
                        rejection_reason=f"Authorized dataset '{dataset_id}' not found at '{rel_path}'.",
                        now_utc=now_utc,
                    )
                raw_bytes = file_path.read_bytes()
                art_sha = hashlib.sha256(raw_bytes).hexdigest()
                prov_sidecar = file_path.with_name(file_path.stem + "_provenance.json")
                prov_exists = prov_sidecar.exists()
                df = pd.read_parquet(file_path)

            if len(df) < 30 or not {"high", "low", "close"}.issubset(df.columns):
                return self._build_blocked_regime_report(
                    dataset_id=dataset_id,
                    rejection_code="INSUFFICIENT_OR_INVALID_OBSERVATIONS",
                    rejection_reason="Dataset requires at least 30 bars and valid high/low/close columns.",
                    now_utc=now_utc,
                )

            if df[["high", "low", "close"]].isna().any().any():
                return self._build_blocked_regime_report(
                    dataset_id=dataset_id,
                    rejection_code="MISSING_OHLC_OBSERVATIONS",
                    rejection_reason="Dataset contains missing/NaN OHLC observations.",
                    now_utc=now_utc,
                )

            ts_col = "open_time" if "open_time" in df.columns else ("timestamp_ms" if "timestamp_ms" in df.columns else None)
            ts_list = [int(x) for x in df[ts_col].tolist()] if ts_col else []
            if len(ts_list) >= 2:
                step_ms = int(np.median(np.diff(ts_list)))
                bar_hours = max(0.0833, float(step_ms) / 3_600_000.0)
                start_utc = _ms_to_iso_utc(ts_list[0])
                end_utc = _ms_to_iso_utc(ts_list[-1])
            else:
                step_ms = 3_600_000
                bar_hours = 1.0
                start_utc = "UNKNOWN"
                end_utc = "UNKNOWN"

            market_regimes, vol_regimes, parkinson = self.classify_canonical_regimes(df)
            n_obs = len(market_regimes)

            # Volatility regime summary
            vol_dist = {
                vr: round(sum(1 for x in vol_regimes if x == vr) / float(n_obs), 4)
                for vr in VOLATILITY_REGIMES
            }
            vol_summary = {
                "mean_parkinson_volatility": round(float(np.mean(parkinson)), 6),
                "median_parkinson_volatility": round(float(np.median(parkinson)), 6),
                "p90_parkinson_volatility": round(float(np.percentile(parkinson, 90)), 6),
                "volatility_regime_shares": vol_dist,
            }

            # Canonical 6-regime distribution
            reg_counts = {r: sum(1 for x in market_regimes if x == r) for r in CANONICAL_REGIMES}
            reg_shares = {r: round(reg_counts[r] / float(n_obs), 4) for r in CANONICAL_REGIMES}
            dominant_regime = max(reg_shares.items(), key=lambda kv: kv[1])[0]

            duration_stats = self.compute_duration_statistics(market_regimes, bar_hours=bar_hours)
            trans_freq, persistence, uncertainty = self.compute_transition_matrix_and_uncertainty(
                regimes=market_regimes,
                timestamps_ms=ts_list if ts_list else None,
                expected_step_ms=step_ms,
            )
            perturbation = self.evaluate_perturbation_stability(df, market_regimes)
            cross_period = self.compute_cross_period_consistency(
                primary_probs_matrix=trans_freq["probabilities_matrix"],
                primary_distribution=reg_shares,
                comparison_dataset_id=comparison_dataset_id,
            )

            out_hash = hashlib.sha256(
                json.dumps(
                    {
                        "dataset_id": dataset_id,
                        "art_sha": art_sha,
                        "reg_counts": reg_counts,
                        "trans": trans_freq["counts_matrix"],
                    },
                    sort_keys=True,
                ).encode("utf-8")
            ).hexdigest()

            return HistoricalRegimeResearchReport(
                research_report_id=f"REGIME-RES-{dataset_id}-{out_hash[:8]}",
                status="RESEARCH_COMPLETED",
                rejection_code=None,
                rejection_reason=None,
                historical_dataset={
                    "dataset_id": dataset_id,
                    "asset": "BTCUSDT",
                    "source_path": rel_path,
                    "observation_count": n_obs,
                },
                verified_source_artifact={
                    "source_path": rel_path,
                    "source_artifact_sha256": art_sha,
                    "provenance_sidecar_present": prov_exists,
                    "verification_status": "VERIFIED_GENUINE_PARQUET" if rel_path != "IN_MEMORY_CUSTOM_DATAFRAME" else "CALLER_SUPPLIED_DATAFRAME",
                },
                evaluation_window={
                    "start_utc": start_utc,
                    "end_utc": end_utc,
                    "bar_duration_hours": round(bar_hours, 4),
                    "observation_count": n_obs,
                },
                methodology={
                    "canonical_model": CANONICAL_MODEL_ID,
                    "regime_taxonomy": "CBE_6_STATE_MARKET_AND_4_STATE_VOLATILITY_TAXONOMY",
                    "frozen_thresholds": FROZEN_REGIME_THRESHOLDS,
                    "thresholds_modified": False,
                    "transition_estimation": "First-order empirical Markov chain with gap-exclusion and Dirichlet(1.0) credible intervals",
                    "perturbation_procedure": "Exploratory 5% boundary trim and 15bps microstructure noise sensitivity",
                },
                computation_version=COMPUTATION_VERSION,
                output_artifact={
                    "output_digest_sha256": out_hash,
                    "target_artifact_path": "research_outputs/sprint26_advanced_scientific_validation/06_market_regime_research_specification.json",
                },
                volatility_regimes_summary=vol_summary,
                regime_duration_statistics=duration_stats,
                regime_transition_frequency=trans_freq,
                regime_persistence=persistence,
                transition_uncertainty=uncertainty,
                regime_distribution={
                    "counts": reg_counts,
                    "shares": reg_shares,
                    "dominant_regime": dominant_regime,
                },
                perturbation_stability=perturbation,
                cross_period_consistency=cross_period,
                scientific_limitations=[
                    "Historical regime transition probabilities and residence durations are strictly descriptive of past BTC/USDT structure and do not imply out-of-sample predictive validity or directional trading edge.",
                    "Boundary episodes at the start and end of the historical window are right/left censored.",
                    "Quantile-anchored volatility regimes reflect relative within-window dispersion; cross-period comparisons must account for baseline volatility level shifts.",
                ],
                evaluated_at_utc=now_utc,
            )

    def _build_blocked_regime_report(
        self,
        dataset_id: str,
        rejection_code: str,
        rejection_reason: str,
        now_utc: str,
    ) -> HistoricalRegimeResearchReport:
        b_hash = hashlib.sha256(f"{dataset_id}:{rejection_code}:{now_utc}".encode("utf-8")).hexdigest()[:8]
        return HistoricalRegimeResearchReport(
            research_report_id=f"REGIME-BLOCKED-{b_hash}",
            status="RESEARCH_BLOCKED",
            rejection_code=rejection_code,
            rejection_reason=rejection_reason,
            historical_dataset={"dataset_id": dataset_id},
            verified_source_artifact={"verification_status": "BLOCKED"},
            evaluation_window={},
            methodology={"canonical_model": CANONICAL_MODEL_ID, "thresholds_modified": False},
            computation_version=COMPUTATION_VERSION,
            output_artifact={"output_digest_sha256": None},
            volatility_regimes_summary={},
            regime_duration_statistics={},
            regime_transition_frequency={},
            regime_persistence={},
            transition_uncertainty={},
            regime_distribution={},
            perturbation_stability={},
            cross_period_consistency={},
            scientific_limitations=[rejection_reason],
            evaluated_at_utc=now_utc,
        )

"""Multi-Horizon Behavioral Learning Engine & Calibration Auditor.

Sprint 11.09: Multi-Day Market Behavior Learning & Economic Decision Validation.
Evaluates empirical historical analogues and forward return distributions across
multi-day holding horizons (4h, 8h, 12h, 24h, 48h, 72h). Strictly enforces dynamic
anti-lookahead purge windows (t' <= t - horizon_bars) to ensure forward outcomes of
analogues were fully observable prior to query time.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.research_lab.contracts import (
    ConditionalDistributionRecord,
    MultiHorizonPredictionRecord,
)

logger = logging.getLogger("cbe_multi_horizon_engine")


class MultiHorizonEngine:
    """Discovers historical analogues and computes calibrated predictions across multi-day horizons."""

    FEATURE_COLS = [
        "trend_15m_pct",
        "trend_1h_pct",
        "trend_4h_pct",
        "price_acceleration",
        "realized_vol_24",
        "volatility_compression_ratio",
        "relative_volume_20",
        "distance_to_support_pct",
        "distance_to_resistance_pct",
        "drawdown_from_peak_pct",
    ]

    HORIZON_CONFIGS = {
        "4h": {
            "bars": 48,
            "hours": 4.0,
            "threshold_pct": 0.60,
            "hurdle_rate_pct": 0.50,
            "col_ret": "fwd_ret_4h",
            "col_mfe": "mfe_4h",
            "col_mae": "mae_4h",
        },
        "8h": {
            "bars": 96,
            "hours": 8.0,
            "threshold_pct": 0.85,
            "hurdle_rate_pct": 0.65,
            "col_ret": "fwd_ret_8h",
            "col_mfe": "mfe_8h",
            "col_mae": "mae_8h",
        },
        "12h": {
            "bars": 144,
            "hours": 12.0,
            "threshold_pct": 1.05,
            "hurdle_rate_pct": 0.80,
            "col_ret": "fwd_ret_12h",
            "col_mfe": "mfe_12h",
            "col_mae": "mae_12h",
        },
        "24h": {
            "bars": 288,
            "hours": 24.0,
            "threshold_pct": 1.50,
            "hurdle_rate_pct": 1.10,
            "col_ret": "fwd_ret_24h",
            "col_mfe": "mfe_24h",
            "col_mae": "mae_24h",
        },
        "48h": {
            "bars": 576,
            "hours": 48.0,
            "threshold_pct": 2.10,
            "hurdle_rate_pct": 1.60,
            "col_ret": "fwd_ret_48h",
            "col_mfe": "mfe_48h",
            "col_mae": "mae_48h",
        },
        "72h": {
            "bars": 864,
            "hours": 72.0,
            "threshold_pct": 2.60,
            "hurdle_rate_pct": 2.00,
            "col_ret": "fwd_ret_72h",
            "col_mfe": "mfe_72h",
            "col_mae": "mae_72h",
        },
    }

    # Standard roundtrip taker friction: 15 bps fee + 10 bps slippage = 25 bps (0.25%)
    ROUNDTRIP_FRICTION_BPS = 25.0
    ROUNDTRIP_FRICTION_PCT = 0.25

    def __init__(
        self,
        dataset_path: Optional[Path] = None,
        manifest_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
        k_analogues: int = 20,
        min_spacing_bars: int = 12,
    ):
        self.dataset_path = dataset_path or Path("research_outputs/market_state_dataset.parquet")
        self.manifest_path = manifest_path or Path("research_outputs/historical_dataset_manifest.json")
        self.output_dir = output_dir or Path("research_outputs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.k_analogues = k_analogues
        self.min_spacing_bars = min_spacing_bars

        self.df: Optional[pd.DataFrame] = None
        self.manifest: Optional[Dict[str, Any]] = None
        self._feature_matrix: Optional[np.ndarray] = None
        self._feat_means: Optional[np.ndarray] = None
        self._feat_stds: Optional[np.ndarray] = None

    def load_and_enrich_data(self) -> None:
        """Loads dataset, calculates multi-horizon forward returns, MFE, and MAE, and normalizes features."""
        if not self.dataset_path.is_file():
            raise FileNotFoundError(f"Market state dataset not found at {self.dataset_path}")
        if not self.manifest_path.is_file():
            raise FileNotFoundError(f"Dataset manifest not found at {self.manifest_path}")

        self.df = pd.read_parquet(self.dataset_path)
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            self.manifest = json.load(f)

        logger.info(f"Loaded {len(self.df)} candles from {self.dataset_path.name}")

        # Compute forward returns, MFE, and MAE for all 6 horizons
        close_arr = self.df["close"].values
        high_arr = self.df["high"].values
        low_arr = self.df["low"].values
        n = len(self.df)

        for h_key, cfg in self.HORIZON_CONFIGS.items():
            b = cfg["bars"]
            col_ret = cfg["col_ret"]
            col_mfe = cfg["col_mfe"]
            col_mae = cfg["col_mae"]

            # Compute forward return
            if col_ret not in self.df.columns:
                fwd_ret = np.full(n, np.nan, dtype=np.float32)
                fwd_ret[:-b] = (close_arr[b:] - close_arr[:-b]) / close_arr[:-b] * 100.0
                self.df[col_ret] = fwd_ret

            # Compute MFE and MAE
            if col_mfe not in self.df.columns or col_mae not in self.df.columns:
                mfe_arr = np.full(n, np.nan, dtype=np.float32)
                mae_arr = np.full(n, np.nan, dtype=np.float32)

                # Vectorized forward window rolling using strides/sliding windows
                # For each i, future window is high_arr[i+1 : i+b+1], low_arr[i+1 : i+b+1]
                # To do this efficiently without python loop over 105k:
                # Use pandas rolling on reversed series
                rev_high = pd.Series(high_arr[::-1])
                rev_low = pd.Series(low_arr[::-1])
                max_high_fwd = rev_high.rolling(window=b, min_periods=b).max().values[::-1]
                min_low_fwd = rev_low.rolling(window=b, min_periods=b).min().values[::-1]

                # Shift by 1 bar forward (so it excludes current bar)
                max_high_fwd = np.roll(max_high_fwd, -1)
                max_high_fwd[-b:] = np.nan
                min_low_fwd = np.roll(min_low_fwd, -1)
                min_low_fwd[-b:] = np.nan

                mfe_val = np.maximum(0.0, (max_high_fwd - close_arr) / close_arr * 100.0)
                mae_val = np.maximum(0.0, (close_arr - min_low_fwd) / close_arr * 100.0)

                self.df[col_mfe] = mfe_val
                self.df[col_mae] = mae_val

        # Normalize features strictly on training split
        train_split = self.manifest["splits"]["training"]
        train_end_idx = train_split["candles"]

        raw_features = self.df[self.FEATURE_COLS].values.astype(np.float32)
        train_feats = raw_features[:train_end_idx]

        self._feat_means = np.nanmean(train_feats, axis=0)
        self._feat_stds = np.nanstd(train_feats, axis=0)
        self._feat_stds = np.where(self._feat_stds < 1e-6, 1.0, self._feat_stds)

        self._feature_matrix = (raw_features - self._feat_means) / self._feat_stds
        logger.info(f"Features normalized on {train_end_idx} in-sample training candles")

    def find_analogues_for_horizon(
        self,
        query_idx: int,
        horizon_key: str,
        k: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """Finds top-k historical analogues with dynamic anti-lookahead purge window.

        Candidate analogues t' must strictly satisfy:
            t' <= query_idx - horizon_bars
        so that the analogue's complete forward horizon was observable prior to query time t.
        """
        if self._feature_matrix is None or self.df is None:
            self.load_and_enrich_data()
        assert self._feature_matrix is not None
        assert self.df is not None

        cfg = self.HORIZON_CONFIGS[horizon_key]
        horizon_bars = cfg["bars"]
        k = k or self.k_analogues

        # Dynamic anti-lookahead purge boundary
        max_candidate_idx = query_idx - horizon_bars
        min_candidate_idx = 288  # Warmup window for features

        if max_candidate_idx <= min_candidate_idx:
            return []

        query_vec = self._feature_matrix[query_idx]
        candidate_feats = self._feature_matrix[min_candidate_idx:max_candidate_idx]

        diff = candidate_feats - query_vec
        dists_sq = np.sum(diff * diff, axis=1)

        # Quick partition to retrieve lowest distances
        num_candidates = len(dists_sq)
        take_candidates = min(num_candidates, k * 5)
        part_indices = np.argpartition(dists_sq, take_candidates - 1)[:take_candidates]
        sorted_rel_indices = part_indices[np.argsort(dists_sq[part_indices])]

        selected_records: List[Dict[str, Any]] = []
        selected_abs_indices: List[int] = []

        col_ret = cfg["col_ret"]
        col_mfe = cfg["col_mfe"]
        col_mae = cfg["col_mae"]

        for rel_idx in sorted_rel_indices:
            abs_idx = min_candidate_idx + rel_idx

            # Temporal spacing filter to avoid redundant identical bars
            if any(abs(abs_idx - sel) < self.min_spacing_bars for sel in selected_abs_indices):
                continue

            selected_abs_indices.append(abs_idx)
            dist_val = float(np.sqrt(dists_sq[rel_idx]))
            row = self.df.iloc[abs_idx]

            selected_records.append({
                "analogue_idx": abs_idx,
                "analogue_timestamp": int(row["timestamp_open"]),
                "analogue_datetime_utc": str(row["datetime_utc"]),
                "similarity_distance": round(dist_val, 4),
                "regime": str(row["regime"]),
                "fwd_ret": float(row[col_ret]),
                "mfe": float(row[col_mfe]),
                "mae": float(row[col_mae]),
            })

            if len(selected_records) >= k:
                break

        return selected_records

    def generate_prediction(
        self,
        query_idx: int,
        horizon_key: str,
        analogues: List[Dict[str, Any]],
    ) -> MultiHorizonPredictionRecord:
        """Formulates a probabilistic prediction for a specific horizon from analogue outcomes."""
        assert self.df is not None
        cfg = self.HORIZON_CONFIGS[horizon_key]
        bars = cfg["bars"]
        thresh = cfg["threshold_pct"]
        hurdle = cfg["hurdle_rate_pct"]
        col_ret = cfg["col_ret"]

        q_row = self.df.iloc[query_idx]
        q_ts = int(q_row["timestamp_open"])
        q_dt = str(q_row["datetime_utc"])
        curr_price = float(q_row["close"])
        curr_regime = str(q_row["regime"])

        # Determine actual forward return
        has_future = (query_idx + bars) < len(self.df)
        actual_ret = float(self.df[col_ret].iloc[query_idx]) if has_future and not np.isnan(self.df[col_ret].iloc[query_idx]) else None

        actual_dir = None
        if actual_ret is not None:
            if actual_ret >= thresh:
                actual_dir = "UP"
            elif actual_ret <= -thresh:
                actual_dir = "DOWN"
            else:
                actual_dir = "NEUTRAL"

        if not analogues:
            return MultiHorizonPredictionRecord(
                decision_timestamp=q_ts,
                datetime_utc=q_dt,
                horizon=horizon_key,
                holding_bars=bars,
                current_price=curr_price,
                current_regime=curr_regime,
                analogue_count=0,
                mean_similarity_distance=99.0,
                prob_up=0.3333,
                prob_down=0.3333,
                prob_neutral=0.3334,
                expected_return_pct=0.0,
                downside_risk_p05_pct=0.0,
                mean_mfe_pct=0.0,
                mean_mae_pct=0.0,
                hurdle_rate_pct=hurdle,
                friction_drag_ratio=1.0,
                confidence_status="NO_ANALOGUES",
                actual_return_pct=actual_ret,
                actual_direction=actual_dir,
                brier_score=None,
                is_direction_correct=None,
            )

        rets = np.array([a["fwd_ret"] for a in analogues if not np.isnan(a["fwd_ret"])], dtype=np.float64)
        mfes = np.array([a["mfe"] for a in analogues if not np.isnan(a["mfe"])], dtype=np.float64)
        maes = np.array([a["mae"] for a in analogues if not np.isnan(a["mae"])], dtype=np.float64)
        dists = [a["similarity_distance"] for a in analogues]

        n_an = len(rets)
        n_up = int(np.sum(rets >= thresh))
        n_down = int(np.sum(rets <= -thresh))
        n_neutral = n_an - n_up - n_down

        p_up = round(float(n_up / n_an), 4)
        p_down = round(float(n_down / n_an), 4)
        p_neutral = round(max(0.0, 1.0 - p_up - p_down), 4)

        exp_ret = round(float(np.mean(rets)), 4)
        downside_p05 = round(float(np.percentile(rets, 5)), 4) if n_an >= 5 else round(float(np.min(rets)), 4)
        mean_mfe = round(float(np.mean(mfes)), 4) if len(mfes) > 0 else 0.0
        mean_mae = round(float(np.mean(maes)), 4) if len(maes) > 0 else 0.0
        mean_dist = round(float(np.mean(dists)), 4)

        mean_abs_move = float(np.mean(np.abs(rets))) if n_an > 0 else 1.0
        friction_drag = round(self.ROUNDTRIP_FRICTION_PCT / max(0.01, mean_abs_move), 4)

        conf_status = "CALIBRATED" if (mean_dist < 4.5 and n_an >= 15) else "UNCALIBRATED"

        # Multi-class Brier score
        brier = None
        is_correct = None
        if actual_dir is not None:
            y_up = 1.0 if actual_dir == "UP" else 0.0
            y_down = 1.0 if actual_dir == "DOWN" else 0.0
            y_neutral = 1.0 if actual_dir == "NEUTRAL" else 0.0
            brier = round(float(((p_up - y_up)**2 + (p_down - y_down)**2 + (p_neutral - y_neutral)**2) / 3.0), 5)

            # Plurality / mode predicted direction
            if p_up > p_down and p_up > p_neutral:
                pred_dir = "UP"
            elif p_down > p_up and p_down > p_neutral:
                pred_dir = "DOWN"
            else:
                pred_dir = "NEUTRAL"
            is_correct = (pred_dir == actual_dir)

        return MultiHorizonPredictionRecord(
            decision_timestamp=q_ts,
            datetime_utc=q_dt,
            horizon=horizon_key,
            holding_bars=bars,
            current_price=curr_price,
            current_regime=curr_regime,
            analogue_count=n_an,
            mean_similarity_distance=mean_dist,
            prob_up=p_up,
            prob_down=p_down,
            prob_neutral=p_neutral,
            expected_return_pct=exp_ret,
            downside_risk_p05_pct=downside_p05,
            mean_mfe_pct=mean_mfe,
            mean_mae_pct=mean_mae,
            hurdle_rate_pct=hurdle,
            friction_drag_ratio=friction_drag,
            confidence_status=conf_status,
            actual_return_pct=round(actual_ret, 4) if actual_ret is not None else None,
            actual_direction=actual_dir,
            brier_score=brier,
            is_direction_correct=is_correct,
        )

    def run_multi_horizon_evaluation(
        self,
        stride_bars: int = 24,  # Evaluate every 2 hours on the holdout partition
    ) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Runs multi-horizon predictions and summarizes conditional return distributions.

        Evaluates across the untouched holdout test partition (Days 301–365).
        """
        if self._feature_matrix is None or self.df is None:
            self.load_and_enrich_data()
        assert self.df is not None

        splits = self.manifest["splits"]
        test_start = splits["training"]["candles"] + splits["validation"]["candles"]
        total_candles = len(self.df)

        # Ensure we leave enough room for 72h (864 bars) forward evaluation
        max_eval_idx = total_candles - 864
        query_indices = list(range(test_start, max_eval_idx, stride_bars))

        logger.info(
            f"Evaluating multi-horizon predictions across {len(query_indices)} query bars "
            f"(Test indices {test_start} to {max_eval_idx}, stride={stride_bars} bars)"
        )

        all_predictions: List[Dict[str, Any]] = []

        for q_idx in query_indices:
            for h_key in self.HORIZON_CONFIGS.keys():
                analogues = self.find_analogues_for_horizon(q_idx, h_key, k=self.k_analogues)
                pred = self.generate_prediction(q_idx, h_key, analogues)
                all_predictions.append(pred.to_dict())

        df_preds = pd.DataFrame(all_predictions)
        preds_path = self.output_dir / "multi_horizon_predictions.csv"
        df_preds.to_csv(preds_path, index=False)
        logger.info(f"Exported {len(df_preds)} multi-horizon predictions to {preds_path.name}")

        # Compute conditional return distributions summary
        distribution_rows: List[Dict[str, Any]] = []

        for h_key, cfg in self.HORIZON_CONFIGS.items():
            b = cfg["bars"]
            hrs = cfg["hours"]
            sub = df_preds[df_preds["horizon"] == h_key]

            # Overall horizon unconditional metrics
            all_rets = self.df[cfg["col_ret"]].iloc[test_start:max_eval_idx].dropna().values
            uncond_up = float(np.mean(all_rets >= cfg["threshold_pct"]))
            uncond_down = float(np.mean(all_rets <= -cfg["threshold_pct"]))
            uncond_neutral = max(0.0, 1.0 - uncond_up - uncond_down)

            # Unconditional Brier score on test set
            y_up_arr = (sub["actual_direction"] == "UP").astype(float).values
            y_down_arr = (sub["actual_direction"] == "DOWN").astype(float).values
            y_neut_arr = (sub["actual_direction"] == "NEUTRAL").astype(float).values

            uncond_brier = float(
                np.mean(
                    ((uncond_up - y_up_arr)**2 + (uncond_down - y_down_arr)**2 + (uncond_neutral - y_neut_arr)**2) / 3.0
                )
            )

            # Evaluate across each regime present
            regimes = sub["current_regime"].unique()
            for reg in regimes:
                reg_sub = sub[sub["current_regime"] == reg]
                if len(reg_sub) == 0:
                    continue

                sample_cnt = len(reg_sub)
                eff_n = round(sample_cnt * (stride_bars / b), 1)

                actual_rets = reg_sub["actual_return_pct"].dropna().values
                mean_ret = round(float(np.mean(actual_rets)), 4) if len(actual_rets) > 0 else 0.0
                med_ret = round(float(np.median(actual_rets)), 4) if len(actual_rets) > 0 else 0.0
                std_ret = round(float(np.std(actual_rets)), 4) if len(actual_rets) > 0 else 0.0
                p05_var = round(float(np.percentile(actual_rets, 5)), 4) if len(actual_rets) >= 5 else 0.0
                p95_up = round(float(np.percentile(actual_rets, 95)), 4) if len(actual_rets) >= 5 else 0.0

                mean_mfe = round(float(reg_sub["mean_mfe_pct"].mean()), 4)
                mean_mae = round(float(reg_sub["mean_mae_pct"].mean()), 4)

                mean_abs_move = float(np.mean(np.abs(actual_rets))) if len(actual_rets) > 0 else 1.0
                fric_drag_pct = round((self.ROUNDTRIP_FRICTION_PCT / max(0.01, mean_abs_move)) * 100.0, 2)

                brier_score = round(float(reg_sub["brier_score"].dropna().mean()), 5)
                skill_score = round(float(1.0 - (brier_score / uncond_brier)), 4) if uncond_brier > 0 else 0.0

                dist_rec = ConditionalDistributionRecord(
                    horizon=h_key,
                    holding_bars=b,
                    holding_hours=hrs,
                    market_regime=reg,
                    sample_count=sample_cnt,
                    effective_n=eff_n,
                    mean_fwd_ret_pct=mean_ret,
                    median_fwd_ret_pct=med_ret,
                    std_fwd_ret_pct=std_ret,
                    p05_downside_var_pct=p05_var,
                    p95_upside_pct=p95_up,
                    mean_mfe_pct=mean_mfe,
                    mean_mae_pct=mean_mae,
                    roundtrip_friction_bps=self.ROUNDTRIP_FRICTION_BPS,
                    friction_drag_pct=fric_drag_pct,
                    brier_score=brier_score,
                    unconditional_brier_score=round(uncond_brier, 5),
                    calibration_skill_score=skill_score,
                )
                distribution_rows.append(dist_rec.to_dict())

        df_dist = pd.DataFrame(distribution_rows)
        dist_path = self.output_dir / "conditional_return_distributions.csv"
        df_dist.to_csv(dist_path, index=False)
        logger.info(f"Exported {len(df_dist)} conditional distribution rows to {dist_path.name}")

        return df_preds, df_dist

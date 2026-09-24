"""Session Behavior and Boundary Response Analysis Engine for Sprint 04.

Implements Parts 4, 5, 7, and 8:
- Session Boundary Research (Asia, London, NY, US Equity open/close across T-120m to T+4h)
- Session Base Rates (descriptive distributions by hour, weekday, weekend, sessions, overlaps)
- Weekend vs Weekday Behavior (Friday post-close, Sat, Sun, Sun pre-futures, Mon transition)
- Funding Settlement Proximity Analysis (8h funding cycles)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Tuple
import numpy as np
import pandas as pd

from coin_behavior_engine.utils.logging import logger


class SessionAnalysisEngine:
    """Computes session base rates, boundary responses, weekend dynamics, and funding proximity."""

    def __init__(
        self,
        spot_parquet: str | Path = "data/derived/features_with_outcomes_5m.parquet",
        session_parquet: str | Path = "data/reports/sprint04/session_context_features.parquet",
        reports_dir: str | Path = "data/reports/sprint04",
    ):
        self.spot_path = Path(spot_parquet)
        self.session_path = Path(session_parquet)
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def load_merged_data(self) -> pd.DataFrame:
        """Load spot and session features merged on datetime_open."""
        df_spot = pd.read_parquet(self.spot_path)
        df_spot["datetime_open"] = pd.to_datetime(df_spot["datetime_open"], utc=True)

        df_sess = pd.read_parquet(self.session_path)
        df_sess["datetime_open"] = pd.to_datetime(df_sess["datetime_open"], utc=True)

        df = pd.merge(df_spot, df_sess, on="datetime_open", how="inner")
        df = df.sort_values("datetime_open").reset_index(drop=True)
        return df

    def run_all_session_analyses(self) -> Dict[str, pd.DataFrame]:
        """Execute all session-level research routines and save CSV outputs."""
        logger.info("Executing Session Analysis Engine...")
        df = self.load_merged_data()

        # Part 4: Session Boundary Response Surface
        df_boundary = self.analyze_boundary_response(df)

        # Part 5: Session Base Rates
        df_base_rates = self.analyze_session_base_rates(df)

        # Part 7: Weekend Dynamics
        df_weekend = self.analyze_weekend_behavior(df)

        # Part 8: Funding Settlement Proximity
        df_funding = self.analyze_funding_proximity(df)

        return {
            "boundary": df_boundary,
            "base_rates": df_base_rates,
            "weekend": df_weekend,
            "funding": df_funding,
        }

    # =========================================================================
    # Part 4: Session Boundary Research (Response Surface)
    # =========================================================================
    def analyze_boundary_response(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Part 4: Analyzing Session Boundary Response Surfaces...")
        boundaries = [
            ("ASIA_OPEN", (df["session_asia_active"] == 1) & (df["session_asia_active"].shift(1) == 0)),
            ("LONDON_OPEN", (df["session_london_active"] == 1) & (df["session_london_active"].shift(1) == 0)),
            ("NEW_YORK_OPEN", (df["session_new_york_active"] == 1) & (df["session_new_york_active"].shift(1) == 0)),
            ("US_EQUITY_OPEN", (df["us_equity_market_open"] == 1) & (df["us_equity_market_open"].shift(1) == 0)),
            ("US_EQUITY_CLOSE", (df["us_equity_market_open"] == 0) & (df["us_equity_market_open"].shift(1) == 1)),
        ]

        # Windows: T-120m (-24), T-60m (-12), T-30m (-6), T-15m (-3), T (0), T+15m (+3), T+30m (+6), T+60m (+12), T+120m (+24), T+4h (+48)
        window_offsets = [
            ("T-120m", -24),
            ("T-60m", -12),
            ("T-30m", -6),
            ("T-15m", -3),
            ("T", 0),
            ("T+15m", 3),
            ("T+30m", 6),
            ("T+60m", 12),
            ("T+120m", 24),
            ("T+4h", 48),
        ]

        q95_move = df["fwd_abs_ret_4h"].quantile(0.95)
        records = []

        for b_name, b_mask in boundaries:
            b_indices = df.index[b_mask.fillna(False)].to_numpy()
            b_indices = b_indices[(b_indices >= 48) & (b_indices < len(df) - 48)]

            for w_label, offset in window_offsets:
                target_idx = b_indices + offset
                sub = df.iloc[target_idx]

                ret_mean = float(sub["fwd_ret_4h"].mean())
                abs_ret_mean = float(sub["fwd_abs_ret_4h"].mean())
                vol_mean = float(sub["fwd_vol_4h"].mean())
                range_mean = float(sub["fwd_range_4h"].mean())
                tail_prob = float((sub["fwd_abs_ret_4h"] > q95_move).mean())

                records.append({
                    "boundary_name": b_name,
                    "window_offset": w_label,
                    "offset_bars_5m": offset,
                    "sample_size": len(sub),
                    "mean_signed_return_4h": ret_mean,
                    "mean_abs_return_4h": abs_ret_mean,
                    "mean_realized_vol_4h": vol_mean,
                    "mean_range_4h": range_mean,
                    "tail_event_probability_95th": tail_prob,
                })

        res_df = pd.DataFrame(records)
        p_out = self.reports_dir / "session_boundary_response.csv"
        res_df.to_csv(p_out, index=False)
        logger.info(f"Saved {p_out} ({len(res_df)} rows)")
        return res_df

    # =========================================================================
    # Part 5: Session Base Rates
    # =========================================================================
    def analyze_session_base_rates(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Part 5: Computing Descriptive Session Base Rates...")
        q95_move = df["fwd_abs_ret_4h"].quantile(0.95)

        categories: List[Tuple[str, str, pd.Series]] = []

        # Hourly UTC
        for h in range(24):
            categories.append(("HOUR_UTC", f"Hour_{h:02d}", df["hour_utc"] == h))

        # Day of week
        day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        for d_num, d_name in enumerate(day_names):
            categories.append(("WEEKDAY", d_name, df["weekday"] == d_num))

        # Broad Session Definitions
        categories.append(("SESSION", "ASIA_SESSION", df["session_asia_active"] == 1))
        categories.append(("SESSION", "LONDON_SESSION", df["session_london_active"] == 1))
        categories.append(("SESSION", "NEW_YORK_SESSION", df["session_new_york_active"] == 1))
        categories.append(("SESSION_OVERLAP", "ASIA_LONDON_OVERLAP", df["asia_london_overlap"] == 1))
        categories.append(("SESSION_OVERLAP", "LONDON_NEW_YORK_OVERLAP", df["london_new_york_overlap"] == 1))
        categories.append(("US_EQUITY", "US_EQUITY_OPEN_REGULAR", df["us_equity_market_open"] == 1))
        categories.append(("WEEKEND", "WEEKEND_CONTINUOUS", df["weekend_flag"] == 1))
        categories.append(("WEEKEND", "WEEKDAY_TRADING", df["weekend_flag"] == 0))

        records = []
        for cat_type, cat_name, mask in categories:
            sub = df[mask]
            n = len(sub)
            if n == 0:
                continue

            ret_mean = float(sub["fwd_ret_4h"].mean())
            ret_std = float(sub["fwd_ret_4h"].std())
            abs_ret_mean = float(sub["fwd_abs_ret_4h"].mean())
            vol_mean = float(sub["fwd_vol_4h"].mean())
            range_mean = float(sub["fwd_range_4h"].mean())
            tail_freq = float((sub["fwd_abs_ret_4h"] > q95_move).mean())

            records.append({
                "category_type": cat_type,
                "category_name": cat_name,
                "sample_size": n,
                "pct_of_total": float(n / len(df) * 100),
                "mean_signed_ret_4h": ret_mean,
                "std_signed_ret_4h": ret_std,
                "mean_abs_ret_4h": abs_ret_mean,
                "mean_volatility_4h": vol_mean,
                "mean_range_4h": range_mean,
                "tail_frequency_95th": tail_freq,
            })

        res_df = pd.DataFrame(records)
        p_out = self.reports_dir / "session_base_rates.csv"
        res_df.to_csv(p_out, index=False)
        logger.info(f"Saved {p_out} ({len(res_df)} rows)")
        return res_df

    # =========================================================================
    # Part 7: Weekend Research
    # =========================================================================
    def analyze_weekend_behavior(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Part 7: Analyzing Weekend vs Weekday Dynamics...")
        q95_move = df["fwd_abs_ret_4h"].quantile(0.95)

        # Regimes within weekend:
        # Friday post-US close: Fri 21:00 UTC to Fri 23:55 UTC
        fri_post = (df["weekday"] == 4) & (df["hour_utc"] >= 21)
        sat = df["weekday"] == 5
        sun_early = (df["weekday"] == 6) & (df["hour_utc"] < 22)
        # Sunday pre-futures-open: Sun 22:00 UTC to 23:55 UTC (CME futures open 18:00 ET)
        sun_pre_fut = (df["weekday"] == 6) & (df["hour_utc"] >= 22)
        # Monday transition: Mon 00:00 to 08:00 UTC
        mon_trans = (df["weekday"] == 0) & (df["hour_utc"] < 8)
        weekday_core = (df["weekday"] >= 0) & (df["weekday"] <= 4) & (~fri_post)

        segments = [
            ("WEEKDAY_CORE", weekday_core),
            ("FRIDAY_POST_US_CLOSE", fri_post),
            ("SATURDAY_FULL_DAY", sat),
            ("SUNDAY_EARLY_DAY", sun_early),
            ("SUNDAY_PRE_FUTURES_OPEN", sun_pre_fut),
            ("MONDAY_TRANSITION", mon_trans),
            ("WEEKEND_TOTAL", df["weekend_flag"] == 1),
        ]

        records = []
        for name, mask in segments:
            sub = df[mask]
            n = len(sub)
            if n == 0:
                continue

            vol_mean = float(sub["fwd_vol_4h"].mean())
            range_mean = float(sub["fwd_range_4h"].mean())
            abs_ret_mean = float(sub["fwd_abs_ret_4h"].mean())
            spot_vol_mean = float(sub["volume"].mean())
            tail_freq = float((sub["fwd_abs_ret_4h"] > q95_move).mean())
            comp_ratio = float(sub["volatility_compression_ratio"].mean())

            records.append({
                "period_segment": name,
                "sample_size": n,
                "mean_4h_volatility": vol_mean,
                "mean_4h_range": range_mean,
                "mean_4h_abs_return": abs_ret_mean,
                "mean_spot_volume_btc": spot_vol_mean,
                "mean_compression_ratio": comp_ratio,
                "tail_event_rate_95th": tail_freq,
            })

        res_df = pd.DataFrame(records)
        p_out = self.reports_dir / "weekend_behavior.csv"
        res_df.to_csv(p_out, index=False)
        logger.info(f"Saved {p_out} ({len(res_df)} rows)")
        return res_df

    # =========================================================================
    # Part 8: Funding Settlement Proximity
    # =========================================================================
    def analyze_funding_proximity(self, df: pd.DataFrame) -> pd.DataFrame:
        logger.info("Part 8: Analyzing Funding Settlement Proximity Dynamics...")
        # Buckets: 0-30m before, 0-30m after, 30-60m before, 30-60m after, baseline middle (120-360m)
        mins_in_cycle = (df["hour_utc"] * 60 + df["datetime_open"].dt.minute) % 480

        b1 = (mins_in_cycle >= 450)  # T-30m to T
        b2 = (mins_in_cycle < 30)   # T to T+30m
        b3 = (mins_in_cycle >= 420) & (mins_in_cycle < 450)  # T-60m to T-30m
        b4 = (mins_in_cycle >= 30) & (mins_in_cycle < 60)   # T+30m to T+60m
        b_mid = (mins_in_cycle >= 120) & (mins_in_cycle <= 360)  # Middle baseline

        buckets = [
            ("FUNDING_PRE_30M", b1),
            ("FUNDING_POST_30M", b2),
            ("FUNDING_PRE_60M_TO_30M", b3),
            ("FUNDING_POST_30M_TO_60M", b4),
            ("MID_CYCLE_CONTROL", b_mid),
        ]

        records = []
        for b_name, mask in buckets:
            sub = df[mask]
            n = len(sub)
            if n == 0:
                continue

            vol = float(sub["fwd_vol_1h"].mean()) if "fwd_vol_1h" in sub.columns else 0.0
            range_1h = float(sub["fwd_range_1h"].mean()) if "fwd_range_1h" in sub.columns else 0.0
            basis_abs = float(sub["basis_abs"].mean()) if "basis_abs" in sub.columns else 0.0
            taker_imb = float(sub["futures_net_taker_imbalance"].mean()) if "futures_net_taker_imbalance" in sub.columns else 0.0
            oi_chg = float(sub["oi_change_1h"].mean()) if "oi_change_1h" in sub.columns else 0.0

            records.append({
                "proximity_bucket": b_name,
                "sample_size": n,
                "mean_fwd_1h_volatility": vol,
                "mean_fwd_1h_range": range_1h,
                "mean_abs_basis": basis_abs,
                "mean_net_taker_imbalance": taker_imb,
                "mean_1h_oi_change": oi_chg,
            })

        res_df = pd.DataFrame(records)
        p_out = self.reports_dir / "funding_proximity_analysis.csv"
        res_df.to_csv(p_out, index=False)
        logger.info(f"Saved {p_out} ({len(res_df)} rows)")
        return res_df

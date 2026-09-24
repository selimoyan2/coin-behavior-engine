"""ETF Flow Feature Engineering Layer for Sprint 05.

Constructs causal 5m aligned feature tables incorporating:
- Causal as-of join semantics with available_at_timestamp
- Pre-ETF era gating (zero synthetic observations)
- Normalized flow metrics (robust z-score, rolling percentile, acceleration, persistence)
- Flow breadth and concentration (Herfindahl index, top-fund share)
- GBTC vs non-GBTC structural flow decomposition
- Data-derived flow states (no arbitrary fixed dollar thresholds)
- Staleness and source-age indicators
- Interactions with Session, Derivatives, Weekend, and Compression
- CME institutional futures context

Outputs:
- data/reports/sprint05/etf_flow_features.parquet (602,240 rows)
- Summary analytical CSVs in data/reports/sprint05/
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from coin_behavior_engine.utils.logging import logger


class ETFFeatureEngine:
    """Computes and aligns ETF flow and institutional features onto the 5m BTC grid."""

    def __init__(
        self,
        spot_path: str | Path = "data/normalized/btcusdt_5m.parquet",
        canonical_flows_path: str | Path = "data/reports/sprint05/etf_flow_canonical.parquet",
        session_path: str | Path = "data/reports/sprint04/session_context_features.parquet",
        derivatives_dir: str | Path = "data/reports/sprint03",
        cme_path: str | Path = "data/normalized/etf/cme_futures_daily.parquet",
        reports_dir: str | Path = "data/reports/sprint05",
    ):
        self.spot_path = Path(spot_path)
        self.canonical_flows_path = Path(canonical_flows_path)
        self.session_path = Path(session_path)
        self.derivatives_dir = Path(derivatives_dir)
        self.cme_path = Path(cme_path)
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def compute_daily_flow_features(self, canonical_df: pd.DataFrame) -> pd.DataFrame:
        """Computes causal rolling metrics on canonical daily flow observations."""
        df = canonical_df.copy().sort_values("available_at_timestamp").reset_index(drop=True)

        flow = df["total_net_flow_usd"]
        n_days = len(df)

        # 1. Causal Rolling Median and MAD (20-day past window)
        roll_med = flow.shift(1).rolling(window=20, min_periods=5).median()
        roll_mad = (
            (flow.shift(1) - roll_med)
            .abs()
            .rolling(window=20, min_periods=5)
            .median()
        )
        df["flow_roll_median_20d"] = roll_med.fillna(0.0)
        df["flow_roll_mad_20d"] = roll_mad.replace(0.0, 1e6).fillna(1e6)
        df["flow_robust_z_20d"] = (
            (flow - df["flow_roll_median_20d"]) / (1.4826 * df["flow_roll_mad_20d"])
        ).clip(-5.0, 5.0).fillna(0.0)

        # 2. Causal Rolling Percentile (past 30 trading days)
        pctiles = []
        for i in range(n_days):
            if i < 5:
                pctiles.append(0.5)
            else:
                past = flow.iloc[max(0, i - 30):i].values
                val = flow.iloc[i]
                rank = (past < val).sum() / len(past)
                pctiles.append(float(rank))
        df["flow_roll_pctile_30d"] = pctiles

        # 3. Flow Acceleration & Persistence
        df["flow_acceleration_usd"] = (flow - flow.shift(1)).fillna(0.0)

        # Consecutive positive / negative days (persistence)
        persistence = []
        cur_streak = 0
        for val in flow.values:
            if val > 1e5:
                cur_streak = cur_streak + 1 if cur_streak > 0 else 1
            elif val < -1e5:
                cur_streak = cur_streak - 1 if cur_streak < 0 else -1
            else:
                cur_streak = 0
            persistence.append(cur_streak)
        df["flow_persistence_days"] = persistence

        # 4. Cumulative Multi-Day Flows
        df["cum_flow_3d_usd"] = flow.rolling(window=3, min_periods=1).sum()
        df["cum_flow_5d_usd"] = flow.rolling(window=5, min_periods=1).sum()
        df["cum_flow_10d_usd"] = flow.rolling(window=10, min_periods=1).sum()
        df["cum_flow_20d_usd"] = flow.rolling(window=20, min_periods=1).sum()

        # 5. Non-GBTC Rolling Z-Score
        non_gbtc = df["non_gbtc_net_flow_usd"]
        ng_med = non_gbtc.shift(1).rolling(window=20, min_periods=5).median()
        ng_mad = (non_gbtc.shift(1) - ng_med).abs().rolling(window=20, min_periods=5).median()
        df["non_gbtc_robust_z"] = (
            (non_gbtc - ng_med.fillna(0.0)) / (1.4826 * ng_mad.replace(0.0, 1e6).fillna(1e6))
        ).clip(-5.0, 5.0).fillna(0.0)

        # 6. Data-Derived Flow States (Frozen Discovery quantiles)
        # Using 2024 Discovery period (first 245 trading days of 2024)
        disc_mask = df["trade_date"] <= "2024-12-31"
        disc_flow = flow[disc_mask] if disc_mask.sum() > 30 else flow
        p20 = float(disc_flow.quantile(0.20))
        p80 = float(disc_flow.quantile(0.80))
        p_med_herf = float(df.loc[disc_mask, "flow_herfindahl_index"].median())

        df["flow_state_expansion"] = (flow >= p80).astype(int)
        df["flow_state_contraction"] = (flow <= p20).astype(int)
        df["flow_state_neutral"] = ((flow > p20) & (flow < p80)).astype(int)
        df["flow_state_inflow_dominant"] = (
            (flow > 0) & (df["positive_fund_fraction"] >= 0.6)
        ).astype(int)
        df["flow_state_outflow_dominant"] = (
            (flow < 0) & (df["negative_fund_fraction"] >= 0.4)
        ).astype(int)
        df["flow_state_broad"] = (df["flow_herfindahl_index"] < p_med_herf).astype(int)
        df["flow_state_concentrated"] = (df["flow_herfindahl_index"] >= p_med_herf).astype(int)

        return df

    def build_aligned_features(self) -> pd.DataFrame:
        """Performs causal as-of alignment onto 5m grid and builds all interactions."""
        logger.info("Building aligned ETF flow features...")

        # 1. Load spot 5m grid
        spot_df = pd.read_parquet(self.spot_path)[["datetime_open", "open", "high", "low", "close", "volume"]]
        spot_df["datetime_open"] = pd.to_datetime(spot_df["datetime_open"], utc=True).astype("datetime64[ns, UTC]")
        spot_df = spot_df.sort_values("datetime_open").reset_index(drop=True)
        n_bars = len(spot_df)

        # Rolling 24h spot volume in USD
        spot_vol_24h = (spot_df["volume"] * spot_df["close"]).rolling(window=288, min_periods=12).sum()
        spot_df["spot_vol_24h_usd"] = spot_vol_24h.fillna(1e8)

        # 2. Load and prepare daily flow features
        canonical_df = pd.read_parquet(self.canonical_flows_path)
        canonical_df["available_at_timestamp"] = pd.to_datetime(
            canonical_df["available_at_timestamp"], utc=True
        ).astype("datetime64[ns, UTC]")
        daily_features = self.compute_daily_flow_features(canonical_df)

        # 3. Causal As-Of Join: spot_df.datetime_open >= daily_features.available_at_timestamp
        daily_features = daily_features.sort_values("available_at_timestamp").reset_index(drop=True)
        merged = pd.merge_asof(
            spot_df,
            daily_features,
            left_on="datetime_open",
            right_on="available_at_timestamp",
            direction="backward",
        )

        # 4. Era gating: Pre-ETF vs ETF-Active
        first_avail_ts = daily_features["available_at_timestamp"].min()
        is_active = merged["datetime_open"] >= first_avail_ts
        merged["is_etf_active"] = is_active.astype(int)

        # Zero-out / nan flow fields during Pre-ETF era (Zero synthetic history!)
        flow_cols = [
            c for c in daily_features.columns
            if c not in ["trade_date", "publication_timestamp", "available_at_timestamp"]
        ]
        for c in flow_cols:
            if c in merged.columns:
                if pd.api.types.is_numeric_dtype(merged[c]):
                    merged.loc[~is_active, c] = 0.0
                else:
                    merged.loc[~is_active, c] = "PRE_ETF"

        # 5. Source Age and Staleness Indicators
        age_hours = (merged["datetime_open"] - merged["available_at_timestamp"]).dt.total_seconds() / 3600.0
        merged["etf_source_age_hours"] = np.where(is_active, age_hours, np.nan)
        merged["hours_since_latest_flow_publication"] = merged["etf_source_age_hours"]

        # Freshness state
        freshness = np.where(
            ~is_active,
            "PRE_ETF",
            np.where(
                merged["etf_source_age_hours"] <= 24.0,
                "FRESH",
                np.where(merged["etf_source_age_hours"] <= 48.0, "AGING", "STALE"),
            ),
        )
        merged["etf_freshness_state"] = freshness
        merged["is_etf_fresh"] = (freshness == "FRESH").astype(int)
        merged["is_etf_stale"] = (freshness == "STALE").astype(int)

        # Flow to Spot Volume Ratio
        merged["flow_to_spot_vol"] = np.where(
            is_active,
            merged["total_net_flow_usd"] / merged["spot_vol_24h_usd"],
            0.0,
        )

        # 6. Session and Weekend Merge & Interactions
        if self.session_path.exists():
            session_df = pd.read_parquet(self.session_path)[
                [
                    "datetime_open",
                    "session_asia_active",
                    "session_london_active",
                    "session_new_york_active",
                    "london_new_york_overlap",
                    "weekend_flag",
                ]
            ]
            session_df["datetime_open"] = pd.to_datetime(session_df["datetime_open"], utc=True).astype("datetime64[ns, UTC]")
            merged = pd.merge(merged, session_df, on="datetime_open", how="left")
        else:
            merged["session_asia_active"] = 0
            merged["session_london_active"] = 0
            merged["session_new_york_active"] = 0
            merged["london_new_york_overlap"] = 0
            merged["weekend_flag"] = 0

        # ETF Flow x Session Interactions
        fz = merged["flow_robust_z_20d"]
        merged["etf_flow_x_asia"] = fz * merged["session_asia_active"].fillna(0)
        merged["etf_flow_x_london"] = fz * merged["session_london_active"].fillna(0)
        merged["etf_flow_x_ny"] = fz * merged["session_new_york_active"].fillna(0)
        merged["etf_flow_x_overlap"] = fz * merged["london_new_york_overlap"].fillna(0)
        merged["etf_flow_x_weekend"] = fz * merged["weekend_flag"].fillna(0)

        # 7. Derivatives Merge & Interactions
        oi_path = self.derivatives_dir / "open_interest_features.parquet"
        basis_path = self.derivatives_dir / "basis_features.parquet"
        taker_path = self.derivatives_dir / "futures_taker_features.parquet"

        if oi_path.exists():
            oi_df = pd.read_parquet(oi_path)[["datetime_open", "oi_change_1h"]]
            oi_df["datetime_open"] = pd.to_datetime(oi_df["datetime_open"], utc=True).astype("datetime64[ns, UTC]")
            merged = pd.merge(merged, oi_df, on="datetime_open", how="left")
            merged["etf_flow_x_oi_chg"] = fz * merged["oi_change_1h"].fillna(0.0)
        else:
            merged["etf_flow_x_oi_chg"] = 0.0

        if basis_path.exists():
            basis_df = pd.read_parquet(basis_path)[["datetime_open", "basis_level"]]
            basis_df["datetime_open"] = pd.to_datetime(basis_df["datetime_open"], utc=True).astype("datetime64[ns, UTC]")
            merged = pd.merge(merged, basis_df, on="datetime_open", how="left")
            merged["etf_flow_x_basis"] = fz * merged["basis_level"].fillna(0.0)
        else:
            merged["etf_flow_x_basis"] = 0.0

        if taker_path.exists():
            taker_df = pd.read_parquet(taker_path)[["datetime_open", "futures_taker_buy_sell_ratio"]]
            taker_df["datetime_open"] = pd.to_datetime(taker_df["datetime_open"], utc=True).astype("datetime64[ns, UTC]")
            merged = pd.merge(merged, taker_df, on="datetime_open", how="left")
            merged["etf_flow_x_taker"] = fz * (merged["futures_taker_buy_sell_ratio"].fillna(1.0) - 1.0)
        else:
            merged["etf_flow_x_taker"] = 0.0

        # ETF Flow x Compression Interaction
        spot_ret_5m = (merged["close"] / merged["open"] - 1.0).fillna(0.0)
        vol_24h = spot_ret_5m.rolling(288, min_periods=24).std()
        vol_7d = spot_ret_5m.rolling(2016, min_periods=100).std()
        compression_ratio = (vol_24h / vol_7d.replace(0.0, np.nan)).fillna(1.0)
        merged["compression_ratio"] = compression_ratio
        merged["etf_flow_x_compression"] = fz * compression_ratio

        # 8. CME Continuous Futures Features
        if self.cme_path.exists():
            cme_raw = pd.read_parquet(self.cme_path)
            cme_raw["trade_date"] = pd.to_datetime(cme_raw["trade_date"])
            # CME settlement available at 22:00 UTC
            cme_raw["cme_available_at"] = pd.to_datetime(
                cme_raw["trade_date"].dt.strftime("%Y-%m-%d") + " 22:00:00", utc=True
            ).astype("datetime64[ns, UTC]")
            cme_raw["cme_ret_1d"] = (cme_raw["close"] / cme_raw["close"].shift(1) - 1.0).fillna(0.0)
            cme_vol_med = cme_raw["volume"].rolling(20, min_periods=5).median().replace(0, 1.0)
            cme_raw["cme_volume_z"] = ((cme_raw["volume"] - cme_vol_med) / cme_vol_med).clip(-3.0, 3.0).fillna(0.0)

            cme_sub = cme_raw[["cme_available_at", "close", "cme_ret_1d", "cme_volume_z"]].rename(
                columns={"close": "cme_close"}
            ).sort_values("cme_available_at")

            merged = pd.merge_asof(
                merged,
                cme_sub,
                left_on="datetime_open",
                right_on="cme_available_at",
                direction="backward",
            )
            merged["cme_basis_bps"] = np.where(
                merged["cme_close"].notna() & (merged["close"] > 0),
                (merged["cme_close"] - merged["close"]) / merged["close"] * 10000.0,
                0.0,
            )
        else:
            merged["cme_basis_bps"] = 0.0
            merged["cme_ret_1d"] = 0.0
            merged["cme_volume_z"] = 0.0

        # Save primary feature parquet
        out_parquet = self.reports_dir / "etf_flow_features.parquet"
        merged.to_parquet(out_parquet, index=False)
        logger.info(
            "Saved aligned ETF flow features to %s (%d rows, %d cols)",
            out_parquet,
            len(merged),
            len(merged.columns),
        )

        # Generate summary CSVs
        self._export_feature_summaries(merged, daily_features)

        return merged

    def _export_feature_summaries(self, aligned_df: pd.DataFrame, daily_df: pd.DataFrame) -> None:
        """Exports analytical CSV tables specified in Mandatory Outputs."""
        etf_active = aligned_df[aligned_df["is_etf_active"] == 1]

        # 1. aggregate_flow_analysis.csv
        agg_summary = daily_df[
            [
                "total_net_flow_usd",
                "gross_inflow_usd",
                "gross_outflow_usd",
                "total_gross_volume_usd",
                "flow_breadth",
                "flow_dispersion_usd",
            ]
        ].describe().transpose().reset_index().rename(columns={"index": "metric"})
        agg_summary.to_csv(self.reports_dir / "aggregate_flow_analysis.csv", index=False)

        # 2. normalized_flow_analysis.csv
        norm_summary = daily_df[
            [
                "flow_robust_z_20d",
                "flow_roll_pctile_30d",
                "flow_acceleration_usd",
                "flow_persistence_days",
                "cum_flow_5d_usd",
                "cum_flow_20d_usd",
            ]
        ].describe().transpose().reset_index().rename(columns={"index": "metric"})
        norm_summary.to_csv(self.reports_dir / "normalized_flow_analysis.csv", index=False)

        # 3. flow_breadth_analysis.csv
        breadth_summary = daily_df[
            [
                "flow_breadth",
                "positive_fund_fraction",
                "negative_fund_fraction",
                "flow_herfindahl_index",
                "top_fund_contribution",
            ]
        ].describe().transpose().reset_index().rename(columns={"index": "metric"})
        breadth_summary.to_csv(self.reports_dir / "flow_breadth_analysis.csv", index=False)

        # 4. flow_persistence_analysis.csv
        pers_counts = daily_df["flow_persistence_days"].value_counts().sort_index().reset_index()
        pers_counts.columns = ["persistence_days", "count"]
        pers_counts.to_csv(self.reports_dir / "flow_persistence_analysis.csv", index=False)

        # 5. gbtc_structure_analysis.csv
        gbtc_summary = daily_df[
            [
                "gbtc_net_flow_usd",
                "non_gbtc_net_flow_usd",
                "gbtc_share_of_total",
                "non_gbtc_robust_z",
            ]
        ].describe().transpose().reset_index().rename(columns={"index": "metric"})
        gbtc_summary.to_csv(self.reports_dir / "gbtc_structure_analysis.csv", index=False)

        # 6. etf_session_interactions.csv
        sess_cols = [
            "etf_flow_x_asia",
            "etf_flow_x_london",
            "etf_flow_x_ny",
            "etf_flow_x_overlap",
            "etf_flow_x_weekend",
        ]
        etf_active[sess_cols].describe().transpose().reset_index().rename(
            columns={"index": "interaction_feature"}
        ).to_csv(self.reports_dir / "etf_session_interactions.csv", index=False)

        # 7. etf_derivatives_interactions.csv
        deriv_cols = [
            "etf_flow_x_oi_chg",
            "etf_flow_x_basis",
            "etf_flow_x_taker",
            "etf_flow_x_compression",
        ]
        etf_active[deriv_cols].describe().transpose().reset_index().rename(
            columns={"index": "interaction_feature"}
        ).to_csv(self.reports_dir / "etf_derivatives_interactions.csv", index=False)

        # 8. etf_compression_analysis.csv
        comp_summary = etf_active[["compression_ratio", "etf_flow_x_compression"]].describe().transpose().reset_index()
        comp_summary.to_csv(self.reports_dir / "etf_compression_analysis.csv", index=False)

        # 9. etf_weekend_analysis.csv
        weekend_comp = etf_active.groupby("weekend_flag")[
            ["etf_source_age_hours", "flow_robust_z_20d", "is_etf_stale"]
        ].mean().reset_index()
        weekend_comp.to_csv(self.reports_dir / "etf_weekend_analysis.csv", index=False)

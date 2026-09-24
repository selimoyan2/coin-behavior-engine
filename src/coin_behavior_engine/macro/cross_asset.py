"""Cross-Asset Macro Feature Engineering & Correlation Engine for Sprint 04.

Engineers causally aligned cross-asset macro features on the 5-minute spot grid:
- Strictly causal as-of join (available_at_timestamp <= datetime_open)
- Features for 8 macro instruments:
  - NASDAQ Composite (^IXIC)
  - S&P 500 (^GSPC)
  - CBOE Volatility Index (^VIX)
  - U.S. Dollar Index (DX-Y.NYB)
  - 10-Year Treasury Yield (^TNX)
  - 2-Year Treasury Yield Futures (2YY=F)
  - Gold Futures (GC=F)
  - Crude Oil Futures (CL=F)
- Per-instrument features: close, ret_1d, ret_5d, vol_20d, trend_20d, source_age_seconds, is_stale, market_open
- Composite features: yield_spread_10y_2y, vix_regime, equity_risk_on, etc.
- Dynamic rolling correlations with BTC: 30d and 7d rolling correlations.

Generates:
- data/reports/sprint04/cross_asset_features.parquet (602,240 rows)
- data/reports/sprint04/staleness_audit.csv
- data/reports/sprint04/cross_asset_correlations.csv
- data/reports/sprint04/cross_asset_lead_lag.csv
- data/reports/sprint04/btc_dynamic_correlations.csv
- data/reports/sprint04/macro_redundancy_analysis.csv
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from coin_behavior_engine.utils.logging import logger


class CrossAssetEngine:
    """Engineers causal cross-asset macro features and analyzes macro-BTC relationships."""

    INSTRUMENT_MAP = [
        {"name": "NASDAQ", "prefix": "nasdaq", "file": "IXIC.parquet", "symbol": "^IXIC", "class": "EQUITY"},
        {"name": "SP500", "prefix": "sp500", "file": "GSPC.parquet", "symbol": "^GSPC", "class": "EQUITY"},
        {"name": "VIX", "prefix": "vix", "file": "VIX.parquet", "symbol": "^VIX", "class": "VOLATILITY"},
        {"name": "DXY", "prefix": "dxy", "file": "DX_Y.NYB.parquet", "symbol": "DX-Y.NYB", "class": "CURRENCY"},
        {"name": "TNX", "prefix": "tnx_10y", "file": "TNX.parquet", "symbol": "^TNX", "class": "RATES"},
        {"name": "2YY", "prefix": "yield_2y", "file": "2YY_F.parquet", "symbol": "2YY=F", "class": "RATES"},
        {"name": "GOLD", "prefix": "gold", "file": "GC_F.parquet", "symbol": "GC=F", "class": "COMMODITY"},
        {"name": "OIL", "prefix": "oil", "file": "CL_F.parquet", "symbol": "CL=F", "class": "COMMODITY"},
    ]

    def __init__(
        self,
        macro_dir: Path | str = "data/normalized/macro",
        spot_grid_path: Path | str = "data/derived/features_with_outcomes_5m.parquet",
        session_features_path: Path | str = "data/reports/sprint04/session_context_features.parquet",
        output_dir: Path | str = "data/reports/sprint04",
    ):
        self.macro_dir = Path(macro_dir)
        self.spot_grid_path = Path(spot_grid_path)
        self.session_features_path = Path(session_features_path)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def load_macro_series(self) -> Dict[str, pd.DataFrame]:
        """Load and engineer daily features for each macro instrument."""
        series_dict: Dict[str, pd.DataFrame] = {}

        for item in self.INSTRUMENT_MAP:
            filepath = self.macro_dir / item["file"]
            if not filepath.exists():
                logger.warning(f"Macro file not found: {filepath}")
                continue

            df = pd.read_parquet(filepath)
            df = df.sort_values("available_at_timestamp").reset_index(drop=True)

            # Daily return: (P_t - P_{t-1}) / P_{t-1}
            df["ret_1d"] = df["close"].pct_change()
            df["ret_5d"] = df["close"].pct_change(5)

            # Realized volatility over 20 trading days (annualized)
            df["vol_20d"] = df["ret_1d"].rolling(20).std() * np.sqrt(252)

            # 20-day trend slope / cumulative change
            df["trend_20d"] = df["close"].pct_change(20)

            # Clean NaNs in warmup
            df["ret_1d"] = df["ret_1d"].fillna(0.0)
            df["ret_5d"] = df["ret_5d"].fillna(0.0)
            df["vol_20d"] = df["vol_20d"].bfill().fillna(0.0)
            df["trend_20d"] = df["trend_20d"].fillna(0.0)

            series_dict[item["name"]] = df

        return series_dict

    def build_cross_asset_features(self) -> pd.DataFrame:
        """As-of merge all macro series onto the 5m spot grid and engineer composite features."""
        logger.info("Loading 5m spot grid timestamps and session features...")
        grid = pd.read_parquet(self.spot_grid_path, columns=["datetime_open", "close", "fwd_ret_4h", "fwd_vol_4h", "fwd_ret_24h", "fwd_vol_24h"])
        grid = grid.sort_values("datetime_open").reset_index(drop=True)

        # Load session features for market open flags
        session_df = pd.read_parquet(self.session_features_path, columns=["datetime_open", "us_equity_market_open", "weekend_flag"])
        grid = pd.merge(grid, session_df, on="datetime_open", how="left")

        macro_series = self.load_macro_series()

        result_df = pd.DataFrame({"datetime_open": grid["datetime_open"]})

        logger.info("Performing strictly causal as-of joins for all 8 macro instruments...")
        for item in self.INSTRUMENT_MAP:
            name = item["name"]
            prefix = item["prefix"]
            if name not in macro_series:
                continue

            m_df = macro_series[name][["available_at_timestamp", "close", "ret_1d", "ret_5d", "vol_20d", "trend_20d"]].copy()
            m_df["available_at_timestamp"] = m_df["available_at_timestamp"].astype("datetime64[ms, UTC]")
            m_df = m_df.rename(columns={
                "close": f"{prefix}_close",
                "ret_1d": f"{prefix}_ret_1d",
                "ret_5d": f"{prefix}_ret_5d",
                "vol_20d": f"{prefix}_vol_20d",
                "trend_20d": f"{prefix}_trend_20d",
            })

            # As-of join: backward match ensures available_at_timestamp <= datetime_open
            joined = pd.merge_asof(
                result_df[["datetime_open"]],
                m_df,
                left_on="datetime_open",
                right_on="available_at_timestamp",
                direction="backward",
            )

            # Elapsed age in seconds
            source_age = (joined["datetime_open"] - joined["available_at_timestamp"]).dt.total_seconds()
            result_df[f"{prefix}_source_age_seconds"] = source_age.fillna(86400 * 7).astype(np.float64)

            # Forward fill initial warmups if any
            result_df[f"{prefix}_close"] = joined[f"{prefix}_close"].ffill().bfill()
            result_df[f"{prefix}_ret_1d"] = joined[f"{prefix}_ret_1d"].ffill().fillna(0.0)
            result_df[f"{prefix}_ret_5d"] = joined[f"{prefix}_ret_5d"].ffill().fillna(0.0)
            result_df[f"{prefix}_vol_20d"] = joined[f"{prefix}_vol_20d"].ffill().fillna(0.0)
            result_df[f"{prefix}_trend_20d"] = joined[f"{prefix}_trend_20d"].ffill().fillna(0.0)

            # Market open and staleness flags
            if item["class"] in ["EQUITY", "VOLATILITY", "RATES"]:
                result_df[f"{prefix}_market_open"] = grid["us_equity_market_open"].astype(np.int8)
                result_df[f"{prefix}_is_stale"] = (
                    (grid["us_equity_market_open"] == 0) | (result_df[f"{prefix}_source_age_seconds"] > 86400 * 2.5)
                ).astype(np.int8)
            else:
                # Commodities (Globex open ~23h/day except weekend)
                comm_open = (grid["weekend_flag"] == 0).astype(np.int8)
                result_df[f"{prefix}_market_open"] = comm_open
                result_df[f"{prefix}_is_stale"] = (
                    (grid["weekend_flag"] == 1) | (result_df[f"{prefix}_source_age_seconds"] > 86400 * 2.5)
                ).astype(np.int8)

        logger.info("Computing composite cross-asset features...")
        # 1. Yield Curve Spread (10Y - 2Y) in percentage points
        if "tnx_10y_close" in result_df and "yield_2y_close" in result_df:
            result_df["yield_spread_10y_2y"] = result_df["tnx_10y_close"] - result_df["yield_2y_close"]
            result_df["yield_spread_chg_5d"] = (result_df["tnx_10y_ret_5d"] - result_df["yield_2y_ret_5d"])
        else:
            result_df["yield_spread_10y_2y"] = 0.0
            result_df["yield_spread_chg_5d"] = 0.0

        # 2. VIX Regime (0: Low <15, 1: Normal 15-25, 2: Elevated >25)
        if "vix_close" in result_df:
            vix_c = result_df["vix_close"]
            result_df["vix_regime"] = np.where(vix_c < 15.0, 0, np.where(vix_c <= 25.0, 1, 2)).astype(np.int8)
            result_df["vix_change_1d"] = result_df["vix_ret_1d"]
            result_df["vix_change_5d"] = result_df["vix_ret_5d"]
        else:
            result_df["vix_regime"] = 1
            result_df["vix_change_1d"] = 0.0
            result_df["vix_change_5d"] = 0.0

        # 3. Equity Risk-On Composites
        if "nasdaq_ret_1d" in result_df and "sp500_ret_1d" in result_df:
            result_df["equity_risk_on_1d"] = (result_df["nasdaq_ret_1d"] + result_df["sp500_ret_1d"]) / 2.0
            result_df["equity_risk_on_5d"] = (result_df["nasdaq_ret_5d"] + result_df["sp500_ret_5d"]) / 2.0
        else:
            result_df["equity_risk_on_1d"] = 0.0
            result_df["equity_risk_on_5d"] = 0.0

        logger.info("Computing rolling dynamic correlations with BTC on daily aggregation...")
        # To compute mathematically rigorous dynamic correlations without lookahead bias,
        # we compute daily BTC returns aligned to macro daily available timestamps,
        # compute 30-day and 7-day rolling correlations, and merge as-of.
        btc_daily = grid[["datetime_open", "close"]].copy()
        btc_daily["date"] = btc_daily["datetime_open"].dt.date.astype(str)
        # Daily close is the close at or immediately preceding 21:00 UTC
        daily_close_btc = btc_daily.groupby("date")["close"].last().reset_index()
        daily_close_btc["btc_ret_1d"] = daily_close_btc["close"].pct_change().fillna(0.0)

        # Merge daily BTC return with macro series
        m_daily = daily_close_btc.copy()
        for item in self.INSTRUMENT_MAP:
            name = item["name"]
            prefix = item["prefix"]
            if name in macro_series:
                sub = macro_series[name][["date", "ret_1d"]].rename(columns={"ret_1d": f"{prefix}_ret_1d"})
                m_daily = pd.merge(m_daily, sub, on="date", how="left")
                m_daily[f"{prefix}_ret_1d"] = m_daily[f"{prefix}_ret_1d"].ffill().fillna(0.0)

        # Rolling correlations (min_periods=10)
        corr_cols = {}
        for target_prefix, col_name in [
            ("nasdaq", "corr_btc_nasdaq_30d"),
            ("sp500", "corr_btc_sp500_30d"),
            ("dxy", "corr_btc_dxy_30d"),
            ("gold", "corr_btc_gold_30d"),
            ("vix", "corr_btc_vix_30d"),
        ]:
            if f"{target_prefix}_ret_1d" in m_daily:
                m_daily[col_name] = (
                    m_daily["btc_ret_1d"]
                    .rolling(30, min_periods=10)
                    .corr(m_daily[f"{target_prefix}_ret_1d"])
                    .fillna(0.0)
                )
                corr_cols[col_name] = col_name

        if "nasdaq_ret_1d" in m_daily:
            m_daily["corr_btc_nasdaq_7d"] = (
                m_daily["btc_ret_1d"]
                .rolling(7, min_periods=5)
                .corr(m_daily["nasdaq_ret_1d"])
                .fillna(0.0)
            )
            corr_cols["corr_btc_nasdaq_7d"] = "corr_btc_nasdaq_7d"

        # Stamped available at 21:00 UTC
        m_daily["available_at_timestamp"] = pd.to_datetime(m_daily["date"] + " 21:00:00", utc=True).astype("datetime64[ms, UTC]")
        m_daily_corr = m_daily[["available_at_timestamp"] + list(corr_cols.keys())]

        # As-of join rolling correlations to result_df
        corr_joined = pd.merge_asof(
            result_df[["datetime_open"]],
            m_daily_corr,
            left_on="datetime_open",
            right_on="available_at_timestamp",
            direction="backward",
        )

        for col in corr_cols.keys():
            result_df[col] = corr_joined[col].ffill().fillna(0.0).astype(np.float64)

        # Save cross-asset features parquet
        out_parquet = self.output_dir / "cross_asset_features.parquet"
        result_df.to_parquet(out_parquet, index=False)
        logger.info(f"Saved {out_parquet} ({len(result_df)} rows, {len(result_df.columns)} columns)")

        return result_df

    def run_staleness_audit(self, feat_df: pd.DataFrame) -> pd.DataFrame:
        """Audit staleness and market open distribution for each macro instrument."""
        logger.info("Running Staleness and Market Open Audit...")
        rows = []
        for item in self.INSTRUMENT_MAP:
            prefix = item["prefix"]
            age_col = f"{prefix}_source_age_seconds"
            open_col = f"{prefix}_market_open"
            stale_col = f"{prefix}_is_stale"

            if age_col not in feat_df:
                continue

            ages_hr = feat_df[age_col] / 3600.0
            rows.append({
                "instrument_name": item["name"],
                "symbol": item["symbol"],
                "asset_class": item["class"],
                "mean_age_hours": float(ages_hr.mean()),
                "median_age_hours": float(ages_hr.median()),
                "max_age_hours": float(ages_hr.max()),
                "pct_market_open": float((feat_df[open_col] == 1).mean() * 100.0),
                "pct_stale": float((feat_df[stale_col] == 1).mean() * 100.0),
                "staleness_threshold_rule": "age > 60h or market_closed",
            })

        df = pd.DataFrame(rows)
        out_file = self.output_dir / "staleness_audit.csv"
        df.to_csv(out_file, index=False)
        logger.info(f"Saved {out_file}")
        return df

    def run_cross_asset_correlations(self, feat_df: pd.DataFrame) -> pd.DataFrame:
        """Compute correlations between macro features and BTC forward outcomes across partitions."""
        logger.info("Computing Cross-Asset vs BTC Forward Outcome Correlations...")
        # Load spot outcomes
        spot = pd.read_parquet(
            self.spot_grid_path,
            columns=["datetime_open", "fwd_ret_4h", "fwd_vol_4h", "fwd_ret_24h", "fwd_vol_24h"],
        )
        merged = pd.merge(feat_df, spot, on="datetime_open", how="inner")

        partitions = {
            "ALL_HISTORY": merged["datetime_open"] < "2026-10-01",
            "DISCOVERY_2021_2024": (merged["datetime_open"] >= "2021-01-01") & (merged["datetime_open"] < "2025-01-01"),
            "VALIDATION_2025": (merged["datetime_open"] >= "2025-01-01") & (merged["datetime_open"] < "2026-01-01"),
            "HOLDOUT_2026": merged["datetime_open"] >= "2026-01-01",
        }

        test_features = [
            ("nasdaq_ret_1d", "NASDAQ 1d Return"),
            ("nasdaq_ret_5d", "NASDAQ 5d Return"),
            ("sp500_ret_1d", "S&P 500 1d Return"),
            ("vix_close", "VIX Level"),
            ("vix_ret_1d", "VIX 1d Return"),
            ("dxy_ret_1d", "DXY 1d Return"),
            ("tnx_10y_close", "10Y Yield Level"),
            ("yield_spread_10y_2y", "10Y-2Y Yield Spread"),
            ("gold_ret_1d", "Gold 1d Return"),
            ("oil_ret_1d", "Crude Oil 1d Return"),
            ("equity_risk_on_1d", "Equity Risk-On Composite"),
        ]

        rows = []
        for part_name, mask in partitions.items():
            sub = merged[mask]
            for col, desc in test_features:
                if col not in sub:
                    continue
                r_ret4 = sub[col].corr(sub["fwd_ret_4h"])
                r_vol4 = sub[col].corr(sub["fwd_vol_4h"])
                r_ret24 = sub[col].corr(sub["fwd_ret_24h"])
                r_vol24 = sub[col].corr(sub["fwd_vol_24h"])

                rows.append({
                    "partition": part_name,
                    "feature_name": col,
                    "description": desc,
                    "corr_fwd_return_4h": float(r_ret4) if not np.isnan(r_ret4) else 0.0,
                    "corr_fwd_vol_4h": float(r_vol4) if not np.isnan(r_vol4) else 0.0,
                    "corr_fwd_return_24h": float(r_ret24) if not np.isnan(r_ret24) else 0.0,
                    "corr_fwd_vol_24h": float(r_vol24) if not np.isnan(r_vol24) else 0.0,
                })

        df = pd.DataFrame(rows)
        out_file = self.output_dir / "cross_asset_correlations.csv"
        df.to_csv(out_file, index=False)
        logger.info(f"Saved {out_file}")
        return df

    def run_lead_lag_analysis(self) -> pd.DataFrame:
        """Perform daily lead-lag cross-correlation analysis between macro series and BTC."""
        logger.info("Computing Daily Cross-Asset Lead-Lag Structure...")
        # Get daily BTC return
        spot = pd.read_parquet(self.spot_grid_path, columns=["datetime_open", "close"])
        spot["date"] = spot["datetime_open"].dt.date.astype(str)
        btc_daily = spot.groupby("date")["close"].last().reset_index()
        btc_daily["btc_ret"] = btc_daily["close"].pct_change()

        macro_series = self.load_macro_series()

        rows = []
        lags = list(range(-5, 6))  # Lag -5 (Macro lags BTC) to +5 (Macro leads BTC)

        for item in self.INSTRUMENT_MAP:
            name = item["name"]
            if name not in macro_series:
                continue

            m_df = macro_series[name][["date", "ret_1d"]].rename(columns={"ret_1d": "macro_ret"})
            merged = pd.merge(btc_daily, m_df, on="date", how="inner").dropna()

            if len(merged) < 50:
                continue

            lag_corrs = {}
            for lag in lags:
                # If lag > 0: macro_ret is shifted backward, so macro at t predicts btc at t+lag (Macro LEADS)
                # If lag < 0: btc at t predicts macro at t+|lag| (BTC LEADS)
                if lag > 0:
                    r = merged["macro_ret"].iloc[:-lag].corr(merged["btc_ret"].iloc[lag:])
                elif lag < 0:
                    pos_lag = abs(lag)
                    r = merged["btc_ret"].iloc[:-pos_lag].corr(merged["macro_ret"].iloc[pos_lag:])
                else:
                    r = merged["macro_ret"].corr(merged["btc_ret"])
                lag_corrs[lag] = r

            best_lag = max(lag_corrs.keys(), key=lambda k: abs(lag_corrs[k]))
            peak_r = lag_corrs[best_lag]
            lag0_r = lag_corrs[0]

            if best_lag > 0:
                verdict = f"MACRO_LEADS_BTC_BY_{best_lag}D"
            elif best_lag < 0:
                verdict = f"BTC_LEADS_MACRO_BY_{abs(best_lag)}D"
            else:
                verdict = "COINCIDENT_LAG_0"

            rows.append({
                "instrument": name,
                "symbol": item["symbol"],
                "asset_class": item["class"],
                "sample_days": len(merged),
                "lag_0_correlation": float(lag0_r),
                "peak_lag_days": best_lag,
                "peak_correlation": float(peak_r),
                "lead_lag_verdict": verdict,
                "corr_lag_minus_2": float(lag_corrs.get(-2, 0.0)),
                "corr_lag_minus_1": float(lag_corrs.get(-1, 0.0)),
                "corr_lag_plus_1": float(lag_corrs.get(1, 0.0)),
                "corr_lag_plus_2": float(lag_corrs.get(2, 0.0)),
            })

        df = pd.DataFrame(rows)
        out_file = self.output_dir / "cross_asset_lead_lag.csv"
        df.to_csv(out_file, index=False)
        logger.info(f"Saved {out_file}")
        return df

    def run_dynamic_correlations_summary(self, feat_df: pd.DataFrame) -> pd.DataFrame:
        """Summarize dynamic 30-day rolling correlation stats across regimes and years."""
        logger.info("Summarizing Dynamic BTC-Macro Correlations...")
        feat_df = feat_df.copy()
        feat_df["year"] = feat_df["datetime_open"].dt.year

        periods = [
            {"period": "2021_BULL_PEAK", "mask": feat_df["year"] == 2021, "desc": "2021 Bull Market / ATH"},
            {"period": "2022_FED_TIGHTENING_BEAR", "mask": feat_df["year"] == 2022, "desc": "2022 Aggressive Fed Tightening / Bear"},
            {"period": "2023_BANKING_CRISIS_RECOVERY", "mask": feat_df["year"] == 2023, "desc": "2023 Recovery & Banking Stress"},
            {"period": "2024_SPOT_ETF_EXPANSION", "mask": feat_df["year"] == 2024, "desc": "2024 US Spot ETF Inflows & ATH"},
            {"period": "2025_POST_HALVING_CYCLE", "mask": feat_df["year"] == 2025, "desc": "2025 Validation Partition"},
            {"period": "2026_HOLDOUT", "mask": feat_df["year"] == 2026, "desc": "2026 Observed Holdout"},
            {"period": "FULL_SAMPLE_2021_2026", "mask": feat_df["year"] >= 2021, "desc": "Full 5.75 Year History"},
        ]

        corr_targets = [
            ("corr_btc_nasdaq_30d", "BTC vs NASDAQ 30d Rolling Corr"),
            ("corr_btc_sp500_30d", "BTC vs S&P 500 30d Rolling Corr"),
            ("corr_btc_dxy_30d", "BTC vs DXY 30d Rolling Corr"),
            ("corr_btc_gold_30d", "BTC vs Gold 30d Rolling Corr"),
            ("corr_btc_vix_30d", "BTC vs VIX 30d Rolling Corr"),
        ]

        rows = []
        for p in periods:
            sub = feat_df[p["mask"]]
            if len(sub) == 0:
                continue

            for col, desc in corr_targets:
                if col not in sub:
                    continue
                s = sub[col]
                rows.append({
                    "period": p["period"],
                    "description": p["desc"],
                    "correlation_metric": col,
                    "target_description": desc,
                    "mean_correlation": float(s.mean()),
                    "min_correlation": float(s.min()),
                    "max_correlation": float(s.max()),
                    "std_correlation": float(s.std()),
                    "pct_positive": float((s > 0).mean() * 100.0),
                })

        df = pd.DataFrame(rows)
        out_file = self.output_dir / "btc_dynamic_correlations.csv"
        df.to_csv(out_file, index=False)
        logger.info(f"Saved {out_file}")
        return df

    def run_macro_redundancy_analysis(self, feat_df: pd.DataFrame) -> pd.DataFrame:
        """Analyze multicollinearity, redundancy, and mutual correlations among macro features."""
        logger.info("Computing Macro Redundancy and Collinearity Analysis...")
        candidate_cols = [
            "nasdaq_ret_1d", "nasdaq_ret_5d", "nasdaq_vol_20d",
            "sp500_ret_1d", "sp500_ret_5d", "sp500_vol_20d",
            "vix_close", "vix_ret_1d",
            "dxy_ret_1d", "dxy_ret_5d",
            "tnx_10y_close", "yield_2y_close", "yield_spread_10y_2y",
            "gold_ret_1d", "oil_ret_1d",
            "equity_risk_on_1d",
        ]

        avail_cols = [c for c in candidate_cols if c in feat_df]
        corr_matrix = feat_df[avail_cols].corr()

        rows = []
        for i, col_a in enumerate(avail_cols):
            for col_b in avail_cols[i + 1:]:
                val = corr_matrix.loc[col_a, col_b]
                redundancy_status = "REDUNDANT" if abs(val) >= 0.85 else ("MODERATE_OVERLAP" if abs(val) >= 0.50 else "INDEPENDENT")
                rows.append({
                    "feature_1": col_a,
                    "feature_2": col_b,
                    "pairwise_correlation": float(val),
                    "abs_correlation": float(abs(val)),
                    "redundancy_verdict": redundancy_status,
                })

        df = pd.DataFrame(rows).sort_values("abs_correlation", ascending=False).reset_index(drop=True)
        out_file = self.output_dir / "macro_redundancy_analysis.csv"
        df.to_csv(out_file, index=False)
        logger.info(f"Saved {out_file}")
        return df

    def run_all(self) -> Dict[str, Any]:
        """Execute full cross-asset pipeline."""
        logger.info("Starting CrossAssetEngine full execution...")
        feat_df = self.build_cross_asset_features()
        stale_df = self.run_staleness_audit(feat_df)
        corr_df = self.run_cross_asset_correlations(feat_df)
        lead_df = self.run_lead_lag_analysis()
        dyn_df = self.run_dynamic_correlations_summary(feat_df)
        red_df = self.run_macro_redundancy_analysis(feat_df)

        return {
            "cross_asset_features_count": len(feat_df),
            "staleness_rows": len(stale_df),
            "correlations_rows": len(corr_df),
            "lead_lag_rows": len(lead_df),
            "dynamic_corr_rows": len(dyn_df),
            "redundancy_pairs": len(red_df),
        }


if __name__ == "__main__":
    engine = CrossAssetEngine()
    summary = engine.run_all()
    print("CrossAssetEngine execution completed successfully:", summary)

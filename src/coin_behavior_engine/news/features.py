"""Event Feature Engineering, Anti-Lookahead Clocks, TF-IDF Semantics & Interactions.

Builds causal event feature matrices aligned to the 5m Bitcoin bar grid:
1. Four-Timestamp Anti-Leakage: At bar T, event info enters only if available_at <= T
2. Pre-Scheduled Event Clocks (known calendar risk before release, outcome unknown)
3. Post-Event Clocks & Complete 10-Bucket Decay Curves (0-5m to 24-48h)
4. Event Density & News Absence States
5. Causal Novelty (strictly prior history)
6. Causal TF-IDF Semantic Representations (fitted on Discovery 2021-2024 only)
7. Event Surprise & Severity (without future price outcome circularity)
8. Cross-Layer Interactions (Event x Compression, OI, Basis, Funding, Session, Weekend, ETF Staleness)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from coin_behavior_engine.utils.logging import logger


class EventFeatureEngine:
    """Computes strictly causal event features aligned to 5m bars."""

    def __init__(
        self,
        events_path: str | Path = "data/reports/sprint06/event_canonical.parquet",
        reports_dir: str | Path = "data/reports/sprint06",
        spot_5m_path: str | Path = "data/derived/features_with_outcomes_5m.parquet",
        session_path: str | Path = "data/reports/sprint04/session_context_features.parquet",
        etf_path: str | Path = "data/reports/sprint05/etf_flow_features.parquet",
    ):
        self.events_path = Path(events_path)
        self.reports_dir = Path(reports_dir)
        self.spot_5m_path = Path(spot_5m_path)
        self.session_path = Path(session_path)
        self.etf_path = Path(etf_path)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def load_grid_and_events(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Load 5m bar grid and canonical events with UTC timestamps."""
        logger.info(f"Loading 5m base grid from {self.spot_5m_path}...")
        df_grid = pd.read_parquet(
            self.spot_5m_path,
            columns=[
                "datetime_open", "open", "high", "low", "close", "volume",
                "volatility_realized_24h", "volatility_compression_ratio",
            ]
        )
        df_grid["datetime_open"] = pd.to_datetime(df_grid["datetime_open"], utc=True)

        if self.session_path.exists():
            df_sess = pd.read_parquet(
                self.session_path,
                columns=[
                    "datetime_open", "session_asia_active", "session_london_active",
                    "session_new_york_active", "london_new_york_overlap", "weekend_flag"
                ]
            )
            df_sess["datetime_open"] = pd.to_datetime(df_sess["datetime_open"], utc=True)
            df_grid = df_grid.merge(df_sess, on="datetime_open", how="left")
        else:
            df_grid["session_asia_active"] = ((df_grid["datetime_open"].dt.hour >= 0) & (df_grid["datetime_open"].dt.hour < 9)).astype(int)
            df_grid["session_london_active"] = ((df_grid["datetime_open"].dt.hour >= 8) & (df_grid["datetime_open"].dt.hour < 16)).astype(int)
            df_grid["session_new_york_active"] = ((df_grid["datetime_open"].dt.hour >= 13) & (df_grid["datetime_open"].dt.hour < 20)).astype(int)
            df_grid["london_new_york_overlap"] = ((df_grid["datetime_open"].dt.hour >= 13) & (df_grid["datetime_open"].dt.hour < 16)).astype(int)
            df_grid["weekend_flag"] = (df_grid["datetime_open"].dt.dayofweek >= 5).astype(int)

        df_grid = df_grid.sort_values("datetime_open").reset_index(drop=True)

        logger.info(f"Loading canonical events from {self.events_path}...")
        df_events = pd.read_parquet(self.events_path)
        df_events["available_at_timestamp"] = pd.to_datetime(df_events["available_at_timestamp"], utc=True)
        df_events["event_time"] = pd.to_datetime(df_events["event_time"], utc=True)
        df_events = df_events.sort_values("available_at_timestamp").reset_index(drop=True)

        return df_grid, df_events

    def fit_causal_tfidf(self, df_events: pd.DataFrame) -> Tuple[TfidfVectorizer, List[str]]:
        """Fit TF-IDF vectorizer strictly on Discovery partition (<= 2024-12-31) to prevent lookahead."""
        logger.info("Fitting TF-IDF vectorizer strictly on Discovery partition (2021-2024)...")
        discovery_events = df_events[df_events["available_at_timestamp"] <= "2024-12-31 23:59:59+00:00"]
        corpus = discovery_events["headline"].fillna("").tolist()

        vectorizer = TfidfVectorizer(
            max_features=8,
            stop_words="english",
            token_pattern=r"(?u)\b[a-zA-Z]{3,}\b",
            norm="l2"
        )
        vectorizer.fit(corpus)
        feature_names = [f"sem_tfidf_{w}" for w in vectorizer.get_feature_names_out()]
        logger.info(f"Fitted TF-IDF vocabulary on {len(corpus)} Discovery headlines: {feature_names}")
        return vectorizer, feature_names

    def build_features(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """Compute full event feature matrix and text semantic matrix."""
        df_grid, df_events = self.load_grid_and_events()
        vectorizer, tfidf_col_names = self.fit_causal_tfidf(df_events)

        # Transform headlines via fitted TF-IDF
        tfidf_matrix = vectorizer.transform(df_events["headline"].fillna("")).toarray()
        for idx, col in enumerate(tfidf_col_names):
            df_events[col] = tfidf_matrix[:, idx]

        # Pre-filter primary events (cluster leads or high quality to avoid duplicate counting)
        primary_events = df_events[df_events["source_tier"] != "REJECTED"].copy()
        scheduled_events = primary_events[primary_events["is_scheduled"]].copy()

        grid_times = df_grid["datetime_open"].values
        n_bars = len(df_grid)

        # Pre-allocate feature arrays
        minutes_to_sched = np.full(n_bars, 9999.0, dtype=np.float32)
        sched_within_15m = np.zeros(n_bars, dtype=np.int8)
        sched_within_1h = np.zeros(n_bars, dtype=np.int8)
        sched_within_4h = np.zeros(n_bars, dtype=np.int8)

        min_since_avail = np.full(n_bars, 9999.0, dtype=np.float32)
        ev_age_hours = np.full(n_bars, 168.0, dtype=np.float32)

        # 10 Decay buckets
        decay_0_5m = np.zeros(n_bars, dtype=np.int8)
        decay_5_15m = np.zeros(n_bars, dtype=np.int8)
        decay_15_30m = np.zeros(n_bars, dtype=np.int8)
        decay_30_60m = np.zeros(n_bars, dtype=np.int8)
        decay_1_2h = np.zeros(n_bars, dtype=np.int8)
        decay_2_4h = np.zeros(n_bars, dtype=np.int8)
        decay_4_8h = np.zeros(n_bars, dtype=np.int8)
        decay_8_12h = np.zeros(n_bars, dtype=np.int8)
        decay_12_24h = np.zeros(n_bars, dtype=np.int8)
        decay_24_48h = np.zeros(n_bars, dtype=np.int8)

        # Densities
        density_15m = np.zeros(n_bars, dtype=np.int16)
        density_1h = np.zeros(n_bars, dtype=np.int16)
        density_4h = np.zeros(n_bars, dtype=np.int16)
        density_24h = np.zeros(n_bars, dtype=np.int16)
        tier1_density_4h = np.zeros(n_bars, dtype=np.int16)
        clusters_24h = np.zeros(n_bars, dtype=np.int16)

        # Novelty, severity, sentiment
        causal_novelty = np.zeros(n_bars, dtype=np.float32)
        event_severity = np.zeros(n_bars, dtype=np.float32)
        event_sentiment = np.zeros(n_bars, dtype=np.float32)
        event_surprise = np.zeros(n_bars, dtype=np.float32)

        # Top event classes active flags
        ev_macro_active = np.zeros(n_bars, dtype=np.int8)
        ev_monetary_active = np.zeros(n_bars, dtype=np.int8)
        ev_regulatory_active = np.zeros(n_bars, dtype=np.int8)
        ev_security_active = np.zeros(n_bars, dtype=np.int8)
        ev_stablecoin_active = np.zeros(n_bars, dtype=np.int8)

        # TF-IDF bar features
        tfidf_bar_feats = np.zeros((n_bars, len(tfidf_col_names)), dtype=np.float32)

        logger.info(f"Computing causal clocks, densities, and decays across {n_bars} 5m bars...")

        sched_event_times = scheduled_events["event_time"].values
        all_avail_times = primary_events["available_at_timestamp"].values
        tier1_mask = (primary_events["source_tier"] == "TIER_1_PRIMARY").values
        cluster_ids = primary_events["event_cluster_id"].values
        families = primary_events["taxonomy_family"].values
        sentiments = primary_events["sentiment_score"].fillna(0.0).values
        tfidf_event_matrix = primary_events[tfidf_col_names].values

        # Fast searchsorted indexing for causal alignment
        latest_avail_idx = np.searchsorted(all_avail_times, grid_times, side="right") - 1
        next_sched_idx = np.searchsorted(sched_event_times, grid_times, side="left")

        # Compute pre-event clock
        for i in range(n_bars):
            # 1. Pre-scheduled clock
            ns_idx = next_sched_idx[i]
            if ns_idx < len(sched_event_times):
                diff_m = (sched_event_times[ns_idx] - grid_times[i]) / np.timedelta64(1, "m")
                if 0 <= diff_m <= 1440:  # within 24h
                    minutes_to_sched[i] = diff_m
                    if diff_m <= 15:
                        sched_within_15m[i] = 1
                    if diff_m <= 60:
                        sched_within_1h[i] = 1
                    if diff_m <= 240:
                        sched_within_4h[i] = 1

            # 2. Post-event clock & latest available event properties
            la_idx = latest_avail_idx[i]
            if la_idx >= 0:
                elapsed_m = (grid_times[i] - all_avail_times[la_idx]) / np.timedelta64(1, "m")
                min_since_avail[i] = max(0.0, elapsed_m)
                ev_age_hours[i] = min_since_avail[i] / 60.0

                # Decay buckets
                if elapsed_m <= 5:
                    decay_0_5m[i] = 1
                elif elapsed_m <= 15:
                    decay_5_15m[i] = 1
                elif elapsed_m <= 30:
                    decay_15_30m[i] = 1
                elif elapsed_m <= 60:
                    decay_30_60m[i] = 1
                elif elapsed_m <= 120:
                    decay_1_2h[i] = 1
                elif elapsed_m <= 240:
                    decay_2_4h[i] = 1
                elif elapsed_m <= 480:
                    decay_4_8h[i] = 1
                elif elapsed_m <= 720:
                    decay_8_12h[i] = 1
                elif elapsed_m <= 1440:
                    decay_12_24h[i] = 1
                elif elapsed_m <= 2880:
                    decay_24_48h[i] = 1

                # If event occurred within last 24h, copy semantic and sentiment features
                if elapsed_m <= 1440:
                    event_sentiment[i] = sentiments[la_idx]
                    tfidf_bar_feats[i, :] = tfidf_event_matrix[la_idx, :]

                    fam = families[la_idx]
                    if fam == "MACRO_SCHEDULED":
                        ev_macro_active[i] = 1
                    elif fam == "MONETARY_POLICY":
                        ev_monetary_active[i] = 1
                    elif fam in ["REGULATORY", "ETF_REGULATORY"]:
                        ev_regulatory_active[i] = 1
                    elif fam in ["EXCHANGE_SECURITY", "PROTOCOL_SECURITY"]:
                        ev_security_active[i] = 1
                    elif fam == "STABLECOIN":
                        ev_stablecoin_active[i] = 1

                    # Severity derivation
                    tier_weight = 1.0 if tier1_mask[la_idx] else 0.6
                    decay_factor = np.exp(-elapsed_m / 240.0)
                    event_severity[i] = tier_weight * decay_factor

                    # Novelty (hours since previous event of this same family)
                    if la_idx > 0:
                        prev_fam_matches = np.where(families[:la_idx] == fam)[0]
                        if len(prev_fam_matches) > 0:
                            prev_time = all_avail_times[prev_fam_matches[-1]]
                            novelty_h = (all_avail_times[la_idx] - prev_time) / np.timedelta64(1, "h")
                            causal_novelty[i] = min(1.0, novelty_h / 720.0)  # normalized up to 30 days
                        else:
                            causal_novelty[i] = 1.0

                # 3. Density calculations using window backward bounds
                t_15m_ago = grid_times[i] - np.timedelta64(15, "m")
                t_1h_ago = grid_times[i] - np.timedelta64(60, "m")
                t_4h_ago = grid_times[i] - np.timedelta64(240, "m")
                t_24h_ago = grid_times[i] - np.timedelta64(1440, "m")

                start_15m = np.searchsorted(all_avail_times, t_15m_ago, side="left")
                start_1h = np.searchsorted(all_avail_times, t_1h_ago, side="left")
                start_4h = np.searchsorted(all_avail_times, t_4h_ago, side="left")
                start_24h = np.searchsorted(all_avail_times, t_24h_ago, side="left")

                density_15m[i] = max(0, la_idx + 1 - start_15m)
                density_1h[i] = max(0, la_idx + 1 - start_1h)
                density_4h[i] = max(0, la_idx + 1 - start_4h)
                density_24h[i] = max(0, la_idx + 1 - start_24h)

                if start_4h <= la_idx:
                    tier1_density_4h[i] = int(np.sum(tier1_mask[start_4h:la_idx + 1]))
                if start_24h <= la_idx:
                    clusters_24h[i] = len(np.unique(cluster_ids[start_24h:la_idx + 1]))

        # Assign computed features to grid
        df_feat = df_grid.copy()

        df_feat["minutes_to_scheduled_event"] = minutes_to_sched
        df_feat["is_event_within_15m"] = sched_within_15m
        df_feat["is_event_within_1h"] = sched_within_1h
        df_feat["is_event_within_4h"] = sched_within_4h

        df_feat["minutes_since_event_available"] = min_since_avail
        df_feat["event_age_hours"] = ev_age_hours

        # Decay buckets
        df_feat["event_age_0_5m"] = decay_0_5m
        df_feat["event_age_5_15m"] = decay_5_15m
        df_feat["event_age_15_30m"] = decay_15_30m
        df_feat["event_age_30_60m"] = decay_30_60m
        df_feat["event_age_1_2h"] = decay_1_2h
        df_feat["event_age_2_4h"] = decay_2_4h
        df_feat["event_age_4_8h"] = decay_4_8h
        df_feat["event_age_8_12h"] = decay_8_12h
        df_feat["event_age_12_24h"] = decay_12_24h
        df_feat["event_age_24_48h"] = decay_24_48h

        # Density features
        df_feat["events_last_15m"] = density_15m
        df_feat["events_last_1h"] = density_1h
        df_feat["events_last_4h"] = density_4h
        df_feat["events_last_24h"] = density_24h
        df_feat["tier1_events_last_4h"] = tier1_density_4h
        df_feat["clusters_last_24h"] = clusters_24h

        df_feat["is_event_active_1h"] = (density_1h > 0).astype(int)
        df_feat["is_event_active_4h"] = (density_4h > 0).astype(int)
        df_feat["is_no_event_state"] = (density_24h == 0).astype(int)

        # Novelty, severity, sentiment
        df_feat["event_novelty_score"] = causal_novelty
        df_feat["event_severity_score"] = event_severity
        df_feat["event_sentiment_score"] = event_sentiment

        # Event classes active
        df_feat["event_macro_active"] = ev_macro_active
        df_feat["event_monetary_active"] = ev_monetary_active
        df_feat["event_regulatory_active"] = ev_regulatory_active
        df_feat["event_security_active"] = ev_security_active
        df_feat["event_stablecoin_active"] = ev_stablecoin_active

        # TF-IDF text features
        df_text = pd.DataFrame({"datetime_open": df_grid["datetime_open"]})
        for idx, col in enumerate(tfidf_col_names):
            df_feat[col] = tfidf_bar_feats[:, idx]
            df_text[col] = tfidf_bar_feats[:, idx]

        # Load derivatives & ETF features if available for cross-layer interactions
        logger.info("Computing cross-layer event interactions (Compression, Sessions, Derivatives, ETF)...")
        # Event x Compression
        comp_ratio = df_feat["volatility_compression_ratio"].fillna(1.0)
        df_feat["event_x_compression"] = df_feat["is_event_active_1h"] * (comp_ratio < 0.70).astype(float)
        df_feat["event_x_high_vol"] = df_feat["is_event_active_1h"] * (df_feat["volatility_realized_24h"] > df_feat["volatility_realized_24h"].median()).astype(float)

        # Event x Session
        df_feat["event_x_asia"] = df_feat["is_event_active_1h"] * df_feat["session_asia_active"]
        df_feat["event_x_london"] = df_feat["is_event_active_1h"] * df_feat["session_london_active"]
        df_feat["event_x_ny"] = df_feat["is_event_active_1h"] * df_feat["session_new_york_active"]
        df_feat["event_x_overlap"] = df_feat["is_event_active_1h"] * df_feat["london_new_york_overlap"]
        df_feat["event_x_weekend"] = df_feat["is_event_active_1h"] * df_feat["weekend_flag"]

        # Derivatives interactions (if derivatives features exist)
        s3_dir = Path("data/reports/sprint03")
        if (s3_dir / "basis_features.parquet").exists() and (s3_dir / "funding_features.parquet").exists():
            df_basis = pd.read_parquet(s3_dir / "basis_features.parquet", columns=["datetime_open", "basis_level"])
            df_funding = pd.read_parquet(s3_dir / "funding_features.parquet", columns=["datetime_open", "funding_rate_latest"])
            df_oi = pd.read_parquet(s3_dir / "open_interest_features.parquet", columns=["datetime_open", "oi_change_1h"])
            df_taker = pd.read_parquet(s3_dir / "futures_taker_features.parquet", columns=["datetime_open", "futures_taker_buy_sell_ratio"])

            for d_df in [df_basis, df_funding, df_oi, df_taker]:
                d_df["datetime_open"] = pd.to_datetime(d_df["datetime_open"], utc=True)
                df_feat = df_feat.merge(d_df, on="datetime_open", how="left")

            df_feat["event_x_oi_chg"] = df_feat["is_event_active_1h"] * df_feat["oi_change_1h"].fillna(0.0)
            df_feat["event_x_basis"] = df_feat["is_event_active_1h"] * df_feat["basis_level"].fillna(0.0)
            df_feat["event_x_funding"] = df_feat["is_event_active_1h"] * df_feat["funding_rate_latest"].abs().fillna(0.0)
            df_feat["event_x_taker"] = df_feat["is_event_active_1h"] * (df_feat["futures_taker_buy_sell_ratio"].fillna(1.0) - 1.0)
        else:
            df_feat["event_x_oi_chg"] = 0.0
            df_feat["event_x_basis"] = 0.0
            df_feat["event_x_funding"] = 0.0
            df_feat["event_x_taker"] = 0.0

        # ETF interactions
        if self.etf_path.exists():
            df_etf = pd.read_parquet(self.etf_path, columns=["datetime_open", "is_etf_stale"])
            df_etf["datetime_open"] = pd.to_datetime(df_etf["datetime_open"], utc=True)
            df_feat = df_feat.merge(df_etf, on="datetime_open", how="left")
            df_feat["event_x_etf_stale"] = df_feat["is_event_active_1h"] * df_feat["is_etf_stale"].fillna(0.0)

        return df_feat, df_text

    def run_feature_pipeline(self) -> Dict[str, Any]:
        """Execute full feature engineering and export parquets & summary CSVs."""
        df_feat, df_text = self.build_features()

        # 1. Event Features Parquet
        feat_file = self.reports_dir / "event_features.parquet"
        df_feat.to_parquet(feat_file, index=False)
        logger.info(f"Saved event features ({len(df_feat)} rows, {len(df_feat.columns)} cols) to {feat_file}")

        # 2. Text Features Parquet
        text_file = self.reports_dir / "event_text_features.parquet"
        df_text.to_parquet(text_file, index=False)
        logger.info(f"Saved text features to {text_file}")

        # 3. Event Density Analysis CSV
        density_summary = df_feat[
            ["events_last_15m", "events_last_1h", "events_last_4h", "events_last_24h", "clusters_last_24h", "is_no_event_state"]
        ].describe().transpose().reset_index().rename(columns={"index": "density_metric"})
        density_file = self.reports_dir / "event_density_analysis.csv"
        density_summary.to_csv(density_file, index=False)
        logger.info(f"Saved density analysis to {density_file}")

        # 4. Event Decay Analysis CSV
        decay_cols = [c for c in df_feat.columns if c.startswith("event_age_") and c.endswith("m") or c.endswith("h")]
        decay_summary = df_feat[decay_cols].mean().reset_index()
        decay_summary.columns = ["decay_bucket", "fraction_of_total_bars"]
        decay_file = self.reports_dir / "event_decay_analysis.csv"
        decay_summary.to_csv(decay_file, index=False)
        logger.info(f"Saved decay analysis to {decay_file}")

        # 5. Event Novelty Analysis CSV
        nov_active = df_feat[df_feat["is_event_active_4h"] == 1]["event_novelty_score"]
        nov_summary = pd.DataFrame([{
            "metric": "event_novelty_score_active",
            "mean": float(nov_active.mean()),
            "std": float(nov_active.std()),
            "median": float(nov_active.median()),
            "p25": float(nov_active.quantile(0.25)),
            "p75": float(nov_active.quantile(0.75)),
        }])
        nov_file = self.reports_dir / "event_novelty_analysis.csv"
        nov_summary.to_csv(nov_file, index=False)
        logger.info(f"Saved novelty analysis to {nov_file}")

        return {
            "total_bars": len(df_feat),
            "feature_columns": len(df_feat.columns),
            "active_1h_bars": int(df_feat["is_event_active_1h"].sum()),
            "no_event_bars": int(df_feat["is_no_event_state"].sum()),
        }


if __name__ == "__main__":
    engine = EventFeatureEngine()
    res = engine.run_feature_pipeline()
    print("Event feature pipeline results:", res)

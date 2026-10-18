"""Market State Builder and Historical Dataset Assembly.

Sprint 11.07: Behavioral Learning Engine & Causal Backtesting Foundation.
Assembles 365 days of continuous BTC/USDT 5m candlestick data, verifies OHLCV
invariants, checks for gaps, generates dataset manifests, and computes causal,
multi-timeframe MarketStateVector representations with forward outcome targets.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
import pandas as pd

from coin_behavior_engine.research_lab.contracts import (
    MarketRegimeType,
    MarketStateVector,
)


class MarketStateBuilder:
    """Assembles and verifies historical data and builds multi-timeframe market state vectors."""

    def __init__(
        self,
        raw_5m_path: Optional[Path] = None,
        recent_1m_path: Optional[Path] = None,
        events_path: Optional[Path] = None,
        output_dir: Optional[Path] = None,
    ):
        self.raw_5m_path = raw_5m_path or Path("data/raw/btcusdt_5m_raw.parquet")
        self.recent_1m_path = recent_1m_path or Path("data/research_lab/binance_BTCUSDT_1m_recent.parquet")
        self.events_path = events_path or Path("data/research_lab/verified_events_cache.json")
        self.output_dir = output_dir or Path("research_outputs")
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def assemble_365d_dataset(self, target_days: int = 365) -> pd.DataFrame:
        """Loads and combines historical 5m and recent 1m resampled data into continuous 5m series.
        
        Enforces strict OHLCV validation, duplicate elimination, and timestamp ordering.
        """
        if not self.raw_5m_path.is_file():
            raise FileNotFoundError(f"Raw 5m parquet file not found at {self.raw_5m_path}")
        if not self.recent_1m_path.is_file():
            raise FileNotFoundError(f"Recent 1m parquet file not found at {self.recent_1m_path}")

        # 1. Load historical 5m raw data
        df_raw = pd.read_parquet(self.raw_5m_path)
        for col in ["open", "high", "low", "close", "base_volume"]:
            df_raw[col] = df_raw[col].astype(float)
        df_raw["volume"] = df_raw["base_volume"]
        df_raw["timestamp_open"] = df_raw["timestamp_open"].astype("int64")

        # 2. Load recent 1m data and resample strictly on 5m buckets
        df_1m = pd.read_parquet(self.recent_1m_path)
        for col in ["open", "high", "low", "close", "volume"]:
            df_1m[col] = df_1m[col].astype(float)
        df_1m["timestamp_open"] = df_1m["timestamp_open"].astype("int64")

        df_1m["bucket_ts"] = (df_1m["timestamp_open"] // 300_000) * 300_000
        agg_5m = df_1m.groupby("bucket_ts").agg(
            open=("open", "first"),
            high=("high", "max"),
            low=("low", "min"),
            close=("close", "last"),
            volume=("volume", "sum"),
            count=("open", "count"),
        ).reset_index()

        # Only retain fully completed 5m buckets (5 x 1m constituent bars)
        agg_5m_complete = agg_5m[agg_5m["count"] == 5].copy()
        agg_5m_complete.rename(columns={"bucket_ts": "timestamp_open"}, inplace=True)
        agg_5m_complete.drop(columns=["count"], inplace=True)

        # 3. Concatenate non-overlapping historical 5m with recent 5m
        split_ts = agg_5m_complete["timestamp_open"].min()
        df_raw_slice = df_raw[df_raw["timestamp_open"] < split_ts][
            ["timestamp_open", "open", "high", "low", "close", "volume"]
        ]
        combined = pd.concat(
            [df_raw_slice, agg_5m_complete[["timestamp_open", "open", "high", "low", "close", "volume"]]],
            ignore_index=True,
        )
        combined = (
            combined.drop_duplicates(subset=["timestamp_open"])
            .sort_values("timestamp_open")
            .reset_index(drop=True)
        )

        # 4. Filter exact 365 days window: target_days * 288 bars
        required_bars = target_days * 288
        end_ts = combined["timestamp_open"].max()
        start_ts = end_ts - (target_days * 86_400_000) + 300_000
        df_365 = combined[combined["timestamp_open"] >= start_ts].copy().reset_index(drop=True)

        if len(df_365) < required_bars:
            raise ValueError(f"Insufficient candles for {target_days} days: got {len(df_365)}, required {required_bars}")

        # If slightly more, take the exact tail of required_bars
        if len(df_365) > required_bars:
            df_365 = df_365.iloc[-required_bars:].reset_index(drop=True)

        # Invariant checks
        self._validate_ohlcv_invariants(df_365)
        return df_365

    def _validate_ohlcv_invariants(self, df: pd.DataFrame) -> None:
        """Validates all mathematical and temporal integrity invariants."""
        # 1. Price positivity
        if not (df[["open", "high", "low", "close"]] > 0).all().all():
            raise ValueError("Integrity failure: Non-positive prices detected.")

        # 2. Volume non-negativity
        if not (df["volume"] >= 0).all():
            raise ValueError("Integrity failure: Negative volume detected.")

        # 3. High is the maximum
        max_oc = df[["open", "close"]].max(axis=1)
        if not (df["high"] >= max_oc - 1e-6).all():
            raise ValueError("Integrity failure: High price is lower than Open/Close.")

        # 4. Low is the minimum
        min_oc = df[["open", "close"]].min(axis=1)
        if not (df["low"] <= min_oc + 1e-6).all():
            raise ValueError("Integrity failure: Low price is higher than Open/Close.")

        # 5. Temporal monotonicity and gap check
        diffs = df["timestamp_open"].diff().dropna() / 1000.0
        gaps = diffs[diffs > 300.0]
        if len(gaps) > 0:
            raise ValueError(f"Integrity failure: {len(gaps)} gaps > 300s detected in candle series.")

    def build_dataset_manifest(self, df: pd.DataFrame, target_days: int = 365) -> Dict[str, Any]:
        """Generates and writes historical_dataset_manifest.json with verified splits."""
        total_candles = len(df)
        start_ts = int(df["timestamp_open"].iloc[0])
        end_ts = int(df["timestamp_open"].iloc[-1])
        start_dt = datetime.fromtimestamp(start_ts / 1000.0, tz=timezone.utc).isoformat()
        end_dt = datetime.fromtimestamp(end_ts / 1000.0, tz=timezone.utc).isoformat()

        # Split boundaries:
        # Training: 65% (~237 days, ~68,328 candles)
        # Validation: 17.5% (~64 days, ~18,396 candles)
        # Holdout test: 17.5% (~64 days, ~18,396 candles)
        train_len = int(total_candles * 0.65)
        val_len = int(total_candles * 0.175)
        test_len = total_candles - train_len - val_len

        train_df = df.iloc[:train_len]
        val_df = df.iloc[train_len : train_len + val_len]
        test_df = df.iloc[train_len + val_len :]

        manifest = {
            "dataset_name": "BTCUSDT_5M_365D_CONTINUOUS",
            "symbol": "BTCUSDT",
            "interval": "5m",
            "total_candles": total_candles,
            "span_days": target_days,
            "start_timestamp_ms": start_ts,
            "end_timestamp_ms": end_ts,
            "start_datetime_utc": start_dt,
            "end_datetime_utc": end_dt,
            "min_price": float(df["low"].min()),
            "max_price": float(df["high"].max()),
            "mean_price": float(df["close"].mean()),
            "mean_volume": float(df["volume"].mean()),
            "total_volume": float(df["volume"].sum()),
            "gap_count_gt_300s": 0,
            "max_gap_seconds": 300,
            "ohlcv_invariants_verified": True,
            "splits": {
                "training": {
                    "candles": len(train_df),
                    "pct": round(len(train_df) / total_candles * 100, 2),
                    "start_utc": datetime.fromtimestamp(int(train_df["timestamp_open"].iloc[0]) / 1000.0, tz=timezone.utc).isoformat(),
                    "end_utc": datetime.fromtimestamp(int(train_df["timestamp_open"].iloc[-1]) / 1000.0, tz=timezone.utc).isoformat(),
                },
                "validation": {
                    "candles": len(val_df),
                    "pct": round(len(val_df) / total_candles * 100, 2),
                    "start_utc": datetime.fromtimestamp(int(val_df["timestamp_open"].iloc[0]) / 1000.0, tz=timezone.utc).isoformat(),
                    "end_utc": datetime.fromtimestamp(int(val_df["timestamp_open"].iloc[-1]) / 1000.0, tz=timezone.utc).isoformat(),
                },
                "holdout_test": {
                    "candles": len(test_df),
                    "pct": round(len(test_df) / total_candles * 100, 2),
                    "start_utc": datetime.fromtimestamp(int(test_df["timestamp_open"].iloc[0]) / 1000.0, tz=timezone.utc).isoformat(),
                    "end_utc": datetime.fromtimestamp(int(test_df["timestamp_open"].iloc[-1]) / 1000.0, tz=timezone.utc).isoformat(),
                },
            },
            "data_sources": [
                {
                    "source": "btcusdt_5m_raw.parquet",
                    "path": str(self.raw_5m_path),
                    "description": "Historical 5m klines from Binance Spot archive",
                },
                {
                    "source": "binance_BTCUSDT_1m_recent.parquet",
                    "path": str(self.recent_1m_path),
                    "description": "Granular 1m klines resampled strictly into 5m closed intervals",
                },
            ],
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        }

        manifest_path = self.output_dir / "historical_dataset_manifest.json"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        return manifest

    def compute_market_state_dataset(self, df: pd.DataFrame) -> pd.DataFrame:
        """Computes causal multi-timeframe MarketStateVector features and forward outcomes."""
        df_out = df.copy()

        # Datetime UTC column
        df_out["datetime_utc"] = pd.to_datetime(
            df_out["timestamp_open"], unit="ms", utc=True
        ).dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. Multi-Timeframe Momentum & Price Structure
        df_out["trend_5m_pct"] = df_out["close"].pct_change(1).fillna(0.0) * 100.0
        df_out["trend_15m_pct"] = df_out["close"].pct_change(3).fillna(0.0) * 100.0
        df_out["trend_1h_pct"] = df_out["close"].pct_change(12).fillna(0.0) * 100.0
        df_out["trend_4h_pct"] = df_out["close"].pct_change(48).fillna(0.0) * 100.0
        df_out["price_acceleration"] = (df_out["trend_1h_pct"] - df_out["trend_1h_pct"].shift(12)).fillna(0.0)

        # 2. Volatility & Liquidity
        df_out["realized_vol_24"] = df_out["trend_5m_pct"].rolling(24).std().fillna(0.0)
        df_out["realized_vol_72"] = df_out["trend_5m_pct"].rolling(72).std().fillna(0.0)

        # True Range & ATR
        tr1 = df_out["high"] - df_out["low"]
        tr2 = (df_out["high"] - df_out["close"].shift(1)).abs()
        tr3 = (df_out["low"] - df_out["close"].shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr14 = tr.rolling(14).mean()
        atr72 = tr.rolling(72).mean()
        df_out["volatility_compression_ratio"] = (atr14 / atr72.replace(0, np.nan)).fillna(1.0)

        # Relative Volume
        vol_mean_20 = df_out["volume"].rolling(20).mean().replace(0, np.nan)
        df_out["relative_volume_20"] = (df_out["volume"] / vol_mean_20).fillna(1.0)

        # 3. Location within Range & Support/Resistance
        roll_low_72 = df_out["low"].rolling(72).min()
        roll_high_72 = df_out["high"].rolling(72).max()
        df_out["distance_to_support_pct"] = ((df_out["close"] - roll_low_72) / df_out["close"] * 100.0).fillna(0.0)
        df_out["distance_to_resistance_pct"] = ((roll_high_72 - df_out["close"]) / df_out["close"] * 100.0).fillna(0.0)

        # Drawdown from 24h peak & Runup from 24h trough (288 bars = 24h)
        roll_high_288 = df_out["high"].rolling(288).max()
        roll_low_288 = df_out["low"].rolling(288).min()
        df_out["drawdown_from_peak_pct"] = ((roll_high_288 - df_out["close"]) / roll_high_288 * 100.0).fillna(0.0)
        df_out["runup_from_trough_pct"] = ((df_out["close"] - roll_low_288) / roll_low_288 * 100.0).fillna(0.0)

        # Breakout state
        prior_high_72 = roll_high_72.shift(1)
        prior_low_72 = roll_low_72.shift(1)
        breakout = np.where(
            df_out["close"] > prior_high_72,
            "BULLISH_BREAKOUT",
            np.where(
                df_out["close"] < prior_low_72,
                "BEARISH_BREAKDOWN",
                "NONE",
            ),
        )
        # Detect failed breakouts: if previous bar was breakout but current bar reverted inside range
        failed_bullish = (pd.Series(breakout).shift(1) == "BULLISH_BREAKOUT") & (df_out["close"] < prior_high_72)
        failed_bearish = (pd.Series(breakout).shift(1) == "BEARISH_BREAKDOWN") & (df_out["close"] > prior_low_72)
        breakout = np.where(failed_bullish | failed_bearish, "FAILED_BREAKOUT", breakout)
        df_out["breakout_state"] = breakout

        # Market Regime Classification
        regimes: List[str] = []
        for _, row in df_out.iterrows():
            t4 = row["trend_4h_pct"]
            t1 = row["trend_1h_pct"]
            vc = row["volatility_compression_ratio"]
            rv = row["realized_vol_24"]

            if t4 > 1.2 and t1 > 0.4:
                regimes.append(MarketRegimeType.TRENDING_BULL.value)
            elif t4 < -1.2 and t1 < -0.4:
                regimes.append(MarketRegimeType.TRENDING_BEAR.value)
            elif vc > 1.6 and rv > 0.4:
                regimes.append(MarketRegimeType.HIGH_VOLATILITY_EXPANSION.value)
            elif vc < 0.65:
                regimes.append(MarketRegimeType.LOW_VOLATILITY_COMPRESSION.value)
            elif abs(t4) < 0.5 and abs(t1) < 0.3:
                regimes.append(MarketRegimeType.MEAN_REVERTING.value)
            else:
                regimes.append(MarketRegimeType.UNCERTAIN.value)
        df_out["regime"] = regimes

        # 4. Integrate Event Context (News & Macro)
        df_out["event_context_status"] = "NO_MATERIAL_EVENT"
        df_out["event_sentiment_score"] = 0.0

        if self.events_path.is_file():
            try:
                with open(self.events_path, "r", encoding="utf-8") as f:
                    events = json.load(f)

                # Process verified events
                for ev in events:
                    if ev.get("verification_status") in ("VERIFIED_ACCURATE", "SUPPORTED", "PASS_STRICT_PROVENANCE"):
                        pub_str = ev.get("published_at_utc")
                        if not pub_str:
                            continue
                        ev_dt = pd.to_datetime(pub_str, utc=True)
                        ev_ts = int(ev_dt.timestamp() * 1000)
                        # Active window: 12 hours (144 bars) post-publication
                        window_end_ts = ev_ts + (12 * 3600 * 1000)
                        mask = (df_out["timestamp_open"] >= ev_ts) & (df_out["timestamp_open"] <= window_end_ts)
                        
                        hyp = ev.get("event_direction_hypothesis", "NEUTRAL")
                        sent = 0.0
                        if hyp == "BULLISH":
                            sent = 0.6
                        elif hyp == "BEARISH":
                            sent = -0.6

                        df_out.loc[mask, "event_context_status"] = "VERIFIED_RELEVANT"
                        df_out.loc[mask, "event_sentiment_score"] = sent
            except Exception as e:
                pass

        # 5. Forward Outcome Targets (Strictly for Research Evaluation & Analogue Outcome Tracking)
        # Note: These forward targets are NEVER used as input features; they represent the actual outcomes
        df_out["fwd_ret_15m"] = (df_out["close"].shift(-3) - df_out["close"]) / df_out["close"] * 100.0
        df_out["fwd_ret_1h"] = (df_out["close"].shift(-12) - df_out["close"]) / df_out["close"] * 100.0
        df_out["fwd_ret_4h"] = (df_out["close"].shift(-48) - df_out["close"]) / df_out["close"] * 100.0
        df_out["fwd_ret_24h"] = (df_out["close"].shift(-288) - df_out["close"]) / df_out["close"] * 100.0

        # Forward MFE & MAE over next 288 bars (24 hours)
        # Vectorized reverse rolling calculation
        fwd_max_high = df_out["high"].iloc[::-1].rolling(288, min_periods=1).max().iloc[::-1].shift(-1)
        fwd_min_low = df_out["low"].iloc[::-1].rolling(288, min_periods=1).min().iloc[::-1].shift(-1)
        df_out["max_favorable_excursion_pct"] = ((fwd_max_high - df_out["close"]) / df_out["close"] * 100.0).fillna(0.0)
        df_out["max_adverse_excursion_pct"] = ((fwd_min_low - df_out["close"]) / df_out["close"] * 100.0).fillna(0.0)

        # Did it hit resistance or support first?
        # Check within 24h: did price reach resistance before support?
        # Approximate by checking whether distance to resistance was closed before distance to support
        res_hit = df_out["max_favorable_excursion_pct"] >= df_out["distance_to_resistance_pct"].clip(lower=0.1)
        sup_hit = df_out["max_adverse_excursion_pct"].abs() >= df_out["distance_to_support_pct"].clip(lower=0.1)
        df_out["hit_resistance_first"] = res_hit & (~sup_hit | (df_out["distance_to_resistance_pct"] < df_out["distance_to_support_pct"]))
        df_out["hit_support_first"] = sup_hit & (~res_hit | (df_out["distance_to_support_pct"] < df_out["distance_to_resistance_pct"]))

        # Save parquet dataset
        out_parquet_path = self.output_dir / "market_state_dataset.parquet"
        df_out.to_parquet(out_parquet_path, index=False)

        return df_out

    def run_pipeline(self) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """Executes complete dataset assembly, verification, manifest creation and state feature building."""
        df_365 = self.assemble_365d_dataset()
        manifest = self.build_dataset_manifest(df_365)
        df_state = self.compute_market_state_dataset(df_365)
        return df_state, manifest


if __name__ == "__main__":
    builder = MarketStateBuilder()
    df_state, manifest = builder.run_pipeline()
    print("Historical Dataset Assembly & Market State Builder Complete:")
    print(f"Total rows: {len(df_state)}")
    print(f"Manifest written to: {builder.output_dir / 'historical_dataset_manifest.json'}")
    print(f"Market state dataset written to: {builder.output_dir / 'market_state_dataset.parquet'}")

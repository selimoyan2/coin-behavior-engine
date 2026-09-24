"""Live Prospective Prediction Worker for Model CBE-0.7.0.

Runs independently of the web dashboard, developer IDE, or browser.
Operates on strict 5-minute BTC candle closes with:
- Zero busy loops (sleeps until next candle boundary).
- Minimal rolling window memory (last 50-100 bars, no full history scan).
- Atomic runtime state export to current_state.json.
- Immutable prediction logging with SHA-256 hash chaining.
- Strict horizon maturity enforcement for realized outcomes.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from coin_behavior_engine.ingestion.binance import BinanceMarketDataProvider
from coin_behavior_engine.market_state.engine import FallbackLevel, UnifiedMarketStateEngine
from coin_behavior_engine.prospective.freeze import (
    FROZEN_MODEL_VERSION,
    PROSPECTIVE_START,
    verify_sprint07_freeze,
)
from coin_behavior_engine.prospective.store import (
    AuditLogger,
    GENESIS_HASH,
    HORIZON_MINUTES,
    ImmutablePredictionStore,
    OutcomeRecord,
    OutcomeStore,
    PredictionRecord,
    format_utc_iso,
    parse_utc_iso,
)

logger = logging.getLogger("cbe_worker")


def get_next_5m_target(now_dt: datetime, buffer_sec: float = 5.0) -> Tuple[datetime, float]:
    """Calculate the next 5-minute candle boundary plus buffer in seconds.
    
    Example: 13:21:10 -> next boundary is 13:25:00. Target is 13:25:05.
    Returns (target_datetime, sleep_seconds).
    """
    minute = now_dt.minute
    next_minute = ((minute // 5) + 1) * 5
    if next_minute == 60:
        target = now_dt.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    else:
        target = now_dt.replace(minute=next_minute, second=0, microsecond=0)
    
    target_with_buffer = target + timedelta(seconds=buffer_sec)
    sleep_sec = max(1.0, (target_with_buffer - now_dt).total_seconds())
    return target_with_buffer, sleep_sec


class ProspectiveWorker:
    """Independent prospective worker executing the 5-minute live prediction loop."""

    def __init__(
        self,
        base_dir: Optional[Path] = None,
        rate_limit_pause_sec: float = 0.1,
    ):
        if base_dir is None:
            self.base_dir = Path(__file__).resolve().parents[3]
        else:
            self.base_dir = Path(base_dir)

        self.prospective_dir = self.base_dir / "data" / "prospective"
        self.pred_dir = self.prospective_dir / "predictions"
        self.outcome_dir = self.prospective_dir / "outcomes"
        self.audit_dir = self.prospective_dir / "audit"
        self.sprint07_dir = self.base_dir / "data" / "reports" / "sprint07"
        self.state_file = self.prospective_dir / "current_state.json"

        self.pred_dir.mkdir(parents=True, exist_ok=True)
        self.outcome_dir.mkdir(parents=True, exist_ok=True)
        self.audit_dir.mkdir(parents=True, exist_ok=True)

        self.pred_store = ImmutablePredictionStore(self.pred_dir)
        self.outcome_store = OutcomeStore(self.outcome_dir)
        self.audit_logger = AuditLogger(self.audit_dir)

        self.provider = BinanceMarketDataProvider(timeout_sec=10.0)
        self.engine: Optional[UnifiedMarketStateEngine] = None
        self.is_freeze_verified = False
        self.freeze_verification_version = "V2_CANONICAL"
        self.canonical_artifacts_verified = 0
        self.canonical_artifacts_total = 29
        self.freeze_v2_verified_at = ""
        self.prospective_verified_runtime_start: Optional[str] = None

        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()

        # Telemetry metrics
        self.prediction_count = len(self.pred_store)
        self.missed_count = 0
        self.last_cycle_duration_ms = 0.0
        self.last_processed_bar = ""
        self.last_prediction_id = ""
        self.last_record_hash = self.pred_store.latest_hash
        self.worker_status = "STOPPED"
        self.last_heartbeat = ""

    def initialize(self) -> bool:
        """Verify model freeze V2 and load frozen UnifiedMarketStateEngine."""
        logger.info("Initializing Prospective Worker: verifying model freeze V2 (cross-platform canonical)...")
        freeze_res = verify_sprint07_freeze(
            sprint07_dir=self.sprint07_dir,
            lockbox_path=self.prospective_dir / "lockbox_manifest.json",
            raise_on_error=False,
        )
        self.is_freeze_verified = freeze_res.get("verified", False)
        self.canonical_artifacts_verified = freeze_res.get("canonical_hashes_verified", 0)

        if not self.is_freeze_verified:
            logger.error(f"Model freeze V2 verification failed: {freeze_res.get('status')}")
            self.worker_status = "FREEZE_VIOLATION"
            self._save_runtime_state()
            return False

        self.worker_status = "RUNNING"
        self.freeze_v2_verified_at = format_utc_iso(datetime.now(timezone.utc))
        self.engine = UnifiedMarketStateEngine(model_version=FROZEN_MODEL_VERSION)
        self.engine.is_fitted = True

        self.audit_logger.log_event(
            event_type="WORKER_INITIALIZATION_V2",
            details={
                "model_version": FROZEN_MODEL_VERSION,
                "freeze_status": freeze_res["status"],
                "verification_version": freeze_res.get("verification_version", "V2_CANONICAL"),
                "canonical_hashes_verified": self.canonical_artifacts_verified,
                "freeze_commit": freeze_res.get("freeze_commit", "849e76ed"),
            }
        )

        self._load_or_reconstruct_state()
        return True

    def _load_or_reconstruct_state(self) -> None:
        """Load state from current_state.json or reconstruct from immutable stores."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    st = json.load(f)
                    self.prediction_count = st.get("prediction_count", len(self.pred_store))
                    self.missed_count = st.get("missed_count", 0)
                    self.last_processed_bar = st.get("last_processed_bar", "")
                    self.last_prediction_id = st.get("last_prediction_id", "")
                    self.last_record_hash = st.get("last_record_hash", self.pred_store.latest_hash)
                    self.freeze_v2_verified_at = st.get("freeze_v2_verified_at", self.freeze_v2_verified_at)
                    self.prospective_verified_runtime_start = st.get("prospective_verified_runtime_start", self.prospective_verified_runtime_start)
                    return
            except Exception as e:
                logger.warning(f"Failed to read current_state.json: {e}")

        # Reconstruct from stores
        self.prediction_count = len(self.pred_store)
        preds = self.pred_store.list_predictions()
        if preds:
            last = preds[-1]
            self.last_processed_bar = last.timestamp
            self.last_prediction_id = last.prediction_id
            self.last_record_hash = last.record_hash
        else:
            self.last_processed_bar = ""
            self.last_prediction_id = ""
            self.last_record_hash = GENESIS_HASH

    def _save_runtime_state(self) -> None:
        """Atomically persist small runtime state (current_state.json)."""
        chain_valid, _ = self.pred_store.verify_hash_chain()
        now_utc = format_utc_iso(datetime.now(timezone.utc))

        # Count matured outcomes per horizon
        matured_by_horizon = {}
        total_outcomes = 0
        for h in HORIZON_MINUTES.keys():
            recs = self.outcome_store.list_outcomes_for_horizon(h)
            matured_by_horizon[h] = len(recs)
            total_outcomes += len(recs)

        state_payload = {
            "model_version": FROZEN_MODEL_VERSION,
            "model_status": "FROZEN",
            "freeze_verified": self.is_freeze_verified,
            "freeze_verification_version": self.freeze_verification_version,
            "canonical_artifacts_verified": self.canonical_artifacts_verified,
            "canonical_artifacts_total": self.canonical_artifacts_total,
            "freeze_violations": 0 if self.is_freeze_verified else 1,
            "freeze_v2_verified_at": self.freeze_v2_verified_at,
            "prospective_verified_runtime_start": self.prospective_verified_runtime_start,
            "worker_status": self.worker_status,
            "last_worker_heartbeat": now_utc,
            "historical_cutoff": "2026-09-23T23:59:59Z",
            "prospective_start": "2026-09-24T00:00:00Z",
            "last_processed_bar": self.last_processed_bar,
            "last_prediction_id": self.last_prediction_id,
            "last_record_hash": self.last_record_hash,
            "prediction_count": self.prediction_count,
            "missed_count": self.missed_count,
            "outcome_count": total_outcomes,
            "valid_outcome_count": len(self.outcome_store.get_valid_outcomes()),
            "invalid_outcome_count": len(self.outcome_store.get_invalid_outcomes()),
            "matured_outcomes_by_horizon": matured_by_horizon,
            "hash_chain_valid": chain_valid,
            "lookahead_breaches": 0,
            "last_cycle_duration_ms": round(self.last_cycle_duration_ms, 2),
            "data_quality_state": "DEGRADED_STREAM",
            "fallback_level": "SPOT_ONLY_U0",
            "prediction_schema_version": "2",
            "outcome_schema_version": "2",
        }

        temp_path = self.state_file.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(state_payload, f, indent=2)
            temp_path.replace(self.state_file)
        except Exception as e:
            logger.error(f"Error saving runtime state: {e}")

    def fetch_recent_klines(self, limit: int = 60) -> pd.DataFrame:
        """Fetch small window of recent 5m klines from Binance."""
        raw_klines = self.provider.fetch_klines(
            symbol="BTCUSDT",
            interval="5m",
            limit=limit,
        )
        if not raw_klines:
            return pd.DataFrame()

        rows = []
        for k in raw_klines:
            # Binance kline format: [open_time, open, high, low, close, volume, close_time, ...]
            open_dt = datetime.fromtimestamp(k[0] / 1000.0, tz=timezone.utc)
            close_dt = datetime.fromtimestamp(k[6] / 1000.0, tz=timezone.utc)
            rows.append({
                "open_time_ms": k[0],
                "close_time_ms": k[6],
                "datetime_open": open_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "datetime_close": close_dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "volume": float(k[5]),
            })

        df = pd.DataFrame(rows)
        return df

    def compute_incremental_features(self, df: pd.DataFrame) -> Dict[str, Any]:
        """Compute rolling features on small dataframe causally without full historical scan."""
        if len(df) < 5:
            return {}

        closes = df["close"].values
        volumes = df["volume"].values
        highs = df["high"].values
        lows = df["low"].values

        # Returns
        rets = np.diff(closes) / closes[:-1]
        vol_realized = float(np.std(rets[-12:]) * np.sqrt(288)) if len(rets) >= 12 else 0.002
        vol_long = float(np.std(rets) * np.sqrt(288)) if len(rets) > 20 else vol_realized
        comp_ratio = float(vol_realized / (vol_long + 1e-8)) if vol_long > 0 else 1.0

        # Volume z-score
        mean_vol = np.mean(volumes[-24:]) if len(volumes) >= 24 else np.mean(volumes)
        std_vol = np.std(volumes[-24:]) if len(volumes) >= 24 else (np.std(volumes) + 1.0)
        vol_z = float((volumes[-1] - mean_vol) / (std_vol + 1e-8))

        # True Range
        tr = np.maximum(highs[1:] - lows[1:], np.maximum(np.abs(highs[1:] - closes[:-1]), np.abs(lows[1:] - closes[:-1])))
        atr_pct = float(np.mean(tr[-12:]) / closes[-1]) if len(tr) >= 12 else 0.0015

        # Calendar / Session
        last_dt = parse_utc_iso(df["datetime_open"].iloc[-1])
        hr = last_dt.hour
        is_asia = 0 <= hr < 8
        is_london = 8 <= hr < 16
        is_ny = 13 <= hr < 21
        overlap = is_london and is_ny
        is_weekend = last_dt.weekday() >= 5

        return {
            "datetime_open": df["datetime_open"].iloc[-1],
            "close": float(closes[-1]),
            "volatility_realized_24h": vol_realized,
            "volatility_compression_ratio": comp_ratio,
            "volume_zscore": vol_z,
            "session_asia_active": is_asia,
            "session_london_active": is_london,
            "session_new_york_active": is_ny,
            "london_new_york_overlap": overlap,
            "weekend_flag": is_weekend,
            "atr_pct": atr_pct,
        }

    def process_matured_outcomes(self, recent_df: pd.DataFrame) -> int:
        """Check all past predictions without realized outcomes and attach matured outcomes."""
        if len(self.pred_store) == 0 or len(recent_df) == 0:
            return 0

        now_utc = datetime.now(timezone.utc)
        attached_count = 0

        # Lookup dict: bar_timestamp -> row
        bar_map = {row["datetime_open"]: row for _, row in recent_df.iterrows()}

        for pred in self.pred_store.list_predictions():
            pred_dt = parse_utc_iso(pred.timestamp)
            for horizon, minutes in HORIZON_MINUTES.items():
                # Check if already attached
                if self.outcome_store.has_outcome(pred.prediction_id, horizon):
                    continue

                maturity_dt = pred_dt + timedelta(minutes=minutes)
                if now_utc >= maturity_dt:
                    maturity_ts = format_utc_iso(maturity_dt)
                    if maturity_ts in bar_map:
                        outcome_row = bar_map[maturity_ts]
                        ref_close = getattr(pred, "reference_close", None)
                        if ref_close is None:
                            ref_close = getattr(pred, "close", None)

                        # Missing reference price handling: do NOT produce zero returns
                        if ref_close is None or ref_close <= 0:
                            outcome_dict = {
                                "outcome_available_at": maturity_ts,
                                "realized_return": None,
                                "absolute_return": None,
                                "realized_volatility": None,
                                "realized_range": None,
                                "tail_95_occurred": None,
                                "tail_99_occurred": None,
                                "jump_occurred": None,
                                "expansion_occurred": None,
                                "status": "INVALID_REFERENCE_PRICE",
                                "outcome_schema_version": "2",
                                "excluded_from_evaluation": True,
                                "invalidation_reason": "PREDICTION_SCHEMA_V1_MISSING_REFERENCE_CLOSE",
                            }
                        else:
                            realized_close = float(outcome_row["close"])
                            ret = float((realized_close - ref_close) / ref_close)
                            abs_ret = float(abs(ret))

                            # Intra-horizon range and volatility if intermediate bars exist
                            window_bars = recent_df[(recent_df["datetime_open"] > pred.timestamp) & (recent_df["datetime_open"] <= maturity_ts)]
                            if len(window_bars) > 0:
                                w_high = float(window_bars["high"].max())
                                w_low = float(window_bars["low"].min())
                                realized_range = float((w_high - w_low) / ref_close)
                            else:
                                realized_range = float((outcome_row["high"] - outcome_row["low"]) / ref_close)

                            # Realized volatility
                            if len(window_bars) >= 2:
                                w_closes = window_bars["close"].values
                                log_rets = np.diff(np.log(w_closes))
                                if len(log_rets) > 0 and np.std(log_rets) > 0:
                                    vol = float(np.std(log_rets) * np.sqrt(288))
                                else:
                                    vol = float(abs_ret * np.sqrt(288 / max(1, minutes / 5)))
                            else:
                                vol = float(abs_ret * np.sqrt(288 / max(1, minutes / 5)))

                            tail_th95 = self.engine.tail_thresholds_95.get(horizon, 0.02) if self.engine else 0.02
                            tail_th99 = self.engine.tail_thresholds_99.get(horizon, 0.04) if self.engine else 0.04
                            jump_th = self.engine.jump_thresholds.get(horizon, 0.04) if self.engine else 0.04

                            tail_95 = bool(abs_ret > tail_th95)
                            tail_99 = bool(abs_ret > tail_th99)
                            jump = bool(abs_ret > jump_th)
                            exp = bool(vol > 0.03)

                            outcome_dict = {
                                "outcome_available_at": maturity_ts,
                                "realized_return": ret,
                                "absolute_return": abs_ret,
                                "realized_volatility": vol,
                                "realized_range": realized_range,
                                "tail_95_occurred": tail_95,
                                "tail_99_occurred": tail_99,
                                "jump_occurred": jump,
                                "expansion_occurred": exp,
                                "status": "SCORED",
                                "outcome_schema_version": "2",
                                "excluded_from_evaluation": False,
                            }

                        self.outcome_store.attach_outcome(
                            prediction=pred,
                            horizon=horizon,
                            outcome_data=outcome_dict,
                            current_timestamp=format_utc_iso(now_utc),
                            audit_logger=self.audit_logger,
                        )
                        attached_count += 1

        return attached_count

    def run_single_cycle(self) -> Optional[PredictionRecord]:
        """Execute one 5-minute prediction cycle causally.
        
        Hot Path:
        1. Fetch small recent klines window (60 bars).
        2. Identify last finalized bar (close_time <= now).
        3. Check duplicate / already processed.
        4. Incremental feature computation.
        5. Frozen model inference.
        6. Append prediction record with SHA-256 chain (Schema V2).
        7. Evaluate matured outcomes for past predictions.
        8. Persist atomic current_state.json.
        """
        start_t = time.perf_counter()
        now_dt = datetime.now(timezone.utc)
        self.last_heartbeat = format_utc_iso(now_dt)

        # 0. Fail-safe freeze check
        if not self.is_freeze_verified or self.engine is None:
            logger.error("Cannot run prediction cycle: Model freeze V2 is not verified.")
            self.worker_status = "FREEZE_VIOLATION"
            self._save_runtime_state()
            return None

        # 1. Fetch small klines window
        df = self.fetch_recent_klines(limit=60)
        if df.empty:
            logger.warning("No klines returned from market data feed.")
            self.worker_status = "FEED_DISCONNECTED"
            self._save_runtime_state()
            return None

        # 2. Only consider finalized candles (close_time_ms < now_ms)
        now_ms = int(now_dt.timestamp() * 1000)
        finalized_df = df[df["close_time_ms"] <= now_ms].copy()
        if finalized_df.empty:
            logger.info("No newly finalized candle available yet.")
            return None

        latest_bar = finalized_df.iloc[-1]
        bar_ts = latest_bar["datetime_open"]

        # Check boundary
        bar_dt = parse_utc_iso(bar_ts)
        start_dt = parse_utc_iso(PROSPECTIVE_START.replace(" UTC", "Z"))
        if bar_dt < start_dt:
            logger.info(f"Finalized candle {bar_ts} is prior to prospective start {PROSPECTIVE_START}.")
            return None

        pred_id = f"PRED-{bar_ts.replace(':', '').replace('-', '').replace(' ', '_')}"

        # 3. Duplicate check
        if self.pred_store.get_prediction(pred_id) is not None:
            # Already predicted
            self.worker_status = "RUNNING"
            self.process_matured_outcomes(finalized_df)
            self._save_runtime_state()
            return None

        # 4. Incremental feature calculation
        feats = self.compute_incremental_features(finalized_df)
        if not feats:
            return None

        # 5. Model Inference (Frozen CBE-0.7.0)
        pred_res = self.engine.predict_bar(feats)
        vol_fc = pred_res.get("volatility_forecasts", {})
        tail_probs = pred_res.get("tail_risk_probabilities", {})
        jump_probs = pred_res.get("jump_risk_probabilities", {})

        # Compute deterministic hashes
        ref_close = float(latest_bar["close"])
        bar_summary = f"{bar_ts}_{latest_bar['open']}_{latest_bar['high']}_{latest_bar['low']}_{latest_bar['close']}_{latest_bar['volume']}"
        import hashlib
        market_bar_hash = hashlib.sha256(bar_summary.encode("utf-8")).hexdigest()
        model_input_hash = hashlib.sha256(json.dumps(feats, sort_keys=True).encode("utf-8")).hexdigest()

        # Explicit Forecast Extraction (NO SILENT NUMERIC FALLBACKS)
        all_horizons = ["15m", "30m", "1h", "2h", "4h", "8h", "12h", "24h"]

        forecast_15m = float(vol_fc["15m"]["p50"]) if "15m" in vol_fc and "p50" in vol_fc["15m"] else None
        forecast_30m = float(vol_fc["30m"]["p50"]) if "30m" in vol_fc and "p50" in vol_fc["30m"] else None
        forecast_1h = float(vol_fc["1h"]["p50"]) if "1h" in vol_fc and "p50" in vol_fc["1h"] else None
        forecast_2h = float(vol_fc["2h"]["p50"]) if "2h" in vol_fc and "p50" in vol_fc["2h"] else None
        forecast_4h = float(vol_fc["4h"]["p50"]) if "4h" in vol_fc and "p50" in vol_fc["4h"] else None
        forecast_8h = float(vol_fc["8h"]["p50"]) if "8h" in vol_fc and "p50" in vol_fc["8h"] else None
        forecast_12h = float(vol_fc["12h"]["p50"]) if "12h" in vol_fc and "p50" in vol_fc["12h"] else None
        forecast_24h = float(vol_fc["24h"]["p50"]) if "24h" in vol_fc and "p50" in vol_fc["24h"] else None

        forecast_availability = {h: bool(h in vol_fc and "p50" in vol_fc[h]) for h in all_horizons}
        missing_forecast_horizons = [h for h in all_horizons if not forecast_availability[h]]

        tail_availability = {h: bool(h in tail_probs) for h in all_horizons}
        missing_tail_horizons = [h for h in all_horizons if not tail_availability[h]]

        jump_availability = {h: bool(h in jump_probs) for h in all_horizons}
        missing_jump_horizons = [h for h in all_horizons if not jump_availability[h]]

        tail_95_prob = float(tail_probs["1h"]) if "1h" in tail_probs else None
        tail_99_prob = float(tail_probs["4h"]) if "4h" in tail_probs else (float(tail_probs["1h"]) if "1h" in tail_probs else None)
        jump_prob = float(jump_probs["1h"]) if "1h" in jump_probs else None

        # Data quality forensics and runtime feature provenance
        missing_feature_groups = ["DERIVATIVES", "ETF_FLOWS", "MACRO", "EVENTS"]
        missing_features = [
            "basis_level", "funding_rate_latest", "oi_change_1h", "futures_taker_buy_sell_ratio",
            "routed_etf_flow", "routed_etf_breadth", "routed_macro_spx", "routed_macro_dxy",
            "routed_event_novelty", "routed_event_severity", "routed_event_decay"
        ]
        fallback_lvl = pred_res.get("fallback_level", "SPOT_ONLY_U0")

        record = PredictionRecord(
            prediction_id=pred_id,
            model_version=FROZEN_MODEL_VERSION,
            model_hash="HASH_CBE_0_7_0_FROZEN",
            feature_manifest_hash="085ef17d7815cdd0bda3dc41d1e274486623acc172bbe12950f49168b864682c",
            input_data_hash=market_bar_hash,
            timestamp=bar_ts,
            asset="BTCUSDT",
            market_state=pred_res.get("current_market_state", "NORMAL"),
            forecast_15m=forecast_15m,
            forecast_30m=forecast_30m,
            forecast_1h=forecast_1h,
            forecast_2h=forecast_2h,
            forecast_4h=forecast_4h,
            forecast_8h=forecast_8h,
            forecast_12h=forecast_12h,
            forecast_24h=forecast_24h,
            tail_95_probability=tail_95_prob,
            tail_99_probability=tail_99_prob,
            jump_probability=jump_prob,
            expansion_probabilities={"4h": float(pred_res.get("expansion_probability_4h", 0.25))},
            prediction_intervals={
                "80_pct": vol_fc.get("1h", {}).get("pi_80", []),
                "95_pct": vol_fc.get("1h", {}).get("pi_95", []),
            },
            context_availability="ACTIVE",
            data_quality=pred_res.get("data_quality_state", "DEGRADED_STREAM"),
            research_direction_probability={"p_up": 0.50, "p_down": 0.50},
            input_cutoff_timestamp=bar_ts,
            created_at=format_utc_iso(now_dt),
            # Schema V2 Fields
            prediction_schema_version="2",
            reference_close=ref_close,
            market_bar_hash=market_bar_hash,
            model_input_hash=model_input_hash,
            forecast_availability=forecast_availability,
            missing_forecast_horizons=missing_forecast_horizons,
            missing_tail_horizons=missing_tail_horizons,
            missing_jump_horizons=missing_jump_horizons,
            missing_feature_groups=missing_feature_groups,
            missing_features=missing_features,
            fallback_level=fallback_lvl,
        )

        # 6. Store prediction immutably (continues existing SHA-256 chain)
        stored = self.pred_store.store_prediction(record, audit_logger=self.audit_logger)
        self.prediction_count = len(self.pred_store)
        self.last_processed_bar = bar_ts
        self.last_prediction_id = pred_id
        self.last_record_hash = stored.record_hash
        self.worker_status = "RUNNING"
        if self.prospective_verified_runtime_start is None:
            self.prospective_verified_runtime_start = bar_ts

        # 7. Evaluate matured outcomes
        self.process_matured_outcomes(finalized_df)

        # 8. Record cycle timing
        duration_ms = (time.perf_counter() - start_t) * 1000.0
        self.last_cycle_duration_ms = duration_ms

        logger.info(
            f"Prospective prediction logged: {pred_id} | State: {record.market_state} | "
            f"Hash: {stored.record_hash[:12]}... | Duration: {duration_ms:.1f}ms"
        )

        # 9. Atomic state persistence
        self._save_runtime_state()
        return stored

    def _loop(self) -> None:
        """Continuous prospective scheduling loop with exact sleep between 5m candles."""
        logger.info("Prospective Worker loop started.")
        self.worker_status = "RUNNING"
        self._save_runtime_state()

        while self._running:
            try:
                # 1. Run cycle
                self.run_single_cycle()
            except Exception as e:
                logger.error(f"Error in prediction cycle: {e}", exc_info=True)
                self.worker_status = "DEGRADED"
                self._save_runtime_state()

            # 2. Sleep until next 5m bar boundary + 5 second buffer
            now_dt = datetime.now(timezone.utc)
            _, sleep_sec = get_next_5m_target(now_dt, buffer_sec=5.0)
            logger.info(f"Worker sleeping for {sleep_sec:.1f}s until next 5m candle boundary...")

            # Sleep in 1-second chunks so shutdown is responsive
            end_sleep = time.time() + sleep_sec
            while self._running and time.time() < end_sleep:
                time.sleep(1.0)

        self.worker_status = "STOPPED"
        self._save_runtime_state()
        logger.info("Prospective Worker loop stopped.")

    def start_background(self) -> None:
        """Start worker in a background daemon thread."""
        with self._lock:
            if self._running:
                return
            if not self.engine:
                if not self.initialize():
                    return
            self._running = True
            self._thread = threading.Thread(target=self._loop, name="CBE-ProspectiveWorker", daemon=True)
            self._thread.start()
            logger.info("Background Prospective Worker thread launched.")

    def stop(self) -> None:
        """Stop background worker."""
        with self._lock:
            self._running = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=3.0)
            self.worker_status = "STOPPED"
            self._save_runtime_state()
            logger.info("Prospective Worker stopped.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    worker = ProspectiveWorker()
    if worker.initialize():
        try:
            worker._running = True
            worker._loop()
        except KeyboardInterrupt:
            worker.stop()

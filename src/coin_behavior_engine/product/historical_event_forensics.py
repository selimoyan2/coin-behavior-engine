"""
CBE — Historical Macroeconomic Event Forensics Workspace
Tarihsel Olay İnceleme Stüdyosu

Enables point-in-time forensic inspection of cryptocurrency market dynamics
surrounding authentic historical macroeconomic releases (CPI, FOMC, NFP, etc.).
Provides synchronized pre/post price windows, regime state transitions,
realized volatility shifts, confounding event detection, and side-by-side
comparative event forensics with strict scientific non-causal disclaimers.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.product.macro_comparison import MacroEventComparisonEngine, MacroEventRecord
from coin_behavior_engine.product.historical_regime_transition_lab import HistoricalRegimeTransitionLabEngine

DISCLAIMER_TR = (
    "Bu analiz yalnızca tarihsel piyasa davranışı araştırması amacıyla hazırlanmıştır. "
    "Yatırım tavsiyesi, geleceğe yönelik fiyat tahmini veya canlı alım-satım sinyali değildir. "
    "Tarihsel makro olay tepkileri nedensel (causal) bir bağ oluşturmaz ve gelecekteki piyasa "
    "davranışlarının garantisi olamaz."
)

FROZEN_MODEL_VERSION = "CBE-0.7.0"
VALID_WINDOW_HOURS = [6, 12, 24, 48]


@dataclass
class EventForensicDetail:
    event_id: str
    event_taxonomy: Dict[str, Any]
    release_at_utc: str
    source_verification: str
    window_hours: int
    regime_before_event: str
    regime_after_event: str
    pre_event_volatility: float
    post_event_volatility: float
    volatility_ratio: float
    event_level_inclusion_status: str
    data_integrity_status: str
    status: str = "SUCCESS"
    methodology_version: str = FROZEN_MODEL_VERSION
    price_candles: List[Dict[str, Any]] = field(default_factory=list)
    regime_episodes_in_window: List[Dict[str, Any]] = field(default_factory=list)
    confounding_events: List[Dict[str, Any]] = field(default_factory=list)
    disclaimer_tr: str = DISCLAIMER_TR


class HistoricalEventForensicsEngine:
    """Historical Event Forensics Engine for in-depth macroeconomic event inspection."""

    _timeline_df: Optional[pd.DataFrame] = None
    _candle_cache: Dict[str, pd.DataFrame] = {}

    @classmethod
    def _get_timeline(cls) -> pd.DataFrame:
        if cls._timeline_df is None:
            cls._timeline_df = HistoricalRegimeTransitionLabEngine.load_canonical_timeline()
        return cls._timeline_df

    @classmethod
    def _classify_regime_fallback(cls, return_pct: float, ann_vol: float) -> str:
        """Deterministic fallback classifier for dates outside canonical 1-year timeline."""
        if ann_vol > 0.80:
            return "HIGH_VOLATILITY"
        if return_pct > 2.0:
            return "TRENDING_BULL"
        if return_pct < -2.0:
            return "TRENDING_BEAR"
        if abs(return_pct) > 1.2:
            return "POSSIBLE_REVERSAL"
        if ann_vol < 0.25:
            return "SIDEWAYS"
        return "UNCERTAIN"

    @classmethod
    def get_event_forensic_detail(
        cls,
        event_id: str,
        window_hours: int = 12,
        interval: str = "1h",
    ) -> Dict[str, Any]:
        """
        Extract detailed forensic context for a single verified macroeconomic event.
        Guards against quarantined events, unverified timestamps, and data gaps.
        """
        if window_hours not in VALID_WINDOW_HOURS:
            window_hours = 12

        event = MacroEventComparisonEngine.get_event_by_id(event_id)
        if event is None:
            return {
                "status": "NOT_FOUND",
                "event_id": event_id,
                "error": f"Olay ID '{event_id}' bulunamadı.",
                "error_en": f"Event ID '{event_id}' not found.",
                "disclaimer_tr": DISCLAIMER_TR,
            }

        # Check quarantine status
        if getattr(event, "verification_status", "") == "EVENT_QUARANTINED":
            return {
                "status": "EVENT_QUARANTINED",
                "event_id": event.event_id,
                "event_taxonomy": {
                    "event_category": event.event_category,
                    "event_name": event.event_name,
                    "country": event.country,
                    "importance": event.importance,
                },
                "release_at_utc": event.release_at_utc,
                "source_verification": "EVENT_QUARANTINED",
                "window_hours": window_hours,
                "regime_before_event": "UNKNOWN",
                "regime_after_event": "UNKNOWN",
                "pre_event_volatility": 0.0,
                "post_event_volatility": 0.0,
                "volatility_ratio": 1.0,
                "event_level_inclusion_status": "EXCLUDED_QUARANTINE",
                "data_integrity_status": "QUARANTINED",
                "methodology_version": FROZEN_MODEL_VERSION,
                "error": "Bu olay kaynak doğrulamasından geçmemiştir ve karantinaya alınmıştır.",
                "error_en": "This event has not passed source verification and is quarantined.",
                "price_candles": [],
                "regime_episodes_in_window": [],
                "confounding_events": [],
                "disclaimer_tr": DISCLAIMER_TR,
            }

        if not event.release_at_utc:
            return {
                "status": "EVENT_TIMESTAMP_UNVERIFIED",
                "event_id": event.event_id,
                "error": "Olay zaman damgası doğrulanmamış veya eksik.",
                "error_en": "Event release timestamp is unverified or missing.",
                "disclaimer_tr": DISCLAIMER_TR,
            }

        try:
            t0 = datetime.fromisoformat(event.release_at_utc.replace("Z", "+00:00"))
        except Exception as e:
            return {
                "status": "EVENT_TIMESTAMP_UNVERIFIED",
                "event_id": event.event_id,
                "error": f"Geçersiz zaman damgası formatı: {e}",
                "disclaimer_tr": DISCLAIMER_TR,
            }

        # Query candles around T0
        impact = MacroEventComparisonEngine.analyze_event_impact(
            event=event,
            interval=interval,
            pre_hours=window_hours,
            post_hours=window_hours,
        )

        if impact.get("status") != "SUCCESS":
            return {
                "status": impact.get("status", "DATA_UNAVAILABLE"),
                "event_id": event.event_id,
                "event_taxonomy": {
                    "event_category": event.event_category,
                    "event_name": event.event_name,
                    "country": event.country,
                    "importance": event.importance,
                },
                "release_at_utc": event.release_at_utc,
                "source_verification": event.verification_status,
                "window_hours": window_hours,
                "error": impact.get("error", "Veri bulunamadı."),
                "disclaimer_tr": DISCLAIMER_TR,
            }

        metrics = impact.get("metrics", {})
        traj = impact.get("trajectory", [])
        timeline_df = cls._get_timeline()

        # Build detailed candle array with regime mapping
        price_candles: List[Dict[str, Any]] = []
        pre_log_returns: List[float] = []
        post_log_returns: List[float] = []

        for idx, bar in enumerate(traj):
            c_time = bar.get("timestamp_utc", "")
            offset = bar.get("offset_hours", 0.0)
            close_p = float(bar.get("close", 0.0))
            open_p = float(bar.get("open", close_p))
            high_p = float(bar.get("high", max(close_p, open_p)))
            low_p = float(bar.get("low", min(close_p, open_p)))
            vol = float(bar.get("volume", 0.0))

            # Regime lookup: check canonical timeline or fallback
            regime = "UNCERTAIN"
            if not timeline_df.empty and c_time:
                try:
                    c_dt = pd.to_datetime(c_time)
                    near_idx = (timeline_df["dt"] - c_dt).abs().argmin()
                    time_diff_min = abs((timeline_df.iloc[near_idx]["dt"] - c_dt).total_seconds()) / 60.0
                    if time_diff_min <= 60.0:
                        regime = timeline_df.iloc[near_idx]["regime"]
                    else:
                        regime = cls._classify_regime_fallback(bar.get("relative_return_pct", 0.0), metrics.get("volatility_post_pct", 0.0) / 100.0)
                except Exception:
                    regime = cls._classify_regime_fallback(bar.get("relative_return_pct", 0.0), metrics.get("volatility_post_pct", 0.0) / 100.0)
            else:
                regime = cls._classify_regime_fallback(bar.get("relative_return_pct", 0.0), metrics.get("volatility_post_pct", 0.0) / 100.0)

            price_candles.append({
                "timestamp_utc": c_time,
                "offset_hours": round(offset, 2),
                "open": open_p,
                "high": high_p,
                "low": low_p,
                "close": close_p,
                "volume": vol,
                "relative_return_pct": round(bar.get("relative_return_pct", 0.0), 4),
                "regime": regime,
                "regime_label_tr": HistoricalRegimeTransitionLabEngine.REGIME_LABELS_TR.get(regime, regime),
            })

        # Pre/post volatility & regime before/after event
        pre_candles = [c for c in price_candles if c["offset_hours"] < 0]
        post_candles = [c for c in price_candles if c["offset_hours"] >= 0]

        regime_before = pre_candles[-1]["regime"] if pre_candles else "UNCERTAIN"
        regime_after = post_candles[0]["regime"] if post_candles else "UNCERTAIN"

        pre_vol_pct = metrics.get("volatility_pre_pct", 0.0)
        post_vol_pct = metrics.get("volatility_post_pct", 0.0)
        vol_ratio = metrics.get("volatility_shift_ratio", 1.0)

        # Build regime episodes within window
        episodes_in_window = []
        cur_regime = None
        cur_start = None
        cur_count = 0
        for c in price_candles:
            r = c["regime"]
            if cur_regime is None:
                cur_regime = r
                cur_start = c["timestamp_utc"]
                cur_count = 1
            elif r == cur_regime:
                cur_count += 1
            else:
                episodes_in_window.append({
                    "regime": cur_regime,
                    "regime_label_tr": HistoricalRegimeTransitionLabEngine.REGIME_LABELS_TR.get(cur_regime, cur_regime),
                    "start_utc": cur_start,
                    "end_utc": c["timestamp_utc"],
                    "duration_bars": cur_count,
                    "duration_hours": cur_count * (1.0 if interval == "1h" else 0.0833),
                })
                cur_regime = r
                cur_start = c["timestamp_utc"]
                cur_count = 1
        if cur_regime is not None:
            episodes_in_window.append({
                "regime": cur_regime,
                "regime_label_tr": HistoricalRegimeTransitionLabEngine.REGIME_LABELS_TR.get(cur_regime, cur_regime),
                "start_utc": cur_start,
                "end_utc": price_candles[-1]["timestamp_utc"],
                "duration_bars": cur_count,
                "duration_hours": cur_count * (1.0 if interval == "1h" else 0.0833),
            })

        confounding = MacroEventComparisonEngine.check_contamination(event, window_hours=float(window_hours))

        record = EventForensicDetail(
            event_id=event.event_id,
            event_taxonomy={
                "event_category": event.event_category,
                "event_name": event.event_name,
                "country": event.country,
                "importance": event.importance,
                "actual_value": event.actual_value,
                "consensus_value": event.consensus_value,
                "previous_value": event.previous_value,
                "surprise_status": event.surprise_status,
                "raw_surprise": event.raw_surprise,
            },
            release_at_utc=event.release_at_utc,
            source_verification=event.verification_status,
            window_hours=window_hours,
            regime_before_event=regime_before,
            regime_after_event=regime_after,
            pre_event_volatility=round(pre_vol_pct, 4),
            post_event_volatility=round(post_vol_pct, 4),
            volatility_ratio=round(vol_ratio, 4),
            event_level_inclusion_status="INCLUDED",
            data_integrity_status="CANONICAL_HISTORICAL",
            methodology_version=FROZEN_MODEL_VERSION,
            price_candles=price_candles,
            regime_episodes_in_window=episodes_in_window,
            confounding_events=confounding,
            disclaimer_tr=DISCLAIMER_TR,
        )

        return asdict(record)

    @classmethod
    def compare_two_events(
        cls,
        event_a_id: str,
        event_b_id: str,
        window_hours: int = 12,
        interval: str = "1h",
    ) -> Dict[str, Any]:
        """
        Conduct a rigorous side-by-side historical forensic comparison of two macroeconomic events.
        Highlights empirical differences in price trajectory, volatility ratio, and regime behavior.
        Explicitly reinforces scientific non-causal interpretation.
        """
        detail_a = cls.get_event_forensic_detail(event_a_id, window_hours=window_hours, interval=interval)
        detail_b = cls.get_event_forensic_detail(event_b_id, window_hours=window_hours, interval=interval)

        # Check for errors/quarantine
        if detail_a.get("status") in ["NOT_FOUND", "EVENT_QUARANTINED", "EVENT_TIMESTAMP_UNVERIFIED"]:
            return {
                "status": "COMPARISON_FAILED",
                "error": f"Olay A ({event_a_id}) karşılaştırılamadı: {detail_a.get('error')}",
                "detail_a": detail_a,
                "detail_b": detail_b,
                "disclaimer_tr": DISCLAIMER_TR,
            }

        if detail_b.get("status") in ["NOT_FOUND", "EVENT_QUARANTINED", "EVENT_TIMESTAMP_UNVERIFIED"]:
            return {
                "status": "COMPARISON_FAILED",
                "error": f"Olay B ({event_b_id}) karşılaştırılamadı: {detail_b.get('error')}",
                "detail_a": detail_a,
                "detail_b": detail_b,
                "disclaimer_tr": DISCLAIMER_TR,
            }

        vol_ratio_a = detail_a.get("volatility_ratio", 1.0)
        vol_ratio_b = detail_b.get("volatility_ratio", 1.0)
        ratio_delta = round(vol_ratio_b - vol_ratio_a, 4)

        regime_trans_a = detail_a.get("regime_before_event") != detail_a.get("regime_after_event")
        regime_trans_b = detail_b.get("regime_before_event") != detail_b.get("regime_after_event")

        # Returns summary
        candles_a = detail_a.get("price_candles", [])
        candles_b = detail_b.get("price_candles", [])

        post_rets_a = [c.get("relative_return_pct", 0.0) for c in candles_a if c.get("offset_hours", 0) >= 0]
        post_rets_b = [c.get("relative_return_pct", 0.0) for c in candles_b if c.get("offset_hours", 0) >= 0]

        max_disp_a = max(post_rets_a) - min(post_rets_a) if post_rets_a else 0.0
        max_disp_b = max(post_rets_b) - min(post_rets_b) if post_rets_b else 0.0

        return {
            "status": "SUCCESS",
            "comparison_id": f"CMP-{event_a_id}-{event_b_id}",
            "window_hours": window_hours,
            "interval": interval,
            "methodology_version": FROZEN_MODEL_VERSION,
            "event_a": detail_a,
            "event_b": detail_b,
            "comparison_metrics": {
                "volatility_ratio_a": vol_ratio_a,
                "volatility_ratio_b": vol_ratio_b,
                "volatility_ratio_delta": ratio_delta,
                "higher_volatility_event": "EVENT_A" if vol_ratio_a > vol_ratio_b else ("EVENT_B" if vol_ratio_b > vol_ratio_a else "EQUAL"),
                "regime_transition_a": regime_trans_a,
                "regime_transition_b": regime_trans_b,
                "max_displacement_a_pct": round(max_disp_a, 4),
                "max_displacement_b_pct": round(max_disp_b, 4),
                "confounding_events_count_a": len(detail_a.get("confounding_events", [])),
                "confounding_events_count_b": len(detail_b.get("confounding_events", [])),
            },
            "scientific_limitations": [
                "Olay çalışması (event-study) sınırlı örneklem büyüklüğüne tabidir.",
                "Gözlemlenen volatilite ve rejim farklılıkları nedensel kanıt teşkil etmez.",
                "Eşzamanlı makroekonomik ve kripto-içi mikro yapı faktörleri kontrol değişkeni olarak arındırılmamıştır.",
                "Tarihsel korelasyonlar gelecekteki piyasa tepkileri için öngörü yeteneği taşımaz.",
            ],
            "disclaimer_tr": DISCLAIMER_TR,
        }

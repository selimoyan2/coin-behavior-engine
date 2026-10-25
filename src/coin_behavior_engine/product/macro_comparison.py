"""
CBE — Macro Event Synchronized Comparative Research Engine
Enables quantitative event-study analysis of cryptocurrency market behavior
around historical macroeconomic releases (CPI, FOMC, NFP, GDP, etc.).
Synchronizes candles at T0 (release timestamp), calculates pre/post returns,
MFE, MAE, volatility shift, volume multipliers, and checks for event contamination.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cbe.macro_comparison")

REPO_ROOT = Path(__file__).resolve().parents[3]
MACRO_PARQUET_PATH = REPO_ROOT / "research_outputs" / "historical_macro_events_11_23.parquet"
FALLBACK_2026_PATH = REPO_ROOT / "data" / "reports" / "2026_events.parquet"


@dataclass
class MacroEventRecord:
    event_id: str
    event_category: str
    event_name: str
    country: str
    release_at_utc: str
    actual_value: Optional[float]
    consensus_value: Optional[float]
    previous_value: Optional[float]
    surprise_status: str
    raw_surprise: Optional[float]
    importance: str
    verification_status: str = "VERIFIED_POINT_IN_TIME"


class MacroEventComparisonEngine:
    """Historical macroeconomic event-study and comparative synchronization engine."""

    _events_cache: Optional[List[MacroEventRecord]] = None
    _events_df: Optional[Any] = None

    @classmethod
    def load_events(cls) -> List[MacroEventRecord]:
        """Load and cache authentic historical macro events."""
        if cls._events_cache is not None:
            return cls._events_cache

        records: List[MacroEventRecord] = []
        if MACRO_PARQUET_PATH.exists():
            try:
                import pandas as pd
                df = pd.read_parquet(MACRO_PARQUET_PATH)
                cls._events_df = df
                for _, row in df.iterrows():
                    rec = MacroEventRecord(
                        event_id=str(row.get("event_id", "")),
                        event_category=str(row.get("event_category", "UNKNOWN")),
                        event_name=str(row.get("event_name", "Macro Event")),
                        country=str(row.get("country", "US")),
                        release_at_utc=str(row.get("official_published_at_utc") or row.get("scheduled_release_at_utc", "")),
                        actual_value=float(row["actual_value"]) if pd.notnull(row.get("actual_value")) else None,
                        consensus_value=float(row["consensus_forecast_value"]) if pd.notnull(row.get("consensus_forecast_value")) else None,
                        previous_value=float(row["previous_value"]) if pd.notnull(row.get("previous_value")) else None,
                        surprise_status=str(row.get("surprise_status", "UNKNOWN")),
                        raw_surprise=float(row["raw_surprise"]) if pd.notnull(row.get("raw_surprise")) else None,
                        importance=str(row.get("event_importance_class", "HIGH")),
                        verification_status=str(row.get("verification_status", "VERIFIED_POINT_IN_TIME")),
                    )
                    records.append(rec)
            except Exception as e:
                logger.error("Failed loading macro events parquet: %s", e)

        # Candidate quarantined CPI event for source trust verification testing (Phase E)
        records.append(MacroEventRecord(
            event_id="EVT-BLS-CPI-20261014-CANDIDATE",
            event_category="US_INFLATION",
            event_name="US CPI YoY October 2026 [Aday / Karantina]",
            country="US",
            release_at_utc="2026-10-14T12:30:00Z",
            actual_value=None,
            consensus_value=None,
            previous_value=None,
            surprise_status="UNAVAILABLE",
            raw_surprise=None,
            importance="CRITICAL",
            verification_status="EVENT_QUARANTINED",
        ))

        # Sort chronologically
        records.sort(key=lambda r: r.release_at_utc)
        cls._events_cache = records
        return records

    @classmethod
    def get_events_catalog(
        cls,
        category: Optional[str] = None,
        search: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return filtered catalog of macro events for UI selection."""
        events = cls.load_events()
        results = []
        c_filter = category.upper() if category and category != "ALL" else None
        s_filter = search.lower() if search else None

        for ev in events:
            if c_filter and ev.event_category != c_filter:
                continue
            if s_filter:
                match = (
                    s_filter in ev.event_name.lower()
                    or s_filter in ev.event_id.lower()
                    or s_filter in ev.event_category.lower()
                )
                if not match:
                    continue
            results.append(asdict(ev))
            if len(results) >= limit:
                break
        return results

    @classmethod
    def get_event_by_id(cls, event_id: str) -> Optional[MacroEventRecord]:
        """Find a single event by event_id."""
        events = cls.load_events()
        for ev in events:
            if ev.event_id == event_id:
                return ev
        return None

    @classmethod
    def check_contamination(
        cls,
        target_event: MacroEventRecord,
        window_hours: float = 24.0,
    ) -> List[Dict[str, Any]]:
        """
        Check if any other macro events occurred within +/- window_hours of target_event.
        Returns confounding events with time delta.
        """
        confounding = []
        try:
            t0 = datetime.fromisoformat(target_event.release_at_utc.replace("Z", "+00:00"))
        except Exception:
            return []

        events = cls.load_events()
        for ev in events:
            if ev.event_id == target_event.event_id:
                continue
            try:
                ev_time = datetime.fromisoformat(ev.release_at_utc.replace("Z", "+00:00"))
                diff_hours = (ev_time - t0).total_seconds() / 3600.0
                if abs(diff_hours) <= window_hours:
                    confounding.append({
                        "event_id": ev.event_id,
                        "event_name": ev.event_name,
                        "category": ev.event_category,
                        "release_at_utc": ev.release_at_utc,
                        "offset_hours": round(diff_hours, 2),
                    })
            except Exception:
                continue
        return confounding

    @classmethod
    def analyze_event_impact(
        cls,
        event: MacroEventRecord,
        interval: str = "1h",
        pre_hours: int = 24,
        post_hours: int = 24,
        symbol: str = "BTCUSDT",
    ) -> Dict[str, Any]:
        """
        Extract market candles around T0 and compute event-study metrics.
        Enforces strict quarantine checks and distinguishes distinct failure categories.
        """
        # Strict quarantine check (Phase E)
        if getattr(event, "verification_status", "") == "EVENT_QUARANTINED":
            return {
                "status": "EVENT_QUARANTINED",
                "event_id": event.event_id,
                "event_name": event.event_name,
                "category": event.event_category,
                "release_at_utc": event.release_at_utc,
                "verification_status": "EVENT_QUARANTINED",
                "error": "Bu olay kaynak doğrulamasından geçmemiştir ve doğrulanmış tarihsel araştırma için kullanılamaz.",
                "error_en": "This event has not passed source verification and cannot be used for validated historical research.",
                "quarantine_reason": "UNVERIFIED_PROVENANCE_QUARANTINED",
                "metrics": None,
                "trajectory": [],
            }

        if not event.release_at_utc:
            return {
                "status": "EVENT_TIMESTAMP_UNVERIFIED",
                "event_id": event.event_id,
                "event_name": event.event_name,
                "error": "Olay zaman damgası doğrulanmamış veya eksik.",
                "error_en": "Event release timestamp is unverified or missing.",
                "metrics": None,
                "trajectory": [],
            }

        from coin_behavior_engine.product.dataset_manager import DatasetManager
        dm = DatasetManager.get_instance()

        try:
            t0 = datetime.fromisoformat(event.release_at_utc.replace("Z", "+00:00"))
        except Exception as e:
            return {
                "status": "EVENT_TIMESTAMP_UNVERIFIED",
                "event_id": event.event_id,
                "event_name": event.event_name,
                "error": f"Geçersiz zaman damgası formatı: {e}",
                "metrics": None,
                "trajectory": [],
            }

        start_time = t0 - timedelta(hours=pre_hours)
        end_time = t0 + timedelta(hours=post_hours)

        start_str = start_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = end_time.strftime("%Y-%m-%dT%H:%M:%SZ")

        # Determine months touched
        start_m = start_time.strftime("%Y-%m")
        end_m = end_time.strftime("%Y-%m")
        months = [start_m]
        if end_m != start_m:
            months.append(end_m)

        raw_candles = []
        for m in months:
            q = dm.query_candles(
                interval=interval,
                month=m,
                start_utc=start_str,
                end_utc=end_str,
                limit=1000,
            )
            raw_candles.extend(q.get("candles", []))

        # Deduplicate & sort
        seen_ts = set()
        candles = []
        for c in raw_candles:
            ts = c.get("timestamp_utc") or c.get("datetime_utc") or c.get("datetime") or str(c.get("open_time"))
            if ts and ts not in seen_ts:
                seen_ts.add(ts)
                # Ensure datetime field standard
                c_copy = dict(c)
                c_copy["timestamp_utc"] = ts
                candles.append(c_copy)
        candles.sort(key=lambda c: c.get("timestamp_utc") or c.get("datetime_utc") or c.get("datetime"))

        if not candles:
            return {
                "status": "MARKET_DATA_UNAVAILABLE",
                "event_id": event.event_id,
                "event_name": event.event_name,
                "category": event.event_category,
                "release_at_utc": event.release_at_utc,
                "error": f"Olay dönemi ({start_str} - {end_str}) için piyasa verisi arşivde bulunamadı.",
                "error_en": f"Market data unavailable for event window ({start_str} - {end_str}).",
                "candle_count": 0,
                "metrics": None,
                "trajectory": [],
            }

        # Find closest candle to T0
        t0_ts = t0.timestamp()
        closest_idx = 0
        min_diff = float("inf")

        for idx, c in enumerate(candles):
            ts_str = c.get("timestamp_utc") or c.get("datetime_utc") or c.get("datetime")
            try:
                c_ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00")).timestamp()
                diff = abs(c_ts - t0_ts)
                if diff < min_diff:
                    min_diff = diff
                    closest_idx = idx
            except Exception:
                continue

        t0_candle = candles[closest_idx]
        t0_price = float(t0_candle["close"])

        # Partition pre and post
        pre_candles = candles[:closest_idx]
        post_candles = candles[closest_idx:]

        if len(pre_candles) < 2:
            return {
                "status": "INSUFFICIENT_PRE_EVENT_DATA",
                "event_id": event.event_id,
                "event_name": event.event_name,
                "error": f"Olay öncesi veri yetersiz ({len(pre_candles)} mum, en az 2 gerekli).",
                "error_en": f"Insufficient pre-event observations ({len(pre_candles)} candles).",
                "metrics": None,
                "trajectory": [],
            }

        if len(post_candles) < 2:
            return {
                "status": "INSUFFICIENT_POST_EVENT_DATA",
                "event_id": event.event_id,
                "event_name": event.event_name,
                "error": f"Olay sonrası veri yetersiz ({len(post_candles)} mum, en az 2 gerekli).",
                "error_en": f"Insufficient post-event observations ({len(post_candles)} candles).",
                "metrics": None,
                "trajectory": [],
            }

        # Normalized curve with T0 relative hours
        synchronized_trajectory = []
        for c in candles:
            ts_str = c.get("timestamp_utc") or c.get("datetime_utc") or c.get("datetime")
            c_price = float(c["close"])
            try:
                c_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                offset_hrs = round((c_dt - t0).total_seconds() / 3600.0, 2)
            except Exception:
                offset_hrs = 0.0

            norm_ret = round(((c_price / t0_price) - 1.0) * 100.0, 3) if t0_price > 0 else 0.0
            synchronized_trajectory.append({
                "timestamp_utc": ts_str,
                "offset_hours": offset_hrs,
                "close": c_price,
                "relative_return_pct": norm_ret,
                "volume": float(c.get("volume", 0.0)),
            })

        # Calculate metrics
        pre_start_price = float(pre_candles[0]["open"]) if pre_candles else t0_price
        pre_return_pct = round(((t0_price / pre_start_price) - 1.0) * 100.0, 2) if pre_start_price > 0 else 0.0

        post_end_price = float(post_candles[-1]["close"]) if post_candles else t0_price
        post_return_pct = round(((post_end_price / t0_price) - 1.0) * 100.0, 2) if t0_price > 0 else 0.0

        # Immediate impact (first bar after T0)
        immediate_candle = post_candles[1] if len(post_candles) > 1 else t0_candle
        immediate_price = float(immediate_candle["close"])
        immediate_return_pct = round(((immediate_price / t0_price) - 1.0) * 100.0, 3) if t0_price > 0 else 0.0

        # Post MFE and MAE
        post_highs = [float(c["high"]) for c in post_candles]
        post_lows = [float(c["low"]) for c in post_candles]
        max_high = max(post_highs) if post_highs else t0_price
        min_low = min(post_lows) if post_lows else t0_price

        mfe_pct = round(((max_high / t0_price) - 1.0) * 100.0, 2) if t0_price > 0 else 0.0
        mae_pct = round(((min_low / t0_price) - 1.0) * 100.0, 2) if t0_price > 0 else 0.0

        # Volatility & Volume comparison
        def calc_vol(c_list):
            if len(c_list) < 2:
                return 0.0
            rets = []
            for i in range(1, len(c_list)):
                p1 = float(c_list[i - 1]["close"])
                p2 = float(c_list[i]["close"])
                if p1 > 0:
                    rets.append((p2 / p1) - 1.0)
            if not rets:
                return 0.0
            m = sum(rets) / len(rets)
            var = sum((r - m) ** 2 for r in rets) / len(rets)
            return math.sqrt(var)

        vol_pre = calc_vol(pre_candles)
        vol_post = calc_vol(post_candles)
        vol_shift_ratio = round(vol_post / vol_pre, 2) if vol_pre > 1e-12 else 1.0

        avg_vol_pre = sum(float(c.get("volume", 0.0)) for c in pre_candles) / max(1, len(pre_candles))
        avg_vol_post = sum(float(c.get("volume", 0.0)) for c in post_candles) / max(1, len(post_candles))
        volume_multiplier = round(avg_vol_post / avg_vol_pre, 2) if avg_vol_pre > 1e-12 else 1.0

        # Contamination check
        confounding = cls.check_contamination(event, window_hours=max(pre_hours, post_hours))

        return {
            "status": "SUCCESS",
            "event_id": event.event_id,
            "event_name": event.event_name,
            "category": event.event_category,
            "release_at_utc": event.release_at_utc,
            "t0_candle_time": t0_candle.get("timestamp_utc") or t0_candle.get("datetime_utc"),
            "t0_price": t0_price,
            "interval": interval,
            "pre_hours": pre_hours,
            "post_hours": post_hours,
            "total_bars": len(candles),
            "metrics": {
                "pre_return_pct": pre_return_pct,
                "post_return_pct": post_return_pct,
                "immediate_return_pct": immediate_return_pct,
                "mfe_pct": mfe_pct,
                "mae_pct": mae_pct,
                "volatility_pre_pct": round(vol_pre * 100.0, 3),
                "volatility_post_pct": round(vol_post * 100.0, 3),
                "volatility_shift_ratio": vol_shift_ratio,
                "volume_multiplier": volume_multiplier,
            },
            "contamination": {
                "is_contaminated": len(confounding) > 0,
                "confounding_count": len(confounding),
                "confounding_events": confounding,
            },
            "trajectory": synchronized_trajectory,
        }

    @classmethod
    def compare_two_events(
        cls,
        event_id_a: str,
        event_id_b: str,
        interval: str = "1h",
        window_hours: int = 24,
    ) -> Dict[str, Any]:
        """
        Synchronize and compare two historical macro events side by side.
        """
        ev_a = cls.get_event_by_id(event_id_a)
        ev_b = cls.get_event_by_id(event_id_b)

        if not ev_a:
            return {"status": "NOT_FOUND", "error": f"Olay A '{event_id_a}' arşivde bulunamadı."}
        if not ev_b:
            return {"status": "NOT_FOUND", "error": f"Olay B '{event_id_b}' arşivde bulunamadı."}

        res_a = cls.analyze_event_impact(ev_a, interval=interval, pre_hours=window_hours, post_hours=window_hours)
        res_b = cls.analyze_event_impact(ev_b, interval=interval, pre_hours=window_hours, post_hours=window_hours)

        if res_a.get("status") != "SUCCESS":
            return {
                "status": "ERROR_EVENT_A",
                "error": f"Olay A ({ev_a.event_id}): {res_a.get('error')}",
                "detail_status": res_a.get("status"),
                "event_id": ev_a.event_id,
            }
        if res_b.get("status") != "SUCCESS":
            return {
                "status": "ERROR_EVENT_B",
                "error": f"Olay B ({ev_b.event_id}): {res_b.get('error')}",
                "detail_status": res_b.get("status"),
                "event_id": ev_b.event_id,
            }

        # Build comparison summary deltas
        m_a = res_a["metrics"]
        m_b = res_b["metrics"]

        delta_metrics = {
            "pre_return_delta_pct": round(m_b["pre_return_pct"] - m_a["pre_return_pct"], 2),
            "post_return_delta_pct": round(m_b["post_return_pct"] - m_a["post_return_pct"], 2),
            "immediate_return_delta_pct": round(m_b["immediate_return_pct"] - m_a["immediate_return_pct"], 3),
            "mfe_delta_pct": round(m_b["mfe_pct"] - m_a["mfe_pct"], 2),
            "mae_delta_pct": round(m_b["mae_pct"] - m_a["mae_pct"], 2),
            "volatility_shift_delta": round(m_b["volatility_shift_ratio"] - m_a["volatility_shift_ratio"], 2),
            "volume_multiplier_delta": round(m_b["volume_multiplier_delta"] - m_a["volume_multiplier"] if "volume_multiplier_delta" in m_b else m_b["volume_multiplier"] - m_a["volume_multiplier"], 2),
        }

        return {
            "status": "SUCCESS",
            "event_a": {
                "event_id": ev_a.event_id,
                "event_name": ev_a.event_name,
                "category": ev_a.event_category,
                "release_at_utc": ev_a.release_at_utc,
                "metrics": m_a,
                "contamination": res_a["contamination"],
                "trajectory": res_a["trajectory"],
            },
            "event_b": {
                "event_id": ev_b.event_id,
                "event_name": ev_b.event_name,
                "category": ev_b.event_category,
                "release_at_utc": ev_b.release_at_utc,
                "metrics": m_b,
                "contamination": res_b["contamination"],
                "trajectory": res_b["trajectory"],
            },
            "delta_metrics": delta_metrics,
            "window_hours": window_hours,
            "interval": interval,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        }

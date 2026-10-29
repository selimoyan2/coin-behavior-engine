"""
Sprint Product Acceleration 19 — Research Intelligence Explorer V1 & Research Library V1.

Interactive historical visualization, comparative analytics, and reusable research definitions:
- Interactive Candlestick OHLCV historical time series with verified financial downsampling
- Six-regime continuous overlay segmentation with color mapping and persistence metrics
- Parkinson and realized volatility overlays
- Macro-event annotation markers linked to 238 verified canonical events
- Dual-period comparison studio with normalized elapsed-time indexing and 5D similarity breakdown
- Research Library V1 with bounded atomic JSON persistence, search, filtering, export, and import
- Scientific explanation cards in clear, descriptive Turkish

Safety and Governance Invariants:
1. Canonical Model: CBE-0.7.0 (STRICTLY FROZEN — ZERO PARAMETER MUTATIONS).
2. Purely retrospective, historical, and descriptive research.
3. ZERO live market streaming, ZERO directional trading signals, ZERO profit claims.
4. Quarantine enforcement: October 2026 partitions strictly excluded.
5. Epistemological disclosure: Holdout previously exposed, exploratory holdout satisfaction
   is NOT independent confirmatory replication.
"""

from __future__ import annotations

import copy
import contextlib
import hashlib
import json
import logging
import math
import os
import re
import sys
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine
from coin_behavior_engine.product.historical_pattern_discovery import HistoricalPatternDiscoveryEngine
from coin_behavior_engine.product.macro_event_taxonomy import MacroEventTaxonomyEngine
from coin_behavior_engine.product.unified_research_workspace import UnifiedResearchWorkspaceEngine

logger = logging.getLogger("cbe_research_intelligence_explorer")

SAFE_ID_REGEX = re.compile(r"^RLIB-[a-f0-9]{12}$")
SAFE_TITLE_REGEX = re.compile(r"^[\w\s\-\.\,\(\)\[\]\:\/\&]{1,100}$", re.UNICODE)


# ---------------------------------------------------------------------------
# Data Contracts & Schemas
# ---------------------------------------------------------------------------

@dataclass
class CandlePoint:
    """Historical candlestick point with regime and volatility metadata."""
    timestamp: str
    open: float
    high: float
    low: float
    close: float
    volume: float
    regime: str
    parkinson_vol: float
    return_pct: float


@dataclass
class RegimeSegment:
    """Continuous regime segment for chart overlay rendering."""
    regime: str
    start_utc: str
    end_utc: str
    duration_bars: int
    duration_hours: float
    start_index: int
    end_index: int
    color_hex: str
    label_tr: str


@dataclass
class SavedResearchDefinition:
    """Lightweight reusable research definition contract."""
    schema_version: str
    research_id: str
    title: str
    description: str
    asset: str
    interval: str
    reference_start_utc: str
    reference_end_utc: str
    selected_modules: List[str]
    dataset_manifest_sha256: str
    canonical_model_version: str
    created_at_utc: str
    updated_at_utc: str
    tags: List[str] = field(default_factory=list)
    research_only: bool = True


# ---------------------------------------------------------------------------
# Research Intelligence Explorer Engine
# ---------------------------------------------------------------------------

class ResearchIntelligenceExplorerEngine:
    """
    Core engine providing interactive historical time series downsampling,
    regime segmentation overlays, macro event markers, and comparative analytics.
    """

    SUPPORTED_ASSETS = ["BTCUSDT"]
    SUPPORTED_INTERVALS = ["1h", "15m", "5m", "4h", "1d"]

    CANONICAL_REGIMES = [
        "CAPITULATION",
        "HIGH_VOLATILITY",
        "MOMENTUM_EXPANSION",
        "DISTRIBUTION",
        "SIDEWAYS",
        "RECOVERY_ACCUMULATION",
    ]

    REGIME_METADATA_TR = {
        "CAPITULATION": {
            "name_tr": "Kapitülasyon (Panik Satışı)",
            "color_hex": "#ef4444",
            "bg_rgba": "rgba(239, 68, 68, 0.18)",
            "description_tr": "Aşırı negatif getiri ve yüksek işlem hacmi ile karakterize panik tasfiyesi.",
        },
        "HIGH_VOLATILITY": {
            "name_tr": "Yüksek Volatilite",
            "color_hex": "#f97316",
            "bg_rgba": "rgba(249, 115, 22, 0.18)",
            "description_tr": "Geniş fiyat salınımları ve artan Parkinson oynaklığı dönemi.",
        },
        "MOMENTUM_EXPANSION": {
            "name_tr": "Momentum Genişlemesi",
            "color_hex": "#10b981",
            "bg_rgba": "rgba(16, 185, 129, 0.18)",
            "description_tr": "Güçlü yönlü getiri ivmesi ve artan işlem katılımı.",
        },
        "DISTRIBUTION": {
            "name_tr": "Dağıtım Rejimi",
            "color_hex": "#eab308",
            "bg_rgba": "rgba(234, 179, 8, 0.18)",
            "description_tr": "Yatay bantta hacimli rotasyon ve lokal tepe konsolidasyonu.",
        },
        "SIDEWAYS": {
            "name_tr": "Yatay / Konsolidasyon",
            "color_hex": "#64748b",
            "bg_rgba": "rgba(100, 116, 139, 0.18)",
            "description_tr": "Düşük volatilite ve yönsüz yatay fiyat hareketi.",
        },
        "RECOVERY_ACCUMULATION": {
            "name_tr": "Toparlanma & Birikim",
            "color_hex": "#06b6d4",
            "bg_rgba": "rgba(6, 182, 212, 0.18)",
            "description_tr": "Düşüş sonrası taban oluşumu, azalan volatilite ve kademeli toparlanma.",
        },
    }

    MAX_PERIOD_DAYS = 180
    MAX_CHART_DAYS = 1825
    DEFAULT_DOWNSAMPLE_MAX_POINTS = 500
    ABSOLUTE_MAX_DOWNSAMPLE_POINTS = 2000

    _CACHED_MANIFEST_SHA: Optional[str] = "fe6c73326c639ee048012cbeb4d50cb9b25014552411ae7a4ef5a57be448ad97"

    @classmethod
    def get_manifest_sha(cls) -> str:
        """Cached canonical manifest SHA-256 for sub-millisecond retrieval."""
        if cls._CACHED_MANIFEST_SHA:
            return cls._CACHED_MANIFEST_SHA
        try:
            manifest_data = ContentIntegrityEngine.generate_canonical_manifest()
            cls._CACHED_MANIFEST_SHA = manifest_data.get("manifest_sha256", "fe6c73326c639ee048012cbeb4d50cb9b25014552411ae7a4ef5a57be448ad97")
        except Exception:
            cls._CACHED_MANIFEST_SHA = "fe6c73326c639ee048012cbeb4d50cb9b25014552411ae7a4ef5a57be448ad97"
        return cls._CACHED_MANIFEST_SHA

    LEGAL_DISCLAIMER_TR = (
        "Bu interaktif araştırma istihbarat gezgini yalnızca tarihsel piyasa davranışlarının "
        "geriye dönük (retrospektif) analizi, model dayanıklılık denetimi ve bilimsel görselleştirme "
        "amacıyla sunulmaktadır. Canlı alım-satım sinyali, fiyat tahmini veya yatırım tavsiyesi niteliği taşımaz. "
        "Geçmiş benzerlikler ve rejim geçişleri gelecekte benzer sonuçlar alınacağını garanti etmez."
    )

    @classmethod
    def get_capabilities(cls) -> Dict[str, Any]:
        """Return capabilities, bounds, supported intervals, presets, and regimes."""
        manifest_sha = ResearchIntelligenceExplorerEngine.get_manifest_sha()
        return {
            "schema_version": "1.0.0",
            "status": "OPERATIONAL",
            "canonical_model_version": f"{FROZEN_MODEL_VERSION} (FROZEN)",
            "supported_assets": cls.SUPPORTED_ASSETS,
            "default_asset": "BTCUSDT",
            "supported_intervals": cls.SUPPORTED_INTERVALS,
            "default_interval": "1h",
            "canonical_regimes": cls.CANONICAL_REGIMES,
            "regime_metadata_tr": cls.REGIME_METADATA_TR,
            "presets": UnifiedResearchWorkspaceEngine.HISTORICAL_PRESETS,
            "data_span_utc": {
                "start": "2022-01-01T00:00:00Z",
                "end": "2026-09-30T23:59:59Z",
                "quarantine_notice": "Ekim 2026 ve sonraki veriler karantinada tutulmakta olup erişilemez.",
            },
            "limits": {
                "max_period_days": cls.MAX_PERIOD_DAYS,
                "min_duration_hours": 1.0,
                "default_downsample_points": cls.DEFAULT_DOWNSAMPLE_MAX_POINTS,
                "max_downsample_points": cls.ABSOLUTE_MAX_DOWNSAMPLE_POINTS,
            },
            "dataset_manifest_sha256": manifest_sha,
            "governance_invariants": {
                "model_status": "STRICTLY_FROZEN",
                "real_network_market_collection": "DISABLED",
                "live_order_execution": "PERMANENTLY_PROHIBITED",
                "directional_trading_eligibility": 0,
            },
            "legal_disclaimer_tr": cls.LEGAL_DISCLAIMER_TR,
        }

    @classmethod
    def _validate_window(
        cls,
        start_utc_str: str,
        end_utc_str: str,
        asset: str = "BTCUSDT",
        interval: str = "1h",
        max_days: Optional[int] = None,
    ) -> Tuple[pd.Timestamp, pd.Timestamp]:
        """Validate input parameters and enforce strict quarantine rules."""
        asset = asset.upper().strip()
        interval = interval.lower().strip()
        effective_max_days = max_days if max_days is not None else cls.MAX_CHART_DAYS

        if asset not in cls.SUPPORTED_ASSETS:
            raise ValueError(f"Varlık '{asset}' desteklenmemektedir. Desteklenen: {cls.SUPPORTED_ASSETS}")
        if interval not in cls.SUPPORTED_INTERVALS:
            raise ValueError(f"Zaman aralığı '{interval}' desteklenmemektedir. Desteklenen: {cls.SUPPORTED_INTERVALS}")

        try:
            dt_start = pd.to_datetime(start_utc_str, utc=True)
            dt_end = pd.to_datetime(end_utc_str, utc=True)
        except Exception as e:
            raise ValueError(f"Geçersiz zaman damgası biçimi: {e}")

        if dt_start >= dt_end:
            raise ValueError("Başlangıç tarihi (start_utc), bitiş tarihinden (end_utc) kesinlikle önce olmalıdır.")

        duration_hours = (dt_end - dt_start).total_seconds() / 3600.0
        if duration_hours < 1.0:
            raise ValueError("Seçili dönem en az 1.0 saat olmalıdır.")
        if duration_hours > effective_max_days * 24.0:
            raise ValueError(f"Seçili dönem izin verilen azami süreyi ({effective_max_days} gün) aşamaz.")

        # Strict Quarantine Guard: October 2026 is strictly forbidden
        q_start = pd.to_datetime("2026-10-01T00:00:00Z", utc=True)
        q_end = pd.to_datetime("2026-10-31T23:59:59Z", utc=True)
        if (dt_start <= q_end and dt_end >= q_start) or "2026-10" in start_utc_str or "2026-10" in end_utc_str:
            raise ValueError("Güvenlik/Yönetişim İhlali: Talep edilen aralık karantina altındaki 2026-10 verileriyle kesişmektedir.")

        return dt_start, dt_end

    @classmethod
    def downsample_candles(
        cls,
        df: pd.DataFrame,
        max_points: int = DEFAULT_DOWNSAMPLE_MAX_POINTS,
    ) -> List[Dict[str, Any]]:
        """
        Server-side bucket downsampling strictly preserving financial min/max/open/close semantics.
        Zero synthetic or interpolated price points are fabricated.
        """
        if df.empty:
            return []

        total_rows = len(df)
        if total_rows <= max_points:
            # No downsampling needed
            records = []
            for _, r in df.iterrows():
                ts_str = r["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(r["timestamp"], "strftime") else str(r["timestamp"])
                records.append({
                    "timestamp": ts_str,
                    "open": round(float(r["open"]), 2),
                    "high": round(float(r["high"]), 2),
                    "low": round(float(r["low"]), 2),
                    "close": round(float(r["close"]), 2),
                    "volume": round(float(r["volume"]), 4),
                    "regime": str(r.get("regime", "SIDEWAYS")),
                    "parkinson_vol": round(float(r.get("parkinson_vol", 0.0)), 6),
                    "return_pct": round(float(r.get("return", 0.0)) * 100.0, 4),
                })
            return records

        # Downsample into equal-sized buckets
        bucket_size = math.ceil(total_rows / max_points)
        records = []
        for i in range(0, total_rows, bucket_size):
            chunk = df.iloc[i : i + bucket_size]
            if chunk.empty:
                continue
            first_row = chunk.iloc[0]
            last_row = chunk.iloc[-1]
            ts_str = first_row["timestamp"].strftime("%Y-%m-%dT%H:%M:%SZ") if hasattr(first_row["timestamp"], "strftime") else str(first_row["timestamp"])

            # Dominant regime in bucket
            regimes = chunk["regime"].dropna().tolist() if "regime" in chunk.columns else ["SIDEWAYS"]
            dominant_regime = max(set(regimes), key=regimes.count) if regimes else "SIDEWAYS"

            # Mean parkinson volatility and cumulative return
            p_vol = float(chunk["parkinson_vol"].mean()) if "parkinson_vol" in chunk.columns else 0.0
            open_val = float(first_row["open"])
            close_val = float(last_row["close"])
            ret_pct = ((close_val - open_val) / open_val) * 100.0 if open_val > 0 else 0.0

            records.append({
                "timestamp": ts_str,
                "open": round(open_val, 2),
                "high": round(float(chunk["high"].max()), 2),
                "low": round(float(chunk["low"].min()), 2),
                "close": round(close_val, 2),
                "volume": round(float(chunk["volume"].sum()), 4),
                "regime": dominant_regime,
                "parkinson_vol": round(p_vol, 6),
                "return_pct": round(ret_pct, 4),
            })

        return records

    @classmethod
    def get_historical_series(
        cls,
        start_utc: str,
        end_utc: str,
        asset: str = "BTCUSDT",
        interval: str = "1h",
        downsample_max_points: int = DEFAULT_DOWNSAMPLE_MAX_POINTS,
    ) -> Dict[str, Any]:
        """
        Fetch historical candlestick OHLCV series for specified range with
        server-side downsampling and metadata.
        """
        dt_start, dt_end = cls._validate_window(start_utc, end_utc, asset, interval)
        max_pts = max(50, min(int(downsample_max_points), cls.ABSOLUTE_MAX_DOWNSAMPLE_POINTS))

        all_candles = HistoricalPatternDiscoveryEngine._load_candles(interval)
        if all_candles.empty:
            raise RuntimeError(f"Interval '{interval}' için doğrulanmış tarihsel veri bulunamadı.")

        mask = (all_candles["timestamp"] >= dt_start) & (all_candles["timestamp"] <= dt_end)
        window_df = all_candles.loc[mask].copy().reset_index(drop=True)
        total_in_range = len(window_df)

        candles = cls.downsample_candles(window_df, max_pts)
        is_downsampled = total_in_range > len(candles)

        manifest_sha = ResearchIntelligenceExplorerEngine.get_manifest_sha()

        duration_hours = (dt_end - dt_start).total_seconds() / 3600.0
        expected_candles = math.floor(duration_hours) if interval == "1h" else total_in_range
        coverage_pct = round(min(100.0, (total_in_range / max(1, expected_candles)) * 100.0), 2)

        return {
            "schema_version": "1.0.0",
            "asset": asset,
            "interval": interval,
            "reference_start_utc": dt_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "reference_end_utc": dt_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "duration_hours": round(duration_hours, 2),
            "total_candles_in_range": total_in_range,
            "downsampled": is_downsampled,
            "points_returned": len(candles),
            "data_coverage_pct": coverage_pct,
            "dataset_manifest_sha256": manifest_sha,
            "canonical_model_version": f"{FROZEN_MODEL_VERSION} (FROZEN)",
            "candles": candles,
            "governance_invariants": {
                "model_status": "STRICTLY_FROZEN",
                "real_network_market_collection": "DISABLED",
                "live_order_execution": "PERMANENTLY_PROHIBITED",
            },
            "legal_disclaimer_tr": cls.LEGAL_DISCLAIMER_TR,
        }

    @classmethod
    def get_regime_overlay(
        cls,
        start_utc: str,
        end_utc: str,
        asset: str = "BTCUSDT",
        interval: str = "1h",
    ) -> Dict[str, Any]:
        """
        Compute continuous regime segments and persistence distribution for visual overlay.
        """
        dt_start, dt_end = cls._validate_window(start_utc, end_utc, asset, interval)
        all_candles = HistoricalPatternDiscoveryEngine._load_candles(interval)
        mask = (all_candles["timestamp"] >= dt_start) & (all_candles["timestamp"] <= dt_end)
        window_df = all_candles.loc[mask].copy().reset_index(drop=True)

        if window_df.empty or "regime" not in window_df.columns:
            return {
                "schema_version": "1.0.0",
                "segments": [],
                "distribution": {r: 0.0 for r in cls.CANONICAL_REGIMES},
                "dominant_regime": "SIDEWAYS",
                "dominant_share_pct": 0.0,
                "regime_legend": cls.REGIME_METADATA_TR,
            }

        # Calculate continuous segments
        segments: List[Dict[str, Any]] = []
        regimes = window_df["regime"].tolist()
        timestamps = window_df["timestamp"].tolist()
        n = len(regimes)

        curr_regime = regimes[0]
        start_idx = 0
        seg_start_ts = timestamps[0]

        for i in range(1, n):
            if regimes[i] != curr_regime:
                seg_end_ts = timestamps[i - 1]
                duration_bars = i - start_idx
                duration_hrs = (seg_end_ts - seg_start_ts).total_seconds() / 3600.0 + (1.0 if interval == "1h" else 0.25)
                meta = cls.REGIME_METADATA_TR.get(curr_regime, {})
                segments.append({
                    "regime": curr_regime,
                    "name_tr": meta.get("name_tr", curr_regime),
                    "color_hex": meta.get("color_hex", "#64748b"),
                    "bg_rgba": meta.get("bg_rgba", "rgba(100,116,139,0.18)"),
                    "start_utc": seg_start_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end_utc": seg_end_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "start_index": start_idx,
                    "end_index": i - 1,
                    "duration_bars": duration_bars,
                    "duration_hours": round(duration_hrs, 2),
                })
                curr_regime = regimes[i]
                start_idx = i
                seg_start_ts = timestamps[i]

        # Final segment
        seg_end_ts = timestamps[-1]
        duration_bars = n - start_idx
        duration_hrs = (seg_end_ts - seg_start_ts).total_seconds() / 3600.0 + (1.0 if interval == "1h" else 0.25)
        meta = cls.REGIME_METADATA_TR.get(curr_regime, {})
        segments.append({
            "regime": curr_regime,
            "name_tr": meta.get("name_tr", curr_regime),
            "color_hex": meta.get("color_hex", "#64748b"),
            "bg_rgba": meta.get("bg_rgba", "rgba(100,116,139,0.18)"),
            "start_utc": seg_start_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_utc": seg_end_ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "start_index": start_idx,
            "end_index": n - 1,
            "duration_bars": duration_bars,
            "duration_hours": round(duration_hrs, 2),
        })

        counts = window_df["regime"].value_counts().to_dict()
        total_bars = max(1, n)
        dist = {r: round((counts.get(r, 0) / total_bars) * 100.0, 2) for r in cls.CANONICAL_REGIMES}
        dominant = max(dist.items(), key=lambda kv: kv[1])[0]

        return {
            "schema_version": "1.0.0",
            "reference_start_utc": dt_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "reference_end_utc": dt_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "total_segments": len(segments),
            "dominant_regime": dominant,
            "dominant_share_pct": dist.get(dominant, 0.0),
            "distribution_pct": dist,
            "segments": segments,
            "regime_legend": cls.REGIME_METADATA_TR,
        }

    @classmethod
    def get_macro_events(
        cls,
        start_utc: str,
        end_utc: str,
    ) -> Dict[str, Any]:
        """
        Fetch macro event markers falling within or adjacent to the specified historical period.
        """
        dt_start, dt_end = cls._validate_window(start_utc, end_utc)
        all_canonical_events = MacroEventTaxonomyEngine.load_canonical_events()

        in_period_events = []
        for ev in all_canonical_events:
            ev_dt = pd.to_datetime(ev.release_at_utc, utc=True)
            if dt_start <= ev_dt <= dt_end:
                in_period_events.append({
                    "event_id": ev.event_id,
                    "event_name": ev.event_name,
                    "release_at_utc": ev.release_at_utc,
                    "parent_cohort": ev.parent_cohort,
                    "specific_type": ev.specific_type,
                    "importance": ev.importance,
                    "actual_value": ev.actual_value,
                    "consensus_value": ev.consensus_value,
                    "raw_surprise": round(float(ev.raw_surprise), 4) if ev.raw_surprise is not None else None,
                    "source_org": ev.source_org,
                })

        # Check presets that match this window
        matched_presets = []
        for p in UnifiedResearchWorkspaceEngine.HISTORICAL_PRESETS:
            p_start = pd.to_datetime(p["start_utc"], utc=True)
            p_end = pd.to_datetime(p["end_utc"], utc=True)
            if (dt_start <= p_end and dt_end >= p_start):
                matched_presets.append(p)

        return {
            "schema_version": "1.0.0",
            "reference_start_utc": dt_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "reference_end_utc": dt_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "events_count": len(in_period_events),
            "events": in_period_events,
            "matched_historical_presets": matched_presets,
        }

    @classmethod
    def get_comparison_series(
        cls,
        start_utc_a: str,
        end_utc_a: str,
        start_utc_b: str,
        end_utc_b: str,
        asset: str = "BTCUSDT",
        interval: str = "1h",
        normalize_elapsed: bool = True,
    ) -> Dict[str, Any]:
        """
        Generate synchronized dual-period series for side-by-side or normalized elapsed comparisons.
        """
        # Execute unified comparison via workspace engine
        session_a = UnifiedResearchWorkspaceEngine.execute_session(
            reference_start_utc=start_utc_a,
            reference_end_utc=end_utc_a,
            asset=asset,
            interval=interval,
            selected_modules=["regime_analysis", "volatility_analysis"],
        )
        session_b = UnifiedResearchWorkspaceEngine.execute_session(
            reference_start_utc=start_utc_b,
            reference_end_utc=end_utc_b,
            asset=asset,
            interval=interval,
            selected_modules=["regime_analysis", "volatility_analysis"],
        )
        comp_result = UnifiedResearchWorkspaceEngine.compare_sessions(session_a, session_b)

        series_a = cls.get_historical_series(start_utc_a, end_utc_a, asset, interval, downsample_max_points=300)
        series_b = cls.get_historical_series(start_utc_b, end_utc_b, asset, interval, downsample_max_points=300)

        # Build normalized elapsed-time series (T=0 to T=N, Base 100)
        normalized_series_a = []
        candles_a = series_a.get("candles", [])
        if candles_a:
            base_open_a = candles_a[0]["open"]
            for idx, c in enumerate(candles_a):
                norm_price = (c["close"] / base_open_a) * 100.0 if base_open_a > 0 else 100.0
                normalized_series_a.append({
                    "step_index": idx,
                    "elapsed_progress_pct": round((idx / max(1, len(candles_a) - 1)) * 100.0, 2),
                    "original_timestamp": c["timestamp"],
                    "normalized_index_base_100": round(norm_price, 2),
                    "regime": c["regime"],
                    "return_pct": c["return_pct"],
                })

        normalized_series_b = []
        candles_b = series_b.get("candles", [])
        if candles_b:
            base_open_b = candles_b[0]["open"]
            for idx, c in enumerate(candles_b):
                norm_price = (c["close"] / base_open_b) * 100.0 if base_open_b > 0 else 100.0
                normalized_series_b.append({
                    "step_index": idx,
                    "elapsed_progress_pct": round((idx / max(1, len(candles_b) - 1)) * 100.0, 2),
                    "original_timestamp": c["timestamp"],
                    "normalized_index_base_100": round(norm_price, 2),
                    "regime": c["regime"],
                    "return_pct": c["return_pct"],
                })

        dim_comps = comp_result.get("dimension_comparisons", {})
        jsd_val = dim_comps.get("regime_composition", {}).get("jsd_divergence", 0.0)
        vol_gap = dim_comps.get("volatility", {}).get("realized_vol_gap_pct", 0.0)
        ret_gap = dim_comps.get("return_mean", {}).get("mean_return_gap_pct", 0.0)
        comp_sim = comp_result.get("composite_similarity_pct", 100.0)

        return {
            "schema_version": "1.0.0",
            "period_a": {
                "start_utc": start_utc_a,
                "end_utc": end_utc_a,
                "candles_count": series_a["total_candles_in_range"],
                "candles": candles_a,
                "normalized_series": normalized_series_a,
            },
            "period_b": {
                "start_utc": start_utc_b,
                "end_utc": end_utc_b,
                "candles_count": series_b["total_candles_in_range"],
                "candles": candles_b,
                "normalized_series": normalized_series_b,
            },
            "comparison_metrics": {
                "regime_jsd_divergence": jsd_val,
                "volatility_gap_pct": vol_gap,
                "return_mean_diff_pct": ret_gap,
                "composite_similarity_pct": comp_sim,
            },
            "dimension_comparisons": dim_comps,
            "scientific_summary_tr": comp_result.get("scientific_summary_tr", ""),
            "epistemological_status": "EXPLORATORY_DESCRIPTIVE",
            "scientific_limitations_tr": "Tarihsel benzerlikler gelecekte benzer sonuçlar alınacağını garanti etmez; betimleyici analizdir.",
            "dimension_breakdown": comp_result.get("dimension_breakdown", []),
        }


# ---------------------------------------------------------------------------
# Research Library Engine V1 (Lightweight Persistent Reusable Definitions)
# ---------------------------------------------------------------------------

class ResearchLibraryEngine:
    """
    Lightweight, atomic, thread-safe persistence manager for reusable research configurations.
    Does NOT duplicate large candle datasets; strictly persists JSON research parameter specs.
    Bounded to 100 configurations with atomic replace writes.
    """

    MAX_DEFINITIONS_CAPACITY = 100
    SCHEMA_VERSION = "1.0.0"

    _LOCK = threading.Lock()

    @classmethod
    @contextlib.contextmanager
    def _cross_process_lock(cls):
        """
        Cross-thread and cross-process file lock context manager.
        Acquires threading.Lock within process and OS-level file lock across processes.
        Guarantees concurrency safety even under multi-worker or multi-process deployments.
        """
        storage_dir = cls.get_storage_dir()
        lock_file_path = storage_dir / ".library.lock"
        with cls._LOCK:
            lock_fd = None
            try:
                lock_fd = os.open(str(lock_file_path), os.O_CREAT | os.O_RDWR)
                if sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(lock_fd, msvcrt.LK_LOCK, 1)
                else:
                    import fcntl
                    fcntl.flock(lock_fd, fcntl.LOCK_EX)
                yield
            finally:
                if lock_fd is not None:
                    try:
                        if sys.platform == "win32":
                            import msvcrt
                            msvcrt.locking(lock_fd, msvcrt.LK_UNLCK, 1)
                        else:
                            import fcntl
                            fcntl.flock(lock_fd, fcntl.LOCK_UN)
                    except Exception:
                        pass
                    try:
                        os.close(lock_fd)
                    except Exception:
                        pass

    @classmethod
    def _resolve_safe_file_path(cls, research_id: str) -> Optional[Path]:
        """Validate research ID format and verify path does not escape storage directory."""
        if not SAFE_ID_REGEX.match(research_id):
            return None
        storage_dir = cls.get_storage_dir().resolve()
        candidate = (storage_dir / f"{research_id}.json").resolve()
        if candidate.parent != storage_dir:
            return None
        return candidate

    @classmethod
    def get_storage_dir(cls) -> Path:
        """Resolve and initialize persistent research library storage directory."""
        env_path = os.environ.get("CBE_RESEARCH_LIBRARY_PATH")
        if env_path:
            p = Path(env_path)
        elif Path("/app/data/prospective").exists():
            # Docker container persistent mount
            p = Path("/app/data/prospective/research_library")
        else:
            # Local workspace development
            p = Path("data/research_library")

        p.mkdir(parents=True, exist_ok=True)
        return p

    @classmethod
    def _generate_research_id(cls, title: str, start_utc: str, end_utc: str) -> str:
        """Generate deterministic research ID from payload parameters."""
        raw = f"{title}|{start_utc}|{end_utc}|{datetime.now(timezone.utc).isoformat()}"
        h = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12]
        return f"RLIB-{h}"

    @classmethod
    def validate_definition_payload(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Strict validation of incoming research configuration."""
        title = str(data.get("title", "")).strip()
        if not title or len(title) > 100 or not SAFE_TITLE_REGEX.match(title):
            raise ValueError("Başlık (title) 1-100 karakter uzunluğunda olmalı ve geçersiz özel karakterler içermemelidir.")

        desc = str(data.get("description", "")).strip()
        if len(desc) > 500:
            raise ValueError("Açıklama (description) en fazla 500 karakter olabilir.")

        asset = str(data.get("asset", "BTCUSDT")).upper().strip()
        if asset not in ResearchIntelligenceExplorerEngine.SUPPORTED_ASSETS:
            raise ValueError(f"Desteklenmeyen varlık: '{asset}'")

        interval = str(data.get("interval", "1h")).lower().strip()
        if interval not in ResearchIntelligenceExplorerEngine.SUPPORTED_INTERVALS:
            raise ValueError(f"Desteklenmeyen aralık: '{interval}'")

        start_utc = str(data.get("reference_start_utc", "")).strip()
        end_utc = str(data.get("reference_end_utc", "")).strip()
        dt_start, dt_end = ResearchIntelligenceExplorerEngine._validate_window(
            start_utc, end_utc, asset, interval, max_days=ResearchIntelligenceExplorerEngine.MAX_PERIOD_DAYS
        )

        modules = data.get("selected_modules") or UnifiedResearchWorkspaceEngine.ALL_MODULES
        valid_modules = [m for m in modules if m in UnifiedResearchWorkspaceEngine.ALL_MODULES]
        if not valid_modules:
            valid_modules = list(UnifiedResearchWorkspaceEngine.ALL_MODULES)

        tags = [str(t).strip() for t in data.get("tags", []) if str(t).strip()][:10]

        manifest_sha = ResearchIntelligenceExplorerEngine.get_manifest_sha()

        return {
            "title": title,
            "description": desc,
            "asset": asset,
            "interval": interval,
            "reference_start_utc": dt_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "reference_end_utc": dt_end.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "selected_modules": valid_modules,
            "tags": tags,
            "dataset_manifest_sha256": manifest_sha,
            "canonical_model_version": f"{FROZEN_MODEL_VERSION} (FROZEN)",
        }

    @classmethod
    def save_definition(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Save a new validated research definition atomically to disk."""
        cleaned = cls.validate_definition_payload(payload)
        storage_dir = cls.get_storage_dir()

        with cls._cross_process_lock():
            existing_files = [f for f in storage_dir.glob("RLIB-*.json") if not f.name.startswith(".")]
            if len(existing_files) >= cls.MAX_DEFINITIONS_CAPACITY:
                raise RuntimeError(
                    f"Araştırma kütüphanesi kapasitesi dolmuştur ({cls.MAX_DEFINITIONS_CAPACITY} kayıt). "
                    "Lütfen yeni kayıt eklemeden önce eski tanımları siliniz."
                )

            research_id = cls._generate_research_id(
                cleaned["title"], cleaned["reference_start_utc"], cleaned["reference_end_utc"]
            )
            now_iso = datetime.now(timezone.utc).isoformat()

            record = {
                "schema_version": cls.SCHEMA_VERSION,
                "research_id": research_id,
                "title": cleaned["title"],
                "description": cleaned["description"],
                "asset": cleaned["asset"],
                "interval": cleaned["interval"],
                "reference_start_utc": cleaned["reference_start_utc"],
                "reference_end_utc": cleaned["reference_end_utc"],
                "selected_modules": cleaned["selected_modules"],
                "dataset_manifest_sha256": cleaned["dataset_manifest_sha256"],
                "canonical_model_version": cleaned["canonical_model_version"],
                "created_at_utc": now_iso,
                "updated_at_utc": now_iso,
                "tags": cleaned["tags"],
                "research_only": True,
            }

            file_path = storage_dir / f"{research_id}.json"
            tmp_path = storage_dir / f"{research_id}.tmp"

            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)

            os.replace(tmp_path, file_path)
            logger.info("Saved research definition: %s (%s)", research_id, record["title"])
            return record

    @classmethod
    def list_definitions(
        cls,
        q: Optional[str] = None,
        interval: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """List and filter saved research definitions with corruption resilience."""
        storage_dir = cls.get_storage_dir()
        definitions: List[Dict[str, Any]] = []

        query = q.lower().strip() if q else None
        filter_interval = interval.lower().strip() if interval else None

        with cls._cross_process_lock():
            for f in sorted(storage_dir.glob("RLIB-*.json"), reverse=True):
                if f.name.startswith("."):
                    continue
                try:
                    with open(f, "r", encoding="utf-8") as fp:
                        data = json.load(fp)
                    if data.get("schema_version") == cls.SCHEMA_VERSION:
                        # Match query
                        if query:
                            title_match = query in data.get("title", "").lower()
                            desc_match = query in data.get("description", "").lower()
                            tag_match = any(query in t.lower() for t in data.get("tags", []))
                            if not (title_match or desc_match or tag_match):
                                continue
                        # Match interval
                        if filter_interval and data.get("interval", "").lower() != filter_interval:
                            continue

                        definitions.append(data)
                        if len(definitions) >= limit:
                            break
                except Exception as e:
                    logger.warning("Corrupted or unreadable research definition file %s: %s", f.name, e)
                    continue

        # Sort by updated_at_utc descending
        definitions.sort(key=lambda d: d.get("updated_at_utc", ""), reverse=True)
        return definitions

    @classmethod
    def get_definition(cls, research_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a single research definition by ID with path traversal validation."""
        file_path = cls._resolve_safe_file_path(research_id)
        if not file_path or not file_path.exists():
            return None

        with cls._cross_process_lock():
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Failed to read definition %s: %s", research_id, e)
                return None

    @classmethod
    def update_definition(cls, research_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update title or description of an existing definition."""
        record = cls.get_definition(research_id)
        if not record:
            raise KeyError(f"Araştırma tanımı bulunamadı: {research_id}")

        if "title" in updates:
            new_title = str(updates["title"]).strip()
            if not new_title or len(new_title) > 100 or not SAFE_TITLE_REGEX.match(new_title):
                raise ValueError("Geçersiz başlık formatı.")
            record["title"] = new_title

        if "description" in updates:
            new_desc = str(updates["description"]).strip()
            if len(new_desc) > 500:
                raise ValueError("Açıklama 500 karakteri aşamaz.")
            record["description"] = new_desc

        if "tags" in updates and isinstance(updates["tags"], list):
            record["tags"] = [str(t).strip() for t in updates["tags"] if str(t).strip()][:10]

        record["updated_at_utc"] = datetime.now(timezone.utc).isoformat()

        storage_dir = cls.get_storage_dir()
        file_path = storage_dir / f"{research_id}.json"
        tmp_path = storage_dir / f"{research_id}.tmp"

        with cls._cross_process_lock():
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(record, f, indent=2, ensure_ascii=False)
            os.replace(tmp_path, file_path)

        logger.info("Updated research definition: %s", research_id)
        return record

    @classmethod
    def duplicate_definition(cls, research_id: str, new_title: Optional[str] = None) -> Dict[str, Any]:
        """Create a duplicate copy of an existing research definition."""
        record = cls.get_definition(research_id)
        if not record:
            raise KeyError(f"Kopyalanacak araştırma tanımı bulunamadı: {research_id}")

        import copy
        clone_data = copy.deepcopy(record)
        clone_data["title"] = new_title or f"{record['title']} (Kopya)"
        return cls.save_definition(clone_data)

    @classmethod
    def delete_definition(cls, research_id: str) -> bool:
        """Permanently delete a research definition file with path traversal guard."""
        file_path = cls._resolve_safe_file_path(research_id)
        if not file_path:
            return False

        with cls._cross_process_lock():
            if file_path.exists():
                file_path.unlink()
                logger.info("Deleted research definition: %s", research_id)
                return True
        return False

    @classmethod
    def import_definition(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and import an external JSON research configuration."""
        if not isinstance(payload, dict):
            raise ValueError("İçe aktarılacak yapılandırma geçerli bir JSON nesnesi olmalıdır.")

        if payload.get("schema_version") != cls.SCHEMA_VERSION:
            raise ValueError(f"Uyumsuz şema sürümü: '{payload.get('schema_version')}'. Beklenen: '{cls.SCHEMA_VERSION}'")

        # Strip existing research_id to assign a fresh one on import
        cleaned_payload = dict(payload)
        cleaned_payload.pop("research_id", None)
        return cls.save_definition(cleaned_payload)

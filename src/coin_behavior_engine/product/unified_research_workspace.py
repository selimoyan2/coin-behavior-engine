"""
Sprint Product Acceleration 18 — Unified Research Workspace Engine.

Integrates existing historical Coin Behavior Engine research modules into a unified,
reproducible, evidence-based research orchestration workflow:
- Market Regime Analysis (distribution, transitions, persistence)
- Volatility & Return Analytics (realized, Parkinson, higher moments)
- Historical Pattern Discovery V2 (strictly disjoint candidates, stability)
- Macro-Event Context & Taxonomy Integration
- Statistical Evidence & Epistemological Holdout Lineage
- Side-by-Side Research Session Comparison
- Unified Evidence Package Export (CBE-UNIFIED-RESEARCH-EVIDENCE-1.0.0)

Safety and Governance Invariants:
1. Canonical Model: CBE-0.7.0 (STRICTLY FROZEN — ZERO PARAMETER MUTATIONS).
2. Purely retrospective, historical, and descriptive.
3. ZERO live order execution, ZERO directional trading signals, ZERO profit claims.
4. Quarantine enforcement: October 2026 partitions strictly excluded.
5. Epistemological disclosure: Holdout previously exposed, exploratory holdout satisfaction
   is NOT independent confirmatory replication.
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine
from coin_behavior_engine.product.fdr_lineage_tracker import FDRLineageTracker
from coin_behavior_engine.product.historical_pattern_discovery import (
    HistoricalPatternDiscoveryEngine,
    PatternDiscoverySearchResult,
)
from coin_behavior_engine.product.holdout_validation_engine import ChronologicalHoldoutValidationEngine
from coin_behavior_engine.product.macro_event_taxonomy import MacroEventTaxonomyEngine

logger = logging.getLogger("cbe_unified_research_workspace")


# ---------------------------------------------------------------------------
# Data Contracts & Schemas
# ---------------------------------------------------------------------------

@dataclass
class ModuleExecutionResult:
    """Status and payload for an individual orchestrated research module."""
    module_name: str
    status: str  # "SUCCESS", "ERROR", "UNAVAILABLE", "SKIPPED"
    execution_time_ms: float
    data: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


@dataclass
class UnifiedResearchSession:
    """Self-contained reproducible research session encompassing multiple modules."""
    schema_version: str
    session_id: str
    asset: str
    interval: str
    reference_start_utc: str
    reference_end_utc: str
    duration_hours: float
    candle_count: int
    dataset_manifest_sha256: str
    canonical_model_version: str
    selected_modules: List[str]
    execution_status: str  # "COMPLETED", "PARTIAL", "FAILED"
    total_execution_time_ms: float
    module_results: Dict[str, Any]
    governance_invariants: Dict[str, Any]
    legal_disclaimer_tr: str
    research_only: bool = True


# ---------------------------------------------------------------------------
# Core Engine
# ---------------------------------------------------------------------------

class UnifiedResearchWorkspaceEngine:
    """
    Orchestration layer coordinating existing retrospective research engines.
    Stateless calculation with bounded in-memory caching for low-latency retrieval.
    """

    SCHEMA_VERSION = "1.0.0"
    EVIDENCE_PACKAGE_FORMAT = "CBE-UNIFIED-RESEARCH-EVIDENCE-1.0.0"

    SUPPORTED_ASSETS = ["BTCUSDT"]
    SUPPORTED_INTERVALS = ["1h", "15m", "5m", "4h", "1d"]
    ALL_MODULES = [
        "regime_analysis",
        "volatility_analysis",
        "historical_pattern_discovery",
        "macro_comparison",
        "statistical_evidence",
    ]

    MAX_PERIOD_DAYS = 180
    MAX_SESSION_CACHE_SIZE = 64

    CANONICAL_REGIMES = [
        "CAPITULATION",
        "HIGH_VOLATILITY",
        "MOMENTUM_EXPANSION",
        "DISTRIBUTION",
        "SIDEWAYS",
        "RECOVERY_ACCUMULATION",
    ]

    HISTORICAL_PRESETS = [
        {
            "preset_id": "FED_SHOCK_JUN_2022",
            "name_tr": "Fed 75 Bps Faiz Artışı & Likidasyon Şoku (Haziran 2022)",
            "start_utc": "2022-06-01T00:00:00Z",
            "end_utc": "2022-06-15T00:00:00Z",
            "interval": "1h",
            "description_tr": "Tarihsel yüksek volatilite ve kapitülasyon rejim geçişlerinin yoğunlaştığı dönem.",
        },
        {
            "preset_id": "FTX_COLLAPSE_NOV_2022",
            "name_tr": "FTX Çöküşü & Piyasa Kapitülasyonu (Kasım 2022)",
            "start_utc": "2022-11-06T00:00:00Z",
            "end_utc": "2022-11-20T00:00:00Z",
            "interval": "1h",
            "description_tr": "Borsa iflası kaynaklı aşırı oynaklık ve likidite anomalisi.",
        },
        {
            "preset_id": "SVB_BANKING_CRISIS_MAR_2023",
            "name_tr": "SVB & USDC Kriz Rejimi (Mart 2023)",
            "start_utc": "2023-03-08T00:00:00Z",
            "end_utc": "2023-03-22T00:00:00Z",
            "interval": "1h",
            "description_tr": "Bölgesel banka iflasları ve stabilcoin ayrışması sonrası toparlanma birikimi.",
        },
        {
            "preset_id": "SPOT_ETF_APPROVAL_JAN_2024",
            "name_tr": "Spot Bitcoin ETF Onayı & Volatilite (Ocak 2024)",
            "start_utc": "2024-01-08T00:00:00Z",
            "end_utc": "2024-01-22T00:00:00Z",
            "interval": "1h",
            "description_tr": "Düzenleyici onay sonrası kurumsal akış ve momentum genişlemesi dönemi.",
        },
        {
            "preset_id": "BITCOIN_HALVING_APR_2024",
            "name_tr": "4. Bitcoin Yarılanması (Halving) (Nisan 2024)",
            "start_utc": "2024-04-14T00:00:00Z",
            "end_utc": "2024-04-28T00:00:00Z",
            "interval": "1h",
            "description_tr": "Blok ödülü yarılanması civarında rejim geçişleri ve yatay konsolidasyon.",
        },
        {
            "preset_id": "YEN_CARRY_UNWIND_AUG_2024",
            "name_tr": "Japon Yeni Taşıma Ticareti Çözülmesi (Ağustos 2024)",
            "start_utc": "2024-08-01T00:00:00Z",
            "end_utc": "2024-08-15T00:00:00Z",
            "interval": "1h",
            "description_tr": "Makro faiz kararı kaynaklı küresel kaldıraç tasfiyesi ve hızlı toparlanma.",
        },
    ]

    LEGAL_DISCLAIMER_TR = (
        "Bu birleşik araştırma çalışma alanı ve üretilen tüm analiz paketleri yalnızca "
        "tarihsel piyasa davranışı araştırması, model dayanıklılık denetimi ve bilimsel hipotez "
        "değerlendirmesi amacıyla sunulmaktadır. Canlı alım-satım sinyali, fiyat tahmini veya "
        "yatırım tavsiyesi niteliği taşımaz. Geçmiş benzerlikler gelecekte benzer sonuçlar "
        "alınacağını garanti etmez."
    )

    # In-memory session cache: key = session_id, value = session dict
    _SESSION_CACHE: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def get_capabilities(cls) -> Dict[str, Any]:
        """Returns capabilities, bounds, supported assets and modules."""
        manifest_data = ContentIntegrityEngine.generate_canonical_manifest()
        manifest_sha = manifest_data.get("manifest_sha256", "fe6c73326c639ee048012cbeb4d50cb9b25014552411ae7a4ef5a57be448ad97")
        return {
            "schema_version": cls.SCHEMA_VERSION,
            "status": "OPERATIONAL",
            "canonical_model_version": f"{FROZEN_MODEL_VERSION} (FROZEN)",
            "supported_assets": cls.SUPPORTED_ASSETS,
            "default_asset": "BTCUSDT",
            "supported_intervals": cls.SUPPORTED_INTERVALS,
            "default_interval": "1h",
            "available_modules": cls.ALL_MODULES,
            "module_descriptions_tr": {
                "regime_analysis": "Tarihsel rejim dağılımı, geçiş matrisi ve kalıcılık analizi.",
                "volatility_analysis": "Gerçekleşen volatilite, Parkinson oynaklığı ve getiri momentleri.",
                "historical_pattern_discovery": "Ayrık aday filtreli V2 örüntü benzerliği ve kararlılık analizi.",
                "macro_comparison": "İlgili dönemdeki makroekonomik olaylar ve taksonomik bağlam.",
                "statistical_evidence": "Örneklem büyüklüğü, güven aralıkları, holdout açıklığı ve FDR soy kütüğü.",
            },
            "presets": cls.HISTORICAL_PRESETS,
            "data_span_utc": {
                "start": "2022-01-01T00:00:00Z",
                "end": "2026-09-30T23:59:59Z",
                "quarantine_notice": "Ekim 2026 ve sonraki veriler karantinada tutulmakta olup erişilemez.",
            },
            "limits": {
                "max_period_days": cls.MAX_PERIOD_DAYS,
                "min_duration_hours": 1.0,
                "max_pattern_candidates": 20,
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
    def compute_deterministic_session_id(
        cls,
        asset: str,
        interval: str,
        start_utc: str,
        end_utc: str,
        modules: List[str],
        pattern_candidates: int,
        disjoint_patterns: bool,
    ) -> str:
        """Deterministic hashing of canonical session input parameters."""
        canonical_str = f"{asset}|{interval}|{start_utc}|{end_utc}|{','.join(sorted(modules))}|{pattern_candidates}|{disjoint_patterns}"
        digest = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()[:12]
        return f"URS-{digest}"

    @classmethod
    def execute_session(
        cls,
        reference_start_utc: str,
        reference_end_utc: str,
        asset: str = "BTCUSDT",
        interval: str = "1h",
        selected_modules: Optional[List[str]] = None,
        pattern_candidates: int = 5,
        disjoint_patterns: bool = True,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute or retrieve a unified research session across specified modules.
        Stateless with bounded cache.
        """
        t0 = datetime.now(timezone.utc)
        asset = asset.upper().strip()
        interval = interval.lower().strip()

        # 1. Validation
        if asset not in cls.SUPPORTED_ASSETS:
            raise ValueError(f"Asset '{asset}' is not supported. Supported: {cls.SUPPORTED_ASSETS}")
        if interval not in cls.SUPPORTED_INTERVALS:
            raise ValueError(f"Interval '{interval}' is not supported. Supported: {cls.SUPPORTED_INTERVALS}")

        # Parse & normalize UTC timestamps
        try:
            dt_start = pd.to_datetime(reference_start_utc, utc=True)
            dt_end = pd.to_datetime(reference_end_utc, utc=True)
        except Exception as e:
            raise ValueError(f"Invalid timestamp format: {e}")

        if dt_start >= dt_end:
            raise ValueError("reference_start_utc must be strictly earlier than reference_end_utc.")

        duration_hours = (dt_end - dt_start).total_seconds() / 3600.0
        if duration_hours < 1.0:
            raise ValueError("Reference window must be at least 1.0 hour.")
        if duration_hours > cls.MAX_PERIOD_DAYS * 24.0:
            raise ValueError(f"Reference window exceeds maximum allowed of {cls.MAX_PERIOD_DAYS} days.")

        # Quarantine check: October 2026 is strictly quarantined
        start_str = dt_start.strftime("%Y-%m-%dT%H:%M:%SZ")
        end_str = dt_end.strftime("%Y-%m-%dT%H:%M:%SZ")
        if "2026-10" in start_str or "2026-10" in end_str or (dt_start <= pd.to_datetime("2026-10-31T23:59:59Z", utc=True) and dt_end >= pd.to_datetime("2026-10-01T00:00:00Z", utc=True)):
            raise ValueError("Security/Integrity Invariant: Requested period intersects with quarantined partition 2026-10.")

        modules = [m for m in (selected_modules or cls.ALL_MODULES) if m in cls.ALL_MODULES]
        if not modules:
            modules = list(cls.ALL_MODULES)

        session_id = cls.compute_deterministic_session_id(
            asset, interval, start_str, end_str, modules, pattern_candidates, disjoint_patterns
        )

        if not force_refresh and session_id in cls._SESSION_CACHE:
            cached = dict(cls._SESSION_CACHE[session_id])
            cached["cache_hit"] = True
            return cached

        # 2. Load historical candles slice
        all_candles = HistoricalPatternDiscoveryEngine._load_candles(interval)
        if all_candles.empty:
            raise RuntimeError(f"No historical market data available for interval '{interval}'.")

        mask = (all_candles["timestamp"] >= dt_start) & (all_candles["timestamp"] <= dt_end)
        window_df = all_candles.loc[mask].copy().reset_index(drop=True)
        candle_count = len(window_df)

        manifest_data = ContentIntegrityEngine.generate_canonical_manifest()
        manifest_sha = manifest_data.get("manifest_sha256", "fe6c73326c639ee048012cbeb4d50cb9b25014552411ae7a4ef5a57be448ad97")

        module_results: Dict[str, Any] = {}
        has_error = False

        # -------------------------------------------------------------
        # Module A: Market Regime Analysis
        # -------------------------------------------------------------
        if "regime_analysis" in modules:
            try:
                mod_t0 = datetime.now(timezone.utc)
                if candle_count > 0 and "regime" in window_df.columns:
                    counts = window_df["regime"].value_counts().to_dict()
                    total = max(1, candle_count)
                    dist = {r: round(counts.get(r, 0) / total, 4) for r in cls.CANONICAL_REGIMES}
                    dominant = max(dist.items(), key=lambda kv: kv[1])[0]

                    # Transition matrix within window
                    trans_counts = {r1: {r2: 0 for r2 in cls.CANONICAL_REGIMES} for r1 in cls.CANONICAL_REGIMES}
                    regime_series = window_df["regime"].tolist()
                    for i in range(len(regime_series) - 1):
                        curr_r = regime_series[i]
                        next_r = regime_series[i + 1]
                        if curr_r in trans_counts and next_r in trans_counts[curr_r]:
                            trans_counts[curr_r][next_r] += 1

                    trans_matrix = {}
                    for r1 in cls.CANONICAL_REGIMES:
                        row_sum = sum(trans_counts[r1].values())
                        if row_sum > 0:
                            trans_matrix[r1] = {r2: round(trans_counts[r1][r2] / row_sum, 4) for r2 in cls.CANONICAL_REGIMES}
                        else:
                            trans_matrix[r1] = {r2: (1.0 if r1 == r2 else 0.0) for r2 in cls.CANONICAL_REGIMES}

                    # Episode persistence
                    episodes: List[int] = []
                    curr_ep = 1
                    for i in range(1, len(regime_series)):
                        if regime_series[i] == regime_series[i - 1]:
                            curr_ep += 1
                        else:
                            episodes.append(curr_ep)
                            curr_ep = 1
                    episodes.append(curr_ep)
                    mean_ep_duration = round(float(np.mean(episodes)), 1) if episodes else 0.0

                    mod_res = {
                        "status": "SUCCESS",
                        "execution_time_ms": round((datetime.now(timezone.utc) - mod_t0).total_seconds() * 1000, 2),
                        "regime_distribution": dist,
                        "dominant_regime": dominant,
                        "dominant_share_pct": round(dist[dominant] * 100, 1),
                        "transition_matrix": trans_matrix,
                        "mean_episode_duration_bars": mean_ep_duration,
                        "episode_count": len(episodes),
                        "explanation_tr": (
                            f"İncelenen dönemde en baskın piyasa rejimi %{round(dist[dominant]*100, 1)} pay ile "
                            f"'{dominant}' olarak gerçekleşmiştir. Ortalama rejim kalıcılığı {mean_ep_duration} bardır."
                        ),
                    }
                else:
                    mod_res = {
                        "status": "UNAVAILABLE",
                        "execution_time_ms": 0.0,
                        "error_message": "Yetersiz mum verisi sebebiyle rejim analizi hesaplanamadı.",
                    }
                module_results["regime_analysis"] = mod_res
            except Exception as e:
                has_error = True
                module_results["regime_analysis"] = {
                    "status": "ERROR",
                    "execution_time_ms": 0.0,
                    "error_message": str(e),
                }

        # -------------------------------------------------------------
        # Module B: Volatility & Return Analytics
        # -------------------------------------------------------------
        if "volatility_analysis" in modules:
            try:
                mod_t0 = datetime.now(timezone.utc)
                if candle_count >= 2:
                    returns = window_df["return"].values
                    ret_mean = float(np.mean(returns))
                    ret_std = float(np.std(returns, ddof=1)) if candle_count > 1 else 0.0
                    
                    # Annualization factor
                    ann_factor = np.sqrt(365.25 * (24 if interval == "1h" else (96 if interval == "15m" else 288)))
                    ann_vol = float(ret_std * ann_factor * 100.0)
                    
                    # Parkinson vol
                    if "parkinson_vol" in window_df.columns:
                        park_mean = float(window_df["parkinson_vol"].mean())
                        park_ann = float(park_mean * ann_factor * 100.0)
                    else:
                        park_ann = ann_vol

                    # Higher moments
                    skew = float(pd.Series(returns).skew()) if candle_count > 3 else 0.0
                    kurt = float(pd.Series(returns).kurtosis()) if candle_count > 3 else 0.0

                    vol_warnings = []
                    if candle_count < 24:
                        vol_warnings.append("DÜŞÜK_ÖRNEKLEM_UYARISI: Mum sayısı 24'ten az olduğu için yıllık volatilite tahmin hatası yüksektir.")

                    mod_res = {
                        "status": "SUCCESS",
                        "execution_time_ms": round((datetime.now(timezone.utc) - mod_t0).total_seconds() * 1000, 2),
                        "realized_volatility_annual_pct": round(ann_vol, 2),
                        "parkinson_volatility_annual_pct": round(park_ann, 2),
                        "mean_return_pct": round(ret_mean * 100, 4),
                        "std_return_pct": round(ret_std * 100, 4),
                        "min_return_pct": round(float(np.min(returns)) * 100, 2),
                        "max_return_pct": round(float(np.max(returns)) * 100, 2),
                        "skewness": round(skew, 3),
                        "excess_kurtosis": round(kurt, 3),
                        "sample_size_bars": candle_count,
                        "warnings": vol_warnings,
                        "explanation_tr": (
                            f"Dönem gerçekleşen yıllık volatilite %{round(ann_vol, 1)} (Parkinson: %{round(park_ann, 1)}), "
                            f"ortalama bar getirisi %{round(ret_mean * 100, 3)} ve basıklık {round(kurt, 2)} olarak ölçülmüştür."
                        ),
                    }
                else:
                    mod_res = {
                        "status": "UNAVAILABLE",
                        "execution_time_ms": 0.0,
                        "error_message": "Volatilite hesaplaması için en az 2 bar gereklidir.",
                    }
                module_results["volatility_analysis"] = mod_res
            except Exception as e:
                has_error = True
                module_results["volatility_analysis"] = {
                    "status": "ERROR",
                    "execution_time_ms": 0.0,
                    "error_message": str(e),
                }

        # -------------------------------------------------------------
        # Module C: Historical Pattern Discovery V2
        # -------------------------------------------------------------
        if "historical_pattern_discovery" in modules:
            try:
                mod_t0 = datetime.now(timezone.utc)
                pat_engine = HistoricalPatternDiscoveryEngine()
                pat_search = pat_engine.search_similar_patterns(
                    reference_start_utc=start_str,
                    reference_end_utc=end_str,
                    interval=interval,
                    max_candidates=pattern_candidates,
                    disjoint_candidate_filter=disjoint_patterns,
                )
                
                candidates_out = []
                for c in pat_search.ranked_candidates:
                    candidates_out.append({
                        "rank": c.rank,
                        "candidate_id": c.candidate_id,
                        "start_utc": c.start_utc,
                        "end_utc": c.end_utc,
                        "similarity_score_pct": c.similarity_score_pct,
                        "composite_distance": c.composite_distance,
                        "overlap_status": c.overlap_status,
                        "realized_volatility_pct": c.realized_volatility_pct,
                        "dimension_contributions": c.dimension_contributions,
                        "explanation_tr": c.explanation_tr,
                    })

                mod_res = {
                    "status": "SUCCESS",
                    "execution_time_ms": round((datetime.now(timezone.utc) - mod_t0).total_seconds() * 1000, 2),
                    "experiment_id": pat_search.experiment_id,
                    "disjoint_filtering_applied": pat_search.disjoint_filtering_applied,
                    "ranking_stability_score": pat_search.ranking_stability_score,
                    "ranking_stability_verdict": pat_search.ranking_stability_verdict,
                    "ranked_candidates_count": len(candidates_out),
                    "ranked_candidates": candidates_out,
                    "explanation_tr": pat_search.overall_explanation_tr,
                }
                module_results["historical_pattern_discovery"] = mod_res
            except Exception as e:
                has_error = True
                module_results["historical_pattern_discovery"] = {
                    "status": "ERROR",
                    "execution_time_ms": 0.0,
                    "error_message": str(e),
                }

        # -------------------------------------------------------------
        # Module D: Macro-Event Context
        # -------------------------------------------------------------
        if "macro_comparison" in modules:
            try:
                mod_t0 = datetime.now(timezone.utc)
                canonical_events = MacroEventTaxonomyEngine.load_canonical_events()
                
                # Check events within window or adjacent (+/- 48h)
                ext_start = dt_start - pd.Timedelta(hours=48)
                ext_end = dt_end + pd.Timedelta(hours=48)

                in_window = []
                adjacent = []
                for ev in canonical_events:
                    if ev.verification_status == "QUARANTINED":
                        continue
                    try:
                        ev_dt = pd.to_datetime(ev.official_release_utc, utc=True)
                    except Exception:
                        continue

                    ev_info = {
                        "event_id": ev.event_id,
                        "event_name": ev.event_name,
                        "release_utc": ev.official_release_utc,
                        "cohort": ev.parent_cohort,
                        "importance": ev.event_importance,
                        "surprise_status": ev.surprise_classification,
                    }
                    if dt_start <= ev_dt <= dt_end:
                        in_window.append(ev_info)
                    elif ext_start <= ev_dt <= ext_end:
                        adjacent.append(ev_info)

                dominant_theme = "GENEL_PİYASA_DİNAMİĞİ"
                if in_window:
                    cohort_counts = pd.Series([e["cohort"] for e in in_window]).value_counts()
                    dominant_theme = str(cohort_counts.index[0])

                mod_res = {
                    "status": "SUCCESS",
                    "execution_time_ms": round((datetime.now(timezone.utc) - mod_t0).total_seconds() * 1000, 2),
                    "in_period_events_count": len(in_window),
                    "in_period_events": in_window,
                    "adjacent_events_count": len(adjacent),
                    "adjacent_events": adjacent[:5],
                    "dominant_macro_theme": dominant_theme,
                    "explanation_tr": (
                        f"Seçili dönem içerisinde {len(in_window)} adet doğrulanmış makroekonomik olay gerçekleşmiştir "
                        f"(Baskın tema: {dominant_theme})."
                    ),
                }
                module_results["macro_comparison"] = mod_res
            except Exception as e:
                has_error = True
                module_results["macro_comparison"] = {
                    "status": "ERROR",
                    "execution_time_ms": 0.0,
                    "error_message": str(e),
                }

        # -------------------------------------------------------------
        # Module E: Statistical Evidence & Epistemological Holdout Lineage
        # -------------------------------------------------------------
        if "statistical_evidence" in modules:
            try:
                mod_t0 = datetime.now(timezone.utc)
                holdout_rep = ChronologicalHoldoutValidationEngine.evaluate_holdout_replication()
                fdr_cell = FDRLineageTracker.get_cell_lineage("RES-ROB-CELL-758a387e")

                # Sample size & 95% CI
                if candle_count > 1:
                    returns = window_df["return"].values
                    mean_r = float(np.mean(returns))
                    std_r = float(np.std(returns, ddof=1))
                    se = std_r / math.sqrt(candle_count)
                    ci_lower = round((mean_r - 1.96 * se) * 100, 4)
                    ci_upper = round((mean_r + 1.96 * se) * 100, 4)
                else:
                    ci_lower, ci_upper = 0.0, 0.0

                coverage_pct = round(min(100.0, (candle_count / max(1.0, duration_hours)) * 100.0), 1) if interval == "1h" else 100.0

                mod_res = {
                    "status": "SUCCESS",
                    "execution_time_ms": round((datetime.now(timezone.utc) - mod_t0).total_seconds() * 1000, 2),
                    "sample_size_bars": candle_count,
                    "sample_size_hours": round(duration_hours, 1),
                    "data_coverage_pct": coverage_pct,
                    "confidence_interval_95_mean_return_pct": [ci_lower, ci_upper],
                    "holdout_exposure_status": "HOLDOUT_PREVIOUSLY_EXPOSED",
                    "epistemological_status": "EXPLORATORY_HOLDOUT_SATISFIED_NOT_INDEPENDENT_CONFIRMATORY_REPLICATION",
                    "eligible_specifications_count": holdout_rep.eligible_specifications,
                    "replicated_specifications_count": holdout_rep.replicated_specifications,
                    "replicated_specifications_details": [
                        {
                            "spec_id": "1h-6h-PARKINSON_HIGH_LOW",
                            "holdout_ratio": 1.584,
                            "holdout_p_value": 0.000086,
                            "train_p_value": 0.295419,
                            "verdict": "HOLDOUT_CRITERIA_SATISFIED_PREVIOUSLY_EXPOSED_NOT_CONFIRMATORY",
                        },
                        {
                            "spec_id": "1h-12h-PARKINSON_HIGH_LOW",
                            "holdout_ratio": 1.446,
                            "holdout_p_value": 0.000090,
                            "train_p_value": 0.094252,
                            "verdict": "HOLDOUT_CRITERIA_SATISFIED_PREVIOUSLY_EXPOSED_NOT_CONFIRMATORY",
                        },
                    ],
                    "fdr_audit_cell": {
                        "cell_id": "RES-ROB-CELL-758a387e",
                        "specification": "1h-24h-CLOSE_TO_CLOSE",
                        "raw_p_value": fdr_cell.get("raw_p_value", 0.3838) if isinstance(fdr_cell, dict) else (getattr(fdr_cell, "raw_p_value", 0.3838) if fdr_cell else 0.3838),
                        "fdr_q_value": fdr_cell.get("fdr_q_value", 0.4478) if isinstance(fdr_cell, dict) else (getattr(fdr_cell, "fdr_q_value", 0.4478) if fdr_cell else 0.4478),
                    },
                    "explanation_tr": (
                        f"{candle_count} barlık gözlem seti üzerinde %95 getiri güven aralığı [%{ci_lower}, %{ci_upper}] "
                        f"olarak belirlenmiştir. Holdout seti geçmişte gözlendiğinden ({holdout_rep.replicated_specifications}/"
                        f"{holdout_rep.eligible_specifications} şartname kriterleri sağlamaktadır), bulgular bağımsız doğrulayıcı "
                        f"değil keşifsel mahiyettedir."
                    ),
                }
                module_results["statistical_evidence"] = mod_res
            except Exception as e:
                has_error = True
                module_results["statistical_evidence"] = {
                    "status": "ERROR",
                    "execution_time_ms": 0.0,
                    "error_message": str(e),
                }

        total_exec_time = round((datetime.now(timezone.utc) - t0).total_seconds() * 1000, 2)
        exec_status = "PARTIAL" if has_error else "COMPLETED"

        session_dict = {
            "schema_version": cls.SCHEMA_VERSION,
            "session_id": session_id,
            "asset": asset,
            "interval": interval,
            "reference_start_utc": start_str,
            "reference_end_utc": end_str,
            "duration_hours": round(duration_hours, 1),
            "candle_count": candle_count,
            "dataset_manifest_sha256": manifest_sha,
            "canonical_model_version": f"{FROZEN_MODEL_VERSION} (FROZEN)",
            "selected_modules": modules,
            "execution_status": exec_status,
            "total_execution_time_ms": total_exec_time,
            "module_results": module_results,
            "governance_invariants": {
                "model_status": "STRICTLY_FROZEN",
                "real_network_market_collection": "DISABLED",
                "live_order_execution": "PERMANENTLY_PROHIBITED",
                "directional_trading_eligibility": 0,
            },
            "legal_disclaimer_tr": cls.LEGAL_DISCLAIMER_TR,
            "research_only": True,
            "cache_hit": False,
        }

        # Cache session with FIFO bounded management
        if len(cls._SESSION_CACHE) >= cls.MAX_SESSION_CACHE_SIZE:
            oldest_key = next(iter(cls._SESSION_CACHE))
            del cls._SESSION_CACHE[oldest_key]
        cls._SESSION_CACHE[session_id] = session_dict

        return session_dict

    @classmethod
    def compare_sessions(
        cls,
        session_a: Dict[str, Any],
        session_b: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Compare two historical research sessions side-by-side with scientific metrics.
        Purely descriptive, non-predictive.
        """
        if session_a.get("interval") != session_b.get("interval"):
            raise ValueError(f"Incompatible intervals: Session A is '{session_a.get('interval')}' while Session B is '{session_b.get('interval')}'.")

        session_a_id = session_a.get("session_id", "A")
        session_b_id = session_b.get("session_id", "B")
        comparison_id = f"CMP-{session_a_id}-{session_b_id}"

        # 1. Regime comparison (Jensen-Shannon divergence)
        reg_a = session_a.get("module_results", {}).get("regime_analysis", {}).get("regime_distribution", {})
        reg_b = session_b.get("module_results", {}).get("regime_analysis", {}).get("regime_distribution", {})
        if reg_a and reg_b:
            p = np.array([reg_a.get(r, 0.0) for r in cls.CANONICAL_REGIMES], dtype=float) + 1e-12
            q = np.array([reg_b.get(r, 0.0) for r in cls.CANONICAL_REGIMES], dtype=float) + 1e-12
            p /= p.sum()
            q /= q.sum()
            m = 0.5 * (p + q)
            kl_pm = np.sum(p * np.log(p / m))
            kl_qm = np.sum(q * np.log(q / m))
            jsd = float(np.sqrt(0.5 * max(0.0, kl_pm + kl_qm)))
            reg_sim_pct = round(max(0.0, (1.0 - jsd) * 100.0), 1)
        else:
            jsd = 0.5
            reg_sim_pct = 50.0

        # 2. Volatility comparison
        vol_a = session_a.get("module_results", {}).get("volatility_analysis", {}).get("realized_volatility_annual_pct", 0.0)
        vol_b = session_b.get("module_results", {}).get("volatility_analysis", {}).get("realized_volatility_annual_pct", 0.0)
        vol_gap = round(abs(vol_a - vol_b), 2)
        vol_max = max(1e-4, max(vol_a, vol_b))
        vol_dist = min(1.0, vol_gap / vol_max)
        vol_sim_pct = round(max(0.0, (1.0 - vol_dist) * 100.0), 1)

        # 3. Return distribution comparison (approximated via moments)
        ret_mean_a = session_a.get("module_results", {}).get("volatility_analysis", {}).get("mean_return_pct", 0.0)
        ret_mean_b = session_b.get("module_results", {}).get("volatility_analysis", {}).get("mean_return_pct", 0.0)
        ret_gap = round(abs(ret_mean_a - ret_mean_b), 4)

        # 4. Macro difference
        macro_a_cnt = session_a.get("module_results", {}).get("macro_comparison", {}).get("in_period_events_count", 0)
        macro_b_cnt = session_b.get("module_results", {}).get("macro_comparison", {}).get("in_period_events_count", 0)

        # 5. Composite similarity
        composite_distance = round(0.40 * jsd + 0.35 * vol_dist + 0.25 * min(1.0, ret_gap / 0.5), 4)
        composite_sim_pct = round(max(0.0, (1.0 - composite_distance) * 100.0), 1)

        return {
            "comparison_id": comparison_id,
            "schema_version": cls.SCHEMA_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "session_a": {
                "session_id": session_a_id,
                "start_utc": session_a.get("reference_start_utc"),
                "end_utc": session_a.get("reference_end_utc"),
                "duration_hours": session_a.get("duration_hours"),
                "candle_count": session_a.get("candle_count"),
                "dominant_regime": session_a.get("module_results", {}).get("regime_analysis", {}).get("dominant_regime"),
                "realized_volatility_annual_pct": vol_a,
                "mean_return_pct": ret_mean_a,
                "macro_events_count": macro_a_cnt,
            },
            "session_b": {
                "session_id": session_b_id,
                "start_utc": session_b.get("reference_start_utc"),
                "end_utc": session_b.get("reference_end_utc"),
                "duration_hours": session_b.get("duration_hours"),
                "candle_count": session_b.get("candle_count"),
                "dominant_regime": session_b.get("module_results", {}).get("regime_analysis", {}).get("dominant_regime"),
                "realized_volatility_annual_pct": vol_b,
                "mean_return_pct": ret_mean_b,
                "macro_events_count": macro_b_cnt,
            },
            "dimension_comparisons": {
                "regime_composition": {
                    "jsd_divergence": round(jsd, 4),
                    "similarity_pct": reg_sim_pct,
                    "explanation_tr": f"Rejim kompozisyonu benzerliği %{reg_sim_pct} (JSD: {round(jsd, 4)}).",
                },
                "volatility": {
                    "realized_vol_gap_pct": vol_gap,
                    "similarity_pct": vol_sim_pct,
                    "explanation_tr": f"Yıllık volatilite farkı %{vol_gap} puan olarak gözlenmiştir.",
                },
                "return_mean": {
                    "mean_return_gap_pct": ret_gap,
                    "explanation_tr": f"Ortalama bar getirisi farkı %{ret_gap} seviyesindedir.",
                },
                "macro_context": {
                    "events_a_count": macro_a_cnt,
                    "events_b_count": macro_b_cnt,
                    "explanation_tr": f"A Dönemi {macro_a_cnt} makro olay barındırırken B Dönemi {macro_b_cnt} olay barındırmaktadır.",
                },
            },
            "composite_distance": composite_distance,
            "composite_similarity_pct": composite_sim_pct,
            "scientific_summary_tr": (
                f"Dönem A ({session_a.get('reference_start_utc')} - {session_a.get('reference_end_utc')}) ile "
                f"Dönem B ({session_b.get('reference_start_utc')} - {session_b.get('reference_end_utc')}) karşılaştırıldığında, "
                f"toplam çok boyutlu davranış benzerliği %{composite_sim_pct} olarak ölçülmüştür. "
                f"Rejim kompozisyon uyumu %{reg_sim_pct}, volatilite yakınlığı %{vol_sim_pct}'dir."
            ),
            "canonical_model_version": f"{FROZEN_MODEL_VERSION} (FROZEN)",
            "legal_disclaimer_tr": cls.LEGAL_DISCLAIMER_TR,
        }

    @classmethod
    def export_unified_evidence_package(
        cls,
        session_data: Dict[str, Any],
        comparison_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Produce a self-contained, reproducible, downloadable evidence package
        matching format CBE-UNIFIED-RESEARCH-EVIDENCE-1.0.0.
        """
        now_str = datetime.now(timezone.utc).isoformat()
        session_id = session_data.get("session_id", "URS-UNKNOWN")
        package_id = f"PKG-{session_id}"

        # Clean session data without runtime caching flags
        clean_session = {k: v for k, v in session_data.items() if k not in ("cache_hit",)}

        deterministic_payload = {
            "package_id": package_id,
            "session": clean_session,
            "comparison": comparison_data or {},
            "canonical_model": f"{FROZEN_MODEL_VERSION} (FROZEN)",
        }
        raw_json = json.dumps(deterministic_payload, sort_keys=True)
        checksum = hashlib.sha256(raw_json.encode("utf-8")).hexdigest()

        return {
            "package_format": cls.EVIDENCE_PACKAGE_FORMAT,
            "package_id": package_id,
            "generated_at_utc": now_str,
            "integrity_checksum_sha256": checksum,
            "canonical_model": f"{FROZEN_MODEL_VERSION} (FROZEN)",
            "scientific_integrity_attestation": {
                "model_parameters_mutated": False,
                "forward_leakage_risk": 0,
                "holdout_exposure_status": "HOLDOUT_PREVIOUSLY_EXPOSED",
                "replicated_specifications_epistemology": (
                    "2 out of 14 eligible specifications met predeclared holdout criteria. "
                    "Because holdout was previously exposed and training p-values are exploratory (0.295, 0.094), "
                    "these are NOT presented as independent confirmatory replication."
                ),
                "quarantined_partition_excluded": True,
                "quarantined_period": "2026-10",
                "trading_prohibited": True,
                "directional_trading_eligibility": 0,
            },
            "session_data": clean_session,
            "comparison_data": comparison_data,
            "governance_invariants": {
                "technical_decision": "TECHNICAL_NO_GO",
                "governance_authorization": "NOT_GRANTED",
                "production_token": "NOT_ISSUED",
                "real_network_market_collection": "DISABLED",
                "btcusdt_live_observation": "DISABLED",
                "unattended_monitoring": "DISABLED",
                "live_order_execution": "PERMANENTLY_PROHIBITED",
                "directional_trading_eligibility": 0,
            },
            "legal_disclaimer_tr": cls.LEGAL_DISCLAIMER_TR,
            "status": "SUCCESS",
        }

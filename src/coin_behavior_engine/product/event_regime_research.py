"""
CBE — Event-Conditioned Regime Research Engine
Sprint 10 (CBE_PRODUCT_ACCELERATION_10)

Investigates how historical market regime distributions, volatility, transitions,
and persistence differ before and after verified macroeconomic events.
Enforces strictly causal window alignment, overlap detection, sample adequacy gates,
and statistical uncertainty bounds.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.product.macro_comparison import MacroEventComparisonEngine, MacroEventRecord
from coin_behavior_engine.product.statistical_validity import StatisticalValidityEngine

logger = logging.getLogger("cbe.event_regime_research")

CANONICAL_REGIMES = [
    "MOMENTUM_EXPANSION",
    "COMPRESSION_ACCUMULATION",
    "HIGH_VOLATILITY_EXPANSION",
    "SYSTEMIC_LIQUIDATION",
    "DRIFT_REVERSION",
    "EQUILIBRIUM_CHOP",
]


class EventRegimeResearchEngine:
    """Quantitative research engine for event-conditioned market regime dynamics."""

    @classmethod
    def load_verified_events(cls, category: str = "ALL") -> Tuple[List[MacroEventRecord], List[MacroEventRecord]]:
        """
        Load historical macro events, separating verified events from quarantined candidates.
        """
        all_events = MacroEventComparisonEngine.load_events()
        verified: List[MacroEventRecord] = []
        quarantined: List[MacroEventRecord] = []

        for ev in all_events:
            # Check verification status
            if ev.verification_status == "EVENT_QUARANTINED" or "CANDIDATE" in ev.event_id:
                quarantined.append(ev)
                continue

            if category != "ALL" and ev.event_category != category:
                continue

            verified.append(ev)

        return verified, quarantined

    @classmethod
    def run_cohort_study(
        cls,
        category: str = "US_INFLATION",
        interval: str = "1h",
        window_hours: int = 12,
        alpha: float = 0.05,
    ) -> Dict[str, Any]:
        """
        Conduct a comprehensive event-conditioned regime study across a verified event cohort.
        """
        verified_events, quarantined_events = cls.load_verified_events(category=category)

        if not verified_events and quarantined_events:
            return {
                "status": "EVENT_QUARANTINED",
                "category": category,
                "verified_event_count": 0,
                "quarantined_event_count": len(quarantined_events),
                "error": "Bu kategorideki tüm aday kayıtlar karantinaya alınmıştır.",
                "error_en": "All candidate events in this category are quarantined.",
                "sample_adequacy": {
                    "status": "DATA_CONTAMINATED",
                    "label_tr": "Karantina / Doğrulanmamış",
                    "is_adequate": False,
                },
            }

        if not verified_events:
            return {
                "status": "NO_VERIFIED_EVENTS",
                "category": category,
                "verified_event_count": 0,
                "quarantined_event_count": 0,
                "error": f"'{category}' kategorisinde doğrulanmış tarihsel olay bulunamadı.",
                "error_en": f"No verified events found in category '{category}'.",
                "sample_adequacy": {
                    "status": "INSUFFICIENT_SAMPLE",
                    "label_tr": "Kayıt Yok",
                    "is_adequate": False,
                },
            }

        # Analyze events and collect pre/post trajectories and regimes
        analyzed_events: List[Dict[str, Any]] = []
        excluded_events: List[Dict[str, Any]] = []

        pre_vols: List[float] = []
        post_vols: List[float] = []
        vol_shift_ratios: List[float] = []
        pre_returns: List[float] = []
        post_returns: List[float] = []

        # Regime distribution counters
        pre_regime_counts = {r: 0 for r in CANONICAL_REGIMES}
        post_regime_counts = {r: 0 for r in CANONICAL_REGIMES}
        pre_total_bars = 0
        post_total_bars = 0

        # Overlap detection: check release timestamps
        sorted_events = sorted(verified_events, key=lambda e: e.release_at_utc)
        overlap_flagged = 0

        for i, ev in enumerate(sorted_events):
            # Check overlap with previous event
            is_confounded = False
            if i > 0:
                try:
                    t_curr = datetime.fromisoformat(ev.release_at_utc.replace("Z", "+00:00"))
                    t_prev = datetime.fromisoformat(sorted_events[i - 1].release_at_utc.replace("Z", "+00:00"))
                    diff_hours = (t_curr - t_prev).total_seconds() / 3600.0
                    if diff_hours < (window_hours * 2):
                        is_confounded = True
                        overlap_flagged += 1
                except Exception:
                    pass

            impact = MacroEventComparisonEngine.analyze_event_impact(
                event=ev,
                interval=interval,
                pre_hours=window_hours,
                post_hours=window_hours,
            )

            if impact.get("status") != "SUCCESS":
                excluded_events.append({
                    "event_id": ev.event_id,
                    "release_at_utc": ev.release_at_utc,
                    "reason": impact.get("error", "ANALYSIS_FAILED"),
                })
                continue

            metrics = impact.get("metrics", {})
            pre_vols.append(metrics.get("volatility_pre_pct", 0.0))
            post_vols.append(metrics.get("volatility_post_pct", 0.0))
            vol_shift_ratios.append(metrics.get("volatility_shift_ratio", 1.0))
            pre_returns.append(metrics.get("pre_return_pct", 0.0))
            post_returns.append(metrics.get("post_return_pct", 0.0))

            # Synthesize regime proxy distribution based on volatility & trajectory
            traj = impact.get("trajectory", [])
            for bar in traj:
                offset = bar.get("offset_hours", 0)
                rel_ret = abs(bar.get("relative_return_pct", 0.0))
                # Deterministic classification for research
                if rel_ret > 2.0:
                    regime = "HIGH_VOLATILITY_EXPANSION"
                elif rel_ret > 1.0:
                    regime = "MOMENTUM_EXPANSION"
                elif rel_ret > 0.5:
                    regime = "DRIFT_REVERSION"
                elif rel_ret < 0.15:
                    regime = "COMPRESSION_ACCUMULATION"
                else:
                    regime = "EQUILIBRIUM_CHOP"

                if offset < 0:
                    pre_regime_counts[regime] += 1
                    pre_total_bars += 1
                else:
                    post_regime_counts[regime] += 1
                    post_total_bars += 1

            analyzed_events.append({
                "event_id": ev.event_id,
                "event_name": ev.event_name,
                "release_at_utc": ev.release_at_utc,
                "is_confounded": is_confounded,
                "pre_vol_pct": metrics.get("volatility_pre_pct"),
                "post_vol_pct": metrics.get("volatility_post_pct"),
                "vol_shift_ratio": metrics.get("volatility_shift_ratio"),
                "immediate_return_pct": metrics.get("immediate_return_pct"),
                "mfe_pct": metrics.get("mfe_pct"),
                "mae_pct": metrics.get("mae_pct"),
            })

        n_analyzed = len(analyzed_events)
        sample_adequacy = StatisticalValidityEngine.evaluate_sample_adequacy(
            sample_count=n_analyzed,
            independent_units=n_analyzed - overlap_flagged,
            is_contaminated=False,
            missing_rate=len(excluded_events) / float(len(verified_events)) if verified_events else 0.0,
        )

        # Normalized regime distributions
        pre_dist = {r: round(pre_regime_counts[r] / float(max(1, pre_total_bars)), 4) for r in CANONICAL_REGIMES}
        post_dist = {r: round(post_regime_counts[r] / float(max(1, post_total_bars)), 4) for r in CANONICAL_REGIMES}

        # Calculate Population Stability Index (PSI) between pre and post regime distributions
        psi = 0.0
        for r in CANONICAL_REGIMES:
            p = max(0.0001, pre_dist[r])
            q = max(0.0001, post_dist[r])
            psi += (q - p) * math.log(q / p)
        psi = round(max(0.0, psi), 4)

        # Statistical bootstrap confidence intervals for volatility shift
        vol_shift_ci = StatisticalValidityEngine.block_bootstrap_ci(
            series=vol_shift_ratios,
            statistic_fn="mean",
            block_size=4,
            alpha=alpha,
        )

        # Effect size between pre and post volatility
        effect_size = StatisticalValidityEngine.compute_effect_size(
            pre_series=pre_vols,
            post_series=post_vols,
        )

        # Evidence status
        if not sample_adequacy["is_adequate"]:
            evidence_status = "INSUFFICIENT_EVIDENCE"
        elif vol_shift_ci["null_effect_included"] or effect_size["magnitude"] == "NEGLIGIBLE":
            evidence_status = "DESCRIPTIVE_ONLY"
        else:
            evidence_status = "STATISTICALLY_SUPPORTED_ASSOCIATION"

        return {
            "status": "SUCCESS",
            "category": category,
            "interval": interval,
            "window_hours": window_hours,
            "total_verified_events": len(verified_events),
            "analyzed_event_count": n_analyzed,
            "excluded_event_count": len(excluded_events),
            "overlap_confounded_count": overlap_flagged,
            "quarantined_event_count": len(quarantined_events),
            "sample_adequacy": sample_adequacy,
            "evidence_status": evidence_status,
            "scientific_interpretation": {
                "tr": (
                    "Bu çalışma gözlemsel bir tarihsel araştırmadır. Olay öncesi ve sonrası rejim dağılımlarındaki "
                    "farklılıklar nedensel bir kural veya kesin karlı alım-satım avantajı teşkil etmez."
                ),
                "en": (
                    "This study is observational historical research. Regime distribution shifts before and after "
                    "macro events do not imply causal predictive edge or trading profitability."
                ),
            },
            "regime_distributions": {
                "pre_event": pre_dist,
                "post_event": post_dist,
                "regime_distribution_shift_psi": psi,
            },
            "volatility_response": {
                "mean_pre_vol_pct": round(float(np.mean(pre_vols)), 3) if pre_vols else 0.0,
                "mean_post_vol_pct": round(float(np.mean(post_vols)), 3) if post_vols else 0.0,
                "mean_vol_shift_ratio": round(float(np.mean(vol_shift_ratios)), 3) if vol_shift_ratios else 1.0,
                "volatility_shift_ci": vol_shift_ci,
                "effect_size": effect_size,
            },
            "directional_descriptive": {
                "mean_pre_return_pct": round(float(np.mean(pre_returns)), 3) if pre_returns else 0.0,
                "mean_post_return_pct": round(float(np.mean(post_returns)), 3) if post_returns else 0.0,
                "return_is_directional_edge": False,
            },
            "analyzed_events_sample": analyzed_events[:10],
            "excluded_events": excluded_events[:10],
        }

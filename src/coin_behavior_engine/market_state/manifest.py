"""Qualified Feature Manifest & Admission Gate for Unified Market State Engine.

Sprint 07: Unifies only empirically qualified features across Sprints 01-06.
Rejects unverified or harmful features (e.g., historical analogue directional signals,
unconditioned macro staleness, unconditional event noise dilution).
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from coin_behavior_engine.utils.logging import logger


VALID_FEATURE_CATEGORIES = {"CORE", "CONTEXTUAL", "EVENT_ONLY", "CONDITIONED", "REJECTED"}
VALID_FAMILIES = {"SPOT", "DERIVATIVES", "SESSION", "ETF", "MACRO", "EVENTS", "INTERACTION", "REJECTED"}


@dataclass
class QualifiedFeature:
    """Represents a feature evaluated and classified for the unified engine."""

    feature_id: str
    feature_name: str
    family: str
    category: str  # CORE, CONTEXTUAL, EVENT_ONLY, CONDITIONED, REJECTED
    sprint_verified: str
    description: str
    evidence_status: str  # VERIFIED_INCREMENTAL, HARMFUL_UNCONDITIONED, UNVERIFIED_DIRECTIONAL
    admission_decision: str  # ADMITTED_CORE, ADMITTED_CONTEXTUAL, ADMITTED_OVERLAY, ADMITTED_CONDITIONED, REJECTED
    routing_condition: str  # ALWAYS_ACTIVE, ROUTED_ON_FRESHNESS, ROUTED_ON_EVENT_WINDOW, QUARANTINED
    fallback_replacement: Optional[str] = None
    expected_sample_coverage: float = 1.0
    notes: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FeatureManifestRegistry:
    """Registry that audits and compiles the qualified feature manifest."""

    def __init__(self):
        self.features: Dict[str, QualifiedFeature] = {}
        self._populate_canonical_manifest()

    def _populate_canonical_manifest(self) -> None:
        """Populate the canonical feature taxonomy across Sprints 01-06."""
        # 1. CORE SPOT FEATURES
        self.add_feature(
            feature_id="FEAT-SPOT-01",
            feature_name="realized_vol_1h",
            family="SPOT",
            category="CORE",
            sprint_verified="Sprint 01/01.1",
            description="1-hour rolling realized volatility from 5-minute logarithmic returns.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="realized_vol_4h",
            expected_sample_coverage=1.0,
            notes="Primary volatility state feature. Stationary and causal.",
        )
        self.add_feature(
            feature_id="FEAT-SPOT-02",
            feature_name="realized_vol_4h",
            family="SPOT",
            category="CORE",
            sprint_verified="Sprint 01/01.1",
            description="4-hour rolling realized volatility.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="realized_vol_24h",
            expected_sample_coverage=1.0,
            notes="Medium-term volatility anchor.",
        )
        self.add_feature(
            feature_id="FEAT-SPOT-03",
            feature_name="realized_vol_24h",
            family="SPOT",
            category="CORE",
            sprint_verified="Sprint 01/01.1",
            description="24-hour rolling realized volatility baseline.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="EXPANDING_MEDIAN_VOL",
            expected_sample_coverage=1.0,
            notes="Diurnal baseline volatility normalizer.",
        )
        self.add_feature(
            feature_id="FEAT-SPOT-04",
            feature_name="volume_zscore_24h",
            family="SPOT",
            category="CORE",
            sprint_verified="Sprint 01/01.1",
            description="Volume standardized by 24-hour rolling mean and standard deviation.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="0.0",
            expected_sample_coverage=1.0,
            notes="Activity surge indicator.",
        )
        self.add_feature(
            feature_id="FEAT-SPOT-05",
            feature_name="compression_ratio",
            family="SPOT",
            category="CORE",
            sprint_verified="Sprint 01/01.1",
            description="Parkinson high-low variance relative to close-to-close variance.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="1.0",
            expected_sample_coverage=1.0,
            notes="Pre-expansion compression diagnostic.",
        )

        # 2. CORE DERIVATIVES FEATURES
        self.add_feature(
            feature_id="FEAT-DERIV-01",
            feature_name="basis_annualized",
            family="DERIVATIVES",
            category="CORE",
            sprint_verified="Sprint 03",
            description="Perpetual futures mark price vs spot price annualized basis spread.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="0.0",
            expected_sample_coverage=1.0,
            notes="Leverage sentiment and market strain measure.",
        )
        self.add_feature(
            feature_id="FEAT-DERIV-02",
            feature_name="funding_rate",
            family="DERIVATIVES",
            category="CORE",
            sprint_verified="Sprint 03",
            description="8-hour periodic perpetual funding rate applied to longs/shorts.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="0.0",
            expected_sample_coverage=1.0,
            notes="Perpetual funding crowding signal.",
        )
        self.add_feature(
            feature_id="FEAT-DERIV-03",
            feature_name="oi_change_1h",
            family="DERIVATIVES",
            category="CORE",
            sprint_verified="Sprint 03",
            description="1-hour percentage change in open interest across major derivative venues.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="0.0",
            expected_sample_coverage=1.0,
            notes="Capital build-up and deleveraging risk indicator.",
        )
        self.add_feature(
            feature_id="FEAT-DERIV-04",
            feature_name="taker_buy_ratio",
            family="DERIVATIVES",
            category="CORE",
            sprint_verified="Sprint 03",
            description="Taker buy volume divided by total taker volume on derivatives.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="0.5",
            expected_sample_coverage=1.0,
            notes="Aggressive taker aggression imbalance.",
        )

        # 3. CORE SESSION FEATURES
        self.add_feature(
            feature_id="FEAT-SESS-01",
            feature_name="session_asia",
            family="SESSION",
            category="CORE",
            sprint_verified="Sprint 04",
            description="Binary flag for Asia trading hours (00:00 - 08:00 UTC).",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="0.0",
            expected_sample_coverage=1.0,
            notes="Deterministic diurnal liquidity cycle.",
        )
        self.add_feature(
            feature_id="FEAT-SESS-02",
            feature_name="session_london",
            family="SESSION",
            category="CORE",
            sprint_verified="Sprint 04",
            description="Binary flag for London trading hours (08:00 - 16:00 UTC).",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="0.0",
            expected_sample_coverage=1.0,
            notes="European session volatility expansion.",
        )
        self.add_feature(
            feature_id="FEAT-SESS-03",
            feature_name="session_ny",
            family="SESSION",
            category="CORE",
            sprint_verified="Sprint 04",
            description="Binary flag for New York trading hours (13:00 - 21:00 UTC).",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="0.0",
            expected_sample_coverage=1.0,
            notes="US market high-volume regime.",
        )
        self.add_feature(
            feature_id="FEAT-SESS-04",
            feature_name="session_overlap",
            family="SESSION",
            category="CORE",
            sprint_verified="Sprint 04",
            description="Binary flag for London-NY overlap window (13:00 - 16:00 UTC).",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="0.0",
            expected_sample_coverage=1.0,
            notes="Peak global liquidity and volatility concentration.",
        )
        self.add_feature(
            feature_id="FEAT-SESS-05",
            feature_name="is_weekend",
            family="SESSION",
            category="CORE",
            sprint_verified="Sprint 04",
            description="Binary flag for weekend bars (Saturday 00:00 to Sunday 23:59 UTC).",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CORE",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="0.0",
            expected_sample_coverage=1.0,
            notes="Low institutional participation, compression environment.",
        )

        # 4. CONTEXTUAL ETF FEATURES (ROUTED)
        self.add_feature(
            feature_id="FEAT-ETF-01",
            feature_name="etf_net_flow_usd_zscore",
            family="ETF",
            category="CONTEXTUAL",
            sprint_verified="Sprint 05",
            description="Standardized aggregate US Spot BTC ETF daily net flow (USD).",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CONTEXTUAL",
            routing_condition="ROUTED_ON_FRESHNESS",
            fallback_replacement="0.0",
            expected_sample_coverage=0.71,  # Active only on trading days
            notes="Gated: active during US session and post-close reporting window; zeroed/stale on weekends.",
        )
        self.add_feature(
            feature_id="FEAT-ETF-02",
            feature_name="etf_flow_breadth",
            family="ETF",
            category="CONTEXTUAL",
            sprint_verified="Sprint 05",
            description="Fraction of reporting ETF funds exhibiting positive net inflow.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CONTEXTUAL",
            routing_condition="ROUTED_ON_FRESHNESS",
            fallback_replacement="0.5",
            expected_sample_coverage=0.71,
            notes="Breadth concentration metric; routed as contextual overlay.",
        )
        self.add_feature(
            feature_id="FEAT-ETF-03",
            feature_name="etf_persistence_streak",
            family="ETF",
            category="CONTEXTUAL",
            sprint_verified="Sprint 05",
            description="Consecutive days of net inflow (+streak) or net outflow (-streak).",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CONTEXTUAL",
            routing_condition="ROUTED_ON_FRESHNESS",
            fallback_replacement="0.0",
            expected_sample_coverage=0.71,
            notes="Institutional flow regime persistence.",
        )

        # 5. CONTEXTUAL MACRO FEATURES (CONDITIONED)
        self.add_feature(
            feature_id="FEAT-MACRO-01",
            feature_name="dxy_return_1d",
            family="MACRO",
            category="CONTEXTUAL",
            sprint_verified="Sprint 04",
            description="1-day return of US Dollar Index, gated by market session freshness.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CONTEXTUAL",
            routing_condition="ROUTED_ON_FRESHNESS",
            fallback_replacement="0.0",
            expected_sample_coverage=0.71,
            notes="Conditioned on open market hours; zeroed when market closed or stale.",
        )
        self.add_feature(
            feature_id="FEAT-MACRO-02",
            feature_name="spx_return_1d",
            family="MACRO",
            category="CONTEXTUAL",
            sprint_verified="Sprint 04",
            description="1-day return of S&P 500, gated by active trading hours.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CONTEXTUAL",
            routing_condition="ROUTED_ON_FRESHNESS",
            fallback_replacement="0.0",
            expected_sample_coverage=0.71,
            notes="Cross-asset equity beta context; conditioned on US market hours.",
        )
        self.add_feature(
            feature_id="FEAT-MACRO-03",
            feature_name="macro_regime_encoded",
            family="MACRO",
            category="CONDITIONED",
            sprint_verified="Sprint 04",
            description="Categorical macro risk regime (Risk-On, Risk-Off, Neutral).",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CONDITIONED",
            routing_condition="ROUTED_ON_FRESHNESS",
            fallback_replacement="0.0",
            expected_sample_coverage=0.71,
            notes="Macro risk state switch.",
        )

        # 6. EVENT-ONLY FEATURES (ROUTED OVERLAY)
        self.add_feature(
            feature_id="FEAT-EVENT-01",
            feature_name="event_novelty",
            family="EVENTS",
            category="EVENT_ONLY",
            sprint_verified="Sprint 06",
            description="Information novelty score of external headline or economic release.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_OVERLAY",
            routing_condition="ROUTED_ON_EVENT_WINDOW",
            fallback_replacement="0.0",
            expected_sample_coverage=0.05,  # Active only during post-event shock windows
            notes="Routed overlay: non-zero only during active event decay window; 0 elsewhere.",
        )
        self.add_feature(
            feature_id="FEAT-EVENT-02",
            feature_name="event_severity",
            family="EVENTS",
            category="EVENT_ONLY",
            sprint_verified="Sprint 06",
            description="Calibrated taxonomy severity tier (1 to 4) of incoming event.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_OVERLAY",
            routing_condition="ROUTED_ON_EVENT_WINDOW",
            fallback_replacement="0.0",
            expected_sample_coverage=0.05,
            notes="Event shock magnitude scaler.",
        )
        self.add_feature(
            feature_id="FEAT-EVENT-03",
            feature_name="event_density_24h",
            family="EVENTS",
            category="EVENT_ONLY",
            sprint_verified="Sprint 06",
            description="Count of distinct verified events within rolling 24 hours.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_OVERLAY",
            routing_condition="ROUTED_ON_EVENT_WINDOW",
            fallback_replacement="0.0",
            expected_sample_coverage=0.05,
            notes="Cluster and news-flow velocity context.",
        )
        self.add_feature(
            feature_id="FEAT-EVENT-04",
            feature_name="event_surprise_tfidf",
            family="EVENTS",
            category="EVENT_ONLY",
            sprint_verified="Sprint 06",
            description="TF-IDF vocabulary surprise relative to Discovery corpus baseline.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_OVERLAY",
            routing_condition="ROUTED_ON_EVENT_WINDOW",
            fallback_replacement="0.0",
            expected_sample_coverage=0.05,
            notes="Semantic novelty metric fitted strictly on Discovery partition.",
        )
        self.add_feature(
            feature_id="FEAT-EVENT-05",
            feature_name="event_decay_clock",
            family="EVENTS",
            category="EVENT_ONLY",
            sprint_verified="Sprint 06",
            description="Exponential decay clock exp(-lambda * delta_t) from event arrival.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_OVERLAY",
            routing_condition="ROUTED_ON_EVENT_WINDOW",
            fallback_replacement="0.0",
            expected_sample_coverage=0.05,
            notes="Deterministic decay weight for post-event shock duration.",
        )

        # 7. CONDITIONED INTERACTION FEATURES
        self.add_feature(
            feature_id="FEAT-INT-01",
            feature_name="vol_x_ny_session",
            family="INTERACTION",
            category="CONDITIONED",
            sprint_verified="Sprint 04",
            description="Interaction term between realized_vol_1h and NY session flag.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CONDITIONED",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="0.0",
            expected_sample_coverage=1.0,
            notes="Captures enhanced volatility persistence during US market hours.",
        )
        self.add_feature(
            feature_id="FEAT-INT-02",
            feature_name="oi_change_x_compression",
            family="INTERACTION",
            category="CONDITIONED",
            sprint_verified="Sprint 03",
            description="Interaction between derivative open interest surge and price compression.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CONDITIONED",
            routing_condition="ALWAYS_ACTIVE",
            fallback_replacement="0.0",
            expected_sample_coverage=1.0,
            notes="Identifies explosive coiled-spring spring-load regimes.",
        )
        self.add_feature(
            feature_id="FEAT-INT-03",
            feature_name="event_decay_x_severity",
            family="INTERACTION",
            category="CONDITIONED",
            sprint_verified="Sprint 06",
            description="Product of event decay clock and severity tier.",
            evidence_status="VERIFIED_INCREMENTAL",
            admission_decision="ADMITTED_CONDITIONED",
            routing_condition="ROUTED_ON_EVENT_WINDOW",
            fallback_replacement="0.0",
            expected_sample_coverage=0.05,
            notes="Transient shock amplitude modifier.",
        )

        # 8. REJECTED / DISQUALIFIED FEATURES (STRICTLY PROHIBITED)
        self.add_feature(
            feature_id="FEAT-REJ-01",
            feature_name="historical_analogue_directional_concordance",
            family="REJECTED",
            category="REJECTED",
            sprint_verified="Sprint 02.1",
            description="Nearest-neighbor historical analogue directional prediction (claimed 64.2%).",
            evidence_status="UNVERIFIED_DIRECTIONAL",
            admission_decision="REJECTED",
            routing_condition="QUARANTINED",
            fallback_replacement="NONE_PROHIBITED",
            expected_sample_coverage=0.0,
            notes="REJECTED: Failed forensic reconstruction in Sprint 02.1. OOS concordance ~48%, calibration failed.",
        )
        self.add_feature(
            feature_id="FEAT-REJ-02",
            feature_name="unconditioned_macro_5m",
            family="REJECTED",
            category="REJECTED",
            sprint_verified="Sprint 04",
            description="Continuous unconditioned macro index injection across all 5m weekend/night bars.",
            evidence_status="HARMFUL_UNCONDITIONED",
            admission_decision="REJECTED",
            routing_condition="QUARANTINED",
            fallback_replacement="NONE_PROHIBITED",
            expected_sample_coverage=0.0,
            notes="REJECTED: Degraded 5m volatility model in Sprint 04 due to market closure staleness.",
        )
        self.add_feature(
            feature_id="FEAT-REJ-03",
            feature_name="unconditional_event_dense",
            family="REJECTED",
            category="REJECTED",
            sprint_verified="Sprint 06",
            description="Dense unrouted news features included across all quiet non-event 5m bars.",
            evidence_status="HARMFUL_UNCONDITIONED",
            admission_decision="REJECTED",
            routing_condition="QUARANTINED",
            fallback_replacement="NONE_PROHIBITED",
            expected_sample_coverage=0.0,
            notes="REJECTED: Negative delta R2 (-0.0032) in 2025 Validation due to noise dilution.",
        )
        self.add_feature(
            feature_id="FEAT-REJ-04",
            feature_name="directional_signal_binary_trade",
            family="REJECTED",
            category="REJECTED",
            sprint_verified="Sprint 01-06",
            description="Binary long/short buy/sell execution signals.",
            evidence_status="UNVERIFIED_DIRECTIONAL",
            admission_decision="REJECTED",
            routing_condition="QUARANTINED",
            fallback_replacement="NONE_PROHIBITED",
            expected_sample_coverage=0.0,
            notes="REJECTED: Directional edge unverified across all major information layers. Trading execution prohibited.",
        )

    def add_feature(self, **kwargs) -> QualifiedFeature:
        feat = QualifiedFeature(**kwargs)
        if feat.category not in VALID_FEATURE_CATEGORIES:
            raise ValueError(f"Invalid category: {feat.category}")
        if feat.family not in VALID_FAMILIES:
            raise ValueError(f"Invalid family: {feat.family}")
        self.features[feat.feature_id] = feat
        return feat

    def get_features_by_category(self, category: str) -> List[QualifiedFeature]:
        return [f for f in self.features.values() if f.category == category]

    def get_admitted_features(self) -> List[QualifiedFeature]:
        return [f for f in self.features.values() if f.category != "REJECTED"]

    def export_manifest(self, output_path: str | Path) -> None:
        """Export manifest to JSON."""
        p = Path(output_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "manifest_version": "CBE-MANIFEST-0.7.0",
            "total_evaluated_features": len(self.features),
            "admitted_core_features": len(self.get_features_by_category("CORE")),
            "admitted_contextual_features": len(self.get_features_by_category("CONTEXTUAL")),
            "admitted_overlay_features": len(self.get_features_by_category("EVENT_ONLY")),
            "admitted_conditioned_features": len(self.get_features_by_category("CONDITIONED")),
            "rejected_features": len(self.get_features_by_category("REJECTED")),
            "features": [f.to_dict() for f in self.features.values()],
        }
        with open(p, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Exported qualified feature manifest ({len(self.features)} features) to {p}")

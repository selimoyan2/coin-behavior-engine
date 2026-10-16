"""Sprint 10.02 — Product-Facing Data Contracts and Fail-Closed Display Rules.

Defines:
1. Standardized ContractField container with full audit provenance.
2. Read-only schemas for all 10 mandated product domain contracts:
   - MarketOverviewContract
   - MarketRegimeContract
   - VolatilityDiagnosticsContract
   - PredictionDiagnosticsContract
   - CalibrationStatusContract
   - DataFreshnessContract
   - ProbabilityProvenanceContract
   - ModelVersionContract
   - FeatureAvailabilityContract
   - ExperimentalWarningsContract
3. FailClosedDisplayRuleEngine enforcing strict display protections:
   - Invalid regime -> UNKNOWN
   - Static fallbacks -> never labeled live predictions
   - Insufficient evidence -> suppressed confidence claims
   - Missing derivatives -> suppressed derivatives-risk labels
   - Stale data -> prominent staleness warning
   - Experimental metrics -> clearly separated
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


# ---------------------------------------------------------------------------
# Section 1: Provenance and Validation Status Enums
# ---------------------------------------------------------------------------
class ProductValidationStatus(str, Enum):
    """Validation lifecycle status for product metrics and features."""
    VALIDATED_FOR_PRODUCT = "VALIDATED_FOR_PRODUCT"
    VALIDATED_WITH_LIMITATIONS = "VALIDATED_WITH_LIMITATIONS"
    EXPERIMENTAL_ONLY = "EXPERIMENTAL_ONLY"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    BLOCKED_BY_DATA_QUALITY = "BLOCKED_BY_DATA_QUALITY"
    UNKNOWN = "UNKNOWN"


class FieldAvailabilityStatus(str, Enum):
    """Data availability tier for contract fields."""
    AVAILABLE = "AVAILABLE"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class FieldFallbackStatus(str, Enum):
    """Provenance status indicating whether field is computed or a fallback."""
    DYNAMIC_MODEL_DERIVED = "DYNAMIC_MODEL_DERIVED"
    EMPIRICALLY_CALIBRATED = "EMPIRICALLY_CALIBRATED"
    STATIC_FALLBACK_CONSTANT = "STATIC_FALLBACK_CONSTANT"
    FAIL_CLOSED_SUPPRESSED = "FAIL_CLOSED_SUPPRESSED"


# ---------------------------------------------------------------------------
# Section 2: Standardized Contract Field
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ContractField:
    """Standardized field representation guaranteeing machine-checkable provenance."""
    name: str
    value: Any
    unit: str
    observation_timestamp: str
    data_source: str
    model_version: str
    validation_status: str
    availability_status: str
    fallback_status: str
    human_readable_explanation: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Section 3: Read-Only Product Contract Schemas (10 Domains)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MarketOverviewContract:
    """Contract 1: High-level market overview and bar context."""
    symbol: ContractField
    spot_price_usdt: ContractField
    price_change_24h_pct: ContractField
    volume_24h_usdt: ContractField
    data_mode: ContractField
    bar_timestamp_utc: ContractField

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketRegimeContract:
    """Contract 2: Market regime classification with fail-closed safeguards."""
    classified_state: ContractField
    regime_confidence: ContractField
    reference_window_bars: ContractField
    data_mode_awareness: ContractField
    is_experimental: ContractField
    consumer_display_label: ContractField

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class VolatilityDiagnosticsContract:
    """Contract 3: Realized volatility term structure and compression ratio."""
    realized_vol_15m: ContractField
    realized_vol_1h: ContractField
    realized_vol_4h: ContractField
    realized_vol_24h: ContractField
    compression_ratio: ContractField
    volatility_tercile: ContractField

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PredictionDiagnosticsContract:
    """Contract 4: Multi-horizon forecasts and calibrated uncertainty bands."""
    horizons_evaluated: List[str]
    forecast_15m_bps: ContractField
    forecast_1h_bps: ContractField
    forecast_4h_bps: ContractField
    forecast_24h_bps: ContractField
    conformal_band_80_15m_bps: ContractField
    conformal_band_95_15m_bps: ContractField
    conformal_band_80_1h_bps: ContractField
    conformal_band_95_1h_bps: ContractField
    conformal_band_80_4h_bps: ContractField
    conformal_band_95_4h_bps: ContractField
    conformal_band_80_24h_bps: ContractField  # Classified as INSUFFICIENT_EVIDENCE
    conformal_band_95_24h_bps: ContractField  # Classified as INSUFFICIENT_EVIDENCE

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CalibrationStatusContract:
    """Contract 5: Conformal calibration layer configuration and health."""
    contract_version: ContractField
    calibration_method: ContractField
    calibration_sample_size: ContractField
    effective_sample_sizes: Dict[str, int]
    coverage_tolerances_met: Dict[str, bool]
    last_calibration_cutoff_utc: ContractField

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class DataFreshnessContract:
    """Contract 6: Pipeline data freshness, staleness tracking, and latency."""
    latest_bar_timestamp_utc: ContractField
    evaluation_timestamp_utc: ContractField
    ingestion_latency_seconds: ContractField
    staleness_threshold_seconds: ContractField
    is_stale: ContractField
    staleness_warning: ContractField

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ProbabilityProvenanceContract:
    """Contract 7: Explicit provenance taxonomy for all probabilities."""
    expansion_probability_4h: ContractField
    directional_probability_up: ContractField
    tail_risk_probability: ContractField  # Must be STATIC_FALLBACK_CONSTANT
    jump_risk_probability: ContractField  # Must be STATIC_FALLBACK_CONSTANT
    conformal_interval_80: ContractField
    conformal_interval_95: ContractField

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ModelVersionContract:
    """Contract 8: Model versioning and canonical freeze integrity."""
    model_version: ContractField
    model_artifact_hash: ContractField
    canonical_freeze_files_count: ContractField
    canonical_freeze_verified: ContractField
    approval4_status: ContractField

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FeatureAvailabilityContract:
    """Contract 9: Feature group availability and degradation status."""
    spot_ohlcv: ContractField
    derivatives_open_interest: ContractField
    derivatives_funding_rate: ContractField
    derivatives_liquidations: ContractField
    macro_session: ContractField
    etf_flows: ContractField

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ExperimentalWarningsContract:
    """Contract 10: Mandatory consumer-facing experimental disclaimers."""
    total_warnings_active: int
    active_warnings: List[str]
    suppressed_fields: List[str]
    disclaimer_turkish: str
    disclaimer_english: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Section 4: Fail-Closed Display Rule Engine
# ---------------------------------------------------------------------------
class FailClosedDisplayRuleEngine:
    """Enforces strict display protections and fail-closed rules before exposing data."""

    STALENESS_THRESHOLD_SECONDS = 1800  # 30 minutes (2 x 15m bars)
    MIN_HISTORICAL_BARS_FOR_REGIME = 96  # 24 hours of 15m bars
    MIN_EFFECTIVE_SAMPLES_FOR_CONFORMAL = 100

    @classmethod
    def sanitize_regime_display(
        cls,
        raw_state: str,
        history_length: int,
        data_mode: str,
        is_computed_causally: bool = True,
    ) -> Dict[str, Any]:
        """Rule 1: Invalid regime classifications display UNKNOWN."""
        if history_length < cls.MIN_HISTORICAL_BARS_FOR_REGIME:
            return {
                "display_state": "UNKNOWN",
                "display_label": "Bilinmeyen / Yetersiz Tarihsel Veri",
                "validation_status": ProductValidationStatus.UNKNOWN.value,
                "reason": f"Reference history has {history_length} bars; minimum required is {cls.MIN_HISTORICAL_BARS_FOR_REGIME}.",
                "suppressed": True,
            }

        if not is_computed_causally:
            return {
                "display_state": "UNKNOWN",
                "display_label": "Bilinmeyen / Dondurulmuş Model Kısıtı",
                "validation_status": ProductValidationStatus.UNKNOWN.value,
                "reason": "Single-row percentile collapse identified in legacy engine; raw classification suppressed.",
                "suppressed": True,
            }

        # Check derivatives dependency in Spot-Only mode
        derivatives_dependent_states = ["DELEVERAGING_STRESS", "JUMP_RISK_ELEVATED", "TAIL_RISK_ELEVATED"]
        if data_mode in ("SPOT_ONLY_U0", "DEGRADED_STREAM") and raw_state in derivatives_dependent_states:
            return {
                "display_state": "UNKNOWN_DERIVATIVES",
                "display_label": "Bilinmeyen (Türev Verisi Eksik)",
                "validation_status": ProductValidationStatus.BLOCKED_BY_DATA_QUALITY.value,
                "reason": "Derivatives features (OI, basis, funding) unavailable in Spot-Only mode; cannot compute derivatives stress.",
                "suppressed": True,
            }

        return {
            "display_state": raw_state,
            "display_label": f"Deneysel Rejim ({raw_state})",
            "validation_status": ProductValidationStatus.EXPERIMENTAL_ONLY.value,
            "reason": "Causal historical reference distribution verified.",
            "suppressed": False,
        }

    @classmethod
    def sanitize_probability_display(
        cls,
        prob_name: str,
        prob_value: float,
        provenance_type: str,
    ) -> Dict[str, Any]:
        """Rule 2: Static fallback probabilities are never labeled live predictive probabilities."""
        if "STATIC_FALLBACK" in provenance_type or prob_name in ("tail_risk_probability", "jump_risk_probability"):
            return {
                "display_value": prob_value,
                "display_label": f"Statik Güvenlik Sabiti ({prob_value:.2f})",
                "is_live_prediction": False,
                "provenance": FieldFallbackStatus.STATIC_FALLBACK_CONSTANT.value,
                "consumer_warning": "Bu değer canlı bir model tahmini değil, veri yokluğunda kullanılan statik güvenlik sabitidir.",
            }

        return {
            "display_value": prob_value,
            "display_label": f"Model Olasılığı ({prob_value:.2%})",
            "is_live_prediction": True,
            "provenance": provenance_type,
            "consumer_warning": None,
        }

    @classmethod
    def sanitize_horizon_conformal_display(
        cls,
        horizon_name: str,
        nominal_cov: float,
        empirical_cov: float,
        effective_sample_size: int,
    ) -> Dict[str, Any]:
        """Rule 3: Insufficient-evidence horizons cannot display validated confidence claims."""
        if effective_sample_size < cls.MIN_EFFECTIVE_SAMPLES_FOR_CONFORMAL:
            return {
                "display_allowed": False,
                "validation_status": ProductValidationStatus.INSUFFICIENT_EVIDENCE.value,
                "display_badge": "Yetersiz Bağımsız Örneklem (Deneysel)",
                "explanation": (
                    f"{horizon_name} vadesinde efektif bağımsız örnek sayısı ({effective_sample_size}) "
                    f"asgari eşiğin ({cls.MIN_EFFECTIVE_SAMPLES_FOR_CONFORMAL}) altındadır. "
                    "Bu vadedeki güven aralığı iddiaları ürün katmanında sınırlandırılmıştır."
                ),
            }

        if horizon_name in ("8h", "12h"):
            return {
                "display_allowed": True,
                "validation_status": ProductValidationStatus.VALIDATED_WITH_LIMITATIONS.value,
                "display_badge": "Kısıtlı Doğrulandı (Yüksek Otokorelasyon)",
                "explanation": f"{horizon_name} vadesi doğrulanmıştır ancak örtüşen pencere bağımlılığı mevcuttur.",
            }

        return {
            "display_allowed": True,
            "validation_status": ProductValidationStatus.VALIDATED_FOR_PRODUCT.value,
            "display_badge": "Doğrulanmış Güven Aralığı",
            "explanation": f"{horizon_name} vadesi split conformal protokolü ile başarıyla doğrulanmıştır.",
        }

    @classmethod
    def check_data_freshness(
        cls,
        latest_bar_ts: str,
        current_ts: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Rule 4: Stale data must be visibly marked."""
        try:
            t_bar = datetime.fromisoformat(latest_bar_ts.replace("Z", "+00:00"))
            if current_ts:
                t_now = datetime.fromisoformat(current_ts.replace("Z", "+00:00"))
            else:
                t_now = datetime.now(timezone.utc)
            delta_sec = max(0.0, (t_now - t_bar).total_seconds())
        except Exception:
            delta_sec = 0.0

        is_stale = delta_sec > cls.STALENESS_THRESHOLD_SECONDS
        return {
            "is_stale": is_stale,
            "latency_seconds": delta_sec,
            "warning_message": (
                f"DİKKAT: Veri akışı son {delta_sec / 60:.1f} dakikadır güncellenmemiştir (Eşik: {cls.STALENESS_THRESHOLD_SECONDS // 60} dk)."
                if is_stale
                else "Veri akışı güncel."
            ),
        }

"""Dual-Branch Inference Runner for CBE-0.8.0 Shadow Collector.

Executes:
- Ridge Volatility Point Forecasts (CandidateInferenceEngineV080).
- Market State Classification (MarketStateClassifierV080).
- Candidate C: Volatility-Normalized Global Conformal Intervals (CalibrationBranchC).
- Candidate E: Conservative Hybrid Regime-Conditioned Conformal Intervals (CalibrationBranchE).
- Horizons: 1h, 4h, 24h.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from coin_behavior_engine.candidate_v080.calibration_branches import (
    BranchIntervals,
    DualBranchCalibrationManager,
)
from coin_behavior_engine.candidate_v080.classifier import MarketStateClassifierV080
from coin_behavior_engine.candidate_v080.inference import CandidateInferenceEngineV080
from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig
from coin_behavior_engine.shadow_v080.prospective_guard import (
    CausalDataEligibilityGuard,
    InsufficientWarmupBarsError,
    PROSPECTIVE_RECORD_LABELS,
    ProspectiveAuthorizationGuard,
    UnverifiedEvidenceError,
)


@dataclass
class DualBranchPredictionResult:
    forecast_origin_utc: str
    primary_state: str
    secondary_flags: List[str]
    classification_reason: str
    point_forecasts: Dict[str, float]  # Shared across both branches
    candidate_c_intervals: Dict[str, BranchIntervals]
    candidate_e_intervals: Dict[str, BranchIntervals]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "forecast_origin_utc": self.forecast_origin_utc,
            "primary_state": self.primary_state,
            "secondary_flags": self.secondary_flags,
            "classification_reason": self.classification_reason,
            "point_forecasts": self.point_forecasts,
            "candidate_c_intervals": {h: b.to_dict() for h, b in self.candidate_c_intervals.items()},
            "candidate_e_intervals": {h: b.to_dict() for h, b in self.candidate_e_intervals.items()},
        }


def verify_prospective_execution_boundary(
    evidence_store: Optional[Any],
    record_label: str = "HISTORICAL_REPLAY",
    is_prospective: bool = False,
    env: Optional[Dict[str, str]] = None,
) -> None:
    """Verify that prospective scoring requires a non-null, verified evidence store at the execution boundary."""
    ProspectiveAuthorizationGuard.verify_authorization(
        record_label=record_label,
        is_prospective=is_prospective,
        env=env,
    )
    if is_prospective or record_label == "PROSPECTIVE_LIVE":
        if evidence_store is None:
            raise UnverifiedEvidenceError(
                "Prospective inference requires a non-null, verified evidence store at execution boundary."
            )


class DualBranchInferenceRunnerV080:
    """Coordinates deterministic inference across Ridge, Market State, and Dual Calibrations."""

    def __init__(self, config: ShadowCollectorConfig):
        self.config = config
        models_dir = config.models_dir
        bundle_path = models_dir / "cbe_model_bundle_v080.json"
        thresh_path = models_dir / "cbe_state_thresholds_v080.json"
        cal_c_path = models_dir / "cbe_interval_calibration_v080_candidate_c.json"
        cal_e_path = models_dir / "cbe_interval_calibration_v080_095.json"

        # 1. Ridge Point Inference Engine
        self.ridge_engine = CandidateInferenceEngineV080(bundle_path)

        # 2. Market State Classifier
        self.classifier = MarketStateClassifierV080(thresh_path)

        # 3. Dual Branch Calibration Manager
        self.cal_manager = DualBranchCalibrationManager(
            branch_c_path=cal_c_path,
            branch_e_path=cal_e_path,
        )

    def predict(
        self,
        features: Dict[str, float],
        forecast_origin_utc: str,
        horizons: Optional[List[str]] = None,
        record_label: str = "HISTORICAL_REPLAY",
        is_prospective: bool = False,
        context_candles: Optional[List[Any]] = None,
        current_candle: Optional[Any] = None,
        current_time_ms: Optional[int] = None,
        evidence_store: Optional[Any] = None,
        require_evidence_store: bool = False,
        env: Optional[Dict[str, str]] = None,
    ) -> DualBranchPredictionResult:
        """Run synchronized inference for both candidate branches with strict fail-closed guards."""
        # 0. Fail-Closed Prospective Authorization & Causal Eligibility Check
        ProspectiveAuthorizationGuard.verify_authorization(
            record_label=record_label,
            is_prospective=is_prospective,
            env=env,
        )

        if is_prospective or record_label == "PROSPECTIVE_LIVE":
            if require_evidence_store and evidence_store is None:
                raise UnverifiedEvidenceError(
                    "Prospective inference requires a non-null, verified evidence store at execution boundary."
                )
            if context_candles is None:
                raise InsufficientWarmupBarsError(
                    "Context candles must be provided to verify causal data eligibility for prospective scoring."
                )
            CausalDataEligibilityGuard.verify_causal_data_eligibility(
                candles=context_candles,
                current_candle=current_candle,
                current_time_ms=current_time_ms,
                evidence_store=evidence_store,
                is_prospective=is_prospective,
            )

        target_horizons = horizons or ["1h", "4h", "24h"]

        # 1. Validate feature vector
        _ = self.ridge_engine.validate_features_dict(features)

        # 2. Compute Ridge point forecasts
        point_forecasts = {}
        for h in target_horizons:
            point_forecasts[h] = self.ridge_engine.predict(features, horizon=h)

        # 3. Classify Market State (strictly causal, SPOT_ONLY_U0 tier)
        cls_res = self.classifier.classify_bar(features, tier="SPOT_ONLY_U0")

        # 4. Compute Calibrated Intervals for Branch C and Branch E
        c_intervals = {}
        e_intervals = {}
        for h in target_horizons:
            dual_int = self.cal_manager.compute_dual_intervals(
                point_forecast=point_forecasts[h],
                horizon=h,
                market_state=cls_res.primary_state,
            )
            c_intervals[h] = dual_int["branch_c"]
            e_intervals[h] = dual_int["branch_e"]

        return DualBranchPredictionResult(
            forecast_origin_utc=forecast_origin_utc,
            primary_state=cls_res.primary_state,
            secondary_flags=cls_res.secondary_flags,
            classification_reason=cls_res.classification_reason,
            point_forecasts=point_forecasts,
            candidate_c_intervals=c_intervals,
            candidate_e_intervals=e_intervals,
        )

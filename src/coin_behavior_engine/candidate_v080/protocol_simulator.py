"""CBE-0.8.0 Offline Prospective Protocol Simulator & Append-Only Event Engine.

Simulates the prospective shadow protocol using historical bars while enforcing:
1. Pure HISTORICAL_REPLAY status (never masquerading as prospective).
2. Parallel dual-branch generation (Branch C and Branch E).
3. Cryptographic hash chaining for tamper-evident append-only event logs.
4. Non-overwriting, append-only outcome maturity recording.
5. Idempotent duplicate rejection and crash recovery validation.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd

from coin_behavior_engine.candidate_v080.calibration_branches import (
    BranchIntervals,
    DualBranchCalibrationManager,
)
from coin_behavior_engine.candidate_v080.classifier import MarketStateClassifierV080
from coin_behavior_engine.candidate_v080.inference import CandidateInferenceEngineV080

SQRT_288 = math.sqrt(288.0)
TARGET_UNITS = "Daily-scaled standard deviation (sigma_5m * sqrt(288))"
GENESIS_HASH = "GENESIS_CBE_0_8_0_SHADOW_CHAIN_000000000000000000000000000000000000"


def compute_payload_hash(payload: Dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of a dictionary payload."""
    canonical_str = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()


@dataclass
class AppendOnlyEvent:
    sequence_number: int
    previous_record_hash: str
    record_hash: str
    schema_version: str
    experiment_id: str
    event_timestamp_utc: str
    event_type: str
    payload_hash: str
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EventChainIntegrityError(Exception):
    """Raised when an event log violates cryptographic hash chaining or sequence order."""
    pass


class DuplicateEventError(Exception):
    """Raised when a duplicate forecast origin and branch event is detected."""
    pass


class OfflineProtocolSimulator:
    """Simulates the prospective shadow forecasting protocol on historical bars."""

    HORIZON_STEPS = {"1h": 12, "4h": 48, "24h": 288}
    HORIZONS = ["1h", "4h", "24h"]

    def __init__(
        self,
        experiment_id: str = "EXP-CBE-0.8.0-SHADOW-2026",
        protocol_version: str = "1.0.0",
        bundle_path: str = "data/models/cbe_model_bundle_v080.json",
        thresholds_path: str = "data/models/cbe_state_thresholds_v080.json",
        branch_c_path: str = "data/models/cbe_interval_calibration_v080_candidate_c.json",
        branch_e_path: str = "data/models/cbe_interval_calibration_v080_095.json",
    ):
        self.experiment_id = experiment_id
        self.protocol_version = protocol_version

        self.engine = CandidateInferenceEngineV080(bundle_path)
        self.classifier = MarketStateClassifierV080(thresholds_path)
        self.calibrator = DualBranchCalibrationManager(branch_c_path, branch_e_path)

        self.events: List[AppendOnlyEvent] = []
        self.outcomes: List[Dict[str, Any]] = []
        self._seen_forecast_keys = set()
        self._last_record_hash = GENESIS_HASH

    def append_event(self, event_type: str, timestamp_utc: str, payload: Dict[str, Any]) -> AppendOnlyEvent:
        """Append a new event with cryptographic chaining and idempotency verification."""
        # Idempotency check for forecasts
        if event_type == "FORECAST_EMITTED":
            f_key = (
                payload.get("forecast_origin_timestamp_utc"),
                payload.get("candidate_branch_id"),
                payload.get("forecast_horizon"),
            )
            if f_key in self._seen_forecast_keys:
                raise DuplicateEventError(f"Duplicate forecast detected for key: {f_key}")
            self._seen_forecast_keys.add(f_key)

        seq = len(self.events) + 1
        p_hash = compute_payload_hash(payload)

        # Compute record hash chaining from previous record hash
        chain_content = f"{seq}|{self._last_record_hash}|{self.experiment_id}|{timestamp_utc}|{event_type}|{p_hash}"
        record_hash = hashlib.sha256(chain_content.encode("utf-8")).hexdigest()

        event = AppendOnlyEvent(
            sequence_number=seq,
            previous_record_hash=self._last_record_hash,
            record_hash=record_hash,
            schema_version="CBE-EVENT-0.8.0",
            experiment_id=self.experiment_id,
            event_timestamp_utc=timestamp_utc,
            event_type=event_type,
            payload_hash=p_hash,
            payload=payload,
        )

        self.events.append(event)
        self._last_record_hash = record_hash
        return event

    def verify_event_chain(self, events: Optional[List[AppendOnlyEvent]] = None) -> Dict[str, Any]:
        """Verify unbroken cryptographic chaining and sequence order."""
        chain = events if events is not None else self.events
        if not chain:
            return {"verified": True, "event_count": 0, "status": "EMPTY_CHAIN"}

        prev_hash = GENESIS_HASH
        for i, ev in enumerate(chain):
            seq = i + 1
            if ev.sequence_number != seq:
                raise EventChainIntegrityError(
                    f"Sequence broken at index {i}: expected {seq}, got {ev.sequence_number}"
                )
            if ev.previous_record_hash != prev_hash:
                raise EventChainIntegrityError(
                    f"Hash chain broken at seq {seq}: expected prev {prev_hash}, got {ev.previous_record_hash}"
                )

            # Recompute payload hash
            expected_p_hash = compute_payload_hash(ev.payload)
            if ev.payload_hash != expected_p_hash:
                raise EventChainIntegrityError(
                    f"Payload hash mismatch at seq {seq}: {ev.payload_hash} != {expected_p_hash}"
                )

            # Recompute record hash
            chain_content = f"{seq}|{prev_hash}|{ev.experiment_id}|{ev.event_timestamp_utc}|{ev.event_type}|{expected_p_hash}"
            expected_rec_hash = hashlib.sha256(chain_content.encode("utf-8")).hexdigest()
            if ev.record_hash != expected_rec_hash:
                raise EventChainIntegrityError(
                    f"Record hash mismatch at seq {seq}: {ev.record_hash} != {expected_rec_hash}"
                )

            prev_hash = ev.record_hash

        return {
            "verified": True,
            "event_count": len(chain),
            "final_record_hash": prev_hash,
            "status": "CHAIN_INTEGRITY_VERIFIED",
        }

    def simulate_bar(
        self,
        features: Dict[str, Any],
        forecast_origin: pd.Timestamp,
        creation_time: pd.Timestamp,
        realized_targets: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:
        """Simulate execution for a single bar, creating parallel forecast records and outcomes."""
        origin_str = forecast_origin.isoformat()
        creation_str = creation_time.isoformat()

        # Classify market state
        cls_res = self.classifier.classify_bar(features, tier="SPOT_ONLY_U0")

        forecast_records = []

        for h in self.HORIZONS:
            pt = self.engine.predict(features, horizon=h)
            dual_itv = self.calibrator.compute_dual_intervals(pt, h, market_state=cls_res.primary_state)

            delta_m = 60 if h == "1h" else (240 if h == "4h" else 1440)
            maturity_time = forecast_origin + pd.Timedelta(minutes=delta_m)
            maturity_str = maturity_time.isoformat()

            # Precondition checks
            assert creation_time <= maturity_time, "creation_time must be <= target_maturity_time"

            # Create Branch C record
            c_itv = dual_itv["branch_c"]
            payload_c = {
                "record_type": "HISTORICAL_REPLAY",
                "experiment_id": self.experiment_id,
                "protocol_version": self.protocol_version,
                "candidate_branch_id": "BRANCH_C_VOLATILITY_NORMALIZED",
                "market_symbol": "BTCUSDT",
                "forecast_origin_timestamp_utc": origin_str,
                "record_creation_timestamp_utc": creation_str,
                "forecast_horizon": h,
                "forecast_target_maturity_timestamp_utc": maturity_str,
                "source_data_cutoff_timestamp_utc": origin_str,
                "availability_tier": "SPOT_ONLY_U0",
                "data_quality_status": "VALID",
                "market_state_label": cls_res.primary_state,
                "market_state_point_forecast_role": "DESCRIPTIVE_ONLY",
                "point_prediction": pt,
                "intervals_80": {"lower": c_itv.lower_80, "upper": c_itv.upper_80, "width": c_itv.width_80},
                "intervals_95": {"lower": c_itv.lower_95, "upper": c_itv.upper_95, "width": c_itv.width_95},
                "calibration_method": "VOL_NORMALIZED",
                "fallback_reason": None,
                "target_units": TARGET_UNITS,
            }
            ev_c = self.append_event("FORECAST_EMITTED", creation_str, payload_c)
            forecast_records.append(ev_c)

            # Create Branch E record
            e_itv = dual_itv["branch_e"]
            payload_e = {
                "record_type": "HISTORICAL_REPLAY",
                "experiment_id": self.experiment_id,
                "protocol_version": self.protocol_version,
                "candidate_branch_id": "BRANCH_E_CONSERVATIVE_HYBRID",
                "market_symbol": "BTCUSDT",
                "forecast_origin_timestamp_utc": origin_str,
                "record_creation_timestamp_utc": creation_str,
                "forecast_horizon": h,
                "forecast_target_maturity_timestamp_utc": maturity_str,
                "source_data_cutoff_timestamp_utc": origin_str,
                "availability_tier": "SPOT_ONLY_U0",
                "data_quality_status": "VALID",
                "market_state_label": cls_res.primary_state,
                "market_state_point_forecast_role": "DESCRIPTIVE_ONLY",
                "point_prediction": pt,
                "intervals_80": {"lower": e_itv.lower_80, "upper": e_itv.upper_80, "width": e_itv.width_80},
                "intervals_95": {"lower": e_itv.lower_95, "upper": e_itv.upper_95, "width": e_itv.width_95},
                "calibration_method": "HYBRID",
                "fallback_reason": "MINIMUM_SAMPLE_FALLBACK" if e_itv.fallback_used else None,
                "target_units": TARGET_UNITS,
            }
            ev_e = self.append_event("FORECAST_EMITTED", creation_str, payload_e)
            forecast_records.append(ev_e)

            # Outcome generation (if targets available)
            if realized_targets and f"fwd_vol_{h}" in realized_targets:
                realized_val = realized_targets[f"fwd_vol_{h}"] * SQRT_288
                for pred_ev in [ev_c, ev_e]:
                    out_payload = {
                        "outcome_id": f"OUT-{pred_ev.record_hash[:16]}",
                        "prediction_record_hash": pred_ev.record_hash,
                        "observation_timestamp_utc": origin_str,
                        "maturity_timestamp_utc": maturity_str,
                        "outcome_computation_timestamp_utc": maturity_str,
                        "forecast_horizon": h,
                        "target_units": TARGET_UNITS,
                        "realized_volatility": realized_val,
                        "source_bar_count": self.HORIZON_STEPS[h],
                        "status": "MATURED",
                    }
                    self.outcomes.append(out_payload)
                    self.append_event("OUTCOME_MATURED", maturity_str, out_payload)

        return {"forecasts_count": len(forecast_records), "market_state": cls_res.primary_state}

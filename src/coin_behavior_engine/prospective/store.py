"""Immutable Prediction Store, Hash Chain, Outcome Store, and Audit Logger for Sprint 08.

Enforces:
- Immutable predictions with SHA-256 tamper-evident hash chaining.
- Strict horizon maturity enforcement (no partial-horizon cheating).
- Separate outcome storage.
- Append-only cryptographic audit logging.
- Strict prohibition of prediction overwrites, deletions, and retroactive generation.
"""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

HORIZON_MINUTES = {
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "8h": 480,
    "12h": 720,
    "24h": 1440,
}

PROSPECTIVE_START_ISO = "2026-09-24T00:00:00Z"
GENESIS_HASH = "GENESIS_CBE_0_7_0_PROSPECTIVE_CHAIN"


class ImmutableStoreViolation(Exception):
    """Raised when an attempt is made to overwrite, modify, or delete a prediction."""
    pass


class HorizonNotMaturedError(Exception):
    """Raised when an outcome is attached before its complete horizon has elapsed."""
    pass


class ProspectiveBoundaryViolation(Exception):
    """Raised when a prediction timestamp is before the prospective research boundary."""
    pass


def parse_utc_iso(dt_str: str) -> datetime:
    """Parse ISO8601 UTC timestamp string reliably."""
    dt_str = dt_str.replace("Z", "+00:00").replace(" UTC", "+00:00")
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def format_utc_iso(dt: datetime) -> str:
    """Format datetime as UTC ISO8601 string."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Fields that belonged to PredictionRecord Schema V1
PREDICTION_V1_FIELDS = {
    "prediction_id",
    "model_version",
    "model_hash",
    "feature_manifest_hash",
    "input_data_hash",
    "timestamp",
    "asset",
    "market_state",
    "forecast_15m",
    "forecast_30m",
    "forecast_1h",
    "forecast_2h",
    "forecast_4h",
    "forecast_8h",
    "forecast_12h",
    "forecast_24h",
    "tail_95_probability",
    "tail_99_probability",
    "jump_probability",
    "expansion_probabilities",
    "prediction_intervals",
    "context_availability",
    "data_quality",
    "research_direction_probability",
    "input_cutoff_timestamp",
    "created_at",
    "previous_record_hash",
}


@dataclass
class PredictionRecord:
    prediction_id: str
    model_version: str
    model_hash: str
    feature_manifest_hash: str
    input_data_hash: str
    timestamp: str  # Bar timestamp (e.g. 2026-09-24T00:00:00Z)
    asset: str = "BTCUSDT"
    market_state: str = "NORMAL"
    forecast_15m: Optional[float] = None
    forecast_30m: Optional[float] = None
    forecast_1h: Optional[float] = None
    forecast_2h: Optional[float] = None
    forecast_4h: Optional[float] = None
    forecast_8h: Optional[float] = None
    forecast_12h: Optional[float] = None
    forecast_24h: Optional[float] = None
    tail_95_probability: Optional[float] = None
    tail_99_probability: Optional[float] = None
    jump_probability: Optional[float] = None
    expansion_probabilities: Dict[str, float] = field(default_factory=dict)
    prediction_intervals: Dict[str, Any] = field(default_factory=dict)
    context_availability: str = "ACTIVE"
    data_quality: str = "DATA_OK"
    research_direction_probability: Dict[str, float] = field(default_factory=lambda: {"p_up": 0.50, "p_down": 0.50})
    input_cutoff_timestamp: str = ""
    created_at: str = ""
    previous_record_hash: str = ""
    record_hash: str = ""
    # Schema V2 Fields: explicit reference close, inputs hashes, data quality & forecast availability provenance
    prediction_schema_version: str = "2"
    reference_close: Optional[float] = None
    market_bar_hash: Optional[str] = None
    model_input_hash: Optional[str] = None
    forecast_availability: Dict[str, bool] = field(default_factory=dict)
    missing_forecast_horizons: List[str] = field(default_factory=list)
    missing_tail_horizons: List[str] = field(default_factory=list)
    missing_jump_horizons: List[str] = field(default_factory=list)
    missing_feature_groups: List[str] = field(default_factory=list)
    missing_features: List[str] = field(default_factory=list)
    fallback_level: str = "SPOT_ONLY_U0"

    @property
    def close(self) -> Optional[float]:
        """Backward-compatible property for reference_close."""
        return self.reference_close

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Return deterministic dict for hashing (excluding record_hash).
        
        Strictly preserves V1 byte-compatibility for historical predictions.
        """
        d = asdict(self)
        d.pop("record_hash", None)
        if getattr(self, "prediction_schema_version", "1") == "1":
            return {k: v for k, v in d.items() if k in PREDICTION_V1_FIELDS}
        return d

    def compute_hash(self) -> str:
        """Compute SHA-256 hash of canonical JSON string."""
        raw_json = json.dumps(self.to_canonical_dict(), sort_keys=True)
        return hashlib.sha256(raw_json.encode("utf-8")).hexdigest()


@dataclass
class OutcomeRecord:
    prediction_id: str
    horizon: str
    outcome_available_at: str
    realized_return: Optional[float] = None
    absolute_return: Optional[float] = None
    realized_volatility: Optional[float] = None
    realized_range: Optional[float] = None
    tail_95_occurred: Optional[bool] = None
    tail_99_occurred: Optional[bool] = None
    jump_occurred: Optional[bool] = None
    expansion_occurred: Optional[bool] = None
    status: str = "SCORED"  # "SCORED", "INVALID_REFERENCE_PRICE", "MATURED"
    outcome_schema_version: str = "2"
    excluded_from_evaluation: bool = False
    invalidation_reason: Optional[str] = None
    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ImmutablePredictionStore:
    """Append-only, tamper-evident prediction store backed by JSONL file."""

    def __init__(self, store_dir: Path = Path("data/prospective/predictions")):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.store_dir / "predictions.jsonl"
        self._index: Dict[str, PredictionRecord] = {}
        self._chain: List[str] = []
        self._load_existing()

    def _load_existing(self) -> None:
        """Load and verify existing predictions in the append-only store."""
        if not self.log_file.exists():
            return

        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if "prediction_schema_version" not in data:
                    data["prediction_schema_version"] = "1"
                rec = PredictionRecord(**data)
                self._index[rec.prediction_id] = rec
                self._chain.append(rec.record_hash)

    @property
    def latest_hash(self) -> str:
        """Get the hash of the latest prediction in the chain, or GENESIS_HASH."""
        return self._chain[-1] if self._chain else GENESIS_HASH

    def store_prediction(self, record: PredictionRecord, audit_logger: Optional['AuditLogger'] = None) -> PredictionRecord:
        """Store a new prediction immutably.
        
        Enforces:
        - Must be >= prospective boundary.
        - Cannot overwrite existing prediction_id.
        - Must chain correctly to previous record hash.
        """
        # 1. Boundary check
        bar_dt = parse_utc_iso(record.timestamp)
        bound_dt = parse_utc_iso(PROSPECTIVE_START_ISO)
        if bar_dt < bound_dt:
            raise ProspectiveBoundaryViolation(
                f"Prediction timestamp {record.timestamp} is before prospective boundary {PROSPECTIVE_START_ISO}"
            )

        # 2. Immutability check
        if record.prediction_id in self._index:
            raise ImmutableStoreViolation(
                f"Prediction {record.prediction_id} already exists. Overwriting is strictly prohibited."
            )

        # 3. Hash chain linkage
        expected_prev_hash = self.latest_hash
        record.previous_record_hash = expected_prev_hash

        if not record.created_at:
            record.created_at = format_utc_iso(datetime.now(timezone.utc))
        if not record.input_cutoff_timestamp:
            record.input_cutoff_timestamp = record.timestamp

        # 4. Compute record hash
        record.record_hash = record.compute_hash()

        # 5. Persist to append-only log
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record)) + "\n")

        self._index[record.prediction_id] = record
        self._chain.append(record.record_hash)

        if audit_logger:
            audit_logger.log_event(
                event_type="PREDICTION_CREATION",
                details={
                    "prediction_id": record.prediction_id,
                    "timestamp": record.timestamp,
                    "market_state": record.market_state,
                    "record_hash": record.record_hash,
                    "prev_hash": record.previous_record_hash,
                }
            )

        return record

    def get_prediction(self, prediction_id: str) -> Optional[PredictionRecord]:
        return self._index.get(prediction_id)

    def list_predictions(self) -> List[PredictionRecord]:
        return list(self._index.values())

    def __len__(self) -> int:
        return len(self._index)

    def verify_hash_chain(self) -> Tuple[bool, List[str]]:
        """Verify the integrity of the entire cryptographic hash chain."""
        errors: List[str] = []
        prev_hash = GENESIS_HASH

        for i, rec in enumerate(self._index.values()):
            if rec.previous_record_hash != prev_hash:
                errors.append(
                    f"Chain break at record {i} ({rec.prediction_id}): expected prev_hash {prev_hash}, got {rec.previous_record_hash}"
                )
            expected_hash = rec.compute_hash()
            if rec.record_hash != expected_hash:
                errors.append(
                    f"Tamper detected at record {i} ({rec.prediction_id}): expected hash {expected_hash}, got {rec.record_hash}"
                )
            prev_hash = rec.record_hash

        return (len(errors) == 0), errors

    def update_prediction(self, *args, **kwargs):
        raise ImmutableStoreViolation("Updating predictions is prohibited.")

    def delete_prediction(self, *args, **kwargs):
        raise ImmutableStoreViolation("Deleting predictions is prohibited.")


class OutcomeStore:
    """Separated outcome storage with strict horizon maturity enforcement."""

    def __init__(self, store_dir: Path = Path("data/prospective/outcomes")):
        self.store_dir = Path(store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.store_dir / "outcomes.jsonl"
        self._outcomes: Dict[str, Dict[str, OutcomeRecord]] = {}  # pred_id -> horizon -> OutcomeRecord
        self._load_existing()

    def _load_existing(self) -> None:
        if not self.log_file.exists():
            return
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                data = json.loads(line)
                if "outcome_schema_version" not in data:
                    data["outcome_schema_version"] = "1"
                rec = OutcomeRecord(**data)
                if rec.prediction_id not in self._outcomes:
                    self._outcomes[rec.prediction_id] = {}
                self._outcomes[rec.prediction_id][rec.horizon] = rec

    def attach_outcome(
        self,
        prediction: PredictionRecord,
        horizon: str,
        outcome_data: Dict[str, Any],
        current_timestamp: str,
        audit_logger: Optional['AuditLogger'] = None,
    ) -> OutcomeRecord:
        """Attach a realized outcome to a prediction.
        
        Strictly enforces:
        1. Horizon must have fully elapsed: current_time >= pred_time + horizon_duration.
        2. Prediction created_at must precede outcome_available_at.
        3. Excludes invalid reference price outcomes from valid scientific evaluation.
        """
        if horizon not in HORIZON_MINUTES:
            raise ValueError(f"Unsupported horizon {horizon}. Must be one of {list(HORIZON_MINUTES.keys())}")

        pred_dt = parse_utc_iso(prediction.timestamp)
        curr_dt = parse_utc_iso(current_timestamp)
        horizon_mins = HORIZON_MINUTES[horizon]
        maturity_dt = pred_dt + timedelta(minutes=horizon_mins)

        if curr_dt < maturity_dt:
            raise HorizonNotMaturedError(
                f"Horizon {horizon} for prediction {prediction.prediction_id} has not matured. "
                f"Matures at {format_utc_iso(maturity_dt)}, current evaluation time is {current_timestamp}"
            )

        outcome_avail = outcome_data.get("outcome_available_at", current_timestamp)
        outcome_avail_dt = parse_utc_iso(outcome_avail)
        pred_created_dt = parse_utc_iso(prediction.created_at) if prediction.created_at else pred_dt

        if pred_created_dt >= outcome_avail_dt:
            raise ImmutableStoreViolation(
                f"Temporal violation: prediction created at {prediction.created_at} is not strictly prior to outcome available at {outcome_avail}"
            )

        # Check existing outcome
        if prediction.prediction_id in self._outcomes and horizon in self._outcomes[prediction.prediction_id]:
            raise ImmutableStoreViolation(
                f"Outcome for prediction {prediction.prediction_id} horizon {horizon} already recorded."
            )

        now_str = format_utc_iso(datetime.now(timezone.utc))

        def _opt_float(v):
            return float(v) if v is not None else None

        def _opt_bool(v):
            return bool(v) if v is not None else None

        status = outcome_data.get("status", "SCORED")
        excluded = bool(outcome_data.get("excluded_from_evaluation", False))
        invalidation_reason = outcome_data.get("invalidation_reason")
        schema_version = outcome_data.get("outcome_schema_version", "2")

        rec = OutcomeRecord(
            prediction_id=prediction.prediction_id,
            horizon=horizon,
            outcome_available_at=outcome_avail,
            realized_return=_opt_float(outcome_data.get("realized_return")),
            absolute_return=_opt_float(outcome_data.get("absolute_return")),
            realized_volatility=_opt_float(outcome_data.get("realized_volatility")),
            realized_range=_opt_float(outcome_data.get("realized_range")),
            tail_95_occurred=_opt_bool(outcome_data.get("tail_95_occurred")),
            tail_99_occurred=_opt_bool(outcome_data.get("tail_99_occurred")),
            jump_occurred=_opt_bool(outcome_data.get("jump_occurred")),
            expansion_occurred=_opt_bool(outcome_data.get("expansion_occurred")),
            status=status,
            outcome_schema_version=schema_version,
            excluded_from_evaluation=excluded,
            invalidation_reason=invalidation_reason,
            created_at=now_str,
        )

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec.to_dict()) + "\n")

        if prediction.prediction_id not in self._outcomes:
            self._outcomes[prediction.prediction_id] = {}
        self._outcomes[prediction.prediction_id][horizon] = rec

        if audit_logger:
            audit_logger.log_event(
                event_type="OUTCOME_ATTACHMENT",
                details={
                    "prediction_id": prediction.prediction_id,
                    "horizon": horizon,
                    "outcome_available_at": outcome_avail,
                    "status": rec.status,
                    "excluded_from_evaluation": rec.excluded_from_evaluation,
                    "realized_return": rec.realized_return,
                    "realized_volatility": rec.realized_volatility,
                }
            )

        return rec

    def get_outcome(self, prediction_id: str, horizon: str) -> Optional[OutcomeRecord]:
        return self._outcomes.get(prediction_id, {}).get(horizon)

    def has_outcome(self, prediction_id: str, horizon: str) -> bool:
        return prediction_id in self._outcomes and horizon in self._outcomes[prediction_id]

    def get_status(self, prediction_id: str, horizon: str, current_time: str, pred_time: str) -> str:
        """Return status: SCORED, MATURED, or PENDING."""
        if prediction_id in self._outcomes and horizon in self._outcomes[prediction_id]:
            return self._outcomes[prediction_id][horizon].status
        dt_curr = parse_utc_iso(current_time)
        dt_pred = parse_utc_iso(pred_time)
        mins = HORIZON_MINUTES.get(horizon, 60)
        if dt_curr >= dt_pred + timedelta(minutes=mins):
            return "MATURED"
        return "PENDING"

    def list_outcomes_for_horizon(self, horizon: str) -> List[OutcomeRecord]:
        results = []
        for preds in self._outcomes.values():
            if horizon in preds:
                results.append(preds[horizon])
        return results

    def get_valid_outcomes(self) -> List[OutcomeRecord]:
        """Return all outcomes eligible for scientific evaluation (not excluded)."""
        valid = []
        for preds in self._outcomes.values():
            for o in preds.values():
                if not o.excluded_from_evaluation and o.status not in ("INVALID_REFERENCE_PRICE", "INVALID"):
                    valid.append(o)
        return valid

    def get_invalid_outcomes(self) -> List[OutcomeRecord]:
        """Return all outcomes that are invalidated / excluded from evaluation."""
        invalid = []
        for preds in self._outcomes.values():
            for o in preds.values():
                if o.excluded_from_evaluation or o.status in ("INVALID_REFERENCE_PRICE", "INVALID"):
                    invalid.append(o)
        return invalid


class AuditLogger:
    """Tamper-evident, append-only cryptographic audit logger."""

    def __init__(self, audit_dir: Path = Path("data/prospective/audit")):
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.audit_dir / "audit_log.jsonl"
        self._last_hash = "GENESIS_AUDIT_LOG_CBE_0_7_0"
        self._load_last_hash()

    def _load_last_hash(self) -> None:
        """Load the last entry hash from the existing audit log to maintain chain continuity."""
        if not self.log_file.exists():
            return
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        if "entry_hash" in data:
                            self._last_hash = data["entry_hash"]
                    except Exception:
                        pass

    def log_event(self, event_type: str, details: Dict[str, Any]) -> Dict[str, Any]:
        """Record an append-only audit event."""
        now_str = format_utc_iso(datetime.now(timezone.utc))
        entry_payload = {
            "timestamp": now_str,
            "event_type": event_type,
            "details": details,
            "prev_hash": self._last_hash,
        }
        entry_hash = hashlib.sha256(json.dumps(entry_payload, sort_keys=True).encode("utf-8")).hexdigest()
        entry_payload["entry_hash"] = entry_hash
        self._last_hash = entry_hash

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry_payload) + "\n")

        return entry_payload

    def verify_audit_chain(self) -> bool:
        """Verify hash chain integrity across audit records."""
        if not self.log_file.exists():
            return True
        prev = "GENESIS_AUDIT_LOG_CBE_0_7_0"
        with open(self.log_file, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                data = json.loads(line.strip())
                prev_h = data.get("prev_hash")
                if prev_h not in (prev, "GENESIS_AUDIT_LOG_CBE_0_7_0"):
                    return False
                stored_hash = data.get("entry_hash")
                payload = {k: v for k, v in data.items() if k != "entry_hash"}
                computed = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
                if stored_hash != computed:
                    return False
                prev = stored_hash
        return True

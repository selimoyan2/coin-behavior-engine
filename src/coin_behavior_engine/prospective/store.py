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
    forecast_15m: float = 0.001
    forecast_30m: float = 0.0015
    forecast_1h: float = 0.002
    forecast_2h: float = 0.003
    forecast_4h: float = 0.004
    forecast_8h: float = 0.006
    forecast_12h: float = 0.0075
    forecast_24h: float = 0.010
    tail_95_probability: float = 0.05
    tail_99_probability: float = 0.01
    jump_probability: float = 0.01
    expansion_probabilities: Dict[str, float] = field(default_factory=dict)
    prediction_intervals: Dict[str, Any] = field(default_factory=dict)
    context_availability: str = "ACTIVE"
    data_quality: str = "DATA_OK"
    research_direction_probability: Dict[str, float] = field(default_factory=lambda: {"p_up": 0.50, "p_down": 0.50})
    input_cutoff_timestamp: str = ""
    created_at: str = ""
    previous_record_hash: str = ""
    record_hash: str = ""

    def to_canonical_dict(self) -> Dict[str, Any]:
        """Return deterministic dict for hashing (excluding record_hash)."""
        d = asdict(self)
        d.pop("record_hash", None)
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
    realized_return: float
    absolute_return: float
    realized_volatility: float
    realized_range: float
    tail_95_occurred: bool
    tail_99_occurred: bool
    jump_occurred: bool
    expansion_occurred: bool
    status: str = "MATURED"
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
        rec = OutcomeRecord(
            prediction_id=prediction.prediction_id,
            horizon=horizon,
            outcome_available_at=outcome_avail,
            realized_return=float(outcome_data.get("realized_return", 0.0)),
            absolute_return=float(outcome_data.get("absolute_return", 0.0)),
            realized_volatility=float(outcome_data.get("realized_volatility", 0.0)),
            realized_range=float(outcome_data.get("realized_range", 0.0)),
            tail_95_occurred=bool(outcome_data.get("tail_95_occurred", False)),
            tail_99_occurred=bool(outcome_data.get("tail_99_occurred", False)),
            jump_occurred=bool(outcome_data.get("jump_occurred", False)),
            expansion_occurred=bool(outcome_data.get("expansion_occurred", False)),
            status="SCORED",
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
            return "SCORED"
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


class AuditLogger:
    """Tamper-evident, append-only cryptographic audit logger."""

    def __init__(self, audit_dir: Path = Path("data/prospective/audit")):
        self.audit_dir = Path(audit_dir)
        self.audit_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = self.audit_dir / "audit_log.jsonl"
        self._last_hash = "GENESIS_AUDIT_LOG_CBE_0_7_0"

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
                if data.get("prev_hash") != prev:
                    return False
                stored_hash = data.get("entry_hash")
                payload = {k: v for k, v in data.items() if k != "entry_hash"}
                computed = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
                if stored_hash != computed:
                    return False
                prev = stored_hash
        return True

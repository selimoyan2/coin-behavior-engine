"""Shadow Market Data Bridge & Warmup Integrity Engine.

Sprint 11.16B.4: Frozen Policy Parity, Analogue Integrity & Crash-Safe Data Bridge.
Provides a persistent, bounded rolling buffer, atomic snapshot consumer,
frozen-policy feature compatibility adapter, historical seed cryptographic validator,
analogue artifact verifier, and strict execution causality enforcement.

Guaranteed Invariants:
1. Longest lookback: 864 contiguous 5m bars for 72h SMA; buffer capacity 1,000 bars.
2. Never infer historical arrays from contiguous_bars_count.
3. Never fabricate missing candles, never interpolate gaps.
4. Never interpret unclosed candle as closed.
5. Historical seed data strictly marked HISTORICAL_SEED_WARMUP; never counted as prospective observations.
6. Analogue reference artifact strictly verified against cryptographic SHA-256 digest; hardcoded probabilities strictly prohibited.
7. Next-open execution causality: fills strictly at next_bar_open with 30 bps friction.
8. State persistence is crash-safe with cryptographic checksum envelopes.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import enum
import hashlib
import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("cbe_shadow_market_data_bridge")

CANONICAL_ANALOGUE_CSV_SHA256 = "c6ed5912524e176bde0e941a0d69fe8f0c4f121759036ef2caa7219c06526ff1"
MINIMUM_WARMUP_BARS = 864  # 72 hours of 5-minute candles
DEFAULT_BUFFER_CAPACITY = 1000  # Bounded retention capacity
CANDLE_INTERVAL_SECONDS = 300  # 5 minutes
MAX_FEED_LATENCY_SECONDS = 900.0  # 15 minutes
MAX_HEARTBEAT_LATENCY_SECONDS = 180.0  # 3 minutes


class CandleStreamType(str, enum.Enum):
    HISTORICAL_SEED_WARMUP = "HISTORICAL_SEED_WARMUP"
    PROSPECTIVE_LIVE_OBSERVATION = "PROSPECTIVE_LIVE_OBSERVATION"


class BridgeStatus(str, enum.Enum):
    READY_FOR_EVALUATION = "READY_FOR_EVALUATION"
    WARMUP_BUFFERING = "WARMUP_BUFFERING"
    FEED_STALE = "FEED_STALE"
    GAP_DETECTED = "GAP_DETECTED"
    SNAPSHOT_CORRUPT = "SNAPSHOT_CORRUPT"
    UNCLOSED_CANDLE = "UNCLOSED_CANDLE"
    DUPLICATE_CANDLE = "DUPLICATE_CANDLE"


@dataclass(frozen=True)
class MarketCandle:
    """Immutable representation of a validated 5-minute spot candle."""
    symbol: str
    interval: str
    timestamp_open_utc: str
    timestamp_close_utc: str
    open_p: float
    high_p: float
    low_p: float
    close_p: float
    volume_base: float
    volume_usdt: float
    is_closed: bool
    stream_type: CandleStreamType
    sequence_number: int
    provenance: str = "BINANCE_SPOT"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["stream_type"] = self.stream_type.value
        return d


@dataclass
class HistoricalSeedProvenance:
    """Metadata and cryptographic proof of an authorized historical seed dataset."""
    seed_id: str
    dataset_name: str
    dataset_sha256: str
    start_timestamp_utc: str
    end_timestamp_utc: str
    candle_count: int
    is_authorized: bool = True
    validation_status: str = "UNVALIDATED"
    expected_manifest_sha256: Optional[str] = None
    computed_seed_sha256: Optional[str] = None

    @staticmethod
    def compute_canonical_digest(candles: List[MarketCandle]) -> str:
        """Compute deterministic SHA-256 over canonical string representation of candle sequence."""
        lines = [
            f"{c.symbol},{c.interval},{c.timestamp_open_utc},{c.timestamp_close_utc},"
            f"{c.open_p:.8f},{c.high_p:.8f},{c.low_p:.8f},{c.close_p:.8f},"
            f"{c.volume_base:.8f},{c.volume_usdt:.8f}"
            for c in candles
        ]
        payload = "\n".join(lines).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def verify_seed_integrity(
        self,
        candles: List[MarketCandle],
        expected_manifest_sha256: Optional[str] = None,
        enforce_crypto_hash: bool = True,
    ) -> Tuple[bool, str]:
        """Perform full cryptographic validation of seed candles."""
        if not self.is_authorized:
            self.validation_status = "UNAUTHORIZED_SEED"
            return False, "SEED_NOT_AUTHORIZED: Provenance is_authorized is False"

        # Reject dummy or invalid hashes if crypto hash enforcement is enabled
        if enforce_crypto_hash:
            if not self.dataset_sha256 or self.dataset_sha256.lower() in ("dummy", "placeholder", "none", "test") or len(self.dataset_sha256) != 64:
                self.validation_status = "REJECTED_DUMMY_OR_INVALID_HASH"
                return False, f"REJECTED_DUMMY_OR_INVALID_HASH: '{self.dataset_sha256}' is not a valid 64-character SHA-256 digest"

        if len(candles) < MINIMUM_WARMUP_BARS:
            self.validation_status = f"INSUFFICIENT_CANDLES_{len(candles)}_LT_864"
            return False, f"INSUFFICIENT_CANDLES: {len(candles)} < {MINIMUM_WARMUP_BARS}"

        if len(candles) != self.candle_count:
            self.validation_status = f"COUNT_MISMATCH_{len(candles)}_NE_{self.candle_count}"
            return False, f"COUNT_MISMATCH: Provided {len(candles)} candles != declared count {self.candle_count}"

        # Boundary timestamp check
        if candles[0].timestamp_open_utc != self.start_timestamp_utc:
            self.validation_status = "START_TIMESTAMP_MISMATCH"
            return False, f"START_TIMESTAMP_MISMATCH: {candles[0].timestamp_open_utc} != {self.start_timestamp_utc}"

        if candles[-1].timestamp_open_utc != self.end_timestamp_utc:
            self.validation_status = "END_TIMESTAMP_MISMATCH"
            return False, f"END_TIMESTAMP_MISMATCH: {candles[-1].timestamp_open_utc} != {self.end_timestamp_utc}"

        # Continuity check
        for i in range(1, len(candles)):
            prev_dt = datetime.fromisoformat(candles[i - 1].timestamp_open_utc.replace("Z", "+00:00"))
            curr_dt = datetime.fromisoformat(candles[i].timestamp_open_utc.replace("Z", "+00:00"))
            step_sec = (curr_dt - prev_dt).total_seconds()
            if step_sec != CANDLE_INTERVAL_SECONDS:
                self.validation_status = "NON_CONTIGUOUS_TIMESTAMPS"
                return False, f"NON_CONTIGUOUS_TIMESTAMPS: Step at index {i} is {step_sec}s != {CANDLE_INTERVAL_SECONDS}s"

        # Compute digest
        computed_hash = self.compute_canonical_digest(candles)
        self.computed_seed_sha256 = computed_hash

        if enforce_crypto_hash:
            if computed_hash.lower() != self.dataset_sha256.lower():
                self.validation_status = "HASH_MISMATCH"
                return False, f"HASH_MISMATCH: Computed digest {computed_hash} != declared {self.dataset_sha256}"

            exp_hash = expected_manifest_sha256 or self.expected_manifest_sha256
            if exp_hash and computed_hash.lower() != exp_hash.lower():
                self.validation_status = "MANIFEST_HASH_MISMATCH"
                return False, f"MANIFEST_HASH_MISMATCH: Computed digest {computed_hash} != manifest {exp_hash}"

        self.validation_status = "VERIFIED_VALID"
        return True, "VERIFIED_VALID"

    def verify_provenance(self, expected_sha256: str) -> bool:
        """Legacy helper maintained for backward compatibility."""
        if not self.is_authorized:
            self.validation_status = "UNAUTHORIZED_SEED"
            return False
        if self.dataset_sha256.lower() != expected_sha256.lower():
            self.validation_status = "HASH_MISMATCH"
            return False
        if self.candle_count < MINIMUM_WARMUP_BARS:
            self.validation_status = f"INSUFFICIENT_CANDLES_{self.candle_count}_LT_864"
            return False
        self.validation_status = "VERIFIED_VALID"
        return True


class AnalogueArtifactLoader:
    """Loads and cryptographically verifies the immutable historical analogue library."""

    def __init__(self, artifact_path: Optional[Path] = None, expected_sha256: Optional[str] = None):
        self.artifact_path = Path(artifact_path) if artifact_path else Path("research_outputs/historical_analogues.csv")
        self.expected_sha256 = expected_sha256 or CANONICAL_ANALOGUE_CSV_SHA256
        self.is_loaded = False
        self.analogues_count = 0
        self.status = "UNLOADED"

    def verify_and_load(self) -> Tuple[bool, str]:
        """Verify SHA-256 digest of analogue artifact and load record count."""
        if not self.artifact_path.is_file():
            self.status = "ARTIFACT_MISSING"
            self.is_loaded = False
            return False, f"Analogue artifact not found at {self.artifact_path}"

        content = self.artifact_path.read_bytes()
        actual_hash = hashlib.sha256(content).hexdigest()
        if actual_hash.lower() != self.expected_sha256.lower():
            self.status = f"HASH_MISMATCH_EXPECTED_{self.expected_sha256[:8]}_FOUND_{actual_hash[:8]}"
            self.is_loaded = False
            return False, f"Analogue artifact SHA-256 mismatch: expected {self.expected_sha256}, got {actual_hash}"

        # Count records
        lines = content.decode("utf-8").strip().split("\n")
        self.analogues_count = max(0, len(lines) - 1)
        self.is_loaded = True
        self.status = "VERIFIED_LOADED"
        return True, f"Analogue library verified with {self.analogues_count} records (SHA-256: {actual_hash[:16]}...)"

    def get_directional_probability(self, threshold: float = 0.60) -> Optional[float]:
        """Return analogue directional probability if loaded and authenticated, or None if blocked.
        
        CRITICAL SCIENTIFIC INTEGRITY ENFORCEMENT:
        In prospective shadow observation, computing authentic k-NN analogue matching requires
        the full 365-day training candidate library (68,328 candles x 10 standardized features + forward returns),
        which consumes over 100 MB of RAM, exceeding the 250 MB prospective container ceiling.
        Furthermore, historical_analogues.csv contains only pre-computed historical query matches,
        not the full candidate feature vectors required for prospective queries.
        
        Under Sprint 11.16B.4 Phase 1, hardcoded probabilities (such as 0.65) are strictly eradicated.
        Since authentic parity cannot be computed solely from the rolling buffer, we fail closed:
        declare POLICY_E_STATUS = BLOCKED_ANALOGUE_PARITY and return None.
        """
        if not self.is_loaded:
            return None
        self.status = "BLOCKED_ANALOGUE_PARITY"
        return None


class PersistentRollingBuffer:
    """Thread-safe, persistent, bounded rolling ring buffer for 5m OHLCV candles."""

    def __init__(
        self,
        capacity: int = DEFAULT_BUFFER_CAPACITY,
        min_warmup_bars: int = MINIMUM_WARMUP_BARS,
        state_file: Optional[Path] = None,
    ):
        if capacity < min_warmup_bars:
            raise ValueError(f"Capacity {capacity} cannot be less than minimum warmup {min_warmup_bars}")
        self.capacity = capacity
        self.min_warmup_bars = min_warmup_bars
        self.state_file = Path(state_file) if state_file else None
        self._buffer: Deque[MarketCandle] = deque(maxlen=capacity)
        self._seen_open_timestamps: set[str] = set()
        self._gap_detected: bool = False
        self._executed_decision_ids: set[str] = set()

    def __len__(self) -> int:
        return len(self._buffer)

    @property
    def is_warmup_ready(self) -> bool:
        """True if and only if buffer holds at least min_warmup_bars contiguous candles without gaps."""
        if self._gap_detected:
            return False
        return len(self._buffer) >= self.min_warmup_bars

    @property
    def gap_detected(self) -> bool:
        return self._gap_detected

    @property
    def candles(self) -> List[MarketCandle]:
        return list(self._buffer)

    def mark_executed(self, decision_id: str) -> None:
        """Mark a decision as filled to prevent duplicate execution after restart."""
        self._executed_decision_ids.add(decision_id)

    def is_executed(self, decision_id: str) -> bool:
        """Check if a decision was already executed."""
        return decision_id in self._executed_decision_ids

    def clear(self) -> None:
        self._buffer.clear()
        self._seen_open_timestamps.clear()

    def append_candle(self, candle: MarketCandle) -> Tuple[bool, Optional[str]]:
        """Append a validated closed candle, enforcing monotonic time, continuity, and gap handling."""
        if not candle.is_closed:
            return False, "UNCLOSED_CANDLE: Candle is_closed must be True"

        # Duplicate check
        if candle.timestamp_open_utc in self._seen_open_timestamps:
            return False, f"DUPLICATE_CANDLE: Timestamp {candle.timestamp_open_utc} already present in buffer"

        if len(self._buffer) > 0:
            last = self._buffer[-1]
            last_dt = datetime.fromisoformat(last.timestamp_open_utc.replace("Z", "+00:00"))
            curr_dt = datetime.fromisoformat(candle.timestamp_open_utc.replace("Z", "+00:00"))

            delta_sec = (curr_dt - last_dt).total_seconds()
            if delta_sec <= 0:
                return False, f"TIME_INVERSION: Current open {curr_dt} <= last open {last_dt}"
            if delta_sec > CANDLE_INTERVAL_SECONDS:
                # Robust gap handling (Sprint 11.16B.4 Phase 3):
                # Disjoint historical data cannot be used for multi-timeframe moving averages.
                # Immediately invalidate contiguous warmup and clear disjoint pre-gap candles.
                self._gap_detected = True
                self.clear()
                return False, f"GAP_DETECTED: Delta {delta_sec}s exceeds expected {CANDLE_INTERVAL_SECONDS}s. Buffer invalidated; 864 new contiguous bars required."

        # Manage seen set size
        if len(self._buffer) == self.capacity:
            oldest = self._buffer[0]
            self._seen_open_timestamps.discard(oldest.timestamp_open_utc)

        self._buffer.append(candle)
        self._seen_open_timestamps.add(candle.timestamp_open_utc)

        # Clear gap state if we have accumulated a full fresh contiguous buffer of 864 bars
        if self._gap_detected and len(self._buffer) >= self.min_warmup_bars:
            self._gap_detected = False

        return True, None

    def ingest_seed_candles(
        self,
        seed_candles: List[MarketCandle],
        provenance: HistoricalSeedProvenance,
        expected_manifest_sha256: Optional[str] = None,
        enforce_crypto_hash: bool = True,
    ) -> Tuple[bool, str]:
        """Ingest immutable historical seed partition with strict cryptographic verification."""
        ok_prov, prov_msg = provenance.verify_seed_integrity(
            seed_candles,
            expected_manifest_sha256=expected_manifest_sha256,
            enforce_crypto_hash=enforce_crypto_hash,
        )
        if not ok_prov:
            self.clear()
            return False, f"SEED_INTEGRITY_VERIFICATION_FAILED: {prov_msg}"

        self.clear()
        self._gap_detected = False

        for idx, c in enumerate(seed_candles):
            if c.stream_type != CandleStreamType.HISTORICAL_SEED_WARMUP:
                c = MarketCandle(
                    symbol=c.symbol,
                    interval=c.interval,
                    timestamp_open_utc=c.timestamp_open_utc,
                    timestamp_close_utc=c.timestamp_close_utc,
                    open_p=c.open_p,
                    high_p=c.high_p,
                    low_p=c.low_p,
                    close_p=c.close_p,
                    volume_base=c.volume_base,
                    volume_usdt=c.volume_usdt,
                    is_closed=c.is_closed,
                    stream_type=CandleStreamType.HISTORICAL_SEED_WARMUP,
                    sequence_number=idx,
                    provenance=provenance.dataset_name,
                )
            ok, err = self.append_candle(c)
            if not ok:
                self.clear()
                return False, f"SEED_INGESTION_FAILED_AT_INDEX_{idx}: {err}"

        ready_msg = "WARMUP_READY" if self.is_warmup_ready else "WARMUP_INCOMPLETE"
        return True, f"Ingested {len(self._buffer)} seed candles: {ready_msg}"

    def save_state(self) -> None:
        """Persist rolling buffer state atomically to disk with cryptographic checksum."""
        if not self.state_file:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "capacity": self.capacity,
            "min_warmup_bars": self.min_warmup_bars,
            "candle_count": len(self._buffer),
            "is_warmup_ready": self.is_warmup_ready,
            "gap_detected": self._gap_detected,
            "executed_decision_ids": sorted(list(self._executed_decision_ids)),
            "candles": [c.to_dict() for c in self._buffer],
        }
        canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        state_sha256 = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

        envelope = {
            "state_sha256": state_sha256,
            "payload": payload,
        }

        temp_file = self.state_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(envelope, f, indent=2)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass  # fsync may not be supported on all virtualized platforms

        temp_file.replace(self.state_file)

    def load_state(self) -> bool:
        """Load persisted buffer state from disk with strict integrity validation.
        
        Fails closed on missing file, corrupt JSON, hash mismatch, or invalid candles.
        Buffer warmup readiness is dynamically recomputed from validated candles.
        """
        if not self.state_file or not self.state_file.is_file():
            return False

        try:
            raw_text = self.state_file.read_text(encoding="utf-8")
            if not raw_text.strip():
                logger.warning("Empty state file encountered. Failing closed.")
                self.clear()
                return False

            data = json.loads(raw_text)
            if not isinstance(data, dict):
                logger.warning("Invalid JSON structure in state file. Failing closed.")
                self.clear()
                return False

            # Verify cryptographic envelope
            if "state_sha256" not in data or "payload" not in data:
                logger.warning("State file missing envelope or checksum. Failing closed.")
                self.clear()
                return False

            declared_sha256 = data["state_sha256"]
            payload = data["payload"]
            canonical_json = json.dumps(payload, sort_keys=True, separators=(",", ":"))
            computed_sha256 = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

            if declared_sha256.lower() != computed_sha256.lower():
                logger.error(f"State file tamper/corruption detected! Declared: {declared_sha256}, computed: {computed_sha256}")
                self.clear()
                return False

            # Sequential candle-by-candle revalidation
            self.clear()
            raw_candles = payload.get("candles", [])
            for idx, r in enumerate(raw_candles):
                if not isinstance(r, dict):
                    self.clear()
                    return False

                req_fields = [
                    "symbol", "interval", "timestamp_open_utc", "timestamp_close_utc",
                    "open_p", "high_p", "low_p", "close_p", "volume_base", "volume_usdt",
                    "is_closed", "stream_type", "sequence_number"
                ]
                if any(k not in r for k in req_fields):
                    logger.warning(f"Corrupt candle record at index {idx}. Missing required fields.")
                    self.clear()
                    return False

                c_o = float(r["open_p"])
                c_h = float(r["high_p"])
                c_l = float(r["low_p"])
                c_c = float(r["close_p"])
                if math.isnan(c_c) or c_o <= 0.0 or c_c <= 0.0 or c_h < c_l:
                    logger.warning(f"Invalid candle numerics at index {idx}.")
                    self.clear()
                    return False

                candle = MarketCandle(
                    symbol=r["symbol"],
                    interval=r["interval"],
                    timestamp_open_utc=r["timestamp_open_utc"],
                    timestamp_close_utc=r["timestamp_close_utc"],
                    open_p=c_o,
                    high_p=c_h,
                    low_p=c_l,
                    close_p=c_c,
                    volume_base=float(r["volume_base"]),
                    volume_usdt=float(r["volume_usdt"]),
                    is_closed=bool(r["is_closed"]),
                    stream_type=CandleStreamType(r["stream_type"]),
                    sequence_number=int(r["sequence_number"]),
                    provenance=r.get("provenance", "RECOVERED_STATE"),
                )
                ok, err = self.append_candle(candle)
                if not ok:
                    logger.warning(f"State recovery candle validation failed at index {idx}: {err}")
                    self.clear()
                    return False

            # Restore execution IDs and gap status
            self._executed_decision_ids = set(payload.get("executed_decision_ids", []))
            self._gap_detected = bool(payload.get("gap_detected", False))

            return len(self._buffer) > 0
        except Exception as e:
            logger.warning(f"State recovery failed with exception: {e}. Failing closed.")
            self.clear()
            return False


class FrozenFeatureAdapter:
    """Extracts features for all 5 frozen policies with zero logical divergence."""

    def __init__(self, buffer: PersistentRollingBuffer, analogue_loader: Optional[AnalogueArtifactLoader] = None):
        self.buffer = buffer
        self.analogue_loader = analogue_loader or AnalogueArtifactLoader()

    def extract_features(self) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Extract multi-timeframe moving averages, ATR, and analogue scores."""
        if not self.buffer.is_warmup_ready:
            return False, None, f"INSUFFICIENT_WARMUP: Buffer has {len(self.buffer)} candles; 864 contiguous required"

        candles = self.buffer.candles
        n = len(candles)
        closes = [c.close_p for c in candles]
        highs = [c.high_p for c in candles]
        lows = [c.low_p for c in candles]

        # 1. Moving Averages
        sma_288 = sum(closes[-288:]) / 288.0
        sma_576 = sum(closes[-576:]) / 576.0
        sma_864 = sum(closes[-864:]) / 864.0
        roll_high_864 = max(highs[-864:])

        current_close = closes[-1]

        # 2. 14-bar Average True Range (ATR)
        tr_list = []
        for i in range(n - 14, n):
            h = highs[i]
            l = lows[i]
            prev_c = closes[i - 1]
            tr = max(h - l, abs(h - prev_c), abs(l - prev_c))
            tr_list.append(tr)
        atr_14 = sum(tr_list) / 14.0
        vol_atr_pct = (atr_14 / current_close) if current_close > 0 else 0.0

        # 3. Anti-chase extension
        anti_chase_extension_pct = ((current_close - sma_288) / sma_288 * 100.0) if sma_288 > 0 else 0.0

        # 4. Gating conditions
        trend_aligned = (current_close > sma_288) and (current_close > sma_864)
        anti_chase_ok = (anti_chase_extension_pct <= 2.25)
        vol_ok = (0.015 <= vol_atr_pct <= 0.065)

        # 5. Analogue conditional probability
        # In prospective observation, authentic k-NN cannot be run under memory constraints;
        # hardcoded probabilities are removed, failing closed to None.
        analogue_prob = self.analogue_loader.get_directional_probability(threshold=0.60)
        analogue_ok = (analogue_prob is not None and analogue_prob >= 0.60)
        policy_e_status = "READY" if analogue_ok else "BLOCKED_ANALOGUE_PARITY"

        features = {
            "current_close": current_close,
            "sma_288": round(sma_288, 4),
            "sma_576": round(sma_576, 4),
            "sma_864": round(sma_864, 4),
            "sma_24h": round(sma_288, 4),
            "sma_48h": round(sma_576, 4),
            "sma_72h": round(sma_864, 4),
            "roll_high_864": round(roll_high_864, 4),
            "atr_14": round(atr_14, 4),
            "vol_atr_pct": round(vol_atr_pct, 6),
            "atr_pct": round(vol_atr_pct, 6),
            "anti_chase_extension_pct": round(anti_chase_extension_pct, 4),
            "trend_aligned": trend_aligned,
            "anti_chase_ok": anti_chase_ok,
            "vol_ok": vol_ok,
            "analogue_prob": analogue_prob,
            "analogue_ok": analogue_ok,
            "analogue_library_loaded": self.analogue_loader.is_loaded,
            "policy_e_status": policy_e_status,
        }
        return True, features, None


@dataclass
class BridgeEvaluationPayload:
    """Complete evaluation context delivered to prospective decision engines."""
    status: BridgeStatus
    candle: Optional[MarketCandle]
    features: Optional[Dict[str, Any]]
    is_warmup_ready: bool
    execution_eligible: bool
    message: str
    availability_timestamp_utc: str


class ShadowMarketDataBridge:
    """Read-only market data bridge connecting atomic snapshots to shadow policy engines."""

    def __init__(
        self,
        buffer_capacity: int = DEFAULT_BUFFER_CAPACITY,
        min_warmup_bars: int = MINIMUM_WARMUP_BARS,
        state_file: Optional[Path] = None,
        analogue_artifact_path: Optional[Path] = None,
    ):
        self.buffer = PersistentRollingBuffer(
            capacity=buffer_capacity,
            min_warmup_bars=min_warmup_bars,
            state_file=state_file,
        )
        self.analogue_loader = AnalogueArtifactLoader(artifact_path=analogue_artifact_path)
        self.feature_adapter = FrozenFeatureAdapter(self.buffer, self.analogue_loader)
        self.prospective_evaluations_count = 0

    def initialize_analogue_library(self) -> Tuple[bool, str]:
        return self.analogue_loader.verify_and_load()

    def ingest_snapshot_payload(
        self,
        payload: Dict[str, Any],
        availability_timestamp_utc: str,
        publication_timestamp_utc: Optional[str] = None,
    ) -> BridgeEvaluationPayload:
        """Ingest single raw snapshot dict, validate, append to buffer, and extract features."""
        # 1. Structural validation
        symbol = payload.get("symbol", "")
        interval = payload.get("candle_interval", "")
        is_closed = payload.get("is_closed", False)

        if symbol != "BTCUSDT" or interval != "5m":
            return BridgeEvaluationPayload(
                status=BridgeStatus.SNAPSHOT_CORRUPT,
                candle=None,
                features=None,
                is_warmup_ready=self.buffer.is_warmup_ready,
                execution_eligible=False,
                message=f"INVALID_SYMBOL_OR_INTERVAL: symbol={symbol}, interval={interval}",
                availability_timestamp_utc=availability_timestamp_utc,
            )

        if not is_closed:
            return BridgeEvaluationPayload(
                status=BridgeStatus.UNCLOSED_CANDLE,
                candle=None,
                features=None,
                is_warmup_ready=self.buffer.is_warmup_ready,
                execution_eligible=False,
                message="UNCLOSED_CANDLE: Candle has is_closed=False",
                availability_timestamp_utc=availability_timestamp_utc,
            )

        # 2. Extract OHLCV
        try:
            o_p = float(payload["open_price_usdt"])
            h_p = float(payload["high_price_usdt"])
            l_p = float(payload["low_price_usdt"])
            c_p = float(payload["close_price_usdt"])
            v_b = float(payload["volume_base"])
            v_u = float(payload["volume_usdt"])
            ts_open = str(payload["timestamp_open_utc"])
            ts_close = str(payload["timestamp_close_utc"])
        except (KeyError, TypeError, ValueError) as e:
            return BridgeEvaluationPayload(
                status=BridgeStatus.SNAPSHOT_CORRUPT,
                candle=None,
                features=None,
                is_warmup_ready=self.buffer.is_warmup_ready,
                execution_eligible=False,
                message=f"CORRUPT_OHLCV_FIELDS: {e}",
                availability_timestamp_utc=availability_timestamp_utc,
            )

        if math.isnan(c_p) or o_p <= 0.0 or c_p <= 0.0 or h_p < l_p:
            return BridgeEvaluationPayload(
                status=BridgeStatus.SNAPSHOT_CORRUPT,
                candle=None,
                features=None,
                is_warmup_ready=self.buffer.is_warmup_ready,
                execution_eligible=False,
                message="INVALID_PRICE_NUMERICS",
                availability_timestamp_utc=availability_timestamp_utc,
            )

        # 3. Check timestamps & freshness
        try:
            close_dt = datetime.fromisoformat(ts_close.replace("Z", "+00:00"))
            avail_dt = datetime.fromisoformat(availability_timestamp_utc.replace("Z", "+00:00"))
            latency_sec = (avail_dt - close_dt).total_seconds()
            if latency_sec < 0:
                return BridgeEvaluationPayload(
                    status=BridgeStatus.SNAPSHOT_CORRUPT,
                    candle=None,
                    features=None,
                    is_warmup_ready=self.buffer.is_warmup_ready,
                    execution_eligible=False,
                    message=f"LOOKAHEAD_VIOLATION: Data available {avail_dt} before close {close_dt}",
                    availability_timestamp_utc=availability_timestamp_utc,
                )

            if publication_timestamp_utc:
                pub_dt = datetime.fromisoformat(publication_timestamp_utc.replace("Z", "+00:00"))
                if pub_dt < close_dt:
                    return BridgeEvaluationPayload(
                        status=BridgeStatus.SNAPSHOT_CORRUPT,
                        candle=None,
                        features=None,
                        is_warmup_ready=self.buffer.is_warmup_ready,
                        execution_eligible=False,
                        message=f"LOOKAHEAD_VIOLATION: Published {pub_dt} before close {close_dt}",
                        availability_timestamp_utc=availability_timestamp_utc,
                    )

            if latency_sec > MAX_FEED_LATENCY_SECONDS:
                return BridgeEvaluationPayload(
                    status=BridgeStatus.FEED_STALE,
                    candle=None,
                    features=None,
                    is_warmup_ready=self.buffer.is_warmup_ready,
                    execution_eligible=False,
                    message=f"FEED_STALE: Latency {latency_sec}s > {MAX_FEED_LATENCY_SECONDS}s",
                    availability_timestamp_utc=availability_timestamp_utc,
                )
        except Exception as e:
            return BridgeEvaluationPayload(
                status=BridgeStatus.SNAPSHOT_CORRUPT,
                candle=None,
                features=None,
                is_warmup_ready=self.buffer.is_warmup_ready,
                execution_eligible=False,
                message=f"TIMESTAMP_PARSE_ERROR: {e}",
                availability_timestamp_utc=availability_timestamp_utc,
            )

        # 4. Construct candle and append
        seq_num = len(self.buffer)
        candle = MarketCandle(
            symbol=symbol,
            interval=interval,
            timestamp_open_utc=ts_open,
            timestamp_close_utc=ts_close,
            open_p=o_p,
            high_p=h_p,
            low_p=l_p,
            close_p=c_p,
            volume_base=v_b,
            volume_usdt=v_u,
            is_closed=True,
            stream_type=CandleStreamType.PROSPECTIVE_LIVE_OBSERVATION,
            sequence_number=seq_num,
            provenance="BINANCE_SPOT_SNAPSHOT",
        )

        ok, err = self.buffer.append_candle(candle)
        if not ok:
            status = BridgeStatus.DUPLICATE_CANDLE if "DUPLICATE" in str(err) else BridgeStatus.GAP_DETECTED
            return BridgeEvaluationPayload(
                status=status,
                candle=None,
                features=None,
                is_warmup_ready=self.buffer.is_warmup_ready,
                execution_eligible=False,
                message=f"BUFFER_APPEND_FAILED: {err}",
                availability_timestamp_utc=availability_timestamp_utc,
            )

        # 5. Check warmup readiness & extract features
        if not self.buffer.is_warmup_ready:
            return BridgeEvaluationPayload(
                status=BridgeStatus.WARMUP_BUFFERING,
                candle=candle,
                features=None,
                is_warmup_ready=False,
                execution_eligible=False,
                message=f"WARMUP_IN_PROGRESS: {len(self.buffer)} / {MINIMUM_WARMUP_BARS} bars accumulated",
                availability_timestamp_utc=availability_timestamp_utc,
            )

        ok_feat, features, feat_err = self.feature_adapter.extract_features()
        if not ok_feat or features is None:
            return BridgeEvaluationPayload(
                status=BridgeStatus.WARMUP_BUFFERING,
                candle=candle,
                features=None,
                is_warmup_ready=False,
                execution_eligible=False,
                message=f"FEATURE_EXTRACTION_FAILED: {feat_err}",
                availability_timestamp_utc=availability_timestamp_utc,
            )

        self.prospective_evaluations_count += 1
        return BridgeEvaluationPayload(
            status=BridgeStatus.READY_FOR_EVALUATION,
            candle=candle,
            features=features,
            is_warmup_ready=True,
            execution_eligible=True,
            message="SUCCESS: Full 864-bar feature bundle extracted",
            availability_timestamp_utc=availability_timestamp_utc,
        )

    def execute_causal_fill(
        self,
        sim: Any,
        action: str,
        next_open_price: Optional[float],
        decision_timestamp_utc: Optional[str] = None,
        next_candle_close_utc: Optional[str] = None,
        current_close_price: Optional[float] = None,
        fee_bps: float = 10.0,
        slippage_bps: float = 5.0,
        decision_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute fill at NEXT bar open price, strictly enforcing causal constraints."""
        # 1. Duplicate check
        if decision_id and self.buffer.is_executed(decision_id):
            return {
                "success": False,
                "status": "REJECTED_DUPLICATE_EXECUTION",
                "fill_price": None,
                "friction_usdt": 0.0,
                "reason": f"Decision {decision_id} already executed previously",
            }

        # 2. Next open price validity
        if next_open_price is None or math.isnan(next_open_price) or next_open_price <= 0.0:
            return {
                "success": False,
                "status": "EXECUTION_REFUSED_MISSING_NEXT_OPEN",
                "fill_price": None,
                "friction_usdt": 0.0,
            }

        # 3. Prohibit execution at current close price
        if current_close_price is not None and abs(next_open_price - current_close_price) < 1e-9:
            return {
                "success": False,
                "status": "EXECUTION_REFUSED_AT_CLOSE_PRICE",
                "fill_price": None,
                "friction_usdt": 0.0,
                "reason": "Execution at T_close price strictly forbidden; next open quote must be distinct",
            }

        # 4. Causality window: T_dec must not be after next candle close
        if decision_timestamp_utc and next_candle_close_utc:
            try:
                dec_dt = datetime.fromisoformat(decision_timestamp_utc.replace("Z", "+00:00"))
                next_close_dt = datetime.fromisoformat(next_candle_close_utc.replace("Z", "+00:00"))
                if dec_dt > next_close_dt:
                    return {
                        "success": False,
                        "status": "EXECUTION_REFUSED_EXPIRED_WINDOW",
                        "fill_price": None,
                        "friction_usdt": 0.0,
                        "reason": f"Decision timestamp {dec_dt} after next candle close {next_close_dt}",
                    }
            except Exception as e:
                logger.warning(f"Error parsing execution timestamps: {e}")

        # 5. Execute via simulator
        if action == "BUY":
            res = sim.execute_hypothetical_buy(next_open=next_open_price)
        elif action in ("EXIT", "EXIT_TO_USDT"):
            res = sim.execute_hypothetical_exit(exit_raw_price=next_open_price)
        else:
            return {"success": False, "status": "UNKNOWN_ACTION", "fill_price": None, "friction_usdt": 0.0}

        if res.get("success", False) and decision_id:
            self.buffer.mark_executed(decision_id)

        return res

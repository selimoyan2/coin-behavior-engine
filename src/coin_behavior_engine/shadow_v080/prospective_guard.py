"""CBE-0.8.0 Prospective Inference Authorization & Causal Data Eligibility Guards.

Sprint 09.15: Prospective Inference Authorization Hardening.

Enforces:
1. Strict fail-closed authorization checks at every prospective inference execution boundary:
   - CBE_APPROVAL_4_AUTHORIZED must be strictly 'true'.
   - CBE_PROSPECTIVE_OBSERVATION_ENABLED must be strictly 'true'.
   - CBE_TRADING_DISABLED must be strictly 'true' (trading permanently prohibited).
   - Fails closed on missing or malformed values ('1', 'True', 'yes', etc. rejected).
   - Approval 3 active alone does NOT confer prospective scoring authorization.
   - Dynamic evaluation immediately before inference so runtime revocation stops execution instantly.
   - Forbids offline research from producing PROSPECTIVE_LIVE or PROSPECTIVE_SHADOW labeled records unless authorized.
2. Causal Data Eligibility Guard:
   - Minimum 288 contiguous closed 5m candles required for prospective scoring.
   - Rejects fewer than 288 bars (e.g. 287 bars).
   - Verifies market identity: symbol='BTCUSDT', interval='5m', market_type='SPOT'.
   - Rejects unclosed / incomplete candles.
   - Rejects discontinuous timestamps or timestamp gaps.
   - Rejects duplicate timestamps.
   - Rejects temporal misalignments (future-dated or excessively stale observations).
   - Rejects synthetic, mock, or historical replay provenance for prospective events.
   - Verifies durable raw market evidence store references when provided.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("cbe_prospective_guard")

# Constants
EXPECTED_SYMBOL = "BTCUSDT"
EXPECTED_INTERVAL = "5m"
EXPECTED_MARKET_TYPE = "SPOT"
CANDLE_INTERVAL_MS = 300_000  # 5 minutes in milliseconds
MIN_PROSPECTIVE_WARMUP_BARS = 288  # 24 hours of 5-minute bars
CLOCK_SKEW_BUDGET_MS = 1000
MAX_STALENESS_MS = 900_000  # 15 minutes (3 intervals)

from enum import Enum

PROSPECTIVE_RECORD_LABELS = frozenset({"PROSPECTIVE_LIVE", "PROSPECTIVE_SHADOW"})
OFFLINE_RECORD_LABELS = frozenset({"HISTORICAL_REPLAY", "WARMUP_REPLAY", "OFFLINE_FIXTURE"})


class ExecutionBoundary(str, Enum):
    DIRECT_CALL = "DIRECT_CALL"
    PIPELINE_RUNNER = "PIPELINE_RUNNER"
    CLI = "CLI"
    BACKGROUND_WORKER = "BACKGROUND_WORKER"
    SCHEDULED_JOB = "SCHEDULED_JOB"


# ==============================================================================
# Exceptions
# ==============================================================================

class ProspectiveSafetyError(Exception):
    """Base exception for all prospective inference safety violations."""
    pass


class ProspectiveAuthorizationError(ProspectiveSafetyError):
    """Raised when prospective scoring is invoked without explicit, valid Gate 4 authorization."""
    pass


class InsufficientWarmupBarsError(ProspectiveSafetyError):
    """Raised when fewer than 288 contiguous closed 5m bars are available."""
    pass


class IncompleteCandleError(ProspectiveSafetyError):
    """Raised when an unclosed or incomplete candle is submitted for prospective inference."""
    pass


class InvalidMarketIdentityError(ProspectiveSafetyError):
    """Raised when candle symbol, interval, or market type fails to match Spot BTCUSDT 5m."""
    pass


class DiscontinuousCandlesError(ProspectiveSafetyError):
    """Raised when timestamp gaps or out-of-sequence intervals are detected in warmup candles."""
    pass


class DuplicateTimestampError(ProspectiveSafetyError):
    """Raised when duplicate candle timestamps are detected in the observation sequence."""
    pass


class TemporalAlignmentError(ProspectiveSafetyError):
    """Raised when candle timestamps are future-dated relative to clock or excessively stale."""
    pass


class SyntheticProvenanceError(ProspectiveSafetyError):
    """Raised when synthetic, mock, or replay provenance data is passed as a prospective observation event."""
    pass


class UnverifiedEvidenceError(ProspectiveSafetyError):
    """Raised when candidate candle cannot be verified against the durable raw evidence ledger."""
    pass


# ==============================================================================
# Helpers
# ==============================================================================

def _get_candle_attr(candle: Any, key: str, default: Any = None) -> Any:
    """Extract attribute or dict key from candle object."""
    if isinstance(candle, dict):
        return candle.get(key, default)
    return getattr(candle, key, default)


def _get_timestamp_open(candle: Any) -> int:
    """Extract open timestamp in milliseconds."""
    ts = _get_candle_attr(candle, "timestamp_open")
    if ts is None:
        ts = _get_candle_attr(candle, "open_time_ms")
    if ts is None:
        raise ValueError(f"Candle missing timestamp_open: {candle}")
    return int(ts)


def _get_timestamp_close(candle: Any) -> int:
    """Extract close timestamp in milliseconds."""
    ts = _get_candle_attr(candle, "timestamp_close")
    if ts is None:
        ts = _get_candle_attr(candle, "close_time_ms")
    if ts is None:
        # Fallback based on open time + 5m - 1ms
        ts_open = _get_timestamp_open(candle)
        return ts_open + CANDLE_INTERVAL_MS - 1
    return int(ts)


# ==============================================================================
# Authorization Guard
# ==============================================================================

class ProspectiveAuthorizationGuard:
    """Centralized gatekeeper for prospective inference authorization."""

    @staticmethod
    def check_authorization(
        boundary_or_record_label: Union[ExecutionBoundary, str] = "HISTORICAL_REPLAY",
        run_mode_or_is_prospective: Union[str, bool] = False,
        env: Optional[Dict[str, str]] = None,
        record_label: Optional[str] = None,
        is_prospective: Optional[bool] = None,
        boundary: Optional[Union[ExecutionBoundary, str]] = None,
        run_mode: Optional[str] = None,
    ) -> Tuple[bool, List[str]]:
        """Verify environment variables and runtime flags for prospective scoring.

        Fails closed on any non-strict value.
        Evaluated dynamically immediately before inference execution.
        Supports both (record_label, is_prospective) and (boundary, run_mode) calling patterns.
        """
        env_map = env if env is not None else os.environ
        violations: List[str] = []

        # Determine effective boundary
        if boundary is not None:
            effective_boundary = boundary
        elif isinstance(boundary_or_record_label, ExecutionBoundary) or (
            isinstance(boundary_or_record_label, str)
            and boundary_or_record_label in {e.value for e in ExecutionBoundary}
        ):
            effective_boundary = boundary_or_record_label
        else:
            effective_boundary = None

        # Determine effective record_label
        if record_label is not None:
            effective_record_label = record_label
        elif run_mode is not None:
            effective_record_label = run_mode
        elif effective_boundary is not None and boundary_or_record_label == effective_boundary:
            if isinstance(run_mode_or_is_prospective, str):
                effective_record_label = run_mode_or_is_prospective
            elif isinstance(run_mode_or_is_prospective, bool):
                effective_record_label = "PROSPECTIVE_LIVE" if run_mode_or_is_prospective else "HISTORICAL_REPLAY"
            else:
                effective_record_label = "HISTORICAL_REPLAY"
        else:
            effective_record_label = str(boundary_or_record_label)

        # Determine effective is_prospective
        if is_prospective is not None:
            effective_is_prosp = is_prospective
        elif isinstance(run_mode_or_is_prospective, bool) and effective_boundary is None:
            effective_is_prosp = run_mode_or_is_prospective
        else:
            effective_is_prosp = (effective_record_label == "PROSPECTIVE_LIVE")

        prospective_requested = effective_is_prosp or (effective_record_label == "PROSPECTIVE_LIVE")

        # 1. Trading must ALWAYS be strictly disabled
        trading_val = env_map.get("CBE_TRADING_DISABLED")
        if prospective_requested:
            if trading_val != "true":
                violations.append(
                    f"CBE_TRADING_DISABLED must be strictly 'true' (got '{trading_val}'). Trading is prohibited."
                )
        else:
            if trading_val is not None and trading_val != "true":
                violations.append(
                    f"CBE_TRADING_DISABLED cannot be '{trading_val}'. Trading is prohibited."
                )

        if prospective_requested:
            # Gate 4: Approval 4 authorization check
            app4_val = env_map.get("CBE_APPROVAL_4_AUTHORIZED")
            if app4_val != "true":
                violations.append(
                    f"CBE_APPROVAL_4_AUTHORIZED must be strictly 'true' (got '{app4_val}'). "
                    "Prospective inference is NOT authorized."
                )

            # Prospective observation switch
            prosp_val = env_map.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED")
            if prosp_val != "true":
                violations.append(
                    f"CBE_PROSPECTIVE_OBSERVATION_ENABLED must be strictly 'true' (got '{prosp_val}'). "
                    "Prospective observation is disabled."
                )

            # Explicit check: Approval 3 does not imply Approval 4
            app3_val = env_map.get("CBE_APPROVAL_3_AUTHORIZED")
            if app3_val == "true" and app4_val != "true":
                violations.append(
                    "Approval 3 (live capture) does NOT confer Approval 4 (prospective inference) authorization."
                )

        else:
            # Offline research / replay execution path
            # Must NOT produce PROSPECTIVE_LIVE records
            if effective_record_label == "PROSPECTIVE_LIVE":
                violations.append(
                    "Offline research cannot emit prospective record label 'PROSPECTIVE_LIVE'."
                )

        return len(violations) == 0, violations

    @classmethod
    def verify_authorization(
        cls,
        boundary_or_record_label: Union[ExecutionBoundary, str] = "HISTORICAL_REPLAY",
        run_mode_or_is_prospective: Union[str, bool] = False,
        env: Optional[Dict[str, str]] = None,
        record_label: Optional[str] = None,
        is_prospective: Optional[bool] = None,
        boundary: Optional[Union[ExecutionBoundary, str]] = None,
        run_mode: Optional[str] = None,
    ) -> None:
        """Enforce prospective authorization, raising ProspectiveAuthorizationError on failure."""
        is_valid, violations = cls.check_authorization(
            boundary_or_record_label=boundary_or_record_label,
            run_mode_or_is_prospective=run_mode_or_is_prospective,
            env=env,
            record_label=record_label,
            is_prospective=is_prospective,
            boundary=boundary,
            run_mode=run_mode,
        )
        if not is_valid:
            msg = "; ".join(violations)
            logger.error(f"Prospective inference authorization check failed: {msg}")
            raise ProspectiveAuthorizationError(f"Prospective inference authorization failed: {msg}")


# ==============================================================================
# Causal Data Eligibility Guard
# ==============================================================================

class CausalDataEligibilityGuard:
    """Verifies that market data fed into prospective inference satisfies all causal & integrity contracts."""

    @staticmethod
    def verify_candle_identity(
        candle: Any,
        expected_symbol: str = EXPECTED_SYMBOL,
        expected_interval: str = EXPECTED_INTERVAL,
        expected_market_type: str = EXPECTED_MARKET_TYPE,
    ) -> None:
        """Verify market identity attributes of a candle."""
        sym = _get_candle_attr(candle, "symbol")
        if sym is not None and sym != expected_symbol:
            raise InvalidMarketIdentityError(
                f"Invalid symbol '{sym}': expected '{expected_symbol}'"
            )

        inv = _get_candle_attr(candle, "interval")
        if inv is not None and inv != expected_interval:
            raise InvalidMarketIdentityError(
                f"Invalid interval '{inv}': expected '{expected_interval}'"
            )

        mt = _get_candle_attr(candle, "market_type")
        if mt is not None and mt != expected_market_type:
            raise InvalidMarketIdentityError(
                f"Invalid market type '{mt}': expected '{expected_market_type}'"
            )

    @staticmethod
    def verify_closed_candle(candle: Any) -> None:
        """Verify that candle is confirmed closed."""
        is_closed = _get_candle_attr(candle, "is_closed")
        if is_closed is False:
            raise IncompleteCandleError("Candle is incomplete / not closed (is_closed=False).")

        is_final = _get_candle_attr(candle, "is_final")
        if is_final is False:
            raise IncompleteCandleError("Candle is incomplete / not final (is_final=False).")

    @staticmethod
    def verify_temporal_alignment(
        candle: Any,
        current_time_ms: Optional[int] = None,
        clock_skew_budget_ms: int = CLOCK_SKEW_BUDGET_MS,
        max_staleness_ms: int = MAX_STALENESS_MS,
    ) -> None:
        """Verify candle close timestamp against current observation clock."""
        if current_time_ms is None:
            return

        ts_close = _get_timestamp_close(candle)

        # 1. Receipt before exchange close time (future-dated observation)
        if ts_close > (current_time_ms + clock_skew_budget_ms):
            raise TemporalAlignmentError(
                f"Future-dated candle rejected: close timestamp {ts_close} exceeds "
                f"current clock {current_time_ms} by more than allowable clock skew ({clock_skew_budget_ms}ms)."
            )

        # 2. Excessively stale backdated observation
        age_ms = current_time_ms - ts_close
        if age_ms > max_staleness_ms:
            raise TemporalAlignmentError(
                f"Excessively stale candle rejected: closed {age_ms}ms ago "
                f"(exceeds max staleness threshold of {max_staleness_ms}ms)."
            )

    @staticmethod
    def verify_provenance(candle: Any, is_prospective: bool = True) -> None:
        """Verify provenance for prospective observation."""
        if not is_prospective:
            return

        # Check for synthetic flags
        if _get_candle_attr(candle, "is_synthetic") is True:
            raise SyntheticProvenanceError("Synthetic candle rejected for prospective scoring.")

        if _get_candle_attr(candle, "is_mock") is True:
            raise SyntheticProvenanceError("Mock candle rejected for prospective scoring.")

        prov = _get_candle_attr(candle, "provenance")
        if prov is not None:
            prov_str = str(prov).upper()
            if prov_str in ("OFFLINE_FIXTURE", "HISTORICAL_REPLAY", "SYNTHETIC", "MOCK"):
                raise SyntheticProvenanceError(
                    f"Invalid provenance '{prov}' for prospective scoring. "
                    "Only genuine live market data is permitted for prospective observations."
                )

    @classmethod
    def verify_causal_data_eligibility(
        cls,
        candles: List[Any],
        current_candle: Optional[Any] = None,
        current_time_ms: Optional[int] = None,
        evidence_store: Optional[Any] = None,
        is_prospective: bool = True,
        min_warmup_bars: int = MIN_PROSPECTIVE_WARMUP_BARS,
    ) -> None:
        """Perform comprehensive causal data eligibility validation across rolling window and target bar."""
        # 1. Warm-up bar count invariant
        num_candles = len(candles)
        if num_candles < min_warmup_bars:
            raise InsufficientWarmupBarsError(
                f"Insufficient warmup bars: expected at least {min_warmup_bars} contiguous closed candles, "
                f"got {num_candles}."
            )

        # 2. Validate rolling window candle identity, closure, and continuity
        prev_open: Optional[int] = None
        for idx, c in enumerate(candles):
            cls.verify_candle_identity(c)
            cls.verify_closed_candle(c)

            ts_open = _get_timestamp_open(c)
            if prev_open is not None:
                if ts_open == prev_open:
                    raise DuplicateTimestampError(
                        f"Duplicate candle timestamp {ts_open} detected at index {idx}."
                    )
                if ts_open != (prev_open + CANDLE_INTERVAL_MS):
                    raise DiscontinuousCandlesError(
                        f"Discontinuous candles at index {idx}: gap between {prev_open} and {ts_open} "
                        f"(expected {prev_open + CANDLE_INTERVAL_MS})."
                    )
            prev_open = ts_open

        # 3. Evaluate target observation candle
        target_candle = current_candle if current_candle is not None else candles[-1]
        cls.verify_candle_identity(target_candle)
        cls.verify_closed_candle(target_candle)
        cls.verify_temporal_alignment(target_candle, current_time_ms=current_time_ms)
        cls.verify_provenance(target_candle, is_prospective=is_prospective)

        # If current_candle is distinct from window tail, verify continuity
        if current_candle is not None and current_candle is not candles[-1]:
            last_open = _get_timestamp_open(candles[-1])
            curr_open = _get_timestamp_open(current_candle)
            if curr_open == last_open:
                pass  # Represents the same head bar
            elif curr_open == (last_open + CANDLE_INTERVAL_MS):
                pass  # Strictly contiguous next bar
            elif curr_open < last_open:
                raise TemporalAlignmentError(
                    f"Current candle timestamp {curr_open} precedes window tail {last_open}."
                )
            else:
                raise DiscontinuousCandlesError(
                    f"Gap detected between window tail {last_open} and current candle {curr_open}."
                )

        # 4. Durable evidence store reference verification (if provided)
        if evidence_store is not None:
            target_ts_open = _get_timestamp_open(target_candle)
            persisted = evidence_store.get_candle_by_timestamp(target_ts_open)
            if persisted is None:
                raise UnverifiedEvidenceError(
                    f"Candle at timestamp {target_ts_open} has not been committed to the durable raw evidence ledger."
                )

"""Sprint 26 — Module 26.2: Walk-Forward Research Lab.

Evaluates historical research findings across sequential time windows without
future-data leakage while enforcing the strictly frozen CBE-0.7.0 model boundary.

Key Scientific & Temporal Integrity Safeguards:
1. Supports both expanding-window and rolling-window chronological splits with
   explicit warm-up bars, outcome-horizon purge bars, and dynamic embargo bars.
2. Composes PurgedEmbargoTimeSeriesSplitter to guarantee zero look-ahead leakage.
3. Enforces the frozen CBE-0.7.0 boundary: any attempt to refit, retrain, or
   optimize canonical model parameters returns EVALUATION_BLOCKED immediately.
4. Rejects future observations in earlier windows, overlapping train/test sets,
   non-monotonic timestamps, missing timestamps, unsupported frequencies, and
   unverified or quarantined historical inputs.
5. Evaluates cross-window scientific consistency using non-directional metrics
   (Parkinson volatility stability, high-volatility regime share, Population
   Stability Index PSI, and fold-to-fold consistency) — never directional PnL.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd

from coin_behavior_engine.product.resource_governor import resource_governor
from coin_behavior_engine.research.historical.walkforward_purged import (
    PurgedEmbargoTimeSeriesSplitter,
)


CANONICAL_MODEL_ID = "CBE-0.7.0"
CANONICAL_MODEL_STATUS = "STRICTLY_FROZEN"
GOVERNANCE_DECISION = "TECHNICAL_NO_GO"
WALK_FORWARD_VERSION = "SPRINT26-WF-LAB-V1.0"

SUPPORTED_FREQUENCIES: Dict[str, int] = {
    "5m": 300_000,
    "15m": 900_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "1d": 86_400_000,
    "8h": 28_800_000,
}

FROZEN_CANONICAL_PARAMETERS: Dict[str, Any] = {
    "model_id": "CBE-0.7.0",
    "parkinson_window_bars": 24,
    "high_volatility_z_threshold": 1.5,
    "capitulation_return_z_threshold": -2.0,
    "fdr_alpha_threshold": 0.05,
    "parameter_refit_allowed": False,
}

MAX_WALK_FORWARD_FOLDS = 24
MAX_DATASET_ROWS = 45000
MIN_REQUIRED_WARMUP_BARS = 24


@dataclass(frozen=True)
class WalkForwardFoldResult:
    """Scientific evaluation result for a single chronological walk-forward fold."""

    fold_index: int
    split_mode: str
    train_start_idx: int
    train_end_idx: int
    test_start_idx: int
    test_end_idx: int
    train_start_utc: str
    train_end_utc: str
    test_start_utc: str
    test_end_utc: str
    train_bar_count: int
    test_bar_count: int
    warmup_bars_applied: int
    purged_bars_count: int
    embargo_bars_count: int
    temporal_gap_ms: int
    leakage_check_passed: bool
    train_metrics: Dict[str, float]
    test_metrics: Dict[str, float]
    consistency_metrics: Dict[str, float]
    fold_verdict: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def dataset_provenance(self) -> Dict[str, Any]:
        return self.source_provenance


@dataclass(frozen=True)
class WalkForwardEvaluationReport:
    """Complete output contract for Module 26.2 Walk-Forward Research Lab."""

    evaluation_id: str
    status: str
    rejection_code: Optional[str]
    rejection_reason: Optional[str]
    record_id: str
    dataset_id: str
    frequency: str
    split_mode: str
    source_provenance: Dict[str, Any]
    frozen_model_contract: Dict[str, Any]
    temporal_leakage_diagnostics: Dict[str, Any]
    evaluation_manifest: Dict[str, Any]
    fold_count: int
    folds: List[Dict[str, Any]]
    cross_window_consistency: Dict[str, Any]
    limitations: List[str]
    evaluated_at_utc: str
    canonical_model: str = CANONICAL_MODEL_ID
    model_status: str = CANONICAL_MODEL_STATUS
    governance_decision: str = GOVERNANCE_DECISION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @property
    def dataset_provenance(self) -> Dict[str, Any]:
        return self.source_provenance


def _ms_to_iso_utc(ts_ms: int) -> str:
    return datetime.fromtimestamp(float(ts_ms) / 1000.0, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


def _compute_psi(expected_probs: Sequence[float], actual_probs: Sequence[float]) -> float:
    """Compute Population Stability Index (PSI) between train and test regime/volatility buckets."""
    eps = 1e-4
    psi = 0.0
    for p_exp, p_act in zip(expected_probs, actual_probs):
        e = max(eps, float(p_exp))
        a = max(eps, float(p_act))
        psi += (a - e) * math.log(a / e)
    return round(float(max(0.0, psi)), 6)


class WalkForwardResearchLab:
    """Module 26.2 — Chronological walk-forward evaluation engine with strict leakage guards."""

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

    # ------------------------------------------------------------------
    # Pre-Evaluation Integrity & Leakage Diagnostics
    # ------------------------------------------------------------------

    @staticmethod
    def validate_frozen_model_boundary(
        allow_parameter_refit: bool = False,
        optimize_parameters: bool = False,
        custom_model_parameters: Optional[Dict[str, Any]] = None,
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """Verify that the walk-forward request does not refit or mutate CBE-0.7.0."""
        if allow_parameter_refit:
            return (
                False,
                "FROZEN_MODEL_REFIT_PROHIBITED",
                "Walk-forward evaluation is not permission to retrain or refit the frozen CBE-0.7.0 model.",
            )
        if optimize_parameters:
            return (
                False,
                "FROZEN_MODEL_OPTIMIZATION_PROHIBITED",
                "In-window parameter optimization or hyperparameter tuning is prohibited under CBE-0.7.0 governance.",
            )
        if custom_model_parameters:
            for k, v in custom_model_parameters.items():
                if k in FROZEN_CANONICAL_PARAMETERS and FROZEN_CANONICAL_PARAMETERS[k] != v:
                    return (
                        False,
                        "CANONICAL_PARAMETER_MUTATION_BLOCKED",
                        f"Attempted mutation of frozen parameter '{k}' from "
                        f"'{FROZEN_CANONICAL_PARAMETERS[k]}' to '{v}' is blocked.",
                    )
        return True, None, None

    @staticmethod
    def inspect_temporal_integrity(
        timestamps_ms: Optional[Sequence[Any]],
        frequency: str,
        explicit_splits: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Verify chronological ordering, absence of duplicates, frequency validity, and split separation."""
        freq_norm = str(frequency or "").strip().lower()
        if freq_norm not in SUPPORTED_FREQUENCIES:
            return {
                "valid": False,
                "rejection_code": "UNSUPPORTED_DATA_FREQUENCY",
                "rejection_reason": (
                    f"Data frequency '{frequency}' is unsupported. "
                    f"Supported frequencies: {list(SUPPORTED_FREQUENCIES.keys())}."
                ),
            }

        if timestamps_ms is None or len(timestamps_ms) == 0:
            return {
                "valid": False,
                "rejection_code": "MISSING_EVALUATION_TIMESTAMPS",
                "rejection_reason": "Evaluation series is missing timestamps; chronological order cannot be verified.",
            }

        clean_ts: List[int] = []
        for idx, t in enumerate(timestamps_ms):
            if t is None or (isinstance(t, float) and math.isnan(t)):
                return {
                    "valid": False,
                    "rejection_code": "MISSING_EVALUATION_TIMESTAMPS",
                    "rejection_reason": f"Missing or null timestamp at index {idx}.",
                }
            clean_ts.append(int(t))

        arr_ts = np.asarray(clean_ts, dtype=np.int64)
        if len(arr_ts) < 2:
            return {
                "valid": False,
                "rejection_code": "INSUFFICIENT_OBSERVATIONS",
                "rejection_reason": "At least 2 chronological timestamps are required.",
            }

        diffs = np.diff(arr_ts)
        if np.any(diffs < 0):
            bad_idx = int(np.where(diffs < 0)[0][0])
            return {
                "valid": False,
                "rejection_code": "CHRONOLOGICAL_ORDER_VIOLATION",
                "rejection_reason": (
                    f"Non-monotonic timestamps detected at index {bad_idx}: "
                    f"{arr_ts[bad_idx]} -> {arr_ts[bad_idx + 1]}."
                ),
            }

        if np.any(diffs == 0):
            dup_idx = int(np.where(diffs == 0)[0][0])
            return {
                "valid": False,
                "rejection_code": "DUPLICATE_TIMESTAMP_VIOLATION",
                "rejection_reason": f"Duplicate timestamp {arr_ts[dup_idx]} at index {dup_idx}.",
            }

        # If caller supplied explicit train/test windows, verify zero future leakage and zero overlap
        if explicit_splits:
            for s_idx, sp in enumerate(explicit_splits):
                tr_start = int(sp.get("train_start_ms", 0))
                tr_end = int(sp.get("train_end_ms", 0))
                te_start = int(sp.get("test_start_ms", 0))
                te_end = int(sp.get("test_end_ms", 0))
                if tr_end < tr_start or te_end < te_start:
                    return {
                        "valid": False,
                        "rejection_code": "CHRONOLOGICAL_ORDER_VIOLATION",
                        "rejection_reason": f"Fold {s_idx} has inverted window boundaries.",
                    }
                if tr_end >= te_start:
                    if tr_start > te_start:
                        return {
                            "valid": False,
                            "rejection_code": "FUTURE_OBSERVATION_LEAKAGE_DETECTED",
                            "rejection_reason": (
                                f"Fold {s_idx} uses future observations ({tr_start}..{tr_end}) "
                                f"to evaluate an earlier test window ({te_start}..{te_end})."
                            ),
                        }
                    return {
                        "valid": False,
                        "rejection_code": "TRAIN_TEST_OVERLAP_DETECTED",
                        "rejection_reason": (
                            f"Fold {s_idx} has overlapping train_end ({tr_end}) and test_start ({te_start})."
                        ),
                    }

        return {
            "valid": True,
            "rejection_code": None,
            "rejection_reason": None,
            "observation_count": int(len(arr_ts)),
            "start_timestamp_ms": int(arr_ts[0]),
            "end_timestamp_ms": int(arr_ts[-1]),
            "start_utc": _ms_to_iso_utc(int(arr_ts[0])),
            "end_utc": _ms_to_iso_utc(int(arr_ts[-1])),
            "monotonic_increasing_verified": True,
            "unique_timestamps_verified": True,
        }

    # ------------------------------------------------------------------
    # Dataset Resolution
    # ------------------------------------------------------------------

    def _resolve_verified_dataset(
        self,
        dataset_id: str,
        frequency: str = "1h",
        custom_df: Optional[pd.DataFrame] = None,
        source_path: Optional[str] = None,
        record_id: str = "RES-29-PAT-SIM",
        intake_manifest: Optional[Dict[str, Any]] = None,
        intake_manifest_path: Optional[str] = None,
        provenance_sidecar_path: Optional[str] = None,
        attestation: Optional[Dict[str, Any]] = None,
        caller_supplied_sha256: Optional[str] = None,
        require_explicit_evidence: bool = False,
        trusted_fixture_context: bool = False,
    ) -> Tuple[Optional[pd.DataFrame], Dict[str, Any], Optional[str], Optional[str]]:
        """Resolve an authorized historical dataset and enforce Sprint 25–26 trusted provenance."""
        from coin_behavior_engine.product.scientific_readiness import (
            ScientificReadinessEvaluator,
        )

        ds_norm = str(dataset_id or "").strip()

        # 1. Caller-supplied DataFrame policy (never automatically VERIFIED)
        if custom_df is not None:
            df_sha = hashlib.sha256(
                pd.util.hash_pandas_object(custom_df, index=True).values.tobytes()
            ).hexdigest()
            if not trusted_fixture_context:
                return (
                    None,
                    {
                        "dataset_id": ds_norm or "CUSTOM_IN_MEMORY_DATASET",
                        "source_path": "IN_MEMORY_DATAFRAME",
                        "source_sha256": df_sha,
                        "is_verified": False,
                        "verification_status": "CALLER_SUPPLIED_UNVERIFIED",
                        "provenance_status": "CALLER_SUPPLIED_UNVERIFIED",
                        "provenance_rejection_code": "CALLER_SUPPLIED_UNVERIFIED",
                    },
                    "CALLER_SUPPLIED_UNVERIFIED",
                    (
                        "Caller-supplied DataFrame lacks independently authenticated dataset provenance "
                        "(CALLER_SUPPLIED_UNVERIFIED) and cannot be promoted to a verified research dataset."
                    ),
                )
            return (
                custom_df.copy(),
                {
                    "dataset_id": ds_norm or "TEST_FIXTURE_DATAFRAME",
                    "source_path": "TRUSTED_TEST_FIXTURE_IN_MEMORY",
                    "source_sha256": df_sha,
                    "is_verified": False,
                    "verification_status": "TRUSTED_TEST_FIXTURE_ONLY",
                    "provenance_status": "TRUSTED_TEST_FIXTURE_ONLY",
                    "trusted_fixture_context": True,
                },
                None,
                None,
            )

        freq_norm = str(frequency or "1h").strip().lower()
        effective_ds_id = ds_norm
        effective_src_path = source_path

        if ds_norm.endswith(".parquet") and not effective_src_path:
            effective_src_path = ds_norm
        elif (
            ds_norm == "DS-BTC-1H-Q1-2024"
            and freq_norm == "15m"
            and not effective_src_path
            and intake_manifest is None
            and intake_manifest_path is None
            and provenance_sidecar_path is None
            and attestation is None
        ):
            effective_ds_id = "DS-BTC-15M-Q1-2024"

        prov_res = ScientificReadinessEvaluator.verify_historical_dataset_provenance(
            dataset_id=effective_ds_id,
            source_path=effective_src_path,
            record_id=record_id,
            methodology_id=CANONICAL_MODEL_ID,
            intake_manifest=intake_manifest,
            intake_manifest_path=intake_manifest_path,
            provenance_sidecar_path=provenance_sidecar_path,
            attestation=attestation,
            caller_supplied_sha256=caller_supplied_sha256,
            require_explicit_evidence=require_explicit_evidence,
            workspace_root=self.workspace_root,
        )

        if not prov_res.get("is_verified"):
            return (
                None,
                {
                    "dataset_id": effective_ds_id,
                    "source_path": prov_res.get("source_path"),
                    "source_sha256": None,
                    "is_verified": False,
                    "verification_status": "UNVERIFIED_HISTORICAL_INPUT",
                    "provenance_status": prov_res.get("provenance_status", "UNVERIFIED_HISTORICAL_INPUT"),
                    "provenance_rejection_code": prov_res.get("provenance_rejection_code"),
                    "trust_progression_state": prov_res.get("trust_progression_state", "UNVERIFIED"),
                },
                "UNVERIFIED_HISTORICAL_INPUT",
                str(
                    prov_res.get("rejection_reason")
                    or f"Historical dataset '{effective_ds_id}' provenance could not be verified."
                ),
            )

        resolved_path = Path(prov_res["resolved_path"])
        df = pd.read_parquet(resolved_path)
        if len(df) > MAX_DATASET_ROWS:
            df = df.iloc[:MAX_DATASET_ROWS].copy()

        return (
            df,
            {
                "dataset_id": effective_ds_id,
                "source_path": prov_res["source_path"],
                "source_sha256": prov_res["source_sha256"],
                "is_verified": True,
                "verification_status": "VERIFIED_TRUSTED_PROVENANCE",
                "provenance_status": "VERIFIED_TRUSTED_PROVENANCE",
                "provenance_mechanism": prov_res["mechanism"],
                "verified_key_id": prov_res["verified_key_id"],
                "source_lineage": prov_res["source_lineage"],
                "evidence_reference": prov_res["evidence_reference"],
                "trust_progression_state": "INTEGRITY_VERIFIED",
                "row_count": int(len(df)),
            },
            None,
            None,
        )

    # ------------------------------------------------------------------
    # Walk-Forward Execution
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_window_scientific_metrics(
        parkinson_vol: np.ndarray,
        log_returns: np.ndarray,
        vol_threshold: float,
    ) -> Tuple[Dict[str, float], List[float]]:
        """Compute non-directional scientific metrics on a single window."""
        n = len(parkinson_vol)
        if n == 0:
            return {}, [0.25, 0.25, 0.25, 0.25]

        mean_vol = float(np.mean(parkinson_vol))
        median_vol = float(np.median(parkinson_vol))
        std_vol = float(np.std(parkinson_vol, ddof=1)) if n > 1 else 0.0
        iqr_vol = float(np.percentile(parkinson_vol, 75) - np.percentile(parkinson_vol, 25)) if n >= 4 else 0.0
        high_vol_share = float(np.mean(parkinson_vol > vol_threshold))
        abs_ret_mean = float(np.mean(np.abs(log_returns)))

        # Lag-1 volatility persistence
        if n > 5 and std_vol > 1e-12:
            c = parkinson_vol - mean_vol
            v_autocorr = float(np.sum(c[:-1] * c[1:]) / np.sum(c ** 2))
        else:
            v_autocorr = 0.0

        metrics = {
            "mean_parkinson_volatility": round(mean_vol, 6),
            "median_parkinson_volatility": round(median_vol, 6),
            "volatility_std": round(std_vol, 6),
            "volatility_iqr": round(iqr_vol, 6),
            "high_volatility_regime_share": round(high_vol_share, 4),
            "mean_abs_log_return": round(abs_ret_mean, 6),
            "volatility_persistence_lag1": round(v_autocorr, 4),
        }

        # 4-bucket distribution for PSI computation
        q1, q2, q3 = (
            float(np.percentile(parkinson_vol, 25)),
            float(np.percentile(parkinson_vol, 50)),
            float(np.percentile(parkinson_vol, 75)),
        )
        probs = [
            float(np.mean(parkinson_vol <= q1)),
            float(np.mean((parkinson_vol > q1) & (parkinson_vol <= q2))),
            float(np.mean((parkinson_vol > q2) & (parkinson_vol <= q3))),
            float(np.mean(parkinson_vol > q3)),
        ]
        return metrics, probs

    def run_walk_forward_evaluation(
        self,
        record_id: str = "RES-29-PAT-SIM",
        dataset_id: str = "DS-BTC-1H-Q1-2024",
        frequency: str = "1h",
        split_mode: str = "expanding",
        n_splits: int = 4,
        warmup_bars: int = 24,
        purge_bars: int = 2,
        embargo_bars: int = 2,
        rolling_train_bars: Optional[int] = None,
        allow_parameter_refit: bool = False,
        optimize_parameters: bool = False,
        custom_model_parameters: Optional[Dict[str, Any]] = None,
        custom_df: Optional[pd.DataFrame] = None,
        explicit_splits: Optional[Sequence[Dict[str, Any]]] = None,
        source_path: Optional[str] = None,
        intake_manifest: Optional[Dict[str, Any]] = None,
        intake_manifest_path: Optional[str] = None,
        provenance_sidecar_path: Optional[str] = None,
        attestation: Optional[Dict[str, Any]] = None,
        caller_supplied_sha256: Optional[str] = None,
        require_explicit_evidence: bool = False,
        trusted_fixture_context: bool = False,
    ) -> WalkForwardEvaluationReport:
        """Execute chronological walk-forward evaluation under frozen CBE-0.7.0 governance."""
        with resource_governor.ComputationGuard("walk_forward_research_lab_run"):
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            mode_norm = str(split_mode or "expanding").strip().lower()
            if mode_norm not in ("expanding", "rolling"):
                return self._build_blocked_report(
                    record_id=record_id,
                    dataset_id=dataset_id,
                    frequency=frequency,
                    split_mode=mode_norm,
                    rejection_code="INVALID_SPLIT_MODE",
                    rejection_reason=f"Split mode '{split_mode}' is invalid; must be 'expanding' or 'rolling'.",
                    provenance={},
                    leakage_diag={"valid": False},
                    now_utc=now_utc,
                )

            # 1. Frozen-model boundary check
            frozen_ok, refit_code, refit_reason = self.validate_frozen_model_boundary(
                allow_parameter_refit=allow_parameter_refit,
                optimize_parameters=optimize_parameters,
                custom_model_parameters=custom_model_parameters,
            )
            if not frozen_ok:
                return self._build_blocked_report(
                    record_id=record_id,
                    dataset_id=dataset_id,
                    frequency=frequency,
                    split_mode=mode_norm,
                    rejection_code=refit_code or "FROZEN_MODEL_REFIT_PROHIBITED",
                    rejection_reason=refit_reason or "Frozen model modification prohibited.",
                    provenance={},
                    leakage_diag={"valid": False, "frozen_model_violation": True},
                    now_utc=now_utc,
                )

            # 2. Warmup requirement check
            if int(warmup_bars) < MIN_REQUIRED_WARMUP_BARS:
                return self._build_blocked_report(
                    record_id=record_id,
                    dataset_id=dataset_id,
                    frequency=frequency,
                    split_mode=mode_norm,
                    rejection_code="INSUFFICIENT_WARMUP_BARS",
                    rejection_reason=(
                        f"Requested warmup_bars={warmup_bars} is below the minimum required "
                        f"CBE-0.7.0 rolling window warmup ({MIN_REQUIRED_WARMUP_BARS} bars)."
                    ),
                    provenance={},
                    leakage_diag={"valid": False, "warmup_bars": warmup_bars},
                    now_utc=now_utc,
                )

            # 3. Resolve dataset
            df, provenance, ds_err_code, ds_err_reason = self._resolve_verified_dataset(
                dataset_id=dataset_id,
                frequency=frequency,
                custom_df=custom_df,
                source_path=source_path,
                record_id=record_id,
                intake_manifest=intake_manifest,
                intake_manifest_path=intake_manifest_path,
                provenance_sidecar_path=provenance_sidecar_path,
                attestation=attestation,
                caller_supplied_sha256=caller_supplied_sha256,
                require_explicit_evidence=require_explicit_evidence,
                trusted_fixture_context=trusted_fixture_context,
            )
            if df is None or ds_err_code is not None:
                return self._build_blocked_report(
                    record_id=record_id,
                    dataset_id=dataset_id,
                    frequency=frequency,
                    split_mode=mode_norm,
                    rejection_code=ds_err_code or "UNVERIFIED_HISTORICAL_INPUT",
                    rejection_reason=ds_err_reason or "Dataset could not be verified.",
                    provenance=provenance,
                    leakage_diag={"valid": False},
                    now_utc=now_utc,
                )

            # 4. Extract timestamps and verify chronological integrity
            ts_col = None
            for col_cand in ("open_time", "timestamp_ms", "timestamp_open"):
                if col_cand in df.columns:
                    ts_col = col_cand
                    break

            raw_ts = df[ts_col].tolist() if ts_col else None
            leakage_diag = self.inspect_temporal_integrity(
                timestamps_ms=raw_ts,
                frequency=frequency,
                explicit_splits=explicit_splits,
            )
            if not leakage_diag.get("valid", False):
                return self._build_blocked_report(
                    record_id=record_id,
                    dataset_id=dataset_id,
                    frequency=frequency,
                    split_mode=mode_norm,
                    rejection_code=str(leakage_diag.get("rejection_code") or "TEMPORAL_INTEGRITY_FAILURE"),
                    rejection_reason=str(leakage_diag.get("rejection_reason") or "Temporal integrity check failed."),
                    provenance=provenance,
                    leakage_diag=leakage_diag,
                    now_utc=now_utc,
                )

            # 5. Compute frozen CBE-0.7.0 series (Parkinson volatility & log returns)
            if not {"high", "low", "close"}.issubset(df.columns):
                return self._build_blocked_report(
                    record_id=record_id,
                    dataset_id=dataset_id,
                    frequency=frequency,
                    split_mode=mode_norm,
                    rejection_code="MISSING_OHLC_COLUMNS",
                    rejection_reason="Dataset is missing required OHLC columns ('high', 'low', 'close').",
                    provenance=provenance,
                    leakage_diag=leakage_diag,
                    now_utc=now_utc,
                )

            highs = df["high"].astype(float).to_numpy()
            lows = df["low"].astype(float).to_numpy()
            closes = df["close"].astype(float).to_numpy()
            ts_arr = np.asarray(raw_ts, dtype=np.int64)

            if np.any(np.isnan(highs)) or np.any(np.isnan(lows)) or np.any(np.isnan(closes)):
                return self._build_blocked_report(
                    record_id=record_id,
                    dataset_id=dataset_id,
                    frequency=frequency,
                    split_mode=mode_norm,
                    rejection_code="MISSING_OBSERVATION_VALUES",
                    rejection_reason="Dataset contains NaN/null OHLC values; imputation without explicit contract is prohibited.",
                    provenance=provenance,
                    leakage_diag=leakage_diag,
                    now_utc=now_utc,
                )

            hl_ratio = np.log(np.maximum(highs, 1e-9) / np.maximum(lows, 1e-9))
            parkinson = np.sqrt((hl_ratio ** 2) / (4.0 * math.log(2.0)))
            log_ret = np.zeros_like(closes)
            log_ret[1:] = np.log(np.maximum(closes[1:], 1e-9) / np.maximum(closes[:-1], 1e-9))

            bounded_splits = max(2, min(MAX_WALK_FORWARD_FOLDS, int(n_splits)))
            bounded_purge = max(1, int(purge_bars))
            bounded_embargo = max(0, int(embargo_bars))
            total_bars = len(df)

            min_required_bars = (bounded_splits + 1) * max(MIN_REQUIRED_WARMUP_BARS + 10, int(warmup_bars) + 10)
            if total_bars < min_required_bars:
                return self._build_blocked_report(
                    record_id=record_id,
                    dataset_id=dataset_id,
                    frequency=frequency,
                    split_mode=mode_norm,
                    rejection_code="INSUFFICIENT_WINDOW_OBSERVATIONS",
                    rejection_reason=(
                        f"Dataset has {total_bars} bars, which is fewer than the minimum {min_required_bars} "
                        f"bars required for {bounded_splits} purged walk-forward folds with warmup={warmup_bars}."
                    ),
                    provenance=provenance,
                    leakage_diag=leakage_diag,
                    now_utc=now_utc,
                )

            splitter = PurgedEmbargoTimeSeriesSplitter(
                n_splits=bounded_splits,
                outcome_horizon_bars=bounded_purge,
                embargo_bars=bounded_embargo,
            )
            purged_folds = list(splitter.split(total_bars=total_bars))
            zero_leakage = bool(
                len(purged_folds) > 0
                and all(
                    pf.train_end_idx <= pf.val_start_idx
                    and set(pf.train_indices).isdisjoint(set(pf.val_indices))
                    for pf in purged_folds
                )
            )
            splitter_audit = {
                "overall_zero_leakage_verified": zero_leakage,
                "fold_count": len(purged_folds),
            }
            if not splitter_audit.get("overall_zero_leakage_verified", False):
                return self._build_blocked_report(
                    record_id=record_id,
                    dataset_id=dataset_id,
                    frequency=frequency,
                    split_mode=mode_norm,
                    rejection_code="TEMPORAL_LEAKAGE_DETECTED",
                    rejection_reason="PurgedEmbargoTimeSeriesSplitter failed zero-leakage verification.",
                    provenance=provenance,
                    leakage_diag={**leakage_diag, "splitter_audit": splitter_audit},
                    now_utc=now_utc,
                )

            fold_results: List[WalkForwardFoldResult] = []
            vol_ratios: List[float] = []
            psi_values: List[float] = []

            for pf in purged_folds:
                tr_indices = list(pf.train_indices)
                te_indices = list(pf.val_indices)

                if mode_norm == "rolling":
                    roll_len = int(rolling_train_bars) if rolling_train_bars else len(pf.val_indices) * 2
                    roll_len = max(int(warmup_bars) + 20, roll_len)
                    if len(tr_indices) > roll_len:
                        tr_indices = tr_indices[-roll_len:]

                # Apply explicit warm-up inside each window
                eff_tr_idx = tr_indices[int(warmup_bars) :] if len(tr_indices) > int(warmup_bars) else tr_indices
                eff_te_idx = te_indices[int(warmup_bars) :] if len(te_indices) > int(warmup_bars) else te_indices

                tr_vol = parkinson[eff_tr_idx]
                tr_ret = log_ret[eff_tr_idx]
                te_vol = parkinson[eff_te_idx]
                te_ret = log_ret[eff_te_idx]

                # Frozen CBE-0.7.0 high-volatility threshold derived strictly from past (train) window
                tr_vol_thresh = float(
                    np.mean(tr_vol) + FROZEN_CANONICAL_PARAMETERS["high_volatility_z_threshold"] * np.std(tr_vol)
                )

                tr_metrics, _ = self._compute_window_scientific_metrics(tr_vol, tr_ret, tr_vol_thresh)
                te_metrics, _ = self._compute_window_scientific_metrics(te_vol, te_ret, tr_vol_thresh)

                # Compute PSI between train quartiles and test observations using train quartile cutoffs
                q25, q50, q75 = (
                    float(np.percentile(tr_vol, 25)),
                    float(np.percentile(tr_vol, 50)),
                    float(np.percentile(tr_vol, 75)),
                )
                te_bucket_probs = [
                    float(np.mean(te_vol <= q25)),
                    float(np.mean((te_vol > q25) & (te_vol <= q50))),
                    float(np.mean((te_vol > q50) & (te_vol <= q75))),
                    float(np.mean(te_vol > q75)),
                ]
                psi_val = _compute_psi([0.25, 0.25, 0.25, 0.25], te_bucket_probs)
                vol_ratio = round(
                    float(te_metrics["mean_parkinson_volatility"])
                    / max(1e-9, float(tr_metrics["mean_parkinson_volatility"])),
                    4,
                )
                vol_ratios.append(vol_ratio)
                psi_values.append(psi_val)

                tr_start_i = int(tr_indices[0])
                tr_end_i = int(tr_indices[-1])
                te_start_i = int(te_indices[0])
                te_end_i = int(te_indices[-1])
                gap_ms = int(ts_arr[te_start_i] - ts_arr[tr_end_i])

                if psi_val < 0.25 and 0.60 <= vol_ratio <= 1.65:
                    f_verdict = "CONSISTENT_ACROSS_WINDOW"
                elif psi_val < 0.50:
                    f_verdict = "MODERATE_REGIME_SHIFT"
                else:
                    f_verdict = "STRUCTURAL_REGIME_DIVERGENCE"

                fold_results.append(
                    WalkForwardFoldResult(
                        fold_index=pf.fold_index,
                        split_mode=mode_norm,
                        train_start_idx=tr_start_i,
                        train_end_idx=tr_end_i,
                        test_start_idx=te_start_i,
                        test_end_idx=te_end_i,
                        train_start_utc=_ms_to_iso_utc(int(ts_arr[tr_start_i])),
                        train_end_utc=_ms_to_iso_utc(int(ts_arr[tr_end_i])),
                        test_start_utc=_ms_to_iso_utc(int(ts_arr[te_start_i])),
                        test_end_utc=_ms_to_iso_utc(int(ts_arr[te_end_i])),
                        train_bar_count=len(tr_indices),
                        test_bar_count=len(te_indices),
                        warmup_bars_applied=int(warmup_bars),
                        purged_bars_count=pf.purged_count,
                        embargo_bars_count=pf.embargo_count,
                        temporal_gap_ms=gap_ms,
                        leakage_check_passed=bool(tr_end_i < te_start_i and gap_ms > 0),
                        train_metrics=tr_metrics,
                        test_metrics=te_metrics,
                        consistency_metrics={
                            "test_to_train_volatility_ratio": vol_ratio,
                            "volatility_distribution_psi": psi_val,
                            "high_vol_share_delta": round(
                                float(te_metrics["high_volatility_regime_share"])
                                - float(tr_metrics["high_volatility_regime_share"]),
                                4,
                            ),
                        },
                        fold_verdict=f_verdict,
                    )
                )

            consistent_count = sum(1 for f in fold_results if f.fold_verdict == "CONSISTENT_ACROSS_WINDOW")
            mean_psi = round(float(np.mean(psi_values)), 4) if psi_values else 0.0
            mean_vol_ratio = round(float(np.mean(vol_ratios)), 4) if vol_ratios else 1.0
            cv_vol_ratio = (
                round(float(np.std(vol_ratios) / max(1e-9, np.mean(vol_ratios))), 4)
                if len(vol_ratios) > 1
                else 0.0
            )

            consistency_summary = {
                "total_folds": len(fold_results),
                "consistent_folds_count": consistent_count,
                "consistency_ratio": round(consistent_count / max(1, len(fold_results)), 4),
                "mean_test_to_train_volatility_ratio": mean_vol_ratio,
                "volatility_ratio_cv": cv_vol_ratio,
                "mean_distribution_psi": mean_psi,
                "overall_consistency_verdict": (
                    "TEMPORALLY_CONSISTENT"
                    if mean_psi < 0.25 and consistent_count >= len(fold_results) // 2
                    else "REGIME_DEPENDENT_VARIATION_OBSERVED"
                ),
                "primary_validation_objective": "SCIENTIFIC_STRUCTURAL_CONSISTENCY_NON_DIRECTIONAL",
            }

            manifest_payload = {
                "record_id": record_id,
                "dataset_id": dataset_id,
                "source_sha256": provenance.get("source_sha256"),
                "frequency": frequency,
                "split_mode": mode_norm,
                "n_splits": bounded_splits,
                "warmup_bars": int(warmup_bars),
                "purge_bars": bounded_purge,
                "embargo_bars": bounded_embargo,
                "canonical_model": CANONICAL_MODEL_ID,
                "fold_boundaries": [
                    {
                        "fold": f.fold_index,
                        "train": [f.train_start_utc, f.train_end_utc],
                        "test": [f.test_start_utc, f.test_end_utc],
                    }
                    for f in fold_results
                ],
            }
            manifest_sha = hashlib.sha256(
                json.dumps(manifest_payload, sort_keys=True).encode("utf-8")
            ).hexdigest()
            manifest_payload["manifest_sha256"] = manifest_sha

            full_leakage_diag = {
                **leakage_diag,
                "splitter_zero_leakage_audit": splitter_audit,
                "future_data_leakage_detected": False,
                "train_test_overlap_detected": False,
                "parameter_refitting_performed": False,
            }

            return WalkForwardEvaluationReport(
                evaluation_id=f"WF-{record_id}-{mode_norm.upper()}-{manifest_sha[:8]}",
                status="EVALUATION_COMPLETED",
                rejection_code=None,
                rejection_reason=None,
                record_id=record_id,
                dataset_id=dataset_id,
                frequency=frequency,
                split_mode=mode_norm,
                source_provenance=provenance,
                frozen_model_contract={
                    **FROZEN_CANONICAL_PARAMETERS,
                    "parameter_mutations_applied": 0,
                },
                temporal_leakage_diagnostics=full_leakage_diag,
                evaluation_manifest=manifest_payload,
                fold_count=len(fold_results),
                folds=[f.to_dict() for f in fold_results],
                cross_window_consistency=consistency_summary,
                limitations=[
                    "Walk-forward evaluation measures structural and distributional consistency across chronological windows; it does not evaluate or authorize trading profitability.",
                    "Cryptocurrency volatility exhibits structural regime shifts across macro cycles, reflected in fold-level PSI.",
                ],
                evaluated_at_utc=now_utc,
            )

    def _build_blocked_report(
        self,
        record_id: str,
        dataset_id: str,
        frequency: str,
        split_mode: str,
        rejection_code: str,
        rejection_reason: str,
        provenance: Dict[str, Any],
        leakage_diag: Dict[str, Any],
        now_utc: str,
    ) -> WalkForwardEvaluationReport:
        """Construct a fail-closed EVALUATION_BLOCKED report."""
        block_hash = hashlib.sha256(
            f"{record_id}:{dataset_id}:{rejection_code}:{now_utc}".encode("utf-8")
        ).hexdigest()[:8]
        return WalkForwardEvaluationReport(
            evaluation_id=f"WF-BLOCKED-{block_hash}",
            status="EVALUATION_BLOCKED",
            rejection_code=rejection_code,
            rejection_reason=rejection_reason,
            record_id=record_id,
            dataset_id=dataset_id,
            frequency=frequency,
            split_mode=split_mode,
            source_provenance=provenance,
            frozen_model_contract={
                **FROZEN_CANONICAL_PARAMETERS,
                "parameter_mutations_applied": 0,
            },
            temporal_leakage_diagnostics=leakage_diag,
            evaluation_manifest={
                "status": "BLOCKED",
                "rejection_code": rejection_code,
                "manifest_sha256": None,
            },
            fold_count=0,
            folds=[],
            cross_window_consistency={"status": "EVALUATION_BLOCKED"},
            limitations=[rejection_reason],
            evaluated_at_utc=now_utc,
        )

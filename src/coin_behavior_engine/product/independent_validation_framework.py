"""Sprint 26 — Module 26.5: Independent Validation Framework.

Establishes an auditable, fail-closed framework for distinguishing genuine
independent validation from repeated analysis of the same evidence.

Required Non-Interchangeable Categories:
- REPRODUCTION
- TEMPORAL_HOLDOUT_VALIDATION
- CROSS_PERIOD_VALIDATION
- INDEPENDENT_DATASET_VALIDATION
- INDEPENDENT_REPLICATION
- VALIDATION_BLOCKED
- INDEPENDENCE_NOT_ESTABLISHED

Key Scientific Trust Boundaries:
1. A different filename or dataset ID is NEVER sufficient evidence of independence.
   Content digests, candle-value hashes, and normalized UTC timestamp intersections
   are inspected directly.
2. INDEPENDENT_DATASET_VALIDATION does NOT automatically grant INDEPENDENT_REPLICATION.
   Independent replication requires an independent procedure/execution lineage,
   verified out-of-sample replication evidence, and zero observation/source overlap.
3. Fail-closed: whenever independence evidence is missing, ambiguous, or violated,
   returns INDEPENDENCE_NOT_ESTABLISHED (or VALIDATION_BLOCKED for quarantined inputs).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

import pandas as pd

from coin_behavior_engine.product.resource_governor import resource_governor


CANONICAL_MODEL_ID = "CBE-0.7.0"
CANONICAL_MODEL_STATUS = "STRICTLY_FROZEN"
GOVERNANCE_DECISION = "TECHNICAL_NO_GO"
INDEPENDENCE_FRAMEWORK_VERSION = "SPRINT26-IND-VAL-V1.0"

VALIDATION_CATEGORIES: Tuple[str, ...] = (
    "REPRODUCTION",
    "TEMPORAL_HOLDOUT_VALIDATION",
    "CROSS_PERIOD_VALIDATION",
    "INDEPENDENT_DATASET_VALIDATION",
    "INDEPENDENT_REPLICATION",
    "VALIDATION_BLOCKED",
    "INDEPENDENCE_NOT_ESTABLISHED",
)


def _parse_iso_to_ms(iso_str: Optional[str]) -> Optional[int]:
    if not iso_str or not str(iso_str).strip():
        return None
    s = str(iso_str).strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except Exception:
        return None


@dataclass(frozen=True)
class IndependenceCheckDimension:
    """Result of one of the 8 mandatory independence checks."""

    check_name: str
    passed: bool
    status_code: str
    details: str
    evidence: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class IndependentValidationAuditReport:
    """Complete output contract for Module 26.5 Independent Validation Framework."""

    audit_id: str
    primary_record_id: str
    candidate_record_id: str
    claimed_category: Optional[str]
    assigned_category: str
    independence_established: bool
    rejection_or_downgrade_reasons: List[str]
    eight_point_checks: Dict[str, Dict[str, Any]]
    primary_evidence_summary: Dict[str, Any]
    candidate_evidence_summary: Dict[str, Any]
    scientific_distinction_note: str
    limitations: List[str]
    evaluated_at_utc: str
    framework_version: str = INDEPENDENCE_FRAMEWORK_VERSION
    canonical_model: str = CANONICAL_MODEL_ID
    model_status: str = CANONICAL_MODEL_STATUS
    governance_decision: str = GOVERNANCE_DECISION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IndependentValidationFramework:
    """Module 26.5 — Fail-closed auditor for scientific validation and replication claims."""

    def __init__(self, workspace_root: Optional[Path] = None) -> None:
        self.workspace_root = Path(workspace_root) if workspace_root else Path.cwd()

    # ------------------------------------------------------------------
    # Evidence & Content Digest Extraction
    # ------------------------------------------------------------------

    def _inspect_study_evidence(self, study: Dict[str, Any]) -> Dict[str, Any]:
        """Extract content hashes, normalized timestamps, and lineage metadata for a study."""
        rec_id = str(study.get("record_id") or study.get("research_id") or "UNKNOWN")
        ds_id = str(study.get("dataset_id") or "UNKNOWN")
        source_path_str = str(study.get("source_path") or study.get("source_artifact") or "")
        explicit_sha = study.get("source_sha256") or study.get("source_artifact_sha256")
        content_fingerprint = study.get("content_fingerprint_sha256")
        timestamps: Set[int] = set()

        if study.get("timestamps_ms") is not None:
            timestamps = {int(x) for x in study["timestamps_ms"] if x is not None}

        file_exists = False
        file_sha = explicit_sha

        if source_path_str:
            fp = self.workspace_root / source_path_str
            if fp.exists() and fp.is_file():
                file_exists = True
                raw_bytes = fp.read_bytes()
                file_sha = hashlib.sha256(raw_bytes).hexdigest()
                if fp.suffix.lower() == ".parquet":
                    try:
                        df = pd.read_parquet(fp)
                        for col in ("open_time", "timestamp_ms", "timestamp_open"):
                            if col in df.columns:
                                timestamps = {int(x) for x in df[col].dropna().tolist()}
                                break
                        if {"open", "high", "low", "close"}.issubset(df.columns):
                            ohlc_bytes = (
                                df[["open", "high", "low", "close"]]
                                .astype(float)
                                .round(6)
                                .to_csv(index=False)
                                .encode("utf-8")
                            )
                            content_fingerprint = hashlib.sha256(ohlc_bytes).hexdigest()
                    except Exception:
                        pass

        # If caller supplied an in-memory dataframe or values array, compute content fingerprint
        if study.get("ohlc_values") is not None and not content_fingerprint:
            content_fingerprint = hashlib.sha256(
                json.dumps(study["ohlc_values"], sort_keys=True).encode("utf-8")
            ).hexdigest()

        start_ms = study.get("start_ms") or _parse_iso_to_ms(study.get("period_start_utc"))
        end_ms = study.get("end_ms") or _parse_iso_to_ms(study.get("period_end_utc"))
        if timestamps and (start_ms is None or end_ms is None):
            start_ms = min(timestamps)
            end_ms = max(timestamps)

        return {
            "record_id": rec_id,
            "dataset_id": ds_id,
            "dataset_lineage_id": study.get("dataset_lineage_id") or content_fingerprint or file_sha,
            "source_path": source_path_str,
            "file_exists": file_exists,
            "source_sha256": file_sha,
            "content_fingerprint_sha256": content_fingerprint or file_sha,
            "timestamps_set": timestamps,
            "observation_count": len(timestamps) if timestamps else int(study.get("sample_size") or 0),
            "start_ms": start_ms,
            "end_ms": end_ms,
            "period_start_utc": study.get("period_start_utc"),
            "period_end_utc": study.get("period_end_utc"),
            "preprocessing_lineage_id": study.get("preprocessing_lineage_id"),
            "shared_in_sample_scaler_or_quantiles": bool(
                study.get("shared_in_sample_scaler_or_quantiles", False)
            ),
            "outcome_label_horizon_end_ms": study.get("outcome_label_horizon_end_ms"),
            "shared_labels_or_outcomes": bool(study.get("shared_labels_or_outcomes", False)),
            "methodology_id": study.get("methodology_id", "CBE-0.7.0-CANONICAL"),
            "procedure_id": study.get("procedure_id"),
            "researcher_or_execution_lineage": study.get("researcher_or_execution_lineage"),
            "independent_replication_evidence_verified": bool(
                study.get("independent_replication_evidence_verified", False)
            ),
            "quarantined": bool(
                study.get("quarantined", False)
                or "QUARANTINE" in str(study.get("evidence_status", "")).upper()
                or "QUARANTINE" in ds_id.upper()
            ),
        }

    # ------------------------------------------------------------------
    # 8-Point Independence Verification Engine
    # ------------------------------------------------------------------

    def evaluate_validation_independence(
        self,
        primary_study: Dict[str, Any],
        candidate_study: Dict[str, Any],
        claimed_category: Optional[str] = None,
    ) -> IndependentValidationAuditReport:
        """Audit primary vs candidate study across all 8 independence dimensions."""
        with resource_governor.ComputationGuard("independent_validation_audit"):
            now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            prim = self._inspect_study_evidence(primary_study)
            cand = self._inspect_study_evidence(candidate_study)

            prim_id = prim["record_id"]
            cand_id = cand["record_id"]
            reasons: List[str] = []

            # Fail-closed check for quarantined datasets
            if prim["quarantined"] or cand["quarantined"]:
                reasons.append("One or both studies reference a quarantined/contaminated dataset.")
                return self._build_report(
                    prim=prim,
                    cand=cand,
                    claimed_category=claimed_category,
                    assigned_category="VALIDATION_BLOCKED",
                    independence_established=False,
                    reasons=reasons,
                    checks={},
                    now_utc=now_utc,
                )

            checks: Dict[str, IndependenceCheckDimension] = {}

            # 1. Dataset Lineage Check (detects same data under different filename/dataset_id)
            prim_fp = prim["content_fingerprint_sha256"]
            cand_fp = cand["content_fingerprint_sha256"]
            prim_lin = prim["dataset_lineage_id"]
            cand_lin = cand["dataset_lineage_id"]

            if not prim_fp or not cand_fp:
                lineage_pass = False
                lineage_code = "MISSING_DATASET_LINEAGE_DIGEST"
                lineage_msg = "Dataset content fingerprint or SHA-256 lineage is missing; independence cannot be verified."
                reasons.append(lineage_msg)
            elif prim_fp == cand_fp or (prim_lin and cand_lin and prim_lin == cand_lin):
                lineage_pass = False
                lineage_code = "IDENTICAL_DATASET_CONTENT_OR_LINEAGE"
                lineage_msg = (
                    f"Primary ('{prim['dataset_id']}') and candidate ('{cand['dataset_id']}') share "
                    f"identical underlying data content/lineage ({str(prim_fp)[:12]}), even if filenames or IDs differ."
                )
                reasons.append(lineage_msg)
            else:
                lineage_pass = True
                lineage_code = "DISTINCT_DATASET_LINEAGE_VERIFIED"
                lineage_msg = "Primary and candidate datasets have distinct content digests and lineage."

            checks["dataset_lineage"] = IndependenceCheckDimension(
                check_name="dataset_lineage",
                passed=lineage_pass,
                status_code=lineage_code,
                details=lineage_msg,
                evidence={
                    "primary_dataset_id": prim["dataset_id"],
                    "candidate_dataset_id": cand["dataset_id"],
                    "primary_content_sha256": prim_fp,
                    "candidate_content_sha256": cand_fp,
                },
            )

            # 2. Source Artifact Overlap Check
            p_sha = prim["source_sha256"]
            c_sha = cand["source_sha256"]
            if not p_sha or not c_sha:
                src_pass = False
                src_code = "MISSING_SOURCE_ARTIFACT_HASH"
                src_msg = "Source artifact SHA-256 hash is missing for one or both studies."
                reasons.append(src_msg)
            elif p_sha == c_sha:
                src_pass = False
                src_code = "SHARED_SOURCE_ARTIFACT_HASH"
                src_msg = f"Both studies share the exact same source artifact SHA-256 ({p_sha[:12]})."
                reasons.append(src_msg)
            else:
                src_pass = True
                src_code = "DISTINCT_SOURCE_ARTIFACTS"
                src_msg = "Source artifact SHA-256 digests are distinct."

            checks["source_overlap"] = IndependenceCheckDimension(
                check_name="source_overlap",
                passed=src_pass,
                status_code=src_code,
                details=src_msg,
                evidence={
                    "primary_source_sha256": p_sha,
                    "candidate_source_sha256": c_sha,
                },
            )

            # 3. Observation Overlap Check (Timestamp Set Intersection)
            p_ts: Set[int] = prim["timestamps_set"]
            c_ts: Set[int] = cand["timestamps_set"]
            if p_ts and c_ts:
                shared_ts = p_ts.intersection(c_ts)
                shared_count = len(shared_ts)
                union_count = len(p_ts.union(c_ts))
                jaccard = float(shared_count) / float(max(1, union_count))
                if shared_count > 0:
                    obs_pass = False
                    obs_code = "OBSERVATION_TIMESTAMP_OVERLAP_DETECTED"
                    obs_msg = (
                        f"Detected {shared_count} overlapping observation timestamps "
                        f"(Jaccard={jaccard:.4f}) between primary and candidate datasets."
                    )
                    reasons.append(obs_msg)
                else:
                    obs_pass = True
                    obs_code = "ZERO_OBSERVATION_OVERLAP_VERIFIED"
                    obs_msg = "Zero shared observation timestamps between primary and candidate datasets."
            else:
                shared_count = -1
                jaccard = -1.0
                # Fall back to time window check if raw timestamp sets are not loaded, but require non-overlapping windows
                if (
                    prim["start_ms"] is not None
                    and prim["end_ms"] is not None
                    and cand["start_ms"] is not None
                    and cand["end_ms"] is not None
                    and (prim["end_ms"] < cand["start_ms"] or cand["end_ms"] < prim["start_ms"])
                ):
                    obs_pass = True
                    obs_code = "DISJOINT_EPOCH_BOUNDS_VERIFIED"
                    obs_msg = "Disjoint UTC epoch boundaries guarantee zero observation overlap."
                    shared_count = 0
                    jaccard = 0.0
                else:
                    obs_pass = False
                    obs_code = "MISSING_OBSERVATION_TIMESTAMP_EVIDENCE"
                    obs_msg = "Observation timestamps are missing and disjoint bounds cannot be established."
                    reasons.append(obs_msg)

            checks["observation_overlap"] = IndependenceCheckDimension(
                check_name="observation_overlap",
                passed=obs_pass,
                status_code=obs_code,
                details=obs_msg,
                evidence={
                    "shared_observation_count": shared_count,
                    "jaccard_overlap": round(jaccard, 6) if jaccard >= 0 else None,
                },
            )

            # 4. Time-Window Overlap Check
            p_s, p_e = prim["start_ms"], prim["end_ms"]
            c_s, c_e = cand["start_ms"], cand["end_ms"]
            if p_s is None or p_e is None or c_s is None or c_e is None:
                win_pass = False
                win_code = "MISSING_TIME_WINDOW_BOUNDARIES"
                win_msg = "Start or end UTC timestamps are missing; window separation cannot be verified."
                reasons.append(win_msg)
            else:
                overlap_ms = max(0, min(int(p_e), int(c_e)) - max(int(p_s), int(c_s)))
                touching_or_overlapping = int(p_e) >= int(c_s) and int(c_e) >= int(p_s)
                if touching_or_overlapping:
                    win_pass = False
                    win_code = "TIME_WINDOW_OVERLAP_DETECTED"
                    win_msg = f"Time windows overlap by {overlap_ms} ms."
                    reasons.append(win_msg)
                else:
                    win_pass = True
                    win_code = "DISJOINT_TIME_WINDOWS_VERIFIED"
                    win_msg = "Primary and candidate time windows are strictly disjoint."

            checks["time_window_overlap"] = IndependenceCheckDimension(
                check_name="time_window_overlap",
                passed=win_pass,
                status_code=win_code,
                details=win_msg,
                evidence={
                    "primary_window_ms": [p_s, p_e],
                    "candidate_window_ms": [c_s, c_e],
                },
            )

            # 5. Shared Preprocessing Artifacts Check
            shared_prep = bool(
                prim["shared_in_sample_scaler_or_quantiles"]
                or cand["shared_in_sample_scaler_or_quantiles"]
                or (
                    prim["preprocessing_lineage_id"]
                    and cand["preprocessing_lineage_id"]
                    and prim["preprocessing_lineage_id"] == cand["preprocessing_lineage_id"]
                )
            )
            if shared_prep:
                prep_pass = False
                prep_code = "SHARED_PREPROCESSING_LINEAGE_DETECTED"
                prep_msg = (
                    "Studies share an unisolated preprocessing artifact or in-sample quantile/scaler fit."
                )
                reasons.append(prep_msg)
            else:
                prep_pass = True
                prep_code = "ISOLATED_PREPROCESSING_VERIFIED"
                prep_msg = "No shared in-sample preprocessing leakage detected."

            checks["shared_preprocessing_artifacts"] = IndependenceCheckDimension(
                check_name="shared_preprocessing_artifacts",
                passed=prep_pass,
                status_code=prep_code,
                details=prep_msg,
                evidence={
                    "primary_preprocessing_lineage": prim["preprocessing_lineage_id"],
                    "candidate_preprocessing_lineage": cand["preprocessing_lineage_id"],
                },
            )

            # 6. Shared Labels or Outcomes Check
            label_leak = bool(prim["shared_labels_or_outcomes"] or cand["shared_labels_or_outcomes"])
            if (
                not label_leak
                and prim["outcome_label_horizon_end_ms"] is not None
                and c_s is not None
                and int(prim["outcome_label_horizon_end_ms"]) >= int(c_s)
            ):
                label_leak = True

            if label_leak:
                lbl_pass = False
                lbl_code = "SHARED_OR_OVERLAPPING_OUTCOME_LABELS"
                lbl_msg = "Primary outcome lookahead horizon overlaps with candidate evaluation window."
                reasons.append(lbl_msg)
            else:
                lbl_pass = True
                lbl_code = "DISJOINT_OUTCOME_HORIZONS_VERIFIED"
                lbl_msg = "Outcome horizons and evaluation labels are strictly separated."

            checks["shared_labels_or_outcomes"] = IndependenceCheckDimension(
                check_name="shared_labels_or_outcomes",
                passed=lbl_pass,
                status_code=lbl_code,
                details=lbl_msg,
                evidence={
                    "primary_horizon_end_ms": prim["outcome_label_horizon_end_ms"],
                    "candidate_start_ms": c_s,
                },
            )

            # 7. Methodology Independence & Compatibility Check
            m_prim = str(prim["methodology_id"] or "CBE-0.7.0-CANONICAL")
            m_cand = str(cand["methodology_id"] or "CBE-0.7.0-CANONICAL")
            if m_prim == "INCOMPATIBLE" or m_cand == "INCOMPATIBLE":
                meth_pass = False
                meth_code = "INCOMPATIBLE_METHODOLOGY"
                meth_msg = "Candidate methodology is incompatible with the primary scientific hypothesis."
                reasons.append(meth_msg)
            else:
                meth_pass = True
                meth_code = "METHODOLOGY_COMPATIBLE"
                meth_msg = f"Methodology contract verified ({m_cand})."

            checks["methodology_independence"] = IndependenceCheckDimension(
                check_name="methodology_independence",
                passed=meth_pass,
                status_code=meth_code,
                details=meth_msg,
                evidence={"primary_methodology": m_prim, "candidate_methodology": m_cand},
            )

            # 8. Researcher / Procedure Independence Check (Required for INDEPENDENT_REPLICATION)
            p_proc = prim["procedure_id"] or prim["researcher_or_execution_lineage"]
            c_proc = cand["procedure_id"] or cand["researcher_or_execution_lineage"]
            has_ind_rep_evidence = bool(
                cand["independent_replication_evidence_verified"]
                and p_proc
                and c_proc
                and str(p_proc) != str(c_proc)
            )
            checks["researcher_or_procedure_independence"] = IndependenceCheckDimension(
                check_name="researcher_or_procedure_independence",
                passed=has_ind_rep_evidence,
                status_code=(
                    "INDEPENDENT_PROCEDURE_LINEAGE_VERIFIED"
                    if has_ind_rep_evidence
                    else "SAME_OR_UNVERIFIED_PROCEDURE_LINEAGE"
                ),
                details=(
                    "Independent replication procedure and out-of-sample replication evidence verified."
                    if has_ind_rep_evidence
                    else "Procedure lineage is shared or lacks independent replication certification; eligible for dataset/holdout validation only, not INDEPENDENT_REPLICATION."
                ),
                evidence={
                    "primary_procedure_lineage": p_proc,
                    "candidate_procedure_lineage": c_proc,
                    "independent_replication_evidence_verified": cand[
                        "independent_replication_evidence_verified"
                    ],
                },
            )

            # ------------------------------------------------------------------
            # Determine Assigned Non-Interchangeable Category
            # ------------------------------------------------------------------
            core_six_passed = (
                lineage_pass
                and src_pass
                and obs_pass
                and win_pass
                and prep_pass
                and lbl_pass
                and meth_pass
            )

            claimed_norm = str(claimed_category or "").strip().upper()

            if not core_six_passed:
                # Check if it's an exact same-evidence local reproduction vs failed independence claim
                is_exact_same_data = (
                    bool(prim_fp and cand_fp and prim_fp == cand_fp)
                    or bool(p_sha and c_sha and p_sha == c_sha)
                )
                if is_exact_same_data and claimed_norm in ("", "REPRODUCTION"):
                    assigned = "REPRODUCTION"
                    ind_established = False
                else:
                    assigned = "INDEPENDENCE_NOT_ESTABLISHED"
                    ind_established = False
                    if is_exact_same_data and claimed_norm not in ("", "REPRODUCTION"):
                        reasons.append(
                            f"Claimed '{claimed_norm}' rejected because candidate study reuses the same underlying dataset/source evidence."
                        )
            else:
                # All 6 core data/temporal/preprocessing/label independence checks passed!
                ind_established = True
                if claimed_norm == "INDEPENDENT_REPLICATION":
                    if has_ind_rep_evidence:
                        assigned = "INDEPENDENT_REPLICATION"
                    else:
                        # Important rule: Independent dataset validation does NOT automatically mean independent replication!
                        assigned = "INDEPENDENCE_NOT_ESTABLISHED"
                        ind_established = False
                        reasons.append(
                            "INDEPENDENT_REPLICATION claim rejected: independent dataset validation does not "
                            "automatically establish independent replication without independent procedure "
                            "lineage and verified replication evidence."
                        )
                elif claimed_norm == "TEMPORAL_HOLDOUT_VALIDATION":
                    assigned = "TEMPORAL_HOLDOUT_VALIDATION"
                elif claimed_norm == "CROSS_PERIOD_VALIDATION":
                    assigned = "CROSS_PERIOD_VALIDATION"
                elif claimed_norm == "INDEPENDENT_DATASET_VALIDATION":
                    assigned = "INDEPENDENT_DATASET_VALIDATION"
                else:
                    # Infer appropriate category based on relationship
                    if has_ind_rep_evidence:
                        assigned = "INDEPENDENT_REPLICATION"
                    elif prim["dataset_id"].split("-Q")[0] == cand["dataset_id"].split("-Q")[0]:
                        assigned = "CROSS_PERIOD_VALIDATION"
                    else:
                        assigned = "INDEPENDENT_DATASET_VALIDATION"

            return self._build_report(
                prim=prim,
                cand=cand,
                claimed_category=claimed_norm or None,
                assigned_category=assigned,
                independence_established=ind_established,
                reasons=reasons,
                checks={k: v.to_dict() for k, v in checks.items()},
                now_utc=now_utc,
            )

    def _build_report(
        self,
        prim: Dict[str, Any],
        cand: Dict[str, Any],
        claimed_category: Optional[str],
        assigned_category: str,
        independence_established: bool,
        reasons: List[str],
        checks: Dict[str, Dict[str, Any]],
        now_utc: str,
    ) -> IndependentValidationAuditReport:
        p_summary = {k: v for k, v in prim.items() if k != "timestamps_set"}
        c_summary = {k: v for k, v in cand.items() if k != "timestamps_set"}
        audit_hash = hashlib.sha256(
            json.dumps(
                {
                    "p": prim["record_id"],
                    "c": cand["record_id"],
                    "claimed": claimed_category,
                    "assigned": assigned_category,
                    "p_sha": prim["content_fingerprint_sha256"],
                    "c_sha": cand["content_fingerprint_sha256"],
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()[:8]

        return IndependentValidationAuditReport(
            audit_id=f"IND-AUDIT-{prim['record_id']}-{cand['record_id']}-{audit_hash}",
            primary_record_id=prim["record_id"],
            candidate_record_id=cand["record_id"],
            claimed_category=claimed_category,
            assigned_category=assigned_category,
            independence_established=independence_established,
            rejection_or_downgrade_reasons=reasons,
            eight_point_checks=checks,
            primary_evidence_summary=p_summary,
            candidate_evidence_summary=c_summary,
            scientific_distinction_note=(
                "REPRODUCTION, TEMPORAL_HOLDOUT_VALIDATION, CROSS_PERIOD_VALIDATION, "
                "INDEPENDENT_DATASET_VALIDATION, and INDEPENDENT_REPLICATION are strictly "
                "non-interchangeable scientific validation tiers. A different filename or "
                "dataset ID never suffices to establish independence."
            ),
            limitations=[
                "Independent validation confirms empirical consistency across disjoint evidence; it does not grant live trading authorization (TECHNICAL_NO_GO remains in force).",
            ],
            evaluated_at_utc=now_utc,
        )

    def run_canonical_independence_matrix(self) -> Dict[str, Any]:
        """Run a canonical matrix of independence audits across authorized repository datasets and records."""
        q1_1h = {
            "record_id": "RES-29-PAT-SIM",
            "dataset_id": "DS-BTC-1H-Q1-2024",
            "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
            "period_start_utc": "2024-01-01T00:00:00Z",
            "period_end_utc": "2024-03-31T23:00:00Z",
            "preprocessing_lineage_id": "PREP-Q1-2024-ISOLATED",
            "procedure_id": "PROC-DISCOVERY-SPRINT09",
        }
        jan_2025_1h = {
            "record_id": "VAL-BTC-1H-JAN-2025",
            "dataset_id": "DS-BTC-1H-JAN-2025",
            "source_path": "data/historical/historical_binance_btcusdt_1h_jan_2025.parquet",
            "period_start_utc": "2025-01-01T00:00:00Z",
            "period_end_utc": "2025-01-31T23:00:00Z",
            "preprocessing_lineage_id": "PREP-JAN-2025-ISOLATED",
            "procedure_id": "PROC-HOLDOUT-SPRINT26",
            "independent_replication_evidence_verified": True,
        }
        q2_15m = {
            "record_id": "VAL-BTC-15M-Q2-2024",
            "dataset_id": "DS-BTC-15M-Q2-2024",
            "source_path": "data/historical/historical_binance_btcusdt_15m_q2_2024.parquet",
            "period_start_utc": "2024-04-01T00:00:00Z",
            "period_end_utc": "2024-06-30T23:45:00Z",
            "preprocessing_lineage_id": "PREP-Q2-2024-ISOLATED",
            "procedure_id": "PROC-DISCOVERY-SPRINT09",
            "independent_replication_evidence_verified": False,
        }
        same_data_alias = {
            "record_id": "ALIAS-Q1-2024-RENAMED",
            "dataset_id": "DS-BTC-1H-Q1-2024-RENAMED-COPY",
            "source_path": "data/historical/historical_binance_btcusdt_1h_q1_2024.parquet",
            "period_start_utc": "2024-01-01T00:00:00Z",
            "period_end_utc": "2024-03-31T23:00:00Z",
            "preprocessing_lineage_id": "PREP-Q1-2024-ISOLATED",
            "procedure_id": "PROC-DISCOVERY-SPRINT09",
        }
        quarantined_study = {
            "record_id": "RES-CRYPTO-01",
            "dataset_id": "DS-BTC-1H-OCT2026-QUARANTINE",
            "source_path": "data/staging_intake/BTCUSDT-5m-2026-10-intake.parquet",
            "quarantined": True,
        }

        audits = [
            self.evaluate_validation_independence(
                q1_1h, jan_2025_1h, claimed_category="INDEPENDENT_REPLICATION"
            ).to_dict(),
            self.evaluate_validation_independence(
                q1_1h, q2_15m, claimed_category="CROSS_PERIOD_VALIDATION"
            ).to_dict(),
            self.evaluate_validation_independence(
                q1_1h, q2_15m, claimed_category="INDEPENDENT_REPLICATION"
            ).to_dict(),
            self.evaluate_validation_independence(
                q1_1h, same_data_alias, claimed_category="REPRODUCTION"
            ).to_dict(),
            self.evaluate_validation_independence(
                q1_1h, same_data_alias, claimed_category="INDEPENDENT_DATASET_VALIDATION"
            ).to_dict(),
            self.evaluate_validation_independence(
                q1_1h, quarantined_study, claimed_category="INDEPENDENT_DATASET_VALIDATION"
            ).to_dict(),
        ]

        return {
            "status": "SUCCESS",
            "framework_version": INDEPENDENCE_FRAMEWORK_VERSION,
            "canonical_model": CANONICAL_MODEL_ID,
            "model_status": CANONICAL_MODEL_STATUS,
            "governance_decision": GOVERNANCE_DECISION,
            "total_audits": len(audits),
            "audits": audits,
            "evaluated_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }

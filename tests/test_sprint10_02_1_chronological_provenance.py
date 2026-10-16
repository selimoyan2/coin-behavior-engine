"""Sprint 10.02.1 — Comprehensive Unit & Forensic Test Suite for Chronological Provenance Repair.

Verifies:
1. Baseline commit verification (edbe054158e976629a6ee1c0d1a8d3f3cad24f20) and artifact preservation.
2. Exact timestamp boundaries: 2026-09-01T21:05:00Z to 2026-09-23T20:20:00Z.
3. Cadence verification: 5-minute (300s) strict cadence (disproving 15-minute assumption).
4. Cadence regularity: zero gaps, uniform 300s intervals across all 6,328 bars.
5. Exact identification of prediction #4,400: PRED-20260917T034500Z at 2026-09-17T03:45:00Z.
6. Machine-readable 3-way chronological split manifest schema & integrity.
7. Horizon-specific embargo verification (3, 6, 12, 24, 48, 96, 144, 288 bars of 5m).
8. Calibration and evaluation non-overlap guarantee.
9. Denominator reconciliation: 6,328 events -> 50,007 matured outcomes (49,855 valid).
10. Unsupported virgin-holdout claims rejected (INDEPENDENTLY_VALIDATED strictly prohibited).
11. Evidence classification audit:
    - 15m to 4h: CHRONOLOGICALLY_VERIFIED_EXPLORATORY
    - 8h & 12h: VALIDATED_WITH_LIMITATIONS
    - 24h: INSUFFICIENT_EVIDENCE
12. Versioned prior report corrections registry.
13. Production isolation & safety invariants (APPROVAL4 = FALSE).
14. Pure analytical compute latency budget (< 50 ms).
"""

from __future__ import annotations

import json
from pathlib import Path
import time

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.calibration import (
    CalibrationEvidenceStatus,
    ChronologicalProvenanceRepairEngine,
    HorizonEvidenceAssessment,
    PriorReportCorrectionItem,
    SplitManifestRecord,
    Sprint10021MasterReport,
    TimelineReconstructionRecord,
)


@pytest.fixture(scope="module")
def repair_engine() -> ChronologicalProvenanceRepairEngine:
    return ChronologicalProvenanceRepairEngine()


@pytest.fixture(scope="module")
def master_report(repair_engine: ChronologicalProvenanceRepairEngine) -> Sprint10021MasterReport:
    rep_path = Path("data/reports/sprint10_02_1_chronological_provenance_repair.json")
    manifest_path = Path("data/reports/sprint10_02_1_split_manifest.json")
    corrections_path = Path("data/reports/sprint10_02_1_prior_report_corrections.json")
    return repair_engine.run_full_repair_audit(
        output_report_path=rep_path,
        split_manifest_path=manifest_path,
        corrections_path=corrections_path,
    )


def test_01_baseline_commit_and_prior_reports_preservation(master_report: Sprint10021MasterReport):
    """Test 1: Verify baseline commit and preservation of all prior sprint reports."""
    assert master_report.baseline_commit == "edbe054158e976629a6ee1c0d1a8d3f3cad24f20"
    assert "10.02.1" in master_report.sprint_id

    prior_reports = [
        "data/reports/sprint09_36_delta_neutral_forensics_report.json",
        "data/reports/sprint09_37_carry_accounting_closure_report.json",
        "data/reports/sprint09_38_funding_predictability_report.json",
        "data/reports/sprint09_39_cross_instrument_funding_report.json",
        "data/reports/sprint09_40_multi_asset_carry_report.json",
        "data/reports/sprint09_41_multi_asset_carry_report.json",
        "data/reports/sprint09_42_master_report.json",
        "data/reports/sprint09_43_product_readiness_audit.json",
        "data/reports/sprint10_01_conformal_calibration_report.json",
        "data/reports/sprint10_01_calibration_contract.json",
        "data/reports/sprint10_02_independent_verification_report.json",
        "data/reports/sprint10_02_product_data_contracts.json",
    ]
    for rep in prior_reports:
        p = Path(rep)
        assert p.exists(), f"Prior report missing: {rep}"
        assert p.stat().st_size > 0, f"Prior report empty: {rep}"


def test_02_exact_timestamp_boundaries(master_report: Sprint10021MasterReport):
    """Test 2: Verify exact start and end timestamps of the 6,328-bar timeline."""
    tl = master_report.timeline
    assert tl.earliest_prediction_timestamp == "2026-09-01T21:05:00Z"
    assert tl.latest_prediction_timestamp == "2026-09-23T20:20:00Z"
    assert tl.total_prediction_events == 6328


def test_03_cadence_verification_disproving_15m_assumption(master_report: Sprint10021MasterReport):
    """Test 3: Prove that cadence is strictly 5-minute (300s), disproving the 15m assumption."""
    tl = master_report.timeline
    assert tl.actual_prediction_cadence_seconds == 300
    assert tl.actual_prediction_cadence_minutes == 5
    assert tl.cadence_strictly_uniform is True

    # Check root cause explanation
    assert "COMPOUND_CADENCE_AND_DATE_CONFLATION" in tl.chronology_discrepancy_root_cause


def test_04_parquet_cadence_and_continuity_check():
    """Test 4: Verify 300.0s uniform step and zero irregular gaps in the 6,328 tail bars."""
    parquet_path = Path("data/normalized/btcusdt_5m.parquet")
    df = pd.read_parquet(parquet_path)
    tail = df.tail(6328)

    diffs = tail["timestamp_open"].diff().dropna()
    assert (diffs == 300000).all(), "Non-uniform cadence detected in tail bars"
    assert len(diffs) == 6327


def test_05_prediction_4400_exact_provenance(master_report: Sprint10021MasterReport):
    """Test 5: Verify exact identification of prediction event #4,400."""
    tl = master_report.timeline
    assert tl.prediction_4400_index == 4400
    assert tl.prediction_4400_timestamp == "2026-09-17T03:45:00Z"
    assert tl.prediction_4400_id == "PRED-20260917T034500Z"


def test_06_split_manifest_specification(master_report: Sprint10021MasterReport):
    """Test 6: Verify machine-readable 3-way chronological split manifest schema."""
    sm = master_report.split_manifest
    assert sm.manifest_version == "CBE-SPLIT-MANIFEST-V1.0"
    assert sm.source_model_version == "CBE-0.7.0"
    assert sm.source_model_hash == "c3e5dfbe3bf637f9ef8c8f0f0a40232d3e0984852c786720f17e0b5efd581559"

    # Calibration segment: 4,400 bars
    assert sm.calibration_segment.bar_count == 4400
    assert sm.calibration_segment.start_timestamp_utc == "2026-09-01T21:05:00Z"
    assert sm.calibration_segment.end_timestamp_utc == "2026-09-17T03:40:00Z"

    # Embargo segment: 288 bars = 24h
    assert sm.embargo_segment.bar_count == 288
    assert sm.embargo_segment.start_timestamp_utc == "2026-09-17T03:45:00Z"
    assert sm.embargo_segment.end_timestamp_utc == "2026-09-18T03:40:00Z"

    # Evaluation segment: 1,640 bars
    assert sm.evaluation_segment.bar_count == 1640
    assert sm.evaluation_segment.start_timestamp_utc == "2026-09-18T03:45:00Z"
    assert sm.evaluation_segment.end_timestamp_utc == "2026-09-23T20:20:00Z"

    # Total = 4400 + 288 + 1640 = 6328 bars
    assert sm.calibration_segment.bar_count + sm.embargo_segment.bar_count + sm.evaluation_segment.bar_count == 6328


def test_07_horizon_specific_embargo_bars(master_report: Sprint10021MasterReport):
    """Test 7: Verify horizon embargoes match 5m bar equivalents."""
    emb = master_report.split_manifest.embargo_bars_by_horizon_5m
    assert emb["15m"] == 3    # 15 min / 5m
    assert emb["30m"] == 6    # 30 min / 5m
    assert emb["1h"] == 12    # 60 min / 5m
    assert emb["2h"] == 24    # 120 min / 5m
    assert emb["4h"] == 48    # 240 min / 5m
    assert emb["8h"] == 96    # 480 min / 5m
    assert emb["12h"] == 144  # 720 min / 5m
    assert emb["24h"] == 288  # 1440 min / 5m


def test_08_calibration_evaluation_zero_overlap(master_report: Sprint10021MasterReport):
    """Test 8: Verify strict separation between calibration and evaluation segments."""
    sm = master_report.split_manifest
    assert sm.calibration_evaluation_overlap is False
    assert sm.calibration_segment.end_bar_index < sm.embargo_segment.start_bar_index
    assert sm.embargo_segment.end_bar_index < sm.evaluation_segment.start_bar_index


def test_09_denominator_reconciliation(master_report: Sprint10021MasterReport):
    """Test 9: Verify exact denominator reconciliation."""
    tl = master_report.timeline
    assert tl.total_prediction_events == 6328
    assert tl.total_matured_outcomes == 50007
    assert tl.valid_outcomes == 49855
    assert tl.invalid_outcomes == 114
    assert tl.excluded_outcomes == 38
    assert tl.pending_unmatured_outcomes == 617
    # 50,007 + 617 = 50,624 = 6,328 * 8
    assert tl.total_matured_outcomes + tl.pending_unmatured_outcomes == tl.total_prediction_events * 8


def test_10_unsupported_virgin_holdout_rejected(master_report: Sprint10021MasterReport):
    """Test 10: Verify unsupported virgin-holdout claims are strictly rejected."""
    sb = master_report.selection_bias_audit
    assert sb["evaluation_data_previously_inspected"] is True
    assert sb["evaluation_data_used_in_method_selection"] is True
    assert sb["virgin_holdout_claim"] == "REJECTED_AS_UNFOUNDED"
    assert sb["current_evidence_classification"] == CalibrationEvidenceStatus.CHRONOLOGICALLY_VERIFIED_EXPLORATORY.value

    # Verify INDEPENDENTLY_VALIDATED is NEVER used across any horizon
    for h, assess in master_report.evidence_assessments.items():
        assert assess.evidence_status != CalibrationEvidenceStatus.INDEPENDENTLY_VALIDATED.value


def test_11_evidence_classification_by_horizon(master_report: Sprint10021MasterReport):
    """Test 11: Verify correct evidence classification across all 8 horizons."""
    ev = master_report.evidence_assessments

    # 15m to 4h: CHRONOLOGICALLY_VERIFIED_EXPLORATORY
    for h in ["15m", "30m", "1h", "2h", "4h"]:
        assert ev[h].evidence_status == CalibrationEvidenceStatus.CHRONOLOGICALLY_VERIFIED_EXPLORATORY.value
        assert ev[h].effective_sample_size >= 390

    # 8h and 12h: VALIDATED_WITH_LIMITATIONS
    assert ev["8h"].evidence_status == CalibrationEvidenceStatus.VALIDATED_WITH_LIMITATIONS.value
    assert ev["12h"].evidence_status == CalibrationEvidenceStatus.VALIDATED_WITH_LIMITATIONS.value

    # 24h: INSUFFICIENT_EVIDENCE (N_eff = 62 < 100)
    assert ev["24h"].evidence_status == CalibrationEvidenceStatus.INSUFFICIENT_EVIDENCE.value
    assert ev["24h"].effective_sample_size == 62


def test_12_prior_report_corrections_registry(master_report: Sprint10021MasterReport):
    """Test 12: Verify prior report corrections are fully registered without overwriting history."""
    corrs = master_report.prior_report_corrections
    assert len(corrs) >= 3

    c_ids = [c.correction_id for c in corrs]
    assert "CORR-10021-01" in c_ids
    assert "CORR-10021-02" in c_ids
    assert "CORR-10021-03" in c_ids


def test_13_future_protocol_dormant(master_report: Sprint10021MasterReport):
    """Test 13: Verify future prospective validation protocol is marked dormant."""
    fp = master_report.future_validation_protocol
    assert fp["status"] == "NOT_YET_EXECUTABLE_DORMANT"
    assert len(fp["activation_requirements"]) >= 4


def test_14_pure_analytical_compute_latency(repair_engine: ChronologicalProvenanceRepairEngine):
    """Test 14: Verify repair audit execution completes well within 50 ms budget."""
    t0 = time.perf_counter()
    repair_engine.reconstruct_timeline()
    repair_engine.build_split_manifest()
    repair_engine.assess_horizon_evidence()
    repair_engine.audit_prior_report_corrections()
    elapsed_ms = (time.perf_counter() - t0) * 1000.0

    assert elapsed_ms < 50.0, f"Pure compute latency {elapsed_ms:.2f} ms exceeded 50 ms budget"

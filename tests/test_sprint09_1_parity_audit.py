"""Tests for Sprint 09.1 Frozen Model Artifact Recovery & Runtime Parity Audit.

Verifies:
1. Artifact inventory confirms zero serialized models on disk and verified 29 Sprint 07 report artifacts.
2. Feature parity matrix correctly maps names, dimensions, transformations, and worker mislabeling.
3. Target parity correctly detects the ~17x scale discrepancy (sqrt(288)) between historical targets and live outcomes.
4. Scientific decision gates evaluate to BLOCKED FOR RUNTIME DEPLOYMENT (3 PASS, 6 FAIL/BLOCKED).
5. Report generator creates all 10 required deliverables in output directory.
6. Sprint 07 model freeze remains 100% verified (29/29 canonical artifacts).
"""

import json
import tempfile
from pathlib import Path

import pytest

from coin_behavior_engine.audit.parity_audit import (
    audit_artifact_inventory,
    audit_feature_parity,
    audit_target_parity,
    evaluate_scientific_gates,
    generate_reports,
)
from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze


def test_artifact_inventory_and_search():
    """Verify that audit_artifact_inventory detects 0 model artifacts and discovers 29 Sprint 07 reports."""
    res = audit_artifact_inventory(Path("."))
    assert res["serialized_binary_models_found_in_repo"] == 0
    assert res["missing_model_artifacts_count"] == 5
    assert res["frozen_report_artifacts_count"] >= 29
    assert res["total_artifacts_inventoried"] >= 34


def test_feature_parity_matrix():
    """Verify feature parity matrix detects naming discrepancies and worker mislabeling."""
    res = audit_feature_parity()
    assert res["total_features_audited"] >= 15
    assert res["compatible_count"] >= 5
    assert res["disconnected_runtime_count"] >= 5
    assert res["mismatch_count"] >= 2

    feat_names = [f["name"] for f in res["features"]]
    assert "volatility_realized_24h" in feat_names
    assert "volume_zscore" in feat_names

    # Check volume_zscore specific findings
    vz = next(f for f in res["features"] if f["name"] == "volume_zscore")
    assert vz["parity_status"] == "SHAPE_COLLAPSE_MISMATCH"
    assert vz["training_availability"] == "DROPPED_IN_TRAINING"

    # Check volatility_realized_24h specific findings
    vr = next(f for f in res["features"] if f["name"] == "volatility_realized_24h")
    assert vr["parity_status"] == "SEMANTIC_AND_SCALE_MISMATCH"


def test_target_scale_discrepancy():
    """Verify target parity audit isolates the 17x sqrt(288) scale difference."""
    res = audit_target_parity()
    assert "horizons" in res
    assert "1h" in res["horizons"]
    assert "4h" in res["horizons"]
    assert "24h" in res["horizons"]

    h1 = res["horizons"]["1h"]
    assert h1["scale_factor_ratio"] > 10.0
    assert "17x" in h1["compatibility_verdict"]

    finding_ids = [f["finding_id"] for f in res["critical_findings"]]
    assert "SQRT_288_SCALE_GAP" in finding_ids
    assert "VOLATILITY_REALIZED_24H_MISLABELING" in finding_ids


def test_scientific_decision_gates():
    """Verify scientific decision gates evaluate to BLOCKED FOR RUNTIME DEPLOYMENT."""
    res = evaluate_scientific_gates()
    assert res["overall_candidate_verdict"] == "BLOCKED_FOR_RUNTIME_DEPLOYMENT"
    assert res["gates_evaluated"] == 9
    assert res["gates_passed"] == 3
    assert res["gates_failed"] == 6
    assert res["blocking_gates_count"] == 6

    gate_map = {g["gate_id"]: g["status"] for g in res["gates"]}
    assert gate_map["GATE_A"] == "FAIL"
    assert gate_map["GATE_B"] == "FAIL"
    assert gate_map["GATE_C"] == "FAIL"
    assert gate_map["GATE_D"] == "FAIL"
    assert gate_map["GATE_E"] == "FAIL"
    assert gate_map["GATE_F"] == "PASS"
    assert gate_map["GATE_G"] == "PASS"
    assert gate_map["GATE_H"] == "FAIL"
    assert gate_map["GATE_I"] == "PASS"


def test_report_generation_in_tempdir():
    """Verify that all 10 reports are generated successfully."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        out_path = Path(tmp_dir)
        summary = generate_reports(Path("."), out_path)
        assert summary["status"] == "COMPLETED"
        assert len(summary["files_generated"]) == 10

        expected_files = [
            "artifact_inventory.json",
            "training_pipeline_forensics.md",
            "vol_models_root_cause.md",
            "feature_parity_matrix.json",
            "target_horizon_parity.md",
            "scaler_transformation_audit.md",
            "reproducibility_audit.md",
            "candidate_runtime_architecture.md",
            "scientific_gate_registry.json",
            "executive_summary.md",
        ]
        for f in expected_files:
            file_path = out_path / f
            assert file_path.exists()
            assert file_path.stat().st_size > 0


def test_sprint07_freeze_verification_untouched():
    """Verify that Sprint 07 model freeze remains 100% verified (29/29 canonical artifacts)."""
    freeze_res = verify_sprint07_freeze()
    assert freeze_res["verified"] is True
    assert freeze_res["status"] == "FREEZE_VERIFIED"
    assert freeze_res["verified_artifacts_count"] == 29
    assert freeze_res["total_artifacts_checked"] == 29
    assert len(freeze_res["missing_files"]) == 0

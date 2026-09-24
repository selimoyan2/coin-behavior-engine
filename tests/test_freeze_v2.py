"""Negative security and cross-platform verification test suite for Freeze V2.

Verifies all 9 mandatory mutation and cross-platform invariants:
1. CRLF artifact vs equivalent LF artifact -> BOTH PASS canonical verification.
2. Change one numeric CSV value by 0.000001 -> MUST FAIL.
3. Change one JSON value -> MUST FAIL.
4. Delete one artifact -> MUST FAIL.
5. Change one ordinary space/content byte -> MUST FAIL.
6. Change model version -> MUST FAIL.
7. Change historical boundary -> MUST FAIL.
8. Legacy manifest missing -> MUST FAIL.
9. 29 original Linux/Git artifacts -> MUST PASS.
"""

import json
from pathlib import Path
import shutil
import tempfile
import pytest

from coin_behavior_engine.prospective.freeze import (
    FROZEN_MODEL_VERSION,
    HISTORICAL_RESEARCH_END,
    PROSPECTIVE_START,
    FREEZE_COMMIT,
    compute_sha256,
    compute_canonical_text_sha256,
    verify_sprint07_freeze,
    ModelFreezeViolation,
)

BASE_DIR = Path(__file__).resolve().parents[1]
SPRINT07_DIR = BASE_DIR / "data" / "reports" / "sprint07"
SPRINT08_DIR = BASE_DIR / "data" / "reports" / "sprint08"
V2_MANIFEST = SPRINT08_DIR / "cross_platform_freeze_manifest_v2.json"
LOCKBOX = BASE_DIR / "data" / "prospective" / "lockbox_manifest.json"


def test_01_crlf_vs_lf_both_pass_canonical():
    """Test 1: CRLF artifact vs equivalent LF artifact -> BOTH PASS canonical verification."""
    # Compute canonical hash on raw disk (CRLF on Windows)
    sample_file = SPRINT07_DIR / "absolute_move_forecasts.csv"
    assert sample_file.exists()
    
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)
        crlf_file = tmp_path / "crlf.csv"
        lf_file = tmp_path / "lf.csv"
        
        raw = sample_file.read_bytes()
        lf_bytes = raw.replace(b"\r\n", b"\n")
        crlf_bytes = lf_bytes.replace(b"\n", b"\r\n")
        
        crlf_file.write_bytes(crlf_bytes)
        lf_file.write_bytes(lf_bytes)
        
        h_crlf = compute_canonical_text_sha256(crlf_file)
        h_lf = compute_canonical_text_sha256(lf_file)
        
        assert h_crlf == h_lf
        # Verify both match expected V2 manifest hash
        with open(V2_MANIFEST, "r", encoding="utf-8") as f:
            v2 = json.load(f)
        exp = v2["artifacts"]["absolute_move_forecasts.csv"]["canonical_sha256"]
        assert h_crlf == exp
        assert h_lf == exp


def test_02_change_one_numeric_csv_value_fails():
    """Test 2: Change one numeric CSV value by 0.000001 -> MUST FAIL."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_s7 = Path(tmp_dir) / "sprint07"
        shutil.copytree(SPRINT07_DIR, tmp_s7)
        
        # Mutate a numeric value in absolute_move_forecasts.csv
        target_csv = tmp_s7 / "absolute_move_forecasts.csv"
        content = target_csv.read_text(encoding="utf-8")
        # Replace first decimal occurrence
        mutated = content.replace("0.", "0.000001", 1)
        assert mutated != content
        target_csv.write_text(mutated, encoding="utf-8")
        
        res = verify_sprint07_freeze(sprint07_dir=tmp_s7, lockbox_path=LOCKBOX, v2_manifest_path=V2_MANIFEST)
        assert res["verified"] is False
        assert res["status"] == "MODEL_FREEZE_VIOLATION"
        assert len(res["canonical_mismatches"]) >= 1
        assert res["canonical_mismatches"][0]["file"] == "absolute_move_forecasts.csv"


def test_03_change_one_json_value_fails():
    """Test 3: Change one JSON value -> MUST FAIL."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_s7 = Path(tmp_dir) / "sprint07"
        shutil.copytree(SPRINT07_DIR, tmp_s7)
        
        target_json = tmp_s7 / "claim_registry.json"
        data = json.loads(target_json.read_text(encoding="utf-8"))
        # Mutate one field
        data[0]["status"] = "TAMPERED_STATUS"
        target_json.write_text(json.dumps(data, indent=2), encoding="utf-8")
        
        res = verify_sprint07_freeze(sprint07_dir=tmp_s7, lockbox_path=LOCKBOX, v2_manifest_path=V2_MANIFEST)
        assert res["verified"] is False
        assert res["status"] == "MODEL_FREEZE_VIOLATION"
        assert any(m["file"] == "claim_registry.json" for m in res["canonical_mismatches"])


def test_04_delete_one_artifact_fails():
    """Test 4: Delete one artifact -> MUST FAIL."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_s7 = Path(tmp_dir) / "sprint07"
        shutil.copytree(SPRINT07_DIR, tmp_s7)
        
        target = tmp_s7 / "volatility_forecasts.csv"
        target.unlink()
        
        res = verify_sprint07_freeze(sprint07_dir=tmp_s7, lockbox_path=LOCKBOX, v2_manifest_path=V2_MANIFEST)
        assert res["verified"] is False
        assert res["status"] == "MODEL_FREEZE_VIOLATION"
        assert "volatility_forecasts.csv" in res["missing_files"]


def test_05_change_one_space_or_content_byte_fails():
    """Test 5: Change one ordinary space/content byte -> MUST FAIL."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_s7 = Path(tmp_dir) / "sprint07"
        shutil.copytree(SPRINT07_DIR, tmp_s7)
        
        target = tmp_s7 / "latency_benchmark.csv"
        raw = target.read_bytes()
        # Add a trailing space
        mutated = raw + b" "
        target.write_bytes(mutated)
        
        res = verify_sprint07_freeze(sprint07_dir=tmp_s7, lockbox_path=LOCKBOX, v2_manifest_path=V2_MANIFEST)
        assert res["verified"] is False
        assert res["status"] == "MODEL_FREEZE_VIOLATION"
        assert any(m["file"] == "latency_benchmark.csv" for m in res["canonical_mismatches"])


def test_06_change_model_version_fails():
    """Test 6: Change model version -> MUST FAIL."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_v2 = Path(tmp_dir) / "v2.json"
        with open(V2_MANIFEST, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["model_version"] = "CBE-0.8.0-UNAUTHORIZED"
        tmp_v2.write_text(json.dumps(data), encoding="utf-8")
        
        res = verify_sprint07_freeze(sprint07_dir=SPRINT07_DIR, lockbox_path=LOCKBOX, v2_manifest_path=tmp_v2)
        assert res["verified"] is False
        assert res["status"] == "MODEL_FREEZE_VIOLATION"


def test_07_change_historical_boundary_fails():
    """Test 7: Change historical boundary -> MUST FAIL."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_lockbox = Path(tmp_dir) / "lockbox.json"
        with open(LOCKBOX, "r", encoding="utf-8") as f:
            data = json.load(f)
        data["historical_research_end"] = "2026-09-24T12:00:00 UTC"  # Leaked prospective boundary
        tmp_lockbox.write_text(json.dumps(data), encoding="utf-8")
        
        res = verify_sprint07_freeze(sprint07_dir=SPRINT07_DIR, lockbox_path=tmp_lockbox, v2_manifest_path=V2_MANIFEST)
        assert res["verified"] is False
        assert res["status"] == "MODEL_FREEZE_VIOLATION"
        assert res["lockbox_verified"] is False


def test_08_legacy_manifest_missing_fails():
    """Test 8: Legacy manifest missing -> MUST FAIL."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_s7 = Path(tmp_dir) / "sprint07"
        shutil.copytree(SPRINT07_DIR, tmp_s7)
        
        # Remove legacy reproducibility_manifest.json
        legacy = tmp_s7 / "reproducibility_manifest.json"
        legacy.unlink()
        
        res = verify_sprint07_freeze(sprint07_dir=tmp_s7, lockbox_path=LOCKBOX, v2_manifest_path=V2_MANIFEST)
        assert res["verified"] is False
        assert res["status"] == "MODEL_FREEZE_VIOLATION"
        assert res["legacy_manifest_present"] is False


def test_09_all_29_original_linux_git_artifacts_pass():
    """Test 9: 29 original Linux/Git artifacts (LF) -> MUST PASS."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_s7 = Path(tmp_dir) / "sprint07"
        tmp_s7.mkdir(parents=True, exist_ok=True)
        
        # Copy legacy manifest as-is
        shutil.copy(SPRINT07_DIR / "reproducibility_manifest.json", tmp_s7)
        
        # Write all 29 artifacts strictly with POSIX LF (Linux / Git checkout simulation)
        with open(V2_MANIFEST, "r", encoding="utf-8") as f:
            v2 = json.load(f)
            
        for fname in v2["artifacts"].keys():
            orig_bytes = (SPRINT07_DIR / fname).read_bytes()
            lf_bytes = orig_bytes.replace(b"\r\n", b"\n")
            (tmp_s7 / fname).write_bytes(lf_bytes)
            
        res = verify_sprint07_freeze(sprint07_dir=tmp_s7, lockbox_path=LOCKBOX, v2_manifest_path=V2_MANIFEST)
        assert res["verified"] is True
        assert res["status"] == "FREEZE_VERIFIED"
        assert res["canonical_hashes_verified"] == 29
        assert len(res["canonical_mismatches"]) == 0
        assert len(res["missing_files"]) == 0
        assert res["lockbox_verified"] is True
        assert res["legacy_manifest_present"] is True

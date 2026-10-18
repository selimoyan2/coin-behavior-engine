"""Regression & Integrity Test Suite for Sprint 11.16B.1.

Sprint 11.16B.1: Shadow Activation Readiness — Resource & Data Safety Verification.
Verifies all 6 deliverables, exact status declarations, dynamic checklist v2
mathematical consistency, atomic snapshot I/O read contracts, and offline
benchmark invariants.
"""

from collections import Counter
import json
from pathlib import Path
import tempfile
import pytest

from coin_behavior_engine.product.market_data_adapter import (
    AtomicSnapshotIO,
    DataClassification,
    FactualMarketDataRecord,
    MarketDataFreshnessStatus,
    MarketDataSourceHealth,
)
from coin_behavior_engine.research_lab.shadow_decision_protocol import (
    BASE_CODE_COMMIT,
    CANONICAL_DATASET_SHA256,
    GENESIS_PARENT_HASH,
    PolicyFreezeManifest,
    ProspectiveIntegrityEngine,
    ShadowDecisionAction,
    ShadowDecisionRecord,
)

DELIVERABLE_FILES = [
    "shadow_cpu_contention_audit.md",
    "shadow_resource_benchmark.md",
    "live_capture_read_contract_audit.md",
    "shadow_freeze_chronology_audit.md",
    "shadow_activation_checklist_v2.json",
    "research_report_11_16b_1.md",
]


def test_deliverables_exist_in_research_outputs_and_root():
    """Verify that all 6 required deliverables exist in research_outputs/ and project root."""
    for filename in DELIVERABLE_FILES:
        res_file = Path("research_outputs") / filename
        root_file = Path(filename)
        assert res_file.is_file(), f"Missing deliverable in research_outputs: {filename}"
        assert root_file.is_file(), f"Missing deliverable in root: {filename}"
        assert res_file.stat().st_size > 300, f"Deliverable too small: {filename}"
        assert root_file.stat().st_size > 300, f"Root deliverable too small: {filename}"


def test_declarations_exact_values():
    """Verify that research report and checklist contain the exact required declarations."""
    rep_text = Path("research_outputs/research_report_11_16b_1.md").read_text(encoding="utf-8")
    assert "RESOURCE_CAPACITY=VERIFIED" in rep_text
    assert "MARKET_DATA_ACCESS=NOT_AUTHORIZED" in rep_text
    assert "FREEZE_CHRONOLOGY=UNVERIFIED" in rep_text
    assert "PROSPECTIVE_OBSERVATION=NOT_STARTED" in rep_text
    assert "PROTECTED_SERVICES_MUTATED=NO" in rep_text
    assert "LIVE_TRADING=PROHIBITED" in rep_text

    chk = json.loads(Path("research_outputs/shadow_activation_checklist_v2.json").read_text(encoding="utf-8"))
    decls = chk["formal_declarations"]
    assert decls["RESOURCE_CAPACITY"] == "VERIFIED"
    assert decls["MARKET_DATA_ACCESS"] == "NOT_AUTHORIZED"
    assert decls["FREEZE_CHRONOLOGY"] == "UNVERIFIED"
    assert decls["PROSPECTIVE_OBSERVATION"] == "NOT_STARTED"
    assert decls["PROTECTED_SERVICES_MUTATED"] == "NO"
    assert decls["LIVE_TRADING"] == "PROHIBITED"


def test_dynamic_checklist_v2_mathematical_consistency():
    """Verify that checklist v2 is computed dynamically with zero arithmetic discrepancies."""
    chk_path = Path("research_outputs/shadow_activation_checklist_v2.json")
    data = json.loads(chk_path.read_text(encoding="utf-8"))
    
    conditions = data["conditions"]
    stats = data["summary_statistics"]
    
    total = len(conditions)
    assert stats["total_mandatory_conditions"] == total, "Total conditions mismatch"
    
    status_counts = Counter(c["status"] for c in conditions)
    assert stats["verified_count"] == status_counts.get("VERIFIED", 0)
    assert stats["blocked_count"] == status_counts.get("BLOCKED", 0)
    assert stats["not_yet_tested_count"] == status_counts.get("NOT_YET_TESTED", 0)
    
    # Mathematical identity: Total == Sum of partition counts
    assert total == stats["verified_count"] + stats["blocked_count"] + stats["not_yet_tested_count"]
    
    # Check that each condition has non-empty required fields
    for cond in conditions:
        assert cond["id"].startswith("COND_")
        assert len(cond["name"]) > 5
        assert cond["status"] in {"VERIFIED", "BLOCKED", "NOT_YET_TESTED"}
        assert len(cond["evidence"]) > 10
        if cond["status"] == "BLOCKED":
            assert cond["blocker"] is not None
            assert cond["remediation"] is not None


def test_atomic_snapshot_io_atomic_write_and_safe_read():
    """Verify that AtomicSnapshotIO safely writes and reads JSON snapshots without torn states."""
    with tempfile.TemporaryDirectory() as tmpdir:
        snap_path = Path(tmpdir) / "live_market_state.json"
        
        # Test safe_read on non-existent file
        ok, data, err = AtomicSnapshotIO.safe_read(snap_path)
        assert not ok
        assert err == "FILE_NOT_FOUND"
        
        # Test atomic write
        payload = {
            "schema_version": "1.0.0",
            "symbol": "BTCUSDT",
            "spot_price_usdt": 82000.0,
            "is_closed": True,
            "writer_heartbeat_utc": "2026-10-18T20:30:00Z",
        }
        AtomicSnapshotIO.atomic_write(snap_path, payload)
        assert snap_path.is_file()
        
        # Test safe_read on valid file
        ok, read_data, err = AtomicSnapshotIO.safe_read(snap_path)
        assert ok
        assert err is None
        assert read_data["spot_price_usdt"] == 82000.0
        assert read_data["is_closed"] is True
        
        # Test corruption handling
        snap_path.write_text("{corrupt_json: invalid", encoding="utf-8")
        ok, corrupt_data, err = AtomicSnapshotIO.safe_read(snap_path)
        assert not ok
        assert "CORRUPT_JSON" in err


def test_offline_engine_evaluation_and_chain_integrity():
    """Verify that ProspectiveIntegrityEngine correctly evaluates synthetic bars and chains hashes."""
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_D_SELECTIVE_TREND_ONLY")
    
    for i in range(10):
        rec = engine.evaluate_bar(
            bar_idx=i,
            timestamp_utc=f"2026-10-18T12:{i*5:02d}:00Z",
            availability_timestamp_utc=f"2026-10-18T12:{i*5:02d}:00Z",
            open_p=80000.0 + i * 10,
            high_p=80050.0 + i * 10,
            low_p=79950.0 + i * 10,
            close_p=80020.0 + i * 10,
            features={"trend_direction": 1, "analogue_score": 0.65},
        )
        assert rec.sequence_number == i
        assert len(rec.decision_hash) == 64
        
    ok, err = engine.hash_chain.verify_integrity()
    assert ok, f"Hash chain integrity failed: {err}"
    assert len(engine.hash_chain) == 10


def test_freeze_chronology_audit_contents():
    """Verify that freeze chronology audit correctly documents UTC+3 root cause."""
    text = Path("research_outputs/shadow_freeze_chronology_audit.md").read_text(encoding="utf-8")
    assert "09773621f7026ac2630fb7674cd11aadaf934a70" in text
    assert "2026-10-18T21:00:00Z" in text
    assert "2026-10-18T18:31:03Z" in text
    assert "TRT" in text or "UTC+3" in text
    assert "FREEZE_CHRONOLOGY=UNVERIFIED" in text


def test_cpu_contention_audit_contents():
    """Verify that CPU contention audit documents 0.02% steady-state CPU."""
    text = Path("research_outputs/shadow_cpu_contention_audit.md").read_text(encoding="utf-8")
    assert "6t63aehpaw0cw1bbt4zcm09g" in text
    assert "0.02%" in text
    assert "RESOURCE_CAPACITY=VERIFIED" in text

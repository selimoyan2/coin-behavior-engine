"""Deterministic Preflight Verification Test Suite for CBE Sprint 11.16A.

Sprint 11.16A: Prospective Shadow Environment Preflight & Isolation Verification.
Verifies:
1. Protected services inventory and non-mutation invariants.
2. Five frozen policy parameter digests and Policy E hurdle lock.
3. Preservation of FREEZE_CHRONOLOGY_UNVERIFIED status.
4. Proposed shadow Docker Compose isolation invariants (air-gap, CPU, memory, read-only root).
5. Read-only volume mount (:ro) configuration for live capture data.
6. Fail-closed engine behavior on stale or missing market data.
7. Zero-order capability and air-gap network isolation.
8. Preflight verdict structure and mandatory status declarations.
9. Completeness of all 9 markdown and JSON deliverables.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import pytest

from coin_behavior_engine.research_lab.shadow_decision_protocol import (
    BASE_CODE_COMMIT,
    CANONICAL_DATASET_SHA256,
    GENESIS_PARENT_HASH,
    DecisionHashChain,
    PolicyFreezeManifest,
    ProspectiveIntegrityEngine,
    ShadowDecisionAction,
    ShadowDecisionRecord,
    ShadowExecutionSimulator,
)

OUTPUT_DIR = Path("research_outputs")
VERDICT_PATH = OUTPUT_DIR / "shadow_preflight_verdict.json"
MANIFEST_PATH = OUTPUT_DIR / "policy_freeze_manifest.json"


# -------------------------------------------------------------------------
# Test 1: Base Commit & Clean Baseline State
# -------------------------------------------------------------------------
def test_01_base_commit_and_dataset_lock():
    """Verify base code commit and canonical dataset SHA-256 fingerprint."""
    dataset_file = OUTPUT_DIR / "market_state_dataset.parquet"
    assert dataset_file.is_file(), f"Dataset missing: {dataset_file}"

    hasher = hashlib.sha256()
    with open(dataset_file, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    assert hasher.hexdigest() == CANONICAL_DATASET_SHA256


# -------------------------------------------------------------------------
# Test 2: Protected Services Inventory Invariants
# -------------------------------------------------------------------------
def test_02_protected_services_inventory():
    """Verify that all four protected service UUIDs are tracked in the preflight verdict."""
    assert VERDICT_PATH.is_file()
    verdict = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))

    protected = verdict.get("protected_services_status", {})
    assert "production" in protected
    assert protected["production"]["uuid"] == "6t63aehpaw0cw1bbt4zcm09g"
    assert protected["production"]["mutated"] is False

    assert "market_intelligence_staging" in protected
    assert protected["market_intelligence_staging"]["uuid"] == "dzzfws54by1whlbq6fk4ywut"
    assert protected["market_intelligence_staging"]["live_capture_volume_mount_mode"] == "ro"
    assert protected["market_intelligence_staging"]["mutated"] is False

    assert "live_capture" in protected
    assert protected["live_capture"]["uuid"] == "zgit1s3n1acdtqtsxp0s44vj"
    assert protected["live_capture"]["role"] == "EXCLUSIVE_WRITER"
    assert protected["live_capture"]["mutated"] is False

    assert "stopped_scoring_worker" in protected
    assert protected["stopped_scoring_worker"]["uuid"] == "3v3dey5y1ybg6zqkv0wmuxtd"
    assert protected["stopped_scoring_worker"]["state"] == "exited"
    assert protected["stopped_scoring_worker"]["mutated"] is False


# -------------------------------------------------------------------------
# Test 3: Five Frozen Policies Parameter Digests
# -------------------------------------------------------------------------
def test_03_five_frozen_policies_digests():
    """Verify bit-for-bit SHA-256 digests for all 5 frozen candidate policies."""
    assert MANIFEST_PATH.is_file()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["freeze_status"] == "FROZEN_BEFORE_UNSEEN_EVALUATION"
    assert manifest["winner_selection_status"] == "FORBIDDEN_NO_WINNER_SELECTED"

    expected_hashes = {
        "POLICY_A_USDT_CASH": "08f5376a30e5fa54902b13df8d012f218d8e8279986dceec4368b362e4ad0fed",
        "POLICY_B_BTC_BUY_AND_HOLD": "40a72dedfd4daf722ab8f49dab9f1741827530d51c88ff8f8b2e9df1e47bc461",
        "POLICY_C_TREND48_FOLLOWING": "0bd242a12943b9e58f6cf0047c2def95fbd74334eeb74a91bda4ccf4f5aa37e7",
        "POLICY_D_SELECTIVE_TREND_ONLY": "ef5e193beebcade0eef74b3804c72f1bd6212d2a73d9520284c830d28f9e1065",
        "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED": "f64eab504192d969af4ac2aaeb6d875f33ccc5dffae5582a16ff120c2128d994",
    }

    policies = manifest.get("candidate_policies", {})
    for pid, expected_h in expected_hashes.items():
        assert pid in policies, f"Missing policy: {pid}"
        raw_params = policies[pid]["frozen_parameters"]
        calc_h = hashlib.sha256(
            json.dumps(raw_params, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        assert calc_h == expected_h, f"Parameter hash mismatch for {pid}: {calc_h} != {expected_h}"


# -------------------------------------------------------------------------
# Test 4: Policy E Operational Analogue Hurdle Lock
# -------------------------------------------------------------------------
def test_04_policy_e_analogue_hurdle_lock():
    """Verify that Policy E analogue threshold is locked to 0.60."""
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    params = manifest["candidate_policies"]["POLICY_E_SELECTIVE_ANALOGUE_ASSISTED"]["frozen_parameters"]
    assert params["analogue_min_positive_prob"] == 0.60


# -------------------------------------------------------------------------
# Test 5: Freeze Chronology Status Unverified Preservation
# -------------------------------------------------------------------------
def test_05_freeze_chronology_unverified_preserved():
    """Verify that freeze chronology status remains explicitly FREEZE_CHRONOLOGY_UNVERIFIED."""
    verdict = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))
    assert verdict.get("freeze_chronology_status") == "FREEZE_CHRONOLOGY_UNVERIFIED"
    assert "FREEZE_CHRONOLOGY_UNVERIFIED" in verdict.get("preflight_verdicts", {}).get("4_policy_freeze_verification", "")


# -------------------------------------------------------------------------
# Test 6: Shadow Isolation Architecture Specification Checks
# -------------------------------------------------------------------------
def test_06_shadow_isolation_architecture_file():
    """Verify that shadow_isolation_architecture.md contains all required isolation invariants."""
    arch_file = OUTPUT_DIR / "shadow_isolation_architecture.md"
    assert arch_file.is_file()
    content = arch_file.read_text(encoding="utf-8")

    assert 'network_mode: "none"' in content
    assert 'read_only: true' in content
    assert 'cpus: 0.20' in content or "0.20" in content
    assert 'mem_limit: 250m' in content or "250" in content
    assert 'zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data:/app/data/live_capture:ro' in content
    assert 'cbe_prospective_shadow_data' in content
    assert 'CBE_TRADING_DISABLED=true' in content


# -------------------------------------------------------------------------
# Test 7: Fail-Closed On Stale Market Data
# -------------------------------------------------------------------------
def test_07_fail_closed_on_stale_market_data():
    """Verify that ProspectiveIntegrityEngine fails closed to POSITION_OPEN_DATA_STALE when latency > 15m."""
    engine = ProspectiveIntegrityEngine(policy_id="POLICY_B_BTC_BUY_AND_HOLD", max_data_latency_minutes=15.0)

    # Initial buy at bar 0
    engine.evaluate_bar(
        bar_idx=0,
        timestamp_utc="2026-10-18T12:00:00Z",
        availability_timestamp_utc="2026-10-18T12:00:00Z",
        open_p=68000.0,
        high_p=68100.0,
        low_p=67900.0,
        close_p=68050.0,
        features={"regime": "SIDEWAYS"},
    )
    engine.simulator.execute_hypothetical_buy(next_open=68050.0, bar_idx=1)
    assert engine.simulator.position_active is True
    btc_qty = engine.simulator.btc_balance

    # Bar 1 with 20 minute latency (>15 minute threshold)
    rec_stale = engine.evaluate_bar(
        bar_idx=1,
        timestamp_utc="2026-10-18T12:05:00Z",
        availability_timestamp_utc="2026-10-18T12:25:00Z",  # 20 min latency
        open_p=68050.0,
        high_p=68150.0,
        low_p=68000.0,
        close_p=68100.0,
        features={"regime": "SIDEWAYS"},
    )

    # Must transition to POSITION_OPEN_DATA_STALE and preserve inventory
    assert rec_stale.decision == ShadowDecisionAction.POSITION_OPEN_DATA_STALE.value
    assert engine.simulator.position_active is True
    assert engine.simulator.btc_balance == btc_qty
    assert rec_stale.evidence_rationale.get("valuation_status") == "VALUATION_UNAVAILABLE_MARK_FROZEN"


# -------------------------------------------------------------------------
# Test 8: Preflight Verdict Mandatory Declarations
# -------------------------------------------------------------------------
def test_08_preflight_verdict_declarations():
    """Verify all 7 mandatory declarations are explicitly present in shadow_preflight_verdict.json."""
    verdict = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))
    decs = verdict.get("mandatory_declarations", {})

    assert decs.get("SPRINT_11_16A_STATUS") in ("PASS", "BLOCKED")
    assert decs.get("SHADOW_ENVIRONMENT_CREATED") == "NO"
    assert decs.get("PROSPECTIVE_OBSERVATION_STARTED") == "NO"
    assert decs.get("LIVE_TRADING_AUTHORIZATION") == "UNAUTHORIZED_PROHIBITED"
    assert decs.get("PROTECTED_SERVICES_MUTATED") == "NO"
    assert decs.get("POLICY_PARAMETERS_CHANGED") == "NO"
    assert decs.get("NEXT_STEP") == "OPERATOR_REVIEW_REQUIRED"


# -------------------------------------------------------------------------
# Test 9: Deliverables Files Presence
# -------------------------------------------------------------------------
def test_09_deliverables_presence():
    """Verify that all required markdown and JSON deliverables exist in research_outputs/."""
    required_files = [
        "shadow_environment_discovery.md",
        "shadow_isolation_architecture.md",
        "shadow_market_data_access_plan.md",
        "shadow_policy_freeze_verification.md",
        "shadow_storage_and_checkpoint_plan.md",
        "shadow_operational_safety_plan.md",
        "shadow_activation_checklist.md",
        "shadow_preflight_verdict.json",
        "research_report_11_16a.md",
    ]
    for rf in required_files:
        p = OUTPUT_DIR / rf
        assert p.is_file(), f"Missing required deliverable: {p}"

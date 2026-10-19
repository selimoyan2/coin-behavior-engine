"""Comprehensive test suite for Sprint 11.16B.7: ATR Unit Forensics & Runtime Evidence Correction.

Verifies:
1. Canonical dataset provenance & integrity (SHA-256 match, 105,120 rows).
2. Gate attribution calculations matching empirical findings across 104,256 valid bars.
3. Frozen policy parameters remain 100% unmodified (scientific policy identity preserved).
4. Runtime resource truth: LINUX_CGROUP_RUNTIME=NOT_TESTED, tracemalloc vs RSS disambiguation.
5. Activation matrix consistency across software correctness, frozen identity, real-data coverage,
   resource verification, and operator authorization.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import pytest
import pandas as pd
import numpy as np

CANONICAL_DATASET_SHA256 = "2e99190189dcc7b041de67e7833c3581770c87737cf42e0d35ebd1d52fd2c487"
DATASET_PATH = Path("research_outputs/market_state_dataset.parquet")
CSV_ATTRIBUTION_PATH = Path("research_outputs/policy_gate_attribution_11_16b_7.csv")
ROOT_CSV_PATH = Path("policy_gate_attribution_11_16b_7.csv")
FORENSICS_MD_PATH = Path("research_outputs/atr_unit_forensics_11_16b_7.md")
RUNTIME_MD_PATH = Path("research_outputs/runtime_measurement_corrections_11_16b_7.md")
ACTIVATION_GATE_PATH = Path("research_outputs/shadow_activation_gate_11_16b_7.json")
FREEZE_MANIFEST_PATH = Path("research_outputs/policy_freeze_manifest.json")


def test_canonical_dataset_provenance():
    """Verify the canonical market dataset exists and matches cryptographic digest."""
    assert DATASET_PATH.is_file(), f"Canonical dataset missing at {DATASET_PATH}"
    data_bytes = DATASET_PATH.read_bytes()
    computed_hash = hashlib.sha256(data_bytes).hexdigest()
    assert computed_hash.lower() == CANONICAL_DATASET_SHA256.lower(), (
        f"Digest mismatch: {computed_hash} != {CANONICAL_DATASET_SHA256}"
    )

    df = pd.read_parquet(DATASET_PATH)
    assert len(df) == 105120, f"Expected 105120 rows, got {len(df)}"


def test_gate_attribution_csv_content():
    """Verify the gate attribution CSV exists, is well-formed, and contains verified counts."""
    assert CSV_ATTRIBUTION_PATH.is_file(), "Attribution CSV missing from research_outputs"
    assert ROOT_CSV_PATH.is_file(), "Attribution CSV missing from root"

    with open(CSV_ATTRIBUTION_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = {r["gate_id"]: r for r in reader}

    # Verify key gates are present
    assert "GATE_0_WARMUP_EXCLUSION" in rows
    assert "GATE_1_TREND_ALIGNMENT" in rows
    assert "GATE_2_ANTI_CHASE" in rows
    assert "GATE_3_STRUCTURAL_ELIGIBLE" in rows
    assert "GATE_4_FROZEN_ATR_FILTER" in rows
    assert "GATE_5_POLICY_D_FROZEN_COMBINED" in rows
    assert "GATE_7_POLICY_E_FROZEN_COMBINED" in rows
    assert "GATE_8_PROPOSED_CORRECTED_ATR" in rows
    assert "GATE_9_POLICY_D_V2_PROPOSED_COMBINED" in rows

    # Verify counts
    assert int(rows["GATE_0_WARMUP_EXCLUSION"]["eligible_bars"]) == 104256
    assert int(rows["GATE_1_TREND_ALIGNMENT"]["eligible_bars"]) == 38569
    assert int(rows["GATE_2_ANTI_CHASE"]["eligible_bars"]) == 100330
    assert int(rows["GATE_3_STRUCTURAL_ELIGIBLE"]["eligible_bars"]) == 34813
    assert int(rows["GATE_4_FROZEN_ATR_FILTER"]["eligible_bars"]) == 4
    assert int(rows["GATE_5_POLICY_D_FROZEN_COMBINED"]["eligible_bars"]) == 0
    assert int(rows["GATE_7_POLICY_E_FROZEN_COMBINED"]["eligible_bars"]) == 0
    assert int(rows["GATE_8_PROPOSED_CORRECTED_ATR"]["eligible_bars"]) == 89675
    assert int(rows["GATE_9_POLICY_D_V2_PROPOSED_COMBINED"]["eligible_bars"]) == 31092


def test_frozen_policy_invariants_unmodified():
    """Verify that original frozen parameters for Policy D and Policy E are NOT modified."""
    assert FREEZE_MANIFEST_PATH.is_file(), "Policy freeze manifest missing"
    manifest = json.loads(FREEZE_MANIFEST_PATH.read_text(encoding="utf-8"))

    policies = manifest.get("candidate_policies", {})
    assert "POLICY_D_SELECTIVE_TREND_ONLY" in policies
    assert "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED" in policies

    pol_d = policies["POLICY_D_SELECTIVE_TREND_ONLY"]
    pol_e = policies["POLICY_E_SELECTIVE_ANALOGUE_ASSISTED"]

    # Frozen thresholds must strictly remain 0.015 and 0.065
    assert pol_d["frozen_parameters"]["min_volatility_atr_pct"] == 0.015
    assert pol_d["frozen_parameters"]["max_volatility_atr_pct"] == 0.065
    assert pol_e["frozen_parameters"]["min_volatility_atr_pct"] == 0.015
    assert pol_e["frozen_parameters"]["max_volatility_atr_pct"] == 0.065


def test_runtime_resource_truth_reporting():
    """Verify runtime report and activation gate mandate LINUX_CGROUP_RUNTIME=NOT_TESTED."""
    assert RUNTIME_MD_PATH.is_file(), "Runtime corrections markdown missing"
    content = RUNTIME_MD_PATH.read_text(encoding="utf-8")
    assert "LINUX_CGROUP_RUNTIME=NOT_TESTED" in content
    assert "tracemalloc" in content
    assert "Resident Set Size (RSS)" in content
    assert "cgroup v2 memory.current" in content
    assert "retracted" in content.lower()

    assert ACTIVATION_GATE_PATH.is_file(), "Activation gate JSON missing"
    gate_data = json.loads(ACTIVATION_GATE_PATH.read_text(encoding="utf-8"))
    decl = gate_data.get("global_runtime_declarations", {})

    assert decl.get("linux_cgroup_runtime") == "NOT_TESTED"
    assert decl.get("prospective_observation") == "NOT_STARTED"
    assert "PROHIBITED" in decl.get("live_trading")
    assert decl.get("policy_parameters_changed") == "NO"
    assert decl.get("operator_authorization") == "NOT_GRANTED"
    assert decl.get("next_step") == "OPERATOR_REVIEW"


def test_activation_matrix_evaluations():
    """Verify activation matrix contains rigorous 5-dimension assessment for all 5 policies."""
    assert ACTIVATION_GATE_PATH.is_file()
    gate_data = json.loads(ACTIVATION_GATE_PATH.read_text(encoding="utf-8"))
    matrix = gate_data.get("policy_activation_matrix", {})

    expected_policies = [
        "POLICY_A_USDT_CASH",
        "POLICY_B_BTC_BUY_AND_HOLD",
        "POLICY_C_TREND48_FOLLOWING",
        "POLICY_D_SELECTIVE_TREND_ONLY",
        "POLICY_E_SELECTIVE_ANALOGUE_ASSISTED",
    ]

    for p in expected_policies:
        assert p in matrix, f"Policy {p} missing from matrix"
        p_eval = matrix[p]
        assert "software_correctness" in p_eval
        assert "frozen_policy_identity" in p_eval
        assert "real_data_execution_coverage" in p_eval
        assert "resource_verification" in p_eval
        assert "operator_authorization" in p_eval
        assert "activation_readiness" in p_eval

        # None of the policies can be authorized or active
        assert p_eval["operator_authorization"]["status"] == "NOT_GRANTED"
        assert "BLOCKED" in p_eval["activation_readiness"] or "REJECTED" in p_eval["activation_readiness"]

    # Policies D and E must reflect defect identification and rejection
    assert matrix["POLICY_D_SELECTIVE_TREND_ONLY"]["software_correctness"]["status"] == "DEFECT_IDENTIFIED"
    assert matrix["POLICY_D_SELECTIVE_TREND_ONLY"]["real_data_execution_coverage"]["status"] == "FAIL_ZERO_TRADES"
    assert matrix["POLICY_E_SELECTIVE_ANALOGUE_ASSISTED"]["software_correctness"]["status"] == "DEFECT_IDENTIFIED"
    assert matrix["POLICY_E_SELECTIVE_ANALOGUE_ASSISTED"]["real_data_execution_coverage"]["status"] == "FAIL_ZERO_TRADES"

    # Proposed V2 candidate must be segregated
    assert "proposed_candidates_for_future_freeze" in gate_data
    assert "POLICY_D_V2_CORRECTED_ATR" in gate_data["proposed_candidates_for_future_freeze"]

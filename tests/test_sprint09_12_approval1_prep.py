"""Sprint 09.12 / Approval 1 Preparation Test Suite.

Verifies:
1. 29/29 Production freeze integrity.
2. Inert Docker Compose template safety (read-only root, network none, cgroup limits).
3. Linux staging benchmark runner execution and accounting conservation.
4. Operator runbook completeness.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze
from coin_behavior_engine.shadow_v080.benchmark_staging_linux import run_staging_benchmark


def test_01_production_freeze_verified():
    """Verify 29/29 canonical Sprint 07 frozen artifacts."""
    res = verify_sprint07_freeze(raise_on_error=False)
    assert res.get("verified") is True
    assert res.get("status") == "FREEZE_VERIFIED"
    assert res.get("canonical_hashes_verified") == 29


def test_02_inert_compose_safety_controls():
    """Verify all mandatory safety constraints in docker-compose.cbe-080-shadow.inert.yaml."""
    compose_file = Path("deploy/shadow_v080/docker-compose.cbe-080-shadow.inert.yaml")
    assert compose_file.exists(), "Missing docker-compose.cbe-080-shadow.inert.yaml"

    content = compose_file.read_text(encoding="utf-8")

    # 1. Network disabled
    assert 'network_mode: "none"' in content, "network_mode must be 'none'"

    # 2. Read-only root
    assert "read_only: true" in content, "read_only must be true"

    # 3. Tmpfs configured
    assert "tmpfs:" in content, "tmpfs must be configured for /tmp"

    # 4. Prospective guards
    assert "CBE_RECORD_LABEL=WARMUP_REPLAY" in content
    assert "CBE_PROSPECTIVE_OBSERVATION_ENABLED=false" in content
    assert "CBE_ENFORCE_PROSPECTIVE_GUARD=true" in content

    # 5. Trading disabled
    assert "CBE_TRADING_DISABLED=true" in content

    # 6. Manual start only
    assert 'profiles: ["manual"]' in content
    assert 'restart: "no"' in content

    # 7. CGroup limits
    assert "mem_limit: 300m" in content
    assert "cpus: 0.25" in content
    assert "memory: 300M" in content


def test_03_benchmark_staging_runner_offline():
    """Verify offline benchmark execution, accounting conservation, and prospective label guard."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        res = run_staging_benchmark(
            output_dir=Path(tmp_dir),
            warmup_bars=20,
            steady_state_cycles=20,
            rss_budget_mb=300.0,
        )

        assert res["benchmark_verdict"]["status"] == "PASS"
        assert res["recovery_and_integrity"]["hash_chain_valid"] is True
        assert res["recovery_and_integrity"]["accounting_conserved"] is True
        assert res["safety_invariants"]["network_requests_executed"] == 0
        assert res["safety_invariants"]["prospective_label_guard_intact"] is True
        assert res["safety_invariants"]["prospective_scored_events_count"] == 0
        assert res["safety_invariants"]["trading_disabled"] is True

        out_json = Path(tmp_dir) / "staging_linux_benchmark_results.json"
        assert out_json.exists()


def test_04_operator_runbook_completeness():
    """Verify operator runbook specifies required prerequisites, commands, and failure conditions."""
    runbook_path = Path("data/reports/sprint09_12/operator_linux_benchmark_runbook.md")
    assert runbook_path.exists(), "Missing operator runbook"

    content = runbook_path.read_text(encoding="utf-8")
    assert "PREREQUISITES" in content
    assert "OPTION A" in content
    assert "OPTION B" in content
    assert "EXPECTED OUTPUTS" in content
    assert "FAILURE CONDITIONS" in content
    assert "CLEANUP COMMANDS" in content
    assert "CONFIRM PRODUCTION IS COMPLETELY UNAFFECTED" in content

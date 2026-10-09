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
    assert "OPTION 1" in content
    assert "OPTION 2" in content
    assert "--memory=300m" in content
    assert "EXPECTED OUTPUTS" in content
    assert "FAILURE CONDITIONS" in content
    assert "CLEANUP COMMANDS" in content
    assert "CONFIRM PRODUCTION IS COMPLETELY UNAFFECTED" in content


def test_05_rss_budget_breach_produces_fail():
    """Verify that a Linux peak RSS measurement above budget strictly forces verdict to FAIL."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        # Set an unrealistically low budget of 5.0 MB so measured RSS (~150MB) exceeds it
        res = run_staging_benchmark(
            output_dir=Path(tmp_dir),
            warmup_bars=20,
            steady_state_cycles=20,
            rss_budget_mb=5.0,
            simulate_linux=True,
        )

        assert res["benchmark_verdict"]["status"] == "FAIL"
        assert "RSS_BUDGET_BREACH" in res["benchmark_verdict"]["blocking_failure_reasons"]
        assert res["mandatory_gates"]["gate_rss_budget"]["passed"] is False


def test_06_invalid_hash_chain_produces_fail(monkeypatch):
    """Verify that a corrupted or tampered cryptographic hash chain forces verdict to FAIL."""
    from collections import namedtuple
    from coin_behavior_engine.shadow_v080.collector import ShadowCollectorV080

    AuditResult = namedtuple("AuditResult", ["is_valid", "total_events", "violations"])

    audit_calls = 0
    orig_audit = ShadowCollectorV080.audit_full_history

    def mock_audit(self):
        nonlocal audit_calls
        audit_calls += 1
        if audit_calls >= 3:
            return AuditResult(is_valid=False, total_events=10, violations=["Tampered hash at seq=5"])
        return orig_audit(self)

    monkeypatch.setattr(ShadowCollectorV080, "audit_full_history", mock_audit)

    with tempfile.TemporaryDirectory() as tmp_dir:
        res = run_staging_benchmark(
            output_dir=Path(tmp_dir),
            warmup_bars=20,
            steady_state_cycles=20,
            rss_budget_mb=300.0,
        )

        assert res["benchmark_verdict"]["status"] == "FAIL"
        assert "HASH_CHAIN_INTEGRITY_FAIL" in res["benchmark_verdict"]["blocking_failure_reasons"]
        assert res["mandatory_gates"]["gate_hash_chain"]["passed"] is False


def test_07_broken_accounting_identity_produces_fail(monkeypatch):
    """Verify that broken accounting conservation (preds != matured + disqualified + pending) forces verdict to FAIL."""
    from coin_behavior_engine.shadow_v080.prediction_store import ImmutablePredictionStoreV080, ShadowPredictionEvent

    phantom_ev = ShadowPredictionEvent(
        event_id="PHANTOM-PRED",
        experiment_id="phantom",
        protocol_version="1.0",
        candidate_branch="candidate_c",
        forecast_origin_utc="2026-10-09T00:00:00Z",
        durable_commit_time_utc="2026-10-09T00:00:00Z",
        target_horizon="1h",
        target_maturity_utc="2026-10-09T01:00:00Z",
        feature_fingerprint="abc",
        component_hashes={},
        data_quality={},
        point_prediction=0.0,
        interval_80={},
        interval_95={},
        market_state="STABLE",
        record_label="WARMUP_REPLAY",
    )

    def mock_list(self):
        evs = self._unmatured_events.copy()
        evs.append(phantom_ev)
        return evs

    monkeypatch.setattr(ImmutablePredictionStoreV080, "list_events", mock_list)

    with tempfile.TemporaryDirectory() as tmp_dir:
        res = run_staging_benchmark(
            output_dir=Path(tmp_dir),
            warmup_bars=20,
            steady_state_cycles=20,
            rss_budget_mb=300.0,
        )

        assert res["benchmark_verdict"]["status"] == "FAIL"
        assert "ACCOUNTING_CONSERVATION_FAIL" in res["benchmark_verdict"]["blocking_failure_reasons"]
        assert res["mandatory_gates"]["gate_accounting_conservation"]["passed"] is False


def test_08_invalid_prospective_label_or_flag_produces_fail(monkeypatch):
    """Verify that any prospective label or prospective scoring flag during staging forces verdict to FAIL."""
    from coin_behavior_engine.shadow_v080.prediction_store import ImmutablePredictionStoreV080, ShadowPredictionEvent

    prospective_ev = ShadowPredictionEvent(
        event_id="PROSPECTIVE-ILLEGAL-PRED",
        experiment_id="test",
        protocol_version="1.0",
        candidate_branch="candidate_c",
        forecast_origin_utc="2026-10-09T00:00:00Z",
        durable_commit_time_utc="2026-10-09T00:00:00Z",
        target_horizon="1h",
        target_maturity_utc="2026-10-09T01:00:00Z",
        feature_fingerprint="abc",
        component_hashes={},
        data_quality={"eligible_for_prospective_scoring": True},
        point_prediction=0.0,
        interval_80={},
        interval_95={},
        market_state="STABLE",
        record_label="PROSPECTIVE_SHADOW",
    )

    def mock_list(self):
        evs = self._unmatured_events.copy()
        evs.append(prospective_ev)
        return evs

    monkeypatch.setattr(ImmutablePredictionStoreV080, "list_events", mock_list)

    with tempfile.TemporaryDirectory() as tmp_dir:
        res = run_staging_benchmark(
            output_dir=Path(tmp_dir),
            warmup_bars=20,
            steady_state_cycles=20,
            rss_budget_mb=300.0,
        )

        assert res["benchmark_verdict"]["status"] == "FAIL"
        assert "PROSPECTIVE_GUARD_BREACH" in res["benchmark_verdict"]["blocking_failure_reasons"]
        assert res["mandatory_gates"]["gate_prospective_guard"]["passed"] is False
        assert res["safety_and_provenance_evidence"]["prospective_guard_intact"] is False


def test_09_restart_recovery_failure_produces_fail(monkeypatch):
    """Verify that a corrupted or incomplete restart state restoration forces verdict to FAIL."""
    from coin_behavior_engine.shadow_v080.collector import ShadowCollectorV080

    orig_init = ShadowCollectorV080.initialize
    init_call_count = 0

    def mock_init(self):
        nonlocal init_call_count
        init_call_count += 1
        res = orig_init(self)
        if init_call_count >= 2:
            # Simulate corrupted buffer on cold restart
            self.feature_pipeline.adapter.buffer.clear()
        return res

    monkeypatch.setattr(ShadowCollectorV080, "initialize", mock_init)

    with tempfile.TemporaryDirectory() as tmp_dir:
        res = run_staging_benchmark(
            output_dir=Path(tmp_dir),
            warmup_bars=20,
            steady_state_cycles=20,
            rss_budget_mb=300.0,
        )

        assert res["benchmark_verdict"]["status"] == "FAIL"
        assert "RESTART_RECOVERY_FAIL" in res["benchmark_verdict"]["blocking_failure_reasons"]
        assert res["mandatory_gates"]["gate_restart_recovery"]["passed"] is False

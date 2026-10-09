"""Sprint 09.13 / Approval 2 — Coolify Isolated Deployment Readiness Test Suite.

Verifies:
1. Canonical 29/29 production freeze integrity.
2. Complete security and resource specifications in docker-compose.coolify-inert.yaml.
3. Fail-closed behavior on missing or unauthorized safety configurations (trading, prospective, binance, database).
4. Network isolation and filesystem immutability invariants.
5. Inert landing execution (zero collection, zero prediction, zero trading, exit code 0).
6. Total isolation from CBE-0.7.0 production resources.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze
from coin_behavior_engine.shadow_v080.deploy_safety import (
    run_inert_landing_audit,
    verify_coolify_inert_contract,
)


def test_01_canonical_freeze_verified():
    """Verify 29/29 canonical Sprint 07 frozen artifacts remain untouched."""
    res = verify_sprint07_freeze(raise_on_error=False)
    assert res.get("verified") is True
    assert res.get("status") == "FREEZE_VERIFIED"
    assert res.get("canonical_hashes_verified") == 29


def test_02_coolify_compose_security_and_resource_constraints():
    """Verify all mandatory isolation and resource controls in docker-compose.coolify-inert.yaml."""
    compose_path = Path("deploy/shadow_v080/docker-compose.coolify-inert.yaml")
    assert compose_path.exists(), "Missing docker-compose.coolify-inert.yaml"

    with open(compose_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    svc = spec["services"]["cbe-080-shadow-inert"]

    # 1. Isolation & Security
    assert svc["network_mode"] == "none", "network_mode must be 'none'"
    assert svc["read_only"] is True, "read_only must be true"
    assert svc["restart"] == "no", "restart must be 'no'"
    assert svc["user"] == "1000:1000", "user must be non-root (1000:1000)"
    assert svc["profiles"] == ["manual"], "profile must be manual only"
    assert any("/tmp" in str(t) for t in svc["tmpfs"]), "tmpfs must be configured for /tmp"

    # 2. Resource limits
    assert svc["mem_limit"] == "300m", "mem_limit must be 300m"
    assert svc["memswap_limit"] == "300m", "swap must not exceed memory limit"
    assert svc["cpus"] == 0.25, "cpus quota must be 0.25"
    assert svc["pids_limit"] == 64, "pids_limit must be 64"

    # 3. Log bounds
    logging_cfg = svc.get("logging", {})
    assert logging_cfg.get("driver") == "json-file"
    assert logging_cfg.get("options", {}).get("max-size") == "10m"
    assert logging_cfg.get("options", {}).get("max-file") == "3"

    # 4. Environment safety interlocks
    env_vars = dict(e.split("=", 1) for e in svc["environment"])
    assert env_vars.get("CBE_TRADING_DISABLED") == "true"
    assert env_vars.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED") == "false"
    assert env_vars.get("CBE_BINANCE_COLLECTION_ENABLED") == "false"
    assert env_vars.get("CBE_RECORD_LABEL") == "WARMUP_REPLAY"
    assert env_vars.get("CBE_ENFORCE_PROSPECTIVE_GUARD") == "true"

    # 5. Production Volume Isolation
    for vol in svc.get("volumes", []):
        host_src = vol.split(":")[0]
        assert "cbe_080_shadow_data" in host_src, "Volume source must be isolated cbe_080_shadow_data"
        assert not host_src.endswith("data/prospective"), "Cannot mount production data/prospective as source"
        assert "database" not in vol, "Cannot mount database volumes"


def test_03_inert_verification_passes_with_safe_defaults(monkeypatch):
    """Verify that safety contract passes when default safe environment is present."""
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")

    # In local test environment, probe_network=False to test logical safety contract
    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False)
    assert res.status == "PASS"
    assert res.lifecycle_state == "DEPLOYED_INERT"
    assert res.trading_disabled is True
    assert res.prospective_scoring_disabled is True
    assert res.binance_collection_disabled is True
    assert len(res.violations) == 0


def test_04_fail_closed_if_trading_enabled(monkeypatch):
    """Verify that attempting to enable trading forces verdict to FAIL and FAILED_SAFE state."""
    monkeypatch.setenv("CBE_TRADING_DISABLED", "false")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")

    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert any("TRADING_NOT_DISABLED" in v for v in res.violations)


def test_05_fail_closed_if_prospective_enabled_without_approval_4(monkeypatch):
    """Verify that attempting to enable prospective scoring forces verdict to FAIL and FAILED_SAFE."""
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "true")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")

    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert any("PROSPECTIVE_UNAUTHORIZED" in v for v in res.violations)


def test_06_fail_closed_if_binance_enabled_without_approval_3(monkeypatch):
    """Verify that attempting to enable Binance collection forces verdict to FAIL and FAILED_SAFE."""
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")

    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert any("BINANCE_COLLECTION_UNAUTHORIZED" in v for v in res.violations)


def test_07_fail_closed_if_production_database_credentials_present(monkeypatch):
    """Verify that presence of database credentials forces verdict to FAIL and FAILED_SAFE."""
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@db:5432/cbe_prod")

    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert any("UNAUTHORIZED_CREDENTIAL_PRESENT" in v for v in res.violations)


def test_08_fail_closed_on_network_isolation_breach(monkeypatch):
    """Verify that an active socket connect forces verdict to FAIL and logs NETWORK_ISOLATION_BREACH."""
    import socket

    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")

    # Mock socket connect_ex returning 0 (connection succeeded)
    def mock_connect_ex(self, address):
        return 0

    monkeypatch.setattr(socket.socket, "connect_ex", mock_connect_ex)

    res = verify_coolify_inert_contract(probe_network=True, check_filesystem=False)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert res.network_isolated is False
    assert any("NETWORK_ISOLATION_BREACH" in v for v in res.violations)


def test_09_inert_landing_audit_writes_audit_file(monkeypatch, tmp_path):
    """Verify run_inert_landing_audit generates audit JSON and exits cleanly with 0."""
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")

    # Mock probe_network to avoid live network query during test
    import coin_behavior_engine.shadow_v080.deploy_safety as ds

    orig_verify = ds.verify_coolify_inert_contract

    def mock_verify(*args, **kwargs):
        return orig_verify(probe_network=False, check_filesystem=False)

    monkeypatch.setattr(ds, "verify_coolify_inert_contract", mock_verify)

    exit_code = run_inert_landing_audit(output_dir=tmp_path)
    assert exit_code == 0

    audit_file = tmp_path / "audit" / "coolify_inert_landing_audit.json"
    assert audit_file.exists()

    import json

    audit_data = json.loads(audit_file.read_text(encoding="utf-8"))
    assert audit_data["status"] == "PASS"
    assert audit_data["lifecycle_state"] == "DEPLOYED_INERT"
    assert audit_data["trading_disabled"] is True
    assert audit_data["prospective_scoring_disabled"] is True
    assert audit_data["binance_collection_disabled"] is True


def test_10_no_continuous_collector_or_auto_deploy():
    """Verify that no auto-deploy or background cron hooks exist in deployment configurations."""
    compose_path = Path("deploy/shadow_v080/docker-compose.coolify-inert.yaml")
    content = compose_path.read_text(encoding="utf-8")

    assert 'restart: "no"' in content
    assert 'profiles: ["manual"]' in content
    assert "cron" not in content.lower()
    assert "celery" not in content.lower()
    assert "daemon" not in content.lower()

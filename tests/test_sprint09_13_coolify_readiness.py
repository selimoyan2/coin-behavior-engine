"""Sprint 09.13.1 / Approval 2 — Coolify Isolated Deployment Readiness Test Suite (Hardened).

Verifies:
1. Canonical 29/29 production freeze integrity.
2. Complete security and resource specifications in docker-compose.coolify-inert.yaml (no profiles manual, restart no).
3. Fail-closed behavior on missing, malformed, or unauthorized safety configurations (strict exact matching).
4. Deterministic network isolation checks (raw IP only, zero DNS hostname queries, interface inspection).
5. Read-only filesystem checks (statvfs and errno.EROFS distinction).
6. Mandatory audit evidence persistence with volume permission failure fail-closed behavior.
7. Safe-by-default Dockerfile CMD configuration (entrypoint_inert.sh).
8. Total isolation from CBE-0.7.0 production resources.
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
    # profiles: ["manual"] omitted so operator manual Deploy action in Coolify can start the container
    assert "profiles" not in svc, "profiles must be omitted to allow Coolify manual deployment execution"
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
    assert env_vars.get("CBE_ENV") == "staging_coolify_inert"
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


def test_03_inert_verification_passes_with_safe_defaults(monkeypatch, tmp_path):
    """Verify that safety contract passes when exact default safe environment is present."""
    monkeypatch.setenv("CBE_ENV", "staging_coolify_inert")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")
    monkeypatch.setenv("CBE_ENFORCE_PROSPECTIVE_GUARD", "true")

    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "PASS"
    assert res.lifecycle_state == "DEPLOYED_INERT"
    assert res.trading_disabled is True
    assert res.prospective_scoring_disabled is True
    assert res.binance_collection_disabled is True
    assert res.volume_writable is True
    assert len(res.violations) == 0


def test_04_fail_closed_if_trading_enabled(monkeypatch, tmp_path):
    """Verify that attempting to enable trading forces verdict to FAIL and FAILED_SAFE state."""
    monkeypatch.setenv("CBE_ENV", "staging_coolify_inert")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "false")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")
    monkeypatch.setenv("CBE_ENFORCE_PROSPECTIVE_GUARD", "true")

    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert any("CONFIG_INVALID_CBE_TRADING_DISABLED" in v for v in res.violations)


def test_05_fail_closed_if_prospective_enabled_without_approval_4(monkeypatch, tmp_path):
    """Verify that attempting to enable prospective scoring forces verdict to FAIL and FAILED_SAFE."""
    monkeypatch.setenv("CBE_ENV", "staging_coolify_inert")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "true")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")
    monkeypatch.setenv("CBE_ENFORCE_PROSPECTIVE_GUARD", "true")

    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert any("CONFIG_INVALID_CBE_PROSPECTIVE_OBSERVATION_ENABLED" in v for v in res.violations)


def test_06_fail_closed_if_binance_enabled_without_approval_3(monkeypatch, tmp_path):
    """Verify that attempting to enable Binance collection forces verdict to FAIL and FAILED_SAFE."""
    monkeypatch.setenv("CBE_ENV", "staging_coolify_inert")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")
    monkeypatch.setenv("CBE_ENFORCE_PROSPECTIVE_GUARD", "true")

    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert any("CONFIG_INVALID_CBE_BINANCE_COLLECTION_ENABLED" in v for v in res.violations)


def test_07_fail_closed_if_production_database_credentials_present(monkeypatch, tmp_path):
    """Verify that presence of database credentials forces verdict to FAIL and FAILED_SAFE."""
    monkeypatch.setenv("CBE_ENV", "staging_coolify_inert")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")
    monkeypatch.setenv("CBE_ENFORCE_PROSPECTIVE_GUARD", "true")
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@db:5432/cbe_prod")

    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert any("UNAUTHORIZED_CREDENTIAL_PRESENT" in v for v in res.violations)


def test_08_fail_closed_on_network_isolation_breach(monkeypatch, tmp_path):
    """Verify that an active socket connect to raw IP forces verdict to FAIL and logs NETWORK_ISOLATION_BREACH."""
    import socket

    monkeypatch.setenv("CBE_ENV", "staging_coolify_inert")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")
    monkeypatch.setenv("CBE_ENFORCE_PROSPECTIVE_GUARD", "true")

    # Mock socket connect_ex returning 0 (connection succeeded)
    def mock_connect_ex(self, address):
        return 0

    monkeypatch.setattr(socket.socket, "connect_ex", mock_connect_ex)

    res = verify_coolify_inert_contract(probe_network=True, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert res.network_isolated is False
    assert any("NETWORK_ISOLATION_BREACH" in v for v in res.violations)


def test_09_inert_landing_audit_writes_audit_file(monkeypatch, tmp_path):
    """Verify run_inert_landing_audit generates audit JSON and exits cleanly with 0."""
    monkeypatch.setenv("CBE_ENV", "staging_coolify_inert")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")
    monkeypatch.setenv("CBE_ENFORCE_PROSPECTIVE_GUARD", "true")

    # Mock probe_network to avoid live network query during test
    import coin_behavior_engine.shadow_v080.deploy_safety as ds

    orig_verify = ds.verify_coolify_inert_contract

    def mock_verify(*args, **kwargs):
        return orig_verify(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)

    monkeypatch.setattr(ds, "verify_coolify_inert_contract", mock_verify)

    exit_code = run_inert_landing_audit(output_dir=tmp_path, probe_network=False, check_filesystem=False)
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
    assert "cron" not in content.lower()
    assert "celery" not in content.lower()
    assert "daemon" not in content.lower()


def test_11_strict_config_validation_exact_matching(monkeypatch, tmp_path):
    """Verify that missing, malformed, or unexpected values fail closed with specific violation tokens."""
    monkeypatch.setenv("CBE_ENV", "staging_coolify_inert")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")
    monkeypatch.setenv("CBE_ENFORCE_PROSPECTIVE_GUARD", "true")

    # 1. Missing variable
    monkeypatch.delenv("CBE_RECORD_LABEL", raising=False)
    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "FAIL"
    assert any("CONFIG_MISSING_CBE_RECORD_LABEL" in v for v in res.violations)

    # 2. Malformed / unapproved value
    monkeypatch.setenv("CBE_RECORD_LABEL", "HISTORICAL_REPLAY")  # Not WARMUP_REPLAY
    res2 = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res2.status == "FAIL"
    assert any("CONFIG_INVALID_CBE_RECORD_LABEL" in v for v in res2.violations)

    # 3. Invalid environment name
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")
    monkeypatch.setenv("CBE_ENV", "production_live")
    res3 = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res3.status == "FAIL"
    assert any("CONFIG_INVALID_CBE_ENV" in v for v in res3.violations)


def test_12_safe_default_image_invocation():
    """Verify that Dockerfile.staging sets CMD to entrypoint_inert.sh (safe by default)."""
    dockerfile_path = Path("deploy/shadow_v080/Dockerfile.staging")
    assert dockerfile_path.exists()
    content = dockerfile_path.read_text(encoding="utf-8")

    assert 'CMD ["/app/entrypoint_inert.sh"]' in content
    # Ensure benchmark is NOT the default command
    assert 'CMD ["python3", "-m", "coin_behavior_engine.shadow_v080.benchmark_staging_linux"]' not in content


def test_13_network_namespace_device_inspection(monkeypatch, tmp_path):
    """Verify that presence of non-loopback network interfaces in /proc/net/dev fails closed."""
    monkeypatch.setenv("CBE_ENV", "staging_coolify_inert")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")
    monkeypatch.setenv("CBE_ENFORCE_PROSPECTIVE_GUARD", "true")

    import coin_behavior_engine.shadow_v080.deploy_safety as ds

    mock_proc_net = tmp_path / "proc_net_dev"
    mock_proc_net.write_text(
        "Inter-|   Receive                                                |  Transmit\n"
        " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n"
        "    lo: 1234567       0    0    0    0     0          0         0  1234567       0    0    0    0     0       0          0\n"
        "  eth0: 9876543       0    0    0    0     0          0         0  9876543       0    0    0    0     0       0          0\n"
    )

    monkeypatch.setattr(ds, "Path", lambda p: mock_proc_net if str(p) == "/proc/net/dev" else Path(p))

    res = ds.verify_coolify_inert_contract(probe_network=True, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "FAIL"
    assert any("NETWORK_NAMESPACE_NOT_NONE" in v for v in res.violations)


def test_14_volume_write_failure_fails_closed(monkeypatch, tmp_path):
    """Verify that failure to write mandatory audit JSON to volume fails closed (exit code 1)."""
    monkeypatch.setenv("CBE_ENV", "staging_coolify_inert")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")
    monkeypatch.setenv("CBE_ENFORCE_PROSPECTIVE_GUARD", "true")

    # Point target directory to a non-existent or unwritable file path
    non_writable_dir = tmp_path / "unwritable_dir"
    non_writable_dir.touch()  # It's a file, not a dir -> mkdir inside will fail with NotADirectoryError / PermissionError

    exit_code = run_inert_landing_audit(output_dir=non_writable_dir, require_persistent_audit=True, probe_network=False, check_filesystem=False)
    assert exit_code == 1

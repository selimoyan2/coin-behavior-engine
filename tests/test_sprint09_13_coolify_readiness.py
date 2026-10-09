"""Sprint 09.13.2 / Approval 2 — Coolify Isolated Deployment Readiness Test Suite (Final Hardened).

Covers all 17 required regression test scenarios:
1. Canonical 29/29 production freeze integrity.
2. Complete security and resource specifications in docker-compose.coolify-inert.yaml.
3. Safe defaults contract verification.
4. Trading interlock fail-closed.
5. Prospective observation fail-closed.
6. Binance collection fail-closed.
7. Database credential isolation fail-closed.
8. Raw-IP socket breach fail-closed.
9. Inert landing audit persistence (latest JSON + bounded history JSONL).
10. Absence of continuous daemons/cron.
11. Strict exact configuration matching.
12. Safe-by-default image CMD configuration.
13. Missing /proc/net/dev fails closed.
14. Unreadable /proc/net/dev fails closed.
15. Malformed network interface evidence fails closed.
16. Unexpected eth0 non-loopback interface fails closed.
17. Valid loopback-only interface evidence passes.
18. Missing /proc/mounts fails closed.
19. Unreadable /proc/mounts fails closed.
20. Writable root with DAC permission denial fails closed.
21. Contradictory statvfs and /proc/mounts evidence fails closed.
22. Genuine read-only root filesystem passes.
23. New writable volume and existing owned volume pass.
24. Root-owned inaccessible volume fails closed.
25. Read-only volume fails closed.
26. Failed mandatory audit write fails closed.
27. Repeated audit without evidence corruption & bounded retention.
"""

from __future__ import annotations

import errno
import json
import os
import socket
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml

from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze
from coin_behavior_engine.shadow_v080.deploy_safety import (
    MAX_AUDIT_HISTORY_ENTRIES,
    run_inert_landing_audit,
    verify_coolify_inert_contract,
)


@pytest.fixture(autouse=True)
def safe_env(monkeypatch):
    """Ensure safe base environment for all tests."""
    monkeypatch.setenv("CBE_ENV", "staging_coolify_inert")
    monkeypatch.setenv("CBE_TRADING_DISABLED", "true")
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false")
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "false")
    monkeypatch.setenv("CBE_RECORD_LABEL", "WARMUP_REPLAY")
    monkeypatch.setenv("CBE_ENFORCE_PROSPECTIVE_GUARD", "true")


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

    build_cfg = svc.get("build", {})
    assert build_cfg.get("context") == ".", "build context must be '.' for Coolify --project-directory resolution"
    assert build_cfg.get("dockerfile") == "deploy/shadow_v080/Dockerfile.staging", "dockerfile must point to deploy/shadow_v080/Dockerfile.staging"

    assert svc["network_mode"] == "none", "network_mode must be 'none'"
    assert svc["read_only"] is True, "read_only must be true"
    assert svc["restart"] == "no", "restart must be 'no'"
    assert svc["user"] == "1000:1000", "user must be non-root (1000:1000)"
    assert "profiles" not in svc, "profiles must be omitted to allow Coolify manual deployment execution"
    assert any("/tmp" in str(t) for t in svc["tmpfs"]), "tmpfs must be configured for /tmp"
    assert svc["mem_limit"] == "300m", "mem_limit must be 300m"
    assert svc["memswap_limit"] == "300m", "swap must not exceed memory limit"
    assert svc["cpus"] == 0.25, "cpus quota must be 0.25"
    assert svc["pids_limit"] == 64, "pids_limit must be 64"

    logging_cfg = svc.get("logging", {})
    assert logging_cfg.get("driver") == "json-file"
    assert logging_cfg.get("options", {}).get("max-size") == "10m"
    assert logging_cfg.get("options", {}).get("max-file") == "3"

    env_vars = dict(e.split("=", 1) for e in svc["environment"])
    assert env_vars.get("CBE_ENV") == "staging_coolify_inert"
    assert env_vars.get("CBE_TRADING_DISABLED") == "true"
    assert env_vars.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED") == "false"
    assert env_vars.get("CBE_BINANCE_COLLECTION_ENABLED") == "false"
    assert env_vars.get("CBE_RECORD_LABEL") == "WARMUP_REPLAY"
    assert env_vars.get("CBE_ENFORCE_PROSPECTIVE_GUARD") == "true"

    for vol in svc.get("volumes", []):
        host_src = vol.split(":")[0]
        assert "cbe_080_shadow_data" in host_src, "Volume source must be isolated cbe_080_shadow_data"
        assert not host_src.endswith("data/prospective"), "Cannot mount production data/prospective as source"
        assert "database" not in vol, "Cannot mount database volumes"


def test_03_inert_verification_passes_with_safe_defaults(tmp_path):
    """Verify that safety contract passes when exact default safe environment is present."""
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
    monkeypatch.setenv("CBE_TRADING_DISABLED", "false")
    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert any("CONFIG_INVALID_CBE_TRADING_DISABLED" in v for v in res.violations)


def test_05_fail_closed_if_prospective_enabled_without_approval_4(monkeypatch, tmp_path):
    """Verify that attempting to enable prospective scoring forces verdict to FAIL and FAILED_SAFE."""
    monkeypatch.setenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "true")
    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert any("CONFIG_INVALID_CBE_PROSPECTIVE_OBSERVATION_ENABLED" in v for v in res.violations)


def test_06_fail_closed_if_binance_enabled_without_approval_3(monkeypatch, tmp_path):
    """Verify that attempting to enable Binance collection forces verdict to FAIL and FAILED_SAFE."""
    monkeypatch.setenv("CBE_BINANCE_COLLECTION_ENABLED", "true")
    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert any("CONFIG_INVALID_CBE_BINANCE_COLLECTION_ENABLED" in v for v in res.violations)


def test_07_fail_closed_if_production_database_credentials_present(monkeypatch, tmp_path):
    """Verify that presence of database credentials forces verdict to FAIL and FAILED_SAFE."""
    monkeypatch.setenv("DATABASE_URL", "postgres://user:pass@db:5432/cbe_prod")
    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert any("UNAUTHORIZED_CREDENTIAL_PRESENT" in v for v in res.violations)


def test_08_fail_closed_on_raw_ip_socket_breach(monkeypatch, tmp_path):
    """Verify that an active socket connect to raw IP forces verdict to FAIL and logs NETWORK_ISOLATION_BREACH."""
    import socket

    def mock_connect_ex(self, address):
        return 0

    monkeypatch.setattr(socket.socket, "connect_ex", mock_connect_ex)

    res = verify_coolify_inert_contract(probe_network=True, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "FAIL"
    assert res.lifecycle_state == "FAILED_SAFE"
    assert res.network_isolated is False
    assert any("NETWORK_ISOLATION_BREACH" in v for v in res.violations)


def test_09_inert_landing_audit_writes_audit_file(monkeypatch, tmp_path):
    """Verify run_inert_landing_audit generates latest audit JSON and history JSONL and exits 0."""
    exit_code = run_inert_landing_audit(output_dir=tmp_path, probe_network=False, check_filesystem=False)
    assert exit_code == 0

    audit_file = tmp_path / "audit" / "coolify_inert_landing_audit.json"
    history_file = tmp_path / "audit" / "coolify_inert_landing_history.jsonl"
    assert audit_file.exists()
    assert history_file.exists()

    audit_data = json.loads(audit_file.read_text(encoding="utf-8"))
    assert audit_data["status"] == "PASS"
    assert audit_data["lifecycle_state"] == "DEPLOYED_INERT"
    assert "landing_id" in audit_data
    assert "record_sha256" in audit_data

    history_lines = history_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(history_lines) == 1


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
    monkeypatch.delenv("CBE_RECORD_LABEL", raising=False)
    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res.status == "FAIL"
    assert any("CONFIG_MISSING_CBE_RECORD_LABEL" in v for v in res.violations)

    monkeypatch.setenv("CBE_RECORD_LABEL", "HISTORICAL_REPLAY")
    res2 = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=tmp_path)
    assert res2.status == "FAIL"
    assert any("CONFIG_INVALID_CBE_RECORD_LABEL" in v for v in res2.violations)

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
    assert 'CMD ["python3", "-m", "coin_behavior_engine.shadow_v080.benchmark_staging_linux"]' not in content


def test_13_missing_proc_net_dev_fails_closed(tmp_path):
    """Verify that missing /proc/net/dev evidence in container fails closed."""
    non_existent = tmp_path / "proc_net_missing"
    res = verify_coolify_inert_contract(
        probe_network=True,
        check_filesystem=False,
        target_data_dir=tmp_path,
        proc_net_dev_path=non_existent,
        is_container=True,
    )
    assert res.status == "FAIL"
    assert any("NETWORK_EVIDENCE_MISSING" in v for v in res.violations)


def test_14_unreadable_proc_net_dev_fails_closed(monkeypatch, tmp_path):
    """Verify that unreadable /proc/net/dev fails closed."""
    dev_path = tmp_path / "unreadable_net_dev"
    dev_path.touch()

    # Mock read_text raising OSError
    def mock_read(self, *args, **kwargs):
        raise OSError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(Path, "read_text", mock_read)

    res = verify_coolify_inert_contract(
        probe_network=True,
        check_filesystem=False,
        target_data_dir=tmp_path,
        proc_net_dev_path=dev_path,
        is_container=True,
    )
    assert res.status == "FAIL"
    assert any("NETWORK_EVIDENCE_UNREADABLE" in v for v in res.violations)


def test_15_malformed_proc_net_dev_fails_closed(tmp_path):
    """Verify that malformed or empty /proc/net/dev fails closed."""
    malformed = tmp_path / "malformed_net_dev"
    malformed.write_text("invalid content without header\n", encoding="utf-8")

    res = verify_coolify_inert_contract(
        probe_network=True,
        check_filesystem=False,
        target_data_dir=tmp_path,
        proc_net_dev_path=malformed,
        is_container=True,
    )
    assert res.status == "FAIL"
    assert any("NETWORK_EVIDENCE_MALFORMED" in v for v in res.violations)


def test_16_unexpected_non_loopback_interface_fails_closed(tmp_path):
    """Verify that presence of non-loopback network interface (e.g. eth0) fails closed."""
    mock_dev = tmp_path / "proc_net_eth0"
    mock_dev.write_text(
        "Inter-|   Receive                                                |  Transmit\n"
        " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n"
        "    lo: 1234567       0    0    0    0     0          0         0  1234567       0    0    0    0     0       0          0\n"
        "  eth0: 9876543       0    0    0    0     0          0         0  9876543       0    0    0    0     0       0          0\n",
        encoding="utf-8",
    )

    res = verify_coolify_inert_contract(
        probe_network=True,
        check_filesystem=False,
        target_data_dir=tmp_path,
        proc_net_dev_path=mock_dev,
        is_container=True,
    )
    assert res.status == "FAIL"
    assert any("NETWORK_NAMESPACE_NOT_NONE" in v for v in res.violations)


def test_17_valid_loopback_only_interface_passes(monkeypatch, tmp_path):
    """Verify that valid loopback-only network evidence passes with LOOPBACK_ONLY check."""
    mock_dev = tmp_path / "proc_net_lo"
    mock_dev.write_text(
        "Inter-|   Receive                                                |  Transmit\n"
        " face |bytes    packets errs drop fifo frame compressed multicast|bytes    packets errs drop fifo colls carrier compressed\n"
        "    lo: 1234567       0    0    0    0     0          0         0  1234567       0    0    0    0     0       0          0\n",
        encoding="utf-8",
    )

    # Mock socket connect_ex to simulate network unreachable (offline)
    monkeypatch.setattr(socket.socket, "connect_ex", lambda self, addr: errno.ENETUNREACH)

    res = verify_coolify_inert_contract(
        probe_network=True,
        check_filesystem=False,
        target_data_dir=tmp_path,
        proc_net_dev_path=mock_dev,
        is_container=True,
    )
    assert res.status == "PASS"
    assert res.metadata["network_details"]["interface_check"] == "LOOPBACK_ONLY"


def test_18_missing_proc_mounts_fails_closed(tmp_path):
    """Verify that missing /proc/mounts in container fails closed."""
    missing_mounts = tmp_path / "missing_mounts"
    res = verify_coolify_inert_contract(
        probe_network=False,
        check_filesystem=True,
        target_data_dir=tmp_path,
        proc_mounts_path=missing_mounts,
        is_container=True,
    )
    assert res.status == "FAIL"
    assert any("FILESYSTEM_EVIDENCE_MISSING" in v for v in res.violations)


def test_19_unreadable_proc_mounts_fails_closed(monkeypatch, tmp_path):
    """Verify that unreadable /proc/mounts in container fails closed."""
    unreadable = tmp_path / "unreadable_mounts"
    unreadable.touch()

    def mock_read(self, *args, **kwargs):
        raise OSError(errno.EACCES, "Permission denied")

    monkeypatch.setattr(Path, "read_text", mock_read)

    res = verify_coolify_inert_contract(
        probe_network=False,
        check_filesystem=True,
        target_data_dir=tmp_path,
        proc_mounts_path=unreadable,
        is_container=True,
    )
    assert res.status == "FAIL"
    assert any("FILESYSTEM_EVIDENCE_UNREADABLE" in v for v in res.violations)


def test_20_writable_root_with_dac_permission_denial_fails_closed(tmp_path):
    """Verify that a root filesystem mounted rw fails closed even if probe fails with EACCES."""
    rw_mounts = tmp_path / "rw_mounts"
    rw_mounts.write_text("overlay / overlay rw,relatime 0 0\n", encoding="utf-8")

    # Mock statvfs returning rw
    mock_st = MagicMock(f_flag=0)  # ST_RDONLY is not set

    res = verify_coolify_inert_contract(
        probe_network=False,
        check_filesystem=True,
        target_data_dir=tmp_path,
        proc_mounts_path=rw_mounts,
        statvfs_func=lambda p: mock_st,
        is_container=True,
    )
    assert res.status == "FAIL"
    assert any("FILESYSTEM_NOT_MOUNTED_RO" in v for v in res.violations)


def test_21_contradictory_mount_and_statvfs_evidence_fails_closed(tmp_path):
    """Verify that contradictory mount options vs statvfs flags fails closed."""
    ro_mounts = tmp_path / "ro_mounts"
    ro_mounts.write_text("overlay / overlay ro,relatime 0 0\n", encoding="utf-8")

    # Mock statvfs returning rw (contradicting mounts ro)
    mock_st = MagicMock(f_flag=0)

    res = verify_coolify_inert_contract(
        probe_network=False,
        check_filesystem=True,
        target_data_dir=tmp_path,
        proc_mounts_path=ro_mounts,
        statvfs_func=lambda p: mock_st,
        is_container=True,
    )
    assert res.status == "FAIL"
    assert any("FILESYSTEM_MOUNT_EVIDENCE_CONTRADICTORY" in v for v in res.violations)


def test_22_genuine_read_only_root_filesystem_passes(tmp_path):
    """Verify that genuine read-only mount options and statvfs ST_RDONLY pass."""
    ro_mounts = tmp_path / "ro_mounts_ok"
    ro_mounts.write_text("overlay / overlay ro,relatime 0 0\n", encoding="utf-8")

    mock_st = MagicMock(f_flag=1)  # ST_RDONLY flag set

    def mock_write_probe():
        raise OSError(errno.EROFS, "Read-only file system")

    res = verify_coolify_inert_contract(
        probe_network=False,
        check_filesystem=True,
        target_data_dir=tmp_path,
        proc_mounts_path=ro_mounts,
        statvfs_func=lambda p: mock_st,
        write_probe_func=mock_write_probe,
        is_container=True,
    )
    assert res.status == "PASS"
    assert res.metadata["filesystem_details"]["root_mount_is_ro"] is True
    assert res.metadata["filesystem_details"]["is_mount_statvfs_ro"] is True


def test_23_new_writable_volume_and_existing_owned_volume_passes(tmp_path):
    """Verify that a newly created or existing correctly owned volume passes."""
    vol_dir = tmp_path / "new_vol"
    res1 = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=vol_dir)
    assert res1.status == "PASS"
    assert res1.volume_writable is True

    # Existing volume
    res2 = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=vol_dir)
    assert res2.status == "PASS"
    assert res2.volume_writable is True


def test_24_root_owned_inaccessible_volume_fails_closed(monkeypatch, tmp_path):
    """Verify that a root-owned volume with permission denial fails closed with VOLUME_PERMISSION_DENIED."""
    vol_dir = tmp_path / "root_vol"
    vol_dir.mkdir()

    orig_write = Path.write_text

    def mock_write_text(self, *args, **kwargs):
        if ".volume_perm_check" in str(self):
            raise OSError(errno.EACCES, "Permission denied")
        return orig_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", mock_write_text)

    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=vol_dir)
    assert res.status == "FAIL"
    assert res.volume_writable is False
    assert any("VOLUME_PERMISSION_DENIED" in v for v in res.violations)


def test_25_read_only_volume_fails_closed(monkeypatch, tmp_path):
    """Verify that a volume mistakenly mounted :ro fails closed with VOLUME_MOUNT_READ_ONLY."""
    vol_dir = tmp_path / "ro_vol"
    vol_dir.mkdir()

    orig_write = Path.write_text

    def mock_write_text(self, *args, **kwargs):
        if ".volume_perm_check" in str(self):
            raise OSError(errno.EROFS, "Read-only file system")
        return orig_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", mock_write_text)

    res = verify_coolify_inert_contract(probe_network=False, check_filesystem=False, target_data_dir=vol_dir)
    assert res.status == "FAIL"
    assert res.volume_writable is False
    assert any("VOLUME_MOUNT_READ_ONLY" in v for v in res.violations)


def test_26_failed_mandatory_audit_write_fails_closed(tmp_path):
    """Verify that failure to persist mandatory audit JSON terminates with exit code 1."""
    non_writable_file = tmp_path / "blocker_file"
    non_writable_file.touch()

    exit_code = run_inert_landing_audit(
        output_dir=non_writable_file,
        require_persistent_audit=True,
        probe_network=False,
        check_filesystem=False,
    )
    assert exit_code == 1


def test_27_repeated_audit_without_evidence_corruption_and_bounded_retention(tmp_path):
    """Verify repeated audits maintain append-only history without corrupting earlier runs and bound growth."""
    # Run audit 3 times
    for i in range(3):
        exit_code = run_inert_landing_audit(
            output_dir=tmp_path,
            require_persistent_audit=True,
            probe_network=False,
            check_filesystem=False,
        )
        assert exit_code == 0

    history_file = tmp_path / "audit" / "coolify_inert_landing_history.jsonl"
    assert history_file.exists()

    lines = history_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3

    # Verify each entry has unique landing_id
    records = [json.loads(l) for l in lines]
    landing_ids = [r["landing_id"] for r in records]
    assert len(set(landing_ids)) == 3, "Each landing entry must have unique landing_id"

    # Verify latest audit file matches the third run
    latest_file = tmp_path / "audit" / "coolify_inert_landing_audit.json"
    latest_data = json.loads(latest_file.read_text(encoding="utf-8"))
    assert latest_data["landing_id"] == landing_ids[2]

    # Test bounded pruning
    fake_lines = [json.dumps({"landing_id": f"GENESIS-{i}"}) for i in range(MAX_AUDIT_HISTORY_ENTRIES + 10)]
    history_file.write_text("\n".join(fake_lines) + "\n", encoding="utf-8")

    # Run audit once more
    run_inert_landing_audit(
        output_dir=tmp_path,
        require_persistent_audit=True,
        probe_network=False,
        check_filesystem=False,
    )

    pruned_lines = history_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(pruned_lines) <= MAX_AUDIT_HISTORY_ENTRIES + 1
    # Verify genesis entry (line 0) was preserved
    assert "GENESIS-0" in pruned_lines[0]


def test_28_coolify_build_context_and_dockerfile_resolution():
    """Verify that build context and Dockerfile resolve correctly under Coolify project-directory semantics."""
    compose_path = Path("deploy/shadow_v080/docker-compose.coolify-inert.yaml")
    with open(compose_path, "r", encoding="utf-8") as f:
        spec = yaml.safe_load(f)

    svc = spec["services"]["cbe-080-shadow-inert"]
    build_cfg = svc["build"]
    context_str = build_cfg["context"]
    dockerfile_str = build_cfg["dockerfile"]

    # In Coolify, project-directory is the repository root checkout
    repo_root = Path(__file__).resolve().parents[1]
    resolved_context = (repo_root / context_str).resolve()
    resolved_dockerfile = (resolved_context / dockerfile_str).resolve()

    assert resolved_dockerfile.exists(), f"Dockerfile does not exist at {resolved_dockerfile}"
    assert (resolved_context / "src").exists(), f"src/ missing from resolved context {resolved_context}"
    assert (resolved_context / "data" / "models").exists(), f"data/models/ missing from resolved context {resolved_context}"
    assert (resolved_context / "deploy" / "shadow_v080" / "entrypoint_inert.sh").exists(), f"entrypoint missing from {resolved_context}"


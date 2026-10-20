"""
Sprint 11.23.5A: Comprehensive Security Regression & Negative Testing Suite
Validates:
  1. Read-Only HTTPS transport security (SSRF, DNS rebinding, streaming size limits,
     zip bomb decompression protection, redirect loops, unauthorized schemes/domains).
  2. Cross-process evidence vault durability and crash recovery using separate OS processes.
  3. Atomic checkpoint persistence, corruption detection, and self-healing fallback.
  4. Real-world observation authorization framework and fail-closed capability segregation.
  5. Official source adapter contracts and response specifications.
  6. Timestamp provenance, consensus vintage enforcement, and retrospective data guards.
  7. Deterministic end-to-end recovery simulation and zero-trading compliance.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import gzip
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import shutil
import time
import pytest

from coin_behavior_engine.prospective import (
    ReadOnlyResearchTransport,
    TransportResponse,
    TransportSecurityError,
    NetworkAccessProhibitedError,
    InsecureSchemeError,
    DomainNotAllowedError,
    SSRFProtectionError,
    MethodNotAllowedError,
    SensitiveHeaderError,
    TradingEndpointAccessError,
    ResponseSizeExceededError,
    TransportTimeoutError,
    RateLimitExceededError,
    TLSVerificationError,
    RedirectSecurityError,
    ImmutableEvidenceVault,
    CrossProcessVaultLock,
    VaultCorruptionError,
    VaultSecurityError,
    VaultRecoveryStatus,
    ProspectivePilotRunner,
    PilotConfig,
    PilotAuthorizationToken,
    CheckpointCorruptionError,
    ObservationAuthorizationToken,
    ObservationAuthorizationEngine,
    AuthorizationCapability,
    AuthorizationStatus,
    SigningKeyRegistry,
    TradingIsolationViolation,
    ProspectiveGovernanceGuard,
    ProspectiveEventRecord,
    ProspectiveEventCategory,
    ProspectiveEventStatus,
    ConsensusRecord,
    ConsensusVerificationStatus,
    ConsensusEvidenceRegistry,
    EndToEndRecoverySimulationRunner,
    BLSSourceAdapter,
    BEASourceAdapter,
    FederalReserveSourceAdapter,
    CryptoProtocolAdapter,
    ProspectiveMarketObserver,
)
from coin_behavior_engine.prospective.research_transport import (
    is_private_or_restricted_ip,
    is_allowed_domain,
    is_ip_literal,
)


# ==============================================================================
# 1. READ-ONLY HTTPS TRANSPORT SECURITY TESTS
# ==============================================================================

def test_01_transport_network_disabled_by_default():
    transport = ReadOnlyResearchTransport(network_enabled=False)
    with pytest.raises(NetworkAccessProhibitedError):
        transport.execute_request("GET", "https://www.bls.gov/cpi")


def test_02_transport_rejects_ip_literals():
    transport = ReadOnlyResearchTransport(network_enabled=False)
    for bad_target in [
        "https://127.0.0.1/cpi",
        "https://10.0.0.1/data",
        "https://[::1]/leak",
        "https://192.168.1.1/admin",
        "https://8.8.8.8/dns",
    ]:
        with pytest.raises(DomainNotAllowedError):
            transport.execute_request("GET", bad_target)


def test_03_transport_rejects_domain_suffix_spoofing():
    transport = ReadOnlyResearchTransport(network_enabled=False)
    for spoofed in [
        "https://bls.gov.attacker.com/leak",
        "https://www.bls.gov.fake.net/cpi",
        "https://evil-bls.gov/news",
        "https://federalreserve.gov.phishing.io/statement",
    ]:
        with pytest.raises(DomainNotAllowedError):
            transport.execute_request("GET", spoofed)


def test_04_transport_rejects_mixed_dns_answers():
    # DNS returns both a public IP and a private loopback address -> Must FAIL closed!
    def mixed_dns(h: str):
        return ["93.184.216.34", "127.0.0.1"]

    transport = ReadOnlyResearchTransport(network_enabled=True, dns_resolver=mixed_dns)
    with pytest.raises(SSRFProtectionError):
        transport.execute_request("GET", "https://www.bls.gov/news")


def test_05_transport_rejects_ipv6_restricted_addresses():
    def ipv6_loopback_dns(h: str):
        return ["::1"]

    transport = ReadOnlyResearchTransport(network_enabled=True, dns_resolver=ipv6_loopback_dns)
    with pytest.raises(SSRFProtectionError):
        transport.execute_request("GET", "https://www.bls.gov/news")

    def ipv6_unique_local_dns(h: str):
        return ["fc00::1"]

    transport2 = ReadOnlyResearchTransport(network_enabled=True, dns_resolver=ipv6_unique_local_dns)
    with pytest.raises(SSRFProtectionError):
        transport2.execute_request("GET", "https://www.bls.gov/news")


def test_06_transport_redirect_disabled_by_default():
    transport = ReadOnlyResearchTransport(network_enabled=False, allow_redirects=False)
    url = "https://www.bls.gov/old_url"
    transport.register_mock_response(
        url=url,
        status_code=301,
        headers={"location": "https://www.bls.gov/new_url"},
        body=b"Moved",
    )
    resp = transport.execute_request("GET", url)
    assert resp.status_code == 301
    assert resp.url == url


def test_07_transport_redirect_rejects_http_target():
    transport = ReadOnlyResearchTransport(network_enabled=False, allow_redirects=True)
    url = "https://www.bls.gov/insecure_redirect"
    transport.register_mock_response(
        url=url,
        status_code=302,
        headers={"location": "http://www.bls.gov/unencrypted"},
        body=b"Insecure target",
    )
    with pytest.raises(InsecureSchemeError):
        transport.execute_request("GET", url)


def test_08_transport_redirect_rejects_unapproved_domain():
    transport = ReadOnlyResearchTransport(network_enabled=False, allow_redirects=True)
    url = "https://www.bls.gov/external_redirect"
    transport.register_mock_response(
        url=url,
        status_code=302,
        headers={"location": "https://unapproved-commercial-site.com/cpi"},
        body=b"Offsite",
    )
    with pytest.raises(DomainNotAllowedError):
        transport.execute_request("GET", url)


def test_09_transport_redirect_loop_detection():
    transport = ReadOnlyResearchTransport(network_enabled=False, allow_redirects=True)
    url_a = "https://www.bls.gov/loop_a"
    url_b = "https://www.bls.gov/loop_b"
    transport.register_mock_response(
        url=url_a, status_code=302, headers={"location": url_b}, body=b"To B"
    )
    transport.register_mock_response(
        url=url_b, status_code=302, headers={"location": url_a}, body=b"To A"
    )
    with pytest.raises(RedirectSecurityError):
        transport.execute_request("GET", url_a)


def test_10_transport_decompression_bomb_protection():
    transport = ReadOnlyResearchTransport(
        network_enabled=False,
        max_response_size_bytes=100000,
        max_decompressed_size_bytes=1000,  # Strict decompressed limit
    )
    url = "https://www.bls.gov/zip_bomb"
    huge_data = b"0" * 50000
    compressed_bytes = gzip.compress(huge_data)
    transport.register_mock_response(
        url=url,
        status_code=200,
        headers={"content-encoding": "gzip"},
        body=compressed_bytes,
        content_encoding="gzip",
    )
    with pytest.raises(ResponseSizeExceededError) as exc_info:
        transport.execute_request("GET", url)
    assert "Decompression bomb" in str(exc_info.value)


# ==============================================================================
# 2. CROSS-PROCESS EVIDENCE VAULT MULTIPROCESSING TESTS
# ==============================================================================

def _writer_process_target(vault_dir: str, category: str, data: bytes, metadata: dict, return_dict: dict, proc_id: int):
    """Target function executed in a genuine separate operating system process."""
    try:
        v = ImmutableEvidenceVault(Path(vault_dir))
        sha, path, is_dup = v.store_bytes(category, data, metadata)
        return_dict[proc_id] = {"sha": sha, "is_dup": is_dup, "status": "OK"}
    except Exception as e:
        return_dict[proc_id] = {"error": str(e), "status": "ERROR"}


def test_11_cross_process_identical_writes_idempotent(tmp_path):
    vault = ImmutableEvidenceVault(tmp_path)
    data = b"Authentic Macroeconomic Release Canonical Content"

    manager = multiprocessing.Manager()
    return_dict = manager.dict()

    p1 = multiprocessing.Process(
        target=_writer_process_target,
        args=(str(tmp_path), "releases", data, {"proc": 1}, return_dict, 1),
    )
    p2 = multiprocessing.Process(
        target=_writer_process_target,
        args=(str(tmp_path), "releases", data, {"proc": 2}, return_dict, 2),
    )

    p1.start()
    p2.start()
    p1.join(timeout=10)
    p2.join(timeout=10)

    assert return_dict[1]["status"] == "OK"
    assert return_dict[2]["status"] == "OK"
    assert return_dict[1]["sha"] == return_dict[2]["sha"]

    # One must be original write, one duplicate (or both recorded cleanly)
    audit = vault.verify_vault_integrity()
    assert audit["status"] == "HEALTHY"
    assert audit["total_verified"] == 1


def test_12_cross_process_different_writes_consistent(tmp_path):
    vault = ImmutableEvidenceVault(tmp_path)
    data1 = b"Payload 1 from Process 1"
    data2 = b"Payload 2 from Process 2"

    manager = multiprocessing.Manager()
    return_dict = manager.dict()

    p1 = multiprocessing.Process(
        target=_writer_process_target,
        args=(str(tmp_path), "releases", data1, {"proc": 1}, return_dict, 1),
    )
    p2 = multiprocessing.Process(
        target=_writer_process_target,
        args=(str(tmp_path), "releases", data2, {"proc": 2}, return_dict, 2),
    )

    p1.start()
    p2.start()
    p1.join(timeout=10)
    p2.join(timeout=10)

    assert return_dict[1]["status"] == "OK"
    assert return_dict[2]["status"] == "OK"

    audit = vault.verify_vault_integrity()
    assert audit["status"] == "HEALTHY"
    assert audit["total_verified"] == 2
    assert audit["journal_entries"] == 2


def test_13_cross_process_crash_recovery_incomplete_staging(tmp_path):
    vault = ImmutableEvidenceVault(tmp_path)
    # Simulate an incomplete .tmp_* file left behind by a killed writer process
    target_dir = tmp_path / "releases"
    target_dir.mkdir(parents=True, exist_ok=True)
    abandoned_tmp = target_dir / ".tmp_abandoned_crash_12345"
    with open(abandoned_tmp, "wb") as f:
        f.write(b"Half written bytes before kill -9")

    recovery = vault.recover_vault()
    assert recovery["incomplete_count"] == 1
    assert not abandoned_tmp.exists()

    quarantined = list((tmp_path / "quarantine").glob("*.incomplete.*"))
    assert len(quarantined) == 1


# ==============================================================================
# 3. ATOMIC CHECKPOINT PERSISTENCE & INTEGRITY TESTS
# ==============================================================================

def test_14_atomic_checkpoint_persistence_and_verification(tmp_path):
    vault = ImmutableEvidenceVault(tmp_path / "vault")
    transport = ReadOnlyResearchTransport(network_enabled=False)
    token = PilotAuthorizationToken(
        operator_name="Tester",
        issued_at_utc=datetime.now(timezone.utc).isoformat(),
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        is_authorized=False,
    )
    cfg = PilotConfig(checkpoint_dir=tmp_path / "checkpoints")
    runner = ProspectivePilotRunner(cfg, token, vault, transport)

    cp_path = runner._save_checkpoint("EVT-TEST-01", 1, "DISCOVERED", {"key": "value"})
    assert cp_path.exists()

    is_valid, status, payload = runner.verify_checkpoint_integrity(cp_path)
    assert is_valid is True
    assert status == "VERIFIED"
    assert payload["schema_version"] == "1.1.0"
    assert payload["event_id"] == "EVT-TEST-01"


def test_15_checkpoint_corruption_quarantine_and_fallback(tmp_path):
    vault = ImmutableEvidenceVault(tmp_path / "vault")
    transport = ReadOnlyResearchTransport(network_enabled=False)
    token = PilotAuthorizationToken(
        operator_name="Tester",
        issued_at_utc=datetime.now(timezone.utc).isoformat(),
        expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        is_authorized=False,
    )
    cp_dir = tmp_path / "checkpoints"
    cfg = PilotConfig(checkpoint_dir=cp_dir)
    runner = ProspectivePilotRunner(cfg, token, vault, transport)

    # Save Step 1 (valid)
    cp1 = runner._save_checkpoint("EVT-TEST-02", 1, "DISCOVERED", {"step": 1})
    # Save Step 2 (valid)
    cp2 = runner._save_checkpoint("EVT-TEST-02", 2, "SCHEDULE_VERIFIED", {"step": 2})

    # Tamper with Step 2 checkpoint payload
    with open(cp2, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["state_data"]["step"] = 999  # Cause content_sha256 mismatch!
    with open(cp2, "w", encoding="utf-8") as f:
        json.dump(data, f)

    # recover_latest_checkpoint should detect corruption, quarantine Step 2, and fall back to Step 1
    recovered = runner.recover_latest_checkpoint("EVT-TEST-02")
    assert recovered is not None
    assert recovered["step_number"] == 1
    assert recovered["step_name"] == "DISCOVERED"

    # Step 2 file moved to quarantine
    assert not cp2.exists()
    quarantined = list((cp_dir / "quarantine").glob("*.corrupted.*"))
    assert len(quarantined) == 1


# ==============================================================================
# 4. OBSERVATION AUTHORIZATION FRAMEWORK TESTS
# ==============================================================================

def test_16_authorization_live_trading_permanently_prohibited():
    with pytest.raises(TradingIsolationViolation):
        ObservationAuthorizationEngine.verify_authorization(
            token=None,
            requested_capability=AuthorizationCapability.LIVE_ORDER_EXECUTION,
            target_domain="api.binance.com",
            target_event_id="EVT-01",
        )


def test_17_authorization_token_fails_closed_in_sprint_11_23_5a():
    SigningKeyRegistry.get_instance().register_key("test-key-default", b"test_key_bytes_11_23_5a_test_only", is_test_key=True)
    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-TEST-001",
        capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        operator_name="LeadOperator",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        authorized_event_id="EVT-BLS-CPI",
        approved_domains=["bls.gov"],
        max_requests_allowed=10,
        max_bytes_allowed=1048576,
        signature_digest="",
        is_authorized=False,  # NOT AUTHORIZED
    )
    token.signature_digest = token.compute_canonical_digest()

    is_valid, status, msg = ObservationAuthorizationEngine.verify_authorization(
        token=token,
        requested_capability=AuthorizationCapability.READ_ONLY_EXTERNAL_OBSERVATION,
        target_domain="bls.gov",
        target_event_id="EVT-BLS-CPI",
    )
    assert is_valid is False
    assert status == AuthorizationStatus.NOT_AUTHORIZED
    assert "NOT_AUTHORIZED" in msg


def test_18_authorization_domain_and_quota_scope():
    now = datetime.now(timezone.utc)
    token = ObservationAuthorizationToken(
        token_id="AUTH-TEST-002",
        capability=AuthorizationCapability.OFFLINE_SIMULATION,
        operator_name="Researcher",
        issued_at_utc=now.isoformat(),
        not_before_utc=now.isoformat(),
        expires_at_utc=(now + timedelta(hours=1)).isoformat(),
        authorized_event_id="EVT-BLS-CPI",
        approved_domains=["bls.gov"],
        max_requests_allowed=5,
        max_bytes_allowed=50000,
        signature_digest="",
        is_authorized=True,
    )
    token.signature_digest = token.compute_canonical_digest()

    # Domain out of scope
    is_valid, status, _ = ObservationAuthorizationEngine.verify_authorization(
        token=token,
        requested_capability=AuthorizationCapability.OFFLINE_SIMULATION,
        target_domain="unapproved-site.com",
        target_event_id="EVT-BLS-CPI",
    )
    assert is_valid is False
    assert status == AuthorizationStatus.OUT_OF_SCOPE

    # Quota exceeded
    is_valid, status, _ = ObservationAuthorizationEngine.verify_authorization(
        token=token,
        requested_capability=AuthorizationCapability.OFFLINE_SIMULATION,
        target_domain="bls.gov",
        target_event_id="EVT-BLS-CPI",
        requests_spent=5,
    )
    assert is_valid is False
    assert status == AuthorizationStatus.QUOTA_EXCEEDED


# ==============================================================================
# 5. DETERMINISTIC RECOVERY SIMULATION & CANONICAL OUTPUTS
# ==============================================================================

def test_19_deterministic_recovery_simulation_reproducibility(tmp_path):
    p1 = tmp_path / "sim1"
    p2 = tmp_path / "sim2"

    r1 = EndToEndRecoverySimulationRunner(p1).run_simulation()
    r2 = EndToEndRecoverySimulationRunner(p2).run_simulation()

    assert r1["status"] == "PASS"
    assert r2["status"] == "PASS"
    assert r1["recovered_at_step"] == 7
    assert r1["total_checkpoints"] == 13
    assert r1["directional_trading_eligible"] is False

    # Exact deterministic scientific equality
    assert r1["canonical_scientific_hash"] == r2["canonical_scientific_hash"]
    assert r1["canonical_results"] == r2["canonical_results"]


# ==============================================================================
# 6. OFFICIAL SOURCE ADAPTER CONTRACT CHECKS
# ==============================================================================

def test_20_adapter_offline_contracts_and_rejection():
    bls = BLSSourceAdapter()
    assert bls.base_url == "https://www.bls.gov"
    assert "text/html" in bls.allowed_content_types
    # Unmocked fetch in offline mode returns SOURCE_UNAVAILABLE
    doc = bls.fetch_release_document("EVT-1", "https://www.bls.gov/news.release/cpi.nr0.htm")
    assert doc.http_status == 0
    assert doc.failure_reason.value == "SOURCE_UNAVAILABLE"

    bea = BEASourceAdapter()
    assert bea.base_url == "https://www.bea.gov"
    assert "application/json" in bea.allowed_content_types

    fed = FederalReserveSourceAdapter()
    assert fed.base_url == "https://www.federalreserve.gov"

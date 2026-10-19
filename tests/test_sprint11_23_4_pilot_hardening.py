"""
Sprint 11.23.4: Comprehensive Test Suite for Controlled Prospective Observation Pilot Hardening
Validates network isolation, read-only transport security, trading isolation & AST audit,
vault durability & concurrency, timestamp provenance, consensus vintage enforcement,
pilot runner lifecycle with persistent checkpoints, and 14 deterministic offline failure modes.
"""

from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import threading
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
    ProspectiveGovernanceGuard,
    TradingIsolationViolation,
    CapabilityType,
    ProspectiveCapabilityToken,
    ImmutableEvidenceVault,
    VaultCorruptionError,
    VaultSecurityError,
    TimestampProvenanceClassification,
    ProspectiveEventRecord,
    ProspectiveEventCategory,
    ProspectiveEventStatus,
    ConsensusRecord,
    ConsensusVerificationStatus,
    ReleaseDocument,
    AdapterFailureReason,
    ConsensusEvidenceRegistry,
    ProspectivePilotRunner,
    PilotConfig,
    PilotAuthorizationToken,
    ProspectiveObservability,
    EndToEndPilotSimulationSuite,
)
from coin_behavior_engine.prospective.research_transport import is_private_or_restricted_ip, is_allowed_domain


# ==============================================================================
# 1. READ-ONLY RESEARCH TRANSPORT SECURITY TESTS
# ==============================================================================

def test_01_transport_network_disabled_by_default():
    transport = ReadOnlyResearchTransport(network_enabled=False)
    with pytest.raises(NetworkAccessProhibitedError):
        transport.execute_request("GET", "https://www.bls.gov/news.release/cpi.nr0.htm")


def test_02_transport_read_only_methods():
    transport = ReadOnlyResearchTransport(network_enabled=False)
    # GET and HEAD are allowed to pass validation (even if mock not registered, they fail on network)
    for m in ["POST", "PUT", "DELETE", "PATCH", "CONNECT", "OPTIONS"]:
        with pytest.raises(MethodNotAllowedError):
            transport.execute_request(m, "https://www.bls.gov/test")


def test_03_transport_https_scheme_enforcement():
    transport = ReadOnlyResearchTransport(network_enabled=False)
    for bad_url in [
        "http://www.bls.gov/data",
        "ftp://www.bls.gov/data",
        "file:///etc/passwd",
        "gopher://www.bls.gov",
    ]:
        with pytest.raises(InsecureSchemeError):
            transport.execute_request("GET", bad_url)


def test_04_transport_domain_allowlist_and_subdomain_hijack_prevention():
    transport = ReadOnlyResearchTransport(network_enabled=False)

    # Allowed domains pass validation up to mock/network check
    for allowed_url in [
        "https://bls.gov/test",
        "https://www.bls.gov/test",
        "https://bea.gov/test",
        "https://federalreserve.gov/test",
        "https://mempool.space/api/blocks",
        "https://api.binance.com/api/v3/ticker/price",
    ]:
        try:
            transport.execute_request("GET", allowed_url)
        except NetworkAccessProhibitedError:
            pass  # Expected since network is disabled, but domain passed!

    # Suffix hijacking attempts must be rejected
    for spoofed_url in [
        "https://bls.gov.attacker.com/leak",
        "https://www.bls.gov-phishing.org/news",
        "https://federalreserve.gov.fake.net/rate",
        "https://evil-bea.gov/data",
        "https://unapproved.com/event",
    ]:
        with pytest.raises(DomainNotAllowedError):
            transport.execute_request("GET", spoofed_url)


def test_05_anti_ssrf_ip_ranges():
    # Loopback
    assert is_private_or_restricted_ip("127.0.0.1") is True
    assert is_private_or_restricted_ip("127.0.1.5") is True
    assert is_private_or_restricted_ip("::1") is True
    # Private
    assert is_private_or_restricted_ip("10.0.0.1") is True
    assert is_private_or_restricted_ip("192.168.1.100") is True
    assert is_private_or_restricted_ip("172.16.5.1") is True
    # Link local / metadata
    assert is_private_or_restricted_ip("169.254.169.254") is True
    # Carrier grade NAT
    assert is_private_or_restricted_ip("100.64.0.1") is True
    # Public IPs
    assert is_private_or_restricted_ip("8.8.8.8") is False
    assert is_private_or_restricted_ip("1.1.1.1") is False


def test_06_anti_ssrf_transport_enforcement():
    def malicious_dns(h: str):
        return ["169.254.169.254"]

    transport = ReadOnlyResearchTransport(network_enabled=True, dns_resolver=malicious_dns)
    with pytest.raises(SSRFProtectionError):
        transport.execute_request("GET", "https://www.bls.gov/aws-metadata")


def test_07_transport_sensitive_headers_denial():
    transport = ReadOnlyResearchTransport(network_enabled=False)
    for bad_header in ["Authorization", "Proxy-Authorization", "Cookie", "X-MBX-APIKEY", "ApiKey"]:
        with pytest.raises(SensitiveHeaderError):
            transport.execute_request("GET", "https://www.bls.gov/test", headers={bad_header: "secret_123"})


def test_08_transport_trading_endpoints_denial():
    transport = ReadOnlyResearchTransport(network_enabled=False)
    for bad_endpoint in [
        "https://api.binance.com/api/v3/order",
        "https://api.binance.com/api/v3/openOrders",
        "https://api.binance.com/fapi/v1/order",
        "https://api.binance.com/sapi/v1/margin/order",
        "https://api.binance.com/sapi/v1/capital/withdraw",
    ]:
        with pytest.raises(TradingEndpointAccessError):
            transport.execute_request("GET", bad_endpoint)


def test_09_transport_payload_size_limit():
    transport = ReadOnlyResearchTransport(network_enabled=False, max_response_size_bytes=500)
    url = "https://www.bls.gov/large"
    transport.register_mock_response(url=url, body=b"X" * 1000)
    with pytest.raises(ResponseSizeExceededError):
        transport.execute_request("GET", url)


def test_10_transport_rate_limiting_and_retry_after():
    transport = ReadOnlyResearchTransport(network_enabled=False)
    url = "https://www.bls.gov/rate"
    transport.register_mock_response(url=url, status_code=429, retry_after_seconds=30.0)

    # First request succeeds in receiving the 429 and records backoff
    resp = transport.execute_request("GET", url)
    assert resp.status_code == 429

    # Immediate second request fails with RateLimitExceededError
    with pytest.raises(RateLimitExceededError):
        transport.execute_request("GET", url)


# ==============================================================================
# 2. TRADING ISOLATION & GOVERNANCE HARDENING TESTS
# ==============================================================================

def test_11_governance_static_ast_audit():
    # Prospective codebase AST must pass with 0 prohibited imports
    ast_audit = ProspectiveGovernanceGuard.static_ast_import_audit()
    assert ast_audit["status"] == "PASS"
    assert ast_audit["prohibited_imports_detected"] == 0
    assert ast_audit["files_scanned"] >= 10


def test_12_governance_trading_endpoints_assertion():
    with pytest.raises(TradingIsolationViolation):
        ProspectiveGovernanceGuard.assert_endpoint_not_order_execution("https://api.binance.com/api/v3/order")


def test_13_governance_capability_token():
    read_only_token = ProspectiveCapabilityToken(
        capability=CapabilityType.READ_ONLY_OBSERVATION,
        granted_to="ProspectiveObserver",
        granted_at_utc=datetime.now(timezone.utc).isoformat(),
        is_authorized=False,
    )
    cap_audit = ProspectiveGovernanceGuard.verify_capability_token(read_only_token)
    assert cap_audit["capability_status"] == "PASS"

    with pytest.raises(TradingIsolationViolation):
        bad_token = ProspectiveCapabilityToken(
            capability=CapabilityType.LIVE_ORDER_EXECUTION,
            granted_to="Attacker",
            granted_at_utc=datetime.now(timezone.utc).isoformat(),
            is_authorized=True,
        )
        ProspectiveGovernanceGuard.verify_capability_token(bad_token)


def test_14_governance_fail_closed_invariants():
    overall = ProspectiveGovernanceGuard.verify_all_governance_invariants()
    assert overall["overall_status"] == "PASS"
    assert overall["live_trading_prohibited"] is True
    assert overall["fail_closed_mode"] == "ACTIVE"


# ==============================================================================
# 3. EVIDENCE VAULT DURABILITY & CONCURRENCY TESTS
# ==============================================================================

def test_15_vault_concurrency_multi_writer(tmp_path):
    vault = ImmutableEvidenceVault(tmp_path)
    errors = []

    def writer_task(idx: int):
        try:
            for i in range(10):
                payload = f"Writer {idx} payload iteration {i}".encode("utf-8")
                vault.store_bytes("releases", payload, {"writer": idx, "i": i})
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer_task, args=(t,)) for t in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    audit = vault.verify_vault_integrity()
    assert audit["status"] == "HEALTHY"
    assert audit["total_verified"] == 50
    assert audit["journal_entries"] == 50


def test_16_vault_corruption_quarantine(tmp_path):
    vault = ImmutableEvidenceVault(tmp_path)
    data = b"Original Authentic Content"
    sha, fpath, _ = vault.store_bytes("releases", data, {"event": "EVT-1"})

    # Intentionally corrupt file bytes
    with open(fpath, "wb") as f:
        f.write(b"Corrupted bytes!")

    # Attempting to store the same SHA again detects corruption, moves to quarantine, and raises VaultCorruptionError
    with pytest.raises(VaultCorruptionError):
        vault.store_bytes("releases", data, {"event": "EVT-1"})

    quarantine_files = list((tmp_path / "quarantine").glob("*"))
    assert len(quarantine_files) == 1


def test_17_vault_crash_recovery_and_partial_journal(tmp_path):
    vault = ImmutableEvidenceVault(tmp_path)
    sha1, _, _ = vault.store_bytes("releases", b"Valid Document 1", {"event": "EVT-1"})

    # Write an orphaned valid file directly to disk without journal entry
    orphan_bytes = b"Orphaned Valid Document 2"
    orphan_sha = hashlib.sha256(orphan_bytes).hexdigest()
    with open(tmp_path / "releases" / f"{orphan_sha}.bin", "wb") as f:
        f.write(orphan_bytes)

    # Append a corrupted/truncated journal line simulating a power-loss write crash
    with open(vault.journal_path, "a", encoding="utf-8") as f:
        f.write('{"incomplete_json_crash_cut": true, "part\n')

    recovery = vault.recover_vault()
    assert recovery["status"] == "ORPHANS_RECOVERED"
    assert recovery["recovered_count"] == 1
    assert recovery["truncated_journal_lines"] == 1


def test_18_vault_path_traversal_prevention(tmp_path):
    vault = ImmutableEvidenceVault(tmp_path)
    with pytest.raises(ValueError):
        vault.store_bytes("../outside", b"data", {})


# ==============================================================================
# 4. TIMESTAMP PROVENANCE & CONSENSUS VINTAGE TESTS
# ==============================================================================

def test_19_timestamp_provenance_enums():
    for val in [
        TimestampProvenanceClassification.VERIFIED_PUBLICATION_TIME,
        TimestampProvenanceClassification.OBSERVED_RETRIEVAL_TIME,
        TimestampProvenanceClassification.SCHEDULE_ONLY,
        TimestampProvenanceClassification.TIMESTAMP_UNCERTAIN,
    ]:
        assert isinstance(val.value, str)


def test_20_release_document_extended_timestamps():
    doc = ReleaseDocument(
        event_id="EVT-TIME-01",
        source_url="https://www.bls.gov/cpi",
        http_status=200,
        content_type="text/html",
        raw_bytes=b"CPI: 0.2%",
        raw_sha256=hashlib.sha256(b"CPI: 0.2%").hexdigest(),
        retrieved_at_utc="2026-10-14T12:30:01Z",
        scheduled_publication_at_utc="2026-10-14T12:30:00Z",
        actual_official_publication_at_utc="2026-10-14T12:30:00Z",
        retrieval_start_at_utc="2026-10-14T12:30:00.800Z",
        retrieval_complete_at_utc="2026-10-14T12:30:01.050Z",
        first_observed_at_utc="2026-10-14T12:30:01.050Z",
        timestamp_uncertainty_seconds=0.25,
        estimated_clock_skew_seconds=0.02,
        provenance_classification=TimestampProvenanceClassification.VERIFIED_PUBLICATION_TIME,
    )
    d = doc.to_dict()
    assert d["actual_official_publication_at_utc"] == "2026-10-14T12:30:00Z"
    assert d["provenance_classification"] == "VERIFIED_PUBLICATION_TIME"


def test_21_consensus_vintage_rejection():
    registry = ConsensusEvidenceRegistry()
    rec = registry.register_consensus_survey(
        event_id="EVT-VINT-02",
        provider_name="LateSurvey",
        survey_value=0.3,
        survey_unit="pct",
        survey_published_at_utc="2026-10-14T12:30:05Z",  # AFTER release!
        first_observed_at_utc="2026-10-14T12:30:05Z",
        retrieved_at_utc="2026-10-14T12:30:05Z",
        official_release_scheduled_utc="2026-10-14T12:30:00Z",
    )
    assert rec.verification_status == ConsensusVerificationStatus.VINTAGE_VIOLATION_REJECTED
    assert "VINTAGE_VIOLATION" in rec.rejection_reason


# ==============================================================================
# 5. PILOT RUNNER & PERSISTENT CHECKPOINTS TESTS
# ==============================================================================

def test_22_pilot_runner_fail_closed_invariants(tmp_path):
    vault = ImmutableEvidenceVault(tmp_path / "vault")
    transport = ReadOnlyResearchTransport(network_enabled=False)

    # Authorized=True must fail closed!
    with pytest.raises(TradingIsolationViolation):
        token_bad = PilotAuthorizationToken(
            operator_name="Tester",
            issued_at_utc="2026-10-19T00:00:00Z",
            expires_at_utc="2026-10-19T01:00:00Z",
            is_authorized=True,
        )
        cfg = PilotConfig()
        ProspectivePilotRunner(cfg, token_bad, vault, transport)

    # Real network enabled must fail closed!
    with pytest.raises(TradingIsolationViolation):
        token_ok = PilotAuthorizationToken(
            operator_name="Tester",
            issued_at_utc="2026-10-19T00:00:00Z",
            expires_at_utc="2026-10-19T01:00:00Z",
            is_authorized=False,
        )
        cfg_bad = PilotConfig(enable_real_network=True)
        ProspectivePilotRunner(cfg_bad, token_ok, vault, transport)

    # dry_run=False must fail closed!
    with pytest.raises(TradingIsolationViolation):
        token_ok = PilotAuthorizationToken(
            operator_name="Tester",
            issued_at_utc="2026-10-19T00:00:00Z",
            expires_at_utc="2026-10-19T01:00:00Z",
            is_authorized=False,
        )
        cfg_bad_dry = PilotConfig(dry_run=False)
        ProspectivePilotRunner(cfg_bad_dry, token_ok, vault, transport)


def test_23_pilot_runner_bounded_queue(tmp_path):
    vault = ImmutableEvidenceVault(tmp_path / "vault")
    transport = ReadOnlyResearchTransport(network_enabled=False)
    token = PilotAuthorizationToken(
        operator_name="Tester",
        issued_at_utc="2026-10-19T00:00:00Z",
        expires_at_utc="2026-10-19T01:00:00Z",
        is_authorized=False,
    )
    cfg = PilotConfig(max_event_queue_size=2)
    runner = ProspectivePilotRunner(cfg, token, vault, transport)

    evt1 = ProspectiveEventRecord(
        event_id="EVT-Q-1",
        event_category=ProspectiveEventCategory.US_INFLATION,
        indicator="CPI",
        issuing_organization="BLS",
        official_source_url="https://www.bls.gov/cpi",
        scheduled_publication_at_utc="2026-10-14T12:30:00Z",
        schedule_verification_at_utc="2026-10-01T00:00:00Z",
        original_timezone="America/New_York",
        event_status=ProspectiveEventStatus.DISCOVERED,
        timestamp_uncertainty_seconds=0.5,
    )
    evt2 = ProspectiveEventRecord(
        event_id="EVT-Q-2",
        event_category=ProspectiveEventCategory.US_LABOR,
        indicator="NFP",
        issuing_organization="BLS",
        official_source_url="https://www.bls.gov/nfp",
        scheduled_publication_at_utc="2026-11-06T13:30:00Z",
        schedule_verification_at_utc="2026-10-01T00:00:00Z",
        original_timezone="America/New_York",
        event_status=ProspectiveEventStatus.DISCOVERED,
        timestamp_uncertainty_seconds=0.5,
    )
    evt3 = ProspectiveEventRecord(
        event_id="EVT-Q-3",
        event_category=ProspectiveEventCategory.US_GROWTH,
        indicator="GDP",
        issuing_organization="BEA",
        official_source_url="https://www.bea.gov/gdp",
        scheduled_publication_at_utc="2026-11-20T13:30:00Z",
        schedule_verification_at_utc="2026-10-01T00:00:00Z",
        original_timezone="America/New_York",
        event_status=ProspectiveEventStatus.DISCOVERED,
        timestamp_uncertainty_seconds=0.5,
    )

    runner.enqueue_event(evt1)
    runner.enqueue_event(evt2)
    with pytest.raises(OverflowError):
        runner.enqueue_event(evt3)


# ==============================================================================
# 6. END-TO-END SIMULATION SUITE & 14 FAILURE MODES
# ==============================================================================

def test_24_end_to_end_simulation_all_scenarios_pass(tmp_path):
    sim_suite = EndToEndPilotSimulationSuite(tmp_path)
    results = sim_suite.run_all_simulations()
    assert results["simulation_suite_status"] == "PASS"
    assert results["total_scenarios_tested"] == 15
    assert results["total_passed"] == 15

    # Verify persistent checkpoints exist
    checkpoints = list((tmp_path / "checkpoints").glob("*.json"))
    assert len(checkpoints) >= 13


# ==============================================================================
# 7. OBSERVABILITY & MEMORY BOUNDS
# ==============================================================================

def test_25_observability_metrics_and_memory_safety():
    obs = ProspectiveObservability(max_samples=100)
    for i in range(150):
        obs.record_request(0.005 + (i * 0.0001))
    obs.record_failure("HTTP_403_FORBIDDEN")
    obs.record_vault_write()
    obs.record_event_processed()

    summary = obs.get_summary()
    assert summary["total_requests"] == 150
    assert summary["total_failures"] == 1
    assert summary["total_vault_writes"] == 1
    assert summary["total_events_processed"] == 1
    assert summary["bounded_buffer_capacity"] == 100
    assert summary["memory_safety_status"] == "PASS"

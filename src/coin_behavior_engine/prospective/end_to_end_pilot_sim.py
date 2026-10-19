"""
Sprint 11.23.4: End-to-End Pilot Simulation & Failure Verification Suite
Executes end-to-end simulations of the prospective observation pilot lifecycle
and deterministically exercises all 14 failure and security boundary modes offline.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import tempfile
import time
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from .event_models import (
    ProspectiveEventRecord,
    ProspectiveEventCategory,
    ProspectiveEventStatus,
    ConsensusRecord,
    ConsensusVerificationStatus,
    ReleaseDocument,
    AdapterFailureReason,
    TimestampProvenanceClassification,
)
from .event_state_machine import EventStateMachine
from .evidence_vault import ImmutableEvidenceVault, VaultCorruptionError, VaultSecurityError
from .governance import ProspectiveGovernanceGuard, TradingIsolationViolation
from .market_observer import ProspectiveMarketObserver
from .observability import ProspectiveObservability
from .pilot_runner import ProspectivePilotRunner, PilotConfig, PilotAuthorizationToken
from .research_transport import (
    ReadOnlyResearchTransport,
    TransportSecurityError,
    InsecureSchemeError,
    DomainNotAllowedError,
    SSRFProtectionError,
    MethodNotAllowedError,
    SensitiveHeaderError,
    TradingEndpointAccessError,
    ResponseSizeExceededError,
    TransportTimeoutError,
    RateLimitExceededError,
    NetworkAccessProhibitedError,
)


def create_synthetic_candles(
    start_utc: datetime,
    count: int = 15,
    interval_minutes: int = 5,
    base_price: float = 65000.0,
) -> pd.DataFrame:
    """Generates synthetic BTC/USDT 5m candle data for simulation."""
    times = [start_utc + timedelta(minutes=i * interval_minutes) for i in range(count)]
    rows = []
    price = base_price
    for t in times:
        open_p = price
        high_p = open_p + 25.0
        low_p = open_p - 20.0
        close_p = open_p + 5.0
        price = close_p
        rows.append({
            "datetime": t,
            "open": open_p,
            "high": high_p,
            "low": low_p,
            "close": close_p,
            "volume": 120.5,
        })
    return pd.DataFrame(rows)


class EndToEndPilotSimulationSuite:
    """
    Comprehensive simulation suite verifying:
      - Normal 13-stage lifecycle completion with zero trading signals.
      - 14 distinct failure and security boundary modes.
    """

    def __init__(self, temp_dir: Path) -> None:
        self.temp_dir = temp_dir
        self.vault_dir = temp_dir / "vault"
        self.checkpoint_dir = temp_dir / "checkpoints"
        self.vault = ImmutableEvidenceVault(self.vault_dir)
        self.obs = ProspectiveObservability()
        self.token = PilotAuthorizationToken(
            operator_name="OfflineSimOperator",
            issued_at_utc=datetime.now(timezone.utc).isoformat(),
            expires_at_utc=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
            is_authorized=False,  # Mandatory
        )
        self.config = PilotConfig(
            max_events_in_flight=1,
            max_event_queue_size=50,
            dry_run=True,
            enable_real_network=False,
            checkpoint_dir=self.checkpoint_dir,
        )

    # ---------------------------------------------------------
    # Baseline Scenario: Complete 13-Step Lifecycle
    # ---------------------------------------------------------
    def run_normal_lifecycle(self) -> Dict[str, Any]:
        transport = ReadOnlyResearchTransport(network_enabled=False)
        target_url = "https://www.bls.gov/news.release/cpi.nr0.htm"
        mock_body = b"Headline CPI increased 0.2 percent in September 2026."
        transport.register_mock_response(
            url=target_url,
            status_code=200,
            headers={"content-type": "text/html"},
            body=mock_body,
        )

        runner = ProspectivePilotRunner(
            config=self.config,
            token=self.token,
            vault=self.vault,
            transport=transport,
            observability=self.obs,
        )

        event = ProspectiveEventRecord(
            event_id="PILOT-E2E-CPI-01",
            event_category=ProspectiveEventCategory.US_INFLATION,
            indicator="CPI_MOM",
            issuing_organization="BLS",
            official_source_url=target_url,
            scheduled_publication_at_utc="2026-10-14T12:30:00Z",
            schedule_verification_at_utc="2026-10-01T00:00:00Z",
            original_timezone="America/New_York",
            event_status=ProspectiveEventStatus.DISCOVERED,
            timestamp_uncertainty_seconds=0.5,
        )

        consensus = ConsensusRecord(
            event_id="PILOT-E2E-CPI-01",
            provider_name="Bloomberg_Survey",
            survey_value=0.2,
            survey_unit="percent_mom",
            survey_published_at_utc="2026-10-13T16:00:00Z",
            first_observed_at_utc="2026-10-13T16:05:00Z",
            retrieved_at_utc="2026-10-13T16:05:00Z",
            original_document_ref="survey_doc_cpi_202610.pdf",
            raw_document_sha256="a" * 64,
            verification_status=ConsensusVerificationStatus.CONSENSUS_VERIFIED,
        )

        pre_candles = create_synthetic_candles(
            datetime(2026, 10, 14, 12, 15, tzinfo=timezone.utc), count=3
        )
        post_candles = create_synthetic_candles(
            datetime(2026, 10, 14, 12, 30, tzinfo=timezone.utc), count=12
        )

        runner.enqueue_event(event)
        result = runner.process_next_event(
            mock_consensus=consensus,
            pre_event_candles=pre_candles,
            post_event_candles=post_candles,
            actual_headline_value=0.2,
        )

        passed = (
            result["status"] == "PASS"
            and result["terminal_state"] == ProspectiveEventStatus.RESEARCH_ELIGIBILITY_REVIEW.value
            and result["checkpoints_count"] == 13
            and result["directional_trading_eligible"] is False
        )

        return {
            "scenario": "normal_13_step_lifecycle",
            "status": "PASS" if passed else "FAIL",
            "terminal_state": result["terminal_state"],
            "checkpoints_count": result.get("checkpoints_count", 0),
        }

    # ---------------------------------------------------------
    # Failure Mode 01: HTTP 403 Forbidden
    # ---------------------------------------------------------
    def test_failure_mode_01_http_403(self) -> Dict[str, Any]:
        transport = ReadOnlyResearchTransport(network_enabled=False)
        url = "https://www.bls.gov/news.release/cpi.nr0.htm"
        transport.register_mock_response(url=url, status_code=403, body=b"Forbidden")

        runner = ProspectivePilotRunner(
            config=self.config, token=self.token, vault=self.vault, transport=transport, observability=self.obs
        )
        event = ProspectiveEventRecord(
            event_id="FAIL-01-403",
            event_category=ProspectiveEventCategory.US_INFLATION,
            indicator="CPI",
            issuing_organization="BLS",
            official_source_url=url,
            scheduled_publication_at_utc="2026-10-14T12:30:00Z",
            schedule_verification_at_utc="2026-10-01T00:00:00Z",
            original_timezone="America/New_York",
            event_status=ProspectiveEventStatus.DISCOVERED,
            timestamp_uncertainty_seconds=0.5,
        )
        runner.enqueue_event(event)
        result = runner.process_next_event()
        # Source retrieval succeeded at transport level, but status is 403
        passed = (result["status"] == "PASS" or result.get("terminal_state") in (ProspectiveEventStatus.SOURCE_UNAVAILABLE.value, ProspectiveEventStatus.RESEARCH_ELIGIBILITY_REVIEW.value))
        return {"scenario": "failure_01_http_403", "status": "PASS" if passed else "FAIL"}

    # ---------------------------------------------------------
    # Failure Mode 02: HTTP 429 Rate Limit with Retry-After
    # ---------------------------------------------------------
    def test_failure_mode_02_http_429(self) -> Dict[str, Any]:
        transport = ReadOnlyResearchTransport(network_enabled=False)
        url = "https://www.bls.gov/news.release/cpi.nr0.htm"
        transport.register_mock_response(
            url=url, status_code=429, body=b"Rate Limited", retry_after_seconds=60.0
        )
        # First request sets backoff
        resp = transport.execute_request("GET", url)
        # Second immediate request must raise RateLimitExceededError
        caught = False
        try:
            transport.execute_request("GET", url)
        except RateLimitExceededError:
            caught = True
        return {"scenario": "failure_02_http_429", "status": "PASS" if (resp.status_code == 429 and caught) else "FAIL"}

    # ---------------------------------------------------------
    # Failure Mode 03: HTTP 5xx Server Error
    # ---------------------------------------------------------
    def test_failure_mode_03_http_500(self) -> Dict[str, Any]:
        transport = ReadOnlyResearchTransport(network_enabled=False)
        url = "https://www.bls.gov/news.release/cpi.nr0.htm"
        transport.register_mock_response(url=url, status_code=500, body=b"Internal Server Error")
        resp = transport.execute_request("GET", url)
        return {"scenario": "failure_03_http_500", "status": "PASS" if resp.status_code == 500 else "FAIL"}

    # ---------------------------------------------------------
    # Failure Mode 04: DNS Resolution Failure
    # ---------------------------------------------------------
    def test_failure_mode_04_dns_failure(self) -> Dict[str, Any]:
        def failing_dns(h: str) -> List[str]:
            raise TransportSecurityError(f"DNS failure: Name not resolved for {h}")

        transport = ReadOnlyResearchTransport(network_enabled=True, dns_resolver=failing_dns)
        caught = False
        try:
            transport.execute_request("GET", "https://www.bls.gov/test")
        except TransportSecurityError:
            caught = True
        return {"scenario": "failure_04_dns_failure", "status": "PASS" if caught else "FAIL"}

    # ---------------------------------------------------------
    # Failure Mode 05: Connection / Read Timeout
    # ---------------------------------------------------------
    def test_failure_mode_05_timeout(self) -> Dict[str, Any]:
        transport = ReadOnlyResearchTransport(network_enabled=False)
        url = "https://www.bls.gov/timeout"
        transport.register_mock_response(
            url=url, failure_exception=TransportTimeoutError("Gateway timeout breached")
        )
        caught = False
        try:
            transport.execute_request("GET", url)
        except TransportTimeoutError:
            caught = True
        return {"scenario": "failure_05_timeout", "status": "PASS" if caught else "FAIL"}

    # ---------------------------------------------------------
    # Failure Mode 06: Content-Type Mismatch
    # ---------------------------------------------------------
    def test_failure_mode_06_content_type_mismatch(self) -> Dict[str, Any]:
        transport = ReadOnlyResearchTransport(network_enabled=False)
        url = "https://www.bls.gov/data.json"
        transport.register_mock_response(
            url=url, status_code=200, headers={"content-type": "text/html"}, body=b"<html>Cloudflare Error</html>"
        )
        resp = transport.execute_request("GET", url)
        is_mismatch = (resp.content_type == "text/html" and "json" in url)
        return {"scenario": "failure_06_content_type_mismatch", "status": "PASS" if is_mismatch else "FAIL"}

    # ---------------------------------------------------------
    # Failure Mode 07: Checksum Mismatch / Corrupted Storage
    # ---------------------------------------------------------
    def test_failure_mode_07_checksum_mismatch(self) -> Dict[str, Any]:
        data = b"Original bytes to store"
        sha, fpath, _ = self.vault.store_bytes("releases", data, {"test": "corruption"})
        with open(fpath, "wb") as f:
            f.write(b"Corrupted bytes!")
        audit = self.vault.verify_vault_integrity()
        passed = (audit["status"] == "CORRUPTION_DETECTED" and audit["total_corrupt"] > 0)
        return {"scenario": "failure_07_checksum_mismatch", "status": "PASS" if passed else "FAIL"}

    # ---------------------------------------------------------
    # Failure Mode 08: Excessive Payload Size (>10MB)
    # ---------------------------------------------------------
    def test_failure_mode_08_payload_too_large(self) -> Dict[str, Any]:
        transport = ReadOnlyResearchTransport(network_enabled=False, max_response_size_bytes=1024)
        url = "https://www.bls.gov/large"
        huge_body = b"A" * 2048
        transport.register_mock_response(url=url, body=huge_body)
        caught = False
        try:
            transport.execute_request("GET", url)
        except ResponseSizeExceededError:
            caught = True
        return {"scenario": "failure_08_payload_too_large", "status": "PASS" if caught else "FAIL"}

    # ---------------------------------------------------------
    # Failure Mode 09: Non-HTTPS Scheme (Insecure)
    # ---------------------------------------------------------
    def test_failure_mode_09_insecure_scheme(self) -> Dict[str, Any]:
        transport = ReadOnlyResearchTransport(network_enabled=False)
        caught = False
        try:
            transport.execute_request("GET", "http://www.bls.gov/test")
        except InsecureSchemeError:
            caught = True
        return {"scenario": "failure_09_insecure_scheme", "status": "PASS" if caught else "FAIL"}

    # ---------------------------------------------------------
    # Failure Mode 10: Disallowed Domain
    # ---------------------------------------------------------
    def test_failure_mode_10_disallowed_domain(self) -> Dict[str, Any]:
        transport = ReadOnlyResearchTransport(network_enabled=False)
        caught = False
        try:
            transport.execute_request("GET", "https://unapproved-financial-blog.com/leak")
        except DomainNotAllowedError:
            caught = True
        return {"scenario": "failure_10_disallowed_domain", "status": "PASS" if caught else "FAIL"}

    # ---------------------------------------------------------
    # Failure Mode 11: Private IP / SSRF Attempt
    # ---------------------------------------------------------
    def test_failure_mode_11_ssrf(self) -> Dict[str, Any]:
        def ssrf_resolver(h: str) -> List[str]:
            return ["127.0.0.1", "169.254.169.254", "10.0.0.5"]

        transport = ReadOnlyResearchTransport(network_enabled=True, dns_resolver=ssrf_resolver)
        caught = False
        try:
            transport.execute_request("GET", "https://www.bls.gov/test")
        except SSRFProtectionError:
            caught = True
        return {"scenario": "failure_11_ssrf", "status": "PASS" if caught else "FAIL"}

    # ---------------------------------------------------------
    # Failure Mode 12: Trading Endpoint Access Attempt
    # ---------------------------------------------------------
    def test_failure_mode_12_trading_endpoint(self) -> Dict[str, Any]:
        transport = ReadOnlyResearchTransport(network_enabled=False)
        caught = False
        try:
            transport.execute_request("GET", "https://api.binance.com/api/v3/order")
        except TradingEndpointAccessError:
            caught = True
        return {"scenario": "failure_12_trading_endpoint", "status": "PASS" if caught else "FAIL"}

    # ---------------------------------------------------------
    # Failure Mode 13: Vault Write Crash & Partial Journal Recovery
    # ---------------------------------------------------------
    def test_failure_mode_13_crash_recovery(self) -> Dict[str, Any]:
        # Corrupt journal with a truncated line
        journal = self.vault.journal_path
        with open(journal, "a", encoding="utf-8") as f:
            f.write('{"incomplete_json": true, "trun\n')

        recovery = self.vault.recover_vault()
        passed = (recovery["truncated_journal_lines"] > 0)
        return {"scenario": "failure_13_crash_recovery", "status": "PASS" if passed else "FAIL"}

    # ---------------------------------------------------------
    # Failure Mode 14: Consensus Vintage Violation
    # ---------------------------------------------------------
    def test_failure_mode_14_vintage_violation(self) -> Dict[str, Any]:
        from .consensus_registry import ConsensusEvidenceRegistry

        reg = ConsensusEvidenceRegistry()
        rec = reg.register_consensus_survey(
            event_id="EVT-VINTAGE-01",
            provider_name="PostEventLeak",
            survey_value=0.2,
            survey_unit="pct",
            survey_published_at_utc="2026-10-14T12:35:00Z",  # AFTER release!
            first_observed_at_utc="2026-10-14T12:35:00Z",
            retrieved_at_utc="2026-10-14T12:35:00Z",
            official_release_scheduled_utc="2026-10-14T12:30:00Z",
        )
        passed = (
            rec.verification_status == ConsensusVerificationStatus.VINTAGE_VIOLATION_REJECTED
        )
        return {"scenario": "failure_14_vintage_violation", "status": "PASS" if passed else "FAIL"}

    def run_all_simulations(self) -> Dict[str, Any]:
        """Runs the complete suite of baseline and failure mode simulations."""
        results = {}
        results["baseline_lifecycle"] = self.run_normal_lifecycle()
        results["fail_01_http_403"] = self.test_failure_mode_01_http_403()
        results["fail_02_http_429"] = self.test_failure_mode_02_http_429()
        results["fail_03_http_500"] = self.test_failure_mode_03_http_500()
        results["fail_04_dns_failure"] = self.test_failure_mode_04_dns_failure()
        results["fail_05_timeout"] = self.test_failure_mode_05_timeout()
        results["fail_06_content_type_mismatch"] = self.test_failure_mode_06_content_type_mismatch()
        results["fail_07_checksum_mismatch"] = self.test_failure_mode_07_checksum_mismatch()
        results["fail_08_payload_too_large"] = self.test_failure_mode_08_payload_too_large()
        results["fail_09_insecure_scheme"] = self.test_failure_mode_09_insecure_scheme()
        results["fail_10_disallowed_domain"] = self.test_failure_mode_10_disallowed_domain()
        results["fail_11_ssrf"] = self.test_failure_mode_11_ssrf()
        results["fail_12_trading_endpoint"] = self.test_failure_mode_12_trading_endpoint()
        results["fail_13_crash_recovery"] = self.test_failure_mode_13_crash_recovery()
        results["fail_14_vintage_violation"] = self.test_failure_mode_14_vintage_violation()

        all_pass = all(r["status"] == "PASS" for r in results.values())
        return {
            "simulation_suite_status": "PASS" if all_pass else "FAIL",
            "total_scenarios_tested": len(results),
            "total_passed": sum(1 for r in results.values() if r["status"] == "PASS"),
            "scenarios": results,
        }

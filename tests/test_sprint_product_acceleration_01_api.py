"""Unit tests for Sprint Product Acceleration 01: Product Dashboard API Service.

Verifies:
1. All 8 endpoints under /api/v1/product/ return valid HTTP 200 with structured JSON envelopes.
2. Safety contract preservation: TECHNICAL_NO_GO, NOT_GRANTED, PROHIBITED, ZERO edge.
3. Path traversal attacks on /artifacts/preview are strictly rejected (HTTP 403 Forbidden).
4. Sensitive files (.env, private keys, database files) are strictly blocked from preview (HTTP 403).
5. Non-existent artifacts return HTTP 404 Not Found.
6. Research results filtering by category and search term.
7. Verified events loading, pagination, and BLS CPI candidate presence.
8. Governance center operator visibility without exposing secrets.
9. Operations status and storage metrics.
"""

from __future__ import annotations

from http import HTTPStatus
import json
from pathlib import Path
import pytest

from coin_behavior_engine.product.dashboard_api import (
    ProductDashboardApiService,
    MAX_PREVIEW_BYTES,
)


@pytest.fixture
def api() -> ProductDashboardApiService:
    return ProductDashboardApiService()


def test_01_overview_endpoint(api):
    status_code, data = api.handle_request("/api/v1/product/overview")
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"

    # Verify safety contract invariants
    contract = data["safety_contract"]
    assert contract["technical_decision"] == "TECHNICAL_NO_GO"
    assert contract["governance_authorization"] == "NOT_GRANTED"
    assert contract["live_order_execution"] == "PROHIBITED"
    assert contract["directional_trading_eligibility"] == "ZERO"
    assert contract["btcusdt_live_observation"] == "DISABLED"

    # Verify model integrity
    model = data["model_integrity"]
    assert model["version"] == "CBE-0.7.0"
    assert model["status"] == "FROZEN"
    assert model["canonical_artifacts_verified"] == 29

    # Verify qualification
    tests = data["test_qualification"]
    assert tests["full_suite_collected"] == 2107
    assert tests["full_suite_passed"] == 2102
    assert tests["full_suite_failed"] == 5
    assert tests["funding_median_latency_ms"] == 21.38
    assert tests["funding_latency_status"] == "PASS"


def test_02_research_results_endpoint(api):
    status_code, data = api.handle_request("/api/v1/product/research-results")
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["total_canonical"] >= 6
    assert len(data["results"]) >= 6

    # Verify specific canonical studies
    ids = [r["id"] for r in data["results"]]
    assert "RES-FUND-01" in ids
    assert "RES-REGIME-01" in ids
    assert "RES-DURABILITY-01" in ids
    assert "RES-CRYPTO-01" in ids

    # Test filtering by category
    status_code, filtered = api.handle_request(
        "/api/v1/product/research-results",
        {"category": ["Derivatives & Carry"]},
    )
    assert status_code == HTTPStatus.OK
    assert len(filtered["results"]) >= 1
    for r in filtered["results"]:
        assert "derivatives" in r["category"].lower() or "carry" in r["category"].lower()

    # Test search query
    status_code, searched = api.handle_request(
        "/api/v1/product/research-results",
        {"search": ["latency"]},
    )
    assert status_code == HTTPStatus.OK
    assert len(searched["results"]) >= 1


def test_03_market_behavior_endpoint(api):
    status_code, data = api.handle_request("/api/v1/product/market-behavior")
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["market_symbol"] == "BTCUSDT"

    # Regimes
    regimes = data["regime_distribution"]
    regime_names = [r["regime"] for r in regimes]
    assert "NORMAL" in regime_names
    assert "COMPRESSION" in regime_names
    assert "EXPANSION_WATCH" in regime_names
    assert "HIGH_VOLATILITY" in regime_names
    assert "DELEVERAGING_STRESS" in regime_names

    # Check regime flaw disclosure
    assert "safeguards" in data
    assert "x <= x" in data["safeguards"]["regime_flaw_notice"]


def test_04_events_endpoint(api):
    status_code, data = api.handle_request("/api/v1/product/events", {"page": ["1"], "limit": ["10"]})
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert "bls_cpi_candidate" in data

    # Verify BLS Candidate is explicitly UNVERIFIED and NOT_GRANTED
    bls = data["bls_cpi_candidate"]
    assert bls["status"] == "PROPOSED (UNVERIFIED CANDIDATE)"
    assert bls["operator_authorization"] == "NOT_GRANTED"
    assert bls["real_network_access"] == "DISABLED"

    # Check paginated events
    assert data["total_events"] > 0
    assert len(data["events"]) <= 10
    evt0 = data["events"][0]
    assert "event_id" in evt0
    assert "category" in evt0
    assert "headline" in evt0


def test_05_governance_endpoint(api):
    status_code, data = api.handle_request("/api/v1/product/governance")
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"

    gov = data["governance_contract"]
    assert gov["technical_decision"] == "TECHNICAL_NO_GO"
    assert gov["governance_authorization"] == "NOT_GRANTED"
    assert "cryptography" in gov["cryptographic_implementation"]

    operators = data["operator_identities"]
    assert len(operators) >= 3
    op_roles = [op["role"] for op in operators]
    assert "RESEARCH_LEAD" in op_roles
    assert "SECURITY_AUDITOR" in op_roles
    assert "GOVERNANCE_ADMIN" in op_roles

    # Verify zero secrets or private keys leaked
    sec = data["security_assurances"]
    assert sec["private_keys_exposed"] is False
    assert sec["token_secrets_exposed"] is False


def test_06_artifacts_listing_and_filtering(api):
    status_code, data = api.handle_request("/api/v1/product/artifacts", {"page": ["1"], "limit": ["25"]})
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["total_artifacts"] >= 100
    assert len(data["artifacts"]) <= 25

    # Filter by category
    status_code, dur = api.handle_request("/api/v1/product/artifacts", {"category": ["durability"]})
    assert status_code == HTTPStatus.OK
    for a in dur["artifacts"]:
        assert a["category"] == "durability"

    # Filter by extension
    status_code, jsons = api.handle_request("/api/v1/product/artifacts", {"extension": [".json"]})
    assert status_code == HTTPStatus.OK
    for a in jsons["artifacts"]:
        assert a["extension"] == ".json"


def test_07_artifact_preview_security_and_traversal_guards(api):
    # Valid preview: final_go_no_go from research_outputs
    status_code, data = api.handle_request(
        "/api/v1/product/artifacts/preview",
        {"path": ["research_outputs/final_go_no_go_11_23_5b6_5_5c.json"]},
    )
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert "TECHNICAL_NO_GO" in data["content"]
    assert data["is_binary"] is False

    # Path traversal attack attempt 1: ../../
    status_code, err = api.handle_request(
        "/api/v1/product/artifacts/preview",
        {"path": ["../../Windows/System32/drivers/etc/hosts"]},
    )
    assert status_code == HTTPStatus.FORBIDDEN
    assert "Access denied" in err["message"]

    # Path traversal attack attempt 2: relative escape
    status_code, err = api.handle_request(
        "/api/v1/product/artifacts/preview",
        {"path": ["research_outputs/../../pyproject.toml"]},
    )
    assert status_code == HTTPStatus.FORBIDDEN

    # Denylisted file: .env
    status_code, err = api.handle_request(
        "/api/v1/product/artifacts/preview",
        {"path": [".env"]},
    )
    assert status_code == HTTPStatus.FORBIDDEN

    # Non-existent file in allowlisted dir
    status_code, err = api.handle_request(
        "/api/v1/product/artifacts/preview",
        {"path": ["research_outputs/non_existent_artifact_xyz.json"]},
    )
    assert status_code == HTTPStatus.NOT_FOUND


def test_08_operations_endpoint(api):
    status_code, data = api.handle_request("/api/v1/product/operations")
    assert status_code == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["app_name"] == "Coin Behavior Engine (CBE)"
    assert data["model_version"] == "CBE-0.7.0"
    assert data["git_revision"] == "2e7ad236ba07f71eee54dac01d6ffe9c115ba9d9"
    assert data["health_state"] == "HEALTHY"
    assert "storage_status" in data
    assert data["storage_status"]["artifacts_indexed_count"] > 0
    assert data["coolify_deployment_status"]["application_domain"] == "coin.ozelweb.com.tr"


def test_09_unknown_endpoint(api):
    status_code, data = api.handle_request("/api/v1/product/unknown_sub_route")
    assert status_code == HTTPStatus.NOT_FOUND
    assert data["error"] == "Not Found"
    assert "available_endpoints" in data

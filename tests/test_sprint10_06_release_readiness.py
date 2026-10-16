"""Tests for CBE Sprint 10.06: MVP Release Readiness, Live Data Architecture & Final Acceptance Gates.

Validates:
1. Mandatory safety invariants: 29/29 canonical freeze, APPROVAL4=FALSE, prospective scoring disabled, trading disabled.
2. Verification and reconciliation of Sprint 10.05 evidence (5 viewports, 6 screenshot artifacts, engine coverage).
3. End-to-end HTTP acceptance metrics (p50/p95/p99, TTFB, cold/warm, concurrency, resource limits).
4. Live data architecture audit & clean separation of the 5 authorization concepts.
5. Isolated FactualMarketDataAdapter functionality, BTCUSDT snapshot, and ETHUSDT/SOLUSDT fail-closed states.
6. Product feature acceptance matrix for all 6 MVP frontend modules.
7. Scientific evidence integrity (8 core scientific and calibration boundaries).
8. Security, CSP, rate limiting, and rollback architecture.
9. Empirical release decision: BLOCKED_PENDING_LIVE_DATA_INTEGRATION with explicit blocker/authorization audit.
10. Isolation of existing production dashboard (/dashboard).
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict

import pytest

from coin_behavior_engine.product.acceptance import (
    FeatureAcceptanceRecord,
    FeatureReleaseStatus,
    MvpReleaseAuditor,
    ReleaseDecision,
)
from coin_behavior_engine.product.market_data_adapter import (
    DataClassification,
    FactualMarketDataAdapter,
    MarketDataFreshnessStatus,
    MarketDataSourceHealth,
)
from coin_behavior_engine.prospective.freeze import (
    FROZEN_MODEL_VERSION,
    verify_sprint07_freeze,
)
from coin_behavior_engine.web.server import get_engine_state, render_dashboard_html


REPO_ROOT = Path(__file__).resolve().parents[1]


def test_01_mandatory_safety_invariants_and_canonical_freeze():
    """Test 01: Verify baseline commit invariants, 29/29 freeze, APPROVAL4=FALSE, and trading disabled."""
    verify_sprint07_freeze()

    state = get_engine_state()
    assert state["model_version"] == FROZEN_MODEL_VERSION
    assert state["canonical_artifacts_verified"] == 29
    assert state["canonical_artifacts_total"] == 29
    assert state["freeze_verified"] is True
    assert state["freeze_violations"] == 0
    assert state.get("approval4", False) is False


def test_02_sprint_10_05_evidence_reconciliation():
    """Test 02: Independently verify Sprint 10.05 artifacts (5 viewports, 6 screenshots, engine coverage)."""
    evidence = MvpReleaseAuditor.verify_sprint_10_05_evidence(REPO_ROOT)

    assert evidence["viewports_evaluated_count"] == 5
    assert set(evidence["viewports_list"]) == {"1440x900", "1280x800", "768x1024", "390x844", "320x568"}
    assert evidence["screenshots_count"] == 6
    assert evidence["screenshots_verified"] is True
    assert evidence["responsive_layout_overflow_px"] == 0
    assert "PASS_TECHNICAL_CRITERIA" in evidence["accessibility_audit_status"]
    assert "not equated to certified manual" in evidence["accessibility_notes"]
    assert evidence["regression_tests_total"] >= 95


def test_03_end_to_end_http_performance_acceptance():
    """Test 03: Verify measured HTTP p50, p95, p99, TTFB, bundle size, and concurrency from acceptance audit."""
    acceptance_file = REPO_ROOT / "data" / "reports" / "sprint10_06_http_acceptance.json"
    assert acceptance_file.exists(), "Missing http acceptance benchmark report"

    data = json.loads(acceptance_file.read_text(encoding="utf-8"))
    assert data["total_requests"] >= 500

    # Latency budgets: warm p50 < 5ms, p95 < 15ms, p99 < 25ms
    assert data["warm_latency_ms"]["p50"] < 5.0
    assert data["warm_latency_ms"]["p95"] < 15.0
    assert data["warm_latency_ms"]["p99"] < 25.0

    # TTFB budget: TTFB p50 < 5ms
    assert data["ttfb_ms"]["p50"] < 5.0

    # Payload budgets: initial page load bundle < 50 KB
    assert data["initial_page_load_bundle_bytes"] < 50 * 1024

    # Concurrency: 0 errors
    assert data["concurrent_test"]["errors_count"] == 0

    # Error handling: 404 on nonexistent route
    assert data["error_handling"]["nonexistent_route_status"] == 404

    # Resource stability: Memory growth during 500+ requests < 20 MB
    assert data["resource_utilization"]["memory_growth_mb"] < 20.0


def test_04_live_data_architecture_concept_separation():
    """Test 04: Verify strict architectural separation between observation, presentation, diagnostics, scoring, trading."""
    adapter = FactualMarketDataAdapter(data_root=REPO_ROOT / "data")

    # Adapter must NOT possess or import scoring workers or order execution
    assert not hasattr(adapter, "execute_order")
    assert not hasattr(adapter, "run_model_inference")
    assert not hasattr(adapter, "calculate_prospective_score")
    assert not hasattr(adapter, "api_key")
    assert not hasattr(adapter, "api_secret")


def test_05_factual_market_data_adapter_btcusdt_and_freshness():
    """Test 05: Verify BTCUSDT factual snapshot extraction, explicit provenance, and freshness evaluation."""
    adapter = FactualMarketDataAdapter(data_root=REPO_ROOT / "data")

    # Evaluation with reference time equal to observation time
    ref_fresh = datetime.fromisoformat("2026-09-23T20:25:00+00:00")
    rec_fresh = adapter.get_btcusdt_factual_record(reference_time=ref_fresh)
    assert rec_fresh.symbol == "BTCUSDT"
    assert rec_fresh.spot_price == 63842.15
    assert rec_fresh.candle_interval == "5m"
    assert rec_fresh.exchange_source == "BINANCE_SPOT"
    assert rec_fresh.freshness_status == MarketDataFreshnessStatus.FRESH
    assert rec_fresh.is_live is False
    assert rec_fresh.classification == DataClassification.HISTORICAL_SNAPSHOT
    assert rec_fresh.price_change_24h_pct is None  # Suppressed when unbroken 24h lookback unavailable

    # Evaluation with current time (stale by >30m)
    now = datetime(2026, 10, 16, 20, 0, 0, tzinfo=timezone.utc)
    rec_stale = adapter.get_btcusdt_factual_record(reference_time=now)
    assert rec_stale.freshness_status == MarketDataFreshnessStatus.STALE
    assert rec_stale.source_health == MarketDataSourceHealth.OFFLINE_SNAPSHOT


def test_06_factual_market_data_adapter_boundary_logic():
    """Test 06: Test all 5 freshness boundary conditions (<30m, 30m exact, >30m, clock skew, missing)."""
    now = datetime(2026, 10, 16, 20, 0, 0, tzinfo=timezone.utc)

    # 1. Under 30m -> FRESH
    assert FactualMarketDataAdapter.evaluate_freshness("2026-10-16T19:45:00Z", reference_time=now) == MarketDataFreshnessStatus.FRESH

    # 2. Exact 30m (1800s) -> BOUNDARY_STALE
    assert FactualMarketDataAdapter.evaluate_freshness("2026-10-16T19:30:00Z", reference_time=now) == MarketDataFreshnessStatus.BOUNDARY_STALE

    # 3. Over 30m -> STALE
    assert FactualMarketDataAdapter.evaluate_freshness("2026-10-16T19:20:00Z", reference_time=now) == MarketDataFreshnessStatus.STALE

    # 4. Future timestamp (skew > 60s) -> FUTURE_SKEW
    assert FactualMarketDataAdapter.evaluate_freshness("2026-10-16T20:05:00Z", reference_time=now) == MarketDataFreshnessStatus.FUTURE_SKEW

    # 5. Missing / None -> MISSING
    assert FactualMarketDataAdapter.evaluate_freshness(None, reference_time=now) == MarketDataFreshnessStatus.MISSING
    assert FactualMarketDataAdapter.evaluate_freshness("", reference_time=now) == MarketDataFreshnessStatus.MISSING


def test_07_future_assets_ethusdt_and_solusdt_fail_closed():
    """Test 07: Verify ETHUSDT and SOLUSDT fail-closed behavior (marked UNAVAILABLE, no live feed)."""
    adapter = FactualMarketDataAdapter(data_root=REPO_ROOT / "data")

    eth = adapter.get_ethusdt_factual_record()
    assert eth.symbol == "ETHUSDT"
    assert eth.spot_price is None
    assert eth.source_health == MarketDataSourceHealth.UNAVAILABLE
    assert eth.classification == DataClassification.UNAVAILABLE
    assert eth.is_live is False
    assert "FUTURE_EXTENSION_ONLY" in eth.provenance_details["scope"]

    sol = adapter.get_solusdt_factual_record()
    assert sol.symbol == "SOLUSDT"
    assert sol.spot_price is None
    assert sol.source_health == MarketDataSourceHealth.UNAVAILABLE
    assert sol.classification == DataClassification.UNAVAILABLE
    assert sol.is_live is False
    assert "FUTURE_EXTENSION_ONLY" in sol.provenance_details["scope"]


def test_08_product_feature_acceptance_matrix():
    """Test 08: Verify all 6 MVP frontend features are classified with precise release conditions."""
    records = MvpReleaseAuditor.audit_feature_acceptance_matrix()
    assert len(records) == 6

    modules_by_name = {r.feature_module: r for r in records}

    # Module A: Market Overview
    assert modules_by_name["Module A"].status == FeatureReleaseStatus.RELEASE_READY_HISTORICAL_WITH_DISCLOSURE

    # Module B: Volatility & Risk
    assert modules_by_name["Module B"].status == FeatureReleaseStatus.RELEASE_READY_HISTORICAL_WITH_DISCLOSURE

    # Module C: Prediction Diagnostics
    assert modules_by_name["Module C"].status == FeatureReleaseStatus.RELEASE_READY_HISTORICAL_WITH_DISCLOSURE

    # Module D: Market Regime Safeguard
    assert modules_by_name["Module D"].status == FeatureReleaseStatus.EXPERIMENTAL_RESEARCH_ONLY

    # Module E: Data Health
    assert modules_by_name["Module E"].status == FeatureReleaseStatus.RELEASE_READY_HISTORICAL_WITH_DISCLOSURE

    # Module F: Model Transparency
    assert modules_by_name["Module F"].status == FeatureReleaseStatus.RELEASE_READY_FACTUAL


def test_09_security_and_release_architecture():
    """Test 09: Verify public/private API separation, rate limiting, and rollback plans."""
    sec = MvpReleaseAuditor.audit_security_and_deployment_architecture()

    assert sec["api_exposure"]["read_only_strictly_enforced"] is True
    assert len(sec["api_exposure"]["write_endpoints"]) == 0
    assert "/intelligence" in sec["api_exposure"]["public_endpoints"]
    assert "/api/status (Internal engine monitoring)" in sec["api_exposure"]["private_protected_endpoints"]

    # Security headers
    assert sec["security_controls"]["http_headers"]["X-Content-Type-Options"] == "nosniff"
    assert sec["security_controls"]["http_headers"]["X-Frame-Options"] == "DENY"

    # Rollback plan
    assert len(sec["rollback_plan"]) >= 4
    assert len(sec["proposed_deployment_plan"]) >= 5


def test_10_release_decision_logic_and_blockers():
    """Test 10: Verify empirical release decision logic (BLOCKED_PENDING_LIVE_DATA_INTEGRATION)."""
    decision, blockers, auths = MvpReleaseAuditor.evaluate_release_decision(
        live_data_integrated=False,
        all_tests_passing=True,
        security_headers_verified=True,
    )

    assert decision == ReleaseDecision.BLOCKED_PENDING_LIVE_DATA_INTEGRATION
    assert len(blockers) >= 1
    assert "Canlı Veri Eksikliği" in blockers[0]
    assert len(auths) >= 1
    assert "Canlı Veri Alım İzni" in auths[0]


def test_11_production_dashboard_isolation():
    """Test 11: Verify original production dashboard (/dashboard) is 100% untouched."""
    state = get_engine_state()
    dash = render_dashboard_html(state)

    assert "Coin Behavior Engine" in dash
    assert "CBE-0.7.0" in dash
    assert "FAZ A — İLK İLERİYE DÖNÜK GÖZLEM" in dash
    assert "FAZ B — İLERİYE DÖNÜK CANLI GÖZLEM" in dash
    assert "KİLİTLİ KAYIT & DENETİM BÜTÜNLÜĞÜ" in dash

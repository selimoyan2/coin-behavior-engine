"""
CBE — Product Acceleration Sprint 17 Test Suite
Tests for:
1. Disjoint Candidate Filtering Invariant (Candidate windows strictly non-overlapping)
2. Spaced Candidate Filtering Fallback (min_spacing_hours)
3. Multi-Scenario Ranking Stability Indicator & Stability Verdict
4. Explainable 5-Dimension Contribution Decomposition & Sum Parity
5. Sample-Size & Data Coverage Warnings (<24 bars)
6. Deterministic Reproducible Experiment ID (EXP-PAT-V2-*)
7. Scientific Evidence Package Export (HISTORICAL_PATTERN_DISCOVERY_V2_EVIDENCE)
8. Product Dashboard API V2 Endpoints (/search-v2, /compare-v2, /export-evidence)
9. Non-Trading Invariants, Asset Safety & Governance Boundaries
10. Research Workbench V6 HTML Structure & Component Integration
"""

import json
import re
from dataclasses import asdict
from http import HTTPStatus
import pytest

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.product.historical_pattern_discovery import (
    HistoricalPatternDiscoveryEngine,
    PatternCandidateMatch,
    PatternDiscoverySearchResult,
    SimilarityComponentScore,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.dashboard_ui import render_product_dashboard_html


# =========================================================================
# 1. DISJOINT CANDIDATE FILTERING INVARIANT
# =========================================================================

def test_disjoint_candidate_filtering():
    """When disjoint_candidate_filter=True, no accepted candidate window overlaps any other."""
    engine = HistoricalPatternDiscoveryEngine()
    result = engine.search_similar_patterns(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        interval="1h",
        max_candidates=8,
        disjoint_candidate_filter=True,
    )
    assert isinstance(result, PatternDiscoverySearchResult)
    assert result.disjoint_filtering_applied is True
    candidates = result.ranked_candidates
    assert len(candidates) >= 3

    # Verify every pair of candidate windows is strictly disjoint
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            c_a, c_b = candidates[i], candidates[j]
            # Strict non-overlap: either A ends before B starts, or A starts after B ends
            is_disjoint = (c_a.end_utc < c_b.start_utc or c_a.start_utc > c_b.end_utc)
            assert is_disjoint, f"Overlap detected between candidate #{c_a.rank} ({c_a.start_utc}->{c_a.end_utc}) and #{c_b.rank} ({c_b.start_utc}->{c_b.end_utc})"

    # Verify each candidate has is_strictly_disjoint=True
    for c in candidates:
        assert c.is_strictly_disjoint is True
        assert c.overlap_status == "DISJOINT"


def test_spaced_candidate_filtering_fallback():
    """When disjoint_candidate_filter=False, fallback to spacing policy operates cleanly."""
    engine = HistoricalPatternDiscoveryEngine()
    result = engine.search_similar_patterns(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        interval="1h",
        max_candidates=5,
        min_spacing_hours=48,
        disjoint_candidate_filter=False,
    )
    assert result.disjoint_filtering_applied is False
    assert len(result.ranked_candidates) >= 3
    for c in result.ranked_candidates:
        assert c.overlap_status == "SPACED"


# =========================================================================
# 2. RANKING STABILITY EVALUATION
# =========================================================================

def test_ranking_stability_calculation():
    """Ranking stability score is bounded [0.0, 1.0] and verdict is categorical."""
    engine = HistoricalPatternDiscoveryEngine()
    result = engine.search_similar_patterns(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        interval="1h",
        max_candidates=5,
        disjoint_candidate_filter=True,
    )
    assert 0.0 <= result.ranking_stability_score <= 1.0
    assert result.ranking_stability_verdict in ("HIGH_STABILITY", "MODERATE_STABILITY", "SENSITIVE")
    assert isinstance(result.ranking_stability_details, dict)
    assert "scenarios" in result.ranking_stability_details
    scenarios = result.ranking_stability_details["scenarios"]
    assert "volatility_heavy" in scenarios
    assert "regime_heavy" in scenarios
    assert "return_heavy" in scenarios


# =========================================================================
# 3. EXPLAINABLE 5-DIMENSION DECOMPOSITION & SUM PARITY
# =========================================================================

def test_explainable_dimension_contributions():
    """Candidate match contains explicit contribution of all 5 dimensions summing to ~100%."""
    engine = HistoricalPatternDiscoveryEngine()
    result = engine.search_similar_patterns(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        interval="1h",
        max_candidates=3,
        disjoint_candidate_filter=True,
    )
    top_cand = result.ranked_candidates[0]
    expected_dims = {
        "REGIME_COMPOSITION",
        "REALIZED_VOLATILITY",
        "RETURN_DISTRIBUTION",
        "TRANSITION_STRUCTURE",
        "REGIME_PERSISTENCE",
    }
    assert set(top_cand.components.keys()) == expected_dims
    assert set(top_cand.dimension_contributions.keys()) == expected_dims

    total_pct = sum(c.contribution_pct for c in top_cand.components.values())
    assert total_pct == pytest.approx(100.0, abs=0.5)

    # Check Turkish explanation text is populated
    assert len(top_cand.explanation_tr) > 20
    assert "%" in top_cand.explanation_tr


# =========================================================================
# 4. SAMPLE SIZE & COVERAGE WARNINGS
# =========================================================================

def test_coverage_and_sample_size_warnings():
    """Short reference periods (<24 bars) trigger sample size warning."""
    engine = HistoricalPatternDiscoveryEngine()
    # 12-hour window on 1h interval has 13 candles < 24 threshold
    result = engine.search_similar_patterns(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-01T12:00:00Z",
        interval="1h",
        max_candidates=2,
        disjoint_candidate_filter=True,
    )
    assert len(result.coverage_warnings) > 0
    assert any("DÜŞÜK_ÖRNEKLEM_UYARISI" in w for w in result.coverage_warnings)


# =========================================================================
# 5. REPRODUCIBLE EXPERIMENT ID
# =========================================================================

def test_deterministic_reproducible_experiment_id():
    """Calling pattern search twice with identical parameters generates the exact same experiment ID."""
    engine = HistoricalPatternDiscoveryEngine()
    res1 = engine.search_similar_patterns(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        interval="1h",
        max_candidates=5,
        disjoint_candidate_filter=True,
    )
    res2 = engine.search_similar_patterns(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        interval="1h",
        max_candidates=5,
        disjoint_candidate_filter=True,
    )
    assert res1.experiment_id.startswith("EXP-PAT-V2-")
    assert re.match(r"^EXP-PAT-V2-[a-f0-9]{12}$", res1.experiment_id)
    assert res1.experiment_id == res2.experiment_id


# =========================================================================
# 6. EVIDENCE PACKAGE EXPORT
# =========================================================================

def test_export_evidence_package():
    """Evidence package is self-contained, reproducible, and includes governance invariants."""
    engine = HistoricalPatternDiscoveryEngine()
    res = engine.search_similar_patterns(
        reference_start_utc="2022-06-01T00:00:00Z",
        reference_end_utc="2022-06-15T00:00:00Z",
        interval="1h",
        max_candidates=3,
        disjoint_candidate_filter=True,
    )
    pkg = engine.export_evidence_package(res)

    assert pkg["package_type"] == "HISTORICAL_PATTERN_DISCOVERY_V2_EVIDENCE"
    assert pkg["schema_version"] == "2.0.0"
    assert pkg["experiment_id"] == res.experiment_id
    assert pkg["canonical_model"] == f"{FROZEN_MODEL_VERSION} (FROZEN)"
    assert len(pkg["dataset_manifest_sha256"]) == 64
    assert pkg["governance_invariants"]["model_status"] == "STRICTLY_FROZEN"
    assert pkg["governance_invariants"]["live_order_execution"] == "PERMANENTLY_PROHIBITED"
    assert pkg["governance_invariants"]["directional_trading_eligibility"] == 0
    assert len(pkg["legal_disclaimer_tr"]) > 50


# =========================================================================
# 7. PRODUCT DASHBOARD API V2 ENDPOINTS
# =========================================================================

def test_api_search_v2_endpoint():
    """API endpoint /api/v1/product/pattern-discovery/search-v2 returns HTTP 200 with V2 schema."""
    status, res = ProductDashboardApiService.handle_request(
        "/api/v1/product/pattern-discovery/search-v2",
        {
            "reference_start_utc": ["2022-06-01T00:00:00Z"],
            "reference_end_utc": ["2022-06-15T00:00:00Z"],
            "max_candidates": ["3"],
            "disjoint_candidate_filter": ["true"],
        }
    )
    assert status == HTTPStatus.OK
    assert res["status"] == "SUCCESS"
    assert res["disjoint_filtering_applied"] is True
    assert res["experiment_id"].startswith("EXP-PAT-V2-")
    assert len(res["ranked_candidates"]) == 3


def test_api_compare_v2_endpoint():
    """API endpoint /api/v1/product/pattern-discovery/compare-v2 returns HTTP 200."""
    status, res = ProductDashboardApiService.handle_request(
        "/api/v1/product/pattern-discovery/compare-v2",
        {
            "reference_start_utc": ["2022-06-01T00:00:00Z"],
            "reference_end_utc": ["2022-06-15T00:00:00Z"],
            "candidate_start_utc": ["2022-11-01T00:00:00Z"],
            "candidate_end_utc": ["2022-11-15T00:00:00Z"],
            "interval": ["1h"],
        }
    )
    assert status == HTTPStatus.OK
    assert res["status"] == "SUCCESS"
    assert "similarity_analysis" in res
    assert "dimension_breakdown" in res["similarity_analysis"]
    assert "scientific_commentary_tr" in res


def test_api_export_evidence_endpoint():
    """API endpoint /api/v1/product/pattern-discovery/export-evidence returns HTTP 200."""
    status, pkg = ProductDashboardApiService.handle_request(
        "/api/v1/product/pattern-discovery/export-evidence",
        {
            "reference_start_utc": ["2022-06-01T00:00:00Z"],
            "reference_end_utc": ["2022-06-15T00:00:00Z"],
            "max_candidates": ["3"],
            "disjoint_candidate_filter": ["true"],
        }
    )
    assert status == HTTPStatus.OK
    assert pkg["status"] == "SUCCESS"
    assert pkg["package_type"] == "HISTORICAL_PATTERN_DISCOVERY_V2_EVIDENCE"
    assert "experiment_id" in pkg
    assert "governance_invariants" in pkg


# =========================================================================
# 8. NON-TRADING & ASSET SAFETY BOUNDARIES
# =========================================================================

def test_asset_safety_guard():
    """Attempting pattern discovery on assets other than BTCUSDT raises ValueError."""
    engine = HistoricalPatternDiscoveryEngine()
    with pytest.raises(ValueError, match="Asset 'ETHUSDT' is not supported"):
        engine.search_similar_patterns(
            reference_start_utc="2022-06-01T00:00:00Z",
            reference_end_utc="2022-06-15T00:00:00Z",
            asset="ETHUSDT",
        )


def test_live_trading_endpoints_strictly_prohibited():
    """Trading/order endpoints return HTTP 404 (strictly prohibited)."""
    for endpoint in ("/api/v1/orders", "/api/v1/trade", "/api/v1/execute", "/api/v1/order/submit"):
        status, _ = ProductDashboardApiService.handle_request(endpoint, {})
        assert status == HTTPStatus.NOT_FOUND


# =========================================================================
# 9. RESEARCH WORKBENCH V6 HTML STRUCTURE
# =========================================================================

def test_research_workbench_v6_html():
    """Product dashboard HTML contains Workbench V6 and Pattern Discovery V2 elements."""
    html = render_product_dashboard_html()
    assert "Araştırma Tezgahı V6 & Tarihsel Örüntü Keşfi V2 (Sprint 17)" in html
    assert 'id="pat-disjoint-filter"' in html
    assert 'id="btn-export-evidence"' in html
    assert 'id="pat-stability-badge"' in html
    assert 'id="pat-warnings-banner"' in html
    assert "Nisan 2024 (4. Bitcoin Halving)" in html
    assert "Ağustos 2024 (Yen Taşıma Çözülmesi)" in html

"""Comprehensive Test Suite for Sprint 09.33: Research Consolidation, Evidence Registry & Roadmap.

Verifies:
1. Complete inventory of all 25 research hypotheses, strategies, and benchmarks from Sprints 09.20-09.32.
2. Historical dataset exposure ledger with explicit quarantine of Q4 2024, Jan 2025, and Feb 2025.
3. Canonical accounting standards and verification of the mathematical compounding bridge.
4. Binding statistical research policy rules (pre-registration, multiple testing, block bootstrap).
5. Infrastructure quality audit confirming zero lookahead and latency within budget.
6. Next-generation research roadmap and domain feasibility scoring (Domain C ranked #1).
7. Machine-readable JSON artifact validity.
8. Pure compute latency budget strictly under 50 ms.
"""

import json
from pathlib import Path
import time
from typing import Any, Dict, List

import numpy as np
import pytest

from coin_behavior_engine.research.historical.accounting_standard import (
    AccountingConceptDefinition,
    CanonicalAccountingStandard,
)
from coin_behavior_engine.research.historical.evidence_registry import (
    CanonicalEvidenceRegistry,
    DatasetExposureRecord,
    InfrastructureAuditReport,
    ResearchHypothesisRecord,
    StatisticalPolicyRule,
)
from coin_behavior_engine.research.historical.market_regime_intelligence import MarketRegimeEngine
from coin_behavior_engine.research.historical.research_roadmap import (
    ResearchDomainFeasibilityAssessment,
    ResearchRoadmapEvaluator,
    ResearchRoadmapReport,
)


def test_all_25_hypotheses_inventoried_and_verified():
    """Verify that all 25 experiments and benchmarks are cataloged with complete provenance."""
    registry = CanonicalEvidenceRegistry()
    inventory = registry.get_all_hypotheses_inventory()

    assert len(inventory) == 25, f"Expected 25 cataloged experiments, got {len(inventory)}"

    expected_ids = [
        # Technical Patterns (7)
        "H1_OPENING_RANGE_BREAKOUT",
        "H2_OPENING_RANGE_SWEEP_FADE",
        "H3_TREND_PULLBACK_CONTINUATION",
        "H4_VOLATILITY_COMPRESSION_EXPANSION",
        "H5_TREND_CONTINUATION_FLAG",
        "H6_FAILED_BREAKOUT_STRONG_REJECTION",
        "H7_SESSION_TRANSITION_EXPANSION",
        # Behavioral (2)
        "B3_EXHAUSTION_REVERSAL",
        "B5_SESSION_TRANSITION_MOMENTUM_REVERSAL",
        # Cross-Sectional (4)
        "CS1_RELATIVE_MOMENTUM_PERSISTENCE",
        "CS2_LEADERSHIP_ROTATION",
        "CS3_MARKET_BREADTH_CONFIRMATION",
        "CS4_BTC_REGIME_DEPENDENT_MOMENTUM",
        # Capital Preservation (4)
        "CP1_VOLATILITY_EXPOSURE_REDUCTION",
        "CP2_DRAWDOWN_AWARE_CASH",
        "CP3_TREND_REGIME_PROTECTION",
        "CP4_LOW_TURNOVER_SELECTIVE",
        # Regime-Conditioned (3)
        "RC1_TREND_EXPOSURE",
        "RC2_VOLATILITY_DEFENSIVE",
        "RC3_COMPOSITE_QUALITY",
        # Passive Benchmarks (5)
        "PASSIVE_100_CASH",
        "PASSIVE_25_BTC",
        "PASSIVE_50_BTC",
        "PASSIVE_75_BTC",
        "PASSIVE_100_BTC_BUY_AND_HOLD",
    ]

    found_ids = [h.experiment_id for h in inventory]
    for exp_id in expected_ids:
        assert exp_id in found_ids, f"Missing hypothesis ID {exp_id} in registry"

    for h in inventory:
        assert len(h.economic_rationale) > 10
        assert len(h.artifact_references) >= 1
        assert len(h.commit_provenance) >= 8
        assert h.final_verdict in ("REJECTED", "BENCHMARK_VALIDATED", "BENCHMARK_DOMINANT", "EXPLORATORY_ONLY")


def test_dataset_exposure_ledger_contamination_and_quarantine():
    """Verify that all 6 historical partitions are tracked and holdouts are strictly quarantined."""
    registry = CanonicalEvidenceRegistry()
    ledger = registry.get_dataset_exposure_ledger()

    assert len(ledger) == 6

    ledger_map = {d.dataset_id: d for d in ledger}

    # Verify Q4 2024, Jan 2025, and Feb 2025 are permanently quarantined
    q4 = ledger_map["BINANCE_BTC_15M_2024_Q4"]
    assert q4.is_virgin_holdout is False
    assert q4.quarantine_status == "EXPOSED_PERMANENTLY"
    assert q4.exposure_type == "SPENT_CONFIRMATORY_HOLDOUT"

    jan = ledger_map["BINANCE_BTC_15M_JAN_2025"]
    assert jan.is_virgin_holdout is False
    assert jan.quarantine_status == "EXPOSED_PERMANENTLY"
    assert jan.exposure_type == "SPENT_CONFIRMATORY_HOLDOUT"

    feb = ledger_map["BINANCE_BTC_15M_FEB_2025"]
    assert feb.is_virgin_holdout is False
    assert feb.quarantine_status == "EXPOSED_PERMANENTLY"
    assert feb.exposure_type == "SPENT_CONFIRMATORY_HOLDOUT"


def test_canonical_accounting_standard_and_compounding_bridge():
    """Verify approved accounting definitions and test the volatility drag compounding bridge."""
    definitions = CanonicalAccountingStandard.get_canonical_definitions()
    assert len(definitions) >= 10

    def_map = {d.concept_id: d for d in definitions}
    assert "ONE_WAY_TURNOVER" in def_map
    assert "TWO_WAY_TRADED_NOTIONAL" in def_map
    assert "VOLATILITY_DRAG" in def_map
    assert "WARMUP_TIMELINE_PARITY" in def_map

    # Test numerical compounding bridge: mu = 6.47 bps, var ~ 2.36e-4
    rng = np.random.default_rng(42)
    returns = rng.normal(loc=0.000647, scale=0.015, size=2189)
    returns = returns - np.mean(returns) + 0.000647
    mean_bps, vol_drag_bps, geom_bps, comp_pct, naive_pct = CanonicalAccountingStandard.verify_compounding_bridge(returns)

    assert abs(mean_bps - 6.47) < 2.0
    assert vol_drag_bps > 0.0
    assert geom_bps < mean_bps
    # Naive compounded exceeds true volatility-adjusted compounded return
    assert naive_pct > comp_pct


def test_statistical_research_policy_invariants():
    """Verify binding statistical research rules."""
    rules = CanonicalEvidenceRegistry.get_statistical_research_policy()
    assert len(rules) == 6

    rule_ids = [r.rule_id for r in rules]
    assert "RULE_01_PREREGISTRATION_LOCK" in rule_ids
    assert "RULE_02_MULTIPLE_TESTING_CONTROL" in rule_ids
    assert "RULE_03_HOLDOUT_QUARANTINE_NO_REUSE" in rule_ids
    assert "RULE_04_BLOCK_BOOTSTRAP_DEPENDENCE" in rule_ids
    assert "RULE_05_EXPOSURE_MATCHED_BENCHMARKING" in rule_ids
    assert "RULE_06_MINIMUM_SAMPLE_SIZE" in rule_ids


def test_infrastructure_quality_audit_compliance():
    """Verify that infrastructure audit confirms vectorization and latency compliance."""
    audit = CanonicalEvidenceRegistry.audit_infrastructure_quality()
    assert audit.latency_compliance is True
    assert audit.median_pure_compute_latency_ms < 50.0
    assert audit.lookahead_audit_verdict == "ZERO_LOOKAHEAD_VERIFIED_POINT_IN_TIME_ONLY"


def test_research_roadmap_domain_feasibility_ranking():
    """Verify evaluation and ranking of future research domains (Domain C ranked #1)."""
    report = ResearchRoadmapEvaluator.evaluate_all_domains()

    assert len(report.domains) == 3
    assert report.top_recommended_domain == "DOMAIN_C_PERPETUAL_FUNDING_AND_BASIS"
    assert report.ranked_domain_ids[0] == "DOMAIN_C_PERPETUAL_FUNDING_AND_BASIS"

    domain_c = [d for d in report.domains if d.domain_id == "DOMAIN_C_PERPETUAL_FUNDING_AND_BASIS"][0]
    assert domain_c.total_score >= 70.0
    assert domain_c.data_authenticity_score == 10.0
    assert domain_c.historical_coverage_score == 10.0


def test_canonical_registry_json_file_validity():
    """Verify that canonical JSON evidence registry file exists, is valid, and matches schema."""
    json_path = Path("data/reports/canonical_research_evidence_registry.json")
    if not json_path.exists():
        registry = CanonicalEvidenceRegistry()
        registry.generate_canonical_registry_json(json_path)

    assert json_path.exists()
    assert json_path.stat().st_size > 10000

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["total_hypotheses_inventoried"] == 25
    assert data["total_dataset_partitions"] == 6
    assert data["total_statistical_rules"] == 6
    assert "hypotheses_inventory" in data
    assert "dataset_exposure_ledger" in data
    assert "statistical_policy" in data


def test_pure_compute_latency_budget():
    """Verify that pure compute latency across 200 bars is strictly under the 50 ms budget."""
    closes = 40000.0 + np.cumsum(np.random.randn(200) * 50.0)
    highs = closes + 20.0
    lows = closes - 20.0
    opens = closes - 5.0
    volumes = np.random.uniform(10.0, 100.0, 200)
    candles = [
        {
            "open": opens[i],
            "high": highs[i],
            "low": lows[i],
            "close": closes[i],
            "volume": volumes[i],
            "open_time": 1704067200000 + i * 900000,
        }
        for i in range(200)
    ]

    latencies = []
    for _ in range(15):
        t0 = time.perf_counter()
        regime_engine = MarketRegimeEngine(candles)
        _ = [regime_engine.classify_bar(i) for i in range(50, 200, 16)]
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    median_lat = sorted(latencies)[len(latencies) // 2]
    assert median_lat < 50.0, f"Median latency {median_lat:.2f} ms exceeds 50 ms budget."

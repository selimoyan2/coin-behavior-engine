"""Sprint 09.38 — Comprehensive Unit & Forensic Test Suite.

Verifies:
1. Baseline integrity verification and historical margin classification.
2. Forensic reconciliation of funding timestamp deviations (195 records, 1-15 ms jitter).
3. Strictly causal point-in-time feature engineering with decision cutoff (T - 15m) and zero lookahead.
4. Chronological walk-forward benchmark across 5 baselines and 4 candidate predictive models.
5. Directional prediction vs majority class baseline (91.31% positive funding).
6. Statistical significance with Newey-West HAC Diebold-Mariano tests and Holm-Bonferroni correction.
7. Cost-aware break-even analysis (19 bps maker / 36 bps taker vs -1.12 bps worst negative funding).
8. Dynamic carry policy simulation proving negative incremental economic value vs passive carry.
9. Market regime stability and Research Decision Gate classification (STATISTICALLY_INTERESTING_BUT_NOT_ECONOMIC).
10. Pure compute latency budget (< 50 ms) and artifact preservation.
"""

import json
import time
from pathlib import Path

import numpy as np
import pytest

from coin_behavior_engine.research.historical import (
    DynamicCarryPolicyResult,
    EconomicBreakEvenResult,
    FundingTimestampForensicRecord,
    ModelForecastMetrics,
    Sprint38FundingAuditor,
    Sprint38MasterReport,
    compute_diebold_mariano,
    holm_bonferroni_correction,
)


@pytest.fixture(scope="module")
def auditor() -> Sprint38FundingAuditor:
    return Sprint38FundingAuditor()


@pytest.fixture(scope="module")
def master_report(auditor: Sprint38FundingAuditor) -> Sprint38MasterReport:
    report_path = Path("data/reports/sprint09_38_funding_predictability_report.json")
    return auditor.run_full_sprint_audit(output_report_path=report_path)


def test_01_baseline_verification_and_margin_documentation(master_report: Sprint38MasterReport):
    """Test 1: Verify baseline commit, prior sprint artifacts, and margin schedule status."""
    assert master_report.baseline_commit_sha == "3ce9da321308cd92fd29af07c921991a1d7956a1"

    # Prior sprint artifacts must exist and be intact
    assert Path("data/reports/sprint09_36_delta_neutral_forensics_report.json").exists()
    assert Path("data/reports/sprint09_37_carry_accounting_closure_report.json").exists()
    assert Path("data/historical/futures/btcusdt_perp_mark_price_15m_2024_2025.parquet").exists()

    # Verify that historical margin assumptions remain classified as approximate
    with open("data/reports/sprint09_37_carry_accounting_closure_report.json", "r", encoding="utf-8") as f:
        s37_data = json.load(f)
    assert s37_data["mark_price_integrity_report"]["all_14_checksums_verified"] is True
    assert s37_data["mark_price_integrity_report"]["actual_bars_count"] == 40800
    assert s37_data["simulator_classification"] == "READY_FOR_FURTHER_OFFLINE_ECONOMIC_RESEARCH"


def test_02_funding_timestamp_reconciliation(auditor: Sprint38FundingAuditor, master_report: Sprint38MasterReport):
    """Test 2: Reconcile 195 vs 203 records, 1-15 ms jitter, and 100% boundary alignment."""
    record = master_report.timestamp_forensics
    assert record.total_settlements == 1275
    assert record.exact_boundary_count == 1080
    assert record.jittered_count == 195
    assert record.min_jitter_ms == 1
    assert record.max_jitter_ms == 15
    assert record.tolerance_applied_ms == 1000
    assert record.all_aligned_successfully is True
    assert "RECONCILED" in record.forensic_reconciliation_verdict

    # Check distribution: 154 records have 1 ms jitter
    assert record.jitter_distribution.get(1) == 154


def test_03_point_in_time_causality_and_zero_lookahead(auditor: Sprint38FundingAuditor):
    """Test 3: Feature availability timestamps strictly precede settlement (T - 15m)."""
    df_feat = auditor.extract_point_in_time_features()
    assert len(df_feat) == 1275

    interval = 8 * 3600 * 1000
    cutoff_offset = 15 * 60 * 1000

    for i in range(1, len(df_feat)):
        row = df_feat.iloc[i]
        can_ts = row["canonical_ts"]
        dec_ts = row["dec_bar_ts"]

        # Strict causality checks:
        assert dec_ts == can_ts - cutoff_offset
        assert dec_ts < can_ts

        # Lagged funding checks:
        prev_row = df_feat.iloc[i - 1]
        assert row["f_lag1"] == prev_row["funding_rate_bps"]


def test_04_walk_forward_evaluation_sample_size_and_metrics(master_report: Sprint38MasterReport):
    """Test 4: Chronological walk-forward test covers N = 1,185 out-of-sample settlements."""
    evals = {m.model_name: m for m in master_report.model_evaluations}
    assert len(evals) == 9

    # Check sample size
    for m in evals.values():
        assert m.sample_size == 1185

    # Check baseline ordering in continuous metrics:
    # AR(3) and LinearMulti must beat Unconditional Mean and Random Walk in RMSE
    assert evals["ar3"].rmse_bps < evals["uncond_mean"].rmse_bps
    assert evals["linear_multi"].rmse_bps < evals["uncond_mean"].rmse_bps
    assert evals["linear_multi"].rmse_bps < evals["random_walk"].rmse_bps

    # Skill score vs mean for AR(3) and LinearMulti should be ~0.70
    assert evals["ar3"].skill_score_vs_mean > 0.65
    assert evals["linear_multi"].skill_score_vs_mean > 0.70


def test_05_directional_accuracy_vs_majority_class_baseline(master_report: Sprint38MasterReport):
    """Test 5: Explicit comparison against the 91.31% majority class baseline."""
    evals = {m.model_name: m for m in master_report.model_evaluations}
    maj_acc = evals["uncond_mean"].majority_class_accuracy
    assert maj_acc == 0.9131

    # Unconditional mean always predicts positive, achieving 91.31%
    assert evals["uncond_mean"].directional_accuracy == 0.9131
    assert evals["uncond_mean"].balanced_accuracy == 0.5000

    # Random walk (sign persistence) is actually worse than majority baseline:
    assert evals["random_walk"].directional_accuracy < maj_acc

    # Best candidate model (AR3) provides at most +1.2% incremental accuracy over majority class
    inc_acc = evals["ar3"].directional_accuracy - maj_acc
    assert 0.0 < inc_acc < 0.02


def test_06_statistical_significance_and_multiple_testing_correction():
    """Test 6: Newey-West Diebold-Mariano test and Holm-Bonferroni correction."""
    # Test DM function on synthetic loss differential
    np.random.seed(42)
    e_rw = np.random.normal(0, 1.0, 500)
    e_cand = 0.8 * e_rw  # strictly superior model
    stat, p_val = compute_diebold_mariano(e_rw, e_cand)
    assert stat > 3.0
    assert p_val < 0.01

    # Test Holm-Bonferroni correction properties
    p_vals = [0.001, 0.02, 0.04, 0.10]
    adj = holm_bonferroni_correction(p_vals)
    assert adj[0] == 0.004  # 0.001 * 4
    assert adj[1] <= 0.06   # 0.02 * 3
    assert adj[0] <= adj[1] <= adj[2] <= adj[3]


def test_07_cost_aware_break_even_analysis(master_report: Sprint38MasterReport):
    """Test 7: Break-even analysis proves transaction costs exceed negative funding by 17x-68x."""
    be = master_report.break_even_analysis
    assert be.maker_roundtrip_cost_bps == 19.0
    assert be.taker_roundtrip_cost_bps == 36.0
    assert be.observed_min_funding_bps == -1.1235

    # Friction multiple over worst historical negative funding (-1.12 bps)
    assert be.friction_multiple_over_worst_negative_funding_maker >= 16.0
    assert be.friction_multiple_over_worst_negative_funding_taker >= 32.0

    # Friction multiple over average negative funding (-0.28 bps)
    assert be.friction_multiple_over_mean_negative_funding_maker >= 50.0
    assert be.friction_multiple_over_mean_negative_funding_taker >= 100.0


def test_08_dynamic_carry_policy_simulation_negative_incremental_value(master_report: Sprint38MasterReport):
    """Test 8: Dynamic switching policies produce deeply negative incremental value vs passive carry."""
    policies = {p.policy_name: p for p in master_report.policy_simulations}
    assert len(policies) == 4

    # Passive carry net P&L must be strictly positive
    sample_policy = list(policies.values())[0]
    assert sample_policy.passive_net_pnl_maker_usdt > 500.0
    assert sample_policy.passive_net_pnl_taker_usdt > 500.0

    # Every dynamic policy must have NEGATIVE incremental value compared to passive carry
    for p in policies.values():
        assert p.incremental_value_maker_usdt < 0.0
        assert p.incremental_value_taker_usdt < 0.0
        assert p.economic_advantage_achieved is False


def test_09_decision_gate_strict_classification(master_report: Sprint38MasterReport):
    """Test 9: Decision gate strictly classifies signal as STATISTICALLY_INTERESTING_BUT_NOT_ECONOMIC."""
    assert master_report.decision_gate_classification == "STATISTICALLY_INTERESTING_BUT_NOT_ECONOMIC"
    assert "STATISTICALLY_INTERESTING_BUT_NOT_ECONOMIC" in master_report.justification

    # Verify that regimes were broken down
    assert "Q1_2024_BULL_EXPANSION" in master_report.regime_breakdown
    assert "Q2_Q3_2024_CHOP_CONSOLIDATION" in master_report.regime_breakdown
    assert "Q4_2024_ELECTION_RALLY" in master_report.regime_breakdown
    assert "JAN_FEB_2025_RANGEBOUND" in master_report.regime_breakdown


def test_10_pure_compute_latency_and_report_file(master_report: Sprint38MasterReport, auditor: Sprint38FundingAuditor):
    """Test 10: Pure compute latency is < 50 ms and JSON report is written."""
    report_file = Path("data/reports/sprint09_38_funding_predictability_report.json")
    assert report_file.exists()
    assert report_file.stat().st_size > 5000

    with open(report_file, "r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["sprint_id"] == "CBE-09.38"
    assert loaded["decision_gate_classification"] == "STATISTICALLY_INTERESTING_BUT_NOT_ECONOMIC"

    # Verify pure compute latency on in-memory features is strictly under 50 ms
    import gc
    df_feat = auditor.extract_point_in_time_features()
    gc.collect()

    latencies = []
    for _ in range(5):
        t0 = time.perf_counter()
        _ = auditor.run_walk_forward_evaluation(df_feat)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    median_lat = sorted(latencies)[len(latencies) // 2]
    assert median_lat < 50.0, f"Median pure compute latency {median_lat:.2f} ms exceeded 50 ms budget"

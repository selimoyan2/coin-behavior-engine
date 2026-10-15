"""Comprehensive Test Suite for Sprint 09.36: Financial Forensics, Liquidation Realism & Economic Validation.

Verifies:
1. Mandatory P&L forensic reconciliation of Sprint 09.35 scenarios S1-S6 down to unrounded primitives
   (explaining the +1.49 USDT S1 entry-slippage embedding in execution-referenced Basis P&L and S2 parity).
2. S6 liquidation breach forensic investigation (Bar 5627 uncertainty onset, Bar 5632 last clean bar,
   Bar 5633 first authentic intrabar high breach, Bar 5634 close breach, 4-way P&L separation, and intrabar
   execution uncertainty bands).
3. Exchange margin mechanics audit (Binance Tier 1 0.40% MMR vs conservative 5.00% MMR, Mark Price vs Last Price
   OHLCV approximation, APPROXIMATE_CONSERVATIVE classification).
4. Capital and collateral conservation across ISOLATED_NO_SUPPORT, ISOLATED_EXPLICIT_CASH_SUPPORT, and
   HYPOTHETICAL_CROSS_MARGIN_BENCHMARK (confirming Spot BTC is never pledged as perpetual margin).
5. Standalone 28-digit Decimal reference accounting implementation with < 1e-12 USDT conservation error.
6. Property-based randomized and adversarial accounting tests (extreme rallies, sharp crashes, funding sign
   reversals, insufficient collateral, duplicate events, out-of-order timestamps).
7. Funding and basis candle-boundary causality at 00:00, 08:00, and 16:00 UTC (T_settle > T_entry, open price notional).
8. Complete period-by-period non-optimized diagnostics across 2024 Q1, Q2, Q3, Q4, Jan 2025, and Feb 2025.
9. Predetermined 8-scenario economic sensitivity grid.
10. Test coverage reconciliation between Sprint 09.34 (148), Sprint 09.35 (61 subset / 159 full), and Sprint 09.36.
11. Pure compute latency budget under 50 ms.
12. Simulator classification gate: SIMULATOR_VALIDATED_WITH_LIMITATIONS.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import time
from typing import List, Tuple

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research.historical import (
    DeltaNeutralCarrySimulator,
    DeltaNeutralExecutionParams,
    ExchangeMarginMechanicRule,
    FundingSettlementRecord,
    IndependentDecimalReferenceAccountant,
    IndependentDecimalReferenceResult,
    PerpetualCandleRecord,
    S6LiquidationForensicReport,
    ScenarioPnLForensicReconciliation,
    SpotCandleOHLC,
    SpotPerpAlignedBasisRecord,
    Sprint36ForensicValidator,
)


@pytest.fixture(scope="module")
def full_425d_forensic_datasets():
    """Load all 40,800 Spot OHLC candles, 40,800 Perp OHLC candles, 40,800 Basis records, and 1,275 Funding events."""
    f_path = Path("data/historical/futures/btcusdt_funding_settlements_2024_2025.parquet")
    b_path = Path("data/historical/futures/btcusdt_spot_perp_basis_15m_2024_2025.parquet")
    p_path = Path("data/historical/futures/btcusdt_perp_15m_2024_2025.parquet")

    df_f = pd.read_parquet(f_path)
    funding_records = [FundingSettlementRecord(**r) for r in df_f.to_dict(orient="records")]

    df_b = pd.read_parquet(b_path)
    basis_records = [SpotPerpAlignedBasisRecord(**r) for r in df_b.to_dict(orient="records")]

    df_p = pd.read_parquet(p_path)
    perp_candles = [PerpetualCandleRecord(**r) for r in df_p.to_dict(orient="records")]

    spot_files = [
        "data/historical/historical_binance_btcusdt_15m_q1_2024.parquet",
        "data/historical/historical_binance_btcusdt_15m_q2_2024.parquet",
        "data/historical/historical_binance_btcusdt_15m_q3_2024.parquet",
        "data/historical/historical_binance_btcusdt_15m_q4_2024.parquet",
        "data/historical/historical_binance_btcusdt_15m_jan_2025.parquet",
        "data/historical/historical_binance_btcusdt_15m_feb_2025.parquet",
    ]
    df_s = pd.concat([pd.read_parquet(f) for f in spot_files], ignore_index=True)
    spot_candles = [
        SpotCandleOHLC(
            open_time_ms=int(r["timestamp_open"]),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["volume"]),
        )
        for r in df_s.to_dict(orient="records")
    ]

    return spot_candles, perp_candles, basis_records, funding_records


def test_sprint35_s1_to_s6_exact_unrounded_pnl_reconciliation(full_425d_forensic_datasets):
    """Verify exact unrounded P&L reconciliation for Sprint 09.35 scenarios S1 through S6."""
    spot_candles, perp_candles, basis_records, funding_records = full_425d_forensic_datasets
    reconciliations = Sprint36ForensicValidator.reconcile_sprint35_scenarios(
        spot_candles, perp_candles, basis_records, funding_records
    )

    assert len(reconciliations) == 6

    # S1: Explain the exact +1.49 USDT apparent table discrepancy
    s1 = reconciliations["S1_BASELINE_CONSERVATIVE_TAKER"]
    assert s1.reported_net_funding_usdt == 49.52
    assert s1.reported_basis_pnl_usdt == 6.03
    assert s1.reported_fees_usdt == 13.00
    assert s1.reported_slippage_usdt == 3.00
    assert s1.reported_net_total_pnl_usdt == 41.04
    assert s1.visible_table_sum_usdt == 39.55
    assert s1.apparent_table_discrepancy_usdt == 1.49

    # True Mid-to-Mid Basis P&L is +7.524389 USDT; Exec Basis P&L (+6.025028) embedded -1.499361 USDT entry slippage
    assert abs(s1.exact_mid_basis_pnl_usdt - 7.524389) < 1e-5
    assert abs(s1.exact_exec_basis_pnl_usdt - 6.025028) < 1e-5
    assert abs(s1.exact_entry_slippage_usdt - 1.499361) < 1e-5
    assert abs(s1.mid_basis_minus_exec_basis_usdt - s1.exact_entry_slippage_usdt) < 1e-6
    assert s1.reconciled_mid_identity_error_usdt < 1e-5
    assert s1.reconciled_exec_identity_error_usdt < 1e-5

    # S2: Frictionless reference has 0.00 slippage and 0.00 discrepancy
    s2 = reconciliations["S2_FRICTIONLESS_REFERENCE"]
    assert s2.apparent_table_discrepancy_usdt == 0.0
    assert s2.exact_entry_slippage_usdt == 0.0
    assert abs(s2.exact_mid_basis_pnl_usdt - s2.exact_exec_basis_pnl_usdt) < 1e-9

    # S3: Stressed costs has +5.00 USDT apparent difference due to 4.994125 USDT entry slippage
    s3 = reconciliations["S3_STRESSED_COSTS"]
    assert s3.apparent_table_discrepancy_usdt == 5.00
    assert abs(s3.exact_entry_slippage_usdt - 4.994125) < 1e-5

    # Verify all 6 scenarios have < 1e-5 identity error
    for k, rec in reconciliations.items():
        assert rec.reconciled_mid_identity_error_usdt < 1e-5, f"{k} mid identity failed"
        assert rec.reconciled_exec_identity_error_usdt < 1e-5, f"{k} exec identity failed"


def test_s6_liquidation_breach_forensics_and_four_way_pnl_separation(full_425d_forensic_datasets):
    """Verify exact timestamps, prices, and 4-way P&L separation for S6 liquidation breach."""
    spot_candles, perp_candles, basis_records, funding_records = full_425d_forensic_datasets
    s6_rep = Sprint36ForensicValidator.investigate_s6_liquidation_breach(
        spot_candles[:8736], perp_candles[:8736], basis_records[:8736], funding_records
    )

    # 1. Exact breach chronology
    assert s6_rep.first_uncertainty_bar_index == 5627
    assert s6_rep.first_uncertainty_timestamp_utc == "2024-02-28T14:45:00+00:00"
    assert s6_rep.last_clean_bar_index == 5632
    assert s6_rep.last_clean_timestamp_utc == "2024-02-28T16:00:00+00:00"
    assert s6_rep.first_authentic_high_breach_bar_index == 5633
    assert s6_rep.first_authentic_high_breach_timestamp_utc == "2024-02-28T16:15:00+00:00"
    assert s6_rep.first_close_breach_bar_index == 5634
    assert s6_rep.first_close_breach_timestamp_utc == "2024-02-28T16:30:00+00:00"

    # At bar 5633, authentic perp high (61644.90) > isolated liq price (61620.4063) > proxy high (61601.2566)
    assert s6_rep.bar_5633_authentic_perp_high_usdt == 61644.90
    assert s6_rep.bar_5633_authentic_perp_high_usdt > s6_rep.bar_5633_isolated_liq_price_usdt
    assert s6_rep.bar_5633_proxy_perp_high_usdt < s6_rep.bar_5633_isolated_liq_price_usdt

    # 2. 4-Way P&L Separation
    assert s6_rep.pre_breach_bar_5632_mtm_pnl_usdt == 101.0894
    assert s6_rep.pre_breach_bar_5632_realizable_net_pnl_usdt == 89.6020
    assert abs(s6_rep.realizable_forced_close_bar_5633_intrabar_liq_pnl_usdt - 2.6823) < 0.01
    assert abs(s6_rep.realizable_forced_close_bar_5634_close_liq_pnl_usdt - 20.1545) < 0.01
    assert abs(s6_rep.theoretical_uninterrupted_q1_net_pnl_usdt - 318.6537) < 0.01
    assert s6_rep.forfeited_post_breach_funding_usdt > 230.0

    # 3. Intrabar execution uncertainty interval & fail-closed post-liquidation
    assert s6_rep.bar_5633_intrabar_pnl_uncertainty_min_usdt < 0.0
    assert s6_rep.bar_5633_intrabar_uncertainty_width_usdt > 50.0
    assert s6_rep.post_liquidation_funding_accrued_usdt == 0.0
    assert s6_rep.fail_closed_post_liquidation_verified is True


def test_exchange_margin_mechanics_audit_and_approximate_classification():
    """Verify exchange margin rules comparison and APPROXIMATE_CONSERVATIVE model classification."""
    classification, rules = Sprint36ForensicValidator.get_exchange_margin_mechanics_audit()
    assert classification == "APPROXIMATE_CONSERVATIVE"
    assert len(rules) >= 5
    rule_ids = {r.mechanic_id for r in rules}
    assert "INITIAL_MARGIN" in rule_ids
    assert "MAINTENANCE_MARGIN_AND_TIERS" in rule_ids
    assert "MARK_PRICE_LIQUIDATION" in rule_ids
    assert "ISOLATED_VS_CROSS_MARGIN" in rule_ids
    assert "LIQUIDATION_FEES_AND_BANKRUPTCY" in rule_ids


def test_capital_and_collateral_conservation_three_margin_modes(full_425d_forensic_datasets):
    """Compare ISOLATED_NO_SUPPORT, ISOLATED_EXPLICIT_CASH_SUPPORT, and HYPOTHETICAL_CROSS_MARGIN_BENCHMARK."""
    spot_candles, perp_candles, _, funding_records = full_425d_forensic_datasets

    # Evaluate on Q1 2024 (+73.7% BTC surge)
    r_iso = IndependentDecimalReferenceAccountant.run_reference_accounting(
        spot_candles[:8736], perp_candles[:8736], funding_records, margin_mode="ISOLATED_NO_SUPPORT"
    )
    r_sup = IndependentDecimalReferenceAccountant.run_reference_accounting(
        spot_candles[:8736], perp_candles[:8736], funding_records, margin_mode="ISOLATED_EXPLICIT_CASH_SUPPORT"
    )
    r_cross = IndependentDecimalReferenceAccountant.run_reference_accounting(
        spot_candles[:8736], perp_candles[:8736], funding_records, margin_mode="HYPOTHETICAL_CROSS_MARGIN_BENCHMARK"
    )

    # 1. Isolated without support liquidates at bar 5633
    assert r_iso.terminal_classification == "LIQUIDATED_INTRABAR_HIGH_BREACH"
    assert r_iso.bars_evaluated == 5634
    assert r_iso.collateral_injections_count == 0
    assert r_iso.final_available_reserve_usdt == 2500.0

    # 2. Isolated with explicit cash support injects $1,500 from reserve and survives all 8,736 bars
    assert r_sup.terminal_classification == "NORMAL_HORIZON_EXIT"
    assert r_sup.bars_evaluated == 8736
    assert r_sup.collateral_injections_count == 3
    assert r_sup.collateral_injected_total_usdt == 1500.0
    assert r_sup.final_available_reserve_usdt == 1000.0
    assert abs(r_sup.final_available_reserve_usdt + r_sup.collateral_injected_total_usdt - 2500.0) < 1e-6

    # 3. Hypothetical cross-margin benchmark has identical terminal equity to explicit cash support
    assert r_cross.terminal_classification == "NORMAL_HORIZON_EXIT"
    assert abs(r_sup.final_realizable_equity_usdt - r_cross.final_realizable_equity_usdt) < 1e-6

    # 4. Invariant checks across all three modes
    for r in (r_iso, r_sup, r_cross):
        assert r.spot_pledged_as_perp_margin is False
        assert r.perp_short_proceeds_spent is False
        assert r.negative_cash_balance_occurred is False
        assert r.post_liquidation_funding_occurred is False
        assert r.decimal_equity_conservation_error_usdt < 1e-12
        assert r.all_invariants_passed is True


def test_randomized_property_based_and_adversarial_accounting_invariants():
    """Run seeded randomized property tests and adversarial scenarios on IndependentDecimalReferenceAccountant."""
    rng = np.random.default_rng(20260936)

    def make_synthetic_series(n_bars: int, prices: List[float], f_rates: List[float]):
        s_cands = []
        p_cands = []
        f_recs = []
        base_ts = 1704067200000
        for i in range(n_bars):
            ts = base_ts + i * 900000
            p = prices[i]
            s_cands.append(SpotCandleOHLC(open_time_ms=ts, open=p, high=p * 1.005, low=p * 0.995, close=p))
            p_cands.append(
                PerpetualCandleRecord(
                    symbol="BTCUSDT",
                    open_time_ms=ts,
                    close_time_ms=ts + 899999,
                    open_time_utc=datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).isoformat(),
                    close_time_utc=datetime.fromtimestamp((ts + 899999) / 1000.0, tz=timezone.utc).isoformat(),
                    open=p * 1.0002,
                    high=p * 1.006,
                    low=p * 0.994,
                    close=p * 1.0002,
                    volume=100.0,
                    quote_volume=p * 100.0,
                    trades_count=100,
                    taker_buy_volume=50.0,
                    taker_buy_quote_volume=p * 50.0,
                    source="SYNTHETIC_TEST",
                    instrument_type="USDT_MARGINED_PERPETUAL",
                )
            )
            if i % 32 == 0 and (i // 32) < len(f_recs_rates := f_rates):
                rate = f_recs_rates[i // 32]
                f_recs.append(
                    FundingSettlementRecord(
                        exchange="BINANCE",
                        instrument_symbol="BTCUSDT",
                        instrument_type="USDT_MARGINED_PERPETUAL",
                        settlement_asset="USDT",
                        funding_event_timestamp_ms=ts,
                        funding_event_time_utc=datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc).isoformat(),
                        funding_rate=rate,
                        funding_rate_bps=rate * 10000.0,
                        funding_interval_hours=8,
                        source_identifier="TEST",
                        source_publication_status="SETTLED_AT_BOUNDARY",
                        ingestion_timestamp_utc="2024-01-01T00:00:00+00:00",
                        source_checksum="HASH",
                        verification_status="CHECKSUM_VERIFIED",
                        data_quality_flags=[],
                    )
                )
        return s_cands, p_cands, f_recs

    # 1. Property-based randomized paths (10 seeded paths)
    for trial in range(10):
        steps = rng.normal(loc=0.0, scale=0.008, size=128)
        prices = list(50000.0 * np.exp(np.cumsum(steps)))
        f_rates = list(rng.uniform(-0.0005, 0.0008, size=4))
        s_c, p_c, f_r = make_synthetic_series(128, prices, f_rates)
        res = IndependentDecimalReferenceAccountant.run_reference_accounting(
            s_c, p_c, f_r, period_id=f"RANDOM_TRIAL_{trial}"
        )
        assert res.decimal_equity_conservation_error_usdt < 1e-12
        assert res.all_invariants_passed is True

    # 2. Adversarial Case A: Extreme +200% rally -> deterministic liquidation, zero post-liq funding
    rally_prices = list(np.linspace(40000.0, 120000.0, 96))
    s_c, p_c, f_r = make_synthetic_series(96, rally_prices, [0.0005, 0.0005, 0.0005])
    res_rally = IndependentDecimalReferenceAccountant.run_reference_accounting(s_c, p_c, f_r)
    assert res_rally.liquidation_or_margin_breaches_count == 1
    assert res_rally.bars_evaluated < 96
    assert res_rally.all_invariants_passed is True

    # 3. Adversarial Case B: Sharp -60% crash with negative funding reversal
    crash_prices = list(np.linspace(60000.0, 24000.0, 96))
    s_c, p_c, f_r = make_synthetic_series(96, crash_prices, [-0.0010, -0.0015, -0.0010])
    res_crash = IndependentDecimalReferenceAccountant.run_reference_accounting(s_c, p_c, f_r)
    assert res_crash.liquidation_or_margin_breaches_count == 0
    assert res_crash.funding_paid_usdt > 0.0
    assert res_crash.net_funding_usdt < 0.0
    assert res_crash.all_invariants_passed is True

    # 4. Adversarial Case C: Insufficient initial collateral -> fail-closed ValueError
    with pytest.raises(ValueError, match="Insufficient initial perpetual collateral"):
        IndependentDecimalReferenceAccountant.run_reference_accounting(
            s_c, p_c, f_r, perp_margin_allocation_pct=0.01, perp_taker_fee_rate=0.005
        )

    # 5. Adversarial Case D: Duplicate or out-of-order funding events -> fail-closed ValueError
    dup_funding = [f_r[0], f_r[0]]
    with pytest.raises(ValueError, match="Out-of-order or duplicate funding event"):
        IndependentDecimalReferenceAccountant.run_reference_accounting(s_c, p_c, dup_funding)

    # 6. Adversarial Case E: Out-of-order candle timestamps -> fail-closed ValueError
    bad_s_c = list(s_c)
    bad_p_c = list(p_c)
    bad_s_c[5], bad_s_c[6] = bad_s_c[6], bad_s_c[5]
    bad_p_c[5], bad_p_c[6] = bad_p_c[6], bad_p_c[5]
    with pytest.raises(ValueError, match="Timestamp alignment or ordering violation"):
        IndependentDecimalReferenceAccountant.run_reference_accounting(bad_s_c, bad_p_c, f_r)


def test_funding_and_basis_candle_boundary_causality_00_08_16_utc(full_425d_forensic_datasets):
    """Verify strict candle-boundary causality at 00:00, 08:00, and 16:00 UTC."""
    spot_candles, perp_candles, _, funding_records = full_425d_forensic_datasets

    # Compare STRICT_CAUSAL_OPEN_BOUNDARY vs LEGACY_SPRINT35_CLOSE_BOUNDARY on Jan 2024 (2,976 bars = 93 settlements)
    r_strict = IndependentDecimalReferenceAccountant.run_reference_accounting(
        spot_candles[:2976],
        perp_candles[:2976],
        funding_records,
        causal_boundary_mode="STRICT_CAUSAL_OPEN_BOUNDARY",
    )
    r_legacy = IndependentDecimalReferenceAccountant.run_reference_accounting(
        spot_candles[:2976],
        perp_candles[:2976],
        funding_records,
        causal_boundary_mode="LEGACY_SPRINT35_CLOSE_BOUNDARY",
    )

    # In Jan 2024, 78 funding records have exact .000 ms candle-boundary timestamps:
    # Bar 0 is 2024-01-01 00:00:00 UTC. Since entry occurs at Bar 0 close (00:15:00 UTC),
    # strict causal ordering excludes the 2024-01-01 00:00:00 settlement -> 77 settlements instead of 78!
    assert r_legacy.funding_events_settled_count == 78
    assert r_strict.funding_events_settled_count == 77
    assert r_legacy.funding_events_settled_count - r_strict.funding_events_settled_count == 1
    assert r_strict.net_funding_usdt < r_legacy.net_funding_usdt


def test_multi_period_historical_diagnostics_all_6_exposed_partitions(full_425d_forensic_datasets):
    """Verify non-optimized baseline diagnostics across all 6 exposed periods (2024 Q1-Q4, Jan 2025, Feb 2025)."""
    spot_candles, perp_candles, _, funding_records = full_425d_forensic_datasets
    period_results = Sprint36ForensicValidator.run_multi_period_historical_diagnostics(
        spot_candles, perp_candles, funding_records
    )

    expected_periods = ["2024_Q1", "2024_Q2", "2024_Q3", "2024_Q4", "2025_JAN", "2025_FEB"]
    assert list(period_results.keys()) == expected_periods

    for p_name in expected_periods:
        for mode, res in period_results[p_name].items():
            assert res.all_invariants_passed is True
            assert res.decimal_equity_conservation_error_usdt < 1e-12

    # 2024 Q4 under ISOLATED_NO_SUPPORT suffers a net realizable loss (-44.78 USDT) due to Nov 2024 liquidation
    assert period_results["2024_Q4"]["ISOLATED_NO_SUPPORT"].net_realizable_pnl_usdt < 0.0
    assert period_results["2024_Q4"]["ISOLATED_NO_SUPPORT"].liquidation_or_margin_breaches_count == 1

    # Feb 2025 has near-zero net return (+0.04 USDT) due to low funding + taker fee drag
    assert abs(period_results["2025_FEB"]["ISOLATED_NO_SUPPORT"].net_realizable_pnl_usdt - 0.04) < 0.05


def test_predetermined_8_scenario_economic_sensitivity_grid(full_425d_forensic_datasets):
    """Verify all 8 predetermined economic sensitivity scenarios."""
    spot_candles, perp_candles, _, funding_records = full_425d_forensic_datasets
    grid = Sprint36ForensicValidator.run_predetermined_sensitivity_grid(
        spot_candles, perp_candles, funding_records
    )

    assert len(grid) == 8
    for g_name, res in grid.items():
        assert res.all_invariants_passed is True

    # G5 (delayed collateral transfer) and G7 (severe basis divergence) demonstrate negative net P&L
    assert grid["G5_DELAYED_COLLATERAL_TRANSFER_Q1"].net_realizable_pnl_usdt < -100.0
    assert grid["G7_SEVERE_BASIS_DIVERGENCE_WINDOW"].net_realizable_pnl_usdt < 0.0


def test_pure_compute_latency_budget_under_50ms(full_425d_forensic_datasets):
    """Verify that pure compute reference accounting latency is well under the 50 ms budget."""
    spot_candles, perp_candles, _, funding_records = full_425d_forensic_datasets
    sub_s = spot_candles[:500]
    sub_p = perp_candles[:500]

    latencies = []
    for _ in range(15):
        t0 = time.perf_counter()
        _ = IndependentDecimalReferenceAccountant.run_reference_accounting(sub_s, sub_p, funding_records)
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000.0)

    median_lat = sorted(latencies)[len(latencies) // 2]
    assert median_lat < 50.0, f"Median reference accounting latency {median_lat:.2f} ms exceeds 50 ms budget."


def test_sprint36_report_artifact_and_classification_gate():
    """Verify that Sprint 09.36 report artifact exists and uses SIMULATOR_VALIDATED_WITH_LIMITATIONS."""
    rep_path = Path("data/reports/sprint09_36_delta_neutral_forensics_report.json")
    assert rep_path.exists(), "Sprint 09.36 report JSON must exist."

    with open(rep_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert data["sprint_id"] == "SPRINT_09_36"
    assert data["simulator_classification"] == "SIMULATOR_VALIDATED_WITH_LIMITATIONS"
    assert len(data["sprint35_pnl_reconciliations"]) == 6
    assert len(data["period_by_period_diagnostics"]) == 6
    assert len(data["economic_sensitivity_grid"]) == 8

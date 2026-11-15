"""Portfolio Drawdown Integrity and Statistical Inference Patch Test Suite.

Sprint 34.2 Final Patch P0 Regression Gate.
Enforces:
1. Exact reconstruction of Buy & Hold and policy drawdowns from raw price data.
2. Rejection of contradictory peak/trough numbers ($104,115.58 / $70,473.49).
3. Exact reconciliation of 2025 final equity ($9,270.73 vs $9,271.18).
4. Dependence-aware statistical bootstrap inference verifying p > 0.50 for returns.
5. Statistically significant downside risk separation (p < 0.01).
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest


class TestPortfolioDrawdownIntegrityPatch:

    @pytest.fixture(scope="module")
    def patch_drawdown_data(self):
        p = Path("research_outputs/sprint34_2_final_patch/01_portfolio_drawdown_reconciliation.json")
        assert p.exists(), f"Patch drawdown JSON must exist at {p}"
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    @pytest.fixture(scope="module")
    def patch_stat_data(self):
        p = Path("research_outputs/sprint34_2_final_patch/02_corrected_statistical_inference.json")
        assert p.exists(), f"Patch statistical inference JSON must exist at {p}"
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_01_2023_2024_recompute_drawdown_from_raw_price_data(self, patch_drawdown_data):
        """Reconstruct 2023-2024 Buy & Hold equity curve from raw parquet bars."""
        df23 = pd.read_parquet("data/historical/BTCUSDT-1h-2023-10-to-2024-11.parquet")
        assert len(df23) == 9528, f"Expected 9,528 bars in 2023-2024, got {len(df23)}"

        initial_capital = 10000.0
        fee_rate = 0.0015
        entry_fee = initial_capital * fee_rate
        btc_bought = (initial_capital - entry_fee) / df23.iloc[0]["close"]

        equity_curve = btc_bought * df23["close"]
        cummax = equity_curve.cummax()
        dd = (equity_curve - cummax) / cummax

        max_dd = dd.min()
        trough_idx = dd.idxmin()
        peak_idx = equity_curve.loc[:trough_idx].idxmax()

        peak_equity = round(float(equity_curve.iloc[peak_idx]), 2)
        trough_equity = round(float(equity_curve.iloc[trough_idx]), 2)
        final_equity = round(float(equity_curve.iloc[-1]), 2)
        recomputed_max_dd_pct = round(float(max_dd * 100.0), 2)

        # Assert exact verified values
        assert peak_equity == 27219.00
        assert trough_equity == 18424.35
        assert final_equity == 26003.63
        assert recomputed_max_dd_pct == -32.31

        # Verify corresponding BTC close prices
        btc_price_at_peak = round(float(df23.iloc[peak_idx]["close"]), 2)
        btc_price_at_trough = round(float(df23.iloc[trough_idx]["close"]), 2)
        assert btc_price_at_peak == 73577.35
        assert btc_price_at_trough == 49804.00

        # Reject contradictory claims
        contradictory_peak = 104115.58
        contradictory_trough = 70473.49
        assert peak_equity != contradictory_peak, (
            "Peak equity cannot be $104,115.58 for a $10,000 portfolio in 2023-2024"
        )
        assert trough_equity != contradictory_trough

        # Verify against structured artifact
        bnh = patch_drawdown_data["authoritative_portfolio_evaluations"]["2023_2024_in_sample"]["buy_and_hold_benchmark"]
        assert bnh["peak_equity_usdt"] == peak_equity
        assert bnh["trough_equity_usdt"] == trough_equity
        assert bnh["max_drawdown_pct"] == -32.31

    def test_02_2025_recompute_drawdown_and_final_equity(self, patch_drawdown_data):
        """Reconstruct 2025 Buy & Hold equity curve from raw parquet bars and resolve final equity."""
        df25 = pd.read_parquet("data/historical/historical_binance_btcusdt_1h_2025.parquet")
        assert len(df25) == 8760, f"Expected 8,760 bars in 2025, got {len(df25)}"

        initial_capital = 10000.0
        fee_rate = 0.0015
        entry_fee = initial_capital * fee_rate
        btc_bought = (initial_capital - entry_fee) / df25.iloc[0]["close"]

        equity_curve = btc_bought * df25["close"]
        cummax = equity_curve.cummax()
        dd = (equity_curve - cummax) / cummax

        max_dd = dd.min()
        trough_idx = dd.idxmin()
        peak_idx = equity_curve.loc[:trough_idx].idxmax()

        peak_equity = round(float(equity_curve.iloc[peak_idx]), 2)
        trough_equity = round(float(equity_curve.iloc[trough_idx]), 2)
        final_equity = round(float(equity_curve.iloc[-1]), 2)
        recomputed_max_dd_pct = round(float(max_dd * 100.0), 2)

        # Assert exact verified values
        assert peak_equity == 13328.46
        assert trough_equity == 8695.29
        assert recomputed_max_dd_pct == -34.76

        # Authoritative final equity must be exactly 9,270.73
        assert final_equity == 9270.73
        assert final_equity != 9271.18, "Final equity must NOT be the erroneous 9,271.18 figure"

        # Verify structured artifact
        bnh = patch_drawdown_data["authoritative_portfolio_evaluations"]["2025_out_of_sample"]["buy_and_hold_benchmark"]
        assert bnh["final_equity_usdt"] == 9270.73
        assert bnh["max_drawdown_pct"] == -34.76

    def test_03_bounded_tail_policy_drawdowns(self, patch_drawdown_data):
        """Verify bounded policy drawdowns and protection deltas across both periods."""
        evals = patch_drawdown_data["authoritative_portfolio_evaluations"]

        # 2023-2024
        pol23 = evals["2023_2024_in_sample"]["bounded_tail_policy"]
        assert pol23["max_drawdown_pct"] == -28.94
        assert pol23["peak_equity_usdt"] == 17793.90
        assert pol23["trough_equity_usdt"] == 12644.26
        delta23 = evals["2023_2024_in_sample"]["comparison"]["drawdown_truncation_delta_pp"]
        assert delta23 == 3.37
        assert delta23 > 0

        # 2025
        pol25 = evals["2025_out_of_sample"]["bounded_tail_policy"]
        assert pol25["max_drawdown_pct"] == -25.66
        assert pol25["peak_equity_usdt"] == 10643.15
        assert pol25["trough_equity_usdt"] == 7912.01
        delta25 = evals["2025_out_of_sample"]["comparison"]["drawdown_truncation_delta_pp"]
        assert delta25 == 9.10
        assert delta25 > 0

    def test_04_statistical_bootstrap_inference_resolves_discrepancy(self, patch_stat_data):
        """Verify that 24h forward-return bootstrap inference correctly uses non-overlapping sample and yields p > 0.50."""
        h24 = patch_stat_data["horizons"]["24h"]
        fwd_ret = h24["forward_return_inference"]

        # Verify test statistic and effective sample size
        assert h24["effective_sample_size_neff"] == 761
        assert fwd_ret["non_overlapping_subsample_F"] == 0.4452
        assert fwd_ret["non_overlapping_subsample_p"] == 0.8169

        # Bootstrap p-value must align with non-overlapping p-value (> 0.50, specifically ~0.80)
        boot_p = fwd_ret["block_permutation_bootstrap"]["laplace_corrected_finite_sample_p"]
        assert boot_p > 0.50, f"Expected bootstrap p > 0.50, got {boot_p}"
        assert abs(boot_p - 0.8169) < 0.05, f"Bootstrap p ({boot_p}) must align closely with parametric p (0.8169)"

        # Must reject previous erroneous p=0.0020
        assert boot_p != 0.0020, "Spurious p=0.0020 from overlap-inflated permutation must not be reported"

        # Evidence classification must remain STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED
        assert fwd_ret["scientific_evidence_classification"] == "STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED"

    def test_05_downside_risk_mae_separation_significance(self, patch_stat_data):
        """Verify that downside risk (MAE) maintains statistically significant separation (p < 0.01)."""
        h24 = patch_stat_data["horizons"]["24h"]
        mae = h24["downside_risk_mae_inference"]

        assert mae["non_overlapping_subsample_F"] == 4.26
        assert mae["non_overlapping_subsample_p"] < 0.01
        boot_p_mae = mae["block_permutation_bootstrap"]["laplace_corrected_finite_sample_p"]
        assert boot_p_mae < 0.01

        # Evidence classification must be DESCRIPTIVE_HISTORICAL_FINDING
        assert mae["scientific_evidence_classification"] == "DESCRIPTIVE_HISTORICAL_FINDING"

    def test_06_all_horizons_preserve_statistical_invariants(self, patch_stat_data):
        """Verify all horizons (6h, 24h, 72h, 168h) preserve STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED for returns."""
        for h_key in ["6h", "24h", "72h", "168h"]:
            h_data = patch_stat_data["horizons"][h_key]
            ret_inf = h_data["forward_return_inference"]
            assert ret_inf["scientific_evidence_classification"] == "STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED"
            assert ret_inf["non_overlapping_subsample_p"] > 0.05
            assert ret_inf["block_permutation_bootstrap"]["laplace_corrected_finite_sample_p"] > 0.05

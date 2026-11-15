"""Portfolio Accounting Reconciliation Integrity Test Suite.

Sprint 34.2 P0 Regression Gate A.
Enforces that authoritative valuation ledgers, transaction records, and narrative reports
are 100% numerically synchronized and reject contradictory claims.
"""

import json
from pathlib import Path
import pytest


class TestPortfolioReconciliationIntegrity:

    @pytest.fixture(scope="module")
    def reconstruction_data(self):
        json_path = Path("research_outputs/sprint34_2_final_reconciliation/02_independent_portfolio_reconstruction.json")
        assert json_path.exists(), "Reconstructed portfolio ledger JSON must exist"
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def test_01_accounting_standard_and_metadata(self, reconstruction_data):
        assert reconstruction_data["accounting_standard"] == "CBE-PORTFOLIO-RECONCILED-V1.2"
        assert reconstruction_data["attribution_tier"] == "CANONICAL_COMPATIBLE_DERIVED_OUTPUT"
        assert "discrepancy_resolutions" in reconstruction_data
        res = reconstruction_data["discrepancy_resolutions"]
        assert "drawdown_discrepancy_resolution" in res
        assert "transaction_cost_discrepancy_resolution" in res

    def test_02_2023_2024_authoritative_drawdown_and_rejection_of_stale_36_79(self, reconstruction_data):
        r23 = reconstruction_data["results"]["2023_2024_in_sample"]
        policy = r23["bounded_tail_policy"]
        bnh = r23["buy_and_hold_benchmark"]
        delta = r23["drawdown_comparison"]["drawdown_truncation_delta_pp"]

        # Authoritative verified figures
        assert policy["max_drawdown_pct"] == -28.94
        assert bnh["max_drawdown_pct"] == -32.31
        assert delta == +3.37
        assert delta > 0, "Policy must truncate drawdown relative to Buy & Hold in 2023-2024"

        # Explicitly reject contradictory statement
        contradictory_drawdown = -36.79
        assert policy["max_drawdown_pct"] != contradictory_drawdown, (
            "Regression error: Narrative figure -36.79% must NOT be reported as the multi-regime policy drawdown"
        )

    def test_03_2025_authoritative_drawdown(self, reconstruction_data):
        r25 = reconstruction_data["results"]["2025_out_of_sample"]
        policy = r25["bounded_tail_policy"]
        bnh = r25["buy_and_hold_benchmark"]
        delta = r25["drawdown_comparison"]["drawdown_truncation_delta_pp"]

        assert policy["max_drawdown_pct"] == -25.66
        assert bnh["max_drawdown_pct"] == -34.76
        assert delta == +9.10
        assert delta > 0

    def test_04_fee_summation_matches_reported_down_to_cents(self, reconstruction_data):
        ledgers = reconstruction_data["authoritative_ledgers"]

        # 2023-2024
        trades_23 = ledgers["2023_2024_transactions"]
        assert len(trades_23) == 409
        reported_fees_23 = reconstruction_data["results"]["2023_2024_in_sample"]["bounded_tail_policy"]["total_friction_costs"]
        assert reported_fees_23 == 2685.40
        sum_exact_23 = round(sum(t["fee_exact"] for t in trades_23), 2)
        assert sum_exact_23 == reported_fees_23

        # Reject contradictory narrative fee
        assert reported_fees_23 != 5876.32

        # 2025
        trades_25 = ledgers["2025_transactions"]
        assert len(trades_25) == 366
        reported_fees_25 = reconstruction_data["results"]["2025_out_of_sample"]["bounded_tail_policy"]["total_friction_costs"]
        assert reported_fees_25 == 1403.15
        sum_exact_25 = round(sum(t["fee_exact"] for t in trades_25), 2)
        assert sum_exact_25 == reported_fees_25

        # Reject contradictory narrative fee
        assert reported_fees_25 != 4120.45

    def test_05_conservation_of_value_across_all_transactions(self, reconstruction_data):
        ledgers = reconstruction_data["authoritative_ledgers"]
        for period_key in ["2023_2024_transactions", "2025_transactions"]:
            trades = ledgers[period_key]
            for t in trades:
                delta_cash = t["cash_after_exact"] - t["cash_before_exact"]
                delta_btc = t["btc_after_exact"] - t["btc_before_exact"]
                price = t["close_price_exact"]
                delta_btc_val = delta_btc * price
                net_change = delta_cash + delta_btc_val
                # Net change must equal exactly -fee_exact
                assert abs(net_change + t["fee_exact"]) < 1e-4, (
                    f"Conservation of value violated on trade {t['trade_id']}: net_change={net_change}, fee={t['fee_exact']}"
                )

    def test_06_full_valuation_ledger_completeness(self, reconstruction_data):
        ledgers = reconstruction_data["authoritative_ledgers"]
        assert ledgers["2023_2024_valuation_bars_count"] == 9528
        assert len(ledgers["2023_2024_valuation_ledger"]) == 9528
        assert ledgers["2025_valuation_bars_count"] == 8760
        assert len(ledgers["2025_valuation_ledger"]) == 8760

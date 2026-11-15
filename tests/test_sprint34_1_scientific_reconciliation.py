"""Comprehensive Test Suite for Sprint 34.1 Scientific Reconciliation, Data Recovery & Deployment Forensics.

Validates:
1. Constructor side-effect removal & pre-calibrated frozen lockbox loading.
2. Point-in-time per-bar fallback evaluation (zero middle-row sampling).
3. 100% Prefix invariance across multi-horizon prefix slices.
4. Reconciled portfolio valuation ledger & event categorization.
5. Statistical overlap correction, effective degrees of freedom & non-overlapping tests.
6. Hardened offline importer validation & zero-synthesis invariant.
7. Historical dataset registry & partition statuses (2026-10 PARTIAL, 2026-11 MISSING).
8. Dashboard UI status badges and multi-month controls.
"""

from calendar import monthrange
import json
from pathlib import Path
import sys
import tempfile
import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from coin_behavior_engine.market_state.engine import FallbackLevel, UnifiedMarketStateEngine
from coin_behavior_engine.product.btc_timing_research.canonical_model_research_bridge import (
    CanonicalAttributionTier,
    CanonicalModelResearchBridge,
    CausalCalibrationMode,
    FROZEN_DISCOVERY_THRESHOLDS,
)
from coin_behavior_engine.product.dashboard_ui import render_product_dashboard_html
from coin_behavior_engine.product.dataset_registry import (
    DatasetPartitionRecord,
    DatasetStatus,
    HistoricalDatasetRegistry,
)
from scripts.import_offline_historical_partition import (
    detect_and_normalize_timestamps,
    import_partition_atomic,
    validate_and_harden_partition,
)


class TestSprint341ScientificReconciliation:

    # 1. Constructor Side-Effect Removal & Frozen Lockbox
    def test_01_bridge_constructor_loads_frozen_lockbox_without_parquet_fit(self):
        bridge = CanonicalModelResearchBridge()
        assert bridge.engine.is_fitted is True
        assert bridge.model_version == "CBE-0.7.0"
        assert bridge.model_status == "STRICTLY_FROZEN"
        assert bridge.engine.tail_thresholds_95["24h"] == 0.02
        assert bridge.engine.jump_thresholds["24h"] == 0.04

    def test_02_frozen_lockbox_manifest_and_file_exist(self):
        pkl_path = Path("data/models/cbe_070_canonical_frozen_lockbox.pkl")
        manifest_path = Path("data/models/cbe_070_canonical_frozen_lockbox_manifest.json")
        assert pkl_path.exists()
        assert manifest_path.exists()

        with open(manifest_path, "r", encoding="utf-8") as f:
            m = json.load(f)
        assert m["model_version"] == "CBE-0.7.0"
        assert m["model_status"] == "STRICTLY_FROZEN"
        assert m["total_bars"] == 2000
        assert m["discovery_start_utc"] == "2023-10-01T00:00:00Z"
        assert m["discovery_end_utc"] == "2023-12-23T07:00:00Z"

    # 2. Point-in-Time Per-Bar Fallback Evaluation
    def test_03_point_in_time_fallback_evaluation_no_middle_row_sampling(self):
        bridge = CanonicalModelResearchBridge()

        # Construct synthetic dataframe where first 20 bars lack derivatives, but last 20 have them
        n = 40
        dates = pd.date_range("2024-01-01", periods=n, freq="1h", tz="UTC")
        df = pd.DataFrame({
            "datetime": dates,
            "open_time": (dates.astype(np.int64) // 10**6),
            "open": 50000.0,
            "high": 50100.0,
            "low": 49900.0,
            "close": 50000.0,
            "volume": 100.0,
            "basis_level": [np.nan] * 20 + [-0.01] * 20,
            "oi_change_1h": [np.nan] * 20 + [0.01] * 20,
        })

        res = bridge.evaluate_historical_dataset(df, causal_mode=CausalCalibrationMode.PREDECLARED_FROZEN)
        # Should evaluate without errors and produce active fallback
        assert res.total_bars == 40
        assert res.active_fallback_level in (FallbackLevel.SPOT_DERIVATIVES_U1.value, FallbackLevel.CORE_BASELINE_U2.value)

    # 3. Prefix Invariance Guarantee
    def test_04_prefix_invariance_under_point_in_time_fallbacks(self):
        bridge = CanonicalModelResearchBridge()
        dates = pd.date_range("2024-01-01", periods=100, freq="1h", tz="UTC")
        np.random.seed(42)
        close_prices = 50000.0 + np.cumsum(np.random.randn(100) * 150.0)

        df = pd.DataFrame({
            "datetime": dates,
            "open_time": (dates.astype(np.int64) // 10**6),
            "open": close_prices,
            "high": close_prices + 50.0,
            "low": close_prices - 50.0,
            "close": close_prices,
            "volume": 1000.0,
        })

        res_full = bridge.evaluate_historical_dataset(df, causal_mode=CausalCalibrationMode.PREDECLARED_FROZEN)
        reg_full = res_full.classified_series["canonical_regime"].values

        # Test slices at k=24, k=48, k=72
        for k in [24, 48, 72]:
            sub_df = df.iloc[:k]
            res_sub = bridge.evaluate_historical_dataset(sub_df, causal_mode=CausalCalibrationMode.PREDECLARED_FROZEN)
            reg_sub = res_sub.classified_series["canonical_regime"].values
            # All bars up to k must match exactly
            np.testing.assert_array_equal(reg_sub, reg_full[:k])

    # 4. Portfolio Reconciliation & Event Categorization
    def test_05_portfolio_reconciliation_event_categories_and_drawdown(self):
        rec_path = Path("research_outputs/sprint34_1_scientific_data_deployment_closure/02_portfolio_ledger_reconciliation.json")
        assert rec_path.exists()

        with open(rec_path, "r", encoding="utf-8") as f:
            rec = json.load(f)

        assert rec["accounting_standard"] == "CBE-PORTFOLIO-RECONCILED-V1.1"
        res23 = rec["results"]["2023_2024_in_sample"]
        res25 = rec["results"]["2025_out_of_sample"]

        for r in [res23, res25]:
            counts = r["event_counts"]
            assert "SIGNAL_EVENTS" in counts
            assert "POSITION_CHANGES" in counts
            assert "REBALANCE_EVENTS" in counts
            assert "EXECUTED_TRADES" in counts
            assert "COST_BEARING_TRANSACTIONS" in counts
            assert counts["EXECUTED_TRADES"] == counts["REBALANCE_EVENTS"] + 1

            # Invariance: initial capital preserved at start minus fee
            assert r["buy_and_hold"]["initial_capital"] == 10000.0
            assert r["bounded_tail_policy"]["initial_capital"] == 10000.0

        # Verify drawdown truncation is explicitly calculated
        assert res23["reconciled_drawdown_delta"]["drawdown_delta_pp"] > 0
        assert res25["reconciled_drawdown_delta"]["drawdown_delta_pp"] > 0

    # 5. Statistical Claims Audit
    def test_06_statistical_claims_audit_effective_sample_size_and_verdicts(self):
        stats_path = Path("research_outputs/sprint34_1_scientific_data_deployment_closure/04_statistical_claims_audit.json")
        assert stats_path.exists()

        with open(stats_path, "r", encoding="utf-8") as f:
            s = json.load(f)

        h24 = s["horizons"]["24h"]
        assert h24["overlap_ratio_pct"] == 95.83
        assert h24["effective_sample_size_neff"] < 1000
        # Return non-overlapping p-value must establish lack of statistical significance
        assert h24["forward_return_inference"]["non_overlapping_subsample_p"] > 0.05
        assert h24["forward_return_inference"]["scientific_verdict"] == "STATISTICAL_SIGNIFICANCE_NOT_ESTABLISHED"
        # Risk (MAE) separation must remain valid
        assert h24["forward_risk_mae_inference"]["scientific_verdict"] == "DESCRIPTIVE_HISTORICAL_FINDING"

    # 6. Hardened Offline Importer Integrity
    def test_07_offline_importer_deduplication_and_zero_synthesis(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            # Create synthetic raw CSV with duplicate and un-normalized time
            raw_csv = tmp_path / "raw_test.csv"
            raw_csv.write_text(
                "open_time,open,high,low,close,volume\n"
                "1700000000000,50000,50100,49900,50050,10\n"
                "1700000000000,50000,50100,49900,50050,10\n"  # Duplicate
                "1700003600000,50050,50200,50000,50150,15\n"
            )

            target_parquet = tmp_path / "imported.parquet"
            report = import_partition_atomic(raw_csv, target_parquet, expected_interval_minutes=60)

            assert target_parquet.exists()
            assert report["raw_rows"] == 3
            assert report["clean_rows"] == 2
            assert report["duplicates_removed"] == 1
            assert report["synthesis_applied"] is False
            assert report["validation_passed"] is True

    def test_08_offline_importer_rejects_candle_physics_violation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            raw_csv = tmp_path / "corrupt.csv"
            # High < Close violation
            raw_csv.write_text(
                "open_time,open,high,low,close,volume\n"
                "1700000000000,50000,49000,48000,50050,10\n"
            )
            with pytest.raises(ValueError, match="violates candle physics"):
                validate_and_harden_partition(raw_csv, expected_interval_minutes=60)

    # 7. Dataset Registry Reconciliation
    def test_09_dataset_registry_october_partial_and_november_missing(self):
        registry = HistoricalDatasetRegistry()
        rec_oct = registry.audit_monthly_partition(2026, 10)
        # In Sprint 34.1, October was PARTIAL_VERIFIED (24 rows).
        # In Sprint 35, October was fully recovered to COMPLETE_VERIFIED (744 1h rows).
        assert rec_oct.status in (DatasetStatus.COMPLETE_VERIFIED.value, DatasetStatus.PARTIAL_VERIFIED.value)
        if rec_oct.status == DatasetStatus.COMPLETE_VERIFIED.value:
            assert rec_oct.row_count >= 742
            assert rec_oct.completeness_pct >= 99.0
        else:
            assert rec_oct.row_count == 24
            assert rec_oct.completeness_pct < 10.0

        rec_nov = registry.audit_monthly_partition(2026, 11)
        # In Sprint 34.1, November was MISSING (0 rows).
        # In Sprint 35, November was partially registered (PARTIAL_VERIFIED, 358 1h rows).
        assert rec_nov.status in (DatasetStatus.MISSING.value, DatasetStatus.PARTIAL_VERIFIED.value)
        if rec_nov.status == DatasetStatus.PARTIAL_VERIFIED.value:
            assert rec_nov.row_count > 0
            assert "KISMİ DOĞRULANMIŞ VERİ" in rec_nov.coverage_notes
        else:
            assert rec_nov.row_count == 0
            assert "VERİ HENÜZ MEVCUT DEĞİL" in rec_nov.coverage_notes

    def test_10_dataset_registry_full_audit_distribution(self):
        reg_file = Path("research_outputs/sprint34_1_scientific_data_deployment_closure/10_dataset_registry_reconciliation.json")
        assert reg_file.exists()

        with open(reg_file, "r", encoding="utf-8") as f:
            d = json.load(f)

        assert d["summary"]["total_partitions_audited"] == 59
        assert d["summary"]["status_distribution"]["COMPLETE_VERIFIED"] == 57
        assert d["summary"]["status_distribution"]["PARTIAL_VERIFIED"] == 1
        assert d["summary"]["status_distribution"]["MISSING"] == 1
        assert d["summary"]["status_distribution"]["INVALID"] == 0

    # 8. Dashboard UI Badges & Navigation Controls
    def test_11_dashboard_ui_renders_status_badges_and_month_options(self):
        html = render_product_dashboard_html()
        assert "candle-data-status-badge" in html
        assert "candle-data-status-badge-2" in html
        # Accepts Sprint 34.1 initial badges or Sprint 35 upgraded badges
        assert ("EKİM 2026: KISMİ DOĞRULANMIŞ VERİ" in html or "EKİM 2026: TAM DOĞRULANMIŞ VERİ" in html)
        assert ("KASIM 2026: VERİ HENÜZ MEVCUT DEĞİL" in html or "KASIM 2026: KISMİ DOĞRULANMIŞ VERİ" in html)
        assert "TAM DOĞRULANMIŞ VERİ" in html

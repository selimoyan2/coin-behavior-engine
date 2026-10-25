"""
Sprint Product Acceleration 08 — Comprehensive Automated Regression Suite
Tests:
1. Operations Console (intake discovery, path safety, preview ticket, operator auth, derivation, audit log)
2. Multi-Asset Historical Research (catalog discovery, fail-closed missing data, cross-asset synchronization)
3. Macro Event Comparison (T0 alignment, MFE/MAE, vol shift, contamination, 2-event delta)
4. Regime Drift Sensitivity Lab (PSI/JSD thresholds, min sample size, frozen model invariant)
5. Reproducible Research Reports (JSON/CSV, manifest hash, formula injection defense, Turkish disclaimer)
6. Server-side HTTP API routing and Governance Invariants
"""

import csv
from datetime import datetime, timezone
from http import HTTPStatus
import io
import json
import os
from pathlib import Path
import tempfile
import pytest

from coin_behavior_engine.product.operations_console import OperationsConsoleEngine
from coin_behavior_engine.product.multi_asset import MultiAssetCatalogEngine
from coin_behavior_engine.product.macro_comparison import MacroEventComparisonEngine
from coin_behavior_engine.product.regime_drift import RegimeDriftEngine
from coin_behavior_engine.product.research_reports import ResearchReportGenerator, sanitize_csv_value
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService


class TestOperationsConsole:
    """Tests for Phase B: Secure Data Operations Console."""

    def test_01_intake_candidates_discovery(self):
        intake_dir = OperationsConsoleEngine.get_intake_dir()
        assert intake_dir.exists()
        candidates = OperationsConsoleEngine.list_intake_candidates()
        assert isinstance(candidates, list)

    def test_02_path_traversal_rejection(self):
        res = OperationsConsoleEngine.create_import_preview("../../etc/passwd")
        assert res.get("status") == "error"
        assert res.get("error") == "SECURITY_VIOLATION"

        res2 = OperationsConsoleEngine.create_import_preview("sub/dir/file.parquet")
        assert res2.get("status") == "error"
        assert res2.get("error") == "SECURITY_VIOLATION"

    def test_03_preview_ticket_and_validation(self):
        intake_dir = OperationsConsoleEngine.get_intake_dir()
        test_file = intake_dir / "BTCUSDT-5m-2026-10-test.parquet"
        
        # Create a small valid parquet for testing
        import pandas as pd
        df = pd.DataFrame([
            {"open_time": 1790812800000 + i * 300000, "open": 65000.0 + i, "high": 65100.0 + i, "low": 64900.0 + i, "close": 65050.0 + i, "volume": 10.5}
            for i in range(10)
        ])
        df.to_parquet(test_file)

        try:
            res = OperationsConsoleEngine.create_import_preview(test_file.name, declared_symbol="BTCUSDT", declared_interval="5m")
            assert res.get("status") == "success"
            prev_id = res.get("preview_id")
            assert prev_id.startswith("prev_")
            ticket = res.get("preview")
            assert ticket["record_count"] == 10
            assert ticket["validation_verdict"] == "VALIDATED"
            assert len(ticket["source_sha256"]) == 64
        finally:
            if test_file.exists():
                test_file.unlink()

    def test_04_unauthorized_publication_rejection(self):
        res = OperationsConsoleEngine.publish_import("prev_nonexistent", operator_token="wrong_token", confirmed=True)
        assert res.get("status") == "error"
        assert res.get("error") == "UNAUTHORIZED"

    def test_05_production_mutation_latch(self, monkeypatch):
        monkeypatch.setenv("CBE_ENV", "production")
        res = OperationsConsoleEngine.publish_import("prev_123", operator_token="authorized_test_token", confirmed=True)
        assert res.get("status") == "error"
        assert "MUTATIONS_PERMANENTLY_BLOCKED_IN_PRODUCTION" in res.get("message")

    def test_06_audit_log_append_and_retrieval(self):
        OperationsConsoleEngine._record_audit_log(
            operation_id="test_audit_01",
            action="TEST_ACTION",
            actor="test_runner",
            source_hash="abcd1234efgh5678",
            verdict="SUCCESS",
        )
        trail = OperationsConsoleEngine.get_audit_trail(limit=10)
        assert any(t.get("operation_id") == "test_audit_01" for t in trail)


class TestMultiAssetResearch:
    """Tests for Phase C: Multi-Asset Historical Research Foundation."""

    def test_07_symbol_discovery_and_catalog(self):
        engine = MultiAssetCatalogEngine()
        catalog = engine.discover_symbols()
        assert "BTCUSDT" in catalog
        assert "ETHUSDT" in catalog
        assert "SOLUSDT" in catalog
        assert catalog["BTCUSDT"].status == "AVAILABLE"
        assert catalog["ETHUSDT"].status == "UNAVAILABLE_NO_DATA"
        assert catalog["SOLUSDT"].status == "UNAVAILABLE_NO_DATA"

    def test_08_fail_closed_zero_synthetic_data(self):
        engine = MultiAssetCatalogEngine()
        ok, candles, err = engine.load_symbol_candles("ETHUSDT")
        assert not ok
        assert len(candles) == 0
        assert "FAIL_CLOSED" in err
        assert "sentetik" in err.lower()

    def test_09_cross_asset_time_series_alignment(self):
        # Self-alignment of BTCUSDT across two offset samples
        candles_a = [
            {"timestamp_utc": f"2026-09-01T{h:02d}:00:00Z", "close": 60000.0 + h * 10, "open": 60000.0, "volume": 100.0}
            for h in range(24)
        ]
        candles_b = [
            {"timestamp_utc": f"2026-09-01T{h:02d}:00:00Z", "close": 3000.0 + h * 2, "open": 3000.0, "volume": 500.0}
            for h in range(24)
        ]
        res = MultiAssetCatalogEngine.compare_assets(candles_a, candles_b, symbol_a="BTCUSDT", symbol_b="ETHUSDT")
        assert res.get("status") == "SUCCESS"
        assert res.get("aligned_bars") == 24
        assert "overall_pearson_correlation" in res["metrics"]
        assert res["metrics"]["overall_pearson_correlation"] > 0.99  # perfectly colinear returns


class TestMacroEventComparison:
    """Tests for Phase D: Macro Event Synchronized Comparison."""

    def test_10_load_verified_macro_events(self):
        events = MacroEventComparisonEngine.load_events()
        assert len(events) >= 200
        cat_counts = {}
        for ev in events:
            cat_counts[ev.event_category] = cat_counts.get(ev.event_category, 0) + 1
        assert "US_INFLATION" in cat_counts
        assert "US_MONETARY_POLICY" in cat_counts

    def test_11_t0_impact_study_metrics(self):
        events = MacroEventComparisonEngine.load_events()
        # Find an event in 2022 where candle data exists
        ev = next(e for e in events if e.event_id == "EVT-BLS-CPI-20220112")
        res = MacroEventComparisonEngine.analyze_event_impact(ev, interval="1h", pre_hours=12, post_hours=12)
        assert res.get("status") == "SUCCESS"
        assert "pre_return_pct" in res["metrics"]
        assert "post_return_pct" in res["metrics"]
        assert "mfe_pct" in res["metrics"]
        assert "mae_pct" in res["metrics"]
        assert "volatility_shift_ratio" in res["metrics"]
        assert "volume_multiplier" in res["metrics"]
        assert len(res["trajectory"]) > 0

    def test_12_two_event_synchronized_comparison(self):
        events = MacroEventComparisonEngine.load_events()
        ev1 = events[0].event_id
        ev2 = events[1].event_id
        res = MacroEventComparisonEngine.compare_two_events(ev1, ev2, interval="1h", window_hours=12)
        assert res.get("status") == "SUCCESS"
        assert "event_a" in res
        assert "event_b" in res
        assert "delta_metrics" in res


class TestRegimeDriftSensitivity:
    """Tests for Phase E: Regime Drift Sensitivity Lab."""

    def test_13_regime_drift_threshold_parameterization(self):
        res = RegimeDriftEngine.analyze_drift_for_months(
            baseline_month="2026-08",
            target_month="2026-09",
            psi_threshold_moderate=0.08,
            psi_threshold_significant=0.20,
        )
        assert res.get("status") == "success"
        telemetry = res.get("drift_telemetry", {})
        assert "population_stability_index" in telemetry
        assert "jensen_shannon_divergence" in telemetry
        sens = res.get("sensitivity_parameters", {})
        assert sens.get("psi_threshold_moderate") == 0.08
        assert sens.get("model_mutation_prohibited") is True

    def test_14_min_sample_size_warning(self):
        res = RegimeDriftEngine.analyze_drift_for_months(
            baseline_month="2026-08",
            target_month="2026-09",
            min_sample_bars=100000,  # Unattainable threshold to force warning
        )
        assert res.get("status") == "success"
        warn = res.get("drift_telemetry", {}).get("sample_size_warning")
        assert warn is not None
        assert "minimum güven eşiğinin" in warn


class TestReproducibleResearchReports:
    """Tests for Phase F: Reproducible Historical Research Report Generator."""

    def test_15_period_comparison_report(self):
        res = ResearchReportGenerator.generate_period_comparison_report("2026-08", "2026-09", interval="1h", export_format="csv")
        assert res.get("report_id", "").startswith("RPT-PER-COMP-")
        assert res.get("model_version") == "CBE-0.7.0"
        assert "manifest_hash" in res["dataset_provenance"]
        assert "Yatırım tavsiyesi" in res["disclaimer_tr"]
        assert "csv_content" in res
        assert "# Report ID" in res["csv_content"]

    def test_16_macro_event_report(self):
        res = ResearchReportGenerator.generate_macro_event_report("EVT-BLS-CPI-20220112", export_format="json")
        assert res.get("report_id", "").startswith("RPT-MACRO-")
        assert res.get("model_version") == "CBE-0.7.0"
        assert res.get("results", {}).get("status") == "SUCCESS"

    def test_17_formula_injection_defense(self):
        assert sanitize_csv_value("=cmd|'/C calc'!A0") == "'=cmd|'/C calc'!A0"
        assert sanitize_csv_value("+12345") == "'+12345"
        assert sanitize_csv_value("-50.2") == "'-50.2"
        assert sanitize_csv_value("@SUM(A1:A10)") == "'@SUM(A1:A10)"
        assert sanitize_csv_value("Normal Text") == "Normal Text"
        assert sanitize_csv_value(100.5) == 100.5


class TestGovernanceInvariants:
    """Tests for Core Governance & Safety Policies."""

    def test_18_governance_invariants_frozen(self):
        status, gov = ProductDashboardApiService.handle_request("/api/v1/product/governance")
        assert status == HTTPStatus.OK
        contract = gov.get("governance_contract", {})
        assert contract.get("technical_decision") == "TECHNICAL_NO_GO"
        assert contract.get("governance_authorization") == "NOT_GRANTED"
        assert contract.get("production_token_issued") is False
        
        caps = gov.get("capabilities_matrix", [])
        obs = next((c for c in caps if c.get("capability") == "PROSPECTIVE_LIVE_OBSERVATION"), None)
        assert obs and obs["status"] == "DISABLED"
        order = next((c for c in caps if c.get("capability") == "ORDER_EXECUTION"), None)
        assert order and order["status"] == "PERMANENTLY_PROHIBITED"

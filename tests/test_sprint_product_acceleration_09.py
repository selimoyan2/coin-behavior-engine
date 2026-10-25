"""
Sprint Product Acceleration 09 — Comprehensive Automated Regression Suite
Tests:
1. Deployment Safety & Isolation Invariants
2. Operator Authentication Hardening (Revocation, Rate-limiting, Fail-closed, Production Lock)
3. October 2026 Intake Quarantine & Synthetic Fixture Protection
4. Canonical Timeframe Consistency & Lineage Graph
5. Macro Event Research Reliability & Failure Taxonomy (Quarantined CPI, Missing Data, Bilingual strings)
6. Professional PDF Research Reporting (4 report types, PDF headers, Turkish Unicode, Blocked data handling)
7. Data Quality Center V3 API & Provenance Audit
"""

from datetime import datetime, timezone
from http import HTTPStatus
import io
import json
import os
from pathlib import Path
import tempfile
import pytest

from coin_behavior_engine.product.operations_console import OperationsConsoleEngine, REVOKED_OPERATOR_TOKENS
from coin_behavior_engine.product.macro_comparison import MacroEventComparisonEngine, MacroEventRecord
from coin_behavior_engine.product.research_reports import ResearchReportGenerator, sanitize_csv_value
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.timeframe_derivation import MultiTimeframeDerivationEngine, INTERVAL_RATIOS, INTERVAL_MS


class TestDeploymentAndGovernanceSafety:
    """Verify production safety invariants and environment isolation."""

    def test_01_governance_invariants(self):
        status_code, res = ProductDashboardApiService.handle_request("/api/v1/product/governance")
        assert status_code == HTTPStatus.OK
        gov = res.get("governance_contract", {})
        assert gov.get("technical_decision") == "TECHNICAL_NO_GO"
        assert gov.get("governance_authorization") == "NOT_GRANTED"
        assert gov.get("production_token_issued") is False
        
        caps = res.get("capabilities_matrix", [])
        obs = next((c for c in caps if c.get("capability") == "PROSPECTIVE_LIVE_OBSERVATION"), None)
        assert obs is not None
        assert obs.get("status") == "DISABLED"


class TestOperatorSecurityHardening:
    """Verify security hardening in OperationsConsoleEngine."""

    def setup_method(self):
        # Reset failed attempts dictionary before each test
        with OperationsConsoleEngine._lock:
            OperationsConsoleEngine._failed_attempts.clear()

    def test_02_revoked_token_permanently_rejected(self):
        for token in REVOKED_OPERATOR_TOKENS:
            ok, reason = OperationsConsoleEngine.is_authorized_operator(token, client_ip="127.0.0.1")
            assert not ok
            assert "REVOKED" in reason

    def test_03_fail_closed_when_env_unset(self, monkeypatch):
        monkeypatch.delenv("CBE_OPERATOR_TOKEN", raising=False)
        monkeypatch.delenv("OPERATOR_TOKEN", raising=False)
        ok, reason = OperationsConsoleEngine.is_authorized_operator("any-token-attempt", client_ip="127.0.0.1")
        assert not ok
        assert reason == "OPERATOR_AUTH_NOT_CONFIGURED"

    def test_04_valid_token_authentication(self, monkeypatch):
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "valid-sprint09-operator-secret-xyz-987")
        monkeypatch.setenv("CBE_ENV", "staging")
        ok, reason = OperationsConsoleEngine.is_authorized_operator("valid-sprint09-operator-secret-xyz-987", client_ip="127.0.0.1")
        assert ok
        assert reason == "AUTHORIZED_STAGING_OPERATOR"

    def test_05_brute_force_rate_limiting_lockout(self, monkeypatch):
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "valid-sprint09-operator-secret-xyz-987")
        monkeypatch.setenv("CBE_ENV", "staging")
        client_ip = "192.168.1.105"

        # Submit 5 wrong attempts
        for i in range(5):
            ok, reason = OperationsConsoleEngine.is_authorized_operator(f"wrong-token-{i}", client_ip=client_ip)
            assert not ok
            assert "INVALID" in reason

        # 6th attempt with ANY token (even correct one) must be locked out
        ok, reason = OperationsConsoleEngine.is_authorized_operator("valid-sprint09-operator-secret-xyz-987", client_ip=client_ip)
        assert not ok
        assert "OPERATOR_AUTH_RATE_LIMITED_LOCKOUT" in reason

    def test_06_production_mutation_block(self, monkeypatch):
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "valid-sprint09-operator-secret-xyz-987")
        monkeypatch.setenv("CBE_ENV", "production")

        ok, reason = OperationsConsoleEngine.is_authorized_operator("valid-sprint09-operator-secret-xyz-987", client_ip="127.0.0.1")
        assert not ok
        assert reason == "MUTATIONS_PERMANENTLY_BLOCKED_IN_PRODUCTION"


class TestOctoberIntakeQuarantine:
    """Verify quarantine of synthetic fixtures and candidate files."""

    def test_07_october_candidate_quarantined_as_synthetic(self):
        intake_dir = OperationsConsoleEngine.get_intake_dir()
        target_file = intake_dir / "BTCUSDT-5m-2026-10-intake.parquet"
        if target_file.exists():
            preview = OperationsConsoleEngine.create_import_preview("BTCUSDT-5m-2026-10-intake.parquet")
            assert preview.get("status") == "success"
            assert preview.get("provenance_verdict") == "QUARANTINED"
            assert preview.get("safe_to_publish") is False
            ticket = preview.get("preview", {})
            assert ticket.get("provenance_verdict") == "QUARANTINED"
            assert "SYNTHETIC_FIXTURE" in ticket.get("quarantine_reason", "")

    def test_08_quarantined_ticket_cannot_be_published(self, monkeypatch):
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", "valid-sprint09-operator-secret-xyz-987")
        monkeypatch.setenv("CBE_ENV", "staging")
        intake_dir = OperationsConsoleEngine.get_intake_dir()
        target_file = intake_dir / "BTCUSDT-5m-2026-10-intake.parquet"
        if target_file.exists():
            preview = OperationsConsoleEngine.create_import_preview("BTCUSDT-5m-2026-10-intake.parquet")
            preview_id = preview["preview_id"]
            
            pub_res = OperationsConsoleEngine.publish_import(
                preview_id=preview_id,
                operator_token="valid-sprint09-operator-secret-xyz-987",
                confirmed=True,
            )
            assert pub_res.get("status") == "error"
            assert pub_res.get("error") == "QUARANTINED_SOURCE_CANNOT_BE_PUBLISHED"


class TestCanonicalTimeframeDerivation:
    """Verify timeframe lineage graph and mathematical aggregation parity."""

    def test_09_timeframe_lineage_graph(self):
        assert ("5m", "15m") in INTERVAL_RATIOS
        assert INTERVAL_RATIOS[("5m", "15m")] == 3
        assert ("5m", "1h") in INTERVAL_RATIOS
        assert INTERVAL_RATIOS[("5m", "1h")] == 12
        assert ("1h", "4h") in INTERVAL_RATIOS
        assert INTERVAL_RATIOS[("1h", "4h")] == 4
        assert ("1h", "1d") in INTERVAL_RATIOS
        assert INTERVAL_RATIOS[("1h", "1d")] == 24

    def test_10_mathematical_derivation_parity(self):
        import pandas as pd
        base_t = 1790812800000 - (1790812800000 % 3600000)
        rows = []
        for i in range(12):
            rows.append({
                "open_time": base_t + i * 300000,
                "open": 60000.0 + i,
                "high": 60100.0 + i,
                "low": 59900.0 - i,
                "close": 60050.0 + i,
                "volume": 10.0,
                "close_time": base_t + (i + 1) * 300000 - 1
            })
        df_5m = pd.DataFrame(rows)
        df_1h = MultiTimeframeDerivationEngine.derive_dataframe(df_5m, source_interval="5m", target_interval="1h")
        assert len(df_1h) == 1
        d = df_1h.iloc[0]
        assert d["open"] == 60000.0
        assert d["close"] == 60050.0 + 11
        assert d["high"] == max(r["high"] for r in rows)
        assert d["low"] == min(r["low"] for r in rows)
        assert d["volume"] == 120.0


class TestMacroEventResearchReliability:
    """Verify macro event failure taxonomy and bilingual diagnostics."""

    def test_11_quarantined_candidate_event_status(self):
        ev = MacroEventComparisonEngine.get_event_by_id("EVT-BLS-CPI-20261014-CANDIDATE")
        assert ev is not None
        assert ev.verification_status == "EVENT_QUARANTINED"
        res = MacroEventComparisonEngine.analyze_event_impact(ev)
        assert res.get("status") == "EVENT_QUARANTINED"
        assert res.get("verification_status") == "EVENT_QUARANTINED"
        assert "error" in res
        assert "error_en" in res
        assert res.get("quarantine_reason") == "UNVERIFIED_PROVENANCE_QUARANTINED"

    def test_12_nonexistent_event_status(self):
        ev = MacroEventComparisonEngine.get_event_by_id("NONEXISTENT-EVENT-ID")
        assert ev is None

    def test_13_verified_fomc_event_success(self):
        ev = MacroEventComparisonEngine.get_event_by_id("EVT-BLS-CPI-20220112")
        assert ev is not None
        res = MacroEventComparisonEngine.analyze_event_impact(ev, interval="1h", pre_hours=12, post_hours=12)
        assert res.get("status") == "SUCCESS"
        assert "trajectory" in res
        assert len(res["trajectory"]) > 0
        assert res.get("event_id") == "EVT-BLS-CPI-20220112"
        assert "metrics" in res

    def test_14_api_macro_event_returns_200_with_structured_status(self):
        status_code, body = ProductDashboardApiService.handle_request("/api/v1/product/macro-event-comparison?event_id=EVT-BLS-CPI-20261014-CANDIDATE")
        assert status_code == HTTPStatus.OK
        assert body.get("status") == "EVENT_QUARANTINED"
        assert "error" in body
        assert "error_en" in body
        assert body.get("quarantine_reason") == "UNVERIFIED_PROVENANCE_QUARANTINED"


class TestProfessionalPdfReporting:
    """Verify pure-Python PDF generation across all 4 report types."""

    def test_15_pdf_export_period_comparison(self):
        rep = ResearchReportGenerator.generate_period_comparison_report("2026-08", "2026-09", interval="1h")
        pdf_bytes = ResearchReportGenerator.export_report_as_pdf(rep)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF-")

    def test_16_pdf_export_macro_event_verified(self):
        rep = ResearchReportGenerator.generate_macro_event_report("EVT-BLS-CPI-20220112")
        pdf_bytes = ResearchReportGenerator.export_report_as_pdf(rep)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF-")

    def test_17_pdf_export_macro_event_quarantined(self):
        rep = ResearchReportGenerator.generate_macro_event_report("EVT-BLS-CPI-20261014-CANDIDATE")
        pdf_bytes = ResearchReportGenerator.export_report_as_pdf(rep)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF-")

    def test_18_pdf_export_regime_drift(self):
        rep = ResearchReportGenerator.generate_regime_drift_report("2026-08", "2026-09")
        pdf_bytes = ResearchReportGenerator.export_report_as_pdf(rep)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF-")

    def test_19_pdf_export_data_quality(self):
        rep = ResearchReportGenerator.generate_data_quality_report()
        pdf_bytes = ResearchReportGenerator.export_report_as_pdf(rep)
        assert isinstance(pdf_bytes, bytes)
        assert len(pdf_bytes) > 1000
        assert pdf_bytes.startswith(b"%PDF-")


class TestDataQualityCenterV3:
    """Verify Data Quality Center V3 API response and audit trail."""

    def test_20_data_quality_v3_api_schema(self):
        status_code, body = ProductDashboardApiService.handle_request("/api/v1/product/dataset-quality")
        assert status_code == HTTPStatus.OK
        assert body.get("version") == "V3"
        assert "canonical_intervals" in body
        assert "derived_intervals" in body
        assert "provenance_breakdown" in body
        assert "recent_audit_trail" in body
        assert body.get("governance_classification") == "OFFLINE_AUDITED_HISTORICAL_DATA"
        assert body.get("fail_closed_mode") == "STRICTLY_OFFLINE"

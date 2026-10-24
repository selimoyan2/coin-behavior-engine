"""Sprint Product Acceleration 06 — Test Suite.

Verifies:
1. Cross-interval integrity validation engine on canonical datasets (5m <-> 15m, 5m <-> 1h, 1h <-> 4h, 1h <-> 1d)
2. Mathematical aggregation rules (Open == first, High == max, Low == min, Close == last, Volume == sum)
3. Incomplete aggregation window detection and boundary rejection
4. Cross-interval discrepancy detection (fail-closed on corrupted aggregate)
5. Research readiness evaluation on canonical data (prerequisites & score verification)
6. Research readiness lookahead leakage protection and context rules
7. Research readiness on unimported months (fail-closed, missing prerequisites)
8. Offline historical data importer preview mode (--mode preview)
9. Offline historical data importer partition verification (--mode verify)
10. Offline historical data importer receipt tracking and retrieval
11. Dashboard API endpoint: /api/v1/product/interval-integrity
12. Dashboard API endpoint: /api/v1/product/research-readiness
13. Dashboard API endpoint: /api/v1/product/import-history
14. Dataset freshness metrics in /api/v1/product/dataset-catalog
15. Unimported month fail-closed behavior (no synthetic candles generated)
16. Non-negotiable governance invariants
"""

from datetime import datetime, timezone
from http import HTTPStatus
import json
from pathlib import Path
import tempfile
import uuid

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.data_import import HistoricalDataImporter
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.dataset_manager import DatasetManager
from coin_behavior_engine.product.interval_integrity import CrossIntervalIntegrityEngine
from coin_behavior_engine.product.research_readiness import ResearchReadinessEvaluator

REPO_ROOT = Path(__file__).resolve().parents[1]


# -----------------------------------------------------------------------------
# 1. Cross-Interval Integrity Engine — Canonical Partitions
# -----------------------------------------------------------------------------
def test_01_cross_interval_integrity_canonical():
    """Verify cross-interval consistency across canonical September 2026 partitions."""
    engine = CrossIntervalIntegrityEngine()
    result = engine.verify_all(month="2026-09")

    assert result["overall_verdict"] == "PASS"
    assert len(result["checks"]) >= 4
    for check in result["checks"]:
        assert check["verdict"] == "PASS"
        assert check["discrepancies_count"] == 0
        assert check["max_absolute_price_diff"] < 1e-4
        assert check["max_volume_diff"] < 1e-4
        assert check["windows_evaluated"] > 0


# -----------------------------------------------------------------------------
# 2. Cross-Interval Mathematical Aggregation Rules
# -----------------------------------------------------------------------------
def test_02_cross_interval_mathematical_aggregation_rules():
    """Verify exact mathematical aggregation logic (OHLCV) between sub-bars and parent bar."""
    engine = CrossIntervalIntegrityEngine()

    start_ms = 1725148800000  # 2024-09-01 00:00:00 UTC
    sub_df = pd.DataFrame([
        {"open_time": start_ms + 0 * 300000, "open": 60000.0, "high": 60100.0, "low": 59900.0, "close": 60050.0, "volume": 10.0},
        {"open_time": start_ms + 1 * 300000, "open": 60050.0, "high": 60200.0, "low": 60000.0, "close": 60150.0, "volume": 15.0},
        {"open_time": start_ms + 2 * 300000, "open": 60150.0, "high": 60180.0, "low": 59950.0, "close": 60000.0, "volume": 12.0},
    ])
    parent_df = pd.DataFrame([
        {"open_time": start_ms, "open": 60000.0, "high": 60200.0, "low": 59900.0, "close": 60000.0, "volume": 37.0},
    ])

    report = engine.verify_pair(
        df_lower=sub_df,
        df_higher=parent_df,
        interval_lower="5m",
        interval_higher="15m",
        month="2024-09",
    )
    assert report["verdict"] == "PASS"
    assert report["discrepancies_count"] == 0
    assert report["windows_evaluated"] == 1
    assert report["max_absolute_price_diff"] == 0.0
    assert report["max_volume_diff"] == 0.0


# -----------------------------------------------------------------------------
# 3. Incomplete Aggregation Window Detection & Rejection
# -----------------------------------------------------------------------------
def test_03_cross_interval_incomplete_window_rejection():
    """Verify that incomplete windows (e.g. 11/12 bars) are not aggregated or falsely validated."""
    engine = CrossIntervalIntegrityEngine()

    start_ms = 1725148800000  # 1h starts here
    # Provide only 11 5m bars instead of 12 for the hour
    sub_df = pd.DataFrame([
        {"open_time": start_ms + i * 300000, "open": 60000.0 + i, "high": 60010.0 + i, "low": 59990.0 + i, "close": 60005.0 + i, "volume": 1.0}
        for i in range(11)
    ])
    parent_df = pd.DataFrame([
        {"open_time": start_ms, "open": 60000.0, "high": 60020.0, "low": 59990.0, "close": 60015.0, "volume": 11.0},
    ])

    report = engine.verify_pair(
        df_lower=sub_df,
        df_higher=parent_df,
        interval_lower="5m",
        interval_higher="1h",
        month="2024-09",
    )
    # The window has 11 bars != 12 expected bars, so windows_evaluated should be 0 (incomplete windows dropped)
    assert report["windows_evaluated"] == 0
    assert report["discrepancies_count"] == 0


# -----------------------------------------------------------------------------
# 4. Cross-Interval Discrepancy Detection (Fail-Closed)
# -----------------------------------------------------------------------------
def test_04_cross_interval_discrepancy_detection():
    """Verify that corrupt aggregate values trigger explicit FAIL verdict."""
    engine = CrossIntervalIntegrityEngine()

    start_ms = 1725148800000
    sub_df = pd.DataFrame([
        {"open_time": start_ms + 0 * 300000, "open": 60000.0, "high": 60100.0, "low": 59900.0, "close": 60050.0, "volume": 10.0},
        {"open_time": start_ms + 1 * 300000, "open": 60050.0, "high": 60200.0, "low": 60000.0, "close": 60150.0, "volume": 15.0},
        {"open_time": start_ms + 2 * 300000, "open": 60150.0, "high": 60180.0, "low": 59950.0, "close": 60000.0, "volume": 12.0},
    ])
    # Deliberate mismatch: Close is 60500.0 instead of 60000.0
    corrupt_parent_df = pd.DataFrame([
        {"open_time": start_ms, "open": 60000.0, "high": 60200.0, "low": 59900.0, "close": 60500.0, "volume": 37.0},
    ])

    report = engine.verify_pair(
        df_lower=sub_df,
        df_higher=corrupt_parent_df,
        interval_lower="5m",
        interval_higher="15m",
        month="2024-09",
    )
    assert report["verdict"] == "FAIL"
    assert report["discrepancies_count"] >= 1
    assert report["max_absolute_price_diff"] == 500.0


# -----------------------------------------------------------------------------
# 5. Research Readiness Evaluation — Canonical Month
# -----------------------------------------------------------------------------
def test_05_research_readiness_canonical_month():
    """Verify research readiness on September 2026 canonical dataset."""
    evaluator = ResearchReadinessEvaluator()
    res = evaluator.evaluate_readiness("2026-09")

    assert res["target_month"] == "2026-09"
    assert res["overall_verdict"] == "READY"
    assert res["overall_score_pct"] == 100.0
    assert len(res["modules"]) == 5

    module_names = [m["module_id"] for m in res["modules"]]
    assert "historical_charts" in module_names
    assert "regime_intelligence" in module_names
    assert "analog_intelligence" in module_names
    assert ("macro_impact" in module_names or "macro_reactions" in module_names)
    assert "scenario_laboratory" in module_names


# -----------------------------------------------------------------------------
# 6. Research Readiness — Lookahead Leakage Protection & Context Rules
# -----------------------------------------------------------------------------
def test_06_research_readiness_leakage_protection_rules():
    """Verify lookahead leakage safeguards and lookback thresholds in research modules."""
    evaluator = ResearchReadinessEvaluator()
    res = evaluator.evaluate_readiness("2026-09")

    analog_mod = next(m for m in res["modules"] if m["module_id"] == "analog_intelligence")
    assert analog_mod["status"] == "READY"
    assert any("720" in p.lower() for p in analog_mod["prerequisites_met"])
    assert any("lookahead" in r.lower() for r in analog_mod["restrictions"])

    macro_mod = next(m for m in res["modules"] if m["module_id"] in ("macro_impact", "macro_reactions"))
    assert macro_mod["status"] == "READY"
    assert any("macro" in p.lower() for p in macro_mod["prerequisites_met"])


# -----------------------------------------------------------------------------
# 7. Research Readiness — Unimported Month Fail-Closed
# -----------------------------------------------------------------------------
def test_07_research_readiness_unimported_month():
    """Verify unimported October 2026 is properly flagged as PARTIALLY_READY / NOT_READY."""
    evaluator = ResearchReadinessEvaluator()
    res = evaluator.evaluate_readiness("2026-10")

    assert res["target_month"] == "2026-10"
    assert res["overall_verdict"] in ("BLOCKED_NO_DATA", "PARTIALLY_READY", "NOT_READY")
    assert res["overall_score_pct"] < 100.0

    # Modules depending on October partitions should flag missing prerequisites
    chart_mod = next(m for m in res["modules"] if m["module_id"] == "historical_charts")
    assert chart_mod["status"] in ("BLOCKED_NO_DATA", "NOT_READY", "PARTIALLY_READY", "BLOCKED_MISSING_DATA")
    assert len(chart_mod["missing_prerequisites"]) > 0


# -----------------------------------------------------------------------------
# 8. Importer Preview Mode (--mode preview)
# -----------------------------------------------------------------------------
def test_08_importer_preview_mode():
    """Verify importer preview mode audits candidate file without writing partitions."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_base_dir = Path(tmpdir) / "data"
        receipts_dir = Path(tmpdir) / "receipts"
        test_base_dir.mkdir(parents=True, exist_ok=True)

        # Create candidate file
        start_ts = int(datetime(2026, 8, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
        bars_count = 100
        df = pd.DataFrame({
            "open_time": [start_ts + i * 3600000 for i in range(bars_count)],
            "open": [60000.0 + i for i in range(bars_count)],
            "high": [60050.0 + i for i in range(bars_count)],
            "low": [59950.0 + i for i in range(bars_count)],
            "close": [60010.0 + i for i in range(bars_count)],
            "volume": [10.0 for _ in range(bars_count)],
        })
        cand_file = Path(tmpdir) / "BTCUSDT-1h-2026-08-cand.parquet"
        df.to_parquet(cand_file)

        importer = HistoricalDataImporter(base_dir=test_base_dir, receipt_dir=receipts_dir)
        preview = importer.preview_file(cand_file, symbol="BTCUSDT", interval="1h", allow_partial=True)

        assert preview["valid"] is True
        assert preview["target_month"] == "2026-08"
        assert preview["records_count"] == 100
        assert len(preview["preview_candles"]) > 0
        assert preview["is_partial_month"] is True

        # Verify no partition was written
        dest_partition = test_base_dir / "1h" / "BTCUSDT-1h-2026-08.parquet"
        assert not dest_partition.exists()


# -----------------------------------------------------------------------------
# 9. Importer Partition Verification (--mode verify)
# -----------------------------------------------------------------------------
def test_09_importer_partition_verification():
    """Verify that --mode verify audits an existing partition cleanly."""
    importer = HistoricalDataImporter()
    # Verify canonical September 2026 1h partition
    ver = importer.verify_partition(symbol="BTCUSDT", interval="1h", month="2026-09")

    assert ver["valid"] is True
    assert ver["status"] == "VERIFIED"
    assert ver["records_count"] == 720  # 30 days * 24h
    assert ver["missing_candles"] == 0
    assert ver["completeness_pct"] == 100.0


# -----------------------------------------------------------------------------
# 10. Importer Receipts History
# -----------------------------------------------------------------------------
def test_10_importer_receipts_history():
    """Verify listing and retrieval of import receipts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        test_base_dir = Path(tmpdir) / "data"
        receipts_dir = Path(tmpdir) / "receipts"
        (test_base_dir / "1h").mkdir(parents=True, exist_ok=True)

        start_ts = int(datetime(2026, 7, 1, 0, 0, tzinfo=timezone.utc).timestamp() * 1000)
        df = pd.DataFrame({
            "open_time": [start_ts + i * 3600000 for i in range(50)],
            "open": [60000.0 for _ in range(50)],
            "high": [60100.0 for _ in range(50)],
            "low": [59900.0 for _ in range(50)],
            "close": [60050.0 for _ in range(50)],
            "volume": [10.0 for _ in range(50)],
        })
        src_file = Path(tmpdir) / "test.parquet"
        df.to_parquet(src_file)

        importer = HistoricalDataImporter(base_dir=test_base_dir, receipt_dir=receipts_dir)
        rec = importer.import_file(src_file, symbol="BTCUSDT", interval="1h", allow_partial=True)

        # List receipts
        all_recs = importer.list_receipts()
        assert len(all_recs) == 1
        assert all_recs[0]["receipt_id"] == rec["receipt_id"]

        # Get specific receipt
        fetched = importer.get_receipt(rec["receipt_id"])
        assert fetched is not None
        assert fetched["receipt_id"] == rec["receipt_id"]
        assert fetched["records_accepted"] == 50


# -----------------------------------------------------------------------------
# 11. API Endpoint: /api/v1/product/interval-integrity
# -----------------------------------------------------------------------------
def test_11_api_interval_integrity_endpoint():
    """Verify GET /api/v1/product/interval-integrity returns multi-interval cross verification."""
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/interval-integrity?month=2026-09")
    assert status == HTTPStatus.OK
    assert data["status"] == "success"
    assert data["overall_verdict"] == "PASS"
    assert "checks" in data
    assert len(data["checks"]) >= 4

    pairs = [f"{c['interval_from']}->{c['interval_to']}" for c in data["checks"]]
    assert "5m->15m" in pairs
    assert "5m->1h" in pairs


# -----------------------------------------------------------------------------
# 12. API Endpoint: /api/v1/product/research-readiness
# -----------------------------------------------------------------------------
def test_12_api_research_readiness_endpoint():
    """Verify GET /api/v1/product/research-readiness for both canonical and unimported months."""
    # Canonical month
    status_09, data_09 = ProductDashboardApiService.handle_request("/api/v1/product/research-readiness?month=2026-09")
    assert status_09 == HTTPStatus.OK
    assert data_09["overall_verdict"] == "READY"
    assert data_09["overall_score_pct"] == 100.0

    # Unimported month (2026-10)
    status_10, data_10 = ProductDashboardApiService.handle_request("/api/v1/product/research-readiness?month=2026-10")
    assert status_10 == HTTPStatus.OK
    assert data_10["overall_verdict"] in ("BLOCKED_NO_DATA", "PARTIALLY_READY", "NOT_READY")
    assert data_10["overall_score_pct"] < 100.0


# -----------------------------------------------------------------------------
# 13. API Endpoint: /api/v1/product/import-history
# -----------------------------------------------------------------------------
def test_13_api_import_history_endpoint():
    """Verify GET /api/v1/product/import-history returns structured receipt ledger."""
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/import-history")
    assert status == HTTPStatus.OK
    assert data["status"] == "success"
    assert "receipts" in data
    assert "total_receipts" in data


# -----------------------------------------------------------------------------
# 14. API Endpoint: /api/v1/product/dataset-catalog (Freshness Metrics)
# -----------------------------------------------------------------------------
def test_14_api_dataset_catalog_freshness_metrics():
    """Verify GET /api/v1/product/dataset-catalog includes dynamic freshness metrics."""
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/dataset-catalog")
    assert status == HTTPStatus.OK
    assert "freshness_metrics" in data
    fm = data["freshness_metrics"]
    assert "freshness_tier" in fm
    assert fm["freshness_tier"] == "T-1_REFINED_ARCHIVE"
    assert fm["latest_archive_month"] == "2026-09"
    assert fm["current_candidate_month"] == "2026-10"
    assert fm["current_candidate_status"] == "SOURCE_NOT_AVAILABLE"


# -----------------------------------------------------------------------------
# 15. Unimported Month Fail-Closed: Zero Synthetic Price Fabrication
# -----------------------------------------------------------------------------
def test_15_unimported_month_fail_closed_no_synthetic_fabrication():
    """Verify requesting unimported October 2026 returns no_data and zero synthetic candles."""
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/historical-candles?interval=1h&month=2026-10")
    assert status == HTTPStatus.OK
    assert data["status"] == "no_data"
    assert data["available"] is False
    assert len(data.get("candles", [])) == 0
    assert "sahte veya sentetik mum üretmez" in data.get("message", "") or "veri seti henüz aktarılmamıştır" in data.get("message", "")


# -----------------------------------------------------------------------------
# 16. Non-Negotiable Governance Invariants
# -----------------------------------------------------------------------------
def test_16_non_negotiable_governance_invariants():
    """Verify strict fail-closed governance invariants remain intact."""
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/governance")
    assert status == HTTPStatus.OK
    gov = data["governance_contract"]

    assert gov["technical_decision"] == "TECHNICAL_NO_GO"
    assert gov["governance_authorization"] == "NOT_GRANTED"
    assert gov["production_token_issued"] is False

    obs_cap = next(c for c in data["capabilities_matrix"] if c["capability"] == "PROSPECTIVE_LIVE_OBSERVATION")
    assert obs_cap["status"] == "DISABLED"

    exec_cap = next(c for c in data["capabilities_matrix"] if c["capability"] == "ORDER_EXECUTION")
    assert exec_cap["status"] == "PERMANENTLY_PROHIBITED"

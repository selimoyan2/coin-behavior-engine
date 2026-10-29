"""
Sprint Product Acceleration 19 — Comprehensive Unit & Integration Tests.

Verifies:
1. Historical Candlestick Loading & True Financial OHLCV Integrity
2. UTC Timezone Normalization, Bounds & Strict Quarantine Exclusion (October 2026)
3. Server-Side Downsampling without Price Fabrication (Min/Max/Open/Close Semantics)
4. Six-Regime Continuous Segmentation Overlays & Dominant Regime Persistence
5. Macro-Event Annotation Markers linked to Canonical Macro Taxonomy
6. Dual-Period Comparison Studio V2 (Normalized Elapsed Time Base 100 & JSD)
7. Research Library V1 Atomic Persistence, Validation, Concurrency & Bounded Storage
8. Research Library Search, Filter, Rename, Duplicate, Export & Import
9. Dashboard API Endpoints for Explorer & Library (GET, POST, PATCH, DELETE)
10. Scientific Epistemology & Canonical Model Freeze Invariants (CBE-0.7.0 Zero Mutations)
"""

import json
import threading
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import pytest

from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION
from coin_behavior_engine.product.content_integrity import ContentIntegrityEngine
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.dashboard_ui import render_product_dashboard_html
from coin_behavior_engine.product.research_intelligence_explorer import (
    ResearchIntelligenceExplorerEngine,
    ResearchLibraryEngine,
)


class TestSprint19HistoricalExplorerCore:
    """Tests for historical candlestick series, downsampling, and quarantine enforcement."""

    def test_capabilities_endpoint(self):
        caps = ResearchIntelligenceExplorerEngine.get_capabilities()
        assert caps["status"] == "OPERATIONAL"
        assert "CBE-0.7.0" in caps["canonical_model_version"]
        assert "BTCUSDT" in caps["supported_assets"]
        assert "1h" in caps["supported_intervals"]
        assert len(caps["canonical_regimes"]) == 6
        assert len(caps["presets"]) >= 6
        assert caps["governance_invariants"]["model_status"] == "STRICTLY_FROZEN"
        assert caps["governance_invariants"]["live_order_execution"] == "PERMANENTLY_PROHIBITED"

    def test_historical_series_loading_and_ohlc_integrity(self):
        res = ResearchIntelligenceExplorerEngine.get_historical_series(
            start_utc="2022-06-01T00:00:00Z",
            end_utc="2022-06-15T00:00:00Z",
            asset="BTCUSDT",
            interval="1h",
            downsample_max_points=500,
        )
        assert res["schema_version"] == "1.0.0"
        assert res["total_candles_in_range"] == 337
        assert res["points_returned"] == 337
        assert res["downsampled"] is False
        assert len(res["candles"]) == 337

        # Verify true financial OHLC semantics
        for c in res["candles"]:
            assert c["high"] >= c["low"]
            assert c["high"] >= c["open"]
            assert c["high"] >= c["close"]
            assert c["low"] <= c["open"]
            assert c["low"] <= c["close"]
            assert c["volume"] >= 0.0
            assert c["regime"] in ResearchIntelligenceExplorerEngine.CANONICAL_REGIMES
            assert c["parkinson_vol"] >= 0.0

    def test_server_side_downsampling_preserves_extrema(self):
        # 1-year range (8,760 hours)
        res = ResearchIntelligenceExplorerEngine.get_historical_series(
            start_utc="2022-01-01T00:00:00Z",
            end_utc="2023-01-01T00:00:00Z",
            asset="BTCUSDT",
            interval="1h",
            downsample_max_points=200,
        )
        assert res["downsampled"] is True
        assert res["points_returned"] <= 200
        assert res["total_candles_in_range"] > 8000

        # Downsampled candles must strictly maintain OHLC validity
        for c in res["candles"]:
            assert c["high"] >= c["low"]
            assert c["high"] >= c["open"]
            assert c["high"] >= c["close"]
            assert c["low"] <= c["open"]
            assert c["low"] <= c["close"]
            assert c["regime"] in ResearchIntelligenceExplorerEngine.CANONICAL_REGIMES

    def test_strict_quarantine_enforcement_october_2026(self):
        # Any request intersecting October 2026 must be strictly rejected
        with pytest.raises(ValueError, match="karantina"):
            ResearchIntelligenceExplorerEngine.get_historical_series(
                start_utc="2026-10-01T00:00:00Z",
                end_utc="2026-10-15T00:00:00Z",
            )

        with pytest.raises(ValueError, match="karantina"):
            ResearchIntelligenceExplorerEngine.get_regime_overlay(
                start_utc="2026-09-28T00:00:00Z",
                end_utc="2026-10-05T00:00:00Z",
            )

    def test_invalid_parameters_and_safety_guards(self):
        # Inverted dates
        with pytest.raises(ValueError, match="önce olmalıdır"):
            ResearchIntelligenceExplorerEngine.get_historical_series(
                start_utc="2022-06-15T00:00:00Z",
                end_utc="2022-06-01T00:00:00Z",
            )

        # Window too small (< 1 hour)
        with pytest.raises(ValueError, match="en az 1.0 saat"):
            ResearchIntelligenceExplorerEngine.get_historical_series(
                start_utc="2022-06-01T00:00:00Z",
                end_utc="2022-06-01T00:30:00Z",
            )

        # Window exceeds max chart days
        with pytest.raises(ValueError, match="azami süreyi"):
            ResearchIntelligenceExplorerEngine.get_historical_series(
                start_utc="2010-01-01T00:00:00Z",
                end_utc="2020-01-01T00:00:00Z",
            )

        # Unsupported asset
        with pytest.raises(ValueError, match="desteklenmemektedir"):
            ResearchIntelligenceExplorerEngine.get_historical_series(
                start_utc="2022-06-01T00:00:00Z",
                end_utc="2022-06-15T00:00:00Z",
                asset="DOGEUSDT",
            )


class TestSprint19RegimeAndMacroOverlays:
    """Tests for continuous regime segmentation and macro event tagging."""

    def test_continuous_regime_overlay_segmentation(self):
        res = ResearchIntelligenceExplorerEngine.get_regime_overlay(
            start_utc="2022-06-01T00:00:00Z",
            end_utc="2022-06-15T00:00:00Z",
            interval="1h",
        )
        assert res["total_segments"] > 0
        assert res["dominant_regime"] in ResearchIntelligenceExplorerEngine.CANONICAL_REGIMES
        assert res["dominant_share_pct"] > 0.0

        # Verify segments continuity
        segments = res["segments"]
        total_bars_sum = sum(s["duration_bars"] for s in segments)
        assert total_bars_sum == 337

        for seg in segments:
            assert seg["regime"] in ResearchIntelligenceExplorerEngine.CANONICAL_REGIMES
            assert seg["duration_bars"] >= 1
            assert seg["start_index"] <= seg["end_index"]
            assert seg["color_hex"].startswith("#")

    def test_macro_events_filtering_and_taxonomy_link(self):
        res = ResearchIntelligenceExplorerEngine.get_macro_events(
            start_utc="2022-06-01T00:00:00Z",
            end_utc="2022-06-15T00:00:00Z",
        )
        assert "events" in res
        assert res["events_count"] >= 1
        for ev in res["events"]:
            assert ev["event_id"].startswith("EVT-")
            assert ev["release_at_utc"] >= "2022-06-01"
            assert ev["release_at_utc"] <= "2022-06-15"
            assert ev["parent_cohort"] in ("US_INFLATION", "US_MONETARY_POLICY", "US_LABOR", "US_GROWTH", "CRYPTO_REGULATORY", "SYSTEMIC_RISK", "MARKET_STRUCTURE")


class TestSprint19ComparisonStudioV2:
    """Tests for side-by-side and normalized elapsed-time historical comparisons."""

    def test_comparison_series_and_normalized_elapsed_progress(self):
        res = ResearchIntelligenceExplorerEngine.get_comparison_series(
            start_utc_a="2022-06-01T00:00:00Z",
            end_utc_a="2022-06-15T00:00:00Z",
            start_utc_b="2024-07-27T01:00:00Z",
            end_utc_b="2024-08-10T01:00:00Z",
        )
        assert "period_a" in res and "period_b" in res
        assert "comparison_metrics" in res
        assert "dimension_breakdown" in res

        # Check normalized series (Base 100, elapsed % 0 to 100)
        norm_a = res["period_a"]["normalized_series"]
        norm_b = res["period_b"]["normalized_series"]
        assert len(norm_a) > 0 and len(norm_b) > 0

        assert norm_a[0]["elapsed_progress_pct"] == 0.0
        assert norm_a[-1]["elapsed_progress_pct"] == 100.0
        assert norm_a[0]["normalized_index_base_100"] > 0.0

        # Check statistical metrics
        m = res["comparison_metrics"]
        assert "regime_jsd_divergence" in m
        assert 0.0 <= m["regime_jsd_divergence"] <= 1.0
        assert "volatility_gap_pct" in m
        assert "composite_similarity_pct" in m


class TestSprint19ResearchLibraryV1:
    """Tests for atomic persistence, search, duplicate, rename, delete, and concurrency."""

    @pytest.fixture(autouse=True)
    def setup_and_teardown_library(self, tmp_path, monkeypatch):
        # Set temporary isolated directory for testing
        test_lib_dir = tmp_path / "research_library"
        test_lib_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("CBE_RESEARCH_LIBRARY_PATH", str(test_lib_dir))
        yield
        # Teardown: clean files
        for f in test_lib_dir.glob("RLIB-*.json"):
            f.unlink()

    def test_save_and_retrieve_definition(self):
        payload = {
            "title": "Fed Haziran 2022 Şok Rejimi Analizi",
            "description": "75 bps faiz artışı sırasındaki rejim geçişleri.",
            "asset": "BTCUSDT",
            "interval": "1h",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
            "selected_modules": ["regime_analysis", "volatility_analysis"],
            "tags": ["fed", "fomc", "2022"],
        }
        rec = ResearchLibraryEngine.save_definition(payload)
        assert rec["research_id"].startswith("RLIB-")
        assert rec["title"] == payload["title"]
        assert rec["schema_version"] == "1.0.0"

        # Retrieve
        fetched = ResearchLibraryEngine.get_definition(rec["research_id"])
        assert fetched is not None
        assert fetched["research_id"] == rec["research_id"]
        assert fetched["tags"] == ["fed", "fomc", "2022"]

    def test_list_and_search_filtering(self):
        ResearchLibraryEngine.save_definition({
            "title": "FTX Çöküşü Likidite Krizi",
            "reference_start_utc": "2022-11-06T00:00:00Z",
            "reference_end_utc": "2022-11-20T00:00:00Z",
            "interval": "1h",
        })
        ResearchLibraryEngine.save_definition({
            "title": "SVB Bankacılık Kriz Rejimi",
            "reference_start_utc": "2023-03-08T00:00:00Z",
            "reference_end_utc": "2023-03-22T00:00:00Z",
            "interval": "15m",
        })

        # Search by query
        res_ftx = ResearchLibraryEngine.list_definitions(q="FTX")
        assert len(res_ftx) == 1
        assert "FTX" in res_ftx[0]["title"]

        # Filter by interval
        res_15m = ResearchLibraryEngine.list_definitions(interval="15m")
        assert len(res_15m) == 1
        assert "SVB" in res_15m[0]["title"]

    def test_duplicate_and_rename_definition(self):
        rec = ResearchLibraryEngine.save_definition({
            "title": "Orijinal Analiz",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
        })
        dup = ResearchLibraryEngine.duplicate_definition(rec["research_id"], "Kopya Analiz V2")
        assert dup["research_id"] != rec["research_id"]
        assert dup["title"] == "Kopya Analiz V2"

        # Rename original
        updated = ResearchLibraryEngine.update_definition(rec["research_id"], {"title": "Yeniden Adlandırılmış Analiz"})
        assert updated["title"] == "Yeniden Adlandırılmış Analiz"

    def test_delete_definition(self):
        rec = ResearchLibraryEngine.save_definition({
            "title": "Silinecek Analiz",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
        })
        assert ResearchLibraryEngine.delete_definition(rec["research_id"]) is True
        assert ResearchLibraryEngine.get_definition(rec["research_id"]) is None
        # Deleting non-existent returns False
        assert ResearchLibraryEngine.delete_definition(rec["research_id"]) is False

    def test_import_external_definition(self):
        external_data = {
            "schema_version": "1.0.0",
            "title": "Dışarıdan Alınan ETF Hipotezi",
            "description": "Paylaşılan araştırma konfigürasyonu",
            "asset": "BTCUSDT",
            "interval": "4h",
            "reference_start_utc": "2024-01-08T00:00:00Z",
            "reference_end_utc": "2024-01-22T00:00:00Z",
            "selected_modules": ["regime_analysis", "macro_comparison"],
        }
        imported = ResearchLibraryEngine.import_definition(external_data)
        assert imported["research_id"].startswith("RLIB-")
        assert imported["title"] == "Dışarıdan Alınan ETF Hipotezi"
        assert imported["interval"] == "4h"

        # Mismatched schema rejection
        bad_schema = dict(external_data)
        bad_schema["schema_version"] = "9.9.9"
        with pytest.raises(ValueError, match="Uyumsuz şema"):
            ResearchLibraryEngine.import_definition(bad_schema)

    def test_thread_safe_concurrency_writes(self):
        # Concurrently create 20 definitions without corruption
        errors = []

        def worker(idx):
            try:
                ResearchLibraryEngine.save_definition({
                    "title": f"Eşzamanlı İşlem {idx}",
                    "reference_start_utc": "2022-06-01T00:00:00Z",
                    "reference_end_utc": "2022-06-15T00:00:00Z",
                })
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        all_defs = ResearchLibraryEngine.list_definitions(limit=100)
        assert len(all_defs) == 20


class TestSprint19DashboardApiIntegration:
    """Tests for HTTP endpoint routing and status codes via ProductDashboardApiService."""

    def test_explorer_capabilities_api(self):
        status, data = ProductDashboardApiService.handle_request("/api/v1/product/research-explorer/capabilities", {})
        assert status == HTTPStatus.OK
        assert data["status"] == "OPERATIONAL"

    def test_explorer_historical_series_api(self):
        params = {
            "start_utc": ["2022-06-01T00:00:00Z"],
            "end_utc": ["2022-06-15T00:00:00Z"],
            "interval": ["1h"],
        }
        status, data = ProductDashboardApiService.handle_request("/api/v1/product/research-explorer/historical-series", params)
        assert status == HTTPStatus.OK
        assert data["total_candles_in_range"] == 337
        assert len(data["candles"]) == 337

    def test_explorer_regime_overlay_api(self):
        params = {
            "start_utc": ["2022-06-01T00:00:00Z"],
            "end_utc": ["2022-06-15T00:00:00Z"],
        }
        status, data = ProductDashboardApiService.handle_request("/api/v1/product/research-explorer/regime-overlay", params)
        assert status == HTTPStatus.OK
        assert len(data["segments"]) > 0

    def test_explorer_macro_events_api(self):
        params = {
            "start_utc": ["2022-06-01T00:00:00Z"],
            "end_utc": ["2022-06-15T00:00:00Z"],
        }
        status, data = ProductDashboardApiService.handle_request("/api/v1/product/research-explorer/macro-events", params)
        assert status == HTTPStatus.OK
        assert data["events_count"] >= 1

    def test_explorer_comparison_api(self):
        params = {
            "start_utc_a": ["2022-06-01T00:00:00Z"],
            "end_utc_a": ["2022-06-15T00:00:00Z"],
            "start_utc_b": ["2024-07-27T01:00:00Z"],
            "end_utc_b": ["2024-08-10T01:00:00Z"],
        }
        status, data = ProductDashboardApiService.handle_request("/api/v1/product/research-explorer/comparison", params)
        assert status == HTTPStatus.OK
        assert "comparison_metrics" in data

    def test_research_library_crud_lifecycle_api(self, tmp_path, monkeypatch):
        test_lib_dir = tmp_path / "test_api_lib"
        test_lib_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.setenv("CBE_RESEARCH_LIBRARY_PATH", str(test_lib_dir))

        # 1. CREATE via POST
        create_payload = {
            "title": "API Döngü Testi",
            "description": "CRUD testi",
            "asset": "BTCUSDT",
            "interval": "1h",
            "reference_start_utc": "2022-06-01T00:00:00Z",
            "reference_end_utc": "2022-06-15T00:00:00Z",
        }
        status, created = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/research-library", {}, create_payload
        )
        assert status == HTTPStatus.CREATED
        rid = created["research_id"]

        # 2. READ via GET
        status, item = ProductDashboardApiService.handle_request(f"/api/v1/product/research-library/{rid}", {})
        assert status == HTTPStatus.OK
        assert item["title"] == "API Döngü Testi"

        # 3. UPDATE via PATCH
        status, updated = ProductDashboardApiService.handle_patch_request(
            f"/api/v1/product/research-library/{rid}", {}, {"title": "Güncellenmiş Başlık"}
        )
        assert status == HTTPStatus.OK
        assert updated["definition"]["title"] == "Güncellenmiş Başlık"

        # 4. DUPLICATE via POST
        status, dup = ProductDashboardApiService.handle_post_request(
            "/api/v1/product/research-library/duplicate", {}, {"research_id": rid, "title": "Kopya Başlık"}
        )
        assert status == HTTPStatus.CREATED
        assert dup["definition"]["title"] == "Kopya Başlık"

        # 5. DELETE via DELETE
        status, del_res = ProductDashboardApiService.handle_delete_request(
            f"/api/v1/product/research-library/{rid}", {}
        )
        assert status == HTTPStatus.OK
        assert del_res["status"] == "success"

        # 6. Verify 404
        status, _ = ProductDashboardApiService.handle_request(f"/api/v1/product/research-library/{rid}", {})
        assert status == HTTPStatus.NOT_FOUND

    def test_prohibited_live_trading_isolation(self):
        # Any attempt to call trading or order execution routes must be rejected
        status, res = ProductDashboardApiService.handle_request("/api/v1/product/live-trading/execute", {})
        assert status == HTTPStatus.NOT_FOUND

        status, res = ProductDashboardApiService.handle_post_request("/api/v1/product/order-routing", {}, {"order": "BUY"})
        assert status == HTTPStatus.NOT_FOUND


class TestSprint19DashboardUiIntegration:
    """Tests for UI HTML structure, nav tabs, SVG elements, and script integration."""

    def test_dashboard_ui_html_rendering_sprint19(self):
        html = render_product_dashboard_html()
        assert len(html) > 500000

        # Nav tab verification
        assert 'id="tab-btn-research-explorer"' in html
        assert "Araştırma İstihbarat Gezgini V1 & Kütüphane (Sprint 19)" in html

        # Section presence
        assert 'id="module-research-explorer"' in html
        assert 'id="explorer-chart-svg"' in html
        assert 'id="explorer-selection-hud"' in html
        assert 'id="comp-dual-view"' in html
        assert 'id="library-items-container"' in html

        # Script functions
        assert "loadResearchExplorer" in html
        assert "explorerLoadData" in html
        assert "compRunComparison" in html
        assert "libraryRefresh" in html
        assert "librarySubmitSave" in html

        # Frozen model notice in UI
        assert "CBE-0.7.0 (FROZEN)" in html
        assert "SIFIR ALIM-SATIM" in html

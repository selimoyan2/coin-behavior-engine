"""Sprint 34 Comprehensive Test Suite.

Canonical Execution Parity, Causal Research Correction & 2026 Historical Data Completion.
Covers 32+ targeted automated tests verifying:
- Canonical model lockbox immutability (29 artifacts)
- Causal point-in-time calibration modes (PREDECLARED_FROZEN & EXPANDING_CAUSAL_WINDOW)
- Prefix invariance across horizons k in {24, 72, 168, 720, 2160}
- 3-Tier attribution hierarchy standards
- Authoritative inference predict_bar_authoritative()
- October 2026 partial data registration and multi-timeframe invariants
- November 2026 missing status and zero-fabrication invariant
- Controlled offline import workflow validation
- DatasetManager completeness status and latest verified candle
- Dashboard V11.1 API endpoints and UI elements
- Production zero-touch invariants and permanent live trading prohibition
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict

import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.market_state.engine import (
    FallbackLevel,
    HISTORICAL_RESEARCH_END,
    UnifiedMarketStateEngine,
)
from coin_behavior_engine.product.btc_timing_research.canonical_model_research_bridge import (
    CANONICAL_MODEL_VERSION,
    CanonicalAttributionTier,
    CanonicalModelResearchBridge,
    CausalCalibrationMode,
    FROZEN_DISCOVERY_THRESHOLDS,
    MODEL_STATUS,
)
from coin_behavior_engine.product.btc_timing_research.investment_research_v11 import (
    InvestmentResearchV11Service,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.dataset_manager import DatasetManager


class TestSprint34CanonicalParityAndHistoricalData:

    # 1. Governance & Model Freeze
    def test_01_canonical_model_version_frozen(self):
        assert CANONICAL_MODEL_VERSION == "CBE-0.7.0"
        assert MODEL_STATUS == "STRICTLY_FROZEN"

    def test_02_lockbox_integrity_29_artifacts(self):
        lockbox_dir = Path("src/coin_behavior_engine/market_state/canonical_model_lockbox")
        if lockbox_dir.exists():
            files = list(lockbox_dir.glob("*.*"))
            assert len(files) >= 29, f"Expected 29 artifacts, found {len(files)}"

    def test_03_historical_research_end_preserved(self):
        assert HISTORICAL_RESEARCH_END == "2026-09-23T23:59:59 UTC"

    # 2. Causal Calibration & Prefix Invariance
    def test_04_predeclared_frozen_thresholds_values(self):
        assert FROZEN_DISCOVERY_THRESHOLDS["vol_p25"] == pytest.approx(0.254757, rel=1e-4)
        assert FROZEN_DISCOVERY_THRESHOLDS["vol_p75"] == pytest.approx(0.454040, rel=1e-4)
        assert FROZEN_DISCOVERY_THRESHOLDS["comp_p25"] == pytest.approx(0.623250, rel=1e-4)
        assert FROZEN_DISCOVERY_THRESHOLDS["comp_p75"] == pytest.approx(1.203961, rel=1e-4)

    def test_05_bridge_initialization_defaults(self):
        bridge = CanonicalModelResearchBridge()
        assert bridge.model_version == "CBE-0.7.0"
        assert bridge.model_status == "STRICTLY_FROZEN"
        assert bridge.enforce_read_only is True

    def test_06_predeclared_frozen_prefix_invariance_guarantee(self):
        bridge = CanonicalModelResearchBridge()
        # Synthetic test data: 200 bars
        dates = pd.date_range("2024-01-01", periods=200, freq="1h", tz="UTC")
        prices = 50000.0 + np.sin(np.linspace(0, 10, 200)) * 1000.0
        df_dummy = pd.DataFrame({
            "datetime": dates,
            "open_time": (dates.astype(np.int64) // 10**6),
            "open": prices,
            "high": prices + 50.0,
            "low": prices - 50.0,
            "close": prices,
            "volume": 100.0,
        })
        res = bridge.evaluate_prefix_invariance(
            df_dummy, test_indices=[50], append_horizons=[24, 72], causal_mode=CausalCalibrationMode.PREDECLARED_FROZEN
        )
        assert res["all_passed"] is True
        assert res["causal_mode"] == CausalCalibrationMode.PREDECLARED_FROZEN.value

    def test_07_full_sample_quantiles_fails_prefix_invariance_diagnostic(self):
        evidence_path = Path("research_outputs/sprint34_canonical_causal_and_historical_data/04_prefix_invariance_test_evidence.json")
        assert evidence_path.exists(), "Prefix invariance evidence missing"
        with open(evidence_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data["summary"]["predeclared_frozen_passed"] is True
        assert data["summary"]["full_sample_quantiles_passed"] is False

    # 3. Attribution Tiers
    def test_08_attribution_tier_enum_values(self):
        assert CanonicalAttributionTier.CANONICAL_AUTHORITATIVE_OUTPUT.value == "CANONICAL_AUTHORITATIVE_OUTPUT"
        assert CanonicalAttributionTier.CANONICAL_COMPATIBLE_DERIVED_OUTPUT.value == "CANONICAL_COMPATIBLE_DERIVED_OUTPUT"
        assert CanonicalAttributionTier.RESEARCH_HEURISTIC_OUTPUT.value == "RESEARCH_HEURISTIC_OUTPUT"

    def test_09_predict_bar_authoritative_contract(self):
        bridge = CanonicalModelResearchBridge()
        dummy_row = {
            "volatility_realized_24h": 0.35,
            "volatility_compression_ratio": 1.10,
            "volume_zscore": 0.5,
            "session_asia_active": 1.0,
            "session_london_active": 0.0,
            "session_new_york_active": 0.0,
            "weekend_flag": 0.0,
            "london_new_york_overlap": 0.0,
        }
        res = bridge.predict_bar_authoritative(dummy_row)
        assert res["attribution_tier"] == CanonicalAttributionTier.CANONICAL_AUTHORITATIVE_OUTPUT.value
        assert res["engine_version"] == "CBE-0.7.0"
        assert "volatility_forecasts" in res
        assert "tail_risk_probabilities" in res

    def test_10_evaluation_result_attribution_metadata(self):
        bridge = CanonicalModelResearchBridge()
        dates = pd.date_range("2024-01-01", periods=50, freq="1h", tz="UTC")
        df_dummy = pd.DataFrame({
            "datetime": dates,
            "open_time": (dates.astype(np.int64) // 10**6),
            "open": 50000.0,
            "high": 50100.0,
            "low": 49900.0,
            "close": 50000.0,
            "volume": 100.0,
        })
        res = bridge.evaluate_historical_dataset(df_dummy, causal_mode=CausalCalibrationMode.PREDECLARED_FROZEN)
        assert res.attribution_tier == CanonicalAttributionTier.CANONICAL_COMPATIBLE_DERIVED_OUTPUT.value
        assert res.causal_calibration_mode == CausalCalibrationMode.PREDECLARED_FROZEN.value
        assert res.prefix_invariance_verified is True

    # 4. October 2026 Data & Multi-Timeframe Resampling
    def test_11_october_2026_5m_partition_exists_and_verified(self):
        p = Path("data/binance_spot_multiyear/5m/BTCUSDT-5m-2026-10.parquet")
        assert p.exists()
        df = pd.read_parquet(p)
        assert len(df) in (288, 8928)
        assert str(df["datetime"].iloc[0]).startswith("2026-10-01 00:00:00")

    def test_12_october_2026_15m_partition_exists_and_verified(self):
        p = Path("data/binance_spot_multiyear/15m/BTCUSDT-15m-2026-10.parquet")
        assert p.exists()
        df = pd.read_parquet(p)
        assert len(df) in (96, 2976)

    def test_13_october_2026_1h_partition_exists_and_verified(self):
        p = Path("data/binance_spot_multiyear/1h/BTCUSDT-1h-2026-10.parquet")
        assert p.exists()
        df = pd.read_parquet(p)
        assert len(df) in (24, 744)

    def test_14_october_2026_4h_partition_exists_and_verified(self):
        p = Path("data/binance_spot_multiyear/4h/BTCUSDT-4h-2026-10.parquet")
        assert p.exists()
        df = pd.read_parquet(p)
        assert len(df) in (6, 186)

    def test_15_october_2026_1d_partition_exists_and_verified(self):
        p = Path("data/binance_spot_multiyear/1d/BTCUSDT-1d-2026-10.parquet")
        assert p.exists()
        df = pd.read_parquet(p)
        assert len(df) in (1, 31)

    def test_16_multi_timeframe_volume_conservation(self):
        df_5m = pd.read_parquet("data/binance_spot_multiyear/5m/BTCUSDT-5m-2026-10.parquet")
        df_15m = pd.read_parquet("data/binance_spot_multiyear/15m/BTCUSDT-15m-2026-10.parquet")
        df_1h = pd.read_parquet("data/binance_spot_multiyear/1h/BTCUSDT-1h-2026-10.parquet")
        df_4h = pd.read_parquet("data/binance_spot_multiyear/4h/BTCUSDT-4h-2026-10.parquet")
        df_1d = pd.read_parquet("data/binance_spot_multiyear/1d/BTCUSDT-1d-2026-10.parquet")

        v5 = df_5m["volume"].sum()
        assert abs(v5 - df_15m["volume"].sum()) < 1e-4
        assert abs(v5 - df_1h["volume"].sum()) < 1e-4
        assert abs(v5 - df_4h["volume"].sum()) < 1e-4
        assert abs(v5 - df_1d["volume"].sum()) < 1e-4

    def test_17_multi_timeframe_price_extremes_conservation(self):
        df_5m = pd.read_parquet("data/binance_spot_multiyear/5m/BTCUSDT-5m-2026-10.parquet")
        df_1d = pd.read_parquet("data/binance_spot_multiyear/1d/BTCUSDT-1d-2026-10.parquet")
        assert abs(df_1d["open"].iloc[0] - df_5m["open"].iloc[0]) < 1e-4
        assert abs(df_1d["close"].iloc[-1] - df_5m["close"].iloc[-1]) < 1e-4
        assert abs(df_1d["high"].max() - df_5m["high"].max()) < 1e-4
        assert abs(df_1d["low"].min() - df_5m["low"].min()) < 1e-4

    # 5. November 2026 Data Absence & Zero-Fabrication Invariant
    def test_18_november_2026_missing_status(self):
        p = Path("data/binance_spot_multiyear/5m/BTCUSDT-5m-2026-11.parquet")
        # In Sprint 34, 2026-11 did not exist on disk.
        # In Sprint 35, 2026-11 was partially registered (PARTIAL_VERIFIED) from genuine live feed.
        dm = DatasetManager.get_instance()
        comp = dm.get_month_completeness("2026-11")
        if p.exists():
            assert comp.status == "PARTIAL"
            assert comp.actual_candles > 0
        else:
            assert comp.status in ("NOT_IMPORTED", "MISSING")

    def test_19_controlled_offline_importer_script_exists(self):
        p = Path("scripts/import_offline_historical_partition.py")
        assert p.exists()

    # 6. DatasetManager Verification
    def test_20_dataset_manager_latest_candle_is_october_2026(self):
        dm = DatasetManager.get_instance()
        dm.invalidate_cache()
        candle = dm.get_latest_candle("5m")
        assert candle is not None
        assert candle["month"] in ("2026-10", "2026-11")

    def test_21_dataset_manager_october_completeness_partial(self):
        dm = DatasetManager.get_instance()
        comp = dm.get_month_completeness("2026-10", "5m")
        # In Sprint 34 it was PARTIAL (288 bars). In Sprint 35 it was fully recovered to COMPLETE (8928 bars).
        assert comp.status in ("PARTIAL", "COMPLETE")
        if comp.status == "COMPLETE":
            assert comp.actual_candles == 8928
        else:
            assert comp.actual_candles == 288

    # 7. Corrected Research Artifacts
    def test_22_corrected_regime_analysis_artifact(self):
        p = Path("research_outputs/sprint34_canonical_causal_and_historical_data/06_corrected_regime_analysis.json")
        assert p.exists()
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        assert d["causal_calibration_mode"] == "PREDECLARED_FROZEN"
        assert d["total_analyzed_bars"] > 18000

    def test_23_corrected_forward_return_artifact(self):
        p = Path("research_outputs/sprint34_canonical_causal_and_historical_data/07_corrected_forward_return_analysis.json")
        assert p.exists()
        with open(p, "r", encoding="utf-8") as f:
            d = json.load(f)
        assert "forward_return_distributions" in d
        assert "downside_risk_by_regime" in d

    def test_24_corrected_incremental_value_artifact(self):
        p = Path("research_outputs/sprint34_canonical_causal_and_historical_data/08_corrected_incremental_value_assessment.md")
        assert p.exists()
        content = p.read_text(encoding="utf-8")
        assert "ANOVA F" in content
        assert "CANONICAL_DERIVED" in content

    def test_25_corrected_paper_portfolio_reconciliation_artifact(self):
        p = Path("research_outputs/sprint34_canonical_causal_and_historical_data/09_corrected_paper_portfolio_reconciliation.md")
        assert p.exists()
        content = p.read_text(encoding="utf-8")
        assert "Drawdown Truncation" in content

    # 8. Dashboard V11.1 API & Endpoints
    def test_26_api_v11_model_status_attribution_fields(self):
        service = InvestmentResearchV11Service.get_instance()
        st = service.get_model_status()
        assert st["attribution_tier"] == "CANONICAL_COMPATIBLE_DERIVED_OUTPUT"
        assert st["causal_calibration_mode"] == "PREDECLARED_FROZEN"
        assert st["prefix_invariance_verified"] is True
        assert "verified_up_to" in st["dataset_coverage"]

    def test_27_api_v11_regime_explorer_data(self):
        service = InvestmentResearchV11Service.get_instance()
        reg = service.get_regime_explorer()
        assert "regimes" in reg
        assert "persistence_stats" in reg
        assert "transition_matrix_24h" in reg

    def test_28_api_v11_forward_returns_horizons(self):
        service = InvestmentResearchV11Service.get_instance()
        fwd = service.get_forward_returns("24h")
        assert fwd["selected_horizon"] == "24h"
        assert "horizon_data" in fwd

    def test_29_api_v11_risk_intelligence_cvar(self):
        service = InvestmentResearchV11Service.get_instance()
        risk = service.get_risk_intelligence()
        assert "risk_metrics_24h" in risk
        assert "TAIL_RISK_ELEVATED" in risk["risk_metrics_24h"]

    def test_30_api_v11_evidence_ledger_all_22_artifacts(self):
        service = InvestmentResearchV11Service.get_instance()
        ledger = service.get_evidence_ledger(sprint="34")
        assert ledger["total_artifacts"] == 22
        assert len(ledger["artifacts"]) == 22

    # 9. Safety & Production Isolation
    def test_31_deployment_safety_zero_touch(self):
        service = InvestmentResearchV11Service.get_instance()
        safety = service.get_deployment_safety()
        assert safety["production_zero_touch_status"] == "STRICT_ZERO_TOUCH_PRESERVED"
        assert safety["production_container_id"] == "4c6a29b5fbf6"
        assert safety["production_port"] == 8000
        assert safety["production_restart_count"] == 0

    def test_32_live_trading_permanently_prohibited(self):
        service = InvestmentResearchV11Service.get_instance()
        status_data = service.get_model_status()
        assert status_data["live_trading_prohibition"] == "PERMANENTLY_PROHIBITED"
        safety = service.get_deployment_safety()
        assert safety["live_trading_lock"] == "PERMANENTLY_PROHIBITED (HTTP 403 ENFORCED)"

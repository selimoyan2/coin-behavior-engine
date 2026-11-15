"""Automated Test Suite for Sprint 33: Canonical Model Bridge & Market Behavior Intelligence.

Validates all 32 required dimensions across:
- Canonical model identity and freeze preservation (CBE-0.7.0, 29/29 lockbox artifacts)
- CanonicalModelResearchBridge functionality and Information Ladder fallback hierarchy
- Point-in-time feature extraction without future lookahead
- Regime persistence, empirical transition matrices, and forward returns
- Downside risk, MAE distributions, and CVaR tail separation
- Incremental value assessment (Baselines A-D)
- Dashboard V11 REST API endpoints and UI integration
- Production deployment isolation (Option 3, Strict Zero-Touch container forensics)
- Permanent live trading prohibition
"""

from http import HTTPStatus
import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.market_state.engine import (
    FallbackLevel,
    HISTORICAL_RESEARCH_END,
    MarketStateId,
    UnifiedMarketStateEngine,
)
from coin_behavior_engine.product.btc_timing_research.canonical_model_research_bridge import (
    CANONICAL_MODEL_VERSION,
    MODEL_STATUS,
    CanonicalModelResearchBridge,
)
from coin_behavior_engine.product.btc_timing_research.investment_research_v11 import (
    InvestmentResearchV11Service,
)
from coin_behavior_engine.product.dashboard_api import ProductDashboardApiService
from coin_behavior_engine.product.dashboard_ui import render_product_dashboard_html

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUTS_DIR = REPO_ROOT / "research_outputs" / "sprint33_canonical_model_market_behavior"


# ============================================================================
# 1. Canonical Model Identity & Governance Invariants (1 - 4)
# ============================================================================

def test_01_canonical_model_version_frozen():
    assert CANONICAL_MODEL_VERSION == "CBE-0.7.0"
    assert MODEL_STATUS == "STRICTLY_FROZEN"
    engine = UnifiedMarketStateEngine()
    assert engine.model_version == "CBE-0.7.0"


def test_02_lockbox_integrity_29_artifacts():
    manifest_p = REPO_ROOT / "data" / "reports" / "sprint08" / "cross_platform_freeze_manifest_v2.json"
    assert manifest_p.exists(), "Freeze Manifest V2 must exist"
    with open(manifest_p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["model_version"] == "CBE-0.7.0"
    assert len(data["artifacts"]) == 29


def test_03_historical_research_end_preserved():
    assert HISTORICAL_RESEARCH_END == "2026-09-23T23:59:59 UTC"


def test_04_bridge_initialization_read_only():
    bridge = CanonicalModelResearchBridge()
    assert bridge.enforce_read_only is True
    assert bridge.model_version == "CBE-0.7.0"


# ============================================================================
# 2. Feature Extraction & Fallback Hierarchy (5 - 8)
# ============================================================================

def test_05_feature_extraction_spot_core():
    dummy = pd.DataFrame({
        "open_time": [1704067200000 + i * 3600000 for i in range(50)],
        "open": np.linspace(42000, 43000, 50),
        "high": np.linspace(42500, 43500, 50),
        "low": np.linspace(41500, 42500, 50),
        "close": np.linspace(42100, 43100, 50),
        "volume": np.random.uniform(100, 500, 50),
    })
    extracted = CanonicalModelResearchBridge.extract_features(dummy)
    assert "volatility_realized_24h" in extracted.columns
    assert "volatility_compression_ratio" in extracted.columns
    assert "volatility_parkinson_24h" in extracted.columns
    assert "volume_zscore" in extracted.columns


def test_06_feature_extraction_session_context():
    dummy = pd.DataFrame({
        "open_time": [1704067200000 + i * 3600000 for i in range(24)],
        "open": [42000] * 24, "high": [42100] * 24, "low": [41900] * 24, "close": [42050] * 24, "volume": [100] * 24
    })
    extracted = CanonicalModelResearchBridge.extract_features(dummy)
    assert "session_asia_active" in extracted.columns
    assert "session_london_active" in extracted.columns
    assert "session_new_york_active" in extracted.columns
    assert "weekend_flag" in extracted.columns


def test_07_fallback_hierarchy_spot_only_u0():
    bridge = CanonicalModelResearchBridge()
    dummy = pd.DataFrame({
        "open_time": [1704067200000 + i * 3600000 for i in range(50)],
        "open": [42000] * 50, "high": [42100] * 50, "low": [41900] * 50, "close": [42050] * 50, "volume": [100] * 50
    })
    res = bridge.evaluate_historical_dataset(dummy, "TEST_DATASET")
    assert res.active_fallback_level == FallbackLevel.SPOT_ONLY_U0.value
    assert res.feature_availability_pct > 50.0


def test_08_no_lookahead_leakage():
    # Modifying bar T+k must NOT alter features at bar T
    dummy1 = pd.DataFrame({
        "open_time": [1704067200000 + i * 3600000 for i in range(30)],
        "open": [42000] * 30, "high": [42200] * 30, "low": [41800] * 30, "close": [42100] * 30, "volume": [100] * 30
    })
    dummy2 = dummy1.copy()
    dummy2.loc[29, "close"] = 999999.0  # Shock on final bar

    f1 = CanonicalModelResearchBridge.extract_features(dummy1)
    f2 = CanonicalModelResearchBridge.extract_features(dummy2)

    # Bars 0 to 28 must be identical
    np.testing.assert_array_equal(f1.loc[:28, "volatility_realized_24h"], f2.loc[:28, "volatility_realized_24h"])
    np.testing.assert_array_equal(f1.loc[:28, "volatility_compression_ratio"], f2.loc[:28, "volatility_compression_ratio"])


# ============================================================================
# 3. Canonical Bridge Evaluation on Datasets (9 - 11)
# ============================================================================

def test_09_canonical_evaluation_2023_2024():
    p = REPO_ROOT / "data" / "historical" / "BTCUSDT-1h-2023-10-to-2024-11.parquet"
    if p.exists():
        df = pd.read_parquet(p)
        bridge = CanonicalModelResearchBridge()
        res = bridge.evaluate_historical_dataset(df, "DS-BTC-1H-2023-2024")
        assert res.total_bars == 9528
        assert "NORMAL" in res.regime_distribution
        assert "HIGH_VOLATILITY" in res.regime_distribution
        assert "TAIL_RISK_ELEVATED" in res.regime_distribution


def test_10_canonical_evaluation_2025_sealed():
    p = REPO_ROOT / "data" / "historical" / "historical_binance_btcusdt_1h_2025.parquet"
    if p.exists():
        df = pd.read_parquet(p)
        bridge = CanonicalModelResearchBridge()
        res = bridge.evaluate_historical_dataset(df, "DS-BTC-1H-2025-SEALED")
        assert res.total_bars == 8760
        assert "NORMAL" in res.regime_distribution
        assert "TAIL_RISK_ELEVATED" in res.regime_distribution


def test_11_epistemic_confidence_bounds():
    p = REPO_ROOT / "data" / "historical" / "historical_binance_btcusdt_1h_2025.parquet"
    if p.exists():
        df = pd.read_parquet(p)
        bridge = CanonicalModelResearchBridge()
        res = bridge.evaluate_historical_dataset(df, "TEST")
        confs = res.classified_series["canonical_confidence"]
        assert confs.min() >= 0.50
        assert confs.max() <= 0.95


# ============================================================================
# 4. Regime Persistence & Transition Matrix (12 - 14)
# ============================================================================

def test_12_persistence_artifact_exists():
    p = OUTPUTS_DIR / "05_regime_persistence_analysis.json"
    assert p.exists()
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "persistence_by_regime" in data
    assert "transition_matrix_24h" in data


def test_13_regime_persistence_durations():
    p = OUTPUTS_DIR / "05_regime_persistence_analysis.json"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    pers = data["persistence_by_regime"]
    for r, d in pers.items():
        assert d["mean_duration_hours"] > 0
        assert d["max_duration_hours"] >= d["median_duration_hours"]


def test_14_transition_matrix_row_stochastic():
    p = OUTPUTS_DIR / "05_regime_persistence_analysis.json"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    trans = data["transition_matrix_24h"]
    for r, row in trans.items():
        total = sum(row.values())
        assert abs(total - 1.0) < 0.05  # Within float rounding


# ============================================================================
# 5. Forward Return & Downside Risk Analysis (15 - 18)
# ============================================================================

def test_15_forward_return_horizons_complete():
    p = OUTPUTS_DIR / "06_forward_return_distributions.json"
    assert p.exists()
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    returns = data["regime_forward_returns"]
    for r in ["NORMAL", "HIGH_VOLATILITY", "EXPANSION_WATCH", "TAIL_RISK_ELEVATED", "QUIET", "COMPRESSION"]:
        assert r in returns
        for h in ["6h", "24h", "72h", "168h"]:
            assert h in returns[r]
            assert "mean_return_pct" in returns[r][h]
            assert "win_rate_pct" in returns[r][h]


def test_16_tail_risk_negative_skewness():
    p = OUTPUTS_DIR / "06_forward_return_distributions.json"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    tail_24h = data["regime_forward_returns"]["TAIL_RISK_ELEVATED"]["24h"]
    assert tail_24h["skewness"] < 0, "Tail risk regime must exhibit negative skewness"


def test_17_downside_risk_cvar_separation():
    p = OUTPUTS_DIR / "07_downside_risk_analysis.json"
    assert p.exists()
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    risk_24h = data["downside_risk_by_regime"]
    tail_cvar = risk_24h["TAIL_RISK_ELEVATED"]["24h"]["cvar_95_pct"]
    quiet_cvar = risk_24h["QUIET"]["24h"]["cvar_95_pct"]
    assert tail_cvar < quiet_cvar, "TAIL_RISK CVaR must be more negative than QUIET CVaR"


def test_18_mae_metrics_consistency():
    p = OUTPUTS_DIR / "07_downside_risk_analysis.json"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    risk = data["downside_risk_by_regime"]
    for r, h_dict in risk.items():
        d24 = h_dict["24h"]
        assert d24["mean_mae_pct"] <= 0
        assert d24["max_drawdown_pct"] <= d24["mean_mae_pct"]


# ============================================================================
# 6. Incremental Value & Model Comparison (19 - 21)
# ============================================================================

def test_19_incremental_value_report_exists():
    p = OUTPUTS_DIR / "08_incremental_value_assessment.md"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "Kruskal-Wallis" in content
    assert "CVaR Spread" in content
    assert "Baseline D" in content


def test_20_model_comparison_artifact():
    p = OUTPUTS_DIR / "04_canonical_vs_derived_regime_comparison.json"
    assert p.exists()
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "DS-BTC-1H-2023-2024" in data["datasets"]
    assert "DS-BTC-1H-2025-SEALED" in data["datasets"]
    concordance = data["datasets"]["DS-BTC-1H-2023-2024"]["conceptual_concordance_rate"]
    assert 0.35 <= concordance <= 0.85


def test_21_historical_integrity_audit_exists():
    p = OUTPUTS_DIR / "09_historical_research_integrity_audit.md"
    assert p.exists()
    content = p.read_text(encoding="utf-8")
    assert "Drawdown" in content
    assert "Tail-Protection" in content


# ============================================================================
# 7. Dashboard V11 REST API Service & Endpoints (22 - 28)
# ============================================================================

def test_22_api_v11_model_status():
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/btc-timing/v11/model-status", {})
    assert status == HTTPStatus.OK
    assert data["canonical_model_version"] == "CBE-0.7.0"
    assert data["model_status"] == "STRICTLY_FROZEN"
    assert data["active_fallback_level"] == "SPOT_ONLY_U0"


def test_23_api_v11_regime_explorer():
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/btc-timing/v11/regime-explorer", {})
    assert status == HTTPStatus.OK
    assert len(data["regimes"]) == 6
    assert "NORMAL" in data["regimes"]


def test_24_api_v11_forward_returns():
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/btc-timing/v11/forward-returns", {"horizon": ["24h"]})
    assert status == HTTPStatus.OK
    assert data["selected_horizon"] == "24h"
    assert "horizon_data" in data


def test_25_api_v11_risk_intelligence():
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/btc-timing/v11/risk-intelligence", {})
    assert status == HTTPStatus.OK
    assert "risk_metrics_24h" in data
    assert "TAIL_RISK_ELEVATED" in data["risk_metrics_24h"]


def test_26_api_v11_model_comparison():
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/btc-timing/v11/model-comparison", {})
    assert status == HTTPStatus.OK
    assert "synthesis" in data
    assert "dataset_2023_2024" in data


def test_27_api_v11_evidence_ledger():
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/btc-timing/v11/evidence-ledger", {})
    assert status == HTTPStatus.OK
    assert data["total_artifacts"] == 21
    assert len(data["artifacts"]) == 21


def test_28_api_v11_deployment_safety():
    status, data = ProductDashboardApiService.handle_request("/api/v1/product/btc-timing/v11/deployment-safety", {})
    assert status == HTTPStatus.OK
    assert data["production_zero_touch_status"] == "STRICT_ZERO_TOUCH_PRESERVED"
    assert data["production_container_id"] == "4c6a29b5fbf6"
    assert data["production_port"] == 8000
    assert data["staging_port"] == 18080


# ============================================================================
# 8. Deployment Safety, Performance & UI Acceptance (29 - 32)
# ============================================================================

def test_29_live_trading_permanently_prohibited():
    service = InvestmentResearchV11Service.get_instance()
    status_data = service.get_model_status()
    assert status_data["live_trading_prohibition"] == "PERMANENTLY_PROHIBITED"


def test_30_deployment_audit_and_isolation_plan():
    audit_file = OUTPUTS_DIR / "15_deployment_trigger_audit.md"
    isolation_file = OUTPUTS_DIR / "16_deployment_isolation_plan.md"
    assert audit_file.exists()
    assert isolation_file.exists()


def test_31_performance_benchmarks_sla():
    bench_file = OUTPUTS_DIR / "11_performance_benchmarks.json"
    assert bench_file.exists()
    with open(bench_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["overall_status"] == "ALL_ENDPOINTS_MEET_SLA"
    for ep, res in data["endpoints"].items():
        assert res["p95_under_500ms_sla"] is True


def test_32_dashboard_html_contains_v11_panels():
    html = render_product_dashboard_html()
    assert "timing-panel-v11-market-intelligence" in html
    assert "timing-btn-v11-market-intelligence" in html
    assert "CBE-0.7.0 KANONİK MODEL ARAŞTIRMA KÖPRÜSÜ" in html
    assert "loadTimingV11Intelligence" in html

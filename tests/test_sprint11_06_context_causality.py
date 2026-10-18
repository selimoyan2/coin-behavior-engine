"""
Sprint 11.06 Automated Verification Test Suite
================================================
Comprehensive verification of Historical News Provenance, Context Causality,
Controlled Ablation Experiments, Rejected Trade Attribution, and Market Regime Validation:
- Fail-closed research safety interlocks
- 122-event provenance audit, categorization, and latency checks
- Identification of derivative kline proxies and altcoin noise
- Numerical reproduction of Sprint 11.05 ledger metrics
- Controlled ablation experiments across Models A through G
- 100-seed random trade matching distribution vs Context Aware performance
- Trade-by-trade rejection attribution ledger
- Market regime performance decomposition
- Statistical significance evaluation and NO_VERIFIED_CONTEXT_EDGE verdict
- Deliverables existence and schema compliance
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.research_lab.configuration import (
    ResearchLabConfig,
    RESEARCH_LAB_ACTIVE,
    RESEARCH_TRADING_ENABLED,
    RESEARCH_PROSPECTIVE_OBSERVATION,
    RESEARCH_APPROVAL_4_AUTHORIZED,
)
from coin_behavior_engine.research_lab.contracts import (
    CandleData,
    ContextAblationExperimentRecord,
    EventIntelligenceRecord,
    MarketBehaviorFeatures,
    ProvenanceAuditRecord,
    RejectedTradeAttributionRecord,
)
from coin_behavior_engine.research_lab.historical_data import TimeframeAggregator
from coin_behavior_engine.research_lab.feature_engine import MarketBehaviorFeatureEngine
from coin_behavior_engine.research_lab.news_adapters import NewsIngestionCoordinator
from coin_behavior_engine.research_lab.provenance_auditor import HistoricalNewsProvenanceAuditor
from coin_behavior_engine.research_lab.ablation_engine import ControlledAblationEngine


# ---------------------------------------------------------------------------
# Test Category 1: Research Safety & Invariants
# ---------------------------------------------------------------------------
def test_sprint11_06_safety_invariants():
    """Ensure fail-closed safety interlocks and production isolation remain intact."""
    assert RESEARCH_LAB_ACTIVE is True
    assert RESEARCH_TRADING_ENABLED is False
    assert RESEARCH_PROSPECTIVE_OBSERVATION is False
    assert RESEARCH_APPROVAL_4_AUTHORIZED is False


# ---------------------------------------------------------------------------
# Test Category 2: Historical News Provenance Audit
# ---------------------------------------------------------------------------
def test_historical_news_provenance_audit_completeness():
    """Verify that all 122 historical events are audited across all criteria."""
    auditor = HistoricalNewsProvenanceAuditor()
    records = auditor.audit_all_events()

    assert len(records) == 122, f"Expected 122 events, got {len(records)}"

    # Check that each record has valid required fields
    for r in records:
        assert r.event_id.startswith("EVT-")
        assert len(r.headline) > 5
        assert r.source_url.startswith("http")
        assert r.observation_latency_seconds >= 0.0
        assert r.strict_provenance_verdict in [
            "PASS_STRICT_PROVENANCE",
            "PASS_WITH_RESERVATION_GENERAL_POLICY",
            "REJECT_ALTCOIN_NOISE",
            "REJECT_NON_CRYPTO_EQUITY",
            "REJECT_DERIVATIVES_PROXY",
            "REJECT_UNVERIFIED_PROVENANCE",
        ]

    df = pd.DataFrame([r.to_dict() for r in records])

    # 1. Check genuine macro events
    strict_pass = df[df["strict_provenance_verdict"] == "PASS_STRICT_PROVENANCE"]
    assert len(strict_pass) == 4, f"Expected exactly 4 strict macro events, got {len(strict_pass)}"
    pass_ids = set(strict_pass["event_id"].tolist())
    assert "EVT-FED-202610071800" in pass_ids
    assert "EVT-FED-202610131800" in pass_ids
    assert "EVT-BLS-CPI-20261014" in pass_ids
    assert "EVT-BLS-NFP-20261002" in pass_ids

    # 2. Check liquidation proxy classification
    liq_events = df[df["event_id"] == "EVT-LIQ-20261007-0815"]
    assert len(liq_events) == 1
    assert liq_events.iloc[0]["strict_provenance_verdict"] == "REJECT_DERIVATIVES_PROXY"
    assert not bool(liq_events.iloc[0]["is_genuine_external_news"])

    # 3. Check non-crypto SEC releases
    sec_events = df[df["source_name"] == "US Securities and Exchange Commission"]
    assert len(sec_events) == 14
    non_crypto_sec = sec_events[sec_events["strict_provenance_verdict"] == "REJECT_NON_CRYPTO_EQUITY"]
    assert len(non_crypto_sec) == 13

    # 4. Check altcoin noise from Binance CMS
    binance_events = df[df["source_name"] == "Binance Exchange Official Announcements"]
    assert len(binance_events) == 103
    rejected_binance = binance_events[binance_events["strict_provenance_verdict"] == "REJECT_ALTCOIN_NOISE"]
    assert len(rejected_binance) == 103


# ---------------------------------------------------------------------------
# Test Category 3: Independent Reproduction of Previous Results
# ---------------------------------------------------------------------------
def test_independent_reproduction_numerical_parity():
    """Verify that Sprint 11.05 ledger metrics reproduce with exact numerical parity."""
    parquet_path = Path("data/research_lab/binance_BTCUSDT_1m_recent.parquet")
    assert parquet_path.is_file(), "Parquet cache file required"

    df_1m = pd.read_parquet(parquet_path)
    candles_1m = [
        CandleData(
            timestamp_open=int(r["timestamp_open"]),
            timestamp_close=int(r["timestamp_close"]),
            datetime_open_utc=str(r["datetime_open_utc"]),
            datetime_close_utc=str(r["datetime_close_utc"]),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["volume"]),
            interval="1m",
        )
        for _, r in df_1m.iterrows()
    ]

    candles_5m = TimeframeAggregator.aggregate(candles_1m, target_interval="5m", symbol="BTCUSDT", allow_partial_boundaries=False)
    candles_1h = TimeframeAggregator.aggregate(candles_5m, target_interval="1h", symbol="BTCUSDT", allow_partial_boundaries=False)
    candles_4h = TimeframeAggregator.aggregate(candles_5m, target_interval="4h", symbol="BTCUSDT", allow_partial_boundaries=False)

    features = MarketBehaviorFeatureEngine.compute_all(candles_5m, lookback_bars=24, candles_1h=candles_1h, candles_4h=candles_4h)
    coordinator = NewsIngestionCoordinator()
    events = coordinator.ingest_all_events(candles_5m[0].datetime_open_utc, candles_5m[-1].datetime_close_utc)

    engine = ControlledAblationEngine()
    repro = engine.reproduce_sprint11_05_results(candles_5m, features, events)

    assert repro["reproduction_verdict"] == "VERIFIED_EXACT_NUMERICAL_PARITY"
    strats = repro["strategies"]

    # Verify Strategy A
    strat_a = strats["Strategy_A_Technical_Only"]
    assert strat_a["total_trades"] == 137
    assert strat_a["net_pnl_usd"] == -981.48
    assert strat_a["return_pct"] == -9.815
    assert strat_a["max_drawdown_pct"] == 9.78
    assert strat_a["win_rate_pct"] == 19.7
    assert strat_a["total_fees_usd"] == 652.56
    assert strat_a["matches_sprint11_05_baseline"] is True

    # Verify Strategy B
    strat_b = strats["Strategy_B_Context_Aware"]
    assert strat_b["total_trades"] == 91
    assert strat_b["net_pnl_usd"] == -766.61
    assert strat_b["return_pct"] == -7.666
    assert strat_b["max_drawdown_pct"] == 7.67
    assert strat_b["win_rate_pct"] == 8.8
    assert strat_b["total_fees_usd"] == 438.28
    assert strat_b["matches_sprint11_05_baseline"] is True

    # Verify Strategy C
    strat_c = strats["Strategy_C_Risk_Controlled"]
    assert strat_c["total_trades"] == 49
    assert strat_c["net_pnl_usd"] == -305.66
    assert strat_c["return_pct"] == -3.057
    assert strat_c["max_drawdown_pct"] == 3.07
    assert strat_c["win_rate_pct"] == 10.2
    assert strat_c["total_fees_usd"] == 180.81
    assert strat_c["matches_sprint11_05_baseline"] is True


# ---------------------------------------------------------------------------
# Test Category 4: Controlled Ablation & Multi-Seed Statistical Edge
# ---------------------------------------------------------------------------
def test_controlled_ablation_models_and_multi_seed_distribution():
    """Verify that random trade removal outperforms context-aware filtering across 100 seeds."""
    parquet_path = Path("data/research_lab/binance_BTCUSDT_1m_recent.parquet")
    df_1m = pd.read_parquet(parquet_path)
    candles_1m = [
        CandleData(
            timestamp_open=int(r["timestamp_open"]),
            timestamp_close=int(r["timestamp_close"]),
            datetime_open_utc=str(r["datetime_open_utc"]),
            datetime_close_utc=str(r["datetime_close_utc"]),
            open=float(r["open"]),
            high=float(r["high"]),
            low=float(r["low"]),
            close=float(r["close"]),
            volume=float(r["volume"]),
            interval="1m",
        )
        for _, r in df_1m.iterrows()
    ]

    candles_5m = TimeframeAggregator.aggregate(candles_1m, target_interval="5m", symbol="BTCUSDT", allow_partial_boundaries=False)
    candles_1h = TimeframeAggregator.aggregate(candles_5m, target_interval="1h", symbol="BTCUSDT", allow_partial_boundaries=False)
    candles_4h = TimeframeAggregator.aggregate(candles_5m, target_interval="4h", symbol="BTCUSDT", allow_partial_boundaries=False)

    features = MarketBehaviorFeatureEngine.compute_all(candles_5m, lookback_bars=24, candles_1h=candles_1h, candles_4h=candles_4h)
    coordinator = NewsIngestionCoordinator()
    events = coordinator.ingest_all_events(candles_5m[0].datetime_open_utc, candles_5m[-1].datetime_close_utc)

    engine = ControlledAblationEngine()
    records = engine.run_ablation_experiments(candles_5m, features, events, num_seeds=100)

    rec_map = {r.model_id: r for r in records}
    assert "Model_A_Technical_Only" in rec_map
    assert "Model_B_Context_Aware" in rec_map
    assert "Model_C_Random_Trade_Matching" in rec_map
    assert "Model_D_Time_Matched_Random_Filter" in rec_map
    assert "Model_E_Volatility_Only_Filter" in rec_map
    assert "Model_F_HTF_Regime_Filter" in rec_map
    assert "Model_G_Context_Plus_Risk_Control" in rec_map

    mod_b = rec_map["Model_B_Context_Aware"]
    mod_c = rec_map["Model_C_Random_Trade_Matching"]
    mod_e = rec_map["Model_E_Volatility_Only_Filter"]

    # 1. Random trade removal performed significantly better than Model B
    assert mod_c.net_pnl_mean > mod_b.net_pnl_usd, f"Random mean ({mod_c.net_pnl_mean}) must beat Model B ({mod_b.net_pnl_usd})"
    assert mod_c.win_rate_mean > mod_b.win_rate_pct, f"Random win rate ({mod_c.win_rate_mean}%) must beat Model B ({mod_b.win_rate_pct}%)"

    # 2. Model B underperformed even the worst random seed
    assert mod_b.net_pnl_usd < mod_c.net_pnl_min, f"Model B ({mod_b.net_pnl_usd}) was worse than worst random seed ({mod_c.net_pnl_min})"

    # 3. Model E (Volatility filter) beats Model B without news
    assert mod_e.net_pnl_usd > mod_b.net_pnl_usd
    assert mod_e.max_drawdown_pct < mod_b.max_drawdown_pct


# ---------------------------------------------------------------------------
# Test Category 5: Deliverables & Schema Integrity
# ---------------------------------------------------------------------------
def test_sprint11_06_deliverables_and_verdict():
    """Verify that all Sprint 11.06 deliverables exist and declare NO_VERIFIED_CONTEXT_EDGE."""
    out_dir = Path("research_outputs")
    required_files = [
        "historical_news_provenance_audit.csv",
        "verified_event_coverage_report.md",
        "reproduced_sprint11_05_results.json",
        "context_ablation_experiments.csv",
        "rejected_trade_attribution.csv",
        "market_regime_comparison.csv",
        "context_edge_statistical_report.md",
        "research_report_11_06.md",
        "run_manifest_11_06.json",
    ]

    for f_name in required_files:
        f_path = out_dir / f_name
        assert f_path.is_file(), f"Missing required deliverable: {f_name}"
        assert f_path.stat().st_size > 50, f"File {f_name} is unexpectedly empty"

    # Verify statistical report verdict
    stat_report_text = (out_dir / "context_edge_statistical_report.md").read_text(encoding="utf-8")
    assert "NO_VERIFIED_CONTEXT_EDGE" in stat_report_text

    # Verify master report verdict
    master_report_text = (out_dir / "research_report_11_06.md").read_text(encoding="utf-8")
    assert "NO_VERIFIED_CONTEXT_EDGE" in master_report_text

    # Verify run manifest
    manifest_data = json.loads((out_dir / "run_manifest_11_06.json").read_text(encoding="utf-8"))
    assert manifest_data["sprint"] == "11.06"
    assert manifest_data["findings_summary"]["verdict"] == "NO_VERIFIED_CONTEXT_EDGE"
    assert len(manifest_data["deliverables"]) == 9

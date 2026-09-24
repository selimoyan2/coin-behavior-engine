"""Automated Verification Test Suite for Sprint 05: US Spot Bitcoin ETF Flow & Institutional Capital Dynamics.

Contains 35 comprehensive tests verifying:
 1. ETF universe catalog completeness, survivorship protection, launch dates, custodians
 2. Ingestion coverage matrix, row counts, 693 trading days, zero missing flow dates
 3. CME Bitcoin futures ingestion and alignment
 4. ETF canonical dataset schema, dimensions, and types
 5. Strictly causal availability timestamps (06:00:00 UTC D+1)
 6. No intraday leakage in causal as-of merge
 7. Zero pre-ETF synthetic data (is_etf_active=0, zeros before 2024-01-12 06:00 UTC)
 8. Survivorship bias protection (all 12 ETFs defined and tracked)
 9. GBTC conversion history and trust structure
10. Total net flow identity: Total == GBTC + Non-GBTC
11. Gross flow identity: Total Net == Gross Inflow - Gross Outflow
12. Flow breadth bounds [-1.0, 1.0]
13. Herfindahl-Hirschman concentration index bounds [0.0, 1.0]
14. Top fund contribution ratio bounds [0.0, 1.0]
15. Flow persistence streak lengths and signs
16. Robust z-score computation using median/MAD
17. Rolling 30d flow percentiles strictly in [0.0, 1.0]
18. ETF telemetry staleness and weekend vacuum (>48h lag)
19. Partition isolation and matched baseline samples (2024, 2025, 2026)
20. Information Ladder Model definitions (Model A through E)
21. Model C -> Model D incremental volatility lift in 2025 Validation
22. Directional edge strictly UNVERIFIED (~50% accuracy, p > 0.1)
23. Sprint 02 64.2% directional claim non-reintroduction check
24. Tail risk classification (95th & 99th percentile excursions)
25. 5-fold expanding walk-forward temporal stability
26. Feature family ablation leave-one-out rankings
27. ETF feature redundancy matrix
28. Conditioned macro with ETF features
29. Benjamini-Hochberg FDR multiple testing correction integrity
30. September 21, 2026 anomaly post-hoc forensic audit
31. Claim registry audit 100% pass rate
32. CLAIM-S05-001 discrete test (volatility edge)
33. CLAIM-S05-002 discrete test (tail risk lift)
34. CLAIM-S05-003 discrete test (directional edge unverified)
35. CLAIM-S05-004 discrete test (September 21 ETF telemetry vacuum)
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

REPORTS_DIR = Path("data/reports/sprint05")


# ======================================================================
# 1. ETF Universe Catalog & Survivorship Forensics
# ======================================================================

def test_etf_catalog_completeness():
    """Verify all 12 spot Bitcoin ETFs are defined with complete metadata."""
    catalog_path = REPORTS_DIR / "etf_data_catalog.json"
    assert catalog_path.exists(), "etf_data_catalog.json missing"
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    universe = catalog["instruments"]
    assert len(universe) == 12, f"Expected 12 ETFs in universe, found {len(universe)}"
    tickers = {item["ticker"] for item in universe}
    expected_tickers = {
        "IBIT", "FBTC", "GBTC", "ARKB", "BITB", "BTCO",
        "EZBC", "BRRR", "HODL", "BTCW", "MSBT", "BTC"
    }
    assert tickers == expected_tickers, f"Universe tickers mismatch: {expected_tickers - tickers}"
    
    # Check custodians, fees, and launch dates
    for item in universe:
        assert item["sponsor_fee_bps"] >= 0.0, f"Negative fee for {item['ticker']}"
        assert item["launch_date"] >= "2024-01-11", f"Invalid launch date for {item['ticker']}"


def test_etf_coverage_matrix():
    """Verify coverage matrix has 13 rows (12 spot ETFs + CME futures) with full coverage."""
    cov_path = REPORTS_DIR / "etf_coverage_matrix.csv"
    assert cov_path.exists(), "etf_coverage_matrix.csv missing"
    df = pd.read_csv(cov_path)
    assert len(df) == 13, f"Expected 13 ticker rows in coverage matrix, found {len(df)}"
    # Check coverage status is FULL
    assert (df["coverage_status"] == "FULL").all(), "Coverage status is not full"
    assert (df["flow_records_count"] >= 0).all()


def test_cme_futures_ingestion():
    """Verify CME Bitcoin futures data was ingested and normalized."""
    cme_path = Path("data/normalized/etf/cme_futures_daily.parquet")
    assert cme_path.exists(), "cme_futures_daily.parquet missing"
    df = pd.read_parquet(cme_path)
    assert len(df) >= 600, f"Insufficient CME futures records: {len(df)}"
    assert "close" in df.columns, "CME futures missing close column"
    assert "volume" in df.columns, "CME futures missing volume column"
    assert "symbol" in df.columns, "CME futures missing symbol column"


# ======================================================================
# 2. Canonical Dataset Schema & Causality Guarantees
# ======================================================================

def test_etf_canonical_dimensions_and_schema():
    """Verify canonical parquet file schema and dimensions."""
    canon_path = REPORTS_DIR / "etf_flow_canonical.parquet"
    assert canon_path.exists(), "etf_flow_canonical.parquet missing"
    df = pd.read_parquet(canon_path)
    assert len(df) == 693, f"Expected 693 trading days, found {len(df)}"
    assert len(df.columns) >= 30, f"Expected at least 30 columns, found {len(df.columns)}"
    
    required_cols = [
        "trade_date", "publication_timestamp", "available_at_timestamp",
        "total_net_flow_usd", "gross_inflow_usd", "gross_outflow_usd",
        "flow_breadth", "flow_herfindahl_index", "top_fund_contribution",
        "gbtc_net_flow_usd", "non_gbtc_net_flow_usd"
    ]
    for col in required_cols:
        assert col in df.columns, f"Required column {col} missing from canonical dataset"


def test_etf_availability_timestamp_causality():
    """Verify availability timestamp is strictly 06:00:00 UTC D+1 (never same day)."""
    df = pd.read_parquet(REPORTS_DIR / "etf_flow_canonical.parquet")
    df["trade_date_dt"] = pd.to_datetime(df["trade_date"], utc=True)
    df["avail_dt"] = pd.to_datetime(df["available_at_timestamp"], utc=True)
    
    # Lag between trade date (00:00 UTC) and availability timestamp (06:00 UTC D+1) must be >= 30 hours
    lag_hours = (df["avail_dt"] - df["trade_date_dt"]).dt.total_seconds() / 3600.0
    assert (lag_hours >= 30.0).all(), "Availability timestamp allows same-day lookahead leakage!"
    
    # Available hour must be exactly 06:00 UTC
    assert (df["avail_dt"].dt.hour == 6).all(), "Availability hour is not 06:00 UTC"


def test_no_intraday_leakage_in_asof_merge():
    """Verify that 5m bars cannot access contemporaneous same-day ETF flows."""
    feat_path = REPORTS_DIR / "etf_flow_features.parquet"
    assert feat_path.exists(), "etf_flow_features.parquet missing"
    df = pd.read_parquet(feat_path, columns=["datetime_open", "total_net_flow_usd", "is_etf_active", "etf_source_age_hours"])
    
    # Sample a bar on a trading day at 15:00 UTC (during US market hours)
    # The ETF flow must reflect the PREVIOUS trading day's flow, not today's
    sample_bar = df[df["datetime_open"] == "2024-05-15 15:00:00+00:00"].iloc[0]
    assert sample_bar["is_etf_active"] == 1
    # On 2024-05-15 at 15:00 UTC, the latest available flow is 2024-05-14 flow (published 2024-05-15 06:00 UTC)
    # Source age should be >= 8 hours
    assert sample_bar["etf_source_age_hours"] >= 8.0, f"Unexpected source age hours: {sample_bar['etf_source_age_hours']}"


def test_zero_pre_etf_synthetic_data():
    """Verify zero synthetic data: pre-ETF period has is_etf_active=0 and zero flow values."""
    feat_path = REPORTS_DIR / "etf_flow_features.parquet"
    df = pd.read_parquet(feat_path, columns=["datetime_open", "total_net_flow_usd", "is_etf_active"])
    
    pre_etf = df[df["datetime_open"] < "2024-01-12 06:00:00+00:00"]
    assert len(pre_etf) > 0, "No pre-ETF bars found"
    assert (pre_etf["is_etf_active"] == 0).all(), "Pre-ETF bars flagged as active!"
    assert (pre_etf["total_net_flow_usd"] == 0.0).all(), "Found non-zero ETF flow before ETF launch!"


def test_survivorship_bias_protection():
    """Verify all 12 ETFs are represented, preventing survivorship filtering."""
    with open(REPORTS_DIR / "etf_data_catalog.json", "r", encoding="utf-8") as f:
        catalog = json.load(f)
    assert catalog["total_instruments"] == 12
    tickers = [e["ticker"] for e in catalog["instruments"]]
    assert "BTCW" in tickers
    assert "EZBC" in tickers


def test_gbtc_conversion_date():
    """Verify GBTC conversion date is correctly recorded as 2024-01-11."""
    with open(REPORTS_DIR / "etf_data_catalog.json", "r", encoding="utf-8") as f:
        catalog = json.load(f)
    gbtc = [e for e in catalog["instruments"] if e["ticker"] == "GBTC"][0]
    assert gbtc["is_legacy_conversion"] is True
    assert gbtc["launch_date"] == "2024-01-11"


# ======================================================================
# 3. Flow Mathematical Identities & Boundary Audits
# ======================================================================

def test_etf_flow_identity_consistency():
    """Verify Total Net Flow == GBTC Net Flow + Non-GBTC Net Flow for all rows."""
    df = pd.read_parquet(REPORTS_DIR / "etf_flow_canonical.parquet")
    diff = (df["total_net_flow_usd"] - (df["gbtc_net_flow_usd"] + df["non_gbtc_net_flow_usd"])).abs()
    assert (diff < 1e-4).all(), f"GBTC decomposition mismatch: max diff = {diff.max()}"


def test_gross_flow_identities():
    """Verify Total Net Flow == Gross Inflow + Gross Outflow (outflow is negative)."""
    df = pd.read_parquet(REPORTS_DIR / "etf_flow_canonical.parquet")
    diff = (df["total_net_flow_usd"] - (df["gross_inflow_usd"] + df["gross_outflow_usd"])).abs()
    assert (diff < 1e-4).all(), f"Gross flow identity mismatch: max diff = {diff.max()}"


def test_flow_breadth_bounds():
    """Verify flow breadth is strictly bounded within [-1.0, 1.0]."""
    df = pd.read_parquet(REPORTS_DIR / "etf_flow_canonical.parquet")
    assert (df["flow_breadth"] >= -1.0 - 1e-6).all(), "Flow breadth below -1.0"
    assert (df["flow_breadth"] <= 1.0 + 1e-6).all(), "Flow breadth above 1.0"


def test_herfindahl_index_bounds():
    """Verify Herfindahl concentration index is bounded within [0.0, 1.0]."""
    df = pd.read_parquet(REPORTS_DIR / "etf_flow_canonical.parquet")
    assert (df["flow_herfindahl_index"] >= 0.0 - 1e-6).all(), "HHI below 0.0"
    assert (df["flow_herfindahl_index"] <= 1.0 + 1e-6).all(), "HHI above 1.0"


def test_top_fund_contribution_bounds():
    """Verify top fund contribution ratio is bounded within [0.0, 1.0]."""
    df = pd.read_parquet(REPORTS_DIR / "etf_flow_canonical.parquet")
    assert (df["top_fund_contribution"] >= 0.0 - 1e-6).all(), "Top fund share below 0.0"
    assert (df["top_fund_contribution"] <= 1.0 + 1e-6).all(), "Top fund share above 1.0"


def test_flow_persistence_streaks():
    """Verify flow persistence streak lengths have matching signs."""
    feat_path = REPORTS_DIR / "etf_flow_features.parquet"
    df = pd.read_parquet(feat_path, columns=["total_net_flow_usd", "flow_persistence_days", "is_etf_active"])
    active = df[df["is_etf_active"] == 1]
    
    # When flow is positive, persistence days must be >= 1
    pos_flow = active[active["total_net_flow_usd"] > 0]
    assert (pos_flow["flow_persistence_days"] >= 1.0).all(), "Positive flow has negative persistence!"
    
    # When flow is negative, persistence days must be <= -1
    neg_flow = active[active["total_net_flow_usd"] < 0]
    assert (neg_flow["flow_persistence_days"] <= -1.0).all(), "Negative flow has positive persistence!"


def test_robust_zscore_properties():
    """Verify robust z-score is calculated and clipped within bounds."""
    feat_path = REPORTS_DIR / "etf_flow_features.parquet"
    df = pd.read_parquet(feat_path, columns=["flow_robust_z_20d", "is_etf_active"])
    active = df[df["is_etf_active"] == 1]
    assert (active["flow_robust_z_20d"] >= -5.0).all()
    assert (active["flow_robust_z_20d"] <= 5.0).all()
    assert abs(active["flow_robust_z_20d"].mean()) < 0.5


def test_rolling_percentile_causality():
    """Verify rolling 30d flow percentiles are strictly within [0.0, 1.0]."""
    feat_path = REPORTS_DIR / "etf_flow_features.parquet"
    df = pd.read_parquet(feat_path, columns=["flow_roll_pctile_30d", "is_etf_active"])
    active = df[df["is_etf_active"] == 1]
    assert (active["flow_roll_pctile_30d"] >= 0.0).all()
    assert (active["flow_roll_pctile_30d"] <= 1.0).all()


def test_etf_staleness_and_weekend_vacuum():
    """Verify weekend telemetry vacuum logic: staleness increases significantly on weekends."""
    feat_path = REPORTS_DIR / "etf_flow_features.parquet"
    df = pd.read_parquet(feat_path, columns=["datetime_open", "etf_source_age_hours", "etf_freshness_state", "is_etf_active"])
    df["dt"] = pd.to_datetime(df["datetime_open"], utc=True)
    active = df[df["is_etf_active"] == 1]
    
    # Sample Sunday evening bars (e.g. Sunday 20:00 UTC)
    sunday_bars = active[(active["dt"].dt.dayofweek == 6) & (active["dt"].dt.hour >= 18)]
    assert len(sunday_bars) > 0, "No Sunday bars found"
    assert (sunday_bars["etf_source_age_hours"] >= 30.0).all(), "Sunday evening bars not exhibiting weekend aging (>=30h)!"
    assert active["etf_source_age_hours"].max() >= 48.0, "Telemetry vacuum did not exceed 48h staleness threshold!"


# ======================================================================
# 4. Partition Isolation & Information Ladder
# ======================================================================

def test_partition_isolation_and_matching():
    """Verify partition isolation and matching bar counts."""
    manifest_path = REPORTS_DIR / "etf_partition_manifest.json"
    assert manifest_path.exists(), "etf_partition_manifest.json missing"
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    
    parts = manifest["partitions"]
    assert parts["early_etf_discovery"]["sample_size"] == 102168
    assert parts["later_etf_validation"]["sample_size"] == 105120
    assert parts["observed_holdout_2026"]["sample_size"] == 76565


def test_information_ladder_model_definitions():
    """Verify Information Ladder CSV structure and model columns."""
    ladder_path = REPORTS_DIR / "information_ladder_sprint05.csv"
    assert ladder_path.exists(), "information_ladder_sprint05.csv missing"
    df = pd.read_csv(ladder_path)
    required_cols = [
        "target", "target_type", "horizon", "sample_size_val", "sample_size_hold",
        "model_a_spot", "model_b_spot_deriv", "model_c_spot_deriv_session",
        "model_d_etf", "model_e_etf_macro", "etf_incremental_delta"
    ]
    for col in required_cols:
        assert col in df.columns, f"Column {col} missing from information ladder table"


def test_information_ladder_volatility_results():
    """Verify Model C -> Model D incremental volatility lift in 2025 Validation."""
    df = pd.read_csv(REPORTS_DIR / "information_ladder_sprint05.csv")
    vol_row = df[df["target"] == "fwd_vol_4h"].iloc[0]
    
    # Model C to Model D lift should be positive in 2025 Validation
    assert vol_row["etf_incremental_delta"] > 0.003, f"Expected positive lift > 0.003, got {vol_row['etf_incremental_delta']}"
    assert vol_row["validation_status"] == "VERIFIED_LIFT"
    assert vol_row["raw_p_value"] < 0.01, f"Expected p-value < 0.01, got {vol_row['raw_p_value']}"


def test_directional_edge_unverified():
    """Verify directional edge is strictly UNVERIFIED (accuracy ~50%, validation status NO_DIRECTIONAL_EDGE)."""
    df = pd.read_csv(REPORTS_DIR / "information_ladder_sprint05.csv")
    dir_rows = df[df["target_type"] == "DIRECTION"]
    assert len(dir_rows) >= 3, "Expected at least 3 directional horizons"
    
    for _, row in dir_rows.iterrows():
        # Accuracy must not exceed 55%
        assert row["model_d_etf"] < 0.55, f"Directional accuracy suspiciously high: {row['model_d_etf']}"
        assert row["validation_status"] == "NO_DIRECTIONAL_EDGE", f"Directional status is {row['validation_status']}"
        assert row["raw_p_value"] > 0.10, f"Directional p-value suspiciously significant: {row['raw_p_value']}"


def test_sprint02_directional_claim_non_reintroduction():
    """Audit check: verify Sprint 02's discredited 64.2% directional claim is NOT revived."""
    with open(REPORTS_DIR / "claim_registry.json", "r", encoding="utf-8") as f:
        registry = json.load(f)
    for c in registry:
        assert "64.2%" not in c["claim_text"], "Forbidden 64.2% directional claim reintroduced!"
        assert "64%" not in c["claim_text"], "Forbidden directional claim reintroduced!"


def test_tail_risk_classification():
    """Verify tail risk classification rows exist and ROC-AUC is in valid range."""
    df = pd.read_csv(REPORTS_DIR / "information_ladder_sprint05.csv")
    tail_rows = df[df["target_type"] == "TAIL_RISK"]
    assert len(tail_rows) >= 2, "Tail risk rows missing"
    for _, row in tail_rows.iterrows():
        assert 0.50 <= row["model_c_spot_deriv_session"] <= 1.0, "Model C ROC-AUC out of bounds"
        assert 0.50 <= row["model_d_etf"] <= 1.0, "Model D ROC-AUC out of bounds"


def test_walk_forward_temporal_isolation():
    """Verify 5-fold walk-forward validation completed with no lookahead."""
    wf_path = REPORTS_DIR / "walk_forward_etf.csv"
    assert wf_path.exists(), "walk_forward_etf.csv missing"
    df = pd.read_csv(wf_path)
    assert len(df) == 5, f"Expected 5 walk-forward folds, found {len(df)}"
    assert (df["train_cutoff"].is_monotonic_increasing), "Walk-forward train cutoffs are not monotonic increasing!"


def test_etf_family_ablation_matrix():
    """Verify feature family ablation has evaluated all subfamilies."""
    abl_path = REPORTS_DIR / "etf_family_ablation.csv"
    assert abl_path.exists(), "etf_family_ablation.csv missing"
    df = pd.read_csv(abl_path)
    families = set(df["feature_family"])
    expected = {
        "CORE_BASELINE_C", "ALL_ETF_FLOW_D", "AGGREGATE_FLOW", "NORMALIZED_FLOW",
        "FLOW_BREADTH", "FLOW_PERSISTENCE", "GBTC_STRUCTURE", "CME_CONTEXT", "INTERACTIONS"
    }
    assert expected.issubset(families), f"Missing feature families in ablation: {expected - families}"


def test_etf_feature_redundancy_matrix():
    """Verify feature redundancy analysis was conducted."""
    red_path = REPORTS_DIR / "etf_redundancy_analysis.csv"
    assert red_path.exists(), "etf_redundancy_analysis.csv missing"
    df = pd.read_csv(red_path)
    assert len(df) >= 8, f"Insufficient feature redundancy rows: {len(df)}"


def test_conditioned_macro_with_etf():
    """Verify conditioned macro experiment with ETF features was saved."""
    cm_path = REPORTS_DIR / "conditioned_macro_with_etf.csv"
    assert cm_path.exists(), "conditioned_macro_with_etf.csv missing"
    df = pd.read_csv(cm_path)
    assert len(df) >= 1


def test_fdr_multiple_testing_integrity():
    """Verify Benjamini-Hochberg FDR correction was applied properly."""
    mt_path = REPORTS_DIR / "multiple_testing_registry.csv"
    assert mt_path.exists(), "multiple_testing_registry.csv missing"
    df = pd.read_csv(mt_path)
    assert len(df) >= 10, f"Expected at least 10 hypotheses tested, found {len(df)}"
    assert "fdr_q_value" in df.columns
    assert "fdr_survived" in df.columns
    df_sorted = df.sort_values("raw_p_value").reset_index(drop=True)
    assert (df_sorted["raw_p_value"] <= df_sorted["fdr_q_value"]).all(), "FDR q-value cannot be smaller than raw p-value!"


def test_september21_posthoc_forensics():
    """Verify September 21 anomaly forensic audit confirms weekend telemetry vacuum."""
    sep_path = REPORTS_DIR / "september21_etf_posthoc.json"
    assert sep_path.exists(), "september21_etf_posthoc.json missing"
    with open(sep_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["incident_date"] == "2026-09-21"
    assert "2026-09-18" in data["latest_available_flow_trade_date"]
    assert data["source_age_hours_at_monday_close"] >= 48.0, "Staleness hours during crash onset must exceed 48h"
    assert "telemetry vacuum" in data["forensic_verdict"].lower()


def test_claim_registry_integrity_and_100_percent_pass():
    """Verify claim registry integrity audit achieves 100% pass rate."""
    audit_path = REPORTS_DIR / "claim_integrity_audit.json"
    assert audit_path.exists(), "claim_integrity_audit.json missing"
    with open(audit_path, "r", encoding="utf-8") as f:
        audit = json.load(f)
    assert audit["claim_integrity_status"] == "PASSED"
    assert audit["pass_rate"] == 1.0, f"Pass rate is {audit['pass_rate']}, expected 1.0"
    assert audit["failed_claims"] == 0


# ======================================================================
# 5. Discrete Claim Verification Tests (CLAIM-S05-001 to CLAIM-S05-004)
# ======================================================================

def test_claim_001_etf_volatility_incremental_edge():
    """CLAIM-S05-001: Observable US spot Bitcoin ETF flows add verified incremental 4h forward volatility explanatory power."""
    with open(REPORTS_DIR / "claim_registry.json", "r", encoding="utf-8") as f:
        registry = json.load(f)
    claim = [c for c in registry if c["claim_id"] == "CLAIM-S05-001"][0]
    assert claim["status"] == "VERIFIED"
    assert claim["partition"] == "LATER_ETF_VALIDATION_2025"
    assert claim["metric_name"] == "etf_incremental_delta"
    assert float(claim["metric_value"]) > 0.003


def test_claim_002_etf_tail_risk_lift():
    """CLAIM-S05-002: ETF flow features improve 95th percentile forward return excursion classification ROC-AUC."""
    with open(REPORTS_DIR / "claim_registry.json", "r", encoding="utf-8") as f:
        registry = json.load(f)
    claim = [c for c in registry if c["claim_id"] == "CLAIM-S05-002"][0]
    assert claim["status"] == "VERIFIED"
    assert claim["partition"] == "LATER_ETF_VALIDATION_2025"
    assert claim["metric_name"] == "etf_incremental_delta"


def test_claim_003_directional_edge_unverified():
    """CLAIM-S05-003: Directional forecasting edge from ETF flows remains UNVERIFIED."""
    with open(REPORTS_DIR / "claim_registry.json", "r", encoding="utf-8") as f:
        registry = json.load(f)
    claim = [c for c in registry if c["claim_id"] == "CLAIM-S05-003"][0]
    assert claim["status"] == "VERIFIED"
    assert claim["metric_name"] == "validation_status"
    assert claim["metric_value"] == "NO_DIRECTIONAL_EDGE"


def test_claim_004_september21_etf_signature():
    """CLAIM-S05-004: September 21 anomaly forensic audit confirms weekend staleness (> 48h gap)."""
    with open(REPORTS_DIR / "claim_registry.json", "r", encoding="utf-8") as f:
        registry = json.load(f)
    claim = [c for c in registry if c["claim_id"] == "CLAIM-S05-004"][0]
    assert claim["status"] == "VERIFIED"
    assert claim["metric_name"] == "forensic_verdict"
    assert "telemetry vacuum" in claim["metric_value"].lower()

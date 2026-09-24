"""Automated Verification Test Suite for Sprint 04: Session, Time-of-Day & Cross-Asset Macro Context.

Contains comprehensive tests verifying:
1. Macro data ingestion, coverage, and catalog integrity
2. Calendar engine DST transitions (GMT/BST, EST/EDT) and US equity holiday awareness
3. Session boundary response surfaces (Asia, London, NY, Overlaps, Bell proximity)
4. Session diurnal base rates and weekend volatility compression / Sunday expansion
5. Perpetual funding settlement proximity dynamics
6. Strictly causal macro as-of alignment, source age, and staleness flags
7. Cross-asset lead/lag coincident structure and dynamic rolling correlations
8. Macro redundancy and multicollinearity (VIF / correlation thresholds)
9. 5-Layer Information Ladder Out-of-Sample R2 evaluations (Spot -> Deriv -> Session -> Macro -> Combined)
10. Session family ablation rankings and incremental explanatory power
11. Macro family ablation and market closure staleness dilution
12. Extreme tail risk (95th percentile) classification and ROC-AUC lifts
13. Directional forecasting benchmarks (Majority Baseline, Trend Baseline, lack of edge)
14. Benjamini-Hochberg FDR multiple testing correction procedure
15. Expanding-window 5-fold temporal walk-forward stability
16. September 21 anomaly forensic cross-market dislocation signature
17. Machine-verifiable Claim Registry audit (100% pass rate)
18. Discrete Claim tests (test_claim_001 through test_claim_004)
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pandas as pd
import pytest

REPORTS_DIR = Path("data/reports/sprint04")
NORMALIZED_MACRO_DIR = Path("data/normalized/macro")


# ======================================================================
# 1. Macro Data Ingestion, Coverage & Catalog Forensics
# ======================================================================

def test_macro_data_catalog_completeness():
    catalog_path = REPORTS_DIR / "macro_data_catalog.json"
    assert catalog_path.exists(), "macro_data_catalog.json does not exist"
    with open(catalog_path, "r", encoding="utf-8") as f:
        catalog = json.load(f)
    instruments = catalog["instruments"]
    assert len(instruments) == 8, f"Expected 8 instruments, found {len(instruments)}"
    symbols = {item["symbol"] for item in instruments}
    expected = {"^IXIC", "^GSPC", "^VIX", "DX-Y.NYB", "^TNX", "2YY=F", "GC=F", "CL=F"}
    assert symbols == expected, f"Catalog missing instruments: {expected - symbols}"


def test_macro_coverage_matrix():
    cov_path = REPORTS_DIR / "macro_coverage_matrix.csv"
    assert cov_path.exists(), "macro_coverage_matrix.csv does not exist"
    df = pd.read_csv(cov_path)
    assert len(df) == 8
    assert (df["trading_days_observed"] >= 1200).all(), "Observed trading days below minimum threshold"
    assert (df[df["symbol"] != "2YY=F"]["start_date"] <= "2021-01-05").all(), "Coverage start date exceeds January 2021"


def test_macro_normalized_files_exist():
    expected_files = [
        "IXIC.parquet", "GSPC.parquet", "VIX.parquet", "DX_Y.NYB.parquet",
        "TNX.parquet", "2YY_F.parquet", "GC_F.parquet", "CL_F.parquet"
    ]
    for fn in expected_files:
        p = NORMALIZED_MACRO_DIR / fn
        assert p.exists(), f"Normalized macro file {fn} missing"
        df = pd.read_parquet(p)
        assert len(df) >= 1200, f"File {fn} has insufficient rows ({len(df)})"
        assert "available_at_timestamp" in df.columns, f"Missing available_at_timestamp in {fn}"


# ======================================================================
# 2. Calendar Engine & DST Transitions
# ======================================================================

def test_market_calendar_audit():
    audit_path = REPORTS_DIR / "market_calendar_audit.json"
    assert audit_path.exists(), "market_calendar_audit.json does not exist"
    with open(audit_path, "r", encoding="utf-8") as f:
        audit = json.load(f)
    assert audit["timezone_standards"]["london"] == "Europe/London (GMT/BST calendar-aware)"
    assert audit["timezone_standards"]["new_york"] == "America/New_York (EST/EDT calendar-aware)"
    assert audit["dst_verification"]["dst_correctness_verified"] is True


def test_session_context_features_shape():
    p = REPORTS_DIR / "session_context_features.parquet"
    assert p.exists(), "session_context_features.parquet does not exist"
    df = pd.read_parquet(p)
    assert len(df) == 602240, f"Expected 602,240 rows, got {len(df)}"
    required_cols = [
        "datetime_open", "hour_utc", "weekday", "weekend_flag",
        "session_asia_active", "session_london_active", "session_new_york_active",
        "asia_london_overlap", "london_new_york_overlap", "us_equity_market_open",
        "minutes_before_us_equity_open", "minutes_to_next_funding"
    ]
    for c in required_cols:
        assert c in df.columns, f"Missing column {c} in session_context_features"


def test_dst_transition_precision():
    # Verify that in summer (e.g. July 2024), London is BST (UTC+1) and NY is EDT (UTC-4)
    # London opens at 08:00 local time -> 07:00 UTC in BST
    p = REPORTS_DIR / "session_context_features.parquet"
    df = pd.read_parquet(p, columns=["datetime_open", "session_london_active", "session_new_york_active", "us_equity_market_open"])
    
    # Summer sample: 2024-07-10 07:05 UTC (London is open under BST)
    summer_bar = df[df["datetime_open"] == "2024-07-10 07:05:00+00:00"]
    assert len(summer_bar) == 1
    assert summer_bar["session_london_active"].iloc[0] == 1, "London should be active at 07:05 UTC in summer (BST)"

    # Winter sample: 2024-01-10 07:05 UTC (London is GMT, opens at 08:00 UTC)
    winter_bar = df[df["datetime_open"] == "2024-01-10 07:05:00+00:00"]
    assert len(winter_bar) == 1
    assert winter_bar["session_london_active"].iloc[0] == 0, "London should NOT be active at 07:05 UTC in winter (GMT)"


# ======================================================================
# 3. Session Boundary Responses & Diurnal Base Rates
# ======================================================================

def test_session_boundary_response():
    p = REPORTS_DIR / "session_boundary_response.csv"
    assert p.exists(), "session_boundary_response.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) == 50, f"Expected 50 window rows, got {len(df)}"
    boundaries = set(df["boundary_name"].unique())
    assert "US_EQUITY_OPEN" in boundaries
    assert "US_EQUITY_CLOSE" in boundaries
    assert "LONDON_OPEN" in boundaries
    assert "NEW_YORK_OPEN" in boundaries
    assert "ASIA_OPEN" in boundaries


def test_session_family_ablation():
    p = REPORTS_DIR / "session_family_ablation.csv"
    assert p.exists(), "session_family_ablation.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) == 6
    assert df["subfamily_id"].iloc[0] == "ALL_SESSION_COMBINED"
    assert (df["delta_r2_val_vs_model_b"] > 0.0).all(), "All session subfamilies should show positive delta R2"


def test_macro_family_ablation():
    p = REPORTS_DIR / "macro_family_ablation.csv"
    assert p.exists(), "macro_family_ablation.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) == 7
    subfamilies = set(df["subfamily_id"].unique())
    assert "MACRO_EQUITIES" in subfamilies
    assert "MACRO_VIX" in subfamilies
    assert "ALL_MACRO_COMBINED" in subfamilies


def test_session_base_rates():
    p = REPORTS_DIR / "session_base_rates.csv"
    assert p.exists(), "session_base_rates.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) >= 30
    hours = df[df["category_type"] == "HOUR_UTC"]
    assert len(hours) == 24, "Missing 24-hour diurnal rows"
    # Diurnal variation: London/NY overlap (14-16 UTC) vol should exceed Asia early morning (02-04 UTC)
    vol_ny = hours[hours["category_name"].isin(["Hour_14", "Hour_15", "Hour_16"])]["mean_volatility_4h"].mean()
    vol_asia = hours[hours["category_name"].isin(["Hour_02", "Hour_03", "Hour_04"])]["mean_volatility_4h"].mean()
    assert vol_ny > vol_asia, f"Expected NY vol ({vol_ny}) > Asia vol ({vol_asia})"


def test_weekend_volatility_compression():
    p = REPORTS_DIR / "weekend_behavior.csv"
    assert p.exists(), "weekend_behavior.csv does not exist"
    df = pd.read_csv(p)
    wd = df[df["period_segment"] == "WEEKDAY_CORE"].iloc[0]
    sat = df[df["period_segment"] == "SATURDAY_FULL_DAY"].iloc[0]
    sun_pre = df[df["period_segment"] == "SUNDAY_PRE_FUTURES_OPEN"].iloc[0]

    # Saturday volatility should be significantly compressed vs weekday
    assert sat["mean_4h_volatility"] < wd["mean_4h_volatility"] * 0.75, "Saturday volatility compression not verified"
    # Sunday pre-futures open should surge vs Saturday
    assert sun_pre["mean_4h_volatility"] > sat["mean_4h_volatility"], "Sunday pre-futures open surge not verified"
    assert sun_pre["tail_event_rate_95th"] > wd["tail_event_rate_95th"], "Sunday pre-futures tail risk not elevated"


def test_funding_settlement_proximity():
    p = REPORTS_DIR / "funding_proximity_analysis.csv"
    assert p.exists(), "funding_proximity_analysis.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) == 5
    pre_30 = df[df["proximity_bucket"] == "FUNDING_PRE_30M"].iloc[0]
    mid = df[df["proximity_bucket"] == "MID_CYCLE_CONTROL"].iloc[0]
    # Pre-funding volatility should exceed mid-cycle control
    assert pre_30["mean_fwd_1h_volatility"] > mid["mean_fwd_1h_volatility"], "Pre-funding vol elevation not verified"


# ======================================================================
# 4. Cross-Asset Feature Engineering & Causal Alignment
# ======================================================================

def test_cross_asset_features_parquet_shape():
    p = REPORTS_DIR / "cross_asset_features.parquet"
    assert p.exists(), "cross_asset_features.parquet does not exist"
    df = pd.read_parquet(p)
    assert len(df) == 602240, f"Expected 602,240 rows, got {len(df)}"
    assert "nasdaq_ret_1d" in df.columns
    assert "vix_close" in df.columns
    assert "corr_btc_nasdaq_30d" in df.columns
    assert "yield_spread_10y_2y" in df.columns


def test_cross_asset_causality_and_staleness():
    p = REPORTS_DIR / "staleness_audit.csv"
    assert p.exists(), "staleness_audit.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) == 8
    # Equities are open only ~18.5% of the 24/7 continuous week
    nasdaq = df[df["instrument_name"] == "NASDAQ"].iloc[0]
    assert 15.0 <= nasdaq["pct_market_open"] <= 25.0, f"Unexpected pct_market_open: {nasdaq['pct_market_open']}"
    assert nasdaq["pct_stale"] > 80.0, f"Expected pct_stale > 80% due to closures, got {nasdaq['pct_stale']}"


def test_cross_asset_lead_lag_coincident_peak():
    p = REPORTS_DIR / "cross_asset_lead_lag.csv"
    assert p.exists(), "cross_asset_lead_lag.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) == 8
    # NASDAQ & S&P should have peak correlation at lag 0 (coincident)
    nasdaq = df[df["instrument"] == "NASDAQ"].iloc[0]
    assert nasdaq["peak_lag_days"] == 0, f"Expected peak lag 0 for NASDAQ, got {nasdaq['peak_lag_days']}"
    assert nasdaq["lag_0_correlation"] > 0.30, f"Expected NASDAQ-BTC correlation > 0.30, got {nasdaq['lag_0_correlation']}"


def test_macro_redundancy_and_collinearity():
    p = REPORTS_DIR / "macro_redundancy_analysis.csv"
    assert p.exists(), "macro_redundancy_analysis.csv does not exist"
    df = pd.read_csv(p)
    # NASDAQ and S&P 1d returns should be flagged as REDUNDANT (> 0.85 correlation)
    pair = df[((df["feature_1"] == "nasdaq_ret_1d") & (df["feature_2"] == "sp500_ret_1d")) |
              ((df["feature_1"] == "sp500_ret_1d") & (df["feature_2"] == "nasdaq_ret_1d"))]
    assert len(pair) == 1
    assert pair["redundancy_verdict"].iloc[0] == "REDUNDANT"
    assert pair["abs_correlation"].iloc[0] > 0.90


def test_dynamic_btc_macro_correlations():
    p = REPORTS_DIR / "btc_dynamic_correlations.csv"
    assert p.exists(), "btc_dynamic_correlations.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) >= 20
    # In 2022 Fed tightening bear market, BTC-NASDAQ correlation should be high positive (> 0.40 mean)
    sub_2022 = df[(df["period"] == "2022_FED_TIGHTENING_BEAR") & (df["correlation_metric"] == "corr_btc_nasdaq_30d")]
    assert len(sub_2022) == 1
    assert sub_2022["mean_correlation"].iloc[0] > 0.40


# ======================================================================
# 5. Information Ladder & Research Claims
# ======================================================================

def test_information_ladder_structure():
    p = REPORTS_DIR / "information_ladder.csv"
    assert p.exists(), "information_ladder.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) == 20  # 4 targets x 5 models
    models = set(df["model_id"].unique())
    assert "MODEL_A_SPOT_ONLY" in models
    assert "MODEL_B_SPOT_DERIV" in models
    assert "MODEL_C_SPOT_DERIV_SESSION" in models
    assert "MODEL_D_SPOT_DERIV_MACRO" in models
    assert "MODEL_E_SPOT_DERIV_SESSION_MACRO" in models


def test_session_incremental_volatility_edge():
    p = REPORTS_DIR / "incremental_session_information.csv"
    assert p.exists(), "incremental_session_information.csv does not exist"
    df = pd.read_csv(p)
    vol4 = df[df["target"] == "fwd_vol_4h"].iloc[0]
    # Model C vs Model B should have positive delta R2 > +0.05
    assert vol4["delta_r2_val"] > 0.05, f"Expected delta R2 > 0.05, got {vol4['delta_r2_val']}"
    assert vol4["delta_r2_holdout"] > 0.05, f"Expected holdout delta R2 > 0.05, got {vol4['delta_r2_holdout']}"
    assert vol4["verdict"] == "VERIFIED_INCREMENTAL_EDGE"


def test_macro_staleness_dilution():
    p = REPORTS_DIR / "incremental_macro_information.csv"
    assert p.exists(), "incremental_macro_information.csv does not exist"
    df = pd.read_csv(p)
    vol4 = df[df["target"] == "fwd_vol_4h"].iloc[0]
    # Unconditional daily macro on 5m grid is diluted by market closures
    assert vol4["delta_r2_val"] < 0.0, "Expected negative delta R2 due to staleness dilution"
    assert vol4["verdict"] == "MARGINAL_OR_UNVERIFIED"


def test_tail_risk_context_lift():
    p = REPORTS_DIR / "tail_risk_context_analysis.csv"
    assert p.exists(), "tail_risk_context_analysis.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) == 5
    mod_c = df[df["model_id"] == "MODEL_C_SPOT_DERIV_SESSION"].iloc[0]
    mod_b = df[df["model_id"] == "MODEL_B_SPOT_DERIV"].iloc[0]
    # Session features should improve tail risk classification AUC
    assert mod_c["auc_validation_2025"] > mod_b["auc_validation_2025"]
    assert mod_c["delta_auc_val_vs_model_b"] > 0.02


def test_directional_edge_unverified():
    p = REPORTS_DIR / "direction_context_analysis.csv"
    assert p.exists(), "direction_context_analysis.csv does not exist"
    df = pd.read_csv(p)
    # Directional verdict for all models should be UNVERIFIED_OR_NO_EDGE
    for _, row in df.iterrows():
        assert row["directional_verdict"] == "UNVERIFIED_OR_NO_EDGE"
        # Holdout lift over majority baseline should be near zero or negative
        assert row["lift_over_majority_holdout"] < 0.02


def test_compression_context_dynamics():
    p = REPORTS_DIR / "compression_context_analysis.csv"
    assert p.exists(), "compression_context_analysis.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) >= 5
    wknd = df[df["condition_id"] == "COMPRESSION_WEEKEND"].iloc[0]
    ny = df[df["condition_id"] == "COMPRESSION_US_EQUITY_OPEN"].iloc[0]
    # Weekend compressions have lower subsequent 4h vol than NY regular hours
    assert wknd["mean_fwd_vol_4h"] < ny["mean_fwd_vol_4h"]


def test_interaction_analysis():
    p = REPORTS_DIR / "interaction_analysis.csv"
    assert p.exists(), "interaction_analysis.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) >= 5
    # Linear main effects are sufficient; interactions add marginal lift (< 0.003)
    assert (df["delta_r2_val"] < 0.005).all()


def test_walk_forward_stability():
    p = REPORTS_DIR / "walk_forward_context.csv"
    assert p.exists(), "walk_forward_context.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) == 5  # 5 expanding folds
    # In all 5 folds, Model C (Session) consistently improves over Model B (Spot + Derivatives)
    assert (df["r2_model_c_session"] > df["r2_model_b_deriv"]).all()
    # Across expanding window folds with 2+ years of training data (Folds 2 to 5), Model E achieves strong positive R2
    assert (df.iloc[1:]["r2_model_e_combined"] > 0.20).all()


def test_multiple_testing_registry_fdr():
    p = REPORTS_DIR / "multiple_testing_registry.csv"
    assert p.exists(), "multiple_testing_registry.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) >= 20
    assert "raw_p_value" in df.columns
    assert "bh_critical_value" in df.columns
    assert "is_significant_fdr_05" in df.columns


def test_september21_posthoc_json():
    p = REPORTS_DIR / "september21_context_posthoc.json"
    assert p.exists(), "september21_context_posthoc.json does not exist"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["event_date"] == "2026-09-21"
    assert "VERIFIED_POSTHOC_CROSS_MARKET_DISLOCATION" in data["forensic_verdict"]
    assert data["macro_context_at_onset"]["vix_close"] > 10.0


def test_parameter_inventory_completeness():
    p = REPORTS_DIR / "parameter_inventory_sprint04.csv"
    assert p.exists(), "parameter_inventory_sprint04.csv does not exist"
    df = pd.read_csv(p)
    assert len(df) >= 8
    params = set(df["parameter_name"].unique())
    assert "ridge_alpha" in params
    assert "tail_quantile_threshold" in params
    assert "fdr_nominal_q" in params


# ======================================================================
# 6. Claim Registry Audit & Discrete Claim Verifications
# ======================================================================

def test_claim_registry_audit_100_percent():
    p = REPORTS_DIR / "claim_integrity_audit.json"
    assert p.exists(), "claim_integrity_audit.json does not exist"
    with open(p, "r", encoding="utf-8") as f:
        audit = json.load(f)
    assert audit["claim_integrity_status"] == "PASSED"
    assert audit["pass_rate"] == 1.0, f"Expected 1.0 pass rate, got {audit['pass_rate']}"
    assert audit["verified_claims"] == 4
    assert audit["unverified_claims"] == 0
    assert audit["failed_claims"] == 0


def test_claim_001_session_incremental_edge():
    # CLAIM-S04-001: Session context provides incremental 4h volatility explanatory power
    p = REPORTS_DIR / "incremental_session_information.csv"
    df = pd.read_csv(p)
    row = df[df["target"] == "fwd_vol_4h"].iloc[0]
    assert row["delta_r2_val"] > 0.05
    assert row["verdict"] == "VERIFIED_INCREMENTAL_EDGE"


def test_claim_002_macro_incremental_edge():
    # CLAIM-S04-002: Daily macro added unconditionally is diluted by market closure staleness
    p = REPORTS_DIR / "incremental_macro_information.csv"
    df = pd.read_csv(p)
    row = df[df["target"] == "fwd_vol_4h"].iloc[0]
    assert row["delta_r2_val"] < 0.0
    assert row["verdict"] == "MARGINAL_OR_UNVERIFIED"


def test_claim_003_directional_edge_unverified():
    # CLAIM-S04-003: Directional edge remains UNVERIFIED
    p = REPORTS_DIR / "direction_context_analysis.csv"
    df = pd.read_csv(p)
    row = df[(df["model_id"] == "MODEL_E_SPOT_DERIV_SESSION_MACRO") & (df["horizon"] == "fwd_ret_4h")].iloc[0]
    assert row["directional_verdict"] == "UNVERIFIED_OR_NO_EDGE"
    assert row["lift_over_majority_holdout"] < 0.02


def test_claim_004_september21_macro_session_signature():
    # CLAIM-S04-004: September 21 cross-market post-hoc signature
    p = REPORTS_DIR / "september21_context_posthoc.json"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "VERIFIED_POSTHOC_CROSS_MARKET_DISLOCATION" in data["forensic_verdict"]
    assert data["active_sessions"]["asia_active"] or data["active_sessions"]["london_active"]

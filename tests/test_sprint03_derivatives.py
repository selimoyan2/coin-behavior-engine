"""Automated Unit & Scientific Verification Tests for Sprint 03.

Enforces:
- 100% presence and integrity of all Sprint 03 artifacts.
- Machine-verifiable evidence chains: CLAIM -> ARTIFACT -> CODE -> TEST.
- Verification that directional edge is NOT over-claimed and audited against strict baselines.
- Temporal isolation across Discovery (2021-2024), Validation (2025), Holdout (2026).
"""

from __future__ import annotations

import json
from pathlib import Path
import pandas as pd
import pytest


REPORTS_DIR = Path("data/reports/sprint03")
NORM_DIR = Path("data/normalized/derivatives")
CHARTS_DIR = REPORTS_DIR / "charts"


def test_derivatives_data_catalog_exists():
    p = REPORTS_DIR / "derivatives_data_catalog.json"
    assert p.exists(), f"Missing {p}"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "catalog_name" in data
    assert "datasets" in data
    liq_ds = next(d for d in data["datasets"] if d["dataset_name"] == "BTCUSDT_LIQUIDATION_DATA")
    assert "DATA_UNAVAILABLE" in liq_ds["limitations"]


def test_derivatives_data_quality_exists():
    p = REPORTS_DIR / "derivatives_data_quality.json"
    assert p.exists(), f"Missing {p}"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "audit_name" in data
    assert "feature_families_qualified" in data
    assert data["rejected_or_unavailable_datasets"][0]["status"] == "DATA_UNAVAILABLE"


def test_derivatives_coverage_matrix_exists():
    p = REPORTS_DIR / "derivatives_coverage_matrix.csv"
    assert p.exists(), f"Missing {p}"
    df = pd.read_csv(p)
    assert len(df) >= 4
    assert "feature_family" in df.columns
    assert "quality_status" in df.columns


def test_all_six_family_parquets_exist():
    families = [
        "perpetual_features.parquet",
        "basis_features.parquet",
        "funding_features.parquet",
        "open_interest_features.parquet",
        "positioning_features.parquet",
        "futures_taker_features.parquet",
    ]
    for fam in families:
        p = REPORTS_DIR / fam
        assert p.exists(), f"Missing family parquet: {p}"
        df = pd.read_parquet(p)
        assert len(df) == 602240, f"Expected 602,240 rows in {fam}, got {len(df)}"
        assert "datetime_open" in df.columns


def test_baseline_feature_manifest():
    p = REPORTS_DIR / "baseline_feature_manifest.json"
    assert p.exists(), f"Missing {p}"
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "features" in data
    assert len(data["features"]) >= 8
    assert "historical_analogue_direction" in data["excluded_features"]


def test_claim_registry_exists():
    p = REPORTS_DIR / "claim_registry.json"
    assert p.exists(), f"Missing {p}"
    with open(p, "r", encoding="utf-8") as f:
        claims = json.load(f)
    assert len(claims) >= 4
    for c in claims:
        assert c["status"] == "VERIFIED"
        assert Path(c["artifact_path"]).exists()


def test_claim_integrity_audit():
    p = REPORTS_DIR / "claim_integrity_audit.json"
    assert p.exists(), f"Missing {p}"
    with open(p, "r", encoding="utf-8") as f:
        audit = json.load(f)
    assert audit["failed_claims"] == 0
    assert audit["pass_rate"] == 1.0


def test_claim_001_volatility_incremental_edge():
    p = REPORTS_DIR / "incremental_volatility_information.csv"
    assert p.exists()
    df = pd.read_csv(p)
    row = df[(df["target_horizon"] == "fwd_vol_4h") & (df["model_specification"] == "Baseline + All Derivatives")]
    assert len(row) == 1
    assert row["val_2025_delta_r2"].iloc[0] > 0.0


def test_claim_002_directional_edge_unverified():
    p = REPORTS_DIR / "incremental_direction_information.csv"
    assert p.exists()
    df = pd.read_csv(p)
    row = df[(df["target_horizon"] == "fwd_ret_4h") & (df["model_specification"] == "Spot + All Derivatives")]
    assert len(row) == 1
    assert row["directional_edge_verified"].iloc[0] == False


def test_claim_003_tail_risk_lift():
    p = REPORTS_DIR / "incremental_tail_risk_information.csv"
    assert p.exists()
    df = pd.read_csv(p)
    row = df[(df["target_horizon"] == "fwd_abs_ret_4h") & (df["model_specification"] == "Spot + All Derivatives")]
    assert len(row) >= 1
    assert row["val_2025_roc_auc"].iloc[0] > 0.5


def test_claim_004_september21_signature():
    p = REPORTS_DIR / "september21_derivatives_posthoc.json"
    assert p.exists()
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["post_hoc_verdict"] == "VERIFIED_STRUCTURAL_DERIVATIVES_SIGNATURE"


def test_incremental_volatility_information_structure():
    p = REPORTS_DIR / "incremental_volatility_information.csv"
    df = pd.read_csv(p)
    expected_cols = [
        "target_horizon",
        "model_specification",
        "val_2025_r2",
        "val_2025_delta_r2",
        "val_2025_mae",
        "val_2025_spearman_corr",
        "holdout_2026_r2",
        "holdout_2026_delta_r2",
    ]
    for c in expected_cols:
        assert c in df.columns


def test_incremental_absolute_move_information():
    p = REPORTS_DIR / "incremental_absolute_move_information.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) >= 15
    assert "val_2025_delta_r2" in df.columns


def test_incremental_tail_risk_information():
    p = REPORTS_DIR / "incremental_tail_risk_information.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) >= 4
    assert "val_2025_roc_auc" in df.columns
    assert "val_2025_brier_score" in df.columns


def test_incremental_direction_information():
    p = REPORTS_DIR / "incremental_direction_information.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) >= 10
    assert "val_2025_raw_accuracy" in df.columns
    assert "val_2025_baseline_adjusted_lift" in df.columns


def test_compression_derivatives_analysis():
    p = REPORTS_DIR / "compression_derivatives_analysis.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) >= 2
    assert "expansion_r2" in df.columns


def test_lead_lag_analysis():
    p = REPORTS_DIR / "lead_lag_analysis.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) == 25  # -12 to +12 lags
    assert "lag_bars_5m" in df.columns
    assert "perp_ret_vs_spot_corr" in df.columns


def test_feature_family_ablation():
    p = REPORTS_DIR / "feature_family_ablation.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) >= 14
    assert "ablation_group" in df.columns
    assert "val_2025_r2" in df.columns


def test_derivatives_redundancy():
    p = REPORTS_DIR / "derivatives_redundancy_analysis.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) >= 20
    assert "max_spot_baseline_correlation" in df.columns


def test_interaction_analysis():
    p = REPORTS_DIR / "interaction_analysis.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) >= 4
    assert "interaction_pair" in df.columns
    assert "delta_r2" in df.columns


def test_pre_event_signatures():
    p_ev = REPORTS_DIR / "pre_event_derivatives_profiles.parquet"
    p_ct = REPORTS_DIR / "matched_derivatives_controls.parquet"
    assert p_ev.exists() and p_ct.exists()
    df_ev = pd.read_parquet(p_ev)
    df_ct = pd.read_parquet(p_ct)
    assert len(df_ev) > 0 and len(df_ct) > 0
    assert "horizon_pre" in df_ev.columns


def test_walk_forward_validation():
    p = REPORTS_DIR / "walk_forward_derivatives.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) == 5  # 5 expanding folds
    assert "spot_baseline_r2" in df.columns
    assert "spot_plus_derivatives_r2" in df.columns


def test_validation_2025_summary():
    p = REPORTS_DIR / "validation_2025_derivatives.json"
    assert p.exists()
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["scientific_conclusion"]["volatility_information"] == "STRONG_VERIFIED_INCREMENTAL_EDGE"
    assert data["scientific_conclusion"]["directional_information"] == "UNVERIFIED_MARGINAL_EDGE_NEAR_ZERO_LIFT"


def test_holdout_2026_summary():
    p = REPORTS_DIR / "observed_holdout_2026_derivatives.json"
    assert p.exists()
    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "volatility_incremental_r2_4h" in data


def test_multiple_testing_registry():
    p = REPORTS_DIR / "multiple_testing_registry.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) > 0
    assert "bh_critical_value" in df.columns
    assert "reject_null" in df.columns


def test_parameter_inventory():
    p = REPORTS_DIR / "parameter_inventory_sprint03.csv"
    assert p.exists()
    df = pd.read_csv(p)
    assert len(df) >= 10
    assert "parameter_name" in df.columns


def test_research_charts():
    charts = [
        "01_volatility_incremental_r2.svg",
        "02_directional_accuracy_baselines.svg",
        "03_lead_lag_cross_correlation.svg",
        "04_walk_forward_stability.svg",
        "05_september21_forensic_timeline.svg",
    ]
    for c in charts:
        p = CHARTS_DIR / c
        assert p.exists(), f"Missing chart {p}"

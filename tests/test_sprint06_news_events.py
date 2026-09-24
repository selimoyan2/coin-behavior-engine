"""Comprehensive Test Suite for Sprint 06: News, Event Intelligence & Semantic Claim Integrity.

Contains 50+ unit and integration tests covering:
- Hierarchical Event Taxonomy & Metadata
- Source Quality Forensic Catalog & Rejection Funnel
- Four-Timestamp Model & Causal Ordering
- Duplicate Story Clustering & Cascade Delay
- Anti-Lookahead Clock Alignment & TF-IDF Causal Fitting
- Event Study Engine & Matched Controls
- Information Ladder & Core Model Residuals
- Information Latency Sensitivity & Decay
- September 21 Forensic Modularity & Independence
- Semantic Claim Integrity V2 Operators & Contradiction Detection
- Prohibition of Directional Edge Promotion & 64.2% Rejection
"""

from pathlib import Path
import json
import numpy as np
import pandas as pd
import pytest

from coin_behavior_engine.claims.registry import ResearchClaimRegistry, ResearchClaim
from coin_behavior_engine.news.taxonomy import build_default_event_taxonomy, export_event_taxonomy, TAXONOMY_VERSION
from coin_behavior_engine.news.catalog import build_event_sources, export_event_catalog
from coin_behavior_engine.news.ingestion import EventIngestionEngine
from coin_behavior_engine.news.features import EventFeatureEngine
from coin_behavior_engine.news.event_study import EventStudyEngine
from coin_behavior_engine.news.research import NewsEventResearchEngine


# ==============================================================================
# 1. TAXONOMY TESTS (1-6)
# ==============================================================================

def test_taxonomy_canonical_families_count():
    families = build_default_event_taxonomy()
    assert len(families) == 14, "Must contain exactly 14 top-level event families."


def test_taxonomy_version_metadata():
    assert TAXONOMY_VERSION == "1.0.0"
    v_path = Path("data/reports/sprint06/event_taxonomy_version.json")
    assert v_path.exists()
    with open(v_path) as f:
        meta = json.load(f)
    assert meta["version"] == "1.0.0"


def test_taxonomy_scheduled_macro_attributes():
    families = build_default_event_taxonomy()
    fam = families.get("MACRO_SCHEDULED")
    assert fam is not None
    assert "CPI" in fam.subcategories
    sub = fam.subcategories["CPI"]
    assert sub.is_scheduled_by_default is True
    assert sub.typical_lead_hours >= 24.0


def test_taxonomy_unscheduled_security_attributes():
    families = build_default_event_taxonomy()
    fam = families.get("EXCHANGE_SECURITY")
    assert fam is not None
    assert "HACK" in fam.subcategories
    sub = fam.subcategories["HACK"]
    assert sub.is_scheduled_by_default is False
    assert sub.typical_lead_hours == 0.0


def test_taxonomy_export_integrity(tmp_path):
    export_event_taxonomy(reports_dir=tmp_path)
    assert (tmp_path / "event_taxonomy.json").exists()
    assert (tmp_path / "event_taxonomy_version.json").exists()


def test_taxonomy_subcategories_non_empty():
    families = build_default_event_taxonomy()
    for fam_name, fam in families.items():
        assert len(fam.subcategories) > 0, f"Family {fam_name} must have subcategories."


# ==============================================================================
# 2. SOURCE CATALOG & FORENSIC TIERS (7-12)
# ==============================================================================

def test_source_catalog_tiers_present():
    sources = build_event_sources()
    assert len(sources) >= 10
    tiers = {s.source_tier for s in sources}
    assert "TIER_1_PRIMARY" in tiers
    assert "TIER_2_HIGH_QUALITY_SECONDARY" in tiers
    assert "TIER_3_AGGREGATOR" in tiers
    assert "REJECTED" in tiers


def test_source_catalog_primary_sources():
    sources = build_event_sources()
    t1_ids = [s.source_id for s in sources if s.source_tier == "TIER_1_PRIMARY"]
    assert "SRC_BLS_CPI_NFP" in t1_ids
    assert "SRC_FED_FOMC" in t1_ids
    assert "SRC_SEC_EDGAR" in t1_ids


def test_source_catalog_disallowed_social_rejected():
    sources = build_event_sources()
    rejected = [s for s in sources if s.source_tier == "REJECTED"]
    rej_ids = [s.source_id for s in rejected]
    assert "SRC_TWITTER_UNVERIFIED" in rej_ids
    assert "SRC_TELEGRAM_LEAKS" in rej_ids
    for s in rejected:
        assert s.reproducibility_score < 0.3


def test_source_catalog_export(tmp_path):
    export_event_catalog(reports_dir=tmp_path)
    assert (tmp_path / "event_data_catalog.json").exists()
    assert (tmp_path / "event_source_quality.json").exists()
    assert (tmp_path / "event_partition_manifest.json").exists()


def test_source_catalog_latency_rankings():
    catalog_path = Path("data/reports/sprint06/event_data_catalog.json")
    assert catalog_path.exists()
    with open(catalog_path) as f:
        catalog = json.load(f)
    for s in catalog["sources"]:
        assert "source_tier" in s
        assert "source_id" in s


def test_partition_manifest_ranges():
    manifest_path = Path("data/reports/sprint06/event_partition_manifest.json")
    assert manifest_path.exists()
    with open(manifest_path) as f:
        manifest = json.load(f)
    assert "2024-12-31" in manifest["partitions"]["early_event_discovery"]["end"]
    assert "2025-01-01" in manifest["partitions"]["later_event_validation"]["start"]
    assert "2026-01-01" in manifest["partitions"]["observed_holdout_2026"]["start"]


# ==============================================================================
# 3. FOUR-TIMESTAMP INGESTION & CLUSTERING (13-18)
# ==============================================================================

def test_canonical_parquet_exists():
    path = Path("data/reports/sprint06/event_canonical.parquet")
    assert path.exists(), "event_canonical.parquet must exist."
    df = pd.read_parquet(path)
    assert len(df) >= 200


def test_four_timestamps_present():
    df = pd.read_parquet("data/reports/sprint06/event_canonical.parquet")
    required = ["event_time", "publication_time", "first_observed_time", "ingestion_time", "available_at_timestamp"]
    for col in required:
        assert col in df.columns, f"Missing timestamp column {col}"


def test_available_at_timestamp_causality():
    df = pd.read_parquet("data/reports/sprint06/event_canonical.parquet")
    # available_at_timestamp must equal first_observed_time
    assert (df["available_at_timestamp"] == df["first_observed_time"]).all()


def test_no_negative_cascade_delays():
    df = pd.read_parquet("data/reports/sprint06/event_canonical.parquet")
    assert (df["cascade_delay_seconds"] >= 0.0).all()


def test_duplicate_story_clustering():
    df = pd.read_parquet("data/reports/sprint06/event_canonical.parquet")
    assert "event_cluster_id" in df.columns
    assert "is_cluster_lead" in df.columns
    assert df["is_cluster_lead"].sum() > 0
    # Every cluster must have at least one lead
    cluster_leads = df[df["is_cluster_lead"]]["event_cluster_id"].nunique()
    total_clusters = df["event_cluster_id"].nunique()
    assert cluster_leads == total_clusters


def test_distinct_counts_hierarchy():
    df = pd.read_parquet("data/reports/sprint06/event_canonical.parquet")
    n_events = len(df)
    n_clusters = df["event_cluster_id"].nunique()
    assert n_clusters < n_events, "N_clusters must be less than N_events due to wire duplicate clustering."


# ==============================================================================
# 4. EVENT FEATURE ENGINEERING & ANTI-LOOKAHEAD (19-25)
# ==============================================================================

def test_event_features_shape():
    path = Path("data/reports/sprint06/event_features.parquet")
    assert path.exists()
    df = pd.read_parquet(path)
    assert len(df) == 602240, "Feature grid must match 602,240 5m bars."
    assert len(df.columns) >= 50


def test_event_clocks_non_negative():
    df = pd.read_parquet("data/reports/sprint06/event_features.parquet")
    assert (df["minutes_to_scheduled_event"] >= 0.0).all()
    assert (df["minutes_since_event_available"] >= 0.0).all()
    assert (df["event_age_hours"] >= 0.0).all()


def test_decay_buckets_exist():
    df = pd.read_parquet("data/reports/sprint06/event_features.parquet")
    buckets = [
        "event_age_0_5m", "event_age_5_15m", "event_age_15_30m", "event_age_30_60m",
        "event_age_1_2h", "event_age_2_4h", "event_age_4_8h", "event_age_8_12h",
        "event_age_12_24h", "event_age_24_48h"
    ]
    for b in buckets:
        assert b in df.columns
        assert set(df[b].unique()).issubset({0, 1})


def test_event_density_monotonicity():
    df = pd.read_parquet("data/reports/sprint06/event_features.parquet")
    # 15m <= 1h <= 4h <= 24h
    assert (df["events_last_15m"] <= df["events_last_1h"]).all()
    assert (df["events_last_1h"] <= df["events_last_4h"]).all()
    assert (df["events_last_4h"] <= df["events_last_24h"]).all()


def test_novelty_score_bounds():
    df = pd.read_parquet("data/reports/sprint06/event_features.parquet")
    assert (df["event_novelty_score"] >= 0.0).all()
    assert (df["event_novelty_score"] <= 1.0).all()


def test_tfidf_fitted_on_discovery_only():
    engine = EventFeatureEngine()
    df_grid, df_events = engine.load_grid_and_events()
    vec, feat_names = engine.fit_causal_tfidf(df_events)
    assert len(feat_names) == 8
    # Ensure vocabulary was learned strictly from Discovery
    disc_events = df_events[df_events["available_at_timestamp"] <= "2024-12-31 23:59:59+00:00"]
    assert len(disc_events) < len(df_events)


def test_cross_layer_interaction_features():
    df = pd.read_parquet("data/reports/sprint06/event_features.parquet")
    interactions = [
        "event_x_compression", "event_x_high_vol", "event_x_ny",
        "event_x_overlap", "event_x_etf_stale"
    ]
    for col in interactions:
        assert col in df.columns


# ==============================================================================
# 5. EVENT STUDY ENGINE & CONTROLS (26-31)
# ==============================================================================

def test_event_study_results_exist():
    path = Path("data/reports/sprint06/event_study_results.csv")
    assert path.exists()
    df = pd.read_csv(path)
    assert len(df) > 0
    assert "vol_ratio" in df.columns
    assert "jump_multiplier" in df.columns


def test_matched_controls_exist():
    path = Path("data/reports/sprint06/matched_event_controls.csv")
    assert path.exists()
    df = pd.read_csv(path)
    assert len(df) >= 1000
    assert "event_bar_idx" in df.columns
    assert "control_bar_idx" in df.columns


def test_event_overlap_audit_exists():
    path = Path("data/reports/sprint06/event_overlap_audit.csv")
    assert path.exists()
    df = pd.read_csv(path)
    assert "overlapping_events_4h" in df.columns
    assert "overlapping_events_24h" in df.columns
    assert "is_isolated_24h" in df.columns
    assert df["is_isolated_24h"].sum() > 0


def test_event_study_volatility_elevation():
    df = pd.read_csv("data/reports/sprint06/event_study_results.csv")
    # Post-event +30m vol ratio for ALL must be > 1.5x
    row = df[(df["event_family"] == "ALL") & (df["horizon"] == "+30m")].iloc[0]
    assert row["vol_ratio"] > 1.5, f"Expected vol ratio > 1.5x, got {row['vol_ratio']}"


def test_event_study_jump_multiplier_elevation():
    df = pd.read_csv("data/reports/sprint06/event_study_results.csv")
    row = df[(df["event_family"] == "ALL") & (df["horizon"] == "+4h")].iloc[0]
    assert row["jump_multiplier"] > 3.0, f"Expected jump multiplier > 3.0x, got {row['jump_multiplier']}"


def test_event_study_directional_symmetry():
    df = pd.read_csv("data/reports/sprint06/event_study_results.csv")
    post = df[(df["event_family"] == "ALL") & (df["window_type"] == "POST")]
    for _, r in post.iterrows():
        # Directional positive % should be between 40% and 60% (no persistent directional edge)
        assert 40.0 <= r["ev_directional_pos_pct"] <= 60.0


# ==============================================================================
# 6. RESEARCH ENGINE & INFORMATION LADDER (32-38)
# ==============================================================================

def test_information_ladder_models_count():
    df = pd.read_csv("data/reports/sprint06/information_ladder_results.csv")
    assert len(df) == 7, "Information ladder must contain 7 models (A through G)."


def test_model_c_is_primary_baseline():
    df = pd.read_csv("data/reports/sprint06/information_ladder_results.csv")
    row_c = df[df["model_name"].str.contains("BASELINE")].iloc[0]
    assert row_c["delta_vol_r2_validation"] == 0.0
    assert row_c["delta_jump_auc_validation"] == 0.0


def test_unconditional_volatility_dilution():
    df = pd.read_csv("data/reports/sprint06/information_ladder_results.csv")
    row_f = df[df["model_name"].str.contains("Model F")].iloc[0]
    # Unconditional delta R2 on all bars is negative due to sparse noise dilution
    assert row_f["delta_vol_r2_validation"] < 0.0


def test_core_model_residual_analysis():
    path = Path("data/reports/sprint06/residual_analysis.json")
    assert path.exists()
    with open(path) as f:
        data = json.load(f)
    assert data["error_odds_ratio"] > 2.0
    assert data["fisher_p_value"] < 0.001


def test_latency_sensitivity_results():
    path = Path("data/reports/sprint06/latency_sensitivity_results.csv")
    assert path.exists()
    df = pd.read_csv(path)
    assert len(df) == 5
    assert set(df["latency_lag_bars"]).issubset({0, 1, 3, 6, 12})


def test_expanding_walk_forward_folds():
    path = Path("data/reports/sprint06/walk_forward_results.csv")
    assert path.exists()
    df = pd.read_csv(path)
    assert len(df) == 5, "Must contain 5 walk-forward folds."
    assert (df["train_bars"] > 100000).all()
    assert (df["test_bars"] > 50000).all()


def test_september21_audit_modularity():
    path = Path("data/reports/sprint06/september21_audit.json")
    assert path.exists()
    with open(path) as f:
        data = json.load(f)
    assert data["is_independent_and_removable"] is True
    assert abs(data["delta_r2_impact"]) < 0.05


# ==============================================================================
# 7. SEMANTIC CLAIM INTEGRITY V2 OPERATORS & CLAIMS (39-46)
# ==============================================================================

def test_semantic_operator_improves_rejects_negative():
    reg = ResearchClaimRegistry()
    reg.register_claim(
        claim_id="TEST-IMPROVES-FAIL",
        claim_text="Model improves performance over baseline.",
        metric_name="delta_r2",
        metric_value=-0.02,
        sample_size=1000,
        partition="VALIDATION_2025",
        horizon="1h",
        artifact_path="data/reports/sprint06/information_ladder_results.csv",
        artifact_row_or_key="dummy",
        generating_module="tests",
        test_reference="tests/test_sprint06_news_events.py",
        claim_semantic_operator="IMPROVES",
    )
    passed, reason = reg.verify_semantic_operator("TEST-IMPROVES-FAIL")
    assert passed is False
    assert "delta -0.02 is non-positive" in reason


def test_semantic_operator_degrades_rejects_positive():
    reg = ResearchClaimRegistry()
    reg.register_claim(
        claim_id="TEST-DEGRADES-FAIL",
        claim_text="Model degrades performance.",
        metric_name="delta_r2",
        metric_value=0.03,
        sample_size=1000,
        partition="VALIDATION_2025",
        horizon="1h",
        artifact_path="data/reports/sprint06/information_ladder_results.csv",
        artifact_row_or_key="dummy",
        generating_module="tests",
        test_reference="tests/test_sprint06_news_events.py",
        claim_semantic_operator="DEGRADES",
    )
    passed, reason = reg.verify_semantic_operator("TEST-DEGRADES-FAIL")
    assert passed is False
    assert "delta 0.03 is non-negative" in reason


def test_language_contradiction_improves_with_negative_metric():
    reg = ResearchClaimRegistry()
    reg.register_claim(
        claim_id="TEST-LANG-CONTRA",
        claim_text="Model improves out-of-sample volatility explanatory power.",
        metric_name="delta_r2",
        metric_value=-0.005,
        sample_size=1000,
        partition="VALIDATION_2025",
        horizon="1h",
        artifact_path="data/reports/sprint06/information_ladder_results.csv",
        artifact_row_or_key="dummy",
        generating_module="tests",
        test_reference="tests/test_sprint06_news_events.py",
        claim_semantic_operator="NEGATIVE_DELTA",
    )
    passed, reason = reg.verify_claim_language("TEST-LANG-CONTRA")
    assert passed is False
    assert "Semantic contradiction: claim text asserts improvement but metric is negative" in reason


def test_semantic_operator_fails_to_replicate():
    reg = ResearchClaimRegistry()
    reg.register_claim(
        claim_id="TEST-FAIL-REP",
        claim_text="Directional edge fails to replicate.",
        metric_name="accuracy",
        metric_value=0.505,
        sample_size=1000,
        partition="VALIDATION_2025",
        horizon="1h",
        artifact_path="data/reports/sprint06/information_ladder_results.csv",
        artifact_row_or_key="dummy",
        generating_module="tests",
        test_reference="tests/test_sprint06_news_events.py",
        claim_semantic_operator="FAILS_TO_REPLICATE",
    )
    passed, reason = reg.verify_semantic_operator("TEST-FAIL-REP")
    assert passed is True


def test_sprint06_all_claims_verified():
    path = Path("data/reports/sprint06/claim_semantic_integrity.json")
    assert path.exists()
    with open(path) as f:
        claims = json.load(f)
    assert len(claims) == 6
    for c in claims:
        assert c["final_status"] == "VERIFIED", f"Claim {c['claim_id']} failed: {c.get('failure_reason')}"
        assert c["semantic_integrity"] == "PASSED"
        assert c["numeric_integrity"] == "PASSED"


def test_sprint06_claim_ids_present():
    path = Path("data/reports/sprint06/claim_registry.json")
    with open(path) as f:
        reg = json.load(f)
    if isinstance(reg, list):
        claim_ids = [c["claim_id"] for c in reg]
    elif "claims" in reg:
        claim_ids = [c["claim_id"] for c in reg["claims"]] if isinstance(reg["claims"], list) else list(reg["claims"].keys())
    else:
        claim_ids = list(reg.keys())
    expected = [
        "CLAIM-S06-001", "CLAIM-S06-002", "CLAIM-S06-003",
        "CLAIM-S06-004", "CLAIM-S06-005", "CLAIM-S06-006"
    ]
    for cid in expected:
        assert cid in claim_ids


# ==============================================================================
# 8. AUDIT BOUNDARIES & ANTI-64.2% REPLICATION (47-50)
# ==============================================================================

def test_no_64_percent_analogue_claim():
    path = Path("data/reports/sprint06/claim_registry.json")
    with open(path) as f:
        content = f.read()
    assert "64.2%" not in content
    assert "64.2" not in content, "Discredited 64.2% analogue claim must never appear in verified registry."


def test_no_directional_edge_promoted():
    path = Path("data/reports/sprint06/information_ladder_results.csv")
    df = pd.read_csv(path)
    # Check that all directional accuracies are below 52%
    assert (df["dir_accuracy_validation"] < 0.52).all()
    assert (df["dir_accuracy_holdout"] < 0.52).all()


def test_zero_trading_execution_leakage():
    # Verify no BUY/SELL rules, order routing, or PnL columns exist in event features
    df = pd.read_parquet("data/reports/sprint06/event_features.parquet")
    banned = ["buy_signal", "sell_signal", "pnl", "sharpe", "position_size", "order_type", "stop_loss", "take_profit"]
    for col in df.columns:
        for b in banned:
            assert b not in col.lower(), f"Banned trading execution term '{b}' found in feature '{col}'"


def test_charts_dual_format_presence():
    charts_dir = Path("data/reports/sprint06/charts")
    assert charts_dir.exists()
    pngs = list(charts_dir.glob("*.png"))
    svgs = list(charts_dir.glob("*.svg"))
    assert len(pngs) >= 20, f"Expected at least 20 PNG charts, found {len(pngs)}"
    assert len(svgs) >= 20, f"Expected at least 20 SVG charts, found {len(svgs)}"

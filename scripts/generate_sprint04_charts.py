"""Chart Generation Engine for Sprint 04 Research Visualizations.

Generates 5 publication-quality vector SVG and high-resolution PNG charts:
1. 01_information_ladder_comparison (Models A through E across partitions)
2. 02_session_diurnal_profiles (24h UTC volatility & volume across regional sessions)
3. 03_macro_dynamic_correlation_timeline (30d rolling BTC-Macro correlations 2021-2026)
4. 04_walk_forward_stability_ladder (5-fold walk-forward out-of-sample R2)
5. 05_september21_cross_market_forensic (September 20-21 cross-market crash timeline)
"""

from __future__ import annotations

import json
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from coin_behavior_engine.utils.logging import logger

plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
plt.rcParams["font.sans-serif"] = "DejaVu Sans"
plt.rcParams["axes.edgecolor"] = "#cccccc"
plt.rcParams["axes.linewidth"] = 0.8


def generate_charts(reports_dir: str | Path = "data/reports/sprint04") -> None:
    reports_path = Path(reports_dir)
    charts_dir = reports_path / "charts"
    charts_dir.mkdir(parents=True, exist_ok=True)

    # ----------------------------------------------------
    # Chart 1: Information Ladder Comparison
    # ----------------------------------------------------
    logger.info("Generating Chart 1: Information Ladder Comparison...")
    ladder_file = reports_path / "information_ladder.csv"
    if ladder_file.exists():
        df_ladder = pd.read_csv(ladder_file)
        df_vol4 = df_ladder[df_ladder["target"] == "fwd_vol_4h"].copy()

        models = ["MODEL_A_SPOT_ONLY", "MODEL_B_SPOT_DERIV", "MODEL_C_SPOT_DERIV_SESSION", "MODEL_D_SPOT_DERIV_MACRO", "MODEL_E_SPOT_DERIV_SESSION_MACRO"]
        labels = ["Model A\n(Spot Only)", "Model B\n(Spot+Deriv)", "Model C\n(+Session)", "Model D\n(+Macro)", "Model E\n(Combined)"]
        colors = ["#7f8c8d", "#2980b9", "#27ae60", "#e67e22", "#8e44ad"]

        r2_disc = [df_vol4[df_vol4["model_id"] == m]["r2_discovery_2021_2024"].iloc[0] for m in models]
        r2_val = [df_vol4[df_vol4["model_id"] == m]["r2_validation_2025"].iloc[0] for m in models]
        r2_hold = [df_vol4[df_vol4["model_id"] == m]["r2_holdout_2026"].iloc[0] for m in models]

        x = np.arange(len(models))
        width = 0.25

        fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
        bars1 = ax.bar(x - width, r2_disc, width, label="Discovery (2021-2024)", color="#95a5a6", alpha=0.9)
        bars2 = ax.bar(x, r2_val, width, label="Validation (2025)", color="#3498db", alpha=0.95)
        bars3 = ax.bar(x + width, r2_hold, width, label="Holdout (2026)", color="#e74c3c", alpha=0.95)

        ax.set_ylabel("Out-of-Sample $R^2$ (Forward 4h Volatility)", fontsize=11, fontweight="bold")
        ax.set_title("Sprint 04 Information Ladder: Incremental Explanatory Power by Context Layer", fontsize=13, fontweight="bold", pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels(labels, fontsize=10, fontweight="semibold")
        ax.legend(frameon=True, facecolor="white", loc="upper left")
        ax.set_ylim(0.0, 0.50)

        for bar in bars2:
            h = bar.get_height()
            ax.annotate(f"{h:.3f}", xy=(bar.get_x() + bar.get_width() / 2, h),
                        xytext=(0, 3), textcoords="offset points", ha="center", va="bottom", fontsize=8, fontweight="bold")

        plt.tight_layout()
        fig.savefig(charts_dir / "01_information_ladder_comparison.png", dpi=300)
        fig.savefig(charts_dir / "01_information_ladder_comparison.svg")
        plt.close(fig)

    # ----------------------------------------------------
    # Chart 2: Session Diurnal Profiles (24h UTC)
    # ----------------------------------------------------
    logger.info("Generating Chart 2: Session Diurnal Profiles...")
    base_rates_file = reports_path / "session_base_rates.csv"
    if base_rates_file.exists():
        df_base = pd.read_csv(base_rates_file)
        df_hourly = df_base[df_base["category_type"] == "HOUR_UTC"].copy()
        df_hourly["hour"] = df_hourly["category_name"].str.replace("Hour_", "").astype(int)
        df_hourly = df_hourly.sort_values("hour").reset_index(drop=True)

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 7), dpi=300, sharex=True)

        # Volatility & Range
        ax1.plot(df_hourly["hour"], df_hourly["mean_volatility_4h"] * 1000, color="#e74c3c", marker="o", linewidth=2.2, label="Mean 4h Realized Vol (x1000)")
        ax1.plot(df_hourly["hour"], df_hourly["mean_range_4h"] * 100, color="#f39c12", marker="s", linewidth=1.8, linestyle="--", label="Mean 4h High-Low Range (%)")
        ax1.set_ylabel("Volatility & Range Metric", fontsize=10, fontweight="bold")
        ax1.set_title("Bitcoin 24-Hour Diurnal Activity & Session Alignment (UTC)", fontsize=13, fontweight="bold", pad=12)
        ax1.legend(loc="upper left")

        # Session shaded spans
        # Asia: 00:00 to 09:00 UTC
        ax1.axvspan(0, 9, color="#f1c40f", alpha=0.15, label="Asia Session")
        # London: 08:00 to 16:30 UTC
        ax1.axvspan(8, 16.5, color="#3498db", alpha=0.15, label="London Session")
        # New York: 13:30 to 20:00 UTC
        ax1.axvspan(13.5, 20, color="#2ecc71", alpha=0.15, label="New York Regular")

        # Overlap highlights
        ax1.axvspan(13.5, 16.5, color="#9b59b6", alpha=0.25)
        ax1.text(15.0, ax1.get_ylim()[1] * 0.90, "London/NY Overlap", ha="center", fontsize=8, fontweight="bold", color="#8e44ad")

        # Tail Risk Frequency (%)
        ax2.bar(df_hourly["hour"], df_hourly["tail_frequency_95th"] * 100.0, color="#34495e", alpha=0.8, width=0.6, label="95th Tail Excursion Frequency (%)")
        ax2.set_ylabel("Tail Excursion Rate (%)", fontsize=10, fontweight="bold")
        ax2.set_xlabel("Hour of Day (UTC)", fontsize=11, fontweight="bold")
        ax2.set_xticks(range(0, 24))
        ax2.legend(loc="upper left")

        plt.tight_layout()
        fig.savefig(charts_dir / "02_session_diurnal_profiles.png", dpi=300)
        fig.savefig(charts_dir / "02_session_diurnal_profiles.svg")
        plt.close(fig)

    # ----------------------------------------------------
    # Chart 3: Dynamic Macro Correlation Timeline
    # ----------------------------------------------------
    logger.info("Generating Chart 3: Dynamic Macro Correlation Timeline...")
    cross_feat_file = reports_path / "cross_asset_features.parquet"
    if cross_feat_file.exists():
        df_cross = pd.read_parquet(cross_feat_file, columns=["datetime_open", "corr_btc_nasdaq_30d", "corr_btc_sp500_30d", "corr_btc_dxy_30d", "corr_btc_gold_30d"])
        # Downsample to daily for fast, clean plotting
        df_daily = df_cross.set_index("datetime_open").resample("1D").last().dropna().reset_index()

        fig, ax = plt.subplots(figsize=(12, 6), dpi=300)
        ax.plot(df_daily["datetime_open"], df_daily["corr_btc_nasdaq_30d"], label="BTC vs NASDAQ 30d Corr", color="#2980b9", linewidth=1.8)
        ax.plot(df_daily["datetime_open"], df_daily["corr_btc_sp500_30d"], label="BTC vs S&P 500 30d Corr", color="#27ae60", linewidth=1.5, alpha=0.7)
        ax.plot(df_daily["datetime_open"], df_daily["corr_btc_dxy_30d"], label="BTC vs DXY (Dollar) 30d Corr", color="#e74c3c", linewidth=1.5, linestyle="--")
        ax.plot(df_daily["datetime_open"], df_daily["corr_btc_gold_30d"], label="BTC vs Gold 30d Corr", color="#f39c12", linewidth=1.5)

        ax.axhline(0, color="black", linestyle="-", linewidth=0.8, alpha=0.7)
        ax.set_ylabel("30-Day Rolling Pearson Correlation", fontsize=11, fontweight="bold")
        ax.set_title("Dynamic Macro-BTC Correlations: Regime Transitions (2021 – 2026)", fontsize=13, fontweight="bold", pad=15)
        ax.legend(frameon=True, facecolor="white", loc="lower left")
        ax.set_ylim(-0.8, 0.9)

        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))

        # Annotations for major macro regimes
        ax.text(pd.to_datetime("2021-06-01"), 0.75, "2021 Bull Peak", fontsize=9, fontweight="bold", color="#2980b9")
        ax.text(pd.to_datetime("2022-06-01"), 0.75, "2022 Fed Tightening (High Tech Corr)", fontsize=9, fontweight="bold", color="#2980b9")
        ax.text(pd.to_datetime("2024-03-01"), 0.65, "2024 Spot ETF Expansion", fontsize=9, fontweight="bold", color="#27ae60")

        plt.tight_layout()
        fig.savefig(charts_dir / "03_macro_dynamic_correlation_timeline.png", dpi=300)
        fig.savefig(charts_dir / "03_macro_dynamic_correlation_timeline.svg")
        plt.close(fig)

    # ----------------------------------------------------
    # Chart 4: Walk-Forward Temporal Stability
    # ----------------------------------------------------
    logger.info("Generating Chart 4: Walk-Forward Temporal Stability...")
    wf_file = reports_path / "walk_forward_context.csv"
    if wf_file.exists():
        df_wf = pd.read_csv(wf_file)
        folds = df_wf["fold_id"].tolist()
        fold_labels = ["Fold 1\n(2022)", "Fold 2\n(2023)", "Fold 3\n(2024)", "Fold 4\n(2025 Val)", "Fold 5\n(2026 Hold)"]

        x = np.arange(len(folds))
        width = 0.22

        fig, ax = plt.subplots(figsize=(10, 6), dpi=300)
        ax.bar(x - width, df_wf["r2_model_a_spot"], width, label="Model A (Spot Baseline)", color="#7f8c8d", alpha=0.9)
        ax.bar(x, df_wf["r2_model_b_deriv"], width, label="Model B (Spot + Derivatives)", color="#3498db", alpha=0.95)
        ax.bar(x + width, df_wf["r2_model_e_combined"], width, label="Model E (Spot + Deriv + Session + Macro)", color="#8e44ad", alpha=0.95)

        ax.set_ylabel("Out-of-Sample $R^2$ (Forward 4h Volatility)", fontsize=11, fontweight="bold")
        ax.set_title("Walk-Forward Temporal Stability: Expanding Window Model Performance Across Regimes", fontsize=12, fontweight="bold", pad=15)
        ax.set_xticks(x)
        ax.set_xticklabels(fold_labels, fontsize=10, fontweight="semibold")
        ax.legend(frameon=True, facecolor="white", loc="upper left")
        ax.set_ylim(0.0, 0.55)

        plt.tight_layout()
        fig.savefig(charts_dir / "04_walk_forward_stability_ladder.png", dpi=300)
        fig.savefig(charts_dir / "04_walk_forward_stability_ladder.svg")
        plt.close(fig)

    # ----------------------------------------------------
    # Chart 5: September 21 Forensic Cross-Market Timeline
    # ----------------------------------------------------
    logger.info("Generating Chart 5: September 21 Forensic Cross-Market Timeline...")
    spot_file = Path("data/derived/features_with_outcomes_5m.parquet")
    if spot_file.exists() and cross_feat_file.exists():
        df_spot = pd.read_parquet(spot_file, columns=["datetime_open", "close", "volatility_realized_24h"])
        df_cross = pd.read_parquet(cross_feat_file, columns=["datetime_open", "vix_close", "nasdaq_ret_1d"])

        df_m = pd.merge(df_spot, df_cross, on="datetime_open")
        sep_mask = (df_m["datetime_open"] >= "2026-09-20 00:00:00") & (df_m["datetime_open"] <= "2026-09-22 00:00:00")
        df_sep = df_m[sep_mask].copy()

        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(12, 8), dpi=300, sharex=True)

        # Panel 1: BTC Price
        ax1.plot(df_sep["datetime_open"], df_sep["close"], color="#2c3e50", linewidth=2.0)
        ax1.set_ylabel("BTC Spot Price ($)", fontsize=10, fontweight="bold")
        ax1.set_title("September 21 Crash Anomaly: Multi-Market Forensic Confluence Timeline", fontsize=13, fontweight="bold", pad=12)

        # Highlight crash onset
        ax1.axvspan(pd.to_datetime("2026-09-20 22:00:00"), pd.to_datetime("2026-09-21 08:00:00"), color="#e74c3c", alpha=0.15, label="Crash Window")
        ax1.legend(loc="upper right")

        # Panel 2: Realized Volatility
        ax2.plot(df_sep["datetime_open"], df_sep["volatility_realized_24h"] * 1000, color="#e67e22", linewidth=1.8, label="BTC 24h Realized Vol (x1000)")
        ax2.set_ylabel("BTC Realized Vol", fontsize=10, fontweight="bold")
        ax2.legend(loc="upper left")

        # Panel 3: Macro VIX Level
        ax3.plot(df_sep["datetime_open"], df_sep["vix_close"], color="#9b59b6", linewidth=1.8, label="VIX Index Level")
        ax3.set_ylabel("VIX Level", fontsize=10, fontweight="bold")
        ax3.set_xlabel("Timestamp UTC", fontsize=11, fontweight="bold")
        ax3.xaxis.set_major_formatter(mdates.DateFormatter("%b %d\n%H:%M"))
        ax3.legend(loc="upper left")

        plt.tight_layout()
        fig.savefig(charts_dir / "05_september21_cross_market_forensic.png", dpi=300)
        fig.savefig(charts_dir / "05_september21_cross_market_forensic.svg")
        plt.close(fig)

    logger.info("All 5 Sprint 04 charts generated in both PNG and SVG formats!")


if __name__ == "__main__":
    generate_charts()

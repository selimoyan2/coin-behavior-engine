"""Matplotlib chart generators for visual research outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional
import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
import pandas as pd

from coin_behavior_engine.utils.logging import logger
from coin_behavior_engine.utils.timestamp import to_utc_ms


class ResearchChartGenerator:
    """Generates clean, publication-ready research charts."""

    def __init__(self, charts_dir: str | Path = "data/reports/charts"):
        self.charts_dir = Path(charts_dir)
        self.charts_dir.mkdir(parents=True, exist_ok=True)
        plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")

    def generate_all_charts(
        self,
        features_5m: pd.DataFrame,
        events_5m: pd.DataFrame,
        regimes_5m: pd.DataFrame,
        sept21_info: Optional[Dict] = None
    ) -> Dict[str, Path]:
        """Produce the 9 required research charts."""
        logger.info("Generating research visualization charts...")
        charts: Dict[str, Path] = {}

        df = features_5m.copy()
        if "datetime_open" not in df.columns:
            df["datetime_open"] = pd.to_datetime(df["timestamp_open"], unit="ms", utc=True)

        # 1. Price + Events
        p1 = self.charts_dir / "btc_2026_price_events.png"
        self._plot_price_and_events(df, events_5m, p1)
        charts["price_events"] = p1

        # 2. Price + Regimes
        p2 = self.charts_dir / "btc_2026_price_regimes.png"
        self._plot_price_and_regimes(df, regimes_5m, p2)
        charts["price_regimes"] = p2

        # 3. Rolling Volatility
        p3 = self.charts_dir / "rolling_volatility.png"
        self._plot_rolling_volatility(df, p3)
        charts["rolling_volatility"] = p3

        # 4. Volume Anomaly
        p4 = self.charts_dir / "volume_anomaly.png"
        self._plot_volume_anomaly(df, p4)
        charts["volume_anomaly"] = p4

        # 5. Event Score Timeline
        p5 = self.charts_dir / "event_score_timeline.png"
        self._plot_event_score_timeline(df, p5)
        charts["event_score_timeline"] = p5

        # 6. Top Upward Events
        p6 = self.charts_dir / "top_upward_events.png"
        self._plot_top_directional_events(events_5m, direction="upward", save_path=p6)
        charts["top_upward_events"] = p6

        # 7. Top Downward Events
        p7 = self.charts_dir / "top_downward_events.png"
        self._plot_top_directional_events(events_5m, direction="downward", save_path=p7)
        charts["top_downward_events"] = p7

        # 8. Major Compression Periods
        p8 = self.charts_dir / "major_compression_periods.png"
        self._plot_compression_periods(regimes_5m, p8)
        charts["major_compression_periods"] = p8

        # 9. September 21 Window
        p9 = self.charts_dir / "september_21_window.png"
        self._plot_september_21_window(df, events_5m, p9)
        charts["september_21_window"] = p9

        logger.info(f"Generated {len(charts)} charts in {self.charts_dir}")
        return charts

    def _plot_price_and_events(self, df: pd.DataFrame, events_df: pd.DataFrame, save_path: Path):
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(df["datetime_open"], df["close"], color="#2b5c8f", lw=1.2, label="BTCUSDT Close (5m)")

        if not events_df.empty:
            sig_events = events_df[events_df["is_significant"]]
            if not sig_events.empty:
                # Merge datetime_open if not in events_df
                if "datetime_open" not in sig_events.columns:
                    sig_events = sig_events.copy()
                    sig_events["datetime_open"] = pd.to_datetime(sig_events["timestamp_open"], unit="ms", utc=True)

                up_mask = sig_events["event_type"].str.contains("UPWARD|BREAKOUT", na=False)
                down_mask = sig_events["event_type"].str.contains("DOWNWARD|BREAKDOWN", na=False)

                ax.scatter(sig_events.loc[up_mask, "datetime_open"], sig_events.loc[up_mask, "close_price"],
                           color="green", s=35, marker="^", label="Significant Upward Event", zorder=5)
                ax.scatter(sig_events.loc[down_mask, "datetime_open"], sig_events.loc[down_mask, "close_price"],
                           color="red", s=35, marker="v", label="Significant Downward Event", zorder=5)

        ax.set_title("BTCUSDT 2026: Price Action & Unsupervised Statistical Events", fontsize=14, fontweight="bold")
        ax.set_ylabel("Price (USDT)")
        ax.legend(loc="upper left")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close(fig)

    def _plot_price_and_regimes(self, df: pd.DataFrame, regimes_df: pd.DataFrame, save_path: Path):
        fig, ax = plt.subplots(figsize=(14, 6))
        ax.plot(df["datetime_open"], df["close"], color="black", lw=1.0, label="BTCUSDT Price")

        color_map = {
            "TRENDING_UP": "#c8e6c9",
            "TRENDING_DOWN": "#ffcdd2",
            "LOW_VOLATILITY_COMPRESSION": "#bbdefb",
            "HIGH_VOLATILITY": "#ffe0b2",
            "SIDEWAYS": "#f5f5f5",
            "TRANSITION": "#e1bee7",
        }

        # Subsample or plot top regime blocks
        for _, reg in regimes_df.iterrows():
            st = pd.to_datetime(reg["start_timestamp"], unit="ms", utc=True)
            et = pd.to_datetime(reg["end_timestamp"], unit="ms", utc=True)
            lbl = reg["regime_label"]
            col = color_map.get(lbl, "#e0e0e0")
            ax.axvspan(st, et, color=col, alpha=0.35)

        ax.set_title("BTCUSDT 2026: Unsupervised Market Regimes", fontsize=14, fontweight="bold")
        ax.set_ylabel("Price (USDT)")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close(fig)

    def _plot_rolling_volatility(self, df: pd.DataFrame, save_path: Path):
        fig, ax = plt.subplots(figsize=(14, 5))
        if "volatility_realized_short" in df.columns:
            ax.plot(df["datetime_open"], df["volatility_realized_short"], color="#d35400", lw=1.0, label="Realized Vol (1h)")
        if "volatility_realized_baseline" in df.columns:
            ax.plot(df["datetime_open"], df["volatility_realized_baseline"], color="#2c3e50", lw=1.2, label="Realized Vol (24h Baseline)")

        ax.set_title("BTCUSDT 2026: Rolling Realized Volatility Dynamics", fontsize=14, fontweight="bold")
        ax.set_ylabel("Standard Deviation of Log Returns")
        ax.legend(loc="upper right")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close(fig)

    def _plot_volume_anomaly(self, df: pd.DataFrame, save_path: Path):
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True, gridspec_kw={"height_ratios": [2, 1]})
        ax1.plot(df["datetime_open"], df["close"], color="#34495e", lw=1.0, label="Close Price")
        ax1.set_ylabel("Price (USDT)")
        ax1.set_title("BTCUSDT 2026: Volume Profile and Anomalies", fontsize=14, fontweight="bold")

        ax2.bar(df["datetime_open"], df["volume"], color="#95a5a6", width=0.003, label="5m Volume")
        if "volume_mean_baseline" in df.columns:
            ax2.plot(df["datetime_open"], df["volume_mean_baseline"], color="#e74c3c", lw=1.2, label="24h Rolling Mean Volume")
        ax2.set_ylabel("Volume (BTC)")
        ax2.legend(loc="upper right")
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close(fig)

    def _plot_event_score_timeline(self, df: pd.DataFrame, save_path: Path):
        fig, ax = plt.subplots(figsize=(14, 5))
        score = df.get("event_score", pd.Series(np.zeros(len(df))))
        ax.plot(df["datetime_open"], score, color="#8e44ad", lw=0.8, label="Composite Event Score")
        ax.axhline(0.95, color="#e67e22", linestyle="--", lw=1.0, label="Candidate Threshold (p95)")
        ax.axhline(0.99, color="#c0392b", linestyle="--", lw=1.2, label="Significant Threshold (p99)")

        ax.set_title("BTCUSDT 2026: Adaptive Event Anomaly Score Timeline", fontsize=14, fontweight="bold")
        ax.set_ylabel("Event Score [0.0 - 1.0]")
        ax.set_ylim(0.0, 1.05)
        ax.legend(loc="upper left")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y-%m-%d"))
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close(fig)

    def _plot_top_directional_events(self, events_df: pd.DataFrame, direction: str, save_path: Path):
        fig, ax = plt.subplots(figsize=(12, 6))
        if events_df.empty:
            ax.text(0.5, 0.5, "No events detected", ha="center", va="center")
            plt.savefig(save_path)
            plt.close(fig)
            return

        if direction == "upward":
            subset = events_df[events_df["return_simple"] > 0].sort_values("event_score", ascending=False).head(10)
            color = "#27ae60"
            title = "Top 10 Upward Anomaly Events (2026)"
        else:
            subset = events_df[events_df["return_simple"] < 0].sort_values("event_score", ascending=False).head(10)
            color = "#c0392b"
            title = "Top 10 Downward Anomaly Events (2026)"

        if subset.empty:
            ax.text(0.5, 0.5, "No directional events found", ha="center", va="center")
        else:
            labels = [f"{r['event_id']}\n({r['datetime_open_utc'][:16]})" for _, r in subset.iterrows()]
            scores = subset["event_score"]
            ax.barh(labels, scores, color=color)
            ax.set_xlabel("Event Score")
            ax.set_xlim(0.9, 1.0)
            ax.invert_yaxis()

        ax.set_title(title, fontsize=14, fontweight="bold")
        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close(fig)

    def _plot_compression_periods(self, regimes_df: pd.DataFrame, save_path: Path):
        fig, ax = plt.subplots(figsize=(12, 6))
        if regimes_df.empty:
            ax.text(0.5, 0.5, "No regimes recorded", ha="center", va="center")
            plt.savefig(save_path)
            plt.close(fig)
            return

        comps = regimes_df[regimes_df["regime_label"] == "LOW_VOLATILITY_COMPRESSION"]
        if comps.empty:
            ax.text(0.5, 0.5, "No compression periods identified", ha="center", va="center")
        else:
            top_comps = comps.sort_values("duration_hours", ascending=False).head(10)
            labels = [f"ID {r['regime_id']}\n({r['start_utc'][:10]})" for _, r in top_comps.iterrows()]
            ax.bar(labels, top_comps["duration_hours"], color="#2980b9")
            ax.set_ylabel("Duration (Hours)")
            ax.set_title("Longest Low-Volatility Compression Periods (2026)", fontsize=14, fontweight="bold")
            plt.xticks(rotation=45, ha="right")

        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close(fig)

    def _plot_september_21_window(self, df: pd.DataFrame, events_df: pd.DataFrame, save_path: Path):
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 7), sharex=True, gridspec_kw={"height_ratios": [2, 1]})

        start_ms = to_utc_ms("2026-09-20T00:00:00Z")
        end_ms = to_utc_ms("2026-09-22T23:59:59Z")

        sub = df[(df["timestamp_open"] >= start_ms) & (df["timestamp_open"] <= end_ms)].copy()

        if sub.empty:
            ax1.text(0.5, 0.5, "No data available in September 20-22 window", ha="center", va="center")
            plt.savefig(save_path)
            plt.close(fig)
            return

        ax1.plot(sub["datetime_open"], sub["close"], color="#2c3e50", lw=1.5, label="BTC Price (5m)")
        ax1.set_title("BTCUSDT 2026-09-20 to 2026-09-22 Objective Market Audit", fontsize=14, fontweight="bold")
        ax1.set_ylabel("Price (USDT)")

        # Highlight detected events in window if any
        sub_events = events_df[
            (events_df["timestamp_open"] >= start_ms) & (events_df["timestamp_open"] <= end_ms)
        ]
        if not sub_events.empty:
            for _, ev in sub_events.iterrows():
                dt = pd.to_datetime(ev["timestamp_open"], unit="ms", utc=True)
                ax1.axvline(dt, color="purple", linestyle=":", lw=1.2, alpha=0.7)
                ax1.scatter(dt, ev["close_price"], color="purple", s=60, zorder=6)

        ax2.plot(sub["datetime_open"], sub.get("event_score", pd.Series(np.zeros(len(sub)))), color="#8e44ad", lw=1.2, label="Event Score")
        ax2.axhline(0.95, color="#e67e22", linestyle="--", lw=1.0, label="Candidate p95")
        ax2.axhline(0.99, color="#c0392b", linestyle="--", lw=1.0, label="Significant p99")
        ax2.set_ylabel("Score")
        ax2.set_ylim(0.0, 1.05)
        ax2.legend(loc="upper left")

        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%m-%d %H:%M"))
        fig.autofmt_xdate()
        plt.tight_layout()
        plt.savefig(save_path, dpi=150)
        plt.close(fig)

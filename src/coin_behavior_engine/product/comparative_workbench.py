"""
CBE — Interactive Comparative Historical Market Workbench
Enables quantitative comparison between two distinct historical cryptocurrency market periods.
Computes return profiles, annualized realized volatility, maximum drawdown, amplitude,
volume characteristics, and normalized trajectory curves with anchor candle locking.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
import io
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cbe.comparative_workbench")

ANNUAL_BARS_LOOKUP = {
    "5m": 365.25 * 24 * 12,    # 105,192
    "15m": 365.25 * 24 * 4,    # 35,064
    "1h": 365.25 * 24,         # 8,766
    "4h": 365.25 * 6,          # 2,191.5
    "1d": 365.25,              # 365.25
}


def sanitize_csv_cell(val: Any) -> Any:
    """Prepend a single quote if string starts with dangerous spreadsheet formula triggers."""
    if isinstance(val, str):
        if val.startswith(("=", "+", "-", "@", "\t", "\r")):
            return "'" + val
    return val


class ComparativeMarketEngine:
    """Quantitative comparison engine for historical market periods."""

    @classmethod
    def load_period_candles(
        cls,
        month: Optional[str] = None,
        interval: str = "1h",
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        limit: int = 500,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """Load candles for a period using DatasetManager."""
        from coin_behavior_engine.product.dataset_manager import DatasetManager
        dm = DatasetManager.get_instance()
        res = dm.query_candles(
            interval=interval,
            month=month,
            start_utc=start_utc,
            end_utc=end_utc,
            limit=limit,
            offset=offset,
        )
        return res.get("candles", [])

    @classmethod
    def compute_period_metrics(
        cls,
        candles: List[Dict[str, Any]],
        interval: str = "1h",
    ) -> Dict[str, Any]:
        """Compute statistical and price action metrics for a set of candles."""
        if not candles:
            return {
                "candle_count": 0,
                "start_time_utc": None,
                "end_time_utc": None,
                "start_price": 0.0,
                "end_price": 0.0,
                "high_price": 0.0,
                "low_price": 0.0,
                "abs_change": 0.0,
                "net_return_pct": 0.0,
                "amplitude_pct": 0.0,
                "max_drawdown_pct": 0.0,
                "realized_volatility_annualized_pct": 0.0,
                "total_volume": 0.0,
                "avg_volume_per_bar": 0.0,
                "gaps_count": 0,
            }

        start_time = candles[0].get("timestamp_utc") or candles[0].get("datetime_utc")
        end_time = candles[-1].get("timestamp_utc") or candles[-1].get("datetime_utc")
        start_price = float(candles[0]["open"])
        end_price = float(candles[-1]["close"])
        abs_change = round(end_price - start_price, 2)
        net_return_pct = round(((end_price / start_price) - 1.0) * 100.0, 3) if start_price > 0 else 0.0

        highs = [float(c["high"]) for c in candles]
        lows = [float(c["low"]) for c in candles]
        closes = [float(c["close"]) for c in candles]
        volumes = [float(c.get("volume", 0.0)) for c in candles]

        high_price = round(max(highs), 2)
        low_price = round(min(lows), 2)
        amplitude_pct = round(((high_price - low_price) / low_price) * 100.0, 3) if low_price > 0 else 0.0

        # Maximum Drawdown
        peak = closes[0]
        max_dd = 0.0
        for price in closes:
            if price > peak:
                peak = price
            elif peak > 0:
                dd = (peak - price) / peak
                if dd > max_dd:
                    max_dd = dd
        max_drawdown_pct = round(max_dd * 100.0, 3)

        # Realized Volatility (Annualized)
        annual_bars = ANNUAL_BARS_LOOKUP.get(interval.lower(), 8766.0)
        log_returns = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            curr = closes[i]
            if prev > 0 and curr > 0:
                log_returns.append(math.log(curr / prev))

        if len(log_returns) > 1:
            mean_ret = sum(log_returns) / len(log_returns)
            variance = sum((r - mean_ret) ** 2 for r in log_returns) / (len(log_returns) - 1)
            vol_per_bar = math.sqrt(variance)
            realized_vol_pct = round(vol_per_bar * math.sqrt(annual_bars) * 100.0, 2)
        else:
            realized_vol_pct = 0.0

        total_vol = round(sum(volumes), 2)
        avg_vol = round(total_vol / len(volumes), 2) if volumes else 0.0

        # Gaps count
        gaps_count = 0
        from coin_behavior_engine.product.dataset_manager import INTERVAL_DURATIONS_MS
        dur_ms = INTERVAL_DURATIONS_MS.get(interval.lower(), 3600_000)
        for i in range(1, len(candles)):
            diff = candles[i]["open_time"] - candles[i - 1]["open_time"]
            if diff > dur_ms:
                gaps_count += 1

        return {
            "candle_count": len(candles),
            "start_time_utc": start_time,
            "end_time_utc": end_time,
            "start_price": start_price,
            "end_price": end_price,
            "high_price": high_price,
            "low_price": low_price,
            "abs_change": abs_change,
            "net_return_pct": net_return_pct,
            "amplitude_pct": amplitude_pct,
            "max_drawdown_pct": max_drawdown_pct,
            "realized_volatility_annualized_pct": realized_vol_pct,
            "total_volume": total_vol,
            "avg_volume_per_bar": avg_vol,
            "gaps_count": gaps_count,
        }

    @classmethod
    def normalize_trajectories(
        cls,
        candles_a: List[Dict[str, Any]],
        candles_b: List[Dict[str, Any]],
        anchor_index_a: int = 0,
        anchor_index_b: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        Normalize price trajectories of both periods relative to an anchor candle.
        R_t = ((Close_t / AnchorClose) - 1.0) * 100.
        """
        len_a = len(candles_a)
        len_b = len(candles_b)
        max_steps = max(len_a, len_b)

        idx_a = min(max(0, anchor_index_a), len_a - 1) if len_a > 0 else 0
        idx_b = min(max(0, anchor_index_b), len_b - 1) if len_b > 0 else 0

        anchor_price_a = float(candles_a[idx_a]["close"]) if len_a > 0 else 1.0
        anchor_price_b = float(candles_b[idx_b]["close"]) if len_b > 0 else 1.0

        trajectory: List[Dict[str, Any]] = []
        for step in range(max_steps):
            entry: Dict[str, Any] = {"step": step}
            if step < len_a:
                ca = candles_a[step]
                p_a = float(ca["close"])
                ret_a = round(((p_a / anchor_price_a) - 1.0) * 100.0, 3)
                entry["time_a"] = ca.get("timestamp_utc") or ca.get("datetime_utc")
                entry["price_a"] = p_a
                entry["return_pct_a"] = ret_a
                entry["volume_a"] = float(ca.get("volume", 0.0))
            else:
                entry["time_a"] = None
                entry["price_a"] = None
                entry["return_pct_a"] = None
                entry["volume_a"] = None

            if step < len_b:
                cb = candles_b[step]
                p_b = float(cb["close"])
                ret_b = round(((p_b / anchor_price_b) - 1.0) * 100.0, 3)
                entry["time_b"] = cb.get("timestamp_utc") or cb.get("datetime_utc")
                entry["price_b"] = p_b
                entry["return_pct_b"] = ret_b
                entry["volume_b"] = float(cb.get("volume", 0.0))
            else:
                entry["time_b"] = None
                entry["price_b"] = None
                entry["return_pct_b"] = None
                entry["volume_b"] = None

            trajectory.append(entry)

        return trajectory

    @classmethod
    def compare_periods(
        cls,
        period_a: Dict[str, Any],
        period_b: Dict[str, Any],
        anchor_a: int = 0,
        anchor_b: int = 0,
    ) -> Dict[str, Any]:
        """
        Execute full comparative analysis between Period A and Period B.
        """
        intv_a = period_a.get("interval", "1h")
        intv_b = period_b.get("interval", "1h")

        candles_a = cls.load_period_candles(
            month=period_a.get("month"),
            interval=intv_a,
            start_utc=period_a.get("start_utc"),
            end_utc=period_a.get("end_utc"),
            limit=period_a.get("limit", 500),
            offset=period_a.get("offset", 0),
        )

        candles_b = cls.load_period_candles(
            month=period_b.get("month"),
            interval=intv_b,
            start_utc=period_b.get("start_utc"),
            end_utc=period_b.get("end_utc"),
            limit=period_b.get("limit", 500),
            offset=period_b.get("offset", 0),
        )

        metrics_a = cls.compute_period_metrics(candles_a, interval=intv_a)
        metrics_b = cls.compute_period_metrics(candles_b, interval=intv_b)

        trajectory = cls.normalize_trajectories(
            candles_a,
            candles_b,
            anchor_index_a=anchor_a,
            anchor_index_b=anchor_b,
        )

        # Delta metrics (Period B - Period A)
        delta_metrics = {
            "net_return_diff_pct": round(metrics_b["net_return_pct"] - metrics_a["net_return_pct"], 3),
            "volatility_diff_pct": round(metrics_b["realized_volatility_annualized_pct"] - metrics_a["realized_volatility_annualized_pct"], 2),
            "max_drawdown_diff_pct": round(metrics_b["max_drawdown_pct"] - metrics_a["max_drawdown_pct"], 3),
            "amplitude_diff_pct": round(metrics_b["amplitude_pct"] - metrics_a["amplitude_pct"], 3),
            "volume_ratio": round(metrics_b["total_volume"] / metrics_a["total_volume"], 3) if metrics_a["total_volume"] > 0 else 0.0,
        }

        return {
            "status": "success",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "period_a": {
                "params": period_a,
                "anchor_index": anchor_a,
                "metrics": metrics_a,
            },
            "period_b": {
                "params": period_b,
                "anchor_index": anchor_b,
                "metrics": metrics_b,
            },
            "delta_metrics": delta_metrics,
            "candles_count_a": len(candles_a),
            "candles_count_b": len(candles_b),
            "trajectory_steps": len(trajectory),
            "normalized_trajectory": trajectory,
            "candles_a": candles_a,
            "candles_b": candles_b,
            "governance_safeguard": {
                "predictive_validity": "NOT_CLAIMED",
                "purpose": "HISTORICAL_COMPARATIVE_RESEARCH_ONLY",
            }
        }

    @classmethod
    def export_comparison_csv(cls, comparison_data: Dict[str, Any]) -> str:
        """
        Export comparative trajectory data as CSV with formula injection sanitization.
        """
        output = io.StringIO()
        writer = csv.writer(output, lineterminator="\n")

        # Header metadata rows
        writer.writerow(["# CBE HISTORICAL COMPARATIVE WORKBENCH EXPORT"])
        writer.writerow(["# Exported UTC", sanitize_csv_cell(comparison_data.get("timestamp_utc", ""))])
        
        pa_params = comparison_data.get("period_a", {}).get("params", {})
        pb_params = comparison_data.get("period_b", {}).get("params", {})
        writer.writerow(["# Period A Month", sanitize_csv_cell(pa_params.get("month", "Custom"))])
        writer.writerow(["# Period B Month", sanitize_csv_cell(pb_params.get("month", "Custom"))])

        ma = comparison_data.get("period_a", {}).get("metrics", {})
        mb = comparison_data.get("period_b", {}).get("metrics", {})
        writer.writerow(["# Metric", "Period A", "Period B", "Delta (B - A)"])
        writer.writerow(["# Net Return %", ma.get("net_return_pct", 0), mb.get("net_return_pct", 0), comparison_data.get("delta_metrics", {}).get("net_return_diff_pct", 0)])
        writer.writerow(["# Realized Vol %", ma.get("realized_volatility_annualized_pct", 0), mb.get("realized_volatility_annualized_pct", 0), comparison_data.get("delta_metrics", {}).get("volatility_diff_pct", 0)])
        writer.writerow(["# Max Drawdown %", ma.get("max_drawdown_pct", 0), mb.get("max_drawdown_pct", 0), comparison_data.get("delta_metrics", {}).get("max_drawdown_diff_pct", 0)])
        writer.writerow(["# Amplitude %", ma.get("amplitude_pct", 0), mb.get("amplitude_pct", 0), comparison_data.get("delta_metrics", {}).get("amplitude_diff_pct", 0)])
        writer.writerow(["# Total Volume", ma.get("total_volume", 0), mb.get("total_volume", 0), ""])

        writer.writerow([])
        # Trajectory table header
        columns = [
            "step",
            "time_a", "price_a", "return_pct_a", "volume_a",
            "time_b", "price_b", "return_pct_b", "volume_b"
        ]
        writer.writerow(columns)

        trajectory = comparison_data.get("normalized_trajectory", [])
        for row in trajectory:
            writer.writerow([
                row.get("step"),
                sanitize_csv_cell(row.get("time_a") or ""),
                row.get("price_a") if row.get("price_a") is not None else "",
                row.get("return_pct_a") if row.get("return_pct_a") is not None else "",
                row.get("volume_a") if row.get("volume_a") is not None else "",
                sanitize_csv_cell(row.get("time_b") or ""),
                row.get("price_b") if row.get("price_b") is not None else "",
                row.get("return_pct_b") if row.get("return_pct_b") is not None else "",
                row.get("volume_b") if row.get("volume_b") is not None else "",
            ])

        return output.getvalue()

    @classmethod
    def export_comparison_json(cls, comparison_data: Dict[str, Any]) -> str:
        """Export comparative analysis as JSON."""
        # Omit raw candles to keep JSON bounded
        export_payload = {k: v for k, v in comparison_data.items() if k not in ("candles_a", "candles_b")}
        return json.dumps(export_payload, indent=2, ensure_ascii=False)

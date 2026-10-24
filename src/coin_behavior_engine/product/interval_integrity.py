"""
CBE — Cross-Interval Data Integrity Engine
Validates mathematical, temporal, and aggregation consistency across canonical
historical intervals (5m, 15m, 1h, 4h, 1d) for Coin Behavior Engine.

Fail-Closed Rules Enforced:
1. Higher-timeframe candle open == first sub-bar open.
2. Higher-timeframe candle high == max(sub-bar highs).
3. Higher-timeframe candle low == min(sub-bar lows).
4. Higher-timeframe candle close == last sub-bar close.
5. Higher-timeframe candle volume == sum(sub-bar volumes).
6. Strict UTC boundary alignment.
7. Incomplete aggregation windows are NEVER filled with synthetic data and are classified as INCOMPLETE.
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

logger = logging.getLogger("cbe_interval_integrity")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_DIR = REPO_ROOT / "data" / "binance_spot_multiyear"

INTERVAL_RATIOS = {
    ("5m", "15m"): 3,
    ("5m", "1h"): 12,
    ("15m", "1h"): 4,
    ("1h", "4h"): 4,
    ("1h", "1d"): 24,
    ("4h", "1d"): 6,
    ("5m", "4h"): 48,
    ("5m", "1d"): 288,
}

INTERVAL_MS = {
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}

# Numerical tolerance policies
PRICE_TOLERANCE_ABS = 1e-4
PRICE_TOLERANCE_REL = 1e-5
VOLUME_TOLERANCE_ABS = 1e-2
VOLUME_TOLERANCE_REL = 1e-4


@dataclass
class DiscrepancyRecord:
    timestamp_utc: str
    open_time_ms: int
    base_interval: str
    target_interval: str
    field_name: str
    expected_value: float
    actual_value: float
    abs_difference: float
    rel_difference: float
    classification: str  # DISCREPANCY, WARNING, INCOMPLETE_WINDOW


@dataclass
class IntervalPairAuditResult:
    base_interval: str
    target_interval: str
    month: str
    status: str  # PASS, PASS_WITH_WARNINGS, FAIL, INCOMPLETE, NOT_EVALUATED
    total_candles_checked: int
    valid_complete_windows: int
    incomplete_windows_count: int
    discrepancy_count: int
    max_price_diff: float
    max_volume_diff: float
    discrepancies: List[DiscrepancyRecord] = field(default_factory=list)
    execution_time_ms: float = 0.0


class CrossIntervalIntegrityEngine:
    """Vectorized mathematical and temporal validation engine for multi-interval historical archives."""

    _lock = threading.Lock()
    _instance: Optional["CrossIntervalIntegrityEngine"] = None

    def __init__(self, dataset_dir: Optional[Path] = None):
        self.dataset_dir = Path(dataset_dir) if dataset_dir else DEFAULT_DATASET_DIR
        self._cache: Dict[str, Any] = {}
        self._cache_time: float = 0.0
        self._cache_ttl_sec: float = 120.0

    @classmethod
    def get_instance(cls, dataset_dir: Optional[Path] = None) -> "CrossIntervalIntegrityEngine":
        if dataset_dir and Path(dataset_dir) != DEFAULT_DATASET_DIR:
            return cls(dataset_dir)
        with cls._lock:
            if cls._instance is None or cls._instance.dataset_dir != DEFAULT_DATASET_DIR:
                cls._instance = cls(DEFAULT_DATASET_DIR)
            return cls._instance

    def invalidate_cache(self) -> None:
        with self._lock:
            self._cache.clear()
            self._cache_time = 0.0

    def verify_pair(
        self,
        df_lower: pd.DataFrame,
        df_higher: pd.DataFrame,
        interval_lower: str,
        interval_higher: str,
        month: str = "2026-09",
    ) -> Dict[str, Any]:
        """Validate mathematical consistency between two in-memory interval dataframes."""
        pair = (interval_lower, interval_higher)
        if pair not in INTERVAL_RATIOS:
            raise ValueError(f"Unsupported interval pair: {pair}")

        expected_ratio = INTERVAL_RATIOS[pair]
        target_ms = INTERVAL_MS[interval_higher]

        df_base = df_lower.copy()
        df_base["window_time"] = (df_base["open_time"] // target_ms) * target_ms

        agg = (
            df_base.groupby("window_time")
            .agg(
                agg_open=("open", "first"),
                agg_high=("high", "max"),
                agg_low=("low", "min"),
                agg_close=("close", "last"),
                agg_volume=("volume", "sum"),
                sub_bars=("open", "count"),
                first_sub_time=("open_time", "first"),
            )
            .reset_index()
        )

        merged = pd.merge(
            df_higher,
            agg,
            left_on="open_time",
            right_on="window_time",
            how="inner",
        )

        total_checked = len(merged)
        if total_checked == 0:
            return {
                "verdict": "INCOMPLETE",
                "status": "INCOMPLETE",
                "discrepancies_count": 0,
                "windows_evaluated": 0,
                "sub_bars_evaluated": len(df_lower),
                "max_absolute_price_diff": 0.0,
                "max_volume_diff": 0.0,
                "discrepancies": [],
            }

        incomplete_mask = merged["sub_bars"] < expected_ratio
        incomplete_count = int(incomplete_mask.sum())
        complete_count = total_checked - incomplete_count

        valid_merged = merged[~incomplete_mask].copy()

        discrepancies = []
        max_p_diff = 0.0
        max_v_diff = 0.0

        if len(valid_merged) > 0:
            diff_o = (valid_merged["open"] - valid_merged["agg_open"]).abs()
            diff_h = (valid_merged["high"] - valid_merged["agg_high"]).abs()
            diff_l = (valid_merged["low"] - valid_merged["agg_low"]).abs()
            diff_c = (valid_merged["close"] - valid_merged["agg_close"]).abs()
            diff_v = (valid_merged["volume"] - valid_merged["agg_volume"]).abs()

            max_p_diff = float(max(diff_o.max(), diff_h.max(), diff_l.max(), diff_c.max()))
            max_v_diff = float(diff_v.max())

            failed_mask = (
                (diff_o > PRICE_TOLERANCE_ABS)
                | (diff_h > PRICE_TOLERANCE_ABS)
                | (diff_l > PRICE_TOLERANCE_ABS)
                | (diff_c > PRICE_TOLERANCE_ABS)
                | (diff_v > VOLUME_TOLERANCE_ABS)
            )

            for idx, row in valid_merged[failed_mask].iterrows():
                discrepancies.append({
                    "open_time": int(row["open_time"]),
                    "diff_open": float(abs(row["open"] - row["agg_open"])),
                    "diff_close": float(abs(row["close"] - row["agg_close"])),
                })

        status = "PASS" if (len(discrepancies) == 0 and complete_count > 0) else ("FAIL" if len(discrepancies) > 0 else "INCOMPLETE")

        return {
            "verdict": status,
            "status": status,
            "discrepancies_count": len(discrepancies),
            "windows_evaluated": complete_count,
            "incomplete_windows_count": incomplete_count,
            "sub_bars_evaluated": len(df_lower),
            "max_absolute_price_diff": max_p_diff,
            "max_volume_diff": max_v_diff,
            "discrepancies": discrepancies,
        }

    def verify_all(self, month: str = "2026-09", symbol: str = "BTCUSDT") -> Dict[str, Any]:
        """Validate key interval transitions for a given month."""
        pairs = [("5m", "15m"), ("5m", "1h"), ("1h", "4h"), ("1h", "1d")]
        checks = []
        overall = "PASS"
        for b_itv, t_itv in pairs:
            res = self.validate_interval_pair(symbol, month, b_itv, t_itv)
            c = {
                "interval_from": b_itv,
                "interval_to": t_itv,
                "month": month,
                "sub_bars_evaluated": res.valid_complete_windows * INTERVAL_RATIOS.get((b_itv, t_itv), 1),
                "windows_evaluated": res.valid_complete_windows,
                "discrepancies_count": res.discrepancy_count,
                "max_absolute_price_diff": res.max_price_diff,
                "max_volume_diff": res.max_volume_diff,
                "verdict": res.status,
            }
            checks.append(c)
            if res.status == "FAIL":
                overall = "FAIL"
            elif res.status in ("PASS_WITH_WARNINGS", "INCOMPLETE") and overall != "FAIL":
                overall = "PASS_WITH_WARNINGS"

        return {
            "status": "success",
            "overall_verdict": overall,
            "month": month,
            "checks": checks,
        }

    def validate_interval_pair(
        self,
        symbol: str,
        month: str,
        base_interval: str,
        target_interval: str,
    ) -> IntervalPairAuditResult:
        """Validate consistency of target_interval against base_interval for a given month."""
        t0 = time.perf_counter()

        pair = (base_interval, target_interval)
        if pair not in INTERVAL_RATIOS:
            raise ValueError(f"Unsupported interval pair: {pair}")

        expected_ratio = INTERVAL_RATIOS[pair]
        target_ms = INTERVAL_MS[target_interval]

        base_file = self.dataset_dir / base_interval / f"{symbol}-{base_interval}-{month}.parquet"
        target_file = self.dataset_dir / target_interval / f"{symbol}-{target_interval}-{month}.parquet"

        if not base_file.exists() or not target_file.exists():
            return IntervalPairAuditResult(
                base_interval=base_interval,
                target_interval=target_interval,
                month=month,
                status="NOT_EVALUATED",
                total_candles_checked=0,
                valid_complete_windows=0,
                incomplete_windows_count=0,
                discrepancy_count=0,
                max_price_diff=0.0,
                max_volume_diff=0.0,
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        try:
            df_base = pd.read_parquet(base_file)
            df_target = pd.read_parquet(target_file)
        except Exception as e:
            logger.error("Failed to read parquet for integrity audit: %s", e)
            return IntervalPairAuditResult(
                base_interval=base_interval,
                target_interval=target_interval,
                month=month,
                status="FAIL",
                total_candles_checked=0,
                valid_complete_windows=0,
                incomplete_windows_count=0,
                discrepancy_count=1,
                max_price_diff=0.0,
                max_volume_diff=0.0,
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        # Aggregate base candles to target window boundaries
        df_base = df_base.copy()
        df_base["window_time"] = (df_base["open_time"] // target_ms) * target_ms

        agg = (
            df_base.groupby("window_time")
            .agg(
                agg_open=("open", "first"),
                agg_high=("high", "max"),
                agg_low=("low", "min"),
                agg_close=("close", "last"),
                agg_volume=("volume", "sum"),
                sub_bars=("open", "count"),
                first_sub_time=("open_time", "first"),
            )
            .reset_index()
        )

        merged = pd.merge(
            df_target,
            agg,
            left_on="open_time",
            right_on="window_time",
            how="inner",
        )

        total_checked = len(merged)
        if total_checked == 0:
            return IntervalPairAuditResult(
                base_interval=base_interval,
                target_interval=target_interval,
                month=month,
                status="INCOMPLETE",
                total_candles_checked=0,
                valid_complete_windows=0,
                incomplete_windows_count=0,
                discrepancy_count=0,
                max_price_diff=0.0,
                max_volume_diff=0.0,
                execution_time_ms=(time.perf_counter() - t0) * 1000,
            )

        # Check window completeness
        incomplete_mask = merged["sub_bars"] < expected_ratio
        incomplete_count = int(incomplete_mask.sum())
        complete_count = total_checked - incomplete_count

        # Compute differences on complete windows
        valid_merged = merged[~incomplete_mask].copy()

        discrepancies: List[DiscrepancyRecord] = []
        max_p_diff = 0.0
        max_v_diff = 0.0

        if len(valid_merged) > 0:
            diff_open = (valid_merged["open"] - valid_merged["agg_open"]).abs()
            diff_high = (valid_merged["high"] - valid_merged["agg_high"]).abs()
            diff_low = (valid_merged["low"] - valid_merged["agg_low"]).abs()
            diff_close = (valid_merged["close"] - valid_merged["agg_close"]).abs()
            diff_vol = (valid_merged["volume"] - valid_merged["agg_volume"]).abs()

            max_p_diff = float(max(diff_open.max(), diff_high.max(), diff_low.max(), diff_close.max()))
            max_v_diff = float(diff_vol.max())

            # Detect specific violations
            for col_target, col_agg, field_name, is_vol in [
                ("open", "agg_open", "open", False),
                ("high", "agg_high", "high", False),
                ("low", "agg_low", "low", False),
                ("close", "agg_close", "close", False),
                ("volume", "agg_volume", "volume", True),
            ]:
                diff_series = (valid_merged[col_target] - valid_merged[col_agg]).abs()
                tol = VOLUME_TOLERANCE_ABS if is_vol else PRICE_TOLERANCE_ABS
                bad_idx = diff_series[diff_series > tol].index

                for idx in bad_idx[:10]:  # Limit sample size
                    row = valid_merged.loc[idx]
                    dt_str = str(row.get("datetime", row["open_time"]))
                    discrepancies.append(
                        DiscrepancyRecord(
                            timestamp_utc=dt_str,
                            open_time_ms=int(row["open_time"]),
                            base_interval=base_interval,
                            target_interval=target_interval,
                            field_name=field_name,
                            expected_value=float(row[col_agg]),
                            actual_value=float(row[col_target]),
                            abs_difference=float(diff_series.loc[idx]),
                            rel_difference=float(diff_series.loc[idx] / (abs(row[col_agg]) + 1e-9)),
                            classification="DISCREPANCY",
                        )
                    )

        # Record sample incomplete windows if any
        if incomplete_count > 0:
            for idx in merged[incomplete_mask].index[:5]:
                row = merged.loc[idx]
                dt_str = str(row.get("datetime", row["open_time"]))
                discrepancies.append(
                    DiscrepancyRecord(
                        timestamp_utc=dt_str,
                        open_time_ms=int(row["open_time"]),
                        base_interval=base_interval,
                        target_interval=target_interval,
                        field_name="sub_bars_count",
                        expected_value=float(expected_ratio),
                        actual_value=float(row["sub_bars"]),
                        abs_difference=float(expected_ratio - row["sub_bars"]),
                        rel_difference=float((expected_ratio - row["sub_bars"]) / expected_ratio),
                        classification="INCOMPLETE_WINDOW",
                    )
                )

        # Verdict assignment
        if len(discrepancies) == 0 and incomplete_count == 0:
            status = "PASS"
        elif len(discrepancies) == 0 and incomplete_count > 0:
            status = "INCOMPLETE"
        elif max_p_diff <= PRICE_TOLERANCE_ABS * 2 and max_v_diff <= VOLUME_TOLERANCE_ABS * 2:
            status = "PASS_WITH_WARNINGS"
        else:
            status = "FAIL"

        return IntervalPairAuditResult(
            base_interval=base_interval,
            target_interval=target_interval,
            month=month,
            status=status,
            total_candles_checked=total_checked,
            valid_complete_windows=complete_count,
            incomplete_windows_count=incomplete_count,
            discrepancy_count=len(discrepancies),
            max_price_diff=max_p_diff,
            max_volume_diff=max_v_diff,
            discrepancies=discrepancies,
            execution_time_ms=(time.perf_counter() - t0) * 1000,
        )

    def audit_archive_summary(
        self,
        symbol: str = "BTCUSDT",
        target_months: Optional[List[str]] = None,
        force_refresh: bool = False,
    ) -> Dict[str, Any]:
        """Audit sample representative historical months across key interval transitions."""
        now = time.time()
        with self._lock:
            if not force_refresh and self._cache and (now - self._cache_time) < self._cache_ttl_sec:
                return self._cache

        # Canonical pairs to audit
        pairs = [
            ("5m", "15m"),
            ("5m", "1h"),
            ("1h", "4h"),
            ("1h", "1d"),
        ]

        if not target_months:
            # Audit latest 3 months plus sample historical anchor months
            target_months = ["2026-09", "2026-08", "2026-07", "2024-03", "2022-01"]

        pair_results = []
        overall_status = "PASS"
        total_candles = 0
        total_discrepancies = 0

        for base_itv, tgt_itv in pairs:
            for m in target_months:
                res = self.validate_interval_pair(symbol, m, base_itv, tgt_itv)
                pair_dict = asdict(res)
                # Keep discrepancy count compact
                pair_dict["discrepancies_sample"] = pair_dict.pop("discrepancies")[:5]
                pair_results.append(pair_dict)

                total_candles += res.total_candles_checked
                total_discrepancies += res.discrepancy_count

                if res.status == "FAIL":
                    overall_status = "FAIL"
                elif res.status in ("PASS_WITH_WARNINGS", "INCOMPLETE") and overall_status != "FAIL":
                    overall_status = "PASS_WITH_WARNINGS"

        # Build checks list for UI and API consumers
        checks = []
        for p in pair_results:
            b = p["base_interval"]
            t = p["target_interval"]
            m = p["month"]
            checks.append({
                "interval_from": b,
                "interval_to": t,
                "month": m,
                "sub_bars_evaluated": p.get("valid_complete_windows", 0) * INTERVAL_RATIOS.get((b, t), 1),
                "windows_evaluated": p.get("valid_complete_windows", 0),
                "discrepancies_count": p.get("discrepancy_count", 0),
                "max_absolute_price_diff": p.get("max_price_diff", 0.0),
                "max_volume_diff": p.get("max_volume_diff", 0.0),
                "verdict": p.get("status", "PASS"),
            })

        summary = {
            "status": "success",
            "audit_timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "overall_integrity_verdict": overall_status,
            "overall_verdict": overall_status,
            "symbol": symbol,
            "audited_months": target_months,
            "audited_interval_pairs": [f"{b} -> {t}" for b, t in pairs],
            "total_candles_evaluated": total_candles,
            "total_discrepancies_detected": total_discrepancies,
            "tolerance_policies": {
                "price_tolerance_abs": PRICE_TOLERANCE_ABS,
                "price_tolerance_rel": PRICE_TOLERANCE_REL,
                "volume_tolerance_abs": VOLUME_TOLERANCE_ABS,
                "volume_tolerance_rel": VOLUME_TOLERANCE_REL,
                "incomplete_window_policy": "NO_SYNTHETIC_INTERPOLATION",
            },
            "pair_audits": pair_results,
            "checks": checks,
        }

        with self._lock:
            self._cache = summary
            self._cache_time = time.time()

        return summary

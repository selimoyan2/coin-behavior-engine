"""
CBE — Multi-Asset Historical Research Foundation
Provides symbol discovery, multi-asset data cataloging, cross-asset alignment,
rolling correlation, trajectory comparison, and strict fail-closed handling for missing archives.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("cbe.multi_asset")

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DATASET_DIR = REPO_ROOT / "data" / "binance_spot_multiyear"

SUPPORTED_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]


@dataclass
class SymbolCatalogEntry:
    symbol: str
    status: str  # "AVAILABLE", "UNAVAILABLE_NO_DATA", "PARTIAL"
    base_asset: str
    quote_asset: str
    market_type: str
    available_intervals: List[str]
    available_months_count: int
    earliest_month: Optional[str]
    latest_month: Optional[str]
    total_partitions: int
    size_mb: float
    notes: str


class MultiAssetCatalogEngine:
    """Discovers and catalogs multi-asset historical archives with fail-closed safety."""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir) if base_dir else DEFAULT_DATASET_DIR

    def discover_symbols(self) -> Dict[str, SymbolCatalogEntry]:
        """Discover available symbols across the historical archive directory."""
        catalog: Dict[str, SymbolCatalogEntry] = {}

        for sym in SUPPORTED_SYMBOLS:
            quote = "USDT"
            base = sym.replace("USDT", "")
            
            # Check partition presence across intervals
            intervals_found = []
            all_months = set()
            total_parts = 0
            total_bytes = 0

            if self.base_dir.exists():
                for intv_dir in self.base_dir.iterdir():
                    if intv_dir.is_dir() and intv_dir.name in ("1m", "5m", "15m", "1h", "4h", "1d"):
                        matching = list(intv_dir.glob(f"{sym}-{intv_dir.name}-*.parquet"))
                        if matching:
                            intervals_found.append(intv_dir.name)
                            total_parts += len(matching)
                            for m in matching:
                                total_bytes += m.stat().st_size
                                # Extract month string YYYY-MM
                                stem = m.stem
                                prefix = f"{sym}-{intv_dir.name}-"
                                if stem.startswith(prefix):
                                    m_str = stem[len(prefix):]
                                    if len(m_str) >= 7:
                                        all_months.add(m_str[:7])

            sorted_months = sorted(list(all_months))
            size_mb = round(total_bytes / (1024 * 1024), 2)

            if total_parts > 0:
                catalog[sym] = SymbolCatalogEntry(
                    symbol=sym,
                    status="AVAILABLE",
                    base_asset=base,
                    quote_asset=quote,
                    market_type="SPOT",
                    available_intervals=sorted(intervals_found),
                    available_months_count=len(sorted_months),
                    earliest_month=sorted_months[0] if sorted_months else None,
                    latest_month=sorted_months[-1] if sorted_months else None,
                    total_partitions=total_parts,
                    size_mb=size_mb,
                    notes=f"Orijinal Binance Spot arşivinden {len(sorted_months)} ay doğrulandı."
                )
            else:
                catalog[sym] = SymbolCatalogEntry(
                    symbol=sym,
                    status="UNAVAILABLE_NO_DATA",
                    base_asset=base,
                    quote_asset=quote,
                    market_type="SPOT",
                    available_intervals=[],
                    available_months_count=0,
                    earliest_month=None,
                    latest_month=None,
                    total_partitions=0,
                    size_mb=0.0,
                    notes="Bu varlık için çevrimdışı arşiv henüz içe aktarılmamıştır. Sentetik veri üretimi engellenmiştir."
                )

        return catalog

    def get_symbol_catalog_summary(self) -> Dict[str, Any]:
        """Return serialized catalog and operational state."""
        catalog = self.discover_symbols()
        return {
            "supported_symbols": SUPPORTED_SYMBOLS,
            "catalog": {k: asdict(v) for k, v in catalog.items()},
            "governance_rule": "FAIL_CLOSED_NO_SYNTHETIC_DATA",
            "active_symbol_default": "BTCUSDT",
        }

    def load_symbol_candles(
        self,
        symbol: str,
        interval: str = "1h",
        month: Optional[str] = None,
        start_utc: Optional[str] = None,
        end_utc: Optional[str] = None,
        limit: int = 500,
    ) -> Tuple[bool, List[Dict[str, Any]], Optional[str]]:
        """
        Load candles for specified symbol.
        Fails closed with explicit error message if data is unavailable.
        """
        catalog = self.discover_symbols()
        entry = catalog.get(symbol)

        if not entry or entry.status != "AVAILABLE":
            return (
                False,
                [],
                f"Varlık '{symbol}' için doğrulanmış çevrimdışı veri bulunamadı. "
                f"Sistem sentetik veri üretmez (Güvenlik Politikası: FAIL_CLOSED)."
            )

        if symbol == "BTCUSDT":
            from coin_behavior_engine.product.dataset_manager import DatasetManager
            dm = DatasetManager.get_instance(self.base_dir)
            res = dm.query_candles(
                interval=interval,
                month=month,
                start_utc=start_utc,
                end_utc=end_utc,
                limit=limit,
            )
            return (True, res.get("candles", []), None)

        # For other symbols if archives exist in base_dir/{interval}/{symbol}-{interval}-{month}.parquet
        # In this sprint, ETH/SOL archives are not yet ingested, so it triggers fail-closed above.
        return (False, [], f"Varlık '{symbol}' için veri akışı henüz aktif değil.")

    @classmethod
    def compare_assets(
        cls,
        candles_a: List[Dict[str, Any]],
        candles_b: List[Dict[str, Any]],
        symbol_a: str = "BTCUSDT",
        symbol_b: str = "ETHUSDT",
        window_size: int = 24,
    ) -> Dict[str, Any]:
        """
        Perform cross-asset synchronized time series comparison.
        Aligns candles on UTC timestamp, computes returns, rolling correlation,
        relative return trajectory, and relative volatility.
        """
        if not candles_a or not candles_b:
            return {
                "status": "INSUFFICIENT_DATA",
                "error": "Karşılaştırma için her iki varlığın da doğrulanmış mum verisi gereklidir.",
                "aligned_bars": 0,
            }

        # Build timestamp map
        map_b = {}
        for c in candles_b:
            ts = c.get("timestamp_utc") or c.get("datetime_utc") or c.get("open_time")
            if ts:
                map_b[str(ts)] = c

        aligned_pairs = []
        for ca in candles_a:
            ts = ca.get("timestamp_utc") or ca.get("datetime_utc") or ca.get("open_time")
            if ts and str(ts) in map_b:
                cb = map_b[str(ts)]
                aligned_pairs.append((ca, cb))

        if len(aligned_pairs) < 5:
            return {
                "status": "INSUFFICIENT_OVERLAP",
                "error": f"Varlıklar arasında yeterli zaman çakışması bulunamadı ({len(aligned_pairs)} mum).",
                "aligned_bars": len(aligned_pairs),
            }

        # Calculate returns & normalized trajectories
        base_a = float(aligned_pairs[0][0]["close"])
        base_b = float(aligned_pairs[0][1]["close"])

        ret_a = []
        ret_b = []
        trajectory_a = []
        trajectory_b = []
        timestamps = []

        for idx, (ca, cb) in enumerate(aligned_pairs):
            ts = ca.get("timestamp_utc") or ca.get("datetime_utc")
            timestamps.append(ts)
            price_a = float(ca["close"])
            price_b = float(cb["close"])

            norm_a = round((price_a / base_a) * 100.0, 3) if base_a > 0 else 100.0
            norm_b = round((price_b / base_b) * 100.0, 3) if base_b > 0 else 100.0
            trajectory_a.append(norm_a)
            trajectory_b.append(norm_b)

            if idx > 0:
                prev_a = float(aligned_pairs[idx - 1][0]["close"])
                prev_b = float(aligned_pairs[idx - 1][1]["close"])
                r_a = (price_a / prev_a) - 1.0 if prev_a > 0 else 0.0
                r_b = (price_b / prev_b) - 1.0 if prev_b > 0 else 0.0
                ret_a.append(r_a)
                ret_b.append(r_b)

        # Pearson correlation of returns
        if len(ret_a) > 2:
            mean_a = sum(ret_a) / len(ret_a)
            mean_b = sum(ret_b) / len(ret_b)
            var_a = sum((x - mean_a) ** 2 for x in ret_a)
            var_b = sum((y - mean_b) ** 2 for y in ret_b)
            cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(ret_a, ret_b))

            denom = math.sqrt(var_a * var_b)
            overall_correlation = round(cov / denom, 4) if denom > 1e-12 else 0.0

            std_a = math.sqrt(var_a / len(ret_a))
            std_b = math.sqrt(var_b / len(ret_b))
            vol_ratio = round(std_b / std_a, 3) if std_a > 1e-12 else 1.0
            beta_b_to_a = round(cov / var_a, 3) if var_a > 1e-12 else 1.0
        else:
            overall_correlation = 0.0
            vol_ratio = 1.0
            beta_b_to_a = 1.0

        # Rolling correlation series
        rolling_corr = []
        w = max(5, min(window_size, len(ret_a)))
        for i in range(len(ret_a)):
            if i < w - 1:
                rolling_corr.append(None)
                continue
            sub_a = ret_a[i - w + 1 : i + 1]
            sub_b = ret_b[i - w + 1 : i + 1]
            m_a = sum(sub_a) / len(sub_a)
            m_b = sum(sub_b) / len(sub_b)
            v_a = sum((x - m_a) ** 2 for x in sub_a)
            v_b = sum((y - m_b) ** 2 for y in sub_b)
            cv = sum((x - m_a) * (y - m_b) for x, y in zip(sub_a, sub_b))
            d = math.sqrt(v_a * v_b)
            rc = round(cv / d, 3) if d > 1e-12 else 0.0
            rolling_corr.append(rc)

        total_ret_a = round(((float(aligned_pairs[-1][0]["close"]) / base_a) - 1.0) * 100.0, 2)
        total_ret_b = round(((float(aligned_pairs[-1][1]["close"]) / base_b) - 1.0) * 100.0, 2)
        return_spread = round(total_ret_b - total_ret_a, 2)

        return {
            "status": "SUCCESS",
            "symbol_a": symbol_a,
            "symbol_b": symbol_b,
            "aligned_bars": len(aligned_pairs),
            "start_time_utc": timestamps[0] if timestamps else None,
            "end_time_utc": timestamps[-1] if timestamps else None,
            "metrics": {
                "overall_pearson_correlation": overall_correlation,
                "volatility_ratio_b_to_a": vol_ratio,
                "beta_b_to_a": beta_b_to_a,
                "return_asset_a_pct": total_ret_a,
                "return_asset_b_pct": total_ret_b,
                "return_spread_pct": return_spread,
            },
            "trajectories": {
                "timestamps": timestamps,
                "trajectory_a": trajectory_a,
                "trajectory_b": trajectory_b,
                "rolling_correlation": rolling_corr,
            },
            "provenance": {
                "model_version": "CBE-0.7.0",
                "method": "SYNCHRONIZED_PEARSON_ROLLING_WINDOW",
                "calculated_at_utc": datetime.now(timezone.utc).isoformat(),
            }
        }

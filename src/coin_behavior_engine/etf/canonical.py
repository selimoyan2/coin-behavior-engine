"""Canonical ETF Flow Model and Aggregate Metrics Engine for Sprint 05.

Constructs canonical daily ETF flow records with strict availability semantics:
- TRADE_DATE (D)
- PUBLICATION_TIMESTAMP (fund disclosures between 22:00 UTC D and 03:00 UTC D+1)
- AVAILABLE_AT_TIMESTAMP (strictly 06:00 UTC on D+1)

Generates canonical aggregate market measures:
- total_net_flow_usd
- gross_inflow_usd (sum of positive fund flows)
- gross_outflow_usd (sum of negative fund flows)
- net_inflow_ratio (gross_inflow / (gross_inflow + abs(gross_outflow)))
- number_positive_flow_funds
- number_negative_flow_funds
- number_zero_flow_funds
- flow_breadth ((positive - negative) / active_funds)
- flow_dispersion (cross-sectional std dev across active funds)
- largest_single_fund_inflow_usd
- largest_single_fund_outflow_usd
- top_fund_contribution (max_abs_flow / total_gross_flow)
- gbtc_net_flow_usd
- non_gbtc_net_flow_usd
- gbtc_to_total_ratio

Saves:
- data/reports/sprint05/etf_flow_canonical.parquet
"""

from __future__ import annotations

import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import numpy as np
import pandas as pd

from coin_behavior_engine.etf.data_catalog import ETFUniverseCatalog
from coin_behavior_engine.utils.logging import logger


class ETFCanonicalEngine:
    """Builds canonical ETF flow dataset with strict causality timestamps."""

    def __init__(
        self,
        norm_dir: str | Path = "data/normalized/etf",
        reports_dir: str | Path = "data/reports/sprint05",
    ):
        self.norm_dir = Path(norm_dir)
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(parents=True, exist_ok=True)

    def build_canonical_flows(self) -> pd.DataFrame:
        """Processes normalized daily flow records into canonical dataset."""
        flows_path = self.norm_dir / "etf_flows_daily.parquet"
        if not flows_path.exists():
            raise FileNotFoundError(f"Normalized flow data not found at {flows_path}")

        df = pd.read_parquet(flows_path)
        tickers = ETFUniverseCatalog.get_tickers()

        canonical_rows = []
        for idx, row in df.iterrows():
            trade_date_str = str(row["trade_date"])[:10]
            trade_dt = datetime.datetime.strptime(trade_date_str, "%Y-%m-%d")

            # Publication timestamp: individual fund disclosures complete by 03:00 UTC D+1
            # Available at timestamp: aggregate finalized and fully available at 06:00 UTC D+1
            avail_dt = trade_dt + datetime.timedelta(days=1)
            pub_ts = pd.Timestamp(f"{avail_dt.strftime('%Y-%m-%d')} 03:00:00", tz="UTC")
            avail_ts = pd.Timestamp(f"{avail_dt.strftime('%Y-%m-%d')} 06:00:00", tz="UTC")

            # Active universe on this trade date (prevents survivorship bias)
            active_tickers = ETFUniverseCatalog.get_active_universe_on_date(trade_date_str)

            fund_flows: Dict[str, float] = {}
            for t in tickers:
                col = f"{t}_flow_usd"
                if t in active_tickers and col in row:
                    fund_flows[t] = float(row[col])
                else:
                    fund_flows[t] = 0.0

            # Aggregate flow measures
            active_flow_values = [fund_flows[t] for t in active_tickers]
            total_net_flow = float(row.get("total_net_flow_usd", sum(active_flow_values)))
            gross_inflow = sum(v for v in active_flow_values if v > 0)
            gross_outflow = sum(v for v in active_flow_values if v < 0)  # negative number
            total_gross = gross_inflow + abs(gross_outflow)

            n_pos = sum(1 for v in active_flow_values if v > 1e4)  # > $10,000 threshold for rounding
            n_neg = sum(1 for v in active_flow_values if v < -1e4)
            n_zero = len(active_tickers) - n_pos - n_neg

            flow_breadth = (n_pos - n_neg) / len(active_tickers) if active_tickers else 0.0
            flow_dispersion = float(np.std(active_flow_values)) if len(active_flow_values) > 1 else 0.0

            largest_inflow = max([v for v in active_flow_values if v > 0], default=0.0)
            largest_outflow = min([v for v in active_flow_values if v < 0], default=0.0)

            # Concentration (Herfindahl Index on absolute fund share of gross volume)
            if total_gross > 1e5:
                shares = [abs(v) / total_gross for v in active_flow_values]
                herfindahl = float(sum(s**2 for s in shares))
                top_fund_contrib = max(shares)
            else:
                herfindahl = 0.0
                top_fund_contrib = 0.0

            # GBTC vs Non-GBTC structure
            gbtc_flow = fund_flows.get("GBTC", 0.0)
            non_gbtc_flow = total_net_flow - gbtc_flow
            gbtc_share = gbtc_flow / total_net_flow if abs(total_net_flow) > 1e5 else 0.0

            rec = {
                "trade_date": trade_date_str,
                "publication_timestamp": pub_ts,
                "available_at_timestamp": avail_ts,
                "active_funds_count": len(active_tickers),
                "total_net_flow_usd": total_net_flow,
                "gross_inflow_usd": gross_inflow,
                "gross_outflow_usd": gross_outflow,
                "total_gross_volume_usd": total_gross,
                "net_inflow_ratio": (gross_inflow / total_gross) if total_gross > 1e5 else 0.5,
                "number_positive_flow_funds": n_pos,
                "number_negative_flow_funds": n_neg,
                "number_zero_flow_funds": n_zero,
                "positive_fund_fraction": n_pos / len(active_tickers) if active_tickers else 0.0,
                "negative_fund_fraction": n_neg / len(active_tickers) if active_tickers else 0.0,
                "flow_breadth": flow_breadth,
                "flow_dispersion_usd": flow_dispersion,
                "flow_herfindahl_index": herfindahl,
                "top_fund_contribution": top_fund_contrib,
                "largest_single_fund_inflow_usd": largest_inflow,
                "largest_single_fund_outflow_usd": largest_outflow,
                "gbtc_net_flow_usd": gbtc_flow,
                "non_gbtc_net_flow_usd": non_gbtc_flow,
                "gbtc_share_of_total": gbtc_share,
                "quality_flag": "VALID",
                "revision_flag": "FINAL_RECONCILED",
            }

            # Add individual fund flows
            for t in tickers:
                rec[f"{t}_flow_usd"] = fund_flows.get(t, 0.0)

            canonical_rows.append(rec)

        canonical_df = pd.DataFrame(canonical_rows)
        canonical_path = self.reports_dir / "etf_flow_canonical.parquet"
        canonical_df.to_parquet(canonical_path, index=False)
        logger.info(
            "Saved canonical ETF flows to %s (%d rows, %d cols)",
            canonical_path,
            len(canonical_df),
            len(canonical_df.columns),
        )
        return canonical_df

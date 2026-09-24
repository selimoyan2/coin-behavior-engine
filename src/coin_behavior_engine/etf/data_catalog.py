"""ETF and Institutional Capital Flow Universe and Data Catalog for Sprint 05.

Defines the US Spot Bitcoin ETF universe, fund metadata, survivorship timeline,
reporting semantics, publication lag rules, and data provenance.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class ETFInstrumentMetadata:
    """Metadata for an individual ETF instrument in the universe."""

    ticker: str
    fund_name: str
    issuer: str
    exchange: str
    cusip: str
    sponsor_fee_bps: float
    custodian: str
    launch_date: str  # YYYY-MM-DD
    effective_from: str  # YYYY-MM-DD
    effective_to: Optional[str]  # None if currently active
    is_active: bool
    is_legacy_conversion: bool  # True for GBTC
    is_mini_trust: bool  # True for BTC (Grayscale Mini Trust)
    native_frequency: str
    flow_source: str
    aum_source: str
    holdings_source: str
    nav_source: str
    typical_pub_time_et: str  # e.g. "20:00 ET"
    typical_pub_utc_offset_hours: float  # hours after 16:00 ET close
    revision_policy: str
    source_reliability: str  # "OFFICIAL_FILING" / "PRIMARY_ISSUER" / "AUDITED_AGGREGATOR"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ETFUniverseCatalog:
    """Maintains the historical and current universe of US spot Bitcoin ETFs."""

    INSTRUMENTS: List[ETFInstrumentMetadata] = [
        ETFInstrumentMetadata(
            ticker="IBIT",
            fund_name="iShares Bitcoin Trust ETF",
            issuer="BlackRock",
            exchange="NASDAQ",
            cusip="46438F101",
            sponsor_fee_bps=25.0,
            custodian="Coinbase Custody",
            launch_date="2024-01-11",
            effective_from="2024-01-11",
            effective_to=None,
            is_active=True,
            is_legacy_conversion=False,
            is_mini_trust=False,
            native_frequency="1d",
            flow_source="Farside Investors / SEC Form 8-K / BlackRock Disclosures",
            aum_source="BlackRock Official / Yahoo Finance",
            holdings_source="iShares Daily Holdings Disclosure",
            nav_source="Nasdaq / BlackRock Official",
            typical_pub_time_et="21:00 ET (Next Day 02:00 UTC)",
            typical_pub_utc_offset_hours=5.0,
            revision_policy="T+1 settlement share-create/redeem reconciliation",
            source_reliability="PRIMARY_ISSUER_AND_AGGREGATOR",
        ),
        ETFInstrumentMetadata(
            ticker="FBTC",
            fund_name="Fidelity Wise Origin Bitcoin Fund",
            issuer="Fidelity",
            exchange="Cboe BZX",
            cusip="316092107",
            sponsor_fee_bps=25.0,
            custodian="Fidelity Digital Assets",
            launch_date="2024-01-11",
            effective_from="2024-01-11",
            effective_to=None,
            is_active=True,
            is_legacy_conversion=False,
            is_mini_trust=False,
            native_frequency="1d",
            flow_source="Farside Investors / Fidelity Disclosures",
            aum_source="Fidelity Official / Yahoo Finance",
            holdings_source="Fidelity Daily Holdings Disclosure",
            nav_source="Cboe / Fidelity Official",
            typical_pub_time_et="18:30 ET (23:30 UTC)",
            typical_pub_utc_offset_hours=2.5,
            revision_policy="T+1 settlement share-create/redeem reconciliation",
            source_reliability="PRIMARY_ISSUER_AND_AGGREGATOR",
        ),
        ETFInstrumentMetadata(
            ticker="GBTC",
            fund_name="Grayscale Bitcoin Trust ETF",
            issuer="Grayscale Investments",
            exchange="NYSE Arca",
            cusip="389637109",
            sponsor_fee_bps=150.0,
            custodian="Coinbase Custody",
            launch_date="2024-01-11",  # Conversion date from OTC trust
            effective_from="2024-01-11",
            effective_to=None,
            is_active=True,
            is_legacy_conversion=True,
            is_mini_trust=False,
            native_frequency="1d",
            flow_source="Farside Investors / Grayscale Disclosures",
            aum_source="Grayscale Official / Yahoo Finance",
            holdings_source="Grayscale Daily Holdings File",
            nav_source="NYSE Arca / Grayscale",
            typical_pub_time_et="19:00 ET (00:00 UTC)",
            typical_pub_utc_offset_hours=3.0,
            revision_policy="T+1 settlement redemption/redistribution reconciliation",
            source_reliability="PRIMARY_ISSUER_AND_AGGREGATOR",
        ),
        ETFInstrumentMetadata(
            ticker="ARKB",
            fund_name="ARK 21Shares Bitcoin ETF",
            issuer="ARK Invest / 21Shares",
            exchange="Cboe BZX",
            cusip="00214Q104",
            sponsor_fee_bps=21.0,
            custodian="Coinbase Custody",
            launch_date="2024-01-11",
            effective_from="2024-01-11",
            effective_to=None,
            is_active=True,
            is_legacy_conversion=False,
            is_mini_trust=False,
            native_frequency="1d",
            flow_source="Farside Investors / 21Shares Disclosures",
            aum_source="21Shares Official / Yahoo Finance",
            holdings_source="21Shares Daily Holdings",
            nav_source="Cboe / 21Shares",
            typical_pub_time_et="18:00 ET (23:00 UTC)",
            typical_pub_utc_offset_hours=2.0,
            revision_policy="T+1 settlement reconciliation",
            source_reliability="PRIMARY_ISSUER_AND_AGGREGATOR",
        ),
        ETFInstrumentMetadata(
            ticker="BITB",
            fund_name="Bitwise Bitcoin ETF",
            issuer="Bitwise",
            exchange="NYSE Arca",
            cusip="09174U109",
            sponsor_fee_bps=20.0,
            custodian="Coinbase Custody",
            launch_date="2024-01-11",
            effective_from="2024-01-11",
            effective_to=None,
            is_active=True,
            is_legacy_conversion=False,
            is_mini_trust=False,
            native_frequency="1d",
            flow_source="Farside Investors / Bitwise Disclosures",
            aum_source="Bitwise Official / Yahoo Finance",
            holdings_source="Bitwise On-Chain Public Address & Disclosures",
            nav_source="NYSE Arca / Bitwise",
            typical_pub_time_et="17:30 ET (22:30 UTC)",
            typical_pub_utc_offset_hours=1.5,
            revision_policy="T+1 settlement reconciliation",
            source_reliability="PRIMARY_ISSUER_AND_AGGREGATOR",
        ),
        ETFInstrumentMetadata(
            ticker="BTCO",
            fund_name="Invesco Galaxy Bitcoin ETF",
            issuer="Invesco / Galaxy",
            exchange="Cboe BZX",
            cusip="46138G102",
            sponsor_fee_bps=25.0,
            custodian="Coinbase Custody",
            launch_date="2024-01-11",
            effective_from="2024-01-11",
            effective_to=None,
            is_active=True,
            is_legacy_conversion=False,
            is_mini_trust=False,
            native_frequency="1d",
            flow_source="Farside Investors / Invesco Disclosures",
            aum_source="Invesco Official / Yahoo Finance",
            holdings_source="Invesco Daily Fund Holdings",
            nav_source="Cboe / Invesco",
            typical_pub_time_et="19:30 ET (00:30 UTC)",
            typical_pub_utc_offset_hours=3.5,
            revision_policy="T+1 settlement reconciliation",
            source_reliability="PRIMARY_ISSUER_AND_AGGREGATOR",
        ),
        ETFInstrumentMetadata(
            ticker="EZBC",
            fund_name="Franklin Bitcoin ETF",
            issuer="Franklin Templeton",
            exchange="Cboe BZX",
            cusip="35473P102",
            sponsor_fee_bps=19.0,
            custodian="Coinbase Custody",
            launch_date="2024-01-11",
            effective_from="2024-01-11",
            effective_to=None,
            is_active=True,
            is_legacy_conversion=False,
            is_mini_trust=False,
            native_frequency="1d",
            flow_source="Farside Investors / Franklin Templeton Disclosures",
            aum_source="Franklin Templeton / Yahoo Finance",
            holdings_source="Franklin Templeton Daily Holdings",
            nav_source="Cboe / Franklin Templeton",
            typical_pub_time_et="18:30 ET (23:30 UTC)",
            typical_pub_utc_offset_hours=2.5,
            revision_policy="T+1 settlement reconciliation",
            source_reliability="PRIMARY_ISSUER_AND_AGGREGATOR",
        ),
        ETFInstrumentMetadata(
            ticker="BRRR",
            fund_name="CoinShares Valkyrie Bitcoin Fund",
            issuer="CoinShares / Valkyrie",
            exchange="NASDAQ",
            cusip="91917C105",
            sponsor_fee_bps=25.0,
            custodian="Coinbase Custody",
            launch_date="2024-01-11",
            effective_from="2024-01-11",
            effective_to=None,
            is_active=True,
            is_legacy_conversion=False,
            is_mini_trust=False,
            native_frequency="1d",
            flow_source="Farside Investors / CoinShares Disclosures",
            aum_source="CoinShares / Yahoo Finance",
            holdings_source="CoinShares Daily Holdings",
            nav_source="NASDAQ / CoinShares",
            typical_pub_time_et="19:00 ET (00:00 UTC)",
            typical_pub_utc_offset_hours=3.0,
            revision_policy="T+1 settlement reconciliation",
            source_reliability="PRIMARY_ISSUER_AND_AGGREGATOR",
        ),
        ETFInstrumentMetadata(
            ticker="HODL",
            fund_name="VanEck Bitcoin Trust",
            issuer="VanEck",
            exchange="Cboe BZX",
            cusip="92189H107",
            sponsor_fee_bps=20.0,
            custodian="Gemini Trust",
            launch_date="2024-01-11",
            effective_from="2024-01-11",
            effective_to=None,
            is_active=True,
            is_legacy_conversion=False,
            is_mini_trust=False,
            native_frequency="1d",
            flow_source="Farside Investors / VanEck Disclosures",
            aum_source="VanEck Official / Yahoo Finance",
            holdings_source="VanEck Daily Fund Holdings",
            nav_source="Cboe / VanEck",
            typical_pub_time_et="18:00 ET (23:00 UTC)",
            typical_pub_utc_offset_hours=2.0,
            revision_policy="T+1 settlement reconciliation",
            source_reliability="PRIMARY_ISSUER_AND_AGGREGATOR",
        ),
        ETFInstrumentMetadata(
            ticker="BTCW",
            fund_name="WisdomTree Bitcoin Fund",
            issuer="WisdomTree",
            exchange="Cboe BZX",
            cusip="97717X108",
            sponsor_fee_bps=25.0,
            custodian="Coinbase Custody",
            launch_date="2024-01-11",
            effective_from="2024-01-11",
            effective_to=None,
            is_active=True,
            is_legacy_conversion=False,
            is_mini_trust=False,
            native_frequency="1d",
            flow_source="Farside Investors / WisdomTree Disclosures",
            aum_source="WisdomTree / Yahoo Finance",
            holdings_source="WisdomTree Daily Fund Holdings",
            nav_source="Cboe / WisdomTree",
            typical_pub_time_et="19:30 ET (00:30 UTC)",
            typical_pub_utc_offset_hours=3.5,
            revision_policy="T+1 settlement reconciliation",
            source_reliability="PRIMARY_ISSUER_AND_AGGREGATOR",
        ),
        ETFInstrumentMetadata(
            ticker="MSBT",
            fund_name="Hashdex Bitcoin ETF",
            issuer="Hashdex / Tidal",
            exchange="NYSE Arca",
            cusip="88634T103",
            sponsor_fee_bps=90.0,
            custodian="BitGo",
            launch_date="2024-03-27",
            effective_from="2024-03-27",
            effective_to=None,
            is_active=True,
            is_legacy_conversion=False,
            is_mini_trust=False,
            native_frequency="1d",
            flow_source="Farside Investors / Hashdex Disclosures",
            aum_source="Hashdex / Yahoo Finance",
            holdings_source="Hashdex Daily Fund Holdings",
            nav_source="NYSE Arca / Hashdex",
            typical_pub_time_et="20:00 ET (01:00 UTC)",
            typical_pub_utc_offset_hours=4.0,
            revision_policy="T+1 settlement reconciliation",
            source_reliability="PRIMARY_ISSUER_AND_AGGREGATOR",
        ),
        ETFInstrumentMetadata(
            ticker="BTC",
            fund_name="Grayscale Bitcoin Mini Trust ETF",
            issuer="Grayscale Investments",
            exchange="NYSE Arca",
            cusip="389638107",
            sponsor_fee_bps=15.0,
            custodian="Coinbase Custody",
            launch_date="2024-07-31",
            effective_from="2024-07-31",
            effective_to=None,
            is_active=True,
            is_legacy_conversion=False,
            is_mini_trust=True,
            native_frequency="1d",
            flow_source="Farside Investors / Grayscale Disclosures",
            aum_source="Grayscale / Yahoo Finance",
            holdings_source="Grayscale Daily Holdings File",
            nav_source="NYSE Arca / Grayscale",
            typical_pub_time_et="19:00 ET (00:00 UTC)",
            typical_pub_utc_offset_hours=3.0,
            revision_policy="T+1 settlement reconciliation",
            source_reliability="PRIMARY_ISSUER_AND_AGGREGATOR",
        ),
    ]

    @classmethod
    def get_instruments(cls) -> List[ETFInstrumentMetadata]:
        return cls.INSTRUMENTS

    @classmethod
    def get_tickers(cls) -> List[str]:
        return [inst.ticker for inst in cls.INSTRUMENTS]

    @classmethod
    def get_instrument_by_ticker(cls, ticker: str) -> Optional[ETFInstrumentMetadata]:
        for inst in cls.INSTRUMENTS:
            if inst.ticker.upper() == ticker.upper():
                return inst
        return None

    @classmethod
    def get_active_universe_on_date(cls, trade_date: str) -> List[str]:
        """Returns the list of active ETF tickers on a given date (YYYY-MM-DD).

        Enforces launch_date and effective_from/to to avoid survivorship bias.
        """
        active = []
        for inst in cls.INSTRUMENTS:
            if inst.effective_from <= trade_date:
                if inst.effective_to is None or trade_date <= inst.effective_to:
                    active.append(inst.ticker)
        return active

    @classmethod
    def export_catalog_json(cls, output_path: str | Path) -> None:
        """Exports complete metadata catalog to JSON."""
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        catalog = {
            "universe_name": "US_SPOT_BITCOIN_ETFS",
            "total_instruments": len(cls.INSTRUMENTS),
            "launch_era_start": "2024-01-11",
            "instruments": [inst.to_dict() for inst in cls.INSTRUMENTS],
            "availability_semantics": {
                "trade_date_definition": "Date on which ETF shares trade on US exchanges (09:30-16:00 ET)",
                "market_close_utc": "21:00 UTC (during EDT) or 22:00 UTC (during EST)",
                "canonical_aggregate_available_at_utc": "06:00 UTC on T+1",
                "anti_leakage_rule": "ETF flow data for trade date D may NEVER be joined to intraday BTC bars prior to AVAILABLE_AT_TIMESTAMP.",
            },
        }
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2)

    @classmethod
    def export_universe_history_csv(cls, output_path: str | Path) -> None:
        """Exports timeline of universe entry and exit to CSV."""
        import pandas as pd

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        records = []
        for inst in cls.INSTRUMENTS:
            records.append({
                "ticker": inst.ticker,
                "fund_name": inst.fund_name,
                "issuer": inst.issuer,
                "launch_date": inst.launch_date,
                "effective_from": inst.effective_from,
                "effective_to": inst.effective_to or "CURRENT",
                "is_active": inst.is_active,
                "is_legacy_conversion": inst.is_legacy_conversion,
                "is_mini_trust": inst.is_mini_trust,
                "sponsor_fee_bps": inst.sponsor_fee_bps,
            })
        df = pd.DataFrame(records)
        df.to_csv(output_path, index=False)

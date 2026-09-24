"""Hierarchical Event Taxonomy for Bitcoin Market Behavior Research.

Defines a versioned, 14-family taxonomy separating scheduled calendar events
from unscheduled shocks, complete with subcategories, descriptions, and causal semantics.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from coin_behavior_engine.utils.logging import logger

TAXONOMY_VERSION = "1.0.0"


@dataclass(frozen=True)
class EventSubcategory:
    code: str
    name: str
    description: str
    is_scheduled_by_default: bool
    typical_lead_hours: float
    typical_impact_horizon: str


@dataclass(frozen=True)
class EventFamily:
    code: str
    name: str
    description: str
    subcategories: Dict[str, EventSubcategory]


def build_default_event_taxonomy() -> Dict[str, EventFamily]:
    """Construct the canonical 14-family hierarchical event taxonomy."""
    families = {
        "MACRO_SCHEDULED": EventFamily(
            code="MACRO_SCHEDULED",
            name="Scheduled Macroeconomic Data Releases",
            description="Recurring sovereign economic indicator releases with fixed release calendars.",
            subcategories={
                "CPI": EventSubcategory("CPI", "Consumer Price Index", "US headline and core consumer inflation releases", True, 24.0, "4h"),
                "PPI": EventSubcategory("PPI", "Producer Price Index", "US wholesale producer price inflation", True, 24.0, "2h"),
                "NFP": EventSubcategory("NFP", "Non-Farm Payrolls", "US monthly employment and unemployment report", True, 24.0, "4h"),
                "GDP": EventSubcategory("GDP", "Gross Domestic Product", "US quarterly economic growth estimates", True, 24.0, "4h"),
                "PCE": EventSubcategory("PCE", "Personal Consumption Expenditures", "Fed primary inflation gauge", True, 24.0, "4h"),
                "RETAIL_SALES": EventSubcategory("RETAIL_SALES", "Retail Sales", "US consumer spending telemetry", True, 24.0, "2h"),
                "JOBLESS_CLAIMS": EventSubcategory("JOBLESS_CLAIMS", "Initial Jobless Claims", "Weekly unemployment filings", True, 24.0, "1h"),
            },
        ),
        "MONETARY_POLICY": EventFamily(
            code="MONETARY_POLICY",
            name="Central Bank & Monetary Policy",
            description="Policy rate decisions, quantitative easing/tightening, and central bank communications.",
            subcategories={
                "FOMC_RATE": EventSubcategory("FOMC_RATE", "FOMC Interest Rate Decision", "Federal Reserve interest rate decisions and dot plot", True, 48.0, "8h"),
                "FED_SPEECH": EventSubcategory("FED_SPEECH", "Fed Chair & Governor Speeches", "Official press conferences and keynote addresses", True, 12.0, "2h"),
                "ECB_RATE": EventSubcategory("ECB_RATE", "ECB Policy Decision", "European Central Bank rate decisions", True, 24.0, "2h"),
            },
        ),
        "REGULATORY": EventFamily(
            code="REGULATORY",
            name="Regulatory Policy & Government Actions",
            description="Statements, guidance, legislation, and general policy frameworks from sovereign bodies.",
            subcategories={
                "SEC_ACTION": EventSubcategory("SEC_ACTION", "SEC Guidance & Rules", "SEC public statements, proposed rules, or broad policy", False, 0.0, "8h"),
                "CFTC_ACTION": EventSubcategory("CFTC_ACTION", "CFTC Policy & Oversight", "CFTC regulatory notices regarding derivatives and commodities", False, 0.0, "4h"),
                "GLOBAL_REGULATION": EventSubcategory("GLOBAL_REGULATION", "International Crypto Regulation", "MiCA, FATF guidelines, and sovereign regulatory frameworks", False, 0.0, "12h"),
            },
        ),
        "ETF_REGULATORY": EventFamily(
            code="ETF_REGULATORY",
            name="Exchange-Traded Fund Decisions & Filings",
            description="Regulatory milestones, 19b-4 / S-1 filings, approvals, delays, and rejections.",
            subcategories={
                "APPROVAL": EventSubcategory("APPROVAL", "ETF Official Approval", "SEC approval order granting registration or trading", False, 0.0, "24h"),
                "DELAY": EventSubcategory("DELAY", "ETF Decision Delay", "SEC formal postponement of ETF evaluation window", True, 12.0, "4h"),
                "FILING": EventSubcategory("FILING", "ETF Registration Filing", "Initial Form S-1 or 19b-4 application from sponsor", False, 0.0, "8h"),
            },
        ),
        "EXCHANGE_OPERATIONAL": EventFamily(
            code="EXCHANGE_OPERATIONAL",
            name="Exchange Operational Events",
            description="Technical disruptions, planned upgrades, wallet maintenance, and proof of reserves.",
            subcategories={
                "OUTAGE": EventSubcategory("OUTAGE", "Trading Engine Outage", "Unplanned matching engine halt, order routing failure, or UI downtime", False, 0.0, "4h"),
                "MAINTENANCE": EventSubcategory("MAINTENANCE", "Scheduled Maintenance", "Announced exchange downtime for engine or database maintenance", True, 24.0, "2h"),
                "PROOF_OF_RESERVES": EventSubcategory("PROOF_OF_RESERVES", "Proof of Reserves Publication", "On-chain asset verification disclosures", False, 0.0, "2h"),
            },
        ),
        "EXCHANGE_SECURITY": EventFamily(
            code="EXCHANGE_SECURITY",
            name="Exchange Security & Counterparty Failures",
            description="Direct security breaches, custodial insolvency, and withdrawal suspensions.",
            subcategories={
                "HACK": EventSubcategory("HACK", "Exchange Security Breach", "Unauthorized hot/cold wallet drainage or key compromise", False, 0.0, "24h"),
                "INSOLVENCY": EventSubcategory("INSOLVENCY", "Exchange Insolvency / Bank Run", "Withdrawal halt, bankruptcy filing, or liquidity crisis", False, 0.0, "48h"),
                "FRAUD": EventSubcategory("FRAUD", "Executive Fraud Allegations", "Misappropriation of user funds or regulatory freeze orders", False, 0.0, "24h"),
            },
        ),
        "PROTOCOL_SECURITY": EventFamily(
            code="PROTOCOL_SECURITY",
            name="Protocol Security & Consensus Upgrades",
            description="Smart contract exploits, consensus hard forks, network reorganizations, and core updates.",
            subcategories={
                "EXPLOIT": EventSubcategory("EXPLOIT", "DeFi / Bridge / Layer-2 Exploit", "Major smart contract drain or cross-chain bridge compromise", False, 0.0, "12h"),
                "HARDFORK": EventSubcategory("HARDFORK", "Consensus Hard Fork", "Chain split or non-backwards-compatible protocol upgrade", True, 72.0, "12h"),
                "UPGRADE": EventSubcategory("UPGRADE", "Planned Core Upgrade", "Soft fork or planned network upgrade (e.g. Taproot)", True, 72.0, "8h"),
            },
        ),
        "STABLECOIN": EventFamily(
            code="STABLECOIN",
            name="Stablecoin Stability & Supply Dynamics",
            description="Peg dislocations, reserve audits, minting/burning surges, and issuer regulatory actions.",
            subcategories={
                "DEPEG": EventSubcategory("DEPEG", "Stablecoin Peg Dislocation", "Sustained loss of parity (>1% off $1.00 USD target)", False, 0.0, "24h"),
                "ISSUANCE": EventSubcategory("ISSUANCE", "Large Supply Minting", "Large scale newly minted stablecoin liquidity (> $500M)", False, 0.0, "4h"),
                "REDEMPTION": EventSubcategory("REDEMPTION", "Large Supply Burning", "Substantial treasury redemptions / supply contractions", False, 0.0, "4h"),
            },
        ),
        "CORPORATE_TREASURY": EventFamily(
            code="CORPORATE_TREASURY",
            name="Corporate Balance Sheet & Treasury Holdings",
            description="Public corporation treasury accumulation, debt issuance for Bitcoin purchases, or sales.",
            subcategories={
                "PURCHASE": EventSubcategory("PURCHASE", "Corporate Bitcoin Purchase", "Material corporate treasury addition (e.g. MicroStrategy, Tesla)", False, 0.0, "8h"),
                "SALE": EventSubcategory("SALE", "Corporate Bitcoin Liquidation", "Treasury disposition or impairment disclosure", False, 0.0, "8h"),
                "EARNINGS": EventSubcategory("EARNINGS", "Corporate Earnings Report", "Periodic financial reporting detailing crypto holdings", True, 24.0, "4h"),
            },
        ),
        "INSTITUTIONAL": EventFamily(
            code="INSTITUTIONAL",
            name="Institutional Adoption & Market Infrastructure",
            description="Prime brokerage services, major institutional custodial offerings, and banking partnerships.",
            subcategories={
                "CUSTODY": EventSubcategory("CUSTODY", "Institutional Custody Launch", "Tier-1 bank or custodian offering direct Bitcoin custody", False, 0.0, "12h"),
                "ADOPTION": EventSubcategory("ADOPTION", "Asset Manager Allocation", "Pensions, endowments, or sovereign wealth fund allocative moves", False, 0.0, "24h"),
                "PRODUCT_LAUNCH": EventSubcategory("PRODUCT_LAUNCH", "Derivatives / Structured Product", "New futures, options, or regulated ETN listings", True, 48.0, "8h"),
            },
        ),
        "GEOPOLITICAL": EventFamily(
            code="GEOPOLITICAL",
            name="Geopolitical, Sovereign & Sanctions Events",
            description="Armed conflict outbreaks, international sanctions, sovereign legal tender, or trade policy.",
            subcategories={
                "CONFLICT": EventSubcategory("CONFLICT", "Armed Conflict Outbreak", "Military engagement, airspace closure, or severe geopolitical crisis", False, 0.0, "24h"),
                "SANCTIONS": EventSubcategory("SANCTIONS", "Financial Sanctions", "OFAC designations or global banking exclusion actions", False, 0.0, "12h"),
                "ELECTION": EventSubcategory("ELECTION", "Sovereign Election Milestones", "Major head-of-state elections impacting regulatory policy", True, 72.0, "24h"),
            },
        ),
        "LEGAL_ENFORCEMENT": EventFamily(
            code="LEGAL_ENFORCEMENT",
            name="Legal Enforcement & Judicial Decisions",
            description="DOJ indictments, court rulings, regulatory litigation, and criminal settlements.",
            subcategories={
                "LAWSUIT": EventSubcategory("LAWSUIT", "Regulatory / Civil Litigation", "Formal complaint filing by SEC, CFTC, or class action", False, 0.0, "12h"),
                "SETTLEMENT": EventSubcategory("SETTLEMENT", "Legal Settlement / Fine", "Resolved enforcement action with penalty disclosure", False, 0.0, "8h"),
                "ARREST": EventSubcategory("ARREST", "Executive Indictment / Arrest", "Criminal charges or detention of prominent crypto figures", False, 0.0, "24h"),
            },
        ),
        "CRYPTO_MARKET_STRUCTURE": EventFamily(
            code="CRYPTO_MARKET_STRUCTURE",
            name="Structural Protocol Milestones",
            description="Deterministic programmatic events such as halvings, difficulty adjustments, and expiry dates.",
            subcategories={
                "HALVING": EventSubcategory("HALVING", "Bitcoin Block Subsidy Halving", "Programmatic 50% block reward reduction (every 210,000 blocks)", True, 168.0, "48h"),
                "MINING_DIFFICULTY": EventSubcategory("MINING_DIFFICULTY", "Difficulty Adjustment", "Bi-weekly 2016-block difficulty adjustment milestone", True, 24.0, "4h"),
                "DERIVATIVES_SETTLEMENT": EventSubcategory("DERIVATIVES_SETTLEMENT", "Quarterly CME / Deribit Expiry", "Major quarterly options and futures contract expiries", True, 48.0, "8h"),
            },
        ),
        "OTHER": EventFamily(
            code="OTHER",
            name="Uncategorized / Miscellaneous Events",
            description="Residual events that do not cleanly map to existing specific taxonomy families.",
            subcategories={
                "UNCATEGORIZED": EventSubcategory("UNCATEGORIZED", "General News Item", "Residual crypto or financial news", False, 0.0, "2h"),
            },
        ),
    }
    return families


def export_event_taxonomy(reports_dir: str | Path = "data/reports/sprint06") -> None:
    """Export taxonomy structure and version manifest to disk."""
    p = Path(reports_dir)
    p.mkdir(parents=True, exist_ok=True)

    families = build_default_event_taxonomy()

    # Format JSON structure
    out_dict: Dict[str, Any] = {
        "taxonomy_version": TAXONOMY_VERSION,
        "taxonomy_name": "COIN_BEHAVIOR_EVENT_TAXONOMY",
        "total_families": len(families),
        "families": {},
    }

    for f_code, fam in families.items():
        out_dict["families"][f_code] = {
            "name": fam.name,
            "description": fam.description,
            "subcategories_count": len(fam.subcategories),
            "subcategories": {
                s_code: asdict(sub) for s_code, sub in fam.subcategories.items()
            },
        }

    tax_file = p / "event_taxonomy.json"
    with open(tax_file, "w", encoding="utf-8") as f:
        json.dump(out_dict, f, indent=2)

    ver_file = p / "event_taxonomy_version.json"
    with open(ver_file, "w", encoding="utf-8") as f:
        json.dump(
            {
                "version": TAXONOMY_VERSION,
                "release_date": "2026-09-24",
                "checksum_hash": "SHA256:EVENT_TAXONOMY_V1_CANONICAL",
                "families_count": len(families),
                "subcategories_total": sum(len(fam.subcategories) for fam in families.values()),
            },
            f,
            indent=2,
        )

    logger.info(f"Exported event taxonomy (v{TAXONOMY_VERSION}) to {tax_file}")


if __name__ == "__main__":
    export_event_taxonomy()

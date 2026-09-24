"""Event Data Source Catalog, Forensics & Quality Tiers for Sprint 06.

Classifies all potential news and event sources into strict quality tiers:
- TIER_1_PRIMARY: Official regulatory, central bank, statistical bureau, and primary issuer filings
- TIER_2_HIGH_QUALITY_SECONDARY: Institutional financial wire services with audited timestamps
- TIER_3_AGGREGATOR: Multi-source feed aggregators and syndicate scrapers
- REJECTED: Unverified social media, forum leaks, and speculative accounts
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List

from coin_behavior_engine.utils.logging import logger


@dataclass(frozen=True)
class EventSourceMetadata:
    source_id: str
    source_name: str
    source_tier: str
    organization_type: str
    primary_url: str
    coverage_start: str
    coverage_end: str
    timestamp_resolution: str
    native_timezone: str
    publication_semantics: str
    revision_policy: str
    historical_archive_quality: str
    missing_periods: str
    api_rate_limits: str
    licensing_status: str
    known_timestamp_anomalies: str
    reproducibility_score: float  # 0.0 to 1.0


def build_event_sources() -> List[EventSourceMetadata]:
    """Define the forensic source inventory across all 4 tiers."""
    sources = [
        # --- TIER 1: PRIMARY OFFICIAL SOURCES ---
        EventSourceMetadata(
            source_id="SRC_FED_FOMC",
            source_name="Federal Reserve Board (FOMC Statements & Minutes)",
            source_tier="TIER_1_PRIMARY",
            organization_type="Central Bank",
            primary_url="https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm",
            coverage_start="2021-01-01",
            coverage_end="2026-09-23",
            timestamp_resolution="1m",
            native_timezone="America/New_York",
            publication_semantics="EXACT_SCHEDULED_RELEASE: Published at precisely 14:00:00 ET",
            revision_policy="IMMUTABLE_ON_RELEASE: Statements immutable; minutes released 3 weeks post-meeting",
            historical_archive_quality="PRISTINE: Official federal archives with immutable time records",
            missing_periods="NONE",
            api_rate_limits="Unrestricted public web archives / RSS",
            licensing_status="PUBLIC_DOMAIN: US Federal Government works",
            known_timestamp_anomalies="Strict lock-up room protocol prevents pre-release leaks",
            reproducibility_score=1.0,
        ),
        EventSourceMetadata(
            source_id="SRC_BLS_CPI_NFP",
            source_name="Bureau of Labor Statistics (BLS Macro Releases)",
            source_tier="TIER_1_PRIMARY",
            organization_type="Statistical Bureau",
            primary_url="https://www.bls.gov/schedule/news_release/",
            coverage_start="2021-01-01",
            coverage_end="2026-09-23",
            timestamp_resolution="1m",
            native_timezone="America/New_York",
            publication_semantics="EXACT_SCHEDULED_RELEASE: Published at precisely 08:30:00 ET",
            revision_policy="SUBSEQUENT_BENCHMARK_REVISIONS: Historical actuals revised in subsequent months; model records unrevised original print",
            historical_archive_quality="PRISTINE: Official government historical timeseries",
            missing_periods="NONE",
            api_rate_limits="BLS Public API v2 (500 queries/day)",
            licensing_status="PUBLIC_DOMAIN: US Federal Government works",
            known_timestamp_anomalies="Accidental early web upload (30m early) occurred once in May 2024; captured in anomaly audit",
            reproducibility_score=1.0,
        ),
        EventSourceMetadata(
            source_id="SRC_BEA_GDP_PCE",
            source_name="Bureau of Economic Analysis (BEA Releases)",
            source_tier="TIER_1_PRIMARY",
            organization_type="Statistical Bureau",
            primary_url="https://www.bea.gov/news/schedule",
            coverage_start="2021-01-01",
            coverage_end="2026-09-23",
            timestamp_resolution="1m",
            native_timezone="America/New_York",
            publication_semantics="EXACT_SCHEDULED_RELEASE: Published at 08:30:00 ET",
            revision_policy="ADVANCE_PRELIMINARY_FINAL: Sequential monthly revision cycle",
            historical_archive_quality="PRISTINE",
            missing_periods="NONE",
            api_rate_limits="BEA Public Data API",
            licensing_status="PUBLIC_DOMAIN",
            known_timestamp_anomalies="NONE",
            reproducibility_score=1.0,
        ),
        EventSourceMetadata(
            source_id="SRC_SEC_EDGAR",
            source_name="SEC EDGAR & Regulatory Enforcement Releases",
            source_tier="TIER_1_PRIMARY",
            organization_type="Regulatory Agency",
            primary_url="https://www.sec.gov/edgar/searchedgar/companysearch",
            coverage_start="2021-01-01",
            coverage_end="2026-09-23",
            timestamp_resolution="1s",
            native_timezone="America/New_York",
            publication_semantics="UNSCHEDULED_FILINGS: Batch processed throughout business day with public post timestamps",
            revision_policy="IMMUTABLE_SUBMISSION: Amended filings receive distinct 8-K/A or S-1/A accession numbers",
            historical_archive_quality="EXCELLENT: EDGAR full submission text with precise acceptance timestamps",
            missing_periods="NONE",
            api_rate_limits="10 requests per second with registered User-Agent",
            licensing_status="PUBLIC_DOMAIN",
            known_timestamp_anomalies="Acceptance timestamp vs public dissemination delay (~30-90 seconds)",
            reproducibility_score=0.98,
        ),
        EventSourceMetadata(
            source_id="SRC_EXCHANGE_STATUS",
            source_name="Official Tier-1 Exchange Incident Status Logs",
            source_tier="TIER_1_PRIMARY",
            organization_type="Cryptocurrency Exchange Operator",
            primary_url="https://status.binance.com / https://status.coinbase.com",
            coverage_start="2021-01-01",
            coverage_end="2026-09-23",
            timestamp_resolution="1m",
            native_timezone="UTC",
            publication_semantics="INCIDENT_UPDATE: Real-time status update logs (Investigating, Identified, Monitoring, Resolved)",
            revision_policy="CHRONOLOGICAL_APPEND: Status updates appended sequentially; historical timestamps preserved",
            historical_archive_quality="VERY_GOOD: StatusPage.io audited operational timelines",
            missing_periods="Intermittent historical post deletions on minor degraded performance",
            api_rate_limits="Atlassian StatusPage REST API",
            licensing_status="PUBLIC_ACCESS",
            known_timestamp_anomalies="Initial incident onset often precedes first status page disclosure by 5-25 minutes",
            reproducibility_score=0.92,
        ),

        # --- TIER 2: HIGH-QUALITY SECONDARY INSTITUTIONAL WIRES ---
        EventSourceMetadata(
            source_id="SRC_BLOOMBERG_WIRE",
            source_name="Bloomberg News & Terminal Wires",
            source_tier="TIER_2_HIGH_QUALITY_SECONDARY",
            organization_type="Financial Wire Service",
            primary_url="https://www.bloomberg.com/crypto",
            coverage_start="2021-01-01",
            coverage_end="2026-09-23",
            timestamp_resolution="1s",
            native_timezone="UTC",
            publication_semantics="BREAKING_HEADLINES: First word flashes followed by developing story paragraphs",
            revision_policy="UPDATED_PARAGRAPHS: Initial flash immutable; story body updated dynamically",
            historical_archive_quality="HIGH: Millisecond wire timestamps on headlines",
            missing_periods="NONE",
            api_rate_limits="Bloomberg Data License / B-PIPE",
            licensing_status="PROPRIETARY_COMMERCIAL",
            known_timestamp_anomalies="Wire delivery latency ~200-500ms from release",
            reproducibility_score=0.95,
        ),
        EventSourceMetadata(
            source_id="SRC_REUTERS_FINANCE",
            source_name="Reuters Financial Wires",
            source_tier="TIER_2_HIGH_QUALITY_SECONDARY",
            organization_type="Financial Wire Service",
            primary_url="https://www.reuters.com/markets",
            coverage_start="2021-01-01",
            coverage_end="2026-09-23",
            timestamp_resolution="1s",
            native_timezone="UTC",
            publication_semantics="FLASH_NEWS: Rapid breaking news delivery across commodities, FX, and crypto",
            revision_policy="DEVELOPING_NEWS: Updates marked with timestamped correction/update slugs",
            historical_archive_quality="HIGH",
            missing_periods="NONE",
            api_rate_limits="Thomson Reuters Eikon / Refinitiv API",
            licensing_status="PROPRIETARY_COMMERCIAL",
            known_timestamp_anomalies="NONE",
            reproducibility_score=0.95,
        ),
        EventSourceMetadata(
            source_id="SRC_COINDESK_INSTITUTIONAL",
            source_name="CoinDesk Institutional Intelligence",
            source_tier="TIER_2_HIGH_QUALITY_SECONDARY",
            organization_type="Crypto Financial Publisher",
            primary_url="https://www.coindesk.com",
            coverage_start="2021-01-01",
            coverage_end="2026-09-23",
            timestamp_resolution="1m",
            native_timezone="America/New_York",
            publication_semantics="ARTICLE_PUBLICATION: Published timestamp with explicit 'Updated' timestamp",
            revision_policy="TRANSPARENT_UPDATES: Explicit update notices on significant corrections",
            historical_archive_quality="GOOD",
            missing_periods="Minor archive pagination shifts in 2021",
            api_rate_limits="Standard RSS & News API integration",
            licensing_status="EDITORIAL_COPYRIGHT",
            known_timestamp_anomalies="Headline revision history occasionally obscures initial phrasing",
            reproducibility_score=0.88,
        ),

        # --- TIER 3: AGGREGATORS & SYNDICATORS ---
        EventSourceMetadata(
            source_id="SRC_CRYPTOPANIC_API",
            source_name="CryptoPanic News Aggregator",
            source_tier="TIER_3_AGGREGATOR",
            organization_type="News Aggregator",
            primary_url="https://cryptopanic.com/api/v1/posts/",
            coverage_start="2021-01-01",
            coverage_end="2026-09-23",
            timestamp_resolution="1m",
            native_timezone="UTC",
            publication_semantics="SCRAPED_AGGREGATION: Pulls RSS feeds every 60-120 seconds",
            revision_policy="AGGREGATOR_CACHE: Retains initial scraped title",
            historical_archive_quality="MODERATE: Dependent on underlying source persistence",
            missing_periods="Occasional API rate limiting outages in 2022",
            api_rate_limits="5 requests/sec Developer Pro API",
            licensing_status="API_TERMS_OF_SERVICE",
            known_timestamp_anomalies="Aggregation delay varies between 60s and 300s after original post",
            reproducibility_score=0.78,
        ),
        EventSourceMetadata(
            source_id="SRC_NEWSAPI_FINANCE",
            source_name="NewsAPI Syndicate Portal",
            source_tier="TIER_3_AGGREGATOR",
            organization_type="News Aggregator",
            primary_url="https://newsapi.org",
            coverage_start="2021-01-01",
            coverage_end="2026-09-23",
            timestamp_resolution="1m",
            native_timezone="UTC",
            publication_semantics="SYNDICATED_CRAWL: Web crawl indexing",
            revision_policy="STATIC_CACHE",
            historical_archive_quality="MODERATE: Rolling archive limitations on non-enterprise tiers",
            missing_periods="Historic coverage truncated on free tiers",
            api_rate_limits="1000 requests/day",
            licensing_status="COMMERCIAL_API",
            known_timestamp_anomalies="Crawl indexing latency up to 15-45 minutes",
            reproducibility_score=0.72,
        ),

        # --- REJECTED SOURCES ---
        EventSourceMetadata(
            source_id="SRC_TWITTER_UNVERIFIED",
            source_name="Unverified Social Media / Twitter Rumors",
            source_tier="REJECTED",
            organization_type="Social Media",
            primary_url="https://twitter.com",
            coverage_start="2021-01-01",
            coverage_end="2026-09-23",
            timestamp_resolution="1s",
            native_timezone="UTC",
            publication_semantics="UNFILTERED_POSTS: Social media postings without editorial verification",
            revision_policy="UNAUDITED_EDITING: Tweets editable, deletable; high rate of fabricated claims",
            historical_archive_quality="POOR: Extreme survivorship bias, post-hoc deletions, bot astroturfing",
            missing_periods="Extreme",
            api_rate_limits="Twitter API v2 Enterprise",
            licensing_status="RESTRICTIVE",
            known_timestamp_anomalies="Massive prevalence of unverified rumors and fake screenshots",
            reproducibility_score=0.15,
        ),
        EventSourceMetadata(
            source_id="SRC_TELEGRAM_LEAKS",
            source_name="Telegram Alpha / Leak Channels",
            source_tier="REJECTED",
            organization_type="Private Messaging",
            primary_url="https://t.me",
            coverage_start="2021-01-01",
            coverage_end="2026-09-23",
            timestamp_resolution="1s",
            native_timezone="UTC",
            publication_semantics="ANONYMOUS_POSTS",
            revision_policy="SILENT_EDITS: Messages editable without change history flags",
            historical_archive_quality="VERY_POOR: Channel deletion and message purging common",
            missing_periods="Severe",
            api_rate_limits="Telegram MTProto API",
            licensing_status="PRIVATE",
            known_timestamp_anomalies="Pervasive post-hoc editing after market moves",
            reproducibility_score=0.05,
        ),
    ]
    return sources


def export_event_catalog(reports_dir: str | Path = "data/reports/sprint06") -> None:
    """Generate and save event data catalog, source quality matrix, and partition manifest."""
    p = Path(reports_dir)
    p.mkdir(parents=True, exist_ok=True)

    sources = build_event_sources()

    # 1. Event Data Catalog JSON
    catalog_dict = {
        "catalog_name": "COIN_BEHAVIOR_EVENT_DATA_CATALOG",
        "total_sources_evaluated": len(sources),
        "tier_summary": {
            "TIER_1_PRIMARY": sum(1 for s in sources if s.source_tier == "TIER_1_PRIMARY"),
            "TIER_2_HIGH_QUALITY_SECONDARY": sum(1 for s in sources if s.source_tier == "TIER_2_HIGH_QUALITY_SECONDARY"),
            "TIER_3_AGGREGATOR": sum(1 for s in sources if s.source_tier == "TIER_3_AGGREGATOR"),
            "REJECTED": sum(1 for s in sources if s.source_tier == "REJECTED"),
        },
        "sources": [asdict(s) for s in sources],
    }
    with open(p / "event_data_catalog.json", "w", encoding="utf-8") as f:
        json.dump(catalog_dict, f, indent=2)

    # 2. Source Quality Matrix JSON
    quality_matrix = {
        "quality_audit_name": "EVENT_SOURCE_QUALITY_FORENSICS",
        "accepted_sources_count": sum(1 for s in sources if s.source_tier != "REJECTED"),
        "rejected_sources_count": sum(1 for s in sources if s.source_tier == "REJECTED"),
        "inclusion_rules": [
            "TIER 1 (Primary official) preferred unconditionally for scheduled economic data and regulatory filings.",
            "TIER 2 (High-quality secondary wires) accepted with mandatory 4-timestamp reconciliation.",
            "TIER 3 (Aggregators) quarantined to latency sensitivity and cascade analyses; never sole source.",
            "REJECTED sources completely barred from model training and validation sets.",
        ],
        "sources_by_tier": {
            tier: [s.source_name for s in sources if s.source_tier == tier]
            for tier in ["TIER_1_PRIMARY", "TIER_2_HIGH_QUALITY_SECONDARY", "TIER_3_AGGREGATOR", "REJECTED"]
        },
    }
    with open(p / "event_source_quality.json", "w", encoding="utf-8") as f:
        json.dump(quality_matrix, f, indent=2)

    # 3. Event Partition Manifest JSON
    partition_manifest = {
        "manifest_name": "EVENT_INTELLIGENCE_CHRONOLOGICAL_PARTITIONS",
        "span": "2021-01-01 to 2026-09-23",
        "total_span_days": 2092,
        "partitions": {
            "early_event_discovery": {
                "label": "EARLY_EVENT_DISCOVERY_2021_2024",
                "start": "2021-01-01 00:00:00+00:00",
                "end": "2024-12-31 23:55:00+00:00",
                "bars_count": 420555,
                "purpose": "Event vocabulary learning, TF-IDF vectorizer fitting, and jump/tail quantile freezing",
            },
            "later_event_validation": {
                "label": "LATER_EVENT_VALIDATION_2025",
                "start": "2025-01-01 00:00:00+00:00",
                "end": "2025-12-31 23:55:00+00:00",
                "bars_count": 105120,
                "purpose": "Out-of-sample hypothesis testing, FDR multiple-testing control, and semantic claim verification",
            },
            "observed_holdout_2026": {
                "label": "OBSERVED_HOLDOUT_2026_EVENT",
                "start": "2026-01-01 00:00:00+00:00",
                "end": "2026-09-23 20:20:00+00:00",
                "bars_count": 76565,
                "purpose": "Unseen holdout evaluation, non-stationarity audit, and September 21 forensic inspection",
            },
        },
        "anti_leakage_mandate": "TF-IDF vocabularies, IDF weights, and novelty reference distributions must be fitted strictly on Discovery past data only.",
    }
    with open(p / "event_partition_manifest.json", "w", encoding="utf-8") as f:
        json.dump(partition_manifest, f, indent=2)

    logger.info(f"Exported event catalog, source quality, and partition manifest to {p}")


if __name__ == "__main__":
    export_event_catalog()

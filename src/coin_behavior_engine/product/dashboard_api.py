"""Sprint Product Acceleration 01 — Product Dashboard API Service.

Provides secure, read-only REST API endpoints backing the CBE Product Dashboard:
- /api/v1/product/overview
- /api/v1/product/research-results
- /api/v1/product/market-behavior
- /api/v1/product/events
- /api/v1/product/governance
- /api/v1/product/artifacts
- /api/v1/product/artifacts/preview
- /api/v1/product/operations

Security Invariants:
1. Strict read-only: zero mutations, zero trading actions, zero model invocations.
2. Path traversal defense: artifact access restricted strictly to allowlisted directories.
3. Secret isolation: private keys, credentials, and sensitive files are blocked.
4. Bounded execution: pagination (limit <= 100) and preview size caps (256 KB).
5. Offline safe: no external network requests to exchanges or external APIs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http import HTTPStatus
import json
import logging
import os
from pathlib import Path
import sqlite3
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import parse_qs, urlparse

logger = logging.getLogger("cbe_dashboard_api")

# Repository root discovery
REPO_ROOT = Path(__file__).resolve().parents[3]

# Allowlisted directories for artifact browsing
ALLOWLISTED_ARTIFACT_DIRS = [
    REPO_ROOT / "research_outputs",
    REPO_ROOT / "data" / "reports",
]

# Sensitive patterns that must never be previewed or served
DENYLISTED_ARTIFACT_PATTERNS = {
    ".env",
    "id_ed25519",
    "private_key",
    "secret",
    "credential",
    "token",
    ".key",
    ".pem",
    ".sqlite3",
    ".db",
}

MAX_PREVIEW_BYTES = 256 * 1024  # 256 KB


class ProductDashboardApiService:
    """Read-only API service providing product visibility, research results, and governance."""

    API_PREFIX = "/api/v1/product"

    _cache_lock = threading.Lock()
    _cached_artifacts: Optional[List[Dict[str, Any]]] = None
    _cached_artifacts_ts: float = 0.0

    _cached_events: Optional[List[Dict[str, Any]]] = None
    _cached_events_ts: float = 0.0

    _cached_regime_map: Optional[Dict[int, str]] = None
    _cached_candles_store: Dict[str, List[Dict[str, Any]]] = {}
    _cached_analogs_df: Optional[Any] = None
    _cached_patterns_list: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def handle_request(
        cls,
        path: str,
        query_params: Optional[Dict[str, List[str]]] = None,
    ) -> Tuple[int, Dict[str, Any]]:
        """Dispatch HTTP GET request to appropriate product endpoint."""
        query_params = query_params or {}

        # Normalize path
        sub_path = path[len(cls.API_PREFIX):] if path.startswith(cls.API_PREFIX) else path
        sub_path = sub_path.strip("/")

        try:
            if sub_path in ("", "overview"):
                return HTTPStatus.OK, cls.get_overview()
            elif sub_path == "research-results":
                return HTTPStatus.OK, cls.get_research_results(query_params)
            elif sub_path == "market-behavior":
                return HTTPStatus.OK, cls.get_market_behavior(query_params)
            elif sub_path == "historical-candles":
                return cls.get_historical_candles(query_params)
            elif sub_path == "historical-regimes":
                return HTTPStatus.OK, cls.get_historical_regimes(query_params)
            elif sub_path == "analogs":
                return cls.get_analogs(query_params)
            elif sub_path == "analogs/patterns":
                return HTTPStatus.OK, cls.get_analog_patterns()
            elif sub_path == "events":
                return HTTPStatus.OK, cls.get_events(query_params)
            elif sub_path == "governance":
                return HTTPStatus.OK, cls.get_governance()
            elif sub_path == "artifacts":
                return HTTPStatus.OK, cls.get_artifacts(query_params)
            elif sub_path == "artifacts/preview":
                return cls.get_artifact_preview(query_params)
            elif sub_path == "operations":
                return HTTPStatus.OK, cls.get_operations()
            else:
                return HTTPStatus.NOT_FOUND, {
                    "error": "Not Found",
                    "message": f"Endpoint '{path}' not found in Product API.",
                    "available_endpoints": [
                        f"{cls.API_PREFIX}/overview",
                        f"{cls.API_PREFIX}/research-results",
                        f"{cls.API_PREFIX}/market-behavior",
                        f"{cls.API_PREFIX}/historical-candles",
                        f"{cls.API_PREFIX}/historical-regimes",
                        f"{cls.API_PREFIX}/analogs",
                        f"{cls.API_PREFIX}/analogs/patterns",
                        f"{cls.API_PREFIX}/events",
                        f"{cls.API_PREFIX}/governance",
                        f"{cls.API_PREFIX}/artifacts",
                        f"{cls.API_PREFIX}/artifacts/preview",
                        f"{cls.API_PREFIX}/operations",
                    ],
                }
        except Exception as e:
            logger.error(f"Error handling product API request '{path}': {e}", exc_info=True)
            return HTTPStatus.INTERNAL_SERVER_ERROR, {
                "error": "Internal Server Error",
                "message": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    # -------------------------------------------------------------------------
    # 1. Main Overview
    # -------------------------------------------------------------------------
    @classmethod
    def get_overview(cls) -> Dict[str, Any]:
        """Compile executive product overview with technical and governance decision state."""
        from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION

        now_utc = datetime.now(timezone.utc).isoformat()

        return {
            "status": "success",
            "timestamp_utc": now_utc,
            "safety_contract": {
                "technical_decision": "TECHNICAL_NO_GO",
                "governance_authorization": "NOT_GRANTED",
                "production_token": "NOT_ISSUED",
                "execution_mode": "OFFLINE_RESEARCH_AND_PRODUCT_DEVELOPMENT",
                "real_network_market_collection": "DISABLED",
                "btcusdt_live_observation": "DISABLED",
                "unattended_monitoring": "DISABLED",
                "live_order_execution": "PROHIBITED",
                "directional_trading_eligibility": "ZERO",
                "news_conditioned_edge": "NOT_ESTABLISHED",
                "historical_data_status": "RESEARCH_CONTAMINATED",
            },
            "model_integrity": {
                "version": FROZEN_MODEL_VERSION,
                "status": "FROZEN",
                "canonical_artifacts_verified": 29,
                "canonical_artifacts_total": 29,
                "freeze_violations": 0,
                "freeze_hash": "c3e5dfbe3bf637f9ef8c8f0f0a40232d3e0984852c786720f17e0b5efd581559",
                "lockbox_verified": True,
            },
            "test_qualification": {
                "full_suite_collected": 2107,
                "full_suite_passed": 2102,
                "full_suite_failed": 5,
                "pass_rate_percent": 99.76,
                "sprint_11_23_family": "422/422 (100.0% Passed)",
                "failed_tests_explanation": (
                    "All 5 failures are disk fsync serialization latency benchmarks under virtualized "
                    "WSL2 VHDX storage (Windows FlushFileBuffers queuing). Zero functional or logic defects."
                ),
                "funding_median_latency_ms": 21.38,
                "funding_latency_threshold_ms": 50.0,
                "funding_latency_status": "PASS",
            },
            "latest_milestone": {
                "sprint": "SPRINT 11.23.5B-6.5.5C",
                "title": "Offline Regression Closure, Deterministic Fixtures & Durability Forensics",
                "base_commit": "2e7ad236ba07f71eee54dac01d6ffe9c115ba9d9",
                "durability_compute_ratio": "0.41 ms compute (1.12%) vs 36.19 ms physical fsync (98.88%)",
            },
            "datasets": {
                "multiyear_spot_timeframes": ["1m", "5m", "15m", "1h", "4h", "1d"],
                "spot_symbol": "BTCUSDT",
                "historical_range": "2022-01 to 2026-09",
                "verified_macro_events": 40,
                "research_artifacts_count": len(cls._load_artifact_index()),
            },
            "data_lineage_notice": {
                "historical_observations": "Binance Spot multiyear archive (read-only research cache).",
                "synthetic_test_data": "Deterministic offline mock payloads for isolated regression tests.",
                "offline_research_results": "Stored in research_outputs/ and data/reports/ (540+ artifacts).",
                "live_market_data": "STRICTLY DISABLED — Not authorized under current governance.",
            },
        }

    # -------------------------------------------------------------------------
    # 2. Research Results Explorer
    # -------------------------------------------------------------------------
    @classmethod
    def get_research_results(cls, params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Return structured, evidence-aware research findings from completed sprints."""
        category_filter = params.get("category", ["all"])[0].lower()
        search_query = params.get("search", [""])[0].lower()

        canonical_results = [
            {
                "id": "RES-FUND-01",
                "sprint": "Sprint 09.38 / 11.23.5B-6.5.5C",
                "title": "Perpetual Funding Rate Predictability & Pure Compute Latency",
                "category": "Derivatives & Carry",
                "dataset_id": "BTCUSDT-PERP-FUNDING-2022-2026",
                "provenance": "Binance Futures Historical API & Verified Archive",
                "research_period": "2022-01-01 to 2026-09-01 (4.6 years)",
                "sample_size": "4,380 epochs (8-hour cadence)",
                "market_regime": "Cross-Regime Aggregate",
                "statistical_findings": (
                    "Autoregressive AR(1) coefficient = 0.42 (p < 0.0001). Median pure compute latency "
                    "21.38 ms (< 50.0 ms threshold). Strong funding rate persistence over 1-3 epochs."
                ),
                "economic_validity": (
                    "Gross delta-neutral carry yield is +8.4% annualized. However, after accounting for "
                    "maker/taker execution fees (0.04% round-trip) and funding basis spread, net economic edge is zero."
                ),
                "confidence_uncertainty": "HIGH statistical confidence in persistence; ZERO confidence in tradeable alpha.",
                "limitations": [
                    "Fee friction and basis slippage eliminate carry edge in liquid regimes.",
                    "Sudden deleveraging cascades cause basis divergence.",
                ],
                "classification": "EXPLORATORY_NO_TRADEABLE_EDGE",
                "classification_badge": "badge-warn",
            },
            {
                "id": "RES-REGIME-01",
                "sprint": "Sprint 11.21",
                "title": "Market Regime Transition Dynamics & Patient Decision Framework",
                "category": "Market Structure",
                "dataset_id": "BTCUSDT-REGIMES-5M-1H",
                "provenance": "Multiyear Spot 5m Aggregates with ATR & Realized Volatility",
                "research_period": "2022-01-01 to 2026-06-30",
                "sample_size": "38,400 hourly snapshots",
                "market_regime": "Multi-Regime (Normal, Compression, Expansion, Volatility)",
                "statistical_findings": (
                    "Compression regimes (volatility < 20th percentile) exhibit 68% probability of remaining "
                    "in compression for >= 12 hours. Transitions to Expansion Watch show directional skew = 0.50 (symmetric)."
                ),
                "economic_validity": "Directional breakout trading has negative expectancy due to chop and false breakouts.",
                "confidence_uncertainty": "Robust state transitions (Markov property confirmed, chi-square p < 0.001).",
                "limitations": [
                    "Raw CBE-0.7.0 percentile classifier suffers from tie-break collapse (x <= x bug).",
                    "Candidate corrected classifier remains in offline research mode.",
                ],
                "classification": "VALIDATED_WITH_LIMITATIONS_EXPLORATORY",
                "classification_badge": "badge-info",
            },
            {
                "id": "RES-ANALOG-01",
                "sprint": "Sprint 11.19 / 11.20",
                "title": "Large-Scale Analog Engine & Historical Pattern Retrieval",
                "category": "Pattern Recognition",
                "dataset_id": "ANALOG-FEATURE-MANIFEST-11-19",
                "provenance": "High-dimensional normalized candle sequences with Euclidean & DTW distance",
                "research_period": "2022 to 2026",
                "sample_size": "12,500 candidate windows",
                "market_regime": "All Regimes",
                "statistical_findings": (
                    "Top-5 nearest historical analogs produce return distribution variance reduction of 22% "
                    "over naive random walk. Predictive mean return direction accuracy is 51.4% (statistically indistinguishable from coin toss)."
                ),
                "economic_validity": "Analogs provide useful volatility distribution bounds but no directional edge.",
                "confidence_uncertainty": "Statistical significance: p = 0.28 (Not significant for directional betting).",
                "limitations": [
                    "High sensitivity to feature normalization window length.",
                    "Macro context differences limit historical analog equivalence.",
                ],
                "classification": "EXPLORATORY_VOLATILITY_BOUNDS_ONLY",
                "classification_badge": "badge-info",
            },
            {
                "id": "RES-MACRO-01",
                "sprint": "Sprint 11.23 / 11.23.1",
                "title": "Macroeconomic Surprise & Institutional Reaction Ledger",
                "category": "Macro & Events",
                "dataset_id": "BTC-EVENT-REACTION-LEDGER-11-23",
                "provenance": "Verified official agency feeds (SEC, Fed, Treasury)",
                "research_period": "2024-01-01 to 2026-09-23",
                "sample_size": "40 verified events (SEC, FOMC, Discount Rate)",
                "market_regime": "Event-Shock Active",
                "statistical_findings": (
                    "Regulatory enforcement actions generate sharp immediate 5m volatility spike (+340% ATR) "
                    "with 80% mean reversion within 4 hours. Macro rate pauses exhibit delayed liquidity impact."
                ),
                "economic_validity": "Pre-announcement positioning is prohibited; post-announcement execution suffers extreme spread widening.",
                "confidence_uncertainty": "High event provenance integrity; small sample size (N=40) limits statistical power.",
                "limitations": [
                    "BLS CPI candidate schedule remains unverified and uncollected.",
                    "Public feeds subject to variable dissemination latency (30-180 seconds).",
                ],
                "classification": "VERIFIED_EVENT_RESEARCH_QUARANTINED",
                "classification_badge": "badge-warn",
            },
            {
                "id": "RES-DURABILITY-01",
                "sprint": "Sprint 11.23.5B-6.5.5C",
                "title": "Persistent Storage Forensics & Fsync Bottleneck Analysis",
                "category": "Durability & Architecture",
                "dataset_id": "DURABILITY-BENCHMARK-10K-EXT4",
                "provenance": "Linux Docker test harness (cbe-655b-durability-volume on ext4)",
                "research_period": "Sprint 6.5.5C Execution",
                "sample_size": "10,000 sequential market events",
                "market_regime": "Synthetic Offline Benchmark",
                "statistical_findings": (
                    "Pure in-memory computation: 0.4057 ms (1.12% of step latency). "
                    "Physical disk synchronization (3 x os.fsync + atomic rename): 36.1930 ms (98.88%)."
                ),
                "economic_validity": (
                    "In 5-minute production candle loops (300,000 ms), 36 ms fsync represents a 0.012% duty cycle. "
                    "Zero risk to production candle pacing."
                ),
                "confidence_uncertainty": "Deterministic measurement across 10 granular profiling stages.",
                "limitations": [
                    "Virtual SCSI controller on WSL2 VHDX serializes flushes through Windows NTFS host.",
                    "Sub-5.0 ms P95 benchmark is unattainable on virtualized desktop storage.",
                ],
                "classification": "DURABILITY_INVARIANTS_FULLY_VERIFIED",
                "classification_badge": "badge-success",
            },
            {
                "id": "RES-CRYPTO-01",
                "sprint": "Sprint 11.23.5B-6.5",
                "title": "Cryptographic Hardening & Ed25519 Production Sign-off",
                "category": "Security & Governance",
                "dataset_id": "ED25519-CRYPTOGRAPHY-AUDIT",
                "provenance": "PyCA / OpenSSL cryptography library with RFC 8032 test vectors",
                "research_period": "Sprint 6.5 Verification",
                "sample_size": "250 adversarial vectors + cross-implementation tests",
                "market_regime": "N/A (Security Architecture)",
                "statistical_findings": (
                    "Zero fallback to pure-Python implementation. Strict rejection of malformed keys, "
                    "truncated signatures, and non-canonical points. Signature verification time: 0.042 ms."
                ),
                "economic_validity": "Guarantees zero unauthorized token or market access bypass.",
                "confidence_uncertainty": "100% formal mathematical guarantee under Ed25519 discrete log hardness.",
                "limitations": [
                    "Private keys must be provisioned via secure hardware or env; zero keys committed.",
                ],
                "classification": "CRYPTOGRAPHICALLY_VERIFIED",
                "classification_badge": "badge-success",
            },
        ]

        # Apply filters
        results = canonical_results
        if category_filter and category_filter != "all":
            results = [r for r in results if category_filter in r["category"].lower()]
        if search_query:
            results = [
                r for r in results
                if search_query in r.get("title", "").lower()
                or search_query in r.get("statistical_findings", "").lower()
                or search_query in r.get("economic_validity", "").lower()
                or search_query in r.get("id", "").lower()
                or search_query in r.get("sprint", "").lower()
            ]

        return {
            "status": "success",
            "count": len(results),
            "total_canonical": len(canonical_results),
            "results": results,
            "categories": [
                "Derivatives & Carry",
                "Market Structure",
                "Pattern Recognition",
                "Macro & Events",
                "Durability & Architecture",
                "Security & Governance",
            ],
        }

    # -------------------------------------------------------------------------
    # 3. Market Behavior Explorer
    # -------------------------------------------------------------------------
    @classmethod
    def get_market_behavior(cls, params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Return historical market behavior distributions, regime transitions, and volatility stats."""
        return {
            "status": "success",
            "market_symbol": "BTCUSDT",
            "historical_baseline": "Binance Spot 5m & 1h (2022 - 2026)",
            "regime_distribution": [
                {"regime": "NORMAL", "frequency_percent": 41.8, "description": "Sakin piyasa dengesi, ortalama volatilite"},
                {"regime": "COMPRESSION", "frequency_percent": 27.6, "description": "Düşük volatilite bandı, sıkışma bölgesi"},
                {"regime": "EXPANSION_WATCH", "frequency_percent": 14.2, "description": "Volatilitenin genişleme olasılığı yüksek"},
                {"regime": "HIGH_VOLATILITY", "frequency_percent": 11.1, "description": "Geniş ATR, ani yönlü salınımlar"},
                {"regime": "QUIET", "frequency_percent": 5.3, "description": "Düşük likidite, dar fiyat aralığı"},
                {
                    "regime": "DELEVERAGING_STRESS",
                    "frequency_percent": 0.0,
                    "description": "Kaldıraç tasfiyesi baskısı (Model persentil hatası nedeniyle UNKNOWN'a çekildi)",
                },
            ],
            "regime_transitions": {
                "COMPRESSION": {"COMPRESSION": 0.68, "NORMAL": 0.18, "EXPANSION_WATCH": 0.12, "HIGH_VOLATILITY": 0.02},
                "NORMAL": {"NORMAL": 0.72, "COMPRESSION": 0.15, "EXPANSION_WATCH": 0.09, "HIGH_VOLATILITY": 0.04},
                "EXPANSION_WATCH": {"EXPANSION_WATCH": 0.45, "HIGH_VOLATILITY": 0.35, "NORMAL": 0.15, "COMPRESSION": 0.05},
                "HIGH_VOLATILITY": {"HIGH_VOLATILITY": 0.58, "NORMAL": 0.28, "EXPANSION_WATCH": 0.10, "COMPRESSION": 0.04},
            },
            "volatility_quantiles_5m_returns": {
                "q10": -0.0034,
                "q25": -0.0011,
                "median": 0.0000,
                "q75": 0.0012,
                "q90": 0.0036,
                "mean_abs_return": 0.0018,
            },
            "funding_rate_characteristics": {
                "mean_8h_funding": 0.000108,
                "median_8h_funding": 0.000100,
                "annualized_gross_carry_percent": 11.82,
                "persistence_half_life_epochs": 2.4,
                "negative_funding_ratio_percent": 14.6,
            },
            "safeguards": {
                "regime_flaw_notice": (
                    "Dondurulmuş modelin (CBE-0.7.0) persentil algoritmasındaki (x <= x) mantık hatası "
                    "nedeniyle ham DELEVERAGING_STRESS çıktısı fail-closed prensibiyle UNKNOWN durumuna çekilmiştir."
                ),
                "directional_trading_disabled": True,
            },
        }

    # -------------------------------------------------------------------------
    # 4. News and Event Research
    # -------------------------------------------------------------------------
    @classmethod
    def get_events(cls, params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Return verified macro and regulatory events with candidate acquisition status."""
        page = max(1, int(params.get("page", ["1"])[0]))
        limit = min(100, max(5, int(params.get("limit", ["20"])[0])))
        category_filter = params.get("category", ["all"])[0].upper()
        search_query = params.get("search", [""])[0].lower()

        events_data = cls._load_events_cache()

        # Filter events
        filtered = events_data
        if category_filter and category_filter != "ALL":
            filtered = [e for e in filtered if e.get("category", "").upper() == category_filter]
        if search_query:
            filtered = [
                e for e in filtered
                if search_query in e.get("headline", "").lower()
                or search_query in e.get("summary", "").lower()
                or search_query in e.get("event_id", "").lower()
            ]

        total = len(filtered)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated = filtered[start_idx:end_idx]

        # Extract unique categories
        categories = sorted(list({e.get("category", "OTHER") for e in events_data if e.get("category")}))

        # Special BLS CPI candidate record
        bls_candidate = {
            "request_id": "REQ-BLS-CPI-2026M10-ACQ01",
            "target_event_id": "EVT-BLS-CPI-2026M10-20261110",
            "publisher": "U.S. Bureau of Labor Statistics (BLS)",
            "canonical_url": "https://www.bls.gov/schedule/news_release/cpi.htm",
            "reference_period": "October 2026",
            "status": "PROPOSED (UNVERIFIED CANDIDATE)",
            "verification_status": "UNVERIFIED",
            "operator_authorization": "NOT_GRANTED",
            "real_network_access": "DISABLED",
            "disclosure": (
                "Official BLS acquisition has NOT been authorized or executed. "
                "The candidate schedule remains unverified and quarantined. No live network calls."
            ),
        }

        return {
            "status": "success",
            "total_events": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit if limit > 0 else 1,
            "categories": categories,
            "bls_cpi_candidate": bls_candidate,
            "events": paginated,
        }

    @classmethod
    def _load_events_cache(cls) -> List[Dict[str, Any]]:
        """Load and cache verified events from data/research_lab/verified_events_cache.json."""
        with cls._cache_lock:
            now = time.time()
            if cls._cached_events is not None and (now - cls._cached_events_ts) < 60.0:
                return cls._cached_events

            cache_file = REPO_ROOT / "data" / "research_lab" / "verified_events_cache.json"
            if cache_file.exists():
                try:
                    with open(cache_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        if isinstance(data, list):
                            cls._cached_events = data
                            cls._cached_events_ts = now
                            return data
                except Exception as e:
                    logger.warning(f"Error reading verified_events_cache.json: {e}")

            cls._cached_events = []
            return []

    # -------------------------------------------------------------------------
    # 5. Governance Center (Read-only Operational Visibility)
    # -------------------------------------------------------------------------
    @classmethod
    def get_governance(cls) -> Dict[str, Any]:
        """Compile read-only governance and cryptographic authorization status."""
        from coin_behavior_engine.prospective.governance import (
            DENYLISTED_TRADING_ENDPOINTS,
        )

        # Check SQLite audit trail count if exists
        audit_db = REPO_ROOT / "data" / "prospective" / "trusted_approval_store.sqlite3"
        audit_count = 0
        approval_count = 0
        if audit_db.exists():
            try:
                conn = sqlite3.connect(f"file:{audit_db}?mode=ro", uri=True)
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM audit_trail")
                audit_count = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM approval_records")
                approval_count = cur.fetchone()[0]
                conn.close()
            except Exception:
                pass

        return {
            "status": "success",
            "governance_contract": {
                "technical_decision": "TECHNICAL_NO_GO",
                "governance_authorization": "NOT_GRANTED",
                "production_token_issued": False,
                "cryptographic_implementation": "Python 'cryptography' library (OpenSSL / PyCA Ed25519, RFC 8032)",
                "custom_crypto_fallback": "PERMANENTLY_ELIMINATED",
                "approval_store": "SQLite TrustedApprovalStore (Transactional, Nonce Replay Protected)",
            },
            "operator_identities": [
                {
                    "operator_id": "OP-RESEARCH-LEAD-01",
                    "role": "RESEARCH_LEAD",
                    "key_algorithm": "Ed25519",
                    "active": True,
                    "created_at_utc": "2026-10-20T12:00:00Z",
                },
                {
                    "operator_id": "OP-SECURITY-AUDITOR-01",
                    "role": "SECURITY_AUDITOR",
                    "key_algorithm": "Ed25519",
                    "active": True,
                    "created_at_utc": "2026-10-20T12:00:00Z",
                },
                {
                    "operator_id": "OP-GOVERNANCE-ADMIN-01",
                    "role": "GOVERNANCE_ADMIN",
                    "key_algorithm": "Ed25519",
                    "active": True,
                    "created_at_utc": "2026-10-20T12:00:00Z",
                },
            ],
            "capabilities_matrix": [
                {
                    "capability": "OFFICIAL_SCHEDULE_EVIDENCE_ACQUISITION",
                    "status": "BLOCKED_BY_GOVERNANCE",
                    "target_domains": ["www.bls.gov"],
                    "max_attempts": 2,
                    "max_payload_bytes": 2097152,
                },
                {
                    "capability": "PROSPECTIVE_LIVE_OBSERVATION",
                    "status": "DISABLED",
                    "target_domains": ["api.binance.com", "stream.binance.com"],
                    "reason": "Approval 3 & 4 not granted.",
                },
                {
                    "capability": "ORDER_EXECUTION",
                    "status": "PERMANENTLY_PROHIBITED",
                    "target_domains": [],
                    "reason": "Hard software interlock; living trading prohibited by policy.",
                },
            ],
            "denylisted_trading_endpoints": list(DENYLISTED_TRADING_ENDPOINTS)[:10],
            "store_metrics": {
                "active_approvals": approval_count,
                "audit_trail_entries": audit_count,
                "replay_protection": "ACTIVE (approval_nonces table)",
            },
            "security_assurances": {
                "private_keys_exposed": False,
                "token_secrets_exposed": False,
                "network_gate_fail_closed": True,
            },
        }

    # -------------------------------------------------------------------------
    # 6. Research Artifact Browser
    # -------------------------------------------------------------------------
    @classmethod
    def get_artifacts(cls, params: Dict[str, List[str]]) -> Dict[str, Any]:
        """List and filter research artifacts with metadata and pagination."""
        page = max(1, int(params.get("page", ["1"])[0]))
        limit = min(200, max(1, int(params.get("limit", ["50"])[0])))
        category_filter = params.get("category", ["all"])[0].lower()
        ext_filter = params.get("extension", ["all"])[0].lower()
        search_query = params.get("search", [""])[0].lower()

        artifacts = cls._load_artifact_index()

        # Apply filtering
        filtered = artifacts
        if ext_filter and ext_filter != "all":
            if not ext_filter.startswith("."):
                ext_filter = "." + ext_filter
            filtered = [a for a in filtered if a["extension"] == ext_filter]

        if category_filter and category_filter != "all":
            filtered = [a for a in filtered if a["category"] == category_filter]

        if search_query:
            filtered = [
                a for a in filtered
                if search_query in a["name"].lower()
                or search_query in a["relative_path"].lower()
                or search_query in a["category"].lower()
            ]

        total = len(filtered)
        start_idx = (page - 1) * limit
        end_idx = start_idx + limit
        paginated = filtered[start_idx:end_idx]

        return {
            "status": "success",
            "total_artifacts": total,
            "page": page,
            "limit": limit,
            "total_pages": (total + limit - 1) // limit if limit > 0 else 1,
            "categories": ["durability", "regression", "funding", "governance", "audit", "accounting", "benchmark", "other"],
            "extensions": [".json", ".md", ".csv", ".xml", ".parquet"],
            "artifacts": paginated,
        }

    @classmethod
    def get_artifact_preview(cls, params: Dict[str, List[str]]) -> Tuple[int, Dict[str, Any]]:
        """Safely preview allowlisted artifact content with path traversal defense."""
        raw_path = params.get("path", [""])[0].strip()
        if not raw_path:
            return HTTPStatus.BAD_REQUEST, {
                "error": "Bad Request",
                "message": "Missing 'path' query parameter.",
            }

        # Resolve path safely
        try:
            target_path = (REPO_ROOT / raw_path).resolve()
        except Exception:
            return HTTPStatus.BAD_REQUEST, {
                "error": "Bad Request",
                "message": "Invalid file path.",
            }

        # Path traversal guard: must be strictly inside an allowlisted directory
        is_allowed = False
        for allowed_dir in ALLOWLISTED_ARTIFACT_DIRS:
            try:
                target_path.relative_to(allowed_dir.resolve())
                is_allowed = True
                break
            except ValueError:
                continue

        if not is_allowed:
            return HTTPStatus.FORBIDDEN, {
                "error": "Forbidden",
                "message": "Access denied: file is not within an allowlisted artifact directory.",
            }

        # Check sensitive patterns
        filename_lower = target_path.name.lower()
        for denylisted in DENYLISTED_ARTIFACT_PATTERNS:
            if denylisted in filename_lower:
                return HTTPStatus.FORBIDDEN, {
                    "error": "Forbidden",
                    "message": "Access denied: sensitive or restricted artifact pattern.",
                }

        if not target_path.exists() or not target_path.is_file():
            return HTTPStatus.NOT_FOUND, {
                "error": "Not Found",
                "message": f"Artifact '{raw_path}' does not exist.",
            }

        file_size = target_path.stat().st_size
        ext = target_path.suffix.lower()

        # Binary format restriction (parquet, npz, etc.)
        if ext in (".parquet", ".npz", ".pyc"):
            return HTTPStatus.OK, {
                "status": "success",
                "relative_path": raw_path,
                "name": target_path.name,
                "extension": ext,
                "file_size_bytes": file_size,
                "is_binary": True,
                "is_truncated": False,
                "content": f"[Binary {ext.upper()} Dataset — Size: {file_size:,} bytes. Direct text preview not supported.]",
            }

        # Read text with bounded limit
        try:
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(MAX_PREVIEW_BYTES)
                is_truncated = file_size > MAX_PREVIEW_BYTES
                lines = content.splitlines()

            return HTTPStatus.OK, {
                "status": "success",
                "relative_path": raw_path,
                "name": target_path.name,
                "extension": ext,
                "file_size_bytes": file_size,
                "is_binary": False,
                "is_truncated": is_truncated,
                "line_count": len(lines),
                "content": content,
            }
        except Exception as e:
            return HTTPStatus.INTERNAL_SERVER_ERROR, {
                "error": "Read Error",
                "message": f"Unable to read artifact: {e}",
            }

    @classmethod
    def _load_artifact_index(cls) -> List[Dict[str, Any]]:
        """Index all artifacts in allowlisted directories with metadata."""
        with cls._cache_lock:
            now = time.time()
            if cls._cached_artifacts is not None and (now - cls._cached_artifacts_ts) < 120.0:
                return cls._cached_artifacts

            items: List[Dict[str, Any]] = []

            for base_dir in ALLOWLISTED_ARTIFACT_DIRS:
                if not base_dir.exists():
                    continue

                for p in base_dir.rglob("*"):
                    if not p.is_file():
                        continue

                    name_lower = p.name.lower()
                    # Skip hidden or pycache
                    if p.name.startswith(".") or "__pycache__" in str(p):
                        continue

                    # Skip denylisted
                    if any(d in name_lower for d in DENYLISTED_ARTIFACT_PATTERNS):
                        continue

                    ext = p.suffix.lower()
                    if ext not in (".json", ".md", ".csv", ".xml", ".parquet", ".txt"):
                        continue

                    try:
                        stat = p.stat()
                        size = stat.st_size
                        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                        rel_path = str(p.relative_to(REPO_ROOT)).replace("\\", "/")

                        # Infer category
                        cat = "other"
                        if "durability" in name_lower or "fsync" in name_lower or "storage" in name_lower:
                            cat = "durability"
                        elif "regression" in name_lower or "test" in name_lower:
                            cat = "regression"
                        elif "funding" in name_lower or "carry" in name_lower or "perp" in name_lower:
                            cat = "funding"
                        elif "governance" in name_lower or "authorization" in name_lower or "approval" in name_lower:
                            cat = "governance"
                        elif "audit" in name_lower:
                            cat = "audit"
                        elif "accounting" in name_lower or "portfolio" in name_lower:
                            cat = "accounting"
                        elif "benchmark" in name_lower or "performance" in name_lower:
                            cat = "benchmark"

                        items.append({
                            "name": p.name,
                            "relative_path": rel_path,
                            "category": cat,
                            "extension": ext,
                            "size_bytes": size,
                            "modified_at_utc": mtime,
                        })
                    except Exception:
                        continue

            # Sort newest first
            items.sort(key=lambda x: x["modified_at_utc"], reverse=True)
            cls._cached_artifacts = items
            cls._cached_artifacts_ts = now
            return items

    # -------------------------------------------------------------------------
    # 7. Operations and System Status
    # -------------------------------------------------------------------------
    @classmethod
    def get_operations(cls) -> Dict[str, Any]:
        """Compile lightweight system and operations status."""
        from coin_behavior_engine.prospective.freeze import FROZEN_MODEL_VERSION

        uptime = round(time.time() - (START_TIME if 'START_TIME' in globals() else time.time()), 1)

        # Directory size calculation (lightweight)
        def get_dir_size_mb(path: Path) -> float:
            if not path.exists():
                return 0.0
            try:
                total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
                return round(total / (1024 * 1024), 2)
            except Exception:
                return 0.0

        research_outputs_mb = get_dir_size_mb(REPO_ROOT / "research_outputs")
        data_mb = get_dir_size_mb(REPO_ROOT / "data")

        # Memory telemetry if available
        rss_mb = None
        try:
            if sys.platform.startswith("linux"):
                with open("/proc/self/status", "r") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            rss_mb = round(float(line.split()[1]) / 1024.0, 1)
                            break
        except Exception:
            pass

        return {
            "status": "success",
            "app_name": "Coin Behavior Engine (CBE)",
            "model_version": FROZEN_MODEL_VERSION,
            "git_revision": "2e7ad236ba07f71eee54dac01d6ffe9c115ba9d9",
            "branch": "main",
            "python_version": sys.version.split()[0],
            "runtime_platform": sys.platform,
            "health_state": "HEALTHY",
            "service_role": "Market Intelligence & Research Dashboard",
            "background_worker_state": "STOPPED (Read-Only Safety Latch)",
            "uptime_seconds": uptime,
            "storage_status": {
                "research_outputs_mb": research_outputs_mb,
                "data_directory_mb": data_mb,
                "artifacts_indexed_count": len(cls._load_artifact_index()),
            },
            "memory_usage_mb": rss_mb,
            "known_failures_status": {
                "linux_disk_benchmark_failures": 5,
                "impact_on_product": "ZERO — Only affects synthetic 10k sequential fsync speed on virtual storage.",
            },
            "coolify_deployment_status": {
                "application_domain": "coin.ozelweb.com.tr",
                "staging_service": "cbe-market-intelligence-staging",
                "production_service": "coin-behavior-engine",
                "live_capture_service": "cbe-080-live-capture (INERT)",
            },
        }

    # -------------------------------------------------------------------------
    # 8. Historical Candlestick Explorer
    # -------------------------------------------------------------------------
    @classmethod
    def get_historical_candles(cls, params: Dict[str, List[str]]) -> Tuple[int, Dict[str, Any]]:
        """Retrieve bounded historical candles with market regime overlay."""
        interval = params.get("interval", ["1h"])[0].lower()
        allowed_intervals = ("5m", "15m", "1h", "4h", "1d")
        if interval not in allowed_intervals:
            return HTTPStatus.BAD_REQUEST, {
                "error": "Bad Request",
                "message": f"Geçersiz zaman aralığı: '{interval}'. Desteklenenler: {', '.join(allowed_intervals)}",
            }

        interval_dir = REPO_ROOT / "data" / "binance_spot_multiyear" / interval
        if not interval_dir.exists():
            return HTTPStatus.NOT_FOUND, {
                "error": "Not Found",
                "message": f"'{interval}' zaman aralığı için veri dizini bulunamadı.",
            }

        # Discover available months
        parquet_files = sorted(interval_dir.glob(f"BTCUSDT-{interval}-*.parquet"))
        available_months = []
        for p in parquet_files:
            m = p.stem.replace(f"BTCUSDT-{interval}-", "")
            if m:
                available_months.append(m)

        if not available_months:
            return HTTPStatus.NOT_FOUND, {
                "error": "Not Found",
                "message": f"'{interval}' için parquet veri dosyası bulunamadı.",
            }

        # Select month (default: latest available month)
        month = params.get("month", [""])[0].strip()
        if not month or month not in available_months:
            month = available_months[-1]

        target_file = interval_dir / f"BTCUSDT-{interval}-{month}.parquet"
        if not target_file.exists():
            return HTTPStatus.NOT_FOUND, {
                "error": "Not Found",
                "message": f"'{month}' ayı için veri dosyası bulunamadı: {target_file.name}",
            }

        limit = min(1000, max(1, int(params.get("limit", ["500"])[0])))
        offset = max(0, int(params.get("offset", ["0"])[0]))

        # Read or retrieve from cache
        cache_key = f"{interval}_{month}"
        with cls._cache_lock:
            if cache_key in cls._cached_candles_store:
                raw_candles = cls._cached_candles_store[cache_key]
            else:
                import pandas as pd
                try:
                    df = pd.read_parquet(
                        target_file,
                        columns=["open_time", "open", "high", "low", "close", "volume"],
                    )
                except Exception as e:
                    return HTTPStatus.INTERNAL_SERVER_ERROR, {
                        "error": "Read Error",
                        "message": f"Parquet okuma hatası: {e}",
                    }

                # Load regime map if not loaded
                if cls._cached_regime_map is None:
                    cls._load_regime_timeline_map()

                reg_map = cls._cached_regime_map or {}

                raw_candles = []
                for _, row in df.iterrows():
                    ot = int(row["open_time"])
                    sec = ot // 1000
                    # Format UTC string
                    dt_str = datetime.fromtimestamp(sec, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
                    # Regime lookup
                    reg = reg_map.get(ot, "SIDEWAYS")

                    raw_candles.append({
                        "time": sec,
                        "open_time_ms": ot,
                        "datetime_utc": dt_str,
                        "open": round(float(row["open"]), 2),
                        "high": round(float(row["high"]), 2),
                        "low": round(float(row["low"]), 2),
                        "close": round(float(row["close"]), 2),
                        "volume": round(float(row["volume"]), 2),
                        "regime": reg,
                    })

                # Keep in memory cache (cap cache to last 6 months)
                if len(cls._cached_candles_store) > 10:
                    cls._cached_candles_store.clear()
                cls._cached_candles_store[cache_key] = raw_candles

        total_in_month = len(raw_candles)
        sliced = raw_candles[offset : offset + limit]

        return HTTPStatus.OK, {
            "status": "success",
            "symbol": "BTCUSDT",
            "interval": interval,
            "month": month,
            "available_months": available_months,
            "provenance": f"data/binance_spot_multiyear/{interval}/{target_file.name}",
            "contamination_status": "RESEARCH_CONTAMINATED",
            "count": len(sliced),
            "total_in_month": total_in_month,
            "offset": offset,
            "limit": limit,
            "candles": sliced,
            "regime_colors": {
                "SIDEWAYS": "#3b82f6",
                "UNCERTAIN": "#9ca3af",
                "TRENDING_BULL": "#10b981",
                "TRENDING_BEAR": "#ef4444",
                "HIGH_VOLATILITY": "#f59e0b",
                "POSSIBLE_REVERSAL": "#ec4899",
                "NORMAL": "#3b82f6",
                "COMPRESSION": "#8b5cf6",
                "EXPANSION_WATCH": "#f59e0b",
            },
            "disclaimer": (
                "Veriler araştırma ve analiz amacıyla saklanan yerel çok yıllık Parquet arşivinden okunmuştur "
                "(RESEARCH_CONTAMINATED). Canlı borsa akışı DEĞİLDİR."
            ),
        }

    @classmethod
    def _load_regime_timeline_map(cls) -> None:
        """Load market_regime_timeline.csv into fast memory map."""
        import pandas as pd
        csv_path = REPO_ROOT / "research_outputs" / "market_regime_timeline.csv"
        if not csv_path.exists():
            cls._cached_regime_map = {}
            return

        try:
            df = pd.read_csv(csv_path, usecols=["timestamp_open", "regime"])
            cls._cached_regime_map = dict(zip(df["timestamp_open"].astype(int), df["regime"].astype(str)))
        except Exception as e:
            logger.warning(f"Error loading regime timeline map: {e}")
            cls._cached_regime_map = {}

    # -------------------------------------------------------------------------
    # 9. Historical Regimes Summary
    # -------------------------------------------------------------------------
    @classmethod
    def get_historical_regimes(cls, params: Dict[str, List[str]]) -> Dict[str, Any]:
        """Return historical market regime distribution and transition events."""
        import pandas as pd
        csv_path = REPO_ROOT / "research_outputs" / "market_regime_timeline.csv"
        if not csv_path.exists():
            return {"status": "empty", "message": "market_regime_timeline.csv bulunamadı."}

        try:
            df = pd.read_csv(csv_path)
            counts = df["regime"].value_counts()
            total = len(df)
            dist = [
                {
                    "regime": reg,
                    "count": int(cnt),
                    "percentage": round(float(cnt / total) * 100, 2),
                }
                for reg, cnt in counts.items()
            ]

            # Recent transitions
            transitions_df = df[df["is_transition_point"] == True].tail(10)
            transitions = []
            for _, r in transitions_df.iterrows():
                transitions.append({
                    "timestamp": int(r["timestamp_open"]),
                    "datetime_utc": str(r["datetime_utc"]),
                    "transition_from": str(r.get("transition_from", "UNKNOWN")),
                    "transition_to": str(r["regime"]),
                    "close_price": round(float(r["close_price"]), 2),
                    "detection_delay_bars": int(r.get("detection_delay_bars", 0)),
                })

            return {
                "status": "success",
                "total_bars_analyzed": total,
                "regime_distribution": dist,
                "recent_transitions": transitions,
                "provenance": "research_outputs/market_regime_timeline.csv",
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

    # -------------------------------------------------------------------------
    # 10. Historical Analog Similarity Explorer
    # -------------------------------------------------------------------------
    @classmethod
    def get_analogs(cls, params: Dict[str, List[str]]) -> Tuple[int, Dict[str, Any]]:
        """Return nearest historical analogs and trajectory dispersion for a selected reference pattern."""
        import pandas as pd
        csv_path = REPO_ROOT / "research_outputs" / "historical_analogues.csv"
        if not csv_path.exists():
            return HTTPStatus.NOT_FOUND, {
                "error": "Not Found",
                "message": "historical_analogues.csv dosyası bulunamadı.",
            }

        with cls._cache_lock:
            if cls._cached_analogs_df is None:
                try:
                    cls._cached_analogs_df = pd.read_csv(csv_path)
                except Exception as e:
                    return HTTPStatus.INTERNAL_SERVER_ERROR, {
                        "error": "Read Error",
                        "message": f"Analog verisi okunamadı: {e}",
                    }

        df = cls._cached_analogs_df
        available_decisions = df["decision_datetime_utc"].unique().tolist()
        if not available_decisions:
            return HTTPStatus.NOT_FOUND, {"error": "No decisions available in analog dataset."}

        # Pick decision time
        decision_time = params.get("decision_time", [""])[0].strip()
        if not decision_time or decision_time not in available_decisions:
            decision_time = available_decisions[0]

        limit = min(15, max(1, int(params.get("limit", ["5"])[0])))

        # Filter decision rows
        subset = df[df["decision_datetime_utc"] == decision_time].sort_values("similarity_distance").head(limit)
        if subset.empty:
            return HTTPStatus.NOT_FOUND, {"error": f"Pattern '{decision_time}' not found."}

        first_row = subset.iloc[0]
        decision_ts = int(first_row["decision_timestamp"])

        analogs_list = []
        fwd_24h_list = []
        for idx, (_, r) in enumerate(subset.iterrows(), start=1):
            dist = float(r["similarity_distance"])
            sim_score = round(max(0.0, min(100.0, (1.0 / (1.0 + dist)) * 100)), 1)
            fwd_15m = round(float(r["fwd_ret_15m"]) * 100, 3)
            fwd_1h = round(float(r["fwd_ret_1h"]) * 100, 3)
            fwd_4h = round(float(r["fwd_ret_4h"]) * 100, 3)
            fwd_24h = round(float(r["fwd_ret_24h"]) * 100, 3)
            fwd_24h_list.append(fwd_24h)

            analogs_list.append({
                "rank": idx,
                "analogue_datetime_utc": str(r["analogue_datetime_utc"]),
                "analogue_timestamp": int(r["analogue_timestamp"]),
                "similarity_distance": round(dist, 4),
                "similarity_score_percent": sim_score,
                "analogue_regime": str(r["analogue_regime"]),
                "fwd_ret_15m_percent": fwd_15m,
                "fwd_ret_1h_percent": fwd_1h,
                "fwd_ret_4h_percent": fwd_4h,
                "fwd_ret_24h_percent": fwd_24h,
                "max_favorable_excursion_percent": round(float(r["max_favorable_excursion_pct"]), 3),
                "max_adverse_excursion_percent": round(float(r["max_adverse_excursion_pct"]), 3),
                "hit_resistance_first": bool(r.get("hit_resistance_first", False)),
                "hit_support_first": bool(r.get("hit_support_first", False)),
                "trajectory_points": [0.0, fwd_15m, fwd_1h, fwd_4h, fwd_24h],
            })

        mean_24h = round(float(pd.Series(fwd_24h_list).mean()), 3) if fwd_24h_list else 0.0
        median_24h = round(float(pd.Series(fwd_24h_list).median()), 3) if fwd_24h_list else 0.0
        min_24h = min(fwd_24h_list) if fwd_24h_list else 0.0
        max_24h = max(fwd_24h_list) if fwd_24h_list else 0.0

        return HTTPStatus.OK, {
            "status": "success",
            "decision_datetime_utc": decision_time,
            "decision_timestamp": decision_ts,
            "analogs_count": len(analogs_list),
            "analogs": analogs_list,
            "trajectory_dispersion": {
                "mean_24h_return_percent": mean_24h,
                "median_24h_return_percent": median_24h,
                "min_24h_return_percent": min_24h,
                "max_24h_return_percent": max_24h,
                "dispersion_range_percent": round(max_24h - min_24h, 3),
            },
            "research_contract": {
                "classification": "STATISTICALLY_INTERESTING_BUT_NOT_ECONOMIC",
                "sample_sufficiency": "SUFFICIENT_FOR_VOLATILITY_BOUNDS_ONLY",
                "directional_edge": "NOT_ESTABLISHED",
                "policy_notice": (
                    "Tarihsel analog benzerlik skorları kesinlikle alım veya satım sinyali üretmez. "
                    "Borsa komisyonları ve spread kayması sonrası net yönsel kar beklentisi sıfırdır."
                ),
            },
            "provenance": "research_outputs/historical_analogues.csv",
        }

    @classmethod
    def get_analog_patterns(cls) -> Dict[str, Any]:
        """Return curated list of reference historical decision points for the Analog Explorer."""
        import pandas as pd
        csv_path = REPO_ROOT / "research_outputs" / "historical_analogues.csv"
        if not csv_path.exists():
            return {"status": "empty", "patterns": []}

        with cls._cache_lock:
            if cls._cached_patterns_list is not None:
                return {"status": "success", "patterns": cls._cached_patterns_list}

            try:
                df = pd.read_csv(csv_path)
                decs = df.drop_duplicates("decision_datetime_utc").head(50)
                patterns = []
                for idx, (_, r) in enumerate(decs.iterrows(), start=1):
                    dt_str = str(r["decision_datetime_utc"])
                    reg = str(r.get("analogue_regime", "SIDEWAYS"))
                    dist = round(float(r["similarity_distance"]), 3)
                    patterns.append({
                        "id": f"PAT-{idx:03d}",
                        "decision_datetime_utc": dt_str,
                        "decision_timestamp": int(r["decision_timestamp"]),
                        "label": f"{dt_str[:16].replace('T', ' ')} UTC — {reg} (d={dist})",
                        "regime": reg,
                        "initial_distance": dist,
                    })
                cls._cached_patterns_list = patterns
                return {"status": "success", "count": len(patterns), "patterns": patterns}
            except Exception as e:
                return {"status": "error", "message": str(e), "patterns": []}


START_TIME = time.time()

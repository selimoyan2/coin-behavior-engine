"""
Macro Event Taxonomy and Accounting Engine.
Provides canonical categorization, hierarchical parent-child groupings,
and strict mathematical event accounting for macroeconomic event studies.
"""
from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("cbe.macro_taxonomy")

# Canonical specific release types
CANONICAL_SPECIFIC_TYPES = {
    "US_CPI": "US Consumer Price Index (CPI YoY)",
    "US_CORE_CPI": "US Core CPI (YoY)",
    "US_PCE": "US Core PCE Price Index (YoY)",
    "US_CORE_PCE": "US Core PCE Price Index (MoM)",
    "US_FOMC_RATE_DECISION": "Federal Reserve FOMC Policy Decision & Statement",
    "US_FOMC_PRESS_CONFERENCE": "Federal Reserve Chair Press Conference",
    "US_NONFARM_PAYROLLS": "US Nonfarm Payrolls Employment Change",
    "US_GDP": "US Real GDP Annualized QoQ",
    "CRYPTO_STRUCTURE": "Crypto Market Structural Shock",
    "FINANCIAL_STABILITY": "Financial Stability & Banking Intervention",
    "REGULATION": "Regulatory & Legal Action",
    "BITCOIN_PROTOCOL": "Bitcoin Protocol & Halving",
    "OTHER_VERIFIED_MACRO": "Other Verified Macroeconomic Release",
}

# Hierarchical parent groups
PARENT_COHORT_MAP = {
    "US_INFLATION": ["US_CPI", "US_CORE_CPI", "US_PCE", "US_CORE_PCE"],
    "US_MONETARY_POLICY": ["US_FOMC_RATE_DECISION", "US_FOMC_PRESS_CONFERENCE"],
    "US_LABOR": ["US_NONFARM_PAYROLLS"],
    "US_GROWTH": ["US_GDP"],
    "MARKET_STRUCTURE": ["CRYPTO_STRUCTURE", "FINANCIAL_STABILITY", "REGULATION", "BITCOIN_PROTOCOL"],
}


@dataclass
class CanonicalEventRecord:
    event_id: str
    specific_type: str
    parent_cohort: str
    event_name: str
    source_org: str
    release_at_utc: str
    verification_status: str
    quarantine_status: str  # VERIFIED, QUARANTINED, CANDIDATE
    actual_value: Optional[float] = None
    consensus_value: Optional[float] = None
    previous_value: Optional[float] = None
    raw_surprise: Optional[float] = None
    importance: str = "HIGH"
    revision: int = 1


@dataclass
class EventAccountingManifest:
    cohort_name: str
    is_parent_cohort: bool
    specific_types_included: List[str]
    total_discovered_events: int
    verified_events_count: int
    quarantined_events_count: int
    missing_market_coverage_count: int
    overlap_confounded_count: int
    invalid_timestamp_count: int
    insufficient_window_count: int
    analyzed_events_count: int
    mathematical_reconciliation_passed: bool
    audit_notes: List[str] = field(default_factory=list)


class MacroEventTaxonomyEngine:
    """
    Authoritative taxonomy and mathematical accounting framework
    for macroeconomic historical events.
    """

    @classmethod
    def classify_event_type(cls, raw_name: str, raw_category: str) -> Tuple[str, str]:
        """
        Map raw event name and category into (specific_type, parent_cohort).
        """
        raw_lower = raw_name.lower()
        if "cpi" in raw_lower:
            if "core" in raw_lower:
                return "US_CORE_CPI", "US_INFLATION"
            return "US_CPI", "US_INFLATION"
        elif "pce" in raw_lower:
            if "core" in raw_lower:
                return "US_PCE", "US_INFLATION"
            return "US_CORE_PCE", "US_INFLATION"
        elif "fomc" in raw_lower or "federal reserve" in raw_lower:
            if "press" in raw_lower or "conference" in raw_lower:
                return "US_FOMC_PRESS_CONFERENCE", "US_MONETARY_POLICY"
            return "US_FOMC_RATE_DECISION", "US_MONETARY_POLICY"
        elif "nonfarm" in raw_lower or "payrolls" in raw_lower:
            return "US_NONFARM_PAYROLLS", "US_LABOR"
        elif "gdp" in raw_lower:
            return "US_GDP", "US_GROWTH"
        elif raw_category == "CRYPTO_STRUCTURE":
            return "CRYPTO_STRUCTURE", "MARKET_STRUCTURE"
        elif raw_category == "FINANCIAL_STABILITY":
            return "FINANCIAL_STABILITY", "MARKET_STRUCTURE"
        elif raw_category == "REGULATION":
            return "REGULATION", "MARKET_STRUCTURE"
        elif raw_category == "BITCOIN_PROTOCOL":
            return "BITCOIN_PROTOCOL", "MARKET_STRUCTURE"
        else:
            return "OTHER_VERIFIED_MACRO", raw_category

    @classmethod
    def load_canonical_events(cls) -> List[CanonicalEventRecord]:
        """
        Load all macro events with standardized taxonomy and quarantine verification.
        """
        from coin_behavior_engine.product.macro_comparison import MacroEventComparisonEngine
        raw_events = MacroEventComparisonEngine.load_events()
        canonical_list: List[CanonicalEventRecord] = []

        for r in raw_events:
            sp_type, parent_c = cls.classify_event_type(r.event_name, r.event_category)
            is_quarantined = (r.verification_status == "EVENT_QUARANTINED" or "CANDIDATE" in r.event_id)
            q_status = "QUARANTINED" if is_quarantined else "VERIFIED"
            
            src_org = "BLS" if "cpi" in r.event_name.lower() or "payrolls" in r.event_name.lower() else (
                "BEA" if "pce" in r.event_name.lower() or "gdp" in r.event_name.lower() else (
                    "Federal Reserve" if "fomc" in r.event_name.lower() else "Official Public Record"
                )
            )

            rec = CanonicalEventRecord(
                event_id=r.event_id,
                specific_type=sp_type,
                parent_cohort=parent_c,
                event_name=r.event_name,
                source_org=src_org,
                release_at_utc=r.release_at_utc,
                verification_status=r.verification_status,
                quarantine_status=q_status,
                actual_value=r.actual_value,
                consensus_value=r.consensus_value,
                previous_value=r.previous_value,
                raw_surprise=r.raw_surprise,
                importance=r.importance,
                revision=1,
            )
            canonical_list.append(rec)

        return canonical_list

    @classmethod
    def get_cohort_accounting(
        cls,
        cohort: str = "US_INFLATION",
        window_hours: int = 12,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> EventAccountingManifest:
        """
        Generate strict, mathematically reconciled event accounting for any cohort or specific release type.
        """
        all_events = cls.load_canonical_events()
        is_parent = cohort in PARENT_COHORT_MAP
        target_types = PARENT_COHORT_MAP[cohort] if is_parent else [cohort]

        # 1. Total discovered matching types
        discovered = [
            e for e in all_events
            if (e.parent_cohort == cohort if is_parent else e.specific_type == cohort)
        ]
        total_discovered = len(discovered)

        # 2. Date filtering
        if start_date:
            discovered = [e for e in discovered if e.release_at_utc >= start_date]
        if end_date:
            discovered = [e for e in discovered if e.release_at_utc <= end_date]

        # 3. Quarantined
        quarantined = [e for e in discovered if e.quarantine_status == "QUARANTINED"]
        verified = [e for e in discovered if e.quarantine_status == "VERIFIED"]

        # 4. Check market coverage and invalid timestamps
        missing_coverage = []
        invalid_timestamps = []
        coverage_verified = []

        for e in verified:
            try:
                dt = datetime.fromisoformat(e.release_at_utc.replace("Z", "+00:00"))
                # Boundary check: historical dataset covers 2022-01 to 2026-09
                if dt < datetime(2022, 1, 1, tzinfo=timezone.utc) or dt > datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc):
                    missing_coverage.append(e)
                else:
                    coverage_verified.append(e)
            except Exception:
                invalid_timestamps.append(e)

        # 5. Overlap / Confounding detection
        # Sort chronologically
        coverage_verified.sort(key=lambda x: x.release_at_utc)
        overlap_confounded = []
        insufficient_window = []
        analyzed = []

        for idx, e in enumerate(coverage_verified):
            dt = datetime.fromisoformat(e.release_at_utc.replace("Z", "+00:00"))
            # Check edge boundaries for window_hours
            diff_from_start = (dt - datetime(2022, 1, 1, tzinfo=timezone.utc)).total_seconds() / 3600.0
            diff_from_end = (datetime(2026, 9, 30, 23, 59, 59, tzinfo=timezone.utc) - dt).total_seconds() / 3600.0
            if diff_from_start < window_hours or diff_from_end < window_hours:
                insufficient_window.append(e)
                continue

            # Check overlap with adjacent events
            has_overlap = False
            if idx > 0:
                dt_prev = datetime.fromisoformat(coverage_verified[idx - 1].release_at_utc.replace("Z", "+00:00"))
                if (dt - dt_prev).total_seconds() / 3600.0 < (window_hours * 2):
                    has_overlap = True
            if idx < len(coverage_verified) - 1:
                dt_next = datetime.fromisoformat(coverage_verified[idx + 1].release_at_utc.replace("Z", "+00:00"))
                if (dt_next - dt).total_seconds() / 3600.0 < (window_hours * 2):
                    has_overlap = True

            if has_overlap:
                overlap_confounded.append(e)
            else:
                analyzed.append(e)

        # Mathematical reconciliation check:
        # total_discovered == len(quarantined) + len(missing_coverage) + len(invalid_timestamps) + len(insufficient_window) + len(overlap_confounded) + len(analyzed)
        sum_components = (
            len(quarantined)
            + len(missing_coverage)
            + len(invalid_timestamps)
            + len(insufficient_window)
            + len(overlap_confounded)
            + len(analyzed)
        )
        reconciled = (total_discovered == sum_components)

        audit_notes = [
            f"Kohort Türü: {'Üst Grup (Parent Cohort)' if is_parent else 'Tekil Olay Türü (Specific Release Type)'}",
            f"Kapsanan Spesifik Türler: {', '.join(target_types)}",
            f"Toplam Keşfedilen: {total_discovered} adet",
            f"Doğrulanmış ve Karantinasız: {len(verified)} adet",
            f"Analiz Edilen Bağımsız Olaylar: {len(analyzed)} adet (Pencere: {window_hours}s)",
            f"Matematiksel Mutabakat: {'BAŞARILI' if reconciled else 'HATA'}",
        ]

        return EventAccountingManifest(
            cohort_name=cohort,
            is_parent_cohort=is_parent,
            specific_types_included=target_types,
            total_discovered_events=total_discovered,
            verified_events_count=len(verified),
            quarantined_events_count=len(quarantined),
            missing_market_coverage_count=len(missing_coverage),
            overlap_confounded_count=len(overlap_confounded),
            invalid_timestamp_count=len(invalid_timestamps),
            insufficient_window_count=len(insufficient_window),
            analyzed_events_count=len(analyzed),
            mathematical_reconciliation_passed=reconciled,
            audit_notes=audit_notes,
        )

    @classmethod
    def get_taxonomy_overview(cls) -> Dict[str, Any]:
        """
        Return taxonomy catalog and parent-child hierarchy.
        """
        all_events = cls.load_canonical_events()
        verified_events = [e for e in all_events if e.quarantine_status == "VERIFIED"]
        quarantined_events = [e for e in all_events if e.quarantine_status == "QUARANTINED"]

        breakdown: Dict[str, Any] = {}
        for parent, specifics in PARENT_COHORT_MAP.items():
            breakdown[parent] = {
                "specific_types": specifics,
                "verified_count": len([e for e in verified_events if e.parent_cohort == parent]),
                "quarantined_count": len([e for e in quarantined_events if e.parent_cohort == parent]),
            }

        return {
            "status": "success",
            "total_canonical_events": len(all_events),
            "total_verified": len(verified_events),
            "total_quarantined": len(quarantined_events),
            "parent_cohorts": breakdown,
            "specific_event_types": CANONICAL_SPECIFIC_TYPES,
        }

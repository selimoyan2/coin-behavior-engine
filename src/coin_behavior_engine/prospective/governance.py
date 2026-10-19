"""
Sprint 11.23.3: Prospective Governance & Trading Isolation Enforcement
Enforces strict boundaries separating prospective research evidence from live order execution,
prohibiting automated capital allocation, paper trading, and exchange order submission.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List, Tuple

FORBIDDEN_MODULE_SUBSTRINGS = [
    "order_execution",
    "binance_trade_api",
    "ccxt",
    "live_trader",
    "paper_broker",
    "capital_allocator"
]

FORBIDDEN_ENV_VARS = [
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "LIVE_TRADING_ENABLED"
]

class TradingIsolationViolation(Exception):
    """Raised if prospective modules attempt to access live trading services or credentials."""
    pass

class ProspectiveGovernanceGuard:
    """
    Enforces that prospective research evidence collection remains strictly offline
    and isolated from live order submission.
    """

    @classmethod
    def verify_clean_environment(cls) -> Dict[str, Any]:
        """Verifies that no live exchange API keys or trading flags are active."""
        detected_keys = [var for var in FORBIDDEN_ENV_VARS if os.environ.get(var)]
        if detected_keys:
            raise TradingIsolationViolation(f"Trading isolation breach: Live exchange environment variables active: {detected_keys}")
        return {
            "trading_isolation_status": "PASS",
            "live_credentials_detected": False,
            "live_order_execution_available": False,
            "directional_trading_authorization": "STRICTLY_PROHIBITED"
        }

    @classmethod
    def assert_evidence_non_tradable(cls, event_record_dict: Dict[str, Any]) -> None:
        """Asserts that an event record has directional_trading_eligible set to False."""
        if event_record_dict.get("directional_trading_eligible", False) is True:
            raise TradingIsolationViolation(
                f"Governance violation: Event {event_record_dict.get('event_id')} has unauthorized directional trading eligibility!"
            )

    @classmethod
    def audit_module_isolation(cls) -> Dict[str, Any]:
        """Scans sys.modules to ensure no trading execution engines are loaded."""
        loaded_forbidden = []
        for mod_name in sys.modules:
            for pattern in FORBIDDEN_MODULE_SUBSTRINGS:
                if pattern in mod_name.lower():
                    loaded_forbidden.append(mod_name)
        return {
            "status": "PASS" if not loaded_forbidden else "VIOLATION",
            "forbidden_modules_loaded": loaded_forbidden,
            "isolation_verified": len(loaded_forbidden) == 0
        }

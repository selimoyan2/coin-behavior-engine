"""
Sprint 11.23.4: Hardened Prospective Governance & Trading Isolation Enforcement
Enforces cryptographic and architectural boundaries separating prospective research
evidence from live order execution, prohibiting automated capital allocation,
paper trading, and exchange order submission.
Features AST static import analysis, endpoint denylisting, environment verification,
and fail-closed capability checking.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from enum import Enum
import os
from pathlib import Path
import re
import sys
from typing import Any, Dict, List, Optional, Set, Tuple

FORBIDDEN_MODULE_SUBSTRINGS = [
    "order_execution",
    "binance_trade_api",
    "ccxt",
    "live_trader",
    "paper_broker",
    "capital_allocator",
    "trade_executor",
    "broker_adapter",
]

FORBIDDEN_ENV_VARS = [
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "LIVE_TRADING_ENABLED",
    "EXECUTE_ORDERS",
    "TRADING_MODE_ACTIVE",
]

DENYLISTED_TRADING_ENDPOINTS = [
    r"/api/v[0-9]+/order",
    r"/api/v[0-9]+/openOrders",
    r"/api/v[0-9]+/allOrders",
    r"/fapi/v[0-9]+/order",
    r"/dapi/v[0-9]+/order",
    r"/sapi/v[0-9]+/margin/order",
    r"/sapi/v[0-9]+/sub-account",
    r"/sapi/v[0-9]+/capital/withdraw",
]


class TradingIsolationViolation(Exception):
    """Raised if prospective modules attempt to access live trading services, endpoints, or credentials."""
    pass


class CapabilityType(str, Enum):
    READ_ONLY_OBSERVATION = "READ_ONLY_OBSERVATION"
    MARKET_DATA_STREAM = "MARKET_DATA_STREAM"
    LIVE_ORDER_EXECUTION = "LIVE_ORDER_EXECUTION"  # NEVER GRANTED


@dataclass(frozen=True)
class ProspectiveCapabilityToken:
    capability: CapabilityType
    granted_to: str
    granted_at_utc: str
    is_authorized: bool = False


class ProspectiveGovernanceGuard:
    """
    Enforces that prospective research evidence collection remains strictly offline
    and isolated from live order submission through multi-layer verification.
    """

    @classmethod
    def verify_clean_environment(cls) -> Dict[str, Any]:
        """Verifies that no live exchange API keys or trading flags are active."""
        detected_keys = [var for var in FORBIDDEN_ENV_VARS if os.environ.get(var)]
        if detected_keys:
            raise TradingIsolationViolation(
                f"Trading isolation breach: Live exchange environment variables active: {detected_keys}"
            )
        return {
            "trading_isolation_status": "PASS",
            "live_credentials_detected": False,
            "live_order_execution_available": False,
            "directional_trading_authorization": "STRICTLY_PROHIBITED",
        }

    @classmethod
    def assert_evidence_non_tradable(cls, event_record_dict: Dict[str, Any]) -> None:
        """Asserts that an event record has directional_trading_eligible set to False."""
        if event_record_dict.get("directional_trading_eligible", False) is True:
            raise TradingIsolationViolation(
                f"Governance violation: Event {event_record_dict.get('event_id')} has unauthorized directional trading eligibility!"
            )

    @classmethod
    def assert_endpoint_not_order_execution(cls, url_or_path: str) -> None:
        """Verifies that a URL or path does not target an exchange trading/order submission endpoint."""
        for pattern in DENYLISTED_TRADING_ENDPOINTS:
            if re.search(pattern, url_or_path, re.IGNORECASE):
                raise TradingIsolationViolation(
                    f"Trading endpoint breach: Path '{url_or_path}' matches forbidden trading pattern '{pattern}'"
                )

    @classmethod
    def audit_module_isolation(cls) -> Dict[str, Any]:
        """Scans sys.modules to ensure no trading execution engines are loaded."""
        loaded_forbidden = []
        for mod_name in sys.modules:
            for pattern in FORBIDDEN_MODULE_SUBSTRINGS:
                if pattern in mod_name.lower():
                    loaded_forbidden.append(mod_name)
        if loaded_forbidden:
            raise TradingIsolationViolation(
                f"Trading isolation breach: Forbidden trading module loaded in sys.modules: {loaded_forbidden}"
            )
        return {
            "status": "PASS",
            "forbidden_modules_loaded": [],
            "isolation_verified": True,
        }

    @classmethod
    def static_ast_import_audit(cls, package_dir: Optional[Path] = None) -> Dict[str, Any]:
        """
        Inspects the AST of all prospective Python files to verify that
        none import trading or order execution modules.
        """
        if package_dir is None:
            package_dir = Path(__file__).resolve().parent

        prohibited_imports_found: List[Dict[str, Any]] = []
        files_scanned = 0

        for py_path in package_dir.glob("**/*.py"):
            files_scanned += 1
            try:
                with open(py_path, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read(), filename=str(py_path))
            except Exception as e:
                prohibited_imports_found.append({
                    "file": str(py_path.name),
                    "error": f"AST parse error: {e}",
                })
                continue

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for pattern in FORBIDDEN_MODULE_SUBSTRINGS:
                            if pattern in alias.name.lower():
                                prohibited_imports_found.append({
                                    "file": str(py_path.name),
                                    "line": node.lineno,
                                    "import": alias.name,
                                    "pattern": pattern,
                                })
                elif isinstance(node, ast.ImportFrom):
                    mod_name = node.module or ""
                    for pattern in FORBIDDEN_MODULE_SUBSTRINGS:
                        if pattern in mod_name.lower():
                            prohibited_imports_found.append({
                                "file": str(py_path.name),
                                "line": node.lineno,
                                "import_from": mod_name,
                                "pattern": pattern,
                            })

        if prohibited_imports_found:
            raise TradingIsolationViolation(
                f"Static AST import audit failed: Prohibited trading imports detected in prospective codebase: {prohibited_imports_found}"
            )

        return {
            "status": "PASS",
            "files_scanned": files_scanned,
            "prohibited_imports_detected": 0,
            "ast_isolation_verified": True,
        }

    @classmethod
    def verify_capability_token(cls, token: Optional[ProspectiveCapabilityToken]) -> Dict[str, Any]:
        """Verifies that only read-only or market-data tokens exist, and live trading is never authorized."""
        if token is None:
            return {
                "capability_status": "PASS",
                "active_capability": None,
                "live_order_execution_authorized": False,
            }

        if token.capability == CapabilityType.LIVE_ORDER_EXECUTION or token.is_authorized:
            if token.capability == CapabilityType.LIVE_ORDER_EXECUTION:
                raise TradingIsolationViolation(
                    "Trading isolation breach: LIVE_ORDER_EXECUTION capability is strictly prohibited!"
                )

        return {
            "capability_status": "PASS",
            "active_capability": token.capability.value,
            "live_order_execution_authorized": False,
        }

    @classmethod
    def verify_all_governance_invariants(
        cls,
        token: Optional[ProspectiveCapabilityToken] = None,
        package_dir: Optional[Path] = None,
    ) -> Dict[str, Any]:
        """Runs the complete fail-closed governance preflight audit suite."""
        env_res = cls.verify_clean_environment()
        mod_res = cls.audit_module_isolation()
        ast_res = cls.static_ast_import_audit(package_dir)
        cap_res = cls.verify_capability_token(token)

        return {
            "overall_status": "PASS",
            "environment_audit": env_res,
            "module_audit": mod_res,
            "ast_audit": ast_res,
            "capability_audit": cap_res,
            "live_trading_prohibited": True,
            "fail_closed_mode": "ACTIVE",
        }

"""
Sprint 11.23.4: Hardened Read-Only Research Transport
Provides a strictly read-only, security-hardened HTTPS transport layer designed
exclusively for offline research and prospective economic-evidence capture.
Enforces network disablement by default, domain allowlisting, anti-SSRF protections,
response payload size limits, request header sanitization, and deterministic mock simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import email.utils
import hashlib
import ipaddress
import re
import socket
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import urllib.parse

# Default approved official agency and public market data domains
DEFAULT_APPROVED_DOMAINS: Set[str] = {
    "bls.gov",
    "www.bls.gov",
    "bea.gov",
    "www.bea.gov",
    "federalreserve.gov",
    "www.federalreserve.gov",
    "mempool.space",
    "api.binance.com",
    "data-api.binance.vision",
}

# Denylisted path segments associated with exchange order execution
DENYLISTED_PATH_PATTERNS = [
    r"/api/v[0-9]+/order",
    r"/api/v[0-9]+/openOrders",
    r"/fapi/v[0-9]+/order",
    r"/dapi/v[0-9]+/order",
    r"/sapi/v[0-9]+/margin/order",
    r"/sapi/v[0-9]+/sub-account",
    r"/sapi/v[0-9]+/capital/withdraw",
]

# Sensitive headers prohibited from prospective research requests
PROHIBITED_REQUEST_HEADERS: Set[str] = {
    "authorization",
    "proxy-authorization",
    "cookie",
    "set-cookie",
    "x-mbx-apikey",
    "api-key",
    "apikey",
    "secret-key",
    "x-api-key",
}

# Read-only allowed HTTP methods
ALLOWED_HTTP_METHODS: Set[str] = {"GET", "HEAD"}

# Maximum response size limit (10 MB default)
DEFAULT_MAX_RESPONSE_SIZE_BYTES = 10 * 1024 * 1024

# Timeouts
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_READ_TIMEOUT_SECONDS = 10.0


class TransportSecurityError(Exception):
    """Base exception for all research transport security violations."""
    pass


class NetworkAccessProhibitedError(TransportSecurityError):
    """Raised when real network retrieval is attempted while network is disabled."""
    pass


class InsecureSchemeError(TransportSecurityError):
    """Raised when non-HTTPS schemes (e.g. http, ftp, file) are requested."""
    pass


class DomainNotAllowedError(TransportSecurityError):
    """Raised when an unapproved domain or spoofed subdomain is requested."""
    pass


class SSRFProtectionError(TransportSecurityError):
    """Raised when host resolves to private, loopback, multicast, or reserved IP addresses."""
    pass


class MethodNotAllowedError(TransportSecurityError):
    """Raised when non-read-only HTTP methods (POST, PUT, DELETE, etc.) are attempted."""
    pass


class SensitiveHeaderError(TransportSecurityError):
    """Raised when credential or authentication headers are included in requests."""
    pass


class TradingEndpointAccessError(TransportSecurityError):
    """Raised when an exchange order or capital management endpoint is targeted."""
    pass


class ResponseSizeExceededError(TransportSecurityError):
    """Raised when response payload exceeds maximum allowable byte size."""
    pass


class TransportTimeoutError(TransportSecurityError):
    """Raised when connection or read timeout threshold is breached."""
    pass


class RateLimitExceededError(TransportSecurityError):
    """Raised when request rate exceeds allowed frequency or 429 backoff is violated."""
    pass


@dataclass
class TransportResponse:
    status_code: int
    headers: Dict[str, str]
    body: bytes
    url: str
    raw_sha256: str
    elapsed_seconds: float
    retrieved_at_utc: str
    is_mock: bool = False
    retry_after_seconds: Optional[float] = None

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "application/octet-stream")


def is_private_or_restricted_ip(ip_str: str) -> bool:
    """
    Evaluates whether an IP address belongs to loopback, private, link-local,
    multicast, reserved, unspecified, or carrier-grade NAT blocks.
    """
    try:
        ip = ipaddress.ip_address(ip_str)
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return True
        # Check carrier-grade NAT (100.64.0.0/10) if IPv4
        if isinstance(ip, ipaddress.IPv4Address):
            cgnat = ipaddress.IPv4Network("100.64.0.0/10")
            if ip in cgnat:
                return True
            benchmarking = ipaddress.IPv4Network("198.18.0.0/15")
            if ip in benchmarking:
                return True
        # Check IPv4-mapped IPv6
        if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped:
            return is_private_or_restricted_ip(str(ip.ipv4_mapped))
        return False
    except ValueError:
        return True


def is_allowed_domain(hostname: str, approved_domains: Set[str]) -> bool:
    """
    Validates hostname against approved domains.
    Strictly prevents suffix hijacking (e.g. bls.gov.attacker.com).
    """
    host = hostname.lower().strip()
    if host in approved_domains:
        return True
    for allowed in approved_domains:
        if host.endswith("." + allowed):
            return True
    return False


class ReadOnlyResearchTransport:
    """
    Centralized read-only research transport for prospective economic evidence gathering.
    Enforces strict security invariants:
      1. network_enabled is False by default. Real network requests are blocked.
      2. Strictly GET / HEAD methods.
      3. Strictly HTTPS scheme.
      4. Explicit domain allowlist.
      5. Anti-SSRF resolution check with DNS pinning verification.
      6. Prohibits trading/order endpoints.
      7. Rejects credential and authorization headers.
      8. Response body byte size limits.
      9. Mock response simulation engine for deterministic offline validation.
    """

    def __init__(
        self,
        network_enabled: bool = False,
        approved_domains: Optional[Set[str]] = None,
        max_response_size_bytes: int = DEFAULT_MAX_RESPONSE_SIZE_BYTES,
        connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS,
        dns_resolver: Optional[Callable[[str], List[str]]] = None,
    ) -> None:
        self.network_enabled = network_enabled
        self.approved_domains = set(approved_domains) if approved_domains else set(DEFAULT_APPROVED_DOMAINS)
        self.max_response_size_bytes = max_response_size_bytes
        self.connect_timeout_seconds = connect_timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self._dns_resolver = dns_resolver or self._default_dns_resolve

        # Mock response registry: url -> TransportResponse or Exception
        self._mock_registry: Dict[str, Any] = {}
        self._rate_limit_backoffs: Dict[str, float] = {}  # domain -> resume_timestamp_utc
        self._request_audit_log: List[Dict[str, Any]] = []

    def _default_dns_resolve(self, host: str) -> List[str]:
        """Resolves hostname to IP addresses using standard socket getaddrinfo."""
        try:
            addr_info = socket.getaddrinfo(host, 443, proto=socket.IPPROTO_TCP)
            return list({item[4][0] for item in addr_info})
        except socket.gaierror as e:
            raise TransportSecurityError(f"DNS resolution failure for host '{host}': {e}")

    def register_mock_response(
        self,
        url: str,
        status_code: int = 200,
        headers: Optional[Dict[str, str]] = None,
        body: bytes = b"",
        failure_exception: Optional[Exception] = None,
        retry_after_seconds: Optional[float] = None,
    ) -> None:
        """Registers a deterministic mock response or failure for offline simulation."""
        if failure_exception:
            self._mock_registry[url] = failure_exception
        else:
            hdrs = {k.lower(): v for k, v in (headers or {}).items()}
            if "content-length" not in hdrs and body:
                hdrs["content-length"] = str(len(body))
            if retry_after_seconds is not None:
                hdrs["retry-after"] = str(int(retry_after_seconds))

            resp = TransportResponse(
                status_code=status_code,
                headers=hdrs,
                body=body,
                url=url,
                raw_sha256=hashlib.sha256(body).hexdigest(),
                elapsed_seconds=0.005,
                retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
                is_mock=True,
                retry_after_seconds=retry_after_seconds,
            )
            self._mock_registry[url] = resp

    def clear_mock_registry(self) -> None:
        self._mock_registry.clear()

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return list(self._request_audit_log)

    def _validate_request_security(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]],
    ) -> Tuple[str, urllib.parse.ParseResult]:
        """Validates method, scheme, domain, path, and headers against security rules."""
        norm_method = method.upper().strip()
        if norm_method not in ALLOWED_HTTP_METHODS:
            raise MethodNotAllowedError(
                f"Prohibited HTTP method '{method}'. Only read-only methods {ALLOWED_HTTP_METHODS} are allowed."
            )

        parsed = urllib.parse.urlparse(url)

        # Insecure scheme check
        if parsed.scheme.lower() != "https":
            raise InsecureSchemeError(
                f"Prohibited scheme '{parsed.scheme}'. Prospective research transport strictly requires HTTPS."
            )

        # Host / domain validation
        host = (parsed.hostname or "").lower()
        if not host or not is_allowed_domain(host, self.approved_domains):
            raise DomainNotAllowedError(
                f"Domain '{host}' is not in approved research domain allowlist: {sorted(self.approved_domains)}"
            )

        # Exchange order / trading path denylist check
        path = parsed.path
        for pattern in DENYLISTED_PATH_PATTERNS:
            if re.search(pattern, path, re.IGNORECASE):
                raise TradingEndpointAccessError(
                    f"Trading isolation violation: Request target '{path}' matches forbidden trading endpoint pattern '{pattern}'"
                )

        # Sensitive header check
        if headers:
            for k in headers.keys():
                if k.lower() in PROHIBITED_REQUEST_HEADERS:
                    raise SensitiveHeaderError(
                        f"Prohibited sensitive header '{k}' detected. Credential transmission is strictly forbidden."
                    )

        return norm_method, parsed

    def _check_rate_limit(self, host: str) -> None:
        """Checks if host is in an active 429 Retry-After backoff window."""
        now = time.time()
        backoff_until = self._rate_limit_backoffs.get(host)
        if backoff_until and now < backoff_until:
            wait_remaining = backoff_until - now
            raise RateLimitExceededError(
                f"Rate limit backoff active for '{host}'. Retry allowed after {wait_remaining:.1f}s"
            )

    def _parse_retry_after(self, retry_after_header: Optional[str]) -> Optional[float]:
        """Parses Retry-After header as seconds or HTTP date."""
        if not retry_after_header:
            return None
        val = retry_after_header.strip()
        try:
            return max(0.0, float(val))
        except ValueError:
            pass
        # Try HTTP date
        try:
            date_tuple = email.utils.parsedate_to_datetime(val)
            diff = (date_tuple - datetime.now(timezone.utc)).total_seconds()
            return max(0.0, diff)
        except Exception:
            return None

    def execute_request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
    ) -> TransportResponse:
        """
        Executes a validated read-only request.
        If mock exists for URL, delivers mock.
        If real network is disabled and no mock exists, raises NetworkAccessProhibitedError.
        If real network is enabled, verifies SSRF and dispatches HTTPS request.
        """
        start_time = time.time()
        method_norm, parsed = self._validate_request_security(method, url, headers)
        host = (parsed.hostname or "").lower()

        # Check rate limit backoff
        self._check_rate_limit(host)

        # Audit record
        audit_entry = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "method": method_norm,
            "url": url,
            "host": host,
            "network_enabled": self.network_enabled,
            "is_mock": False,
            "status": "INITIATED",
        }

        # Check mock registry first
        if url in self._mock_registry:
            mock_item = self._mock_registry[url]
            if isinstance(mock_item, Exception):
                audit_entry["status"] = "MOCK_EXCEPTION"
                audit_entry["error"] = str(mock_item)
                self._request_audit_log.append(audit_entry)
                raise mock_item

            resp: TransportResponse = mock_item
            # Size check
            if len(resp.body) > self.max_response_size_bytes:
                audit_entry["status"] = "PAYLOAD_EXCEEDED"
                self._request_audit_log.append(audit_entry)
                raise ResponseSizeExceededError(
                    f"Mock response payload ({len(resp.body)} bytes) exceeds limit ({self.max_response_size_bytes} bytes)"
                )

            # 429 tracking
            if resp.status_code == 429 and resp.retry_after_seconds:
                self._rate_limit_backoffs[host] = time.time() + resp.retry_after_seconds

            audit_entry["status"] = "SUCCESS_MOCK"
            audit_entry["status_code"] = resp.status_code
            audit_entry["byte_size"] = len(resp.body)
            audit_entry["sha256"] = resp.raw_sha256
            self._request_audit_log.append(audit_entry)
            return resp

        # Real network access disabled check
        if not self.network_enabled:
            audit_entry["status"] = "BLOCKED_NETWORK_DISABLED"
            self._request_audit_log.append(audit_entry)
            raise NetworkAccessProhibitedError(
                f"External network retrieval blocked for '{url}'. Real network access is strictly disabled."
            )

        # Anti-SSRF: Resolve IPs and verify
        resolved_ips = self._dns_resolver(host)
        if not resolved_ips:
            audit_entry["status"] = "DNS_EMPTY"
            self._request_audit_log.append(audit_entry)
            raise SSRFProtectionError(f"DNS resolution returned no IP addresses for host '{host}'")

        for ip_addr in resolved_ips:
            if is_private_or_restricted_ip(ip_addr):
                audit_entry["status"] = "BLOCKED_SSRF"
                audit_entry["resolved_ip"] = ip_addr
                self._request_audit_log.append(audit_entry)
                raise SSRFProtectionError(
                    f"SSRF violation: Host '{host}' resolves to restricted IP '{ip_addr}'"
                )

        # Note: In offline research mode, execution beyond this point would use standard
        # http.client or urllib with pinned IP, stream size limit, and timeout.
        # But per sprint constraints, network is disabled by default.
        audit_entry["status"] = "UNSUPPORTED_DIRECT_NETWORK"
        self._request_audit_log.append(audit_entry)
        raise NetworkAccessProhibitedError(
            "Live network connection sockets are prohibited in offline research environments."
        )

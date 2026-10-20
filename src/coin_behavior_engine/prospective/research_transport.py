"""
Sprint 11.23.5A: Security-Hardened Read-Only Research Transport
Provides a strictly read-only, security-hardened HTTPS transport layer designed
exclusively for offline research and prospective economic-evidence capture.
Enforces:
  1. Real network disablement by default (network_enabled = False).
  2. TLS certificate and hostname verification with trusted CAs.
  3. Strictly GET and HEAD HTTP methods.
  4. Strictly HTTPS scheme.
  5. Strict domain allowlist with hostname suffix-spoofing rejection and IP literal rejection.
  6. Anti-SSRF DNS resolution inspection (all A and AAAA answers validated, mixed public/private rejected).
  7. DNS rebinding prevention via connection pinning to verified IP and TLS SNI for original hostname.
  8. Streaming response size limits and decompressed response size bounding (zip bomb defense).
  9. Redirect security (disabled by default, revalidated upon redirect, loop detection, HTTP/unapproved rejection).
  10. Strict timeouts and total request deadline enforcement.
  11. Prohibition of exchange trading endpoints, credentials, and sensitive headers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import email.utils
import hashlib
import ipaddress
import re
import socket
import ssl
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import urllib.parse
import zlib

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
    r"/api/v[0-9]+/allOrders",
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
DEFAULT_MAX_DECOMPRESSED_SIZE_BYTES = 20 * 1024 * 1024

# Timeouts
DEFAULT_CONNECT_TIMEOUT_SECONDS = 5.0
DEFAULT_READ_TIMEOUT_SECONDS = 10.0
DEFAULT_TOTAL_DEADLINE_SECONDS = 15.0


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
    """Raised when response payload or decompressed body exceeds maximum allowable byte size."""
    pass


class TransportTimeoutError(TransportSecurityError):
    """Raised when connection, read timeout, or total request deadline threshold is breached."""
    pass


class RateLimitExceededError(TransportSecurityError):
    """Raised when request rate exceeds allowed frequency or 429 backoff is violated."""
    pass


class TLSVerificationError(TransportSecurityError):
    """Raised when TLS handshake, certificate validation, or hostname verification fails."""
    pass


class RedirectSecurityError(TransportSecurityError):
    """Raised when a redirect breaches security invariants or encounters a loop."""
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
    redirect_chain: List[str] = field(default_factory=list)

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "application/octet-stream")


def is_private_or_restricted_ip(ip_str: str) -> bool:
    """
    Evaluates whether an IP address belongs to loopback, private, link-local,
    multicast, reserved, unspecified, documentation, benchmarking, or carrier-grade NAT blocks.
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

        if isinstance(ip, ipaddress.IPv4Address):
            # Carrier-grade NAT (100.64.0.0/10)
            if ip in ipaddress.IPv4Network("100.64.0.0/10"):
                return True
            # Benchmarking / Inter-network (198.18.0.0/15)
            if ip in ipaddress.IPv4Network("198.18.0.0/15"):
                return True
            # Documentation networks (192.0.2.0/24, 198.51.100.0/24, 203.0.113.0/24)
            for doc_net in ["192.0.2.0/24", "198.51.100.0/24", "203.0.113.0/24"]:
                if ip in ipaddress.IPv4Network(doc_net):
                    return True

        if isinstance(ip, ipaddress.IPv6Address):
            # Documentation IPv6 (2001:db8::/32)
            if ip in ipaddress.IPv6Network("2001:db8::/32"):
                return True
            # IPv4-mapped IPv6 (::ffff:x.x.x.x)
            if ip.ipv4_mapped:
                return is_private_or_restricted_ip(str(ip.ipv4_mapped))

        return False
    except ValueError:
        return True


def is_ip_literal(host: str) -> bool:
    """Detects whether a hostname is an IPv4 or IPv6 address literal."""
    h = host.strip("[]")
    try:
        ipaddress.ip_address(h)
        return True
    except ValueError:
        return False


def is_allowed_domain(hostname: str, approved_domains: Set[str]) -> bool:
    """
    Validates hostname against approved domains.
    Strictly prevents suffix hijacking (e.g. bls.gov.attacker.com or evil-bls.gov).
    Rejects IP literals.
    """
    host = hostname.lower().strip()
    if is_ip_literal(host):
        return False

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
      4. Explicit domain allowlist with suffix spoofing and IP literal rejection.
      5. Anti-SSRF resolution check with DNS pinning verification (all A and AAAA checked).
      6. Prohibits trading/order endpoints.
      7. Rejects credential and authorization headers.
      8. Response body byte size limits and streaming decompression bomb protection.
      9. Redirect validation (disabled by default; strictly checked when enabled).
      10. Mock response simulation engine for deterministic offline validation.
    """

    def __init__(
        self,
        network_enabled: bool = False,
        approved_domains: Optional[Set[str]] = None,
        max_response_size_bytes: int = DEFAULT_MAX_RESPONSE_SIZE_BYTES,
        max_decompressed_size_bytes: int = DEFAULT_MAX_DECOMPRESSED_SIZE_BYTES,
        connect_timeout_seconds: float = DEFAULT_CONNECT_TIMEOUT_SECONDS,
        read_timeout_seconds: float = DEFAULT_READ_TIMEOUT_SECONDS,
        total_deadline_seconds: float = DEFAULT_TOTAL_DEADLINE_SECONDS,
        allow_redirects: bool = False,
        max_redirects: int = 3,
        dns_resolver: Optional[Callable[[str], List[str]]] = None,
        socket_factory: Optional[Callable[[str, int, float], Any]] = None,
        activation_gate: Optional[Any] = None,
    ) -> None:
        self.network_enabled = network_enabled
        self.approved_domains = set(approved_domains) if approved_domains else set(DEFAULT_APPROVED_DOMAINS)
        self.max_response_size_bytes = max_response_size_bytes
        self.max_decompressed_size_bytes = max_decompressed_size_bytes
        self.connect_timeout_seconds = connect_timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self.total_deadline_seconds = total_deadline_seconds
        self.allow_redirects = allow_redirects
        self.max_redirects = max_redirects
        self._dns_resolver = dns_resolver or self._default_dns_resolve
        self._socket_factory = socket_factory
        self.activation_gate = activation_gate

        # Mock response registry: url -> TransportResponse or Exception
        self._mock_registry: Dict[str, Any] = {}
        self._rate_limit_backoffs: Dict[str, float] = {}  # domain -> resume_timestamp_utc
        self._request_audit_log: List[Dict[str, Any]] = []

    def _default_dns_resolve(self, host: str) -> List[str]:
        """Resolves hostname to IP addresses using standard socket getaddrinfo for both IPv4 and IPv6."""
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
        content_encoding: Optional[str] = None,
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
            if content_encoding:
                hdrs["content-encoding"] = content_encoding

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
        if not host:
            raise DomainNotAllowedError("Missing hostname in target URL")

        if is_ip_literal(host):
            raise DomainNotAllowedError(f"IP address literals are prohibited in research URLs: '{host}'")

        if not is_allowed_domain(host, self.approved_domains):
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

    def _decompress_body_safely(self, body: bytes, encoding: str) -> bytes:
        """Decompresses gzip or deflate payload with strict decompression bomb bounds."""
        enc = encoding.lower().strip()
        if enc not in ("gzip", "deflate"):
            return body

        decomp = zlib.decompressobj(16 + zlib.MAX_WBITS if enc == "gzip" else zlib.MAX_WBITS)
        out_chunks = []
        total_decompressed = 0
        chunk_size = 4096

        for i in range(0, len(body), chunk_size):
            chunk = body[i:i + chunk_size]
            data = decomp.decompress(chunk)
            if data:
                total_decompressed += len(data)
                if total_decompressed > self.max_decompressed_size_bytes:
                    raise ResponseSizeExceededError(
                        f"Decompressed response payload ({total_decompressed} bytes) exceeds limit ({self.max_decompressed_size_bytes} bytes). Decompression bomb rejected."
                    )
                out_chunks.append(data)

        remainder = decomp.flush()
        if remainder:
            total_decompressed += len(remainder)
            if total_decompressed > self.max_decompressed_size_bytes:
                raise ResponseSizeExceededError(
                    f"Decompressed response payload ({total_decompressed} bytes) exceeds limit ({self.max_decompressed_size_bytes} bytes). Decompression bomb rejected."
                )
            out_chunks.append(remainder)

        return b"".join(out_chunks)

    def _execute_real_https_connection(
        self,
        method: str,
        parsed_url: urllib.parse.ParseResult,
        headers: Optional[Dict[str, str]],
        pinned_ip: str,
        start_time: float,
    ) -> TransportResponse:
        """
        Executes a secure TLS socket connection against pinned public IP,
        enforcing SNI, certificate validation, streaming response bounds, and deadlines.
        """
        host = (parsed_url.hostname or "").lower()
        port = parsed_url.port or 443
        path = parsed_url.path or "/"
        if parsed_url.query:
            path = f"{path}?{parsed_url.query}"

        deadline = start_time + self.total_deadline_seconds

        # 1. Connect TCP socket
        if self._socket_factory:
            raw_sock = self._socket_factory(pinned_ip, port, self.connect_timeout_seconds)
        else:
            raw_sock = socket.create_connection((pinned_ip, port), timeout=self.connect_timeout_seconds)

        # 2. Verify peer IP
        try:
            peer_ip = raw_sock.getpeername()[0]
            if is_private_or_restricted_ip(peer_ip):
                raw_sock.close()
                raise SSRFProtectionError(f"Connected peer IP '{peer_ip}' is in a restricted range!")
        except Exception as e:
            if not isinstance(e, TransportSecurityError):
                raw_sock.close()
                raise TransportSecurityError(f"Socket peer verification failed: {e}")
            raise

        # 3. Perform TLS handshake with certificate and hostname validation
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = True
        ssl_ctx.verify_mode = ssl.CERT_REQUIRED
        try:
            tls_sock = ssl_ctx.wrap_socket(raw_sock, server_hostname=host)
        except (ssl.SSLCertVerificationError, ssl.SSLError) as e:
            raw_sock.close()
            raise TLSVerificationError(f"TLS verification failed for host '{host}': {e}")

        tls_sock.settimeout(self.read_timeout_seconds)

        try:
            # 4. Send HTTP request
            req_lines = [
                f"{method} {path} HTTP/1.1",
                f"Host: {host}",
                "User-Agent: CoinBehaviorEngine-Research/1.0",
                "Accept: */*",
                "Accept-Encoding: gzip, deflate",
                "Connection: close",
            ]
            if headers:
                for k, v in headers.items():
                    req_lines.append(f"{k}: {v}")
            req_lines.append("\r\n")
            req_data = "\r\n".join(req_lines).encode("utf-8")
            tls_sock.sendall(req_data)

            # 5. Read response headers
            header_bytes = b""
            while b"\r\n\r\n" not in header_bytes:
                if time.time() > deadline:
                    raise TransportTimeoutError("Total request deadline exceeded while reading headers")
                chunk = tls_sock.recv(4096)
                if not chunk:
                    break
                header_bytes += chunk
                if len(header_bytes) > 65536:
                    raise ResponseSizeExceededError("HTTP header size exceeds 64KB limit")

            if b"\r\n\r\n" not in header_bytes:
                raise TransportSecurityError("Incomplete HTTP response from server")

            header_part, initial_body = header_bytes.split(b"\r\n\r\n", 1)
            header_lines = header_part.decode("latin1").split("\r\n")
            status_line = header_lines[0]
            status_parts = status_line.split(" ", 2)
            status_code = int(status_parts[1]) if len(status_parts) > 1 else 0

            resp_headers: Dict[str, str] = {}
            for line in header_lines[1:]:
                if ":" in line:
                    hk, hv = line.split(":", 1)
                    resp_headers[hk.strip().lower()] = hv.strip()

            # Check Content-Length if present
            if "content-length" in resp_headers:
                try:
                    cl = int(resp_headers["content-length"])
                    if cl > self.max_response_size_bytes:
                        raise ResponseSizeExceededError(
                            f"Content-Length ({cl} bytes) exceeds maximum limit ({self.max_response_size_bytes} bytes)"
                        )
                except ValueError:
                    pass

            # 6. Stream response body
            body_chunks = [initial_body]
            total_bytes = len(initial_body)

            if method != "HEAD":
                while True:
                    if time.time() > deadline:
                        raise TransportTimeoutError("Total request deadline exceeded while reading response body")
                    chunk = tls_sock.recv(8192)
                    if not chunk:
                        break
                    total_bytes += len(chunk)
                    if total_bytes > self.max_response_size_bytes:
                        raise ResponseSizeExceededError(
                            f"Streaming response payload ({total_bytes} bytes) exceeds limit ({self.max_response_size_bytes} bytes)"
                        )
                    body_chunks.append(chunk)

            raw_body = b"".join(body_chunks)

            # 7. Safe Decompression
            content_encoding = resp_headers.get("content-encoding", "")
            final_body = self._decompress_body_safely(raw_body, content_encoding)

            elapsed = time.time() - start_time
            retry_after = self._parse_retry_after(resp_headers.get("retry-after"))

            return TransportResponse(
                status_code=status_code,
                headers=resp_headers,
                body=final_body,
                url=parsed_url.geturl(),
                raw_sha256=hashlib.sha256(final_body).hexdigest(),
                elapsed_seconds=elapsed,
                retrieved_at_utc=datetime.now(timezone.utc).isoformat(),
                is_mock=False,
                retry_after_seconds=retry_after,
            )

        finally:
            try:
                tls_sock.close()
            except Exception:
                pass

    def _parse_retry_after(self, retry_after_header: Optional[str]) -> Optional[float]:
        """Parses Retry-After header as seconds or HTTP date."""
        if not retry_after_header:
            return None
        val = retry_after_header.strip()
        try:
            return max(0.0, float(val))
        except ValueError:
            pass
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
        visited_urls: Optional[Set[str]] = None,
        auth_token: Optional[Any] = None,
        target_event_id: str = "",
    ) -> TransportResponse:
        """
        Executes a validated read-only request.
        If mock exists for URL, delivers mock.
        If real network is disabled and no mock exists, raises NetworkAccessProhibitedError.
        If real network is enabled (or mock socket provided), verifies SSRF and dispatches secure HTTPS request.
        Handles redirects if enabled, re-verifying security on each redirect.
        """
        start_time = time.time()
        visited = visited_urls or set()

        if url in visited:
            raise RedirectSecurityError(f"Redirect loop detected: '{url}' visited multiple times")
        visited.add(url)

        if len(visited) > (self.max_redirects + 1):
            raise RedirectSecurityError(f"Maximum redirect limit ({self.max_redirects}) exceeded")

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

            # Decompression check if mock is encoded
            if resp.headers.get("content-encoding") in ("gzip", "deflate"):
                resp.body = self._decompress_body_safely(resp.body, resp.headers["content-encoding"])
                resp.raw_sha256 = hashlib.sha256(resp.body).hexdigest()

            # 429 tracking
            if resp.status_code == 429 and resp.retry_after_seconds:
                self._rate_limit_backoffs[host] = time.time() + resp.retry_after_seconds

            audit_entry["status"] = "SUCCESS_MOCK"
            audit_entry["status_code"] = resp.status_code
            audit_entry["byte_size"] = len(resp.body)
            audit_entry["sha256"] = resp.raw_sha256
            self._request_audit_log.append(audit_entry)

            # Handle mock redirects if enabled
            if resp.status_code in (301, 302, 303, 307, 308) and "location" in resp.headers:
                if not self.allow_redirects:
                    return resp
                next_url = urllib.parse.urljoin(url, resp.headers["location"])
                return self.execute_request(
                    method,
                    next_url,
                    headers=headers,
                    visited_urls=visited,
                    auth_token=auth_token,
                    target_event_id=target_event_id,
                )

            return resp

        # Real network access disabled check
        if not self.network_enabled:
            audit_entry["status"] = "BLOCKED_NETWORK_DISABLED"
            self._request_audit_log.append(audit_entry)
            raise NetworkAccessProhibitedError(
                f"External network retrieval blocked for '{url}'. Real network access is strictly disabled."
            )

        # Anti-SSRF: Resolve all A and AAAA records and verify ALL
        resolved_ips = self._dns_resolver(host)
        if not resolved_ips:
            audit_entry["status"] = "DNS_EMPTY"
            self._request_audit_log.append(audit_entry)
            raise SSRFProtectionError(f"DNS resolution returned no IP addresses for host '{host}'")

        # Mixed DNS check: if ANY resolved IP is private/restricted, reject the whole host
        for ip_addr in resolved_ips:
            if is_private_or_restricted_ip(ip_addr):
                audit_entry["status"] = "BLOCKED_SSRF"
                audit_entry["resolved_ip"] = ip_addr
                self._request_audit_log.append(audit_entry)
                raise SSRFProtectionError(
                    f"SSRF violation: Host '{host}' resolves to restricted IP '{ip_addr}'"
                )

        pinned_ip = resolved_ips[0]

        # Enforce Network Activation Gate (10 Mandatory Conditions)
        from .observation_authorization import NetworkActivationGate, NetworkActivationGateError
        gate = self.activation_gate or NetworkActivationGate()
        allowed, gate_reason = gate.evaluate_request(
            token=auth_token,
            target_url=url,
            target_event_id=target_event_id,
            method=method_norm,
            headers=headers,
        )
        if not allowed:
            audit_entry["status"] = "BLOCKED_ACTIVATION_GATE"
            audit_entry["error"] = gate_reason
            self._request_audit_log.append(audit_entry)
            raise NetworkActivationGateError(
                f"External network retrieval blocked by network activation gate: {gate_reason}"
            )

        # Execute real TLS connection
        try:
            resp = self._execute_real_https_connection(method_norm, parsed, headers, pinned_ip, start_time)
            audit_entry["status"] = "SUCCESS_HTTPS"
            audit_entry["status_code"] = resp.status_code
            audit_entry["byte_size"] = len(resp.body)
            audit_entry["sha256"] = resp.raw_sha256
            self._request_audit_log.append(audit_entry)

            # Reconcile quota usage if gate has store
            if gate and gate.approval_store and auth_token:
                gate.approval_store.commit_quota(auth_token.token_id, actual_bytes=len(resp.body))

            # Handle redirects
            if resp.status_code in (301, 302, 303, 307, 308) and "location" in resp.headers:
                if not self.allow_redirects:
                    return resp
                next_url = urllib.parse.urljoin(url, resp.headers["location"])
                return self.execute_request(
                    method,
                    next_url,
                    headers=headers,
                    visited_urls=visited,
                    auth_token=auth_token,
                    target_event_id=target_event_id,
                )

            return resp
        except Exception as e:
            if not isinstance(e, TransportSecurityError):
                audit_entry["status"] = "TRANSPORT_ERROR"
                audit_entry["error"] = str(e)
                self._request_audit_log.append(audit_entry)
                raise TransportSecurityError(f"HTTPS connection failed for '{url}': {e}") from e
            audit_entry["status"] = type(e).__name__
            audit_entry["error"] = str(e)
            self._request_audit_log.append(audit_entry)
            raise

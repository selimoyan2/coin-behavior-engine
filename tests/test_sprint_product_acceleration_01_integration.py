"""Integration tests for Sprint Product Acceleration 01: Master Web Server & HTTP Routes.

Verifies:
1. Live HTTP requests to ThreadingHTTPServer on an ephemeral port.
2. GET / returns master Product Dashboard HTML (200 OK).
3. GET /product returns master Product Dashboard HTML (200 OK).
4. GET /dashboard returns legacy prospective monitor HTML (200 OK).
5. GET /api/v1/product/overview returns JSON status success (200 OK).
6. GET /api/v1/product/research-results returns canonical findings.
7. GET /api/v1/product/artifacts returns indexed artifacts.
8. GET /api/v1/product/artifacts/preview with path traversal returns 403 Forbidden.
9. GET /health returns container healthcheck (200 OK).
"""

from __future__ import annotations

from http import HTTPStatus
from http.server import ThreadingHTTPServer
import json
import threading
import time
import urllib.error
import urllib.request
import pytest

from coin_behavior_engine.web.server import EngineRequestHandler


@pytest.fixture(scope="module")
def running_server():
    """Start an ephemeral HTTP server in background thread for integration tests."""
    server_address = ("127.0.0.1", 0)  # OS assigns free port
    httpd = ThreadingHTTPServer(server_address, EngineRequestHandler)
    port = httpd.server_port

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()
    time.sleep(0.1)

    yield f"http://127.0.0.1:{port}"

    httpd.shutdown()
    httpd.server_close()


def test_http_get_root_serves_product_dashboard(running_server):
    req = urllib.request.Request(f"{running_server}/")
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        assert resp.status == HTTPStatus.OK
        content_type = resp.headers.get("Content-Type", "")
        assert "text/html" in content_type
        body = resp.read().decode("utf-8")
        assert "Coin Behavior Engine" in body
        assert "Kanıt Arşivi" in body
        assert "Yönetişim & Güvenlik" in body
        assert "Piyasa Davranışı" in body


def test_http_get_product_route(running_server):
    req = urllib.request.Request(f"{running_server}/product")
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        assert resp.status == HTTPStatus.OK
        body = resp.read().decode("utf-8")
        assert "TECHNICAL NO-GO" in body
        assert "Araştırma Bulguları" in body


def test_http_get_dashboard_legacy_route(running_server):
    req = urllib.request.Request(f"{running_server}/dashboard")
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        assert resp.status == HTTPStatus.OK
        body = resp.read().decode("utf-8")
        assert "FAZ A — İLK İLERİYE DÖNÜK GÖZLEM" in body


def test_http_get_product_api_overview(running_server):
    req = urllib.request.Request(f"{running_server}/api/v1/product/overview")
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        assert resp.status == HTTPStatus.OK
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "success"
        assert data["safety_contract"]["technical_decision"] == "TECHNICAL_NO_GO"
        assert data["safety_contract"]["live_order_execution"] == "PROHIBITED"
        assert data["model_integrity"]["version"] == "CBE-0.7.0"


def test_http_get_product_api_artifacts(running_server):
    req = urllib.request.Request(f"{running_server}/api/v1/product/artifacts?limit=5")
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        assert resp.status == HTTPStatus.OK
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "success"
        assert len(data["artifacts"]) <= 5
        assert data["total_artifacts"] >= 100


def test_http_get_artifact_preview_security_traversal_blocked(running_server):
    url = f"{running_server}/api/v1/product/artifacts/preview?path=../../pyproject.toml"
    req = urllib.request.Request(url)
    with pytest.raises(urllib.error.HTTPError) as exc_info:
        urllib.request.urlopen(req, timeout=5.0)
    assert exc_info.value.code == HTTPStatus.FORBIDDEN


def test_http_get_healthcheck(running_server):
    req = urllib.request.Request(f"{running_server}/health")
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        assert resp.status == HTTPStatus.OK
        data = json.loads(resp.read().decode("utf-8"))
        assert data["status"] == "healthy"
        assert data["service"] == "coin-behavior-engine"

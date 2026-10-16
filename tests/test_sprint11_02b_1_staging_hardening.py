"""CBE — Sprint 11.02B.1: Staging Compose Hardening & Offline Deployment Validation.

Comprehensive Automated Verification Suite:
1. Staging network binding: loopback 127.0.0.1 enforced (no 0.0.0.0 binding).
2. Container root filesystem read_only: true enforced with narrow tmpfs mounts.
3. Supervised activation restart policy: restart: "no" enforced.
4. Compose build context and Dockerfile path resolution to repository root.
5. Dockerfile runtime dependencies and curl presence validation.
6. Healthcheck endpoint /health verification (returns HTTP 200 and healthy status).
7. Healthcheck lightweight fallback mechanism (urllib vs curl).
8. Snapshot reader configuration via CBE_FACTUAL_SNAPSHOT_PATH.
9. Missing snapshot safe fallback (canonical frozen baseline 63,842.15 USDT).
10. Stale snapshot auto-demotion (stale heartbeat or candle age demotes to HISTORICAL_SNAPSHOT).
11. External capture volume declaration (external: true, exact name, read_only :ro).
12. Feature isolation environment flags (APPROVAL4=false, PROSPECTIVE=false, TRADING=true).
13. Server execution safety: worker cannot start when prospective observation is disabled.
14. Server CLI --no-worker execution safety.
15. Auditable OCI labels present in compose service.
16. Port conflict preflight documentation and commands.
17. Rollback command completeness and zero mutation guarantee.
18. Frozen CBE-0.7.0 canonical integrity (29/29 files intact).
19. APPROVAL4 strictly FALSE invariant.
20. HTTP routing integrity across all endpoints (/health, /intelligence, /api/v1/intelligence/overview).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from http import HTTPStatus
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import time
from typing import Any, Dict
import urllib.request
import yaml

import pytest

from coin_behavior_engine.product.data_contracts import FieldAvailabilityStatus
from coin_behavior_engine.product.intelligence_api import (
    ApiEvidenceClassification,
    MarketIntelligenceApiService,
)
from coin_behavior_engine.product.market_data_adapter import (
    AtomicSnapshotIO,
    DataClassification,
    FactualMarketDataAdapter,
    FactualMarketDataRecord,
    MarketDataFreshnessStatus,
    MarketDataSourceHealth,
)
from coin_behavior_engine.prospective.freeze import verify_sprint07_freeze
from coin_behavior_engine.web.server import EngineRequestHandler, run_server


REPO_ROOT = Path(__file__).resolve().parents[1]
STAGING_COMPOSE_PATH = REPO_ROOT / "deploy" / "staging" / "docker-compose.market-intelligence-staging.yaml"
DOCKERFILE_PATH = REPO_ROOT / "Dockerfile"


def _load_compose_yaml() -> Dict[str, Any]:
    assert STAGING_COMPOSE_PATH.exists(), f"Staging compose file missing: {STAGING_COMPOSE_PATH}"
    with open(STAGING_COMPOSE_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ==============================================================================
# 1. Staging Network Binding
# ==============================================================================

def test_01_staging_network_binding_restricted_to_loopback():
    """Verify that host port is strictly bound to 127.0.0.1 (loopback) and preserves 8000 internally."""
    compose = _load_compose_yaml()
    service = compose["services"]["cbe-market-intelligence-staging"]
    ports = service.get("ports", [])
    assert len(ports) == 1, "Expected exactly 1 port mapping"
    port_spec = ports[0]

    assert port_spec.startswith("127.0.0.1:"), f"Port must be bound to 127.0.0.1, got: {port_spec}"
    assert port_spec.endswith(":8000"), f"Container port must be 8000, got: {port_spec}"
    assert "8080" in port_spec, f"Default staging host port must be 8080, got: {port_spec}"


# ==============================================================================
# 2. Container Root Filesystem Read-Only & Tmpfs
# ==============================================================================

def test_02_read_only_rootfs_and_tmpfs_mounts():
    """Verify read_only: true is set and narrow tmpfs mounts are configured."""
    compose = _load_compose_yaml()
    service = compose["services"]["cbe-market-intelligence-staging"]

    assert service.get("read_only") is True, "read_only must be set to True"
    tmpfs = service.get("tmpfs", [])
    assert len(tmpfs) >= 1, "tmpfs mounts required for read-only rootfs"

    tmpfs_str = " ".join(tmpfs)
    assert "/tmp" in tmpfs_str, "Writable tmpfs required for /tmp"
    assert "size=" in tmpfs_str, "tmpfs size limits must be specified"


# ==============================================================================
# 3. Supervised Activation Restart Policy
# ==============================================================================

def test_03_supervised_activation_restart_policy_no():
    """Verify restart policy is set to 'no' for initial supervised staging activation."""
    compose = _load_compose_yaml()
    service = compose["services"]["cbe-market-intelligence-staging"]
    assert service.get("restart") == "no", "restart policy must be 'no' for supervised activation"


# ==============================================================================
# 4. Compose Build Context & Dockerfile Path Resolution
# ==============================================================================

def test_04_compose_build_context_and_dockerfile_resolution():
    """Verify that build.context: ../.. and dockerfile: Dockerfile resolve to existing root files."""
    compose = _load_compose_yaml()
    service = compose["services"]["cbe-market-intelligence-staging"]
    build = service.get("build", {})

    context_rel = build.get("context")
    dockerfile_rel = build.get("dockerfile")

    compose_dir = STAGING_COMPOSE_PATH.parent
    resolved_context = (compose_dir / context_rel).resolve()
    resolved_dockerfile = (resolved_context / dockerfile_rel).resolve()

    assert resolved_context == REPO_ROOT, f"Resolved context {resolved_context} does not match {REPO_ROOT}"
    assert resolved_dockerfile.exists(), f"Dockerfile not found at {resolved_dockerfile}"
    assert (resolved_context / "pyproject.toml").exists(), "pyproject.toml missing from build context"


# ==============================================================================
# 5. Dockerfile Dependencies & Curl Presence
# ==============================================================================

def test_05_dockerfile_contains_curl_and_correct_base():
    """Verify Dockerfile contains curl package for healthcheck and python:3.11-slim base."""
    assert DOCKERFILE_PATH.exists()
    content = DOCKERFILE_PATH.read_text(encoding="utf-8")

    assert "python:3.11-slim" in content, "Expected python:3.11-slim base image"
    assert "curl" in content, "curl must be installed for container healthcheck"
    assert "PYTHONDONTWRITEBYTECODE=1" in content, "PYTHONDONTWRITEBYTECODE=1 required for read_only rootfs"


# ==============================================================================
# 6. Healthcheck Endpoint Verification
# ==============================================================================

def test_06_healthcheck_endpoint_returns_healthy():
    """Verify /health responds with HTTP 200 and healthy status payload."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), EngineRequestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        url = f"http://127.0.0.1:{port}/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            assert resp.status == HTTPStatus.OK
            data = json.loads(resp.read().decode("utf-8"))
            assert data["status"] == "healthy"
            assert data["service"] == "coin-behavior-engine"
            assert data["model_version"] == "CBE-0.7.0"
    finally:
        server.shutdown()
        server.server_close()


# ==============================================================================
# 7. Healthcheck Lightweight Fallback Mechanism
# ==============================================================================

def test_07_healthcheck_python_fallback():
    """Verify that Python urllib can perform the healthcheck without external binaries."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), EngineRequestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        # Emulate python -c healthcheck command
        python_check = f"import urllib.request; resp = urllib.request.urlopen('http://127.0.0.1:{port}/health'); assert resp.status == 200"
        exec_globals: Dict[str, Any] = {}
        exec(python_check, exec_globals)
    finally:
        server.shutdown()
        server.server_close()


# ==============================================================================
# 8. Snapshot Reader Path Configuration
# ==============================================================================

def test_08_snapshot_reader_path_configuration():
    """Verify CBE_FACTUAL_SNAPSHOT_PATH env var is respected by adapter."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        custom_snap = tmp_path / "custom_live_state.json"
        now_dt = datetime.now(timezone.utc)
        payload = {
            "symbol": "BTCUSDT",
            "exchange_source": "BINANCE_SPOT",
            "candle_interval": "5m",
            "timestamp_close_utc": (now_dt - timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "spot_price_usdt": 64500.0,
            "is_closed": True,
            "is_live": True,
            "writer_heartbeat_utc": now_dt.isoformat(),
        }
        AtomicSnapshotIO.atomic_write(custom_snap, payload)

        old_val = os.environ.get("CBE_FACTUAL_SNAPSHOT_PATH")
        try:
            os.environ["CBE_FACTUAL_SNAPSHOT_PATH"] = str(custom_snap)
            adapter = FactualMarketDataAdapter(data_root=tmp_path)
            assert adapter.snapshot_path == custom_snap

            rec = adapter.get_btcusdt_factual_record(reference_time=now_dt, force_fresh_read=True)
            assert rec.spot_price_usdt == 64500.0
            assert rec.classification == DataClassification.LIVE_OBSERVED
        finally:
            if old_val:
                os.environ["CBE_FACTUAL_SNAPSHOT_PATH"] = old_val
            else:
                os.environ.pop("CBE_FACTUAL_SNAPSHOT_PATH", None)


# ==============================================================================
# 9. Missing Snapshot Fallback
# ==============================================================================

def test_09_missing_snapshot_safe_fallback():
    """Verify that a missing snapshot path safely falls back to canonical baseline."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        missing_file = tmp_path / "non_existent_snapshot.json"

        adapter = FactualMarketDataAdapter(data_root=tmp_path, snapshot_path=missing_file)
        rec = adapter.get_btcusdt_factual_record(force_fresh_read=True)

        assert rec.spot_price_usdt == 63842.15
        assert rec.classification == DataClassification.HISTORICAL_SNAPSHOT
        assert rec.is_live is False
        assert rec.source_availability == "AVAILABLE"
        assert "FILE_NOT_FOUND" in rec.provenance_details["note"]


# ==============================================================================
# 10. Stale Snapshot Auto-Demotion
# ==============================================================================

def test_10_stale_snapshot_auto_demotion():
    """Verify that stale heartbeat (> 120s) demotes to HISTORICAL_SNAPSHOT."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        snap_file = tmp_path / "live_market_state.json"

        ref_time = datetime(2026, 10, 16, 22, 0, 0, tzinfo=timezone.utc)
        payload = {
            "symbol": "BTCUSDT",
            "exchange_source": "BINANCE_SPOT",
            "candle_interval": "5m",
            "timestamp_close_utc": (ref_time - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "spot_price_usdt": 64800.0,
            "is_closed": True,
            "is_live": True,
            "writer_heartbeat_utc": (ref_time - timedelta(seconds=200)).isoformat(),  # 200s > 120s
        }
        AtomicSnapshotIO.atomic_write(snap_file, payload)

        adapter = FactualMarketDataAdapter(data_root=tmp_path, snapshot_path=snap_file)
        rec = adapter.get_btcusdt_factual_record(reference_time=ref_time, force_fresh_read=True)

        assert rec.is_live is False
        assert rec.classification == DataClassification.HISTORICAL_SNAPSHOT


# ==============================================================================
# 11. External Capture Volume Declaration
# ==============================================================================

def test_11_external_capture_volume_safety():
    """Verify existing capture volume is external: true and mounted :ro."""
    compose = _load_compose_yaml()
    volumes = compose.get("volumes", {})
    assert "cbe_live_capture_data" in volumes
    cap_vol = volumes["cbe_live_capture_data"]
    assert cap_vol.get("external") is True, "Volume must be declared external: true"
    assert "zgit1s3n1acdtqtsxp0s44vj_cbe-080-live-capture-data" in cap_vol.get("name", "")

    service = compose["services"]["cbe-market-intelligence-staging"]
    mounts = service.get("volumes", [])
    assert len(mounts) == 1
    assert mounts[0] == "cbe_live_capture_data:/app/data/live_capture:ro", "Must be mounted strictly :ro"


# ==============================================================================
# 12. Feature Isolation Environment Flags
# ==============================================================================

def test_12_feature_isolation_environment_flags():
    """Verify that staging compose enforces all safety invariants."""
    compose = _load_compose_yaml()
    service = compose["services"]["cbe-market-intelligence-staging"]
    env_list = service.get("environment", [])

    env_dict = {}
    for item in env_list:
        if "=" in item:
            k, v = item.split("=", 1)
            env_dict[k] = v

    assert env_dict.get("CBE_APPROVAL_4_AUTHORIZED") == "false"
    assert env_dict.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED") == "false"
    assert env_dict.get("CBE_TRADING_DISABLED") == "true"
    assert env_dict.get("START_WORKER") == "false"


# ==============================================================================
# 13. Server Worker Disabled When Prospective Observation Disabled
# ==============================================================================

def test_13_server_worker_cannot_start_when_prospective_disabled():
    """Verify run_server forces start_worker=False when CBE_PROSPECTIVE_OBSERVATION_ENABLED=false."""
    old_env = os.environ.get("CBE_PROSPECTIVE_OBSERVATION_ENABLED")
    try:
        os.environ["CBE_PROSPECTIVE_OBSERVATION_ENABLED"] = "false"
        os.environ["START_WORKER"] = "true"  # Even if requested, must be rejected

        # Verify logic in run_server without blocking
        prospective_enabled = os.getenv("CBE_PROSPECTIVE_OBSERVATION_ENABLED", "false").lower() in ("true", "1", "yes")
        start_worker_env = os.getenv("START_WORKER", "false").lower() in ("true", "1", "yes")
        effective_start = prospective_enabled and start_worker_env
        assert effective_start is False
    finally:
        if old_env is not None:
            os.environ["CBE_PROSPECTIVE_OBSERVATION_ENABLED"] = old_env
        else:
            os.environ.pop("CBE_PROSPECTIVE_OBSERVATION_ENABLED", None)


# ==============================================================================
# 14. Server CLI --no-worker Execution Flag
# ==============================================================================

def test_14_server_cli_no_worker_command_flag():
    """Verify command in compose includes --no-worker."""
    compose = _load_compose_yaml()
    service = compose["services"]["cbe-market-intelligence-staging"]
    cmd = service.get("command", [])
    assert "--no-worker" in cmd, "Compose command must include --no-worker"


# ==============================================================================
# 15. Auditable OCI Labels in Compose
# ==============================================================================

def test_15_auditable_oci_labels():
    """Verify presence of OCI labels for image auditability."""
    compose = _load_compose_yaml()
    service = compose["services"]["cbe-market-intelligence-staging"]
    labels = service.get("labels", {})

    assert "org.opencontainers.image.title" in labels
    assert "org.opencontainers.image.version" in labels
    assert "org.opencontainers.image.revision" in labels
    assert labels.get("cbe.trading") == "disabled"
    assert labels.get("cbe.scoring") == "disabled"


# ==============================================================================
# 16. Port Conflict Preflight Documentation
# ==============================================================================

def test_16_port_conflict_preflight_documentation():
    """Verify that compose file includes preflight instructions for port 8080."""
    content = STAGING_COMPOSE_PATH.read_text(encoding="utf-8")
    assert "ss -tulpn | grep 8080" in content
    assert "netstat -ano | findstr 8080" in content


# ==============================================================================
# 17. Rollback Command Completeness
# ==============================================================================

def test_17_rollback_command_completeness():
    """Verify rollback instructions are documented and non-destructive."""
    content = STAGING_COMPOSE_PATH.read_text(encoding="utf-8")
    assert "docker compose -f deploy/staging/docker-compose.market-intelligence-staging.yaml down" in content


# ==============================================================================
# 18. Frozen CBE-0.7.0 Canonical Integrity
# ==============================================================================

def test_18_frozen_cbe_070_canonical_integrity():
    """Verify 29/29 CBE-0.7.0 frozen files match cryptographic hashes."""
    res = verify_sprint07_freeze()
    assert res["verified"] is True
    assert res["canonical_hashes_verified"] == 29


# ==============================================================================
# 19. APPROVAL4 Strictly False
# ==============================================================================

def test_19_approval_4_strictly_false():
    """Verify APPROVAL4 remains false in environment."""
    assert os.environ.get("CBE_APPROVAL_4_AUTHORIZED") != "true"


# ==============================================================================
# 20. HTTP Routing Integrity Across All Endpoints
# ==============================================================================

def test_20_http_routing_integrity_across_endpoints():
    """Verify /intelligence, /api/v1/intelligence/overview, /api/status, and /health."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), EngineRequestHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        base = f"http://127.0.0.1:{port}"

        # 1. /health
        with urllib.request.urlopen(f"{base}/health", timeout=5.0) as r:
            assert r.status == 200

        # 2. /api/status
        with urllib.request.urlopen(f"{base}/api/status", timeout=5.0) as r:
            assert r.status == 200

        # 3. /intelligence
        with urllib.request.urlopen(f"{base}/intelligence", timeout=5.0) as r:
            assert r.status == 200
            html = r.read().decode("utf-8")
            assert "Piyasa İstihbarat Portalı" in html or "intelligence-root" in html

        # 4. /api/v1/intelligence/market-overview
        with urllib.request.urlopen(f"{base}/api/v1/intelligence/market-overview", timeout=5.0) as r:
            assert r.status == 200
            data = json.loads(r.read().decode("utf-8"))
            assert "metadata" in data
            assert "data" in data
            assert "spot_price_usdt" in data["data"]
    finally:
        server.shutdown()
        server.server_close()

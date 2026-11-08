"""
Sprint 23 Final Acceptance Correction Test Suite
Verifies:
1. P0 Genuine Persistent Volume Verification (10 Negative Tests + Positive Recovery)
2. P0 Global Resource Governance Multi-Process Concurrency (>= 4 Worker Processes + Worker Crash Recovery)
3. P1 Multi-Worker Shared SQLite Session Store (Multi-Worker Lifecycle, Expiration, Concurrency, Restart)
4. P1 RFC 8785 JSON Canonicalization Scheme & Backward Compatibility
"""

import hashlib
import json
import multiprocessing as mp
import os
import sqlite3
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from coin_behavior_engine.product.resource_governor import (
    FileBackedSemaphore,
    ResourceGovernor,
    ResourceLimitExceededError,
)
from coin_behavior_engine.product.session_manager import (
    SessionManager,
    SqliteSessionStore,
)
from coin_behavior_engine.product.storage_durability import (
    ResearchBackupRestoreEngine,
    StorageDurabilityEngine,
)
from coin_behavior_engine.product.research_report_evidence import (
    ResearchReportEvidenceBundleEngine,
    rfc8785_canonical_json,
    _canonicalize_payload,
)


# =============================================================================
# GROUP 1: GENUINE PERSISTENT VOLUME VERIFICATION (10 NEGATIVE TESTS)
# =============================================================================

class TestGroup1StorageDurability10Negative:
    """Strict persistent volume mount-boundary and fstype verification tests."""

    def test_neg1_writable_container_overlay_rejected(self, monkeypatch):
        """1. Writable Docker container overlay layer must be rejected as ephemeral."""
        monkeypatch.setenv("CBE_ENV", "staging")
        mock_mounts = [
            {
                "device": "overlay",
                "mount_point": "/",
                "fstype": "overlay",
                "options": "rw,relatime",
                "is_readonly": False,
                "is_tmpfs": False,
                "is_overlay": True,
            }
        ]
        info = StorageDurabilityEngine.inspect_storage_path("/app/data/unauthorized", mounts_override=mock_mounts)
        assert info["classification"] == "UNAUTHORIZED_MOUNT_ROOT"
        assert not info["verified_durable"]

        with pytest.raises(RuntimeError) as exc:
            StorageDurabilityEngine.require_durable_storage("/app/data/unauthorized", mounts_override=mock_mounts)
        assert "UNVERIFIED_PERSISTENCE" in str(exc.value)

    def test_neg2_ephemeral_tmpfs_rejected(self, monkeypatch):
        """2. Ephemeral tmpfs mounts must be rejected."""
        monkeypatch.setenv("CBE_ENV", "staging")
        mock_mounts = [
            {
                "device": "tmpfs",
                "mount_point": "/app/data/prospective",
                "fstype": "tmpfs",
                "options": "rw,nosuid,nodev",
                "is_readonly": False,
                "is_tmpfs": True,
                "is_overlay": False,
            }
        ]
        info = StorageDurabilityEngine.inspect_storage_path("/app/data/prospective", mounts_override=mock_mounts)
        assert info["is_ephemeral"]
        assert info["classification"] == "EPHEMERAL"

        with pytest.raises(RuntimeError) as exc:
            StorageDurabilityEngine.require_durable_storage("/app/data/prospective", mounts_override=mock_mounts)
        assert "EPHEMERAL_STORAGE_REJECTED" in str(exc.value)

    def test_neg3_ephemeral_ramfs_rejected(self, monkeypatch):
        """3. Ephemeral ramfs mounts must be rejected."""
        monkeypatch.setenv("CBE_ENV", "staging")
        mock_mounts = [
            {
                "device": "ramfs",
                "mount_point": "/app/data/prospective",
                "fstype": "ramfs",
                "options": "rw",
                "is_readonly": False,
                "is_tmpfs": True,
                "is_overlay": False,
            }
        ]
        info = StorageDurabilityEngine.inspect_storage_path("/app/data/prospective", mounts_override=mock_mounts)
        assert info["is_ephemeral"]
        assert info["classification"] == "EPHEMERAL"

    def test_neg4_readonly_mount_rejected(self, tmp_path, monkeypatch):
        """4. Read-only filesystems must be rejected."""
        monkeypatch.setenv("CBE_ENV", "staging")
        mock_mounts = [
            {
                "device": "/dev/sda1",
                "mount_point": "/app/data/prospective",
                "fstype": "ext4",
                "options": "ro,relatime",
                "is_readonly": True,
                "is_tmpfs": False,
                "is_overlay": False,
            }
        ]
        info = StorageDurabilityEngine.inspect_storage_path("/app/data/prospective", mounts_override=mock_mounts)
        # Even if directory is writable on test host, mount options declare read-only
        assert info["classification"] in ("READ_ONLY", "UNAVAILABLE")

    def test_neg5_symlink_escape_rejected(self, tmp_path, monkeypatch):
        """5. Symlinks escaping the authorized volume root must be detected and rejected."""
        monkeypatch.setenv("CBE_ENV", "staging")
        import re

        simulated_root = tmp_path / "simulated_prospective"
        simulated_root.mkdir()
        outside_target = tmp_path / "outside_secret"
        outside_target.mkdir()

        # Temporarily register simulated_root as authorized (without drive letter for POSIX matching)
        auth_root_posix = re.sub(r"^[a-zA-Z]:", "", str(simulated_root).replace("\\", "/"))
        monkeypatch.setattr(
            StorageDurabilityEngine,
            "AUTHORIZED_STAGING_PERSISTENT_PREFIXES",
            (auth_root_posix,),
        )

        escape_dir = simulated_root / "escaped_reports"
        escape_dir.mkdir(exist_ok=True)
        escape_path = str(escape_dir).replace("\\", "/")
        outside_posix = re.sub(r"^[a-zA-Z]:", "", str(outside_target).replace("\\", "/"))

        # Mock realpath to simulate symlink resolution pointing to outside_target
        real_realpath = os.path.realpath
        def mock_realpath(p):
            p_posix = str(p).replace("\\", "/")
            if "escaped_reports" in p_posix:
                return outside_posix
            return real_realpath(p)

        monkeypatch.setattr(os.path, "realpath", mock_realpath)

        info = StorageDurabilityEngine.inspect_storage_path(escape_path)
        assert info["symlink_escaped"]
        assert info["classification"] == "SYMLINK_ESCAPE_REJECTED"

        with pytest.raises(RuntimeError) as exc:
            StorageDurabilityEngine.require_durable_storage(escape_path)
        assert "SYMLINK_ESCAPE_REJECTED" in str(exc.value)

    def test_neg6_prefix_collision_rejected(self, monkeypatch):
        """6. Mount boundary matching must prevent prefix collisions (e.g. /app/data/prospective_fake)."""
        monkeypatch.setenv("CBE_ENV", "staging")
        mock_mounts = [
            {
                "device": "overlay",
                "mount_point": "/",
                "fstype": "overlay",
                "options": "rw",
                "is_readonly": False,
                "is_tmpfs": False,
                "is_overlay": True,
            },
            {
                "device": "/dev/sda1",
                "mount_point": "/app/data/prospective",
                "fstype": "ext4",
                "options": "rw",
                "is_readonly": False,
                "is_tmpfs": False,
                "is_overlay": False,
            },
        ]
        # /app/data/prospective_fake shares a string prefix with /app/data/prospective,
        # but is a DIFFERENT path component!
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective_fake/reports",
            mounts_override=mock_mounts,
        )
        assert info["classification"] in ("UNAUTHORIZED_MOUNT_ROOT", "CONTAINER_OVERLAY_REJECTED")
        assert not info["verified_durable"]

    def test_neg7_unauthorized_bind_mount_rejected(self, monkeypatch):
        """7. Host bind mounts outside authorized paths must be rejected."""
        monkeypatch.setenv("CBE_ENV", "staging")
        mock_mounts = [
            {
                "device": "/dev/sdb1",
                "mount_point": "/mnt/host_unauthorized",
                "fstype": "ext4",
                "options": "rw",
                "is_readonly": False,
                "is_tmpfs": False,
                "is_overlay": False,
            }
        ]
        info = StorageDurabilityEngine.inspect_storage_path(
            "/mnt/host_unauthorized/reports",
            mounts_override=mock_mounts,
        )
        assert info["classification"] == "UNAUTHORIZED_MOUNT_ROOT"
        assert not info["verified_durable"]

    def test_neg8_missing_mount_provenance_fails_closed(self, monkeypatch):
        """8. If mounts table exists but path has no proven persistent mount, fail closed."""
        monkeypatch.setenv("CBE_ENV", "staging")
        mock_mounts = [
            {
                "device": "overlay",
                "mount_point": "/",
                "fstype": "overlay",
                "options": "rw",
                "is_readonly": False,
                "is_tmpfs": False,
                "is_overlay": True,
            }
        ]
        info = StorageDurabilityEngine.inspect_storage_path(
            "/var/unregistered_dir",
            mounts_override=mock_mounts,
        )
        assert info["classification"] in ("UNAUTHORIZED_MOUNT_ROOT", "CONTAINER_OVERLAY_REJECTED")

    def test_neg9_unwritable_path_rejected(self, monkeypatch):
        """9. Storage path that cannot be written or created must be UNAVAILABLE."""
        monkeypatch.setenv("CBE_ENV", "staging")
        # An invalid path on Windows or impossible root path
        bad_path = "/non_existent_mount_root/nested/path/to/test"
        if sys.platform != "win32":
            info = StorageDurabilityEngine.inspect_storage_path(bad_path)
            assert info["classification"] in ("UNAVAILABLE", "UNAUTHORIZED_MOUNT_ROOT")
        else:
            # Simulated check
            assert StorageDurabilityEngine.inspect_storage_path("Z:\\impossible_drive\\sub")["classification"] in ("UNAVAILABLE", "UNAUTHORIZED_MOUNT_ROOT")

    def test_neg10_unauthorized_volume_id_rejected(self, monkeypatch):
        """10. Storage volume with an unapproved volume identity is rejected."""
        monkeypatch.setenv("CBE_ENV", "staging")
        mock_mounts = [
            {
                "device": "/dev/sda1",
                "mount_point": "/app/data/prospective",
                "root": "/var/lib/docker/volumes/unauthorized-volume-id-attacker/_data",
                "volume_id": "unauthorized-volume-id-attacker",
                "fstype": "ext4",
                "options": "rw",
                "is_readonly": False,
                "is_tmpfs": False,
                "is_overlay": False,
            }
        ]
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
        )
        assert info["classification"] == "UNAUTHORIZED_VOLUME_ID"
        assert not info["verified_durable"]

    def test_pos1_authorized_staging_volume_accepted(self, monkeypatch):
        """Positive test: Staging volume with verified kernel mountinfo root is PERSISTENT_VERIFIED."""
        monkeypatch.setenv("CBE_ENV", "staging")
        mock_mounts = [
            {
                "device": "/dev/sda1",
                "mount_point": "/app/data/prospective",
                "root": "/var/lib/docker/volumes/dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f/_data",
                "volume_id": "dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f",
                "fstype": "ext4",
                "options": "rw",
                "is_readonly": False,
                "is_tmpfs": False,
                "is_overlay": False,
            }
        ]
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
        )
        assert info["classification"] == "PERSISTENT_VERIFIED"
        assert info["verified_durable"]
        assert info["volume_id"] == "dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f"
        assert info["volume_provenance"] == "KERNEL_MOUNTINFO"

    def test_pos2_authorized_deployment_contract_accepted(self, monkeypatch):
        """Positive test: Authorized deployment contract validated against runtime metadata is PERSISTENT_VERIFIED."""
        monkeypatch.setenv("CBE_ENV", "staging")
        mock_mounts = [
            {
                "device": "/dev/sda1",
                "mount_point": "/app/data/prospective",
                "fstype": "ext4",
                "options": "rw",
                "is_readonly": False,
                "is_tmpfs": False,
                "is_overlay": False,
            }
        ]
        contract = {
            "authorized_volume_id": "dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f",
            "expected_destination": "/app/data/prospective",
            "expected_filesystem": "ext4",
        }
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            contract_override=contract,
        )
        assert info["classification"] == "PERSISTENT_VERIFIED"
        assert info["verified_durable"]
        assert info["volume_id"] == "dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f"
        assert info["volume_provenance"] == "DEPLOYMENT_CONTRACT"

    def test_forged_environment_without_runtime_metadata_rejected(self, monkeypatch):
        """Environment variable alone without kernel mountinfo or contract MUST be rejected."""
        monkeypatch.setenv("CBE_ENV", "staging")
        monkeypatch.setenv("CBE_AUTHORIZED_VOLUME_ID", "dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f")
        mock_mounts = [
            {
                "device": "/dev/sda1",
                "mount_point": "/app/data/prospective",
                "fstype": "ext4",
                "options": "rw",
                "is_readonly": False,
                "is_tmpfs": False,
                "is_overlay": False,
            }
        ]
        # No volume_id/root in mount, and no contract override provided
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
        )
        assert info["classification"] == "UNVERIFIABLE_VOLUME_IDENTITY"
        assert not info["verified_durable"]

    def test_contradictory_environment_volume_id_rejected(self, monkeypatch):
        """Environment variable contradicting runtime mountinfo is rejected."""
        monkeypatch.setenv("CBE_ENV", "staging")
        monkeypatch.setenv("CBE_AUTHORIZED_VOLUME_ID", "forged-contradictory-id-999")
        mock_mounts = [
            {
                "device": "/dev/sda1",
                "mount_point": "/app/data/prospective",
                "volume_id": "dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f",
                "fstype": "ext4",
                "options": "rw",
                "is_readonly": False,
                "is_tmpfs": False,
                "is_overlay": False,
            }
        ]
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
        )
        assert info["classification"] == "CONTRADICTORY_VOLUME_IDENTITY"
        assert not info["verified_durable"]

    def test_contract_destination_mismatch_rejected(self, monkeypatch):
        """Contract destination mismatching inspected path is rejected."""
        monkeypatch.setenv("CBE_ENV", "staging")
        mock_mounts = [
            {
                "device": "/dev/sda1",
                "mount_point": "/app/data/prospective",
                "fstype": "ext4",
                "options": "rw",
                "is_readonly": False,
                "is_tmpfs": False,
                "is_overlay": False,
            }
        ]
        contract = {
            "authorized_volume_id": "dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f",
            "expected_destination": "/app/data/different_destination",
            "expected_filesystem": "ext4",
        }
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            contract_override=contract,
        )
        assert info["classification"] == "UNAUTHORIZED_MOUNT_ROOT"
        assert not info["verified_durable"]

    def test_contract_filesystem_mismatch_rejected(self, monkeypatch):
        """Contract specifying ext4 when runtime mount is xfs is rejected."""
        monkeypatch.setenv("CBE_ENV", "staging")
        mock_mounts = [
            {
                "device": "/dev/sda1",
                "mount_point": "/app/data/prospective",
                "fstype": "xfs",
                "options": "rw",
                "is_readonly": False,
                "is_tmpfs": False,
                "is_overlay": False,
            }
        ]
        contract = {
            "authorized_volume_id": "dbc52dc547a4121d1fdb3bf69709337f322c62fb08d97194287f22d2d229868f",
            "expected_destination": "/app/data/prospective",
            "expected_filesystem": "ext4",
        }
        info = StorageDurabilityEngine.inspect_storage_path(
            "/app/data/prospective/reports",
            mounts_override=mock_mounts,
            contract_override=contract,
        )
        assert info["classification"] == "REJECTED_FILESYSTEM_TYPE"
        assert not info["verified_durable"]


# =============================================================================
# GROUP 2: GLOBAL RESOURCE GOVERNANCE MULTI-PROCESS CONCURRENCY
# =============================================================================

def _worker_acquire_research(slot_dir: str, duration_sec: float, out_queue: mp.Queue):
    """Worker function for multiprocess test: acquires research slot, sleeps, reports status."""
    gov = ResourceGovernor(lock_dir=slot_dir)
    try:
        start_t = time.monotonic()
        with gov.acquire_research_slot(timeout=1.5):
            acq_t = time.monotonic()
            out_queue.put({"status": "ACQUIRED", "worker_pid": os.getpid(), "start": start_t, "acquired_at": acq_t})
            time.sleep(duration_sec)
            rel_t = time.monotonic()
            out_queue.put({"status": "RELEASED", "worker_pid": os.getpid(), "released_at": rel_t})
    except ResourceLimitExceededError as e:
        out_queue.put({"status": "REJECTED", "worker_pid": os.getpid(), "error": str(e)})
    except Exception as ex:
        out_queue.put({"status": "ERROR", "worker_pid": os.getpid(), "error": str(ex)})


def _crashing_worker(slot_dir: str, ready_queue: mp.Queue):
    """Worker function that acquires slot and informs parent, then loops waiting to be killed."""
    gov = ResourceGovernor(lock_dir=slot_dir)
    try:
        with gov.acquire_research_slot(timeout=2.0):
            ready_queue.put({"status": "HOLDING_LOCK", "pid": os.getpid()})
            time.sleep(60.0)
    except Exception as e:
        ready_queue.put({"status": "ERROR", "error": str(e)})


class TestGroup2GlobalResourceGovernanceMultiprocess:
    """Cross-worker process aggregate concurrency control and failure recovery."""

    def test_multiprocess_concurrency_limit_honored(self, tmp_path):
        """
        4 independent worker processes compete for research slots (capacity = 2).
        Must ensure maximum concurrent workers holding lock never exceeds 2,
        and workers beyond limit are throttled or rejected with ResourceLimitExceededError.
        """
        slot_dir = str(tmp_path / "cbe_test_semaphores")
        gov_main = ResourceGovernor(lock_dir=slot_dir)
        assert gov_main.MAX_CONCURRENT_RESEARCH_JOBS == 2

        out_queue = mp.Queue()
        processes = []
        # Launch 4 independent worker processes simultaneously
        for _ in range(4):
            p = mp.Process(target=_worker_acquire_research, args=(slot_dir, 0.4, out_queue))
            p.daemon = True
            processes.append(p)

        for p in processes:
            p.start()

        for p in processes:
            p.join(timeout=10.0)

        results = []
        while not out_queue.empty():
            results.append(out_queue.get_nowait())

        acquired_events = [r for r in results if r["status"] == "ACQUIRED"]
        rejected_events = [r for r in results if r["status"] == "REJECTED"]
        released_events = [r for r in results if r["status"] == "RELEASED"]

        # All workers either successfully acquired (serially/in pairs) or got backpressure rejection
        assert len(acquired_events) >= 2
        assert len(acquired_events) + len(rejected_events) == 4

        # Verify active slots never exceeded 2 simultaneously
        # Check intervals of workers that acquired
        # Worker times:
        intervals = []
        for r_acq in acquired_events:
            pid = r_acq["worker_pid"]
            rel = next((r for r in released_events if r["worker_pid"] == pid), None)
            if rel:
                intervals.append((r_acq["acquired_at"], rel["released_at"]))

        # Verify instantaneous active slots never exceeded 2 simultaneously at any point in time
        sample_points = [s + 0.005 for s, e in intervals]
        if sample_points:
            max_concurrent = max(sum(1 for s, e in intervals if s <= t < e) for t in sample_points)
            assert max_concurrent <= 2, f"Concurrency limit of 2 was violated! Observed max simultaneous: {max_concurrent}"

    def test_worker_crash_kernel_lock_cleanup(self, tmp_path):
        """
        Simulate a worker process crash (SIGKILL/terminate) holding a lock.
        The operating system kernel must release file locks automatically,
        allowing subsequent workers to acquire the permit immediately.
        """
        slot_dir = str(tmp_path / "cbe_test_crash_sem")
        ready_queue = mp.Queue()

        # Start worker that holds a slot
        p = mp.Process(target=_crashing_worker, args=(slot_dir, ready_queue))
        p.daemon = True
        p.start()

        # Wait until it holds the lock
        msg = ready_queue.get(timeout=5.0)
        assert msg["status"] == "HOLDING_LOCK"

        # Now abruptly kill the worker (crash simulation)
        p.terminate()
        p.join(timeout=3.0)

        # Parent or new worker should be able to acquire slots up to max limit without deadlock!
        gov = ResourceGovernor(lock_dir=slot_dir)
        with gov.acquire_research_slot(timeout=1.0):
            with gov.acquire_research_slot(timeout=1.0):
                # Successfully acquired both permits!
                pass


# =============================================================================
# GROUP 3: MULTI-WORKER SHARED SQLITE SESSION STORE
# =============================================================================

def _worker_create_session(db_path: str, op_token: str, out_q: mp.Queue):
    sm = SessionManager(db_path=db_path)
    try:
        rec = sm.create_session(op_token, client_ip="192.168.1.10", user_agent="WorkerProcessA/1.0")
        out_q.put({"status": "SUCCESS", "session_id": rec.session_id, "csrf_token": rec.csrf_token})
    except Exception as e:
        out_q.put({"status": "ERROR", "error": str(e)})


def _worker_validate_session(db_path: str, session_id: str, csrf_token: str, out_q: mp.Queue):
    sm = SessionManager(db_path=db_path)
    try:
        valid, reason, rec = sm.validate_session(session_id, csrf_token=csrf_token, check_csrf=True)
        out_q.put({"status": "SUCCESS", "valid": valid, "reason": reason})
    except Exception as e:
        out_q.put({"status": "ERROR", "error": str(e)})


def _worker_revoke_session(db_path: str, session_id: str, out_q: mp.Queue):
    sm = SessionManager(db_path=db_path)
    try:
        revoked = sm.revoke_session(session_id)
        out_q.put({"status": "SUCCESS", "revoked": revoked})
    except Exception as e:
        out_q.put({"status": "ERROR", "error": str(e)})


class TestGroup3MultiWorkerSessions:
    """Multi-process lifecycle and transaction tests for SQLite WAL session store."""

    @pytest.fixture
    def test_op_token(self, monkeypatch):
        tok = "test-operator-multiworker-sec-key-01"
        monkeypatch.setenv("CBE_OPERATOR_TOKEN", tok)
        monkeypatch.setenv("CBE_ENV", "development")
        return tok

    def test_multi_worker_session_lifecycle(self, tmp_path, test_op_token):
        """
        Verify multi-worker session coordination across 4 distinct worker processes:
        1. Worker A creates session.
        2. Worker B validates session -> VALID.
        3. Worker C revokes session -> REVOKED.
        4. Worker D validates session -> REJECTED (SESSION_REVOKED).
        """
        db_path = str(tmp_path / "sessions.db")
        q_a = mp.Queue()
        q_b = mp.Queue()
        q_c = mp.Queue()
        q_d = mp.Queue()

        # Step 1: Worker A logs in
        p_a = mp.Process(target=_worker_create_session, args=(db_path, test_op_token, q_a))
        p_a.start()
        p_a.join(timeout=5.0)
        res_a = q_a.get_nowait()
        assert res_a["status"] == "SUCCESS"
        session_id = res_a["session_id"]
        csrf_token = res_a["csrf_token"]

        # Step 2: Worker B validates session
        p_b = mp.Process(target=_worker_validate_session, args=(db_path, session_id, csrf_token, q_b))
        p_b.start()
        p_b.join(timeout=5.0)
        res_b = q_b.get_nowait()
        assert res_b["status"] == "SUCCESS"
        assert res_b["valid"]
        assert res_b["reason"] == "SESSION_VALID"

        # Step 3: Worker C logs out (revokes session)
        p_c = mp.Process(target=_worker_revoke_session, args=(db_path, session_id, q_c))
        p_c.start()
        p_c.join(timeout=5.0)
        res_c = q_c.get_nowait()
        assert res_c["status"] == "SUCCESS"
        assert res_c["revoked"]

        # Step 4: Worker D validates revoked session
        p_d = mp.Process(target=_worker_validate_session, args=(db_path, session_id, csrf_token, q_d))
        p_d.start()
        p_d.join(timeout=5.0)
        res_d = q_d.get_nowait()
        assert res_d["status"] == "SUCCESS"
        assert not res_d["valid"]
        assert res_d["reason"] == "SESSION_REVOKED"

    def test_session_expiration_and_cleanup(self, tmp_path, test_op_token):
        """Expired sessions are rejected and pruned by cleanup."""
        db_path = str(tmp_path / "sessions_exp.db")
        sm = SessionManager(db_path=db_path)

        # Create session with 0s TTL
        rec = sm.create_session(test_op_token, ttl_seconds=-1)
        valid, reason, _ = sm.validate_session(rec.session_id)
        assert not valid
        assert reason == "SESSION_EXPIRED"

        # Prune expired
        cleaned = sm.store.cleanup_expired_sessions()
        assert cleaned >= 1

    def test_restart_durability(self, tmp_path, test_op_token):
        """Sessions survive process restart and re-instantiation."""
        db_path = str(tmp_path / "sessions_restart.db")
        sm1 = SessionManager(db_path=db_path)
        rec = sm1.create_session(test_op_token, ttl_seconds=3600)
        sid = rec.session_id

        # Destroy first instance
        del sm1

        # Create new instance pointing to same SQLite DB
        sm2 = SessionManager(db_path=db_path)
        valid, reason, stored_rec = sm2.validate_session(sid)
        assert valid
        assert reason == "SESSION_VALID"
        assert stored_rec.session_id == sid


# =============================================================================
# GROUP 4: RFC 8785 CANONICALIZATION & COMPATIBILITY
# =============================================================================

class TestGroup4RFC8785CanonicalizationAndCompatibility:
    """RFC 8785 compliance and historical backward compatibility verification."""

    def test_rfc8785_number_formatting(self):
        """RFC 8785 and ECMAScript number serialization vectors."""
        test_cases = [
            ({"val": 0.0}, b'{"val":0}'),
            ({"val": -0.0}, b'{"val":0}'),
            ({"val": 1.0}, b'{"val":1}'),
            ({"val": 42}, b'{"val":42}'),
            ({"val": 0.05}, b'{"val":0.05}'),
            ({"val": 1e-5}, b'{"val":0.00001}'),
            ({"val": 1e-6}, b'{"val":0.000001}'),
            ({"val": 1e-7}, b'{"val":1e-7}'),
            ({"val": 1e20}, b'{"val":100000000000000000000}'),
            ({"val": 1e21}, b'{"val":1e+21}'),
            ({"val": -1e21}, b'{"val":-1e+21}'),
        ]
        for obj, expected in test_cases:
            res = rfc8785_canonical_json(obj)
            assert res == expected, f"Failed for {obj}: expected {expected}, got {res}"

    def test_rfc8785_unicode_supplementary_characters_and_utf16_ordering(self):
        """RFC 8785 requires UTF-16 code unit ordering and valid Unicode supplementary characters."""
        # \U0001F600 (surrogate pair D83D DE00 in UTF-16) comes before \uFFFF in UTF-16 code unit order
        # whereas in UTF-8 \xF0 > \xEF
        obj = {
            "\uffff": 1,
            "\U0001F600": 2,
            "a": 3,
            "\u00e9": 4,
        }
        res = rfc8785_canonical_json(obj)
        # Expected UTF-16 code unit order: "a" (0x0061) < "\u00e9" (0x00e9) < "\U0001F600" (0xd83d...) < "\uffff" (0xffff)
        expected = b'{"a":3,"\xc3\xa9":4,"\xf0\x9f\x98\x80":2,"\xef\xbf\xbf":1}'
        assert res == expected

    def test_rfc8785_string_escaping(self):
        """RFC 8785 requires standard escaping for quotes, backslashes, and control characters."""
        obj = {
            "quote": '"',
            "backslash": "\\",
            "newline": "\n",
            "carriage_return": "\r",
            "tab": "\t",
            "ctrl": "\x00\x1f",
        }
        res = rfc8785_canonical_json(obj)
        expected = b'{"backslash":"\\\\","carriage_return":"\\r","ctrl":"\\u0000\\u001f","newline":"\\n","quote":"\\"","tab":"\\t"}'
        assert res == expected

    def test_rfc8785_non_finite_numbers_rejected(self):
        """Non-finite numbers (NaN, Infinity, -Infinity) must be rejected."""
        import math
        for bad_val in [float("nan"), float("inf"), float("-inf")]:
            with pytest.raises(Exception):
                rfc8785_canonical_json({"val": bad_val})

    def test_rfc8785_large_integers_outside_ieee754_rejected(self):
        """Integers outside safe IEEE-754 range [-(2^53 - 1), 2^53 - 1] must be rejected."""
        safe_max = 9007199254740991  # 2^53 - 1
        safe_min = -9007199254740991
        # Safe should pass
        assert rfc8785_canonical_json({"v": safe_max}) == b'{"v":9007199254740991}'
        assert rfc8785_canonical_json({"v": safe_min}) == b'{"v":-9007199254740991}'

        # Outside safe range should raise error
        with pytest.raises(Exception):
            rfc8785_canonical_json({"v": 2**53})
        with pytest.raises(Exception):
            rfc8785_canonical_json({"v": -(2**53)})
        with pytest.raises(Exception):
            rfc8785_canonical_json({"v": 2**64})

    def test_rfc8785_sorted_keys_and_no_whitespace(self):
        """Keys must be sorted lexicographically and all spaces stripped."""
        obj = {
            "z": 1,
            "a": "hello world",
            "m": [3, 2, 1],
            "nested": {"beta": True, "alpha": None},
        }
        res = rfc8785_canonical_json(obj)
        expected = b'{"a":"hello world","m":[3,2,1],"nested":{"alpha":null,"beta":true},"z":1}'
        assert res == expected

    def test_evidence_bundle_creation_and_rfc8785_verification(self):
        """New evidence bundles are generated and verified via RFC-8785."""
        engine = ResearchReportEvidenceBundleEngine()
        sample_report = {
            "report_metadata": {
                "report_id": "RPT-20261108-RFC01",
                "title": "RFC 8785 Test Report",
                "generated_at_utc": "2026-11-08T00:00:00Z",
                "dataset_manifest_version": "V2_CANONICAL_2026_V1",
            },
            "historical_scope": {
                "asset": "BTCUSDT",
                "start_utc": "2022-06-01T00:00:00Z",
                "end_utc": "2022-06-03T00:00:00Z",
                "dataset_manifest_version": "V2_CANONICAL_2026_V1",
            },
            "canonical_model_identity": {
                "version": "CBE-0.7.0",
                "status": "STRICTLY_FROZEN",
                "parameter_mutations": 0,
            },
            "statistical_evidence": {
                "predeclared_holdout_criteria_satisfied": True,
                "p_value": 0.012,
            },
            "evidence_provenance": {
                "dataset_manifest_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "source_commit_sha": "db3bb63e1aca90582847880e80abd9e87938b142",
            },
        }
        bundle = engine.create_evidence_bundle(sample_report)
        assert bundle["bundle_metadata"]["canonicalization_scheme"] == "RFC-8785"
        ver = engine.verify_evidence_bundle(bundle)

        assert ver["valid"]
        assert ver["canonical_scheme"] == "RFC-8785"
        assert ver["recorded_checksum"] == ver["recomputed_checksum"]

    def test_legacy_bundle_verification_compatibility(self):
        """Historical evidence bundles signed with CBE-CANONICAL-JSON-v1 remain valid."""
        engine = ResearchReportEvidenceBundleEngine()
        sample_report = {
            "report_metadata": {
                "report_id": "RPT-20261108-LEGACY01",
                "title": "Legacy Test Report",
                "generated_at_utc": "2026-11-08T00:00:00Z",
                "dataset_manifest_version": "V2_CANONICAL_2026_V1",
            },
            "historical_scope": {
                "asset": "BTCUSDT",
                "start_utc": "2022-06-01T00:00:00Z",
                "end_utc": "2022-06-03T00:00:00Z",
                "dataset_manifest_version": "V2_CANONICAL_2026_V1",
            },
            "canonical_model_identity": {
                "version": "CBE-0.7.0",
                "status": "STRICTLY_FROZEN",
                "parameter_mutations": 0,
            },
            "statistical_evidence": {
                "predeclared_holdout_criteria_satisfied": True,
                "p_value": 0.012,
            },
            "evidence_provenance": {
                "dataset_manifest_sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                "source_commit_sha": "db3bb63e1aca90582847880e80abd9e87938b142",
            },
        }
        bundle = engine.create_evidence_bundle(sample_report)

        # Force recorded checksum to legacy checksum and specify legacy scheme
        legacy_bytes = json.dumps(_canonicalize_payload(bundle["payload"]), sort_keys=True, ensure_ascii=False).encode("utf-8")
        legacy_chk = hashlib.sha256(legacy_bytes).hexdigest()
        bundle["bundle_metadata"]["package_checksum_sha256"] = legacy_chk
        bundle["bundle_metadata"]["canonicalization_scheme"] = "CBE-CANONICAL-JSON-v1"

        ver = engine.verify_evidence_bundle(bundle)
        assert ver["valid"]
        assert ver["canonical_scheme"] == "CBE-CANONICAL-JSON-v1"

        ver = engine.verify_evidence_bundle(bundle)
        assert ver["valid"]
        assert ver["canonical_scheme"] == "CBE-CANONICAL-JSON-v1"

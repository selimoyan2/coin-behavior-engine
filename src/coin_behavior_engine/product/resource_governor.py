"""
Resource Governor and Concurrency Protection Module
Sprint 23 — Enterprise-Grade Security Hardening, Multi-Process Concurrency & Operational Readiness

Protects shared VPS hardware from resource exhaustion:
- Enforces concurrency semaphores for heavy research, PDF rendering, and verification tasks.
- Validates payload size and historical candle budgets.
- Bounded LRU caching with canonical provenance-aware cache keys.
- Transparent backpressure with structured HTTP 429/503 signals.
"""

from __future__ import annotations

import collections
import os
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple


class ResourceLimitExceededError(RuntimeError):
    """Raised when concurrency or resource capacity budget is exceeded."""
    def __init__(self, message: str, retry_after_sec: int = 5):
        super().__init__(message)
        self.retry_after_sec = retry_after_sec


class FileBackedSemaphore:
    """
    Cross-worker and cross-process aggregate concurrency semaphore backed by OS file locks.
    Kernel automatically closes file descriptors and releases flock locks on worker exit or crash.
    """

    def __init__(self, name: str, max_permits: int, lock_dir: Optional[str | Path] = None):
        self.name = name
        self.max_permits = max(1, int(max_permits))
        if lock_dir:
            self.lock_dir = Path(lock_dir)
        else:
            base_dir = os.environ.get("CBE_LOCK_DIR")
            if not base_dir:
                if sys.platform == "win32":
                    base_dir = os.path.join(tempfile.gettempdir(), "cbe_locks")
                else:
                    base_dir = "/tmp/cbe_locks"
            self.lock_dir = Path(base_dir) / "semaphores" / name

        self.lock_dir.mkdir(parents=True, exist_ok=True)
        self._local_lock = threading.Lock()
        # Thread/process tracking: thread_ident -> (slot_index, open_fd)
        self._acquired_slots: Dict[int, Tuple[int, int]] = {}

    def acquire(self, timeout: float = 5.0) -> bool:
        """
        Attempts to acquire any available slot within timeout.
        Returns True if acquired, False on timeout.
        """
        start_time = time.monotonic()
        tid = threading.get_ident()

        while True:
            for slot_idx in range(self.max_permits):
                slot_path = self.lock_dir / f"slot_{slot_idx}.lock"
                try:
                    fd = os.open(str(slot_path), os.O_CREAT | os.O_RDWR, 0o600)
                    if sys.platform != "win32":
                        import fcntl
                        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    else:
                        import msvcrt
                        # Seek to offset 0 and lock 1 byte
                        os.lseek(fd, 0, os.SEEK_SET)
                        if os.write(fd, b"\x00") != 1:
                            pass
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)

                    with self._local_lock:
                        self._acquired_slots[tid] = (slot_idx, fd)
                    return True
                except (BlockingIOError, OSError, PermissionError):
                    if "fd" in locals():
                        try:
                            os.close(fd)
                        except Exception:
                            pass
                    continue

            if (time.monotonic() - start_time) >= timeout:
                return False
            time.sleep(0.02)

    def release(self) -> None:
        """Releases the slot held by current thread/worker."""
        tid = threading.get_ident()
        with self._local_lock:
            slot_info = self._acquired_slots.pop(tid, None)

        if slot_info is not None:
            slot_idx, fd = slot_info
            try:
                if sys.platform != "win32":
                    import fcntl
                    try:
                        fcntl.flock(fd, fcntl.LOCK_UN)
                    except Exception:
                        pass
                else:
                    import msvcrt
                    try:
                        os.lseek(fd, 0, os.SEEK_SET)
                        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                    except Exception:
                        pass
            finally:
                try:
                    os.close(fd)
                except Exception:
                    pass

    def get_active_count(self) -> int:
        """Returns the number of currently acquired slots across all worker processes."""
        active = 0
        for slot_idx in range(self.max_permits):
            slot_path = self.lock_dir / f"slot_{slot_idx}.lock"
            if not slot_path.exists():
                continue
            fd = None
            try:
                fd = os.open(str(slot_path), os.O_CREAT | os.O_RDWR, 0o600)
                if sys.platform != "win32":
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(fd, fcntl.LOCK_UN)
                else:
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                os.close(fd)
                fd = None
            except (BlockingIOError, OSError, PermissionError):
                active += 1
                if fd is not None:
                    try:
                        os.close(fd)
                    except Exception:
                        pass
        return active

    def __enter__(self):
        if not self.acquire():
            raise ResourceLimitExceededError(f"Failed to acquire slot in pool '{self.name}'")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class ResourceGovernor:
    """Central governor for resource limits, job concurrency, and provenance-aware caching."""

    MAX_CONCURRENT_RESEARCH_JOBS = int(os.environ.get("CBE_MAX_CONCURRENT_RESEARCH_JOBS", "2"))
    MAX_CONCURRENT_PDF_JOBS = int(os.environ.get("CBE_MAX_CONCURRENT_PDF_JOBS", "2"))
    MAX_CONCURRENT_EVIDENCE_JOBS = int(os.environ.get("CBE_MAX_CONCURRENT_EVIDENCE_JOBS", "4"))

    MAX_REPORT_PAYLOAD_BYTES = int(os.environ.get("CBE_MAX_REPORT_PAYLOAD_BYTES", str(2 * 1024 * 1024)))  # 2 MB
    MAX_CANDLE_COUNT_BUDGET = int(os.environ.get("CBE_MAX_CANDLE_COUNT_BUDGET", "5000"))
    MAX_EXECUTION_TIMEOUT_SECONDS = float(os.environ.get("CBE_MAX_EXECUTION_TIMEOUT_SEC", "60.0"))

    def __init__(self, lock_dir: Optional[str | Path] = None):
        self.lock_dir = lock_dir
        self._research_sem = FileBackedSemaphore("research", self.MAX_CONCURRENT_RESEARCH_JOBS, lock_dir=lock_dir)
        self._pdf_sem = FileBackedSemaphore("pdf", self.MAX_CONCURRENT_PDF_JOBS, lock_dir=lock_dir)
        self._evidence_sem = FileBackedSemaphore("evidence", self.MAX_CONCURRENT_EVIDENCE_JOBS, lock_dir=lock_dir)

        self._active_research = 0
        self._active_pdf = 0
        self._active_evidence = 0
        self._rejected_count = 0
        self._lock = threading.Lock()

        # Bounded LRU Cache: (key) -> (timestamp, data)
        self._cache_capacity = 64
        self._cache: collections.OrderedDict = collections.OrderedDict()
        self._cache_lock = threading.Lock()

    @contextmanager
    def acquire_research_slot(self, timeout: float = 5.0):
        """Acquires a concurrency slot for heavy research/report generation."""
        acquired = False
        try:
            if hasattr(self._research_sem, "acquire"):
                # Handle timeout argument if supported
                import inspect
                sig = inspect.signature(self._research_sem.acquire)
                if "timeout" in sig.parameters:
                    acquired = self._research_sem.acquire(timeout=timeout)
                else:
                    acquired = self._research_sem.acquire()
            else:
                acquired = True
        except Exception:
            acquired = False

        if not acquired:
            with self._lock:
                self._rejected_count += 1
            raise ResourceLimitExceededError(
                "CONCURRENCY_LIMIT_EXCEEDED: Maximum concurrent research jobs reached. "
                "The platform is operating under shared VPS resource limits.",
                retry_after_sec=5,
            )
        with self._lock:
            self._active_research += 1
        try:
            yield
        finally:
            with self._lock:
                self._active_research = max(0, self._active_research - 1)
            try:
                self._research_sem.release()
            except Exception:
                pass

    @contextmanager
    def acquire_pdf_slot(self, timeout: float = 5.0):
        """Acquires a concurrency slot for PDF chart rendering."""
        acquired = False
        try:
            if hasattr(self._pdf_sem, "acquire"):
                import inspect
                sig = inspect.signature(self._pdf_sem.acquire)
                if "timeout" in sig.parameters:
                    acquired = self._pdf_sem.acquire(timeout=timeout)
                else:
                    acquired = self._pdf_sem.acquire()
            else:
                acquired = True
        except Exception:
            acquired = False

        if not acquired:
            with self._lock:
                self._rejected_count += 1
            raise ResourceLimitExceededError(
                "CONCURRENCY_LIMIT_EXCEEDED: Maximum concurrent PDF export jobs reached.",
                retry_after_sec=3,
            )
        with self._lock:
            self._active_pdf += 1
        try:
            yield
        finally:
            with self._lock:
                self._active_pdf = max(0, self._active_pdf - 1)
            try:
                self._pdf_sem.release()
            except Exception:
                pass

    @contextmanager
    def acquire_evidence_slot(self, timeout: float = 5.0):
        """Acquires a concurrency slot for evidence verification."""
        acquired = False
        try:
            if hasattr(self._evidence_sem, "acquire"):
                import inspect
                sig = inspect.signature(self._evidence_sem.acquire)
                if "timeout" in sig.parameters:
                    acquired = self._evidence_sem.acquire(timeout=timeout)
                else:
                    acquired = self._evidence_sem.acquire()
            else:
                acquired = True
        except Exception:
            acquired = False

        if not acquired:
            with self._lock:
                self._rejected_count += 1
            raise ResourceLimitExceededError(
                "CONCURRENCY_LIMIT_EXCEEDED: Maximum concurrent evidence verification jobs reached.",
                retry_after_sec=2,
            )
        with self._lock:
            self._active_evidence += 1
        try:
            yield
        finally:
            with self._lock:
                self._active_evidence = max(0, self._active_evidence - 1)
            try:
                self._evidence_sem.release()
            except Exception:
                pass

    def validate_payload_size(self, payload_bytes: bytes) -> None:
        """Validates that incoming request payload does not exceed configured size limit."""
        if len(payload_bytes) > self.MAX_REPORT_PAYLOAD_BYTES:
            raise ValueError(
                f"PAYLOAD_TOO_LARGE: Request size {len(payload_bytes)} bytes exceeds limit of "
                f"{self.MAX_REPORT_PAYLOAD_BYTES} bytes."
            )

    def validate_candle_count(self, candle_count: int) -> None:
        """Validates that requested historical period candle count does not exceed budget."""
        if candle_count > self.MAX_CANDLE_COUNT_BUDGET:
            raise ValueError(
                f"CANDLE_BUDGET_EXCEEDED: Requested {candle_count} candles exceeds limit of "
                f"{self.MAX_CANDLE_COUNT_BUDGET} candles."
            )

    @staticmethod
    def get_cgroup_limits() -> Dict[str, Any]:
        """Inspects Docker/Linux cgroup limits for CPU, memory, and PIDs."""
        limits: Dict[str, Any] = {
            "cgroup_version": "none",
            "cpu_limit_cores": None,
            "memory_limit_mb": None,
            "pids_max": None,
        }
        if sys.platform == "win32":
            return limits

        # Check cgroup v2
        cgroup2_path = Path("/sys/fs/cgroup")
        if (cgroup2_path / "cgroup.controllers").exists():
            limits["cgroup_version"] = "v2"
            cpu_max = cgroup2_path / "cpu.max"
            if cpu_max.exists():
                try:
                    quota, period = cpu_max.read_text().strip().split()
                    if quota != "max":
                        limits["cpu_limit_cores"] = round(float(quota) / float(period), 2)
                except Exception:
                    pass
            mem_max = cgroup2_path / "memory.max"
            if mem_max.exists():
                try:
                    val = mem_max.read_text().strip()
                    if val != "max":
                        limits["memory_limit_mb"] = round(int(val) / (1024 * 1024), 2)
                except Exception:
                    pass
            pids_max = cgroup2_path / "pids.max"
            if pids_max.exists():
                try:
                    pval = pids_max.read_text().strip()
                    if pval != "max":
                        limits["pids_max"] = int(pval)
                except Exception:
                    pass
            return limits

        # Check cgroup v1
        cgroup1_cpu = Path("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
        cgroup1_period = Path("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
        cgroup1_mem = Path("/sys/fs/cgroup/memory/memory.limit_in_bytes")
        cgroup1_pids = Path("/sys/fs/cgroup/pids/pids.max")

        if cgroup1_cpu.exists() or cgroup1_mem.exists():
            limits["cgroup_version"] = "v1"
            if cgroup1_cpu.exists() and cgroup1_period.exists():
                try:
                    quota = int(cgroup1_cpu.read_text().strip())
                    period = int(cgroup1_period.read_text().strip())
                    if quota > 0 and period > 0:
                        limits["cpu_limit_cores"] = round(quota / period, 2)
                except Exception:
                    pass
            if cgroup1_mem.exists():
                try:
                    mval = int(cgroup1_mem.read_text().strip())
                    if mval < (1 << 60):
                        limits["memory_limit_mb"] = round(mval / (1024 * 1024), 2)
                except Exception:
                    pass
            if cgroup1_pids.exists():
                try:
                    limits["pids_max"] = int(cgroup1_pids.read_text().strip())
                except Exception:
                    pass

        return limits

    def get_resource_status(self) -> Dict[str, Any]:
        """Compiles current active jobs and resource utilization status across workers."""
        mem_rss_mb = self.get_memory_rss_mb()
        active_res = (
            self._research_sem.get_active_count()
            if isinstance(self._research_sem, FileBackedSemaphore)
            else self._active_research
        )
        active_pdf = (
            self._pdf_sem.get_active_count()
            if isinstance(self._pdf_sem, FileBackedSemaphore)
            else self._active_pdf
        )
        active_ev = (
            self._evidence_sem.get_active_count()
            if isinstance(self._evidence_sem, FileBackedSemaphore)
            else self._active_evidence
        )

        with self._lock:
            return {
                "active_research_jobs": active_res,
                "max_research_jobs": self.MAX_CONCURRENT_RESEARCH_JOBS,
                "active_pdf_jobs": active_pdf,
                "max_pdf_jobs": self.MAX_CONCURRENT_PDF_JOBS,
                "active_evidence_jobs": active_ev,
                "max_evidence_jobs": self.MAX_CONCURRENT_EVIDENCE_JOBS,
                "total_rejected_jobs": self._rejected_count,
                "memory_rss_mb": mem_rss_mb,
                "cache_entries": len(self._cache),
                "cgroup_limits": self.get_cgroup_limits(),
            }

    @staticmethod
    def get_memory_rss_mb() -> float:
        """Returns current process Resident Set Size (RSS) in megabytes."""
        try:
            if sys.platform != "win32" and os.path.exists("/proc/self/statm"):
                with open("/proc/self/statm", "r") as f:
                    pages = int(f.read().split()[1])
                    page_size = os.sysconf("SC_PAGE_SIZE")
                    return round((pages * page_size) / (1024 * 1024), 2)
            else:
                import psutil
                return round(psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024), 2)
        except Exception:
            return 0.0

    # Provenance-Aware LRU Cache
    def get_cached(self, key: str) -> Optional[Any]:
        with self._cache_lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        return None

    def set_cached(self, key: str, value: Any) -> None:
        with self._cache_lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            if len(self._cache) > self._cache_capacity:
                self._cache.popitem(last=False)

    def clear_cache(self) -> None:
        with self._cache_lock:
            self._cache.clear()


# Global singleton instance
resource_governor = ResourceGovernor()

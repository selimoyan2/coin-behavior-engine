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
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, Optional, Tuple


class ResourceLimitExceededError(RuntimeError):
    """Raised when concurrency or resource capacity budget is exceeded."""
    def __init__(self, message: str, retry_after_sec: int = 5):
        super().__init__(message)
        self.retry_after_sec = retry_after_sec


class ResourceGovernor:
    """Central governor for resource limits, job concurrency, and provenance-aware caching."""

    MAX_CONCURRENT_RESEARCH_JOBS = int(os.environ.get("CBE_MAX_CONCURRENT_RESEARCH_JOBS", "2"))
    MAX_CONCURRENT_PDF_JOBS = int(os.environ.get("CBE_MAX_CONCURRENT_PDF_JOBS", "2"))
    MAX_CONCURRENT_EVIDENCE_JOBS = int(os.environ.get("CBE_MAX_CONCURRENT_EVIDENCE_JOBS", "4"))

    MAX_REPORT_PAYLOAD_BYTES = int(os.environ.get("CBE_MAX_REPORT_PAYLOAD_BYTES", str(2 * 1024 * 1024)))  # 2 MB
    MAX_CANDLE_COUNT_BUDGET = int(os.environ.get("CBE_MAX_CANDLE_COUNT_BUDGET", "5000"))
    MAX_EXECUTION_TIMEOUT_SECONDS = float(os.environ.get("CBE_MAX_EXECUTION_TIMEOUT_SEC", "60.0"))

    def __init__(self):
        self._research_sem = threading.Semaphore(self.MAX_CONCURRENT_RESEARCH_JOBS)
        self._pdf_sem = threading.Semaphore(self.MAX_CONCURRENT_PDF_JOBS)
        self._evidence_sem = threading.Semaphore(self.MAX_CONCURRENT_EVIDENCE_JOBS)

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
        acquired = self._research_sem.acquire(timeout=timeout)
        if not acquired:
            with self._lock:
                self._rejected_count += 1
            raise ResourceLimitExceededError(
                "CONCURRENCY_LIMIT_EXCEEDED: Maximum concurrent research jobs reached. "
                "The platform is operating under shared VPS resource limits.",
                retry_after_sec=5
            )
        with self._lock:
            self._active_research += 1
        try:
            yield
        finally:
            with self._lock:
                self._active_research = max(0, self._active_research - 1)
            self._research_sem.release()

    @contextmanager
    def acquire_pdf_slot(self, timeout: float = 5.0):
        """Acquires a concurrency slot for PDF chart rendering."""
        acquired = self._pdf_sem.acquire(timeout=timeout)
        if not acquired:
            with self._lock:
                self._rejected_count += 1
            raise ResourceLimitExceededError(
                "CONCURRENCY_LIMIT_EXCEEDED: Maximum concurrent PDF export jobs reached.",
                retry_after_sec=3
            )
        with self._lock:
            self._active_pdf += 1
        try:
            yield
        finally:
            with self._lock:
                self._active_pdf = max(0, self._active_pdf - 1)
            self._pdf_sem.release()

    @contextmanager
    def acquire_evidence_slot(self, timeout: float = 5.0):
        """Acquires a concurrency slot for evidence verification."""
        acquired = self._evidence_sem.acquire(timeout=timeout)
        if not acquired:
            with self._lock:
                self._rejected_count += 1
            raise ResourceLimitExceededError(
                "CONCURRENCY_LIMIT_EXCEEDED: Maximum concurrent evidence verification jobs reached.",
                retry_after_sec=2
            )
        with self._lock:
            self._active_evidence += 1
        try:
            yield
        finally:
            with self._lock:
                self._active_evidence = max(0, self._active_evidence - 1)
            self._evidence_sem.release()

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

    def get_resource_status(self) -> Dict[str, Any]:
        """Compiles current active jobs and resource utilization status."""
        mem_rss_mb = self.get_memory_rss_mb()
        with self._lock:
            return {
                "active_research_jobs": self._active_research,
                "max_research_jobs": self.MAX_CONCURRENT_RESEARCH_JOBS,
                "active_pdf_jobs": self._active_pdf,
                "max_pdf_jobs": self.MAX_CONCURRENT_PDF_JOBS,
                "active_evidence_jobs": self._active_evidence,
                "max_evidence_jobs": self.MAX_CONCURRENT_EVIDENCE_JOBS,
                "total_rejected_jobs": self._rejected_count,
                "memory_rss_mb": mem_rss_mb,
                "cache_entries": len(self._cache),
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

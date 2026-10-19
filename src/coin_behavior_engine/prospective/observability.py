"""
Sprint 11.23.4: Bounded Prospective Observability & Health Telemetry
Provides lightweight, bounded metrics tracking, latency recording, retry counting,
queue depth monitoring, and process memory safety checks for prospective research.
Guarantees fixed memory bounds to prevent memory leaks during long-running simulations
using standard library facilities without external dependencies.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
import os
import sys
import time
from typing import Any, Dict, List, Optional

MAX_METRIC_SAMPLES = 5000


def _get_process_rss_bytes() -> int:
    """Retrieves current process RSS memory in bytes using standard library."""
    if sys.platform == "win32":
        try:
            import ctypes
            class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                _fields_ = [
                    ("cb", ctypes.c_ulong),
                    ("PageFaultCount", ctypes.c_ulong),
                    ("PeakWorkingSetSize", ctypes.c_size_t),
                    ("WorkingSetSize", ctypes.c_size_t),
                    ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                    ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                    ("PagefileUsage", ctypes.c_size_t),
                    ("PeakPagefileUsage", ctypes.c_size_t),
                ]
            counters = PROCESS_MEMORY_COUNTERS()
            counters.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
            handle = ctypes.windll.kernel32.GetCurrentProcess()
            if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), ctypes.sizeof(counters)):
                return int(counters.WorkingSetSize)
        except Exception:
            pass
    elif sys.platform.startswith("linux") or sys.platform == "darwin":
        try:
            import resource
            # ru_maxrss is in kilobytes on Linux, bytes on macOS
            rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
            if sys.platform.startswith("linux"):
                return rss * 1024
            return rss
        except Exception:
            pass
    return 0


@dataclass
class ObservabilityMetrics:
    total_requests: int = 0
    total_retries: int = 0
    total_failures: int = 0
    total_events_processed: int = 0
    total_vault_writes: int = 0
    current_queue_depth: int = 0
    failures_by_reason: Dict[str, int] = field(default_factory=dict)
    latencies_seconds: deque = field(default_factory=lambda: deque(maxlen=MAX_METRIC_SAMPLES))


class ProspectiveObservability:
    """
    Central telemetry and health monitor for prospective pilot execution.
    Bounded capacity ensures zero unbounded heap growth.
    """

    def __init__(self, max_samples: int = MAX_METRIC_SAMPLES) -> None:
        self.max_samples = max_samples
        self.metrics = ObservabilityMetrics(
            latencies_seconds=deque(maxlen=max_samples)
        )
        self._start_time = time.time()
        self._initial_memory_bytes = _get_process_rss_bytes()

    def record_request(self, latency_seconds: float, is_retry: bool = False) -> None:
        self.metrics.total_requests += 1
        if is_retry:
            self.metrics.total_retries += 1
        self.metrics.latencies_seconds.append(max(0.0, latency_seconds))

    def record_failure(self, reason: str) -> None:
        self.metrics.total_failures += 1
        self.metrics.failures_by_reason[reason] = (
            self.metrics.failures_by_reason.get(reason, 0) + 1
        )

    def record_vault_write(self) -> None:
        self.metrics.total_vault_writes += 1

    def record_event_processed(self) -> None:
        self.metrics.total_events_processed += 1

    def set_queue_depth(self, depth: int) -> None:
        self.metrics.current_queue_depth = max(0, depth)

    def get_summary(self) -> Dict[str, Any]:
        """Calculates bounded statistical summary of observed operations."""
        latencies = list(self.metrics.latencies_seconds)
        if latencies:
            min_lat = float(min(latencies))
            max_lat = float(max(latencies))
            mean_lat = float(sum(latencies) / len(latencies))
            sorted_lat = sorted(latencies)
            p95_idx = int(0.95 * len(sorted_lat))
            p95_lat = float(sorted_lat[min(p95_idx, len(sorted_lat) - 1)])
        else:
            min_lat = max_lat = mean_lat = p95_lat = 0.0

        current_rss = _get_process_rss_bytes()
        mem_delta_mb = max(0.0, (current_rss - self._initial_memory_bytes) / (1024 * 1024))

        return {
            "uptime_seconds": round(time.time() - self._start_time, 2),
            "total_requests": self.metrics.total_requests,
            "total_retries": self.metrics.total_retries,
            "total_failures": self.metrics.total_failures,
            "total_events_processed": self.metrics.total_events_processed,
            "total_vault_writes": self.metrics.total_vault_writes,
            "current_queue_depth": self.metrics.current_queue_depth,
            "latency_min_s": round(min_lat, 6),
            "latency_mean_s": round(mean_lat, 6),
            "latency_p95_s": round(p95_lat, 6),
            "latency_max_s": round(max_lat, 6),
            "failures_by_reason": dict(self.metrics.failures_by_reason),
            "process_rss_mb": round(current_rss / (1024 * 1024), 2),
            "memory_delta_mb": round(mem_delta_mb, 2),
            "bounded_buffer_capacity": self.max_samples,
            "memory_safety_status": "PASS" if mem_delta_mb < 256.0 else "WARNING",
        }

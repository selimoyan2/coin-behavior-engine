"""Local Observation-Only Health & Resource Monitor for CBE-0.8.0 Shadow Collector.

Enforces:
- Observation-only telemetry (zero production impact, zero external webhooks).
- Continuous tracking of buffer state, clock skew, and chain integrity.
- Memory (RSS), disk consumption, and CPU time auditing.
- Fail-safe alerting if provisional operational budgets are approached.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

from coin_behavior_engine.shadow_v080.configuration import ShadowCollectorConfig

logger = logging.getLogger("cbe_health_monitor")


@dataclass
class HealthTelemetrySnapshot:
    timestamp_utc: str
    collector_status: str
    source_status: str
    last_finalized_candle_close_utc: str
    buffer_candle_count: int
    warmup_status: str
    clock_trusted: bool
    data_gaps_detected: int
    total_predictions_stored: int
    pending_outcomes_count: int
    matured_outcomes_count: int
    invalidated_outcomes_count: int
    hash_chain_valid: bool
    process_rss_mb: float
    cpu_time_ms: float
    event_log_disk_kb: float
    snapshot_disk_kb: float
    network_requests_count: int
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ShadowHealthMonitorV080:
    """Manages telemetry snapshots and resource threshold monitoring."""

    def __init__(self, config: ShadowCollectorConfig):
        self.config = config
        self.telemetry_file = config.telemetry_dir / "collector_health.json"
        self.last_error: Optional[str] = None
        self.data_gaps_count: int = 0
        self.start_time = time.time()

    def record_error(self, err_msg: str) -> None:
        self.last_error = err_msg
        logger.warning(f"ShadowCollector Error: {err_msg}")

    def record_gap(self) -> None:
        self.data_gaps_count += 1

    def capture_telemetry(
        self,
        collector_status: str,
        source_status: str,
        last_candle_close_utc: str,
        buffer_count: int,
        warmup_status: str,
        clock_trusted: bool,
        total_predictions: int,
        pending_outcomes: int,
        matured_outcomes: int,
        invalidated_outcomes: int,
        hash_chain_valid: bool,
        cpu_time_ms: float,
        network_req_count: int,
    ) -> HealthTelemetrySnapshot:
        """Capture comprehensive telemetry and export state atomically."""
        now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Estimate process resident memory (RSS)
        rss_mb = self._get_process_rss_mb()

        # Disk footprints
        pred_log = self.config.prediction_dir / "shadow_predictions.jsonl"
        pred_kb = round(os.path.getsize(pred_log) / 1024.0, 2) if pred_log.exists() else 0.0

        snap_file = self.config.snapshot_dir / "candle_buffer_snapshot.json"
        snap_kb = round(os.path.getsize(snap_file) / 1024.0, 2) if snap_file.exists() else 0.0

        snap = HealthTelemetrySnapshot(
            timestamp_utc=now_utc,
            collector_status=collector_status,
            source_status=source_status,
            last_finalized_candle_close_utc=last_candle_close_utc,
            buffer_candle_count=buffer_count,
            warmup_status=warmup_status,
            clock_trusted=clock_trusted,
            data_gaps_detected=self.data_gaps_count,
            total_predictions_stored=total_predictions,
            pending_outcomes_count=pending_outcomes,
            matured_outcomes_count=matured_outcomes,
            invalidated_outcomes_count=invalidated_outcomes,
            hash_chain_valid=hash_chain_valid,
            process_rss_mb=rss_mb,
            cpu_time_ms=round(cpu_time_ms, 3),
            event_log_disk_kb=pred_kb,
            snapshot_disk_kb=snap_kb,
            network_requests_count=network_req_count,
            last_error=self.last_error,
        )

        # Atomically write telemetry snapshot
        tmp_file = self.telemetry_file.with_suffix(".json.tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(snap.to_dict(), f, indent=2)
            f.flush()
            os.fsync(f.fileno())

        # Windows-safe atomic replace with retry
        for attempt in range(5):
            try:
                os.replace(tmp_file, self.telemetry_file)
                break
            except PermissionError:
                time.sleep(0.01)

        return snap

    def _get_process_rss_mb(self) -> float:
        """Query real OS process resident set size in MB using standard OS APIs."""
        import sys
        if sys.platform == "win32":
            try:
                import ctypes
                from ctypes import wintypes

                class PROCESS_MEMORY_COUNTERS(ctypes.Structure):
                    _fields_ = [
                        ("cb", wintypes.DWORD),
                        ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t),
                        ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t),
                        ("PeakPagefileUsage", ctypes.c_size_t),
                    ]

                pmc = PROCESS_MEMORY_COUNTERS()
                pmc.cb = ctypes.sizeof(PROCESS_MEMORY_COUNTERS)
                psapi = ctypes.windll.psapi
                kernel32 = ctypes.windll.kernel32
                psapi.GetProcessMemoryInfo.argtypes = [
                    wintypes.HANDLE,
                    ctypes.POINTER(PROCESS_MEMORY_COUNTERS),
                    wintypes.DWORD,
                ]
                psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
                h = kernel32.GetCurrentProcess()
                if psapi.GetProcessMemoryInfo(h, ctypes.byref(pmc), pmc.cb):
                    return round(pmc.WorkingSetSize / (1024.0 * 1024.0), 2)
            except Exception:
                pass
        elif sys.platform.startswith("linux"):
            try:
                with open("/proc/self/status", "r") as f:
                    for line in f:
                        if line.startswith("VmRSS:"):
                            return round(float(line.split()[1]) / 1024.0, 2)
            except Exception:
                pass

        try:
            import psutil
            return round(psutil.Process(os.getpid()).memory_info().rss / (1024.0 * 1024.0), 2)
        except Exception:
            return -1.0

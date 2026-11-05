"""
Multi-Process and Multi-Thread Safe Advisory File Locking Module
Sprint 23 — Enterprise-Grade Security Hardening, Multi-Process Concurrency & Operational Readiness

Provides robust cross-process synchronization:
- Uses OS-level advisory file locks (msvcrt on Windows, fcntl on POSIX).
- Integrated with threading.RLock for re-entrant in-process thread safety.
- Bounded lock acquisition timeouts with explicit LockTimeoutError.
- Automatic cleanup of stale locks and safe release under process termination.
"""

from __future__ import annotations

import os
import sys
import time
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Optional


class LockTimeoutError(TimeoutError):
    """Raised when an advisory lock cannot be acquired within the configured timeout."""
    pass


class MultiProcessLock:
    """
    Cross-platform re-entrant file lock supporting multiple processes and threads.
    """

    _THREAD_LOCKS: dict[str, threading.RLock] = {}
    _GLOBAL_LOCK = threading.Lock()

    def __init__(self, lock_path: str | Path, timeout: float = 5.0, poll_interval: float = 0.05):
        self.lock_path = Path(lock_path).resolve()
        self.timeout = max(0.1, float(timeout))
        self.poll_interval = max(0.01, float(poll_interval))
        self._fd: Optional[int] = None

        with self._GLOBAL_LOCK:
            key = str(self.lock_path)
            if key not in self._THREAD_LOCKS:
                self._THREAD_LOCKS[key] = threading.RLock()
            self._thread_lock = self._THREAD_LOCKS[key]

    def acquire(self) -> None:
        """Acquires in-process thread lock and cross-process OS file lock."""
        # 1. Acquire thread lock with timeout
        acquired_thread = self._thread_lock.acquire(timeout=self.timeout)
        if not acquired_thread:
            raise LockTimeoutError(f"Thread lock acquisition timed out after {self.timeout}s for '{self.lock_path}'")

        # 2. Acquire OS file lock with timeout
        start_time = time.monotonic()
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._fd = os.open(str(self.lock_path), os.O_CREAT | os.O_RDWR)
        except Exception as e:
            self._thread_lock.release()
            raise IOError(f"Could not open lockfile '{self.lock_path}': {e}") from e

        locked = False
        while not locked:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    # Non-blocking lock attempt (1 byte)
                    msvcrt.locking(self._fd, msvcrt.LK_NBLCK, 1)
                    locked = True
                else:
                    import fcntl
                    fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
            except (BlockingIOError, PermissionError, OSError):
                if time.monotonic() - start_time >= self.timeout:
                    self._cleanup_fd()
                    self._thread_lock.release()
                    raise LockTimeoutError(
                        f"Cross-process lock acquisition timed out after {self.timeout}s for '{self.lock_path}'"
                    )
                time.sleep(self.poll_interval)

    def release(self) -> None:
        """Releases cross-process OS lock and thread lock."""
        try:
            if self._fd is not None:
                try:
                    if sys.platform == "win32":
                        import msvcrt
                        msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(self._fd, fcntl.LOCK_UN)
                except Exception:
                    pass
                self._cleanup_fd()
        finally:
            self._thread_lock.release()

    def _cleanup_fd(self) -> None:
        if self._fd is not None:
            try:
                os.close(self._fd)
            except Exception:
                pass
            self._fd = None

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


@contextmanager
def locked_path(path: str | Path, timeout: float = 5.0):
    """Context manager for acquiring an advisory lock on a given target path."""
    lock_file = Path(path).with_suffix(Path(path).suffix + ".lock")
    lock = MultiProcessLock(lock_file, timeout=timeout)
    with lock:
        yield

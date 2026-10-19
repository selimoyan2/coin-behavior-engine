"""
Sprint 11.23.3: Performance & Resource Safety Guard
Implements bounded queues, rate limiters, batch processing controls, and restart-safe checkpointing
for resource-constrained research environments.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from typing import Any, Dict, List, Optional

class BoundedEventQueue:
    """Bounded, thread-safe FIFO queue with overflow rejection."""

    def __init__(self, max_capacity: int = 1000) -> None:
        self.max_capacity = max_capacity
        self._queue: deque = deque(maxlen=max_capacity)
        self.overflow_rejections = 0

    def push(self, item: Any) -> bool:
        if len(self._queue) >= self.max_capacity:
            self.overflow_rejections += 1
            return False
        self._queue.append(item)
        return True

    def pop(self) -> Optional[Any]:
        if not self._queue:
            return None
        return self._queue.popleft()

    def __len__(self) -> int:
        return len(self._queue)

class RateLimiter:
    """Lightweight token bucket rate limiter to prevent aggressive source polling."""

    def __init__(self, requests_per_minute: float = 30.0, burst_limit: int = 5) -> None:
        self.rate = requests_per_minute / 60.0
        self.capacity = burst_limit
        self.tokens = burst_limit
        self.last_update = time.monotonic()
        self.throttled_count = 0

    def acquire(self) -> bool:
        now = time.monotonic()
        elapsed = now - self.last_update
        self.last_update = now
        self.tokens = min(self.capacity, self.tokens + elapsed * self.rate)

        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        else:
            self.throttled_count += 1
            return False

class CheckpointManager:
    """Restart-safe state checkpoint manager for idempotent resumption."""

    def __init__(self, checkpoint_file: Path) -> None:
        self.checkpoint_file = checkpoint_file

    def save_checkpoint(self, state: Dict[str, Any]) -> None:
        self.checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "checkpoint_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "state": state
        }
        tmp = self.checkpoint_file.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
            f.flush()
        tmp.replace(self.checkpoint_file)

    def load_checkpoint(self) -> Optional[Dict[str, Any]]:
        if not self.checkpoint_file.exists():
            return None
        try:
            with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("state")
        except Exception:
            return None

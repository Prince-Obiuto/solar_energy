"""Small in-process rate limiter for security-sensitive endpoints."""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class RateLimitExceeded(RuntimeError):
    pass


class SlidingWindowRateLimiter:
    """Bound attempts per key without retaining request bodies or credentials."""

    def __init__(
        self,
        *,
        attempts: int,
        window_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if attempts < 1 or window_seconds <= 0:
            raise ValueError("Rate limit values must be positive")
        self.attempts = attempts
        self.window_seconds = window_seconds
        self.clock = clock
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        now = self.clock()
        cutoff = now - self.window_seconds
        with self._lock:
            entries = self._attempts[key]
            while entries and entries[0] <= cutoff:
                entries.popleft()
            if len(entries) >= self.attempts:
                raise RateLimitExceeded
            entries.append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._attempts.pop(key, None)

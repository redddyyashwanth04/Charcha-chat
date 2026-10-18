import threading
import time
from collections import defaultdict, deque

from app.config import get_settings
from app.errors import RateLimitError


class RateLimiter:
    """Per-key sliding window (in-memory; swap for Redis when running several workers)."""

    def __init__(self) -> None:
        self._hits: dict[int, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: int) -> None:
        limit = get_settings().rate_limit_per_minute
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and now - hits[0] > 60:
                hits.popleft()
            if len(hits) >= limit:
                raise RateLimitError("You're sending messages too quickly. Please wait a moment.")
            hits.append(now)

    def reset(self) -> None:
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()

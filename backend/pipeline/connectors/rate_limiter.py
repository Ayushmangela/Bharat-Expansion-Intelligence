"""Shared rate limiter, matching docs/09-DATA-QUALITY.md's documented design
exactly: "token bucket, 2 rps, max 4 concurrent." Previously every fetch was
fully sequential (one page at a time, sleep between each) even though
settings.http_max_concurrency existed and was never used — meaning effective
throughput was latency-bound (~0.5-0.7 req/s in practice) rather than
rate-limit-bound. A shared limiter lets multiple in-flight requests overlap
their network latency while still respecting one global rate cap, closing
that gap without exceeding the ceiling the docs specify.
"""

import threading
import time
from typing import Self


class TokenBucketLimiter:
    def __init__(self, rate_per_second: float, max_concurrent: int) -> None:
        self._rate = rate_per_second
        self._lock = threading.Lock()
        self._next_allowed = time.monotonic()
        self._semaphore = threading.Semaphore(max_concurrent)

    def __enter__(self) -> Self:
        self._semaphore.acquire()
        with self._lock:
            now = time.monotonic()
            wait = self._next_allowed - now
            if wait > 0:
                time.sleep(wait)
                now = time.monotonic()
            self._next_allowed = now + 1.0 / self._rate
        return self

    def __exit__(self, *exc: object) -> None:
        self._semaphore.release()

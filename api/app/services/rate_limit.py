"""Fixed-window rate limiting: O(1) time and memory per key per window."""

import hashlib
import hmac
import threading
import time
from collections.abc import Callable
from typing import Protocol

import redis


class RateLimiter(Protocol):
    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        """Record one request; return False if the key is over its limit for the current window."""


class RedisRateLimiter:
    """INCR + EXPIRE in one pipelined round trip; shared across API workers.

    Keys hold client IPs, so they're stored as keyed HMAC-SHA256 digests: Redis never sees a raw IP,
    and without the secret the 2^32 IPv4 space can't be brute-forced back out of the digests.
    """

    def __init__(self, client: redis.Redis, secret: str):
        self.client = client
        self._secret = secret.encode()

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        window = int(time.time() // window_seconds)
        digest = hmac.new(self._secret, key.encode(), hashlib.sha256).hexdigest()
        redis_key = f"rl:{digest}:{window}"
        pipe = self.client.pipeline()
        pipe.incr(redis_key)
        pipe.expire(redis_key, window_seconds + 1)
        count, _ = pipe.execute()
        return count <= limit


class InMemoryRateLimiter:
    """Single-process limiter for tests and local dev."""

    def __init__(self, clock: Callable[[], float] = time.time):
        self.clock = clock
        self._counts: dict[tuple[str, int], int] = {}
        self._lock = threading.Lock()

    def hit(self, key: str, limit: int, window_seconds: int) -> bool:
        window = int(self.clock() // window_seconds)
        with self._lock:
            # Drop older windows so memory stays bounded by active keys.
            if len(self._counts) > 10_000:
                self._counts = {k: v for k, v in self._counts.items() if k[1] == window}
            count = self._counts.get((key, window), 0) + 1
            self._counts[(key, window)] = count
        return count <= limit

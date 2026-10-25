from app.services.rate_limit import InMemoryRateLimiter, RedisRateLimiter


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_allows_up_to_limit_then_blocks():
    limiter = InMemoryRateLimiter(clock=Clock())
    assert [limiter.hit("k", limit=3, window_seconds=60) for _ in range(4)] == [True, True, True, False]


def test_window_resets():
    clock = Clock()
    limiter = InMemoryRateLimiter(clock=clock)
    for _ in range(3):
        limiter.hit("k", 3, 60)
    assert not limiter.hit("k", 3, 60)
    clock.now += 61
    assert limiter.hit("k", 3, 60)


def test_keys_are_independent():
    limiter = InMemoryRateLimiter(clock=Clock())
    assert limiter.hit("a", 1, 60)
    assert not limiter.hit("a", 1, 60)
    assert limiter.hit("b", 1, 60)


# --- Redis limiter stores keyed hashes, never raw client IPs --------------------------------

class FakePipeline:
    def __init__(self, store):
        self.store, self.ops = store, []

    def incr(self, key):
        self.ops.append(key)

    def expire(self, key, seconds):
        pass

    def execute(self):
        key = self.ops[-1]
        self.store[key] = self.store.get(key, 0) + 1
        return [self.store[key], True]


class FakeRedis:
    def __init__(self):
        self.store = {}

    def pipeline(self):
        return FakePipeline(self.store)


def test_redis_limiter_never_stores_raw_ip():
    client = FakeRedis()
    limiter = RedisRateLimiter(client, secret="s3cret")
    limiter.hit("login:203.0.113.7", 5, 60)
    (key,) = client.store
    assert "203.0.113.7" not in key and key.startswith("rl:")


def test_redis_limiter_counts_same_key_together_and_separates_others():
    client = FakeRedis()
    limiter = RedisRateLimiter(client, secret="s3cret")
    assert [limiter.hit("login:1.2.3.4", 2, 60) for _ in range(3)] == [True, True, False]
    assert limiter.hit("login:5.6.7.8", 2, 60)


def test_redis_limiter_hash_depends_on_secret():
    a, b = FakeRedis(), FakeRedis()
    RedisRateLimiter(a, secret="one").hit("login:1.2.3.4", 5, 60)
    RedisRateLimiter(b, secret="two").hit("login:1.2.3.4", 5, 60)
    assert set(a.store) != set(b.store)

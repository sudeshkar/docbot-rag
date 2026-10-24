from app.services.rate_limit import InMemoryRateLimiter


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

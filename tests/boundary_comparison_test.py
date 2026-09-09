import redis
from unittest.mock import patch

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

from app.token_bucket import TokenBucket
from app.sliding_window import SlidingWindow


def test_boundary_burst_comparison():
    capacity = 5
    window = 10
    refill_rate = capacity / window

    r.delete("test_boundary_bucket")
    r.delete("test_boundary_sliding")

    bucket = TokenBucket(r)
    sliding = SlidingWindow(r)

    fake_now = 1000.0

    # first burst: both should allow exactly capacity amnt of requests
    with patch("time.time", return_value=fake_now):
        bucket_allowed_first = 0
        for i in range(capacity):
            allowed, _ = bucket.is_allowed(
                "test_boundary_bucket", capacity, refill_rate, 1
            )
            if allowed:
                bucket_allowed_first += 1

        sliding_allowed_first = 0
        for i in range(capacity):
            allowed, _ = sliding.is_allowed("test_boundary_sliding", capacity, window)
            if allowed:
                sliding_allowed_first += 1

    assert bucket_allowed_first == capacity
    assert sliding_allowed_first == capacity

    # second burst that fires nearly instantly after the first.
    # a naive fixed window counter would reset to 0 here and allow a second burst
    # to come through doubling effect throughput. we want to assert that neither of our
    # implementations fall for that
    with patch("time.time", return_value=fake_now + 0.001):
        bucket_allowed_second = 0
        for i in range(capacity):
            allowed, _ = bucket.is_allowed(
                "test_boundary_bucket", capacity, refill_rate, 1
            )
            if allowed:
                bucket_allowed_second += 1

        sliding_allowed_second = 0
        for i in range(capacity):
            allowed, _ = sliding.is_allowed("test_boundary_sliding", capacity, window)
            if allowed:
                sliding_allowed_second += 1

    total_bucket = bucket_allowed_first + bucket_allowed_second
    total_sliding = sliding_allowed_first + sliding_allowed_second

    # neither should exceed capacity within this ~0-second span
    assert bucket_allowed_second == 0
    assert sliding_allowed_second == 0
    assert total_bucket == capacity
    assert total_sliding == capacity

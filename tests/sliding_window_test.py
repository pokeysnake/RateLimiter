import redis
import time
import uuid

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

from app.sliding_window import SlidingWindow


# confirms requests are allowed up to capacity, then denied, within one window
def test_allows_up_to_capacity():
    r.delete("test_sliding_capacity_key")

    limiter = SlidingWindow(r)
    for i in range(5):
        allowed, retry_after = limiter.is_allowed("test_sliding_capacity_key", 5, 10)
        assert allowed is True
        assert retry_after == 0

    denied, retry_after = limiter.is_allowed("test_sliding_capacity_key", 5, 10)
    assert denied is False
    assert retry_after > 0


from unittest.mock import patch


def test_key_isolation():
    r.delete("test_iso_a")
    r.delete("test_iso_b")

    limiter = SlidingWindow(r)

    for i in range(5):
        allowed, retry_after = limiter.is_allowed("test_iso_a", 5, 10)
        assert allowed is True
        assert retry_after == 0

    allowed2, retry_after_2 = limiter.is_allowed("test_iso_a", 5, 10)
    assert allowed2 is False
    assert retry_after_2 > 0

    allowed_b, retry_after_b = limiter.is_allowed("test_iso_b", 5, 10)
    assert allowed_b is True
    assert retry_after_b == 0


def test_partial_usage():
    r.delete("test_partial")

    limiter = SlidingWindow(r)

    for i in range(3):
        allowed, retry_after = limiter.is_allowed("test_partial", 5, 10)
        assert allowed is True
        assert retry_after == 0

    for i in range(2):
        allowed, retry_after = limiter.is_allowed("test_partial", 5, 10)
        assert allowed is True
        assert retry_after == 0

    # 6th call in a 5 call window of 10 seconds should deny
    allowed_2, retry_after_2 = limiter.is_allowed("test_partial", 5, 10)
    assert allowed_2 is False
    assert retry_after_2 > 0  # >0 signifies that we need to wait


def test_small_window():
    r.delete("test_small_window")

    limiter = SlidingWindow(r)

    # need to use a mock clock
    fake_now = 1000.0
    with patch("time.time", return_value=fake_now):
        for i in range(3):
            allowed, retry_after = limiter.is_allowed(
                "test_small_window", 3, 2
            )  # 2 second window
            assert allowed is True
            assert retry_after == 0

        allowed_4, retry_after_4 = limiter.is_allowed("test_small_window", 3, 2)
        assert allowed_4 is False
        assert retry_after_4 > 0

    # fake_now + 2 seconds within the +5 buffer but aged/cleaned up already, should allow
    with patch("time.time", return_value=fake_now + 2):
        allowed, retry_after = limiter.is_allowed("test_small_window", 3, 2)
        assert allowed is True
        assert retry_after == 0

    # fake_now + 3 within the +5 buffer but a new window should allow
    with patch("time.time", return_value=fake_now + 3):
        allowed, retry_after = limiter.is_allowed("test_small_window", 3, 2)
        assert allowed is True
        assert retry_after == 0

    # fake_now + 5 outside of the buffer and within a new window should allow
    with patch("time.time", return_value=fake_now + 5):
        allowed, retry_after = limiter.is_allowed("test_small_window", 3, 2)
        assert allowed is True
        assert retry_after == 0


def test_burst_capacity_exploit():
    r.delete("test_burst")

    limiter = SlidingWindow(r)

    fake_now = 1000.0

    with patch("time.time", return_value=fake_now):
        for i in range(5):
            allowed, retry_after = limiter.is_allowed("test_burst", 5, 10)
            assert allowed is True
            assert retry_after == 0

    with patch("time.time", return_value=fake_now + 1):
        allowed, retry_after = limiter.is_allowed("test_burst", 5, 10)
        assert allowed is False
        assert retry_after > 0


def test_burst_allowed_after_capacity():
    r.delete("test_burst_continued")
    limiter = SlidingWindow(r)

    fake_now = 1000.0

    with patch("time.time", return_value=fake_now):
        for i in range(5):
            allowed, retry_after = limiter.is_allowed("test_burst_continued", 5, 10)
            assert allowed is True
            assert retry_after == 0

    with patch("time.time", return_value=fake_now + 1):
        for i in range(5):
            allowed, retry_after = limiter.is_allowed("test_burst_continued", 5, 10)
            assert allowed is False
            assert retry_after > 0

    with patch("time.time", return_value=fake_now + 10):
        for i in range(5):
            allowed, retry_after = limiter.is_allowed("test_burst_continued", 5, 10)
            assert allowed is True
            assert retry_after == 0

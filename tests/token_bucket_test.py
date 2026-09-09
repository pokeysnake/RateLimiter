import redis
import time

#creates a local host client
r = redis.Redis(host = "localhost", port = 6379, decode_responses=True)

from app.token_bucket import TokenBucket #import the token_bucket.py file

#confirms that we can fill up the capacity properly and the {bool, float} returns of isAllowed are valid
def test_allows_up_to_capacity():
    r.delete("test_capacity_key")
    
    bucket = TokenBucket(r)
    for i in range(5):
        allowed, remaining = bucket.isAllowed("test_capacity_key", 5, .01, 1)
        assert allowed is True
        assert remaining == 5 - (i + 1)

    allowed_after, remaining_after = bucket.isAllowed("test_capacity_key", 5, .01, 1)
    assert allowed_after is False

#confirms that we fill up to capacity and reject everything after
def test_capacity_then_refill():
    r.delete("test_capacity_reject_after")

    bucket = TokenBucket(r)
    for i in range(5):
        allowed, remaining = bucket.isAllowed("test_capacity_reject_after", 5, 10, 1)
        assert allowed is True
        assert remaining == 5 - (i + 1)

    time.sleep(5)

    allowed_after, remaining_after = bucket.isAllowed("test_capacity_reject_after", 5,10, 1)
    assert allowed_after is True
    assert remaining_after == 4

#mock-clock to make deterministic instantly, no real sleep needed
from unittest.mock import patch

def test_capacity_then_refill_mock():
    r.delete("test_capacity_reject_after_mockclock")
    bucket = TokenBucket(r)

    fake_now = 1000.0
    with patch("time.time", return_value=fake_now):
        for i in range(5):
            allowed, remaining = bucket.isAllowed("test_capacity_reject_after_mockclock", 5, 10, 1)
            assert allowed is True
            assert remaining == 5 - (i + 1)

    # jump the clock forward 5 fake seconds without any real waiting
    with patch("time.time", return_value=fake_now + 5):
        allowed_after, remaining_after = bucket.isAllowed("test_capacity_reject_after_mockclock", 5, 10, 1)
        assert allowed_after is True
        assert remaining_after == 4


#request larger than the capacity --> should deny forever
def test_request_more_than_capacity():
    r.delete("test_request_more_than_capacity")
    bucket = TokenBucket(r)
    for i in range(5):
        allowed, remaining = bucket.isAllowed("test_request_more_than_capacity", 5, 1, 10)
        assert allowed is False
        assert remaining == 5

#request > 1
def test_request_greater_one():
    r.delete("test_request_greater_than_one")
    bucket = TokenBucket(r)

    expected_tokens = 5 #simulate token count to compare with actual
    for i in range(5):
        allowed, remaining = bucket.isAllowed("test_request_greater_than_one", 5, 1, 3)
        if expected_tokens >= 3:
            expected_tokens -= 3
            assert allowed is True
        else:
            assert allowed is False
        assert remaining == expected_tokens #actual vs sim

#partial refill --> less time passes than needed to fully refill to capacity
def test_partial_refill():
    r.delete("test_partial_refill")
    bucket = TokenBucket(r)

    fake_now = 1000.0
    with patch("time.time", return_value=fake_now):
        for i in range(5):
            allowed, remaining = bucket.isAllowed("test_partial_refill", 5, 1, 1)
            assert allowed is True
            assert remaining == 5 - (i + 1)

    # only 2 fake seconds pass, refillRate=1 --> only 2 tokens should come back, not all 5
    with patch("time.time", return_value=fake_now + 2):
        allowed, remaining = bucket.isAllowed("test_partial_refill", 5, 1, 1)
        assert allowed is True
        assert remaining == 1  # 0 + 2 refilled - 1 requested

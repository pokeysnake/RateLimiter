import time
import uuid
import redis

class SlidingWindow:

    LUA_SLIDING_WINDOW = """
    local key = KEYS[1]
    local now = tonumber(ARGV[1])
    local window = tonumber(ARGV[2])
    local capacity = tonumber(ARGV[3])
    local request_id = ARGV[4]

    local clear_before = now - window

    --remove old elements
    redis.call('ZREMRANGEBYSCORE', key, 0, clear_before)

    --get current element count
    local current_requests = redis.call('ZCARD', key)

    if current_requests < capacity then
        --add the request tiumestamp if under capacity
        redis.call('ZADD', key, now, request_id)
        redis.call('EXPIRE', key, window + 5)
        return {1, 0} --allowed, no wait needed
    else
        --oldest entry still in the window tells us when a slot frees up
        local oldest = redis.call('ZRANGE', key, 0, 0, 'WITHSCORES')
        local oldest_score = tonumber(oldest[2])
        local retry_after = (oldest_score + window) - now
        return {0, retry_after} --denied, seconds until retry

    end
    """

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.lua_script = self.redis.register_script(self.LUA_SLIDING_WINDOW)

    def is_allowed(self, client_id:str, capacity: int, window_seconds: int) -> tuple[bool, float]:
        """
        checks if a lcient is allowed to proceed based off the rate limit of a rolling window

        client_id: unique id for the client
        capacity: max requests allowed within the rolling window
        window_seconds: how many seconds per window
        return: (allowed, retry_after_seconds) - retry_after_seconds is 0 when allowed,
        otherwise how many seconds until a slot frees up
        """
        key = f"rate_limit:{client_id}"
        now = time.time()
        #generate a unique string to ensure identical timestamps dont overwrite each other
        request_id = f"{now}:{uuid.uuid4().hex}"

        # execute the registered script
        # script returns {1, 0} for allowed, or {0, retry_after} for denied
        allowed, retry_after = self.lua_script(
            keys = [key],
            args = [now,window_seconds,capacity,request_id]
        )

        return bool(allowed), float(retry_after)
        
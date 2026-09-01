import time
import redis


class token_bucket:



    def __init__(self, redis_client : redis.Redis):
        self.redis = redis_client

        self.lua_script = self.redis.register_script("""
            local key = KEYS[1] 
            local capacity = tonumber(ARGV[1])
            local refill_rate = tonumber(ARGV[2])
            local now = tonumber(ARGV[3])
            local requested = tonumber(ARGV[4])

            -- retrieve current bucket state
            local data = redis.call('HMGET', key, 'tokens', 'last_updated')
            local tokens = tonumber(data[1])
            local last_updated = tonumber(data[2])

            --init full bucket for new keys
            if not tokens then 
                tokens = capacity
                last_updated = now
            else
                --lazily compute refills based on elapsed time
                local elapsed = now - last_updated
                if elapsed > 0 then
                    tokens = math.min(capacity, tokens + (elapsed * refill_rate))
                    last_updated = now 
                end
            end

            --eval request
            if tokens >= requested then
                tokens = tokens - requested
                redis.call('HMSET',key,'tokens', tokens, 'last_updated', last_updated)
                -- keep the key alive for cleanup if inactive
                redis.call('EXPIRE', key, math.ceil(capacity / refill_rate))
                return {1, tokens} -- allowed
            else
                redis.call('HMSET',key,'tokens', tokens, 'last_updated', last_updated)
                return {0, tokens} -- denied
            end
        """)

    def is_allowed(self, key: str, capacity: int, refill_rate: float, requested: int = 1) -> tuple[bool, float]:
        """
        Check if a request can be filled
        - key: unique id 
        - capacity: how many the pool can provide 
        - refill rate: number of tokens added per second
        - requested: token cost for this action
        - returns (is_allowed, remaining_token s) --> needs it for similar syntax for the lua scripts
        """

        now = time.time()
        allowed, remaining_tokens = self.lua_script(
            keys = [key],
            args = [capacity,refill_rate,now, requested]
        )

        return bool(allowed), float(remaining_tokens)

    
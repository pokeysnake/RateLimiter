from fastapi import FastAPI, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse

import os
import redis

from app.db import SessionLocal
from app.api_keys import get_config_by_key
from app.token_bucket import TokenBucket
from app.sliding_window import SlidingWindow

app = FastAPI()

# create redis, token bucket, sliding window ONCE at the module level
redis_client = redis.Redis(
    host=os.environ.get("REDIS_HOST", "localhost"),
    port=int(os.environ.get("REDIS_PORT", 6379)),
    decode_responses=True,
)
token_bucket = TokenBucket(redis_client)
sliding_window = SlidingWindow(redis_client)


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # api_key acts both as the client_id and the rate-limiter identifier
    api_key = request.headers.get("X-API-Key")

    if not api_key:
        # 401 --> missing key entirely
        return JSONResponse(status_code=401, content={"detail": "missing API key"})

    session = SessionLocal()
    try:
        config = await run_in_threadpool(get_config_by_key, session, api_key)

        if not config:
            # 403 --> key given but not recognized
            return JSONResponse(status_code=403, content={"detail": "invalid API key"})

        if config.algorithm == "token_bucket":
            refill_rate = config.capacity / config.window_seconds
            allowed, retry_after = await run_in_threadpool(
                token_bucket.is_allowed, api_key, config.capacity, refill_rate, 1
            )
        else:
            allowed, retry_after = await run_in_threadpool(
                sliding_window.is_allowed,
                api_key,
                config.capacity,
                config.window_seconds,
            )

        if not allowed:
            return JSONResponse(
                status_code=429,
                content={"detail": "rate limit exceeded"},
                headers={"Retry-After": str(int(retry_after))},
            )
    finally:
        session.close()

    response = await call_next(request)
    return response


@app.get("/ping")
def ping():
    return {"message": "pong"}

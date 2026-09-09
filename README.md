# Distributed Rate Limiter Service

A rate limiting API gateway built with FastAPI, Redis, and PostgreSQL. Each client authenticates with an API key, and every request is checked against that client's configured limit before it's allowed to reach the actual application.

This project exists to answer a specific engineering question: how do you enforce a rate limit correctly when your application runs as multiple separate processes (or containers, or servers)? An in memory counter works fine for a single process, but breaks the moment you scale horizontally, since each process would keep its own independent count. Redis solves this by giving every instance a single, shared, atomically updated source of truth.

## Architecture

```
Client request (with API key)
  |
FastAPI middleware
  |  lookup client's configured limit (PostgreSQL, queried fresh each request)
  |  check/increment request count in Redis (atomic, via a Lua script)
  |  over limit? return 429 with a Retry After header
  |  under limit? pass through to the route handler
```

Two rate limiting algorithms are implemented and selectable per API key: a continuously refilling token bucket, and a sliding window log. Both live behind the same interface (an `is_allowed` method returning `(allowed, retry_after_seconds)`), so the middleware doesn't need to know which one it's calling.

## Key design decisions

**Why Redis, specifically.** A plain Python counter can't be shared safely across multiple processes. Even within a single process, a naive "read the count, then write the incremented count" pattern has a race condition under concurrent requests: two requests can both read the same starting value before either writes back, silently losing an increment. Redis commands like `INCR` are atomic on their own, and more complex multi step logic (used by the sliding window algorithm) is made atomic with a Lua script run via `EVAL`, since Redis executes an entire script without interleaving any other client's command in the middle.

**Token bucket vs sliding window.** The common argument against fixed window counters is a boundary exploit: a client can burst up to the limit right before a window resets, then burst again immediately after, getting roughly double the intended throughput in a short span. This project actually tested that claim directly (see `tests/boundary_comparison_test.py`) by firing the same burst pattern at both algorithms with a mocked clock. The result: this project's token bucket implementation, which refills continuously based on elapsed time rather than resetting at a fixed clock boundary, does not exhibit that exploit either. Both algorithms correctly capped the client at its configured limit. The real difference between them is mechanical, not correctness: token bucket needs fractional tokens to accumulate back over time before allowing another request, while sliding window needs its oldest recorded timestamp to age out of the rolling window.

**API keys are hashed with SHA 256, not bcrypt.** Password hashing (bcrypt, scrypt, argon2) is deliberately slow, to make brute forcing a weak, human chosen password expensive. API keys are the opposite case: they're already high entropy random strings, generated with Python's `secrets` module, so brute forcing isn't the realistic threat. What actually matters here is fast, deterministic, indexable lookup, since an incoming request needs to be matched against a stored row by its key alone, with no separate username to narrow the search first. SHA 256 gives an exact, indexable match while still protecting the raw key if the database were ever leaked.

**Async correctness in the middleware.** FastAPI middleware must be declared `async def`, but the actual work it does (a SQLAlchemy query, a Redis call through `redis py`) is blocking, synchronous I/O. A blocking call inside `async def` freezes the entire event loop for every concurrent request, not just its own, since the loop is single threaded and can't hand control to another request mid blocking call. This was confirmed directly during Stage 0 (three concurrent `time.sleep` calls inside `async def` took roughly three times as long as the equivalent `await asyncio.sleep` calls). The middleware avoids this by explicitly offloading every blocking call to a thread pool with `run_in_threadpool`, so unrelated clients' requests are never serialized behind each other.

**Known limitation: no caching on the Postgres lookup.** Every request currently opens a fresh SQLAlchemy session and queries Postgres for that client's config. This is correct but not fast at scale. A real deployment would cache this lookup somewhere, either in process memory (simple, but goes stale across instances and on restart) or in Redis alongside the rate limit state itself (consistent across instances, at the cost of an extra round trip). This project doesn't implement either yet, that tradeoff is left as a deliberate, named open decision rather than something silently skipped.

**Known limitation: Redis availability.** If Redis is unreachable, the current middleware has no explicit handling for that failure, the call simply raises and the request errors out. This is effectively "fail closed" by accident rather than by design. A production version of this service would need to explicitly decide between failing open (letting requests through when the rate limiter itself is down) and failing closed (rejecting everything), since neither is universally correct and the right choice depends on whether availability or strict enforcement matters more for the API being protected.

## Running it

Requires Docker.

```
docker compose up --build -d
docker compose exec app1 python -m scripts.create_tables
docker compose exec app1 python -m scripts.try_create_key
```

The last command prints a raw API key. This is the only time it's ever visible, since only its hash is stored. Use it on any request:

```
curl -i -H "X-API-Key: <your key>" http://127.0.0.1:8001/ping
```

Two app instances are exposed, on ports `8001` and `8002`, both enforcing the same shared limit through the single Redis container.

## Testing

```
python -m pytest tests/ -v
```

Covers both algorithms individually (capacity limits, key isolation, partial usage, clock boundary edge cases) and a direct empirical comparison between them under a burst-at-boundary scenario.

## Proving it's actually distributed

`docs/distributed-results.md` documents a real run showing a single client's requests, alternated across both app instances, correctly rate limited as one combined total rather than each instance keeping its own separate count.

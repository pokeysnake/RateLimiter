# Stage 5: Proof the Rate Limiter Is Actually Distributed

## Claim

Two independent FastAPI instances, each with their own process and their own
in-memory objects, correctly enforce **one shared** rate limit for a single
API key because the actual limiter state lives in Redis, not in either
process. Hitting the two instances alternately (round-robin) still caps the
client at its configured capacity, combined across both.

## Setup

`docker-compose.yml` runs 4 containers: a single `redis`, a single
`postgres`, and two separate app instances (`app1` on host port `8001`,
`app2` on host port `8002`), both built from the same image and both
pointing at the same `redis`/`postgres` containers via Docker's internal
service names.

## Commands run

```powershell
# fresh stack
docker compose down -v
docker compose up --build -d
docker compose ps

# create table and a test key (capacity=5, window_seconds=10, sliding_window)
docker compose exec app1 python -m scripts.create_tables
docker compose exec app1 python -m scripts.try_create_key

# round-robin 8 requests across both instances with the same key
$key = "<key from previous step>"
$ports = @(8001, 8002)
for ($i=0; $i -lt 8; $i++) {
    $port = $ports[$i % 2]
    Write-Output "--- request $($i+1) -> port $port ---"
    curl.exe -s -i -H "X-API-Key: $key" http://127.0.0.1:$port/ping | Select-String -Pattern "HTTP/|retry-after"
}
```

## Result

```
--- request 1 -> port 8001 ---
HTTP/1.1 200 OK
--- request 2 -> port 8002 ---
HTTP/1.1 200 OK
--- request 3 -> port 8001 ---
HTTP/1.1 200 OK
--- request 4 -> port 8002 ---
HTTP/1.1 200 OK
--- request 5 -> port 8001 ---
HTTP/1.1 200 OK
--- request 6 -> port 8002 ---
HTTP/1.1 429 Too Many Requests
retry-after: 9
--- request 7 -> port 8001 ---
HTTP/1.1 429 Too Many Requests
retry-after: 9
--- request 8 -> port 8002 ---
HTTP/1.1 429 Too Many Requests
retry-after: 9
```

## Why this proves it

Exactly 5 requests (the configured `capacity`) were allowed **in total**,
spread across both `app1` and `app2` in alternation and not 5 per instance.
Requests 6-8 were denied on *both* ports, with an identical, correctly
computed `retry-after`.

If the rate limiter's state lived in each process's memory instead of
Redis, each instance would have kept its own independent count: `app1`
would allow its own first 5 hits, and `app2` — with no knowledge of
`app1`'s counter would independently allow its own first 5 hits too,
letting 10 total requests through for one client instead of 5. The fact
that the 6th request (routed to a different process than the 5th) was
correctly denied is directly proves that both instances are reading
and writing the same shared Redis-backed state rather than tracking
anything locally.

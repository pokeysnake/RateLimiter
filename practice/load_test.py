import httpx
import asyncio
import time

async def hit(client, url):
    start = time.time()
    await client.get(url)
    print(f"{url} finished in {time.time() - start:.2f}s")

async def main():
    async with httpx.AsyncClient(timeout=20) as client:
        start = time.time()
        await asyncio.gather(
            hit(client, "http://127.0.0.1:8000/slow-blocking"),
            hit(client, "http://127.0.0.1:8000/slow-blocking"),
            hit(client, "http://127.0.0.1:8000/slow-blocking"),
        )
        print(f"Total: {time.time()-start:.2f}s") #expected error until you swap slow-block for slow-async 


asyncio.run(main())
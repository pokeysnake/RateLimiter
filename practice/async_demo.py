import time
import asyncio
from fastapi import FastAPI

app = FastAPI()

#wrong way - blocking call inside async def --> blocks entire process
@app.get("/slow-blocking")
async def slow_blocking():
    time.sleep(5)

    return{"status" : "done (blocking)"}

#the right way - async native sleep command
@app.get("/slow-async")
async def slow_async():
    await asyncio.sleep(5)

    return{"status" : "done (async)"}
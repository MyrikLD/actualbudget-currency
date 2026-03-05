import asyncio
import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI

from src.sync import run_sync

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler()


def _parse_cron(expr: str) -> dict:
    minute, hour, day, month, dow = expr.split()
    return dict(minute=minute, hour=hour, day=day, month=month, day_of_week=dow)


@asynccontextmanager
async def lifespan(app: FastAPI):
    cron = os.getenv("CRON_SCHEDULE", "0 6 * * *")
    scheduler.add_job(run_sync, "cron", **_parse_cron(cron))
    scheduler.start()
    logger.info(f"Scheduler started: {cron}")
    yield
    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/sync")
async def sync():
    asyncio.create_task(run_sync())
    return {"started": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)

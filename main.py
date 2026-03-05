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


@app.get("/accounts")
async def list_accounts():
    """Список аккаунтов из Actual Budget с их ID — для проверки маппинга."""
    import os
    from actual import Actual
    from actual.queries import get_accounts

    with Actual(
        base_url=os.environ["ACTUAL_SERVER_URL"],
        password=os.environ["ACTUAL_PASSWORD"],
        file=os.environ["ACTUAL_BUDGET_NAME"],
        data_dir="/data/actual-sync",
    ) as actual:
        actual.download_budget()
        return [{"id": a.id, "name": a.name} for a in get_accounts(actual.session)]


@app.post("/sync")
async def sync():
    asyncio.create_task(run_sync())
    return {"started": True}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=3000)

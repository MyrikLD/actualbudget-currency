import asyncio
import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://bankaccountdata.gocardless.com/api/v2"

_token: str | None = None
_token_expiry: float = 0


async def _get_token(client: httpx.AsyncClient) -> str:
    global _token, _token_expiry
    if _token and time.time() < _token_expiry:
        return _token

    r = await client.post(
        f"{BASE_URL}/token/new/",
        json={
            "secret_id": os.environ["GOCARDLESS_SECRET_ID"],
            "secret_key": os.environ["GOCARDLESS_SECRET_KEY"],
        },
    )
    r.raise_for_status()
    data = r.json()
    _token = data["access"]
    _token_expiry = time.time() + data["access_expires"] - 60
    return _token  # type: ignore[return-value]


async def get_transactions(
    client: httpx.AsyncClient, account_id: str, date_from: str, retries: int = 3
) -> list[dict]:
    token = await _get_token(client)
    for attempt in range(retries):
        r = await client.get(
            f"{BASE_URL}/accounts/{account_id}/transactions/",
            params={"date_from": date_from},
            headers={"Authorization": f"Bearer {token}"},
        )
        if r.status_code == 429:
            wait = int(r.headers.get("Retry-After", 60 * (attempt + 1)))
            logger.warning(f"Rate limited on {account_id}, waiting {wait}s...")
            await asyncio.sleep(wait)
            continue
        r.raise_for_status()
        return r.json()["transactions"]["booked"]
    raise RuntimeError(f"GoCardless rate limit exceeded for {account_id}")

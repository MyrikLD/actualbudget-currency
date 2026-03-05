from datetime import date, timedelta

import httpx

_cache: dict[str, float] = {}


async def get_rate(client: httpx.AsyncClient, currency: str, on_date: str) -> float:
    if currency == "PLN":
        return 1.0

    key = f"{currency}:{on_date}"
    if key in _cache:
        return _cache[key]

    # NBP не работает по выходным/праздникам — берём последний рабочий день
    d = date.fromisoformat(on_date)
    for i in range(7):
        check = (d - timedelta(days=i)).isoformat()
        r = await client.get(
            f"https://api.nbp.pl/api/exchangerates/rates/A/{currency}/{check}/",
            params={"format": "json"},
        )
        if r.status_code == 200:
            rate: float = r.json()["rates"][0]["mid"]
            _cache[key] = rate
            return rate

    raise ValueError(f"No NBP rate for {currency} on {on_date}")

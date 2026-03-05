import os
from typing import Literal

import yaml
from pydantic import BaseModel

Currency = Literal["PLN", "USD", "EUR"]


class AccountConfig(BaseModel):
    name: str
    gocardless_id: str
    actual_id: str
    currency: Currency


class Config(BaseModel):
    accounts: list[AccountConfig]


def load_config() -> Config:
    path = os.getenv("CONFIG_PATH", "/config/accounts.yaml")
    with open(path) as f:
        data = yaml.safe_load(f)
    return Config(**data)

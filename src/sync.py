import asyncio
import logging
import os
from datetime import date

import httpx
from actual import Actual
from actual.database import Transactions, int_to_date, select
from actual.queries import get_accounts

from .config import load_config
from .nbp import get_rate

logger = logging.getLogger(__name__)

CONVERTED_MARKER = "PLN @"


async def run_sync() -> None:
    config = load_config()
    foreign_accounts = [a for a in config.accounts if a.currency != "PLN"]

    if not foreign_accounts:
        logger.info("No foreign currency accounts, nothing to do")
        return

    logger.info(f"Converting {len(foreign_accounts)} accounts to PLN")

    async with httpx.AsyncClient(timeout=30) as client:
        with Actual(
            base_url=os.environ["ACTUAL_SERVER_URL"],
            password=os.environ["ACTUAL_PASSWORD"],
            file=os.environ["ACTUAL_BUDGET_NAME"],
            data_dir="/data/actual-sync",
        ) as actual:
            actual.download_budget()

            accounts = {a.id: a for a in get_accounts(actual.session)}

            for account_cfg in foreign_accounts:
                if account_cfg.actual_id not in accounts:
                    logger.warning(f"Account {account_cfg.actual_id!r} not found, skipping")
                    continue

                logger.info(f"Processing {account_cfg.name} ({account_cfg.currency})")

                txs = actual.session.exec(
                    select(Transactions).where(
                        Transactions.account_id == account_cfg.actual_id,
                        Transactions.tombstone == 0,
                    )
                ).all()

                updated = 0
                for tx in txs:
                    # Пропускаем уже сконвертированные
                    if tx.notes and CONVERTED_MARKER in tx.notes:
                        continue

                    tx_date = int_to_date(tx.date).isoformat()
                    rate = await get_rate(client, account_cfg.currency, tx_date)

                    original = tx.amount / 100
                    pln = round(original * rate * 100)

                    note = f"{account_cfg.currency} {original:.2f} @ {rate:.4f}"
                    tx.notes = f"{note} | {tx.notes}" if tx.notes else note
                    tx.amount = pln
                    updated += 1

                actual.commit()
                logger.info(f"{account_cfg.name}: {updated} transactions converted")
                await asyncio.sleep(1)

    logger.info("Sync complete")

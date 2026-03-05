import logging
import os
from datetime import date, timedelta

import httpx
from actual import Actual
from actual.models import Payees
from actual.queries import create_payee, create_transaction, get_accounts
from sqlmodel import select

from .config import load_config
from .gocardless import get_transactions
from .nbp import get_rate

logger = logging.getLogger(__name__)


def _get_or_create_payee(session, name: str) -> Payees | None:
    """actualpy's get_or_create_payee uses one_or_none() which crashes on duplicate payees."""
    if not name:
        return None
    payee = session.exec(
        select(Payees).filter(Payees.name == name, Payees.tombstone == 0)
    ).first()
    return payee or create_payee(session, name)


async def run_sync(days_back: int = 30) -> None:
    config = load_config()
    date_from = (date.today() - timedelta(days=days_back)).isoformat()
    logger.info(f"Sync from {date_from}")

    async with httpx.AsyncClient(timeout=30) as client:
        with Actual(
            base_url=os.environ["ACTUAL_SERVER_URL"],
            password=os.environ["ACTUAL_PASSWORD"],
            file=os.environ["ACTUAL_BUDGET_NAME"],
            data_dir="/data/actual-sync",
        ) as actual:
            actual.download_budget()

            accounts = {a.id: a for a in get_accounts(actual.session)}

            for account_cfg in config.accounts:
                if account_cfg.actual_id not in accounts:
                    logger.warning(f"Account {account_cfg.actual_id!r} not found in Actual, skipping")
                    continue

                logger.info(f"Syncing {account_cfg.name} ({account_cfg.currency})")
                transactions = await get_transactions(client, account_cfg.gocardless_id, date_from)
                logger.info(f"Got {len(transactions)} transactions")

                added = 0
                for tx in transactions:
                    tx_currency = tx["transactionAmount"]["currency"]
                    tx_amount = float(tx["transactionAmount"]["amount"])
                    tx_date = date.fromisoformat(tx["bookingDate"])
                    payee = tx.get("creditorName") or tx.get("debtorName") or ""
                    memo = tx.get("remittanceInformationUnstructured", "")

                    if tx_currency == "PLN":
                        pln_amount = tx_amount
                        notes = memo
                    else:
                        rate = await get_rate(client, tx_currency, tx["bookingDate"])
                        pln_amount = tx_amount * rate
                        notes = f"{tx_currency} {tx_amount:.2f} @ {rate:.4f}" + (f" | {memo}" if memo else "")

                    create_transaction(
                        actual.session,
                        date=tx_date,
                        account=accounts[account_cfg.actual_id],
                        payee=_get_or_create_payee(actual.session, payee),
                        notes=notes,
                        amount=round(pln_amount * 100),  # grosze
                        imported_id=tx["transactionId"],
                    )
                    added += 1

                actual.commit()
                logger.info(f"{account_cfg.name}: {added} transactions imported")

    logger.info("Sync complete")

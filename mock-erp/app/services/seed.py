"""Seed a minimal chart of accounts for the SME Asset Finance scenario."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models.account import Account
from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_ACCOUNTS = [
    {"external_reference": "GL-1100", "code": "1100", "name": "Bank", "type": "ASSET", "currency": "RWF"},
    {"external_reference": "GL-1200", "code": "1200", "name": "Loan Receivable", "type": "ASSET", "currency": "RWF"},
    {"external_reference": "GL-4000", "code": "4000", "name": "Interest Income", "type": "INCOME", "currency": "RWF"},
    {"external_reference": "GL-2100", "code": "2100", "name": "Suspense", "type": "LIABILITY", "currency": "RWF"},
]


async def seed_chart_of_accounts() -> None:
    async with AsyncSessionLocal() as session:
        for acc_data in DEFAULT_ACCOUNTS:
            exists = await session.scalar(
                select(Account).where(Account.external_reference == acc_data["external_reference"])
            )
            if not exists:
                session.add(Account(**acc_data))
                logger.info("Seeded account %s", acc_data["code"])
        await session.commit()
    logger.info("Chart of accounts seed complete")
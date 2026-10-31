"""Startup sweep and explicit recovery for interrupted operations."""

from __future__ import annotations

from sqlalchemy import select

from app.core.logging import get_logger
from app.core.state_machine import OperationStatus
from app.db.session import AsyncSessionLocal
from app.models.operation import Operation

logger = get_logger(__name__)


async def recovery_sweep() -> int:
    """
    On startup (or via admin endpoint) find operations that are in a recoverable
    state and either complete them or mark them for reconciliation.

    Recoverable states:
    - FINERACT_DONE  → still need ERP journal entry
    - ERP_PENDING    → ERP call may have timed out; safe to re-check / retry
    """
    recovered = 0
    async with AsyncSessionLocal() as session:
        result = await session.scalars(
            select(Operation).where(
                Operation.status.in_(
                    [
                        OperationStatus.FINERACT_DONE.value,
                        OperationStatus.ERP_PENDING.value,
                    ]
                )
            )
        )
        ops = list(result)
        for op in ops:
            logger.info(
                "Recovery candidate found",
                extra={
                    "external_reference": op.external_reference,
                    "status": op.status,
                    "operation_type": op.operation_type,
                },
            )
            # Mark for explicit reconciliation rather than auto-retrying blindly.
            # A more sophisticated implementation would re-drive the ERP call
            # after looking up the Fineract transaction by external reference.
            op.status = OperationStatus.NEEDS_RECONCILIATION.value
            recovered += 1
        await session.commit()
    logger.info("Recovery sweep finished", extra={"recovered": recovered})
    return recovered
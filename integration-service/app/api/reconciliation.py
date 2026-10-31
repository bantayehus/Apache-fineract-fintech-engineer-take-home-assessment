"""Reconciliation endpoint (Part K)."""

from __future__ import annotations

from datetime import date
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import AuthDep, CorrelationDep, SessionDep
from app.core.state_machine import OperationStatus
from app.models.operation import Operation
from app.services.erp_client import erp_client

router = APIRouter()


class ReconciliationRequest(BaseModel):
    from_date: date | None = None
    to_date: date | None = None
    references: list[str] = Field(default_factory=list)


class ReconciliationItem(BaseModel):
    external_reference: str
    status: Literal["MATCHED", "MISSING_IN_ERP", "MISSING_IN_FINERACT", "AMOUNT_MISMATCH"]
    fineract_transaction_id: str | None = None
    erp_transaction_id: str | None = None
    detail: str | None = None


class ReconciliationResponse(BaseModel):
    items: list[ReconciliationItem]
    correlation_id: str


@router.post("/reconciliation", response_model=ReconciliationResponse)
async def run_reconciliation(
    body: ReconciliationRequest,
    session: SessionDep,
    correlation_id: CorrelationDep,
    _: AuthDep,
) -> ReconciliationResponse:
    """
    Compare Integration operations (that reached Fineract) against ERP journal entries
    keyed by external_reference.
    """
    query = select(Operation).where(
        Operation.operation_type.in_(["DISBURSEMENT", "REPAYMENT"]),
        Operation.status.in_(
            [
                OperationStatus.COMPLETED.value,
                OperationStatus.FINERACT_DONE.value,
                OperationStatus.ERP_PENDING.value,
                OperationStatus.NEEDS_RECONCILIATION.value,
            ]
        ),
    )
    if body.references:
        query = query.where(Operation.external_reference.in_(body.references))

    ops = list(await session.scalars(query))
    items: list[ReconciliationItem] = []

    for op in ops:
        erp_entry = None
        try:
            erp_entry = await erp_client.get_journal_entry(op.external_reference)
        except Exception:
            erp_entry = None

        if op.fineract_transaction_id and erp_entry:
            items.append(
                ReconciliationItem(
                    external_reference=op.external_reference,
                    status="MATCHED",
                    fineract_transaction_id=op.fineract_transaction_id,
                    erp_transaction_id=str(erp_entry.get("id") or op.erp_transaction_id),
                )
            )
        elif op.fineract_transaction_id and not erp_entry:
            items.append(
                ReconciliationItem(
                    external_reference=op.external_reference,
                    status="MISSING_IN_ERP",
                    fineract_transaction_id=op.fineract_transaction_id,
                    detail="Present in Fineract / Integration but no ERP journal entry",
                )
            )
        elif not op.fineract_transaction_id and erp_entry:
            items.append(
                ReconciliationItem(
                    external_reference=op.external_reference,
                    status="MISSING_IN_FINERACT",
                    erp_transaction_id=str(erp_entry.get("id")),
                    detail="Present in ERP but no Fineract transaction recorded",
                )
            )
        else:
            items.append(
                ReconciliationItem(
                    external_reference=op.external_reference,
                    status="AMOUNT_MISMATCH",  # placeholder when both missing or amounts differ
                    detail="Unable to match or amounts differ",
                )
            )

    return ReconciliationResponse(items=items, correlation_id=correlation_id)
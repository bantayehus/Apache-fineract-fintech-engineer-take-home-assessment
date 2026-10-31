"""Lookup of integration transactions by external_reference."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.deps import AuthDep, CorrelationDep, SessionDep
from app.models.operation import Operation

router = APIRouter()


class TransactionResponse(BaseModel):
    external_reference: str
    operation_type: str
    status: str
    client_uid: str | None = None
    loan_reference: str | None = None
    fineract_transaction_id: str | None = None
    erp_transaction_id: str | None = None
    correlation_id: str | None = None
    error_message: str | None = None
    attempt_count: int = 0


@router.get("/transactions/{external_reference}", response_model=TransactionResponse)
async def get_transaction(
    external_reference: str,
    session: SessionDep,
    correlation_id: CorrelationDep,
    _: AuthDep,
) -> TransactionResponse:
    op = await session.scalar(
        select(Operation).where(Operation.external_reference == external_reference)
    )
    if not op:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Transaction not found"})
    return TransactionResponse(
        external_reference=op.external_reference,
        operation_type=op.operation_type,
        status=op.status,
        client_uid=op.client_uid,
        loan_reference=op.loan_reference,
        fineract_transaction_id=op.fineract_transaction_id,
        erp_transaction_id=op.erp_transaction_id,
        correlation_id=op.correlation_id or correlation_id,
        error_message=op.error_message,
        attempt_count=op.attempt_count,
    )
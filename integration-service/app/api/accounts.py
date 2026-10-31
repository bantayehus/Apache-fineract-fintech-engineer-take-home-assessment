"""GL account sync endpoint (Part A – Python side)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import AuthDep, CorrelationDep, SessionDep
from app.core.logging import get_logger
from app.core.state_machine import OperationStatus, can_transition
from app.models.mapping import GLAccountMapping
from app.models.operation import Operation
from app.services.account_type_mapping import map_erp_type_to_fineract
from app.services.fineract_client import fineract_client

router = APIRouter()
logger = get_logger(__name__)


class AccountSyncRequest(BaseModel):
    external_reference: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., pattern="^(ASSET|LIABILITY|EQUITY|INCOME|EXPENSE)$")
    currency: str = Field(default="RWF", min_length=3, max_length=3)


class AccountSyncResponse(BaseModel):
    external_reference: str
    code: str
    fineract_gl_id: str | None
    sync_status: str
    correlation_id: str


@router.post("/accounts/sync", response_model=AccountSyncResponse)
async def sync_account(
    body: AccountSyncRequest,
    session: SessionDep,
    correlation_id: CorrelationDep,
    _: AuthDep,
) -> AccountSyncResponse:
    """
    Synchronise an ERP-owned GL account into Fineract (create-only).
    Idempotent on external_reference.
    """
    logger.info(
        "GL sync requested",
        extra={"correlation_id": correlation_id, "external_reference": body.external_reference},
    )

    # Idempotency: look for an existing operation
    existing_op = await session.scalar(
        select(Operation).where(
            Operation.operation_type == "GL_SYNC",
            Operation.external_reference == body.external_reference,
        )
    )
    if existing_op and existing_op.status == OperationStatus.COMPLETED.value:
        mapping = await session.scalar(
            select(GLAccountMapping).where(GLAccountMapping.external_reference == body.external_reference)
        )
        return AccountSyncResponse(
            external_reference=body.external_reference,
            code=body.code,
            fineract_gl_id=mapping.fineract_gl_id if mapping else None,
            sync_status="SYNCED",
            correlation_id=correlation_id,
        )

    # Create or reuse operation record
    if not existing_op:
        op = Operation(
            operation_type="GL_SYNC",
            external_reference=body.external_reference,
            correlation_id=correlation_id,
            status=OperationStatus.RECEIVED.value,
            request_payload=body.model_dump(),
        )
        session.add(op)
        await session.flush()
    else:
        op = existing_op

    op.status = OperationStatus.FINERACT_PENDING.value
    op.attempt_count += 1
    await session.flush()

    try:
        fineract_type = map_erp_type_to_fineract(body.type)
        result = await fineract_client.create_gl_account(
            name=body.name,
            gl_code=body.code,
            type_=fineract_type,
            external_reference=body.external_reference,
        )
        resource_id = str(result.get("resourceId") or result.get("glAccountId") or "")
        op.fineract_resource_id = resource_id
        op.status = OperationStatus.FINERACT_DONE.value
        await session.flush()

        # Upsert local mapping
        mapping = await session.scalar(
            select(GLAccountMapping).where(GLAccountMapping.external_reference == body.external_reference)
        )
        if not mapping:
            mapping = GLAccountMapping(
                external_reference=body.external_reference,
                code=body.code,
                fineract_gl_id=resource_id,
                name=body.name,
                sync_status="SYNCED",
            )
            session.add(mapping)
        else:
            mapping.fineract_gl_id = resource_id
            mapping.sync_status = "SYNCED"

        op.status = OperationStatus.COMPLETED.value
        await session.flush()

        return AccountSyncResponse(
            external_reference=body.external_reference,
            code=body.code,
            fineract_gl_id=resource_id,
            sync_status="SYNCED",
            correlation_id=correlation_id,
        )
    except Exception as exc:
        op.status = OperationStatus.FAILED.value
        op.error_message = str(exc)
        await session.flush()
        logger.exception(
            "GL sync failed",
            extra={"correlation_id": correlation_id, "external_reference": body.external_reference},
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "FINERACT_ERROR", "message": str(exc), "correlation_id": correlation_id},
        )
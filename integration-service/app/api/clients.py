"""Client create / lookup (Part C)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import AuthDep, CorrelationDep, SessionDep
from app.core.logging import get_logger
from app.core.state_machine import OperationStatus
from app.models.mapping import ClientMapping
from app.models.operation import Operation
from app.services.fineract_client import fineract_client

router = APIRouter()
logger = get_logger(__name__)


class ClientCreateRequest(BaseModel):
    external_reference: str = Field(..., min_length=1, max_length=100)
    client_uid: str = Field(..., min_length=1, max_length=64)
    firstname: str = Field(..., min_length=1)
    lastname: str = Field(..., min_length=1)
    office: str = "Kigali Main Office"


class ClientResponse(BaseModel):
    client_uid: str
    firstname: str | None = None
    lastname: str | None = None
    display_name: str | None = None
    active: bool | None = None
    correlation_id: str


@router.post("/clients", response_model=ClientResponse, status_code=status.HTTP_200_OK)
async def create_client(
    body: ClientCreateRequest,
    session: SessionDep,
    correlation_id: CorrelationDep,
    _: AuthDep,
) -> ClientResponse:
    """Create a client. Idempotent on external_reference. client_uid is unique."""
    # Check existing operation
    existing_op = await session.scalar(
        select(Operation).where(
            Operation.operation_type == "CLIENT_CREATE",
            Operation.external_reference == body.external_reference,
        )
    )
    if existing_op and existing_op.status == OperationStatus.COMPLETED.value:
        mapping = await session.scalar(
            select(ClientMapping).where(ClientMapping.client_uid == body.client_uid)
        )
        return ClientResponse(
            client_uid=body.client_uid,
            display_name=mapping.display_name if mapping else None,
            correlation_id=correlation_id,
        )

    # client_uid uniqueness
    uid_exists = await session.scalar(
        select(ClientMapping).where(ClientMapping.client_uid == body.client_uid)
    )
    if uid_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CONFLICT", "message": f"client_uid {body.client_uid} already exists"},
        )

    op = Operation(
        operation_type="CLIENT_CREATE",
        external_reference=body.external_reference,
        correlation_id=correlation_id,
        client_uid=body.client_uid,
        status=OperationStatus.RECEIVED.value,
        request_payload=body.model_dump(),
    )
    session.add(op)
    await session.flush()

    op.status = OperationStatus.FINERACT_PENDING.value
    try:
        today = date.today().isoformat()
        result = await fineract_client.create_client(
            firstname=body.firstname,
            lastname=body.lastname,
            external_id=body.client_uid,
            active=True,
            activation_date=today,
        )
        resource_id = str(result.get("clientId") or result.get("resourceId") or "")
        op.fineract_resource_id = resource_id
        op.status = OperationStatus.FINERACT_DONE.value

        mapping = ClientMapping(
            client_uid=body.client_uid,
            fineract_client_id=resource_id,
            external_reference=body.external_reference,
            display_name=f"{body.firstname} {body.lastname}",
        )
        session.add(mapping)
        op.status = OperationStatus.COMPLETED.value
        await session.flush()

        return ClientResponse(
            client_uid=body.client_uid,
            firstname=body.firstname,
            lastname=body.lastname,
            display_name=mapping.display_name,
            active=True,
            correlation_id=correlation_id,
        )
    except Exception as exc:
        op.status = OperationStatus.FAILED.value
        op.error_message = str(exc)
        await session.flush()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "FINERACT_ERROR", "message": str(exc), "correlation_id": correlation_id},
        )


@router.get("/clients/{client_uid}", response_model=ClientResponse)
async def get_client(
    client_uid: str,
    session: SessionDep,
    correlation_id: CorrelationDep,
    _: AuthDep,
) -> ClientResponse:
    mapping = await session.scalar(
        select(ClientMapping).where(ClientMapping.client_uid == client_uid)
    )
    if not mapping:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Client not found"})

    # Optionally validate against Fineract
    try:
        ft = await fineract_client.get_client_by_external_id(client_uid)
        return ClientResponse(
            client_uid=client_uid,
            firstname=ft.get("firstname"),
            lastname=ft.get("lastname"),
            display_name=ft.get("displayName") or mapping.display_name,
            active=ft.get("active"),
            correlation_id=correlation_id,
        )
    except Exception:
        return ClientResponse(
            client_uid=client_uid,
            display_name=mapping.display_name,
            correlation_id=correlation_id,
        )
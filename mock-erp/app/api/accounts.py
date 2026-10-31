from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.models.account import Account

router = APIRouter()


class AccountCreate(BaseModel):
    external_reference: str = Field(..., min_length=1, max_length=100)
    code: str = Field(..., min_length=1, max_length=20)
    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., pattern="^(ASSET|LIABILITY|EQUITY|INCOME|EXPENSE)$")
    currency: str = Field(default="RWF", min_length=3, max_length=3)


class AccountOut(BaseModel):
    id: int
    external_reference: str
    code: str
    name: str
    type: str
    currency: str
    balance: Decimal

    model_config = {"from_attributes": True}


@router.post("/accounts", response_model=AccountOut, status_code=status.HTTP_200_OK)
async def create_account(
    body: AccountCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Account:
    """Create a GL account. Idempotent on external_reference."""
    existing = await session.scalar(
        select(Account).where(Account.external_reference == body.external_reference)
    )
    if existing:
        # Same reference – check payload identity
        if (
            existing.code == body.code
            and existing.name == body.name
            and existing.type == body.type
            and existing.currency == body.currency
        ):
            return existing
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "CONFLICT",
                "message": "external_reference already exists with a different payload",
            },
        )

    # Also enforce unique code
    code_exists = await session.scalar(select(Account).where(Account.code == body.code))
    if code_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "CONFLICT", "message": f"Account code {body.code} already exists"},
        )

    account = Account(
        external_reference=body.external_reference,
        code=body.code,
        name=body.name,
        type=body.type,
        currency=body.currency,
        balance=Decimal("0"),
    )
    session.add(account)
    await session.flush()
    await session.refresh(account)
    return account


@router.get("/accounts", response_model=list[AccountOut])
async def list_accounts(session: Annotated[AsyncSession, Depends(get_session)]) -> list[Account]:
    result = await session.scalars(select(Account).order_by(Account.code))
    return list(result)


@router.get("/accounts/{code}/balance", response_model=AccountOut)
async def get_balance(
    code: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> Account:
    account = await session.scalar(select(Account).where(Account.code == code))
    if not account:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": f"Account {code} not found"})
    return account
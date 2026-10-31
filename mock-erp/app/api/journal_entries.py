from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.session import get_session
from app.models.account import Account
from app.models.journal import JournalEntry, JournalLine

router = APIRouter()


class JournalLineIn(BaseModel):
    account_code: str
    debit: Decimal = Field(default=Decimal("0"), ge=0)
    credit: Decimal = Field(default=Decimal("0"), ge=0)
    description: str | None = None


class JournalEntryCreate(BaseModel):
    external_reference: str = Field(..., min_length=1, max_length=100)
    description: str | None = None
    entry_date: datetime
    lines: list[JournalLineIn] = Field(..., min_length=2)

    @field_validator("lines")
    @classmethod
    def must_balance(cls, lines: list[JournalLineIn]) -> list[JournalLineIn]:
        total_debit = sum(l.debit for l in lines)
        total_credit = sum(l.credit for l in lines)
        if total_debit != total_credit:
            raise ValueError(f"Entry does not balance: debits={total_debit} credits={total_credit}")
        if total_debit == 0:
            raise ValueError("Entry must have non-zero amounts")
        for line in lines:
            if (line.debit > 0 and line.credit > 0) or (line.debit == 0 and line.credit == 0):
                raise ValueError("Each line must be either debit or credit, not both or neither")
        return lines


class JournalLineOut(BaseModel):
    account_code: str
    debit: Decimal
    credit: Decimal
    description: str | None

    model_config = {"from_attributes": True}


class JournalEntryOut(BaseModel):
    id: int
    external_reference: str
    description: str | None
    entry_date: datetime
    lines: list[JournalLineOut]

    model_config = {"from_attributes": True}


@router.post("/journal-entries", response_model=JournalEntryOut, status_code=status.HTTP_200_OK)
async def create_journal_entry(
    body: JournalEntryCreate,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JournalEntry:
    """Create a balanced journal entry. Idempotent on external_reference."""
    existing = await session.scalar(
        select(JournalEntry)
        .where(JournalEntry.external_reference == body.external_reference)
        .options(selectinload(JournalEntry.lines))
    )
    if existing:
        return existing  # Idempotent – return original

    # Validate all account codes exist
    for line in body.lines:
        acc = await session.scalar(select(Account).where(Account.code == line.account_code))
        if not acc:
            raise HTTPException(
                status_code=400,
                detail={"code": "INVALID_ACCOUNT", "message": f"Account code {line.account_code} does not exist"},
            )

    entry = JournalEntry(
        external_reference=body.external_reference,
        description=body.description,
        entry_date=body.entry_date,
    )
    session.add(entry)
    await session.flush()

    for line_in in body.lines:
        line = JournalLine(
            journal_entry_id=entry.id,
            account_code=line_in.account_code,
            debit=line_in.debit,
            credit=line_in.credit,
            description=line_in.description,
        )
        session.add(line)

        # Update running balance
        acc = await session.scalar(select(Account).where(Account.code == line_in.account_code))
        if acc:
            # Simple signed balance: assets/expenses increase with debit
            if acc.type in ("ASSET", "EXPENSE"):
                acc.balance = acc.balance + line_in.debit - line_in.credit
            else:
                acc.balance = acc.balance + line_in.credit - line_in.debit

    await session.flush()
    await session.refresh(entry, attribute_names=["lines"])
    return entry


@router.get("/journal-entries/{external_reference}", response_model=JournalEntryOut)
async def get_journal_entry(
    external_reference: str,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JournalEntry:
    entry = await session.scalar(
        select(JournalEntry)
        .where(JournalEntry.external_reference == external_reference)
        .options(selectinload(JournalEntry.lines))
    )
    if not entry:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Journal entry not found"})
    return entry
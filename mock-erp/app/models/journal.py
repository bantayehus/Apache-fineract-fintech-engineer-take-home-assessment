from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Numeric, DateTime, ForeignKey, UniqueConstraint, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class JournalEntry(Base):
    __tablename__ = "journal_entries"
    __table_args__ = (
        UniqueConstraint("external_reference", name="uq_journal_external_reference"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    entry_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    lines: Mapped[list["JournalLine"]] = relationship(back_populates="entry", cascade="all, delete-orphan")


class JournalLine(Base):
    __tablename__ = "journal_lines"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    journal_entry_id: Mapped[int] = mapped_column(ForeignKey("journal_entries.id"), nullable=False)
    account_code: Mapped[str] = mapped_column(String(20), nullable=False)
    debit: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False, default=Decimal("0"))
    credit: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False, default=Decimal("0"))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    entry: Mapped["JournalEntry"] = relationship(back_populates="lines")
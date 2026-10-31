from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Numeric, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("external_reference", name="uq_accounts_external_reference"),
        UniqueConstraint("code", name="uq_accounts_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # ASSET, LIABILITY, EQUITY, INCOME, EXPENSE
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="RWF")
    balance: Mapped[Decimal] = mapped_column(Numeric(19, 6), nullable=False, default=Decimal("0"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
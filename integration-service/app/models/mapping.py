"""Local mapping tables so callers never see Fineract numeric IDs."""

from datetime import datetime

from sqlalchemy import String, DateTime, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class ClientMapping(Base):
    __tablename__ = "client_mappings"
    __table_args__ = (
        UniqueConstraint("client_uid", name="uq_client_uid"),
        UniqueConstraint("fineract_client_id", name="uq_fineract_client_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    fineract_client_id: Mapped[str] = mapped_column(String(64), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LoanMapping(Base):
    __tablename__ = "loan_mappings"
    __table_args__ = (
        UniqueConstraint("loan_reference", name="uq_loan_reference"),
        UniqueConstraint("fineract_loan_id", name="uq_fineract_loan_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    loan_reference: Mapped[str] = mapped_column(String(64), nullable=False)
    client_uid: Mapped[str] = mapped_column(String(64), nullable=False)
    fineract_loan_id: Mapped[str] = mapped_column(String(64), nullable=False)
    external_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class GLAccountMapping(Base):
    __tablename__ = "gl_account_mappings"
    __table_args__ = (
        UniqueConstraint("external_reference", name="uq_gl_ext_ref"),
        UniqueConstraint("fineract_gl_id", name="uq_fineract_gl_id"),
        UniqueConstraint("code", name="uq_gl_code"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(20), nullable=False)
    fineract_gl_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False, default="SYNCED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
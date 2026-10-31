"""Persisted state-machine record for every state-changing financial operation."""

from datetime import datetime
from typing import Any

from sqlalchemy import String, DateTime, Text, Integer, UniqueConstraint, func, Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base
from app.core.state_machine import OperationStatus


class Operation(Base):
    """
    One row per business operation (GL sync, client create, loan app,
    disbursement, repayment). Uniqueness is scoped by (operation_type, external_reference).
    """

    __tablename__ = "operations"
    __table_args__ = (
        UniqueConstraint("operation_type", "external_reference", name="uq_op_type_ext_ref"),
        Index("ix_operations_status", "status"),
        Index("ix_operations_loan_reference", "loan_reference"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    operation_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # GL_SYNC | CLIENT_CREATE | LOAN_APPLICATION | LOAN_APPROVAL | DISBURSEMENT | REPAYMENT
    external_reference: Mapped[str] = mapped_column(String(100), nullable=False)
    correlation_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    status: Mapped[str] = mapped_column(String(40), nullable=False, default=OperationStatus.RECEIVED.value)

    # Business identifiers (never Fineract numeric IDs as primary keys)
    client_uid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    loan_reference: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Payloads & results
    request_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    response_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    fineract_resource_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    fineract_transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    erp_transaction_id: Mapped[str | None] = mapped_column(String(64), nullable=True)

    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
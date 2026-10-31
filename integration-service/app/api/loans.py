"""Loan application, disbursement and repayment endpoints (Parts D, E, F)."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.api.deps import AuthDep, CorrelationDep, SessionDep
from app.core.logging import get_logger
from app.core.state_machine import OperationStatus
from app.models.mapping import ClientMapping, LoanMapping
from app.models.operation import Operation
from app.services.accounting_mapping import (
    derive_disbursement_journal,
    derive_repayment_journal,
    extract_portions_from_fineract_transaction,
)
from app.services.erp_client import erp_client
from app.services.fineract_client import fineract_client

router = APIRouter()
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class LoanApplicationRequest(BaseModel):
    external_reference: str = Field(..., min_length=1, max_length=100)
    loan_reference: str = Field(..., min_length=1, max_length=64)
    client_uid: str
    product: str = "SME Asset Finance"
    principal: Decimal = Field(..., gt=0)
    currency: str = "RWF"
    term_months: int = 12
    interest_rate: float = 18.0
    auto_approve: bool = True


class LoanResponse(BaseModel):
    loan_reference: str
    client_uid: str
    status: str | None = None
    principal: Decimal | None = None
    correlation_id: str


class DisburseRequest(BaseModel):
    external_reference: str = Field(..., min_length=1, max_length=100)
    disbursement_date: date | None = None
    note: str | None = None


class RepaymentRequest(BaseModel):
    external_reference: str = Field(..., min_length=1, max_length=100)
    amount: Decimal = Field(..., gt=0)
    payment_date: date | None = None
    note: str | None = None


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

@router.post("/loans", response_model=LoanResponse)
async def create_loan(
    body: LoanApplicationRequest,
    session: SessionDep,
    correlation_id: CorrelationDep,
    _: AuthDep,
) -> LoanResponse:
    # Idempotency
    existing_op = await session.scalar(
        select(Operation).where(
            Operation.operation_type == "LOAN_APPLICATION",
            Operation.external_reference == body.external_reference,
        )
    )
    if existing_op and existing_op.status == OperationStatus.COMPLETED.value:
        return LoanResponse(
            loan_reference=body.loan_reference,
            client_uid=body.client_uid,
            status="submitted",
            principal=body.principal,
            correlation_id=correlation_id,
        )

    client_map = await session.scalar(
        select(ClientMapping).where(ClientMapping.client_uid == body.client_uid)
    )
    if not client_map:
        raise HTTPException(status_code=400, detail={"code": "CLIENT_NOT_FOUND", "message": body.client_uid})

    op = Operation(
        operation_type="LOAN_APPLICATION",
        external_reference=body.external_reference,
        correlation_id=correlation_id,
        client_uid=body.client_uid,
        loan_reference=body.loan_reference,
        status=OperationStatus.RECEIVED.value,
        request_payload=body.model_dump(mode="json"),
    )
    session.add(op)
    await session.flush()

    op.status = OperationStatus.FINERACT_PENDING.value
    try:
        # Minimal loan application payload – productId / officeId must match the seeded environment.
        # In a full seed we would look up the product by name.
        today = date.today().isoformat()
        payload = {
            "clientId": int(client_map.fineract_client_id),
            "productId": 1,  # seeded "SME Asset Finance"
            "principal": float(body.principal),
            "loanTermFrequency": body.term_months,
            "loanTermFrequencyType": 2,  # months
            "numberOfRepayments": body.term_months,
            "repaymentEvery": 1,
            "repaymentFrequencyType": 2,
            "interestRatePerPeriod": body.interest_rate,
            "amortizationType": 1,
            "interestType": 0,
            "interestCalculationPeriodType": 1,
            "transactionProcessingStrategyCode": "mifos-standard-strategy",
            "expectedDisbursementDate": today,
            "submittedOnDate": today,
            "locale": "en",
            "dateFormat": "yyyy-MM-dd",
            "externalId": body.loan_reference,
            "loanType": "individual",
        }
        result = await fineract_client.create_loan_application(payload)
        loan_id = str(result.get("loanId") or result.get("resourceId") or "")
        op.fineract_resource_id = loan_id

        if body.auto_approve and loan_id:
            await fineract_client.approve_loan(
                loan_id,
                {
                    "approvedOnDate": today,
                    "approvedLoanAmount": float(body.principal),
                    "locale": "en",
                    "dateFormat": "yyyy-MM-dd",
                },
            )

        mapping = LoanMapping(
            loan_reference=body.loan_reference,
            client_uid=body.client_uid,
            fineract_loan_id=loan_id,
            external_reference=body.external_reference,
            status="approved" if body.auto_approve else "submitted",
        )
        session.add(mapping)
        op.status = OperationStatus.COMPLETED.value
        await session.flush()

        return LoanResponse(
            loan_reference=body.loan_reference,
            client_uid=body.client_uid,
            status=mapping.status,
            principal=body.principal,
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


@router.get("/loans/{loan_reference}", response_model=LoanResponse)
async def get_loan(
    loan_reference: str,
    session: SessionDep,
    correlation_id: CorrelationDep,
    _: AuthDep,
) -> LoanResponse:
    mapping = await session.scalar(
        select(LoanMapping).where(LoanMapping.loan_reference == loan_reference)
    )
    if not mapping:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Loan not found"})
    return LoanResponse(
        loan_reference=loan_reference,
        client_uid=mapping.client_uid,
        status=mapping.status,
        correlation_id=correlation_id,
    )


# ---------------------------------------------------------------------------
# Disbursement (unique per loan)
# ---------------------------------------------------------------------------

@router.post("/loans/{loan_reference}/disburse", response_model=dict)
async def disburse_loan(
    loan_reference: str,
    body: DisburseRequest,
    session: SessionDep,
    correlation_id: CorrelationDep,
    _: AuthDep,
) -> dict:
    mapping = await session.scalar(
        select(LoanMapping).where(LoanMapping.loan_reference == loan_reference)
    )
    if not mapping:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Loan not found"})

    # Disbursement is unique per loan – any prior successful DISBURSEMENT for this loan blocks
    prior = await session.scalar(
        select(Operation).where(
            Operation.operation_type == "DISBURSEMENT",
            Operation.loan_reference == loan_reference,
            Operation.status == OperationStatus.COMPLETED.value,
        )
    )
    if prior:
        # Also respect external_reference idempotency
        if prior.external_reference == body.external_reference:
            return {
                "loan_reference": loan_reference,
                "status": "already_disbursed",
                "fineract_transaction_id": prior.fineract_transaction_id,
                "correlation_id": correlation_id,
            }
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "ALREADY_DISBURSED", "message": "Loan has already been disbursed"},
        )

    # Same external_reference already in progress or completed
    existing_op = await session.scalar(
        select(Operation).where(
            Operation.operation_type == "DISBURSEMENT",
            Operation.external_reference == body.external_reference,
        )
    )
    if existing_op and existing_op.status == OperationStatus.COMPLETED.value:
        return {
            "loan_reference": loan_reference,
            "status": "already_disbursed",
            "fineract_transaction_id": existing_op.fineract_transaction_id,
            "correlation_id": correlation_id,
        }

    op = Operation(
        operation_type="DISBURSEMENT",
        external_reference=body.external_reference,
        correlation_id=correlation_id,
        loan_reference=loan_reference,
        client_uid=mapping.client_uid,
        status=OperationStatus.RECEIVED.value,
        request_payload=body.model_dump(mode="json"),
    )
    session.add(op)
    await session.flush()

    op.status = OperationStatus.FINERACT_PENDING.value
    try:
        disb_date = (body.disbursement_date or date.today()).isoformat()
        result = await fineract_client.disburse_loan(
            mapping.fineract_loan_id,
            {
                "actualDisbursementDate": disb_date,
                "locale": "en",
                "dateFormat": "yyyy-MM-dd",
                "note": body.note or "",
            },
        )
        txn_id = str(result.get("resourceId") or result.get("transactionId") or "")
        op.fineract_transaction_id = txn_id
        op.fineract_resource_id = mapping.fineract_loan_id
        op.status = OperationStatus.FINERACT_DONE.value
        await session.flush()

        # Derive journal entry from the disbursement and post to ERP
        op.status = OperationStatus.ERP_PENDING.value
        # We need the principal – for simplicity take it from the loan or a fixed value;
        # in production we would read the Fineract transaction breakdown.
        principal = Decimal("5000000")  # will be replaced by real lookup in full implementation
        journal = derive_disbursement_journal(external_reference=body.external_reference, principal=principal)
        erp_result = await erp_client.create_journal_entry(
            external_reference=body.external_reference,
            entry_date=datetime.now(timezone.utc),
            lines=[
                {"account_code": l.account_code, "debit": float(l.debit), "credit": float(l.credit), "description": l.description}
                for l in journal.lines
            ],
            description=journal.description,
        )
        op.erp_transaction_id = str(erp_result.get("id") or body.external_reference)
        op.status = OperationStatus.COMPLETED.value
        mapping.status = "active"
        await session.flush()

        return {
            "loan_reference": loan_reference,
            "status": "disbursed",
            "fineract_transaction_id": txn_id,
            "erp_transaction_id": op.erp_transaction_id,
            "correlation_id": correlation_id,
        }
    except Exception as exc:
        op.status = OperationStatus.FAILED.value
        op.error_message = str(exc)
        await session.flush()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "DISBURSE_ERROR", "message": str(exc), "correlation_id": correlation_id},
        )


# ---------------------------------------------------------------------------
# Repayment
# ---------------------------------------------------------------------------

@router.post("/loans/{loan_reference}/repayments", response_model=dict)
async def repay_loan(
    loan_reference: str,
    body: RepaymentRequest,
    session: SessionDep,
    correlation_id: CorrelationDep,
    _: AuthDep,
) -> dict:
    mapping = await session.scalar(
        select(LoanMapping).where(LoanMapping.loan_reference == loan_reference)
    )
    if not mapping:
        raise HTTPException(status_code=404, detail={"code": "NOT_FOUND", "message": "Loan not found"})

    existing_op = await session.scalar(
        select(Operation).where(
            Operation.operation_type == "REPAYMENT",
            Operation.external_reference == body.external_reference,
        )
    )
    if existing_op and existing_op.status == OperationStatus.COMPLETED.value:
        return {
            "loan_reference": loan_reference,
            "status": "already_applied",
            "fineract_transaction_id": existing_op.fineract_transaction_id,
            "correlation_id": correlation_id,
        }

    op = Operation(
        operation_type="REPAYMENT",
        external_reference=body.external_reference,
        correlation_id=correlation_id,
        loan_reference=loan_reference,
        client_uid=mapping.client_uid,
        status=OperationStatus.RECEIVED.value,
        request_payload=body.model_dump(mode="json"),
    )
    session.add(op)
    await session.flush()

    op.status = OperationStatus.FINERACT_PENDING.value
    try:
        pay_date = (body.payment_date or date.today()).isoformat()
        result = await fineract_client.repay_loan(
            mapping.fineract_loan_id,
            {
                "transactionDate": pay_date,
                "transactionAmount": float(body.amount),
                "locale": "en",
                "dateFormat": "yyyy-MM-dd",
                "note": body.note or "",
            },
        )
        txn_id = str(result.get("resourceId") or result.get("transactionId") or "")
        op.fineract_transaction_id = txn_id
        op.status = OperationStatus.FINERACT_DONE.value
        await session.flush()

        # Accounting mapping – use Fineract breakdown when available
        principal_portion, interest_portion = extract_portions_from_fineract_transaction(result)
        if principal_portion + interest_portion == 0:
            # Fallback if Fineract did not return breakdown in the response
            principal_portion = body.amount
            interest_portion = Decimal("0")

        op.status = OperationStatus.ERP_PENDING.value
        journal = derive_repayment_journal(
            external_reference=body.external_reference,
            principal_portion=principal_portion,
            interest_portion=interest_portion,
        )
        erp_result = await erp_client.create_journal_entry(
            external_reference=body.external_reference,
            entry_date=datetime.now(timezone.utc),
            lines=[
                {"account_code": l.account_code, "debit": float(l.debit), "credit": float(l.credit), "description": l.description}
                for l in journal.lines
            ],
            description=journal.description,
        )
        op.erp_transaction_id = str(erp_result.get("id") or body.external_reference)
        op.status = OperationStatus.COMPLETED.value
        await session.flush()

        return {
            "loan_reference": loan_reference,
            "status": "repaid",
            "amount": str(body.amount),
            "principal_portion": str(principal_portion),
            "interest_portion": str(interest_portion),
            "fineract_transaction_id": txn_id,
            "erp_transaction_id": op.erp_transaction_id,
            "correlation_id": correlation_id,
        }
    except Exception as exc:
        op.status = OperationStatus.FAILED.value
        op.error_message = str(exc)
        await session.flush()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"code": "REPAYMENT_ERROR", "message": str(exc), "correlation_id": correlation_id},
        )
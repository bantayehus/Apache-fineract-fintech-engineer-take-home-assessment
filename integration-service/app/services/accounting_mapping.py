"""
Pure, unit-tested function that derives balanced journal entries
from Fineract transaction data (Part H).

Never recalculates interest independently – always uses the breakdown
returned by Fineract.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Literal


@dataclass(frozen=True)
class JournalLine:
    account_code: str
    debit: Decimal
    credit: Decimal
    description: str | None = None


@dataclass(frozen=True)
class DerivedJournal:
    external_reference: str
    description: str
    lines: list[JournalLine]

    def is_balanced(self) -> bool:
        total_debit = sum(l.debit for l in self.lines)
        total_credit = sum(l.credit for l in self.lines)
        return total_debit == total_credit and total_debit > 0


# Default chart codes used by the assessment seed
BANK_CODE = "1100"
LOAN_RECEIVABLE_CODE = "1200"
INTEREST_INCOME_CODE = "4000"


def derive_disbursement_journal(
    *,
    external_reference: str,
    principal: Decimal,
    bank_code: str = BANK_CODE,
    loan_receivable_code: str = LOAN_RECEIVABLE_CODE,
) -> DerivedJournal:
    """
    Disbursement: DR Loan Receivable / CR Bank
    """
    if principal <= 0:
        raise ValueError("Disbursement principal must be positive")
    lines = [
        JournalLine(account_code=loan_receivable_code, debit=principal, credit=Decimal("0"), description="Loan principal"),
        JournalLine(account_code=bank_code, debit=Decimal("0"), credit=principal, description="Cash outflow"),
    ]
    journal = DerivedJournal(
        external_reference=external_reference,
        description=f"Disbursement {external_reference}",
        lines=lines,
    )
    assert journal.is_balanced()
    return journal


def derive_repayment_journal(
    *,
    external_reference: str,
    principal_portion: Decimal,
    interest_portion: Decimal,
    bank_code: str = BANK_CODE,
    loan_receivable_code: str = LOAN_RECEIVABLE_CODE,
    interest_income_code: str = INTEREST_INCOME_CODE,
) -> DerivedJournal:
    """
    Repayment: DR Bank / CR Loan Receivable (principal) / CR Interest Income (interest)

    principal_portion and interest_portion MUST come from Fineract's
    transaction breakdown, never from local interest calculation.
    """
    if principal_portion < 0 or interest_portion < 0:
        raise ValueError("Portions must be non-negative")
    total = principal_portion + interest_portion
    if total <= 0:
        raise ValueError("Repayment total must be positive")

    lines: list[JournalLine] = [
        JournalLine(account_code=bank_code, debit=total, credit=Decimal("0"), description="Cash inflow"),
    ]
    if principal_portion > 0:
        lines.append(
            JournalLine(
                account_code=loan_receivable_code,
                debit=Decimal("0"),
                credit=principal_portion,
                description="Principal repayment",
            )
        )
    if interest_portion > 0:
        lines.append(
            JournalLine(
                account_code=interest_income_code,
                debit=Decimal("0"),
                credit=interest_portion,
                description="Interest income",
            )
        )

    journal = DerivedJournal(
        external_reference=external_reference,
        description=f"Repayment {external_reference}",
        lines=lines,
    )
    assert journal.is_balanced()
    return journal


def extract_portions_from_fineract_transaction(txn: dict) -> tuple[Decimal, Decimal]:
    """
    Pull principal and interest portions from a Fineract loan transaction object.
    Fineract returns these under keys such as 'principalPortion' / 'interestPortion'
    (exact key names can vary slightly by version; this helper centralises the mapping).
    """
    principal = Decimal(str(txn.get("principalPortion") or txn.get("principal_portion") or 0))
    interest = Decimal(str(txn.get("interestPortion") or txn.get("interest_portion") or 0))
    return principal, interest
from decimal import Decimal

import pytest

from app.services.accounting_mapping import (
    derive_disbursement_journal,
    derive_repayment_journal,
    extract_portions_from_fineract_transaction,
)


def test_disbursement_balanced():
    j = derive_disbursement_journal(external_reference="DISB-1", principal=Decimal("5000000"))
    assert j.is_balanced()
    assert len(j.lines) == 2
    assert j.lines[0].debit == Decimal("5000000")
    assert j.lines[1].credit == Decimal("5000000")


def test_disbursement_rejects_zero():
    with pytest.raises(ValueError):
        derive_disbursement_journal(external_reference="X", principal=Decimal("0"))


def test_repayment_with_interest():
    j = derive_repayment_journal(
        external_reference="REP-1",
        principal_portion=Decimal("400000"),
        interest_portion=Decimal("100000"),
    )
    assert j.is_balanced()
    total_debit = sum(l.debit for l in j.lines)
    assert total_debit == Decimal("500000")


def test_repayment_principal_only():
    j = derive_repayment_journal(
        external_reference="REP-2",
        principal_portion=Decimal("500000"),
        interest_portion=Decimal("0"),
    )
    assert j.is_balanced()
    assert len(j.lines) == 2  # bank + loan receivable only


def test_extract_portions():
    txn = {"principalPortion": 300000, "interestPortion": 50000}
    p, i = extract_portions_from_fineract_transaction(txn)
    assert p == Decimal("300000")
    assert i == Decimal("50000")
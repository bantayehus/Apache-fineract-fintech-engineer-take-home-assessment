from app.core.state_machine import (
    OperationStatus,
    can_transition,
    SAFE_TO_RETRY,
    ALLOWED_TRANSITIONS,
)


def test_happy_path_transitions():
    assert can_transition(OperationStatus.RECEIVED, OperationStatus.FINERACT_PENDING)
    assert can_transition(OperationStatus.FINERACT_PENDING, OperationStatus.FINERACT_DONE)
    assert can_transition(OperationStatus.FINERACT_DONE, OperationStatus.ERP_PENDING)
    assert can_transition(OperationStatus.ERP_PENDING, OperationStatus.COMPLETED)


def test_terminal_has_no_outgoing():
    assert ALLOWED_TRANSITIONS[OperationStatus.COMPLETED] == set()


def test_safe_to_retry():
    assert OperationStatus.ERP_PENDING in SAFE_TO_RETRY
    assert OperationStatus.COMPLETED not in SAFE_TO_RETRY


def test_invalid_transition():
    assert not can_transition(OperationStatus.COMPLETED, OperationStatus.RECEIVED)
"""Explicit state machine for every state-changing financial operation."""

from enum import Enum
from typing import Final


class OperationStatus(str, Enum):
    RECEIVED = "RECEIVED"
    FINERACT_PENDING = "FINERACT_PENDING"
    FINERACT_DONE = "FINERACT_DONE"
    ERP_PENDING = "ERP_PENDING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION"


# Allowed transitions
ALLOWED_TRANSITIONS: Final[dict[OperationStatus, set[OperationStatus]]] = {
    OperationStatus.RECEIVED: {OperationStatus.FINERACT_PENDING, OperationStatus.FAILED},
    OperationStatus.FINERACT_PENDING: {
        OperationStatus.FINERACT_DONE,
        OperationStatus.FAILED,
        OperationStatus.NEEDS_RECONCILIATION,
    },
    OperationStatus.FINERACT_DONE: {
        OperationStatus.ERP_PENDING,
        OperationStatus.FAILED,
        OperationStatus.NEEDS_RECONCILIATION,
    },
    OperationStatus.ERP_PENDING: {
        OperationStatus.COMPLETED,
        OperationStatus.FAILED,
        OperationStatus.NEEDS_RECONCILIATION,
    },
    OperationStatus.COMPLETED: set(),
    OperationStatus.FAILED: {OperationStatus.FINERACT_PENDING},  # allow controlled retry
    OperationStatus.NEEDS_RECONCILIATION: {OperationStatus.COMPLETED, OperationStatus.FAILED},
}


def can_transition(current: OperationStatus, target: OperationStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


# What is safe to retry
SAFE_TO_RETRY: Final[set[OperationStatus]] = {
    OperationStatus.RECEIVED,
    OperationStatus.FINERACT_PENDING,  # only after lookup confirms not already done
    OperationStatus.ERP_PENDING,
    OperationStatus.FAILED,
}
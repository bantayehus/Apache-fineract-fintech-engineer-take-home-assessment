"""
Explicit, unit-tested mapping from ERP account types to Fineract GL types.

Fineract GL type integers (from GLAccountType):
  1 = ASSET
  2 = LIABILITY
  3 = EQUITY
  4 = INCOME
  5 = EXPENSE
"""

from __future__ import annotations

ERP_TO_FINERACT_TYPE: dict[str, int] = {
    "ASSET": 1,
    "LIABILITY": 2,
    "EQUITY": 3,
    "INCOME": 4,
    "EXPENSE": 5,
}

FINERACT_TO_ERP_TYPE: dict[int, str] = {v: k for k, v in ERP_TO_FINERACT_TYPE.items()}


def map_erp_type_to_fineract(erp_type: str) -> int:
    key = erp_type.strip().upper()
    if key not in ERP_TO_FINERACT_TYPE:
        raise ValueError(f"Unknown ERP account type: {erp_type!r}. Expected one of {list(ERP_TO_FINERACT_TYPE)}")
    return ERP_TO_FINERACT_TYPE[key]


def map_fineract_type_to_erp(fineract_type: int) -> str:
    if fineract_type not in FINERACT_TO_ERP_TYPE:
        raise ValueError(f"Unknown Fineract GL type: {fineract_type}")
    return FINERACT_TO_ERP_TYPE[fineract_type]
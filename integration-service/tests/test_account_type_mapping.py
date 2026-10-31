import pytest

from app.services.account_type_mapping import (
    map_erp_type_to_fineract,
    map_fineract_type_to_erp,
    ERP_TO_FINERACT_TYPE,
)


def test_all_erp_types_map():
    for erp, expected in ERP_TO_FINERACT_TYPE.items():
        assert map_erp_type_to_fineract(erp) == expected
        assert map_erp_type_to_fineract(erp.lower()) == expected


def test_unknown_erp_type_raises():
    with pytest.raises(ValueError, match="Unknown ERP account type"):
        map_erp_type_to_fineract("UNKNOWN")


def test_round_trip():
    for erp, ft in ERP_TO_FINERACT_TYPE.items():
        assert map_fineract_type_to_erp(ft) == erp
import pytest
from model_bakery import baker

from tests.test_db.models import UpdatableTestModel


class TestUpdatableModel:
    @pytest.mark.parametrize(
        ["fields", "raises"],
        [
            ({"field1": "another_value", "field2": "20"}, False),
            ({"field1": "new_value"}, False),
            ({}, False),
            ({"pk": "10", "field1": "new_value"}, True),
            ({"non_existent_field": "some_value"}, True),
            ({"bypass_orm": True, "field1": "another_value", "field2": "20"}, False),
            ({"bypass_orm": True, "field1": "new_value"}, False),
            (
                {
                    "bypass_orm": True,
                },
                False,
            ),
            ({"bypass_orm": True, "pk": "10", "field1": "new_value"}, True),
            ({"bypass_orm": True, "non_existent_field": "some_value"}, True),
        ],
    )
    def test_updatable_mixin_update(
        self,
        db,
        fields: dict,
        raises: bool,
    ):
        instance = baker.make(UpdatableTestModel, field1="old_value", field2="10")
        if raises:
            # Test updating with an invalid field name (raises AttributeError)
            with pytest.raises(Exception):
                instance.update(**fields)
            return
        instance.update(**fields)
        instance.refresh_from_db()
        for key, val in fields.items():
            if hasattr(instance, key):
                assert getattr(instance, key) == val
from unittest.mock import MagicMock, call, patch

import pytest
from django.db import DEFAULT_DB_ALIAS
from django.db.models import signals
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

    def test_bypass_orm(self, db):
        old_value = "old_value"
        inst = baker.make(UpdatableTestModel, field1=old_value, field2="10")
        new_value = "new_value"
        with patch.object(inst, "save") as save:
            # should use orm filter & update rather than save.
            inst.update(field1=new_value, bypass_orm=True)
            save.assert_not_called()
            assert inst.field1 == old_value
            inst.refresh_from_db()
            assert inst.field1 == new_value

    def test_update_without_commit(self, db):
        # Test branch: if commit is False, update in-memory but do not persist via save()
        old_value = "old_value"
        new_value = "new_value"
        inst = baker.make(UpdatableTestModel, field1=old_value, field2="10")
        with patch.object(inst, "save") as mock_save:
            inst.update(field1=new_value, commit=False)
            mock_save.assert_not_called()
        # In-memory value is updated immediately...
        assert inst.field1 == new_value
        # ...but the database still holds the old value
        inst.refresh_from_db()
        assert inst.field1 == old_value

    def test_save_without_commit_triggers_pre_save_signal(self, db):
        # Test that calling save(commit=False, ...) triggers the pre_save signal.
        inst = baker.make(UpdatableTestModel, field1="old_value", field2="10")
        with patch.object(signals.pre_save, "send") as mock_pre_save:
            inst.save(commit=False, update_fields=["field1"])
            mock_pre_save.assert_called_once()
            args, kwargs = mock_pre_save.call_args
            assert kwargs["sender"] == type(inst)
            assert kwargs["instance"] == inst
            assert kwargs["raw"] is False
            assert kwargs["using"] == DEFAULT_DB_ALIAS
            assert kwargs["update_fields"] == ["field1"]

    def test_update_with_databases(self, db):
        # Test branch: if databases is provided and bypass_orm is True,
        # the update should be done via queryset update for each db.
        old_value = "old_value"
        new_value = "new_value"
        inst = baker.make(UpdatableTestModel, field1=old_value, field2="10")
        databases = ["db1", "db2"]

        with patch.object(inst.__class__.objects, "using") as using_patch:
            # Configure the chain: using(...).filter(...).update(...) should be callable.
            fake_filter = MagicMock()
            fake_filter.update = MagicMock()
            using_patch.return_value.filter.return_value = fake_filter

            inst.update(field1=new_value, bypass_orm=True, databases=databases)

            # Ensure 'using' is called with each database alias.
            expected_calls = [call("db1"), call("db2")]
            assert using_patch.call_args_list == expected_calls

            # Ensure update is called once per database with correct arguments.
            assert fake_filter.update.call_count == len(databases)
            for call_args in fake_filter.update.call_args_list:
                # The kwargs passed should update field1 to new_value.
                kwargs = call_args[1]
                assert kwargs == {"field1": new_value}

        # In bypass_orm mode, in-memory instance remains unchanged.
        assert inst.field1 == old_value

    def test_update_databases_without_bypass(self, db):
        # Test branch: if databases is provided but bypass_orm is False,
        # a RuntimeError should be raised.
        inst = baker.make(UpdatableTestModel, field1="old_value", field2="10")
        with pytest.raises(
            RuntimeError,
            match="Please set bypass_orm to True when specifying databases",
        ):
            inst.update(field1="new_value", databases=["db1"])

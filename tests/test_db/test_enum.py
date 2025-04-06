import dataclasses

import pytest
from model_bakery import baker

from django_infra.db import enum
from tests.test_db.models import Order, OrderStatus


@dataclasses.dataclass
class SpecificCode(enum.CodeChoice):
    """A subclass of enum.CodeChoice for testing subclass validation."""

    extra_field: int = 0


class SubclassStatus(enum.DBSafeChoices):
    """Valid example using a subclass of enum.CodeChoice."""

    ACTIVE = SpecificCode(code="ACT", extra_field=1)
    INACTIVE = SpecificCode(code="INA", extra_field=2)


class AltValidationStatus(enum.DBSafeChoices):
    """Example demonstrating overriding get_type_validation_cls."""

    ITEM_A = SpecificCode(code="A", extra_field=10)
    ITEM_B = SpecificCode(code="B", extra_field=20)

    @classmethod
    def get_type_validation_cls(cls) -> type:
        return SpecificCode


def test_valid_enum_creation():
    """Verify that a valid enum.DBSafeChoices enum can be created."""
    assert OrderStatus.PENDING_STATUS is not None
    assert OrderStatus.PROCESSING.name == "PROCESSING"
    assert OrderStatus.COMPLETED.value == enum.CodeChoice(code="CP")
    assert OrderStatus.CANCELLED.label == "Cancelled"


def test_valid_enum_with_subclass_member():
    """Verify enum creation works with members whose type is a subclass."""
    assert SubclassStatus.ACTIVE is not None
    assert SubclassStatus.ACTIVE.value == SpecificCode(code="ACT", extra_field=1)
    assert SubclassStatus.INACTIVE.label == "Inactive"
    assert SubclassStatus.INACTIVE.value.extra_field == 2


def test_invalid_enum_member_type_direct_string():
    """Verify TypeError is raised for members not inheriting from enum.CodeChoice."""
    with pytest.raises(TypeError) as excinfo:

        class InvalidStatusStr(enum.DBSafeChoices):
            FAIL = "FAIL_CODE", "Fail Label"  # Incorrect type

    assert "Enum member FAIL in InvalidStatusStr must inherit from" in str(
        excinfo.value
    )
    assert "InvalidStatusStr" in str(excinfo.value)
    assert "got type <class 'tuple'>" in str(excinfo.value)  # The incorrect type


def test_invalid_enum_member_type_other_dataclass():
    """Verify TypeError for members using an unrelated dataclass."""

    @dataclasses.dataclass
    class OtherData:
        id: int

    with pytest.raises(TypeError) as excinfo:

        class InvalidStatusOther(enum.DBSafeChoices):
            BAD = OtherData(id=1)

    assert "Enum member BAD in InvalidStatusOther must inherit from" in str(
        excinfo.value
    )


def test_invalid_enum_with_custom_validation_type():
    """Verify TypeError when using a custom validation type and providing wrong
    member type."""
    with pytest.raises(TypeError) as excinfo:

        class InvalidAltStatus(enum.DBSafeChoices):
            # This one is ok
            ITEM_A = SpecificCode(code="A", extra_field=10)
            # This one is not SpecificCode, should fail validation
            ITEM_C = enum.CodeChoice(code="C")

            @classmethod
            def get_type_validation_cls(cls) -> type:
                return SpecificCode

    assert "Enum member ITEM_C in InvalidAltStatus must inherit from" in str(
        excinfo.value
    )


def test_duplicate_code_raises_err():
    """Verify TypeError when using a custom validation type and providing wrong
    member type."""
    with pytest.raises(ValueError) as excinfo:

        class InvalidAltStatus(enum.DBSafeChoices):
            # This one is ok
            ITEM_A = SpecificCode(code="A", extra_field=10)
            # This one is not SpecificCode, should fail validation
            ITEM_C = SpecificCode(code="A", extra_field=10)

            @classmethod
            def get_type_validation_cls(cls) -> type:
                return SpecificCode

    assert "duplicate values found" in str(excinfo.value)


def test_db_choices_property():
    """Verify the db_choices property returns the correct (code, label) format."""
    expected_choices = [
        ("PN", "Pending Status"),
        ("PR", "Processing"),
        ("CP", "Completed"),
        ("CN", "Cancelled"),
    ]
    assert OrderStatus.db_choices == expected_choices


def test_db_choices_property_with_subclass():
    """Verify db_choices works correctly with subclassed enum.CodeChoice members."""
    expected_choices = [
        ("ACT", "Active"),
        ("INA", "Inactive"),
    ]
    assert SubclassStatus.db_choices == expected_choices


def test_equality_comparison():
    """Verify the overridden __eq__ method works as expected."""
    # Member vs Member
    assert OrderStatus.PENDING_STATUS == OrderStatus.PENDING_STATUS
    assert not (OrderStatus.PENDING_STATUS == OrderStatus.PROCESSING)

    # Member vs Code String
    assert OrderStatus.PROCESSING == "PR"
    assert not (OrderStatus.COMPLETED == "PN")
    assert "CP" == OrderStatus.COMPLETED  # Reverse comparison

    # Member vs enum.CodeChoice Instance
    assert OrderStatus.COMPLETED == enum.CodeChoice(code="CP")
    assert not (OrderStatus.CANCELLED == enum.CodeChoice(code="XX"))
    assert enum.CodeChoice(code="CN") == OrderStatus.CANCELLED  # Reverse comparison

    # Member vs Subclass Instance (compatible if code matches)
    assert SubclassStatus.ACTIVE == SpecificCode(
        code="ACT", extra_field=999
    )  # Extra field ignored
    assert not (SubclassStatus.INACTIVE == SpecificCode(code="ACT"))
    assert SpecificCode(code="INA") == SubclassStatus.INACTIVE  # Reverse comparison

    # Member vs Unrelated Type
    assert not (OrderStatus.PENDING_STATUS == 123)
    assert OrderStatus.PENDING_STATUS is not None
    assert not (OrderStatus.PENDING_STATUS == object())

    # Member vs object with different attribute name but same value
    @dataclasses.dataclass
    class SimilarObject:
        code: str

    assert OrderStatus.PENDING_STATUS == SimilarObject(code="PN")
    assert not (OrderStatus.PENDING_STATUS == SimilarObject(code="XX"))

    # Member vs object without code attribute
    @dataclasses.dataclass
    class DifferentObject:
        value: str

    assert not (OrderStatus.PENDING_STATUS == DifferentObject(value="PN"))


def test_standard_choices_properties():
    """Verify standard Django Choices properties still work."""
    assert OrderStatus.labels == [
        "Pending Status",
        "Processing",
        "Completed",
        "Cancelled",
    ]
    # Note: OrderStatus.values are the enum.CodeChoice instances themselves
    assert OrderStatus.values == [
        enum.CodeChoice(code="PN"),
        enum.CodeChoice(code="PR"),
        enum.CodeChoice(code="CP"),
        enum.CodeChoice(code="CN"),
    ]
    # OrderStatus.choices are (member, label) tuples
    assert OrderStatus.choices == [
        (OrderStatus.PENDING_STATUS, "Pending Status"),
        (OrderStatus.PROCESSING, "Processing"),
        (OrderStatus.COMPLETED, "Completed"),
        (OrderStatus.CANCELLED, "Cancelled"),
    ]


def test_hashability():
    """Verify enum members can be used in sets and dict keys."""
    status_set = {
        OrderStatus.PENDING_STATUS,
        OrderStatus.PROCESSING,
        OrderStatus.PENDING_STATUS,
    }
    assert len(status_set) == 2
    assert OrderStatus.PENDING_STATUS in status_set
    assert OrderStatus.COMPLETED not in status_set

    status_dict = {
        OrderStatus.COMPLETED: "Done",
        OrderStatus.CANCELLED: "Stopped",
    }
    assert status_dict[OrderStatus.COMPLETED] == "Done"
    assert OrderStatus.CANCELLED in status_dict


# Test edge case where enum.CodeChoice might have mutable defaults (it doesn't here,
# but good practice)
def test_codechoice_immutability_assumption():
    """Check that separate instances with same code are equal but distinct objects"""
    c1 = enum.CodeChoice(code="TEST")
    c2 = enum.CodeChoice(code="TEST")
    assert c1 == c2
    assert id(c1) != id(c2)


def test_load_from_db(db):
    order = baker.make(Order, status=str(OrderStatus.PROCESSING))
    order.refresh_from_db()
    assert order.status == OrderStatus.PROCESSING
    assert order.status == OrderStatus.PROCESSING.value.code
    assert OrderStatus.PROCESSING == OrderStatus.from_code(order.status)
    assert isinstance(OrderStatus.from_code(order.status), OrderStatus)

"""
Django Choices Enhancement for Database Safety and Type Validation

This module provides a custom Django Choices implementation (`DBSafeChoices`)
that enhances the standard `django.db.models.enums.Choices` by:

1.  **Enforcing Member Type:** Ensures that all members defined within a
    `DBSafeChoices` subclass are instances of a specific base class
    (by default, `CodeChoice`). This promotes consistency and allows
    attaching specific data (like a 'code') to each choice member.
2.  **Providing Database-Friendly Choices:** Includes a `db_choices` property
    that automatically generates a list of `(code, label)` tuples suitable
    for use in Django model field `choices` attributes. This decouples the
    database representation (the 'code') from the Python enum member instance.
3.  **Flexible Equality Comparison:** Overrides the `__eq__` method to allow
    comparing enum members directly with their code string, their corresponding
    `CodeChoice` instance, or another enum member.

Core Components:
    - CodeChoice: A simple dataclass holding a 'code' string. Enum members
                  in `DBSafeChoices` must inherit from this (or the class
                  specified by `get_type_validation_cls`).
    - CodeChoices (Metaclass): The metaclass responsible for validating member
                               types during class creation and providing the
                               `db_choices` property logic.
    - DBSafeChoices: The base class users should inherit from to create their
                     custom, validated choices enums.

Use Case:
    Ideal for scenarios where you want to store a specific, often shorter or
    more stable, code (e.g., 'PEND', 'COMP') in the database field, while
    working with more descriptive enum members (`OrderStatus.PENDING`) and
    user-friendly labels ('Pending Status') in your Python code and Django admin.
    The type validation adds robustness by preventing accidental definition of
    members with incorrect structures.
"""

import dataclasses

from django.db.models.enums import Choices, ChoicesType


@dataclasses.dataclass
class CodeChoice:
    """Data structure required as a base for members of DBSafeChoices.

    Attributes:
        code (str): The string representation to be stored in the database
                    or used for comparisons.
    """

    code: str


class CodeChoices(ChoicesType):
    """Metaclass for DBSafeChoices or similar.

    Ensures that all enum members are instances of a specific type
    (retrieved via `get_type_validation_cls`) and provides the `db_choices`
    property.
    """

    def __new__(metacls, clsname, bases, clsdict, **kwargs):
        cls = super().__new__(metacls, clsname, bases, clsdict, **kwargs)
        type_validation_cls = cls.get_type_validation_cls()
        # Validate that each enum member inherits from CodeChoice
        for member in cls.__members__.keys():
            member_type = type(clsdict.get(member))
            if not issubclass(member_type, type_validation_cls):
                raise TypeError(
                    f"Enum member {member} in {clsname} must inherit from "
                    f"{type_validation_cls}, got type {member_type}"
                )
        return cls

    @property
    def db_choices(cls) -> list[tuple[str, str]]:
        """Generates choices suitable for Django model fields.
        format: (<code>, <label>)
        example: [('SC','SCHEDULED'),('PR','PROCESSING')]
        """
        # Return a list of tuples (code, label)
        return [(v.code, label) for v, label in cls.choices]


class DBSafeChoices(Choices, metaclass=CodeChoices):
    """A base class to implement DB safe choices with code validation."""

    @classmethod
    def get_type_validation_cls(cls):
        return CodeChoice

    def __eq__(self, other):
        if isinstance(other, str):
            return self.value.code == other
        elif other_code := getattr(other, "code", None):
            return self.value.code == other_code
        return super().__eq__(other)

    def __hash__(self):
        return hash(self.value.code)

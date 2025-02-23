import abc
import itertools
from typing import Any, Callable, Set

import pytest
from rest_framework.serializers import Serializer


def validate_serializer_fields(
    serializer_class,
    read_only_fields: Set[str] = None,
    normal_fields: Set[str] = None,
    write_only_fields: Set[str] = None,
):
    """Checks if the serializer fields match the expected read-only and normal fields"""
    read_only_fields = read_only_fields or set()
    write_only_fields = write_only_fields or set()
    normal_fields = normal_fields or set()
    serializer = serializer_class()
    actual_read_only_fields = {
        field_name for field_name, field in serializer.fields.items() if field.read_only
    }
    actual_write_only_fields = {
        field_name
        for field_name, field in itertools.chain(
            getattr(serializer, "fields", dict()).items(),
            getattr(serializer, "read_only_fields", dict()).items(),
        )
        if field.write_only
    }
    actual_normal_fields = (
        set(serializer.fields.keys())
        - actual_read_only_fields
        - actual_write_only_fields
    )

    read_only_diff = actual_read_only_fields.symmetric_difference(read_only_fields)
    write_only_diff = actual_write_only_fields.symmetric_difference(write_only_fields)
    normal_diff = actual_normal_fields.symmetric_difference(normal_fields)

    error_message = []
    if read_only_diff:

        error_message.append("--------------[ READ ONLY FIELDS ]--------------- ")
        error_message.append(f"- {read_only_fields - actual_read_only_fields} ")
        error_message.append(f"+ {actual_read_only_fields-read_only_fields} ")
    if normal_diff:
        error_message.append("--------------[ NORMAL FIELDS ]--------------- ")

        error_message.append(f"- {normal_fields - actual_normal_fields} ")
        error_message.append(f"+ {actual_normal_fields - normal_fields} ")
    if write_only_diff:
        error_message.append("--------------[ WRITE ONLY FIELDS ]--------------- ")
        error_message.append(f"- {write_only_fields - actual_write_only_fields} ")
        error_message.append(f"+ {actual_write_only_fields - write_only_fields} ")
    if error_message:
        print("")
        message = "\n".join(error_message)
        print(message)
        pytest.fail(message)


class SerializerTest:

    @property
    @abc.abstractmethod
    def serializer(self) -> Serializer:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def factory(self) -> Callable:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def write_only_fields(self) -> Set[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def read_only_fields(self) -> Set[str]:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def normal_fields(self) -> Set[str]:
        raise NotImplementedError

    @property
    def serializer_context(self) -> dict:
        return {}

    @property
    def model_factory(self):
        """Avoid passing `self` to factory."""
        return self.__class__.factory

    def test_fields_correct(self):
        """Validate serializer keys match expected keys
        The purpose of this test is to fail when serializer's keys are modified
        """
        validate_serializer_fields(
            serializer_class=self.serializer,
            read_only_fields=self.read_only_fields,
            normal_fields=self.normal_fields,
            write_only_fields=self.write_only_fields,
        )

    def get_queryset(self, *, model_cls):
        return model_cls.objects.all()

    def test_instantiation(self, db):
        """Validate serializer instantiation, serialization & keys in data
        The purpose of this test is to fail if serialization fails (such as method fields)
        or if the keys in the serialized data miss-match what is expected.
        """
        inst = self.model_factory()
        inst = self.get_queryset(model_cls=type(inst)).filter(pk=inst.pk).first()
        self.serializer(instance=inst, context=self.serializer_context).data


class ViewTest:
    """
    Base class for testing views

    """

    @property
    @abc.abstractmethod
    def view_parents(self) -> tuple:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def view(self) -> Any:
        raise NotImplementedError

    @property
    @abc.abstractmethod
    def permission_classes(self) -> Any:
        raise NotImplementedError

    def test_view_signature(self, db):
        """
        Validate that the view has the expected signature
        """

        assert issubclass(self.view, self.view_parents)

    def test_permissions_match(self):
        assert getattr(self.view, "permission_classes") == self.permission_classes


class ModelViewTest(ViewTest, SerializerTest, abc.ABC):
    permission_classes = None

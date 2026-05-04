import copy

from rest_framework import serializers
from rest_framework.serializers import SerializerMetaclass


def normalized_field_names(fields) -> set[str]:
    if not fields:
        return set()
    if isinstance(fields, dict):
        return set(fields.keys())
    return set(fields)


class RequestDrivenFieldsSerializerMeta(SerializerMetaclass):
    """Keep opt-in nested fields valid for DRF without serving them by default."""

    def __new__(cls, name, bases, attrs):
        meta = attrs.get("Meta")
        if meta is not None:
            nested_fields = normalized_field_names(
                getattr(meta, "nested_fields", set())
            )
            fields = getattr(meta, "fields", [])
            if nested_fields and fields != "__all__":
                meta.fields = list(dict.fromkeys([*fields, *nested_fields]))
        return super().__new__(cls, name, bases, attrs)


class RequestDrivenFieldsSerializer(
    serializers.ModelSerializer,
    metaclass=RequestDrivenFieldsSerializerMeta,
):
    """ModelSerializer with opt-in computed and nested response fields.

    Views should provide requested_computed_fields and requested_nested_fields in
    serializer context. HandledFieldsMixin does this and applies matching
    @handle_fields queryset handlers before serialization.
    """

    computed_fields_context_key = "requested_computed_fields"
    nested_fields_context_key = "requested_nested_fields"

    @classmethod
    def get_computed_fields_definition(cls) -> dict:
        return getattr(cls.Meta, "computed_fields", {})

    @classmethod
    def get_nested_fields_definition(cls) -> set[str]:
        return normalized_field_names(getattr(cls.Meta, "nested_fields", set()))

    def get_fields(self):
        fields = super().get_fields()
        if not self.is_top_level_serializer():
            return self.exclude_opt_in_fields(fields, set(), set())

        requested_computed = self.get_requested_computed_fields()
        requested_nested = self.get_requested_nested_fields()
        self.validate_requested_computed_fields(requested_computed)
        self.validate_requested_nested_fields(requested_nested)
        fields = self.add_requested_computed_fields(fields, requested_computed)
        return self.exclude_opt_in_fields(fields, requested_computed, requested_nested)

    def is_top_level_serializer(self) -> bool:
        parent = getattr(self, "parent", None)
        return parent is None or (
            isinstance(parent, serializers.ListSerializer)
            and getattr(parent, "parent", None) is None
        )

    def get_requested_computed_fields(self) -> set[str]:
        return set(self.context.get(self.computed_fields_context_key, set()))

    def get_requested_nested_fields(self) -> set[str]:
        return set(self.context.get(self.nested_fields_context_key, set()))

    def validate_requested_computed_fields(self, requested_fields: set[str]) -> None:
        available_fields = set(self.get_computed_fields_definition().keys())
        unknown_fields = requested_fields - available_fields
        if unknown_fields:
            raise serializers.ValidationError(
                "Unknown computed field(s): "
                f"{', '.join(sorted(unknown_fields))}. "
                f"Available: {', '.join(sorted(available_fields)) or 'none'}"
            )

    def validate_requested_nested_fields(self, requested_fields: set[str]) -> None:
        available_fields = self.get_nested_fields_definition()
        unknown_fields = requested_fields - available_fields
        if unknown_fields:
            raise serializers.ValidationError(
                "Unknown nested field(s): "
                f"{', '.join(sorted(unknown_fields))}. "
                f"Available: {', '.join(sorted(available_fields)) or 'none'}"
            )

    def add_requested_computed_fields(self, fields, requested_fields: set[str]):
        for (
            field_name,
            field_definition,
        ) in self.get_computed_fields_definition().items():
            if field_name in requested_fields:
                fields[field_name] = self.build_computed_field(
                    field_name, field_definition
                )
        return fields

    def build_computed_field(self, field_name: str, field_definition):
        if isinstance(field_definition, str):
            if field_definition == field_name:
                return serializers.ReadOnlyField()
            return serializers.ReadOnlyField(source=field_definition)

        field = copy.deepcopy(field_definition)
        field.read_only = True
        return field

    def exclude_opt_in_fields(
        self,
        fields,
        requested_computed: set[str],
        requested_nested: set[str],
    ):
        payload_fields = self.get_payload_fields_for_write()
        opt_in_fields = (
            set(self.get_computed_fields_definition().keys())
            | self.get_nested_fields_definition()
        )
        included_fields = requested_computed | requested_nested | payload_fields
        for field_name in opt_in_fields - included_fields:
            fields.pop(field_name, None)
        return fields

    def get_payload_fields_for_write(self) -> set[str]:
        request = self.context.get("request")
        if request is None or request.method not in ("POST", "PUT", "PATCH"):
            return set()
        try:
            return set(self.initial_data.keys())
        except AttributeError:
            return set()

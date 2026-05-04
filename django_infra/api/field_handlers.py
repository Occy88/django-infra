from __future__ import annotations

import functools
from typing import Callable

from djangorestframework_camel_case.util import camel_to_underscore
from rest_framework import exceptions


def handle_fields(*field_names: str):
    """Mark a view method as handling computed or nested serializer fields.

    Use with HandledFieldsMixin:

        @handle_fields("latest_status", "latest_status_code")
        def annotate_latest_status(self, queryset):
            return queryset.with_latest_status()
    """

    def decorator(method):
        @functools.wraps(method)
        def wrapper(*args, **kwargs):
            return method(*args, **kwargs)

        wrapper.handled_fields = frozenset(field_names)
        return wrapper

    return decorator


class HandledFieldsMixin:
    """Opt-in queryset handling for requested computed and nested fields."""

    computed_fields_param = "computed_fields"
    nested_fields_param = "nested_fields"

    @property
    def requested_computed_fields(self) -> set[str]:
        return self.parse_requested_field_set(self.computed_fields_param)

    @property
    def requested_nested_fields(self) -> set[str]:
        return self.parse_requested_field_set(self.nested_fields_param)

    def parse_requested_field_set(self, param_name: str) -> set[str]:
        values = self.request.query_params.getlist(param_name)
        if not values:
            value = self.request.query_params.get(param_name, "")
            values = [value] if value else []
        if not values:
            return set()

        items = []
        for value in values:
            if not value:
                continue
            value = value.strip("()")
            items.extend([item.strip() for item in value.split(",") if item.strip()])
        return {camel_to_underscore(item) for item in items}

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["requested_computed_fields"] = self.requested_computed_fields
        context["requested_nested_fields"] = self.requested_nested_fields
        return context

    def optimize_queryset(self, queryset):
        queryset = super().optimize_queryset(queryset)
        queryset = self.apply_requested_computed_field_handlers(queryset)
        queryset = self.apply_requested_nested_field_handlers(queryset)
        return queryset

    def get_field_handlers(self) -> dict[str, Callable]:
        handlers = {}
        for name in dir(self):
            method = getattr(self.__class__, name, None)
            if method is None:
                continue
            handled_fields = getattr(method, "handled_fields", None)
            if handled_fields:
                for field_name in handled_fields:
                    handlers[field_name] = getattr(self, name)
        return handlers

    def get_serializer_computed_field_names(self) -> set[str]:
        serializer_class = getattr(self, "serializer_class", None)
        if serializer_class is None:
            return set()
        meta = getattr(serializer_class, "Meta", None)
        if meta is None:
            return set()
        computed_fields = getattr(meta, "computed_fields", {})
        return set(computed_fields.keys())

    def apply_requested_computed_field_handlers(self, queryset):
        if not self.requested_computed_fields:
            return queryset

        valid_fields = self.get_serializer_computed_field_names()
        invalid_fields = self.requested_computed_fields - valid_fields
        if invalid_fields:
            raise exceptions.ParseError(
                f"Unknown computed field(s): {', '.join(sorted(invalid_fields))}. "
                f"Available: {', '.join(sorted(valid_fields)) or 'none'}"
            )

        handlers = self.get_field_handlers()
        missing_handlers = [
            field_name
            for field_name in self.requested_computed_fields
            if field_name not in handlers
        ]
        if missing_handlers:
            raise RuntimeError(
                "No handler for computed field(s): "
                f"{', '.join(sorted(missing_handlers))}."
            )

        for handler in {
            handlers[field_name] for field_name in self.requested_computed_fields
        }:
            queryset = handler(queryset)
        return queryset

    def apply_requested_nested_field_handlers(self, queryset):
        if not self.requested_nested_fields:
            return queryset

        handlers = self.get_field_handlers()
        for handler in {
            handlers[field_name]
            for field_name in self.requested_nested_fields
            if field_name in handlers
        }:
            queryset = handler(queryset)
        return queryset

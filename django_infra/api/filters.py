from __future__ import annotations

import re
import typing
from typing import List, Type, Union

from django.db import models as dm
from django_filters import rest_framework as filters


def field_supports_partial_matching(model, field_name):
    """True if field (nested or not) supports partial matching.

    Fields supporting partial matching:
    - TextField
    - CharField

    Examples
    ---------
    >>> field_supports_partial_matching(PatientJourney,'patient__user__first_name')
    >>> True
    >>> field_supports_partial_matching(PatientJourney,'patient__user_id')
    >>> False
    >>> field_supports_partial_matching(PatientJourney,'id')
    >>> False
    """
    parts = field_name.split("__")
    field = None
    for part in parts:
        if field is None:
            # Start from the base model
            field = model._meta.get_field(part)
        else:
            # Traverse related fields
            if hasattr(field, "remote_field") and field.remote_field:
                model = field.remote_field.model
                field = model._meta.get_field(part)
            else:
                # Field cannot be traversed further
                return False
    return isinstance(field, (dm.CharField, dm.TextField))


class FilterField:
    internal: str = None
    external: str = None
    exclude: bool = False

    def __init__(
        self, *, internal: dm.Field | str, external: str = None, exclude=False
    ):
        """
        internal: variable used in orm e.g.: user__first_name
        external: variable used by client: patient_name
        """
        self.exclude = exclude
        if self.internal is None and internal is None:
            raise RuntimeError("Internal not set.")
        if self.internal is None:
            internal = self.normalise_internal(internal)
            self.internal = internal
        if self.external is None:
            self.external = external or internal

    @staticmethod
    def normalise_internal(field: dm.Field | str) -> str:
        if hasattr(field, "field"):
            field = field.field.attname
        return field

    @property
    def field(self) -> tuple[str, str]:
        return self.internal, self.external

    def retrieve_value_from_instance(self, instance):
        """Retrieve internal field value from instance.

        If the field does have the internal attribute we split by `__`
        and attempt a nested retrieval

        Raises: AttributeError
        """
        if hasattr(instance, self.internal):
            return getattr(instance, self.internal)
        field_tree = self.internal.split("__")
        if len(field_tree) == 1:
            return getattr(instance, self.internal)  # will raise
        # try to perform a nested retrieval
        # e.g. pj.team.lead.user.first_name
        # given "team__lead__user__first_name"
        value = instance
        while field_tree and value is not None:
            node = field_tree.pop(0)
            try:
                value = getattr(value, node)
            except AttributeError as e:
                raise AttributeError(
                    f"Failed to get {self.internal} from {instance}: {e}"
                )
        return value


class TypedFilterField(FilterField):
    type_: Type[bool | int | str | float]

    def __init__(
        self,
        *,
        type_: Type[bool | int | str | float],
        internal: Union[dm.Field, str],
        external: str = None,
        exclude: bool = False,
    ):
        self.type_ = type_
        super().__init__(internal=internal, external=external, exclude=exclude)


class MultiInternalFilterField(FilterField):
    internal: List[str]

    def __init__(
        self,
        *,
        internal: List[Union[dm.Field, str]],
        external: str,
        exclude: bool = False,
    ):
        self.internal = [self.normalise_internal(f) for f in internal]
        self.external = external
        super().__init__(internal="", exclude=exclude)


FIELD_TYPES = FilterField | MultiInternalFilterField | TypedFilterField


class Filter:
    fields = List[FIELD_TYPES]
    _internal_map: dict[str, FilterField]
    _external_map: dict[str, FilterField]
    name: str

    def __init__(
        self,
        *,
        fields: List[FilterField | MultiInternalFilterField | TypedFilterField],
        name: str,
    ):
        self.fields = fields
        self.name = name
        self._validate()
        self.fields = fields

    def _validate(self):
        self._external_map = dict()
        self._internal_map = dict()
        if self.fields is None:
            raise ValueError("fields should not be None")
        for f in self.fields:
            if not isinstance(f, FilterField):
                raise RuntimeError(f"{f} should be of type {FilterField}")
            self._external_map[f.external] = f
            if not isinstance(f, MultiInternalFilterField):
                self._internal_map[f.internal] = f

    def add_field(self, field: FIELD_TYPES) -> Filter:
        self.fields.append(field)
        self._validate()
        return self

    @property
    def fields_names(self):
        return [f.field for f in self.fields]


class CustomFilter(Filter):
    fields: List[TypedFilterField]

    def __init__(self, *, fields, custom_filter: typing.Callable):
        """Partial matching of string into one or more internal fields
        Examples
        ---------
        >>> CustomFilter(
        >>>     custom_filter:typing.Callable=<my_filter>
        >>> )
        >>> client.get(url="/?search_by_name=<name>")
        >>> client.get(url="/?search_by_slug=<slug>")
        Parameters
        ----------
        fields:List[MultiInternalFilterField]
        """
        super().__init__(fields=fields, name="icontains_filter")
        self.custom_filter = custom_filter

    def get_filter(self, qs, external_field: str, payload_value: typing.Any):
        """Returns custom filter implementation with external map injected into kwargs.
        !!! Attention, there is some gimmicky stuff going on here !!!
        Django filters requires you to add a `self` attr when defining a custom filter
        So essentially here `self` is both acting as the instance of this class
        AND a reference to the django filter.

        What is important is that we clean this data up when handing it off to
        the custom filter function specified, (we don't pass any `self` instance
        to avoid this confusion.
        """
        return self.custom_filter(
            qs=qs, value=payload_value, external_map=self._external_map
        )

    def to_meta(self):
        # this is what is used in the query see filter fn.
        d = dict()
        for f in self.fields:
            d.update(
                {
                    f"{f.external}": filters.Filter(
                        field_name=f.external,
                        method=f"filter_{f.external}",
                    ),
                    f"filter_{f.external}": self.get_filter,
                }
            )
        return d


class _NullLastOrderingFilter(filters.OrderingFilter):
    def get_ordering_value(self, param):
        descending = param.startswith("-")
        param = param[1:] if descending else param
        field_name = self.param_map.get(param, param)
        if descending:
            return dm.F(field_name).desc(nulls_last=True)
        else:
            return dm.F(field_name).asc(nulls_last=True)


class OrderingFilter(Filter):
    def __init__(
        self, *, fields: List[FilterField], name: str, base_ordering_filter=None
    ):
        """Orders by one or more client defined string mapped to internal fields
        Examples
        ---------
        >>> OrderingFilter(
        >>>     name='ordering',
        >>>     fields=[
        >>>         FilterField(
        >>>             internal='team__lead_id',
        >>>             external='order_by_lead_id',
        >>>         ),
        >>>         FilterField(
        >>>             internal='slug',
        >>>             external='order_by_slug',
        >>>         ),
        >>>     ]
        >>> )
        >>> client.get(url="/?ordering=-order_by_slug,order_by_lead_id")

        Parameters
        ----------
        fields:List[FilterField]
        """
        self.base_ordering_filter = base_ordering_filter or _NullLastOrderingFilter
        super().__init__(fields=fields, name=name)

    def to_meta(self):
        return {
            self.name: self.base_ordering_filter(
                field_name=self.name, fields=self.fields_names
            )
        }


class IContainsFilter(Filter):
    fields: List[MultiInternalFilterField]

    @staticmethod
    def format_regex(value: str) -> str:
        """
        Creates an ORM readable regex string, escaping all initial
        regex characters except * which is used as wildcard
        """
        value = re.escape(value)
        value = f"^{value}$"
        value = value.replace("\\*", ".*")
        return value

    def __init__(self, *, fields: List[MultiInternalFilterField], allow_wildcard=False):
        """Partial matching of string into one or more internal fields
        Examples
        ---------
        >>> IContainsFilter(
        >>>     fields=[
        >>>         MultiInternalFilterField(
        >>>             internal=['team__lead__user__first_name',
        'patient__user__first_name'],
        >>>             external='search_by_name')
        >>>         ),
        >>>         MultiInternalFilterField(
        >>>             internal=['journey__slug','slug'],
        >>>             external='search_by_slug')
        >>>         ),
        >>>     ]
        >>> )
        >>> client.get(url="/?search_by_name=<name>")
        >>> client.get(url="/?search_by_slug=<slug>")

        Parameters
        ----------
        fields:List[MultiInternalFilterField]
        """
        super().__init__(fields=fields, name="icontains_filter")
        self.allow_wildcard = allow_wildcard

    def to_meta(self):
        # this is what is used in the query see filter fn.
        d = dict()
        external_map = self._external_map
        for f in self.fields:

            def filter(self_, queryset, name, value):
                q_objects = dm.Q()
                for internal in external_map.get(name).internal:
                    fn = "icontains"
                    if "*" in value and self.allow_wildcard:
                        fn = "iregex"
                        value = self.format_regex(value)
                    if field_supports_partial_matching(queryset.model, internal):
                        q_objects |= dm.Q(**{f"{internal}__{fn}": value})
                    elif value.isnumeric():
                        # field does not support partial matching,
                        # most likely FK & val needs to be numeric.
                        q_objects |= dm.Q(**{internal: value})
                return queryset.filter(q_objects)

            d.update(
                {
                    f"{f.external}": filters.CharFilter(
                        # this is what is used in the url
                        field_name=f.external,
                        method=f"filter_{f.external}",
                    ),
                    f"filter_{f.external}": filter,
                }
            )
        return d


def format_regex(value: str) -> str:
    """
    Creates an ORM readable regex string, escaping all initial
    regex characters except * which is used as wildcard
    """
    value = re.escape(value)
    value = f"^{value}$"

    value = value.replace("\\*", ".*")

    return value


class WildcardFilter(filters.CharFilter):
    def filter(self, qs, value):
        """
        Custom char filter which accepts a string of substring parts to match against,
        optionally separated by one or more wildcards, denoted with '*'

        Args:
            qs (QuerySet): The full queryset passed from the view before filtering
            value (str): The value to filter against

        Example values:
        - exact match: foofoofoo
        - starts with match: *foo
        - ends with match: foo*
        - multiple wildcard separators: f*f*f*

        Returns:
            QuerySet
        """

        # If filter value is empty, return unfiltered
        if not value:
            return qs

        wildcard = "*"

        # No wildcard - return exact case insensitive match
        if wildcard not in value:
            return qs.filter(**{f"{self.field_name}__iexact": value})

        value = format_regex(value)

        qs = qs.filter(**{f"{self.field_name}__iregex": value})

        return qs


class ExactMatchFilter(Filter):
    fields: List[TypedFilterField]

    def __init__(self, *, fields: List[TypedFilterField]):
        """Exact matching of string into internal field
        Examples
        ---------
        >>> ExactMatchFilter(
        >>>     fields=[
        >>>         TypedFilterField(
        >>>             internal='team__lead_id',
        >>>             external='match_on_lead_id',
        >>>             type_=int,
        >>>         ),
        >>>         TypedFilterField(
        >>>             internal='slug',
        >>>             external='match_on_slug',
        >>>             type_=str,
        >>>         ),
        >>>     ]
        >>> )
        >>> client.get(url="/?match_on_lead_id=<id:int>")
        >>> client.get(url="/?match_on_slug=<slug:str>")

        Parameters
        ----------
        fields:List[TypedFilterField]
        """
        super().__init__(fields=fields, name="exact_match_filter")

    @staticmethod
    def get_filter(type_):
        return {
            str: filters.CharFilter,
            bool: filters.BooleanFilter,
            int: filters.NumberFilter,
            float: filters.NumberFilter,
            typing.Any: WildcardFilter,
        }.get(type_)

    def to_meta(self):
        # this is what is used in the query see filter fn.
        d = dict()
        external_map = self._external_map
        for f in self.fields:

            def filter(self, queryset, name, value):
                return queryset.filter(**{f"{external_map.get(name).internal}": value})

            d.update(
                {
                    f"{f.external}": self.get_filter(f.type_)(
                        # this is what is used in the url
                        field_name=f.external,
                        method=f"filter_{f.external}",
                    ),
                    f"filter_{f.external}": filter,
                }
            )
        return d


class StringInFilter(filters.BaseInFilter, filters.CharFilter):
    """
    Comma separated string filter.

    Can be used for `in` or `overlap` lookups for strings and arrays.

    """

    pass


class MatchesAnyOfFilter(Filter):

    def __init__(self, *, fields: List[FilterField]):
        """Exact matching of multiple strings into internal field
        Examples
        ---------
        >>> MatchesAnyOfFilter(
        >>>     fields=[
        >>>         FilterField(
        >>>             internal='team__lead_id',
        >>>             external='match_on_lead_id',
        >>>         ),
        >>>         FilterField(
        >>>             internal='slug',
        >>>             external='match_on_slug',
        >>>         ),
        >>>     ]
        >>> )
        >>> client.get(url="/?match_on_lead_id=<id1:int>,<id2:int>,<id3:int>")
        >>> client.get(url="/?match_on_slug=<slug1:str>,<slug2:str>,<slug3:str>")

        Parameters
        ----------
        fields:List[FilterField]
        """
        super().__init__(fields=fields, name="matches_any_of")

    def to_meta(self):
        # this is what is used in the query see filter fn.
        d = dict()
        for f in self.fields:
            d.update(
                {
                    f"{f.external}": StringInFilter(
                        field_name=f.internal,
                        help_text="Filter by comma separated contact values",
                        exclude=f.exclude,
                    ),
                }
            )
        return d

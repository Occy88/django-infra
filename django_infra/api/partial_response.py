import collections
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from django.conf import settings
from django.db.models import ForeignKey, ManyToManyField, Prefetch, QuerySet
from djangorestframework_camel_case.util import underscoreize
from drf_partial_response import constants
from drf_partial_response.views import OptimizedQuerySetBase, OptimizedQuerySetMixin
from jsonmask import parse_fields
from rest_framework import exceptions


@dataclass
class Mutation:
    _mutations: Optional[List[Callable[[QuerySet], QuerySet]]] = None

    priority: int = 0
    base_queryset: QuerySet = None

    @property
    def mutations(self) -> List[Callable[[QuerySet], QuerySet]]:
        if self._mutations is None:
            self._mutations = list()
        return self._mutations

    def add(
        self,
        mutation: Callable[[QuerySet], QuerySet],
        base_queryset: QuerySet,
        priority: int = 0,
    ):
        if priority > self.priority or self.base_queryset is None:
            self.base_queryset = base_queryset
        self.mutations.append(mutation)

    def apply_all(self) -> QuerySet:
        queryset = self.base_queryset
        for mutation in self.mutations:
            queryset = mutation(queryset)
        return queryset


class PrefetchKwargs:
    def __init__(self, lookup: str, to_attr=None):
        self.lookup = lookup
        self.to_attr = to_attr

    def __eq__(self, other):
        return hash(self) == hash(other)

    def __hash__(self):
        return hash(f"{self.lookup}_{self.to_attr}")


class OptimizedQuerySetAnnotationsMixin(
    OptimizedQuerySetMixin, metaclass=OptimizedQuerySetBase
):
    """Extends OptimizedQuerySetMixin to allow for combining annotations rather than
    prefetching at each data predicate instantiation.
    by using add_nested_queryset_mutation, all mutations will be stored and applied once
    optimization is called at the end.

    Optionally pre-fetches all relations associated with the model via
    """

    _mutations: Dict[PrefetchKwargs, Mutation] = None
    # default fields to default to None defaults to all, empty list will default to None.
    default_requested_fields_to: None | List[str] = None
    auto_prefetch_related = False

    @property
    def requested_fields(self):
        # have to do this manually instead of calling super() due
        # to cached_property breaking in drf_partial...
        # also allows us to set fields directly into _requested_fields
        if not hasattr(self, "_requested_fields"):
            fields_name = getattr(
                settings, "REST_FRAMEWORK_JSONMASK_FIELDS_NAME", constants.FIELDS_NAME
            )
            self._requested_fields = underscoreize(
                parse_fields(self.request.query_params.get(fields_name))
            )
        if (
            isinstance(self.default_requested_fields_to, list)
            and self._requested_fields is None
        ):
            self._requested_fields = {
                field: dict() for field in self.default_requested_fields_to
            }
        return self._requested_fields

    @property
    def requested_fields_set(self):
        fields = self.requested_fields or dict()
        return set(fields.keys())

    def get_serializer_context(self):
        """Patch over original get serializer context.
        avoids accessing GET & simplifies.
        """
        context = super(OptimizedQuerySetMixin, self).get_serializer_context()

        if self.requested_fields and self.excluded_fields:
            raise exceptions.ParseError(
                detail="Cannot provide both requested and excluded fields"
            )
        if self.requested_fields:
            context["requested_fields"] = self.requested_fields
        if self.excluded_fields:
            context["excluded_fields"] = self.excluded_fields
        return context

    @property
    def mutations(self) -> Dict[PrefetchKwargs, Mutation]:
        if self._mutations is None:
            self._mutations = collections.defaultdict(Mutation)
        return self._mutations

    def _clean(self):
        self._mutations = None

    def get_queryset(self):
        self._clean()
        queryset = super(OptimizedQuerySetMixin, self).get_queryset()
        queryset = self.optimize_queryset(queryset)
        if "Auto-Prefetch" in self.request.headers:
            self.prefetch_related_objects(queryset)
        queryset = self.apply_all_mutations(queryset)
        return queryset

    def add_nested_queryset_mutation(
        self,
        lookup: str,
        base_queryset: QuerySet,
        queryset_transformer_lambda: Callable[[QuerySet], QuerySet] = None,
        base_queryset_priority: int = 0,
        to_attr: str = None,
    ):
        """Only for nested lookups.
        >>> # This will fail (initial annotation will be lost)
        >>> my_queryset.prefetch_related('my_attr',queryset=my_queryset_annotated_1)
        >>> my_queryset.prefetch_related('my_attr',queryset=my_queryset_annotated_2)
        >>> # This will pass:
        >>> self.add_nested_queryset_mutation('my_attr',queryset=my_base_queryset,queryset_transformer_lambda=lambda q:q.annotated_1())
        >>> self.add_nested_queryset_mutation('my_attr',queryset=my_base_queryset,queryset_transformer_lambda=lambda q:q.annotated_2())
        Parameters
        ----------
        lookup
        base_queryset
        queryset_transformer_lambda
        base_queryset_priority
        to_attr
        Returns
        -------

        """
        if queryset_transformer_lambda is None:
            queryset_transformer_lambda = lambda q: q.all()  # noqa
        self.mutations[PrefetchKwargs(lookup=lookup, to_attr=to_attr)].add(
            queryset_transformer_lambda, base_queryset, base_queryset_priority
        )

    def prefetch_related_objects(self, queryset):
        # Retrieve the model class associated with this queryset
        model = queryset.model
        # Get all the fields of the model
        fields = [
            field
            for field in model._meta.get_fields()
            if isinstance(field, (ForeignKey, ManyToManyField))
        ]
        for field in fields:
            self.add_nested_queryset_mutation(
                field.name, field.related_model.objects.all()
            )

    def apply_all_mutations(self, queryset):
        for prefetch_kwargs, mutation in self.mutations.items():
            queryset = queryset.prefetch_related(
                Prefetch(
                    lookup=prefetch_kwargs.lookup,
                    queryset=mutation.apply_all(),
                    to_attr=prefetch_kwargs.to_attr,
                )
            )
        return queryset


class CaseInsensitiveEnumMixin:
    _set = None  # Initialize the attribute to store the set

    @classmethod
    def _initialize_set(cls):
        # This creates a set with both standard and lowercase values
        if cls._set is None:
            cls._set = {e.name for e in cls} | {e.name.lower() for e in cls}

    @classmethod
    def __contains__(cls, item):
        cls._initialize_set()  # Ensure the set is initialized
        # Perform a case-insensitive check
        return item in cls._set or item.lower() in cls._set

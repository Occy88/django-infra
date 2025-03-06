from typing import List

from django.db import models
from rest_framework import pagination, parsers, viewsets

from django_infra.api.filters import Filter
from django_infra.api.meta import FilteredPartialResponseModelViewSetMetaClass
from django_infra.api.partial_response import OptimizedQuerySetAnnotationsMixin


class PaginatedViewMixin:
    parser_classes = [
        parsers.JSONParser,
        parsers.FormParser,
        parsers.MultiPartParser,
    ]
    pagination_class = pagination.LimitOffsetPagination
    pagination_class.default_limit = 20


class FilteredPartialResponseModelViewSet(
    OptimizedQuerySetAnnotationsMixin,
    viewsets.ModelViewSet,
    metaclass=FilteredPartialResponseModelViewSetMetaClass,
):
    model: models.Model
    serializer_class = None
    serializer_mixins = None
    related_serializers_list = None
    filterset_mixins = None
    filters: List[Filter] = None
    default_requested_fields_to: None | List = None
    auto_prefetch_related = False

    def __init_subclass__(cls, **kwargs):
        if not hasattr(cls, "model"):
            raise RuntimeError(
                f"Specify `model` attr when using OptimizedModelViewSet for `{cls}"
            )
        super().__init_subclass__(**kwargs)

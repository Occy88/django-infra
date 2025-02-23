from typing import Any, Callable, Dict, List

from django_filters import rest_framework as filters
from django_filters.rest_framework import DjangoFilterBackend
from drf_partial_response.serializers import FieldsListSerializerMixin
from drf_partial_response.views import OptimizedQuerySetBase
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import serializers


class FiltersetSerializerModelMetaClass(type):
    """Auto creates filterset class if one is not specified, and augments view with `filters` attribute.
        This metaclass should work in the background to enhance the power of views without modifying existing functionality
        unless the implementation specifically attempts to make use of it.

        The primary use of this metaclass is for the enabling of the `filters` attribute in a View.

        The secondary uses are for the reduction of boilerplate code associated with serializers and Filtersets.

        Examples
        --------
    import django_extras.filters    >>> # FilteredPartialResponseModelViewSet has a metaclass which inherits `FiltersetSerializerModelMetaClass`
        >>> import django_infra
        >>> from my_app.models import TestModelRelations
        >>> from my_app.serializers import M2MModelSerializer, FKModelSerializer
        >>> class OptimizedTestView(django_infra.api.views.PaginatedViewMixin, django_infra.api.views.FilteredPartialResponseModelViewSet):
        >>>     permission_classes = []
        >>>     authentication_classes = []
        >>>     model = TestModelRelations
        >>>     related_serializers_list = [M2MModelSerializer, FKModelSerializer]
        >>>     filters = [
        >>>         django_infra.api.filters.OrderingFilter(
        >>>             name='ordering',
        >>>             fields=[
        >>>                 django_infra.api.filters.FilterField(internal='date_field',external='dateField'),
        >>>                 django_infra.api.filters.FilterField(internal='id'),
        >>>             ],
        >>>         ),
        >>>         django_infra.api.filters.IContainsFilter(
        >>>             fields=[
        >>>                 django_infra.api.filters.MultiInternalFilterField(
        >>>                     internal=['char_field','date_field'], external='search'
        >>>                 )
        >>>             ]
        >>>         ),
        >>>     ]
        In this example:
        1. Filters are anabled (see documentation on each individual filter.
        2. A serializer is auto created for this class (this can be overwritten simply by specifying one)
        3. The created/specified serializer will automatically use M2MModelSerializer and FKModelSerializer on any fields matching these models.
        Note -M2MModelSerializer and FKModelSerializer are for M2MModel and FKModel test models,
        so if this view was for something like `PatientJourneyViewSet` the equivalent FKModelSerializer would be `PatientSerializer`
        and instead of receiving a `patient_id` in the response you would get a serialized patient based on the specified related serializer.


        This meta class performs the following:
        - if `filterset_class` is not specified, this Meta class will auto create one.
        - the `filterset_class` is injected with any `filterset_mixins` specified, by default `FilterSet` is injected.
        - specified `filters` (as shown in the example) are automatically injected into the `filterser_class` thereby avoiding boilerplate.

        - if `filter_backends` is not specified, this Meta class will auto create one using DjangoFilterBackend.

        - if a `serializer_class` is not specified, this Meta class will auto create one with `__all__` fields.
        - if `related_serializers` are specified then these serializers will be automatically used in related fields matching the serializers model
        -


    """

    def __new__(cls, name, bases, attrs):
        if attrs.get("model", NotImplemented) is NotImplemented:
            return super().__new__(cls, name, bases, attrs)
        if "queryset" not in attrs:
            attrs["queryset"] = attrs["model"].objects.all()
        # Precompute related_serializers mapping
        attrs["related_serializers"] = cls.precompute_related_serializers(
            attrs.get("related_serializers_list", [])
        )
        cls.create_serializer_class(attrs)
        cls.create_filterset_class(attrs)

        return super().__new__(cls, name, bases, attrs)

    @staticmethod
    def create_filterset_class(attrs: Dict[str, Any]):
        """Auto create a filterset class based on `filters` specified in view.
        Filters must be of list of type: django_extras.views.Filter
        """
        FiltersetSerializerModelMetaClass.inject_default_classes(
            attrs=attrs,
            default_classes=[
                DjangoFilterBackend,
            ],
            key="filter_backends",
        )
        FiltersetSerializerModelMetaClass.inject_default_classes(
            attrs=attrs,
            default_classes=[
                filters.FilterSet,
            ],
            key="filterset_mixins",
        )
        filters_ = attrs.get("filters", [])
        all_fields = {k: v for f in filters_ for k, v in f.to_meta().items()}
        model = attrs["model"]
        meta = type(
            "Meta",
            tuple(),
            dict(
                fields=[
                    k for k, v in all_fields.items() if not isinstance(v, Callable)
                ],
                model=attrs["model"],
            ),
        )
        kwargs = {**all_fields, "Meta": meta}
        attrs["filterset_class"] = type(
            f"{model.__name__}FilterSet", attrs.get("filterset_mixins"), kwargs
        )
        return attrs["filterset_class"]

    @staticmethod
    def precompute_related_serializers(related_serializers_list):
        return {
            serializer.Meta.model.__name__: serializer
            for serializer in related_serializers_list
        }

    @staticmethod
    def create_serializer_class(attrs: dict) -> serializers.ModelSerializer:
        model = attrs["model"]
        FiltersetSerializerModelMetaClass.inject_default_classes(
            attrs=attrs,
            default_classes=[
                FieldsListSerializerMixin,
                serializers.ModelSerializer,
            ],
            key="serializer_mixins",
        )
        field_serializers = FiltersetSerializerModelMetaClass.get_field_serializers(
            model, attrs["related_serializers"]
        )

        meta = type("Meta", tuple(), dict(fields="__all__", model=attrs["model"]))
        serializer_attrs = {"Meta": meta, **field_serializers}
        if attrs.get("serializer_class") is not None:
            attrs["serializer_mixins"] = (
                attrs.get("serializer_class"),
                *attrs["serializer_mixins"],
            )
            serializer_attrs["Meta"] = attrs.get("serializer_class").Meta
        # Inject the generated serializer class into attrs without return
        attrs["serializer_class"] = type(
            f"{model.__name__}Serializer",
            attrs.get("serializer_mixins"),
            serializer_attrs,
        )
        return attrs["serializer_class"]

    @staticmethod
    def inject_default_classes(attrs: dict, default_classes: List[object], key: str):
        """Inject default classes into an attrs key if they do not exist."""
        existing_classes = attrs.get(key, tuple())
        missing_classes = []
        for c in default_classes:
            if c not in existing_classes:
                missing_classes.append(c)
        attrs[key] = (*missing_classes, *existing_classes)

    @staticmethod
    def get_field_serializers(model, related_serializers):
        field_serializers = {}
        for field in model._meta.get_fields():
            if hasattr(field, "related_model") and field.related_model:
                related_model_name = field.related_model.__name__
                serializer = related_serializers.get(related_model_name)
                if serializer:
                    field_serializers[field.name] = serializer(
                        many=field.many_to_many or field.one_to_many
                    )
        return field_serializers


class BestGuessCrudSchemaMeta(type):
    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if hasattr(cls, "model") and hasattr(cls, "serializer_class"):
            model_name = cls.model.__name__
            serializer_class = getattr(cls, "serializer_class")
            http_method_names = getattr(cls, "http_method_names", list())
            schemas = dict()
            if "get" in http_method_names:
                schemas.update(
                    list=extend_schema(
                        summary=f"List {model_name}",
                        description=f"Retrieve a list of {model_name}.",
                        responses={200: serializer_class(many=True)},
                    ),
                    retrieve=extend_schema(
                        summary=f"Retrieve {model_name}",
                        description=f"Retrieves a {model_name} by pk.",
                        responses={200: serializer_class},
                    ),
                )
            if "post" in http_method_names:
                schemas.update(
                    update=extend_schema(
                        summary=f"Update {model_name}",
                        description=f"Updates a {model_name} by pk.",
                        responses={200: serializer_class},
                    ),
                    partial_update=extend_schema(
                        summary=f"Patch {model_name}",
                        description=f"Partially updates a {model_name} by pk.",
                        responses={200: serializer_class},
                    ),
                    create=extend_schema(
                        summary=f"Create {model_name}",
                        description=f"Creates a new {model_name}.",
                        responses={201: serializer_class},
                        request=serializer_class,
                    ),
                )
            if "delete" in http_method_names:
                schemas.update(
                    destroy=extend_schema(
                        summary=f"Delete {model_name}",
                        description=f"Deletes a {model_name} by pk.",
                        responses={404: "Not Found"},
                    ),
                )
            cls = extend_schema_view(**schemas)(cls)
        return cls


class FilteredPartialResponseModelViewSetMetaClass(
    BestGuessCrudSchemaMeta, FiltersetSerializerModelMetaClass, OptimizedQuerySetBase
): ...

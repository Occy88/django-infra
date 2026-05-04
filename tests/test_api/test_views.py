from django.db.models import CharField, OuterRef, Value
from model_bakery import baker
from rest_framework import serializers, status
from rest_framework.test import APIRequestFactory

from django_infra.api import filters
from django_infra.api.field_handlers import HandledFieldsMixin, handle_fields
from django_infra.api.views import (
    FilteredPartialResponseModelViewSet,
    PaginatedViewMixin,
)
from tests.test_api.models import FKTestModel, M2MTestModel, TestModelRelations


class FKModelSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = FKTestModel


class M2MModelSerializer(serializers.ModelSerializer):
    class Meta:
        fields = "__all__"
        model = M2MTestModel


class TestModelRelationsSerializer(serializers.ModelSerializer):
    m2m_models = M2MModelSerializer(many=True)
    fk_model = FKModelSerializer(many=False)

    class Meta:
        fields = "__all__"
        model = TestModelRelations


class HandledFieldSerializer(serializers.ModelSerializer):
    handled_label = serializers.CharField(read_only=True)

    class Meta:
        fields = ("id", "char_field", "handled_label")
        model = TestModelRelations
        computed_fields = {
            "handled_label": serializers.CharField(read_only=True),
        }


class OptimizedTestView(PaginatedViewMixin, FilteredPartialResponseModelViewSet):
    permission_classes = []
    authentication_classes = []
    model = TestModelRelations
    related_serializers_list = [M2MModelSerializer, FKModelSerializer]
    filters = [
        filters.OrderingFilter(
            name="ordering",
            fields=[
                filters.FilterField(internal="date_field"),
                filters.FilterField(internal=TestModelRelations.id),
            ],
        ),
        filters.IContainsFilter(
            fields=[
                filters.MultiInternalFilterField(
                    internal=[TestModelRelations.char_field], external="search"
                )
            ]
        ),
    ]


class ExistsSearchTestView(PaginatedViewMixin, FilteredPartialResponseModelViewSet):
    permission_classes = []
    authentication_classes = []
    model = TestModelRelations
    serializer_class = TestModelRelationsSerializer
    filters = [
        filters.IContainsFilter(
            fields=[
                filters.MultiInternalFilterField(
                    internal=[
                        TestModelRelations.char_field,
                        filters.ExistsField(
                            model=FKTestModel,
                            outer_ref="fk_model",
                            fields=["name"],
                        ),
                    ],
                    external="search",
                )
            ]
        ),
    ]


def build_fk_name_exists(*, value, external_map):
    return FKTestModel.objects.filter(
        pk=OuterRef("fk_model"),
        name__iexact=value,
    )


class ExistsSubqueryTestView(PaginatedViewMixin, FilteredPartialResponseModelViewSet):
    permission_classes = []
    authentication_classes = []
    model = TestModelRelations
    serializer_class = TestModelRelationsSerializer
    filters = [
        filters.ExistsSubqueryFilter(
            fields=[
                filters.TypedFilterField(
                    internal="fk_name",
                    external="fk_name",
                    type_=str,
                )
            ],
            subquery_builder=build_fk_name_exists,
        )
    ]


class HandledFieldsTestView(
    HandledFieldsMixin,
    PaginatedViewMixin,
    FilteredPartialResponseModelViewSet,
):
    permission_classes = []
    authentication_classes = []
    model = TestModelRelations
    serializer_class = HandledFieldSerializer

    @handle_fields("handled_label")
    def annotate_handled_label(self, queryset):
        return queryset.annotate(
            handled_label=Value("handled", output_field=CharField())
        )


class TestFilters:
    def test_view_filter(self, db):
        baker.make(
            TestModelRelations,
            char_field="hello my friend",
            _quantity=1,
        )
        baker.make(
            TestModelRelations,
            _quantity=10,
        )
        request = APIRequestFactory().get("/?fields=id,char_field&search=hello")
        view_ = OptimizedTestView.as_view({"get": "list"})
        response = view_(request)
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get("results")) == 1

    def test_handled_fields_mixin_applies_requested_computed_field(self, db):
        baker.make(TestModelRelations, char_field="base text", _quantity=1)

        request = APIRequestFactory().get(
            "/?fields=id,handled_label&computed_fields=handledLabel"
        )
        view_ = HandledFieldsTestView.as_view({"get": "list"})
        response = view_(request)

        assert response.status_code == status.HTTP_200_OK
        assert response.data.get("results")[0]["handled_label"] == "handled"

    def test_icontains_filter_supports_exists_field(self, db):
        matching_fk = baker.make(FKTestModel, name="Needle relation")
        other_fk = baker.make(FKTestModel, name="Other relation")
        baker.make(
            TestModelRelations,
            char_field="base text",
            fk_model=matching_fk,
            _quantity=1,
        )
        baker.make(
            TestModelRelations,
            char_field="base text",
            fk_model=other_fk,
            _quantity=1,
        )

        request = APIRequestFactory().get("/?fields=id,char_field&search=needle")
        view_ = ExistsSearchTestView.as_view({"get": "list"})
        response = view_(request)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get("results")) == 1

    def test_exists_subquery_filter(self, db):
        matching_fk = baker.make(FKTestModel, name="needle")
        other_fk = baker.make(FKTestModel, name="other")
        baker.make(TestModelRelations, fk_model=matching_fk, _quantity=1)
        baker.make(TestModelRelations, fk_model=other_fk, _quantity=1)

        request = APIRequestFactory().get("/?fields=id&fk_name=needle")
        view_ = ExistsSubqueryTestView.as_view({"get": "list"})
        response = view_(request)

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data.get("results")) == 1

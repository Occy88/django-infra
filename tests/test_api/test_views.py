from model_bakery import baker
from rest_framework import serializers, status
from rest_framework.test import APIRequestFactory

from django_infra.api import filters
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

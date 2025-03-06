from rest_framework.serializers import ModelSerializer

from django_infra.api import filters
from django_infra.api.views import FilteredPartialResponseModelViewSet
from django_infra.exporter.models import QueryExport


class QueryExportSerializer(ModelSerializer):
    class Meta:
        model = QueryExport
        fields = "__all__"
        read_only_fields = ("state", "file", "format", "id", "metadata")


class QueryExportViewSet(FilteredPartialResponseModelViewSet):
    model = QueryExport
    serializer_class = QueryExportSerializer
    permission_classes = []
    filters = [
        filters.OrderingFilter(
            name="sort",
            fields=[
                filters.FilterField(internal="id"),
            ],
        ),
        filters.ExactMatchFilter(
            fields=[filters.TypedFilterField(type_=str, internal="state")]
        ),
        filters.IContainsFilter(
            fields=[
                filters.MultiInternalFilterField(internal=["file"], external="search")
            ]
        ),
    ]

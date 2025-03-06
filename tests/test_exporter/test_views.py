from model_bakery import baker

from django_infra.api.views import FilteredPartialResponseModelViewSet
from django_infra.exporter.models import QueryExport
from django_infra.exporter.views import QueryExportSerializer, QueryExportViewSet
from django_infra.testing.common import ModelViewTest


def query_export_factory(**kwargs):
    return baker.make(QueryExport)


class TestQueryExportViewSet(ModelViewTest):
    view_parents = (FilteredPartialResponseModelViewSet,)
    view = QueryExportViewSet
    serializer = QueryExportSerializer
    permission_classes = []
    factory = query_export_factory
    write_only_fields = set()
    read_only_fields = {"state", "metadata", "id", "file", "format"}
    normal_fields = set()

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from django_infra.exporter.views import QueryExportViewSet

app_name = "exporter"

# Create a router and register our viewsets with it, using an empty prefix.
router = DefaultRouter()
router.register(r"", QueryExportViewSet, basename="exporter")

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path("", include(router.urls)),
]

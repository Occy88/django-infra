from django.urls import include, path
from rest_framework.routers import DefaultRouter

from django_infra.feature_flags.views import FeatureFlagViewSet

app_name = "feature_flags"

# Create a router and register our viewsets with it, using an empty prefix.
router = DefaultRouter()
router.register(r"", FeatureFlagViewSet, basename="featureflag")

# The API URLs are now determined automatically by the router.
urlpatterns = [
    path("", include(router.urls)),
]

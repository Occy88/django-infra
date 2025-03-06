from rest_framework import status
from rest_framework.decorators import action
from rest_framework.permissions import SAFE_METHODS, IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from django_infra.feature_flags.models import FeatureFlag
from django_infra.feature_flags.serializers import FeatureFlagSerializer


class IsAdminOrReadOnlyPermission(IsAdminUser):
    def has_permission(self, request, view):
        return request.method in SAFE_METHODS or super().has_permission(request, view)


class FeatureFlagViewSet(ModelViewSet):
    queryset = FeatureFlag.objects.all()
    serializer_class = FeatureFlagSerializer
    permission_classes = [IsAdminOrReadOnlyPermission]

    def get_queryset(self):
        # hack to ensure sync occurs at least once (on access)
        # won't sync on every call.
        return FeatureFlag.objects.all()

    @action(detail=False, methods=["post"], url_path="reset")
    def reset(self, request):
        FeatureFlag.objects.reset_env_flags()
        return Response(dict(), status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], url_path="activate")
    def activate(self, request, pk=None):
        flag = self.get_object()
        flag.update(active=True)
        return Response(
            self.serializer_class(instance=flag).data, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], url_path="deactivate")
    def deactivate(self, request, pk=None):
        flag = self.get_object()
        flag.update(active=False)
        return Response(
            self.serializer_class(instance=flag).data, status=status.HTTP_200_OK
        )

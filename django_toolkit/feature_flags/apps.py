from django.apps import AppConfig


class FeatureFlagConfig(AppConfig):
    name = "django_toolkit.feature_flags"

    def ready(self):
        # load receivers
        import django_toolkit.feature_flags.receivers  # noqa F401

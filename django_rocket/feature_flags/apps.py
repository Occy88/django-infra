from django.apps import AppConfig


class FeatureFlagConfig(AppConfig):
    name = "django_rocket.feature_flags"

    def ready(self):
        # load receivers
        import django_rocket.feature_flags.receivers  # noqa F401

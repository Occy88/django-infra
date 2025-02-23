from django.apps import AppConfig


class ExporterConfig(AppConfig):
    name = "django_rocket.exporter"

    def ready(self):
        # load receivers
        # import django_rocket.exporter.receivers  # noqa F401
        ...

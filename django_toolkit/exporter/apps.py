from django.apps import AppConfig


class ExporterConfig(AppConfig):
    name = "django_toolkit.exporter"

    def ready(self):
        # load receivers
        # import django_toolkit.exporter.receivers  # noqa F401
        ...

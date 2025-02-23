from django.apps import AppConfig


class ExporterConfig(AppConfig):
    name = "django_infra.exporter"

    def ready(self):
        # load receivers
        # import django_infra.exporter.receivers  # noqa F401
        ...

from django.apps import AppConfig


class SampleAppConfig(AppConfig):
    name = "sample_app"

    # def ready(self):
    #     # load receivers
    #     import sample_app.receivers  # noqa F401

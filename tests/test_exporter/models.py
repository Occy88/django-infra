from django.db import models as dm

from django_toolkit.db.models import UpdatableModel


class ExportRelatedTestModel(UpdatableModel):
    field2 = dm.CharField(max_length=100, default="", blank=True)

    class Meta:
        app_label = __package__.replace(".", "_")


class ExportTestModel(UpdatableModel):
    field1 = dm.CharField(max_length=100, default="", blank=True)
    related_model = dm.ForeignKey(ExportRelatedTestModel,on_delete=dm.CASCADE)
    class Meta:
        app_label = __package__.replace(".", "_")

from django.db import models as dm

from django_infra.db.models import UpdatableModel


class M2MTestModel(dm.Model):
    name = dm.CharField(max_length=40)

    class Meta:
        app_label = __package__.replace(".", "_")


class FKTestModel(dm.Model):
    name = dm.CharField(max_length=40)

    class Meta:
        app_label = __package__.replace(".", "_")


class TestModel(UpdatableModel, dm.Model):
    field1 = dm.CharField(max_length=100, default="", blank=True)
    field2 = dm.CharField(max_length=100, default="", blank=True)

    class Meta:
        app_label = __package__.replace(".", "_")


class TestModelRelations(dm.Model):
    date_field = dm.DateTimeField()
    value_field = dm.IntegerField()
    char_field = dm.CharField(max_length=100)
    m2m_models = dm.ManyToManyField(M2MTestModel)
    fk_model = dm.ForeignKey(FKTestModel, on_delete=dm.CASCADE)

    class Meta:
        app_label = __package__.replace(".", "_")

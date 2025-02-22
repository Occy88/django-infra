from django.db import models

from django_toolkit.db.models import UpdatableModel


class MyModelManager(models.Manager):
    ...


class MyModel(UpdatableModel):
    ...
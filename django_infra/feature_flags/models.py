from django.db import models

from django_infra.db.models import UpdatableModel


class FeatureFlagManager(models.Manager):
    def create(self, *args, **kwargs):
        # Prevent direct creation of objects
        raise NotImplementedError(
            "Direct creation of FeatureFlag objects is not allowed."
        )

    def delete(self, *args, **kwargs):
        # Prevent deletion of objects
        raise NotImplementedError("Deletion of FeatureFlag objects is not allowed.")


class FeatureFlag(UpdatableModel):
    id = models.CharField(
        max_length=50,
        unique=True,
        primary_key=True,
    )
    active = models.BooleanField(default=False)
    value = models.IntegerField(default=0)
    value_str = models.CharField(default="", max_length=100)
    # Assign the custom manager
    objects = FeatureFlagManager()

    def __bool__(self):
        return self.active

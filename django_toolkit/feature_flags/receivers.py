from django.db.models.signals import post_save
from django.dispatch import receiver

from django_toolkit.feature_flags.flags import db_get_or_create
from django_toolkit.feature_flags.models import FeatureFlag


@receiver(post_save, sender=FeatureFlag)
def pop_cache(*args, **kwargs):
    db_get_or_create.cache_clear()

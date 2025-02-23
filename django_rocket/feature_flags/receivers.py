from django.db.models.signals import post_save
from django.dispatch import receiver

from django_infra.feature_flags.flags import retrieve_feature_flag_from_db
from django_infra.feature_flags.models import FeatureFlag


@receiver(post_save, sender=FeatureFlag)
def pop_cache(*args, **kwargs):
    retrieve_feature_flag_from_db.cache_clear()

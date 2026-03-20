from __future__ import annotations

import logging

from django.conf import settings
from django.db import models as dm

logger = logging.getLogger(__name__)


class TimeTrackingModel(dm.Model):
    created_time = dm.DateTimeField(auto_now_add=True, null=True)
    modified_time = dm.DateTimeField(auto_now=True, null=True)

    class Meta:
        abstract = True


class UserTrackingMixin(dm.Model):
    created_by = dm.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=dm.PROTECT,
        related_name="created_by_%(app_label)s_%(class)s_related",
        editable=False,
        null=True,
    )
    modified_by = dm.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=dm.PROTECT,
        related_name="modified_by_%(app_label)s_%(class)s_related",
        editable=False,
        null=True,
    )

    def save(self, *args, **kwargs):
        """Best effort attempt to set modified_by/created_by using crum."""
        try:
            from crum import get_current_user
        except ImportError:
            return super().save(*args, **kwargs)

        creating = self.id is None
        a_user_is_null = None in {self.created_by, self.modified_by}
        current_user = get_current_user()
        # attempt resolve any None fields
        if a_user_is_null and current_user:
            self.created_by = self.created_by or current_user
            self.modified_by = self.modified_by or current_user
        # best effort to update modifying user.
        if not creating and current_user != self.modified_by:
            self.modified_by = self.modified_by or current_user
        if a_user_is_null:
            logger.info("Creator or modifier is still null: %s", self)

        return super().save(*args, **kwargs)

    class Meta:
        abstract = True


class TrackingMixin(TimeTrackingModel, UserTrackingMixin):
    class Meta:
        abstract = True

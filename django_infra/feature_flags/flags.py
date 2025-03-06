from __future__ import annotations

import dataclasses
from functools import lru_cache
from typing import TYPE_CHECKING, Set

from django_infra.env import load_env_val

if TYPE_CHECKING:
    from django_infra.feature_flags.models import FeatureFlag


@lru_cache  # this is popped in a post save signal on FeatureFlag.
def retrieve_feature_flag_from_db(*, key: str, active=False) -> "FeatureFlag":
    from django_infra.feature_flags.models import FeatureFlag

    """Get feature flag value from db, Ensure sync is run once.
    Property overriding every attribute in FeatureFlags, set by FeatureFlagsMeta"""
    # set a boolean flag stating we have synced with the database on any initial use.
    ff, _ = FeatureFlag.objects.get_or_create(pk=key, defaults=dict(active=active))
    return ff


def register_feature_flag(flag_name, default=False) -> "FeatureFlag":
    return_val = property(
        fget=lambda self: retrieve_feature_flag_from_db(
            key=flag_name, active=load_env_val(flag_name, default=default)
        )
    )
    return return_val


@dataclasses.dataclass
class FeatureFlags:
    """Exposed database stored flags as bool properties efficiently.
    A flag is loaded once request
    Example:
        >>> # settings.py:
        >>> Flags = FeatureFlags()
        >>> Flags.DEFAULT_FLAG=register_feature_flag('DEFAULT_FLAG',default=True),
        >>>
        >>> # somewhere else.
        >>> from django_infra.feature_f1lags import FeatureFlags # noqa
        >>> def my_function(*args,**kwargs):
        >>>     if FeatureFlags.DEFAULT_FLAG:
        >>>         print("default flag is enable")
        >>>         FeatureFlags.DEFAULT_FLAG.update(active=False)
        >>>         print("default flag is disabled")
        >>>     return args
    """

    _flags: set = dataclasses.field(init=False, default_factory=set)

    def __setattr__(self, key, value):
        if key not in {"_flags"}:
            # some minimal validation that register_feature_flag was used for setup.
            if not isinstance(value, property):
                raise ValueError(
                    f"Flag value must be created via {register_feature_flag}"
                )
            setattr(self.__class__, key, value)
            self._flags.add(key)
            return

        super().__setattr__(key, value)

    @property
    def choices(self) -> Set[str]:
        return self._flags

    def __hash__(self):
        return 10


FeatureFlags = FeatureFlags()
flags = FeatureFlags

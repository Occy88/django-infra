import os

import pytest
from django import setup
from django.apps import AppConfig, apps
from django.core.management import call_command

from config import settings

"""Common file to load across all of pytest see conftest.pytest_plugins"""

import pytest

@pytest.fixture(scope="session")
def apps_ready():
    if not apps.ready:
        setup()


@pytest.fixture(scope="session")
def setup_test_app_factory(django_db_setup, django_db_blocker, apps_ready):
    """Migrate models.py in a test directory creating migrations for useage in tests.

    Creates a temporary app based on the package name such that any directory
    can have a models.py file defining models for testing purposes only.

    >>> @pytest.fixture(scope='session',autouse=True)
    >>> def conftest_fixture(setup_test_app_factory):
    >>>     setup_test_app_factory(__package__)
    """

    def inner(package):
        if settings.INTEGRATION_TEST:
            return
        with django_db_blocker.unblock():
            app_config = AppConfig.create(package)
            app_config.apps = apps
            if package in apps.app_configs:
                # already setup, just return.
                return
            app_config.label = package.replace('.','_')

            apps.app_configs[app_config.label] = app_config
            app_config.import_models()
            apps.clear_cache()
            # Consolidate the condition to check for migrations existence and apply
            call_command(
                "makemigrations", app_config.label, interactive=False, verbosity=0
            )
            call_command("migrate", app_config.label, interactive=False, verbosity=0)
            apps.clear_cache()
    return inner


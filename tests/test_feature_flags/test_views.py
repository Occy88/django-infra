import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from rest_framework import status
from rest_framework.test import APIClient

from django_rocket.feature_flags.flags import (
    retrieve_feature_flag_from_db,
    flags,
    register_feature_flag,
)

default_flag_name = "DEFAULT_FLAG"
flags.DEFAULT_FLAG = register_feature_flag(default_flag_name, True)



@pytest.fixture(scope="function", autouse=True)
def clear_lru_caches():
    retrieve_feature_flag_from_db.cache_clear()


@pytest.fixture()
def default_flag():
    # use flag for db registration
    _ = flags.DEFAULT_FLAG
    return flags.DEFAULT_FLAG


def test_get_feature_flags(db, default_flag, admin_client):
    response = admin_client.get("/feature-flags/")
    assert response.status_code == status.HTTP_200_OK, response.content


def test_activate_feature_flag_ok(db, default_flag, admin_client):
    """Activate"""
    # ensure that modifying the feature flag is permanent regardless of sync
    admin_client.post("/feature-flags/sync/")
    response = admin_client.post(f"/feature-flags/{default_flag.id}/activate/")
    admin_client.post("/feature-flags/sync/")
    assert response.status_code == status.HTTP_200_OK, response.content


def test_deactivate_feature_flag_ok(db, default_flag, admin_client):
    # ensure that modifying the feature flag is permanent regardless of sync
    default_flag.update(active=True)
    response = admin_client.post(f"/feature-flags/{default_flag.id}/deactivate/")
    default_flag.refresh_from_db()
    assert response.status_code == status.HTTP_200_OK, response.content
    assert not default_flag.active


def test_patch_feature_flag_true_ok(db, default_flag, admin_client):
    default_flag.update(active=False)
    response = admin_client.patch(
        path=f"/feature-flags/{default_flag.id}/",
        data=dict(active=True, value=2, value_str="test"),
        format="json",
    )
    default_flag.refresh_from_db()

    assert response.status_code == status.HTTP_200_OK, response.content
    assert default_flag.active
    assert default_flag.value == 2
    assert default_flag.value_str == "test"


def test_patch_feature_flag_false_ok(db, default_flag, admin_client):
    response = admin_client.patch(
        f"/feature-flags/{default_flag.id}/", data=dict(active=False), format="json"
    )
    default_flag.refresh_from_db()
    assert response.status_code == status.HTTP_200_OK, response.content
    assert not default_flag.active


def test_patch_feature_flag_true_permission_err(db, default_flag, user_client):
    response = user_client.patch(
        f"/feature-flags/{default_flag}/", data=dict(active=True), format="json"
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN, response.content


def test_feature_flag_integration(db, default_flag):
    assert default_flag.active == bool(default_flag)
    default_flag.update(active=not default_flag.active)
    assert default_flag.active == bool(default_flag)

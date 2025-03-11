import logging

import pytest

logger = logging.getLogger(__file__)


@pytest.fixture(scope="session", autouse=True)
def test_api_model_setup(setup_test_app_factory):
    setup_test_app_factory(package=__package__)

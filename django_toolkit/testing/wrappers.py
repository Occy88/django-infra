import pytest
from django.conf import settings
from django.db import transaction


def disable_on_transaction_commit():
    """
    Break this out to allow for easier patching. Basically if you're test is transactional then
    you'll want to patch this to False to sure that the behaviour matches the release code
    """
    return settings.IS_TEST


def on_transaction_commit(func):
    """Decorator to delay function execution until after the current transaction commits."""

    def wrapper(*args, **kwargs):
        # Use a lambda to capture args and kwargs and pass them to the function
        if disable_on_transaction_commit():
            func(*args, **kwargs)
        else:
            transaction.on_commit(lambda: func(*args, **kwargs))

    return wrapper


def synchronous_in_test(func):
    def wrapper(*args, **kwargs):
        existing_state = settings.CELERY_TASK_ALWAYS_EAGER
        if settings.IS_TEST:
            settings.CELERY_TASK_ALWAYS_EAGER = True
        try:
            result = func(*args, **kwargs)
        except Exception:
            raise
        finally:
            if settings.IS_TEST:
                settings.CELERY_TASK_ALWAYS_EAGER = existing_state
        return result

    return wrapper


def integration_test(
    func,
):
    return pytest.mark.skipif(not settings.INTEGRATION_TEST, reason="integration test")(
        pytest.mark.integration(func)
    )


def qa_test(
    func,
):
    return pytest.mark.skipif(not settings.QA_TEST, reason="qa test")(
        pytest.mark.qa(func)
    )


def prod_test(
    func,
):
    return pytest.mark.skipif(not settings.PROD_TEST, reason="prod test")(
        pytest.mark.prod(func)
    )

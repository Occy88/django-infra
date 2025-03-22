import pytest

from django_infra.env.shell import run_command


@pytest.mark.order("first")
def test_lint():
    """
    Test that runs the pre-commit linting.
    """
    run_command("pre-commit run --all-files")

from config.settings import BASE_DIR
from django_infra.db.config import get_db_config_from_connection_name


def pytest_configure(config):
    """Pytest pre-xdist configuration."""
    if hasattr(config, "workerinput"):
        return
    # setup django test database using a dump.
    config = get_db_config_from_connection_name()
    config.DUMP_ROOT = BASE_DIR
    config.reset_database_from_dump()

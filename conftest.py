from django_rocket.db.config import get_db_config_from_connection_name


def pytest_configure(config):
    """Pytest pre-xdist configuration."""
    if hasattr(config, "workerinput"):
        return
    # setup django test database using a dump.\
    get_db_config_from_connection_name().reset_database_from_dump()

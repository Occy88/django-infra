import os

from django.core.management.base import BaseCommand
from django.db import connections
from django.test.utils import setup_test_environment, teardown_test_environment

from django_toolkit.db.config import get_db_config_from_connection_name


class Command(BaseCommand):
    help = "manage test database."

    def add_arguments(self, parser):
        parser.add_argument(
            "--refreshdb", action="store_true", help="Refresh the test database."
        )
        parser.add_argument(
            "--restoredump",
            action="store_true",
            help="Restore dump of the test database.",
        )
        parser.add_argument("--dropdb", action="store_true", help="drop the test db.")
        parser.add_argument(
            "--dumpdb", action="store_true", help="Just dump the test database."
        )

    def handle(self, *args, **options):
        """
        if refresh db -> run migrations, dump

        if dump exists -> load dump
        if dump doesn't exist:
            check db exists
                dump
            migrate & dump

        Parameters
        ----------
        args
        options

        Returns
        -------

        """
        from conftest import refresh_test_db

        setup_test_environment()
        self.connection = connections["default"]
        self.test_db_config = get_db_config_from_connection_name()
        try:
            if options["refreshdb"]:
                refresh_test_db()
            if options["dumpdb"]:
                self.test_db_config.create_dump()
            if options["dropdb"]:
                self.test_db_config.drop_database()
            if options["restoredump"]:
                self.test_db_config.restore_dump()
            self.stdout.write(self.style.SUCCESS("DB SETUP SUCCESS!"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Unexpected error occurred: {e}"))
            exit(1)
        finally:
            self.cleanup()

    @staticmethod
    def cleanup():
        teardown_test_environment()

    @property
    def cpu_count(self):
        return os.cpu_count() or 1

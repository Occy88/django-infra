from __future__ import annotations

import dataclasses
import logging
import os
import pprint
import subprocess
import typing

import pydantic
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError, connections, transaction

from django_infra.env import run_command

logger = logging.getLogger(__file__)


def get_db_config_from_connection_name(
    connection_name: str = "default",
) -> DatabaseConfig:
    assert connection_name in settings.DATABASES
    return DatabaseConfig(
        CONNECTION_NAME=connection_name, **settings.DATABASES[connection_name]
    )


@pydantic.dataclasses.dataclass(config=pydantic.ConfigDict(extra="allow"))
class DatabaseConfig:
    """Handle database related operations."""

    ENGINE: str
    NAME: str
    USER: str
    PASSWORD: str
    HOST: str
    PORT: int
    CONNECTION_NAME: str = None
    DUMP_ROOT = os.path.join(settings.BASE_DIR, "docker")

    def update(self, update_settings=False, **kwargs):
        """Updates config and optionally settings as well to match."""
        for key, val in kwargs.items():
            setattr(self, key, val)
            if update_settings:
                settings.DATABASES[self.CONNECTION_NAME][key] = val

    @property
    def pg_env(self):
        env = {
            **os.environ,
            "PGPASSWORD": self.PASSWORD,
        }
        return env

    def create_dump(self):
        """Create a database dump using pg_dump."""
        command = [
            "pg_dump",
            *self.user_host_port_params,
            "-Fc",
            "-f",
            self.db_dump_path,
            self.NAME,
        ]
        run_command(command, self.pg_env)

    @property
    def user_host_port_params(self) -> typing.List[str]:
        return [
            "-U",
            self.USER,
            "-h",
            self.HOST,
            "-p",
            str(self.PORT),
        ]

    @property
    def db_dump_path(self):
        return os.path.join(self.DUMP_ROOT, f"{self.NAME}.psql")

    @property
    def dump_exists(self):
        return os.path.exists(self.db_dump_path)

    def apply_migrations(self):
        create_db_command = [
            "python",
            os.path.join(settings.BASE_DIR, "manage.py"),
            "migrate",
            "--database",
            self.CONNECTION_NAME,
        ]
        run_command(create_db_command, self.pg_env)

    def makemigrations(self):
        create_db_command = [
            "python",
            os.path.join(settings.BASE_DIR, "manage.py"),
            "makemigrations",
        ]
        run_command(create_db_command, self.pg_env)

    def clone_database(self, to_config: DatabaseConfig):
        to_config.drop_database()
        self.terminate_db_connection()
        create_db_command = [
            "createdb",
            "-T",
            self.NAME,
            to_config.NAME,
            *self.user_host_port_params,
        ]
        run_command(create_db_command, self.pg_env)

    def terminate_db_connection(self):
        terminate_command = [
            "psql",
            *self.user_host_port_params,
            "-d",
            "postgres",
            # Connect to the default 'postgres' database to issue the command
            "-c",
            f"SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity "
            f"WHERE pg_stat_activity.datname = '{self.NAME}' AND pid <> "
            f"pg_backend_pid();",
        ]
        run_command(terminate_command, self.pg_env)

    def reset_database(self):
        """Drops and re-creates a blank database"""
        self.drop_database()
        self.create_database()

    def reset_database_from_dump(self, allow_input=False):
        """Restore database from dump, apply migrations, update dump.

        In cases where a dump does not exist and input is allowed:
        An existing database may optionally be fully reset for migration rebuild.
        """
        # If a dump exists, drop default & test to restore both.
        if self.dump_exists:
            self.restore_dump()
            if self.makemigrations_applied() and self.all_migrations_applied():
                return
        else:
            # ask user if they want to drop the default db if it exists.
            # (in case of partial migrations, no need to restart from scratch)
            if allow_input and (
                not self.database_exists
                or input(f"Re-run all migrations on {self.NAME} db [n]:") == "y"
            ):
                self.reset_database()
        # for some reason migrations can only be applied on a db named `default`...
        self.makemigrations()
        self.apply_migrations()
        self.create_dump()

    def restore_dump(self):
        """Restores database from locally stored dump."""
        if not self.dump_exists:
            raise ValueError(f"Dump {self.db_dump_path} does not exist.")
        self.reset_database()
        command = [
            "pg_restore",
            *self.user_host_port_params,
            "-d",
            self.NAME,
            self.db_dump_path,
        ]
        run_command(command, self.pg_env)
        return True

    @property
    def database_exists(self):
        exists_ok = self.check_database_connection()
        return exists_ok

    def create_database(self):
        create_db_command = [
            "createdb",
            self.NAME,
            *self.user_host_port_params,
        ]
        run_command(create_db_command, self.pg_env)

    def drop_database(self, fail_silently=True):
        self.terminate_db_connection()
        try:
            drop_db_command = [
                "dropdb",
                self.NAME,
                *self.user_host_port_params,
            ]
            run_command(drop_db_command, self.pg_env)
        except (RuntimeError, OperationalError, subprocess.CalledProcessError):
            # if there is an error mostly it's because the db doesn't exist.
            if not fail_silently:
                raise

    def check_database_connection(self):
        db_conn = connections[self.CONNECTION_NAME]
        try:
            db_conn.cursor()
        except (
            OperationalError,
            ImproperlyConfigured,
            transaction.TransactionManagementError,
        ):
            return False
        except Exception as e:
            logger.error(f"Unknown db exception: {e}")
            return False
        return True

    def all_migrations_applied(self) -> bool:
        command = [
            "python",
            os.path.join(settings.BASE_DIR, "manage.py"),
            "showmigrations",
            "--database",
            self.CONNECTION_NAME,
        ]
        try:
            output = subprocess.check_output(command, env=self.pg_env, text=True)
        except subprocess.CalledProcessError:
            return False
        return "[ ]" not in output

    def makemigrations_applied(self) -> bool:
        command = [
            "python",
            os.path.join(settings.BASE_DIR, "manage.py"),
            "makemigrations",
            "--check",
        ]
        try:
            run_command(command)
            return True
        except subprocess.CalledProcessError:
            return False

    def __str__(self):
        data = dataclasses.asdict(self)
        data.update(db_dump_path=self.db_dump_path)
        return pprint.pformat(data)

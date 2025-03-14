import dataclasses
import os
import subprocess
from unittest.mock import MagicMock, PropertyMock, patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.db import OperationalError
from django.db.transaction import TransactionManagementError

from config import settings
from django_infra.db.config import DatabaseConfig


class TestDatabaseConfig:
    """Test suite for the DatabaseConfig class."""

    @pytest.fixture
    def db_config(self):
        """Create a fixture for DatabaseConfig instance."""
        settings.DATABASES["fish"] = dict(
            ENGINE="django.db.backends.postgresql",
            NAME="fish_db",
            USER="test_user",
            PASSWORD="test_password",
            HOST="localhost",
            PORT=5432,
            CONNECTION_NAME="fish",
            DUMP_ROOT="/mock/path/",
        )
        config = DatabaseConfig(**settings.DATABASES["fish"])
        return config

    @pytest.fixture
    def mock_run_command(self):
        """Mock the run_command function."""
        with patch("django_infra.db.config.run_command") as mock:
            yield mock

    @pytest.fixture
    def mock_connections(self):
        """Mock Django connections."""
        with patch("django_infra.db.config.connections") as mock:
            mock_conn = MagicMock()
            mock_cursor = MagicMock()
            mock_conn.__getitem__.return_value.cursor.return_value = mock_cursor
            mock.__getitem__.return_value = mock_conn
            yield mock

    @pytest.fixture
    def mock_os_path_exists(self):
        """Mock os.path.exists function."""
        with patch("os.path.exists") as mock:
            yield mock

    @pytest.fixture
    def mock_check_output(self):
        """Mock subprocess.check_output function."""
        with patch("subprocess.check_output") as mock:
            yield mock

    def test_init(self, db_config):
        """Test initialization of DatabaseConfig."""
        assert db_config.ENGINE == "django.db.backends.postgresql"
        assert db_config.NAME == "fish_db"
        assert db_config.USER == "test_user"
        assert db_config.PASSWORD == "test_password"
        assert db_config.HOST == "localhost"
        assert db_config.PORT == 5432
        assert db_config.CONNECTION_NAME == "fish"

    def test_update(self, db_config):
        """Test update method."""
        # Test without updating settings
        db_config.update(NAME="new_db", PORT=5433)
        assert db_config.NAME == "new_db"
        assert db_config.PORT == 5433
        assert (
            settings.DATABASES[db_config.CONNECTION_NAME]["NAME"] == "fish_db"
        )  # Not updated

        # Test with updating settings
        db_config.update(update_settings=True, NAME="newer_db")
        assert db_config.NAME == "newer_db"
        assert (
            settings.DATABASES[db_config.CONNECTION_NAME]["NAME"] == "newer_db"
        )  # Updated

    def test_pg_env(self, db_config):
        """Test pg_env property."""
        with patch.dict(os.environ, {"EXISTING_VAR": "existing_value"}):
            env = db_config.pg_env
            assert env["PGPASSWORD"] == "test_password"
            assert env["EXISTING_VAR"] == "existing_value"

    def test_user_host_port_params(self, db_config):
        """Test user_host_port_params property."""
        params = db_config.user_host_port_params
        assert params == ["-U", "test_user", "-h", "localhost", "-p", "5432"]

    def test_db_dump_path(self, db_config):
        """Test db_dump_path property."""
        expected_path = os.path.join("/mock/path/", "fish_db.psql")
        assert db_config.db_dump_path == expected_path

    def test_dump_exists(self, db_config, mock_os_path_exists):
        """Test dump_exists property."""
        # Test when dump exists
        mock_os_path_exists.return_value = True
        assert db_config.dump_exists is True

        # Test when dump doesn't exist
        mock_os_path_exists.return_value = False
        assert db_config.dump_exists is False

    def test_create_dump(self, db_config, mock_run_command):
        """Test create_dump method."""
        db_config.create_dump()
        expected_command = [
            "pg_dump",
            "-U",
            "test_user",
            "-h",
            "localhost",
            "-p",
            "5432",
            "-Fc",
            "-f",
            db_config.db_dump_path,
            "fish_db",
        ]
        mock_run_command.assert_called_once_with(expected_command, db_config.pg_env)

    def test_apply_migrations(self, db_config, mock_run_command):
        """Test apply_migrations method."""
        db_config.apply_migrations()
        expected_command = [
            "python",
            os.path.join(settings.BASE_DIR, "manage.py"),
            "migrate",
            "--database",
            "fish",
        ]
        mock_run_command.assert_called_once_with(expected_command, db_config.pg_env)

    def test_makemigrations(self, db_config, mock_run_command):
        """Test makemigrations method."""
        db_config.makemigrations()
        expected_command = [
            "python",
            os.path.join(settings.BASE_DIR, "manage.py"),
            "makemigrations",
        ]
        mock_run_command.assert_called_once_with(expected_command, db_config.pg_env)

    def test_clone_database(self, db_config, mock_run_command):
        """Test clone_database method."""
        # Create a second config to clone to
        to_config = DatabaseConfig(
            ENGINE="django.db.backends.postgresql",
            NAME="target_db",
            USER="test_user",
            PASSWORD="test_password",
            HOST="localhost",
            PORT=5432,
            CONNECTION_NAME="target",
        )

        # Patch the terminate_db_connection and drop_database methods
        with (
            patch.object(to_config, "drop_database") as mock_drop,
            patch.object(db_config, "terminate_db_connection") as mock_terminate,
        ):
            db_config.clone_database(to_config)

            # Verify method calls
            mock_drop.assert_called_once()
            mock_terminate.assert_called_once()

            # Verify run_command was called with correct arguments
            expected_command = [
                "createdb",
                "-T",
                "fish_db",
                "target_db",
                "-U",
                "test_user",
                "-h",
                "localhost",
                "-p",
                "5432",
            ]
            mock_run_command.assert_called_once_with(expected_command, db_config.pg_env)

    #
    def test_terminate_db_connection(self, db_config, mock_run_command):
        """Test terminate_db_connection method."""
        db_config.terminate_db_connection()
        expected_command = [
            "psql",
            "-U",
            "test_user",
            "-h",
            "localhost",
            "-p",
            "5432",
            "-d",
            "postgres",
            "-c",
            "SELECT pg_terminate_backend(pg_stat_activity.pid) FROM pg_stat_activity "
            "WHERE pg_stat_activity.datname = 'fish_db' AND pid <> pg_backend_pid();",
        ]
        mock_run_command.assert_called_once_with(expected_command, db_config.pg_env)

    #
    def test_reset_database(self, db_config):
        """Test reset_database method."""
        with (
            patch.object(db_config, "drop_database") as mock_drop,
            patch.object(db_config, "create_database") as mock_create,
        ):
            db_config.reset_database()

            # Verify method calls
            mock_drop.assert_called_once()
            mock_create.assert_called_once()

    def test_restore_dump_exists(
        self, db_config, mock_run_command, mock_os_path_exists
    ):
        """Test restore_dump method when dump exists."""
        mock_os_path_exists.return_value = True

        with patch.object(db_config, "reset_database") as mock_reset:
            result = db_config.restore_dump()

            # Verify reset_database was called
            mock_reset.assert_called_once()

            # Verify run_command was called with correct arguments
            expected_command = [
                "pg_restore",
                "-U",
                "test_user",
                "-h",
                "localhost",
                "-p",
                "5432",
                "-d",
                "fish_db",
                db_config.db_dump_path,
            ]
            mock_run_command.assert_called_once_with(expected_command, db_config.pg_env)

            # Verify return value
            assert result is True

    def test_restore_dump_not_exists(self, db_config, mock_os_path_exists):
        """Test restore_dump method when dump doesn't exist."""
        mock_os_path_exists.return_value = False

        with pytest.raises(ValueError) as excinfo:
            db_config.restore_dump()

        assert f"Dump {db_config.db_dump_path} does not exist" in str(excinfo.value)

    def test_database_exists(self, db_config):
        """Test database_exists property."""
        with patch.object(db_config, "check_database_connection") as mock_check:
            # Test when database exists
            mock_check.return_value = True
            assert db_config.database_exists is True

            # Test when database doesn't exist
            mock_check.return_value = False
            assert db_config.database_exists is False

    def test_create_database(self, db_config, mock_run_command):
        """Test create_database method."""
        db_config.create_database()
        expected_command = [
            "createdb",
            "fish_db",
            "-U",
            "test_user",
            "-h",
            "localhost",
            "-p",
            "5432",
        ]
        mock_run_command.assert_called_once_with(expected_command, db_config.pg_env)

    def test_drop_database_success(self, db_config, mock_run_command):
        """Test drop_database method when successful."""
        with patch.object(db_config, "terminate_db_connection") as mock_terminate:
            db_config.drop_database()

            # Verify method calls
            mock_terminate.assert_called_once()

            # Verify run_command was called with correct arguments
            expected_command = [
                "dropdb",
                "fish_db",
                "-U",
                "test_user",
                "-h",
                "localhost",
                "-p",
                "5432",
            ]
            mock_run_command.assert_called_once_with(expected_command, db_config.pg_env)

    def test_drop_database_failure_silent(self, db_config, mock_run_command):
        """Test drop_database method when it fails silently."""
        mock_run_command.side_effect = subprocess.CalledProcessError(1, [])

        with patch.object(db_config, "terminate_db_connection") as mock_terminate:
            # Should not raise an exception with fail_silently=True (default)
            db_config.drop_database()

            # Verify method calls
            mock_terminate.assert_called_once()
            mock_run_command.assert_called_once()

    def test_drop_database_failure_not_silent(self, db_config, mock_run_command):
        """Test drop_database method when it fails and not silent."""
        mock_run_command.side_effect = subprocess.CalledProcessError(1, [])

        with patch.object(db_config, "terminate_db_connection") as mock_terminate:
            # Should raise an exception with fail_silently=False
            with pytest.raises(subprocess.CalledProcessError):
                db_config.drop_database(fail_silently=False)

            # Verify method calls
            mock_terminate.assert_called_once()
            mock_run_command.assert_called_once()

    def test_check_database_connection_success(self, db_config, mock_connections):
        """Test check_database_connection method when successful."""
        result = db_config.check_database_connection()
        assert result is True
        mock_connections.__getitem__.assert_called_with("fish")

    def test_check_database_connection_operational_error(
        self, db_config, mock_connections
    ):
        """Test check_database_connection method with OperationalError."""
        mock_connections.__getitem__.return_value.cursor.side_effect = OperationalError
        result = db_config.check_database_connection()
        assert result is False

    def test_check_database_connection_improperly_configured(
        self, db_config, mock_connections
    ):
        """Test check_database_connection method with ImproperlyConfigured."""
        mock_connections.__getitem__.return_value.cursor.side_effect = (
            ImproperlyConfigured
        )
        result = db_config.check_database_connection()
        assert result is False

    def test_check_database_connection_transaction_error(
        self, db_config, mock_connections
    ):
        """Test check_database_connection method with TransactionManagementError."""
        mock_connections.__getitem__.return_value.cursor.side_effect = (
            TransactionManagementError
        )
        result = db_config.check_database_connection()
        assert result is False

    def test_check_database_connection_generic_exception(
        self, db_config, mock_connections
    ):
        """Test check_database_connection method with a generic exception."""
        mock_connections.__getitem__.return_value.cursor.side_effect = Exception(
            "Unknown error"
        )
        result = db_config.check_database_connection()
        assert result is False

    def test_all_migrations_applied_true(self, db_config, mock_check_output):
        """Test all_migrations_applied method when all migrations are applied."""
        mock_check_output.return_value = "[X] migration1\n[X] migration2"
        result = db_config.all_migrations_applied()
        assert result is True

        # Verify check_output was called with correct arguments
        expected_command = [
            "python",
            os.path.join(settings.BASE_DIR, "manage.py"),
            "showmigrations",
            "--database",
            "fish",
        ]
        mock_check_output.assert_called_with(
            expected_command, env=db_config.pg_env, text=True
        )

    def test_all_migrations_applied_false(self, db_config, mock_check_output):
        """Test all_migrations_applied method when not all migrations are applied."""
        mock_check_output.return_value = "[X] migration1\n[ ] migration2"
        result = db_config.all_migrations_applied()
        assert result is False

    def test_all_migrations_applied_error(self, db_config, mock_check_output):
        """Test all_migrations_applied method when check_output raises an error."""
        mock_check_output.side_effect = subprocess.CalledProcessError(1, [])
        result = db_config.all_migrations_applied()
        assert result is False

    def test_makemigrations_applied_true(self, db_config, mock_run_command):
        """Test makemigrations_applied method when all makemigrations are applied."""
        result = db_config.makemigrations_applied()
        assert result is True

        # Verify run_command was called with correct arguments
        expected_command = [
            "python",
            os.path.join(settings.BASE_DIR, "manage.py"),
            "makemigrations",
            "--check",
        ]
        mock_run_command.assert_called_with(expected_command)

    def test_makemigrations_applied_false(self, db_config, mock_run_command):
        """Test makemigrations_applied method when not all makemigrations are applied."""
        mock_run_command.side_effect = subprocess.CalledProcessError(1, [])
        result = db_config.makemigrations_applied()
        assert result is False

    def test_str_representation(self, db_config):
        """Test __str__ method."""
        with patch("pprint.pformat") as mock_pformat:
            mock_pformat.return_value = "formatted_output"

            result = str(db_config)

            # Verify pformat was called with correct arguments
            expected_dict = dataclasses.asdict(db_config)
            expected_dict.update(db_dump_path=db_config.db_dump_path)
            mock_pformat.assert_called_with(expected_dict)

            assert result == "formatted_output"

    def test_reset_database_from_dump_with_dump(self, db_config):
        """Test reset_database_from_dump method when dump exists and migrations are applied."""
        type(db_config).dump_exists = PropertyMock(return_value=True)
        with (
            patch.object(db_config, "restore_dump") as mock_restore,
            patch.object(
                db_config, "makemigrations_applied", return_value=True
            ) as mock_makemigrations_applied,
            patch.object(
                db_config, "all_migrations_applied", return_value=True
            ) as mock_all_migrations_applied,
            patch.object(db_config, "makemigrations") as mock_makemigrations,
            patch.object(db_config, "apply_migrations") as mock_apply_migrations,
            patch.object(db_config, "create_dump") as mock_create_dump,
        ):
            db_config.reset_database_from_dump()

            # Verify method calls
            mock_restore.assert_called_once()
            mock_makemigrations_applied.assert_called_once()
            mock_all_migrations_applied.assert_called_once()

            # These should not be called if migrations are applied
            mock_makemigrations.assert_not_called()
            mock_apply_migrations.assert_not_called()
            mock_create_dump.assert_not_called()

    def test_reset_database_from_dump_without_dump_no_input(self, db_config):
        """Test reset_database_from_dump method when dump doesn't exist and no input allowed."""
        type(db_config).dump_exists = PropertyMock(return_value=False)
        type(db_config).database_exists = PropertyMock(return_value=True)
        with (
            patch.object(db_config, "reset_database") as mock_reset,
            patch.object(db_config, "makemigrations") as mock_makemigrations,
            patch.object(db_config, "apply_migrations") as mock_apply_migrations,
            patch.object(db_config, "create_dump") as mock_create_dump,
        ):
            db_config.reset_database_from_dump(allow_input=False)

            # Verify method calls
            mock_reset.assert_not_called()  # Should not be called when allow_input is False
            mock_makemigrations.assert_called_once()
            mock_apply_migrations.assert_called_once()
            mock_create_dump.assert_called_once()

    def test_reset_database_from_dump_without_dump_with_input_yes(self, db_config):
        """Test reset_database_from_dump method when dump doesn't exist, input allowed, user says yes."""
        type(db_config).dump_exists = PropertyMock(return_value=False)
        type(db_config).database_exists = PropertyMock(return_value=True)
        with (
            patch("builtins.input", return_value="y"),
            patch.object(db_config, "reset_database") as mock_reset,
            patch.object(db_config, "makemigrations") as mock_makemigrations,
            patch.object(db_config, "apply_migrations") as mock_apply_migrations,
            patch.object(db_config, "create_dump") as mock_create_dump,
        ):
            db_config.reset_database_from_dump(allow_input=True)

            # Verify method calls
            mock_reset.assert_called_once()
            mock_makemigrations.assert_called_once()
            mock_apply_migrations.assert_called_once()
            mock_create_dump.assert_called_once()

    def test_reset_database_from_dump_without_dump_with_input_no(self, db_config):
        """Test reset_database_from_dump method when dump doesn't exist, input allowed, user says no."""
        type(db_config).dump_exists = PropertyMock(return_value=False)
        type(db_config).database_exists = PropertyMock(return_value=True)
        with (
            patch("builtins.input", return_value="n"),
            patch.object(db_config, "reset_database") as mock_reset,
            patch.object(db_config, "makemigrations") as mock_makemigrations,
            patch.object(db_config, "apply_migrations") as mock_apply_migrations,
            patch.object(db_config, "create_dump") as mock_create_dump,
        ):
            db_config.reset_database_from_dump(allow_input=True)

            # Verify method calls
            mock_reset.assert_not_called()  # Should not be called when user says no
            mock_makemigrations.assert_called_once()
            mock_apply_migrations.assert_called_once()
            mock_create_dump.assert_called_once()

    def test_reset_database_from_dump_without_dump_with_input_no2(self, db_config):
        """Test reset_database_from_dump method when dump doesn't exist, input allowed, user says no."""
        type(db_config).dump_exists = PropertyMock(return_value=False)
        type(db_config).database_exists = PropertyMock(return_value=False)
        with (
            patch("builtins.input", return_value="n"),
            patch.object(db_config, "reset_database") as mock_reset,
            patch.object(db_config, "makemigrations") as mock_makemigrations,
            patch.object(db_config, "apply_migrations") as mock_apply_migrations,
            patch.object(db_config, "create_dump") as mock_create_dump,
        ):
            db_config.reset_database_from_dump(allow_input=True)

            # Verify method calls
            mock_reset.assert_called_once()  # Should not be called when user says no
            mock_makemigrations.assert_called_once()
            mock_apply_migrations.assert_called_once()
            mock_create_dump.assert_called_once()

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from django_infra.env import run_command
from django_infra.env.shell import load_env_val, logger


class TestRunCommand:
    """Test suite for the run_command function."""

    def test_successful_command_no_output(self, capfd):
        """Test that successful commands don't print output."""
        # Run a command that succeeds (echo)
        run_command(["echo", "Hello World"])

        # Check that nothing was printed to stdout
        captured = capfd.readouterr()
        assert captured.out == "", "Successful command should not print output"

    def test_failed_command_prints_output(self, capfd):
        """Test that failed commands print their output."""
        # Run a command that fails (non-existing command)
        with pytest.raises(subprocess.CalledProcessError):
            if os.name == "nt":  # Windows
                run_command(["cmd", "/c", "exit 1"])
            else:  # Unix/Linux/Mac
                run_command(["bash", "-c", "echo 'Error message'; exit 1"])

        # Check that output was printed to stdout
        captured = capfd.readouterr()
        if os.name != "nt":  # Only on Unix systems
            assert "Error message" in captured.out, "Failed command should print output"

    def test_background_process_no_output(self, capfd):
        """Test that background processes don't produce output."""
        # Run a command in the background
        if os.name == "nt":
            run_command(["cmd", "/c", "echo Hello from background"], background=True)
        else:
            run_command(["echo", "Hello from background"], background=True)

        # Give it a moment to complete (though it shouldn't matter)
        import time

        time.sleep(0.1)

        # Check that nothing was printed to stdout
        captured = capfd.readouterr()
        assert captured.out == "", "Background process should not print output"

    def test_with_custom_env(self):
        """Test that custom environment variables are passed correctly."""
        # Create a custom environment with a test variable
        test_env = os.environ.copy()
        test_env["TEST_VAR"] = "test_value"

        # We'll use the command to print the environment variable
        if os.name == "nt":
            command = ["cmd", "/c", "echo %TEST_VAR%"]
        else:
            command = ["bash", "-c", "echo $TEST_VAR"]

        # Mock subprocess to capture the env passed
        with patch("subprocess.Popen") as mock_popen:
            # Configure the mock to return a successful process
            mock_proc = MagicMock()
            mock_proc.returncode = 0
            mock_proc.communicate.return_value = ("", None)
            mock_popen.return_value = mock_proc

            # Run command with custom env
            run_command(command, env=test_env)

            # Check that Popen was called with the correct env
            _, kwargs = mock_popen.call_args
            assert (
                kwargs["env"] == test_env
            ), "Custom environment should be passed to subprocess"

    def test_error_includes_full_output(self):
        """Test that error includes the full command output."""
        # Run a command that produces output and then fails
        multi_line_output = "Line 1\nLine 2\nLine 3\nError!"
        command = (
            ["bash", "-c", f"echo '{multi_line_output}'; exit 1"]
            if os.name != "nt"
            else [
                "cmd",
                "/c",
                "echo Line 1 & echo Line 2 & echo Line 3 & echo Error! & exit 1",
            ]
        )

        # Capture the exception
        with pytest.raises(subprocess.CalledProcessError) as excinfo:
            run_command(command)

        # Check that all output lines are included in the exception
        if os.name != "nt":  # Unix systems
            assert (
                multi_line_output in excinfo.value.output
            ), "Error should include all output lines"

    def test_logger_call(self):
        """Test that logger.info is called with the correct message."""
        with patch.object(logger, "info") as mock_info:
            # Run a simple command
            command = ["echo", "test"]
            try:
                run_command(command)
            except Exception:
                pass  # Ignore any errors for this test

            # Check logger was called with expected message
            mock_info.assert_called_once()
            args, _ = mock_info.call_args
            log_message = args[0]
            assert (
                "EXECUTING: echo test" in log_message
            ), "Logger should record the command being executed"


class TestLoadEnvVal:
    """Test suite for the load_env_val function."""

    def setup_method(self):
        """Setup method to clear environment variables before each test."""
        # Save original environment
        self.original_env = os.environ.copy()

        # Clear test environment variables
        for key in [
            "TEST_VAR",
            "TEST_JSON_VAR",
            "TEST_INVALID_JSON",
            "TEST_VALIDATED_VAR",
        ]:
            if key in os.environ:
                del os.environ[key]

    def teardown_method(self):
        """Teardown method to restore original environment variables."""
        os.environ.clear()
        os.environ.update(self.original_env)

    def test_basic_load(self):
        """Test basic loading of an environment variable."""
        # Set the environment variable
        os.environ["TEST_VAR"] = "test_value"

        # Load the value
        value = load_env_val("TEST_VAR")

        # Check that the value was loaded correctly
        assert value == "test_value", "Should load the value from environment"

    def test_default_value(self):
        """Test that default value is used when variable is not set."""
        # Ensure the variable is not set
        if "TEST_VAR" in os.environ:
            del os.environ["TEST_VAR"]

        # Load with default value
        value = load_env_val("TEST_VAR", default="default_value")

        # Check that the default value was used
        assert (
            value == "default_value"
        ), "Should use the default value when variable not set"

    def test_none_not_allowed(self):
        """Test that error is raised when None is not allowed."""
        # Ensure the variable is not set
        if "TEST_VAR" in os.environ:
            del os.environ["TEST_VAR"]

        # Try to load without allowing None
        with pytest.raises(
            RuntimeError, match="Failed to load env var with key:TEST_VAR"
        ):
            load_env_val("TEST_VAR", allow_none=False)

    def test_none_allowed(self):
        """Test that None is returned when allowed."""
        # Ensure the variable is not set
        if "TEST_VAR" in os.environ:
            del os.environ["TEST_VAR"]

        # Load with None allowed
        value = load_env_val("TEST_VAR", allow_none=True)

        # Check that None was returned
        assert (
            value is None
        ), "Should return None when variable not set and None is allowed"

    def test_json_parsing(self):
        """Test JSON parsing from environment variable."""
        # Set a JSON string in the environment variable
        json_data = '{"key": "value", "list": [1, 2, 3]}'
        os.environ["TEST_JSON_VAR"] = f"_json_{json_data}"

        # Load and parse the JSON
        value = load_env_val("TEST_JSON_VAR")

        # Check that the JSON was parsed correctly
        assert isinstance(value, dict), "Should parse JSON into a dictionary"
        assert value["key"] == "value", "Should correctly parse JSON values"
        assert value["list"] == [1, 2, 3], "Should correctly parse JSON arrays"

    def test_invalid_json(self):
        """Test handling of invalid JSON."""
        # Set an invalid JSON string
        os.environ["TEST_INVALID_JSON"] = "_json_{ invalid json }"

        # Try to load and parse the invalid JSON
        with pytest.raises(
            RuntimeError, match="Failed to load env var with key:TEST_INVALID_JSON"
        ):
            load_env_val("TEST_INVALID_JSON")

    def test_validation_pass(self):
        """Test that validation function works correctly when it passes."""
        # Set a numeric value
        os.environ["TEST_VALIDATED_VAR"] = "42"

        # Load with validation that should pass
        value = load_env_val("TEST_VALIDATED_VAR", validation=lambda x: x.isdigit())

        # Check that the value was loaded correctly
        assert value == "42", "Should load the value when validation passes"

    def test_validation_fail(self):
        """Test that validation function works correctly when it fails."""
        # Set a non-numeric value
        os.environ["TEST_VALIDATED_VAR"] = "not_a_number"

        # Try to load with validation that should fail
        with pytest.raises(RuntimeError) as excinfo:
            load_env_val("TEST_VALIDATED_VAR", validation=lambda x: x.isdigit())

        # Check error message
        assert "Validation error" in str(excinfo.value)

    def test_complex_validation(self):
        """Test complex validation with JSON data."""
        # Set a JSON object with nested structure
        json_data = '{"name": "test", "count": 5, "nested": {"key": "value"}}'
        os.environ["TEST_JSON_VAR"] = f"_json_{json_data}"

        # Define a complex validation function
        def validate_structure(obj):
            return (
                isinstance(obj, dict)
                and "name" in obj
                and "count" in obj
                and isinstance(obj["count"], int)
                and obj["count"] > 0
                and "nested" in obj
                and isinstance(obj["nested"], dict)
            )

        # Load with complex validation
        value = load_env_val("TEST_JSON_VAR", validation=validate_structure)

        # Check that the value was loaded and validated correctly
        assert (
            value["name"] == "test"
        ), "Should correctly load and validate complex JSON"
        assert (
            value["nested"]["key"] == "value"
        ), "Should correctly handle nested JSON structures"

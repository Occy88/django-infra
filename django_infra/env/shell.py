import json
import logging
import os
import subprocess
import typing

logger = logging.getLogger(__file__)


def get_failure_msg(key, default, var, validation, allow_none):
    return "\n".join(
        [
            f"Failed to load env var with key:{key},",
            f" default:{default}, ",
            f"loaded val: {var}",
            f"validation:{validation} ",
            f"allow_none:{allow_none}",
        ]
    )


def load_env_val(
    key: str, default=None, allow_none=False, validation: typing.Callable = None
) -> typing.Any:
    """

    Parameters
    ----------
    key
    default: default value if not defined
    allow_none: is it ok for val not to be defined
    validation: validation function for loaded variable, e.g. lambda x: isinstance(x,dict)

    Returns
    -------

    """
    var = os.environ.get(key, default=default)
    if var is not None and isinstance(var, str):
        if var.startswith("_json_"):
            try:
                var = json.loads(var[6:])
            except json.JSONDecodeError:
                raise RuntimeError(
                    get_failure_msg(key, default, var, validation, allow_none)
                )
    elif var is None and not allow_none:
        raise RuntimeError(get_failure_msg(key, default, var, validation, allow_none))
    if validation and not validation(var):
        raise RuntimeError(
            f"Validation error: "
            f"{get_failure_msg(key, default, var, validation, allow_none)}"
        )
    return var


def run_command(
    command: str | typing.List[str], env: dict = None, background=False
) -> subprocess.Popen[str]:
    """
    Execute a command with output in a fixed-height window.
    Prints all output only on failure, otherwise remains silent.
    Raises CalledProcessError on failure with last output lines.
    """
    if isinstance(command, str):
        command = command.split(" ")

    command_style = "\033[38;5;45m"
    exec_command = " ".join(list(map(str, command)))

    logger.info(f"[ {command_style} EXECUTING: {exec_command}\033[0m ]")

    # Configure process parameters based on background flag
    stdout = subprocess.PIPE
    stderr = subprocess.STDOUT
    if background:
        stdout = subprocess.DEVNULL
        stderr = subprocess.DEVNULL

    # Initialize process once
    proc = subprocess.Popen(
        command,
        stdout=stdout,
        stderr=stderr,
        text=True,
        bufsize=1,
        env=env,
    )

    # For background processes, don't wait
    if background:
        return proc

    # For foreground processes, capture output and check return code
    stdout_data, _ = proc.communicate()
    output_lines = stdout_data.splitlines() if stdout_data else []

    # If command failed, print all captured output and raise exception
    if proc.returncode != 0:
        for line in output_lines:
            print(line)
        raise subprocess.CalledProcessError(
            proc.returncode, command, output=stdout_data
        )
    return proc

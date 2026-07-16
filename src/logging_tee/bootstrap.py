"""Startup support used by the :mod:`logging_tee.cli` launcher."""

import logging
import os
import subprocess

from .tee import setup_logger

_DISABLE_SITE_HOOK = "LOGGING_TEE_DISABLE_SITE_HOOK"
_LOG_FILE = "LOGGING_TEE_LOG_FILE"
_LOG_LEVEL = "LOGGING_TEE_LOG_LEVEL"


def _captured_stdout(arguments, keyword_arguments):
    """Return the ``stdout`` argument passed to :class:`subprocess.Popen`."""
    if "stdout" in keyword_arguments:
        return keyword_arguments["stdout"]
    # Popen's positional arguments are args, bufsize, executable, stdin, stdout.
    return arguments[4] if len(arguments) > 4 else None


def _disable_hook_for_captured_children():
    """Keep captured child stdout available for machine-readable protocols."""
    original_popen = subprocess.Popen

    class LoggingTeePopen(original_popen):
        """A subclass so libraries such as Ray can subclass ``Popen`` too."""

        def __init__(self, *arguments, **keyword_arguments):
            if _captured_stdout(arguments, keyword_arguments) == subprocess.PIPE:
                environment = os.environ.copy() if keyword_arguments.get("env") is None else keyword_arguments["env"].copy()
                environment[_DISABLE_SITE_HOOK] = "1"
                keyword_arguments["env"] = environment
            super().__init__(*arguments, **keyword_arguments)

    subprocess.Popen = LoggingTeePopen


def install_from_environment():
    """Configure logging for a launched program unless this is a captured child."""
    if os.environ.pop(_DISABLE_SITE_HOOK, None):
        return

    # vLLM otherwise writes preformatted records to stdout, causing a duplicate
    # logging-tee prefix. Do not override an explicit user configuration.
    os.environ.setdefault("VLLM_CONFIGURE_LOGGING", "0")
    setup_logger(
        log_file=os.environ[_LOG_FILE],
        level=getattr(logging, os.environ[_LOG_LEVEL]),
        file_mode="a",
        capture_print=True,
        capture_stderr=True,
        capture_uncaught_exceptions=True,
        auto_log_tqdm=True,
    )
    _disable_hook_for_captured_children()

"""Command-line launcher for logging a Python program without editing it."""

import argparse
from datetime import datetime
import fcntl
import os
from pathlib import Path
import pty
import re
import select
import subprocess
import sys
import tempfile
import textwrap
import termios


_SITECUSTOMIZE = """\
import logging
import os

from logging_tee import setup_logger

setup_logger(
    log_file=os.environ["LOGGING_TEE_LOG_FILE"],
    level=getattr(logging, os.environ["LOGGING_TEE_LOG_LEVEL"]),
    file_mode="a",
    capture_print=True,
    capture_stderr=True,
    capture_uncaught_exceptions=True,
    auto_log_tqdm=True,
)
"""

_FORMATTED_LOG_LINE_RE = re.compile(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} ")
_ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")


def _parse_level(value):
    level = value.upper()
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise argparse.ArgumentTypeError("must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
    return level


def _parser():
    parser = argparse.ArgumentParser(
        description="Run a Python command while teeing stdout, stderr, logging, and tqdm snapshots to a log file."
    )
    parser.add_argument(
        "--log-file",
        type=Path,
        help="Log destination (default: YYYYMMDD-HHMMSS.log in the current directory).",
    )
    parser.add_argument(
        "--level",
        type=_parse_level,
        default="INFO",
        help="Minimum log level to store (default: INFO).",
    )
    parser.add_argument("command", nargs=argparse.REMAINDER, help="Python command, for example: python demo.py")
    return parser


def _prepare_environment(log_file, level, site_dir):
    environment = os.environ.copy()
    environment["LOGGING_TEE_LOG_FILE"] = str(log_file)
    environment["LOGGING_TEE_LOG_LEVEL"] = level

    existing_pythonpath = environment.get("PYTHONPATH")
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(site_dir), existing_pythonpath) if part
    )
    return environment


def _is_python_command(command):
    executable = Path(command[0]).name.lower()
    return executable.startswith("python") or executable.startswith("pypy")


def _append_shell_line(stream, line):
    """Store one shell-only line without duplicating child logging records."""
    if not line or _FORMATTED_LOG_LINE_RE.search(line):
        return
    stream.write(f"{datetime.now():%Y-%m-%d %H:%M:%S,%f}"[:-3])
    stream.write(f" root INFO      {line}\n")
    stream.flush()


def _attach_controlling_terminal():
    """Make the pseudo-terminal the command's controlling terminal."""
    os.setsid()
    fcntl.ioctl(0, termios.TIOCSCTTY, 0)


def _copy_terminal_size(source_fd, destination_fd):
    """Give the child PTY the same dimensions as the user-facing terminal."""
    try:
        window_size = fcntl.ioctl(source_fd, termios.TIOCGWINSZ, b"\0" * 8)
        fcntl.ioctl(destination_fd, termios.TIOCSWINSZ, window_size)
    except OSError:
        # The caller may be redirected; the PTY's default size is still usable.
        pass


def _write_terminal_bytes(terminal_fd, data):
    """Relay terminal-control bytes unchanged, including tqdm cursor updates."""
    if terminal_fd is None:
        sys.__stderr__.buffer.write(data)
        sys.__stderr__.buffer.flush()
        return

    view = memoryview(data)
    while view:
        written = os.write(terminal_fd, view)
        view = view[written:]


def _run_interactive_command(command, environment, log_file):
    """Run a non-Python command on a pseudo-terminal and retain its shell output."""
    master_fd, slave_fd = pty.openpty()
    try:
        terminal_fd = os.open("/dev/tty", os.O_WRONLY)
    except OSError:
        terminal_fd = None
    try:
        if terminal_fd is not None:
            _copy_terminal_size(terminal_fd, slave_fd)
        else:
            _copy_terminal_size(sys.__stderr__.fileno(), slave_fd)
    except (AttributeError, OSError):
        pass
    partial_line = ""
    reached_eof = False
    try:
        process = subprocess.Popen(
            command,
            env=environment,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            preexec_fn=_attach_controlling_terminal,
        )
    finally:
        os.close(slave_fd)

    try:
        with log_file.open("a", encoding="utf-8") as log_stream:
            while True:
                ready, _, _ = select.select([master_fd], [], [], 0.1)
                if ready:
                    try:
                        data = os.read(master_fd, 4096)
                    except OSError:
                        data = b""
                    if data:
                        # Keep the raw bytes intact: tqdm's live display uses
                        # carriage returns and ANSI cursor-control sequences.
                        _write_terminal_bytes(terminal_fd, data)
                        text = data.decode(errors="replace")
                        partial_line += text
                        while "\n" in partial_line:
                            line, partial_line = partial_line.split("\n", 1)
                            # A pseudo-terminal translates ordinary newlines to
                            # CRLF. Only a carriage return within the line (rather
                            # than its CRLF terminator) is a tqdm-style redraw.
                            is_terminal_redraw = "\r" in line.rstrip("\r")
                            visible_line = _ANSI_ESCAPE_RE.sub("", line).rstrip("\r")
                            if not is_terminal_redraw:
                                _append_shell_line(log_stream, visible_line)
                    else:
                        reached_eof = True
                if process.poll() is not None and (reached_eof or not ready):
                    break

            is_terminal_redraw = "\r" in partial_line.rstrip("\r")
            visible_line = _ANSI_ESCAPE_RE.sub("", partial_line).rstrip("\r")
            if not is_terminal_redraw:
                _append_shell_line(log_stream, visible_line)
    finally:
        os.close(master_fd)
        if terminal_fd is not None:
            os.close(terminal_fd)
    return process.returncode


def main(argv=None):
    """Run the requested command and return its exit status."""
    args = _parser().parse_args(argv)
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        _parser().error("a command is required; for example: logging-tee python demo.py")

    log_file = args.log_file or Path.cwd() / f"{datetime.now():%Y%m%d-%H%M%S}.log"
    log_file = log_file.expanduser().resolve()
    log_file.parent.mkdir(parents=True, exist_ok=True)
    # Truncate once before the shell wrapper can emit output. The Python startup
    # hook then uses append mode, preserving output that preceded the child.
    log_file.write_text("", encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="logging-tee-") as temporary_directory:
        site_dir = Path(temporary_directory)
        (site_dir / "sitecustomize.py").write_text(
            textwrap.dedent(_SITECUSTOMIZE), encoding="utf-8"
        )
        environment = _prepare_environment(log_file, args.level, site_dir)
        if _is_python_command(command):
            result = subprocess.run(command, env=environment)
            returncode = result.returncode
        else:
            returncode = _run_interactive_command(command, environment, log_file)

    if returncode < 0:
        return 128 - returncode
    return returncode


if __name__ == "__main__":
    sys.exit(main())
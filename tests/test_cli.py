import subprocess
import sys
from pathlib import Path

from logging_tee.tee import LineBufferLoggerWriter


class _InteractiveStream:
    def __init__(self):
        self.writes = []
        self.was_flushed = False
        self.encoding = "utf-8"

    def write(self, message):
        self.writes.append(message)

    def flush(self):
        self.was_flushed = True

    def isatty(self):
        return True


def test_stderr_writer_mirrors_raw_tqdm_output_to_the_terminal():
    terminal = _InteractiveStream()
    writer = LineBufferLoggerWriter(
        logger=__import__("logging").getLogger("test-stderr-tee"),
        level=__import__("logging").ERROR,
        stream=terminal,
    )

    writer.write("\rprogress: 50%")
    writer.flush()

    assert terminal.writes == ["\rprogress: 50%"]
    assert terminal.was_flushed
    assert writer.isatty()
    assert writer.encoding == "utf-8"


def test_cli_captures_an_unmodified_python_program(tmp_path):
    """The launcher configures the child interpreter before its script runs."""
    script = tmp_path / "demo.py"
    script.write_text(
        "import logging\nimport sys\nprint('standard output')\n"
        "logging.warning('standard logging')\n"
        "sys.stderr.write('standard error\\n')\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "logging_tee.cli",
            "--log-file",
            "run.log",
            "python",
            str(script),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    contents = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert "standard output" in contents
    assert "standard logging" in contents
    assert "standard error" in contents


def test_cli_preserves_the_child_exit_status(tmp_path):
    script = tmp_path / "failure.py"
    script.write_text("raise SystemExit(7)\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, "-m", "logging_tee.cli", "python", str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 7
    assert list(tmp_path.glob("*.log"))


def test_cli_discards_tqdm_terminal_control_sequences(tmp_path):
    script = tmp_path / "control.py"
    script.write_text(
        "import sys\nsys.stderr.write('\\x1b[A\\n')\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "logging_tee.cli",
            "--log-file",
            "run.log",
            "python",
            str(script),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "\x1b[A" not in (tmp_path / "run.log").read_text(encoding="utf-8")


def test_cli_captures_shell_script_output(tmp_path):
    script = tmp_path / "demo.sh"
    script.write_text("#!/usr/bin/env bash\necho 'shell output'\n", encoding="utf-8")
    script.chmod(0o755)

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "logging_tee.cli",
            "--log-file",
            "run.log",
            str(script),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "shell output" in result.stdout
    assert "shell output" in (tmp_path / "run.log").read_text(encoding="utf-8")


def test_cli_captures_shell_output_with_pseudoterminal_line_endings(tmp_path):
    script = tmp_path / "echo.sh"
    script.write_text("#!/usr/bin/env bash\necho 'Hello, world!'\n", encoding="utf-8")
    script.chmod(0o755)

    result = subprocess.run(
        [sys.executable, "-m", "logging_tee.cli", "--log-file", "run.log", str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "Hello, world!" in (tmp_path / "run.log").read_text(encoding="utf-8")


def test_cli_preserves_shell_output_before_a_python_child(tmp_path):
    script = tmp_path / "wrapper.sh"
    script.write_text(
        "#!/usr/bin/env bash\necho 'before python'\npython -c \"print('from python')\"\n",
        encoding="utf-8",
    )
    script.chmod(0o755)

    result = subprocess.run(
        [sys.executable, "-m", "logging_tee.cli", "--log-file", "run.log", str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    contents = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert contents.index("before python") < contents.index("from python")


def test_cli_shell_child_detects_an_interactive_terminal(tmp_path):
    script = tmp_path / "terminal.sh"
    script.write_text(
        "#!/usr/bin/env bash\npython -c \"import sys; print(sys.stderr.isatty())\"\n",
        encoding="utf-8",
    )
    script.chmod(0o755)

    result = subprocess.run(
        [sys.executable, "-m", "logging_tee.cli", "--log-file", "run.log", str(script)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "True" in result.stderr
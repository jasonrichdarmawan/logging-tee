from pathlib import Path
import re
import subprocess
import sys

from logging_tee.tee import ColorFormatter, LineBufferLoggerWriter, TqdmLoggingHandler


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


def test_color_formatter_colors_fields_and_level_by_severity():
    logging = __import__("logging")
    formatter = ColorFormatter()
    info = logging.LogRecord("worker", logging.INFO, "", 0, "ready", (), None)
    error = logging.LogRecord("worker", logging.ERROR, "", 0, "failed", (), None)

    info_text = formatter.format(info)
    error_text = formatter.format(error)

    assert "\x1b[90m" in info_text
    assert "\x1b[35mworker\x1b[0m" in info_text
    assert "\x1b[32mINFO" in info_text
    assert "\x1b[37mready\x1b[0m" in info_text
    assert "\x1b[31mERROR" in error_text


def test_tqdm_handler_writes_colored_records_to_interactive_terminal():
    logging = __import__("logging")
    terminal = _InteractiveStream()
    handler = TqdmLoggingHandler(stream=terminal)
    handler.setFormatter(ColorFormatter())

    handler.emit(logging.LogRecord("worker", logging.WARNING, "", 0, "careful", (), None))

    output = "".join(terminal.writes)
    assert "\x1b[33mWARNING" in output
    assert "\x1b[37mcareful\x1b[0m" in output


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


def test_writer_delegates_stream_capabilities_without_mirroring_output():
    terminal = _InteractiveStream()
    terminal.fileno = lambda: 42
    writer = LineBufferLoggerWriter(
        logger=__import__("logging").getLogger("test-stdout-tee"),
        level=__import__("logging").INFO,
        delegate_stream=terminal,
    )

    writer.write("captured output\n")

    assert terminal.writes == []
    assert writer.fileno() == 42
    assert writer.encoding == "utf-8"
    assert writer.isatty()


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


def test_cli_writes_timestamped_log_to_requested_directory(tmp_path):
    log_dir = tmp_path / "nested" / "logs"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "logging_tee.cli",
            "--log-dir",
            str(log_dir),
            "python",
            "-c",
            "print('timestamped output')",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    logs = list(log_dir.glob("*.log"))
    assert len(logs) == 1
    assert re.fullmatch(r"\d{8}-\d{6}\.log", logs[0].name)
    assert "timestamped output" in logs[0].read_text(encoding="utf-8")


def test_cli_preserves_third_party_stream_handler_records(tmp_path):
    """Formatted library stderr records retain their logger name and severity."""
    script = tmp_path / "library_logging.py"
    script.write_text(
        "import logging\n"
        "import sys\n"
        "logger = logging.getLogger('ContinuousBatchingLogger')\n"
        "logger.setLevel(logging.INFO)\n"
        "logger.propagate = False\n"
        "handler = logging.StreamHandler(sys.stderr)\n"
        "handler.setFormatter(logging.Formatter(\n"
        "    '%(asctime)s - %(name)s - %(levelname)s - %(message)s'\n"
        "))\n"
        "logger.addHandler(handler)\n"
        "logger.info('cache initialized')\n"
        "logger.warning('warming up')\n",
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

    assert result.returncode == 0, result.stderr
    contents = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert "ContinuousBatchingLogger INFO      cache initialized" in contents
    assert "ContinuousBatchingLogger WARNING   warming up" in contents
    assert "root ERROR" not in contents
    assert contents.count("cache initialized") == 1
    assert contents.count("warming up") == 1


def test_cli_stdout_supports_fileno_for_vllm_style_fd_redirection(tmp_path):
    """vLLM temporarily redirects the stdout file descriptor while starting workers."""
    script = tmp_path / "fileno.py"
    script.write_text(
        "import os\n"
        "import sys\n"
        "stdout_fd = sys.stdout.fileno()\n"
        "saved_fd = os.dup(stdout_fd)\n"
        "try:\n"
        "    with open(os.devnull, 'w') as devnull:\n"
        "        os.dup2(devnull.fileno(), stdout_fd)\n"
        "finally:\n"
        "    os.dup2(saved_fd, stdout_fd)\n"
        "    os.close(saved_fd)\n"
        "print('stdout fileno works')\n",
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

    assert result.returncode == 0, result.stderr
    assert "stdout fileno works" in (tmp_path / "run.log").read_text(encoding="utf-8")


def test_cli_does_not_intercept_a_captured_python_subprocess_stdout(tmp_path):
    """Protocol output from Python subprocesses must remain available to callers."""
    script = tmp_path / "parent.py"
    script.write_text(
        "import subprocess\nimport sys\n"
        "result = subprocess.run(\n"
        "    [sys.executable, '-c', \"import json; print(json.dumps({'ok': True}))\"],\n"
        "    capture_output=True, text=True, check=True,\n"
        ")\n"
        "assert result.stdout == '{\\\"ok\\\": true}\\n', result.stdout\n"
        "print('captured subprocess output:', result.stdout.strip())\n",
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

    assert result.returncode == 0, result.stderr
    contents = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert 'captured subprocess output: {"ok": true}' in contents


def test_cli_keeps_subprocess_popen_subclassable(tmp_path):
    """Libraries such as Ray subclass Popen during their import process."""
    script = tmp_path / "parent.py"
    script.write_text(
        "import subprocess\n"
        "class ChildPopen(subprocess.Popen):\n"
        "    pass\n"
        "assert issubclass(ChildPopen, subprocess.Popen)\n"
        "print('Popen remains subclassable')\n",
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

    assert result.returncode == 0, result.stderr
    assert "Popen remains subclassable" in (tmp_path / "run.log").read_text(encoding="utf-8")


def test_cli_logs_share_tqdm_stderr_stream(tmp_path):
    """The console handler must use the stream tqdm uses for live bars."""
    script = tmp_path / "stream.py"
    script.write_text(
        "import logging\n"
        "import sys\n"
        "from tqdm import tqdm\n"
        "handler = logging.getLogger().handlers[-1]\n"
        "assert handler.stream is sys.stderr\n"
        "for _ in tqdm(range(1), desc='bar'):\n"
        "    logging.info('while progress is active')\n",
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

    assert result.returncode == 0, result.stderr
    assert "while progress is active" in (tmp_path / "run.log").read_text(encoding="utf-8")


def test_cli_hides_tqdm_snapshots_from_the_terminal(tmp_path):
    """Live bars belong on the terminal; snapshots belong only in the log file."""
    script = tmp_path / "progress.py"
    script.write_text(
        "from tqdm import tqdm\n"
        "for _ in tqdm(range(1), desc='bar'):\n"
        "    pass\n",
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

    assert result.returncode == 0, result.stderr
    assert "tqdm[bar]" in (tmp_path / "run.log").read_text(encoding="utf-8")
    assert "tqdm[bar]" not in result.stderr


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
    assert "True" in result.stdout
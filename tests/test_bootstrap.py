import os
import subprocess

from logging_tee.bootstrap import _captured_stdout


def test_captured_stdout_reads_keyword_and_positional_arguments():
    assert _captured_stdout((), {"stdout": subprocess.PIPE}) is subprocess.PIPE
    assert _captured_stdout((None, None, None, None, subprocess.PIPE), {}) is subprocess.PIPE


def test_bootstrap_popen_remains_subclassable_in_a_launched_program(tmp_path):
    script = tmp_path / "program.py"
    script.write_text(
        "import subprocess\n"
        "class ChildPopen(subprocess.Popen):\n"
        "    pass\n"
        "assert issubclass(ChildPopen, subprocess.Popen)\n",
        encoding="utf-8",
    )

    environment = os.environ.copy()
    environment["LOGGING_TEE_LOG_FILE"] = str(tmp_path / "run.log")
    environment["LOGGING_TEE_LOG_LEVEL"] = "INFO"
    environment["PYTHONPATH"] = os.pathsep.join(
        part for part in (str(tmp_path), environment.get("PYTHONPATH")) if part
    )
    (tmp_path / "sitecustomize.py").write_text(
        "from logging_tee.bootstrap import install_from_environment\ninstall_from_environment()\n",
        encoding="utf-8",
    )

    result = subprocess.run([os.sys.executable, str(script)], env=environment, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
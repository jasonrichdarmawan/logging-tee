import logging
from pathlib import Path
from tqdm import tqdm

from logging_tee import setup_logger
from examples.otherfile import do_something_with_progress


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_demo_style_logging_preserves_multiline_and_named_logger_output(tmp_path):
    """
    Regression test for the behavior demonstrated in `examples/demo.py`.

    This keeps the important guarantees of the demo:
    - root logger writes to the file
    - named loggers propagate to the configured root logger
    - `print(...)` is captured into the log file
    - multi-line messages are split into separate formatted log lines
    """
    log_path = tmp_path / "output.log"

    logger = setup_logger(
        log_file=str(log_path),
        level=logging.DEBUG,
        capture_uncaught_exceptions=False,
        auto_log_tqdm=False,
    )
    logger2 = logging.getLogger("test_logger2")

    logger.info("Processing item %d", 1)
    print("from print statement")
    print("multiple lines\nfrom print statement 2")
    logger.debug("Single line")
    logger.debug("Multiple lines:\nnext line")
    logger.debug("Another single line")
    logger.debug("Multiple lines:\n%s", "next line\nnext line 2")
    logger.warning("Warning message\nwith multiple lines\nand should be logged properly.")
    logger.error("Error message\nwith multiple lines\nand should be logged properly.")
    logger2.info("Logger2 info message\nwith multiple lines\nand should be logged properly.")

    contents = _read_text(log_path)

    assert "Processing item 1" in contents
    assert "from print statement" in contents
    assert "multiple lines" in contents
    assert "from print statement 2" in contents
    assert "Single line" in contents
    assert "Another single line" in contents
    assert "Warning message" in contents
    assert "and should be logged properly." in contents
    assert "Logger2 info message" in contents

    assert "DEBUG     Single line" in contents
    assert "WARNING   Warning message" in contents
    assert "ERROR     Error message" in contents


def test_demo_style_uncaught_exception_is_logged(tmp_path):
    """
    Regression test for the demo's uncaught-exception logging behavior.
    """
    log_path = tmp_path / "output.log"

    setup_logger(
        log_file=str(log_path),
        level=logging.DEBUG,
        capture_print=False,
        capture_uncaught_exceptions=True,
        auto_log_tqdm=False,
    )

    try:
        raise ValueError("This is an error message\nwith multiple lines\nand should be logged properly.")
    except ValueError as exc:
        sys_excepthook = __import__("sys").excepthook
        sys_excepthook(type(exc), exc, exc.__traceback__)

    contents = _read_text(log_path)
    assert "Uncaught exception" in contents
    assert "ValueError: This is an error message" in contents
    assert "with multiple lines" in contents
    assert "and should be logged properly." in contents


def test_demo_style_tqdm_progress_is_logged(tmp_path):
    """
    Regression test for tqdm snapshot logging used by the demo.
    """
    log_path = tmp_path / "output.log"

    logger = setup_logger(
        log_file=str(log_path),
        level=logging.DEBUG,
        capture_print=False,
        capture_uncaught_exceptions=False,
        auto_log_tqdm=True,
        tqdm_log_interval_seconds=0,
    )

    for _ in tqdm(range(2), desc="Processing"):
        pass

    contents = _read_text(log_path)
    assert "tqdm[Processing] progress:" in contents or "tqdm[Processing] done:" in contents
    assert "2/2 (100.0%)" in contents

    # Keep a direct logger call so the test also confirms ordinary log records still work.
    logger.info("done with tqdm")
    contents = _read_text(log_path)
    assert "done with tqdm" in contents


def test_demo_style_tqdm_uses_calling_module_logger(tmp_path):
    """
    tqdm snapshot logs should be attributed to the module that created the bar,
    not always the root logger.
    """
    log_path = tmp_path / "output.log"

    setup_logger(
        log_file=str(log_path),
        level=logging.DEBUG,
        capture_print=False,
        capture_uncaught_exceptions=False,
        auto_log_tqdm=True,
        tqdm_log_interval_seconds=0,
    )

    do_something_with_progress()

    contents = _read_text(log_path)
    assert "examples.otherfile INFO      Processing item 0" in contents
    assert "examples.otherfile INFO      Processing item 1" in contents
    assert "examples.otherfile INFO      tqdm[Processing items] done:" in contents


def test_tqdm_snapshot_clamps_overshoot_to_total(tmp_path):
    """
    If a bar overshoots its total before close, the logged snapshot should still
    report at most the declared total instead of values above 100%.
    """
    log_path = tmp_path / "output.log"

    setup_logger(
        log_file=str(log_path),
        level=logging.DEBUG,
        capture_print=False,
        capture_uncaught_exceptions=False,
        auto_log_tqdm=True,
        tqdm_log_interval_seconds=0,
    )

    pbar = tqdm(total=17, desc="Overall Progress")
    pbar.update(16)
    pbar.update(16)
    pbar.close()

    contents = _read_text(log_path)
    assert "tqdm[Overall Progress]" in contents
    assert "17/17 (100.0%)" in contents
    assert "32/17" not in contents


def test_tqdm_snapshot_includes_postfix(tmp_path):
    """
    Postfix values set on a tqdm bar should be preserved in the logged snapshot.
    """
    log_path = tmp_path / "output.log"

    setup_logger(
        log_file=str(log_path),
        level=logging.DEBUG,
        capture_print=False,
        capture_uncaught_exceptions=False,
        auto_log_tqdm=True,
        tqdm_log_interval_seconds=0,
    )

    additional_info = 2
    pbar = tqdm(range(3), total=3, desc="Outer Progress")
    for _ in pbar:
        additional_info *= 2
        pbar.set_postfix({"additional_info": f"{additional_info}"})

    contents = _read_text(log_path)
    assert "tqdm[Outer Progress]" in contents
    assert "additional_info" in contents
    assert "8" in contents or "16" in contents

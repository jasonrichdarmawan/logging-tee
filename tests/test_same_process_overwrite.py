import logging
from pathlib import Path

from logging_tee.tee import setup_logger


def _read_text(path: Path) -> str:
	return path.read_text(encoding="utf-8")


def test_setup_logger_does_not_truncate_within_same_process(tmp_path):
	"""
	Purpose:
		Reproduce the suspected bug where the same FileHandler gets closed during one
		Python process, then later receives another log record and silently reopens
		the log file.

	Why explicitly close the handler here:
		In normal logging, a handler can be closed by cleanup/finalization code while
		still remaining attached to the logger object. If another log record is sent
		after that, `emit()` can run again. In this package, `emit()` checks whether
		`self.stream is None` and, if so, calls `_open()` again.

	Why `logger.debug(...)` still writes after `file_handler.close()`:
		Closing the handler closes its file stream, but does not remove the handler
		from `logger.handlers`. So the logger still tries to use that handler for the
		next log record. That next log call is what exercises the reopen path.

	What this test is trying to prove:
		- First run of the handler should use mode="w" to clear old logs from a
		  previous program run.
		- Any reopen later in the same process should append, not truncate again.
		If this test fails, it means the handler is deleting earlier logs during the
		same Python process.
	"""
	log_path = tmp_path / "output.log"

	logger = setup_logger(
		log_file=str(log_path),
		level=logging.DEBUG,
		capture_print=False,
		capture_uncaught_exceptions=False,
		auto_log_tqdm=False,
	)

	logger.info("before-close")
	first_contents = _read_text(log_path)
	assert "before-close" in first_contents

	file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
	assert len(file_handlers) == 1
	file_handler = file_handlers[0]

	file_handler.close()

	logger.debug("after-reopen")
	second_contents = _read_text(log_path)

	assert "before-close" in second_contents
	assert "after-reopen" in second_contents


def test_plain_logging_filehandler_in_w_mode_retruncates_after_close(tmp_path):
	"""
	Control test:
		Shows baseline behavior of the standard library handler once it has been
		closed and then removed from the logger. After removal, later log calls do
		not reach that handler anymore, so the file remains unchanged.
	"""
	log_path = tmp_path / "plain.log"

	logger = logging.getLogger(f"plain-{id(tmp_path)}")
	logger.handlers.clear()
	logger.setLevel(logging.DEBUG)
	logger.propagate = False

	handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
	handler.setFormatter(logging.Formatter("%(message)s"))
	logger.addHandler(handler)

	logger.info("before-close")
	assert "before-close" in _read_text(log_path)

	handler.close()
	logger.removeHandler(handler)
	logger.info("after-reopen")

	contents = _read_text(log_path)
	assert contents == "before-close\n"

	logger.handlers.clear()

# %%

import logging
import os
import sys
import time
import inspect
import re
import threading
import tqdm.std as tqdm_std
import tqdm.auto as tqdm_auto
from tqdm.auto import tqdm

from .records import iter_formatted_lines


_ANSI_ESCAPE_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
_ANSI_RESET = "\x1b[0m"
_LEVEL_COLORS = {
    logging.DEBUG: "\x1b[36m",
    logging.INFO: "\x1b[32m",
    logging.WARNING: "\x1b[33m",
    logging.ERROR: "\x1b[31m",
    logging.CRITICAL: "\x1b[1;31m",
}
_stream_handler_state = threading.local()


def _install_stream_handler_context():
    """Expose the LogRecord currently being rendered by standard stream handlers."""
    if getattr(logging.StreamHandler.emit, "_logging_tee_wrapped", False):
        return

    original_emit = logging.StreamHandler.emit

    def emit(handler, record):
        previous_record = getattr(_stream_handler_state, "record", None)
        _stream_handler_state.record = record
        try:
            return original_emit(handler, record)
        finally:
            _stream_handler_state.record = previous_record

    emit._logging_tee_wrapped = True
    logging.StreamHandler.emit = emit


class ColorFormatter(logging.Formatter):
    """Color each field while preserving the plain formatter's layout."""

    def format(self, record):
        asctime = self.formatTime(record, self.datefmt)
        level_color = _LEVEL_COLORS.get(record.levelno, "\x1b[37m")
        return (
            f"\x1b[90m{asctime}{_ANSI_RESET} "
            f"\x1b[35m{record.name}{_ANSI_RESET} "
            f"{level_color}{record.levelname:<9}{_ANSI_RESET} "
            f"\x1b[37m{record.getMessage()}{_ANSI_RESET}"
        )


class TqdmLoggingHandler(logging.Handler):
    def __init__(self, level=logging.NOTSET, stream=None):
        """
        Why `sys.stderr`: Because tqdm and logging are sharing terminal space, `stderr` is the safer channel.
        """
        super().__init__(level)
        self.stream = sys.__stderr__ if stream is None else stream
        self._terminal_stream = getattr(self.stream, "stream", self.stream)

    def emit(self, record):
        """
        Normal `StreamHandler` writes directly to terminal, which can overwrite or break tqdm lines.
        Clear and redraw bars using their wrapped stderr stream, but write records
        to the underlying terminal stream to avoid logging the handler's own
        output recursively.
        """
        if getattr(record, "_logging_tee_skip_handlers", False):
            return
        try:
            with tqdm.external_write_mode(file=self.stream):
                for line in iter_formatted_lines(record, self.formatter):
                    self._terminal_stream.write(line + "\n")
                self._terminal_stream.flush()
        except Exception:
            self.handleError(record)

    def filter(self, record):
        """Keep auto-generated tqdm snapshots in the log file only."""
        return not getattr(record, "logging_tee_tqdm_snapshot", False)


class FileHandler(logging.FileHandler):
    def __init__(self, filename, mode="a", encoding=None, delay=False, errors=None):
        self._initial_mode = mode
        self._reopen_mode = "a" if mode == "w" else mode
        self._has_opened = False
        super().__init__(filename, mode=mode, encoding=encoding, delay=delay, errors=errors)
        self._has_opened = getattr(self, "stream", None) is not None

    def _open(self):
        mode = self._initial_mode if not self._has_opened else self._reopen_mode
        stream = open(self.baseFilename, mode, encoding=self.encoding, errors=self.errors)
        self._has_opened = True
        return stream

    def emit(self, record):
        if getattr(record, "_logging_tee_skip_handlers", False):
            return
        try:
            lines = iter_formatted_lines(record, self.formatter)

            self.acquire()
            try:
                if self.stream is None:
                    self.stream = self._open()
                for line in lines:
                    self.stream.write(line + self.terminator)
                self.flush()
            finally:
                self.release()
        except Exception:
            self.handleError(record)


class LineBufferLoggerWriter:
    def __init__(self, logger, level, stream=None, delegate_stream=None, record_handler=None):
        self.logger = logger
        self.level = level
        self.stream = stream
        self._delegate_stream = stream if delegate_stream is None else delegate_stream
        self._record_handler = record_handler
        self.buffer = ""
        self._contains_carriage_return = False

    @staticmethod
    def _visible_text(line):
        """Remove terminal control sequences before recording redirected output."""
        return _ANSI_ESCAPE_RE.sub("", line)

    def write(self, message):
        """
        `print()` and many libraries call `stream.write(...)`.
        It buffers text until it sees `\n`, then logs complete lines with `self.logger.log(self.level, line)`.
        """
        if not message:
            return 0

        record = getattr(_stream_handler_state, "record", None)
        if record is not None and self._record_handler is not None:
            if not getattr(record, "_logging_tee_stream_captured", False):
                record._logging_tee_stream_captured = True
                record._logging_tee_skip_handlers = True
                self._record_handler(record)
            return len(message)

        if self.stream is not None:
            self.stream.write(message)
        self._contains_carriage_return = self._contains_carriage_return or "\r" in message
        self.buffer += message
        while "\n" in self.buffer:
            # Why buffer: `print()`/writers may send partial chunks, and logging partial fragments would create broken lines.
            line, self.buffer = self.buffer.split("\n", 1)
            line = line.rstrip("\r")
            visible_line = self._visible_text(line)
            # tqdm redraws its visual progress bar using carriage returns. Its
            # structured snapshots are logged separately. Nested bars also emit
            # ANSI cursor controls (for example, ``\x1b[A``); discard lines
            # that consist only of these controls.
            if visible_line and not self._contains_carriage_return:
                self.logger.log(self.level, visible_line)
            self._contains_carriage_return = "\r" in self.buffer
        return len(message)

    def flush(self):
        """
        Some code calls `flush()` explicitly (or `print(.., flush=True)`).
        This forces any leftover buffered text (without trailing newline) to be logged.
        Without it, the last partial line might never appear in logs.
        """
        if self.buffer:
            line = self.buffer.rstrip("\r")
            visible_line = self._visible_text(line)
            if visible_line and not self._contains_carriage_return:
                self.logger.log(self.level, visible_line)
            self.buffer = ""
            self._contains_carriage_return = False

        if self.stream is not None:
            self.stream.flush()

    def isatty(self):
        """
        Many tools check `stream.isatty()` to decide whether to use terminal UI behaviors (colors, progress animations, carriage returns).
        stdout remains non-interactive, but stderr delegates to the original
        terminal so tqdm can keep its normal interactive progress display.
        """
        return self._delegate_stream.isatty() if self._delegate_stream is not None else False

    def __getattr__(self, name):
        """Expose stream capabilities such as ``fileno`` and ``encoding``."""
        if self._delegate_stream is not None:
            return getattr(self._delegate_stream, name)
        raise AttributeError(name)


def _log_tqdm_snapshot(logger, pbar, level=logging.INFO, event="progress"):
    if pbar.disable:
        return

    n = min(pbar.n, pbar.total) if pbar.total is not None else pbar.n
    total = pbar.total
    elapsed = pbar.format_dict.get("elapsed", 0.0) or 0.0
    rate = pbar.format_dict.get("rate", None)

    if rate is None:
        rate = (n / elapsed) if elapsed > 0 else 0.0

    percent = (100.0 * n / total) if total else 0.0
    remaining_units = max(total - n, 0) if total is not None else None
    remaining = (remaining_units / rate) if (remaining_units is not None and rate > 0) else float("inf")
    remaining_text = "unknown" if remaining == float("inf") else f"{remaining:.1f}s"
    elapsed_text = f"{elapsed:.1f}s"
    postfix = getattr(pbar, "postfix", None)
    postfix_text = f", {postfix}" if postfix else ""

    desc = (getattr(pbar, "desc", "") or "tqdm").strip() or "tqdm"
    logger.log(
        level,
        "tqdm[%s] %s: %d/%d (%.1f%%), elapsed %s, %.2f it/s, ETA %s%s",
        desc,
        event,
        n,
        total if total is not None else -1,
        percent,
        elapsed_text,
        rate,
        remaining_text,
        postfix_text,
        extra={"logging_tee_tqdm_snapshot": True},
    )


def _infer_tqdm_logger(default_logger):
    current_frame = inspect.currentframe()
    try:
        frame = current_frame.f_back if current_frame is not None else None
        while frame is not None:
            module_name = frame.f_globals.get("__name__")
            if module_name and not module_name.startswith("logging_tee") and not module_name.startswith("tqdm"):
                return logging.getLogger(module_name)
            frame = frame.f_back
    finally:
        del current_frame

    return default_logger


def install_tqdm_logging(logger, interval_seconds=0.5, level=logging.INFO):
    cls = tqdm_std.tqdm

    if not hasattr(cls, "_auto_log_original_init"):
        cls._auto_log_original_init = cls.__init__
        cls._auto_log_original_update = cls.update
        cls._auto_log_original_close = cls.close

        def _patched_init(self, *args, **kwargs):
            auto_assign_position = getattr(cls, "_auto_assign_position", False)
            if auto_assign_position and kwargs.get("position", None) is None:
                active_positions = set()
                for inst in list(getattr(cls, "_instances", [])):
                    pos = getattr(inst, "pos", None)
                    if pos is None:
                        continue
                    try:
                        active_positions.add(abs(int(pos)))
                    except (TypeError, ValueError):
                        continue

                if active_positions:
                    kwargs["position"] = max(active_positions) + 1

            default_logger = getattr(cls, "_auto_log_logger", None)
            self._auto_log_logger = _infer_tqdm_logger(default_logger)

            cls._auto_log_original_init(self, *args, **kwargs)
            self._auto_log_last_snapshot = time.monotonic()

        def _patched_update(self, n=1):
            result = cls._auto_log_original_update(self, n)

            if self.disable:
                return result

            logger_obj = getattr(self, "_auto_log_logger", getattr(cls, "_auto_log_logger", None))
            interval = getattr(cls, "_auto_log_interval", 0.5)
            log_level = getattr(cls, "_auto_log_level", logging.INFO)

            if logger_obj is None:
                return result

            now = time.monotonic()
            last = getattr(self, "_auto_log_last_snapshot", now)
            is_final_step = self.total is not None and self.n >= self.total
            if is_final_step or (now - last) >= interval:
                _log_tqdm_snapshot(logger=logger_obj, pbar=self, level=log_level)
                self._auto_log_last_snapshot = now

            return result

        def _patched_close(self):
            try:
                logger_obj = getattr(self, "_auto_log_logger", getattr(cls, "_auto_log_logger", None))
                log_level = getattr(cls, "_auto_log_level", logging.INFO)
                if logger_obj is not None:
                    _log_tqdm_snapshot(logger=logger_obj, pbar=self, level=log_level, event="done")
            finally:
                return cls._auto_log_original_close(self)

        cls.__init__ = _patched_init
        cls.update = _patched_update
        cls.close = _patched_close

    cls._auto_log_logger = logger
    cls._auto_log_interval = interval_seconds
    cls._auto_log_level = level
    cls._auto_assign_position = True

    tqdm_auto.tqdm = cls
    globals()["tqdm"] = cls


def setup_logger(
    log_file,
    name=None,
    level=logging.INFO,
    file_mode="w",
    capture_print=True,
    capture_stderr=False,
    capture_uncaught_exceptions=True,
    auto_log_tqdm=True,
    tqdm_log_interval_seconds=1,
    tqdm_auto_assign_position=True,
):
    logger = logging.getLogger(name)
    _install_stream_handler_context()
    logger.setLevel(level)
    # Useful when setup code runs multiple times, otherwise handlers stack and the same
    # log can print/write multiple times.
    logger.handlers.clear()
    # Stops this logger from forwarding records to its parent logger (often the root logger).
    # If `True`, the message is handled by this logger's handlers and parent handlers,
    # which often causes double printing.
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s %(name)s %(levelname)-9s %(message)s")

    dirname = os.path.dirname(log_file)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    file_handler = FileHandler(log_file, mode=file_mode, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(fmt)
    logger.addHandler(file_handler)

    capture_handlers = [file_handler]

    def _handle_stream_record(record):
        record_copy = logging.makeLogRecord(record.__dict__.copy())
        record_copy._logging_tee_skip_handlers = False
        for handler in capture_handlers:
            if record_copy.levelno >= handler.level:
                handler.handle(record_copy)

    if capture_print:
        # replaces `sys.stdout` with `LineBuferLoggerWriter`, so `print(...)` becomes logger `INFO`
        sys.stdout = LineBufferLoggerWriter(
            logger=logger,
            level=logging.INFO,
            delegate_stream=sys.__stdout__,
            record_handler=_handle_stream_record,
        )

    if capture_stderr:
        # Keep logging handlers on sys.__stderr__ to avoid recursion. The writer
        # mirrors raw stderr there so terminal programs such as tqdm retain their
        # interactive rendering, while clean non-control lines are also logged.
        sys.stderr = LineBufferLoggerWriter(
            logger=logger,
            level=logging.ERROR,
            stream=sys.__stderr__,
            record_handler=_handle_stream_record,
        )

    # Use the same stream as tqdm. When stderr is wrapped above, passing the
    # wrapper to tqdm.write() lets tqdm clear and redraw active bars around log
    # records, keeping the live display at the bottom of the terminal.
    console_handler = TqdmLoggingHandler(level=level, stream=sys.stderr)
    terminal_stream = console_handler._terminal_stream
    use_color = os.environ.get("NO_COLOR") is None and getattr(terminal_stream, "isatty", lambda: False)()
    console_handler.setFormatter(ColorFormatter() if use_color else fmt)
    logger.addHandler(console_handler)
    capture_handlers.append(console_handler)

    if capture_uncaught_exceptions:
        def _excepthook(exc_type, exc_value, exc_traceback):
            logger.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

        sys.excepthook = _excepthook

    if auto_log_tqdm:
        install_tqdm_logging(
            logger,
            interval_seconds=tqdm_log_interval_seconds,
            level=logging.INFO,
        )
        tqdm_std.tqdm._auto_assign_position = tqdm_auto_assign_position

    return logger

# %%

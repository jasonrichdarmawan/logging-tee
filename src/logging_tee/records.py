"""Helpers for rendering logging records safely to line-oriented outputs."""

import copy
import logging


def iter_formatted_lines(record, formatter=None):
    """Yield a formatted line for each message, exception, and stack line."""
    formatter = formatter or logging.Formatter("%(message)s")
    base_record = copy.copy(record)
    base_record.args = None
    base_record.exc_info = None
    base_record.exc_text = None
    base_record.stack_info = None

    for message_line in record.getMessage().splitlines() or [record.getMessage()]:
        line_record = copy.copy(base_record)
        line_record.msg = message_line
        yield formatter.format(line_record)

    if record.exc_info:
        for exception_line in formatter.formatException(record.exc_info).splitlines():
            line_record = copy.copy(base_record)
            line_record.msg = exception_line
            yield formatter.format(line_record)

    if record.stack_info:
        for stack_line in formatter.formatStack(record.stack_info).splitlines():
            line_record = copy.copy(base_record)
            line_record.msg = stack_line
            yield formatter.format(line_record)

# -*- coding: utf-8 -*-
"""Small multi-sink reporting helper for pyRevit scripts."""

import datetime
import io
import os
import re
import sys
import time

try:
    text_type = unicode  # type: ignore[name-defined]
except NameError:
    text_type = str

_LOG_RETENTION_DAYS = 30


def _to_text(value):
    """Convert any value to text without raising."""
    if value is None:
        return text_type("")
    if isinstance(value, text_type):
        return value
    try:
        return text_type(value)
    except Exception:
        try:
            return text_type(str(value))
        except Exception:
            return text_type("<unprintable>")


def _slugify(value):
    value = _to_text(value).strip()
    if not value:
        return "report"
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value)
    value = value.strip("._-")
    return value or "report"


def _html_escape(value):
    value = _to_text(value)
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _cleanup_old_logs(folder, max_age_days=_LOG_RETENTION_DAYS):
    """Delete log files older than *max_age_days* from *folder*."""
    try:
        cutoff = time.time() - max_age_days * 86400
        for name in os.listdir(folder):
            if not name.endswith(".log"):
                continue
            path = os.path.join(folder, name)
            try:
                if os.path.getmtime(path) < cutoff:
                    os.remove(path)
            except Exception:
                pass
    except Exception:
        pass


def _build_default_log_path(title=None, log_stem=None):
    stem = _slugify(log_stem or title or "report")
    root = os.environ.get("LOCALAPPDATA") or os.environ.get("TEMP") or os.path.expanduser("~")
    folder = os.path.join(root, "RaisedFloor.extension", "logs")
    try:
        if not os.path.isdir(folder):
            os.makedirs(folder)
    except Exception:
        return None

    _cleanup_old_logs(folder)

    timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return os.path.join(folder, "{}-{}.log".format(stem, timestamp))


class ScriptReporter(object):
    """Write the same report line to output, logger, and optional text file."""

    def __init__(self, title=None, output=None, logger=None, log_path=None):
        self.title = _to_text(title or "")
        self.output = output
        self.logger = logger
        self.log_path = log_path
        self.lines = []
        self._file_handle = None
        self._start = datetime.datetime.now()

        if self.output is not None and self.title:
            try:
                self.output.set_title(self.title)
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self):
        """Flush and close the log file handle if open."""
        if self._file_handle is not None:
            try:
                self._file_handle.close()
            except Exception:
                pass
            self._file_handle = None

    @classmethod
    def from_pyrevit(cls, title=None, log_stem=None, persist_to_file=True):
        output = None
        logger = None
        try:
            from pyrevit import script  # type: ignore

            try:
                output = script.get_output()
            except Exception:
                output = None
            try:
                logger = script.get_logger()
            except Exception:
                logger = None
        except Exception:
            output = None
            logger = None

        log_path = None
        if persist_to_file:
            log_path = _build_default_log_path(title=title, log_stem=log_stem)

        return cls(title=title, output=output, logger=logger, log_path=log_path)

    def get_sink_labels(self):
        labels = []
        if self.output is not None:
            labels.append("pyRevit output")
        if self.logger is not None:
            labels.append("pyRevit Logs")
        if self.log_path:
            labels.append("text log")
        return labels

    def elapsed(self):
        """Return elapsed time since reporter creation as a formatted string."""
        delta = datetime.datetime.now() - self._start
        total_seconds = int(delta.total_seconds())
        if total_seconds < 60:
            return "{}s".format(total_seconds)
        minutes, seconds = divmod(total_seconds, 60)
        return "{}m {}s".format(minutes, seconds)

    # -- public write methods ------------------------------------------------

    def write(self, text="", level="info"):
        text = _to_text(text)
        level = _to_text(level or "info").lower()
        self.lines.append((level, text))

        self._write_output(level, text)
        self._write_logger(level, text)
        self._write_file(level, text)

        if self.output is None and self.logger is None:
            self._write_stdout(text)

        return text

    def info(self, text=""):
        return self.write(text, level="info")

    def warning(self, text=""):
        return self.write(text, level="warn")

    def error(self, text=""):
        return self.write(text, level="error")

    def debug(self, text=""):
        return self.write(text, level="debug")

    def separator(self, char="-", length=60):
        self.write(_to_text(char) * int(length))

    def stage(self, title):
        self.separator()
        self.write(title)
        self.separator()

    def finish(self):
        """Print a summary of counts by level and close resources."""
        counts = {}
        for level, _ in self.lines:
            counts[level] = counts.get(level, 0) + 1
        self.separator()
        self.write(
            "Done in {}: {} info, {} warnings, {} errors".format(
                self.elapsed(),
                counts.get("info", 0),
                counts.get("warn", 0),
                counts.get("error", 0),
            )
        )
        self.close()

    def write_table(self, headers, rows):
        """Write a simple aligned text table.

        *headers* is a sequence of column names, *rows* is a sequence of
        sequences (one per row) with the same length as *headers*.
        """
        if not headers:
            return
        cols = len(headers)
        str_rows = []
        for row in rows:
            str_rows.append([_to_text(cell) for cell in row])

        widths = [len(_to_text(h)) for h in headers]
        for row in str_rows:
            for i in range(min(cols, len(row))):
                widths[i] = max(widths[i], len(row[i]))

        def _fmt(cells):
            parts = []
            for i, cell in enumerate(cells):
                parts.append(_to_text(cell).ljust(widths[i]))
            return "  ".join(parts)

        self.write(_fmt(headers))
        self.write("  ".join("-" * w for w in widths))
        for row in str_rows:
            self.write(_fmt(row))

    # -- private sink methods ------------------------------------------------

    def _write_output(self, level, text):
        if self.output is None:
            return False

        if hasattr(self.output, "print_html"):
            try:
                level_style = {
                    "warn": "color:#8a5a00;",
                    "warning": "color:#8a5a00;",
                    "error": "color:#9b1c1c;",
                    "debug": "color:#666666;",
                }.get(level, "")
                html = (
                    "<pre style='margin:0; white-space:pre-wrap; {}'>{}</pre>".format(
                        level_style,
                        _html_escape(text),
                    )
                )
                self.output.print_html(html)
                return True
            except Exception:
                pass

        if hasattr(self.output, "write"):
            try:
                self.output.write(text + "\n")
                return True
            except Exception:
                pass

        if hasattr(self.output, "print_md"):
            try:
                self.output.print_md(text)
                return True
            except Exception:
                pass

        return False

    def _write_logger(self, level, text):
        if self.logger is None:
            return False

        method_name = {
            "warn": "warning",
            "warning": "warning",
            "error": "error",
            "debug": "debug",
        }.get(level, "info")
        logger_method = getattr(self.logger, method_name, None)
        if logger_method is None:
            logger_method = getattr(self.logger, "info", None)
        if logger_method is None:
            return False

        try:
            logger_method(text)
            return True
        except Exception:
            return False

    def _open_file(self):
        """Lazily open the log file on first write."""
        if self._file_handle is not None:
            return self._file_handle
        if not self.log_path:
            return None
        try:
            self._file_handle = io.open(self.log_path, "a", encoding="utf-8")
        except Exception:
            self._file_handle = None
        return self._file_handle

    def _write_file(self, level, text):
        if not self.log_path:
            return False

        handle = self._open_file()
        if handle is None:
            return False

        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        line = "[{}] [{}] {}".format(timestamp, level.upper(), text)
        try:
            handle.write(_to_text(line))
            handle.write(u"\n")
            handle.flush()
            return True
        except Exception:
            return False

    def _write_stdout(self, text):
        try:
            sys.stdout.write(_to_text(text) + u"\n")
            return True
        except Exception:
            return False

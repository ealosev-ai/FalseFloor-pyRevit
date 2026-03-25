# -*- coding: utf-8 -*-
"""Pure tests for the multi-sink reporting helper."""

import datetime
import os
import tempfile

import rf_reporting
from rf_reporting import ScriptReporter, _build_default_log_path, _slugify, _to_text


# ---------------------------------------------------------------------------
# Dummy / mock helpers
# ---------------------------------------------------------------------------


class _DummyOutput(object):
    """Simulates pyRevit output with print_html, print_md, and write."""

    def __init__(self, support_print_md=True):
        self.title = None
        self.lines = []
        self.md_lines = []
        self.html_lines = []
        self._support_print_md = support_print_md

    def set_title(self, title):
        self.title = title

    def print_html(self, text):
        self.html_lines.append(text)

    def print_md(self, text):
        if not self._support_print_md:
            raise AttributeError("no print_md")
        self.md_lines.append(text)

    def write(self, text):
        self.lines.append(text)


class _WriteOnlyOutput(object):
    """Output that only has write(), no print_md()."""

    def __init__(self):
        self.title = None
        self.lines = []

    def set_title(self, title):
        self.title = title

    def write(self, text):
        self.lines.append(text)


class _MarkdownOnlyOutput(object):
    """Output that only has print_md(), no write()."""

    def __init__(self):
        self.title = None
        self.md_lines = []

    def set_title(self, title):
        self.title = title

    def print_md(self, text):
        self.md_lines.append(text)


class _HtmlOnlyOutput(object):
    """Output that only has print_html()."""

    def __init__(self):
        self.title = None
        self.html_lines = []

    def set_title(self, title):
        self.title = title

    def print_html(self, text):
        self.html_lines.append(text)


class _DummyLogger(object):
    def __init__(self):
        self.infos = []
        self.warnings = []
        self.errors = []
        self.debugs = []

    def info(self, text):
        self.infos.append(text)

    def warning(self, text):
        self.warnings.append(text)

    def error(self, text):
        self.errors.append(text)

    def debug(self, text):
        self.debugs.append(text)


class _DummyStream(object):
    def __init__(self, chunks):
        self._chunks = chunks

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def write(self, text):
        self._chunks.append(text)

    def flush(self):
        pass

    def close(self):
        pass


# ---------------------------------------------------------------------------
# _to_text
# ---------------------------------------------------------------------------


def test_to_text_none():
    assert _to_text(None) == ""


def test_to_text_string():
    assert _to_text("hello") == "hello"


def test_to_text_int():
    assert _to_text(42) == "42"


def test_to_text_float():
    assert _to_text(3.14) == "3.14"


def test_to_text_bool():
    assert _to_text(True) == "True"


def test_to_text_list():
    assert _to_text([1, 2]) == "[1, 2]"


# ---------------------------------------------------------------------------
# _slugify
# ---------------------------------------------------------------------------


def test_slugify_normal():
    assert _slugify("My Report") == "My_Report"


def test_slugify_empty():
    assert _slugify("") == "report"


def test_slugify_none():
    assert _slugify(None) == "report"


def test_slugify_special_chars():
    assert _slugify("a/b\\c:d") == "a_b_c_d"


def test_slugify_only_special():
    assert _slugify("...") == "report"


def test_slugify_preserves_dots_and_hyphens():
    assert _slugify("my-file.v2") == "my-file.v2"


# ---------------------------------------------------------------------------
# ScriptReporter: core write + sinks
# ---------------------------------------------------------------------------


def test_script_reporter_writes_to_output_logger_and_file(monkeypatch):
    output = _DummyOutput()
    logger = _DummyLogger()
    file_chunks = []

    def _fake_open(path, mode, encoding=None):
        assert path == "C:\\temp\\report.log"
        assert mode == "a"
        assert encoding == "utf-8"
        return _DummyStream(file_chunks)

    monkeypatch.setattr(rf_reporting.io, "open", _fake_open)

    reporter = ScriptReporter(
        title="Smoke",
        output=output,
        logger=logger,
        log_path="C:\\temp\\report.log",
    )

    reporter.stage("Stage")
    reporter.write("Warning line", level="warn")
    reporter.write("Error line", level="error")

    assert output.title == "Smoke"
    assert any("Stage" in line for line in output.html_lines)
    assert "Stage" in logger.infos
    assert "Warning line" in logger.warnings
    assert "Error line" in logger.errors

    file_text = "".join(file_chunks)
    assert "[INFO] Stage" in file_text
    assert "[WARN] Warning line" in file_text
    assert "[ERROR] Error line" in file_text

    reporter.close()


def test_write_only_output_fallback():
    """When output has no print_md, falls back to write()."""
    output = _WriteOnlyOutput()
    reporter = ScriptReporter(title="Test", output=output)
    reporter.write("hello")
    assert any("hello" in line for line in output.lines)


def test_print_html_preferred_over_other_methods():
    """When output has print_html, it is used before print_md/write."""
    output = _DummyOutput(support_print_md=True)
    reporter = ScriptReporter(output=output)
    reporter.write("markdown line")
    assert any("markdown line" in line for line in output.html_lines)
    assert len(output.md_lines) == 0
    assert len(output.lines) == 0


def test_print_html_only_output_supported():
    output = _HtmlOnlyOutput()
    reporter = ScriptReporter(output=output)
    reporter.write("html line")
    assert any("html line" in line for line in output.html_lines)


def test_print_md_fallback_when_write_missing():
    """When output lacks write(), print_md() is still supported."""
    output = _MarkdownOnlyOutput()
    reporter = ScriptReporter(output=output)
    reporter.write("markdown fallback")
    assert "markdown fallback" in output.md_lines


def test_script_reporter_sink_labels_reflect_available_targets():
    reporter = ScriptReporter(
        title="Smoke",
        output=_DummyOutput(),
        logger=_DummyLogger(),
        log_path="C:\\temp\\rf.log",
    )

    assert reporter.get_sink_labels() == [
        "pyRevit output",
        "pyRevit Logs",
        "text log",
    ]


# ---------------------------------------------------------------------------
# separator / stage
# ---------------------------------------------------------------------------


def test_separator_default():
    reporter = ScriptReporter()
    reporter.separator()
    assert len(reporter.lines) == 1
    assert reporter.lines[0] == ("info", "-" * 60)


def test_separator_custom():
    reporter = ScriptReporter()
    reporter.separator(char="=", length=10)
    assert reporter.lines[0] == ("info", "=" * 10)


def test_stage_produces_three_lines():
    reporter = ScriptReporter()
    reporter.stage("Build")
    assert len(reporter.lines) == 3
    assert reporter.lines[1] == ("info", "Build")
    assert reporter.lines[0][1] == "-" * 60
    assert reporter.lines[2][1] == "-" * 60


# ---------------------------------------------------------------------------
# convenience methods
# ---------------------------------------------------------------------------


def test_info_method():
    logger = _DummyLogger()
    reporter = ScriptReporter(logger=logger)
    reporter.info("msg")
    assert "msg" in logger.infos


def test_warning_method():
    logger = _DummyLogger()
    reporter = ScriptReporter(logger=logger)
    reporter.warning("oops")
    assert "oops" in logger.warnings


def test_error_method():
    logger = _DummyLogger()
    reporter = ScriptReporter(logger=logger)
    reporter.error("fail")
    assert "fail" in logger.errors


def test_debug_method():
    logger = _DummyLogger()
    reporter = ScriptReporter(logger=logger)
    reporter.debug("trace")
    assert "trace" in logger.debugs


# ---------------------------------------------------------------------------
# stdout fallback
# ---------------------------------------------------------------------------


def test_stdout_fallback_when_no_output_or_logger(monkeypatch, capsys):
    reporter = ScriptReporter()
    reporter.write("fallback line")
    captured = capsys.readouterr()
    assert "fallback line" in captured.out


# ---------------------------------------------------------------------------
# context manager
# ---------------------------------------------------------------------------


def test_context_manager(monkeypatch):
    file_chunks = []

    def _fake_open(path, mode, encoding=None):
        return _DummyStream(file_chunks)

    monkeypatch.setattr(rf_reporting.io, "open", _fake_open)

    with ScriptReporter(log_path="C:\\temp\\ctx.log") as reporter:
        reporter.write("inside")

    assert len(file_chunks) > 0
    assert reporter._file_handle is None  # closed by __exit__


# ---------------------------------------------------------------------------
# elapsed
# ---------------------------------------------------------------------------


def test_elapsed_returns_formatted_string(monkeypatch):
    reporter = ScriptReporter()
    # Force start to 90 seconds ago
    reporter._start = datetime.datetime.now() - datetime.timedelta(seconds=90)
    result = reporter.elapsed()
    assert result == "1m 30s"


def test_elapsed_seconds_only():
    reporter = ScriptReporter()
    reporter._start = datetime.datetime.now() - datetime.timedelta(seconds=5)
    assert reporter.elapsed() == "5s"


# ---------------------------------------------------------------------------
# finish
# ---------------------------------------------------------------------------


def test_finish_writes_summary_and_closes(monkeypatch):
    file_chunks = []

    def _fake_open(path, mode, encoding=None):
        return _DummyStream(file_chunks)

    monkeypatch.setattr(rf_reporting.io, "open", _fake_open)

    reporter = ScriptReporter(log_path="C:\\temp\\fin.log")
    reporter.info("ok")
    reporter.warning("hmm")
    reporter.error("bad")
    reporter.error("worse")
    reporter.finish()

    last_line = reporter.lines[-1][1]
    assert "1 info" in last_line
    assert "1 warnings" in last_line
    assert "2 errors" in last_line
    assert reporter._file_handle is None


# ---------------------------------------------------------------------------
# write_table
# ---------------------------------------------------------------------------


def test_write_table_basic():
    reporter = ScriptReporter()
    reporter.write_table(["Name", "Value"], [["a", "1"], ["bb", "22"]])
    texts = [line[1] for line in reporter.lines]
    # header + separator + 2 rows = 4 lines
    assert len(texts) == 4
    assert "Name" in texts[0]
    assert "Value" in texts[0]
    assert "----" in texts[1]
    assert "a" in texts[2]
    assert "bb" in texts[3]


def test_write_table_empty_headers():
    reporter = ScriptReporter()
    reporter.write_table([], [["a"]])
    assert len(reporter.lines) == 0


# ---------------------------------------------------------------------------
# log rotation
# ---------------------------------------------------------------------------


def test_cleanup_old_logs():
    """Old .log files are removed, recent ones are kept."""
    import shutil
    import time as _time

    folder = os.path.join(tempfile.gettempdir(), "rf_reporting_test_cleanup")
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)

    try:
        old_log = os.path.join(folder, "old-20200101-120000.log")
        with open(old_log, "w") as f:
            f.write("old")
        old_mtime = _time.time() - 60 * 86400
        os.utime(old_log, (old_mtime, old_mtime))

        new_log = os.path.join(folder, "new-20260325-120000.log")
        with open(new_log, "w") as f:
            f.write("new")

        not_a_log = os.path.join(folder, "keep.txt")
        with open(not_a_log, "w") as f:
            f.write("keep")

        rf_reporting._cleanup_old_logs(folder, max_age_days=30)

        assert not os.path.exists(old_log)
        assert os.path.exists(new_log)
        assert os.path.exists(not_a_log)
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def test_build_default_log_path_prefers_localappdata(monkeypatch):
    folder_root = os.path.join(tempfile.gettempdir(), "rf_reporting_localappdata")
    monkeypatch.setenv("LOCALAPPDATA", folder_root)
    monkeypatch.delenv("TEMP", raising=False)

    path = _build_default_log_path(title="Smoke", log_stem="migrate_guids")

    assert path.startswith(os.path.join(folder_root, "RaisedFloor.extension", "logs"))
    assert path.endswith(".log")

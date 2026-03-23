# -*- coding: utf-8 -*-
"""Run RaisedFloor in-Revit test contour."""

import os
import sys

from pyrevit import forms  # type: ignore


def _get_extension_root():
    path = __file__
    for _ in range(5):
        path = os.path.dirname(path)
    return path


try:
    ext_root = _get_extension_root()
    if ext_root not in sys.path:
        sys.path.insert(0, ext_root)

    import run_tests  # type: ignore

    results = run_tests.run_tests()

    passed = int(results.get("passed", 0)) if isinstance(results, dict) else 0
    failed = int(results.get("failed", 0)) if isinstance(results, dict) else 0
    total = passed + failed

    lines = [
        "Результаты тестов RaisedFloor",
        "",
        "Пройдено: {}".format(passed),
        "Провалено: {}".format(failed),
        "Всего: {}".format(total),
    ]

    errors = results.get("errors", []) if isinstance(results, dict) else []
    if errors:
        lines.append("")
        lines.append("Ошибки:")
        for test_name, error in errors[:10]:
            lines.append("- {}: {}".format(test_name, error))
        if len(errors) > 10:
            lines.append("- ... и еще {} ошибок".format(len(errors) - 10))

    forms.alert("\n".join(lines), title="RaisedFloor Tests")
except Exception as ex:
    forms.alert("Не удалось запустить тесты:\n{}".format(str(ex)), title="RaisedFloor")

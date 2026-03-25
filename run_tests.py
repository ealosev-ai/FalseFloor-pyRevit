# -*- coding: utf-8 -*-
"""Legacy entrypoint preserved for pyRevit Run Script usage."""

import os
import sys


def _get_extension_root():
    return os.path.dirname(os.path.abspath(__file__))


def run_tests():
    """Run the grouped Revit smoke runner with legacy summary shape."""
    root = _get_extension_root()
    lib_dir = os.path.join(root, "lib")
    for path in (root, lib_dir):
        if path not in sys.path:
            sys.path.insert(0, path)

    import revit_smoke  # type: ignore

    result = revit_smoke.run_smoke(extension_root=root)
    counts = result.get("counts", {}) if isinstance(result, dict) else {}
    groups = result.get("groups", []) if isinstance(result, dict) else []

    errors = []
    for group in groups:
        group_name = group.get("name", "Unknown")
        for item in group.get("items", []):
            if item.get("status") != "fail":
                continue
            label = item.get("label", "check")
            details = item.get("details", "")
            message = "{}: {}".format(label, details) if details else label
            errors.append((group_name, message))

    return {
        "passed": int(counts.get("pass", 0)),
        "failed": int(counts.get("fail", 0)),
        "warnings": int(counts.get("warn", 0)),
        "errors": errors,
        "groups": groups,
    }


if __name__ == "__main__":
    run_tests()

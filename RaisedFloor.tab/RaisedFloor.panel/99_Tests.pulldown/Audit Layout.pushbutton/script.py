# -*- coding: utf-8 -*-
"""Audit a selected RaisedFloor slab and its stored layout ownership."""

import os
import sys

from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import FloorOrPartSelectionFilter, get_source_floor  # type: ignore
from floor_i18n import tr  # type: ignore
from pyrevit import forms  # type: ignore
from revit_context import get_active_view, get_doc, get_uidoc  # type: ignore
from rf_reporting import ScriptReporter  # type: ignore

TITLE = "Аудит раскладки"


class _Cancel(Exception):
    pass


def _get_extension_root():
    path = __file__
    for _ in range(5):
        path = os.path.dirname(path)
    return path


try:
    ext_root = _get_extension_root()
    lib_dir = os.path.join(ext_root, "lib")
    for path in (ext_root, lib_dir):
        if path not in sys.path:
            sys.path.insert(0, path)

    from floor_audit import run_floor_layout_audit  # type: ignore

    doc = get_doc()
    uidoc = get_uidoc()
    view = get_active_view()

    if not doc or not uidoc:
        raise Exception(tr("source_floor_not_found"))

    if doc.IsFamilyDocument:
        raise Exception("Audit Layout works only in a project document.")

    pick_filter = FloorOrPartSelectionFilter()
    try:
        ref = uidoc.Selection.PickObject(
            ObjectType.Element,
            pick_filter,
            tr("pick_floor_or_part_prompt"),
        )
    except OperationCanceledException:
        raise _Cancel()

    picked_el = doc.GetElement(ref.ElementId)
    floor = get_source_floor(picked_el)
    if not floor:
        raise Exception(tr("source_floor_not_found"))

    reporter = ScriptReporter.from_pyrevit(title=TITLE, log_stem="audit_layout")
    reporter.stage("RaisedFloor Layout Audit")
    if view is not None:
        reporter.info("Active view: {}".format(getattr(view, "Name", "<unnamed>")))

    report = run_floor_layout_audit(doc, floor)
    report.render(reporter, TITLE)
    reporter.finish()

    counts = report.counts()
    lines = [
        "Аудит завершён.",
        "pass={pass_count}, fail={fail_count}, warn={warn_count}, info={info_count}".format(
            pass_count=counts.get("pass", 0),
            fail_count=counts.get("fail", 0),
            warn_count=counts.get("warn", 0),
            info_count=counts.get("info", 0),
        ),
    ]
    if reporter.log_path:
        lines.append("Log: {}".format(reporter.log_path))
    forms.alert("\n".join(lines), title=TITLE)

except _Cancel:
    pass
except Exception as ex:
    forms.alert(tr("error_inline_fmt", error=str(ex)), title=TITLE)

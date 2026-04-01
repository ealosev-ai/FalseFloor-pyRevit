# -*- coding: utf-8 -*-
"""Grouped Revit-hosted smoke runner for RaisedFloor."""

import os
import sys

from rf_param_schema import (  # type: ignore
    RFFamilies,
    RF_ALL_FAMILY_PARAM_NAMES,
    RF_PROJECT_PARAM_NAMES,
    RF_STRINGER_FAMILY_PARAM_NAMES,
    RF_SUPPORT_FAMILY_PARAM_NAMES,
    RF_TILE_FAMILY_PARAM_NAMES,
    RFParams as P,
)
from rf_reporting import ScriptReporter  # type: ignore

PROJECT_PARAM_NAMES = RF_PROJECT_PARAM_NAMES
REQUIRED_FAMILY_NAMES = (RFFamilies.TILE, RFFamilies.STRINGER, RFFamilies.SUPPORT)
_TILE_PARAMS = set(RF_TILE_FAMILY_PARAM_NAMES)
_STRINGER_PARAMS = set(RF_STRINGER_FAMILY_PARAM_NAMES)
_SUPPORT_PARAMS = set(RF_SUPPORT_FAMILY_PARAM_NAMES)
_ALL_FAMILY_PARAMS = set(RF_ALL_FAMILY_PARAM_NAMES)


def get_extension_root(start_path):
    """Walk up until we find the extension root containing lib and RaisedFloor.tab."""
    current = os.path.abspath(start_path)
    if os.path.isfile(current):
        current = os.path.dirname(current)

    while True:
        if os.path.isdir(os.path.join(current, "lib")) and os.path.isdir(
            os.path.join(current, "RaisedFloor.tab")
        ):
            return current

        parent = os.path.dirname(current)
        if parent == current:
            raise ValueError(
                "Could not detect extension root from '{}'".format(start_path)
            )
        current = parent


def get_expected_family_param_names(family_name):
    """Return the RF parameter set expected for a family name."""
    name_upper = (family_name or "").upper()
    if "TILE" in name_upper or "VENT" in name_upper or "GRILL" in name_upper:
        return set(_TILE_PARAMS)
    if "STRINGER" in name_upper:
        return set(_STRINGER_PARAMS)
    if "SUPPORT" in name_upper:
        return set(_SUPPORT_PARAMS)
    return set(_ALL_FAMILY_PARAMS)


class SmokeReport(object):
    """Small grouped report with stable text rendering."""

    def __init__(self):
        self.groups = []

    def add(self, group, status, label, details=None):
        for entry in self.groups:
            if entry["name"] == group:
                entry["items"].append(
                    {"status": status, "label": label, "details": details or ""}
                )
                return
        self.groups.append(
            {
                "name": group,
                "items": [{"status": status, "label": label, "details": details or ""}],
            }
        )

    def counts(self):
        result = {"pass": 0, "fail": 0, "warn": 0, "info": 0}
        for group in self.groups:
            for item in group["items"]:
                key = item["status"].lower()
                result[key] = result.get(key, 0) + 1
        return result

    def as_dict(self):
        return {"groups": list(self.groups), "counts": self.counts()}

    def render(self, reporter, title):
        reporter.write("# {}".format(title))
        reporter.write("")
        summary = self.counts()
        reporter.write(
            "Summary pass={0} fail={1} warn={2} info={3}".format(
                summary.get("pass", 0),
                summary.get("fail", 0),
                summary.get("warn", 0),
                summary.get("info", 0),
            ),
        )
        reporter.write("")
        for group in self.groups:
            reporter.write("## {}".format(group["name"]))
            for item in group["items"]:
                line = "- [{0}] {1}".format(item["status"].upper(), item["label"])
                if item["details"]:
                    line += " :: {}".format(item["details"])
                reporter.write(line)
            reporter.write("")

    def render_to_output(self, output, title):
        reporter = ScriptReporter(
            title=title, output=output, logger=None, log_path=None
        )
        self.render(reporter, title)


def _format_guid_mismatches(mismatches):
    return "; ".join(
        "{}: {} != {}".format(name, actual_guid, expected_guid)
        for name, actual_guid, expected_guid in mismatches
    )


def _ensure_paths(extension_root):
    for path in (extension_root, os.path.join(extension_root, "lib")):
        if path not in sys.path:
            sys.path.insert(0, path)


def _check_environment(report, doc, extension_root, reporter):
    report.add(
        "Environment", "pass", "Revit host available", doc.Application.VersionName
    )
    report.add("Environment", "pass", "Extension root detected", extension_root)

    families_dir = os.path.join(extension_root, "Families")
    if os.path.isdir(families_dir):
        report.add("Environment", "pass", "Families directory present", families_dir)
    else:
        report.add("Environment", "fail", "Families directory missing", families_dir)

    core_modules = (
        "floor_common",
        "floor_exact",
        "floor_grid",
        "floor_i18n",
        "floor_ui",
        "floor_utils",
        "rf_param_schema",
    )
    failed = []
    for module_name in core_modules:
        try:
            __import__(module_name)
        except Exception as exc:
            failed.append("{}: {}".format(module_name, exc))
    if failed:
        report.add("Environment", "fail", "Core module imports", " | ".join(failed))
    else:
        report.add(
            "Environment", "pass", "Core module imports", ", ".join(core_modules)
        )

    sink_labels = reporter.get_sink_labels()
    if sink_labels:
        report.add("Environment", "pass", "Reporting surfaces", ", ".join(sink_labels))
    else:
        report.add(
            "Environment", "warn", "Reporting surfaces", "No reporting sinks ready"
        )
    if reporter.log_path:
        report.add("Environment", "info", "Text log file", reporter.log_path)


def _check_document_context(report, doc):
    from Autodesk.Revit.DB import FilteredElementCollector, Level, ViewPlan  # type: ignore

    if doc is None:
        report.add("Document Context", "fail", "Active document", "No active document")
        return

    title = getattr(doc, "Title", "") or "<untitled>"
    if doc.IsFamilyDocument:
        report.add(
            "Document Context",
            "warn",
            "Document mode",
            "Family document: {}".format(title),
        )
        return

    report.add("Document Context", "pass", "Document mode", "Project: {}".format(title))

    active_view = getattr(doc, "ActiveView", None)
    if isinstance(active_view, ViewPlan):
        report.add(
            "Document Context",
            "pass",
            "Active view compatibility",
            "{}".format(getattr(active_view, "Name", "<unnamed view>")),
        )
    else:
        view_type = type(active_view).__name__ if active_view is not None else "None"
        report.add(
            "Document Context",
            "fail",
            "Active view compatibility",
            "Need ViewPlan, got {}".format(view_type),
        )

    levels = list(FilteredElementCollector(doc).OfClass(Level))
    if levels:
        report.add("Document Context", "pass", "Levels available", str(len(levels)))
    else:
        report.add("Document Context", "fail", "Levels available", "No levels found")


def _check_project_parameters(report, doc):
    if doc.IsFamilyDocument:
        report.add(
            "Families and Parameters",
            "warn",
            "Project parameter bindings",
            "Skipped in family document",
        )
        return

    from floor_utils import get_existing_parameter_bindings  # type: ignore
    from rf_param_schema import collect_project_parameter_guid_mismatches  # type: ignore

    existing = get_existing_parameter_bindings(doc)
    missing = [name for name in PROJECT_PARAM_NAMES if name not in existing]
    if missing:
        report.add(
            "Families and Parameters",
            "fail",
            "Project parameter bindings",
            "Missing: {}".format(", ".join(missing)),
        )
    else:
        report.add(
            "Families and Parameters",
            "pass",
            "Project parameter bindings",
            "{} RF params".format(len(PROJECT_PARAM_NAMES)),
        )

    mismatches = collect_project_parameter_guid_mismatches(
        doc,
        allowed_names=PROJECT_PARAM_NAMES,
        bound_names=existing.keys(),
    )
    if mismatches:
        report.add(
            "Families and Parameters",
            "warn",
            "Project parameter GUIDs",
            _format_guid_mismatches(mismatches),
        )
    else:
        report.add(
            "Families and Parameters",
            "pass",
            "Project parameter GUIDs",
            "Canonical schema intact",
        )


def _find_loaded_families(doc):
    from Autodesk.Revit.DB import Family, FilteredElementCollector  # type: ignore

    result = {}
    for family in FilteredElementCollector(doc).OfClass(Family):
        name = getattr(family, "Name", None)
        if name:
            result[name] = family
    return result


def _count_family_symbols(family):
    symbol_ids = family.GetFamilySymbolIds()
    try:
        return symbol_ids.Count
    except Exception:
        return len(list(symbol_ids))


def _check_current_family_doc(report, doc):
    from rf_param_schema import collect_family_parameter_guid_mismatches  # type: ignore

    family_name = os.path.splitext(getattr(doc, "Title", "") or "")[0]
    allowed_names = get_expected_family_param_names(family_name)
    mismatches = collect_family_parameter_guid_mismatches(doc, allowed_names)
    if mismatches:
        report.add(
            "Families and Parameters",
            "warn",
            "Current family RF parameter GUIDs",
            _format_guid_mismatches(mismatches),
        )
    else:
        report.add(
            "Families and Parameters",
            "pass",
            "Current family RF parameter GUIDs",
            "{}".format(family_name or "<unnamed family>"),
        )


def _check_project_families(report, doc):
    from rf_param_schema import collect_family_parameter_guid_mismatches  # type: ignore

    loaded = _find_loaded_families(doc)
    missing = [name for name in REQUIRED_FAMILY_NAMES if name not in loaded]
    if missing:
        report.add(
            "Families and Parameters",
            "fail",
            "Required RF families loaded",
            "Missing: {}".format(", ".join(missing)),
        )
    else:
        report.add(
            "Families and Parameters",
            "pass",
            "Required RF families loaded",
            ", ".join(REQUIRED_FAMILY_NAMES),
        )

    for family_name in REQUIRED_FAMILY_NAMES:
        family = loaded.get(family_name)
        if family is None:
            continue

        symbol_count = _count_family_symbols(family)
        if symbol_count > 0:
            report.add(
                "Families and Parameters",
                "pass",
                "Family types available",
                "{} -> {}".format(family_name, symbol_count),
            )
        else:
            report.add(
                "Families and Parameters",
                "fail",
                "Family types available",
                "{} -> 0 symbols".format(family_name),
            )

        if not family.IsEditable:
            report.add(
                "Families and Parameters",
                "warn",
                "Editable family inspection",
                "{} is not editable".format(family_name),
            )
            continue

        fam_doc = None
        try:
            fam_doc = doc.EditFamily(family)
            mismatches = collect_family_parameter_guid_mismatches(
                fam_doc, get_expected_family_param_names(family_name)
            )
            if mismatches:
                report.add(
                    "Families and Parameters",
                    "warn",
                    "Family RF parameter GUIDs",
                    "{} -> {}".format(family_name, _format_guid_mismatches(mismatches)),
                )
            else:
                report.add(
                    "Families and Parameters",
                    "pass",
                    "Family RF parameter GUIDs",
                    "{}".format(family_name),
                )
        except Exception as exc:
            report.add(
                "Families and Parameters",
                "warn",
                "Editable family inspection",
                "{} -> {}".format(family_name, exc),
            )
        finally:
            if fam_doc is not None:
                try:
                    fam_doc.Close(False)
                except Exception:
                    pass


def _check_families(report, doc):
    if doc.IsFamilyDocument:
        _check_current_family_doc(report, doc)
    else:
        _check_project_families(report, doc)


def _check_transaction_safety(report, doc):
    from Autodesk.Revit.DB import Transaction  # type: ignore

    tx = Transaction(doc, "RF Smoke Empty Commit")
    try:
        tx.Start()
        tx.Commit()
        report.add("Transaction Safety", "pass", "Empty transaction commit", "OK")
    except Exception as exc:
        try:
            if tx.HasStarted():
                tx.RollBack()
        except Exception:
            pass
        report.add("Transaction Safety", "fail", "Empty transaction commit", str(exc))

    tx = Transaction(doc, "RF Smoke Forced Rollback")
    try:
        tx.Start()
        raise RuntimeError("forced smoke rollback")
    except Exception:
        try:
            if tx.HasStarted():
                tx.RollBack()
            report.add("Transaction Safety", "pass", "Forced rollback", "OK")
        except Exception as exc:
            report.add("Transaction Safety", "fail", "Forced rollback", str(exc))


def _is_positive_double_param(element, name):
    try:
        param = element.LookupParameter(name)
        if param is None or not hasattr(param, "AsDouble"):
            return False
        return (param.AsDouble() or 0.0) > 0.0
    except Exception:
        return False


def _has_nonempty_string_param(element, name):
    try:
        param = element.LookupParameter(name)
        if param is None or not hasattr(param, "AsString"):
            return False
        return bool((param.AsString() or "").strip())
    except Exception:
        return False


def _check_readiness(report, doc):
    if doc.IsFamilyDocument:
        report.add(
            "Lightweight Command Readiness",
            "warn",
            "Project workflow readiness",
            "Skipped in family document",
        )
        return

    from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector  # type: ignore

    floors = list(
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Floors)
        .WhereElementIsNotElementType()
    )
    if not floors:
        report.add(
            "Lightweight Command Readiness",
            "fail",
            "Floors in project",
            "No floor elements found",
        )
        return

    report.add(
        "Lightweight Command Readiness",
        "pass",
        "Floors in project",
        str(len(floors)),
    )

    grid_ready = any(
        _is_positive_double_param(floor, P.STEP_X)
        and _is_positive_double_param(floor, P.STEP_Y)
        for floor in floors
    )
    report.add(
        "Lightweight Command Readiness",
        "pass" if grid_ready else "warn",
        "Grid prerequisites",
        "{}/{} present".format(P.STEP_X, P.STEP_Y)
        if grid_ready
        else "No prepared floor with {}/{}".format(P.STEP_X, P.STEP_Y),
    )

    contour_ready = any(
        _has_nonempty_string_param(floor, P.CONTOUR_LINES_ID) for floor in floors
    )
    report.add(
        "Lightweight Command Readiness",
        "pass" if contour_ready else "warn",
        "Contour prerequisites",
        "{} present".format(P.CONTOUR_LINES_ID)
        if contour_ready
        else "No floor with contour IDs yet",
    )

    loaded = _find_loaded_families(doc)
    missing = []
    for family_name in REQUIRED_FAMILY_NAMES:
        family = loaded.get(family_name)
        if family is None or _count_family_symbols(family) == 0:
            missing.append(family_name)
    if missing:
        report.add(
            "Lightweight Command Readiness",
            "fail",
            "Placement prerequisites",
            "Missing loaded family types: {}".format(", ".join(missing)),
        )
    else:
        report.add(
            "Lightweight Command Readiness",
            "pass",
            "Placement prerequisites",
            "All required family types loaded",
        )


def run_smoke(extension_root=None):
    """Run grouped smoke checks inside Revit and render a structured report."""
    from pyrevit import revit  # type: ignore

    root = extension_root or get_extension_root(__file__)
    _ensure_paths(root)

    report = SmokeReport()
    reporter = ScriptReporter.from_pyrevit(
        title="RaisedFloor Revit Smoke",
        log_stem="revit_smoke",
    )
    logger = getattr(reporter, "logger", None)
    if logger is not None and reporter.log_path:
        try:
            logger.info("Smoke log file: {}".format(reporter.log_path))
        except Exception:
            pass

    doc = revit.doc
    _check_environment(report, doc, root, reporter)
    _check_document_context(report, doc)
    _check_project_parameters(report, doc)
    _check_families(report, doc)
    _check_transaction_safety(report, doc)
    _check_readiness(report, doc)

    report.render(reporter, "RaisedFloor Revit Smoke")
    result = report.as_dict()
    if reporter.log_path:
        result["log_path"] = reporter.log_path
    return result

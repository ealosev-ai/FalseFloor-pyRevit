# -*- coding: utf-8 -*-
"""Pure tests for the grouped Revit smoke report helpers."""

import os

import pytest

from revit_smoke import SmokeReport, get_expected_family_param_names, get_extension_root


class _DummyOutput(object):
    def __init__(self):
        self.lines = []

    def print_md(self, text):
        self.lines.append(text)


def test_get_extension_root_walks_up_from_button_script():
    start = os.path.join(
        "D:\\pyRevit\\RaisedFloor.extension",
        "RaisedFloor.tab",
        "RaisedFloor.panel",
        "99_Tests.pulldown11",
        "Run Tests.pushbutton",
        "script.py",
    )

    root = get_extension_root(start)

    assert root.endswith("RaisedFloor.extension")


@pytest.mark.parametrize(
    "family_name, expected",
    [
        ("RF_Tile", {"RF_Tile_Type", "RF_Ventilated"}),
        ("RF_Stringer", {"RF_Stringer_Type", "RF_Profile_Height"}),
        ("RF_Support", {"RF_Support_Height", "RF_Base_Size"}),
    ],
)
def test_expected_family_param_names_are_partitioned(family_name, expected):
    assert expected.issubset(get_expected_family_param_names(family_name))


def test_smoke_report_counts_and_render():
    report = SmokeReport()
    report.add("Environment", "pass", "Imports", "OK")
    report.add("Environment", "warn", "Output", "Missing")
    report.add("Document Context", "fail", "View", "Need ViewPlan")

    output = _DummyOutput()
    report.render_to_output(output, "RaisedFloor Revit Smoke")

    assert report.counts() == {"pass": 1, "fail": 1, "warn": 1, "info": 0}
    joined = "\n".join(output.lines)
    assert "RaisedFloor Revit Smoke" in joined
    assert "[PASS] Imports" in joined
    assert "[FAIL] View" in joined

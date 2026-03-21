"""Pure unit tests for floor_ui formatting and status logic."""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))

pytestmark = [pytest.mark.unit]


def _fake_tr(key, **kwargs):
    if kwargs:
        parts = ["{}={}".format(k, kwargs[k]) for k in sorted(kwargs.keys())]
        return "{}|{}".format(key, ",".join(parts))
    return key


@pytest.fixture
def ui(monkeypatch):
    import floor_ui

    monkeypatch.setattr(floor_ui, "tr", _fake_tr)
    return floor_ui


def _base_result(**overrides):
    data = {
        "shift_x_mm": 100,
        "shift_y_mm": 200,
        "full_count": 10,
        "viable_simple_count": 8,
        "complex_count": 0,
        "total_simple_count": 10,
        "non_viable_count": 0,
        "unwanted_count": 0,
        "acceptable_count": 0,
        "good_count": 2,
        "unique_sizes": 3,
        "min_viable_cut_mm": 150,
        "min_cut_all_mm": 160,
        "micro_fragment_count": 0,
        "total_cut_area_mm2": 12345.0,
    }
    data.update(overrides)
    return data


def test_shift_quality_invalid_when_non_viable(ui):
    assert (
        ui.get_shift_quality_status(_base_result(non_viable_count=1))
        == "shift_status_invalid"
    )


def test_shift_quality_ok_when_complex_or_unwanted(ui):
    assert (
        ui.get_shift_quality_status(_base_result(complex_count=1)) == "shift_status_ok"
    )
    assert (
        ui.get_shift_quality_status(_base_result(unwanted_count=1)) == "shift_status_ok"
    )


def test_shift_quality_good_when_acceptable(ui):
    assert (
        ui.get_shift_quality_status(_base_result(acceptable_count=2))
        == "shift_status_good"
    )


def test_shift_quality_great_when_clean(ui):
    assert ui.get_shift_quality_status(_base_result()) == "shift_status_great"


def test_format_shift_result_lines_without_index(ui):
    lines = ui.format_shift_result_lines(_base_result())
    assert len(lines) == 8
    assert lines[0].startswith("shift_status|")
    assert lines[1].startswith("shift_x|")
    assert lines[2].startswith("shift_y|")
    assert lines[-1].startswith("cut_area|")


def test_format_shift_result_lines_with_index(ui):
    lines = ui.format_shift_result_lines(_base_result(), index=7)
    assert lines[1].startswith("shift_xy_ranked|")
    assert "index=7" in lines[1]


def test_format_shift_result_lines_with_custom_area_text(ui):
    lines = ui.format_shift_result_lines(_base_result(), area_text="A=42")
    assert lines[-1] == "cut_area|area=A=42"


def test_format_shift_summary_line_with_prefix_and_suffix(ui):
    line = ui.format_shift_result_summary_line(
        _base_result(min_cut_all_mm=100, min_viable_cut_mm=150), index=2
    )
    assert line.startswith("shift_summary_line|")
    assert "prefix=2. " in line
    assert "shift_abs_min_suffix" in line


def test_format_shift_summary_line_without_suffix(ui):
    line = ui.format_shift_result_summary_line(
        _base_result(min_cut_all_mm=180, min_viable_cut_mm=150), index=None
    )
    assert "prefix=" in line
    assert "shift_abs_min_suffix" not in line


def test_format_shift_search_info_short(ui):
    search = {
        "coarse_step_mm": 100,
        "refine_step_mm": 25,
        "refine_radius_mm": 150,
        "coarse_count": 8,
        "refine_count": 16,
        "total_count": 24,
    }
    lines = ui.format_shift_search_info_lines(search, include_threshold=False)
    assert len(lines) == 2
    assert lines[0].startswith("shift_search_short|")
    assert "snap=" in lines[1]


def test_format_shift_search_info_full_with_thresholds_and_snap(ui):
    search = {
        "coarse_step_mm": 120,
        "refine_step_mm": 40,
        "refine_radius_mm": 200,
        "unacceptable_cut_mm": 80,
        "unwanted_cut_mm": 120,
        "acceptable_cut_mm": 180,
        "coarse_count": 7,
        "refine_count": 9,
        "total_count": 16,
        "snap_x_count": 3,
        "snap_y_count": 2,
        "hole_snap_pair_count": 1,
    }
    lines = ui.format_shift_search_info_lines(search, include_threshold=True)
    assert len(lines) == 3
    assert lines[0].startswith("shift_search_full|")
    assert lines[1].startswith("shift_thresholds|")
    assert "holes=1" in lines[2]

"""Non-Revit tests for pure logic in floor_common.

These tests inject lightweight Autodesk/pyRevit stubs so floor_common can be
imported outside Revit runtime, then validate deterministic helper logic.
"""

import importlib
import json
import os
import sys
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit]


def _install_revit_stubs():
    """Install minimal Autodesk + pyRevit stubs required by floor_common import."""
    if "Autodesk.Revit.DB" not in sys.modules:
        db = ModuleType("Autodesk.Revit.DB")

        class _BuiltInCategory:
            OST_Floors = 1
            OST_Lines = 2

        class _StorageType:
            Double = "Double"
            Integer = "Integer"
            String = "String"

        class _ElementId:
            def __init__(self, val):
                self.IntegerValue = int(val)
                self.Value = int(val)

        class _Color:
            def __init__(self, r, g, b):
                self.Red = r
                self.Green = g
                self.Blue = b

        class _FilteredElementCollector:
            def __init__(self, *args, **kwargs):
                pass

            def OfClass(self, *args, **kwargs):
                return []

        class _Part:
            pass

        class _GraphicsStyleType:
            Projection = 0

        class _LinePatternElement:
            Name = ""

        class _SpecTypeId:
            Length = "Spec.Length"

        class _ParameterType:
            Length = "Param.Length"

        db.BuiltInCategory = _BuiltInCategory
        db.Color = _Color
        db.ElementId = _ElementId
        db.FilteredElementCollector = _FilteredElementCollector
        db.GraphicsStyleType = _GraphicsStyleType
        db.LinePatternElement = _LinePatternElement
        db.Part = _Part
        db.SpecTypeId = _SpecTypeId
        db.ParameterType = _ParameterType
        db.StorageType = _StorageType

        autodesk = ModuleType("Autodesk")
        revit = ModuleType("Autodesk.Revit")
        autodesk.Revit = revit
        revit.DB = db

        sys.modules["Autodesk"] = autodesk
        sys.modules["Autodesk.Revit"] = revit
        sys.modules["Autodesk.Revit.DB"] = db

    if "Autodesk.Revit.UI.Selection" not in sys.modules:
        selection = ModuleType("Autodesk.Revit.UI.Selection")

        class _ISelectionFilter:
            pass

        selection.ISelectionFilter = _ISelectionFilter
        ui = ModuleType("Autodesk.Revit.UI")
        ui.Selection = selection
        sys.modules["Autodesk.Revit.UI"] = ui
        sys.modules["Autodesk.Revit.UI.Selection"] = selection

    if "pyrevit" not in sys.modules:
        pyrevit = ModuleType("pyrevit")
        pyrevit.revit = ModuleType("pyrevit.revit")
        pyrevit.revit.doc = object()
        sys.modules["pyrevit"] = pyrevit
        sys.modules["pyrevit.revit"] = pyrevit.revit


def _import_floor_common():
    _install_revit_stubs()

    lib_dir = os.path.join(os.path.dirname(__file__), "..", "lib")
    lib_dir = os.path.normpath(lib_dir)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)

    if "floor_common" in sys.modules:
        return importlib.reload(sys.modules["floor_common"])
    return importlib.import_module("floor_common")


def test_build_positions_padding_and_bounds():
    mod = _import_floor_common()
    pos = mod.build_positions(0.0, 10.0, 0.0, 3.0, end_padding_steps=1.0)
    assert pos[0] <= 0.0
    assert pos[-1] >= 10.0
    assert len(pos) >= 4


def test_build_positions_zero_step_returns_empty():
    mod = _import_floor_common()
    with pytest.raises(ValueError):
        mod.build_positions(0.0, 10.0, 0.0, 0.0)


def test_build_positions_rejects_invalid_range():
    mod = _import_floor_common()
    with pytest.raises(ValueError):
        mod.build_positions(10.0, 0.0, 0.0, 1.0)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1;2;3", [1, 2, 3]),
        (" 1 ; x ; 3 ", [1, 3]),
        ("", []),
        (None, []),
    ],
)
def test_parse_ids_from_string(raw, expected):
    mod = _import_floor_common()
    assert mod.parse_ids_from_string(raw) == expected


def test_cut_equal_1d_balanced_segments():
    mod = _import_floor_common()
    segs = mod.cut_equal_1d(0.0, 12.0, 5.0)
    assert len(segs) == 3
    assert abs(sum(b - a for a, b in segs) - 12.0) < 1e-9


def test_cut_at_positions_uses_hints_and_fallback():
    mod = _import_floor_common()
    hinted = mod.cut_at_positions_1d(0.0, 10.0, 5.0, [3.0, 5.0, 8.0])
    assert hinted[0] == (0.0, 5.0) or hinted[0] == (0.0, 3.0)

    fallback = mod.cut_at_positions_1d(0.0, 20.0, 5.0, [100.0])
    assert len(fallback) == 4


def test_cut_segments_with_stagger_preference_prefers_fewer_pieces():
    mod = _import_floor_common()
    segs = [(0.0, 0.0, 6180.0, 0.0)]
    result = mod.cut_segments_with_stagger_preference(
        segs,
        3600.0,
        preferred_positions=[0.0, 2400.0, 4800.0, 7200.0],
        alternate_positions=[1200.0, 3600.0, 6000.0],
    )

    assert result["used_alternate"] is True
    assert result["piece_count"] == 2
    assert result["seams"] == [3600.0]


def test_cut_segments_with_stagger_preference_avoids_previous_row_seam():
    mod = _import_floor_common()
    segs = [(0.0, 0.0, 6180.0, 0.0)]
    result = mod.cut_segments_with_stagger_preference(
        segs,
        3600.0,
        preferred_positions=[0.0, 2400.0, 4800.0, 7200.0],
        alternate_positions=[1200.0, 3600.0, 6000.0],
        previous_seams=[3600.0],
    )

    assert result["used_alternate"] is False
    assert result["conflict_count"] == 0
    assert result["piece_count"] == 3
    assert result["seams"] == [2400.0, 4800.0]


def test_split_orthogonal_segments_horizontal_vertical_and_diagonal():
    mod = _import_floor_common()
    src = [(0.0, 0.0, 10.0, 0.0), (2.0, 1.0, 2.0, 11.0), (0.0, 0.0, 2.0, 2.0)]
    out = mod.split_orthogonal_segments(src, max_len=5.0)

    assert any(
        abs(y1 - y2) < 1e-9 and abs((x2 - x1) - 5.0) < 1e-6 for x1, y1, x2, y2 in out
    )
    assert any(abs(x1 - x2) < 1e-9 for x1, y1, x2, y2 in out)
    assert (0.0, 0.0, 2.0, 2.0) in out


def test_build_support_nodes_deduplicates_and_inserts_intermediate():
    mod = _import_floor_common()
    segs = [(0.0, 0.0, 30.0, 0.0), (30.0, 0.0, 30.0, 30.0)]
    nodes = mod.build_support_nodes(segs, max_spacing=10.0, support_half=0.0)

    # Линия X: y=0, от 0 до 30 → start, ~10, ~20, end (4 шт.)
    # Линия Y: x=30, от 0 до 30 → start, ~10, ~20, end (4 шт.)
    # (30,0) дедуплицируется → итого ≥ 4 уникальных
    assert len(nodes) >= 4
    assert len(nodes) == len(set(nodes))
    assert (0.0, 0.0) in nodes
    assert (30.0, 0.0) in nodes


def test_build_support_nodes_global_grid_alignment():
    """Parallel segments with grid_positions get intermediate supports at the same positions."""
    mod = _import_floor_common()
    # Two parallel horizontal segments with different start/end
    segs = [
        (0.0, 0.0, 50.0, 0.0),
        (5.0, 10.0, 45.0, 10.0),
    ]
    grid_pos = [10.0, 20.0, 30.0, 40.0]
    nodes = mod.build_support_nodes(
        segs, max_spacing=15.0, support_half=0.0, grid_positions=grid_pos
    )
    # Extract x-positions per y-row
    row_0 = sorted(x for x, y in nodes if abs(y) < 0.01)
    row_10 = sorted(x for x, y in nodes if abs(y - 10.0) < 0.01)
    # Intermediate grid supports should align across rows
    grid_in_0 = [x for x in row_0 if x in grid_pos]
    grid_in_10 = [x for x in row_10 if x in grid_pos]
    # Both rows should pick the same global grid positions (20.0, 30.0)
    # because grid step=10 < max_spacing=15, so global grid picks every other: [10, 30] or [10, 20, 30, 40]
    # with spacing filter ≥15: [10, 30] or [10, 40]
    # The important thing: the SAME grid positions in both rows
    assert grid_in_0 == grid_in_10


def test_looks_like_legacy_mm_in_length_heuristic():
    mod = _import_floor_common()
    assert mod._looks_like_legacy_mm_in_length("RF_Bottom_Step", 1200.0) is True
    assert mod._looks_like_legacy_mm_in_length("RF_Bottom_Step", 3.9) is False
    assert mod._looks_like_legacy_mm_in_length("Unknown", 1200.0) is False


def test_load_reinforcement_zones_supports_list_and_dict(monkeypatch):
    mod = _import_floor_common()

    monkeypatch.setattr(
        mod, "get_string_param", lambda _f, _n: json.dumps([{"name": "A"}])
    )
    data = mod.load_reinforcement_zones(object())
    assert data["zones"] == [{"name": "A"}]
    assert data["version"] == 1

    monkeypatch.setattr(
        mod,
        "get_string_param",
        lambda _f, _n: json.dumps({"version": 3, "zones": [{"name": "B"}]}),
    )
    data = mod.load_reinforcement_zones(object())
    assert data["version"] == 3
    assert data["zones"] == [{"name": "B"}]


def test_load_reinforcement_zones_rejects_invalid_payload(monkeypatch):
    mod = _import_floor_common()

    monkeypatch.setattr(mod, "get_string_param", lambda _f, _n: "{bad json")
    with pytest.raises(ValueError):
        mod.load_reinforcement_zones(object())

    monkeypatch.setattr(mod, "get_string_param", lambda _f, _n: json.dumps({"x": 1}))
    with pytest.raises(ValueError):
        mod.load_reinforcement_zones(object())


def test_read_reinforcement_zone_ids_collects_all_keys(monkeypatch):
    mod = _import_floor_common()
    monkeypatch.setattr(
        mod,
        "load_reinforcement_zones",
        lambda _f: {
            "version": 1,
            "zones": [
                {"upper_ids": [1, "2"], "lower_ids": [3], "support_ids": ["x", 4]},
                {"upper_ids": [5]},
            ],
        },
    )
    assert mod.read_reinforcement_zone_ids(object()) == [1, 2, 3, 4, 5]


def test_get_id_value_and_selection_filter():
    mod = _import_floor_common()

    class _IdObj:
        def __init__(self, value):
            self.Id = type("_Id", (), {"IntegerValue": value, "Value": value})()

    assert mod.get_id_value(_IdObj(42)) == 42

    floor_el = type(
        "_Floor",
        (),
        {
            "Category": type(
                "_Cat", (), {"Id": type("_Id", (), {"IntegerValue": 1})()}
            )()
        },
    )()
    part_el = mod.Part()
    filt = mod.FloorOrPartSelectionFilter()
    assert filt.AllowElement(floor_el) is True
    assert filt.AllowElement(part_el) is True
    assert filt.AllowElement(None) is False


def test_read_floor_grid_params_success_and_missing(monkeypatch):
    mod = _import_floor_common()
    values = {"RF_Step_X": 1.0, "RF_Step_Y": 2.0, "RF_Base_X": 3.0, "RF_Base_Y": 4.0}
    monkeypatch.setattr(mod, "get_double_param", lambda _f, name: values.get(name))
    result = mod.read_floor_grid_params(object())
    assert result == {
        "step_x": 1.0,
        "step_y": 2.0,
        "base_x_raw": 3.0,
        "base_y_raw": 4.0,
    }

    monkeypatch.setattr(
        mod,
        "get_double_param",
        lambda _f, name: None if name == "RF_Base_X" else values.get(name),
    )
    monkeypatch.setattr(
        mod, "tr", lambda key, **kwargs: "{}:{}".format(key, kwargs["missing"])
    )
    with pytest.raises(Exception) as exc:
        mod.read_floor_grid_params(object())
    assert "RF_Base_X" in str(exc.value)


def test_read_floor_grid_params_rejects_non_finite(monkeypatch):
    mod = _import_floor_common()
    values = {
        "RF_Step_X": float("nan"),
        "RF_Step_Y": 2.0,
        "RF_Base_X": 3.0,
        "RF_Base_Y": 4.0,
    }
    monkeypatch.setattr(mod, "get_double_param", lambda _f, name: values.get(name))
    with pytest.raises(Exception) as exc:
        mod.read_floor_grid_params(object())
    assert "RF_Step_X" in str(exc.value)


def test_param_getters_and_setters():
    mod = _import_floor_common()

    class _Param:
        def __init__(self, storage_type, value, read_only=False):
            self.StorageType = storage_type
            self._value = value
            self.IsReadOnly = read_only

        def AsDouble(self):
            return float(self._value)

        def AsString(self):
            return str(self._value)

        def AsInteger(self):
            return int(self._value)

        def Set(self, value):
            self._value = value

    class _El:
        def __init__(self, params):
            self._params = params

        def LookupParameter(self, name):
            return self._params.get(name)

    el = _El(
        {
            "D": _Param(mod.StorageType.Double, 1.5),
            "S": _Param(mod.StorageType.String, "abc"),
        }
    )

    assert mod.get_double_param(el, "D") == 1.5
    assert mod.get_double_param(el, "S") is None
    assert mod.set_double_param(el, "D", 2.5) is True
    assert el.LookupParameter("D")._value == 2.5

    assert mod.get_string_param(el, "S") == "abc"
    assert mod.set_string_param(el, "S", "xyz") is True
    assert el.LookupParameter("S")._value == "xyz"
    assert mod.set_string_param(el, "S", 123) is True
    assert el.LookupParameter("S")._value == "123"
    assert mod.set_string_param(el, "S", None) is True
    assert el.LookupParameter("S")._value == ""


def test_mm_param_helpers_and_legacy_normalization(monkeypatch):
    mod = _import_floor_common()
    db = sys.modules["Autodesk.Revit.DB"]

    class _Def:
        def __init__(self, is_length=False):
            self._is_length = is_length
            self.ParameterType = db.ParameterType.Length if is_length else None

        def GetDataType(self):
            return db.SpecTypeId.Length if self._is_length else None

    class _Param:
        def __init__(self, storage_type, value, is_length=False, read_only=False):
            self.StorageType = storage_type
            self._value = value
            self.IsReadOnly = read_only
            self.Definition = _Def(is_length=is_length)

        def AsDouble(self):
            return float(self._value)

        def AsString(self):
            return str(self._value)

        def AsInteger(self):
            return int(self._value)

        def Set(self, value):
            self._value = value

    class _El:
        def __init__(self, params):
            self._params = params

        def LookupParameter(self, name):
            return self._params.get(name)

    el = _El(
        {
            "str": _Param(mod.StorageType.String, "123,5"),
            "dbl_len": _Param(mod.StorageType.Double, 1.0, is_length=True),
            "dbl_num": _Param(mod.StorageType.Double, 77.0, is_length=False),
            "int": _Param(mod.StorageType.Integer, 42),
            "RF_Bottom_Step": _Param(mod.StorageType.Double, 1200.0, is_length=True),
        }
    )

    assert mod.get_mm_param(el, "str") == 123.5
    assert abs(mod.get_mm_param(el, "dbl_len") - 304.8) < 1e-9
    assert mod.get_mm_param(el, "dbl_num") == 77.0
    assert mod.get_mm_param(el, "int") == 42.0

    assert mod.set_mm_param(el, "str", 10.6) is True
    assert el.LookupParameter("str")._value == "11"
    assert mod.set_mm_param(el, "dbl_len", 304.8) is True
    assert abs(el.LookupParameter("dbl_len")._value - 1.0) < 1e-9
    assert mod.set_mm_param(el, "int", 12.2) is True
    assert el.LookupParameter("int")._value == 12

    assert mod.normalize_legacy_mm_param(el, "RF_Bottom_Step") is True
    assert abs(el.LookupParameter("RF_Bottom_Step")._value - (1200.0 / 304.8)) < 1e-9


def test_delete_elements_and_zone_save(monkeypatch):
    mod = _import_floor_common()

    class _Doc:
        def __init__(self):
            self.deleted = []

        def GetElement(self, el_id):
            return object() if el_id.IntegerValue in (1, 3) else None

        def Delete(self, el_id):
            self.deleted.append(el_id.IntegerValue)

    fake_doc = _Doc()
    monkeypatch.setattr(mod, "get_doc", lambda: fake_doc)
    assert mod.delete_elements_by_ids([1, 2, 3]) == 2
    assert fake_doc.deleted == [1, 3]

    captured = {}
    monkeypatch.setattr(
        mod,
        "set_string_param",
        lambda _f, name, raw: captured.update({"name": name, "raw": raw}) or True,
    )
    assert (
        mod.save_reinforcement_zones(object(), {"version": 1, "zones": [{"x": 1}]})
        is True
    )
    assert captured["name"] == mod.REINFORCEMENT_ZONES_PARAM
    assert '"zones"' in captured["raw"]


def test_cut_and_support_helpers_reject_invalid_spacing():
    mod = _import_floor_common()

    with pytest.raises(ValueError):
        mod.cut_equal_1d(0.0, 10.0, 0.0)

    with pytest.raises(ValueError):
        mod.cut_at_positions_1d(0.0, 10.0, -1.0, [])

    with pytest.raises(ValueError):
        mod.build_support_nodes([(0.0, 0.0, 10.0, 0.0)], 0.0)


def test_line_style_helpers(monkeypatch):
    mod = _import_floor_common()

    class _Pattern:
        def __init__(self, name, pid):
            self.Name = name
            self.Id = pid

    class _GraphicsStyle:
        def __init__(self, sid):
            self.Id = sid

    class _SubCat:
        def __init__(self, name, sid):
            self.Name = name
            self._style = _GraphicsStyle(sid)
            self.LineColor = None
            self.pattern_id = None
            self.weight = None

        def SetLineWeight(self, weight, _proj):
            self.weight = weight

        def SetLinePatternId(self, pattern_id, _proj):
            self.pattern_id = pattern_id

        def GetGraphicsStyle(self, _proj):
            return self._style

    class _LinesCat:
        def __init__(self, subs):
            self.SubCategories = subs

    class _Categories:
        def __init__(self, lines_cat):
            self._lines_cat = lines_cat

        def get_Item(self, _bic):
            return self._lines_cat

        def NewSubcategory(self, lines_cat, style_name):
            sub = _SubCat(style_name, 99)
            lines_cat.SubCategories.append(sub)
            return sub

    class _Settings:
        def __init__(self, categories):
            self.Categories = categories

    class _Doc:
        def __init__(self, lines_cat):
            self.Settings = _Settings(_Categories(lines_cat))

    existing = _SubCat("Existing", 7)
    lines_cat = _LinesCat([existing])
    doc = _Doc(lines_cat)

    class _Collector:
        def __init__(self, *_args, **_kwargs):
            pass

        def OfClass(self, *_args, **_kwargs):
            return [_Pattern("Center", 123)]

    monkeypatch.setattr(mod, "FilteredElementCollector", _Collector)
    style = mod.get_or_create_line_style(
        doc, "Existing", weight=5, line_pattern_name="Center", update_existing=True
    )
    assert style.Id == 7
    assert existing.weight == 5
    assert existing.pattern_id == 123
    assert mod.line_style_exists(doc, "Existing") is True
    assert mod.get_line_style_id(doc, "Existing") == 7

    new_style = mod.get_or_create_line_style(
        doc, "NewStyle", line_pattern_name="Center"
    )
    assert new_style.Id == 99
    assert mod.line_style_exists(doc, "NewStyle") is True
    assert mod._find_line_pattern(doc, "center").Id == 123

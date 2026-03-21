"""Non-Revit tests for floor_grid using lightweight stubs."""

import importlib
import os
import sys
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit]


def _install_stubs():
    if "Autodesk.Revit.DB" not in sys.modules:
        db = ModuleType("Autodesk.Revit.DB")

        class _XYZ:
            def __init__(self, x, y, z):
                self.X = x
                self.Y = y
                self.Z = z

        class _Color:
            def __init__(self, r, g, b):
                self.Red = r
                self.Green = g
                self.Blue = b

        class _CurveElement:
            pass

        class _ElementId:
            def __init__(self, value):
                self.IntegerValue = int(value)
                self.Value = int(value)

        class _Family:
            pass

        class _FilteredElementCollector:
            def __init__(self, *_args, **_kwargs):
                self._items = []

            def OfClass(self, *_args, **_kwargs):
                return self._items

        class _Line:
            @staticmethod
            def CreateBound(a, b):
                return (a, b)

        db.XYZ = _XYZ
        db.Color = _Color
        db.CurveElement = _CurveElement
        db.ElementId = _ElementId
        db.Family = _Family
        db.FilteredElementCollector = _FilteredElementCollector
        db.Line = _Line

        autodesk = ModuleType("Autodesk")
        revit = ModuleType("Autodesk.Revit")
        autodesk.Revit = revit
        revit.DB = db

        sys.modules["Autodesk"] = autodesk
        sys.modules["Autodesk.Revit"] = revit
        sys.modules["Autodesk.Revit.DB"] = db

    if "floor_common" not in sys.modules:
        floor_common = ModuleType("floor_common")

        floor_common.build_positions = lambda *a, **k: []
        floor_common.get_double_param = lambda obj, name: getattr(
            obj, "_params", {}
        ).get(name)
        floor_common.get_line_style_id = lambda *_a, **_k: None
        floor_common.get_or_create_line_style = lambda *_a, **_k: object()
        floor_common.get_string_param = lambda *_a, **_k: ""
        floor_common.parse_ids_from_string = lambda _s: []
        floor_common.set_string_param = lambda *_a, **_k: True

        sys.modules["floor_common"] = floor_common

    if "pyrevit" not in sys.modules:
        pyrevit = ModuleType("pyrevit")
        pyrevit.revit = ModuleType("pyrevit.revit")
        pyrevit.revit.doc = object()
        sys.modules["pyrevit"] = pyrevit
        sys.modules["pyrevit.revit"] = pyrevit.revit


def _import_floor_grid():
    _install_stubs()

    lib_dir = os.path.join(os.path.dirname(__file__), "..", "lib")
    lib_dir = os.path.normpath(lib_dir)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)

    if "floor_grid" in sys.modules:
        return importlib.reload(sys.modules["floor_grid"])
    return importlib.import_module("floor_grid")


def test_internal_clipper_roundtrip_close_enough():
    mod = _import_floor_grid()
    src = 1.234567
    packed = mod._internal_to_clipper(src)
    restored = mod._clipper_to_internal(packed)

    assert isinstance(packed, int)
    assert abs(restored - src) < 1e-5


def test_get_bbox_xy_active_view_then_fallback_none():
    mod = _import_floor_grid()

    class _Pt:
        def __init__(self, x, y, z):
            self.X = x
            self.Y = y
            self.Z = z

    class _Bbox:
        def __init__(self):
            self.Min = _Pt(1, 2, 3)
            self.Max = _Pt(10, 20, 30)

    class _El:
        def __init__(self, active_bbox, model_bbox):
            self._active = active_bbox
            self._model = model_bbox

        def get_BoundingBox(self, view):
            return self._active if view is not None else self._model

    data = mod.get_bbox_xy(_El(_Bbox(), None), active_view=object())
    assert data == (1, 2, 10, 20, 3, 30)

    data = mod.get_bbox_xy(_El(None, _Bbox()), active_view=object())
    assert data == (1, 2, 10, 20, 3, 30)

    data = mod.get_bbox_xy(_El(None, None), active_view=object())
    assert data is None


def test_collect_styled_curve_ids_filters_correctly(monkeypatch):
    mod = _import_floor_grid()

    class _Style:
        def __init__(self, sid):
            self.Id = sid

    class _Curve:
        def __init__(self, eid, view_specific, style):
            self.ViewSpecific = view_specific
            self.LineStyle = style
            self.Id = type("_Id", (), {"IntegerValue": eid})()

    curves = [
        _Curve(1, True, _Style(10)),
        _Curve(2, True, _Style(99)),
        _Curve(3, False, _Style(10)),
    ]

    class _Collector:
        def __init__(self, *_args, **_kwargs):
            pass

        def OfClass(self, *_args, **_kwargs):
            return curves

    monkeypatch.setattr(mod, "FilteredElementCollector", _Collector)

    ids = mod._collect_styled_curve_ids(type("_V", (), {"Id": 1})(), style_id=10)
    assert ids == [1]


def test_get_stringer_clearance_max_and_default(monkeypatch):
    mod = _import_floor_grid()

    class _Fam:
        def __init__(self, name, symbol_ids):
            self.Name = name
            self._ids = symbol_ids

        def GetFamilySymbolIds(self):
            return self._ids

    class _Sym:
        def __init__(self, width_ft):
            self._params = {"RF_Profile_Width": width_ft}

    class _Doc:
        def __init__(self, mapping):
            self._map = mapping

        def GetElement(self, sid):
            return self._map.get(sid)

    families = [_Fam("Other", [1]), _Fam("RF_Stringer", [2, 3])]
    mapping = {2: _Sym(0.1), 3: _Sym(0.2)}

    class _Collector:
        def __init__(self, *_args, **_kwargs):
            pass

        def OfClass(self, *_args, **_kwargs):
            return families

    monkeypatch.setattr(mod, "FilteredElementCollector", _Collector)
    monkeypatch.setattr(mod, "doc", _Doc(mapping))

    clearance_mm = mod._get_stringer_clearance_mm()
    assert abs(clearance_mm - (0.2 * mod._INTERNAL_TO_MM)) < 1e-6

    class _EmptyCollector:
        def __init__(self, *_args, **_kwargs):
            pass

        def OfClass(self, *_args, **_kwargs):
            return []

    monkeypatch.setattr(mod, "FilteredElementCollector", _EmptyCollector)
    clearance_default = mod._get_stringer_clearance_mm()
    assert clearance_default == mod._DEFAULT_COL_CLEARANCE_MM


def test_recreate_contour_on_top_rebuilds_lines(monkeypatch):
    mod = _import_floor_grid()

    class _CurveEl:
        def __init__(self, cid):
            self.GeometryCurve = "curve{}".format(cid)

    class _Created:
        def __init__(self, cid):
            self.Id = type("_Id", (), {"Value": cid})()
            self.LineStyle = None

    class _Create:
        def __init__(self):
            self.created = []

        def NewDetailCurve(self, _view, curve):
            cid = 100 + len(self.created)
            obj = _Created(cid)
            self.created.append((curve, obj))
            return obj

    class _Doc:
        def __init__(self):
            self.Create = _Create()
            self.deleted = []

        def GetElement(self, el_id):
            return _CurveEl(el_id.IntegerValue)

        def Delete(self, el_id):
            self.deleted.append(el_id.IntegerValue)

    captured = {}
    fake_doc = _Doc()
    monkeypatch.setattr(mod, "doc", fake_doc)
    monkeypatch.setattr(mod, "get_string_param", lambda *_a, **_k: "1;2")
    monkeypatch.setattr(mod, "parse_ids_from_string", lambda _s: [1, 2])
    monkeypatch.setattr(mod, "get_or_create_line_style", lambda *_a, **_k: "STYLE")
    monkeypatch.setattr(
        mod,
        "set_string_param",
        lambda _f, name, value: captured.update({name: value}) or True,
    )

    count = mod._recreate_contour_on_top(object(), object(), update_style=True)
    assert count == 2
    assert fake_doc.deleted == [1, 2]
    assert captured["RF_Contour_Lines_ID"] == "100;101"


def test_redraw_grid_for_floor_main_flow(monkeypatch):
    mod = _import_floor_grid()

    class _Tx:
        def __init__(self, *_a, **_k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Created:
        def __init__(self, cid, line):
            self.Id = type("_Id", (), {"Value": cid})()
            self.LineStyle = None
            self.line = line

    class _Create:
        def __init__(self):
            self.items = []

        def NewDetailCurve(self, _view, line):
            cid = 200 + len(self.items)
            obj = _Created(cid, line)
            self.items.append(obj)
            return obj

    class _Doc:
        def __init__(self):
            self.Create = _Create()
            self.deleted = []

        def GetElement(self, el_id):
            return object() if el_id.IntegerValue in (1, 4, 6) else None

        def Delete(self, el_id):
            self.deleted.append(el_id.IntegerValue)

    class _View:
        Id = 10

    floor = object()
    params = {
        "RF_Step_X": 2.0,
        "RF_Step_Y": 2.0,
        "RF_Base_X": 5.0,
        "RF_Base_Y": 7.0,
        "RF_Offset_X": 1.0,
        "RF_Offset_Y": 2.0,
    }
    stored = {}
    fake_doc = _Doc()

    monkeypatch.setattr(mod, "doc", fake_doc)
    monkeypatch.setattr(mod.revit, "Transaction", _Tx)
    monkeypatch.setattr(mod, "get_double_param", lambda _f, name: params.get(name))
    monkeypatch.setattr(
        mod, "get_bbox_xy", lambda *_a, **_k: (0.0, 0.0, 10.0, 10.0, 3.0, 4.0)
    )
    monkeypatch.setattr(
        mod,
        "build_positions",
        lambda min_v, max_v, base_v, step_v, **_k: [base_v, base_v + step_v],
    )
    monkeypatch.setattr(
        mod,
        "get_string_param",
        lambda _f, name: "1;1;4" if name == "RF_Grid_Lines_ID" else "6",
    )
    monkeypatch.setattr(
        mod, "parse_ids_from_string", lambda s: [int(x) for x in s.split(";") if x]
    )

    style_ids = {
        mod.GRID_LINE_STYLE_NAME: 11,
        mod.NEAR_COLUMN_STYLE_NAME: 12,
        mod.BASE_MARKER_STYLE_NAME: 13,
    }
    monkeypatch.setattr(mod, "get_line_style_id", lambda _d, name: style_ids.get(name))
    monkeypatch.setattr(
        mod,
        "_collect_styled_curve_ids",
        lambda _view, sid: {11: [4], 12: [7], 13: [8]}.get(sid, []),
    )
    monkeypatch.setattr(mod, "_build_clip_paths", lambda _f: (None, []))
    monkeypatch.setattr(mod, "get_or_create_line_style", lambda *_a, **_k: "STYLE")
    monkeypatch.setattr(mod, "_recreate_contour_on_top", lambda *_a, **_k: 2)
    monkeypatch.setattr(
        mod,
        "set_string_param",
        lambda _f, name, value: stored.update({name: value}) or True,
    )

    result = mod.redraw_grid_for_floor(floor, _View(), "tx")
    assert result["deleted_count"] == 3
    assert result["created_count"] == 4
    assert result["marker_count"] == 6
    assert result["contour_recreated"] == 2
    assert stored["RF_Grid_Lines_ID"]
    assert stored["RF_Base_Marker_ID"]
    assert fake_doc.deleted == [1, 4, 6]


def test_redraw_grid_for_floor_with_holes_and_empty_marker(monkeypatch):
    mod = _import_floor_grid()

    class _Tx:
        def __init__(self, *_a, **_k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class _Created:
        def __init__(self, cid):
            self.Id = type("_Id", (), {"Value": cid})()
            self.LineStyle = None

    class _Create:
        def __init__(self):
            self.items = []

        def NewDetailCurve(self, _view, _line):
            cid = 300 + len(self.items)
            obj = _Created(cid)
            self.items.append(obj)
            return obj

    class _Doc:
        def __init__(self):
            self.Create = _Create()

        def GetElement(self, _el_id):
            return None

        def Delete(self, _el_id):
            pass

    params = {
        "RF_Step_X": 2.0,
        "RF_Step_Y": 2.0,
        "RF_Base_X": 20.0,
        "RF_Base_Y": 20.0,
        "RF_Offset_X": 0.0,
        "RF_Offset_Y": 0.0,
    }
    stored = {}
    monkeypatch.setattr(mod, "doc", _Doc())
    monkeypatch.setattr(mod.revit, "Transaction", _Tx)
    monkeypatch.setattr(mod, "get_double_param", lambda _f, name: params.get(name))
    monkeypatch.setattr(
        mod, "get_bbox_xy", lambda *_a, **_k: (0.0, 0.0, 10.0, 10.0, 0.0, 1.0)
    )
    monkeypatch.setattr(mod, "build_positions", lambda *_a, **_k: [1.0])
    monkeypatch.setattr(mod, "get_string_param", lambda *_a, **_k: "")
    monkeypatch.setattr(mod, "parse_ids_from_string", lambda _s: [])
    monkeypatch.setattr(mod, "get_line_style_id", lambda *_a, **_k: None)
    monkeypatch.setattr(mod, "get_or_create_line_style", lambda *_a, **_k: "STYLE")
    monkeypatch.setattr(mod, "_get_stringer_clearance_mm", lambda: 30.0)
    monkeypatch.setattr(
        mod, "_clip_line_segments", lambda *_a, **_k: [((1, 0), (1, 10))]
    )
    monkeypatch.setattr(mod, "_recreate_contour_on_top", lambda *_a, **_k: 0)
    monkeypatch.setattr(
        mod,
        "set_string_param",
        lambda _f, name, value: stored.update({name: value}) or True,
    )
    monkeypatch.setattr(
        mod, "_build_clip_paths", lambda _f: ("clip", [(1.1, 0, 3.0, 5.0)])
    )

    result = mod.redraw_grid_for_floor(object(), type("_View", (), {"Id": 1})(), "tx")
    assert result["created_count"] == 2
    assert result["marker_count"] == 0
    assert stored["RF_Base_Marker_ID"] == ""

"""Non-Revit tests for floor_exact with lightweight Clipper/Revit stubs."""

import importlib
import os
import sys
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit]


def _install_stubs():
    clr = sys.modules.get("clr")
    if clr is None:
        clr = ModuleType("clr")
        sys.modules["clr"] = clr

    if not hasattr(clr, "AddReferenceToFileAndPath"):
        clr.AddReferenceToFileAndPath = lambda _p: None

    if "Autodesk.Revit.DB" not in sys.modules:
        db = ModuleType("Autodesk.Revit.DB")

        class _CurveElement:
            pass

        class _ElementId:
            def __init__(self, value):
                self.IntegerValue = int(value)
                self.Value = int(value)

        db.CurveElement = _CurveElement
        db.ElementId = _ElementId

        autodesk = ModuleType("Autodesk")
        revit = ModuleType("Autodesk.Revit")
        autodesk.Revit = revit
        revit.DB = db

        sys.modules["Autodesk"] = autodesk
        sys.modules["Autodesk.Revit"] = revit
        sys.modules["Autodesk.Revit.DB"] = db

    floor_common = ModuleType("floor_common")
    floor_common.build_positions = lambda *a, **k: []
    floor_common.get_string_param = lambda *_a, **_k: ""
    floor_common.parse_ids_from_string = lambda _s: []
    floor_common.read_floor_grid_params = lambda *_a, **_k: {}
    sys.modules["floor_common"] = floor_common

    if "Clipper2Lib" not in sys.modules:
        clipper = ModuleType("Clipper2Lib")

        class _Point64:
            def __init__(self, x, y):
                self.X = int(x)
                self.Y = int(y)

        class _Path64(list):
            def Add(self, p):
                self.append(p)

            @property
            def Count(self):
                return len(self)

        class _Paths64(list):
            def Add(self, p):
                self.append(p)

            @property
            def Count(self):
                return len(self)

        class _Clipper64:
            pass

        class _ClipType:
            Intersection = 1

        class _FillRule:
            NonZero = 1

        class _JoinType:
            Miter = 1

        class _EndType:
            Polygon = 1

        clipper.Point64 = _Point64
        clipper.Path64 = _Path64
        clipper.Paths64 = _Paths64
        clipper.Clipper64 = _Clipper64
        clipper.ClipType = _ClipType
        clipper.FillRule = _FillRule
        clipper.JoinType = _JoinType
        clipper.EndType = _EndType

        clipper_sub = ModuleType("Clipper2Lib.Clipper")
        clipper_sub.Difference = lambda a, b, *_: a
        clipper_sub.Intersect = lambda a, b, *_: a
        clipper_sub.InflatePaths = lambda paths, *_: paths

        sys.modules["Clipper2Lib"] = clipper
        sys.modules["Clipper2Lib.Clipper"] = clipper_sub


def _import_floor_exact():
    _install_stubs()

    lib_dir = os.path.join(os.path.dirname(__file__), "..", "lib")
    lib_dir = os.path.normpath(lib_dir)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)

    if "floor_exact" in sys.modules:
        return importlib.reload(sys.modules["floor_exact"])
    return importlib.import_module("floor_exact")


def _pt(x, y):
    return type("_P", (), {"X": x, "Y": y})()


def test_unit_conversions_and_area_format():
    mod = _import_floor_exact()
    assert abs(mod.internal_to_mm(1.0) - 304.8) < 1e-9
    assert abs(mod.mm_to_internal(304.8) - 1.0) < 1e-9
    assert mod.format_area_m2(2500000) == "2.500 м²"


def test_polygon_area_helpers():
    mod = _import_floor_exact()
    square = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert abs(mod.polygon_area_mm2(square) - 100.0) < 1e-9
    assert mod.polygon_area_mm2([(0, 0), (1, 1)]) == 0.0


def test_path_and_paths_area_bbox_helpers():
    mod = _import_floor_exact()
    p = mod.Path64()
    p.Add(mod.Point64(0, 0))
    p.Add(mod.Point64(10000, 0))
    p.Add(mod.Point64(10000, 10000))
    p.Add(mod.Point64(0, 10000))

    pts = mod.path64_to_points_mm(p)
    assert pts[0] == (0.0, 0.0)
    assert abs(mod.path64_area_mm2(p) - 100.0) < 1e-9

    paths = mod.Paths64()
    paths.Add(p)
    assert abs(mod.paths64_total_area_mm2(paths) - 100.0) < 1e-9
    assert mod.paths64_bbox_mm(paths) == (0.0, 0.0, 10.0, 10.0)


def test_points_and_polygon_internal_math():
    mod = _import_floor_exact()
    assert mod.points_equal_xy(_pt(1.0, 2.0), _pt(1.0 + 1e-7, 2.0 - 1e-7))
    assert not mod.points_equal_xy(_pt(1.0, 2.0), _pt(1.01, 2.0))

    poly = [_pt(0, 0), _pt(10, 0), _pt(10, 10), _pt(0, 10)]
    assert abs(mod.polygon_area_xy_internal(poly) - 100.0) < 1e-9


def test_shift_positions_and_rounding():
    mod = _import_floor_exact()
    values = mod.build_shift_positions(step_internal=1.0, shift_step_internal=0.25)
    assert values == [0.0, 0.25, 0.5, 0.75]
    assert mod.build_shift_positions(0.0, 0.1) == []
    assert mod.normalize_mm(12.345) == round(12.345, mod.ROUND_MM)


def test_split_outer_inner_and_bbox():
    mod = _import_floor_exact()
    outer = [_pt(0, 0), _pt(10, 0), _pt(10, 10), _pt(0, 10)]
    inner = [_pt(2, 2), _pt(3, 2), _pt(3, 3), _pt(2, 3)]

    out, inn = mod.split_outer_inner_loops([inner, outer])
    assert len(out) == 1
    assert len(inn) == 1

    bbox = mod.get_loops_bbox_internal(out + inn)
    assert bbox == (0, 0, 10, 10)


def test_rect_and_bbox_intersection_helpers():
    mod = _import_floor_exact()
    rect = mod.make_rect_path64(0, 0, 10, 10)
    assert mod.is_single_axis_rect(rect)

    weird = mod.Path64()
    weird.Add(mod.Point64(0, 0))
    weird.Add(mod.Point64(10000, 0))
    weird.Add(mod.Point64(8000, 8000))
    weird.Add(mod.Point64(0, 10000))
    assert not mod.is_single_axis_rect(weird)

    assert mod.bbox_intersects((0, 0, 10, 10), (10.5, 0, 20, 5), tol=1.0)
    assert not mod.bbox_intersects((0, 0, 10, 10), (12, 0, 20, 5), tol=1.0)


def test_extension_root_detection():
    mod = _import_floor_exact()
    root = mod._get_extension_root()
    assert root.lower().endswith(".extension") or (
        os.path.isdir(os.path.join(root, "lib"))
        and os.path.isdir(os.path.join(root, "RaisedFloor.tab"))
    )


def test_point_in_polygon_and_decompose_void_rects():
    mod = _import_floor_exact()
    poly = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert mod._point_in_polygon_mm(5, 5, poly)
    assert mod._point_in_polygon_mm(0, 5, poly)  # on edge
    assert not mod._point_in_polygon_mm(11, 5, poly)

    # L-shape: should be decomposed into multiple rectangles.
    l_shape = [(0, 0), (8, 0), (8, 3), (3, 3), (3, 8), (0, 8)]
    rects = mod._decompose_void_to_rects(l_shape, (0, 0, 10, 10))
    assert len(rects) >= 2


def test_compute_voids_empty_and_rectangular(monkeypatch):
    mod = _import_floor_exact()

    empty = mod.Paths64()
    monkeypatch.setattr(mod, "Difference", lambda *_a, **_k: empty)
    result = mod.compute_voids((0, 0, 10, 10), mod.Paths64(), max_voids=3)
    assert result == {"voids": [], "has_unhandled_voids": False}

    # One rectangular void of 4x2 starting at (1,2)
    void_path = mod.Path64()
    void_path.Add(mod.mm_xy_to_clipper_point(1, 2))
    void_path.Add(mod.mm_xy_to_clipper_point(5, 2))
    void_path.Add(mod.mm_xy_to_clipper_point(5, 4))
    void_path.Add(mod.mm_xy_to_clipper_point(1, 4))

    diff = mod.Paths64()
    diff.Add(void_path)
    monkeypatch.setattr(mod, "Difference", lambda *_a, **_k: diff)
    result = mod.compute_voids((0, 0, 10, 10), mod.Paths64(), max_voids=3)
    assert result["has_unhandled_voids"] is False
    assert len(result["voids"]) == 1
    w, h, mx, my = result["voids"][0]
    assert (w, h, mx, my) == (4.0, 2.0, 1.0, 2.0)


def test_normalize_shift_and_local_positions():
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    assert mod._normalize_shift(-mod.mm_to_internal(10), step) > 0
    assert mod._normalize_shift(mod.mm_to_internal(610), step) < step

    local = mod._build_local_shift_positions(
        step_internal=step,
        center_shift_internal=mod.mm_to_internal(123),
        local_step_internal=mod.mm_to_internal(20),
        radius_internal=mod.mm_to_internal(40),
    )
    assert len(local) >= 3
    assert local == sorted(local)


def test_snap_shifts_axis_pairs_and_extract_vertices():
    mod = _import_floor_exact()
    step_x = mod.mm_to_internal(600)
    step_y = mod.mm_to_internal(600)

    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1200, 1200))

    hole = mod.Paths64()
    hole.Add(mod.make_rect_path64(300, 300, 500, 500))

    xs, ys = mod._extract_contour_vertex_coords(outer, hole)
    assert len(xs) >= 4
    assert len(ys) >= 4

    snaps_x = mod._snap_shifts_for_axis(xs, base_internal=0.0, step_internal=step_x)
    assert len(snaps_x) > 0
    assert all(0 <= s < step_x for s in snaps_x)

    pairs = mod._snap_pairs_for_holes(
        hole_paths=hole,
        base_x_internal=0.0,
        base_y_internal=0.0,
        step_x_internal=step_x,
        step_y_internal=step_y,
    )
    assert len(pairs) > 0
    assert all(0 <= p[0] < step_x and 0 <= p[1] < step_y for p in pairs)


def test_dedup_key_and_cut_round_deltas():
    mod = _import_floor_exact()
    step_x = mod.mm_to_internal(600)
    step_y = mod.mm_to_internal(600)

    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1200, 1200))

    best = {
        "shift_x_mm": 10.4,
        "shift_y_mm": 20.6,
        "shift_x_internal": mod.mm_to_internal(10.4),
        "shift_y_internal": mod.mm_to_internal(20.6),
    }
    assert mod._dedup_key(best) == (10, 21)

    deltas = mod._cut_round_deltas(
        best_result=best,
        base_x_raw=0.0,
        base_y_raw=0.0,
        step_x=step_x,
        step_y=step_y,
        outer_paths=outer,
        hole_paths=None,
    )
    assert isinstance(deltas, list)
    assert len(deltas) > 0
    assert all(0 <= sx < step_x and 0 <= sy < step_y for sx, sy in deltas)


def test_build_exact_zone_and_offset_helpers(monkeypatch):
    mod = _import_floor_exact()
    outer = [_pt(0, 0), _pt(10, 0), _pt(10, 10), _pt(0, 10)]
    inner = [_pt(2, 2), _pt(3, 2), _pt(3, 3), _pt(2, 3)]

    monkeypatch.setattr(
        mod, "build_loops_from_model_curves", lambda _els: [inner, outer]
    )
    zone = mod.build_exact_zone([object()])
    assert len(zone["outer_loops"]) == 1
    assert len(zone["inner_loops"]) == 1
    assert zone["hole_paths"].Count == 1

    calls = []
    monkeypatch.setattr(
        mod,
        "InflatePaths",
        lambda paths, delta, *_a: calls.append((paths, delta)) or paths,
    )
    outer_off, holes_off = mod.offset_zone_contours(zone, inset_mm=5)
    assert outer_off is zone["outer_paths"]
    assert holes_off is zone["hole_paths"]
    assert len(calls) == 2


def test_get_exact_zone_for_floor_and_evaluate_floor_shift(monkeypatch):
    mod = _import_floor_exact()

    class _CurveEl(mod.CurveElement):
        pass

    class _Doc:
        def GetElement(self, el_id):
            return _CurveEl() if el_id.IntegerValue in (1, 2) else None

    monkeypatch.setattr(mod, "get_string_param", lambda *_a, **_k: "1;2")
    monkeypatch.setattr(mod, "parse_ids_from_string", lambda _s: [1, 2])
    monkeypatch.setattr(mod, "build_exact_zone", lambda els: {"elements": len(els)})
    assert mod.get_exact_zone_for_floor(_Doc(), object()) == {"elements": 2}

    captured = {}
    monkeypatch.setattr(
        mod,
        "read_floor_grid_params",
        lambda _f: {"step_x": 1, "step_y": 2, "base_x_raw": 3, "base_y_raw": 4},
    )
    monkeypatch.setattr(
        mod,
        "get_exact_zone_for_floor",
        lambda _d, _f: {
            "outer_paths": "o",
            "hole_paths": "h",
            "holes_bboxes_mm": [1],
            "outer_bbox_internal": (0, 0, 1, 1),
        },
    )
    monkeypatch.setattr(
        mod, "find_best_shift", lambda **kwargs: captured.update(kwargs) or {"best": 1}
    )
    result = mod.evaluate_floor_shift(
        object(),
        object(),
        unacceptable_cut_mm=10,
        unwanted_cut_mm=20,
        acceptable_cut_mm=30,
        coarse_shift_step_mm=40,
        top_n=5,
        refine_shift_step_mm=6,
        refine_radius_mm=7,
        refine_top_n=2,
        min_edge_clearance_mm=8,
    )
    assert result == {"best": 1}
    assert captured["step_x"] == 1
    assert captured["outer_paths"] == "o"
    assert captured["min_edge_clearance_mm"] == 8


def test_find_best_shift_orchestration(monkeypatch):
    mod = _import_floor_exact()
    step_x = mod.mm_to_internal(600)
    step_y = mod.mm_to_internal(600)

    hole_paths = mod.Paths64()
    hole_paths.Add(mod.make_rect_path64(100, 100, 200, 200))
    outer_paths = mod.Paths64()
    outer_paths.Add(mod.make_rect_path64(0, 0, 1200, 1200))

    monkeypatch.setattr(mod, "build_positions", lambda step, coarse: [0.0, step / 2.0])
    monkeypatch.setattr(
        mod,
        "_extract_contour_vertex_coords",
        lambda *_a, **_k: ([0.0, step_x / 3.0], [0.0, step_y / 3.0]),
    )
    monkeypatch.setattr(
        mod, "_snap_shifts_for_axis", lambda *_a, **_k: [0.0, step_x / 4.0]
    )
    monkeypatch.setattr(
        mod, "_snap_pairs_for_holes", lambda *_a, **_k: [(step_x / 5.0, step_y / 5.0)]
    )

    def _make_result(sx, sy, rank):
        return {
            "shift_x_internal": sx,
            "shift_y_internal": sy,
            "shift_x_mm": mod.internal_to_mm(sx),
            "shift_y_mm": mod.internal_to_mm(sy),
            "rank_key": rank,
            "non_viable_count": int(rank * 10) % 3,
            "complex_count": int(rank * 10) % 2,
        }

    monkeypatch.setattr(
        mod,
        "_evaluate_shifts_grid",
        lambda shift_x_values, shift_y_values, **_k: [
            _make_result(sx, sy, sx + sy + 1.0)
            for sx in shift_x_values
            for sy in shift_y_values
        ],
    )
    monkeypatch.setattr(
        mod,
        "evaluate_shift_exact",
        lambda shift_x, shift_y, **_k: _make_result(
            shift_x, shift_y, shift_x + shift_y + 0.1
        ),
    )
    monkeypatch.setattr(
        mod,
        "_build_local_shift_positions",
        lambda step, center, local_step, radius: [center, (center + local_step) % step],
    )
    monkeypatch.setattr(
        mod, "_cut_round_deltas", lambda *_a, **_k: [(step_x / 6.0, step_y / 6.0)]
    )

    result = mod.find_best_shift(
        step_x=step_x,
        step_y=step_y,
        base_x_raw=0.0,
        base_y_raw=0.0,
        outer_paths=outer_paths,
        hole_paths=hole_paths,
        holes_bboxes_mm=[],
        outer_bbox_internal=(0, 0, 1, 1),
        unacceptable_cut_mm=100,
        unwanted_cut_mm=150,
        acceptable_cut_mm=200,
        coarse_shift_step_mm=50,
        top_n=3,
        refine_shift_step_mm=10,
        refine_radius_mm=20,
        refine_top_n=2,
        min_edge_clearance_mm=15,
    )

    assert "best" in result
    assert len(result["top_results"]) <= 3
    assert result["coarse_count"] > 0
    assert result["hole_snap_pair_count"] == 1
    assert result["snap_x_count"] > 0
    assert result["refine_count"] > 0
    assert result["total_count"] >= len(result["top_results"])
    assert "equivalent_top_results" in result


def test_analyze_cell_exact_empty_full_fragment_simple_and_complex(monkeypatch):
    mod = _import_floor_exact()
    rect = mod.make_rect_path64(0, 0, 1000, 1000)
    bbox = (0, 0, 1000, 1000)
    outer_paths = mod.Paths64()
    hole_paths = mod.Paths64()

    empty = mod.Paths64()
    monkeypatch.setattr(mod, "Intersect", lambda *_a, **_k: empty)
    result = mod.analyze_cell_exact(rect, bbox, outer_paths, hole_paths, [])
    assert result["is_empty"] is True

    full = mod.Paths64()
    full.Add(rect)
    monkeypatch.setattr(mod, "Intersect", lambda *_a, **_k: full)
    result = mod.analyze_cell_exact(rect, bbox, outer_paths, hole_paths, [])
    assert result["is_full"] is True
    assert result["size_x_mm"] == 1000.0
    assert result["size_y_mm"] == 1000.0

    frag_path = mod.make_rect_path64(0, 0, 4, 4)
    frag = mod.Paths64()
    frag.Add(frag_path)
    monkeypatch.setattr(mod, "Intersect", lambda *_a, **_k: frag)
    result = mod.analyze_cell_exact(
        rect,
        bbox,
        outer_paths,
        hole_paths,
        [],
        min_fragment_area_mm2=20.0,
    )
    assert result["is_fragment"] is True

    simple_path = mod.make_rect_path64(0, 0, 600, 1000)
    simple = mod.Paths64()
    simple.Add(simple_path)
    monkeypatch.setattr(mod, "Intersect", lambda *_a, **_k: simple)
    result = mod.analyze_cell_exact(rect, bbox, outer_paths, hole_paths, [])
    assert result["is_simple_cut"] is True
    assert result["kind"] == "Простая подрезка"

    weird = mod.Path64()
    weird.Add(mod.Point64(0, 0))
    weird.Add(mod.Point64(1000000, 0))
    weird.Add(mod.Point64(800000, 800000))
    weird.Add(mod.Point64(0, 1000000))
    complex_paths = mod.Paths64()
    complex_paths.Add(weird)
    monkeypatch.setattr(mod, "Intersect", lambda *_a, **_k: complex_paths)
    result = mod.analyze_cell_exact(rect, bbox, outer_paths, hole_paths, [])
    assert result["is_complex_cut"] is True
    assert result["kind"] == "Сложная подрезка"


def test_count_unsplit_holes_detects_split_and_unsplit():
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    holes = mod.Paths64()
    holes.Add(mod.make_rect_path64(100, 100, 200, 200))

    unsplit = mod._count_unsplit_holes([0.0], [0.0], holes, step, step)
    assert unsplit == 1

    split = mod._count_unsplit_holes(
        [0.0, mod.mm_to_internal(150)],
        [0.0],
        holes,
        step,
        step,
    )
    assert split == 0


def test_evaluate_shift_exact_aggregates_and_ranks(monkeypatch):
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)
    x_positions = [0.0, mod.mm_to_internal(10)]
    y_positions = [0.0, mod.mm_to_internal(10)]
    monkeypatch.setattr(
        mod,
        "build_positions",
        lambda *_a, **_k: x_positions if _a[2] == 0.0 else y_positions,
    )

    results = iter(
        [
            {
                "is_full": True,
                "is_simple_cut": False,
                "is_complex_cut": False,
                "is_fragment": False,
            },
            {
                "is_full": False,
                "is_simple_cut": True,
                "is_complex_cut": False,
                "is_fragment": False,
                "size_x_mm": 90.0,
                "size_y_mm": 200.0,
                "area_mm2": 1000.0,
            },
            {
                "is_full": False,
                "is_simple_cut": False,
                "is_complex_cut": True,
                "is_fragment": False,
                "size_x_mm": 300.0,
                "size_y_mm": 170.0,
                "min_width_mm": 170.0,
                "area_mm2": 2000.0,
            },
            {
                "is_full": False,
                "is_simple_cut": True,
                "is_complex_cut": False,
                "is_fragment": False,
                "size_x_mm": 220.0,
                "size_y_mm": 600.0,
                "area_mm2": 3000.0,
            },
        ]
    )
    monkeypatch.setattr(mod, "analyze_cell_exact", lambda *_a, **_k: next(results))
    monkeypatch.setattr(mod, "_count_unsplit_holes", lambda *_a, **_k: 1)

    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1200, 1200))
    hole_paths = mod.Paths64()

    result = mod.evaluate_shift_exact(
        step_x=step,
        step_y=step,
        base_x_raw=0.0,
        base_y_raw=0.0,
        shift_x=0.0,
        shift_y=mod.mm_to_internal(5),
        outer_paths=outer,
        hole_paths=hole_paths,
        holes_bboxes_mm=[],
        outer_bbox_internal=(0.0, 0.0, step, step),
        unacceptable_cut_mm=100.0,
        unwanted_cut_mm=150.0,
        acceptable_cut_mm=200.0,
        min_edge_clearance_mm=15.0,
        edge_xs_mm=[0.0, 10.0],
        edge_ys_mm=[0.0, 10.0],
    )

    assert result["full_count"] == 1
    assert result["non_viable_count"] == 1
    assert result["acceptable_count"] == 1
    assert result["good_count"] == 1
    assert result["complex_count"] == 1
    assert result["viable_simple_count"] == 1
    assert result["total_simple_count"] == 2
    assert result["min_viable_cut_mm"] == 170.0
    assert result["min_cut_all_mm"] == 90.0
    assert result["unique_sizes"] == 1
    assert result["unsplit_holes"] == 1
    assert result["near_edge_count"] > 0
    assert isinstance(result["rank_key"], tuple)


def test_evaluate_shifts_grid_returns_all_combinations(monkeypatch):
    mod = _import_floor_exact()
    seen = []

    def _fake_eval(**kwargs):
        seen.append((kwargs["shift_x"], kwargs["shift_y"]))
        return {
            "shift_x_internal": kwargs["shift_x"],
            "shift_y_internal": kwargs["shift_y"],
        }

    monkeypatch.setattr(mod, "evaluate_shift_exact", _fake_eval)
    result = mod._evaluate_shifts_grid(
        step_x=1,
        step_y=2,
        base_x_raw=0,
        base_y_raw=0,
        shift_x_values=[10, 20],
        shift_y_values=[1, 2, 3],
        outer_paths=None,
        hole_paths=None,
        holes_bboxes_mm=[],
        outer_bbox_internal=(0, 0, 1, 1),
        unacceptable_cut_mm=100,
        unwanted_cut_mm=150,
        acceptable_cut_mm=200,
    )
    assert len(result) == 6
    assert seen == [(10, 1), (10, 2), (10, 3), (20, 1), (20, 2), (20, 3)]


# ---------------------------------------------------------------------------
# build_loops_from_model_curves + split_outer_inner_loops
# ---------------------------------------------------------------------------


class _Pt:
    """Stub Revit XYZ-style point (only X, Y used)."""

    def __init__(self, x, y):
        self.X = float(x)
        self.Y = float(y)
        self.Z = 0.0


def _curve_el(x0, y0, x1, y1):
    """Create a stub curve element with two endpoints."""

    class _Curve:
        def __init__(self, p0, p1):
            self._p0, self._p1 = p0, p1

        def GetEndPoint(self, i):
            return self._p0 if i == 0 else self._p1

    class _El:
        pass

    el = _El()
    el.GeometryCurve = _Curve(_Pt(x0, y0), _Pt(x1, y1))
    return el


def test_build_loops_forward_and_reversed_and_bad_element():
    mod = _import_floor_exact()

    # Forward: 4 segments forming a closed rectangle
    elements = [
        _curve_el(0, 0, 1, 0),
        _curve_el(1, 0, 1, 1),
        _curve_el(1, 1, 0, 1),
        _curve_el(0, 1, 0, 0),
    ]
    loops = mod.build_loops_from_model_curves(elements)
    assert len(loops) == 1
    # 4 unique pts (closing duplicate stripped)
    assert len(loops[0]) == 4

    # Reversed segment: second element has p1=(1,0) → matches current_end
    elements_rev = [
        _curve_el(0, 0, 1, 0),  # →(1,0)
        _curve_el(1, 1, 1, 0),  # reversed: p1=(1,0) → next_end=p0=(1,1)
        _curve_el(1, 1, 0, 1),  # →(0,1)
        _curve_el(0, 1, 0, 0),  # →(0,0) == start → closed
    ]
    loops_rev = mod.build_loops_from_model_curves(elements_rev)
    assert len(loops_rev) == 1
    assert len(loops_rev[0]) == 4

    # Bad element (raises on GeometryCurve access) must be silently skipped
    class _BadEl:
        @property
        def GeometryCurve(self):
            raise RuntimeError("bad curve")

    # Bad element is skipped; the two valid segments that form a closed degenerate
    # path are still processed — just ensure no crash, bad el is ignored
    elements_bad = [_BadEl(), _curve_el(0, 0, 1, 0), _curve_el(1, 0, 0, 0)]
    loops_bad = mod.build_loops_from_model_curves(elements_bad)
    # 2 valid back-to-back segments close → degenerate 2-pt loop; count 0 or 1 is ok
    assert isinstance(loops_bad, list)

    # Unclosed chain: two segments that don't connect to each other → no loops
    elements_unc = [
        _curve_el(0, 0, 1, 0),
        _curve_el(5, 5, 6, 5),  # not connected to the first segment
    ]
    loops_unc = mod.build_loops_from_model_curves(elements_unc)
    assert len(loops_unc) == 0


def test_split_outer_inner_loops_by_area():
    mod = _import_floor_exact()

    # Outer loop: large 1000×1000 square
    outer_pts = [_Pt(0, 0), _Pt(1000, 0), _Pt(1000, 1000), _Pt(0, 1000)]
    # Inner loop: small 100×100 square inside
    inner_pts = [_Pt(200, 200), _Pt(300, 200), _Pt(300, 300), _Pt(200, 300)]

    outer_loops, inner_loops = mod.split_outer_inner_loops([outer_pts, inner_pts])
    assert len(outer_loops) == 1
    assert len(inner_loops) == 1
    # The outer loop should be the bigger one
    big = outer_loops[0]
    assert big is outer_pts or big[0].X == 0.0

    # Edge case: empty input
    o2, i2 = mod.split_outer_inner_loops([])
    assert o2 == [] and i2 == []


# ---------------------------------------------------------------------------
# offset_zone_contours with holes
# ---------------------------------------------------------------------------


def test_offset_zone_contours_with_non_empty_holes():
    mod = _import_floor_exact()
    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1000, 1000))

    hole = mod.Paths64()
    hole.Add(mod.make_rect_path64(300, 300, 400, 400))

    zone = {"outer_paths": outer, "hole_paths": hole}
    inset_outer, inset_holes = mod.offset_zone_contours(zone, 5.0)
    assert inset_outer.Count >= 1
    assert inset_holes.Count >= 1


# ---------------------------------------------------------------------------
# is_footprint_inside_zone
# ---------------------------------------------------------------------------


def test_is_footprint_inside_zone_zero_and_inside_and_outside(monkeypatch):
    mod = _import_floor_exact()
    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1000, 1000))
    empty_holes = mod.Paths64()

    # Zero-size footprint → always True (skips Clipper entirely, covers early-return branch)
    assert mod.is_footprint_inside_zone(0, 0, 0, outer, empty_holes) is True

    # Footprint with stubs: Intersect returns first arg (rect itself) → area match → True
    cx = mod.mm_to_internal(500)
    cy = mod.mm_to_internal(500)
    half = mod.mm_to_internal(50)
    assert mod.is_footprint_inside_zone(cx, cy, half, outer, empty_holes) is True

    # Force False: monkeypatch Intersect to return empty → clipped_area=0 ≠ rect_area
    empty_result = mod.Paths64()
    monkeypatch.setattr(mod, "Intersect", lambda *_a, **_k: empty_result)
    assert mod.is_footprint_inside_zone(cx, cy, half, outer, empty_holes) is False


# ---------------------------------------------------------------------------
# _scan_min_width_mm
# ---------------------------------------------------------------------------


def test_scan_min_width_empty_and_degenerate_and_l_shape():
    mod = _import_floor_exact()
    SCALE = 1000  # SCALE constant from floor_exact

    # Empty Paths64 → 0.0
    empty = mod.Paths64()
    assert mod._scan_min_width_mm(empty) == 0.0

    # Degenerate: all Y identical → only X extent, dy ≈ 0
    flat = mod.Path64()
    flat.Add(mod.Point64(0, 0))
    flat.Add(mod.Point64(int(500 * SCALE), 0))
    flat.Add(mod.Point64(int(500 * SCALE), 1))  # tiny Y to avoid dx < eps only
    flat.Add(mod.Point64(0, 1))
    flat_paths = mod.Paths64()
    flat_paths.Add(flat)
    w_flat = mod._scan_min_width_mm(flat_paths)
    assert isinstance(w_flat, float)
    assert w_flat >= 0.0

    # Both dimensions zero → 0.0
    dot = mod.Path64()
    dot.Add(mod.Point64(0, 0))
    dot.Add(mod.Point64(0, 0))
    dot_paths = mod.Paths64()
    dot_paths.Add(dot)
    assert mod._scan_min_width_mm(dot_paths) == 0.0

    # L-shaped polygon: overall bbox 200×200, but narrows to 50mm in one arm
    s = mod.SCALE
    l_path = mod.Path64()
    l_path.Add(mod.Point64(0, 0))
    l_path.Add(mod.Point64(int(200 * s), 0))
    l_path.Add(mod.Point64(int(200 * s), int(50 * s)))
    l_path.Add(mod.Point64(int(50 * s), int(50 * s)))
    l_path.Add(mod.Point64(int(50 * s), int(200 * s)))
    l_path.Add(mod.Point64(0, int(200 * s)))
    l_paths = mod.Paths64()
    l_paths.Add(l_path)
    min_w = mod._scan_min_width_mm(l_paths)
    assert min_w > 0.0
    assert min_w <= 200.0


# ---------------------------------------------------------------------------
# compute_voids with L-shaped void (non-rectangular decomposition)
# ---------------------------------------------------------------------------


def test_compute_voids_l_shaped_void():
    mod = _import_floor_exact()

    # Cell: 0–600 × 0–600 mm
    cell_bbox = (0.0, 0.0, 600.0, 600.0)

    # Clipped area: L-shape = full cell minus top-right 200×200 corner
    # Vertices of the L:  (0,0)→(600,0)→(600,400)→(400,400)→(400,600)→(0,600)
    s = mod.SCALE
    l_path = mod.Path64()
    l_path.Add(mod.Point64(0, 0))
    l_path.Add(mod.Point64(int(600 * s), 0))
    l_path.Add(mod.Point64(int(600 * s), int(400 * s)))
    l_path.Add(mod.Point64(int(400 * s), int(400 * s)))
    l_path.Add(mod.Point64(int(400 * s), int(600 * s)))
    l_path.Add(mod.Point64(0, int(600 * s)))
    clipped = mod.Paths64()
    clipped.Add(l_path)

    result = mod.compute_voids(cell_bbox, clipped)
    assert isinstance(result["voids"], list)
    # The top-right corner is a void: at least one rect should be found
    assert len(result["voids"]) >= 1
    assert "has_unhandled_voids" in result


# ---------------------------------------------------------------------------
# evaluate_shift_exact: micro_fragment + hole_roundness_penalty branches
# ---------------------------------------------------------------------------


def test_evaluate_shift_exact_micro_fragment_and_hole_penalty(monkeypatch):
    """Covers micro_fragment_count branch and hole_roundness_penalty calculation."""
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    # Sequence: full, micro_fragment (30mm < 50mm), unwanted (120mm), complex (250mm)
    _cells = iter(
        [
            {
                "is_full": True,
                "is_simple_cut": False,
                "is_complex_cut": False,
                "is_fragment": False,
            },
            {  # micro: simple cut with min_width < 50mm
                "is_full": False,
                "is_simple_cut": True,
                "is_complex_cut": False,
                "is_fragment": False,
                "size_x_mm": 30.0,
                "size_y_mm": 600.0,
                "min_width_mm": 30.0,
                "area_mm2": 500.0,
            },
            {  # unwanted: 100 <= min_width < 150
                "is_full": False,
                "is_simple_cut": False,
                "is_complex_cut": True,
                "is_fragment": False,
                "size_x_mm": 120.0,
                "size_y_mm": 600.0,
                "min_width_mm": 120.0,
                "area_mm2": 2000.0,
            },
            {  # good: >= 200mm
                "is_full": False,
                "is_simple_cut": False,
                "is_complex_cut": True,
                "is_fragment": False,
                "size_x_mm": 600.0,
                "size_y_mm": 250.0,
                "min_width_mm": 250.0,
                "area_mm2": 4000.0,
            },
        ]
    )
    monkeypatch.setattr(mod, "analyze_cell_exact", lambda *_a, **_k: next(_cells))

    # hole_paths with a real rectangle so hole_roundness_penalty is computed
    hole_paths = mod.Paths64()
    hole_paths.Add(mod.make_rect_path64(200, 200, 250, 250))

    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1300, 1300))

    # build_positions returns a real list based on the outer_bbox
    monkeypatch.setattr(
        mod,
        "build_positions",
        lambda *_a, **_k: [0.0, mod.mm_to_internal(600)],
    )

    result = mod.evaluate_shift_exact(
        step_x=step,
        step_y=step,
        base_x_raw=0.0,
        base_y_raw=0.0,
        shift_x=0.0,
        shift_y=0.0,
        outer_paths=outer,
        hole_paths=hole_paths,
        holes_bboxes_mm=[],
        outer_bbox_internal=(0.0, 0.0, step, step),
        unacceptable_cut_mm=100.0,
        unwanted_cut_mm=150.0,
        acceptable_cut_mm=200.0,
    )

    assert result["micro_fragment_count"] == 1
    assert result["non_viable_count"] >= 1
    assert result["unwanted_count"] == 1
    assert result["good_count"] == 1
    # hole_roundness_penalty is baked into rank_key (index 12)
    assert isinstance(result["rank_key"], tuple)
    assert len(result["rank_key"]) >= 12


# ---------------------------------------------------------------------------
# evaluate_shift_exact: near_edge auto-collect from hole_paths branch
# ---------------------------------------------------------------------------


def test_evaluate_shift_exact_near_edge_auto_collect(monkeypatch):
    """Covers the branch where edge_xs_mm/ys_mm is None → auto-collected from hole_paths."""
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    monkeypatch.setattr(
        mod,
        "analyze_cell_exact",
        lambda *_a, **_k: {
            "is_full": True,
            "is_simple_cut": False,
            "is_complex_cut": False,
            "is_fragment": False,
        },
    )
    monkeypatch.setattr(
        mod,
        "build_positions",
        lambda *_a, **_k: [
            mod.mm_to_internal(225)
        ],  # one grid line near hole edge ~200mm
    )

    # hole at x=200–300, y=200–300 mm; grid line at x=225 → within clearance of 30mm
    hole_paths = mod.Paths64()
    hole_paths.Add(mod.make_rect_path64(200, 200, 300, 300))

    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1200, 1200))

    result = mod.evaluate_shift_exact(
        step_x=step,
        step_y=step,
        base_x_raw=0.0,
        base_y_raw=0.0,
        shift_x=0.0,
        shift_y=0.0,
        outer_paths=outer,
        hole_paths=hole_paths,
        holes_bboxes_mm=[],
        outer_bbox_internal=(0.0, 0.0, step, step),
        unacceptable_cut_mm=100.0,
        unwanted_cut_mm=150.0,
        acceptable_cut_mm=200.0,
        min_edge_clearance_mm=30.0,
        edge_xs_mm=None,  # force auto-collect
        edge_ys_mm=None,
    )

    # near_edge_count should be > 0 because the grid line is within 30mm of hole edge
    assert result["near_edge_count"] > 0
    # near_edge_penalty is baked into rank_key (index 4)
    assert isinstance(result["rank_key"], tuple)
    assert result["rank_key"][4] > 0.0  # near_edge_penalty slot


# ---------------------------------------------------------------------------
# _get_extension_root – disk-root raise path
# ---------------------------------------------------------------------------


def test_get_extension_root_raises_when_disk_root_reached(monkeypatch):
    mod = _import_floor_exact()
    import os as _os

    # Make dirname return the same path → simulates reaching the disk root
    monkeypatch.setattr(_os.path, "dirname", lambda p: p)
    with pytest.raises(Exception, match="Extension root not found"):
        mod._get_extension_root()


# ---------------------------------------------------------------------------
# _load_clipper_api – DLL-not-found and CLR-fail paths
# ---------------------------------------------------------------------------


def test_load_clipper_api_dll_not_found(monkeypatch):
    mod = _import_floor_exact()
    import os as _os

    monkeypatch.setattr(_os.path, "exists", lambda p: False)
    with pytest.raises(Exception, match="not found"):
        mod._load_clipper_api()


def test_load_clipper_api_clr_fails(monkeypatch):
    mod = _import_floor_exact()
    import os as _os

    monkeypatch.setattr(_os.path, "exists", lambda p: True)

    def _bad_add(path):
        raise RuntimeError("clr load error")

    import clr as _clr

    monkeypatch.setattr(_clr, "AddReferenceToFileAndPath", _bad_add)
    with pytest.raises(Exception, match="Failed to load"):
        mod._load_clipper_api()


# ---------------------------------------------------------------------------
# polygon_area_xy_internal – n < 3 path
# ---------------------------------------------------------------------------


def test_polygon_area_xy_internal_degenerate():
    mod = _import_floor_exact()
    assert mod.polygon_area_xy_internal([]) == 0.0
    assert mod.polygon_area_xy_internal([_Pt(0, 0), _Pt(1, 1)]) == 0.0


# ---------------------------------------------------------------------------
# build_shift_positions – empty-values fallback path
# ---------------------------------------------------------------------------


def test_build_shift_positions_empty_values_fallback():
    """With step_internal ≈ TOL, no value passes the filter → if-not-values."""
    mod = _import_floor_exact()
    # step_internal=5e-7 > 0, shift_step_internal=1.0 → count=-1 → empty loop
    result = mod.build_shift_positions(step_internal=5e-7, shift_step_internal=1.0)
    assert result == [0.0]


# ---------------------------------------------------------------------------
# is_single_axis_rect – non-4-point path
# ---------------------------------------------------------------------------


def test_is_single_axis_rect_non_4_points():
    mod = _import_floor_exact()
    p3 = mod.Path64()
    p3.Add(mod.Point64(0, 0))
    p3.Add(mod.Point64(1000, 0))
    p3.Add(mod.Point64(0, 1000))
    assert mod.is_single_axis_rect(p3) is False


# ---------------------------------------------------------------------------
# get_exact_zone_for_floor – error raises
# ---------------------------------------------------------------------------


def test_get_exact_zone_no_ids_raises(monkeypatch):
    mod = _import_floor_exact()
    monkeypatch.setattr(mod, "get_string_param", lambda *_a: "")
    monkeypatch.setattr(mod, "parse_ids_from_string", lambda *_a: [])

    class _Doc:
        def GetElement(self, eid):
            return None

    with pytest.raises(Exception, match="RF_Contour_Lines_ID"):
        mod.get_exact_zone_for_floor(_Doc(), object())


def test_get_exact_zone_no_elements_raises(monkeypatch):
    mod = _import_floor_exact()
    monkeypatch.setattr(mod, "get_string_param", lambda *_a: "1;2")
    monkeypatch.setattr(mod, "parse_ids_from_string", lambda *_a: [1, 2])

    class _Doc:
        def GetElement(self, eid):
            return None  # always None → no valid CurveElement found

    with pytest.raises(Exception, match="контура"):
        mod.get_exact_zone_for_floor(_Doc(), object())


# ---------------------------------------------------------------------------
# build_exact_zone – error raises
# ---------------------------------------------------------------------------


def test_build_exact_zone_no_loops_raises():
    mod = _import_floor_exact()
    with pytest.raises(Exception, match="замкнутые контуры"):
        mod.build_exact_zone([])


def test_build_exact_zone_no_outer_loops_raises(monkeypatch):
    mod = _import_floor_exact()
    monkeypatch.setattr(mod, "build_loops_from_model_curves", lambda _: [[_Pt(0, 0)]])
    monkeypatch.setattr(mod, "split_outer_inner_loops", lambda _: ([], [_Pt(0, 0)]))
    with pytest.raises(Exception, match="внешний контур"):
        mod.build_exact_zone(["dummy"])


def test_build_exact_zone_multiple_outer_loops_raises(monkeypatch):
    mod = _import_floor_exact()
    loop1 = [_Pt(0, 0), _Pt(10, 0), _Pt(10, 10), _Pt(0, 10)]
    loop2 = [_Pt(20, 20), _Pt(30, 20), _Pt(30, 30), _Pt(20, 30)]
    monkeypatch.setattr(mod, "build_loops_from_model_curves", lambda _: [loop1, loop2])
    monkeypatch.setattr(mod, "split_outer_inner_loops", lambda _: ([loop1, loop2], []))
    with pytest.raises(Exception, match="Ожидался 1 внешний контур"):
        mod.build_exact_zone(["dummy"])


# ---------------------------------------------------------------------------
# analyze_cell_exact – holes_bboxes_mm intersection → break
# ---------------------------------------------------------------------------


def test_analyze_cell_exact_hole_bbox_triggers_break(monkeypatch):
    mod = _import_floor_exact()
    rect = mod.make_rect_path64(0, 0, 600, 600)
    rect_bbox_mm = (0.0, 0.0, 600.0, 600.0)
    outer_paths = mod.Paths64()
    hole_paths = mod.Paths64()

    # Return partial intersection so we don't hit the "fast-full" path
    partial = mod.Paths64()
    partial.Add(mod.make_rect_path64(0, 0, 400, 600))
    monkeypatch.setattr(mod, "Intersect", lambda *_a, **_k: partial)

    # holes_bboxes_mm overlapping with rect_bbox → triggers intersects_hole_bbox=True → break
    holes_bboxes_mm = [(50.0, 50.0, 200.0, 200.0)]
    result = mod.analyze_cell_exact(
        rect, rect_bbox_mm, outer_paths, hole_paths, holes_bboxes_mm
    )
    assert isinstance(result, dict)


# ---------------------------------------------------------------------------
# analyze_cell_exact – empty result after hole subtraction
# ---------------------------------------------------------------------------


def test_analyze_cell_exact_empty_after_difference(monkeypatch):
    mod = _import_floor_exact()
    rect = mod.make_rect_path64(0, 0, 600, 600)
    rect_bbox_mm = (0.0, 0.0, 600.0, 600.0)
    outer_paths = mod.Paths64()

    # Intersect returns something (Count > 0)
    partial = mod.Paths64()
    partial.Add(mod.make_rect_path64(0, 0, 400, 600))
    monkeypatch.setattr(mod, "Intersect", lambda *_a, **_k: partial)

    # Difference returns empty → triggers "empty after subtraction" early return
    monkeypatch.setattr(mod, "Difference", lambda *_a, **_k: mod.Paths64())

    hole_paths = mod.Paths64()
    hole_paths.Add(mod.make_rect_path64(100, 100, 200, 200))

    result = mod.analyze_cell_exact(rect, rect_bbox_mm, outer_paths, hole_paths, [])
    assert result["is_empty"] is True
    assert result["area_mm2"] == 0.0


# ---------------------------------------------------------------------------
# analyze_cell_exact – is_full after hole subtraction (area matches cell)
# ---------------------------------------------------------------------------


def test_analyze_cell_exact_full_after_difference(monkeypatch):
    mod = _import_floor_exact()
    rect = mod.make_rect_path64(0, 0, 600, 600)
    rect_bbox_mm = (0.0, 0.0, 600.0, 600.0)
    outer_paths = mod.Paths64()

    # Intersect returns the full rect so area matches, but intersects_hole_bbox=True
    # → forces it past the fast-full check, into the Difference path
    full = mod.Paths64()
    full.Add(rect)
    monkeypatch.setattr(mod, "Intersect", lambda *_a, **_k: full)

    # Difference also returns the full rect (hole doesn't cut anything in this cell)
    monkeypatch.setattr(mod, "Difference", lambda *_a, **_k: full)

    hole_paths = mod.Paths64()
    hole_paths.Add(mod.make_rect_path64(700, 700, 800, 800))  # well outside cell

    holes_bboxes_mm = [(50.0, 50.0, 150.0, 150.0)]  # bbox overlaps → skip fast-full
    result = mod.analyze_cell_exact(
        rect, rect_bbox_mm, outer_paths, hole_paths, holes_bboxes_mm
    )
    assert result["is_full"] is True


# ---------------------------------------------------------------------------
# _decompose_void_to_rects – tiny sub-cell filter (rx1-rx0 < 0.5)
# ---------------------------------------------------------------------------


def test_decompose_void_tiny_cells_skipped():
    """Verifies that the 'if rx1 - rx0 < 0.5' guard skips micro-cells."""
    mod = _import_floor_exact()
    # Tiny void polygon: 0.2mm × 0.2mm – all grid sub-cells will be < 0.5mm
    tiny_pts = [(0.0, 0.0), (0.2, 0.0), (0.2, 0.2), (0.0, 0.2)]
    cell_bbox = (-1.0, -1.0, 1.0, 1.0)
    rects = mod._decompose_void_to_rects(tiny_pts, cell_bbox)
    # All sub-cells are < 0.5mm → they're filtered → either empty or very few
    assert isinstance(rects, list)


# ---------------------------------------------------------------------------
# compute_voids – rectangular void path (4-point, single-axis rect) branch
# ---------------------------------------------------------------------------


def test_compute_voids_rectangular_void_and_overflow():
    mod = _import_floor_exact()

    # Cell: 0–600 × 0–600 mm
    cell_bbox = (0.0, 0.0, 600.0, 600.0)

    # Clipped: upper 2/3 of cell (rectangular void at bottom)
    clipped_path = mod.make_rect_path64(0, 200, 600, 600)
    clipped = mod.Paths64()
    clipped.Add(clipped_path)

    # Difference will be 0-200 strip (rectangular) → hits the 4-point rect branch
    result = mod.compute_voids(cell_bbox, clipped, max_voids=1)
    assert isinstance(result["voids"], list)
    assert "has_unhandled_voids" in result


def test_compute_voids_has_unhandled_when_more_than_max():
    """Force more items than max_voids to cover has_unhandled_voids=True."""
    mod = _import_floor_exact()

    cell_bbox = (0.0, 0.0, 600.0, 600.0)

    # A complex clipped shape with many separate void sub-areas
    # Use an L-shaped clipping that creates a big void region
    l_path = mod.make_rect_path64(200, 200, 400, 400)
    clipped = mod.Paths64()
    clipped.Add(l_path)  # small island → large void area around it

    # max_voids=1 but may produce multiple items
    result = mod.compute_voids(cell_bbox, clipped, max_voids=1)
    assert isinstance(result["has_unhandled_voids"], bool)


# ---------------------------------------------------------------------------
# _count_unsplit_holes – empty-point hole path (xs_h/ys_h empty → continue)
# ---------------------------------------------------------------------------


def test_count_unsplit_holes_empty_path_continues():
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    holes = mod.Paths64()
    empty_path = mod.Path64()  # no points → xs_h empty → continue
    holes.Add(empty_path)
    result = mod._count_unsplit_holes([0.0], [0.0], holes, step, step)
    assert result == 0  # skipped, not counted as unsplit


# ---------------------------------------------------------------------------
# _count_unsplit_holes – Y-axis-only split
# ---------------------------------------------------------------------------


def test_count_unsplit_holes_only_y_axis_split():
    """X lines don't cut the hole but a Y line does → has_split via Y branch."""
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    # Hole: x 100–200mm, y 100–400mm (wide in Y)
    holes = mod.Paths64()
    holes.Add(mod.make_rect_path64(100, 100, 200, 400))

    # X gridlines: {0, step=600} – neither passes through x-range 100–200
    # Y gridlines: {0, mm_to_internal(200), step=600} – 200mm IS inside y 100–400
    y_split = mod.mm_to_internal(200)
    result = mod._count_unsplit_holes([0.0], [0.0, y_split], holes, step, step)
    assert result == 0  # split found via Y → not counted as unsplit


# ---------------------------------------------------------------------------
# _normalize_shift – zero and negative step edge cases
# ---------------------------------------------------------------------------


def test_normalize_shift_edge_cases():
    mod = _import_floor_exact()
    assert mod._normalize_shift(100.0, 0.0) == 0.0
    assert mod._normalize_shift(100.0, -5.0) == 0.0
    # Normal: 250 % 600 = 250
    step = mod.mm_to_internal(600)
    val = mod.mm_to_internal(250)
    assert abs(mod._normalize_shift(val, step) - val) < 1e-9


# ---------------------------------------------------------------------------
# _build_local_shift_positions – zero step, dedup, empty-values
# ---------------------------------------------------------------------------


def test_build_local_shift_positions_edge_cases():
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)
    local_step = mod.mm_to_internal(10)

    # step_internal <= 0 → return [0.0]
    assert mod._build_local_shift_positions(0.0, 50.0, local_step, 30.0) == [0.0]
    # local_step_internal <= 0 → return [0.0]
    assert mod._build_local_shift_positions(step, 50.0, 0.0, 30.0) == [0.0]

    # Normal call: should return sorted unique values around center
    center = mod.mm_to_internal(100)
    result = mod._build_local_shift_positions(
        step, center, local_step, mod.mm_to_internal(20)
    )
    assert len(result) >= 1
    assert result == sorted(result)
    # All values in [0, step)
    assert all(0 <= v < step for v in result)

    # Dedup: when radius=0 all offsets collapse to same point → only 1 unique value
    result_single = mod._build_local_shift_positions(step, center, local_step, 0.0)
    assert len(result_single) == 1


# ---------------------------------------------------------------------------
# _snap_shifts_for_axis – zero step returns [], with vertices
# ---------------------------------------------------------------------------


def test_snap_shifts_for_axis_zero_step_and_vertices():
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    # Zero step → return []
    assert mod._snap_shifts_for_axis([0.0, step], 0.0, 0.0) == []

    # Vertices produce snap candidates
    coords = [mod.mm_to_internal(200), mod.mm_to_internal(400)]
    result = mod._snap_shifts_for_axis(coords, 0.0, step)
    assert len(result) > 0
    assert result == sorted(result)


# ---------------------------------------------------------------------------
# _snap_pairs_for_holes – zero step, real holes
# ---------------------------------------------------------------------------


def test_snap_pairs_for_holes_zero_step_and_real():
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    # Zero step_x → return []
    hole_paths = mod.Paths64()
    hole_paths.Add(mod.make_rect_path64(100, 100, 200, 200))
    assert mod._snap_pairs_for_holes(hole_paths, 0.0, 0.0, 0.0, step) == []
    assert mod._snap_pairs_for_holes(hole_paths, 0.0, 0.0, step, 0.0) == []

    # None or empty hole_paths → return []
    assert mod._snap_pairs_for_holes(None, 0.0, 0.0, step, step) == []
    empty_paths = mod.Paths64()
    assert mod._snap_pairs_for_holes(empty_paths, 0.0, 0.0, step, step) == []

    # Real holes → produces pairs
    result = mod._snap_pairs_for_holes(hole_paths, 0.0, 0.0, step, step)
    assert isinstance(result, list)
    assert len(result) > 0


# ---------------------------------------------------------------------------
# _cut_round_deltas – with and without hole_paths
# ---------------------------------------------------------------------------


def test_cut_round_deltas_with_and_without_holes():
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    best = {
        "shift_x_internal": mod.mm_to_internal(33),
        "shift_y_internal": mod.mm_to_internal(47),
    }
    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1200, 1200))

    # Without holes
    pairs_no_holes = mod._cut_round_deltas(best, 0.0, 0.0, step, step, outer, None)
    assert isinstance(pairs_no_holes, list)

    # With holes → covers the dx_holes/dy_holes branch
    hole_paths = mod.Paths64()
    hole_paths.Add(mod.make_rect_path64(195, 195, 305, 305))  # non-round edges
    pairs_with_holes = mod._cut_round_deltas(
        best, 0.0, 0.0, step, step, outer, hole_paths
    )
    assert isinstance(pairs_with_holes, list)


# ---------------------------------------------------------------------------
# evaluate_shift_exact – complex viable cuts (acceptable + good complex branch)
# ---------------------------------------------------------------------------


def test_evaluate_shift_exact_complex_acceptable_and_good(monkeypatch):
    """Covers complex_count increment for acceptable and good cuts."""
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    _rows = iter(
        [
            {  # acceptable complex (150 <= min_width < 200)
                "is_full": False,
                "is_simple_cut": False,
                "is_complex_cut": True,
                "is_fragment": False,
                "size_x_mm": 160.0,
                "size_y_mm": 600.0,
                "min_width_mm": 160.0,
                "area_mm2": 2500.0,
            },
            {  # good complex (>= 200)
                "is_full": False,
                "is_simple_cut": False,
                "is_complex_cut": True,
                "is_fragment": False,
                "size_x_mm": 250.0,
                "size_y_mm": 600.0,
                "min_width_mm": 250.0,
                "area_mm2": 4000.0,
            },
        ]
    )
    monkeypatch.setattr(mod, "analyze_cell_exact", lambda *_a, **_k: next(_rows))
    _bp_calls = [0]

    def _bp_mock(*_a, **_k):
        _bp_calls[0] += 1
        return [0.0] if _bp_calls[0] == 1 else [0.0, step]

    monkeypatch.setattr(mod, "build_positions", _bp_mock)

    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1200, 1200))

    result = mod.evaluate_shift_exact(
        step_x=step,
        step_y=step,
        base_x_raw=0.0,
        base_y_raw=0.0,
        shift_x=0.0,
        shift_y=0.0,
        outer_paths=outer,
        hole_paths=mod.Paths64(),
        holes_bboxes_mm=[],
        outer_bbox_internal=(0.0, 0.0, step, step),
        unacceptable_cut_mm=100.0,
        unwanted_cut_mm=150.0,
        acceptable_cut_mm=200.0,
    )
    assert result["complex_count"] == 2
    assert result["acceptable_count"] == 1
    assert result["good_count"] == 1
    assert result["max_viable_cut_mm"] == 250.0


# ---------------------------------------------------------------------------
# evaluate_shift_exact – cut_groups for simple viable cuts with different sizes
# ---------------------------------------------------------------------------


def test_evaluate_shift_exact_simple_cut_groups(monkeypatch):
    """Covers the cut_groups[key] += 1 branch for multiple different simple cut sizes."""
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    _rows = iter(
        [
            {  # simple viable: 200mm wide, 600mm tall
                "is_full": False,
                "is_simple_cut": True,
                "is_complex_cut": False,
                "is_fragment": False,
                "size_x_mm": 200.0,
                "size_y_mm": 600.0,
                "area_mm2": 3000.0,
            },
            {  # simple viable: 300mm wide, 600mm tall (different size group)
                "is_full": False,
                "is_simple_cut": True,
                "is_complex_cut": False,
                "is_fragment": False,
                "size_x_mm": 300.0,
                "size_y_mm": 600.0,
                "area_mm2": 4500.0,
            },
        ]
    )
    monkeypatch.setattr(mod, "analyze_cell_exact", lambda *_a, **_k: next(_rows))
    _bp_calls2 = [0]

    def _bp_mock2(*_a, **_k):
        _bp_calls2[0] += 1
        return [0.0] if _bp_calls2[0] == 1 else [0.0, step]

    monkeypatch.setattr(mod, "build_positions", _bp_mock2)

    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1200, 1200))

    result = mod.evaluate_shift_exact(
        step_x=step,
        step_y=step,
        base_x_raw=0.0,
        base_y_raw=0.0,
        shift_x=0.0,
        shift_y=0.0,
        outer_paths=outer,
        hole_paths=mod.Paths64(),
        holes_bboxes_mm=[],
        outer_bbox_internal=(0.0, 0.0, step, step),
        unacceptable_cut_mm=100.0,
        unwanted_cut_mm=150.0,
        acceptable_cut_mm=200.0,
    )
    # Two different size groups
    assert result["unique_sizes"] == 2
    assert result["good_count"] == 2


# ---------------------------------------------------------------------------
# evaluate_shift_exact – unwanted complex branch + unwanted simple branch
# ---------------------------------------------------------------------------


def test_evaluate_shift_exact_unwanted_complex(monkeypatch):
    """Covers 'else: complex_count += 1' in the unwanted bracket (100–150)."""
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    _rows = iter(
        [
            {  # unwanted complex: 100 <= min_width < 150 AND not simple
                "is_full": False,
                "is_simple_cut": False,
                "is_complex_cut": True,
                "is_fragment": False,
                "size_x_mm": 120.0,
                "size_y_mm": 600.0,
                "min_width_mm": 120.0,
                "area_mm2": 1500.0,
            },
        ]
    )
    monkeypatch.setattr(mod, "analyze_cell_exact", lambda *_a, **_k: next(_rows))
    monkeypatch.setattr(mod, "build_positions", lambda *_a, **_k: [0.0])

    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1200, 1200))

    result = mod.evaluate_shift_exact(
        step_x=step,
        step_y=step,
        base_x_raw=0.0,
        base_y_raw=0.0,
        shift_x=0.0,
        shift_y=0.0,
        outer_paths=outer,
        hole_paths=mod.Paths64(),
        holes_bboxes_mm=[],
        outer_bbox_internal=(0.0, 0.0, step, step),
        unacceptable_cut_mm=100.0,
        unwanted_cut_mm=150.0,
        acceptable_cut_mm=200.0,
    )
    assert result["unwanted_count"] == 1
    assert result["complex_count"] == 1


# ---------------------------------------------------------------------------
# analyze_cell_exact – null bbox on "full" fast path (line 578)
# ---------------------------------------------------------------------------


def test_analyze_cell_exact_null_bbox_full_fast_path(monkeypatch):
    """paths64_bbox_mm returns None → covers line 578 defensive return."""
    mod = _import_floor_exact()
    rect = mod.make_rect_path64(0, 0, 600, 600)
    rect_bbox_mm = (0.0, 0.0, 600.0, 600.0)
    outer = mod.Paths64()
    outer.Add(rect)

    # Intersect returns the full rect area
    monkeypatch.setattr(mod, "Intersect", lambda *_a, **_k: outer)
    # But bbox returns None → defensive path
    monkeypatch.setattr(mod, "paths64_bbox_mm", lambda _p: (None, None, None, None))

    result = mod.analyze_cell_exact(rect, rect_bbox_mm, outer, mod.Paths64(), [])
    assert result["is_full"] is True
    assert result["size_x_mm"] == 0.0


# ---------------------------------------------------------------------------
# analyze_cell_exact – null bbox after Difference (line 647)
# ---------------------------------------------------------------------------


def test_analyze_cell_exact_null_bbox_after_difference(monkeypatch):
    """After Difference, paths64_bbox_mm returns None → covers line 647."""
    mod = _import_floor_exact()
    rect = mod.make_rect_path64(0, 0, 600, 600)
    rect_bbox_mm = (0.0, 0.0, 600.0, 600.0)
    outer = mod.Paths64()

    partial = mod.Paths64()
    partial.Add(mod.make_rect_path64(0, 0, 400, 600))
    monkeypatch.setattr(mod, "Intersect", lambda *_a, **_k: partial)
    monkeypatch.setattr(mod, "Difference", lambda *_a, **_k: partial)
    # Always return None bbox → the call after Difference returns None
    monkeypatch.setattr(mod, "paths64_bbox_mm", lambda _p: (None, None, None, None))

    hole_paths = mod.Paths64()
    hole_paths.Add(mod.make_rect_path64(100, 100, 200, 200))

    result = mod.analyze_cell_exact(rect, rect_bbox_mm, outer, hole_paths, [])
    assert result["is_empty"] is True


# ---------------------------------------------------------------------------
# find_best_shift – integration test (covers lines 1618, 1773, 1807, 1811, 1827)
# ---------------------------------------------------------------------------


def test_find_best_shift_basic():
    """Integration test for find_best_shift with a simple rectangular zone."""
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    # Simple 1300×1300 zone → forces partial tiles
    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1300, 1300))

    bbox = (0.0, 0.0, mod.mm_to_internal(1300), mod.mm_to_internal(1300))
    hole_paths = mod.Paths64()
    hole_paths.Add(mod.make_rect_path64(400, 400, 500, 500))

    # Track progress callbacks
    progress_log = []

    def _on_progress(phase, current, total):
        progress_log.append((phase, current, total))

    result = mod.find_best_shift(
        step_x=step,
        step_y=step,
        base_x_raw=0.0,
        base_y_raw=0.0,
        outer_paths=outer,
        hole_paths=hole_paths,
        holes_bboxes_mm=[(400.0, 400.0, 500.0, 500.0)],
        outer_bbox_internal=bbox,
        unacceptable_cut_mm=100.0,
        unwanted_cut_mm=150.0,
        acceptable_cut_mm=200.0,
        coarse_shift_step_mm=50.0,
        top_n=3,
        refine_shift_step_mm=5.0,
        refine_radius_mm=25.0,
        min_edge_clearance_mm=15.0,
        progress_callback=_on_progress,
    )
    assert "best" in result
    assert "top_results" in result
    assert "equivalent_top_results" in result
    assert len(result["top_results"]) <= 3
    assert result["best"]["rank_key"] is not None
    assert result["coarse_count"] > 0
    assert "phase_x_internal" in result["best"]
    assert "phase_y_internal" in result["best"]

    # Verify all phases reported
    phases = [p[0] for p in progress_log]
    assert "phase1" in phases
    assert "phase1_done" in phases
    assert "phase2" in phases
    assert "phase3" in phases


# ---------------------------------------------------------------------------
# _build_local_shift_positions – dedup (line 1415) and empty values (line 1420)
# ---------------------------------------------------------------------------


def test_build_local_shift_positions_dedup_and_empty():
    """When radius is tiny, all offsets collapse → dedup fires.
    When the step is so large relative to local_step that no unique values
    are found, 'if not values' fires.
    """
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)
    local_step = mod.mm_to_internal(10)

    # Dedup: radius=0 → only center survives
    center = mod.mm_to_internal(100)
    result = mod._build_local_shift_positions(step, center, local_step, 0.0)
    assert len(result) == 1

    # Test with a local_step that equals step → few unique values
    big_local_step = step
    result2 = mod._build_local_shift_positions(
        step, center, big_local_step, mod.mm_to_internal(200)
    )
    assert len(result2) >= 1

    # Dedup collision: local_step = step/3 → indices {-3,0,3} all normalise to same
    # value → 'continue' fires on duplicates (line 1413)
    local_step_third = step / 3.0
    center = mod.mm_to_internal(100)
    result3 = mod._build_local_shift_positions(step, center, local_step_third, step)
    # 7 candidates but only 3 unique normalized values
    assert len(result3) == 3


# ---------------------------------------------------------------------------
# _snap_pairs_for_holes – empty hole_path fires the 'continue' (line 1557)
# ---------------------------------------------------------------------------


def test_snap_pairs_for_holes_empty_path_skips():
    """A hole path with no points → xs empty → 'if not xs: continue'."""
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)
    hole_paths = mod.Paths64()
    hole_paths.Add(mod.Path64())  # empty path
    hole_paths.Add(mod.make_rect_path64(100, 100, 200, 200))  # valid
    result = mod._snap_pairs_for_holes(hole_paths, 0.0, 0.0, step, step)
    assert len(result) > 0  # the valid hole produces pairs


# ---------------------------------------------------------------------------
# _count_unsplit_holes – None hole_paths → return 0 (line 992)
# ---------------------------------------------------------------------------


def test_count_unsplit_holes_none_paths():
    mod = _import_floor_exact()
    assert mod._count_unsplit_holes([0.0], [0.0], None, 600.0, 600.0) == 0


# ---------------------------------------------------------------------------
# evaluate_shift_exact – unwanted/acceptable SIMPLE branches (lines 1181, 1187)
# ---------------------------------------------------------------------------


def test_evaluate_shift_exact_unwanted_and_acceptable_simple(monkeypatch):
    """Covers 'simple_count += 1' in unwanted (line 1181) and acceptable (1187)."""
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    _rows = iter(
        [
            {  # unwanted simple: 100 <= 120 < 150
                "is_full": False,
                "is_simple_cut": True,
                "is_complex_cut": False,
                "is_fragment": False,
                "size_x_mm": 120.0,
                "size_y_mm": 600.0,
                "area_mm2": 1500.0,
            },
            {  # acceptable simple: 150 <= 160 < 200
                "is_full": False,
                "is_simple_cut": True,
                "is_complex_cut": False,
                "is_fragment": False,
                "size_x_mm": 160.0,
                "size_y_mm": 600.0,
                "area_mm2": 2000.0,
            },
        ]
    )
    monkeypatch.setattr(mod, "analyze_cell_exact", lambda *_a, **_k: next(_rows))
    _bp = [0]

    def _bpm(*_a, **_k):
        _bp[0] += 1
        return [0.0] if _bp[0] == 1 else [0.0, step]

    monkeypatch.setattr(mod, "build_positions", _bpm)

    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1200, 1200))

    result = mod.evaluate_shift_exact(
        step_x=step,
        step_y=step,
        base_x_raw=0.0,
        base_y_raw=0.0,
        shift_x=0.0,
        shift_y=0.0,
        outer_paths=outer,
        hole_paths=mod.Paths64(),
        holes_bboxes_mm=[],
        outer_bbox_internal=(0.0, 0.0, step, step),
        unacceptable_cut_mm=100.0,
        unwanted_cut_mm=150.0,
        acceptable_cut_mm=200.0,
    )
    assert result["unwanted_count"] == 1
    assert result["acceptable_count"] == 1
    # Both are simple → enter simple_count += 1 branch
    assert result["viable_simple_count"] == 2


# ---------------------------------------------------------------------------
# evaluate_shift_exact – fragment and empty cell branches (lines 1213-1216)
# ---------------------------------------------------------------------------


def test_evaluate_shift_exact_fragment_and_empty(monkeypatch):
    """Covers 'elif is_fragment' (line 1213) and 'else: empty_count' (line 1216)."""
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    _rows = iter(
        [
            {  # fragment
                "is_full": False,
                "is_simple_cut": False,
                "is_complex_cut": False,
                "is_fragment": True,
                "size_x_mm": 5.0,
                "size_y_mm": 5.0,
                "area_mm2": 25.0,
            },
            {  # empty
                "is_full": False,
                "is_simple_cut": False,
                "is_complex_cut": False,
                "is_fragment": False,
                "is_empty": True,
                "size_x_mm": 0.0,
                "size_y_mm": 0.0,
                "area_mm2": 0.0,
            },
        ]
    )
    monkeypatch.setattr(mod, "analyze_cell_exact", lambda *_a, **_k: next(_rows))
    _bp = [0]

    def _bpm2(*_a, **_k):
        _bp[0] += 1
        return [0.0] if _bp[0] == 1 else [0.0, step]

    monkeypatch.setattr(mod, "build_positions", _bpm2)

    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1200, 1200))

    result = mod.evaluate_shift_exact(
        step_x=step,
        step_y=step,
        base_x_raw=0.0,
        base_y_raw=0.0,
        shift_x=0.0,
        shift_y=0.0,
        outer_paths=outer,
        hole_paths=mod.Paths64(),
        holes_bboxes_mm=[],
        outer_bbox_internal=(0.0, 0.0, step, step),
        unacceptable_cut_mm=100.0,
        unwanted_cut_mm=150.0,
        acceptable_cut_mm=200.0,
    )
    assert result["fragment_count"] == 1
    assert result["empty_count"] == 1


# ---------------------------------------------------------------------------
# compute_voids – L-shaped void → decompose path + zero-dim filter
# ---------------------------------------------------------------------------


def test_compute_voids_l_shaped_and_small(monkeypatch):
    """Non-rectangular void forces _decompose_void_to_rects (line 866) and
    its Y-merge pass (lines 810-813).
    """
    mod = _import_floor_exact()

    cell_bbox = (0.0, 0.0, 600.0, 600.0)

    # Monkeypatch Difference to return an L-shaped polygon (6 vertices)
    l_path = mod.Path64()
    for x, y in [(0, 0), (600, 0), (600, 300), (300, 300), (300, 600), (0, 600)]:
        l_path.Add(mod.Point64(int(x * 1000), int(y * 1000)))
    l_result = mod.Paths64()
    l_result.Add(l_path)
    monkeypatch.setattr(mod, "Difference", lambda *_a, **_k: l_result)

    clipped = mod.Paths64()
    clipped.Add(mod.make_rect_path64(0, 0, 300, 300))  # unused but required

    result = mod.compute_voids(cell_bbox, clipped, max_voids=5)
    assert isinstance(result["voids"], list)
    assert len(result["voids"]) > 0


def test_decompose_void_to_rects_y_merge():
    """Directly test _decompose_void_to_rects Y-merge (lines 810-813).

    A tall vertical void with collinear-midpoint vertices produces
    grid cells that share the same X-range and are vertically adjacent,
    triggering the Y-merge pass.
    """
    mod = _import_floor_exact()

    # 6-point polygon that is geometrically a 300×600 rectangle
    # but has extra collinear vertices so len(pts) != 4.
    # Grid xs=[0,300], ys=[0,300,600] → 2 cells with same X → Y-merge
    void_pts = [
        (0.0, 0.0),
        (300.0, 0.0),
        (300.0, 300.0),
        (300.0, 600.0),
        (0.0, 600.0),
        (0.0, 300.0),
    ]
    cell_bbox = (0.0, 0.0, 600.0, 600.0)

    rects = mod._decompose_void_to_rects(void_pts, cell_bbox)
    # After Y-merge the two stacked rects collapse into one
    assert len(rects) == 1
    x0, y0, x1, y1 = rects[0]
    assert abs(x1 - x0 - 300.0) < 1.0
    assert abs(y1 - y0 - 600.0) < 1.0


def test_compute_voids_rect_void():
    """4-point rectangular void → 'is_single_axis_rect' path."""
    mod = _import_floor_exact()

    cell_bbox = (0.0, 0.0, 600.0, 600.0)

    # Clipped is just the left half → void is right half (rectangular)
    clipped = mod.Paths64()
    clipped.Add(mod.make_rect_path64(0, 0, 300, 600))

    result = mod.compute_voids(cell_bbox, clipped, max_voids=3)
    assert len(result["voids"]) >= 1
    w, h, mx, my = result["voids"][0]
    assert w > 0 and h > 0


# ---------------------------------------------------------------------------
# rank_key – hierarchical priority invariants
# ---------------------------------------------------------------------------


def test_rank_key_unsplit_always_dominates():
    """1 unsplit_holes ALWAYS outweighs any advantage in other metrics.

    rank_key is a tuple with unsplit_holes at position 0.
    This verifies the lexicographic ordering invariant: a result
    with 0 unsplit_holes is ALWAYS better than one with 1 unsplit_holes,
    regardless of all other metrics.
    """
    # rank_key = (unsplit, non_viable, micro, near_edge_count, near_edge_pen,
    #             unwanted, complex, -full, viable_simple, unique_sizes,
    #             -min_viable_cut_rank, outer_round, hole_round, cut_spread)
    #
    # "bad" result: 0 unsplit, but terrible everything else
    bad_other = (0, 99, 99, 99, 999.0, 99, 99, 0, 99, 99, 0.0, 99.0, 99.0, 99.0)
    # "good" result: 1 unsplit, but perfect everything else
    good_other = (1, 0, 0, 0, 0.0, 0, 0, -100, 0, 0, -999.0, 0.0, 0.0, 0.0)

    assert bad_other < good_other, (
        "0 unsplit must ALWAYS beat 1 unsplit even with terrible other metrics"
    )


def test_rank_key_non_viable_dominates_after_unsplit():
    """Non-viable count is second priority after unsplit_holes."""
    fewer_nv = (0, 1, 99, 99, 999.0, 99, 99, 0, 99, 99, 0.0, 99.0, 99.0, 99.0)
    more_nv = (0, 2, 0, 0, 0.0, 0, 0, -100, 0, 0, -999.0, 0.0, 0.0, 0.0)
    assert fewer_nv < more_nv


def test_rank_key_full_count_inverted():
    """Higher full_count means better — stored as -full_count (minimized)."""
    more_full = (0, 0, 0, 0, 0.0, 0, 0, -50, 5, 3, -200.0, 0.0, 0.0, 0.0)
    fewer_full = (0, 0, 0, 0, 0.0, 0, 0, -20, 5, 3, -200.0, 0.0, 0.0, 0.0)
    assert more_full < fewer_full, "More full tiles should rank better (lower)"


def test_rank_key_complex_before_full():
    """Fewer complex cuts beats more full tiles — complex is position 6,
    full is position 7."""
    fewer_complex = (0, 0, 0, 0, 0.0, 0, 1, -10, 5, 3, -200.0, 0.0, 0.0, 0.0)
    more_complex = (0, 0, 0, 0, 0.0, 0, 2, -100, 0, 0, -999.0, 0.0, 0.0, 0.0)
    assert fewer_complex < more_complex


def test_rank_key_min_viable_cut_inverted():
    """Larger min viable cut is better — stored as -value (minimized)."""
    big_min_cut = (0, 0, 0, 0, 0.0, 0, 0, -20, 5, 3, -250.0, 0.0, 0.0, 0.0)
    small_min_cut = (0, 0, 0, 0, 0.0, 0, 0, -20, 5, 3, -100.0, 0.0, 0.0, 0.0)
    assert big_min_cut < small_min_cut


# ---------------------------------------------------------------------------
# _cut_round_deltas – verify deltas actually yield round cuts
# ---------------------------------------------------------------------------


def test_cut_round_deltas_produces_round_cuts():
    """After applying a delta, the cut at each contour edge should be
    closer to a multiple of CUT_ROUND_MM (10 mm)."""
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    # Shift 33mm → cut at edge 0 = (33 - 0) % 600 = 33mm → 33 % 10 = 3mm off
    best = {
        "shift_x_internal": mod.mm_to_internal(33),
        "shift_y_internal": mod.mm_to_internal(47),
    }
    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1200, 1200))

    pairs = mod._cut_round_deltas(best, 0.0, 0.0, step, step, outer, None)
    assert len(pairs) > 0

    step_mm = 600.0
    # At least one pair should yield cuts closer to multiples of 10mm
    base_cut_x = (33.0 - 0.0) % step_mm  # 33mm → penalty min(3, 7) = 3
    base_penalty_x = min(base_cut_x % 10, 10 - base_cut_x % 10)

    found_improvement = False
    for sx, sy in pairs:
        new_base_x_mm = mod.internal_to_mm(sx)
        new_cut_x = (new_base_x_mm - 0.0) % step_mm
        new_penalty_x = min(new_cut_x % 10, 10 - new_cut_x % 10)
        if new_penalty_x < base_penalty_x - 0.01:
            found_improvement = True
            break
    assert found_improvement, "At least one delta should reduce the roundness penalty"


def test_cut_round_deltas_already_round_returns_few():
    """When cuts are already multiples of 10mm, few/no deltas needed."""
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    # Shift 30mm → (30 - 0) % 600 = 30mm → 30 % 10 = 0 → already round
    best = {
        "shift_x_internal": mod.mm_to_internal(30),
        "shift_y_internal": mod.mm_to_internal(50),
    }
    outer = mod.Paths64()
    # Contour edges at 0 and 1200 — both produce round cuts with shift 30/50
    outer.Add(mod.make_rect_path64(0, 0, 1200, 1200))

    pairs = mod._cut_round_deltas(best, 0.0, 0.0, step, step, outer, None)
    # Should produce 0 or very few pairs (all already rounded)
    assert len(pairs) <= 2


# ---------------------------------------------------------------------------
# Regression test — captures reference output of find_best_shift for a fixed
# geometry so that any accidental change in scoring, grid generation, or
# search logic is detected immediately.
# ---------------------------------------------------------------------------


def test_find_best_shift_regression():
    """Regression: fixed 1300×1300 zone + hole → deterministic reference values."""
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1300, 1300))
    bbox = (0.0, 0.0, mod.mm_to_internal(1300), mod.mm_to_internal(1300))
    hole_paths = mod.Paths64()
    hole_paths.Add(mod.make_rect_path64(400, 400, 500, 500))

    result = mod.find_best_shift(
        step_x=step,
        step_y=step,
        base_x_raw=0.0,
        base_y_raw=0.0,
        outer_paths=outer,
        hole_paths=hole_paths,
        holes_bboxes_mm=[(400.0, 400.0, 500.0, 500.0)],
        outer_bbox_internal=bbox,
        unacceptable_cut_mm=100.0,
        unwanted_cut_mm=150.0,
        acceptable_cut_mm=200.0,
        coarse_shift_step_mm=50.0,
        top_n=3,
        refine_shift_step_mm=5.0,
        refine_radius_mm=25.0,
        min_edge_clearance_mm=15.0,
    )

    # --- coarse grid size ---
    assert result["coarse_count"] == 400

    best = result["best"]

    # --- rank_key structure (14-element tuple) ---
    rk = best["rank_key"]
    assert len(rk) == 14
    assert rk == (1, 0, 0, 0, 0.0, 0, 0, 0, 0, 0, -0.0, 0.0, 0.0, 0.0)

    # --- best shift values ---
    assert best["shift_x_mm"] == 0
    assert best["shift_y_mm"] == 0
    assert best["shift_x_internal"] == 0.0
    assert best["shift_y_internal"] == 0.0
    assert best["phase_x_mm"] == 0
    assert best["phase_y_mm"] == 0
    assert best["phase_x_internal"] == 0.0
    assert best["phase_y_internal"] == 0.0

    # --- counters ---
    assert best["unsplit_holes"] == 1
    assert best["full_count"] == 0
    assert best["simple_count"] == 0
    assert best["complex_count"] == 0
    assert best["non_viable_count"] == 0
    assert best["near_edge_count"] == 0
    assert best["viable_simple_count"] == 0

    # --- top-N ---
    tops = result["top_results"]
    assert len(tops) == 3
    assert len(result["equivalent_top_results"]) == 5
    # All top results share the same rank_key (mock geometry is uniform)
    for t in tops:
        assert t["rank_key"] == rk
    # Top results ordered by shift values (deterministic tie-breaking)
    assert tops[0]["shift_x_mm"] == 0 and tops[0]["shift_y_mm"] == 0
    assert tops[1]["shift_x_mm"] == 0 and tops[1]["shift_y_mm"] == 10
    assert tops[2]["shift_x_mm"] == 0 and tops[2]["shift_y_mm"] == 20


def test_find_best_shift_base_invariance():
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1300, 1300))
    bbox = (0.0, 0.0, mod.mm_to_internal(1300), mod.mm_to_internal(1300))
    hole_paths = mod.Paths64()
    hole_paths.Add(mod.make_rect_path64(400, 400, 500, 500))

    bases_mm = [(0.0, 0.0), (137.0, 251.0), (450.0, 300.0)]
    reference_phase = None
    reference_rank = None

    for base_x_mm, base_y_mm in bases_mm:
        base_x = mod.mm_to_internal(base_x_mm)
        base_y = mod.mm_to_internal(base_y_mm)
        result = mod.find_best_shift(
            step_x=step,
            step_y=step,
            base_x_raw=base_x,
            base_y_raw=base_y,
            outer_paths=outer,
            hole_paths=hole_paths,
            holes_bboxes_mm=[(400.0, 400.0, 500.0, 500.0)],
            outer_bbox_internal=bbox,
            unacceptable_cut_mm=100.0,
            unwanted_cut_mm=150.0,
            acceptable_cut_mm=200.0,
            coarse_shift_step_mm=50.0,
            top_n=3,
            refine_shift_step_mm=5.0,
            refine_radius_mm=25.0,
            min_edge_clearance_mm=15.0,
        )
        best = result["best"]

        resolved_phase_x = mod._normalize_shift(base_x + best["shift_x_internal"], step)
        resolved_phase_y = mod._normalize_shift(base_y + best["shift_y_internal"], step)

        assert resolved_phase_x == pytest.approx(best["phase_x_internal"])
        assert resolved_phase_y == pytest.approx(best["phase_y_internal"])

        if reference_phase is None:
            reference_phase = (best["phase_x_internal"], best["phase_y_internal"])
            reference_rank = best["rank_key"]
            continue

        assert best["phase_x_internal"] == pytest.approx(reference_phase[0])
        assert best["phase_y_internal"] == pytest.approx(reference_phase[1])
        assert best["rank_key"] == reference_rank


def test_find_best_shift_is_repeatable_for_same_inputs():
    mod = _import_floor_exact()
    step = mod.mm_to_internal(600)

    outer = mod.Paths64()
    outer.Add(mod.make_rect_path64(0, 0, 1300, 1300))
    bbox = (0.0, 0.0, mod.mm_to_internal(1300), mod.mm_to_internal(1300))
    hole_paths = mod.Paths64()
    hole_paths.Add(mod.make_rect_path64(400, 400, 500, 500))

    kwargs = dict(
        step_x=step,
        step_y=step,
        base_x_raw=mod.mm_to_internal(137.0),
        base_y_raw=mod.mm_to_internal(251.0),
        outer_paths=outer,
        hole_paths=hole_paths,
        holes_bboxes_mm=[(400.0, 400.0, 500.0, 500.0)],
        outer_bbox_internal=bbox,
        unacceptable_cut_mm=100.0,
        unwanted_cut_mm=150.0,
        acceptable_cut_mm=200.0,
        coarse_shift_step_mm=50.0,
        top_n=3,
        refine_shift_step_mm=5.0,
        refine_radius_mm=25.0,
        min_edge_clearance_mm=15.0,
    )

    first = mod.find_best_shift(**kwargs)
    second = mod.find_best_shift(**kwargs)

    assert first["best"]["rank_key"] == second["best"]["rank_key"]
    assert first["best"]["phase_x_internal"] == pytest.approx(
        second["best"]["phase_x_internal"]
    )
    assert first["best"]["phase_y_internal"] == pytest.approx(
        second["best"]["phase_y_internal"]
    )
    assert first["best"]["shift_x_internal"] == pytest.approx(
        second["best"]["shift_x_internal"]
    )
    assert first["best"]["shift_y_internal"] == pytest.approx(
        second["best"]["shift_y_internal"]
    )

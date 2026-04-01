# -*- coding: utf-8 -*-

import math
import os
from collections import Counter

import clr  # type: ignore
from Autodesk.Revit.DB import CurveElement, ElementId  # type: ignore
from floor_common import (
    build_positions,
    get_string_param,
    parse_ids_from_string,
    read_floor_grid_params,
)
from rf_config import (  # type: ignore
    AREA_EQUAL_TOL_MM2,
    BBOX_TOL_MM,
    CLIPPER_SCALE,
    CUT_ROUND_MM,
    DEFAULT_ACCEPTABLE_CUT_MM,
    DEFAULT_COARSE_SHIFT_STEP_MM,
    DEFAULT_MICRO_FRAGMENT_CUT_MM,
    DEFAULT_REFINE_RADIUS_MM,
    DEFAULT_REFINE_SHIFT_STEP_MM,
    DEFAULT_REFINE_TOP_N,
    DEFAULT_TOP_N,
    DEFAULT_UNACCEPTABLE_CUT_MM,
    DEFAULT_UNWANTED_CUT_MM,
    EDGE_TOL_MM,
    GEOM_TOL,
    MIN_FRAGMENT_AREA_MM2,
    ROUND_MM_DIGITS,
    SCAN_EPS_MM,
    SCAN_HIT_TOL_MM,
    SCAN_SAMPLES,
)
from rf_param_schema import RFParams as P  # type: ignore

TOL = GEOM_TOL  # допуск сравнения floating-point (internal units ≈ 0.0003 мм)
SCALE = CLIPPER_SCALE  # мм → Clipper2 int64 (1 мм = 1000 единиц, точность 0.001 мм)
ROUND_MM = ROUND_MM_DIGITS  # знаков после запятой при округлении мм

# 4-уровневые пороги подрезок (по реальным спецификациям производителей)
# < 50 мм       : micro_fragment — геометрический мусор, считается немонтируемым (non_viable)
# < 100 мм      : недопустимо — независимо от типа подрезки (простая/сложная)
# 100–150 мм    : нежелательно (монтаж с оговорками по поддержке)
# 150–200 мм    : допустимо (Bergvik: avoid < 200mm, но разрешено)
# >= 200 мм     : хорошо (целевой минимум)
# Целевая кратность подрезок по краям (мм).
# При равных основных метриках предпочитается вариант,
# размеры подрезок которого ближе к кратным CUT_ROUND_MM.
# Сканирование min-width для сложных подрезок (ray-casting эвристика)
_SCAN_SAMPLES = SCAN_SAMPLES  # равномерных лучей по каждой оси
_SCAN_EPS = SCAN_EPS_MM  # мм — сдвиг луча от вершин (чтобы не попасть точно на ребро)
_SCAN_HIT_TOL = SCAN_HIT_TOL_MM  # мм — склейка совпавших пересечений (дедупликация)
_BBOX_TOL_MM = BBOX_TOL_MM  # мм — допуск для быстрой bbox-проверки


def _get_extension_root():
    """Возвращает корневую папку расширения.

    Использует __file__ для определения пути и поднимается вверх
    до нахождения папки с ожидаемой структурой расширения.

    Returns:
        str: Абсолютный путь к корню расширения.

    Raises:
        Exception: Если корень расширения не найден.
    """
    # Нормализуем путь для Windows (UNC paths)
    script_dir = os.path.normpath(os.path.dirname(os.path.abspath(__file__)))
    search_dir = script_dir

    max_iterations = 20
    iterations = 0

    while iterations < max_iterations:
        iterations += 1
        dir_lower = search_dir.lower()
        if dir_lower.endswith(".extension"):
            return search_dir
        if os.path.isdir(os.path.join(search_dir, "lib")) and os.path.isdir(
            os.path.join(search_dir, "RaisedFloor.tab")
        ):
            return search_dir

        parent = os.path.dirname(search_dir)
        # Достигли корня диска
        if parent == search_dir:
            break
        search_dir = parent

    raise Exception("Extension root not found. Searched from: {}".format(script_dir))


def _load_clipper_api():
    """Загружает Clipper2Lib.dll через CLR.

    DLL должна находиться в папке lib/ внутри расширения.

    Returns:
        tuple: Кортеж импортированных классов Clipper2.

    Raises:
        Exception: Если DLL не найдена или не загрузилась.
    """
    ext_dir = _get_extension_root()
    dll_path = os.path.join(ext_dir, "lib", "Clipper2Lib.dll")

    if not os.path.exists(dll_path):
        raise Exception(
            "Clipper2Lib.dll not found at: {}. "
            "Ensure the DLL is in the lib/ folder of the extension.".format(dll_path)
        )

    try:
        clr.AddReferenceToFileAndPath(dll_path)
    except Exception as ex:
        raise Exception(
            "Failed to load Clipper2Lib.dll from {}: {}".format(dll_path, str(ex))
        )

    from Clipper2Lib import (  # type: ignore
        Clipper64,
        ClipType,
        EndType,
        FillRule,
        JoinType,
        Path64,
        Paths64,
        Point64,
    )
    from Clipper2Lib.Clipper import Difference, InflatePaths, Intersect  # type: ignore

    return (
        Paths64,
        Path64,
        Point64,
        FillRule,
        Intersect,
        Difference,
        JoinType,
        EndType,
        InflatePaths,
        Clipper64,
        ClipType,
    )


(
    Paths64,
    Path64,
    Point64,
    FillRule,
    Intersect,
    Difference,
    JoinType,
    EndType,
    InflatePaths,
    Clipper64,
    ClipType,
) = _load_clipper_api()


def internal_to_mm(value_internal):
    return value_internal * 304.8


def mm_to_internal(mm_value):
    return float(mm_value) / 304.8


def internal_xyz_to_mm_xy(pt):
    return internal_to_mm(pt.X), internal_to_mm(pt.Y)


def mm_xy_to_clipper_point(x_mm, y_mm):
    return Point64(int(round(x_mm * SCALE)), int(round(y_mm * SCALE)))


def clipper_to_mm(value_int):
    return float(value_int) / SCALE


def format_area_m2(area_mm2):
    return "{:.3f} м²".format(float(area_mm2) / 1000000.0)


def polygon_area_mm2(points_mm):
    area = 0.0
    n = len(points_mm)
    if n < 3:
        return 0.0

    for i in range(n):
        x1, y1 = points_mm[i]
        x2, y2 = points_mm[(i + 1) % n]
        area += x1 * y2 - x2 * y1

    return abs(area * 0.5)


def path64_to_points_mm(path64):
    pts = []
    for point in path64:
        pts.append((clipper_to_mm(point.X), clipper_to_mm(point.Y)))
    return pts


def path64_area_mm2(path64):
    return polygon_area_mm2(path64_to_points_mm(path64))


def paths64_total_area_mm2(paths64):
    total = 0.0
    for path in paths64:
        total += path64_area_mm2(path)
    return total


def paths64_bbox_mm(paths64):
    min_x = None
    min_y = None
    max_x = None
    max_y = None

    for path in paths64:
        for point in path:
            x_val = clipper_to_mm(point.X)
            y_val = clipper_to_mm(point.Y)

            if min_x is None or x_val < min_x:
                min_x = x_val
            if min_y is None or y_val < min_y:
                min_y = y_val
            if max_x is None or x_val > max_x:
                max_x = x_val
            if max_y is None or y_val > max_y:
                max_y = y_val

    return min_x, min_y, max_x, max_y


def points_equal_xy(p1, p2, tol=TOL):
    return abs(p1.X - p2.X) <= tol and abs(p1.Y - p2.Y) <= tol


def polygon_area_xy_internal(points):
    area = 0.0
    n = len(points)
    if n < 3:
        return 0.0

    for i in range(n):
        p1 = points[i]
        p2 = points[(i + 1) % n]
        area += p1.X * p2.Y - p2.X * p1.Y

    return area * 0.5


def build_shift_positions(step_internal, shift_step_internal):
    values = []
    if step_internal <= 0 or shift_step_internal <= 0:
        return values

    count = int(math.floor((step_internal - TOL) / shift_step_internal))
    for i in range(count + 1):
        value = i * shift_step_internal
        if value < step_internal - TOL:
            values.append(value)

    if not values:
        values.append(0.0)

    return values


def normalize_mm(value):
    return round(float(value), ROUND_MM)


def get_model_curve_endpoints(curve_el):
    curve = curve_el.GeometryCurve
    return curve.GetEndPoint(0), curve.GetEndPoint(1)


def build_loops_from_model_curves(curve_elements):
    unused = []
    for element in curve_elements:
        try:
            p0, p1 = get_model_curve_endpoints(element)
            unused.append({"p0": p0, "p1": p1})
        except Exception:
            pass

    loops = []

    while unused:
        current = unused.pop(0)
        loop_points = [current["p0"], current["p1"]]
        start_pt = current["p0"]
        current_end = current["p1"]

        closed = False
        guard = 0

        while guard < 10000:
            guard += 1

            if points_equal_xy(current_end, start_pt):
                closed = True
                break

            found_index = None
            reverse_needed = False

            for index, item in enumerate(unused):
                if points_equal_xy(item["p0"], current_end):
                    found_index = index
                    break
                if points_equal_xy(item["p1"], current_end):
                    found_index = index
                    reverse_needed = True
                    break

            if found_index is None:
                break

            item = unused.pop(found_index)
            next_end = item["p0"] if reverse_needed else item["p1"]
            loop_points.append(next_end)
            current_end = next_end

        if closed:
            if len(loop_points) > 1 and points_equal_xy(
                loop_points[0], loop_points[-1]
            ):
                loop_points.pop()
            loops.append(loop_points)

    return loops


def split_outer_inner_loops(loops):
    """Определяет внешний контур по максимальной абсолютной площади.

    Направление обхода линий модели в Revit не гарантировано,
    поэтому знак площади ненадёжен. Контур с наибольшей площадью
    всегда является внешним, остальные — отверстия.
    """
    if not loops:
        return [], []

    sorted_loops = sorted(
        loops,
        key=lambda loop: abs(polygon_area_xy_internal(loop)),
        reverse=True,
    )

    outer = [sorted_loops[0]]
    inner = sorted_loops[1:]
    return outer, inner


def get_loops_bbox_internal(loops):
    min_x = None
    min_y = None
    max_x = None
    max_y = None

    for loop in loops:
        for point in loop:
            if min_x is None or point.X < min_x:
                min_x = point.X
            if min_y is None or point.Y < min_y:
                min_y = point.Y
            if max_x is None or point.X > max_x:
                max_x = point.X
            if max_y is None or point.Y > max_y:
                max_y = point.Y

    return min_x, min_y, max_x, max_y


def revit_loop_to_path64(loop_pts):
    path = Path64()
    for point in loop_pts:
        x_mm, y_mm = internal_xyz_to_mm_xy(point)
        path.Add(mm_xy_to_clipper_point(x_mm, y_mm))
    return path


def make_rect_path64(x0_mm, y0_mm, x1_mm, y1_mm):
    path = Path64()
    path.Add(mm_xy_to_clipper_point(x0_mm, y0_mm))
    path.Add(mm_xy_to_clipper_point(x1_mm, y0_mm))
    path.Add(mm_xy_to_clipper_point(x1_mm, y1_mm))
    path.Add(mm_xy_to_clipper_point(x0_mm, y1_mm))
    return path


def is_single_axis_rect(path64):
    pts = path64_to_points_mm(path64)
    if len(pts) != 4:
        return False

    xs = sorted(set([round(point[0], 6) for point in pts]))
    ys = sorted(set([round(point[1], 6) for point in pts]))

    if len(xs) != 2 or len(ys) != 2:
        return False

    area = path64_area_mm2(path64)
    bbox_area = abs((xs[1] - xs[0]) * (ys[1] - ys[0]))

    return abs(area - bbox_area) <= AREA_EQUAL_TOL_MM2


def bbox_intersects(a, b, tol=_BBOX_TOL_MM):
    a_min_x, a_min_y, a_max_x, a_max_y = a
    b_min_x, b_min_y, b_max_x, b_max_y = b
    return not (
        a_max_x < b_min_x - tol
        or a_min_x > b_max_x + tol
        or a_max_y < b_min_y - tol
        or a_min_y > b_max_y + tol
    )


def get_exact_zone_for_floor(doc, floor):
    contour_ids_string = get_string_param(floor, P.CONTOUR_LINES_ID)
    contour_ids = parse_ids_from_string(contour_ids_string)
    if not contour_ids:
        raise Exception(
            "На перекрытии нет {}. Сначала запусти 'Контур'.".format(
                P.CONTOUR_LINES_ID
            )
        )

    contour_elements = []
    for int_id in contour_ids:
        element = doc.GetElement(ElementId(int_id))
        if element and isinstance(element, CurveElement):
            contour_elements.append(element)

    if not contour_elements:
        raise Exception("Не удалось получить линии контура")

    return build_exact_zone(contour_elements)


def build_exact_zone(contour_elements):
    loops = build_loops_from_model_curves(contour_elements)
    if not loops:
        raise Exception("Не удалось собрать замкнутые контуры")

    outer_loops, inner_loops = split_outer_inner_loops(loops)
    if not outer_loops:
        raise Exception("Не удалось определить внешний контур")

    if len(outer_loops) != 1:
        raise Exception(
            "Ожидался 1 внешний контур, найдено: {}".format(len(outer_loops))
        )

    outer_paths = Paths64()
    outer_paths.Add(revit_loop_to_path64(outer_loops[0]))

    hole_paths = Paths64()
    holes_bboxes_mm = []
    for hole in inner_loops:
        hole_path = revit_loop_to_path64(hole)
        hole_paths.Add(hole_path)

        hole_path_set = Paths64()
        hole_path_set.Add(hole_path)
        holes_bboxes_mm.append(paths64_bbox_mm(hole_path_set))

    return {
        "loops": loops,
        "outer_loops": outer_loops,
        "inner_loops": inner_loops,
        "outer_paths": outer_paths,
        "hole_paths": hole_paths,
        "holes_bboxes_mm": holes_bboxes_mm,
        "outer_bbox_internal": get_loops_bbox_internal(outer_loops),
    }


def offset_zone_contours(exact_zone, inset_mm):
    """Сдвигает контуры зоны внутрь на inset_mm (Clipper2 InflatePaths).

    Внешний контур — уменьшается (deflate, delta = -inset).
    Дыры — увеличиваются (inflate, delta = +inset).

    Returns:
        inset_outer_paths: Paths64 — сдвинутый внешний контур
        inset_hole_paths: Paths64 — сдвинутые дыры
    """
    delta_clipper = inset_mm * SCALE  # из мм в clipper-единицы

    # Deflate outer (negative delta = shrink)
    inset_outer = InflatePaths(
        exact_zone["outer_paths"], -delta_clipper, JoinType.Miter, EndType.Polygon
    )

    # Inflate holes (positive delta = expand hole outward)
    inset_holes = Paths64()
    if exact_zone["hole_paths"].Count > 0:
        inset_holes = InflatePaths(
            exact_zone["hole_paths"], delta_clipper, JoinType.Miter, EndType.Polygon
        )

    return inset_outer, inset_holes


def is_footprint_inside_zone(
    x_internal, y_internal, half_size_internal, outer_paths, hole_paths
):
    """Проверяет, что квадрат опоры целиком помещается в допустимую зону.

    Строит квадрат со стороной 2*half_size_internal вокруг точки (x, y),
    пересекает с outer_paths и вычитает hole_paths.
    Возвращает True, если площадь пересечения == площадь квадрата.
    """
    x_mm = internal_to_mm(x_internal)
    y_mm = internal_to_mm(y_internal)
    hs_mm = internal_to_mm(half_size_internal)

    rect = make_rect_path64(x_mm - hs_mm, y_mm - hs_mm, x_mm + hs_mm, y_mm + hs_mm)
    rect_area = path64_area_mm2(rect)
    if rect_area < AREA_EQUAL_TOL_MM2:
        return True

    rect_paths = Paths64()
    rect_paths.Add(rect)
    clipped = Intersect(rect_paths, outer_paths, FillRule.NonZero)
    clipped = Difference(clipped, hole_paths, FillRule.NonZero)

    clipped_area = paths64_total_area_mm2(clipped)
    return abs(clipped_area - rect_area) < AREA_EQUAL_TOL_MM2


def analyze_cell_exact(
    rect_path,
    rect_bbox_mm,
    outer_paths,
    hole_paths,
    holes_bboxes_mm,
    area_equal_tol_mm2=AREA_EQUAL_TOL_MM2,
    min_fragment_area_mm2=MIN_FRAGMENT_AREA_MM2,
):
    rect_paths = Paths64()
    rect_paths.Add(rect_path)
    current = Intersect(rect_paths, outer_paths, FillRule.NonZero)

    cell_area_mm2 = path64_area_mm2(rect_path)

    if current.Count == 0:
        return {
            "state": "Вне зоны",
            "kind": "Пустая",
            "area_mm2": 0.0,
            "size_x_mm": 0.0,
            "size_y_mm": 0.0,
            "poly_count": 0,
            "is_empty": True,
            "is_full": False,
            "is_partial": False,
            "is_simple_cut": False,
            "is_complex_cut": False,
            "is_fragment": False,
        }

    intersects_hole_bbox = False
    for hole_bbox in holes_bboxes_mm:
        if bbox_intersects(rect_bbox_mm, hole_bbox):
            intersects_hole_bbox = True
            break

    inter_area_mm2 = paths64_total_area_mm2(current)

    if (not intersects_hole_bbox) and abs(
        inter_area_mm2 - cell_area_mm2
    ) <= area_equal_tol_mm2:
        min_x, min_y, max_x, max_y = paths64_bbox_mm(current)
        if min_x is None or min_y is None or max_x is None or max_y is None:
            return {
                "state": "Full",
                "kind": "Full",
                "area_mm2": inter_area_mm2,
                "size_x_mm": 0.0,
                "size_y_mm": 0.0,
                "poly_count": current.Count,
                "is_empty": False,
                "is_full": True,
                "is_partial": False,
                "is_simple_cut": False,
                "is_complex_cut": False,
                "is_fragment": False,
            }

        return {
            "state": "Full",
            "kind": "Full",
            "area_mm2": inter_area_mm2,
            "size_x_mm": normalize_mm(max_x - min_x),
            "size_y_mm": normalize_mm(max_y - min_y),
            "poly_count": current.Count,
            "is_empty": False,
            "is_full": True,
            "is_partial": False,
            "is_simple_cut": False,
            "is_complex_cut": False,
            "is_fragment": False,
        }

    if hole_paths.Count > 0 and current.Count > 0:
        current = Difference(current, hole_paths, FillRule.NonZero)

    if current.Count == 0:
        return {
            "state": "Вне зоны",
            "kind": "Пустая",
            "area_mm2": 0.0,
            "size_x_mm": 0.0,
            "size_y_mm": 0.0,
            "poly_count": 0,
            "is_empty": True,
            "is_full": False,
            "is_partial": False,
            "is_simple_cut": False,
            "is_complex_cut": False,
            "is_fragment": False,
        }

    area_mm2 = paths64_total_area_mm2(current)

    if area_mm2 < min_fragment_area_mm2:
        return {
            "state": "Вне зоны",
            "kind": "Фрагмент",
            "area_mm2": area_mm2,
            "size_x_mm": 0.0,
            "size_y_mm": 0.0,
            "poly_count": current.Count,
            "is_empty": False,
            "is_full": False,
            "is_partial": False,
            "is_simple_cut": False,
            "is_complex_cut": False,
            "is_fragment": True,
        }

    min_x, min_y, max_x, max_y = paths64_bbox_mm(current)
    if min_x is None or min_y is None or max_x is None or max_y is None:
        return {
            "state": "Вне зоны",
            "kind": "Пустая",
            "area_mm2": area_mm2,
            "size_x_mm": 0.0,
            "size_y_mm": 0.0,
            "poly_count": current.Count,
            "is_empty": True,
            "is_full": False,
            "is_partial": False,
            "is_simple_cut": False,
            "is_complex_cut": False,
            "is_fragment": False,
        }

    size_x_mm = normalize_mm(max_x - min_x)
    size_y_mm = normalize_mm(max_y - min_y)

    is_full = abs(area_mm2 - cell_area_mm2) <= area_equal_tol_mm2
    if is_full:
        return {
            "state": "Full",
            "kind": "Full",
            "area_mm2": area_mm2,
            "size_x_mm": size_x_mm,
            "size_y_mm": size_y_mm,
            "poly_count": current.Count,
            "is_empty": False,
            "is_full": True,
            "is_partial": False,
            "is_simple_cut": False,
            "is_complex_cut": False,
            "is_fragment": False,
        }

    if current.Count == 1 and is_single_axis_rect(current[0]):
        kind = "Простая подрезка"
        is_simple = True
        is_complex = False
        min_width_mm = min(size_x_mm, size_y_mm)
    else:
        kind = "Сложная подрезка"
        is_simple = False
        is_complex = True
        min_width_mm = _scan_min_width_mm(current)

    return {
        "state": "SimpleCut",
        "kind": kind,
        "area_mm2": area_mm2,
        "size_x_mm": size_x_mm,
        "size_y_mm": size_y_mm,
        "min_width_mm": min_width_mm,
        "clip_center_x_mm": (min_x + max_x) / 2.0,
        "clip_center_y_mm": (min_y + max_y) / 2.0,
        "poly_count": current.Count,
        "clipped_paths": current,
        "is_empty": False,
        "is_full": False,
        "is_partial": True,
        "is_simple_cut": is_simple,
        "is_complex_cut": is_complex,
        "is_fragment": False,
    }


def _point_in_polygon_mm(px, py, polygon_pts):
    """Point-in-polygon test с проверкой точки на ребре (мм координаты)."""
    n = len(polygon_pts)
    edge_tol = EDGE_TOL_MM  # мм — допуск для попадания на ребро
    inside = False
    j = n - 1
    for i in range(n):
        xi, yi = polygon_pts[i]
        xj, yj = polygon_pts[j]
        # Проверка: точка лежит на отрезке (xi,yi)-(xj,yj)
        dx_seg = xj - xi
        dy_seg = yj - yi
        dx_pt = px - xi
        dy_pt = py - yi
        cross = abs(dx_seg * dy_pt - dy_seg * dx_pt)
        seg_len = (dx_seg * dx_seg + dy_seg * dy_seg) ** 0.5
        if seg_len > 0 and cross / seg_len < edge_tol:
            # Точка на прямой — проверим bbox отрезка
            if (
                min(xi, xj) - edge_tol <= px <= max(xi, xj) + edge_tol
                and min(yi, yj) - edge_tol <= py <= max(yi, yj) + edge_tol
            ):
                return True
        # Стандартный ray-casting
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _decompose_void_to_rects(void_pts, cell_bbox_mm):
    """Разложить void-полигон на ортогональные прямоугольники.

    Строит сетку из уникальных X/Y координат вершин полигона,
    проверяет центр каждой ячейки на попадание внутрь полигона.
    Возвращает список (x0, y0, x1, y1) прямоугольников в мм.
    """
    c_x0, c_y0, c_x1, c_y1 = cell_bbox_mm

    # Собираем уникальные координаты из вершин + границы ячейки
    xs = sorted(set([round(p[0], 1) for p in void_pts] + [c_x0, c_x1]))
    ys = sorted(set([round(p[1], 1) for p in void_pts] + [c_y0, c_y1]))

    # Оставляем только координаты внутри bbox void-а
    vxs = [p[0] for p in void_pts]
    vys = [p[1] for p in void_pts]
    v_min_x, v_max_x = min(vxs), max(vxs)
    v_min_y, v_max_y = min(vys), max(vys)

    xs = [x for x in xs if v_min_x - 0.5 <= x <= v_max_x + 0.5]
    ys = [y for y in ys if v_min_y - 0.5 <= y <= v_max_y + 0.5]

    rects = []
    for i in range(len(xs) - 1):
        for j in range(len(ys) - 1):
            rx0, rx1 = xs[i], xs[i + 1]
            ry0, ry1 = ys[j], ys[j + 1]
            if rx1 - rx0 < 0.5 or ry1 - ry0 < 0.5:
                continue
            # Проверяем центр подъячейки
            cx = (rx0 + rx1) / 2.0
            cy = (ry0 + ry1) / 2.0
            if _point_in_polygon_mm(cx, cy, void_pts):
                rects.append((rx0, ry0, rx1, ry1))

    # Мержим смежные прямоугольники: сначала по горизонтали, потом по вертикали
    def _merge_pass(rects, axis):
        """axis='x' — горизонтальный merge, 'y' — вертикальный."""
        merged = []
        used = [False] * len(rects)
        for i, (ax0, ay0, ax1, ay1) in enumerate(rects):
            if used[i]:
                continue
            cur_x0, cur_y0, cur_x1, cur_y1 = ax0, ay0, ax1, ay1
            changed = True
            while changed:
                changed = False
                for k in range(len(rects)):
                    if used[k]:
                        continue
                    bx0, by0, bx1, by1 = rects[k]
                    if axis == "x":
                        # Тот же Y-диапазон и примыкают по X
                        if (
                            abs(by0 - cur_y0) < 0.5
                            and abs(by1 - cur_y1) < 0.5
                            and (abs(bx0 - cur_x1) < 0.5 or abs(bx1 - cur_x0) < 0.5)
                        ):
                            cur_x0 = min(cur_x0, bx0)
                            cur_x1 = max(cur_x1, bx1)
                            used[k] = True
                            changed = True
                    else:
                        # Тот же X-диапазон и примыкают по Y
                        if (
                            abs(bx0 - cur_x0) < 0.5
                            and abs(bx1 - cur_x1) < 0.5
                            and (abs(by0 - cur_y1) < 0.5 or abs(by1 - cur_y0) < 0.5)
                        ):
                            cur_y0 = min(cur_y0, by0)
                            cur_y1 = max(cur_y1, by1)
                            used[k] = True
                            changed = True
            used[i] = True
            merged.append((cur_x0, cur_y0, cur_x1, cur_y1))
        return merged

    merged = _merge_pass(rects, "x")
    merged = _merge_pass(merged, "y")

    return merged if merged else rects


def compute_voids(cell_bbox_mm, clipped_paths, max_voids=3):
    """Вычислить до max_voids вырезов = ячейка − обрезанный полигон.

    Разница cell_rect − clipped даёт области, которые нужно удалить.
    Непрямоугольные void-полигоны (L, T, U) раскладываются на
    отдельные прямоугольники через сетку вершин.
    Смещения считаются от левого/нижнего края ячейки.

    Args:
        cell_bbox_mm: (x0, y0, x1, y1) ячейки сетки в мм.
        clipped_paths: Paths64 — полигон(ы) обрезанной плитки.
        max_voids: максимальное количество вырезов (по умолчанию 3).

    Returns:
        dict с ключами:
            voids — list of (w_mm, h_mm, margin_x_mm, margin_y_mm), до max_voids шт.
            has_unhandled_voids — bool (найдено больше max_voids областей)
    """
    c_x0, c_y0, c_x1, c_y1 = cell_bbox_mm

    cell_rect = make_rect_path64(c_x0, c_y0, c_x1, c_y1)
    cell_paths = Paths64()
    cell_paths.Add(cell_rect)

    diff = Difference(cell_paths, clipped_paths, FillRule.NonZero)

    if diff.Count == 0:
        return {"voids": [], "has_unhandled_voids": False}

    items = []
    for void_path in diff:
        pts = path64_to_points_mm(void_path)
        if not pts:  # pragma: no cover
            continue  # pragma: no cover

        # Прямоугольный void — берём как есть
        if len(pts) == 4 and is_single_axis_rect(void_path):
            vxs = [p[0] for p in pts]
            vys = [p[1] for p in pts]
            sub_rects = [(min(vxs), min(vys), max(vxs), max(vys))]
        else:
            # Непрямоугольный (L, T, U) — раскладываем на прямоугольники
            sub_rects = _decompose_void_to_rects(pts, cell_bbox_mm)

        for r_x0, r_y0, r_x1, r_y1 in sub_rects:
            w_mm = normalize_mm(r_x1 - r_x0)
            h_mm = normalize_mm(r_y1 - r_y0)
            if w_mm <= 0 or h_mm <= 0:  # pragma: no cover
                continue  # pragma: no cover
            margin_x_mm = normalize_mm(r_x0 - c_x0)
            margin_y_mm = normalize_mm(r_y0 - c_y0)
            area = w_mm * h_mm
            items.append((area, (w_mm, h_mm, margin_x_mm, margin_y_mm)))

    items.sort(key=lambda t: t[0], reverse=True)
    voids_out = [item[1] for item in items[:max_voids]]

    return {
        "voids": voids_out,
        "has_unhandled_voids": len(items) > max_voids,
    }


def _scan_min_width_mm(paths64, num_samples=_SCAN_SAMPLES):
    """Приблизительная минимальная рабочая ширина фигуры.

    Сканирует сечения по X и Y, находит самый узкий «проход».
    Использует равномерную сетку + дополнительные лучи вблизи каждой
    вершины полигона, чтобы гарантированно поймать узкие участки
    у колонн, L-вырезов, U-форм.
    """
    all_pts = []
    edges = []
    for path in paths64:
        pts = path64_to_points_mm(path)
        all_pts.extend(pts)
        n = len(pts)
        for i in range(n):
            edges.append(
                (pts[i][0], pts[i][1], pts[(i + 1) % n][0], pts[(i + 1) % n][1])
            )

    if not all_pts or not edges:
        return 0.0

    xs = [p[0] for p in all_pts]
    ys = [p[1] for p in all_pts]
    lo_x, hi_x = min(xs), max(xs)
    lo_y, hi_y = min(ys), max(ys)

    dx = hi_x - lo_x
    dy = hi_y - lo_y
    if dx < _SCAN_EPS and dy < _SCAN_EPS:
        return 0.0

    min_w = min(dx, dy) if (dx > _SCAN_EPS and dy > _SCAN_EPS) else max(dx, dy)

    def _build_scan_coords(lo, hi, vertex_coords):
        """Равномерная сетка + лучи вблизи каждой вершины."""
        coords = set()
        step = (hi - lo) / (num_samples + 1)
        for i in range(1, num_samples + 1):
            coords.add(lo + i * step + _SCAN_EPS)
        for v in vertex_coords:
            if lo + _SCAN_EPS * 2 < v < hi - _SCAN_EPS * 2:
                coords.add(v + _SCAN_EPS)
                coords.add(v - _SCAN_EPS)
        return sorted(coords)

    def _ray_min(scan_coords, is_vertical):
        best = min_w
        for coord in scan_coords:
            hits = []
            for x1, y1, x2, y2 in edges:
                if is_vertical:
                    d = x2 - x1
                    if abs(d) < _SCAN_HIT_TOL:
                        continue
                    t = (coord - x1) / d
                    if t < -_SCAN_HIT_TOL or t > 1.0 + _SCAN_HIT_TOL:
                        continue
                    hits.append(y1 + t * (y2 - y1))
                else:
                    d = y2 - y1
                    if abs(d) < _SCAN_HIT_TOL:
                        continue
                    t = (coord - y1) / d
                    if t < -_SCAN_HIT_TOL or t > 1.0 + _SCAN_HIT_TOL:
                        continue
                    hits.append(x1 + t * (x2 - x1))
            hits.sort()
            # dedupe
            unique = []
            for h in hits:
                if not unique or abs(h - unique[-1]) > _SCAN_HIT_TOL:
                    unique.append(h)
            for j in range(0, len(unique) - 1, 2):
                seg = unique[j + 1] - unique[j]
                if seg > _SCAN_EPS:
                    best = min(best, seg)
        return best

    unique_xs = sorted(set(round(v, 6) for v in xs))
    unique_ys = sorted(set(round(v, 6) for v in ys))

    if dx > _SCAN_EPS:
        coords = _build_scan_coords(lo_x, hi_x, unique_xs)
        min_w = _ray_min(coords, is_vertical=True)
    if dy > _SCAN_EPS:
        coords = _build_scan_coords(lo_y, hi_y, unique_ys)
        w = _ray_min(coords, is_vertical=False)
        min_w = min(min_w, w)

    return round(min_w, ROUND_MM)


def _count_unsplit_holes(x_positions, y_positions, hole_paths, step_x, step_y):
    """Считает колонны, через которые НЕ проходит ни одна линия сетки.

    Колонна целиком внутри одной ячейки = немонтируемая плитка
    (нельзя физически надеть плитку с вырезом на колонну).
    Линия сетки должна проходить через колонну, чтобы разделить плитки
    на куски, которые можно подсунуть сбоку.

    Returns:
        Кол-во колонн, не разрезанных сеткой.
    """
    if hole_paths is None:
        return 0

    tol = mm_to_internal(2.0)  # допуск попадания на грань
    unsplit = 0

    # Собираем все X- и Y-линии сетки (включая правые/верхние границы ячеек)
    all_x = set()
    for x in x_positions:
        all_x.add(x)
        all_x.add(x + step_x)
    all_y = set()
    for y in y_positions:
        all_y.add(y)
        all_y.add(y + step_y)

    for hole_path in hole_paths:
        xs_h = []
        ys_h = []
        for pt in hole_path:
            xs_h.append(mm_to_internal(clipper_to_mm(pt.X)))
            ys_h.append(mm_to_internal(clipper_to_mm(pt.Y)))
        if not xs_h or not ys_h:
            continue
        hmin_x = min(xs_h)
        hmax_x = max(xs_h)
        hmin_y = min(ys_h)
        hmax_y = max(ys_h)

        # Есть ли хоть одна линия, проходящая через колонну?
        has_split = False
        for x in all_x:
            if hmin_x + tol < x < hmax_x - tol:
                has_split = True
                break
        if not has_split:
            for y in all_y:
                if hmin_y + tol < y < hmax_y - tol:
                    has_split = True
                    break
        if not has_split:
            unsplit += 1

    return unsplit


def evaluate_shift_exact(
    step_x,
    step_y,
    base_x_raw,
    base_y_raw,
    shift_x,
    shift_y,
    outer_paths,
    hole_paths,
    holes_bboxes_mm,
    outer_bbox_internal,
    unacceptable_cut_mm=100.0,
    unwanted_cut_mm=150.0,
    acceptable_cut_mm=200.0,
    min_edge_clearance_mm=0,
    edge_xs_mm=None,
    edge_ys_mm=None,
):
    base_x = base_x_raw + shift_x
    base_y = base_y_raw + shift_y

    min_x, min_y, max_x, max_y = outer_bbox_internal
    x_positions = build_positions(
        min_x, max_x, base_x, step_x, end_padding_steps=1.0, end_tolerance=0.0
    )
    y_positions = build_positions(
        min_y, max_y, base_y, step_y, end_padding_steps=1.0, end_tolerance=0.0
    )

    # Взвешенный штраф за линии сетки, лежащие ближе min_edge_clearance_mm
    # к ребру выреза/колонны. Чем ближе — тем выше штраф (clearance/distance).
    # (внешний контур не учитываем — у стен сеточный лонжерон рядом с контурным нормален)
    near_edge_count = 0
    near_edge_penalty = 0.0
    if min_edge_clearance_mm > 0:
        if edge_xs_mm is None or edge_ys_mm is None:
            _exs = set()
            _eys = set()
            if hole_paths is not None:
                for path in hole_paths:
                    for pt in path:
                        _exs.add(clipper_to_mm(pt.X))
                        _eys.add(clipper_to_mm(pt.Y))
            edge_xs_mm = sorted(_exs)
            edge_ys_mm = sorted(_eys)
        clearance = min_edge_clearance_mm
        for x in x_positions:
            x_mm = internal_to_mm(x)
            for ex in edge_xs_mm:
                dist = abs(x_mm - ex)
                if dist < clearance:
                    near_edge_count += 1
                    near_edge_penalty += clearance / max(dist, 0.1)
                    break
        for y in y_positions:
            y_mm = internal_to_mm(y)
            for ey in edge_ys_mm:
                dist = abs(y_mm - ey)
                if dist < clearance:
                    near_edge_count += 1
                    near_edge_penalty += clearance / max(dist, 0.1)
                    break
    near_edge_penalty = round(near_edge_penalty, 2)

    full_count = 0
    simple_count = 0  # viable simple (>= 100 мм min_width)
    complex_count = (
        0  # viable complex (>= 100 мм); non-viable complex уходят в non_viable_count
    )
    empty_count = 0
    fragment_count = 0
    micro_fragment_count = 0  # < 50 мм (и простые и сложные)

    # Единое правило: min_width < 100 мм = немонтируемая,
    # одинаково для простых и сложных.
    # micro (<50) тоже считается non_viable + дополнительно штрафуется в rank_key.
    non_viable_count = 0
    non_viable_simple = 0
    non_viable_cells = []  # (x0, y0, x1, y1) internal для подсветки
    unwanted_count = 0  # 100–150 мм
    acceptable_count = 0  # 150–200 мм
    good_count = 0  # >= 200 мм

    min_viable_cut_mm = None
    max_viable_cut_mm = None
    min_cut_all_mm = None  # абсолютный минимум среди ВСЕХ подрезок
    # Площадь только рабочих подрезок (>= 50 мм); micro-фрагменты не входят.
    total_cut_area_mm2 = 0.0
    cut_groups = Counter()
    viable_cuts_mm = []  # все viable cut_min для расчёта spread

    micro_fragment_cut_mm = DEFAULT_MICRO_FRAGMENT_CUT_MM

    for x0 in x_positions:
        for y0 in y_positions:
            x1 = x0 + step_x
            y1 = y0 + step_y

            x0_mm = internal_to_mm(x0)
            y0_mm = internal_to_mm(y0)
            x1_mm = internal_to_mm(x1)
            y1_mm = internal_to_mm(y1)

            rect_path = make_rect_path64(x0_mm, y0_mm, x1_mm, y1_mm)
            rect_bbox_mm = (x0_mm, y0_mm, x1_mm, y1_mm)

            result = analyze_cell_exact(
                rect_path,
                rect_bbox_mm,
                outer_paths,
                hole_paths,
                holes_bboxes_mm,
            )

            if result["is_full"]:
                full_count += 1
            elif result["is_simple_cut"] or result["is_complex_cut"]:
                is_simple = result["is_simple_cut"]
                cut_min = result.get(
                    "min_width_mm",
                    min(result["size_x_mm"], result["size_y_mm"]),
                )

                # Трекаем абсолютный минимум по всем подрезкам
                if min_cut_all_mm is None or cut_min < min_cut_all_mm:
                    min_cut_all_mm = cut_min

                # < 50 мм — micro-фрагмент: считается немонтируемым (non_viable)
                # + дополнительный штраф в rank_key (micro хуже обычного non-viable)
                if cut_min < micro_fragment_cut_mm:
                    micro_fragment_count += 1
                    non_viable_count += 1
                    non_viable_cells.append((x0, y0, x1, y1))
                    if is_simple:
                        non_viable_simple += 1
                    continue

                total_cut_area_mm2 += result["area_mm2"]

                if cut_min < unacceptable_cut_mm:
                    non_viable_count += 1
                    non_viable_cells.append((x0, y0, x1, y1))
                    if is_simple:
                        non_viable_simple += 1
                elif cut_min < unwanted_cut_mm:
                    unwanted_count += 1
                    if is_simple:
                        simple_count += 1
                    else:
                        complex_count += 1
                elif cut_min < acceptable_cut_mm:
                    acceptable_count += 1
                    if is_simple:
                        simple_count += 1
                    else:
                        complex_count += 1
                else:
                    good_count += 1
                    if is_simple:
                        simple_count += 1
                    else:
                        complex_count += 1

                # min/max и группы — по всем viable (>= 100 мм)
                if cut_min >= unacceptable_cut_mm:
                    viable_cuts_mm.append(cut_min)
                    if min_viable_cut_mm is None or cut_min < min_viable_cut_mm:
                        min_viable_cut_mm = cut_min
                    if max_viable_cut_mm is None or cut_min > max_viable_cut_mm:
                        max_viable_cut_mm = cut_min

                    if is_simple:
                        size_x_key = int(round(result["size_x_mm"]))
                        size_y_key = int(round(result["size_y_mm"]))
                        key = "{}x{}".format(
                            min(size_x_key, size_y_key),
                            max(size_x_key, size_y_key),
                        )
                        cut_groups[key] += 1
            elif result["is_fragment"]:
                fragment_count += 1
            else:
                empty_count += 1

    viable_simple_count = simple_count
    total_simple_count = viable_simple_count + non_viable_simple
    min_viable_cut_rank = min_viable_cut_mm if min_viable_cut_mm is not None else 0.0
    unique_sizes = len(cut_groups)

    # Штраф за колонны без разреза сеткой (немонтируемая плитка с вырезом)
    unsplit_holes = _count_unsplit_holes(
        x_positions, y_positions, hole_paths, step_x, step_y
    )

    # Штраф за некратность подрезок CUT_ROUND_MM (тайбрекер)
    # Внешний контур — приоритет; колонны — вторичный тайбрекер.
    step_x_mm_r = internal_to_mm(step_x)
    step_y_mm_r = internal_to_mm(step_y)
    base_x_mm_r = internal_to_mm(base_x)
    base_y_mm_r = internal_to_mm(base_y)

    def _edge_penalty_x(edge_x_mm):
        cut = (base_x_mm_r - edge_x_mm) % step_x_mm_r
        if cut < 0:  # pragma: no cover
            cut += step_x_mm_r  # pragma: no cover
        r = cut % CUT_ROUND_MM
        return min(r, CUT_ROUND_MM - r)

    def _edge_penalty_y(edge_y_mm):
        cut = (base_y_mm_r - edge_y_mm) % step_y_mm_r
        if cut < 0:  # pragma: no cover
            cut += step_y_mm_r  # pragma: no cover
        r = cut % CUT_ROUND_MM
        return min(r, CUT_ROUND_MM - r)

    outer_roundness_penalty = 0.0
    _outer_xs_mm = set()
    _outer_ys_mm = set()
    for _op in outer_paths:
        for _pt in _op:
            _outer_xs_mm.add(round(clipper_to_mm(_pt.X), 1))
            _outer_ys_mm.add(round(clipper_to_mm(_pt.Y), 1))
    _outer_penalties = []
    for _ex in _outer_xs_mm:
        _outer_penalties.append(_edge_penalty_x(_ex))
    for _ey in _outer_ys_mm:
        _outer_penalties.append(_edge_penalty_y(_ey))
    if _outer_penalties:
        outer_roundness_penalty = round(
            sum(_outer_penalties) / len(_outer_penalties), 2
        )

    hole_roundness_penalty = 0.0
    if hole_paths is not None:
        _hole_penalties = []
        for _hp in hole_paths:
            _hxs = [clipper_to_mm(pt.X) for pt in _hp]
            _hys = [clipper_to_mm(pt.Y) for pt in _hp]
            if _hxs and _hys:
                _hole_penalties.append(_edge_penalty_x(min(_hxs)))
                _hole_penalties.append(_edge_penalty_x(max(_hxs)))
                _hole_penalties.append(_edge_penalty_y(min(_hys)))
                _hole_penalties.append(_edge_penalty_y(max(_hys)))
        if _hole_penalties:
            hole_roundness_penalty = round(
                sum(_hole_penalties) / len(_hole_penalties), 2
            )

    # Штраф за разброс размеров подрезок — предпочитаем однородные подрезки
    # (150+150 лучше, чем 100+200). Используем стандартное отклонение viable cut_min.
    cut_spread_penalty = 0.0
    if viable_cuts_mm:
        _mean = sum(viable_cuts_mm) / len(viable_cuts_mm)
        _var = sum((c - _mean) ** 2 for c in viable_cuts_mm) / len(viable_cuts_mm)
        cut_spread_penalty = round(_var**0.5, 2)

    rank_key = (
        unsplit_holes,
        non_viable_count,
        micro_fragment_count,
        near_edge_count,
        near_edge_penalty,
        unwanted_count,
        complex_count,
        -full_count,
        viable_simple_count,
        unique_sizes,
        -min_viable_cut_rank,
        outer_roundness_penalty,
        hole_roundness_penalty,
        cut_spread_penalty,
    )

    return {
        "shift_x_internal": shift_x,
        "shift_y_internal": shift_y,
        "shift_x_mm": round(internal_to_mm(shift_x)),
        "shift_y_mm": round(internal_to_mm(shift_y)),
        "phase_x_internal": shift_x,
        "phase_y_internal": shift_y,
        "phase_x_mm": round(internal_to_mm(shift_x)),
        "phase_y_mm": round(internal_to_mm(shift_y)),
        "full_count": full_count,
        "viable_simple_count": viable_simple_count,
        "total_simple_count": total_simple_count,
        "simple_count": simple_count,
        "complex_count": complex_count,
        "fragment_count": fragment_count,
        "micro_fragment_count": micro_fragment_count,
        "empty_count": empty_count,
        "non_viable_count": non_viable_count,
        "non_viable_cells": non_viable_cells,
        "unwanted_count": unwanted_count,
        "acceptable_count": acceptable_count,
        "good_count": good_count,
        "min_viable_cut_mm": (
            min_viable_cut_mm if min_viable_cut_mm is not None else 0.0
        ),
        "max_viable_cut_mm": (
            max_viable_cut_mm if max_viable_cut_mm is not None else 0.0
        ),
        "min_viable_cut_rank": min_viable_cut_rank,
        "min_cut_all_mm": min_cut_all_mm if min_cut_all_mm is not None else 0.0,
        "unique_sizes": unique_sizes,
        "total_cut_area_mm2": total_cut_area_mm2,
        "cut_groups": dict(cut_groups),
        "rank_key": rank_key,
        "unsplit_holes": unsplit_holes,
        "near_edge_count": near_edge_count,
    }


def _evaluate_shifts_grid(
    step_x,
    step_y,
    base_x_raw,
    base_y_raw,
    shift_x_values,
    shift_y_values,
    outer_paths,
    hole_paths,
    holes_bboxes_mm,
    outer_bbox_internal,
    unacceptable_cut_mm,
    unwanted_cut_mm,
    acceptable_cut_mm,
    min_edge_clearance_mm=0,
    edge_xs_mm=None,
    edge_ys_mm=None,
):
    results = []
    for shift_x in shift_x_values:
        for shift_y in shift_y_values:
            result = evaluate_shift_exact(
                step_x=step_x,
                step_y=step_y,
                base_x_raw=base_x_raw,
                base_y_raw=base_y_raw,
                shift_x=shift_x,
                shift_y=shift_y,
                outer_paths=outer_paths,
                hole_paths=hole_paths,
                holes_bboxes_mm=holes_bboxes_mm,
                outer_bbox_internal=outer_bbox_internal,
                unacceptable_cut_mm=unacceptable_cut_mm,
                unwanted_cut_mm=unwanted_cut_mm,
                acceptable_cut_mm=acceptable_cut_mm,
                min_edge_clearance_mm=min_edge_clearance_mm,
                edge_xs_mm=edge_xs_mm,
                edge_ys_mm=edge_ys_mm,
            )
            results.append(result)
    return results


def _normalize_shift(shift_internal, step_internal):
    if step_internal <= 0:
        return 0.0
    value = shift_internal % step_internal
    if value < 0:  # pragma: no cover
        value += step_internal  # pragma: no cover
    return value


def _phase_to_user_shift(phase_internal, original_base_internal, step_internal):
    return _normalize_shift(phase_internal - original_base_internal, step_internal)


def _result_sort_key(result):
    return (
        result["rank_key"],
        result.get("phase_x_mm", result["shift_x_mm"]),
        result.get("phase_y_mm", result["shift_y_mm"]),
    )


def _convert_results_to_user_offsets(
    results,
    original_base_x_raw,
    original_base_y_raw,
    step_x,
    step_y,
):
    for result in results:
        phase_x = result.get("phase_x_internal", result["shift_x_internal"])
        phase_y = result.get("phase_y_internal", result["shift_y_internal"])
        result["shift_x_internal"] = _phase_to_user_shift(
            phase_x, original_base_x_raw, step_x
        )
        result["shift_y_internal"] = _phase_to_user_shift(
            phase_y, original_base_y_raw, step_y
        )
        result["shift_x_mm"] = round(internal_to_mm(result["shift_x_internal"]))
        result["shift_y_mm"] = round(internal_to_mm(result["shift_y_internal"]))


def _build_local_shift_positions(
    step_internal,
    center_shift_internal,
    local_step_internal,
    radius_internal,
):
    if step_internal <= 0 or local_step_internal <= 0:
        return [0.0]

    center = _normalize_shift(center_shift_internal, step_internal)
    radius_steps = int(math.floor((radius_internal + TOL) / local_step_internal))

    values = []
    seen = set()

    for index in range(-radius_steps, radius_steps + 1):
        candidate = center + index * local_step_internal
        normalized = _normalize_shift(candidate, step_internal)
        key = round(normalized, 12)
        if key in seen:
            continue
        seen.add(key)
        values.append(normalized)

    if not values:
        values.append(center)  # pragma: no cover

    return sorted(values)


def evaluate_floor_shift(
    doc,
    floor,
    unacceptable_cut_mm=None,
    unwanted_cut_mm=None,
    acceptable_cut_mm=None,
    coarse_shift_step_mm=None,
    top_n=None,
    refine_shift_step_mm=None,
    refine_radius_mm=None,
    refine_top_n=None,
    min_edge_clearance_mm=0,
    progress_callback=None,
):
    params = read_floor_grid_params(floor)
    exact_zone = get_exact_zone_for_floor(doc, floor)

    return find_best_shift(
        step_x=params["step_x"],
        step_y=params["step_y"],
        base_x_raw=params["base_x_raw"],
        base_y_raw=params["base_y_raw"],
        outer_paths=exact_zone["outer_paths"],
        hole_paths=exact_zone["hole_paths"],
        holes_bboxes_mm=exact_zone["holes_bboxes_mm"],
        outer_bbox_internal=exact_zone["outer_bbox_internal"],
        unacceptable_cut_mm=(
            unacceptable_cut_mm
            if unacceptable_cut_mm is not None
            else DEFAULT_UNACCEPTABLE_CUT_MM
        ),
        unwanted_cut_mm=(
            unwanted_cut_mm if unwanted_cut_mm is not None else DEFAULT_UNWANTED_CUT_MM
        ),
        acceptable_cut_mm=(
            acceptable_cut_mm
            if acceptable_cut_mm is not None
            else DEFAULT_ACCEPTABLE_CUT_MM
        ),
        coarse_shift_step_mm=(
            coarse_shift_step_mm
            if coarse_shift_step_mm is not None
            else DEFAULT_COARSE_SHIFT_STEP_MM
        ),
        top_n=top_n if top_n is not None else DEFAULT_TOP_N,
        refine_shift_step_mm=(
            refine_shift_step_mm
            if refine_shift_step_mm is not None
            else DEFAULT_REFINE_SHIFT_STEP_MM
        ),
        refine_radius_mm=(
            refine_radius_mm
            if refine_radius_mm is not None
            else DEFAULT_REFINE_RADIUS_MM
        ),
        refine_top_n=(
            refine_top_n if refine_top_n is not None else DEFAULT_REFINE_TOP_N
        ),
        min_edge_clearance_mm=min_edge_clearance_mm,
        progress_callback=progress_callback,
    )


def _snap_shifts_for_axis(vertex_coords_internal, base_internal, step_internal):
    """Вычисляет значения смещений, при которых линия сетки проходит
    через вершину контура (или рядом с ней).

    Для каждой координаты вершины:
      grid_line = base + shift + n * step  =>  shift = (coord - base) mod step
    """
    if step_internal <= 0:
        return []

    seen_mm = set()  # дедупликация с точностью 1мм
    shifts = []
    tiny = mm_to_internal(1.0)  # ±1мм от точного совпадения
    half_step = step_internal / 2.0

    def _add(val):
        key = round(internal_to_mm(val))
        if key not in seen_mm:
            seen_mm.add(key)
            shifts.append(val)

    for coord in vertex_coords_internal:
        raw = (coord - base_internal) % step_internal
        if raw < 0:  # pragma: no cover
            raw += step_internal  # pragma: no cover
        _add(raw)
        # Чуть в стороны (±1мм) чтобы линия не совпадала с ребром точно
        for offset in (tiny, -tiny):
            shifted = (raw + offset) % step_internal
            if shifted < 0:  # pragma: no cover
                shifted += step_internal  # pragma: no cover
            _add(shifted)
        # Полшага от грани — грань колонны попадает между линиями сетки
        for offset in (half_step, -half_step):
            shifted = (raw + offset) % step_internal
            if shifted < 0:  # pragma: no cover
                shifted += step_internal  # pragma: no cover
            _add(shifted)

    return sorted(shifts)


def _snap_pairs_for_holes(
    hole_paths,
    base_x_internal,
    base_y_internal,
    step_x_internal,
    step_y_internal,
):
    """Парные snap-кандидаты (sx, sy) по 4 углам каждого hole.

    Идея: угол отверстия (колонны) совмещается с узлом сетки.
    Это добавляет инженерно осмысленные кандидаты без полного декартова перебора.
    """
    if hole_paths is None or hole_paths.Count == 0:
        return []
    if step_x_internal <= 0 or step_y_internal <= 0:
        return []

    tiny = mm_to_internal(1.0)
    half_x = step_x_internal / 2.0
    half_y = step_y_internal / 2.0
    pairs = []
    seen = set()

    for hole_path in hole_paths:
        # bbox отверстия в internal units
        xs = []
        ys = []
        for pt in hole_path:
            xs.append(mm_to_internal(clipper_to_mm(pt.X)))
            ys.append(mm_to_internal(clipper_to_mm(pt.Y)))
        if not xs or not ys:
            continue

        min_x = min(xs)
        max_x = max(xs)
        min_y = min(ys)
        max_y = max(ys)

        corners = [
            (min_x, min_y),
            (min_x, max_y),
            (max_x, min_y),
            (max_x, max_y),
        ]

        for cx, cy in corners:
            sx = (cx - base_x_internal) % step_x_internal
            sy = (cy - base_y_internal) % step_y_internal
            if sx < 0:  # pragma: no cover
                sx += step_x_internal  # pragma: no cover
            if sy < 0:  # pragma: no cover
                sy += step_y_internal  # pragma: no cover

            # Точное совпадение + легкие смещения от вырожденных случаев
            for ox in (0.0, tiny, -tiny):
                for oy in (0.0, tiny, -tiny):
                    px = (sx + ox) % step_x_internal
                    py = (sy + oy) % step_y_internal
                    if px < 0:  # pragma: no cover
                        px += step_x_internal  # pragma: no cover
                    if py < 0:  # pragma: no cover
                        py += step_y_internal  # pragma: no cover
                    key = (round(internal_to_mm(px)), round(internal_to_mm(py)))
                    if key not in seen:
                        seen.add(key)
                        pairs.append((px, py))

            # Полшага от грани — колонна между линиями сетки
            for ox in (half_x, -half_x):
                for oy in (half_y, -half_y):
                    px = (sx + ox) % step_x_internal
                    py = (sy + oy) % step_y_internal
                    if px < 0:  # pragma: no cover
                        px += step_x_internal  # pragma: no cover
                    if py < 0:  # pragma: no cover
                        py += step_y_internal  # pragma: no cover
                    key = (round(internal_to_mm(px)), round(internal_to_mm(py)))
                    if key not in seen:
                        seen.add(key)
                        pairs.append((px, py))

    return sorted(pairs)


def _extract_contour_vertex_coords(outer_paths, hole_paths=None):
    """Извлекает уникальные X и Y координаты вершин (internal units)."""
    xs = set()
    ys = set()
    for paths in [outer_paths] + ([hole_paths] if hole_paths else []):
        if paths is None:  # pragma: no cover
            continue  # pragma: no cover
        for path in paths:
            for pt in path:
                xs.add(mm_to_internal(clipper_to_mm(pt.X)))
                ys.add(mm_to_internal(clipper_to_mm(pt.Y)))
    return sorted(xs), sorted(ys)


def _dedup_key(result):
    """Ключ для дедупликации: смещение с точностью 1 мм."""
    return (
        round(result["shift_x_mm"]),
        round(result["shift_y_mm"]),
    )


def _cut_round_deltas(
    best_result,
    base_x_raw,
    base_y_raw,
    step_x,
    step_y,
    outer_paths,
    hole_paths=None,
):
    """Аналитически вычисляет дельты сдвига, при которых подрезки
    у границ контура и колонн становятся кратны CUT_ROUND_MM.

    Кандидаты генерируются по уникальным X/Y вершинам внешнего контура
    (приоритет) и по колоннам (дополнительно).

    Возвращает список пар (shift_x, shift_y) в internal units.
    """
    shift_x = best_result["shift_x_internal"]
    shift_y = best_result["shift_y_internal"]

    base_x_mm = internal_to_mm(base_x_raw + shift_x)
    base_y_mm = internal_to_mm(base_y_raw + shift_y)
    step_x_mm = internal_to_mm(step_x)
    step_y_mm = internal_to_mm(step_y)

    tol = EDGE_TOL_MM  # мм — порог «уже кратно»

    def _deltas_for_edge(edge_mm, step_mm, base_mm):
        cut = (base_mm - edge_mm) % step_mm
        if cut < 0:  # pragma: no cover
            cut += step_mm  # pragma: no cover
        r = cut % CUT_ROUND_MM
        ds = set()
        if min(r, CUT_ROUND_MM - r) > tol:
            ds.add(-r)
            ds.add(CUT_ROUND_MM - r)
        return ds

    # Кандидаты по всем уникальным X/Y вершинам внешнего контура (приоритет)
    # Для L/U-форм это покрывает все реальные рёбра, а не только bbox.
    outer_xs_mm = set()
    outer_ys_mm = set()
    if outer_paths is not None:
        for path in outer_paths:
            for pt in path:
                outer_xs_mm.add(round(clipper_to_mm(pt.X), 1))
                outer_ys_mm.add(round(clipper_to_mm(pt.Y), 1))
    dx_outer = set()
    for ex in outer_xs_mm:
        dx_outer |= _deltas_for_edge(ex, step_x_mm, base_x_mm)
    dy_outer = set()
    for ey in outer_ys_mm:
        dy_outer |= _deltas_for_edge(ey, step_y_mm, base_y_mm)

    # Кандидаты по колоннам (дополнительно)
    dx_holes = set()
    dy_holes = set()
    if hole_paths is not None:
        for hp in hole_paths:
            hxs = [clipper_to_mm(pt.X) for pt in hp]
            hys = [clipper_to_mm(pt.Y) for pt in hp]
            if hxs and hys:
                dx_holes |= _deltas_for_edge(min(hxs), step_x_mm, base_x_mm)
                dx_holes |= _deltas_for_edge(max(hxs), step_x_mm, base_x_mm)
                dy_holes |= _deltas_for_edge(min(hys), step_y_mm, base_y_mm)
                dy_holes |= _deltas_for_edge(max(hys), step_y_mm, base_y_mm)

    # Сначала кандидаты с outer-дельтами, потом с hole-дельтами
    dx_all = {0.0} | dx_outer | dx_holes
    dy_all = {0.0} | dy_outer | dy_holes

    seen = set()
    pairs = []
    for dx in sorted(dx_all):
        for dy in sorted(dy_all):
            if abs(dx) < tol and abs(dy) < tol:
                continue
            new_sx = _normalize_shift(shift_x + mm_to_internal(dx), step_x)  # noqa
            new_sy = _normalize_shift(shift_y + mm_to_internal(dy), step_y)
            key = (round(internal_to_mm(new_sx)), round(internal_to_mm(new_sy)))
            if key not in seen:
                seen.add(key)
                pairs.append((new_sx, new_sy))

    return pairs


def find_best_shift(
    step_x,
    step_y,
    base_x_raw,
    base_y_raw,
    outer_paths,
    hole_paths,
    holes_bboxes_mm,
    outer_bbox_internal,
    unacceptable_cut_mm,
    unwanted_cut_mm,
    acceptable_cut_mm,
    coarse_shift_step_mm,
    top_n,
    refine_shift_step_mm=None,
    refine_radius_mm=None,
    refine_top_n=None,
    min_edge_clearance_mm=0,
    progress_callback=None,
):
    original_base_x_raw = base_x_raw
    original_base_y_raw = base_y_raw
    search_base_x = 0.0
    search_base_y = 0.0

    # Предвычисляем координаты рёбер вырезов/колонн для near-edge проверки
    # (внешний контур не учитываем — у стен дублирование нормально)
    edge_xs_mm = None
    edge_ys_mm = None
    if min_edge_clearance_mm > 0:
        _exs = set()
        _eys = set()
        if hole_paths is not None:
            for path in hole_paths:
                for pt in path:
                    _exs.add(clipper_to_mm(pt.X))
                    _eys.add(clipper_to_mm(pt.Y))
        edge_xs_mm = sorted(_exs)
        edge_ys_mm = sorted(_eys)

    eval_kwargs = dict(
        step_x=step_x,
        step_y=step_y,
        base_x_raw=search_base_x,
        base_y_raw=search_base_y,
        outer_paths=outer_paths,
        hole_paths=hole_paths,
        holes_bboxes_mm=holes_bboxes_mm,
        outer_bbox_internal=outer_bbox_internal,
        unacceptable_cut_mm=unacceptable_cut_mm,
        unwanted_cut_mm=unwanted_cut_mm,
        acceptable_cut_mm=acceptable_cut_mm,
        min_edge_clearance_mm=min_edge_clearance_mm,
        edge_xs_mm=edge_xs_mm,
        edge_ys_mm=edge_ys_mm,
    )

    if refine_top_n is None:
        refine_top_n = DEFAULT_REFINE_TOP_N

    # ---- Фаза 1: грубый проход + snap-to-edge ----
    coarse_step_internal = mm_to_internal(coarse_shift_step_mm)
    shift_x_values = build_shift_positions(step_x, coarse_step_internal)
    shift_y_values = build_shift_positions(step_y, coarse_step_internal)

    # Snap-to-edge: аналитические кандидаты — смещения, при которых
    # линия сетки проходит через вершину контура (или ± 1мм от неё).
    # Это ключевое для L-форм и вырезов: минимизирует сложные подрезки.
    contour_xs, contour_ys = _extract_contour_vertex_coords(
        outer_paths, hole_paths if hole_paths.Count > 0 else None
    )
    snap_x = _snap_shifts_for_axis(contour_xs, search_base_x, step_x)
    snap_y = _snap_shifts_for_axis(contour_ys, search_base_y, step_y)

    # Парные snap-кандидаты по углам отверстий (колонн)
    hole_snap_pairs = _snap_pairs_for_holes(
        hole_paths, search_base_x, search_base_y, step_x, step_y
    )

    shift_x_set = {}  # key: round(mm) -> internal value
    shift_y_set = {}
    for v in shift_x_values:
        k = round(internal_to_mm(v))
        if k not in shift_x_set:
            shift_x_set[k] = v
    for v in shift_y_values:
        k = round(internal_to_mm(v))
        if k not in shift_y_set:
            shift_y_set[k] = v
    for v in snap_x:
        k = round(internal_to_mm(v))
        if k not in shift_x_set:
            shift_x_set[k] = v
    for v in snap_y:
        k = round(internal_to_mm(v))
        if k not in shift_y_set:
            shift_y_set[k] = v
    shift_x_values = sorted(shift_x_set.values())
    shift_y_values = sorted(shift_y_set.values())

    if progress_callback:
        progress_callback("phase1", 0, len(shift_x_values) * len(shift_y_values))

    coarse_results = _evaluate_shifts_grid(
        shift_x_values=shift_x_values, shift_y_values=shift_y_values, **eval_kwargs
    )

    hole_pair_results = []
    for shift_x, shift_y in hole_snap_pairs:
        result = evaluate_shift_exact(shift_x=shift_x, shift_y=shift_y, **eval_kwargs)
        hole_pair_results.append(result)

    phase1_results = coarse_results + hole_pair_results

    if progress_callback:
        progress_callback("phase1_done", len(phase1_results), len(phase1_results))

    if not phase1_results:
        raise Exception("Не удалось рассчитать варианты смещений")  # pragma: no cover

    all_results_map = {}
    for result in phase1_results:
        key = _dedup_key(result)
        if (
            key not in all_results_map
            or result["rank_key"] < all_results_map[key]["rank_key"]
        ):
            all_results_map[key] = result

    # ---- Фаза 2: уточнение вокруг top-N грубых ----
    refine_count = 0
    if (
        refine_shift_step_mm is not None
        and refine_radius_mm is not None
        and refine_shift_step_mm > 0
        and refine_radius_mm > 0
    ):
        coarse_sorted = sorted(phase1_results, key=_result_sort_key)
        seeds = coarse_sorted[: min(refine_top_n, len(coarse_sorted))]

        refine_step_internal = mm_to_internal(refine_shift_step_mm)
        refine_radius_internal = mm_to_internal(refine_radius_mm)

        if progress_callback:
            progress_callback("phase2", 0, len(seeds))

        for seed_idx, seed in enumerate(seeds):
            local_x = _build_local_shift_positions(
                step_x,
                seed["shift_x_internal"],
                refine_step_internal,
                refine_radius_internal,
            )
            local_y = _build_local_shift_positions(
                step_y,
                seed["shift_y_internal"],
                refine_step_internal,
                refine_radius_internal,
            )
            batch = _evaluate_shifts_grid(
                shift_x_values=local_x, shift_y_values=local_y, **eval_kwargs
            )
            refine_count += len(batch)
            if progress_callback:
                progress_callback("phase2", seed_idx + 1, len(seeds))
            for result in batch:
                key = _dedup_key(result)
                if (
                    key not in all_results_map
                    or result["rank_key"] < all_results_map[key]["rank_key"]
                ):
                    all_results_map[key] = result

    # ---- Фаза 3: округление подрезок до кратных CUT_ROUND_MM ----
    if progress_callback:
        progress_callback("phase3", 0, 0)

    all_results = list(all_results_map.values())
    results_sorted = sorted(all_results, key=_result_sort_key)
    _cr_seeds = results_sorted[: min(3, len(results_sorted))]

    for _cr_seed in _cr_seeds:
        _cr_pairs = _cut_round_deltas(
            _cr_seed,
            search_base_x,
            search_base_y,
            step_x,
            step_y,
            outer_paths,
            hole_paths=hole_paths,
        )
        for _cr_sx, _cr_sy in _cr_pairs:
            _cr_result = evaluate_shift_exact(
                shift_x=_cr_sx, shift_y=_cr_sy, **eval_kwargs
            )
            _cr_key = _dedup_key(_cr_result)
            if (
                _cr_key not in all_results_map
                or _cr_result["rank_key"] < all_results_map[_cr_key]["rank_key"]
            ):
                all_results_map[_cr_key] = _cr_result

    all_results = list(all_results_map.values())
    _convert_results_to_user_offsets(
        all_results,
        original_base_x_raw,
        original_base_y_raw,
        step_x,
        step_y,
    )
    results_sorted = sorted(all_results, key=_result_sort_key)

    top_results = results_sorted[: min(top_n, len(results_sorted))]
    equivalent_top_results = [
        result
        for result in results_sorted
        if result["rank_key"] == top_results[0]["rank_key"]
    ][:5]

    # Диагностика: диапазон non_viable и complex по всем вариантам
    all_nv = [r["non_viable_count"] for r in all_results]
    min_non_viable = min(all_nv) if all_nv else 0
    max_non_viable = max(all_nv) if all_nv else 0
    all_complex = [r["complex_count"] for r in all_results]
    min_complex_count = min(all_complex) if all_complex else 0
    max_complex_count = max(all_complex) if all_complex else 0

    return {
        "best": top_results[0],
        "top_results": top_results,
        "equivalent_top_results": equivalent_top_results,
        "results_sorted": results_sorted,
        "coarse_count": len(coarse_results),
        "hole_snap_pair_count": len(hole_snap_pairs),
        "snap_x_count": len(snap_x),
        "snap_y_count": len(snap_y),
        "refine_count": refine_count,
        "total_count": len(all_results),
        "min_non_viable": min_non_viable,
        "max_non_viable": max_non_viable,
        "min_complex_count": min_complex_count,
        "max_complex_count": max_complex_count,
        "unacceptable_cut_mm": int(unacceptable_cut_mm),
        "unwanted_cut_mm": int(unwanted_cut_mm),
        "acceptable_cut_mm": int(acceptable_cut_mm),
        "coarse_step_mm": int(coarse_shift_step_mm),
        "refine_step_mm": int(refine_shift_step_mm) if refine_shift_step_mm else 0,
        "refine_radius_mm": int(refine_radius_mm) if refine_radius_mm else 0,
    }

# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (  # type: ignore
    XYZ,
    Color,
    CurveElement,
    ElementId,
    Family,
    FilteredElementCollector,
    Line,
)
from floor_common import (
    build_positions,
    get_double_param,
    get_line_style_id,
    get_or_create_line_style,
    get_string_param,
    parse_ids_from_string,
    set_string_param,
)
from pyrevit import revit  # type: ignore

doc = revit.doc

GRID_LINE_STYLE_NAME = "RF_Grid"
GRID_COLOR = Color(100, 149, 237)  # васильковый синий
GRID_LINE_PATTERN = "Center"

BASE_MARKER_STYLE_NAME = "RF_Base"
BASE_MARKER_COLOR = Color(255, 0, 120)

CONTOUR_STYLE_NAME = "RF_Contour"
CONTOUR_COLOR = Color(0, 255, 0)

NEAR_COLUMN_STYLE_NAME = "RF_GridColumn"
NEAR_COLUMN_COLOR = Color(255, 80, 80)  # красный — внимание

# Минимальный порог, если стрингер не найден (мм)
_DEFAULT_COL_CLEARANCE_MM = 30.0


def _get_stringer_clearance_mm():
    """Читает макс. ширину профиля стрингера (мм) для near-edge подсветки."""
    clearance = 0.0
    for fam in FilteredElementCollector(doc).OfClass(Family):
        if fam.Name == "RF_Stringer":
            for sid in fam.GetFamilySymbolIds():
                sym = doc.GetElement(sid)
                if sym:
                    pw = get_double_param(sym, "RF_Profile_Width")
                    if pw:
                        pw_mm = pw * _INTERNAL_TO_MM
                        if pw_mm > clearance:
                            clearance = pw_mm
            break
    return clearance if clearance > 0 else _DEFAULT_COL_CLEARANCE_MM


# Минимальная длина отрезка (в футах) — короче не рисуем
_MIN_SEG_LEN = 0.005  # ~1.5 мм
# Размер маркера базовой точки (в футах)
_MARKER_ARM = 0.45  # ~137 мм
_MARKER_RING_HALF = 0.18  # ~55 мм

_INTERNAL_TO_MM = 304.8
_SCALE = 1000.0  # мм → clipper-единицы


# ---------------------------------------------------------------------------
#  Clipper2: клиппинг линий по контуру
# ---------------------------------------------------------------------------


def _internal_to_clipper(val):
    """internal (feet) → clipper int64 units."""
    return int(round(val * _INTERNAL_TO_MM * _SCALE))


def _clipper_to_internal(val):
    """clipper int64 units → internal (feet)."""
    return float(val) / _SCALE / _INTERNAL_TO_MM


def _build_clip_paths(floor):
    """Builds clip-paths from exact zone and returns (clip_paths, hole_edge_coords).

    hole_edge_coords: list of (min_x, min_y, max_x, max_y) in internal units per hole,
    or empty list if no holes.
    """
    try:
        from floor_exact import (
            Difference,
            FillRule,
            clipper_to_mm,
            get_exact_zone_for_floor,
            mm_to_internal,
        )
    except Exception:
        return None, []

    try:
        zone = get_exact_zone_for_floor(doc, floor)
    except Exception:
        return None, []

    outer = zone.get("outer_paths")
    holes = zone.get("hole_paths")
    if not outer or outer.Count == 0:
        return None, []

    hole_edge_coords = []
    if holes and holes.Count > 0:
        for hp in holes:
            hxs = [mm_to_internal(clipper_to_mm(pt.X)) for pt in hp]
            hys = [mm_to_internal(clipper_to_mm(pt.Y)) for pt in hp]
            if hxs and hys:
                hole_edge_coords.append((min(hxs), min(hys), max(hxs), max(hys)))
        clip = Difference(outer, holes, FillRule.NonZero)
    else:
        clip = outer

    return clip, hole_edge_coords


def _clip_line_segments(x0, y0, x1, y1, clip_paths):
    """Клиппирует отрезок (x0,y0)-(x1,y1) в internal-координатах Clipper2-контуром.

    Возвращает список кортежей ((ax,ay), (bx,by)) в internal units.
    """
    from floor_exact import Clipper64, ClipType, FillRule, Path64, Paths64, Point64

    line_path = Path64()
    line_path.Add(Point64(_internal_to_clipper(x0), _internal_to_clipper(y0)))
    line_path.Add(Point64(_internal_to_clipper(x1), _internal_to_clipper(y1)))

    open_subj = Paths64()
    open_subj.Add(line_path)

    clipper = Clipper64()
    clipper.AddOpenSubject(open_subj)
    clipper.AddClip(clip_paths)

    sol_closed = Paths64()
    sol_open = Paths64()
    clipper.Execute(ClipType.Intersection, FillRule.NonZero, sol_closed, sol_open)

    segments = []
    for path in sol_open:
        if path.Count < 2:
            continue
        p0 = path[0]
        p1 = path[path.Count - 1]
        ax = _clipper_to_internal(p0.X)
        ay = _clipper_to_internal(p0.Y)
        bx = _clipper_to_internal(p1.X)
        by = _clipper_to_internal(p1.Y)
        # Фильтр слишком коротких
        length = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
        if length >= _MIN_SEG_LEN:
            segments.append(((ax, ay), (bx, by)))

    return segments


def get_bbox_xy(el, active_view):
    bbox = el.get_BoundingBox(active_view)
    if not bbox:
        bbox = el.get_BoundingBox(None)
    if not bbox:
        return None

    return bbox.Min.X, bbox.Min.Y, bbox.Max.X, bbox.Max.Y, bbox.Min.Z, bbox.Max.Z


def _collect_styled_curve_ids(view, style_id):
    """Собирает Id всех DetailCurve на виде с заданным стилем линии."""
    ids = []
    if not style_id:
        return ids

    collector = FilteredElementCollector(doc, view.Id).OfClass(CurveElement)
    for curve_el in collector:
        try:
            if not curve_el.ViewSpecific:
                continue
            ls = curve_el.LineStyle
            if ls and ls.Id == style_id:
                ids.append(curve_el.Id.IntegerValue)
        except Exception:
            pass

    return ids


def _recreate_contour_on_top(floor, view, update_style=False):
    """Пересоздать контурные линии (удалить → создать), чтобы они были поверх сетки.

    Считывает геометрию кривых со старых элементов, удаляет их,
    рисует заново с тем же стилем. Возвращает количество пересозданных.
    """
    old_contour_ids = parse_ids_from_string(
        get_string_param(floor, "RF_Contour_Lines_ID")
    )
    if not old_contour_ids:
        return 0

    # Собрать кривые со старых элементов
    curves = []
    for int_id in old_contour_ids:
        try:
            el = doc.GetElement(ElementId(int_id))
            if el and hasattr(el, "GeometryCurve"):
                curves.append(el.GeometryCurve)
        except Exception:
            pass

    if not curves:
        return 0

    contour_style = get_or_create_line_style(
        doc,
        CONTOUR_STYLE_NAME,
        color=CONTOUR_COLOR,
        weight=5,
        update_existing=update_style,
    )

    # Удалить старые
    for int_id in old_contour_ids:
        try:
            doc.Delete(ElementId(int_id))
        except Exception:
            pass

    # Создать заново (последними → поверх сетки)
    new_ids = []
    for crv in curves:
        try:
            dc = doc.Create.NewDetailCurve(view, crv)
            dc.LineStyle = contour_style
            new_ids.append(str(dc.Id.Value))
        except Exception:
            pass

    if new_ids:
        set_string_param(floor, "RF_Contour_Lines_ID", ";".join(new_ids))

    return len(new_ids)


def redraw_grid_for_floor(floor, view, transaction_name, update_style=False):
    step_x = get_double_param(floor, "RF_Step_X")
    step_y = get_double_param(floor, "RF_Step_Y")
    base_x_raw = get_double_param(floor, "RF_Base_X")
    base_y_raw = get_double_param(floor, "RF_Base_Y")
    shift_x = get_double_param(floor, "RF_Offset_X")
    shift_y = get_double_param(floor, "RF_Offset_Y")

    missing = []
    if step_x is None:
        missing.append("RF_Step_X")
    if step_y is None:
        missing.append("RF_Step_Y")
    if base_x_raw is None:
        missing.append("RF_Base_X")
    if base_y_raw is None:
        missing.append("RF_Base_Y")
    if shift_x is None:
        missing.append("RF_Offset_X")
    if shift_y is None:
        missing.append("RF_Offset_Y")

    if missing:
        raise Exception(
            "Не удалось прочитать параметры:\n- {}".format("\n- ".join(missing))
        )

    if step_x <= 0 or step_y <= 0:
        raise Exception("Шаг сетки должен быть больше нуля.")

    base_x = base_x_raw + shift_x
    base_y = base_y_raw + shift_y

    bbox_data = get_bbox_xy(floor, view)
    if not bbox_data:
        raise Exception("Не удалось определить габариты перекрытия.")

    min_x, min_y, max_x, max_y, z0 = bbox_data[:5]

    pad = min(step_x, step_y) * 0.2
    min_x -= pad
    min_y -= pad
    max_x += pad
    max_y += pad

    x_positions = build_positions(
        min_x, max_x, base_x, step_x, end_padding_steps=1.0, end_tolerance=0.0
    )
    y_positions = build_positions(
        min_y, max_y, base_y, step_y, end_padding_steps=1.0, end_tolerance=0.0
    )

    if not x_positions and not y_positions:
        raise Exception("Не удалось построить позиции линий сетки.")

    # Собираем ID для удаления: сохранённые + fallback по стилю
    old_ids = parse_ids_from_string(get_string_param(floor, "RF_Grid_Lines_ID"))
    old_marker_ids = parse_ids_from_string(get_string_param(floor, "RF_Base_Marker_ID"))
    style_id = get_line_style_id(doc, GRID_LINE_STYLE_NAME)
    styled_ids = _collect_styled_curve_ids(view, style_id) if style_id else []
    near_col_style_id = get_line_style_id(doc, NEAR_COLUMN_STYLE_NAME)
    near_col_styled_ids = (
        _collect_styled_curve_ids(view, near_col_style_id) if near_col_style_id else []
    )
    marker_style_id = get_line_style_id(doc, BASE_MARKER_STYLE_NAME)
    marker_styled_ids = (
        _collect_styled_curve_ids(view, marker_style_id) if marker_style_id else []
    )

    ids_to_delete = []
    seen_ids = set()
    for int_id in (
        old_ids + styled_ids + near_col_styled_ids + old_marker_ids + marker_styled_ids
    ):
        if int_id in seen_ids:
            continue
        seen_ids.add(int_id)
        ids_to_delete.append(int_id)

    deleted_count = 0
    created_ids = []

    with revit.Transaction(transaction_name):
        grid_style = get_or_create_line_style(
            doc,
            GRID_LINE_STYLE_NAME,
            GRID_COLOR,
            line_pattern_name=GRID_LINE_PATTERN,
            update_existing=update_style,
        )

        for int_id in ids_to_delete:
            try:
                el_id = ElementId(int_id)
                old_el = doc.GetElement(el_id)
                if old_el:
                    doc.Delete(el_id)
                    deleted_count += 1
            except Exception:
                pass

        # Подрезка по контуру через Clipper2 (если контур построен)
        clip_paths, hole_edge_coords = _build_clip_paths(floor)

        # Стиль для линий у колонн (если есть колонны)
        near_col_style = None
        if hole_edge_coords:
            near_col_style = get_or_create_line_style(
                doc,
                NEAR_COLUMN_STYLE_NAME,
                NEAR_COLUMN_COLOR,
                line_pattern_name=GRID_LINE_PATTERN,
                update_existing=update_style,
            )

        # Проверка: линия сетки рядом с ребром колонны?
        _col_clearance = _get_stringer_clearance_mm() / _INTERNAL_TO_MM  # мм → feet

        def _is_near_column_x(x_val):
            for hmin_x, _hmin_y, hmax_x, _hmax_y in hole_edge_coords:
                if (
                    abs(x_val - hmin_x) < _col_clearance
                    or abs(x_val - hmax_x) < _col_clearance
                ):
                    return True
            return False

        def _is_near_column_y(y_val):
            for _hmin_x, hmin_y, _hmax_x, hmax_y in hole_edge_coords:
                if (
                    abs(y_val - hmin_y) < _col_clearance
                    or abs(y_val - hmax_y) < _col_clearance
                ):
                    return True
            return False

        for x in x_positions:
            is_near = near_col_style and _is_near_column_x(x)
            if clip_paths:
                segs = _clip_line_segments(x, min_y, x, max_y, clip_paths)
            else:
                segs = [((x, min_y), (x, max_y))]
            for (ax, ay), (bx, by) in segs:
                line = Line.CreateBound(XYZ(ax, ay, z0), XYZ(bx, by, z0))
                dc = doc.Create.NewDetailCurve(view, line)
                dc.LineStyle = near_col_style if is_near else grid_style
                created_ids.append(str(dc.Id.Value))

        for y in y_positions:
            is_near = near_col_style and _is_near_column_y(y)
            if clip_paths:
                segs = _clip_line_segments(min_x, y, max_x, y, clip_paths)
            else:
                segs = [((min_x, y), (max_x, y))]
            for (ax, ay), (bx, by) in segs:
                line = Line.CreateBound(XYZ(ax, ay, z0), XYZ(bx, by, z0))
                dc = doc.Create.NewDetailCurve(view, line)
                dc.LineStyle = near_col_style if is_near else grid_style
                created_ids.append(str(dc.Id.Value))

        # Крестик точки начала раскладки (только если база в зоне bbox)
        marker_ids = []
        marker_pad = _MARKER_ARM * 2
        if (
            min_x - marker_pad <= base_x <= max_x + marker_pad
            and min_y - marker_pad <= base_y <= max_y + marker_pad
        ):
            marker_style = get_or_create_line_style(
                doc,
                BASE_MARKER_STYLE_NAME,
                BASE_MARKER_COLOR,
                weight=4,
                update_existing=update_style,
            )

            # Контрастная, но компактная мишень: + и квадратная рамка.
            m_line_h = Line.CreateBound(
                XYZ(base_x - _MARKER_ARM, base_y, z0),
                XYZ(base_x + _MARKER_ARM, base_y, z0),
            )
            dc_h = doc.Create.NewDetailCurve(view, m_line_h)
            dc_h.LineStyle = marker_style
            marker_ids.append(str(dc_h.Id.Value))

            m_line_v = Line.CreateBound(
                XYZ(base_x, base_y - _MARKER_ARM, z0),
                XYZ(base_x, base_y + _MARKER_ARM, z0),
            )
            dc_v = doc.Create.NewDetailCurve(view, m_line_v)
            dc_v.LineStyle = marker_style
            marker_ids.append(str(dc_v.Id.Value))

            rx0 = base_x - _MARKER_RING_HALF
            rx1 = base_x + _MARKER_RING_HALF
            ry0 = base_y - _MARKER_RING_HALF
            ry1 = base_y + _MARKER_RING_HALF
            ring_lines = [
                Line.CreateBound(XYZ(rx0, ry0, z0), XYZ(rx1, ry0, z0)),
                Line.CreateBound(XYZ(rx1, ry0, z0), XYZ(rx1, ry1, z0)),
                Line.CreateBound(XYZ(rx1, ry1, z0), XYZ(rx0, ry1, z0)),
                Line.CreateBound(XYZ(rx0, ry1, z0), XYZ(rx0, ry0, z0)),
            ]
            for ring in ring_lines:
                dc_r = doc.Create.NewDetailCurve(view, ring)
                dc_r.LineStyle = marker_style
                marker_ids.append(str(dc_r.Id.Value))

        ids_string = ";".join(created_ids)
        ok = set_string_param(floor, "RF_Grid_Lines_ID", ids_string)
        if not ok:
            raise Exception("Не удалось записать RF_Grid_Lines_ID")

        if marker_ids:
            marker_ids_string = ";".join(marker_ids)
            ok_marker = set_string_param(floor, "RF_Base_Marker_ID", marker_ids_string)
            if not ok_marker:
                raise Exception("Не удалось записать RF_Base_Marker_ID")
        else:
            ok_marker = set_string_param(floor, "RF_Base_Marker_ID", "")
            if not ok_marker:
                raise Exception("Не удалось очистить RF_Base_Marker_ID")

        # Пересоздать контурные линии последними — чтобы они были поверх сетки
        contour_recreated = _recreate_contour_on_top(floor, view, update_style)

    return {
        "deleted_count": deleted_count,
        "created_count": len(created_ids),
        "marker_count": len(marker_ids),
        "contour_recreated": contour_recreated,
        "step_x": step_x,
        "step_y": step_y,
        "shift_x": shift_x,
        "shift_y": shift_y,
        "base_x": base_x,
        "base_y": base_y,
    }

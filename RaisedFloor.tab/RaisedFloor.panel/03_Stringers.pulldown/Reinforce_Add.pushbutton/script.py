# -*- coding: utf-8 -*-
"""Лонжероны: добавить зону усиления (Линия / Прямоугольник)."""

import math
from datetime import datetime

from Autodesk.Revit.DB import (  # type: ignore
    XYZ,
    Color,
    ElementId,
    ElementTransformUtils,
    Family,
    FilteredElementCollector,
    Line,
    StorageType,
    ViewPlan,
)
from Autodesk.Revit.DB.Structure import StructuralType  # type: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType, PickBoxStyle  # type: ignore
from floor_common import (  # type: ignore
    FloorOrPartSelectionFilter,
    build_support_nodes,
    cut_at_positions_1d,
    cut_equal_1d,
    get_double_param,
    get_mm_param,
    get_or_create_line_style,
    get_source_floor,
    get_string_param,
    load_reinforcement_zones,
    normalize_legacy_mm_param,
    parse_ids_from_string,
    save_reinforcement_zones,
)
from floor_exact import internal_to_mm, mm_to_internal  # type: ignore
from floor_grid import get_bbox_xy  # type: ignore
from floor_i18n import tr  # type: ignore
from pyrevit import forms, revit  # type: ignore
from revit_context import get_active_view, get_doc, get_uidoc  # type: ignore

doc = None
uidoc = None
view = None

TITLE = tr("reinf_add_title")
FAMILY_LONGERON = "RF_Stringer"
FAMILY_SUPPORT = "RF_Support"
PARAM_ZONES = "RF_Reinf_Zones_JSON"
TOL = 1e-6
DEFAULT_SUPPORT_SPACING_MM = 1000.0
PREVIEW_STYLE_UPPER = "RF_Preview_Top"
PREVIEW_STYLE_LOWER = "RF_Preview_Bottom"


class _Cancel(Exception):
    pass


def _draw_preview(upper_segs, lower_segs, z0):
    """Draw dashed detail lines as preview; return list of ElementIds."""
    ids = []
    style_upper = get_or_create_line_style(
        doc,
        PREVIEW_STYLE_UPPER,
        color=Color(0, 120, 255),
        weight=1,
        line_pattern_name="Dash",
    )
    style_lower = get_or_create_line_style(
        doc,
        PREVIEW_STYLE_LOWER,
        color=Color(255, 80, 0),
        weight=1,
        line_pattern_name="Dash",
    )
    for x1, y1, x2, y2 in upper_segs:
        try:
            crv = Line.CreateBound(XYZ(x1, y1, z0), XYZ(x2, y2, z0))
            dc = doc.Create.NewDetailCurve(view, crv)
            dc.LineStyle = style_upper
            ids.append(dc.Id)
        except Exception:
            pass
    for x1, y1, x2, y2 in lower_segs:
        try:
            crv = Line.CreateBound(XYZ(x1, y1, z0), XYZ(x2, y2, z0))
            dc = doc.Create.NewDetailCurve(view, crv)
            dc.LineStyle = style_lower
            ids.append(dc.Id)
        except Exception:
            pass
    return ids


def _delete_preview(preview_ids):
    for eid in preview_ids:
        try:
            doc.Delete(eid)
        except Exception:
            pass


def _rc(v):
    return round(v, 6)


def _eid_int(eid):
    try:
        return eid.Value
    except Exception:
        return eid.IntegerValue


def _set_param(inst, name, value):
    p = inst.LookupParameter(name)
    if not p or p.IsReadOnly:
        return
    if p.StorageType == StorageType.Integer:
        p.Set(int(value))
    elif p.StorageType == StorageType.Double:
        p.Set(float(value))
    elif p.StorageType == StorageType.String:
        p.Set(str(value))


def _find_symbols(family_name):
    for fam in FilteredElementCollector(doc).OfClass(Family):
        if fam.Name != family_name:
            continue
        result = {}
        for sid in fam.GetFamilySymbolIds():
            sym = doc.GetElement(sid)
            if not sym:
                continue
            try:
                name = sym.Name
            except Exception:
                name = str(_eid_int(sym.Id))
            result[name] = sym
        return result
    return {}


def _pick_floor():
    if not isinstance(view, ViewPlan):
        forms.alert(tr("open_plan"), title=TITLE)
        raise _Cancel()

    try:
        ref = uidoc.Selection.PickObject(
            ObjectType.Element,
            FloorOrPartSelectionFilter(),
            tr("pick_floor_prompt"),
        )
    except OperationCanceledException:
        raise _Cancel()

    floor = get_source_floor(doc.GetElement(ref.ElementId))
    if not floor:
        raise Exception(tr("source_floor_not_found"))
    return floor


def _pick_rect():
    # Более наглядный UX: сначала пытаемся взять прямоугольник рамкой.
    try:
        box = uidoc.Selection.PickBox(
            PickBoxStyle.Enclosing,
            "Обведи зону усиления рамкой",
        )
        x_min, x_max = min(box.Min.X, box.Max.X), max(box.Min.X, box.Max.X)
        y_min, y_max = min(box.Min.Y, box.Max.Y), max(box.Min.Y, box.Max.Y)
        if (x_max - x_min) >= TOL and (y_max - y_min) >= TOL:
            return x_min, y_min, x_max, y_max
    except OperationCanceledException:
        raise _Cancel()
    except Exception:
        pass

    # Fallback для окружений, где PickBox недоступен.
    try:
        p1 = uidoc.Selection.PickPoint("Точка 1 прямоугольника зоны усиления")
        p2 = uidoc.Selection.PickPoint("Точка 2 прямоугольника зоны усиления")
    except OperationCanceledException:
        raise _Cancel()

    x_min, x_max = min(p1.X, p2.X), max(p1.X, p2.X)
    y_min, y_max = min(p1.Y, p2.Y), max(p1.Y, p2.Y)
    if (x_max - x_min) < TOL or (y_max - y_min) < TOL:
        raise Exception("Прямоугольник слишком мал")
    return x_min, y_min, x_max, y_max


def _pick_line():
    mode = forms.CommandSwitchWindow.show(
        ["Провести 2 точки", "Выбрать существующую линию"],
        message="Как задать линию усиления:",
    )
    if not mode:
        raise _Cancel()

    if mode.startswith("Выбрать"):
        try:
            ref = uidoc.Selection.PickObject(
                ObjectType.Element,
                "Выбери элемент с линией (деталь/лонжерон/модельная линия)",
            )
        except OperationCanceledException:
            raise _Cancel()

        el = doc.GetElement(ref.ElementId)
        if el is None:
            raise Exception("Элемент не найден")

        crv = getattr(el, "GeometryCurve", None)
        if crv is None:
            loc = getattr(el, "Location", None)
            crv = getattr(loc, "Curve", None) if loc is not None else None

        if crv is None:
            raise Exception("У выбранного элемента нет линейной геометрии")

        p1 = crv.GetEndPoint(0)
        p2 = crv.GetEndPoint(1)
        if p1.DistanceTo(p2) < TOL:
            raise Exception("Выбрана слишком короткая линия")
        return p1, p2

    try:
        p1 = uidoc.Selection.PickPoint("Точка 1 линии усиления")
        p2 = uidoc.Selection.PickPoint("Точка 2 линии усиления")
    except OperationCanceledException:
        raise _Cancel()
    if p1.DistanceTo(p2) < TOL:
        raise Exception("Линия слишком мала")
    return p1, p2


def _dominant_axis(p1, p2):
    dx = abs(p2.X - p1.X)
    dy = abs(p2.Y - p1.Y)
    return "X" if dx >= dy else "Y"


def _cut_equal(start, end, max_len):
    return cut_equal_1d(start, end, max_len, tol=TOL)


def _cut_at_positions(start, end, max_len, positions):
    return cut_at_positions_1d(start, end, max_len, positions, tol=TOL)


def _split_segments(segs, max_len):
    result = []
    for x1, y1, x2, y2 in segs:
        if abs(y1 - y2) < TOL:
            s, e = min(x1, x2), max(x1, x2)
            for a, b in _cut_equal(s, e, max_len):
                result.append((a, y1, b, y2))
        elif abs(x1 - x2) < TOL:
            s, e = min(y1, y2), max(y1, y2)
            for a, b in _cut_equal(s, e, max_len):
                result.append((x1, a, x2, b))
        else:
            result.append((x1, y1, x2, y2))
    return result


def _split_segments_with_positions(segs, max_len, positions):
    result = []
    for x1, y1, x2, y2 in segs:
        if abs(y1 - y2) < TOL:
            s, e = min(x1, x2), max(x1, x2)
            pieces = _cut_at_positions(s, e, max_len, positions)
            for a, b in pieces:
                result.append((a, y1, b, y2))
        elif abs(x1 - x2) < TOL:
            s, e = min(y1, y2), max(y1, y2)
            pieces = _cut_at_positions(s, e, max_len, positions)
            for a, b in pieces:
                result.append((x1, a, x2, b))
        else:
            result.append((x1, y1, x2, y2))
    return result


def _unique_sorted(vals):
    out = []
    for v in sorted(vals):
        if not out or abs(v - out[-1]) > TOL:
            out.append(v)
    return out


def _crossings_for_axis_line(axis, coord, perp_segs):
    vals = []
    for x1, y1, x2, y2 in perp_segs:
        if axis == "X":
            # Ищем пересечение горизонтали y=coord с вертикальными сегментами.
            if abs(x1 - x2) < TOL:
                y_min, y_max = min(y1, y2), max(y1, y2)
                if y_min - TOL <= coord <= y_max + TOL:
                    vals.append(_rc((x1 + x2) / 2.0))
        else:
            # Ищем пересечение вертикали x=coord с горизонтальными сегментами.
            if abs(y1 - y2) < TOL:
                x_min, x_max = min(x1, x2), max(x1, x2)
                if x_min - TOL <= coord <= x_max + TOL:
                    vals.append(_rc((y1 + y2) / 2.0))
    return _unique_sorted(vals)


def _snap_range_to_crossings(a, b, crossings):
    """Привязка диапазона [a,b] к ближайшим crossings.

    Containing-подход: находим crossings, которые *объемлют*
    нарисованный диапазон — snap до ближайшего crossing на каждом
    конце.  Расширение — макс. на 1 пролёт с каждой стороны.
    Никогда не обрезает середину.
    """
    s, e = (a, b) if a <= b else (b, a)
    if not crossings:
        return s, e

    at_or_before = [c for c in crossings if c <= s + TOL]
    at_or_after = [c for c in crossings if c >= e - TOL]

    s2 = at_or_before[-1] if at_or_before else crossings[0]
    e2 = at_or_after[0] if at_or_after else crossings[-1]

    if e2 < s2:
        s2, e2 = e2, s2
    return s2, e2


def _read_max_len_from_floor(floor):
    mm = get_mm_param(floor, "RF_Max_Stringer_Len", 4000.0)
    return mm_to_internal(max(100.0, mm))


def _get_axis_from_segments(segs):
    for x1, y1, x2, y2 in segs:
        if abs(y1 - y2) < TOL and abs(x1 - x2) > TOL:
            return "X"
        if abs(x1 - x2) < TOL and abs(y1 - y2) > TOL:
            return "Y"
    return None


def _read_layer_segments_from_ids(param_name):
    ids = parse_ids_from_string(get_string_param(floor_global, param_name))
    segs = []
    for int_id in ids:
        el = doc.GetElement(ElementId(int_id))
        if el is None:
            continue
        loc = getattr(el, "Location", None)
        if loc is None:
            continue
        crv = getattr(loc, "Curve", None)
        if crv is None:
            continue
        p0 = crv.GetEndPoint(0)
        p1 = crv.GetEndPoint(1)
        segs.append((_rc(p0.X), _rc(p0.Y), _rc(p1.X), _rc(p1.Y)))
    return segs


def _layer_axes(floor):
    upper_axis = None
    lower_axis = None

    upper_saved = get_string_param(floor, "RF_Top_Direction")
    if upper_saved in ("X", "Y"):
        upper_axis = upper_saved
        lower_axis = "Y" if upper_axis == "X" else "X"

    upper_segs = _read_layer_segments_from_ids("RF_Stringers_Top_ID")
    lower_segs = _read_layer_segments_from_ids("RF_Stringers_Bottom_ID")

    up_seg_axis = _get_axis_from_segments(upper_segs)
    lo_seg_axis = _get_axis_from_segments(lower_segs)

    if up_seg_axis:
        upper_axis = up_seg_axis
    if lo_seg_axis:
        lower_axis = lo_seg_axis

    if not upper_axis and lower_axis:
        upper_axis = "Y" if lower_axis == "X" else "X"
    if not lower_axis and upper_axis:
        lower_axis = "Y" if upper_axis == "X" else "X"

    return upper_axis or "X", lower_axis or "Y", upper_segs, lower_segs


def _layer_coords(segs, axis):
    vals = set()
    for x1, y1, x2, y2 in segs:
        if axis == "X" and abs(y1 - y2) < TOL:
            vals.add(_rc((y1 + y2) / 2.0))
        elif axis == "Y" and abs(x1 - x2) < TOL:
            vals.add(_rc((x1 + x2) / 2.0))
    return sorted(vals)


def _nearest_value(values, target):
    if not values:
        return None
    best = values[0]
    best_d = abs(best - target)
    for v in values[1:]:
        d = abs(v - target)
        if d < best_d:
            best_d = d
            best = v
    return best


def _choose_mirror_axis(line_coord, ref_coords):
    """Возвращает (mirror_axis_coord|None, mirror_mode_label).

    Два режима зеркала:
    - "В том же пролёте" → ось = центр пролёта, обе линии внутри одного пролёта.
    - "В соседний пролёт" → ось = ближайший лонжерон, зеркало по ту сторону.
    """
    below = [v for v in ref_coords if v < line_coord - TOL]
    above = [v for v in ref_coords if v > line_coord + TOL]
    near_below = max(below) if below else None
    near_above = min(above) if above else None

    bay_center = None
    if near_below is not None and near_above is not None:
        bay_center = (near_below + near_above) / 2.0

    options = ["Без зеркала"]
    if bay_center is not None:
        options.append("В том же пролёте (симметрия)")
    if near_below is not None or near_above is not None:
        options.append("В соседний пролёт (через ось)")

    mode = forms.CommandSwitchWindow.show(options, message="Режим зеркалирования:")
    if not mode:
        raise _Cancel()

    if mode.startswith("Без"):
        return None, "none"

    if mode.startswith("В том же"):
        return bay_center, "same_bay"

    # "В соседний пролёт" — ось = ближайший существующий лонжерон
    near = _nearest_value(ref_coords, line_coord)
    return near, "adjacent_bay"


def _get_longeron_symbols(layer_mode):
    symbols = _find_symbols(FAMILY_LONGERON)
    if not symbols:
        raise Exception(tr("family_not_found_fmt", family=FAMILY_LONGERON))
    names = sorted(symbols.keys())

    need_upper = layer_mode in ("Оба слоя", "Upper")
    need_lower = layer_mode in ("Оба слоя", "Lower")
    sym_upper = None
    sym_lower = None

    if len(names) == 1:
        if need_upper:
            sym_upper = symbols[names[0]]
        if need_lower:
            sym_lower = symbols[names[0]]
        return sym_upper, sym_lower

    if need_upper:
        n = forms.CommandSwitchWindow.show(names, message="Типоразмер ВЕРХНИХ:")
        if not n:
            raise _Cancel()
        sym_upper = symbols[n]
    if need_lower:
        n = forms.CommandSwitchWindow.show(names, message="Типоразмер НИЖНИХ:")
        if not n:
            raise _Cancel()
        sym_lower = symbols[n]
    return sym_upper, sym_lower


def _get_support_symbol():
    symbols = _find_symbols(FAMILY_SUPPORT)
    if not symbols:
        return None
    names = sorted(symbols.keys())
    if len(names) == 1:
        return symbols[names[0]]
    n = forms.CommandSwitchWindow.show(names, message="Типоразмер СТОЕК:")
    if not n:
        raise _Cancel()
    return symbols[n]


def _calc_z_offsets(floor, level, sym_upper, sym_lower):
    ph_upper = (
        (get_double_param(sym_upper, "RF_Profile_Height") or 0.0) if sym_upper else 0.0
    )
    ph_lower = (
        (get_double_param(sym_lower, "RF_Profile_Height") or 0.0) if sym_lower else 0.0
    )
    total_h = get_double_param(floor, "RF_Floor_Height") or 0.0
    tile_t = get_double_param(floor, "RF_Tile_Thickness") or 0.0
    bbox = get_bbox_xy(floor, view)
    if not bbox or len(bbox) < 6:
        raise Exception("get_bbox_xy: неожиданный формат")
    z0 = bbox[5]
    slab_off = z0 - level.Elevation
    if total_h > 0 and (ph_upper + ph_lower) > 0:
        support_h = total_h - tile_t - ph_upper - ph_lower
        dz_upper = slab_off + support_h + ph_lower
        dz_lower = slab_off + support_h
    else:
        dz_upper = slab_off
        dz_lower = slab_off
    return z0, dz_upper, dz_lower, ph_upper, ph_lower


def _place_longerons(segs, symbol, level, z0, dz, prefix, axis_label, zone_id):
    ids = []
    for i, (x1, y1, x2, y2) in enumerate(segs, 1):
        line = Line.CreateBound(XYZ(x1, y1, z0), XYZ(x2, y2, z0))
        inst = doc.Create.NewFamilyInstance(
            line, symbol, level, StructuralType.NonStructural
        )
        if dz:
            ElementTransformUtils.MoveElement(doc, inst.Id, XYZ(0, 0, dz))

        l_mm = int(round(internal_to_mm(line.Length)))
        _set_param(inst, "RF_Stringer_Type", "Upper" if prefix == "УВ" else "Lower")
        _set_param(inst, "RF_Direction_Axis", axis_label)
        _set_param(inst, "RF_Mark", "{}.{}.{}.{}мм".format(prefix, zone_id, i, l_mm))
        ids.append(str(_eid_int(inst.Id)))
    return ids


def _generate_support_nodes(lower_segs, max_spacing, support_half):
    return build_support_nodes(
        lower_segs,
        max_spacing,
        support_half=support_half,
        tol=TOL,
    )


def _place_supports(nodes, symbol, level, z0, support_h, lower_axis, zone_id):
    if not nodes or symbol is None:
        return []
    ids = []
    angle = math.pi / 2.0 if lower_axis == "Y" else 0.0
    for i, (sx, sy) in enumerate(nodes, 1):
        inst = doc.Create.NewFamilyInstance(
            XYZ(sx, sy, z0), symbol, level, StructuralType.NonStructural
        )
        if abs(angle) > 1e-9:
            axis = Line.CreateBound(XYZ(sx, sy, z0), XYZ(sx, sy, z0 + 1.0))
            ElementTransformUtils.RotateElement(doc, inst.Id, axis, angle)
        if support_h > 0:
            _set_param(inst, "RF_Support_Height", support_h)
        _set_param(inst, "RF_Mark", "УС.{}.{}".format(zone_id, i))
        ids.append(str(_eid_int(inst.Id)))
    return ids


def _line_mode_build(floor, upper_axis, lower_axis, upper_segs, lower_segs):
    p1, p2 = _pick_line()
    axis = _dominant_axis(p1, p2)

    layer = None
    if axis == lower_axis:
        layer = "Lower"
    elif axis == upper_axis:
        layer = "Upper"
    else:
        layer = forms.CommandSwitchWindow.show(
            ["Upper", "Lower"], message="Слой линии:"
        )
        if not layer:
            raise _Cancel()

    if axis == "X":
        p_start, p_end = min(p1.X, p2.X), max(p1.X, p2.X)
        line_coord = (p1.Y + p2.Y) / 2.0
    else:
        p_start, p_end = min(p1.Y, p2.Y), max(p1.Y, p2.Y)
        line_coord = (p1.X + p2.X) / 2.0

    ref_coords = _layer_coords(lower_segs if layer == "Lower" else upper_segs, axis)
    if not ref_coords:
        raise Exception("Нет существующих осей выбранного слоя для зеркалирования")

    mirror_axis, mirror_mode = _choose_mirror_axis(line_coord, ref_coords)
    mirror_coord = None
    if mirror_axis is not None:
        mirror_coord = 2.0 * mirror_axis - line_coord

    perp_segs = upper_segs if layer == "Lower" else lower_segs
    crossings_base = _crossings_for_axis_line(axis, line_coord, perp_segs)
    crossings_mirror = (
        _crossings_for_axis_line(axis, mirror_coord, perp_segs)
        if mirror_coord is not None
        else []
    )

    if not crossings_base:
        forms.alert(
            "Нет перпендикулярных опор в зоне выбранной линии.\n"
            "Лонжерон будет размещён от точки до точки без привязки к стыкам.",
            title=TITLE,
        )

    s_base, e_base = _snap_range_to_crossings(p_start, p_end, crossings_base)
    if mirror_coord is not None:
        if not crossings_mirror:
            s_mir, e_mir = s_base, e_base
        else:
            # Snap зеркала от уже приснапленной базы → одинаковая длина
            s_mir, e_mir = _snap_range_to_crossings(s_base, e_base, crossings_mirror)
            if e_mir - s_mir <= TOL:
                s_mir, e_mir = s_base, e_base
    else:
        s_mir, e_mir = None, None

    if e_base - s_base <= TOL:
        raise Exception("Нет валидного пролёта между опорами по выбранной линии")
    if mirror_coord is not None and (e_mir - s_mir <= TOL):
        raise Exception("Нет валидного пролёта для зеркальной линии")

    segs = []
    if axis == "X":
        base_seg = (s_base, _rc(line_coord), e_base, _rc(line_coord))
        segs.append(base_seg)
        if mirror_coord is not None:
            mir_seg = (s_mir, _rc(mirror_coord), e_mir, _rc(mirror_coord))
            segs.append(mir_seg)
    else:
        base_seg = (_rc(line_coord), s_base, _rc(line_coord), e_base)
        segs.append(base_seg)
        if mirror_coord is not None:
            mir_seg = (_rc(mirror_coord), s_mir, _rc(mirror_coord), e_mir)
            segs.append(mir_seg)

    mode_name = "Линия"
    all_cross = _unique_sorted(crossings_base + crossings_mirror)
    return (
        mode_name,
        layer,
        axis,
        segs,
        all_cross,
        {
            "source_coord": internal_to_mm(line_coord),
            "mirror_mode": mirror_mode,
            "mirror_axis": (
                internal_to_mm(mirror_axis) if mirror_axis is not None else None
            ),
            "mirror_coord": (
                internal_to_mm(mirror_coord) if mirror_coord is not None else None
            ),
            "crossings_count": len(all_cross),
        },
    )


def _get_base_symbols(floor):
    """Находит типоразмеры уже размещённых базовых лонжеронов и стоек."""
    sym_upper = sym_lower = support_sym = None

    for param_name, attr in [
        ("RF_Stringers_Top_ID", "upper"),
        ("RF_Stringers_Bottom_ID", "lower"),
    ]:
        ids = parse_ids_from_string(get_string_param(floor, param_name))
        for int_id in ids:
            el = doc.GetElement(ElementId(int_id))
            if el is None:
                continue
            sym = getattr(el, "Symbol", None)
            if sym is None:
                continue
            if attr == "upper" and sym_upper is None:
                sym_upper = sym
            elif attr == "lower" and sym_lower is None:
                sym_lower = sym
            if sym_upper and sym_lower:
                break
        if sym_upper and sym_lower:
            break

    # Стойка — первый типоразмер семейства RF_Support
    support_syms = _find_symbols(FAMILY_SUPPORT)
    if support_syms:
        support_sym = list(support_syms.values())[0]

    return sym_upper, sym_lower, support_sym


def _rect_mode_build(floor, upper_axis, lower_axis, upper_base_segs, lower_base_segs):
    """Прямоугольная зона усиления: учащение шага в выбранной области.

    Работает просто:
    1. Обводишь рамку на виде.
    2. Указываешь шаг усиления (мм) — один для обоих слоёв.
    3. Скрипт добавляет ТОЛЬКО недостающие лонжероны между существующими.
    """
    rect = _pick_rect()
    x_min, y_min, x_max, y_max = rect

    # Текущий базовый шаг для подсказки
    base_step_mm = max(100.0, float(get_mm_param(floor, "RF_Bottom_Step", 1200.0)))
    default_reinforced = max(100.0, base_step_mm / 2.0)

    layer_choice = forms.CommandSwitchWindow.show(
        ["Оба слоя", "Только верхний", "Только нижний"],
        message="Какие слои усилить:",
    )
    if not layer_choice:
        raise _Cancel()

    s = forms.ask_for_string(
        prompt="Шаг усиления (мм):",
        default=str(int(round(default_reinforced))),
        title=TITLE,
    )
    if not s:
        raise _Cancel()
    step_mm = max(100.0, float(s.strip()))
    step = mm_to_internal(step_mm)

    do_upper = layer_choice in ("Оба слоя", "Только верхний")
    do_lower = layer_choice in ("Оба слоя", "Только нижний")

    # --- Координаты существующих базовых лонжеронов внутри зоны ---
    def _base_coords_in_rect(segs, axis, rng_min, rng_max):
        coords = set()
        for x1, y1, x2, y2 in segs:
            if axis == "X" and abs(y1 - y2) < TOL:
                c = _rc((y1 + y2) / 2.0)
                if rng_min - TOL <= c <= rng_max + TOL:
                    coords.add(c)
            elif axis == "Y" and abs(x1 - x2) < TOL:
                c = _rc((x1 + x2) / 2.0)
                if rng_min - TOL <= c <= rng_max + TOL:
                    coords.add(c)
        return sorted(coords)

    # --- Генерация новых позиций (между существующими, без дубликатов) ---
    def _gen_aligned(ref, stp, rng_min, rng_max, existing):
        pos = ref
        while pos > rng_min + TOL:
            pos -= stp
        if pos < rng_min - TOL:
            pos += stp
        result = []
        while pos <= rng_max + TOL:
            if not any(abs(pos - ex) < TOL for ex in existing):
                result.append(_rc(pos))
            pos += stp
        return result

    upper_segs = []
    lower_segs = []
    new_upper_coords = []
    new_lower_coords = []
    existing_upper = []
    existing_lower = []

    if do_upper:
        if upper_axis == "X":
            existing_upper = _base_coords_in_rect(upper_base_segs, "X", y_min, y_max)
            u_min, u_max = y_min, y_max
        else:
            existing_upper = _base_coords_in_rect(upper_base_segs, "Y", x_min, x_max)
            u_min, u_max = x_min, x_max
        ref = existing_upper[0] if existing_upper else u_min
        new_upper_coords = _gen_aligned(ref, step, u_min, u_max, existing_upper)
        if upper_axis == "X":
            for y in new_upper_coords:
                upper_segs.append((x_min, y, x_max, y))
        else:
            for x in new_upper_coords:
                upper_segs.append((x, y_min, x, y_max))

    if do_lower:
        if lower_axis == "X":
            existing_lower = _base_coords_in_rect(lower_base_segs, "X", y_min, y_max)
            l_min, l_max = y_min, y_max
        else:
            existing_lower = _base_coords_in_rect(lower_base_segs, "Y", x_min, x_max)
            l_min, l_max = x_min, x_max
        ref = existing_lower[0] if existing_lower else l_min
        new_lower_coords = _gen_aligned(ref, step, l_min, l_max, existing_lower)
        if lower_axis == "X":
            for y in new_lower_coords:
                lower_segs.append((x_min, y, x_max, y))
        else:
            for x in new_lower_coords:
                lower_segs.append((x, y_min, x, y_max))

    # Позиции нарезки верхних — все нижние (база + новые)
    def _perp_coords(segs, axis):
        coords = set()
        for x1, y1, x2, y2 in segs:
            if axis == "X" and abs(y1 - y2) < TOL:
                coords.add(_rc((y1 + y2) / 2.0))
            elif axis == "Y" and abs(x1 - x2) < TOL:
                coords.add(_rc((x1 + x2) / 2.0))
        return coords

    all_lower_coords = _perp_coords(lower_base_segs, lower_axis)
    all_lower_coords.update(new_lower_coords)
    cut_positions_upper = sorted(all_lower_coords)

    meta = {
        "rect_mm": [
            internal_to_mm(x_min),
            internal_to_mm(y_min),
            internal_to_mm(x_max),
            internal_to_mm(y_max),
        ],
        "step_mm": step_mm,
        "layers": layer_choice,
        "new_upper": len(new_upper_coords),
        "new_lower": len(new_lower_coords),
        "skipped_upper": len(existing_upper),
        "skipped_lower": len(existing_lower),
    }
    return (
        "Прямоугольник",
        layer_choice,
        upper_segs,
        lower_segs,
        cut_positions_upper,
        meta,
    )


def main():
    global doc, uidoc, view

    doc = get_doc()
    uidoc = get_uidoc()
    view = get_active_view()

    if not doc or not uidoc:
        raise Exception(tr("source_floor_not_found"))

    floor = _pick_floor()

    with revit.Transaction("Нормализовать параметры усиления"):
        normalize_legacy_mm_param(floor, "RF_Bottom_Step")
        normalize_legacy_mm_param(floor, "RF_Max_Stringer_Len")

    if floor.LookupParameter(PARAM_ZONES) is None:
        forms.alert(
            tr("reinf_param_not_found", param=PARAM_ZONES),
            title=TITLE,
        )
        raise _Cancel()

    global floor_global
    floor_global = floor

    upper_axis, lower_axis, upper_base_segs, lower_base_segs = _layer_axes(floor)

    mode = forms.CommandSwitchWindow.show(
        ["Линия", "Прямоугольник"], message="Режим усиления:"
    )
    if not mode:
        raise _Cancel()

    sym_upper = None
    sym_lower = None
    support_symbol = None
    upper_new = []
    lower_new = []
    meta = {}
    layer_mode = "Оба слоя"

    if mode == "Линия":
        _, layer, axis, segs, cut_positions, meta = _line_mode_build(
            floor, upper_axis, lower_axis, upper_base_segs, lower_base_segs
        )
        layer_mode = layer
        max_len = _read_max_len_from_floor(floor)
        if layer == "Upper":
            sym_upper, _ = _get_longeron_symbols("Upper")
            upper_new = segs
            upper_new = _split_segments_with_positions(
                upper_new, max_len, cut_positions
            )
        else:
            _, sym_lower = _get_longeron_symbols("Lower")
            support_symbol = _get_support_symbol()
            lower_new = segs
            lower_new = _split_segments_with_positions(
                lower_new, max_len, cut_positions
            )
        mode_name = "Линия"
    else:
        mode_name, layer_choice, upper_new, lower_new, cut_pos_upper, meta = (
            _rect_mode_build(
                floor, upper_axis, lower_axis, upper_base_segs, lower_base_segs
            )
        )
        layer_mode = layer_choice

        # Типоразмеры = те же что базовые лонжероны
        sym_upper, sym_lower, support_symbol = _get_base_symbols(floor)
        if not sym_upper and not sym_lower:
            # Fallback: ручной выбор
            sym_upper, sym_lower = _get_longeron_symbols("Оба слоя")
            support_symbol = _get_support_symbol()
        elif not sym_upper and upper_new:
            sym_upper = sym_lower
        elif not sym_lower and lower_new:
            sym_lower = sym_upper

        max_len = _read_max_len_from_floor(floor)
        upper_new = _split_segments_with_positions(upper_new, max_len, cut_pos_upper)
        lower_new = _split_segments(lower_new, max_len)

    lid = floor.LevelId
    level = (
        doc.GetElement(lid)
        if lid and lid != ElementId.InvalidElementId
        else view.GenLevel
    )
    z0, dz_upper, dz_lower, ph_up, ph_low = _calc_z_offsets(
        floor, level, sym_upper, sym_lower
    )

    total_h = get_double_param(floor, "RF_Floor_Height") or 0.0
    tile_t = get_double_param(floor, "RF_Tile_Thickness") or 0.0
    support_h = total_h - tile_t - ph_up - ph_low if total_h > 0 else 0.0

    support_ids = []
    support_nodes = []
    if lower_new and support_symbol is not None:
        max_sp = mm_to_internal(DEFAULT_SUPPORT_SPACING_MM)
        base_size = get_double_param(support_symbol, "RF_Base_Size") or 0.0
        support_nodes = _generate_support_nodes(lower_new, max_sp, base_size / 2.0)

    zone_id = datetime.now().strftime("ZU%Y%m%d%H%M%S")
    msg = [
        "Зона: {}".format(zone_id),
        "Режим: {}".format(mode_name),
        "Ось верхних: {}, ось нижних: {}".format(upper_axis, lower_axis),
        "Добавить верхних: {}".format(len(upper_new)),
        "Добавить нижних: {}".format(len(lower_new)),
        "Добавить стоек: {}".format(len(support_nodes)),
    ]
    if mode_name == "Линия":
        msg.append("Mirror mode: {}".format(meta.get("mirror_mode")))
        if meta.get("mirror_axis") is not None:
            msg.append("Mirror axis: {:.0f} мм".format(meta.get("mirror_axis")))
        if meta.get("mirror_coord") is not None:
            msg.append("Mirror line: {:.0f} мм".format(meta.get("mirror_coord")))
    elif mode_name == "Прямоугольник":
        sk_u = meta.get("skipped_upper", 0)
        sk_l = meta.get("skipped_lower", 0)
        if sk_u or sk_l:
            msg.append("Пропущено дубликатов: верх={}, низ={}".format(sk_u, sk_l))
    # --- Превью: пунктирные линии на виде ---
    preview_ids = []
    with revit.Transaction("Превью усиления"):
        preview_ids = _draw_preview(upper_new, lower_new, z0)
    uidoc.RefreshActiveView()

    msg.extend(["", tr("continue")])
    confirmed = forms.alert("\n".join(msg), title=TITLE, yes=True, no=True)

    # Удаляем превью в любом случае
    if preview_ids:
        with revit.Transaction("Удалить превью"):
            _delete_preview(preview_ids)

    if not confirmed:
        raise _Cancel()

    with revit.Transaction("Добавить зону усиления"):
        if sym_upper is not None and not sym_upper.IsActive:
            sym_upper.Activate()
        if sym_lower is not None and not sym_lower.IsActive:
            sym_lower.Activate()
        if support_symbol is not None and not support_symbol.IsActive:
            support_symbol.Activate()
        doc.Regenerate()

        upper_ids = []
        lower_ids = []

        if upper_new and sym_upper is not None:
            upper_ids = _place_longerons(
                upper_new, sym_upper, level, z0, dz_upper, "УВ", upper_axis, zone_id
            )

        if lower_new and sym_lower is not None:
            lower_ids = _place_longerons(
                lower_new, sym_lower, level, z0, dz_lower, "УН", lower_axis, zone_id
            )

        if support_nodes and support_symbol is not None:
            support_ids = _place_supports(
                support_nodes,
                support_symbol,
                level,
                z0,
                support_h,
                lower_axis,
                zone_id,
            )

        zones_data = load_reinforcement_zones(floor, default_version=2)
        zones_data["zones"].append(
            {
                "zone_id": zone_id,
                "mode": mode_name,
                "layers": layer_mode,
                "upper_axis": upper_axis,
                "lower_axis": lower_axis,
                "meta": meta,
                "upper_ids": upper_ids,
                "lower_ids": lower_ids,
                "support_ids": support_ids,
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        save_reinforcement_zones(floor, zones_data)

    forms.alert(
        "Усиление создано.\nЗона: {}\nВерх: {}\nНиз: {}\nСтойки: {}".format(
            zone_id,
            len(upper_ids),
            len(lower_ids),
            len(support_ids),
        ),
        title=TITLE,
    )


try:
    main()
except _Cancel:
    pass
except Exception as ex:
    forms.alert(tr("error_inline_fmt", error=str(ex)), title=TITLE)

# -*- coding: utf-8 -*-
"""06 Лонжероны — размещение верхних и нижних.

Логика:
  1. Верхние — строго по линиям сетки плитки (основное направление).
  2. Нижние — перпендикулярно, с регулярным шагом (независимо от сетки).
  3. Контурная обвязка — по смещённому контуру (внешний, колонны, проёмы).
  4. Монтажный зазор 5 мм от всех границ.
  5. Верхние подрезаются в местах пересечения с нижними.
  6. Максимальная длина — нарезка с привязкой стыков к нижним.
"""

import math

from Autodesk.Revit.DB import (  # type: ignore
    XYZ,
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
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import (  # type: ignore
    FloorOrPartSelectionFilter,
    cut_at_positions_1d,
    cut_equal_1d,
    get_double_param,
    get_mm_param,
    get_source_floor,
    get_string_param,
    normalize_legacy_mm_param,
    parse_ids_from_string,
    set_mm_param,
    set_string_param,
)
from floor_exact import (  # type: ignore
    get_exact_zone_for_floor,
    internal_to_mm,
    mm_to_internal,
    offset_zone_contours,
    path64_to_points_mm,
)
from floor_grid import get_bbox_xy  # type: ignore
from floor_i18n import tr  # type: ignore
from pyrevit import forms, revit  # type: ignore

# ─── Константы ────────────────────────────────────────────

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView

TITLE = tr("title_longerons")
FAMILY_NAME = "ФП_Лонжерон"
TOL = 1e-6
_MIN_PIECE = 0.005  # ~1.5 мм
MOUNTING_GAP_MM = 5.0  # монтажный зазор от границ

REQUIRED_FLOOR_PARAMS = [
    "FP_ID_Лонжеронов_Верх",
    "FP_ID_Лонжеронов_Низ",
    "FP_Режим_Нижних",
    "FP_Шаг_Нижних",
    "FP_Макс_Длина_Лонжерона",
    "FP_Направление_Верхних",
]


class _Cancel(Exception):
    pass


# ─── Утилиты ─────────────────────────────────────────────


def _rc(v):
    return round(v, 6)


def _seg_key(seg):
    p1 = (_rc(seg[0]), _rc(seg[1]))
    p2 = (_rc(seg[2]), _rc(seg[3]))
    return (p1, p2) if p1 <= p2 else (p2, p1)


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


def _get_tile_thickness_fallback():
    """Возвращает толщину плитки (ft) из семейства ФП_Плитка как fallback."""
    thickness = 0.0
    for fam in FilteredElementCollector(doc).OfClass(Family):
        if fam.Name == "ФП_Плитка":
            for sid in fam.GetFamilySymbolIds():
                sym = doc.GetElement(sid)
                if sym:
                    t = get_double_param(sym, "FP_Толщина") or 0.0
                    if t > thickness:
                        thickness = t
            break
    return thickness


def _extend_ends(segs, ext):
    """Удлиняет каждый H/V-сегмент на ext с каждого конца (нахлёст в углах)."""
    if ext < TOL:
        return list(segs)
    result = []
    for x1, y1, x2, y2 in segs:
        if abs(y1 - y2) < TOL:  # горизонтальный
            mn, mx = min(x1, x2), max(x1, x2)
            result.append((mn - ext, y1, mx + ext, y2))
        elif abs(x1 - x2) < TOL:  # вертикальный
            mn, mx = min(y1, y2), max(y1, y2)
            result.append((x1, mn - ext, x2, mx + ext))
        else:
            result.append((x1, y1, x2, y2))
    return result


def _dedup(segs):
    seen = set()
    out = []
    for seg in segs:
        k = _seg_key(seg)
        if k not in seen:
            seen.add(k)
            out.append(seg)
    return out


# ─── Чтение сетки ────────────────────────────────────────


def _read_grid_lines(floor_el):
    """→ v_lines {x: [(y_min,y_max)]}, h_lines {y: [(x_min,x_max)]}."""
    ids = parse_ids_from_string(get_string_param(floor_el, "FP_ID_ЛинийСетки"))
    v_lines, h_lines = {}, {}
    for int_id in ids:
        el = doc.GetElement(ElementId(int_id))
        if el is None:
            continue
        crv = getattr(el, "GeometryCurve", None)
        if crv is None:
            continue
        p0, p1 = crv.GetEndPoint(0), crv.GetEndPoint(1)
        dx, dy = abs(p1.X - p0.X), abs(p1.Y - p0.Y)
        if dx < TOL and dy > TOL:
            v_lines.setdefault(_rc(p0.X), []).append((min(p0.Y, p1.Y), max(p0.Y, p1.Y)))
        elif dy < TOL and dx > TOL:
            h_lines.setdefault(_rc(p0.Y), []).append((min(p0.X, p1.X), max(p0.X, p1.X)))
    return v_lines, h_lines


# ─── Нарезка ─────────────────────────────────────────────


def _cut_at_positions(start, end, max_len, positions):
    """Режет [start,end] ≤ max_len, стыки в positions (greedy)."""
    return cut_at_positions_1d(start, end, max_len, positions, tol=TOL)


def _cut_equal(start, end, max_len):
    """Равномерная нарезка ≤ max_len."""
    return cut_equal_1d(start, end, max_len, tol=TOL)


def _cut_seg(seg, max_len, positions=None):
    """Нарезка одного H/V-сегмента. → список сегментов."""
    x1, y1, x2, y2 = seg
    if abs(y1 - y2) < TOL:  # горизонтальный
        s, e = min(x1, x2), max(x1, x2)
        pieces = (
            _cut_at_positions(s, e, max_len, positions)
            if positions
            else _cut_equal(s, e, max_len)
        )
        return [(a, y1, b, y2) for a, b in pieces]
    if abs(x1 - x2) < TOL:  # вертикальный
        s, e = min(y1, y2), max(y1, y2)
        pieces = (
            _cut_at_positions(s, e, max_len, positions)
            if positions
            else _cut_equal(s, e, max_len)
        )
        return [(x1, a, x2, b) for a, b in pieces]
    return [seg]


# ─── Рёбра из контуров ───────────────────────────────────


def _edges_from_paths64(paths64):
    """H/V рёбра из Clipper2 Paths64 → internal units.
    → h_edges [(x_min,x_max,y)], v_edges [(y_min,y_max,x)], skipped.
    """
    tol_mm = 0.5
    h, v, skipped = [], [], 0
    for path in paths64:
        pts = path64_to_points_mm(path)
        n = len(pts)
        for i in range(n):
            x0, y0 = pts[i]
            x1, y1 = pts[(i + 1) % n]
            dx, dy = abs(x1 - x0), abs(y1 - y0)
            if dx < tol_mm and dy > tol_mm:
                x_int = mm_to_internal((x0 + x1) / 2.0)
                v.append(
                    (
                        mm_to_internal(min(y0, y1)),
                        mm_to_internal(max(y0, y1)),
                        _rc(x_int),
                    )
                )
            elif dy < tol_mm and dx > tol_mm:
                y_int = mm_to_internal((y0 + y1) / 2.0)
                h.append(
                    (
                        mm_to_internal(min(x0, x1)),
                        mm_to_internal(max(x0, x1)),
                        _rc(y_int),
                    )
                )
            else:
                skipped += 1
    return h, v, skipped


def _edges_from_loops(loops):
    """H/V рёбра из XYZ-петель.
    → h_edges [(x_min,x_max,y)], v_edges [(y_min,y_max,x)], skipped.
    """
    h, v, skipped = [], [], 0
    for pts in loops:
        n = len(pts)
        for i in range(n):
            p0, p1 = pts[i], pts[(i + 1) % n]
            dx, dy = abs(p1.X - p0.X), abs(p1.Y - p0.Y)
            if dx < TOL and dy > TOL:
                v.append((min(p0.Y, p1.Y), max(p0.Y, p1.Y), _rc(p0.X)))
            elif dy < TOL and dx > TOL:
                h.append((min(p0.X, p1.X), max(p0.X, p1.X), _rc(p0.Y)))
            else:
                skipped += 1
    return h, v, skipped


# ─── Клиппинг (even-odd) ─────────────────────────────────


def _clip_to_boundary(segs, clip_h, clip_v):
    """Обрезает сегменты по контуру (even-odd ray-casting)."""
    if not clip_h and not clip_v:
        return list(segs)

    _C = 0.001

    def _inside(px, py):
        cnt = 0
        for xs, xe, yc in clip_h:
            if min(xs, xe) - _C <= px <= max(xs, xe) + _C and yc > py + _C:
                cnt += 1
        return cnt % 2 == 1

    def _clip_1d(s_min, s_max, crossings):
        if len(crossings) < 2:
            return None
        cs = sorted(crossings)
        dd = [cs[0]]
        for c in cs[1:]:
            if c - dd[-1] > _C:
                dd.append(c)
        spans = []
        for i in range(0, len(dd) - 1, 2):
            a, b = max(s_min, dd[i]), min(s_max, dd[i + 1])
            if b - a > TOL:
                spans.append((a, b))
        return spans or None

    result = []
    for x1, y1, x2, y2 in segs:
        if abs(y1 - y2) < TOL:  # горизонтальный → clip по V
            y = (y1 + y2) / 2.0
            s_min, s_max = min(x1, x2), max(x1, x2)
            cx = [xc for ys, ye, xc in clip_v if ys - _C <= y <= ye + _C]
            spans = _clip_1d(s_min, s_max, cx)
            if spans:
                for a, b in spans:
                    result.append((a, y1, b, y2))
            elif _inside((s_min + s_max) / 2.0, y):
                result.append((x1, y1, x2, y2))
        elif abs(x1 - x2) < TOL:  # вертикальный → clip по H
            x = (x1 + x2) / 2.0
            s_min, s_max = min(y1, y2), max(y1, y2)
            cx = [yc for xs, xe, yc in clip_h if xs - _C <= x <= xe + _C]
            spans = _clip_1d(s_min, s_max, cx)
            if spans:
                for a, b in spans:
                    result.append((x1, a, x2, b))
            elif _inside(x, (s_min + s_max) / 2.0):
                result.append((x1, y1, x2, y2))
        else:
            result.append((x1, y1, x2, y2))
    return result


# ─── Фильтр коротких ─────────────────────────────────────


def _filter_short(segs, min_len):
    kept, dropped = [], 0
    for x1, y1, x2, y2 in segs:
        if math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2) < min_len:
            dropped += 1
        else:
            kept.append((x1, y1, x2, y2))
    return kept, dropped


# ─── Revit: UI ────────────────────────────────────────────


def _find_symbols(family_name):
    for fam in FilteredElementCollector(doc).OfClass(Family):
        if fam.Name == family_name:
            result = {}
            for sid in fam.GetFamilySymbolIds():
                sym = doc.GetElement(sid)
                if sym:
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
    el = doc.GetElement(ref.ElementId)
    floor = get_source_floor(el)
    if not floor:
        raise Exception(tr("source_floor_not_found"))
    return floor


def _ask_config(floor):
    """→ (dir_x, sym_upper, sym_lower, max_len, lower_step)."""
    v, h = _read_grid_lines(floor)
    if not v and not h:
        forms.alert(tr("long_no_grid"), title=TITLE)
        raise _Cancel()

    sym_dict = _find_symbols(FAMILY_NAME)
    if not sym_dict:
        forms.alert(tr("family_not_found_fmt", family=FAMILY_NAME), title=TITLE)
        raise _Cancel()

    direction = forms.CommandSwitchWindow.show(
        [tr("long_dir_x"), tr("long_dir_y")],
        message=tr("long_dir_message"),
    )
    if not direction:
        raise _Cancel()
    dir_x = direction.startswith("X")

    if dir_x and not h:
        forms.alert(tr("long_no_h_grid"), title=TITLE)
        raise _Cancel()
    if not dir_x and not v:
        forms.alert(tr("long_no_v_grid"), title=TITLE)
        raise _Cancel()

    names = sorted(sym_dict.keys())
    if len(names) == 1:
        sym_upper = sym_lower = list(sym_dict.values())[0]
    else:
        n = forms.CommandSwitchWindow.show(names, message=tr("long_upper_type"))
        if not n:
            raise _Cancel()
        sym_upper = sym_dict[n]
        n = forms.CommandSwitchWindow.show(names, message=tr("long_lower_type"))
        if not n:
            raise _Cancel()
        sym_lower = sym_dict[n]

    max_len_default = int(round(get_mm_param(floor, "FP_Макс_Длина_Лонжерона", 4000.0)))
    s = forms.ask_for_string(
        prompt=tr("prompt_max_length"),
        default=str(max_len_default),
        title=TITLE,
    )
    if not s:
        raise _Cancel()
    try:
        max_len = mm_to_internal(float(s.strip()))
    except ValueError:
        forms.alert(tr("invalid_number"), title=TITLE)
        raise _Cancel()

    lower_step_default = int(round(get_mm_param(floor, "FP_Шаг_Нижних", 1200.0)))
    s = forms.ask_for_string(
        prompt=tr("prompt_lower_step"),
        default=str(lower_step_default),
        title=TITLE,
    )
    if not s:
        raise _Cancel()
    try:
        lower_step = mm_to_internal(float(s.strip()))
    except ValueError:
        forms.alert(tr("invalid_number"), title=TITLE)
        raise _Cancel()
    if lower_step <= TOL:
        forms.alert(tr("step_positive"), title=TITLE)
        raise _Cancel()

    return dir_x, sym_upper, sym_lower, max_len, lower_step


# ─── Revit: размещение ───────────────────────────────────


def _place_layer(segs, symbol, level, z0, dz, prefix, dir_label, max_len):
    ids = []
    max_mm = int(round(internal_to_mm(max_len)))
    for i, (x1, y1, x2, y2) in enumerate(segs, 1):
        line = Line.CreateBound(XYZ(x1, y1, z0), XYZ(x2, y2, z0))
        inst = doc.Create.NewFamilyInstance(
            line, symbol, level, StructuralType.NonStructural
        )
        if dz:
            ElementTransformUtils.MoveElement(doc, inst.Id, XYZ(0, 0, dz))
        l_mm = int(round(internal_to_mm(line.Length)))
        mark = "{}.{}.{}мм".format(prefix, i, l_mm)
        if l_mm > max_mm:
            mark += " [!ДЛИНА]"
        _set_param(inst, "FP_Тип_Лонжерона", "Верхний" if prefix == "ВЛ" else "Нижний")
        _set_param(inst, "FP_Ось_Направления", dir_label)
        _set_param(inst, "FP_Марка", mark)
        ids.append(str(_eid_int(inst.Id)))
    return ids


# ─── Главная функция ─────────────────────────────────────


def main():
    floor = _pick_floor()

    with revit.Transaction(tr("tx_normalize_longeron_sizes")):
        normalize_legacy_mm_param(floor, "FP_Шаг_Нижних")
        normalize_legacy_mm_param(floor, "FP_Макс_Длина_Лонжерона")

    missing = [n for n in REQUIRED_FLOOR_PARAMS if floor.LookupParameter(n) is None]
    if missing:
        forms.alert(tr("missing_params", params="\n".join(missing)), title=TITLE)
        raise _Cancel()

    tile_ids = parse_ids_from_string(get_string_param(floor, "FP_ID_Плиток"))
    if not tile_ids:
        proceed = forms.alert(
            tr("long_tiles_missing"),
            title=TITLE,
            yes=True,
            no=True,
        )
        if not proceed:
            raise _Cancel()

    dir_x, sym_upper, sym_lower, max_len, lower_step = _ask_config(floor)

    # ── Сетка ──
    v_lines, h_lines = _read_grid_lines(floor)
    v_keys, h_keys = sorted(v_lines.keys()), sorted(h_lines.keys())

    if dir_x:
        main_keys, main_lines = h_keys, h_lines
        perp_keys = v_keys
    else:
        main_keys, main_lines = v_keys, v_lines
        perp_keys = h_keys

    # ── Профили ──
    pw_upper = get_double_param(sym_upper, "FP_Ширина_Профиля") or 0.0
    pw_lower = get_double_param(sym_lower, "FP_Ширина_Профиля") or 0.0
    pw = max(pw_upper, pw_lower)
    pw_upper_mm = internal_to_mm(pw_upper)
    pw_lower_mm = internal_to_mm(pw_lower)
    ph_upper = get_double_param(sym_upper, "FP_Высота_Профиля") or 0.0
    ph_lower = get_double_param(sym_lower, "FP_Высота_Профиля") or 0.0

    # ── Стойка: полуразмер (max из опоры и оголовка) ──
    support_half_mm = 0.0
    for fam in FilteredElementCollector(doc).OfClass(Family):
        if fam.Name == "ФП_Стойка":
            for sid in fam.GetFamilySymbolIds():
                sym = doc.GetElement(sid)
                if sym:
                    head = get_double_param(sym, "FP_Размер_Оголовка") or 0.0
                    base = get_double_param(sym, "FP_Размер_Опоры") or 0.0
                    half = internal_to_mm(max(head, base)) / 2.0
                    if half > support_half_mm:
                        support_half_mm = half
            break

    # ── Bbox, Z, уровень ──
    bbox = get_bbox_xy(floor, view)
    if not bbox or len(bbox) < 6:
        raise Exception("get_bbox_xy: неожиданный формат")
    z0 = bbox[5]

    lid = floor.LevelId
    level = (
        doc.GetElement(lid)
        if lid and lid != ElementId.InvalidElementId
        else view.GenLevel
    )

    total_h = get_double_param(floor, "FP_Высота_Фальшпола") or 0.0
    tile_t = get_double_param(floor, "FP_Толщина_Плитки") or 0.0
    if tile_t <= TOL:
        tile_t = _get_tile_thickness_fallback()

    if total_h <= TOL:
        forms.alert(
            tr("floor_height_zero"),
            title=TITLE,
        )
        raise _Cancel()

    if tile_t <= TOL:
        forms.alert(
            tr("tile_thickness_missing"),
            title=TITLE,
        )
        raise _Cancel()

    slab_off = z0 - level.Elevation
    if (ph_upper + ph_lower) > 0:
        support_h = total_h - tile_t - ph_upper - ph_lower
        if support_h < -TOL:
            forms.alert(
                tr("height_conflict_full"),
                title=TITLE,
            )
            raise _Cancel()
        support_h = max(0.0, support_h)
        dz_upper = slab_off + support_h + ph_lower
        dz_lower = slab_off + support_h
    else:
        dz_upper = slab_off
        dz_lower = slab_off

    # ── Позиции нижних (регулярный шаг от первой perp-линии) ──
    if dir_x:
        perp_min, perp_max = bbox[0], bbox[2]
    else:
        perp_min, perp_max = bbox[1], bbox[3]

    origin = perp_keys[0] if perp_keys else perp_min
    lower_positions = []
    p = origin
    while p >= perp_min - TOL:
        lower_positions.append(p)
        p -= lower_step
    p = origin + lower_step
    while p <= perp_max + TOL:
        lower_positions.append(p)
        p += lower_step
    lower_positions.append(_rc(perp_min))
    lower_positions.append(_rc(perp_max))
    lower_positions = sorted(set(_rc(lp) for lp in lower_positions))

    # ── Контур (Clipper2 offset) ──
    contour_error = None
    contour_skipped = 0
    clip_h, clip_v = [], []

    try:
        zone = get_exact_zone_for_floor(doc, floor)
    except Exception as ex:
        forms.alert(tr("contour_not_received", error=str(ex)), title=TITLE)
        raise _Cancel()

    # Граница клиппинга = контур − 5 мм
    try:
        clip_outer, clip_holes = offset_zone_contours(zone, MOUNTING_GAP_MM)
        ch1, cv1, sk1 = _edges_from_paths64(clip_outer)
        ch2, cv2, sk2 = _edges_from_paths64(clip_holes)
        clip_h, clip_v = ch1 + ch2, cv1 + cv2
        contour_skipped += sk1 + sk2
    except Exception as ex:
        contour_error = "clip offset: " + str(ex)
        all_loops = zone["outer_loops"] + zone["inner_loops"]
        clip_h, clip_v, _ = _edges_from_loops(all_loops)

    # Центровые линии обвязки (расстояние от стены до центра лонжерона):
    #   верхние = 5 мм + pw_upper/2
    #   нижние  = max(пол-оголовка, pw_lower/2) + 5 мм
    frame_mm_upper = MOUNTING_GAP_MM + pw_upper_mm / 2.0
    frame_mm_lower = max(support_half_mm, pw_lower_mm / 2.0) + MOUNTING_GAP_MM

    frame_h_upper, frame_v_upper = [], []
    frame_h_lower, frame_v_lower = [], []
    if pw > TOL:
        # Полигон для верхних контурных
        try:
            fu_outer, fu_holes = offset_zone_contours(zone, frame_mm_upper)
            fhu1, fvu1, sku1 = _edges_from_paths64(fu_outer)
            fhu2, fvu2, sku2 = _edges_from_paths64(fu_holes)
            frame_h_upper = fhu1 + fhu2
            frame_v_upper = fvu1 + fvu2
            contour_skipped += sku1 + sku2
        except Exception as ex:
            if not contour_error:
                contour_error = "frame upper offset: " + str(ex)
        # Полигон для нижних контурных
        try:
            fl_outer, fl_holes = offset_zone_contours(zone, frame_mm_lower)
            fhl1, fvl1, skl1 = _edges_from_paths64(fl_outer)
            fhl2, fvl2, skl2 = _edges_from_paths64(fl_holes)
            frame_h_lower = fhl1 + fhl2
            frame_v_lower = fvl1 + fvl2
            contour_skipped += skl1 + skl2
        except Exception as ex:
            if not contour_error:
                contour_error = "frame lower offset: " + str(ex)

    # ── 1. Верхние по сетке (main direction) ──
    upper_segs = []
    for pos in main_keys:
        for s, e in main_lines.get(pos, []):
            if dir_x:
                upper_segs.append((s, pos, e, pos))
            else:
                upper_segs.append((pos, s, pos, e))

    # ── 2. Нижние (perp direction, полный пролёт) ──
    if dir_x:
        span_min, span_max = bbox[1], bbox[3]
    else:
        span_min, span_max = bbox[0], bbox[2]

    lower_segs = []
    for pos in lower_positions:
        if dir_x:
            lower_segs.append((pos, span_min, pos, span_max))
        else:
            lower_segs.append((span_min, pos, span_max, pos))

    # ── 3. Контурная обвязка ──
    #   Верхние контурные берём из frame_upper-полигона,
    #   нижние — из frame_lower (учитывает пол-оголовка стойки).
    contour_upper, contour_lower = [], []
    if dir_x:
        for x_s, x_e, y in frame_h_upper:
            contour_upper.append((x_s, y, x_e, y))
        for y_s, y_e, x in frame_v_lower:
            contour_lower.append((x, y_s, x, y_e))
    else:
        for x_s, x_e, y in frame_h_lower:
            contour_lower.append((x_s, y, x_e, y))
        for y_s, y_e, x in frame_v_upper:
            contour_upper.append((x, y_s, x, y_e))

    # ── 3a. Нахлёст контурных в углах (опирание + монтажный запас) ──
    contour_lower = _extend_ends(contour_lower, pw_upper)
    contour_upper = _extend_ends(contour_upper, pw_lower)

    # ── 4. Клиппинг к границе −5 мм ──
    upper_segs = _clip_to_boundary(upper_segs, clip_h, clip_v)
    lower_segs = _clip_to_boundary(lower_segs, clip_h, clip_v)
    contour_upper = _clip_to_boundary(contour_upper, clip_h, clip_v)
    contour_lower = _clip_to_boundary(contour_lower, clip_h, clip_v)

    # ── 5. Нарезка по макс. длине ──
    #   Верхние → стыки на нижних позициях (для опоры)
    #   Нижние / контур → равномерно
    upper_segs = [
        p for seg in upper_segs for p in _cut_seg(seg, max_len, lower_positions)
    ]
    lower_segs = [p for seg in lower_segs for p in _cut_seg(seg, max_len)]
    contour_upper = [
        p for seg in contour_upper for p in _cut_seg(seg, max_len, lower_positions)
    ]
    contour_lower = [p for seg in contour_lower for p in _cut_seg(seg, max_len)]

    # ── 6. Объединение + дедупликация ──
    upper_segs = _dedup(upper_segs + contour_upper)
    lower_segs = _dedup(lower_segs + contour_lower)

    # ── 7. Фильтр коротких ──
    min_seg = max(pw * 0.5, mm_to_internal(30))
    upper_segs, short_u = _filter_short(upper_segs, min_seg)
    lower_segs, short_l = _filter_short(lower_segs, min_seg)

    if not upper_segs and not lower_segs:
        forms.alert(tr("no_longerons_to_place"), title=TITLE)
        raise _Cancel()

    # ── Подтверждение ──
    old_upper = parse_ids_from_string(get_string_param(floor, "FP_ID_Лонжеронов_Верх"))
    old_lower = parse_ids_from_string(get_string_param(floor, "FP_ID_Лонжеронов_Низ"))
    old_ids = list(set(old_upper + old_lower))

    msg = [
        tr("long_upper_count", count=len(upper_segs)),
        tr("long_lower_count", count=len(lower_segs), positions=len(lower_positions)),
        tr("long_lower_step", step=internal_to_mm(lower_step)),
        tr("long_max_length", length=internal_to_mm(max_len)),
        tr("long_gap", gap=MOUNTING_GAP_MM),
        "",
        tr("long_z0", z=internal_to_mm(z0)),
        tr("long_dz", upper=internal_to_mm(dz_upper), lower=internal_to_mm(dz_lower)),
    ]
    if total_h == 0:
        msg.append("!!! FP_Высота_Фальшпола = 0")
    if contour_error:
        msg.append("!!! " + contour_error)
    if contour_skipped:
        msg.append("!!! Наклонных рёбер: {}".format(contour_skipped))
    if short_u or short_l:
        msg.append(tr("long_short_count", upper=short_u, lower=short_l))
    msg.extend(["", tr("deleted_old", count=len(old_ids)), "", tr("continue")])

    if not forms.alert("\n".join(msg), title=TITLE, yes=True, no=True):
        raise _Cancel()

    # ── Размещение ──
    with revit.Transaction(tr("tx_place_longerons")):
        if not sym_upper.IsActive:
            sym_upper.Activate()
        if not sym_lower.IsActive:
            sym_lower.Activate()
        doc.Regenerate()

        deleted = 0
        for int_id in old_ids:
            try:
                el = doc.GetElement(ElementId(int_id))
                if el:
                    doc.Delete(ElementId(int_id))
                    deleted += 1
            except Exception:
                pass

        upper_ids = _place_layer(
            upper_segs,
            sym_upper,
            level,
            z0,
            dz_upper,
            "ВЛ",
            "X" if dir_x else "Y",
            max_len,
        )
        lower_ids = _place_layer(
            lower_segs,
            sym_lower,
            level,
            z0,
            dz_lower,
            "НЛ",
            "Y" if dir_x else "X",
            max_len,
        )

        set_string_param(floor, "FP_ID_Лонжеронов_Верх", ";".join(upper_ids))
        set_string_param(floor, "FP_ID_Лонжеронов_Низ", ";".join(lower_ids))
        _set_param(floor, "FP_Режим_Нижних", "Регулярные")
        set_mm_param(floor, "FP_Шаг_Нижних", internal_to_mm(lower_step))
        set_mm_param(floor, "FP_Макс_Длина_Лонжерона", internal_to_mm(max_len))
        _set_param(floor, "FP_Направление_Верхних", "X" if dir_x else "Y")

    forms.alert(
        tr("long_done", upper=len(upper_ids), lower=len(lower_ids), deleted=deleted),
        title=TITLE,
    )


try:
    main()
except _Cancel:
    pass
except Exception as ex:
    forms.alert(tr("error_inline_fmt", error=str(ex)), title=TITLE)

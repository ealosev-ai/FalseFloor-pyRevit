# -*- coding: utf-8 -*-
"""07 Стойки — расстановка по размещённым нижним лонжеронам.

Логика:
  1. На каждом конце нижнего лонжерона — обязательная стойка.
  2. Промежуточные стойки равномерно с макс.шагом (по умолчанию 600 мм).
  3. Минимум 2 стойки на каждый лонжерон (концы).
  4. Совпадающие узлы (перекрёстки) дедуплицируются.
Сохраняет ID стоек в FP_ID_Стоек.
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
    build_support_nodes,
    get_double_param,
    get_source_floor,
    get_string_param,
    parse_ids_from_string,
    set_string_param,
)
from floor_exact import (  # type: ignore
    internal_to_mm,
    mm_to_internal,
)
from floor_grid import get_bbox_xy  # type: ignore
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView

TITLE = "07 Стойки"
FAMILY_SUPPORT = "ФП_Стойка"
_CANCELLED = "@@CANCELLED@@"
COORD_TOL = 1e-6
DEFAULT_MAX_SPACING_MM = 1000.0  # макс. шаг между стойками вдоль лонжерона


def _rc(v):
    return round(v, 6)


def _get_family_symbols(family_name):
    collector = FilteredElementCollector(doc).OfClass(Family)
    for fam in collector:
        if fam.Name == family_name:
            result = []
            for sid in fam.GetFamilySymbolIds():
                sym = doc.GetElement(sid)
                if sym:
                    result.append(sym)
            return result
    return []


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


def _read_grid_lines(floor_el):
    """Читает DetailCurves сетки → v_keys, h_keys (отсортированные координаты)."""
    ids = parse_ids_from_string(get_string_param(floor_el, "FP_ID_ЛинийСетки"))
    v_set = set()
    h_set = set()
    for int_id in ids:
        el = doc.GetElement(ElementId(int_id))
        if el is None:
            continue
        geom = getattr(el, "GeometryCurve", None)
        if geom is None:
            continue
        p0 = geom.GetEndPoint(0)
        p1 = geom.GetEndPoint(1)
        dx = abs(p1.X - p0.X)
        dy = abs(p1.Y - p0.Y)
        if dx < COORD_TOL and dy > COORD_TOL:
            v_set.add(_rc(p0.X))
        elif dy < COORD_TOL and dx > COORD_TOL:
            h_set.add(_rc(p0.Y))
    return sorted(v_set), sorted(h_set)


def _read_lower_segments(floor_el):
    """Читает нижние лонжероны → список (x1, y1, x2, y2)."""
    ids = parse_ids_from_string(get_string_param(floor_el, "FP_ID_Лонжеронов_Низ"))
    segs = []
    for int_id in ids:
        el = doc.GetElement(ElementId(int_id))
        if el is None:
            continue
        loc = el.Location
        if loc is None:
            continue
        curve = loc.Curve
        p0 = curve.GetEndPoint(0)
        p1 = curve.GetEndPoint(1)
        segs.append((_rc(p0.X), _rc(p0.Y), _rc(p1.X), _rc(p1.Y)))
    return segs


def _get_lower_axis_and_angle(lower_segs):
    """Возвращает ось нижних лонжеронов и угол поворота стойки.

    Нижние в проекте идут одним набором параллельных сегментов,
    поэтому достаточно первого валидного сегмента:
      - по X  -> угол 0
      - по Y  -> угол pi/2
    """
    for x1, y1, x2, y2 in lower_segs:
        dx = abs(x2 - x1)
        dy = abs(y2 - y1)
        if dx < COORD_TOL and dy < COORD_TOL:
            continue
        if dx >= dy:
            return "X", 0.0
        return "Y", math.pi / 2.0
    return "X", 0.0


def _generate_support_nodes(lower_segs, max_spacing, support_half=0.0):
    """Генерация узлов стоек вдоль нижних лонжеронов (shared logic)."""
    return build_support_nodes(
        lower_segs,
        max_spacing,
        support_half=support_half,
        tol=COORD_TOL,
    )


try:
    if not isinstance(view, ViewPlan):
        forms.alert("Открой план.", title=TITLE)
        raise Exception(_CANCELLED)

    pick_filter = FloorOrPartSelectionFilter()
    try:
        ref = uidoc.Selection.PickObject(
            ObjectType.Element,
            pick_filter,
            "Выберите перекрытие фальшпола",
        )
    except OperationCanceledException:
        raise Exception(_CANCELLED)

    picked_el = doc.GetElement(ref.ElementId)
    floor = get_source_floor(picked_el)
    if not floor:
        raise Exception("Не удалось определить исходное перекрытие")

    # Семейство стоек
    support_symbols = _get_family_symbols(FAMILY_SUPPORT)
    if not support_symbols:
        forms.alert(
            "Семейство '{}' не найдено.\nЗагрузи его.".format(FAMILY_SUPPORT),
            title=TITLE,
        )
        raise Exception(_CANCELLED)

    if len(support_symbols) == 1:
        sym_support = support_symbols[0]
    else:
        sup_dict = {}
        for s in support_symbols:
            try:
                name = s.Name
            except Exception:
                name = str(s.Id.Value)
            sup_dict[name] = s
        chosen_sup = forms.CommandSwitchWindow.show(
            sorted(sup_dict.keys()),
            message="Типоразмер стойки:",
        )
        if not chosen_sup:
            raise Exception(_CANCELLED)
        sym_support = sup_dict[chosen_sup]

    # Спросить макс. шаг стоек
    s_spacing = forms.ask_for_string(
        prompt="Макс. шаг стоек вдоль лонжерона (мм):",
        default=str(int(DEFAULT_MAX_SPACING_MM)),
        title=TITLE,
    )
    if not s_spacing:
        raise Exception(_CANCELLED)
    try:
        max_spacing = mm_to_internal(float(s_spacing.strip()))
    except ValueError:
        forms.alert("Некорректное число.", title=TITLE)
        raise Exception(_CANCELLED)

    # Чтение данных
    lower_segs = _read_lower_segments(floor)
    if not lower_segs:
        forms.alert(
            "Нижние лонжероны не найдены.\nСначала запусти 3 Лонжероны.",
            title=TITLE,
        )
        raise Exception(_CANCELLED)
    lower_axis, support_angle = _get_lower_axis_and_angle(lower_segs)

    v_keys, h_keys = _read_grid_lines(floor)

    # --- Система высот ---
    profile_h_upper = 0.0
    profile_h_lower = 0.0

    upper_ids_str = get_string_param(floor, "FP_ID_Лонжеронов_Верх")
    upper_longeron_ids = parse_ids_from_string(upper_ids_str)
    if upper_longeron_ids:
        first_el = doc.GetElement(ElementId(upper_longeron_ids[0]))
        if first_el:
            t = doc.GetElement(first_el.GetTypeId())
            if t:
                profile_h_upper = get_double_param(t, "FP_Высота_Профиля") or 0.0

    lower_longeron_ids = parse_ids_from_string(
        get_string_param(floor, "FP_ID_Лонжеронов_Низ")
    )
    if lower_longeron_ids:
        first_el = doc.GetElement(ElementId(lower_longeron_ids[0]))
        if first_el:
            t = doc.GetElement(first_el.GetTypeId())
            if t:
                profile_h_lower = get_double_param(t, "FP_Высота_Профиля") or 0.0

    total_h = get_double_param(floor, "FP_Высота_Фальшпола") or 0.0
    tile_t = get_double_param(floor, "FP_Толщина_Плитки") or 0.0

    if total_h > 0 and (profile_h_upper + profile_h_lower) > 0:
        support_h = total_h - tile_t - profile_h_upper - profile_h_lower
    else:
        support_h = 0.0

    _h_diag = (
        "  FP_Высота_Фальшпола = {:.0f} мм\n"
        "  FP_Толщина_Плитки = {:.0f} мм\n"
        "  Профиль верх = {:.0f} мм\n"
        "  Профиль низ = {:.0f} мм\n"
        "  → Высота стойки = {:.0f} мм"
    ).format(
        internal_to_mm(total_h),
        internal_to_mm(tile_t),
        internal_to_mm(profile_h_upper),
        internal_to_mm(profile_h_lower),
        internal_to_mm(support_h),
    )

    # Генерация узлов стоек
    base_size = get_double_param(sym_support, "FP_Размер_Опоры") or 0.0
    support_half = base_size / 2.0
    support_nodes = _generate_support_nodes(lower_segs, max_spacing, support_half)

    # Индексы колонка/ряд для стоек
    def _nearest_idx(keys, val):
        best_i, best_d = 0, float("inf")
        for i, k in enumerate(keys):
            d = abs(k - val)
            if d < best_d:
                best_d = d
                best_i = i
        return best_i

    # Level
    level_id = floor.LevelId
    if level_id and level_id != ElementId.InvalidElementId:
        level = doc.GetElement(level_id)
    else:
        level = view.GenLevel

    # Z стойки = верх перекрытия (стойка стоит на плите)
    bbox_data = get_bbox_xy(floor, view)
    z0_abs = bbox_data[5] if bbox_data else 0.0
    level_elevation = level.Elevation if hasattr(level, "Elevation") else 0.0
    z0 = z0_abs - level_elevation

    # Подтверждение
    old_ids = parse_ids_from_string(get_string_param(floor, "FP_ID_Стоек"))

    msg = [
        "Стоек: {}".format(len(support_nodes)),
        "Нижних лонжеронов: {}".format(len(lower_segs)),
        "Ось нижних: {}".format(lower_axis),
        "Макс. шаг: {:.0f} мм".format(internal_to_mm(max_spacing)),
    ]
    if base_size > 0:
        msg.append("Опора: {:.0f} мм".format(internal_to_mm(base_size)))
    if support_h > 0:
        msg.append("Высота стойки: {:.0f} мм".format(internal_to_mm(support_h)))
    else:
        msg.append("!!! Высота стойки = 0 (не рассчитана)")
    msg.append("")
    msg.append(_h_diag)
    msg.extend(
        [
            "",
            "Удалить старых стоек: {}".format(len(old_ids)),
            "",
            "Продолжить?",
        ]
    )
    confirm = forms.alert(
        "\n".join(msg),
        title=TITLE,
        yes=True,
        no=True,
    )
    if not confirm:
        raise Exception(_CANCELLED)

    # Размещение
    with revit.Transaction("Разместить стойки"):
        if not sym_support.IsActive:
            sym_support.Activate()
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

        placed_ids = []
        s_count = 0
        for sx, sy in support_nodes:
            inst = doc.Create.NewFamilyInstance(
                XYZ(sx, sy, z0),
                sym_support,
                level,
                StructuralType.NonStructural,
            )
            if abs(support_angle) > 1e-9:
                axis = Line.CreateBound(XYZ(sx, sy, z0), XYZ(sx, sy, z0 + 1.0))
                ElementTransformUtils.RotateElement(doc, inst.Id, axis, support_angle)
            s_count += 1
            col = _nearest_idx(v_keys, sx)
            row = _nearest_idx(h_keys, sy)
            _set_param(inst, "FP_Колонка", col)
            _set_param(inst, "FP_Ряд", row)
            _set_param(inst, "FP_Марка", "СТ.{}".format(s_count))
            if support_h > 0:
                _set_param(inst, "FP_Высота_Стойки", support_h)
            placed_ids.append(str(inst.Id.Value))

        set_string_param(floor, "FP_ID_Стоек", ";".join(placed_ids))

    report = "Готово.\n\nСтоек: {}\nУдалено старых: {}".format(s_count, deleted)
    report += "\nОсь нижних: {}".format(lower_axis)
    if support_h > 0:
        report += "\nВысота стойки: {:.0f} мм".format(internal_to_mm(support_h))
    forms.alert(report, title=TITLE)

except Exception as ex:
    if str(ex) == _CANCELLED:
        pass
    else:
        forms.alert("Ошибка: {}".format(str(ex)), title=TITLE)

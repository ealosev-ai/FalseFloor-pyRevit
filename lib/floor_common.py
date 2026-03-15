# -*- coding: utf-8 -*-

import json
import math

from Autodesk.Revit.DB import (  # type: ignore
    BuiltInCategory,
    Color,
    ElementId,
    FilteredElementCollector,
    GraphicsStyleType,
    LinePatternElement,
    Part,
    StorageType,
)
from Autodesk.Revit.UI.Selection import ISelectionFilter  # type: ignore
from floor_i18n import tr  # type: ignore
from pyrevit import revit  # type: ignore

doc = revit.doc

REINFORCEMENT_ZONES_PARAM = "FP_ЗоныУсиления_JSON"

_LEGACY_MM_LENGTH_PARAM_LIMITS = {
    "FP_Шаг_Нижних": 10000.0,
    "FP_Макс_Длина_Лонжерона": 20000.0,
}


def build_positions(
    min_val,
    max_val,
    base_val,
    step_val,
    end_padding_steps=0.0,
    end_tolerance=0.0,
):
    import math

    positions = []
    if step_val <= 0:
        return positions

    n_start = int(math.floor((min_val - base_val) / step_val))
    current = base_val + n_start * step_val

    # Keep current near min_val to avoid extra far-left values caused by float noise.
    while current < min_val - step_val:
        current += step_val

    max_with_tail = max_val + step_val * float(end_padding_steps) + float(end_tolerance)
    while current <= max_with_tail:
        positions.append(current)
        current += step_val

    return positions


def get_id_value(obj):
    try:
        return obj.Id.IntegerValue
    except Exception:
        try:
            return obj.Id.Value
        except Exception:
            try:
                return obj.IntegerValue
            except Exception:
                return obj.Value


class FloorOrPartSelectionFilter(ISelectionFilter):
    def AllowElement(self, element):
        if not element:
            return False

        try:
            if element.Category and get_id_value(element.Category.Id) == int(
                BuiltInCategory.OST_Floors
            ):
                return True
        except Exception:
            pass

        if isinstance(element, Part):
            return True

        return False

    def AllowReference(self, reference, position):
        return True


def get_source_floor(el, visited_ids=None):
    if not el:
        return None

    if visited_ids is None:
        visited_ids = set()

    try:
        el_id_val = get_id_value(el)
        if el_id_val in visited_ids:
            return None
        visited_ids.add(el_id_val)
    except Exception:
        pass

    try:
        if el.Category and get_id_value(el.Category.Id) == int(
            BuiltInCategory.OST_Floors
        ):
            return el
    except Exception:
        pass

    if isinstance(el, Part):
        try:
            source_ids = el.GetSourceElementIds()
            for sid in source_ids:
                host_id = sid.HostElementId
                host_el = doc.GetElement(host_id)
                if not host_el:
                    continue

                try:
                    if host_el.Category and get_id_value(host_el.Category.Id) == int(
                        BuiltInCategory.OST_Floors
                    ):
                        return host_el
                except Exception:
                    pass

                if isinstance(host_el, Part):
                    result = get_source_floor(host_el, visited_ids)
                    if result:
                        return result
        except Exception:
            return None

    return None


def read_floor_grid_params(floor):
    params = {
        "FP_Шаг_X": get_double_param(floor, "FP_Шаг_X"),
        "FP_Шаг_Y": get_double_param(floor, "FP_Шаг_Y"),
        "FP_База_X": get_double_param(floor, "FP_База_X"),
        "FP_База_Y": get_double_param(floor, "FP_База_Y"),
    }

    missing = [name for name, val in params.items() if val is None]
    if missing:
        raise Exception(
            tr("params_read_error", missing="\n- ".join(missing))
        )

    return {
        "step_x": params["FP_Шаг_X"],
        "step_y": params["FP_Шаг_Y"],
        "base_x_raw": params["FP_База_X"],
        "base_y_raw": params["FP_База_Y"],
    }


def get_double_param(el, name):
    p = el.LookupParameter(name)
    if not p:
        return None
    try:
        if p.StorageType != StorageType.Double:
            return None
    except Exception:
        return None
    try:
        return p.AsDouble()
    except Exception:
        return None


def set_double_param(el, name, value):
    p = el.LookupParameter(name)
    if not p:
        return False
    try:
        if p.StorageType != StorageType.Double:
            return False
        if p.IsReadOnly:
            return False
    except Exception:
        return False
    try:
        p.Set(value)
        return True
    except Exception:
        return False


def get_string_param(el, name):
    p = el.LookupParameter(name)
    if not p:
        return None
    try:
        if p.StorageType != StorageType.String:
            return None
    except Exception:
        return None
    try:
        return p.AsString()
    except Exception:
        return None


def set_string_param(el, name, value):
    p = el.LookupParameter(name)
    if not p:
        return False
    if p.IsReadOnly:
        return False
    if p.StorageType != StorageType.String:
        return False
    p.Set(value)
    return True


def get_mm_param(el, name, default_mm=None):
    """Читает параметр как мм.

    Поддерживает:
    - String: хранится число в мм
    - Double Length: Revit internal (ft), конвертируется в мм
    - Double Number: трактуется как мм без конвертации
    - Integer: трактуется как мм
    """
    p = el.LookupParameter(name)
    if not p:
        return default_mm

    try:
        st = p.StorageType
    except Exception:
        return default_mm

    try:
        if st == StorageType.String:
            s = p.AsString()
            if not s:
                return default_mm
            return float(str(s).replace(",", ".").strip())

        if st == StorageType.Double:
            value = float(p.AsDouble())
            if _is_length_param(p):
                if _looks_like_legacy_mm_in_length(name, value):
                    return value
                return value * 304.8
            return value

        if st == StorageType.Integer:
            return float(p.AsInteger())
    except Exception:
        return default_mm

    return default_mm


def set_mm_param(el, name, mm_value):
    """Записывает параметр из мм.

    String  -> текст в мм (целое)
    Double Length -> internal feet
    Double Number -> мм как число
    Integer -> мм как int
    """
    p = el.LookupParameter(name)
    if not p:
        return False
    if p.IsReadOnly:
        return False

    try:
        mm = float(mm_value)
    except Exception:
        return False

    try:
        st = p.StorageType
    except Exception:
        return False

    try:
        if st == StorageType.String:
            p.Set(str(int(round(mm))))
            return True

        if st == StorageType.Double:
            if _is_length_param(p):
                p.Set(mm / 304.8)
            else:
                p.Set(mm)
            return True

        if st == StorageType.Integer:
            p.Set(int(round(mm)))
            return True
    except Exception:
        return False

    return False


def normalize_legacy_mm_param(el, name):
    p = el.LookupParameter(name)
    if not p:
        return False

    try:
        if p.IsReadOnly or p.StorageType != StorageType.Double:
            return False
    except Exception:
        return False

    if not _is_length_param(p):
        return False

    try:
        raw_value = float(p.AsDouble())
    except Exception:
        return False

    if not _looks_like_legacy_mm_in_length(name, raw_value):
        return False

    try:
        p.Set(raw_value / 304.8)
        return True
    except Exception:
        return False


def _is_length_param(param):
    try:
        defn = param.Definition
    except Exception:
        return False

    try:
        from Autodesk.Revit.DB import SpecTypeId  # type: ignore

        return defn.GetDataType() == SpecTypeId.Length
    except Exception:
        pass

    try:
        from Autodesk.Revit.DB import ParameterType as PT  # type: ignore

        return defn.ParameterType == PT.Length
    except Exception:
        return False


def _looks_like_legacy_mm_in_length(name, raw_value):
    """Detect mm written directly into a Length parameter (should be feet).

    Proper feet for these params are small (e.g. 3.9 ft for 1200mm).
    Legacy raw values are the mm number itself (e.g. 1200).
    The gap between max valid feet and min legacy mm is huge,
    so a simple range check is reliable.
    """
    limit_mm = _LEGACY_MM_LENGTH_PARAM_LIMITS.get(name)
    if not limit_mm:
        return False

    try:
        value = float(raw_value)
    except Exception:
        return False

    if value <= 0:
        return False

    max_valid_ft = limit_mm / 304.8
    return value > max_valid_ft and value <= limit_mm


def parse_ids_from_string(ids_string):
    result = []
    if not ids_string:
        return result

    for part in ids_string.split(";"):
        part = part.strip()
        if not part:
            continue
        try:
            result.append(int(part))
        except Exception:
            pass
    return result


def delete_elements_by_ids(ids_list):
    """Удаляет элементы по списку int id. Возвращает количество удалённых."""
    deleted = 0
    for int_id in ids_list:
        try:
            el_id = ElementId(int_id)
            el = doc.GetElement(el_id)
            if el:
                doc.Delete(el_id)
                deleted += 1
        except Exception:
            pass
    return deleted


def get_or_create_line_style(
    doc,
    style_name,
    color=None,
    weight=1,
    line_pattern_name=None,
    update_existing=False,
):
    """Возвращает GraphicsStyle для подкатегории style_name под OST_Lines.

    Создаёт подкатегорию если не существует (требует открытой транзакции).
    color — Autodesk.Revit.DB.Color, по умолчанию серый (140,140,140).
    line_pattern_name — имя LinePattern (например 'Center', 'Dash'), None = сплошная.
    update_existing — если True, обновляет цвет/толщину/паттерн существующего стиля.
    """
    if color is None:
        color = Color(140, 140, 140)

    lines_cat = doc.Settings.Categories.get_Item(BuiltInCategory.OST_Lines)

    for sub in lines_cat.SubCategories:
        if sub.Name == style_name:
            if update_existing:
                sub.LineColor = color
                sub.SetLineWeight(weight, GraphicsStyleType.Projection)
                if line_pattern_name:
                    pattern = _find_line_pattern(doc, line_pattern_name)
                    if pattern:
                        sub.SetLinePatternId(pattern.Id, GraphicsStyleType.Projection)
            return sub.GetGraphicsStyle(GraphicsStyleType.Projection)

    new_subcat = doc.Settings.Categories.NewSubcategory(lines_cat, style_name)
    new_subcat.LineColor = color
    new_subcat.SetLineWeight(weight, GraphicsStyleType.Projection)

    if line_pattern_name:
        pattern = _find_line_pattern(doc, line_pattern_name)
        if pattern:
            new_subcat.SetLinePatternId(pattern.Id, GraphicsStyleType.Projection)

    return new_subcat.GetGraphicsStyle(GraphicsStyleType.Projection)


def line_style_exists(doc, style_name):
    """Проверяет, существует ли подкатегория линии с таким именем."""
    lines_cat = doc.Settings.Categories.get_Item(BuiltInCategory.OST_Lines)
    for sub in lines_cat.SubCategories:
        if sub.Name == style_name:
            return True
    return False


def _find_line_pattern(doc, name):
    """Ищет LinePatternElement по имени (case-insensitive)."""
    collector = FilteredElementCollector(doc).OfClass(LinePatternElement)
    name_lower = name.lower()
    for lpe in collector:
        if lpe.Name.lower() == name_lower:
            return lpe
    return None


def get_line_style_id(doc, style_name):
    """Возвращает Id стиля линии по имени или None."""
    lines_cat = doc.Settings.Categories.get_Item(BuiltInCategory.OST_Lines)
    for sub in lines_cat.SubCategories:
        if sub.Name == style_name:
            gs = sub.GetGraphicsStyle(GraphicsStyleType.Projection)
            if gs:
                return gs.Id
    return None


def load_reinforcement_zones(floor, default_version=1):
    """Читает JSON зон усиления из параметра перекрытия."""
    raw = get_string_param(floor, REINFORCEMENT_ZONES_PARAM)
    if not raw:
        return {"version": int(default_version), "zones": []}

    try:
        data = json.loads(raw)
    except Exception:
        return {"version": int(default_version), "zones": []}

    if isinstance(data, list):
        return {"version": int(default_version), "zones": data}

    if isinstance(data, dict):
        zones = data.get("zones")
        if isinstance(zones, list):
            return {
                "version": int(data.get("version", default_version)),
                "zones": zones,
            }

    return {"version": int(default_version), "zones": []}


def save_reinforcement_zones(floor, data):
    """Сохраняет JSON зон усиления в параметр перекрытия."""
    raw = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return set_string_param(floor, REINFORCEMENT_ZONES_PARAM, raw)


def read_reinforcement_zone_ids(floor):
    """Собирает все element ids из зон усиления (верх/низ/стойки)."""
    data = load_reinforcement_zones(floor)
    zones = data.get("zones") or []

    ids = []
    for zone in zones:
        if not isinstance(zone, dict):
            continue
        for key in ("upper_ids", "lower_ids", "support_ids"):
            values = zone.get(key) or []
            for v in values:
                try:
                    ids.append(int(v))
                except Exception:
                    pass
    return ids


def cut_equal_1d(start, end, max_len, tol=1e-6):
    """Равномерная нарезка отрезка [start, end] на части <= max_len."""
    total = end - start
    if total <= max_len + tol:
        return [(start, end)]

    n = int(math.ceil(total / max_len))
    step = total / n
    segs = []
    for i in range(n):
        a = start + step * i
        b = start + step * (i + 1) if i < n - 1 else end
        segs.append((a, b))
    return segs


def cut_at_positions_1d(start, end, max_len, positions, tol=1e-6):
    """Нарезка [start, end] <= max_len с приоритетом стыков в positions."""
    if end - start <= max_len + tol:
        return [(start, end)]

    cands = sorted(p for p in positions if start + tol < p < end - tol)
    if not cands:
        return cut_equal_1d(start, end, max_len, tol=tol)

    segs = []
    cur = start
    while end - cur > max_len + tol:
        best = None
        for p in cands:
            if p <= cur + tol:
                continue
            if p - cur > max_len + tol:
                break
            best = p
        if best is None:
            segs.extend(cut_equal_1d(cur, end, max_len, tol=tol))
            return segs
        segs.append((cur, best))
        cur = best

    segs.append((cur, end))
    return segs


def split_orthogonal_segments(segs, max_len, tol=1e-6, positions=None):
    """Нарезка H/V сегментов на части <= max_len.

    Если передан positions, стыки пытаются попадать в эти позиции.
    Для горизонтальных сегментов positions интерпретируется как X-позиции,
    для вертикальных - как Y-позиции.
    """
    result = []
    positions = positions or []

    for x1, y1, x2, y2 in segs:
        if abs(y1 - y2) < tol:
            s, e = min(x1, x2), max(x1, x2)
            pieces = (
                cut_at_positions_1d(s, e, max_len, positions, tol=tol)
                if positions
                else cut_equal_1d(s, e, max_len, tol=tol)
            )
            for a, b in pieces:
                result.append((a, y1, b, y2))
        elif abs(x1 - x2) < tol:
            s, e = min(y1, y2), max(y1, y2)
            pieces = (
                cut_at_positions_1d(s, e, max_len, positions, tol=tol)
                if positions
                else cut_equal_1d(s, e, max_len, tol=tol)
            )
            for a, b in pieces:
                result.append((x1, a, x2, b))
        else:
            result.append((x1, y1, x2, y2))

    return result


def build_support_nodes(lower_segs, max_spacing, support_half=0.0, tol=1e-6):
    """Узлы стоек вдоль нижних лонжеронов с дедупликацией."""

    def _rc(v):
        return round(v, 6)

    endpoint_count = {}
    for x1, y1, x2, y2 in lower_segs:
        p_start = (_rc(x1), _rc(y1))
        p_end = (_rc(x2), _rc(y2))
        endpoint_count[p_start] = endpoint_count.get(p_start, 0) + 1
        endpoint_count[p_end] = endpoint_count.get(p_end, 0) + 1

    support_set = set()
    for x1, y1, x2, y2 in lower_segs:
        length = math.sqrt((x2 - x1) ** 2 + (y2 - y1) ** 2)
        if length < tol:
            continue

        dx = (x2 - x1) / length
        dy = (y2 - y1) / length
        p_start = (_rc(x1), _rc(y1))
        p_end = (_rc(x2), _rc(y2))

        if endpoint_count.get(p_start, 1) > 1 or support_half < tol:
            support_set.add(p_start)
        else:
            support_set.add((_rc(x1 + dx * support_half), _rc(y1 + dy * support_half)))

        if endpoint_count.get(p_end, 1) > 1 or support_half < tol:
            support_set.add(p_end)
        else:
            support_set.add((_rc(x2 - dx * support_half), _rc(y2 - dy * support_half)))

        if length > max_spacing + tol:
            n_spans = int(math.ceil(length / max_spacing))
            for i in range(1, n_spans):
                t = float(i) / n_spans
                px = x1 + t * (x2 - x1)
                py = y1 + t * (y2 - y1)
                support_set.add((_rc(px), _rc(py)))

    return sorted(support_set)

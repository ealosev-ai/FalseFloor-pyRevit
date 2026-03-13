# -*- coding: utf-8 -*-

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
from pyrevit import revit  # type: ignore

doc = revit.doc


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
            "Не удалось прочитать параметры:\n- {}".format("\n- ".join(missing))
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

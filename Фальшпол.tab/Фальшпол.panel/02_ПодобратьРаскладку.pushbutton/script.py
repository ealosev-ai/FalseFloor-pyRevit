# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import Family, FilteredElementCollector, ViewPlan  # type: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import (  # type: ignore
    FloorOrPartSelectionFilter,
    get_double_param,
    get_source_floor,
    set_double_param,
)
from floor_exact import (  # type: ignore
    evaluate_floor_shift,
    format_area_m2,
    internal_to_mm,
)
from floor_grid import redraw_grid_for_floor  # type: ignore
from floor_ui import (  # type: ignore
    TITLE_SHIFT,
    get_shift_quality_status,
)
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView

_CANCELLED = "@@CANCELLED@@"


try:
    if not isinstance(view, ViewPlan):
        forms.alert(
            "Открой план. Применение смещения выполняется на плане.",
            title=TITLE_SHIFT,
        )
        raise Exception("Active view is not a plan")

    pick_filter = FloorOrPartSelectionFilter()
    try:
        ref = uidoc.Selection.PickObject(
            ObjectType.Element,
            pick_filter,
            "Выберите перекрытие фальшпола или его часть",
        )
    except OperationCanceledException:
        raise Exception(_CANCELLED)

    picked_el = doc.GetElement(ref.ElementId)
    floor = get_source_floor(picked_el)

    if not floor:
        raise Exception("Не удалось определить исходное перекрытие")

    # Запоминаем текущее смещение до оптимизации
    cur_sx = get_double_param(floor, "FP_Смещение_X")
    cur_sy = get_double_param(floor, "FP_Смещение_Y")
    cur_sx_mm = round(internal_to_mm(cur_sx)) if cur_sx else 0.0
    cur_sy_mm = round(internal_to_mm(cur_sy)) if cur_sy else 0.0

    # Зазор от рёбер вырезов = макс. ширина профиля лонжерона
    _longeron_clearance_mm = 0
    for fam in FilteredElementCollector(doc).OfClass(Family):
        if fam.Name == "ФП_Лонжерон":
            for sid in fam.GetFamilySymbolIds():
                sym = doc.GetElement(sid)
                if sym:
                    pw = get_double_param(sym, "FP_Ширина_Профиля")
                    if pw:
                        pw_mm = internal_to_mm(pw)
                        if pw_mm > _longeron_clearance_mm:
                            _longeron_clearance_mm = pw_mm
            break

    search = evaluate_floor_shift(
        doc, floor, min_edge_clearance_mm=_longeron_clearance_mm
    )

    best = search["best"]

    preview_lines = []

    # Текущее vs. предлагаемое
    delta_x = abs(best["shift_x_mm"] - cur_sx_mm)
    delta_y = abs(best["shift_y_mm"] - cur_sy_mm)
    if delta_x < 2.0 and delta_y < 2.0:
        preview_lines.append(
            "Текущее смещение X={:.0f}, Y={:.0f} мм — уже оптимально.".format(
                cur_sx_mm, cur_sy_mm
            )
        )
    else:
        preview_lines.append(
            "Текущее: X={:.0f}, Y={:.0f} мм".format(cur_sx_mm, cur_sy_mm)
        )
        preview_lines.append(
            "Лучшее:  X={:.0f}, Y={:.0f} мм".format(
                best["shift_x_mm"], best["shift_y_mm"]
            )
        )
    preview_lines.append("")

    # Статус и ключевые цифры
    preview_lines.append("Статус: {}".format(get_shift_quality_status(best)))
    preview_lines.append(
        "Полных: {} | Подрезок: {} | Сложных: {}".format(
            best["full_count"],
            best["viable_simple_count"],
            best["complex_count"],
        )
    )

    nv = best["non_viable_count"]
    if nv > 0:
        preview_lines.append("Немонтируемых (<100 мм): {}".format(nv))

    gth = best.get("unsplit_holes", 0)
    if gth > 0:
        preview_lines.append("!! Колонн без разреза сеткой: {}".format(gth))

    nec = best.get("near_edge_count", 0)
    if nec > 0:
        preview_lines.append("Линий сетки у края колонн: {}".format(nec))

    preview_lines.append(
        "Мин. подрезка: {:.0f} мм | Типов: {}".format(
            best["min_viable_cut_mm"], best["unique_sizes"]
        )
    )
    preview_lines.append(
        "Площадь подрезок: {}".format(format_area_m2(best["total_cut_area_mm2"]))
    )

    preview_lines.append("")
    total_var = search.get("total_count", "?")
    preview_lines.append("Проверено вариантов: {}".format(total_var))

    apply_answer = forms.alert(
        "\n".join(preview_lines) + "\n\nПрименить и перерисовать сетку?",
        title=TITLE_SHIFT,
        yes=True,
        no=True,
    )

    if not apply_answer:
        raise Exception(_CANCELLED)

    with revit.Transaction("Применить лучшее смещение фальшпола"):
        ok_x = set_double_param(floor, "FP_Смещение_X", best["shift_x_internal"])
        ok_y = set_double_param(floor, "FP_Смещение_Y", best["shift_y_internal"])

        if not ok_x or not ok_y:
            raise Exception(
                "Не удалось записать FP_Смещение_X / FP_Смещение_Y. Проверь тип параметров и доступность записи."
            )

    grid_result = redraw_grid_for_floor(floor, view, "Перерисовать сетку фальшпола")

    done_lines = []
    done_lines.append("Готово. Смещение применено.")
    done_lines.append("")
    done_lines.append(
        "X = {:.0f} мм, Y = {:.0f} мм".format(best["shift_x_mm"], best["shift_y_mm"])
    )
    done_lines.append("Статус: {}".format(get_shift_quality_status(best)))
    done_lines.append("")
    done_lines.append("Полных: {}".format(best["full_count"]))
    done_lines.append("Подрезок (>=100 мм): {}".format(best["viable_simple_count"]))
    done_lines.append("Сложных (>=100 мм): {}".format(best["complex_count"]))
    nv = best["non_viable_count"]
    if nv > 0:
        done_lines.append("Немонтируемых (<100 мм): {}".format(nv))
    gth = best.get("unsplit_holes", 0)
    if gth > 0:
        done_lines.append("!! Колонн без разреза сеткой: {}".format(gth))
    nec = best.get("near_edge_count", 0)
    if nec > 0:
        done_lines.append("Линий сетки у края колонн: {}".format(nec))
    done_lines.append("")
    done_lines.append("Мин. подрезка: {:.0f} мм".format(best["min_viable_cut_mm"]))
    done_lines.append("Типов подрезок: {}".format(best["unique_sizes"]))
    done_lines.append(
        "Площадь подрезок: {}".format(format_area_m2(best["total_cut_area_mm2"]))
    )

    if grid_result:
        done_lines.append("")
        done_lines.append("Сетка перерисована.")
        done_lines.append(
            "Удалено старых линий: {}".format(grid_result["deleted_count"])
        )
        done_lines.append(
            "Создано новых линий: {}".format(grid_result["created_count"])
        )

    forms.alert("\n".join(done_lines), title=TITLE_SHIFT)

except Exception as ex:
    if str(ex) == _CANCELLED:
        forms.alert("Операция отменена.", title=TITLE_SHIFT)
    else:
        forms.alert("Ошибка:\n{}".format(str(ex)), title=TITLE_SHIFT)

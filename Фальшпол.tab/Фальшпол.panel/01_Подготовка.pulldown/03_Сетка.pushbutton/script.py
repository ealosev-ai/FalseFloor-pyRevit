# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import ViewPlan  # type: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import get_source_floor  # type: ignore
from floor_grid import redraw_grid_for_floor  # type: ignore
from floor_ui import TITLE_GRID  # type: ignore
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView


try:
    # 1. Проверка вида
    if not isinstance(view, ViewPlan):
        forms.alert(
            "Открой план, чтобы построить и перерисовать сетку линиями детализации.",
            title=TITLE_GRID,
        )
        raise Exception("Active view is not a plan")

    # 2. Выбор перекрытия или части
    ref = uidoc.Selection.PickObject(
        ObjectType.Element, "Выберите перекрытие фальшпола или его часть"
    )

    picked_el = doc.GetElement(ref.ElementId)
    floor = get_source_floor(picked_el)

    if not floor:
        forms.alert(
            "Не удалось определить исходное перекрытие.\n"
            "Выбери перекрытие или часть, созданную из него.",
            title=TITLE_GRID,
        )
        raise Exception("Source floor not found")

    grid_result = redraw_grid_for_floor(
        floor,
        view,
        "Построить сетку фальшпола",
        update_style=True,
    )

    # 8. Отчёт
    forms.alert(
        "Готово.\n\n"
        "ID перекрытия: {}\n"
        "Шаг X: {:.1f} мм\n"
        "Шаг Y: {:.1f} мм\n"
        "Смещение X: {:.1f} мм\n"
        "Смещение Y: {:.1f} мм\n"
        "Удалено старых линий: {}\n"
        "Создано новых линий: {}".format(
            floor.Id.Value,
            grid_result["step_x"] * 304.8,
            grid_result["step_y"] * 304.8,
            grid_result["shift_x"] * 304.8,
            grid_result["shift_y"] * 304.8,
            grid_result["deleted_count"],
            grid_result["created_count"],
        ),
        title=TITLE_GRID,
    )

except OperationCanceledException:
    forms.alert("Операция отменена.", title=TITLE_GRID)

except Exception as ex:
    forms.alert("Ошибка:\n{}".format(str(ex)), title=TITLE_GRID)

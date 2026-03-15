# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import ViewPlan  # type: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import FloorOrPartSelectionFilter, get_source_floor  # type: ignore
from floor_grid import redraw_grid_for_floor  # type: ignore
from floor_i18n import tr  # type: ignore
from floor_ui import TITLE_GRID  # type: ignore
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView


try:
    # 1. Проверка вида
    if not isinstance(view, ViewPlan):
        forms.alert(
            tr("open_plan_grid"),
            title=TITLE_GRID,
        )
        raise Exception("Active view is not a plan")

    # 2. Выбор перекрытия или части
    pick_filter = FloorOrPartSelectionFilter()
    ref = uidoc.Selection.PickObject(
        ObjectType.Element,
        pick_filter,
        tr("pick_floor_or_part_prompt"),
    )

    picked_el = doc.GetElement(ref.ElementId)
    floor = get_source_floor(picked_el)

    if not floor:
        forms.alert(
            tr("grid_source_not_found"),
            title=TITLE_GRID,
        )
        raise Exception("Source floor not found")

    grid_result = redraw_grid_for_floor(
        floor,
        view,
        tr("tx_redraw_grid"),
        update_style=True,
    )

    # 8. Отчёт
    forms.alert(
        tr(
            "grid_done",
            floor_id=floor.Id.Value,
            step_x=grid_result["step_x"] * 304.8,
            step_y=grid_result["step_y"] * 304.8,
            shift_x=grid_result["shift_x"] * 304.8,
            shift_y=grid_result["shift_y"] * 304.8,
            deleted=grid_result["deleted_count"],
            created=grid_result["created_count"],
        ),
        title=TITLE_GRID,
    )

except OperationCanceledException:
    forms.alert(tr("operation_cancelled"), title=TITLE_GRID)

except Exception as ex:
    forms.alert(tr("error_fmt", error=str(ex)), title=TITLE_GRID)

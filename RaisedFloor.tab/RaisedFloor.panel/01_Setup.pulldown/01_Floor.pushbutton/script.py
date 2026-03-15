# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import BuiltInCategory  # type: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import (  # type: ignore
    FloorOrPartSelectionFilter,
    get_id_value,
    get_source_floor,
    set_double_param,
    set_string_param,
)
from floor_i18n import tr  # type: ignore
from floor_ui import TITLE_PREPARE  # type: ignore
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc


def mm_to_internal(mm_value):
    return float(mm_value) / 304.8


def ask_mm_value(title, prompt, default_value):
    text_val = forms.ask_for_string(
        default=str(default_value), prompt=prompt, title=title
    )
    if text_val is None:
        return None
    text_val = text_val.replace(",", ".").strip()
    try:
        return float(text_val)
    except Exception:
        forms.alert(
            tr("invalid_number_fmt", value=text_val),
            title=title,
        )
        return None


try:
    # 1. Выбор перекрытия
    pick_filter = FloorOrPartSelectionFilter()
    ref = uidoc.Selection.PickObject(
        ObjectType.Element,
        pick_filter,
        tr("pick_floor_prompt"),
    )
    picked_el = doc.GetElement(ref.ElementId)
    floor = get_source_floor(picked_el)

    if not floor or not floor.Category:
        forms.alert(tr("invalid_element"), title=TITLE_PREPARE)
        raise Exception("Invalid element")

    if get_id_value(floor.Category.Id) != int(BuiltInCategory.OST_Floors):
        forms.alert(tr("element_not_floor"), title=TITLE_PREPARE)
        raise Exception("Element is not a floor")

    # 2. Базовая точка (клик на плане)
    base_point = uidoc.Selection.PickPoint(tr("base_point_prompt"))

    # 3. Ввод шага плитки
    step_x_mm = ask_mm_value(TITLE_PREPARE, tr("prompt_step_x"), 600)
    if step_x_mm is None:
        raise OperationCanceledException()

    step_y_mm = ask_mm_value(TITLE_PREPARE, tr("prompt_step_y"), 600)
    if step_y_mm is None:
        raise OperationCanceledException()

    # 3b. Ввод высоты фальшпола
    height_mm = ask_mm_value(TITLE_PREPARE, tr("prompt_floor_height"), 500)
    if height_mm is None:
        raise OperationCanceledException()

    # 4. Запись параметров (смещение = 0, будет найдено кнопкой 04)
    missing_params = []

    with revit.Transaction(tr("tx_prepare_floor")):
        pairs = [
            ("RF_Step_X", mm_to_internal(step_x_mm)),
            ("RF_Step_Y", mm_to_internal(step_y_mm)),
            ("RF_Offset_X", 0.0),
            ("RF_Offset_Y", 0.0),
            ("RF_Base_X", base_point.X),
            ("RF_Base_Y", base_point.Y),
            ("RF_Base_Z", base_point.Z),
            ("RF_Floor_Height", mm_to_internal(height_mm)),
        ]
        for name, val in pairs:
            if not set_double_param(floor, name, val):
                missing_params.append(name)

        if not set_string_param(floor, "RF_Gen_Status", "Подготовлено"):
            missing_params.append("RF_Gen_Status")

    # 5. Отчёт
    if missing_params:
        forms.alert(
            tr(
                "prepare_partial",
                floor_id=get_id_value(floor.Id),
                step_x=step_x_mm,
                step_y=step_y_mm,
                height=height_mm,
                missing="\n- ".join(missing_params),
            ),
            title=TITLE_PREPARE,
        )
    else:
        forms.alert(
            tr(
                "prepare_done",
                floor_id=get_id_value(floor.Id),
                step_x=step_x_mm,
                step_y=step_y_mm,
                height=height_mm,
            ),
            title=TITLE_PREPARE,
        )

except OperationCanceledException:
    forms.alert(tr("operation_cancelled"), title=TITLE_PREPARE)

except Exception as ex:
    forms.alert(tr("error_fmt", error=str(ex)), title=TITLE_PREPARE)

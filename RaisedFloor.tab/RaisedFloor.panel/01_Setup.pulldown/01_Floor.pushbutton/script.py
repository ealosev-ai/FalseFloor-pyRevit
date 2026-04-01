# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import BuiltInCategory  # type: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_base import get_canonical_base_point  # type: ignore
from floor_common import (  # type: ignore
    FloorOrPartSelectionFilter,
    get_id_value,
    get_source_floor,
    set_double_param,
    set_string_param,
)
from floor_i18n import tr  # type: ignore
from floor_ui import TITLE_PREPARE  # type: ignore
from rf_param_schema import RFParams as P  # type: ignore
from pyrevit import forms, revit  # type: ignore
from revit_context import get_doc, get_uidoc  # type: ignore


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
    doc = get_doc()
    uidoc = get_uidoc()

    if not doc or not uidoc:
        raise Exception(tr("source_floor_not_found"))

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

    # 2. Каноническая базовая точка по внешнему контуру
    base_point = get_canonical_base_point(floor)
    if not base_point:
        raise Exception(tr("contour_face_not_found"))

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
            (P.STEP_X, mm_to_internal(step_x_mm)),
            (P.STEP_Y, mm_to_internal(step_y_mm)),
            (P.OFFSET_X, 0.0),
            (P.OFFSET_Y, 0.0),
            (P.BASE_X, base_point.X),
            (P.BASE_Y, base_point.Y),
            (P.BASE_Z, base_point.Z),
            (P.FLOOR_HEIGHT, mm_to_internal(height_mm)),
        ]
        for name, val in pairs:
            if not set_double_param(floor, name, val):
                missing_params.append(name)

        if not set_string_param(floor, P.GEN_STATUS, "Подготовлено"):
            missing_params.append(P.GEN_STATUS)

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

# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import BuiltInCategory  # type: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import (  # type: ignore
    get_id_value,
    set_double_param,
    set_string_param,
)
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
            "Не удалось преобразовать '{}' в число.".format(text_val),
            title=title,
        )
        return None


try:
    # 1. Выбор перекрытия
    ref = uidoc.Selection.PickObject(
        ObjectType.Element, "Выберите управляющее перекрытие фальшпола"
    )
    floor = doc.GetElement(ref.ElementId)

    if not floor or not floor.Category:
        forms.alert("Элемент не найден или без категории.", title=TITLE_PREPARE)
        raise Exception("Invalid element")

    if get_id_value(floor.Category.Id) != int(BuiltInCategory.OST_Floors):
        forms.alert("Выбранный элемент не является перекрытием.", title=TITLE_PREPARE)
        raise Exception("Element is not a floor")

    # 2. Базовая точка (клик на плане)
    base_point = uidoc.Selection.PickPoint("Укажите базовую точку раскладки")

    # 3. Ввод шага плитки
    step_x_mm = ask_mm_value(TITLE_PREPARE, "Введите шаг X, мм", 600)
    if step_x_mm is None:
        raise OperationCanceledException()

    step_y_mm = ask_mm_value(TITLE_PREPARE, "Введите шаг Y, мм", 600)
    if step_y_mm is None:
        raise OperationCanceledException()

    # 3b. Ввод высоты фальшпола
    height_mm = ask_mm_value(TITLE_PREPARE, "Введите высоту фальшпола, мм", 500)
    if height_mm is None:
        raise OperationCanceledException()

    # 4. Запись параметров (смещение = 0, будет найдено кнопкой 04)
    missing_params = []

    with revit.Transaction("Подготовить зону фальшпола"):
        pairs = [
            ("FP_Шаг_X", mm_to_internal(step_x_mm)),
            ("FP_Шаг_Y", mm_to_internal(step_y_mm)),
            ("FP_Смещение_X", 0.0),
            ("FP_Смещение_Y", 0.0),
            ("FP_База_X", base_point.X),
            ("FP_База_Y", base_point.Y),
            ("FP_База_Z", base_point.Z),
            ("FP_Высота_Фальшпола", mm_to_internal(height_mm)),
        ]
        for name, val in pairs:
            if not set_double_param(floor, name, val):
                missing_params.append(name)

        if not set_string_param(floor, "FP_Статус_Генерации", "Подготовлено"):
            missing_params.append("FP_Статус_Генерации")

    # 5. Отчёт
    if missing_params:
        forms.alert(
            "Зона подготовлена, но не все параметры записаны.\n\n"
            "ID перекрытия: {}\n"
            "Шаг: {} x {} мм\n"
            "Высота: {} мм\n\n"
            "Не записаны:\n- {}".format(
                get_id_value(floor.Id),
                step_x_mm,
                step_y_mm,
                height_mm,
                "\n- ".join(missing_params),
            ),
            title=TITLE_PREPARE,
        )
    else:
        forms.alert(
            "Готово.\n\n"
            "ID перекрытия: {}\n"
            "Шаг: {} x {} мм\n"
            "Высота фальшпола: {} мм\n"
            "Смещение: 0 (будет найдено кнопкой 04)\n"
            "База записана.\n"
            "Статус: Подготовлено".format(
                get_id_value(floor.Id), step_x_mm, step_y_mm, height_mm
            ),
            title=TITLE_PREPARE,
        )

except OperationCanceledException:
    forms.alert("Операция отменена.", title=TITLE_PREPARE)

except Exception as ex:
    forms.alert("Ошибка:\n{}".format(str(ex)), title=TITLE_PREPARE)

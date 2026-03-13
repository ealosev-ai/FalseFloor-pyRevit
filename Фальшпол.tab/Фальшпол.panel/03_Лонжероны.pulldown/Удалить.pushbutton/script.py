# -*- coding: utf-8 -*-
"""Удаление всех лонжеронов, размещённых скриптом."""

from Autodesk.Revit.DB import ElementId, ViewPlan  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import (  # type: ignore
    FloorOrPartSelectionFilter,
    get_source_floor,
    get_string_param,
    parse_ids_from_string,
    set_string_param,
)
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView

TITLE = "Удалить лонжероны"
_CANCELLED = "@@CANCELLED@@"

try:
    if not isinstance(view, ViewPlan):
        forms.alert("Открой план.", title=TITLE)
        raise Exception(_CANCELLED)

    ref = uidoc.Selection.PickObject(
        ObjectType.Element,
        FloorOrPartSelectionFilter(),
        "Выберите перекрытие фальшпола",
    )
    floor = get_source_floor(doc.GetElement(ref.ElementId))
    if not floor:
        raise Exception("Не удалось определить перекрытие")

    upper_ids = parse_ids_from_string(get_string_param(floor, "FP_ID_Лонжеронов_Верх"))
    lower_ids = parse_ids_from_string(get_string_param(floor, "FP_ID_Лонжеронов_Низ"))
    all_ids = list(set(upper_ids + lower_ids))

    if not all_ids:
        forms.alert("Лонжероны не найдены.", title=TITLE)
        raise Exception(_CANCELLED)

    confirm = forms.alert(
        "Удалить лонжеронов: {} (верх: {}, низ: {})\n\nПродолжить?".format(
            len(all_ids), len(upper_ids), len(lower_ids)
        ),
        title=TITLE,
        yes=True,
        no=True,
    )
    if not confirm:
        raise Exception(_CANCELLED)

    with revit.Transaction("Удалить лонжероны"):
        deleted = 0
        for int_id in all_ids:
            try:
                el = doc.GetElement(ElementId(int_id))
                if el:
                    doc.Delete(ElementId(int_id))
                    deleted += 1
            except Exception:
                pass
        set_string_param(floor, "FP_ID_Лонжеронов_Верх", "")
        set_string_param(floor, "FP_ID_Лонжеронов_Низ", "")

    forms.alert("Удалено лонжеронов: {}".format(deleted), title=TITLE)

except Exception as ex:
    if str(ex) != _CANCELLED:
        forms.alert("Ошибка: {}".format(ex), title=TITLE)

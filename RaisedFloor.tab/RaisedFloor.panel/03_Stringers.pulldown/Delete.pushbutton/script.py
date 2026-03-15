# -*- coding: utf-8 -*-
"""Удаление всех стрингеров, размещённых скриптом."""

from Autodesk.Revit.DB import ElementId, ViewPlan  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import (  # type: ignore
    FloorOrPartSelectionFilter,
    get_source_floor,
    get_string_param,
    parse_ids_from_string,
    set_string_param,
)
from floor_i18n import tr  # type: ignore
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView

TITLE = tr("del_title_longerons")
_CANCELLED = "@@CANCELLED@@"

try:
    if not isinstance(view, ViewPlan):
        forms.alert(tr("open_plan"), title=TITLE)
        raise Exception(_CANCELLED)

    ref = uidoc.Selection.PickObject(
        ObjectType.Element,
        FloorOrPartSelectionFilter(),
        tr("pick_floor_prompt"),
    )
    floor = get_source_floor(doc.GetElement(ref.ElementId))
    if not floor:
        raise Exception(tr("source_floor_not_found"))

    upper_ids = parse_ids_from_string(get_string_param(floor, "FP_ID_Лонжеронов_Верх"))
    lower_ids = parse_ids_from_string(get_string_param(floor, "FP_ID_Лонжеронов_Низ"))
    all_ids = list(set(upper_ids + lower_ids))

    if not all_ids:
        forms.alert(tr("del_not_found_longerons"), title=TITLE)
        raise Exception(_CANCELLED)

    confirm = forms.alert(
        tr(
            "del_confirm_longerons",
            count=len(all_ids),
            upper=len(upper_ids),
            lower=len(lower_ids),
        ),
        title=TITLE,
        yes=True,
        no=True,
    )
    if not confirm:
        raise Exception(_CANCELLED)

    with revit.Transaction(tr("tx_delete_longerons")):
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

    forms.alert(tr("del_done_longerons", count=deleted), title=TITLE)

except Exception as ex:
    if str(ex) != _CANCELLED:
        forms.alert(tr("error_inline_fmt", error=str(ex)), title=TITLE)

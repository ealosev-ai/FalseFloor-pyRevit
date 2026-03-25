# -*- coding: utf-8 -*-
"""Удаление всех плиток, размещённых скриптом."""

from Autodesk.Revit.DB import ElementId, ViewPlan  # type: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
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
from rf_param_schema import RFParams as P  # type: ignore
from revit_context import get_active_view, get_doc, get_uidoc  # type: ignore

TITLE = tr("del_title_tiles")


class _Cancel(Exception):
    pass


try:
    doc = get_doc()
    uidoc = get_uidoc()
    view = get_active_view()

    if not doc or not uidoc:
        raise Exception(tr("source_floor_not_found"))

    if not isinstance(view, ViewPlan):
        forms.alert(tr("open_plan"), title=TITLE)
        raise _Cancel()

    try:
        ref = uidoc.Selection.PickObject(
            ObjectType.Element,
            FloorOrPartSelectionFilter(),
            tr("pick_floor_prompt"),
        )
    except OperationCanceledException:
        raise _Cancel()
    floor = get_source_floor(doc.GetElement(ref.ElementId))
    if not floor:
        raise Exception(tr("source_floor_not_found"))

    old_ids = parse_ids_from_string(get_string_param(floor, P.TILES_ID))
    if not old_ids:
        forms.alert(tr("del_not_found_tiles"), title=TITLE)
        raise _Cancel()

    confirm = forms.alert(
        tr("del_confirm_tiles", count=len(old_ids)),
        title=TITLE,
        yes=True,
        no=True,
    )
    if not confirm:
        raise _Cancel()

    with revit.Transaction(tr("tx_delete_tiles")):
        deleted = 0
        for int_id in old_ids:
            try:
                el = doc.GetElement(ElementId(int_id))
                if el:
                    doc.Delete(ElementId(int_id))
                    deleted += 1
            except Exception:
                pass
        set_string_param(floor, P.TILES_ID, "")

    forms.alert(tr("del_done_tiles", count=deleted), title=TITLE)

except _Cancel:
    pass
except Exception as ex:
    forms.alert(tr("error_inline_fmt", error=str(ex)), title=TITLE)

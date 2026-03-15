# -*- coding: utf-8 -*-
"""Удаление ВСЕХ элементов фальшпола: плитки, стрингеры, стойки, сетка, контур."""

from Autodesk.Revit.DB import ElementId, ViewPlan  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import (  # type: ignore
    FloorOrPartSelectionFilter,
    get_source_floor,
    get_string_param,
    parse_ids_from_string,
    read_reinforcement_zone_ids,
    set_string_param,
)
from floor_i18n import tr  # type: ignore
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView

TITLE = tr("del_title_all")
_CANCELLED = "@@CANCELLED@@"

# Параметры → какие ID хранят элементы фальшпола
_PARAM_MAP = [
    ("FP_ID_Стоек", "label_supports"),
    ("FP_ID_Лонжеронов_Верх", "label_longerons_upper"),
    ("FP_ID_Лонжеронов_Низ", "label_longerons_lower"),
    ("FP_ID_Плиток", "label_tiles"),
    ("FP_ID_ЛинийСетки", "label_grid_lines"),
    ("FP_ID_МаркераБазы", "label_base_marker"),
    ("FP_ID_ЛинийКонтура", "label_contour_lines"),
]

_PARAM_ZONES = "FP_ЗоныУсиления_JSON"
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

    # Собираем все ID
    groups = []
    total = 0
    for param_name, label_key in _PARAM_MAP:
        ids = parse_ids_from_string(get_string_param(floor, param_name))
        if ids:
            groups.append((param_name, tr(label_key), ids))
            total += len(ids)

    zone_ids = list(set(read_reinforcement_zone_ids(floor)))
    if zone_ids:
        groups.append((_PARAM_ZONES, tr("label_reinf_longerons"), zone_ids))
        total += len(zone_ids)

    if total == 0:
        forms.alert(tr("del_elements_not_found"), title=TITLE)
        raise Exception(_CANCELLED)

    msg_lines = [tr("del_will_delete", count=total), ""]
    for _, label, ids in groups:
        msg_lines.append("  {} — {}".format(label, len(ids)))
    msg_lines.extend(["", tr("continue")])

    confirm = forms.alert(
        "\n".join(msg_lines),
        title=TITLE,
        yes=True,
        no=True,
    )
    if not confirm:
        raise Exception(_CANCELLED)

    with revit.Transaction(tr("tx_delete_all")):
        deleted = 0
        for param_name, label, ids in groups:
            for int_id in ids:
                try:
                    el = doc.GetElement(ElementId(int_id))
                    if el:
                        doc.Delete(ElementId(int_id))
                        deleted += 1
                except Exception:
                    pass
            if param_name != _PARAM_ZONES:
                set_string_param(floor, param_name, "")

        set_string_param(floor, _PARAM_ZONES, "")

    forms.alert(tr("del_done_all", deleted=deleted, total=total), title=TITLE)

except Exception as ex:
    if str(ex) != _CANCELLED:
        forms.alert(tr("error_inline_fmt", error=str(ex)), title=TITLE)

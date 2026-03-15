# -*- coding: utf-8 -*-
"""Стрингеры: удалить зону усиления по ID."""

from Autodesk.Revit.DB import ElementId, ViewPlan  # type: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import (  # type: ignore
    FloorOrPartSelectionFilter,
    get_source_floor,
    load_reinforcement_zones,
    save_reinforcement_zones,
)
from floor_i18n import tr  # type: ignore
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView

TITLE = tr("reinf_del_title")
PARAM_ZONES = "FP_ЗоныУсиления_JSON"


class _Cancel(Exception):
    pass


def _pick_floor():
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
    return floor


def _zone_label(zone):
    zid = zone.get("zone_id", "?")
    mode = zone.get("mode", "?")
    layers = zone.get("layers", "?")
    up = len(zone.get("upper_ids") or [])
    lo = len(zone.get("lower_ids") or [])
    su = len(zone.get("support_ids") or [])
    created = zone.get("created_at", "")
    return tr(
        "reinf_zone_label",
        zid=zid,
        mode=mode,
        layers=layers,
        upper=up,
        lower=lo,
        supports=su,
        created=created,
    )


def main():
    floor = _pick_floor()

    p_zone = floor.LookupParameter(PARAM_ZONES)
    if p_zone is None:
        forms.alert(
            tr("reinf_param_not_found", param=PARAM_ZONES),
            title=TITLE,
        )
        raise _Cancel()

    data = load_reinforcement_zones(floor, default_version=1)
    zones = data.get("zones", [])
    if not zones:
        forms.alert(tr("reinf_zones_not_found"), title=TITLE)
        raise _Cancel()

    labels = [_zone_label(z) for z in zones]
    selected = forms.CommandSwitchWindow.show(labels, message=tr("reinf_select_zone"))
    if not selected:
        raise _Cancel()

    idx = labels.index(selected)
    zone = zones[idx]

    upper_ids = zone.get("upper_ids") or []
    lower_ids = zone.get("lower_ids") or []
    support_ids = zone.get("support_ids") or []
    all_ids = list(set([int(i) for i in upper_ids + lower_ids + support_ids]))

    msg = [
        tr("reinf_delete_zone", zid=zone.get("zone_id", "?")),
        tr("reinf_upper_fmt", count=len(upper_ids)),
        tr("reinf_lower_fmt", count=len(lower_ids)),
        tr("reinf_supports_fmt", count=len(support_ids)),
        "",
        tr("continue"),
    ]
    if not forms.alert("\n".join(msg), title=TITLE, yes=True, no=True):
        raise _Cancel()

    with revit.Transaction(tr("tx_delete_reinf_zone")):
        deleted = 0
        for int_id in all_ids:
            try:
                el = doc.GetElement(ElementId(int_id))
                if el:
                    doc.Delete(ElementId(int_id))
                    deleted += 1
            except Exception:
                pass

        zones.pop(idx)
        data["zones"] = zones
        save_reinforcement_zones(floor, data)

    forms.alert(
        tr("reinf_zone_deleted", deleted=deleted, remaining=len(zones)),
        title=TITLE,
    )


try:
    main()
except _Cancel:
    pass
except Exception as ex:
    forms.alert(tr("error_inline_fmt", error=str(ex)), title=TITLE)

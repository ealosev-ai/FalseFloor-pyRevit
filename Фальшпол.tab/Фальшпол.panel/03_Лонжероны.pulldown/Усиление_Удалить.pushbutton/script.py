# -*- coding: utf-8 -*-
"""Лонжероны: удалить зону усиления по ID."""

from Autodesk.Revit.DB import ElementId, ViewPlan  # type: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import (  # type: ignore
    FloorOrPartSelectionFilter,
    get_source_floor,
    load_reinforcement_zones,
    save_reinforcement_zones,
)
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView

TITLE = "Усиление: удалить"
PARAM_ZONES = "FP_ЗоныУсиления_JSON"


class _Cancel(Exception):
    pass


def _pick_floor():
    if not isinstance(view, ViewPlan):
        forms.alert("Открой план.", title=TITLE)
        raise _Cancel()
    try:
        ref = uidoc.Selection.PickObject(
            ObjectType.Element,
            FloorOrPartSelectionFilter(),
            "Выберите перекрытие фальшпола",
        )
    except OperationCanceledException:
        raise _Cancel()

    floor = get_source_floor(doc.GetElement(ref.ElementId))
    if not floor:
        raise Exception("Не удалось определить исходное перекрытие")
    return floor


def _zone_label(zone):
    zid = zone.get("zone_id", "?")
    mode = zone.get("mode", "?")
    layers = zone.get("layers", "?")
    up = len(zone.get("upper_ids") or [])
    lo = len(zone.get("lower_ids") or [])
    su = len(zone.get("support_ids") or [])
    created = zone.get("created_at", "")
    return "{} | {} | {} | верх={} низ={} стойки={} | {}".format(
        zid,
        mode,
        layers,
        up,
        lo,
        su,
        created,
    )


def main():
    floor = _pick_floor()

    p_zone = floor.LookupParameter(PARAM_ZONES)
    if p_zone is None:
        forms.alert(
            "Не найден параметр {}.\nСначала запусти 00 Параметры ФП.".format(
                PARAM_ZONES
            ),
            title=TITLE,
        )
        raise _Cancel()

    data = load_reinforcement_zones(floor, default_version=1)
    zones = data.get("zones", [])
    if not zones:
        forms.alert("Зоны усиления не найдены.", title=TITLE)
        raise _Cancel()

    labels = [_zone_label(z) for z in zones]
    selected = forms.CommandSwitchWindow.show(
        labels, message="Выбери зону для удаления:"
    )
    if not selected:
        raise _Cancel()

    idx = labels.index(selected)
    zone = zones[idx]

    upper_ids = zone.get("upper_ids") or []
    lower_ids = zone.get("lower_ids") or []
    support_ids = zone.get("support_ids") or []
    all_ids = list(set([int(i) for i in upper_ids + lower_ids + support_ids]))

    msg = [
        "Удалить зону {}".format(zone.get("zone_id", "?")),
        "Верхних: {}".format(len(upper_ids)),
        "Нижних: {}".format(len(lower_ids)),
        "Стоек: {}".format(len(support_ids)),
        "",
        "Продолжить?",
    ]
    if not forms.alert("\n".join(msg), title=TITLE, yes=True, no=True):
        raise _Cancel()

    with revit.Transaction("Удалить зону усиления"):
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
        "Зона удалена.\nУдалено элементов: {}\nОсталось зон: {}".format(
            deleted,
            len(zones),
        ),
        title=TITLE,
    )


try:
    main()
except _Cancel:
    pass
except Exception as ex:
    forms.alert("Ошибка: {}".format(str(ex)), title=TITLE)

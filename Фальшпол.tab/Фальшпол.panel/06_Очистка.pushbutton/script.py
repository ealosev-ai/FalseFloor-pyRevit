# -*- coding: utf-8 -*-
"""Удаление ВСЕХ элементов фальшпола: плитки, лонжероны, стойки, сетка, контур."""

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

TITLE = "Удалить всё"
_CANCELLED = "@@CANCELLED@@"

# Параметры → какие ID хранят элементы фальшпола
_PARAM_MAP = [
    ("FP_ID_Стоек", "Стойки"),
    ("FP_ID_Лонжеронов_Верх", "Лонжероны верх"),
    ("FP_ID_Лонжеронов_Низ", "Лонжероны низ"),
    ("FP_ID_Плиток", "Плитки"),
    ("FP_ID_ЛинийСетки", "Линии сетки"),
    ("FP_ID_МаркераБазы", "Маркер базы"),
    ("FP_ID_ЛинийКонтура", "Линии контура"),
]

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

    # Собираем все ID
    groups = []
    total = 0
    for param_name, label in _PARAM_MAP:
        ids = parse_ids_from_string(get_string_param(floor, param_name))
        if ids:
            groups.append((param_name, label, ids))
            total += len(ids)

    if total == 0:
        forms.alert("Элементы фальшпола не найдены.", title=TITLE)
        raise Exception(_CANCELLED)

    msg_lines = ["Будет удалено элементов: {}".format(total), ""]
    for _, label, ids in groups:
        msg_lines.append("  {} — {}".format(label, len(ids)))
    msg_lines.extend(["", "Продолжить?"])

    confirm = forms.alert(
        "\n".join(msg_lines),
        title=TITLE,
        yes=True,
        no=True,
    )
    if not confirm:
        raise Exception(_CANCELLED)

    with revit.Transaction("Удалить всё (фальшпол)"):
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
            set_string_param(floor, param_name, "")

    forms.alert("Удалено: {} из {}".format(deleted, total), title=TITLE)

except Exception as ex:
    if str(ex) != _CANCELLED:
        forms.alert("Ошибка: {}".format(ex), title=TITLE)

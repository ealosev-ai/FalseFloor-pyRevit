# -*- coding: utf-8 -*-
"""05В Вентиляция — пометить выбранные плитки как вентилируемые.

Выберите плитки RF_Tile → скрипт переключает RF_Ventilated (0↔1).
Если в семействе есть тип с «Вент» в названии — переключает на него
(или обратно на стандартный тип при снятии пометки).
"""

from Autodesk.Revit.DB import (  # type: ignore
    FamilyInstance,
    StorageType,
)
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ISelectionFilter, ObjectType  # type: ignore
from floor_i18n import tr  # type: ignore
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
TITLE = tr("vent_title")
FAMILY_NAME = "RF_Tile"


class _Cancel(Exception):
    pass


class _TileSelectionFilter(ISelectionFilter):
    def AllowElement(self, element):
        if not isinstance(element, FamilyInstance):
            return False
        try:
            return element.Symbol.Family.Name == FAMILY_NAME
        except Exception:
            return False

    def AllowReference(self, reference, position):
        return True


def _get_int_param(inst, name):
    p = inst.LookupParameter(name)
    if p and p.StorageType == StorageType.Integer:
        return p.AsInteger()
    return 0


def _set_int_param(inst, name, value):
    p = inst.LookupParameter(name)
    if p and not p.IsReadOnly and p.StorageType == StorageType.Integer:
        p.Set(int(value))
        return True
    return False


def _set_string_param(inst, name, value):
    p = inst.LookupParameter(name)
    if p and not p.IsReadOnly and p.StorageType == StorageType.String:
        p.Set(str(value))
        return True
    return False


def _get_string_param(inst, name):
    p = inst.LookupParameter(name)
    if p and p.StorageType == StorageType.String:
        return p.AsString() or ""
    return ""


def _find_vent_type(family):
    """Ищет тип с 'Вент'/'Vent' в названии среди типов семейства."""
    for sid in family.GetFamilySymbolIds():
        sym = doc.GetElement(sid)
        lower_name = (sym.Name or "").lower() if sym else ""
        if sym and ("вент" in lower_name or "vent" in lower_name):
            return sym
    return None


def _find_standard_type(family):
    """Ищет стандартный (не вент) тип — первый без 'Вент'/'Vent' в названии."""
    for sid in family.GetFamilySymbolIds():
        sym = doc.GetElement(sid)
        lower_name = (sym.Name or "").lower() if sym else ""
        if sym and "вент" not in lower_name and "vent" not in lower_name:
            return sym
    return None


try:
    # --- Выбор плиток ---
    sel_ids = uidoc.Selection.GetElementIds()
    tiles = []
    if sel_ids.Count > 0:
        for eid in sel_ids:
            el = doc.GetElement(eid)
            if isinstance(el, FamilyInstance):
                fam_name = el.Symbol.Family.Name
                if fam_name == FAMILY_NAME:
                    tiles.append(el)

    if not tiles:
        try:
            refs = uidoc.Selection.PickObjects(
                ObjectType.Element, _TileSelectionFilter(), tr("vent_select_tiles")
            )
        except OperationCanceledException:
            raise _Cancel()

        for r in refs:
            el = doc.GetElement(r.ElementId)
            if isinstance(el, FamilyInstance):
                fam_name = el.Symbol.Family.Name
                if fam_name == FAMILY_NAME:
                    tiles.append(el)

    if not tiles:
        forms.alert(tr("vent_none_selected"), title=TITLE)
        raise _Cancel()

    # --- Определяем действие: пометить или снять ---
    vent_count = sum(1 for t in tiles if _get_int_param(t, "RF_Ventilated") == 1)
    non_vent_count = len(tiles) - vent_count

    if vent_count == 0:
        action = "mark"
    elif non_vent_count == 0:
        action = "unmark"
    else:
        options = [
            tr("vent_mark_option"),
            tr("vent_unmark_option"),
        ]
        choice = forms.CommandSwitchWindow.show(
            options,
            message=tr(
                "vent_mixed_message",
                total=len(tiles),
                vent=vent_count,
                normal=non_vent_count,
            ),
        )
        if not choice:
            raise _Cancel()
        action = "mark" if choice == tr("vent_mark_option") else "unmark"

    # --- Ищем типы семейства (вент / стандартный) ---
    family = tiles[0].Symbol.Family
    vent_type = _find_vent_type(family)
    std_type = _find_standard_type(family)

    # --- Применяем ---
    with revit.Transaction(tr("tx_vent_tiles")):
        if vent_type and not vent_type.IsActive:
            vent_type.Activate()
        if std_type and not std_type.IsActive:
            std_type.Activate()

        changed = 0
        for tile in tiles:
            if action == "mark":
                _set_int_param(tile, "RF_Ventilated", 1)
                mark = _get_string_param(tile, "RF_Mark")
                if mark and not mark.endswith(".В"):
                    _set_string_param(tile, "RF_Mark", mark + ".В")
                if vent_type:
                    tile.ChangeTypeId(vent_type.Id)
                changed += 1
            else:
                _set_int_param(tile, "RF_Ventilated", 0)
                mark = _get_string_param(tile, "RF_Mark")
                if mark and mark.endswith(".В"):
                    _set_string_param(tile, "RF_Mark", mark[:-2])
                if std_type:
                    tile.ChangeTypeId(std_type.Id)
                changed += 1

    # --- Отчёт ---
    if action == "mark":
        type_info = tr("vent_type_info", name=vent_type.Name) if vent_type else ""
        msg = tr("vent_marked", count=changed) + type_info
    else:
        type_info = tr("vent_type_info", name=std_type.Name) if std_type else ""
        msg = tr("vent_unmarked", count=changed) + type_info

    forms.alert(msg, title=TITLE)

except _Cancel:
    pass
except Exception as ex:
    forms.alert(tr("error_inline_fmt", error=str(ex)), title=TITLE)

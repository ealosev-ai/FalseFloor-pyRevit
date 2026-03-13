# -*- coding: utf-8 -*-
"""05В Вентиляция — пометить выбранные плитки как вентилируемые.

Выберите плитки ФП_Плитка → скрипт переключает FP_Вентилируемая (0↔1).
Если в семействе есть тип с «Вент» в названии — переключает на него
(или обратно на стандартный тип при снятии пометки).
"""

from Autodesk.Revit.DB import (  # type: ignore
    FamilyInstance,
    StorageType,
)
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
TITLE = u"05В Вентиляция"
FAMILY_NAME = u"ФП_Плитка"
_CANCELLED = "@@CANCELLED@@"


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
    """Ищет тип с 'Вент' в названии среди типов семейства."""
    for sid in family.GetFamilySymbolIds():
        sym = doc.GetElement(sid)
        if sym and u"Вент" in sym.Name:
            return sym
    return None


def _find_standard_type(family):
    """Ищет стандартный (не вент) тип — первый без 'Вент' в названии."""
    for sid in family.GetFamilySymbolIds():
        sym = doc.GetElement(sid)
        if sym and u"Вент" not in sym.Name:
            return sym
    return None


try:
    # --- Выбор плиток ---
    # Сначала проверяем текущее выделение
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
        # Ручной выбор
        try:
            refs = uidoc.Selection.PickObjects(
                ObjectType.Element,
                u"Выберите плитки ФП_Плитка"
            )
        except OperationCanceledException:
            raise Exception(_CANCELLED)

        for r in refs:
            el = doc.GetElement(r.ElementId)
            if isinstance(el, FamilyInstance):
                fam_name = el.Symbol.Family.Name
                if fam_name == FAMILY_NAME:
                    tiles.append(el)

    if not tiles:
        forms.alert(u"Не выбрано ни одной плитки ФП_Плитка.", title=TITLE)
        raise Exception(_CANCELLED)

    # --- Определяем действие: пометить или снять ---
    # Считаем сколько уже вентилируемых
    vent_count = sum(1 for t in tiles if _get_int_param(t, "FP_Вентилируемая") == 1)
    non_vent_count = len(tiles) - vent_count

    if vent_count == 0:
        action = "mark"  # все обычные → пометить
    elif non_vent_count == 0:
        action = "unmark"  # все вентилируемые → снять
    else:
        # Смешанный выбор — спросить
        choice = forms.alert(
            u"Выбрано {} плиток:\n"
            u"  Вентилируемых: {}\n"
            u"  Обычных: {}\n\n"
            u"Что сделать?".format(len(tiles), vent_count, non_vent_count),
            title=TITLE,
            options=[
                u"Пометить все как вентилируемые",
                u"Снять пометку со всех",
            ],
        )
        if not choice:
            raise Exception(_CANCELLED)
        action = "mark" if u"Пометить" in choice else "unmark"

    # --- Ищем типы семейства (вент / стандартный) ---
    family = tiles[0].Symbol.Family
    vent_type = _find_vent_type(family)
    std_type = _find_standard_type(family)

    # --- Применяем ---
    with revit.Transaction(u"Вентилируемые плитки"):
        if vent_type and not vent_type.IsActive:
            vent_type.Activate()
        if std_type and not std_type.IsActive:
            std_type.Activate()

        changed = 0
        for tile in tiles:
            if action == "mark":
                _set_int_param(tile, "FP_Вентилируемая", 1)
                # Добавляем суффикс "В" к марке если нет
                mark = _get_string_param(tile, "FP_Марка")
                if mark and not mark.endswith(u".В"):
                    _set_string_param(tile, "FP_Марка", mark + u".В")
                # Переключаем тип если есть вентилируемый
                if vent_type:
                    tile.ChangeTypeId(vent_type.Id)
                changed += 1
            else:  # unmark
                _set_int_param(tile, "FP_Вентилируемая", 0)
                # Убираем суффикс "В" из марки
                mark = _get_string_param(tile, "FP_Марка")
                if mark and mark.endswith(u".В"):
                    _set_string_param(tile, "FP_Марка", mark[:-2])
                # Возвращаем стандартный тип
                if std_type:
                    tile.ChangeTypeId(std_type.Id)
                changed += 1

    # --- Отчёт ---
    if action == "mark":
        type_info = u"\nТип → {}".format(vent_type.Name) if vent_type else ""
        msg = u"Помечено вентилируемых: {}{}".format(changed, type_info)
    else:
        type_info = u"\nТип → {}".format(std_type.Name) if std_type else ""
        msg = u"Снята пометка: {}{}".format(changed, type_info)

    forms.alert(msg, title=TITLE)

except Exception as ex:
    if str(ex) == _CANCELLED:
        pass
    else:
        forms.alert(u"Ошибка: {}".format(str(ex)), title=TITLE)

# -*- coding: utf-8 -*-
"""Очистить FP_-параметры — удаляет все FP_-параметры.

В редакторе семейства: удаляет FP_-параметры из текущего семейства.
В проекте: удаляет FP_-привязки из проекта через Revit API.
Определения в файле общих параметров (ФОП) не затрагиваются.
"""

from Autodesk.Revit.DB import (  # type: ignore
    Transaction,
)
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
app = doc.Application
TITLE = "Очистить FP_-параметры"


def _clean_family():
    """Удаляет все FP_-параметры из текущего документа семейства."""
    fam_mgr = doc.FamilyManager

    fp_params = []
    for p in fam_mgr.GetParameters():
        if p.Definition.Name.startswith("FP_"):
            fp_params.append(p)

    if not fp_params:
        forms.alert("FP_-параметров не найдено в семействе.", title=TITLE)
        return

    names = sorted([p.Definition.Name for p in fp_params])
    confirm = forms.alert(
        "Найдено FP_-параметров: {}\n\n{}\n\nУдалить все?".format(
            len(fp_params), "\n".join(names)
        ),
        title=TITLE,
        yes=True,
        no=True,
    )
    if not confirm:
        return

    removed = []
    errors = []

    t = Transaction(doc, "Remove FP params")
    t.Start()
    try:
        for p in fp_params:
            name = p.Definition.Name
            try:
                fam_mgr.RemoveParameter(p)
                removed.append(name)
            except Exception as ex:
                errors.append("{}: {}".format(name, ex))
        t.Commit()
    except Exception:
        if t.HasStarted():
            t.RollBack()
        raise

    report = ["Удалено: {}".format(len(removed))]
    if errors:
        report.append("\nОшибки:")
        for e in errors:
            report.append("  " + e)
    forms.alert("\n".join(report), title=TITLE)


def _clean_project():
    """Удаляет все FP_-привязки параметров из проекта через API."""
    bm = doc.ParameterBindings
    it = bm.ForwardIterator()
    it.Reset()

    fp_defs = []
    while it.MoveNext():
        defn = it.Key
        if defn and defn.Name and defn.Name.startswith("FP_"):
            fp_defs.append(defn)

    if not fp_defs:
        forms.alert("FP_-параметров не найдено в проекте.", title=TITLE)
        return

    names = sorted([d.Name for d in fp_defs])
    confirm = forms.alert(
        "Найдено FP_-параметров в проекте: {}\n\n{}\n\nУдалить все?".format(
            len(fp_defs), "\n".join(names)
        ),
        title=TITLE,
        yes=True,
        no=True,
    )
    if not confirm:
        return

    removed = []
    errors = []

    with revit.Transaction("Remove FP params"):
        for defn in fp_defs:
            name = defn.Name
            try:
                if bm.Remove(defn):
                    removed.append(name)
                else:
                    errors.append("{}: Remove returned False".format(name))
            except Exception as ex:
                errors.append("{}: {}".format(name, ex))

    report = ["Удалено из проекта: {}".format(len(removed))]
    if errors:
        report.append("\nОшибки:")
        for e in errors:
            report.append("  " + e)
    forms.alert("\n".join(report), title=TITLE)


# ── Основной блок ────────────────────────────────────────
try:
    if doc.IsFamilyDocument:
        _clean_family()
    else:
        _clean_project()
except Exception as ex:
    forms.alert("Ошибка: {}".format(str(ex)), title=TITLE)

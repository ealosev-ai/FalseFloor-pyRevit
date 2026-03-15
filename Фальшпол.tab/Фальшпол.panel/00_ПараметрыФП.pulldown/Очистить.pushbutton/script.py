# -*- coding: utf-8 -*-
"""Вычистить FP_ — удаляет все FP_-параметры из текущего документа.

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
TITLE = "Вычистить FP_ (ОПАСНО)"
CONFIRM_PHRASE = "УДАЛИТЬ FP"


def _confirm_hard_delete(scope_label, count, names):
    preview = "\n".join(names[:40])
    if len(names) > 40:
        preview += "\n... (+{} ещё)".format(len(names) - 40)

    msg = (
        "Найдено FP_-параметров {}: {}\n\n{}\n\n"
        "Это удалит все FP_-параметры из {}.\n"
        "Операция потенциально ломает старые спецификации/фильтры/скрипты.\n\n"
        "Продолжить?"
    ).format(scope_label, count, preview, scope_label)

    confirm = forms.alert(msg, title=TITLE, yes=True, no=True)
    if not confirm:
        return False

    typed = forms.ask_for_string(
        prompt="Для подтверждения введи: {}".format(CONFIRM_PHRASE),
        default="",
        title=TITLE,
    )
    return (typed or "").strip() == CONFIRM_PHRASE


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
    if not _confirm_hard_delete("в семействе", len(fp_params), names):
        forms.alert("Отмена очистки.", title=TITLE)
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
    if not _confirm_hard_delete("в проекте", len(fp_defs), names):
        forms.alert("Отмена очистки.", title=TITLE)
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

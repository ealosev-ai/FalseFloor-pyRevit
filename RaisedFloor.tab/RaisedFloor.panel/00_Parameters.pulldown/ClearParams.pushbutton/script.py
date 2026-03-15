# -*- coding: utf-8 -*-
"""Вычистить RF_ — удаляет все RF_ parameters из текущего документа.

В редакторе семейства: удаляет RF_ parameters из текущего семейства.
В проекте: удаляет RF_ bindings из проекта через Revit API.
Определения в файле общих параметров (ФОП) не затрагиваются.
"""

from Autodesk.Revit.DB import (  # type: ignore
    Transaction,
)
from floor_i18n import tr  # type: ignore
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
app = doc.Application
TITLE = tr("clean_title")
CONFIRM_PHRASE = tr("clean_confirm_phrase")


def _confirm_hard_delete(scope_label, count, names):
    preview = "\n".join(names[:40])
    if len(names) > 40:
        preview += "\n" + tr("clean_more", count=len(names) - 40)

    msg = tr("clean_found", scope=scope_label, count=count, preview=preview)

    confirm = forms.alert(msg, title=TITLE, yes=True, no=True)
    if not confirm:
        return False

    typed = forms.ask_for_string(
        prompt=tr("clean_type_confirm", phrase=CONFIRM_PHRASE),
        default="",
        title=TITLE,
    )
    return (typed or "").strip() == CONFIRM_PHRASE


def _clean_family():
    """Удаляет все RF_ parameters из текущего документа семейства."""
    fam_mgr = doc.FamilyManager

    fp_params = []
    for p in fam_mgr.GetParameters():
        if p.Definition.Name.startswith("RF_"):
            fp_params.append(p)

    if not fp_params:
        forms.alert(tr("clean_no_params_family"), title=TITLE)
        return

    names = sorted([p.Definition.Name for p in fp_params])
    if not _confirm_hard_delete(tr("clean_scope_family"), len(fp_params), names):
        forms.alert(tr("clean_cancel"), title=TITLE)
        return

    removed = []
    errors = []

    t = Transaction(doc, "Remove RF params")
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

    report = [tr("clean_removed", count=len(removed))]
    if errors:
        report.append(tr("clean_errors_header"))
        for e in errors:
            report.append("  " + e)
    forms.alert("\n".join(report), title=TITLE)


def _clean_project():
    """Удаляет все RF_ bindings параметров из проекта через API."""
    bm = doc.ParameterBindings
    it = bm.ForwardIterator()
    it.Reset()

    fp_defs = []
    while it.MoveNext():
        defn = it.Key
        if defn and defn.Name and defn.Name.startswith("RF_"):
            fp_defs.append(defn)

    if not fp_defs:
        forms.alert(tr("clean_no_params_project"), title=TITLE)
        return

    names = sorted([d.Name for d in fp_defs])
    if not _confirm_hard_delete(tr("clean_scope_project"), len(fp_defs), names):
        forms.alert(tr("clean_cancel"), title=TITLE)
        return

    removed = []
    errors = []

    with revit.Transaction("Remove RF params"):
        for defn in fp_defs:
            name = defn.Name
            try:
                if bm.Remove(defn):
                    removed.append(name)
                else:
                    errors.append("{}: Remove returned False".format(name))
            except Exception as ex:
                errors.append("{}: {}".format(name, ex))

    report = [tr("clean_removed_project", count=len(removed))]
    if errors:
        report.append(tr("clean_errors_header"))
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
    forms.alert(tr("error_inline_fmt", error=str(ex)), title=TITLE)

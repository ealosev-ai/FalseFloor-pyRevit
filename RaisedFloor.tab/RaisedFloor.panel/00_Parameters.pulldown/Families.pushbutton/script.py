# -*- coding: utf-8 -*-
"""Параметры семейств — добавляет FP_-параметры в загруженные ФП-семейства.

Открывает каждое семейство с префиксом «ФП_», добавляет недостающие
общие параметры через FamilyManager и перезагружает семейство в проект.

Каждому семейству добавляются только релевантные параметры:
  ФП_Плитка / ФП_вент_решетка  → параметры плитки
  ФП_Лонжерон                  → параметры стрингера
  ФП_Стойка                    → параметры стойки
"""

import os

from Autodesk.Revit.DB import (  # type: ignore
    ExternalDefinitionCreationOptions,
    Family,
    FilteredElementCollector,
    StorageType,
    Transaction,
)
from floor_i18n import tr  # type: ignore
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
app = doc.Application
TITLE = tr("fam_title")

# ── Все параметры (имя, StorageType, описание, is_instance) ──
FAMILY_PARAMS = [
    # Instance
    ("FP_Колонка", StorageType.Integer, "Колонка в сетке", True),
    ("FP_Ряд", StorageType.Integer, "Ряд в сетке", True),
    ("FP_Марка", StorageType.String, "Марка элемента ФП", True),
    ("FP_Тип_Плитки", StorageType.String, "Тип плитки (Полная/Подрезка/Сложная)", True),
    ("FP_Подрезка_X", StorageType.Double, "Размер подрезки X (ft)", True),
    ("FP_Подрезка_Y", StorageType.Double, "Размер подрезки Y (ft)", True),
    ("FP_Вырез_X", StorageType.Double, "Вырез ширина", True),
    ("FP_Вырез_Y", StorageType.Double, "Вырез высота", True),
    (
        "FP_Вырез_Смещ_X",
        StorageType.Double,
        "Отступ выреза от левого края плитки",
        True,
    ),
    (
        "FP_Вырез_Смещ_Y",
        StorageType.Double,
        "Отступ выреза от нижнего края плитки",
        True,
    ),
    ("FP_Вырез2_X", StorageType.Double, "Вырез 2 ширина", True),
    ("FP_Вырез2_Y", StorageType.Double, "Вырез 2 высота", True),
    (
        "FP_Вырез2_Смещ_X",
        StorageType.Double,
        "Отступ выреза 2 от левого края плитки",
        True,
    ),
    (
        "FP_Вырез2_Смещ_Y",
        StorageType.Double,
        "Отступ выреза 2 от нижнего края плитки",
        True,
    ),
    ("FP_Вырез3_X", StorageType.Double, "Вырез 3 ширина", True),
    ("FP_Вырез3_Y", StorageType.Double, "Вырез 3 высота", True),
    (
        "FP_Вырез3_Смещ_X",
        StorageType.Double,
        "Отступ выреза 3 от левого края плитки",
        True,
    ),
    (
        "FP_Вырез3_Смещ_Y",
        StorageType.Double,
        "Отступ выреза 3 от нижнего края плитки",
        True,
    ),
    ("FP_Тип_Лонжерона", StorageType.String, "Тип стрингера (Верхний/Нижний)", True),
    ("FP_Ось_Направления", StorageType.String, "Ось направления (X/Y)", True),
    ("FP_Высота_Стойки", StorageType.Double, "Высота стойки (ft)", True),
    ("FP_Вентилируемая", StorageType.Integer, "Вентилируемая плитка (0/1)", True),
    # Type
    ("FP_Высота_Профиля", StorageType.Double, "Высота профиля (ft)", False),
    ("FP_Ширина_Профиля", StorageType.Double, "Ширина профиля (ft)", False),
    ("FP_Толщина", StorageType.Double, "Толщина элемента (ft)", False),
    ("FP_Толщина_Стенки", StorageType.Double, "Толщина стенки профиля (ft)", False),
    ("FP_Размер_Опоры", StorageType.Double, "Размер опорной площадки (ft)", False),
    ("FP_Размер_Оголовка", StorageType.Double, "Размер оголовка стойки (ft)", False),
]

# ── Какие параметры нужны каждому типу семейства ──
_TILE_PARAMS = {
    "FP_Колонка",
    "FP_Ряд",
    "FP_Марка",
    "FP_Тип_Плитки",
    "FP_Подрезка_X",
    "FP_Подрезка_Y",
    "FP_Вырез_X",
    "FP_Вырез_Y",
    "FP_Вырез_Смещ_X",
    "FP_Вырез_Смещ_Y",
    "FP_Вырез2_X",
    "FP_Вырез2_Y",
    "FP_Вырез2_Смещ_X",
    "FP_Вырез2_Смещ_Y",
    "FP_Вырез3_X",
    "FP_Вырез3_Y",
    "FP_Вырез3_Смещ_X",
    "FP_Вырез3_Смещ_Y",
    "FP_Толщина",
    "FP_Вентилируемая",
}
_LONGERON_PARAMS = {
    "FP_Марка",
    "FP_Тип_Лонжерона",
    "FP_Ось_Направления",
    "FP_Высота_Профиля",
    "FP_Ширина_Профиля",
    "FP_Толщина_Стенки",
}
_SUPPORT_PARAMS = {
    "FP_Колонка",
    "FP_Ряд",
    "FP_Марка",
    "FP_Высота_Стойки",
    "FP_Размер_Опоры",
    "FP_Размер_Оголовка",
}
_ALL_PARAM_NAMES = set(p[0] for p in FAMILY_PARAMS)

# Префикс, по которому определяем «наши» параметры
_FP_PREFIX = "FP_"


def _get_params_for_family(family_name):
    """Возвращает set имён параметров, нужных данному семейству."""
    name_upper = family_name.upper()
    if "ПЛИТКА" in name_upper or "ВЕНТ" in name_upper or "РЕШЕТКА" in name_upper:
        return _TILE_PARAMS
    if "ЛОНЖЕРОН" in name_upper:
        return _LONGERON_PARAMS
    if "СТОЙК" in name_upper:
        return _SUPPORT_PARAMS
    return _ALL_PARAM_NAMES


def _storage_to_param_type(st):
    """StorageType → ForgeTypeId (Revit 2025+) или ParameterType (старые)."""
    # Специальный случай: Yes/No
    if st == "YesNo":
        try:
            from Autodesk.Revit.DB import SpecTypeId  # type: ignore

            return SpecTypeId.Boolean.YesNo
        except Exception:
            pass
        try:
            from Autodesk.Revit.DB import ParameterType  # type: ignore

            return ParameterType.YesNo
        except Exception:
            pass
        return None
    try:
        from Autodesk.Revit.DB import SpecTypeId  # type: ignore

        if st == StorageType.Double:
            return SpecTypeId.Length
        elif st == StorageType.Integer:
            return SpecTypeId.Int.Integer
        elif st == StorageType.String:
            return SpecTypeId.String.Text
    except Exception:
        pass
    try:
        from Autodesk.Revit.DB import ParameterType  # type: ignore

        if st == StorageType.Double:
            return ParameterType.Length
        elif st == StorageType.Integer:
            return ParameterType.Integer
        elif st == StorageType.String:
            return ParameterType.Text
    except Exception:
        pass
    return None


def _safe_name(obj):
    """Безопасно получает .Name из объекта Revit. Возвращает None при любой ошибке."""
    if obj is None:
        return None
    try:
        return obj.Name
    except Exception:
        return None


SP_GROUP_NAME = "Фальшпол"


def _ensure_sp_file():
    """Проверяет что файл общих параметров задан и существует."""
    sp_path = app.SharedParametersFilename
    if not sp_path:
        raise Exception(tr("fam_sp_not_set"))
    if not os.path.exists(sp_path):
        raise Exception(tr("fam_sp_not_found", path=sp_path))
    return sp_path


def _get_or_create_definitions():
    """Находит или создаёт определения в файле общих параметров.

    Все операции через Revit API: группы и определения создаются
    штатными методами Groups.Create / Definitions.Create.

    Возвращает dict {name: (ExternalDefinition, is_instance)}.
    """
    sp_file = app.OpenSharedParameterFile()
    if not sp_file:
        raise Exception(tr("fam_sp_open_failed"))

    group = None
    for g in sp_file.Groups:
        if _safe_name(g) == SP_GROUP_NAME:
            group = g
            break

    if group is None:
        group = sp_file.Groups.Create(SP_GROUP_NAME)

    existing_defs = {}
    for d in group.Definitions:
        dn = _safe_name(d)
        if dn:
            existing_defs[dn] = d

    # Создаём недостающие определения через API
    for name, st, desc, is_instance in FAMILY_PARAMS:
        if name not in existing_defs:
            param_type = _storage_to_param_type(st)
            opts = ExternalDefinitionCreationOptions(name, param_type)
            opts.Description = desc
            existing_defs[name] = group.Definitions.Create(opts)

    # Собираем результат
    result = {}
    for name, st, desc, is_instance in FAMILY_PARAMS:
        if name in existing_defs:
            result[name] = (existing_defs[name], is_instance)
        else:
            raise Exception(tr("fam_def_not_found", name=name))

    return result


def _load_fresh_definitions():
    """Перечитывает определения из файла общих параметров (свежие ссылки).

    Вызывается перед обработкой каждого семейства чтобы избежать
    ситуации со stale-ссылками после LoadFamily/Close.
    """
    sp_file = app.OpenSharedParameterFile()
    if not sp_file:
        raise Exception(tr("fam_sp_open_failed"))
    group = None
    for g in sp_file.Groups:
        if _safe_name(g) == SP_GROUP_NAME:
            group = g
            break
    if group is None:
        raise Exception(tr("fam_group_not_found", name=SP_GROUP_NAME))

    existing_defs = {}
    for d in group.Definitions:
        if d and d.Name:
            existing_defs[d.Name] = d

    result = {}
    for name, st, desc, is_instance in FAMILY_PARAMS:
        if name in existing_defs:
            result[name] = (existing_defs[name], is_instance)
    return result


def _collect_fp_families():
    """Собирает загруженные семейства с префиксом «ФП_»."""
    families = []
    for fam in FilteredElementCollector(doc).OfClass(Family):
        if fam.Name and fam.Name.startswith("ФП_") and fam.IsEditable:
            families.append(fam)
    return families


def _get_group_type_id():
    """Возвращает группу параметров для FamilyManager.AddParameter.

    Revit 2025+: GroupTypeId.Data
    Revit старше: BuiltInParameterGroup.PG_DATA
    """
    try:
        from Autodesk.Revit.DB import GroupTypeId  # type: ignore

        return GroupTypeId.Data
    except Exception:
        pass
    try:
        from Autodesk.Revit.DB import BuiltInParameterGroup  # type: ignore

        return BuiltInParameterGroup.PG_DATA
    except Exception:
        pass
    return None


def _find_obsolete_params(fam_doc, allowed_names):
    """Находит FP_-параметры, которых нет в актуальном наборе (для информации).

    Не удаляет — только возвращает список имён.
    """
    fam_mgr = fam_doc.FamilyManager
    obsolete = []
    for p in fam_mgr.GetParameters():
        if not p or not p.Definition or not p.Definition.Name:
            continue
        name = p.Definition.Name
        if name.startswith(_FP_PREFIX) and name not in allowed_names:
            obsolete.append(name)
    return obsolete


def _remove_deprecated_params(fam_doc, allowed_names):
    """Удаляет из семейства все FP_-параметры, которых нет в allowed_names.

    Находит все параметры с префиксом FP_ и удаляет те,
    которые не входят в актуальный набор для этого типа семейства.
    Возвращает (removed_list, error_list).
    """
    fam_mgr = fam_doc.FamilyManager

    to_remove = []
    for p in fam_mgr.GetParameters():
        if not p or not p.Definition or not p.Definition.Name:
            continue
        name = p.Definition.Name
        if name.startswith(_FP_PREFIX) and name not in allowed_names:
            to_remove.append(p)

    if not to_remove:
        return [], []

    removed = []
    errors = []
    t = Transaction(fam_doc, "Remove deprecated FP params")
    t.Start()
    try:
        for p in to_remove:
            name = _safe_name(p.Definition) or "?"
            try:
                fam_mgr.RemoveParameter(p)
                removed.append(name)
            except Exception as ex:
                errors.append("{}: {}".format(name, str(ex)))
        t.Commit()
    except Exception:
        if t.HasStarted():
            t.RollBack()
        raise
    return removed, errors


def _add_params_to_family_doc(fam_doc, ext_defs, allowed_names=None):
    """Добавляет отсутствующие параметры в документ семейства.

    Если параметр уже есть (по имени) — пропускает.
    Возвращает (added_list, error_list).
    """
    fam_mgr = fam_doc.FamilyManager

    existing = set()
    for p in fam_mgr.GetParameters():
        if p and p.Definition and p.Definition.Name:
            existing.add(p.Definition.Name)

    to_add = []
    for name, (ext_def, is_instance) in ext_defs.items():
        if allowed_names and name not in allowed_names:
            continue
        if name in existing:
            continue
        to_add.append((name, ext_def, is_instance))

    if not to_add:
        return [], []

    added = []
    errors = []
    group_id = _get_group_type_id()

    t = Transaction(fam_doc, "Add FP params")
    t.Start()
    try:
        for name, ext_def, is_instance in to_add:
            try:
                if group_id is not None:
                    fam_mgr.AddParameter(
                        ext_def,
                        group_id,
                        is_instance,
                    )
                else:
                    fam_mgr.AddParameter(
                        ext_def,
                        is_instance,
                    )
                added.append(name)
            except Exception as ex:
                errors.append("{}: {}".format(name, str(ex)))
        t.Commit()
    except Exception:
        if t.HasStarted():
            t.RollBack()
        raise

    return added, errors


def _process_family(family):
    """Открывает семейство, добавляет параметры, перезагружает.

    Перечитывает определения из ФОП перед каждым семейством,
    чтобы ссылки были гарантированно свежими.
    """
    allowed = _get_params_for_family(family.Name)

    fam_doc = doc.EditFamily(family)
    if not fam_doc:
        return 0, 0, [tr("fam_open_failed", name=family.Name)]

    try:
        ext_defs = _load_fresh_definitions()
        added, errors = _add_params_to_family_doc(fam_doc, ext_defs, allowed)

        # Находим устаревшие (не удаляем — могут использоваться в геометрии)
        obsolete = _find_obsolete_params(fam_doc, allowed)
        if obsolete:
            errors.append(tr("fam_obsolete", names=", ".join(sorted(obsolete))))

        if added:
            fam_doc.LoadFamily(doc)

        fam_doc.Close(False)
        return len(added), 0, errors

    except Exception as ex:
        try:
            fam_doc.Close(False)
        except Exception:
            pass
        return 0, 0, [str(ex)]


def _run_in_family_editor():
    """Режим: мы уже в редакторе семейства — добавляем параметры в текущий doc."""
    fam_name = ""
    try:
        fam_name = doc.Title or ""
    except Exception:
        pass
    allowed = _get_params_for_family(fam_name) if fam_name else _ALL_PARAM_NAMES

    ext_defs = _load_fresh_definitions()

    added, errors = _add_params_to_family_doc(doc, ext_defs, allowed)

    # Находим устаревшие (не удаляем — могут использоваться в геометрии)
    obsolete = _find_obsolete_params(doc, allowed)

    if not added and not obsolete and not errors:
        forms.alert(tr("fam_all_ok"), title=TITLE)
        return

    report = []
    if obsolete:
        report.append(tr("fam_obsolete_header"))
        for n in sorted(obsolete):
            report.append("  - {}".format(n))
    if added:
        report.append(tr("fam_added", count=len(added)))
        for n in sorted(added):
            report.append("  + {}".format(n))
    if errors:
        report.append(tr("clean_errors_header"))
        for e in errors:
            report.append("  " + e)
    forms.alert("\n".join(report), title=TITLE)


def _run_in_project():
    """Режим: мы в проекте — обрабатываем загруженные ФП_-семейства."""
    families = _collect_fp_families()
    if not families:
        forms.alert(
            tr("fam_no_families"),
            title=TITLE,
        )
        return

    fam_info = []
    for f in families:
        params = _get_params_for_family(f.Name)
        fam_info.append(tr("fam_params_info", name=f.Name, count=len(params)))
    msg = tr("fam_found", count=len(families)) + "\n\n" + "\n".join(sorted(fam_info))
    confirm = forms.alert(
        msg + "\n\n" + tr("fam_confirm_add"),
        title=TITLE,
        yes=True,
        no=True,
    )
    if not confirm:
        return

    total_added = 0
    report_lines = []

    for fam in families:
        count_add, count_rem, errs = _process_family(fam)
        total_added += count_add
        if count_add > 0:
            report_lines.append(tr("fam_added_to", name=fam.Name, count=count_add))
        if errs:
            for e in errs:
                report_lines.append("  {} — {}".format(fam.Name, e))

    if total_added == 0 and not report_lines:
        summary = tr("fam_all_present")
    else:
        parts = []
        if total_added:
            parts.append(tr("fam_added", count=total_added))
        if report_lines:
            parts.append("\n".join(report_lines))
        summary = "\n\n".join(parts)

    forms.alert(summary, title=TITLE)


# ── Основной блок ────────────────────────────────────────
try:
    _ensure_sp_file()
    # Создаём определения в ФОП через Revit API
    _get_or_create_definitions()

    if doc.IsFamilyDocument:
        _run_in_family_editor()
    else:
        _run_in_project()

except Exception as ex:
    import traceback

    if str(ex) != "cancel":
        forms.alert(
            tr("error_fmt", error="{}\n\n{}".format(str(ex), traceback.format_exc())),
            title=TITLE,
        )

# -*- coding: utf-8 -*-
"""Параметры семейств — добавляет RF_-параметры в загруженные RF-семейства.

Открывает каждое семейство с префиксом «RF_», добавляет недостающие
общие параметры через FamilyManager и перезагружает семейство в проект.

Каждому семейству добавляются только релевантные параметры:
  RF_Tile / RF_Vent_Grill  → параметры плитки
  RF_Stringer              → параметры стрингера
  RF_Support               → параметры стойки
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
from floor_utils import (  # type: ignore
    get_storage_type_id,
    safe_get_name,
)
from pyrevit import forms  # type: ignore
from revit_context import get_doc  # type: ignore

doc = None
app = None
TITLE = tr("fam_title")

# ── Все параметры (имя, StorageType, описание, is_instance) ──
FAMILY_PARAMS = [
    # Instance
    ("RF_Column", StorageType.Integer, "Колонка в сетке", True),
    ("RF_Row", StorageType.Integer, "Ряд в сетке", True),
    ("RF_Mark", StorageType.String, "Марка элемента ФП", True),
    ("RF_Tile_Type", StorageType.String, "Тип плитки (Полная/Подрезка/Сложная)", True),
    (
        "RF_Tile_Size_X",
        StorageType.Double,
        "Базовый размер плитки X = шаг сетки (ft)",
        True,
    ),
    (
        "RF_Tile_Size_Y",
        StorageType.Double,
        "Базовый размер плитки Y = шаг сетки (ft)",
        True,
    ),
    ("RF_Cut_X", StorageType.Double, "Размер подрезки X (ft)", True),
    ("RF_Cut_Y", StorageType.Double, "Размер подрезки Y (ft)", True),
    ("RF_Void1_X", StorageType.Double, "Вырез ширина", True),
    ("RF_Void1_Y", StorageType.Double, "Вырез высота", True),
    (
        "RF_Void1_OX",
        StorageType.Double,
        "Отступ выреза от левого края плитки",
        True,
    ),
    (
        "RF_Void1_OY",
        StorageType.Double,
        "Отступ выреза от нижнего края плитки",
        True,
    ),
    ("RF_Void2_X", StorageType.Double, "Вырез 2 ширина", True),
    ("RF_Void2_Y", StorageType.Double, "Вырез 2 высота", True),
    (
        "RF_Void2_OX",
        StorageType.Double,
        "Отступ выреза 2 от левого края плитки",
        True,
    ),
    (
        "RF_Void2_OY",
        StorageType.Double,
        "Отступ выреза 2 от нижнего края плитки",
        True,
    ),
    ("RF_Void3_X", StorageType.Double, "Вырез 3 ширина", True),
    ("RF_Void3_Y", StorageType.Double, "Вырез 3 высота", True),
    (
        "RF_Void3_OX",
        StorageType.Double,
        "Отступ выреза 3 от левого края плитки",
        True,
    ),
    (
        "RF_Void3_OY",
        StorageType.Double,
        "Отступ выреза 3 от нижнего края плитки",
        True,
    ),
    ("RF_Stringer_Type", StorageType.String, "Тип стрингера (Верхний/Нижний)", True),
    ("RF_Direction_Axis", StorageType.String, "Ось направления (X/Y)", True),
    ("RF_Support_Height", StorageType.Double, "Высота стойки (ft)", True),
    ("RF_Ventilated", StorageType.Integer, "Вентилируемая плитка (0/1)", True),
    # Type
    ("RF_Profile_Height", StorageType.Double, "Высота профиля (ft)", False),
    ("RF_Profile_Width", StorageType.Double, "Ширина профиля (ft)", False),
    ("RF_Thickness", StorageType.Double, "Толщина элемента (ft)", False),
    ("RF_Wall_Thickness", StorageType.Double, "Толщина стенки профиля (ft)", False),
    ("RF_Base_Size", StorageType.Double, "Размер опорной площадки (ft)", False),
    ("RF_Head_Size", StorageType.Double, "Размер оголовка стойки (ft)", False),
]

# ── Какие параметры нужны каждому типу семейства ──
_TILE_PARAMS = {
    "RF_Column",
    "RF_Row",
    "RF_Mark",
    "RF_Tile_Type",
    "RF_Tile_Size_X",
    "RF_Tile_Size_Y",
    "RF_Cut_X",
    "RF_Cut_Y",
    "RF_Void1_X",
    "RF_Void1_Y",
    "RF_Void1_OX",
    "RF_Void1_OY",
    "RF_Void2_X",
    "RF_Void2_Y",
    "RF_Void2_OX",
    "RF_Void2_OY",
    "RF_Void3_X",
    "RF_Void3_Y",
    "RF_Void3_OX",
    "RF_Void3_OY",
    "RF_Thickness",
    "RF_Ventilated",
}
_LONGERON_PARAMS = {
    "RF_Mark",
    "RF_Stringer_Type",
    "RF_Direction_Axis",
    "RF_Profile_Height",
    "RF_Profile_Width",
    "RF_Wall_Thickness",
}
_SUPPORT_PARAMS = {
    "RF_Column",
    "RF_Row",
    "RF_Mark",
    "RF_Support_Height",
    "RF_Base_Size",
    "RF_Head_Size",
}
_ALL_PARAM_NAMES = set(p[0] for p in FAMILY_PARAMS)

# Префикс, по которому определяем «наши» параметры
_RF_PREFIX = "RF_"


def _get_params_for_family(family_name):
    """Возвращает set имён параметров, нужных данному семейству."""
    name_upper = family_name.upper()
    if "TILE" in name_upper or "VENT" in name_upper or "GRILL" in name_upper:
        return _TILE_PARAMS
    if "STRINGER" in name_upper:
        return _LONGERON_PARAMS
    if "SUPPORT" in name_upper:
        return _SUPPORT_PARAMS
    return _ALL_PARAM_NAMES


# Алиасы на функции из utils для обратной совместимости
_storage_to_param_type = get_storage_type_id
_safe_name = safe_get_name

SP_GROUP_NAME = "RaisedFloor"


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

    Returns:
        dict: {name: (Definition, is_instance)} для всех FAMILY_PARAMS.

    Raises:
        Exception: Если файл общих параметров не открыт или группа не найдена.
    """
    # Закрываем и заново открываем файл для получения свежих данных
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


def _collect_rf_families():
    """Собирает загруженные семейства с префиксом 'RF_'."""
    families = []
    for fam in FilteredElementCollector(doc).OfClass(Family):
        if fam.Name and fam.Name.startswith("RF_") and fam.IsEditable:
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
    """Находит RF_ parameters, которых нет в актуальном наборе (для информации).

    Не удаляет — только возвращает список имён.
    """
    fam_mgr = fam_doc.FamilyManager
    obsolete = []
    for p in fam_mgr.GetParameters():
        if not p or not p.Definition or not p.Definition.Name:
            continue
        name = p.Definition.Name
        if name.startswith(_RF_PREFIX) and name not in allowed_names:
            obsolete.append(name)
    return obsolete


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

    t = Transaction(fam_doc, "Add RF params")
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

    Args:
        family: Revit Family object для обработки.

    Returns:
        tuple: (added_count, removed_count, error_list)
    """
    allowed = _get_params_for_family(family.Name)

    fam_doc = None
    try:
        fam_doc = doc.EditFamily(family)
        if not fam_doc:
            return 0, 0, [tr("fam_open_failed", name=family.Name)]

        ext_defs = _load_fresh_definitions()
        added, errors = _add_params_to_family_doc(fam_doc, ext_defs, allowed)

        # Находим устаревшие (не удаляем — могут использоваться в геометрии)
        obsolete = _find_obsolete_params(fam_doc, allowed)
        if obsolete:
            errors.append(tr("fam_obsolete", names=", ".join(sorted(obsolete))))

        # Перезагрузка семейства в проект с обработкой ошибок
        if added:
            try:
                # Сохраняем семейство перед загрузкой
                fam_doc.Save()
                load_result = fam_doc.LoadFamily(doc)
                if not load_result:
                    errors.append("{}: LoadFamily returned False".format(family.Name))
            except Exception as load_ex:
                errors.append(
                    "{}: LoadFamily failed - {}".format(family.Name, str(load_ex))
                )
                # Откат: удаляем только что добавленные параметры
                if added:
                    try:
                        _rollback_added_params(fam_doc, added)
                    except Exception as rollback_ex:
                        errors.append(
                            "{}: Rollback failed - {}".format(
                                family.Name, str(rollback_ex)
                            )
                        )

        fam_doc.Close(False)
        return len(added), 0, errors

    except Exception as ex:
        # Гарантируем закрытие документа семейства при любой ошибке
        if fam_doc:
            try:
                fam_doc.Close(False)
            except Exception:
                pass
        return 0, 0, [str(ex)]


def _rollback_added_params(fam_doc, param_names):
    """Откатывает добавленные параметры из семейства.

    Args:
        fam_doc: Revit Family document.
        param_names: Список имён параметров для удаления.
    """
    fam_mgr = fam_doc.FamilyManager
    params_to_remove = []

    for p in fam_mgr.GetParameters():
        if p and p.Definition and p.Definition.Name:
            if p.Definition.Name in param_names:
                params_to_remove.append(p)

    if params_to_remove:
        t = Transaction(fam_doc, "Rollback RF params")
        t.Start()
        try:
            for p in params_to_remove:
                try:
                    fam_mgr.RemoveParameter(p)
                except Exception:
                    pass  # Игнорируем ошибки отката
            t.Commit()
        except Exception:
            if t.HasStarted():
                t.RollBack()


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
    """Режим: мы в проекте — обрабатываем загруженные RF_-семейства."""
    families = _collect_rf_families()
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
    doc = get_doc()
    if not doc:
        raise Exception("No active document")
    app = doc.Application

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

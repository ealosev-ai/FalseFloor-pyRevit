# -*- coding: utf-8 -*-
"""Параметры семейств — добавляет RF_-параметры в загруженные RF-семейства.

Открывает каждое семейство с префиксом «RF_», добавляет недостающие
общие параметры через FamilyManager и перезагружает семейство в проект.

Каждому семейству добавляются только релевантные параметры:
  RF_Tile / RF_Vent_Grill  → параметры плитки
  RF_Stringer              → параметры стрингера
  RF_Support               → параметры стойки
"""

from Autodesk.Revit.DB import (  # type: ignore
    Family,
    FamilySource,
    FilteredElementCollector,
    IFamilyLoadOptions,
    StorageType,
    Transaction,
)
from floor_i18n import tr  # type: ignore
from rf_param_schema import (  # type: ignore
    RF_ALL_FAMILY_PARAM_NAMES,
    RF_STRINGER_FAMILY_PARAM_NAMES,
    RF_SUPPORT_FAMILY_PARAM_NAMES,
    RF_TILE_FAMILY_PARAM_NAMES,
    RFParams as P,
    collect_family_parameter_guid_mismatches,
    ensure_schema_definitions,
)
from rf_family_migration import migrate_family_doc  # type: ignore
from floor_utils import (  # type: ignore
    get_storage_type_id,
)
from pyrevit import forms, script  # type: ignore
from revit_context import get_doc  # type: ignore

doc = None
app = None
TITLE = tr("fam_title")

# ── Все параметры (имя, StorageType, описание, is_instance) ──
FAMILY_PARAMS = [
    # Instance
    (P.COLUMN, StorageType.Integer, "Колонка в сетке", True),
    (P.ROW, StorageType.Integer, "Ряд в сетке", True),
    (P.MARK, StorageType.String, "Марка элемента ФП", True),
    (P.TILE_TYPE, StorageType.String, "Тип плитки (Полная/Подрезка/Сложная)", True),
    (P.TILE_SIZE_X, StorageType.Double, "Базовый размер плитки X = шаг сетки (ft)", True),
    (P.TILE_SIZE_Y, StorageType.Double, "Базовый размер плитки Y = шаг сетки (ft)", True),
    (P.CUT_X, StorageType.Double, "Размер подрезки X (ft)", True),
    (P.CUT_Y, StorageType.Double, "Размер подрезки Y (ft)", True),
    (P.VOID1_X, StorageType.Double, "Вырез ширина", True),
    (P.VOID1_Y, StorageType.Double, "Вырез высота", True),
    (P.VOID1_OX, StorageType.Double, "Отступ выреза от левого края плитки", True),
    (P.VOID1_OY, StorageType.Double, "Отступ выреза от нижнего края плитки", True),
    (P.VOID2_X, StorageType.Double, "Вырез 2 ширина", True),
    (P.VOID2_Y, StorageType.Double, "Вырез 2 высота", True),
    (P.VOID2_OX, StorageType.Double, "Отступ выреза 2 от левого края плитки", True),
    (P.VOID2_OY, StorageType.Double, "Отступ выреза 2 от нижнего края плитки", True),
    (P.VOID3_X, StorageType.Double, "Вырез 3 ширина", True),
    (P.VOID3_Y, StorageType.Double, "Вырез 3 высота", True),
    (P.VOID3_OX, StorageType.Double, "Отступ выреза 3 от левого края плитки", True),
    (P.VOID3_OY, StorageType.Double, "Отступ выреза 3 от нижнего края плитки", True),
    (P.STRINGER_TYPE, StorageType.String, "Тип стрингера (Верхний/Нижний)", True),
    (P.DIRECTION_AXIS, StorageType.String, "Ось направления (X/Y)", True),
    (P.SUPPORT_HEIGHT, StorageType.Double, "Высота стойки (ft)", True),
    (P.VENTILATED, StorageType.Integer, "Вентилируемая плитка (0/1)", True),
    # Type
    (P.PROFILE_HEIGHT, StorageType.Double, "Высота профиля (ft)", False),
    (P.PROFILE_WIDTH, StorageType.Double, "Ширина профиля (ft)", False),
    (P.THICKNESS, StorageType.Double, "Толщина элемента (ft)", False),
    (P.WALL_THICKNESS, StorageType.Double, "Толщина стенки профиля (ft)", False),
    (P.BASE_SIZE, StorageType.Double, "Размер опорной площадки (ft)", False),
    (P.HEAD_SIZE, StorageType.Double, "Размер оголовка стойки (ft)", False),
]

# ── Какие параметры нужны каждому типу семейства ──
_TILE_PARAMS = set(RF_TILE_FAMILY_PARAM_NAMES)
_LONGERON_PARAMS = set(RF_STRINGER_FAMILY_PARAM_NAMES)
_SUPPORT_PARAMS = set(RF_SUPPORT_FAMILY_PARAM_NAMES)
_ALL_PARAM_NAMES = set(RF_ALL_FAMILY_PARAM_NAMES)

# Префикс, по которому определяем «наши» параметры
_RF_PREFIX = "RF_"


class _ReloadFamilyLoadOptions(IFamilyLoadOptions):
    """Reload edited family back into the source project without disk save."""

    def OnFamilyFound(self, familyInUse, overwriteParameterValues):
        overwriteParameterValues.Value = True
        return True

    def OnSharedFamilyFound(
        self, sharedFamily, familyInUse, source, overwriteParameterValues
    ):
        source.Value = FamilySource.Family
        overwriteParameterValues.Value = True
        return True


def _format_guid_mismatch_lines(mismatches):
    lines = []
    for name, actual_guid, expected_guid in mismatches:
        lines.append("  {}: {} != {}".format(name, actual_guid, expected_guid))
    return lines


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


def _load_fresh_definitions():
    """Load canonical shared definitions with fresh references.

    Called before each family to avoid stale references after LoadFamily/Close.
    """
    definition_specs = []
    for name, st, desc, is_instance in FAMILY_PARAMS:
        param_type = _storage_to_param_type(st)
        if param_type is None:
            raise Exception("Unsupported parameter type for '{}'".format(name))
        definition_specs.append(
            {
                "name": name,
                "description": desc,
                "param_type": param_type,
            }
        )

    existing_defs = ensure_schema_definitions(app, definition_specs)
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

        guid_mismatches = collect_family_parameter_guid_mismatches(fam_doc, allowed)
        migrated_count = 0
        if guid_mismatches:
            mig_result = migrate_family_doc(
                fam_doc,
                app,
                project_doc=None,
                save_family=False,
                family_name_hint=family.Name,
            )
            if mig_result["errors"]:
                errors = list(mig_result["errors"])
                fam_doc.Close(False)
                return 0, 0, errors
            migrated_count = len(mig_result.get("replaced", []))

        ext_defs = _load_fresh_definitions()
        added, errors = _add_params_to_family_doc(fam_doc, ext_defs, allowed)

        # Находим устаревшие (не удаляем — могут использоваться в геометрии)
        obsolete = _find_obsolete_params(fam_doc, allowed)
        if obsolete:
            errors.append(tr("fam_obsolete", names=", ".join(sorted(obsolete))))

        # Перезагрузка семейства в проект с обработкой ошибок
        if added or migrated_count:
            try:
                load_result = fam_doc.LoadFamily(doc, _ReloadFamilyLoadOptions())
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

    guid_mismatches = collect_family_parameter_guid_mismatches(doc, allowed)
    migrated = []
    mig_errors = []
    if guid_mismatches:
        confirm = forms.alert(
            "Обнаружены RF_ параметры с неканоническими GUID ({} шт.).\n"
            "Выполнить миграцию через ReplaceParameter?".format(
                len(guid_mismatches)
            ),
            title=TITLE,
            yes=True,
            no=True,
        )
        if confirm:
            mig_result = migrate_family_doc(
                doc,
                app,
                project_doc=None,
                save_family=False,
                family_name_hint=fam_name,
            )
            migrated = mig_result.get("replaced", [])
            mig_errors = mig_result.get("errors", [])

    ext_defs = _load_fresh_definitions()

    added, errors = _add_params_to_family_doc(doc, ext_defs, allowed)
    errors.extend(mig_errors)

    # Находим устаревшие (не удаляем — могут использоваться в геометрии)
    obsolete = _find_obsolete_params(doc, allowed)

    if not added and not obsolete and not errors and not migrated:
        forms.alert(tr("fam_all_ok"), title=TITLE)
        return

    output = script.get_output()
    output.set_title("RF Family Parameters")
    if migrated:
        output.print_md("### Migrated GUIDs: {}".format(len(migrated)))
        for name, old_g, new_g in migrated:
            output.print_md("- **{}**: `{}` → `{}`".format(name, old_g, new_g))
    if obsolete:
        output.print_md("### " + tr("fam_obsolete_header"))
        for n in sorted(obsolete):
            output.print_md("- {}".format(n))
    if added:
        output.print_md("### " + tr("fam_added", count=len(added)))
        for n in sorted(added):
            output.print_md("- + {}".format(n))
    if errors:
        output.print_md("### " + tr("clean_errors_header"))
        for e in errors:
            output.print_md("- {}".format(e))


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

# -*- coding: utf-8 -*-
"""Maintenance helpers for migrating RF family parameters to canonical GUIDs."""

import os

from Autodesk.Revit.DB import (  # type: ignore
    Family,
    FamilySource,
    FilteredElementCollector,
    IFamilyLoadOptions,
    StorageType,
    SubTransaction,
    Transaction,
)
from floor_utils import get_storage_type_id  # type: ignore
from rf_param_schema import (  # type: ignore
    collect_family_parameter_guid_mismatches,
    ensure_schema_definitions,
    use_canonical_shared_parameter_file,
)

TARGET_FAMILY_NAMES = ("RF_Tile", "RF_Stringer", "RF_Support")

FAMILY_PARAMS = [
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
    ("RF_Void1_OX", StorageType.Double, "Отступ выреза от левого края плитки", True),
    ("RF_Void1_OY", StorageType.Double, "Отступ выреза от нижнего края плитки", True),
    ("RF_Void2_X", StorageType.Double, "Вырез 2 ширина", True),
    ("RF_Void2_Y", StorageType.Double, "Вырез 2 высота", True),
    ("RF_Void2_OX", StorageType.Double, "Отступ выреза 2 от левого края плитки", True),
    ("RF_Void2_OY", StorageType.Double, "Отступ выреза 2 от нижнего края плитки", True),
    ("RF_Void3_X", StorageType.Double, "Вырез 3 ширина", True),
    ("RF_Void3_Y", StorageType.Double, "Вырез 3 высота", True),
    ("RF_Void3_OX", StorageType.Double, "Отступ выреза 3 от левого края плитки", True),
    ("RF_Void3_OY", StorageType.Double, "Отступ выреза 3 от нижнего края плитки", True),
    ("RF_Stringer_Type", StorageType.String, "Тип стрингера (Верхний/Нижний)", True),
    ("RF_Direction_Axis", StorageType.String, "Ось направления (X/Y)", True),
    ("RF_Support_Height", StorageType.Double, "Высота стойки (ft)", True),
    ("RF_Ventilated", StorageType.Integer, "Вентилируемая плитка (0/1)", True),
    ("RF_Profile_Height", StorageType.Double, "Высота профиля (ft)", False),
    ("RF_Profile_Width", StorageType.Double, "Ширина профиля (ft)", False),
    ("RF_Thickness", StorageType.Double, "Толщина элемента (ft)", False),
    ("RF_Wall_Thickness", StorageType.Double, "Толщина стенки профиля (ft)", False),
    ("RF_Base_Size", StorageType.Double, "Размер опорной площадки (ft)", False),
    ("RF_Head_Size", StorageType.Double, "Размер оголовка стойки (ft)", False),
]

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
_STRINGER_PARAMS = {
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


class ReloadFamilyLoadOptions(IFamilyLoadOptions):
    """Reload edited family back into the source project."""

    def OnFamilyFound(self, familyInUse, overwriteParameterValues):
        overwriteParameterValues.Value = True
        return True

    def OnSharedFamilyFound(
        self, sharedFamily, familyInUse, source, overwriteParameterValues
    ):
        source.Value = FamilySource.Family
        overwriteParameterValues.Value = True
        return True


def get_params_for_family(family_name):
    name_upper = (family_name or "").upper()
    if "TILE" in name_upper or "VENT" in name_upper or "GRILL" in name_upper:
        return set(_TILE_PARAMS)
    if "STRINGER" in name_upper:
        return set(_STRINGER_PARAMS)
    if "SUPPORT" in name_upper:
        return set(_SUPPORT_PARAMS)
    return set()


def _get_group_type_id():
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


def _load_canonical_defs(app):
    definition_specs = []
    instance_flags = {}
    for name, storage_type, description, is_instance in FAMILY_PARAMS:
        param_type = get_storage_type_id(storage_type)
        if param_type is None:
            raise Exception("Unsupported parameter type for '{}'".format(name))
        definition_specs.append(
            {"name": name, "description": description, "param_type": param_type}
        )
        instance_flags[name] = is_instance

    existing_defs = ensure_schema_definitions(app, definition_specs)
    result = {}
    for name, storage_type, description, is_instance in FAMILY_PARAMS:
        result[name] = (existing_defs[name], instance_flags[name])
    return result


def _collect_family_param_by_name(fam_doc):
    result = {}
    for param in fam_doc.FamilyManager.GetParameters():
        try:
            definition = param.Definition
            name = definition.Name if definition else None
        except Exception:
            name = None
        if name:
            result[name] = param
    return result


def _add_missing_params_no_tx(fam_doc, ext_defs, allowed_names, added, errors):
    fam_mgr = fam_doc.FamilyManager
    existing_names = set(_collect_family_param_by_name(fam_doc))
    group_id = _get_group_type_id()
    if group_id is None:
        errors.append("No compatible parameter group id for AddParameter")
        return

    for name in sorted(allowed_names):
        if name in existing_names:
            continue
        ext_def, is_instance = ext_defs[name]
        subtx = SubTransaction(fam_doc)
        try:
            subtx.Start()
            fam_mgr.AddParameter(ext_def, group_id, is_instance)
            subtx.Commit()
            added.append(name)
            existing_names.add(name)
        except Exception as ex:
            try:
                subtx.RollBack()
            except Exception:
                pass
            errors.append("Add missing '{}' failed: {}".format(name, str(ex)))


def _replace_mismatched_params_no_tx(
    fam_doc, ext_defs, allowed_names, replaced, errors, allow_destructive=False
):
    """Migrate parameters with wrong GUIDs to canonical GUIDs.

    Tries ReplaceParameter first (strategies A-D). If all fail:
    - allow_destructive=False (default): hard fail, parameter untouched
    - allow_destructive=True: fallback to Remove+Add with value backup
    """
    fam_mgr = fam_doc.FamilyManager
    group_id = _get_group_type_id()
    if group_id is None:
        errors.append("No compatible parameter group id for migration")
        return
    existing = _collect_family_param_by_name(fam_doc)
    mismatches = collect_family_parameter_guid_mismatches(fam_doc, allowed_names)

    for name, actual_guid, expected_guid in mismatches:
        current_param = existing.get(name)
        if current_param is None:
            errors.append(
                "Could not resolve FamilyParameter '{}' for migration".format(name)
            )
            continue
        ext_def, is_instance = ext_defs[name]

        # Try ReplaceParameter (safe path, preserves formulas/labels/geometry)
        subtx = SubTransaction(fam_doc)
        try:
            subtx.Start()
            success, strategy, err = _try_replace_parameter(
                fam_mgr, current_param, ext_def, group_id, is_instance
            )
            if success:
                subtx.Commit()
                replaced.append((name, actual_guid, expected_guid))
                continue
            else:
                subtx.RollBack()
        except Exception as ex:
            try:
                subtx.RollBack()
            except Exception:
                pass
            err = str(ex)

        # ReplaceParameter failed
        if not allow_destructive:
            errors.append(
                "{}: ReplaceParameter failed ({}). "
                "Use maintenance mode (allow_destructive) for Remove+Add fallback.".format(
                    name, err
                )
            )
            continue

        # Destructive fallback: Remove+Add with value backup
        storage_type, backed_up = _backup_family_param_values(fam_mgr, current_param)

        subtx = SubTransaction(fam_doc)
        try:
            subtx.Start()
            fam_mgr.RemoveParameter(current_param)
            new_param = fam_mgr.AddParameter(ext_def, group_id, is_instance)
            restore_failed = 0
            if backed_up and storage_type is not None:
                restored, restore_failed = _restore_family_param_values(
                    fam_mgr, new_param, storage_type, backed_up
                )
            subtx.Commit()
            existing.pop(name, None)
            try:
                new_name = new_param.Definition.Name
            except Exception:
                new_name = name
            existing[new_name] = new_param
            replaced.append((name, actual_guid, expected_guid))
            if restore_failed:
                errors.append(
                    "{}: Remove+Add succeeded but {} value(s) failed to restore".format(
                        name, restore_failed
                    )
                )
        except Exception as ex:
            try:
                subtx.RollBack()
            except Exception:
                pass
            errors.append("{}: Remove+Add fallback failed: {}".format(name, str(ex)))


def _try_replace_parameter(fam_mgr, old_param, ext_def, group_id, is_instance):
    """Try FamilyManager.ReplaceParameter using multiple pythonnet strategies.

    Returns (success, strategy_used, error_message).
    Does NOT fall back to Remove+Add — hard fail if all strategies fail.
    """
    strategies = []

    # Strategy A: direct call
    def _strategy_a():
        fam_mgr.ReplaceParameter(old_param, ext_def, group_id, is_instance)

    strategies.append(("direct_call", _strategy_a))

    # Strategy B: Overloads[] with explicit types
    def _strategy_b():
        from Autodesk.Revit.DB import ExternalDefinition, FamilyParameter  # type: ignore

        group_type = type(group_id)
        fam_mgr.ReplaceParameter.Overloads[
            FamilyParameter, ExternalDefinition, group_type, bool
        ](old_param, ext_def, group_id, is_instance)

    strategies.append(("Overloads[]", _strategy_b))

    # Strategy C: __overloads__[] (alternative pythonnet/IronPython syntax)
    def _strategy_c():
        from Autodesk.Revit.DB import ExternalDefinition, FamilyParameter  # type: ignore

        group_type = type(group_id)
        fam_mgr.ReplaceParameter.__overloads__[
            FamilyParameter, ExternalDefinition, group_type, bool
        ](old_param, ext_def, group_id, is_instance)

    strategies.append(("__overloads__[]", _strategy_c))

    # Strategy D: .NET Reflection
    def _strategy_d():
        import clr  # type: ignore
        from System import Array, Boolean, Object, Type  # type: ignore

        fm_type = clr.GetClrType(type(fam_mgr))
        param_types = Array[Type](
            [
                clr.GetClrType(type(old_param)),
                clr.GetClrType(type(ext_def)),
                clr.GetClrType(type(group_id)),
                clr.GetClrType(Boolean),
            ]
        )
        method = fm_type.GetMethod("ReplaceParameter", param_types)
        if method is None:
            raise Exception("ReplaceParameter method not found via reflection")
        args = Array[Object]([old_param, ext_def, group_id, is_instance])
        method.Invoke(fam_mgr, args)

    strategies.append(("reflection", _strategy_d))

    errors = []
    for name, fn in strategies:
        try:
            fn()
            return (True, name, "")
        except Exception as ex:
            errors.append("{}: {}".format(name, str(ex)))

    combined = "; ".join(errors)
    return (False, "", "All ReplaceParameter strategies failed: " + combined)


def _backup_family_param_values(fam_mgr, param):
    """Backup parameter values across all family types.

    Uses FamilyManager.CurrentType + param accessors to read values.
    Returns (storage_type, {FamilyType.Id.IntegerValue: value}).
    """
    values = {}
    try:
        storage_type = param.StorageType
    except Exception:
        return (None, values)

    original_type = fam_mgr.CurrentType
    for fam_type in fam_mgr.Types:
        try:
            fam_mgr.CurrentType = fam_type
        except Exception:
            continue

        key = fam_type.Id.IntegerValue
        try:
            if storage_type == StorageType.Double:
                values[key] = param.AsDouble()
            elif storage_type == StorageType.Integer:
                values[key] = param.AsInteger()
            elif storage_type == StorageType.String:
                values[key] = param.AsString()
            elif storage_type == StorageType.ElementId:
                values[key] = param.AsElementId()
        except Exception:
            pass

    try:
        if original_type is not None:
            fam_mgr.CurrentType = original_type
    except Exception:
        pass

    return (storage_type, values)


def _restore_family_param_values(fam_mgr, param, storage_type, values):
    """Restore parameter values across family types from backup.

    Returns (restored_count, failed_count).
    """
    if not values:
        return (0, 0)

    restored = 0
    failed = 0
    original_type = fam_mgr.CurrentType
    for fam_type in fam_mgr.Types:
        key = fam_type.Id.IntegerValue
        if key not in values:
            continue
        try:
            fam_mgr.CurrentType = fam_type
        except Exception:
            failed += 1
            continue
        value = values[key]
        if value is None:
            continue
        try:
            fam_mgr.Set(param, value)
            restored += 1
        except Exception:
            failed += 1

    try:
        if original_type is not None:
            fam_mgr.CurrentType = original_type
    except Exception:
        pass

    return (restored, failed)


def _make_temp_family_param_name(existing, name):
    index = 1
    while True:
        candidate = "__RF_TMP_{0}_{1}".format(name, index)
        if candidate not in existing:
            return candidate
        index += 1


def _find_obsolete_params(fam_doc, allowed_names):
    obsolete = []
    for param in fam_doc.FamilyManager.GetParameters():
        try:
            definition = param.Definition
            name = definition.Name if definition else None
        except Exception:
            name = None
        if name and name.startswith("RF_") and name not in allowed_names:
            obsolete.append(name)
    return sorted(obsolete)


def migrate_family_doc(
    fam_doc,
    app,
    project_doc=None,
    save_family=False,
    family_name_hint=None,
    dry_run=False,
    allow_destructive=False,
):
    """Migrate one family document to canonical shared-parameter GUIDs.

    Args:
        dry_run: If True, only report mismatches without making changes.
        allow_destructive: If True, allow Remove+Add fallback when
            ReplaceParameter fails. Maintenance-only, not for normal UI.
    """
    family_name = family_name_hint or ""
    try:
        if not family_name:
            family_name = fam_doc.OwnerFamily.Name
    except Exception:
        pass

    if not family_name:
        family_name = os.path.splitext(getattr(fam_doc, "Title", "") or "")[0]

    allowed_names = get_params_for_family(family_name)
    result = {
        "family_name": family_name or "<unknown>",
        "path": getattr(fam_doc, "PathName", "") or "",
        "replaced": [],
        "added": [],
        "obsolete": [],
        "saved": False,
        "reloaded": False,
        "errors": [],
        "dry_run": dry_run,
    }

    if not allowed_names:
        result["errors"].append("Family is not in migration target set")
        return result

    # Dry-run: report mismatches and missing params without transaction
    # NOTE: do NOT call _load_canonical_defs() here — it creates definitions
    # in the shared parameter file via ensure_schema_definitions().
    if dry_run:
        mismatches = collect_family_parameter_guid_mismatches(fam_doc, allowed_names)
        result["replaced"] = [
            (name, actual, expected) for name, actual, expected in mismatches
        ]
        existing_names = set(_collect_family_param_by_name(fam_doc))
        canonical_names = {name for name, _, _, _ in FAMILY_PARAMS}
        for name in sorted(allowed_names):
            if name not in existing_names and name in canonical_names:
                result["added"].append(name)
        result["obsolete"] = _find_obsolete_params(fam_doc, allowed_names)
        return result

    with use_canonical_shared_parameter_file(app):
        ext_defs = _load_canonical_defs(app)

        replace_errors = []
        add_errors = []

        replace_tx = Transaction(fam_doc, "Migrate RF family parameter GUIDs")
        try:
            replace_tx.Start()
            _replace_mismatched_params_no_tx(
                fam_doc,
                ext_defs,
                allowed_names,
                result["replaced"],
                replace_errors,
                allow_destructive=allow_destructive,
            )
            if replace_errors:
                replace_tx.RollBack()
                result["replaced"] = []
            else:
                replace_tx.Commit()
        except Exception as ex:
            if replace_tx.HasStarted():
                replace_tx.RollBack()
            result["replaced"] = []
            replace_errors.append(str(ex))

        add_tx = Transaction(fam_doc, "Add missing RF family parameters")
        try:
            add_tx.Start()
            _add_missing_params_no_tx(
                fam_doc, ext_defs, allowed_names, result["added"], add_errors
            )
            if add_errors:
                add_tx.RollBack()
                result["added"] = []
            else:
                add_tx.Commit()
        except Exception as ex:
            if add_tx.HasStarted():
                add_tx.RollBack()
            result["added"] = []
            add_errors.append(str(ex))

        result["errors"].extend(replace_errors)
        result["errors"].extend(add_errors)
    result["obsolete"] = _find_obsolete_params(fam_doc, allowed_names)

    changed = bool(result["replaced"] or result["added"])

    if changed and save_family:
        try:
            fam_doc.Save()
            result["saved"] = True
        except Exception as ex:
            result["errors"].append("Save failed: {}".format(str(ex)))

    if changed and project_doc is not None:
        try:
            load_result = fam_doc.LoadFamily(project_doc, ReloadFamilyLoadOptions())
            if load_result:
                result["reloaded"] = True
            else:
                result["errors"].append("LoadFamily returned False")
        except Exception as ex:
            result["errors"].append("Reload failed: {}".format(str(ex)))

    return result


def collect_loaded_target_families(project_doc):
    """Collect loaded editable target families from the active project."""
    families = []
    for family in FilteredElementCollector(project_doc).OfClass(Family):
        try:
            name = family.Name
        except Exception:
            name = None
        if not name or name not in TARGET_FAMILY_NAMES:
            continue
        try:
            is_editable = family.IsEditable
        except Exception:
            is_editable = False
        if is_editable:
            families.append(family)
    return families

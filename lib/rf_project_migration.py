# -*- coding: utf-8 -*-
"""Project-level GUID migration for RF shared parameters.

Migrates project parameter bindings from legacy GUIDs to canonical GUIDs
defined in rf_param_schema.RF_PARAMETER_GUIDS.
"""

from Autodesk.Revit.DB import (  # type: ignore
    FilteredElementCollector,
    SharedParameterElement,
    StorageType,
    Transaction,
    TransactionGroup,
)
from floor_utils import get_full_parameter_binding_info  # type: ignore
from rf_param_schema import (  # type: ignore
    collect_project_parameter_guid_mismatches,
    ensure_schema_definitions,
)

# Marker returned by collect_project_parameter_guid_mismatches for
# parameters that exist as bound but have no resolvable SharedParameterElement.
_UNRESOLVABLE_MARKER = "<not-shared-or-unresolved>"


def _find_shared_param_element_by_guid(doc, guid_text):
    """Find SharedParameterElement by GuidValue, not by name.

    Returns the element or None.
    """
    normalized = guid_text.strip().lower()
    for spe in FilteredElementCollector(doc).OfClass(SharedParameterElement):
        try:
            spe_guid = str(spe.GuidValue).strip().lower()
        except Exception:
            continue
        if spe_guid == normalized:
            return spe
    return None


def _read_param_value(param):
    """Read a parameter value based on its StorageType. Returns (value, ok)."""
    if param is None:
        return (None, False)
    try:
        if param.IsReadOnly:
            return (None, False)
        if not param.HasValue:
            return (None, False)
    except Exception:
        pass

    try:
        st = param.StorageType
    except Exception:
        return (None, False)

    try:
        if st == StorageType.Double:
            return (param.AsDouble(), True)
        elif st == StorageType.Integer:
            return (param.AsInteger(), True)
        elif st == StorageType.String:
            return (param.AsString(), True)
        elif st == StorageType.ElementId:
            return (param.AsElementId(), True)
    except Exception:
        pass
    return (None, False)


def _write_param_value(param, value, storage_type):
    """Write a value to a parameter. Returns True on success."""
    if param is None or value is None:
        return False
    try:
        if param.IsReadOnly:
            return False
    except Exception:
        pass
    try:
        param.Set(value)
        return True
    except Exception:
        return False


def _get_param_on_element(elem, name, guid_text=None):
    """Get parameter on element using multiple fallback strategies.

    Primary: LookupParameter(name)
    Fallback 1: elem.get_Parameter(definition) — not used here (no def)
    Fallback 2: lookup by GUID
    """
    # Primary path
    try:
        p = elem.LookupParameter(name)
        if p is not None:
            return p
    except Exception:
        pass

    # Fallback: by GUID
    if guid_text:
        try:
            from System import Guid  # type: ignore

            guid_obj = Guid(guid_text)
            p = elem.get_Parameter(guid_obj)
            if p is not None:
                return p
        except Exception:
            pass

    return None


def _get_storage_type_from_spe(spe):
    """Get StorageType from SharedParameterElement's internal definition.

    This is authoritative — the SPE always knows its own storage type.
    Returns StorageType or None.
    """
    if spe is None:
        return None
    try:
        internal_def = spe.GetDefinition()
        if internal_def is not None:
            return internal_def.StorageType
    except Exception:
        pass
    return None


def _backup_element_values(doc, binding_info, name, actual_guid, spe=None):
    """Backup parameter values from all elements that have this parameter.

    Returns (storage_type, {element_id_int: value}, total_count).
    """
    values = {}
    is_instance = binding_info.get("is_instance", True)

    # Determine storage type: SPE internal definition is authoritative
    storage_type = _get_storage_type_from_spe(spe)

    # Fallback: try binding definition
    if storage_type is None:
        definition = binding_info.get("definition")
        if definition:
            try:
                storage_type = definition.StorageType
            except Exception:
                pass

    # Collect elements from all bound categories
    categories = binding_info.get("categories", [])
    elements = []
    for cat in categories:
        try:
            collector = FilteredElementCollector(doc).OfCategory(cat)
            if is_instance:
                collector = collector.WhereElementIsNotElementType()
            else:
                collector = collector.WhereElementIsElementType()
            elements.extend(collector.ToElements())
        except Exception:
            pass

    for elem in elements:
        param = _get_param_on_element(elem, name, actual_guid)
        if param is None:
            continue
        value, ok = _read_param_value(param)
        if ok and value is not None:
            try:
                values[elem.Id.IntegerValue] = value
            except Exception:
                pass

        # Detect storage type from first successful read
        if storage_type is None and ok:
            try:
                storage_type = param.StorageType
            except Exception:
                pass

    return (storage_type, values, len(elements))


def _restore_element_values(doc, name, new_guid, storage_type, values):
    """Restore parameter values to elements after rebinding.

    Returns (restored_count, failed_count).
    """
    restored = 0
    failed = 0

    for elem_id_int, value in values.items():
        try:
            from Autodesk.Revit.DB import ElementId  # type: ignore

            elem = doc.GetElement(ElementId(elem_id_int))
        except Exception:
            failed += 1
            continue

        if elem is None:
            failed += 1
            continue

        param = _get_param_on_element(elem, name, new_guid)
        if param is None:
            failed += 1
            continue

        if _write_param_value(param, value, storage_type):
            restored += 1
        else:
            failed += 1

    return (restored, failed)


def migrate_project_parameter_guids(doc, app, dry_run=False):
    """Migrate project shared parameter GUIDs to canonical values.

    Args:
        doc: Revit project document.
        app: Revit Application.
        dry_run: If True, only report what would change.

    Returns:
        dict with keys: migrated, skipped, values_backed_up, values_restored,
        values_failed, errors, dry_run.
    """
    result = {
        "migrated": [],
        "skipped": [],
        "values_backed_up": 0,
        "values_restored": 0,
        "values_failed": 0,
        "errors": [],
        "dry_run": dry_run,
    }

    # Get full binding info for snapshot
    binding_info_map = get_full_parameter_binding_info(doc)

    # Detect mismatches
    bound_names = set(binding_info_map.keys())
    rf_bound_names = {n for n in bound_names if n.startswith("RF_")}
    mismatches = collect_project_parameter_guid_mismatches(
        doc, allowed_names=rf_bound_names, bound_names=rf_bound_names
    )

    if not mismatches:
        return result

    # Phase 1: Analyze and backup
    migration_plan = []  # [(name, actual_guid, expected_guid, binding_info, spe, storage_type, values)]
    for name, actual_guid, expected_guid in mismatches:
        # Skip unresolvable
        if actual_guid == _UNRESOLVABLE_MARKER:
            result["skipped"].append((name, "unresolvable-guid"))
            continue

        info = binding_info_map.get(name)
        if not info:
            result["skipped"].append((name, "no-binding-info"))
            continue

        # Find SharedParameterElement by GUID (not by name)
        spe = _find_shared_param_element_by_guid(doc, actual_guid)
        if spe is None:
            result["skipped"].append((name, "SharedParameterElement-not-found"))
            continue

        if dry_run:
            # For dry-run, just count what would be affected
            storage_type, values, elem_count = _backup_element_values(
                doc, info, name, actual_guid, spe=spe
            )
            result["migrated"].append((name, actual_guid, expected_guid))
            result["values_backed_up"] += len(values)
            continue

        # Backup values
        storage_type, values, elem_count = _backup_element_values(
            doc, info, name, actual_guid, spe=spe
        )
        result["values_backed_up"] += len(values)

        migration_plan.append(
            (name, actual_guid, expected_guid, info, spe, storage_type, values)
        )

    if dry_run:
        return result

    if not migration_plan:
        return result

    # Phase 2-4: Execute migration in TransactionGroup for single Undo
    tg = TransactionGroup(doc, "Migrate RF project parameter GUIDs")
    try:
        tg.Start()

        # Step 1: Remove all old bindings and SharedParameterElements
        t1 = Transaction(doc, "Remove legacy RF parameter bindings")
        t1.Start()
        try:
            bm = doc.ParameterBindings
            for name, actual_guid, expected_guid, info, spe, st, vals in migration_plan:
                try:
                    bm.Remove(info["definition"])
                except Exception as ex:
                    result["errors"].append(
                        "{}: Remove binding failed: {}".format(name, str(ex))
                    )
                try:
                    doc.Delete(spe.Id)
                except Exception as ex:
                    result["errors"].append(
                        "{}: Delete SharedParameterElement failed: {}".format(
                            name, str(ex)
                        )
                    )

            if result["errors"]:
                t1.RollBack()
                tg.RollBack()
                return result
            t1.Commit()
        except Exception as ex:
            if t1.HasStarted():
                t1.RollBack()
            tg.RollBack()
            result["errors"].append("Remove phase failed: {}".format(str(ex)))
            return result

        # Step 2: Create new bindings with canonical GUIDs
        # Build definition specs for all params being migrated
        from floor_utils import (  # type: ignore
            create_category_set,
            get_storage_type_id,
        )

        definition_specs = []
        for name, actual_guid, expected_guid, info, spe, st, vals in migration_plan:
            if st is None:
                # Try one more time from SPE
                st = _get_storage_type_from_spe(spe)
            if st is None:
                result["errors"].append(
                    "{}: Cannot determine StorageType — skipping".format(name)
                )
                continue
            param_type = get_storage_type_id(st)
            if param_type is None:
                result["errors"].append(
                    "{}: Cannot determine param_type".format(name)
                )
                continue
            definition_specs.append(
                {"name": name, "description": "", "param_type": param_type}
            )

        if result["errors"]:
            tg.RollBack()
            return result

        canonical_defs = ensure_schema_definitions(app, definition_specs)

        t2 = Transaction(doc, "Create canonical RF parameter bindings")
        t2.Start()
        try:
            from Autodesk.Revit.DB import (  # type: ignore
                InstanceBinding,
                TypeBinding,
            )

            bm = doc.ParameterBindings
            for name, actual_guid, expected_guid, info, spe, st, vals in migration_plan:
                new_def = canonical_defs.get(name)
                if new_def is None:
                    result["errors"].append(
                        "{}: Canonical definition not found".format(name)
                    )
                    continue

                # Rebuild category set from original binding
                categories = info.get("categories", [])
                cat_set = create_category_set(doc, categories)

                if info.get("is_instance", True):
                    binding = InstanceBinding(cat_set)
                else:
                    binding = TypeBinding(cat_set)

                group_id = info.get("group_id")
                try:
                    if group_id is not None:
                        ok = bm.Insert(new_def, binding, group_id)
                    else:
                        ok = bm.Insert(new_def, binding)
                except Exception as ex:
                    result["errors"].append(
                        "{}: Insert failed: {}".format(name, str(ex))
                    )
                    continue

                if ok:
                    result["migrated"].append((name, actual_guid, expected_guid))
                else:
                    result["errors"].append(
                        "{}: Insert returned False".format(name)
                    )

            if result["errors"]:
                t2.RollBack()
                tg.RollBack()
                return result
            t2.Commit()
        except Exception as ex:
            if t2.HasStarted():
                t2.RollBack()
            tg.RollBack()
            result["errors"].append("Create phase failed: {}".format(str(ex)))
            return result

        # Step 3: Restore values
        t3 = Transaction(doc, "Restore RF parameter values")
        try:
            t3.Start()
            for name, actual_guid, expected_guid, info, spe, st, vals in migration_plan:
                if not vals:
                    continue
                new_guid = expected_guid
                restored, failed = _restore_element_values(
                    doc, name, new_guid, st, vals
                )
                result["values_restored"] += restored
                result["values_failed"] += failed

            t3.Commit()
        except Exception as ex:
            if t3.HasStarted():
                t3.RollBack()
            result["errors"].append("Restore phase failed: {}".format(str(ex)))
            tg.RollBack()
            return result

        tg.Assimilate()

    except Exception as ex:
        try:
            tg.RollBack()
        except Exception:
            pass
        result["errors"].append("TransactionGroup failed: {}".format(str(ex)))

    return result

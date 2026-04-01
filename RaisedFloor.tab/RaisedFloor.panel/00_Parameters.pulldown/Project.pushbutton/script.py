# -*- coding: utf-8 -*-
"""00 Параметры — добавляет все RF_ parameters в проект.

Проверяет наличие параметров на нужных категориях и добавляет
недостающие через ProjectParameter API.
Параметры создаются с описаниями для понятности.
"""

from Autodesk.Revit.DB import (  # type: ignore
    BuiltInCategory,
    InstanceBinding,
    StorageType,
    TypeBinding,
)
from floor_i18n import tr  # type: ignore
from rf_param_schema import (  # type: ignore
    RFParams as P,
    collect_project_parameter_guid_mismatches,
    ensure_schema_definitions,
)
from rf_project_migration import migrate_project_parameter_guids  # type: ignore
from floor_utils import (  # type: ignore
    create_category_set,
    get_data_group_type_id,
    get_existing_parameter_bindings,
    get_storage_type_id,
)
from pyrevit import forms, revit, script  # type: ignore
from revit_context import get_doc  # type: ignore

doc = None
app = None
TITLE = tr("proj_title")

# ── Определения параметров ───────────────────────────────
# (имя, StorageType, описание, категории_builtin, instance=True/type=False)

_CATS_FLOORS = [BuiltInCategory.OST_Floors]

PARAM_DEFS = [
    # ── Параметры перекрытия (instance) ──
    (P.STEP_X, StorageType.Double, "Шаг сетки по X (ft)", _CATS_FLOORS, True),
    (P.STEP_Y, StorageType.Double, "Шаг сетки по Y (ft)", _CATS_FLOORS, True),
    (P.BASE_X, StorageType.Double, "Базовая точка X (ft)", _CATS_FLOORS, True),
    (P.BASE_Y, StorageType.Double, "Базовая точка Y (ft)", _CATS_FLOORS, True),
    (P.BASE_Z, StorageType.Double, "Базовая точка Z (ft)", _CATS_FLOORS, True),
    (P.OFFSET_X, StorageType.Double, "Оптимальное смещение X (ft)", _CATS_FLOORS, True),
    (P.OFFSET_Y, StorageType.Double, "Оптимальное смещение Y (ft)", _CATS_FLOORS, True),
    (
        P.FLOOR_HEIGHT,
        StorageType.Double,
        "Полная высота фальшпола (ft)",
        _CATS_FLOORS,
        True,
    ),
    (P.TILE_THICKNESS, StorageType.Double, "Толщина плитки (ft)", _CATS_FLOORS, True),
    (P.GEN_STATUS, StorageType.String, "Статус генерации", _CATS_FLOORS, True),
    (
        P.CONTOUR_LINES_ID,
        StorageType.String,
        "ID линий контура (;)",
        _CATS_FLOORS,
        True,
    ),
    (P.GRID_LINES_ID, StorageType.String, "ID линий сетки (;)", _CATS_FLOORS, True),
    (P.BASE_MARKER_ID, StorageType.String, "ID маркера базы", _CATS_FLOORS, True),
    (P.TILES_ID, StorageType.String, "ID размещённых плиток (;)", _CATS_FLOORS, True),
    (
        P.STRINGERS_TOP_ID,
        StorageType.String,
        "ID верхних лонжеронов (;)",
        _CATS_FLOORS,
        True,
    ),
    (
        P.STRINGERS_BOTTOM_ID,
        StorageType.String,
        "ID нижних лонжеронов (;)",
        _CATS_FLOORS,
        True,
    ),
    (
        P.REINF_ZONES_JSON,
        StorageType.String,
        "JSON зон усиления лонжеронов",
        _CATS_FLOORS,
        True,
    ),
    (P.SUPPORTS_ID, StorageType.String, "ID стоек (;)", _CATS_FLOORS, True),
    (P.BOTTOM_MODE, StorageType.String, "Режим размещения нижних", _CATS_FLOORS, True),
    (
        P.BOTTOM_STEP,
        StorageType.String,
        "Шаг нижних лонжеронов (мм)",
        _CATS_FLOORS,
        True,
    ),
    (
        P.MAX_STRINGER_LEN,
        StorageType.String,
        "Макс. длина лонжерона (мм)",
        _CATS_FLOORS,
        True,
    ),
    (
        P.TOP_DIRECTION,
        StorageType.String,
        "Направление верхних (X/Y)",
        _CATS_FLOORS,
        True,
    ),
]

# Алиасы на функции из utils для обратной совместимости
_storage_to_param_type = get_storage_type_id
_get_data_group_id = get_data_group_type_id
_get_existing_bindings = get_existing_parameter_bindings
_make_cat_set = create_category_set

# Набор имён Double-параметров для определения «неправильного типа»
_DOUBLE_PARAM_NAMES = set(
    name for name, st, _, _, _ in PARAM_DEFS if st == StorageType.Double
)

# Все актуальные имена параметров
_ACTUAL_PARAM_NAMES = set(name for name, _, _, _, _ in PARAM_DEFS)

# Префикс «наших» параметров
_RF_PREFIX = "RF_"


def _offer_guid_migration(mismatches, doc, app):
    """Offer to migrate project parameter GUIDs instead of blocking."""
    lines = [
        "Обнаружены RF_ параметры проекта с неканоническими GUID ({} шт.).".format(
            len(mismatches)
        ),
        "",
        "ВНИМАНИЕ: миграция GUID может сломать:",
        "  - Спецификации (schedules), ссылающиеся на эти параметры",
        "  - Фильтры видов (view filters)",
        "  - Теги (tags)",
        "",
        "Рекомендуется делать только на копии проекта.",
        "",
        "Мигрировать GUID?",
    ]
    confirm = forms.alert("\n".join(lines), title=TITLE, yes=True, no=True)
    if not confirm:
        raise Exception("cancel")

    result = migrate_project_parameter_guids(doc, app)

    output = script.get_output()
    output.set_title("RF Project GUID Migration")

    if result["migrated"]:
        output.print_md("### Migrated: {}".format(len(result["migrated"])))
        for name, old_g, new_g in result["migrated"]:
            output.print_md("- **{}**: `{}` → `{}`".format(name, old_g, new_g))

    if result["skipped"]:
        output.print_md("### Skipped: {}".format(len(result["skipped"])))
        for name, reason in result["skipped"]:
            output.print_md("- **{}**: {}".format(name, reason))

    if result["values_backed_up"] or result["values_restored"]:
        output.print_md(
            "### Values: backed up {}, restored {}, failed {}".format(
                result["values_backed_up"],
                result["values_restored"],
                result["values_failed"],
            )
        )

    if result["errors"]:
        output.print_md("### Errors")
        for e in result["errors"]:
            output.print_md("- {}".format(e))
        raise Exception("cancel")

    if not result["migrated"] and not result["errors"]:
        output.print_md("No parameters needed migration.")


try:
    doc = get_doc()
    if not doc:
        raise Exception(tr("proj_temp_file_failed"))
    app = doc.Application

    existing = _get_existing_bindings(doc)
    guid_mismatches = collect_project_parameter_guid_mismatches(
        doc,
        allowed_names=_ACTUAL_PARAM_NAMES,
        bound_names=existing.keys(),
    )
    if guid_mismatches:
        _offer_guid_migration(guid_mismatches, doc, app)
        # Refresh bindings — migration changed definitions and GUIDs
        existing = _get_existing_bindings(doc)

    # ── Определяем устаревшие RF_ parameters (есть в проекте, нет в PARAM_DEFS) ──
    obsolete = []
    for name in existing:
        if name.startswith(_RF_PREFIX) and name not in _ACTUAL_PARAM_NAMES:
            obsolete.append(name)

    # ── Определяем, какие параметры нужно пересоздать (неправильный тип) ──
    wrong_type = []
    for name, defn in existing.items():
        if name not in _DOUBLE_PARAM_NAMES:
            continue
        # Проверяем тип: если параметр Double но создан как Number (не Length)
        try:
            from Autodesk.Revit.DB import SpecTypeId  # type: ignore

            # Revit 2022+: GetDataType() возвращает ForgeTypeId
            dt = defn.GetDataType()
            if dt != SpecTypeId.Length:
                wrong_type.append(name)
        except Exception:
            try:
                from Autodesk.Revit.DB import ParameterType as PT  # type: ignore

                if defn.ParameterType != PT.Length:
                    wrong_type.append(name)
            except Exception:
                pass

    needed = []
    already = []
    for name, st, desc, cats, is_instance in PARAM_DEFS:
        if name in existing and name not in wrong_type:
            already.append(name)
        else:
            needed.append((name, st, desc, cats, is_instance))

    has_actions = bool(needed or wrong_type)

    if not has_actions:
        msg = [tr("proj_all_bound", count=len(PARAM_DEFS))]
        if obsolete:
            msg.extend(
                [
                    "",
                    tr("proj_legacy_found", count=len(obsolete)),
                    "  {}".format(", ".join(sorted(obsolete))),
                ]
            )
            msg.append("")
            msg.append(tr("proj_legacy_hint"))
        forms.alert("\n".join(msg), title=TITLE)
    else:
        parts = []
        if already:
            parts.append(tr("proj_already_ok", count=len(already)))
        if obsolete:
            parts.append(
                tr(
                    "proj_legacy_not_removed",
                    count=len(obsolete),
                    names=", ".join(sorted(obsolete)),
                )
            )
        if wrong_type:
            parts.append(
                tr(
                    "proj_wrong_type_list",
                    count=len(wrong_type),
                    names=", ".join(sorted(wrong_type)),
                )
            )
        new_count = len(needed) - len(wrong_type)
        if new_count > 0:
            parts.append(tr("proj_new_count", count=new_count))

        confirm = forms.alert(
            "\n".join(parts) + "\n\n" + tr("proj_confirm_update"),
            title=TITLE,
            yes=True,
            no=True,
        )
        if not confirm:
            raise Exception("cancel")

        # ── Шаг 1: удалить привязки параметров с неправильным типом ──
        if wrong_type:
            with revit.Transaction("Remove RF_ wrong-type params"):
                bm = doc.ParameterBindings
                for name in wrong_type:
                    defn = existing.get(name)
                    if defn:
                        bm.Remove(defn)

        definition_specs = []
        for name, st, desc, cats, is_instance in needed:
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

        definitions_by_name = ensure_schema_definitions(app, definition_specs)

        added = []
        errors = []
        data_group_id = _get_data_group_id()

        with revit.Transaction("Add RF_ parameters"):
            for name, st, desc, cats, is_instance in needed:
                try:
                    defn = definitions_by_name[name]
                    cat_set = _make_cat_set(doc, cats)

                    if is_instance:
                        binding = InstanceBinding(cat_set)
                    else:
                        binding = TypeBinding(cat_set)

                    if data_group_id is not None:
                        ok = doc.ParameterBindings.Insert(defn, binding, data_group_id)
                    else:
                        ok = doc.ParameterBindings.Insert(defn, binding)
                    if ok:
                        added.append(name)
                    else:
                        errors.append("{}: Insert failed".format(name))
                except Exception as ex:
                    errors.append("{}: {}".format(name, str(ex)))

        report = []
        if wrong_type:
            report.append(
                tr("proj_recreated", count=len([n for n in wrong_type if n in added]))
            )
        new_added = [n for n in added if n not in wrong_type]
        if new_added:
            report.append(tr("proj_new_added", count=len(new_added)))
        if obsolete:
            report.append(tr("proj_legacy_untouched", count=len(obsolete)))
        if errors:
            report.append("")
            report.append(tr("proj_errors_header", count=len(errors)))
            for e in errors:
                report.append("  " + e)
        if not report:
            report.append(tr("proj_done"))
        forms.alert("\n".join(report), title=TITLE)

except Exception as ex:
    if str(ex) != "cancel":
        forms.alert(tr("error_inline_fmt", error=str(ex)), title=TITLE)

# -*- coding: utf-8 -*-
"""00 Параметры — добавляет все RF_ parameters в проект.

Проверяет наличие параметров на нужных категориях и добавляет
недостающие через ProjectParameter API.
Параметры создаются с описаниями для понятности.
"""

import os

from Autodesk.Revit.DB import (  # type: ignore
    BuiltInCategory,
    ExternalDefinitionCreationOptions,
    InstanceBinding,
    StorageType,
    TypeBinding,
)
from floor_i18n import tr  # type: ignore
from floor_utils import (  # type: ignore
    create_category_set,
    get_data_group_type_id,
    get_existing_parameter_bindings,
    get_storage_type_id,
)
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
app = doc.Application
TITLE = tr("proj_title")

# ── Определения параметров ───────────────────────────────
# (имя, StorageType, описание, категории_builtin, instance=True/type=False)

_CATS_FLOORS = [BuiltInCategory.OST_Floors]

PARAM_DEFS = [
    # ── Параметры перекрытия (instance) ──
    ("RF_Step_X", StorageType.Double, "Шаг сетки по X (ft)", _CATS_FLOORS, True),
    ("RF_Step_Y", StorageType.Double, "Шаг сетки по Y (ft)", _CATS_FLOORS, True),
    ("RF_Base_X", StorageType.Double, "Базовая точка X (ft)", _CATS_FLOORS, True),
    ("RF_Base_Y", StorageType.Double, "Базовая точка Y (ft)", _CATS_FLOORS, True),
    ("RF_Base_Z", StorageType.Double, "Базовая точка Z (ft)", _CATS_FLOORS, True),
    (
        "RF_Offset_X",
        StorageType.Double,
        "Оптимальное смещение X (ft)",
        _CATS_FLOORS,
        True,
    ),
    (
        "RF_Offset_Y",
        StorageType.Double,
        "Оптимальное смещение Y (ft)",
        _CATS_FLOORS,
        True,
    ),
    (
        "RF_Floor_Height",
        StorageType.Double,
        "Полная высота фальшпола (ft)",
        _CATS_FLOORS,
        True,
    ),
    (
        "RF_Tile_Thickness",
        StorageType.Double,
        "Толщина плитки (ft)",
        _CATS_FLOORS,
        True,
    ),
    ("RF_Gen_Status", StorageType.String, "Статус генерации", _CATS_FLOORS, True),
    (
        "RF_Contour_Lines_ID",
        StorageType.String,
        "ID линий контура (;)",
        _CATS_FLOORS,
        True,
    ),
    ("RF_Grid_Lines_ID", StorageType.String, "ID линий сетки (;)", _CATS_FLOORS, True),
    ("RF_Base_Marker_ID", StorageType.String, "ID маркера базы", _CATS_FLOORS, True),
    (
        "RF_Tiles_ID",
        StorageType.String,
        "ID размещённых плиток (;)",
        _CATS_FLOORS,
        True,
    ),
    (
        "RF_Stringers_Top_ID",
        StorageType.String,
        "ID верхних лонжеронов (;)",
        _CATS_FLOORS,
        True,
    ),
    (
        "RF_Stringers_Bottom_ID",
        StorageType.String,
        "ID нижних лонжеронов (;)",
        _CATS_FLOORS,
        True,
    ),
    (
        "RF_Reinf_Zones_JSON",
        StorageType.String,
        "JSON зон усиления лонжеронов",
        _CATS_FLOORS,
        True,
    ),
    ("RF_Supports_ID", StorageType.String, "ID стоек (;)", _CATS_FLOORS, True),
    (
        "RF_Bottom_Mode",
        StorageType.String,
        "Режим размещения нижних",
        _CATS_FLOORS,
        True,
    ),
    (
        "RF_Bottom_Step",
        StorageType.String,
        "Шаг нижних лонжеронов (мм)",
        _CATS_FLOORS,
        True,
    ),
    (
        "RF_Max_Stringer_Len",
        StorageType.String,
        "Макс. длина лонжерона (мм)",
        _CATS_FLOORS,
        True,
    ),
    (
        "RF_Top_Direction",
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


try:
    existing = _get_existing_bindings()

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

        # ── Шаг 2: создать определения во ВРЕМЕННОМ файле ──
        # Revit кеширует DefinitionFile — старые определения (NUMBER)
        # остаются в памяти даже после правки текста. Единственный
        # способ получить чистые определения с LENGTH — создать их
        # в новом файле, который Revit ещё не кешировал.
        original_sp_path = app.SharedParametersFilename or ""
        temp_path = os.path.join(
            os.environ.get("TEMP", os.path.expanduser("~")),
            "RF_TempParams_{}.txt".format(os.getpid()),
        )
        try:
            # Записать минимальный заголовок
            with open(temp_path, "w") as f:
                f.write("# This is a Revit shared parameter file.\n")
                f.write("# Do not edit manually.\n")
                f.write("*META\tVERSION\tMINVERSION\n")
                f.write("META\t2\t1\n")
                f.write("*GROUP\tID\tNAME\n")
                f.write(
                    "*PARAM\tGUID\tNAME\tDATATYPE\tDATACATEGORY\tGROUP\tVISIBLE\tDESCRIPTION\tUSERMODIFIABLE\n"
                )

            app.SharedParametersFilename = temp_path
            tmp_sp_file = app.OpenSharedParameterFile()
            if not tmp_sp_file:
                raise Exception(tr("proj_temp_file_failed"))

            GROUP_NAME = "RaisedFloor"
            dg = tmp_sp_file.Groups.Create(GROUP_NAME)

            added = []
            errors = []
            data_group_id = _get_data_group_id()

            with revit.Transaction("Add RF_ parameters"):
                for name, st, desc, cats, is_instance in needed:
                    try:
                        param_type = _storage_to_param_type(st)
                        opts = ExternalDefinitionCreationOptions(name, param_type)
                        opts.Description = desc
                        defn = dg.Definitions.Create(opts)

                        cat_set = _make_cat_set(cats)

                        if is_instance:
                            binding = InstanceBinding(cat_set)
                        else:
                            binding = TypeBinding(cat_set)

                        if data_group_id is not None:
                            ok = doc.ParameterBindings.Insert(
                                defn, binding, data_group_id
                            )
                        else:
                            ok = doc.ParameterBindings.Insert(defn, binding)
                        if ok:
                            added.append(name)
                        else:
                            errors.append("{}: Insert failed".format(name))
                    except Exception as ex:
                        errors.append("{}: {}".format(name, str(ex)))

        finally:
            # Восстановить оригинальный файл
            if original_sp_path:
                app.SharedParametersFilename = original_sp_path
            # Удалить временный файл
            try:
                os.remove(temp_path)
            except Exception:
                pass

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

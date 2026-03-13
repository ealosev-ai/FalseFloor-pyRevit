# -*- coding: utf-8 -*-
"""00 Параметры — добавляет все FP_-параметры в проект.

Проверяет наличие параметров на нужных категориях и добавляет
недостающие через ProjectParameter API.
Параметры создаются с описаниями для понятности.
"""

import os

from Autodesk.Revit.DB import (  # type: ignore
    BuiltInCategory,
    BuiltInParameterGroup,
    Category,
    CategorySet,
    ExternalDefinitionCreationOptions,
    InstanceBinding,
    StorageType,
    TypeBinding,
)
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
app = doc.Application
TITLE = "00 Параметры ФП"

# ── Определения параметров ───────────────────────────────
# (имя, StorageType, описание, категории_builtin, instance=True/type=False)

_CATS_FLOORS = [BuiltInCategory.OST_Floors]
_CATS_GENERIC = [BuiltInCategory.OST_GenericModel]
_CATS_FLOORS_GENERIC = [BuiltInCategory.OST_Floors, BuiltInCategory.OST_GenericModel]

PARAM_DEFS = [
    # ── Параметры перекрытия (instance) ──
    ("FP_Шаг_X", StorageType.Double, "Шаг сетки по X (ft)", _CATS_FLOORS, True),
    ("FP_Шаг_Y", StorageType.Double, "Шаг сетки по Y (ft)", _CATS_FLOORS, True),
    ("FP_База_X", StorageType.Double, "Базовая точка X (ft)", _CATS_FLOORS, True),
    ("FP_База_Y", StorageType.Double, "Базовая точка Y (ft)", _CATS_FLOORS, True),
    ("FP_База_Z", StorageType.Double, "Базовая точка Z (ft)", _CATS_FLOORS, True),
    (
        "FP_Смещение_X",
        StorageType.Double,
        "Оптимальное смещение X (ft)",
        _CATS_FLOORS,
        True,
    ),
    (
        "FP_Смещение_Y",
        StorageType.Double,
        "Оптимальное смещение Y (ft)",
        _CATS_FLOORS,
        True,
    ),
    (
        "FP_Высота_Фальшпола",
        StorageType.Double,
        "Полная высота фальшпола (ft)",
        _CATS_FLOORS,
        True,
    ),
    (
        "FP_Толщина_Плитки",
        StorageType.Double,
        "Толщина плитки (ft)",
        _CATS_FLOORS,
        True,
    ),
    ("FP_Статус_Генерации", StorageType.String, "Статус генерации", _CATS_FLOORS, True),
    (
        "FP_ID_ЛинийКонтура",
        StorageType.String,
        "ID линий контура (;)",
        _CATS_FLOORS,
        True,
    ),
    ("FP_ID_ЛинийСетки", StorageType.String, "ID линий сетки (;)", _CATS_FLOORS, True),
    ("FP_ID_МаркераБазы", StorageType.String, "ID маркера базы", _CATS_FLOORS, True),
    (
        "FP_ID_Плиток",
        StorageType.String,
        "ID размещённых плиток (;)",
        _CATS_FLOORS,
        True,
    ),
    (
        "FP_ID_Лонжеронов_Верх",
        StorageType.String,
        "ID верхних лонжеронов (;)",
        _CATS_FLOORS,
        True,
    ),
    (
        "FP_ID_Лонжеронов_Низ",
        StorageType.String,
        "ID нижних лонжеронов (;)",
        _CATS_FLOORS,
        True,
    ),
    ("FP_ID_Стоек", StorageType.String, "ID стоек (;)", _CATS_FLOORS, True),
    (
        "FP_Режим_Нижних",
        StorageType.String,
        "Режим размещения нижних",
        _CATS_FLOORS,
        True,
    ),
    (
        "FP_Шаг_Нижних",
        StorageType.String,
        "Шаг нижних лонжеронов (мм)",
        _CATS_FLOORS,
        True,
    ),
    (
        "FP_Макс_Длина_Лонжерона",
        StorageType.String,
        "Макс. длина лонжерона (мм)",
        _CATS_FLOORS,
        True,
    ),
    (
        "FP_Направление_Верхних",
        StorageType.String,
        "Направление верхних (X/Y)",
        _CATS_FLOORS,
        True,
    ),
    # ── Параметры экземпляра (Generic Model — плитки, лонжероны, стойки) ──
    ("FP_Колонка", StorageType.Integer, "Колонка в сетке", _CATS_GENERIC, True),
    ("FP_Ряд", StorageType.Integer, "Ряд в сетке", _CATS_GENERIC, True),
    ("FP_Марка", StorageType.String, "Марка элемента ФП", _CATS_GENERIC, True),
    (
        "FP_Тип_Плитки",
        StorageType.String,
        "Тип плитки (Полная/Подрезка/Сложная)",
        _CATS_GENERIC,
        True,
    ),
    (
        "FP_Подрезка_X",
        StorageType.Double,
        "Размер подрезки X (ft)",
        _CATS_GENERIC,
        True,
    ),
    (
        "FP_Подрезка_Y",
        StorageType.Double,
        "Размер подрезки Y (ft)",
        _CATS_GENERIC,
        True,
    ),
    (
        "FP_Тип_Лонжерона",
        StorageType.String,
        "Тип лонжерона (Верхний/Нижний)",
        _CATS_GENERIC,
        True,
    ),
    (
        "FP_Ось_Направления",
        StorageType.String,
        "Ось направления (X/Y)",
        _CATS_GENERIC,
        True,
    ),
    ("FP_Высота_Стойки", StorageType.Double, "Высота стойки (ft)", _CATS_GENERIC, True),
    (
        "FP_Вентилируемая",
        StorageType.Integer,
        "Вентилируемая плитка (0/1)",
        _CATS_GENERIC,
        True,
    ),
    (
        "FP_Вырез_Видимость",
        "YesNo",
        "Видимость выреза (Да/Нет)",
        _CATS_GENERIC,
        True,
    ),
    # ── Параметры типоразмера (Generic Model — type) ──
    (
        "FP_Высота_Профиля",
        StorageType.Double,
        "Высота профиля (ft)",
        _CATS_GENERIC,
        False,
    ),
    (
        "FP_Ширина_Профиля",
        StorageType.Double,
        "Ширина профиля (ft)",
        _CATS_GENERIC,
        False,
    ),
    ("FP_Толщина", StorageType.Double, "Толщина элемента (ft)", _CATS_GENERIC, False),
    (
        "FP_Толщина_Стенки",
        StorageType.Double,
        "Толщина стенки профиля (ft)",
        _CATS_GENERIC,
        False,
    ),
    (
        "FP_Размер_Опоры",
        StorageType.Double,
        "Размер опорной площадки (ft)",
        _CATS_GENERIC,
        False,
    ),
    (
        "FP_Размер_Оголовка",
        StorageType.Double,
        "Размер оголовка стойки (ft)",
        _CATS_GENERIC,
        False,
    ),
]


def _storage_to_param_type(st):
    """Тип хранения → ForgeTypeId / ParameterType."""
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
        # Revit 2025+: SpecTypeId
        from Autodesk.Revit.DB import SpecTypeId  # type: ignore

        if st == StorageType.Double:
            return SpecTypeId.Length
        elif st == StorageType.Integer:
            return SpecTypeId.Int.Integer
        elif st == StorageType.String:
            return SpecTypeId.String.Text
    except Exception:
        pass

    # Revit < 2025: ParameterType enum
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


def _get_existing_bindings():
    """Собирает словарь {имя: definition} для привязанных к проекту параметров."""
    existing = {}
    bm = doc.ParameterBindings
    it = bm.ForwardIterator()
    it.Reset()
    while it.MoveNext():
        defn = it.Key
        if defn and defn.Name:
            existing[defn.Name] = defn
    return existing


def _make_cat_set(built_in_cats):
    """Создаёт CategorySet из списка BuiltInCategory."""
    cs = CategorySet()
    for bic in built_in_cats:
        cat = Category.GetCategory(doc, bic)
        if cat:
            cs.Insert(cat)
    return cs


# Набор имён Double-параметров для определения «неправильного типа»
_DOUBLE_PARAM_NAMES = set(
    name for name, st, _, _, _ in PARAM_DEFS if st == StorageType.Double
)

# Все актуальные имена параметров
_ACTUAL_PARAM_NAMES = set(name for name, _, _, _, _ in PARAM_DEFS)

# Префикс «наших» параметров
_FP_PREFIX = "FP_"


try:
    existing = _get_existing_bindings()

    # ── Определяем устаревшие FP_-параметры (есть в проекте, нет в PARAM_DEFS) ──
    obsolete = []
    for name in existing:
        if name.startswith(_FP_PREFIX) and name not in _ACTUAL_PARAM_NAMES:
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

    if not needed and not wrong_type and not obsolete:
        forms.alert(
            "Все {} параметров уже есть в проекте с правильным типом.".format(
                len(PARAM_DEFS)
            ),
            title=TITLE,
        )
    else:
        parts = []
        if already:
            parts.append("Уже есть (ОК): {}".format(len(already)))
        if obsolete:
            parts.append(
                "Устаревшие (будут удалены): {}\n  {}".format(
                    len(obsolete), ", ".join(sorted(obsolete))
                )
            )
        if wrong_type:
            parts.append(
                "С неправильным типом (Number→Length): {}\n  {}".format(
                    len(wrong_type), ", ".join(sorted(wrong_type))
                )
            )
        new_count = len(needed) - len(wrong_type)
        if new_count > 0:
            parts.append("Новых: {}".format(new_count))

        confirm = forms.alert(
            "\n".join(parts) + "\n\nПродолжить?",
            title=TITLE,
            yes=True,
            no=True,
        )
        if not confirm:
            raise Exception("Отмена")

        # ── Шаг 0: удалить устаревшие FP_-параметры ──
        removed_obsolete = []
        if obsolete:
            with revit.Transaction("Удалить устаревшие FP_ параметры"):
                bm = doc.ParameterBindings
                for name in obsolete:
                    defn = existing.get(name)
                    if defn and bm.Remove(defn):
                        removed_obsolete.append(name)

        # ── Шаг 1: удалить привязки параметров с неправильным типом ──
        if wrong_type:
            with revit.Transaction("Удалить FP_ параметры (неправильный тип)"):
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
            "FP_TempParams_{}.txt".format(os.getpid()),
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
                raise Exception("Не удалось создать временный файл параметров")

            GROUP_NAME = "Фальшпол"
            dg = tmp_sp_file.Groups.Create(GROUP_NAME)

            added = []
            errors = []

            with revit.Transaction("Добавить FP_ параметры"):
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

                        ok = doc.ParameterBindings.Insert(
                            defn, binding, BuiltInParameterGroup.PG_DATA
                        )
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
        if removed_obsolete:
            report.append(
                "Удалено устаревших: {} ({})".format(
                    len(removed_obsolete), ", ".join(sorted(removed_obsolete))
                )
            )
        if wrong_type:
            report.append(
                "Пересоздано (Number→Length): {}".format(
                    len([n for n in wrong_type if n in added])
                )
            )
        new_added = [n for n in added if n not in wrong_type]
        if new_added:
            report.append("Новых добавлено: {}".format(len(new_added)))
        if errors:
            report.append("")
            report.append("Ошибки ({}):".format(len(errors)))
            for e in errors:
                report.append("  " + e)
        if not report:
            report.append("Готово.")
        forms.alert("\n".join(report), title=TITLE)

except Exception as ex:
    if str(ex) != "Отмена":
        forms.alert("Ошибка: {}".format(str(ex)), title=TITLE)

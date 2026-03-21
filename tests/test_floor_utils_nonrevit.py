"""Non-Revit tests for floor_utils using lightweight Autodesk stubs."""

import importlib
import os
import sys
from types import ModuleType

import pytest

pytestmark = [pytest.mark.unit]


def _install_db_stubs():
    if "Autodesk.Revit.DB" in sys.modules:
        return

    db = ModuleType("Autodesk.Revit.DB")

    class _StorageType:
        Double = "Double"
        Integer = "Integer"
        String = "String"

    class _GroupTypeId:
        Data = "GroupType.Data"

    class _BuiltInParameterGroup:
        PG_DATA = "PG_DATA"

    class _SpecTypeId:
        Length = "Spec.Length"

        class Int:
            Integer = "Spec.Int.Integer"

        class String:
            Text = "Spec.String.Text"

        class Boolean:
            YesNo = "Spec.Boolean.YesNo"

    class _ParameterType:
        Length = "Param.Length"
        Integer = "Param.Integer"
        Text = "Param.Text"
        YesNo = "Param.YesNo"

    class _CategorySet:
        def __init__(self):
            self.items = []

        def Insert(self, category):
            self.items.append(category)

    class _Category:
        @staticmethod
        def GetCategory(_doc, bic):
            return "CAT:{}".format(bic)

    class _Document:
        pass

    class _ExternalDefinitionCreationOptions:
        pass

    db.StorageType = _StorageType
    db.GroupTypeId = _GroupTypeId
    db.BuiltInParameterGroup = _BuiltInParameterGroup
    db.SpecTypeId = _SpecTypeId
    db.ParameterType = _ParameterType
    db.Category = _Category
    db.CategorySet = _CategorySet
    db.Document = _Document
    db.ExternalDefinitionCreationOptions = _ExternalDefinitionCreationOptions

    autodesk = ModuleType("Autodesk")
    revit = ModuleType("Autodesk.Revit")
    autodesk.Revit = revit
    revit.DB = db

    sys.modules["Autodesk"] = autodesk
    sys.modules["Autodesk.Revit"] = revit
    sys.modules["Autodesk.Revit.DB"] = db


def _import_floor_utils():
    _install_db_stubs()

    lib_dir = os.path.join(os.path.dirname(__file__), "..", "lib")
    lib_dir = os.path.normpath(lib_dir)
    if lib_dir not in sys.path:
        sys.path.insert(0, lib_dir)

    if "floor_utils" in sys.modules:
        return importlib.reload(sys.modules["floor_utils"])
    return importlib.import_module("floor_utils")


def test_get_storage_type_id_for_yesno_and_scalars():
    mod = _import_floor_utils()
    assert mod.get_storage_type_id("YesNo") == "Spec.Boolean.YesNo"
    assert mod.get_storage_type_id(mod.StorageType.Double) == "Spec.Length"
    assert mod.get_storage_type_id(mod.StorageType.Integer) == "Spec.Int.Integer"
    assert mod.get_storage_type_id(mod.StorageType.String) == "Spec.String.Text"


def test_get_storage_type_id_falls_back_to_parameter_type(monkeypatch):
    mod = _import_floor_utils()
    monkeypatch.setattr(mod, "SpecTypeId", None)
    assert mod.get_storage_type_id("YesNo") == "Param.YesNo"
    assert mod.get_storage_type_id(mod.StorageType.Double) == "Param.Length"


def test_get_storage_type_id_returns_none_for_unknown(monkeypatch):
    mod = _import_floor_utils()
    monkeypatch.setattr(mod, "SpecTypeId", None)
    monkeypatch.setattr(mod, "ParameterType", None)
    assert mod.get_storage_type_id("Unknown") is None


def test_get_data_group_type_id_prefer_new_api_then_old(monkeypatch):
    mod = _import_floor_utils()
    assert mod.get_data_group_type_id() == "GroupType.Data"

    monkeypatch.setattr(mod, "GroupTypeId", None)
    assert mod.get_data_group_type_id() == "PG_DATA"

    monkeypatch.setattr(mod, "BuiltInParameterGroup", None)
    assert mod.get_data_group_type_id() is None


def test_create_category_set_inserts_all_categories():
    mod = _import_floor_utils()
    cat_set = mod.create_category_set(object(), [1, 2, 3])
    assert hasattr(cat_set, "items")
    assert cat_set.items == ["CAT:1", "CAT:2", "CAT:3"]


def test_get_existing_parameter_bindings_collects_named_defs():
    mod = _import_floor_utils()

    class _Def:
        def __init__(self, name):
            self.Name = name

    class _Iter:
        def __init__(self):
            self._items = [_Def("A"), _Def("B"), _Def(None)]
            self._idx = -1

        def Reset(self):
            self._idx = -1

        def MoveNext(self):
            self._idx += 1
            return self._idx < len(self._items)

        @property
        def Key(self):
            return self._items[self._idx]

    class _Bindings:
        def ForwardIterator(self):
            return _Iter()

    class _Doc:
        ParameterBindings = _Bindings()

    result = mod.get_existing_parameter_bindings(_Doc())
    assert result == {"A": result["A"], "B": result["B"]}


def test_safe_get_name_for_valid_none_and_faulty_objects():
    mod = _import_floor_utils()

    class _Obj:
        Name = "Name1"

    class _Broken:
        @property
        def Name(self):
            raise RuntimeError("boom")

    assert mod.safe_get_name(_Obj()) == "Name1"
    assert mod.safe_get_name(None) is None
    assert mod.safe_get_name(_Broken()) is None


def test_normalize_path_returns_abs_norm_path():
    mod = _import_floor_utils()
    raw = os.path.join(".", "tests", "..", "tests")
    norm = mod.normalize_path(raw)
    assert os.path.isabs(norm)
    assert norm == os.path.normpath(norm)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("1.2.3", (1, 2, 3)),
        ("v2.0", (2, 0)),
        ("V10.20.30", (10, 20, 30)),
        ("invalid", ()),
        ("", ()),
    ],
)
def test_parse_version_string(raw, expected):
    mod = _import_floor_utils()
    assert mod.parse_version_string(raw) == expected


def test_format_error_message_with_and_without_traceback():
    mod = _import_floor_utils()
    err = ValueError("bad")
    short = mod.format_error_message(err)
    full = mod.format_error_message(err, include_traceback=True)

    assert short == "bad"
    assert "bad" in full
    assert "\n\n" in full

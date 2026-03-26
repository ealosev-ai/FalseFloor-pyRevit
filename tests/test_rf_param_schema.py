"""Pure tests for canonical RF shared-parameter schema helper."""

import os
import shutil
import sys
import uuid
from types import ModuleType

import pytest

import rf_param_schema

pytestmark = [pytest.mark.unit]


def test_rf_parameter_guids_are_unique():
    names = list(rf_param_schema.RF_PARAMETER_GUIDS)
    guids = list(rf_param_schema.RF_PARAMETER_GUIDS.values())

    assert len(names) == len(set(names))
    assert len(guids) == len(set(guids))


def test_rfparams_constants_match_guid_keys():
    expected = {
        name[3:].upper(): name for name in rf_param_schema.RF_PARAMETER_GUIDS
    }
    actual = {
        attr: getattr(rf_param_schema.RFParams, attr)
        for attr in dir(rf_param_schema.RFParams)
        if attr.isupper() and not attr.startswith("_")
    }

    assert actual == expected


def test_get_expected_guid_requires_known_name():
    guid = rf_param_schema.get_expected_guid("RF_Step_X")
    assert guid == "aa5ed481-5cf0-5933-b251-3a290396bb12"

    with pytest.raises(KeyError):
        rf_param_schema.get_expected_guid("RF_Unknown")


def test_collect_definition_guid_mismatches_skips_unverifiable_and_detects_wrong_guid():
    class _Def:
        def __init__(self, name, guid_marker):
            self.Name = name
            self._guid_marker = guid_marker

        @property
        def GUID(self):
            if self._guid_marker == "missing":
                raise AttributeError("No GUID")
            return self._guid_marker

    defs = {
        "RF_Step_X": _Def("RF_Step_X", "aa5ed481-5cf0-5933-b251-3a290396bb12"),
        "RF_Step_Y": _Def("RF_Step_Y", "WRONG-GUID"),
        "RF_Base_X": _Def("RF_Base_X", "missing"),
    }

    mismatches = rf_param_schema.collect_definition_guid_mismatches(defs)

    assert mismatches == [
        (
            "RF_Step_Y",
            "WRONG-GUID",
            "78a22501-2b4d-5c0b-8174-8178817fadfc",
        ),
    ]


def test_collect_project_parameter_guid_mismatches_uses_shared_parameter_elements():
    class _SharedParam:
        def __init__(self, name, guid):
            self.Name = name
            self.GuidValue = guid

    class _Collector(list):
        def __init__(self, doc):
            list.__init__(self, doc._shared_params)

        def OfClass(self, _cls):
            return self

    db_mod = ModuleType("Autodesk.Revit.DB")
    db_mod.SharedParameterElement = type("SharedParameterElement", (), {})
    db_mod.FilteredElementCollector = _Collector

    prev = sys.modules.get("Autodesk.Revit.DB")
    sys.modules["Autodesk.Revit.DB"] = db_mod
    try:
        class _Doc:
            _shared_params = [
                _SharedParam("RF_Step_X", "aa5ed481-5cf0-5933-b251-3a290396bb12"),
                _SharedParam("RF_Step_Y", "WRONG-GUID"),
            ]

        mismatches = rf_param_schema.collect_project_parameter_guid_mismatches(
            _Doc(),
            allowed_names={"RF_Step_X", "RF_Step_Y", "RF_Base_X"},
            bound_names={"RF_Step_X", "RF_Step_Y", "RF_Base_X"},
        )
    finally:
        if prev is None:
            del sys.modules["Autodesk.Revit.DB"]
        else:
            sys.modules["Autodesk.Revit.DB"] = prev

    assert mismatches == [
        (
            "RF_Base_X",
            "<not-shared-or-unresolved>",
            "7c3e45d9-b916-5ba6-9b74-c41f435658cf",
        ),
        (
            "RF_Step_Y",
            "WRONG-GUID",
            "78a22501-2b4d-5c0b-8174-8178817fadfc",
        ),
    ]


def test_collect_family_parameter_guid_mismatches_filters_allowed_names():
    class _Def:
        def __init__(self, name):
            self.Name = name

    class _Param:
        def __init__(self, definition, is_shared, guid=None):
            self.Definition = definition
            self.IsShared = is_shared
            self.GUID = guid

    class _FamMgr:
        def GetParameters(self):
            return [
                _Param(_Def("RF_Row"), True, "WRONG"),
                _Param(_Def("RF_Column"), False, None),
                _Param(_Def("Other"), True, "IGNORED"),
            ]

    class _FamDoc:
        FamilyManager = _FamMgr()

    mismatches = rf_param_schema.collect_family_parameter_guid_mismatches(
        _FamDoc(), allowed_names={"RF_Row", "RF_Column"}
    )

    assert mismatches == [
        ("RF_Row", "WRONG", "b383ef29-f11a-5a57-90b7-1949e25ecc1a"),
        ("RF_Column", "<not-shared>", "979a04ee-ea89-51fa-aa05-5ebf40609007"),
    ]


def _make_workspace_tmp_dir():
    root = os.path.join(os.path.dirname(__file__), "_tmp_rf_param_schema")
    path = os.path.join(root, str(uuid.uuid4()))
    os.makedirs(path)
    return path


def test_ensure_canonical_shared_parameter_file_writes_header():
    tmp_dir = _make_workspace_tmp_dir()
    path = os.path.join(tmp_dir, "RaisedFloor.sharedparameters.txt")

    try:
        created = rf_param_schema.ensure_canonical_shared_parameter_file(path)
        with open(path, "r") as fp:
            content = fp.read()
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    assert created == path
    assert "*META\tVERSION\tMINVERSION" in content
    assert "*PARAM\tGUID\tNAME\tDATATYPE" in content


def test_use_canonical_shared_parameter_file_restores_original_value():
    tmp_dir = _make_workspace_tmp_dir()
    path = os.path.join(tmp_dir, "RaisedFloor.sharedparameters.txt")

    class _App:
        SharedParametersFilename = "C:\\temp\\original.txt"

    app = _App()
    try:
        with rf_param_schema.use_canonical_shared_parameter_file(app, path) as active:
            assert active == path
            assert app.SharedParametersFilename == path
            assert os.path.exists(active)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    assert app.SharedParametersFilename == "C:\\temp\\original.txt"

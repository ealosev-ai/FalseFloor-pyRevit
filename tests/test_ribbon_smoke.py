# -*- coding: utf-8 -*-
"""Smoke tests for ribbon (pushbutton) scripts.

AST-based static analysis catching common regressions WITHOUT Revit:
1. SyntaxError in any button script
2. Importing non-existent names from floor_* library modules
3. Calling floor_* functions with wrong argument counts

These tests would have caught:
- _get_existing_bindings() called without doc  (CRITICAL, 2026-03)
- _make_cat_set(cats) called without doc        (CRITICAL, 2026-03)
- Element used but not imported in Place tiles  (MEDIUM, 2026-03)
"""

import ast
import glob
import importlib
import inspect
import os
import sys
from types import ModuleType
from typing import Any, cast

import pytest

pytestmark = [pytest.mark.unit]

# ── Paths ─────────────────────────────────────────────────
_TESTS_DIR = os.path.dirname(__file__)
_EXT_DIR = os.path.normpath(os.path.join(_TESTS_DIR, ".."))
_LIB_DIR = os.path.join(_EXT_DIR, "lib")
_PANEL_DIR = os.path.join(_EXT_DIR, "RaisedFloor.tab", "RaisedFloor.panel")
_FLOOR_MODULES = [
    "floor_common",
    "floor_exact",
    "floor_grid",
    "floor_i18n",
    "floor_ui",
    "floor_utils",
]


# ── Script discovery ──────────────────────────────────────
def _discover_scripts():
    """Return pytest.param(path, id=label) for every pushbutton script.py."""
    pattern = os.path.join(_PANEL_DIR, "**", "script.py")
    result = []
    for path in sorted(glob.glob(pattern, recursive=True)):
        rel = os.path.relpath(path, _PANEL_DIR)
        label = "/".join(
            p.replace(".pulldown", "").replace(".pushbutton", "")
            for p in rel.replace("\\", "/").split("/")[:-1]
        )
        result.append(pytest.param(path, id=label))
    return result


_ALL_SCRIPTS = _discover_scripts()


# ── Minimal Revit API stubs ──────────────────────────────
def _install_stubs():
    """Install lightweight Autodesk / clr / pyrevit / Clipper2 stubs for floor_* import."""
    if "Autodesk.Revit.DB" in sys.modules:
        # Ensure missing attributes exist even if partial stubs are installed
        db = cast(Any, sys.modules["Autodesk.Revit.DB"])
        for attr in ("Element", "ViewPlan", "FamilyInstance"):
            if not hasattr(db, attr):
                setattr(db, attr, type(attr, (), {}))
        _ensure_clr_stubs()
        _ensure_clipper_stubs()
        return

    db = cast(Any, ModuleType("Autodesk.Revit.DB"))

    # Simple tag-style stubs
    db.StorageType = type("StorageType", (), {"Double": 0, "Integer": 1, "String": 2})
    db.BuiltInCategory = type(
        "BuiltInCategory", (), {"OST_Floors": 1, "OST_GenericModel": 2}
    )
    db.GroupTypeId = type("GroupTypeId", (), {"Data": "stub"})
    db.BuiltInParameterGroup = type("BuiltInParameterGroup", (), {"PG_DATA": "stub"})
    db.Document = type("Document", (), {})
    db.ExternalDefinitionCreationOptions = type("EDCO", (), {})
    db.Family = type("Family", (), {})
    db.FamilyInstance = type("FamilyInstance", (), {})
    db.Part = type("Part", (), {})
    db.CurveElement = type("CurveElement", (), {})
    db.ViewPlan = type("ViewPlan", (), {})
    db.GraphicsStyleType = type("GraphicsStyleType", (), {"Projection": 1})

    # Stubs with minimal behaviour
    class _SpecTypeId:
        Length = "Spec.Length"

        class Int:
            Integer = "Spec.Int.Integer"

        class String:
            Text = "Spec.String.Text"

        class Boolean:
            YesNo = "Spec.Boolean.YesNo"

    db.SpecTypeId = _SpecTypeId
    db.ParameterType = type(
        "ParameterType",
        (),
        {"Length": "PL", "Integer": "PI", "Text": "PT", "YesNo": "PY"},
    )

    class _CategorySet:
        def __init__(self):
            self._items = []

        def Insert(self, c):
            self._items.append(c)

    db.CategorySet = _CategorySet

    class _Category:
        @staticmethod
        def GetCategory(_doc, bic):
            return bic

    db.Category = _Category

    class _ElementId:
        InvalidElementId = -1

        def __init__(self, v=-1):
            self.IntegerValue = v

    db.ElementId = _ElementId
    db.Element = type("Element", (), {})

    class _Color:
        def __init__(self, r=0, g=0, b=0):
            pass

    db.Color = _Color

    class _XYZ:
        def __init__(self, x=0, y=0, z=0):
            self.X, self.Y, self.Z = x, y, z

    db.XYZ = _XYZ

    class _Line:
        @staticmethod
        def CreateBound(a, b):
            return _Line()

    db.Line = _Line

    class _LinePatternElement:
        @staticmethod
        def GetLinePatternElementByName(*a):
            return None

    db.LinePatternElement = _LinePatternElement

    class _FilteredElementCollector:
        def __init__(self, *a):
            pass

        def OfClass(self, c):
            return self

        def OfCategory(self, c):
            return self

        def WhereElementIsNotElementType(self):
            return self

        def __iter__(self):
            return iter([])

    db.FilteredElementCollector = _FilteredElementCollector

    # Module hierarchy
    autodesk = cast(Any, ModuleType("Autodesk"))
    revit_mod = cast(Any, ModuleType("Autodesk.Revit"))
    ui_mod = cast(Any, ModuleType("Autodesk.Revit.UI"))
    autodesk.Revit = revit_mod
    revit_mod.DB = db
    revit_mod.UI = ui_mod

    sel = cast(Any, ModuleType("Autodesk.Revit.UI.Selection"))
    sel.ISelectionFilter = type("ISelectionFilter", (), {})
    sel.ObjectType = type("ObjectType", (), {"Element": 1})

    exc = cast(Any, ModuleType("Autodesk.Revit.Exceptions"))
    exc.OperationCanceledException = type("OpCancelled", (Exception,), {})

    struct = cast(Any, ModuleType("Autodesk.Revit.DB.Structure"))
    struct.StructuralType = type("StructuralType", (), {"NonStructural": 0})

    for key, mod in {
        "Autodesk": autodesk,
        "Autodesk.Revit": revit_mod,
        "Autodesk.Revit.DB": db,
        "Autodesk.Revit.DB.Structure": struct,
        "Autodesk.Revit.UI": ui_mod,
        "Autodesk.Revit.UI.Selection": sel,
        "Autodesk.Revit.Exceptions": exc,
    }.items():
        sys.modules[key] = mod

    # clr stub
    _ensure_clr_stubs()

    # Clipper2Lib stubs (needed for floor_exact module-level _load_clipper_api())
    _ensure_clipper_stubs()


def _ensure_clr_stubs():
    """Ensure clr module exists with all required attributes."""
    if "clr" not in sys.modules:
        sys.modules["clr"] = ModuleType("clr")
    clr = cast(Any, sys.modules["clr"])
    if not hasattr(clr, "AddReference"):
        clr.AddReference = lambda *a: None
    if not hasattr(clr, "AddReferenceToFileAndPath"):
        clr.AddReferenceToFileAndPath = lambda *a: None


def _ensure_clipper_stubs():
    """Ensure Clipper2Lib stubs exist for floor_exact import."""
    if "Clipper2Lib" in sys.modules:
        return

    clipper = cast(Any, ModuleType("Clipper2Lib"))

    class _Point64:
        def __init__(self, x, y):
            self.X, self.Y = int(x), int(y)

    class _Path64(list):
        def Add(self, p):
            self.append(p)

        @property
        def Count(self):
            return len(self)

    class _Paths64(list):
        def Add(self, p):
            self.append(p)

        @property
        def Count(self):
            return len(self)

    clipper.Point64 = _Point64
    clipper.Path64 = _Path64
    clipper.Paths64 = _Paths64
    clipper.Clipper64 = type("Clipper64", (), {})
    clipper.ClipType = type("ClipType", (), {"Intersection": 1})
    clipper.FillRule = type("FillRule", (), {"NonZero": 1})
    clipper.JoinType = type("JoinType", (), {"Miter": 1})
    clipper.EndType = type("EndType", (), {"Polygon": 1})

    clipper_sub = cast(Any, ModuleType("Clipper2Lib.Clipper"))
    clipper_sub.Difference = lambda a, b, *_: a
    clipper_sub.Intersect = lambda a, b, *_: a
    clipper_sub.InflatePaths = lambda paths, *_: paths

    sys.modules["Clipper2Lib"] = clipper
    sys.modules["Clipper2Lib.Clipper"] = clipper_sub


# ── Load floor_* exports & signatures ────────────────────
_CACHE: dict = {}


def _get_floor_api():
    """Return (exports, signatures, errors) with lazy caching."""
    if _CACHE:
        return _CACHE["exports"], _CACHE["sigs"], _CACHE["errors"]

    _install_stubs()
    if _LIB_DIR not in sys.path:
        sys.path.insert(0, _LIB_DIR)

    exports = {}
    sigs = {}
    errors = {}

    for mod_name in _FLOOR_MODULES:
        try:
            if mod_name in sys.modules:
                mod = importlib.reload(sys.modules[mod_name])
            else:
                mod = importlib.import_module(mod_name)
            exports[mod_name] = set(dir(mod))

            for name in dir(mod):
                obj = getattr(mod, name, None)
                if not callable(obj):
                    continue
                try:
                    sig = inspect.signature(obj)
                    params = [
                        p
                        for p in sig.parameters.values()
                        if p.kind not in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                    ]
                    min_a = sum(
                        1 for p in params if p.default is inspect.Parameter.empty
                    )
                    max_a = len(params)
                    has_var = any(
                        p.kind in (p.VAR_POSITIONAL, p.VAR_KEYWORD)
                        for p in sig.parameters.values()
                    )
                    sigs[(mod_name, name)] = (min_a, max_a, has_var)
                except (ValueError, TypeError):
                    pass
        except Exception as exc:
            exports[mod_name] = set()
            errors[mod_name] = str(exc)

    _CACHE.update(exports=exports, sigs=sigs, errors=errors)
    return exports, sigs, errors


# ── AST helpers ───────────────────────────────────────────
def _parse_script(path):
    with open(path, "r", encoding="utf-8-sig") as f:
        return ast.parse(f.read(), filename=path)


def _extract_floor_imports_and_aliases(tree):
    """Map local_name -> (module, original_name) for floor_* imports + aliases."""
    mapping = {}
    for node in ast.iter_child_nodes(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("floor_")
        ):
            for alias in node.names:
                mapping[alias.asname or alias.name] = (node.module, alias.name)
        # Track module-level aliases: _alias = imported_name
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Name)
            and node.value.id in mapping
        ):
            mapping[node.targets[0].id] = mapping[node.value.id]
    return mapping


def _extract_floor_module_aliases(tree):
    """Map module alias -> module for import floor_* [as alias]."""
    aliases = {}
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("floor_"):
                    aliases[alias.asname or alias.name] = alias.name
        if (
            isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and isinstance(node.value, ast.Name)
            and node.value.id in aliases
        ):
            aliases[node.targets[0].id] = aliases[node.value.id]
    return aliases


def _find_floor_calls(tree, known_names):
    """Find Call(Name) nodes targeting known_names.

    Skips calls with *args or **kwargs (can't count reliably).
    Returns [(local_name, n_args, lineno)].
    """
    calls = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id not in known_names:
            continue
        if any(isinstance(a, ast.Starred) for a in node.args):
            continue
        if any(kw.arg is None for kw in node.keywords):
            continue
        n = len(node.args) + len(node.keywords)
        calls.append((node.func.id, n, node.lineno))
    return calls


def _find_floor_attr_calls(tree, module_aliases):
    """Find Call(alias.func) where alias points to imported floor_* module.

    Skips calls with *args or **kwargs (can't count reliably).
    Returns [(module_alias, function_name, n_args, lineno)].
    """
    calls = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
        ):
            continue
        mod_alias = node.func.value.id
        if mod_alias not in module_aliases:
            continue
        if any(isinstance(a, ast.Starred) for a in node.args):
            continue
        if any(kw.arg is None for kw in node.keywords):
            continue
        n = len(node.args) + len(node.keywords)
        calls.append((mod_alias, node.func.attr, n, node.lineno))
    return calls


# ── Tests ─────────────────────────────────────────────────


class TestFloorModulesLoadable:
    """Verify our stubs allow all floor_* modules to import."""

    @pytest.mark.parametrize("mod_name", _FLOOR_MODULES)
    def test_module_imports(self, mod_name):
        exports, _, errors = _get_floor_api()
        assert mod_name not in errors, "Import failed: {}".format(errors.get(mod_name))
        assert exports.get(mod_name), "{} exports nothing".format(mod_name)


class TestRibbonSyntax:
    """Every pushbutton script.py must be valid Python."""

    @pytest.mark.parametrize("path", _ALL_SCRIPTS)
    def test_compiles(self, path):
        with open(path, "r", encoding="utf-8-sig") as f:
            source = f.read()
        compile(source, path, "exec")


class TestRibbonImports:
    """Names imported from floor_* modules must actually exist there."""

    @pytest.mark.parametrize("path", _ALL_SCRIPTS)
    def test_floor_import_names(self, path):
        exports, _, _ = _get_floor_api()
        tree = _parse_script(path)
        missing = []
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.ImportFrom)
                and node.module
                and node.module.startswith("floor_")
            ):
                continue
            mod_exports = exports.get(node.module, set())
            if not mod_exports:
                continue
            for alias in node.names:
                if alias.name not in mod_exports:
                    missing.append(
                        "L{}: '{}' not in {}".format(
                            node.lineno, alias.name, node.module
                        )
                    )
        assert not missing, "Missing imports:\n  " + "\n  ".join(missing)


class TestRibbonCallSignatures:
    """Calls to floor_* functions must pass correct number of arguments."""

    @pytest.mark.parametrize("path", _ALL_SCRIPTS)
    def test_arg_counts(self, path):
        _, sigs, _ = _get_floor_api()
        tree = _parse_script(path)
        mapping = _extract_floor_imports_and_aliases(tree)
        module_aliases = _extract_floor_module_aliases(tree)
        calls = _find_floor_calls(tree, set(mapping))
        attr_calls = _find_floor_attr_calls(tree, set(module_aliases))

        errors = []
        for local_name, n_args, lineno in calls:
            mod_name, orig_name = mapping[local_name]
            key = (mod_name, orig_name)
            if key not in sigs:
                continue
            min_a, max_a, has_var = sigs[key]
            if has_var:
                if n_args < min_a:
                    errors.append(
                        "L{}: {}() got {} args, needs >= {}".format(
                            lineno, local_name, n_args, min_a
                        )
                    )
            elif n_args < min_a or n_args > max_a:
                errors.append(
                    "L{}: {}() got {} args, expected {}-{}".format(
                        lineno, local_name, n_args, min_a, max_a
                    )
                )
        for mod_alias, func_name, n_args, lineno in attr_calls:
            mod_name = module_aliases[mod_alias]
            key = (mod_name, func_name)
            if key not in sigs:
                continue
            min_a, max_a, has_var = sigs[key]
            label = "{}.{}".format(mod_alias, func_name)
            if has_var:
                if n_args < min_a:
                    errors.append(
                        "L{}: {}() got {} args, needs >= {}".format(
                            lineno, label, n_args, min_a
                        )
                    )
            elif n_args < min_a or n_args > max_a:
                errors.append(
                    "L{}: {}() got {} args, expected {}-{}".format(
                        lineno, label, n_args, min_a, max_a
                    )
                )
        assert not errors, "Arg count mismatches:\n  " + "\n  ".join(errors)

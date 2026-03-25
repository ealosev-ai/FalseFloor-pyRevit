# -*- coding: utf-8 -*-
"""Common utility functions for RaisedFloor extension.

This module contains shared utilities that are used across multiple
modules in the extension, avoiding code duplication.
"""

import os
from typing import Any, Dict, Optional, Tuple

# Import StorageType first (always available)
from Autodesk.Revit.DB import StorageType  # type: ignore

# Other imports are conditional based on Revit version
try:
    from Autodesk.Revit.DB import GroupTypeId  # type: ignore
except ImportError:
    GroupTypeId = None

try:
    from Autodesk.Revit.DB import BuiltInParameterGroup  # type: ignore
except ImportError:
    BuiltInParameterGroup = None

try:
    from Autodesk.Revit.DB import SpecTypeId  # type: ignore
except ImportError:
    SpecTypeId = None

try:
    from Autodesk.Revit.DB import ParameterType  # type: ignore
except ImportError:
    ParameterType = None

# These are always available
from Autodesk.Revit.DB import Category, CategorySet, Document  # type: ignore


def get_storage_type_id(
    storage_type: StorageType,
) -> Any:
    """Convert StorageType to appropriate ForgeTypeId or ParameterType.

    Handles both Revit 2025+ (SpecTypeId) and older versions (ParameterType).

    Args:
        storage_type: The StorageType to convert.

    Returns:
        ForgeTypeId (Revit 2025+) or ParameterType (older), or None if unsupported.
    """
    # Special case: Yes/No boolean
    if storage_type == "YesNo":
        if SpecTypeId is not None:
            try:
                return SpecTypeId.Boolean.YesNo
            except Exception:
                pass
        if ParameterType is not None:
            try:
                return ParameterType.YesNo
            except Exception:
                pass
        return None

    # Revit 2025+: SpecTypeId
    if SpecTypeId is not None:
        try:
            if storage_type == StorageType.Double:
                return SpecTypeId.Length
            elif storage_type == StorageType.Integer:
                return SpecTypeId.Int.Integer
            elif storage_type == StorageType.String:
                return SpecTypeId.String.Text
        except Exception:
            pass

    # Revit < 2025: ParameterType enum
    if ParameterType is not None:
        try:
            if storage_type == StorageType.Double:
                return ParameterType.Length
            elif storage_type == StorageType.Integer:
                return ParameterType.Integer
            elif storage_type == StorageType.String:
                return ParameterType.Text
        except Exception:
            pass

    return None


def get_data_group_type_id() -> Optional[Any]:
    """Get the data group type ID for parameter bindings.

    Handles both Revit 2025+ (GroupTypeId) and older versions
    (BuiltInParameterGroup).

    Returns:
        GroupTypeId or BuiltInParameterGroup.PG_DATA, or None if unavailable.
    """
    # Revit 2025+: GroupTypeId
    if GroupTypeId is not None:
        try:
            return GroupTypeId.Data
        except Exception:
            pass

    # Revit < 2025: BuiltInParameterGroup
    if BuiltInParameterGroup is not None:
        try:
            return BuiltInParameterGroup.PG_DATA
        except Exception:
            pass

    return None


def create_category_set(
    doc: Document,
    built_in_categories: list,
) -> CategorySet:
    """Create a CategorySet from a list of BuiltInCategory values.

    Args:
        doc: Revit document.
        built_in_categories: List of BuiltInCategory enum values.

    Returns:
        CategorySet containing the specified categories.
    """
    category_set = CategorySet()
    for bic in built_in_categories:
        category = Category.GetCategory(doc, bic)
        if category:
            category_set.Insert(category)
    return category_set


def get_existing_parameter_bindings(
    doc: Document,
) -> Dict[str, Any]:
    """Collect existing parameter bindings in the project.

    Args:
        doc: Revit document.

    Returns:
        Dictionary mapping parameter names to their definitions.
    """
    existing = {}
    binding_map = doc.ParameterBindings
    iterator = binding_map.ForwardIterator()
    iterator.Reset()

    while iterator.MoveNext():
        definition = iterator.Key
        if definition and definition.Name:
            existing[definition.Name] = definition

    return existing


def _get_definition_group_id(definition):
    # type: (Any) -> Any
    """Get the parameter group id from a definition, version-agnostic."""
    try:
        return definition.GetGroupTypeId()
    except Exception:
        pass
    try:
        return definition.ParameterGroup
    except Exception:
        pass
    return None


def get_full_parameter_binding_info(
    doc,  # type: Document
):
    # type: (...) -> Dict[str, Dict[str, Any]]
    """Collect full parameter binding info for all bound parameters.

    Returns a dict keyed by parameter name with values containing:
      - definition: the InternalDefinition
      - binding: the InstanceBinding or TypeBinding object
      - is_instance: True if InstanceBinding, False if TypeBinding
      - categories: list of BuiltInCategory values from the binding
      - group_id: ForgeTypeId or BuiltInParameterGroup (or None)
    """
    from Autodesk.Revit.DB import InstanceBinding  # type: ignore

    result = {}  # type: Dict[str, Dict[str, Any]]
    binding_map = doc.ParameterBindings
    iterator = binding_map.ForwardIterator()
    iterator.Reset()

    while iterator.MoveNext():
        definition = iterator.Key
        if not definition or not definition.Name:
            continue
        binding = iterator.Current
        if not binding:
            continue

        is_instance = isinstance(binding, InstanceBinding)

        categories = []  # type: List[Any]
        try:
            cat_set = binding.Categories
            if cat_set:
                for cat in cat_set:
                    try:
                        categories.append(cat.BuiltInCategory)
                    except Exception:
                        categories.append(cat)
        except Exception:
            pass

        group_id = _get_definition_group_id(definition)

        result[definition.Name] = {
            "definition": definition,
            "binding": binding,
            "is_instance": is_instance,
            "categories": categories,
            "group_id": group_id,
        }

    return result


def safe_get_name(obj: Any) -> Optional[str]:
    """Safely get the Name property from a Revit object.

    Args:
        obj: Object that may have a Name property.

    Returns:
        The name string, or None if the object is None or has no Name.
    """
    if obj is None:
        return None
    try:
        return obj.Name
    except Exception:
        return None


def normalize_path(path: str) -> str:
    """Normalize a file path for cross-platform compatibility.

    Handles Windows UNC paths and normalizes separators.

    Args:
        path: File path to normalize.

    Returns:
        Normalized absolute path.
    """
    return os.path.normpath(os.path.abspath(path))


def parse_version_string(version_str: str) -> Tuple[int, ...]:
    """Parse a version string into a tuple of integers.

    Args:
        version_str: Version string like "1.2.3" or "v1.2.0".

    Returns:
        Tuple of integers (major, minor, patch).
    """
    cleaned = version_str.lstrip("vV")
    parts = cleaned.split(".")
    return tuple(int(p) for p in parts if p.isdigit())


def format_error_message(
    error: Exception,
    include_traceback: bool = False,
) -> str:
    """Format an error message for display.

    Args:
        error: The exception to format.
        include_traceback: Whether to include traceback.

    Returns:
        Formatted error message string.
    """
    if include_traceback:
        import traceback

        return "{}\n\n{}".format(str(error), traceback.format_exc())
    return str(error)

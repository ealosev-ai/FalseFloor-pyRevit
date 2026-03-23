# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import ElementId, ViewPlan  # type: ignore
from pyrevit import revit  # type: ignore


def get_doc():
    """Return the current active Revit document from pyRevit."""
    return revit.doc


def get_uidoc():
    """Return the current active UI document from pyRevit."""
    return revit.uidoc


def get_active_view():
    """Return the active view for the current document, if any."""
    doc = get_doc()
    return doc.ActiveView if doc else None


def is_valid_revit_object(obj):
    """Best-effort validity check for Revit API objects."""
    try:
        return bool(obj) and bool(obj.IsValidObject)
    except Exception:
        return False


def get_element(element_id, doc=None):
    """Resolve an element by ElementId or int against the current document."""
    doc = doc or get_doc()
    if not doc or element_id is None:
        return None

    try:
        if isinstance(element_id, ElementId):
            return doc.GetElement(element_id)
        return doc.GetElement(ElementId(int(element_id)))
    except Exception:
        return None


def require_view_plan():
    """Return the active view if it is a plan view, otherwise None."""
    view = get_active_view()
    return view if isinstance(view, ViewPlan) else None

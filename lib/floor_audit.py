# -*- coding: utf-8 -*-
"""Audit helpers for RaisedFloor layout ownership and stored IDs."""

from rf_param_schema import RFFamilies, RFParams as P  # type: ignore
from revit_smoke import SmokeReport  # type: ignore

ZONE_SOURCE = "__zones__"

CURVE_ID_SPECS = (
    {"param": P.CONTOUR_LINES_ID, "label": "Contour lines", "kind": "curve"},
    {"param": P.GRID_LINES_ID, "label": "Grid lines", "kind": "curve"},
    {"param": P.BASE_MARKER_ID, "label": "Base marker", "kind": "curve"},
)

FAMILY_ID_SPECS = (
    {"param": P.TILES_ID, "label": "Tiles", "family": RFFamilies.TILE},
    {
        "param": P.STRINGERS_TOP_ID,
        "label": "Top stringers",
        "family": RFFamilies.STRINGER,
    },
    {
        "param": P.STRINGERS_BOTTOM_ID,
        "label": "Bottom stringers",
        "family": RFFamilies.STRINGER,
    },
    {"param": P.SUPPORTS_ID, "label": "Supports", "family": RFFamilies.SUPPORT},
)

LAYOUT_ID_SPECS = CURVE_ID_SPECS + FAMILY_ID_SPECS


def parse_raw_id_string(raw_value):
    """Parse semicolon-separated integer IDs and keep invalid tokens."""
    ids = []
    invalid_tokens = []
    if raw_value is None:
        return ids, invalid_tokens

    for token in str(raw_value).split(";"):
        token = token.strip()
        if not token:
            continue
        try:
            ids.append(int(token))
        except Exception:
            invalid_tokens.append(token)
    return ids, invalid_tokens


def summarize_ids(ids):
    """Return count, stable unique ids, and duplicate ids."""
    unique_ids = []
    duplicate_ids = []
    seen = set()
    duplicate_seen = set()

    for value in ids or []:
        int_id = int(value)
        if int_id in seen:
            if int_id not in duplicate_seen:
                duplicate_seen.add(int_id)
                duplicate_ids.append(int_id)
            continue
        seen.add(int_id)
        unique_ids.append(int_id)

    return {
        "count": len(ids or []),
        "unique_ids": tuple(unique_ids),
        "duplicate_ids": tuple(sorted(duplicate_ids)),
    }


def extract_zone_ids(zone_data):
    """Extract reinforcement-zone ids and invalid raw values."""
    ids = []
    invalid_values = []

    zones = []
    if isinstance(zone_data, dict):
        zones = zone_data.get("zones") or []

    for zone in zones:
        if not isinstance(zone, dict):
            invalid_values.append(repr(zone))
            continue
        for key in ("upper_ids", "lower_ids", "support_ids"):
            for value in zone.get(key) or []:
                try:
                    ids.append(int(value))
                except Exception:
                    invalid_values.append("{}={}".format(key, value))

    return ids, invalid_values


def build_owner_index(records):
    """Build {element_id: [{floor_id, source}, ...]} from floor records."""
    owner_index = {}
    for record in records or []:
        floor_id = record["floor_id"]
        for source_name, ids in (record.get("param_ids") or {}).items():
            for int_id in summarize_ids(ids)["unique_ids"]:
                owner_index.setdefault(int_id, []).append(
                    {"floor_id": floor_id, "source": source_name}
                )
        for int_id in summarize_ids(record.get("zone_ids") or [])["unique_ids"]:
            owner_index.setdefault(int_id, []).append(
                {"floor_id": floor_id, "source": ZONE_SOURCE}
            )
    return owner_index


def find_conflicting_owners(floor_id, source_name, ids, owner_index):
    """Return owners for *ids* excluding the current floor/source pair."""
    conflicts = {}
    for int_id in summarize_ids(ids)["unique_ids"]:
        owners = []
        for owner in owner_index.get(int_id, []):
            if owner["floor_id"] == floor_id and owner["source"] == source_name:
                continue
            owners.append(owner)
        if owners:
            conflicts[int_id] = owners
    return conflicts


def summarize_unowned_instances(instance_ids_by_family, owner_index):
    """Return {family_name: (ids...)} for generated instances with no owner floor."""
    owned_ids = set(owner_index.keys())
    result = {}
    for family_name, ids in (instance_ids_by_family or {}).items():
        unowned = []
        for int_id in summarize_ids(ids)["unique_ids"]:
            if int_id not in owned_ids:
                unowned.append(int_id)
        if unowned:
            result[family_name] = tuple(sorted(unowned))
    return result


def summarize_zone_membership(zone_ids, top_ids, bottom_ids, support_ids):
    """Return zone ids missing from stored stringer/support ownership."""
    allowed = set(summarize_ids(top_ids)["unique_ids"])
    allowed.update(summarize_ids(bottom_ids)["unique_ids"])
    allowed.update(summarize_ids(support_ids)["unique_ids"])
    return tuple(
        sorted(
            int_id
            for int_id in summarize_ids(zone_ids)["unique_ids"]
            if int_id not in allowed
        )
    )


def _format_id_list(ids, limit=8):
    ids = list(ids or [])
    if not ids:
        return "-"
    head = ", ".join(str(v) for v in ids[:limit])
    if len(ids) > limit:
        head += ", ... +{}".format(len(ids) - limit)
    return head


def _get_floor_record(floor):
    from floor_common import (  # type: ignore
        get_id_value,
        get_string_param,
        load_reinforcement_zones,
    )

    param_ids = {}
    invalid_tokens = {}
    for spec in LAYOUT_ID_SPECS:
        raw = get_string_param(floor, spec["param"])
        ids, invalid = parse_raw_id_string(raw)
        param_ids[spec["param"]] = ids
        invalid_tokens[spec["param"]] = invalid

    zone_ids = []
    zone_invalid = []
    zone_error = None
    raw_zone = get_string_param(floor, P.REINF_ZONES_JSON)
    if raw_zone:
        try:
            zone_data = load_reinforcement_zones(floor)
            zone_ids, zone_invalid = extract_zone_ids(zone_data)
        except Exception as exc:
            zone_error = str(exc)

    return {
        "floor_id": get_id_value(floor),
        "param_ids": param_ids,
        "invalid_tokens": invalid_tokens,
        "zone_ids": zone_ids,
        "zone_invalid": zone_invalid,
        "zone_error": zone_error,
    }


def _collect_floor_records(doc):
    from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector  # type: ignore

    records = []
    floors = (
        FilteredElementCollector(doc)
        .OfCategory(BuiltInCategory.OST_Floors)
        .WhereElementIsNotElementType()
    )
    for floor in floors:
        records.append(_get_floor_record(floor))
    return records


def _get_element_family_name(element):
    try:
        symbol = getattr(element, "Symbol", None)
        family = getattr(symbol, "Family", None)
        name = getattr(family, "Name", None)
        if name:
            return name
    except Exception:
        pass
    try:
        symbol = getattr(element, "Symbol", None)
        family_name = getattr(symbol, "FamilyName", None)
        if family_name:
            return family_name
    except Exception:
        pass
    return None


def _inspect_expected_element(doc, int_id, spec):
    from Autodesk.Revit.DB import CurveElement, ElementId  # type: ignore

    element = doc.GetElement(ElementId(int_id))
    if element is None:
        return "missing", "missing"

    if spec.get("kind") == "curve":
        if not isinstance(element, CurveElement):
            return "wrong", type(element).__name__
        if not getattr(element, "ViewSpecific", False):
            return "wrong", "not view-specific"
        return "ok", None

    expected_family = spec.get("family")
    actual_family = _get_element_family_name(element)
    if actual_family != expected_family:
        return "wrong", actual_family or type(element).__name__
    return "ok", None


def _collect_generated_instance_ids(doc):
    from Autodesk.Revit.DB import FamilyInstance, FilteredElementCollector  # type: ignore
    from floor_common import get_id_value  # type: ignore

    result = {
        RFFamilies.TILE: [],
        RFFamilies.STRINGER: [],
        RFFamilies.SUPPORT: [],
    }
    for instance in (
        FilteredElementCollector(doc)
        .OfClass(FamilyInstance)
        .WhereElementIsNotElementType()
    ):
        family_name = _get_element_family_name(instance)
        if family_name in result:
            result[family_name].append(get_id_value(instance))
    return result


def _audit_floor_context(report, floor, record):
    report.add("Floor Context", "info", "Selected floor id", str(record["floor_id"]))

    total_linked = 0
    for spec in LAYOUT_ID_SPECS:
        total_linked += summarize_ids(record["param_ids"].get(spec["param"], []))[
            "count"
        ]
    total_linked += summarize_ids(record.get("zone_ids") or [])["count"]

    report.add("Floor Context", "info", "Tracked references", str(total_linked))


def _audit_floor_parameters(report, floor):
    from floor_common import get_double_param, get_string_param, read_floor_grid_params  # type: ignore

    try:
        params = read_floor_grid_params(floor)
        report.add(
            "Parameters",
            "pass",
            "Grid parameters",
            "step_x={:.1f}, step_y={:.1f}".format(params["step_x"], params["step_y"]),
        )
    except Exception as exc:
        report.add("Parameters", "fail", "Grid parameters", str(exc))

    status = (get_string_param(floor, P.GEN_STATUS) or "").strip()
    report.add(
        "Parameters",
        "pass" if status else "warn",
        "Generation status",
        status or "empty",
    )

    floor_height = get_double_param(floor, P.FLOOR_HEIGHT) or 0.0
    report.add(
        "Parameters",
        "pass" if floor_height > 0 else "warn",
        "Floor height",
        "{:.1f}".format(floor_height),
    )

    tile_thickness = get_double_param(floor, P.TILE_THICKNESS) or 0.0
    report.add(
        "Parameters",
        "pass" if tile_thickness > 0 else "warn",
        "Tile thickness",
        "{:.1f}".format(tile_thickness),
    )


def _audit_stored_id_spec(report, doc, record, owner_index, spec):
    source_name = spec["param"]
    label = spec["label"]
    ids = record["param_ids"].get(source_name, [])
    summary = summarize_ids(ids)
    invalid_tokens = record["invalid_tokens"].get(source_name, [])

    if invalid_tokens:
        report.add(
            "Stored IDs",
            "fail",
            "{} raw value".format(label),
            "Invalid tokens: {}".format(", ".join(invalid_tokens)),
        )

    if summary["count"] == 0:
        report.add("Stored IDs", "info", label, "No ids stored")
        return

    if summary["duplicate_ids"]:
        report.add(
            "Stored IDs",
            "warn",
            "{} duplicates".format(label),
            _format_id_list(summary["duplicate_ids"]),
        )

    missing_ids = []
    wrong_ids = []
    for int_id in summary["unique_ids"]:
        status, details = _inspect_expected_element(doc, int_id, spec)
        if status == "missing":
            missing_ids.append(int_id)
        elif status == "wrong":
            wrong_ids.append("{}({})".format(int_id, details))

    conflicts = find_conflicting_owners(
        record["floor_id"], source_name, summary["unique_ids"], owner_index
    )
    if conflicts:
        details = []
        for int_id in sorted(conflicts):
            refs = [
                "floor {} via {}".format(owner["floor_id"], owner["source"])
                for owner in conflicts[int_id]
            ]
            details.append("{} -> {}".format(int_id, "; ".join(refs)))
        report.add(
            "Stored IDs",
            "fail",
            "{} ownership".format(label),
            "Conflicts: {}".format(" | ".join(details[:4])),
        )

    if missing_ids:
        report.add(
            "Stored IDs",
            "fail",
            "{} stale ids".format(label),
            _format_id_list(missing_ids),
        )

    if wrong_ids:
        report.add(
            "Stored IDs",
            "fail",
            "{} type check".format(label),
            "Wrong elements: {}".format(", ".join(wrong_ids[:6])),
        )

    if not conflicts and not missing_ids and not wrong_ids and not invalid_tokens:
        report.add(
            "Stored IDs",
            "pass",
            label,
            "{} linked".format(len(summary["unique_ids"])),
        )


def _audit_reinforcement_zones(report, doc, record):
    if record.get("zone_error"):
        report.add(
            "Reinforcement Zones",
            "fail",
            "Zone payload",
            record["zone_error"],
        )
        return

    zone_ids = record.get("zone_ids") or []
    if not zone_ids:
        report.add("Reinforcement Zones", "info", "Zone payload", "No stored zones")
        return

    if record.get("zone_invalid"):
        report.add(
            "Reinforcement Zones",
            "warn",
            "Zone id values",
            ", ".join(record["zone_invalid"][:8]),
        )

    from Autodesk.Revit.DB import ElementId  # type: ignore

    missing_zone_ids = []
    for int_id in summarize_ids(zone_ids)["unique_ids"]:
        if doc.GetElement(ElementId(int_id)) is None:
            missing_zone_ids.append(int_id)

    if missing_zone_ids:
        report.add(
            "Reinforcement Zones",
            "fail",
            "Zone references",
            "Missing: {}".format(_format_id_list(missing_zone_ids)),
        )

    untracked = summarize_zone_membership(
        zone_ids,
        record["param_ids"].get(P.STRINGERS_TOP_ID, []),
        record["param_ids"].get(P.STRINGERS_BOTTOM_ID, []),
        record["param_ids"].get(P.SUPPORTS_ID, []),
    )
    if untracked:
        report.add(
            "Reinforcement Zones",
            "warn",
            "Zone ownership",
            "Not present in stored stringer/support ids: {}".format(
                _format_id_list(untracked)
            ),
        )

    if not missing_zone_ids and not untracked:
        report.add(
            "Reinforcement Zones",
            "pass",
            "Zone references",
            "{} linked ids".format(len(summarize_ids(zone_ids)["unique_ids"])),
        )


def _audit_global_generated_instances(report, doc, owner_index):
    orphan_map = summarize_unowned_instances(
        _collect_generated_instance_ids(doc), owner_index
    )
    if not orphan_map:
        report.add(
            "Global Ownership",
            "pass",
            "Unowned generated instances",
            "No orphan RF instances found",
        )
        return

    for family_name, ids in sorted(orphan_map.items()):
        report.add(
            "Global Ownership",
            "warn",
            "{} ownership".format(family_name),
            "Unowned ids: {}".format(_format_id_list(ids)),
        )


def run_floor_layout_audit(doc, floor):
    """Run layout ownership audit for a selected floor and return SmokeReport."""
    report = SmokeReport()

    if doc is None or floor is None:
        report.add("Floor Context", "fail", "Selected floor", "No floor selected")
        return report

    record = _get_floor_record(floor)
    all_records = _collect_floor_records(doc)
    owner_index = build_owner_index(all_records)

    _audit_floor_context(report, floor, record)
    _audit_floor_parameters(report, floor)

    for spec in LAYOUT_ID_SPECS:
        _audit_stored_id_spec(report, doc, record, owner_index, spec)

    _audit_reinforcement_zones(report, doc, record)
    _audit_global_generated_instances(report, doc, owner_index)

    return report

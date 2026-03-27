# -*- coding: utf-8 -*-
"""Canonical RF shared-parameter schema with stable GUIDs."""

import os
import shutil
from contextlib import contextmanager

SHARED_PARAM_GROUP_NAME = "RaisedFloor"
SHARED_PARAM_FILE_NAME = "RaisedFloor.sharedparameters.txt"

RF_PARAMETER_GUIDS = {
    "RF_Step_X": "aa5ed481-5cf0-5933-b251-3a290396bb12",
    "RF_Step_Y": "78a22501-2b4d-5c0b-8174-8178817fadfc",
    "RF_Base_X": "7c3e45d9-b916-5ba6-9b74-c41f435658cf",
    "RF_Base_Y": "050db1f8-b7fb-52cd-995e-3a0ee1ebff15",
    "RF_Base_Z": "584bc467-e858-5de6-99e2-afd812763215",
    "RF_Offset_X": "7f1a5a67-7f04-50de-b131-0a46965a2ad8",
    "RF_Offset_Y": "9596eb81-eac0-533d-b900-3de414c8be65",
    "RF_Floor_Height": "dcd9d808-03c5-5c3d-b49d-389f45de922e",
    "RF_Tile_Thickness": "2dcf34ea-4f6f-51e5-a4f0-afaea18daaa1",
    "RF_Gen_Status": "8e547486-8556-56d5-8894-33cb3abb25bd",
    "RF_Contour_Lines_ID": "f4318b36-1a90-5143-a9ae-f85e06bca2cb",
    "RF_Grid_Lines_ID": "8983d5ea-cc2f-514f-9567-1fb06d743312",
    "RF_Base_Marker_ID": "235a7627-f562-5eff-8b77-617fdfcc1c5e",
    "RF_Tiles_ID": "37300258-1f9e-58d9-9225-15ce34073d15",
    "RF_Stringers_Top_ID": "1a489b79-c8a6-5cd9-82c2-8101de19814a",
    "RF_Stringers_Bottom_ID": "13696026-d23a-57b8-bedc-38f51fc5a8e4",
    "RF_Reinf_Zones_JSON": "50d3eb01-9d10-5539-bb63-55c08720bf58",
    "RF_Supports_ID": "01e5e51f-5130-523b-92a9-dd598a6fb0a1",
    "RF_Bottom_Mode": "743ed647-3bb3-547e-a07c-da3d7d69cf05",
    "RF_Bottom_Step": "6360e7b6-54ed-5b6d-a291-a24059e2c0af",
    "RF_Max_Stringer_Len": "056ccb9f-cf87-5d64-95d9-e76505dc7d2a",
    "RF_Top_Direction": "6a0e5a78-e408-554a-9a98-f7d9770718da",
    "RF_Column": "979a04ee-ea89-51fa-aa05-5ebf40609007",
    "RF_Row": "b383ef29-f11a-5a57-90b7-1949e25ecc1a",
    "RF_Mark": "18e0da58-6433-5f69-b34b-6a67aaed3913",
    "RF_Tile_Type": "8fd32e94-6519-5440-bd19-8bceb049228d",
    "RF_Tile_Size_X": "d01a6b97-8275-5790-aa04-d20b86035557",
    "RF_Tile_Size_Y": "c0ae94a2-4248-5334-af1f-54e4c4825686",
    "RF_Cut_X": "ac0f1d86-9b29-500a-a4c9-66ea7f7617cb",
    "RF_Cut_Y": "a6031024-7412-59eb-bee4-36fa9f2b6ce9",
    "RF_Void1_X": "228dc86c-2945-59ed-830a-4076acaa33b6",
    "RF_Void1_Y": "6b3cdefb-7c4b-5894-8938-8688e96c60d9",
    "RF_Void1_OX": "ac1680eb-8462-5134-a5ce-dbee75e745fb",
    "RF_Void1_OY": "569af3ac-e864-5c89-afe9-4c7c19757c2d",
    "RF_Void2_X": "6495bb97-f9d9-5a3a-8700-135a4653245d",
    "RF_Void2_Y": "79c58c5f-28f5-529d-98f5-9fff59419c72",
    "RF_Void2_OX": "19bff586-da6d-55b7-bcf1-5c8ca9517aa6",
    "RF_Void2_OY": "69ed9e21-01db-5788-8884-dbc6761e2aa0",
    "RF_Void3_X": "b372225b-f8f8-576f-810d-0db3ce3688a9",
    "RF_Void3_Y": "88c0aa97-eea1-5ca9-a67f-7b316b23616f",
    "RF_Void3_OX": "c17f882d-ed84-54ca-8614-6ccbd1f1fc0e",
    "RF_Void3_OY": "3039c1a8-876c-5bce-b707-7754f95e30be",
    "RF_Stringer_Type": "ab79a808-7cde-5ae4-9445-05b1e610775e",
    "RF_Direction_Axis": "60ba28c1-81b3-5904-9331-a49aeadefe48",
    "RF_Support_Height": "3ae3fa00-35b4-5f3d-ab97-0f95c96d192b",
    "RF_Ventilated": "679ac47a-7cc4-53fe-92ab-27d1128e3c36",
    "RF_Profile_Height": "9323d0a7-ab3e-53e6-9c9f-a65df928e463",
    "RF_Profile_Width": "2fcffad5-ce38-5c01-86e6-c82a433ae1e1",
    "RF_Thickness": "d487c996-a7b4-5914-82bb-eab7bc18c5b7",
    "RF_Wall_Thickness": "212e451c-684a-52e6-8e52-63ea817ccbd5",
    "RF_Base_Size": "19a3444b-f749-5e42-9d41-e9a20122ada5",
    "RF_Head_Size": "891f3bbf-9af9-5f46-9710-e277e0cb3fbd",
}


class RFParams(object):
    """Canonical RF parameter names."""
    STEP_X = "RF_Step_X"
    STEP_Y = "RF_Step_Y"
    BASE_X = "RF_Base_X"
    BASE_Y = "RF_Base_Y"
    BASE_Z = "RF_Base_Z"
    OFFSET_X = "RF_Offset_X"
    OFFSET_Y = "RF_Offset_Y"
    FLOOR_HEIGHT = "RF_Floor_Height"
    TILE_THICKNESS = "RF_Tile_Thickness"
    GEN_STATUS = "RF_Gen_Status"
    CONTOUR_LINES_ID = "RF_Contour_Lines_ID"
    GRID_LINES_ID = "RF_Grid_Lines_ID"
    BASE_MARKER_ID = "RF_Base_Marker_ID"
    TILES_ID = "RF_Tiles_ID"
    STRINGERS_TOP_ID = "RF_Stringers_Top_ID"
    STRINGERS_BOTTOM_ID = "RF_Stringers_Bottom_ID"
    REINF_ZONES_JSON = "RF_Reinf_Zones_JSON"
    SUPPORTS_ID = "RF_Supports_ID"
    BOTTOM_MODE = "RF_Bottom_Mode"
    BOTTOM_STEP = "RF_Bottom_Step"
    MAX_STRINGER_LEN = "RF_Max_Stringer_Len"
    TOP_DIRECTION = "RF_Top_Direction"
    COLUMN = "RF_Column"
    ROW = "RF_Row"
    MARK = "RF_Mark"
    TILE_TYPE = "RF_Tile_Type"
    TILE_SIZE_X = "RF_Tile_Size_X"
    TILE_SIZE_Y = "RF_Tile_Size_Y"
    CUT_X = "RF_Cut_X"
    CUT_Y = "RF_Cut_Y"
    VOID1_X = "RF_Void1_X"
    VOID1_Y = "RF_Void1_Y"
    VOID1_OX = "RF_Void1_OX"
    VOID1_OY = "RF_Void1_OY"
    VOID2_X = "RF_Void2_X"
    VOID2_Y = "RF_Void2_Y"
    VOID2_OX = "RF_Void2_OX"
    VOID2_OY = "RF_Void2_OY"
    VOID3_X = "RF_Void3_X"
    VOID3_Y = "RF_Void3_Y"
    VOID3_OX = "RF_Void3_OX"
    VOID3_OY = "RF_Void3_OY"
    STRINGER_TYPE = "RF_Stringer_Type"
    DIRECTION_AXIS = "RF_Direction_Axis"
    SUPPORT_HEIGHT = "RF_Support_Height"
    VENTILATED = "RF_Ventilated"
    PROFILE_HEIGHT = "RF_Profile_Height"
    PROFILE_WIDTH = "RF_Profile_Width"
    THICKNESS = "RF_Thickness"
    WALL_THICKNESS = "RF_Wall_Thickness"
    BASE_SIZE = "RF_Base_Size"
    HEAD_SIZE = "RF_Head_Size"


def _validate_rfparams_constants():
    expected = {
        name[3:].upper(): name for name in sorted(RF_PARAMETER_GUIDS)
    }
    actual = {
        attr: getattr(RFParams, attr)
        for attr in dir(RFParams)
        if attr.isupper() and not attr.startswith("_")
    }

    if actual == expected:
        return

    details = []
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    mismatched = sorted(
        attr
        for attr in expected
        if attr in actual and actual[attr] != expected[attr]
    )
    if missing:
        details.append("missing={}".format(", ".join(missing)))
    if extra:
        details.append("extra={}".format(", ".join(extra)))
    if mismatched:
        details.append(
            "mismatched={}".format(
                ", ".join(
                    "{}:{}!={}".format(attr, actual[attr], expected[attr])
                    for attr in mismatched
                )
            )
        )

    raise RuntimeError(
        "RFParams constants are out of sync with RF_PARAMETER_GUIDS ({})".format(
            "; ".join(details) or "unknown mismatch"
        )
    )


_validate_rfparams_constants()


class RFFamilies(object):
    """Canonical RF family names."""

    TILE = "RF_Tile"
    STRINGER = "RF_Stringer"
    SUPPORT = "RF_Support"


RF_DOUBLE_PARAM_NAMES = (
    RFParams.STEP_X,
    RFParams.STEP_Y,
    RFParams.BASE_X,
    RFParams.BASE_Y,
    RFParams.BASE_Z,
    RFParams.OFFSET_X,
    RFParams.OFFSET_Y,
    RFParams.FLOOR_HEIGHT,
    RFParams.TILE_THICKNESS,
    RFParams.BOTTOM_STEP,
    RFParams.MAX_STRINGER_LEN,
    RFParams.TILE_SIZE_X,
    RFParams.TILE_SIZE_Y,
    RFParams.CUT_X,
    RFParams.CUT_Y,
    RFParams.VOID1_X,
    RFParams.VOID1_Y,
    RFParams.VOID1_OX,
    RFParams.VOID1_OY,
    RFParams.VOID2_X,
    RFParams.VOID2_Y,
    RFParams.VOID2_OX,
    RFParams.VOID2_OY,
    RFParams.VOID3_X,
    RFParams.VOID3_Y,
    RFParams.VOID3_OX,
    RFParams.VOID3_OY,
    RFParams.SUPPORT_HEIGHT,
    RFParams.PROFILE_HEIGHT,
    RFParams.PROFILE_WIDTH,
    RFParams.THICKNESS,
    RFParams.WALL_THICKNESS,
    RFParams.BASE_SIZE,
    RFParams.HEAD_SIZE,
)

RF_INTEGER_PARAM_NAMES = (
    RFParams.COLUMN,
    RFParams.ROW,
    RFParams.VENTILATED,
)

_string_name_set = set(RF_PARAMETER_GUIDS) - set(RF_DOUBLE_PARAM_NAMES) - set(
    RF_INTEGER_PARAM_NAMES
)
RF_STRING_PARAM_NAMES = tuple(
    name for name in RF_PARAMETER_GUIDS if name in _string_name_set
)

RF_PARAMETER_STORAGE_KINDS = {}
for _name in RF_DOUBLE_PARAM_NAMES:
    RF_PARAMETER_STORAGE_KINDS[_name] = "Double"
for _name in RF_INTEGER_PARAM_NAMES:
    RF_PARAMETER_STORAGE_KINDS[_name] = "Integer"
for _name in RF_STRING_PARAM_NAMES:
    RF_PARAMETER_STORAGE_KINDS[_name] = "String"

if set(RF_PARAMETER_STORAGE_KINDS) != set(RF_PARAMETER_GUIDS):
    raise RuntimeError(
        "RF_PARAMETER_STORAGE_KINDS is out of sync with RF_PARAMETER_GUIDS"
    )


RF_FLOOR_GRID_PARAMS = (
    RFParams.STEP_X,
    RFParams.STEP_Y,
    RFParams.BASE_X,
    RFParams.BASE_Y,
)

RF_PROJECT_PARAM_NAMES = (
    RFParams.STEP_X,
    RFParams.STEP_Y,
    RFParams.BASE_X,
    RFParams.BASE_Y,
    RFParams.BASE_Z,
    RFParams.OFFSET_X,
    RFParams.OFFSET_Y,
    RFParams.FLOOR_HEIGHT,
    RFParams.TILE_THICKNESS,
    RFParams.GEN_STATUS,
    RFParams.CONTOUR_LINES_ID,
    RFParams.GRID_LINES_ID,
    RFParams.BASE_MARKER_ID,
    RFParams.TILES_ID,
    RFParams.STRINGERS_TOP_ID,
    RFParams.STRINGERS_BOTTOM_ID,
    RFParams.REINF_ZONES_JSON,
    RFParams.SUPPORTS_ID,
    RFParams.BOTTOM_MODE,
    RFParams.BOTTOM_STEP,
    RFParams.MAX_STRINGER_LEN,
    RFParams.TOP_DIRECTION,
)

RF_GENERATED_ID_PARAMS = (
    RFParams.SUPPORTS_ID,
    RFParams.STRINGERS_TOP_ID,
    RFParams.STRINGERS_BOTTOM_ID,
    RFParams.TILES_ID,
    RFParams.GRID_LINES_ID,
    RFParams.BASE_MARKER_ID,
    RFParams.CONTOUR_LINES_ID,
)

RF_TILE_REQUIRED_INSTANCE_PARAMS = (
    RFParams.COLUMN,
    RFParams.ROW,
    RFParams.TILE_TYPE,
    RFParams.TILE_SIZE_X,
    RFParams.TILE_SIZE_Y,
    RFParams.CUT_X,
    RFParams.CUT_Y,
    RFParams.MARK,
)

RF_TILE_VOID_PARAM_GROUPS = (
    (RFParams.VOID1_X, RFParams.VOID1_Y, RFParams.VOID1_OX, RFParams.VOID1_OY),
    (RFParams.VOID2_X, RFParams.VOID2_Y, RFParams.VOID2_OX, RFParams.VOID2_OY),
    (RFParams.VOID3_X, RFParams.VOID3_Y, RFParams.VOID3_OX, RFParams.VOID3_OY),
)

RF_TILE_FAMILY_PARAM_NAMES = (
    RFParams.COLUMN,
    RFParams.ROW,
    RFParams.MARK,
    RFParams.TILE_TYPE,
    RFParams.TILE_SIZE_X,
    RFParams.TILE_SIZE_Y,
    RFParams.CUT_X,
    RFParams.CUT_Y,
    RFParams.VOID1_X,
    RFParams.VOID1_Y,
    RFParams.VOID1_OX,
    RFParams.VOID1_OY,
    RFParams.VOID2_X,
    RFParams.VOID2_Y,
    RFParams.VOID2_OX,
    RFParams.VOID2_OY,
    RFParams.VOID3_X,
    RFParams.VOID3_Y,
    RFParams.VOID3_OX,
    RFParams.VOID3_OY,
    RFParams.THICKNESS,
    RFParams.VENTILATED,
)

RF_STRINGER_FAMILY_PARAM_NAMES = (
    RFParams.MARK,
    RFParams.STRINGER_TYPE,
    RFParams.DIRECTION_AXIS,
    RFParams.PROFILE_HEIGHT,
    RFParams.PROFILE_WIDTH,
    RFParams.WALL_THICKNESS,
)

RF_SUPPORT_FAMILY_PARAM_NAMES = (
    RFParams.COLUMN,
    RFParams.ROW,
    RFParams.MARK,
    RFParams.SUPPORT_HEIGHT,
    RFParams.BASE_SIZE,
    RFParams.HEAD_SIZE,
)

def _unique_names(names):
    seen = set()
    result = []
    for name in names:
        if name in seen:
            continue
        seen.add(name)
        result.append(name)
    return tuple(result)


RF_ALL_FAMILY_PARAM_NAMES = _unique_names(
    RF_TILE_FAMILY_PARAM_NAMES
    + RF_STRINGER_FAMILY_PARAM_NAMES
    + RF_SUPPORT_FAMILY_PARAM_NAMES
)

RF_STRINGER_REQUIRED_FLOOR_PARAMS = (
    RFParams.STRINGERS_TOP_ID,
    RFParams.STRINGERS_BOTTOM_ID,
    RFParams.BOTTOM_MODE,
    RFParams.BOTTOM_STEP,
    RFParams.MAX_STRINGER_LEN,
    RFParams.TOP_DIRECTION,
)


def get_bundled_shared_parameter_file_path():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(root, "resources", SHARED_PARAM_FILE_NAME)


def get_canonical_shared_parameter_file_path():
    root = (
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("TEMP")
        or os.path.expanduser("~")
    )
    return os.path.join(
        root,
        "RaisedFloor.extension",
        "sharedparams",
        SHARED_PARAM_FILE_NAME,
    )


def _shared_parameter_file_header():
    return (
        "# RaisedFloor canonical shared parameter file.\n"
        "# Managed by the extension; GUIDs are part of the repo contract.\n"
        "*META\tVERSION\tMINVERSION\n"
        "META\t2\t1\n"
        "*GROUP\tID\tNAME\n"
        "*PARAM\tGUID\tNAME\tDATATYPE\tDATACATEGORY\tGROUP\tVISIBLE\tDESCRIPTION\tUSERMODIFIABLE\n"
    )


def ensure_canonical_shared_parameter_file(path=None):
    use_default_path = not path
    if not path:
        path = get_canonical_shared_parameter_file_path()

    folder = os.path.dirname(path)
    if folder and not os.path.exists(folder):
        os.makedirs(folder)

    bundled_path = get_bundled_shared_parameter_file_path()
    if (
        use_default_path
        and path != bundled_path
        and os.path.exists(bundled_path)
        and os.path.getsize(bundled_path) > 0
    ):
        shutil.copy2(bundled_path, path)

    if not os.path.exists(path) or os.path.getsize(path) == 0:
        with open(path, "w") as fp:
            fp.write(_shared_parameter_file_header())

    return path


@contextmanager
def use_canonical_shared_parameter_file(app, path=None):
    canonical_path = ensure_canonical_shared_parameter_file(path)
    original_path = app.SharedParametersFilename or ""
    app.SharedParametersFilename = canonical_path
    try:
        yield canonical_path
    finally:
        app.SharedParametersFilename = original_path


def get_expected_guid(name):
    guid = RF_PARAMETER_GUIDS.get(name)
    if not guid:
        raise KeyError("RF shared-parameter schema has no GUID for '{}'".format(name))
    return guid


def get_parameter_storage_kind(name):
    return RF_PARAMETER_STORAGE_KINDS.get(name)


def _normalize_guid_text(value):
    return str(value).strip().lower()


def _get_definition_guid_text(definition):
    try:
        guid = definition.GUID
    except Exception:
        return None

    if guid is None:
        return None

    return str(guid).strip()


def _validate_existing_definition(definition, expected_guid):
    actual_guid = _get_definition_guid_text(definition)
    if not actual_guid:
        return

    if _normalize_guid_text(actual_guid) != _normalize_guid_text(expected_guid):
        raise Exception(
            "Canonical shared parameter GUID mismatch for '{}': {} != {}".format(
                definition.Name, actual_guid, expected_guid
            )
        )


def ensure_schema_definitions(app, definition_specs):
    """Ensure canonical shared definitions exist and return them by name.

    definition_specs: iterable of dicts with keys:
      - name
      - description
      - param_type
    """
    from Autodesk.Revit.DB import ExternalDefinitionCreationOptions  # type: ignore
    from System import Guid  # type: ignore

    with use_canonical_shared_parameter_file(app) as canonical_path:
        sp_file = app.OpenSharedParameterFile()
        if not sp_file:
            raise Exception(
                "Could not open canonical shared parameter file:\n{}".format(
                    canonical_path
                )
            )

        group = None
        for existing_group in sp_file.Groups:
            if existing_group and existing_group.Name == SHARED_PARAM_GROUP_NAME:
                group = existing_group
                break

        if group is None:
            group = sp_file.Groups.Create(SHARED_PARAM_GROUP_NAME)

        existing_defs = {}
        for definition in group.Definitions:
            if definition and definition.Name:
                existing_defs[definition.Name] = definition

        result = {}
        for spec in definition_specs:
            name = spec["name"]
            expected_guid = get_expected_guid(name)
            current = existing_defs.get(name)
            if current is not None:
                _validate_existing_definition(current, expected_guid)
                result[name] = current
                continue

            opts = ExternalDefinitionCreationOptions(name, spec["param_type"])
            opts.Description = spec.get("description", "")
            opts.GUID = Guid(expected_guid)
            created = group.Definitions.Create(opts)
            if not created:
                raise Exception(
                    "Failed to create canonical shared parameter '{}'".format(name)
                )
            result[name] = created

        return result


def collect_definition_guid_mismatches(definitions_by_name, allowed_names=None):
    """Return [(name, actual_guid, expected_guid)] for legacy mismatches."""
    mismatches = []
    candidate_names = allowed_names or definitions_by_name.keys()

    for name in sorted(candidate_names):
        if name not in RF_PARAMETER_GUIDS:
            continue
        definition = definitions_by_name.get(name)
        if definition is None:
            continue

        expected_guid = get_expected_guid(name)
        actual_guid = _get_definition_guid_text(definition)
        if not actual_guid:
            continue

        if _normalize_guid_text(actual_guid) != _normalize_guid_text(expected_guid):
            mismatches.append((name, actual_guid, expected_guid))

    return mismatches


def collect_project_parameter_guid_mismatches(doc, allowed_names=None, bound_names=None):
    """Inspect loaded SharedParameterElements and report canonical GUID mismatches.

    Returns tuples: (name, actual_guid_marker, expected_guid)
    where actual_guid_marker may be '<not-shared-or-unresolved>' if a bound RF_
    parameter exists in the project but no SharedParameterElement with that name
    can be resolved.
    """
    from Autodesk.Revit.DB import FilteredElementCollector, SharedParameterElement  # type: ignore

    candidate_names = allowed_names or RF_PARAMETER_GUIDS.keys()
    bound_name_set = set(bound_names or [])

    actual_guid_by_name = {}
    for shared_param in FilteredElementCollector(doc).OfClass(SharedParameterElement):
        try:
            name = shared_param.Name
        except Exception:
            try:
                definition = shared_param.GetDefinition()
                name = definition.Name if definition else None
            except Exception:
                name = None

        if not name:
            continue

        try:
            guid_value = shared_param.GuidValue
        except Exception:
            guid_value = None

        if guid_value is None:
            continue

        actual_guid_by_name[name] = str(guid_value).strip()

    mismatches = []
    for name in sorted(candidate_names):
        if name not in RF_PARAMETER_GUIDS:
            continue
        if bound_name_set and name not in bound_name_set:
            continue

        expected_guid = get_expected_guid(name)
        actual_guid = actual_guid_by_name.get(name)
        if not actual_guid:
            mismatches.append((name, "<not-shared-or-unresolved>", expected_guid))
            continue

        if _normalize_guid_text(actual_guid) != _normalize_guid_text(expected_guid):
            mismatches.append((name, actual_guid, expected_guid))

    return mismatches


def collect_family_parameter_guid_mismatches(fam_doc, allowed_names=None):
    """Inspect FamilyManager parameters and return legacy GUID mismatches."""
    fam_mgr = fam_doc.FamilyManager
    mismatches = []

    for param in fam_mgr.GetParameters():
        try:
            definition = param.Definition
            name = definition.Name if definition else None
        except Exception:
            continue
        if not name:
            continue
        if allowed_names and name not in allowed_names:
            continue
        if name not in RF_PARAMETER_GUIDS:
            continue

        expected_guid = get_expected_guid(name)
        try:
            is_shared = bool(param.IsShared)
        except Exception:
            is_shared = False

        actual_guid = None
        if is_shared:
            try:
                guid_value = param.GUID
            except Exception:
                guid_value = None
            if guid_value is not None:
                actual_guid = str(guid_value).strip()
            else:
                actual_guid = "<no-guid>"
        else:
            actual_guid = "<not-shared>"

        if _normalize_guid_text(actual_guid) != _normalize_guid_text(expected_guid):
            mismatches.append((name, actual_guid, expected_guid))

    return mismatches

# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (  # type: ignore
    BuiltInCategory,
    Color,
    ElementId,
    Options,
    PlanarFace,
    Solid,
    ViewPlan,
)
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import (  # type: ignore
    FloorOrPartSelectionFilter,
    delete_elements_by_ids,
    get_id_value,
    get_or_create_line_style,
    get_source_floor,
    get_string_param,
    parse_ids_from_string,
    set_double_param,
    set_string_param,
)
from floor_grid import redraw_grid_for_floor  # type: ignore
from floor_i18n import tr  # type: ignore
from revit_context import get_active_view, get_doc, get_uidoc  # type: ignore
from pyrevit import forms, revit  # type: ignore

TITLE_PREPARE_ALL = tr("prepare_all_title")
CONTOUR_STYLE_NAME = "RF_Contour"
CONTOUR_COLOR = Color(0, 255, 0)

def mm_to_internal(mm_value):
    return float(mm_value) / 304.8


def ask_mm_value(title, prompt, default_value):
    text_val = forms.ask_for_string(
        default=str(default_value), prompt=prompt, title=title
    )
    if text_val is None:
        return None
    text_val = text_val.replace(",", ".").strip()
    try:
        return float(text_val)
    except Exception:
        forms.alert(
            tr("invalid_number_fmt", value=text_val),
            title=title,
        )
        return None


def get_top_face_and_loops(floor):
    view = get_active_view()
    opt = Options()
    opt.ComputeReferences = True
    if view:
        opt.DetailLevel = view.DetailLevel

    doc = get_doc()
    geom = floor.get_Geometry(opt)
    if not geom:
        return None, None

    best_face = None
    best_z = None

    for geom_obj in geom:
        solid = geom_obj if isinstance(geom_obj, Solid) else None
        if not solid or solid.Volume <= 0:
            continue

        for face in solid.Faces:
            planar_face = face if isinstance(face, PlanarFace) else None
            if not planar_face:
                continue
            if abs(planar_face.FaceNormal.Z - 1.0) < 1e-6:
                z_coord = planar_face.Origin.Z
                if best_face is None or z_coord > best_z:
                    best_face = planar_face
                    best_z = z_coord

    if not best_face:
        return None, None

    try:
        return best_face, best_face.GetEdgesAsCurveLoops()
    except Exception:
        return best_face, None


def _resolve_floor(floor_id_int):
    doc = get_doc()
    if not doc:
        raise Exception(tr("source_floor_not_found"))

    floor = None
    try:
        floor = doc.GetElement(ElementId(int(floor_id_int)))
    except Exception:
        floor = None

    if not floor:
        raise Exception(tr("source_floor_not_found"))

    try:
        is_valid = bool(floor.IsValidObject)
    except Exception:
        is_valid = False
    if not is_valid:
        raise Exception(tr("source_floor_not_found"))

    return floor


def rebuild_contour_for_floor(floor_id_int):
    view = get_active_view()
    if not isinstance(view, ViewPlan):
        raise Exception(tr("prepare_all_open_plan"))

    floor = _resolve_floor(floor_id_int)
    face, edge_loops = get_top_face_and_loops(floor)
    if not face or not edge_loops:
        raise Exception(tr("contour_face_not_found"))

    # Клонируем кривые ДО транзакции — внутри транзакции ссылки на
    # геометрию элемента могут стать невалидными.
    curves = []
    for loop in edge_loops:
        for curve in loop:
            curves.append(curve.Clone())
    loop_count = edge_loops.Count if edge_loops else 0

    old_ids = parse_ids_from_string(get_string_param(floor, "RF_Contour_Lines_ID"))
    ids_to_delete = old_ids

    created_ids = []
    with revit.Transaction(tr("tx_draw_contour")):
        contour_style = get_or_create_line_style(
            doc,
            CONTOUR_STYLE_NAME,
            color=CONTOUR_COLOR,
            weight=5,
            update_existing=True,
        )

        deleted_count = delete_elements_by_ids(ids_to_delete)

        for crv in curves:
            try:
                detail_curve = doc.Create.NewDetailCurve(view, crv)
                detail_curve.LineStyle = contour_style
                created_ids.append(str(get_id_value(detail_curve.Id)))
            except Exception:
                pass

        floor_for_write = _resolve_floor(floor_id_int)
        if not set_string_param(
            floor_for_write,
            "RF_Contour_Lines_ID",
            ";".join(created_ids),
        ):
            raise Exception(tr("contour_write_failed"))

    return {
        "deleted_count": deleted_count,
        "created_count": len(created_ids),
        "loop_count": loop_count,
    }


try:
    doc = get_doc()
    uidoc = get_uidoc()
    view = get_active_view()

    if not doc or not uidoc:
        raise Exception(tr("source_floor_not_found"))

    if not isinstance(view, ViewPlan):
        forms.alert(
            tr("prepare_all_open_plan"),
            title=TITLE_PREPARE_ALL,
        )
        raise Exception("Active view is not a plan")

    pick_filter = FloorOrPartSelectionFilter()
    ref = uidoc.Selection.PickObject(
        ObjectType.Element,
        pick_filter,
        tr("prepare_all_pick_floor"),
    )
    picked_el = doc.GetElement(ref.ElementId)
    floor = get_source_floor(picked_el)

    if not floor or not floor.Category:
        forms.alert(tr("invalid_element"), title=TITLE_PREPARE_ALL)
        raise Exception("Invalid element")

    if get_id_value(floor.Category.Id) != int(BuiltInCategory.OST_Floors):
        forms.alert(tr("element_not_floor"), title=TITLE_PREPARE_ALL)
        raise Exception("Element is not a floor")

    floor_id_int = get_id_value(floor.Id)

    base_point = uidoc.Selection.PickPoint(tr("base_point_prompt"))

    step_x_mm = ask_mm_value(TITLE_PREPARE_ALL, tr("prompt_step_x"), 600)
    if step_x_mm is None:
        raise OperationCanceledException()

    step_y_mm = ask_mm_value(TITLE_PREPARE_ALL, tr("prompt_step_y"), 600)
    if step_y_mm is None:
        raise OperationCanceledException()

    height_mm = ask_mm_value(TITLE_PREPARE_ALL, tr("prompt_floor_height"), 500)
    if height_mm is None:
        raise OperationCanceledException()

    tile_thickness_mm = ask_mm_value(TITLE_PREPARE_ALL, tr("prompt_tile_thickness"), 40)
    if tile_thickness_mm is None:
        raise OperationCanceledException()

    missing_params = []
    with revit.Transaction(tr("tx_prepare_floor")):
        floor_for_write = _resolve_floor(floor_id_int)
        pairs = [
            ("RF_Step_X", mm_to_internal(step_x_mm)),
            ("RF_Step_Y", mm_to_internal(step_y_mm)),
            ("RF_Offset_X", 0.0),
            ("RF_Offset_Y", 0.0),
            ("RF_Base_X", base_point.X),
            ("RF_Base_Y", base_point.Y),
            ("RF_Base_Z", base_point.Z),
            ("RF_Floor_Height", mm_to_internal(height_mm)),
            ("RF_Tile_Thickness", mm_to_internal(tile_thickness_mm)),
        ]
        for name, val in pairs:
            if not set_double_param(floor_for_write, name, val):
                missing_params.append(name)
        if not set_string_param(
            floor_for_write,
            "RF_Gen_Status",
            tr("status_prepared"),
        ):
            missing_params.append("RF_Gen_Status")

    if missing_params:
        raise Exception(
            tr("prepare_all_write_failed", missing="\n- ".join(missing_params))
        )

    contour_result = rebuild_contour_for_floor(floor_id_int)
    floor_for_grid = _resolve_floor(floor_id_int)
    grid_result = redraw_grid_for_floor(
        floor_for_grid,
        view,
        tr("tx_redraw_grid"),
        update_style=True,
    )

    forms.alert(
        tr(
            "prepare_all_done",
            floor_id=floor_id_int,
            step_x=step_x_mm,
            step_y=step_y_mm,
            height=height_mm,
            tile_thickness=tile_thickness_mm,
            loops=contour_result["loop_count"],
            del_contour=contour_result["deleted_count"],
            new_contour=contour_result["created_count"],
            del_grid=grid_result["deleted_count"],
            new_grid=grid_result["created_count"],
        ),
        title=TITLE_PREPARE_ALL,
    )

except OperationCanceledException:
    forms.alert(tr("operation_cancelled"), title=TITLE_PREPARE_ALL)

except Exception as ex:
    forms.alert(tr("error_fmt", error=str(ex)), title=TITLE_PREPARE_ALL)

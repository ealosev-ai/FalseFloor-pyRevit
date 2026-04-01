# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (  # type: ignore
    BuiltInCategory,
    Color,
    ElementId,
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
from floor_base import get_canonical_base_point, get_top_face_and_loops  # type: ignore
from floor_grid import redraw_grid_for_floor  # type: ignore
from floor_i18n import tr  # type: ignore
from rf_param_schema import RFParams as P  # type: ignore
from revit_context import get_active_view, get_doc, get_uidoc  # type: ignore
from pyrevit import forms, revit  # type: ignore
from rf_reporting import ScriptReporter  # type: ignore

TITLE_PREPARE_ALL = tr("prepare_all_title")
CONTOUR_STYLE_NAME = "RF_Contour"
CONTOUR_COLOR = Color(0, 255, 0)


def _append_log_path(text, reporter):
    if reporter and reporter.log_path:
        return text + "\n\nLog: {}".format(reporter.log_path)
    return text


reporter = None
reporter_done = False


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
    face, edge_loops = get_top_face_and_loops(floor, view=view)
    if not face or not edge_loops:
        raise Exception(tr("contour_face_not_found"))

    # Клонируем кривые ДО транзакции — внутри транзакции ссылки на
    # геометрию элемента могут стать невалидными.
    curves = []
    for loop in edge_loops:
        for curve in loop:
            curves.append(curve.Clone())
    loop_count = edge_loops.Count if edge_loops else 0

    old_ids = parse_ids_from_string(get_string_param(floor, P.CONTOUR_LINES_ID))
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
            P.CONTOUR_LINES_ID,
            ";".join(created_ids),
        ):
            raise Exception(tr("contour_write_failed"))

    return {
        "deleted_count": deleted_count,
        "created_count": len(created_ids),
        "loop_count": loop_count,
    }


try:
    reporter = ScriptReporter.from_pyrevit(
        title=TITLE_PREPARE_ALL,
        log_stem="setup_all",
    )
    reporter.stage("Prepare All")

    doc = get_doc()
    uidoc = get_uidoc()
    view = get_active_view()

    if not doc or not uidoc:
        raise Exception(tr("source_floor_not_found"))

    if view is not None:
        reporter.info("Active view: {}".format(getattr(view, "Name", "<unnamed>")))

    if not isinstance(view, ViewPlan):
        reporter.warning("Active view is not a plan view")
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
        reporter.warning("Selected element is invalid or has no category")
        forms.alert(tr("invalid_element"), title=TITLE_PREPARE_ALL)
        raise Exception("Invalid element")

    if get_id_value(floor.Category.Id) != int(BuiltInCategory.OST_Floors):
        reporter.warning("Selected element is not a floor")
        forms.alert(tr("element_not_floor"), title=TITLE_PREPARE_ALL)
        raise Exception("Element is not a floor")

    floor_id_int = get_id_value(floor.Id)
    reporter.info("Selected floor id: {}".format(floor_id_int))

    base_point = get_canonical_base_point(floor, view=view)
    if not base_point:
        raise Exception(tr("contour_face_not_found"))
    reporter.info(
        "Canonical base point: X={:.3f}, Y={:.3f}, Z={:.3f}".format(
            base_point.X,
            base_point.Y,
            base_point.Z,
        )
    )

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

    reporter.stage("Collected Inputs")
    reporter.info("Step X: {} mm".format(step_x_mm))
    reporter.info("Step Y: {} mm".format(step_y_mm))
    reporter.info("Floor height: {} mm".format(height_mm))
    reporter.info("Tile thickness: {} mm".format(tile_thickness_mm))

    missing_params = []
    reporter.stage("Write Floor Parameters")
    with revit.Transaction(tr("tx_prepare_floor")):
        floor_for_write = _resolve_floor(floor_id_int)
        pairs = [
            (P.STEP_X, mm_to_internal(step_x_mm)),
            (P.STEP_Y, mm_to_internal(step_y_mm)),
            (P.OFFSET_X, 0.0),
            (P.OFFSET_Y, 0.0),
            (P.BASE_X, base_point.X),
            (P.BASE_Y, base_point.Y),
            (P.BASE_Z, base_point.Z),
            (P.FLOOR_HEIGHT, mm_to_internal(height_mm)),
            (P.TILE_THICKNESS, mm_to_internal(tile_thickness_mm)),
        ]
        for name, val in pairs:
            if not set_double_param(floor_for_write, name, val):
                missing_params.append(name)
        if not set_string_param(
            floor_for_write,
            P.GEN_STATUS,
            tr("status_prepared"),
        ):
            missing_params.append(P.GEN_STATUS)

    if missing_params:
        raise Exception(
            tr("prepare_all_write_failed", missing="\n- ".join(missing_params))
        )
    reporter.info("Floor parameters written successfully")

    reporter.stage("Rebuild Contour")
    contour_result = rebuild_contour_for_floor(floor_id_int)
    reporter.info(
        "Contour rebuilt: loops={loops}, deleted={deleted}, created={created}".format(
            loops=contour_result["loop_count"],
            deleted=contour_result["deleted_count"],
            created=contour_result["created_count"],
        )
    )

    reporter.stage("Redraw Grid")
    floor_for_grid = _resolve_floor(floor_id_int)
    grid_result = redraw_grid_for_floor(
        floor_for_grid,
        view,
        tr("tx_redraw_grid"),
        update_style=True,
    )
    reporter.info(
        "Grid redrawn: deleted={deleted}, created={created}".format(
            deleted=grid_result["deleted_count"],
            created=grid_result["created_count"],
        )
    )

    result_text = tr(
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
    )
    reporter.stage("Result")
    for line in result_text.splitlines():
        reporter.info(line)
    reporter.finish()
    reporter_done = True

    forms.alert(
        _append_log_path(result_text, reporter),
        title=TITLE_PREPARE_ALL,
    )

except OperationCanceledException:
    if reporter and not reporter_done:
        reporter.warning("Operation cancelled")
        reporter.finish()
        reporter_done = True
    forms.alert(
        _append_log_path(tr("operation_cancelled"), reporter),
        title=TITLE_PREPARE_ALL,
    )

except Exception as ex:
    if reporter and not reporter_done:
        reporter.error(str(ex))
        reporter.finish()
        reporter_done = True
    forms.alert(
        _append_log_path(tr("error_fmt", error=str(ex)), reporter),
        title=TITLE_PREPARE_ALL,
    )

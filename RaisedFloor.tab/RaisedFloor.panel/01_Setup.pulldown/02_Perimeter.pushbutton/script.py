# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (  # type: ignore
    Color,
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
    get_or_create_line_style,
    get_source_floor,
    get_string_param,
    parse_ids_from_string,
    set_string_param,
)
from floor_i18n import tr  # type: ignore
from floor_ui import TITLE_CONTOUR  # type: ignore
from pyrevit import forms, revit  # type: ignore
from revit_context import get_active_view, get_doc, get_uidoc  # type: ignore

doc = None
uidoc = None
view = None

CONTOUR_STYLE_NAME = "RF_Contour"
CONTOUR_COLOR = Color(0, 255, 0)  # ярко-зелёный


def get_top_face_and_loops(floor):
    """Находит верхнюю PlanarFace перекрытия и возвращает (face, edge_loops)."""
    opt = Options()
    opt.ComputeReferences = True
    opt.DetailLevel = view.DetailLevel

    geom = floor.get_Geometry(opt)
    if not geom:
        return None, None

    best_face = None
    best_z = None

    for g in geom:
        solid = g if isinstance(g, Solid) else None
        if not solid or solid.Volume <= 0:
            continue

        for face in solid.Faces:
            pf = face if isinstance(face, PlanarFace) else None
            if not pf:
                continue
            if abs(pf.FaceNormal.Z - 1.0) < 1e-6:
                z = pf.Origin.Z
                if best_face is None or z > best_z:
                    best_face = pf
                    best_z = z

    if not best_face:
        return None, None

    try:
        return best_face, best_face.GetEdgesAsCurveLoops()
    except Exception:
        return best_face, None


try:
    doc = get_doc()
    uidoc = get_uidoc()
    view = get_active_view()

    if not doc or not uidoc:
        raise Exception(tr("source_floor_not_found"))

    if not isinstance(view, ViewPlan):
        forms.alert(
            tr("open_plan_contour"),
            title=TITLE_CONTOUR,
        )
        raise Exception("Active view is not a plan")

    pick_filter = FloorOrPartSelectionFilter()
    ref = uidoc.Selection.PickObject(
        ObjectType.Element,
        pick_filter,
        tr("pick_floor_or_part_prompt"),
    )

    picked_el = doc.GetElement(ref.ElementId)
    floor = get_source_floor(picked_el)

    if not floor:
        forms.alert(
            tr("contour_source_not_found"),
            title=TITLE_CONTOUR,
        )
        raise Exception("Source floor not found")

    face, edge_loops = get_top_face_and_loops(floor)

    if not face or not edge_loops:
        forms.alert(
            tr("contour_face_not_found"),
            title=TITLE_CONTOUR,
        )
        raise Exception("Top face or loops not found")

    # Клонируем кривые ДО транзакции — внутри ссылки геометрии невалидны
    curves = []
    for loop in edge_loops:
        for curve in loop:
            curves.append(curve.Clone())

    # ID для удаления: только линии текущего перекрытия
    old_ids = parse_ids_from_string(get_string_param(floor, "RF_Contour_Lines_ID"))
    ids_to_delete = old_ids

    created_ids = []
    deleted_count = 0

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
                dc = doc.Create.NewDetailCurve(view, crv)
                dc.LineStyle = contour_style
                created_ids.append(str(dc.Id.Value))
            except Exception:
                pass

        ids_string = ";".join(created_ids)
        ok = set_string_param(floor, "RF_Contour_Lines_ID", ids_string)
        if not ok:
            raise Exception(tr("contour_write_failed"))

    forms.alert(
        tr(
            "contour_done",
            floor_id=floor.Id.Value,
            deleted=deleted_count,
            created=len(created_ids),
            loops=edge_loops.Count if edge_loops else 0,
        ),
        title=TITLE_CONTOUR,
    )

except OperationCanceledException:
    forms.alert(tr("operation_cancelled"), title=TITLE_CONTOUR)

except Exception as ex:
    forms.alert(tr("error_fmt", error=str(ex)), title=TITLE_CONTOUR)

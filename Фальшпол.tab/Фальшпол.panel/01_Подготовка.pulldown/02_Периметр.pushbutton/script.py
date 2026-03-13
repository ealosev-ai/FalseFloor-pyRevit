# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (  # type: ignore
    Color,
    CurveElement,
    FilteredElementCollector,
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
    get_line_style_id,
    get_or_create_line_style,
    get_source_floor,
    get_string_param,
    parse_ids_from_string,
    set_string_param,
)
from floor_ui import TITLE_CONTOUR  # type: ignore
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView

CONTOUR_STYLE_NAME = "ФП_Контур"
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


def _collect_styled_contour_ids(style_id):
    """Собирает Id всех CurveElement со стилем ФП_Контур."""
    ids = []
    if not style_id:
        return ids

    collector = FilteredElementCollector(doc).OfClass(CurveElement)
    for curve_el in collector:
        try:
            ls = curve_el.LineStyle
            if ls and ls.Id == style_id:
                ids.append(curve_el.Id.IntegerValue)
        except Exception:
            pass

    return ids


try:
    if not isinstance(view, ViewPlan):
        forms.alert(
            "Открой план, чтобы построить контур.",
            title=TITLE_CONTOUR,
        )
        raise Exception("Active view is not a plan")

    pick_filter = FloorOrPartSelectionFilter()
    ref = uidoc.Selection.PickObject(
        ObjectType.Element,
        pick_filter,
        "Выберите перекрытие фальшпола или его часть",
    )

    picked_el = doc.GetElement(ref.ElementId)
    floor = get_source_floor(picked_el)

    if not floor:
        forms.alert(
            "Не удалось определить исходное перекрытие.",
            title=TITLE_CONTOUR,
        )
        raise Exception("Source floor not found")

    face, edge_loops = get_top_face_and_loops(floor)

    if not face or not edge_loops:
        forms.alert(
            "Не удалось получить верхнюю грань или её контуры.",
            title=TITLE_CONTOUR,
        )
        raise Exception("Top face or loops not found")

    # ID для удаления: сохранённые + fallback по стилю
    old_ids = parse_ids_from_string(get_string_param(floor, "FP_ID_ЛинийКонтура"))
    style_id = get_line_style_id(doc, CONTOUR_STYLE_NAME)
    styled_ids = _collect_styled_contour_ids(style_id) if style_id else []

    ids_to_delete = list(set(old_ids + styled_ids))

    created_ids = []
    deleted_count = 0

    with revit.Transaction("Обвести контур фальшпола"):
        contour_style = get_or_create_line_style(
            doc,
            CONTOUR_STYLE_NAME,
            color=CONTOUR_COLOR,
            weight=5,
            update_existing=True,
        )

        deleted_count = delete_elements_by_ids(ids_to_delete)

        for loop in edge_loops:
            for curve in loop:
                try:
                    dc = doc.Create.NewDetailCurve(view, curve)
                    dc.LineStyle = contour_style
                    created_ids.append(str(dc.Id.Value))
                except Exception:
                    pass

        ids_string = ";".join(created_ids)
        ok = set_string_param(floor, "FP_ID_ЛинийКонтура", ids_string)
        if not ok:
            raise Exception("Не удалось записать FP_ID_ЛинийКонтура")

    forms.alert(
        "Готово.\n\n"
        "ID перекрытия: {}\n"
        "Удалено старых линий: {}\n"
        "Создано новых линий: {}\n"
        "Контуров найдено: {}".format(
            floor.Id.Value,
            deleted_count,
            len(created_ids),
            edge_loops.Count if edge_loops else 0,
        ),
        title=TITLE_CONTOUR,
    )

except OperationCanceledException:
    forms.alert("Операция отменена.", title=TITLE_CONTOUR)

except Exception as ex:
    forms.alert("Ошибка:\n{}".format(str(ex)), title=TITLE_CONTOUR)

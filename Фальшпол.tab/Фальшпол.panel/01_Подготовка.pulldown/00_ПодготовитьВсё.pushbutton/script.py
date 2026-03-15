# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (  # type: ignore
    BuiltInCategory,
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
    get_id_value,
    get_line_style_id,
    get_or_create_line_style,
    get_source_floor,
    get_string_param,
    parse_ids_from_string,
    set_double_param,
    set_string_param,
)
from floor_grid import redraw_grid_for_floor  # type: ignore
from pyrevit import forms, revit  # type: ignore

TITLE_PREPARE_ALL = "00 Подготовить всё"
CONTOUR_STYLE_NAME = "ФП_Контур"
CONTOUR_COLOR = Color(0, 255, 0)

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView


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
            "Не удалось преобразовать '{}' в число.".format(text_val),
            title=title,
        )
        return None


def get_top_face_and_loops(floor):
    opt = Options()
    opt.ComputeReferences = True
    opt.DetailLevel = view.DetailLevel

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


def collect_styled_contour_ids(style_id):
    ids = []
    if not style_id:
        return ids

    collector = FilteredElementCollector(doc).OfClass(CurveElement)
    for curve_el in collector:
        try:
            line_style = curve_el.LineStyle
            if line_style and line_style.Id == style_id:
                ids.append(get_id_value(curve_el.Id))
        except Exception:
            pass

    return ids


def rebuild_contour_for_floor(floor):
    face, edge_loops = get_top_face_and_loops(floor)
    if not face or not edge_loops:
        raise Exception("Не удалось получить верхнюю грань или её контуры.")

    old_ids = parse_ids_from_string(get_string_param(floor, "FP_ID_ЛинийКонтура"))
    style_id = get_line_style_id(doc, CONTOUR_STYLE_NAME)
    styled_ids = collect_styled_contour_ids(style_id) if style_id else []
    ids_to_delete = list(set(old_ids + styled_ids))

    created_ids = []
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
                    detail_curve = doc.Create.NewDetailCurve(view, curve)
                    detail_curve.LineStyle = contour_style
                    created_ids.append(str(get_id_value(detail_curve.Id)))
                except Exception:
                    pass

        if not set_string_param(floor, "FP_ID_ЛинийКонтура", ";".join(created_ids)):
            raise Exception("Не удалось записать FP_ID_ЛинийКонтура")

    return {
        "deleted_count": deleted_count,
        "created_count": len(created_ids),
        "loop_count": edge_loops.Count if edge_loops else 0,
    }


try:
    if not isinstance(view, ViewPlan):
        forms.alert(
            "Открой план, чтобы выполнить полную подготовку.",
            title=TITLE_PREPARE_ALL,
        )
        raise Exception("Active view is not a plan")

    pick_filter = FloorOrPartSelectionFilter()
    ref = uidoc.Selection.PickObject(
        ObjectType.Element,
        pick_filter,
        "Выберите управляющее перекрытие фальшпола",
    )
    picked_el = doc.GetElement(ref.ElementId)
    floor = get_source_floor(picked_el)

    if not floor or not floor.Category:
        forms.alert("Элемент не найден или без категории.", title=TITLE_PREPARE_ALL)
        raise Exception("Invalid element")

    if get_id_value(floor.Category.Id) != int(BuiltInCategory.OST_Floors):
        forms.alert(
            "Выбранный элемент не является перекрытием.", title=TITLE_PREPARE_ALL
        )
        raise Exception("Element is not a floor")

    base_point = uidoc.Selection.PickPoint("Укажите базовую точку раскладки")

    step_x_mm = ask_mm_value(TITLE_PREPARE_ALL, "Введите шаг X, мм", 600)
    if step_x_mm is None:
        raise OperationCanceledException()

    step_y_mm = ask_mm_value(TITLE_PREPARE_ALL, "Введите шаг Y, мм", 600)
    if step_y_mm is None:
        raise OperationCanceledException()

    height_mm = ask_mm_value(TITLE_PREPARE_ALL, "Введите высоту фальшпола, мм", 500)
    if height_mm is None:
        raise OperationCanceledException()

    missing_params = []
    with revit.Transaction("Подготовить перекрытие фальшпола"):
        pairs = [
            ("FP_Шаг_X", mm_to_internal(step_x_mm)),
            ("FP_Шаг_Y", mm_to_internal(step_y_mm)),
            ("FP_Смещение_X", 0.0),
            ("FP_Смещение_Y", 0.0),
            ("FP_База_X", base_point.X),
            ("FP_База_Y", base_point.Y),
            ("FP_База_Z", base_point.Z),
            ("FP_Высота_Фальшпола", mm_to_internal(height_mm)),
        ]
        for name, val in pairs:
            if not set_double_param(floor, name, val):
                missing_params.append(name)
        if not set_string_param(floor, "FP_Статус_Генерации", "Подготовлено"):
            missing_params.append("FP_Статус_Генерации")

    if missing_params:
        raise Exception(
            "Не удалось записать параметры:\n- {}".format("\n- ".join(missing_params))
        )

    contour_result = rebuild_contour_for_floor(floor)
    grid_result = redraw_grid_for_floor(
        floor,
        view,
        "Построить сетку фальшпола",
        update_style=True,
    )

    forms.alert(
        "Готово.\n\n"
        "ID перекрытия: {}\n"
        "Шаг: {} x {} мм\n"
        "Высота фальшпола: {} мм\n"
        "Контуров найдено: {}\n"
        "Удалено старых линий контура: {}\n"
        "Создано новых линий контура: {}\n"
        "Удалено старых линий сетки: {}\n"
        "Создано новых линий сетки: {}".format(
            get_id_value(floor.Id),
            step_x_mm,
            step_y_mm,
            height_mm,
            contour_result["loop_count"],
            contour_result["deleted_count"],
            contour_result["created_count"],
            grid_result["deleted_count"],
            grid_result["created_count"],
        ),
        title=TITLE_PREPARE_ALL,
    )

except OperationCanceledException:
    forms.alert("Операция отменена.", title=TITLE_PREPARE_ALL)

except Exception as ex:
    forms.alert("Ошибка:\n{}".format(str(ex)), title=TITLE_PREPARE_ALL)

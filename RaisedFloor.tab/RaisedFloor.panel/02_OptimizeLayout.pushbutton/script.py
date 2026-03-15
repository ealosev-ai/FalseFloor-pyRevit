# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import Family, FilteredElementCollector, ViewPlan  # type: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import (  # type: ignore
    FloorOrPartSelectionFilter,
    get_double_param,
    get_source_floor,
    set_double_param,
)
from floor_exact import (  # type: ignore
    evaluate_floor_shift,
    format_area_m2,
    internal_to_mm,
)
from floor_grid import redraw_grid_for_floor  # type: ignore
from floor_i18n import tr  # type: ignore
from floor_ui import (  # type: ignore
    TITLE_SHIFT,
    get_shift_quality_status,
)
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView

_CANCELLED = "@@CANCELLED@@"


try:
    if not isinstance(view, ViewPlan):
        forms.alert(
            tr("open_plan_shift"),
            title=TITLE_SHIFT,
        )
        raise Exception("Active view is not a plan")

    pick_filter = FloorOrPartSelectionFilter()
    try:
        ref = uidoc.Selection.PickObject(
            ObjectType.Element,
            pick_filter,
            tr("pick_floor_or_part_prompt"),
        )
    except OperationCanceledException:
        raise Exception(_CANCELLED)

    picked_el = doc.GetElement(ref.ElementId)
    floor = get_source_floor(picked_el)

    if not floor:
        raise Exception(tr("source_floor_not_found"))

    # Запоминаем текущее смещение до оптимизации
    cur_sx = get_double_param(floor, "FP_Смещение_X")
    cur_sy = get_double_param(floor, "FP_Смещение_Y")
    cur_sx_mm = round(internal_to_mm(cur_sx)) if cur_sx else 0.0
    cur_sy_mm = round(internal_to_mm(cur_sy)) if cur_sy else 0.0

    # Зазор от рёбер вырезов = макс. ширина профиля стрингера
    _stringer_clearance_mm = 0
    for fam in FilteredElementCollector(doc).OfClass(Family):
        if fam.Name == "ФП_Лонжерон":
            for sid in fam.GetFamilySymbolIds():
                sym = doc.GetElement(sid)
                if sym:
                    pw = get_double_param(sym, "FP_Ширина_Профиля")
                    if pw:
                        pw_mm = internal_to_mm(pw)
                        if pw_mm > _stringer_clearance_mm:
                            _stringer_clearance_mm = pw_mm
            break

    search = evaluate_floor_shift(
        doc, floor, min_edge_clearance_mm=_stringer_clearance_mm
    )

    best = search["best"]

    preview_lines = []

    # Текущее vs. предлагаемое
    delta_x = abs(best["shift_x_mm"] - cur_sx_mm)
    delta_y = abs(best["shift_y_mm"] - cur_sy_mm)
    if delta_x < 2.0 and delta_y < 2.0:
        preview_lines.append(tr("shift_current_optimal", x=cur_sx_mm, y=cur_sy_mm))
    else:
        preview_lines.append(tr("shift_current", x=cur_sx_mm, y=cur_sy_mm))
        preview_lines.append(
            tr("shift_best", x=best["shift_x_mm"], y=best["shift_y_mm"])
        )
    preview_lines.append("")

    # Статус и ключевые цифры
    preview_lines.append(tr("shift_status", status=get_shift_quality_status(best)))
    preview_lines.append(
        tr(
            "shift_preview_counts",
            full=best["full_count"],
            simple=best["viable_simple_count"],
            complex=best["complex_count"],
        )
    )

    nv = best["non_viable_count"]
    if nv > 0:
        preview_lines.append(tr("shift_non_viable", count=nv))

    gth = best.get("unsplit_holes", 0)
    if gth > 0:
        preview_lines.append(tr("shift_unsplit_holes", count=gth))

    nec = best.get("near_edge_count", 0)
    if nec > 0:
        preview_lines.append(tr("shift_near_columns", count=nec))

    preview_lines.append(
        tr(
            "shift_min_types",
            min_cut=best["min_viable_cut_mm"],
            types=best["unique_sizes"],
        )
    )
    preview_lines.append(
        tr("cut_area", area=format_area_m2(best["total_cut_area_mm2"]))
    )

    preview_lines.append("")
    total_var = search.get("total_count", "?")
    preview_lines.append(tr("shift_checked", count=total_var))

    apply_answer = forms.alert(
        "\n".join(preview_lines) + "\n\n" + tr("shift_apply_prompt"),
        title=TITLE_SHIFT,
        yes=True,
        no=True,
    )

    if not apply_answer:
        raise Exception(_CANCELLED)

    with revit.Transaction(tr("tx_apply_shift")):
        ok_x = set_double_param(floor, "FP_Смещение_X", best["shift_x_internal"])
        ok_y = set_double_param(floor, "FP_Смещение_Y", best["shift_y_internal"])

        if not ok_x or not ok_y:
            raise Exception(tr("shift_write_failed"))

    grid_result = redraw_grid_for_floor(floor, view, tr("tx_redraw_grid"))

    done_lines = []
    done_lines.append(tr("shift_done"))
    done_lines.append("")
    done_lines.append(
        tr("shift_applied_xy", x=best["shift_x_mm"], y=best["shift_y_mm"])
    )
    done_lines.append(tr("shift_status", status=get_shift_quality_status(best)))
    done_lines.append("")
    done_lines.append(tr("tiles_full", count=best["full_count"]).strip())
    done_lines.append(tr("shift_simple_viable", count=best["viable_simple_count"]))
    done_lines.append(tr("shift_complex_viable", count=best["complex_count"]))
    nv = best["non_viable_count"]
    if nv > 0:
        done_lines.append(tr("shift_non_viable", count=nv))
    gth = best.get("unsplit_holes", 0)
    if gth > 0:
        done_lines.append(tr("shift_unsplit_holes", count=gth))
    nec = best.get("near_edge_count", 0)
    if nec > 0:
        done_lines.append(tr("shift_near_columns", count=nec))
    done_lines.append("")
    done_lines.append(
        tr(
            "shift_min_types",
            min_cut=best["min_viable_cut_mm"],
            types=best["unique_sizes"],
        )
    )
    done_lines.append(tr("cut_area", area=format_area_m2(best["total_cut_area_mm2"])))

    if grid_result:
        done_lines.append("")
        done_lines.append(tr("shift_grid_redrawn"))
        done_lines.append(tr("deleted_old_lines", count=grid_result["deleted_count"]))
        done_lines.append(tr("created_new_lines", count=grid_result["created_count"]))

    forms.alert("\n".join(done_lines), title=TITLE_SHIFT)

except Exception as ex:
    if str(ex) == _CANCELLED:
        forms.alert(tr("operation_cancelled"), title=TITLE_SHIFT)
    else:
        forms.alert(tr("error_fmt", error=str(ex)), title=TITLE_SHIFT)

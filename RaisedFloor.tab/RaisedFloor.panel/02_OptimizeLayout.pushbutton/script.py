# -*- coding: utf-8 -*-

import time

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
    cur_sx = get_double_param(floor, "RF_Offset_X")
    cur_sy = get_double_param(floor, "RF_Offset_Y")
    cur_sx_mm = round(internal_to_mm(cur_sx)) if cur_sx else 0.0
    cur_sy_mm = round(internal_to_mm(cur_sy)) if cur_sy else 0.0

    # Параметры плитки и высоты для отображения в отчёте
    step_x_raw = get_double_param(floor, "RF_Step_X")
    step_y_raw = get_double_param(floor, "RF_Step_Y")
    tile_w = round(internal_to_mm(step_x_raw)) if step_x_raw else "?"
    tile_h = round(internal_to_mm(step_y_raw)) if step_y_raw else "?"
    floor_h_raw = get_double_param(floor, "RF_Floor_Height")
    floor_h = round(internal_to_mm(floor_h_raw)) if floor_h_raw else "?"

    # Зазор от рёбер вырезов = макс. ширина профиля стрингера
    _stringer_clearance_mm = 0
    for fam in FilteredElementCollector(doc).OfClass(Family):
        if fam.Name == "RF_Stringer":
            for sid in fam.GetFamilySymbolIds():
                sym = doc.GetElement(sid)
                if sym:
                    pw = get_double_param(sym, "RF_Profile_Width")
                    if pw:
                        pw_mm = internal_to_mm(pw)
                        if pw_mm > _stringer_clearance_mm:
                            _stringer_clearance_mm = pw_mm
            break

    _t0 = time.time()

    search = evaluate_floor_shift(
        doc,
        floor,
        min_edge_clearance_mm=_stringer_clearance_mm,
    )

    _elapsed = time.time() - _t0

    best = search["best"]

    lines = []

    # --- Исходные данные ---
    lines.append(tr("rpt_tile_size", w=tile_w, h=tile_h, fh=floor_h))
    lines.append("")

    # --- Текущее vs. предлагаемое ---
    delta_x = abs(best["shift_x_mm"] - cur_sx_mm)
    delta_y = abs(best["shift_y_mm"] - cur_sy_mm)
    if delta_x < 2.0 and delta_y < 2.0:
        lines.append(tr("rpt_shift_same", x=cur_sx_mm, y=cur_sy_mm))
    else:
        lines.append(tr("rpt_shift_cur", x=cur_sx_mm, y=cur_sy_mm))
        lines.append(tr("rpt_shift_new", x=best["shift_x_mm"], y=best["shift_y_mm"]))
    lines.append("")

    # --- Качество раскладки ---
    lines.append(tr("rpt_quality", status=get_shift_quality_status(best)))
    lines.append("")

    # --- Плитки ---
    lines.append(tr("rpt_full", count=best["full_count"]))
    lines.append(tr("rpt_cuts", count=best["viable_simple_count"]))
    if best["complex_count"] > 0:
        lines.append(tr("rpt_complex", count=best["complex_count"]))

    nv = best["non_viable_count"]
    if nv > 0:
        lines.append(tr("rpt_non_viable", count=nv))

    lines.append("")

    # --- Предупреждения ---
    gth = best.get("unsplit_holes", 0)
    if gth > 0:
        lines.append(tr("rpt_unsplit", count=gth))

    nec = best.get("near_edge_count", 0)
    if nec > 0:
        lines.append(tr("rpt_near_edge", count=nec))

    if gth > 0 or nec > 0:
        lines.append("")

    # --- Детали ---
    lines.append(tr("rpt_min_cut", mm=best["min_viable_cut_mm"]))
    lines.append(tr("rpt_types", count=best["unique_sizes"]))
    lines.append(tr("rpt_cut_area", area=format_area_m2(best["total_cut_area_mm2"])))
    lines.append("")

    # --- Поиск ---
    total_var = search.get("total_count", "?")
    lines.append(tr("rpt_search", count=total_var, sec=_elapsed))

    apply_answer = forms.alert(
        "\n".join(lines) + "\n\n" + tr("shift_apply_prompt"),
        title=TITLE_SHIFT,
        yes=True,
        no=True,
    )

    if not apply_answer:
        raise Exception(_CANCELLED)

    with revit.Transaction(tr("tx_apply_shift")):
        ok_x = set_double_param(floor, "RF_Offset_X", best["shift_x_internal"])
        ok_y = set_double_param(floor, "RF_Offset_Y", best["shift_y_internal"])

        if not ok_x or not ok_y:
            raise Exception(tr("shift_write_failed"))

    grid_result = redraw_grid_for_floor(
        floor,
        view,
        tr("tx_redraw_grid"),
        non_viable_cells=best.get("non_viable_cells"),
    )

    done = []
    done.append(tr("rpt_done_title"))
    done.append("")
    done.append(tr("rpt_tile_size", w=tile_w, h=tile_h, fh=floor_h))
    done.append(tr("rpt_shift_applied", x=best["shift_x_mm"], y=best["shift_y_mm"]))
    done.append(tr("rpt_quality", status=get_shift_quality_status(best)))
    done.append("")
    done.append(tr("rpt_full", count=best["full_count"]))
    done.append(tr("rpt_cuts", count=best["viable_simple_count"]))
    if best["complex_count"] > 0:
        done.append(tr("rpt_complex", count=best["complex_count"]))
    nv = best["non_viable_count"]
    if nv > 0:
        done.append(tr("rpt_non_viable", count=nv))
    gth = best.get("unsplit_holes", 0)
    if gth > 0:
        done.append(tr("rpt_unsplit", count=gth))
    nec_done = grid_result.get("near_col_count", 0) if grid_result else 0
    if nec_done > 0:
        done.append(tr("rpt_near_edge", count=nec_done))
    done.append("")
    done.append(tr("rpt_min_cut", mm=best["min_viable_cut_mm"]))
    done.append(tr("rpt_types", count=best["unique_sizes"]))
    done.append(tr("rpt_cut_area", area=format_area_m2(best["total_cut_area_mm2"])))

    if grid_result:
        done.append("")
        done.append(
            tr(
                "rpt_grid_ok",
                deleted=grid_result["deleted_count"],
                created=grid_result["created_count"],
            )
        )

    forms.alert("\n".join(done), title=TITLE_SHIFT)

except Exception as ex:
    if str(ex) == _CANCELLED:
        forms.alert(tr("operation_cancelled"), title=TITLE_SHIFT)
    else:
        forms.alert(tr("error_fmt", error=str(ex)), title=TITLE_SHIFT)

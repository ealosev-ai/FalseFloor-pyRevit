# -*- coding: utf-8 -*-

from floor_i18n import tr  # type: ignore

TITLE_PREPARE = tr("title_prepare")
TITLE_PARTS = "⛔ Части (устар.)"
TITLE_GRID = tr("title_grid")
TITLE_SPLIT = "⛔ Разделить (устар.)"
TITLE_CONTOUR = tr("title_contour")
TITLE_SHIFT = tr("title_shift")

TITLE_DIAG_CELLS = "D1 Точные ячейки"
TITLE_DIAG_CLIPPER = "D2 Clipper test"

# Legacy aliases for obsolete scripts (Z1-Z3)
TITLE_D1 = "⛔ Ячейки (устар.)"


def get_shift_quality_status(result):
    non_viable = result.get("non_viable_count", 0)
    unwanted = result.get("unwanted_count", 0)
    complex_count = result.get("complex_count", 0)

    if non_viable > 0:
        return tr("shift_status_invalid")
    if complex_count > 0 or unwanted > 0:
        return tr("shift_status_ok")
    acceptable = result.get("acceptable_count", 0)
    if acceptable > 0:
        return tr("shift_status_good")
    return tr("shift_status_great")


def format_shift_result_lines(result, index=None, area_text=None):
    lines = []
    lines.append(tr("shift_status", status=get_shift_quality_status(result)))

    if index is None:
        lines.append(tr("shift_x", x=result["shift_x_mm"]))
        lines.append(tr("shift_y", y=result["shift_y_mm"]))
    else:
        lines.append(
            tr(
                "shift_xy_ranked",
                index=index,
                x=result["shift_x_mm"],
                y=result["shift_y_mm"],
            )
        )

    lines.append(
        tr(
            "shift_full_simple_complex",
            full=result["full_count"],
            simple=result["viable_simple_count"],
            complex=result["complex_count"],
        )
    )
    lines.append(
        tr(
            "shift_simple_total",
            total=result["total_simple_count"],
            non_viable=result["non_viable_count"],
            micro=result.get("micro_fragment_count", 0),
        )
    )
    lines.append(
        tr(
            "shift_buckets",
            non_viable=result["non_viable_count"],
            unwanted=result.get("unwanted_count", 0),
            acceptable=result.get("acceptable_count", 0),
            good=result.get("good_count", 0),
        )
    )
    lines.append(
        tr(
            "shift_types_min",
            types=result["unique_sizes"],
            min_viable=result["min_viable_cut_mm"],
            min_all=result.get("min_cut_all_mm", 0.0),
        )
    )

    if area_text is None:
        area_text = "{:.0f} мм²".format(result["total_cut_area_mm2"])
    lines.append(tr("cut_area", area=area_text))

    return lines


def format_shift_result_summary_line(result, index=None):
    prefix = ""
    if index is not None:
        prefix = "{}. ".format(index)

    return (
        "{prefix}{status} | X={x:.0f}, Y={y:.0f} мм | "
        "сложн {complex} | недоп {unacc} | нежел {unw} | "
        "micro {micro} | min {min_cut:.0f} мм"
    ).format(
        prefix=prefix,
        status=get_shift_quality_status(result),
        x=result["shift_x_mm"],
        y=result["shift_y_mm"],
        complex=result["complex_count"],
        unacc=result.get("non_viable_count", 0),
        unw=result.get("unwanted_count", 0),
        micro=result.get("micro_fragment_count", 0),
        min_cut=result["min_viable_cut_mm"],
    ) + (
        " [abs {:.0f}]".format(result.get("min_cut_all_mm", 0.0))
        if result.get("min_cut_all_mm", 0.0) < result["min_viable_cut_mm"]
        else ""
    )


def format_shift_search_info_lines(search, include_threshold=False):
    lines = []

    if include_threshold:
        lines.append(
            tr(
                "shift_search_full",
                coarse=search["coarse_step_mm"],
                refine=search["refine_step_mm"],
                radius=search["refine_radius_mm"],
            )
        )
        lines.append(
            tr(
                "shift_thresholds",
                unacc=search.get("unacceptable_cut_mm", 100),
                unw=search.get("unwanted_cut_mm", 150),
                acc=search.get("acceptable_cut_mm", 200),
            )
        )
    else:
        lines.append(
            tr(
                "shift_search_short",
                coarse=search["coarse_step_mm"],
                refine=search["refine_step_mm"],
                radius=search["refine_radius_mm"],
            )
        )

    refine_count = search.get("refine_count", 0)
    coarse_count = search.get("coarse_count", 0)
    total_count = search.get("total_count", 0)
    snap_x = search.get("snap_x_count", 0)
    snap_y = search.get("snap_y_count", 0)
    hole_pairs = search.get("hole_snap_pair_count", 0)

    snap_info = ""
    if snap_x or snap_y or hole_pairs:
        snap_info = " (snap: X={}, Y={}, holes={})".format(snap_x, snap_y, hole_pairs)

    lines.append(
        tr(
            "shift_variants",
            coarse=coarse_count,
            snap=snap_info,
            refine=refine_count,
            total=total_count,
        )
    )
    return lines

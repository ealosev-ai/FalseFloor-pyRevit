# -*- coding: utf-8 -*-

TITLE_PREPARE = "01 Подготовить"
TITLE_PARTS = "⛔ Части (устар.)"
TITLE_GRID = "03 Сетка"
TITLE_SPLIT = "⛔ Разделить (устар.)"
TITLE_CONTOUR = "02 Контур"
TITLE_SHIFT = "04 Смещение"

TITLE_DIAG_CELLS = "D1 Точные ячейки"
TITLE_DIAG_CLIPPER = "D2 Clipper test"

# Legacy aliases for obsolete scripts (Z1-Z3)
TITLE_D1 = "⛔ Ячейки (устар.)"


def get_shift_quality_status(result):
    non_viable = result.get("non_viable_count", 0)
    unwanted = result.get("unwanted_count", 0)
    complex_count = result.get("complex_count", 0)

    if non_viable > 0:
        return "Недопустимый"
    if complex_count > 0 or unwanted > 0:
        return "Допустимый"
    acceptable = result.get("acceptable_count", 0)
    if acceptable > 0:
        return "Хороший"
    return "Отличный"


def format_shift_result_lines(result, index=None, area_text=None):
    lines = []
    lines.append("Статус: {}".format(get_shift_quality_status(result)))

    if index is None:
        lines.append("Смещение X: {:.0f} мм".format(result["shift_x_mm"]))
        lines.append("Смещение Y: {:.0f} мм".format(result["shift_y_mm"]))
    else:
        lines.append(
            "{}. X={:.0f} мм, Y={:.0f} мм".format(
                index, result["shift_x_mm"], result["shift_y_mm"]
            )
        )

    lines.append(
        "Полных: {} | Простых(>=100): {} | Сложных(>=100): {}".format(
            result["full_count"],
            result["viable_simple_count"],
            result["complex_count"],
        )
    )
    lines.append(
        "Простых всего: {} | Немонтируемых(<100): {} (вкл. micro: {})".format(
            result["total_simple_count"],
            result["non_viable_count"],
            result.get("micro_fragment_count", 0),
        )
    )
    lines.append(
        "Недопуст: {} | Нежелат: {} | Допуст: {} | Хорош: {}".format(
            result["non_viable_count"],
            result.get("unwanted_count", 0),
            result.get("acceptable_count", 0),
            result.get("good_count", 0),
        )
    )
    lines.append(
        "Типов: {} | Мин. подрезка: {:.0f} мм | Мин. абс: {:.0f} мм".format(
            result["unique_sizes"],
            result["min_viable_cut_mm"],
            result.get("min_cut_all_mm", 0.0),
        )
    )

    if area_text is None:
        area_text = "{:.0f} мм²".format(result["total_cut_area_mm2"])
    lines.append("Площадь подрезок: {}".format(area_text))

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
            "Грубый шаг: {} мм | Уточнение: {} мм | Радиус: {} мм".format(
                search["coarse_step_mm"],
                search["refine_step_mm"],
                search["refine_radius_mm"],
            )
        )
        lines.append(
            "Недопуст. < {} мм | Нежелат. < {} мм | Допуст. < {} мм".format(
                search.get("unacceptable_cut_mm", 100),
                search.get("unwanted_cut_mm", 150),
                search.get("acceptable_cut_mm", 200),
            )
        )
    else:
        lines.append(
            "Грубый: {} мм | Уточнение: {} мм (R {})".format(
                search["coarse_step_mm"],
                search["refine_step_mm"],
                search["refine_radius_mm"],
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
        "Вариантов: грубых {}{} + уточн. {} = {}".format(
            coarse_count, snap_info, refine_count, total_count
        )
    )
    return lines

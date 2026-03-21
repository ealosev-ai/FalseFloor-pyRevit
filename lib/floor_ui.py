# -*- coding: utf-8 -*-

from floor_i18n import tr  # type: ignore

# Line style constants for show_report_dialog
STYLE_WARN = "warn"
STYLE_GOOD = "good"
STYLE_HEADER = "header"
STYLE_DIM = "dim"

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


def get_shift_quality_style(result):
    """Return STYLE_* matching the quality of *result*."""
    non_viable = result.get("non_viable_count", 0)
    if non_viable > 0:
        return STYLE_WARN
    unwanted = result.get("unwanted_count", 0)
    complex_count = result.get("complex_count", 0)
    if complex_count > 0 or unwanted > 0:
        return None
    return STYLE_GOOD


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
        area_text = tr("area_mm2", area=result["total_cut_area_mm2"])
    lines.append(tr("cut_area", area=area_text))

    return lines


def format_shift_result_summary_line(result, index=None):
    prefix = ""
    if index is not None:
        prefix = "{}. ".format(index)

    return (
        tr(
            "shift_summary_line",
            prefix=prefix,
            status=get_shift_quality_status(result),
            x=result["shift_x_mm"],
            y=result["shift_y_mm"],
            complex=result["complex_count"],
            unacc=result.get("non_viable_count", 0),
            unw=result.get("unwanted_count", 0),
            micro=result.get("micro_fragment_count", 0),
            min_cut=result["min_viable_cut_mm"],
        )
        or ""
    ) + (
        (tr("shift_abs_min_suffix", value=result.get("min_cut_all_mm", 0.0)) or "")
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


def show_report_dialog(lines, title, yes_no=False):
    """Show a modern WPF dialog with colour-coded text lines.

    Args:
        lines: list of items, each is either
            - a plain string  (rendered as normal text)
            - a tuple ``(text, style)`` where *style* is one of
              ``STYLE_WARN``, ``STYLE_GOOD``, ``STYLE_HEADER``,
              ``STYLE_DIM``, or ``None`` for default
            - an empty string ``""`` inserts a vertical spacer
        title:  window title bar text
        yes_no: ``True`` → show *Да / Нет* buttons and return bool;
                ``False``→ show *OK* button, return ``None``.
    """
    import clr  # noqa: E402 – lazy WPF import (IronPython only)

    clr.AddReference("PresentationFramework")
    clr.AddReference("PresentationCore")
    clr.AddReference("WindowsBase")

    from System.Windows import (  # type: ignore
        CornerRadius,
        FontWeights,
        HorizontalAlignment,
        ResizeMode,
        SizeToContent,
        TextWrapping,
        Thickness,
        Window,
        WindowStartupLocation,
        WindowStyle,
    )
    from System.Windows.Controls import (  # type: ignore
        Border,
        Button,
        Orientation,
        ScrollBarVisibility,
        ScrollViewer,
        StackPanel,
        TextBlock,
    )
    from System.Windows.Input import MouseButtonState  # type: ignore
    from System.Windows.Media import (  # type: ignore
        Color,
        FontFamily,
        SolidColorBrush,
    )

    # ── Palette ──────────────────────────────────────────
    BG = SolidColorBrush(Color.FromRgb(250, 250, 250))
    BRUSH_WARN = SolidColorBrush(Color.FromRgb(210, 55, 15))
    BRUSH_GOOD = SolidColorBrush(Color.FromRgb(22, 140, 55))
    BRUSH_DIM = SolidColorBrush(Color.FromRgb(130, 130, 130))
    BRUSH_NORMAL = SolidColorBrush(Color.FromRgb(40, 40, 40))
    BRUSH_BTN_BG = SolidColorBrush(Color.FromRgb(62, 62, 66))
    BRUSH_BTN_FG = SolidColorBrush(Color.FromRgb(255, 255, 255))
    BRUSH_ACCENT = SolidColorBrush(Color.FromRgb(0, 122, 204))

    FONT = FontFamily("Segoe UI")

    # ── Window (borderless with own chrome) ──────────────
    win = Window()
    win.Title = title
    win.SizeToContent = SizeToContent.Height
    win.Width = 420
    win.MaxHeight = 680
    win.WindowStartupLocation = WindowStartupLocation.CenterScreen
    win.ResizeMode = ResizeMode.NoResize
    win.WindowStyle = getattr(WindowStyle, "None")
    win.AllowsTransparency = True
    win.Background = SolidColorBrush(Color.FromArgb(0, 0, 0, 0))

    # Outer card with shadow-like border + rounded corners
    card = Border()
    card.CornerRadius = CornerRadius(8)
    card.Background = BG
    card.BorderBrush = SolidColorBrush(Color.FromRgb(200, 200, 200))
    card.BorderThickness = Thickness(1)
    card.Margin = Thickness(8)  # space for visual "shadow"

    outer = StackPanel()

    # ── Title bar ────────────────────────────────────────
    title_bar = Border()
    title_bar.Background = BRUSH_ACCENT
    title_bar.CornerRadius = CornerRadius(7, 7, 0, 0)
    title_bar.Padding = Thickness(16, 8, 16, 8)

    title_tb = TextBlock()
    title_tb.Text = title
    title_tb.Foreground = BRUSH_BTN_FG
    title_tb.FontFamily = FONT
    title_tb.FontSize = 14
    title_tb.FontWeight = FontWeights.SemiBold
    title_bar.Child = title_tb

    def _on_title_mouse(sender, e):
        if e.LeftButton == MouseButtonState.Pressed:
            win.DragMove()

    title_bar.MouseLeftButtonDown += _on_title_mouse

    outer.Children.Add(title_bar)

    # ── Body ─────────────────────────────────────────────
    body = StackPanel()
    body.Margin = Thickness(22, 14, 22, 6)

    for item in lines:
        if isinstance(item, tuple):
            text, style = item[0], item[1]
        else:
            text = str(item) if item is not None else ""
            style = None

        if not text:
            spacer = TextBlock()
            spacer.Height = 7
            body.Children.Add(spacer)
            continue

        tb = TextBlock()
        tb.Text = text
        tb.TextWrapping = TextWrapping.Wrap
        tb.FontFamily = FONT
        tb.Margin = Thickness(0, 1.5, 0, 1.5)
        tb.FontSize = 13

        if style == STYLE_WARN:
            tb.Foreground = BRUSH_WARN
            tb.FontWeight = FontWeights.SemiBold
        elif style == STYLE_GOOD:
            tb.Foreground = BRUSH_GOOD
            tb.FontWeight = FontWeights.SemiBold
        elif style == STYLE_HEADER:
            tb.FontWeight = FontWeights.Bold
            tb.FontSize = 13.5
            tb.Foreground = BRUSH_NORMAL
        elif style == STYLE_DIM:
            tb.Foreground = BRUSH_DIM
            tb.FontSize = 12.5
        else:
            tb.Foreground = BRUSH_NORMAL

        body.Children.Add(tb)

    scroll = ScrollViewer()
    scroll.Content = body
    scroll.VerticalScrollBarVisibility = ScrollBarVisibility.Auto
    outer.Children.Add(scroll)

    # ── Buttons ──────────────────────────────────────────
    btn_panel = StackPanel()
    btn_panel.Orientation = Orientation.Horizontal
    btn_panel.HorizontalAlignment = HorizontalAlignment.Right
    btn_panel.Margin = Thickness(0, 6, 22, 16)

    result_box = [False]

    def _make_btn(label, primary=False, width=90):
        b = Button()
        b.Content = label
        b.Width = width
        b.Height = 30
        b.FontFamily = FONT
        b.FontSize = 13
        b.Margin = Thickness(6, 0, 0, 0)
        if primary:
            b.Background = BRUSH_ACCENT
            b.Foreground = BRUSH_BTN_FG
            b.FontWeight = FontWeights.SemiBold
        else:
            b.Background = SolidColorBrush(Color.FromRgb(230, 230, 230))
            b.Foreground = BRUSH_NORMAL
        b.BorderThickness = Thickness(0)
        return b

    if yes_no:
        btn_yes = _make_btn(tr("btn_yes"), primary=True)
        btn_no = _make_btn(tr("btn_no"))

        def _on_yes(s, e):
            result_box[0] = True
            win.Close()

        def _on_no(s, e):
            win.Close()

        btn_yes.Click += _on_yes
        btn_no.Click += _on_no
        btn_panel.Children.Add(btn_no)
        btn_panel.Children.Add(btn_yes)
    else:
        btn_ok = _make_btn("OK", primary=True)

        def _on_ok(s, e):
            win.Close()

        btn_ok.Click += _on_ok
        btn_panel.Children.Add(btn_ok)

    outer.Children.Add(btn_panel)
    card.Child = outer
    win.Content = card
    win.ShowDialog()

    return result_box[0] if yes_no else None

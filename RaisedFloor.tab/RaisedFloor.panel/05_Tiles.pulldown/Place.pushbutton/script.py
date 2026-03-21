# -*- coding: utf-8 -*-

from Autodesk.Revit.DB import (  # type: ignore
    XYZ,
    ElementId,
    Family,
    FilteredElementCollector,
    StorageType,
    ViewPlan,
)
from Autodesk.Revit.DB.Structure import StructuralType  # type: ignore
from Autodesk.Revit.Exceptions import OperationCanceledException  # type: ignore
from Autodesk.Revit.UI.Selection import ObjectType  # type: ignore
from floor_common import (  # type: ignore
    FloorOrPartSelectionFilter,
    build_positions,
    get_double_param,
    get_source_floor,
    get_string_param,
    parse_ids_from_string,
    read_floor_grid_params,
    set_double_param,
    set_string_param,
)
from floor_exact import (  # type: ignore
    analyze_cell_exact,
    compute_voids,
    get_exact_zone_for_floor,
    internal_to_mm,
    make_rect_path64,
    mm_to_internal,
)
from floor_grid import get_bbox_xy  # type: ignore
from floor_i18n import tr  # type: ignore
from pyrevit import forms, revit  # type: ignore

doc = revit.doc
uidoc = revit.uidoc
view = doc.ActiveView

TITLE = tr("title_tiles")
FAMILY_NAME = "RF_Tile"
_CANCELLED = "@@CANCELLED@@"
MIN_VIABLE_WIDTH_MM = 100.0
_REQUIRED_PARAMS = [
    "RF_Column",
    "RF_Row",
    "RF_Tile_Type",
    "RF_Tile_Size_X",
    "RF_Tile_Size_Y",
    "RF_Cut_X",
    "RF_Cut_Y",
    "RF_Mark",
]
_VOID_PARAMS = (
    ("RF_Void1_X", "RF_Void1_Y", "RF_Void1_OX", "RF_Void1_OY"),
    ("RF_Void2_X", "RF_Void2_Y", "RF_Void2_OX", "RF_Void2_OY"),
    ("RF_Void3_X", "RF_Void3_Y", "RF_Void3_OX", "RF_Void3_OY"),
)
_VOID_MIN = mm_to_internal(1.0)  # void hidden by formula RF_Void*_X ≤ 1mm


def _find_family_symbol(family_name):
    """Находит стандартный (не вент.) FamilySymbol для семейства по имени."""
    collector = FilteredElementCollector(doc).OfClass(Family)
    for fam in collector:
        if fam.Name == family_name:
            symbol_ids = fam.GetFamilySymbolIds()
            if symbol_ids.Count == 0:
                return None
            fallback = None
            for sid in symbol_ids:
                sym = doc.GetElement(sid)
                try:
                    name_str = sym.Name
                except Exception:
                    name_str = Element.Name.GetValue(sym)
                name_str = name_str or ""
                if "вент" not in name_str.lower():
                    return sym
                if fallback is None:
                    fallback = sym
            return fallback
    return None


def _set_instance_param(instance, name, value):
    """Устанавливает параметр экземпляра (int/float/string)."""
    p = instance.LookupParameter(name)
    if not p or p.IsReadOnly:
        return False
    try:
        if p.StorageType == StorageType.Integer:
            p.Set(int(value))
        elif p.StorageType == StorageType.Double:
            p.Set(float(value))
        elif p.StorageType == StorageType.String:
            p.Set(str(value))
        else:
            return False
        return True
    except Exception:
        return False


def _is_viable(result):
    """Ячейка монтируемая: полная или подрезка с min_width >= 100мм."""
    if result["is_full"]:
        return True
    if result["is_partial"]:
        return result.get("min_width_mm", 0.0) >= MIN_VIABLE_WIDTH_MM
    return False


def _validate_params(instance, param_names):
    """Возвращает список отсутствующих параметров."""
    missing = []
    for name in param_names:
        if not instance.LookupParameter(name):
            missing.append(name)
    return missing


def _get_int_param(el, name):
    p = el.LookupParameter(name)
    if p and p.StorageType == StorageType.Integer:
        return p.AsInteger()
    return 0


def _get_string_param(el, name):
    p = el.LookupParameter(name)
    if p and p.StorageType == StorageType.String:
        return p.AsString() or ""
    return ""


def _collect_vent_cells(old_ids):
    """Собирает set((row, col)) вентилируемых плиток из старого размещения."""
    vent_cells = set()
    for int_id in old_ids:
        try:
            el = doc.GetElement(ElementId(int_id))
            if el and _get_int_param(el, "RF_Ventilated") == 1:
                row = _get_int_param(el, "RF_Row")
                col = _get_int_param(el, "RF_Column")
                vent_cells.add((row, col))
        except Exception:
            pass
    return vent_cells


def _find_vent_symbol(family):
    """Находит тип с 'Вент' в имени среди типов семейства."""
    for sid in family.GetFamilySymbolIds():
        sym = doc.GetElement(sid)
        if sym and "Vent" in (sym.Name or ""):
            return sym
    return None


try:
    if not isinstance(view, ViewPlan):
        forms.alert(tr("open_plan"), title=TITLE)
        raise Exception(_CANCELLED)

    pick_filter = FloorOrPartSelectionFilter()
    try:
        ref = uidoc.Selection.PickObject(
            ObjectType.Element,
            pick_filter,
            tr("pick_floor_prompt"),
        )
    except OperationCanceledException:
        raise Exception(_CANCELLED)

    picked_el = doc.GetElement(ref.ElementId)
    floor = get_source_floor(picked_el)
    if not floor:
        raise Exception(tr("source_floor_not_found"))

    # --- Найти семейство ---
    symbol = _find_family_symbol(FAMILY_NAME)
    if not symbol:
        forms.alert(
            tr("tiles_family_missing", family=FAMILY_NAME),
            title=TITLE,
        )
        raise Exception(_CANCELLED)

    try:
        _sym_name = symbol.Name
    except Exception:
        _sym_name = "?"

    # --- Параметры сетки ---
    params = read_floor_grid_params(floor)
    step_x = params["step_x"]
    step_y = params["step_y"]
    base_x_raw = params["base_x_raw"]
    base_y_raw = params["base_y_raw"]

    shift_x = get_double_param(floor, "RF_Offset_X") or 0.0
    shift_y = get_double_param(floor, "RF_Offset_Y") or 0.0

    base_x = base_x_raw + shift_x
    base_y = base_y_raw + shift_y

    # --- Зона и позиции (идентично evaluate_shift_exact) ---
    exact_zone = get_exact_zone_for_floor(doc, floor)
    min_x, min_y, max_x, max_y = exact_zone["outer_bbox_internal"]

    x_positions = build_positions(
        min_x, max_x, base_x, step_x, end_padding_steps=1.0, end_tolerance=0.0
    )
    y_positions = build_positions(
        min_y, max_y, base_y, step_y, end_padding_steps=1.0, end_tolerance=0.0
    )

    # Z: верх перекрытия + высота стека (или fallback: толщина плитки)
    bbox_data = get_bbox_xy(floor, view)
    z_top = bbox_data[5] if bbox_data else 0.0  # Max.Z = верх перекрытия
    p_thick = symbol.LookupParameter("RF_Thickness")
    tile_thickness = p_thick.AsDouble() if p_thick else mm_to_internal(40.0)

    total_h = get_double_param(floor, "RF_Floor_Height") or 0.0
    if total_h > 0:
        z0 = z_top + total_h - tile_thickness
    else:
        z0 = z_top

    # Level: перекрытие → вид (TODO: проверить на этажах без GenLevel)
    level_id = floor.LevelId
    if level_id and level_id != ElementId.InvalidElementId:
        level = doc.GetElement(level_id)
    else:
        level = view.GenLevel

    if not level:
        forms.alert(tr("open_plan"), title=TITLE)
        raise Exception(_CANCELLED)

    # z0 — абсолютная отметка, а NewFamilyInstance(XYZ, sym, level, ...)
    # трактует Z как смещение от уровня → вычитаем отметку уровня
    level_elevation = level.Elevation if hasattr(level, "Elevation") else 0.0
    z0 = z0 - level_elevation

    # --- Старые плитки: собрать вентилируемые ---
    old_ids = parse_ids_from_string(get_string_param(floor, "RF_Tiles_ID"))
    vent_cells = _collect_vent_cells(old_ids)
    keep_vent = False

    # --- Предварительный подсчёт ---
    cells_to_place = 0
    _diag_full = 0
    _diag_simple = 0
    _diag_complex = 0
    _diag_empty = 0
    _diag_fragment = 0
    _diag_small = 0
    for x0 in x_positions:
        for y0 in y_positions:
            x0_mm = internal_to_mm(x0)
            y0_mm = internal_to_mm(y0)
            x1_mm = internal_to_mm(x0 + step_x)
            y1_mm = internal_to_mm(y0 + step_y)

            rect_path = make_rect_path64(x0_mm, y0_mm, x1_mm, y1_mm)
            rect_bbox_mm = (x0_mm, y0_mm, x1_mm, y1_mm)

            result = analyze_cell_exact(
                rect_path,
                rect_bbox_mm,
                exact_zone["outer_paths"],
                exact_zone["hole_paths"],
                exact_zone["holes_bboxes_mm"],
            )
            if _is_viable(result):
                cells_to_place += 1
            if result["is_full"]:
                _diag_full += 1
            elif result["is_simple_cut"]:
                _diag_simple += 1
            elif result["is_complex_cut"]:
                _diag_complex += 1
            elif result["is_fragment"]:
                _diag_fragment += 1
            elif result["is_empty"]:
                _diag_empty += 1
            if result.get("is_partial") and not _is_viable(result):
                _diag_small += 1

    if cells_to_place == 0:
        forms.alert(tr("tiles_no_cells"), title=TITLE)
        raise Exception(_CANCELLED)

    _diag_text = tr(
        "tiles_diag",
        total=len(x_positions) * len(y_positions),
        full=_diag_full,
        simple=_diag_simple,
        complex=_diag_complex,
        fragment=_diag_fragment,
        empty=_diag_empty,
        small=_diag_small,
    )

    _vent_info = ""
    if vent_cells:
        _vent_info = tr("tiles_old_vent", count=len(vent_cells))

    confirm = forms.alert(
        tr(
            "tiles_confirm",
            cells=cells_to_place,
            symbol=_sym_name,
            deleted=len(old_ids),
            vent=_vent_info,
            diag=_diag_text,
        ),
        title=TITLE,
        yes=True,
        no=True,
    )
    if not confirm:
        raise Exception(_CANCELLED)

    if vent_cells:
        keep_vent = forms.alert(
            tr("tiles_keep_vent", count=len(vent_cells)),
            title=TITLE,
            yes=True,
            no=True,
        )

    # --- Размещение ---
    with revit.Transaction(tr("tx_place_tiles")):
        if not symbol.IsActive:
            symbol.Activate()
            doc.Regenerate()

        # Удалить старые
        deleted = 0
        for int_id in old_ids:
            try:
                el = doc.GetElement(ElementId(int_id))
                if el:
                    doc.Delete(ElementId(int_id))
                    deleted += 1
            except Exception:
                pass

        placed_ids = []  # type: list[str]
        full_count = 0
        cut_simple_count = 0
        cut_complex_count = 0
        cut_complex_with_voids = 0
        cut_complex_unhandled = 0

        for x0 in x_positions:
            for y0 in y_positions:
                x0_mm = internal_to_mm(x0)
                y0_mm = internal_to_mm(y0)
                x1_mm = internal_to_mm(x0 + step_x)
                y1_mm = internal_to_mm(y0 + step_y)

                rect_path = make_rect_path64(x0_mm, y0_mm, x1_mm, y1_mm)
                rect_bbox_mm = (x0_mm, y0_mm, x1_mm, y1_mm)

                result = analyze_cell_exact(
                    rect_path,
                    rect_bbox_mm,
                    exact_zone["outer_paths"],
                    exact_zone["hole_paths"],
                    exact_zone["holes_bboxes_mm"],
                )

                if not _is_viable(result):
                    continue

                # Все плитки в центре ячейки; подрезка через void.
                cx = x0 + step_x / 2.0
                cy = y0 + step_y / 2.0

                instance = doc.Create.NewFamilyInstance(
                    XYZ(cx, cy, z0),
                    symbol,
                    level,
                    StructuralType.NonStructural,
                )

                # Валидация параметров после первого размещения
                if not placed_ids:
                    missing = _validate_params(instance, _REQUIRED_PARAMS)
                    if missing:
                        forms.alert(
                            tr("tiles_missing_params", params="\n".join(missing)),
                            title=TITLE,
                        )
                        raise Exception(_CANCELLED)

                # Колонка/ряд от базы
                col = int(round((x0 - base_x) / step_x))
                row = int(round((y0 - base_y) / step_y))
                _set_instance_param(instance, "RF_Column", col)
                _set_instance_param(instance, "RF_Row", row)
                _set_instance_param(instance, "RF_Mark", "ПЛ.{}.{}".format(row, col))
                _set_instance_param(instance, "RF_Ventilated", 0)

                # Базовый размер плитки = шаг сетки
                _set_instance_param(instance, "RF_Tile_Size_X", step_x)
                _set_instance_param(instance, "RF_Tile_Size_Y", step_y)

                if result["is_full"]:
                    _set_instance_param(instance, "RF_Tile_Type", "Full")
                    _set_instance_param(instance, "RF_Cut_X", 0.0)
                    _set_instance_param(instance, "RF_Cut_Y", 0.0)
                    # Void hidden by formula (RF_Void*_X ≤ 1mm)
                    for vp in _VOID_PARAMS:
                        _set_instance_param(instance, vp[0], _VOID_MIN)
                        _set_instance_param(instance, vp[1], _VOID_MIN)
                        _set_instance_param(instance, vp[2], 0.0)
                        _set_instance_param(instance, vp[3], 0.0)
                    full_count += 1
                elif result["is_simple_cut"] or result["is_complex_cut"]:
                    # Any cut — RF_Cut + voids work together
                    cut_x = result["size_x_mm"]
                    cut_y = result["size_y_mm"]
                    px = mm_to_internal(cut_x)
                    py = mm_to_internal(cut_y)

                    if result["is_simple_cut"]:
                        _set_instance_param(instance, "RF_Tile_Type", "SimpleCut")
                    else:
                        _set_instance_param(instance, "RF_Tile_Type", "ComplexCut")
                    _set_instance_param(instance, "RF_Cut_X", px)
                    _set_instance_param(instance, "RF_Cut_Y", py)

                    # Voids = cell − clipped (до 3 вырезов)
                    clipped = result.get("clipped_paths")
                    num_voids = 0
                    if clipped:
                        vdata = compute_voids(rect_bbox_mm, clipped)
                        for vi, vp in enumerate(_VOID_PARAMS):
                            if vi < len(vdata["voids"]):
                                vw, vh, vox, voy = vdata["voids"][vi]
                                _set_instance_param(instance, vp[0], mm_to_internal(vw))
                                _set_instance_param(instance, vp[1], mm_to_internal(vh))
                                _set_instance_param(
                                    instance, vp[2], mm_to_internal(vox)
                                )
                                _set_instance_param(
                                    instance, vp[3], mm_to_internal(voy)
                                )
                                num_voids += 1
                            else:
                                _set_instance_param(instance, vp[0], _VOID_MIN)
                                _set_instance_param(instance, vp[1], _VOID_MIN)
                                _set_instance_param(instance, vp[2], 0.0)
                                _set_instance_param(instance, vp[3], 0.0)
                        if vdata["has_unhandled_voids"]:
                            cut_complex_unhandled += 1
                    else:
                        for vp in _VOID_PARAMS:
                            _set_instance_param(instance, vp[0], _VOID_MIN)
                            _set_instance_param(instance, vp[1], _VOID_MIN)
                            _set_instance_param(instance, vp[2], 0.0)
                            _set_instance_param(instance, vp[3], 0.0)

                    if result["is_simple_cut"]:
                        cut_simple_count += 1
                    else:
                        cut_complex_count += 1
                        if num_voids > 0:
                            cut_complex_with_voids += 1

                placed_ids.append(str(instance.Id.Value))

        # Сохранить ID для будущего удаления
        ids_string = ";".join(placed_ids)
        set_string_param(floor, "RF_Tiles_ID", ids_string)

        # Записать толщину плитки для расчёта высот в 06/07
        set_double_param(floor, "RF_Tile_Thickness", tile_thickness)

        # --- Восстановление вентиляции ---
        vent_restored = 0
        if keep_vent and vent_cells:
            vent_sym = _find_vent_symbol(symbol.Family)
            if vent_sym and not vent_sym.IsActive:
                vent_sym.Activate()
            for str_id in placed_ids:
                try:
                    el = doc.GetElement(ElementId(int(str_id)))
                    if not el:
                        continue
                    r = _get_int_param(el, "RF_Row")
                    c = _get_int_param(el, "RF_Column")
                    if (r, c) in vent_cells:
                        _set_instance_param(el, "RF_Ventilated", 1)
                        mark = _get_string_param(el, "RF_Mark")
                        if mark and not mark.endswith(".В"):
                            _set_instance_param(el, "RF_Mark", mark + ".В")
                        if vent_sym:
                            el.ChangeTypeId(vent_sym.Id)
                        vent_restored += 1
                except Exception:
                    pass

    # --- Отчёт ---
    done_lines = [
        tr("tiles_done"),
        "",
        tr("tiles_placed", count=len(placed_ids)),
        tr("tiles_full", count=full_count),
        tr("tiles_simple", count=cut_simple_count),
        tr("tiles_complex", count=cut_complex_count),
    ]
    if cut_complex_count > 0:
        done_lines.append(tr("tiles_with_voids", count=cut_complex_with_voids))
        if cut_complex_unhandled > 0:
            done_lines.append(tr("tiles_unhandled_voids", count=cut_complex_unhandled))
        if placed_ids:
            _chk = doc.GetElement(ElementId(int(placed_ids[0])))
            if _chk:
                for _vi, _vp in enumerate(_VOID_PARAMS):
                    if not _chk.LookupParameter(_vp[0]):
                        done_lines.append(
                            tr("tiles_family_missing_param", param=_vp[0])
                        )
    done_lines.extend(
        [
            "",
            tr("deleted_old", count=deleted),
        ]
    )
    if vent_restored > 0:
        done_lines.append(tr("tiles_vent_restored", count=vent_restored))

    forms.alert("\n".join(done_lines), title=TITLE)

except Exception as ex:
    if str(ex) == _CANCELLED:
        pass
    else:
        forms.alert(tr("error_inline_fmt", error=str(ex)), title=TITLE)

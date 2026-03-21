# Changelog

## 2026-03-21 (v1.4.1)

### Changed

- Release packaging switched to runtime-only bundle (`lib/`, `RaisedFloor.tab/`, `Families/`, `README.md`, `LICENSE`, `CHANGELOG.md`) and excludes contributor-only content (`tests/`, `docs/`, `99_Tests.pulldown`).
- CI test step now generates `coverage.xml` (`--cov-report=xml`) to match the Codecov upload step.

### Docs

- README installation section now recommends CLI install/update commands.
- README explicitly states that end-user release ZIP does not include dev-only content.

---
## 2026-03-21 (v1.4.0)

### Added — Стрингеры: конструктивные улучшения

- **Шахматный порядок стыков верхних стрингеров**: чётные ряды режутся на чётных нижних позициях, нечётные — на нечётных. Стыки соседних рядов гарантированно смещены минимум на одну стойку. Устраняет слабую линию, где все стыки совпадают.

- **Стыки нижних стрингеров в серединах пролётов**: нижние режутся не на верхних позициях (где максимальная нагрузка от плиток), а в серединах пролётов между верхними. Нижний непрерывен под каждым пересечением — максимальная прочность в точке нагрузки. Шахматный порядок также применяется.

- **Разделение контурных стрингеров wall/hole**: контурные сегменты из `offset_zone_contours()` разделены на стеновые (от outer boundary) и вокруг отверстий (от holes). Это позволяет применять разную логику фильтрации.

- **Отсев дублирующих hole-контурных (`_drop_near_parallel`)**: если осевой стрингер проходит параллельно и ближе чем `pw + 5 мм` к контурному вокруг отверстия — контурный отсеивается (невозможно поставить 2 опоры рядом). Стеновые контурные не трогаются.

- **Верхние hole-контурные не отсеиваются**: плитка опирается на верхние стрингеры, ей всегда нужны минимум 2 параллельные опоры. `_drop_near_parallel` применяется только к нижним hole-контурным.

### Refactored — Экстракция функций и тесты

- **`compute_stagger_positions()`** извлечена в `lib/floor_common.py`: чистая функция (без Revit API), принимает верхние и нижние позиции, возвращает все раскладки (lp_even/lp_odd, mk_mids_even/mk_mids_odd, stagger_odd_upper/stagger_odd_lower).

- **`drop_near_parallel()`** извлечена в `lib/floor_common.py`: чистая функция, фильтрует параллельные контурные сегменты рядом с осевыми.

- **19 новых юнит-тестов** в `tests/test_stringer_logic.py` (9 stagger + 10 drop_near_parallel). Используют `ast.parse`+`exec` для изолированной загрузки без Revit-зависимостей.

- **Итого 174 теста** проходят (2 skipped).

### Docs — Реструктуризация документации

- **README.md** сокращён до кратких пользовательских описаний (2-3 предложения на раздел).
- **docs/DEVELOPER_GUIDE.md** расширен: добавлены полные алгоритмы (Setup, Optimizer, Stringers, Supports, Tiles), таблица значений по умолчанию.

### Architecture — Алгоритм стрингеров (03_Stringers/Place)

Обновлённый pipeline:

1. **Сетка** → верхние/нижние осевые сегменты
2. **Контурная обвязка** → wall (стены) + hole (отверстия), раздельно upper/lower
3. **Extend ends** → нахлёст контурных в углах
4. **Clip** → стандартный зазор 5 мм от границы (единый для всех)
5. **Cut (шахматка)**:
   - Верхние осевые → стыки на нижних позициях, чётные/нечётные чередуются
   - Нижние осевые → стыки в серединах пролётов между верхними, чередуются
   - Контурные → по соответствующим позициям
6. **Drop near parallel** → только нижние hole-контурные
7. **Dedup** → grid + wall + filtered_hole
8. **Filter short** → убрать < 30 мм

## 2026-03-20 (v1.3.0)

### Added

- **New module `lib/floor_utils.py`**: common utilities for Revit API operations, avoiding code duplication.
- **Unit tests**: pytest test suite for `floor_utils`, `floor_common`, and `floor_i18n` modules.
- **CI/CD pipeline**: GitHub Actions workflow for automated testing on Python 3.9-3.12.
- **Developer documentation**: comprehensive guide in `docs/DEVELOPER_GUIDE.md`.
- **requirements.txt**: dependency management for development and testing.
- **pytest.ini**: test configuration with coverage reporting.

### Fixed

- **DLL path handling**: improved `_get_extension_root()` with UNC path support and better error messages.
- **LoadFamily error handling**: added rollback mechanism for failed family loads in `Families.pushbutton`.
- **Stale definition references**: ensured fresh parameter definitions are loaded before each family processing.
- **Git ignore rules**: excluded `*.rfa`, `*.dll`, `release/*.zip` from version control.

### Changed

- **Refactored duplicate functions**: `_storage_to_param_type`, `_get_data_group_id`, `_make_cat_set`, `_get_existing_bindings` moved to `floor_utils.py`.
- **Improved docstrings**: added Google-style docstrings to public functions in `floor_utils.py` and `floor_exact.py`.
- **Enhanced error reporting**: more descriptive error messages with context information.

### Notes

- Run `pip install -r requirements.txt` to set up development environment.
- Execute tests with `pytest tests/` to verify installation.
- See `docs/DEVELOPER_GUIDE.md` for detailed development instructions.

---

## 2026-03-16 (v1.2.0)

### Added

- Introduced a shared runtime localization layer in lib/floor_i18n.py with RU/EN dictionaries.
- Added automatic UI language detection (CurrentUICulture) and optional override via RAISEDFLOOR_LANG.
- Added a new Parameters command: UI Language (Auto/RU/EN) for runtime language switching.
- MIT license.

### Changed

- **Shift optimizer improvements**: practical cut rounding to 10 mm (CUT_ROUND_MM), contour rounding guards, improved pipeline validation.
- **Renamed extension**: FalseFloor → RaisedFloor (correct English engineering term).
- **Renamed all folders to English**: tab, panel, pulldowns, pushbuttons now use English names.
- Russian UI titles preserved via bundle.yaml `title:` and `layout: [title:]` overrides.
- **Terminology fix**: «лонжерон» → «стрингер» in all Russian user-facing strings; English already used "stringer".
- Renamed env variable: FALSEFLOOR_LANG → RAISEDFLOOR_LANG.
- **Unified naming to RF_ prefix** (was FP_/ФП_):
  - Families: ФП_Плитка → RF_Tile, ФП_Лонжерон → RF_Stringer, ФП_Стойка → RF_Support
  - All ~51 Revit parameters: FP_Шаг_X → RF_Step_X, FP_Высота_Фальшпола → RF_Floor_Height, etc.
  - Line styles: ФП_Сетка → RF_Grid, ФП_Контур → RF_Contour, etc.
  - Shared parameter group: Фальшпол → RaisedFloor
  - Parameter value strings: Верхний/Нижний → Upper/Lower, Полная/Подрезка/Сложная → Full/SimpleCut/ComplexCut
- **Removed duplicate project parameters**: Generic Model params (RF_Column, RF_Void_*, etc.) now live only inside families, not as project parameter bindings.
- Localized core user workflows to RU/EN.
- Updated documentation to bilingual RU/EN format.

### Notes

- Families must be re-saved in Revit Family Editor with the new RF_ parameter names.
- Families are not backward-compatible across Revit versions. If the package families are saved in Revit 2026, Revit 2024 cannot open them.
- Runtime dialogs/reports are fully bilingual.


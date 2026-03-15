# Changelog

## 2026-03-15 (v1.1.0)

### Added

- Introduced a shared runtime localization layer in lib/floor_i18n.py with RU/EN dictionaries.
- Added automatic UI language detection (CurrentUICulture) and optional override via RAISEDFLOOR_LANG.
- Added a new Parameters command: UI Language (Auto/RU/EN) for runtime language switching.

### Changed

- **Renamed extension**: FalseFloor → RaisedFloor (correct English engineering term).
- **Renamed all folders to English**: tab, panel, pulldowns, pushbuttons now use English names.
- Russian UI titles preserved via bundle.yaml `title:` and `layout: [title:]` overrides.
- **Terminology fix**: «лонжерон» → «стрингер» in all Russian user-facing strings; English already used "stringer".
- Renamed env variable: FALSEFLOOR_LANG → RAISEDFLOOR_LANG.
- Localized core user workflows to RU/EN:
    - 01 Prepare -> Slab
    - 01 Prepare -> Contour
    - 01 Prepare -> Grid
    - 02 Find Layout Shift
    - 05 Tiles -> Place
    - 06 Stringers -> Place
    - 07 Supports -> Place
- Localized shared shift/result UI strings in lib/floor_ui.py.
- Updated documentation to bilingual RU/EN format:
    - README.md
    - RaisedFloor.tab/RaisedFloor.panel/README.md

### Notes

- Revit family names (ФП_Лонжерон) and parameter names (FP_ID_Лонжеронов_Верх etc.) remain unchanged for backward compatibility with existing projects.
- Runtime dialogs/reports are fully bilingual.

# Changelog

## 2026-03-15

### Added

- Introduced a shared runtime localization layer in lib/floor_i18n.py with RU/EN dictionaries.
- Added automatic UI language detection (CurrentUICulture) and optional override via FALSEFLOOR_LANG.

### Changed

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
    - Фальшпол.tab/Фальшпол.panel/README.md

### Notes

- Runtime dialogs/reports are bilingual now.
- Bundle button names were intentionally not renamed in this stage (packaging-level change, planned separately).

# Changelog

## 2026-03-15 (v1.2.0)

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
- **Unified naming to RF_ prefix** (was FP_/ФП_):
  - Families: ФП_Плитка → RF_Tile, ФП_Лонжерон → RF_Stringer, ФП_Стойка → RF_Support
  - All ~51 Revit parameters: FP_Шаг_X → RF_Step_X, FP_Высота_Фальшпола → RF_Floor_Height, etc.
  - Line styles: ФП_Сетка → RF_Grid, ФП_Контур → RF_Contour, etc.
  - Shared parameter group: Фальшпол → RaisedFloor
  - Parameter value strings: Верхний/Нижний → Upper/Lower, Полная/Подрезка/Сложная → Full/SimpleCut/ComplexCut
- Localized core user workflows to RU/EN.
- Updated documentation to bilingual RU/EN format.

### Notes

- Families must be re-saved in Revit Family Editor with the new RF_ parameter names.
- Runtime dialogs/reports are fully bilingual.

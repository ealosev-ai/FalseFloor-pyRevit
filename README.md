# FalseFloor.extension

RU: pyRevit-расширение для раскладки фальшпола по точному контуру зоны.

EN: A pyRevit extension for raised-floor layout driven by the exact zone contour.

## Compatibility

RU:

- Проверено в Revit: 2024, 2026.
- Проверено в pyRevit: 6.1.0.x.
- Для других версий нужна отдельная проверка.

EN:

- Verified in Revit: 2024, 2026.
- Verified in pyRevit: 6.1.0.x.
- Other versions require separate validation.

## Quick Start

RU:

1. Добавьте путь к папке FalseFloor.extension в pyRevit: Extensions -> Add Folder.
2. Выполните Reload pyRevit.
3. Загрузите семейства из папки Families:
    - ФП_Плитка.rfa
    - ФП_Лонжерон.rfa
    - ФП_Стойка.rfa
4. Откройте вкладку Фальшпол.
5. Для подробной инструкции используйте кнопку 7 Справка или файл Фальшпол.tab/Фальшпол.panel/README.md.

EN:

1. Add the FalseFloor.extension folder to pyRevit: Extensions -> Add Folder.
2. Run Reload pyRevit.
3. Load the family files from Families:
    - ФП_Плитка.rfa
    - ФП_Лонжерон.rfa
    - ФП_Стойка.rfa
4. Open the Фальшпол tab.
5. Use the 7 Справка button or Фальшпол.tab/Фальшпол.panel/README.md for the full guide.

## Recommended Workflow

RU:

1. Параметры.
2. Подготовка -> Перекрытие.
3. Подготовка -> Периметр.
4. Подготовка -> Сетка.
5. Подобрать раскладку.
6. Плитки -> Разместить.
7. Лонжероны -> Разместить.
8. Стойки -> Разместить.

EN:

1. Parameters.
2. Prepare -> Slab.
3. Prepare -> Contour.
4. Prepare -> Grid.
5. Find layout shift.
6. Tiles -> Place.
7. Stringers -> Place.
8. Supports -> Place.

This order is intentional: tiles write the tile thickness used later by stringer/support height logic. Stringer and support tools can still run earlier, but they will show warnings and use fallback values.

## Current Capabilities

- Exact shift optimization with contour-aware ranking and practical cut rounding to 10 mm.
- Grid redraw and contour rebuild on plan views.
- Tile placement with full, simple-cut, and complex-cut cells.
- Up to 3 void groups per tile family instance.
- Stringer/support height-stack validation and out-of-order workflow warnings.

## Documentation And Reporting

- Main user guide: Фальшпол.tab/Фальшпол.panel/README.md
- Issue template: ISSUE_REPORT.md
- Test scenario: TESTPLAN.md

# RaisedFloor.extension

RU: pyRevit-расширение для раскладки фальшпола по точному контуру зоны.

EN: A pyRevit extension for raised-floor layout driven by the exact zone contour.

## For English Users

- Quick start: see the EN section below.
- Detailed guide: RaisedFloor.tab/RaisedFloor.panel/README.md (EN section).
- Issue template: ISSUE_REPORT.md.
- Test plan: TESTPLAN.md.

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

1. Добавьте путь к папке RaisedFloor.extension в pyRevit: Extensions -> Add Folder.
2. Выполните Reload pyRevit.
3. Загрузите семейства из папки Families:
    - RF_Tile.rfa
    - RF_Stringer.rfa (стрингер)
    - RF_Support.rfa
4. Откройте вкладку Фальшпол.
5. Для подробной инструкции используйте кнопку 7 Справка или файл RaisedFloor.tab/RaisedFloor.panel/README.md.

EN:

1. Add the RaisedFloor.extension folder to pyRevit: Extensions -> Add Folder.
2. Run Reload pyRevit.
3. Load the family files from Families:
    - RF_Tile.rfa
    - RF_Stringer.rfa (stringer)
    - RF_Support.rfa
4. Open the Фальшпол tab.
5. Use the 7 Справка button or RaisedFloor.tab/RaisedFloor.panel/README.md for the full guide.

## Recommended Workflow

RU:

1. Параметры.
2. Подготовка -> Перекрытие.
3. Подготовка -> Периметр.
4. Подготовка -> Сетка.
5. Подобрать раскладку.
6. Плитки -> Разместить.
7. Стрингеры -> Разместить.
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

- Main user guide: RaisedFloor.tab/RaisedFloor.panel/README.md
- Issue template: ISSUE_REPORT.md
- Test scenario: TESTPLAN.md

## Naming Convention / Соглашение об именовании

RU:

Расширение использует **единую англоязычную схему именования** с префиксом `RF_`:

| Слой | Язык | Пример |
| --- | --- | --- |
| Папки расширения | EN | `RaisedFloor.tab`, `03_Stringers.pulldown` |
| Кнопки на ленте Revit | RU | Стрингеры, Плитки (через bundle.yaml) |
| Диалоги и сообщения | RU/EN авто | `tr("shift_done")` |
| Семейства .rfa | EN | RF_Tile, RF_Stringer, RF_Support |
| Параметры Revit | EN | RF_Step_X, RF_Floor_Height, RF_Stringers_Top_ID |
| Стили линий | EN | RF_Grid, RF_Contour, RF_Base |
| Группа общих параметров | EN | RaisedFloor |

EN:

The extension uses a **unified English naming scheme** with the `RF_` prefix:

| Layer | Language | Example |
| --- | --- | --- |
| Extension folders | EN | `RaisedFloor.tab`, `03_Stringers.pulldown` |
| Ribbon buttons | RU | Стрингеры, Плитки (via bundle.yaml) |
| Dialogs & messages | RU/EN auto | `tr("shift_done")` |
| Families .rfa | EN | RF_Tile, RF_Stringer, RF_Support |
| Revit parameters | EN | RF_Step_X, RF_Floor_Height, RF_Stringers_Top_ID |
| Line styles | EN | RF_Grid, RF_Contour, RF_Base |
| Shared param group | EN | RaisedFloor |

## License

MIT — see [LICENSE](LICENSE).

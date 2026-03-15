# RaisedFloor Panel Guide

## RU

### Назначение

Это подробная справка по панели Фальшпол в pyRevit.

Плагин работает через семейства, а не через Revit Parts:

- RF_Tile
- RF_Stringer
- RF_Support

Базовый принцип:

1. Подготовить геометрию зоны.
2. Подобрать смещение раскладки по точному контуру.
3. Разместить элементы подсистемы и плитки.

### Перед первым запуском

Проверьте:

1. Загружены семейства RF_Tile, RF_Stringer, RF_Support.
2. Вы работаете в плане, не в 3D виде.
3. Созданы и доступны параметры RF_** в проекте и нужных семействах.
4. Выбрано корректное перекрытие зоны фальшпола.

### Структура панели

Рабочие команды:

1. Параметры
2. 1 Подготовка
3. 2 Подобрать раскладку
4. 3 Лонжероны
5. 4 Стойки
6. 5 Плитки
7. 6 Очистка
8. 7 Справка

### Рекомендуемая последовательность

1. Параметры -> Параметры проекта.
2. Параметры -> Параметры семейств.
3. 1 Подготовка -> Перекрытие.
4. 1 Подготовка -> Периметр.
5. 1 Подготовка -> Сетка.
6. 2 Подобрать раскладку.
7. 5 Плитки -> Разместить.
8. 3 Лонжероны -> Разместить.
9. 4 Стойки -> Разместить.

Почему плитки раньше лонжеронов и стоек:

- команда плиток записывает RF_Tile_Thickness в зону;
- лонжероны и стойки используют её в расчёте высотной схемы;
- при запуске в обратном порядке сработают предупреждения и fallback к толщине из семейства.

### Что делает каждая команда

#### Параметры

- Параметры проекта: создаёт/обновляет обязательные RF_** параметры в проекте.
- Параметры семейств: создаёт/обновляет RF_** параметры в семействах.
- Язык UI: переключает язык runtime-интерфейса RaisedFloor (Auto/RU/EN).
- Очистить параметры: удаляет привязки параметров.

#### 1 Подготовка -> Перекрытие

Действия:

- выбор исходного перекрытия;
- запись базовой точки раскладки;
- запись шага X/Y;
- запись высоты фальшпола;
- сброс смещения в 0.

Параметры:

- RF_Step_X, RF_Step_Y
- RF_Base_X, RF_Base_Y, RF_Base_Z
- RF_Floor_Height
- RF_Offset_X, RF_Offset_Y

#### 1 Подготовка -> Периметр

Действия:

- строит контур по верхней грани зоны;
- обновляет старые контурные линии.

Параметры:

- RF_Contour_Lines_ID

Важно:

- именно этот контур используется точной раскладкой;
- если геометрия зоны изменилась, периметр нужно перестроить.

#### 1 Подготовка -> Сетка

Действия:

- строит сетку по шагу и текущему смещению;
- удаляет старые линии сетки;
- перерисовывает результат в текущем плане.

Параметры:

- RF_Grid_Lines_ID

#### 2 Подобрать раскладку

Действия:

- перебирает смещения X/Y;
- анализирует реальные ячейки по точному контуру;
- ранжирует варианты по качеству подрезок;
- применяет лучшее смещение;
- сразу перерисовывает сетку.

Что учитывается в оценке:

- количество полных плиток;
- допустимость подрезок;
- сложные подрезки;
- близость линий к колоннам/вырезам;
- площадь и типоразмеры подрезок.

#### 5 Плитки -> Разместить

Действия:

- размещает плитки по центрам ячеек;
- поддерживает полные, простые и сложные ячейки;
- пишет параметры void-вырезов для сложных ячеек;
- может восстановить ранее помеченные вентилируемые плитки.

Поддержка void:

- до 3 групп: RF_Void1_*, RF_Void2_*, RF_Void3_*

Параметры экземпляра:

- RF_Tile_Type
- RF_Cut_X, RF_Cut_Y
- RF_Void_* (и группы 2/3)
- RF_Column, RF_Row, RF_Mark, RF_Ventilated

Параметры зоны:

- RF_Tiles_ID
- RF_Tile_Thickness

#### 3 Лонжероны -> Разместить

Действия:

- верхние лонжероны строятся по линиям сетки;
- нижние строятся перпендикулярно с заданным шагом;
- режутся по максимальной длине;
- проверяется конфликт высотной схемы.

Параметры:

- RF_Stringers_Top_ID
- RF_Stringers_Bottom_ID

#### 4 Стойки -> Разместить

Действия:

- ставит стойки по концам и промежуточным узлам нижних лонжеронов;
- поворачивает стойки по оси нижних;
- рассчитывает RF_Support_Height из высотной схемы.

Параметры:

- RF_Supports_ID

#### 6 Очистка

Удаляет элементы, созданные плагином:

- плитки
- лонжероны
- стойки
- линии сетки
- линии контура

### Частые ситуации

Если раскладка выглядит плохо:

1. Перестройте Периметр.
2. Перестройте Сетку.
3. Запустите 2 Подобрать раскладку снова.

Если изменился тип/толщина плитки:

1. Переразместите плитки.
2. Затем переразместите лонжероны.
3. Затем переразместите стойки.

Если стойки/лонжероны не размещаются:

1. Проверьте RF_Floor_Height.
2. Проверьте, что семейства загружены.
3. Проверьте наличие RF_** параметров.

Если нужно начать заново:

1. Выполните 6 Очистка.
2. Повторите цепочку от Перекрытия до Стоек в рекомендованном порядке.

### Ключевые параметры зоны

- RF_Step_X, RF_Step_Y
- RF_Offset_X, RF_Offset_Y
- RF_Base_X, RF_Base_Y, RF_Base_Z
- RF_Floor_Height
- RF_Tile_Thickness
- RF_Contour_Lines_ID
- RF_Grid_Lines_ID
- RF_Tiles_ID
- RF_Stringers_Top_ID, RF_Stringers_Bottom_ID
- RF_Supports_ID

## EN

### Purpose

This is the detailed help page for the RaisedFloor panel in pyRevit.

The workflow is family-based, not Revit Parts based:

- RF_Tile
- RF_Stringer
- RF_Support

Core idea:

1. Prepare the zone geometry.
2. Find the best layout shift from the exact contour.
3. Place subsystem elements and tiles.

### Before First Run

Check:

1. Families RF_Tile, RF_Stringer, RF_Support are loaded.
2. You are working in a plan view, not a 3D view.
3. RF_** parameters exist and are writable in project/families.
4. You select the correct source slab.

### Panel Structure

Main commands:

1. Parameters
2. 1 Prepare
3. 2 Find Layout Shift
4. 3 Stringers
5. 4 Supports
6. 5 Tiles
7. 6 Cleanup
8. 7 Help

### Recommended Sequence

1. Parameters -> Project Parameters.
2. Parameters -> Family Parameters.
3. 1 Prepare -> Slab.
4. 1 Prepare -> Contour.
5. 1 Prepare -> Grid.
6. 2 Find Layout Shift.
7. 5 Tiles -> Place.
8. 3 Stringers -> Place.
9. 4 Supports -> Place.

Why tiles come before stringers/supports:

- tile placement writes RF_Tile_Thickness into the zone;
- stringers/supports use it for height-stack calculations;
- if run earlier, warnings are shown and fallback thickness is used.

### What Each Command Does

#### Parameters

- Project Parameters: creates/updates required RF_** project parameters.
- Family Parameters: creates/updates required RF_** family parameters.
- UI Language: switches RaisedFloor runtime UI language (Auto/RU/EN).
- Clear Parameters: removes parameter bindings.

#### 1 Prepare -> Slab

Actions:

- selects source slab;
- saves layout base point;
- writes X/Y step;
- writes raised-floor height;
- resets shift to zero.

Parameters:

- RF_Step_X, RF_Step_Y
- RF_Base_X, RF_Base_Y, RF_Base_Z
- RF_Floor_Height
- RF_Offset_X, RF_Offset_Y

#### 1 Prepare -> Contour

Actions:

- rebuilds contour from the top slab face;
- replaces old contour lines.

Parameters:

- RF_Contour_Lines_ID

Important:

- this contour is the source of truth for exact layout;
- rebuild it whenever zone geometry changes.

#### 1 Prepare -> Grid

Actions:

- builds grid by step and current shift;
- removes old grid lines;
- redraws in current plan.

Parameters:

- RF_Grid_Lines_ID

#### 2 Find Layout Shift

Actions:

- tests X/Y shifts;
- evaluates real cells against exact contour;
- ranks variants by cut quality;
- applies best shift;
- redraws grid immediately.

Metrics include:

- full tile count;
- viable/non-viable cuts;
- complex cuts;
- near-column/void proximity;
- cut area and size diversity.

#### 5 Tiles -> Place

Actions:

- places tile instances at cell centers;
- supports full, simple-cut, and complex cells;
- writes void parameters for complex cells;
- can restore ventilation marks from previous placement.

Void support:

- up to 3 groups: RF_Void1_*, RF_Void2_*, RF_Void3_*

Instance parameters:

- RF_Tile_Type
- RF_Cut_X, RF_Cut_Y
- RF_Void_* (plus groups 2/3)
- RF_Column, RF_Row, RF_Mark, RF_Ventilated

Zone parameters:

- RF_Tiles_ID
- RF_Tile_Thickness

#### 3 Stringers -> Place

Actions:

- places upper stringers on grid lines;
- places lower stringers perpendicular by spacing;
- cuts pieces by max length;
- validates full height-stack constraints.

Parameters:

- RF_Stringers_Top_ID
- RF_Stringers_Bottom_ID

#### 4 Supports -> Place

Actions:

- places supports on lower stringer endpoints and intermediate nodes;
- rotates supports to match lower axis;
- computes RF_Support_Height from full stack.

Parameters:

- RF_Supports_ID

#### 6 Cleanup

Removes plugin-generated elements:

- tiles
- stringers
- supports
- grid lines
- contour lines

### Common Scenarios

If layout quality looks wrong:

1. Rebuild Contour.
2. Rebuild Grid.
3. Run 2 Find Layout Shift again.

If tile type/thickness changed:

1. Re-place tiles.
2. Then re-place stringers.
3. Then re-place supports.

If stringers/supports do not place:

1. Check RF_Floor_Height.
2. Verify families are loaded.
3. Verify RF_** parameters exist and are writable.

If you need a full rebuild:

1. Run 6 Cleanup.
2. Repeat from Slab through Supports in the recommended order.

### Critical Zone Parameters

- RF_Step_X, RF_Step_Y
- RF_Offset_X, RF_Offset_Y
- RF_Base_X, RF_Base_Y, RF_Base_Z
- RF_Floor_Height
- RF_Tile_Thickness
- RF_Contour_Lines_ID
- RF_Grid_Lines_ID
- RF_Tiles_ID
- RF_Stringers_Top_ID, RF_Stringers_Bottom_ID
- RF_Supports_ID

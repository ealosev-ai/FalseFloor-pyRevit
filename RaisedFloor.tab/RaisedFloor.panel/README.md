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

### Шпаргалка: как выбирается смещение (30 секунд)

1. Строится точная зона: внешний контур минус отверстия.
2. Генерируются кандидаты смещения X/Y: грубый шаг + snap к вершинам/углам.
3. Для лучших вариантов делается локальное уточнение (мелкий шаг).
4. Для каждого кандидата каждая ячейка клиппируется по контуру и классифицируется.
5. Считаются метрики качества: немонтируемые, сложные, полные, близость к колоннам и т.д.
6. Выбирается минимум по rank_key (иерархический приоритет), записывается RF_Offset_X/Y.

Критично:

- сначала минимизируются немонтируемые подрезки `<100 мм`, потом уже оптимизируются остальные показатели;
- при равных условиях предпочтение у варианта с более «ровными» и технологичными подрезками.

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
7. 3 Лонжероны -> Разместить.
8. 4 Стойки -> Разместить.
9. 5 Плитки -> Разместить.

Почему лонжероны и стойки можно ставить до плиток:

- высотная схема берёт толщину плитки из RF_Tile_Thickness, который задаётся на этапе Подготовка;
- если RF_Tile_Thickness не заполнен, используется fallback из семейства RF_Tile;
- такой порядок удобен для наглядного контроля каркаса до укладки плиток.

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

Как работает алгоритм подбора:

1. Входные данные.

- Берутся шаги `RF_Step_X/Y`, база `RF_Base_X/Y`, текущее перекрытие и его точный контур.
- Контур строится как внешняя граница минус отверстия (колонны/вырезы).

1. Фаза 1: грубый поиск кандидатов смещения.

- Перебор смещений по X/Y на грубом шаге (по умолчанию 50 мм).
- Дополняется «инженерными» snap-кандидатами: через вершины контура, углы отверстий, а также варианты ±1 мм и полшага.

1. Фаза 2: локальное уточнение лучших.

- Для top-N кандидатов из фазы 1 строится локальная сетка вокруг каждого (по умолчанию шаг 10 мм, радиус 60 мм).
- Это даёт точность без полного перебора всех комбинаций.

1. Фаза 3: доводка под кратность подрезок.

- Для лучших вариантов пробуются аналитические дельты, чтобы подрезки у границ были ближе к кратности 10 мм (`CUT_ROUND_MM`).

1. Оценка каждого кандидата.

- Для каждой ячейки сетки строится пересечение с точным контуром (Clipper2).
- Ячейка классифицируется как полная, простая подрезка, сложная, фрагмент или пустая.
- Для сложных подрезок min-width оценивается сканированием лучами (ray-casting).

Пороги подрезок (мм):

- `< 50` — micro fragment;
- `< 100` — немонтируемая;
- `100–150` — нежелательная;
- `150–200` — допустимая;
- `>= 200` — хорошая.

Приоритет ранжирования (rank_key, от более важного к менее важному):

1. `unsplit_holes` — неразбитые отверстия;
2. `non_viable_count` — немонтируемые подрезки `<100`;
3. `micro_fragment_count` — микрофрагменты `<50`;
4. `near_edge_count` и `near_edge_penalty` — близость к рёбрам отверстий;
5. `unwanted_count`, `complex_count`;
6. максимум полных плиток (`full_count`), затем качество оставшихся метрик (`unique_sizes`, `min_viable_cut`, roundness/spread penalties).

7. Результат.

- Выбирается вариант с минимальным `rank_key`.
- Записываются `RF_Offset_X/Y`, сетка перерисовывается сразу.
- В отчёте показываются счётчики подрезок и качество найденного смещения.

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

### Quick Cheat Sheet: how shift is chosen (30 seconds)

1. Build exact zone: outer contour minus holes.
2. Generate X/Y shift candidates: coarse step + snap-to-vertices/corners.
3. Run local refinement around top coarse candidates.
4. For each candidate, clip every grid cell by contour and classify it.
5. Compute quality metrics: non-viable cuts, complexity, full tiles, near-hole proximity, etc.
6. Pick minimum rank_key candidate and write RF_Offset_X/Y.

Key point:

- non-viable cuts `<100 mm` are minimized first; only then other quality metrics are optimized.

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
7. 3 Stringers -> Place.
8. 4 Supports -> Place.
9. 5 Tiles -> Place.

Why stringers/supports can be placed before tiles:

- height stack uses RF_Tile_Thickness written during Prepare;
- if RF_Tile_Thickness is missing, fallback from RF_Tile family is used;
- this order is often more convenient for visual frame control before tile placement.

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

How the shift optimizer works:

1. Input data.

- Uses `RF_Step_X/Y`, base `RF_Base_X/Y`, selected floor, and exact zone contour.
- Zone contour is built as outer boundary minus holes (columns/openings).

1. Phase 1: coarse search.

- Enumerates X/Y shifts on a coarse step (default 50 mm).
- Adds engineering snap candidates: contour vertices, hole corners, plus ±1 mm and half-step offsets.

1. Phase 2: local refinement.

- Refines top-N coarse candidates in local neighborhoods (default 10 mm step, 60 mm radius).
- Gives near-exhaustive quality with much less compute.

1. Phase 3: edge-cut rounding.

- Tries analytical deltas so boundary cuts are closer to 10 mm multiples (`CUT_ROUND_MM`).

1. Candidate evaluation.

- Each grid cell is clipped against the exact contour (Clipper2).
- Cell is classified as full, simple cut, complex cut, fragment, or empty.
- For complex cuts, min-width is estimated via ray-casting scan.

Cut thresholds (mm):

- `< 50` — micro fragment;
- `< 100` — non-viable;
- `100–150` — unwanted;
- `150–200` — acceptable;
- `>= 200` — good.

Ranking priority (`rank_key`, most important first):

1. `unsplit_holes`;
2. `non_viable_count` (`<100` cuts);
3. `micro_fragment_count` (`<50` cuts);
4. `near_edge_count` and `near_edge_penalty`;
5. `unwanted_count`, `complex_count`;
6. maximize `full_count`, then tie-break with `unique_sizes`, `min_viable_cut`, and roundness/spread penalties.

7. Output.

- Picks the minimum `rank_key` candidate.
- Writes `RF_Offset_X/Y` and redraws the grid immediately.
- Report shows cut counters and resulting quality.

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

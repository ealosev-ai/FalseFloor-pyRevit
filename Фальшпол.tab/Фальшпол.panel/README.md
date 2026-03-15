# FalseFloor Panel Guide

## RU

### Назначение

Это подробная справка по панели Фальшпол в pyRevit.

Плагин работает через семейства, а не через Revit Parts:

- ФП_Плитка
- ФП_Лонжерон
- ФП_Стойка

Базовый принцип:

1. Подготовить геометрию зоны.
2. Подобрать смещение раскладки по точному контуру.
3. Разместить элементы подсистемы и плитки.

### Перед первым запуском

Проверьте:

1. Загружены семейства ФП*Плитка, ФП*Лонжерон, ФП_Стойка.
2. Вы работаете в плане, не в 3D виде.
3. Созданы и доступны параметры FP\_\* в проекте и нужных семействах.
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

- команда плиток записывает FP*Толщина*Плитки в зону;
- лонжероны и стойки используют её в расчёте высотной схемы;
- при запуске в обратном порядке сработают предупреждения и fallback к толщине из семейства.

### Что делает каждая команда

#### Параметры

- Параметры проекта: создаёт/обновляет обязательные FP\_\* параметры в проекте.
- Параметры семейств: создаёт/обновляет FP\_\* параметры в семействах.
- Очистить параметры: удаляет привязки параметров.

#### 1 Подготовка -> Перекрытие

Действия:

- выбор исходного перекрытия;
- запись базовой точки раскладки;
- запись шага X/Y;
- запись высоты фальшпола;
- сброс смещения в 0.

Параметры:

- FP*Шаг_X, FP*Шаг_Y
- FP*База_X, FP*База*Y, FP*База_Z
- FP*Высота*Фальшпола
- FP*Смещение_X, FP*Смещение_Y

#### 1 Подготовка -> Периметр

Действия:

- строит контур по верхней грани зоны;
- обновляет старые контурные линии.

Параметры:

- FP*ID*ЛинийКонтура

Важно:

- именно этот контур используется точной раскладкой;
- если геометрия зоны изменилась, периметр нужно перестроить.

#### 1 Подготовка -> Сетка

Действия:

- строит сетку по шагу и текущему смещению;
- удаляет старые линии сетки;
- перерисовывает результат в текущем плане.

Параметры:

- FP*ID*ЛинийСетки

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

- до 3 групп: FP*Вырез*_, FP*Вырез2*_, FP*Вырез3*\*

Параметры экземпляра:

- FP*Тип*Плитки
- FP*Подрезка_X, FP*Подрезка_Y
- FP*Вырез*\* (и группы 2/3)
- FP*Колонка, FP*Ряд, FP*Марка, FP*Вентилируемая

Параметры зоны:

- FP*ID*Плиток
- FP*Толщина*Плитки

#### 3 Лонжероны -> Разместить

Действия:

- верхние лонжероны строятся по линиям сетки;
- нижние строятся перпендикулярно с заданным шагом;
- режутся по максимальной длине;
- проверяется конфликт высотной схемы.

Параметры:

- FP*ID*Лонжеронов_Верх
- FP*ID*Лонжеронов_Низ

#### 4 Стойки -> Разместить

Действия:

- ставит стойки по концам и промежуточным узлам нижних лонжеронов;
- поворачивает стойки по оси нижних;
- рассчитывает FP*Высота*Стойки из высотной схемы.

Параметры:

- FP*ID*Стоек

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

1. Проверьте FP*Высота*Фальшпола.
2. Проверьте, что семейства загружены.
3. Проверьте наличие FP\_\* параметров.

Если нужно начать заново:

1. Выполните 6 Очистка.
2. Повторите цепочку от Перекрытия до Стоек в рекомендованном порядке.

### Ключевые параметры зоны

- FP*Шаг_X, FP*Шаг_Y
- FP*Смещение_X, FP*Смещение_Y
- FP*База_X, FP*База*Y, FP*База_Z
- FP*Высота*Фальшпола
- FP*Толщина*Плитки
- FP*ID*ЛинийКонтура
- FP*ID*ЛинийСетки
- FP*ID*Плиток
- FP*ID*Лонжеронов*Верх, FP_ID*Лонжеронов_Низ
- FP*ID*Стоек

## EN

### Purpose

This is the detailed help page for the FalseFloor panel in pyRevit.

The workflow is family-based, not Revit Parts based:

- ФП_Плитка
- ФП_Лонжерон
- ФП_Стойка

Core idea:

1. Prepare the zone geometry.
2. Find the best layout shift from the exact contour.
3. Place subsystem elements and tiles.

### Before First Run

Check:

1. Families ФП*Плитка, ФП*Лонжерон, ФП_Стойка are loaded.
2. You are working in a plan view, not a 3D view.
3. FP\_\* parameters exist and are writable in project/families.
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

- tile placement writes FP*Толщина*Плитки into the zone;
- stringers/supports use it for height-stack calculations;
- if run earlier, warnings are shown and fallback thickness is used.

### What Each Command Does

#### Parameters

- Project Parameters: creates/updates required FP\_\* project parameters.
- Family Parameters: creates/updates required FP\_\* family parameters.
- Clear Parameters: removes parameter bindings.

#### 1 Prepare -> Slab

Actions:

- selects source slab;
- saves layout base point;
- writes X/Y step;
- writes raised-floor height;
- resets shift to zero.

Parameters:

- FP*Шаг_X, FP*Шаг_Y
- FP*База_X, FP*База*Y, FP*База_Z
- FP*Высота*Фальшпола
- FP*Смещение_X, FP*Смещение_Y

#### 1 Prepare -> Contour

Actions:

- rebuilds contour from the top slab face;
- replaces old contour lines.

Parameters:

- FP*ID*ЛинийКонтура

Important:

- this contour is the source of truth for exact layout;
- rebuild it whenever zone geometry changes.

#### 1 Prepare -> Grid

Actions:

- builds grid by step and current shift;
- removes old grid lines;
- redraws in current plan.

Parameters:

- FP*ID*ЛинийСетки

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

- up to 3 groups: FP*Вырез*_, FP*Вырез2*_, FP*Вырез3*\*

Instance parameters:

- FP*Тип*Плитки
- FP*Подрезка_X, FP*Подрезка_Y
- FP*Вырез*\* (plus groups 2/3)
- FP*Колонка, FP*Ряд, FP*Марка, FP*Вентилируемая

Zone parameters:

- FP*ID*Плиток
- FP*Толщина*Плитки

#### 3 Stringers -> Place

Actions:

- places upper stringers on grid lines;
- places lower stringers perpendicular by spacing;
- cuts pieces by max length;
- validates full height-stack constraints.

Parameters:

- FP*ID*Лонжеронов_Верх
- FP*ID*Лонжеронов_Низ

#### 4 Supports -> Place

Actions:

- places supports on lower stringer endpoints and intermediate nodes;
- rotates supports to match lower axis;
- computes FP*Высота*Стойки from full stack.

Parameters:

- FP*ID*Стоек

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

1. Check FP*Высота*Фальшпола.
2. Verify families are loaded.
3. Verify FP\_\* parameters exist and are writable.

If you need a full rebuild:

1. Run 6 Cleanup.
2. Repeat from Slab through Supports in the recommended order.

### Critical Zone Parameters

- FP*Шаг_X, FP*Шаг_Y
- FP*Смещение_X, FP*Смещение_Y
- FP*База_X, FP*База*Y, FP*База_Z
- FP*Высота*Фальшпола
- FP*Толщина*Плитки
- FP*ID*ЛинийКонтура
- FP*ID*ЛинийСетки
- FP*ID*Плиток
- FP*ID*Лонжеронов*Верх, FP_ID*Лонжеронов_Низ
- FP*ID*Стоек

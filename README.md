# RaisedFloor.extension

RU: pyRevit-расширение для автоматической раскладки фальшпола — оптимизация смещения сетки, размещение стрингеров, стоек и плиток по точному контуру зоны.

EN: A pyRevit extension for raised-floor layout — grid shift optimization, stringer/support/tile placement driven by the exact zone contour.

---

## Совместимость / Compatibility

RU:

- Скрипты проверены в Revit 2024, 2026.
- Семейства в текущем ZIP сохранены в Revit 2026 и требуют Revit 2026.
- Для поддержки Revit 2024 семейства нужно пересохранить в Revit 2024.
- Проверено в pyRevit 6.1.0.x.

EN:

- Scripts tested in Revit 2024, 2026.
- Families in the current ZIP are saved in Revit 2026 and require Revit 2026.
- To support Revit 2024, re-save families in Revit 2024.
- Verified in pyRevit 6.1.0.x.

---

## Быстрый старт / Quick Start

RU:

1. Добавьте папку `RaisedFloor.extension` в pyRevit: Extensions → Add Folder.
2. Выполните Reload pyRevit.
3. Загрузите семейства из папки `Families`:
   - `RF_Tile.rfa` — плитка
   - `RF_Stringer.rfa` — стрингер
   - `RF_Support.rfa` — стойка
4. Откройте вкладку **Фальшпол**.
5. Для подробной пользовательской инструкции — кнопка **7 Справка** или файл `RaisedFloor.tab/RaisedFloor.panel/README.md`.

EN:

1. Add the `RaisedFloor.extension` folder to pyRevit: Extensions → Add Folder.
2. Run Reload pyRevit.
3. Load families from the `Families` folder:
   - `RF_Tile.rfa` — tile
   - `RF_Stringer.rfa` — stringer
   - `RF_Support.rfa` — support post
4. Open the **Фальшпол** tab.
5. For the full user guide — use the **7 Справка** button or `RaisedFloor.tab/RaisedFloor.panel/README.md`.

---

## Порядок работы / Recommended Workflow

RU:

| № | Команда | Что делает |
| --- | --------- | ------------ |
| 1 | **Параметры** | Создаёт параметры RF_ в проекте |
| 2 | Подготовка → **Перекрытие** | Привязывает перекрытие, задаёт шаг и высоту |
| 3 | Подготовка → **Периметр** | Рисует контур зоны на плане |
| 4 | Подготовка → **Сетка** | Рисует сетку плитки |
| 5 | **Подобрать раскладку** | Ищет оптимальное смещение сетки |
| 6 | Стрингеры → **Разместить** | Расставляет верхние и нижние стрингеры |
| 7 | Стойки → **Разместить** | Расставляет стойки под стрингеры |
| 8 | Плитки → **Разместить** | Заполняет сетку плитками |

EN:

| # | Command | What it does |
| --- | --------- | -------------- |
| 1 | **Parameters** | Creates RF_ parameters in the project |
| 2 | Prepare → **Slab** | Links floor element, sets tile step and height |
| 3 | Prepare → **Contour** | Draws zone boundary on plan |
| 4 | Prepare → **Grid** | Draws tile grid on plan |
| 5 | **Find Layout Shift** | Searches for optimal grid offset |
| 6 | Stringers → **Place** | Places upper and lower stringers |
| 7 | Supports → **Place** | Places support posts under stringers |
| 8 | Tiles → **Place** | Fills grid with tile instances |

---

## Как это работает / How It Works

### 1. Подготовка / Setup

RU: Привязка перекрытия, построение контура зоны (внешняя граница + отверстия), отрисовка сетки плитки. Геометрия обрабатывается библиотекой Clipper2.

EN: Link floor slab, build zone contour (outer boundary + holes), draw tile grid. Geometry processed by Clipper2 library.

### 2. Подбор раскладки / Optimize Layout

RU: Трёхфазный оптимизатор автоматически перебирает смещения X/Y (грубый поиск → уточнение → округление подрезок) и выбирает вариант с минимумом проблемных плиток. Возвращает Top-10 лучших вариантов.

EN: Three-phase optimizer automatically sweeps X/Y offsets (coarse → refine → cut-round polish) and picks the variant with the fewest problematic tiles. Returns top-10 best candidates.

### 3. Стрингеры / Stringers

RU: Двухуровневая перпендикулярная система: верхние (несут плитку) + нижние (несут верхние) + контурная обвязка у стен и отверстий. Стыки в шахматном порядке для конструктивной прочности.

EN: Two-level perpendicular system: upper (carry tiles) + lower (carry uppers) + contour frames at walls and openings. Staggered joints for structural integrity.

### 4. Стойки / Supports

RU: Стойка на каждом конце нижнего стрингера + промежуточные с равным шагом (макс. 1000 мм). Дедупликация совпадающих точек.

EN: Support at every lower stringer endpoint + intermediate at equal spacing (max 1000 mm). Coincident points deduplicated.

### 5. Плитки / Tiles

RU: Каждая ячейка сетки пересекается с точным контуром (Clipper2), классифицируется (целая / подрез / L/T/U) и размещается с параметрами подреза и вырезов под колонны (до 3 групп).

EN: Each grid cell is intersected with the exact contour (Clipper2), classified (full / cut / L/T/U), and placed with cut dimensions and column voids (up to 3 groups).

---

## Возможности / Capabilities

RU:

- Точная оптимизация смещения с учётом контура, кратность подрезов 10 мм.
- Перестройка сетки и контура на видах плана.
- Размещение плиток: целые, простой подрез, сложный подрез (L/T/U).
- До 3 групп вырезов на экземпляр плитки (колонны).
- Шахматный порядок стыков стрингеров — конструктивная прочность.
- Двухуровневая система стрингеров с контурной обвязкой.
- Проверка высотного стека и предупреждения при размещении.

EN:

- Exact shift optimization with contour-aware ranking, cut rounding to 10 mm.
- Grid and contour redraw on plan views.
- Tile placement: full, simple-cut, complex-cut (L/T/U).
- Up to 3 void groups per tile instance (columns).
- Staggered stringer joints for structural integrity.
- Two-level stringer system with contour frames around walls and openings.
- Height-stack validation and placement safety warnings.

---

## Документация / Documentation

- Руководство пользователя / User guide: `RaisedFloor.tab/RaisedFloor.panel/README.md`
- Руководство разработчика / Developer guide: `docs/DEVELOPER_GUIDE.md`
- История изменений / Changelog: `CHANGELOG.md`

---

## Для разработчиков / For Developers

### Setup

```bash
git clone <repository-url>
cd RaisedFloor.extension

py -3.11 -m venv .venv
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\pip install -r requirements-dev.txt
```

### Tests

```bash
.venv\Scripts\python -m pytest tests/ -m "not revit" -v --cov=lib
```

### Code quality

```bash
.venv\Scripts\python -m ruff check lib/ tests/
.venv\Scripts\python -m mypy lib/ --ignore-missing-imports
```

### Project Structure

```text
RaisedFloor.extension/
├── lib/              # Core libraries (floor_common, floor_exact, floor_grid, floor_i18n, floor_ui, floor_utils)
├── RaisedFloor.tab/  # UI panel and scripts
├── tests/            # Unit tests (155+ tests, pytest)
├── docs/             # Developer guide
├── Families/         # RFA families
└── release/          # Release archives
```

### Contributing

1. Fork → create branch → commit → push → open Pull Request.
2. All tests must pass: `pytest tests/ -m "not revit"`.
3. Update `CHANGELOG.md` with your changes.

See [docs/DEVELOPER_GUIDE.md](docs/DEVELOPER_GUIDE.md) for detailed instructions.

---

## Именование / Naming Convention

RU: Расширение использует **единую англоязычную схему с префиксом `RF_`**:

EN: The extension uses a **unified English naming scheme with the `RF_` prefix**:

| Слой / Layer | Язык / Language | Пример / Example |
| --- | --- | --- |
| Папки расширения / Extension folders | EN | `RaisedFloor.tab`, `03_Stringers.pulldown` |
| Кнопки на ленте / Ribbon buttons | RU | Стрингеры, Плитки (через `bundle.yaml`) |
| Диалоги / Dialogs & messages | RU/EN авто / auto | `tr("shift_done")` |
| Семейства / Families | EN | `RF_Tile`, `RF_Stringer`, `RF_Support` |
| Параметры Revit / Revit parameters | EN | `RF_Step_X`, `RF_Floor_Height` |
| Стили линий / Line styles | EN | `RF_Grid`, `RF_Contour`, `RF_Base` |
| Группа параметров / Param group | EN | `RaisedFloor` |

---

## Лицензия / License

MIT — см. файл / see file [LICENSE](LICENSE).
